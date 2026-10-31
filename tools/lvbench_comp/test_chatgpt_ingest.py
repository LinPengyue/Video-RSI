"""Tests for ChatGPT still-frame event validation and normalization."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.lvbench_comp.batch_factory.chatgpt_ingest import (
    ingest_chatgpt_events_file,
    normalize_chatgpt_event,
    validate_chatgpt_events,
)
from tools.lvbench_comp.batch_factory.relations import mine_relations


class TestChatGPTIngest(unittest.TestCase):
    def test_pilot_events_file_validates(self) -> None:
        path = Path(
            "research_audit/lvbench_compositional/track_b/batch_factory/"
            "chatgpt_frame_production_pilot_2026-10-31/events_CHATGPT_FRAME_OBSERVATION.jsonl"
        )
        man = Path(
            "research_audit/lvbench_compositional/track_b/batch_factory/"
            "chatgpt_frame_production_pilot_2026-10-31/batch_manifest.json"
        )
        if not path.exists():
            self.skipTest("pilot events not present")
        report = ingest_chatgpt_events_file(path, manifest_path=man)
        self.assertEqual(report["n_accepted"], 12)
        self.assertEqual(report["n_rejected"], 0)
        self.assertEqual(len(report["normalized_events"]), 12)
        for ev in report["normalized_events"]:
            self.assertEqual(ev["provenance_tier"], "CHATGPT_FRAME_OBSERVATION")
            self.assertTrue(ev["is_still_frame_observation"])
            self.assertFalse(ev.get("is_continuous_video_event"))
            self.assertFalse(ev.get("video_motion_verified"))
            self.assertTrue(ev["is_newly_discovered_semantic"])

    def test_reject_duplicate_event_id(self) -> None:
        row = {
            "event_id": "E1",
            "video_id": "vid",
            "time_span": {"start_s": 1.0, "end_s": 1.0},
            "action_or_state": "x",
            "evidence_paths": [],
            "observed_vs_inferred": "observed",
            "uncertainty": "u",
            "provenance": "CHATGPT_FRAME_OBSERVATION",
        }
        # missing file → reject; also duplicate id
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f.jpg"
            p.write_bytes(b"abc")
            row["evidence_paths"] = [str(p)]
            row2 = dict(row)
            rep = validate_chatgpt_events([row, row2])
            self.assertEqual(rep["n_accepted"], 1)
            self.assertEqual(rep["n_rejected"], 1)

    def test_still_relations_are_consecutive_not_all_pairs(self) -> None:
        evs = []
        for i, t in enumerate([10.0, 20.0, 30.0, 40.0]):
            evs.append(
                normalize_chatgpt_event(
                    {
                        "event_id": f"E{i}",
                        "video_id": "Mcggugol2ts",
                        "time_span": {"start_s": t, "end_s": t},
                        "actor": None,
                        "action_or_state": f"scene {i} street" if i % 2 == 0 else f"scene {i} indoor plate",
                        "object": f"obj{i}",
                        "evidence_paths": ["x"],
                        "observed_vs_inferred": "observed",
                        "uncertainty": "u",
                        "provenance": "CHATGPT_FRAME_OBSERVATION",
                        "evidence_modality": "single_static_frame",
                    }
                )
            )
        # Bypass file checks by normalizing directly
        rels = mine_relations({"Mcggugol2ts": evs})
        still_rels = [r for r in rels if r["type"] == "still_ordered_setting_contrast"]
        # 4 stills → 3 consecutive pairs (not C(4,2)=6)
        self.assertEqual(len(still_rels), 3)
        cross = [r for r in rels if r["type"] == "cross_scene_attribute_contrast"]
        self.assertEqual(len(cross), 0)


if __name__ == "__main__":
    unittest.main()
