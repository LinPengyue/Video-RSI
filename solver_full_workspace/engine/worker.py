"""Trusted process bootstrap. No pre-created Agent, ToolBox, Memory or Solver."""
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from isolation import filesystem_fence, syscall_fence, python_paths


class RPC:
    def __init__(self, source, sink):
        self.source, self.sink, self.sequence = source, sink, 0

    def call(self, name, arguments):
        self.sequence += 1
        self.sink.write(json.dumps({"type": "service", "id": self.sequence, "name": name, "arguments": arguments}, ensure_ascii=False, allow_nan=False) + "\n")
        self.sink.flush()
        value = json.loads(self.source.readline())
        if value.get("id") != self.sequence:
            raise RuntimeError("service response sequence mismatch")
        if "error" in value:
            raise RuntimeError(value["error"])
        return value["result"]


def main():
    sink, source = sys.stdout, sys.stdin
    request = json.loads(source.readline())
    root = Path(request["candidate"]).resolve()
    manifest = json.loads((root / "candidate.json").read_text())
    file, symbol = manifest["entrypoint"].split(":")
    entry = (root / file).resolve()
    if root not in entry.parents or not entry.is_file():
        raise RuntimeError("invalid candidate entrypoint")

    sys.path = [str(root)] + [p for p in sys.path if p and (str(Path(sys.base_prefix) / "lib") in p or str(Path(sys.prefix) / "lib") in p or p.startswith("/usr/lib/"))]
    os.chdir(root)
    sys.dont_write_bytecode = True
    scratch = Path(request["scratch"]).resolve()
    os.environ["TMPDIR"] = str(scratch)
    if request["isolation"]:
        syscall_fence(network=False)
        filesystem_fence(python_paths() + [root], [scratch])
    executed = set()

    def trace(frame, event, arg):
        if event == "call":
            filename = Path(frame.f_code.co_filename)
            if filename.is_absolute() and root in filename.parents:
                executed.add(str(filename.relative_to(root)))
        return trace

    sys.settrace(trace)

    sys.stdout = sys.stderr
    try:
        spec = importlib.util.spec_from_file_location("full_candidate_entry", entry)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        function = getattr(module, symbol)
        if not callable(function):
            raise ValueError("entrypoint is not callable")
        result = ({"status": "startup_ok"} if request.get("check_only") else function(request["item"], RPC(source, sink), request["budget"]))
        if not isinstance(result, dict):
            raise ValueError("candidate must return a JSON object")
        result = dict(result, executed_files=sorted(executed))
        sink.write(json.dumps({"type": "final", "result": result}, ensure_ascii=False, allow_nan=False) + "\n")
        sink.flush()
    except Exception as exc:
        status = "invalid_decision" if isinstance(exc, ValueError) and str(exc).startswith("invalid_decision:") else "engineering_error"
        sink.write(json.dumps({"type": "failure", "status": status, "error": type(exc).__name__ + ": " + str(exc), "executed_files": sorted(executed)}) + "\n")
        sink.flush()
    finally:
        sys.settrace(None)


if __name__ == "__main__":
    main()
