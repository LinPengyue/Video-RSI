"""B3 — automatic relation mining over event graphs."""

from __future__ import annotations

from typing import Any


def _sig(ops: list[str]) -> str:
    return "→".join(ops)


def mine_relations(events_by_video: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rels: list[dict[str, Any]] = []
    rid = 0

    def add(rel: dict[str, Any]) -> None:
        nonlocal rid
        rid += 1
        rel["relation_id"] = f"REL_{rid:04d}"
        rels.append(rel)

    for vid, events in events_by_video.items():
        # Score / state transitions on same video
        score_ev = [e for e in events if e.get("state_after") and e.get("state_before")]
        score_ev = sorted(score_ev, key=lambda e: e["time_start_s"])
        for i in range(len(score_ev) - 1):
            a, b = score_ev[i], score_ev[i + 1]
            add(
                {
                    "video_id": vid,
                    "type": "ordered_state_transitions",
                    "source_fact_ids": [a["event_id"], b["event_id"]],
                    "minimal_witness_set": [a["event_id"], b["event_id"]],
                    "composition_signature": _sig(["observe_state_A", "observe_state_B", "order_compare"]),
                    "time_span_s": [a["time_start_s"], b["time_end_s"]],
                    "possible_shortcut": "B-only may reveal prior score if overlay shows previous state",
                    "uncertainty": list(set((a.get("unresolved_flags") or []) + (b.get("unresolved_flags") or []))),
                    "source_intervals": [
                        [a["time_start_s"], a["time_end_s"]],
                        [b["time_start_s"], b["time_end_s"]],
                    ],
                    "cause_status": "CAUSE_UNVERIFIED",
                }
            )

        # Same local actor across non-adjacent events
        # Skip still-frame observations: ChatGPT stills do not certify cross-shot identity.
        by_actor: dict[str, list[dict[str, Any]]] = {}
        for e in events:
            if e["verb"] in {"visual_sample", "seed_frame_present", "still_scene_observation"}:
                continue
            if e.get("is_still_frame_observation"):
                continue
            by_actor.setdefault(e["actor_local_track"], []).append(e)
        for actor, evs in by_actor.items():
            evs = sorted(evs, key=lambda e: e["time_start_s"])
            if len(evs) < 2:
                continue
            a, b = evs[0], evs[-1]
            if b["time_start_s"] - a["time_end_s"] < 5:
                continue
            add(
                {
                    "video_id": vid,
                    "type": "same_local_actor_nonadjacent",
                    "source_fact_ids": [a["event_id"], b["event_id"]],
                    "minimal_witness_set": [a["event_id"], b["event_id"]],
                    "composition_signature": _sig(["resolve_early_actor", "bind_hypothesis", "query_late_property"]),
                    "time_span_s": [a["time_start_s"], b["time_end_s"]],
                    "possible_shortcut": "If late frame still shows early property",
                    "uncertainty": ["identity_hypothesis_only"] + (a.get("unresolved_flags") or []) + (b.get("unresolved_flags") or []),
                    "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                    "actor_local_track": actor,
                    "cause_status": "CAUSE_UNVERIFIED",
                }
            )

        # Cross-actor identity hypothesis (TT-style): early garment actor vs late named overlay
        garment = [e for e in events if e["verb"] in {"remove_outer_garment", "wipe_face_wear_jacket"}]
        named = [e for e in events if "previous_results" in e["verb"] or "intro_caption" in e["verb"] or "start_list" in e["verb"]]
        for a in garment:
            for b in named:
                if b["time_start_s"] <= a["time_end_s"]:
                    continue
                add(
                    {
                        "video_id": vid,
                        "type": "late_name_condition_early_attribute",
                        "source_fact_ids": [a["event_id"], b["event_id"]],
                        "minimal_witness_set": [a["event_id"], b["event_id"]],
                        "composition_signature": _sig(
                            ["index_late_name_overlay", "hypothesize_same_athlete", "query_early_garment"]
                        ),
                        "time_span_s": [a["time_start_s"], b["time_end_s"]],
                        "possible_shortcut": "Late stills may retain jacket-in-hand; A-only lacks name",
                        "uncertainty": ["cross_track_identity_unverified"],
                        "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                        "cause_status": "CAUSE_UNVERIFIED",
                    }
                )

        # Athletics heat-boundary: intro USA Gay vs start list Gatlin
        intros = [e for e in events if e["verb"] == "broadcast_intro_caption"]
        starts = [e for e in events if e["verb"] == "display_start_list"]
        for a in intros:
            for b in starts:
                add(
                    {
                        "video_id": vid,
                        "type": "event_boundary_identity_contrast",
                        "source_fact_ids": [a["event_id"], b["event_id"]],
                        "minimal_witness_set": [a["event_id"], b["event_id"]],
                        "composition_signature": _sig(["read_intro_name", "read_start_list_name", "contrast_same_country"]),
                        "time_span_s": [a["time_start_s"], b["time_end_s"]],
                        "possible_shortcut": "Text overlay reading only; low structural complexity",
                        "uncertainty": [],
                        "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                        "cause_status": "N/A_CONTRAST",
                        "development_control": True,
                    }
                )

        # Indoor→city narrative (weak)
        indoor = [e for e in events if e.get("location") == "indoor"]
        outdoor = [e for e in events if "city" in (e.get("location") or "") or e["verb"] == "show_cityscape"]
        for a in indoor:
            for b in outdoor:
                if b["time_start_s"] <= a["time_start_s"]:
                    continue
                add(
                    {
                        "video_id": vid,
                        "type": "cross_shot_narrative_hypothesis",
                        "source_fact_ids": [a["event_id"], b["event_id"]],
                        "minimal_witness_set": [a["event_id"], b["event_id"]],
                        "composition_signature": _sig(["observe_indoor_people", "observe_city_aerial", "hypothesis_link"]),
                        "time_span_s": [a["time_start_s"], b["time_end_s"]],
                        "possible_shortcut": "Unrelated cuts; place/causality unknown",
                        "uncertainty": ["place_unknown", "causality_unknown"],
                        "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                        "cause_status": "CAUSE_UNVERIFIED",
                    }
                )

        # Slide→speech (audio pending)
        slides = [e for e in events if e["verb"] == "present_slide"]
        talks = [e for e in events if e["verb"] == "speak_closeup"]
        for a in slides:
            for b in talks:
                add(
                    {
                        "video_id": vid,
                        "type": "slide_speech_grounding_hypothesis",
                        "source_fact_ids": [a["event_id"], b["event_id"]],
                        "minimal_witness_set": [a["event_id"], b["event_id"]],
                        "composition_signature": _sig(["read_slide", "ground_speech", "match_topic"]),
                        "time_span_s": [a["time_start_s"], b["time_end_s"]],
                        "possible_shortcut": "Text-only slide answer without speech",
                        "uncertainty": ["audio_not_audited"],
                        "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                        "cause_status": "CAUSE_UNVERIFIED",
                    }
                )

        # Schema-general: non-adjacent semantic observations with distinct locations/objects
        # (transferable join; not sport-specific hardcoding).
        # STILL-frame ChatGPT/Cursor observations use consecutive-only pairing below —
        # do NOT expand all still pairs into cross_scene_attribute_contrast (template churn).
        semantic = [
            e
            for e in events
            if e.get("verb") not in {"visual_sample", "seed_frame_present", "still_scene_observation"}
            and not e.get("is_still_frame_observation")
            and (e.get("is_newly_discovered_semantic") or e.get("provenance_tier") == "CURSOR_FRAME_VISUAL_OBSERVATION")
        ]
        semantic = sorted(semantic, key=lambda e: e["time_start_s"])
        for i in range(len(semantic)):
            for j in range(i + 1, len(semantic)):
                a, b = semantic[i], semantic[j]
                if b["time_start_s"] - a["time_end_s"] < 5:
                    continue
                loc_diff = (a.get("location") or "") != (b.get("location") or "") and bool(a.get("location")) and bool(
                    b.get("location")
                )
                obj_diff = (a.get("object") or "") != (b.get("object") or "")
                if not (loc_diff or obj_diff):
                    continue
                add(
                    {
                        "video_id": vid,
                        "type": "cross_scene_attribute_contrast",
                        "source_fact_ids": [a["event_id"], b["event_id"]],
                        "minimal_witness_set": [a["event_id"], b["event_id"]],
                        "composition_signature": _sig(
                            ["observe_scene_A_attrs", "observe_scene_B_attrs", "contrast_location_or_object"]
                        ),
                        "time_span_s": [a["time_start_s"], b["time_end_s"]],
                        "possible_shortcut": "Single still may not prove temporal order without timestamps",
                        "uncertainty": list(
                            set((a.get("unresolved_flags") or []) + (b.get("unresolved_flags") or []) + ["cause_unverified"])
                        ),
                        "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                        "cause_status": "CAUSE_UNVERIFIED",
                        "attrs_a": {"location": a.get("location"), "object": a.get("object"), "verb": a.get("verb")},
                        "attrs_b": {"location": b.get("location"), "object": b.get("object"), "verb": b.get("verb")},
                    }
                )

        # Still-only observations: consecutive temporal pairs only (ordered setting contrast).
        # Explicitly NOT continuous-video events; identity/causality remain PENDING.
        stills = sorted(
            [e for e in events if e.get("is_still_frame_observation") or e.get("verb") == "still_scene_observation"],
            key=lambda e: e["time_start_s"],
        )
        for i in range(len(stills) - 1):
            a, b = stills[i], stills[i + 1]
            if b["time_start_s"] - a["time_end_s"] < 1.0:
                continue
            add(
                {
                    "video_id": vid,
                    "type": "still_ordered_setting_contrast",
                    "source_fact_ids": [a["event_id"], b["event_id"]],
                    "minimal_witness_set": [a["event_id"], b["event_id"]],
                    "composition_signature": _sig(
                        ["observe_still_A_setting", "observe_still_B_setting", "order_by_file_clock"]
                    ),
                    "time_span_s": [a["time_start_s"], b["time_end_s"]],
                    "possible_shortcut": "Either still alone may answer a vague setting question; timestamps needed for order",
                    "uncertainty": list(
                        set(
                            (a.get("unresolved_flags") or [])
                            + (b.get("unresolved_flags") or [])
                            + [
                                "still_pair_not_continuous_motion",
                                "cross_shot_identity_unverified",
                                "cause_unverified",
                            ]
                        )
                    ),
                    "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                    "cause_status": "CAUSE_UNVERIFIED",
                    "evidence_modality": "still_pair",
                    "continuous_video_verified": False,
                    "development_control": True,
                    "attrs_a": {"location": a.get("location"), "object": a.get("object"), "notes": (a.get("notes") or "")[:80]},
                    "attrs_b": {"location": b.get("location"), "object": b.get("object"), "notes": (b.get("notes") or "")[:80]},
                }
            )

        # Bounded domain hypothesis: two stills both showing price-bearing commercial displays
        # (distinct from generic scene-contrast template). Still NOT verified purchase/causality.
        priceish = [
            e
            for e in stills
            if any(
                k in ((e.get("notes") or "") + " " + (e.get("object") or "")).lower()
                for k in ("price", "vending", "100", "120", "display case", "trading", "collectible")
            )
        ]
        priceish = sorted(priceish, key=lambda e: e["time_start_s"])
        if len(priceish) >= 2:
            a, b = priceish[0], priceish[-1]
            if b["time_start_s"] - a["time_end_s"] >= 5:
                add(
                    {
                        "video_id": vid,
                        "type": "still_commerce_price_display_pair",
                        "source_fact_ids": [a["event_id"], b["event_id"]],
                        "minimal_witness_set": [a["event_id"], b["event_id"]],
                        "composition_signature": _sig(
                            ["observe_price_display_A", "observe_price_display_B", "compare_commercial_settings"]
                        ),
                        "time_span_s": [a["time_start_s"], b["time_end_s"]],
                        "possible_shortcut": "A-only or B-only may already show prices; no purchase/causality claimed",
                        "uncertainty": [
                            "still_pair_not_continuous_motion",
                            "currency_unverified",
                            "purchase_unverified",
                            "cause_unverified",
                        ],
                        "source_intervals": [[a["time_start_s"], a["time_end_s"]], [b["time_start_s"], b["time_end_s"]]],
                        "cause_status": "CAUSE_UNVERIFIED",
                        "evidence_modality": "still_pair",
                        "continuous_video_verified": False,
                        "development_control": True,
                    }
                )

    return rels
