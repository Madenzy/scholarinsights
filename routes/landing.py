from flask import Blueprint, jsonify, request

landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/contact', methods=['POST'])
def contact():
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    message = data.get('message', '').strip()

    if not name or not email or not message:
        return jsonify({'error': 'Please fill in all required fields.'}), 400

    # TODO: persist to DB or send email notification
    return jsonify({'message': "Thanks for reaching out! We'll get back to you within one business day."})
