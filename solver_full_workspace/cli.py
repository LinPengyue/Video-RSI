import argparse
import json
from pathlib import Path
from .engine.common import read_json, validate_config
from .engine.evolve import Evolution, initialize
from .engine.runner import INITIAL_HARNESS, run_item
from .engine.services import Services, OfflineProvider
import tempfile


def main():
    parser = argparse.ArgumentParser(description="Full editable Solver: train → same-session analysis/edit → paired Gate → accept/keep parent")
    sub = parser.add_subparsers(dest="command", required=True)
    show = sub.add_parser("config", help="display final effective values; no provider calls")
    show.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    preflight = sub.add_parser("preflight", help="import candidate and check dependencies without model calls")
    preflight.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    preflight.add_argument("--candidate", default=str(INITIAL_HARNESS), help="candidate directory; defaults to the Initial harness")
    init = sub.add_parser("init", help="freeze a new route; does not run models")
    init.add_argument("--root", required=True)
    init.add_argument("--seed", default=str(INITIAL_HARNESS), help="starting candidate directory; defaults to the Initial harness")
    init.add_argument("--config", default=str(Path(__file__).with_name("config.json")))
    init.add_argument("--datasets", required=True)
    run = sub.add_parser("run", help="paid calls: resume / advance rounds")
    run.add_argument("--root", required=True)
    run.add_argument("--rounds", type=int, default=1)
    run.add_argument('--continue-plan', action='store_true', help='continue an optional WAIT_PLAN pause')
    run.add_argument("--allow-provider-calls", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--root", required=True)
    args = parser.parse_args()
    if args.command == "config":
        value = validate_config(read_json(args.config))
    elif args.command == "preflight":
        cfg = validate_config(read_json(args.config))
        item = {"sample_id": "offline_preflight", "question": "Offline startup only", "options": {"A": "one", "F": "six"}, "duration": 60}
        with tempfile.TemporaryDirectory(prefix="full-preflight-") as scratch:
            service = Services(item, {}, cfg, scratch, OfflineProvider())
            value = run_item(args.candidate, item, service, cfg, check_only=True)
        value["effective_config"] = cfg
        if value["status"] != "startup_ok":
            print(json.dumps(value, ensure_ascii=False, indent=2))
            raise SystemExit(1)
    elif args.command == "init":
        root = initialize(args.root, args.seed, read_json(args.config), read_json(args.datasets))
        value = {"status": "INITIALIZED_NOT_RUN", "root": str(root), "effective_config": read_json(root / "effective_config.json")}
    elif args.command == "status":
        root = Path(args.root)
        value = {"state": read_json(root / "state.json"), "current": read_json(root / "current.json"), "effective_config": read_json(root / "effective_config.json")}
    else:
        if not args.allow_provider_calls or args.rounds < 1:
            parser.error("run requires --allow-provider-calls and rounds >=1")
        evolution = Evolution(args.root)
        print(json.dumps({"effective_config": evolution.config}, ensure_ascii=False, indent=2), flush=True)
        value = evolution.advance(args.rounds, args.continue_plan)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
