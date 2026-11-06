#!/usr/bin/env python3
"""Formal Batch Factory entry for S0–S9 production path (DEV).

Unified contract:
  Video Evidence → Sourced Facts → Relation Candidates → QA Family + Program Graph
  → Necessity → Structure Audit → DEV Review Queue

No semantic facts → explicit exit (no fabricated relations).
Does not hardcode video IDs, questions, or Necessity labels in the generic path.
Regression fixtures must not be imported here.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Wire LongVideoCompBench pipeline_conformance as the sole S3–S9 implementation.
_REPO = Path(__file__).resolve().parents[3]
_LVCB_TOOLS = (
    _REPO
    / "research_audit/lvbench_compositional/track_b/LongVideoCompBench/tools"
)
if str(_LVCB_TOOLS) not in sys.path:
    sys.path.insert(0, str(_LVCB_TOOLS))

from pipeline_conformance.formal_certification import evaluate_formal_ready  # noqa: E402
from pipeline_conformance.s3_s5_relation_qa import (  # noqa: E402
    RelationCandidate,
    SourcedFact,
    generate_qa_from_relation,
)
from pipeline_conformance.s6_necessity import (  # noqa: E402
    combine_necessity,
    model_necessity,
    shortcut_audit,
    structural_necessity,
)
from pipeline_conformance.s7_s9_gates import (  # noqa: E402
    independent_status_bundle,
    load_trusted_claims,
    release_gate_check,
)
from pipeline_conformance.s8_signature_feedback import audit_draft_against_seen  # noqa: E402

PRODUCTION_ENTRY = {
    "module": "tools.lvbench_comp.batch_factory.s0_s9_production",
    "wired_into_formal_batch_entry": True,
    "sole_s3_s9_path_for_dev_smoke": True,
    "legacy_qa_draft_bypassed": True,
    "production_closed_loop_scientific": False,
    "note": (
        "Engineering wiring complete for DEV smoke. Scientific Gold/closed-loop "
        "rates remain separate and are not implied by this flag."
    ),
}


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def load_evidence_pairs_from_rois(rois_jsonl: Path) -> list[dict[str, Any]]:
    """Group ROI rows into early/late pairs with real hashes. Generic — no video allowlist."""
    rows = _read_jsonl(rois_jsonl)
    by_pair: dict[str, dict[str, Any]] = defaultdict(dict)
    for r in rows:
        pid = r.get("pair_id")
        role = r.get("role")
        if not pid or role not in {"early", "late"}:
            continue
        by_pair[pid][role] = r
    out = []
    for pid, sides in sorted(by_pair.items()):
        if "early" not in sides or "late" not in sides:
            continue
        a, b = sides["early"], sides["late"]
        clip_a = (a.get("local_clip") or {})
        clip_b = (b.get("local_clip") or {})
        frames_a = a.get("frames_local") or a.get("review_frames") or []
        frames_b = b.get("frames_local") or b.get("review_frames") or []
        out.append(
            {
                "pair_id": pid,
                "video_id": a.get("video_id") or b.get("video_id"),
                "source_rois_jsonl": str(rois_jsonl),
                "method": a.get("method") or b.get("method"),
                "windows": {
                    "A": [float(a["t_start"]), float(a["t_end"])],
                    "B": [float(b["t_start"]), float(b["t_end"])],
                },
                "clip_sha256": {
                    "A": clip_a.get("sha256"),
                    "B": clip_b.get("sha256"),
                },
                "frame_sha256_sample": {
                    "A": [f.get("sha256") for f in frames_a[:3] if f.get("sha256")],
                    "B": [f.get("sha256") for f in frames_b[:3] if f.get("sha256")],
                },
                "semantics_a": a.get("semantics")
                or a.get("event_certification")
                or "UNRESOLVED",
                "semantics_b": b.get("semantics")
                or b.get("event_certification")
                or "UNRESOLVED",
                "evidence_packet_complete": bool(
                    clip_a.get("sha256") and clip_b.get("sha256")
                ),
                "roi_ids": [a.get("roi_id"), b.get("roi_id")],
            }
        )
    return out


def match_identity_claims(
    pair: dict[str, Any],
    trusted: dict[str, dict],
) -> list[dict[str, Any]]:
    """Return identity-scope claims whose video+windows match this pair."""
    matched = []
    vid = pair.get("video_id")
    win = pair.get("windows") or {}
    for claim in trusted.values():
        if claim.get("source_video_id") != vid:
            continue
        if claim.get("decision_scope") != "CROSS_WINDOW_PERSON_IDENTITY":
            continue
        cw = claim.get("windows") or {}
        if list(cw.get("A") or []) != list(win.get("A") or []):
            continue
        if list(cw.get("B") or []) != list(win.get("B") or []):
            continue
        matched.append(claim)
    return matched


def load_evidence_pairs_from_trusted_registry(records_jsonl: Path) -> list[dict[str, Any]]:
    """Build evidence pairs from trusted registry rows that carry clip hashes.

    Generic: groups by pair_id. Does not invent semantics or answer attributes.
    """
    trusted = load_trusted_claims(records_jsonl)
    by_pair: dict[str, dict] = {}
    for claim in trusted.values():
        pid = claim.get("pair_id")
        if not pid:
            continue
        hashes = claim.get("clip_sha256") or {}
        wins = claim.get("windows") or {}
        if not hashes.get("A") or not hashes.get("B") or not wins.get("A") or not wins.get("B"):
            continue
        by_pair[pid] = {
            "pair_id": pid,
            "video_id": claim.get("source_video_id"),
            "source_rois_jsonl": str(records_jsonl),
            "method": "trusted_registry_evidence",
            "windows": {"A": list(wins["A"]), "B": list(wins["B"])},
            "clip_sha256": {"A": hashes["A"], "B": hashes["B"]},
            "frame_sha256_sample": {"A": [], "B": []},
            "semantics_a": "UNRESOLVED",
            "semantics_b": "UNRESOLVED",
            "evidence_packet_complete": True,
            "roi_ids": [f"{pid}:A", f"{pid}:B"],
        }
    return [by_pair[k] for k in sorted(by_pair)]


def process_evidence_pair(
    pair: dict[str, Any],
    *,
    trusted_records_jsonl: Path,
) -> dict[str, Any]:
    """Run one pair through S2–S9 production path. Data-driven exits only."""
    trusted = load_trusted_claims(trusted_records_jsonl)
    trail: dict[str, Any] = {
        "pair_id": pair["pair_id"],
        "video_id": pair.get("video_id"),
        "production_entry": PRODUCTION_ENTRY,
        "built_utc": _utc(),
    }

    # --- Evidence trust ---
    evidence_ok = bool(pair.get("evidence_packet_complete"))
    trust_level = (
        "PACKET_HASHED_CLIPS"
        if evidence_ok
        else "INCOMPLETE_EVIDENCE_PACKET"
    )
    trail["evidence"] = {
        "complete": evidence_ok,
        "trust_level": trust_level,
        "windows": pair.get("windows"),
        "clip_sha256": pair.get("clip_sha256"),
        "semantics_a": pair.get("semantics_a"),
        "semantics_b": pair.get("semantics_b"),
        "source": pair.get("source_rois_jsonl"),
    }

    if not evidence_ok:
        trail["exit"] = "INCOMPLETE_EVIDENCE"
        trail["classification"] = "REJECT"
        trail["failure_reason"] = "missing_clip_sha256"
        return trail

    sem_a = pair.get("semantics_a") or "UNRESOLVED"
    sem_b = pair.get("semantics_b") or "UNRESOLVED"
    identity_claims = match_identity_claims(pair, trusted)
    trail["identity_claims"] = [c.get("claim_id") for c in identity_claims]

    # --- No semantic facts → explicit exit (do not mint fake relations) ---
    has_semantic = sem_a not in {"UNRESOLVED", None, ""} or sem_b not in {
        "UNRESOLVED",
        None,
        "",
    }
    # Identity claims certify bind only — still not answer semantics
    if not has_semantic and not identity_claims:
        trail["exit"] = "NO_SEMANTIC_FACTS"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = (
            "evidence_packet_present_but_semantics_UNRESOLVED_and_no_identity_claim;"
            "refusing_fabricated_relation"
        )
        trail["relation"] = None
        trail["qa"] = None
        trail["scientific"] = {
            "evidence_verified": True,
            "qa_family_generated": False,
            "structural_necessity_verified": False,
            "program_execution_verified": False,
            "atomic_covered_composition_ood_verified": False,
            "independent_gold_certified": False,
        }
        return trail

    # Build sourced facts from evidence (window existence FACT; attributes not certified)
    fact_a = SourcedFact(
        fact_id=f"FACT:{pair['pair_id']}:A",
        video_id=pair["video_id"],
        window=list(pair["windows"]["A"]),
        epistemic="FACT",
        entities=[{"role": "unknown", "desc": "entity_in_window_A"}],
        attributes={"scene": "UNRESOLVED"},
        evidence_refs=[
            f"{pair['pair_id']}/A#sha256:{pair['clip_sha256']['A']}"
        ],
        source_provenance="ROI_PACKET_HASHED_CLIP",
        certified_scopes=["WINDOW_EXISTENCE"]
        + (["CROSS_WINDOW_PERSON_IDENTITY"] if identity_claims else []),
        uncertified_attribute_keys=["scene"],
    )
    fact_b = SourcedFact(
        fact_id=f"FACT:{pair['pair_id']}:B",
        video_id=pair["video_id"],
        window=list(pair["windows"]["B"]),
        epistemic="FACT",
        entities=[{"role": "unknown", "desc": "entity_in_window_B"}],
        attributes={"scene": "UNRESOLVED"},
        evidence_refs=[
            f"{pair['pair_id']}/B#sha256:{pair['clip_sha256']['B']}"
        ],
        source_provenance="ROI_PACKET_HASHED_CLIP",
        certified_scopes=["WINDOW_EXISTENCE"]
        + (["CROSS_WINDOW_PERSON_IDENTITY"] if identity_claims else []),
        uncertified_attribute_keys=["scene"],
    )

    bind_status = "FACT" if identity_claims else "UNKNOWN"
    bind_ids = [c["claim_id"] for c in identity_claims if c.get("claim_id")]

    # Relation discovery: without queryable certified answer attrs, do not invent them
    rel = RelationCandidate(
        relation_id=f"REL:{pair['pair_id']}",
        video_id=pair["video_id"],
        relation_type="cross_window_same_person",
        fact_a=fact_a,
        fact_b=fact_b,
        bind_status=bind_status,
        bind_claim_ids=bind_ids,
        queryable_attributes=[],  # never fabricate seat/shop answers
        dependency_direction="B_identifies_then_query_A",
        notes="Production path: no fabricated answer attributes",
        human_bind_scope="CROSS_WINDOW_PERSON_IDENTITY",
    )
    trail["relation"] = {
        "relation_id": rel.relation_id,
        "bind_status": bind_status,
        "bind_claim_ids": bind_ids,
        "queryable_attributes": [],
        "process": (
            "identity_bind_from_trusted_registry"
            if identity_claims
            else "bind_UNKNOWN_no_identity_claim"
        ),
    }

    if bind_status == "UNKNOWN":
        trail["exit"] = "BIND_UNKNOWN"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = "no_certified_cross_window_identity_bind"
        qa_out = generate_qa_from_relation(rel)
        trail["qa"] = {"status": qa_out["status"], "failure_reason": qa_out.get("failure_reason")}
        trail["scientific"] = {
            "evidence_verified": True,
            "qa_family_generated": False,
            "structural_necessity_verified": False,
            "program_execution_verified": False,
            "atomic_covered_composition_ood_verified": False,
            "independent_gold_certified": False,
        }
        return trail

    # Identity bind present but no answer attributes → QA family must fail explicitly
    qa_out = generate_qa_from_relation(rel)
    trail["qa"] = {
        "status": qa_out["status"],
        "failure_reason": qa_out.get("failure_reason"),
        "family_id": qa_out.get("family_id"),
    }
    if qa_out["status"] != "OK":
        trail["exit"] = "QA_FAMILY_FAILED"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = qa_out.get("failure_reason")
        trail["s7_status"] = independent_status_bundle(
            human_relation="CERTIFIED_SAME_IDENTITY_ONLY",
            qa_draft="FAIL:" + str(qa_out.get("failure_reason")),
            necessity="NOT_REACHED",
            program_execution="PROGRAM_EXECUTION_NOT_RUN",
            formal_gold=False,
        )
        trail["scientific"] = {
            "evidence_verified": True,
            "qa_family_generated": False,
            "structural_necessity_verified": False,
            "program_execution_verified": False,
            "atomic_covered_composition_ood_verified": False,
            "independent_gold_certified": False,
        }
        return trail

    # If QA somehow OK (future attrs), continue Necessity/S8 without blind model / executor
    graph = qa_out["program_graph"]
    structural = structural_necessity(
        {
            "answer_localized_window": None,  # force UNKNOWN — no engineer presets
        }
    )
    # missing fields → UNKNOWN
    shortcut = shortcut_audit({})
    model = model_necessity(blind_model_available=False)
    nec = combine_necessity(structural, model, shortcut)
    s8 = audit_draft_against_seen(graph)
    status = independent_status_bundle(
        human_relation="CERTIFIED_SAME_IDENTITY_ONLY",
        qa_draft="OK_DRAFT",
        necessity=nec["overall_verdict"],
        program_execution="PROGRAM_EXECUTION_NOT_RUN",
        formal_gold=False,
    )
    gate = release_gate_check(
        {
            "bind_claim_ids": bind_ids,
            "video_id": pair["video_id"],
            "windows": pair["windows"],
            "clip_sha256": pair["clip_sha256"],
            "formal_gold": False,
            "necessity_overall": nec["overall_verdict"],
            "necessity_strict_proof": nec.get("strict_necessity_proof"),
            "model_necessity_status": model["status"],
            "program_execution": "PROGRAM_EXECUTION_NOT_RUN",
            "answer_certified_by_human_relation": False,
        },
        trusted_records_jsonl=trusted_records_jsonl,
    )
    formal = evaluate_formal_ready(
        {
            "qa_id": qa_out["qa"]["qa_id"],
            "program_id": graph["program_id"],
            "video_id": pair["video_id"],
            "windows": pair["windows"],
            "clip_sha256": pair["clip_sha256"],
            "bind_claim_ids": bind_ids,
            "answer_certified_by_human_relation": False,
            "formal_gold": False,
            # Intentionally omit store-backed necessity/execution → formal_ready false
        },
        trusted_records_jsonl=trusted_records_jsonl,
    )

    # Classification from data/rules only
    if nec["overall_verdict"] == "FAIL":
        classification = "CONTROL"
    elif not gate["allowed"]:
        classification = "PENDING"
    else:
        classification = "DEV"

    trail.update(
        {
            "exit": "FULL_PATH",
            "classification": classification,
            "s6": nec,
            "s8_audit": s8,
            "s7_status": status,
            "s9_release_gate": gate,
            "formal_certification": formal,
            "program_graph_semantic": graph.get("semantic_validation"),
            "program_execution": "PROGRAM_EXECUTION_NOT_RUN",
            "scientific": {
                "evidence_verified": True,
                "qa_family_generated": True,
                "structural_necessity_verified": bool(
                    nec.get("structural_strict_proof")
                ),
                "program_execution_verified": False,
                "atomic_covered_composition_ood_verified": bool(
                    s8.get("atomic_covered_ood_candidate")
                ),
                "independent_gold_certified": bool(
                    formal.get("independent_gold_certified")
                ),
            },
        }
    )
    return trail


def run_s0_s9_dev_smoke(
    *,
    rois_jsonl_paths: list[Path],
    trusted_records_jsonl: Path,
    output_dir: Path,
    max_pairs: int = 8,
    include_registry_evidence_pairs: bool = True,
) -> dict[str, Any]:
    """Batch Factory formal entry: DEV end-to-end smoke over existing ROI evidence."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[dict[str, Any]] = []
    for p in rois_jsonl_paths:
        pairs.extend(load_evidence_pairs_from_rois(p))
    # Dedup by pair_id (first source wins)
    seen_ids: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for pr in pairs:
        if pr["pair_id"] in seen_ids:
            continue
        seen_ids.add(pr["pair_id"])
        deduped.append(pr)
    pairs = deduped

    # Optionally merge registry-backed evidence (identity packets with hashes).
    # Selection remains generic — no hardcoded video IDs.
    if include_registry_evidence_pairs:
        for pr in load_evidence_pairs_from_trusted_registry(trusted_records_jsonl):
            if pr["pair_id"] not in seen_ids:
                pairs.append(pr)
                seen_ids.add(pr["pair_id"])

    # Prefer a mix: registry-backed first (real identity evidence), then ROI pairs.
    # Cap without hardcoding video IDs.
    trusted = load_trusted_claims(trusted_records_jsonl)
    with_id = [p for p in pairs if match_identity_claims(p, trusted)]
    with_ids = {p["pair_id"] for p in with_id}
    without = [p for p in pairs if p["pair_id"] not in with_ids]
    ordered = with_id + without
    pairs = ordered[: max(0, max_pairs)]

    results = [
        process_evidence_pair(pair, trusted_records_jsonl=trusted_records_jsonl)
        for pair in pairs
    ]

    def _rate(key: str) -> dict[str, Any]:
        n = len(results)
        k = sum(1 for r in results if (r.get("scientific") or {}).get(key))
        return {"numerator": k, "denominator": n, "rate": (k / n) if n else 0.0}

    class_counts: dict[str, int] = defaultdict(int)
    exit_counts: dict[str, int] = defaultdict(int)
    for r in results:
        class_counts[r.get("classification") or "UNKNOWN"] += 1
        exit_counts[r.get("exit") or "UNKNOWN"] += 1

    report = {
        "schema": "s0_s9_dev_smoke_report_v1",
        "built_utc": _utc(),
        "production_entry": PRODUCTION_ENTRY,
        "n_pairs": len(results),
        "rois_sources": [str(p) for p in rois_jsonl_paths],
        "classification_counts": dict(class_counts),
        "exit_counts": dict(exit_counts),
        "pipeline_engineering_completion": {
            "wired_into_formal_batch_entry": True,
            "unified_io_contract": True,
            "legacy_qa_draft_bypassed_on_this_path": True,
            "pairs_processed_end_to_end": len(results),
            "production_closed_loop_scientific_claimed": False,
        },
        "scientific_rates": {
            "evidence_verified": _rate("evidence_verified"),
            "qa_family_generated": _rate("qa_family_generated"),
            "structural_necessity_verified": _rate("structural_necessity_verified"),
            "program_execution_verified": _rate("program_execution_verified"),
            "atomic_covered_composition_ood_verified": _rate(
                "atomic_covered_composition_ood_verified"
            ),
            "independent_gold_certified": _rate("independent_gold_certified"),
        },
        "failures": [
            {
                "pair_id": r.get("pair_id"),
                "exit": r.get("exit"),
                "failure_reason": r.get("failure_reason"),
                "classification": r.get("classification"),
            }
            for r in results
            if r.get("exit") not in {"FULL_PATH"}
        ],
        "results": results,
        "protections": {
            "formal_gold": 0,
            "sealed_accessed": False,
            "track_a_run": False,
            "new_videos": False,
            "expensive_blind_model": False,
        },
    }

    (output_dir / "s0_s9_dev_smoke_results.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + ("\n" if results else ""),
        encoding="utf-8",
    )
    (output_dir / "S0_S9_DEV_SMOKE_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "failures.jsonl").write_text(
        "\n".join(json.dumps(f, ensure_ascii=False) for f in report["failures"])
        + ("\n" if report["failures"] else ""),
        encoding="utf-8",
    )
    return report
