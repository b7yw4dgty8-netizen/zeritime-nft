#!/usr/bin/env python3
"""Install 100% Rebirth save and reset local iCloud sync cache."""

from __future__ import annotations

import plistlib
import shutil
import subprocess
from pathlib import Path

from isaac_build_rebirth import (
    IOS_DOCS,
    IOS_SAVE,
    OUT_DIR,
    build_full_save,
    quarantine_zamiell_copies,
    quit_isaac,
    summarize,
    unlock_save,
)
from isaac_build_rebirth import SRC

PREFS = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Library/Preferences/com.Nicalis.Isaac-iOS.plist"
)
KVS_DIR = Path(
    "/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Library/SyncedPreferences/com.apple.kvs"
)


def clear_local_icloud_cache() -> None:
    if KVS_DIR.exists():
        shutil.rmtree(KVS_DIR)
        print(f"Removed local KVS cache: {KVS_DIR}")

    if not PREFS.exists():
        return

    pl = plistlib.loads(PREFS.read_bytes())
    changed = False
    for key in (
        "KAGE_saveDataLastModifiedDate",
        "KAGE_icloudsync_pending_files",
        "CloudKitAccountInfoCache",
    ):
        if key in pl:
            del pl[key]
            changed = True
            print(f"Cleared preference key: {key}")

    if changed:
        PREFS.write_bytes(plistlib.dumps(pl))


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing template: {SRC}")

    full = build_full_save(SRC.read_bytes())
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "rebirth_100_full.dat"
    out.write_bytes(full)
    print("Built save:")
    summarize(full)

    quit_isaac()
    unlock_save(IOS_SAVE)
    clear_local_icloud_cache()

    if IOS_SAVE.exists():
        backup = IOS_DOCS / "persistentgamedata1.dat.before_100_install.bak"
        shutil.copy2(IOS_SAVE, backup)
        print(f"Backed up current slot 1 -> {backup.name}")

    quarantine_zamiell_copies(IOS_DOCS, IOS_SAVE)
    IOS_SAVE.write_bytes(full)
    IOS_SAVE.chmod(0o644)

    print(f"\nInstalled 100% save -> {IOS_SAVE}")
    print("\n=== ВАЖНО перед запуском игры ===")
    print("1. Системные настройки → Apple ID → iCloud")
    print("   Найди «The Binding of Isaac: Rebirth» и ВЫКЛЮЧИ синхронизацию")
    print("   (или удали «Документы и данные» для этой игры).")
    print("2. Полностью закрой Isaac.")
    print("3. Запусти слот 1 и проверь STATS (341 ITEMS) и CHALLENGES (20/20).")
    print("\nБез отключения iCloud игра снова откатит сейv к 16 предметам.")


if __name__ == "__main__":
    main()
