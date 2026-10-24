#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify a kernel-only EX511 trial UBI, including raw NAND readback. No device IO."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def crc(data):
    return (zlib.crc32(data) ^ 0xffffffff) & 0xffffffff


def check(raw, fit):
    if not raw or len(raw) % 131072:
        raise ValueError('Expected whole 128 KiB eraseblocks')
    volumes, tables = {}, {}
    ec_count = 0
    for pos in range(0, len(raw), 131072):
        block = raw[pos:pos + 131072]
        if block == b'\xff' * 131072:
            continue
        if block[:4] != b'UBI#' or struct.unpack_from('>I', block, 60)[0] != crc(block[:60]):
            raise ValueError('Invalid EC header at PEB ' + str(pos // 131072))
        ec_count += 1
        vid, data = struct.unpack_from('>II', block, 16)
        if (vid, data) != (2048, 4096):
            raise ValueError('Unexpected UBI header geometry')
        header = block[vid:vid + 64]
        if header == b'\xff' * 64:
            continue
        if header[:4] != b'UBI!' or struct.unpack_from('>I', header, 60)[0] != crc(header[:60]):
            raise ValueError('Invalid VID header')
        vol_id, lnum = struct.unpack_from('>II', header, 8)
        if vol_id == 0x7fffefff:
            if lnum not in (0, 1) or lnum in tables:
                raise ValueError('Unexpected or duplicate layout LEB')
            tables[lnum] = block[data:data + 128 * 172]
        else:
            if vol_id != 0 or header[5] != 1 or lnum in volumes:
                raise ValueError('Unexpected or duplicate trial volume/LEB')
            volumes[lnum] = block[data:]
    if len(tables) != 2 or tables[0] != tables[1]:
        raise ValueError('Expected two identical layout tables')
    required = (len(fit) + 126975) // 126976
    for pos in range(0, len(tables[0]), 172):
        record = tables[0][pos:pos + 172]
        if struct.unpack_from('>I', record, 168)[0] != crc(record[:168]):
            raise ValueError('Invalid volume table CRC')
        if pos == 0:
            if (struct.unpack_from('>III', record) != (required, 1, 0) or
                    record[12:16] != b'\x01\x00\x00\x06' or record[16:144] != b'kernel' + bytes(122) or
                    record[144:168] != bytes(24)):
                raise ValueError('Unexpected kernel volume definition')
        elif record[:168] != bytes(168):
            raise ValueError('Additional volume in trial image')
    if sorted(volumes) != list(range(required)):
        raise ValueError('Incomplete trial kernel LEB mapping')
    payload = b''.join(volumes[i] for i in sorted(volumes))
    if payload[:len(fit)] != fit or payload[len(fit):] != b'\xff' * (len(payload) - len(fit)):
        raise ValueError('Reconstructed kernel differs from the verified FIT')
    return {'ubi_bytes': len(raw), 'ubi_sha256': hashlib.sha256(raw).hexdigest(),
            'fit_sha256': hashlib.sha256(fit).hexdigest(), 'kernel_lebs': required,
            'valid_ec_headers': ec_count, 'fit_reconstructed_exactly': True,
            'note': 'Offline integrity only; no bootability or installation guarantee'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ubi', type=Path, required=True)
    p.add_argument('--fit', type=Path, required=True)
    args = p.parse_args()
    try:
        report = check(args.ubi.read_bytes(), args.fit.read_bytes())
    except (ValueError, OSError, struct.error) as error:
        p.exit(1, f'UBI check refused: {error}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
