"""Flask application factory for the whoknows backend."""
from flask import Flask


def create_app() -> Flask:
    """Build the Flask app and register the API blueprint."""
    app = Flask(__name__)
    from .api import bp
    app.register_blueprint(bp)
    return app
