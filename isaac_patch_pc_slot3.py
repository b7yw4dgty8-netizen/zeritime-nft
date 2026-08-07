#!/usr/bin/env python3
"""Patch the PC-format 100% save the game imports, then re-sign it.

The mobile checksum is still unsolved, so the converted mobile save cannot be
edited; the edits land in the PC file before import instead. That file *is*
checksum-validated, so isaac_pc_checksum.sign must run after every edit.

Counter section (type 2) layout, offsets relative to its payload start.
Confirmed against the numbers the game displays:
  0x04  mom kills                (545)
  0x24  deaths                   (772)
  0x4C  donation machine coins   (1113, shown as 113 -- display keeps 3 digits)
  0x50  total donated
  0x58  streak shown as BEST STREAK
  0x5C  secondary streak counter
"""

from __future__ import annotations

import struct
from pathlib import Path

import isaac_pc_checksum as pccrc

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "isaac_saves" / "capture" / "source_downloads_persistentgamedata2.dat"
OUTPUT = ROOT / "isaac_saves" / "rebirth_pc_donation999_streak0.dat"
SLOT3 = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents"
    "/persistentgamedata3.dat"
)

COUNTER_SECTION_TYPE = 2
ENTRY_LENGTHS = [1, 4, 4, 1, 1, 1, 1, 4, 4, 1]

STAT_EDITS = [
    ("mom kills", 0x04, 0),
    ("deaths", 0x24, 0),
    ("donation coins", 0x4C, 999),
    ("streak", 0x58, 0),
    ("streak (alt)", 0x5C, 0),
]


def counter_section_offset(data: bytes) -> int:
    ofs = 0x14
    for entry_len in ENTRY_LENGTHS:
        if ofs + 12 > len(data):
            break
        section_type = struct.unpack_from("<I", data, ofs)[0]
        count = struct.unpack_from("<I", data, ofs + 8)[0]
        payload = ofs + 12
        if section_type == COUNTER_SECTION_TYPE:
            return payload
        ofs = payload + count * entry_len
    raise SystemExit("Counter section not found")


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source save: {SOURCE}")

    data = bytearray(SOURCE.read_bytes())
    if data[:16] != b"ISAACNGSAVE06R  ":
        raise SystemExit(f"Unexpected header: {data[:16]!r}")
    if not pccrc.verify(bytes(data)):
        raise SystemExit("Source checksum does not verify; the model is wrong")

    base = counter_section_offset(data)
    print(f"Counter section @{base:#x}")

    for name, stat_offset, target in STAT_EDITS:
        absolute = base + stat_offset
        old = struct.unpack_from("<I", data, absolute)[0]
        struct.pack_into("<I", data, absolute, target)
        print(f"  {name} @{absolute:#x} (stat 0x{stat_offset:02X}): {old} -> {target}")

    checksum = pccrc.sign(data)
    print(f"Re-signed: checksum {checksum:08X}")
    if not pccrc.verify(bytes(data)):
        raise SystemExit("Re-signing failed verification")

    OUTPUT.write_bytes(data)
    print(f"Written: {OUTPUT} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
