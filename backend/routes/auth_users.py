"""Authentication, static serving, health check, user management, API tokens, avatars, and permission templates."""
import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import requests
from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory
from flask_cors import cross_origin
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
bp = Blueprint('auth_users', __name__)

from core.config import (
    AVATARS_FOLDER,
    BASE_DIR,
    FRONTEND_FOLDER,
    UPLOAD_FOLDER,
)
from core.auth import (
    DEFAULT_ADMIN_MENUS,
    DEFAULT_USER_MENUS,
    _check_login_rate_limit,
    _clear_login_failures,
    _fetch_monthly_token_usage_map,
    _get_client_ip,
    _record_login_failure,
    _validate_password_policy,
    admin_required,
    encode_jwt,
    ensure_user_security_schema,
    get_request_user,
    get_request_user_payload,
    parse_permissions_json,
    record_user_audit,
    revoke_token_jti,
    revoke_user_sessions,
    token_required,
)
from ocr_engine import VERSION

@bp.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    identifier = str(data.get('username') or data.get('email') or '').strip()
    password = data.get('password')
    
    if not identifier or not isinstance(password, str) or not password:
        return jsonify({'error': 'Email/Username and password required'}), 400
    if len(identifier) > 254 or len(password.encode('utf-8')) > 72:
        return jsonify({'error': 'Invalid credentials'}), 400

    client_ip = _get_client_ip()
    acct_key = identifier.lower()
    retry_after = _check_login_rate_limit(client_ip, acct_key)
    if retry_after > 0:
        logger.warning(f"Rate-limited login attempt from {client_ip} for identifier '{acct_key}' (retry in {retry_after}s)")
        resp = jsonify({
            'error': f'พยายามเข้าสู่ระบบผิดหลายครั้งเกินกำหนด กรุณารอ {retry_after} วินาทีแล้วลองใหม่อีกครั้ง',
            'retry_after': retry_after
        })
        resp.status_code = 429
        resp.headers['Retry-After'] = str(retry_after)
        return resp
        
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cursor = conn.cursor()
        
        # ใช้ PostgreSQL crypt() ตรวจสอบ bcrypt password (รองรับทั้ง Email และ Username)
        cursor.execute(
            "SELECT user_id, username, email, display_name, role, is_active, avatar_path, allowed_menus, allowed_projects, COALESCE(must_change_password, FALSE) "
            "FROM users "
            "WHERE (LOWER(TRIM(username)) = LOWER(%s) OR LOWER(TRIM(COALESCE(email, ''))) = LOWER(%s)) "
            "AND password_hash = crypt(%s, password_hash) "
            "ORDER BY (username = %s) DESC LIMIT 1;",
            (identifier, identifier, password, identifier)
        )
        user = cursor.fetchone()
        
        if user and user[5]:  # is_active = True
            _clear_login_failures(acct_key)
            user_id = str(user[0])
            user_role = user[4] or 'user'
            default_menus = DEFAULT_ADMIN_MENUS if user_role == 'admin' else DEFAULT_USER_MENUS
            allowed_menus = parse_permissions_json(user[7], default_menus)
            allowed_projects = parse_permissions_json(user[8], ["all"])
            must_change_password = bool(user[9])
            
            # อัปเดต login_count และ last_login_at
            cursor.execute(
                "UPDATE users SET login_count = login_count + 1, last_login_at = NOW() WHERE user_id = %s;",
                (user[0],)
            )
            conn.commit()
            
            # Token expires in 12 hours
            now_ts = time.time()
            payload = {
                'user_id': user_id,
                'user': user[1],
                'role': user_role,
                'allowed_menus': allowed_menus,
                'allowed_projects': allowed_projects,
                'must_change_password': must_change_password,
                'iat': now_ts,
                'exp': int(now_ts) + (12 * 3600)
            }
            token = encode_jwt(payload)
            
            cursor.close()
            conn.close()
            record_user_audit(user[0], user[1], 'LOGIN_SUCCESS', 'เข้าสู่ระบบสำเร็จ', actor_username=user[1])
            return jsonify({
                'success': True,
                'token': token,
                'user': user[1],
                'email': user[2],
                'display_name': user[3],
                'role': user_role,
                'avatar_path': user[6],
                'allowed_menus': allowed_menus,
                'allowed_projects': allowed_projects,
                'must_change_password': must_change_password
            })
            
        cursor.close()
        conn.close()
        _record_login_failure(client_ip, acct_key)
        record_user_audit(None, identifier, 'LOGIN_FAILED', f'เข้าสู่ระบบไม่สำเร็จ ({identifier})', actor_username=identifier)
        logger.warning(f"Failed login attempt from {client_ip} for identifier '{acct_key}'")
        return jsonify({'error': 'อีเมล/ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'}), 401
        
    except Exception as e:
        logger.error(f"Login DB error: {e}", exc_info=True)
        return jsonify({'error': 'ไม่สามารถเชื่อมต่อระบบยืนยันตัวตนได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง'}), 500


@bp.route('/api/logout', methods=['POST', 'OPTIONS'])
def api_logout():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    payload = get_request_user_payload()
    if payload and payload.get('jti'):
        revoke_token_jti(payload['jti'], float(payload.get('exp', time.time() + 43200)))
    return jsonify({'success': True})


@bp.route('/')
def index():
    return send_from_directory(str(FRONTEND_FOLDER), 'index.html')


@bp.route('/uploads/<path:filename>')
def serve_uploads(filename):
    return send_from_directory(str(UPLOAD_FOLDER), filename)


@bp.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(str(FRONTEND_FOLDER), filename)


@bp.route('/api/users', methods=['GET'])
@admin_required
def get_users():
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT u.user_id, u.username, u.email, u.display_name, u.role, u.is_active, 
                   u.login_count, u.last_login_at, u.created_at, u.avatar_path,
                   u.allowed_menus, u.allowed_projects, u.phone, u.department, u.github_url, u.linkedin_url, u.line_id,
                   COALESCE(u.must_change_password, FALSE),
                   (SELECT COUNT(*) FROM user_api_tokens t WHERE t.user_id = u.user_id AND t.revoked_at IS NULL) AS active_token_count,
                   COALESCE(u.monthly_token_quota, 0),
                   COALESCE(u.trello_username, ''),
                   COALESCE(u.github_username, '')
            FROM users u
            ORDER BY u.user_id ASC;
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        usage_map = _fetch_monthly_token_usage_map()
        users_data = []
        for row in rows:
            u_role = row[4] or 'user'
            default_menus = DEFAULT_ADMIN_MENUS if u_role == 'admin' else DEFAULT_USER_MENUS
            u_usage = usage_map.get(str(row[1] or '').strip().lower(), {'tokens': 0, 'cost_usd': 0.0, 'requests': 0})
            users_data.append({
                'user_id': row[0],
                'username': row[1],
                'email': row[2],
                'display_name': row[3],
                'role': u_role,
                'is_active': row[5],
                'login_count': row[6],
                'last_login_at': row[7].isoformat() if row[7] else None,
                'created_at': row[8].isoformat() if row[8] else None,
                'avatar_path': row[9],
                'allowed_menus': parse_permissions_json(row[10], default_menus),
                'allowed_projects': parse_permissions_json(row[11], ["all"]),
                'phone': row[12] or '',
                'department': row[13] or '',
                'github_url': row[14] or '',
                'linkedin_url': row[15] or '',
                'line_id': row[16] or '',
                'must_change_password': bool(row[17]),
                'active_token_count': int(row[18] or 0),
                'monthly_token_quota': int(row[19] or 0),
                'monthly_tokens_used': u_usage['tokens'],
                'monthly_cost_usd': round(u_usage['cost_usd'], 4),
                'monthly_requests': u_usage['requests'],
                'trello_username': row[20] or '',
                'github_username': row[21] or ''
            })
            
        return jsonify({'success': True, 'users': users_data})
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({'error': 'Failed to load users'}), 500


@bp.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    username = str(data.get('username') or '').strip()
    email = str(data.get('email') or '').strip()
    password = data.get('password')
    display_name = str(data.get('display_name') or '').strip()
    role = data.get('role', 'user')
    if role not in ('admin', 'user'):
        return jsonify({'error': 'Invalid role specified'}), 400
    phone = data.get('phone', '')
    department = data.get('department', '')
    github_url = data.get('github_url', '')
    linkedin_url = data.get('linkedin_url', '')
    line_id = data.get('line_id', '')
    trello_username = str(data.get('trello_username') or '').strip().lstrip('@')
    github_username = str(data.get('github_username') or '').strip().lstrip('@')
    must_change_password = bool(data.get('must_change_password', True))
    try:
        monthly_token_quota = max(0, int(data.get('monthly_token_quota') or 0))
    except Exception:
        monthly_token_quota = 0
    
    if not username or not email or not password:
        return jsonify({'error': 'Username, email, and password required'}), 400
    pw_err = _validate_password_policy(password)
    if pw_err:
        return jsonify({'error': pw_err}), 400
        
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cursor = conn.cursor()
        
        # Check if username or email already exists (case-insensitive)
        cursor.execute(
            "SELECT user_id FROM users WHERE LOWER(TRIM(username)) = LOWER(%s) OR LOWER(TRIM(COALESCE(email, ''))) = LOWER(%s)",
            (username, email)
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Username or Email already exists'}), 400
            
        default_menus = DEFAULT_ADMIN_MENUS if role == 'admin' else DEFAULT_USER_MENUS
        allowed_menus = data.get('allowed_menus')
        if allowed_menus is None:
            allowed_menus = default_menus
        allowed_menus_str = json.dumps(allowed_menus, ensure_ascii=False)

        allowed_projects = data.get('allowed_projects')
        if allowed_projects is None:
            allowed_projects = ["all"]
        allowed_projects_str = json.dumps(allowed_projects, ensure_ascii=False)
            
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, display_name, role, is_active, allowed_menus, allowed_projects, phone, department, github_url, linkedin_url, line_id, must_change_password, monthly_token_quota, trello_username, github_username)
            VALUES (%s, %s, crypt(%s, gen_salt('bf')), %s, %s, true, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id, username, email, display_name, role, is_active, created_at, avatar_path, allowed_menus, allowed_projects, phone, department, github_url, linkedin_url, line_id, must_change_password, monthly_token_quota, trello_username, github_username;
        """, (username, email, password, display_name, role, allowed_menus_str, allowed_projects_str, phone, department, github_url, linkedin_url, line_id, must_change_password, monthly_token_quota, trello_username, github_username))
        
        new_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        record_user_audit(new_user[0], new_user[1], 'USER_CREATED', f'สร้างบัญชีใหม่ (Role: {role.upper()}, เมนู: {len(allowed_menus)} เมนู)')
        
        return jsonify({
            'success': True,
            'user': {
                'user_id': new_user[0],
                'username': new_user[1],
                'email': new_user[2],
                'display_name': new_user[3],
                'role': new_user[4],
                'is_active': new_user[5],
                'created_at': new_user[6].isoformat() if new_user[6] else None,
                'avatar_path': new_user[7],
                'allowed_menus': parse_permissions_json(new_user[8], default_menus),
                'allowed_projects': parse_permissions_json(new_user[9], ["all"]),
                'phone': new_user[10] or '',
                'department': new_user[11] or '',
                'github_url': new_user[12] or '',
                'linkedin_url': new_user[13] or '',
                'line_id': new_user[14] or '',
                'must_change_password': bool(new_user[15]),
                'monthly_token_quota': int(new_user[16] or 0),
                'trello_username': new_user[17] or '',
                'github_username': new_user[18] or ''
            }
        })
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': 'Failed to create user'}), 500


@bp.route('/api/users/<int:user_id>', methods=['GET'])
@token_required
def get_user_detail(user_id):
    req_payload = get_request_user_payload() or {}
    is_admin = req_payload.get('role') == 'admin'
    is_self = str(req_payload.get('user_id', '')) == str(user_id)
    if not (is_admin or is_self):
        return jsonify({'error': 'Forbidden: You can only view your own profile'}), 403
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT user_id, username, email, display_name, role, is_active, 
                   avatar_path, phone, github_url, linkedin_url, line_id, department,
                   allowed_menus, allowed_projects
            FROM users WHERE user_id = %s;
        """, (user_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return jsonify({'error': 'User not found'}), 404
            
        u_role = row[4] or 'user'
        default_menus = DEFAULT_ADMIN_MENUS if u_role == 'admin' else DEFAULT_USER_MENUS

        return jsonify({
            'success': True,
            'user': {
                'user_id': row[0],
                'username': row[1],
                'email': row[2],
                'display_name': row[3],
                'role': u_role,
                'is_active': row[5],
                'avatar_path': row[6],
                'phone': row[7] or '',
                'github_url': row[8] or '',
                'linkedin_url': row[9] or '',
                'line_id': row[10] or '',
                'department': row[11] or '',
                'allowed_menus': parse_permissions_json(row[12], default_menus),
                'allowed_projects': parse_permissions_json(row[13], ["all"])
            }
        })
    except Exception as e:
        logger.error(f"Error getting user detail: {e}")
        return jsonify({'error': 'Failed to load user profile'}), 500


@bp.route('/api/users/<int:user_id>', methods=['PUT'])
@token_required
def update_user(user_id):
    req_payload = get_request_user_payload() or {}
    is_admin = req_payload.get('role') == 'admin'
    is_self = str(req_payload.get('user_id', '')) == str(user_id)
    if not (is_admin or is_self):
        return jsonify({'error': 'Forbidden: You can only update your own profile'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Block privilege escalation attempts from non-admin users
    privileged_fields = ('role', 'is_active', 'allowed_menus', 'allowed_projects', 'must_change_password', 'monthly_token_quota')
    if not is_admin and any(f in data for f in privileged_fields):
        return jsonify({'error': 'Forbidden: Admin privileges required to modify role or permissions'}), 403

    new_password = data.get('password') or ''
    if new_password:
        pw_err = _validate_password_policy(new_password)
        if pw_err:
            return jsonify({'error': pw_err}), 400
        
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cursor = conn.cursor()

        # Self-service password change requires verifying current_password
        if new_password and is_self and not is_admin:
            current_password = data.get('current_password') or ''
            if not current_password:
                cursor.close()
                conn.close()
                return jsonify({'error': 'กรุณาระบุรหัสผ่านปัจจุบันเพื่อยืนยันการเปลี่ยนรหัสผ่าน'}), 400
            cursor.execute(
                "SELECT user_id FROM users WHERE user_id = %s AND password_hash = crypt(%s, password_hash);",
                (user_id, current_password)
            )
            if not cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'error': 'รหัสผ่านปัจจุบันไม่ถูกต้อง'}), 400
        
        # Prevent self-demotion, self-deactivation, and removing the last active admin
        if is_admin and (('role' in data) or ('is_active' in data)):
            cursor.execute("SELECT role, is_active FROM users WHERE user_id = %s;", (user_id,))
            target_row = cursor.fetchone()
            if not target_row:
                cursor.close()
                conn.close()
                return jsonify({'error': 'User not found'}), 404
            curr_role, curr_active = target_row[0], bool(target_row[1])
            next_role = data['role'] if 'role' in data else curr_role
            next_active = bool(data['is_active']) if 'is_active' in data else curr_active

            if is_self and next_role != curr_role:
                cursor.close()
                conn.close()
                return jsonify({'error': 'ไม่สามารถเปลี่ยนระดับสิทธิ์ของบัญชีตัวเองได้'}), 403
            if is_self and not next_active:
                cursor.close()
                conn.close()
                return jsonify({'error': 'ไม่สามารถปิดการใช้งานบัญชีตัวเองได้'}), 403

            if curr_role == 'admin' and curr_active and (next_role != 'admin' or not next_active):
                cursor.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = true AND user_id != %s;",
                    (user_id,)
                )
                other_admins = cursor.fetchone()[0]
                if other_admins == 0:
                    cursor.close()
                    conn.close()
                    return jsonify({'error': 'ไม่สามารถลดสิทธิ์หรือปิดการใช้งานผู้ดูแลระบบ (Admin) คนสุดท้ายของระบบได้'}), 400

        update_fields = []
        params = []
        should_revoke = False
        
        if 'display_name' in data:
            update_fields.append("display_name = %s")
            params.append(data['display_name'])
        if is_admin and 'role' in data:
            if data['role'] not in ('admin', 'user'):
                cursor.close()
                conn.close()
                return jsonify({'error': 'Invalid role specified'}), 400
            update_fields.append("role = %s")
            params.append(data['role'])
            should_revoke = True
        if is_admin and 'is_active' in data:
            update_fields.append("is_active = %s")
            params.append(bool(data['is_active']))
            if not data['is_active']:
                should_revoke = True
        if new_password:
            update_fields.append("password_hash = crypt(%s, gen_salt('bf'))")
            params.append(new_password)
            should_revoke = True
        if 'phone' in data:
            update_fields.append("phone = %s")
            params.append(data['phone'])
        if 'github_url' in data:
            update_fields.append("github_url = %s")
            params.append(data['github_url'])
        if 'linkedin_url' in data:
            update_fields.append("linkedin_url = %s")
            params.append(data['linkedin_url'])
        if 'line_id' in data:
            update_fields.append("line_id = %s")
            params.append(data['line_id'])
        if 'department' in data:
            update_fields.append("department = %s")
            params.append(data['department'])
        if 'trello_username' in data:
            update_fields.append("trello_username = %s")
            params.append(str(data['trello_username'] or '').strip().lstrip('@'))
        if 'github_username' in data:
            update_fields.append("github_username = %s")
            params.append(str(data['github_username'] or '').strip().lstrip('@'))
        if is_admin and 'allowed_menus' in data:
            update_fields.append("allowed_menus = %s")
            params.append(json.dumps(data['allowed_menus'], ensure_ascii=False) if isinstance(data['allowed_menus'], list) else data['allowed_menus'])
            should_revoke = True
        if is_admin and 'allowed_projects' in data:
            update_fields.append("allowed_projects = %s")
            params.append(json.dumps(data['allowed_projects'], ensure_ascii=False) if isinstance(data['allowed_projects'], list) else data['allowed_projects'])
            should_revoke = True
        if 'avatar_path' in data:
            update_fields.append("avatar_path = %s")
            params.append(data['avatar_path'])
        if is_admin and 'must_change_password' in data:
            update_fields.append("must_change_password = %s")
            params.append(bool(data['must_change_password']))
        if is_admin and 'monthly_token_quota' in data:
            try:
                quota_val = max(0, int(data['monthly_token_quota'] or 0))
            except Exception:
                quota_val = 0
            update_fields.append("monthly_token_quota = %s")
            params.append(quota_val)
            
        if not update_fields:
            cursor.close()
            conn.close()
            return jsonify({'error': 'No fields to update'}), 400
            
        params.append(user_id)
        
        query = f"""
            UPDATE users SET {', '.join(update_fields)} 
            WHERE user_id = %s 
            RETURNING user_id, username, email, display_name, role, is_active, avatar_path, phone, github_url, linkedin_url, line_id, department, allowed_menus, allowed_projects, COALESCE(must_change_password, FALSE), COALESCE(monthly_token_quota, 0), COALESCE(trello_username, ''), COALESCE(github_username, '');
        """
        cursor.execute(query, tuple(params))
        
        updated_user = cursor.fetchone()
        if not updated_user:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
            
        conn.commit()
        cursor.close()
        conn.close()

        if should_revoke and not is_self:
            revoke_user_sessions(user_id)

        audit_parts = []
        if is_admin and 'role' in data:
            audit_parts.append(f"Role → {data['role'].upper()}")
        if is_admin and 'is_active' in data:
            audit_parts.append(f"สถานะ → {'เปิดใช้งาน' if data['is_active'] else 'ปิดใช้งาน'}")
        if new_password:
            audit_parts.append("รีเซ็ตรหัสผ่าน")
        if is_admin and 'allowed_menus' in data:
            audit_parts.append(f"สิทธิ์เมนู ({len(data['allowed_menus']) if isinstance(data['allowed_menus'], list) else '?'} เมนู)")
        if is_admin and 'allowed_projects' in data:
            audit_parts.append("สิทธิ์โครงการ")
        if is_admin and 'monthly_token_quota' in data:
            q_num = int(data['monthly_token_quota'] or 0)
            audit_parts.append(f"Token Quota → {'ไม่จำกัด' if q_num == 0 else f'{q_num:,}'}")
        audit_action = 'ROLE_CHANGED' if ('role' in data and is_admin) else ('STATUS_CHANGED' if ('is_active' in data and is_admin) else ('PERMISSIONS_UPDATED' if (('allowed_menus' in data or 'allowed_projects' in data) and is_admin) else 'USER_UPDATED'))
        record_user_audit(updated_user[0], updated_user[1], audit_action, ', '.join(audit_parts) or 'อัปเดตข้อมูลโปรไฟล์')
        
        u_role = updated_user[4] or 'user'
        default_menus = DEFAULT_ADMIN_MENUS if u_role == 'admin' else DEFAULT_USER_MENUS
        
        return jsonify({
            'success': True,
            'user': {
                'user_id': updated_user[0],
                'username': updated_user[1],
                'email': updated_user[2],
                'display_name': updated_user[3],
                'role': u_role,
                'is_active': updated_user[5],
                'avatar_path': updated_user[6],
                'phone': updated_user[7],
                'github_url': updated_user[8],
                'linkedin_url': updated_user[9],
                'line_id': updated_user[10],
                'department': updated_user[11],
                'allowed_menus': parse_permissions_json(updated_user[12], default_menus),
                'allowed_projects': parse_permissions_json(updated_user[13], ["all"]),
                'must_change_password': bool(updated_user[14]),
                'monthly_token_quota': int(updated_user[15] or 0),
                'trello_username': updated_user[16] or '',
                'github_username': updated_user[17] or ''
            }
        })
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return jsonify({'error': 'Failed to update user profile'}), 500


@bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    payload = get_request_user_payload() or {}
    
    if str(payload.get('user_id')) == str(user_id):
        return jsonify({'error': 'Cannot delete your own account'}), 403
        
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT role, is_active FROM users WHERE user_id = %s;", (user_id,))
        target_row = cursor.fetchone()
        if not target_row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        if target_row[0] == 'admin' and bool(target_row[1]):
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = true AND user_id != %s;",
                (user_id,)
            )
            if cursor.fetchone()[0] == 0:
                cursor.close()
                conn.close()
                return jsonify({'error': 'ไม่สามารถลบผู้ดูแลระบบ (Admin) คนสุดท้ายของระบบได้'}), 400

        cursor.execute("DELETE FROM users WHERE user_id = %s RETURNING user_id;", (user_id,))
        deleted = cursor.fetchone()
        
        if not deleted:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404
            
        conn.commit()
        cursor.close()
        conn.close()
        revoke_user_sessions(user_id)
        
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500


@bp.route('/api/users/<int:user_id>/revoke-sessions', methods=['POST'])
@admin_required
def force_logout_user(user_id):
    """Force-revoke all active JWT sessions for a specific user without disabling the account."""
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("SELECT username, display_name FROM users WHERE user_id = %s;", (user_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'User not found'}), 404
        revoke_user_sessions(user_id)
        record_user_audit(user_id, row[0], 'SESSION_REVOKED', 'ผู้ดูแลระบบบังคับออกจากระบบทุกอุปกรณ์')
        return jsonify({
            'success': True,
            'message': f'บังคับออกจากระบบทุกอุปกรณ์ของ {row[0]} เรียบร้อยแล้ว',
            'revoked_at': time.time()
        })
    except Exception as e:
        logger.error(f"Error revoking sessions for user {user_id}: {e}")
        return jsonify({'error': 'Failed to revoke user sessions'}), 500


@bp.route('/api/auth/change-password', methods=['POST'])
@token_required
def change_own_password():
    """Self-service password change (also clears must_change_password and issues a fresh JWT)."""
    req_payload = get_request_user_payload() or {}
    user_id = req_payload.get('user_id')
    if not user_id:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''
    if not current_password or not new_password:
        return jsonify({'error': 'กรุณากรอกรหัสผ่านปัจจุบันและรหัสผ่านใหม่ให้ครบถ้วน'}), 400
    if current_password == new_password:
        return jsonify({'error': 'รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม'}), 400
    pw_err = _validate_password_policy(new_password)
    if pw_err:
        return jsonify({'error': pw_err}), 400

    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, username, role, allowed_menus, allowed_projects "
            "FROM users WHERE user_id = %s AND is_active = true AND password_hash = crypt(%s, password_hash);",
            (int(user_id), current_password)
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            return jsonify({'error': 'รหัสผ่านปัจจุบันไม่ถูกต้อง'}), 400

        cur.execute(
            "UPDATE users SET password_hash = crypt(%s, gen_salt('bf')), must_change_password = FALSE WHERE user_id = %s;",
            (new_password, int(user_id))
        )
        conn.commit()
        cur.close()
        conn.close()

        # Revoke older sessions, then issue a fresh JWT dated strictly after revocation
        revoke_user_sessions(user_id)
        now_ts = time.time() + 0.01
        u_role = row[2] or 'user'
        default_menus = DEFAULT_ADMIN_MENUS if u_role == 'admin' else DEFAULT_USER_MENUS
        fresh_token = encode_jwt({
            'user_id': str(row[0]),
            'user': row[1],
            'role': u_role,
            'allowed_menus': parse_permissions_json(row[3], default_menus),
            'allowed_projects': parse_permissions_json(row[4], ['all']),
            'must_change_password': False,
            'iat': now_ts,
            'exp': int(now_ts) + (12 * 3600)
        })
        return jsonify({
            'success': True,
            'token': fresh_token,
            'must_change_password': False,
            'message': 'เปลี่ยนรหัสผ่านเรียบร้อยแล้ว'
        })
    except Exception as e:
        logger.error(f"Error changing password for user {user_id}: {e}")
        return jsonify({'error': 'ไม่สามารถเปลี่ยนรหัสผ่านได้ในขณะนี้'}), 500


@bp.route('/api/users/<int:user_id>/tokens', methods=['GET'])
@token_required
def list_user_api_tokens(user_id):
    req_payload = get_request_user_payload() or {}
    is_admin = req_payload.get('role') == 'admin'
    is_self = str(req_payload.get('user_id', '')) == str(user_id)
    if not (is_admin or is_self):
        return jsonify({'error': 'Forbidden'}), 403
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT token_id, name, token_prefix, scopes, created_by, last_used_at, revoked_at, created_at
            FROM user_api_tokens
            WHERE user_id = %s
            ORDER BY (revoked_at IS NOT NULL) ASC, created_at DESC;
        """, (user_id,))
        tokens = []
        for r in cur.fetchall():
            tokens.append({
                'token_id': r[0],
                'name': r[1],
                'token_prefix': r[2],
                'scopes': r[3] or 'extension,mcp',
                'created_by': r[4] or '',
                'last_used_at': r[5].isoformat() if r[5] else None,
                'revoked_at': r[6].isoformat() if r[6] else None,
                'created_at': r[7].isoformat() if r[7] else None,
                'is_active': r[6] is None
            })
        cur.close()
        conn.close()
        return jsonify({'success': True, 'tokens': tokens})
    except Exception as e:
        logger.error(f"Error listing API tokens for user {user_id}: {e}")
        return jsonify({'error': 'Failed to load API tokens'}), 500


@bp.route('/api/users/<int:user_id>/tokens', methods=['POST'])
@token_required
def create_user_api_token(user_id):
    req_payload = get_request_user_payload() or {}
    is_admin = req_payload.get('role') == 'admin'
    is_self = str(req_payload.get('user_id', '')) == str(user_id)
    if not (is_admin or is_self):
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'กรุณาระบุชื่อ API Token (เช่น Chrome Extension / MCP)'}), 400
    scopes = str(data.get('scopes') or 'extension,mcp').strip() or 'extension,mcp'

    import hashlib, secrets
    raw_token = f"sqa_{secrets.token_urlsafe(32)}"
    token_prefix = raw_token[:12]
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    created_by = req_payload.get('user') or 'admin'

    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE user_id = %s;", (user_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        cur.execute("""
            INSERT INTO user_api_tokens (user_id, name, token_prefix, token_hash, scopes, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING token_id, created_at;
        """, (user_id, name[:100], token_prefix, token_hash, scopes[:100], created_by))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            'success': True,
            'token': raw_token,
            'token_info': {
                'token_id': row[0],
                'name': name[:100],
                'token_prefix': token_prefix,
                'scopes': scopes[:100],
                'created_by': created_by,
                'last_used_at': None,
                'revoked_at': None,
                'created_at': row[1].isoformat() if row[1] else None,
                'is_active': True
            }
        })
    except Exception as e:
        logger.error(f"Error creating API token for user {user_id}: {e}")
        return jsonify({'error': 'Failed to create API token'}), 500


@bp.route('/api/users/<int:user_id>/tokens/<int:token_id>', methods=['DELETE'])
@token_required
def revoke_user_api_token(user_id, token_id):
    req_payload = get_request_user_payload() or {}
    is_admin = req_payload.get('role') == 'admin'
    is_self = str(req_payload.get('user_id', '')) == str(user_id)
    if not (is_admin or is_self):
        return jsonify({'error': 'Forbidden'}), 403
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_api_tokens SET revoked_at = NOW() WHERE token_id = %s AND user_id = %s AND revoked_at IS NULL RETURNING token_id;",
            (token_id, user_id)
        )
        updated = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if not updated:
            return jsonify({'error': 'Token not found or already revoked'}), 404
        record_user_audit(user_id, '', 'API_TOKEN_REVOKED', f'ยกเลิก Personal API Token #{token_id}')
        return jsonify({'success': True, 'message': 'ยกเลิก API Token เรียบร้อยแล้ว'})
    except Exception as e:
        logger.error(f"Error revoking API token {token_id} for user {user_id}: {e}")
        return jsonify({'error': 'Failed to revoke API token'}), 500


@bp.route('/api/users/<int:user_id>/activity', methods=['GET'])
@admin_required
def get_user_activity_and_usage(user_id):
    """Returns recent audit/login timeline and current-month AI token usage & quota for a member."""
    try:
        from db_ingestion import get_auth_db_connection, get_ocr_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, username, display_name, email, role, is_active,
                   COALESCE(monthly_token_quota, 0), last_login_at, login_count
            FROM users WHERE user_id = %s;
        """, (user_id,))
        u_row = cur.fetchone()
        if not u_row:
            cur.close()
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        target_username = u_row[1] or ''
        monthly_quota = int(u_row[6] or 0)

        cur.execute("""
            SELECT audit_id, actor_username, action, details, ip_address, user_agent, created_at
            FROM user_audit_logs
            WHERE target_user_id = %s OR LOWER(TRIM(target_username)) = LOWER(%s)
            ORDER BY created_at DESC
            LIMIT 50;
        """, (user_id, target_username))
        audit_logs = []
        for r in cur.fetchall():
            audit_logs.append({
                'audit_id': r[0],
                'actor_username': r[1] or 'system',
                'action': r[2] or 'EVENT',
                'details': r[3] or '',
                'ip_address': r[4] or '',
                'user_agent': r[5] or '',
                'created_at': r[6].isoformat() if r[6] else None
            })
        cur.close()
        conn.close()

        # Monthly AI Token Usage & top endpoints from api_usage_logs
        monthly_tokens = 0
        monthly_cost = 0.0
        monthly_requests = 0
        by_endpoint = []
        try:
            ocr_conn = get_ocr_db_connection()
            ocr_cur = ocr_conn.cursor()
            ocr_cur.execute("ALTER TABLE api_usage_logs ADD COLUMN IF NOT EXISTS username VARCHAR(120);")
            ocr_conn.commit()
            ocr_cur.execute("""
                SELECT COALESCE(SUM(total_tokens), 0),
                       COALESCE(SUM(estimated_cost_usd), 0),
                       COUNT(*)
                FROM api_usage_logs
                WHERE LOWER(TRIM(COALESCE(username, ''))) = LOWER(%s)
                  AND created_at >= date_trunc('month', CURRENT_TIMESTAMP);
            """, (target_username,))
            s_row = ocr_cur.fetchone()
            if s_row:
                monthly_tokens = int(s_row[0] or 0)
                monthly_cost = round(float(s_row[1] or 0.0), 4)
                monthly_requests = int(s_row[2] or 0)

            ocr_cur.execute("""
                SELECT COALESCE(endpoint_name, 'AI_Agent') AS ep,
                       COALESCE(SUM(total_tokens), 0) AS tok,
                       COALESCE(SUM(estimated_cost_usd), 0) AS cost,
                       COUNT(*) AS cnt
                FROM api_usage_logs
                WHERE LOWER(TRIM(COALESCE(username, ''))) = LOWER(%s)
                  AND created_at >= date_trunc('month', CURRENT_TIMESTAMP)
                GROUP BY ep
                ORDER BY tok DESC
                LIMIT 6;
            """, (target_username,))
            for ep_row in ocr_cur.fetchall():
                by_endpoint.append({
                    'endpoint': ep_row[0],
                    'tokens': int(ep_row[1] or 0),
                    'cost_usd': round(float(ep_row[2] or 0.0), 4),
                    'requests': int(ep_row[3] or 0)
                })
            ocr_cur.close()
            ocr_conn.close()
        except Exception as ue:
            logger.warning(f"Could not load per-user AI usage for {target_username}: {ue}")

        return jsonify({
            'success': True,
            'audit_logs': audit_logs,
            'usage_summary': {
                'monthly_tokens_used': monthly_tokens,
                'monthly_cost_usd': monthly_cost,
                'monthly_requests': monthly_requests,
                'monthly_token_quota': monthly_quota,
                'by_endpoint': by_endpoint
            }
        })
    except Exception as e:
        logger.error(f"Error loading activity for user {user_id}: {e}")
        return jsonify({'error': 'Failed to load member activity'}), 500


@bp.route('/api/permission-templates', methods=['GET'])
@admin_required
def list_permission_templates():
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT template_id, name, description, target_role, allowed_menus, allowed_projects, created_by, created_at
            FROM permission_templates
            ORDER BY created_at DESC;
        """)
        templates = []
        for r in cur.fetchall():
            templates.append({
                'template_id': r[0],
                'name': r[1],
                'description': r[2] or '',
                'target_role': r[3] or 'user',
                'allowed_menus': parse_permissions_json(r[4], []),
                'allowed_projects': parse_permissions_json(r[5], ['all']),
                'created_by': r[6] or '',
                'created_at': r[7].isoformat() if r[7] else None
            })
        cur.close()
        conn.close()
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        logger.error(f"Error listing permission templates: {e}")
        return jsonify({'error': 'Failed to load permission templates'}), 500


@bp.route('/api/permission-templates', methods=['POST'])
@admin_required
def create_permission_template():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'กรุณาระบุชื่อ Template'}), 400
    description = str(data.get('description') or '').strip()
    target_role = data.get('target_role') if data.get('target_role') in ('user', 'admin', 'all') else 'user'
    allowed_menus = data.get('allowed_menus')
    if not isinstance(allowed_menus, list):
        return jsonify({'error': 'allowed_menus must be a list'}), 400
    allowed_projects = data.get('allowed_projects')
    if not isinstance(allowed_projects, list):
        allowed_projects = ['all']
    created_by = get_request_user() or 'admin'

    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO permission_templates (name, description, target_role, allowed_menus, allowed_projects, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                target_role = EXCLUDED.target_role,
                allowed_menus = EXCLUDED.allowed_menus,
                allowed_projects = EXCLUDED.allowed_projects,
                created_by = EXCLUDED.created_by
            RETURNING template_id, created_at;
        """, (
            name[:80],
            description[:200],
            target_role,
            json.dumps(allowed_menus, ensure_ascii=False),
            json.dumps(allowed_projects, ensure_ascii=False),
            created_by
        ))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            'success': True,
            'template': {
                'template_id': row[0],
                'name': name[:80],
                'description': description[:200],
                'target_role': target_role,
                'allowed_menus': allowed_menus,
                'allowed_projects': allowed_projects,
                'created_by': created_by,
                'created_at': row[1].isoformat() if row[1] else None
            }
        })
    except Exception as e:
        logger.error(f"Error creating permission template: {e}")
        return jsonify({'error': 'Failed to save permission template'}), 500


@bp.route('/api/permission-templates/<int:template_id>', methods=['DELETE'])
@admin_required
def delete_permission_template(template_id):
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("DELETE FROM permission_templates WHERE template_id = %s RETURNING template_id;", (template_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'error': 'Template not found'}), 404
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting permission template {template_id}: {e}")
        return jsonify({'error': 'Failed to delete permission template'}), 500


@bp.route('/api/users/bulk', methods=['POST'])
@admin_required
def bulk_update_users():
    """Bulk team operations: assign/remove projects, apply menu preset/template, or activate/deactivate."""
    data = request.get_json(silent=True) or {}
    user_ids = data.get('user_ids') or []
    action = str(data.get('action') or '').strip()
    if not isinstance(user_ids, list) or len(user_ids) == 0:
        return jsonify({'error': 'กรุณาเลือกผู้ใช้งานอย่างน้อย 1 คน'}), 400
    if action not in ('add_projects', 'remove_projects', 'set_projects_all', 'apply_menus', 'deactivate', 'activate'):
        return jsonify({'error': 'Invalid bulk action'}), 400

    req_payload = get_request_user_payload() or {}
    actor_uid = str(req_payload.get('user_id', ''))
    clean_ids = []
    for uid in user_ids:
        try:
            clean_ids.append(int(uid))
        except Exception:
            pass
    if not clean_ids:
        return jsonify({'error': 'Invalid user_ids'}), 400

    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = true;")
        active_admin_count = int(cur.fetchone()[0] or 0)

        cur.execute(
            "SELECT user_id, username, role, is_active, allowed_menus, allowed_projects "
            "FROM users WHERE user_id = ANY(%s);",
            (clean_ids,)
        )
        rows = cur.fetchall()
        updated_count = 0
        skipped = []
        revoked_ids = []

        for row in rows:
            uid, uname, urole, uactive, u_menus_raw, u_projects_raw = row
            default_menus = DEFAULT_ADMIN_MENUS if urole == 'admin' else DEFAULT_USER_MENUS
            curr_menus = parse_permissions_json(u_menus_raw, default_menus)
            curr_projects = parse_permissions_json(u_projects_raw, ['all'])

            if action == 'deactivate':
                if str(uid) == actor_uid:
                    skipped.append(f'{uname} (บัญชีตัวเอง)')
                    continue
                if urole == 'admin' and uactive and active_admin_count <= 1:
                    skipped.append(f'{uname} (Admin คนสุดท้าย)')
                    continue
                if not uactive:
                    continue
                cur.execute("UPDATE users SET is_active = FALSE WHERE user_id = %s;", (uid,))
                if urole == 'admin':
                    active_admin_count -= 1
                updated_count += 1
                revoked_ids.append(uid)
                record_user_audit(uid, uname, 'STATUS_CHANGED', 'ปิดใช้งานบัญชี (Bulk Action)')

            elif action == 'activate':
                if uactive:
                    continue
                cur.execute("UPDATE users SET is_active = TRUE WHERE user_id = %s;", (uid,))
                if urole == 'admin':
                    active_admin_count += 1
                updated_count += 1
                record_user_audit(uid, uname, 'STATUS_CHANGED', 'เปิดใช้งานบัญชี (Bulk Action)')

            elif action == 'set_projects_all':
                cur.execute("UPDATE users SET allowed_projects = %s WHERE user_id = %s;", (json.dumps(['all']), uid))
                updated_count += 1
                if str(uid) != actor_uid:
                    revoked_ids.append(uid)
                record_user_audit(uid, uname, 'PERMISSIONS_UPDATED', 'ให้สิทธิ์เข้าถึงทุกโครงการ (Bulk Action)')

            elif action == 'add_projects':
                add_list = [str(p).strip() for p in (data.get('projects') or []) if str(p).strip()]
                if not add_list:
                    continue
                if 'all' in curr_projects:
                    skipped.append(f'{uname} (มีสิทธิ์ทุกโครงการอยู่แล้ว)')
                    continue
                merged = list(dict.fromkeys([*curr_projects, *add_list]))
                cur.execute("UPDATE users SET allowed_projects = %s WHERE user_id = %s;", (json.dumps(merged, ensure_ascii=False), uid))
                updated_count += 1
                if str(uid) != actor_uid:
                    revoked_ids.append(uid)
                record_user_audit(uid, uname, 'PERMISSIONS_UPDATED', f'เพิ่มสิทธิ์ {len(add_list)} โครงการ (Bulk Action)')

            elif action == 'remove_projects':
                rem_set = {str(p).strip().lower() for p in (data.get('projects') or []) if str(p).strip()}
                if not rem_set or 'all' in curr_projects:
                    if 'all' in curr_projects:
                        skipped.append(f'{uname} (ตั้งค่าเป็นทุกโครงการอยู่)')
                    continue
                filtered = [p for p in curr_projects if str(p).strip().lower() not in rem_set]
                cur.execute("UPDATE users SET allowed_projects = %s WHERE user_id = %s;", (json.dumps(filtered, ensure_ascii=False), uid))
                updated_count += 1
                if str(uid) != actor_uid:
                    revoked_ids.append(uid)
                record_user_audit(uid, uname, 'PERMISSIONS_UPDATED', f'ถอดสิทธิ์ {len(rem_set)} โครงการ (Bulk Action)')

            elif action == 'apply_menus':
                new_menus = data.get('allowed_menus')
                if not isinstance(new_menus, list):
                    continue
                if urole == 'admin':
                    # Keep admin governance menus when applying a QA preset to admins
                    admin_only = [m for m in curr_menus if m in DEFAULT_ADMIN_MENUS] or list(DEFAULT_ADMIN_MENUS)
                    final_menus = list(dict.fromkeys([*admin_only, *new_menus]))
                else:
                    final_menus = [m for m in new_menus if m in DEFAULT_USER_MENUS]
                cur.execute("UPDATE users SET allowed_menus = %s WHERE user_id = %s;", (json.dumps(final_menus, ensure_ascii=False), uid))
                updated_count += 1
                if str(uid) != actor_uid:
                    revoked_ids.append(uid)
                tpl_label = str(data.get('template_name') or 'Preset').strip()
                record_user_audit(uid, uname, 'PERMISSIONS_UPDATED', f'ใช้ชุดสิทธิ์ "{tpl_label}" ({len(final_menus)} เมนู · Bulk Action)')

        conn.commit()
        cur.close()
        conn.close()

        for ruid in revoked_ids:
            revoke_user_sessions(ruid)

        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'skipped': skipped
        })
    except Exception as e:
        logger.error(f"Bulk user operation failed ({action}): {e}")
        return jsonify({'error': 'ดำเนินการแบบกลุ่มไม่สำเร็จ'}), 500


@bp.route('/api/users/board-mappings', methods=['GET'])
@token_required
def get_user_board_mappings():
    """Returns active Spectra QA members with their mapped Trello/GitHub handles for QA Board Card integration."""
    try:
        from db_ingestion import get_auth_db_connection
        conn = get_auth_db_connection()
        ensure_user_security_schema(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, username, display_name, department, avatar_path,
                   COALESCE(trello_username, ''), COALESCE(github_username, '')
            FROM users
            WHERE is_active = true
            ORDER BY display_name ASC;
        """)
        members = []
        for r in cur.fetchall():
            members.append({
                'user_id': r[0],
                'username': r[1],
                'display_name': r[2] or r[1],
                'department': r[3] or '',
                'avatar_path': r[4] or '',
                'trello_username': r[5] or '',
                'github_username': r[6] or ''
            })
        cur.close()
        conn.close()
        return jsonify({'success': True, 'members': members})
    except Exception as e:
        logger.error(f"Error loading board member mappings: {e}")
        return jsonify({'error': 'Failed to load board member mappings'}), 500


@bp.route('/api/users/<int:user_id>/avatar', methods=['POST'])
@token_required
def upload_avatar(user_id):
    req_payload = get_request_user_payload() or {}
    is_admin = req_payload.get('role') == 'admin'
    is_self = str(req_payload.get('user_id', '')) == str(user_id)
    if not (is_admin or is_self):
        return jsonify({'error': 'Forbidden: You can only update your own avatar'}), 403

    if 'avatar' not in request.files:
        return jsonify({'error': 'No avatar file provided'}), 400
        
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if file:
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
            return jsonify({'error': 'Invalid image format'}), 400

        header_bytes = file.stream.read(16)
        file.stream.seek(0)
        is_valid_magic = (
            header_bytes.startswith(b'\x89PNG\r\n\x1a\n') or
            header_bytes.startswith(b'\xff\xd8\xff') or
            header_bytes.startswith(b'GIF87a') or
            header_bytes.startswith(b'GIF89a') or
            (header_bytes[:4] == b'RIFF' and header_bytes[8:12] == b'WEBP')
        )
        if not is_valid_magic:
            return jsonify({'error': 'Invalid image file signature'}), 400

        file.stream.seek(0, os.SEEK_END)
        file_size = file.stream.tell()
        file.stream.seek(0)
        if file_size > 5 * 1024 * 1024:
            return jsonify({'error': 'Avatar image must not exceed 5 MB'}), 400
            
        filename = secure_filename(f"avatar_{user_id}_{int(time.time())}.{ext}")
        filepath = AVATARS_FOLDER / filename
        file.save(filepath)
        
        avatar_path = f"/uploads/avatars/{filename}"
        
        try:
            from db_ingestion import get_auth_db_connection
            conn = get_auth_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("UPDATE users SET avatar_path = %s WHERE user_id = %s RETURNING avatar_path;", (avatar_path, user_id))
            updated = cursor.fetchone()
            conn.commit()
            cursor.close()
            conn.close()
            
            if not updated:
                return jsonify({'error': 'User not found'}), 404
                
            return jsonify({'success': True, 'avatar_path': avatar_path})
        except Exception as e:
            logger.error(f"Error saving avatar: {e}")
            return jsonify({'error': 'Failed to save avatar'}), 500


@bp.route('/api/avatars/<path:filename>')
@bp.route('/uploads/avatars/<path:filename>')
@bp.route('/uploads/<path:filename>')
@bp.route('/api/uploads/<path:filename>')
def serve_avatar(filename):
    clean_filename = filename.replace('avatars/', '', 1) if filename.startswith('avatars/') else filename
        
    avatar_file = AVATARS_FOLDER / clean_filename
    if avatar_file.exists() and avatar_file.is_file():
        return send_from_directory(str(AVATARS_FOLDER), clean_filename)
        
    upload_file = UPLOAD_FOLDER / filename
    if upload_file.exists() and upload_file.is_file():
        return send_from_directory(str(UPLOAD_FOLDER), filename)
        
    logger.warning(f"Avatar file not found: {filename}")
    return jsonify({'error': 'File not found'}), 404


@bp.route('/', methods=['GET'])
def root_index():
    """Root info endpoint"""
    return jsonify({
        'service': 'Spectra QA & Thai OCR Backend API',
        'status': 'online',
        'health_check': '/api/health'
    })


@bp.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'message': 'Thai OCR Spell Check API is running'
    })

