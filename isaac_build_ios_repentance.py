#!/usr/bin/env python3
"""Build 100% Repentance save for iOS import via rep_persistentgamedata1.dat."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "isaac_saves" / "rep_deadgod.dat"
IOS_DIR = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents"
)
IOS_PERSISTENT = IOS_DIR / "persistentgamedata1.dat"
IOS_REP = IOS_DIR / "rep_persistentgamedata1.dat"

CHARACTERS = 34
SKIP_ITEMS = {43, 59, 61, 235, 587, 613, 620, 630, 648, 656, 662, 666, 718}
HARD_MARK = 2


def rshift(val: int, n: int) -> int:
    return val >> n if val >= 0 else (val + 0x100000000) >> n


CRC_TABLE = [
    0x00000000, 0x09073096, 0x120E612C, 0x1B0951BA, 0xFF6DC419, 0xF66AF48F, 0xED63A535, 0xE46495A3,
    0xFEDB8832, 0xF7DCB8A4, 0xECD5E91E, 0xE5D2D988, 0x01B64C2B, 0x08B17CBD, 0x13B82D07, 0x1ABF1D91,
    0xFDB71064, 0xF4B020F2, 0xEFB97148, 0xE6BE41DE, 0x02DAD47D, 0x0BDDE4EB, 0x10D4B551, 0x19D385C7,
    0x036C9856, 0x0A6BA8C0, 0x1162F97A, 0x1865C9EC, 0xFC015C4F, 0xF5066CD9, 0xEE0F3D63, 0xE7080DF5,
    0xFB6E20C8, 0xF269105E, 0xE96041E4, 0xE0677172, 0x0403E4D1, 0x0D04D447, 0x160D85FD, 0x1F0AB56B,
    0x05B5A8FA, 0x0CB2986C, 0x17BBC9D6, 0x1EBCF940, 0xFAD86CE3, 0xF3DF5C75, 0xE8D60DCF, 0xE1D13D59,
    0x06D930AC, 0x0FDE003A, 0x14D75180, 0x1DD06116, 0xF9B4F4B5, 0xF0B3C423, 0xEBBA9599, 0xE2BDA50F,
    0xF802B89E, 0xF1058808, 0xEA0CD9B2, 0xE30BE924, 0x076F7C87, 0x0E684C11, 0x15611DAB, 0x1C662D3D,
    0xF6DC4190, 0xFFDB7106, 0xE4D220BC, 0xEDD5102A, 0x09B18589, 0x00B6B51F, 0x1BBFE4A5, 0x12B8D433,
    0x0807C9A2, 0x0100F934, 0x1A09A88E, 0x130E9818, 0xF76A0DBB, 0xFE6D3D2D, 0xE5646C97, 0xEC635C01,
    0x0B6B51F4, 0x026C6162, 0x196530D8, 0x1062004E, 0xF40695ED, 0xFD01A57B, 0xE608F4C1, 0xEF0FC457,
    0xF5B0D9C6, 0xFCB7E950, 0xE7BEB8EA, 0xEEB9887C, 0x0ADD1DDF, 0x03DA2D49, 0x18D37CF3, 0x11D44C65,
    0x0DB26158, 0x04B551CE, 0x1FBC0074, 0x16BB30E2, 0xF2DFA541, 0xFBD895D7, 0xE0D1C46D, 0xE9D6F4FB,
    0xF369E96A, 0xFA6ED9FC, 0xE1678846, 0xE860B8D0, 0x0C042D73, 0x05031DE5, 0x1E0A4C5F, 0x170D7CC9,
    0xF005713C, 0xF90241AA, 0xE20B1010, 0xEB0C2086, 0x0F68B525, 0x066F85B3, 0x1D66D409, 0x1461E49F,
    0x0EDEF90E, 0x07D9C998, 0x1CD09822, 0x15D7A8B4, 0xF1B33D17, 0xF8B40D81, 0xE3BD5C3B, 0xEABA6CAD,
    0xEDB88320, 0xE4BFB3B6, 0xFFB6E20C, 0xF6B1D29A, 0x12D54739, 0x1BD277AF, 0x00DB2615, 0x09DC1683,
    0x13630B12, 0x1A643B84, 0x016D6A3E, 0x086A5AA8, 0xEC0ECF0B, 0xE509FF9D, 0xFE00AE27, 0xF7079EB1,
    0x100F9344, 0x1908A3D2, 0x0201F268, 0x0B06C2FE, 0xEF62575D, 0xE66567CB, 0xFD6C3671, 0xF46B06E7,
    0xEED41B76, 0xE7D32BE0, 0xFCDA7A5A, 0xF5DD4ACC, 0x11B9DF6F, 0x18BEEFF9, 0x03B7BE43, 0x0AB08ED5,
    0x16D6A3E8, 0x1FD1937E, 0x04D8C2C4, 0x0DDFF252, 0xE9BB67F1, 0xE0BC5767, 0xFBB506DD, 0xF2B2364B,
    0xE80D2BDA, 0xE10A1B4C, 0xFA034AF6, 0xF3047A60, 0x1760EFC3, 0x1E67DF55, 0x056E8EEF, 0x0C69BE79,
    0xEB61B38C, 0xE266831A, 0xF96FD2A0, 0xF068E236, 0x140C7795, 0x1D0B4703, 0x060216B9, 0x0F05262F,
    0x15BA3BBE, 0x1CBD0B28, 0x07B45A92, 0x0EB36A04, 0xEAD7FFA7, 0xE3D0CF31, 0xF8D99E8B, 0xF1DEAE1D,
    0x1B64C2B0, 0x1263F226, 0x096AA39C, 0x006D930A, 0xE40906A9, 0xED0E363F, 0xF6076785, 0xFF005713,
    0xE5BF4A82, 0xECB87A14, 0xF7B12BAE, 0xFEB61B38, 0x1AD28E9B, 0x13D5BE0D, 0x08DCEFB7, 0x01DBDF21,
    0xE6D3D2D4, 0xEFD4E242, 0xF4DDB3F8, 0xFDDA836E, 0x19BE16CD, 0x10B9265B, 0x0BB077E1, 0x02B74777,
    0x18085AE6, 0x110F6A70, 0x0A063BCA, 0x03010B5C, 0xE7659EFF, 0xEE62AE69, 0xF56BFFD3, 0xFC6CCF45,
    0xE00AE278, 0xE90DD2EE, 0xF2048354, 0xFB03B3C2, 0x1F672661, 0x166016F7, 0x0D69474D, 0x046E77DB,
    0x1ED16A4A, 0x17D65ADC, 0x0CDF0B66, 0x05D83BF0, 0xE1BCAE53, 0xE8BB9EC5, 0xF3B2CF7F, 0xFAB5FFE9,
    0x1DBDF21C, 0x14BAC28A, 0x0FB39330, 0x06B4A3A6, 0xE2D03605, 0xEBD70693, 0xF0DE5729, 0xF9D967BF,
    0xE3667A2E, 0xEA614AB8, 0xF1681B02, 0xF86F2B94, 0x1C0BBE37, 0x150C8EA1, 0x0E05DF1B, 0x0702EF8D,
]


def calc_checksum(data: bytes | bytearray, ofs: int, length: int) -> int:
    checksum = ~0xFEDCBA76
    for i in range(ofs, ofs + length):
        checksum = CRC_TABLE[(checksum & 0xFF) ^ data[i]] ^ rshift(checksum, 8)
    return (~checksum + 2**32) & 0xFFFFFFFF


def update_checksum(data: bytearray) -> bytearray:
    offset = 0x10
    length = len(data) - offset - 4
    checksum = calc_checksum(data, offset, length)
    data[offset + length : offset + length + 4] = checksum.to_bytes(4, "little")
    return data


def get_section_offsets(data: bytes | bytearray) -> list[int]:
    ofs = 0x14
    sect_data = [-1, -1, -1]
    entry_lens = [1, 4, 4, 1, 1, 1, 1, 4, 4, 1]
    section_offsets = [0] * 10
    for i, entry_len in enumerate(entry_lens):
        for j in range(3):
            sect_data[j] = int.from_bytes(data[ofs : ofs + 2], "little")
            ofs += 4
        if section_offsets[i] == 0:
            section_offsets[i] = ofs
        for _ in range(sect_data[2]):
            ofs += entry_len
    return section_offsets


def alter_byte(data: bytearray, offset: int, value: int) -> None:
    data[offset] = value & 0xFF


def alter_int(data: bytearray, offset: int, new_val: int, num_bytes: int = 4) -> None:
    data[offset : offset + num_bytes] = new_val.to_bytes(num_bytes, "little", signed=True)


def update_checklist_unlocks(data: bytearray, char_index: int, marks: list[int]) -> None:
    if char_index == 14:
        clu_ofs = get_section_offsets(data)[1] + 0x32C
        for i, mark in enumerate(marks):
            current_ofs = clu_ofs + i * 4
            alter_int(data, current_ofs, mark)
            if i == 8:
                clu_ofs += 0x4
            if i == 9:
                clu_ofs += 0x37C
            if i == 10:
                clu_ofs += 0x84
    elif char_index > 14:
        clu_ofs = get_section_offsets(data)[1] + 0x31C
        for i, mark in enumerate(marks):
            current_ofs = clu_ofs + char_index * 4 + i * 19 * 4
            alter_int(data, current_ofs, mark)
            if i == 8:
                clu_ofs += 0x4C
            if i == 9:
                clu_ofs += 0x3C
            if i == 10:
                clu_ofs += 0x3C
    else:
        clu_ofs = get_section_offsets(data)[1] + 0x6C
        for i, mark in enumerate(marks):
            current_ofs = clu_ofs + char_index * 4 + i * 14 * 4
            alter_int(data, current_ofs, mark)
            if i == 5:
                clu_ofs += 0x14
            if i == 8:
                clu_ofs += 0x3C
            if i == 9:
                clu_ofs += 0x3B0
            if i == 10:
                clu_ofs += 0x50


def build_repentance_100(source: bytes) -> bytearray:
    data = bytearray(source)
    sections = get_section_offsets(data)

    for i in range(1, 638):
        alter_byte(data, sections[0] + i, 1)

    for i in range(1, 733):
        if i in SKIP_ITEMS:
            continue
        alter_byte(data, sections[3] + i, 1)

    for i in range(1, 46):
        alter_byte(data, sections[6] + i, 1)

    hard_marks = [HARD_MARK] * 12
    for char_index in range(CHARACTERS):
        update_checklist_unlocks(data, char_index, hard_marks)

    stats = sections[1] + 0x4
    alter_int(data, stats + 0x4C, 999)
    alter_int(data, stats + 0x50, 50000)
    alter_int(data, stats + 0x54, 99)
    alter_int(data, stats + 0x58, 99)
    alter_int(data, stats + 0x5C, 99)

    return update_checksum(data)


def summarize(data: bytes | bytearray) -> None:
    sections = get_section_offsets(data)
    secrets = sum(data[sections[0] + i] for i in range(1, 638))
    items = sum(data[sections[3] + i] for i in range(1, 733))
    challenges = sum(data[sections[6] + i] for i in range(1, 46))
    offset = 0x10
    checksum_ok = int.from_bytes(data[-4:], "little") == calc_checksum(
        data, offset, len(data) - offset - 4
    )
    print(f"  header={data[0:16]!r}")
    print(f"  size={len(data)} checksum_ok={checksum_ok}")
    print(f"  secrets={secrets}/637 items={items}/732 challenges={challenges}/45")


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing {SRC}")

    save = build_repentance_100(SRC.read_bytes())
    out = ROOT / "isaac_saves" / "rep_100_ios_import.dat"
    out.write_bytes(save)
    print("Repentance 100% save (ISAACNGSAVE09R):")
    summarize(save)

    if IOS_PERSISTENT.exists():
        backup = IOS_PERSISTENT.with_suffix(".dat.before_import.bak")
        shutil.copy2(IOS_PERSISTENT, backup)
        IOS_PERSISTENT.unlink()
        print(f"\nRemoved {IOS_PERSISTENT.name} (backup: {backup.name})")

    IOS_REP.write_bytes(save)
    print(f"Installed import source -> {IOS_REP}")

    print(
        "\nNext: fully quit Isaac, relaunch, open save slot 1.\n"
        "The game should import rep_persistentgamedata1.dat into a new persistentgamedata1.dat."
    )


if __name__ == "__main__":
    main()
