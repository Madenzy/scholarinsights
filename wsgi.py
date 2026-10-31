"""WSGI entry point for production servers (PythonAnywhere, gunicorn).

PythonAnywhere: in the WSGI config file, add this project's folder to
sys.path and use:  from wsgi import application
gunicorn:          gunicorn wsgi:application
"""
from app import create_app

application = create_app()
