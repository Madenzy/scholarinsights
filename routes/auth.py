from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, School
from routes.utils import admin_required

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


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

        error = None
        if not school_name or not school_email:
            error = 'School name and email are required.'
        elif not username or not email or not password:
            error = 'Admin username, email and password are required.'
        elif School.query.filter_by(email=school_email).first():
            error = 'A school with this email is already registered.'
        elif User.query.filter_by(username=username).first():
            error = 'Username already taken.'
        elif User.query.filter_by(email=email).first():
            error = 'Email already registered.'

        if error:
            flash(error, 'error')
        else:
            school = School(
                name=school_name,
                email=school_email,
                phone=school_phone or None,
                address=school_address or None,
            )
            db.session.add(school)
            db.session.flush()

            admin = User(
                username=username,
                email=email,
                full_name=full_name or username,
                role='school_admin',
                school_id=school.id,
            )
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()

            login_user(admin)
            flash(f'Welcome! "{school_name}" has been registered. Set up your classes and subjects to get started.', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('auth/school_register.html')


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
