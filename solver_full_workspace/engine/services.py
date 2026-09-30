"""Model-provider and media services. No tool selection or evidence interpretation."""
import base64
import json
import math
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


class ServiceError(RuntimeError):
    pass


def http_error_details(exc, secret):
    """Keep useful provider diagnostics, never headers, URLs or raw response bodies."""
    try:
        value = json.loads(exc.read(65536))
        error = value.get('error', {})
    except (ValueError, OSError, AttributeError):
        return {'message': 'non-JSON or unavailable HTTP error body'}
    if not isinstance(error, dict):
        return {'message': 'unstructured HTTP error'}
    result = {}
    for key in ('type', 'code', 'message', 'param'):
        if key not in error:
            continue
        text = str(error[key])
        if secret:
            text = text.replace(secret, '[REDACTED]')
        text = re.sub(r'https?://\S+', '[URL]', text)
        text = re.sub(r'(?i)(bearer\s+|sk-|hf_)[A-Za-z0-9_./+=-]+', '[REDACTED]', text)
        result[key] = text[:1500]
    return result


class OfflineProvider:
    """No-network provider for startup/dependency checks; cannot answer questions."""
    def chat(self, *args, **kwargs):
        raise ServiceError("provider calls disabled in offline preflight")


class Meter:
    def __init__(self):
        self.events = []

    def summary(self):
        providers = [e for e in self.events if e["kind"] == "provider"]
        return {

            "frames": sum(e.get("frames", 0) for e in providers + [e for e in self.events if e["kind"] == "ocr"]),
            "qwen_frames": sum(e.get("frames", 0) for e in providers if e["role"] == "qwen"),
            "ocr_frames": sum(e.get("frames", 0) for e in self.events if e["kind"] == "ocr"),
            "frames_extracted": sum(e.get("frames", 0) for e in self.events if e["kind"] == "extraction"),
            "qwen_calls": sum(e["role"] == "qwen" for e in providers),
            "deepseek_calls": sum(e["role"] == "deepseek" for e in providers),
            "ocr_calls": sum(e["kind"] == "ocr" for e in self.events),
            "provider_errors": sum(e.get("status") == "error" for e in providers),
            "token_usage_unavailable_calls": sum(not all(k in e.get("usage", {}) for k in ("prompt_tokens", "completion_tokens")) for e in providers),
            "input_tokens": sum(e.get("usage", {}).get("prompt_tokens", 0) for e in providers),
            "output_tokens": sum(e.get("usage", {}).get("completion_tokens", 0) for e in providers),
        }


class PinnedProvider:
    def __init__(self, config, meter):
        self.config, self.meter = config, meter
        self.key = os.environ.get(config["key_env"], "")
        self.endpoint = os.environ.get(config["endpoint_env"], "").rstrip("/")
        if not self.key or not self.endpoint.startswith("https://"):
            raise ServiceError("configured HTTPS provider endpoint/key unavailable")

    def chat(self, role, messages, frames=0, payload_extra=None, before_attempt=None):
        model = self.config[role]
        payload = {"model": model["request_model"], "messages": messages,
                   "temperature": self.config["temperature"], "max_tokens": model["max_tokens"],
                   "thinking": {"type": "disabled"}, "stream": False}

        for key in ("tools", "tool_choice", "parallel_tool_calls"):
            if payload_extra and key in payload_extra:
                payload[key] = payload_extra[key]
        encoded_payload = json.dumps(payload).encode()
        for attempt in range(self.config["provider_retries"] + 1):
            if before_attempt:
                before_attempt()
            event = {"kind": "provider", "role": role, "request_model": model["request_model"], "frames": frames, "attempt": attempt, "status": "pending", "request_bytes": len(encoded_payload)}
            self.meter.events.append(event)
            started = time.monotonic()
            try:
                request = urllib.request.Request(self.endpoint + "/chat/completions", data=encoded_payload, headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=self.config["timeout_seconds"]) as response:
                    value = json.load(response)
                event.update(response_model=value.get("model"), usage=value.get("usage", {}))
                if not value.get("choices"):
                    raise ServiceError("empty provider choices")
                event["status"] = "ok"
                return value
            except Exception as exc:
                event.update(status="error", error_type=type(exc).__name__)
                transient = isinstance(exc, (TimeoutError, ConnectionError, urllib.error.URLError))
                if isinstance(exc, urllib.error.HTTPError):
                    transient = exc.code in (408, 429, 500, 502, 503, 504)
                    event["http_status"] = exc.code
                    event['http_error'] = http_error_details(exc, self.key)
                if not transient or attempt == self.config["provider_retries"]:

                    raise ServiceError(type(exc).__name__ + ": provider call failed") from exc
            finally:
                event["latency_seconds"] = time.monotonic() - started


def perception_content(response):
    message = response["choices"][0]["message"]
    text = message.get("content", "")
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    value = {"text": text}
    clean = text.strip()
    if clean.startswith("```") and clean.endswith("```"):
        clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        value["json"] = json.loads(clean)
    except ValueError:
        pass
    return value


class LocalOCR:
    def __init__(self, model_root):
        self.root, self.engine, self.lock = model_root, None, threading.Lock()

    def recognize(self, path):
        with self.lock:
            if self.engine is None:
                from importlib.metadata import version
                from rapidocr import RapidOCR, EngineType, LangDet, LangRec, ModelType, OCRVersion
                if version("rapidocr") != "3.9.2":
                    raise ServiceError("expected rapidocr 3.9.2")
                self.engine = RapidOCR(params={
                    "Global.model_root_dir": self.root, "Global.use_cls": False, "Global.log_level": "error",
                    "Det.engine_type": EngineType.ONNXRUNTIME, "Det.lang_type": LangDet.CH,
                    "Det.model_type": ModelType.SMALL, "Det.ocr_version": OCRVersion.PPOCRV6,
                    "Rec.engine_type": EngineType.ONNXRUNTIME, "Rec.lang_type": LangRec.CH,
                    "Rec.model_type": ModelType.SMALL, "Rec.ocr_version": OCRVersion.PPOCRV6,
                    "EngineConfig.onnxruntime.intra_op_num_threads": 2, "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                })
            result = self.engine(str(path))
            texts = result.txts if result.txts is not None else []
            boxes = result.boxes if result.boxes is not None else []
            scores = result.scores if result.scores is not None else []
            if not len(texts) == len(boxes) == len(scores):
                raise ServiceError("OCR output lengths differ")
            return [{"text": str(t), "bbox": [[float(x), float(y)] for x, y in b], "confidence": float(s)} for t, b, s in zip(texts, boxes, scores)]


class Services:
    """One broker per item; opaque frame handles cannot reference another video."""
    def __init__(self, item, media, config, scratch, provider=None, ocr=None):
        self.item, self.media, self.config = item, media, config
        self.scratch = Path(scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.meter = Meter()
        self.provider = provider or PinnedProvider(config["services"], self.meter)
        self.provider.meter = self.meter
        self.ocr = ocr or LocalOCR(config["services"]["ocr_model_root"])
        self.frames, self.calls, self.trace = {}, 0, []

    def call(self, name, args):
        self.calls += 1
        if self.calls > self.config["solver"]["max_service_calls"]:
            raise ServiceError("service call budget exhausted")
        allowed = {"deepseek": {"messages"}, "sample_frames": {"start", "end", "count", "timestamps"},
                   "qwen": {"frames", "prompt"}, "asr": set(), "ocr": {"frames"}}
        if name not in allowed or not isinstance(args, dict) or set(args) - allowed[name]:
            raise ServiceError("unknown service or unsupported parameter")
        entry = {"service": name, "arguments": args}
        self.trace.append(entry)
        try:
            result = self._call(name, args)
            entry["result"] = result
            return result
        except Exception as exc:
            entry["error"] = type(exc).__name__ + ": " + str(exc)
            raise

    def _check_frames(self, n):
        if self.meter.summary()["frames"] + n > self.config["solver"]["max_frames"]:
            raise ServiceError("frame exposure budget exhausted")

    def _call(self, name, args):
        if name == "deepseek":
            return perception_content(self.provider.chat("deepseek", args["messages"]))
        if name == "sample_frames":
            return self.sample(args)
        if name == "asr":
            path = self.media.get("asr_path")
            if not path:
                return {"status": "unavailable", "segments": []}
            value = json.loads(Path(path).read_text())

            segments = value if isinstance(value, list) else value.get("segments")
            if not isinstance(segments, list):
                raise ServiceError("ASR requires explicit timestamped segments")
            for segment in segments:
                if not isinstance(segment, dict) or not all(k in segment for k in ("start", "end", "text")):
                    raise ServiceError("invalid ASR segment")
                if not 0 <= float(segment["start"]) <= float(segment["end"]):
                    raise ServiceError("invalid ASR time range")
            return {"status": "available", "segments": segments}
        ids = args["frames"]
        if not isinstance(ids, list) or not ids or any(fid not in self.frames for fid in ids):
            raise ServiceError("unknown frame handle")
        frames = [self.frames[fid] for fid in ids]
        self._check_frames(len(frames))
        if name == "qwen":
            content = [{"type": "text", "text": args["prompt"]}]
            for frame in frames:
                content.extend([
                    {"type": "text", "text": "timestamp_seconds=" + str(frame["timestamp"])},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(frame["path"].read_bytes()).decode()}},
                ])
            return perception_content(self.provider.chat("qwen", [{"role": "user", "content": content}], frames=len(frames), before_attempt=lambda: self._check_frames(len(frames))))
        result = []
        for frame in frames:
            self.meter.events.append({"kind": "ocr", "frames": 1})
            for row in self.ocr.recognize(frame["path"]):
                result.append(dict(row, timestamp=frame["timestamp"]))
        return result

    def sample(self, args):
        duration = self.item["duration"]
        ffmpeg = self.config["services"]["ffmpeg"]
        if ffmpeg == "imageio-ffmpeg":
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        timestamps = args.get("timestamps")
        if timestamps is None:
            start, end, count = float(args["start"]), float(args["end"]), args["count"]
            if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= self.config["solver"]["max_frames"] or not 0 <= start < end <= duration:
                raise ServiceError("invalid sampling interval/count")
            timestamps = [start + (end - start) * (i + .5) / count for i in range(count)]
        if not isinstance(timestamps, list) or not timestamps or len(self.frames) + len(timestamps) > self.config["solver"]["max_frames"]:
            raise ServiceError("invalid or excessive frame extraction")
        output = []
        for timestamp in timestamps:
            timestamp = float(timestamp)
            if not math.isfinite(timestamp) or not 0 <= timestamp < duration:
                raise ServiceError("invalid frame timestamp")
            fid = "frame_%06d" % len(self.frames)
            path = self.scratch / (fid + ".jpg")
            subprocess.run([ffmpeg, "-v", "error", "-ss", str(timestamp), "-i", str(self.media["video_path"]), "-frames:v", "1", "-vf", "scale=768:-2", "-threads", "1", "-y", str(path)], capture_output=True, check=True, timeout=60)
            if not path.is_file() or path.stat().st_size == 0:
                raise ServiceError("frame extraction produced no image")
            self.frames[fid] = {"timestamp": timestamp, "path": path}
            self.meter.events.append({"kind": "extraction", "frames": 1})
            output.append({"id": fid, "timestamp": timestamp})
        return output
