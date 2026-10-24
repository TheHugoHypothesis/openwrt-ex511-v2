#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Collect bounded, read-only boot metadata through stock's interactive SSH shell.

Requires host Python pexpect. Does not accept unknown host keys, attach UBI,
read user/factory payloads, change environment/configuration, reboot or flash.
"""
import argparse
import getpass
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shlex
import time


# Only these commands may be sent. In particular, never dump all fw_printenv.
QUERIES = {
    'identity': "grep -E '^(Uid|Gid|CapEff):' /proc/self/status; uname -a; cat /proc/uptime; cat /proc/cmdline; cat /proc/mtd",
    'boot-selection': '''
for path in /proc/boot_info/rootfs/primaryboot /proc/boot_info/rootfs/upgradepartition /etc/fw_env.config; do
    [ ! -r "$path" ] || { echo "$path"; cat "$path"; }
done
if [ -x /usr/sbin/fw_printenv ]; then
    for name in bootcmd tp_boot_idx config_name bootdelay bootcount bootlimit altbootcmd fsbootargs; do
        /usr/sbin/fw_printenv "$name"
    done
fi''',
    'mtd': '''
for entry in /sys/class/mtd/mtd[0-9]*; do
    [ -r "$entry/name" ] || continue
    echo "$entry"
    for field in name size offset erasesize writesize subpagesize oobsize type flags; do
        [ ! -r "$entry/$field" ] || { echo "$field"; cat "$entry/$field"; }
    done
done''',
    'ubi': '''
for entry in /sys/class/ubi/ubi[0-9]*; do
    [ -d "$entry" ] || continue
    echo "$entry"
    for field in mtd_num ro_mode name type eraseblock_size usable_eb_size total_eraseblocks avail_eraseblocks bad_peb_count reserved_for_bad volumes_count data_bytes reserved_ebs corrupted upd_marker; do
        [ ! -r "$entry/$field" ] || { echo "$field"; cat "$entry/$field"; }
    done
done''',
    'tools': '''
for tool in fw_printenv fw_setenv ubiformat ubiattach ubidetach ubiupdatevol ubirmvol ubimkvol ubinfo dumpimage kexec sha256sum md5sum gzip hexdump nanddump nandwrite mtd; do
    for prefix in /bin /sbin /usr/bin /usr/sbin; do
        [ ! -x "$prefix/$tool" ] || echo "$prefix/$tool"
    done
done
for path in /proc/config.gz /sys/kernel/kexec_loaded /sys/kernel/kexec_crash_loaded; do
    [ ! -e "$path" ] || echo "$path exists"
done''',
    'memory': "grep -E '^(MemTotal|MemFree|MemAvailable|Buffers|Cached):' /proc/meminfo",
    'serial-input': '''
ls -l /dev/console /dev/ttyMSM0 /proc/1/fd/0 /proc/1/fd/1 /proc/1/fd/2
for path in /proc/tty/driver/msm_serial /proc/tty/driver/serial; do
    [ ! -r "$path" ] || { echo "$path"; cat "$path"; }
done
for path in /sys/kernel/debug/pinctrl/*/pinmux-pins /sys/kernel/debug/pinctrl/*/pinconf-pins; do
    [ ! -r "$path" ] || { echo "$path"; grep -E 'pin (20|21) ' "$path"; }
done''',
}


def private_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(data)


def collect(args):
    import pexpect

    ipaddress.IPv4Address(args.host)
    if not args.known_hosts.is_file():
        raise ValueError('Supply a separately verified known-hosts file')
    # Never overwrite an earlier capture or change permissions of a user's directory.
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    password = getpass.getpass('Stock SSH password (not saved): ')
    child = pexpect.spawn('ssh', [
        '-tt', '-o', f'UserKnownHostsFile={args.known_hosts.resolve()}',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'NumberOfPasswordPrompts=1',
        '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=10',
        f'{args.user}@{args.host}',
    ], encoding='utf-8', codec_errors='replace', timeout=30)
    try:
        event = child.expect([r'(?i)password:', r'(?m)^/[^\r\n]* # ', pexpect.EOF])
        if event == 0:
            child.sendline(password)
            child.expect(r'(?m)^/[^\r\n]* # ')
        elif event == 2:
            raise RuntimeError('SSH closed before an authenticated stock shell')
        del password
        report = {'host': args.host, 'collected_at_unix': int(time.time()),
                  'remote_writes_requested': False, 'captures': {}}
        for name, command in QUERIES.items():
            token = secrets.token_hex(8)
            begin, end = f'__EX511_{token}_BEGIN__', f'__EX511_{token}_END__'
            # Keep command quoting intact. Everything executed is fixed above.
            line = f'echo {begin}; sh -c {shlex.quote(command)}; echo {end}'
            child.sendline(line)
            child.expect(r'\r?\n' + begin + r'\r?\n')
            child.expect(r'\r?\n' + end + r'\r?\n')
            value = child.before.replace('\r\n', '\n')
            if len(value) > 128 * 1024:
                raise RuntimeError(f'Unexpectedly large {name} metadata response')
            private_write(args.output / f'{name}.txt', value)
            report['captures'][name] = len(value)
            child.expect(r'(?m)^/[^\r\n]* # ')
            print(f'Collected {name}: {len(value)} characters (saved privately)', flush=True)
        private_write(args.output / 'capture.json', json.dumps(report, indent=2) + '\n')
        child.sendline('exit')
        child.expect(pexpect.EOF)
    finally:
        child.close(force=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--user', default='admin', choices=['admin', 'root'])
    parser.add_argument('--known-hosts', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path,
                        help='new directory directly below an existing private parent')
    args = parser.parse_args()
    try:
        collect(args)
    except Exception as error:
        # Do not dump pexpect buffers: they may contain authentication text.
        parser.exit(1, f'Collection stopped ({type(error).__name__}); private partial files retained.\n')
    print('Read-only metadata capture complete. No installer was run.')


if __name__ == '__main__':
    main()
