"""Visual observation, counting, and evidence-graph tools."""
from math import ceil
import json
import re
from copy import deepcopy
if __package__:
    from .time_utils import seconds, question_time_references
    from .graph import VideoGraph
    from .graph_scope import graph_scope
    from .occurrence_counter import OccurrenceCounter
    from .visual_route import global_visual_scope
else:
    from time_utils import seconds, question_time_references
    from graph import VideoGraph
    from graph_scope import graph_scope
    from occurrence_counter import OccurrenceCounter
    from visual_route import global_visual_scope


class ToolArgumentError(ValueError):
    """Repairable before media/provider execution; not a provider failure."""




_COUNT_PATTERNS = [
    r'\bhow\s+many\b',
    r'\bhow\s+much\b',
    r'\bnumber\s+of\b',
    r'\btotal\s+(?:number\s+)?of\b',
    r'\bcount\b',
    r'\bmaximum\s+number\b',
    r'几[个位只块台道场名条辆件张把支根颗粒片座间家口头匹朵棵株艘架部本册页首句段篇幅]',
    r'多少',
    r'数量',
]
_COUNT_RE = re.compile('|'.join(_COUNT_PATTERNS), re.IGNORECASE)

_COUNT_INSTRUCTION = (
    "This question asks for a count or quantity. Count conservatively and precisely: "
    "(1) First restate exactly what is being counted, distinguishing 'present/appearing' "
    "from 'acting/speaking/using/doing' — count only what the question actually asks for. "
    "(2) Enumerate each counted item individually and cite its one-based image_index; "
    "do NOT count partially-visible, occluded, background-blurred, or merely symmetry-inferred "
    "items as confirmed. If a count is uncertain, state the range (e.g. '3 or 4') and which "
    "item is ambiguous rather than committing to a single number. "
    "(3) If the question names a time interval, note whether the sampled window covers the "
    "interval's end — a key item often appears at the very end. "
    "(4) If the counted object's term is ambiguous, state your interpretation before counting. "
)


def is_count_question(question):
    """True when the question asks for a count/quantity. Public text only."""
    return bool(question) and bool(_COUNT_RE.search(question))


def is_global_occurrence_count(question):
    text = str(question or '').lower()
    if not is_count_question(text):
        return False
    if question_time_references(text, 1e9):
        return False
    if re.search(r'\b(?:at|near|during)\s+(?:the\s+)?(?:beginning|start|opening|end|ending)\b', text):
        return False
    return bool(re.search(r'\b(?:throughout|whole video|entire video|how many times|occurrences|instances)\b', text))


_GRAPH_EXTRACTION_PROMPT = (
    "Extract a graph delta using NEW observations only. The question, options and query "
    "identify the information needed; they are hypotheses, never observed facts. Do not answer. "
    "The existing graph supplies identity mappings, not independent evidence. Return JSON: "
    "{entities:[{id,name,type,aliases,attributes:[{attribute,value,polarity,confidence,evidence,uncertainty}],"
    "uncertainty,evidence}], events:[{id,name,aliases,time_start,time_end,participants,location,"
    "uncertainty,evidence}], relations:[{subject,predicate,object,polarity,confidence,evidence,uncertainty}]}. "
    "Reuse existing node IDs only for confirmed same instances. Distinct people or repeated "
    "events need distinct new IDs even when names coincide. Preserve uncertainty in identity. "
    "Use node IDs for participants and relation endpoints; aliases may include the query's "
    "wording only when it truly refers to that node. Evidence must contain exact supplied "
    "source_id values, not invented quotes. Include frame or segment source IDs for time claims. "
    "Time is numeric video seconds, never a displayed clock or image index; leave null if "
    "unbound. Do not infer continuous coverage between sparse frames. "
    "polarity is positive/negative; confidence is high/medium/low. For Boolean attributes "
    "use a Boolean value with positive polarity. Negative relations deny only their exact "
    "subject-predicate-object, not other objects. Put uncertain owner, alternatives and "
    "unresolved identity in uncertainty, not a confirmed fact. Keep distinct times separate. "
    "Return empty lists when no new facts are extractable."
)


def _extract_graph_json(text):
    if not isinstance(text, str):
        raise ValueError('graph extraction must be text')
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{', text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and all(isinstance(value.get(k), list) for k in ('entities', 'events', 'relations')):
            return value
    raise ValueError('no complete graph JSON with entities/events/relations lists')


def _extract_json_object(text):
    if not isinstance(text, str):
        return None
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{', text):
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


_MODEL_TIME_RE = re.compile(
    r'(?i)(?:(?:at|around|near|timestamp(?:_seconds)?\s*[=:]?)\s*)?'
    r'(?<![\w.])\d+(?:\.\d+)?\s*(?:seconds?|secs?|sec|s)\b'
    r'|(?:(?:at|around|near|timestamp)\s*)\d{1,2}:\d{2}(?::\d{2})?'
)


def _remove_model_times(text):
    """Keep visual semantics while preventing free-form time from becoming an anchor."""
    return _MODEL_TIME_RE.sub('[time omitted; use frame_references]', text)


def _bound_visual_response(result, frames):
    """Bind provider-local image references to trusted video seconds.

    Qwen may describe content, but it never gets to author a time anchor.  Its
    raw response remains in the external service trace for audit; only
    observations citing valid one-based image indices enter Solver memory.
    """
    raw = result.get('text', '') if isinstance(result, dict) else ''
    obj = _extract_json_object(raw)
    if not isinstance(obj, dict) or not isinstance(obj.get('observations'), list):
        return {
            'status': 'ungrounded_response',
            'usable': False,
            'message': ('The visual response did not provide grounded image-index observations. '
                        'No model-written timestamp or ungrounded description is usable.'),
        }
    observations = []
    for row in obj['observations']:
        if not isinstance(row, dict):
            continue
        indices = row.get('image_indices')
        if isinstance(row.get('image_index'), int):
            indices = [row['image_index']]
        if not isinstance(indices, list):
            continue
        refs, seen = [], set()
        for index in indices:
            if (isinstance(index, int) and not isinstance(index, bool) and
                    1 <= index <= len(frames) and index not in seen):
                frame = frames[index - 1]
                refs.append({'image_index': index, 'frame_id': frame['id'],
                             'timestamp_seconds': frame['timestamp']})
                seen.add(index)
        evidence = row.get('visible_evidence')
        if not refs or not isinstance(evidence, str) or not evidence.strip():
            continue
        bound = {
            'frame_references': refs,
            'visible_evidence': _remove_model_times(evidence.strip()),
            'confidence': row.get('confidence', 'unknown'),
        }
        for field in ('identity', 'uncertainty'):
            if isinstance(row.get(field), str) and row[field].strip():
                bound[field] = _remove_model_times(row[field].strip())
        observations.append(bound)
    unresolved = obj.get('unresolved', [])
    if not isinstance(unresolved, list):
        unresolved = [str(unresolved)] if unresolved else []
    unresolved = [str(value) for value in unresolved if str(value).strip()]
    return {
        'status': 'grounded' if observations else 'no_grounded_observations',
        'usable': bool(observations),
        'time_authority': 'program_bound_from_image_index',
        'observations': observations,
        'unresolved': unresolved,
    }


def transcript_view(result):
    """All utterances and segment times, without per-word preprocessing metadata.

    The service trace/source file retains the original objects. This is a
    lossless spoken-text view, not a summary, retrieval result or length cap.
    """
    return dict(result, segments=[{key: segment[key] for key in ('start', 'end', 'text')}
                                 for segment in result.get('segments', [])])


class ToolBox:
    def __init__(self, item, services, budget=None):
        self.item, self.services = item, services
        self.budget = budget or {'max_frames': 256}
        self.occurrence_result = None
        self.transcript_read = False
        self.graph = VideoGraph()
        self.graph_observations = set()
        self.graph_sources = {}
        self.graph_mode = None
        self.graph_queried = False
        self.graph_has_new_evidence = False
        self.observed_windows = set()
        self.occurrence_survey_done = False
        self.global_visual_scope = global_visual_scope(item)
        if is_count_question(item['question']) or self.budget.get('max_frames', 256) < 64:
            self.global_visual_scope = None
        self.global64_attempted = False
        self.global64_result = None

    def prepare_graph_scope(self, observations, remaining_steps):
        self.graph_mode = graph_scope(self.item, observations, remaining_steps)
        self.graph_has_new_evidence = any(
            str(index) not in self.graph_observations
            and isinstance(entry, dict)
            and entry.get('tool') in (
                'read_transcript', 'overview', 'global_visual64', 'scan_interval',
                'inspect_interval', 'read_text')
            and isinstance(entry.get('observation'), dict)
            and not entry['observation'].get('error')
            and not entry['observation'].get('reused_observation')
            for index, entry in enumerate(observations))
        self.observed_windows = set()
        for entry in observations:
            tool = entry.get('tool')
            args = entry.get('arguments', {}) or {}
            if tool == 'inspect_interval' and 'start' in args and 'end' in args:
                try:
                    self.observed_windows.add((tool, round(float(args['start']), 3), round(float(args['end']), 3)))
                except (TypeError, ValueError):
                    pass

    def descriptions(self):
        duration = float(self.item['duration'])
        time_format = (' Times: numeric seconds or explicit "MM:SS"/"HH:MM:SS" strings; '
                       f'0 <= start < end <= {duration:g} seconds. No automatic clipping or splitting.')
        descriptions = {
            "overview": "Uniformly observe the whole video, exactly 32 frames; arguments {}. Sparse scene search, not continuous action footage.",
            "scan_interval": f'Coarse localization within a selected interval: 32 < end-start <= {duration / 2:g} seconds (half video). Exactly 16 uniform frames; start,end.' + (' Unavailable: this video has no interval satisfying these bounds.' if duration <= 64 else '') + time_format,
            "inspect_interval": "Observe local action progression and details: 0 < end-start <=16 seconds. Uniform samples across the entire interval, at most8 frames; count is automatic (min(8, ceil(duration in seconds))), do not supply count. Not fixed 1 FPS or continuous video; brief actions can be missed. Arguments start,end. Longer intervals require valid scan_interval or separately chosen short windows." + time_format,
            "read_text": "Local multilingual OCR, 1fps over 0 < end-start <=16 seconds. start,end. Returns timestamp,bbox,text,confidence. Locate the text first if its position is unknown." + time_format,
            "read_transcript": "Read all timestamped speech segments once, no keyword retrieval. {}.",
            "query_video_graph": (
                "Query the per-question knowledge graph built from your observations so far. "
                "It maintains entities, events and relations across steps and lets you check "
                "event order or entity-attribute support against the accumulated evidence. "
                "arguments: {\"query\":\"event_order\",\"events\":[\"event A\",\"event B\",...]} "
                "or {\"query\":\"entity_relation\",\"entity\":\"<name>\",\"predicate\":\"<attr>\","
                "\"object\":\"<optional expected value>\"}. "
                "Use it when multiple events must be ordered, when an attribute's owner is "
                "unclear, or when observations conflict on a key relation. It does NOT observe "
                "new frames, locate targets, read small text, or count items; it only reasons "
                "over what you have already observed. Use returned node IDs or known aliases "
                "for later queries; same-name events can be distinct instances. Clear single-window "
                "facts or unambiguous transcript answers usually do not need this tool. If the graph cannot decide, it returns "
                "undetermined/unknown with the specific gap, and you may answer or observe more."
                " For event-order questions it also compares the grounded order against every "
                "answer option and returns unique_verified_option only when exactly one option is "
                "fully supported. evidence_gaps names missing or uncertain targets for follow-up."
            ),
        }
        if self.global_visual_scope is not None:
            descriptions['global_visual64'] = (
                'Conditional whole-video observation: exactly 64 chronological uniform frames '
                'in one Qwen request, with the question and options as observation targets. '
                'Arguments {} or {"observation_goal":"specific visual question"}. '
                'After a successful call, all later calls reuse its observation without new frames; '
                'changing the goal does not run another global observation. '
                'Scope: ' + self.global_visual_scope + '.')
        if self.global64_result is not None:
            descriptions.pop('overview')
        if is_global_occurrence_count(self.item['question']):
            descriptions['survey_occurrences'] = (
                "Count distinct target scenes/action episodes across the video; arguments {}. "
                "One cached survey: 64 initial frames, offset gap scanning when needed, then "
                "local verification of candidate events. Up to192 Qwen frames, reserving64 for "
                "follow-up. Returns code-bound frame times, verified episodes and unresolved gaps. "
                "Observed count is not proof of exhaustive coverage."
            )
        if self.graph_mode is None:
            descriptions.pop('query_video_graph')
        else:
            descriptions['query_video_graph'] += ' Currently available query: ' + self.graph_mode + '.'
        for name in ('overview', 'global_visual64', 'scan_interval', 'inspect_interval'):
            if name in descriptions:
                descriptions[name] += (
                    ' Optional observation_goal (string): the specific uncertainty to inspect now. '
                    'Include relevant conflicting claims as unverified hypotheses; Qwen does not '
                    'see your full memory. Omit for the default question-focused observation.')
        descriptions['inspect_interval'] += (
            ' The same inspect_interval start/end cannot be inspected again, even with a new '
            'observation_goal. A prior overview or scan_interval does not block fine inspection.')
        return descriptions

    def normalize_arguments(self, name, args):
        """Single source for pre-dispatch repair and execution validation. No IO."""
        if name not in self.descriptions():
            raise ToolArgumentError('unknown tool ' + str(name) + '; choose a listed tool')
        if not isinstance(args, dict):
            raise ToolArgumentError('arguments must be an object')
        if name == 'query_video_graph':
            normalized = self._normalize_graph_args(args)
            if normalized['query'] != self.graph_mode:
                raise ToolArgumentError('graph query must match the available relation: ' + str(self.graph_mode))
            return normalized
        allowed = set() if name in ('overview', 'global_visual64', 'read_transcript', 'survey_occurrences') else {'start', 'end'}
        if name in ('overview', 'global_visual64', 'scan_interval', 'inspect_interval'):
            allowed.add('observation_goal')
        if set(args) - allowed:
            raise ToolArgumentError(f'{name}: unsupported arguments {sorted(set(args) - allowed)}; allowed {sorted(allowed)}')
        normalized = {}
        if 'observation_goal' in args:
            if not isinstance(args['observation_goal'], str):
                raise ToolArgumentError('observation_goal must be a string describing what to inspect')
            goal = args['observation_goal'].strip()
            if goal:
                normalized['observation_goal'] = goal
        if name in ('overview', 'global_visual64', 'read_transcript', 'survey_occurrences'):
            return normalized
        if not {'start', 'end'} <= set(args):
            raise ToolArgumentError(f'{name} requires start and end. ' + self.descriptions()[name])
        try:
            start, end = seconds(args['start']), seconds(args['end'])
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        duration = float(self.item['duration'])
        if not 0 <= start < end <= duration:
            raise ToolArgumentError(f'{name}: requested start={start:g}, end={end:g} seconds; require 0 <= start < end <= {duration:g}. Check time notation; no endpoint is swapped or clipped.')
        span = end - start
        normalized.update(start=start, end=end)
        if name == 'scan_interval' and not 32 < span <= duration / 2:
            raise ToolArgumentError(f'scan_interval requested {span:g}s; require 32 < span <= {duration / 2:g}s. Choose a valid coarse interval, short inspection, or overview; nothing was observed.')
        if name == 'inspect_interval':
            if span > 16:
                raise ToolArgumentError(f'inspect_interval requested {span:g}s; maximum 16s and at most8 uniform frames. Choose scan_interval if valid, or select a short window <=16s; no frames were sampled.')
        if name == 'read_text' and span > 16:
            raise ToolArgumentError(f'read_text requested {span:g}s; maximum 16s at 1fps. Locate the text first or select a <=16s window; no OCR was performed.')
        if name == 'inspect_interval':
            key = (name, round(start, 3), round(end, 3))
            if key in self.observed_windows:
                raise ToolArgumentError(
                    f'{name} interval {start:g}-{end:g}s was already observed; choose a distinct '
                    'window or answer from existing evidence. Changing observation_goal does not '
                    'permit repetition. No repeated observation was run.')
        return normalized

    def needs_occurrence_survey(self):
        return is_global_occurrence_count(self.item['question']) and not self.occurrence_survey_done

    def _survey_occurrences(self):
        if self.occurrence_result is not None:
            return self.occurrence_result
        counter = OccurrenceCounter(self.item, self.services, self.budget.get('max_frames', 256))
        self.occurrence_result = counter.run()
        self.occurrence_survey_done = True
        return self.occurrence_result

    def default_event_order_query(self):



        if self.graph_mode != 'event_order' or not self.graph_has_new_evidence:
            return None
        option_orders = self._event_order_options()
        events = []
        seen = set()
        for order in option_orders.values():
            for event in order:
                key = re.sub(r'^(?:a|an|the)\s+', '', event.lower()).strip()
                if key and key not in seen:
                    events.append(event)
                    seen.add(key)
        return {'query': 'event_order', 'events': events} if len(events) >= 2 else None

    def _event_order_options(self):
        """Parse public answer options into ordered atomic event labels."""
        options = self.item.get('options', {})
        pairs = options.items() if isinstance(options, dict) else (
            (chr(65 + i), value) for i, value in enumerate(options))
        result = {}
        for letter, value in pairs:
            events = [part.strip() for part in
                      re.split(r'\s*(?:-->|→|,)\s*', str(value))
                      if part.strip()]
            if len(events) >= 2:
                result[str(letter)] = events
        return result

    def _match_event_order_options(self):
        """Compare each answer option with the evidence-derived graph order."""
        details = {}
        for letter, events in self._event_order_options().items():
            query = self.graph.query_event_order(events)
            relations = query.get('pairs', [])
            after = [row for row in relations
                     if row.get('relation') in ('after', 'conflict')]
            unknown = [row for row in relations
                       if row.get('relation') == 'unknown']
            missing = query.get('missing', [])
            uncertain = query.get('uncertain_events', [])
            if missing or unknown:
                status = 'unresolved'
            elif after:
                status = 'contradicted'
            elif uncertain:
                status = 'supported_with_uncertainty'
            else:
                status = 'supported'
            details[letter] = {
                'status': status,
                'events': events,
                'missing_events': missing,
                'unknown_relations': unknown,
                'contradictions': after,
                'uncertain_events': uncertain,
            }
        verified = [letter for letter, row in details.items()
                    if row['status'] == 'supported']
        candidates = [letter for letter, row in details.items()
                      if row['status'] in ('supported', 'supported_with_uncertainty')]
        return {
            'by_option': details,
            'unique_verified_option': verified[0] if len(verified) == 1 else None,
            'unique_candidate_option': candidates[0] if len(candidates) == 1 else None,
            'instruction': (
                'A unique_verified_option is fully consistent with the grounded graph order. '
                'A unique_candidate_option may still depend on uncertain event identity. '
                'If neither is unique, gather evidence for the reported gaps; do not infer absence.'),
        }

    @staticmethod
    def _graph_evidence_gaps(result, option_match):
        if option_match.get('unique_verified_option'):
            return {'status': 'resolved',
                    'recommended_action': 'answer_consistently_with_verified_option'}
        missing = list(dict.fromkeys(result.get('missing', [])))
        unknown = [row for row in result.get('pairs', [])
                   if row.get('relation') == 'unknown']
        uncertain = list(dict.fromkeys(result.get('uncertain_events', [])))
        targets = list(dict.fromkeys(
            missing + uncertain +
            [row.get(side) for row in unknown for side in ('left', 'right')
             if row.get(side)]))
        return {
            'status': 'needs_evidence',
            'missing_events': missing,
            'uncertain_events': uncertain,
            'unknown_relations': unknown,
            'priority_targets': targets,
            'recommended_action':
                'locate_or_verify_priority_target_with_visual_tools; then requery_graph',
        }

    def _normalize_graph_args(self, args):
        query = args.get("query")
        if query not in ("event_order", "entity_relation"):
            raise ToolArgumentError(
                "query_video_graph: query must be 'event_order' or 'entity_relation'")
        if query == "event_order":
            events = args.get("events")
            if not isinstance(events, list) or not events or \
                    not all(isinstance(e, str) and e.strip() for e in events):
                raise ToolArgumentError(
                    "query_video_graph event_order requires a nonempty list of event name strings")
            return {"query": "event_order", "events": [e.strip() for e in events]}
        entity = args.get("entity")
        predicate = args.get("predicate")
        if not isinstance(entity, str) or not entity.strip():
            raise ToolArgumentError("query_video_graph entity_relation requires a nonempty 'entity' string")
        if not isinstance(predicate, str) or not predicate.strip():
            raise ToolArgumentError("query_video_graph entity_relation requires a nonempty 'predicate' string")
        out = {"query": "entity_relation", "entity": entity.strip(), "predicate": predicate.strip()}
        if "object" in args and args["object"] is not None:
            out["object"] = args["object"]
        return out

    def _source_view(self, source_id, entry):
        tool, obs = entry['tool'], entry['observation']
        view = {'source_id': source_id, 'tool': tool, 'arguments': entry.get('arguments', {})}
        self.graph_sources[source_id] = None
        if tool == 'read_transcript':
            segments = []
            for index, segment in enumerate(obs.get('segments', [])):
                ref = source_id + '/asr_' + str(index)
                segments.append(dict(segment, source_id=ref))
                self.graph_sources[ref] = (segment.get('start'), segment.get('end'))
            view['segments'] = segments
        elif 'perception' in obs:
            frames = []
            for index, frame in enumerate(obs.get('frames', [])):
                ref = source_id + '/' + str(frame.get('id', 'frame_' + str(index)))
                frames.append(dict(frame, source_id=ref))
                self.graph_sources[ref] = (frame.get('timestamp'), frame.get('timestamp'))
            view.update(frames=frames, perception=obs['perception'])
        else:
            detections = []
            for index, row in enumerate(obs.get('raw_detections', obs.get('detections', []))):
                ref = source_id + '/ocr_' + str(index)
                detections.append(dict(row, source_id=ref))
                timestamp = row.get('timestamp', row.get('timestamp_seconds'))
                self.graph_sources[ref] = (timestamp, timestamp)
            view['detections'] = detections
        return view

    def _ground_extraction(self, extraction):
        result = deepcopy(extraction)
        for kind in ('entities', 'events', 'relations'):
            result[kind] = [r for r in result[kind] if isinstance(r, dict)]
            for row in result[kind]:
                evidence = row.get('evidence', [])
                refs = [r for r in evidence if isinstance(r, str) and r in self.graph_sources] if isinstance(evidence, list) else []
                row['evidence'] = refs
                row['grounded'] = bool(refs)
                if not refs:
                    row['confidence'] = 'low'
                if kind == 'entities':
                    attributes = row.get('attributes', [])
                    row['attributes'] = [a for a in attributes if isinstance(a, dict)] if isinstance(attributes, list) else []
                    for attr in row['attributes']:
                        evidence = attr.get('evidence', refs)
                        attr['evidence'] = [r for r in evidence if isinstance(r, str) and r in self.graph_sources] if isinstance(evidence, list) else []
                        attr['grounded'] = bool(attr['evidence'])
                if kind == 'events':
                    spans = [self.graph_sources[r] for r in refs if self.graph_sources[r] is not None]


                    valid = [(float(a), float(b)) for a, b in spans
                             if isinstance(a, (int, float)) and not isinstance(a, bool)
                             and isinstance(b, (int, float)) and not isinstance(b, bool)]
                    row['time_start'] = min((a for a, _ in valid), default=None)
                    row['time_end'] = max((b for _, b in valid), default=None)
                    row['observed_times'] = spans
        return result

    def _ingest_observations(self, observations, query):
        new_obs = [(str(i), o) for i, o in enumerate(observations)
                   if str(i) not in self.graph_observations and isinstance(o, dict)
                   and o.get('tool') in ('read_transcript', 'overview', 'global_visual64', 'scan_interval', 'inspect_interval', 'read_text')
                   and isinstance(o.get('observation'), dict) and not o['observation'].get('error')
                   and not o['observation'].get('reused_observation')]
        if not new_obs:
            return {'status': 'no_new_observations', 'added': 0}
        view = [self._source_view('obs_' + index, o) for index, o in new_obs]
        messages = [
            {'role': 'system', 'content': _GRAPH_EXTRACTION_PROMPT},
            {'role': 'user', 'content': json.dumps({'question': self.item['question'], 'options': self.item['options'],
             'query': query, 'existing_graph': self.graph.summary(), 'new_observations': view}, ensure_ascii=False)},
        ]
        response = self.services.call('deepseek', {'messages': messages})
        try:
            extraction = self._ground_extraction(_extract_graph_json(response.get('text', '')))
            candidate = deepcopy(self.graph)
            added = candidate.ingest(extraction)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            return {'status': 'extraction_incomplete', 'added': 0, 'reason': str(exc)}
        self.graph = candidate
        self.graph_observations.update(index for index, _ in new_obs)
        return {'status': 'ingested', 'added': added, 'source_ids': ['obs_' + i for i, _ in new_obs]}

    def _execute_graph_query(self, args, observations):
        ingestion = self._ingest_observations(observations, args)
        if args["query"] == "event_order":
            result = self.graph.query_event_order(args["events"])
            option_match = self._match_event_order_options()
            evidence_gaps = self._graph_evidence_gaps(result, option_match)
        else:
            result = self.graph.query_entity_relation(
                args["entity"], args["predicate"], args.get("object"))
            option_match = None
            evidence_gaps = {
                'status': 'resolved' if result.get('status') == 'supported' else 'needs_evidence',
                'recommended_action': (
                    'answer_from_supported_relation' if result.get('status') == 'supported'
                    else 'verify_entity_identity_or_relation_then_requery_graph'),
            }
        self.graph_queried = True
        return {"query": args, "result": result, "option_match": option_match,
                "evidence_gaps": evidence_gaps,
                "graph_summary": self.graph.summary(), 'ingestion': ingestion}

    def visual(self, start, end, count, purpose, observation_goal=None):
        if purpose == "local verification":
            sampling = {"start": start, "end": end, "count": min(8, ceil(end - start))}
            sampling_note = (
                "inspect_interval: at most8 uniform frames across a short clip of at most16 seconds "
                "for following local action progression and checking details. These are sampled "
                "moments, not continuous video; brief actions can still fall between samples.")
        else:
            sampling = {"start": start, "end": end, "count": count}
            if purpose == "coarse localization":
                sampling_note = (
                    "scan_interval: 16 uniform frames across the selected interval to narrow the target "
                    "location; this is coarse localization, not continuous action footage.")
            else:
                sampling_note = (
                    f"Whole-video observation: {count} uniform frames, sparsely spaced to find candidate "
                    "scenes; they are not continuous action footage.")
        frames = self.services.call("sample_frames", sampling)
        context = {"question": self.item["question"], "options": self.item["options"], "purpose": purpose}
        if purpose == 'global_sequence':
            context['observation_goal'] = (
                'Report each target event actually visible in chronological image-index order. '
                'Preserve distinct repeated events and mark missing or ambiguous events; '
                'do not fill in an option sequence from its wording.')
        elif purpose == 'global_unknown_location':
            context['observation_goal'] = (
                'Search all supplied frames for the requested target and describe the detail '
                'that distinguishes options. Cite the target frames, preserve identity '
                'uncertainty, and say if the target/detail is not captured.')
        if observation_goal:
            if 'observation_goal' in context:
                context['route_observation_goal'] = context['observation_goal']
            context['observation_goal'] = observation_goal
        references = question_time_references(self.item['question'], self.item['duration'])
        if references:
            context['question_time_references'] = references
        prompt = (
            "You are DeepSeek's visual observation assistant. Examine the supplied images and "
            "provide concrete visual information that helps resolve the current question.\n\n"
            + sampling_note + "\nChronological frame order alone does not establish what happened immediately next.\n\n"
            +
            "Observation focus: if observation_goal is provided, prioritize that specific question. "
            "Otherwise, use the original question and options to find visual details that distinguish "
            "the candidate answers.\n\n"
            "Report the relevant findings directly: what is visible, which images show it, and "
            "which details support or contradict the current hypothesis. When identifying a person, "
            "look for visible name text and appearance. When checking a setting, establish whether "
            "the person and the described background actually appear together in the same image. "
            "Avoid listing unrelated content, but preserve important detail rather than shortening "
            "it away; there is no fixed fact-count limit.\n\n"
            "When evidence is clear, report it clearly. When the target is not found or a detail "
            "is unreadable, say specifically what is missing or uncertain. The question, options "
            "and observation_goal guide the search; they are not evidence that the described content "
            "is present. Separate observations from inference; absence from these samples does not "
            "establish absence from the video.\n\n"
            "Provide the visual findings; DeepSeek will combine the evidence and select the final "
            "option. Cite image_indices in the order supplied, starting from 1 within this call. "
            "The program supplies video seconds from those references; do not generate timestamps.\n"
            + (_COUNT_INSTRUCTION + "\n" if is_count_question(self.item["question"]) else "")
            + "Return one JSON object using this format: "
            "{\"observations\":[{\"image_indices\":[integer,...],\"visible_evidence\":string,"
            "\"identity\":string,\"confidence\":\"high|medium|low\",\"uncertainty\":string}],"
            "\"unresolved\":[string,...]}. Every observation must cite at least one supplied image.\n"
            + json.dumps(dict(context, image_indices=list(range(1, len(frames) + 1))),
                         ensure_ascii=False)
        )
        result = self.services.call("qwen", {"frames": [f["id"] for f in frames], "prompt": prompt})
        observation = {"frames": frames, "perception": _bound_visual_response(result, frames),
                       "sampling_note": sampling_note}
        if observation_goal:
            observation['observation_goal'] = observation_goal
        return observation

    def execute(self, name, args, observations=None):
        args = self.normalize_arguments(name, args)
        duration = self.item["duration"]
        if name == "query_video_graph":
            return self._execute_graph_query(args, observations or [])
        if name == 'survey_occurrences':
            return self._survey_occurrences()
        if name == 'global_visual64':
            goal = args.get('observation_goal', '')
            if self.global64_result is not None:
                result = dict(self.global64_result, reused_observation=True)
                if goal and goal != result.get('observation_goal', ''):
                    result['goal_not_executed'] = goal
                    result['reuse_note'] = 'Existing global evidence reused; no new goal-specific Qwen observation was performed.'
                return result
            self.global64_attempted = True
            result = self.visual(0, duration, 64, self.global_visual_scope, goal)
            if result.get('perception', {}).get('usable'):
                self.global64_result = result
            return result
        if name == "read_transcript":
            if self.transcript_read:
                return {"already_read": True, "message": "Full transcript remains in memory."}
            result = self.services.call("asr", {})
            self.transcript_read = True
            return transcript_view(result)
        if name == "overview":
            return self.visual(0, duration, 32, "global overview", args.get('observation_goal'))
        start, end = args['start'], args['end']
        if name == "scan_interval":
            return self.visual(start, end, 16, "coarse localization", args.get('observation_goal'))
        if name == "inspect_interval":
            return self.visual(start, end, None, "local verification", args.get('observation_goal'))
        if name == "read_text":
            timestamps = [start + i for i in range(16) if start + i < end]
            frames = self.services.call("sample_frames", {"timestamps": timestamps})
            raw = self.services.call("ocr", {"frames": [f["id"] for f in frames]})
            seen, rows = set(), []
            for row in raw:
                key = row["text"].strip()
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
            return {"detections": rows, "raw_detections": raw}
