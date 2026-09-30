import json
import re
if __package__:
    from .visual_route import global_visual_scope
else:
    from visual_route import global_visual_scope


_STOP = set('the a an of in on at to from and or is are was were be does do did what which who when how it its his her their they he she first last before after then next video scene shown shows show option options answer question'.split())


def _tokens(text):
    return {w for w in re.findall(r'[a-z]+', text.lower()) if len(w) > 2 and w not in _STOP}


def graph_scope(item, observations, remaining_steps):
    if remaining_steps <= 1:
        return None
    question = item.get('question', '').lower()
    if re.search(r'\b(how many|how much|number of|count|why)\b', question):
        return None
    if re.search(r'\b(relationship between|relation between|whose)\b|\bwho\s+(?:is|was)\s+(?:the\s+)?(?:president|chairman|director|owner|founder|captain|leader)\b', question):
        mode = 'entity_relation'
    elif global_visual_scope(item) == 'global_sequence' or re.search(r'\b(in what order|which order|sequence|earlier|later)\b|\bwhat\b.*\b(do|happens|happened|events)\b.*\b(before|after|between)\b|\bwhich\b.*\b(first|last)\b', question):
        mode = 'event_order'
    else:
        return None
    entries = list(observations)
    last_graph = max((i for i, e in enumerate(entries) if e.get('tool') == 'query_video_graph'), default=-1)
    options = item.get('options', {})
    option_values = list(options.values()) if isinstance(options, dict) else list(options)
    option_tokens = [_tokens(str(v)) for v in option_values]
    anchors = _tokens(question) | set().union(*option_tokens)
    relevant = []
    seen = set()
    distinct_visual = []
    grounded_visual_facts = 0
    for index, entry in enumerate(entries):
        if entry.get('tool') not in ('overview', 'global_visual64', 'scan_interval', 'inspect_interval', 'read_text'):
            continue
        observation = entry.get('observation', {})
        if not isinstance(observation, dict) or observation.get('error') or observation.get('reused_observation'):
            continue
        frame_times = tuple(f.get('timestamp') for f in observation.get('frames', []) if isinstance(f, dict))
        arguments = entry.get('arguments', {}) or {}
        key = (entry.get('tool'), frame_times, arguments.get('start'), arguments.get('end'))
        if key in seen:
            continue
        seen.add(key)
        distinct_visual.append(index)
        perception = observation.get('perception', {})
        if isinstance(perception, dict) and isinstance(perception.get('observations'), list):
            grounded_visual_facts += sum(
                bool(row.get('frame_references')) for row in perception['observations']
                if isinstance(row, dict))
        text = json.dumps(perception, ensure_ascii=False) if isinstance(perception, dict) else str(perception)
        if entry.get('tool') == 'read_text':
            text = ' '.join(str(d.get('text', '')) for d in observation.get('raw_detections', observation.get('detections', [])) if isinstance(d, dict))
        words = _tokens(text)
        if len(words & anchors) < 2:
            continue
        if re.search(r'(?:specific|target|requested|key)\s+(?:\w+\s+){0,6}(?:not (?:shown|visible|captured|present)|absent)|(?:no|without)\s+(?:clear\s+)?(?:visual\s+)?evidence\s+(?:of|for)\s+(?:the\s+)?(?:specific|target|requested)', text, re.I):
            continue
        hits = {i for i, terms in enumerate(option_tokens) if terms and len(terms & words) >= min(2, len(terms))}
        relation_gap = bool(re.search(r'(?:order|sequence|identity|relationship|role|attribute)\s+(?:\w+\s+){0,5}(?:unclear|uncertain|ambiguous|conflict|cannot|not (?:confirmed|determined|established))|(?:cannot|unable to)\s+(?:\w+\s+){0,4}(?:order|sequence|identity|relationship)|(?:conflicting|contradictory)\s+(?:\w+\s+){0,3}(?:order|sequence|identity|relationship|role|attribute)', text, re.I))
        relevant.append((index, hits, relation_gap))


    if (mode == 'event_order' and distinct_visual and distinct_visual[-1] > last_graph
            and (len(distinct_visual) >= 2 or grounded_visual_facts >= 2)):
        return mode
    if len(relevant) < 2 or relevant[-1][0] <= last_graph:
        return None
    if not any(gap for _, _, gap in relevant) and len(set().union(*(hits for _, hits, _ in relevant))) < 2:
        return None
    return mode
