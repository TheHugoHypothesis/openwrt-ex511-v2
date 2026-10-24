# SPDX-License-Identifier: GPL-2.0-only
"""Read properties from a flattened device tree without external modules."""
import struct


def read_fdt(data):
    magic, total, off_struct, off_strings, _, version, _, _, nstrings, nstruct = struct.unpack_from('>10I', data)
    if magic != 0xd00dfeed or version < 17 or total > len(data):
        raise ValueError('Not a complete FDT version 17 or later')
    strings = data[off_strings:off_strings + nstrings]
    end = off_struct + nstruct
    if end > total or off_strings + nstrings > total:
        raise ValueError('FDT block outside total size')
    pos, stack, nodes = off_struct, [], {}
    while pos < end:
        token, = struct.unpack_from('>I', data, pos)
        pos += 4
        if token == 1:
            term = data.index(b'\0', pos, end)
            stack.append(data[pos:term].decode())
            nodes['/'.join(stack) or '/'] = {}
            pos = (term + 4) & ~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            length, nameoff = struct.unpack_from('>II', data, pos)
            pos += 8
            name = strings[nameoff:strings.index(b'\0', nameoff)].decode()
            if pos + length > end:
                raise ValueError('Truncated FDT property')
            nodes['/'.join(stack) or '/'][name] = data[pos:pos + length]
            pos = (pos + length + 3) & ~3
        elif token == 9:
            if stack:
                raise ValueError('Unclosed FDT node')
            return nodes
        elif token != 4:
            raise ValueError(f'Unknown FDT token {token}')
    raise ValueError('Missing FDT end token')


def cells(data):
    return list(struct.unpack('>' + 'I' * (len(data) // 4), data))
