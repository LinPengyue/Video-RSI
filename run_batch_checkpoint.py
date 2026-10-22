"""Resumable batch runner with fingerprint guards and runner-level budget stops.

External experiment tool only. Does not modify Solver, Initial Harness, H_S1, or Gate.
Reuses run_batch.load_items / public_item / copy_candidate / run_item.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import tempfile
import threading
import time
from pathlib import Path

from run_batch import load_items
from solver_full_workspace.engine.common import public_item, read_json, validate_config, write_json
from solver_full_workspace.engine.runner import INITIAL_FILES, INITIAL_HARNESS, copy_candidate, run_item
from solver_full_workspace.engine.services import Services

PROTOCOL = "batch_checkpoint_v1"
TERMINAL_OK = frozenset({"answered", "invalid_decision"})
DEFAULT_RATE_IN = 2.0
DEFAULT_RATE_OUT = 8.0


class BatchFingerprintError(ValueError):
    """Harness / items / config / sample_id mismatch on resume."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def harness_tree_sha256(candidate: Path) -> str:
    lines = []
    for name in sorted(INITIAL_FILES):
        path = Path(candidate) / name
        if not path.is_file():
            raise FileNotFoundError("missing harness file: " + name)
        lines.append("%s %s" % (name, sha256_file(path)))
    return sha256_bytes(("\n".join(lines) + "\n").encode())


def config_fingerprint(config: dict) -> str:
    """Hash only fields that affect Solver batch execution (not secrets)."""
    slim = {
        "protocol": config.get("protocol"),
        "solver": config.get("solver"),
        "execution": {
            "concurrency": config.get("execution", {}).get("concurrency"),
            "linux_isolation": config.get("execution", {}).get("linux_isolation"),
        },
        "services": {
            "deepseek": {
                "request_model": config.get("services", {}).get("deepseek", {}).get("request_model"),
                "max_tokens": config.get("services", {}).get("deepseek", {}).get("max_tokens"),
            },
            "qwen": {
                "request_model": config.get("services", {}).get("qwen", {}).get("request_model"),
                "max_tokens": config.get("services", {}).get("qwen", {}).get("max_tokens"),
            },
            "temperature": config.get("services", {}).get("temperature"),
            "provider_retries": config.get("services", {}).get("provider_retries"),
        },
        "gate": config.get("gate"),
        "investigation": config.get("investigation"),
    }
    blob = json.dumps(slim, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256_bytes(blob)


def items_fingerprint(rows: list) -> str:
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return sha256_bytes(blob)


def estimate_cny(prompt_tokens: int, completion_tokens: int, rate_in: float, rate_out: float) -> float:
    return (prompt_tokens * rate_in + completion_tokens * rate_out) / 1e6


def usage_from_result(result: dict) -> dict:
    usage = result.get("usage") or {}
    prompt = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    completion = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    calls = int(usage.get("deepseek_calls") or 0) + int(usage.get("qwen_calls") or 0)
    if calls <= 0:
        for ev in result.get("meter_events") or []:
            if ev.get("kind") == "provider":
                calls += 1
                u = ev.get("usage") or {}
                prompt += int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
                completion += int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    return {"provider_calls": calls, "prompt_tokens": prompt, "completion_tokens": completion}


def item_path(output: Path, index: int) -> Path:
    return output / "items" / ("%06d.json" % index)


def is_terminal_success(result: dict | None) -> bool:
    return isinstance(result, dict) and result.get("status") in TERMINAL_OK and bool(result.get("sample_id"))


def load_existing_result(output: Path, index: int, sample_id: str) -> dict | None:
    path = item_path(output, index)
    if not path.is_file():
        return None
    result = read_json(path)
    if result.get("sample_id") != sample_id:
        raise BatchFingerprintError(
            "item file %s has sample_id %r, expected %r" % (path, result.get("sample_id"), sample_id)
        )
    return result


class BudgetLedger:
    """Thread-safe runner-level call / estimated-CNY guard.

    New work is refused once spent+reserved would exceed limits.
    In-flight tasks that already reserved may still finish, so overshoot is
    bounded by concurrency × reserve (not unbounded open-ended spend).
    """

    def __init__(
        self,
        *,
        max_provider_calls: int | None,
        max_estimated_cny: float | None,
        reserve_calls: int,
        reserve_cny: float,
        rate_in: float,
        rate_out: float,
    ):
        self.max_provider_calls = max_provider_calls
        self.max_estimated_cny = max_estimated_cny
        self.reserve_calls = max(1, int(reserve_calls))
        self.reserve_cny = max(0.0, float(reserve_cny))
        self.rate_in = rate_in
        self.rate_out = rate_out
        self._lock = threading.Lock()
        self.spent_calls = 0
        self.spent_cny = 0.0
        self.reserved_calls = 0
        self.reserved_cny = 0.0
        self.stop_reason = None
        self.skipped_new_submits = 0

    def credit_prior(self, *, provider_calls: int, prompt_tokens: int, completion_tokens: int) -> None:
        cny = estimate_cny(prompt_tokens, completion_tokens, self.rate_in, self.rate_out)
        with self._lock:
            self.spent_calls += max(0, int(provider_calls))
            self.spent_cny += max(0.0, cny)
            self._trip_if_spent_exceeds()

    def _trip_if_spent_exceeds(self) -> None:
        if self.max_provider_calls is not None and self.spent_calls >= self.max_provider_calls:
            self.stop_reason = self.stop_reason or "max_provider_calls"
        if self.max_estimated_cny is not None and self.spent_cny >= self.max_estimated_cny:
            self.stop_reason = self.stop_reason or "max_estimated_cny"

    def _would_exceed(self, calls: int, cny: float) -> str | None:
        if self.max_provider_calls is not None:
            if self.spent_calls + self.reserved_calls + calls > self.max_provider_calls:
                return "max_provider_calls"
        if self.max_estimated_cny is not None:
            if self.spent_cny + self.reserved_cny + cny > self.max_estimated_cny + 1e-12:
                return "max_estimated_cny"
        return None

    def try_reserve(self) -> bool:
        """Reserve budget for one new item before scheduling. False => do not submit."""
        with self._lock:
            if self.stop_reason:
                self.skipped_new_submits += 1
                return False
            reason = self._would_exceed(self.reserve_calls, self.reserve_cny)
            if reason:
                self.stop_reason = reason
                self.skipped_new_submits += 1
                return False
            self.reserved_calls += self.reserve_calls
            self.reserved_cny += self.reserve_cny
            return True

    def settle(self, *, provider_calls: int, prompt_tokens: int, completion_tokens: int) -> None:
        cny = estimate_cny(prompt_tokens, completion_tokens, self.rate_in, self.rate_out)
        with self._lock:
            self.reserved_calls = max(0, self.reserved_calls - self.reserve_calls)
            self.reserved_cny = max(0.0, self.reserved_cny - self.reserve_cny)
            self.spent_calls += max(0, int(provider_calls))
            self.spent_cny += max(0.0, cny)
            self._trip_if_spent_exceeds()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "spent_calls": self.spent_calls,
                "spent_estimated_cny": round(self.spent_cny, 6),
                "reserved_calls": self.reserved_calls,
                "reserved_estimated_cny": round(self.reserved_cny, 6),
                "stop_reason": self.stop_reason,
                "skipped_new_submits": self.skipped_new_submits,
                "max_provider_calls": self.max_provider_calls,
                "max_estimated_cny": self.max_estimated_cny,
                "reserve_calls": self.reserve_calls,
                "reserve_cny": self.reserve_cny,
                "rate_in": self.rate_in,
                "rate_out": self.rate_out,
            }


def expected_manifest_core(config: dict, candidate: Path, rows: list) -> dict:
    return {
        "protocol": PROTOCOL,
        "harness_tree_sha256": harness_tree_sha256(candidate),
        "items_sha256": items_fingerprint(rows),
        "config_fingerprint": config_fingerprint(config),
        "sample_ids": [r["sample_id"] for r in rows],
    }


def create_run(output: Path, config: dict, candidate: Path, rows: list, budget: dict) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    frozen = output / "candidate"
    copy_candidate(candidate, frozen)
    core = expected_manifest_core(config, frozen, rows)
    manifest = {
        **core,
        "budget": budget,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "status": "running",
    }
    write_json(output / "config.json", config)
    write_json(output / "items.json", rows)
    write_json(output / "batch_manifest.json", manifest)
    return manifest


def validate_resume(output: Path, config: dict, rows: list) -> dict:
    manifest_path = output / "batch_manifest.json"
    if not manifest_path.is_file():
        raise BatchFingerprintError("output exists but batch_manifest.json missing; refuse unsafe resume")
    frozen = output / "candidate"
    if not frozen.is_dir():
        raise BatchFingerprintError("frozen candidate directory missing under output")
    existing = read_json(manifest_path)
    expected = expected_manifest_core(config, frozen, rows)
    for key in ("protocol", "harness_tree_sha256", "items_sha256", "config_fingerprint", "sample_ids"):
        if existing.get(key) != expected[key]:
            raise BatchFingerprintError(
                "resume fingerprint mismatch on %s: existing=%r expected=%r"
                % (key, existing.get(key), expected[key])
            )
    # Drift check: frozen tree must still match recorded harness hash.
    if harness_tree_sha256(frozen) != existing["harness_tree_sha256"]:
        raise BatchFingerprintError("frozen candidate harness hash drifted from manifest")
    existing["last_resume_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    write_json(manifest_path, existing)
    return existing


def write_results_aggregate(output: Path, rows: list) -> list:
    results = []
    for index, row in enumerate(rows):
        path = item_path(output, index)
        if path.is_file():
            results.append(read_json(path))
        else:
            results.append({"sample_id": row["sample_id"], "status": "missing", "answer": None})
    write_json(output / "results.json", results)
    return results


def run_batch_checkpoint(
    config: dict,
    candidate,
    rows: list,
    output,
    *,
    resume: bool = True,
    max_provider_calls: int | None = None,
    max_estimated_cny: float | None = None,
    reserve_calls: int = 12,
    reserve_cny: float = 0.15,
    rate_in: float = DEFAULT_RATE_IN,
    rate_out: float = DEFAULT_RATE_OUT,
    services_factory=Services,
    runner=run_item,
) -> dict:
    output = Path(output)
    candidate = Path(candidate)
    budget = {
        "max_provider_calls": max_provider_calls,
        "max_estimated_cny": max_estimated_cny,
        "reserve_calls": reserve_calls,
        "reserve_cny": reserve_cny,
        "rate_in": rate_in,
        "rate_out": rate_out,
    }

    if output.exists():
        if not resume:
            raise FileExistsError("output exists; refuse without resume: " + str(output))
        manifest = validate_resume(output, config, rows)
    else:
        manifest = create_run(output, config, candidate, rows, budget)

    frozen = output / "candidate"
    ledger = BudgetLedger(
        max_provider_calls=max_provider_calls,
        max_estimated_cny=max_estimated_cny,
        reserve_calls=reserve_calls,
        reserve_cny=reserve_cny,
        rate_in=rate_in,
        rate_out=rate_out,
    )

    pending = []
    reused = []
    for index, row in enumerate(rows):
        existing = load_existing_result(output, index, row["sample_id"])
        if is_terminal_success(existing):
            reused.append(row["sample_id"])
            stats = usage_from_result(existing)
            ledger.credit_prior(
                provider_calls=stats["provider_calls"],
                prompt_tokens=stats["prompt_tokens"],
                completion_tokens=stats["completion_tokens"],
            )
            continue
        pending.append((index, row))

    concurrency = int(config["execution"]["concurrency"])
    newly_run = []
    errors = []
    call_counter = {"n": 0}
    call_lock = threading.Lock()

    def one(index_row):
        index, row = index_row
        with call_lock:
            call_counter["n"] += 1
        item = public_item(row)
        media = {key: row[key] for key in ("video_path", "asr_path") if row.get(key)}
        with tempfile.TemporaryDirectory(prefix="video-rsi-batch-") as scratch:
            try:
                services = services_factory(item, media, config, scratch)
                result = runner(frozen, item, services, config)
            except Exception as exc:
                result = {
                    "sample_id": row["sample_id"],
                    "status": "engineering_error",
                    "answer": None,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:500],
                }
        stats = usage_from_result(result)
        ledger.settle(
            provider_calls=stats["provider_calls"],
            prompt_tokens=stats["prompt_tokens"],
            completion_tokens=stats["completion_tokens"],
        )
        write_json(item_path(output, index), result)
        return result

    if pending and ledger.stop_reason is None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {}
            it = iter(pending)

            def try_submit_next():
                try:
                    job = next(it)
                except StopIteration:
                    return False
                if not ledger.try_reserve():
                    return False
                futures[pool.submit(one, job)] = job[1]["sample_id"]
                return True

            for _ in range(min(concurrency, len(pending))):
                if not try_submit_next():
                    break

            while futures:
                done, _ = concurrent.futures.wait(
                    futures, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for fut in done:
                    sid = futures.pop(fut)
                    try:
                        result = fut.result()
                    except Exception as exc:
                        errors.append({"sample_id": sid, "error": type(exc).__name__})
                        continue
                    newly_run.append(result.get("sample_id"))
                    if result.get("status") == "engineering_error":
                        errors.append(
                            {"sample_id": result.get("sample_id"), "error": result.get("error_type")}
                        )

                if ledger.stop_reason is None:
                    while len(futures) < concurrency:
                        if not try_submit_next():
                            break

    # Drain any remaining pending as skipped_budget markers only in summary (no files).
    remaining = [row["sample_id"] for _, row in pending if row["sample_id"] not in newly_run]
    skipped = remaining if ledger.stop_reason else []

    results = write_results_aggregate(output, rows)
    complete = all(is_terminal_success(r) for r in results)
    if complete:
        status = "completed"
    elif ledger.stop_reason:
        status = "stopped_budget"
    else:
        status = "incomplete"

    summary = {
        "protocol": PROTOCOL,
        "status": status,
        "n": len(rows),
        "reused_terminal": reused,
        "newly_run": newly_run,
        "skipped_budget": skipped,
        "runner_invocations": call_counter["n"],
        "errors": errors,
        "budget": ledger.snapshot(),
        "manifest": {
            "harness_tree_sha256": manifest["harness_tree_sha256"],
            "items_sha256": manifest["items_sha256"],
            "config_fingerprint": manifest["config_fingerprint"],
        },
        "output_dir": str(output),
    }
    write_json(output / "batch_summary.json", summary)
    manifest = read_json(output / "batch_manifest.json")
    manifest["status"] = status
    manifest["budget_last"] = ledger.snapshot()
    write_json(output / "batch_manifest.json", manifest)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--candidate", default=str(INITIAL_HARNESS))
    parser.add_argument("--items", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-provider-calls", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="refuse if output_dir exists")
    parser.add_argument("--max-provider-calls", type=int, default=None)
    parser.add_argument("--max-estimated-cny", type=float, default=None)
    parser.add_argument("--reserve-calls", type=int, default=12)
    parser.add_argument("--reserve-cny", type=float, default=0.15)
    parser.add_argument("--rate-in", type=float, default=DEFAULT_RATE_IN)
    parser.add_argument("--rate-out", type=float, default=DEFAULT_RATE_OUT)
    parser.add_argument("--skip-media-check", action="store_true")
    args = parser.parse_args()
    if not args.allow_provider_calls:
        parser.error("inference requires --allow-provider-calls")
    config = validate_config(read_json(args.config))
    rows = load_items(args.items, check_media=not args.skip_media_check)
    summary = run_batch_checkpoint(
        config,
        args.candidate,
        rows,
        args.output_dir,
        resume=not args.no_resume,
        max_provider_calls=args.max_provider_calls,
        max_estimated_cny=args.max_estimated_cny,
        reserve_calls=args.reserve_calls,
        reserve_cny=args.reserve_cny,
        rate_in=args.rate_in,
        rate_out=args.rate_out,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
