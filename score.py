"""Score predictions against separately supplied multiple-choice labels."""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

from run_batch import load_items
from solver_full_workspace.engine.common import public_item, read_json, read_jsonl
from solver_full_workspace.engine.frame_cost import FRAME_METRIC, cost_usage


def indexed(rows):
    values = {}
    for row in rows:
        sid = row['sample_id']
        if not isinstance(sid, str) or not sid or sid in values:
            raise ValueError('sample_id must be a unique nonempty string')
        values[sid] = row
    return values


def score(items, predictions, labels):
    expected, predicted, gold = indexed(items), indexed(predictions), indexed(labels)
    if not expected or set(gold) != set(expected) or set(predicted) - set(expected):
        raise ValueError('labels must cover the full item manifest; predictions cannot contain extra IDs')
    statuses = Counter()
    correct, frames, cost_missing = 0, 0, 0
    groups = {}
    for sid, item in expected.items():
        options = public_item(item)['options']
        if gold[sid].get('answer') not in options:
            raise ValueError('label is not an actual option')
        result = predicted.get(sid)
        status = result.get('status') if result is not None else 'missing'
        statuses[status] += 1
        if status == 'answered' and result.get('answer') not in options:
            raise ValueError('answered prediction is not an actual option')
        hit = status == 'answered' and result.get('answer') == gold[sid]['answer']
        correct += int(hit)
        if result is not None:
            try:
                used = cost_usage(result)['qwen_frames']
                if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) or used < 0:
                    raise ValueError('invalid frame count')
                frames += used
            except (ValueError, TypeError, KeyError):
                cost_missing += 1
        if item.get('task_type') is not None:
            name = item['task_type']
            if not isinstance(name, str) or not name:
                raise ValueError('task_type must be a nonempty string')
            group = groups.setdefault(name, {'n': 0, 'correct': 0})
            group['n'] += 1
            group['correct'] += int(hit)
    complete = all(s in ('answered', 'invalid_decision') for s in statuses)
    n = len(expected)
    for group in groups.values():
        group['accuracy_percent'] = 100 * group['correct'] / group['n'] if complete else None
    macro = None
    if complete and groups and sum(g['n'] for g in groups.values()) == n:
        macro = sum(g['accuracy_percent'] for g in groups.values()) / len(groups)
    return {'status': 'complete' if complete else 'incomplete', 'n': n,
            'prediction_count': len(predicted), 'status_counts': dict(statuses),
            'observed_correct': correct,
            'micro_accuracy_percent': 100 * correct / n if complete else None,
            'mean_visual_frames': frames / n if complete and cost_missing == 0 else None,
            'frame_metric': FRAME_METRIC, 'frame_records_unavailable': cost_missing,
            'task_macro_accuracy_percent': macro, 'by_task': groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--items', required=True, help='same public JSONL manifest used for inference')
    parser.add_argument('--predictions', required=True, help='run_batch.py results.json')
    parser.add_argument('--labels', required=True, help='JSONL rows with sample_id and answer')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error('output exists; choose a new path')
    value = score(load_items(args.items), read_json(args.predictions), read_jsonl(args.labels))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
