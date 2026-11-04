# WP1.1 Change List

Engineering-only patch on top of `adac071`. No scientific re-adjudication. No Track A launch.

1. **Schema validation** — Strict Draft-2020-12 subset validator (`eng/strict_schema.py`) always runs; optional `jsonschema` library if installed. Overall `PASS` requires schema validation PASS (SKIPPED no longer allowed).
2. **Uniqueness + joins** — item_id / qa_uid / video_id / node_id uniqueness; QA↔video and edge↔node joins; SP201/SP202 necessity non-null; P7 human-judgment authority; P7 window eval blocked.
3. **Necessity** — New `necessity_authoritative` field; provenance retained; `a_only_sufficient_full_question` / `b_only_sufficient_full_question` mapped for SP201/SP202; P7 conflicts resolve to `human_judgments_preserved`. See `NECESSITY_DIFF_REPORT.json`.
4. **Projections** — `projections/inference_safe/` and `projections/scorer_private/` with automatic leak regression tests. Oracle-program scope not decided here.
5. **Windows** — Approved-source search only; C2/TJR remain UNKNOWN with `fixed_ab_window_eval=BLOCKED`; blind-packet clip filenames not promoted.
6. **Language / structure** — Report 5 Seen en / 2 Unseen zh; report C2 `ReadNameAbbreviationGraphic` vs generic Layer2 collapse; annotations unchanged.
7. **Unchanged** — Fixed 5+2 IDs; QA answer texts; program graph semantics; formal_* / train_exposed protection fields.
