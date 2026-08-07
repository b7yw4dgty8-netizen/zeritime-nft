#!/usr/bin/env python3
"""Build / patch Mac App Store Isaac mobile saves (experimental)."""

from __future__ import annotations

import shutil
import struct
import subprocess
import time
from pathlib import Path

import isaac_build_rebirth as ibr
import isaac_mobile as mob

ROOT = Path(__file__).resolve().parent
CAPTURE = ROOT / "isaac_saves" / "capture"
TEMPLATE = CAPTURE / "session.after.dat"  # 18 items, valid CRC
PC_FULL = ROOT / "isaac_saves" / "rebirth_100_full.dat"
OUT = ROOT / "isaac_saves" / "rebirth_mobile_draft.dat"

# Observed when picking up item 30 (0x1e): +7 bytes at collection block ~0x8b.
# Full replacement region (after 0f0200 tag context):
#   old: 1f 00 36
#   new: 01 0f 18 00 05 02 02 00 00 1e
ITEM_RECORD_SUFFIX = bytes([0x05, 0x02, 0x02, 0x00, 0x00])  # + item_id u8


def quit_isaac() -> None:
    mob.quit_isaac()
    time.sleep(1)


def load_pc_items() -> list[int]:
    data = PC_FULL.read_bytes()
    sections = ibr.get_section_offsets(data)
    return [i for i in range(1, 342) if data[sections[3] + i]]


def find_item_bytes(data: bytes, item_id: int) -> list[int]:
    hits = []
    for i in range(len(data)):
        if data[i] == item_id:
            hits.append(i)
    return hits


def draft_add_items(base: bytes, item_ids: list[int]) -> bytes:
    """Naive draft — cannot set CRC yet."""
    out = bytearray(base)
    # TODO: proper stream encoder; for now return base unchanged.
    _ = item_ids
    return bytes(out)


def install_draft(data: bytes) -> None:
    quit_isaac()
    if mob.SLOT1.exists():
        shutil.copy2(mob.SLOT1, mob.SLOT1.with_name("persistentgamedata1.dat.pre_draft.bak"))
    mob.SLOT1.write_bytes(data)
    mob.SLOT1.chmod(0o644)


def main() -> None:
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing template: {TEMPLATE}")

    base = TEMPLATE.read_bytes()
    mob.summarize(base, "template")

    pc_items = set(load_pc_items())
    have = set()
    for i in range(1, 342):
        if find_item_bytes(base, i):
            # weak detection — many false positives
            if i in pc_items and i <= 50:
                have.add(i)

    missing = sorted(pc_items - have)
    print(f"PC rebirth items: {len(pc_items)}")
    print(f"Template scan (weak): ~{len(have)} ids in first 50 range")
    print(f"First missing (sample): {missing[:20]}...")

    draft = draft_add_items(base, missing)
    OUT.write_bytes(draft)
    print(f"\nDraft written: {OUT} ({len(draft)} bytes)")
    print("CRC not patched — do NOT install until isaac_crc.py validates.")
    print("\nNext: reverse CRC from 3 known-good saves or lldb hook.")


if __name__ == "__main__":
    main()
