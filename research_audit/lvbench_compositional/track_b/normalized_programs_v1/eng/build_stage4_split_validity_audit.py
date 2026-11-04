#!/usr/bin/env python3
"""Stage 4: split-validity audit — corrected M3, novelty decomposition, M4 reinterpretation.

Does not rebuild graphs, re-split Seen/Unseen, or alter approved vocab.
Preserves Stage-3 historical metrics; writes new stage4_* artifacts.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(HERE))

from stage4_m3_isomorphism import (  # noqa: E402
    LAYERS,
    MODES,
    coverage_report,
    enumerate_subgraphs,
    self_check_duplicate_labels,
)

SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]
UNSEEN = ["P7_VTCD_C2", "P7_TJR_R3"]
CANDIDATE = ["A", "B", "P7_R4_F1", "P7_R4_F2"]
ALGO = "stage4_split_validity_audit_v1.0.0"

# Independent reference (must be matched by computation, not hardcoded into algorithm)
REF_LAYER1 = {
    ("ops", 2): (3, 7),
    ("ops", 3): (1, 7),
    ("ops_role", 2): (3, 8),
    ("ops_role", 3): (0, 8),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_graphs() -> dict[str, dict]:
    graphs = {}
    for p in (OUT / "graphs").glob("*.json"):
        g = json.loads(p.read_text())
        graphs[g["graph_id"]] = g
    return graphs


def archive_stage3() -> str:
    hist_dir = OUT / "reports" / "stage3_historical"
    hist_dir.mkdir(parents=True, exist_ok=True)
    stamp = "08b5483"
    for name in ("overlap_metrics.json", "overlap_report.md"):
        src = OUT / name
        if src.is_file():
            dst = hist_dir / f"{name.replace('.', f'_{stamp}.')}"
            # overlap_metrics_08b5483.json style
            if name.endswith(".json"):
                dst = hist_dir / f"overlap_metrics_{stamp}.json"
            else:
                dst = hist_dir / f"overlap_report_{stamp}.md"
            if not dst.exists():
                shutil.copy2(src, dst)
    return str(hist_dir.relative_to(OUT.parent.parent.parent.parent))  # best-effort


def operator_coverage(g: dict, seen_labels: set[str], layer: str) -> dict:
    labels = [n[layer] for n in g["nodes"]]
    covered = [x for x in labels if x in seen_labels]
    only = [x for x in labels if x not in seen_labels]
    return {
        "n_nodes": len(labels),
        "covered_nodes": len(covered),
        "coverage_ratio": len(covered) / len(labels) if labels else None,
        "unseen_only_labels_on_nodes": only,
        "distinct_labels": sorted(set(labels)),
        "distinct_unseen_only": sorted(set(only)),
    }


def novelty_decomposition(graphs: dict[str, dict], ug: str) -> dict:
    """Task 2: decompose structural novelty for one Unseen graph."""
    seen_l1 = {n["layer1"] for gid in SEEN for n in graphs[gid]["nodes"]}
    seen_l2 = {n["layer2"] for gid in SEEN for n in graphs[gid]["nodes"]}
    g = graphs[ug]

    cov_l1 = operator_coverage(g, seen_l1, "layer1")
    cov_l2 = operator_coverage(g, seen_l2, "layer2")

    def subgraph_stats(size: int, layer: str, mode: str) -> dict:
        items = enumerate_subgraphs(g, size, layer, mode)
        if not items:
            return {"n": 0, "with_unseen_only_l2": None, "seen_atoms_only_overlap": "N/A"}

        # For each occurrence, whether any node has Unseen-only Layer2
        with_uol2 = 0
        seen_atom_only = []
        for it in items:
            nodes = [next(n for n in g["nodes"] if n["node_id"] == nid) for nid in it["nodes"]]
            has_uol2 = any(n["layer2"] not in seen_l2 for n in nodes)
            if has_uol2:
                with_uol2 += 1
            else:
                seen_atom_only.append(it)

        # Overlap of seen-atom-only subgraphs vs Seen pool (Layer2 ops mode for structure)
        if not seen_atom_only:
            seen_only_overlap = "N/A"
            seen_only_ratio = None
            note = "No subgraph composed solely of Seen-covered Layer2 atoms; not scored as zero."
        else:
            from stage4_m3_isomorphism import pool_signatures

            seen_u, _, _ = pool_signatures(graphs, SEEN, size, "layer2", "ops")
            matched = sum(1 for it in seen_atom_only if it["signature"] in seen_u)
            # Recompute signatures for seen_atom_only under layer2/ops consistently
            # (items were enumerated under `layer`/`mode`; for fair atom-structure use layer2/ops)
            items_l2 = enumerate_subgraphs(g, size, "layer2", "ops")
            seen_atom_only_l2 = []
            for it in items_l2:
                nodes = [next(n for n in g["nodes"] if n["node_id"] == nid) for nid in it["nodes"]]
                if all(n["layer2"] in seen_l2 for n in nodes):
                    seen_atom_only_l2.append(it)
            if not seen_atom_only_l2:
                seen_only_overlap = "N/A"
                seen_only_ratio = None
                note = "No Layer2-ops subgraph composed solely of Seen atoms; N/A."
            else:
                matched = sum(1 for it in seen_atom_only_l2 if it["signature"] in seen_u)
                seen_only_overlap = f"{matched}/{len(seen_atom_only_l2)}"
                seen_only_ratio = matched / len(seen_atom_only_l2)
                note = "Occurrence-weighted overlap among Seen-atom-only Layer2 ops subgraphs."

        return {
            "n_subgraphs": len(items),
            "with_unseen_only_layer2_operator": {
                "count": with_uol2,
                "ratio": with_uol2 / len(items),
                "fraction": f"{with_uol2}/{len(items)}",
            },
            "seen_atom_only_structural_overlap_layer2_ops": {
                "value": seen_only_overlap,
                "ratio": seen_only_ratio,
                "note": note,
            },
            "enumeration_mode_for_with_uol2": f"{layer}/{mode}",
        }

    # Role combinations
    seen_roles = {
        (n["layer2"], n.get("normalized_clip_role") or n.get("raw_clip_role"))
        for gid in SEEN
        for n in graphs[gid]["nodes"]
    }
    ug_roles = [
        (n["layer2"], n.get("normalized_clip_role") or n.get("raw_clip_role"))
        for n in g["nodes"]
    ]
    novel_roles = [r for r in ug_roles if r not in seen_roles]

    # Edge-type / connection novelty at Layer2 ops_role_edge 2-node level
    from stage4_m3_isomorphism import pool_signatures

    seen_edge_sigs, _, _ = pool_signatures(graphs, SEEN, 2, "layer2", "ops_role_edge")
    ug_edge_items = enumerate_subgraphs(g, 2, "layer2", "ops_role_edge")
    novel_connections = [it for it in ug_edge_items if it["signature"] not in seen_edge_sigs]

    return {
        "graph_id": ug,
        "layer1_operator_coverage": cov_l1,
        "layer2_operator_coverage": cov_l2,
        "subgraph_2_layer2_ops": subgraph_stats(2, "layer2", "ops"),
        "subgraph_3_layer2_ops": subgraph_stats(3, "layer2", "ops"),
        "contributions": {
            "unseen_operators_layer2": cov_l2["distinct_unseen_only"],
            "unseen_operator_node_fraction": 1.0 - (cov_l2["coverage_ratio"] or 0.0),
            "unseen_connections_2node_ops_role_edge": {
                "novel_count": len(novel_connections),
                "total": len(ug_edge_items),
                "ratio": len(novel_connections) / len(ug_edge_items) if ug_edge_items else None,
            },
            "unseen_window_role_combinations": {
                "novel_node_instances": len(novel_roles),
                "total_nodes": len(ug_roles),
                "novel_pairs": [
                    {"layer2": a, "role": b} for a, b in sorted(set(novel_roles))
                ],
            },
        },
    }


def m4_reinterpret(graphs: dict[str, dict]) -> dict:
    """Task 3: mark TRIVIAL_SIZE_MISMATCH; do not treat as strong novelty evidence."""
    pairs = []
    for ug in UNSEEN:
        for sg in SEEN:
            nu, ns = graphs[ug]["n_nodes"], graphs[sg]["n_nodes"]
            eu, es = graphs[ug]["n_edges"], graphs[sg]["n_edges"]
            if nu != ns or eu != es:
                pairs.append(
                    {
                        "unseen": ug,
                        "seen": sg,
                        "status": "TRIVIAL_SIZE_MISMATCH",
                        "unseen_size": {"nodes": nu, "edges": eu},
                        "seen_size": {"nodes": ns, "edges": es},
                        "interpretation": (
                            "Not strong evidence of novel composition; sizes differ so "
                            "full digraph equivalence is vacuously impossible."
                        ),
                    }
                )
            else:
                pairs.append(
                    {
                        "unseen": ug,
                        "seen": sg,
                        "status": "SAME_SIZE_REQUIRES_ISO_TEST",
                        "unseen_size": {"nodes": nu, "edges": eu},
                        "seen_size": {"nodes": ns, "edges": es},
                        "note": "Would require non-trivial isomorphism test; none in current 5/2 set share sizes with these Unseen (both Unseen are 5-node).",
                    }
                )
    # How many Seen share Unseen sizes?
    size_notes = {
        ug: {
            "unseen_nodes": graphs[ug]["n_nodes"],
            "seen_with_same_n_nodes": [
                sg for sg in SEEN if graphs[sg]["n_nodes"] == graphs[ug]["n_nodes"]
            ],
        }
        for ug in UNSEEN
    }
    return {
        "pairs": pairs,
        "size_notes": size_notes,
        "scientific_caution": (
            "M4 inequivalence driven by TRIVIAL_SIZE_MISMATCH must not be cited as "
            "primary evidence of unseen compositional structure."
        ),
    }


def scientific_validity(m3: dict, novelty: dict, m4: dict, graphs: dict) -> dict:
    """Task 4: judgments A–E without changing splits."""
    # A: Layer1 family-level compositional novelty
    l1_ops_2 = m3["layer1"]["ops"]["2_node"]
    l1_ops_3 = m3["layer1"]["ops"]["3_node"]
    l1_role_2 = m3["layer1"]["ops_role"]["2_node"]
    l1_role_3 = m3["layer1"]["ops_role"]["3_node"]

    a = {
        "question": "Can this split support Layer-1 family-level compositional novelty?",
        "judgment": "PARTIAL_YES_PILOT_SCALE",
        "basis": {
            "m1_layer1_label_coverage": "complete on current Unseen (from Stage3/4 operator sets)",
            "m3_layer1_ops_2node": l1_ops_2["unique_fraction"],
            "m3_layer1_ops_3node": l1_ops_3["unique_fraction"],
            "m3_layer1_ops_role_2node": l1_role_2["unique_fraction"],
            "m3_layer1_ops_role_3node": l1_role_3["unique_fraction"],
        },
        "reading": (
            "Unseen Layer1 families are covered by Seen, but many Layer1 directed subgraphs "
            "are not; this is consistent with family-level recombination novelty at pilot scale. "
            "ops_role 3-node unique coverage is 0/8, strengthening role-sensitive structure novelty."
        ),
    }

    # B: Layer2 atomic pure compositional novelty
    l2_only = sorted(
        {
            lab
            for ug in UNSEEN
            for lab in novelty[ug]["layer2_operator_coverage"]["distinct_unseen_only"]
        }
    )
    b = {
        "question": "Can this split support Layer-2 atomic-level pure compositional novelty?",
        "judgment": "NO_NOT_PURE",
        "basis": {
            "unseen_only_layer2_operators": l2_only,
            "implication": (
                "Several Unseen Layer2 atoms never appear in Seen; novelty mixes new atoms "
                "with possible new wiring — not a pure composition test."
            ),
        },
    }

    # C: atomic distribution shift
    c = {
        "question": "Is atomic operator distribution shift mixed into the split?",
        "judgment": "YES",
        "evidence": {
            "unseen_only_layer2": l2_only,
            "per_unseen": {
                ug: novelty[ug]["layer2_operator_coverage"]["distinct_unseen_only"]
                for ug in UNSEEN
            },
        },
    }

    # D: pilot-only conclusions
    d = {
        "question": "Which conclusions apply only to the current 2-Unseen pilot?",
        "judgment": "MOST_QUANTITATIVE_CLAIMS",
        "pilot_only": [
            "Exact M3 fractions (e.g., Layer1 ops 3/7, 1/7)",
            "M4 all-pairs TRIVIAL_SIZE_MISMATCH pattern (both Unseen are 5-node; Seen are 8/6/8/4/4)",
            "Complete Layer1 label coverage of Unseen",
            "Candidate A/B/F1/F2 sensitivity outcomes",
        ],
        "more_durable_method_claims": [
            "Need Layer1 and Layer2 subgraph modes separately",
            "Need unique and occurrence-weighted denominators",
            "Need TRIVIAL_SIZE_MISMATCH handling for M4",
            "Pure atomic composition requires Seen coverage of Unseen atoms",
        ],
    }

    # E: minimal next experiments without re-splitting
    e = {
        "question": "Without re-splitting, what minimal controls/experiments are needed for CVPR claims?",
        "judgment": "CONTROLS_REQUIRED",
        "minimal_next": [
            {
                "id": "CTRL_SEEN_ATOM_COVERED_UNSEEN_SUBSET",
                "action": (
                    "Identify or construct evaluation items whose Layer2 atoms are all Seen-covered "
                    "(hold-out wiring only); report M3 on that subset separately."
                ),
                "purpose": "Isolate pure compositional novelty from atom inventory shift",
            },
            {
                "id": "CTRL_SIZE_MATCHED_SEEN_PROBE",
                "action": (
                    "Add analysis probes or synthetic controls with 5-node Seen programs matching "
                    "Unseen sizes for non-trivial M4 — without promoting them into formal Unseen."
                ),
                "purpose": "Avoid TRIVIAL_SIZE_MISMATCH dominating full-graph inequivalence narrative",
            },
            {
                "id": "REPORT_LAYER_SEPARATION",
                "action": (
                    "In paper, claim family-level (Layer1) recombination separately from atomic (Layer2) "
                    "composition; never merge M1=1.0 with M2≪1 into one 'compositional' headline."
                ),
                "purpose": "Prevent overclaim",
            },
            {
                "id": "EXPAND_N_UNSEEN_LATER",
                "action": "Treat current 2 Unseen as pilot; defer CVPR-strength generalization claims until N_unseen grows under same frozen vocab.",
                "purpose": "Statistical / external validity",
            },
        ],
        "forbidden_here": [
            "Auto-expand Seen",
            "Move Unseen",
            "Promote A/B/F1/F2",
            "Certify Gold",
        ],
    }

    return {"A": a, "B": b, "C": c, "D": d, "E": e}


def build_m3(graphs: dict[str, dict]) -> dict:
    out = {"definition": (
        "Directed weakly-connected induced subgraphs; canonical signature via "
        "label-preserving isomorphism (lex-min encoding). Modes: ops, ops_role "
        "(no dependency_kind), ops_role_edge, ops_role_edge_io (I/O alpha-renamed)."
    )}
    for layer in LAYERS:
        out[layer] = {}
        for mode in MODES:
            out[layer][mode] = {}
            for size in (2, 3):
                out[layer][mode][f"{size}_node"] = coverage_report(
                    graphs, SEEN, UNSEEN, size, layer, mode
                )
    # reference verification
    ref_check = []
    for (mode, size), (num, den) in REF_LAYER1.items():
        cell = out["layer1"][mode][f"{size}_node"]
        got = (cell["intersection_unique"], cell["unseen_unique"])
        ref_check.append(
            {
                "cell": f"layer1/{mode}/{size}_node",
                "expected_unique_fraction": f"{num}/{den}",
                "got_unique_fraction": cell["unique_fraction"],
                "match": got == (num, den),
            }
        )
    out["independent_reference_check_layer1"] = ref_check
    out["reference_check_all_match"] = all(x["match"] for x in ref_check)
    out["duplicate_label_self_check"] = self_check_duplicate_labels()
    return out


def write_md(audit: dict, path: Path) -> None:
    lines = [
        "# Stage 4 — Split validity audit",
        "",
        f"- algo: `{audit['algo_version']}`",
        f"- built_utc: {audit['built_utc']}",
        f"- baseline_commit: `{audit['baseline_commit']}`",
        f"- Stage3 historical preserved under `reports/stage3_historical/`",
        "",
        "## Task 1 — Corrected M3 (Layer1 ops reference check)",
    ]
    for row in audit["m3_corrected"]["independent_reference_check_layer1"]:
        lines.append(
            f"- {row['cell']}: expected {row['expected_unique_fraction']}, "
            f"got {row['got_unique_fraction']} → {'MATCH' if row['match'] else 'MISMATCH'}"
        )
    lines += ["", "### Unique coverage snapshot"]
    for layer in LAYERS:
        lines.append(f"#### {layer}")
        for mode in MODES:
            for size in (2, 3):
                cell = audit["m3_corrected"][layer][mode][f"{size}_node"]
                lines.append(
                    f"- `{mode}` {size}-node: unique {cell['unique_fraction']} "
                    f"(occ {cell['occurrence_fraction']})"
                )
    lines += ["", "## Task 2 — Novelty decomposition"]
    for ug, block in audit["novelty_decomposition"].items():
        lines.append(f"### {ug}")
        lines.append(f"- L1 coverage: {block['layer1_operator_coverage']['coverage_ratio']}")
        lines.append(f"- L2 coverage: {block['layer2_operator_coverage']['coverage_ratio']}")
        lines.append(
            f"- L2 unseen-only ops: {block['layer2_operator_coverage']['distinct_unseen_only']}"
        )
        s2 = block["subgraph_2_layer2_ops"]
        lines.append(
            f"- 2-node subgraphs with Unseen-only L2 op: "
            f"{s2['with_unseen_only_layer2_operator']['fraction']}"
        )
        lines.append(
            f"- Seen-atom-only structural overlap: "
            f"{s2['seen_atom_only_structural_overlap_layer2_ops']['value']}"
        )
    lines += ["", "## Task 3 — M4 reinterpretation", audit["m4_reinterpretation"]["scientific_caution"]]
    lines += ["", "## Task 4 — Scientific validity"]
    for key in ("A", "B", "C", "D", "E"):
        block = audit["scientific_validity"][key]
        lines.append(f"### {key}. {block['question']}")
        lines.append(f"- judgment: **{block['judgment']}**")
    lines += ["", "## Remaining limits"]
    for x in audit["remaining_limits"]:
        lines.append(f"- {x}")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    graphs = load_graphs()
    missing = [i for i in SEEN + UNSEEN + CANDIDATE if i not in graphs]
    if missing:
        raise SystemExit(f"Missing graphs: {missing}")

    # archive stage3
    hist = OUT / "reports" / "stage3_historical"
    hist.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in (
        ("overlap_metrics.json", "overlap_metrics_08b5483.json"),
        ("overlap_report.md", "overlap_report_08b5483.md"),
    ):
        src = OUT / src_name
        dst = hist / dst_name
        if src.is_file() and not dst.exists():
            shutil.copy2(src, dst)
        elif src.is_file():
            # refresh copy only if content differs and destination marked historical — keep first snapshot
            pass

    m3 = build_m3(graphs)
    if not m3["reference_check_all_match"]:
        print("WARNING: Layer1 reference fractions did not match", file=sys.stderr)
        print(json.dumps(m3["independent_reference_check_layer1"], indent=2), file=sys.stderr)

    novelty = {ug: novelty_decomposition(graphs, ug) for ug in UNSEEN}
    m4 = m4_reinterpret(graphs)
    validity = scientific_validity(m3, novelty, m4, graphs)

    audit = {
        "schema": "stage4_split_validity_audit_v1",
        "algo_version": ALGO,
        "built_utc": utc_now(),
        "baseline_commit": "08b5483f7761ee42a4a0a008988d4d37f484d0a0",
        "fixed_split": {"seen": SEEN, "unseen": UNSEEN, "candidate_only": CANDIDATE},
        "stage3_historical_paths": [
            "reports/stage3_historical/overlap_metrics_08b5483.json",
            "reports/stage3_historical/overlap_report_08b5483.md",
        ],
        "m3_corrected": m3,
        "novelty_decomposition": novelty,
        "m4_reinterpretation": m4,
        "scientific_validity": validity,
        "remaining_limits": [
            "Only 2 formal Unseen graphs — quantitative fractions are pilot-scale",
            "Chat-approved sidecars are not frame-certified video evidence",
            "I/O alpha-renaming is structural; does not recover semantic variable identity across graphs",
            "No Seen graph shares 5-node size with C2/R3 — M4 full-graph tests are dominated by TRIVIAL_SIZE_MISMATCH",
            "Pure Layer2 compositional evaluation requires Seen-atom-covered controls (see validity.E)",
        ],
        "algorithm_self_checks": {
            "duplicate_label_id_independence": m3["duplicate_label_self_check"],
            "layer1_reference_fractions": m3["independent_reference_check_layer1"],
        },
    }

    (OUT / "stage4_split_validity_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n"
    )
    write_md(audit, OUT / "stage4_split_validity_audit.md")
    print(
        json.dumps(
            {
                "status": "OK",
                "reference_check_all_match": m3["reference_check_all_match"],
                "layer1_ops_2": m3["layer1"]["ops"]["2_node"]["unique_fraction"],
                "layer1_ops_3": m3["layer1"]["ops"]["3_node"]["unique_fraction"],
                "layer1_ops_role_2": m3["layer1"]["ops_role"]["2_node"]["unique_fraction"],
                "layer1_ops_role_3": m3["layer1"]["ops_role"]["3_node"]["unique_fraction"],
                "validity": {k: validity[k]["judgment"] for k in validity},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
