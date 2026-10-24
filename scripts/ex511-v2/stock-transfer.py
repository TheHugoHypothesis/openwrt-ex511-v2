#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded binary transfers using stock SSH shell requests (not SSH exec).

Does not flash, modify boot policy, reboot, obtain root, or accept new host keys.
Uses SSH shell requests instead of remote exec requests. Credentials
are prompted locally, never saved. Requires Python 3 + pexpect on Linux.
"""
import argparse
import getpass
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import secrets
import shlex
import tty


class Shell:
    def __init__(self, args):
        import pexpect
        self.pexpect = pexpect
        argv = ['-T', '-o', 'StrictHostKeyChecking=yes', '-o',
                f'UserKnownHostsFile={args.known_hosts.resolve()}',
                '-o', 'EscapeChar=none', '-o', 'ConnectTimeout=8',
                '-o', 'ServerAliveInterval=10', '-o', 'NumberOfPasswordPrompts=1']
        if args.host_key_alias:
            argv += ['-o', 'HostKeyAlias='+args.host_key_alias]
        if args.source:
            argv += ['-b', args.source]
        argv += [f'{args.user}@{args.host}']
        self.p = pexpect.spawn('ssh', argv, encoding=None, timeout=180,
                               maxread=65536)
        self.p.logfile = None
        tty.setraw(self.p.child_fd)
        try:
            # Stock prompts for a password; OpenWrt may authenticate by key and
            # offer a non-PTY shell with no prompt. A marker exchange verifies it.
            event = self.p.expect([rb'(?i)password:', pexpect.EOF, pexpect.TIMEOUT], timeout=5)
            if event == 0:
                password = getpass.getpass('SSH password (not saved): ')
                self.p.sendline(password.encode())
                del password
            elif event == 1:
                raise ValueError('SSH closed before shell authentication')
            uid = self.command("grep '^Uid:' /proc/self/status")
            if not re.fullmatch(r'Uid:\s+0\s+0\s+0\s+0', uid):
                raise ValueError('Shell does not demonstrate effective root')
        except BaseException:
            self.close()
            raise

    def command(self, command):
        marker = ('EX511_' + secrets.token_hex(16)).encode()
        line = b'echo ' + marker + b'; ' + command.encode() + b'; echo ' + marker + b'_END'
        if len(line) > 500:
            raise ValueError('Command exceeds tested stock shell line bound')
        self.p.sendline(line)
        self.p.expect(re.escape(marker) + rb'\r?\n')
        self.p.expect(re.escape(marker) + rb'_END\r?\n')
        return self.p.before.decode(errors='strict').strip()

    def get(self, remote, length):
        marker = ('EX511_' + secrets.token_hex(16)).encode()
        count = (length + 131071) // 131072
        command = f'dd if={shlex.quote(remote)} bs=131072 count={count} 2>/dev/null'
        self.p.sendline(b'echo ' + marker + b'; ' + command.encode() + b'; echo ' + marker + b'_END')
        self.p.expect(re.escape(marker) + rb'\r?\n')
        data = bytearray()
        while len(data) < length:
            data.extend(self.p.read(min(65536, length - len(data))))
        self.p.expect(re.escape(marker) + rb'_END\r?\n')
        # dd must not have emitted any extra payload between exact size and end.
        if self.p.before not in (b'', b'\n', b'\r\n'):
            raise ValueError('Remote data exceeds requested exact length')
        return bytes(data)

    def put(self, remote, data):
        if self.command('umask 077; mkdir -p /tmp/ex511-install; chmod 700 /tmp/ex511-install; echo READY') != 'READY':
            raise ValueError('Cannot prepare private RAM directory')
        if self.command('test ! -e ' + shlex.quote(remote) + '; echo $?') != '0':
            raise ValueError('Refusing to overwrite an existing remote file')
        marker = ('EX511_' + secrets.token_hex(16)).encode()
        command = f'umask 077; dd of={shlex.quote(remote)} bs=1 count={len(data)} 2>/dev/null'
        self.p.sendline(b'echo ' + marker + b'; ' + command.encode() + b'; echo ' + marker + b'_END:$?')
        self.p.expect(re.escape(marker) + rb'\r?\n')
        for pos in range(0, len(data), 65536):
            piece = data[pos:pos + 65536]
            sent = 0
            while sent < len(piece):
                n = self.p.send(piece[sent:])
                if n <= 0:
                    raise ValueError('SSH upload stalled')
                sent += n
        self.p.expect(re.escape(marker) + rb'_END:0\r?\n')
        if self.get(remote, len(data)) != data:
            raise ValueError('RAM round-trip differs from local image; do not flash')

    def close(self):
        if self.p.isalive():
            self.p.sendline(b'exit')
        self.p.close(force=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host', required=True)
    p.add_argument('--user', choices=['admin', 'root'], default='admin')
    p.add_argument('--source')
    p.add_argument('--host-key-alias', help='optional name already pinned in known-hosts')
    p.add_argument('--known-hosts', type=Path, required=True)
    sub = p.add_subparsers(dest='operation', required=True)
    get = sub.add_parser('get', help='read an exact-length MTD or staged RAM file')
    get.add_argument('--remote', required=True)
    get.add_argument('--bytes', type=int, required=True)
    get.add_argument('--output', type=Path, required=True)
    put = sub.add_parser('put', help='write only a new RAM file, then verify byte-for-byte')
    put.add_argument('--remote', required=True)
    put.add_argument('--input', type=Path, required=True)
    a = p.parse_args()
    shell = None
    try:
        ipaddress.IPv4Address(a.host)
        if a.source:
            ipaddress.IPv4Address(a.source)
        if not a.known_hosts.is_file():
            raise ValueError('A separately verified known-hosts file is required')
        ram = re.fullmatch(r'/tmp/ex511-install/[A-Za-z0-9_.-]+', a.remote)
        if a.operation == 'get':
            if not (ram or re.fullmatch(r'/dev/mtd[0-9]+', a.remote)) or not 0 < a.bytes <= 128 * 1024 * 1024:
                raise ValueError('Unsupported source/length; use verified physical MTD metadata')
            # Reserve a new protected output before connecting; never overwrite.
            fd = os.open(a.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                shell = Shell(a)
                data = shell.get(a.remote, a.bytes)
                stream.write(data)
        else:
            if not ram or not a.input.is_file():
                raise ValueError('Upload destination must be a new /tmp/ex511-install file')
            data = a.input.read_bytes()
            if not 0 < len(data) <= 32 * 1024 * 1024:
                raise ValueError('RAM upload must be between 1 byte and 32 MiB')
            shell = Shell(a)
            shell.put(a.remote, data)
        print(f'{a.operation}: {len(data)} bytes; SHA256 {hashlib.sha256(data).hexdigest()}')
        if a.operation == 'put':
            print('RAM round-trip verified; no firmware/environment write requested.')
    except Exception as error:
        # Never include pexpect buffers, credentials, factory bytes or raw output.
        p.exit(1, f'Transfer stopped ({type(error).__name__}). Inspect private files; do not infer success or retry a flash.\n')
    finally:
        if shell:
            shell.close()


if __name__ == '__main__':
    main()
