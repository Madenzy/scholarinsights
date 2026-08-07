from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import db, Student, Class, User
from routes.utils import school_id, staff_required, admin_required

students_bp = Blueprint('students', __name__, url_prefix='/students')


@students_bp.route('/')
@login_required
@staff_required
def index():
    sid = school_id()
    q = request.args.get('q', '').strip()
    class_id = request.args.get('class_id', type=int)

    query = Student.query.filter_by(school_id=sid)
    if q:
        query = query.filter(
            or_(
                Student.first_name.ilike(f'%{q}%'),
                Student.last_name.ilike(f'%{q}%'),
                Student.reg_number.ilike(f'%{q}%'),
            )
        )
    if class_id:
        query = query.filter_by(class_id=class_id)

    students = query.order_by(Student.last_name, Student.first_name).all()
    classes = Class.query.filter_by(school_id=sid).order_by(Class.name).all()
    return render_template(
        'students/index.html',
        students=students, classes=classes, q=q, class_id=class_id,
    )


@students_bp.route('/add', methods=['GET', 'POST'])
@login_required
@staff_required
def add():
    sid = school_id()
    classes = Class.query.filter_by(school_id=sid).order_by(Class.name).all()
    if request.method == 'POST':
        reg_number = request.form.get('reg_number', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        gender = request.form.get('gender', '').strip()
        class_id = request.form.get('class_id', type=int)
        dob_str = request.form.get('date_of_birth', '').strip()

        if not reg_number or not first_name or not last_name:
            flash('Registration number, first name and last name are required.', 'error')
        elif Student.query.filter_by(reg_number=reg_number, school_id=sid).first():
            flash('Registration number already exists in this school.', 'error')
        else:
            student = Student(
                reg_number=reg_number,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date.fromisoformat(dob_str) if dob_str else None,
                gender=gender,
                class_id=class_id or None,
                school_id=sid,
            )
            db.session.add(student)
            db.session.commit()
            flash(f'{student.full_name} added successfully.', 'success')
            return redirect(url_for('students.index'))

    return render_template('students/add.html', classes=classes)


@students_bp.route('/<int:id>')
@login_required
@staff_required
def detail(id):
    student = Student.query.filter_by(id=id, school_id=school_id()).first_or_404()
    return render_template('students/detail.html', student=student)


@students_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@staff_required
def edit(id):
    sid = school_id()
    student = Student.query.filter_by(id=id, school_id=sid).first_or_404()
    classes = Class.query.filter_by(school_id=sid).order_by(Class.name).all()
    if request.method == 'POST':
        student.first_name = request.form.get('first_name', '').strip()
        student.last_name = request.form.get('last_name', '').strip()
        student.gender = request.form.get('gender', '').strip()
        student.class_id = request.form.get('class_id', type=int) or None
        dob_str = request.form.get('date_of_birth', '').strip()
        student.date_of_birth = date.fromisoformat(dob_str) if dob_str else None
        db.session.commit()
        flash('Student updated.', 'success')
        return redirect(url_for('students.detail', id=id))
    return render_template('students/edit.html', student=student, classes=classes)


@students_bp.route('/<int:id>/create-account', methods=['GET', 'POST'])
@login_required
@admin_required
def create_account(id):
    student = Student.query.filter_by(id=id, school_id=school_id()).first_or_404()

    if student.has_account:
        flash('This student already has a login account.', 'info')
        return redirect(url_for('students.detail', id=id))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        else:
            user = User(
                username=username,
                email=email or f'{username}@student.local',
                full_name=student.full_name,
                role='student',
                school_id=school_id(),
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            student.user_id = user.id
            db.session.commit()
            flash(f'Login account created for {student.full_name}.', 'success')
            return redirect(url_for('students.detail', id=id))

    return render_template('students/create_account.html', student=student)


@students_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    student = Student.query.filter_by(id=id, school_id=school_id()).first_or_404()
    name = student.full_name
    db.session.delete(student)
    db.session.commit()
    flash(f'{name} has been deleted.', 'success')
    return redirect(url_for('students.index'))
