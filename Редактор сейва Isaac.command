#!/bin/zsh
cd "$(dirname "$0")" || exit 1
export TK_SILENCE_DEPRECATION=1
exec python3 isaac_editor.py
