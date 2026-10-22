# CVPR 2027 git traceability

Recorded: 2026-10-22. This note pins the baseline commit used for later code review. It does not edit the harness, reset experiments, or start a run.

## Remotes

- Research remote (`origin`): `https://github.com/LinPengyue/Video-RSI.git`
- Upstream (`upstream`): `https://github.com/bingjunluo/Video-RSI.git`

Research commits are pushed only to `origin`, on `research/cvpr2027-audit`. They are not pushed to the upstream repository and are not merged into `main`.

## Baseline commit

- Upstream and fork `main` on 2026-10-22: `5ad014499a5e009b75e3ef05ac83595b78adda09`
- Subject: Add files via upload
- Date: 2026-10-14 03:03:16 +0800

`research_baseline/BASELINE_FREEZE.md` already names this SHA as `Video-RSI upstream initial_harness @ 5ad0144`. That file is committed here unchanged.

Byte check on 2026-10-22: the nine files in `evolution/run-seed42/versions/initial_harness` are identical to `solver_full_workspace/{agent.py,answers.py,candidate.json,main.py,memory.py,prompt.md,skill_policy.py,time_utils.py,tools.py}` at this commit. The historical tree hash inside the freeze note was not rewritten.

## Review branch

Audits and later experiments belong on `research/cvpr2027-audit`. Do not merge that branch into `main` as part of routine review. Do not force-push.

Each completed task should commit its code, experiment config, and report on this branch, then push with a normal push. The commit SHA is the version that a conclusion refers to.

## Left out of this commit

Unstaged edits that change tracked baseline files, and therefore stay out of this pin:

- `prepare_lvbench.py`
- `solver_full_workspace/engine/investigation.py`

Existing untracked experiment trees, run dumps, review zip files, and credential files also stay untracked until a specific task commit selects code, configs, and reports. `evolution/`, `outputs/`, `data/`, videos, and model weights remain ignored.

Credential files that must not be committed: `providers.env`, `paratera.env`, `zhipu.env`, `config.local.json`, `config.evolution.local.json`.

## This commit

No experiment was run. No paid API call was made.
