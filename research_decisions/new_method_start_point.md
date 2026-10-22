# New method start point

The next Fine-Grained Credit Assignment stage starts from the official upstream initial harness.

- Baseline: `evolution/run-seed42/versions/initial_harness` at Video-RSI `5ad014499a5e009b75e3ef05ac83595b78adda09`. See `research_baseline/BASELINE_FREEZE.md`.
- Data protocol: the frozen local train set of 216 questions and the video-disjoint Gate set of 72 questions, with hashes in `reproduction/runtime_manifest.json`.
- Runtime comparisons use the local conditions recorded in that manifest.
- The stage does not claim exact reproduction of the paper's evolutionary trajectory.
- `versions/H_S1` is not the default baseline. Its four-way mechanism ablation stays `deferred_optional` until there is a separate question about why that local revision was accepted.

Subsequent experiments measure relative improvement under these controlled conditions. They do not aim to match the paper's stochastic retained revision sequence.
