"""Church Bell System - Flask Application Factory."""

import os
from flask import Flask
from app.config import Config
from app.database import init_db


def create_app(config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Load config
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    # Ensure directories exist
    os.makedirs(app.config['MUSIC_DIR'], exist_ok=True)
    os.makedirs(app.config['DATA_DIR'], exist_ok=True)

    # Initialize database
    init_db(app)

    # Register blueprints
    from app.routes.views import views_bp
    from app.routes.api import api_bp
    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Initialize services (lazy, after app context)
    with app.app_context():
        from app.services import init_services
        init_services(app)

    return app
