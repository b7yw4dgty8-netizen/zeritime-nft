#!/usr/bin/env python3
"""Build experimental mobile 100% Rebirth save for Mac App Store Isaac.

Without a working mobile CRC encoder, outputs are drafts only.
Also builds PC 100% variants for slot-2 conversion tests.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import time
from pathlib import Path

import isaac_build_rebirth as ibr
import isaac_mobile as mob

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "isaac_saves"
PC_FULL = OUT / "rebirth_100_full.dat"
PC_SRC = OUT / "rebirth_deadgod.dat"
TEMPLATE = mob.CAPTURE / "working_307_23items.dat"
SLOT2 = mob.IOS_DOCS / "persistentgamedata2.dat"

MOBILE_PREFIX = mob.MOBILE_PREFIX
HEADER = mob.HEADER
TAG_04B3 = 0x04B3

# Full record seen when unlocking item #30 (+7 bytes @ ~0x8b).
ITEM_RECORD_FULL = bytes([0x01, 0x0F, 0x18, 0x00, 0x05, 0x02, 0x02, 0x00, 0x00])


def build_pc_100() -> bytes:
    if PC_FULL.exists():
        return PC_FULL.read_bytes()
    if not PC_SRC.exists():
        raise SystemExit(f"Missing template: {PC_SRC}")
    data = ibr.build_full_save(PC_SRC.read_bytes())
    PC_FULL.write_bytes(data)
    return bytes(data)


def pack_param(tag: int, payload_len: int) -> int:
    """Mobile param u32: low u16 tag, length in highest byte (from captures)."""
    return (tag & 0xFFFF) | ((payload_len & 0xFF) << 24)


def load_pc_flags() -> dict[str, list[int]]:
    pc = build_pc_100()
    sections = ibr.get_section_offsets(pc)
    return {
        "items": [i for i in range(1, 342) if pc[sections[3] + i]],
        "secrets": [i for i in range(1, 180) if pc[sections[0] + i]],
        "challenges": [i for i in range(1, 21) if pc[sections[ibr.CHALLENGE_SECTION] + i]],
    }


def append_u32(buf: bytearray, val: int) -> None:
    buf.extend(val.to_bytes(4, "little"))


def build_mobile_draft_from_template() -> bytes:
    """Best-effort: extend 23-item mobile with full item records (CRC NOT valid)."""
    if not TEMPLATE.exists():
        raise SystemExit(f"Missing mobile template: {TEMPLATE}")

    base = bytearray(TEMPLATE.read_bytes())
    flags = load_pc_flags()
    have = set(flags["items"])

    # Naive: append full 10-byte item records for missing IDs not already in template.
    # Real encoder needs TLV stream logic; this is a structural placeholder.
    missing = [i for i in range(1, 342) if i not in have]  # from PC perspective all present
    # Items already in template unknown precisely — append records for IDs 1-341 anyway
    # would duplicate; skip destructive merge for now.

    out = bytearray(base)
    # Force donation 999 @ 0x50
    out[mob.DONATION_U16_OFFSET : mob.DONATION_U16_OFFSET + 2] = (999).to_bytes(2, "little")

    # Stamp invalid CRC placeholder (game will reject until patched)
    out[-4:] = b"\xff\xff\xff\xff"
    return bytes(out)


def build_f30a_pc_100() -> bytes:
    pc = build_pc_100()
    return MOBILE_PREFIX + pc


def build_write_style_draft() -> bytes:
    """Serialize PC progress using write-path section order (experimental)."""
    pc = build_pc_100()
    sections = ibr.get_section_offsets(pc)
    buf = bytearray(MOBILE_PREFIX + HEADER)

    ts = int(time.time()) & 0xFFFFFFFF
    append_u32(buf, ts)
    append_u32(buf, 1)  # version?

    def section(typ: int, param_len: int, count: int, payload: bytes) -> None:
        append_u32(buf, typ)
        append_u32(buf, pack_param(TAG_04B3, param_len))
        append_u32(buf, count)
        buf.extend(payload)

    secrets = bytes([1 if pc[sections[0] + i] else 0 for i in range(1, 180)])
    section(1, len(secrets) + 4, min(179, len(secrets)), secrets[:179].rjust(179, b"\x00"))

    counters = b"".join(
        int.from_bytes(pc[sections[2] + i * 4 : sections[2] + i * 4 + 4], "little").to_bytes(4, "little")
        for i in range(95)
    )
    section(2, len(counters) + 4, 95, counters[: 95 * 4])

    items = bytes([1 if pc[sections[3] + i] else 0 for i in range(1, 342)])
    section(4, len(items) + 4, 341, items[:341])

    challenges = bytes([1 if pc[sections[ibr.CHALLENGE_SECTION] + i] else 0 for i in range(1, 21)])
    section(7, len(challenges) + 4, 20, challenges[:20])

    # Footer guess (from 23-item saves)
    buf.extend(bytes([0x00, 0x02, 0x00, 0x80, 0x20, 0x01, 0x00, 0x00]))
    append_u32(buf, 0xFFFFFFFF)  # invalid CRC
    return bytes(buf)


def install_slot2(data: bytes, label: str) -> None:
    mob.quit_isaac()
    time.sleep(1)
    backup = SLOT2.with_suffix(SLOT2.suffix + f".pre_{label}.bak")
    if SLOT2.exists():
        shutil.copy2(SLOT2, backup)
    SLOT2.write_bytes(data)
    SLOT2.chmod(0o644)
    subprocess.run(["chflags", "nouchg", str(SLOT2)], check=False)
    mob.summarize(data, f"slot2 ({label})")


def try_conversion_test() -> None:
    """Install PC 100% to slot 2, launch game, read back converted mobile."""
    pc = build_pc_100()
    install_slot2(pc, "pc100")
    print("\nLaunching Isaac for conversion test (slot 2)...")
    subprocess.run(["open", "-a", "The Binding of Isaac: Rebirth"], check=False)
    time.sleep(8)
    mob.quit_isaac()
    time.sleep(2)
    if SLOT2.exists():
        converted = SLOT2.read_bytes()
        out = OUT / "rebirth_100_slot2_converted.dat"
        out.write_bytes(converted)
        mob.summarize(converted, "slot2 after launch")
        print(f"Saved converted sample: {out}")
        if len(converted) < 500:
            ibr.summarize(converted) if converted[:16] == ibr.HEADER[:16] else None


def main() -> None:
    OUT.mkdir(exist_ok=True)
    flags = load_pc_flags()
    print("PC 100% flags:")
    print(f"  items={len(flags['items'])}/341 secrets={len(flags['secrets'])}/179 challenges={len(flags['challenges'])}/20")

    pc = build_pc_100()
    mob.summarize(pc, "pc100") if len(pc) > 500 else None
    ibr.summarize(pc)

    f30a = build_f30a_pc_100()
    (OUT / "rebirth_100_f30a_pc.dat").write_bytes(f30a)
    print(f"\nWrote {OUT / 'rebirth_100_f30a_pc.dat'} ({len(f30a)} bytes)")

    draft = build_mobile_draft_from_template()
    (OUT / "rebirth_mobile_100_draft.dat").write_bytes(draft)
    print(f"Wrote {OUT / 'rebirth_mobile_100_draft.dat'} ({len(draft)} bytes) — CRC INVALID")

    write_draft = build_write_style_draft()
    (OUT / "rebirth_mobile_100_write_draft.dat").write_bytes(write_draft)
    print(f"Wrote {OUT / 'rebirth_mobile_100_write_draft.dat'} ({len(write_draft)} bytes) — CRC INVALID")

    print("\n=== Conversion test (PC 100% -> slot 2 -> read back) ===")
    try_conversion_test()

    print("\nDo NOT install CRC-invalid drafts to slot 1.")
    print("If slot-2 conversion produced valid mobile, check rebirth_100_slot2_converted.dat")


if __name__ == "__main__":
    main()
