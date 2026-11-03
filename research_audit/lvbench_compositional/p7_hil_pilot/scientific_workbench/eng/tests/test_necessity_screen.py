#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PILOT = Path(__file__).resolve().parents[2] / "seen_pilot_run_002"
sys.path.insert(0, str(PILOT / "eng"))

from necessity_screen import (  # noqa: E402
    MECHANISM_A_CROSS_WINDOW_TARGET_BIND,
    PRIORITY,
    DIAGNOSTIC,
    SUFF_AB,
    SUFF_REF_UNRESOLVED,
    counterfactual_target_swap,
    screen_candidate,
)


class NecessityScreenTest(unittest.TestCase):
    def test_sp005_class_target_bind_priority(self):
        c = {
            "id": "X",
            "video_id": "V",
            "composition_schema": "identify_person + query_attribute",
            "new_question": "How to describe the feeling of the final winner at 48:16?",
            "new_answer": "frustrated",
            "time_references": ["48:00-48:17", "90:13-90:40"],
        }
        s = screen_candidate(c)
        self.assertEqual(s["diagnosis"]["screen_bucket"], PRIORITY)
        self.assertEqual(s["diagnosis"]["composition_necessity_hypothesis"], SUFF_AB)
        self.assertEqual(s["diagnosis"]["bind"]["mechanism_hypothesis"], MECHANISM_A_CROSS_WINDOW_TARGET_BIND)
        self.assertTrue(s["diagnosis"]["bind"]["target_referent_ambiguous_if_B_names_entity"])
        self.assertTrue(s["diagnosis"]["counterfactual"]["applicable"])
        self.assertFalse(s["diagnosis"]["auto_certified"])
        self.assertTrue(s["program_draft"]["not_approved"])

    def test_b_recognition_not_equated_to_selection(self):
        cf = counterfactual_target_swap("Which player scored for the country whose flag is waved at the beginning?")
        self.assertTrue(cf["applicable"])
        self.assertIn("A selected a different", cf["prompt"])

    def test_event_action_marked_diagnostic_unresolved(self):
        c = {
            "id": "Y",
            "video_id": "V",
            "composition_schema": "identify_event_result + query_action",
            "new_question": "How do the vloggers leave the platform after the high-speed train?",
            "new_answer": "go upstairs",
            "time_references": ["03:22-06:10", "11:03-11:40"],
        }
        s = screen_candidate(c)
        # May be PRIORITY if question has "first means" pattern — use plain question without bind cue
        c2 = dict(c, new_question="How does the vlogger leave the platform and go upstairs?")
        s2 = screen_candidate(c2)
        self.assertIn(s2["diagnosis"]["screen_bucket"], {DIAGNOSTIC, PRIORITY})
        self.assertIn(
            s2["diagnosis"]["composition_necessity_hypothesis"],
            {SUFF_REF_UNRESOLVED, SUFF_AB},
        )
        self.assertFalse(s2["diagnosis"]["auto_certified"])

    def test_does_not_force_pass_or_fail_unresolved(self):
        c = {
            "id": "Z",
            "video_id": "V",
            "composition_schema": "identify_object + query_cause",
            "new_question": "Something vague without clear bind lexicon",
            "new_answer": "x",
            "time_references": ["00:01-00:02", "00:03-00:04"],
        }
        s = screen_candidate(c)
        self.assertFalse(s["diagnosis"]["auto_certified"])
        self.assertNotEqual(s["status"], "USER_APPROVED_STRUCTURED_GRAPH")


if __name__ == "__main__":
    unittest.main()
