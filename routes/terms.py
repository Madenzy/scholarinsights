from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, AcademicTerm
from routes.utils import school_id, staff_required, admin_required
from audit import log_audit_event

terms_bp = Blueprint('terms', __name__, url_prefix='/terms')


@terms_bp.route('/')
@login_required
@staff_required
def index():
    terms = AcademicTerm.query.filter_by(school_id=school_id()).order_by(AcademicTerm.year.desc(), AcademicTerm.term_number.desc()).all()
    return render_template('terms/index.html', terms=terms)


@terms_bp.route('/add', methods=['POST'])
@login_required
@staff_required
def add():
    sid = school_id()
    name = request.form.get('name', '').strip()
    year = request.form.get('year', type=int)
    term_number = request.form.get('term_number', type=int)
    start_str = request.form.get('start_date', '').strip()
    end_str = request.form.get('end_date', '').strip()

    if not name or not year or not term_number:
        flash('Name, year and term number are required.', 'error')
    else:
        term = AcademicTerm(
            name=name, year=year, term_number=term_number,
            start_date=date.fromisoformat(start_str) if start_str else None,
            end_date=date.fromisoformat(end_str) if end_str else None,
            school_id=sid,
        )
        db.session.add(term)
        db.session.commit()
        log_audit_event('TERM_CREATED', actor=current_user, school_id=sid,
                         resource_type='term', resource_id=term.id, extra={'name': name})
        flash(f'Term "{name}" added.', 'success')

    return redirect(url_for('terms.index'))


@terms_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    sid = school_id()
    term = AcademicTerm.query.filter_by(id=id, school_id=sid).first_or_404()
    if term.reports:
        flash('Cannot delete a term that has reports.', 'error')
    else:
        name = term.name
        db.session.delete(term)
        db.session.commit()
        log_audit_event('TERM_DELETED', actor=current_user, school_id=sid,
                         resource_type='term', resource_id=id, extra={'name': name})
        flash('Term deleted.', 'success')
    return redirect(url_for('terms.index'))
