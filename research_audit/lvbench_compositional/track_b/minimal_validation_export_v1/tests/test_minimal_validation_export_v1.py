#!/usr/bin/env python3
"""WP1.1 minimal validation export tests (schema, necessity, leak isolation)."""
from __future__ import annotations

import json
import runpy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENG = ROOT / "eng"
SEEN = ["SP001", "SP002", "SP005", "SP201", "SP202"]
UNSEEN = ["P7_VTCD_C2", "P7_TJR_R3"]


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
        cls.scorer = json.loads(
            (ROOT / "projections/scorer_private/answers.json").read_text()
        )

    def test_validation_pass_requires_schema(self):
        self.assertEqual(self.report["status"], "PASS")
        self.assertEqual(self.report["checks"]["schema_validation"], "PASS")
        self.assertNotIn("SKIPPED", str(self.report["checks"].get("schema_engine", "")))
        self.assertEqual(self.report["checks"]["no_false_gold"], "PASS")
        self.assertEqual(self.report["checks"]["join_qa_video"], "PASS")
        self.assertEqual(self.report["checks"]["join_graph_edges"], "PASS")
        self.assertEqual(self.report["checks"]["uniqueness"], "PASS")
        self.assertEqual(self.report["checks"]["inference_safe_leak_scan"], "PASS")

    def test_builtin_schema_engine_runs(self):
        detail = self.report["schema_validation_detail"]
        self.assertEqual(detail["status"], "PASS")
        self.assertTrue(detail["engine"])
        self.assertNotEqual(detail["engine"], "SKIPPED")

    def test_fixed_split_only_7(self):
        ids = [x["item_id"] for x in self.qa["items"]]
        self.assertEqual(ids, SEEN + UNSEEN)
        self.assertEqual(self.split["fixed_seen"], SEEN)
        self.assertEqual(self.split["fixed_unseen"], UNSEEN)

    def test_no_formal_gold(self):
        for it in self.qa["items"]:
            self.assertFalse(it["answer"]["formal_gold"])
            self.assertEqual(
                it["answer"]["answer_certification_status"],
                "HUMAN_REFERENCE_OR_HISTORICAL_NOT_FORMAL_GOLD",
            )
            self.assertFalse(it["gates"]["formal_gold"])
            self.assertFalse(it["gates"]["formal_seen_train"])
            self.assertFalse(it["gates"]["formal_unseen"])

    def test_sp201_sp202_necessity_mapped(self):
        by = {x["item_id"]: x for x in self.qa["items"]}
        for item_id in ("SP201", "SP202"):
            auth = by[item_id]["necessity"]["necessity_authoritative"]
            self.assertIs(auth["a_only_sufficient"], False)
            self.assertIs(auth["b_only_sufficient"], False)
            maps = {m["canonical_field"]: m["mapped_from"] for m in auth["source_field_mappings"]}
            self.assertEqual(maps["a_only_sufficient"], "a_only_sufficient_full_question")
            self.assertEqual(maps["b_only_sufficient"], "b_only_sufficient_full_question")

    def test_p7_authority_human_not_inventory(self):
        by = {x["item_id"]: x for x in self.qa["items"]}
        for item_id in UNSEEN:
            nec = by[item_id]["necessity"]
            auth = nec["necessity_authoritative"]
            self.assertEqual(auth["authority"], "human_judgments_preserved")
            self.assertIs(auth["a_only_sufficient"], False)
            self.assertIs(auth["b_only_sufficient"], False)
            self.assertTrue(nec["conflict"]["inventory_vs_preserved_conflict"])
            inv = nec["provenance_records"]["inventory_single_window_necessity"]
            self.assertTrue(inv["a_only_sufficient"])  # stale inventory retained

    def test_join_keys(self):
        qa = {x["item_id"]: x for x in self.qa["items"]}
        graphs = {x["item_id"]: x for x in self.graphs["graphs"]}
        videos = {x["video_id"]: x for x in self.videos["videos"]}
        self.assertEqual(set(qa), set(graphs))
        for item_id, row in qa.items():
            self.assertIn(row["video_id"], videos)
            g = graphs[item_id]
            nids = {n["node_id"] for n in g["nodes"]}
            for e in g["edges"]:
                self.assertIn(e["from_node"], nids)
                self.assertIn(e["to_node"], nids)

    def test_graph_counts(self):
        total_n = sum(g["n_nodes"] for g in self.graphs["graphs"])
        total_e = sum(g["n_edges"] for g in self.graphs["graphs"])
        self.assertEqual(total_n, 40)
        self.assertEqual(total_e, 35)

    def test_p7_windows_blocked(self):
        for it in self.qa["items"]:
            if it["item_id"] in UNSEEN:
                self.assertEqual(
                    it["windows"]["status"], "UNKNOWN_PENDING_SOURCE_SECOND_MAPPING"
                )
                self.assertIsNone(it["windows"]["A"])
                self.assertEqual(
                    it["windows"]["evaluation_gates"]["fixed_ab_window_eval"], "BLOCKED"
                )
        self.assertEqual(
            set(self.win["blocked_fixed_ab_window_eval"]), set(UNSEEN)
        )

    def test_language_distribution_reported(self):
        for i in SEEN:
            self.assertEqual(self.lang["per_item"][i]["question_language"], "en")
        for i in UNSEEN:
            self.assertEqual(self.lang["per_item"][i]["question_language"], "zh")
        issues = [
            n.get("issue")
            for n in self.lang["c2_name_abbreviation_constraint"]["nodes"]
            if n.get("issue")
        ]
        self.assertTrue(any("ReadNameAbbreviationGraphic" in (x or "") for x in issues))

    def test_inference_safe_withholds_answers(self):
        for it in self.inf_qa["items"]:
            self.assertEqual(it["answer"]["status"], "WITHHELD_INFERENCE_SAFE")
            self.assertNotIn("answer_text", it["answer"])
        for ans in self.scorer["items"]:
            self.assertIn("answer_text", ans)

    def test_inference_safe_omits_unseen_graphs(self):
        ids = {g["item_id"] for g in self.inf_graphs["graphs"]}
        self.assertEqual(ids, set(SEEN))
        for uid in UNSEEN:
            self.assertNotIn(uid, ids)
        self.assertEqual(self.inf_graphs["omitted_unseen_item_ids"], UNSEEN)

    def test_inference_safe_redacts_answer_outputs(self):
        blob = json.dumps(self.inf_graphs)
        self.assertNotIn("answer_sister", blob)
        self.assertNotIn('"on_screen_text"', blob)
        for g in self.inf_graphs["graphs"]:
            for n in g["nodes"]:
                outs = list(n.get("raw_outputs") or []) + list(
                    n.get("normalized_outputs") or []
                )
                for o in outs:
                    if isinstance(o, str) and o.lower().startswith("answer"):
                        self.assertEqual(o, "__REDACTED_ANSWER_BEARING__")

    def test_necessity_diff_report_exists(self):
        self.assertEqual(len(self.nec_diff["items"]), 7)
        by = {x["item_id"]: x for x in self.nec_diff["items"]}
        self.assertTrue(by["P7_VTCD_C2"]["conflict"]["inventory_vs_preserved_conflict"])

    def test_readme_and_change_list(self):
        self.assertTrue((ROOT / "README.md").is_file())
        self.assertTrue((ROOT / "CHANGE_LIST_WP1_1.md").is_file())
        self.assertTrue((ROOT / "schemas" / "qa_items.schema.json").is_file())


if __name__ == "__main__":
    unittest.main()
