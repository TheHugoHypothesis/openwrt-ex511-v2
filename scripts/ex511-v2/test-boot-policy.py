#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline fixtures only: the SSH backend is replaced; no network or device IO."""
import importlib
import argparse
import fcntl
import contextlib
import io
import json
import re
import shlex
import shutil
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest import mock
import zlib

m = importlib.import_module('boot-policy')
geometry = importlib.import_module('validate-nss-build').PARTITIONS
PACKAGED_ROOTFS = None
QEMU = 'qemu-aarch64-static'


def image(values=None, tail=None):
    if values is None:
        values = {b'bootcmd': m.WRAPPER, b'baudrate': b'115200', b'opaque': b'keep-this-private'}
    data = b'\0'.join(k + b'=' + v for k, v in values.items()) + b'\0\0'
    data += bytes(m.ENV_SIZE - 4 - len(data))
    return struct.pack('<I', zlib.crc32(data)) + data + (tail or b'\xff' * (m.PART_SIZE-m.ENV_SIZE))


def layout(marker='opt-in', writable_env=True):
    lines = ['0', 'tplink,ex511-v2', marker, 'ubi.mtd=rootfs_1 root=/dev/ubiblock0_1']
    for i, (name, offset, size, _) in enumerate(geometry):
        flags = 0x400 if name == 'rootfs_1' or name == '0:APPSBLENV' and writable_env else 0
        lines.append(f'{i}|{name}|{flags:#x}|{offset}|{size}|131072|2048|0')
    return '\n'.join(lines)


class FakeSSH:
    def __init__(self):
        self.raw = image()
        self.report = layout()
        self.commands, self.ram, self.reads, self.writes = [], {}, 0, 0
        self.fail_write = self.mutate_after = self.race = self.race_locked = False

    def layout(self):
        return m.check_layout(self.report)

    def read(self, index):
        assert index == '7'
        self.reads += 1
        if self.race and self.reads == 2:
            v = m.parse_env(self.raw);v[b'opaque'] = b'changed concurrently';return image(v)
        return self.raw

    def run(self, command, data=None, timeout=30):
        self.commands.append(command)
        if command.startswith('umask 077; cat > '):
            self.ram[command.split(' > ')[1]] = data
        elif command.startswith('sha256sum '):
            return (m.digest(self.ram[command.split()[1]]) + '  RAM\n').encode()
        elif command.startswith('flock -n /var/lock/fw_printenv.lock '):
            if self.race_locked:
                values=m.parse_env(self.raw);values[b'opaque']=b'changed at lock';self.raw=image(values)
            expected_hash=re.search(r'[0-9a-f]{64}',command)[0]
            if m.digest(self.raw)!=expected_hash:raise ValueError('locked hash check refused')
            path = re.search(r' -s (/tmp/ex511-boot-policy-[0-9a-f]+/transaction)',command)[1]
            self.writes += 1
            values = m.parse_env(self.raw)
            for row in self.ram[path].splitlines():
                key, sep, value = row.partition(b' ')
                if sep:values[key] = value
                else:values.pop(key, None)
            if self.mutate_after:values[b'opaque'] = b'UNEXPECTED'
            self.raw = image(values, self.raw[m.ENV_SIZE:])
            if self.fail_write:raise OSError('simulated disconnect after possible write')
            return self.raw
        elif not (command.startswith('umask 077; mkdir ') or command.startswith('rm -f ')):
            raise AssertionError('Unexpected transport command: '+command)
        return b''


class BootPolicyTests(unittest.TestCase):
    def test_real_lock_contention_and_nested_tool(self):
        if PACKAGED_ROOTFS is None:
            self.skipTest('optional: --packaged-rootfs and QEMU')
        with tempfile.TemporaryDirectory(prefix='ex511-locked-region-') as t:
            folder=Path(t);env=folder/'env.bin';lock=folder/'env.lock'
            before=image();env.write_bytes(before[:m.ENV_SIZE])
            staging=Path('/tmp/ex511-boot-policy-'+m.secrets.token_hex(8));staging.mkdir(mode=0o700)
            try:
                (staging/'fw_env.config').write_text(str(env)+' 0x0 0x40000 0x20000 2\n')
                (staging/'transaction').write_bytes(m.script('openwrt'))
                argv=shlex.split(m.locked_write_command('7',m.digest(env.read_bytes()),str(staging)))
                argv[2]=str(lock)
                tool=shlex.join([QEMU,'-L',str(PACKAGED_ROOTFS),str(PACKAGED_ROOTFS/'usr/sbin/fw_setenv')])
                argv[-1]=argv[-1].replace('/dev/mtd7',shlex.quote(str(env)))
                argv[-1]=argv[-1].replace('fw_setenv -l ',tool+' -l ')
                with lock.open('wb') as handle:
                    fcntl.flock(handle,fcntl.LOCK_EX)
                    r=subprocess.run(argv,capture_output=True,timeout=10)
                    self.assertNotEqual(r.returncode,0)
                    self.assertEqual(env.read_bytes(),before[:m.ENV_SIZE])
                r=subprocess.run(argv,capture_output=True,timeout=15)
                self.assertEqual(r.returncode,0,r.stderr.decode())
                self.assertEqual(len(r.stdout),m.ENV_SIZE)
                actual=m.parse_env(r.stdout+before[m.ENV_SIZE:])
                self.assertEqual(actual,m.expected(m.parse_env(before),'openwrt'))
                self.assertTrue((staging/'fw_printenv.lock').is_file())
                cleaned=subprocess.run(['sh','-c',m.cleanup_command(str(staging))],capture_output=True,timeout=5)
                self.assertEqual(cleaned.returncode,0,cleaned.stderr.decode())
                self.assertFalse(staging.exists())
            finally:
                if staging.exists():shutil.rmtree(staging)

    def test_packaged_tool_environment_region_on_regular_file(self):
        if PACKAGED_ROOTFS is None:
            self.skipTest('optional: --packaged-rootfs and QEMU')
        with tempfile.TemporaryDirectory(prefix='ex511-fwenv-region-') as t:
            folder=Path(t);env=folder/'environment.bin';conf=folder/'fw_env.config'
            env.write_bytes(image()[:m.ENV_SIZE]);tail=image()[m.ENV_SIZE:]
            conf.write_text(str(env)+' 0x0 0x40000 0x20000 2\n')
            transaction=folder/'transaction'
            for policy in ['openwrt','stock']:
                before=env.read_bytes()+tail;transaction.write_bytes(m.script(policy))
                r=subprocess.run([QEMU,'-L',str(PACKAGED_ROOTFS),
                                  str(PACKAGED_ROOTFS/'usr/sbin/fw_setenv'),
                                  '-l',str(folder),'-c',str(conf),'-s',str(transaction)],
                                 capture_output=True,timeout=15)
                self.assertEqual(r.returncode,0,r.stderr.decode())
                self.assertEqual(len(env.read_bytes()),m.ENV_SIZE)
                # The regular-file backend replaces the configured region.
                # Appending the fixture tail here does not test NAND writes.
                actual=m.parse_env(env.read_bytes()+tail)
                self.assertEqual(actual,m.expected(m.parse_env(before),policy))

    def test_plan_and_roundtrip_both_policies(self):
        raw = image()
        for policy in ['stock', 'openwrt']:
            after = image(m.expected(m.parse_env(raw), policy))
            self.assertTrue(m.verify(raw, after, policy)['reserved_tail_unchanged'])
            self.assertNotIn('keep-this-private', json.dumps(m.plan(raw, policy)))
        self.assertEqual(m.script('stock'), b'tp_boot_idx\nex511_trial\n')
        self.assertEqual(m.script('openwrt'), b'tp_boot_idx 1\nex511_trial\n')

    def test_crc_truncation_duplicate_and_unknown_wrapper(self):
        raw = bytearray(image());raw[100] ^= 1
        for bad in [bytes(raw), image()[:-1], image({b'bootcmd': b'bootipq'})]:
            with self.assertRaises(ValueError):m.plan(bad, 'openwrt')
        data = b'bootcmd='+m.WRAPPER+b'\0bootcmd='+m.WRAPPER+b'\0\0'
        data += bytes(m.ENV_SIZE-4-len(data))
        with self.assertRaises(ValueError):m.parse_env(struct.pack('<I',zlib.crc32(data))+data+bytes(m.ENV_SIZE))

    def test_armed_or_unknown_slot_refused(self):
        for key, value in [(b'ex511_trial', b'1'), (b'tp_boot_idx', b'0'), (b'tp_boot_idx', b'2')]:
            values=m.parse_env(image());values[key]=value
            with self.assertRaises(ValueError):m.plan(image(values), 'stock')

    def test_unrelated_change_and_tail_corruption_refused(self):
        values=m.expected(m.parse_env(image()), 'openwrt');values[b'opaque']=b'wrong'
        with self.assertRaises(ValueError):m.verify(image(), image(values), 'openwrt')
        values=m.expected(m.parse_env(image()), 'openwrt')
        with self.assertRaises(ValueError):m.verify(image(), image(values, b'X'*m.ENV_SIZE), 'openwrt')

    def test_current_profile_and_wrong_geometry_refused_before_write(self):
        for report in [layout(marker='absent'), layout(writable_env=False),
                       layout().replace('|3145728|', '|3145729|'),
                       layout().replace('7|0:APPSBLENV|0x400|3145728|524288|131072|2048|0',
                                        '7|0:APPSBLENV|0x400|3145728|524288|131072|2048|1'),
                       layout().replace('ubi.mtd=rootfs_1', 'ubi.mtd=rootfs')]:
            with tempfile.TemporaryDirectory() as t:
                ssh=FakeSSH();ssh.report=report
                with self.assertRaises(ValueError):m.apply(ssh,m.plan(ssh.raw,'openwrt'),Path(t)/'backup')
                self.assertEqual(ssh.commands, []);self.assertEqual(ssh.reads,0)
        for i,(name,_,_,_) in enumerate(geometry):
            if name in ['0:APPSBLENV','rootfs_1']:continue
            lines=layout().splitlines();fields=lines[i+4].split('|');fields[2]='0x400';lines[i+4]='|'.join(fields)
            with self.assertRaises(ValueError):m.check_layout('\n'.join(lines))

    def test_one_batch_preserves_variables_and_no_reboot(self):
        with tempfile.TemporaryDirectory() as t:
            ssh=FakeSSH();out=Path(t)/'backup';result=m.apply(ssh,m.plan(ssh.raw,'openwrt'),out)
            self.assertTrue(result['exact_expected_variables'])
            self.assertEqual(ssh.writes,1)
            self.assertFalse(any('reboot' in c or 'mtd write' in c or 'unlock' in c for c in ssh.commands))
            self.assertEqual((out/'environment-before.bin').stat().st_mode & 0o777,0o600)
            self.assertTrue((out/'verified.json').is_file())
            self.assertTrue((out/'WRITE-INTENT.txt').is_file())

    def test_snapshot_cli_is_readonly_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as t:
            output=Path(t)/'snapshot.bin'
            argv=['boot-policy.py','snapshot','--host','198.51.100.1','--source','198.51.100.2','--known-hosts','fixture-only','--output',str(output)]
            ssh=FakeSSH()
            with mock.patch.object(m,'SSH',return_value=ssh), mock.patch('sys.argv',argv):
                with contextlib.redirect_stdout(io.StringIO()):m.main()
                self.assertEqual(output.read_bytes(),ssh.raw)
                self.assertEqual(output.stat().st_mode & 0o777,0o600)
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):m.main()
            self.assertEqual(ssh.writes,0)
            self.assertEqual(ssh.commands,[])
            output.unlink();ssh.report=layout(marker='absent')
            with mock.patch.object(m,'SSH',return_value=ssh), mock.patch('sys.argv',argv):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):m.main()
            self.assertFalse(output.exists())

    def test_already_selected_is_noop(self):
        with tempfile.TemporaryDirectory() as t:
            ssh=FakeSSH();result=m.apply(ssh,m.plan(ssh.raw,'stock'),Path(t)/'backup')
            self.assertFalse(result['environment_written']);self.assertEqual(ssh.commands,[])

    def test_stale_plan_and_concurrent_change(self):
        with tempfile.TemporaryDirectory() as t:
            ssh=FakeSSH();p=m.plan(ssh.raw,'openwrt');p['before_partition_sha256']='0'*64
            with self.assertRaises(ValueError):m.apply(ssh,p,Path(t)/'stale')
            self.assertFalse((Path(t)/'stale').exists())
            ssh=FakeSSH();ssh.race=True
            with self.assertRaises(ValueError):m.apply(ssh,m.plan(ssh.raw,'openwrt'),Path(t)/'race')
            self.assertEqual(ssh.writes,0)
            ssh=FakeSSH();ssh.race_locked=True
            with self.assertRaises(ValueError):m.apply(ssh,m.plan(ssh.raw,'openwrt'),Path(t)/'locked-race')
            self.assertEqual(ssh.writes,0)

    def test_cleanup_failure_does_not_mask_verified_write(self):
        class FailedCleanupSSH(FakeSSH):
            def run(self, command, data=None, timeout=30):
                if command.startswith('rm -f '):raise OSError('simulated RAM cleanup failure')
                return super().run(command, data, timeout)
        with tempfile.TemporaryDirectory() as t:
            ssh=FailedCleanupSSH();out=Path(t)/'backup'
            result=m.apply(ssh,m.plan(ssh.raw,'openwrt'),out)
            self.assertTrue(result['environment_written'])
            self.assertTrue(result['ram_cleanup_warning'])
            self.assertTrue((out/'verified.json').exists())
            self.assertTrue((out/'RAM-CLEANUP-FAILED.txt').exists())
            self.assertFalse((out/'OUTCOME-REQUIRES-INSPECTION.txt').exists())
            self.assertEqual(ssh.writes,1)

    def test_uncertain_write_not_retried_or_rolled_back(self):
        for kind in ['fail_write','mutate_after']:
            with tempfile.TemporaryDirectory() as t:
                ssh=FakeSSH();setattr(ssh,kind,True);out=Path(t)/'backup'
                with self.assertRaises((ValueError,OSError)):m.apply(ssh,m.plan(ssh.raw,'openwrt'),out)
                self.assertEqual(ssh.writes,1)
                self.assertTrue((out/'OUTCOME-REQUIRES-INSPECTION.txt').exists())
                self.assertTrue((out/'WRITE-INTENT.txt').exists())
                self.assertFalse((out/'verified.json').exists())


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packaged-rootfs',type=Path)
    parser.add_argument('--qemu',default=QEMU)
    args,remaining=parser.parse_known_args()
    PACKAGED_ROOTFS=args.packaged_rootfs.resolve() if args.packaged_rootfs else None
    QEMU=args.qemu
    unittest.main(argv=[__file__]+remaining)
