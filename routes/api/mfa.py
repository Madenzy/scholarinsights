import base64
import json
import secrets
from io import BytesIO

import pyotp
import qrcode
from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user

from models import db, hash_password, verify_hash
from extensions import limiter
from audit import log_audit_event

api_mfa_bp = Blueprint('api_mfa', __name__, url_prefix='/api/auth/mfa')

PENDING_TOTP_SECRET_KEY = 'pending_totp_secret'
BACKUP_CODE_COUNT = 10


def _staff_only():
    if not current_user.is_staff and not current_user.is_super_admin:
        return jsonify({'error': 'Two-factor authentication is only available for staff and admin accounts.'}), 403
    return None


def _generate_backup_codes():
    """Return (plain_codes, hashed_json) -- plain codes are shown to the user
    exactly once; only the hashes are ever persisted."""
    plain_codes = [f'{secrets.token_hex(4)}-{secrets.token_hex(2)}'.upper() for _ in range(BACKUP_CODE_COUNT)]
    hashed = [hash_password(code) for code in plain_codes]
    return plain_codes, json.dumps(hashed)


def _consume_backup_code(user, code):
    """Check `code` against the user's stored backup codes; if it matches,
    remove that one (single use) and persist. Returns True on match."""
    if not user.mfa_backup_codes or not code:
        return False
    hashed_codes = json.loads(user.mfa_backup_codes)
    for stored_hash in hashed_codes:
        if verify_hash(stored_hash, code.strip().upper()):
            hashed_codes.remove(stored_hash)
            user.mfa_backup_codes = json.dumps(hashed_codes)
            db.session.commit()
            return True
    return False


def verify_mfa_code(user, pending, code):
    """Verify a login-challenge code against whichever of the user's MFA
    methods applies, falling back to a backup code either way. `pending` is
    the session blob from the login interstitial (carries the emailed code
    for the 'email' method)."""
    code = (code or '').strip()
    if not code:
        return False
    if user.mfa_method == 'totp' and user.mfa_totp_secret:
        if pyotp.TOTP(user.mfa_totp_secret).verify(code, valid_window=1):
            return True
    elif user.mfa_method == 'email':
        if pending.get('code') and secrets.compare_digest(code, pending['code']):
            return True
    return _consume_backup_code(user, code)


def _totp_qr_data_uri(provisioning_uri):
    img = qrcode.make(provisioning_uri, box_size=6, border=1)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


@api_mfa_bp.route('/status')
@login_required
def status():
    return jsonify({'enabled': current_user.mfa_enabled, 'method': current_user.mfa_method})


@api_mfa_bp.route('/enroll/totp', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def enroll_totp():
    denied = _staff_only()
    if denied:
        return denied

    secret = pyotp.random_base32()
    session[PENDING_TOTP_SECRET_KEY] = secret
    uri = pyotp.TOTP(secret).provisioning_uri(name=current_user.email, issuer_name='InsightScholar')
    return jsonify({'secret': secret, 'qr_data_uri': _totp_qr_data_uri(uri)})


@api_mfa_bp.route('/enroll/totp/confirm', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def enroll_totp_confirm():
    denied = _staff_only()
    if denied:
        return denied

    secret = session.get(PENDING_TOTP_SECRET_KEY)
    if not secret:
        return jsonify({'error': 'Start enrollment again.'}), 400

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return jsonify({'error': 'Incorrect code. Please try again.'}), 400

    plain_codes, hashed_codes = _generate_backup_codes()
    current_user.mfa_totp_secret = secret
    current_user.mfa_method = 'totp'
    current_user.mfa_enabled = True
    current_user.mfa_backup_codes = hashed_codes
    db.session.commit()
    session.pop(PENDING_TOTP_SECRET_KEY, None)
    log_audit_event('MFA_ENABLED', actor=current_user, extra={'method': 'totp'})

    return jsonify({'enabled': True, 'method': 'totp', 'backup_codes': plain_codes})


@api_mfa_bp.route('/enroll/email', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def enroll_email():
    denied = _staff_only()
    if denied:
        return denied

    plain_codes, hashed_codes = _generate_backup_codes()
    current_user.mfa_method = 'email'
    current_user.mfa_enabled = True
    current_user.mfa_totp_secret = None
    current_user.mfa_backup_codes = hashed_codes
    db.session.commit()
    log_audit_event('MFA_ENABLED', actor=current_user, extra={'method': 'email'})

    return jsonify({'enabled': True, 'method': 'email', 'backup_codes': plain_codes})


@api_mfa_bp.route('/disable', methods=['POST'])
@login_required
@limiter.limit('10 per hour')
def disable():
    data = request.get_json(silent=True) or {}
    password = data.get('password') or ''
    if not current_user.check_password(password):
        return jsonify({'error': 'Incorrect password.'}), 401

    current_user.mfa_enabled = False
    current_user.mfa_method = None
    current_user.mfa_totp_secret = None
    current_user.mfa_backup_codes = None
    db.session.commit()
    log_audit_event('MFA_DISABLED', actor=current_user)
    return jsonify({'enabled': False})
