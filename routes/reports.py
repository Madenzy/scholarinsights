from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Report, Student, AcademicTerm, Subject, Grade, calculate_grade
from routes.utils import school_id, staff_required, admin_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


@reports_bp.route('/')
@login_required
@staff_required
def index():
    sid = school_id()
    term_id = request.args.get('term_id', type=int)
    terms = AcademicTerm.query.filter_by(school_id=sid).order_by(AcademicTerm.year.desc(), AcademicTerm.term_number.desc()).all()
    query = Report.query.filter_by(school_id=sid)
    if term_id:
        query = query.filter_by(term_id=term_id)
    reports = query.order_by(Report.created_at.desc()).all()
    return render_template('reports/index.html', reports=reports, terms=terms, term_id=term_id)


@reports_bp.route('/generate', methods=['GET', 'POST'])
@login_required
@staff_required
def generate():
    sid = school_id()
    students = Student.query.filter_by(school_id=sid).order_by(Student.last_name, Student.first_name).all()
    terms = AcademicTerm.query.filter_by(school_id=sid).order_by(AcademicTerm.year.desc(), AcademicTerm.term_number.desc()).all()
    subjects = Subject.query.filter_by(school_id=sid).order_by(Subject.name).all()

    if request.method == 'POST':
        student_id = request.form.get('student_id', type=int)
        term_id = request.form.get('term_id', type=int)
        teacher_comment = request.form.get('teacher_comment', '').strip()
        head_comment = request.form.get('head_comment', '').strip()

        if not student_id or not term_id:
            flash('Please select a student and term.', 'error')
            return render_template('reports/generate.html', students=students, terms=terms, subjects=subjects)

        existing = Report.query.filter_by(student_id=student_id, term_id=term_id).first()
        if existing:
            flash('A report already exists for this student and term.', 'error')
            return redirect(url_for('reports.view', id=existing.id))

        report = Report(
            student_id=student_id,
            term_id=term_id,
            school_id=sid,
            teacher_comment=teacher_comment,
            head_comment=head_comment,
        )
        db.session.add(report)
        db.session.flush()

        for subject in subjects:
            score_str = request.form.get(f'score_{subject.id}', '').strip()
            comment = request.form.get(f'comment_{subject.id}', '').strip()
            if score_str:
                try:
                    score = max(0.0, min(100.0, float(score_str)))
                    db.session.add(Grade(
                        report_id=report.id,
                        subject_id=subject.id,
                        score=score,
                        grade_letter=calculate_grade(score),
                        comment=comment or None,
                    ))
                except ValueError:
                    pass

        db.session.commit()
        flash('Report generated successfully.', 'success')
        return redirect(url_for('reports.view', id=report.id))

    return render_template('reports/generate.html', students=students, terms=terms, subjects=subjects)


@reports_bp.route('/<int:id>')
@login_required
@staff_required
def view(id):
    report = Report.query.filter_by(id=id, school_id=school_id()).first_or_404()
    return render_template('reports/view.html', report=report)


@reports_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@staff_required
def edit(id):
    sid = school_id()
    report = Report.query.filter_by(id=id, school_id=sid).first_or_404()
    subjects = Subject.query.filter_by(school_id=sid).order_by(Subject.name).all()
    grade_map = {g.subject_id: g for g in report.grades}

    if request.method == 'POST':
        report.teacher_comment = request.form.get('teacher_comment', '').strip()
        report.head_comment = request.form.get('head_comment', '').strip()

        for subject in subjects:
            score_str = request.form.get(f'score_{subject.id}', '').strip()
            comment = request.form.get(f'comment_{subject.id}', '').strip()
            existing = grade_map.get(subject.id)

            if score_str:
                try:
                    score = max(0.0, min(100.0, float(score_str)))
                    if existing:
                        existing.score = score
                        existing.grade_letter = calculate_grade(score)
                        existing.comment = comment or None
                    else:
                        db.session.add(Grade(
                            report_id=report.id,
                            subject_id=subject.id,
                            score=score,
                            grade_letter=calculate_grade(score),
                            comment=comment or None,
                        ))
                except ValueError:
                    pass
            elif existing:
                db.session.delete(existing)

        db.session.commit()
        flash('Report updated.', 'success')
        return redirect(url_for('reports.view', id=id))

    return render_template('reports/edit.html', report=report, subjects=subjects, grade_map=grade_map)


@reports_bp.route('/<int:id>/publish', methods=['POST'])
@login_required
@staff_required
def publish(id):
    report = Report.query.filter_by(id=id, school_id=school_id()).first_or_404()
    report.status = 'published'
    db.session.commit()
    flash('Report published.', 'success')
    return redirect(url_for('reports.view', id=id))


@reports_bp.route('/<int:id>/unpublish', methods=['POST'])
@login_required
@staff_required
def unpublish(id):
    report = Report.query.filter_by(id=id, school_id=school_id()).first_or_404()
    report.status = 'draft'
    db.session.commit()
    flash('Report moved back to draft.', 'success')
    return redirect(url_for('reports.view', id=id))


@reports_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    report = Report.query.filter_by(id=id, school_id=school_id()).first_or_404()
    db.session.delete(report)
    db.session.commit()
    flash('Report deleted.', 'success')
    return redirect(url_for('reports.index'))
