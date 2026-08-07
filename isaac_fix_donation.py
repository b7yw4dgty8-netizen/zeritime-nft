#!/usr/bin/env python3
"""Fix Isaac iOS donation machine counter in persistentgamedata save."""

from __future__ import annotations

import shutil
from pathlib import Path

SAVE = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents/persistentgamedata1.dat"
)
BACKUP = SAVE.with_suffix(".dat.bak")
OUTPUT = Path(__file__).resolve().parent / "persistentgamedata1_fixed.dat"

# Mobile serialized stat record: 02 00 <stat_id> <u16_le value> 00 00
DONATION_STAT_OFFSET = 0xC1
DONATION_MACHINE_STAT = 0x50  # mobile stream id for donation machine fill level
TARGET_COINS = 999


def read_u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def write_u16(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 2] = value.to_bytes(2, "little")


def main() -> None:
    source = BACKUP if BACKUP.exists() else SAVE
    data = bytearray(source.read_bytes())

    print(f"Source: {source}")
    print(f"Size: {len(data)} bytes")
    print(f"Header: {data[2:18]!r}")

    stat_id = data[DONATION_STAT_OFFSET - 1]
    current = read_u16(data, DONATION_STAT_OFFSET)
    print(f"Donation stat id: 0x{stat_id:02X}")
    print(f"Current value at 0x{DONATION_STAT_OFFSET:X}: {current}")

    if stat_id != DONATION_MACHINE_STAT:
        raise SystemExit(
            f"Unexpected stat id 0x{stat_id:02X} at 0x{DONATION_STAT_OFFSET - 1:X}; aborting."
        )

    write_u16(data, DONATION_STAT_OFFSET, TARGET_COINS)
    print(f"Updated value: {read_u16(data, DONATION_STAT_OFFSET)}")

    OUTPUT.write_bytes(data)
    SAVE.write_bytes(data)
    print(f"Written: {OUTPUT}")
    print(f"Written: {SAVE}")

    if not BACKUP.exists():
        shutil.copy2(source, BACKUP)
        print(f"Backup created: {BACKUP}")


if __name__ == "__main__":
    main()
