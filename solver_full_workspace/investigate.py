"""Workspace-local client used by DSH's existing bash tool; no provider secrets."""
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python investigate.py analysis/request.json")
    with open(sys.argv[1], encoding="utf-8") as stream:
        payload = json.load(stream)
    with open(os.environ["INVESTIGATION_CONNECTION_FILE"], encoding="utf-8") as stream:
        connection = json.load(stream)
    request = urllib.request.Request(
        connection["url"], data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + connection["capability"],
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=float(connection["timeout"])) as response:
            print(response.read().decode())
    except urllib.error.HTTPError as exc:
        print(exc.read().decode())
        raise SystemExit(1)


if __name__ == "__main__":
    main()
