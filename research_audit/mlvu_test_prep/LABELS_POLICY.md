# Labels policy for MLVU-Test

Ground truth for MLVU-Test is **not present** in the uploaded tree (`test-ground-truth/` is empty), matching the official statement that Test GT remains undisclosed.

Rules:
1. Never write answers into `mlvu_test_mc_items.jsonl`.
2. `run_batch.py` must receive only the public items JSONL.
3. `score.py` may read a separate labels JSONL (`sample_id`,`answer`) only at scoring time.
4. Do not place labels under harness memory, prompts, or batch item fields.
5. Until an authorized labels file exists, offline Accuracy is **blocked**; online leaderboard remains an alternative.

This repository commit does **not** include any MLVU-Test answers.
