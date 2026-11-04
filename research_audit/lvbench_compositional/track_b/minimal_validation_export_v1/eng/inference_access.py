#!/usr/bin/env python3
"""Machine-enforced Track A inference file access whitelist.

Inference processes must open files only through this module (or equivalent
checks against INFERENCE_ACCESS_WHITELIST.json). Parent-directory escape to
the scientific audit pack or scorer-private projection is rejected.
"""
from __future__ import annotations

import json
from pathlib import Path

WHITELIST_FILENAME = "INFERENCE_ACCESS_WHITELIST.json"

DEFAULT_ALLOWED = (
    "qa_items.json",
    "program_graphs_seen_redacted.json",
    "video_manifest.json",
    "split_manifest.json",
    "ACCESS.md",
    WHITELIST_FILENAME,
)


class InferenceAccessError(PermissionError):
    """Raised when a path is outside the inference-safe whitelist."""


def load_whitelist(inference_root: Path) -> dict:
    path = Path(inference_root) / WHITELIST_FILENAME
    if not path.is_file():
        raise InferenceAccessError(f"missing whitelist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_allowed_path(inference_root: Path, relative_path: str) -> Path:
    """Resolve a relative path under inference_root if and only if whitelisted.

    Rejects absolute paths, ``..`` escapes, symlinks leaving the root, and any
    relative path not listed in the whitelist.
    """
    root = Path(inference_root).resolve()
    if not relative_path or relative_path != str(Path(relative_path).as_posix()):
        # normalize and re-check below; reject empty
        pass
    rel = Path(relative_path)
    if rel.is_absolute():
        raise InferenceAccessError(f"absolute paths denied: {relative_path}")
    if ".." in rel.parts:
        raise InferenceAccessError(f"parent escape denied: {relative_path}")

    wl = load_whitelist(root)
    allowed = set(wl.get("allowed_relative_paths") or [])
    rel_posix = rel.as_posix()
    if rel_posix not in allowed:
        raise InferenceAccessError(
            f"path not on inference whitelist: {rel_posix}; allowed={sorted(allowed)}"
        )

    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise InferenceAccessError(
            f"resolved path escapes inference root: {candidate}"
        ) from e
    if not candidate.is_file():
        raise InferenceAccessError(f"whitelisted path missing: {candidate}")
    return candidate


def open_text(inference_root: Path, relative_path: str, encoding: str = "utf-8"):
    path = resolve_allowed_path(inference_root, relative_path)
    return path.read_text(encoding=encoding)


def assert_no_parent_reads(inference_root: Path, attempted_relative: str) -> None:
    """Explicit negative guard used by tests / Track A harness."""
    resolve_allowed_path(inference_root, attempted_relative)


def build_whitelist_document(algo_version: str) -> dict:
    return {
        "schema": "minimal_validation_inference_access_whitelist_v1",
        "algo_version": algo_version,
        "root_role": "projections/inference_safe",
        "enforcement": "eng/inference_access.py::resolve_allowed_path",
        "allowed_relative_paths": list(DEFAULT_ALLOWED),
        "denied_examples": [
            "../scorer_private/answers.json",
            "../../qa_items.json",
            "../../program_graphs.json",
            "../../split_manifest.json",
            "../scorer_private/eval_private_metadata.json",
        ],
        "policy": (
            "Ordinary Track A inference may open only allowed_relative_paths under "
            "this directory via resolve_allowed_path. Do not rely on ACCESS.md alone."
        ),
    }
