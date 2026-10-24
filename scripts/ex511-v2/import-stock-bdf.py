#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Provision a private EX511 5 GHz BDF overlay from a matching stock extraction."""
import argparse
import functools
import hashlib
import json
import os
from pathlib import Path
import re
import struct

SIZE = 131072
MAGIC = b'QCA-ATH11K-BOARD\0'
VARIANT = 'TP-Link-EX511-v2'


def valid_eeprom(data):
    return (len(data) == SIZE and data[:4] == b'\x01\x00\x04\x04' and
            functools.reduce(int.__xor__, struct.unpack('<65536H', data), 0) == 0xffff)


def ie(kind, data):
    return struct.pack('<II', kind, len(data)) + data + b'\0' * (-len(data) % 4)


def board_container(data):
    # Scope both observed ID conventions to the EX511 variant. Actual external
    # native QMI IDs still need confirming when the experimental image is booted.
    entries = []
    for board_id in (255, 96):
        name = f'bus=ahb,qmi-chip-id=0,qmi-board-id={board_id},variant={VARIANT}'.encode()
        entries.append(ie(0, ie(0, name) + ie(1, data)))
    return MAGIC + b'\0' * (-len(MAGIC) % 4) + b''.join(entries)


def provision(stock_root, country, fem, output):
    if not re.fullmatch(r'[A-Z]{2}', country) or not re.fullmatch(r'[0-9]{2}(?:_FCC)?', fem):
        raise ValueError('country/FEM must be bounded factory values, use the device factory values')
    source = stock_root / 'etc/board_data_files/5g' / f'bdwlan_{country}{fem}.b5g'
    if source.is_symlink() or not source.is_file():
        raise ValueError('matching country/FEM BDF is absent; refusing a generic fallback')
    data = source.read_bytes()
    if not valid_eeprom(data):
        raise ValueError('stock BDF has an unexpected size, EEPROM version or checksum')
    bdf = board_container(data)
    report = {'country': country, 'fem_mask_5g': fem,
              'stock_filename': source.name,
              'stock_payload_sha256': hashlib.sha256(data).hexdigest(),
              'container_sha256': hashlib.sha256(bdf).hexdigest(),
              'variant': VARIANT, 'qmi_chip_id': 0, 'qmi_board_ids': [255, 96],
              'contains_per_unit_calibration': False,
              'hardware_tested_with_openwrt': False}
    destination = Path('lib/firmware/ath11k/QCN6122/hw1.0/board-2.bin')
    files = {
        destination: bdf,
        # ipq-wifi uses install-overlay. Its postinst copies rootfs-overlay
        # after files/ has been applied, so override that staging copy too.
        Path('rootfs-overlay') / destination: bdf,
        Path('etc/ex511-v2-bdf-info'): f'{country} {fem}\n'.encode(),
        Path('etc/ex511-v2-bdf-provenance.json'): (json.dumps(report, indent=2) + '\n').encode(),
    }
    # Keep generated blobs outside the tracked source tree. Overlay them into
    # a separate build directory's files/ tree, never package/firmware/.
    repository = Path(__file__).resolve().parents[2]
    if output.resolve().is_relative_to(repository):
        raise ValueError('write the private overlay outside the source repository')
    for relative, content in files.items():
        target = output / relative
        if target.is_symlink() or (target.exists() and target.read_bytes() != content):
            raise ValueError(f'refusing to overwrite an existing different file: {relative}')
    for relative, content in files.items():
        target = output / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-rootfs', required=True, type=Path)
    parser.add_argument('--country', required=True, help='factory Country value, not a preference')
    parser.add_argument('--fem-mask-5g', required=True, help='factory FEM_MASK_5G value')
    parser.add_argument('--output-dir', required=True, type=Path, help='private overlay outside this repository')
    args = parser.parse_args()
    try:
        report = provision(args.stock_rootfs, args.country, args.fem_mask_5g, args.output_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f'BDF import failed: {error}\n')
    print(json.dumps(report, indent=2))
    print('Private BDF overlay created. Per-unit calibration will be read from read-only factory UBIFS.')
    print('This does not verify OpenWrt RF operation or grant stock-data redistribution rights.')


if __name__ == '__main__':
    main()
