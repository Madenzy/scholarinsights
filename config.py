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
