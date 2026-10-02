from flask import Blueprint, jsonify
from flask_login import login_required

from models import Student, Report, Class, Subject
from routes.utils import school_id, staff_required

api_dashboard_bp = Blueprint('api_dashboard', __name__, url_prefix='/api/dashboard')


@api_dashboard_bp.route('/')
@login_required
@staff_required
def index():
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
    return jsonify({
        'stats': stats,
        'recent_reports': [
            {
                'id': r.id,
                'student_name': r.student.full_name,
                'term_name': r.term.name,
                'status': r.status,
                'average_score': r.average_score,
                'overall_grade': r.overall_grade,
                'created_at': r.created_at.isoformat(),
            }
            for r in recent_reports
        ],
    })
