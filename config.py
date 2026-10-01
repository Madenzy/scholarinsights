import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    # SQLALCHEMY_DATABASE_URI = os.environ.get(
    #     'DATABASE_URL', 'postgresql://localhost/scholarinsights'
    # )
    SQLALCHEMY_DATABASE_URI = 'sqlite:///scholarinsights.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
