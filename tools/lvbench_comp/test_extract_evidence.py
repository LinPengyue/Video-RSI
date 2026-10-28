#!/usr/bin/env python3
"""Minimal checks for LVBench-Compositional phase-1 evidence extraction."""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_evidence as ev


REPO = Path(__file__).resolve().parents[2]
FFMPEG = Path(
    "/home/descfly/miniconda3/envs/videorsi/lib/python3.12/site-packages/"
    "imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
)
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def metadata_pair() -> list[dict]:
    return [
        {
            "key": "vidEarly",
            "video_info": {"duration_minutes": 1},
            "qa": [
                {
                    "uid": "2873",
                    "question": "Name?\n(A) Mikhail\n(B) Eric",
                    "question_type": ["entity recognition"],
                    "answer": "A",
                    "time_reference": "00:02-00:04",
                }
            ],
        },
        {
            "key": "vidOther",
            "video_info": {"duration_minutes": 1},
            "qa": [
                {
                    "uid": "120",
                    "question": "What?\n(A) book\n(B) phone",
                    "question_type": ["event understanding"],
                    "answer": "A",
                    "time_reference": "00:01-00:02",
                }
            ],
        },
    ]


def install_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def ffprobe_for_tests(directory: Path) -> Path:
    cached = Path.home() / ".cache" / "lvbench-comp" / "ffprobe"
    if cached.is_file() and os.access(cached, os.X_OK):
        # A partial download must not be mistaken for the binary.
        try:
            check = subprocess.run([str(cached), "-version"], check=False, capture_output=True, text=True)
        except OSError:
            check = None
        if check and check.returncode == 0 and "ffprobe" in (check.stdout + check.stderr).lower():
            return cached
    script = directory / "ffprobe"
    install_executable(
        script,
        "#!/usr/bin/env python3\n"
        "import json, re, subprocess, sys\n"
        f"ffmpeg = {str(FFMPEG)!r}\n"
        "target = sys.argv[-1]\n"
        "proc = subprocess.run([ffmpeg, '-hide_banner', '-i', target], capture_output=True, text=True)\n"
        "text = proc.stderr or ''\n"
        "matched = re.search(r'Duration: (\\d+):(\\d+):(\\d+(?:\\.\\d+)?)', text)\n"
        "if not matched:\n"
        "    sys.stderr.write(text[-2000:])\n"
        "    sys.exit(1)\n"
        "duration = int(matched.group(1)) * 3600 + int(matched.group(2)) * 60 + float(matched.group(3))\n"
        "video = re.search(r'Video:.*?(\\d+)x(\\d+).*?([\\d.]+) fps', text)\n"
        "streams = [{\n"
        "    'codec_type': 'video',\n"
        "    'width': int(video.group(1)) if video else None,\n"
        "    'height': int(video.group(2)) if video else None,\n"
        "    'avg_frame_rate': (video.group(3) + '/1') if video else '0/1',\n"
        "    'codec_name': 'h264',\n"
        "}]\n"
        "if 'Audio:' in text:\n"
        "    streams.append({'codec_type': 'audio', 'codec_name': 'aac'})\n"
        "print(json.dumps({'format': {'duration': str(duration)}, 'streams': streams}))\n",
    )
    return script


class ParseTests(unittest.TestCase):
    def test_mmss_and_hhmmss(self):
        self.assertEqual(ev.parse_timestamp("04:44"), 284)
        self.assertEqual(ev.parse_timestamp("89:58"), 89 * 60 + 58)
        self.assertEqual(ev.parse_timestamp("01:02:03"), 3723)
        self.assertAlmostEqual(ev.parse_timestamp("01:02:03.250"), 3723.25)
        start, end = ev.parse_time_reference("04:44-04:44")
        self.assertEqual((start, end), (284, 284))
        start, end = ev.parse_time_reference("00:04:42-00:05:00")
        self.assertEqual((start, end), (282, 300))

    def test_rejected_times(self):
        with self.assertRaises(ev.EvidenceError) as inverted:
            ev.parse_time_reference("05:00-04:00")
        self.assertEqual(inverted.exception.code, "time_range_inverted")
        with self.assertRaises(ev.EvidenceError) as missing:
            ev.parse_time_reference("None-None")
        self.assertEqual(missing.exception.code, "time_parse_error")
        with self.assertRaises(ev.EvidenceError):
            ev.parse_timestamp("04:99")

    def test_candidate_windows_match_official_geometry(self):
        duration = 4000
        early = ev.plan_window(284, 284, duration, mode="strict", context_seconds=20, point_strict_seconds=1)
        later_context = ev.plan_window(958, 967, duration, mode="context", context_seconds=20, point_strict_seconds=1)
        early_context = ev.plan_window(284, 284, duration, mode="context", context_seconds=20, point_strict_seconds=1)
        self.assertEqual(early["start_seconds"], 284)
        self.assertEqual(early["end_seconds"], 285)
        self.assertTrue(early["point_reference"])
        self.assertFalse(ev.windows_overlap(early_context, later_context))
        search = ev.plan_window(282, 300, duration, mode="strict", context_seconds=20, point_strict_seconds=1)
        meeting = ev.plan_window(315, 331, duration, mode="strict", context_seconds=20, point_strict_seconds=1)
        search_context = ev.plan_window(282, 300, duration, mode="context", context_seconds=20, point_strict_seconds=1)
        meeting_context = ev.plan_window(315, 331, duration, mode="context", context_seconds=20, point_strict_seconds=1)
        self.assertFalse(ev.windows_overlap(search, meeting))
        self.assertTrue(ev.windows_overlap(search_context, meeting_context))


class CaseTests(unittest.TestCase):
    def test_uid_video_mismatch_stops_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "meta.jsonl"
            write_jsonl(meta, metadata_pair())
            out = root / "out"
            result = ev.extract_case(
                video_id="vidOther",
                uids=["2873"],
                metadata_path=meta,
                video_root=root / "videos",
                output_dir=out,
                repo_root=None,
            )
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], "uid_video_mismatch")
            self.assertIn("vidEarly", result["message"])
            self.assertEqual(result["segments"], [])
            self.assertFalse(result["media_extracted"])
            saved = json.loads((out / "vidOther" / "case_result.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["error_code"], "uid_video_mismatch")
            self.assertEqual(list(out.rglob("*.mp4")), [])

    def test_missing_video_keeps_metadata_and_is_not_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "meta.jsonl"
            write_jsonl(meta, metadata_pair())
            out = root / "out"
            result = ev.extract_case(
                video_id="vidEarly",
                uids=["2873"],
                metadata_path=meta,
                video_root=root / "videos",
                output_dir=out,
                repo_root=None,
            )
            self.assertEqual(result["case_status"], "missing_video")
            self.assertEqual(result["error_code"], "missing_video")
            self.assertFalse(result["media_extracted"])
            self.assertEqual(result["composition_validity"], "NOT_ASSESSED")
            self.assertEqual(result["segments"][0]["time_reference"], "00:02-00:04")
            self.assertEqual(result["segments"][0]["answer"], "A")
            self.assertEqual(result["segments"][0]["extractions"], [])
            self.assertEqual(list(out.rglob("*.mp4")), [])

    def test_time_out_of_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "meta.jsonl"
            rows = metadata_pair()
            rows[0]["qa"][0]["time_reference"] = "00:10-00:12"
            write_jsonl(meta, rows)
            videos = root / "videos"
            videos.mkdir()
            (videos / "vidEarly.mp4").write_bytes(b"not-a-video")
            ffprobe = root / "ffprobe"
            install_executable(
                ffprobe,
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'format': {'duration': '2.0'}, 'streams': ["
                "{'codec_type': 'video', 'width': 16, 'height': 16, "
                "'avg_frame_rate': '10/1', 'codec_name': 'h264'}]}))\n",
            )
            ffmpeg = root / "ffmpeg"
            install_executable(ffmpeg, "#!/bin/sh\necho should-not-run >&2\nexit 9\n")
            out = root / "out"
            result = ev.extract_case(
                video_id="vidEarly",
                uids=["2873"],
                metadata_path=meta,
                video_root=videos,
                output_dir=out,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                font=FONT,
                repo_root=None,
            )
            self.assertEqual(result["error_code"], "time_out_of_bounds")
            self.assertIn("outside probed duration", result["message"])
            self.assertFalse(result["media_extracted"])
            self.assertEqual(result["segments"][0]["extractions"], [])
            self.assertEqual(list(out.rglob("*.mp4")), [])

    def test_ffmpeg_failure_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "meta.jsonl"
            write_jsonl(meta, metadata_pair())
            videos = root / "videos"
            videos.mkdir()
            (videos / "vidEarly.mp4").write_bytes(b"not-a-video")
            ffprobe = root / "ffprobe"
            install_executable(
                ffprobe,
                "#!/usr/bin/env python3\n"
                "import json\n"
                "print(json.dumps({'format': {'duration': '30'}, 'streams': ["
                "{'codec_type': 'video', 'width': 16, 'height': 16, "
                "'avg_frame_rate': '10/1', 'codec_name': 'h264'}, "
                "{'codec_type': 'audio', 'codec_name': 'aac'}]}))\n",
            )
            ffmpeg = root / "ffmpeg"
            install_executable(
                ffmpeg,
                "#!/bin/sh\necho 'simulated ffmpeg failure: decoder exploded' >&2\nexit 3\n",
            )
            out = root / "out"
            result = ev.extract_case(
                video_id="vidEarly",
                uids=["2873"],
                metadata_path=meta,
                video_root=videos,
                output_dir=out,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                font=FONT,
                repo_root=None,
            )
            self.assertEqual(result["error_code"], "ffmpeg_failed")
            self.assertIn("decoder exploded", result["message"])
            saved = (out / "vidEarly" / "case_result.json").read_text(encoding="utf-8")
            self.assertIn("decoder exploded", saved)
            self.assertFalse(result["media_extracted"])
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = ev.main(
                    [
                        "--video-id",
                        "vidEarly",
                        "--uids",
                        "2873",
                        "--metadata",
                        str(meta),
                        "--video-root",
                        str(videos),
                        "--output-dir",
                        str(root / "cli-out"),
                        "--ffmpeg",
                        str(ffmpeg),
                        "--ffprobe",
                        str(ffprobe),
                        "--font",
                        str(FONT),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertIn("decoder exploded", stdout.getvalue())


class ReviewTableTests(unittest.TestCase):
    def test_judgments_stay_pending_even_if_seed_says_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "meta.jsonl"
            write_jsonl(meta, metadata_pair())
            dest = root / "review.csv"
            ev.build_review_csv(
                meta,
                [
                    {
                        "candidate_id": "CAND-X",
                        "video_id": "vidEarly",
                        "source_uids": ["2873"],
                        "candidate_dependency": "hypothesis only",
                        "candidate_answer": "A",
                        "review_decision": "PASS",
                        "single_segment_shortcut": "PASS",
                        "source_time_references": "99:99-99:99",
                    }
                ],
                dest,
            )
            text = dest.read_text(encoding="utf-8")
            self.assertIn("00:02-00:04", text)
            self.assertNotIn("99:99-99:99", text)
            self.assertNotIn("PASS", text)
            self.assertIn("PENDING", text)
            self.assertIn("UNKNOWN", text)

    def test_seed_uid_mismatch_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            meta = root / "meta.jsonl"
            write_jsonl(meta, metadata_pair())
            dest = root / "review.csv"
            with self.assertRaises(ev.EvidenceError) as caught:
                ev.build_review_csv(
                    meta,
                    [
                        {
                            "candidate_id": "CAND-BAD",
                            "video_id": "vidOther",
                            "source_uids": ["2873"],
                            "candidate_dependency": "no",
                        }
                    ],
                    dest,
                )
            self.assertEqual(caught.exception.code, "uid_video_mismatch")
            self.assertFalse(dest.exists())


class GitIgnoreTests(unittest.TestCase):
    def test_media_paths_are_ignored(self):
        media = REPO / ev.DEFAULT_MEDIA_REL
        media.mkdir(parents=True, exist_ok=True)
        samples = [
            media / "probe_clip.mp4",
            media / "probe_frame.jpg",
            media / "probe_sheet.png",
        ]
        try:
            for sample in samples:
                sample.write_bytes(b"local-evidence")
                check = subprocess.run(
                    ["git", "-C", str(REPO), "check-ignore", "-q", "--", str(sample)],
                    check=False,
                )
                self.assertEqual(check.returncode, 0, sample)
                status = subprocess.run(
                    ["git", "-C", str(REPO), "status", "--porcelain", "--", str(sample)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(status.stdout.strip(), "")
        finally:
            for sample in samples:
                if sample.exists():
                    sample.unlink()

    def test_refuses_tracked_output_directory(self):
        tracked = REPO / "research_audit" / "lvbench_compositional" / "phase1" / "tracked_probe_dir"
        if tracked.exists():
            raise AssertionError(f"Refusing to use an existing directory: {tracked}")
        meta = REPO / "research_audit" / "lvbench_compositional" / "phase1" / "tracked_probe_meta.jsonl"
        try:
            write_jsonl(meta, metadata_pair())
            result = ev.extract_case(
                video_id="vidEarly",
                uids=["2873"],
                metadata_path=meta,
                video_root=REPO / "videos",
                output_dir=tracked,
                repo_root=REPO,
            )
            self.assertEqual(result["error_code"], "output_not_gitignored")
            self.assertFalse(tracked.exists())
        finally:
            if meta.exists():
                meta.unlink()
            if tracked.exists():
                subprocess.run(["rm", "-rf", str(tracked)], check=False)


class RealToolTests(unittest.TestCase):
    def test_short_clip_keeps_audio_timestamps_and_sheet(self):
        if not FFMPEG.is_file() or not FONT.is_file():
            self.skipTest("local ffmpeg or font is unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ffprobe = ffprobe_for_tests(root)
            source = root / "videos" / "vidEarly.mp4"
            source.parent.mkdir()
            synth = subprocess.run(
                [
                    str(FFMPEG),
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=320x240:rate=10:duration=8",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:sample_rate=44100:duration=8",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(source),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(synth.returncode, 0, synth.stderr[-500:])
            meta = root / "meta.jsonl"
            write_jsonl(meta, metadata_pair())
            out = root / "out"
            result = ev.extract_case(
                video_id="vidEarly",
                uids=["2873"],
                metadata_path=meta,
                video_root=source.parent,
                output_dir=out,
                context_seconds=1,
                frames=8,
                ffmpeg=FFMPEG,
                ffprobe=ffprobe,
                font=FONT,
                repo_root=None,
                timeout_seconds=120,
            )
            self.assertTrue(result["ok"], result.get("message"))
            self.assertEqual(result["composition_validity"], "NOT_ASSESSED")
            extractions = {item["mode"]: item for item in result["segments"][0]["extractions"]}
            self.assertEqual(set(extractions), {"context", "strict"})
            context = extractions["context"]
            self.assertTrue(context["audio_retained"])
            self.assertTrue(context["timestamp_burn_in"])
            self.assertEqual(len(context["keyframes"]), 8)
            stamps = [frame["video_timestamp_seconds"] for frame in context["keyframes"]]
            self.assertEqual(stamps, sorted(stamps))
            self.assertGreaterEqual(stamps[0], context["start_seconds"])
            self.assertLess(stamps[-1], context["end_seconds"])
            clip = out / context["clip_path"]
            sheet = out / context["contact_sheet"]
            self.assertTrue(clip.is_file())
            self.assertGreater(sheet.stat().st_size, 1000)
            self.assertIn("t=", (out / "vidEarly" / "uid_2873" / "context" / "frames" / "frame_01.txt").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
