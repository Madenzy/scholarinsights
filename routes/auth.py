from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import logout_user, login_required, current_user
from models import db, User
from routes.utils import admin_required
from routes.validators import generate_password
from routes.emails import send_account_credentials_email
from audit import log_audit_event

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Login, registration, and password-reset pages now live in the React app
# (see frontend/src/pages/auth). These routes only exist so links/emails built
# with url_for('auth.*') from pages that are still Flask-rendered (the public
# landing/legal pages) keep working, by bouncing to the SPA route.
_SPA_REDIRECTS = {
    'login': '/login',
    'forgot_password': '/forgot-password',
    'school_register': '/register',
    'verify_email': '/verify-email',
}


@auth_bp.route('/login')
def login():
    return redirect(_SPA_REDIRECTS['login'])


@auth_bp.route('/forgot-password')
def forgot_password():
    return redirect(_SPA_REDIRECTS['forgot_password'])


@auth_bp.route('/reset-password/<token>')
def reset_password(token):
    return redirect(f'/reset-password/{token}')


@auth_bp.route('/school/register')
def school_register():
    return redirect(_SPA_REDIRECTS['school_register'])


@auth_bp.route('/verify-email')
def verify_email():
    return redirect(_SPA_REDIRECTS['verify_email'])


@auth_bp.route('/logout')
@login_required
def logout():
    log_audit_event('LOGOUT', actor=current_user)
    logout_user()
    return redirect(_SPA_REDIRECTS['login'])


# Admin-only: add a teacher to the current school.
# Still Flask-rendered until the Users/Teachers section moves to React.
@auth_bp.route('/add-teacher', methods=['GET', 'POST'])
@login_required
@admin_required
def add_teacher():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()

        if not username or not email:
            flash('Username and email are required.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
        else:
            password = generate_password()
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
            log_audit_event('USER_CREATED', actor=current_user, school_id=current_user.school_id,
                             resource_type='user', resource_id=user.id, extra={'role': 'teacher'})

            emailed = send_account_credentials_email(user, password, 'teacher')
            return render_template(
                'users/account_created.html',
                display_name=user.display_name, username=username, password=password, emailed=emailed,
                back_url=url_for('users.teachers'), back_label='Teachers',
            )

    return render_template('users/add_teacher.html')
