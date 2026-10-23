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

from batch_billing import DEFAULT_MODEL_RATES, usage_from_result
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
                "deepseek": {"request_model": "DeepSeek-V4-Pro-0813", "max_tokens": 128},
                "qwen": {"request_model": "Qwen3.6-Plus", "max_tokens": 128},
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


def meter_result(sid, *, ds_prompt=1000, ds_out=50, qw_prompt=2000, qw_out=100, ds_cached=0, fail_qwen=False):
    events = [
        {
            "kind": "provider",
            "role": "deepseek",
            "status": "ok",
            "usage": {
                "prompt_tokens": ds_prompt,
                "completion_tokens": ds_out,
                "prompt_tokens_details": {"cached_tokens": ds_cached},
            },
        }
    ]
    if fail_qwen:
        events.append({"kind": "provider", "role": "qwen", "status": "error", "usage": {}})
    else:
        events.append(
            {
                "kind": "provider",
                "role": "qwen",
                "status": "ok",
                "usage": {"prompt_tokens": qw_prompt, "completion_tokens": qw_out},
            }
        )
    return {
        "sample_id": sid,
        "status": "answered",
        "answer": "A",
        "usage": {
            "deepseek_calls": 1,
            "qwen_calls": 1,
            "input_tokens": ds_prompt + qw_prompt,
            "output_tokens": ds_out + qw_out,
        },
        "meter_events": events,
    }


def make_mock_runner(invocations, *, delay=0.0, fail_ids=None, fail_qwen_ids=None):
    fail_ids = set(fail_ids or [])
    fail_qwen_ids = set(fail_qwen_ids or [])
    lock = threading.Lock()

    def runner(candidate, item, services, config):
        sid = item["sample_id"]
        with lock:
            invocations.append(sid)
        if delay:
            time.sleep(delay)
        if sid in fail_ids:
            raise RuntimeError("forced fail for " + sid)
        return meter_result(sid, fail_qwen=sid in fail_qwen_ids)

    return runner


class BillingUnitTests(unittest.TestCase):
    def test_no_double_count_meter_and_usage(self):
        result = meter_result("X")
        # Inflate aggregate usage far beyond meters — must ignore aggregate.
        result["usage"]["input_tokens"] = 10_000_000
        result["usage"]["output_tokens"] = 10_000_000
        u = usage_from_result(result, apply_cache=False)
        self.assertEqual(u["source"], "meter_events")
        self.assertEqual(u["prompt_tokens"], 3000)
        self.assertEqual(u["completion_tokens"], 150)
        # deepseek: 1000*9 + 50*27 = 9000+1350=10350 / 1e6
        # qwen: 2000*4 + 100*24 = 8000+2400=10400 / 1e6
        self.assertAlmostEqual(u["estimated_cny"], (10350 + 10400) / 1e6, places=9)

    def test_cache_discount_only_when_logged(self):
        result = meter_result("X", ds_cached=500)
        u_cache = usage_from_result(result, apply_cache=True)
        u_plain = usage_from_result(result, apply_cache=False)
        self.assertLess(u_cache["estimated_cny"], u_plain["estimated_cny"])
        # cached portion billed at 0.3 instead of 9
        self.assertAlmostEqual(
            u_plain["estimated_cny"] - u_cache["estimated_cny"],
            500 * (9.0 - 0.3) / 1e6,
            places=9,
        )

    def test_missing_usage_marks_undercount(self):
        result = meter_result("X", fail_qwen=True)
        u = usage_from_result(result)
        self.assertTrue(u["undercount_risk"])
        self.assertEqual(u["by_role"]["qwen"]["missing_usage_calls"], 1)
        # Only deepseek tokens billed
        self.assertEqual(u["by_role"]["qwen"]["prompt_tokens"], 0)


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
            reserve_calls=2,
            reserve_cny=0.05,
            services_factory=FakeServices,
            runner=make_mock_runner(inv),
        )
        self.assertEqual(summary1["status"], "completed")
        self.assertEqual(sorted(inv), sorted(r["sample_id"] for r in rows))

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
            reserve_calls=2,
            reserve_cny=0.05,
            services_factory=FakeServices,
            runner=make_mock_runner(inv),
        )
        self.assertEqual(summary2["status"], "completed")
        self.assertEqual(sorted(summary2["reused_terminal"]), ["SIM_00", "SIM_01", "SIM_02"])
        self.assertEqual(sorted(summary2["newly_run"]), ["SIM_03", "SIM_04"])
        self.assertEqual(sorted(inv), ["SIM_03", "SIM_04"])
        # Prior spend credited into ledger
        self.assertGreater(summary2["budget"]["spent_estimated_cny"], 0)
        self.assertEqual(summary2["budget"]["by_role"]["deepseek"]["calls"], 5)
        self.assertEqual(summary2["budget"]["by_role"]["qwen"]["calls"], 5)

    def test_fingerprint_mismatch_config_model(self):
        config = make_config()
        rows = make_rows(3)
        out = self.tmp / "run_cfg"
        run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=make_mock_runner([]),
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
        with self.assertRaises(BatchFingerprintError):
            run_batch_checkpoint(
                config,
                INITIAL_HARNESS,
                other,
                out,
                services_factory=FakeServices,
                runner=make_mock_runner([]),
            )

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
        path = out / "items" / "000000.json"
        data = read_json(path)
        data["sample_id"] = "WRONG"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(BatchFingerprintError):
            run_batch_checkpoint(
                config,
                INITIAL_HARNESS,
                rows,
                out,
                services_factory=FakeServices,
                runner=make_mock_runner([]),
            )

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

    def test_budget_cny_breaker_per_model(self):
        config = make_config(concurrency=1)
        rows = make_rows(6)
        out = self.tmp / "run_budget"
        inv = []
        # Each item ≈ 0.02075 CNY no-cache with meter_result defaults
        summary = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            max_estimated_cny=0.045,
            reserve_calls=2,
            reserve_cny=0.021,
            apply_cache=False,
            services_factory=FakeServices,
            runner=make_mock_runner(inv),
        )
        self.assertEqual(summary["status"], "stopped_budget")
        self.assertEqual(summary["budget"]["stop_reason"], "max_estimated_cny")
        self.assertLessEqual(len(inv), 2)
        self.assertIn("deepseek", summary["budget"]["by_role"])
        self.assertIn("qwen", summary["budget"]["by_role"])

        inv.clear()
        summary2 = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            max_estimated_cny=0.045,
            reserve_calls=2,
            reserve_cny=0.021,
            apply_cache=False,
            services_factory=FakeServices,
            runner=make_mock_runner(inv),
        )
        self.assertEqual(inv, [])
        self.assertEqual(summary2["status"], "stopped_budget")

    def test_failed_request_undercount_flag(self):
        config = make_config(concurrency=1)
        rows = make_rows(2)
        out = self.tmp / "run_fail"
        inv = []
        summary = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, fail_qwen_ids={"SIM_00", "SIM_01"}),
        )
        self.assertEqual(summary["status"], "completed")
        self.assertTrue(summary["budget"]["undercount_risk"])
        self.assertEqual(summary["budget"]["missing_usage_calls"], 2)

    def test_concurrent_overshoot_bounded_by_reserves(self):
        config = make_config(concurrency=3)
        rows = make_rows(10)
        out = self.tmp / "run_conc"
        inv = []
        summary = run_batch_checkpoint(
            config,
            INITIAL_HARNESS,
            rows,
            out,
            max_estimated_cny=0.05,
            reserve_calls=2,
            reserve_cny=0.025,
            apply_cache=False,
            services_factory=FakeServices,
            runner=make_mock_runner(inv, delay=0.03),
        )
        self.assertEqual(summary["status"], "stopped_budget")
        # At most floor(0.05/0.025)=2 concurrent reserves
        self.assertLessEqual(len(inv), 2)

    def test_reuses_invalid_decision_as_terminal(self):
        config = make_config(concurrency=1)
        rows = make_rows(2)
        out = self.tmp / "run_invdec"
        inv = []

        def runner(candidate, item, services, config):
            inv.append(item["sample_id"])
            r = meter_result(item["sample_id"])
            r["status"] = "invalid_decision"
            r["answer"] = None
            return r

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
        self.assertEqual(inv, [])

    def test_harness_and_config_fingerprint_stable(self):
        sha1 = harness_tree_sha256(INITIAL_HARNESS)
        sha2 = harness_tree_sha256(INITIAL_HARNESS)
        self.assertEqual(sha1, sha2)
        for name in INITIAL_FILES:
            self.assertTrue((INITIAL_HARNESS / name).is_file())
        cfg = make_config()
        self.assertEqual(config_fingerprint(cfg), config_fingerprint(copy.deepcopy(cfg)))
        self.assertEqual(DEFAULT_MODEL_RATES["deepseek"]["rate_in"], 9.0)
        self.assertEqual(DEFAULT_MODEL_RATES["qwen"]["rate_out"], 24.0)


if __name__ == "__main__":
    unittest.main()
