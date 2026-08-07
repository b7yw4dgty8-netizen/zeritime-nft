#!/usr/bin/env python3
"""Compare save before/after Isaac session to learn Mac write format."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

import isaac_build_rebirth as ibr

SAVE = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents/persistentgamedata1.dat"
)
OUT = Path(__file__).resolve().parent / "isaac_saves" / "capture"


def summarize(data: bytes, label: str) -> None:
    if len(data) < 500 and data[:2] == b"\xf3\x0a":
        import isaac_mobile as mob

        mob.summarize(data, label)
        blocks = mob.parse_blocks(data)
        print(f"  tlv_blocks@0x1a: {len(blocks)}")
        return
    if len(data) < 200:
        print(f"{label}: {len(data)} bytes (compact)")
        print(f"  header prefix: {data[:4].hex()} text={data[2:18]!r}")
        print(f"  tail: {data[-8:].hex()}")
        return
    sections = ibr.get_section_offsets(data)
    items = sum(1 for i in range(1, 342) if data[sections[3] + i])
    chall = sum(1 for i in range(1, 21) if data[sections[5] + i])
    stored = int.from_bytes(data[-4:], "little")
    calc = ibr.calc_checksum(data, 0x10, len(data) - 0x10 - 4)
    print(
        f"{label}: {len(data)} bytes items={items} chall={chall} "
        f"crc={stored:08X} pc_crc_ok={stored == calc} md5={hashlib.md5(data).hexdigest()[:12]}"
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) < 2 or sys.argv[1] not in {"before", "after"}:
        raise SystemExit("Usage: isaac_capture_save.py before|after")

    tag = sys.argv[1]
    if not SAVE.exists():
        raise SystemExit(f"Missing {SAVE}")

    data = SAVE.read_bytes()
    dest = OUT / f"persistentgamedata1.{tag}.dat"
    shutil.copy2(SAVE, dest)
    summarize(data, tag)

    if tag == "after" and (OUT / "persistentgamedata1.before.dat").exists():
        before = (OUT / "persistentgamedata1.before.dat").read_bytes()
        diffs = [i for i, (a, b) in enumerate(zip(before, data)) if a != b]
        print(f"diff bytes vs before: {len(diffs)}")
        if diffs:
            print("first diffs:", diffs[:30])
            print("last diffs:", diffs[-10:])


if __name__ == "__main__":
    main()
