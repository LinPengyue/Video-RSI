import json
import math
import os
from pathlib import Path

GATE_POLICY = 'accuracy_gain_10pct_or_save_20pct_drop1_v1'
MAX_EVOLUTION_ROUNDS = 20


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".pending")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def public_item(row):

    value = {key: row[key] for key in ("sample_id", "question", "options", "duration")}
    options = value["options"]
    if isinstance(options, list):
        options = {chr(65 + i): text for i, text in enumerate(options)}
    if not isinstance(options, dict) or not 2 <= len(options) <= 26:
        raise ValueError("each item needs 2..26 explicit choice options")
    if any(len(k) != 1 or not "A" <= k <= "Z" for k in options):
        raise ValueError("option keys must be uppercase single letters")
    if not isinstance(value["question"], str) or not math.isfinite(float(value["duration"])) or float(value["duration"]) <= 0:
        raise ValueError("invalid question or video duration")
    value["options"] = options
    value["duration"] = float(value["duration"])
    return value


def validate_config(config):
    limit = config.get('evolution', {}).get('max_rounds', MAX_EVOLUTION_ROUNDS)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_EVOLUTION_ROUNDS:
        raise ValueError('evolution.max_rounds must be 1..20')
    if config["protocol"] != "full-candidate-v1":
        raise ValueError("wrong protocol")
    for section, keys in {
        "solver": ("max_steps", "max_service_calls", "max_frames", "timeout_seconds"),
        "editor": ("max_provider_calls", "timeout_seconds"),
        "execution": ("concurrency",),
    }.items():
        for key in keys:
            number = config[section][key]
            if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
                raise ValueError("%s.%s must be a positive integer" % (section, key))
    investigation_frames = config.get("investigation", {}).get("max_frames", config["solver"]["max_frames"])
    if isinstance(investigation_frames, bool) or not isinstance(investigation_frames, int) or investigation_frames <= 0:
        raise ValueError("investigation.max_frames must be a positive integer")
    if config["gate"]["policy"] != GATE_POLICY:
        raise ValueError("unknown Gate policy")
    ceiling = config["gate"]["max_mean_frames"]
    if ceiling is not None and (not math.isfinite(ceiling) or ceiling <= 0):
        raise ValueError("invalid frame ceiling")
    for role in ("deepseek", "qwen"):
        model = config["services"][role]
        if not isinstance(model.get("request_model"), str) or not model["request_model"].strip():
            raise ValueError("request_model must be a nonempty string")
    return config
