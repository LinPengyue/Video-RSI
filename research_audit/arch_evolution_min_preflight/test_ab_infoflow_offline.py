#!/usr/bin/env python3
"""Offline tests before any paid API calls."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from infoflow_lib import (
    PREFLIGHT,
    ResultStore,
    connectivity_ids,
    estimate_cny,
    load_frozen_ids,
    load_gate_ids,
    parse_answer_letter,
    pick_diag_ids,
    sha256_text,
    vqa_prompt,
)
from ab_infoflow_runner import (
    PATH_A_REUSE,
    PATH_B_DIRECT,
    finalize_answer,
    record_template,
    run_a_reuse,
    summarize_ab,
)
from infoflow_lib import MockProvider, overview_bundle, cache_by_sample_id, load_train_items, load_oracle, TRAIN_ORACLE


def test_gate_leakage():
    ids = load_frozen_ids()
    gate = load_gate_ids()
    assert not (set(ids) & gate), "frozen set must not intersect Gate"
    # Injecting a gate id must be detectable
    leaked = ids + [next(iter(gate))]
    assert set(leaked) & gate


def test_answer_parse():
    options = {"A": "x", "B": "y", "C": "z", "D": "w"}
    letter, mode, err = parse_answer_letter('{"type":"answer","answer":"B"}', options)
    assert letter == "B" and mode == "strict_json" and not err
    letter, mode, err = parse_answer_letter("B", options)
    assert letter == "B" and mode == "bare_option"
    letter, mode, err = parse_answer_letter("I think the answer is B because...", options)
    assert letter == "B" and mode in ("regex_fallback", "answer_prefix_fallback")
    letter, mode, err = parse_answer_letter("no letter here", options)
    assert letter is None and mode == "unparsed"
    letter, mode, err = parse_answer_letter('```json\n{"type":"answer","answer":"C"}\n```', options)
    assert letter == "C"


def test_billing_record():
    cny = estimate_cny("qwen", prompt_tokens=1_000_000, completion_tokens=0)
    assert abs(cny - 4.0) < 1e-9
    cny = estimate_cny("deepseek", prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert abs(cny - (9.0 + 27.0)) < 1e-9
    rec = record_template("lvbench_x", PATH_A_REUSE, "answer")
    finalize_answer(rec, '{"type":"answer","answer":"A"}', {"A": "1", "B": "2"}, "A")
    assert rec["correct"] is True and rec["status"] == "ok"
    finalize_answer(rec, "zzz", {"A": "1", "B": "2"}, "A")
    assert rec["status"] == "parse_error"


def test_resume_skips_completed():
    tmp = Path(tempfile.mkdtemp(prefix="infoflow_test_"))
    try:
        store = ResultStore(tmp)
        items = load_train_items()
        cache = cache_by_sample_id()
        sid = load_frozen_ids()[0]
        item = items[sid]
        ov = overview_bundle(cache[sid])
        provider = MockProvider()
        golds = load_oracle(TRAIN_ORACLE)
        r1 = run_a_reuse(store, provider, item, ov, golds.get(sid))
        assert r1["status"] == "ok"
        n_calls = len(provider.calls)
        r2 = run_a_reuse(store, provider, item, ov, golds.get(sid))
        assert len(provider.calls) == n_calls  # no new call
        assert r2["answer"] == r1["answer"]
        # force redo
        r3 = run_a_reuse(store, provider, item, ov, golds.get(sid), force=True)
        assert len(provider.calls) == n_calls + 1
        assert r3["status"] == "ok"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_connectivity_seed_stable():
    ids = load_frozen_ids()
    a = connectivity_ids(ids, 4)
    b = connectivity_ids(ids, 4)
    assert a == b and len(a) == 4
    assert set(a).issubset(set(ids))
    assert not (set(a) & load_gate_ids())


def test_prompt_version_stable():
    q = "What happened?"
    options = {"A": "1", "B": "2", "C": "3", "D": "4"}
    p1 = vqa_prompt(q, options, caption="cap")
    p2 = vqa_prompt(q, options, caption="cap")
    assert sha256_text(p1) == sha256_text(p2)
    assert "type\":\"answer\"" in p1.replace(" ", "") or '"type":"answer"' in p1


def test_diag_picker():
    ids = ["a", "b", "c", "d", "e"]
    assert pick_diag_ids(ids, 3) == pick_diag_ids(ids, 3)
    assert len(pick_diag_ids(ids, 3)) == 3


def _ab(a_only, b_only, a_corr, b_corr, per_item=None):
    n = 20
    return {
        "A_only_correct": a_only,
        "B_only_correct": b_only,
        "A_correct": a_corr,
        "B_correct": b_corr,
        "per_item": per_item or [],
    }


def test_decide_go_stop_no_or_true_shortcut():
    """Complement without mechanism link must STOP (former `or True` bug)."""
    from ab_infoflow_runner import decide_go_stop

    ab = _ab(a_only=1, b_only=4, a_corr=8, b_corr=11, per_item=[
        {"sample_id": "s1", "A_correct": False, "B_correct": True},
    ])
    # diag rows: both text paths wrong BUT B was also wrong on that id → no vision retention
    diag = {
        "rows": [
            {
                "sample_id": "s_unrelated",
                "A_strict": {"answer": "A", "correct": False},
                "C_text_only": {"answer": "A", "correct": False},
            }
        ]
    }
    # B_correct missing for s_unrelated → vision_retention must be false; answers agree → no answerer
    out = decide_go_stop(ab, diag)
    assert out["vision_retention_signal"] is False
    assert out["answerer_identity_signal"] is False
    assert out["strict_support"] is False
    assert out["decision"] == "STOP", out


def test_decide_vision_retention_requires_b_correct():
    """Both caption paths failing is NOT vision retention unless B-direct was correct."""
    from ab_infoflow_runner import decide_go_stop

    ab = _ab(1, 4, 8, 11, per_item=[
        {"sample_id": "x", "A_correct": False, "B_correct": False},
    ])
    diag = {
        "rows": [
            {
                "sample_id": "x",
                "A_strict": {"answer": "A", "correct": False},
                "C_text_only": {"answer": "A", "correct": False},
            }
        ]
    }
    out = decide_go_stop(ab, diag)
    assert out["vision_retention_signal"] is False
    assert out["decision"] == "STOP"


def test_decide_vision_retention_true_when_b_ok_text_fail():
    from ab_infoflow_runner import decide_go_stop

    ab = _ab(1, 4, 8, 11, per_item=[
        {"sample_id": "y", "A_correct": False, "B_correct": True},
    ])
    diag = {
        "rows": [
            {
                "sample_id": "y",
                "A_strict": {"answer": "A", "correct": False},
                "C_text_only": {"answer": "B", "correct": False},
            }
        ]
    }
    out = decide_go_stop(ab, diag)
    assert out["vision_retention_signal"] is True
    assert out["decision"] == "GO"


def test_decide_answerer_identity_go():
    from ab_infoflow_runner import decide_go_stop

    ab = _ab(1, 3, 8, 10, per_item=[])
    diag = {
        "rows": [
            {
                "sample_id": "z",
                "A_strict": {"answer": "A", "correct": False},
                "C_text_only": {"answer": "B", "correct": True},
            }
        ]
    }
    out = decide_go_stop(ab, diag)
    assert out["answerer_identity_signal"] is True
    assert out["decision"] == "GO"


def test_decide_pivot_b_dominates_no_complement():
    from ab_infoflow_runner import decide_go_stop

    ab = _ab(0, 5, 6, 11)
    out = decide_go_stop(ab, {"rows": []})
    assert out["decision"] == "PIVOT"


def test_decide_pending_diag():
    from ab_infoflow_runner import decide_go_stop

    ab = _ab(1, 4, 8, 11)
    out = decide_go_stop(ab, None)
    assert out["decision"] == "PENDING_DIAG"


def test_oracle_router_bound():
    from pathlib import Path
    import json

    path = Path(__file__).resolve().parent / "runs" / "infoflow_v1" / "ab_summary.json"
    if not path.is_file():
        print("SKIP test_oracle_router_bound (no local ab_summary)")
        return
    ab = json.loads(path.read_text())
    oracle = sum(1 for r in ab["per_item"] if r["A_correct"] or r["B_correct"])
    assert oracle == 12
    assert ab["B_correct"] == 11
    assert oracle - ab["B_correct"] == 1


def run_all_tests() -> int:
    tests = [
        test_gate_leakage,
        test_answer_parse,
        test_billing_record,
        test_resume_skips_completed,
        test_connectivity_seed_stable,
        test_prompt_version_stable,
        test_diag_picker,
        test_decide_go_stop_no_or_true_shortcut,
        test_decide_vision_retention_requires_b_correct,
        test_decide_vision_retention_true_when_b_ok_text_fail,
        test_decide_answerer_identity_go,
        test_decide_pivot_b_dominates_no_complement,
        test_decide_pending_diag,
        test_oracle_router_bound,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception as exc:
            failed += 1
            print("FAIL", fn.__name__, exc)
    print("summary", "failed=%d" % failed, "total=%d" % len(tests))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run_all_tests())
