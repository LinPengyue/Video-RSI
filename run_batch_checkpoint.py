"""Resumable batch runner with fingerprint guards and per-model budget stops.

External experiment tool only. Does not modify Solver, Initial Harness, H_S1, or Gate.
Reuses run_batch.load_items / public_item / copy_candidate / run_item.

Estimated CNY uses per-model MaaS rates (see batch_billing.py). This is a local
planning fuse — not a provider account hard limit.
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

from batch_billing import (
    DEFAULT_MODEL_RATES,
    empty_usage,
    merge_usage,
    rates_snapshot,
    usage_from_result,
)
from run_batch import load_items
from solver_full_workspace.engine.common import public_item, read_json, validate_config, write_json
from solver_full_workspace.engine.runner import INITIAL_FILES, INITIAL_HARNESS, copy_candidate, run_item
from solver_full_workspace.engine.services import Services

PROTOCOL = "batch_checkpoint_v1"
TERMINAL_OK = frozenset({"answered", "invalid_decision"})


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
    """Thread-safe runner-level call / estimated-CNY guard (per-model rates).

    New work is refused once spent+reserved would exceed limits.
    In-flight reserved tasks may still finish; overshoot ≤ concurrency × reserve.
    This does NOT equal a provider-side spend hard limit.
    """

    def __init__(
        self,
        *,
        max_provider_calls: int | None,
        max_estimated_cny: float | None,
        reserve_calls: int,
        reserve_cny: float,
        model_rates: dict,
        apply_cache: bool,
    ):
        self.max_provider_calls = max_provider_calls
        self.max_estimated_cny = max_estimated_cny
        self.reserve_calls = max(1, int(reserve_calls))
        self.reserve_cny = max(0.0, float(reserve_cny))
        self.model_rates = model_rates
        self.apply_cache = apply_cache
        self._lock = threading.Lock()
        self.spent_calls = 0
        self.spent_cny = 0.0
        self.reserved_calls = 0
        self.reserved_cny = 0.0
        self.stop_reason = None
        self.skipped_new_submits = 0
        self.usage_total = empty_usage()
        self.undercount_items = 0

    def credit_prior_usage(self, usage: dict) -> None:
        with self._lock:
            merge_usage(self.usage_total, usage)
            self.spent_calls += max(0, int(usage["provider_calls"]))
            self.spent_cny += max(0.0, float(usage["estimated_cny"]))
            if usage.get("undercount_risk"):
                self.undercount_items += 1
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

    def settle_usage(self, usage: dict) -> None:
        with self._lock:
            self.reserved_calls = max(0, self.reserved_calls - self.reserve_calls)
            self.reserved_cny = max(0.0, self.reserved_cny - self.reserve_cny)
            merge_usage(self.usage_total, usage)
            self.spent_calls += max(0, int(usage["provider_calls"]))
            self.spent_cny += max(0.0, float(usage["estimated_cny"]))
            if usage.get("undercount_risk"):
                self.undercount_items += 1
            self._trip_if_spent_exceeds()

    def snapshot(self) -> dict:
        with self._lock:
            by_role = {
                role: {
                    "calls": slot["calls"],
                    "ok_calls": slot["ok_calls"],
                    "non_ok_calls": slot["non_ok_calls"],
                    "missing_usage_calls": slot["missing_usage_calls"],
                    "prompt_tokens": slot["prompt_tokens"],
                    "completion_tokens": slot["completion_tokens"],
                    "cached_tokens": slot["cached_tokens"],
                    "estimated_cny": round(slot["estimated_cny"], 6),
                    "estimated_cny_no_cache": round(slot["estimated_cny_no_cache"], 6),
                }
                for role, slot in self.usage_total["by_role"].items()
            }
            return {
                "spent_calls": self.spent_calls,
                "spent_estimated_cny": round(self.spent_cny, 6),
                "spent_estimated_cny_no_cache": round(self.usage_total["estimated_cny_no_cache"], 6),
                "reserved_calls": self.reserved_calls,
                "reserved_estimated_cny": round(self.reserved_cny, 6),
                "stop_reason": self.stop_reason,
                "skipped_new_submits": self.skipped_new_submits,
                "max_provider_calls": self.max_provider_calls,
                "max_estimated_cny": self.max_estimated_cny,
                "reserve_calls": self.reserve_calls,
                "reserve_cny": self.reserve_cny,
                "apply_cache_rates": self.apply_cache,
                "model_rates": rates_snapshot(self.model_rates),
                "by_role": by_role,
                "missing_usage_calls": self.usage_total["missing_usage_calls"],
                "non_ok_calls": self.usage_total["non_ok_calls"],
                "undercount_items": self.undercount_items,
                "undercount_risk": bool(self.usage_total.get("undercount_risk")),
                "disclaimer": (
                    "estimated_cny is a local planning fuse from MaaS unit rates; "
                    "not a provider account hard limit; missing usage / retries may undercount"
                ),
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
    reserve_calls: int = 16,
    reserve_cny: float = 0.8,
    model_rates: dict | None = None,
    apply_cache: bool = True,
    services_factory=Services,
    runner=run_item,
) -> dict:
    output = Path(output)
    candidate = Path(candidate)
    model_rates = model_rates or DEFAULT_MODEL_RATES
    budget = {
        "max_provider_calls": max_provider_calls,
        "max_estimated_cny": max_estimated_cny,
        "reserve_calls": reserve_calls,
        "reserve_cny": reserve_cny,
        "model_rates": rates_snapshot(model_rates),
        "apply_cache": apply_cache,
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
        model_rates=model_rates,
        apply_cache=apply_cache,
    )

    pending = []
    reused = []
    for index, row in enumerate(rows):
        existing = load_existing_result(output, index, row["sample_id"])
        if is_terminal_success(existing):
            reused.append(row["sample_id"])
            usage = usage_from_result(existing, model_rates, apply_cache=apply_cache)
            ledger.credit_prior_usage(usage)
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
        usage = usage_from_result(result, model_rates, apply_cache=apply_cache)
        # Persist billing snapshot on the item for audit (no secrets).
        result = dict(result)
        result["billing_estimate"] = {
            "by_role": usage["by_role"],
            "estimated_cny": usage["estimated_cny"],
            "estimated_cny_no_cache": usage["estimated_cny_no_cache"],
            "source": usage["source"],
            "undercount_risk": usage["undercount_risk"],
            "notes": usage.get("notes") or [],
        }
        ledger.settle_usage(usage)
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
    parser.add_argument("--reserve-calls", type=int, default=16)
    parser.add_argument("--reserve-cny", type=float, default=0.8)
    parser.add_argument(
        "--no-cache-rates",
        action="store_true",
        help="ignore cached_tokens discounts (bill all prompt at rate_in)",
    )
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
        apply_cache=not args.no_cache_rates,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
