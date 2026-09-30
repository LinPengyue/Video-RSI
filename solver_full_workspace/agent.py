import json
from pathlib import Path
from answers import parse_decision_details
from skill_policy import select_skills
from time_utils import question_time_references
from tools import ToolArgumentError


class Agent:
    def __init__(self, item, services, tools):
        self.item, self.services, self.tools = item, services, tools
        self.root = Path(__file__).parent

    def decide(self, memory, step, max_steps):
        self.decision_attempts = []
        self.argument_error = None
        remaining = max_steps - step
        skills, self.skill_selection = select_skills(self.item, memory.items, remaining)
        payload = {"item": self.item, "tools": self.tools.descriptions(), "observations": memory.items,
                   "step": step, "remaining_steps": remaining}
        references = question_time_references(self.item['question'], self.item['duration'])
        if references:
            payload['question_time_references'] = references
        messages = [
            {"role": "system", "content": self.root.joinpath("prompt.md").read_text() + "\n" + "\n".join(skills)},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        for attempt in range(2):
            response = self.services.call("deepseek", {"messages": messages})
            text = response["text"]
            record = {'attempt': attempt, 'raw_response': text}
            self.decision_attempts.append(record)
            try:
                decision, parse_mode = parse_decision_details(text, self.item["options"])
                record['parse_mode'] = parse_mode
                record['proposed_decision'] = decision
                if remaining <= 1 and decision["type"] != "answer":
                    raise ValueError("last step requires a terminal answer; no tool action will execute")
                if decision['type'] == 'tool':
                    decision = dict(decision, arguments=self.tools.normalize_arguments(decision['tool'], decision.get('arguments', {})))
                record.update(status='accepted', decision=decision)
                return decision
            except (ValueError, TypeError) as exc:
                semantic = isinstance(exc, ToolArgumentError)
                record.update(status='rejected', error_kind='tool_arguments' if semantic else 'response_format', error=str(exc))
                if attempt:
                    if semantic:

                        self.argument_error = {'error': 'ToolArgumentError', 'message': str(exc), 'stage': 'pre_dispatch', 'repair_exhausted': True}
                        return decision
                    raise ValueError("invalid_decision: " + str(exc))
                if semantic:
                    repair = (
                        'Tool argument repair: no tool has executed and no observation was obtained. '
                        'Correct the action using the listed tool bounds and question_time_references if present. '
                        'Numbers are seconds; explicit MM:SS / HH:MM:SS strings are converted by the program. '
                        'Choose a valid tool/window; do not repeat the same invalid arguments. '
                        'This is not a request to answer prematurely. Return one JSON action or answer. '
                        'Only one repair is allowed in this decision; provider cost is still counted. '
                    )
                elif remaining <= 1:
                    repair = (
                        'Response repair: this is the last step. Return only '
                        '{"type":"answer","answer":"<option_letter>","reason":"..."}. '
                        'Select your best-supported single option from ' + ", ".join(self.item["options"]) +
                        '. No further tool action will execute. Do not invent evidence. '
                    )
                else:
                    repair = (
                        'Response repair: return one JSON tool action or terminal answer using the response protocol. '
                        'Keep your intended action if it is valid; this is not a request to answer prematurely. '
                        'If answering, use one actual option from ' + ", ".join(self.item["options"]) + '. '
                    )
                messages.extend([
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": repair + "Issue: " + str(exc)},
                ])
