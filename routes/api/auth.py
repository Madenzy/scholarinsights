import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from models import db, User, School, GradeBand, DEFAULT_GRADE_BANDS, hash_password
from routes.api.serializers import serialize_user
from routes.emails import send_password_reset_email, send_verification_code_email, send_mfa_code_email
from routes.validators import password_error
from routes.api.mfa import verify_mfa_code
from extensions import limiter
from audit import log_audit_event
from malware_scan import scan_bytes

api_auth_bp = Blueprint('api_auth', __name__, url_prefix='/api/auth')

RESET_SALT = 'password-reset'
RESET_MAX_AGE = 3600  # 1 hour

# Per-account login throttling. Complements Flask-Limiter's per-IP limits
# below: this persists across IPs for one targeted username, which IP-based
# limiting alone can't catch.
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

PENDING_MFA_KEY = 'pending_mfa_login'
MFA_CHALLENGE_MAX_AGE = 300  # 5 minutes

PENDING_REGISTRATION_KEY = 'pending_school_registration'
VERIFICATION_CODE_MAX_AGE = 600  # 10 minutes

DEFAULT_THEME_COLOR = '#4f46e5'
ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2MB


def _generate_code():
    return f'{secrets.randbelow(1000000):06d}'


def _logo_upload_dir():
    path = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
    os.makedirs(path, exist_ok=True)
    return path


def _delete_logo_file(filename):
    if not filename:
        return
    path = os.path.join(_logo_upload_dir(), filename)
    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _logo_type_matches(ext, header):
    """Basic magic-byte check that the file's real bytes match its claimed
    extension. This is type-spoofing protection only, not malware/virus
    scanning -- there is no AV engine involved, just a signature check so a
    renamed .exe can't pass itself off as a .png."""
    if ext in ('jpg', 'jpeg'):
        return header.startswith(b'\xff\xd8\xff')
    if ext == 'png':
        return header.startswith(b'\x89PNG\r\n\x1a\n')
    if ext == 'webp':
        return header[:4] == b'RIFF' and header[8:12] == b'WEBP'
    if ext == 'svg':
        # SVG has no binary magic number -- accept plausible XML/SVG text.
        # Note: SVG can embed <script>; this check doesn't address that
        # pre-existing risk, it only confirms the upload is actually SVG-like.
        text_start = header[:200].lstrip().lower()
        return text_start.startswith(b'<?xml') or text_start.startswith(b'<svg')
    return False


def _save_pending_logo(logo_file):
    """Save an uploaded logo under a temp name. Returns (filename, error)."""
    ext = logo_file.filename.rsplit('.', 1)[-1].lower() if '.' in logo_file.filename else ''
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        log_audit_event('FILE_REJECTED', actor=current_user if current_user.is_authenticated else None,
                         result='blocked', extra={'reason': 'extension_not_allowed', 'filename': logo_file.filename})
        return None, 'Logo must be a PNG, JPG, WEBP, or SVG image.'

    logo_file.seek(0, os.SEEK_END)
    size = logo_file.tell()
    logo_file.seek(0)
    if size > MAX_LOGO_SIZE:
        log_audit_event('FILE_REJECTED', result='blocked', extra={'reason': 'too_large', 'size': size})
        return None, 'Logo must be smaller than 2MB.'

    header = logo_file.read(256)
    logo_file.seek(0)
    if not _logo_type_matches(ext, header):
        log_audit_event('FILE_REJECTED', result='blocked',
                         extra={'reason': 'content_does_not_match_extension', 'claimed_type': ext})
        return None, 'That file does not look like a valid image. Please upload a different file.'

    data = logo_file.read()
    logo_file.seek(0)
    scan = scan_bytes(data)
    if not scan.clean:
        log_audit_event('FILE_SCAN_FAILED', result='blocked',
                         extra={'claimed_type': ext, 'detail': scan.detail})
        return None, 'That file failed a malware scan and was rejected. Please upload a different file.'
    log_audit_event('FILE_SCAN_PASSED', extra={'claimed_type': ext})

    filename = f'pending_{uuid.uuid4().hex}.{ext}'
    logo_file.save(os.path.join(_logo_upload_dir(), filename))
    log_audit_event('FILE_UPLOADED', resource_type='school_logo', extra={'type': ext, 'size': size})
    return filename, None


def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _register_failed_login(user):
    """Increment a user's failed-attempt counter; lock the account once it
    crosses the threshold. Resets the counter on lock so the next window
    starts clean after the lockout expires."""
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + LOCKOUT_DURATION
        user.failed_login_attempts = 0
        db.session.commit()
        log_audit_event('ACCOUNT_LOCKED', actor=user, result='blocked')
    else:
        db.session.commit()


def _clear_failed_logins(user):
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()


@api_auth_bp.route('/login', methods=['POST'])
@limiter.limit('10 per minute; 50 per hour')
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    remember = bool(data.get('remember'))

    user = User.query.filter_by(username=username).first()

    # Checked before verifying the password: a locked account stays locked
    # even if the right password is supplied, and this avoids spending an
    # Argon2id verify on a request that's rejected either way.
    if user and user.locked_until and user.locked_until > datetime.utcnow():
        log_audit_event('LOGIN_FAILED', actor=user, result='blocked', extra={'reason': 'account_locked'})
        return jsonify({'error': 'This account is temporarily locked due to repeated failed login attempts. Try again later.'}), 403

    if not user or not user.check_password(password):
        if user:
            _register_failed_login(user)
            log_audit_event('LOGIN_FAILED', actor=user, result='failure')
        else:
            log_audit_event('LOGIN_FAILED', result='failure', extra={'attempted_username': username})
        return jsonify({'error': 'Invalid username or password.'}), 401

    _clear_failed_logins(user)

    if not user.is_active:
        log_audit_event('LOGIN_FAILED', actor=user, result='blocked', extra={'reason': 'account_disabled'})
        return jsonify({'error': 'Your account has been disabled. Contact your administrator.'}), 403
    if user.school and not user.school.is_active:
        log_audit_event('LOGIN_FAILED', actor=user, result='blocked', extra={'reason': 'school_suspended'})
        return jsonify({'error': 'Your school account has been suspended. Contact InsightScholar support.'}), 403

    if user.mfa_enabled:
        pending = {'user_id': user.id, 'remember': remember, 'issued_at': time.time()}
        if user.mfa_method == 'email':
            code = _generate_code()
            pending['code'] = code
            send_mfa_code_email(user.email, code)
        session[PENDING_MFA_KEY] = pending
        return jsonify({'mfa_required': True, 'method': user.mfa_method})

    login_user(user, remember=remember)
    log_audit_event('LOGIN_SUCCESS', actor=user)
    return jsonify({'user': serialize_user(user)})


@api_auth_bp.route('/login/mfa-verify', methods=['POST'])
@limiter.limit('10 per 5 minutes')
def login_mfa_verify():
    pending = session.get(PENDING_MFA_KEY)
    if not pending:
        return jsonify({'error': 'Your login session expired. Please log in again.'}), 400
    if time.time() - pending['issued_at'] > MFA_CHALLENGE_MAX_AGE:
        session.pop(PENDING_MFA_KEY, None)
        return jsonify({'error': 'This login session expired. Please log in again.'}), 400

    user = User.query.get(pending['user_id'])
    if not user or not user.mfa_enabled:
        session.pop(PENDING_MFA_KEY, None)
        return jsonify({'error': 'Your login session expired. Please log in again.'}), 400

    if user.locked_until and user.locked_until > datetime.utcnow():
        session.pop(PENDING_MFA_KEY, None)
        return jsonify({'error': 'This account is temporarily locked due to repeated failed login attempts. Try again later.'}), 403

    data = request.get_json(silent=True) or {}
    entered_code = (data.get('code') or '').strip()

    if verify_mfa_code(user, pending, entered_code):
        _clear_failed_logins(user)
        session.pop(PENDING_MFA_KEY, None)
        login_user(user, remember=pending.get('remember', False))
        log_audit_event('LOGIN_SUCCESS', actor=user, extra={'mfa_method': user.mfa_method})
        return jsonify({'user': serialize_user(user)})

    _register_failed_login(user)
    log_audit_event('MFA_FAILURE', actor=user, result='failure')
    return jsonify({'error': 'Incorrect code. Please try again.'}), 400


@api_auth_bp.route('/login/mfa-resend', methods=['POST'])
@limiter.limit('3 per 5 minutes')
def login_mfa_resend():
    pending = session.get(PENDING_MFA_KEY)
    if not pending:
        return jsonify({'error': 'Your login session expired. Please log in again.'}), 400

    user = User.query.get(pending['user_id'])
    if not user or not user.mfa_enabled or user.mfa_method != 'email':
        return jsonify({'error': 'A new code cannot be sent for this account.'}), 400

    code = _generate_code()
    pending['code'] = code
    pending['issued_at'] = time.time()
    session[PENDING_MFA_KEY] = pending
    send_mfa_code_email(user.email, code)
    return jsonify({'message': 'A new code has been sent.'})


@api_auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    log_audit_event('LOGOUT', actor=current_user)
    logout_user()
    return jsonify({'ok': True})


@api_auth_bp.route('/me')
def me():
    if not current_user.is_authenticated:
        return jsonify({'user': None}), 200
    return jsonify({'user': serialize_user(current_user)})


@api_auth_bp.route('/has-schools')
def has_schools():
    return jsonify({'has_schools': School.query.count() > 0})


@api_auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit('5 per hour')
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    user = User.query.filter_by(email=email).first() if email else None
    if user:
        token = _reset_serializer().dumps(user.id, salt=RESET_SALT)
        reset_url = f"{request.host_url.rstrip('/')}/reset-password/{token}"
        send_password_reset_email(user, reset_url)
        log_audit_event('PASSWORD_RESET_REQUESTED', actor=user)
    # Same message whether or not the email exists, to avoid leaking which emails are registered.
    return jsonify({'message': 'If that email is registered, a password reset link has been sent.'})


@api_auth_bp.route('/reset-password/<token>', methods=['GET'])
def check_reset_token(token):
    try:
        _reset_serializer().loads(token, salt=RESET_SALT, max_age=RESET_MAX_AGE)
    except SignatureExpired:
        return jsonify({'valid': False, 'error': 'This password reset link has expired. Please request a new one.'})
    except BadSignature:
        return jsonify({'valid': False, 'error': 'This password reset link is invalid.'})
    return jsonify({'valid': True})


@api_auth_bp.route('/reset-password/<token>', methods=['POST'])
@limiter.limit('10 per hour')
def reset_password(token):
    try:
        user_id = _reset_serializer().loads(token, salt=RESET_SALT, max_age=RESET_MAX_AGE)
    except SignatureExpired:
        return jsonify({'error': 'This password reset link has expired. Please request a new one.'}), 400
    except BadSignature:
        return jsonify({'error': 'This password reset link is invalid.'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'This password reset link is invalid.'}), 400

    data = request.get_json(silent=True) or {}
    password = data.get('password') or ''
    confirm = data.get('confirm') or ''

    if password_error(password):
        return jsonify({'error': password_error(password)}), 400
    if password != confirm:
        return jsonify({'error': 'Passwords do not match.'}), 400

    user.set_password(password)
    db.session.commit()
    log_audit_event('PASSWORD_RESET_COMPLETED', actor=user)
    return jsonify({'message': 'Your password has been reset. Please sign in.'})


@api_auth_bp.route('/school-register', methods=['POST'])
@limiter.limit('5 per hour')
def school_register():
    form = request.form
    school_name = (form.get('school_name') or '').strip()
    school_email = (form.get('school_email') or '').strip()
    school_phone = (form.get('school_phone') or '').strip()
    school_address = (form.get('school_address') or '').strip()
    full_name = (form.get('full_name') or '').strip()
    username = (form.get('username') or '').strip()
    email = (form.get('email') or '').strip()
    password = form.get('password') or ''
    theme_color = (form.get('theme_color') or '').strip() or DEFAULT_THEME_COLOR
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', theme_color):
        theme_color = DEFAULT_THEME_COLOR

    error = None
    if not school_name or not school_email:
        error = 'School name and email are required.'
    elif not username or not email or not password:
        error = 'Admin username, email and password are required.'
    elif password_error(password):
        error = password_error(password)
    elif School.query.filter_by(email=school_email).first():
        error = 'A school with this email is already registered.'
    elif User.query.filter_by(username=username).first():
        error = 'Username already taken.'
    elif User.query.filter_by(email=email).first():
        error = 'Email already registered.'

    pending_logo_filename = None
    logo_file = request.files.get('logo')
    if not error and logo_file and logo_file.filename:
        pending_logo_filename, logo_error = _save_pending_logo(logo_file)
        if logo_error:
            error = logo_error

    if error:
        return jsonify({'error': error}), 400

    # Clean up a logo left over from an earlier, abandoned attempt at this form.
    old_pending = session.get(PENDING_REGISTRATION_KEY)
    if old_pending:
        _delete_logo_file(old_pending.get('logo_filename'))

    code = _generate_code()
    session[PENDING_REGISTRATION_KEY] = {
        'school_name': school_name,
        'school_email': school_email,
        'school_phone': school_phone or None,
        'school_address': school_address or None,
        'theme_color': theme_color,
        'logo_filename': pending_logo_filename,
        'full_name': full_name or username,
        'username': username,
        'email': email,
        'password_hash': hash_password(password),
        'code': code,
        'issued_at': time.time(),
    }
    send_verification_code_email(email, code)
    return jsonify({'message': f'We sent a verification code to {email}.', 'email': email})


@api_auth_bp.route('/pending-registration')
def pending_registration():
    pending = session.get(PENDING_REGISTRATION_KEY)
    if not pending:
        return jsonify({'pending': None})
    return jsonify({'pending': {'email': pending['email']}})


@api_auth_bp.route('/verify-email/resend', methods=['POST'])
@limiter.limit('3 per 5 minutes')
def resend_verification_code():
    pending = session.get(PENDING_REGISTRATION_KEY)
    if not pending:
        return jsonify({'error': 'Please start your school registration again.'}), 400

    code = _generate_code()
    pending['code'] = code
    pending['issued_at'] = time.time()
    session[PENDING_REGISTRATION_KEY] = pending
    send_verification_code_email(pending['email'], code)
    return jsonify({'message': 'A new verification code has been sent.'})


@api_auth_bp.route('/verify-email', methods=['POST'])
@limiter.limit('10 per 5 minutes')
def verify_email():
    pending = session.get(PENDING_REGISTRATION_KEY)
    if not pending:
        return jsonify({'error': 'Please start your school registration again.'}), 400

    data = request.get_json(silent=True) or {}
    entered_code = (data.get('code') or '').strip()

    if time.time() - pending['issued_at'] > VERIFICATION_CODE_MAX_AGE:
        return jsonify({'error': 'This code has expired. Request a new one below.'}), 400
    if not entered_code or entered_code != pending['code']:
        return jsonify({'error': 'Incorrect code. Please try again.'}), 400

    if School.query.filter_by(email=pending['school_email']).first():
        _delete_logo_file(pending.get('logo_filename'))
        session.pop(PENDING_REGISTRATION_KEY, None)
        return jsonify({'error': 'A school with this email is already registered.', 'restart': True}), 409
    if User.query.filter_by(username=pending['username']).first():
        _delete_logo_file(pending.get('logo_filename'))
        session.pop(PENDING_REGISTRATION_KEY, None)
        return jsonify({'error': 'Username already taken.', 'restart': True}), 409
    if User.query.filter_by(email=pending['email']).first():
        _delete_logo_file(pending.get('logo_filename'))
        session.pop(PENDING_REGISTRATION_KEY, None)
        return jsonify({'error': 'Email already registered.', 'restart': True}), 409

    school = School(
        name=pending['school_name'],
        email=pending['school_email'],
        phone=pending['school_phone'],
        address=pending['school_address'],
        theme_color=pending.get('theme_color') or DEFAULT_THEME_COLOR,
    )
    db.session.add(school)
    db.session.flush()

    for i, (letter, min_score, remark, is_pass) in enumerate(DEFAULT_GRADE_BANDS):
        db.session.add(GradeBand(
            school_id=school.id, letter=letter, min_score=min_score,
            remark=remark, is_pass=is_pass, sort_order=i,
        ))

    pending_logo = pending.get('logo_filename')
    if pending_logo:
        ext = pending_logo.rsplit('.', 1)[-1]
        final_filename = f'school_{school.id}.{ext}'
        os.replace(
            os.path.join(_logo_upload_dir(), pending_logo),
            os.path.join(_logo_upload_dir(), final_filename),
        )
        school.logo_filename = final_filename

    admin = User(
        username=pending['username'],
        email=pending['email'],
        full_name=pending['full_name'],
        role='school_admin',
        school_id=school.id,
    )
    admin.password_hash = pending['password_hash']
    db.session.add(admin)
    db.session.commit()

    session.pop(PENDING_REGISTRATION_KEY, None)
    login_user(admin)
    log_audit_event('SCHOOL_CREATED', actor=admin, school_id=school.id, resource_type='school', resource_id=school.id)
    log_audit_event('LOGIN_SUCCESS', actor=admin, extra={'via': 'school_registration'})
    return jsonify({'user': serialize_user(admin)})
