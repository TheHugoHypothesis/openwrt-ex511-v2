#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Test the EEPROM validator, RAM-only preparation and private BDF provisioning."""
import functools
import importlib.util
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'package/utils/ex511-v2-factory/src/caldata.c'
SHELL = shlex.split(os.environ.get('EX511_TEST_SHELL', 'bash'))
spec = importlib.util.spec_from_file_location('bdf_import', Path(__file__).with_name('import-stock-bdf.py'))
bdf_import = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bdf_import)


def eeprom():
    data = bytearray(131072)
    data[:4] = bytes.fromhex('01000404')
    data[0xe:0x14] = bytes.fromhex('021122334450')
    data[0x3e] = 0x40  # Preserve unrelated flag bits when selecting the MAC.
    checksum = functools.reduce(int.__xor__, struct.unpack('<65536H', data), 0) ^ 0xffff
    struct.pack_into('<H', data, 0xa, checksum)
    return bytes(data)


class RadioDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory(prefix='ex511-radio-tests-')
        cls.directory = Path(cls.work.name)
        cls.binary = cls.directory / 'ex511-v2-caldata'
        subprocess.run([os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        str(SOURCE), '-o', str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def run_tool(self, *args):
        return subprocess.run([str(self.binary), *map(str, args)], capture_output=True)

    def test_rejects_blank_truncated_corrupt_and_symlink_records(self):
        with tempfile.TemporaryDirectory(dir=self.directory) as directory:
            path = Path(directory) / 'cal'
            for data in [b'', b'\xff' * 131072, b'\0' * 131072, eeprom()[:-1], eeprom() + b'\0',
                         eeprom()[:100] + b'\x42' + eeprom()[101:]]:
                path.write_bytes(data)
                self.assertNotEqual(self.run_tool('--verify', path).returncode, 0)
            path.write_bytes(eeprom())
            self.assertEqual(self.run_tool('--verify', path).returncode, 0)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            self.assertNotEqual(self.run_tool('--verify', link).returncode, 0)

    def test_prepare_preserves_input_checksum_and_unrelated_bytes(self):
        with tempfile.TemporaryDirectory(dir=self.directory) as directory:
            source, output = Path(directory) / 'source', Path(directory) / 'output'
            source.write_bytes(eeprom())
            result = self.run_tool('--prepare', source, output, '02:11:22:33:44:52')
            self.assertEqual(result.returncode, 0, result.stderr)
            data = output.read_bytes()
            self.assertEqual(source.read_bytes(), eeprom())
            self.assertEqual(data[0xe:0x14], bytes.fromhex('021122334452'))
            self.assertEqual(data[0x3e], 0x41)
            self.assertTrue(bdf_import.valid_eeprom(data))
            allowed = {0xa, 0xb, 0x3e, 0x3f, *range(0xe, 0x14)}
            self.assertTrue(all(i in allowed for i, (a, b) in enumerate(zip(data, eeprom())) if a != b))
            self.assertNotEqual(self.run_tool('--prepare', source, output, '02:11:22:33:44:54').returncode, 0)
            self.assertEqual(output.read_bytes(), data)

    def test_invalid_mac_never_creates_output(self):
        with tempfile.TemporaryDirectory(dir=self.directory) as directory:
            source, output = Path(directory) / 'source', Path(directory) / 'output'
            source.write_bytes(eeprom())
            for mac in ['01:11:22:33:44:50', '00:00:00:00:00:00', '00:11:22:33:44:55',
                        '02:11:22:33:44', '02:11:22:33:44:5z', '02:11:22:33:44:50 extra']:
                self.assertNotEqual(self.run_tool('--prepare', source, output, mac).returncode, 0)
                self.assertFalse(output.exists())

    def test_radio_info_only_emits_bounded_country_fem_fields(self):
        with tempfile.TemporaryDirectory(dir=self.directory) as directory:
            path = Path(directory) / 'info'
            for text, valid in [('Other=fixture;Country=BR;FEM_MASK_5G=10;', True),
                                ('Country=US;FEM_MASK_5G=10_FCC;', True),
                                ('Country=BR;Country=DE;FEM_MASK_5G=10;', False),
                                ('Country=BR;FEM_MASK_5G=../../x;', False),
                                ('Country=BR;FEM_MASK_5G=10;FEM_MASK_5G=20;', False),
                                ('Country=BR;', False)]:
                path.write_bytes(text.encode().ljust(256, b'\0'))
                result = self.run_tool('--radio-info', path)
                self.assertEqual(result.returncode == 0, valid, result.stderr)
                if valid:
                    self.assertIn(result.stdout, [b'BR 10\n', b'US 10_FCC\n'])
                else:
                    self.assertEqual(result.stdout, b'')

    def test_private_import_container_keys_and_no_generic_fallback(self):
        with tempfile.TemporaryDirectory(dir=self.directory) as directory:
            work = Path(directory)
            stock = work / 'stock'
            path = stock / 'etc/board_data_files/5g/bdwlan_BR10.b5g'
            path.parent.mkdir(parents=True)
            path.write_bytes(eeprom())
            out = work / 'private'
            bdf_import.provision(stock, 'BR', '10', out)
            bdf_import.provision(stock, 'BR', '10', out)  # Idempotent, no replacement.
            container = (out / 'lib/firmware/ath11k/QCN6122/hw1.0/board-2.bin').read_bytes()
            self.assertEqual(container, bdf_import.board_container(eeprom()))
            staged = out / 'rootfs-overlay/lib/firmware/ath11k/QCN6122/hw1.0/board-2.bin'
            self.assertEqual(staged.read_bytes(), container)
            # Simulate the package postinst order used by prepare_rootfs.
            import shutil
            image = work / 'image'
            shutil.copytree(out, image)
            shutil.copytree(image / 'rootfs-overlay', image, dirs_exist_ok=True)
            self.assertEqual((image / 'lib/firmware/ath11k/QCN6122/hw1.0/board-2.bin').read_bytes(), container)
            self.assertIn(b'qmi-board-id=255,variant=TP-Link-EX511-v2', container)
            self.assertIn(b'qmi-board-id=96,variant=TP-Link-EX511-v2', container)
            self.assertEqual(container.count(eeprom()), 2)
            self.assertEqual((out / 'etc/ex511-v2-bdf-info').read_text(), 'BR 10\n')
            with self.assertRaises(ValueError):
                bdf_import.provision(stock, 'DE', '10', out)
            with self.assertRaises(ValueError):
                bdf_import.provision(stock, '../../', '10', out)
            (out / 'etc/ex511-v2-bdf-info').write_text('user work')
            with self.assertRaises(ValueError):
                bdf_import.provision(stock, 'BR', '10', out)

    def test_callback_matches_factory_bdf_and_uses_base_plus_two(self):
        base = ROOT / 'target/linux/qualcommax/ipq50xx/base-files/lib/functions'
        helper = (base / 'ex511-v2.sh').read_text()
        wifi = (base / 'ex511-v2-wifi.sh').read_text()
        system = (ROOT / 'package/base-files/files/lib/functions/system.sh').read_text()
        import re
        add_mac = re.search(r'macaddr_add\(\) \{.*?\n\}', system, re.S)[0]
        with tempfile.TemporaryDirectory(dir=self.directory) as directory:
            work = Path(directory)
            (work / '0x043A0000').write_bytes(eeprom())
            (work / '0x0434F100').write_bytes(bytes.fromhex('021122334450'))
            (work / '0x0434F700').write_bytes(b'Country=BR;FEM_MASK_5G=10;'.ljust(256, b'\0'))
            (work / 'bdf-info').write_text('BR 10\n')
            wifi = wifi.replace('/etc/ex511-v2-bdf-info', str(work / 'bdf-info'))
            wifi = wifi.replace('ex511-v2-caldata ', shlex.quote(str(self.binary)) + ' ')
            script = helper + '\n' + wifi + '\n' + add_mac + '''
get_mac_binary() { od -An -v -tx1 -N6 "$1" | tr -d ' \\n' | sed 's/\\(..\\)/\\1:/g; s/:$//'; }
'''
            script += '\nex511_v2_prepare_5g_cal "$1" "$2"\n'
            output = work / 'prepared'
            result = subprocess.run(SHELL + ['-c', script, 'test', str(work), str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_bytes()[0xe:0x14], bytes.fromhex('021122334452'))
            output.unlink()
            (work / 'bdf-info').write_text('DE 10\n')
            result = subprocess.run(SHELL + ['-c', script, 'test', str(work), str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
