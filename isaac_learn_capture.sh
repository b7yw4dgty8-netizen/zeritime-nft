#!/bin/bash
# Capture mobile save before/after a game session to map item/challenge bytes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
CAP="$ROOT/isaac_saves/capture"
SAVE="$HOME/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents/persistentgamedata1.dat"

mkdir -p "$CAP"
case "${1:-}" in
  before)
    cp "$SAVE" "$CAP/session.before.dat"
    python3 "$ROOT/isaac_mobile.py" summarize "$CAP/session.before.dat"
    echo "Play Isaac (pick up an item / beat a challenge), quit fully, then:"
    echo "  bash isaac_learn_capture.sh after"
    ;;
  after)
    cp "$SAVE" "$CAP/session.after.dat"
    python3 "$ROOT/isaac_mobile.py" summarize "$CAP/session.after.dat"
    python3 "$ROOT/isaac_mobile.py" diff "$CAP/session.before.dat" "$CAP/session.after.dat"
    ;;
  *)
    echo "Usage: isaac_learn_capture.sh before|after"
    exit 1
    ;;
esac
