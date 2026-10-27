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


def approved_steps(frame, steps, approvals=None):
    """Return executable steps; approved requests still obey the safety policy.

    Destructive operations require a separate, purpose-built executor.
    """
    approvals = set(approvals or [])
    accepted, deferred = [], []
    for item in review_plan(frame, steps):
        step = steps[item['index']]
        if item['decision'] == 'auto':
            accepted.append(step)
        else:
            deferred.append({**item, 'user_approved': item['fingerprint'] in approvals,
                             'reason': item['reason'] + '; safe executor unavailable'})
    return accepted, deferred


def validate_result(before, after, execution_log):
    """Check row counts, schema changes and execution failures."""
    return {
        'rows_before': int(len(before)),
        'rows_after': int(len(after)),
        'columns_preserved': list(before.columns) == list(after.columns),
        'failed_steps': sum(x.get('status') == 'failed' for x in execution_log),
        'review_required_steps': sum(x.get('status') == 'review_required' for x in execution_log),
        'applied_steps': sum(x.get('status') == 'applied' for x in execution_log),
    }


def audit_record(steps, execution_log, validation):
    """Record operation metadata without storing row-level personal information."""
    import uuid
    return {
        'run_id': str(uuid.uuid4()),
        'steps': [{'fingerprint': fingerprint(s), 'action': s.get('action'),
                   'column': s.get('column')} for s in steps],
        'execution': execution_log,
        'validation': validation,
    }


def preview_plan(frame, steps):
    """Provide non-destructive preview metadata and risk classification."""
    return {
        'row_count': int(len(frame)),
        'column_count': int(len(frame.columns)),
        'reviews': review_plan(frame, steps),
        'source_unchanged': True,
    }
