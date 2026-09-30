"""Returned Qwen frames for evaluation; raw attempts remain execution costs."""
FRAME_METRIC = "qwen_returned_frames_v2"


def cost_usage(result):
    usage = dict(result.get("usage", {}))
    events = result.get("meter_events")
    if events is not None:
        calls = [e for e in events
                 if e.get("kind") == "provider" and e.get("role") == "qwen"]
        if any(e.get("status") not in ("ok", "error", "pending") for e in calls):
            raise ValueError("Returned-frame metric requires provider attempt status")
        qwen = sum(e.get("frames", 0) for e in calls if e.get("status") == "ok")
        submitted = sum(e.get("frames", 0) for e in calls)
        failed = sum(e.get("frames", 0) for e in calls if e.get("status") == "error")
        pending = sum(e.get("frames", 0) for e in calls if e.get("status") == "pending")
        ocr = sum(e.get("frames", 0) for e in events if e.get("kind") == "ocr")
    elif all(k in usage for k in ("qwen_returned_frames", "qwen_submitted_frames",
                                  "qwen_failed_frames", "ocr_frames")):
        qwen, ocr = usage["qwen_returned_frames"], usage["ocr_frames"]
        submitted, failed = usage["qwen_submitted_frames"], usage["qwen_failed_frames"]
        pending = usage.get("qwen_pending_frames", 0)
    else:
        raise ValueError("Cannot infer returned frames from an old submitted-frame total")
    return dict(usage, frames=qwen, qwen_frames=qwen, ocr_frames=ocr,
                qwen_returned_frames=qwen, qwen_submitted_frames=submitted,
                qwen_failed_frames=failed, qwen_pending_frames=pending,
                frame_metric=FRAME_METRIC)
