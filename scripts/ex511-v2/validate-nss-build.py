#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check compiled NSS EX511 DTB and, optionally, the assembled root filesystem."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from fdt import read_fdt, cells

PARTITIONS = [
    ('0:SBL1', 0x0, 0x80000, True),
    ('0:MIBIB', 0x80000, 0x80000, True),
    ('0:BOOTCONFIG', 0x100000, 0x40000, False),
    ('0:BOOTCONFIG1', 0x140000, 0x40000, False),
    ('0:QSEE', 0x180000, 0x100000, True),
    ('0:DEVCFG', 0x280000, 0x40000, True),
    ('0:CDT', 0x2c0000, 0x40000, True),
    ('0:APPSBLENV', 0x300000, 0x80000, False),
    ('0:APPSBL', 0x380000, 0x140000, True),
    ('0:ART', 0x4c0000, 0x100000, True),
    ('0:TRAINING', 0x5c0000, 0x80000, True),
    ('misc_data_ro', 0x640000, 0x600000, True),
    ('misc_data_rw', 0xc40000, 0x600000, False),
    ('rootfs', 0x1240000, 0x2460000, False),
    ('rootfs_1', 0x36a0000, 0x2460000, False),
    ('misc_data_rwbak', 0x5b00000, 0x600000, True),
    ('misc_data_isp', 0x6100000, 0x600000, True),
]


def validate_dtb(path, readonly_trial=False, slot1=False, env_control=False):
    assert not env_control or slot1, "Environment control requires physical slot1"
    nodes = read_fdt(path.read_bytes())
    def node(suffix):
        matches = [(name, props) for name, props in nodes.items() if name.endswith('/' + suffix)]
        assert len(matches) == 1, (suffix, matches)
        return matches[0]

    assert b'tplink,ex511-v2\0' in nodes['/']['compatible']
    gmac_path, gmac = node('ethernet@39d00000')
    switch_path, switch = node('switch@1d')
    cpu_path, cpu = node('switch@1d/ports/port@6')
    for name, props in [(gmac_path, gmac), (cpu_path, cpu)]:
        assert props['phy-mode'] == b'sgmii\0', name
        link = nodes[name + '/fixed-link']
        assert cells(link['speed']) == [1000] and 'full-duplex' in link, name
    assert cells(cpu['ethernet']) == cells(gmac['phandle'])
    assert cells(switch['reg']) == [29]
    # The legacy headerless DTS flag is not consumed by this driver;
    # it cannot establish the runtime topology. Test startup selection
    # separately and validate tagger switching/isolation on hardware.
    # GPIO33 active-low, retaining the tested upstream reset wiring.
    assert cells(switch['reset-gpios'])[1:] == [33, 1]
    for index, label in enumerate(['wan', 'lan1', 'lan2', 'lan3', 'lan4']):
        port = nodes[f'{switch_path}/ports/port@{index}']
        assert port['label'] == (label + '\0').encode()
        assert 'phy-handle' in port
    for radio in ['wifi@c000000', 'wifi@b00a040']:
        _, props = node(radio)
        assert props['status'] == b'okay\0'
        assert cells(props['qcom,ath11k-fw-memory-mode']) == [2]
        assert props['qcom,ath11k-calibration-variant'] == b'TP-Link-EX511-v2\0'
        assert 'nvmem-cells' not in props
    assert 'nvmem-cells' not in gmac
    parts = {}
    for name, props in nodes.items():
        if '/partitions/partition@' in name and 'label' in props:
            parts[props['label'].rstrip(b'\0').decode()] = props
    assert len(parts) == len(PARTITIONS)
    for label, offset, size, readonly in PARTITIONS:
        props = parts[label]
        assert cells(props['reg']) == [offset, size], label
        expected = (label not in (['rootfs_1', '0:APPSBLENV'] if env_control else ['rootfs_1'])) if slot1 else (readonly or readonly_trial)
        assert ('read-only' in props) == expected, label
        assert offset + size <= 128 * 1024 * 1024, label
    assert not any('hw_mac_addr@' in name for name in nodes)
    print('PASS: compiled 1G SGMII/NSS topology, radios, factory-data consumers and 17 partitions')
    if slot1:
        assert 'openwrt,ex511-slot1-layout' in nodes['/chosen']
        assert nodes['/chosen']['bootargs-append'] == b' root=/dev/ubiblock0_1 swiotlb=1 coherent_pool=512K\0'
        assert ('openwrt,ex511-env-control' in nodes['/chosen']) == env_control
        if env_control:
            print('PASS: only physical rootfs_1 and APPSBLENV writable; stock and other boot metadata protected')
        else:
            print('PASS: only physical rootfs_1 is writable; stock slot 0 and all boot metadata protected')
    elif readonly_trial:
        assert nodes['/chosen']['bootargs-append'] == b' swiotlb=1 coherent_pool=512K\0'
        print('PASS: diagnostic DTB makes all 17 NAND partitions read-only')
    else:
        print('NOTE: inherited BOOTCONFIG/APPSBLENV/rootfs writability is retained; no writes were tested')


def validate_rootfs(root, private):
    root = root.resolve()
    def installed(relative):
        # Alternatives use absolute symlinks interpreted inside the image,
        # not against the workstation's /usr/bin.
        path = root / relative
        for _ in range(8):
            if not path.is_symlink():
                return path.is_file()
            target = path.readlink()
            path = root / str(target).lstrip('/') if target.is_absolute() else path.parent / target
        raise AssertionError(f'rootfs symlink loop: {relative}')

    for path in [
        'usr/bin/ex511-v2-caldata', 'usr/bin/flock', 'usr/sbin/ubiattach',
        'usr/sbin/ubidetach', 'lib/functions/ex511-v2.sh',
        'lib/functions/ex511-v2-upgrade.sh', 'usr/bin/jshn', 'usr/bin/fwtool',
        'lib/functions/ex511-v2-wifi.sh', 'lib/preinit/09_ex511_factory_mac',
        'etc/init.d/nss', 'usr/sbin/fw_setenv', 'usr/sbin/fw_printenv',
    ]:
        assert installed(path), path
    for module in ['qca-dwmac-nss', 'qca-nss-drv', 'ecm', 'qca-dsa-nss',
                   'ath11k', 'ath11k_ahb', 'rtl8365mb', 'realtek_dsa']:
        assert list((root / 'lib/modules').rglob(module + '.ko*')), module
    assert list((root / 'lib/firmware').rglob('qca-nss*.bin')), 'NSS firmware'
    source = (root / 'lib/wifi/mac80211.uc').read_text()
    assert 'set ${s}.macaddr_base=' in source
    if private:
        marker = (root / 'etc/ex511-v2-bdf-info').read_text().split()
        assert len(marker) == 2
        assert re.fullmatch(r'[A-Z]{2}', marker[0])
        assert re.fullmatch(r'[0-9]{2}(?:_FCC)?', marker[1])
        bdf = (root / 'lib/firmware/ath11k/QCN6122/hw1.0/board-2.bin').read_bytes()
        provenance = json.loads((root / 'etc/ex511-v2-bdf-provenance.json').read_text())
        assert marker == [provenance['country'], provenance['fem_mask_5g']]
        assert hashlib.sha256(bdf).hexdigest() == provenance['container_sha256']
        assert not provenance['contains_per_unit_calibration']
    print('PASS: factory helpers, UBI tools, NSS/ath11k/Realtek modules and firmware included')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--rootfs', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--readonly-trial', action='store_true',
                        help='require the diagnostic profile with every NAND partition read-only')
    modes.add_argument('--slot1', action='store_true',
                       help='require only physical slot 1 writable and its chosen marker')
    modes.add_argument('--slot1-env', action='store_true',
                       help='require opt-in slot1 with explicit APPSBLENV write opt-in')
    parser.add_argument('--private-overlay', action='store_true',
                        help='validate the local country/FEM marker against private BDF provenance')
    args = parser.parse_args()
    validate_dtb(args.dtb, args.readonly_trial, args.slot1 or args.slot1_env, args.slot1_env)
    if args.rootfs:
        validate_rootfs(args.rootfs, args.private_overlay)
    print('Static/assembly checks do not verify Ethernet, RF, NSS or installation on hardware.')


if __name__ == '__main__':
    main()
