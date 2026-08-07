import click
from flask import Flask
from flask_migrate import Migrate
from config import Config
from models import db, login_manager, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)

    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.students import students_bp
    from routes.reports import reports_bp
    from routes.classes import classes_bp
    from routes.subjects import subjects_bp
    from routes.terms import terms_bp
    from routes.portal import portal_bp
    from routes.users import users_bp
    from routes.superadmin import superadmin_bp
    from routes.legal import legal_bp
    from routes.landing import landing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(classes_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(terms_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(superadmin_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(landing_bp)

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
