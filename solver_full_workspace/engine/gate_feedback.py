"""Scalar-only Gate feedback; item data remains on the evaluator side."""
POLICY = 'fixed_gate_aggregate_only_v1'
FIELDS = frozenset((
    'accepted', 'n', 'parent_correct', 'candidate_correct', 'accuracy_delta',
    'fix', 'harm', 'net', 'parent_mean_frames', 'candidate_mean_frames',
    'parent_invalid', 'candidate_invalid', 'parent_qwen_calls', 'candidate_qwen_calls',
    'parent_ocr_frames', 'candidate_ocr_frames',
    'accuracy_branch_passed', 'efficiency_branch_passed',
))


def aggregate_feedback(value):
    status = value.get('status')
    if status not in ('initial_parent', 'ACCEPTED', 'REJECTED', 'INCOMPLETE', 'ENGINEERING_FAILED', 'NO_CHANGE'):
        raise ValueError('unknown aggregate Gate status')
    result = {'status': status, 'feedback_policy': POLICY}
    for key in FIELDS:
        if key in value:
            if not isinstance(value[key], (int, float, bool)):
                raise ValueError('Gate aggregate must contain only numeric metrics: ' + key)
            result[key] = value[key]
    return result
