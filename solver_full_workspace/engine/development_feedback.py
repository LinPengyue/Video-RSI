"""Gate feedback policy: per-item Gate exports are disabled."""


def export_feedback(*args, **kwargs):
    raise ValueError('Per-item Gate feedback is disabled; use scalar aggregate_feedback only')
