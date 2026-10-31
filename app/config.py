import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

APP_ENV = os.environ.get('APP_ENV', 'development')

_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if APP_ENV == 'production':
        raise RuntimeError(
            'SECRET_KEY must be set in the environment when APP_ENV=production. '
            'Refusing to start with the public dev fallback key.'
        )
    _secret_key = 'dev-key-change-in-production'

# Cookies/HSTS are only marked Secure when the app is actually served over
# HTTPS. Set this to true once deployed behind TLS (directly or via a
# TLS-terminating proxy, see BEHIND_PROXY in app.py) -- leaving it false in
# local HTTP dev so cookies still work on http://localhost.
SESSION_COOKIE_SECURE_FLAG = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in ('1', 'true', 'yes')


class Config:
    SECRET_KEY = _secret_key
    # SQLALCHEMY_DATABASE_URI = os.environ.get(
    #     'DATABASE_URL', 'postgresql://localhost/scholarinsights'
    # )
    SQLALCHEMY_DATABASE_URI = 'sqlite:///scholarinsights.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Sessions ────────────────────────────────────────────────
    SESSION_COOKIE_SECURE = SESSION_COOKIE_SECURE_FLAG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'  # not 'Strict': reset/verify links land as a top-level GET from a mail client
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE_FLAG
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=14)

    # ── CSRF (Flask-WTF) ────────────────────────────────────────
    WTF_CSRF_TIME_LIMIT = None  # tokens live as long as the session, not a fixed window
    WTF_CSRF_SSL_STRICT = SESSION_COOKIE_SECURE_FLAG
    WTF_CSRF_HEADERS = ['X-CSRFToken']

    # Email (report-published notifications, etc.)
    # Set MAIL_SERVER (and friends) in .env to send real email. Left unset,
    # MAIL_SUPPRESS_SEND defaults to on so the app never tries to reach an SMTP
    # server that isn't configured.
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'InsightScholar <no-reply@insightscholar.com>')
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', '' if MAIL_SERVER else 'true').lower() in ('1', 'true', 'yes')

    # ── Malware scanning (ClamAV via clamd) ────────────────────
    # clamd must be running and reachable at this host/port -- see malware_scan.py.
    # Scanning fails closed: if clamd can't be reached or errors, the upload is
    # rejected rather than let through unscanned.
    CLAMAV_HOST = os.environ.get('CLAMAV_HOST', '127.0.0.1')
    CLAMAV_PORT = int(os.environ.get('CLAMAV_PORT', 3310))
    CLAMAV_TIMEOUT = int(os.environ.get('CLAMAV_TIMEOUT', 10))
