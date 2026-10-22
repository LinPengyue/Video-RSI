# 15 — Long-batch checkpoint reliability (external runner)

**Status:** ready for review · **Harness:** frozen (no Solver / Initial / H_S1 / Gate edits) · **API:** none called

## Verdict

`run_batch.py` cannot resume: `mkdir(..., exist_ok=False)` and always re-runs the full item list. Added external `run_batch_checkpoint.py` with fingerprint-gated resume, runner-level call/CNY breaker, and offline sim tests (10/10 pass). Formal MLVU eval still blocked (videos/GT incomplete).

## Findings on `run_batch.py`

| Concern | Baseline behavior |
|---|---|
| Interrupt recovery | No. Existing `output_dir` raises; no read of `items/%06d.json`. |
| Duplicate paid calls | Any restart = full re-inference. |
| Config mixing | No harness/items/model fingerprint on disk. |

## Minimal resume design (`batch_checkpoint_v1`)

On first create, write under `output_dir/`:

- `batch_manifest.json` — `harness_tree_sha256`, `items_sha256`, `config_fingerprint`, ordered `sample_ids`, budget metadata
- `candidate/` — frozen harness copy (hash source of truth)
- `items/%06d.json` — per-item results (atomic `write_json`)
- `batch_summary.json` / `results.json`

On resume, refuse unless **all** of these match: protocol, harness tree SHA, items SHA, config fingerprint (solver / models / concurrency / gate / investigation), and per-file `sample_id` vs manifest order. Terminal statuses reused without re-invocation: `answered`, `invalid_decision`. Non-terminal / missing slots are re-run.

## Budget / concurrent stop

- CLI: `--max-provider-calls`, `--max-estimated-cny`, `--reserve-calls`, `--reserve-cny`, `--rate-in`, `--rate-out`
- **Reserve-before-submit:** a slot is only scheduled after `try_reserve`; failure trips `stop_reason` and skips further submits.
- **In-flight overshoot:** already-reserved workers may finish; overshoot ≤ `concurrency × reserve_*`, not open-ended.
- Prior terminal usage is credited into the ledger on resume so a resumed run does not “reset” the fuse.

Does not modify Solver / Initial Harness / H_S1 / Gate.

## Frozen stratified IDs (engineering smoke / primary prep)

| Set | Path | Seed | Note |
|---|---|---|---|
| n=10 | `research_audit/mlvu_test_prep/sample_ids_n10.json` | 20261022 | min-1 per task type; `topic_reasoning×2` |
| n=200 | `research_audit/mlvu_test_prep/sample_ids_n200.json` | 20261022 | proportional largest-remainder |

Smoke is for **engineering validation only** — do not retune harnesses from MLVU answers.

## Offline tests

```text
PYTHONPATH=. python3 -m unittest test_run_batch_checkpoint -v
# 10 tests, OK (~0.17s) — no provider API
```

Covered: resume without duplicate invocations; config / items / harness / sample_id mismatch refuse; call & CNY breakers; concurrent overshoot bounded by reserves; `invalid_decision` treated terminal.

## Usage (when videos/GT ready — not now)

```bash
PYTHONPATH=. python3 run_batch_checkpoint.py \
  --config CONFIG.json \
  --items ITEMS.jsonl \
  --output-dir OUT_DIR \
  --allow-provider-calls \
  --max-provider-calls N \
  --max-estimated-cny Y \
  --skip-media-check   # only if media intentionally unchecked
# Re-run same command to resume; omit --no-resume.
```

## Explicitly out of scope this commit

- No paid API calls
- No formal MLVU-Test evaluation
- No harness / Gate / Solver changes
