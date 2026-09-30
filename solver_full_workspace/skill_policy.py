"""Editable skill activation. No seed skills and no automatic Markdown loading.

Register dicts in SKILLS: name, scope ('global' or 'conditional'), prompt (text
or callable(context) -> text). Conditional entries also need when(context) ->
bool. Context contains public question/options/duration, observations and
remaining_steps, never dataset type labels or training annotations.

This selects instructions, not a forced tool workflow. Implement executable
workflows in the candidate's ordinary code when needed; this file is editable too.
"""
from copy import deepcopy


SKILLS = []


def select_skills(item, observations, remaining_steps):
    prompts = []
    selection = {"active": [], "inactive": [], "errors": []}
    names = set()
    for index, skill in enumerate(SKILLS):
        name = "entry_%d" % index
        try:
            name = skill["name"]
            if not isinstance(name, str) or not name.strip() or name in names:
                raise ValueError("skill name must be a nonempty unique string")
            names.add(name)
            scope = skill["scope"]
            context = deepcopy({"question": item["question"], "options": item["options"],
                                "duration": item["duration"], "observations": observations,
                                "remaining_steps": remaining_steps})
            if scope == "conditional":
                predicate = skill.get("when")
                if not callable(predicate):
                    raise ValueError("conditional skill needs a callable when(context)")
                matched = predicate(context)
                if type(matched) is not bool:
                    raise ValueError("skill condition must return bool, not text or a score")
                if not matched:
                    selection["inactive"].append(name)
                    continue
            elif scope != "global" or "when" in skill:
                raise ValueError("declare global without when, or conditional with when")
            body = skill["prompt"]
            body = body(context) if callable(body) else body
            if not isinstance(body, str) or not body.strip():
                raise ValueError("active skill prompt must be nonempty text")
            prompts.append("Active %s skill [%s]:\n%s" % (scope, name, body))
            selection["active"].append({"name": name, "scope": scope})
        except Exception as exc:

            selection["errors"].append({"name": str(name), "error": type(exc).__name__ + ": " + str(exc)})
    return prompts, selection
