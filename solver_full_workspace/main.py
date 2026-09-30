"""Initial online solve loop."""
import json
from agent import Agent
from memory import Memory
from tools import ToolBox


def solve(item, services, budget):
    memory = Memory()
    toolbox = ToolBox(item, services)
    agent = Agent(item, services, toolbox)
    trace = []
    def finish(status, answer=None, **extra):
        attempts = [a for t in trace for a in t.get('decision_attempts', [])]
        diagnostics = {
            'tool_argument_errors': sum(a.get('error_kind') == 'tool_arguments' for a in attempts),
            'decision_repair_calls': sum(a['attempt'] > 0 for a in attempts),
            'locally_extracted_decisions': sum(a.get('parse_mode') == 'extracted_json' for a in attempts),
            'tool_execution_errors': sum('error' in t.get('observation', {}) and t['observation'].get('stage') != 'pre_dispatch' for t in trace),
        }
        return dict(status=status, answer=answer, trace=trace, memory=memory.items, diagnostics=diagnostics, **extra)
    for step in range(budget["max_steps"]):
        try:
            decision = agent.decide(memory, step, budget["max_steps"])
        except ValueError as exc:
            if not str(exc).startswith("invalid_decision:"):
                raise
            trace.append({"step": step, "error": str(exc), "skill_selection": agent.skill_selection, 'decision_attempts': agent.decision_attempts})
            return finish('invalid_decision', error=str(exc))
        trace.append({"step": step, "decision": decision, "skill_selection": agent.skill_selection, 'decision_attempts': agent.decision_attempts})
        if decision["type"] == "answer":
            return finish('answered', decision['answer'])
        try:
            observation = agent.argument_error if agent.argument_error is not None else toolbox.execute(decision["tool"], decision.get("arguments", {}))
        except Exception as exc:
            observation = {"error": type(exc).__name__, "message": str(exc)}
        memory.add(decision, observation)
        trace[-1]["observation"] = observation
    return finish('invalid_decision')
