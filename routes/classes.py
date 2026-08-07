from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Class, User
from routes.utils import school_id, staff_required, admin_required

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
        db.session.add(Class(name=name, grade_level=grade_level or None, teacher_id=teacher_id or None, school_id=sid))
        db.session.commit()
        flash(f'Class "{name}" added.', 'success')

    return redirect(url_for('classes.index'))


@classes_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    class_ = Class.query.filter_by(id=id, school_id=school_id()).first_or_404()
    if class_.students:
        flash('Cannot delete a class that has students assigned.', 'error')
    else:
        db.session.delete(class_)
        db.session.commit()
        flash('Class deleted.', 'success')
    return redirect(url_for('classes.index'))
