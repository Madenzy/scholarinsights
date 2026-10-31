"""Start the InsightScholar development server.

    python run.py

Set FLASK_DEBUG=true in .env to turn on the debugger and auto-reload.
"""
import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    app.run(debug=debug)
