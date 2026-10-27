"""Non-mutating review of proposed cleaning actions."""
import hashlib
import json
from engineer_runtime.cleaning_policy import assess_step


def fingerprint(step):
    fields = {key: step.get(key) for key in ('action', 'column', 'parameters')}
    return hashlib.sha256(json.dumps(fields, sort_keys=True, default=str).encode()).hexdigest()


def review_plan(frame, steps):
    reviews = []
    for index, step in enumerate(steps):
        allowed, reason = assess_step(frame, step)
        reviews.append({'index': index, 'fingerprint': fingerprint(step), 'action': step.get('action'), 'column': step.get('column'), 'decision': 'auto' if allowed else 'review_required', 'reason': reason})
    return reviews
