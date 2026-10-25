#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise MAC parsing and read-only UBI handling with local fixtures only."""
import argparse
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'target/linux/qualcommax/ipq50xx/base-files'
HELPER = (BASE / 'lib/functions/ex511-v2.sh').read_text()
SYSTEM = (ROOT / 'package/base-files/files/lib/functions/system.sh').read_text()
NETWORK = (BASE / 'etc/board.d/02_network').read_text()
SHELL = ['bash']


class FactoryMacTests(unittest.TestCase):
    def run_fixture(self, record=b'\x02\x11\x22\x33\x44\x50', *, existing=False,
                    flags='0x0', ro_mode='1', fail='', symlink=False):
        with tempfile.TemporaryDirectory(prefix='ex511-mac-fixture-') as work:
            fixture = Path(work)
            (fixture / 'sys/class/mtd/mtd11').mkdir(parents=True)
            (fixture / 'sys/class/ubi/ubi7').mkdir(parents=True)
            if flags is not None:
                (fixture / 'sys/class/mtd/mtd11/flags').write_text(flags + '\n')
            (fixture / 'sys/class/ubi/ubi7/ro_mode').write_text(ro_mode + '\n')
            if record is not None:
                (fixture / 'record').write_bytes(record)
            if existing:
                (fixture / 'attached').touch()
            script = r'''
find_mtd_index() { [ "$1" = misc_data_ro ] && echo 11; }
nand_find_ubi() {
    [ "$fail" != discover ] && [ -e "$fixture/attached" ] && echo ubi7
}
ubiattach() {
    echo "attach $*" >> "$fixture/calls"
    [ "$fail" != attach ] || return 1
    touch "$fixture/attached"
}
ubidetach() {
    echo "detach $*" >> "$fixture/calls"
    rm "$fixture/attached"
}
mount() {
    echo "mount $*" >> "$fixture/calls"
    [ "$fail" != mount ] || return 1
    for last; do :; done
    if [ -f "$fixture/record" ]; then
        if [ "$symlink" = yes ]; then
            ln -s "$fixture/record" "$last/0x0434F100"
        else
            cp "$fixture/record" "$last/0x0434F100"
        fi
    fi
}
umount() {
    echo "umount $*" >> "$fixture/calls"
    [ "$fail" != umount ] || return 1
    rm -f "$1/0x0434F100"
}
# Format real fixture bytes; the production get_mac_binary uses hexdump.
get_mac_binary() {
    od -An -v -tx1 -N6 "$1" | tr -d ' \n' |
        sed 's/\(..\)/\1:/g; s/:$//'
}
'''
            script += HELPER.replace('/sys/class/', str(fixture) + '/sys/class/').replace(
                '/tmp/lock', str(fixture / 'lock'))
            script += '\nex511_v2_get_factory_mac\n'
            script = '\n'.join([
                'fixture=' + shlex.quote(str(fixture)),
                'fail=' + shlex.quote(fail),
                'symlink=' + ('yes' if symlink else 'no'), script,
            ])
            result = subprocess.run(SHELL + ['-c', script], text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            calls = (fixture / 'calls').read_text() if (fixture / 'calls').exists() else ''
            # There are no real mounts. Clean up a simulated unmount failure.
            for line in calls.splitlines():
                if line.startswith('mount '):
                    mountpoint = Path(line.split()[-1])
                    if mountpoint.exists():
                        (mountpoint / '0x0434F100').unlink(missing_ok=True)
                        mountpoint.rmdir()
            return result, calls

    def test_new_attachment(self):
        result, calls = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), '02:11:22:33:44:50')
        self.assertIn('attach -m 11\n', calls)
        self.assertIn('mount -t ubifs -o ro,noatime ubi7:misc_ro ', calls)
        self.assertIn('umount ', calls)
        self.assertIn('detach -m 11\n', calls)

    def test_existing_attachment_is_preserved(self):
        result, calls = self.run_fixture(existing=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('attach ', calls)
        self.assertNotIn('detach ', calls)
        self.assertIn('umount ', calls)

    def test_writable_or_unknown_mtd_is_refused_before_attach(self):
        for flags in ('0x400', '0xc00', None):
            with self.subTest(flags=flags):
                result, calls = self.run_fixture(flags=flags)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertEqual(calls, '')

    def test_writable_ubi_is_refused_before_mount(self):
        result, calls = self.run_fixture(existing=True, ro_mode='0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertEqual(calls, '')

    def test_invalid_or_missing_records(self):
        records = [None, b'', b'\0' * 6, b'\xff' * 6,
                   b'\x01\x11\x22\x33\x44\x50',
                   b'\x02\x11\x22\x33\x44', b'\x02\x11\x22\x33\x44\x50\x00',
                   bytes.fromhex('001122334455'), bytes.fromhex('001122334456')]
        for record in records:
            with self.subTest(record=record):
                result, calls = self.run_fixture(record)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertIn('umount ', calls)
                self.assertIn('detach -m 11\n', calls)

    def test_record_symlink_is_refused(self):
        result, calls = self.run_fixture(symlink=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('detach -m 11\n', calls)

    def test_attach_and_mount_failures(self):
        for fail in ('attach', 'mount', 'discover'):
            with self.subTest(fail=fail):
                result, calls = self.run_fixture(fail=fail)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertNotIn('umount ', calls)
                if fail == 'attach':
                    self.assertNotIn('detach ', calls)
                else:
                    self.assertIn('detach -m 11\n', calls)

    def test_failed_unmount_never_detaches_a_mounted_volume(self):
        result, calls = self.run_fixture(fail='umount')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('detach ', calls)

    def test_concurrent_factory_readers_serialize_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='ex511-concurrent-readers-') as directory:
            fixture = Path(directory)
            (fixture / 'sys/class/mtd/mtd11').mkdir(parents=True)
            (fixture / 'sys/class/ubi/ubi7').mkdir(parents=True)
            (fixture / 'sys/class/mtd/mtd11/flags').write_text('0x0\n')
            (fixture / 'sys/class/ubi/ubi7/ro_mode').write_text('1\n')
            script = 'fixture=' + shlex.quote(str(fixture)) + '\n' + r'''
find_mtd_index() { echo 11; }
nand_find_ubi() { [ -e "$fixture/attached" ] && echo ubi7; }
ubiattach() { touch "$fixture/attached"; }
ubidetach() { rm "$fixture/attached"; }
mount() { echo mounted >> "$fixture/calls"; }
umount() { echo unmounted >> "$fixture/calls"; }
reader() { sleep 0.1; }
'''
            script += HELPER.replace('/sys/class/', str(fixture) + '/sys/class/').replace(
                '/tmp/lock', str(fixture / 'lock'))
            script += '\nex511_v2_with_factory reader\n'
            processes = [subprocess.Popen(SHELL + ['-c', script], stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE) for _ in range(2)]
            for process in processes:
                _, error = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, error)
            self.assertEqual((fixture / 'calls').read_text().splitlines(),
                             ['mounted', 'unmounted', 'mounted', 'unmounted'])
            self.assertFalse((fixture / 'attached').exists())

    def run_board(self, board, mac):
        source = NETWORK.split('board_config_update\n', 1)[0]
        source = re.sub(r'^\s*\. /lib/[^\n]+', '\n:', source, flags=re.M)
        add = re.search(r'macaddr_add\(\) \{.*?\n\}', SYSTEM, re.S)[0]
        mocks = r'''
ex511_v2_get_factory_mac() { [ -n "$test_mac" ] && echo "$test_mac"; }
ucidef_set_interface_macaddr() { echo "$1=$2"; }
ucidef_set_label_macaddr() { echo "label=$1"; }
ucidef_set_network_device_mac() { echo "device:$1=$2"; }
ucidef_add_wlan() { echo "wlan:$*"; }
logger() { :; }
'''
        script = source + '\n' + add + '\n' + mocks
        script += '\ntest_mac=' + shlex.quote(mac)
        script += '\nipq50xx_setup_macs ' + shlex.quote(board)
        return subprocess.run(SHELL + ['-c', script], text=True, capture_output=True)

    def test_other_board_mount_hook_leaves_ex511_to_validated_helper(self):
        hook = (BASE / 'lib/preinit/09_mount_misc_ro').read_text()
        hook = hook.replace('. /lib/functions.sh', '')
        # Fail before touching any real sysfs, UBI device or mount point.
        for board, expected in [('tplink,ex511-v2', ''),
                                ('glinet,gl-b3000', ''),
                                ('tplink,mx515v-v1', 'lookup\n')]:
            with self.subTest(board=board):
                script = ('board_name() { echo ' + shlex.quote(board) + '; }\n'
                          'boot_hook_add() { :; }\n'
                          'find_mtd_index() { echo lookup >&2; return 1; }\n')
                result = subprocess.run(SHELL + ['-c', script + hook + '\nmount_misc_ro'],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, expected)

    def test_board_lan_wan_and_label(self):
        result = self.run_board('tplink,ex511-v2', '02:11:22:33:44:50')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            'lan=02:11:22:33:44:50', 'wan=02:11:22:33:44:51', 'label=02:11:22:33:44:50',
            'device:eth0=02:11:22:33:44:50',
            'wlan:platform/soc@0/c000000.wifi platform/soc/c000000.wifi macaddr_base=02:11:22:33:44:50',
            'wlan:platform/soc@0/b00a040.wifi platform/soc/b00a040.wifi macaddr_base=02:11:22:33:44:52'])

    def test_wan_increment_carry(self):
        result = self.run_board('tplink,ex511-v2', '02:11:22:ff:ff:ff')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('wan=02:11:22:00:00:00\n', result.stdout)

    def test_missing_mac_or_other_board_sets_no_addresses(self):
        for board, mac in [('tplink,ex511-v2', ''), ('glinet,gl-b3000', '02:11:22:33:44:50')]:
            with self.subTest(board=board):
                result = self.run_board(board, mac)
                self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell', default='bash', help='shell command, e.g. "busybox ash"')
    args = parser.parse_args()
    SHELL = shlex.split(args.shell)
    unittest.main(argv=[__file__], verbosity=2)
