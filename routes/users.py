from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, User, Student
from routes.utils import school_id, admin_required

users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/')
@login_required
@admin_required
def index():
    sid = school_id()
    staff = User.query.filter_by(school_id=sid).filter(
        User.role.in_(['school_admin', 'teacher'])
    ).order_by(User.role, User.full_name).all()
    parents = User.query.filter_by(school_id=sid, role='parent').order_by(User.full_name).all()
    student_accounts = User.query.filter_by(school_id=sid, role='student').order_by(User.full_name).all()
    return render_template('users/index.html', staff=staff, parents=parents, student_accounts=student_accounts)


@users_bp.route('/add-parent', methods=['GET', 'POST'])
@login_required
@admin_required
def add_parent():
    sid = school_id()
    students = Student.query.filter_by(school_id=sid).order_by(Student.last_name, Student.first_name).all()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        child_ids = request.form.getlist('child_ids')
        child_ids = [int(i) for i in child_ids if i.isdigit()]

        error = None
        if not username or not password:
            error = 'Username and password are required.'
        elif not child_ids:
            error = 'Select at least one child.'
        elif User.query.filter_by(username=username).first():
            error = 'Username already taken.'

        if error:
            flash(error, 'error')
        else:
            parent = User(
                username=username,
                email=email or f'{username}@parent.local',
                full_name=full_name or username,
                role='parent',
                school_id=sid,
            )
            parent.set_password(password)
            children = Student.query.filter(
                Student.id.in_(child_ids),
                Student.school_id == sid,
            ).all()
            parent.children = children
            db.session.add(parent)
            db.session.commit()
            flash(f'Parent account created for {parent.display_name}.', 'success')
            return redirect(url_for('users.index'))

    return render_template('users/add_parent.html', students=students)


@users_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    sid = school_id()
    user = User.query.filter_by(id=id, school_id=sid).first_or_404()

    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('users.index'))

    # If deleting a student account, unlink from the student record
    if user.role == 'student' and user.student_profile:
        user.student_profile.user_id = None

    db.session.delete(user)
    db.session.commit()
    flash(f'Account for {user.display_name} deleted.', 'success')
    return redirect(url_for('users.index'))
