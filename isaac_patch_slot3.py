#!/usr/bin/env python3
"""Patch slot 3 — DISABLED until mobile CRC is solved.

Previous attempt patched @0x50 thinking it was donation machine fill; that
offset is TOTAL_DONATIONS (Statistics_offset 0x50). Editing without a valid
CRC wiped the slot to a 145-byte empty save.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import time
from pathlib import Path

import isaac_mobile as mob

SLOT3 = mob.IOS_DOCS / "persistentgamedata3.dat"
BACKUP = mob.CAPTURE / "working_338_slot3_100.dat"

DONATION_OFFSET = mob.DONATION_U16_OFFSET  # 0x50, u16 LE (999 = e7 03)
STREAK_OFFSET = 0x81  # u32 LE win streak in full mobile saves
TARGET_DONATION = 999
TARGET_STREAK = 0


def quit_isaac() -> None:
    mob.quit_isaac()
    time.sleep(1)


def patch(data: bytearray) -> tuple[int, int]:
    old_donation = struct.unpack_from("<H", data, DONATION_OFFSET)[0]
    old_streak = struct.unpack_from("<I", data, STREAK_OFFSET)[0]

    struct.pack_into("<H", data, DONATION_OFFSET, TARGET_DONATION)
    struct.pack_into("<I", data, STREAK_OFFSET, TARGET_STREAK)

    return old_donation, old_streak


def main() -> None:
    raise SystemExit(
        "Slot 3 patch is disabled: mobile CRC is unknown. "
        "Restoring backup would wipe the save again. "
        "Use: python3 isaac_mobile.py restore-slot3"
    )


if __name__ == "__main__":
    main()
