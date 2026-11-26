"""Admin API usage/billing, QA Research chat & overview, Requirement extraction/sync, and QA Security scan."""
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
bp = Blueprint('research_requirements', __name__)

from core.auth import admin_required, get_request_user, resolve_request_auth

@bp.route('/api/admin/usage', methods=['GET'])
def admin_usage_stats():
    try:
        from db_ingestion import get_api_usage_stats
        time_filter = request.args.get('time_filter', 'all')
        stats = get_api_usage_stats(time_filter=time_filter)
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Error fetching usage stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/admin/usage/recalculate', methods=['POST'])
@admin_required
def admin_recalculate_usage():
    try:
        from db_ingestion import recalculate_api_usage_costs
        result = recalculate_api_usage_costs()
        status = 200 if result.get('success') else 500
        return jsonify(result), status
    except Exception as e:
        logger.error(f"Error recalculating usage costs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/admin/credit', methods=['GET', 'POST'])
def admin_billing_credit():
    try:
        from db_ingestion import get_billing_credit, update_billing_credit
        if request.method == 'GET':
            credit = get_billing_credit()
            return jsonify({'success': True, 'credit_thb': credit})
        elif request.method == 'POST':
            payload = resolve_request_auth()
            if not payload:
                return jsonify({'success': False, 'error': 'Unauthorized, please login'}), 401
            if payload.get('role') != 'admin':
                return jsonify({'success': False, 'error': 'Forbidden: Admin privileges required'}), 403
            data = request.json or {}
            new_amount = float(data.get('credit_thb', 0.0))
            if update_billing_credit(new_amount):
                return jsonify({'success': True, 'message': 'Credit updated successfully', 'credit_thb': new_amount})
            else:
                return jsonify({'success': False, 'error': 'Failed to update credit'}), 500
    except Exception as e:
        logger.error(f"Error handling billing credit: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/research/knowledge-overview', methods=['GET'])
def research_knowledge_overview():
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'Missing project_id'}), 400
    conn = None
    cursor = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Active Documents
        cursor.execute("""
            SELECT doc_id, original_filename, doc_category, doc_type, LENGTH(COALESCE(full_markdown_content, ''))
            FROM documents
            WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL)
            ORDER BY doc_id DESC;
        """, (project_id,))
        docs = [
            {
                "doc_id": str(r[0]),
                "filename": r[1] or "Document",
                "category": r[2] or "General",
                "doc_type": r[3] or "Document",
                "size_chars": int(r[4] or 0)
            }
            for r in cursor.fetchall()
        ]

        # 2. Counts across Agents
        def safe_count(sql):
            try:
                cursor.execute(sql, (project_id,))
                return int(cursor.fetchone()[0] or 0)
            except Exception:
                conn.rollback()
                return 0

        reqs_count = safe_count("SELECT COUNT(*) FROM structured_requirements WHERE project_id = %s::uuid;")
        gen_docs_count = safe_count("SELECT COUNT(*) FROM qa_generated_documents WHERE project_id = %s::uuid AND UPPER(COALESCE(status, '')) = 'COMPLETED';")
        audits_count = safe_count("SELECT COUNT(*) FROM qa_transactions WHERE project_id = %s::uuid;")
        diagrams_count = safe_count("SELECT COUNT(*) FROM qa_analysis_diagrams WHERE project_id = %s::uuid;")
        testcases_count = safe_count("SELECT COUNT(*) FROM qa_automation_testcases WHERE project_id = %s::uuid;")

        return jsonify({
            "success": True,
            "documents": docs,
            "stats": {
                "docs_count": len(docs),
                "reqs_count": reqs_count,
                "generated_docs_count": gen_docs_count,
                "audits_count": audits_count,
                "has_diagram": diagrams_count > 0,
                "testcases_count": testcases_count
            }
        })
    except Exception as e:
        logger.error(f"Error in research_knowledge_overview: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


@bp.route('/api/research/chat', methods=['POST'])
def research_chat():
    logger.info("Received request at /api/research/chat. Processing...")
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400
        
    project_id = data.get('project_id')
    message = data.get('message')
    history = (data.get('history') or [])[-10:]
    doc_ids = data.get('doc_ids') or []
    research_mode = data.get('research_mode') or 'deep_research'
    
    try:
        # 1. Retrieve comprehensive multi-source grounded context from DB (optionally scoped by doc_ids)
        logger.info(f"Querying comprehensive knowledge base for project {project_id} (mode={research_mode}, scoped_docs={len(doc_ids)})...")
        import db_ingestion
        import base64
        ctx_data = db_ingestion.retrieve_comprehensive_qa_context(
            project_id, message, history=history, doc_ids=doc_ids if doc_ids else None
        )
        
        context_str = ctx_data.get('context_str', '')
        project_name = ctx_data.get('project_name', '')
        project_code = ctx_data.get('project_code', '')
        
        logger.info(
            f"Assembled comprehensive QA context ({len(context_str)} chars, {ctx_data.get('docs_count', 0)} docs, "
            f"{ctx_data.get('reqs_count', 0)} reqs, {ctx_data.get('chunks_matched', 0)} chunks) for project '{project_name}' ({project_code})."
        )
        
        # 2. Serialize recent history into text format
        history_text = ""
        for h in history:
            role = "User" if h.get("role") == "user" else "Assistant"
            history_text += f"{role}: {(h.get('content') or '')[:1200]}\n"
        
        try:
            from orchestrator.state import QAState
            from orchestrator.agents import QAResearchAgent
        except ImportError:
            from backend.orchestrator.state import QAState
            from backend.orchestrator.agents import QAResearchAgent
            
        qa_state = QAState(
            project_id=project_id,
            project_name=project_name,
            project_code=project_code,
            doc_type=research_mode,
            kb_context=context_str,
            instruction=message,
            original_text=history_text
        )

        sources_payload = {
            "mode": research_mode,
            "docs_count": ctx_data.get("docs_count", 0),
            "reqs_count": ctx_data.get("reqs_count", 0),
            "generated_docs_count": ctx_data.get("generated_docs_count", 0),
            "audits_count": ctx_data.get("audits_count", 0),
            "has_diagram": ctx_data.get("has_diagram", False),
            "chunks_matched": ctx_data.get("chunks_matched", 0),
            "sources": ctx_data.get("sources_metadata", [])
        }
        encoded_sources = base64.b64encode(
            json.dumps(sources_payload, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        
        from flask import Response, stream_with_context
        def generate():
            yield ""
            for chunk in QAResearchAgent.generate_stream(qa_state):
                yield chunk
                
        resp = Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')
        resp.headers['X-Research-Sources'] = encoded_sources
        resp.headers['Access-Control-Expose-Headers'] = 'X-Research-Sources'
        return resp
            
    except Exception as e:
        logger.error(f"Research chat error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/requirements/extract', methods=['POST'])
def extract_requirements():
    try:
        from agent_1_ingestion import extract_requirements_from_text
        data = request.json
        project_id = data.get('project_id')
        doc_id = data.get('doc_id')
        text = data.get('text')
        
        if not project_id or not doc_id or not text:
            return jsonify({'error': 'Missing project_id, doc_id, or text'}), 400
            
        success, msg = extract_requirements_from_text(text, project_id, doc_id)
        if success:
            return jsonify({'success': True, 'message': msg})
        return jsonify({'error': msg}), 500
    except Exception as e:
        logger.error(f"Error extracting requirements: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _fetch_github_code(repo_url: str) -> str:
    import tempfile
    import subprocess
    import os
    if not repo_url.startswith("https://github.com/"):
        raise ValueError("Invalid GitHub URL. Must start with https://github.com/")
        
    combined_code = []
    total_chars = 0
    max_chars = 150000
    allowed_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.php', '.c', '.cpp', '.cs', '.rb', '.html', '.css'}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(['git', 'clone', '--depth', '1', repo_url, tmpdir], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to clone repository: {result.stderr}")
            
        for root, dirs, files in os.walk(tmpdir):
            if '.git' in dirs:
                dirs.remove('.git')
                
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in allowed_extensions:
                    filepath = os.path.join(root, file)
                    relpath = os.path.relpath(filepath, tmpdir)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        file_header = f"\n\n--- FILE: {relpath} ---\n"
                        combined_code.append(file_header + content)
                        total_chars += len(content)
                        
                        if total_chars > max_chars:
                            combined_code.append("\n\n[WARNING: Repository size exceeded safe limits. Truncated.]")
                            return "".join(combined_code)[:max_chars + 1000]
                    except Exception:
                        pass
                        
    if not combined_code:
        raise ValueError("No valid source code files found in the repository.")
        
    return "".join(combined_code)


@bp.route('/api/qa/security/scan', methods=['POST'])
def api_qa_security_scan():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON payload provided'}), 400
            
        language = data.get('language', 'auto')
        
        if 'github_url' in data and data['github_url']:
            try:
                source_code = _fetch_github_code(data['github_url'])
                language = 'auto (GitHub Repo)'
            except Exception as github_err:
                return jsonify({'error': str(github_err)}), 400
        elif 'source_code' in data and data['source_code']:
            source_code = data['source_code']
        else:
            return jsonify({'error': 'Missing source_code or github_url'}), 400
        
        standard = data.get('standard', 'OWASP Top 10 (2021)')
        
        from orchestrator.state import QASecurityState
        from orchestrator.pipeline import run_qa_security
        
        state = QASecurityState(source_code=source_code, language=language, standard=standard)
        state = run_qa_security(state)
        
        if state.status == "failed":
            return jsonify({'error': state.error}), 500
            
        return jsonify({
            'success': True,
            'report': state.report,
            'vulnerabilities_found': state.vulnerability_count
        })
        
    except Exception as e:
        logger.error(f"QA Security Scan error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/requirements', methods=['GET'])
def get_requirements():
    project_id = request.args.get('project_id', type=str)
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        base_query = """
            SELECT 
                r.req_id, r.req_code, r.title, r.description, r.actors, 
                r.preconditions, r.steps, r.expected_results, r.ui_elements, 
                r.api_endpoints, r.status, r.created_at, r.doc_id,
                d.original_filename, d.doc_category, d.doc_type
            FROM structured_requirements r
            LEFT JOIN documents d ON r.doc_id = d.doc_id
        """
        if project_id:
            cursor.execute(base_query + " WHERE r.project_id = %s::uuid ORDER BY r.created_at DESC;", (project_id,))
        else:
            cursor.execute(base_query + " ORDER BY r.created_at DESC;")
            
        rows = cursor.fetchall()
        reqs = []
        for row in rows:
            reqs.append({
                'req_id': str(row[0]),
                'req_code': row[1],
                'title': row[2],
                'description': row[3],
                'actors': row[4],
                'preconditions': row[5],
                'steps': row[6],
                'expected_results': row[7],
                'ui_elements': row[8],
                'api_endpoints': row[9],
                'status': row[10],
                'created_at': row[11].isoformat() if row[11] else None,
                'doc_id': str(row[12]) if row[12] else None,
                'doc_name': row[13] or 'ไม่ระบุเอกสาร',
                'doc_category': row[14] or 'General',
                'doc_type': row[15] or 'General'
            })
            
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'requirements': reqs})
    except Exception as e:
        logger.error(f"Error fetching requirements: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/requirements/sync-from-project', methods=['POST'])
def sync_requirements_from_project():
    """
    Extracts & synchronizes structured requirements directly from the active
    documents/resources stored in the system for this project.
    """
    data = request.get_json() or {}
    project_id = data.get('project_id')
    doc_ids = data.get('doc_ids', [])
    
    if not project_id:
        return jsonify({'error': 'Missing project_id'}), 400
        
    try:
        from db_ingestion import get_db_connection
        from agent_1_ingestion import extract_requirements_from_text, init_requirements_table
        
        init_requirements_table()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if doc_ids and len(doc_ids) > 0:
            cursor.execute("""
                SELECT doc_id, original_filename, doc_category, doc_type, full_markdown_content
                FROM documents
                WHERE project_id = %s::uuid AND doc_id = ANY(%s::uuid[]) AND (status = 'Active' OR status IS NULL)
                ORDER BY doc_id DESC;
            """, (project_id, doc_ids))
        else:
            cursor.execute("""
                SELECT doc_id, original_filename, doc_category, doc_type, full_markdown_content
                FROM documents
                WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL)
                ORDER BY doc_id DESC;
            """, (project_id,))
            
        doc_rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not doc_rows:
            return jsonify({
                'success': False, 
                'error': 'ไม่พบเอกสารหรือ Resource ในโครงการนี้ กรุณาอัปโหลดเอกสารผ่านหน้า Knowledge Base หรือสแกนเอกสารในโครงการก่อน'
            }), 404
            
        doc_messages = []
        for d in doc_rows:
            did = d[0]
            fname = d[1] or "Document"
            markdown_text = d[4] or ""
            if not markdown_text.strip():
                continue
                
            success, msg = extract_requirements_from_text(markdown_text, str(project_id), did)
            if success:
                doc_messages.append(f"{fname}: สำเร็จ")
            else:
                doc_messages.append(f"{fname}: {msg}")
                
        # Query updated requirements with source doc details
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.req_id, r.req_code, r.title, r.description, r.actors, 
                r.preconditions, r.steps, r.expected_results, r.ui_elements, 
                r.api_endpoints, r.status, r.created_at, r.doc_id,
                d.original_filename, d.doc_category, d.doc_type
            FROM structured_requirements r
            LEFT JOIN documents d ON r.doc_id = d.doc_id
            WHERE r.project_id = %s::uuid
            ORDER BY r.created_at DESC;
        """, (project_id,))
        rows = cursor.fetchall()
        reqs = []
        for row in rows:
            reqs.append({
                'req_id': str(row[0]),
                'req_code': row[1],
                'title': row[2],
                'description': row[3],
                'actors': row[4],
                'preconditions': row[5],
                'steps': row[6],
                'expected_results': row[7],
                'ui_elements': row[8],
                'api_endpoints': row[9],
                'status': row[10],
                'created_at': row[11].isoformat() if row[11] else None,
                'doc_id': str(row[12]) if row[12] else None,
                'doc_name': row[13] or 'ไม่ระบุเอกสาร',
                'doc_category': row[14] or 'General',
                'doc_type': row[15] or 'General'
            })
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'สกัดและซิงค์ Requirement จากเอกสาร {len(doc_rows)} รายการเรียบร้อยแล้ว',
            'details': doc_messages,
            'requirements': reqs,
            'docs_processed': len(doc_rows)
        })
        
    except Exception as e:
        logger.error(f"Error syncing requirements from project: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

