# LongVideoCompBench (Track B DEV)

Internal dataset skeleton for a CVPR 2027–oriented **long-video compositional generalization** benchmark.

This is **not** a public release. It is not limited to the 11 seed graphs; those seeds bootstrap the DEV store so incremental Human–GPT–Cursor batches can grow the benchmark safely.

## Task definition

Given a long source video and a compositional question that requires binding evidence across temporally separated windows, produce an answer that cannot be obtained from a single window shortcut.

Program graphs record directed operator structure (Layer1/Layer2) used for coverage and OOD analysis — they are **not** automatic Gold certificates.

## Layout

See repository tree under this directory: `schemas/`, `data/`, `annotations/`, `staging/`, `releases/`, `tools/`, `reports/`.

## Track A isolation

- Immutable **5 Seen + 2 Unseen** WP1 pack remains at  
  `../minimal_validation_export_v1/` (inference-safe whitelist there).
- This LongVideoCompBench DEV tree may contain answers and Unseen graph structure for **internal** work.
- Do **not** mount this tree as Track A ordinary inference input.
- Future sealed tests must live in a separate sealed store (not created this round).

## Quick start

```bash
python3 tools/bootstrap_dataset.py
python3 tools/validate_dataset.py
python3 tools/dataset_statistics.py
python3 tools/build_release.py --version v0.1.0
python3 tests/test_longvideocompbenc_v0_1.py -v
```

Incremental import (dry-run):

```bash
python3 tools/import_annotation_batch.py staging/example_batch.json
# add --apply only after review; never auto-Gold
```

## Versions

See `VERSION`, `CHANGELOG.md`, `DATASET_CARD.md`, `LICENSE_STATUS.md`.
