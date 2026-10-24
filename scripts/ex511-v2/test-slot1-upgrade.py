#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise physical-slot guards with fixture sysfs and real fwtool/jshn; no device IO."""
import argparse
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'target/linux/qualcommax/ipq50xx/base-files'
HELPER = (BASE / 'lib/functions/ex511-v2-upgrade.sh').read_text()
PLATFORM = (BASE / 'lib/upgrade/platform.sh').read_text()
DISPATCH = re.search(r'^platform_do_upgrade\(\) \{.*?^\}', PLATFORM, re.M | re.S)[0]
GEOMETRY = importlib.import_module('validate-nss-build').PARTITIONS
TOOLS = None
SHELL = ['bash']


class Slot1UpgradeTests(unittest.TestCase):
    def fixture(self, *, mutation=None, marker=True, cmdline='ubi.mtd=rootfs_1 root=/dev/ubiblock0_1',
                compat='2.0', devices=None, corrupt=False, env_control=False):
        with tempfile.TemporaryDirectory(prefix='ex511-slot1-fixture-') as work:
            work = Path(work)
            marker_path = work / 'slot1-marker'
            if marker:
                marker_path.touch()
            env_marker = work / 'env-marker'
            if env_control:
                env_marker.touch()
            (work / 'cmdline').write_text(cmdline + '\n')
            for index, (label, offset, size, _) in enumerate(GEOMETRY):
                node = work / 'sys' / f'mtd{index}'
                node.mkdir(parents=True)
                values = {'flags': '0x400' if index == 14 or env_control and index == 7 else '0x0',
                          'size': str(size), 'erasesize': '131072', 'writesize': '2048',
                          'offset': str(offset)}
                for key, value in values.items():
                    (node / key).write_text(value + '\n')
            if mutation:
                index, key, value = mutation
                path = work / 'sys' / f'mtd{index}' / key
                if value is None:
                    path.unlink()
                else:
                    path.write_text(value + '\n')
            image = work / 'image.bin'
            image.write_bytes(b'EX511 fixture only; never a flash image\n')
            meta = work / 'metadata.json'
            meta.write_text(json.dumps({'compat_version': compat, 'new_supported_devices':
                                       devices if devices is not None else ['tplink,ex511-v2',
                                                                           'tplink,ex511-v2-slot1'] + (['tplink,ex511-v2-slot1-env'] if env_control else [])}))
            subprocess.run([str(TOOLS / 'bin/fwtool'), '-I', str(meta), str(image)], check=True)
            if corrupt:
                data = bytearray(image.read_bytes())
                data[-20] ^= 1
                image.write_bytes(data)
            helper = HELPER.replace('/sys/class/mtd', str(work / 'sys'))
            helper = helper.replace('/proc/device-tree/chosen/openwrt,ex511-slot1-layout', str(marker_path))
            helper = helper.replace('/proc/device-tree/chosen/openwrt,ex511-env-control', str(env_marker))
            helper = helper.replace('/proc/cmdline', str(work / 'cmdline'))
            helper = helper.replace('/usr/share/libubox/jshn.sh', str(TOOLS / 'share/libubox/jshn.sh'))
            script = '''
find_mtd_index() { case "$1" in rootfs) echo 13 ;; rootfs_1) echo 14 ;; 0:APPSBLENV) echo 7 ;; *) return 1 ;; esac; }
board_name() { echo tplink,ex511-v2; }
# A successful fixture records the destination; it never writes a device.
nand_do_upgrade() { echo "NAND:$CI_UBIPART:$CI_KERN_UBIPART:$CI_ROOT_UBIPART:$CI_DATA_UBIPART"; }
fw_setenv() { echo FORBIDDEN; return 1; }
mtd() { echo FORBIDDEN; return 1; }
set_bootconfig_primaryboot() { echo FORBIDDEN; return 1; }
remove_oem_ubi_volume() { echo FORBIDDEN; return 1; }
'''
            script += helper + '\n' + DISPATCH
            script += '\nplatform_do_upgrade ' + shlex.quote(str(image)) + '\n'
            env = dict(os.environ, PATH=str(TOOLS / 'bin') + os.pathsep + os.environ['PATH'])
            return subprocess.run(SHELL + ['-c', script], env=env, capture_output=True,
                                  text=True, timeout=15)

    def refused(self, **kwargs):
        result = self.fixture(**kwargs)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('NAND:', result.stdout)
        self.assertNotIn('FORBIDDEN', result.stdout)

    def test_valid_slot1_dispatch_only(self):
        result = self.fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'NAND:rootfs_1:rootfs_1:rootfs_1:rootfs_1')

    def test_env_control_dispatch_and_transition_metadata(self):
        result = self.fixture(env_control=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'NAND:rootfs_1:rootfs_1:rootfs_1:rootfs_1')
        # The installed protected-profile handler accepts the new image markers.
        result = self.fixture(devices=['tplink,ex511-v2', 'tplink,ex511-v2-slot1',
                                       'tplink,ex511-v2-slot1-env'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.refused(env_control=True, devices=['tplink,ex511-v2', 'tplink,ex511-v2-slot1'])
        self.refused(env_control=True, devices=['tplink,ex511-v2-slot1-env'])

    def test_env_control_protection_and_geometry(self):
        for change in [(7, 'flags', '0x0'), (7, 'offset', '3145729'),
                       (7, 'size', '262144'), (7, 'writesize', '4096'),
                       (7, 'erasesize', '4096'), (13, 'flags', '0x400'),
                       (2, 'flags', '0x400'), (14, 'flags', '0x0')]:
            with self.subTest(change=change):
                self.refused(env_control=True, mutation=change)

    def test_legacy_and_readonly_layouts_refused(self):
        self.refused(marker=False)
        self.refused(mutation=(14, 'flags', '0x0'))

    def test_protected_partition_writability_refused(self):
        for index in range(17):
            if index != 14:
                with self.subTest(index=index):
                    self.refused(mutation=(index, 'flags', '0x400'))

    def test_geometry_and_unknown_flags_refused(self):
        for change in [(13, 'offset', '57278464'), (14, 'offset', '19136512'),
                       (14, 'size', '999'), (13, 'erasesize', '4096'),
                       (7, 'flags', None), (14, 'flags', '0xc00')]:
            with self.subTest(change=change):
                self.refused(mutation=change)

    def test_wrong_or_ambiguous_boot_arguments_refused(self):
        for command in ['', 'ubi.mtd=rootfs', 'ubi.mtd=rootfs_1 ubi.mtd=rootfs',
                        'ubi.mtd=rootfs_1 ubi.mtd=rootfs_1', 'ubi.mtd=14']:
            with self.subTest(command=command):
                self.refused(cmdline=command)

    def test_foreign_or_legacy_image_metadata_refused(self):
        for compat, devices in [('1.0', None), ('2.1', None),
                                ('2.0', ['tplink,ex511-v2']), ('2.0', [])]:
            with self.subTest(compat=compat, devices=devices):
                self.refused(compat=compat, devices=devices)

    def test_corrupt_metadata_refused(self):
        self.refused(corrupt=True)

    def test_legacy_bootconfig_writer_removed(self):
        self.assertNotIn('tplink_ex511_set_primaryboot', PLATFORM)
        self.assertNotIn('tplink_ex511_pre_upgrade', PLATFORM)
        self.assertNotIn('fw_setenv', HELPER)
        self.assertIn('jshn mktemp', PLATFORM)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-tools', type=Path, required=True,
                        help='OpenWrt staging_dir/host, containing fwtool and jshn')
    parser.add_argument('--shell', default='bash', help='shell command, optionally QEMU + target ash')
    args, remaining = parser.parse_known_args()
    TOOLS = args.host_tools.resolve()
    SHELL = shlex.split(args.shell)
    unittest.main(argv=[__file__] + remaining)
