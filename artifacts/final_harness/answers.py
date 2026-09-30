import json
import re


def _json_objects(text):
    """Yield complete top-level JSON-object substrings in textual order."""
    start = None
    depth = 0
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start:index + 1]
                start = None


def _validate(value, options):
    if not isinstance(value, dict):
        raise ValueError("decision must be an object")
    if value.get("type") == "answer":
        answer = str(value.get("answer", "")).strip().upper()
        if answer not in options:
            raise ValueError("submit exactly one actual option: " + ",".join(options))
        value["answer"] = answer
    elif value.get("type") != "tool" or not isinstance(value.get("tool"), str) or not isinstance(value.get("arguments", {}), dict):
        raise ValueError("expected a tool action or final answer")
    return value


def parse_decision_details(text, options):
    """Parse a decision without another model call.

    Strict JSON remains the first choice. If the model wrapped its final action
    in reasoning text or a Markdown fence, use the last complete JSON object
    whose ``type`` identifies it as a decision. Validation is unchanged: an
    extracted action cannot bypass option, shape, tool or argument checks.
    """
    text = text.strip()
    if text in options:
        return {"type": "answer", "answer": text}, "bare_option"
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    strict = match.group(1) if match else text
    try:
        return _validate(json.loads(strict), options), "strict_json" if not match else "json_fence"
    except json.JSONDecodeError as strict_error:
        candidates = list(_json_objects(text))
        for candidate in reversed(candidates):
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict) or value.get("type") not in ("answer", "tool"):
                continue


            return _validate(value, options), "extracted_json"
        raise strict_error


def parse_decision(text, options):
    return parse_decision_details(text, options)[0]
