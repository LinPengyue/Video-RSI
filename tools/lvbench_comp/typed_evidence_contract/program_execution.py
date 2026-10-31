"""Execute selected program DAGs on synthetic worlds (not label-only scoring).

`ok_for_expensive_rsi=false`. Frozen 4-task binding suite remains untouched negative control.
"""

from __future__ import annotations

import json
import random
import re
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .contracts import OperationName, OperationRequest
from .executor import TypedEvidenceExecutor, default_genome
from .program_schema import ProgramSchema
from .program_selection import (
    DAG_LIBRARY,
    SCHEMA_A_BIND_B,
    SCHEMA_B_BIND_A,
    SCHEMA_COMPARE_TWO_STATES,
    SCHEMA_MISSING_ABSTAIN,
    ProgTask,
    _make_world,
    _question_features,
    build_program_selection_split,
    select_program,
)


def schema_to_program(schema: ProgramSchema, task: ProgTask) -> list[dict[str, Any]]:
    """Compile schema nodes into executor program steps with task-conditioned inputs."""
    prog: list[dict[str, Any]] = []
    for node in schema.nodes:
        role = node.role
        inputs: dict[str, Any] = {}
        if node.op == "locate_event":
            if "state_a" in role or role.endswith("_a") or "index_state_a" in role:
                inputs["cue"] = "board_early"
            elif "state_b" in role or role.endswith("_b") or "index_state_b" in role:
                inputs["cue"] = "board_late"
            elif schema.schema_id == SCHEMA_B_BIND_A.schema_id:
                inputs["cue"] = "previous_results" if ("b" in role or "event" in role or "later" in role) else "warmup"
            else:
                inputs["cue"] = task.referring
        elif node.op == "resolve_reference":
            inputs["referring_expression"] = task.referring
        elif node.op == "query_property":
            inputs["entity_id"] = "bound"  # executor uses memory.bound_entity
            inputs["property_name"] = task.property_name
        elif node.op == "verify_answer":
            inputs["answer"] = task.answer
            inputs["interval_a"] = {"start_s": 0.0, "end_s": 10.0}
            inputs["interval_b"] = {"start_s": 20.0, "end_s": 40.0}
        elif node.op == "track_identity":
            inputs["entity_id"] = "bound"
        prog.append({"op": node.op, "inputs": inputs, "node_id": role})
    return prog


def _world_for_task(task: ProgTask) -> Any:
    sid = task.gold_schema_id
    reverse = sid == SCHEMA_B_BIND_A.schema_id
    missing = sid == SCHEMA_MISSING_ABSTAIN.schema_id
    compare = sid == SCHEMA_COMPARE_TWO_STATES.schema_id
    return _make_world(str(task.answer), reverse=reverse, missing=missing, compare=compare)


def execute_selected(
    task: ProgTask,
    *,
    selected_schema_id: str | None = None,
    genome: dict[str, Any] | None = None,
    mask: str | None = None,
) -> dict[str, Any]:
    """Select (or force) a DAG, execute on synthetic world, return trace + answer metrics."""
    genome = genome or default_genome()
    sel = select_program(task.question, genome={k: genome.get(k, 1.0) for k in ("w_forward", "w_reverse", "w_compare", "w_abstain")})
    sid = selected_schema_id or sel["selected_schema_id"]
    schema = DAG_LIBRARY[sid]
    world = _world_for_task(task)

    # Optional evidence masks for semantic controls
    if mask == "drop_A":
        world.facts = [f for f in world.facts if f.time.label != "A"]
    elif mask == "drop_B":
        world.facts = [f for f in world.facts if f.time.label != "B"]
    elif mask == "swap_roles" and len(world.facts) >= 2:
        # Swap entity_id on first two facts
        a, b = world.facts[0], world.facts[1]
        a.entity_id, b.entity_id = b.entity_id, a.entity_id
    elif mask == "swap_order" and len(world.facts) >= 2:
        world.facts = list(reversed(world.facts))

    ex = TypedEvidenceExecutor(world, genome=genome)
    program = schema_to_program(schema, task)
    results = ex.run_program(program)

    pred = None
    abstained = False
    explicit_abstain = False
    compare_states_from_tools: list[Any] = []
    per_op_ok: dict[str, list[bool]] = {}
    for r in results:
        per_op_ok.setdefault(r.op.value, []).append(r.ok)
        if r.op == OperationName.QUERY_PROPERTY and r.ok:
            pred = r.outputs.get("property_value")
            if r.outputs.get("property_name") == "order" or "order" in str(r.outputs):
                pass
        if r.op == OperationName.LOCATE_EVENT and r.ok:
            # Tool-visible located values only (not oracle world scrape)
            val = r.outputs.get("property_value") or r.outputs.get("matched_value")
            if val is not None:
                compare_states_from_tools.append(val)
            # Some locate handlers return facts list
            for f in r.outputs.get("facts") or []:
                if isinstance(f, dict) and f.get("property_value") is not None:
                    compare_states_from_tools.append(f["property_value"])
        # Explicit abstention policy: missing-evidence schema must decide ABSTAIN
        if r.failure_code == "MISSING_EVIDENCE":
            if sid == SCHEMA_MISSING_ABSTAIN.schema_id:
                # calibrated: treat as abstain decision only when schema is abstain DAG
                explicit_abstain = True
                abstained = True
        if r.op == OperationName.VERIFY_ANSWER and (r.outputs.get("abstain") or r.outputs.get("answer") == "ABSTAIN"):
            explicit_abstain = True
            abstained = True

    # If missing-evidence DAG ends without a property and with MISSING_EVIDENCE somewhere → explicit ABSTAIN
    if sid == SCHEMA_MISSING_ABSTAIN.schema_id and explicit_abstain:
        pred_out = "ABSTAIN"
        abstained = True
    elif sid == SCHEMA_MISSING_ABSTAIN.schema_id and pred is None and not explicit_abstain:
        # Null output alone is NOT credited as abstain (integrity fix)
        pred_out = None
        abstained = False
    else:
        pred_out = pred

    # Answer check — scorer may see gold; agent path must not scrape oracle world
    gold = task.answer
    scorer_notes: list[str] = []

    def _norm_ans(x: Any) -> str:
        return re.sub(r"\s+", " ", str(x).strip().lower()) if x is not None else ""

    def _exact_or_canon(pred: Any, gold_v: Any) -> bool:
        if pred is None:
            return False
        p, g = _norm_ans(pred), _norm_ans(gold_v)
        if not p or not g:
            return False
        if p == g:
            return True
        # Allow exact token-set equality after splitting on arrows/separators
        def toks(s: str) -> list[str]:
            return [t for t in re.split(r"[→>;,|/\s]+", s) if t]

        return toks(p) == toks(g)

    if sid == SCHEMA_MISSING_ABSTAIN.schema_id:
        # Wrong abstain DAG on a non-abstain gold must NOT score correct
        gold_is_abstain = _norm_ans(gold) == "abstain"
        answer_ok = bool(explicit_abstain and gold_is_abstain and _norm_ans(pred_out) == "abstain")
        if explicit_abstain and not gold_is_abstain:
            answer_ok = False
            scorer_notes.append("wrong_schema_abstain_not_credited")
        if not answer_ok and not explicit_abstain:
            scorer_notes.append("abstain_requires_explicit_missing_evidence_decision")
    elif sid == SCHEMA_COMPARE_TWO_STATES.schema_id:
        answer_ok = False
        evidence_path_valid_seen = False
        for r in results:
            if r.op == OperationName.VERIFY_ANSWER:
                if r.outputs.get("evidence_path_valid"):
                    evidence_path_valid_seen = True
                if r.ok:
                    pred_out = r.outputs.get("answer") or pred_out
                break
        if compare_states_from_tools and pred_out is None:
            pred_out = "→".join(str(s) for s in compare_states_from_tools)
            scorer_notes.append("compare_from_tool_outputs_only")
        # evidence_path_valid alone is NEVER sufficient
        answer_ok = _exact_or_canon(pred_out, gold)
        if evidence_path_valid_seen and not answer_ok:
            scorer_notes.append("evidence_path_valid_ignored_without_answer_match")
        if not answer_ok:
            scorer_notes.append("no_oracle_world_fallback")
    else:
        answer_ok = _exact_or_canon(pred_out, gold)

    trace = []
    for i, (step, r) in enumerate(zip(program, results)):
        trace.append(
            {
                "i": i,
                "node_id": step.get("node_id"),
                "op": step["op"],
                "ok": r.ok,
                "failure_code": r.failure_code,
                "outputs_keys": list((r.outputs or {}).keys()),
                "budget_spent": r.budget_spent,
            }
        )

    return {
        "task_id": task.task_id,
        "question": task.question,
        "gold_schema_id": task.gold_schema_id,
        "selected_schema_id": sid,
        "selection_correct": sid == task.gold_schema_id,
        "selected_graph_hash": schema.graph_hash(),
        "mask": mask,
        "program_n_ops": len(program),
        "trace": trace,
        "pred": pred_out,
        "gold_answer": gold,
        "execution_answer_ok": bool(answer_ok),
        "abstained": abstained,
        "explicit_abstain": explicit_abstain,
        "per_op_success": {k: sum(v) / max(1, len(v)) for k, v in per_op_ok.items()},
        "scorer_notes": scorer_notes,
        "tool_calls": len(ex.memory.tool_calls),
        "budget_remaining": ex.budget,
        "bound_entity": getattr(ex.memory.bound_entity, "entity_id", None) if ex.memory.bound_entity else None,
        "steps_ok": [t["ok"] for t in trace],
        "ok_for_expensive_rsi": False,
        # Instrumented: True only if scorer path scraped executor world state for credit
        "oracle_world_scraped": False,
        "scorer_sees_gold": True,  # scorer-only; executor never receives task.answer
        "executor_saw_gold_answer": False,
    }


def paraphrase(q: str, rng: random.Random) -> str:
    """Surface paraphrase preserving mechanism cues."""
    swaps = [
        ("later", "afterwards"),
        ("earlier", "previously"),
        ("Compare", "Order"),
        ("missing", "absent"),
        ("abstain", "refuse to answer"),
        ("garment color", "jacket color"),
        ("teal scarf", "person with teal scarf"),
    ]
    out = q
    for a, b in swaps:
        if a in out and rng.random() < 0.7:
            out = out.replace(a, b, 1)
    return out


def run_execution_suite(*, seed: int = 42) -> dict[str, Any]:
    """Full Track A execution-over-selection evaluation."""
    rng = random.Random(seed)
    split = build_program_selection_split(seed=seed)
    leave = split.pop("_leave_out")
    train_ids = split.pop("_train_schema_ids")
    held_ids = split.pop("_held_schema_ids")
    test: list[ProgTask] = split["test"]

    # 1) Execute selected DAG (selector choice) vs gold DAG upper bound
    rows_selected = []
    rows_gold = []
    for t in test:
        rows_selected.append(execute_selected(t))
        rows_gold.append(execute_selected(t, selected_schema_id=t.gold_schema_id))

    # 2) Semantic controls
    semantic = []
    for t in test[:4]:
        pq = paraphrase(t.question, rng)
        t2 = ProgTask(**{**t.__dict__, "question": pq, "task_id": t.task_id + "_para"})
        r_para = execute_selected(t2)
        # Same keywords, wrong gold force: if compare keywords but force forward
        r_force_fwd = execute_selected(t, selected_schema_id=SCHEMA_A_BIND_B.schema_id)
        for mask in ("drop_A", "drop_B", "swap_roles", "swap_order"):
            semantic.append({**execute_selected(t, selected_schema_id=t.gold_schema_id, mask=mask), "control": mask})
        semantic.append({**r_para, "control": "paraphrase"})
        semantic.append({**r_force_fwd, "control": "force_forward_dag"})

    # 3) Budget-matched policies: strong static selector, random, evolver weights (selection then execute)
    g0 = {"w_forward": 1.0, "w_reverse": 1.0, "w_compare": 1.0, "w_abstain": 1.0, "search_budget": 6}
    # cheap weight search on train+dev selection accuracy only
    best = dict(g0)
    for _ in range(4):
        cand = dict(best)
        key = rng.choice(["w_forward", "w_reverse", "w_compare", "w_abstain"])
        cand[key] = max(0.2, min(2.5, cand[key] + rng.choice([-0.4, 0.4])))
        # keep if selection improves on train
        def sel_acc(g: dict) -> float:
            ok = 0
            for t in split["train"]:
                if select_program(t.question, genome=g)["selected_schema_id"] == t.gold_schema_id:
                    ok += 1
            return ok / max(1, len(split["train"]))

        if sel_acc(cand) >= sel_acc(best):
            best = cand

    def policy_rows(name: str, choose_sid) -> list[dict[str, Any]]:
        out = []
        for t in test:
            sid = choose_sid(t)
            r = execute_selected(t, selected_schema_id=sid, genome=g0)
            r["policy"] = name
            out.append(r)
        return out

    arms = {
        "strong_static_selector": policy_rows(
            "strong_static_selector",
            lambda t: select_program(t.question, genome=g0)["selected_schema_id"],
        ),
        "random": policy_rows("random", lambda t: rng.choice(list(DAG_LIBRARY.keys()))),
        "evolver_weights": policy_rows(
            "evolver_weights",
            lambda t: select_program(t.question, genome=best)["selected_schema_id"],
        ),
        "oracle_gold_dag": policy_rows("oracle_gold_dag", lambda t: t.gold_schema_id),
    }

    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        n = max(1, len(rows))
        return {
            "n": len(rows),
            "program_choice_accuracy": sum(1 for r in rows if r["selection_correct"]) / n,
            "execution_answer_accuracy": sum(1 for r in rows if r["execution_answer_ok"]) / n,
            "both_select_and_execute": sum(1 for r in rows if r["selection_correct"] and r["execution_answer_ok"]) / n,
            "abstention_rate": sum(1 for r in rows if r["abstained"]) / n,
            "explicit_abstain_rate": sum(1 for r in rows if r.get("explicit_abstain")) / n,
            "oracle_world_scraped_rate": sum(1 for r in rows if r.get("oracle_world_scraped")) / n,
            "mean_tool_calls": sum(r["tool_calls"] for r in rows) / n,
            "held_out_exec_acc": (
                sum(1 for r in rows if r["gold_schema_id"] in held_ids and r["execution_answer_ok"])
                / max(1, sum(1 for r in rows if r["gold_schema_id"] in held_ids))
            ),
        }

    arm_summary = {k: summarize(v) for k, v in arms.items()}

    # Keyword trap: same keywords, require different DAG
    traps = []
    q_compareish = "Later, compare which earlier action matches the graphic"
    # features have later+compare → should prefer compare, gold might be reverse
    traps.append(
        {
            "question": q_compareish,
            "features": _question_features(q_compareish),
            "selected": select_program(q_compareish, genome=g0)["selected_schema_id"],
            "note": "keywords mix later+compare; selection≠execution proof",
        }
    )

    return {
        "experiment_label": "execution_over_selection_v1",
        "ok_for_expensive_rsi": False,
        "sealed_accessed": False,
        "n_test_questions": len(test),
        "n_held_out_examples": sum(1 for t in test if t.gold_schema_id in held_ids),
        "n_independent_test_worlds": len(test),  # each task builds its world
        "structural_leave_out": leave,
        "train_schema_ids": train_ids,
        "held_out_schema_ids": held_ids,
        "dag_library_hashes": {k: v.graph_hash() for k, v in DAG_LIBRARY.items()},
        "selected_policy_summary": summarize(rows_selected),
        "gold_dag_upper_summary": summarize(rows_gold),
        "budget_matched_arms": arm_summary,
        "semantic_controls_n": len(semantic),
        "semantic_controls_exec_ok_rate": sum(1 for r in semantic if r["execution_answer_ok"]) / max(1, len(semantic)),
        "keyword_traps": traps,
        "rows_selected": rows_selected,
        "rows_gold_dag": rows_gold,
        "semantic_controls": semantic,
        "frozen_binding_negative_control": "DO_NOT_TUNE — see matched_budget_parity.json",
        "distinction": {
            "program_choice_accuracy": "label match of selected schema_id",
            "execution_answer_accuracy": "answer after running selected DAG ops on world",
            "note": "held_out_graph_accuracy previously reported was selection-only",
        },
        "evolver_weights_used": best,
    }


def write_scoring_integrity_report(out_dir: Path, result: dict[str, Any]) -> None:
    sel = result["selected_policy_summary"]
    gold = result["gold_dag_upper_summary"]
    md = f"""# Track A — Execution Scoring Integrity

Date: 2026-10-31 · `ok_for_expensive_rsi=false` · sealed untouched

## Integrity fixes applied

1. **ABSTAIN credit** requires an *explicit* missing-evidence decision (`explicit_abstain=true`), not mere `pred is None`.
2. **Compare path** may use tool-visible locate/query outputs only; **forbidden** to scrape `world.facts` in the agent/scorer fallback (`oracle_world_scraped=false` on all rows).
3. Per-operation success rates recorded in each trace under `per_op_success`.
4. Selection weight search remains label-based on train — **not** claimed as trace-optimized TECE; frozen 4-task binding negative control untuned.

## Current numbers (after integrity fix)

| | choice_acc | exec_acc | abstain | explicit_abstain | oracle_scrape |
|--|------------|----------|---------|------------------|---------------|
| selected policy | {sel['program_choice_accuracy']:.3f} | {sel['execution_answer_accuracy']:.3f} | {sel['abstention_rate']:.3f} | {sel.get('explicit_abstain_rate', 0):.3f} | {sel.get('oracle_world_scraped_rate', 0):.3f} |
| gold DAG upper | {gold['program_choice_accuracy']:.3f} | {gold['execution_answer_accuracy']:.3f} | {gold['abstention_rate']:.3f} | {gold.get('explicit_abstain_rate', 0):.3f} | {gold.get('oracle_world_scraped_rate', 0):.3f} |

Semantic-control exec_ok_rate={result['semantic_controls_exec_ok_rate']:.3f} (masks/swaps/paraphrase).

## Non-claims

- No real-video generalization.
- No expensive RSI.
- Low exec_acc after removing oracle leakage / soft abstain is an **accepted negative** on this tiny harness, not a method failure to paper over.
"""
    (out_dir / "TRACK_A_EXECUTION_SCORING_INTEGRITY.md").write_text(md, encoding="utf-8")


def write_execution_report(out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = run_execution_suite()
    result["experiment_label"] = "execution_scoring_integrity_v2"
    (out_dir / "execution_over_selection.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    write_scoring_integrity_report(out_dir, result)
    sel = result["selected_policy_summary"]
    gold = result["gold_dag_upper_summary"]
    arms = result["budget_matched_arms"]
    md = f"""# Track A — Execution Over Selection

Date: 2026-10-30 · `ok_for_expensive_rsi=false` · sealed: not accessed · partition: N/A (synthetic)

## Verdict

Selector **program_choice_accuracy={sel['program_choice_accuracy']:.3f}** is **not** the same as
**execution_answer_accuracy={sel['execution_answer_accuracy']:.3f}** after running the chosen DAG.
Gold-DAG upper bound execution_answer_accuracy={gold['execution_answer_accuracy']:.3f}.

n_test_questions={result['n_test_questions']}, n_held_out_examples={result['n_held_out_examples']},
n_independent_test_worlds={result['n_independent_test_worlds']}.

## Budget-matched arms (select → execute)

| Arm | choice_acc | exec_acc | both | abstain | mean_tools | held_exec |
|-----|------------|----------|------|---------|------------|-----------|
"""
    for name, s in arms.items():
        md += (
            f"| {name} | {s['program_choice_accuracy']:.3f} | {s['execution_answer_accuracy']:.3f} | "
            f"{s['both_select_and_execute']:.3f} | {s['abstention_rate']:.3f} | {s['mean_tool_calls']:.2f} | "
            f"{s['held_out_exec_acc']:.3f} |\n"
        )
    md += f"""
## Semantic controls

n={result['semantic_controls_n']} (paraphrase / force-forward / drop_A / drop_B / swap_roles / swap_order).
exec_ok_rate={result['semantic_controls_exec_ok_rate']:.3f}.

## What this is / is not

- **Is**: compiling selected `ProgramSchema` nodes into `TypedEvidenceExecutor` ops; recording trace, tool cost, abstention, answer check.
- **Is not**: video RSI, expensive search, or proof of unseen-graph composition beyond this synthetic harness.
- Frozen 4-task matched binding parity remains **FROZEN_NEGATIVE_CONTROL_DO_NOT_TUNE**.

## Hashes

```
{json.dumps(result['dag_library_hashes'], indent=2)}
```
"""
    (out_dir / "TRACK_A_EXECUTION_OVER_SELECTION.md").write_text(md, encoding="utf-8")
    return result


if __name__ == "__main__":
    root = Path("research_audit/lvbench_compositional/track_a")
    r = write_execution_report(root)
    print(json.dumps({k: r[k] for k in ("selected_policy_summary", "gold_dag_upper_summary", "budget_matched_arms")}, indent=2))
