from flask import current_app, url_for
from flask_mail import Message

from models import mail


def _is_real_email(email):
    return bool(email) and not email.lower().endswith(('.local',))


def _report_recipients(student):
    emails = set()
    if student.login_user and _is_real_email(student.login_user.email):
        emails.add(student.login_user.email)
    for parent in student.parents:
        if _is_real_email(parent.email):
            emails.add(parent.email)
    return emails


def send_report_published_email(report):
    """Email the student/parent that a report card has been published.

    Returns (sent_count, recipient_count) so callers can flash an accurate
    status message. Never raises: a broken mail server should not block
    publishing a report.
    """
    recipients = _report_recipients(report.student)
    if not recipients:
        return 0, 0

    portal_url = url_for('portal.view_report', id=report.id, _external=True)
    average = report.average_score
    subject = f"{report.student.full_name}'s report card is ready ({report.term.name})"
    body = (
        f"Hello,\n\n"
        f"{report.student.full_name}'s report card for {report.term.name} has been published.\n"
        f"Overall average: {f'{average}%' if average is not None else 'N/A'}\n"
        f"Overall grade: {report.overall_grade}\n\n"
        f"View the full report card here:\n{portal_url}\n\n"
        f"InsightScholar"
    )

    try:
        msg = Message(subject=subject, recipients=list(recipients), body=body)
        mail.send(msg)
        return len(recipients), len(recipients)
    except Exception:
        current_app.logger.exception('Failed to send report-published email for report %s', report.id)
        return 0, len(recipients)


def send_password_reset_email(user, reset_url):
    """Email a password reset link to a user. Returns True on success, never raises."""
    if not _is_real_email(user.email):
        return False

    subject = 'Reset your InsightScholar password'
    body = (
        f"Hello {user.display_name},\n\n"
        f"We received a request to reset your InsightScholar password.\n"
        f"Click the link below to choose a new one. This link expires in 1 hour.\n\n"
        f"{reset_url}\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"InsightScholar"
    )

    try:
        msg = Message(subject=subject, recipients=[user.email], body=body)
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception('Failed to send password reset email for user %s', user.id)
        return False


def send_account_credentials_email(user, password, role_label='account'):
    """Email a newly created user their username and auto-generated password.

    Returns True on success, False if there's nowhere to send it or sending
    failed. Never raises.
    """
    if not _is_real_email(user.email):
        return False

    login_url = url_for('auth.login', _external=True)
    subject = f'Your InsightScholar {role_label} login'
    body = (
        f"Hello {user.display_name},\n\n"
        f"An InsightScholar {role_label} account has been created for you.\n\n"
        f"Username: {user.username}\n"
        f"Password: {password}\n\n"
        f"Sign in here: {login_url}\n"
        f"We recommend changing your password after your first login.\n\n"
        f"InsightScholar"
    )

    try:
        msg = Message(subject=subject, recipients=[user.email], body=body)
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception('Failed to send account credentials email for user %s', user.id)
        return False


def send_verification_code_email(email, code):
    """Email a one-time code to confirm an address during school registration."""
    subject = 'Confirm your email - InsightScholar'
    body = (
        f"Hello,\n\n"
        f"Your InsightScholar email verification code is:\n\n"
        f"    {code}\n\n"
        f"Enter this code to confirm your email and finish registering your school.\n"
        f"This code expires in 10 minutes.\n\n"
        f"If you didn't request this, you can safely ignore this email.\n\n"
        f"InsightScholar"
    )

    try:
        msg = Message(subject=subject, recipients=[email], body=body)
        mail.send(msg)
        return True
    except Exception:
        current_app.logger.exception('Failed to send verification code email to %s', email)
        return False
