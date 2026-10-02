from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Class, User
from routes.utils import school_id, staff_required, admin_required
from audit import log_audit_event

classes_bp = Blueprint('classes', __name__, url_prefix='/classes')


@classes_bp.route('/')
@login_required
@staff_required
def index():
    sid = school_id()
    classes = Class.query.filter_by(school_id=sid).order_by(Class.name).all()
    teachers = User.query.filter_by(school_id=sid).filter(
        User.role.in_(['school_admin', 'teacher'])
    ).order_by(User.full_name).all()
    return render_template('classes/index.html', classes=classes, teachers=teachers)


@classes_bp.route('/add', methods=['POST'])
@login_required
@staff_required
def add():
    sid = school_id()
    name = request.form.get('name', '').strip()
    grade_level = request.form.get('grade_level', '').strip()
    teacher_id = request.form.get('teacher_id', type=int)

    if not name:
        flash('Class name is required.', 'error')
    else:
        class_ = Class(name=name, grade_level=grade_level or None, teacher_id=teacher_id or None, school_id=sid)
        db.session.add(class_)
        db.session.commit()
        log_audit_event('CLASS_CREATED', actor=current_user, school_id=sid,
                         resource_type='class', resource_id=class_.id, extra={'name': name})
        flash(f'Class "{name}" added.', 'success')

    return redirect(url_for('classes.index'))


@classes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    sid = school_id()
    class_ = Class.query.filter_by(id=id, school_id=sid).first_or_404()
    if class_.students:
        flash('Cannot delete a class that has students assigned.', 'error')
    else:
        name = class_.name
        db.session.delete(class_)
        db.session.commit()
        log_audit_event('CLASS_DELETED', actor=current_user, school_id=sid,
                         resource_type='class', resource_id=id, extra={'name': name})
        flash('Class deleted.', 'success')
    return redirect(url_for('classes.index'))
