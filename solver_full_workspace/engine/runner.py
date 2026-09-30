import json
import os
import queue
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .common import public_item, read_json


INITIAL_HARNESS = Path(__file__).resolve().parents[1]
INITIAL_FILES = (
    "candidate.json", "main.py", "agent.py", "answers.py", "memory.py",
    "prompt.md", "skill_policy.py", "time_utils.py", "tools.py",
)


def check_candidate(candidate):
    root = Path(candidate).resolve()
    if not root.is_dir():
        raise ValueError("candidate directory missing")

    for path in root.rglob("*"):
        if path.is_symlink() and (Path(os.readlink(path)).is_absolute() or root not in path.resolve().parents):
            raise ValueError("candidate symlinks must remain relative and inside its snapshot")
    entry, symbol = read_json(root / "candidate.json")["entrypoint"].split(":")
    target = (root / entry).resolve()
    if root not in target.parents or not target.is_file() or not symbol.isidentifier():
        raise ValueError("invalid candidate entrypoint")
    return {"status": "static_pass", "entrypoint": entry + ":" + symbol}


def copy_candidate(source, destination):
    check_candidate(source)
    if Path(source).resolve() == INITIAL_HARNESS:

        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False)
        for name in INITIAL_FILES:
            shutil.copy2(INITIAL_HARNESS / name, destination / name)
        return
    shutil.copytree(source, destination, symlinks=True, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git"))


def run_item(candidate, item, services, config, check_only=False):
    """Every invocation imports a fresh snapshot in a new interpreter."""
    item = public_item(item)
    check_candidate(candidate)
    with tempfile.TemporaryDirectory(prefix="full-candidate-") as temp:
        snapshot = Path(temp) / "candidate"
        copy_candidate(candidate, snapshot)
        scratch = Path(temp) / "scratch"
        scratch.mkdir()
        request = {"candidate": str(snapshot), "scratch": str(scratch), "item": item, "budget": config["solver"], "isolation": config["execution"]["linux_isolation"], "check_only": check_only}
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        stderr = tempfile.TemporaryFile(mode="w+b")
        process = subprocess.Popen([config["execution"]["python"], "-I", str(Path(__file__).with_name("worker.py"))], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True, env=env, start_new_session=True)
        responses = queue.Queue()

        def read():
            try:
                for line in process.stdout:
                    responses.put(line)
            finally:
                responses.put(None)

        threading.Thread(target=read, daemon=True).start()
        timer = threading.Timer(config["solver"]["timeout_seconds"], lambda: stop_process(process))
        timer.start()
        result, failure = None, None
        try:
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + config["solver"]["timeout_seconds"]
            while time.monotonic() < deadline:
                try:
                    line = responses.get(timeout=max(.01, deadline - time.monotonic()))
                except queue.Empty:
                    failure = "candidate timeout"
                    break
                if line is None:
                    break
                value = json.loads(line)
                if value.get("type") == "service":
                    try:
                        response = {"id": value["id"], "result": services.call(value["name"], value["arguments"])}
                    except Exception as exc:
                        response = {"id": value["id"], "error": type(exc).__name__ + ": " + str(exc)}
                    if process.poll() is not None:
                        failure = "candidate exited during service call"
                        break
                    process.stdin.write(json.dumps(response, ensure_ascii=False, allow_nan=False) + "\n")
                    process.stdin.flush()
                elif value.get("type") == "final":
                    result = value["result"]
                    break
                elif value.get("type") == "failure":
                    result = {"status": value.get("status", "engineering_error"), "answer": None, "error": value.get("error"), "executed_files": value.get("executed_files", [])}
                    break
                else:
                    failure = value.get("error", "invalid worker protocol")
                    break
        except Exception as exc:
            failure = type(exc).__name__ + ": " + str(exc)
        finally:
            timer.cancel()
            stop_process(process)
            process.wait()
            process.stdin.close()
            process.stdout.close()
            stderr.seek(0)
            diagnostic = stderr.read().decode(errors="replace")[-8000:]
            stderr.close()
        if result is None:
            result = {"status": "engineering_error", "answer": None, "error": failure or "worker exited without result", "stderr": diagnostic}
        if result.get("status") == "answered" and result.get("answer") not in item["options"]:
            result.update(status="invalid_decision", answer=None, error="answer is not one actual option")
        result.update(sample_id=item["sample_id"], usage=services.meter.summary(), meter_events=services.meter.events, service_trace=services.trace)
        return result


def stop_process(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
