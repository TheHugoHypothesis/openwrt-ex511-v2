#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""EX511 boot-policy review tool. Planning is offline; apply requires the explicit slot1-env DT."""
import argparse
import hashlib
import importlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import struct
import subprocess
import zlib

PART_SIZE = 0x80000
ENV_SIZE = 0x40000
WRAPPER = (b'if printenv ex511_trial; then setenv ex511_trial; if saveenv; '
           b'then setenv tp_boot_idx 1; fi; fi; bootipq')
MARKER = '/proc/device-tree/chosen/openwrt,ex511-env-control'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def parse_env(raw):
    require(len(raw) == PART_SIZE, 'Expected exact 512 KiB APPSBLENV readback')
    require(struct.unpack_from('<I', raw)[0] == zlib.crc32(raw[4:ENV_SIZE]),
            'Environment CRC mismatch; do not repair or write automatically')
    data = raw[4:ENV_SIZE]
    end = data.find(b'\0\0')
    require(end > 0, 'Missing environment terminator')
    values = {}
    for item in data[:end].split(b'\0'):
        key, separator, value = item.partition(b'=')
        require(separator and re.fullmatch(rb'[A-Za-z0-9_.-]+', key), 'Invalid environment record')
        require(key not in values, 'Duplicate environment variable')
        values[key] = value
    require(values.get(b'bootcmd') == WRAPPER, 'Unknown bootcmd; supported wrapper must match exactly')
    require(values.get(b'tp_boot_idx') in (None, b'1'), 'Unreviewed persistent slot selector')
    require(b'ex511_trial' not in values, 'Trial is armed; refuse ambiguous policy changes')
    return values


def expected(values, policy):
    require(policy in ('stock', 'openwrt'), 'Unknown boot policy')
    result = dict(values)
    result.pop(b'ex511_trial', None)
    if policy == 'openwrt':
        result[b'tp_boot_idx'] = b'1'
    else:
        result.pop(b'tp_boot_idx', None)
    return result


def map_digest(values):
    # Length framing also preserves opaque unrelated values without printing them.
    return digest(b''.join(struct.pack('>II', len(k), len(v)) + k + v
                           for k, v in sorted(values.items())))


def plan(raw, policy):
    values = parse_env(raw)
    return {'format': 1, 'policy': policy, 'before_partition_sha256': digest(raw),
            'expected_environment_map_sha256': map_digest(expected(values, policy)),
            'untouched_partition_tail_sha256': digest(raw[ENV_SIZE:]),
            'wrapper_sha256': digest(WRAPPER),
            'environment_size': ENV_SIZE, 'partition_size': PART_SIZE,
            'erase_size': 0x20000, 'erase_sectors': 2,
            'changes': {'tp_boot_idx': '1' if policy == 'openwrt' else None,
                        'ex511_trial': None}}


def verify(before, after, policy):
    original = parse_env(before)
    actual = parse_env(after)
    require(actual == expected(original, policy), 'Unexpected post-write environment variables')
    require(before[ENV_SIZE:] == after[ENV_SIZE:], 'Reserved partition tail changed')
    return {'crc_valid': True, 'exact_expected_variables': True,
            'reserved_tail_unchanged': True, 'after_partition_sha256': digest(after)}


def script(policy):
    require(policy in ('stock', 'openwrt'), 'Unknown policy')
    return (b'tp_boot_idx 1\n' if policy == 'openwrt' else b'tp_boot_idx\n') + b'ex511_trial\n'


def write_private(path, data):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def check_layout(text):
    lines = text.splitlines()
    require(len(lines) >= 5 and lines[:3] == ['0', 'tplink,ex511-v2', 'opt-in'],
            'Requires root EX511 and a separately reviewed env-control DT marker')
    args = lines[3].split()
    require(args.count('ubi.mtd=rootfs_1') == 1 and
            sum(x.startswith('ubi.mtd=') for x in args) == 1, 'Wrong UBI boot selection')
    parts = {}
    for line in lines[4:]:
        fields = line.split('|')
        require(len(fields) == 8, 'Invalid MTD report')
        index, name, flags, offset, size, erase, writesize, bad_blocks = fields
        require(index.isdecimal() and name not in parts, 'Ambiguous MTD identity')
        require(index not in [p[0] for p in parts.values()], 'Duplicate MTD index')
        parts[name] = (index, int(flags, 0), int(offset), int(size), int(erase), int(writesize), int(bad_blocks))
    geometry = importlib.import_module('validate-nss-build').PARTITIONS
    require(set(parts) == {p[0] for p in geometry}, 'Unexpected physical partitions')
    for name, offset, size, _ in geometry:
        _, flags, actual_offset, actual_size, erase, writesize, bad_blocks = parts[name]
        writable = name in ('rootfs_1', '0:APPSBLENV')
        require(flags == (0x400 if writable else 0) and
                (actual_offset, actual_size, erase, writesize) == (offset, size, 131072, 2048),
                'Wrong protection or geometry: ' + name)
        if name == '0:APPSBLENV':
            require(bad_blocks == 0, 'Environment has bad blocks; layout requires separate review')
    return parts['0:APPSBLENV'][0]


LAYOUT_QUERY = '''id -u
cat /tmp/sysinfo/board_name
if [ -e ''' + MARKER + ''' ]; then echo opt-in; else echo absent; fi
cat /proc/cmdline
for d in /sys/class/mtd/mtd*; do
 [ -f "$d/name" ] || continue
 printf '%s|%s|%s|%s|%s|%s|%s|%s\\n' "${d##*/mtd}" "$(cat "$d/name")" "$(cat "$d/flags")" "$(cat "$d/offset")" "$(cat "$d/size")" "$(cat "$d/erasesize")" "$(cat "$d/writesize")" "$(cat "$d/bad_blocks")"
done'''


class SSH:
    def __init__(self, host, source, known_hosts):
        host = str(ipaddress.IPv4Address(host))
        source = str(ipaddress.IPv4Address(source))
        require(known_hosts.is_file(), 'A previously verified SSH host-key file is required')
        self.argv = ['ssh', '-T', '-b', source, '-o', 'BatchMode=yes', '-o',
                     'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5', '-o',
                     'UserKnownHostsFile=' + str(known_hosts.resolve()), 'root@' + host]

    def run(self, command, data=None, timeout=30):
        result = subprocess.run(self.argv + [command], input=data, capture_output=True, timeout=timeout)
        require(result.returncode == 0, 'SSH operation failed; do not retry an environment write blindly')
        return result.stdout

    def layout(self):
        return check_layout(self.run(LAYOUT_QUERY).decode())

    def read(self, index):
        require(index.isdecimal(), 'Invalid MTD index')
        return self.run('dd if=/dev/mtd' + index + ' bs=131072 count=4 2>/dev/null')


def locked_write_command(index, before_hash, staging):
    require(index.isdecimal() and re.fullmatch(r'[0-9a-f]{64}', before_hash), 'Invalid locked write')
    require(re.fullmatch(r'/tmp/ex511-boot-policy-[0-9a-f]{16}', staging), 'Invalid RAM staging path')
    # OpenWrt's 002-envtools patch places the standard fw_setenv flock here.
    # Hold it across the final snapshot check, batch and readback. Give the
    # nested tool a private lock directory to avoid locking ourselves out.
    body = ('set -eu\n'
            'current=$(sha256sum /dev/mtd' + index + ') || exit 73\n'
            '[ "${current%% *}" = ' + before_hash + ' ] || exit 73\n'
            'fw_setenv -l ' + staging + ' -c ' + staging + '/fw_env.config -s ' +
            staging + '/transaction >/dev/null\n'
            'dd if=/dev/mtd' + index + ' bs=131072 count=4 2>/dev/null')
    return 'flock -n /var/lock/fw_printenv.lock sh -c ' + shlex.quote(body)


def cleanup_command(staging):
    require(re.fullmatch(r'/tmp/ex511-boot-policy-[0-9a-f]{16}', staging), 'Invalid RAM staging path')
    # fw_setenv -l creates its own lock file in this private RAM directory.
    return ('rm -f ' + staging + '/fw_env.config ' + staging + '/transaction ' +
            staging + '/fw_printenv.lock; rmdir ' + staging)


def apply(transport, proposed, backup_dir):
    # The protected slot1 profile is refused before any NAND read/write.
    # Only the separate opt-in slot1-env profile opts into this executor.
    require(isinstance(proposed, dict), 'Invalid plan schema')
    index = transport.layout()
    before = transport.read(index)
    require(proposed == plan(before, proposed.get('policy')), 'Stale or modified plan')
    backup_dir.mkdir(mode=0o700)  # exclusive; preserve every older backup
    write_private(backup_dir / 'environment-before.bin', before)
    write_private(backup_dir / 'plan.json', (json.dumps(proposed, indent=2) + '\n').encode())
    sync_directory(backup_dir)
    sync_directory(backup_dir.parent)
    if parse_env(before) == expected(parse_env(before), proposed['policy']):
        return {'unchanged': True, 'environment_written': False}
    staging = '/tmp/ex511-boot-policy-' + secrets.token_hex(8)
    transport.run('umask 077; mkdir ' + staging)
    configuration = ('/dev/mtd' + index + ' 0x0 0x40000 0x20000 2\n').encode()
    transaction = script(proposed['policy'])
    result = None
    try:
        for name, data in [('fw_env.config', configuration), ('transaction', transaction)]:
            path = staging + '/' + name
            transport.run('umask 077; cat > ' + path, data=data)
            require(transport.run('sha256sum ' + path).decode().split()[0] == digest(data),
                    'RAM staging verification failed')
        require(transport.layout() == index and transport.read(index) == before,
                'Environment or layout changed during preparation')
        write_private(backup_dir / 'WRITE-INTENT.txt',
                      b'A write may start after this record. Check verified.json before any reboot.\n')
        sync_directory(backup_dir)
        # One standard fw_setenv batch. Do not patch raw NAND, modify bootcmd,
        # change permissions, select bootloader fallback or reboot here.
        try:
            after = transport.run(locked_write_command(index, digest(before), staging), timeout=90)
            write_private(backup_dir / 'environment-after.bin', after)
            result = verify(before, after, proposed['policy'])
            result.update(environment_written=True, policy=proposed['policy'])
        except (ValueError, OSError, subprocess.SubprocessError):
            write_private(backup_dir / 'OUTCOME-REQUIRES-INSPECTION.txt',
                          b'Write may have started. Do not reboot, retry, or restore automatically.\n')
            raise
        write_private(backup_dir / 'verified.json', (json.dumps(result, indent=2) + '\n').encode())
        sync_directory(backup_dir)
        return result
    finally:
        # RAM files only; never clean a NAND device or touch the preserved backup.
        # A cleanup failure must not disguise a verified write as an uncertain one.
        try:
            transport.run(cleanup_command(staging))
        except (ValueError, OSError, subprocess.SubprocessError):
            write_private(backup_dir / 'RAM-CLEANUP-FAILED.txt',
                          b'Private staging cleanup failed; inspect verified.json for the write outcome.\n')
            sync_directory(backup_dir)
            if result is not None:
                result['ram_cleanup_warning'] = True


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    create = commands.add_parser('plan', help='offline only; emits an auditable standard-tool transaction')
    create.add_argument('--before', required=True, type=Path)
    create.add_argument('--policy', required=True, choices=['stock', 'openwrt'])
    create.add_argument('--output', required=True, type=Path)
    check = commands.add_parser('verify', help='offline post-write comparison; never writes a device')
    check.add_argument('--before', required=True, type=Path)
    check.add_argument('--after', required=True, type=Path)
    check.add_argument('--policy', required=True, choices=['stock', 'openwrt'])
    snapshot = commands.add_parser('snapshot', help='read-only SSH layout check and private environment backup')
    snapshot.add_argument('--output', required=True, type=Path)
    snapshot.add_argument('--host', required=True)
    snapshot.add_argument('--source', required=True)
    snapshot.add_argument('--known-hosts', required=True, type=Path)
    execute = commands.add_parser('apply', help='opt-in slot1-env image only; never reboots')
    execute.add_argument('--reviewed-plan', required=True, type=Path)
    execute.add_argument('--backup-dir', required=True, type=Path)
    execute.add_argument('--host', required=True)
    execute.add_argument('--source', required=True)
    execute.add_argument('--known-hosts', required=True, type=Path)
    a = p.parse_args()
    try:
        if a.command == 'plan':
            raw = a.before.read_bytes()
            result = plan(raw, a.policy)
            a.output.mkdir(mode=0o700)
            write_private(a.output / 'environment-before.bin', raw)
            write_private(a.output / 'plan.json', (json.dumps(result, indent=2) + '\n').encode())
            write_private(a.output / 'fw_setenv.script', script(a.policy))
        elif a.command == 'snapshot':
            transport = SSH(a.host, a.source, a.known_hosts)
            raw = transport.read(transport.layout())
            parse_env(raw)
            write_private(a.output, raw)
            sync_directory(a.output.parent)
            result = {'read_only': True, 'partition_sha256': digest(raw), 'crc_valid': True}
        elif a.command == 'verify':
            result = verify(a.before.read_bytes(), a.after.read_bytes(), a.policy)
        else:
            result = apply(SSH(a.host, a.source, a.known_hosts),
                           json.loads(a.reviewed_plan.read_text()), a.backup_dir)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        p.exit(1, 'Boot policy refused: ' + str(error) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
