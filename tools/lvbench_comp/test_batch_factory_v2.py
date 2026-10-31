"""Acceptance tests for Track B batch factory V2 (ChatGPT 22214a1 audit)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.lvbench_comp.batch_factory.dedup import apply_semantic_dedup, n_distinct_questions
from tools.lvbench_comp.batch_factory.extract_events import CURATED, NEW_FRAME_OBSERVATIONS
from tools.lvbench_comp.batch_factory.fact_binding import validate_fact_binding
from tools.lvbench_comp.batch_factory.human_packets import assert_blind_packet_integrity, build_packet
from tools.lvbench_comp.batch_factory.provenance import annotate_event, count_by_provenance
from tools.lvbench_comp.batch_factory.qa_draft import draft_qa
from tools.lvbench_comp.batch_factory.relations import mine_relations


RUN001 = Path("research_audit/lvbench_compositional/track_b/batch_factory/run_001")


class TestBatchFactoryV2(unittest.TestCase):
    def test_duplicate_question_run001_pairs(self) -> None:
        drafts = [json.loads(l) for l in (RUN001 / "qa_drafts.jsonl").read_text().splitlines() if l.strip()]
        # Simulate V2 dedup on historical drafts
        out = apply_semantic_dedup(drafts)
        by_id = {d["qa_id"]: d for d in out}
        self.assertTrue(by_id["QA_DRAFT_0005"].get("duplicate_of_family") or by_id["QA_DRAFT_0004"].get("duplicate_of_family"))
        self.assertTrue(by_id["QA_DRAFT_0007"].get("duplicate_of_family") or by_id["QA_DRAFT_0006"].get("duplicate_of_family"))
        self.assertLessEqual(n_distinct_questions(out), 6)

    def test_event_qa_alignment_0005(self) -> None:
        drafts = [json.loads(l) for l in (RUN001 / "qa_drafts.jsonl").read_text().splitlines() if l.strip()]
        events = [json.loads(l) for l in (RUN001 / "event_graphs.jsonl").read_text().splitlines() if l.strip()]
        events_by_id = {e["event_id"]: e for e in events}
        d5 = next(d for d in drafts if d["qa_id"] == "QA_DRAFT_0005")
        rep = validate_fact_binding(d5, events_by_id)
        self.assertFalse(rep["ok"])
        self.assertTrue(any("Ndure" in e or "mismatch" in e or "name_not_in" in e for e in rep["errors"]))

    def test_true_blind_packet(self) -> None:
        import tempfile

        drafts = [json.loads(l) for l in (RUN001 / "qa_drafts.jsonl").read_text().splitlines() if l.strip()]
        screened = [json.loads(l) for l in (RUN001 / "qa_auto_screen.jsonl").read_text().splitlines() if l.strip()]
        events = [json.loads(l) for l in (RUN001 / "event_graphs.jsonl").read_text().splitlines() if l.strip()]
        # Mark independent
        for d in drafts:
            d.setdefault("retained_as_independent_sample", True)
            d["duplicate_of_family"] = False
        drafts_by_id = {d["qa_id"]: d for d in drafts}
        screened_by_id = {s["qa_id"]: s for s in screened}
        events_by_id = {e["event_id"]: e for e in events}
        prioritized = [
            {"priority": i + 1, "qa_id": d["qa_id"], "video_id": d["video_id"], "grade": "X", "score": 0.5, "mechanism": d.get("mechanism"), "reason": "t"}
            for i, d in enumerate(drafts[:3])
        ]
        with tempfile.TemporaryDirectory() as td:
            build_packet(
                run_id="test_blind",
                prioritized=prioritized,
                drafts_by_id=drafts_by_id,
                screened_by_id=screened_by_id,
                events_by_id=events_by_id,
                out_dir=Path(td),
            )
            b = json.loads((Path(td) / "B_ONLY_BLIND" / "packet.json").read_text())
            viol = assert_blind_packet_integrity(b)
            self.assertEqual(viol, [], msg=str(viol))
            blob = json.dumps(b)
            self.assertNotIn("provisional_answer_zh", blob)
            self.assertNotIn("auto_grade", blob)
            self.assertNotIn("proxy_necessity", blob)

    def test_provenance_metrics_curated_vs_new(self) -> None:
        curated_n = sum(len(v) for v in CURATED.values())
        self.assertEqual(curated_n, 13)
        new_n = sum(len(v) for v in NEW_FRAME_OBSERVATIONS.values())
        self.assertEqual(new_n, 9)
        # Simulate run_001-like: curated only semantic
        fake = []
        for vid, evs in CURATED.items():
            for e in evs:
                e2 = dict(e)
                e2["from_curated_dict"] = True
                fake.append(annotate_event(e2))
        for i in range(3):
            fake.append(
                annotate_event(
                    {
                        "event_id": f"x{i}",
                        "verb": "visual_sample",
                        "provenance": "FRAME_VISUAL_OBSERVATION",
                        "time_start_s": 0,
                        "time_end_s": 1,
                    }
                )
            )
        c = count_by_provenance(fake)
        self.assertEqual(c["n_curated_semantic_events"], 13)
        self.assertEqual(c["n_new_machine_or_agent_semantic_events"], 0)

    def test_masked_qa_honesty_labels(self) -> None:
        from tools.lvbench_comp.batch_factory.auto_screen import screen_one

        qa = {
            "qa_id": "t",
            "video_id": "v",
            "fact_ids": [],
            "mechanism": "reverse_name_to_early_garment",
            "retained_as_independent_sample": True,
            "answer_status": "ANSWER_PENDING",
            "provisional_answer_zh": "红色外套",
        }
        s = screen_one(qa, {})
        self.assertFalse(s["evidence_tested"])
        self.assertFalse(s["masked_qa_executed"])
        self.assertIn("NOT_VIDEO_TESTED", s["grade"])
        self.assertIn("RULE_PROXY", s["proxy_A_only"]["note"])

    def test_new_observations_without_curated_map(self) -> None:
        """Hardcoded NEW_FRAME_OBSERVATIONS still produce drafts; not proof of auto discovery."""
        events_by_video = {vid: list(evs) for vid, evs in NEW_FRAME_OBSERVATIONS.items()}
        self.assertGreaterEqual(sum(len(v) for v in events_by_video.values()), 1)
        rels = mine_relations(events_by_video)
        self.assertGreaterEqual(len(rels), 1)
        events_by_id = {e["event_id"]: e for evs in events_by_video.values() for e in evs}
        drafts = draft_qa(rels, events_by_id)
        self.assertTrue(any(d.get("from_new_observation") for d in drafts))
        # Post-fix: no both-side location leakage in contrast questions
        for d in drafts:
            if d.get("mechanism") != "cross_scene_attribute_contrast":
                continue
            q = d.get("question_zh") or ""
            self.assertNotIn("snowy_building_exterior", q)
            self.assertNotIn("dark_crystalline_corridor", q)
            self.assertNotIn("indoor_luxury_table", q)
            self.assertFalse(d.get("leakage_error"), msg=d.get("question_leakage"))

    def test_question_side_semantic_leakage_detects_run002_bug(self) -> None:
        from tools.lvbench_comp.batch_factory.leakage import question_side_leakage

        events = {
            "A": {
                "event_id": "A",
                "location": "snowy_building_exterior",
                "object": "kids",
                "verb": "walk",
                "summary_zh": "雪地儿童",
            },
            "B": {
                "event_id": "B",
                "location": "dark_crystalline_corridor",
                "object": "stairs",
                "verb": "show",
                "summary_zh": "晶柱楼梯",
            },
        }
        bad = {
            "mechanism": "cross_scene_attribute_contrast",
            "fact_ids": ["A", "B"],
            "question_zh": "较早在「snowy_building_exterior」与较晚在「dark_crystalline_corridor」有何不同？",
        }
        rep = question_side_leakage(bad, events)
        self.assertFalse(rep["ok"])
        self.assertTrue(rep["both_sides_leaked"])
        good = {
            "mechanism": "cross_scene_attribute_contrast",
            "fact_ids": ["A", "B"],
            "question_zh": "按文件时间顺序观看两段指定片段。两段在可见环境与主要物体上有何不同？",
        }
        self.assertTrue(question_side_leakage(good, events)["ok"])

    def test_metric_aliases_do_not_conflate_provisional_with_verified(self) -> None:
        """Regression: provisional text ≠ independently verified answer."""
        drafts = [
            {"provisional_answer_zh": "foo", "answer_status": "ANSWER_PENDING"},
            {"provisional_answer_zh": "bar", "answer_status": "ANSWER_VERIFIED"},
            {"provisional_answer_zh": "UNKNOWN", "answer_status": "ANSWER_PENDING"},
        ]
        n_prov = sum(
            1 for d in drafts if d.get("provisional_answer_zh") and str(d["provisional_answer_zh"]).upper() != "UNKNOWN"
        )
        n_ver = sum(1 for d in drafts if d.get("answer_status") in {"ANSWER_VERIFIED", "HUMAN_VERIFIED"})
        self.assertEqual(n_prov, 2)
        self.assertEqual(n_ver, 1)
        self.assertNotEqual(n_prov, n_ver)

    def test_distinct_question_texts_not_inflated_by_answers(self) -> None:
        from tools.lvbench_comp.batch_factory.dedup import (
            n_distinct_question_answer_pairs,
            n_distinct_question_texts,
        )

        stem = "按文件时间顺序观看两段指定片段。两段有何不同？"
        drafts = [
            {"question_zh": stem, "provisional_answer_zh": f"ans_{i}"} for i in range(9)
        ]
        self.assertEqual(n_distinct_question_texts(drafts), 1)
        self.assertEqual(n_distinct_question_answer_pairs(drafts), 9)
        # Historical overcount mode must not be used as 'distinct questions'
        self.assertLess(n_distinct_question_texts(drafts), n_distinct_question_answer_pairs(drafts))


if __name__ == "__main__":
    unittest.main()
