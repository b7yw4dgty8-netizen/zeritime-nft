#!/usr/bin/env python3
"""Install Rebirth saves for Mac App Store Isaac (f3 0a + CRC)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents"
)
SAVE = DOCS / "persistentgamedata1.dat"
SAVES = ROOT / "isaac_saves"

VARIANTS = {
    "100": SAVES / "rebirth_100_ios.dat",
    "deadgod": SAVES / "rebirth_deadgod_f30a.dat",
}


def quit_isaac() -> None:
    subprocess.run(
        ["osascript", "-e", 'tell application "The Binding of Isaac: Rebirth" to quit'],
        check=False,
    )
    subprocess.run(["pkill", "-f", "The Binding of Isaac Rebirth"], check=False)


def install(name: str) -> None:
    src = VARIANTS.get(name)
    if not src or not src.exists():
        raise SystemExit(f"Unknown or missing save variant: {name}")

    data = src.read_bytes()
    if data[:2] == b"\xf3\x0a":
        if data[2:18] != b"ISAACNGSAVE06R  ":
            raise SystemExit(f"Wrong iOS header: {data[2:18]!r}")
    elif data[:16] != b"ISAACNGSAVE06R  ":
        raise SystemExit(f"Wrong header: {data[:16]!r}")

    quit_isaac()
    if SAVE.exists():
        shutil.copy2(SAVE, SAVE.with_name(f"{SAVE.name}.before_install.bak"))
    shutil.copy2(src, SAVE)
    print(f"Installed {src.name} -> {SAVE} ({len(data)} bytes)")


def main() -> None:
    install("100")


if __name__ == "__main__":
    main()
