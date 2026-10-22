# Research baseline freeze

baseline_name: `Video-RSI upstream initial_harness @ 5ad0144`

Path: `evolution/run-seed42/versions/initial_harness`

Upstream commit: `5ad014499a5e009b75e3ef05ac83595b78adda09`

Tree SHA256: `5fc0db9a33358a1de7bdd3fedccd9a56261c099ae6005c1b38fd2adb6b6fbea9`

The tree hash is SHA256 over the sorted lines `relative-path SHA256(file-bytes)` for the nine files in that directory. This file does not modify `initial_harness`.

The baseline for a new RSI method is this initial harness, not `versions/H_S1`.

Reasons:

- The nine files are byte-identical to upstream `solver_full_workspace` at `5ad014499a5e009b75e3ef05ac83595b78adda09`.
- Provenance is deterministic: it is the published initial harness, not an accepted sample from a stochastic Editor run.
- It does not depend on which revision the local evolution happened to accept.
- Existing natural-failure analyses correspond to this harness.
- New RSI mechanisms can be compared against the same starting agent.
