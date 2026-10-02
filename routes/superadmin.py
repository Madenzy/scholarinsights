import os
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, func, desc

from models import db, School, User, Student, Class, Subject, AcademicTerm, Report, Grade, AuditLog
from routes.utils import super_admin_required
from routes.validators import password_error
from audit import log_audit_event

superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')

LIST_PAGE_SIZE = 50


def _logo_storage_bytes():
    path = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
    if not os.path.isdir(path):
        return 0
    return sum(
        os.path.getsize(os.path.join(path, f))
        for f in os.listdir(path)
        if os.path.isfile(os.path.join(path, f))
    )


def _human_size(num_bytes):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if num_bytes < 1024:
            return f'{num_bytes:.0f} {unit}' if unit == 'B' else f'{num_bytes:.1f} {unit}'
        num_bytes /= 1024
    return f'{num_bytes:.1f} TB'


def _distinct_active_users(since):
    return (
        db.session.query(AuditLog.actor_user_id)
        .filter(AuditLog.action == 'LOGIN_SUCCESS', AuditLog.created_at >= since, AuditLog.actor_user_id.isnot(None))
        .distinct()
        .count()
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

@superadmin_bp.route('/')
@login_required
@super_admin_required
def dashboard():
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = datetime(now.year, now.month, 1)
    week_ago = now - timedelta(days=7)

    totals = {
        'schools': School.query.count(),
        'active_schools': School.query.filter_by(is_active=True).count(),
        'suspended_schools': School.query.filter_by(is_active=False).count(),
        'students': Student.query.count(),
        'staff': User.query.filter(User.role.in_(['school_admin', 'teacher'])).count(),
        'school_admins': User.query.filter_by(role='school_admin').count(),
        'reports': Report.query.count(),
    }
    new_this_month = {
        'schools': School.query.filter(School.created_at >= month_start).count(),
        'users': User.query.filter(User.created_at >= month_start, User.role != 'super_admin').count(),
        'reports': Report.query.filter(Report.created_at >= month_start).count(),
    }
    active_today = _distinct_active_users(today_start)
    active_week = _distinct_active_users(week_start)

    security_alerts = AuditLog.query.filter(
        AuditLog.result.in_(['blocked', 'failure']), AuditLog.created_at >= week_ago,
    ).count()

    storage_bytes = _logo_storage_bytes()

    recent_security = (
        AuditLog.query.filter(AuditLog.result.in_(['blocked', 'failure']))
        .order_by(desc(AuditLog.created_at)).limit(8).all()
    )
    recent_admin_activity = (
        AuditLog.query.filter(AuditLog.actor_role.in_(['super_admin', 'school_admin']))
        .order_by(desc(AuditLog.created_at)).limit(8).all()
    )

    return render_template(
        'superadmin/dashboard.html',
        totals=totals, new_this_month=new_this_month,
        active_today=active_today, active_week=active_week,
        security_alerts=security_alerts, storage_human=_human_size(storage_bytes),
        recent_security=recent_security, recent_admin_activity=recent_admin_activity,
    )


# ── Schools ───────────────────────────────────────────────────────────────────

@superadmin_bp.route('/schools')
@login_required
@super_admin_required
def schools_list():
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()

    query = School.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(School.name.ilike(like), School.email.ilike(like)))
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'suspended':
        query = query.filter_by(is_active=False)

    schools = query.order_by(School.created_at.desc()).all()
    return render_template('superadmin/schools.html', schools=schools, q=q, status=status)


@superadmin_bp.route('/schools/<int:id>')
@login_required
@super_admin_required
def school_detail(id):
    school = School.query.get_or_404(id)
    users = User.query.filter_by(school_id=id).order_by(User.role, User.full_name).all()
    counts = {
        'students': Student.query.filter_by(school_id=id).count(),
        'reports': Report.query.filter_by(school_id=id).count(),
        'classes': Class.query.filter_by(school_id=id).count(),
    }
    log_audit_event('SUPER_ADMIN_VIEWED_SCHOOL', actor=current_user, school_id=id,
                     resource_type='school', resource_id=id)
    return render_template('superadmin/school_detail.html',
                           school=school, users=users, counts=counts)


# ── Disable / Enable school ───────────────────────────────────────────────────

@superadmin_bp.route('/schools/<int:id>/disable', methods=['POST'])
@login_required
@super_admin_required
def disable_school(id):
    school = School.query.get_or_404(id)
    school.is_active = False
    db.session.commit()
    log_audit_event('SCHOOL_SUSPENDED', actor=current_user, school_id=id,
                     resource_type='school', resource_id=id, extra={'name': school.name})
    flash(f'"{school.name}" has been suspended. All its users are now blocked from logging in.', 'success')
    return redirect(url_for('superadmin.school_detail', id=id))


@superadmin_bp.route('/schools/<int:id>/enable', methods=['POST'])
@login_required
@super_admin_required
def enable_school(id):
    school = School.query.get_or_404(id)
    school.is_active = True
    db.session.commit()
    log_audit_event('SCHOOL_REACTIVATED', actor=current_user, school_id=id,
                     resource_type='school', resource_id=id, extra={'name': school.name})
    flash(f'"{school.name}" has been reactivated.', 'success')
    return redirect(url_for('superadmin.school_detail', id=id))


# ── Delete school (cascades all data) ────────────────────────────────────────

@superadmin_bp.route('/schools/<int:id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_school(id):
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
    # school_id is passed explicitly since the row (and its FK target) no
    # longer exists after this commit -- the audit row keeps the id for
    # reference even though it can't join back to a live School anymore.
    log_audit_event('SCHOOL_DELETED', actor=current_user, school_id=id,
                     resource_type='school', resource_id=id, extra={'name': name})
    flash(f'School "{name}" and all its data have been permanently deleted.', 'success')
    return redirect(url_for('superadmin.schools_list'))


# ── Staff (cross-school) ──────────────────────────────────────────────────────

@superadmin_bp.route('/staff')
@login_required
@super_admin_required
def staff_list():
    q = request.args.get('q', '').strip()
    school_id = request.args.get('school_id', type=int)
    role = request.args.get('role', '').strip()

    query = User.query.filter(User.role.in_(['school_admin', 'teacher']))
    if q:
        like = f'%{q}%'
        query = query.filter(or_(User.full_name.ilike(like), User.username.ilike(like), User.email.ilike(like)))
    if school_id:
        query = query.filter_by(school_id=school_id)
    if role in ('school_admin', 'teacher'):
        query = query.filter_by(role=role)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(User.school_id, User.role, User.full_name).paginate(
        page=page, per_page=LIST_PAGE_SIZE, error_out=False,
    )
    schools = School.query.order_by(School.name).all()
    filter_qs = {k: v for k, v in {'q': q, 'school_id': school_id, 'role': role}.items() if v}

    return render_template(
        'superadmin/staff.html', staff=pagination.items, pagination=pagination,
        schools=schools, q=q, school_id=school_id, role=role, filter_qs=filter_qs,
    )


@superadmin_bp.route('/staff/<int:id>/require-mfa', methods=['POST'])
@login_required
@super_admin_required
def toggle_require_mfa(id):
    user = User.query.get_or_404(id)
    if user.role not in ('school_admin', 'teacher'):
        return redirect(url_for('superadmin.staff_list'))

    user.mfa_required = not user.mfa_required
    db.session.commit()
    log_audit_event('MFA_REQUIRED_SET' if user.mfa_required else 'MFA_REQUIRED_UNSET',
                     actor=current_user, school_id=user.school_id,
                     resource_type='user', resource_id=user.id)
    if user.mfa_required:
        flash(f'{user.display_name} must now set up two-factor authentication.', 'success')
    else:
        flash(f'Two-factor authentication is no longer required for {user.display_name}.', 'success')

    next_url = request.referrer or url_for('superadmin.staff_list')
    return redirect(next_url)


# ── Students (cross-school, privacy-minimal) ─────────────────────────────────

@superadmin_bp.route('/students')
@login_required
@super_admin_required
def students_list():
    q = request.args.get('q', '').strip()
    school_id = request.args.get('school_id', type=int)

    query = Student.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Student.first_name.ilike(like), Student.last_name.ilike(like), Student.reg_number.ilike(like)))
    if school_id:
        query = query.filter_by(school_id=school_id)

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Student.school_id, Student.last_name, Student.first_name).paginate(
        page=page, per_page=LIST_PAGE_SIZE, error_out=False,
    )
    schools = School.query.order_by(School.name).all()
    filter_qs = {k: v for k, v in {'q': q, 'school_id': school_id}.items() if v}

    return render_template(
        'superadmin/students.html', students=pagination.items, pagination=pagination,
        schools=schools, q=q, school_id=school_id, filter_qs=filter_qs,
    )


# ── Disable / Enable individual user ─────────────────────────────────────────

@superadmin_bp.route('/users/<int:id>/disable', methods=['POST'])
@login_required
@super_admin_required
def disable_user(id):
    user = User.query.get_or_404(id)
    if user.is_super_admin:
        flash('Cannot disable a super admin account.', 'error')
    else:
        user.is_active = False
        db.session.commit()
        log_audit_event('USER_SUSPENDED', actor=current_user, school_id=user.school_id,
                         resource_type='user', resource_id=id, extra={'role': user.role})
        flash(f'{user.display_name} has been disabled.', 'success')
    next_url = request.referrer or url_for('superadmin.school_detail', id=user.school_id)
    return redirect(next_url)


@superadmin_bp.route('/users/<int:id>/enable', methods=['POST'])
@login_required
@super_admin_required
def enable_user(id):
    user = User.query.get_or_404(id)
    user.is_active = True
    db.session.commit()
    log_audit_event('USER_REACTIVATED', actor=current_user, school_id=user.school_id,
                     resource_type='user', resource_id=id, extra={'role': user.role})
    flash(f'{user.display_name} has been re-enabled.', 'success')
    next_url = request.referrer or url_for('superadmin.school_detail', id=user.school_id)
    return redirect(next_url)


# ── Reset password ────────────────────────────────────────────────────────────

@superadmin_bp.route('/users/<int:id>/reset-password', methods=['GET', 'POST'])
@login_required
@super_admin_required
def reset_password(id):
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm', '').strip()

        if password_error(password):
            flash(password_error(password), 'error')
        elif password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            user.set_password(password)
            db.session.commit()
            log_audit_event('ADMIN_PASSWORD_RESET', actor=current_user, school_id=user.school_id,
                             resource_type='user', resource_id=id)
            flash(f'Password reset for {user.display_name}.', 'success')
            if user.school_id:
                return redirect(url_for('superadmin.school_detail', id=user.school_id))
            return redirect(url_for('superadmin.schools_list'))

    return render_template('superadmin/reset_password.html', user=user)


# ── Change user role ──────────────────────────────────────────────────────────

@superadmin_bp.route('/users/<int:id>/change-role', methods=['POST'])
@login_required
@super_admin_required
def change_role(id):
    user = User.query.get_or_404(id)
    new_role = request.form.get('role', '').strip()

    allowed = ('school_admin', 'teacher')
    if new_role not in allowed:
        flash('Invalid role.', 'error')
    elif user.is_super_admin:
        flash('Cannot change the role of a super admin.', 'error')
    else:
        old_role = user.role
        user.role = new_role
        db.session.commit()
        log_audit_event('ROLE_CHANGED', actor=current_user, school_id=user.school_id,
                         resource_type='user', resource_id=id,
                         changes={'role': {'old': old_role, 'new': new_role}})
        flash(f'{user.display_name} is now a {new_role.replace("_", " ").title()}.', 'success')

    next_url = request.referrer or url_for('superadmin.school_detail', id=user.school_id)
    return redirect(next_url)


# ── Analytics ─────────────────────────────────────────────────────────────────

@superadmin_bp.route('/analytics')
@login_required
@super_admin_required
def analytics():
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)

    dau = _distinct_active_users(today_start)
    wau = _distinct_active_users(week_start)
    mau = _distinct_active_users(month_start)

    feature_usage = (
        db.session.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc()).limit(15).all()
    )

    engagement_rows = (
        db.session.query(AuditLog.school_id, func.count(AuditLog.id))
        .filter(AuditLog.school_id.isnot(None))
        .group_by(AuditLog.school_id).order_by(func.count(AuditLog.id).desc()).limit(10).all()
    )
    school_names = {s.id: s.name for s in School.query.all()}
    school_engagement = [(school_names.get(sid, f'School #{sid}'), count) for sid, count in engagement_rows]

    hourly_rows = (
        db.session.query(func.strftime('%H', AuditLog.created_at), func.count(AuditLog.id))
        .group_by(func.strftime('%H', AuditLog.created_at)).all()
    )
    hourly_map = {int(h): c for h, c in hourly_rows if h is not None}
    hourly_activity = [hourly_map.get(h, 0) for h in range(24)]
    max_hourly = max(hourly_activity) if any(hourly_activity) else 1

    total_grades = Grade.query.count()
    pass_count = Grade.query.filter_by(is_pass=True).count()
    pass_rate = round(pass_count / total_grades * 100, 1) if total_grades else None
    grade_dist_rows = (
        db.session.query(Grade.grade_letter, func.count(Grade.id))
        .group_by(Grade.grade_letter).order_by(func.count(Grade.id).desc()).all()
    )

    return render_template(
        'superadmin/analytics.html',
        dau=dau, wau=wau, mau=mau,
        feature_usage=feature_usage, school_engagement=school_engagement,
        hourly_activity=hourly_activity, max_hourly=max_hourly,
        total_grades=total_grades, pass_rate=pass_rate, grade_dist_rows=grade_dist_rows,
    )


# ── Security Centre ───────────────────────────────────────────────────────────

@superadmin_bp.route('/security')
@login_required
@super_admin_required
def security_centre():
    recent_failed_logins = (
        AuditLog.query.filter_by(action='LOGIN_FAILED').order_by(desc(AuditLog.created_at)).limit(20).all()
    )
    locked_accounts = (
        User.query.filter(User.locked_until.isnot(None), User.locked_until > datetime.utcnow())
        .order_by(desc(User.locked_until)).all()
    )
    unauthorized_attempts = (
        AuditLog.query.filter_by(action='UNAUTHORIZED_ACCESS_ATTEMPT').order_by(desc(AuditLog.created_at)).limit(20).all()
    )
    malware_detections = (
        AuditLog.query.filter_by(action='FILE_SCAN_FAILED').order_by(desc(AuditLog.created_at)).limit(20).all()
    )
    rate_limit_hits = (
        AuditLog.query.filter_by(action='RATE_LIMIT_TRIGGERED').order_by(desc(AuditLog.created_at)).limit(20).all()
    )

    return render_template(
        'superadmin/security.html',
        recent_failed_logins=recent_failed_logins, locked_accounts=locked_accounts,
        unauthorized_attempts=unauthorized_attempts, malware_detections=malware_detections,
        rate_limit_hits=rate_limit_hits,
    )


# ── Audit logs ────────────────────────────────────────────────────────────────

AUDIT_LOG_PAGE_SIZE = 50


@superadmin_bp.route('/audit-logs')
@login_required
@super_admin_required
def audit_logs():
    query = AuditLog.query

    school_id = request.args.get('school_id', type=int)
    actor_user_id = request.args.get('actor_user_id', type=int)
    role = request.args.get('role', '').strip()
    action = request.args.get('action', '').strip()
    result = request.args.get('result', '').strip()
    resource_type = request.args.get('resource_type', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    if school_id:
        query = query.filter(AuditLog.school_id == school_id)
    if actor_user_id:
        query = query.filter(AuditLog.actor_user_id == actor_user_id)
    if role:
        query = query.filter(AuditLog.actor_role == role)
    if action:
        query = query.filter(AuditLog.action == action)
    if result:
        query = query.filter(AuditLog.result == result)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to + ' 23:59:59')

    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=AUDIT_LOG_PAGE_SIZE, error_out=False,
    )

    schools = School.query.order_by(School.name).all()
    distinct_actions = [r[0] for r in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]

    log_audit_event('SUPER_ADMIN_VIEWED_AUDIT_LOGS', actor=current_user)

    filters = {
        'school_id': school_id, 'actor_user_id': actor_user_id, 'role': role,
        'action': action, 'result': result, 'resource_type': resource_type,
        'date_from': date_from, 'date_to': date_to,
    }
    # Only non-empty filters go into pagination links -- url_for would
    # otherwise render e.g. ?actor_user_id=None into the querystring.
    filter_qs = {k: v for k, v in filters.items() if v}

    return render_template(
        'superadmin/audit_log.html',
        pagination=pagination, logs=pagination.items,
        schools=schools, distinct_actions=distinct_actions,
        filters=filters, filter_qs=filter_qs,
    )
