"""Question-conditioned discovery and verification; all times bound by code."""
import json
import math


def json_object(text):
    decoder = json.JSONDecoder()
    for i, char in enumerate(text or ''):
        if char == '{':
            try:
                obj, _ = decoder.raw_decode(text, i)
                if isinstance(obj, dict):
                    return obj
            except ValueError:
                pass
    return None


def bound_frames(indices, frames):
    """Provider-local one-based positions, never model-generated seconds."""
    if not isinstance(indices, list):
        return []
    selected = []
    for index in indices:
        if isinstance(index, int) and not isinstance(index, bool) and 1 <= index <= len(frames):
            frame = frames[index - 1]
            if frame not in selected:
                selected.append(frame)
    return sorted(selected, key=lambda f: f['timestamp'])


def cluster_hits(records):
    """Group adjacent positive samples; every explicit negative splits a group."""
    groups, current = [], []
    for record in sorted(records, key=lambda r: r['frame']['timestamp']):
        if record['match'] in ('yes', 'possible'):
            current.append(record)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


class OccurrenceCounter:
    def __init__(self, item, services, frame_allowance):
        self.item, self.services = item, services

        self.limit = min(192, max(0, int(frame_allowance) - 64))
        self.used = 0
        self.queries = []
        self.errors = []
        self.cache = {}

    def observe(self, timestamps, instruction):
        if self.used + len(timestamps) > self.limit:
            return None, []
        missing = [t for t in timestamps if round(t, 6) not in self.cache]
        if missing:
            frames = self.services.call('sample_frames', {'timestamps': missing})
            self.cache.update({round(f['timestamp'], 6): f for f in frames})
        frames = [self.cache[round(t, 6)] for t in timestamps]
        prompt = (
            'Images are in the EXACT order below. image_index is ONE-BASED within this call. '
            'Return image indices, never seconds or clip-relative timestamps. '
            'Question and options indicate what to look for, not evidence that it exists. '
            'Describe visible evidence independently; do not choose an answer option.\n'
            + instruction + '\n' + json.dumps({
                'question': self.item['question'], 'options': self.item['options'],
                'target_definition': self.definition,
                'image_map': [{'image_index': i + 1, 'frame_id': f['id'],
                               'video_seconds': f['timestamp']} for i, f in enumerate(frames)],
            }, ensure_ascii=False)
        )
        result = self.services.call('qwen', {'frames': [f['id'] for f in frames], 'prompt': prompt})
        self.used += len(frames)
        obj = json_object(result.get('text', ''))
        self.queries.append({'frames': frames, 'purpose': instruction,
                             'response': result, 'parsed': obj})
        if obj is None:
            self.errors.append('Qwen response lacked a JSON object; retained raw evidence.')
        return obj, frames

    def run(self):
        response = self.services.call('deepseek', {'messages': [
            {'role': 'system', 'content': (
                'Define the counting task from its public question/options. No video evidence yet. '
                'Return JSON {target:string, count_unit:"scene_occurrence"|"action_cycle"|'
                '"distinct_entity"|"local_quantity"|"reported_quantity", scope:string, '
                'positive_criteria:string, exclusion_criteria:string}. '
                'A scene featuring an action counts separate appearances of that scene, including '
                'repeated footage separated by other content; do not require a complete athletic '
                'cycle to identify a scene. A question asking how many times an action is performed '
                'counts distinct cycles. People holding equipment are not necessarily performing '
                'the action. Multiple adjacent frames of one scene are not multiple occurrences.'
            )},
            {'role': 'user', 'content': json.dumps({
                'question': self.item['question'], 'options': self.item['options']}, ensure_ascii=False)},
        ]})
        self.definition = json_object(response.get('text', ''))
        if self.definition is None:
            return {'status': 'definition_unavailable', 'raw': response.get('text', ''),
                    'next_step': 'Use ordinary tools to establish the counting unit.'}
        if self.definition.get('count_unit') not in ('scene_occurrence', 'action_cycle'):
            return {'status': 'not_applicable', 'target_definition': self.definition,
                    'next_step': 'Use local inspection, ASR or entity-specific counting as appropriate.'}
        if self.limit < 64:
            return {'status': 'insufficient_tool_budget', 'target_definition': self.definition}
        duration = float(self.item['duration'])
        coarse_step = duration / 64
        timestamps = [(i + .5) * coarse_step for i in range(64)]
        scan_instruction = (
            'Find EVERY sampled image depicting the target or a plausible candidate. '
            'Report all images, including negatives. Return JSON '
            '{frames:[{image_index:integer,match:"yes"|"possible"|"no",visible_evidence:string}]}. '
            'A preparation or landing view may identify a target scene; mark uncertain identity '
            'possible. Do not extrapolate a total count from these sparse images.'
        )
        records = []

        def scan(times):
            for offset in range(0, len(times), 16):
                obj, frames = self.observe(times[offset:offset + 16], scan_instruction)
                labels = {}
                for row in (obj or {}).get('frames', []):
                    if not isinstance(row, dict):
                        continue
                    bound = bound_frames([row.get('image_index')], frames)
                    if bound:
                        labels[bound[0]['id']] = row
                for frame in frames:
                    row = labels.get(frame['id'], {})
                    status = row.get('match', 'unknown')
                    records.append({'frame': frame, 'match': status if status in
                                    ('yes', 'possible', 'no') else 'unknown',
                                    'evidence': row.get('visible_evidence', '')})

        scan(timestamps)

        if coarse_step > 2 and self.limit >= 192:
            scan([min(duration - 1e-6, (i + .05) * coarse_step) for i in range(64)])
        groups = cluster_hits(records)
        episodes, unresolved = [], []
        verify_instruction = (
            'Verify the target in this candidate window. Respect count_unit exactly. '
            'List separate target scenes or completed action cycles, NOT individual positive frames. '
            'Group consecutive views of one occurrence together. If unrelated content separates two '
            'appearances, keep both. Return JSON {episodes:[{image_indices:[integer], '
            'status:"confirmed"|"uncertain",visible_evidence:string}], '
            'boundary_uncertain:bool, uncertainty:string}. '
            'For action_cycle, repeated motions need distinct cycle evidence. For scene_occurrence, '
            'this candidate window represents one continuous inserted target clip: return at most one '
            'episode for it, even when it contains multiple athletes, attempts, shots, replays, or '
            'phases of the action. Recognizable target footage may count even if the complete motion '
            'is not sampled. '
            'If the candidate was a false positive, return episodes:[].'
        )
        for number, group in enumerate(groups, 1):
            anchors = [r['frame']['timestamp'] for r in group]
            start = max(0., min(anchors) - coarse_step * .6)
            end = min(duration, max(anchors) + coarse_step * .6)
            if end - start > 32:

                unresolved.append({'candidate': number, 'reason': 'candidate spans over 32s; '
                                   'verify continuation or repeated cycles in remaining interval',
                                   'start': start, 'end': end})
                end = start + 32
            if self.used + 8 > self.limit:
                unresolved.append({'candidate': number, 'reason': 'verification budget reserved for Solver',
                                   'start': start, 'end': end})
                continue

            points = sorted(set(t for t in anchors if start <= t < end))
            if len(points) > 8:
                points = [points[round(i * (len(points) - 1) / 7)] for i in range(8)]
            grid = [start + (end - start) * (i + .5) / 16 for i in range(16)]
            while len(points) < 8:
                choices = [t for t in grid if t not in points]
                t = max(choices, key=lambda v: min((abs(v-p) for p in points), default=math.inf))
                points.append(t)
            obj, frames = self.observe(sorted(points), verify_instruction)
            if obj is None:
                unresolved.append({'candidate': number, 'start': start, 'end': end,
                                   'reason': 'unparsed local verification'})
                continue
            accepted = []
            for episode in obj.get('episodes', []):
                if not isinstance(episode, dict):
                    continue
                bound = bound_frames(episode.get('image_indices'), frames)
                if not bound:
                    unresolved.append({'candidate': number, 'reason': 'episode has no valid frame binding'})
                    continue
                ids = {f['id'] for f in bound}

                duplicate = next((e for e in accepted if ids.intersection(e['frame_ids'])), None)
                if duplicate:
                    duplicate['status'] = 'uncertain'
                    duplicate['uncertainty'] = 'overlapping episode references require boundary verification'
                    continue
                accepted.append({'event_id': 'candidate_%d_episode_%d' % (number, len(accepted) + 1),
                                 'candidate': number, 'frame_ids': sorted(ids),
                                 'observed_start_seconds': bound[0]['timestamp'],
                                 'observed_end_seconds': bound[-1]['timestamp'],
                                 'status': 'confirmed' if episode.get('status') == 'confirmed' else 'uncertain',
                                 'visible_evidence': episode.get('visible_evidence', '')})





            if self.definition.get('count_unit') == 'scene_occurrence' and accepted:
                all_ids = sorted({fid for episode in accepted for fid in episode['frame_ids']})
                accepted = [{
                    'event_id': 'candidate_%d_scene' % number,
                    'candidate': number,
                    'frame_ids': all_ids,
                    'observed_start_seconds': min(e['observed_start_seconds'] for e in accepted),
                    'observed_end_seconds': max(e['observed_end_seconds'] for e in accepted),
                    'status': ('confirmed' if any(e['status'] == 'confirmed' for e in accepted)
                               else 'uncertain'),
                    'visible_evidence': 'One continuous target-scene candidate; internal athletes, '
                                        'attempts, shots and motion phases are not separate scene occurrences. '
                                        + ' | '.join(e['visible_evidence'] for e in accepted
                                                     if e['visible_evidence']),
                }]
            episodes.extend(accepted)
            if obj.get('boundary_uncertain'):
                unresolved.append({'candidate': number, 'start': start, 'end': end,
                                   'reason': obj.get('uncertainty', 'event boundary uncertain')})
        count = sum(e['status'] == 'confirmed' for e in episodes)
        return {
            'status': 'survey_and_verification_complete', 'target_definition': self.definition,
            'coverage': {'sampled_points': len(records), 'coverage_complete': False,
                         'short_events_may_be_missed': True,
                         'largest_sample_gap_seconds': max(b['frame']['timestamp'] - a['frame']['timestamp']
                             for a, b in zip(sorted(records, key=lambda r:r['frame']['timestamp']),
                                             sorted(records, key=lambda r:r['frame']['timestamp'])[1:]))},
            'candidate_count': len(groups), 'observed_episode_count': count,
            'episodes': episodes, 'unresolved_candidates': unresolved,
            'scan_records': records, 'investigation_queries': self.queries,
            'parse_issues': self.errors, 'qwen_frames_inside_tool': self.used,
            'next_step': 'Use verified episode count as observed evidence, not a guaranteed complete total. '
                         'Distinct far-apart appearances were NOT merged by matching descriptions. '
                         'Resolve remaining candidate/boundary gaps with local tools if needed. '
                         'If none remain, select the best-supported option; do not resurvey identical frames.',
        }
