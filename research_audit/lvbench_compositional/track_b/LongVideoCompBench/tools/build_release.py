#!/usr/bin/env python3
"""Build an immutable internal release snapshot (no public answers/videos)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DS_ROOT, sha256_file, utc_now, write_json  # noqa: E402


RELEASE_FILES = [
    "data/videos.jsonl",
    "data/qa_items.jsonl",
    "data/program_graphs.jsonl",
    "data/evidence.jsonl",
    "data/splits.json",
    "annotations/human_reviews.jsonl",
    "annotations/necessity_tests.jsonl",
    "annotations/adjudication_log.jsonl",
    "reports/bootstrap_report.json",
    "reports/coverage_report.json",
    "reports/split_integrity_report.json",
    "reports/validation_report.json",
    "VERSION",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v0.1.0")
    args = ap.parse_args()
    out = DS_ROOT / "releases" / args.version
    if out.exists() and any(out.iterdir()):
        # immutable: refuse inplace mutate
        raise SystemExit(
            f"Release {out} already exists; refuse inplace mutation. Bump version."
        )
    out.mkdir(parents=True, exist_ok=True)
    checksums = []
    copied = []
    for rel in RELEASE_FILES:
        src = DS_ROOT / rel
        if not src.is_file():
            continue
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        digest = sha256_file(dest)
        checksums.append(f"{digest}  {rel}")
        copied.append({"path": rel, "sha256": digest, "bytes": dest.stat().st_size})

    (out / "checksums.sha256").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    manifest = {
        "schema": "longvideocompbenc_release_manifest_v0_1",
        "version": args.version,
        "built_utc": utc_now(),
        "immutable": True,
        "public_release": False,
        "includes_video_binaries": False,
        "includes_public_test_answers": False,
        "files": copied,
        "warnings": [
            "Internal DEV snapshot only.",
            "Do not publish scorer-private Track A packs from this tree without isolation review.",
            "License not declared open.",
        ],
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps({"version": args.version, "n_files": len(copied), "path": str(out)}, indent=2))


if __name__ == "__main__":
    main()
