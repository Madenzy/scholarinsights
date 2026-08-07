from flask import Blueprint, render_template

legal_bp = Blueprint('legal', __name__, url_prefix='/legal')


@legal_bp.route('/about')
def about():
    return render_template('legal/about.html')


@legal_bp.route('/privacy')
def privacy():
    return render_template('legal/privacy.html')


@legal_bp.route('/terms')
def terms():
    return render_template('legal/terms.html')


@legal_bp.route('/cookies')
def cookies():
    return render_template('legal/cookies.html')


@legal_bp.route('/security')
def security():
    return render_template('legal/security.html')
