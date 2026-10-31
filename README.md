# InsightScholar

School report management platform: school registration, classes, subjects, terms, grading, report cards (online and PDF), a student/parent portal and a super admin panel.

Built with Flask + SQLAlchemy on the back end and React (Vite + TypeScript) for the newer front-end pages.

## Project layout

```
scholarinsights/
├── app/                    Flask back end (Python package)
│   ├── __init__.py         create_app() – builds and configures the app
│   ├── config.py           settings, read from .env
│   ├── extensions.py       shared extensions (rate limiter)
│   ├── models.py           database models
│   ├── audit.py            audit logging
│   ├── security/           security headers, upload virus scanning
│   ├── routes/             one blueprint per area (students, reports, ...)
│   │   └── api/            JSON API used by the React front end
│   ├── templates/          Jinja HTML pages
│   └── static/             CSS, JS and uploaded files
├── frontend/               React app (login, MFA, registration, dashboard)
│   ├── src/
│   └── dist/               built React app, served by Flask
├── migrations/             database migrations (Flask-Migrate / Alembic)
├── scripts/                one-off scripts (demo data seeding)
├── docs/                   project notes and design reference
├── run.py                  start the dev server
├── wsgi.py                 production entry point
├── requirements.txt
└── .env.example            copy to .env and fill in
```

## Running locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then edit .env

flask --app app db upgrade        # create/update the database
flask --app app create-superadmin
python run.py                     # http://127.0.0.1:5000
```

React front end (in a second terminal):

```bash
cd frontend
npm install
npm run dev      # dev server, proxies /api to Flask
npm run build    # rebuild frontend/dist for Flask to serve
```

## Deploying (PythonAnywhere)

In the WSGI configuration file, add the project folder to `sys.path` and import the app from `wsgi.py`:

```python
import sys
sys.path.insert(0, '/home/<username>/scholarinsights')
from wsgi import application
```

Set the static files mapping `/static/` to `/home/<username>/scholarinsights/app/static`.
