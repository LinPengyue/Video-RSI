"""Candidate-owned online solve loop."""
import json
from agent import Agent
from memory import Memory
from tools import ToolBox


def solve(item, services, budget):
    memory = Memory()
    toolbox = ToolBox(item, services, budget)
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


    try:
        transcript = toolbox.execute('read_transcript', {})
    except Exception as exc:
        transcript = {"error": type(exc).__name__, "message": str(exc)}
    memory.add({"tool": "read_transcript", "arguments": {}}, transcript)

    if toolbox.needs_occurrence_survey():
        survey_decision = {"type": "tool", "tool": "survey_occurrences", "arguments": {}}
        try:
            survey = toolbox.execute('survey_occurrences', {}, memory.items)
        except Exception as exc:
            survey = {"error": type(exc).__name__, "message": str(exc)}
        memory.add(survey_decision, survey)
        trace.append({"step": "pre_count_survey", "decision": survey_decision,
                      "skill_selection": {"active": [], "inactive": [], "errors": []},
                      "decision_attempts": [], "observation": survey})
    for step in range(budget["max_steps"]):


        if (step == 0 and budget['max_steps'] > 1
                and toolbox.global_visual_scope is not None):
            decision = {'type': 'tool', 'tool': 'global_visual64', 'arguments': {}}
            try:
                observation = toolbox.execute('global_visual64', {})
            except Exception as exc:
                observation = {'error': type(exc).__name__, 'message': str(exc)}
            memory.add(decision, observation)
            trace.append({'step': step, 'decision': decision,
                          'route_selection': {'search_scope': toolbox.global_visual_scope,
                                              'source': 'public_question_rules'},
                          'skill_selection': {'active': [], 'inactive': [], 'errors': []},
                          'decision_attempts': [], 'observation': observation})
            continue
        try:
            decision = agent.decide(memory, step, budget["max_steps"])
        except ValueError as exc:
            if not str(exc).startswith("invalid_decision:"):
                raise
            trace.append({"step": step, "error": str(exc), "skill_selection": agent.skill_selection, 'decision_attempts': agent.decision_attempts})
            return finish('invalid_decision', error=str(exc))
        trace.append({"step": step, "decision": decision, "skill_selection": agent.skill_selection, 'decision_attempts': agent.decision_attempts})
        if decision["type"] == "answer":
            graph_args = toolbox.default_event_order_query()
            if graph_args is not None:
                deferred = decision
                decision = {"type": "tool", "tool": "query_video_graph", "arguments": graph_args}
                trace[-1]["decision"] = decision
                trace[-1]["deferred_answer"] = deferred
                try:
                    observation = toolbox.execute('query_video_graph', graph_args, memory.items)
                except Exception as exc:
                    observation = {"error": type(exc).__name__, "message": str(exc)}
                memory.add(decision, observation)
                trace[-1]["observation"] = observation
                continue
            return finish('answered', decision['answer'])
        try:
            observation = agent.argument_error if agent.argument_error is not None else toolbox.execute(decision["tool"], decision.get("arguments", {}), memory.items)
        except Exception as exc:
            observation = {"error": type(exc).__name__, "message": str(exc)}
        memory.add(decision, observation)
        trace[-1]["observation"] = observation
    return finish('invalid_decision')
