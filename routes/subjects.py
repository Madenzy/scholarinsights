from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Subject
from routes.utils import school_id, staff_required, admin_required
from audit import log_audit_event

subjects_bp = Blueprint('subjects', __name__, url_prefix='/subjects')


@subjects_bp.route('/')
@login_required
@staff_required
def index():
    subjects = Subject.query.filter_by(school_id=school_id()).order_by(Subject.name).all()
    return render_template('subjects/index.html', subjects=subjects)


@subjects_bp.route('/add', methods=['POST'])
@login_required
@staff_required
def add():
    sid = school_id()
    name = request.form.get('name', '').strip()
    code = request.form.get('code', '').strip().upper()

    if not name or not code:
        flash('Subject name and code are required.', 'error')
    elif Subject.query.filter_by(code=code, school_id=sid).first():
        flash(f'Subject code "{code}" already exists.', 'error')
    else:
        subject = Subject(name=name, code=code, school_id=sid)
        db.session.add(subject)
        db.session.commit()
        log_audit_event('SUBJECT_CREATED', actor=current_user, school_id=sid,
                         resource_type='subject', resource_id=subject.id, extra={'name': name, 'code': code})
        flash(f'Subject "{name}" added.', 'success')

    return redirect(url_for('subjects.index'))


@subjects_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    sid = school_id()
    subject = Subject.query.filter_by(id=id, school_id=sid).first_or_404()
    if subject.grades:
        flash('Cannot delete a subject that has grades recorded.', 'error')
    else:
        name = subject.name
        db.session.delete(subject)
        db.session.commit()
        log_audit_event('SUBJECT_DELETED', actor=current_user, school_id=sid,
                         resource_type='subject', resource_id=id, extra={'name': name})
        flash('Subject deleted.', 'success')
    return redirect(url_for('subjects.index'))
