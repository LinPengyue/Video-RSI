#!/usr/bin/env python3
"""WP1.2 tests: isolation, whitelist, and negative leak injection."""
from __future__ import annotations

import json
import runpy
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENG = ROOT / "eng"
SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]
UNSEEN = ["P7_VTCD_C2", "P7_TJR_R3"]

sys.path.insert(0, str(ENG))
from inference_access import (  # noqa: E402
    InferenceAccessError,
    resolve_allowed_path,
)
from build_minimal_validation_export_v1 import (  # noqa: E402
    leak_scan_inference_safe,
)


class TestMinimalValidationExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old = sys.argv
        try:
            sys.argv = [str(ENG / "build_minimal_validation_export_v1.py")]
            runpy.run_path(
                str(ENG / "build_minimal_validation_export_v1.py"), run_name="__main__"
            )
        finally:
            sys.argv = old
        cls.qa = json.loads((ROOT / "qa_items.json").read_text())
        cls.graphs = json.loads((ROOT / "program_graphs.json").read_text())
        cls.videos = json.loads((ROOT / "video_manifest.json").read_text())
        cls.split = json.loads((ROOT / "split_manifest.json").read_text())
        cls.report = json.loads((ROOT / "VALIDATION_REPORT.json").read_text())
        cls.nec_diff = json.loads((ROOT / "NECESSITY_DIFF_REPORT.json").read_text())
        cls.win = json.loads((ROOT / "WINDOW_AVAILABILITY_REPORT.json").read_text())
        cls.lang = json.loads(
            (ROOT / "LANGUAGE_AND_STRUCTURE_LIMITS_REPORT.json").read_text()
        )
        cls.inf_qa = json.loads(
            (ROOT / "projections/inference_safe/qa_items.json").read_text()
        )
        cls.inf_graphs = json.loads(
            (
                ROOT / "projections/inference_safe/program_graphs_seen_redacted.json"
            ).read_text()
        )
        cls.inf_split = json.loads(
            (ROOT / "projections/inference_safe/split_manifest.json").read_text()
        )
        cls.scorer = json.loads(
            (ROOT / "projections/scorer_private/answers.json").read_text()
        )
        cls.eval_meta = json.loads(
            (ROOT / "projections/scorer_private/eval_private_metadata.json").read_text()
        )
        cls.inf_root = ROOT / "projections" / "inference_safe"

    def test_validation_pass_requires_schema(self):
        self.assertEqual(self.report["status"], "PASS")
        self.assertEqual(self.report["checks"]["schema_validation"], "PASS")
        self.assertNotIn("SKIPPED", str(self.report["checks"].get("schema_engine", "")))
        self.assertEqual(self.report["checks"]["inference_safe_leak_scan"], "PASS")
        self.assertEqual(self.report["checks"]["necessity_authoritative"], "PASS")
        self.assertEqual(self.report["checks"]["p7_window_eval_blocked"], "PASS")

    def test_scientific_audit_unchanged_has_full_unseen_structure(self):
        by = {x["item_id"]: x for x in self.split["items"]}
        for uid in UNSEEN:
            labels = by[uid]["structure_labels"]
            self.assertIn("layer1_families_normalized", labels)
            self.assertIn("n_nodes", labels)

    def test_inference_split_withholds_unseen_structure(self):
        by = {x["item_id"]: x for x in self.inf_split["items"]}
        for uid in UNSEEN:
            labels = by[uid]["structure_labels"]
            self.assertEqual(labels["status"], "WITHHELD_FROM_INFERENCE")
            self.assertNotIn("layer1_families_normalized", labels)
            self.assertNotIn("layer2_atoms_normalized", labels)
            self.assertNotIn("n_nodes", labels)
            self.assertNotIn("n_edges", labels)
        for sid in SEEN:
            self.assertIn("layer1_families_normalized", by[sid]["structure_labels"])

    def test_necessity_not_in_inference_qa(self):
        for it in self.inf_qa["items"]:
            self.assertNotIn("necessity_authoritative", it)
            self.assertEqual(it["necessity"]["status"], "WITHHELD_SCORER_PRIVATE")
            self.assertNotIn("a_only_sufficient", json.dumps(it))
        for row in self.eval_meta["items"]:
            self.assertIn("necessity_authoritative", row)
            self.assertIn("a_only_sufficient", row["necessity_authoritative"])

    def test_whitelist_allows_only_inference_files(self):
        p = resolve_allowed_path(self.inf_root, "qa_items.json")
        self.assertTrue(p.is_file())
        with self.assertRaises(InferenceAccessError):
            resolve_allowed_path(self.inf_root, "../scorer_private/answers.json")
        with self.assertRaises(InferenceAccessError):
            resolve_allowed_path(self.inf_root, "../../qa_items.json")
        with self.assertRaises(InferenceAccessError):
            resolve_allowed_path(self.inf_root, "../../program_graphs.json")
        with self.assertRaises(InferenceAccessError):
            resolve_allowed_path(
                self.inf_root, "../scorer_private/eval_private_metadata.json"
            )

    def test_negative_inject_unseen_structure_fails(self):
        split_path = self.inf_root / "split_manifest.json"
        original = split_path.read_text()
        try:
            doc = json.loads(original)
            for row in doc["items"]:
                if row["item_id"] == "P7_VTCD_C2":
                    row["structure_labels"] = {
                        "layer1_families_normalized": ["EVENT_DETECTION"],
                        "layer2_atoms_normalized": ["DetectActionEvent"],
                        "n_nodes": 5,
                        "n_edges": 4,
                    }
            split_path.write_text(json.dumps(doc, indent=2) + "\n")
            issues = leak_scan_inference_safe(self.inf_root, self.scorer["items"])
            codes = {i["code"] for i in issues}
            self.assertTrue(
                codes
                & {
                    "UNSEEN_STRUCTURE_LABEL_LEAK",
                    "UNSEEN_STRUCTURE_OPERATOR_OR_SIZE_LEAK",
                },
                msg=issues,
            )
        finally:
            split_path.write_text(original)

    def test_negative_inject_unseen_graph_fails(self):
        gpath = self.inf_root / "program_graphs_seen_redacted.json"
        original = gpath.read_text()
        try:
            doc = json.loads(original)
            full = {g["item_id"]: g for g in self.graphs["graphs"]}
            doc["graphs"].append(deepcopy(full["P7_VTCD_C2"]))
            gpath.write_text(json.dumps(doc, indent=2) + "\n")
            issues = leak_scan_inference_safe(self.inf_root, self.scorer["items"])
            codes = {i["code"] for i in issues}
            self.assertTrue(
                codes & {"UNSEEN_GRAPH_PRESENT", "UNSEEN_GRAPH_LEAK"}, msg=issues
            )
        finally:
            gpath.write_text(original)

    def test_negative_inject_answer_fails(self):
        qpath = self.inf_root / "qa_items.json"
        original = qpath.read_text()
        try:
            doc = json.loads(original)
            doc["items"][0]["answer"] = {
                "status": "LEAKED",
                "answer_text": self.scorer["items"][0]["answer_text"],
            }
            qpath.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
            issues = leak_scan_inference_safe(self.inf_root, self.scorer["items"])
            self.assertTrue(any(i["code"] == "ANSWER_LEAK" for i in issues), msg=issues)
        finally:
            qpath.write_text(original)

    def test_negative_inject_necessity_fails(self):
        qpath = self.inf_root / "qa_items.json"
        original = qpath.read_text()
        try:
            doc = json.loads(original)
            doc["items"][0]["necessity_authoritative"] = {
                "a_only_sufficient": False,
                "b_only_sufficient": False,
            }
            qpath.write_text(json.dumps(doc, indent=2) + "\n")
            issues = leak_scan_inference_safe(self.inf_root, self.scorer["items"])
            self.assertTrue(
                any(i["code"] == "NECESSITY_LABEL_LEAK" for i in issues), msg=issues
            )
        finally:
            qpath.write_text(original)

    def test_fixed_split_only_7(self):
        ids = [x["item_id"] for x in self.qa["items"]]
        self.assertEqual(ids, SEEN + UNSEEN)

    def test_no_formal_gold(self):
        for it in self.qa["items"]:
            self.assertFalse(it["answer"]["formal_gold"])
            self.assertFalse(it["gates"]["formal_gold"])

    def test_sp201_sp202_necessity_mapped(self):
        by = {x["item_id"]: x for x in self.qa["items"]}
        for item_id in ("SP201", "SP202"):
            auth = by[item_id]["necessity"]["necessity_authoritative"]
            self.assertIs(auth["a_only_sufficient"], False)
            self.assertIs(auth["b_only_sufficient"], False)

    def test_p7_windows_blocked(self):
        for it in self.qa["items"]:
            if it["item_id"] in UNSEEN:
                self.assertEqual(
                    it["windows"]["evaluation_gates"]["fixed_ab_window_eval"], "BLOCKED"
                )

    def test_language_distribution_reported(self):
        for i in SEEN:
            self.assertEqual(self.lang["per_item"][i]["question_language"], "en")
        for i in UNSEEN:
            self.assertEqual(self.lang["per_item"][i]["question_language"], "zh")

    def test_change_list_wp12(self):
        self.assertTrue((ROOT / "CHANGE_LIST_WP1_2.md").is_file())


if __name__ == "__main__":
    unittest.main()
