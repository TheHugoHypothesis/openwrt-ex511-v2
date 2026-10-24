#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Test boot-time MAC sequencing and wifi-detect using fixture I/O only."""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
PREINIT = ROOT / 'target/linux/qualcommax/ipq50xx/base-files/lib/preinit/09_ex511_factory_mac'
DETECT = ROOT / 'package/network/config/wifi-scripts/files/lib/wifi/mac80211.uc'
UCODE = ['ucode']
SHELL = ['bash']


class PreinitTests(unittest.TestCase):
    def run_fixture(self, board='tplink,ex511-v2', mac='02:11:22:33:44:50',
                    node='/soc@0/ethernet@39d00000'):
        # Replace library loading and system calls; execute the actual hook body.
        source = re.sub(r'^\s*\. /lib/[^\n]+', '\n:', PREINIT.read_text(), flags=re.M)
        mocks = r'''
board_name() { echo "$fixture_board"; }
ex511_v2_get_factory_mac() { [ -n "$fixture_mac" ] && echo "$fixture_mac"; }
readlink() { echo "$fixture_node"; }
ip() { echo "ip $*"; }
boot_hook_add() { :; }
'''
        env = '\n'.join(f'fixture_{key}={shlex.quote(value)}'
                        for key, value in [('board', board), ('mac', mac), ('node', node)])
        return subprocess.run(SHELL + ['-c', env + '\n' + mocks + source +
                                      '\nex511_v2_preinit_mac\n'],
                              capture_output=True, text=True)

    def test_expected_conduit_gets_factory_address(self):
        result = self.run_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'ip link set dev eth0 address 02:11:22:33:44:50\n')

    def test_no_changes_for_other_board_missing_mac_or_wrong_conduit(self):
        for fields in [{'board': 'tplink,archer-ax55-v1'}, {'mac': ''},
                       {'node': ''}, {'node': '/soc@0/ethernet@39c00000'}]:
            with self.subTest(fields=fields):
                result = self.run_fixture(**fields)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, '')


class WifiDetectTests(unittest.TestCase):
    def run_fixture(self, bases=('02:11:22:33:44:50', '02:11:22:33:44:52'), config=None):
        board = {'wlan': {}}
        for index, (band, address, base) in enumerate(zip(
                ['2G', '5G'], ['c000000', 'b00a040'], bases)):
            phy = {'path': f'platform/soc@0/{address}.wifi',
                   'info': {'bands': {band: {'max_width': 80, 'he': True}}}}
            if base is not None:
                phy['macaddr_base'] = base
            board['wlan'][f'phy{index}'] = phy
        # Keep the complete production control flow, substituting only external
        # board/sysfs/UCI inputs. No real /etc or network device is accessed.
        source = DETECT.read_text().replace('import { readfile } from "fs";', '''
function readfile(path) {
    if (path == "/etc/board.json") return sprintf('%J', fixture_board);
    return "02:aa:bb:cc:dd:ee\\n";
}
''').replace("import * as uci from 'uci';", '''
const uci = { cursor: () => ({ get_all: () => fixture_config }) };
''')
        result = subprocess.run(UCODE + ['-D', 'fixture_board=' + json.dumps(board),
                                        '-D', 'fixture_config=' + json.dumps(config or {}),
                                        '-e', source], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_per_radio_factory_bases(self):
        output = self.run_fixture()
        self.assertIn("set wireless.radio0.macaddr_base='02:11:22:33:44:50'", output)
        self.assertIn("set wireless.radio1.macaddr_base='02:11:22:33:44:52'", output)
        self.assertEqual(output.count('commit wireless'), 1)

    def test_existing_configuration_is_preserved(self):
        output = self.run_fixture(config={'custom': {
            '.type': 'wifi-device', 'path': 'platform/soc@0/c000000.wifi',
            'macaddr_base': '02:ff:ee:dd:cc:bb'}})
        self.assertNotIn('c000000.wifi', output)
        self.assertNotIn('02:11:22:33:44:50', output)
        self.assertIn(".macaddr_base='02:11:22:33:44:52'", output)

    def test_path_lookup_retains_base_when_phy_enumeration_changes(self):
        detect = (ROOT / 'package/network/config/wifi-scripts/files/usr/share/hostap/wifi-detect.uc').read_text()
        # Exercise the actual upstream path matcher and metadata lookup.
        functions = detect[detect.index('function wiphy_path_match('):
                           detect.index('function freq_to_channel(')]
        board = {'wlan': {'wl0': {
            'path': ['platform/soc@0/c000000.wifi', 'platform/soc/c000000.wifi'],
            'macaddr_base': '02:11:22:33:44:50'}}}
        script = 'let board_data = fixture_board;\n' + functions
        script += "print(sprintf('%J', wiphy_get_entry('phy9', 'platform/soc/c000000.wifi')));"
        result = subprocess.run(UCODE + ['-D', 'fixture_board=' + json.dumps(board),
                                        '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['macaddr_base'], '02:11:22:33:44:50')

    def test_optional_or_invalid_bases_do_not_inject_configuration(self):
        for bases in [(None, None), ("'; set evil='yes", 'invalid')]:
            with self.subTest(bases=bases):
                output = self.run_fixture(bases=bases)
                self.assertNotIn('macaddr_base', output)
                self.assertNotIn('evil', output)
                self.assertEqual(output.count('=wifi-device'), 2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ucode', default='ucode', help='ucode command, optionally QEMU + binary')
    parser.add_argument('--shell', default='bash')
    args = parser.parse_args()
    UCODE = shlex.split(args.ucode)
    SHELL = shlex.split(args.shell)
    unittest.main(argv=[__file__], verbosity=2)
