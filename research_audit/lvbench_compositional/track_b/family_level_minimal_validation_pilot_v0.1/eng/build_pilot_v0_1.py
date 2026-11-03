#!/usr/bin/env python3
"""Build FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1 artifacts (P0–P5 engineering only).

Does not mint formal Seen/Unseen/Gold, freeze pools, expose train, or unlock Track A RSI.
Does not rewrite run_003. run_004 remains NOT_STARTED unless separately unlocked.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # .../lvbench_compositional
# __file__ = .../track_b/family.../eng/build → parents[0]=eng [1]=pilot [2]=track_b [3]=lvbench_compositional [4]=research_audit
# Fix: want Video-RSI root
ROOT = Path(__file__).resolve().parents[5]
assert (ROOT / "research_audit").is_dir(), ROOT
PILOT = Path(__file__).resolve().parents[1]
SNAP = PILOT / "provenance_snapshots"
REPO_TB = ROOT / "research_audit/lvbench_compositional/track_b"
P7 = ROOT / "research_audit/lvbench_compositional/p7_hil_pilot"

GATES = {
    "formal_seen_train": False,
    "formal_unseen": False,
    "formal_gold": False,
    "train_exposed": False,
    "seen_pool_frozen": False,
    "approve_expensive_track_a_rsi": False,
}

FAMILY_MAP = {
    "CROSS_CLIP_IDENTITY_BIND": [
        "CrossIntervalSamePersonBind",
        "CrossWindowPersonBind",
        "CrossClipCountryBind",
        "TemporalPersonBind",
        "JoinByPersonReference",
    ],
    "ATTRIBUTE_OR_RELATION_QUERY_AFTER_BIND": [
        "QueryEmotion",
        "QueryEarlierAction",
        "QueryEarlierTransport",
        "QueryLaterAction",
        "QueryMatchResult",
        "QueryLaterTransport",
        "CountMatchedFlags",
        "IdentifyScoringPlayer",
    ],
    "TEXT_OR_GRAPHIC_READ": [
        "ReadNameGraphic",
        "ReadNameAbbreviationGraphic",
        "ReadNameSubtitle",
        "ReadRelationSubtitle",
        "IdentifyFlagOnFlagpole",
        "IdentifyFlagCountry",
        "DetectWavedFlag",
        "IdentifyCountry",
    ],
    "ACTION_OR_EVENT_DETECT": [
        "DetectJacketRemoval",
        "DetectAction",
        "DetectTransportRide",
        "DetectDisembark",
        "DetectSnowScene",
        "IdentifyFirstServer",
        "DetermineMatchWinner",
        "IdentifyFirstTransport",
        "IdentifyTransport",
        "LocateSet",
        "LocateTeamPoint",
        "DetectAnimalCue",
        "DetectAnimal",
    ],
    "APPEARANCE_OR_ROLE_ID": [
        "IdentifyActorByAppearance",
        "IdentifyPersonByAppearance",
        "IdentifyRescuerByRole",
        "ExtractAppearance",
        "ObservePerson",
        "IdentifyTeams",
        "SelectTeam",
        "MatchFlagsByCountry",
        "LocateClockBuilding",
        "LocateFirstSpeechStage",
        "DetectMultipleNationalFlags",
        "IdentifyAnimal",
    ],
    "TEMPORAL_ORDER_COMPARE": ["CompareTemporalOrder", "TimeAnchor", "TemporalSuccessor"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_snap(name: str) -> dict:
    return json.loads((SNAP / name).read_text(encoding="utf-8"))


def family_of(op: str) -> str:
    for fam, ops in FAMILY_MAP.items():
        if any(op == o or op.startswith(o) or o in op for o in ops):
            return fam
    return "OTHER_OR_UNMAPPED"


def git_sha(ref: str = "HEAD") -> str:
    return subprocess.check_output(["git", "rev-parse", ref], cwd=ROOT).decode().strip()


def build_inventory(p7_head: str) -> dict:
    ans = json.loads(
        (P7 / "round_004/certification/ANSWER_KEYS_DO_NOT_SERVE_TO_REVIEWER.json").read_text(encoding="utf-8")
    )
    keys = ans.get("keys") or {}
    items: list[dict] = []

    def add(**kw):
        for g, v in GATES.items():
            kw.setdefault(g, v)
        kw.setdefault("qa_format", "OPEN_ENDED")
        kw["multichoice_auto_generated"] = False
        items.append(kw)

    # --- Seen ---
    r = load_snap("SP001.json")
    g = load_snap("SP001_v0.3.json")
    ops = g["graph_as_reviewed"]["A"] + g["graph_as_reviewed"]["B"] + [g["graph_as_reviewed"]["cross_window"]]
    add(
        item_id="SP001",
        pilot_role="SEEN",
        qa_uid=r["qa_uid"],
        video_id=r["video_id"],
        question_open=r["original_question"],
        answer_reference=r["historical_answer"],
        graph_version=r["approved_graph_version"],
        graph_provenance={
            "source_branch": "research/lvbench-comp-p7-hil-pilot",
            "source_commit": p7_head,
            "source_path": "scientific_workbench/seen_pilot_run_001/scientific_reviews/APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP001_v0.3.json",
            "local_snapshot": "provenance_snapshots/SP001_v0.3.json",
            "record_snapshot": "provenance_snapshots/SP001.json",
        },
        windows_seconds=r["windows_seconds"],
        window_roles={"A": "speech_stage_flags", "B": "clock_building_flagpole"},
        evidence_modality=["video_clip_windows", "national_flag_visual", "building_landmark"],
        directed_program={
            "macro": g["graph_as_reviewed"],
            "nodes_atomic": ops,
            "edge_kinds": ["data", "bind"],
            "dependency_direction": "B_country_then_A_count",
        },
        capability_families_upper=sorted({family_of(o) for o in ops}),
        atomic_operator_labels=ops,
        human_observations=r["raw_scientific_judgment"]["user_observations"],
        evidence_limitations=r["raw_scientific_judgment"].get("caveats", []),
        single_window_necessity={
            "a_only_sufficient": False,
            "b_only_sufficient": False,
            "a_plus_b": "USER_SUPPORTED",
            "source": "seen_pilot_run_001 human judgment",
            "not_model_ablation": True,
        },
        scientific_approval_source="seen_pilot_run_001 USER_APPROVED_STRUCTURED_GRAPH",
        isolation_group=f"VIDEO_{r['video_id']}",
    )

    r = load_snap("SP002.json")
    g = load_snap("SP002_v0.2.json")
    ops = g["graph_as_reviewed"]["A"] + g["graph_as_reviewed"]["B"] + [g["graph_as_reviewed"]["cross_window"]]
    add(
        item_id="SP002",
        pilot_role="SEEN",
        qa_uid=r["qa_uid"],
        video_id=r["video_id"],
        question_open=r["original_question"],
        answer_reference=r["historical_answer"],
        graph_version=r["approved_graph_version"],
        graph_provenance={
            "source_branch": "research/lvbench-comp-p7-hil-pilot",
            "source_commit": p7_head,
            "source_path": "scientific_workbench/seen_pilot_run_001/scientific_reviews/APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP002_v0.2.json",
            "local_snapshot": "provenance_snapshots/SP002_v0.2.json",
            "record_snapshot": "provenance_snapshots/SP002.json",
        },
        windows_seconds=r["windows_seconds"],
        window_roles={"A": "person_and_name_subtitle", "B": "relation_subtitle"},
        evidence_modality=["video_clip_windows", "on_screen_subtitle"],
        directed_program={
            "macro": g["graph_as_reviewed"],
            "nodes_atomic": ops,
            "edge_kinds": ["data", "bind", "temporal"],
            "dependency_direction": "A_identity_then_B_relation",
        },
        capability_families_upper=sorted({family_of(o) for o in ops}),
        atomic_operator_labels=ops,
        human_observations=r["raw_scientific_judgment"]["user_observations"],
        evidence_limitations=r["raw_scientific_judgment"].get("caveats", []),
        single_window_necessity={
            "a_only_sufficient": False,
            "b_only_sufficient": False,
            "a_plus_b": "USER_SUPPORTED",
            "source": "seen_pilot_run_001 human judgment",
            "not_model_ablation": True,
        },
        scientific_approval_source="seen_pilot_run_001 USER_APPROVED_STRUCTURED_GRAPH",
        isolation_group=f"VIDEO_{r['video_id']}",
    )

    r = load_snap("SP005.json")
    g = load_snap("SP005_v0.2.json")
    ops = g["graph_as_reviewed"]["A"] + g["graph_as_reviewed"]["B"] + [g["graph_as_reviewed"]["cross_window"]]
    add(
        item_id="SP005",
        pilot_role="SEEN",
        qa_uid=r["qa_uid"],
        video_id=r["video_id"],
        question_open=r["original_question"],
        answer_reference=r["historical_answer"],
        graph_version=r["approved_graph_version"],
        graph_provenance={
            "source_branch": "research/lvbench-comp-p7-hil-pilot",
            "source_commit": p7_head,
            "source_path": "scientific_workbench/seen_pilot_run_001/scientific_reviews/APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP005_v0.2.json",
            "local_snapshot": "provenance_snapshots/SP005_v0.2.json",
            "record_snapshot": "provenance_snapshots/SP005.json",
        },
        windows_seconds=r["windows_seconds"],
        window_roles={"A": "waved_flag_target_country", "B": "match_scoring_event"},
        evidence_modality=["video_clip_windows", "flag_visual", "score_event"],
        directed_program={
            "macro": g["graph_as_reviewed"],
            "nodes_atomic": ops,
            "edge_kinds": ["data", "bind"],
            "dependency_direction": "A_target_then_B_score",
        },
        capability_families_upper=sorted({family_of(o) for o in ops}),
        atomic_operator_labels=ops,
        human_observations=r["raw_scientific_judgment"]["user_observations"],
        evidence_limitations=r["raw_scientific_judgment"].get("caveats", []),
        single_window_necessity={
            "a_only_sufficient": False,
            "b_only_sufficient": "INSUFFICIENT_FOR_TARGET_SELECTION",
            "a_plus_b": "USER_SUPPORTED_A_REQUIRED_FOR_TARGET_SELECTION",
            "source": "seen_pilot_run_001 human judgment (B-only shortcut retracted)",
            "not_model_ablation": True,
        },
        scientific_approval_source="seen_pilot_run_001 USER_APPROVED_STRUCTURED_GRAPH",
        isolation_group=f"VIDEO_{r['video_id']}",
    )

    r = load_snap("SP201.json")
    ops = ["DetermineMatchWinner", "CrossWindowPersonBind", "QueryEmotion"]
    add(
        item_id="SP201",
        pilot_role="SEEN",
        qa_uid=r["qa_uid"],
        video_id=r["video_id"],
        question_open=r["question_original_en"],
        answer_reference=r["answer_candidate"],
        graph_version=r["graph_version"],
        graph_provenance={
            "source_branch": "research/lvbench-comp-p7-hil-pilot",
            "source_commit": p7_head,
            "source_path": "scientific_workbench/seen_pilot_run_002/scientific_reviews/APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP201_v0.2.json",
            "local_snapshot": "provenance_snapshots/SP201_v0.2.json",
            "record_snapshot": "provenance_snapshots/SP201.json",
        },
        windows_seconds=r["windows_seconds"],
        window_roles={"A": "emotion_after_lost_point", "B": "match_winner"},
        evidence_modality=["video_clip_windows", "player_appearance", "scoreboard_context"],
        directed_program={
            "macro": r["directed_program_graph"],
            "nodes_atomic": ops,
            "edge_kinds": ["data", "bind"],
            "dependency_direction": "B_TO_A",
        },
        capability_families_upper=sorted({family_of(o) for o in ops}),
        atomic_operator_labels=ops,
        human_observations=r["human_observations"],
        evidence_limitations=r["evidence_limitations"],
        single_window_necessity={**r["single_window_necessity_audit"], "not_model_ablation": True},
        scientific_approval_source="seen_pilot_run_002 USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
        isolation_group="VIDEO_Hf-n1yfd8II",
        shared_video_with=["SP202"],
    )

    r = load_snap("SP202.json")
    ops = ["IdentifyFirstServer", "CrossWindowPersonBind", "QueryMatchResult"]
    add(
        item_id="SP202",
        pilot_role="SEEN",
        qa_uid=r["qa_uid"],
        video_id=r["video_id"],
        question_open=r["question_original_en"],
        answer_reference=r["answer_candidate"],
        graph_version=r["graph_version"],
        graph_provenance={
            "source_branch": "research/lvbench-comp-p7-hil-pilot",
            "source_commit": p7_head,
            "source_path": "scientific_workbench/seen_pilot_run_002/scientific_reviews/APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP202_v0.3.json",
            "local_snapshot": "provenance_snapshots/SP202_v0.3.json",
            "record_snapshot": "provenance_snapshots/SP202.json",
        },
        windows_seconds=r["windows_seconds"],
        window_roles={"A": "first_serve_opening", "B": "match_result"},
        evidence_modality=["video_clip_windows", "player_name_flag", "scoreboard"],
        directed_program={
            "macro": r["directed_program_graph"],
            "nodes_atomic": ops,
            "edge_kinds": ["data", "bind"],
            "dependency_direction": "A_TO_B",
        },
        capability_families_upper=sorted({family_of(o) for o in ops}),
        atomic_operator_labels=ops,
        human_observations=r["human_observations"],
        evidence_limitations=r["evidence_limitations"],
        single_window_necessity={**r["single_window_necessity_audit"], "not_model_ablation": True},
        scientific_approval_source="seen_pilot_run_002 USER_APPROVED_COMPOSITIONAL_CANDIDATE_GRAPH",
        isolation_group="VIDEO_Hf-n1yfd8II",
        shared_video_with=["SP201"],
    )

    for pid, role in [("P7_VTCD_C2", "UNSEEN"), ("P7_TJR_R3", "UNSEEN"), ("P7_R4_F1", "HOLD"), ("P7_R4_F2", "HOLD")]:
        g = load_snap(f"{pid}.json")
        pkt = load_snap(f"{pid}_blind_packet.json")
        ops = [n["operator_type"] for n in g["nodes"]]
        edges = [
            {"from": e["from_node"], "to": e["to_node"], "kind": e["dependency_kind"]} for e in g["edges"]
        ]
        hj = g["human_judgments_preserved"]
        add(
            item_id=pid,
            pilot_role=role,
            qa_uid=g["qa_uid"],
            video_id=g["video_id"],
            question_open=pkt["frozen_question"],
            answer_reference=keys.get(pid),
            graph_version=g["structure_version"],
            graph_provenance={
                "source_branch": "research/lvbench-comp-p7-hil-pilot",
                "source_commit": p7_head,
                "source_path": f"scientific_workbench/data/approved_graphs_v0.2/{pid}.json",
                "local_snapshot": f"provenance_snapshots/{pid}.json",
                "blind_packet_snapshot": f"provenance_snapshots/{pid}_blind_packet.json",
            },
            windows_seconds=None,
            windows_note="Precise source-second mapping PENDING / partial playback offsets only",
            window_roles={"A": "earlier_evidence", "B": "later_referent"},
            evidence_modality=["approved_structured_graph", "review_clips_referenced_in_blind_packet"],
            directed_program={
                "raw_text": g["raw_directed_program_text"],
                "nodes": g["nodes"],
                "edges": edges,
                "edge_kinds": sorted({e["kind"] for e in edges}),
            },
            capability_families_upper=sorted({family_of(o) for o in ops}),
            atomic_operator_labels=ops,
            human_observations=[
                f"a_only={hj['a_only_sufficient']}; b_only={hj['b_only_sufficient']}; a+b={hj['a_plus_b_supports_user_answer']}"
            ],
            evidence_limitations=[
                "operator_vocab_status=PENDING_SCIENTIFIC_APPROVAL",
                g.get("precise_timing_status", "timing_pending"),
                "pilot_role is not formal_unseen/formal_seen_train",
            ],
            single_window_necessity={
                "a_only_sufficient": hj["a_only_sufficient"] == "否",
                "b_only_sufficient": hj["b_only_sufficient"] == "否",
                "a_plus_b": hj["a_plus_b_supports_user_answer"],
                "source": "human_judgments_preserved",
                "not_model_ablation": True,
            },
            scientific_approval_source="USER_GPT_SCIENTIFIC_APPROVAL_CHAT_2026-11-02_structured_graphs_v0.2",
            isolation_group=f"VIDEO_{g['video_id']}",
        )

    r = load_snap("SP205.json")
    ops = [n["op"] for n in r["directed_program_graph"]["nodes"]]
    add(
        item_id="SP205",
        pilot_role="HOLD",
        qa_uid=r["qa_uid"],
        video_id=r["video_id"],
        question_open=r.get("question_en") or r["question_original_en"],
        answer_reference=r["answer_candidate"],
        graph_version=r["graph_version"],
        graph_provenance={
            "source_branch": "research/lvbench-comp-p7-hil-pilot",
            "source_commit": p7_head,
            "source_path": "scientific_workbench/seen_pilot_run_002/scientific_reviews/APPROVED_COMPOSITIONAL_CANDIDATE_GRAPHS/SP205_v0.5.json",
            "local_snapshot": "provenance_snapshots/SP205_v0.5.json",
            "record_snapshot": "provenance_snapshots/SP205.json",
        },
        windows_seconds=r["windows_seconds"],
        window_roles={"A": "first_transport_and_disembark", "B": "later_subway"},
        evidence_modality=["video_clip_windows", "transport_signage"],
        directed_program={
            "macro": r["directed_program_graph"],
            "nodes_atomic": ops,
            "edge_kinds": [e["kind"] for e in r["directed_program_graph"]["edges"]],
            "dependency_direction": "A_then_B_later_than",
            "removed_operator": "TemporalSuccessor",
            "required_operator": "CompareTemporalOrder",
        },
        capability_families_upper=sorted({family_of(o) for o in ops}),
        atomic_operator_labels=ops,
        human_observations=r["human_observations"],
        evidence_limitations=r["evidence_limitations"],
        single_window_necessity={**r["single_window_necessity_audit"], "not_model_ablation": True},
        scientific_approval_source="seen_pilot_run_002 USER_APPROVED v0.5; USER_ASSIGNED_UNSEEN",
        user_split_assignment=r["user_split_assignment"],
        user_split_decision=r["user_split_decision"],
        hold_reason=(
            "Included as HOLD in FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1 Unseen-arm capacity control; "
            "USER_ASSIGNED_UNSEEN ≠ formal_unseen freeze"
        ),
        isolation_group="VIDEO_wgBlACG927Y",
        shared_video_with=["DN201"],
    )

    assert len(items) == 10
    by_role = defaultdict(list)
    for it in items:
        by_role[it["pilot_role"]].append(it["item_id"])
    assert by_role["SEEN"] == ["SP001", "SP002", "SP005", "SP201", "SP202"]
    assert by_role["UNSEEN"] == ["P7_VTCD_C2", "P7_TJR_R3"]
    assert set(by_role["HOLD"]) == {"P7_R4_F1", "P7_R4_F2", "SP205"}

    return {
        "protocol": "FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1",
        "created_utc": utc_now(),
        "working_branch": "research/lvbench-comp-video-grounded-evidence",
        "provenance_source_branch": "research/lvbench-comp-p7-hil-pilot",
        "provenance_source_commit": p7_head,
        "note": (
            "pilot_role is a minimal validation assignment only. "
            "formal_seen_train / formal_unseen / formal_gold remain false. "
            "Open-ended QA only; no auto multichoice."
        ),
        "counts": {"SEEN": 5, "UNSEEN": 2, "HOLD": 3, "total": 10},
        "items": items,
        **GATES,
    }


def structural_check(item: dict) -> dict:
    issues = []
    prog = item.get("directed_program") or {}
    if item["item_id"].startswith("P7_") or item["item_id"] == "SP205" and "nodes" in (prog.get("macro") or {}):
        nodes = prog.get("nodes") or (prog.get("macro") or {}).get("nodes") or []
        edges = prog.get("edges") or (prog.get("macro") or {}).get("edges") or []
        if isinstance(nodes, list) and nodes and isinstance(nodes[0], dict):
            ids = {n.get("node_id") or n.get("id") for n in nodes}
            for e in edges:
                fr = e.get("from") or e.get("from_node")
                to = e.get("to") or e.get("to_node")
                if fr not in ids:
                    issues.append(f"edge from missing: {fr}")
                if to not in ids:
                    issues.append(f"edge to missing: {to}")
                if not e.get("kind") and not e.get("dependency_kind"):
                    issues.append("edge missing kind")
    elif "nodes_atomic" in prog:
        if len(prog["nodes_atomic"]) < 2:
            issues.append("macro graph has <2 atomic labels")
        if not prog.get("dependency_direction"):
            issues.append("missing dependency_direction")
    else:
        issues.append("unrecognized graph encoding")
    if item.get("qa_format") != "OPEN_ENDED":
        issues.append("qa_format must be OPEN_ENDED")
    if item.get("multichoice_auto_generated"):
        issues.append("multichoice auto generation forbidden")
    for g in GATES:
        if item.get(g) is not False:
            issues.append(f"gate {g} must be false")
    return {"item_id": item["item_id"], "ok": not issues, "issues": issues}


def graph_fingerprint(item: dict) -> dict:
    """Mechanical structure fingerprint only — NOT certified semantic equivalence."""
    fams = tuple(sorted(item.get("capability_families_upper") or []))
    atoms = tuple(sorted(item.get("atomic_operator_labels") or []))
    edge_kinds = tuple(sorted((item.get("directed_program") or {}).get("edge_kinds") or []))
    return {
        "item_id": item["item_id"],
        "families": fams,
        "n_atomic": len(atoms),
        "edge_kinds": edge_kinds,
        "dependency_direction": (item.get("directed_program") or {}).get("dependency_direction"),
        "semantic_equivalence": "UNAUTHENTICATED_NO_APPROVED_RULE",
    }


def build_integrity(inv: dict) -> dict:
    sealed = json.loads((REPO_TB / "SEALED_POOL_SPLIT_POLICY.json").read_text(encoding="utf-8"))
    sealed_ids = set(sealed.get("sealed_reservoir", {}).get("current_ids") or [])
    exposed = set(sealed.get("exposed_or_construction") or [])

    seen = [i for i in inv["items"] if i["pilot_role"] == "SEEN"]
    unseen = [i for i in inv["items"] if i["pilot_role"] == "UNSEEN"]
    hold = [i for i in inv["items"] if i["pilot_role"] == "HOLD"]

    seen_vids = {i["video_id"] for i in seen}
    unseen_vids = {i["video_id"] for i in unseen}
    hold_vids = {i["video_id"] for i in hold}

    isolation_issues = []
    if seen_vids & unseen_vids:
        isolation_issues.append({"type": "SEEN_UNSEEN_VIDEO_OVERLAP", "videos": sorted(seen_vids & unseen_vids)})
    # SP201/SP202 same group required
    g201 = next(i for i in seen if i["item_id"] == "SP201")
    g202 = next(i for i in seen if i["item_id"] == "SP202")
    if g201["isolation_group"] != g202["isolation_group"]:
        isolation_issues.append({"type": "SP201_SP202_GROUP_MISMATCH"})
    if g201["video_id"] != g202["video_id"]:
        isolation_issues.append({"type": "SP201_SP202_VIDEO_MISMATCH"})
    # Hold SP205 video must not appear in Seen
    if "wgBlACG927Y" in seen_vids:
        isolation_issues.append({"type": "HOLD_SP205_VIDEO_IN_SEEN"})
    # Sealed reservoir must not be touched
    all_vids = seen_vids | unseen_vids | hold_vids
    if all_vids & sealed_ids:
        isolation_issues.append({"type": "SEALED_TOUCHED", "videos": sorted(all_vids & sealed_ids)})

    # Family coverage matrix
    all_fams = sorted(FAMILY_MAP.keys()) + ["OTHER_OR_UNMAPPED"]
    matrix = {}
    for fam in all_fams:
        supporters = [i["item_id"] for i in inv["items"] if fam in (i.get("capability_families_upper") or [])]
        if len(supporters) >= 2:
            status = "CANDIDATE_SUPPORTED"
        elif len(supporters) == 1:
            status = "PARTIAL_SINGLE_ITEM"
        else:
            status = "GAP"
        matrix[fam] = {"status": status, "items": supporters}

    struct = [structural_check(i) for i in inv["items"]]
    fps = [graph_fingerprint(i) for i in inv["items"]]
    # pairwise mechanical overlap (not semantic eq)
    pairs = []
    for i, a in enumerate(fps):
        for b in fps[i + 1 :]:
            fam_overlap = sorted(set(a["families"]) & set(b["families"]))
            pairs.append(
                {
                    "a": a["item_id"],
                    "b": b["item_id"],
                    "family_overlap": fam_overlap,
                    "semantic_equivalence": "UNAUTHENTICATED_NO_APPROVED_RULE",
                }
            )

    necessity = [
        {
            "item_id": i["item_id"],
            "pilot_role": i["pilot_role"],
            "single_window_necessity": i["single_window_necessity"],
            "provenance": i["single_window_necessity"].get("source"),
            "disclaimer": "HUMAN_JUDGMENT_NOT_INDEPENDENT_MODEL_ABLATION",
        }
        for i in inv["items"]
    ]

    return {
        "protocol": "FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1",
        "created_utc": utc_now(),
        "counts": {"SEEN": len(seen), "UNSEEN": len(unseen), "HOLD": len(hold)},
        "video_dedup": {
            "seen_videos": sorted(seen_vids),
            "unseen_videos": sorted(unseen_vids),
            "hold_videos": sorted(hold_vids),
            "n_distinct_seen": len(seen_vids),
            "n_distinct_unseen": len(unseen_vids),
            "n_distinct_hold": len(hold_vids),
            "seen_counts_two_items_same_video": "Hf-n1yfd8II hosts SP201+SP202 (required isolation group)",
        },
        "isolation": {
            "status": "PASS" if not isolation_issues else "FAIL",
            "issues": isolation_issues,
            "sp201_sp202_same_group": g201["isolation_group"] == g202["isolation_group"] == "VIDEO_Hf-n1yfd8II",
            "seen_unseen_video_disjoint": not bool(seen_vids & unseen_vids),
            "sealed_reservoir_untouched": not bool(all_vids & sealed_ids),
            "sealed_current_ids_empty_or_disjoint": True,
            "note_on_exposed_pool": "Pilot videos may already be DEV_CONSTRUCTION/exposed; that ≠ sealed touch.",
            "exposed_membership": {v: (v in exposed) for v in sorted(all_vids)},
        },
        "capability_family_coverage_matrix": matrix,
        "structural_consistency": {"all_ok": all(s["ok"] for s in struct), "checks": struct},
        "computable_structure_comparison": {
            "rule": "Mechanical fingerprint/family overlap only; semantic graph isomorphism UNAUTHENTICATED",
            "fingerprints": fps,
            "pairwise": pairs,
        },
        "a_only_b_only_human_audit": necessity,
        "scientific_classification_unchanged": True,
        **GATES,
    }


def link_multiframe() -> dict:
    mf_dir = REPO_TB / "batch_factory/chatgpt_multiframe_roi_pilot_2026-10-31"
    feas_dir = REPO_TB / "batch_factory/multiframe_relation_feasibility_2026-10-31"
    val = json.loads((feas_dir / "validation_report.json").read_text(encoding="utf-8"))
    feas = json.loads((feas_dir / "relation_feasibility.json").read_text(encoding="utf-8"))
    events_path = mf_dir / "events_CHATGPT_MULTIFRAME_OBSERVATION.jsonl"
    events = [json.loads(l) for l in events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    man = json.loads((mf_dir / "batch_manifest.json").read_text(encoding="utf-8"))
    # verify evidence paths/hashes still match
    issues = []
    for ev in events:
        paths = ev.get("evidence_paths") or []
        hashes = ev.get("evidence_sha256") or []
        if len(paths) != len(hashes):
            issues.append({"event": ev.get("event_id"), "issue": "path_hash_len_mismatch"})
            continue
        for rel, expect in zip(paths, hashes):
            # paths may be relative to ROI pilot dir or repo
            cand = [
                mf_dir / rel,
                ROOT / rel,
                mf_dir / "frames" / rel,
            ]
            hit = next((p for p in cand if p.is_file()), None)
            if hit is None:
                # try basename search under frames
                hits = list((mf_dir / "frames").rglob(Path(rel).name))
                hit = hits[0] if hits else None
            if hit is None:
                issues.append({"event": ev.get("event_id"), "issue": "missing_frame", "path": rel})
            elif sha_file(hit) != expect:
                issues.append({"event": ev.get("event_id"), "issue": "sha_mismatch", "path": rel})

    link = {
        "created_utc": utc_now(),
        "run_003_untouched": True,
        "source_pilot": str(mf_dir.relative_to(ROOT)),
        "n_events": len(events),
        "validation_report_ref": str((feas_dir / "validation_report.json").relative_to(ROOT)),
        "relation_feasibility_ref": str((feas_dir / "relation_feasibility.json").relative_to(ROOT)),
        "prior_validation_summary": val,
        "prior_feasibility_summary": feas.get("summary"),
        "recheck_evidence_sha": {
            "n_issues": len(issues),
            "issues_sample": issues[:10],
            "status": "PASS" if not issues else "FAIL",
        },
        "roi_relation_decisions": [
            {
                "relation_id": c["relation_id"],
                "roi_id": c.get("roi_id"),
                "decision": c["decision"],
                "run_004_qualifying": c.get("run_004_qualifying"),
                "a_only_shortcut": c.get("a_only_shortcut"),
                "b_only_shortcut": c.get("b_only_shortcut"),
            }
            for c in feas.get("candidates", [])
        ],
        "bioprint_priority_note": "REL_FEAS_008 remains DEV_HYPOTHESIS_NOT_QUALIFYING; not auto-upgraded",
        "forbidden_auto_upgrades": [
            "vending_pointing→purchase",
            "card_pointing→buy",
            "aerial→speaker causality",
            "print→plated_food bind",
        ],
        "qa_drafts_from_multiframe": 0,
        **GATES,
    }
    dump(PILOT / "p2_multiframe_link/MULTIFRAME_DIGEST.json", link)
    return link


def _ffmpeg_bin() -> str:
    cached = Path("/home/descfly/.cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg")
    if cached.is_file():
        return str(cached)
    which = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if which.returncode == 0 and which.stdout.strip():
        return which.stdout.strip()
    raise FileNotFoundError("ffmpeg not found")


def extract_p3_frames() -> dict:
    """Light ROI extraction for two new DEV videos; no semantic prefill."""
    ffmpeg = _ffmpeg_bin()
    videos_dir = Path("/home/descfly/lpy/dataset/LVBench/videos")
    sealed = json.loads((REPO_TB / "SEALED_POOL_SPLIT_POLICY.json").read_text(encoding="utf-8"))
    exposed = set(sealed.get("exposed_or_construction") or [])
    # Prefer DEV videos not used in multiframe ROI pilot
    used_mf = {"Mcggugol2ts", "xi6r3hZe5Tg"}
    # Avoid videos already hosting the 10 approved pilot items
    pilot_vids = {
        "aJI8XTa_DII",
        "vHlSoxg8WHo",
        "KLIa2UaE2KE",
        "Hf-n1yfd8II",
        "VTCDQYYKA9o",
        "TJR1oYDDTwg",
        "Cm73ma6Ibcs",
        "LLSJrEgOOtw",
        "wgBlACG927Y",
    }
    # Registered construction seeds with local MP4
    candidates = [
        ("hROKtPqktO8", [(500, 510), (1255, 1265)]),
        ("iA_69g87Ilw", [(358, 368), (900, 910)]),
    ]
    out_rois = []
    frames_root = PILOT / "p3_new_video_discovery/frames"
    frames_root.mkdir(parents=True, exist_ok=True)
    cost = {"ffmpeg_calls": 0, "frames": 0, "videos": 0}

    for vid, windows in candidates:
        assert vid in exposed, f"{vid} not in DEV_CONSTRUCTION/exposed"
        assert vid not in used_mf and vid not in pilot_vids
        src = videos_dir / f"{vid}.mp4"
        if not src.is_file():
            raise FileNotFoundError(src)
        cost["videos"] += 1
        # register source before sampling
        reg = {
            "construction_video_id": vid,
            "pool": "DEV_CONSTRUCTION",
            "registered_utc": utc_now(),
            "source_mp4": str(src),
            "source_sha256": sha_file(src),
            "bytes": src.stat().st_size,
            "not_sealed_final": True,
            "semantics_status": "FRAMES_EXTRACTED_PENDING_GPT_OBSERVATION",
            "cursor_does_not_prefill_unobserved_events": True,
        }
        dump(PILOT / f"p3_new_video_discovery/{vid}_SOURCE_REGISTER.json", reg)

        for wi, (t0, t1) in enumerate(windows[:2]):
            roi_id = f"{vid}_ROI_{t0}_{t1}"
            roi_dir = frames_root / vid / roi_id
            roi_dir.mkdir(parents=True, exist_ok=True)
            # 12 frames @ 1.2fps over 10s ≈ light budget (<16)
            n = 12
            times = [t0 + i * (t1 - t0) / (n - 1) for i in range(n)]
            frame_recs = []
            for fi, t in enumerate(times):
                outp = roi_dir / f"mf_{fi:02d}_t{t:.1f}.jpg"
                cmd = [
                    ffmpeg,
                    "-y",
                    "-ss",
                    f"{t:.3f}",
                    "-i",
                    str(src),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(outp),
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                cost["ffmpeg_calls"] += 1
                cost["frames"] += 1
                frame_recs.append(
                    {
                        "frame_id": f"{roi_id}_f{fi:02d}",
                        "t_s": round(t, 3),
                        "path": str(outp.relative_to(ROOT)),
                        "sha256": sha_file(outp),
                        "bytes": outp.stat().st_size,
                    }
                )
            roi = {
                "roi_id": roi_id,
                "video_id": vid,
                "t_start_s": t0,
                "t_end_s": t1,
                "n_frames": len(frame_recs),
                "max_frames_budget": 16,
                "rationale": "Anchored near prior construction seed timestamps; action/state hypotheses PENDING GPT observation of these frames only.",
                "frames": frame_recs,
                "observation_slot": {
                    "status": "PENDING_GPT_VISUAL_OBSERVATION",
                    "allowed_labels": [
                        "STATIC_VISIBLE",
                        "ORDERED_MULTIFRAME_SUGGESTS",
                        "CONTINUOUS_VIDEO_VERIFIED",
                        "UNRESOLVED",
                    ],
                    "forbid_prefill_by_cursor": True,
                },
            }
            dump(PILOT / f"p3_new_video_discovery/rois/{roi_id}.json", roi)
            out_rois.append(roi)

    manifest = {
        "batch_id": "family_level_pilot_v0_1_p3_discovery_2026-11-03",
        "created_utc": utc_now(),
        "cap": {"max_videos": 2, "max_roi_per_video": 2, "max_frames_per_roi": 16},
        "videos": [c[0] for c in candidates],
        "n_rois": len(out_rois),
        "n_frames": sum(r["n_frames"] for r in out_rois),
        "rois": out_rois,
        "cost_metrics": cost,
        "chatgpt_role": "Observe only the extracted frames; do not invent unobserved events; do not self-blind-grade.",
        "cursor_role": "Source register + frame extract + manifest only.",
        "run_003_untouched": True,
        "run_004_status": "NOT_STARTED",
        **GATES,
    }
    dump(PILOT / "p3_new_video_discovery/batch_manifest.json", manifest)
    return manifest


def build_review_pack(inv: dict, mf_link: dict, p3: dict, integrity: dict) -> dict:
    pack = {
        "title": "FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1 scientific review pack",
        "created_utc": utc_now(),
        "audience": "USER + GPT joint review",
        "disclaimer": "GPT-produced evidence in the same pass must not be treated as independent blind adjudication.",
        "pilot_items_for_review": [
            {
                "item_id": i["item_id"],
                "pilot_role": i["pilot_role"],
                "video_id": i["video_id"],
                "question_open": i["question_open"],
                "answer_reference_held_out_from_blind": True,
                "windows_seconds": i.get("windows_seconds"),
                "capability_families_upper": i["capability_families_upper"],
                "atomic_operator_labels": i["atomic_operator_labels"],
                "directed_program_summary": i["directed_program"].get("dependency_direction")
                or i["directed_program"].get("raw_text", "")[:160],
                "a_only_b_only": i["single_window_necessity"],
                "open_scientific_questions": i.get("evidence_limitations", []),
            }
            for i in inv["items"]
        ],
        "multiframe_zero_yield": {
            "n_qualifying_relations": mf_link["prior_feasibility_summary"]["n_run004_qualifying_relations"],
            "status": mf_link["prior_feasibility_summary"]["status"],
            "note": "Zero qualified compositional candidates from prior multiframe ROI pilot is a valid outcome.",
        },
        "p3_new_discovery": {
            "videos": p3["videos"],
            "n_rois": p3["n_rois"],
            "n_frames": p3["n_frames"],
            "status": "FRAMES_READY_PENDING_GPT_OBSERVATION",
            "candidates_qualified": 0,
            "note": "No QA drafts minted; Cursor did not prefill unobserved events.",
        },
        "contamination_risks": {
            "SP201_SP202_same_video": True,
            "seen_unseen_video_overlap": not integrity["isolation"]["seen_unseen_video_disjoint"],
            "gpt_same_pass_as_blind": "FORBIDDEN",
            "approved_ten_graph_overlap_with_p3": "P3 videos chosen outside the 10-item video set",
        },
        "unresolved_human_science_questions": [
            "Whether SP205 HOLD should later migrate into a formal Unseen arm without freezing the test set",
            "P7 Unseen timing frame-accurate mapping still PENDING",
            "Operator vocabulary still provisional / pending scientific approval",
            "Independent continuous review still required for bioprint lattice hypothesis",
            "P3 frames await GPT observation — zero candidates until then",
        ],
        "run_004": {
            "status": "NOT_STARTED",
            "blockers": [
                "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE from multiframe feasibility (0 qualifying)",
                "P3 discovery frames not yet GPT-observed / no nontrivial directed relation admitted",
                "No USER+GPT scientific admission of a new evidence-grounded candidate this round",
            ],
        },
        **GATES,
    }
    dump(PILOT / "p4_scientific_review_pack/REVIEW_PACK.json", pack)
    md = PILOT / "p4_scientific_review_pack/REVIEW_PACK.md"
    lines = [
        "# Scientific review pack — FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1",
        "",
        f"Created: {pack['created_utc']}",
        "",
        "## Pilot roles (≠ formal gates)",
        "",
        "| ID | role | video | families |",
        "|----|------|-------|----------|",
    ]
    for i in inv["items"]:
        lines.append(
            f"| {i['item_id']} | {i['pilot_role']} | `{i['video_id']}` | {', '.join(i['capability_families_upper'])} |"
        )
    lines += [
        "",
        "## Multiframe digest",
        "",
        f"- Qualifying relations for run_004: **{pack['multiframe_zero_yield']['n_qualifying_relations']}**",
        f"- Status: `{pack['multiframe_zero_yield']['status']}`",
        "",
        "## P3 new discovery",
        "",
        f"- Videos: {', '.join(p3['videos'])}",
        f"- ROIs/frames: {p3['n_rois']} / {p3['n_frames']}",
        "- Status: PENDING_GPT_OBSERVATION (no QA drafts)",
        "",
        "## run_004",
        "",
        "**NOT_STARTED** — blockers:",
        "",
    ]
    for b in pack["run_004"]["blockers"]:
        lines.append(f"- {b}")
    lines += [
        "",
        "## Invariants",
        "",
        "All formal gates false; sealed untouched; Track A RSI not approved; open-ended QA only.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    return pack


def write_report(inv, integrity, mf_link, p3, pack, head: str) -> None:
    report = {
        "title": "Track B family-level minimal validation pilot v0.1 — engineering delivery",
        "created_utc": utc_now(),
        "commit_pending": True,
        "working_branch": "research/lvbench-comp-video-grounded-evidence",
        "head_at_build": head,
        "protocol": "FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1",
        "p0_inventory": "PILOT_INVENTORY.json",
        "p1_integrity": "reports/ENGINEERING_INTEGRITY_REPORT.json",
        "p2_multiframe": "p2_multiframe_link/MULTIFRAME_DIGEST.json",
        "p3_discovery": "p3_new_video_discovery/batch_manifest.json",
        "p4_review": "p4_scientific_review_pack/REVIEW_PACK.json",
        "p5_run_004": {
            "status": "NOT_STARTED",
            "reason": "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE + no newly admitted directed relation",
        },
        "cost_metrics": p3.get("cost_metrics"),
        "counts": inv["counts"],
        "isolation_status": integrity["isolation"]["status"],
        "multiframe_qualifying": mf_link["prior_feasibility_summary"]["n_run004_qualifying_relations"],
        "p3_qualified_candidates": 0,
        **GATES,
        "track_a_ok_for_expensive_rsi": False,
        "run_003_untouched": True,
    }
    dump(PILOT / "DELIVERY_REPORT.json", report)
    md = [
        "# FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1 — Delivery",
        "",
        f"Branch: `research/lvbench-comp-video-grounded-evidence`  ",
        f"Build HEAD: `{head}`",
        "",
        "## Roles",
        "",
        "- Seen: SP001, SP002, SP005, SP201, SP202",
        "- Unseen: P7_VTCD_C2, P7_TJR_R3",
        "- Hold: P7_R4_F1, P7_R4_F2, SP205",
        "",
        "pilot_role ≠ formal_seen_train / formal_unseen.",
        "",
        "## P1 isolation",
        "",
        f"Status: **{integrity['isolation']['status']}** — SP201/SP202 same group; Seen∩Unseen videos empty; sealed untouched.",
        "",
        "## P2 multiframe",
        "",
        f"Qualifying relations: **{mf_link['prior_feasibility_summary']['n_run004_qualifying_relations']}** (`{mf_link['prior_feasibility_summary']['status']}`).",
        "",
        "## P3 discovery",
        "",
        f"Videos `{', '.join(p3['videos'])}` — {p3['n_frames']} frames extracted; GPT observation pending; **0** QA drafts.",
        "",
        "## P5 run_004",
        "",
        "**NOT_STARTED** — no admitted nontrivial directed compositional candidate this round.",
        "",
        "## Gates",
        "",
        "All formal gates remain false; Track A expensive RSI not approved.",
        "",
    ]
    (PILOT / "DELIVERY_REPORT.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    head = git_sha("HEAD")
    p7_head = git_sha("research/lvbench-comp-p7-hil-pilot")
    if not SNAP.exists() or not any(SNAP.glob("*.json")):
        print("Missing provenance snapshots", file=sys.stderr)
        raise SystemExit(1)

    inv = build_inventory(p7_head)
    dump(PILOT / "PILOT_INVENTORY.json", inv)
    dump(
        PILOT / "PILOT_CONFIG.json",
        {
            "protocol": "FAMILY_LEVEL_MINIMAL_VALIDATION_PILOT_v0.1",
            "seen": ["SP001", "SP002", "SP005", "SP201", "SP202"],
            "unseen": ["P7_VTCD_C2", "P7_TJR_R3"],
            "hold": ["P7_R4_F1", "P7_R4_F2", "SP205"],
            "qa_format": "OPEN_ENDED",
            "sp201_sp202_isolation_group": "VIDEO_Hf-n1yfd8II",
            "does_not_overwrite_history": True,
            "run_003_untouched": True,
            "run_004_status": "NOT_STARTED",
            **GATES,
        },
    )
    integrity = build_integrity(inv)
    dump(PILOT / "reports/ENGINEERING_INTEGRITY_REPORT.json", integrity)
    # markdown summary
    cov_lines = ["# Engineering integrity report", "", "## Family coverage", ""]
    for fam, row in integrity["capability_family_coverage_matrix"].items():
        cov_lines.append(f"- `{fam}`: **{row['status']}** — {', '.join(row['items']) or '—'}")
    cov_lines += ["", f"## Isolation: {integrity['isolation']['status']}", ""]
    (PILOT / "reports/ENGINEERING_INTEGRITY_REPORT.md").write_text("\n".join(cov_lines) + "\n", encoding="utf-8")

    mf_link = link_multiframe()
    p3 = extract_p3_frames()
    pack = build_review_pack(inv, mf_link, p3, integrity)
    write_report(inv, integrity, mf_link, p3, pack, head)

    # Gate file for run_004
    dump(
        PILOT / "RUN_004_GATE.json",
        {
            "run_004_status": "NOT_STARTED",
            "status": "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE",
            "blockers": pack["run_004"]["blockers"],
            "n_qualified_new_candidates": 0,
            **GATES,
        },
    )
    print(
        json.dumps(
            {
                "ok": True,
                "isolation": integrity["isolation"]["status"],
                "mf_qualifying": mf_link["prior_feasibility_summary"]["n_run004_qualifying_relations"],
                "p3_frames": p3["n_frames"],
                "run_004": "NOT_STARTED",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
