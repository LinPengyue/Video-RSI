"""CLI: python -m tools.lvbench_comp.batch_factory run|audit ..."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .human_packets import build_packet
from .pipeline import run_factory


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tools.lvbench_comp.batch_factory")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="End-to-end batch factory")
    run_p.add_argument(
        "--manifest",
        type=Path,
        default=Path("research_audit/lvbench_compositional/track_b/construction_video_pool.jsonl"),
    )
    run_p.add_argument("--pool", default="DEV_CONSTRUCTION")
    run_p.add_argument("--max-videos", type=int, default=12)
    run_p.add_argument(
        "--output",
        type=Path,
        default=Path("research_audit/lvbench_compositional/track_b/batch_factory/run_001"),
    )
    run_p.add_argument("--resume", action="store_true")
    run_p.add_argument("--human-k", type=int, default=12)

    audit_p = sub.add_parser("audit", help="Rebuild human packets from an existing run")
    audit_p.add_argument("--run", type=Path, required=True)
    audit_p.add_argument("--build-human-packets", action="store_true")
    audit_p.add_argument("--human-k", type=int, default=12)

    args = p.parse_args(argv)
    if args.cmd == "run":
        out = run_factory(
            manifest=args.manifest,
            output=args.output,
            pool=args.pool,
            max_videos=args.max_videos,
            resume=args.resume,
            human_k=args.human_k,
        )
        print(json.dumps(out["metrics"], ensure_ascii=False, indent=2))
        print(f"\npacket={out['packet_id']} n_human={out['n_human_items']} → {out['output']}")
        return 0

    if args.cmd == "audit":
        run_dir: Path = args.run
        drafts = [json.loads(l) for l in (run_dir / "qa_drafts.jsonl").read_text().splitlines() if l.strip()]
        screened = [json.loads(l) for l in (run_dir / "qa_auto_screen.jsonl").read_text().splitlines() if l.strip()]
        events = [json.loads(l) for l in (run_dir / "event_graphs.jsonl").read_text().splitlines() if l.strip()]
        from .auto_screen import prioritize_for_human

        drafts_by_id = {d["qa_id"]: d for d in drafts}
        screened_by_id = {s["qa_id"]: s for s in screened}
        events_by_id = {e["event_id"]: e for e in events}
        prioritized = prioritize_for_human(screened, drafts_by_id, k=args.human_k)
        if args.build_human_packets:
            pkt = build_packet(
                run_id=run_dir.name,
                prioritized=prioritized,
                drafts_by_id=drafts_by_id,
                screened_by_id=screened_by_id,
                events_by_id=events_by_id,
                out_dir=run_dir / "human_review_packets",
            )
            print(json.dumps({"packet_id": pkt["packet_id"], "n_items": pkt["n_items"]}, indent=2))
        else:
            print(json.dumps(prioritized, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
