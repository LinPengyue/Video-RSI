# Fix-path audit — three representative Gate samples (Round 3)

**Branch:** `research/video-rsi-fix-path-audit`  
**Source:** `evolution/run-seed42/rounds/round_003/private_gate/{parent,candidate}/results.json`  
**Parent harness:** `initial_harness` · **Candidate:** `H_S1` (`prompt.md` + `tools.py`)  
**Paid API this audit:** 0  

Epistemic status tags: **OBSERVED** · **SUPPORTED HYPOTHESIS** · **UNKNOWN** · **COUNTEREVIDENCE**

Perception free text and option wording are summarized, not reproduced. Full local dumps (if generated) stay under `local_untracked/` (gitignored).

---

## Case 1 — `lvbench_2480` (key information retrieval)

**Question shape (desensitized):** first speaker’s suit color; 4 color options.  
**Parent:** overview only → wrong letter. **Candidate:** overview + 4× `inspect_interval` → correct letter.

### Timeline (desensitized)

| Arm | Step | Tool | Interval (s) | Frames | Perception digest | Decision use |
|---|---:|---|---|---:|---|---|
| P | 0 | overview | full video | 32 | Mentions first speaker ~275s; jacket described as dark / earth-toned | Answers wrong color; reason cites olive/khaki vs black shirt |
| C | 0 | overview | full video | 32 | Same overview window as parent (shared t-range); similar dark-jacket language | Continues |
| C | 1 | inspect | 270–286 | 8 | Close-ups; jacket called brown/taupe | Continues |
| C | 2 | inspect | 455–465 | 8 | Again brown / chocolate / taupe; not blue | Continues |
| C | 3 | inspect | 1005–1015 | 8 | Again earth tone; contrasts with black shirt | Continues |
| C | 4 | inspect | 2105–2115 | 8 | Again dark jacket again | Answers **correct** letter; reason maps “dark neutral/taupe-brown” onto that letter |

### Findings

1. **OBSERVED:** Parent never inspected local windows; Candidate inspected four short windows around times already flagged in overview (~275, ~458, ~1008, ~2108).  
2. **OBSERVED:** Additional Qwen text repeatedly describes a **brown/taupe/earth** jacket, not an unambiguous canonical color name matching the gold option label.  
3. **OBSERVED:** Final DeepSeek reason on Candidate explicitly maps that earth-tone description onto the gold letter as “closest match.” Parent mapped similar overview language onto a different letter.  
4. **COUNTEREVIDENCE (to “new decisive visual fact of the gold color name”):** Extra inspects do **not** introduce a clear new atomic fact like “jacket is {gold color word}”; they reinforce an ambiguous earth-tone reading.  
5. **SUPPORTED HYPOTHESIS:** Improvement is closer to **control/evidence-use** (more local looks + different option mapping) than to discovering a previously unseen decisive cue.  
6. **UNKNOWN:** Whether the gold option is the best human color label for the jacket; we did not re-verify pixels independently (no frame export in this audit pass).  
7. **UNKNOWN:** Stochastic DeepSeek variance alone could flip the mapping; this single trajectory cannot prove the inspects were causal.

**Bottom line for Case 1:** Do **not** claim “more vision ⇒ found gray/green/…”. Claim: more local observation + remapping of ambiguous color evidence.

---

## Case 2 — `lvbench_4195` (key information retrieval)

**Question shape:** count athletes on a start-list graphic; numeric options.  
**Parent:** `read_transcript` → overview → inspect → OCR → wrong. **Candidate:** overview only → correct.

### Timeline (desensitized)

| Arm | Step | Tool | Interval | Frames | Perception digest | Decision |
|---|---:|---|---|---:|---|---|
| P | 0 | read_transcript | — | — | `unavailable`, empty segments | Waste step |
| P | 1 | overview | full | 32 | Start-list graphic ~108s; **enumerates 8 named rows (1–8)** | Continues |
| P | 2 | inspect | 100–116 | 8 | Re-reads same graphic; some rows noted as obscured | Continues |
| P | 3 | read_text | 100–116 | 0 usable text in log | Empty OCR payload | Answers **wrong**; reason claims “entries 2–9” / nine athletes |
| C | 0 | overview | full | 32 | Same graphic; **lists 8 athletes**; mentions lanes 2–9 on track | Answers **correct**; reason: list has 8, lanes 2–9 ⇒ 8 athletes |

### Findings

1. **OBSERVED:** Parent overview already contained an 8-athlete enumeration before later tools.  
2. **OBSERVED:** Parent final reason **contradicts** that enumeration (inflates to 9 via lane numbering).  
3. **OBSERVED:** OCR step added no usable text in the logged observation.  
4. **SUPPORTED HYPOTHESIS:** Failure mode is **evidence utilization / counting synthesis**, not missing start-list evidence. Extra inspect did not rescue the error and may have fed the lane-vs-count confusion.  
5. **SUPPORTED HYPOTHESIS:** Candidate’s short path is consistent with a better stop, but “early stopping skill” is **not independently proven**—overview content already sufficed.  
6. **OBSERVED:** Empty ASR step consumed one DeepSeek decision without information.  
7. **COUNTEREVIDENCE (to “more visual investigation helps”):** Here more tools after a sufficient overview accompanied a wrong answer.

**Bottom line for Case 2:** Strongest offline example that **more search can harm** when synthesis misreads already-adequate evidence.

---

## Case 3 — `lvbench_5093` (entity recognition / counting)

**Question shape:** how many children appear; numeric options.  
**Parent:** overview → unavailable ASR → many scans (several empty) → wrong.  
**Candidate:** overview → scans (no ASR; several empty) → correct.

### Timeline (desensitized)

| Arm | Notable steps | Digest |
|---|---|---|
| P | overview | Counts children/photos across sparse frames |
| P | read_transcript | Unavailable — **one decision step, zero segments** |
| P | scan 0–1646 | Non-empty child/photo notes |
| P | scan 1646–3292 ×4 | **Empty** perceptions (failed/empty returns) |
| P | scan 1646–2469 | Non-empty |
| P | scan 2469–3292 ×2 | Empty |
| P | answer | Consolidates to wrong count |
| C | overview | Similar child/photo inventory language |
| C | scans (no ASR) | Similar mix of non-empty + many empty identical windows |
| C | answer | Different consolidation → correct count |

### Findings

1. **OBSERVED:** Parent ASR call is a real wasted decision (`unavailable` / empty segments).  
2. **OBSERVED:** Candidate never calls ASR (consistent with H_S1 removing the tool from `descriptions()`).  
3. **OBSERVED:** Both arms still issue **multiple empty** `scan_interval` calls on the same large windows—cache did **not** prevent empty repeats here (empty results may not populate the success cache the same way).  
4. **UNKNOWN / weak link:** Whether the one freed ASR step is what enabled the correct consolidation. Candidate’s successful scans largely overlap parent’s non-empty scans; final reasons differ in **how cases are merged**, not in an obvious single new timestamped child.  
5. **SUPPORTED HYPOTHESIS (weak):** Code change (remove ASR) → tool choice change is clear; **code → decisive new evidence → answer** chain is **not** tightly established for this sample.  
6. **COUNTEREVIDENCE (to simple “ASR removal frees steps for decisive vision”):** Candidate still burns many empty scans; visual budget is not clearly better spent on unique new evidence.

**Bottom line for Case 3:** Tool-surface change is OBSERVED; causal fix via new decisive evidence is **not** cleanly supported.

---

## Cross-case synthesis (Round 3 focus trio)

| Sample | Best-supported mechanism class | Weaker / rejected class |
|---|---|---|
| 2480 | Control + ambiguous evidence remapping | “Found new gold color word in pixels” |
| 4195 | Evidence use / stop; avoid contradictory synthesis | “Needed more vision” |
| 5093 | Tool menu change (no ASR) | Tight causal vision evidence chain |

**OBSERVED across R3’s 10 fixes (from `audit_summary.safe.json`):** 7/10 parent used transcript & candidate did not; 7/10 candidate had more visual tool calls; 0 logged `reused=true` hits on these fix trajectories in the summary patterns.

**UNKNOWN:** Gate ACCEPTED (+4 net on 72) ≠ statistically validated generalization; parent `initial_harness` alone flips ~19–20/72 answers across the three Gate re-evals (see companion report).
