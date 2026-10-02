import os

import click
from flask import Flask, request, send_from_directory
from flask_migrate import Migrate
from config import Config
from models import db, login_manager, mail, User

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), 'frontend', 'dist')


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.students import students_bp
    from routes.reports import reports_bp
    from routes.classes import classes_bp
    from routes.subjects import subjects_bp
    from routes.terms import terms_bp
    from routes.grading import grading_bp
    from routes.portal import portal_bp
    from routes.users import users_bp
    from routes.superadmin import superadmin_bp
    from routes.legal import legal_bp
    from routes.landing import landing_bp
    from routes.api.auth import api_auth_bp
    from routes.api.dashboard import api_dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(terms_bp)
    app.register_blueprint(grading_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(landing_bp)
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(api_dashboard_bp)

    @app.route('/assets/<path:filename>')
    def spa_assets(filename):
        return send_from_directory(os.path.join(FRONTEND_DIST, 'assets'), filename)

    @app.route('/favicon.svg')
    @app.route('/icons.svg')
    def spa_public_files():
        return send_from_directory(FRONTEND_DIST, request.path.lstrip('/'))

    @app.route('/login')
    @app.route('/register')
    @app.route('/forgot-password')
    @app.route('/reset-password/<path:token>')
    @app.route('/verify-email')
    def spa_auth_routes(token=None):
        return _serve_spa()

    def _serve_spa():
        index_path = os.path.join(FRONTEND_DIST, 'index.html')
        if not os.path.isfile(index_path):
            return (
                'The React app has not been built yet. Run `npm run build` in frontend/, '
                'or use `npm run dev` and visit the Vite dev server directly during development.',
                503,
            )
        return send_from_directory(FRONTEND_DIST, 'index.html')

    with app.app_context():
        db.create_all()

    @app.cli.command('create-superadmin')
    @click.option('--username', prompt=True)
    @click.option('--email', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    def create_superadmin(username, email, password):
        """Create the platform super admin account."""
        with app.app_context():
            if User.query.filter_by(role='super_admin').first():
                click.echo('A super admin account already exists.')
                return
            if User.query.filter_by(username=username).first():
                click.echo(f'Error: username "{username}" is already taken.')
                return
            user = User(username=username, email=email, full_name='Super Admin', role='super_admin')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            click.echo(f'Super admin "{username}" created. Log in at /auth/login')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
