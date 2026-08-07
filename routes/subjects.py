from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from models import db, Subject
from routes.utils import school_id, staff_required, admin_required

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
        db.session.add(Subject(name=name, code=code, school_id=sid))
        db.session.commit()
        flash(f'Subject "{name}" added.', 'success')

    return redirect(url_for('subjects.index'))


@subjects_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    subject = Subject.query.filter_by(id=id, school_id=school_id()).first_or_404()
    if subject.grades:
        flash('Cannot delete a subject that has grades recorded.', 'error')
    else:
        db.session.delete(subject)
        db.session.commit()
        flash('Subject deleted.', 'success')
    return redirect(url_for('subjects.index'))
