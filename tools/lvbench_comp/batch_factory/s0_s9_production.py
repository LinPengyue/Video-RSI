#!/usr/bin/env python3
"""Formal Batch Factory entry for S0–S9 production path (DEV).

Unified contract:
  Video Evidence → Sourced Facts → Relation Candidates → QA Family + Program Graph
  → Necessity → Structure Audit → DEV Review Queue

Consumes real semantic records via Semantic Fact Adapter.
Does not hardcode queryable_attributes=[].
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_LVCB_TOOLS = (
    _REPO
    / "research_audit/lvbench_compositional/track_b/LongVideoCompBench/tools"
)
_WP3 = (
    _REPO
    / "research_audit/lvbench_compositional/track_b/LongVideoCompBench/wp3_production"
)
if str(_LVCB_TOOLS) not in sys.path:
    sys.path.insert(0, str(_LVCB_TOOLS))

from pipeline_conformance.formal_certification import evaluate_formal_ready  # noqa: E402
from pipeline_conformance.media_hash_audit import (  # noqa: E402
    audit_pair_media,
    match_identity_claims_strict,
)
from pipeline_conformance.s3_s5_relation_qa import generate_qa_from_relation  # noqa: E402
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
from pipeline_conformance.semantic_fact_adapter import (  # noqa: E402
    build_relation_candidate,
    build_sourced_facts_for_pair,
    load_dev_semantic_corpus,
)

PRODUCTION_ENTRY = {
    "module": "tools.lvbench_comp.batch_factory.s0_s9_production",
    "wired_into_formal_batch_entry": True,
    "sole_s3_s9_path_for_dev_smoke": True,
    "legacy_qa_draft_bypassed": True,
    "semantic_fact_adapter": True,
    "production_closed_loop_scientific": False,
    "note": (
        "Engineering wiring + semantic adapter for DEV. "
        "Scientific Gold/closed-loop rates remain separate."
    ),
}


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def load_evidence_pairs_from_rois(rois_jsonl: Path) -> list[dict[str, Any]]:
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
        clip_a = a.get("local_clip") or {}
        clip_b = b.get("local_clip") or {}
        out.append(
            {
                "pair_id": pid,
                "video_id": a.get("video_id") or b.get("video_id"),
                "source_rois_jsonl": str(rois_jsonl),
                "method": a.get("method") or a.get("discovery_method") or b.get("method"),
                "windows": {
                    "A": [float(a["t_start"]), float(a["t_end"])],
                    "B": [float(b["t_start"]), float(b["t_end"])],
                },
                "clip_sha256": {
                    "A": clip_a.get("sha256"),
                    "B": clip_b.get("sha256"),
                },
                "clip_paths": {
                    "A": clip_a.get("path"),
                    "B": clip_b.get("path"),
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


def load_evidence_pairs_from_trusted_registry(records_jsonl: Path) -> list[dict[str, Any]]:
    trusted = load_trusted_claims(records_jsonl)
    by_pair: dict[str, dict] = {}
    for claim in trusted.values():
        pid = claim.get("pair_id")
        if not pid:
            continue
        hashes = claim.get("clip_sha256") or {}
        wins = claim.get("windows") or {}
        paths = claim.get("local_clip_paths") or {}
        if not hashes.get("A") or not hashes.get("B") or not wins.get("A") or not wins.get("B"):
            continue
        by_pair[pid] = {
            "pair_id": pid,
            "video_id": claim.get("source_video_id"),
            "source_rois_jsonl": str(records_jsonl),
            "method": "trusted_registry_evidence",
            "windows": {"A": list(wins["A"]), "B": list(wins["B"])},
            "clip_sha256": {"A": hashes["A"], "B": hashes["B"]},
            "clip_paths": {"A": paths.get("A"), "B": paths.get("B")},
            "semantics_a": "UNRESOLVED",
            "semantics_b": "UNRESOLVED",
            "evidence_packet_complete": True,
            "roi_ids": [f"{pid}:A", f"{pid}:B"],
            "from_registry": True,
        }
    return [by_pair[k] for k in sorted(by_pair)]


def _structural_evidence_from_audit(pair_id: str, corpus: dict[str, Any]) -> tuple[dict, dict]:
    """Build Necessity inputs from engineering structural audit with provenance tags."""
    audit = corpus.get("necessity_audit") or {}
    for item in audit.get("items") or []:
        if item.get("pair_id") != pair_id:
            continue
        sc = item.get("structural_shortcut_audit") or {}
        if sc.get("A_boy_seat_directly_observable"):
            structural_ev = {
                "answer_localized_window": "A",
                "a_unique_answer_bearing_entity": bool(sc.get("A_unique_boy")),
                "b_contains_answer_payload": False,
                "bind_required_for_answer_payload": False,
                "within_b_subject_switch": bool(sc.get("B_within_roi_subject_switch")),
                "multi_signage_uniqueness_verified": None,
                "field_provenance": {
                    "answer_localized_window": "engineer_unverified_shortcut_hypothesis",
                    "a_unique_answer_bearing_entity": "engineer_unverified_shortcut_hypothesis",
                    "b_contains_answer_payload": "engineer_unverified_shortcut_hypothesis",
                    "bind_required_for_answer_payload": "engineer_unverified_shortcut_hypothesis",
                    "within_b_subject_switch": "engineer_unverified_shortcut_hypothesis",
                },
                "audited_entity_binds": item.get("qa_id"),
                "notes": sc.get("reason_A_only") or "",
            }
            shortcut_sig = {
                "ocr_answer_in_window_A": False,
                "single_candidate_entity_in_A": bool(sc.get("A_unique_boy")),
                "question_text_leaks_answer": False,
                "language_prior_celebrity_or_brand": False,
                "subtitle_leak": False,
                "signal_provenance": {
                    "single_candidate_entity_in_A": "engineer_unverified_shortcut_hypothesis",
                },
            }
            return structural_ev, shortcut_sig
        if sc.get("A_shop_sign_ocr_visible"):
            structural_ev = {
                "answer_localized_window": "A",
                "a_unique_answer_bearing_entity": True,
                "b_contains_answer_payload": False,
                "bind_required_for_answer_payload": False,
                "within_b_subject_switch": False,
                "multi_signage_uniqueness_verified": False,
                "field_provenance": {
                    "answer_localized_window": "engineer_unverified_shortcut_hypothesis",
                    "a_unique_answer_bearing_entity": "engineer_unverified_shortcut_hypothesis",
                    "b_contains_answer_payload": "engineer_unverified_shortcut_hypothesis",
                    "bind_required_for_answer_payload": "engineer_unverified_shortcut_hypothesis",
                    "multi_signage_uniqueness_verified": "engineer_unverified_shortcut_hypothesis",
                },
                "notes": sc.get("reason_A_only") or "",
            }
            shortcut_sig = {
                "ocr_answer_in_window_A": True,
                "single_candidate_entity_in_A": bool(sc.get("A_unique_plaid_man_in_focus")),
                "question_text_leaks_answer": False,
                "language_prior_celebrity_or_brand": False,
                "subtitle_leak": False,
                "signal_provenance": {
                    "ocr_answer_in_window_A": "engineer_unverified_shortcut_hypothesis",
                },
            }
            return structural_ev, shortcut_sig
    # Default: no engineer presets → structural UNKNOWN
    return (
        {"answer_localized_window": None},
        {},
    )


def process_evidence_pair(
    pair: dict[str, Any],
    *,
    trusted_records_jsonl: Path,
    corpus: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root or _REPO
    corpus = corpus or load_dev_semantic_corpus(_WP3)
    trusted = load_trusted_claims(trusted_records_jsonl)

    trail: dict[str, Any] = {
        "pair_id": pair["pair_id"],
        "video_id": pair.get("video_id"),
        "production_entry": PRODUCTION_ENTRY,
        "built_utc": _utc(),
    }

    # Pick a representative claim for media audit (same pair)
    claim0 = next(
        (c for c in trusted.values() if c.get("pair_id") == pair["pair_id"]),
        None,
    )
    media = audit_pair_media(
        pair_id=pair["pair_id"],
        video_id=pair["video_id"],
        windows=pair["windows"],
        roi_hashes=None if pair.get("from_registry") else pair.get("clip_sha256"),
        roi_paths=None if pair.get("from_registry") else pair.get("clip_paths"),
        claim=claim0,
        repo_root=repo_root,
    )
    equiv = media.get("media_equivalence")

    # Identity match with media chain
    id_match = match_identity_claims_strict(
        video_id=pair["video_id"],
        windows=pair["windows"],
        candidate_clip_sha256=pair.get("clip_sha256"),
        trusted=trusted,
        media_equivalence=equiv if equiv and equiv.get("equivalent") else None,
    )
    media["flags"]["human_relation_certified"] = id_match["human_relation_certified"]

    # Authoritative hashes for evidence refs: prefer registry when claim matched
    if id_match["matched"] and claim0:
        auth_hashes = claim0.get("clip_sha256") or pair.get("clip_sha256")
        auth_paths = claim0.get("local_clip_paths") or pair.get("clip_paths") or {}
    else:
        auth_hashes = pair.get("clip_sha256") or {}
        auth_paths = pair.get("clip_paths") or {}

    manifest_ok = media["flags"]["evidence_manifest_complete"]
    trail["evidence"] = {
        "flags": media["flags"],
        "media_equivalence": equiv,
        "windows": pair.get("windows"),
        "clip_sha256_candidate": pair.get("clip_sha256"),
        "clip_sha256_authoritative": auth_hashes,
        "source": pair.get("source_rois_jsonl"),
        "identity_match": id_match,
    }

    if not manifest_ok:
        trail["exit"] = "INCOMPLETE_EVIDENCE"
        trail["classification"] = "REJECT"
        trail["failure_reason"] = "evidence_manifest_incomplete"
        trail["scientific_gates"] = _empty_gates()
        return trail

    refs_a = [
        f"{auth_paths.get('A') or pair['pair_id']+'/A'}#sha256:{auth_hashes.get('A')}"
    ]
    refs_b = [
        f"{auth_paths.get('B') or pair['pair_id']+'/B'}#sha256:{auth_hashes.get('B')}"
    ]

    assembled = build_sourced_facts_for_pair(
        pair_id=pair["pair_id"],
        video_id=pair["video_id"],
        windows=pair["windows"],
        evidence_refs_a=refs_a,
        evidence_refs_b=refs_b,
        identity_matches=id_match["matched"],
        corpus=corpus,
    )
    media["flags"]["semantic_fact_verified"] = assembled["semantic_fact_verified"]
    trail["evidence"]["flags"] = media["flags"]
    trail["semantic_adapter"] = {
        "has_semantic_records": assembled["has_semantic_records"],
        "has_dev_draft_answer_attributes": assembled["has_dev_draft_answer_attributes"],
        "gpt_observation_n": len(assembled["gpt_observations"]),
        "queryable_n": len(assembled["queryable_attributes"]),
        "bind_status": assembled["bind_status"],
        "qa_draft_packaging_refs": assembled["qa_draft_packaging_refs"],
        "notes": assembled["notes"],
    }

    # Early exit: no semantic records at all
    if not assembled["has_semantic_records"]:
        trail["exit"] = "NO_SEMANTIC_FACTS"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = (
            "evidence_manifest_present_but_no_semantic_records;"
            "refusing_fabricated_relation"
        )
        trail["relation"] = None
        trail["scientific_gates"] = _gates(
            evidence_manifest=True,
            media_reverified=media["flags"]["media_hash_reverified"],
            semantic_facts=False,
        )
        return trail

    # Identity without media equivalence when ROI hashes disagree → unresolved bind media
    if (
        claim0
        and not pair.get("from_registry")
        and pair.get("clip_sha256")
        and claim0.get("clip_sha256")
        and pair["clip_sha256"] != claim0["clip_sha256"]
        and not (equiv and equiv.get("equivalent"))
    ):
        trail["exit"] = "MEDIA_EQUIVALENCE_UNRESOLVED"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = (
            "roi_and_registry_clip_sha_differ_without_equivalence_map"
        )
        trail["scientific_gates"] = _gates(
            evidence_manifest=True,
            media_reverified=media["flags"]["media_hash_reverified"],
            semantic_facts=False,
            human_relation=False,
        )
        return trail

    rel = build_relation_candidate(pair["pair_id"], assembled)
    trail["relation"] = {
        "relation_id": rel.relation_id,
        "relation_type": rel.relation_type,
        "bind_status": rel.bind_status,
        "bind_claim_ids": rel.bind_claim_ids,
        "queryable_attributes": rel.queryable_attributes,
        "process": "semantic_fact_adapter",
    }

    if rel.bind_status == "UNKNOWN":
        qa_out = generate_qa_from_relation(rel)
        trail["exit"] = "BIND_UNKNOWN"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = "no_certified_cross_window_identity_bind"
        trail["qa"] = {
            "status": qa_out["status"],
            "failure_reason": qa_out.get("failure_reason"),
        }
        trail["scientific_gates"] = _gates(
            evidence_manifest=True,
            media_reverified=media["flags"]["media_hash_reverified"],
            semantic_facts=bool(assembled["gpt_observations"] or assembled["queryable_attributes"]),
            relation=False,
        )
        return trail

    if not assembled["queryable_attributes"]:
        trail["exit"] = "NO_TRACEABLE_ANSWER_ATTRIBUTES"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = (
            "identity_certified_but_no_traceable_answer_attributes_in_semantic_corpus;"
            "refusing_fabricated_attributes_for_FULL_PATH"
        )
        trail["scientific_gates"] = _gates(
            evidence_manifest=True,
            media_reverified=media["flags"]["media_hash_reverified"],
            semantic_facts=False,
            human_relation=True,
            relation=True,
        )
        return trail

    qa_out = generate_qa_from_relation(rel)
    trail["qa"] = {
        "status": qa_out["status"],
        "failure_reason": qa_out.get("failure_reason"),
        "family_id": qa_out.get("family_id"),
        "answer_certification": (qa_out.get("qa") or {}).get("answer_certification"),
        "formal_gold": False,
        "dev_draft_only": True,
    }
    if qa_out["status"] != "OK":
        trail["exit"] = "QA_FAMILY_FAILED"
        trail["classification"] = "PENDING"
        trail["failure_reason"] = qa_out.get("failure_reason")
        trail["scientific_gates"] = _gates(
            evidence_manifest=True,
            media_reverified=media["flags"]["media_hash_reverified"],
            semantic_facts=True,
            human_relation=True,
            relation=True,
            qa=False,
        )
        return trail

    graph = qa_out["program_graph"]
    structural_ev, shortcut_sig = _structural_evidence_from_audit(pair["pair_id"], corpus)
    structural = structural_necessity(structural_ev)
    shortcut = shortcut_audit(shortcut_sig)
    model = model_necessity(blind_model_available=False)
    nec = combine_necessity(structural, model, shortcut)
    s8 = audit_draft_against_seen(graph)
    status = independent_status_bundle(
        human_relation="CERTIFIED_SAME_IDENTITY_ONLY",
        qa_draft="OK_DEV_DRAFT_ANSWER_ATTR_NOT_HUMAN_CERTIFIED",
        necessity=nec["overall_verdict"],
        program_execution="PROGRAM_EXECUTION_NOT_RUN",
        formal_gold=False,
    )
    gate = release_gate_check(
        {
            "bind_claim_ids": rel.bind_claim_ids,
            "video_id": pair["video_id"],
            "windows": pair["windows"],
            "clip_sha256": auth_hashes,
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
            "clip_sha256": auth_hashes,
            "bind_claim_ids": rel.bind_claim_ids,
            "answer_certified_by_human_relation": False,
            "formal_gold": False,
            # Intentionally no store paths with records → not formal ready
        },
        trusted_records_jsonl=trusted_records_jsonl,
    )

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
            "s3_s5": {
                "qa": qa_out["qa"],
                "program_graph_summary": {
                    "program_id": graph["program_id"],
                    "dataflow_topology": graph.get("dataflow_topology"),
                    "semantic_validation": graph.get("semantic_validation"),
                    "program_execution": graph.get("program_execution"),
                    "executable_pass": False,
                },
            },
            "s6": nec,
            "s8_audit": {
                "bucket": s8.get("bucket"),
                "atomic_covered_in_seen_layer1": s8.get("atomic_covered_in_seen_layer1"),
                "atomic_covered_in_seen_layer2": s8.get("atomic_covered_in_seen_layer2"),
                "atomic_covered_ood_candidate": s8.get("atomic_covered_ood_candidate"),
                "training_exposure_status": (s8.get("gates") or {})
                .get("training_exposure_check", {})
                .get("status"),
            },
            "s7_status": status,
            "s9_release_gate": {
                "allowed": gate["allowed"],
                "codes": gate["codes"],
                "formal_gold": False,
            },
            "formal_certification": {
                "formal_ready": formal["formal_ready"],
                "codes": formal["codes"][:12],
                "independent_gold_certified": False,
            },
            "scientific_gates": _gates(
                evidence_manifest=True,
                media_reverified=media["flags"]["media_hash_reverified"],
                semantic_facts=True,
                human_relation=True,
                relation=True,
                qa=True,
                graph_semantic=(graph.get("semantic_validation") or {}).get("status")
                == "OK",
                program_execution=False,
                structural_necessity=bool(nec.get("structural_strict_proof")),
                model_necessity=False,
                s8_atomic_ood=bool(s8.get("atomic_covered_ood_candidate")),
                formal_gold=False,
            ),
        }
    )
    return trail


def _empty_gates() -> dict[str, bool]:
    return _gates()


def _gates(
    *,
    evidence_manifest: bool = False,
    media_reverified: bool = False,
    semantic_facts: bool = False,
    human_relation: bool = False,
    relation: bool = False,
    qa: bool = False,
    graph_semantic: bool = False,
    program_execution: bool = False,
    structural_necessity: bool = False,
    model_necessity: bool = False,
    s8_atomic_ood: bool = False,
    formal_gold: bool = False,
) -> dict[str, bool]:
    return {
        "evidence_manifest_complete": evidence_manifest,
        "media_hash_reverified": media_reverified,
        "semantic_facts_available": semantic_facts,
        "human_relation_certified": human_relation,
        "relation_candidates_verified": relation,
        "qa_drafts_generated": qa,
        "program_graph_semantic_validation": graph_semantic,
        "program_execution_verified": program_execution,
        "structural_necessity_verified": structural_necessity,
        "model_necessity_run": model_necessity,
        "atomic_covered_composition_ood_verified": s8_atomic_ood,
        "formal_gold": formal_gold,
    }


def run_s0_s9_dev_smoke(
    *,
    rois_jsonl_paths: list[Path],
    trusted_records_jsonl: Path,
    output_dir: Path,
    max_pairs: int = 8,
    include_registry_evidence_pairs: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus = load_dev_semantic_corpus(_WP3)

    pairs: list[dict[str, Any]] = []
    for p in rois_jsonl_paths:
        pairs.extend(load_evidence_pairs_from_rois(p))
    seen_ids: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for pr in pairs:
        if pr["pair_id"] in seen_ids:
            continue
        seen_ids.add(pr["pair_id"])
        deduped.append(pr)
    pairs = deduped

    if include_registry_evidence_pairs:
        for pr in load_evidence_pairs_from_trusted_registry(trusted_records_jsonl):
            if pr["pair_id"] not in seen_ids:
                pairs.append(pr)
                seen_ids.add(pr["pair_id"])
            else:
                # Prefer registry hashes for pairs already seen from ROI when merging
                for i, existing in enumerate(pairs):
                    if existing["pair_id"] == pr["pair_id"]:
                        # Keep ROI paths for equivalence audit; attach registry twin
                        pairs[i] = {
                            **existing,
                            "registry_twin": {
                                "clip_sha256": pr["clip_sha256"],
                                "clip_paths": pr["clip_paths"],
                            },
                        }
                        break

    trusted = load_trusted_claims(trusted_records_jsonl)
    with_sem = []
    without = []
    for p in pairs:
        # Prefer pairs that have corpus attrs or identity claims
        has_claim = any(c.get("pair_id") == p["pair_id"] for c in trusted.values())
        if has_claim:
            with_sem.append(p)
        else:
            without.append(p)
    ordered = with_sem + without
    pairs = ordered[: max(0, max_pairs)]

    results = [
        process_evidence_pair(
            pair,
            trusted_records_jsonl=trusted_records_jsonl,
            corpus=corpus,
            repo_root=_REPO,
        )
        for pair in pairs
    ]

    def _rate(gate_key: str) -> dict[str, Any]:
        n = len(results)
        k = sum(
            1
            for r in results
            if (r.get("scientific_gates") or {}).get(gate_key)
        )
        return {"numerator": k, "denominator": n, "rate": (k / n) if n else 0.0}

    class_counts: dict[str, int] = defaultdict(int)
    exit_counts: dict[str, int] = defaultdict(int)
    for r in results:
        class_counts[r.get("classification") or "UNKNOWN"] += 1
        exit_counts[r.get("exit") or "UNKNOWN"] += 1

    report = {
        "schema": "s0_s9_dev_smoke_report_v2",
        "built_utc": _utc(),
        "production_entry": PRODUCTION_ENTRY,
        "n_pairs": len(results),
        "rois_sources": [str(p) for p in rois_jsonl_paths],
        "classification_counts": dict(class_counts),
        "exit_counts": dict(exit_counts),
        "pipeline_engineering_completion": {
            "wired_into_formal_batch_entry": True,
            "unified_io_contract": True,
            "semantic_fact_adapter": True,
            "legacy_qa_draft_bypassed_on_this_path": True,
            "pairs_processed_end_to_end": len(results),
            "production_closed_loop_scientific_claimed": False,
        },
        "scientific_rates": {
            "evidence_manifest_complete": _rate("evidence_manifest_complete"),
            "media_hash_reverified": _rate("media_hash_reverified"),
            "semantic_facts_available": _rate("semantic_facts_available"),
            "human_relation_certified": _rate("human_relation_certified"),
            "relation_candidates_verified": _rate("relation_candidates_verified"),
            "qa_drafts_generated": _rate("qa_drafts_generated"),
            "program_graph_semantic_validation": _rate(
                "program_graph_semantic_validation"
            ),
            "program_execution_verified": _rate("program_execution_verified"),
            "structural_necessity_verified": _rate("structural_necessity_verified"),
            "model_necessity_run": _rate("model_necessity_run"),
            "atomic_covered_composition_ood_verified": _rate(
                "atomic_covered_composition_ood_verified"
            ),
            "formal_gold": _rate("formal_gold"),
        },
        "failures": [
            {
                "pair_id": r.get("pair_id"),
                "exit": r.get("exit"),
                "failure_reason": r.get("failure_reason"),
                "classification": r.get("classification"),
            }
            for r in results
            if r.get("exit") != "FULL_PATH"
        ],
        "full_path_pairs": [
            r.get("pair_id") for r in results if r.get("exit") == "FULL_PATH"
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
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results)
        + ("\n" if results else ""),
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
    # Media audit extract
    media_audits = [
        {
            "pair_id": r.get("pair_id"),
            "flags": (r.get("evidence") or {}).get("flags"),
            "media_equivalence": (r.get("evidence") or {}).get("media_equivalence"),
        }
        for r in results
    ]
    (output_dir / "MEDIA_HASH_AUDIT.json").write_text(
        json.dumps(
            {"schema": "media_hash_audit_batch_v1", "items": media_audits},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report
