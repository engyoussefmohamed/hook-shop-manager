import os
import sys
import time
import logging
import secrets
import threading
import webbrowser
import traceback

from flask import Flask
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

from config import APP_DIR

# --- file logging so errors are visible when console=False ---
_LOG_FILE = os.path.join(APP_DIR, "app_error.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
csrf = CSRFProtect()

if getattr(sys, "frozen", False):
    _RES_DIR = sys._MEIPASS
else:
    _RES_DIR = APP_DIR


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(_RES_DIR, "templates"),
        static_folder=os.path.join(_RES_DIR, "static"),
    )

    _SECRET_FILE = os.path.join(APP_DIR, ".secret_key")
    if os.path.exists(_SECRET_FILE):
        with open(_SECRET_FILE) as _f:
            app.secret_key = _f.read().strip()
    else:
        app.secret_key = secrets.token_hex(32)
        with open(_SECRET_FILE, "w") as _f:
            _f.write(app.secret_key)

    from helpers import check_auth, inject_globals
    app.before_request(check_auth)
    app.context_processor(inject_globals)

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e
        logger.error("Unhandled exception:\n%s", traceback.format_exc())
        return "خطأ داخلي في البرنامج — تحقق من app_error.log", 500

    csrf.init_app(app)

    from blueprints.auth import auth_bp
    from blueprints.pos import pos_bp
    from blueprints.products import products_bp
    from blueprints.reports import reports_bp
    from blueprints.settings import settings_bp
    from blueprints.inventory import inventory_bp
    from blueprints.maintenance import maintenance_bp
    from blueprints.customers import customers_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(pos_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(customers_bp)

    return app


FLASK_URL = "http://127.0.0.1:5000"


def _wait_for_server(timeout=15):
    import urllib.request
    import urllib.error
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(FLASK_URL + "/pos", timeout=1)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    return False


def _start_flask():
    try:
        app = create_app()
        logger.info("Flask app created successfully")
    except Exception:
        logger.critical("Failed to create Flask app:\n%s", traceback.format_exc())
        return
    try:
        from waitress import serve
        logger.info("Starting waitress server on 0.0.0.0:5000")
        serve(app, host="0.0.0.0", port=5000)
    except ImportError:
        logger.warning("waitress not found, using Flask dev server")
        app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)
    except Exception:
        logger.critical("Server crashed:\n%s", traceback.format_exc())


def main():
    from database import init_db
    from services import backup as bk

    try:
        init_db()
    except Exception as exc:
        logger.exception("Failed to initialize database: %s", exc)

    try:
        bk.start_auto_backup()
    except Exception as exc:
        logger.exception("Failed to start auto backup scheduler: %s", exc)

    flask_thread = threading.Thread(target=_start_flask, daemon=True)
    flask_thread.start()

    if not _wait_for_server():
        logger.error("Flask server failed to start within timeout")
        return

    webbrowser.open(FLASK_URL + "/pos")
    flask_thread.join()


if __name__ == "__main__":
    main()
