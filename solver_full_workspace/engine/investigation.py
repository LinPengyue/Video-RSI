"""Question-driven training investigation."""
import copy
import json
import math
import threading
import time
from pathlib import Path

from .common import public_item, read_json, write_json
from .runner import copy_candidate, run_item
from .services import Meter, Services, ServiceError


class Investigation:
    def __init__(self, workspace, private, rows, parent, config, provider, ocr=None,
                 services_factory=None, phase="analysis"):
        self.workspace, self.private = Path(workspace).resolve(), Path(private).resolve()
        self.rows = {row["sample_id"]: row for row in rows}
        self.parent, self.config, self.provider = Path(parent).resolve(), config, provider
        self.ocr, self.services_factory, self.phase = ocr, services_factory, phase
        self.private.mkdir(parents=True, exist_ok=True)
        self.lock, self.closed = threading.Lock(), False
        state = self.private / "inquiry_control.json"
        self.control = read_json(state) if state.is_file() else {"duplicate_streak": 0, "pause_requested": False}

    @property
    def pause_requested(self):
        return self.control.get("pause_requested", False)

    def save_control(self):
        write_json(self.private / "inquiry_control.json", self.control)

    def request_key(self, request):
        """Plain values only: compare actual query parameters, never hashes."""
        operation = request["operation"]
        row = self.rows[request["sample_id"]]
        key = {"sample_id": request["sample_id"], "operation": operation,
               "question": " ".join(request["question"].split())}
        if "timestamps" in request:
            key["timestamps"] = [float(t) for t in request["timestamps"]]
        else:
            key.update(start=float(request.get("start", 0)), end=float(request.get("end", row["duration"])))
            if operation != "transcript":
                key["count"] = request.get("count", 32 if operation == "observe" else 8)
        if operation == "observe":
            key["prompt"] = " ".join(request.get("prompt", "Keep relevant entities, actions, visible text and chronology.").split())
        return key

    def reply(self, record, reused=False):
        result = record.get("result", {})
        serialized = json.dumps(result, ensure_ascii=False)
        reply = {"id": record["id"], "status": "reused" if reused else record["status"],
                 "path": "analysis/investigations/" + record["id"] + ".json",
                 "new_observation": not reused and record["status"] == "completed",
                 "usage": Meter().summary() if reused else record.get("usage", {}),
                 "round_usage": self.usage(), "result_complete": len(serialized) <= 24000}
        if hasattr(self.provider, "budget_status"):
            reply["budget"] = dict(self.provider.budget_status(), frame_limit=self.limits()["max_frames"])
        if reply["result_complete"]:
            reply["result"] = result
        else:
            reply["result_preview"] = serialized[:24000]
            reply["notice"] = "Display preview only; read the saved record for the complete unmodified result."
        if record["status"] == "error":
            reply["error_type"] = record.get("error_type")
            reply["error"] = record.get("error")
        return reply

    def submit_analysis(self, request):
        if self.phase != "analysis":
            raise ValueError("finish_analysis is only available during analysis")
        if set(request) - {"operation", "status", "unreviewed_cases", "reason"}:
            raise ValueError("unknown analysis submission argument")
        status = request.get("status")
        unreviewed = request.get("unreviewed_cases", [])
        if status not in ("complete", "partial") or not isinstance(unreviewed, list):
            raise ValueError("declare status complete/partial and unreviewed_cases")
        if any(not isinstance(s, str) or s not in self.rows for s in unreviewed):
            raise ValueError("unreviewed_cases must refer to this training batch")
        if status == "complete" and unreviewed:
            raise ValueError("unreviewed cases require partial status; unresolved cases may be reviewed")
        report = self.workspace / "analysis/analysis.md"
        if not report.is_file() or not report.read_text().strip():
            raise ValueError("save analysis/analysis.md before declaring completion")
        record = {"status": status, "unreviewed_cases": unreviewed,
                  "reason": request.get("reason", ""), "reported_by": "same_core_diagnoser",
                  "report": "analysis/analysis.md", "time": time.time(),
                  "semantic_quality_verified_by_program": False}
        write_json(self.private / "analysis_submission.json", record)
        return dict(record, instruction="Diagnosis submitted. End this turn; do not edit Solver or run Gate.")

    def records(self):
        return [read_json(path) for path in sorted(self.private.glob("request_*.json"))]

    def usage(self):
        meter = Meter()
        for record in self.records():
            meter.events.extend(record.get("meter_events", []))
        return meter.summary()

    def limits(self):
        return {"max_requests": self.config.get("investigation", {}).get("max_requests", self.config["solver"]["max_service_calls"]),
                "max_frames": self.config.get("investigation", {}).get("max_frames", self.config["solver"]["max_frames"]),
                "shared_provider_attempts": self.config["editor"]["max_provider_calls"]}

    def close(self):
        with self.lock:
            self.closed = True

    def execute(self, request):
        with self.lock:
            if self.closed:
                raise ServiceError("investigation session closed")
            if not isinstance(request, dict):
                raise ValueError("expected investigation request object")
            operation = request.get("operation")
            if operation == "finish_analysis":
                return self.submit_analysis(request)
            if (self.private / "analysis_submission.json").is_file() and self.phase == "analysis":
                raise ValueError("diagnosis already submitted; finish this turn")
            if self.pause_requested:
                raise ServiceError("repeated unchanged investigations: paused; preserve notes and report")
            allowed = {"observe": {"start", "end", "count", "timestamps", "prompt"},
                       "ocr": {"start", "end", "count", "timestamps"},
                       "transcript": {"start", "end"},
                       "run_solver": {"source"}}
            if operation not in allowed or set(request) - (allowed[operation] | {"operation", "sample_id", "question", "repeat_reason", "basis"}):
                raise ValueError("unknown investigation operation or argument")
            if request.get("sample_id") not in self.rows:
                raise ValueError("sample_id is not in this round's training allowlist")
            if not isinstance(request.get("question"), str) or not request["question"].strip():
                raise ValueError("state the concrete uncertainty in question")
            if ((self.phase == "analysis" or self.config.get("investigation", {}).get("diagnosis_only"))
                    and operation == "run_solver" and request.get("source", "parent") != "parent"):
                raise ValueError("diagnosis-only run permits only the unchanged parent Solver")
            reason = request.get("repeat_reason", "")
            if not isinstance(reason, str):
                raise ValueError("repeat_reason must describe the intentional repeat")
            if request.get("basis", "unspecified") not in ("annotation_guided", "public_clues", "trajectory_review", "unspecified"):
                raise ValueError("unknown investigation basis")
            records = self.records()
            if any(record.get("status") == "running" for record in records):
                raise ServiceError("an interrupted investigation is unresolved; inspect its private record before resuming")


            if operation in ("observe", "ocr", "transcript") and not reason.strip():
                key = self.request_key(request)
                match = next((r for r in reversed(records)
                              if r["status"] == "completed" and r["request"]["operation"] == operation
                              and self.request_key(r["request"]) == key), None)
                if match:
                    streak = self.control.get("duplicate_streak", 0) + 1 if self.control.get("last_reused") == match["id"] else 1
                    self.control.update(duplicate_streak=streak, last_reused=match["id"], pause_requested=streak >= 3)
                    self.save_control()
                    event = {"time": time.time(), "request": request, "reused_record": match["id"],
                             "new_observation": False, "duplicate_streak": streak}
                    with (self.private / "reuse_events.jsonl").open("a") as stream:
                        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                    reply = self.reply(match, reused=True)
                    reply.update(duplicate_streak=streak, pause_requested=self.pause_requested,
                                 notice="No new evidence: this exact query already succeeded. Update notes, change the test, or leave the conflict unresolved and move on. For an intentional stochastic repeat, supply repeat_reason. Three consecutive ignored duplicate notices pause this run.")
                    return reply
            self.control.update(duplicate_streak=0, last_reused=None)
            self.save_control()
            if len(records) >= self.limits()["max_requests"]:
                raise ServiceError("round investigation request budget exhausted")
            ident = "request_%04d" % (len(records) + 1)
            directory = self.private / ident
            directory.mkdir()
            row = self.rows[request["sample_id"]]
            cfg = copy.deepcopy(self.config)
            cfg["solver"]["max_frames"] = min(self.config["solver"]["max_frames"],
                max(0, self.limits()["max_frames"] - self.usage()["frames"]))
            service = (self.services_factory(row, directory / "media", cfg, self.provider)
                       if self.services_factory else Services(public_item(row), row, cfg, directory / "media", self.provider, self.ocr))
            record = {"id": ident, "phase": self.phase, "request": request,
                      "status": "running", "label": "training_investigation_not_gate",
                      "annotation_context": "analyst_has_training_oracle",
                      "answer_injected_by_broker": False, "started_at": time.time()}

            write_json(self.private / (ident + ".json"), record)
            try:
                if operation == "run_solver":
                    source = request.get("source", "parent")
                    if source == "parent":
                        candidate = self.parent
                    elif source == "candidate":
                        candidate = self.workspace / "candidate"
                    else:
                        candidate = (self.workspace / source).resolve()
                        experiments = (self.workspace / "analysis/experiments").resolve()
                        if experiments not in candidate.parents:
                            raise ValueError("trial source must be parent, candidate, or analysis/experiments/<name>")
                    snapshot = directory / "candidate"
                    copy_candidate(candidate, snapshot)
                    record["trial_kind"] = "unassisted_parent" if source == "parent" else "analyst_authored_training_trial"
                    record["result"] = run_item(snapshot, row, service, cfg)
                elif operation == "transcript":
                    result = service.call("asr", {})
                    if "start" in request or "end" in request:
                        start, end = self.window(request, row)
                        result = dict(result, segments=[s for s in result["segments"]
                                                       if float(s["end"]) >= start and float(s["start"]) <= end],
                                      requested_window=[start, end])
                    record["result"] = result
                else:
                    if "timestamps" in request:
                        if set(request) & {"start", "end", "count"}:
                            raise ValueError("use timestamps OR start/end/count, not both")
                        sample = {"timestamps": request["timestamps"]}
                    else:
                        start, end = self.window(request, row)
                        sample = {"start": start, "end": end, "count": request.get("count", 32 if operation == "observe" else 8)}
                    frames = service.call("sample_frames", sample)
                    args = {"frames": [frame["id"] for frame in frames]}
                    if operation == "observe":


                        args["prompt"] = (
                            "Investigate the stated question using only the supplied timestamped frames. "
                            "Report visible details relevant to the question and the distinctions between the options, "
                            "using the exact supplied numeric second anchors. Options and the investigation hypothesis "
                            "are not observed facts. Describe what the frames support, including observations that "
                            "disagree with the hypothesis; keep interpretation and uncertainty explicit. "
                            "Say when details are unclear, unreadable or not captured by these samples. "
                            "Not seen in sampled frames does not mean absent from the video. "
                            "Do not invent unseen events or transitions, diagnose code, or select an answer. "
                            "Preserve useful detail; there is no fixed fact-count limit.\nQuestion and options: "
                            + json.dumps({k: public_item(row)[k] for k in ("question", "options")}, ensure_ascii=False)
                            + "\nInvestigation question: " + request["question"]
                            + "\nObservation instructions: " + request.get("prompt", "Keep relevant entities, actions, visible text and chronology.")
                        )
                    result = service.call("qwen" if operation == "observe" else "ocr", args)
                    record["result"] = {"frames": frames, "observation": result}
                record["status"] = "completed"
            except Exception as exc:
                record.update(status="error", error_type=type(exc).__name__,
                              error="Investigation failed; inspect service_trace. Do not treat this as a task answer.")
            finally:
                record.update(usage=service.meter.summary(), meter_events=service.meter.events,
                              service_trace=service.trace, finished_at=time.time())
                write_json(self.private / (ident + ".json"), record)
                relative = "analysis/investigations/" + ident + ".json"
                write_json(self.workspace / relative, record)
                write_json(self.workspace / "analysis/investigations/index.json", {
                    "limits": self.limits(), "usage": self.usage(),
                    "records": [{"id": r["id"], "status": r["status"], "sample_id": r["request"]["sample_id"],
                                 "path": "analysis/investigations/" + r["id"] + ".json"} for r in self.records()]})


            return self.reply(record)

    @staticmethod
    def window(request, row):
        start, end = float(request.get("start", 0)), float(request.get("end", row["duration"]))
        if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= row["duration"]:
            raise ValueError("invalid time window; use seconds within video duration")
        return start, end
