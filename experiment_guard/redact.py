"""Desensitize paths and secrets for public / committed reports."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


_HOME = str(Path.home())
_SECRET_KEYS = re.compile(
    r"(api[_-]?key|authorization|secret|token|password|credential)", re.I
)


def redact_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    s = str(path)
    if _HOME and s.startswith(_HOME):
        s = "~" + s[len(_HOME) :]
    # Collapse long absolute prefixes to basename-ish markers for env names
    if "/envs/" in s:
        # keep env name + binary
        parts = Path(s).parts
        try:
            i = parts.index("envs")
            s = "/".join(["...", "envs", *parts[i + 1 :]])
        except ValueError:
            pass
    return s


def redact_obj(obj: Any, *, depth: int = 0) -> Any:
    if depth > 12:
        return "<truncated>"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_KEYS.search(str(k)):
                out[k] = "<redacted>"
            elif isinstance(v, str) and ("API_KEY" in str(k).upper() or "sk-" in v[:6]):
                out[k] = "<redacted>"
            else:
                out[k] = redact_obj(v, depth=depth + 1)
        return out
    if isinstance(obj, list):
        return [redact_obj(x, depth=depth + 1) for x in obj]
    if isinstance(obj, Path):
        return redact_path(obj)
    if isinstance(obj, str) and (obj.startswith("/") or obj.startswith(_HOME)):
        # heuristic path redaction
        if os.path.sep in obj and len(obj) > 24:
            return redact_path(obj)
    return obj


def provider_config_present(config: dict) -> dict:
    """Check provider env wiring without printing secrets."""
    services = config.get("services") or {}
    key_env = services.get("key_env") or "API_KEY"
    endpoint_env = services.get("endpoint_env") or "API_BASE"
    return {
        "key_env_name": key_env,
        "endpoint_env_name": endpoint_env,
        "key_env_set": bool(os.environ.get(key_env)),
        "endpoint_env_set": bool(os.environ.get(endpoint_env)),
        "deepseek_model_configured": bool((services.get("deepseek") or {}).get("request_model")),
        "qwen_model_configured": bool((services.get("qwen") or {}).get("request_model")),
        # never include values
    }
