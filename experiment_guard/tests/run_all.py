#!/usr/bin/env python3
"""Run all Experiment Guard offline tests (0 paid API)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VIDEORSI = "/home/descfly/miniconda3/envs/videorsi/bin/python"


def run_mod(script: str, python: str = sys.executable) -> tuple[str, int, str]:
    r = subprocess.run(
        [python, str(HERE / script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    out = (r.stdout or "") + (r.stderr or "")
    return script, r.returncode, out


def main() -> int:
    suites = [
        ("test_runtime_guard.py", sys.executable),
        ("test_result_validator.py", sys.executable),
        ("test_protocol_validator.py", sys.executable),
        ("test_fault_injection.py", VIDEORSI),  # needs Services.sample_frames path
        ("test_preflight.py", sys.executable),  # internally probes videorsi + system
        ("test_e2e_integration.py", VIDEORSI),
        ("test_direct_vqa_guard_patch.py", VIDEORSI),
    ]
    failed = 0
    total_pass_lines = 0
    for script, py in suites:
        name, code, out = run_mod(script, py)
        print("===== %s (rc=%d) =====" % (name, code))
        print(out)
        total_pass_lines += out.count("PASS ")
        if code != 0:
            failed += 1
    print("===== SUMMARY suites_failed=%d pass_lines≈%d =====" % (failed, total_pass_lines))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
