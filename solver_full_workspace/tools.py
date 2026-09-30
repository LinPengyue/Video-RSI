"""Initial visual observation and OCR tools."""
import json
from math import ceil
if __package__:
    from .time_utils import seconds
else:
    from time_utils import seconds


class ToolArgumentError(ValueError):
    """Repairable before media/provider execution; not a provider failure."""


def transcript_view(result):
    """All utterances and segment times, without per-word preprocessing metadata.

    The service trace/source file retains the original objects. This is a
    lossless spoken-text view, not a summary, retrieval result or length cap.
    """
    return dict(result, segments=[{key: segment[key] for key in ('start', 'end', 'text')}
                                 for segment in result.get('segments', [])])


class ToolBox:
    def __init__(self, item, services):
        self.item, self.services = item, services
        self.transcript_read = False

    def descriptions(self):
        duration = float(self.item['duration'])
        time_format = (' Times: numeric seconds or explicit "MM:SS"/"HH:MM:SS" strings; '
                       f'0 <= start < end <= {duration:g} seconds. No automatic clipping or splitting.')
        return {
            "overview": "Uniformly observe the whole video, exactly 32 frames; arguments {}. Sparse scene search, not continuous action footage.",
            "scan_interval": f'Coarse localization within a selected interval: 32 < end-start <= {duration / 2:g} seconds (half video). Exactly 16 uniform frames; start,end.' + (' Unavailable: this video has no interval satisfying these bounds.' if duration <= 64 else '') + time_format,
            "inspect_interval": "Observe local action progression and details: 0 < end-start <=16 seconds. Uniform samples across the entire interval, at most8 frames; count is automatic (min(8, ceil(duration in seconds))), do not supply count. Not fixed 1 FPS or continuous video; brief actions can be missed. Arguments start,end. Longer intervals require valid scan_interval or separately chosen short windows." + time_format,
            "read_text": "Local multilingual OCR, 1fps over 0 < end-start <=16 seconds. start,end. Returns timestamp,bbox,text,confidence. Locate the text first if its position is unknown." + time_format,
            "read_transcript": "Read all timestamped speech segments once, no keyword retrieval. {}.",
        }

    def normalize_arguments(self, name, args):
        """Single source for pre-dispatch repair and execution validation. No IO."""
        if name not in self.descriptions():
            raise ToolArgumentError('unknown tool ' + str(name) + '; choose a listed tool')
        if not isinstance(args, dict):
            raise ToolArgumentError('arguments must be an object')
        allowed = set() if name in ('overview', 'read_transcript') else {'start', 'end'}
        if set(args) - allowed:
            raise ToolArgumentError(f'{name}: unsupported arguments {sorted(set(args) - allowed)}; allowed {sorted(allowed)}')
        if not allowed:
            return {}
        if not {'start', 'end'} <= set(args):
            raise ToolArgumentError(f'{name} requires start and end. ' + self.descriptions()[name])
        try:
            start, end = seconds(args['start']), seconds(args['end'])
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        duration = float(self.item['duration'])
        if not 0 <= start < end <= duration:
            raise ToolArgumentError(f'{name}: requested start={start:g}, end={end:g} seconds; require 0 <= start < end <= {duration:g}. Check time notation; no endpoint is swapped or clipped.')
        span = end - start
        normalized = {'start': start, 'end': end}
        if name == 'scan_interval' and not 32 < span <= duration / 2:
            raise ToolArgumentError(f'scan_interval requested {span:g}s; require 32 < span <= {duration / 2:g}s. Choose a valid coarse interval, short inspection, or overview; nothing was observed.')
        if name == 'inspect_interval':
            if span > 16:
                raise ToolArgumentError(f'inspect_interval requested {span:g}s; maximum 16s and at most8 uniform frames. Choose scan_interval if valid, or select a short window <=16s; no frames were sampled.')
        if name == 'read_text' and span > 16:
            raise ToolArgumentError(f'read_text requested {span:g}s; maximum 16s at 1fps. Locate the text first or select a <=16s window; no OCR was performed.')
        return normalized

    def visual(self, start, end, count, purpose):
        if purpose == "inspect_interval":
            sampling = {"start": start, "end": end, "count": min(8, ceil(end - start))}
            sampling_note = (
                "inspect_interval: at most8 uniform frames across a short clip of at most16 seconds "
                "for following local action progression and checking details. These are sampled "
                "moments, not continuous video; brief actions can still fall between samples.")
        else:
            sampling = {"start": start, "end": end, "count": count}
            sampling_note = (
                "overview: 32 uniform frames across the whole video, sparsely spaced to find candidate "
                "scenes; they are not continuous action footage."
                if purpose == "overview" else
                "scan_interval: 16 uniform frames across the selected interval to narrow the target "
                "location; this is coarse localization, not continuous action footage.")
        frames = self.services.call("sample_frames", sampling)
        prompt = (
            sampling_note + "\n"
            "Chronological frame order alone does not establish what happened immediately next.\n"
            +
            "Observe the supplied timestamped frames for the question and the distinctions between its options. "
            "Report actual visible details that help distinguish the options, with their exact supplied numeric second anchors. "
            "Keep decimal seconds as decimal seconds: never rewrite 15.1 seconds as 15:10. "
            "Options are hypotheses, not observed facts; do not fill in a scene from their wording. "
            "Separate visible observations from uncertain interpretations. Say when a relevant detail is unclear, "
            "unreadable or not captured by these samples. Not seen in sampled frames does not mean absent from the video. "
            "Describe supported identities, actions, visible text and temporal relations when relevant; "
            "do not invent events or transitions between unsampled moments. "
            "Return observations for the reasoning agent, not an option verdict. "
            "Preserve useful detail; there is no fixed fact-count limit."
            + "\n" + json.dumps({
                "question": self.item["question"], "options": self.item["options"],
                "purpose": {"overview": "global overview", "scan_interval": "coarse localization",
                            "inspect_interval": "local verification"}[purpose],
            }, ensure_ascii=False)
        )
        result = self.services.call("qwen", {"frames": [f["id"] for f in frames], "prompt": prompt})
        return {"frames": frames, "perception": result, "sampling_note": sampling_note}

    def execute(self, name, args):
        args = self.normalize_arguments(name, args)
        duration = self.item["duration"]
        if name == "read_transcript":
            if self.transcript_read:
                return {"already_read": True, "message": "Full transcript remains in memory."}
            result = self.services.call("asr", {})
            self.transcript_read = True
            return transcript_view(result)
        if name == "overview":
            return self.visual(0, duration, 32, "overview")
        start, end = args['start'], args['end']
        if name == "scan_interval":
            return self.visual(start, end, 16, "scan_interval")
        if name == "inspect_interval":
            return self.visual(start, end, None, "inspect_interval")
        if name == "read_text":
            timestamps = [start + i for i in range(16) if start + i < end]
            frames = self.services.call("sample_frames", {"timestamps": timestamps})
            raw = self.services.call("ocr", {"frames": [f["id"] for f in frames]})
            seen, rows = set(), []
            for row in raw:
                key = row["text"].strip()
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
            return {"detections": rows, "raw_detections": raw}
