import math
import re
from copy import deepcopy


def _norm(value):
    return re.sub(r'^(?:a|an|the)\s+', '', re.sub(r'\s+', ' ', value.lower().strip())) if isinstance(value, str) else ''


def _num(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _items(value):
    return value if isinstance(value, list) else []


def _uncertainty_items(value):
    if isinstance(value, list):
        return [v for v in value if v]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _uncertain(entry):
    if entry.get('uncertainty') or entry.get('grounded') is False:
        return True
    if str(entry.get('confidence', 'medium')).lower() in ('low', 'uncertain', 'maybe', 'possible'):
        return True
    value = entry.get('value', entry.get('object'))
    return isinstance(value, str) and bool(re.search(r'\b(maybe|possibly|perhaps|or|uncertain|unknown)\b', value, re.I))


def _value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    result = _norm(str(value)) if value is not None else None
    return {'yes': 'true', 'no': 'false'}.get(result, result)


class VideoGraph:
    def __init__(self):
        self.entities = {}
        self.events = {}
        self.relations = []
        self._next_id = 0
        self._external_ids = {}

    def _new_id(self, prefix):
        self._next_id += 1
        return '%s_%d' % (prefix, self._next_id)

    def _matches(self, table, name):
        if not isinstance(name, str):
            return []
        if name in table:
            return [name]
        mapped = self._external_ids.get(name)
        if mapped in table:
            return [mapped]
        key = _norm(name)
        return [i for i, n in table.items() if key and key in {_norm(n['name']), *[_norm(a) for a in n.get('aliases', [])]}]

    def _resolve(self, table, name):
        found = self._matches(table, name)
        return found[0] if len(found) == 1 else None

    def _node(self, row, event=False):
        table = self.events if event else self.entities
        reference = row.get('same_id') or row.get('id')
        target = self._resolve(table, reference) if isinstance(reference, str) else None
        matches = self._matches(table, row['name'])
        if not target and not reference and len(matches) == 1:
            old = table[matches[0]]
            common = any(e in old['evidence'] for e in _items(row.get('evidence')))
            if event:
                old_range = (old.get('time_start'), old.get('time_end'))
                new_range = (_num(row.get('time_start')), _num(row.get('time_end')))
                if old_range == (None, None) and not old['time_claims'] or old_range == new_range and any(t is not None for t in new_range):
                    target = matches[0]
            elif common and _norm(old['type']) == _norm(row.get('type', 'unknown')):
                target = matches[0]
        if not target:
            target = self._new_id('evt' if event else 'ent')
            table[target] = {'id': target, 'name': row['name'], 'aliases': [], 'uncertainty': [], 'evidence': []}
            if event:
                table[target].update(time_start=None, time_end=None, time_claims=[], participants=[], locations=[], location=None)
            else:
                table[target].update(type=row.get('type') or 'unknown', attributes=[])
        if isinstance(row.get('id'), str):
            self._external_ids[row['id']] = target
        node = table[target]
        for field in ('aliases', 'uncertainty', 'evidence'):
            values = _uncertainty_items(row.get(field)) if field == 'uncertainty' else _items(row.get(field))
            for value in values:
                if value not in node[field]:
                    node[field].append(deepcopy(value))
        return target

    def _add(self, rows, row):
        if row not in rows:
            rows.append(deepcopy(row))

    def ingest(self, extraction):
        if not isinstance(extraction, dict):
            return 0
        added = 0
        identity_context = {}
        for row in _items(extraction.get('entities')):
            if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name'].strip():
                continue
            eid = self._node(row)
            node = self.entities[eid]
            identity_context[eid] = _items(row.get('uncertainty'))
            for attr in _items(row.get('attributes')):
                if not isinstance(attr, dict) or not isinstance(attr.get('attribute'), str):
                    continue
                claim = dict(attr)
                claim.setdefault('evidence', row.get('evidence', []))
                claim['uncertainty'] = list(_items(claim.get('uncertainty'))) + list(_items(row.get('uncertainty')))
                self._add(node['attributes'], claim)
            added += 1
        for row in _items(extraction.get('events')):
            if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not row['name'].strip():
                continue
            eid = self._node(row, event=True)
            node = self.events[eid]
            start, end = _num(row.get('time_start')), _num(row.get('time_end'))
            if start is not None or end is not None:
                claim = {'start': start, 'end': end, 'evidence': row.get('evidence', []), 'uncertainty': _uncertainty_items(row.get('uncertainty')), 'grounded': row.get('grounded', True), 'confidence': row.get('confidence', 'medium')}
                if start is not None and end is not None and end < start:
                    claim['uncertainty'] = ['invalid time interval']
                self._add(node['time_claims'], claim)




                ranges = {(c['start'], c['end']) for c in node['time_claims']
                          if c.get('grounded', True)
                          and (c.get('start') is not None or c.get('end') is not None)}
                if len(ranges) == 1:
                    node['time_start'], node['time_end'] = next(iter(ranges))
                elif len(ranges) > 1:
                    node['time_start'] = node['time_end'] = None
            for person in _items(row.get('participants')):
                ref = (person.get('entity_id') or person.get('name')) if isinstance(person, dict) else person
                if not isinstance(ref, str):
                    continue
                pid = self._resolve(self.entities, ref)
                self._add(node['participants'], {'entity_id': pid, 'name': ref, 'role': person.get('role', 'participant') if isinstance(person, dict) else 'participant'})
            if isinstance(row.get('location'), str):
                self._add(node['locations'], row['location'])
                node['location'] = node['locations'][0] if len(node['locations']) == 1 else None
            added += 1
        for row in _items(extraction.get('relations')):
            if not isinstance(row, dict) or not isinstance(row.get('subject'), str) or not isinstance(row.get('predicate'), str):
                continue
            relation = deepcopy(row)
            relation['subject_id'] = self._resolve(self.entities, row['subject']) or self._resolve(self.events, row['subject'])
            subject_id = relation['subject_id']
            if subject_id in self.entities:
                relation['uncertainty'] = list(_items(relation.get('uncertainty'))) + list(identity_context.get(subject_id, self.entities[subject_id]['uncertainty']))
            obj = row.get('object')
            relation['object_id'] = (self._resolve(self.entities, obj) or self._resolve(self.events, obj)) if isinstance(obj, str) else None
            self._add(self.relations, relation)
            added += 1
        return added

    def _before_edges(self):
        edges = set()
        for row in self.relations:
            if _uncertain(row) or row.get('polarity', 'positive') != 'positive':
                continue
            left, right = row.get('subject_id'), row.get('object_id')
            pred = _norm(row['predicate'])
            if left in self.events and right in self.events:
                if pred == 'before':
                    edges.add((left, right))
                elif pred == 'after':
                    edges.add((right, left))
        return edges

    def _reachable(self, edges, left, right):
        seen, pending = set(), [left]
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            for src, dst in edges:
                if src == node:
                    if dst == right:
                        return True
                    pending.append(dst)
        return False

    def _compare(self, left, right, edges):
        if left == right:
            return 'unknown'
        a, b = self.events[left], self.events[right]
        forward = self._reachable(edges, left, right)
        reverse = self._reachable(edges, right, left)
        a0, a1 = a['time_start'], a['time_end']
        b0, b1 = b['time_start'], b['time_end']
        if all(x is not None for x in (a0, a1, b0, b1)):
            forward = forward or a1 < b0
            reverse = reverse or b1 < a0
        elif a1 is None and b1 is None and a0 is not None and b0 is not None:
            forward = forward or a0 < b0
            reverse = reverse or b0 < a0
        if forward and reverse:
            return 'conflict'
        return 'before' if forward else 'after' if reverse else 'unknown'

    def query_event_order(self, event_names):
        matched = [(name, self._resolve(self.events, name)) for name in event_names]
        missing = [name for name, eid in matched if eid is None]
        edges = self._before_edges()
        pairs = []
        for i, (a, aid) in enumerate(matched):
            for b, bid in matched[i + 1:]:
                pairs.append({'left': a, 'right': b, 'relation': self._compare(aid, bid, edges) if aid and bid else 'unknown'})
        conflict = [p for p in pairs if p['relation'] in ('after', 'conflict')]
        unknown = [p for p in pairs if p['relation'] == 'unknown']
        known = [p for p in pairs if p['relation'] != 'unknown']
        uncertain_events = [name for name, eid in matched
                            if eid is not None and self.events[eid].get('uncertainty')]
        status = ('conflict' if conflict else 'partial' if unknown and known
                  else 'undetermined' if unknown or missing or not pairs
                  else 'supported_with_uncertainty' if uncertain_events
                  else 'supported')
        ordered = []
        if not missing and pairs and not unknown and not any(p['relation'] == 'conflict' for p in pairs):
            ordered = sorted(event_names, key=lambda name: sum((p['right'] == name and p['relation'] == 'before') or (p['left'] == name and p['relation'] == 'after') for p in pairs))
        return {'status': status, 'caller_order': event_names, 'supported_order': ordered, 'consistent': False if conflict else True if status.startswith('supported') else None,
                'missing': missing, 'pairs': pairs, 'conflicts': conflict,
                'uncertain_events': uncertain_events,
                'events': [deepcopy(self.events[eid]) if eid else {'name': name, 'candidates': self._matches(self.events, name)} for name, eid in matched]}

    def query_entity_relation(self, entity_name, predicate, object_value=None):
        eid = self._resolve(self.entities, entity_name)
        if eid is None:
            return {'status': 'unknown', 'reason': 'entity missing or ambiguous', 'entity': entity_name, 'candidates': self._matches(self.entities, entity_name), 'support': [], 'conflict': [], 'uncertain': []}
        entity = self.entities[eid]
        claims = [a for a in entity['attributes'] if _norm(a['attribute']) == _norm(predicate)]
        claims += [r for r in self.relations if r.get('subject_id') == eid and _norm(r['predicate']) == _norm(predicate)]
        support, conflict, uncertain = [], [], []
        expected = _value(object_value)
        for claim in claims:
            if _uncertain(claim):
                uncertain.append(claim)
                continue
            actual = _value(claim.get('value', claim.get('object')))
            negative = claim.get('polarity', 'positive') == 'negative'
            if actual in ('true', 'false'):
                truth = actual == 'true' and not negative
                if expected is None or expected in ('true', 'false'):
                    wanted = expected != 'false'
                    (support if truth == wanted else conflict).append(claim)
                else:
                    uncertain.append(claim)
            elif expected is None:
                (uncertain if negative or actual is None else support).append(claim)
            elif actual == expected:
                (conflict if negative else support).append(claim)
            else:
                uncertain.append(claim)
        status = 'conflict' if conflict else 'supported' if support else 'unknown'
        return deepcopy({'status': status, 'entity': entity_name, 'entity_id': eid, 'predicate': predicate, 'object_value': object_value,
                         'support': support, 'conflict': conflict, 'uncertain': uncertain,
                         'entity_uncertainty': entity['uncertainty'], 'entity_evidence': entity['evidence']})

    def summary(self):
        return deepcopy({'entities': list(self.entities.values()), 'events': list(self.events.values()), 'relations': self.relations})
