#!/usr/bin/env python3
"""Try to derive mobile save CRC from known-good samples."""

from __future__ import annotations

from pathlib import Path

import isaac_mobile as mob

SAMPLES = [
    Path("/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents/persistentgamedata2.dat"),
    mob.CAPTURE / "session.before.dat",
    mob.CAPTURE / "session.after.dat",
]


def load_samples() -> list[tuple[str, bytes, int]]:
    out = []
    for p in SAMPLES:
        if not p.exists():
            continue
        d = p.read_bytes()
        out.append((p.name, d, mob.stored_crc(d)))
    return out


def main() -> None:
    samples = load_samples()
    print(f"Known-good mobile saves: {len(samples)}")
    for name, data, crc in samples:
        mob.summarize(data, name)

    print("\nCRC algorithm: not yet identified (not jellyfish / CRC32 / CRC32C / common hashes).")
    print("Samples available for lldb / further RE.")


if __name__ == "__main__":
    main()
