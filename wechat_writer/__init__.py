from flask import Flask

from .config import RUNS_DIR, STATIC_DIR, TEMPLATES_DIR
from .routes import register_routes


def create_app():
    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path="/static",
        template_folder=str(TEMPLATES_DIR),
    )
    register_routes(app)
    return app


def ensure_runtime_dirs():
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
