"""Create a machine-local configuration; no provider calls or model downloads."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--ocr-model-root')
    parser.add_argument('--harness-root')
    parser.add_argument('--node-binary')
    parser.add_argument('--offline-review', action='store_true',
                        help='disable Linux isolation for local startup inspection only')
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name('config.example.json').read_text())
    config['execution']['python'] = sys.executable
    if args.offline_review:
        config['execution']['linux_isolation'] = False
    for field in ('harness_root', 'node_binary'):
        value = getattr(args, field)
        if value:
            config['editor'][field] = str(Path(value).resolve())
    if args.ocr_model_root:
        config['services']['ocr_model_root'] = str(Path(args.ocr_model_root).resolve())
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(config, stream, ensure_ascii=False, indent=2)
    print('Configuration created; no provider calls:', path.resolve())


if __name__ == '__main__':
    main()
