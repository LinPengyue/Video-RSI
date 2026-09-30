#!/usr/bin/env python3
"""Sample type-balanced, video-disjoint LVBench training and Gate splits."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import re


QUESTION_TYPES = (
    "entity recognition", "event understanding", "key information retrieval",
    "reasoning", "summarization", "temporal grounding",
)


def read_metadata(path, video_dir, excluded=()):
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    rows, seen = [], set()
    for record in records:
        video_id = str(record["key"])
        if Path(video_id).name != video_id or video_id in {"", ".", ".."}:
            raise ValueError("Invalid video ID")
        if video_id in excluded:
            continue
        video_path = (video_dir / (video_id + ".mp4")).resolve()
        if not video_path.is_file():
            raise FileNotFoundError(video_path)
        duration = float(record["video_info"]["duration_minutes"]) * 60
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Invalid video duration: " + video_id)
        for qa in record["qa"]:
            uid = str(qa["uid"])
            if uid in seen:
                raise ValueError("Duplicate question UID: " + uid)
            seen.add(uid)
            kinds = qa["question_type"]
            kind = kinds[0] if isinstance(kinds, list) and kinds else kinds
            if kind not in QUESTION_TYPES:
                raise ValueError("Unsupported question type: " + str(kind))
            rows.append({"uid": uid, "video_id": video_id, "question_type": kind,
                         "duration": duration, "video_path": str(video_path), "qa": qa})
    return rows


def spread_sample(rows, allowed, quota, seed, cap):
    groups = defaultdict(lambda: defaultdict(list))
    for row in sorted(rows, key=lambda r: r["uid"]):
        if row["video_id"] in allowed:
            groups[row["question_type"]][row["video_id"]].append(row)
    rng = random.Random(seed)
    counts, selected = Counter(), []
    order = sorted(QUESTION_TYPES,
                   key=lambda k: (sum(map(len, groups[k].values())), k))
    for kind in order:
        buckets = groups[kind]
        for video in sorted(buckets):
            rng.shuffle(buckets[video])
        for _ in range(quota):
            available = sorted(v for v in buckets if buckets[v] and counts[v] < cap)
            if not available:
                return None
            minimum = min(counts[v] for v in available)
            video = rng.choice([v for v in available if counts[v] == minimum])
            selected.append(buckets[video].pop())
            counts[video] += 1
    return sorted(selected, key=lambda r: (QUESTION_TYPES.index(r["question_type"]), r["uid"]))


def resolve_seed(seed):
    return random.SystemRandom().getrandbits(64) if seed is None else seed


def sample_splits(rows, seed=None, train_per_type=36, gate_per_type=12,
                  gate_videos=18, max_per_video=6, attempts=10000):
    seed = resolve_seed(seed)
    if min(train_per_type, gate_per_type, gate_videos, max_per_video, attempts) <= 0:
        raise ValueError("Quotas and search limits must be positive")
    videos = sorted({r["video_id"] for r in rows})
    if len(videos) <= gate_videos:
        raise ValueError("Not enough videos for disjoint training and Gate splits")
    if gate_videos * max_per_video < gate_per_type * 6:
        raise ValueError("Gate video capacity is below the requested quota")
    if (len(videos) - gate_videos) * max_per_video < train_per_type * 6:
        raise ValueError("Training video capacity is below the requested quota")
    if gate_videos > gate_per_type * 6:
        raise ValueError("Gate video count exceeds the question count")
    totals = Counter(r["question_type"] for r in rows)
    for kind in QUESTION_TYPES:
        if totals[kind] < train_per_type + gate_per_type:
            raise ValueError("Insufficient questions for type: " + kind)
    rng = random.Random(seed)
    for attempt in range(attempts):
        gate_pool = set(rng.sample(videos, gate_videos))
        gate = spread_sample(rows, gate_pool, gate_per_type, seed + 2 * attempt, max_per_video)
        if gate is None or len({r["video_id"] for r in gate}) != gate_videos:
            continue
        train = spread_sample(rows, set(videos) - gate_pool, train_per_type,
                              seed + 2 * attempt + 1, max_per_video)
        if train is not None:
            return {"train": train, "gate": gate}
    raise ValueError("No feasible split found; check the pool, quotas, and search limit")


def split_question(text):
    matches = list(re.finditer(r"(?:^|\n)\s*\(([A-Z])\)\s*", text))
    labels = [m.group(1) for m in matches]
    if len(labels) < 2 or labels != list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:len(labels)]):
        raise ValueError("Expected consecutive (A), (B), ... option lines")
    question = text[:matches[0].start()].strip()
    options = {m.group(1): text[m.end():matches[i + 1].start() if i + 1 < len(matches)
                               else len(text)].strip() for i, m in enumerate(matches)}
    if not question or not all(options.values()):
        raise ValueError("Empty question or option")
    return question, options


def training_evidence(qa, duration):
    reference = qa.get("time_reference")
    parts = [reference] if isinstance(reference, str) else reference
    intervals, unparsed = [], False
    clock = r"\d+:\d{2}(?::\d{2})?(?:\.\d+)?"
    pattern = re.compile(r"(?<![\d:.])(" + clock + r")(?:\s*[-–—~]\s*(" + clock + r"))?(?![\d:.])")
    if isinstance(parts, list) and all(isinstance(part, str) for part in parts):
        for part in parts:
            matches = list(pattern.finditer(part))
            remainder = pattern.sub("", part)
            if remainder.strip(" \t\r\n,;，；/、[]()"):
                unparsed = True
            for match in matches:
                bounds = []
                for value in (match.group(1), match.group(2) or match.group(1)):
                    fields = [float(field) for field in value.split(":")]
                    if any(not math.isfinite(field) for field in fields) or any(field >= 60 for field in fields[1:]):
                        raise ValueError("Invalid annotation timestamp: " + value)
                    seconds = 0.0
                    for field in fields:
                        seconds = seconds * 60 + field
                    bounds.append(seconds)
                start, end = bounds
                if not 0 <= start <= end <= duration + 1:
                    raise ValueError("Annotation interval outside video bounds: " + str(reference))
                intervals.append({"start_seconds": start, "end_seconds": end,
                                  "kind": "point" if start == end else "interval"})
    else:
        unparsed = reference is not None
    present = bool(reference) and (not isinstance(reference, str) or bool(reference.strip()))
    status = ("partially_parsed_reference" if unparsed else "annotated_intervals") if intervals else (
        "unparsed_reference" if present else "unavailable")
    return {"source": "LVBench original annotation", "source_uid": qa.get("uid"),
            "time_reference_raw": reference, "intervals": intervals, "status": status}


def materialize(splits, output_dir, asr_dir=None):
    output_dir = output_dir.resolve()
    payloads, datasets = {}, {}
    for name, rows in splits.items():
        public, oracle = [], []
        for row in rows:
            qa = row["qa"]
            question, options = split_question(qa["question"])
            answer = str(qa["answer"]).strip().upper()
            if answer not in options:
                raise ValueError("Answer does not match options: " + row["uid"])
            item = {"sample_id": "lvbench_" + row["uid"], "question": question,
                    "options": options, "duration": row["duration"],
                    "video_path": row["video_path"], "question_type": row["question_type"]}
            if asr_dir is not None:
                asr_path = (asr_dir / (row["video_id"] + ".json")).resolve()
                if asr_path.is_file():
                    item["asr_path"] = str(asr_path)
            public.append(item)
            label = {"sample_id": item["sample_id"], "answer": answer}
            if name == "train":
                label["gold_evidence"] = training_evidence(qa, row["duration"])
            oracle.append(label)
        payloads[name + "_items.jsonl"] = public
        payloads[name + "_oracle.jsonl"] = oracle
        datasets[name] = {"public_items": str(output_dir / (name + "_items.jsonl")),
                          "oracle": str(output_dir / (name + "_oracle.jsonl"))}
    output_dir.mkdir(parents=True, exist_ok=False)
    for name, rows in payloads.items():
        (output_dir / name).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                              for row in rows), encoding="utf-8")
    (output_dir / "datasets.json").write_text(json.dumps(datasets, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True, help="LVBench video_info.meta.jsonl")
    parser.add_argument("--video-dir", type=Path, required=True, help="Directory containing <video ID>.mp4")
    parser.add_argument("--asr-dir", type=Path, help="Optional directory containing <video ID>.json transcripts")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, help="Optional fixed seed; omitted means a fresh random draw")
    parser.add_argument("--train-per-type", type=int, default=36)
    parser.add_argument("--gate-per-type", type=int, default=12)
    parser.add_argument("--gate-videos", type=int, default=18)
    parser.add_argument("--max-per-video", type=int, default=6)
    parser.add_argument("--attempts", type=int, default=10000)
    parser.add_argument("--exclude-videos", type=Path, help="Optional text file: one excluded video ID per line")
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error("Output directory already exists")
    excluded = set(args.exclude_videos.read_text().split()) if args.exclude_videos else set()
    rows = read_metadata(args.metadata, args.video_dir, excluded)
    args.seed = resolve_seed(args.seed)
    splits = sample_splits(rows, args.seed, args.train_per_type, args.gate_per_type,
                           args.gate_videos, args.max_per_video, args.attempts)
    materialize(splits, args.output_dir, args.asr_dir)
    summary = {"seed": args.seed, "metadata_sha256": hashlib.sha256(args.metadata.read_bytes()).hexdigest(),
               "train_per_type": args.train_per_type, "gate_per_type": args.gate_per_type,
               "gate_videos": args.gate_videos, "max_per_video": args.max_per_video,
               "excluded_video_ids": sorted(excluded),
               "splits": {name: {"questions": len(items),
                                  "videos": len({r["video_id"] for r in items}),
                                  "question_types": dict(Counter(r["question_type"] for r in items))}
                          for name, items in splits.items()}}
    (args.output_dir / "sampling_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["splits"], indent=2))


if __name__ == "__main__":
    main()
