"""Typed Evidence Contract Evolution — Track A RSI mechanism prototype.

Research code name: Typed Evidence Contract Evolution (TECE).
No expensive model calls. Operates on simulated execution traces.
"""

from .contracts import (
    AmbiguityFlag,
    EvidenceRef,
    EntityCandidate,
    OperationName,
    OperationRequest,
    OperationResult,
    TimeSpan,
)
from .executor import TypedEvidenceExecutor
from .evolver import EvolutionGenome, EvolverWorkspace, mutate_genome
from .counterfactual import CounterfactualSuite, run_counterfactual_suite
from .isolation import IsolationPolicy, assert_isolation
from .evolution_loop import run_ablation_suite, evolve, build_task_split, split_witness, run_multiseed_stress
from .evidence_graph import EvidenceDependencyGraph, EvidenceNode, BindingEdge

__all__ = [
    "AmbiguityFlag",
    "EvidenceRef",
    "EntityCandidate",
    "OperationName",
    "OperationRequest",
    "OperationResult",
    "TimeSpan",
    "TypedEvidenceExecutor",
    "EvolutionGenome",
    "EvolverWorkspace",
    "mutate_genome",
    "CounterfactualSuite",
    "run_counterfactual_suite",
    "IsolationPolicy",
    "assert_isolation",
    "run_ablation_suite",
    "evolve",
    "build_task_split",
    "split_witness",
    "run_multiseed_stress",
    "EvidenceDependencyGraph",
    "EvidenceNode",
    "BindingEdge",
]
