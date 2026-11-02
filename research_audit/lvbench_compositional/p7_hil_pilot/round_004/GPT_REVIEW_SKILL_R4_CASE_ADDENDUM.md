# GPT Review Skill v1 — Round 4 Case Addendum

**Source:** `user_reviews/ROUND4_USER_REVIEW_2026-11-02_RAW.json`. This is a case addendum to `round_003/GPT_REVIEW_SKILL_v1.md`, not a model weight update or automatic human-review substitute.

## USER_CASE_JUDGMENT — do not generalize silently

- S1: recognized text `SIERRA`; S2: shoe removal; S3: `BRI 0-0 LIV`; S4: **`Fan Z.D.`** (as read).
- F1: user binds blue-clothed, white-scarfed, sword-wearing rescuer across indoor/snow scenes; QA accepted but answer was blank.
- F2: user rejected question's human target in favor of a dog/animal; user's animal identity reasoning is grounded in black-white coloration; actual answer missing.
- F3: user tracks Tyson Gay, deep-red outfit, lane 7, partially visible `217`, and rewrites the question to pick the American athlete; answer missing.
- F4: user accepts reference relation for purple lattice printing vs plated-food scene and suggests nonoverlapping segments; selected `EDIT_JUXTAPOSITION` conflicts with written causal interpretation, so causal link stays pending.

## GPT_SUGGESTION / INFERRED_RULE_PENDING_CONFIRMATION

- Before generating QA, verify **the question's named/referred entity** matches the entity identified by the user; F1 culprit/rescuer confusion is a failure mode.
- When user modifies a question in the page's "answer" field, tag it `PROPOSED_REVISED_QUESTION`, not `GOLD_ANSWER`.
- Keep the exact readable text/number as observed, with any extrapolation clearly marked.
- Separate chronological/edited cut, source/reference interpretation, and physical causality. Trimming a clip does not prove a causal composition.
- Reuse historical evidence without counting it as an additional independent video; primitive type matters for Track A training coverage.

## Provenance and autonomy

No new standing `USER_EXPLICIT_RULE` claimed from these four samples. No new Gold/Seen/Unseen/necessity status. All QA changes remain suggestions until user confirms them. Future GPT judgments are recommendations until independently checked and user authorizes further autonomy.
