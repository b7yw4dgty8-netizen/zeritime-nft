#!/bin/bash
# Monitor Isaac save until it changes, then analyze.
SAVE="/Users/exit/Library/Containers/com.Nicalis.Isaac-iOS/Data/Documents/persistentgamedata1.dat"
PROJECT="/Users/exit/Desktop/zeritime my project nft"
LOG="$PROJECT/isaac_saves/capture/monitor.log"
BEFORE_HASH=$(md5 -q "$SAVE" 2>/dev/null || md5sum "$SAVE" | awk '{print $1}')
BEFORE_MTIME=$(stat -f "%m" "$SAVE" 2>/dev/null || stat -c "%Y" "$SAVE")

echo "$(date '+%H:%M:%S') monitoring started md5=$BEFORE_HASH size=$(wc -c < "$SAVE")" >> "$LOG"

for i in $(seq 1 600); do
  sleep 3
  NOW_HASH=$(md5 -q "$SAVE" 2>/dev/null || md5sum "$SAVE" | awk '{print $1}')
  NOW_MTIME=$(stat -f "%m" "$SAVE" 2>/dev/null || stat -c "%Y" "$SAVE")
  NOW_SIZE=$(wc -c < "$SAVE" | tr -d ' ')
  if [ "$NOW_HASH" != "$BEFORE_HASH" ] || [ "$NOW_MTIME" != "$BEFORE_MTIME" ]; then
    echo "$(date '+%H:%M:%S') SAVE CHANGED size=$NOW_SIZE md5=$NOW_HASH" >> "$LOG"
    python3 "$PROJECT/isaac_capture_save.py" after >> "$LOG" 2>&1
    echo "DONE" > "$PROJECT/isaac_saves/capture/monitor.done"
    exit 0
  fi
done

echo "$(date '+%H:%M:%S') timeout no change" >> "$LOG"
echo "TIMEOUT" > "$PROJECT/isaac_saves/capture/monitor.done"
exit 1
