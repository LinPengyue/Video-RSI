# Overlap report — BLOCKED

- Stage 2: **BLOCKED**
- Observed totals: {'nodes': 49, 'edges': 22} (expected {'nodes': 60, 'edges': 54})
- Stage 3 M1–M4 **not computed** (no fabricated structure overlap).

## Blocking gaps
- `SIDECAR_INCOMPLETE_BLOCKING`: {"graph_id": "SP001", "code": "SIDECAR_INCOMPLETE_BLOCKING", "gaps": ["NO_AUTHORITATIVE_EDGE_LIST: edges not present in graph_as_reviewed; refusing to invent topology", "NO_AUTHORITATIVE_NODE_IO: inputs/outputs not machine-specified in source", "NO_AUTHORITATIVE_TIME_CONDITIONS_PER_NODE"]}
- `COUNT_MISMATCH_VS_TASK`: {"graph_id": "SP001", "code": "COUNT_MISMATCH_VS_TASK", "got": {"nodes": 8, "edges": 0}, "expected": {"nodes": 8, "edges": 8}}
- `SIDECAR_INCOMPLETE_BLOCKING`: {"graph_id": "SP002", "code": "SIDECAR_INCOMPLETE_BLOCKING", "gaps": ["NO_AUTHORITATIVE_EDGE_LIST: edges not present in graph_as_reviewed; refusing to invent topology", "NO_AUTHORITATIVE_NODE_IO: inputs/outputs not machine-specified in source", "NO_AUTHORITATIVE_TIME_CONDITIONS_PER_NODE"]}
- `SIDECAR_INCOMPLETE_BLOCKING`: {"graph_id": "SP005", "code": "SIDECAR_INCOMPLETE_BLOCKING", "gaps": ["NO_AUTHORITATIVE_EDGE_LIST: edges not present in graph_as_reviewed; refusing to invent topology", "NO_AUTHORITATIVE_NODE_IO: inputs/outputs not machine-specified in source", "NO_AUTHORITATIVE_TIME_CONDITIONS_PER_NODE"]}
- `COUNT_MISMATCH_VS_TASK`: {"graph_id": "SP005", "code": "COUNT_MISMATCH_VS_TASK", "got": {"nodes": 8, "edges": 0}, "expected": {"nodes": 8, "edges": 7}}
- `SIDECAR_INCOMPLETE_BLOCKING`: {"graph_id": "SP201", "code": "SIDECAR_INCOMPLETE_BLOCKING", "gaps": ["MACRO_ONLY_GRAPH: task expects 4 nodes / 3 edges; source has 3 macro operators and no edge list", "REFUSING_TO_SPLIT_MACRO_OPERATORS without scientific expansion", "NODE_COUNT_VS_TASK: macro_ops=3 expected_nodes=4"]}
- `COUNT_MISMATCH_VS_TASK`: {"graph_id": "SP201", "code": "COUNT_MISMATCH_VS_TASK", "got": {"nodes": 3, "edges": 0}, "expected": {"nodes": 4, "edges": 3}}
- `SIDECAR_INCOMPLETE_BLOCKING`: {"graph_id": "SP202", "code": "SIDECAR_INCOMPLETE_BLOCKING", "gaps": ["MACRO_ONLY_GRAPH: task expects 4 nodes / 3 edges; source has 3 macro operators and no edge list", "REFUSING_TO_SPLIT_MACRO_OPERATORS without scientific expansion", "NODE_COUNT_VS_TASK: macro_ops=3 expected_nodes=4"]}
- `COUNT_MISMATCH_VS_TASK`: {"graph_id": "SP202", "code": "COUNT_MISMATCH_VS_TASK", "got": {"nodes": 3, "edges": 0}, "expected": {"nodes": 4, "edges": 3}}
- `MISSING`: {"graph_id": "A", "code": "MISSING", "gaps": ["No approved standalone directed program graph named A in repo or p7 approved_graphs_v0.2", "A appears only as clip_role / graph_as_reviewed window key, not a graph_id"]}
- `MISSING`: {"graph_id": "B", "code": "MISSING", "gaps": ["No approved standalone directed program graph named B in repo or p7 approved_graphs_v0.2", "B appears only as clip_role / graph_as_reviewed window key, not a graph_id"]}
- `TOTAL_COUNT_MISMATCH`: {"code": "TOTAL_COUNT_MISMATCH", "got": {"nodes": 49, "edges": 22}, "expected": {"nodes": 60, "edges": 54}}

## Scientific ambiguities
- **MISSING_GRAPH_A**: No approved standalone directed program graph with graph_id/item_id A
- **MISSING_GRAPH_B**: No approved standalone directed program graph with graph_id/item_id B
- **SEEN_LACK_STRUCTURED_EDGES**: SP001/SP002/SP005 only have graph_as_reviewed operator lists; task expects full node I/O + edges
- **SP201_SP202_MACRO_VS_4N3E**: Approved sources are 3-operator macros; task expects 4 nodes / 3 edges without authorizing a split
- **LAYER_VOCAB_UNFROZEN**: OPERATOR_LIBRARY_v1 on p7 branch is PENDING_SCIENTIFIC_APPROVAL; Layer1/2 map is provisional engineering

## Per-graph ingest
- `SP001`: status=SIDECAR_INCOMPLETE_BLOCKING nodes=8 edges=0
- `SP002`: status=SIDECAR_INCOMPLETE_BLOCKING nodes=5 edges=0
- `SP005`: status=SIDECAR_INCOMPLETE_BLOCKING nodes=8 edges=0
- `SP201`: status=SIDECAR_INCOMPLETE_BLOCKING nodes=3 edges=0
- `SP202`: status=SIDECAR_INCOMPLETE_BLOCKING nodes=3 edges=0
- `P7_VTCD_C2`: status=STRUCTURED_INGESTED nodes=5 edges=4
- `P7_TJR_R3`: status=STRUCTURED_INGESTED nodes=5 edges=5
- `A`: status=MISSING nodes=0 edges=0
- `B`: status=MISSING nodes=0 edges=0
- `P7_R4_F1`: status=STRUCTURED_INGESTED nodes=7 edges=9
- `P7_R4_F2`: status=STRUCTURED_INGESTED_WITH_MAPPING_GAPS nodes=5 edges=4
