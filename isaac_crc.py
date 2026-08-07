#!/usr/bin/env python3
"""Mobile save CRC — ROR+ADD jellyfish (Mac App Store Isaac).

Confirmed via arm64 RE of The Binding of Isaac Rebirth (App Store):

  init      = 0xFEDCBA76
  step      = state = ROR32(state, 1) + value;  value is each hashed u32/u8
  stored    = digest XOR 0x96696996  (last 4 bytes of save, little-endian)

The digest is computed over *deserialized fields* while loading (not a raw
byte slice). Same core functions: 0x1000990c8 (init), 0x1000990d8 (add u32).

Save stream (mobile, after f3 0a + 16-byte ISAACNGSAVE06R header):
  u32 timestamp @ 0x12
  repeat until EOF-CRC:
    u32 section_type   (1..7 for 06R)
    u32 section_param  (low u16 tag 0x04B3, high u16 byte_length — inferred)
    u32 entry_count
    section payload

Exact field order/count rules for partial mobile saves still being verified.
Use `isaac_crc_trace.py` + lldb hook to capture hash inputs from a live load.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

XOR_KEY = 0x96696996
INIT = 0xFEDCBA76

KNOWN_GOOD = [
    Path("/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents/persistentgamedata2.dat"),
    Path(__file__).resolve().parent / "isaac_saves/capture/session.before.dat",
    Path(__file__).resolve().parent / "isaac_saves/capture/session.after.dat",
    Path(__file__).resolve().parent / "isaac_saves/capture/working_295_18items.dat",
    Path(__file__).resolve().parent / "isaac_saves/capture/working_296_19items.dat",
]


def ror32(value: int, bits: int = 1) -> int:
    value &= 0xFFFFFFFF
    bits &= 31
    return ((value >> bits) | (value << (32 - bits))) & 0xFFFFFFFF


@dataclass
class JellyfishHasher:
    state: int = INIT
    trace: list[int] = field(default_factory=list)

    def reset(self) -> None:
        self.state = INIT
        self.trace.clear()

    def add_u32(self, value: int) -> None:
        value &= 0xFFFFFFFF
        self.state = ror32(self.state) + value
        self.state &= 0xFFFFFFFF
        self.trace.append(value)

    def add_i8(self, value: int) -> None:
        if value >= 128:
            value -= 256
        self.add_u32(value & 0xFFFFFFFF)

    def digest(self) -> int:
        return self.state

    def encode_stored(self) -> int:
        return self.digest() ^ XOR_KEY


def stored_crc(data: bytes) -> int:
    return struct.unpack("<I", data[-4:])[0]


def decode_stored(data: bytes) -> int:
    return stored_crc(data) ^ XOR_KEY


def patch_stored_crc(data: bytearray, digest: int) -> None:
    data[-4:] = (digest ^ XOR_KEY).to_bytes(4, "little")


def calc_mobile_crc(data: bytes) -> int | None:
    """Return stored CRC if parser validates; None if format not implemented."""
    _ = data
    return None


def verify(data: bytes) -> bool:
    calc = calc_mobile_crc(data)
    if calc is None:
        return False
    return stored_crc(data) == calc


def patch_crc(data: bytearray) -> bool:
    calc = calc_mobile_crc(bytes(data))
    if calc is None:
        return False
    data[-4:] = calc.to_bytes(4, "little")
    return True


def summarize_sample(path: Path) -> None:
    import isaac_mobile as mob

    data = path.read_bytes()
    mob.summarize(data, path.name)
    print(f"  digest (stored^key) = {decode_stored(data):08X}")


def main() -> None:
    print("Mobile CRC constants:")
    print(f"  INIT = {INIT:08X}")
    print(f"  XOR  = {XOR_KEY:08X}")
    print()
    print("Known-good samples (digest = stored_crc XOR key):")
    for path in KNOWN_GOOD:
        if not path.exists():
            continue
        summarize_sample(path)
    print()
    print("Full stream parser: NOT YET COMPLETE — cannot patch saves safely.")
    print("Next: run isaac_crc_trace.py while loading slot 1 in Isaac.")


if __name__ == "__main__":
    main()
