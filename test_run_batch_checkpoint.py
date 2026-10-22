"""Offline simulation tests for run_batch_checkpoint (no provider API calls)."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from run_batch_checkpoint import (
    BatchFingerprintError,
    config_fingerprint,
    harness_tree_sha256,
    run_batch_checkpoint,
)
from solver_full_workspace.engine.common import read_json, validate_config
from solver_full_workspace.engine.runner import INITIAL_FILES, INITIAL_HARNESS


def make_config(concurrency=2):
    return validate_config(
        {
            "protocol": "full-candidate-v1",
            "evolution": {"max_rounds": 20},
            "solver": {
                "max_steps": 11,
                "max_service_calls": 64,
                "max_frames": 256,
                "timeout_seconds": 1800,
            },
            "execution": {"concurrency": concurrency, "linux_isolation": False, "python": "/usr/bin/python3"},
            "services": {
                "endpoint_env": "API_BASE",
                "key_env": "API_KEY",
                "deepseek": {"request_model": "mock-deepseek", "max_tokens": 128},
                "qwen": {"request_model": "mock-qwen", "max_tokens": 128},
                "temperature": 0,
                "timeout_seconds": 30,
                "provider_retries": 1,
                "ffmpeg": "imageio-ffmpeg",
                "ocr_model_root": "/tmp",
            },
            "editor": {
                "max_provider_calls": 10,
                "timeout_seconds": 60,
                "pause_after_plan": False,
                "harness_root": "/tmp",
                "node_binary": "/usr/bin/node",
            },
            "investigation": {"max_frames": 64},
            "gate": {"policy": "accuracy_gain_10pct_or_save_20pct_drop1_v1", "max_mean_frames": None},
        }
    )


def make_rows(n=6):
    rows = []
    for i in range(n):
        rows.append(
            {
                "sample_id": "SIM_%02d" % i,
                "question": "offline sim question %d?" % i,
                "options": {"A": "a", "B": "b", "C": "c", "D": "d"},
                "duration": 10.0 + i,
                "task_type": "sim",
            }
        )
    return rows


class FakeServices:
    def __init__(self, item, media, config, scratch):
        self.item = item


def make_mock_runner(invocations, *, calls_per_item=3, prompt=1000, completion=200, delay=0.0, fail_ids=None):
    fail_ids = set(fail_ids or [])
    lock = threading.Lock()

    def runner(candidate, item, services, config):
        sid = item["sample_id"]
        with lock:
            invocations.append(sid)
        if delay:
            time.sleep(delay)
        if sid in fail_ids:
            raise RuntimeError("forced fail for " + sid)
        return {
            "sample_id": sid,
            "status": "answered",
            "answer": "A",
            "usage": {
                "deepseek_calls": calls_per_item,
                "qwen_calls": 0,
                "input_tokens": prompt,
                "output_tokens": completion,
            },
        }

    return runner


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="batch-ckpt-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_resume_skips_terminal_no_duplicate_invocations(self):
        config = make_config(concurrency=2)
        rows = make_rows(5)
        out = self.tmp / "run1"
        inv = []
        summary1 = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            resume=True,
            max_provider_calls=1000,
            reserve_calls=3,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, calls_per_item=3),
        )
        self.assertEqual(summary1["status"], "completed")
        self.assertEqual(sorted(inv), sorted(r["sample_id"] for r in rows))
        first_inv = list(inv)

        # Delete last two item files to simulate mid-batch crash after partial write.
        for index in (3, 4):
            (out / "items" / ("%06d.json" % index)).unlink()

        inv.clear()
        summary2 = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            resume=True,
            max_provider_calls=1000,
            reserve_calls=3,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, calls_per_item=3),
        )
        self.assertEqual(summary2["status"], "completed")
        self.assertEqual(sorted(summary2["reused_terminal"]), ["SIM_00", "SIM_01", "SIM_02"])
        self.assertEqual(sorted(summary2["newly_run"]), ["SIM_03", "SIM_04"])
        self.assertEqual(sorted(inv), ["SIM_03", "SIM_04"])
        self.assertEqual(summary2["runner_invocations"], 2)

        results = read_json(out / "results.json")
        self.assertEqual([r["sample_id"] for r in results], [r["sample_id"] for r in rows])
        self.assertTrue(all(r["status"] == "answered" for r in results))
        # Prior completed answers must be unchanged / present.
        for index in range(3):
            self.assertEqual(read_json(out / "items" / ("%06d.json" % index))["answer"], "A")
        self.assertEqual(len(first_inv), 5)

    def test_fingerprint_mismatch_config_model(self):
        config = make_config()
        rows = make_rows(3)
        out = self.tmp / "run_cfg"
        inv = []
        run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=make_mock_runner(inv),
        )
        bad = copy.deepcopy(config)
        bad["services"]["deepseek"]["request_model"] = "other-model"
        with self.assertRaises(BatchFingerprintError) as ctx:
            run_batch_checkpoint(
                bad,
                INITIAL_HARNESS,
                rows,
                out,
                services_factory=FakeServices,
                runner=make_mock_runner([]),
            )
        self.assertIn("config_fingerprint", str(ctx.exception))

    def test_fingerprint_mismatch_items(self):
        config = make_config()
        rows = make_rows(3)
        out = self.tmp / "run_items"
        run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=make_mock_runner([]),
        )
        other = make_rows(3)
        other[1]["question"] = "tampered"
        with self.assertRaises(BatchFingerprintError) as ctx:
            run_batch_checkpoint(
                config,
                INITIAL_HARNESS,
                other,
                out,
                services_factory=FakeServices,
                runner=make_mock_runner([]),
            )
        self.assertIn("items_sha256", str(ctx.exception))

    def test_fingerprint_mismatch_sample_id_in_item_file(self):
        config = make_config()
        rows = make_rows(2)
        out = self.tmp / "run_sid"
        run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=make_mock_runner([]),
        )
        # Corrupt per-item sample_id while keeping manifest.
        path = out / "items" / "000000.json"
        data = read_json(path)
        data["sample_id"] = "WRONG"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(BatchFingerprintError) as ctx:
            run_batch_checkpoint(
                config,
                INITIAL_HARNESS,
                rows,
                out,
                services_factory=FakeServices,
                runner=make_mock_runner([]),
            )
        self.assertIn("sample_id", str(ctx.exception))

    def test_fingerprint_mismatch_harness(self):
        config = make_config()
        rows = make_rows(2)
        out = self.tmp / "run_harness"
        run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=make_mock_runner([]),
        )
        # Mutate frozen harness after run.
        prompt = out / "candidate" / "prompt.md"
        prompt.write_text(prompt.read_text(encoding="utf-8") + "\n# tamper\n", encoding="utf-8")
        with self.assertRaises(BatchFingerprintError):
            run_batch_checkpoint(
                config,
                INITIAL_HARNESS,
                rows,
                out,
                services_factory=FakeServices,
                runner=make_mock_runner([]),
            )

    def test_budget_call_breaker_no_new_submit_after_stop(self):
        config = make_config(concurrency=1)
        rows = make_rows(6)
        out = self.tmp / "run_budget"
        inv = []
        # Each item costs 3 calls; reserve 3; max 9 => at most 3 items.
        summary = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            max_provider_calls=9,
            reserve_calls=3,
            reserve_cny=0.0,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, calls_per_item=3),
        )
        self.assertEqual(summary["status"], "stopped_budget")
        self.assertEqual(summary["budget"]["stop_reason"], "max_provider_calls")
        self.assertEqual(len(inv), 3)
        self.assertEqual(summary["runner_invocations"], 3)
        results = read_json(out / "results.json")
        answered = [r for r in results if r["status"] == "answered"]
        missing = [r for r in results if r["status"] == "missing"]
        self.assertEqual(len(answered), 3)
        self.assertEqual(len(missing), 3)

        # Resume with same budget: prior spend already at cap => no new calls.
        inv.clear()
        summary2 = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            max_provider_calls=9,
            reserve_calls=3,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, calls_per_item=3),
        )
        self.assertEqual(summary2["status"], "stopped_budget")
        self.assertEqual(inv, [])
        self.assertEqual(len(summary2["reused_terminal"]), 3)

    def test_concurrent_overshoot_bounded_by_reserves(self):
        """With concurrency=3 and tight call cap, in-flight may finish but no unbounded overrun."""
        config = make_config(concurrency=3)
        rows = make_rows(10)
        out = self.tmp / "run_conc"
        inv = []
        # Reserve 5 calls each; max 12 => at most 2 concurrent reserves (10+5 would exceed).
        # So at most 2 items ever submitted; overshoot on settle can put spent at 2*5=10 <= 12,
        # or if settle uses actual 5, spent=10. Either way invocations <= 2.
        summary = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            max_provider_calls=12,
            reserve_calls=5,
            reserve_cny=0.0,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, calls_per_item=5, delay=0.05),
        )
        self.assertEqual(summary["status"], "stopped_budget")
        self.assertLessEqual(len(inv), 2)
        self.assertEqual(summary["runner_invocations"], len(inv))
        self.assertLessEqual(summary["budget"]["spent_calls"], 12 + 5)  # hard ceiling: one reserve unit beyond? 
        # Actually spent should be exactly invocations * 5, and invocations <= floor(12/5)=2.
        self.assertEqual(summary["budget"]["spent_calls"], len(inv) * 5)
        self.assertLessEqual(summary["budget"]["spent_calls"], 12)

    def test_cny_breaker(self):
        config = make_config(concurrency=1)
        rows = make_rows(5)
        out = self.tmp / "run_cny"
        inv = []
        # prompt=1000, completion=200, rates 2/8 => cny = (2000+1600)/1e6 = 0.0036 per item
        # max 0.008 => at most 2 items.
        summary = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            max_estimated_cny=0.008,
            reserve_calls=1,
            reserve_cny=0.0036,
            rate_in=2.0,
            rate_out=8.0,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, calls_per_item=1, prompt=1000, completion=200),
        )
        self.assertEqual(summary["status"], "stopped_budget")
        self.assertEqual(summary["budget"]["stop_reason"], "max_estimated_cny")
        self.assertEqual(len(inv), 2)

    def test_reuses_invalid_decision_as_terminal(self):
        config = make_config(concurrency=1)
        rows = make_rows(2)
        out = self.tmp / "run_invdec"
        inv = []

        def runner(candidate, item, services, config):
            inv.append(item["sample_id"])
            return {
                "sample_id": item["sample_id"],
                "status": "invalid_decision",
                "answer": None,
                "usage": {"deepseek_calls": 1, "qwen_calls": 0, "input_tokens": 10, "output_tokens": 5},
            }

        run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=runner,
        )
        inv.clear()
        summary = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=runner,
        )
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(sorted(summary["reused_terminal"]), ["SIM_00", "SIM_01"])
        self.assertEqual(inv, [])

    def test_harness_and_config_fingerprint_stable(self):
        sha1 = harness_tree_sha256(INITIAL_HARNESS)
        sha2 = harness_tree_sha256(INITIAL_HARNESS)
        self.assertEqual(sha1, sha2)
        self.assertEqual(len(sha1), 64)
        for name in INITIAL_FILES:
            self.assertTrue((INITIAL_HARNESS / name).is_file())
        cfg = make_config()
        self.assertEqual(config_fingerprint(cfg), config_fingerprint(copy.deepcopy(cfg)))


if __name__ == "__main__":
    unittest.main()
