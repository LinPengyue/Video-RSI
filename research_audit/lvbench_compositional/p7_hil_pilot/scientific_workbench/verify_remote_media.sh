#!/usr/bin/env bash
# Engineering playback precheck on the machine that can reach the server.
set -euo pipefail
BASE="${1:-http://127.0.0.1:8770}"
echo "Checking $BASE"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/")
echo "index=$code"
mapfile -t clips < <(python3 - <<PY
import json,urllib.request
cat=json.load(urllib.request.urlopen("$BASE/WORKBENCH_CATALOG.json"))
clips=sorted({c for it in cat['items'] for c in it.get('clips',{}).values() if isinstance(c,str) and c.endswith('.mp4')})
print('\n'.join(clips))
PY
)
ok=0
for c in "${clips[@]}"; do
  hdr=$(curl -s -D - -o /tmp/p7wb_clip.bin -H 'Range: bytes=0-1023' "$BASE/$c" | tr -d '\r')
  status=$(printf '%s\n' "$hdr" | head -1)
  ftyp=$(python3 -c "print(open('/tmp/p7wb_clip.bin','rb').read()[4:8])")
  if printf '%s' "$status" | grep -q '206' && [[ "$ftyp" == "b'ftyp'" || "$ftyp" == "ftyp" ]]; then
    ok=$((ok+1))
  else
    echo "FAIL $c :: $status :: $ftyp"
  fi
done
echo "range_ftyp_ok=$ok/${#clips[@]}"
echo "Open $BASE/ in your LOCAL browser after port-forward; click a video to confirm decode/playback."
