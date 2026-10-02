from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

account_bp = Blueprint('account', __name__, url_prefix='/account')


@account_bp.route('/security')
@login_required
def security():
    if not current_user.is_staff and not current_user.is_super_admin:
        abort(403)
    mfa_setup_required = current_user.mfa_required and not current_user.mfa_enabled
    return render_template('account/security.html', mfa_setup_required=mfa_setup_required)
