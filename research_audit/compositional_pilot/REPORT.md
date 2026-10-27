# LVBench Compositional Smoke Test v0 — Initial vs H_S1

**Tag:** Exploratory / Non-Held-Out / Smoke Test  
**Run dir:** `research_audit/compositional_pilot/runs/v0_initial_vs_hs1/`  
**Arms:** Initial harness vs H_S1 (Round-3 Gate-accepted snapshot)  
**Items:** 4 atomic (UID 63, 71, 120, 121) + 2 compositional (LVCOMP-01, LVCOMP-04)  
**Budget:** hard cap ¥8; actual ≈ **¥5.65** (incl. tiny API ping)

This report does **not** claim Compositional Generalization success or failure for RSI.

---

## 1. Execution Validity

| Check | Result |
|---|---|
| Preflight (`videorsi`, `imageio_ffmpeg`, videos, harness load, API ping) | PASS |
| Runs completed | **12 / 12** |
| Zero Qwen frames / engineering abort | **None** |
| Budget stop | Not triggered |
| Core harness modified | No (adapter + external runner only) |
| GT / time_references injected into prompts | No |

All 12 runs have `status=answered` and `qwen_frames > 0`. Comparison is engineering-valid for this smoke.

Artifacts: `runs/v0_initial_vs_hs1/preflight_report.json`, `paired_summary.json`, `usage_cost_summary.json`, per-arm `items/*.json` (full traces).

---

## 2. Per-Question Results

| Question | Ground Truth | Initial Prediction | Initial Correct | H_S1 Prediction | H_S1 Correct |
|---|---|---|---|---|---|
| UID 63 (incense count) | D | A | ✗ | D | ✓ |
| UID 71 (green-door knocks) | D | A | ✗ | C | ✗ |
| **LVCOMP-01** (count diff) | B | A | ✗ | A | ✗ |
| UID 120 (searches for?) | A | A | ✓ | C | ✗ |
| UID 121 (who has item?) | D | D | ✓ | D | ✓ |
| **LVCOMP-04** (item + holder) | A | B | ✗ | B | ✗ |

### Usage / cost

| Arm | Atomic Acc | Comp Acc | Qwen frames | DeepSeek calls | Qwen calls | Tokens in/out | Est. CNY |
|---|---:|---:|---:|---:|---:|---:|---:|
| Initial | 2/4 | 0/2 | 584 | 59 | 45 | 512068 / 24607 | 2.45 |
| H_S1 | 2/4 | 0/2 | 684 | 65 | 54 | 671168 / 33137 | 3.20 |
| **Total** | — | — | 1268 | 124 | 99 | — | **≈5.65** |

---

## 3. Atomic vs Composition

- **Neither arm solved either compositional item (0/2).**
- Atomic accuracy is tied at **2/4**, but on **different** items:
  - Initial: fails 63 & 71; succeeds 120 & 121.
  - H_S1: succeeds 63 & 121; fails 71 & 120.
- Clearest mechanism clue: **Initial gets both book atomics right (120+121) but still fails LVCOMP-04.**  
  That is an **atomic-correct / composition-wrong** pattern on the same video facts, under independent sessions (no shared memory between atomic and composition runs).

LVCOMP-01 does **not** show atomic-correct→composition-wrong for either arm, because knock/incense atomics were not jointly solved.

---

## 4. Trace Analysis

Official evidence windows (audit-only; **not** given to harnesses):

- LVCOMP-01: incense **10:43–10:50** (~643–650s); knocks **31:05–31:45** (~1865–1905s)
- LVCOMP-04: after 2nd collision **04:42–05:00** (~282–300s); 3rd meeting **05:15–05:31** (~315–331s)

### LVCOMP-01

| | Initial | H_S1 |
|---|---|---|
| Atomic 63 / 71 | ✗ / ✗ | ✓ / ✗ |
| Composition | ✗ (A) | ✗ (A) |
| Knock window (~31m) | Partially inspected (~1885–1916s) | Inspected (~1876–1901s); under-counted knocks |
| Incense window (~10:43) | **Missed** (looked ~50–66s and broad scans) | **Missed** (treated ~3260s snow/sticks as incense) |
| Failure mode | Observation miss + uncertain arithmetic; final reason admits counts unverified, guesses smallest diff “2” → A | Wrong incense localization + incomplete knock count; synthesizes A |

**Conclusion:** failure is primarily **video localization / counting observation**, not a clean “had both counts then arithmetic bug.” H_S1’s visual-cache / transcript changes do not yield a composition win here.

### LVCOMP-04

| | Initial | H_S1 |
|---|---|---|
| Atomic 120 / 121 | ✓ / ✓ | ✗ / ✓ |
| Composition | ✗ (B: book; man himself) | ✗ (B: same) |
| Near-official early window | Scanned ~200–320s / 300–316s; overview even notes woman holding book-like object ~257s | Scanned scattered later intervals; weak binding to 2nd/3rd collision |
| Failure mode | **Cross-event binding / event selection:** identifies “book” but attributes possession to the man in a **later** scene (~1078–1085s) | Similar: book vs phone OK-ish, but holder binding uses wrong later segment (~1501s); also fails atomic 120 |

**Conclusion:** Initial’s LVCOMP-04 error is the strongest smoke signal for **integration failure**: separate atomics solvable, joint question collapses holder association across events. H_S1 does **not** improve; both answer **B**.

H_S1 differences visible in traces (more frames, some tool-arg repair on LVCOMP-01) align with its known cache/prompt/transcript edits, **not** with a compositional gain.

---

## 5. Research Implications

1. **Atomic vs composition dissociation?**  
   **Yes, one clear instance:** Initial 120✓ + 121✓ but LVCOMP-04✗. Worth treating as a mechanism hypothesis, not a proof.

2. **Harness Evolution (H_S1) composition benefit?**  
   **Not observed** on these 2 items (both 0/2). Atomic set also not improved overall (2/4 each).

3. **Can any H_S1 edge be explained by its known edits?**  
   H_S1 alone flips incense atomic (63) to correct—possibly more visual revisits—but still misses the true incense window on LVCOMP-01 and fails both compositions. No trajectory evidence of a new composition operator.

4. **Continue building harder compositional probes?**  
   **Cautiously yes for mechanism debugging** (especially atomic✓/comp✗ templates like LVCOMP-04), **not** for claiming RSI compositional generalization. Next probes should: held-out videos, more items, and success criteria that require verified intermediate slots—not only final MCQ letters.

---

## 6. Limitations

1. **n=2 compositional items** — no statistical power.  
2. **Non-held-out / contaminated:** H_S1 evolved on LVBench train/gate; related videos appeared in Gate (not these exact composition questions).  
3. H_S1 changes are **cache / transcript / prompt**, not a composition algorithm.  
4. Single replicate (temperature 0) — still path-dependent tool routing.  
5. Composition labels derive from official atomics; visual localization difficulty can dominate “composition” failures.  
6. Results are **Exploratory / Non-Held-Out / Smoke Test** only.

**Stop point:** 12 runs + this report. No Editor, no Round 4–20, no benchmark expansion performed.
