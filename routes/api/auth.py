import os
import re
import secrets
import time
import uuid

from flask import Blueprint, jsonify, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash

from models import db, User, School, GradeBand, DEFAULT_GRADE_BANDS
from routes.api.serializers import serialize_user
from routes.emails import send_password_reset_email, send_verification_code_email
from routes.validators import password_error

api_auth_bp = Blueprint('api_auth', __name__, url_prefix='/api/auth')

RESET_SALT = 'password-reset'
RESET_MAX_AGE = 3600  # 1 hour

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


def _save_pending_logo(logo_file):
    """Save an uploaded logo under a temp name. Returns (filename, error)."""
    ext = logo_file.filename.rsplit('.', 1)[-1].lower() if '.' in logo_file.filename else ''
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return None, 'Logo must be a PNG, JPG, WEBP, or SVG image.'

    logo_file.seek(0, os.SEEK_END)
    size = logo_file.tell()
    logo_file.seek(0)
    if size > MAX_LOGO_SIZE:
        return None, 'Logo must be smaller than 2MB.'

    filename = f'pending_{uuid.uuid4().hex}.{ext}'
    logo_file.save(os.path.join(_logo_upload_dir(), filename))
    return filename, None


def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


@api_auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    remember = bool(data.get('remember'))

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid username or password.'}), 401
    if not user.is_active:
        return jsonify({'error': 'Your account has been disabled. Contact your administrator.'}), 403
    if user.school and not user.school.is_active:
        return jsonify({'error': 'Your school account has been suspended. Contact InsightScholar support.'}), 403

    login_user(user, remember=remember)
    return jsonify({'user': serialize_user(user)})


@api_auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
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
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    user = User.query.filter_by(email=email).first() if email else None
    if user:
        token = _reset_serializer().dumps(user.id, salt=RESET_SALT)
        reset_url = f"{request.host_url.rstrip('/')}/reset-password/{token}"
        send_password_reset_email(user, reset_url)
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
    return jsonify({'message': 'Your password has been reset. Please sign in.'})


@api_auth_bp.route('/school-register', methods=['POST'])
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
        'password_hash': generate_password_hash(password),
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
    return jsonify({'user': serialize_user(admin)})
