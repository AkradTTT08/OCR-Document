"""Authentication (JWT, API tokens, RBAC decorators), login rate limiting, and audit logging."""
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from functools import wraps
from typing import Any, Dict, List

import jwt as pyjwt
from flask import jsonify, request

logger = logging.getLogger(__name__)

_env_jwt_secret = os.environ.get('JWT_SECRET', '').strip()
if not _env_jwt_secret or len(_env_jwt_secret) < 24:
    JWT_SECRET = secrets.token_urlsafe(48)
    logger.warning(
        "JWT_SECRET is missing or too short in .env; generated ephemeral per-process secret. "
        "Set a 32+ char JWT_SECRET in .env for persistent sessions."
    )
else:
    JWT_SECRET = _env_jwt_secret

_AUTH_LOCK = threading.Lock()
_REVOKED_JTIS: Dict[str, float] = {}
_USER_REVOKED_BEFORE: Dict[str, float] = {}

_LOGIN_WINDOW_SEC = 300
_MAX_FAILS_PER_ACCOUNT = 5
_MAX_FAILS_PER_IP = 15
_LOGIN_FAILS_IP: Dict[str, List[float]] = {}
_LOGIN_FAILS_ACCT: Dict[str, List[float]] = {}

_USER_SECURITY_SCHEMA_READY = False
_USER_SECURITY_SCHEMA_LOCK = threading.Lock()

DEFAULT_USER_MENUS = [
    "qa_consult", "qa_doc_creation", "qa_analysis_diagram", "qa_board",
    "qa_automate", "qa_performance", "qa_security", "qa_research",
    "master_agent", "workflow_builder"
]

DEFAULT_ADMIN_MENUS = [
    "ocr", "project_management", "kb", "skills", "qa_member",
    "exit_criteria", "api_collection", "api_usage"
]


def _get_client_ip() -> str:
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _prune_attempts(bucket: Dict[str, List[float]], key: str, now: float) -> List[float]:
    cutoff = now - _LOGIN_WINDOW_SEC
    recent = [ts for ts in bucket.get(key, []) if ts > cutoff]
    if recent:
        bucket[key] = recent
    else:
        bucket.pop(key, None)
    return recent


def _check_login_rate_limit(client_ip: str, acct_key: str):
    """Returns retry_after seconds (>0) if rate-limited, else 0."""
    now = time.time()
    with _AUTH_LOCK:
        ip_fails = _prune_attempts(_LOGIN_FAILS_IP, client_ip, now)
        acct_fails = _prune_attempts(_LOGIN_FAILS_ACCT, acct_key, now) if acct_key else []
        retry_after = 0
        if len(ip_fails) >= _MAX_FAILS_PER_IP:
            retry_after = max(retry_after, int(_LOGIN_WINDOW_SEC - (now - ip_fails[0])) + 1)
        if acct_key and len(acct_fails) >= _MAX_FAILS_PER_ACCOUNT:
            retry_after = max(retry_after, int(_LOGIN_WINDOW_SEC - (now - acct_fails[0])) + 1)
        return max(0, retry_after)


def _record_login_failure(client_ip: str, acct_key: str):
    now = time.time()
    with _AUTH_LOCK:
        _prune_attempts(_LOGIN_FAILS_IP, client_ip, now)
        _LOGIN_FAILS_IP.setdefault(client_ip, []).append(now)
        if acct_key:
            _prune_attempts(_LOGIN_FAILS_ACCT, acct_key, now)
            _LOGIN_FAILS_ACCT.setdefault(acct_key, []).append(now)


def _clear_login_failures(acct_key: str):
    if not acct_key:
        return
    with _AUTH_LOCK:
        _LOGIN_FAILS_ACCT.pop(acct_key, None)


def revoke_token_jti(jti: str, exp_ts: float):
    if not jti:
        return
    now = time.time()
    with _AUTH_LOCK:
        # Prune expired JTIs opportunistically
        expired = [k for k, v in _REVOKED_JTIS.items() if v < now]
        for k in expired:
            _REVOKED_JTIS.pop(k, None)
        _REVOKED_JTIS[jti] = exp_ts


def ensure_user_security_schema(conn=None):
    """Idempotently ensure security columns & user_api_tokens table exist, and hydrate revocation timestamps."""
    global _USER_SECURITY_SCHEMA_READY
    if _USER_SECURITY_SCHEMA_READY:
        return
    with _USER_SECURITY_SCHEMA_LOCK:
        if _USER_SECURITY_SCHEMA_READY:
            return
        own_conn = False
        try:
            if conn is None:
                from db_ingestion import get_auth_db_connection
                conn = get_auth_db_connection()
                own_conn = True
            cur = conn.cursor()
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_revoked_after DOUBLE PRECISION DEFAULT 0;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS monthly_token_quota BIGINT DEFAULT 0;")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS trello_username TEXT DEFAULT '';")
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS github_username TEXT DEFAULT '';")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_api_tokens (
                    token_id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    token_prefix TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    scopes TEXT DEFAULT 'extension,mcp',
                    created_by TEXT DEFAULT '',
                    last_used_at TIMESTAMP,
                    revoked_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_api_tokens_user_id ON user_api_tokens(user_id);")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_audit_logs (
                    audit_id SERIAL PRIMARY KEY,
                    target_user_id INTEGER,
                    target_username TEXT DEFAULT '',
                    actor_username TEXT DEFAULT '',
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    ip_address TEXT DEFAULT '',
                    user_agent TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_audit_logs_target ON user_audit_logs(target_user_id, created_at DESC);")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS permission_templates (
                    template_id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT DEFAULT '',
                    target_role TEXT DEFAULT 'user',
                    allowed_menus TEXT NOT NULL DEFAULT '[]',
                    allowed_projects TEXT NOT NULL DEFAULT '["all"]',
                    created_by TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("SELECT user_id, token_revoked_after FROM users WHERE COALESCE(token_revoked_after, 0) > 0;")
            rows = cur.fetchall()
            with _AUTH_LOCK:
                for uid, ts in rows:
                    if ts:
                        prev = _USER_REVOKED_BEFORE.get(str(uid), 0)
                        _USER_REVOKED_BEFORE[str(uid)] = max(prev, float(ts))
            conn.commit()
            cur.close()
            _USER_SECURITY_SCHEMA_READY = True
        except Exception as e:
            logger.warning(f"Could not ensure user security schema: {e}")
            try:
                if conn:
                    conn.rollback()
            except Exception:
                pass
        finally:
            if own_conn and conn:
                try:
                    conn.close()
                except Exception:
                    pass


def record_user_audit(target_user_id, target_username, action, details='', actor_username=None):
    """Best-effort audit trail recorder for QA Member governance & login visibility."""
    try:
        from db_ingestion import get_auth_db_connection
        ip_addr = ''
        ua = ''
        try:
            ip_addr = _get_client_ip()
            ua = (request.headers.get('User-Agent') or '')[:240]
            if actor_username is None:
                actor_username = get_request_user() or ''
        except Exception:
            pass
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_audit_logs (target_user_id, target_username, actor_username, action, details, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (
            int(target_user_id) if target_user_id is not None else None,
            str(target_username or '')[:120],
            str(actor_username or 'system')[:120],
            str(action or 'EVENT')[:64],
            str(details or '')[:500],
            ip_addr[:64],
            ua
        ))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Audit log write skipped ({action}): {e}")


def _fetch_monthly_token_usage_map():
    """Returns dict {lower_username: {'tokens': int, 'cost_usd': float, 'requests': int}} for current month."""
    usage_map = {}
    try:
        from db_ingestion import get_ocr_db_connection
        conn = get_ocr_db_connection()
        cur = conn.cursor()
        cur.execute("ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS username VARCHAR(120);")
        conn.commit()
        cur.execute("""
            SELECT LOWER(TRIM(username)) AS uname,
                   COALESCE(SUM(total_tokens), 0) AS total_tok,
                   COALESCE(SUM(estimated_cost_usd), 0) AS total_cost,
                   COUNT(*) AS req_count
            FROM api_usage_logs
            WHERE username IS NOT NULL AND TRIM(username) <> ''
              AND created_at >= date_trunc('month', CURRENT_TIMESTAMP)
            GROUP BY LOWER(TRIM(username));
        """)
        for row in cur.fetchall():
            if row[0]:
                usage_map[row[0]] = {
                    'tokens': int(row[1] or 0),
                    'cost_usd': float(row[2] or 0.0),
                    'requests': int(row[3] or 0)
                }
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not aggregate monthly token usage by user: {e}")
    return usage_map


def _attach_request_username():
    """Populate flask.g.current_username so AI usage telemetry automatically attributes tokens per user."""
    try:
        from flask import g
        g.current_username = None
        if request.headers.get('Authorization') or request.headers.get('X-API-Key'):
            g.current_username = get_request_user()
    except Exception:
        pass


def revoke_user_sessions(user_id: Any):
    now_ts = time.time()
    with _AUTH_LOCK:
        _USER_REVOKED_BEFORE[str(user_id)] = now_ts
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("UPDATE users SET token_revoked_after = %s WHERE user_id = %s;", (now_ts, int(user_id)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not persist session revocation for user {user_id}: {e}")


def decode_api_token(raw_token: str):
    """Verify a personal API key (sqa_...) against user_api_tokens table."""
    if not raw_token or not raw_token.startswith('sqa_'):
        return None
    import hashlib
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT t.token_id, u.user_id, u.username, u.role, u.is_active, u.allowed_menus, u.allowed_projects, t.scopes
            FROM user_api_tokens t
            JOIN users u ON u.user_id = t.user_id
            WHERE t.token_hash = %s AND t.revoked_at IS NULL
            LIMIT 1;
        """, (token_hash,))
        row = cur.fetchone()
        if not row or not row[4]:
            cur.close()
            conn.close()
            return None
        token_id, uid, uname, urole, _, u_menus, u_projects, scopes = row
        cur.execute("UPDATE user_api_tokens SET last_used_at = NOW() WHERE token_id = %s;", (token_id,))
        conn.commit()
        cur.close()
        conn.close()
        role_val = urole or 'user'
        default_menus = DEFAULT_ADMIN_MENUS if role_val == 'admin' else DEFAULT_USER_MENUS
        return {
            'user_id': str(uid),
            'user': uname,
            'role': role_val,
            'allowed_menus': parse_permissions_json(u_menus, default_menus),
            'allowed_projects': parse_permissions_json(u_projects, ['all']),
            'auth_type': 'api_token',
            'token_id': token_id,
            'scopes': scopes or 'extension,mcp'
        }
    except Exception as e:
        logger.warning(f"API token verification failed: {e}")
        return None


def resolve_request_auth():
    """Resolve authenticated user payload from Bearer JWT, Bearer sqa_ token, or X-API-Key header."""
    try:
        api_key = (request.headers.get('X-API-Key') or '').strip()
        if api_key.startswith('sqa_'):
            return decode_api_token(api_key)
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1].strip()
            if token.startswith('sqa_'):
                return decode_api_token(token)
            return decode_jwt(token)
    except Exception:
        pass
    return None


def _validate_password_policy(password: str):
    if not isinstance(password, str) or len(password) < 8:
        return 'รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร (Password must be at least 8 characters)'
    if len(password.encode('utf-8')) > 72:
        return 'รหัสผ่านต้องมีความยาวไม่เกิน 72 ตัวอักษร (Password exceeds maximum length of 72 bytes)'
    return None


def encode_jwt(payload):
    now = time.time()
    claims = dict(payload)
    claims.setdefault('iat', now)
    claims.setdefault('jti', uuid.uuid4().hex)
    return pyjwt.encode(claims, JWT_SECRET, algorithm='HS256')


def decode_jwt(token):
    try:
        if not _USER_SECURITY_SCHEMA_READY:
            ensure_user_security_schema()
        payload = pyjwt.decode(
            token,
            JWT_SECRET,
            algorithms=['HS256'],
            leeway=2,
            options={'require': ['exp']}
        )
        jti = payload.get('jti')
        uid = str(payload.get('user_id', ''))
        iat = float(payload.get('iat', 0) or 0)
        with _AUTH_LOCK:
            if jti and jti in _REVOKED_JTIS:
                return None
            revoked_before = _USER_REVOKED_BEFORE.get(uid)
            if revoked_before and iat <= revoked_before:
                return None
        return payload
    except Exception:
        return None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        payload = resolve_request_auth()
        if not payload:
            auth_header = request.headers.get('Authorization')
            api_key = request.headers.get('X-API-Key')
            if not auth_header and not api_key:
                return jsonify({'error': 'Unauthorized, please login'}), 401
            return jsonify({'error': 'Invalid or expired token'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        payload = resolve_request_auth()
        if not payload:
            auth_header = request.headers.get('Authorization')
            api_key = request.headers.get('X-API-Key')
            if not auth_header and not api_key:
                return jsonify({'error': 'Unauthorized, please login'}), 401
            return jsonify({'error': 'Invalid or expired token'}), 401
        if payload.get('role') != 'admin':
            return jsonify({'error': 'Forbidden: Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated


def get_request_user():
    """Extract authenticated username strictly from verified Bearer JWT or API Token."""
    payload = resolve_request_auth()
    if payload and payload.get('user'):
        return payload.get('user')
    return None


def get_request_user_payload():
    """Extract full decoded JWT or API Token payload from request headers."""
    return resolve_request_auth()


def parse_permissions_json(val, default_val):
    if val is None or val == "":
        return default_val
    if isinstance(val, list):
        return val
    try:
        parsed = json.loads(val)
        if isinstance(parsed, list):
            return parsed
        return default_val
    except Exception:
        return default_val

