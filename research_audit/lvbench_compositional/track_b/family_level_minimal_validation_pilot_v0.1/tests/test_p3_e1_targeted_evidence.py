#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
E1 = PILOT / "p3_e1_targeted_evidence"
P3_OBS = PILOT / "p3_new_video_discovery/gpt_observations"
TB = ROOT / "research_audit/lvbench_compositional/track_b"
BASE = "7daa51985b9b816e3277d862f745ac10d3349508"


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class P3E1TargetedEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adj = json.loads((E1 / "HUMAN_ADJUDICATIONS.json").read_text(encoding="utf-8"))
        cls.man = json.loads((E1 / "EVIDENCE_MANIFEST.json").read_text(encoding="utf-8"))
        cls.sha = json.loads((E1 / "MEDIA_SHA_VALIDATION_REPORT.json").read_text(encoding="utf-8"))
        cls.gate = json.loads((E1 / "RUN_GATE_SNAPSHOT.json").read_text(encoding="utf-8"))
        cls.cfg = json.loads((PILOT / "PILOT_CONFIG.json").read_text(encoding="utf-8"))
        cls.run4 = json.loads((PILOT / "RUN_004_GATE.json").read_text(encoding="utf-8"))
        cls.sealed = json.loads((TB / "SEALED_POOL_SPLIT_POLICY.json").read_text(encoding="utf-8"))

    def test_four_adjudications_match_rois(self):
        by = {r["roi_id"]: r for r in self.adj["records"]}
        self.assertEqual(set(by), {
            "hROKtPqktO8_ROI_500_510",
            "hROKtPqktO8_ROI_1255_1265",
            "iA_69g87Ilw_ROI_358_368",
            "iA_69g87Ilw_ROI_900_910",
        })
        self.assertEqual(by["hROKtPqktO8_ROI_500_510"]["review_status"], "OBSERVATION_REQUIRES_MODIFICATION_OR_ADDITION")
        self.assertEqual(by["hROKtPqktO8_ROI_1255_1265"]["review_status"], "OBSERVATION_REQUIRES_MODIFICATION_OR_ADDITION")
        self.assertEqual(by["iA_69g87Ilw_ROI_358_368"]["review_status"], "ACCEPT_GPT_OBSERVATION")
        self.assertEqual(by["iA_69g87Ilw_ROI_900_910"]["review_status"], "ACCEPT_GPT_OBSERVATION")
        for r in self.adj["records"]:
            self.assertEqual(r["reviewer_role"], "HUMAN_SCIENTIFIC_OWNER")
            self.assertEqual(r["certification_status"], "NOT_CERTIFIED")
            self.assertEqual(r["source_commit"], BASE)
            self.assertTrue(r["direct_visual_observations"])
            self.assertTrue(r["human_interpretations_and_hypotheses"])

    def test_accepted_candidates_not_certified(self):
        r3 = next(r for r in self.adj["records"] if r["roi_id"] == "iA_69g87Ilw_ROI_358_368")
        r4 = next(r for r in self.adj["records"] if r["roi_id"] == "iA_69g87Ilw_ROI_900_910")
        self.assertEqual(r3["candidate_relations"][0]["relation_id"], "FRUIT_DISPLAY_THEN_LOUNGE_DISPLAY")
        self.assertEqual(r3["candidate_relations"][0]["relation_status"], "HUMAN_ACCEPTED_CANDIDATE_NOT_CERTIFIED")
        self.assertEqual(r4["candidate_relations"][0]["relation_id"], "PERSON_SPEAKING_THEN_DOOR_SIGN_DISPLAY")
        self.assertEqual(r4["candidate_relations"][0]["relation_status"], "HUMAN_ACCEPTED_CANDIDATE_NOT_CERTIFIED")

    def test_prior_48_frame_sha(self):
        self.assertEqual(self.sha["prior_48_frames"]["status"], "PASS")
        self.assertEqual(self.sha["prior_48_frames"]["n_ok"], 48)

    def test_media_sha_and_alignment(self):
        self.assertEqual(self.sha["overall"], "PASS")
        self.assertEqual(len(self.man["contexts"]), 4)
        for m in self.man["contexts"]:
            proxy = Path(m["continuous_proxy"]["local_path"])
            audio = Path(m["aligned_audio"]["local_path"])
            self.assertTrue(proxy.is_file(), proxy)
            self.assertTrue(audio.is_file(), audio)
            self.assertEqual(sha_file(proxy), m["continuous_proxy"]["sha256"])
            self.assertEqual(sha_file(audio), m["aligned_audio"]["sha256"])
            self.assertTrue(m["av_alignment"]["aligned_ok"])
            self.assertLess(m["t_start_s"], m["t_end_s"])
            self.assertIn(m["video_id"], {"hROKtPqktO8", "iA_69g87Ilw"})

    def test_no_unauthorized_videos(self):
        self.assertEqual(self.man["authorized_videos_only"], ["hROKtPqktO8", "iA_69g87Ilw"])
        vids = {m["video_id"] for m in self.man["contexts"]}
        self.assertEqual(vids, {"hROKtPqktO8", "iA_69g87Ilw"})

    def test_context_windows(self):
        by = {m["context_id"]: m for m in self.man["contexts"]}
        self.assertEqual([by["ROI1_CONTEXT"]["t_start_s"], by["ROI1_CONTEXT"]["t_end_s"]], [480.0, 530.0])
        self.assertEqual([by["ROI2_CONTEXT"]["t_start_s"], by["ROI2_CONTEXT"]["t_end_s"]], [1235.0, 1285.0])
        self.assertEqual([by["ROI3_CONTEXT"]["t_start_s"], by["ROI3_CONTEXT"]["t_end_s"]], [350.0, 375.0])
        self.assertEqual([by["ROI4_CONTEXT"]["t_start_s"], by["ROI4_CONTEXT"]["t_end_s"]], [890.0, 920.0])

    def test_p3_gpt_obs_files_present_and_git_clean(self):
        for name in (
            "hROKtPqktO8_ROI_500_510.json",
            "hROKtPqktO8_ROI_1255_1265.json",
            "iA_69g87Ilw_ROI_358_368.json",
            "iA_69g87Ilw_ROI_900_910.json",
            "INDEX.json",
        ):
            self.assertTrue((P3_OBS / name).is_file())
        out = subprocess.check_output(
            ["git", "status", "--porcelain", "--", str(P3_OBS)],
            cwd=ROOT,
            text=True,
        )
        self.assertEqual(out.strip(), "")

    def test_roles_and_gates_unchanged(self):
        self.assertEqual(self.cfg["seen"], ["SP001", "SP002", "SP005", "SP201", "SP202"])
        self.assertEqual(self.cfg["unseen"], ["P7_VTCD_C2", "P7_TJR_R3"])
        self.assertEqual(set(self.cfg["hold"]), {"P7_R4_F1", "P7_R4_F2", "SP205"})
        self.assertEqual(self.gate["seen"], self.cfg["seen"])
        self.assertEqual(self.gate["unseen"], self.cfg["unseen"])
        self.assertEqual(set(self.gate["hold"]), set(self.cfg["hold"]))
        self.assertEqual(self.run4["run_004_status"], "NOT_STARTED")
        self.assertEqual(self.gate["run_004_status"], "NOT_STARTED")
        self.assertFalse(self.gate["ok_for_expensive_rsi"])
        self.assertEqual(self.gate["qa_drafts_generated"], 0)
        self.assertEqual(self.sealed["sealed_reservoir"]["status"], "UNTOUCHED_PLACEHOLDER")
        for g in (
            "formal_seen_train",
            "formal_unseen",
            "formal_gold",
            "train_exposed",
            "seen_pool_frozen",
            "approve_expensive_track_a_rsi",
        ):
            self.assertFalse(self.gate[g])
            self.assertFalse(self.run4[g])

    def test_review_packet_and_stills_exist(self):
        self.assertTrue((E1 / "GPT_REVIEW_PACKET.md").is_file())
        text = (E1 / "GPT_REVIEW_PACKET.md").read_text(encoding="utf-8")
        self.assertIn("NOT prefilled", text)
        self.assertIn("NOT_CERTIFIED", text)
        self.assertIn("Do not treat this packet as SUPPORTED/GOLD", text)
        for m in self.man["contexts"]:
            self.assertEqual(len(m["review_stills_github"]), 3)
            for s in m["review_stills_github"]:
                p = ROOT / s["path"]
                self.assertTrue(p.is_file())
                self.assertEqual(sha_file(p), s["sha256"])


if __name__ == "__main__":
    unittest.main()
