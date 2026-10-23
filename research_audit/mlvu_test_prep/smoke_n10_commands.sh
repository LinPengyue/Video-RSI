#!/usr/bin/env bash
# Paired MLVU Smoke n=10 — DO NOT RUN until researcher approval.
# No secrets; uses API_BASE / API_KEY from the environment.
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH=.
CFG=evolution/run-seed42/effective_config.json
ITEMS=research_audit/mlvu_test_prep/smoke_n10_items.jsonl
LABELS=research_audit/mlvu_test_prep/labels.local.jsonl

echo "REFUSING to auto-run paid inference. Inspect commands below, then execute manually after approval."
cat <<EOF
python3 run_batch_checkpoint.py \\
  --config "$CFG" --candidate evolution/run-seed42/versions/initial_harness \\
  --items "$ITEMS" --output-dir outputs/mlvu_smoke_n10_initial \\
  --allow-provider-calls --no-cache-rates \\
  --max-estimated-cny 12 --reserve-cny 1.0 --reserve-calls 20

python3 run_batch_checkpoint.py \\
  --config "$CFG" --candidate evolution/run-seed42/versions/H_S1 \\
  --items "$ITEMS" --output-dir outputs/mlvu_smoke_n10_hs1 \\
  --allow-provider-calls --no-cache-rates \\
  --max-estimated-cny 12 --reserve-cny 1.0 --reserve-calls 20

python3 score.py --items "$ITEMS" --predictions outputs/mlvu_smoke_n10_initial/results.json \\
  --labels "$LABELS" --output outputs/mlvu_smoke_n10_initial/score.json
python3 score.py --items "$ITEMS" --predictions outputs/mlvu_smoke_n10_hs1/results.json \\
  --labels "$LABELS" --output outputs/mlvu_smoke_n10_hs1/score.json
EOF
exit 2
