# Infoflow Probe Audit (Offline, 0 API)

**Treatment arm local path:** `runs/editor_arms_v1/treatment/`  
**Mock smoke:** `PYTHONPATH=. python3 research_audit/arch_self_evolution_failure_audit/test_infoflow_probe_mock.py` (PASS)

---

## B1. Was the tool actually wired? (OBSERVED → mostly YES at code level)

| Check | Evidence | Verdict |
|---|---|---|
| `TreatmentEditor` used | `run_editor_arms.py` L121–153 patches `editor_mod.Investigation = CounterfactualInvestigation` | **OBSERVED** |
| Workspace `INVESTIGATION.md` contains probe docs | File size 6138; contains `infoflow_probe` section from addendum | **OBSERVED** |
| Stock Investigation rejects probe | Mock test `test_stock_investigation_rejects_infoflow_probe` | **OBSERVED** |
| CounterfactualInvestigation accepts 3 modes | Mock test all modes with stubbed `sample_frames`/`qwen` | **OBSERVED** (dispatch/validate) |
| Illegal mode / bad sample_id / missing timestamps | Mock raises `ValueError` | **OBSERVED** |
| Live Treatment investigations | ops: ocr, observe, transcript, run_solver only; **0× infoflow_probe** | **OBSERVED** |
| Would live probe have worked under Treatment Python? | Editor observe/ocr failed with **same** `imageio_ffmpeg` missing (`request_0001/0002`) | **HYPOTHESIS:** probe’s `sample_frames` would also fail unless ffmpeg fixed |

**Conclusion B1:** Tool is **code-integrated and mock-executable**. It was **not proven live-executable** in the Treatment session environment because visual sampling was broken. Classification split:

- Integration of subclass/docs: **OK**  
- Live visual dependency: **TOOL INTEGRATION FAILURE risk** (shared ffmpeg env)  
- Zero calls: **not** explained by “operation unknown” — Editor simply never requested it

---

## B2. Did the Editor know about the probe? (mixed / UNKNOWN)

| Signal | Evidence | Tag |
|---|---|---|
| `infoflow_probe` in `edit_plan.md` / `edit_summary.md` / `feedback_review.md` | **No hits** | **OBSERVED absence** |
| `analysis.md` contains “Qwen 直接” | Refers to overview *text* inferring a title (“Qwen 直接推断…”), **not** Direct-VQA architecture or probe | **OBSERVED** — false friend keyword |
| Protocol mentions `INVESTIGATION.md` | At least one early tool-call blob references the filename | **OBSERVED** weak — does not prove full section read |
| Protocol mentions `infoflow_probe` as an executed request | **None** in investigation records | **OBSERVED** |
| Capability note injected into analysis directive | `TreatmentEditor.run` appends optional-tooling paragraph | **OBSERVED** code path; whether model attended: **UNKNOWN** |
| Editor explicitly diagnosed ffmpeg breakage | `analysis.md` states investigate.py frame sampling failed due to `imageio_ffmpeg` | **OBSERVED** |

**Cannot claim** Editor “knew and rejected” the probe.  
**Can claim** Editor **did not document or execute** it, and focused on trajectory-level M1–M6 mechanisms from **cached wrong trajectories** after visual investigation failed.

---

## B3. Why local edits instead of architecture change?

### What Treatment actually did (OBSERVED)

- Diagnosed identity gating, numeric-vs-subjective conflict, counting sparsity, modality mismatch, redundant calls — from **original** training trajectories.  
- Planned/implemented: `prompt.md` instructions + `tools.py` interval dedup + `skill_policy.py` counting heuristics.  
- **No** solver-loop Direct VQA, answerer router, or caption-vs-vision branch.

### Baseline (for contrast)

- Similar class: constraint extraction in `agent.py`, prompt guards, tool cache — also **not** info-flow architecture.

### Classification (must not collapse)

| Option | Fit |
|---|---|
| A. Did not identify architecture/info-flow issue | **SUPPORTED HYPOTHESIS** for probe-mediated discovery — diagnosis stayed at decision/prompt/tool-dedup |
| B. Identified architecture issue but deemed probe unnecessary | **UNKNOWN** — no written rejection of probe |
| C. Planned architecture test but did not run | **No evidence** of such a plan |
| D. Got mechanism evidence then failed to implement | **No** probe evidence obtained |
| E. Train subset lacked architecture signal | **COUNTEREVIDENCE / weak** — Phase B still found vision-loss on other IDs; but Editor train subset was different 16 wrongs, and **visual re-investigation was impossible** in-session |

Dominant offline reading: **DIAGNOSIS FAILURE under broken investigation env + TOOL DISCOVERY FAILURE (probe unused)**, not a clean proof of “Editor cannot do mechanism-level evolution.”

---

## Probe call = 0 — layered attribution

1. **TOOL DISCOVERY FAILURE (primary for zero calls):** never requested despite docs in workspace.  
2. **EVALUATION / ENV LIMITATION (confounder):** even standard `observe` failed; Editor may have deprioritized further visual tooling.  
3. **Not** “unknown operation” integration miss for CounterfactualInvestigation (mock + code patch).  
4. **Live executability of probe under that env: UNKNOWN→likely FAIL** until ffmpeg/python fixed.
