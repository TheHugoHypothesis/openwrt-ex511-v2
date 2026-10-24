#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Validate an EX511 slot1 SquashFS sysupgrade and factory UBI locally; no device IO."""
import argparse
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import struct
import subprocess
import tarfile
import tempfile
import zlib

from fdt import read_fdt


def module(filename):
    spec = importlib.util.spec_from_file_location(filename.replace('-', '_'),
                                                Path(__file__).with_name(filename + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def crc(data):
    return (zlib.crc32(data) ^ 0xffffffff) & 0xffffffff


def check_ubi(raw, kernel, root):
    if not raw or len(raw) % 131072 or len(raw) > 0x2460000:
        raise ValueError('Factory UBI/readback must contain whole PEBs and fit physical slot 1')
    used = struct.unpack_from('<Q', root, 40)[0]
    # sysupgrade-tar.sh uses dd bs=1024 conv=sync, whereas append-ubi uses
    # the unpadded mksquashfs -nopad output. Compare every filesystem byte,
    # then require the exact zero/erased padding belonging to each format.
    if not 96 < used <= len(root) or len(root) != ((used + 1023) // 1024) * 1024:
        raise ValueError('Unexpected sysupgrade SquashFS length')
    if root[used:] != bytes(len(root) - used):
        raise ValueError('Nonzero sysupgrade SquashFS padding')
    tables, payloads = {}, {}
    for pos in range(0, len(raw), 131072):
        block = raw[pos:pos + 131072]
        if block == b'\xff' * 131072:
            continue
        if (block[:5] != b'UBI#\x01' or
                struct.unpack_from('>I', block, 60)[0] != crc(block[:60]) or
                struct.unpack_from('>II', block, 16) != (2048, 4096)):
            raise ValueError('Invalid EC header/geometry')
        header = block[2048:2112]
        if header == b'\xff' * 64:
            continue
        if (header[:6] != b'UBI!\x01\x01' or header[6] != 0 or
                struct.unpack_from('>I', header, 28)[0] != 0 or
                struct.unpack_from('>I', header, 60)[0] != crc(header[:60])):
            raise ValueError('Invalid or unsupported VID header')
        vol, leb = struct.unpack_from('>II', header, 8)
        if vol == 0x7fffefff:
            if leb not in [0, 1] or leb in tables:
                raise ValueError('Unexpected layout LEB')
            tables[leb] = block[4096:4096 + 128 * 172]
        else:
            key = (vol, leb)
            if vol not in [0, 1, 2] or key in payloads:
                raise ValueError('Unexpected or duplicate volume/LEB')
            payloads[key] = block[4096:]
    if len(tables) != 2 or tables[0] != tables[1]:
        raise ValueError('Expected identical layout tables')
    expected = [(b'kernel', (len(kernel) + 126975) // 126976, 0),
                (b'rootfs', (len(root) + 126975) // 126976, 0),
                (b'rootfs_data', (1048576 + 126975) // 126976, 1)]
    for index in range(128):
        record = tables[0][index * 172:(index + 1) * 172]
        if struct.unpack_from('>I', record, 168)[0] != crc(record[:168]):
            raise ValueError('Volume-table CRC mismatch')
        if index >= 3:
            if record[:168] != bytes(168):
                raise ValueError('Additional UBI volume')
            continue
        name, reserved, flags = expected[index]
        if (struct.unpack_from('>III', record) != (reserved, 1, 0) or
                record[12:16] != bytes([1, 0, 0, len(name)]) or
                record[16:144] != name + bytes(128 - len(name)) or
                record[144:168] != bytes([flags]) + bytes(23)):
            raise ValueError('Unexpected volume definition: ' + name.decode())
    for vol, image in [(0, kernel), (1, root[:used])]:
        required = expected[vol][1]
        if sorted(leb for v, leb in payloads if v == vol) != list(range(required)):
            raise ValueError('Incomplete image LEB mapping')
        data = b''.join(payloads[(vol, i)] for i in range(required))
        if data[:len(image)] != image or data[len(image):] != b'\xff' * (len(data) - len(image)):
            raise ValueError('UBI payload differs from sysupgrade input')
    if any(vol == 2 for vol, _ in payloads):
        raise ValueError('Uninitialized rootfs_data must not have mapped LEBs')
    reserve = 291 - 2 - sum(x[1] for x in expected)
    if reserve < 24:
        raise ValueError('Insufficient initial PEB margin for UBI/bad-block handling')
    return {'kernel_lebs': expected[0][1], 'rootfs_lebs': expected[1][1],
            'rootfs_data_initial_lebs': expected[2][1], 'remaining_physical_pebs': reserve,
            'kernel_and_rootfs_reconstructed_exactly': True}


def check(args):
    with tempfile.TemporaryDirectory(prefix='ex511-slot1-check-') as work:
        work = Path(work)
        meta = work / 'metadata.json'
        subprocess.run([args.fwtool, '-q', '-i', str(meta), str(args.sysupgrade)], check=True,
                       timeout=15)
        info = json.loads(meta.read_text())
        if info.get('compat_version') != '2.0' or 'tplink,ex511-v2-slot1' not in info.get('new_supported_devices', []):
            raise ValueError('Not a slot1-compatible sysupgrade image')
        if args.env_control and 'tplink,ex511-v2-slot1-env' not in info.get('new_supported_devices', []):
            raise ValueError('Missing opt-in env-control image marker')
        prefix = 'sysupgrade-tplink_ex511-v2-slot1'
        with tarfile.open(args.sysupgrade) as archive:
            entries = {x.name: x for x in archive.getmembers()}
            required = {prefix + '/' + x for x in ['CONTROL', 'kernel', 'root']}
            if not required <= entries.keys() or set(entries) - required - {prefix}:
                raise ValueError('Unexpected sysupgrade archive layout')
            for name in required:
                if not entries[name].isfile() or not 0 < entries[name].size < 32 * 1024 * 1024:
                    raise ValueError('Invalid sysupgrade archive entry')
            kernel = archive.extractfile(entries[prefix + '/kernel']).read()
            root = archive.extractfile(entries[prefix + '/root']).read()
        fit = module('assess-ssh-trial').fit_metadata(kernel)
        writable = ['0:APPSBLENV', 'rootfs_1'] if args.env_control else ['rootfs_1']
        if fit['writable_nand_partitions'] != writable or fit['kernel_overlaps_stock_fit_input']:
            raise ValueError('FIT does not preserve stock/protected NAND or has an input overlap')
        nodes = read_fdt(kernel)
        config = nodes['/configurations/config@mp03.3']
        dtb = nodes['/images/' + config['fdt'].rstrip(b'\0').decode()]['data']
        dtb_path = work / 'slot1.dtb'
        dtb_path.write_bytes(dtb)
        module('validate-nss-build').validate_dtb(dtb_path, slot1=True, env_control=args.env_control)
        if (root[:4] != b'hsqs' or len(root) < 96 or
                struct.unpack_from('<H', root, 28)[0] != 4 or
                not 96 < struct.unpack_from('<Q', root, 40)[0] <= len(root)):
            raise ValueError('Root image is not a complete SquashFS v4 filesystem')
        config = args.kernel_config.read_text()
        if 'CONFIG_INITRAMFS_SOURCE=""' not in config:
            raise ValueError('Provide the normal kernel .config.set, not its initramfs configuration')
        for option in ['CONFIG_MTD_CMDLINE_PARTS', 'CONFIG_MTD_PARTITIONED_MASTER', 'CONFIG_MTD_UBI_GLUEBI']:
            if f'# {option} is not set' not in config:
                raise ValueError('Required protection not demonstrated disabled: ' + option)
        for option in ['CONFIG_MTD_UBI=y', 'CONFIG_MTD_UBI_BLOCK=y', 'CONFIG_SQUASHFS=y', 'CONFIG_UBIFS_FS=y']:
            if option not in config:
                raise ValueError('Missing persistent-root dependency: ' + option)
        report = check_ubi(args.ubi.read_bytes(), kernel, root)
        report.update({'profile': 'tplink_ex511-v2-slot1-env' if args.env_control else 'tplink_ex511-v2-slot1', 'fit': fit,
                       'sysupgrade_sha256': hashlib.sha256(args.sysupgrade.read_bytes()).hexdigest(),
                       'ubi_sha256': hashlib.sha256(args.ubi.read_bytes()).hexdigest(),
                       'rootfs_sha256': hashlib.sha256(root[:struct.unpack_from('<Q', root, 40)[0]]).hexdigest(),
                       'tar_rootfs_padded_sha256': hashlib.sha256(root).hexdigest(),
                       'normal_kernel_without_builtin_rootfs': True,
                       'hardware_boot_tested': False,
                       'note': 'Offline integrity only; installation and runtime memory remain unverified'})
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-control', action='store_true',
                        help='require explicit opt-in slot1-env profile and its two writable partitions')
    parser.add_argument('--sysupgrade', required=True, type=Path)
    parser.add_argument('--ubi', required=True, type=Path)
    parser.add_argument('--kernel-config', required=True, type=Path)
    parser.add_argument('--fwtool', required=True)
    args = parser.parse_args()
    try:
        report = check(args)
    except (ValueError, KeyError, AssertionError, OSError, struct.error, tarfile.TarError, lzma.LZMAError,
            subprocess.SubprocessError) as error:
        parser.exit(1, f'Slot1 image refused: {error}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
