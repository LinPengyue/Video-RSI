# Overlap report — Stage 3

- status: `COMPUTED`
- algo: `normalized_programs_v1.1.0_handoff`
- built_utc: 2026-11-04T09:50:30+00:00

## M1 Layer1 coverage
- label-set coverage: 1.0
- node-instance coverage: 1.0
- unseen-only labels: []

## M2 Layer2 coverage
- label-set coverage: 0.14285714285714285
- node-instance coverage: 0.2
- unseen-only labels: ['DetectActionEvent', 'DetectTransportEvent', 'IdentifyPersonByAppearance', 'QueryBoundAction', 'QueryBoundTransport', 'ReadPersonNameFromGraphic']

## M3 subgraph overlap
### mode `ops`
- 2_node: intersection=0 / unseen_unique=8 (ratio=0.0)
- 3_node: intersection=0 / unseen_unique=7 (ratio=0.0)
### mode `ops_role`
- 2_node: intersection=0 / unseen_unique=9 (ratio=0.0)
- 3_node: intersection=0 / unseen_unique=8 (ratio=0.0)
### mode `ops_role_edge`
- 2_node: intersection=0 / unseen_unique=9 (ratio=0.0)
- 3_node: intersection=0 / unseen_unique=8 (ratio=0.0)
### mode `ops_role_edge_io`
- 2_node: intersection=0 / unseen_unique=9 (ratio=0.0)
- 3_node: intersection=0 / unseen_unique=8 (ratio=0.0)

## M4 full digraph equivalence
- `P7_VTCD_C2`: {'layer1': False, 'layer2': False, 'strict': False}
- `P7_TJR_R3`: {'layer1': False, 'layer2': False, 'strict': False}

## Candidate sensitivity (not formal 5/2)
- `A` any-Seen iso: {'layer1': False, 'layer2': False, 'strict': False}
- `B` any-Seen iso: {'layer1': False, 'layer2': False, 'strict': False}
- `P7_R4_F1` any-Seen iso: {'layer1': False, 'layer2': False, 'strict': False}
- `P7_R4_F2` any-Seen iso: {'layer1': False, 'layer2': False, 'strict': False}

Structural novelty ≠ compositional generalization capability.
