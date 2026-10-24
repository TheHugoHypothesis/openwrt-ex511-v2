#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Assess a stock SSH capture and an initramfs FIT locally; never install anything.

This checks sizes, identities, FIT hashes and Linux-side write protection.
It cannot establish bootloader handoff, recovery, or permission to flash.
"""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import struct
import zlib

from fdt import cells, read_fdt

PARTITIONS = {
    '0:SBL1': [0, 0x80000], '0:MIBIB': [0x80000, 0x80000],
    '0:BOOTCONFIG': [0x100000, 0x40000], '0:BOOTCONFIG1': [0x140000, 0x40000],
    '0:QSEE': [0x180000, 0x100000], '0:DEVCFG': [0x280000, 0x40000],
    '0:CDT': [0x2c0000, 0x40000], '0:APPSBLENV': [0x300000, 0x80000],
    '0:APPSBL': [0x380000, 0x140000], '0:ART': [0x4c0000, 0x100000],
    '0:TRAINING': [0x5c0000, 0x80000], 'misc_data_ro': [0x640000, 0x600000],
    'misc_data_rw': [0xc40000, 0x600000], 'rootfs': [0x1240000, 0x2460000],
    'rootfs_1': [0x36a0000, 0x2460000], 'misc_data_rwbak': [0x5b00000, 0x600000],
    'misc_data_isp': [0x6100000, 0x600000],
}


def sections(text, prefix):
    result, current = {}, None
    lines = iter(text.splitlines())
    for line in lines:
        if line.startswith(prefix):
            current = result.setdefault(line, {})
        elif current is not None and line:
            current[line] = next(lines, '')
    return result


def stock_metadata(directory):
    identity = (directory / 'identity.txt').read_text()
    selection = (directory / 'boot-selection.txt').read_text()
    uid = re.search(r'^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)$', identity, re.M)
    if not uid or uid.group(2) != '0':
        raise ValueError('Capture does not demonstrate effective stock root access')
    if 'armv7l' not in identity or 'Linux EX511 ' not in identity:
        raise ValueError('Capture does not identify the expected stock ARMv7 EX511')
    active = re.search(r'^/proc/boot_info/rootfs/primaryboot\n([01])$', selection, re.M)
    target = re.search(r'^/proc/boot_info/rootfs/upgradepartition\n(rootfs(?:_1)?)$', selection, re.M)
    if not active or not target:
        raise ValueError('Missing stock slot metadata')
    expected = 'rootfs_1' if active.group(1) == '0' else 'rootfs'
    if target.group(1) != expected:
        raise ValueError('Stock active slot and upgrade target disagree')
    partitions = {}
    for index, size, erase, name in re.findall(
            r'^mtd(\d+): ([0-9a-f]+) ([0-9a-f]+) "([^"]+)"$', identity, re.M):
        if name in partitions:
            raise ValueError('Ambiguous MTD partition label: ' + name)
        partitions[name] = {'index': int(index), 'size': int(size, 16),
                            'erase_size': int(erase, 16)}
    for name in ['rootfs', 'rootfs_1']:
        if partitions.get(name, {}).get('size') != 0x2460000:
            raise ValueError('Unexpected firmware partition geometry: ' + name)
        if partitions[name]['erase_size'] != 0x20000:
            raise ValueError('Unexpected NAND erase size')
    ubi = sections((directory / 'ubi.txt').read_text(), '/sys/class/ubi/')
    active_name = 'rootfs' if active.group(1) == '0' else 'rootfs_1'
    active_devices = [path for path, props in ubi.items()
                      if props.get('mtd_num') == str(partitions[active_name]['index'])]
    if len(active_devices) != 1:
        raise ValueError('Cannot identify active stock UBI device')
    device = active_devices[0]
    if any(p.get('mtd_num') == str(partitions[target.group(1)]['index']) for p in ubi.values()):
        raise ValueError('Expected inactive target is attached to UBI; re-audit before planning')
    volumes = [p for path, p in ubi.items() if path.startswith(device + '_') and p.get('name') == 'kernel']
    if len(volumes) != 1:
        raise ValueError('Cannot identify active kernel volume')
    volume = volumes[0]
    if (int(volume['usable_eb_size']) != 126976 or
            not 0 < int(volume['reserved_ebs']) <= 291 or
            volume.get('corrupted') != '0' or volume.get('upd_marker') != '0'):
        raise ValueError('Unexpected or unhealthy active kernel UBI volume metadata')
    return {'effective_uid': 0, 'active_slot': int(active.group(1)),
            'active_partition': active_name, 'inactive_partition': target.group(1),
            'inactive_mtd_index_observed': partitions[target.group(1)]['index'],
            'firmware_slot_bytes': partitions[target.group(1)]['size'],
            'erase_bytes': partitions[target.group(1)]['erase_size'],
            'leb_bytes': int(volume['usable_eb_size']),
            'active_kernel_reserved_lebs': int(volume['reserved_ebs']),
            'active_kernel_capacity_bytes': int(volume['reserved_ebs']) * int(volume['usable_eb_size']),
            'bootcmd_is_bootipq': bool(re.search(r'^bootcmd=bootipq$', selection, re.M)),
            'tp_boot_idx_undefined': '"tp_boot_idx" not defined' in selection,
            'stock_kexec_executable_found': any(line.endswith('/kexec') for line in
                                               (directory / 'tools.txt').read_text().splitlines())}


def string(value):
    return value.rstrip(b'\0').decode('ascii')


def fit_metadata(data, stock_load=0x44000000):
    fit = read_fdt(data)
    config = fit.get('/configurations/config@mp03.3')
    if not config:
        raise ValueError('FIT has no config@mp03.3 for this stock bootloader')
    images = {}
    for field in ['kernel', 'fdt']:
        path = '/images/' + string(config[field])
        props = fit[path]
        payload = props.get('data')
        if payload is None:
            raise ValueError('External FIT data is not supported by this checker')
        checked = 0
        for child, h in fit.items():
            if child.startswith(path + '/') and child.count('/') == path.count('/') + 1 and 'algo' in h:
                algo = string(h['algo'])
                if algo == 'crc32':
                    digest = struct.pack('>I', zlib.crc32(payload) & 0xffffffff)
                elif algo in ['sha1', 'sha256']:
                    digest = hashlib.new(algo, payload).digest()
                else:
                    raise ValueError('Unsupported FIT integrity algorithm: ' + algo)
                if digest != h.get('value'):
                    raise ValueError('FIT integrity mismatch for ' + path)
                checked += 1
        if not checked:
            raise ValueError('FIT image has no verified integrity hash: ' + path)
        images[field] = props
    kernel = images['kernel']
    if string(kernel['arch']) != 'arm64' or string(kernel['compression']) != 'lzma':
        raise ValueError('Expected the compiled AArch64/LZMA initramfs FIT')
    decoder = lzma.LZMADecompressor()
    expanded = decoder.decompress(kernel['data'], max_length=64 * 1024 * 1024)
    if not decoder.eof or decoder.unused_data:
        raise ValueError('Kernel decompression exceeds limit or has trailing data')
    if expanded[56:60] != b'ARMd':
        raise ValueError('Expanded kernel lacks the AArch64 Image magic')
    addresses = cells(kernel['load'])
    if len(addresses) != 1:
        raise ValueError('Unsupported FIT load address representation')
    load = addresses[0]
    if cells(kernel['entry']) != [load]:
        raise ValueError('Kernel load and entry addresses differ')
    if load < 0x40000000 or load + len(expanded) > 0x50000000:
        raise ValueError('Expanded kernel is outside the observed 256 MiB RAM')
    dtb = read_fdt(images['fdt']['data'])
    if b'tplink,ex511-v2' not in dtb['/'].get('compatible', b'').split(b'\0'):
        raise ValueError('Embedded DTB is not for EX511 v2')
    parts = {}
    for path, props in dtb.items():
        if '/partitions/partition@' in path and 'label' in props:
            label = string(props['label'])
            if label in parts:
                raise ValueError('Duplicate embedded partition label')
            parts[label] = {'geometry': cells(props['reg']), 'readonly': 'read-only' in props}
    if set(parts) != set(PARTITIONS):
        raise ValueError('Expected the 17 stock physical NAND partition labels')
    for label, geometry in PARTITIONS.items():
        if parts[label]['geometry'] != geometry:
            raise ValueError('Embedded partition geometry mismatch: ' + label)
    return {'fit_bytes': len(data), 'fit_sha256': hashlib.sha256(data).hexdigest(),
            'fit_config': 'config@mp03.3', 'fit_hashes_verified': True,
            'expanded_kernel_bytes': len(expanded), 'kernel_load_address': load,
            'kernel_end_address': load + len(expanded),
            'stock_fit_input_address_assumed': stock_load,
            'kernel_overlaps_stock_fit_input': load < stock_load + len(data) and stock_load < load + len(expanded),
            'writable_nand_partitions': sorted(k for k, p in parts.items() if not p['readonly']),
            'bootargs_append': string(dtb.get('/chosen', {}).get('bootargs-append', b''))}


def assess(stock, fit, kernel_config):
    blockers = []
    if fit['writable_nand_partitions']:
        blockers.append('Current initramfs leaves NAND partitions writable; build a read-only trial profile')
    if fit['kernel_overlaps_stock_fit_input']:
        blockers.append('Expanded kernel overlaps the stock FIT input buffer')
    if re.search(r'(?:^|\s)(?:root|ubi\.mtd)=', fit['bootargs_append']):
        blockers.append('Trial DTB still appends a persistent root/UBI selection')
    for symbol in ['CONFIG_MTD_CMDLINE_PARTS', 'CONFIG_MTD_PARTITIONED_MASTER']:
        if f'# {symbol} is not set' not in kernel_config:
            blockers.append(symbol + ' is not demonstrated disabled')
    if 'CONFIG_BLK_DEV_INITRD=y' not in kernel_config or not re.search(r'^CONFIG_INITRAMFS_SOURCE="[^"\n]+"$', kernel_config, re.M):
        blockers.append('Kernel config does not demonstrate a built-in initramfs')
    required = (fit['fit_bytes'] + stock['leb_bytes'] - 1) // stock['leb_bytes']
    return {'status': 'not_authorized_for_flash', 'stock': stock, 'candidate': fit,
            'capacity': {'trial_kernel_lebs_needed': required,
                         'fits_existing_active_kernel_volume': fit['fit_bytes'] <= stock['active_kernel_capacity_bytes'],
                         'kernel_data_pebs_plus_two_layout_pebs': required + 2,
                         'slot_physical_pebs': stock['firmware_slot_bytes'] // stock['erase_bytes'],
                         'note': 'Not a UBI image size or a bad-block/UBI-overhead capacity guarantee'},
            'offline_blockers': blockers,
            'unresolved': ['Fresh inactive-slot metadata and an device-specific private backup',
                           'Read-only initramfs preinit and effective runtime MTD protection',
                           'Verified bootloader slot selection; inherited slot-0 sysupgrade is not a stock installer',
                           'Reviewed boot-selection/reversion with environment-write constraints resolved',
                           'Verified recovery and actual AArch64 bootloader handoff',
                           'Ethernet availability after kernel handoff'],
            'note': 'Local inspection only. No device access, flash commands, or installation approval.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--fit', type=Path, required=True)
    p.add_argument('--kernel-config', type=Path, required=True)
    args = p.parse_args()
    try:
        report = assess(stock_metadata(args.capture), fit_metadata(args.fit.read_bytes()),
                        args.kernel_config.read_text())
    except (ValueError, KeyError, IndexError, OSError, struct.error, lzma.LZMAError) as error:
        p.exit(1, f'Assessment refused: {error}\n')
    print(json.dumps(report, indent=2))
    return 2 if report['offline_blockers'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
