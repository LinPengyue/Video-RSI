# Root Cause Analysis — Ordered by Evidence Strength

## Top-level verdict

**PARTIALLY VALID overall pilot; Phase D architecture ranking = INVALID EXPERIMENT.**

- Phase B mechanism stability and Placebo/Oracle analyses remain usable.  
- Phase C “probe calls = 0” and “no info-flow code change” remain factual.  
- Phase D Initial/Baseline/Treatment vs Direct VQA **accuracy ranking is not a valid scientific comparison**.

---

## Findings table

| # | Finding | Category | Evidence | Epistemic | Impact |
|---|---|---|---|---|---|
| 1 | Phase D harnesses: all `sample_frames` fail (`imageio_ffmpeg` missing) | **EXPERIMENT BUG** | `service_trace` errors ×108/104/74; `audit_phase_d_offline.py`; `services.py` L237–238; eval runs in-process without videorsi env | **OBSERVED** | Nullifies Phase D harness↔Direct VQA architecture conclusions |
| 2 | `qwen_frames=0` matches failed extraction (not meter bug) | **EXPERIMENT BUG** (symptom) | 0 `qwen` in service_trace; meter only DeepSeek providers; diagnostics `tool_execution_errors`>0 | **OBSERVED** | Case A (attempted vision, never reached Qwen) |
| 3 | Fail-open: status `answered` after total vision failure | **EVALUATION LIMITATION** / protocol | 24/24 answered per arm | **OBSERVED** | Inflates “usable accuracy” under broken sensors |
| 4 | Direct VQA works via `ffmpeg_bin` fallback | **EVALUATION LIMITATION** (asymmetry) | 24/24 Direct calls ok, 32 frames; `infoflow_lib.py` fallback path | **OBSERVED** | Unfair advantage vs harnesses in same process |
| 5 | Treatment `infoflow_probe` never invoked | **TOOL DISCOVERY FAILURE** (+ env confound) | investigation ops inventory; plan/summary lack probe | **OBSERVED** | Cannot claim probe-driven evolution occurred |
| 6 | Probe subclass mock-works; stock rejects op | Integration OK | `test_infoflow_probe_mock.py` | **OBSERVED** | Separates “unwired” from “unused” |
| 7 | Editor observe/ocr also hit `imageio_ffmpeg` | **EXPERIMENT BUG** / env | treatment `request_0001/0002` ModuleNotFoundError | **OBSERVED** | Contaminates Phase C diagnosis quality |
| 8 | Editors chose prompt/tool-dedup/skill edits | **DIAGNOSIS FAILURE** (under confound) / not proven capability limit | edit_plan + diffs | **OBSERVED** edits; **HYPOTHESIS** on capability | No info-flow architecture change — factual; cause mixed |
| 9 | Treatment +1/24 vs Baseline | **EVALUATION LIMITATION** | Phase D scores under #1 | **OBSERVED** numeric; **INVALID** as method gain | Do not interpret as probe benefit |
| 10 | Same-ID historical mean ~52 Qwen frames | Contrasts #1 | training_cache on eval IDs | **OBSERVED** | Rules out “these 24 never need vision” |
| 11 | Eval set 24 IDs / 18 videos | **EVALUATION LIMITATION** | `independent_eval_ids.safe.json` | **OBSERVED** | Dependence; secondary |
| 12 | Phase E `INSUFFICIENT` as valid-negative method failure | Over-claim | Phase E text vs #1–#4 | **OBSERVED** mismatch | Must revise interpretation → **PARTIALLY VALID / invalid Phase D** |

---

## What is *not* supported

- Meter object split between Services and Provider as root cause (**COUNTEREVIDENCE**: binding correct; no Qwen events).  
- “Agents skipped vision intentionally on easy text items” (**COUNTEREVIDENCE**: many failed visual attempts; historical frames high).  
- “Probe JSON could not be dispatched” as reason for zero calls (**COUNTEREVIDENCE**: mock + never requested).  
- Collapsing A–E Editor failure modes into a single “no mechanism-level RSI ability” slogan (**FORBIDDEN by brief**; evidence insufficient once env broken).

---

## Engineering vs scientific

| Layer | Status |
|---|---|
| Engineering | **Broken eval/editor Python env for ffmpeg** is decisive for Phase D and contaminates Phase C investigation |
| Scientific (mechanism hypotheses from Phase B) | Still **hypothesis-grade evidence** for vision-loss / answerer split on other IDs |
| Scientific (Editor+optional probe → architecture self-evolution) | **Not decided** — prior “INSUFFICIENT” over-interpreted invalid Phase D |
