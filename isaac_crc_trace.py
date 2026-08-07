#!/usr/bin/env python3
"""Replay hash trace captured from lldb to derive mobile CRC."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from isaac_crc import JellyfishHasher, XOR_KEY, decode_stored, stored_crc


def replay(values: list[int]) -> int:
    h = JellyfishHasher()
    for v in values:
        h.add_u32(v)
    return h.digest()


def parse_trace(text: str) -> list[int]:
    values: list[int] = []
    for line in text.splitlines():
        m = re.search(r"(?:HASH_ADD|w1)\s*=?\s*(?:0x)?([0-9a-fA-F]+)", line)
        if m:
            values.append(int(m.group(1), 16))
            continue
        m = re.search(r"\b(\d+)\b", line)
        if "HASH" in line and m:
            values.append(int(m.group(1)))
    return values


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: isaac_crc_trace.py <trace.txt> [save.dat]")
        print("Trace file: one hash addend per line (decimal or 0x hex).")
        raise SystemExit(1)

    trace_path = Path(sys.argv[1])
    values = parse_trace(trace_path.read_text())
    if not values:
        raise SystemExit("No values parsed from trace")

    digest = replay(values)
    print(f"Steps: {len(values)}")
    print(f"Digest: {digest:08X}")
    print(f"Stored CRC would be: {(digest ^ XOR_KEY):08X}")

    if len(sys.argv) >= 3:
        save = Path(sys.argv[2]).read_bytes()
        want = decode_stored(save)
        print(f"Save expects digest: {want:08X} (stored {stored_crc(save):08X})")
        print(f"Match: {digest == want}")


if __name__ == "__main__":
    main()
