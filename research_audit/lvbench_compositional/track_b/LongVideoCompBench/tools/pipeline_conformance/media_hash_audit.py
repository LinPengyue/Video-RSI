#!/usr/bin/env python3
"""P0: Evidence manifest vs media hash vs semantic fact vs human relation.

Hash field presence ≠ media_hash_reverified ≠ semantic_fact_verified.
Human Claim SHA and ROI SHA may differ when windows were re-extracted;
equivalence requires auditable same-video/same-window reextract evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def evidence_flags(
    *,
    manifest_has_ab_hashes: bool,
    media_hash_reverified: bool,
    semantic_fact_verified: bool,
    human_relation_certified: bool,
) -> dict[str, Any]:
    return {
        "evidence_manifest_complete": bool(manifest_has_ab_hashes),
        "media_hash_reverified": bool(media_hash_reverified),
        "semantic_fact_verified": bool(semantic_fact_verified),
        "human_relation_certified": bool(human_relation_certified),
        "rules": {
            "hash_field_presence_is_not_semantic_fact_verified": True,
            "manifest_complete_is_not_media_reverified": True,
            "human_identity_is_not_answer_certification": True,
        },
    }


def reverify_declared_hash(path: Path | None, declared: str | None) -> dict[str, Any]:
    if not declared:
        return {"status": "NO_DECLARED_HASH", "match": False, "computed": None}
    if path is None:
        return {
            "status": "PATH_MISSING_CANNOT_REVERIFY",
            "match": False,
            "declared": declared,
            "computed": None,
        }
    computed = sha256_file(path)
    if computed is None:
        return {
            "status": "FILE_MISSING",
            "match": False,
            "declared": declared,
            "path": str(path),
            "computed": None,
        }
    ok = computed == declared
    return {
        "status": "MATCH" if ok else "MISMATCH",
        "match": ok,
        "declared": declared,
        "computed": computed,
        "path": str(path),
        "bytes": path.stat().st_size if path.exists() else None,
    }


def build_reextract_equivalence(
    *,
    pair_id: str,
    video_id: str,
    windows: dict[str, list[float]],
    registry_hashes: dict[str, str],
    registry_paths: dict[str, str],
    roi_hashes: dict[str, str],
    roi_paths: dict[str, str],
    repo_root: Path,
) -> dict[str, Any]:
    """Document ROI vs Human-adj clip hash divergence for same video+window.

    Byte inequality with matching video_id + windows + both files present →
    EQUIVALENT_REEXTRACT_SAME_WINDOW (not byte-identical). Missing files → UNRESOLVED.
    """
    sides = {}
    all_ok = True
    for side in ("A", "B"):
        reg_p = repo_root / registry_paths.get(side, "") if registry_paths.get(side) else None
        roi_p = repo_root / roi_paths.get(side, "") if roi_paths.get(side) else None
        reg_v = reverify_declared_hash(reg_p, registry_hashes.get(side))
        roi_v = reverify_declared_hash(roi_p, roi_hashes.get(side))
        same_bytes = (
            reg_v.get("computed")
            and roi_v.get("computed")
            and reg_v["computed"] == roi_v["computed"]
        )
        if same_bytes:
            status = "BYTE_IDENTICAL"
        elif reg_v.get("match") and roi_v.get("match") and not same_bytes:
            status = "EQUIVALENT_REEXTRACT_SAME_WINDOW"
        elif reg_v.get("status") == "FILE_MISSING" or roi_v.get("status") == "FILE_MISSING":
            status = "UNRESOLVED_MISSING_FILE"
            all_ok = False
        elif not reg_v.get("match") or not roi_v.get("match"):
            status = "UNRESOLVED_HASH_NOT_REVERIFIED"
            all_ok = False
        else:
            status = "UNRESOLVED"
            all_ok = False
        sides[side] = {
            "status": status,
            "registry": reg_v,
            "roi": roi_v,
            "window": windows.get(side),
        }
    equiv = all(
        sides[s]["status"] in {"BYTE_IDENTICAL", "EQUIVALENT_REEXTRACT_SAME_WINDOW"}
        for s in ("A", "B")
    )
    return {
        "schema": "media_equivalence_v1",
        "pair_id": pair_id,
        "video_id": video_id,
        "windows": windows,
        "equivalent": equiv,
        "equivalence_class": (
            "SAME_SOURCE_VIDEO_SAME_WINDOW_REEXTRACT"
            if equiv
            else "UNRESOLVED"
        ),
        "byte_identical": all(sides[s]["status"] == "BYTE_IDENTICAL" for s in ("A", "B")),
        "sides": sides,
        "note": (
            "Different SHA with same video_id+windows and both files re-hashing to their "
            "declared values indicates separate extracts/encodes of the same interval — "
            "not proof of identical pixels/codecs."
        ),
    }


def match_identity_claims_strict(
    *,
    video_id: str,
    windows: dict[str, list[float]],
    candidate_clip_sha256: dict[str, str] | None,
    trusted: dict[str, dict],
    media_equivalence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Match Human SAME claims with decision/scope/video/windows/media-chain checks."""
    matched = []
    rejected = []
    for claim in trusted.values():
        cid = claim.get("claim_id")
        reasons = []
        if claim.get("decision") != "SAME":
            reasons.append("decision_not_SAME")
        if claim.get("decision_scope") != "CROSS_WINDOW_PERSON_IDENTITY":
            reasons.append(f"scope:{claim.get('decision_scope')}")
        if claim.get("source_video_id") != video_id:
            reasons.append("video_mismatch")
        cw = claim.get("windows") or {}
        if list(cw.get("A") or []) != list(windows.get("A") or []):
            reasons.append("window_A_mismatch")
        if list(cw.get("B") or []) != list(windows.get("B") or []):
            reasons.append("window_B_mismatch")
        if not claim.get("provenance_chain"):
            reasons.append("missing_provenance_chain")

        ch = claim.get("clip_sha256") or {}
        media_ok = False
        media_mode = None
        if candidate_clip_sha256 and ch:
            if (
                candidate_clip_sha256.get("A") == ch.get("A")
                and candidate_clip_sha256.get("B") == ch.get("B")
            ):
                media_ok = True
                media_mode = "EXACT_CLAIM_HASH_MATCH"
            elif (
                media_equivalence
                and media_equivalence.get("equivalent")
                and media_equivalence.get("pair_id") == claim.get("pair_id")
                and media_equivalence.get("video_id") == video_id
            ):
                media_ok = True
                media_mode = "EQUIVALENT_REEXTRACT_MAP"
            else:
                reasons.append("media_hash_not_equivalent_to_claim")
        elif not ch:
            reasons.append("claim_missing_clip_sha256")
        else:
            # No candidate hashes — still allow if claim chain complete (registry-only pair)
            media_ok = True
            media_mode = "REGISTRY_AUTHORITATIVE_NO_CANDIDATE_HASH"

        if reasons:
            rejected.append({"claim_id": cid, "reasons": reasons})
            continue
        if not media_ok:
            rejected.append({"claim_id": cid, "reasons": ["media_chain_failed"]})
            continue
        matched.append(
            {
                "claim_id": cid,
                "entity": claim.get("entity"),
                "media_mode": media_mode,
                "decision_scope": claim.get("decision_scope"),
                "does_not_certify": claim.get("does_not_certify"),
            }
        )
    return {
        "matched": matched,
        "rejected": rejected,
        "human_relation_certified": len(matched) > 0,
    }


def audit_pair_media(
    *,
    pair_id: str,
    video_id: str,
    windows: dict[str, list[float]],
    roi_hashes: dict[str, str] | None,
    roi_paths: dict[str, str] | None,
    claim: dict[str, Any] | None,
    repo_root: Path,
) -> dict[str, Any]:
    """Full media audit for one pair."""
    manifest_complete = bool(
        (roi_hashes or {}).get("A") and (roi_hashes or {}).get("B")
    ) or bool(
        claim
        and (claim.get("clip_sha256") or {}).get("A")
        and (claim.get("clip_sha256") or {}).get("B")
    )

    equiv = None
    reverified_any = False
    if claim and roi_hashes:
        equiv = build_reextract_equivalence(
            pair_id=pair_id,
            video_id=video_id,
            windows=windows,
            registry_hashes=claim.get("clip_sha256") or {},
            registry_paths=claim.get("local_clip_paths") or {},
            roi_hashes=roi_hashes,
            roi_paths=roi_paths or {},
            repo_root=repo_root,
        )
        reverified_any = any(
            equiv["sides"][s]["registry"].get("match")
            or equiv["sides"][s]["roi"].get("match")
            for s in ("A", "B")
        )
    elif claim:
        # Registry-only: reverify claim paths
        sides = {}
        for side in ("A", "B"):
            p = claim.get("local_clip_paths", {}).get(side)
            sides[side] = reverify_declared_hash(
                repo_root / p if p else None,
                (claim.get("clip_sha256") or {}).get(side),
            )
            if sides[side].get("match"):
                reverified_any = True
        equiv = {
            "schema": "media_equivalence_v1",
            "pair_id": pair_id,
            "equivalent": all(sides[s].get("match") for s in ("A", "B")),
            "equivalence_class": "REGISTRY_ONLY",
            "sides": sides,
        }

    return {
        "pair_id": pair_id,
        "flags": evidence_flags(
            manifest_has_ab_hashes=manifest_complete,
            media_hash_reverified=reverified_any,
            semantic_fact_verified=False,  # never from hashes alone
            human_relation_certified=False,  # set by caller after claim match
        ),
        "media_equivalence": equiv,
        "roi_hashes": roi_hashes,
        "registry_hashes": (claim or {}).get("clip_sha256"),
    }
