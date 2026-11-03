#!/usr/bin/env python3
"""Acceptance tests for Seen Human Annotation Pilot run_001 (engineering only)."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
PILOT = WB / "seen_pilot_run_001"
sys.path.insert(0, str(WB / "eng"))

from seen_pilot_isolation import (  # noqa: E402
    assert_seen_pilot_isolation,
    historical_train_label_does_not_certify,
    media_unavailable_not_reviewed,
)


class SeenPilotRun001Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.exclusion = json.loads((PILOT / "EXCLUSION_LIST.json").read_text(encoding="utf-8"))
        cls.isolation = json.loads((PILOT / "ISOLATION_CHECK.json").read_text(encoding="utf-8"))
        cls.catalog = json.loads((PILOT / "CATALOG.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((PILOT / "MANIFEST.json").read_text(encoding="utf-8"))
        cls.blank = json.loads((PILOT / "JUDGMENTS_BLANK.json").read_text(encoding="utf-8"))
        cls.approved_lib = json.loads((WB / "data" / "PROGRAM_GRAPH_LIBRARY_v1.json").read_text(encoding="utf-8"))

    def test_count_in_range_and_isolation_pass(self):
        n = len(self.catalog["items"])
        self.assertGreaterEqual(n, 4)
        self.assertLessEqual(n, 6)
        self.assertEqual(self.isolation["status"], "PASS")
        self.assertEqual(self.isolation["hard_exclude_video_leakage"], [])
        self.assertEqual(self.isolation["hard_exclude_uid_leakage"], [])

    def test_block_unseen_or_test_video_in_seen_candidates(self):
        hard_v = set(self.exclusion["hard_exclude_videos"])
        hard_u = set(self.exclusion["hard_exclude_qa_uids"])
        # Inject a known Unseen/approved video → must BLOCK
        poisoned = list(self.catalog["items"]) + [
            {
                "workbench_id": "POISON",
                "video_id": "LLSJrEgOOtw",
                "qa_uid": "P7_R4_F2",
                "user_confirmation_status": "PENDING_HUMAN_VIDEO_REVIEW",
                "formal_seen_train": False,
                "formal_gold": False,
                "train_exposed": False,
            }
        ]
        res = assert_seen_pilot_isolation(
            catalog_items=poisoned,
            hard_exclude_videos=hard_v,
            hard_exclude_uids=hard_u,
        )
        self.assertEqual(res["status"], "BLOCK")
        self.assertTrue(any("LLSJrEgOOtw" in i for i in res["issues"]))

        clean = assert_seen_pilot_isolation(
            catalog_items=self.catalog["items"],
            hard_exclude_videos=hard_v,
            hard_exclude_uids=hard_u,
        )
        self.assertEqual(clean["status"], "PASS")

    def test_old_train_label_does_not_certify_formal_seen(self):
        for it in self.catalog["items"]:
            pack = json.loads((WB / it["pack_path"]).read_text(encoding="utf-8"))
            self.assertTrue(pack["historical_train_label_present"])
            self.assertEqual(pack["historical_train_label_status"], "HISTORICAL_CANDIDATE_ONLY_NOT_FORMAL_SEEN")
            self.assertFalse(pack["formal_seen_train"])
            self.assertIn(
                pack["user_confirmation_status"],
                {"PENDING_HUMAN_VIDEO_REVIEW", "SCIENTIFIC_REVIEW_INGESTED"},
            )
            self.assertFalse(pack.get("formal_seen_train"))
            # Simulated wrong upgrade must fail helper
            bad = dict(pack, formal_seen_train=True)
            self.assertFalse(historical_train_label_does_not_certify(bad))

    def test_media_unavailable_not_shown_reviewed(self):
        fake = {
            "media_status": "MEDIA_UNAVAILABLE",
            "human_reviewed": True,
            "review_completed": True,
        }
        self.assertFalse(media_unavailable_not_reviewed(fake))
        for it in self.catalog["items"]:
            self.assertIn(it["media_status"], {"OK", "MEDIA_UNAVAILABLE"})
            if it["media_status"] == "MEDIA_UNAVAILABLE":
                self.assertNotEqual(it.get("human_reviewed"), True)
            else:
                # OK media exists on disk
                for side in ("A", "B"):
                    rel = it["clips"][side]
                    self.assertTrue((WB / rel).exists(), rel)

    def test_manifest_sha_matches(self):
        for entry in self.manifest["files"]:
            p = WB / entry["relpath"]
            self.assertTrue(p.exists(), entry["relpath"])
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(h, entry["sha256"])
        for name, digest in self.manifest["pack_json_sha256"].items():
            p = PILOT / "review_packs" / name
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), digest)

    def test_does_not_overwrite_approved_graphs(self):
        approved = [
            r
            for r in self.approved_lib["records"]
            if r.get("user_confirmation_status") == "USER_APPROVED_STRUCTURED_GRAPH"
        ]
        self.assertEqual(len(approved), 4)
        for r in approved:
            self.assertTrue(r.get("nodes"))
            self.assertFalse(r.get("formal_unseen"))
        # Seen pilot IDs must not collide with approved qa_uids
        pilot_uids = {i["qa_uid"] for i in self.catalog["items"]}
        approved_uids = {r["qa_uid"] for r in approved}
        self.assertEqual(pilot_uids & approved_uids, set())

    def test_json_roundtrip_preserves_user_fields(self):
        # Use judgment_io semantics
        sys.path.insert(0, str(WB / "v2"))
        # Load via node if available; else python reimplementation check
        original = json.loads(json.dumps(self.blank))
        edited_id = next(iter(original["items"]))
        form = {edited_id: {"events": "USER_EVENT_NOTE"}}
        import os
        import subprocess
        import tempfile

        script = f"""
const IO = require({json.dumps(str(WB / 'v2' / 'judgment_io.js'))});
const original = {json.dumps(original)};
const formItems = {json.dumps(form)};
const exported = IO.buildExportPayload({{ imported: original, formItems, nowIso: '2026-11-02T00:00:00Z' }});
const check = IO.assertRoundTripFidelity({{
  original,
  exported,
  editedId: {json.dumps(edited_id)},
  editedField: 'events',
  editedValue: 'USER_EVENT_NOTE'
}});
if (!check.ok) {{ console.error(check.issues); process.exit(1); }}
if (exported.items[{json.dumps(edited_id)}].pilot_unknown_keep !== 'PRESERVE_ON_ROUNDTRIP') process.exit(2);
if (exported.items[{json.dumps(edited_id)}].a_only_sufficient !== original.items[{json.dumps(edited_id)}].a_only_sufficient) process.exit(3);
// second edit pass: update another field without losing first
const exported2 = IO.buildExportPayload({{
  imported: exported,
  formItems: {{ [{json.dumps(edited_id)}]: {{ directed_program_draft: 'Identify → Bind → Query' }} }},
  nowIso: '2026-11-02T00:00:01Z'
}});
if (exported2.items[{json.dumps(edited_id)}].events !== 'USER_EVENT_NOTE') process.exit(4);
if (exported2.items[{json.dumps(edited_id)}].directed_program_draft !== 'Identify → Bind → Query') process.exit(5);
if (exported2.items[{json.dumps(edited_id)}].pilot_unknown_keep !== 'PRESERVE_ON_ROUNDTRIP') process.exit(6);
console.log('OK');
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
            path = f.name
        try:
            r = subprocess.run(["node", path], capture_output=True, text=True, check=False)
        finally:
            os.unlink(path)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("OK", r.stdout)

    def test_ui_markers_present(self):
        index = (WB / "index.html").read_text(encoding="utf-8")
        self.assertIn("seen-pilot", index)
        self.assertIn("Seen Pilot", index)
        app = (WB / "v2" / "app.js").read_text(encoding="utf-8")
        self.assertIn("seen_pilot_run_001", app)
        self.assertIn("PENDING_HUMAN_VIDEO_REVIEW", app)
        self.assertIn("renderSeenPilotPane", app)


if __name__ == "__main__":
    unittest.main()
