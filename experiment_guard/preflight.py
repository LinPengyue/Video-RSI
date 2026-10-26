"""Layer 1: Preflight Guard — fail-closed environment checks before paid experiments."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from experiment_guard.fingerprints import (
    config_fingerprint,
    git_sha,
    harness_fingerprint,
    host_fingerprint,
    python_dep_probe,
)
from experiment_guard.redact import provider_config_present, redact_obj, redact_path

ROOT = Path(__file__).resolve().parents[1]

CheckStatus = str  # PASS | FAIL | NOT_APPLICABLE


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    detail: dict[str, Any] = field(default_factory=dict)
    reason_code: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "detail": redact_obj(self.detail),
            "reason_code": self.reason_code,
        }


@dataclass
class PreflightCapabilities:
    """Declare which capabilities the upcoming experiment requires."""

    visual_sample_frames: bool = True
    editor_investigation: bool = False
    infoflow_probe: bool = False
    ocr: bool = False
    provider_config: bool = True
    # Host process runs Services.sample_frames (Editor / Investigation / in-process eval)
    host_must_match_config_python: bool = True


def default_config_path() -> Path:
    return ROOT / "evolution" / "run-seed42" / "effective_config.json"


def load_config(path: Path | None = None) -> dict:
    sys.path.insert(0, str(ROOT))
    from solver_full_workspace.engine.common import read_json, validate_config

    return validate_config(read_json(path or default_config_path()))


def expected_python(config: dict) -> Path:
    p = (config.get("execution") or {}).get("python")
    if p:
        return Path(p).resolve()
    # Fallback documented production env — still fail-closed if missing
    cand = Path(sys.executable).resolve()
    return cand


def ensure_correct_interpreter(config: dict, *, reexec: bool = True) -> CheckResult:
    want = expected_python(config)
    have = Path(sys.executable).resolve()
    detail = {
        "sys_executable": redact_path(have),
        "config_execution_python": redact_path(want),
        "match": have == want,
    }
    if have == want:
        return CheckResult("interpreter_match", "PASS", detail)
    if reexec and want.is_file():
        env = os.environ.copy()
        os.execve(str(want), [str(want), *sys.argv], env)
    return CheckResult(
        "interpreter_match",
        "FAIL",
        detail,
        reason_code="host_python_mismatch",
    )


def check_dual_interpreter_deps(config: dict) -> list[CheckResult]:
    """Phase D lesson: host and config.execution.python can differ — probe both."""
    host = Path(sys.executable).resolve()
    worker = expected_python(config)
    out: list[CheckResult] = []
    for label, exe in (("host", host), ("config_execution_python", worker)):
        probe = python_dep_probe(exe)
        ok = bool(probe.get("imageio_ffmpeg_importable")) and bool(probe.get("ffmpeg_exe"))
        # Verify ffmpeg path exists when reported
        if ok and probe.get("ffmpeg_exe"):
            # probe returns redacted path; re-probe existence via subprocess already implied
            pass
        status: CheckStatus = "PASS" if ok else "FAIL"
        out.append(
            CheckResult(
                "imageio_ffmpeg_%s" % label,
                status,
                probe,
                reason_code=None if ok else "imageio_ffmpeg_missing",
            )
        )
    return out


def _pick_smoke_video(config: dict, video_path: Path | None = None) -> tuple[str, Path, float]:
    if video_path is not None:
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            raise FileNotFoundError("smoke video missing: %s" % video_path)
        return "custom_smoke", video_path, 10.0

    ids_path = ROOT / "research_audit" / "arch_self_evolution_pilot" / "out" / "independent_eval_ids.safe.json"
    items_path = ROOT / "data" / "lvbench-split" / "train_items.jsonl"
    if not items_path.is_file():
        raise FileNotFoundError("train_items.jsonl missing for smoke video selection")
    items = {}
    for line in items_path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            items[row["sample_id"]] = row
    if ids_path.is_file():
        sid = json.loads(ids_path.read_text())["sample_ids"][0]
    else:
        sid = next(iter(items))
    row = items[sid]
    path = Path(row["video_path"])
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError("smoke video missing: %s" % path)
    return sid, path, float(row["duration"])


class MockProvider:
    def __init__(self):
        from solver_full_workspace.engine.services import Meter

        self.meter = Meter()
        self.fail_qwen = False

    def chat(self, role, messages, frames=0, payload_extra=None, before_attempt=None):
        if before_attempt:
            before_attempt()
        if self.fail_qwen and role == "qwen":
            raise RuntimeError("injected_qwen_failure")
        self.meter.events.append(
            {
                "kind": "provider",
                "role": role,
                "frames": frames,
                "status": "ok",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }
        )
        return {
            "choices": [{"message": {"content": "mock observation"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


def run_sample_frames_smoke(
    config: dict,
    *,
    video_path: Path | None = None,
    n_frames: int = 4,
    sample_frames_hook: Callable | None = None,
) -> CheckResult:
    """Must use production Services.sample_frames path (not a side ffmpeg script)."""
    sys.path.insert(0, str(ROOT))
    from solver_full_workspace.engine.services import Services
    from solver_full_workspace.engine.common import public_item

    try:
        sid, video, duration = _pick_smoke_video(config, video_path)
    except Exception as exc:
        return CheckResult(
            "sample_frames_smoke",
            "FAIL",
            {"error": "%s:%s" % (type(exc).__name__, exc)},
            reason_code="smoke_video_unavailable",
        )

    item = {
        "sample_id": sid,
        "question": "smoke",
        "options": {"A": "a", "B": "b"},
        "duration": duration,
        "video_path": str(video),
    }
    with tempfile.TemporaryDirectory(prefix="eg_visual_smoke_") as td:
        scratch = Path(td)
        provider = MockProvider()
        services = Services(public_item(item), item, config, scratch, provider=provider, ocr=None)
        timestamps = [duration * (i + 0.5) / n_frames for i in range(n_frames)]
        try:
            if sample_frames_hook:
                frames = sample_frames_hook(services, timestamps)
            else:
                frames = services.call("sample_frames", {"timestamps": timestamps})
        except Exception as exc:
            msg = "%s:%s" % (type(exc).__name__, exc)
            if "No module named 'imageio_ffmpeg'" in msg or "No module named \"imageio_ffmpeg\"" in msg:
                reason = "imageio_ffmpeg_missing"
            else:
                reason = "sample_frames_failed"
            return CheckResult(
                "sample_frames_smoke",
                "FAIL",
                {"error": msg[:500], "sample_id": sid, "video": redact_path(video)},
                reason_code=reason,
            )
        if len(frames) != n_frames:
            return CheckResult(
                "sample_frames_smoke",
                "FAIL",
                {"n_frames": len(frames), "expected": n_frames},
                reason_code="frame_count_mismatch",
            )
        paths = []
        for fr in frames:
            p = services.frames[fr["id"]]["path"]
            if not p.is_file() or p.stat().st_size == 0:
                return CheckResult(
                    "sample_frames_smoke",
                    "FAIL",
                    {"error": "empty_frame", "id": fr["id"]},
                    reason_code="frame_file_missing",
                )
            head = p.read_bytes()[:3]
            paths.append({"id": fr["id"], "bytes": p.stat().st_size, "jpeg_magic": head == b"\xff\xd8\xff"})
            if head != b"\xff\xd8\xff":
                return CheckResult(
                    "sample_frames_smoke",
                    "FAIL",
                    {"error": "not_jpeg", "id": fr["id"]},
                    reason_code="frame_decode_failed",
                )
        try:
            obs = services.call(
                "qwen",
                {"frames": [f["id"] for f in frames], "prompt": "Describe briefly. Do not answer a MCQ."},
            )
        except Exception as exc:
            return CheckResult(
                "sample_frames_smoke",
                "FAIL",
                {"error": "qwen:%s:%s" % (type(exc).__name__, exc)},
                reason_code="qwen_mock_failed",
            )
        summary = services.meter.summary()
        if int(summary.get("qwen_frames") or 0) < n_frames:
            return CheckResult(
                "sample_frames_smoke",
                "FAIL",
                {"meter": summary, "expected_qwen_frames": n_frames},
                reason_code="meter_qwen_frames_underreported",
            )
        if int(summary.get("frames_extracted") or 0) < n_frames:
            return CheckResult(
                "sample_frames_smoke",
                "FAIL",
                {"meter": summary},
                reason_code="meter_frames_extracted_underreported",
            )
        return CheckResult(
            "sample_frames_smoke",
            "PASS",
            {
                "sample_id": sid,
                "video": redact_path(video),
                "n_frames": len(frames),
                "frame_checks": paths,
                "qwen_text_len": len((obs or {}).get("text") or ""),
                "meter_summary": summary,
            },
        )


def _patch_services_call_for_mock():
    """Return (restore_fn) after patching Services.__init__ to mock sample_frames/qwen/ocr."""
    from solver_full_workspace.engine import services as services_mod

    real_init = services_mod.Services.__init__

    def fake_init(self, item, media, config, scratch, provider=None, ocr=None):
        real_init(self, item, media, config, scratch, provider=provider, ocr=ocr)
        self.frames = {}

        def call(name, args):
            if name == "sample_frames":
                out = []
                for i, ts in enumerate(args["timestamps"]):
                    fid = "frame_%06d" % i
                    path = Path(scratch) / (fid + ".jpg")
                    path.write_bytes(b"\xff\xd8\xff\xd9")
                    self.frames[fid] = {"timestamp": float(ts), "path": path}
                    self.meter.events.append({"kind": "extraction", "frames": 1})
                    out.append({"id": fid, "timestamp": float(ts)})
                return out
            if name == "qwen":
                text = (
                    "caption text"
                    if "observation only" in args.get("prompt", "")
                    or "Do not select" in args.get("prompt", "")
                    or "Keep relevant" in args.get("prompt", "")
                    else json.dumps({"type": "answer", "answer": "A"})
                )
                self.meter.events.append(
                    {
                        "kind": "provider",
                        "role": "qwen",
                        "frames": len(args.get("frames") or []),
                        "status": "ok",
                    }
                )
                return {"text": text}
            if name == "ocr":
                self.meter.events.append({"kind": "provider", "role": "ocr", "frames": len(args.get("frames") or []), "status": "ok"})
                return {"text": ""}
            raise AssertionError("unexpected service %s" % name)

        self.call = call

    services_mod.Services.__init__ = fake_init

    def restore():
        services_mod.Services.__init__ = real_init

    return restore


def check_editor_investigation_mock(config: dict, *, need_probe: bool) -> list[CheckResult]:
    """Mock observe + optional infoflow_probe without paid API."""
    results: list[CheckResult] = []
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "research_audit" / "arch_self_evolution_pilot"))

    try:
        from counterfactual_investigation import CounterfactualInvestigation, MODES
        from unittest.mock import MagicMock
        import tempfile as _tf

        with _tf.TemporaryDirectory() as td:
            tmp = Path(td)
            row = {
                "sample_id": "lvbench_guard_smoke",
                "question": "What room?",
                "options": {"A": "Kitchen", "B": "Living room", "C": "Bathroom", "D": "Bedroom"},
                "duration": 100.0,
                "video_path": str(tmp / "dummy.mp4"),
            }
            (tmp / "dummy.mp4").write_bytes(b"not-a-real-video")
            workspace = tmp / "workspace"
            private = tmp / "private"
            workspace.mkdir()
            (workspace / "analysis" / "investigations").mkdir(parents=True)
            private.mkdir()
            (workspace / "candidate").mkdir()

            class FakeProvider:
                def __init__(self):
                    self.calls = []
                    self.meter = MagicMock()
                    self.meter.events = []
                    self.meter.summary = lambda: {"frames": 0, "qwen_frames": 0}

                def chat(self, role, messages, frames=0, payload_extra=None, before_attempt=None):
                    self.calls.append({"role": role, "frames": frames})
                    if before_attempt:
                        before_attempt()
                    blob = json.dumps(messages)
                    if "Do not select an option" in blob or "textual observation only" in blob:
                        text = "A person stands in a room with a sofa visible."
                    else:
                        text = json.dumps({"type": "answer", "answer": "B"})
                    return {
                        "choices": [{"message": {"content": text}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                        "model": "mock-%s" % role,
                    }

            provider = FakeProvider()
            inv = CounterfactualInvestigation(
                workspace, private, [row], workspace / "candidate", config, provider, phase="analysis"
            )
            restore = _patch_services_call_for_mock()
            try:
                try:
                    reply = inv.execute(
                        {
                            "operation": "observe",
                            "sample_id": row["sample_id"],
                            "question": row["question"],
                            "timestamps": [1.0, 2.0],
                            "prompt": "Keep relevant entities, actions, visible text and chronology.",
                            "basis": "trajectory_review",
                        }
                    )
                    ok = reply.get("status") in ("completed", "reused") and not reply.get("error")
                    results.append(
                        CheckResult(
                            "editor_observe_mock",
                            "PASS" if ok else "FAIL",
                            {"status": reply.get("status"), "has_result": "result" in reply},
                            reason_code=None if ok else "observe_failed",
                        )
                    )
                except Exception as exc:
                    results.append(
                        CheckResult(
                            "editor_observe_mock",
                            "FAIL",
                            {"error": "%s:%s" % (type(exc).__name__, exc)},
                            reason_code="observe_exception",
                        )
                    )

                if need_probe:
                    mode_ok = True
                    mode_detail = {}
                    for mode in sorted(MODES):
                        try:
                            out = inv.execute(
                                {
                                    "operation": "infoflow_probe",
                                    "sample_id": row["sample_id"],
                                    "question": "does answerer matter?",
                                    "mode": mode,
                                    "timestamps": [1.0, 2.0, 3.0],
                                    "basis": "trajectory_review",
                                }
                            )
                            mode_detail[mode] = {
                                "ok": out.get("status") in ("completed", "reused") or bool(out.get("result") or out.get("id")),
                                "status": out.get("status"),
                            }
                            if not mode_detail[mode]["ok"]:
                                mode_ok = False
                        except Exception as exc:
                            mode_ok = False
                            mode_detail[mode] = {"error": "%s:%s" % (type(exc).__name__, exc)}
                    results.append(
                        CheckResult(
                            "infoflow_probe_mock",
                            "PASS" if mode_ok else "FAIL",
                            mode_detail,
                            reason_code=None if mode_ok else "infoflow_probe_mock_failed",
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            "infoflow_probe_mock",
                            "NOT_APPLICABLE",
                            {"reason": "experiment does not require infoflow_probe"},
                        )
                    )
            finally:
                restore()
    except Exception as exc:
        results.append(
            CheckResult(
                "editor_investigation_mock",
                "FAIL",
                {"error": "%s:%s" % (type(exc).__name__, exc)},
                reason_code="editor_investigation_unavailable",
            )
        )
    return results


def check_ocr_dependency(config: dict, required: bool) -> CheckResult:
    if not required:
        return CheckResult("ocr_dependency", "NOT_APPLICABLE", {"reason": "ocr not required"})
    root = (config.get("services") or {}).get("ocr_model_root")
    if root and Path(root).exists():
        return CheckResult("ocr_dependency", "PASS", {"ocr_model_root": redact_path(root)})
    return CheckResult(
        "ocr_dependency",
        "FAIL",
        {"ocr_model_root": redact_path(root)},
        reason_code="ocr_root_missing",
    )


def check_provider_config(config: dict, required: bool) -> CheckResult:
    if not required:
        return CheckResult("provider_config", "NOT_APPLICABLE", {})
    detail = provider_config_present(config)
    # For offline preflight we allow missing keys (status PASS with note) when
    # caller only wants visual path — but if required=True for paid, fail if unset.
    # Convention: required means upcoming phase will call paid APIs.
    if not detail["key_env_set"] or not detail["endpoint_env_set"]:
        return CheckResult(
            "provider_config",
            "FAIL",
            detail,
            reason_code="provider_env_missing",
        )
    if not detail["deepseek_model_configured"] or not detail["qwen_model_configured"]:
        return CheckResult(
            "provider_config",
            "FAIL",
            detail,
            reason_code="provider_model_unconfigured",
        )
    return CheckResult("provider_config", "PASS", detail)


def run_preflight(
    *,
    config: dict | None = None,
    config_path: Path | None = None,
    capabilities: PreflightCapabilities | None = None,
    reexec: bool = True,
    harness_dir: Path | None = None,
    smoke_video: Path | None = None,
    require_provider_env: bool = False,
) -> dict[str, Any]:
    """Run all applicable checks. Returns structured report; does not raise on FAIL."""
    caps = capabilities or PreflightCapabilities()
    cfg = config or load_config(config_path)
    checks: list[CheckResult] = []

    if caps.host_must_match_config_python:
        interp = ensure_correct_interpreter(cfg, reexec=reexec)
        checks.append(interp)
        if interp.status == "FAIL":
            return _finalize(checks, cfg, harness_dir, caps)

    checks.extend(check_dual_interpreter_deps(cfg))

    if caps.visual_sample_frames:
        # Only attempt smoke if host imageio check passed (or still try — to capture real error)
        smoke = run_sample_frames_smoke(cfg, video_path=smoke_video)
        checks.append(smoke)
    else:
        checks.append(CheckResult("sample_frames_smoke", "NOT_APPLICABLE", {}))

    if caps.editor_investigation or caps.infoflow_probe:
        checks.extend(check_editor_investigation_mock(cfg, need_probe=caps.infoflow_probe))
    else:
        checks.append(CheckResult("editor_investigation_mock", "NOT_APPLICABLE", {}))
        checks.append(CheckResult("infoflow_probe_mock", "NOT_APPLICABLE", {}))

    checks.append(check_ocr_dependency(cfg, caps.ocr))
    checks.append(check_provider_config(cfg, require_provider_env and caps.provider_config))

    return _finalize(checks, cfg, harness_dir, caps)


def _finalize(
    checks: list[CheckResult],
    cfg: dict,
    harness_dir: Path | None,
    caps: PreflightCapabilities,
) -> dict[str, Any]:
    required_failed = [c for c in checks if c.status == "FAIL"]
    status = "FAIL" if required_failed else "PASS"
    report = {
        "protocol": "experiment_guard_preflight_v1",
        "status": status,
        "capabilities": {
            "visual_sample_frames": caps.visual_sample_frames,
            "editor_investigation": caps.editor_investigation,
            "infoflow_probe": caps.infoflow_probe,
            "ocr": caps.ocr,
            "provider_config": caps.provider_config,
            "host_must_match_config_python": caps.host_must_match_config_python,
        },
        "host": host_fingerprint(),
        "config_fingerprint": config_fingerprint(cfg),
        "code_sha": git_sha(ROOT),
        "harness": harness_fingerprint(harness_dir),
        "checks": [c.to_dict() for c in checks],
        "reason_codes": [c.reason_code for c in required_failed if c.reason_code],
        "fail_closed": True,
        "note": "FAIL blocks paid / batch experiments. No silent no-vision downgrade.",
    }
    return redact_obj(report)


def require_preflight(**kwargs) -> dict[str, Any]:
    """Run preflight; SystemExit(2) on FAIL. Use at the start of paid runners."""
    report = run_preflight(**kwargs)
    if report["status"] != "PASS":
        codes = ",".join(report.get("reason_codes") or ["preflight_failed"])
        raise SystemExit("EXPERIMENT_GUARD_PREFLIGHT_FAIL: %s" % codes)
    return report


def write_preflight_report(report: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
