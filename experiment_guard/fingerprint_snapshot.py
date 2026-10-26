"""Disk-backed fingerprint snapshots — detect real config/harness drift.

Comparing a cached in-memory string to itself cannot detect mid-run edits.
Always re-read files from disk at checkpoints.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiment_guard.fingerprints import config_fingerprint, harness_fingerprint, sha256_file
from experiment_guard.redact import redact_path


@dataclass
class FingerprintSnapshot:
    config_path: Path | None
    harness_dir: Path | None
    config_fp: str
    harness_sha: str | None
    config_mtime_ns: int | None = None
    harness_file_count: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "config_path": redact_path(self.config_path),
            "harness_dir": redact_path(self.harness_dir),
            "config_fp": self.config_fp,
            "harness_sha": self.harness_sha,
            "config_mtime_ns": self.config_mtime_ns,
            "harness_file_count": self.harness_file_count,
        }


def _load_config_dict(config_path: Path | None, config: dict | None) -> dict:
    if config_path is not None and Path(config_path).is_file():
        return json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config is not None:
        return config
    raise FileNotFoundError("no config path or dict for fingerprint snapshot")


def capture_snapshot(
    *,
    config_path: Path | None = None,
    config: dict | None = None,
    harness_dir: Path | None = None,
) -> FingerprintSnapshot:
    """Read current on-disk (or provided) config + harness and hash them."""
    cfg = _load_config_dict(config_path, config)
    mtime = None
    if config_path is not None and Path(config_path).is_file():
        mtime = Path(config_path).stat().st_mtime_ns
    hp = harness_fingerprint(harness_dir)
    return FingerprintSnapshot(
        config_path=Path(config_path).resolve() if config_path else None,
        harness_dir=Path(harness_dir).resolve() if harness_dir else None,
        config_fp=config_fingerprint(cfg),
        harness_sha=hp.get("sha16"),
        config_mtime_ns=mtime,
        harness_file_count=hp.get("n_files_hashed"),
    )


def reread_fingerprint(
    *,
    config_path: Path | None,
    harness_dir: Path | None = None,
    fallback_config: dict | None = None,
) -> tuple[str, str | None]:
    """Force a fresh disk read. Returns (config_fp, harness_sha)."""
    snap = capture_snapshot(
        config_path=config_path,
        config=None if config_path and Path(config_path).is_file() else fallback_config,
        harness_dir=harness_dir,
    )
    return snap.config_fp, snap.harness_sha


def fingerprints_equal(a: FingerprintSnapshot, b: FingerprintSnapshot) -> bool:
    return a.config_fp == b.config_fp and (a.harness_sha or "") == (b.harness_sha or "")


def frame_bundle_hash(timestamps: list[float], frame_paths: list[Path] | None = None) -> str:
    """Hash for matched-frame claims: timestamps + optional JPEG bytes."""
    from experiment_guard.fingerprints import sha256_bytes

    parts = ["ts:" + ",".join("%.6f" % float(t) for t in timestamps)]
    if frame_paths:
        for p in frame_paths:
            digest = sha256_file(Path(p)) or "missing"
            parts.append(digest[:16])
    return sha256_bytes("|".join(parts).encode())[:16]
