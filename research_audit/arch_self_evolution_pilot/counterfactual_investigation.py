"""Treatment-only Investigation subclass adding infoflow_probe (core Video-RSI untouched)."""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from solver_full_workspace.engine.investigation import Investigation
from solver_full_workspace.engine.services import ServiceError, Services
from solver_full_workspace.engine.common import public_item
from solver_full_workspace.answers import parse_decision_details


MODES = {"answerer_swap", "vision_vs_text", "observation_regen"}


def _letter(text: str, options: dict) -> tuple[str | None, str]:
    try:
        decision, mode = parse_decision_details(text, options)
        if decision.get("type") == "answer":
            return decision["answer"], mode
    except Exception:
        pass
    return None, "unparsed"


def _vqa_prompt(item: dict, caption: str | None) -> str:
    options = item["options"]
    letters = ",".join(sorted(options.keys()))
    parts = [
        'Reply with ONLY JSON {"type":"answer","answer":"<LETTER>"} where LETTER is one of %s.' % letters,
        "Question: " + item["question"],
        "Options:",
    ]
    for k in sorted(options):
        parts.append("%s. %s" % (k, options[k]))
    if caption is not None:
        parts.extend(["", "Text observation:", caption])
    return "\n".join(parts)


class CounterfactualInvestigation(Investigation):
    """Adds operation infoflow_probe; all other behavior inherits Investigation."""

    def execute(self, request):
        if isinstance(request, dict) and request.get("operation") == "infoflow_probe":
            return self._infoflow_probe(request)
        return super().execute(request)

    def _infoflow_probe(self, request):
        with self.lock:
            if self.closed:
                raise ServiceError("investigation session closed")
            if (self.private / "analysis_submission.json").is_file() and self.phase == "analysis":
                raise ValueError("diagnosis already submitted; finish this turn")
            mode = request.get("mode")
            if mode not in MODES:
                raise ValueError("mode must be one of %s" % sorted(MODES))
            if request.get("sample_id") not in self.rows:
                raise ValueError("sample_id is not in this round's training allowlist")
            if not isinstance(request.get("question"), str) or not request["question"].strip():
                raise ValueError("state the concrete uncertainty in question")
            timestamps = request.get("timestamps")
            if not isinstance(timestamps, list) or not timestamps:
                raise ValueError("timestamps required for infoflow_probe")
            timestamps = [float(t) for t in timestamps]
            records = self.records()
            if len(records) >= self.limits()["max_requests"]:
                raise ServiceError("round investigation request budget exhausted")
            ident = "request_%04d" % (len(records) + 1)
            directory = self.private / ident
            directory.mkdir()
            row = self.rows[request["sample_id"]]
            cfg = copy.deepcopy(self.config)
            cfg["solver"]["max_frames"] = min(
                self.config["solver"]["max_frames"],
                max(0, self.limits()["max_frames"] - self.usage()["frames"]),
            )
            service = Services(public_item(row), row, cfg, directory / "media", self.provider, self.ocr)
            record = {
                "id": ident,
                "phase": self.phase,
                "request": request,
                "status": "running",
                "label": "training_infoflow_probe_not_gate",
                "started_at": time.time(),
            }
            from solver_full_workspace.engine.common import write_json

            write_json(self.private / (ident + ".json"), record)
            try:
                frames = service.call("sample_frames", {"timestamps": timestamps})
                frame_ids = [f["id"] for f in frames]
                branches = {}
                obs_prompt = request.get(
                    "prompt",
                    "Describe entities, actions, visible text and chronology relevant to distinguishing the options. Do not choose an answer.",
                )

                def observe_text():
                    args = {
                        "frames": frame_ids,
                        "prompt": (
                            "Produce a textual observation only. Do not select an option.\n"
                            + json.dumps({"question": row["question"], "options": row["options"]}, ensure_ascii=False)
                            + "\n"
                            + obs_prompt
                        ),
                    }
                    return service.call("qwen", args).get("text", "")

                def answer_text(caption: str, role: str):
                    # role deepseek via provider.chat messages; qwen text-only via qwen with... need text-only
                    # Services qwen always needs frames. Use provider.chat directly for text-only.
                    prompt = _vqa_prompt(row, caption)
                    if role == "deepseek":
                        resp = self.provider.chat("deepseek", [{"role": "user", "content": prompt}], frames=0)
                        text = resp["choices"][0]["message"].get("content", "")
                        if not isinstance(text, str):
                            text = json.dumps(text, ensure_ascii=False)
                        return text
                    # qwen text-only: still go through provider with text content only
                    resp = self.provider.chat("qwen", [{"role": "user", "content": prompt}], frames=0)
                    text = resp["choices"][0]["message"].get("content", "")
                    if not isinstance(text, str):
                        text = json.dumps(text, ensure_ascii=False)
                    return text

                def answer_vision():
                    prompt = _vqa_prompt(row, None)
                    args = {"frames": frame_ids, "prompt": prompt}
                    return service.call("qwen", args).get("text", "")

                if mode == "answerer_swap":
                    cap = observe_text()
                    t_ds = answer_text(cap, "deepseek")
                    t_qw = answer_text(cap, "qwen")
                    a_ds, m_ds = _letter(t_ds, row["options"])
                    a_qw, m_qw = _letter(t_qw, row["options"])
                    branches = {
                        "shared_caption_chars": len(cap or ""),
                        "deepseek_answer": a_ds,
                        "qwen_text_answer": a_qw,
                        "answers_differ": a_ds != a_qw,
                        "parse": {"deepseek": m_ds, "qwen_text": m_qw},
                    }
                elif mode == "vision_vs_text":
                    cap = observe_text()
                    t_text = answer_text(cap, "deepseek")
                    t_vis = answer_vision()
                    a_text, m_text = _letter(t_text, row["options"])
                    a_vis, m_vis = _letter(t_vis, row["options"])
                    branches = {
                        "caption_chars": len(cap or ""),
                        "text_pipeline_answer": a_text,
                        "vision_direct_answer": a_vis,
                        "answers_differ": a_text != a_vis,
                        "parse": {"text_pipeline": m_text, "vision_direct": m_vis},
                    }
                else:  # observation_regen
                    cap1 = observe_text()
                    cap2 = observe_text()
                    t1 = answer_text(cap1, "deepseek")
                    t2 = answer_text(cap2, "deepseek")
                    a1, m1 = _letter(t1, row["options"])
                    a2, m2 = _letter(t2, row["options"])
                    branches = {
                        "caption_sha_pair": [
                            __import__("hashlib").sha256((cap1 or "").encode()).hexdigest()[:16],
                            __import__("hashlib").sha256((cap2 or "").encode()).hexdigest()[:16],
                        ],
                        "captions_identical": (cap1 or "") == (cap2 or ""),
                        "answer_obs1": a1,
                        "answer_obs2": a2,
                        "answers_differ": a1 != a2,
                        "parse": {"obs1": m1, "obs2": m2},
                    }

                record["result"] = {
                    "mode": mode,
                    "n_frames": len(frames),
                    "timestamps": timestamps,
                    "branches": branches,
                    "note": "Training probe only; not Gate. Editor decides whether/how to use.",
                }
                record["status"] = "completed"
            except Exception as exc:
                record.update(
                    status="error",
                    error_type=type(exc).__name__,
                    error="infoflow_probe failed; inspect service_trace",
                )
            finally:
                record.update(
                    usage=service.meter.summary(),
                    meter_events=service.meter.events,
                    service_trace=service.trace,
                    finished_at=time.time(),
                )
                write_json(self.private / (ident + ".json"), record)
                relative = "analysis/investigations/" + ident + ".json"
                write_json(self.workspace / relative, record)
                write_json(
                    self.workspace / "analysis/investigations/index.json",
                    {
                        "limits": self.limits(),
                        "usage": self.usage(),
                        "records": [
                            {
                                "id": r["id"],
                                "status": r["status"],
                                "sample_id": r["request"]["sample_id"],
                                "path": "analysis/investigations/" + r["id"] + ".json",
                            }
                            for r in self.records()
                        ],
                    },
                )
            return self.reply(record)
