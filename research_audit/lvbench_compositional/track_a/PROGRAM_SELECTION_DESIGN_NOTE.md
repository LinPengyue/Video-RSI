# Design note — agent-adaptive operation sequencing (not threshold TECE)

Status: design only · `ok_for_expensive_rsi=false` · no branded method claim

Current `program_selection` / `evolver_policy` share one fixed pipeline: resolve-A → bind → query-B → verify. Evolution only mutates recovery/threshold/budget. That is **binding_policy_evolution_only**.

## Gap vs video composition transfer
Unseen compositional video QA needs different executable graphs (e.g. order-of-events, set-piece vs open-play contrast, missing modality abort). A single bind-query skeleton cannot express those choices.

## Minimal next mechanism (cheap, synthetic first)
- Library of small DAG templates with distinct semantics (not answer strings).
- Selector inputs: question tokens + observation schema fingerprints + link-entropy — **not** gold matches.
- Held-out graphs must differ in operator topology, not only property values.
- Metrics: template selection accuracy, abstention calibration, necessity agreement — separate from frozen 4-task regression.

Do not implement expensive RSI until a cheap selector shows transfer on independent synthetic graphs.
