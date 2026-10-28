#!/usr/bin/env python3
"""Checks for LVBench compositional QA v1."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.lvbench_comp.build_comp_qa_v1 import (  # noqa: E402
    DRAFT_STATUS,
    REQUIRED_FIELDS,
    REVIEW_STATUS,
    build_v1,
    validate_candidate,
)
from tools.lvbench_comp.build_comp_qa import load_qas  # noqa: E402


OFFICIAL = Path("/home/descfly/lpy/dataset/LVBench/video_info.meta.jsonl")
V0 = Path("research_audit/lvbench_compositional/qa_v0/candidates.jsonl")


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


class BuildCompQaV1Test(unittest.TestCase):
    def test_role_question_is_not_the_original_who_question(self) -> None:
        path = _write(
            [
                {
                    "key": "vid",
                    "qa": [
                        _qa(
                            "1",
                            "What is the name of the stripper?\n(A) Mia\n(B) Roxana",
                            "A",
                            "27:04-29:49",
                        ),
                        _qa(
                            "2",
                            "Who does Austin choose?\n(A) Roxana\n(B) Mia",
                            "B",
                            "31:15-33:45",
                        ),
                    ],
                }
            ]
        )
        chosen, pending, _stats = build_v1(load_qas(path))
        self.assertEqual(pending, [])
        self.assertEqual(len(chosen), 1)
        item = chosen[0]
        self.assertEqual(item["composition_type"], "attribute_binding")
        self.assertIn("role", item["new_question"].lower())
        self.assertIn("stripper", item["new_answer"].lower())
        self.assertNotIn("Mia", item["new_question"])
        self.assertNotEqual(item["new_question"], "Who does Austin choose?")
        self.assertEqual(validate_candidate(item, load_qas(path)), [])

    def test_object_question_hides_the_noun(self) -> None:
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
        chosen, _pending, _stats = build_v1(load_qas(path))
        self.assertEqual(len(chosen), 1)
        item = chosen[0]
        self.assertEqual(item["composition_type"], "object_binding")
        self.assertEqual(item["new_answer"], "the woman in red")
        self.assertNotIn("book", item["new_question"].lower())
        self.assertNotRegex(item["new_question"].lower(), r"pick")
        self.assertNotRegex(item["new_answer"].lower(), r"pick")

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
        chosen, pending, _stats = build_v1(load_qas(path))
        self.assertEqual(chosen, [])
        self.assertEqual(pending, [])

    def test_missing_field_is_rejected(self) -> None:
        candidate = {field: "x" for field in REQUIRED_FIELDS}
        candidate["source_uids"] = ["1", "2"]
        candidate["source_questions"] = ["a", "b"]
        candidate["source_answers"] = ["A: a", "B: b"]
        candidate["time_references"] = ["00:01-00:02", "00:10-00:12"]
        candidate["composition_type"] = "entity_binding"
        candidate["review_status"] = REVIEW_STATUS
        candidate["video_verified"] = False
        candidate["derived_from_v0"] = None
        del candidate["new_answer"]
        self.assertIn("missing new_answer", validate_candidate(candidate))

    @unittest.skipUnless(OFFICIAL.exists() and V0.exists(), "official metadata or v0 file is absent")
    def test_official_v1_keeps_traceability(self) -> None:
        v0_text = V0.read_text(encoding="utf-8")
        records = load_qas(OFFICIAL)
        v0_rows = [json.loads(line) for line in v0_text.splitlines() if line.strip()]
        chosen, pending, stats = build_v1(records, v0_rows)
        self.assertEqual(V0.read_text(encoding="utf-8"), v0_text)
        self.assertGreaterEqual(len(chosen), 30)
        self.assertEqual(stats["complete_candidates"], len(chosen))
        self.assertEqual(stats["needs_human_draft"], len(pending))
        self.assertEqual(stats["scanned_same_video_pairs"], 11470)
        self.assertLess(len(chosen), stats["preliminary_pairs"] + len(pending))
        ids = [item["id"] for item in chosen]
        self.assertEqual(ids, [f"LVCOMP-V1-{index:03d}" for index in range(1, len(ids) + 1)])
        pairs = [(item["video_id"], tuple(sorted(item["source_uids"]))) for item in chosen]
        self.assertEqual(len(pairs), len(set(pairs)))
        questions = [(item["video_id"], item["new_question"].strip().lower()) for item in chosen]
        self.assertEqual(len(questions), len(set(questions)))
        for item in chosen:
            self.assertEqual(validate_candidate(item, records), [])
            self.assertEqual(item["review_status"], REVIEW_STATUS)
            self.assertFalse(item["video_verified"])
            self.assertNotIn("the vlogger tastes", item["new_answer"].lower())
        for item in pending:
            self.assertEqual(item["review_status"], DRAFT_STATUS)
            self.assertFalse(item["video_verified"])
        hotel = [
            item
            for item in chosen
            if item["video_id"] == "_T2Avd3tFHc" and set(item["source_uids"]) == {"2873", "2890"}
        ]
        self.assertEqual(len(hotel), 1)
        self.assertNotIn("Mikhail", hotel[0]["new_question"])
        self.assertIn("hotel", hotel[0]["new_answer"].lower())
        book = [
            item
            for item in chosen
            if item["video_id"] == "q01CUy_gwdU" and set(item["source_uids"]) == {"120", "121"}
        ]
        self.assertEqual(len(book), 1)
        self.assertNotIn("book", book[0]["new_question"].lower())
        self.assertEqual(book[0]["new_answer"], "the woman in red")
        stripper = [
            item
            for item in chosen
            if item["video_id"] == "JTa_Ue2MSwc" and set(item["source_uids"]) == {"5150", "5153"}
        ]
        self.assertEqual(len(stripper), 1)
        self.assertIn("stripper", stripper[0]["new_answer"].lower())
        self.assertNotIn("Mia", stripper[0]["new_question"])
        self.assertNotEqual(stripper[0]["new_question"], "Who does Austin choose?")
        self.assertTrue(all("2759" not in item["source_uids"] for item in chosen))


if __name__ == "__main__":
    unittest.main()
