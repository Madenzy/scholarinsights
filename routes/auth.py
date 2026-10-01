import os
import re
import secrets
import time
import uuid

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash
from models import db, User, School
from routes.utils import admin_required
from routes.emails import send_password_reset_email, send_verification_code_email
from routes.validators import password_error

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

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


def _after_login_url(user):
    if user.is_super_admin:
        return url_for('superadmin.index')
    if user.is_portal_user:
        return url_for('portal.dashboard')
    return url_for('dashboard.index')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(_after_login_url(current_user))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been disabled. Contact your administrator.', 'error')
            elif user.school and not user.school.is_active:
                flash('Your school account has been suspended. Contact InsightScholar support.', 'error')
            else:
                login_user(user, remember=remember)
                return redirect(request.args.get('next') or _after_login_url(user))
        else:
            flash('Invalid username or password.', 'error')

    has_schools = School.query.count() > 0
    return render_template('auth/login.html', has_schools=has_schools)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(_after_login_url(current_user))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        user = User.query.filter_by(email=email).first() if email else None
        if user:
            token = _reset_serializer().dumps(user.id, salt=RESET_SALT)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            send_password_reset_email(user, reset_url)
        # Same message whether or not the email exists, to avoid leaking which emails are registered.
        flash('If that email is registered, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(_after_login_url(current_user))

    try:
        user_id = _reset_serializer().loads(token, salt=RESET_SALT, max_age=RESET_MAX_AGE)
    except SignatureExpired:
        flash('This password reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('This password reset link is invalid.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.get(user_id)
    if not user:
        flash('This password reset link is invalid.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if password_error(password):
            flash(password_error(password), 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(password)
            db.session.commit()
            flash('Your password has been reset. Please sign in.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/school/register', methods=['GET', 'POST'])
def school_register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        school_name = request.form.get('school_name', '').strip()
        school_email = request.form.get('school_email', '').strip()
        school_phone = request.form.get('school_phone', '').strip()
        school_address = request.form.get('school_address', '').strip()
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        theme_color = request.form.get('theme_color', '').strip() or DEFAULT_THEME_COLOR
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
            flash(error, 'error')
        else:
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
            flash(f'We sent a verification code to {email}.', 'info')
            return redirect(url_for('auth.verify_email'))

    return render_template('auth/school_register.html', default_theme_color=DEFAULT_THEME_COLOR)


@auth_bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    if current_user.is_authenticated:
        return redirect(_after_login_url(current_user))

    pending = session.get(PENDING_REGISTRATION_KEY)
    if not pending:
        flash('Please start your school registration again.', 'error')
        return redirect(url_for('auth.school_register'))

    if request.method == 'POST':
        if request.form.get('action') == 'resend':
            code = _generate_code()
            pending['code'] = code
            pending['issued_at'] = time.time()
            session[PENDING_REGISTRATION_KEY] = pending
            send_verification_code_email(pending['email'], code)
            flash('A new verification code has been sent.', 'info')
            return redirect(url_for('auth.verify_email'))

        entered_code = request.form.get('code', '').strip()

        if time.time() - pending['issued_at'] > VERIFICATION_CODE_MAX_AGE:
            flash('This code has expired. Request a new one below.', 'error')
        elif not entered_code or entered_code != pending['code']:
            flash('Incorrect code. Please try again.', 'error')
        elif School.query.filter_by(email=pending['school_email']).first():
            flash('A school with this email is already registered.', 'error')
            _delete_logo_file(pending.get('logo_filename'))
            session.pop(PENDING_REGISTRATION_KEY, None)
            return redirect(url_for('auth.school_register'))
        elif User.query.filter_by(username=pending['username']).first():
            flash('Username already taken.', 'error')
            _delete_logo_file(pending.get('logo_filename'))
            session.pop(PENDING_REGISTRATION_KEY, None)
            return redirect(url_for('auth.school_register'))
        elif User.query.filter_by(email=pending['email']).first():
            flash('Email already registered.', 'error')
            _delete_logo_file(pending.get('logo_filename'))
            session.pop(PENDING_REGISTRATION_KEY, None)
            return redirect(url_for('auth.school_register'))
        else:
            school = School(
                name=pending['school_name'],
                email=pending['school_email'],
                phone=pending['school_phone'],
                address=pending['school_address'],
                theme_color=pending.get('theme_color') or DEFAULT_THEME_COLOR,
            )
            db.session.add(school)
            db.session.flush()

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
            flash(f'Email confirmed! "{school.name}" has been registered. Set up your classes and subjects to get started.', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('auth/verify_email.html', email=pending['email'])


# Admin-only: add a teacher to the current school
@auth_bp.route('/add-teacher', methods=['GET', 'POST'])
@login_required
@admin_required
def add_teacher():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('Username, email and password are required.', 'error')
        elif password_error(password):
            flash(password_error(password), 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            user = User(
                username=username,
                email=email,
                full_name=full_name or username,
                role='teacher',
                school_id=current_user.school_id,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'Teacher account created for {full_name or username}.', 'success')
            return redirect(url_for('users.index'))

    return render_template('users/add_teacher.html')
