import base64
import os
import qrcode
import qrcode.image.svg
from io import BytesIO
from xhtml2pdf import pisa

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app, abort
from flask_login import login_required, current_user
from models import db, Report, Student, School, AcademicTerm, Subject, Grade, calculate_grade
from routes.utils import school_id, staff_required, admin_required
from routes.emails import send_report_published_email
from audit import log_audit_event

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def _report_class_stats(report):
    """Class/form average and ranking for a report, among peers with a
    report for the same term. Returns None for any value that can't be
    computed (e.g. the student has no class assigned)."""
    student = report.student
    peer_reports = (
        Report.query
        .filter_by(school_id=report.school_id, term_id=report.term_id)
        .join(Student, Report.student_id == Student.id)
        .all()
    )

    class_scores = sorted(
        (
            (r.student_id, r.average_score)
            for r in peer_reports
            if student.class_id and r.student.class_id == student.class_id and r.average_score is not None
        ),
        key=lambda pair: pair[1], reverse=True,
    )
    position_in_class = next((i + 1 for i, (sid, _) in enumerate(class_scores) if sid == student.id), None)
    class_average = round(sum(s for _, s in class_scores) / len(class_scores), 1) if class_scores else None

    form_scores = sorted(
        (
            (r.student_id, r.average_score)
            for r in peer_reports
            if student.class_ and r.student.class_ and r.student.class_.grade_level == student.class_.grade_level
            and r.average_score is not None
        ),
        key=lambda pair: pair[1], reverse=True,
    )
    position_in_form = next((i + 1 for i, (sid, _) in enumerate(form_scores) if sid == student.id), None)

    return {
        'class_average': class_average,
        'class_size': len(class_scores),
        'position_in_class': position_in_class,
        'form_size': len(form_scores),
        'position_in_form': position_in_form,
        'subjects_passed': sum(1 for g in report.grades if g.is_pass),
    }


def _apply_grade(grade, score, bands):
    """Set score + the band-derived fields on a Grade from the school's bands."""
    grade.score = score
    band = calculate_grade(score, bands)
    grade.grade_letter = band.letter if band else None
    grade.is_pass = band.is_pass if band else True
    grade.auto_remark = band.remark if band else None


def _report_qr_svg(report):
    """Inline SVG QR code linking to this report's own (login-gated) URL."""
    url = url_for('reports.view', id=report.id, _external=True)
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=1)
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue().decode('utf-8')


def _report_qr_png_data_uri(report):
    """Base64 PNG QR code for PDF rendering (xhtml2pdf has no SVG support)."""
    url = url_for('reports.view', id=report.id, _external=True)
    img = qrcode.make(url, box_size=6, border=1)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


def _logo_data_uri(school):
    """Base64 data URI for a school's logo, for use in PDF templates."""
    if not school.logo_filename:
        return None
    path = os.path.join(current_app.root_path, 'static', 'uploads', 'logos', school.logo_filename)
    if not os.path.exists(path):
        return None
    ext = school.logo_filename.rsplit('.', 1)[-1].lower()
    mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else 'image/png'
    with open(path, 'rb') as f:
        data = f.read()
    return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')


def _render_pdf(html):
    buf = BytesIO()
    pisa.CreatePDF(html, dest=buf)
    buf.seek(0)
    return buf


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

        bands = School.query.get(sid).grade_bands
        for subject in subjects:
            score_str = request.form.get(f'score_{subject.id}', '').strip()
            comment = request.form.get(f'comment_{subject.id}', '').strip()
            if score_str:
                try:
                    score = max(0.0, min(100.0, float(score_str)))
                    grade = Grade(report_id=report.id, subject_id=subject.id, comment=comment or None)
                    _apply_grade(grade, score, bands)
                    db.session.add(grade)
                except ValueError:
                    pass

        db.session.commit()
        log_audit_event('REPORT_CREATED', actor=current_user, school_id=sid,
                         resource_type='report', resource_id=report.id,
                         extra={'student_id': student_id, 'term_id': term_id})
        flash('Report generated successfully.', 'success')
        return redirect(url_for('reports.view', id=report.id))

    return render_template('reports/generate.html', students=students, terms=terms, subjects=subjects)


@reports_bp.route('/<int:id>')
@login_required
@staff_required
def view(id):
    report = Report.query.get_or_404(id)
    if report.school_id != school_id():
        log_audit_event(
            'UNAUTHORIZED_ACCESS_ATTEMPT', actor=current_user, resource_type='report', resource_id=id,
            result='blocked', extra={'reason': 'report belongs to another school'},
        )
        abort(404)
    stats = _report_class_stats(report)
    qr_svg = _report_qr_svg(report)
    return render_template('reports/view.html', report=report, qr_svg=qr_svg, **stats)


@reports_bp.route('/<int:id>/download')
@login_required
@staff_required
def download(id):
    report = Report.query.filter_by(id=id, school_id=school_id()).first_or_404()
    stats = _report_class_stats(report)
    qr_data_uri = _report_qr_png_data_uri(report)
    logo_data_uri = _logo_data_uri(report.school)
    html = render_template('reports/pdf_single.html', report=report, qr_data_uri=qr_data_uri, logo_data_uri=logo_data_uri, **stats)
    pdf_buf = _render_pdf(html)
    safe_name = report.student.full_name.replace(' ', '_')
    safe_term = report.term.name.replace(' ', '_')
    log_audit_event('FILE_DOWNLOAD', actor=current_user, school_id=report.school_id,
                     resource_type='report', resource_id=report.id)
    return send_file(pdf_buf, mimetype='application/pdf', as_attachment=True, download_name=f'{safe_name}_{safe_term}_report.pdf')


def _selected_reports(sid, ids_param):
    ids = [int(x) for x in ids_param.split(',') if x.strip().isdigit()]
    reports_by_id = {
        r.id: r for r in Report.query.filter(Report.id.in_(ids), Report.school_id == sid).all()
    } if ids else {}
    return [reports_by_id[i] for i in ids if i in reports_by_id]


@reports_bp.route('/bulk/print')
@login_required
@admin_required
def bulk_print():
    reports = _selected_reports(school_id(), request.args.get('ids', ''))
    if not reports:
        flash('Select at least one report first.', 'error')
        return redirect(url_for('reports.index'))
    cards = []
    for report in reports:
        stats = _report_class_stats(report)
        cards.append({'report': report, 'qr_svg': _report_qr_svg(report), **stats})
    return render_template('reports/bulk_print.html', cards=cards)


@reports_bp.route('/bulk/download')
@login_required
@admin_required
def bulk_download():
    reports = _selected_reports(school_id(), request.args.get('ids', ''))
    if not reports:
        flash('Select at least one report first.', 'error')
        return redirect(url_for('reports.index'))
    cards = []
    for report in reports:
        stats = _report_class_stats(report)
        cards.append({
            'report': report,
            'qr_data_uri': _report_qr_png_data_uri(report),
            'logo_data_uri': _logo_data_uri(report.school),
            **stats,
        })
    html = render_template('reports/pdf_bulk.html', cards=cards)
    pdf_buf = _render_pdf(html)
    log_audit_event('FILE_DOWNLOAD', actor=current_user, school_id=school_id(),
                     resource_type='report', extra={'bulk': True, 'count': len(reports)})
    return send_file(pdf_buf, mimetype='application/pdf', as_attachment=True, download_name='report_cards.pdf')


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

        bands = School.query.get(sid).grade_bands
        for subject in subjects:
            score_str = request.form.get(f'score_{subject.id}', '').strip()
            comment = request.form.get(f'comment_{subject.id}', '').strip()
            existing = grade_map.get(subject.id)

            if score_str:
                try:
                    score = max(0.0, min(100.0, float(score_str)))
                    if existing:
                        _apply_grade(existing, score, bands)
                        existing.comment = comment or None
                    else:
                        grade = Grade(report_id=report.id, subject_id=subject.id, comment=comment or None)
                        _apply_grade(grade, score, bands)
                        db.session.add(grade)
                except ValueError:
                    pass
            elif existing:
                db.session.delete(existing)

        db.session.commit()
        log_audit_event('REPORT_UPDATED', actor=current_user, school_id=sid,
                         resource_type='report', resource_id=id,
                         extra={'subjects_graded': len(grade_map)})
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
    log_audit_event('REPORT_PUBLISHED', actor=current_user, school_id=report.school_id,
                     resource_type='report', resource_id=id)

    sent, total = send_report_published_email(report)
    if not total:
        flash('Report published.', 'success')
    elif sent:
        flash(f'Report published and emailed to {sent} recipient{"s" if sent != 1 else ""}.', 'success')
    else:
        flash('Report published, but the notification email could not be sent.', 'info')

    return redirect(url_for('reports.view', id=id))


@reports_bp.route('/<int:id>/unpublish', methods=['POST'])
@login_required
@staff_required
def unpublish(id):
    report = Report.query.filter_by(id=id, school_id=school_id()).first_or_404()
    report.status = 'draft'
    db.session.commit()
    log_audit_event('REPORT_UNPUBLISHED', actor=current_user, school_id=report.school_id,
                     resource_type='report', resource_id=id)
    flash('Report moved back to draft.', 'success')
    return redirect(url_for('reports.view', id=id))


@reports_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    sid = school_id()
    report = Report.query.filter_by(id=id, school_id=sid).first_or_404()
    db.session.delete(report)
    db.session.commit()
    log_audit_event('REPORT_DELETED', actor=current_user, school_id=sid,
                     resource_type='report', resource_id=id)
    flash('Report deleted.', 'success')
    return redirect(url_for('reports.index'))
