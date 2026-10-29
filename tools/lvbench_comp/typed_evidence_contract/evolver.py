"""Evolver workspace: what may mutate under Typed Evidence Contract Evolution.

Forbidden: frozen video-model weights, sealed-test answer reads.
Allowed: op order/branching, budgets, recovery, conflict re-investigation, verify predicates.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .executor import default_genome


ALLOWED_MUTATION_KEYS = {
    "search_budget",
    "recovery_strategy",
    "query_requires_bound_entity",
    "verify_requires_dual_evidence",
    "abort_on_hard_fail",
    "op_order_template",
    "branch_on_ambiguity",
    "disambiguation_cue",
    "fallback_referring_expression",
}

FORBIDDEN_ACTIONS = {
    "update_frozen_video_model_weights",
    "read_sealed_test_answers",
    "hardcode_item_specific_pipeline",
}


@dataclass
class EvolutionGenome:
    params: dict[str, Any] = field(default_factory=default_genome)

    def fingerprint(self) -> str:
        blob = json.dumps(self.params, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


@dataclass
class EvolverWorkspace:
    """Records legal mutations; rejects illegal ones."""

    genome: EvolutionGenome
    history: list[dict[str, Any]] = field(default_factory=list)
    isolation_notes: list[str] = field(default_factory=list)

    def propose(self, patch: dict[str, Any]) -> dict[str, Any]:
        illegal = [k for k in patch if k not in ALLOWED_MUTATION_KEYS]
        forbidden = [k for k in patch.get("actions", []) if k in FORBIDDEN_ACTIONS]
        if illegal or forbidden:
            decision = {
                "accepted": False,
                "illegal_keys": illegal,
                "forbidden_actions": forbidden,
            }
            self.history.append(decision)
            return decision
        before = deepcopy(self.genome.params)
        self.genome.params.update({k: v for k, v in patch.items() if k in ALLOWED_MUTATION_KEYS})
        decision = {
            "accepted": True,
            "before": before,
            "after": deepcopy(self.genome.params),
            "fingerprint": self.genome.fingerprint(),
        }
        self.history.append(decision)
        return decision


def mutate_genome(genome: EvolutionGenome, patch: dict[str, Any]) -> tuple[EvolutionGenome, dict[str, Any]]:
    ws = EvolverWorkspace(genome=deepcopy(genome))
    decision = ws.propose(patch)
    return ws.genome, decision


def legal_program_from_genome(genome: EvolutionGenome, referring_expression: str, property_name: str) -> list[dict[str, Any]]:
    """Compile a generic program from genome op order — not item-hardcoded."""
    program = []
    for op in genome.params.get("op_order_template", []):
        if op == "locate_event":
            program.append({"op": op, "inputs": {"cue": referring_expression}})
        elif op == "resolve_reference":
            program.append({"op": op, "inputs": {"referring_expression": referring_expression}})
        elif op == "track_identity":
            program.append({"op": op, "inputs": {}})
        elif op == "query_property":
            program.append({"op": op, "inputs": {"property_name": property_name}})
        elif op == "verify_answer":
            program.append(
                {
                    "op": op,
                    "inputs": {
                        "interval_a": {"start_s": 0.0, "end_s": 10.0},
                        "interval_b": {"start_s": 20.0, "end_s": 30.0},
                    },
                }
            )
    return program
