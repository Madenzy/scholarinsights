from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, GradeBand
from routes.utils import school_id, admin_required
from audit import log_audit_event

grading_bp = Blueprint('grading', __name__, url_prefix='/grading')


@grading_bp.route('/')
@login_required
@admin_required
def index():
    bands = GradeBand.query.filter_by(school_id=school_id()).order_by(GradeBand.min_score.desc()).all()
    return render_template('grading/index.html', bands=bands)


@grading_bp.route('/save', methods=['POST'])
@login_required
@admin_required
def save():
    sid = school_id()
    bands = GradeBand.query.filter_by(school_id=sid).all()
    band_map = {b.id: b for b in bands}

    seen_letters = set()
    error = None
    band_changes = []

    for band_id, band in band_map.items():
        prefix = f'band_{band_id}_'
        letter = request.form.get(f'{prefix}letter', '').strip()
        min_score = request.form.get(f'{prefix}min_score', type=float)
        remark = request.form.get(f'{prefix}remark', '').strip()
        is_pass = bool(request.form.get(f'{prefix}is_pass'))

        if not letter or min_score is None:
            error = 'Every band needs a letter and a minimum score.'
            break
        if letter.upper() in seen_letters:
            error = f'Letter "{letter}" is used more than once.'
            break
        seen_letters.add(letter.upper())

        before = (band.letter, band.min_score, band.remark, band.is_pass)
        after = (letter, max(0.0, min(100.0, min_score)), remark or None, is_pass)
        if before != after:
            band_changes.append({'band_id': band_id, 'letter': letter})

        band.letter = letter
        band.min_score = max(0.0, min(100.0, min_score))
        band.remark = remark or None
        band.is_pass = is_pass

    if not error:
        db.session.commit()
        if band_changes:
            log_audit_event('GRADING_SCALE_UPDATED', actor=current_user, school_id=sid,
                             resource_type='grade_band', extra={'bands_changed': band_changes})
        flash('Grading scale updated.', 'success')
    else:
        db.session.rollback()
        flash(error, 'error')

    return redirect(url_for('grading.index'))


@grading_bp.route('/add', methods=['POST'])
@login_required
@admin_required
def add():
    sid = school_id()
    letter = request.form.get('letter', '').strip()
    min_score = request.form.get('min_score', type=float)
    remark = request.form.get('remark', '').strip()
    is_pass = bool(request.form.get('is_pass'))

    if not letter or min_score is None:
        flash('A new band needs a letter and a minimum score.', 'error')
    elif GradeBand.query.filter_by(school_id=sid, letter=letter).first():
        flash(f'Letter "{letter}" already exists.', 'error')
    else:
        max_order = db.session.query(db.func.max(GradeBand.sort_order)).filter_by(school_id=sid).scalar()
        band = GradeBand(
            school_id=sid, letter=letter, min_score=max(0.0, min(100.0, min_score)),
            remark=remark or None, is_pass=is_pass, sort_order=(max_order or 0) + 1,
        )
        db.session.add(band)
        db.session.commit()
        log_audit_event('GRADING_SCALE_UPDATED', actor=current_user, school_id=sid,
                         resource_type='grade_band', resource_id=band.id,
                         extra={'action': 'band_added', 'letter': letter})
        flash(f'Added grade "{letter}".', 'success')

    return redirect(url_for('grading.index'))


@grading_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(id):
    sid = school_id()
    band = GradeBand.query.filter_by(id=id, school_id=sid).first_or_404()
    letter = band.letter
    db.session.delete(band)
    db.session.commit()
    log_audit_event('GRADING_SCALE_UPDATED', actor=current_user, school_id=sid,
                     resource_type='grade_band', resource_id=id,
                     extra={'action': 'band_removed', 'letter': letter})
    flash(f'Removed grade "{letter}".', 'success')
    return redirect(url_for('grading.index'))
