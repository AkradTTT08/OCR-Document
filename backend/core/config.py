"""Shared environment, folder paths, constants, and startup table initialization."""
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

logger = logging.getLogger(__name__)

UPLOAD_FOLDER = BASE_DIR / 'uploads'
SVELTE_DIST = BASE_DIR / 'svelte-app' / 'dist'
FRONTEND_FOLDER = SVELTE_DIST if SVELTE_DIST.exists() else (BASE_DIR / 'frontend')
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

UPLOAD_FOLDER.mkdir(exist_ok=True)
CACHE_FOLDER = BASE_DIR / 'uploads' / 'cache'
CACHE_FOLDER.mkdir(exist_ok=True, parents=True)
KB_IMAGES_FOLDER = BASE_DIR / 'uploads' / 'kb_images'
KB_IMAGES_FOLDER.mkdir(exist_ok=True, parents=True)
AVATARS_FOLDER = BASE_DIR / 'uploads' / 'avatars'
AVATARS_FOLDER.mkdir(exist_ok=True, parents=True)
WIREFRAMES_FOLDER = BASE_DIR / 'uploads' / 'wireframes'
WIREFRAMES_FOLDER.mkdir(exist_ok=True, parents=True)
_QA_CONSULT_PAGES_DIR = str(BASE_DIR / 'uploads' / 'qa_consult_pages')
os.makedirs(_QA_CONSULT_PAGES_DIR, exist_ok=True)

MASTER_DOC_TYPES = [
    'Project Plan',
    'SRS',
    'SDD',
    'UAT',
    'Test Case',
    'Technical Spec',
    'SOP',
    'Contract',
    'Project Proposal',
    'Summary Report',
    'General',
]


def _auto_init_tables():
    try:
        from db_ingestion import init_qa_transactions, init_api_usage_logs, init_billing_credit, init_ocr_history
        init_ocr_history()
        init_qa_transactions()
        init_api_usage_logs()
        init_billing_credit()
        try:
            from agent_1_ingestion import init_requirements_table
            init_requirements_table()
        except Exception:
            pass
        try:
            from agent_7_flow_analyzer import init_flow_diagrams_table
            init_flow_diagrams_table()
        except Exception:
            pass
        try:
            from db_ingestion import get_auth_db_connection
            _auth_conn = get_auth_db_connection()
            _auth_cur = _auth_conn.cursor()
            _auth_cur.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS github_url VARCHAR(255);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(255);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS line_id VARCHAR(100);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR(100);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_menus TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS allowed_projects TEXT;
            """)
            _auth_conn.commit()
            _auth_cur.close()
            _auth_conn.close()
        except Exception as _u_err:
            logger.warning(f"Could not ensure users columns on startup: {_u_err}")
    except Exception as e:
        logger.warning(f"Could not auto-initialize DB tables on startup: {e}")


def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

