#!/usr/bin/env python3
"""Checks for LVBench compositional QA v0 candidate construction."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.lvbench_comp.build_comp_qa import (
    REQUIRED_FIELDS,
    REVIEW_STATUS,
    build_candidates,
    load_qas,
    validate_candidate,
)


OFFICIAL = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")


def _qa(uid: str, question: str, answer: str, reference: str) -> dict:
    return {
        "uid": uid,
        "question": question,
        "answer": answer,
        "time_reference": reference,
        "question_type": "synthetic",
    }


def _write(rows: list[dict]) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
    for row in rows:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    handle.close()
    return Path(handle.name)


class BuildCompQaTest(unittest.TestCase):
    def test_name_pair_replaces_the_name(self) -> None:
        path = _write(
            [
                {
                    "key": "vid",
                    "qa": [
                        _qa(
                            "1",
                            "What is the name of the elder who joins the vlogger on their travel?\n"
                            "(A) Mikhail\n(B) Eric",
                            "A",
                            "04:44-04:44",
                        ),
                        _qa(
                            "2",
                            "Where do the vlogger team members invite Mikhail on the first night?\n"
                            "(A) They invite Mikhail to the park\n"
                            "(B) They invite Mikhail to the hotel",
                            "B",
                            "15:58-16:07",
                        ),
                    ],
                }
            ]
        )
        records = load_qas(path)
        candidates = build_candidates(records)
        self.assertEqual(len(candidates), 1)
        item = candidates[0]
        self.assertEqual(item["composition_type"], "entity_binding")
        self.assertEqual(item["source_uids"], ["1", "2"])
        self.assertIn("hotel", item["new_answer"])
        self.assertNotIn("Mikhail", item["new_question"])
        self.assertNotIn("Mikhail", item["new_answer"])
        self.assertEqual(item["review_status"], REVIEW_STATUS)
        self.assertEqual(validate_candidate(item, records), [])

    def test_shared_keywords_do_not_qualify(self) -> None:
        path = _write(
            [
                {
                    "key": "vid",
                    "qa": [
                        _qa(
                            "1",
                            "What does the man do in the video?\n(A) He walks\n(B) He sits",
                            "A",
                            "01:00-01:10",
                        ),
                        _qa(
                            "2",
                            "Where is the man in the video?\n(A) The park\n(B) The room",
                            "A",
                            "05:00-05:10",
                        ),
                    ],
                }
            ]
        )
        self.assertEqual(build_candidates(load_qas(path)), [])

    def test_overlapping_windows_are_not_two_events(self) -> None:
        path = _write(
            [
                {
                    "key": "vid",
                    "qa": [
                        _qa(
                            "1",
                            "What is the name of the first guest?\n(A) Sierra\n(B) Mia",
                            "A",
                            "00:29-01:36",
                        ),
                        _qa(
                            "2",
                            "Which picture does Sierra show?\n(A) The dog's pictures\n(B) A cat",
                            "A",
                            "01:25-01:30",
                        ),
                    ],
                }
            ]
        )
        self.assertEqual(build_candidates(load_qas(path)), [])

    def test_object_holder_is_possession_not_pickup(self) -> None:
        path = _write(
            [
                {
                    "key": "vid",
                    "qa": [
                        _qa(
                            "10",
                            "What does the man do after the second collision?\n"
                            "(A) He looks for his book\n(B) He sits down",
                            "A",
                            "04:42-05:00",
                        ),
                        _qa(
                            "11",
                            "What does the woman in red do after they meet for the third time?\n"
                            "(A) The man has his book\n(B) The woman has his book",
                            "B",
                            "05:15-05:31",
                        ),
                    ],
                }
            ]
        )
        candidates = build_candidates(load_qas(path))
        self.assertEqual(len(candidates), 1)
        item = candidates[0]
        self.assertEqual(item["composition_type"], "object_binding")
        self.assertEqual(item["new_answer"], "the woman in red")
        self.assertNotRegex(item["new_question"].lower(), r"pick")
        self.assertNotRegex(item["new_answer"].lower(), r"pick")
        self.assertEqual(item["source_answers"][0], "A: He looks for his book")
        self.assertEqual(item["source_answers"][1], "B: The woman has his book")

    def test_missing_field_is_rejected(self) -> None:
        candidate = {field: "x" for field in REQUIRED_FIELDS}
        candidate["source_uids"] = ["1", "2"]
        candidate["source_questions"] = ["a", "b"]
        candidate["source_answers"] = ["A: a", "B: b"]
        candidate["time_references"] = ["00:01-00:02", "00:10-00:12"]
        candidate["composition_type"] = "entity_binding"
        candidate["review_status"] = REVIEW_STATUS
        del candidate["new_answer"]
        errors = validate_candidate(candidate)
        self.assertIn("missing new_answer", errors)

    def test_duplicate_uids_are_rejected(self) -> None:
        candidate = {field: "x" for field in REQUIRED_FIELDS}
        candidate["source_uids"] = ["1", "1"]
        candidate["source_questions"] = ["a", "b"]
        candidate["source_answers"] = ["A: a", "A: a"]
        candidate["time_references"] = ["00:01-00:02", "00:10-00:12"]
        candidate["composition_type"] = "entity_binding"
        candidate["review_status"] = REVIEW_STATUS
        self.assertIn("source_uids", validate_candidate(candidate))

    @unittest.skipUnless(OFFICIAL.exists(), "official LVBench metadata is not on this machine")
    def test_official_candidates_trace_to_annotations(self) -> None:
        records = load_qas(OFFICIAL)
        candidates = build_candidates(records)
        self.assertGreaterEqual(len(candidates), 1)
        ids = [item["id"] for item in candidates]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [f"LVCOMP-V0-{index:03d}" for index in range(1, len(ids) + 1)])
        pairs = [
            (item["video_id"], tuple(item["source_uids"]), item["composition_type"])
            for item in candidates
        ]
        self.assertEqual(len(pairs), len(set(pairs)))
        questions = [(item["video_id"], item["new_question"].strip().lower()) for item in candidates]
        self.assertEqual(len(questions), len(set(questions)))
        index = {(item["video_id"], item["uid"]): item for item in records}
        for candidate in candidates:
            self.assertEqual(validate_candidate(candidate, records), [])
            self.assertEqual(candidate["review_status"], REVIEW_STATUS)
            self.assertFalse(candidate["video_verified"])
            self.assertGreaterEqual(len(candidate["source_uids"]), 2)
            for uid, label, question, reference in zip(
                candidate["source_uids"],
                candidate["source_answers"],
                candidate["source_questions"],
                candidate["time_references"],
            ):
                source = index[(candidate["video_id"], uid)]
                self.assertEqual(source["question"], question)
                self.assertEqual(source["time_reference"], reference)
                self.assertTrue(label.startswith(source["answer_letter"] + ": "))
                self.assertIn(source["answer_text"], label)
        hotel = [
            item
            for item in candidates
            if item["video_id"] == "_T2Avd3tFHc" and set(item["source_uids"]) == {"2873", "2890"}
        ]
        self.assertEqual(len(hotel), 1)
        self.assertEqual(hotel[0]["composition_type"], "entity_binding")
        self.assertIn("hotel", hotel[0]["new_answer"].lower())
        self.assertNotIn("Mikhail", hotel[0]["new_question"])
        book = [
            item
            for item in candidates
            if item["video_id"] == "q01CUy_gwdU" and set(item["source_uids"]) == {"120", "121"}
        ]
        self.assertEqual(len(book), 1)
        self.assertEqual(book[0]["composition_type"], "object_binding")
        self.assertEqual(book[0]["new_answer"], "the woman in red")
        self.assertNotRegex(book[0]["new_question"].lower(), r"pick")
        self.assertNotRegex(book[0]["new_answer"].lower(), r"pick")


if __name__ == "__main__":
    unittest.main()
