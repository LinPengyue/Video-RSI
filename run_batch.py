"""Batch inference with a frozen candidate and answer-free inputs."""
import argparse
import concurrent.futures
import tempfile
from pathlib import Path

from solver_full_workspace.engine.common import public_item, read_json, read_jsonl, validate_config, write_json
from solver_full_workspace.engine.runner import INITIAL_HARNESS, copy_candidate, run_item
from solver_full_workspace.engine.services import Services


def load_items(path, check_media=False):
    rows = read_jsonl(path)
    seen = set()
    for row in rows:
        if 'question_type' in row:
            if 'task_type' in row and row['task_type'] != row['question_type']:
                raise ValueError('question_type and task_type must agree')
            row['task_type'] = row.pop('question_type')
        if 'task_type' in row and (not isinstance(row['task_type'], str) or not row['task_type']):
            raise ValueError('task_type must be a nonempty string')
        item = public_item(row)
        sid = item['sample_id']
        if not isinstance(sid, str) or not sid or sid in seen:
            raise ValueError('sample_id must be a unique nonempty string')
        seen.add(sid)
        allowed = {'sample_id', 'question', 'options', 'duration', 'video_path', 'asr_path', 'task_type'}
        if set(row) - allowed:
            raise ValueError('input items must contain only public fields; provide labels to score.py separately')
        if check_media:
            if not row.get('video_path'):
                raise ValueError('video_path is required')
            for key in ('video_path', 'asr_path'):
                if row.get(key) and not Path(row[key]).is_file():
                    raise ValueError('missing media file: ' + key)
    if not rows:
        raise ValueError('empty item manifest')
    return rows


def run_batch(config, candidate, rows, output, services_factory=Services, runner=run_item):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / 'candidate'
    copy_candidate(candidate, frozen)
    write_json(output / 'config.json', config)
    write_json(output / 'items.json', rows)

    def one(pair):
        index, row = pair
        item = public_item(row)
        media = {key: row[key] for key in ('video_path', 'asr_path') if row.get(key)}
        with tempfile.TemporaryDirectory(prefix='video-rsi-batch-') as scratch:
            try:
                services = services_factory(item, media, config, scratch)
                result = runner(frozen, item, services, config)
            except Exception as exc:
                result = {'sample_id': row['sample_id'], 'status': 'engineering_error',
                          'answer': None, 'error_type': type(exc).__name__}
        write_json(output / 'items' / ('%06d.json' % index), result)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=config['execution']['concurrency']) as pool:
        results = list(pool.map(one, enumerate(rows)))
    write_json(output / 'results.json', results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--candidate', default=str(INITIAL_HARNESS),
                        help='candidate directory; defaults to the Initial harness')
    parser.add_argument('--items', required=True, help='public questions in JSONL format')
    parser.add_argument('--output-dir', required=True, help='new output directory')
    parser.add_argument('--allow-provider-calls', action='store_true')
    args = parser.parse_args()
    if not args.allow_provider_calls:
        parser.error('inference requires --allow-provider-calls')
    config = validate_config(read_json(args.config))
    rows = load_items(args.items, check_media=True)
    results = run_batch(config, args.candidate, rows, args.output_dir)
    print('Saved %d results to %s/results.json' % (len(results), args.output_dir))


if __name__ == '__main__':
    main()
