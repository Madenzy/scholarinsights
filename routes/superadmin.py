from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import db, School, User, Student, Class, Subject, AcademicTerm, Report

superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')


def _require_super_admin():
    if not current_user.is_authenticated or not current_user.is_super_admin:
        abort(403)


# ── Overview ──────────────────────────────────────────────────────────────────

@superadmin_bp.route('/')
@login_required
def index():
    _require_super_admin()
    schools = School.query.order_by(School.created_at.desc()).all()
    totals = {
        'schools': School.query.count(),
        'users': User.query.filter(User.role != 'super_admin').count(),
        'students': Student.query.count(),
        'reports': Report.query.count(),
    }
    return render_template('superadmin/index.html', schools=schools, totals=totals)


# ── School detail ─────────────────────────────────────────────────────────────

@superadmin_bp.route('/schools/<int:id>')
@login_required
def school_detail(id):
    _require_super_admin()
    school = School.query.get_or_404(id)
    users = User.query.filter_by(school_id=id).order_by(User.role, User.full_name).all()
    counts = {
        'students': Student.query.filter_by(school_id=id).count(),
        'reports': Report.query.filter_by(school_id=id).count(),
        'classes': Class.query.filter_by(school_id=id).count(),
    }
    return render_template('superadmin/school_detail.html',
                           school=school, users=users, counts=counts)


# ── Disable / Enable school ───────────────────────────────────────────────────

@superadmin_bp.route('/schools/<int:id>/disable', methods=['POST'])
@login_required
def disable_school(id):
    _require_super_admin()
    school = School.query.get_or_404(id)
    school.is_active = False
    db.session.commit()
    flash(f'"{school.name}" has been suspended. All its users are now blocked from logging in.', 'success')
    return redirect(url_for('superadmin.school_detail', id=id))


@superadmin_bp.route('/schools/<int:id>/enable', methods=['POST'])
@login_required
def enable_school(id):
    _require_super_admin()
    school = School.query.get_or_404(id)
    school.is_active = True
    db.session.commit()
    flash(f'"{school.name}" has been reactivated.', 'success')
    return redirect(url_for('superadmin.school_detail', id=id))


# ── Delete school (cascades all data) ────────────────────────────────────────

@superadmin_bp.route('/schools/<int:id>/delete', methods=['POST'])
@login_required
def delete_school(id):
    _require_super_admin()
    school = School.query.get_or_404(id)
    name = school.name

    # Unlink student login accounts first to avoid FK conflicts
    Student.query.filter_by(school_id=id).update({'user_id': None})
    db.session.flush()

    # Students cascade to reports → grades
    for student in Student.query.filter_by(school_id=id).all():
        db.session.delete(student)
    db.session.flush()

    # Remaining school records
    Class.query.filter_by(school_id=id).delete()
    Subject.query.filter_by(school_id=id).delete()
    AcademicTerm.query.filter_by(school_id=id).delete()

    # Users (parent_student join entries auto-removed by cascade)
    for user in User.query.filter_by(school_id=id).all():
        db.session.delete(user)

    db.session.delete(school)
    db.session.commit()
    flash(f'School "{name}" and all its data have been permanently deleted.', 'success')
    return redirect(url_for('superadmin.index'))


# ── Disable / Enable individual user ─────────────────────────────────────────

@superadmin_bp.route('/users/<int:id>/disable', methods=['POST'])
@login_required
def disable_user(id):
    _require_super_admin()
    user = User.query.get_or_404(id)
    if user.is_super_admin:
        flash('Cannot disable a super admin account.', 'error')
    else:
        user.is_active = False
        db.session.commit()
        flash(f'{user.display_name} has been disabled.', 'success')
    return redirect(url_for('superadmin.school_detail', id=user.school_id))


@superadmin_bp.route('/users/<int:id>/enable', methods=['POST'])
@login_required
def enable_user(id):
    _require_super_admin()
    user = User.query.get_or_404(id)
    user.is_active = True
    db.session.commit()
    flash(f'{user.display_name} has been re-enabled.', 'success')
    return redirect(url_for('superadmin.school_detail', id=user.school_id))


# ── Reset password ────────────────────────────────────────────────────────────

@superadmin_bp.route('/users/<int:id>/reset-password', methods=['GET', 'POST'])
@login_required
def reset_password(id):
    _require_super_admin()
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm', '').strip()

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(password)
            db.session.commit()
            flash(f'Password reset for {user.display_name}.', 'success')
            if user.school_id:
                return redirect(url_for('superadmin.school_detail', id=user.school_id))
            return redirect(url_for('superadmin.index'))

    return render_template('superadmin/reset_password.html', user=user)


# ── Change user role ──────────────────────────────────────────────────────────

@superadmin_bp.route('/users/<int:id>/change-role', methods=['POST'])
@login_required
def change_role(id):
    _require_super_admin()
    user = User.query.get_or_404(id)
    new_role = request.form.get('role', '').strip()

    allowed = ('school_admin', 'teacher')
    if new_role not in allowed:
        flash('Invalid role.', 'error')
    elif user.is_super_admin:
        flash('Cannot change the role of a super admin.', 'error')
    else:
        user.role = new_role
        db.session.commit()
        flash(f'{user.display_name} is now a {new_role.replace("_", " ").title()}.', 'success')

    return redirect(url_for('superadmin.school_detail', id=user.school_id))
