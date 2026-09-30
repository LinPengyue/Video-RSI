"""Conditional skill activation from public question context.

Register dicts in SKILLS: name, scope ('global' or 'conditional'), prompt (text
or callable(context) -> text). Conditional entries also need when(context) ->
bool. Context contains public question/options/duration, observations and
remaining_steps, never dataset type labels or training annotations.

This selects instructions rather than forcing a tool workflow.
"""
import re
from copy import deepcopy
if __package__:
    from .graph_scope import graph_scope
    from .visual_route import global_visual_instruction
else:
    from graph_scope import graph_scope
    from visual_route import global_visual_instruction





_TIME = r'\d{1,2}:\d{2}(?::\d{2})?'





_ENTITY_NOUNS = (
    r'(?:speaker|driver|song|set|game|half|inning|animal|person|man|woman|player'
    r'|team|member|contestant|guest|host|chef|vlogger|reporter|judge|dancer'
    r'|singer|actor|actress|boy|girl|child|kid|people|two|three|four|five|six'
    r'|seven|eight|nine|ten)'
)


def _is_start_of_video_question(question):
    """True when the question asks about the very start/opening of the video.

    Matches 'first/opening/beginning/initial/earliest ... in/of the video' or
    '... to appear in the video', while excluding ordinals that modify a
    specific entity (first speaker, first set, first inning, ...).
    """
    ql = (question or '').lower()
    m = re.search(r'\b(first|opening|beginning|initial|earliest)\b', ql)
    if not m:
        return False
    after = ql[m.end():m.end() + 40]
    if re.match(r'\s*' + _ENTITY_NOUNS + r'\b', after):
        return False
    return bool(re.search(
        r'\b(?:in|of)\s+the\s+video\b|\b(?:to\s+)?appear\s+in\s+the\s+video\b',
        ql))


def _is_explicit_interval_question(question):
    """True when the question names an explicit time range (from X to Y,
    between X and Y, during X-Y, or a bare X-Y), where X/Y are clock times."""
    ql = (question or '').lower()
    if re.search(r'\bfrom\s+' + _TIME + r'\s*(?:to|[-–—~])\s*' + _TIME, ql):
        return True
    if re.search(r'\bbetween\s+' + _TIME + r'\s+and\s+' + _TIME, ql):
        return True
    if re.search(r'\bduring\s+' + _TIME + r'\s*[-–—~]\s*' + _TIME, ql):
        return True
    if re.search(r'(?<!\w)' + _TIME + r'\s*[-–—~]\s*' + _TIME + r'(?!\w)', ql):
        return True
    return False


_START_OF_VIDEO_PROMPT = (
    "This question asks about the very start or opening of the video. The "
    "overview tool samples the whole video uniformly and does NOT reliably "
    "capture the first few seconds; its spacing is coarse. To answer a "
    "'first / opening / beginning' question, localize to the video start with "
    "inspect_interval over a short window near 0 seconds (for example 0 to "
    "min(16, duration) seconds), and read the actual first frames. "
    "Do not rely on overview alone for the video's opening moments."
)

def _should_offer_graph(context):
    return graph_scope(context, context['observations'], context['remaining_steps']) is not None


_RELATIONAL_PROMPT = (
    "A relation check is available after relevant observations covering multiple grounded events. Before answering an "
    "event-order question, use query_video_graph once so the accumulated evidence is compiled "
    "into explicit temporal relations. Its option_match compares that order with every answer "
    "choice. If unique_verified_option is present, keep the final answer letter consistent with it "
    "unless later concrete evidence invalidates the graph. If evidence_gaps needs evidence, target "
    "the named missing/uncertain event or relation, then query the graph again. Query the observed "
    "events or people, not an unrelated timeline. The graph adds no observations and "
    "cannot locate a missing scene, repair uncertain visual recognition, or count events. "
    "Do not treat an unknown relation as a negative fact or as support for an option."
)

_EXPLICIT_INTERVAL_PROMPT = (
    "This question names an explicit time range. If the transcript already "
    "unambiguously resolves what happens across the full range, you may answer "
    "from it. Otherwise localize to that range with scan_interval or "
    "inspect_interval (at most16 seconds per call; use multiple short windows when needed) "
    "and cover the WHOLE range including its end — a key detail "
    "often appears at the very end of the stated interval, and a window that "
    "stops short of the end will miss it. The transcript is a localization aid, "
    "not a substitute for visual content: when the question asks what is shown "
    "or what happens over a specific interval and the transcript does not settle "
    "it, observe the range visually before answering."
)

SKILLS = [
    {
        'name': 'conditional_global64',
        'scope': 'conditional',
        'when': lambda context: context.get('visual_route') is not None,
        'prompt': lambda context: global_visual_instruction(context['visual_route']),
    },
    {
        "name": "start_of_video_localization",
        "scope": "conditional",
        "when": lambda context: _is_start_of_video_question(context["question"]),
        "prompt": _START_OF_VIDEO_PROMPT,
    },
    {
        "name": "explicit_interval_localization",
        "scope": "conditional",
        "when": lambda context: _is_explicit_interval_question(context["question"]),
        "prompt": _EXPLICIT_INTERVAL_PROMPT,
    },
    {
        "name": "relational_graph_hint",
        "scope": "conditional",
        "when": _should_offer_graph,
        "prompt": _RELATIONAL_PROMPT,
    },
]


def select_skills(item, observations, remaining_steps, visual_route=None):
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
                                "remaining_steps": remaining_steps,
                                "visual_route": visual_route})
            if scope == "conditional":
                predicate = skill.get("when")
                if not callable(predicate):
                    raise ValueError("conditional skill needs a callable when(context)")
                matched = predicate(context)
                if type(matched) is not bool:
                    raise ValueError("skill condition must return bool, not text or a score")
                if not matched:
                    if name != 'relational_graph_hint':
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
