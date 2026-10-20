"""Flask application factory for the whoknows backend."""
from flask import Flask


def create_app() -> Flask:
    """Build the Flask app and register the API blueprint."""
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 32_768
    from .auth import authenticate
    app.before_request(authenticate)
    from .api import bp
    from .signals import bp as signals_bp
    app.register_blueprint(bp)
    app.register_blueprint(signals_bp)
    return app
