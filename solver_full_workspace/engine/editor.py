import http.server
import copy
import json
import os
import secrets
import subprocess
import threading
import time
from pathlib import Path

from .common import read_json, write_json
from .runner import stop_process
from .services import Meter, PinnedProvider, ServiceError
from .investigation import Investigation
from .analysis_progress import AnalysisIncomplete, completion, progress_snapshot, resume_prompt
from .gate_feedback import POLICY, aggregate_feedback


def route_tool_choice(payload, artifact=None):
    """Keep DSH's text-only checkpoint request out of tool-action recovery."""
    messages = payload.get("messages", [])
    last = messages[-1] if messages else {}
    content = last.get("content", "")
    if isinstance(content, list):
        content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    compacting = (last.get("role") == "user" and isinstance(content, str)
                  and content.startswith("You are now acting as a compaction engine for this AI coding assistant."))
    if compacting:
        return dict(payload, tool_choice="none"), "compaction"


    return payload, "agent"


class InvestigationProvider:
    """Share the editor's frozen provider and attempt budget, retain per-test costs."""
    def __init__(self, proxy):
        self.proxy, self.meter = proxy, Meter()

    def budget_status(self):
        return {"provider_used": self.proxy.used,
                "provider_limit": self.proxy.config["editor"]["max_provider_calls"]}

    def chat(self, role, messages, frames=0, payload_extra=None, before_attempt=None):
        proxy = self.proxy
        with proxy.lock:
            position = len(proxy.meter.events)
            def sync():
                nonlocal position
                events = proxy.meter.events[position:]
                for event in events:
                    event["purpose"] = "training_investigation"
                self.meter.events.extend(events)
                position = len(proxy.meter.events)
            def count():
                sync()
                if before_attempt:
                    before_attempt()
                proxy.count_attempt()
            try:
                return proxy.provider.chat(role, messages, frames=frames,
                                           payload_extra=payload_extra, before_attempt=count)
            finally:
                sync()


class EditorProxy:
    """DSH can use tools, but cannot change model/provider or see real API keys."""
    def __init__(self, config, used=0, provider=None):
        self.config, self.used = config, used
        self.token, self.meter = secrets.token_urlsafe(32), Meter()
        self.provider = provider or PinnedProvider(config["services"], self.meter)
        self.provider.meter = self.meter
        editor_services = copy.deepcopy(config["services"])
        editor_services["deepseek"]["max_tokens"] = config["editor"].get(
            "max_output_tokens", editor_services["deepseek"]["max_tokens"])

        self.editor_provider = provider or PinnedProvider(editor_services, self.meter)
        self.editor_provider.meter = self.meter
        self.lock = threading.Lock()
        self.investigation = None
        self.investigation_token = secrets.token_urlsafe(32)
        self.protocol_trace = None
        self.tool_calls_returned = 0
        self.require_action_until = None
        self.on_attempt = None

    def count_attempt(self):
        if self.investigation and self.investigation.pause_requested:
            raise ServiceError("analysis paused after repeated unchanged investigation requests; records preserved")
        if self.used >= self.config["editor"]["max_provider_calls"]:
            raise ServiceError("shared editor/investigation provider call limit exhausted")
        self.used += 1
        if self.on_attempt:
            self.on_attempt(self.used)

    def __enter__(self):
        proxy = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                investigation = self.path == "/v1/investigate"
                token = proxy.investigation_token if investigation else proxy.token
                if self.headers.get("Authorization") != "Bearer " + token or self.path not in ("/chat/completions", "/v1/chat/completions", "/v1/investigate"):
                    self.send_error(403)
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 32 * 1024 * 1024:
                        raise ValueError("invalid payload size")
                    payload = json.loads(self.rfile.read(size))
                    if investigation:
                        if proxy.investigation is None:
                            raise ServiceError("training investigation is unavailable")
                        value = proxy.investigation.execute(payload)
                        body = json.dumps(value, ensure_ascii=False).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return
                    payload, request_purpose = route_tool_choice(payload, proxy.require_action_until)
                    with proxy.lock:
                        value = proxy.editor_provider.chat("deepseek", payload["messages"], payload_extra=payload, before_attempt=proxy.count_attempt)
                        proxy.tool_calls_returned += sum(len(choice.get("message", {}).get("tool_calls") or []) for choice in value.get("choices", []))
                        if proxy.protocol_trace:


                            record = {"provider_call": proxy.used, "time": time.time(),
                                      "request_tool_choice": payload.get("tool_choice", "auto"),
                                      "request_purpose": request_purpose,
                                      "request_tool_names": [t.get("function", {}).get("name") for t in payload.get("tools", [])],
                                      "message_count": len(payload["messages"]),
                                      "choices": value.get("choices"), "usage": value.get("usage")}
                            serialized = json.dumps(record, ensure_ascii=False)
                            for secret in (proxy.token, proxy.investigation_token, getattr(proxy.provider, "key", None)):
                                if secret:
                                    serialized = serialized.replace(secret, "[REDACTED]")
                            with proxy.protocol_trace.open("a") as stream:
                                stream.write(serialized + "\n")
                    if payload.get("stream"):
                        choice = value["choices"][0]
                        message = choice["message"]
                        delta = {"role": "assistant", "content": message.get("content")}
                        if message.get("tool_calls"):
                            delta["tool_calls"] = [dict(call, index=i) for i, call in enumerate(message["tool_calls"])]
                        chunks = [dict(id=value.get("id", "full-editor"), object="chat.completion.chunk", model=value.get("model"), choices=[{"index": 0, "delta": delta, "finish_reason": None}]),
                                  dict(id=value.get("id", "full-editor"), object="chat.completion.chunk", model=value.get("model"), choices=[{"index": 0, "delta": {}, "finish_reason": choice.get("finish_reason", "stop")}])]
                        usage = value.get("usage", {})
                        if all(isinstance(usage.get(key), int) for key in ("prompt_tokens", "completion_tokens")):
                            chunks[-1]["usage"] = usage
                        body = ("".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
                        kind = "text/event-stream"
                    else:
                        body, kind = json.dumps(value).encode(), "application/json"
                    self.send_response(200)
                    self.send_header("Content-Type", kind)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:
                    detail = str(exc) if investigation and isinstance(exc, (ValueError, ServiceError)) else "editor proxy request failed"
                    body = json.dumps({"error": {"message": type(exc).__name__ + ": " + detail, "type": "full_candidate_error"}}).encode()
                    self.send_response(400)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:%d/v1" % self.server.server_port
        return self

    def __exit__(self, *args):
        if self.investigation:
            self.investigation.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def make_profile(home, config, plugin):
    profile = home / "profiles/headless"
    profile.mkdir(parents=True, exist_ok=True)
    write_json(profile / "package.json", {"name": "dsh-profile-full-candidate", "private": True, "dependencies": {}, "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-headless"]}}})
    model = dict(config["services"]["deepseek"])
    model["max_tokens"] = config["editor"].get("max_output_tokens", model["max_tokens"])


    stream_idle_ms = (config["services"]["timeout_seconds"] *
                      (config["services"]["provider_retries"] + 1) + 60) * 1000
    rows = [
        {"id": "agent-default-model", "config": {"provider": "deepseek-official", "model": model["request_model"]}},
        {"id": "llm-deepseek", "config": {"apiKeyEnv": "API_KEY", "thinking": "disabled", "reasoningEffort": "off", "maxTokens": model["max_tokens"], "streamIdleTimeoutMs": stream_idle_ms, "models": [{"id": model["request_model"], "name": model["request_model"], "contextWindow": 128000, "maxTokens": model["max_tokens"]}]}},
        {"id": "approval", "config": {"policy": "never"}},
        {"id": "permission", "config": {"defaultPreset": "full-candidate", "presets": {"full-candidate": {"sandbox": "danger-full-access", "approval": "never", "name": "full-candidate", "description": "Workspace OS fence is enforced by the outer launcher."}}}},
        {"id": "headless-runner", "disabled": True},
        {"insert": [{"id": "full-candidate-runner", "name": str(plugin), "config": {"task": "full candidate task"}}]},
    ]
    disabled = "llm-retry session-title-llm attachment-local agent-instructions goal goal-round-driver command-goal plan-mode tool-goal tool-todo subagent subagent-spawn-in-process subagent-fork-in-process tool-subagent-control tool-subagent-list-agents tool-subagent-report workflow-worker-thread tool-jobs tool-fs-search tool-str-replace-editor tool-pwsh tool-skill skill-filesystem tool-subagent tool-subagent-fork tool-workflow tool-ralph tool-web".split()
    rows.extend({"id": name, "disabled": True} for name in disabled)

    write_json(profile / "cordis.patch.yml", rows)
    write_json(home / "cordis.patch.yml", [])
    write_json(home / "settings.yaml", {"agent-default-model": {"provider": "deepseek-official", "model": model["request_model"], "reasoningEffort": "off"}})


class DeepSeekEditor:
    def __init__(self, config, provider=None):
        self.config, self.provider = config, provider
        self.investigation_context = None

    def configure_investigation(self, rows, parent, ocr=None):

        self.investigation_context = {"rows": rows, "parent": parent, "ocr": ocr}

    def run(self, workspace, private, phase):
        """A stopped model turn is not a completed analysis/edit deliverable."""
        if phase not in ("analysis", "plan", "edit"):
            raise ValueError("unknown editor phase")
        workspace, private = Path(workspace).resolve(), Path(private).resolve()
        private.mkdir(parents=True, exist_ok=True)
        state_path = private / "session.json"
        artifact = workspace / "analysis" / {"analysis": "analysis.md", "plan": "edit_plan.md", "edit": "edit_summary.md"}[phase]

        def ready():
            if phase == "analysis":
                record = completion(workspace, private)
                return bool(record and record.get("status") == "complete")
            return artifact.is_file() and bool(artifact.read_text().strip())

        state = read_json(state_path) if state_path.exists() else {}
        if state.get("pause_reason"):
            raise AnalysisIncomplete("diagnosis is paused; explicit recovery required")
        if state.get("in_flight"):
            raise RuntimeError("previous editor call interrupted; inspect persisted session before resuming")
        if phase in state.get("completed_phases", []):
            if ready():
                return state

            write_json(private / (phase + "_incomplete_completion.json"), state)
            state["session_started"] = True
            state["completed_phases"].remove(phase)
            state.setdefault("pending_artifacts", []).append(phase)
            write_json(state_path, state)
        idle_turns = 0
        while idle_turns < 3:
            before = progress_snapshot(workspace, private)
            state = self._run_turn(workspace, private, phase)
            if phase == "analysis":
                submission = completion(workspace, private)
                if submission and submission.get("status") == "partial":
                    state["analysis_status"] = "partial"
                    write_json(state_path, state)
                    raise AnalysisIncomplete("partial diagnosis saved; do not enter editing or Gate")
            if ready():
                if phase not in state["completed_phases"]:
                    state["completed_phases"].append(phase)
                state["pending_artifacts"] = [p for p in state.get("pending_artifacts", []) if p != phase]
                write_json(state_path, state)
                return state
            if phase not in state.setdefault("pending_artifacts", []):
                state["pending_artifacts"].append(phase)


            after = progress_snapshot(workspace, private)
            idle_turns = 0 if after != before else idle_turns + 1
            state["consecutive_idle_turns"] = idle_turns
            write_json(state_path, state)
        raise RuntimeError("three continuations without new observations or saved analysis; same session preserved")

    def _run_turn(self, workspace, private, phase):
        workspace, private = Path(workspace).resolve(), Path(private).resolve()
        private.mkdir(parents=True, exist_ok=True)
        home, state_path = private / "dsh_home", private / "session.json"
        if not self.config['execution']['linux_isolation']:
            raise ValueError('Editor requires filesystem isolation; offline-review is startup-only')
        if (workspace / 'development_feedback').exists():
            raise ValueError('Gate item feedback found; use a new clean workspace/session')
        feedback_path = workspace / 'lineage_feedback.json'
        if feedback_path.is_file():
            feedback = read_json(feedback_path)
            if feedback != aggregate_feedback(feedback):
                raise ValueError('Only approved scalar Gate metrics may enter the Editor workspace')
        if state_path.exists() and read_json(state_path).get('gate_feedback_policy') != POLICY:
            raise ValueError('Session feedback policy is incompatible; initialize a new session')
        harness = Path(self.config["editor"]["harness_root"])
        plugin = harness / "packages/bundle/headless/src/full-candidate-runner.ts"
        if not plugin.is_file():
            raise RuntimeError("install the additive full-candidate headless plugin first")
        if not state_path.exists():
            make_profile(home, self.config, plugin)
            write_json(state_path, {"session_id": "full-candidate-" + secrets.token_hex(16), "used_calls": 0, "spent_seconds": 0, "completed_phases": [], "gate_feedback_policy": POLICY})
        elif "max_output_tokens" in self.config["editor"]:

            make_profile(home, self.config, plugin)
        state = read_json(state_path)
        if state.get("in_flight"):
            raise RuntimeError("previous editor call interrupted; inspect persisted session before resuming")
        remaining_seconds = self.config["editor"]["timeout_seconds"] - state.get("spent_seconds", 0)
        if remaining_seconds <= 0:
            raise RuntimeError("editor active-time budget exhausted")
        if state["used_calls"] >= self.config["editor"]["max_provider_calls"]:
            raise RuntimeError("editor provider budget exhausted")
        resumed = state.get("session_started", False) or bool(state["completed_phases"])
        investigation_instruction = (
            "Read INVESTIGATION.md. Investigate concrete uncertainties using actual training media "
            "and preserve the observations, alternative explanations, and unresolved questions. "
            "The broker returns complete ordinary observations directly; consult the saved record for "
            "long output. Reused observations are not new evidence. Do not inject gold answers into Qwen. "
            "During analysis do not modify Solver code or run altered copies. During the separately "
            "authorized edit phase, temporary full copies and fresh Solver trials may be used. "
            "Annotation-informed tests are not autonomous localization or Gate. "
            "No fixed Probe, per-case investigation quota, prescribed module, or mandatory new tool. "
        ) if self.investigation_context else "Media investigation is unavailable; do not claim to have used it. "
        investigation_instruction += "Use paths and version names, not content hashes or checksums. "
        improvement_objective = (
            "The primary objective is higher single-choice answer accuracy. Under the existing paired Gate, "
            "acceptance requires either (1) more correct answers with mean Qwen input frames at most "
            "110% of the parent's, or (2) the same correct count or exactly one fewer correct answer "
            "with mean Qwen input frames at most 80% of the parent's. The 10% and 20% boundaries are inclusive. "
            "Losing two or more correct answers is never accepted for frame savings. This is an absolute "
            "one-question tolerance on the fixed Gate cohort, not a percentage-point tolerance. "
            "A zero-frame parent permits only accuracy gain at zero frames, not a claimed 20% saving. "
            "The primary efficiency metric counts frames in successful Qwen provider responses only. "
            "Failed and unfinished Qwen attempts, local OCR processing and extraction are recorded separately. "
            "A successful observation still counts even when it does not find the target or the final answer is wrong. "
            "Use cost_usage and frame_metric=qwen_returned_frames_v2 for paired comparisons. "
            "Raw attempts remain in usage and meter_events and still enforce the execution budget. "
            "Reducing OCR work alone is not a Qwen frame-cost improvement. Do not substitute fewer tool calls; "
            "retain actual usage accounting and existing execution budgets and engineering checks. "
            "Training investigations suggest changes; only the external complete paired Gate establishes acceptance. "
        )
        if phase == "analysis":
            directive = self.config["editor"].get("analysis_directive")
            if not directive:
                directive = Path(__file__).parents[1].joinpath("DIAGNOSIS.md").read_text()
            task = directive + "\n" + improvement_objective + "\n" + investigation_instruction
        else:
            task = (
                improvement_objective +
                "Continue from your own analysis and raw investigation records in this SAME persisted conversation. " + investigation_instruction +
                "The previous PLAN phase in this same session saved analysis/edit_plan.md. Implement that plan; "
                "it remains available as reference, with no mandatory reread or read-tool checkpoint. "
                "Use the prior implementation, training evidence and aggregate failure feedback as needed. "
                "If new evidence changes the plan, append the reason and revised direction without erasing "
                "the original plan. "
                "Now implement a reusable improvement justified by the real trajectories and your investigation. "
                "Choose changes that address the shared mechanism: how existing capabilities are used, how tools acquire "
                "and return information, missing executable operations, or memory/reasoning/answer handling. "
                "Do not reduce every capability gap to a prompt reminder. The existing paired Gate, not the number "
                "of new rules or tools, judges the result. "
                "You may add/delete/refactor ANY candidate files, including main loop, message builder, memory, answer handling, tools, tests, prompts and executable skills/workflows. "
                "The only fixed ABI is candidate.json entrypoint file:function receiving (item,services,budget), returning a JSON result with status and a single actual option answer. "
                "Read SERVICES.md for frozen service interfaces. You can evolve Qwen prompts/sampling/output schemas, process its full JSON, and pass arbitrary structures to memory and DeepSeek. "
                "Fix local failure mechanisms conditionally; change global behavior when the evidence supports a general defect. Conditions must be executed in code using public question/options and available observations, not dataset type labels or a sentence saying 'use when relevant'. "
                "The initial seed provides candidate/skill_policy.py for explicit global entries or conditional entries with when(context) returning bool. Inspect the current candidate: that interface may have evolved and its skill set is not necessarily empty. In the seed, only selected instructions enter the Solver prompt; unregistered Markdown is not automatically loaded. Read SERVICES.md for the seed interface and trace fields. "
                "This registry selects instructions; a real workflow or evidence operator also requires executable code connected to the candidate loop/tools/memory. You can replace the registry or the entire implementation. Exercise both matching and unrelated cases in offline tests for any conditional mechanism you add. "
                "No requirement to invent a tool, a graph, or any particular mechanism. Ordinary question paths should not be needlessly changed. "
                "Keep training answers, annotated intervals, case-specific answer tables and investigation artifacts OUT of the final candidate. "
                "Implement reusable behavior, not a lookup of training IDs or oracle hints. Gate starts fresh without analysis or annotations. "
                "Run your offline tests with the available Python interpreter. Do not read held-out labels or labels outside explicitly authorized workspace feedback; do not modify external scorer/model identities. "
                "Save a small runnable check at analysis/tool_check.py. The host will run it against a fresh "
                "read-only candidate copy before Gate, without API credentials, network, video or labels. "
                "Candidate modules are on sys.path; CANDIDATE_DIR points to the snapshot. Use synthetic "
                "observations and stub services to exercise actual changed tool/loop functions and assert "
                "their returned observations reach the intended consumer. Include the affected route and "
                "one relevant unaffected case; for prompt-only changes, exercise prompt assembly and an "
                "ordinary tool-to-memory path. Keep fixtures in this check, not in candidate code. "
                "Do not merely import modules or print PASS. A failed check stops before Gate. "
                "Save the change explanation and actual tests in analysis/edit_summary.md, referring to "
                "edit_plan.md and explaining any departures from it. Planned tests are not completed tests. Then finish."
            )
        if phase == "plan":
            task = (
                improvement_objective + investigation_instruction +
                "PLAN PHASE: Save the modification plan before any candidate edit. "
                "Continue THIS persisted conversation; do not restart diagnosis. Candidate files are read-only in this phase. Do not change "
                "candidate code, implement in temporary copies, run modified Solvers or run Gate. "
                "Use this round's saved analysis and training cases as a map, verify relevant trajectories and "
                "investigation records as needed, and retain uncertainty. Save a clear Chinese "
                "analysis/feedback_review.md and analysis/edit_plan.md. The plan should explain the "
                "problem, supporting cases, proposed reusable mechanism and files, applicable conditions, "
                "preserved behaviors, and planned checks. Do not invent completed tests. Do not repeat "
                "the entire diagnosis or force a new tool. Once both notes are saved, finish immediately "
                "so the driver can advance to editing (or its configured optional plan pause). "
                "Do not implement in this turn. No edit_summary is required in this phase."
            )
        if phase in state.get("pending_artifacts", []):
            task = resume_prompt(task, phase, workspace, private, state["used_calls"],
                                 self.config["editor"]["max_provider_calls"])
        task += (
            '\nGATE BOUNDARY: The Gate cohort is fixed across rounds. You receive only scalar '
            'aggregate Gate metrics in lineage_feedback.json, never Gate questions, options, '
            'answers, item identities, trajectories, observations or annotated intervals. '
            'Base diagnosis and changes on TRAINING cases, their answers and observations, '
            'the prior code/plan and aggregate outcome. Do not reconstruct or request Gate '
            'cases, import reports/sessions containing Gate item data, or claim an aggregate establishes '
            'a specific failed case or causal mechanism. '
        )
        attempt = state.setdefault("phase_turns", {}).get(phase, 0)

        while (private / (phase + ("" if attempt == 0 else "_turn_%03d" % (attempt + 1)) + "_meter.json")).exists():
            attempt += 1
        stem = phase + ("" if attempt == 0 else "_turn_%03d" % (attempt + 1))
        state["phase_turns"][phase] = attempt + 1
        receipt = home / (stem + "_receipt.json")
        state["in_flight"] = phase
        write_json(state_path, state)
        started = time.monotonic()
        with EditorProxy(self.config, used=state["used_calls"], provider=self.provider) as proxy:
            proxy.protocol_trace = private / (stem + "_protocol.jsonl")
            def record_attempt(used):
                state["used_calls"] = used
                write_json(state_path, state)
            proxy.on_attempt = record_attempt
            if self.investigation_context or phase == "analysis":
                context = self.investigation_context or {"rows": [], "parent": workspace / "candidate"}
                proxy.investigation = Investigation(workspace, private / "investigations",
                    config=self.config, provider=InvestigationProvider(proxy), phase=phase,
                    **context)
            env = {"PATH": str(Path(self.config["editor"]["node_binary"]).parent) + ":" + str(Path(self.config["execution"]["python"]).parent) + ":/usr/bin:/bin", "LANG": "C.UTF-8",
                   "HOME": str(home), "TMPDIR": str(home / "tmp"), "DSH_HOME": str(home), "API_KEY": proxy.token,
                   "DEEPSEEK_BASE_URL": proxy.url, "DSH_PERMISSION_MODE": "danger-full-access", "DSH_WORKSPACE_READ_FENCE": "1", "DSH_TELEMETRY_DISABLED": "1",
                   "TSX_TSCONFIG_PATH": str(harness / "tsconfig.base.json"),
                   "FULL_CANDIDATE_SESSION_ID": state["session_id"], "FULL_CANDIDATE_RESUME": "1" if resumed else "0", "FULL_CANDIDATE_SESSION_RECEIPT": str(receipt), "FULL_CANDIDATE_TASK": task}
            if proxy.investigation:




                connection = home / "investigation_connection.json"
                write_json(connection, {"url": proxy.url + "/investigate",
                                        "capability": proxy.investigation_token,
                                        "timeout": max(self.config["solver"]["timeout_seconds"], self.config["services"]["timeout_seconds"]) + 60})
                connection.chmod(0o600)
                env["INVESTIGATION_CONNECTION_FILE"] = str(connection)
            (home / "tmp").mkdir(exist_ok=True)
            io_compat = str(Path(__file__).with_name("atomic_io_compat.mjs"))
            command = [self.config["editor"]["node_binary"], "--expose-internals", "--import", io_compat, "--import", str(harness / "node_modules/tsx/dist/loader.mjs"), str(harness / "apps/cli/src/bin.ts"), "--profile", "headless", task]
            spec = {"command": command, "env": env, "cwd": str(workspace), "isolation": self.config["execution"]["linux_isolation"],
                    "readable": [str(harness), io_compat, self.config["editor"]["node_binary"], str(workspace), "/usr/bin", "/bin", "/etc/ssl", "/etc/hosts", "/etc/resolv.conf", "/etc/nsswitch.conf"],
                    "writable": [str(home), str(workspace / "analysis")] + ([str(workspace / "candidate")] if phase == "edit" else [])}
            with (private / (stem + ".stdout.log")).open("w") as out, (private / (stem + ".stderr.log")).open("w") as err:
                process = subprocess.Popen([self.config["execution"]["python"], "-I", str(Path(__file__).with_name("editor_worker.py"))], stdin=subprocess.PIPE, stdout=out, stderr=err, text=True, env={"PATH": "/usr/bin:/bin"}, start_new_session=True)
                try:
                    process.communicate(json.dumps(spec) + "\n", timeout=remaining_seconds)
                except subprocess.TimeoutExpired:
                    stop_process(process)
                    process.wait()
                finally:
                    if proxy.investigation:
                        proxy.investigation.close()
                    state["used_calls"] = proxy.used
                    state["last_turn_tool_calls"] = proxy.tool_calls_returned
                    if proxy.investigation and proxy.investigation.pause_requested:
                        state["pause_reason"] = "repeated_unchanged_investigation"
                    state["spent_seconds"] = state.get("spent_seconds", 0) + time.monotonic() - started
                    write_json(private / (stem + "_meter.json"), {"events": proxy.meter.events, "usage": proxy.meter.summary()})
                    write_json(state_path, state)
        if process.returncode != 0 or not receipt.is_file():
            raise RuntimeError("DeepSeek editor failed; session/logs preserved, parent unchanged")
        record = read_json(receipt)
        if record["session_id"] != state["session_id"] or record["resumed"] != resumed:
            raise RuntimeError("session continuation receipt mismatch")
        state["session_started"] = True
        state.pop("in_flight", None)
        write_json(state_path, state)
        return state
