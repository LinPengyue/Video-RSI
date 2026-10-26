#!/usr/bin/env python3
"""Mock smoke tests for CounterfactualInvestigation.infoflow_probe (0 paid API)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research_audit" / "arch_self_evolution_pilot"))

from counterfactual_investigation import CounterfactualInvestigation, MODES


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
        # caption-like vs answer
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


def make_inv(tmpdir: Path, provider, sample_id="lvbench_test"):
    row = {
        "sample_id": sample_id,
        "question": "What room?",
        "options": {"A": "Kitchen", "B": "Living room", "C": "Bathroom", "D": "Bedroom"},
        "duration": 100.0,
        "video_path": str(tmpdir / "dummy.mp4"),
    }
    (tmpdir / "dummy.mp4").write_bytes(b"not-a-real-video")
    workspace = tmpdir / "workspace"
    private = tmpdir / "private"
    workspace.mkdir()
    (workspace / "analysis" / "investigations").mkdir(parents=True)
    private.mkdir()
    cfg = {
        "solver": {"max_frames": 256, "max_service_calls": 64, "max_steps": 11, "timeout_seconds": 60},
        "editor": {"max_provider_calls": 50},
        "investigation": {"max_frames": 1024},
        "services": {
            "ffmpeg": "imageio-ffmpeg",
            "temperature": 0,
            "timeout_seconds": 30,
            "provider_retries": 0,
            "deepseek": {"request_model": "mock-ds", "max_tokens": 128},
            "qwen": {"request_model": "mock-qw", "max_tokens": 128},
            "ocr_model_root": "/tmp",
            "key_env": "API_KEY",
            "endpoint_env": "API_BASE",
        },
    }
    inv = CounterfactualInvestigation(
        workspace, private, [row], workspace / "candidate", cfg, provider, phase="analysis"
    )
    return inv, row


def test_modes_dispatch_and_illegal():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        provider = FakeProvider()
        inv, row = make_inv(tmp, provider)

        # Patch Services.sample_frames / call path: monkeypatch service.call inside execute
        # Easiest: stub Services methods via patching Investigation path used in _infoflow_probe
        import counterfactual_investigation as ci
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
                        path.write_bytes(b"\xff\xd8\xff\xd9")  # minimal jpeg-ish
                        self.frames[fid] = {"timestamp": float(ts), "path": path}
                        self.meter.events.append({"kind": "extraction", "frames": 1})
                        out.append({"id": fid, "timestamp": float(ts)})
                    return out
                if name == "qwen":
                    # vision or observe
                    text = (
                        "caption text"
                        if "observation only" in args.get("prompt", "") or "Do not select" in args.get("prompt", "")
                        else json.dumps({"type": "answer", "answer": "A"})
                    )
                    self.meter.events.append({"kind": "provider", "role": "qwen", "frames": len(args["frames"]), "status": "ok"})
                    return {"text": text}
                raise AssertionError(name)

            self.call = call

        services_mod.Services.__init__ = fake_init
        try:
            for mode in sorted(MODES):
                req = {
                    "operation": "infoflow_probe",
                    "sample_id": row["sample_id"],
                    "question": "does answerer matter?",
                    "mode": mode,
                    "timestamps": [1.0, 2.0, 3.0],
                    "basis": "trajectory_review",
                }
                reply = inv.execute(req)
                assert reply["status"] in ("completed", "reused") or reply.get("result") or reply.get("id")
                # records saved
                assert any(p.name.startswith("request_") for p in (tmp / "private").glob("request_*.json"))
            # illegal mode
            try:
                inv.execute({
                    "operation": "infoflow_probe",
                    "sample_id": row["sample_id"],
                    "question": "x",
                    "mode": "not_a_mode",
                    "timestamps": [1.0],
                })
                raise AssertionError("expected ValueError")
            except ValueError:
                pass
            # invalid sample
            try:
                inv.execute({
                    "operation": "infoflow_probe",
                    "sample_id": "nope",
                    "question": "x",
                    "mode": "answerer_swap",
                    "timestamps": [1.0],
                })
                raise AssertionError("expected ValueError")
            except ValueError:
                pass
            # missing timestamps
            try:
                inv.execute({
                    "operation": "infoflow_probe",
                    "sample_id": row["sample_id"],
                    "question": "x",
                    "mode": "vision_vs_text",
                })
                raise AssertionError("expected ValueError")
            except ValueError:
                pass
        finally:
            services_mod.Services.__init__ = real_init
    print("PASS test_modes_dispatch_and_illegal")


def test_stock_investigation_rejects_infoflow_probe():
    """Baseline Investigation must not accept infoflow_probe."""
    from solver_full_workspace.engine.investigation import Investigation

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        provider = FakeProvider()
        row = {
            "sample_id": "lvbench_test",
            "question": "q",
            "options": {"A": "a", "B": "b"},
            "duration": 10.0,
            "video_path": str(tmp / "v.mp4"),
        }
        (tmp / "v.mp4").write_bytes(b"x")
        ws = tmp / "ws"
        priv = tmp / "priv"
        ws.mkdir()
        (ws / "analysis" / "investigations").mkdir(parents=True)
        priv.mkdir()
        cfg = {
            "solver": {"max_frames": 64, "max_service_calls": 16, "max_steps": 5, "timeout_seconds": 30},
            "editor": {"max_provider_calls": 10},
            "investigation": {},
            "services": {"ffmpeg": "imageio-ffmpeg", "ocr_model_root": "/tmp",
                         "deepseek": {"request_model": "m", "max_tokens": 8},
                         "qwen": {"request_model": "m", "max_tokens": 8},
                         "temperature": 0, "timeout_seconds": 10, "provider_retries": 0,
                         "key_env": "API_KEY", "endpoint_env": "API_BASE"},
        }
        inv = Investigation(ws, priv, [row], ws / "cand", cfg, provider, phase="analysis")
        try:
            inv.execute({
                "operation": "infoflow_probe",
                "sample_id": "lvbench_test",
                "question": "x",
                "mode": "answerer_swap",
                "timestamps": [1.0],
            })
            raise AssertionError("stock Investigation should reject infoflow_probe")
        except ValueError as exc:
            assert "unknown investigation operation" in str(exc)
    print("PASS test_stock_investigation_rejects_infoflow_probe")


def main() -> int:
    test_modes_dispatch_and_illegal()
    test_stock_investigation_rejects_infoflow_probe()
    print("summary failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
