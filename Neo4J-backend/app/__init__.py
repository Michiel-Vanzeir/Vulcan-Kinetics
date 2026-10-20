"""Flask application factory for the whoknows backend."""
from flask import Flask


def create_app() -> Flask:
    """Build the Flask app and register the API blueprint."""
    app = Flask(__name__)
    from .api import bp
    from .signals import bp as signals_bp
    app.register_blueprint(bp)
    app.register_blueprint(signals_bp)
    return app
