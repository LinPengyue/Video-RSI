# P7 Round 003 — Human-first Track B process pilot

**Start date:** 2026-11-01
**Branch:** `research/lvbench-comp-p7-hil-pilot`
**Previous audited HEAD:** `2ec1e4d29d858cbb2c94ef7c5260cca5e6e1f227`
**Status:** `PREPARE_ONE_HUMAN_REVIEW` (not a completed human review).
**Dataset partition:** `UNASSIGNED`; `run_004=NOT_STARTED`; Track A frozen; sealed untouched; P0 runs unchanged.

## Purpose

Trial one **human-first**, low-friction iteration of Track B construction, using established human-reviewed cases to teach review judgment and one new continuous-video candidate to test the handoff. The research target remains **training-unseen, directed, nontrivial video composition**, not generic video QA. Do not call a candidate Seen/Unseen until primitive coverage and a predeclared structural split support that assignment.

## Seed review skill (evidence and ownership)

- **Existing Track A positive calibration (do not count as new):** `pilot_v2_2/judgments.json`: `LVCOMP-V2-002` / `003` on `JTa_Ue2MSwc`; same identified person across a temporal link, later action supported. These are **prior supported observations**, not a new family.
- **User-reviewed VTCD:** `round_002/user_reviews/VTCD_USER_REVIEW_2026-11-01.json`. A jacket **REMOVE** at approx source 168–170s; text “Fan Zhendong” A≈184s and B≈269s; cross-clip `SAME_PERSON`. User accepted **C2 and C4 as question candidates** and approved explaining the overlay as “PREVIOUS RESULTS（过往成绩）”. **No necessity certification** or official Seen/Unseen classification.
- **Negative precedent:** TJR 315–335s royal cast is not established as the later stage performers; original purple-near-king relation = `NO_VALID_EARLY_WINDOW_FOUND`. Do not reuse or silently repair the prior false actor bind.
- Recording principle: `USER_CASE_JUDGMENT` is not a global rule. `USER_EXPLICIT_RULE` only when expressly stated. `GPT_SUGGESTION` / inferred rules are not user-approved. GPT uses these saved examples as **in-context skill/reference**, not model-weight training or claimed reviewer replacement.

## One new review item — TJR, not pre-validated

Source `TJR1oYDDTwg`, existing Round 2 locally extracted videos:
- Early candidate: `round_002/tjr_relocate/media/early_candidate_dragon_ride_1100_1125.mp4` (1100–1125s).
- Late reference: `round_002/tjr_relocate/media/late_dual_performers_1200_1220.mp4` (1200–1220s).
- Existing page: `round_002/tjr_relocate/OPTIONAL_REVIEW_START_HERE.html` (reuse its media; do not expose machine hypotheses upfront to bias the user).
- Original early window 315–335s stays rejected.

**Cursor preparation:** Make **one short browser-playable review page** (or adapt/copy the above) with local, gitignored MP4s and a locally forwarded `127.0.0.1` HTTP service usable from the user's remote Cursor SSH environment. Do not open public ports or upload MP4s. Hide hypotheses until after the user watches. Include just three judgment prompts:
1. **Early event**: What is actually visible? Actor/action, approximate clip seconds, or insufficient evidence.
2. **A↔B same-person**: yes / no / insufficient; what direct identity evidence in each interval? Do not infer the answer from appearance labels alone.
3. **Candidate QA** (show after the first two answers): Does the question “后来在舞台上打鼓的孩子，在更早片段中做了什么？” fairly refer to a supported actor/action? User accept / revise / reject, or `NOT_APPLICABLE` if binding fails. Expected answer stays `ANSWER_PENDING` until user states it. No prefilled gold.

If using the existing HTML page instead of modifying it, show exactly these three prompts in the companion instructions. Do not treat “龙背” or “打鼓” from old machine reconnaissance as an independently verified user fact.

## Lightweight iteration

1. GPT/Cursor prepare review page, no prelabels.
2. User watches both clips and makes the three judgments **once**.
3. GPT extracts (a) exact user case labels, (b) assistant mistakes corrected, (c) inferred rules pending confirmation. Cursor stores with provenance; reuse verified events, do not solicit repeat viewing.
4. Cursor records whether usable **directed dependency** remains. If none, write `NO_USABLE_TJR_FAMILY`; an honest reject is a successful review-process test, not a dataset success.
5. Only after user feedback, discuss whether to keep this **four-part** Track B loop: human demonstration → GPT skill capture → small candidate production/review → necessary Seen/Unseen + compositional checks. Do not independently restart Track A.

## Minimal test of the process

- Media opens and source interval is correct.
- User can make/reject all three decisions without repeated follow-ups.
- Records preserve the exact human judgment and expose unresolved issues.
- No `GOLD_QA_MINTED`, no `COMPOSITION_NECESSITY_VERIFIED`, no formal Seen/Unseen assignment or expensive RSI.
- Report the real number of independent usable candidate families, not QA paraphrase count. If unknown, leave unknown.

**Stop line:** After the **review page is ready**, stop for the user. The next step is **user viewing and judging**, not autonomous annotation or new video scaling.
