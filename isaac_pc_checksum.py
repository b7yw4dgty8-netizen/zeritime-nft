#!/usr/bin/env python3
"""Checksum for PC-format saves as the Mac App Store build validates them.

Recovered from arm64 disassembly of the load routine:

  0x1000990c8   state = 0xFEDCBA76                 (init)
  0x1000990d8   state = ROR32(state, 1) + value    (fed every value read)
  0x10000d500   stored = read_u32();  stored ^= 0x96696996;  compare with state

So the hash runs over deserialized values in read order, not over a byte range.
Read order: the u32 at 0x10, then per section its type/param/count triplet
followed by its entries, then one trailing u32, then the stored checksum.
"""

from __future__ import annotations

import struct

XOR_KEY = 0x96696996
INIT = 0xFEDCBA76
PREFIX_OFFSET = 0x10
FIRST_SECTION = 0x14
ENTRY_LENGTHS = [1, 4, 4, 1, 1, 1, 1, 4, 4, 1]


def ror32(value: int) -> int:
    value &= 0xFFFFFFFF
    return ((value >> 1) | (value << 31)) & 0xFFFFFFFF


def digest(data: bytes) -> tuple[int, int]:
    """Return (digest, checksum_offset)."""
    state = INIT

    def feed(value: int) -> None:
        nonlocal state
        state = (ror32(state) + (value & 0xFFFFFFFF)) & 0xFFFFFFFF

    feed(struct.unpack_from("<I", data, PREFIX_OFFSET)[0])

    ofs = FIRST_SECTION
    for entry_len in ENTRY_LENGTHS:
        if ofs + 12 > len(data):
            break
        section_type, param, count = struct.unpack_from("<III", data, ofs)
        if section_type == 0 or section_type > 12 or count > 4000:
            break
        feed(section_type)
        feed(param)
        feed(count)
        ofs += 12
        for k in range(count):
            if entry_len == 4:
                feed(struct.unpack_from("<I", data, ofs + k * 4)[0])
            else:
                feed(data[ofs + k])
        ofs += count * entry_len

    feed(struct.unpack_from("<I", data, ofs)[0])
    return state, ofs + 4


def stored_checksum(data: bytes) -> tuple[int, int]:
    _, offset = digest(data)
    return struct.unpack_from("<I", data, offset)[0], offset


def verify(data: bytes) -> bool:
    value, offset = digest(data)
    return struct.unpack_from("<I", data, offset)[0] == (value ^ XOR_KEY)


def sign(data: bytearray) -> int:
    value, offset = digest(bytes(data))
    checksum = value ^ XOR_KEY
    struct.pack_into("<I", data, offset, checksum)
    return checksum
