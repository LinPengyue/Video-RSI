# Inference-safe projection

Ordinary Track A inference may read **only** paths listed in `INFERENCE_ACCESS_WHITELIST.json`, opened via `eng/inference_access.py`.

Must NOT contain: reference answers, answer-bearing graph outputs, human Gold-like evidence payloads, Unseen original program graphs, Unseen structure/operator/size labels, or human necessity_authoritative.
Do not rely on this markdown alone — enforce the whitelist.
Oracle-program experiment scope is NOT decided by this export.
