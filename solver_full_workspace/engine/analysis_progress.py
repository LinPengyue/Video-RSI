"""File-based analysis progress tracking."""
from pathlib import Path

from .common import read_json


class AnalysisIncomplete(RuntimeError):
    pass


def completion(workspace, private):
    report = Path(workspace) / "analysis/analysis.md"
    receipt = Path(private) / "investigations/analysis_submission.json"
    if not report.is_file() or not report.read_text().strip() or not receipt.is_file():
        return None
    return read_json(receipt)


def progress_snapshot(workspace, private):

    workspace, private = Path(workspace), Path(private)
    notes = tuple((workspace / "analysis" / name).read_text()
                  if (workspace / "analysis" / name).is_file() else ""
                  for name in ("notes.md", "analysis.md"))
    records = tuple(p.name for p in sorted((private / "investigations").glob("request_*.json"))
                    if read_json(p).get("status") == "completed")
    return notes, records


def resume_prompt(task, phase, workspace, private, used, limit):
    workspace, private = Path(workspace), Path(private)
    index = private / "investigations"
    records = [read_json(p) for p in sorted(index.glob("request_*.json"))]
    recent = [r for r in records if r.get("status") == "completed"][-3:]
    status = "; ".join(r["id"] + ": " + r["request"]["sample_id"]
                       + " / " + r["request"]["operation"] for r in recent) or "none"
    return task + (
        "\n\nCURRENT CONTINUATION (takes precedence over initial-session wording): "
        "This is the SAME persisted conversation, not a fresh review. "
        f"Recorded provider usage: {used}/{limit}. Recent completed investigations: {status}. "
        "Read analysis/notes.md and existing results only as needed; do not restart the review "
        "or repeat completed investigations. A file read or tool call alone is not new diagnostic progress. "
        "Update the conclusion when evidence changes. If a conflict remains and there is no useful new "
        "test, record it as unresolved and move on. Finish the remaining synthesis and save the report. "
        + ("Analysis only: do not modify any Solver code, including temporary copies, or run Gate. "
           "After writing analysis/analysis.md, submit finish_analysis via investigate.py and end. "
           if phase == "analysis" else
           "Finish the authorized candidate work and save analysis/edit_summary.md. ")
    )
