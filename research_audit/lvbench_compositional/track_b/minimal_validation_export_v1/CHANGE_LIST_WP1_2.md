# WP1.2 Change List (inference-side isolation)

Engineering-only patch on top of `b1e57d6`. No scientific re-adjudication. No Track A launch.

1. **Unseen structure withheld** — `projections/inference_safe/split_manifest.json` keeps Seen structure labels; Unseen Layer1/Layer2/operator sets and n_nodes/n_edges are `WITHHELD_FROM_INFERENCE`. Full split remains in the scientific audit pack at package root.
2. **Necessity private** — `necessity_authoritative` removed from inference QA projection; moved to `projections/scorer_private/eval_private_metadata.json` (+ still on scorer answers).
3. **File access whitelist** — `INFERENCE_ACCESS_WHITELIST.json` + `eng/inference_access.py::resolve_allowed_path` reject parent escapes to answers / Unseen graphs. Not ACCESS.md-only.
4. **Negative leak tests** — Injecting Unseen operators/structure or reference answers into the inference projection must fail validation.
5. **Preserved** — Root scientific audit, schema/join/necessity/window/language/evidence checks; formal_* and train_exposed unchanged.
