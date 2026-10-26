#!/usr/bin/env python3
"""Shared library for controlled info-flow A/B experiments (no Editor / RSI)."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT = Path(__file__).resolve().parent
SAMPLES_PATH = PREFLIGHT / "exploratory_samples_n20.json"
TRAIN_CACHE = ROOT / "evolution" / "run-seed42" / "training_cache" / "initial_harness"
TRAIN_ITEMS = ROOT / "data" / "lvbench-split" / "train_items.jsonl"
TRAIN_ORACLE = ROOT / "data" / "lvbench-split" / "train_oracle.jsonl"
GATE_ORACLE = ROOT / "data" / "lvbench-split" / "gate_oracle.jsonl"
EFFECTIVE_CONFIG = ROOT / "evolution" / "run-seed42" / "effective_config.json"

PROMPT_VERSION = "infoflow_vqa_letter_json_v1"
CAPTION_PROMPT_VERSION = "infoflow_caption_overview_v1"
PROTOCOL = "infoflow_mechanism_ab_v1"

# Connectivity subsample seed (fixed; not accuracy-based).
CONNECTIVITY_SEED = 20261027
DIAG_SELECT_SEED = 20261028

# First-batch budget (A-reuse + B-direct only).
BUDGET_QWEN_DIRECT = 20
BUDGET_DEEPSEEK_AREUSE = 20
BUDGET_EDITOR = 0

# Diagnosis budget caps (separate from first batch).
BUDGET_DIAG_MAX_SAMPLES = 8


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_gate_ids() -> set[str]:
    ids = set()
    for line in GATE_ORACLE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.add(json.loads(line)["sample_id"])
    return ids


def load_oracle(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["sample_id"]] = row["answer"]
    return out


def load_train_items() -> dict[str, dict]:
    out = {}
    for line in TRAIN_ITEMS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["sample_id"]] = row
    return out


def load_frozen_ids() -> list[str]:
    frozen = load_json(SAMPLES_PATH)
    ids = list(frozen["sample_ids"])
    gate = load_gate_ids()
    leak = [i for i in ids if i in gate]
    if leak:
        raise RuntimeError("Gate leakage in frozen samples: %s" % leak)
    return ids


def cache_by_sample_id() -> dict[str, dict]:
    out = {}
    for path in TRAIN_CACHE.glob("item_*.json"):
        row = load_json(path)
        out[row["sample_id"]] = row
    return out


def overview_bundle(traj: dict) -> dict:
    for step in traj.get("memory") or []:
        if step.get("tool") != "overview":
            continue
        obs = step.get("observation") or {}
        frames = obs.get("frames") or []
        text = ((obs.get("perception") or {}).get("text") or "").strip()
        timestamps = [float(f["timestamp"]) for f in frames]
        return {
            "timestamps": timestamps,
            "n_frames": len(timestamps),
            "perception_text": text,
            "frame_ids": [f.get("id") for f in frames],
        }
    raise ValueError("no overview step")


def format_options(options: dict) -> str:
    keys = sorted(options.keys())
    return "\n".join("%s. %s" % (k, options[k]) for k in keys)


def vqa_prompt(question: str, options: dict, *, caption: str | None = None) -> str:
    """Unified VQA prompt (PROMPT_VERSION)."""
    letters = ",".join(sorted(options.keys()))
    parts = [
        "You are answering a multiple-choice video question.",
        'Reply with ONLY a JSON object of the form {"type":"answer","answer":"<LETTER>"}.',
        "LETTER must be exactly one of: %s." % letters,
        "Do not include explanation outside the JSON object.",
        "",
        "Question:",
        question.strip(),
        "",
        "Options:",
        format_options(options),
    ]
    if caption is not None:
        parts.extend(
            [
                "",
                "Video overview description (text only; no raw frames provided in this call):",
                caption.strip(),
            ]
        )
    return "\n".join(parts)


def caption_prompt() -> str:
    return (
        "Describe the visual content of these video frames in detail suitable for answering a later "
        "multiple-choice VQA question. Cover people, objects, on-screen text, actions, scene changes, "
        "and note observations by timestamp_seconds when present. Do NOT answer any question and do "
        "NOT choose an option letter."
    )


def parse_answer_letter(text: str, options: dict) -> tuple[str | None, str, str]:
    """Return (letter_or_None, parse_mode, error)."""
    from solver_full_workspace.answers import parse_decision_details

    raw = (text or "").strip()
    if not raw:
        return None, "empty", "empty_response"
    try:
        decision, mode = parse_decision_details(raw, options)
        if decision.get("type") == "answer":
            return decision["answer"], mode, ""
        return None, mode, "non_answer_decision"
    except Exception:
        pass
    # Fallback: last standalone option letter
    letters = set(options.keys())
    m = re.search(r"\b([A-D])\b", raw.upper())
    if m and m.group(1) in letters:
        return m.group(1), "regex_fallback", ""
    # Single letter after Answer:
    m = re.search(r"(?:answer|选项)\s*[:：]\s*([A-D])\b", raw, re.I)
    if m and m.group(1).upper() in letters:
        return m.group(1).upper(), "answer_prefix_fallback", ""
    return None, "unparsed", "could_not_parse_letter"


def ffmpeg_bin(config: dict) -> str:
    ffmpeg = config.get("services", {}).get("ffmpeg", "ffmpeg")
    if ffmpeg == "imageio-ffmpeg":
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            return get_ffmpeg_exe()
        except ImportError:
            # Fall back to videorsi-packaged binary or system ffmpeg.
            candidates = [
                Path("/home/descfly/miniconda3/envs/videorsi/lib/python3.12/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"),
                Path("/usr/bin/ffmpeg"),
            ]
            for c in candidates:
                if c.is_file():
                    return str(c)
            import shutil

            found = shutil.which("ffmpeg")
            if found:
                return found
            raise RuntimeError("ffmpeg binary not found (imageio_ffmpeg missing and no system ffmpeg)")
    return ffmpeg


def extract_frames(video_path: Path, timestamps: list[float], out_dir: Path, config: dict) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_bin(config)
    paths = []
    for i, ts in enumerate(timestamps):
        dest = out_dir / ("frame_%06d.jpg" % i)
        if dest.is_file() and dest.stat().st_size > 0:
            paths.append(dest)
            continue
        subprocess.run(
            [
                ff, "-v", "error", "-ss", str(ts), "-i", str(video_path),
                "-frames:v", "1", "-vf", "scale=768:-2", "-threads", "1", "-y", str(dest),
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
        if not dest.is_file() or dest.stat().st_size == 0:
            raise RuntimeError("ffmpeg produced empty frame at t=%s" % ts)
        paths.append(dest)
    return paths


def bundle_sha(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: x.name):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def estimate_cny(role: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> float:
    import sys

    sys.path.insert(0, str(ROOT))
    from batch_billing import DEFAULT_MODEL_RATES, role_cost

    rates = DEFAULT_MODEL_RATES[role]
    with_cache, _ = role_cost(prompt_tokens, completion_tokens, cached_tokens, rates, apply_cache=True)
    return with_cache


@dataclass
class ProviderResponse:
    text: str
    usage: dict
    request_model: str
    role: str
    frames: int
    latency_seconds: float
    status: str
    error: str = ""
    raw_choice_dump: str = ""


class MockProvider:
    """Deterministic offline provider for tests."""

    def __init__(self, letter_map: dict[str, str] | None = None):
        self.letter_map = letter_map or {}
        self.calls: list[dict] = []

    def chat(self, role: str, messages: list, *, frames: int = 0, request_model: str = "") -> ProviderResponse:
        blob = json.dumps(messages, ensure_ascii=False)
        key = "%s:%s" % (role, sha256_text(blob)[:12])
        self.calls.append({"role": role, "frames": frames, "key": key})
        # Caption calls: return a fixed description
        if "Do NOT answer any question" in blob or "Do not answer any question" in blob:
            text = "Mock caption: a person walks across a room; on-screen text visible at mid timestamps."
        else:
            # Prefer letter encoded in a marker for tests, else A
            letter = self.letter_map.get(key, "A")
            text = json.dumps({"type": "answer", "answer": letter})
        return ProviderResponse(
            text=text,
            usage={"prompt_tokens": 100 + frames * 10, "completion_tokens": 20, "cached_tokens": 0},
            request_model=request_model or ("mock-%s" % role),
            role=role,
            frames=frames,
            latency_seconds=0.01,
            status="ok",
        )


class HttpProvider:
    """Pinned HTTPS chat completions provider (same ABI as engine PinnedProvider)."""

    def __init__(self, config: dict):
        svc = config["services"]
        self.config = svc
        self.key = os.environ.get(svc["key_env"], "")
        self.endpoint = os.environ.get(svc["endpoint_env"], "").rstrip("/")
        if not self.key or not self.endpoint.startswith("https://"):
            raise RuntimeError("HTTPS provider endpoint/key unavailable (set %s / %s)" % (svc["endpoint_env"], svc["key_env"]))

    def chat(self, role: str, messages: list, *, frames: int = 0, request_model: str = "") -> ProviderResponse:
        model = self.config[role]
        req_model = request_model or model["request_model"]
        payload = {
            "model": req_model,
            "messages": messages,
            "temperature": self.config.get("temperature", 0),
            "max_tokens": model["max_tokens"],
            "thinking": {"type": "disabled"},
            "stream": False,
        }
        encoded = json.dumps(payload).encode()
        retries = int(self.config.get("provider_retries", 1))
        timeout = float(self.config.get("timeout_seconds", 240))
        last_err = ""
        for attempt in range(retries + 1):
            started = time.monotonic()
            try:
                request = urllib.request.Request(
                    self.endpoint + "/chat/completions",
                    data=encoded,
                    headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    value = json.load(response)
                if not value.get("choices"):
                    raise RuntimeError("empty provider choices")
                message = value["choices"][0]["message"]
                text = message.get("content", "")
                if not isinstance(text, str):
                    text = json.dumps(text, ensure_ascii=False)
                usage = value.get("usage") or {}
                return ProviderResponse(
                    text=text,
                    usage={
                        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                        "completion_tokens": int(usage.get("completion_tokens") or 0),
                        "cached_tokens": int(
                            (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
                            or usage.get("cached_tokens")
                            or 0
                        ),
                    },
                    request_model=value.get("model") or req_model,
                    role=role,
                    frames=frames,
                    latency_seconds=time.monotonic() - started,
                    status="ok",
                    raw_choice_dump=json.dumps(message, ensure_ascii=False)[:4000],
                )
            except Exception as exc:
                last_err = "%s: %s" % (type(exc).__name__, exc)
                transient = isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError))
                if isinstance(exc, urllib.error.HTTPError):
                    transient = exc.code in (408, 429, 500, 502, 503, 504)
                if not transient or attempt == retries:
                    return ProviderResponse(
                        text="",
                        usage={},
                        request_model=req_model,
                        role=role,
                        frames=frames,
                        latency_seconds=time.monotonic() - started,
                        status="error",
                        error=last_err,
                    )
        return ProviderResponse("", {}, req_model, role, frames, 0.0, "error", last_err)


def vision_messages(prompt: str, frame_paths: list[Path], timestamps: list[float]) -> list:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for path, ts in zip(frame_paths, timestamps):
        content.append({"type": "text", "text": "timestamp_seconds=%s" % ts})
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()
                },
            }
        )
    return [{"role": "user", "content": content}]


def text_messages(prompt: str) -> list:
    return [{"role": "user", "content": prompt}]


class ResultStore:
    """Atomic per-call resume store under run_dir/calls/."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.calls_dir = run_dir / "calls"
        self.frames_dir = run_dir / "frames"
        self.calls_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = run_dir / "run_meta.json"
        self.ledger_path = run_dir / "call_ledger.jsonl"

    def call_key(self, sample_id: str, path_name: str, stage: str) -> str:
        return "%s__%s__%s" % (sample_id, path_name, stage)

    def call_path(self, key: str) -> Path:
        return self.calls_dir / ("%s.json" % key)

    def load_call(self, sample_id: str, path_name: str, stage: str) -> dict | None:
        p = self.call_path(self.call_key(sample_id, path_name, stage))
        if p.is_file():
            return load_json(p)
        return None

    def save_call(self, record: dict) -> None:
        key = self.call_key(record["sample_id"], record["path"], record["stage"])
        write_json(self.call_path(key), record)
        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "status": record.get("status"), "ts": time.time()}, ensure_ascii=False) + "\n")

    def successful(self, sample_id: str, path_name: str, stage: str) -> bool:
        row = self.load_call(sample_id, path_name, stage)
        return bool(row and row.get("status") == "ok")

    def count_ok(self, path_name: str, stage: str | None = None) -> int:
        n = 0
        for p in self.calls_dir.glob("*.json"):
            row = load_json(p)
            if row.get("path") != path_name:
                continue
            if stage is not None and row.get("stage") != stage:
                continue
            if row.get("status") == "ok":
                n += 1
        return n


def connectivity_ids(all_ids: list[str], n: int = 4) -> list[str]:
    rng = random.Random(CONNECTIVITY_SEED)
    ids = list(all_ids)
    rng.shuffle(ids)
    return sorted(ids[:n])


def pick_diag_ids(disagreement_ids: list[str], max_n: int = BUDGET_DIAG_MAX_SAMPLES) -> list[str]:
    """Pre-registered rule: shuffle disagreements with fixed seed, take up to max_n."""
    rng = random.Random(DIAG_SELECT_SEED)
    ids = list(disagreement_ids)
    rng.shuffle(ids)
    return sorted(ids[:max_n])


def load_services_config() -> dict:
    cfg = load_json(EFFECTIVE_CONFIG)
    return cfg
