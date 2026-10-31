# CVPR2027 — independent audit of Cursor run_003 (`bcd1a0f`) and bounded next phase

Date: 2026-10-31. Source SHA: `bcd1a0fd5f12fea2c4695e9ac21de193911e4b79`.
Basis: GitHub `run_003` report, metrics, full relation/QA/screening JSONL and `chatgpt_ingest.py`, `relations.py`, `qa_draft.py`, test source. Cursor reported 22/22 passing; ChatGPT has **not** rerun tests in local source-video environment. Prior 12 directly inspected still observations were committed in `aef575c`.

## Judgment

**ACCEPT as a successful reproducible ChatGPT-still → typed Event Graph → relation/control QA factory intake. REJECT as evidence of validated compositional benchmark yield or autonomous long-video semantics.**

Observed/claimed numbers in the committed run_003 metrics:
- 3 registered DEV videos; 12/12 ChatGPT static observations accepted; 0 continuous-video semantic events, 0 automatic model events.
- 10 generated relation hypotheses: 9 `still_ordered_setting_contrast` (three adjacent sampled-frame pairs per four-frame video), 1 `still_commerce_price_display_pair` (on `Mcggugol2ts`, vending-machine price display around 1067s and collectible-card price labels around 2134s).
- 10 QA drafts, **two literal question stems**, two generated program-signature strings. All drafts = `ANSWER_PENDING` and `SHORTCUT_CONTROL`/`development_control`; every auto-screen record says `evidence_tested=false`, `masked_qa_executed=false`, `RULE_PROXY_NOT_VIDEO_TESTED`. The provisional answers are truncated source-scene descriptions or a tentative comparison, not independently verified gold.
- `n_independent_evidence_families=10` is computed by distinct event-ID combinations (with shared frames across adjacent pairs), NOT independent compositional reasoning skills or ten statistically independent QA families. `candidate_yield_per_video=3.333` is a control candidate rate ONLY; verified QA and novel directed composition yield are both zero.
- 10 blind packet JSONs are serialized but zero reviewer assets verified, zero continuous media, zero formal blind ready and zero true masked A-only/B-only evaluations. Do not ask user for a formal batch yet.
- Reported `elapsed_s=0.1` and decode-only cost 0 omit prior frame extraction, ChatGPT still interpretation and QA validation. Do not call these end-to-end annotation throughput/cost.

## Scientific interpretation

The producer interface now works, but sampling four isolated frames across ~30–45 minute videos yields appearance snapshots and filename order, not actual video-event transitions. Relative timestamp order should not be mistaken for learned temporal relations. The extra commerce/price pair is a valid still-domain comparison hypothesis, not a causal event or new directed composition. The two program signatures are handwritten rule templates, not structure discovery evidence.

Remain conservative on cross-shot identity, narration, speech, actions and causality. Keep both the 9 generic contrasts and 1 commerce candidate as DEV CONTROL historical artifacts; **do not reword the same ten drafts to inflate production**.

## Minimal quality guard (not another engineering rewrite)

The validator currently treats source SHA checks as optional when `source_frame_sha256` is absent, and if a manifest is supplied but an evidence path is not in that manifest, the file can still be accepted if it exists locally. Current twelve events ARE manifest-matched and SHA-declared as recorded, so this is a **future-input trust-boundary test gap**, not an accusation of run_003 corruption. Add a small regression test requiring manifest membership and source SHA when `manifest_path` is explicitly passed in trusted-production mode; keep compatibility when no manifest is provided.

## NEXT — evidence-centric semantic production feasibility, not factory-only churn

Track B (~80%), no rearchitecture or RSI-method work:

1. Choose at most **two previously registered, nonsealed DEV videos** for bounded event-centric evidence pilots. Start with `Mcggugol2ts` (vending/display visually observed) and, if useful, `xi6r3hZe5Tg` (visually mixed real footage, food, diagram, classroom) rather than automatically comparing every coarse-sample pair. Historical `JPPMz8fEml0` can remain a control.
2. For at most **two anchored ROIs per video**, extract a short **timestamped multi-frame sequence/contact sheet** with a predefined fixed evidence budget (e.g., 8–12 seconds per ROI, ~1–2 fps, at most 12–16 frames per ROI) and an optional bounded locally playable clip. Include beginning/middle/end frame times, original video ID, frame checksum and selection rationale. This is a **new local evidence-acquisition probe**, not a new video or proof of continuous observation. Do not sample full 45-minute footage densely or launch endless per-question evidence chasing.
3. Upload small still sequences and metadata through GitHub for ChatGPT to perform a fresh **candidate event/state-transition semantic pass** in the next interactive turn. New labels must distinguish `STATIC_VISIBLE`, `ORDERED_MULTIFRAME_SUGGESTS`, `CONTINUOUS_VIDEO_VERIFIED`, `UNRESOLVED`, and trace actual observation modality and version. ChatGPT does not have the local MP4s: cannot certify continuous motion/audio from contact sheets. Independent A/B blind review must be performed by a separate observer or a separate uncontaminated review pathway, not by this event-generating ChatGPT pass.
4. Before drafting QA, test **relation feasibility**: actual actor/property identity joins, state changes or conditional/temporal dependencies, with a two-witness necessity hypothesis and possible B-only/metadata shortcuts. If none, keep zero and report failure; do not synthesize generic ordered-still comparisons again. New provisional candidates require explicit nontrivial dependency structure, not merely differing backgrounds or file-clock order.
5. Do not start a `run_004` for quantity alone. If the pilot finds at least one evidence-grounded, nontrivial relation hypothesis, consume it through the existing factory under a new unique run ID and log counts by event modality, original video, structural signature, independent verification and annotation time. If not, `BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE` and identify whether the bottleneck is sampling, motion/video access, model capability or reviewer availability. If needed, a larger metadata-only DEV selection step is permitted under sealed exclusion policy, but do not open or sample sealed.
6. Track A (~20%) keep six-task corrected negative baseline frozen (choice 0.833/exec 0.333); no selector tuning, no expensive Evolver/RSI.

## Cursor deliverable

- `track_b/batch_factory/RUN003_AUDIT_AND_EVENT_ROI_PILOT_REPORT.md` with actual processed video/ROI counts, sequence file/sha paths, semantic evidence hypotheses, shortcut tests possible/unavailable, cost and blockers.
- Small bounded GitHub ChatGPT ROI evidence batch (manifest + directly viewable contact frames/sheets); report `PENDING_CHATGPT_MULTIFRAME_SEMANTIC_REVIEW` until the interactive ChatGPT review actually happens. **Do not fabricate its results**.
- Minimal optional intake validator boundary tests; original `run_003` and Track A historical artifacts remain unchanged.
- Commit/push; share SHA. No full user blind packet until verified assets and independent reviewers are ready.

Global constraints: LVBench source, DEV_CONSTRUCTION only for exposed inspection, `UNASSIGNED`, no automatic `SUPPORTED`, sealed untouched, `ok_for_expensive_rsi=false`, no expensive RSI; Seen may be multistep and Unseen holds out the complete target directed composition. The research priority is feasible *video-grounded compositional structure* discovery, not raw QA volume.
