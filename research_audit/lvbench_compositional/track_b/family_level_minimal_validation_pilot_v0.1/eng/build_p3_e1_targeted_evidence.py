#!/usr/bin/env python3
"""P3-E1: ingest human adjudications + extract targeted continuous video/audio evidence.

ENGINEERING_ONLY_WITH_HUMAN_APPROVED_EVIDENCE_PREPARATION.
Does not mint QA/Gold/SUPPORTED, does not unlock run_004, does not overwrite P3 GPT obs.
Continuous mp4/audio live under gitignored track_b/local_media/; review stills are committed.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PILOT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
P3 = PILOT / "p3_new_video_discovery"
E1 = PILOT / "p3_e1_targeted_evidence"
LOCAL_MEDIA = (
    ROOT
    / "research_audit/lvbench_compositional/track_b/local_media/p3_e1_targeted_evidence"
)
FFMPEG = Path("/home/descfly/.cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffmpeg")
FFPROBE = Path("/home/descfly/.cache/lvbench-comp/ffmpeg-7.0.2-amd64-static/ffprobe")
BASE_COMMIT = "7daa51985b9b816e3277d862f745ac10d3349508"
GATES = {
    "formal_seen_train": False,
    "formal_unseen": False,
    "formal_gold": False,
    "train_exposed": False,
    "seen_pool_frozen": False,
    "approve_expensive_track_a_rsi": False,
}
OK_EXPENSIVE = False

CONTEXTS = [
    {
        "context_id": "ROI1_CONTEXT",
        "roi_id": "hROKtPqktO8_ROI_500_510",
        "video_id": "hROKtPqktO8",
        "t_start_s": 480.0,
        "t_end_s": 530.0,
        "purpose": "Travel/street/selfie context around ROI-1 for continuity and identity cues",
    },
    {
        "context_id": "ROI2_CONTEXT",
        "roi_id": "hROKtPqktO8_ROI_1255_1265",
        "video_id": "hROKtPqktO8",
        "t_start_s": 1235.0,
        "t_end_s": 1285.0,
        "purpose": "Hillside/selfie context around ROI-2; do NOT treat ~12min gap alone as cross-event proof",
    },
    {
        "context_id": "ROI3_CONTEXT",
        "roi_id": "iA_69g87Ilw_ROI_358_368",
        "video_id": "iA_69g87Ilw",
        "t_start_s": 350.0,
        "t_end_s": 375.0,
        "purpose": "Fruit display then lounge display order around ROI-3",
    },
    {
        "context_id": "ROI4_CONTEXT",
        "roi_id": "iA_69g87Ilw_ROI_900_910",
        "video_id": "iA_69g87Ilw",
        "t_start_s": 890.0,
        "t_end_s": 920.0,
        "purpose": "Speaking person then door-sign display around ROI-4",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def ffprobe_json(path: Path) -> dict:
    out = subprocess.check_output(
        [
            str(FFPROBE),
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,avg_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        text=True,
    )
    return json.loads(out)


def load_source_register(video_id: str) -> dict:
    return json.loads((P3 / f"{video_id}_SOURCE_REGISTER.json").read_text(encoding="utf-8"))


def human_adjudications(ingested_utc: str) -> dict:
    # Map each ROI to prior GPT observation path for evidence_refs
    gpt_obs = {
        rid: f"p3_new_video_discovery/gpt_observations/{rid}.json"
        for rid in [
            "hROKtPqktO8_ROI_500_510",
            "hROKtPqktO8_ROI_1255_1265",
            "iA_69g87Ilw_ROI_358_368",
            "iA_69g87Ilw_ROI_900_910",
        ]
    }
    records = [
        {
            "roi_id": "hROKtPqktO8_ROI_500_510",
            "video_id": "hROKtPqktO8",
            "start_sec": 500,
            "end_sec": 510,
            "source_commit": BASE_COMMIT,
            "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
            "review_status": "OBSERVATION_REQUIRES_MODIFICATION_OR_ADDITION",
            "direct_visual_observations": [
                "Street / scenery footage visible.",
                "Woman recording a selfie-style video visible.",
                "Multiple shot cuts within the window.",
            ],
            "human_interpretations_and_hypotheses": [
                {
                    "claim": "Woman may be traveling or hiking, filming scenery along the way, then cutting back to selfie to share impressions.",
                    "tier": "HUMAN_HYPOTHESIS_NOT_CERTIFIED",
                    "must_not_upgrade_to": ["certified_hiking_event", "certified_sharing_impressions_event"],
                }
            ],
            "candidate_relations": [],
            "evidence_refs": {
                "prior_gpt_observation": gpt_obs["hROKtPqktO8_ROI_500_510"],
                "roi_manifest": "p3_new_video_discovery/rois/hROKtPqktO8_ROI_500_510.json",
                "context_window": "ROI1_CONTEXT",
            },
            "certification_status": "NOT_CERTIFIED",
        },
        {
            "roi_id": "hROKtPqktO8_ROI_1255_1265",
            "video_id": "hROKtPqktO8",
            "start_sec": 1255,
            "end_sec": 1265,
            "source_commit": BASE_COMMIT,
            "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
            "review_status": "OBSERVATION_REQUIRES_MODIFICATION_OR_ADDITION",
            "direct_visual_observations": [
                "Rocky hillside / slope scenery visible.",
                "Camera viewpoint and distance change across frames.",
                "Woman selfie with mountain landscape in background.",
                "On-screen subtitle mentions a steep slope (字幕提及陡坡).",
            ],
            "human_interpretations_and_hypotheses": [
                {
                    "claim": "Woman may be the camera operator approaching or climbing the slope.",
                    "tier": "HUMAN_HYPOTHESIS_NOT_CERTIFIED",
                    "must_not_upgrade_to": ["certified_climb_in_progress"],
                },
                {
                    "claim": "Woman may already have climbed the slope.",
                    "tier": "HUMAN_HYPOTHESIS_NOT_CERTIFIED",
                    "must_not_upgrade_to": ["certified_climb_completed"],
                },
                {
                    "claim": "Selfie background may correspond to the previously shown hillside.",
                    "tier": "HUMAN_HYPOTHESIS_NOT_CERTIFIED",
                    "must_not_upgrade_to": ["certified_same_location_bind"],
                },
                {
                    "claim": "Appearance cues (blonde hair, nose piercing, etc.) support possible same-person link with ROI-1; NOT authenticated.",
                    "tier": "UNAUTHENTICATED_IDENTITY_HYPOTHESIS",
                    "related_roi_id": "hROKtPqktO8_ROI_500_510",
                    "must_not_upgrade_to": ["CrossIntervalSamePersonBind", "certified_identity"],
                },
                {
                    "claim": "ROI-1 and ROI-2 may have a cross-event dependency; temporal gap alone (~12 min) is insufficient proof.",
                    "tier": "HUMAN_HYPOTHESIS_NOT_CERTIFIED",
                    "must_not_upgrade_to": ["certified_cross_event_dependency"],
                },
            ],
            "candidate_relations": [],
            "evidence_refs": {
                "prior_gpt_observation": gpt_obs["hROKtPqktO8_ROI_1255_1265"],
                "roi_manifest": "p3_new_video_discovery/rois/hROKtPqktO8_ROI_1255_1265.json",
                "context_window": "ROI2_CONTEXT",
            },
            "certification_status": "NOT_CERTIFIED",
        },
        {
            "roi_id": "iA_69g87Ilw_ROI_358_368",
            "video_id": "iA_69g87Ilw",
            "start_sec": 358,
            "end_sec": 368,
            "source_commit": BASE_COMMIT,
            "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
            "review_status": "ACCEPT_GPT_OBSERVATION",
            "direct_visual_observations": [
                "A hand points toward fruit on a fruit platter / bowl.",
                "Camera subsequently turns toward sofa, window, and lounge / rest area.",
            ],
            "human_interpretations_and_hypotheses": [
                {
                    "claim": "Do not infer fruit was taken, eaten, or moved.",
                    "tier": "NEGATIVE_CONSTRAINT",
                    "must_not_upgrade_to": ["take_fruit", "eat_fruit", "transfer_fruit"],
                }
            ],
            "candidate_relations": [
                {
                    "relation_id": "FRUIT_DISPLAY_THEN_LOUNGE_DISPLAY",
                    "relation_status": "HUMAN_ACCEPTED_CANDIDATE_NOT_CERTIFIED",
                    "certification_status": "NOT_CERTIFIED",
                    "note": "Ordered display of fruit then lounge; not a certified compositional program.",
                }
            ],
            "evidence_refs": {
                "prior_gpt_observation": gpt_obs["iA_69g87Ilw_ROI_358_368"],
                "roi_manifest": "p3_new_video_discovery/rois/iA_69g87Ilw_ROI_358_368.json",
                "context_window": "ROI3_CONTEXT",
            },
            "certification_status": "NOT_CERTIFIED",
        },
        {
            "roi_id": "iA_69g87Ilw_ROI_900_910",
            "video_id": "iA_69g87Ilw",
            "start_sec": 900,
            "end_sec": 910,
            "source_commit": BASE_COMMIT,
            "reviewer_role": "HUMAN_SCIENTIFIC_OWNER",
            "review_status": "ACCEPT_GPT_OBSERVATION",
            "direct_visual_observations": [
                "Man seated in a chair speaks and gestures.",
                "Later shot shows a Do Not Disturb door hanger / plaque beside a door.",
                "Hanger/plaque pose changes while held in a hand.",
            ],
            "human_interpretations_and_hypotheses": [
                {
                    "claim": "Do not infer completed hang / remove / flip of the plaque.",
                    "tier": "NEGATIVE_CONSTRAINT",
                    "must_not_upgrade_to": ["hang_complete", "remove_complete", "flip_complete"],
                },
                {
                    "claim": "Do not certify that the speaker and the hand operating the plaque are the same person.",
                    "tier": "NEGATIVE_CONSTRAINT",
                    "must_not_upgrade_to": ["same_person_bind", "CrossIntervalSamePersonBind"],
                },
            ],
            "candidate_relations": [
                {
                    "relation_id": "PERSON_SPEAKING_THEN_DOOR_SIGN_DISPLAY",
                    "relation_status": "HUMAN_ACCEPTED_CANDIDATE_NOT_CERTIFIED",
                    "certification_status": "NOT_CERTIFIED",
                    "note": "Ordered speaking then door-sign display; not certified same-agent or completed hang action.",
                }
            ],
            "evidence_refs": {
                "prior_gpt_observation": gpt_obs["iA_69g87Ilw_ROI_900_910"],
                "roi_manifest": "p3_new_video_discovery/rois/iA_69g87Ilw_ROI_900_910.json",
                "context_window": "ROI4_CONTEXT",
            },
            "certification_status": "NOT_CERTIFIED",
        },
    ]
    return {
        "schema": "p3_e1_human_adjudications_v1",
        "ingested_utc": ingested_utc,
        "source_commit": BASE_COMMIT,
        "authority": "HUMAN_SCIENTIFIC_OWNER",
        "n_records": len(records),
        "records": records,
        "qa_drafts_generated": 0,
        "run_003_untouched": True,
        "run_004_status": "NOT_STARTED",
        "ok_for_expensive_rsi": OK_EXPENSIVE,
        **GATES,
    }


def extract_context(ctx: dict, reg: dict, duration_s: float) -> dict:
    vid = ctx["video_id"]
    cid = ctx["context_id"]
    t0, t1 = ctx["t_start_s"], ctx["t_end_s"]
    if t0 < 0 or t1 > duration_s + 0.5 or t1 <= t0:
        raise SystemExit(f"TIME_OUT_OF_BOUNDS {cid}: [{t0},{t1}] vs duration {duration_s}")

    src = Path(reg["source_mp4"])
    if not src.is_file():
        raise SystemExit(f"SOURCE_MISSING {src}")
    # verify registered sha
    src_sha = sha_file(src)
    if src_sha != reg["source_sha256"]:
        raise SystemExit(f"SOURCE_SHA_MISMATCH {vid}")

    local_dir = LOCAL_MEDIA / vid / cid
    local_dir.mkdir(parents=True, exist_ok=True)
    # mirror pointer dir inside pilot (no large binaries committed due to *.mp4 gitignore)
    pilot_dir = E1 / "media" / vid / cid
    pilot_dir.mkdir(parents=True, exist_ok=True)

    dur = t1 - t0
    # continuous proxy preserving time order + audio
    proxy = local_dir / f"{cid}_continuous_proxy.mp4"
    run(
        [
            str(FFMPEG),
            "-y",
            "-ss",
            f"{t0:.3f}",
            "-i",
            str(src),
            "-t",
            f"{dur:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "28",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(proxy),
        ]
    )
    # aligned audio extract (AAC in m4a)
    audio = local_dir / f"{cid}_audio_aligned.m4a"
    run(
        [
            str(FFMPEG),
            "-y",
            "-ss",
            f"{t0:.3f}",
            "-i",
            str(src),
            "-t",
            f"{dur:.3f}",
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(audio),
        ]
    )

    # review stills (commit-friendly): begin / mid / end of context
    stills_dir = E1 / "review_stills" / vid / cid
    stills_dir.mkdir(parents=True, exist_ok=True)
    still_times = [t0, (t0 + t1) / 2.0, t1 - 0.05]
    stills = []
    for i, ts in enumerate(still_times):
        outp = stills_dir / f"still_{i:02d}_t{ts:.1f}.jpg"
        run(
            [
                str(FFMPEG),
                "-y",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(src),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(outp),
            ]
        )
        stills.append(
            {
                "still_id": f"{cid}_still_{i:02d}",
                "source_t_s": round(ts, 3),
                "path": str(outp.relative_to(ROOT)),
                "sha256": sha_file(outp),
                "bytes": outp.stat().st_size,
                "note": "Still sampled from continuous source for GitHub GPT review; NOT continuous video proof.",
            }
        )

    proxy_meta = ffprobe_json(proxy)
    audio_meta = ffprobe_json(audio)
    proxy_dur = float(proxy_meta["format"]["duration"])
    audio_dur = float(audio_meta["format"]["duration"])

    # write extraction params sidecar next to media
    extract_params = {
        "context_id": cid,
        "video_id": vid,
        "source_mp4": str(src),
        "source_sha256": src_sha,
        "t_start_s": t0,
        "t_end_s": t1,
        "requested_duration_s": dur,
        "ffmpeg": str(FFMPEG),
        "proxy_encode": "libx264 crf28 aac128k copy-time-order",
        "audio_encode": "aac128k aligned to same ss/t window",
        "original_fps_approx": "30000/1001",
        "audio_present_in_source": True,
        "subtitle_streams_in_source": False,
        "asr_run": False,
        "asr_status": "NOT_RUN_NO_LOCAL_OFFLINE_ASR_AUTHORIZED",
        "extracted_utc": utc_now(),
    }
    dump(local_dir / "EXTRACT_PARAMS.json", extract_params)
    # also copy params into pilot tree for git
    dump(pilot_dir / "EXTRACT_PARAMS.json", extract_params)

    media_rec = {
        "context_id": cid,
        "roi_id": ctx["roi_id"],
        "video_id": vid,
        "t_start_s": t0,
        "t_end_s": t1,
        "purpose": ctx["purpose"],
        "source": {
            "path": str(src),
            "sha256": src_sha,
            "pool": "DEV_CONSTRUCTION",
            "register": f"p3_new_video_discovery/{vid}_SOURCE_REGISTER.json",
        },
        "continuous_proxy": {
            "local_path": str(proxy),
            "git_committed": False,
            "reason_not_committed": "Repository policy ignores *.mp4 and track_b/local_media/",
            "sha256": sha_file(proxy),
            "bytes": proxy.stat().st_size,
            "duration_s": proxy_dur,
            "ffprobe": proxy_meta,
            "gpt_github_accessible": False,
            "gpt_local_accessible_if_workspace_present": True,
        },
        "aligned_audio": {
            "local_path": str(audio),
            "git_committed": False,
            "sha256": sha_file(audio),
            "bytes": audio.stat().st_size,
            "duration_s": audio_dur,
            "ffprobe": audio_meta,
            "gpt_github_accessible": False,
            "gpt_local_accessible_if_workspace_present": True,
        },
        "av_alignment": {
            "proxy_vs_audio_abs_diff_s": abs(proxy_dur - audio_dur),
            "aligned_ok": abs(proxy_dur - audio_dur) < 0.25,
            "window_duration_s": dur,
        },
        "subtitles_transcripts": {
            "embedded_subtitle_streams": False,
            "existing_external_vtt_srt": False,
            "asr": {
                "status": "NOT_RUN",
                "reason": "No local offline ASR tool found; paid/external ASR not authorized this round",
                "label_if_produced": "ASR_UNVERIFIED",
            },
            "human_verified_transcript": False,
        },
        "review_stills_github": stills,
        "extract_params_git": str((pilot_dir / "EXTRACT_PARAMS.json").relative_to(ROOT)),
        "extract_params_local": str(local_dir / "EXTRACT_PARAMS.json"),
    }
    dump(pilot_dir / "MEDIA_RECORD.json", media_rec)
    return media_rec


def validate_48_frames() -> dict:
    issues = []
    n_ok = 0
    for p in sorted((P3 / "gpt_observations").glob("*_ROI_*.json")):
        body = json.loads(p.read_text(encoding="utf-8"))
        for fr in body["evidence"]["frames"]:
            path = ROOT / fr["path"]
            if not path.is_file():
                issues.append({"frame_id": fr["frame_id"], "issue": "missing"})
                continue
            if sha_file(path) != fr["sha256"]:
                issues.append({"frame_id": fr["frame_id"], "issue": "sha_mismatch"})
            else:
                n_ok += 1
    return {"n_ok": n_ok, "n_expected": 48, "issues": issues, "status": "PASS" if n_ok == 48 and not issues else "FAIL"}


def assert_p3_gpt_obs_untouched() -> None:
    # working tree for gpt_observations must be clean relative to HEAD
    out = subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            str(P3 / "gpt_observations"),
        ],
        cwd=ROOT,
        text=True,
    )
    if out.strip():
        raise SystemExit(f"P3_GPT_OBS_MODIFIED:\n{out}")


def write_gpt_review_packet(adj: dict, media: list[dict], frame_val: dict) -> None:
    lines = [
        "# P3-E1 GPT Scientific Review Packet",
        "",
        f"Base commit: `{BASE_COMMIT}`",
        f"Generated: {utc_now()}",
        "",
        "**Cursor has NOT prefilled GPT observations for the continuous windows.**",
        "All candidate relations remain `*_NOT_CERTIFIED`. Do not treat this packet as SUPPORTED/GOLD.",
        "",
        "## 1. Human adjudications (4 ROIs)",
        "",
    ]
    for r in adj["records"]:
        lines.append(f"### {r['roi_id']} (`{r['start_sec']}–{r['end_sec']}`)")
        lines.append(f"- review_status: `{r['review_status']}`")
        lines.append(f"- certification_status: `{r['certification_status']}`")
        lines.append("- Direct visual observations:")
        for o in r["direct_visual_observations"]:
            lines.append(f"  - {o}")
        lines.append("- Human interpretations / hypotheses (NOT certified events):")
        for h in r["human_interpretations_and_hypotheses"]:
            lines.append(f"  - [{h['tier']}] {h['claim']}")
        if r["candidate_relations"]:
            lines.append("- Candidate relations:")
            for c in r["candidate_relations"]:
                lines.append(f"  - `{c['relation_id']}` — `{c['relation_status']}`")
        else:
            lines.append("- Candidate relations: _(none accepted)_")
        lines.append("")

    lines += [
        "## 2. Prior 12-frame evidence (unchanged)",
        "",
        f"- 48-frame SHA revalidation: **{frame_val['status']}** ({frame_val['n_ok']}/48)",
        "- Paths: `p3_new_video_discovery/gpt_observations/*_ROI_*.json` → `evidence.frames[]`",
        "",
        "## 3. Continuous video / audio index",
        "",
        "| context | video | window (s) | proxy duration | audio duration | proxy SHA256 | audio SHA256 | GitHub stills |",
        "|---------|-------|------------|----------------|----------------|--------------|--------------|---------------|",
    ]
    for m in media:
        lines.append(
            "| `{cid}` | `{vid}` | {a}–{b} | {pd:.2f}s | {ad:.2f}s | `{ps}` | `{as_}` | {n} |".format(
                cid=m["context_id"],
                vid=m["video_id"],
                a=m["t_start_s"],
                b=m["t_end_s"],
                pd=m["continuous_proxy"]["duration_s"],
                ad=m["aligned_audio"]["duration_s"],
                ps=m["continuous_proxy"]["sha256"][:16],
                as_=m["aligned_audio"]["sha256"][:16],
                n=len(m["review_stills_github"]),
            )
        )
    lines += [
        "",
        "### Media accessibility",
        "",
        "- **Continuous proxy + aligned audio**: local only under `track_b/local_media/p3_e1_targeted_evidence/` (gitignored). GPT GitHub review **cannot** stream these unless the review environment mounts this workspace.",
        "- **Review stills**: committed under `p3_e1_targeted_evidence/review_stills/` for GitHub-visible inspection (stills ≠ continuous certification).",
        "",
        "## 4. Hypotheses pending GPT direct observation",
        "",
        "1. ROI1↔ROI2: possible same woman (hair/piercing cues); need continuous context, not frame order alone.",
        "2. ROI2: hillside vs selfie background correspondence; climb-in-progress vs already-climbed.",
        "3. ROI3: confirm fruit→lounge display order without inventing take/eat.",
        "4. ROI4: speaking→door-sign display order; plaque pose change without certifying hang/remove/flip or same agent.",
        "5. ~12-minute gap between ROI1 and ROI2 contexts must **not** alone prove cross-event dependency.",
        "",
        "## 5. Specific questions for GPT (answer only from accessible evidence)",
        "",
        "- For each context: what is directly visible in stills / continuous clip (if available)?",
        "- Which human hypotheses gain support, remain unresolved, or are contradicted?",
        "- Do audio cues (if locally available) add evidence without over-claiming?",
        "- Any candidate directed compositional relation that is nontrivial and two-witness necessary? If none, report zero yield.",
        "",
        "## 6. Missing evidence / limits",
        "",
        "- No embedded subtitles found; no external VTT/SRT located for these videos.",
        "- ASR not run (no authorized local offline ASR; paid ASR not approved).",
        "- Continuous media not on GitHub; GitHub-only reviewers are limited to stills + prior 12-frame packs.",
        "- Cursor did not prefill continuous-window observations.",
        "",
        "## 7. Gates",
        "",
        "- run_004 = NOT_STARTED",
        "- ok_for_expensive_rsi = false",
        "- QA drafts = 0",
        "- Seen/Unseen/Hold unchanged",
        "",
    ]
    (E1 / "GPT_REVIEW_PACKET.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    assert FFMPEG.is_file() and FFPROBE.is_file()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != BASE_COMMIT:
        # allow building on top of base if ancestor; require base reachable
        try:
            subprocess.check_call(
                ["git", "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as e:
            raise SystemExit(f"BASE_COMMIT_NOT_ANCESTOR {BASE_COMMIT} HEAD={head}") from e

    assert_p3_gpt_obs_untouched()
    E1.mkdir(parents=True, exist_ok=True)
    LOCAL_MEDIA.mkdir(parents=True, exist_ok=True)
    ingested_utc = utc_now()

    # duration checks
    regs = {vid: load_source_register(vid) for vid in ("hROKtPqktO8", "iA_69g87Ilw")}
    durations = {}
    for vid, reg in regs.items():
        meta = ffprobe_json(Path(reg["source_mp4"]))
        durations[vid] = float(meta["format"]["duration"])

    adj = human_adjudications(ingested_utc)
    dump(E1 / "HUMAN_ADJUDICATIONS.json", adj)

    media_records = []
    for ctx in CONTEXTS:
        media_records.append(extract_context(ctx, regs[ctx["video_id"]], durations[ctx["video_id"]]))

    frame_val = validate_48_frames()
    media_sha = {
        "created_utc": ingested_utc,
        "base_commit": BASE_COMMIT,
        "prior_48_frames": frame_val,
        "contexts": [
            {
                "context_id": m["context_id"],
                "proxy_sha256": m["continuous_proxy"]["sha256"],
                "proxy_bytes": m["continuous_proxy"]["bytes"],
                "proxy_duration_s": m["continuous_proxy"]["duration_s"],
                "audio_sha256": m["aligned_audio"]["sha256"],
                "audio_bytes": m["aligned_audio"]["bytes"],
                "audio_duration_s": m["aligned_audio"]["duration_s"],
                "av_aligned_ok": m["av_alignment"]["aligned_ok"],
                "source_sha256_ok": True,
                "time_in_bounds": True,
            }
            for m in media_records
        ],
        "unauthorized_videos": [],
        "overall": "PASS"
        if frame_val["status"] == "PASS" and all(m["av_alignment"]["aligned_ok"] for m in media_records)
        else "FAIL",
    }
    dump(E1 / "MEDIA_SHA_VALIDATION_REPORT.json", media_sha)

    evidence_manifest = {
        "schema": "p3_e1_evidence_manifest_v1",
        "created_utc": ingested_utc,
        "base_commit": BASE_COMMIT,
        "authorized_videos_only": ["hROKtPqktO8", "iA_69g87Ilw"],
        "contexts": media_records,
        "human_adjudications": "HUMAN_ADJUDICATIONS.json",
        "local_media_root": str(LOCAL_MEDIA),
        "git_policy": "Continuous mp4/audio stored under gitignored track_b/local_media/; review stills committed",
        "qa_drafts_generated": 0,
        **GATES,
        "ok_for_expensive_rsi": OK_EXPENSIVE,
        "run_004_status": "NOT_STARTED",
    }
    dump(E1 / "EVIDENCE_MANIFEST.json", evidence_manifest)

    # snapshot gates without mutating PILOT_CONFIG roles
    cfg = json.loads((PILOT / "PILOT_CONFIG.json").read_text(encoding="utf-8"))
    gate = json.loads((PILOT / "RUN_004_GATE.json").read_text(encoding="utf-8"))
    sealed = json.loads(
        (ROOT / "research_audit/lvbench_compositional/track_b/SEALED_POOL_SPLIT_POLICY.json").read_text(
            encoding="utf-8"
        )
    )
    run_gate = {
        "created_utc": ingested_utc,
        "seen": cfg["seen"],
        "unseen": cfg["unseen"],
        "hold": cfg["hold"],
        "run_003_untouched": True,
        "run_004_status": "NOT_STARTED",
        "run_004_gate_status": gate["status"],
        "ok_for_expensive_rsi": OK_EXPENSIVE,
        "sealed_reservoir_status": sealed["sealed_reservoir"]["status"],
        "qa_drafts_generated": 0,
        "p3_e1_does_not_unlock_run_004": True,
        "blockers_retained": gate.get("blockers"),
        **GATES,
    }
    dump(E1 / "RUN_GATE_SNAPSHOT.json", run_gate)

    # keep RUN_004_GATE NOT_STARTED; refresh blockers note only
    gate["blockers"] = [
        "BLOCKED_NO_COMPOSITIONAL_EVENT_EVIDENCE from prior multiframe feasibility (0 qualifying)",
        "P3 GPT observations + P3-E1 human adjudications exist but no certified directed composition admitted",
        "HUMAN_ACCEPTED_CANDIDATE_NOT_CERTIFIED relations are not run_004 unlock criteria",
        "Continuous evidence prepared for GPT/human review; Cursor did not auto-certify",
    ]
    gate["p3_e1_targeted_evidence"] = "p3_e1_targeted_evidence/"
    gate["n_qualified_new_candidates"] = 0
    gate["run_004_status"] = "NOT_STARTED"
    for k, v in GATES.items():
        gate[k] = v
    dump(PILOT / "RUN_004_GATE.json", gate)

    write_gpt_review_packet(adj, media_records, frame_val)

    report = {
        "title": "P3-E1 engineering report",
        "created_utc": ingested_utc,
        "base_commit": BASE_COMMIT,
        "head_at_build": head,
        "human_adjudications": {r["roi_id"]: r["review_status"] for r in adj["records"]},
        "contexts_extracted": [
            {
                "context_id": m["context_id"],
                "window": [m["t_start_s"], m["t_end_s"]],
                "proxy_duration_s": m["continuous_proxy"]["duration_s"],
                "proxy_bytes": m["continuous_proxy"]["bytes"],
                "audio_duration_s": m["aligned_audio"]["duration_s"],
                "audio_bytes": m["aligned_audio"]["bytes"],
                "av_aligned_ok": m["av_alignment"]["aligned_ok"],
                "asr": m["subtitles_transcripts"]["asr"]["status"],
                "github_stills": len(m["review_stills_github"]),
                "continuous_gpt_github_accessible": False,
                "continuous_local_path": m["continuous_proxy"]["local_path"],
            }
            for m in media_records
        ],
        "prior_48_frame_sha": frame_val["status"],
        "media_sha_overall": media_sha["overall"],
        "p3_gpt_obs_untouched": True,
        "run_004_status": "NOT_STARTED",
        "ok_for_expensive_rsi": OK_EXPENSIVE,
        "qa_drafts_generated": 0,
        **GATES,
    }
    dump(E1 / "reports/P3_E1_ENGINEERING_REPORT.json", report)
    md = [
        "# P3-E1 Engineering Report",
        "",
        f"Base: `{BASE_COMMIT}`",
        f"Created: {ingested_utc}",
        "",
        "## Human adjudications",
        "",
    ]
    for rid, st in report["human_adjudications"].items():
        md.append(f"- `{rid}`: `{st}`")
    md += ["", "## Context extraction", ""]
    for c in report["contexts_extracted"]:
        md.append(
            f"- `{c['context_id']}` {c['window']}: proxy {c['proxy_duration_s']:.2f}s / {c['proxy_bytes']} B; "
            f"audio {c['audio_duration_s']:.2f}s; A/V align={c['av_aligned_ok']}; ASR={c['asr']}"
        )
        md.append(f"  - local continuous: `{c['continuous_local_path']}`")
    md += [
        "",
        f"48-frame SHA: **{frame_val['status']}**",
        f"Media SHA overall: **{media_sha['overall']}**",
        "",
        "run_004 = **NOT_STARTED**; ok_for_expensive_rsi = false; QA drafts = 0.",
        "",
        "GPT GitHub can review committed stills; continuous clips require local workspace mount.",
        "",
    ]
    (E1 / "reports/P3_E1_ENGINEERING_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": media_sha["overall"] == "PASS",
                "adjudications": report["human_adjudications"],
                "n_contexts": len(media_records),
                "run_004": "NOT_STARTED",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
