from pathlib import Path
from datetime import timezone
from zoneinfo import ZoneInfo
from flask import Flask, g, render_template
from flask_login import AnonymousUserMixin
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from config import Config
from app.extensions import db, migrate, login_manager, csrf

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def create_app(config_class=Config):
    flask_app = Flask(
        __name__,
        template_folder=str(FRONTEND_DIR / "templates"),
        static_folder=str(FRONTEND_DIR / "static"),
        static_url_path="/static",
    )
    if isinstance(config_class, dict):
        flask_app.config.from_object(Config)
        flask_app.config.update(config_class)
    else:
        flask_app.config.from_object(config_class)

    # Cloud MySQL can close idle connections; verify them before reuse.
    if make_url(flask_app.config['SQLALCHEMY_DATABASE_URI']).get_backend_name() == 'mysql':
        engine_options = dict(flask_app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {}))
        engine_options.setdefault('pool_pre_ping', True)
        engine_options.setdefault('pool_recycle', 280)
        connect_args = dict(engine_options.get('connect_args', {}))
        connect_args.setdefault('connect_timeout', 10)
        engine_options['connect_args'] = connect_args
        flask_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

    # Initialize extensions
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    from app.services.medicine_scan import Store
    flask_app.extensions['medicine_scans'] = Store()

    # Configure login manager
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Silakan masuk terlebih dahulu untuk mengakses halaman ini."
    login_manager.login_message_category = "warning"

    # Import models for Flask-Migrate & SQLAlchemy discovery
    from app import models  # noqa: F401
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.citizen import citizen_bp
    from app.routes.admin import admin_bp
    from app.routes.facilities import facilities_bp
    from app.routes.assistant import assistant_bp

    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(citizen_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(facilities_bp)
    flask_app.register_blueprint(assistant_bp)

    @flask_app.context_processor
    def mapbox_settings():
        from app.services.mapbox_service import public_settings
        return {"map_settings": public_settings()}

    # Register CLI commands
    from app.cli import register_cli_commands
    register_cli_commands(flask_app)

    # Template filters
    @flask_app.template_filter("wib_datetime")
    def format_wib_datetime(value, fmt="%d %B %Y %H:%M WIB"):
        if value is None:
            return "-"
        # Persisted datetimes use UTC; MySQL/SQLite return them without tzinfo.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(ZoneInfo("Asia/Jakarta")).strftime(fmt)

    @flask_app.template_filter("rupiah")
    def format_rupiah(value):
        if value is None:
            return "Rp0"
        try:
            from decimal import Decimal
            val_int = int(round(Decimal(str(value))))
            formatted = f"{val_int:,}".replace(",", ".")
            return f"Rp{formatted}"
        except Exception:
            return f"Rp{value}"

    # Error handlers
    @flask_app.errorhandler(OperationalError)
    def database_unavailable(error):
        db.session.rollback()
        # Avoid another database lookup from the navbar if user loading failed.
        # The login session remains intact for the next request.
        g._login_user = AnonymousUserMixin()
        flask_app.logger.warning('Database temporarily unavailable (%s)', type(error.orig).__name__)
        return render_template('errors/503.html'), 503, {'Retry-After': '30', 'Cache-Control': 'no-store'}

    @flask_app.errorhandler(400)
    def bad_request_error(error):
        return render_template("errors/400.html"), 400

    @flask_app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html"), 403

    @flask_app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @flask_app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return flask_app
