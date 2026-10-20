from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    from .api import bp
    from .signals import bp as signals_bp
    app.register_blueprint(bp)
    app.register_blueprint(signals_bp)
    return app
