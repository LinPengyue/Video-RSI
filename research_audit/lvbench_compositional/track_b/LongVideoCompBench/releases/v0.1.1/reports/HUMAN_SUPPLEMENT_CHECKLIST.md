# Human / GPT supplement checklist (WP2.1)

A/B remain `GRAPH_ONLY`. Do not treat graph I/O tokens as answers.

## A / B — required before completeness upgrade

For each of A and B, supply or approve:
1. Bound `video_id` (or explicitly reject hROKtPqktO8 / iA_69g87Ilw candidates).
2. Original question text (not reverse-derived from program graph).
3. Original answer text with certification status (still not formal Gold unless separately approved).
4. Approved `windows_seconds` A/B (ROI candidates are insufficient alone).
5. Explicit item_id↔evidence pack binding.

- A primary recovery rate: {'primary_fields': ['question', 'answer', 'video_id', 'windows'], 'n_recovered': 0, 'n_total': 4, 'rate': 0.0}
- B primary recovery rate: {'primary_fields': ['question', 'answer', 'video_id', 'windows'], 'n_recovered': 0, 'n_total': 4, 'rate': 0.0}

## C2 / R3 / F1 / F2 — window authorization

Filename-derived candidates exist but are **not** dataset windows. Approve or reject:

- `P7_VTCD_C2`: candidate {'A': [158, 191], 'B': [260, 285]} — status `PARTIAL_USER_PLAYBACK_OFFSETS_ONLY` — **needs scientific authorization**
- `P7_TJR_R3`: candidate {'A': [1100, 1125], 'B': [1200, 1220]} — status `PENDING_SCIENTIFIC_APPROVAL` — **needs scientific authorization**
- `P7_R4_F1`: candidate {'A': [259, 295], 'B': [2995, 3015]} — status `PENDING_SCIENTIFIC_APPROVAL` — **needs scientific authorization**
- `P7_R4_F2`: candidate {'A': [20, 45], 'B': [123, 165]} — status `PENDING_SCIENTIFIC_APPROVAL` — **needs scientific authorization**

See `reports/AB_SOURCE_RECOVERY_AUDIT.json` and `reports/WINDOW_RECOVERY_C2_R3_F1_F2_AUDIT.json`.
