# 01 — Official Video-RSI reproduction consistency audit

Audit date: 2026-10-22  
Baseline commit (upstream / fork `main`): `5ad014499a5e009b75e3ef05ac83595b78adda09`  
Research branch HEAD at audit start: `d30fd7b3e030ede119b8701220be6c6015f02237`  
Remote: `origin` = https://github.com/LinPengyue/Video-RSI.git ; `upstream` = https://github.com/bingjunluo/Video-RSI.git  

Scope: static code review, existing logs, and config comparison. **No** evolution loop, Solver/Editor/Gate run, or paid API call.

Worktree note: `prepare_lvbench.py` and `solver_full_workspace/engine/investigation.py` have **uncommitted** local edits. Unless stated otherwise, baseline claims use **git HEAD** / frozen `versions/initial_harness`, not the dirty worktree.

Evidence labels: **VERIFIED** / **LIKELY** / **UNKNOWN**.

---

## Consistency matrix

| # | Item | Official design (code/docs) | Local implementation / run | Match? | Impact if mismatched | Log support |
|---|---|---|---|---|---|---|
| 1 | Initial Harness structure | Nine files in `INITIAL_FILES` (`runner.py` L16–18); tools `overview` / `scan_interval` / `inspect_interval` / `read_text` / `read_transcript` (`tools.py` L29–38); `SKILLS = []` (`skill_policy.py` L14) | `evolution/run-seed42/versions/initial_harness` nine files **byte-identical** to `HEAD:solver_full_workspace/{...}` | **VERIFIED** consistent | Low for framework; harness identity is pinned | Freeze note + byte compare on 2026-10-22 |
| 2 | Seed | Two meanings: (a) `cli --seed` = starting candidate dir (`cli.py`); (b) `prepare_lvbench --seed` = RNG for video-disjoint split | Local dir `run-seed42` + `sampling_summary.json` `"seed": 42` | **VERIFIED** consistent with README defaults | Seed does **not** rewrite initial harness code | `data/lvbench-split/sampling_summary.json` |
| 3 | Editor I/O & edit scope | Phases analysis/plan/edit; candidate writable only in edit (`editor.py` isolation ~L447–449); plan forbids candidate change (`evolve.py` PLAN assert) | Same engine code at HEAD; round_003 has `analysis.md` / `edit_plan.md` / `edit_summary.md` | **VERIFIED** code consistent; **VERIFIED** local round used Editor | If edit scope widened, Gate would evaluate unauthorized edits | Round 3 private_editor meters/protocols present |
| 4 | Solver flow | `main.py:solve` → `Agent.decide` → toolbox + DeepSeek JSON | Identical initial harness | **VERIFIED** | — | Training cache + Gate item dumps exist (large JSON) |
| 5 | Investigation / ReObserve | Engine ops: `observe` / `ocr` / `transcript` / `run_solver` / `finish_analysis` (HEAD `investigation.py`); Editor-requested; no auto ReObserve | Official path used in evolution analysis; EM+IG uses separate `reobserve_probe` (see `02_`) | **VERIFIED** official ≠ EM+IG probe API | Confusing names can misattribute failures | Editor investigation requests under round_003 |
| 6 | Gate | Policy `accuracy_gain_10pct_or_save_20pct_drop1_v1`; accept if accuracy↑ & frames≤110% **or** efficiency (≤1 fewer correct & frames≤80%) (`evolve.py` L47–49) | Round1 REJECTED 41→41; Round2 REJECTED 42→40; Round3 ACCEPTED 43→47 accuracy branch | **VERIFIED** | Wrong policy would invalidate accept | `rounds/round_00{1,2,3}/round_result.json` |
| 7 | Evolution loop | `one_round` TRAIN→ANALYSIS→PLAN→EDIT→CHECK→GATE→COMMIT; `max_rounds` default 20 | Rounds 1–3 completed; `state.next_round=4`; **intentional stop** before 4–20 | **VERIFIED** code; **VERIFIED** partial run by research decision | Incomplete vs paper 20 attempts / 5 accepts | `current.json` = H_S1; `original_evolution_stop.md` |
| 8 | Video-disjoint split | `sample_splits`: gate videos sampled then train = complement (`prepare_lvbench.py` HEAD L97–101) | 216/72 Q, 85/18 videos, seed 42; `validate_datasets` rejects ID/video overlap | **VERIFIED** construction; local split present | Overlap would contaminate Gate | `sampling_summary.json`; `experiment_manifest.json` `video_overlap: []` |
| 9 | Models / budgets / env | README + `config.example.json`: DeepSeek-V4-Pro / Qwen3.6-Plus; solver 11/64/256; editor 160/3600; inv frames 1024; concurrency **16** | `effective_config.json`: `DeepSeek-V4-Pro-0813`, `Qwen3.6-Plus`; budgets match; concurrency **4**; ASR empty locally | **LIKELY** protocol match; **VERIFIED** concurrency differ; **UNKNOWN** paper endpoint/ASR/OCR weights/thinking | Affects absolute Acc/frames vs paper, not Gate predicate identity | `reproduction/runtime_manifest.json`, `REPRODUCTION_CLAIM.md` |
| 10 | What actually ran | Paper: 20 attempts, 5 retained | Local: 3 attempts, 1 accept (`H_S1`); rounds 4–20 not run | **VERIFIED** local ≠ paper trajectory | Cannot claim paper H_S* sequence | `REPRODUCTION_CLAIM.md` section C |

---

## Critical distinctions

1. **Code present ≠ executed.** Investigation APIs exist; EM+IG `reobserve_probe` ranking is a separate offline/pilot stack. Official evolution did run Editor investigation in completed rounds (request JSON under `private_editor/investigations/`).
2. **`H_S1` local ≠ paper `H_S1`.** Local accept: Gate net +4/72, frame ratio ~1.08, attempt 3. Paper dynamics not claimed (`REPRODUCTION_CLAIM.md`).
3. **Baseline for new methods** is `versions/initial_harness` at commit `5ad0144…`, not `H_S1` (`research_baseline/BASELINE_FREEZE.md`).

---

## Reproduction completeness

| Layer | Status | Evidence |
|---|---|---|
| Framework loop (phases + Gate predicate) | **Sufficient for controlled local science** | Rounds 1–3 + `REPRODUCTION_CLAIM.md` A = SUPPORTED |
| Setup (models, concurrency, ASR, OCR hashes) | **Partial** | Public unknowns listed in `REPRODUCTION_CLAIM.md` B |
| Paper evolutionary trajectory | **Not claimed / not available** | Section C NOT CLAIMED |

**Verdict for Task A:** Local code at `5ad0144` matches the published repository harness and Gate/Editor contracts well enough for **relative** experiments under a frozen local split. It is **not** sufficient to claim paper-number reproduction or paper revision identity.
