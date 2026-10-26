"""Environment and code fingerprints (desensitized)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from experiment_guard.redact import redact_path


def sha256_file(path: Path, nbytes: int | None = None) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        if nbytes is None:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        else:
            h.update(f.read(nbytes))
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_fingerprint(config: dict) -> str:
    # Stable hash; strip volatile absolute paths partially by dumping sorted JSON of key fields
    slim = {
        "execution_python": redact_path((config.get("execution") or {}).get("python")),
        "services_ffmpeg": (config.get("services") or {}).get("ffmpeg"),
        "services_models": {
            "deepseek": ((config.get("services") or {}).get("deepseek") or {}).get("request_model"),
            "qwen": ((config.get("services") or {}).get("qwen") or {}).get("request_model"),
        },
        "solver": config.get("solver"),
        "editor_caps": {
            k: (config.get("editor") or {}).get(k)
            for k in ("max_provider_calls", "max_frames", "max_rounds")
            if (config.get("editor") or {}).get(k) is not None
        },
    }
    blob = json.dumps(slim, sort_keys=True, ensure_ascii=False).encode()
    return sha256_bytes(blob)[:16]


def harness_fingerprint(harness_dir: Path | None) -> dict[str, Any]:
    if harness_dir is None or not Path(harness_dir).is_dir():
        return {"path": None, "sha16": None}
    root = Path(harness_dir)
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".py", ".json", ".md", ".txt"})
    h = hashlib.sha256()
    listed = []
    for p in files[:200]:
        rel = str(p.relative_to(root))
        digest = sha256_file(p) or ""
        h.update(rel.encode())
        h.update(digest.encode())
        listed.append(rel)
    return {
        "path": redact_path(root),
        "n_files_hashed": len(listed),
        "sha16": h.hexdigest()[:16],
    }


def git_sha(repo: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        return None
    return None


def python_dep_probe(python_exe: Path) -> dict[str, Any]:
    """Probe imageio_ffmpeg inside a specific interpreter via subprocess."""
    code = (
        "import json,sys\n"
        "out={'executable':sys.executable,'imageio_ffmpeg_importable':False,'error':None,"
        "'ffmpeg_exe':None,'version':None}\n"
        "try:\n"
        " import imageio_ffmpeg\n"
        " out['imageio_ffmpeg_importable']=True\n"
        " out['version']=getattr(imageio_ffmpeg,'__version__',None)\n"
        " from imageio_ffmpeg import get_ffmpeg_exe\n"
        " out['ffmpeg_exe']=get_ffmpeg_exe()\n"
        "except Exception as e:\n"
        " out['error']='%s:%s'%(type(e).__name__,e)\n"
        "print(json.dumps(out))\n"
    )
    try:
        r = subprocess.run(
            [str(python_exe), "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            return {
                "executable": redact_path(python_exe),
                "imageio_ffmpeg_importable": False,
                "error": (r.stderr or r.stdout or "probe_failed")[:300],
                "ffmpeg_exe": None,
                "version": None,
            }
        raw = json.loads(r.stdout.strip().splitlines()[-1])
        raw["executable"] = redact_path(raw.get("executable"))
        raw["ffmpeg_exe"] = redact_path(raw.get("ffmpeg_exe"))
        return raw
    except Exception as exc:
        return {
            "executable": redact_path(python_exe),
            "imageio_ffmpeg_importable": False,
            "error": "%s:%s" % (type(exc).__name__, exc),
            "ffmpeg_exe": None,
            "version": None,
        }


def host_fingerprint() -> dict[str, Any]:
    return {
        "sys_executable": redact_path(sys.executable),
        "python_version": sys.version.split()[0],
    }
