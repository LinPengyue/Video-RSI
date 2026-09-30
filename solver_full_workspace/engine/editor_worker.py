"""Isolated DSH launcher; gate labels/scorer and original API key stay outside."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from isolation import filesystem_fence, syscall_fence, python_paths


def main():
    spec = json.loads(sys.stdin.readline())
    if spec["isolation"]:
        syscall_fence(network=True)
        filesystem_fence(spec["readable"] + [str(p) for p in python_paths()], spec["writable"])
    os.chdir(spec["cwd"])
    os.execve(spec["command"][0], spec["command"], spec["env"])


if __name__ == "__main__":
    main()
