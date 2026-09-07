import csv
import io
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import db, Student, Class, User
from routes.utils import school_id, staff_required, admin_required
from routes import student_import
from routes.student_import import parse_upload, normalize_gender, parse_date, split_full_name

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


@students_bp.route('/import', methods=['GET', 'POST'])
@login_required
@staff_required
def import_students():
    sid = school_id()
    classes = Class.query.filter_by(school_id=sid).order_by(Class.name).all()

    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Please choose a file to import.', 'error')
            return render_template('students/import.html', classes=classes)

        try:
            rows = parse_upload(file)
        except student_import.ImportError_ as exc:
            flash(str(exc), 'error')
            return render_template('students/import.html', classes=classes)

        if not rows:
            flash('No data rows found in the file.', 'error')
            return render_template('students/import.html', classes=classes)

        classes_by_name = {c.name.strip().lower(): c.id for c in classes}
        classes_by_grade = {
            c.grade_level.strip().lower(): c.id for c in classes if c.grade_level
        }
        existing_reg_numbers = {
            r.reg_number.lower()
            for r in Student.query.filter_by(school_id=sid).with_entities(Student.reg_number)
        }

        imported = 0
        skipped = 0
        errors = []

        for i, row in enumerate(rows, start=2):
            reg_number = str(row.get('reg_number') or '').strip()
            first_name = str(row.get('first_name') or '').strip()
            last_name = str(row.get('last_name') or '').strip()

            if (not first_name and not last_name) and row.get('full_name'):
                first_name, last_name = split_full_name(row['full_name'])

            gender = normalize_gender(row.get('gender'))
            class_name = str(row.get('class') or '').strip()

            if not reg_number or not first_name or not last_name:
                errors.append(f'Row {i}: missing registration number or name.')
                continue
            if reg_number.lower() in existing_reg_numbers:
                skipped += 1
                continue

            try:
                dob = parse_date(row.get('date_of_birth'))
            except ValueError as exc:
                errors.append(f'Row {i}: invalid date of birth "{exc}".')
                continue

            class_id = None
            if class_name:
                class_id = classes_by_name.get(class_name.lower()) or classes_by_grade.get(class_name.lower())
                if not class_id:
                    errors.append(f'Row {i}: class "{class_name}" not found, left unassigned.')

            student = Student(
                reg_number=reg_number,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                gender=gender,
                class_id=class_id,
                school_id=sid,
            )
            db.session.add(student)
            existing_reg_numbers.add(reg_number.lower())
            imported += 1

        if imported:
            db.session.commit()

        if imported:
            flash(f'{imported} student{"s" if imported != 1 else ""} imported successfully.', 'success')
        if skipped:
            flash(f'{skipped} row{"s" if skipped != 1 else ""} skipped (registration number already exists).', 'info')
        for err in errors[:20]:
            flash(err, 'error' if 'not found' not in err else 'info')

        if imported:
            return redirect(url_for('students.index'))

    return render_template('students/import.html', classes=classes)


@students_bp.route('/import/template')
@login_required
@staff_required
def import_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['reg_number', 'first_name', 'last_name', 'gender', 'date_of_birth', 'class'])
    writer.writerow(['2026/001', 'Jane', 'Doe', 'Female', '2012-05-14', 'Form 2A'])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=students_import_template.csv'},
    )


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
