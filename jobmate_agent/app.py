"""
Flask application factory for Jobmate.Agent.
Sets up configuration, database, migrations, CORS, and registers blueprints.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

# Re-export db for scripts that import from jobmate_agent.app
from jobmate_agent.extensions import db, bcrypt, migrate


def _resolve_database_uri() -> str:
    """Resolve SQLAlchemy database URI from environment.

    Supports dual modes:
    - sqlite via `DATABASE_MODE=sqlite` and `DATABASE_DEV`
    - postgres via `DATABASE_MODE=postgres` and `DATABASE_PROD`

    Falls back to `DATABASE_ENV` for compatibility with scripts.
    """
    mode = (os.getenv("DATABASE_MODE") or os.getenv("DATABASE_ENV") or "sqlite").lower()
    if mode == "postgres":
        uri = os.getenv("DATABASE_PROD")
        if not uri:
            raise RuntimeError("DATABASE_PROD must be set when DATABASE_MODE=postgres")
        return uri
    # default sqlite dev path
    uri = os.getenv("DATABASE_DEV") or "sqlite:///instance/efficientai.db"
    return uri


def _ensure_instance_dir(app: Flask) -> None:
    """Ensure the Flask instance directory exists (for SQLite and local storage)."""
    try:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except Exception:
        # Non-fatal; continue even if instance dir can't be created
        pass


def create_app() -> Flask:
    """Create and configure the Flask application."""
    # Load .env for development convenience
    load_dotenv()

    app = Flask(__name__, instance_relative_config=True)

    # Base config
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", _resolve_database_uri())
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("JSON_SORT_KEYS", False)

    # Optional: Secret key for sessions (not critical for API-only)
    app.config.setdefault("SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret-key"))

    # Ensure instance dir exists (for sqlite file path and chroma default directory)
    _ensure_instance_dir(app)

    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    # Enable CORS (allow frontend dev server)
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:3000",
                    "http://127.0.0.1:3000",
                    "http://localhost:3001",
                ]
            }
        },
        supports_credentials=True,
    )

    # Register API blueprint
    from jobmate_agent.blueprints.api import api_bp

    app.register_blueprint(api_bp)

    # Configure logging (info level, file + stderr) if not already configured
    if not app.logger.handlers:
        app.logger.setLevel(logging.INFO)
        root = logging.getLogger()
        if not root.handlers:
            root.setLevel(logging.INFO)
            # Stream handler
            sh = logging.StreamHandler()
            sh.setLevel(logging.INFO)
            root.addHandler(sh)
            # Rotating file handler
            log_path = os.getenv("JOBMATE_LOG", "jobmate_agent.log")
            try:
                fh = RotatingFileHandler(
                    log_path, maxBytes=5 * 1024 * 1024, backupCount=2
                )
                fh.setLevel(logging.INFO)
                formatter = logging.Formatter(
                    "%(asctime)s %(levelname)s [%(name)s] %(message)s"
                )
                fh.setFormatter(formatter)
                root.addHandler(fh)
            except Exception:
                pass

    # Ensure info-level logging even when handlers already exist (e.g., Flask debug server)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in root_logger.handlers:
        handler.setLevel(logging.INFO)

    if not any(
        isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers
    ):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        root_logger.addHandler(stream_handler)

    app.logger.setLevel(logging.INFO)
    for handler in app.logger.handlers:
        handler.setLevel(logging.INFO)

    return app
