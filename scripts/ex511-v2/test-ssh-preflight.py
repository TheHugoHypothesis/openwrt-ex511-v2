#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Fail-closed fixtures for SSH metadata/FIT assessment. No router access."""
import importlib.util
import lzma
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

spec = importlib.util.spec_from_file_location('assessment', Path(__file__).with_name('assess-ssh-trial.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def cstr(value):
    return value.encode() + b'\0'


def be(*values):
    return struct.pack('>' + 'I' * len(values), *values)


def fdt(nodes):
    """Minimal fixture encoder; exercise the real binary parser and hash checks."""
    strings, body = bytearray(), bytearray()

    def align(blob):
        return blob + bytes((-len(blob)) % 4)

    def node(path):
        name = path.rsplit('/', 1)[-1]
        body.extend(be(1) + align(cstr(name)))
        for name, value in nodes[path].items():
            offset = len(strings)
            strings.extend(cstr(name))
            body.extend(be(3, len(value), offset) + align(value))
        for child in nodes:
            if child != '/' and child.rsplit('/', 1)[0] == path.rstrip('/'):
                node(child)
        body.extend(be(2))

    node('/')
    body.extend(be(9))
    header = be(0xd00dfeed, 56 + len(body) + len(strings), 56,
                56 + len(body), 40, 17, 16, 0, len(strings), len(body))
    return header + bytes(16) + body + strings


def fixture_fit(readonly=True, geometry_error=False, damaged=False, load=0x41000000):
    dtb = {'/': {'compatible': cstr('tplink,ex511-v2')}, '/chosen': {}, '/partitions': {}}
    for i, (label, geometry) in enumerate(a.PARTITIONS.items()):
        props = {'label': cstr(label), 'reg': be(*geometry)}
        if readonly:
            props['read-only'] = b''
        if geometry_error and label == '0:ART':
            props['reg'] = be(0x4c0000, 0x80000)
        dtb['/partitions/partition@' + str(i)] = props
    image = bytes(56) + b'ARMd' + bytes(4)
    kernel = lzma.compress(image, format=lzma.FORMAT_ALONE)
    nodes = {'/': {}, '/images': {}, '/configurations': {},
             '/configurations/config@mp03.3': {'kernel': cstr('kernel'), 'fdt': cstr('dtb')}}
    for name, data in [('kernel', kernel), ('dtb', fdt(dtb))]:
        nodes['/images/' + name] = {'data': data, 'arch': cstr('arm64'),
                                   'compression': cstr('lzma' if name == 'kernel' else 'none'),
                                   'load': be(load), 'entry': be(load)}
        nodes['/images/' + name + '/hash'] = {'algo': cstr('crc32'),
                                            'value': be(zlib.crc32(data) ^ int(damaged))}
    return fdt(nodes)


class AssessmentTests(unittest.TestCase):
    def stock(self, root, slot=0, attached=False):
        # Deliberately different MTD indices: target lookup must use labels.
        (root / 'identity.txt').write_text('Uid:\t0\t0\t0\t0\nLinux EX511 4.4.60 armv7l\n'
            'mtd8: 02460000 00020000 "rootfs"\n'
            'mtd9: 02460000 00020000 "rootfs_1"\n')
        (root / 'boot-selection.txt').write_text(
            f'/proc/boot_info/rootfs/primaryboot\n{slot}\n'
            f'/proc/boot_info/rootfs/upgradepartition\n{"rootfs" if slot else "rootfs_1"}\nbootcmd=bootipq\n')
        (root / 'tools.txt').write_text('/bin/ubiformat\n')
        (root / 'ubi.txt').write_text(
            f'/sys/class/ubi/ubi0\nmtd_num\n{8 + slot}\n'
            '/sys/class/ubi/ubi0_1\nname\nkernel\nusable_eb_size\n126976\n'
            'reserved_ebs\n50\ncorrupted\n0\nupd_marker\n0\n' +
            (f'/sys/class/ubi/ubi1\nmtd_num\n{9 - slot}\n' if attached else ''))

    def test_slot_selection_uses_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for slot, target in [(0, 9), (1, 8)]:
                self.stock(root, slot)
                self.assertEqual(a.stock_metadata(root)['inactive_mtd_index_observed'], target)

    def test_refuse_attached_inactive_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.stock(root, attached=True)
            with self.assertRaisesRegex(ValueError, 'attached'):
                a.stock_metadata(root)

    def test_refuse_nonroot_or_inconsistent_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.stock(root)
            p = root / 'identity.txt'
            p.write_text(p.read_text().replace('Uid:\t0\t0', 'Uid:\t0\t1000'))
            with self.assertRaisesRegex(ValueError, 'effective stock root'):
                a.stock_metadata(root)
            self.stock(root)
            p = root / 'boot-selection.txt'
            p.write_text(p.read_text().replace('partition\nrootfs_1', 'partition\nrootfs'))
            with self.assertRaisesRegex(ValueError, 'disagree'):
                a.stock_metadata(root)

    def test_refuse_corrupt_fit(self):
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            a.fit_metadata(fixture_fit(damaged=True))

    def test_protect_factory_partition_geometry(self):
        with self.assertRaisesRegex(ValueError, 'geometry mismatch: 0:ART'):
            a.fit_metadata(fixture_fit(geometry_error=True))

    def test_readonly_vs_writable_and_no_install_approval(self):
        fit = a.fit_metadata(fixture_fit())
        config = ('# CONFIG_MTD_CMDLINE_PARTS is not set\n'
                  '# CONFIG_MTD_PARTITIONED_MASTER is not set\n'
                  'CONFIG_BLK_DEV_INITRD=y\nCONFIG_INITRAMFS_SOURCE="rootfs"\n')
        stock = {'leb_bytes': 126976, 'active_kernel_capacity_bytes': 6348800,
                 'firmware_slot_bytes': 38141952, 'erase_bytes': 131072}
        report = a.assess(stock, fit, config)
        self.assertFalse(report['offline_blockers'])
        self.assertEqual(report['status'], 'not_authorized_for_flash')
        report = a.assess(stock, a.fit_metadata(fixture_fit(readonly=False)), config)
        self.assertTrue(report['offline_blockers'])
        fit['bootargs_append'] = ' root=/dev/ubiblock0_1'
        self.assertTrue(a.assess(stock, fit, config)['offline_blockers'])
        self.assertTrue(a.assess(stock, a.fit_metadata(fixture_fit()), '')['offline_blockers'])

    def test_bad_load_and_input_overlap(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            a.fit_metadata(fixture_fit(load=0x50000000))
        self.assertTrue(a.fit_metadata(fixture_fit(load=0x44000000))['kernel_overlaps_stock_fit_input'])


if __name__ == '__main__':
    unittest.main()
