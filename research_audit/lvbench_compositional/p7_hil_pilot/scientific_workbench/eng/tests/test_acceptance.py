#!/usr/bin/env python3
"""Engineering acceptance checks for workbench v2."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
JUD = WB / "SCIENTIFIC_JUDGMENTS_DIRECTED_PROGRAMS_CORRECTED_F1_F3.json"
BLANK = WB / "SCIENTIFIC_JUDGMENTS_BLANK.json"
CAT = WB / "WORKBENCH_CATALOG.json"
INDEX = WB / "index.html"
TEMPLATES = WB / "v2" / "templates.js"


class AcceptanceTest(unittest.TestCase):
    def test_judgment_json_unchanged_roundtrip_keys(self):
        raw = JUD.read_text(encoding="utf-8")
        data = json.loads(raw)
        again = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        # lossless key set / values for scientific items
        data2 = json.loads(again)
        self.assertEqual(data["items"], data2["items"])
        # S3 remains 否 from synced correction
        self.assertEqual(data["items"]["P7_R4_S3"]["truly_needs_cross_clip_composition"], "否")

    def test_blank_schema_compatible_with_filled_export_shape(self):
        blank = json.loads(BLANK.read_text(encoding="utf-8"))
        filled = json.loads(JUD.read_text(encoding="utf-8"))
        for wid, fields in blank["items"].items():
            self.assertIn(wid, filled["items"])
            for k in fields:
                self.assertIn(k, filled["items"][wid])

    def test_media_urls_still_present_in_catalog(self):
        cat = json.loads(CAT.read_text(encoding="utf-8"))
        for it in cat["items"]:
            clips = it.get("clips") or {}
            vals = [v for v in clips.values() if isinstance(v, str) and v.endswith(".mp4")]
            self.assertTrue(vals, msg=it["workbench_id"])
            for v in vals:
                self.assertTrue(v.startswith("media/"), msg=v)

    def test_templates_are_reference_only_marker(self):
        text = TEMPLATES.read_text(encoding="utf-8")
        app = (WB / "v2" / "app.js").read_text(encoding="utf-8")
        self.assertIn("REFERENCE_ONLY_NOT_EXPORTED", text)
        self.assertIn("data-reference-template", app)
        self.assertIn("closest(\"[data-reference-template]\")", app)

    def test_index_has_windows_and_single_mode(self):
        html = INDEX.read_text(encoding="utf-8")
        app = (WB / "v2" / "app.js").read_text(encoding="utf-8")
        self.assertIn("窗口 A", html)
        self.assertIn("窗口 B", html)
        self.assertIn("v2/app.js", html)
        self.assertIn("single_window", app)
        self.assertIn("data-form-mode", app)
        self.assertIn("composition", app)

    def test_approved_graphs_do_not_auto_promote_formal_labels(self):
        lib = json.loads((WB / "data" / "PROGRAM_GRAPH_LIBRARY_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(lib["approved_structured_graph_count"], 4)
        approved = [r for r in lib["records"] if r.get("user_confirmation_status") == "USER_APPROVED_STRUCTURED_GRAPH"]
        self.assertEqual(len(approved), 4)
        for r in approved:
            self.assertTrue(r.get("nodes"))
            self.assertFalse(r.get("formal_unseen"))
            self.assertFalse(r.get("formal_gold"))
            self.assertFalse(r.get("formal_seen_train"))
        pending = [r for r in lib["records"] if r.get("user_confirmation_status") == "PENDING_STRUCTURED_CONFIRMATION"]
        for r in pending:
            self.assertEqual(r.get("nodes"), [])
            self.assertEqual(r.get("edges"), [])
            self.assertFalse(r.get("formal_unseen"))
            self.assertFalse(r.get("formal_gold"))


if __name__ == "__main__":
    unittest.main()
