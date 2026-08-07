#!/usr/bin/env python3
"""Mac App Store Isaac — mobile persistentgamedata (f3 0a, ~145–400 bytes)."""

from __future__ import annotations

import hashlib
import shutil
import struct
import subprocess
from pathlib import Path

MOBILE_PREFIX = b"\xf3\x0a"
HEADER = b"ISAACNGSAVE06R  "
IOS_DOCS = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents"
)
SLOT1 = IOS_DOCS / "persistentgamedata1.dat"
CAPTURE = Path(__file__).resolve().parent / "isaac_saves" / "capture"
WORKING_BACKUP = CAPTURE / "working_307_23items.dat"
SLOT3_BACKUP = CAPTURE / "working_338_slot3_100.dat"
FALLBACK_BACKUP = CAPTURE / "working_304_22items.dat"

DONATION_U16_OFFSET = 0x50  # in small saves: often machine fill; in large saves: total donated

# Picking up item 30 added 7 bytes @ ~0x8b:
#   01 0f 18 00 05 02 02 00 00 <item_id_u8>
ITEM_RECORD_PREFIX = bytes([0x01, 0x0F, 0x18, 0x00, 0x05, 0x02, 0x02, 0x00, 0x00])


def is_mobile(data: bytes) -> bool:
    return len(data) < 500 and data[:2] == MOBILE_PREFIX and data[2:18] == HEADER


def is_pc(data: bytes) -> bool:
    return len(data) >= 1259 and data[:16] == HEADER


def payload_slice(data: bytes) -> tuple[int, int]:
    """Return (start, end) of body excluding prefix, header, and 4-byte tail."""
    start = 18 if data[:2] == MOBILE_PREFIX else 16
    return start, len(data) - 4


def stored_crc(data: bytes) -> int:
    return int.from_bytes(data[-4:], "little")


def summarize(data: bytes, label: str = "save") -> None:
    kind = "mobile" if is_mobile(data) else "pc" if is_pc(data) else "unknown"
    start, end = payload_slice(data)
    print(
        f"{label}: {len(data)} bytes ({kind}) "
        f"crc={stored_crc(data):08X} body={end - start} "
        f"md5={hashlib.md5(data).hexdigest()[:12]}"
    )
    if is_mobile(data):
        ts = int.from_bytes(data[0x12:0x16], "little")
        print(f"  timestamp@0x12: {ts} ({data[0x12:0x16].hex()})")
        if len(data) > DONATION_U16_OFFSET + 2:
            val = int.from_bytes(data[DONATION_U16_OFFSET : DONATION_U16_OFFSET + 2], "little")
            print(f"  u16@{DONATION_U16_OFFSET:#x}: {val} (donation area)")


def parse_blocks(data: bytes) -> list[tuple[int, int, int, bytes]]:
    """Best-effort TLV: u16 tag, u16 len, payload at offset 0x1a."""
    if not is_mobile(data):
        return []
    pos = 0x1A
    blocks: list[tuple[int, int, int, bytes]] = []
    while pos + 4 <= len(data) - 4:
        tag = struct.unpack_from("<H", data, pos)[0]
        ln = struct.unpack_from("<H", data, pos + 2)[0]
        if ln == 0 or ln > 512 or pos + 4 + ln > len(data) - 4:
            break
        payload = data[pos + 4 : pos + 4 + ln]
        blocks.append((pos, tag, ln, payload))
        pos += 4 + ln
    return blocks


def diff_saves(a: bytes, b: bytes) -> list[tuple[int, int, int]]:
    n = max(len(a), len(b))
    out: list[tuple[int, int, int]] = []
    for i in range(n):
        av = a[i] if i < len(a) else -1
        bv = b[i] if i < len(b) else -1
        if av != bv:
            out.append((i, av, bv))
    return out


def quit_isaac() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "The Binding of Isaac: Rebirth" to quit'],
        check=False,
    )
    subprocess.run(["pkill", "-f", "The Binding of Isaac"], check=False)


def restore_working_slot1() -> None:
    src = WORKING_BACKUP if WORKING_BACKUP.exists() else FALLBACK_BACKUP
    if not src.exists():
        raise SystemExit(f"Missing backup: {WORKING_BACKUP}")
    quit_isaac()
    shutil.copy2(src, SLOT1)
    SLOT1.chmod(0o644)
    subprocess.run(["chflags", "nouchg", str(SLOT1)], check=False)
    summarize(SLOT1.read_bytes(), "restored slot1")


def restore_working_slot3() -> None:
    src = SLOT3_BACKUP
    if not src.exists():
        raise SystemExit(f"Missing backup: {SLOT3_BACKUP}")
    slot3 = IOS_DOCS / "persistentgamedata3.dat"
    quit_isaac()
    shutil.copy2(src, slot3)
    slot3.chmod(0o644)
    subprocess.run(["chflags", "nouchg", str(slot3)], check=False)
    summarize(slot3.read_bytes(), "restored slot3")


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: isaac_mobile.py restore|restore-slot3|summarize [path]|diff <a> <b>|blocks [path]"
        )

    cmd = sys.argv[1]
    if cmd == "restore":
        restore_working_slot1()
        return

    if cmd == "restore-slot3":
        restore_working_slot3()
        return

    if cmd == "summarize":
        path = Path(sys.argv[2]) if len(sys.argv) > 2 else SLOT1
        summarize(path.read_bytes(), path.name)
        return

    if cmd == "blocks":
        path = Path(sys.argv[2]) if len(sys.argv) > 2 else SLOT1
        data = path.read_bytes()
        for pos, tag, ln, payload in parse_blocks(data):
            print(f"@{pos:#x} tag={tag:#06x} len={ln} head={payload[:12].hex()}")
        return

    if cmd == "diff":
        a = Path(sys.argv[2]).read_bytes()
        b = Path(sys.argv[3]).read_bytes()
        changes = diff_saves(a, b)
        print(f"len {len(a)} vs {len(b)} — {len(changes)} byte diffs")
        for off, av, bv in changes[:50]:
            print(f"  @{off:#x}: {av:02x} -> {bv:02x}")
        if len(changes) > 50:
            print(f"  ... +{len(changes) - 50} more")
        return

    raise SystemExit(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
