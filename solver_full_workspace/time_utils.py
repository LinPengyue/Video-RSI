"""Editable, deterministic time units. Never infer answers or localize events."""
import math
import re


def seconds(value):
    """Numbers mean seconds; only explicit colon strings mean clock notation."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('time must be numeric seconds or an explicit MM:SS / HH:MM:SS string')
    if isinstance(value, str) and ':' in value:
        value = value.strip()
        if not re.fullmatch(r'\d+:\d{2}(?::\d{2})?(?:\.\d+)?', value):
            raise ValueError('use MM:SS or HH:MM:SS; for example 15:04 means 904 seconds')
        parts = [float(p) for p in value.split(':')]
        if any(p >= 60 for p in parts[1:]):
            raise ValueError('seconds, and minutes within HH:MM:SS, must be below 60')
        number = sum(p * 60 ** i for i, p in enumerate(reversed(parts)))
    else:
        try:
            number = float(value)
        except (ValueError, OverflowError):
            raise ValueError('time must be numeric seconds or MM:SS / HH:MM:SS') from None
    if not math.isfinite(number) or number < 0:
        raise ValueError('time must be finite and nonnegative')
    return number


def question_time_references(question, duration):
    """Conservative textual hints, not mandatory routes or hidden annotations.

    Only question text in an explicit temporal context is considered. Scores,
    ratios and match/display clocks are not mapped to video elapsed time.
    Unrecognized/ambiguous wording stays untouched for the model to interpret.
    """
    references = []
    last_end = None
    pattern = r'(?<![\w:.])\d+:\d{2}(?::\d{2})?(?:\.\d+)?(?![\w:.])'
    for match in re.finditer(pattern, question):
        prefix = question[:match.start()]
        context = prefix[-80:]
        temporal = re.search(r'\b(at|after|before|from|between|around|during|for|timestamp|timecode)\s*[\"\'（(]?\s*$', context, re.I)
        temporal = temporal or re.search(r'(?:在|从|第|时间|时刻)\s*$', context)
        range_end = last_end is not None and re.fullmatch(r'\s*(?:[-–—~]|to|and|至|到)\s*', question[last_end:match.start()], re.I)
        ambiguous = re.search(r'\b(score|ratio|clock|timer|a\.?m\.?|p\.?m\.?)\b|比分|计时器|比赛时钟', context, re.I)
        ambiguous = ambiguous or re.match(r'\s*(?:[ap]\.?m\.?\b|上午|下午)', question[match.end():], re.I)
        last_end = None
        if ambiguous or not (temporal or range_end):
            continue
        try:
            value = seconds(match.group())
        except ValueError:
            continue
        if value > float(duration):
            continue
        references.append({'text': match.group(), 'seconds': value,
                           'source': 'question_text', 'character_span': [match.start(), match.end()]})
        last_end = match.end()
    return references
