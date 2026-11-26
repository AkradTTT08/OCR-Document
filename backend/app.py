"""Spectra QA Backend — Modular Flask Application Entrypoint."""
import logging
import os
import re as _re
import sys
from pathlib import Path

# Ensure backend and project root are on sys.path before local imports
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.append(_parent_dir)

# Load environment variables & configure logging first
from core.config import (  # noqa: E402
    AVATARS_FOLDER,
    BASE_DIR,
    CACHE_FOLDER,
    FRONTEND_FOLDER,
    KB_IMAGES_FOLDER,
    MAX_CONTENT_LENGTH,
    SVELTE_DIST,
    UPLOAD_FOLDER,
    WIREFRAMES_FOLDER,
    _auto_init_tables,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

from flask import Flask, request  # noqa: E402
from flask_cors import CORS  # noqa: E402

from core.auth import _attach_request_username  # noqa: E402
from dictionary_manager import get_dictionary_stats  # noqa: E402
from ocr_engine import VERSION  # noqa: E402
from routes import register_blueprints  # noqa: E402

# Re-export symbols imported externally (e.g. mcp_server.py)
from routes.exit_criteria import evaluate_document_exit_criteria  # noqa: E402, F401


def create_app() -> Flask:
    """Application factory configuring CORS, security headers, hooks, and all domain blueprints."""
    flask_app = Flask(__name__)

    _env_origins = [o.strip() for o in os.environ.get('ALLOWED_ORIGINS', '').split(',') if o.strip()]
    _allowed_origins = _env_origins + [
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5000',
        'http://127.0.0.1:5000',
        _re.compile(r'^chrome-extension://[a-z]{32}$'),
    ]
    CORS(flask_app, origins=_allowed_origins, supports_credentials=False)

    flask_app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
    flask_app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    @flask_app.before_request
    def _before_request_attach_user():
        return _attach_request_username()

    @flask_app.after_request
    def apply_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), geolocation=(), payment=()')
        if request.path.startswith(('/api/login', '/api/logout', '/api/users')):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
        return response

    register_blueprints(flask_app)
    return flask_app


# Auto-initialize essential DB tables (runs under both Gunicorn and standalone)
_auto_init_tables()

app = create_app()


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info(f"Thai OCR Spell Check System (v{VERSION})")
    logger.info("=" * 50)

    logger.info("กำลังโหลด dictionary...")
    stats = get_dictionary_stats()
    logger.info(f"Dictionary พร้อมใช้งาน: {stats['total_words']:,} คำ")

    logger.info("กำลังเริ่มต้นตาราง DB ที่จำเป็น...")
    try:
        from db_ingestion import (
            init_api_usage_logs,
            init_billing_credit,
            init_ocr_history,
            init_qa_transactions,
        )
        init_qa_transactions()
        init_api_usage_logs()
        init_billing_credit()
        init_ocr_history()

        try:
            from agent_1_ingestion import init_requirements_table
            init_requirements_table()
        except Exception as err:
            logger.error(f"Failed to initialize requirements table: {err}")

        try:
            try:
                from scripts.add_agent_sessions_table import create_agent_sessions_table
            except ImportError:
                from add_agent_sessions_table import create_agent_sessions_table
            create_agent_sessions_table()
        except Exception as err:
            logger.error(f"Failed to initialize agent sessions table: {err}")
    except Exception as e:
        logger.error(f"Failed to initialize DB tables: {e}")

    logger.info("กำลังตรวจสอบและสร้างตาราง Exit Criteria...")
    try:
        try:
            from scripts.add_exit_criteria_tables import add_exit_criteria_tables
        except ImportError:
            from add_exit_criteria_tables import add_exit_criteria_tables
        add_exit_criteria_tables()
        logger.info("Exit Criteria tables ready.")
    except Exception as e:
        logger.error(f"Failed to initialize Exit Criteria tables: {e}")

    try:
        from agent_7_flow_analyzer import init_flow_diagrams_table
        init_flow_diagrams_table()
    except Exception as e:
        logger.error(f"Failed to initialize QA Analysis Diagrams table: {e}")

    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=False,
        threaded=True,
    )
