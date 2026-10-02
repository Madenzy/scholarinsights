"""Append-only audit logging. Every route that changes data, authenticates
a user, or touches a sensitive resource calls log_audit_event() -- nothing
in this app ever updates or deletes an audit_logs row afterward.

A failed write here must never break the action being logged (matches the
philosophy already used for non-critical side effects in routes/emails.py's
send_report_published_email: a broken dependency shouldn't block the user's
real request), so every write is wrapped and failures only go to the app
logger.
"""
import json
import uuid

from flask import g, request, current_app

from models import db, AuditLog

SENSITIVE_FIELD_PATTERNS = ('password', 'secret', 'token', 'code')


def init_request_id(app):
    """Register a before_request hook that stamps every request with a
    short-lived correlation id, so multiple audit rows from one request
    (e.g. a failed login that also trips the rate limiter) can be tied
    together."""
    @app.before_request
    def _set_request_id():
        g.request_id = uuid.uuid4().hex


def _request_id():
    return getattr(g, 'request_id', None)


def _client_ip():
    try:
        return request.remote_addr
    except RuntimeError:
        return None


def _user_agent():
    try:
        ua = request.user_agent.string or ''
        return ua[:255] or None
    except RuntimeError:
        return None


def is_sensitive_field(field_name):
    lowered = field_name.lower()
    return any(p in lowered for p in SENSITIVE_FIELD_PATTERNS)


def diff_fields(changes):
    """Build a redacted changes dict from {field: (old, new)} pairs already
    collected by the caller -- the caller decides which fields it compared,
    this just applies the sensitive-field redaction consistently.

    Returns None if `changes` is empty/None (so callers can pass it straight
    through without an `if` check)."""
    if not changes:
        return None
    result = {}
    for field, (old, new) in changes.items():
        if old == new:
            continue
        if is_sensitive_field(field):
            result[field] = 'UPDATED'
        else:
            result[field] = {'old': old, 'new': new}
    return result or None


def log_audit_event(action, actor=None, school_id=None, resource_type=None,
                     resource_id=None, result='success', changes=None, extra=None):
    """Record one audit event. Never raises.

    `actor` is a User instance or None (e.g. a failed login for an unknown
    username). `changes` should already be the redacted dict from
    diff_fields(), not raw field values. `extra` is any other small, non-
    sensitive JSON-serializable context (file sizes, row counts, reasons)."""
    try:
        entry = AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_role=actor.role if actor else None,
            school_id=school_id if school_id is not None else (actor.school_id if actor else None),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            ip_address=_client_ip(),
            user_agent=_user_agent(),
            request_id=_request_id(),
            changes=json.dumps(changes) if changes else None,
            extra=json.dumps(extra) if extra else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            current_app.logger.exception('Failed to write audit log entry for action %s', action)
        except Exception:
            pass
