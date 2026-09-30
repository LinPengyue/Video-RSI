"""Conservative global visual routing from public question text only."""
import re
if __package__:
    from .time_utils import question_time_references
else:
    from time_utils import question_time_references


def global_visual_scope(item):
    question = str(item.get('question', '')).lower()

    if question_time_references(question, float(item.get('duration', 0))):
        return None
    if re.search(r'\d+:\d{2}|\b\d+(?:\.\d+)?\s*(seconds?|minutes?|hours?)\b|\d+\s*(?:秒|分钟|小时)', question):
        return None
    if re.search(r'\b(how many|how much|number of|count|occurrences|times|why)\b|多少|几次|数量|为什么', question):
        return None
    if re.search(r'\b(beginning|opening|start|ending|end|first|last)\b|开头|结尾|开始时|结束时', question):
        return None
    if re.search(r'\b(main topic|main purpose|primary purpose|best title|summari[sz]e|according to|said|says|say|mention|mentions|explain|explains)\b|主旨|主题|总结|说了|提到|解释', question):
        return None
    if re.search(r'\b(order of (?:the )?(?:actions|events)|sequence of (?:the )?(?:actions|events)|chronological order|actual order|in what order|which order|correct order|correct sequence|actions as they actually appear|events as they occur)\b|动作.*顺序|事件.*顺序|先后顺序', question):
        return 'global_sequence'

    if re.search(r'\b(before|after|during|when)\b|之前|之后|期间|时候', question):
        return None
    visual_attribute = re.search(
        r'\b(color|colour|shape|expression|emotion|wearing|clothing|outfit|holding|gesture|appearance)\b'
        r'|\b(word|text|letter|number)\b.*\b(shown|displayed|written|spelled|screen)\b'
        r'|\b(what|which)\s+(animal|object|toy|vehicle|instrument)\b.*\b(shown|visible|appear|appears|video)\b'
        r'|颜色|形状|表情|穿着|手势|画面.*(?:文字|字母)|什么动物', question)
    visual_event_patterns = re.search(
        r'\bwhat is the (woman|man|child|person)\b.*\b(doing|holding|wearing)\b'
        r'|\bcollision events?\b', question)
    if visual_attribute or visual_event_patterns:
        return 'global_unknown_location'
    return None


def global_visual_instruction(scope):
    common = (
        'The conditional global_visual64 route supplies one chronological 64-frame '
        'whole-video observation before normal reasoning. ASR remains context, not '
        'proof of a physical event or visible attribute. Do not repeat overview or '
        'a whole-video scan after this observation. If it failed, use ordinary '
        'tools to recover. Use program-bound frame references for local follow-up. '
    )
    if scope == 'global_sequence':
        return common + (
            'Match distinct target events to observed frames. Preserve the existing '
            'graph order/option check when available. If an event is missing or '
            'uncertain, investigate that gap; do not invent its time or force a '
            'direct answer merely because 64 frames were sampled.')
    return common + (
        'Find the requested visual target in the global observation. If its identity '
        'and the option-discriminating detail are clear, answer without unnecessary '
        'extra viewing. Otherwise inspect the relevant short interval or use OCR '
        'for visible text. If the target was not found, do not treat a different '
        'person/object as the target; choose a purposeful further search.')
