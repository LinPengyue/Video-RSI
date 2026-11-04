# Stage 4 — Split validity audit

- algo: `stage4_split_validity_audit_v1.0.0`
- built_utc: 2026-11-04T11:26:28+00:00
- baseline_commit: `08b5483f7761ee42a4a0a008988d4d37f484d0a0`
- Stage3 historical preserved under `reports/stage3_historical/`

## Task 1 — Corrected M3 (Layer1 ops reference check)
- layer1/ops/2_node: expected 3/7, got 3/7 → MATCH
- layer1/ops/3_node: expected 1/7, got 1/7 → MATCH
- layer1/ops_role/2_node: expected 3/8, got 3/8 → MATCH
- layer1/ops_role/3_node: expected 0/8, got 0/8 → MATCH

### Unique coverage snapshot
#### layer1
- `ops` 2-node: unique 3/7 (occ 4/9)
- `ops` 3-node: unique 1/7 (occ 1/8)
- `ops_role` 2-node: unique 3/8 (occ 3/9)
- `ops_role` 3-node: unique 0/8 (occ 0/8)
- `ops_role_edge` 2-node: unique 3/8 (occ 3/9)
- `ops_role_edge` 3-node: unique 0/8 (occ 0/8)
- `ops_role_edge_io` 2-node: unique 0/9 (occ 0/9)
- `ops_role_edge_io` 3-node: unique 0/8 (occ 0/8)
#### layer2
- `ops` 2-node: unique 0/8 (occ 0/9)
- `ops` 3-node: unique 0/7 (occ 0/8)
- `ops_role` 2-node: unique 0/9 (occ 0/9)
- `ops_role` 3-node: unique 0/8 (occ 0/8)
- `ops_role_edge` 2-node: unique 0/9 (occ 0/9)
- `ops_role_edge` 3-node: unique 0/8 (occ 0/8)
- `ops_role_edge_io` 2-node: unique 0/9 (occ 0/9)
- `ops_role_edge_io` 3-node: unique 0/8 (occ 0/8)

## Task 2 — Novelty decomposition
### P7_VTCD_C2
- L1 coverage: 1.0
- L2 coverage: 0.2
- L2 unseen-only ops: ['DetectActionEvent', 'QueryBoundAction', 'ReadPersonNameFromGraphic']
- 2-node subgraphs with Unseen-only L2 op: 4/4
- Seen-atom-only structural overlap: N/A
### P7_TJR_R3
- L1 coverage: 1.0
- L2 coverage: 0.2
- L2 unseen-only ops: ['DetectActionEvent', 'DetectTransportEvent', 'IdentifyPersonByAppearance', 'QueryBoundTransport']
- 2-node subgraphs with Unseen-only L2 op: 5/5
- Seen-atom-only structural overlap: N/A

## Task 3 — M4 reinterpretation
M4 inequivalence driven by TRIVIAL_SIZE_MISMATCH must not be cited as primary evidence of unseen compositional structure.

## Task 4 — Scientific validity
### A. Can this split support Layer-1 family-level compositional novelty?
- judgment: **PARTIAL_YES_PILOT_SCALE**
### B. Can this split support Layer-2 atomic-level pure compositional novelty?
- judgment: **NO_NOT_PURE**
### C. Is atomic operator distribution shift mixed into the split?
- judgment: **YES**
### D. Which conclusions apply only to the current 2-Unseen pilot?
- judgment: **MOST_QUANTITATIVE_CLAIMS**
### E. Without re-splitting, what minimal controls/experiments are needed for CVPR claims?
- judgment: **CONTROLS_REQUIRED**

## Remaining limits
- Only 2 formal Unseen graphs — quantitative fractions are pilot-scale
- Chat-approved sidecars are not frame-certified video evidence
- I/O alpha-renaming is structural; does not recover semantic variable identity across graphs
- No Seen graph shares 5-node size with C2/R3 — M4 full-graph tests are dominated by TRIVIAL_SIZE_MISMATCH
- Pure Layer2 compositional evaluation requires Seen-atom-covered controls (see validity.E)
