# Phase D Validity Audit (Offline, 0 API)

**Pilot commit under audit:** `ff1d383` (`research/arch-self-evolution-pilot`)  
**Local run dirs (gitignored, present):** `runs/phase_d_eval_v1/`, `runs/editor_arms_v1/`  
**Reproduce:** `PYTHONPATH=. python3 research_audit/arch_self_evolution_failure_audit/audit_phase_d_offline.py`

---

## Executive finding

**Harness Qwen frames = 0 is not a metering mirage and not “agents chose to skip vision.”**  
It is **CASE A + tool failure**: agents *attempted* visual tools; every `sample_frames` call failed with `ModuleNotFoundError: No module named 'imageio_ffmpeg'` under the **system** Python that invoked `eval_independent.py`. No frames were extracted → no Qwen vision calls → answers still marked `answered` after DeepSeek-only recovery.

**Direct VQA used a different ffmpeg resolution path** (`infoflow_lib.ffmpeg_bin` fallback to the videorsi-packaged binary) and therefore **did** observe 32 frames. Phase D therefore compared **vision-broken harnesses** vs **vision-working Direct VQA**.

**Judgment for Phase D architecture comparisons: INVALID EXPERIMENT (for info-flow / Editor gains).**  
Reported numbers remain factual logs of what ran; they **must not** be used as evidence that Treatment/Baseline/Initial architectural quality ranks as 10/9/8 vs Direct 14.

---

## A1. Per-arm trajectory summary (OBSERVED)

| Arm | n | status | visual tool calls | successful real vision | `sample_frames` errors | `qwen` in service_trace | qwen_frames=0 | mean deepseek_calls |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| Initial | 24 | all `answered` | 108 | **0** | **108** | **0** | 24/24 | 7.63 |
| Baseline | 24 | all `answered` | 104 | **0** | **104** | **0** | 24/24 | 7.33 |
| Treatment | 24 | all `answered` | 105 | **0** (31 are `already_observed` stubs only) | **74** | **0** | 24/24 | 7.29 |

Error string (all `sample_frames` failures):

`ModuleNotFoundError: No module named 'imageio_ffmpeg'`  
(Count: 108 / 104 / 74 on the three arms.)

Example (`initial`, `lvbench_13`, `service_trace`):

- DeepSeek requests `inspect_interval` / `overview` / …
- Next event: `service=sample_frames` with `error: ModuleNotFoundError: No module named 'imageio_ffmpeg'`
- Memory observation: `{"error": "RuntimeError", "message": "ModuleNotFoundError: No module named 'imageio_ffmpeg'"}`
- Diagnostics: `tool_execution_errors` ≈ 4–5 per item; status still `answered`

**Not CASE B:** Meter is consistent with reality — no successful Qwen provider events with frames.  
**Not “zero-step answer”:** mean ~6 decision steps; visual tools were requested repeatedly.  
**Treatment stubs:** `already_observed` returns from Treatment `tools.py` after a failed first attempt — **not** successful Qwen perception.

Historical contrast (**OBSERVED**): same 24 IDs in `training_cache/initial_harness` had mean **`qwen_frames ≈ 51.8`** when evolution used videorsi Python — so the slice is not inherently “text-only.”

---

## A2. Metering / execution path (OBSERVED)

Call chain in `eval_independent.py`:

1. `run_arm_harness` → in-process `PinnedProvider` + `Services` + `run_item` (L~137–180, L65).  
2. Does **not** spawn `config["execution"]["python"]` (`…/envs/videorsi/bin/python`).  
3. `Services.sample()` (`services.py` L237–238) does `from imageio_ffmpeg import get_ffmpeg_exe` when `ffmpeg == "imageio-ffmpeg"`.  
4. Invoking interpreter for Phase D was system `/home/descfly/miniconda3/bin/python3` (**no** `imageio_ffmpeg`).  
5. `Services.__init__` correctly sets `self.provider.meter = self.meter` — **not** the root cause.  
6. Direct VQA path uses `infoflow_lib.extract_frames` → `ffmpeg_bin()` with **hardcoded fallback** to videorsi’s ffmpeg binary (`infoflow_lib.py` ~L191–212) — works without the Python package.

**Candidate versions:** Initial / Baseline / Treatment directories under `runs/editor_arms_v1/*/workspace/candidate` and seed `versions/initial_harness` were the intended trees (file diffs match Phase C). The bug is **environment**, not wrong candidate checkout.

**Resume/cache:** harness `results.json` written after each arm; first 4 IDs from connectivity share the same failure mode — not “stale healthy cache.”

---

## A3. Sample selection (OBSERVED / limited)

| Check | Result |
|---|---|
| n IDs / unique videos | 24 / **18** (6 videos with 2 questions) |
| Durations | ~30–140 min (long-form LVBench; mean ~4429 s) |
| Gate / exploratory-20 / editor-subset leak | none (by construction) |
| “Answerable without video”? | **UNKNOWN** without content audit of options; many questions are classic VQA (room at timestamp, counts, identity). Cannot claim the set is non-visual. |
| Why ≠ ~55 frame historical mean? | **Environment bug**, not selection (historical cache on same IDs ≈ 52 frames). |

Video reuse within the 24 is an **EVALUATION LIMITATION** (dependence) but **not** the cause of zero frames.

---

## What Phase E claims must be withdrawn or downgraded

| Phase E claim | After audit |
|---|---|
| Treatment 10 vs Baseline 9 vs Initial 8 ranks Editor/architecture quality | **WITHDRAW as architecture evidence** — all three vision-broken |
| Direct VQA 14 proves fixed architecture superiority over evolved harnesses on this eval | **WITHDRAW as fair A/B** — asymmetric vision access |
| Treatment +1/24 shows weak but real method gain | **Downgrade to UNKNOWN / noise under broken vision** |
| `INSUFFICIENT` as “method failed under valid protocol” | **Must reclassify:** protocol for harness eval was **invalid**; scientific method failure **not established** by Phase D |
| Phase B stability / placebo / Oracle Router | **Unaffected** (different runners; ffmpeg fallback / videorsi paths) |

**Still valid observations (narrow):**

- Under ffmpeg-broken env, Editors still emit `answered` letters (fail-open).  
- Direct VQA runner’s ffmpeg fallback worked.  
- Treatment never called `infoflow_probe` during Editor session (see companion probe audit) — that finding is **independent** of Phase D scoring.

---

## Overall Phase D label

**INVALID EXPERIMENT** for comparing Initial / Baseline / Treatment / Direct VQA as video-agent architectures.

Do **not** delete historical `phase_d_eval.safe.json`; treat it as a corrupted-condition log and require a fixed-env re-eval before any architecture ranking (design only in `NEXT_EXPERIMENT_DECISION.md` — not executed here).
