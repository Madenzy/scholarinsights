import csv
import io
import zipfile
from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import db, Student, Class, User
from routes.utils import school_id, staff_required, admin_required
from routes import student_import
from routes.student_import import parse_upload, normalize_gender, parse_date, split_full_name
from routes.validators import generate_password
from routes.emails import send_account_credentials_email
from audit import log_audit_event, diff_fields
from malware_scan import scan_bytes

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
            log_audit_event('STUDENT_CREATED', actor=current_user, school_id=sid,
                             resource_type='student', resource_id=student.id,
                             extra={'reg_number': reg_number})
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

        # Type-integrity check -- confirms a .xlsx upload is a real zip
        # archive before handing it to openpyxl. This is not malware
        # scanning, just protection against a renamed file claiming to be
        # something it isn't; the real ClamAV scan happens below regardless
        # of extension.
        filename_lower = file.filename.lower()
        if filename_lower.endswith(('.xlsx', '.xlsm')):
            is_valid_zip = zipfile.is_zipfile(file.stream)
            file.stream.seek(0)
            if not is_valid_zip:
                log_audit_event('FILE_REJECTED', actor=current_user, school_id=sid, result='blocked',
                                 extra={'reason': 'not_a_valid_xlsx', 'filename': file.filename})
                flash('That file does not look like a valid Excel file.', 'error')
                return render_template('students/import.html', classes=classes)

        file_bytes = file.stream.read()
        file.stream.seek(0)
        scan = scan_bytes(file_bytes)
        if not scan.clean:
            log_audit_event('FILE_SCAN_FAILED', actor=current_user, school_id=sid, result='blocked',
                             extra={'filename': file.filename, 'detail': scan.detail})
            flash('That file failed a malware scan and was rejected.', 'error')
            return render_template('students/import.html', classes=classes)
        log_audit_event('FILE_SCAN_PASSED', actor=current_user, school_id=sid,
                         extra={'filename': file.filename})

        log_audit_event('FILE_UPLOADED', actor=current_user, school_id=sid,
                         resource_type='student_import', extra={'filename': file.filename})
        log_audit_event('FILE_IMPORT_STARTED', actor=current_user, school_id=sid,
                         extra={'filename': file.filename})

        try:
            rows = parse_upload(file)
        except student_import.ImportError_ as exc:
            log_audit_event('FILE_IMPORT_FAILED', actor=current_user, school_id=sid, result='failure',
                             extra={'filename': file.filename, 'error': str(exc)})
            flash(str(exc), 'error')
            return render_template('students/import.html', classes=classes)

        if not rows:
            log_audit_event('FILE_IMPORT_FAILED', actor=current_user, school_id=sid, result='failure',
                             extra={'filename': file.filename, 'error': 'no data rows'})
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

        log_audit_event(
            'FILE_IMPORT_COMPLETED', actor=current_user, school_id=sid,
            extra={'filename': file.filename, 'rows_imported': imported, 'rows_skipped': skipped, 'rows_failed': len(errors)},
        )
        log_audit_event(
            'STUDENT_DATA_IMPORTED', actor=current_user, school_id=sid, resource_type='student',
            extra={'rows_imported': imported, 'rows_skipped': skipped, 'rows_failed': len(errors)},
        )

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
    student = Student.query.get_or_404(id)
    if student.school_id != school_id():
        log_audit_event(
            'UNAUTHORIZED_ACCESS_ATTEMPT', actor=current_user, resource_type='student', resource_id=id,
            result='blocked', extra={'reason': 'student belongs to another school'},
        )
        abort(404)
    log_audit_event('STUDENT_RECORD_ACCESSED', actor=current_user, school_id=student.school_id,
                     resource_type='student', resource_id=student.id)
    return render_template('students/detail.html', student=student)


@students_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@staff_required
def edit(id):
    sid = school_id()
    student = Student.query.filter_by(id=id, school_id=sid).first_or_404()
    classes = Class.query.filter_by(school_id=sid).order_by(Class.name).all()
    if request.method == 'POST':
        before = {
            'first_name': student.first_name,
            'last_name': student.last_name,
            'gender': student.gender,
            'class_id': student.class_id,
            'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
        }

        student.first_name = request.form.get('first_name', '').strip()
        student.last_name = request.form.get('last_name', '').strip()
        student.gender = request.form.get('gender', '').strip()
        student.class_id = request.form.get('class_id', type=int) or None
        dob_str = request.form.get('date_of_birth', '').strip()
        student.date_of_birth = date.fromisoformat(dob_str) if dob_str else None
        db.session.commit()

        after = {
            'first_name': student.first_name,
            'last_name': student.last_name,
            'gender': student.gender,
            'class_id': student.class_id,
            'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
        }
        log_audit_event(
            'STUDENT_UPDATED', actor=current_user, school_id=sid, resource_type='student', resource_id=student.id,
            changes=diff_fields({k: (before[k], after[k]) for k in before}),
        )
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

        if not username:
            flash('Username is required.', 'error')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
        else:
            password = generate_password()
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
            log_audit_event('USER_CREATED', actor=current_user, school_id=school_id(),
                             resource_type='user', resource_id=user.id,
                             extra={'role': 'student', 'linked_student_id': student.id})

            emailed = send_account_credentials_email(user, password, 'student')
            return render_template(
                'students/account_created.html',
                student=student, username=username, password=password, emailed=emailed,
            )

    return render_template('students/create_account.html', student=student)


@students_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    sid = school_id()
    student = Student.query.filter_by(id=id, school_id=sid).first_or_404()
    name = student.full_name
    db.session.delete(student)
    db.session.commit()
    log_audit_event('STUDENT_DELETED', actor=current_user, school_id=sid,
                     resource_type='student', resource_id=id, extra={'name': name})
    flash(f'{name} has been deleted.', 'success')
    return redirect(url_for('students.index'))
