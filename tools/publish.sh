#!/bin/bash
# Regenerate the scoreboard data and publish it, but only when the numbers
# actually changed — the 'generated' timestamp alone is not a change.
set -uo pipefail
SITE="$HOME/dragonfyre-site"
cd "$SITE" || exit 1
LOG="$SITE/tools/publish.log"
ts(){ date "+%Y-%m-%d %H:%M:%S"; }

"$SITE/tools/.venv/bin/python" "$SITE/tools/build_data.py" >>"$LOG" 2>&1 || {
  echo "$(ts) build failed" >>"$LOG"; exit 1; }

# Compare against the committed copy, ignoring the timestamp field.
CHANGED=$(python3 - <<'PY'
import json, subprocess, sys
def strip(d):
    d = dict(d); d.pop("generated", None); return json.dumps(d, sort_keys=True)
try:
    new = strip(json.load(open("data/stats.json")))
except Exception:
    print("yes"); sys.exit()
try:
    old_raw = subprocess.run(["git","show","HEAD:data/stats.json"],
                             capture_output=True, text=True, check=True).stdout
    old = strip(json.loads(old_raw))
except Exception:
    print("yes"); sys.exit()
print("yes" if new != old else "no")
PY
)

if [ "$CHANGED" != "yes" ]; then
  git checkout -- data/stats.json 2>/dev/null
  echo "$(ts) no gameplay change — skipped" >>"$LOG"
  exit 0
fi

git add data/stats.json
git -c commit.gpgsign=false commit -q -m "Update scoreboard ($(date '+%Y-%m-%d %H:%M'))" >>"$LOG" 2>&1

if git remote get-url origin >/dev/null 2>&1; then
  if git push -q origin HEAD >>"$LOG" 2>&1; then echo "$(ts) pushed" >>"$LOG"
  else echo "$(ts) committed, push failed (auth or network)" >>"$LOG"; fi
else
  echo "$(ts) committed locally; no 'origin' remote yet" >>"$LOG"
fi
