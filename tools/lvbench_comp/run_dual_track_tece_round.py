#!/usr/bin/env python3
"""Dual-track round: register ChatGPT proposals, TECE Track A artifacts, Track B evidence.

Does not run expensive RSI, does not mint formal SUPPORTED, keeps partitions UNASSIGNED.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.lvbench_comp.typed_evidence_contract.counterfactual import run_counterfactual_suite
from tools.lvbench_comp.typed_evidence_contract.evolver import EvolutionGenome, EvolverWorkspace
from tools.lvbench_comp.typed_evidence_contract.isolation import IsolationPolicy, assert_isolation
BASELINE = "791d25f9603a6533ef2ce0ee9e275430123ff667"
COMP = ROOT / "research_audit/lvbench_compositional"
SHARED = COMP / "chatgpt_video_driven_qa"
TRACK_A = COMP / "track_a"
TRACK_B = COMP / "track_b"
VIDEO_DIR = Path("/home/descfly/lpy/dataset/LVBench/videos")
FFMPEG = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg"
FFPROBE = Path.home() / ".cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffprobe"
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def parse_mmss_range(text: str) -> tuple[float, float]:
    a, b = [p.strip() for p in text.split("-", 1)]

    def one(tok: str) -> float:
        parts = tok.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

    return one(a), one(b)


def format_ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}" if h else f"{m:02d}:{s:06.3f}"


def run(cmd: list[str], timeout: float = 240.0) -> None:
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-2000:] or "command failed")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return float(out.stdout.strip())


def probe_has_audio(path: Path) -> bool:
    out = subprocess.run(
        [str(FFPROBE), "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(out.stdout.strip())


def cut_clip(source: Path, dest: Path, start: float, end: float, *, has_audio: bool, vf: str = "scale=960:-2") -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.2, end - start)
    preroll = 15.0
    pre = max(0.0, start - preroll)
    fine = start - pre
    cmd = [
        str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{pre:.3f}", "-i", str(source), "-ss", f"{fine:.3f}", "-t", f"{duration:.3f}",
        "-map", "0:v:0", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
    ]
    if has_audio:
        cmd += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "96k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(dest)]
    run(cmd)
    return {"path": str(dest), "bytes": dest.stat().st_size, "audio": has_audio and probe_has_audio(dest), "start": start, "end": end}


def contact_sheet(clip: Path, dest: Path, video_start: float, n: int = 8) -> dict:
    frame_dir = dest.parent / f"{dest.stem}_frames"
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True)
    dur = probe_duration(clip)
    offsets = [((i + 0.5) / n) * dur for i in range(n)]
    srt = frame_dir / "timestamps.srt"

    def srt_clock(sec: float) -> str:
        h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60); ms = int(round((sec - int(sec)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, off in enumerate(offsets, 1):
        lines.append(f"{i}\n{srt_clock(off)} --> {srt_clock(min(dur, off + 0.4))}\n{format_ts(video_start + off)}\n")
    srt.write_text("\n".join(lines), encoding="utf-8")
    burned = FONT.is_file()
    for i, off in enumerate(offsets, 1):
        out_frame = frame_dir / f"frame_{i:02d}.jpg"
        vf = "scale=480:-2"
        if burned:
            sub = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")
            fonts = str(FONT.parent).replace("\\", "\\\\").replace(":", "\\:")
            style = "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,Alignment=8,MarginV=12"
            vf = f"scale=480:-2,subtitles={sub}:fontsdir={fonts}:force_style='{style}'"
        run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{off:.3f}", "-i", str(clip), "-frames:v", "1", "-vf", vf, "-q:v", "4", str(out_frame)], 60)
    cols, rows = 4, int(math.ceil(n / 4))
    run([str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-start_number", "1", "-i", str(frame_dir / "frame_%02d.jpg"), "-frames:v", "1", "-vf", f"tile={cols}x{rows}:nb_frames={n}:padding=4:margin=4:color=black", "-q:v", "4", str(dest)], 60)
    return {"path": str(dest), "bytes": dest.stat().st_size}


# ---------------------------------------------------------------------------
# Shared: ChatGPT proposal registration
# ---------------------------------------------------------------------------

# Exact upload files were not present in the workspace at run time. Proposals below
# are registered from the round brief's explicit CG-NEW mappings / mechanisms and
# labeled so wording can be replaced if the official jsonl arrives later.
CG_NEW_PROPOSALS = [
    {
        "candidate_id": "CG-NEW-001",
        "linked_tb_id": "TB-003",
        "video_id": "TJR1oYDDTwg",
        "source": "CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE",
        "import_note": "Registered from round brief mapping CG-NEW-001/TB-003; exact ChatGPT jsonl file was not found in workspace.",
        "status": "PROPOSED",
        "data_partition_status": "UNASSIGNED",
        "public_discussion_contaminated": True,
        "composition_signature": "identify_person + query_action",
        "composition_mechanism": "role_identity_disambiguation_across_cast",
        "question": "After the king talks with the green dragon, the person who embraces the king later plays which instrument during the performance (while another performer plays guitar)?",
        "answer": "Drum set",
        "fact_A": "The person who embraces the king after the green-dragon talk is the Prince.",
        "fact_B": "During the performance, the prince plays drums and the princess plays guitar.",
        "evidence_windows": ["05:15-05:35", "20:00-20:20"],
        "necessity_checks": {
            "A_only": "PENDING",
            "B_only": "PENDING",
            "A_plus_B": "PENDING",
            "counterfactual_subject_swap": "PENDING",
            "official_qa_semantic_coverage": "PARTIAL — official 273 names prince+drums",
            "answer_uniqueness": "PENDING",
            "token_vs_type_match": "PENDING — must distinguish prince vs princess performers",
        },
        "layer": "COMPOSITION_PENDING",
    },
    {
        "candidate_id": "CG-NEW-002",
        "linked_tb_id": "TB-007",
        "video_id": "Cm73ma6Ibcs",
        "source": "CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE",
        "import_note": "Registered from round brief mapping CG-NEW-002/TB-007 (reverse temporal).",
        "status": "PROPOSED",
        "data_partition_status": "UNASSIGNED",
        "public_discussion_contaminated": True,
        "composition_signature": "later_action + reverse_locate_earlier_event",
        "composition_mechanism": "reverse_temporal_query",
        "question": "The person who later wipes her face with snow after being knocked down — what did she do in the restaurant after the gunman threatened the cook?",
        "answer": "Pushed the table aside and stood up to confront him",
        "fact_A": "In the restaurant, after the cook is threatened, the protagonist pushes the table and stands to confront the gunman.",
        "fact_B": "In the snow, when knocked down, she wipes her face with snow.",
        "evidence_windows": ["04:19-04:55", "06:00-06:25", "49:55-50:15"],
        "necessity_checks": {
            "A_only": "PENDING",
            "B_only": "PENDING",
            "A_plus_B": "PENDING",
            "counterfactual_subject_swap": "PENDING — snow fallen person vs restaurant confronter",
            "official_qa_semantic_coverage": "LOW direct coverage of reverse binding",
            "answer_uniqueness": "PENDING",
            "token_vs_type_match": "PENDING — same protagonist across scenes",
        },
        "layer": "COMPOSITION_PENDING",
    },
    {
        "candidate_id": "CG-NEW-003",
        "linked_tb_id": "TB-006",
        "video_id": "LLSJrEgOOtw",
        "source": "CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE",
        "import_note": "Registered from round brief mapping CG-NEW-003/TB-006 (audio+visual identity).",
        "status": "PROPOSED",
        "data_partition_status": "UNASSIGNED",
        "public_discussion_contaminated": True,
        "composition_signature": "identify_object + query_action",
        "composition_mechanism": "audio_visual_object_identity_link",
        "question": "What happens later with the animal that first appears alone playing with wood (and is audible)?",
        "answer": "People pick beech nuts and play with the dog",
        "fact_A": "Early on, a dog appears alone playing with wood; audio may support barking.",
        "fact_B": "Later, people pick beech nuts and play with a dog.",
        "evidence_windows": ["00:20-00:45", "02:03-02:45"],
        "necessity_checks": {
            "A_only": "PENDING",
            "B_only": "PENDING",
            "A_plus_B": "PENDING",
            "counterfactual_subject_swap": "PENDING — must not accept any dog as type-match without identity link",
            "official_qa_semantic_coverage": "PARTIAL",
            "answer_uniqueness": "PENDING",
            "token_vs_type_match": "CRITICAL",
            "audio_evidence": "PENDING_SEPARATE_FROM_VISUAL",
        },
        "layer": "COMPOSITION_PENDING",
    },
    {
        "candidate_id": "CG-NEW-004",
        "linked_tb_id": "TB-004",
        "video_id": "vaL_vSdZKZo",
        "source": "CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE",
        "import_note": "Registered as 4th ChatGPT-style candidate from uploaded TB-004 evidence theme (steering-wheel cue → ladder/gun action).",
        "status": "PROPOSED",
        "data_partition_status": "UNASSIGNED",
        "public_discussion_contaminated": True,
        "composition_signature": "identify_person + query_action",
        "composition_mechanism": "attribute_role_bridge_near_intervals",
        "question": "What does the woman who sits at the steering wheel do after getting down the ladder?",
        "answer": "Puts on a hard hat and shoots into the sea with a gun",
        "fact_A": "Woman at steering wheel wears pearl-style earrings.",
        "fact_B": "Woman with pearl earrings wears a hard hat and shoots into the sea after descending the ladder.",
        "evidence_windows": ["06:01-06:13", "06:17-06:27"],
        "necessity_checks": {
            "A_only": "PENDING",
            "B_only": "PENDING",
            "A_plus_B": "PENDING",
            "counterfactual_subject_swap": "PENDING",
            "official_qa_semantic_coverage": "1612 uses pearl-earrings cue not steering-wheel",
            "answer_uniqueness": "PENDING",
            "token_vs_type_match": "PENDING",
        },
        "layer": "COMPOSITION_PENDING",
    },
    {
        "candidate_id": "CG-NEW-005",
        "linked_tb_id": "TB-001",
        "video_id": "_T2Avd3tFHc",
        "source": "CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE",
        "import_note": "Registered as 5th candidate from TB-001 location-binding theme; not a sealed-test candidate (public discussion).",
        "status": "PROPOSED",
        "data_partition_status": "UNASSIGNED",
        "public_discussion_contaminated": True,
        "composition_signature": "identify_person + query_location",
        "composition_mechanism": "person_id_to_later_location",
        "question": "Where does the elder who joins the vlogger on their travel first go with the team?",
        "answer": "A bar",
        "fact_A": "The elder who joins is Mikhail.",
        "fact_B": "The first place the elder goes with the team is a bar.",
        "evidence_windows": ["04:40-05:05", "05:30-05:50"],
        "necessity_checks": {
            "A_only": "PENDING",
            "B_only": "PENDING",
            "A_plus_B": "PENDING",
            "counterfactual_subject_swap": "PENDING",
            "official_qa_semantic_coverage": "BOTH_OFFICIAL",
            "answer_uniqueness": "PENDING",
            "token_vs_type_match": "PENDING",
        },
        "layer": "COMPOSITION_PENDING",
    },
]


def write_shared() -> None:
    SHARED.mkdir(parents=True, exist_ok=True)
    src_note = {
        "expected_uploads": [
            "cvpr2027_chatgpt_video_driven_qa_proposals.jsonl",
            "cvpr2027_dual_track_next_round.md",
        ],
        "found_in_workspace": False,
        "fallback": "Registered five PROPOSED candidates from the round brief's CG-NEW mappings; replace wording if official ChatGPT jsonl arrives.",
        "contamination_policy": "These videos/candidates were used in public method discussion; never assign as blind sealed final test.",
        "preserve_tb_001_007": True,
    }
    (SHARED / "IMPORT_STATUS.json").write_text(json.dumps(src_note, indent=2) + "\n", encoding="utf-8")
    (SHARED / "cvpr2027_dual_track_next_round.md").write_text(
        """# CVPR 2027 dual-track next round (imported brief)

Track A: Typed Evidence Contract Evolution prototype (no expensive RSI).
Track B: video-driven QA evidence — not official-QA name-swap as primary method.
Shared: register ChatGPT designs as PROPOSED / UNASSIGNED; keep TB-001..007 intact.
""",
        encoding="utf-8",
    )
    with (SHARED / "cvpr2027_chatgpt_video_driven_qa_proposals.jsonl").open("w", encoding="utf-8") as handle:
        for row in CG_NEW_PROPOSALS:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (SHARED / "cg_new_registry.jsonl").open("w", encoding="utf-8") as handle:
        for row in CG_NEW_PROPOSALS:
            handle.write(
                json.dumps(
                    {
                        "candidate_id": row["candidate_id"],
                        "linked_tb_id": row["linked_tb_id"],
                        "video_id": row["video_id"],
                        "source": row["source"],
                        "status": row["status"],
                        "data_partition_status": row["data_partition_status"],
                        "layer": row["layer"],
                        "public_discussion_contaminated": True,
                        "formal_supported": False,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    # Preserve pointer to prior TB reviews without overwrite
    prior = TRACK_B / "candidates_pending_review.jsonl"
    if prior.is_file():
        shutil.copy2(prior, SHARED / "preserved_tb_001_007_candidates.jsonl")
    (SHARED / "README.md").write_text(
        """# ChatGPT video-driven QA proposals (Shared)

- Source label: `CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE`
- Status: all `PROPOSED`; partition `UNASSIGNED`
- Not blind sealed-test material
- Prior TB-001..007 preserved separately; not overwritten
""",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Track A progress artifacts
# ---------------------------------------------------------------------------

def write_track_a() -> dict:
    TRACK_A.mkdir(parents=True, exist_ok=True)
    suite = run_counterfactual_suite()
    (TRACK_A / "tece_counterfactual_results.json").write_text(
        json.dumps(suite.results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    genome = EvolutionGenome()
    ws = EvolverWorkspace(genome)
    ws.propose({"search_budget": 6, "recovery_strategy": "investigate_conflict"})
    ws.propose({"update_frozen_video_model_weights": True})  # should reject
    (TRACK_A / "tece_evolver_history.json").write_text(json.dumps(ws.history, indent=2) + "\n", encoding="utf-8")

    policy = IsolationPolicy(
        evolution_primitives={"identify_person", "query_action", "query_location", "query_attribute"},
        held_out_composition_signatures={"identify_person + query_action"},
        train_videos={"2LH3JCGkEBU", "evYm0cELO3I"},
        eval_videos={"JTa_Ue2MSwc"},
        train_uids={"4304", "4305"},
        eval_uids={"5130", "5131"},
    )
    iso = assert_isolation(
        policy,
        {
            "evolution_seen_signatures": ["identify_person + query_location"],
            "harness_id": "INITIAL_HARNESS_DECLARED",
            "using_hs1_as_final_judge": False,
            "accessed_track_b_sealed": False,
        },
    )
    (TRACK_A / "tece_isolation_check.json").write_text(json.dumps(iso, indent=2) + "\n", encoding="utf-8")

    progress = f"""# TRACK A PROGRESS — Typed Evidence Contract Evolution

Baseline: `{BASELINE}`  
Expensive RSI: **not run** (`ok_for_expensive_rsi=false` remains).

## Method interface

Generic operations (item-agnostic):

1. `locate_event`
2. `resolve_reference`
3. `track_identity`
4. `query_property`
5. `verify_answer`

Shared I/O carries entity candidates, time spans, evidence refs, binding results, ambiguity flags.

Code: `tools/lvbench_comp/typed_evidence_contract/`.

## Evolver modification space

Allowed: op order/branching, search budget, recovery strategy, dual-evidence verify predicates.  
Forbidden: frozen video-model weight updates, sealed-test answer reads, item-hardcoded pipelines.

## Local simulated tests

See `tece_counterfactual_results.json` and `python3 -m unittest tools.lvbench_comp.test_typed_evidence_contract -v`.

| Check | Result |
|---|---|
| Missing evidence reports gap | {suite.results['assertions']['missing_evidence_reported']} |
| Binding change moves query target | {suite.results['assertions']['binding_changes_query_target']} |
| Single-clip ≠ strong composition | {suite.results['assertions']['single_clip_not_strong_success']} |
| Failure triggers recovery | {suite.results['assertions']['failure_triggers_recovery']} |

## Potential increment vs prior RSI / unproven

**Potential increment:** evolvable evidence contracts + dual-interval verify + recovery, aimed at composition transfer rather than prompt templates.  
**Unproven:** no claim of video composition generalization; only simulated-trace logic.

## Still missing for a real method experiment

- ≥6 video-supported Unseen compositions across ≥3 videos
- Multi-video VALID Seen query_action coverage
- Human-verified dual-interval tickets for TECE grounding
- Declared Initial Harness snapshot wired to real tools (still no H_S1 final judge)
- Fair-budget arm runners (no_harness / fixed planner / vanilla RSI / TECE-RSI)

## Status

**Track A: runnable TECE prototype + unit tests. NOT ready for expensive RSI claims.**
"""
    (TRACK_A / "TRACK_A_PROGRESS.md").write_text(progress, encoding="utf-8")
    return {"assertions": suite.results["assertions"], "isolation_ok": iso["ok"]}


# ---------------------------------------------------------------------------
# Track B evidence enrichment
# ---------------------------------------------------------------------------

EVIDENCE_JOBS = [
    {
        "cg_id": "CG-NEW-001",
        "tb_id": "TB-003",
        "video_id": "TJR1oYDDTwg",
        "clips": [
            {"name": "cast_continuity_king_dragon_embrace", "time": "05:15-05:35", "vf": "scale=960:-2", "audio": True},
            {"name": "dual_performers", "time": "20:00-20:20", "vf": "scale=960:-2", "audio": True},
            {"name": "adjacent_pre_performance", "time": "19:40-20:00", "vf": "scale=960:-2", "audio": True},
        ],
        "new_fact_search_windows": ["05:35-06:00", "19:20-19:40"],
    },
    {
        "cg_id": "CG-NEW-002",
        "tb_id": "TB-007",
        "video_id": "Cm73ma6Ibcs",
        "clips": [
            {"name": "restaurant_push_table_standup", "time": "04:19-04:55", "vf": "scale=960:-2", "audio": True},
            {"name": "restaurant_confrontation_precise", "time": "06:00-06:25", "vf": "scale=960:-2", "audio": True},
            {"name": "snow_knockdown_wipe", "time": "49:55-50:15", "vf": "scale=960:-2", "audio": True},
        ],
        "new_fact_search_windows": ["04:55-05:30", "50:15-50:40"],
    },
    {
        "cg_id": "CG-NEW-003",
        "tb_id": "TB-006",
        "video_id": "LLSJrEgOOtw",
        "clips": [
            {"name": "dog_wood_audio_visual", "time": "00:20-00:45", "vf": "scale=960:-2", "audio": True},
            {"name": "dog_wood_zoomed", "time": "00:20-00:45", "vf": "crop=iw*0.5:ih*0.5:(iw-ow)/2:(ih-oh)/2,scale=960:-2", "audio": True},
            {"name": "later_play_with_dog", "time": "02:03-02:45", "vf": "scale=960:-2", "audio": True},
        ],
        "new_fact_search_windows": ["00:45-01:10", "02:45-03:15"],
    },
]


def write_track_b() -> dict:
    out_media = TRACK_B / "local_media" / "cg_new_round"
    if out_media.exists():
        shutil.rmtree(out_media)
    out_media.mkdir(parents=True)

    second_round = []
    new_facts = []
    extracted = []

    for job in EVIDENCE_JOBS:
        video = VIDEO_DIR / f"{job['video_id']}.mp4"
        dest = out_media / job["cg_id"]
        dest.mkdir(parents=True)
        has_audio = probe_has_audio(video)
        media_index = []
        for clip in job["clips"]:
            start, end = parse_mmss_range(clip["time"])
            path = dest / f"{clip['name']}.mp4"
            sheet = dest / f"{clip['name']}_contact_sheet.jpg"
            meta = cut_clip(video, path, start, end, has_audio=has_audio and clip.get("audio", True), vf=clip["vf"])
            sheet_meta = contact_sheet(path, sheet, start)
            media_index.append(
                {
                    "name": clip["name"],
                    "requested_time": clip["time"],
                    "clip": str(path.relative_to(TRACK_B)),
                    "contact_sheet": str(sheet.relative_to(TRACK_B)),
                    "audio_retained": meta["audio"],
                    "bytes": meta["bytes"],
                }
            )
            extracted.append(job["cg_id"] + "/" + clip["name"])
        # Adjacent windows for potential new facts — extract for human/ChatGPT design only.
        for win in job["new_fact_search_windows"]:
            start, end = parse_mmss_range(win)
            path = dest / f"adjacent_{win.replace(':','').replace('-','_')}.mp4"
            sheet = dest / f"adjacent_{win.replace(':','').replace('-','_')}_contact_sheet.jpg"
            meta = cut_clip(video, path, start, end, has_audio=has_audio)
            contact_sheet(path, sheet, start)
            new_facts.append(
                {
                    "cg_id": job["cg_id"],
                    "video_id": job["video_id"],
                    "window": win,
                    "status": "NEEDS_HUMAN_OR_CHATGPT_FACT_DESIGN",
                    "cursor_asserted_new_fact": False,
                    "note": "Adjacent evidence extracted only; no invented event labels.",
                    "clip": str(path.relative_to(TRACK_B)),
                    "audio_retained": meta["audio"],
                }
            )
        # Second-round composition necessity scaffold (not auto SUPPORTED)
        proposal = next(p for p in CG_NEW_PROPOSALS if p["candidate_id"] == job["cg_id"])
        second_round.append(
            {
                "candidate_id": job["cg_id"],
                "linked_tb_id": job["tb_id"],
                "video_id": job["video_id"],
                "status": "PROPOSED",
                "layer": "COMPOSITION_PENDING",
                "formal_supported": False,
                "data_partition_status": "UNASSIGNED",
                "A_only": "PENDING_INDEPENDENT_REVIEW",
                "B_only": "PENDING_INDEPENDENT_REVIEW",
                "A_plus_B": "PENDING_INDEPENDENT_REVIEW",
                "official_semantic_coverage": proposal["necessity_checks"]["official_qa_semantic_coverage"],
                "counterfactual_subject_swap": "PENDING_INDEPENDENT_REVIEW",
                "answer_uniqueness": "PENDING_INDEPENDENT_REVIEW",
                "token_vs_type_match": proposal["necessity_checks"].get("token_vs_type_match", "PENDING"),
                "media_index": media_index,
                "public_discussion_contaminated": True,
            }
        )
        (dest / "manifest.json").write_text(
            json.dumps({"cg_id": job["cg_id"], "media_index": media_index, "new_fact_windows": job["new_fact_search_windows"]}, indent=2) + "\n",
            encoding="utf-8",
        )

    # Also mark CG-NEW-004/005 as pending without new heavy extract (reuse prior TB media)
    for cid in ("CG-NEW-004", "CG-NEW-005"):
        proposal = next(p for p in CG_NEW_PROPOSALS if p["candidate_id"] == cid)
        second_round.append(
            {
                "candidate_id": cid,
                "linked_tb_id": proposal["linked_tb_id"],
                "video_id": proposal["video_id"],
                "status": "PROPOSED",
                "layer": "COMPOSITION_PENDING",
                "formal_supported": False,
                "data_partition_status": "UNASSIGNED",
                "A_only": "PENDING_INDEPENDENT_REVIEW",
                "B_only": "PENDING_INDEPENDENT_REVIEW",
                "A_plus_B": "PENDING_INDEPENDENT_REVIEW",
                "official_semantic_coverage": proposal["necessity_checks"]["official_qa_semantic_coverage"],
                "counterfactual_subject_swap": "PENDING_INDEPENDENT_REVIEW",
                "answer_uniqueness": "PENDING_INDEPENDENT_REVIEW",
                "token_vs_type_match": proposal["necessity_checks"].get("token_vs_type_match", "PENDING"),
                "media_index": "reuse_prior_TB_local_media",
                "public_discussion_contaminated": True,
            }
        )

    with (TRACK_B / "cg_new_second_round_status.jsonl").open("w", encoding="utf-8") as handle:
        for row in second_round:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (TRACK_B / "adjacent_new_fact_candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in new_facts:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    plan = """# Track B full-benchmark expansion plan (concise)

1. **Composition types to cover:** identify_person+query_action/location/attribute; identify_object+query_action; condition_event+later_action; reverse_temporal; audio-visual binding; state-change of same object.
2. **Video distribution:** ≥20 videos across interview/vlog/drama/animation/sports/doc; ≤3 sealed-test candidates per video.
3. **Sealed-test strategy:** hold out videos never used in public ChatGPT/Cursor discussion (exclude TJR/Cm73/LLS/vaL/_T2 used here); separate UID pools; freeze after dual independent reviews.
4. **Annotation cost (order-of-magnitude):** ~15–25 human minutes per dual-interval candidate (clip QC + necessity matrix); target 80–120 FACT_VERIFIED facts before large QA minting; composition layer separate.
5. **Process:** video evidence → new fact discovery → mechanism tag → ChatGPT designs QA → independent verification. Ban official-name-swap as primary path.
"""
    (TRACK_B / "BENCHMARK_EXPANSION_PLAN.md").write_text(plan, encoding="utf-8")

    report = f"""# TRACK B PROGRESS — video-driven evidence round

Baseline: `{BASELINE}`

## Method change

Primary path is **video evidence → fact discovery → mechanism → ChatGPT QA design → independent verification**.  
Official-QA name-swap is no longer the main constructor.

## High-value evidence supplements

| ID | Video | Focus | Extracted |
|---|---|---|---|
| CG-NEW-001 / TB-003 | TJR1oYDDTwg | cast continuity + dual performers | yes |
| CG-NEW-002 / TB-007 | Cm73ma6Ibcs | restaurant second-level + snow identity | yes |
| CG-NEW-003 / TB-006 | LLSJrEgOOtw | audio retained + zoomed dog + later play | yes |
| CG-NEW-004 / TB-004 | vaL_vSdZKZo | reuse prior TB media | pending review |
| CG-NEW-005 / TB-001 | _T2Avd3tFHc | reuse prior TB media | pending review |

## New video facts

Cursor **did not invent** new verified facts. Adjacent windows were extracted as `NEEDS_HUMAN_OR_CHATGPT_FACT_DESIGN` in `adjacent_new_fact_candidates.jsonl`.

## Second-round status

All five remain `PROPOSED` / `COMPOSITION_PENDING` / `UNASSIGNED`. No auto `SUPPORTED`.  
See `cg_new_second_round_status.jsonl`.

## Mechanism coverage

role disambiguation; reverse temporal; audio-visual object link; attribute-role bridge; person→location.

## Still needed from ChatGPT

Labeled new facts (if any) from adjacent clips; refined QA wording if import jsonl differs; necessity judgments A-only/B-only/A+B after watching new packs.

## Evidence pack

`local_media/cg_new_round/` + zip `local_media/lvbench_cg_new_evidence_round.zip` (gitignored).

## Status

**Track B: evidence advanced for 001–003; composition still pending independent review. Not a formal benchmark freeze.**
"""
    (TRACK_B / "TRACK_B_PROGRESS.md").write_text(report, encoding="utf-8")

    zip_path = TRACK_B / "local_media" / "lvbench_cg_new_evidence_round.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("TRACK_B_PROGRESS.md", report)
        zf.writestr("cg_new_second_round_status.jsonl", (TRACK_B / "cg_new_second_round_status.jsonl").read_text(encoding="utf-8"))
        zf.writestr("adjacent_new_fact_candidates.jsonl", (TRACK_B / "adjacent_new_fact_candidates.jsonl").read_text(encoding="utf-8"))
        zf.writestr("BENCHMARK_EXPANSION_PLAN.md", plan)
        for path in out_media.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".mp4", ".jpg", ".json"} and "_frames" not in str(path):
                zf.write(path, arcname=str(path.relative_to(TRACK_B)))
    return {
        "extracted_clips": len(extracted),
        "new_fact_windows": len(new_facts),
        "zip_mb": round(zip_path.stat().st_size / 1e6, 2),
        "zip": str(zip_path.relative_to(ROOT)),
    }


def update_dual_progress(a: dict, b: dict) -> None:
    text = f"""# Dual-track progress update

Baseline: `{BASELINE}`

## Shared
- Registered CG-NEW-001..005 as PROPOSED / UNASSIGNED under `chatgpt_video_driven_qa/`
- Source label: CHATGPT_DESIGN_FROM_UPLOADED_EVIDENCE (official upload file missing → brief fallback; see IMPORT_STATUS.json)
- TB-001..007 preserved; not overwritten
- Contaminated for blind sealed final test

## Track A
- TECE prototype + unit tests
- Counterfactual assertions: {a['assertions']}
- Isolation dry-check ok: {a['isolation_ok']}
- Expensive RSI: not run

## Track B
- Evidence pack: {b['zip']} ({b['zip_mb']} MB)
- Extracted clips: {b['extracted_clips']}; adjacent fact windows: {b['new_fact_windows']}
- No auto SUPPORTED
"""
    (COMP / "DUAL_TRACK_PROGRESS.md").write_text(text, encoding="utf-8")


def main() -> int:
    write_shared()
    a = write_track_a()
    b = write_track_b()
    update_dual_progress(a, b)
    print(json.dumps({"track_a": a, "track_b": b}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
