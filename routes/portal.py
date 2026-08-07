from flask import Blueprint, render_template, abort, redirect, url_for
from flask_login import login_required, current_user
from models import Report

portal_bp = Blueprint('portal', __name__, url_prefix='/portal')


def _portal_required():
    if not current_user.is_portal_user:
        return redirect(url_for('dashboard.index'))
    return None


@portal_bp.route('/')
@login_required
def dashboard():
    if not current_user.is_portal_user:
        return redirect(url_for('dashboard.index'))

    if current_user.role == 'student':
        student = current_user.student_profile
        reports = (
            sorted(student.reports, key=lambda r: r.created_at, reverse=True)
            if student else []
        )
        return render_template('portal/dashboard.html', student=student, reports=reports)

    # parent
    children = current_user.children
    return render_template('portal/dashboard.html', children=children)


@portal_bp.route('/report/<int:id>')
@login_required
def view_report(id):
    if not current_user.is_portal_user:
        return redirect(url_for('reports.view', id=id))

    report = Report.query.get_or_404(id)

    # Only published reports are visible in the portal
    if report.status != 'published':
        abort(403)

    # Students can only see their own reports
    if current_user.role == 'student':
        student = current_user.student_profile
        if not student or student.id != report.student_id:
            abort(403)

    # Parents can only see their children's reports
    elif current_user.role == 'parent':
        child_ids = {c.id for c in current_user.children}
        if report.student_id not in child_ids:
            abort(403)

    return render_template('portal/report.html', report=report)
