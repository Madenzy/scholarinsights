from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user
from models import Student, Report, Class, Subject, AcademicTerm
from routes.utils import school_id, staff_required

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    # Unauthenticated visitors see the public landing page
    if not current_user.is_authenticated:
        return render_template('landing.html')

    # Authenticated users go to their respective area
    if current_user.is_super_admin:
        return redirect(url_for('superadmin.index'))
    if current_user.is_portal_user:
        return redirect(url_for('portal.dashboard'))

    sid = school_id()
    stats = {
        'students': Student.query.filter_by(school_id=sid).count(),
        'reports': Report.query.filter_by(school_id=sid).count(),
        'classes': Class.query.filter_by(school_id=sid).count(),
        'subjects': Subject.query.filter_by(school_id=sid).count(),
    }
    recent_reports = (
        Report.query.filter_by(school_id=sid)
        .order_by(Report.created_at.desc())
        .limit(8)
        .all()
    )
    terms = (
        AcademicTerm.query.filter_by(school_id=sid)
        .order_by(AcademicTerm.year.desc(), AcademicTerm.term_number.desc())
        .all()
    )
    return render_template(
        'dashboard/index.html',
        stats=stats,
        recent_reports=recent_reports,
        terms=terms,
    )
