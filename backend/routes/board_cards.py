"""QA Board Cards (Trello & GitHub) live sync, card CRUD, automated card testing, attachments, and comments."""
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
bp = Blueprint('board_cards', __name__)

from core.config import BASE_DIR, UPLOAD_FOLDER

def safe_project_uuid(val):
    import uuid
    try:
        return str(uuid.UUID(str(val)))
    except Exception:
        return "00000000-0000-0000-0000-000000000001"


def is_header_card(title, col_titles=None):
    t = (title or '').strip().lower()
    if not t:
        return True
    
    default_headers = {
        'deploy', 'review', 'to do', 'todo', 'doing', 'in progress', 'testing', 
        'testing (agent)', 'template & plan', 'done', 'backlog', 'done back log',
        'done (current sprint card)', 'done (back log card)'
    }
    if t in default_headers:
        return True
        
    if col_titles:
        for c in col_titles:
            c_low = (c or '').strip().lower()
            if c_low and (t == c_low or t.startswith(c_low + ' (') or t.startswith(c_low + '(')):
                return True
                
    header_keywords = ['sprint card', 'back log card', 'backlog card', 'header card', 'placeholder card', 'section header', 'separator']
    if any(kw in t for kw in header_keywords):
        return True
        
    return False


_BOARD_TABLES_ENSURED = False


def _ensure_board_tables(cursor, conn):
    global _BOARD_TABLES_ENSURED
    if _BOARD_TABLES_ENSURED:
        return
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS board_cards (
            card_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
            ext_card_id VARCHAR(50),
            title VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'todo',
            card_type VARCHAR(50),
            priority VARCHAR(50),
            test_result TEXT,
            raw_ext_id TEXT,
            labels_json TEXT,
            members_json TEXT,
            story_points VARCHAR(20),
            actions_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS ext_card_id VARCHAR(50);
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS card_type VARCHAR(50);
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS priority VARCHAR(50);
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS test_result TEXT;
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS raw_ext_id TEXT;
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS labels_json TEXT;
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS members_json TEXT;
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS story_points VARCHAR(20);
        ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS actions_json TEXT;

        CREATE TABLE IF NOT EXISTS board_integrations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID UNIQUE REFERENCES projects(project_id) ON DELETE CASCADE,
            provider VARCHAR(20),
            trello_api_key TEXT,
            trello_token TEXT,
            trello_board_id TEXT,
            trello_todo_list_id TEXT,
            trello_done_list_id TEXT,
            github_token TEXT,
            github_owner TEXT,
            github_repo TEXT,
            columns_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS provider VARCHAR(20);
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS trello_api_key TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS trello_token TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS trello_board_id TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS trello_todo_list_id TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS trello_done_list_id TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS github_token TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS github_owner TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS github_repo TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS columns_json TEXT;
        ALTER TABLE board_integrations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """)
    try:
        cursor.execute("ALTER TABLE board_integrations ALTER COLUMN service_name DROP NOT NULL;")
    except Exception:
        conn.rollback()
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_board_integrations_project_id ON board_integrations(project_id);")
    except Exception:
        conn.rollback()
    conn.commit()
    _BOARD_TABLES_ENSURED = True


@bp.route('/api/projects/<string:project_id>/cards', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_project_cards(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    try:
        cursor = conn.cursor()
        _ensure_board_tables(cursor, conn)

        # Retrieve configured columns if available first
        cursor.execute("""
            SELECT provider, columns_json
            FROM board_integrations
            WHERE project_id = %s
        """, (p_id,))
        integ = cursor.fetchone()
        columns = None
        if integ and integ[1]:
            try:
                import json
                columns = json.loads(integ[1])
            except Exception:
                columns = None
        
        # Fallback default columns if not set
        if not columns:
            columns = [
                {"id": "todo", "title": "To Do", "color": "#64748b"},
                {"id": "in_progress", "title": "In Progress", "color": "#3b82f6"},
                {"id": "testing", "title": "Testing (Agent)", "color": "#a855f7"},
                {"id": "done", "title": "Done", "color": "#22c55e"}
            ]

        col_titles = [c['title'] for c in columns if c.get('title')]

        # Delete legacy header/placeholder cards from DB matching column titles or common list header names
        cursor.execute("""
            DELETE FROM board_cards
            WHERE project_id = %s AND (
                LOWER(TRIM(title)) IN (
                    'deploy', 'review', 'to do', 'todo', 'doing', 'in progress', 'testing', 
                    'testing (agent)', 'template & plan', 'done', 'backlog', 'done back log', 
                    'done (current sprint card)', 'done (back log card)'
                )
                OR LOWER(title) LIKE '%%sprint card%%'
                OR LOWER(title) LIKE '%%back log card%%'
                OR LOWER(title) LIKE '%%header card%%'
                OR LOWER(title) LIKE '%%placeholder%%'
            )
        """, (p_id,))
        conn.commit()

        cursor.execute("""
            SELECT card_id, ext_card_id, title, description, status, card_type, priority, test_result, created_at, raw_ext_id,
                   labels_json, members_json, story_points, actions_json
            FROM board_cards
            WHERE project_id = %s
            ORDER BY created_at DESC
        """, (p_id,))
        rows = cursor.fetchall()
        
        cards = []
        for row in rows:
            c_title = (row[2] or '').strip()
            if is_header_card(c_title, col_titles):
                continue

            cards.append({
                "id": str(row[0]),
                "ext_card_id": row[1],
                "title": c_title,
                "description": row[3],
                "status": row[4],
                "type": row[5] or 'Feature',
                "priority": row[6] or 'Medium',
                "test_result": row[7],
                "created_at": row[8].isoformat() if row[8] else None,
                "raw_ext_id": row[9],
                "labels": json.loads(row[10]) if row[10] else [],
                "members": json.loads(row[11]) if row[11] else [],
                "story_points": row[12] or '',
                "actions": json.loads(row[13]) if row[13] else [],
                "is_saved": True,
                "saved_id": str(row[0]),
                "isTesting": False
            })
        
        return jsonify({"success": True, "cards": cards, "columns": columns})
    except Exception as e:
        logger.error(f"Error fetching cards: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@bp.route('/api/projects/<string:project_id>/board-integration', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin()
def project_board_integration(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    try:
        cursor = conn.cursor()
        _ensure_board_tables(cursor, conn)
        if request.method == 'GET':
            cursor.execute("""
                SELECT provider, trello_api_key, trello_token, trello_board_id, 
                       trello_todo_list_id, trello_done_list_id,
                       github_token, github_owner, github_repo, updated_at
                FROM board_integrations
                WHERE project_id = %s
            """, (p_id,))
            row = cursor.fetchone()
            if not row:
                return jsonify({"success": True, "integration": None})
            
            return jsonify({
                "success": True,
                "integration": {
                    "provider": row[0],
                    "trello_api_key": row[1],
                    "trello_token": row[2],
                    "trello_board_id": row[3],
                    "trello_todo_list_id": row[4],
                    "trello_done_list_id": row[5],
                    "github_token": row[6],
                    "github_owner": row[7],
                    "github_repo": row[8],
                    "updated_at": row[9].isoformat() if row[9] else None
                }
            })
        
        elif request.method == 'POST':
            data = request.json or {}
            provider = data.get('provider', 'trello')
            trello_api_key = data.get('trello_api_key', '').strip()
            trello_token = data.get('trello_token', '').strip()
            trello_board_id = data.get('trello_board_id', '').strip()
            trello_todo_list_id = data.get('trello_todo_list_id', '').strip()
            trello_done_list_id = data.get('trello_done_list_id', '').strip()
            github_token = data.get('github_token', '').strip()
            github_owner = data.get('github_owner', '').strip()
            github_repo = data.get('github_repo', '').strip()

            cursor.execute("""
                INSERT INTO board_integrations (
                    project_id, provider, trello_api_key, trello_token, trello_board_id,
                    trello_todo_list_id, trello_done_list_id,
                    github_token, github_owner, github_repo, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (project_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    trello_api_key = EXCLUDED.trello_api_key,
                    trello_token = EXCLUDED.trello_token,
                    trello_board_id = EXCLUDED.trello_board_id,
                    trello_todo_list_id = EXCLUDED.trello_todo_list_id,
                    trello_done_list_id = EXCLUDED.trello_done_list_id,
                    github_token = EXCLUDED.github_token,
                    github_owner = EXCLUDED.github_owner,
                    github_repo = EXCLUDED.github_repo,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                p_id, provider, trello_api_key, trello_token, trello_board_id,
                trello_todo_list_id, trello_done_list_id,
                github_token, github_owner, github_repo
            ))
            conn.commit()
            return jsonify({"success": True, "message": "บันทึกการตั้งค่าการเชื่อมต่อบอร์ดสำเร็จ"})

    except Exception as e:
        conn.rollback()
        logger.error(f"Error handling board integration: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@bp.route('/api/projects/<string:project_id>/board-integration/test', methods=['POST', 'OPTIONS'])
@cross_origin()
def test_board_integration(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    import requests
    data = request.json or {}
    provider = data.get('provider')
    try:
        if provider == 'trello':
            api_key = data.get('trello_api_key', '').strip()
            token = data.get('trello_token', '').strip()
            board_id = data.get('trello_board_id', '').strip()
            if not api_key or not token or not board_id:
                return jsonify({"success": False, "error": "กรุณาระบุ API Key, Token และ Board ID ให้ครบถ้วน"}), 400
            
            res = requests.get(
                f"https://api.trello.com/1/boards/{board_id}",
                params={"key": api_key, "token": token},
                timeout=10
            )
            if res.ok:
                bdata = res.json()
                return jsonify({"success": True, "message": f"เชื่อมต่อ Trello สำเร็จ! บอร์ด: {bdata.get('name')}"})
            else:
                return jsonify({"success": False, "error": f"Trello API Error ({res.status_code}): {res.text}"}), 400
                
        elif provider == 'github':
            token = data.get('github_token', '').strip()
            owner = data.get('github_owner', '').strip()
            repo = data.get('github_repo', '').strip()
            if not token or not owner or not repo:
                return jsonify({"success": False, "error": "กรุณาระบุ GitHub Token, Owner และ Repo ให้ครบถ้วน"}), 400
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "SpectraQA-Integration"
            }
            res = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=10)
            if res.ok:
                rdata = res.json()
                return jsonify({"success": True, "message": f"เชื่อมต่อ GitHub สำเร็จ! Repo: {rdata.get('full_name')}"})
            else:
                return jsonify({"success": False, "error": f"GitHub API Error ({res.status_code}): {res.text}"}), 400
        else:
            return jsonify({"success": False, "error": "Invalid provider"}), 400
    except Exception as e:
        logger.error(f"Error testing integration: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def format_card_as_markdown(card_data, col_title=""):
    ext_id = card_data.get('ext_card_id') or f"TRL-{card_data.get('id', '')[:6]}"
    title = card_data.get('title') or card_data.get('name') or ''
    desc = card_data.get('description') or card_data.get('desc') or 'ไม่มีรายละเอียด (No description provided)'
    status = col_title or card_data.get('status') or 'To Do'
    card_type = card_data.get('type') or card_data.get('card_type') or 'Feature'
    priority = card_data.get('priority') or 'Medium'
    sp = card_data.get('story_points') or '1'
    
    labels = card_data.get('labels') or []
    if isinstance(labels, str):
        try: labels = json.loads(labels)
        except Exception: labels = []
    label_names = ", ".join([l.get('name', '') for l in labels if l.get('name')]) or 'None'
    
    members = card_data.get('members') or []
    if isinstance(members, str):
        try: members = json.loads(members)
        except Exception: members = []
    member_names = ", ".join([m.get('name', '') for m in members if m.get('name')]) or 'Unassigned'
    
    actions = card_data.get('actions') or []
    if isinstance(actions, str):
        try: actions = json.loads(actions)
        except Exception: actions = []
        
    comments_md = ""
    for act in actions:
        user = act.get('user_name', 'User')
        date = act.get('date', '')
        text = act.get('text', '')
        if text:
            comments_md += f"\n- **{user}** ({date}):\n  {text}\n"
    if not comments_md:
        comments_md = "No comments."

    md = f"""# [{ext_id}] {title}

- **External Card ID**: {ext_id}
- **Type**: {card_type}
- **Priority**: {priority}
- **Story Points**: {sp}
- **Status / Column**: {status}
- **Labels / Tags**: {label_names}
- **Assignees**: {member_names}

## Description & Acceptance Criteria
{desc}

## Comments & Activity History
{comments_md}
"""
    return md


def fetch_live_board_data(cursor, p_id):
    import requests
    import json
    import re
    
    cursor.execute("""
        SELECT provider, trello_api_key, trello_token, trello_board_id,
               github_token, github_owner, github_repo
        FROM board_integrations
        WHERE project_id = %s
    """, (p_id,))
    integ = cursor.fetchone()

    if not integ:
        return False, [], [], "ยังไม่ได้ตั้งค่าการเชื่อมต่อบอร์ดสำหรับโครงการนี้ กรุณากดปุ่ม 'ตั้งค่าการเชื่อมต่อ (⚙️)' เพื่อเชื่อมต่อ Trello หรือ GitHub ก่อน", None

    provider, t_key, t_token, t_board, gh_token, gh_owner, gh_repo = integ
    live_cards = []
    board_columns = []

    # Get existing saved cards in board_cards for project_id to flag is_saved
    cursor.execute("""
        SELECT card_id, ext_card_id, raw_ext_id, test_result
        FROM board_cards
        WHERE project_id = %s
    """, (p_id,))
    saved_rows = cursor.fetchall()
    saved_map = {}
    for r in saved_rows:
        if r[1]: saved_map[r[1]] = {"id": str(r[0]), "test_result": r[3]}
        if r[2]: saved_map[r[2]] = {"id": str(r[0]), "test_result": r[3]}

    if provider == 'trello':
        if not t_key or not t_token or not t_board:
            return False, [], [], "ข้อมูลการเชื่อมต่อ Trello ไม่ครบถ้วน กรุณาตรวจสอบในการตั้งค่า", provider
        
        import concurrent.futures

        def fetch_lists():
            return requests.get(
                f"https://api.trello.com/1/boards/{t_board}/lists",
                params={"key": t_key, "token": t_token},
                timeout=12
            )

        def fetch_members():
            return requests.get(
                f"https://api.trello.com/1/boards/{t_board}/members",
                params={"key": t_key, "token": t_token, "fields": "fullName,username,avatarUrl,avatarHash,initials"},
                timeout=12
            )

        def fetch_actions():
            return requests.get(
                f"https://api.trello.com/1/boards/{t_board}/actions",
                params={
                    "key": t_key,
                    "token": t_token,
                    "filter": "commentCard,updateCard:idList,createCard,addMemberToCard,addAttachmentToCard",
                    "limit": 200
                },
                timeout=12
            )

        def fetch_cards():
            return requests.get(
                f"https://api.trello.com/1/boards/{t_board}/cards",
                params={
                    "key": t_key,
                    "token": t_token,
                    "filter": "open",
                    "fields": "name,desc,idList,labels,idShort,id,idMembers,badges,closed,isTemplate",
                    "members": "true",
                    "member_fields": "fullName,username,avatarUrl,avatarHash,initials"
                },
                timeout=15
            )

        # Execute all 4 Trello requests in parallel for maximum speed
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            fut_lists = executor.submit(fetch_lists)
            fut_members = executor.submit(fetch_members)
            fut_actions = executor.submit(fetch_actions)
            fut_cards = executor.submit(fetch_cards)

            lists_res = fut_lists.result()
            bm_res = fut_members.result()
            b_act_res = fut_actions.result()
            cards_res = fut_cards.result()

        if not lists_res.ok:
            return False, [], [], f"Trello API Error: {lists_res.text}", provider

        if not cards_res.ok:
            return False, [], [], f"Trello API Error: {cards_res.text}", provider

        trello_lists = lists_res.json()
        color_palette = ["#64748b", "#3b82f6", "#a855f7", "#06b6d4", "#f59e0b", "#ec4899", "#22c55e"]
        
        for idx, lst in enumerate(trello_lists):
            lname = lst.get('name', '').lower()
            if any(w in lname for w in ['done', 'complete', 'finish', 'ผ่าน', 'เสร็จ']):
                c_color = "#22c55e"
            elif any(w in lname for w in ['test', 'qa', 'review', 'verify', 'ทดสอบ']):
                c_color = "#a855f7"
            elif any(w in lname for w in ['doing', 'progress', 'in-progress', 'กำลัง', 'dev']):
                c_color = "#3b82f6"
            elif any(w in lname for w in ['todo', 'to do', 'backlog', 'ยังไม่']):
                c_color = "#64748b"
            else:
                c_color = color_palette[idx % len(color_palette)]
            
            board_columns.append({
                "id": lst['id'],
                "title": lst.get('name', 'List'),
                "color": c_color
            })
        
        # Save columns to board_integrations
        cursor.execute("""
            UPDATE board_integrations
            SET columns_json = %s
            WHERE project_id = %s
        """, (json.dumps(board_columns, ensure_ascii=False), p_id))

        def get_trello_member_info(m_data):
            if not m_data: return None
            m_id = m_data.get('id')
            m_hash = m_data.get('avatarHash')
            m_avatar = m_data.get('avatarUrl')
            if m_avatar:
                if not m_avatar.endswith('.png'):
                    m_avatar = m_avatar.rstrip('/') + '/170.png'
                elif m_avatar.endswith('/30.png') or m_avatar.endswith('/50.png'):
                    m_avatar = m_avatar[:-7] + '/170.png'
            elif m_id and m_hash:
                m_avatar = f"https://trello-members.s3.amazonaws.com/{m_id}/{m_hash}/170.png"
            name = m_data.get('fullName') or m_data.get('username') or 'Member'
            username = m_data.get('username') or name
            initials = m_data.get('initials') or (''.join([p[0] for p in name.split() if p])[:2].upper() if name else 'M')
            return {
                "id": m_id, "name": name, "username": username, "avatar": m_avatar, "initials": initials
            }

        board_members_map = {}
        if bm_res.ok:
            try:
                for bm in bm_res.json():
                    m_info = get_trello_member_info(bm)
                    if m_info and m_info.get('id'):
                        board_members_map[m_info['id']] = m_info
            except Exception as bm_err:
                logger.warning(f"Could not parse board members: {bm_err}")

        card_actions_map = {}
        if b_act_res.ok:
            try:
                for act in b_act_res.json():
                    c_id = act.get('data', {}).get('card', {}).get('id')
                    if not c_id: continue
                    a_type = act.get('type')
                    a_user = act.get('memberCreator', {}).get('fullName', 'User')
                    a_avatar = act.get('memberCreator', {}).get('avatarUrl')
                    if a_avatar and not a_avatar.endswith('.png'):
                        a_avatar = a_avatar.rstrip('/') + '/170.png'
                    a_date = act.get('date')
                    text = ""
                    data = act.get('data', {})
                    if a_type == 'commentCard':
                        text = data.get('text', '')
                    elif a_type == 'updateCard' and 'listBefore' in data:
                        text = f"moved this card from {data.get('listBefore', {}).get('name')} to {data.get('listAfter', {}).get('name')}"
                    elif a_type == 'createCard':
                        text = f"added this card to {data.get('list', {}).get('name')}"
                    elif a_type == 'addMemberToCard':
                        text = f"joined this card"
                    elif a_type == 'addAttachmentToCard':
                        att = data.get('attachment', {})
                        att_name = att.get('name', 'image')
                        att_url = att.get('url') or att.get('previewUrl2x') or att.get('previewUrl') or ''
                        if att_url:
                            text = f"attached {att_name} to this card\n\n![{att_name}]({att_url})"
                        else:
                            text = f"attached {att_name} to this card"
                    
                    if text:
                        if c_id not in card_actions_map:
                            card_actions_map[c_id] = []
                        card_actions_map[c_id].append({
                            "user_name": a_user, "user_avatar": a_avatar, "type": a_type, "text": text, "date": a_date
                        })
            except Exception as ex:
                logger.warning(f"Could not parse board actions: {ex}")

        trello_color_map = {
            "blue": "#38bdf8", "green": "#22c55e", "yellow": "#eab308", "orange": "#f97316",
            "red": "#ef4444", "purple": "#a855f7", "sky": "#0284c7", "pink": "#ec4899",
            "lime": "#84cc16", "black": "#475569"
        }
        list_names_lower = set(lst.get('name', '').strip().lower() for lst in trello_lists)

        for c in cards_res.json():
            if c.get('closed') or c.get('isTemplate'):
                continue
            title = c.get('name', '').strip()
            if is_header_card(title, list_names_lower):
                continue

            ext_id = f"TRL-{c.get('idShort', c.get('id')[:6])}"
            raw_id = c.get('id')
            desc = c.get('desc', '')
            status = c.get('idList')

            labels = []
            seen_label_names = set()
            for lbl in c.get('labels', []):
                raw_name = lbl.get('name', '').strip()
                clean_name = re.sub(r"[*_`~#]", "", raw_name).strip()
                if clean_name and clean_name.lower() not in seen_label_names:
                    lcol = lbl.get('color', 'blue')
                    hex_col = trello_color_map.get(lcol, '#38bdf8')
                    labels.append({"name": clean_name, "color": hex_col, "trello_color": lcol})
                    seen_label_names.add(clean_name.lower())

            if not labels:
                tag_match = re.search(r"Tags?\s*[:=]\s*([^\r\n]+)", desc, re.IGNORECASE)
                if tag_match:
                    tag_str = tag_match.group(1).strip()
                    for t in tag_str.split(','):
                        t_clean = re.sub(r"[*_`~#]", "", t).strip()
                        if t_clean and t_clean.lower() not in seen_label_names:
                            labels.append({"name": t_clean, "color": "#38bdf8", "trello_color": "blue"})
                            seen_label_names.add(t_clean.lower())

            sp_match = re.search(r"(?:story\s*points?|points?|point|pt|p)\s*[:=]?\s*(\d+(?:\.\d+)?)", desc + " " + title, re.IGNORECASE)
            story_points = sp_match.group(1) if sp_match else "1"

            members = []
            for m in c.get('members', []):
                m_info = get_trello_member_info(m)
                if m_info:
                    board_members_map[m_info['id']] = m_info
                    members.append(m_info)
            
            for mid in c.get('idMembers', []):
                if not any(m.get('id') == mid for m in members):
                    if mid in board_members_map:
                        members.append(board_members_map[mid])

            actions = card_actions_map.get(raw_id, [])

            card_type = 'Feature'
            priority = 'Medium'
            for lbl in labels:
                lname = lbl['name'].lower()
                if 'bug' in lname: card_type = 'Bug'
                elif 'debt' in lname or 'refactor' in lname: card_type = 'Tech Debt'
                elif 'enhance' in lname: card_type = 'Enhancement'
                if 'high' in lname or 'critical' in lname or 'urgent' in lname: priority = 'High'
                elif 'low' in lname: priority = 'Low'

            is_saved = (ext_id in saved_map) or (raw_id in saved_map)
            saved_info = saved_map.get(ext_id) or saved_map.get(raw_id) or {}
            saved_id = saved_info.get('id')
            test_result = saved_info.get('test_result')

            live_cards.append({
                "id": saved_id or raw_id,
                "ext_card_id": ext_id,
                "title": title,
                "description": desc,
                "status": status,
                "type": card_type,
                "priority": priority,
                "raw_ext_id": raw_id,
                "labels": labels,
                "members": members,
                "story_points": story_points,
                "actions": actions,
                "is_saved": is_saved,
                "saved_id": saved_id,
                "test_result": test_result,
                "isTesting": False
            })

    elif provider == 'github':
        if not gh_token or not gh_owner or not gh_repo:
            return False, [], [], "ข้อมูลการเชื่อมต่อ GitHub ไม่ครบถ้วน กรุณาตรวจสอบในการตั้งค่า", provider
        
        board_columns = [
            {"id": "todo", "title": "Open Issues (To Do)", "color": "#64748b"},
            {"id": "in_progress", "title": "In Progress", "color": "#3b82f6"},
            {"id": "testing", "title": "Testing (Agent)", "color": "#a855f7"},
            {"id": "done", "title": "Closed / Done", "color": "#22c55e"}
        ]
        cursor.execute("""
            UPDATE board_integrations
            SET columns_json = %s
            WHERE project_id = %s
        """, (json.dumps(board_columns, ensure_ascii=False), p_id))

        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SpectraQA-Integration"
        }
        gh_res = requests.get(
            f"https://api.github.com/repos/{gh_owner}/{gh_repo}/issues",
            headers=headers,
            params={"state": "all", "per_page": 50},
            timeout=15
        )
        if not gh_res.ok:
            return False, [], [], f"GitHub API Error: {gh_res.text}", provider
        
        for issue in gh_res.json():
            if 'pull_request' in issue:
                continue
            
            ext_id = f"#{issue.get('number')}"
            raw_id = str(issue.get('number'))
            title = issue.get('title', 'Untitled Issue')
            desc = issue.get('body') or ''
            
            labels = [{"name": l['name'], "color": f"#{l.get('color', '38bdf8')}"} for l in issue.get('labels', [])]
            label_names = [l['name'].lower() for l in labels]

            members = []
            if issue.get('assignee'):
                m = issue['assignee']
                members.append({
                    "id": str(m.get('id')),
                    "name": m.get('login'),
                    "username": m.get('login'),
                    "avatar": m.get('avatar_url'),
                    "initials": m.get('login', 'M')[:2].upper()
                })
            
            if issue.get('state') == 'closed':
                status = 'done'
            elif any('in progress' in l or 'doing' in l for l in label_names):
                status = 'in_progress'
            elif any('testing' in l or 'qa' in l for l in label_names):
                status = 'testing'
            else:
                status = 'todo'

            card_type = 'Feature'
            if any('bug' in l for l in label_names): card_type = 'Bug'
            elif any('enhancement' in l for l in label_names): card_type = 'Enhancement'
            elif any('documentation' in l for l in label_names): card_type = 'Documentation'
            elif any('tech debt' in l for l in label_names): card_type = 'Tech Debt'

            priority = 'Medium'
            if any('critical' in l or 'urgent' in l or 'high' in l for l in label_names):
                priority = 'High'
            elif any('low' in l for l in label_names):
                priority = 'Low'

            sp_match = re.search(r"(?:story\s*points?|points?|point|pt|p)\s*[:=]?\s*(\d+(?:\.\d+)?)", desc + " " + title, re.IGNORECASE)
            story_points = sp_match.group(1) if sp_match else "1"
            actions = []

            is_saved = (ext_id in saved_map) or (raw_id in saved_map)
            saved_info = saved_map.get(ext_id) or saved_map.get(raw_id) or {}
            saved_id = saved_info.get('id')
            test_result = saved_info.get('test_result')

            live_cards.append({
                "id": saved_id or raw_id,
                "ext_card_id": ext_id,
                "title": title,
                "description": desc,
                "status": status,
                "type": card_type,
                "priority": priority,
                "raw_ext_id": raw_id,
                "labels": labels,
                "members": members,
                "story_points": story_points,
                "actions": actions,
                "is_saved": is_saved,
                "saved_id": saved_id,
                "test_result": test_result,
                "isTesting": False
            })
    
    return True, live_cards, board_columns, "", provider


@bp.route('/api/projects/<string:project_id>/cards/live', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_live_project_cards(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("""
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS labels_json TEXT;
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS members_json TEXT;
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS story_points VARCHAR(20);
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS actions_json TEXT;
        """)
        conn.commit()

        success, live_cards, board_columns, err_msg, provider = fetch_live_board_data(cursor, p_id)
        if not success:
            return jsonify({"error": err_msg}), 400
        
        conn.commit()
        return jsonify({
            "success": True,
            "cards": live_cards,
            "columns": board_columns,
            "provider": provider
        })
    except Exception as e:
        conn.rollback()
        logger.error(f"Error fetching live cards: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@bp.route('/api/projects/<string:project_id>/cards/save-selected', methods=['POST', 'OPTIONS'])
@cross_origin()
def save_selected_project_cards(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    data = request.json or {}
    cards_to_save = data.get('cards', [])
    if not cards_to_save:
        return jsonify({"error": "ไม่มี Card ที่เลือกสำหรับการบันทึก"}), 400

    import json
    from db_ingestion import get_db_connection, ingest_markdown_document
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("""
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS labels_json TEXT;
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS members_json TEXT;
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS story_points VARCHAR(20);
            ALTER TABLE board_cards ADD COLUMN IF NOT EXISTS actions_json TEXT;
        """)
        conn.commit()

        cards_to_ingest = []
        saved_count = 0
        for c in cards_to_save:
            ext_id = c.get('ext_card_id') or f"TRL-{str(c.get('id', ''))[:6]}"
            title = (c.get('title') or '').strip()
            desc = c.get('description') or ''
            status = c.get('status') or 'todo'
            card_type = c.get('type') or 'Feature'
            priority = c.get('priority') or 'Medium'
            raw_ext_id = str(c.get('raw_ext_id') or c.get('id') or '')
            labels = c.get('labels') or []
            members = c.get('members') or []
            story_points = str(c.get('story_points') or '1')
            actions = c.get('actions') or []

            labels_json = json.dumps(labels, ensure_ascii=False) if not isinstance(labels, str) else labels
            members_json = json.dumps(members, ensure_ascii=False) if not isinstance(members, str) else members
            actions_json = json.dumps(actions, ensure_ascii=False) if not isinstance(actions, str) else actions

            # 1. Upsert into board_cards
            cursor.execute("""
                INSERT INTO board_cards (
                    project_id, ext_card_id, title, description, status,
                    card_type, priority, raw_ext_id, labels_json, members_json,
                    story_points, actions_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, ext_card_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    status = EXCLUDED.status,
                    card_type = EXCLUDED.card_type,
                    priority = EXCLUDED.priority,
                    raw_ext_id = EXCLUDED.raw_ext_id,
                    labels_json = EXCLUDED.labels_json,
                    members_json = EXCLUDED.members_json,
                    story_points = EXCLUDED.story_points,
                    actions_json = EXCLUDED.actions_json
                RETURNING card_id;
            """, (p_id, ext_id, title, desc, status, card_type, priority, raw_ext_id, labels_json, members_json, story_points, actions_json))
            
            card_filename = f"Card-{ext_id}.md"
            card_md = format_card_as_markdown(c, status)
            
            # Clean up previous document for this card to prevent duplicate/stale embeddings
            cursor.execute("""
                DELETE FROM documents
                WHERE project_id = %s AND original_filename = %s
            """, (p_id, card_filename))

            cards_to_ingest.append((card_filename, card_md, ext_id))
            saved_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        # Ingest each card into RAG Knowledge Base
        for card_filename, card_md, ext_id in cards_to_ingest:
            try:
                ingest_markdown_document(
                    filename=card_filename,
                    markdown_text=card_md,
                    project_id=p_id,
                    doc_category='Trello Card',
                    doc_type='Card'
                )
            except Exception as rag_err:
                logger.error(f"Error ingesting card {ext_id} to RAG: {rag_err}")

        return jsonify({
            "success": True,
            "saved_count": saved_count,
            "message": f"บันทึก Card สำเร็จ {saved_count} ใบ และเพิ่มเข้า RAG Knowledge Base เรียบร้อยแล้ว"
        })
    except Exception as e:
        if 'conn' in locals() and conn:
            try: conn.rollback()
            except Exception: pass
        logger.error(f"Error saving selected cards: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@bp.route('/api/projects/<string:project_id>/cards/<string:card_id>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
def delete_project_card(project_id, card_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    try:
        cursor = conn.cursor()
        # Find ext_card_id to remove from documents
        cursor.execute("SELECT ext_card_id FROM board_cards WHERE card_id = %s AND project_id = %s", (card_id, p_id))
        row = cursor.fetchone()
        if row and row[0]:
            ext_id = row[0]
            card_filename = f"Card-{ext_id}.md"
            cursor.execute("DELETE FROM documents WHERE project_id = %s AND original_filename = %s", (p_id, card_filename))
        
        cursor.execute("DELETE FROM board_cards WHERE card_id = %s AND project_id = %s", (card_id, p_id))
        conn.commit()
        return jsonify({"success": True, "message": "ยกเลิกการบันทึก Card และถอนออกจาก RAG เรียบร้อยแล้ว"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting card: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@bp.route('/api/projects/<string:project_id>/cards/clear-all', methods=['POST', 'OPTIONS'])
@cross_origin()
def clear_all_project_cards(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM board_cards WHERE project_id = %s", (p_id,))
        cursor.execute("DELETE FROM documents WHERE project_id = %s AND doc_category = 'Trello Card'", (p_id,))
        conn.commit()
        return jsonify({"success": True, "message": "ล้างการ์ดที่บันทึกทั้งหมดและนำออกจาก RAG เรียบร้อยแล้ว"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error clearing all cards: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@bp.route('/api/projects/<string:project_id>/cards/sync', methods=['POST', 'OPTIONS'])
@cross_origin()
def sync_project_cards(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500
    try:
        cursor = conn.cursor()
        success, live_cards, board_columns, err_msg, provider = fetch_live_board_data(cursor, p_id)
        if not success:
            return jsonify({"error": err_msg}), 400
        
        conn.commit()
        return jsonify({
            "success": True, 
            "message": f"ตรวจสอบข้อมูลจาก {provider.capitalize()} สำเร็จ! พบ {len(live_cards)} การ์ดสด"
        })
    except Exception as e:
        conn.rollback()
        logger.error(f"Error checking live cards: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()


@bp.route('/api/projects/<string:project_id>/cards/<string:card_id>/move', methods=['POST', 'OPTIONS'])
@cross_origin()
def move_project_card(project_id, card_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    data = request.json or {}
    new_status = data.get('status')
    raw_ext_id = data.get('raw_ext_id') or card_id
    clean_raw_id = raw_ext_id.lstrip('#') if isinstance(raw_ext_id, str) else str(raw_ext_id)

    if not new_status:
        return jsonify({"error": "Missing status parameter"}), 400

    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500

    try:
        cursor = conn.cursor()
        
        # 1. Update status in local board_cards database if exists
        cursor.execute("""
            UPDATE board_cards
            SET status = %s
            WHERE (card_id::text = %s OR raw_ext_id = %s OR ext_card_id = %s) AND project_id = %s
        """, (new_status, card_id, card_id, card_id, p_id))
        conn.commit()

        # Find raw_ext_id if card was saved in DB
        cursor.execute("""
            SELECT raw_ext_id FROM board_cards 
            WHERE (card_id::text = %s OR raw_ext_id = %s OR ext_card_id = %s) AND project_id = %s
        """, (card_id, card_id, card_id, p_id))
        card_row = cursor.fetchone()
        actual_raw_id = (card_row[0] if card_row and card_row[0] else None) or data.get('raw_ext_id') or card_id
        clean_raw_id = actual_raw_id.lstrip('#') if isinstance(actual_raw_id, str) else str(actual_raw_id)

        # 2. Check external board integration
        cursor.execute("""
            SELECT provider, trello_api_key, trello_token, trello_board_id,
                   github_token, github_owner, github_repo, columns_json
            FROM board_integrations
            WHERE project_id = %s
        """, (p_id,))
        integ = cursor.fetchone()

        if integ:
            provider, t_key, t_token, t_board, gh_token, gh_owner, gh_repo, cols_json = integ
            if provider == 'trello' and t_key and t_token and clean_raw_id:
                # Resolve target list ID
                target_list_id = new_status
                if cols_json:
                    try:
                        cols = json.loads(cols_json) if isinstance(cols_json, str) else cols_json
                        m = next((c for c in cols if c.get('id') == new_status), None)
                        if not m:
                            m = next((c for c in cols if c.get('title', '').strip().lower() == new_status.strip().lower()), None)
                        if not m:
                            m = next((c for c in cols if new_status.lower() in c.get('title', '').lower() or c.get('title', '').lower() in new_status.lower()), None)
                        if m:
                            target_list_id = m.get('id')
                    except Exception as c_err:
                        logger.warning(f"Error parsing cols_json: {c_err}")

                try:
                    t_res = requests.put(
                        f"https://api.trello.com/1/cards/{clean_raw_id}",
                        params={"idList": target_list_id, "key": t_key, "token": t_token},
                        json={"idList": target_list_id},
                        timeout=10
                    )
                    logger.info(f"Trello card {clean_raw_id} moved to list {target_list_id}: status={t_res.status_code}, response={t_res.text[:150]}")
                except Exception as t_err:
                    logger.warning(f"Could not move card on Trello API: {t_err}")

            elif provider == 'github' and gh_token and gh_owner and gh_repo and clean_raw_id:
                try:
                    gh_state = "closed" if new_status == 'done' else "open"
                    headers = {
                        "Authorization": f"Bearer {gh_token}",
                        "Accept": "application/vnd.github.v3+json",
                        "User-Agent": "SpectraQA-Integration"
                    }
                    requests.patch(
                        f"https://api.github.com/repos/{gh_owner}/{gh_repo}/issues/{clean_raw_id}",
                        headers=headers,
                        json={"state": gh_state},
                        timeout=10
                    )
                except Exception as gh_err:
                    logger.warning(f"Could not update issue state on GitHub API: {gh_err}")

        return jsonify({"success": True, "message": "ย้ายการ์ดสำเร็จ", "status": new_status})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error moving card: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


@bp.route('/api/projects/<string:project_id>/cards/<string:card_id>/test', methods=['POST', 'OPTIONS'])
@cross_origin()
def test_project_card(project_id, card_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    p_id = safe_project_uuid(project_id)
    data = request.json or {}
    card_data = data.get('card') or {}
    if not card_data.get('id'):
        card_data['id'] = card_id

    from agent_card_tester import run_card_agent_test
    try:
        outcome = run_card_agent_test(p_id, card_id, card_data)
        return jsonify(outcome)
    except Exception as e:
        logger.error(f"Error in run_card_agent_test: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route('/api/attachments/<path:filename>', methods=['GET'])
@cross_origin()
def get_uploaded_attachment(filename):
    attachments_dir = BASE_DIR / 'uploads' / 'attachments'
    return send_from_directory(str(attachments_dir), filename)


@bp.route('/api/projects/<string:project_id>/attachment-proxy', methods=['GET', 'OPTIONS'])
@cross_origin()
def project_attachment_proxy(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"error": "Missing url param"}), 400
    
    p_id = safe_project_uuid(project_id)
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    headers = {"User-Agent": "SpectraQA"}
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT trello_api_key, trello_token FROM board_integrations WHERE project_id = %s", (p_id,))
            row = cursor.fetchone()
            if row and row[0] and row[1]:
                headers["Authorization"] = f'OAuth oauth_consumer_key="{row[0]}", oauth_token="{row[1]}"'
            cursor.close()
            conn.close()
        except Exception:
            pass
    
    try:
        resp = requests.get(target_url, headers=headers, stream=True, timeout=15)
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        res_headers = [(name, value) for (name, value) in resp.raw.headers.items() if name.lower() not in excluded_headers]
        return Response(resp.iter_content(chunk_size=1024), status=resp.status_code, headers=res_headers, content_type=resp.headers.get('content-type', 'application/octet-stream'))
    except Exception as e:
        logger.error(f"Attachment proxy error: {e}")
        return jsonify({"error": str(e)}), 500


@bp.route('/api/projects/<string:project_id>/cards/upload-attachment', methods=['POST', 'OPTIONS'])
@cross_origin()
def upload_card_attachment(project_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    
    p_id = safe_project_uuid(project_id)
    attachments_dir = BASE_DIR / 'uploads' / 'attachments'
    attachments_dir.mkdir(exist_ok=True, parents=True)

    import uuid
    import base64

    # Case 1: multipart/form-data file (image or video)
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename:
            orig_name = secure_filename(file.filename) or "upload.png"
            ext = Path(orig_name).suffix.lower()
            if not ext:
                ext = '.png'
            unique_name = f"{uuid.uuid4().hex[:12]}_{orig_name}"
            target_path = attachments_dir / unique_name
            file.save(str(target_path))

            is_video = ext in ['.mp4', '.webm', '.mov', '.avi', '.mkv']
            file_url = f"http://localhost:5000/api/attachments/{unique_name}"
            return jsonify({
                "success": True,
                "url": file_url,
                "filename": unique_name,
                "is_video": is_video,
                "type": "video" if is_video else "image"
            })

    # Case 2: JSON payload with base64 image (from clipboard Ctrl+V)
    data = request.json or {}
    if 'base64_data' in data:
        b64_str = data['base64_data']
        ext = '.png'
        if ',' in b64_str:
            header, b64_str = b64_str.split(',', 1)
            if 'image/jpeg' in header or 'image/jpg' in header:
                ext = '.jpg'
            elif 'image/gif' in header:
                ext = '.gif'
            elif 'image/webp' in header:
                ext = '.webp'
            elif 'video/mp4' in header:
                ext = '.mp4'
            elif 'video/webm' in header:
                ext = '.webm'

        file_bytes = base64.b64decode(b64_str)
        unique_name = f"clip_{uuid.uuid4().hex[:10]}{ext}"
        target_path = attachments_dir / unique_name
        with open(target_path, 'wb') as f:
            f.write(file_bytes)

        is_video = ext in ['.mp4', '.webm']
        file_url = f"http://localhost:5000/api/attachments/{unique_name}"
        return jsonify({
            "success": True,
            "url": file_url,
            "filename": unique_name,
            "is_video": is_video,
            "type": "video" if is_video else "image"
        })

    return jsonify({"error": "No file or base64 data provided"}), 400


@bp.route('/api/projects/<string:project_id>/cards/<string:card_id>/comments', methods=['POST', 'OPTIONS'])
@cross_origin()
def post_card_comment(project_id, card_id):
    if request.method == 'OPTIONS':
        res = jsonify({'status': 'ok'})
        res.headers.add('Access-Control-Allow-Origin', '*')
        res.headers.add('Access-Control-Allow-Headers', '*')
        res.headers.add('Access-Control-Allow-Methods', '*')
        return res, 200
    
    p_id = safe_project_uuid(project_id)
    data = request.json or {}
    comment_text = (data.get('comment') or '').strip()
    if not comment_text:
        return jsonify({"error": "Comment text cannot be empty"}), 400

    from datetime import datetime, timezone
    import json
    import requests
    from db_ingestion import get_db_connection
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection error"}), 500

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT provider, trello_api_key, trello_token, trello_board_id,
                   github_token, github_owner, github_repo
            FROM board_integrations WHERE project_id = %s
        """, (p_id,))
        integ = cursor.fetchone()

        cursor.execute("""
            SELECT raw_ext_id, actions_json
            FROM board_cards WHERE (card_id::text = %s OR raw_ext_id = %s OR ext_card_id = %s) AND project_id = %s
        """, (card_id, card_id, card_id, p_id))
        card_row = cursor.fetchone()

        raw_id = data.get('raw_ext_id') or (card_row[0] if card_row else None) or card_id
        # Clean raw_id if starts with # (like #12 for github)
        clean_raw_id = raw_id.lstrip('#') if isinstance(raw_id, str) else str(raw_id)
        if clean_raw_id.startswith('TRL-'):
            cursor.execute("SELECT raw_ext_id FROM board_cards WHERE ext_card_id = %s AND project_id = %s", (clean_raw_id, p_id))
            bc_row = cursor.fetchone()
            if bc_row and bc_row[0] and not bc_row[0].startswith('TRL-'):
                clean_raw_id = bc_row[0]
            elif integ and integ[0] == 'trello' and integ[1] and integ[2] and integ[3]:
                try:
                    s_num = int(clean_raw_id.replace('TRL-', '').strip())
                    t_cards_res = requests.get(f"https://api.trello.com/1/boards/{integ[3]}/cards", params={"key": integ[1], "token": integ[2], "fields": "id,idShort"}, timeout=8)
                    if t_cards_res.ok:
                        for tc in t_cards_res.json():
                            if tc.get('idShort') == s_num:
                                clean_raw_id = tc.get('id')
                                break
                except Exception as ex:
                    logger.warning(f"Could not resolve TRL- id to Trello hex id: {ex}")

        client_actions = data.get('current_actions') or []
        existing_actions = (json.loads(card_row[1]) if card_row and card_row[1] else None) or client_actions or []

        logger.info(f"Posting comment: project={p_id}, card_id={card_id}, raw_id={raw_id}, clean_raw_id={clean_raw_id}, provider={integ[0] if integ else None}")

        trello_action_created = None
        if integ and integ[0] == 'trello' and integ[1] and integ[2] and clean_raw_id:
            t_key, t_token = integ[1], integ[2]
            
            # 1. Sync attachments to Trello card
            attachments_dir = BASE_DIR / 'uploads' / 'attachments'
            for att in data.get('attachments', []):
                filename = att.get('filename')
                if filename:
                    file_path = attachments_dir / filename
                    if file_path.exists():
                        try:
                            with open(file_path, 'rb') as f_up:
                                att_res = requests.post(
                                    f"https://api.trello.com/1/cards/{clean_raw_id}/attachments",
                                    params={"key": t_key, "token": t_token, "name": att.get('type', 'attachment')},
                                    files={"file": (filename, f_up, 'application/octet-stream')},
                                    timeout=15
                                )
                                logger.info(f"Trello attachment upload result: status={att_res.status_code}")
                        except Exception as att_err:
                            logger.warning(f"Could not upload attachment to Trello: {att_err}")

            # 2. Post comment to Trello card
            try:
                tc_res = requests.post(
                    f"https://api.trello.com/1/cards/{clean_raw_id}/actions/comments",
                    params={"key": t_key, "token": t_token, "text": comment_text},
                    timeout=12
                )
                logger.info(f"Trello comment response: status={tc_res.status_code}, text={tc_res.text[:200]}")
                if tc_res.ok:
                    act_data = tc_res.json()
                    a_user = act_data.get('memberCreator', {}).get('fullName', 'User')
                    a_avatar = act_data.get('memberCreator', {}).get('avatarUrl')
                    if a_avatar and not a_avatar.endswith('.png'):
                        a_avatar = a_avatar.rstrip('/') + '/170.png'
                    trello_action_created = {
                        "user_name": a_user,
                        "user_avatar": a_avatar,
                        "type": "commentCard",
                        "text": comment_text,
                        "date": act_data.get('date', datetime.now(timezone.utc).isoformat())
                    }
                else:
                    logger.error(f"Failed to post comment to Trello: {tc_res.status_code} {tc_res.text}")
            except Exception as t_err:
                logger.exception(f"Could not post comment to Trello API: {t_err}")

            # 3. Refresh complete action list from Trello so history transaction updates seamlessly
            try:
                act_res = requests.get(
                    f"https://api.trello.com/1/cards/{clean_raw_id}/actions",
                    params={
                        "key": t_key,
                        "token": t_token,
                        "filter": "commentCard,updateCard:idList,createCard,addMemberToCard,addAttachmentToCard",
                        "limit": 50
                    },
                    timeout=10
                )
                if act_res.ok:
                    fresh_actions = []
                    for act in act_res.json():
                        a_type = act.get('type')
                        a_user = act.get('memberCreator', {}).get('fullName', 'User')
                        a_avatar = act.get('memberCreator', {}).get('avatarUrl')
                        if a_avatar and not a_avatar.endswith('.png'):
                            a_avatar = a_avatar.rstrip('/') + '/170.png'
                        a_date = act.get('date')
                        t_text = ""
                        act_d = act.get('data', {})
                        if a_type == 'commentCard':
                            t_text = act_d.get('text', '')
                        elif a_type == 'updateCard' and 'listBefore' in act_d:
                            t_text = f"moved this card from {act_d.get('listBefore', {}).get('name')} to {act_d.get('listAfter', {}).get('name')}"
                        elif a_type == 'createCard':
                            t_text = f"added this card to {act_d.get('list', {}).get('name')}"
                        elif a_type == 'addMemberToCard':
                            t_text = "joined this card"
                        elif a_type == 'addAttachmentToCard':
                            att = act_d.get('attachment', {})
                            att_name = att.get('name', 'image')
                            att_url = att.get('url') or att.get('previewUrl2x') or att.get('previewUrl') or ''
                            if att_url:
                                t_text = f"attached {att_name} to this card\n\n![{att_name}]({att_url})"
                            else:
                                t_text = f"attached {att_name} to this card"
                        
                        if t_text:
                            fresh_actions.append({
                                "user_name": a_user,
                                "user_avatar": a_avatar,
                                "type": a_type,
                                "text": t_text,
                                "date": a_date
                            })
                    if fresh_actions:
                        existing_actions = fresh_actions
            except Exception as act_err:
                logger.warning(f"Could not fetch updated actions from Trello: {act_err}")

        elif integ and integ[0] == 'github' and integ[4] and integ[5] and integ[6] and clean_raw_id:
            # GitHub Issues Comment Sync
            gh_token, gh_owner, gh_repo = integ[4], integ[5], integ[6]
            try:
                gh_res = requests.post(
                    f"https://api.github.com/repos/{gh_owner}/{gh_repo}/issues/{clean_raw_id}/comments",
                    headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "SpectraQA"},
                    json={"body": comment_text},
                    timeout=12
                )
                if gh_res.ok:
                    gh_data = gh_res.json()
                    g_user = gh_data.get('user', {}).get('login', 'GitHub User')
                    g_avatar = gh_data.get('user', {}).get('avatar_url')
                    trello_action_created = {
                        "user_name": g_user,
                        "user_avatar": g_avatar,
                        "type": "commentCard",
                        "text": comment_text,
                        "date": gh_data.get('created_at', datetime.now(timezone.utc).isoformat())
                    }
            except Exception as gh_err:
                logger.warning(f"Could not post comment to GitHub API: {gh_err}")

        new_action = trello_action_created or {
            "user_name": "SpectraQA User",
            "user_avatar": None,
            "type": "commentCard",
            "text": comment_text,
            "date": datetime.now(timezone.utc).isoformat()
        }
        is_already_in = False
        for a in existing_actions:
            if isinstance(a, dict) and a.get('type') == 'commentCard' and a.get('text') == comment_text:
                is_already_in = True
                break
        if not is_already_in:
            existing_actions.insert(0, new_action)

        if card_row:
            cursor.execute("""
                UPDATE board_cards
                SET actions_json = %s
                WHERE (card_id::text = %s OR raw_ext_id = %s OR ext_card_id = %s) AND project_id = %s
            """, (json.dumps(existing_actions, ensure_ascii=False), card_id, card_id, card_id, p_id))
        conn.commit()

        return jsonify({
            "success": True,
            "actions": existing_actions,
            "message": "เพิ่มความคิดเห็นและอัปเดตไปยัง Trello เรียบร้อยแล้ว"
        })
    except Exception as e:
        conn.rollback()
        logger.error(f"Error posting comment: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

