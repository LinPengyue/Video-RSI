# Labels policy for MLVU-Test

## Official vs local status (updated 2026-10-23)

- **Official:** MLVU announced that Test Ground Truth is public (researcher note: 2025-03-18). Canonical file:  
  `https://huggingface.co/datasets/MLVU/MLVU_Test/blob/main/test-ground-truth/test_mcq_gt.json`
- **Local (this server, 2026-10-23):** `test-ground-truth/test_mcq_gt.json` is present (researcher upload). Validated 502/502 → gitignored `labels.local.jsonl`. Integer `count` answers are **1-based** (1..6). Do not commit GT or labels.

Earlier prep text that said “Test GT remains undisclosed” referred to the **bundled README wording** and empty local folder. That must be read as **local absence**, not as “still secret upstream.”

## Rules

1. Never write answers into `mlvu_test_mc_items.jsonl` (Solver/Editor input).
2. `run_batch.py` receives only the public items JSONL.
3. After authorized download, place `test_mcq_gt.json` under the local dataset tree (outside git), then run:

```bash
python research_audit/mlvu_test_prep/validate_and_build_labels.py
```

This writes **gitignored** `labels.local.jsonl` for `score.py --labels`.

4. Do not commit `test_mcq_gt.json`, `labels.local.jsonl`, videos, or HF tokens.
5. Do not place labels in harness memory, prompts, or batch item fields.
6. Missing question_ids or unmappable answers → **fail closed** (script exits non-zero; no guessed labels).
