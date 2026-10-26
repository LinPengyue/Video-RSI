"""Fail-closed concurrent batch execution with RuntimeGuard abort.

Stops submitting new work after systematic infra failure; cancels futures that
have not started. In-flight tasks may finish — recorded as extra_calls_after_abort.
"""
from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from experiment_guard.runtime_guard import RuntimeGuard


@dataclass
class BatchExecutionReport:
    submitted: int = 0
    completed: int = 0
    cancelled_before_start: int = 0
    never_submitted: int = 0
    completed_after_abort: int = 0
    aborted: bool = False
    abort_reason: str | None = None
    results: list[dict] = field(default_factory=list)
    never_submitted_ids: list[str] = field(default_factory=list)
    cancelled_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "submitted": self.submitted,
            "completed": self.completed,
            "cancelled_before_start": self.cancelled_before_start,
            "never_submitted": self.never_submitted,
            "completed_after_abort": self.completed_after_abort,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "never_submitted_ids": self.never_submitted_ids,
            "cancelled_ids": self.cancelled_ids,
            "n_results": len(self.results),
            "note": (
                "In-flight tasks may complete after abort; see completed_after_abort. "
                "Those calls may incur extra API cost."
                if self.completed_after_abort
                else None
            ),
        }


def run_guarded_batch(
    item_ids: Iterable[str],
    worker: Callable[[str], dict],
    guard: RuntimeGuard,
    *,
    max_workers: int = 2,
    fingerprint_fn: Callable[[], tuple[str | None, str | None]] | None = None,
    id_key: str = "sample_id",
) -> BatchExecutionReport:
    """Run worker(sid) under ThreadPoolExecutor with incremental submit + abort.

    fingerprint_fn: optional callable returning (config_fp, harness_sha) by re-reading disk.
    """
    ids = list(item_ids)
    report = BatchExecutionReport()
    lock = threading.Lock()
    aborted_at: float | None = None

    def _current_fp() -> str | None:
        if fingerprint_fn is None:
            return None
        cfg_fp, _harness = fingerprint_fn()
        return cfg_fp

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pending = list(ids)
        in_flight: dict[Future, str] = {}

        def _submit_available() -> None:
            while pending and len(in_flight) < max_workers and not guard.aborted:
                sid = pending.pop(0)
                fut = pool.submit(worker, sid)
                in_flight[fut] = sid
                report.submitted += 1

        _submit_available()

        while in_flight or (pending and not guard.aborted):
            if guard.aborted:
                # Cancel not-started futures; leave running ones
                for fut, sid in list(in_flight.items()):
                    if fut.cancel():
                        report.cancelled_before_start += 1
                        report.cancelled_ids.append(sid)
                        del in_flight[fut]
                # Do not submit remaining
                if pending:
                    report.never_submitted_ids.extend(pending)
                    report.never_submitted += len(pending)
                    pending.clear()
                if not in_flight:
                    break

            if not in_flight:
                _submit_available()
                if not in_flight:
                    break

            done, _ = wait(tuple(in_flight.keys()), return_when=FIRST_COMPLETED)
            for fut in done:
                sid = in_flight.pop(fut)
                was_aborted = guard.aborted
                try:
                    row = fut.result()
                except Exception as exc:
                    row = {
                        id_key: sid,
                        "status": "engineering_error",
                        "answer": None,
                        "error": "%s:%s" % (type(exc).__name__, exc)[:400],
                        "usage": {},
                        "memory": [],
                        "service_trace": [],
                        "diagnostics": {"tool_execution_errors": 1},
                    }
                if id_key not in row:
                    row = dict(row)
                    row[id_key] = sid

                cur_fp = _current_fp()
                with lock:
                    guard.observe_result(row, current_fingerprint=cur_fp)
                    report.results.append(row)
                    report.completed += 1
                    if was_aborted:
                        report.completed_after_abort += 1
                    if guard.aborted and aborted_at is None:
                        aborted_at = True  # mark

            if not guard.aborted:
                _submit_available()
            else:
                # drain: cancel pending submits, wait in-flight
                for fut, sid in list(in_flight.items()):
                    if fut.cancel():
                        report.cancelled_before_start += 1
                        report.cancelled_ids.append(sid)
                        del in_flight[fut]
                if pending:
                    report.never_submitted_ids.extend(pending)
                    report.never_submitted += len(pending)
                    pending.clear()

    report.aborted = guard.aborted
    report.abort_reason = guard.abort_reason
    return report
