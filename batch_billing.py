"""Per-model CNY estimate helpers for external batch runners (no harness edits).

Rates are planning estimates from the researcher MaaS price sheet, not invoice
settlement and not a provider hard limit.
"""
from __future__ import annotations

from copy import deepcopy

# CNY per 1M tokens — from「常规模型」sheet of MaaS平台模型列表及报价.xlsx
# DeepSeek-V4-Pro-0813: in 9 / out 27 / cache-hit in 0.30
# Qwen3.6-Plus:         in 4 / out 24 / cache-hit in 0.40
DEFAULT_MODEL_RATES = {
    "deepseek": {
        "request_model": "DeepSeek-V4-Pro-0813",
        "rate_in": 9.0,
        "rate_out": 27.0,
        "rate_cache_in": 0.3,
    },
    "qwen": {
        "request_model": "Qwen3.6-Plus",
        "rate_in": 4.0,
        "rate_out": 24.0,
        "rate_cache_in": 0.4,
    },
}

ROLES = ("deepseek", "qwen")


def empty_role() -> dict:
    return {
        "calls": 0,
        "ok_calls": 0,
        "non_ok_calls": 0,
        "missing_usage_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "estimated_cny": 0.0,
        "estimated_cny_no_cache": 0.0,
    }


def empty_usage() -> dict:
    return {
        "source": None,
        "by_role": {r: empty_role() for r in ROLES},
        "provider_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "missing_usage_calls": 0,
        "non_ok_calls": 0,
        "estimated_cny": 0.0,
        "estimated_cny_no_cache": 0.0,
        "undercount_risk": False,
        "notes": [],
    }


def role_cost(prompt: int, completion: int, cached: int, rates: dict, *, apply_cache: bool) -> tuple[float, float]:
    """Return (cny_with_policy, cny_no_cache). Cache discount only when apply_cache and cached>0."""
    rate_in = float(rates["rate_in"])
    rate_out = float(rates["rate_out"])
    rate_cache = float(rates.get("rate_cache_in") or 0.0)
    no_cache = (prompt * rate_in + completion * rate_out) / 1e6
    if apply_cache and cached > 0:
        uncached = max(0, prompt - cached)
        with_cache = (uncached * rate_in + cached * rate_cache + completion * rate_out) / 1e6
    else:
        with_cache = no_cache
    return with_cache, no_cache


def usage_from_result(result: dict | None, model_rates: dict | None = None, *, apply_cache: bool = True) -> dict:
    """Extract per-role usage without double-counting aggregate usage + meter_events.

    Preference: if any kind==provider meter events exist, bill ONLY from those.
    Else fall back to aggregate usage (cannot split models; marks undercount_risk).
    """
    rates = model_rates or DEFAULT_MODEL_RATES
    out = empty_usage()
    if not isinstance(result, dict):
        out["notes"].append("missing_result")
        out["undercount_risk"] = True
        return out

    events = [e for e in (result.get("meter_events") or []) if e.get("kind") == "provider"]
    if events:
        out["source"] = "meter_events"
        for ev in events:
            role = ev.get("role")
            if role not in out["by_role"]:
                out["notes"].append("unknown_role:%s" % role)
                continue
            slot = out["by_role"][role]
            slot["calls"] += 1
            if ev.get("status") == "ok":
                slot["ok_calls"] += 1
            else:
                slot["non_ok_calls"] += 1
                out["non_ok_calls"] += 1
            usage = ev.get("usage") or {}
            if not usage:
                slot["missing_usage_calls"] += 1
                out["missing_usage_calls"] += 1
                out["undercount_risk"] = True
                continue
            prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
            completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
            details = usage.get("prompt_tokens_details") or {}
            cached = int(details.get("cached_tokens") or 0)
            slot["prompt_tokens"] += prompt
            slot["completion_tokens"] += completion
            slot["cached_tokens"] += cached
        for role, slot in out["by_role"].items():
            cny, cny_nc = role_cost(
                slot["prompt_tokens"],
                slot["completion_tokens"],
                slot["cached_tokens"],
                rates[role],
                apply_cache=apply_cache,
            )
            slot["estimated_cny"] = cny
            slot["estimated_cny_no_cache"] = cny_nc
            out["provider_calls"] += slot["calls"]
            out["prompt_tokens"] += slot["prompt_tokens"]
            out["completion_tokens"] += slot["completion_tokens"]
            out["cached_tokens"] += slot["cached_tokens"]
            out["estimated_cny"] += cny
            out["estimated_cny_no_cache"] += cny_nc
        return out

    # Fallback: aggregate usage only (no per-role token split).
    out["source"] = "aggregate_usage"
    usage = result.get("usage") or {}
    prompt = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    completion = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    ds_calls = int(usage.get("deepseek_calls") or 0)
    qw_calls = int(usage.get("qwen_calls") or 0)
    out["by_role"]["deepseek"]["calls"] = ds_calls
    out["by_role"]["qwen"]["calls"] = qw_calls
    out["provider_calls"] = ds_calls + qw_calls
    out["prompt_tokens"] = prompt
    out["completion_tokens"] = completion
    if prompt or completion:
        # Conservative: bill pooled tokens at max input/output rates across roles.
        max_in = max(float(rates[r]["rate_in"]) for r in ROLES)
        max_out = max(float(rates[r]["rate_out"]) for r in ROLES)
        cny = (prompt * max_in + completion * max_out) / 1e6
        out["estimated_cny"] = cny
        out["estimated_cny_no_cache"] = cny
        out["undercount_risk"] = True
        out["notes"].append("aggregate_usage_billed_at_max_role_rates")
    if out["provider_calls"] <= 0 and (prompt or completion):
        out["undercount_risk"] = True
        out["notes"].append("tokens_without_call_counts")
    return out


def merge_usage(dst: dict, src: dict) -> dict:
    """Accumulate src into dst (mutates dst)."""
    dst["provider_calls"] += src["provider_calls"]
    dst["prompt_tokens"] += src["prompt_tokens"]
    dst["completion_tokens"] += src["completion_tokens"]
    dst["cached_tokens"] += src["cached_tokens"]
    dst["missing_usage_calls"] += src["missing_usage_calls"]
    dst["non_ok_calls"] += src["non_ok_calls"]
    dst["estimated_cny"] += src["estimated_cny"]
    dst["estimated_cny_no_cache"] += src["estimated_cny_no_cache"]
    dst["undercount_risk"] = bool(dst.get("undercount_risk")) or bool(src.get("undercount_risk"))
    for role in ROLES:
        a, b = dst["by_role"][role], src["by_role"][role]
        for k in (
            "calls",
            "ok_calls",
            "non_ok_calls",
            "missing_usage_calls",
            "prompt_tokens",
            "completion_tokens",
            "cached_tokens",
        ):
            a[k] += b[k]
        a["estimated_cny"] += b["estimated_cny"]
        a["estimated_cny_no_cache"] += b["estimated_cny_no_cache"]
    if src.get("notes"):
        dst.setdefault("notes", []).extend(src["notes"])
    return dst


def rates_snapshot(model_rates: dict | None = None) -> dict:
    return deepcopy(model_rates or DEFAULT_MODEL_RATES)
