"""Knowledge Base document CRUD, Hybrid RAG search, re-indexing, AI feedback memory, and format rules."""
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
bp = Blueprint('knowledge_base', __name__)

from core.config import CACHE_FOLDER, KB_IMAGES_FOLDER
from core.auth import get_request_user_payload
from format_checker import load_format_rules, save_format_rules

def _check_kb_write_permission(project_id: str = None, allow_ocr: bool = False):
    """Verify JWT authentication and Knowledge Base write permission."""
    req_payload = get_request_user_payload()
    if not req_payload:
        return jsonify({'error': 'กรุณาเข้าสู่ระบบก่อนดำเนินการจัดการคลังความรู้'}), 401
    role = str(req_payload.get('role') or '').lower()
    if role == 'admin':
        return None
    allowed_menus = req_payload.get('allowed_menus') or []
    required_menus = {'knowledge_base', 'project_management'}
    if allow_ocr:
        required_menus.update({'ocr', 'scan_ocr'})
    if isinstance(allowed_menus, list) and not any(m in required_menus for m in allowed_menus):
        return jsonify({'error': 'คุณไม่มีสิทธิ์แก้ไขหรือจัดการเอกสารใน Knowledge Base'}), 403
    if project_id:
        allowed_projects = req_payload.get('allowed_projects') or ['all']
        if isinstance(allowed_projects, list) and 'all' not in allowed_projects:
            norm = [str(a).strip().lower() for a in allowed_projects]
            if str(project_id).strip().lower() not in norm:
                return jsonify({'error': 'คุณไม่มีสิทธิ์เข้าถึงหรือแก้ไขเอกสารในโครงการนี้'}), 403
    return None


@bp.route('/api/kb/stats', methods=['GET'])
def kb_stats():
    """ดูสถิติรวมของ Knowledge Base"""
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM projects;")
        project_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM documents;")
        doc_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM document_chunks;")
        chunk_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'stats': {
                'projects': project_count,
                'documents': doc_count,
                'chunks': chunk_count
            }
        })
    except Exception as e:
        logger.error(f"KB stats error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/documents', methods=['GET'])
def kb_documents():
    """
    ดูเอกสารทั้งหมดใน DB (optionally filtered by project_id)
    Query: ?project_id=<id>&limit=50&offset=0
    """
    project_id = request.args.get('project_id', type=str)
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        if project_id:
            cursor.execute(
                """
                SELECT d.doc_id, d.original_filename, d.project_id, d.doc_category, d.doc_type,
                       d.status, d.created_at, COALESCE(d.is_golden_data, FALSE) AS is_golden_data,
                       COALESCE(cc.chunk_count, 0) AS chunk_count
                FROM documents d
                LEFT JOIN (
                    SELECT doc_id, COUNT(*) AS chunk_count
                    FROM document_chunks
                    GROUP BY doc_id
                ) cc ON d.doc_id = cc.doc_id
                WHERE d.project_id = %s::uuid AND (d.status = 'Active' OR d.status IS NULL)
                ORDER BY d.created_at DESC NULLS LAST, d.doc_id DESC
                LIMIT %s OFFSET %s;
                """,
                (project_id, limit, offset)
            )
        else:
            cursor.execute(
                """
                SELECT d.doc_id, d.original_filename, d.project_id, d.doc_category, d.doc_type,
                       d.status, d.created_at, COALESCE(d.is_golden_data, FALSE) AS is_golden_data,
                       COALESCE(cc.chunk_count, 0) AS chunk_count
                FROM documents d
                LEFT JOIN (
                    SELECT doc_id, COUNT(*) AS chunk_count
                    FROM document_chunks
                    GROUP BY doc_id
                ) cc ON d.doc_id = cc.doc_id
                WHERE (d.status = 'Active' OR d.status IS NULL)
                ORDER BY d.created_at DESC NULLS LAST, d.doc_id DESC
                LIMIT %s OFFSET %s;
                """,
                (limit, offset)
            )

        rows = cursor.fetchall()
        documents = []
        for row in rows:
            doc_id_val = row[0]
            documents.append({
                'id': str(doc_id_val),
                'doc_id': str(doc_id_val),
                'name': row[1] or 'ไม่ระบุชื่อ',
                'original_filename': row[1] or 'ไม่ระบุชื่อ',
                'filename': row[1] or 'ไม่ระบุชื่อ',
                'project_id': str(row[2]) if row[2] else None,
                'doc_category': row[3],
                'doc_type': row[4],
                'status': row[5],
                'created_at': row[6].isoformat() if row[6] else None,
                'is_golden_data': bool(row[7]),
                'chunk_count': int(row[8] or 0)
            })

        if project_id:
            cursor.execute("SELECT COUNT(*) FROM documents WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL);", (project_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM documents WHERE (status = 'Active' OR status IS NULL);")
        total = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'documents': documents, 'total': total})
    except Exception as e:
        logger.error(f"KB documents error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/documents/<string:doc_id>', methods=['GET'])
def kb_document_detail(doc_id):
    """ดูรายละเอียดเอกสาร รวมถึง content และ chunks"""
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT d.doc_id, d.project_id, d.doc_category, d.doc_type, d.original_filename,
                   d.full_markdown_content, d.is_golden_data, d.file_hash, d.version, d.status, d.created_at,
                   p.project_name
            FROM documents d
            LEFT JOIN projects p ON d.project_id = p.project_id
            WHERE d.doc_id = %s;
            """,
            (doc_id,)
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'ไม่พบเอกสาร'}), 404

        doc = {
            'id': str(row[0]) if row[0] else None,
            'project_id': str(row[1]) if row[1] else None,
            'doc_category': row[2],
            'doc_type': row[3],
            'filename': row[4],
            'content': row[5],
            'is_golden_data': row[6],
            'file_hash': row[7],
            'version': row[8],
            'status': row[9],
            'created_at': row[10].isoformat() if row[10] else None,
            'project_name': row[11]
        }

        # Check total pages in kb_images directory
        total_pages = 0
        img_dir = KB_IMAGES_FOLDER / doc['id']
        if img_dir.exists():
            import glob
            total_pages = len(glob.glob(str(img_dir / 'page_*.jpg')))
        doc['total_pages'] = total_pages

        # Fetch chunks
        cursor.execute(
            "SELECT chunk_id, chunk_text FROM document_chunks WHERE doc_id = %s ORDER BY ctid ASC;",
            (doc_id,)
        )
        chunks = [{'id': r[0], 'text': r[1]} for r in cursor.fetchall()]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'document': doc, 'chunks': chunks})
    except Exception as e:
        logger.error(f"KB document detail error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/search', methods=['GET'])
def kb_search():
    """
    ค้นหาเอกสารด้วย Unified Hybrid Search (Vector Similarity + Keyword Boost + Golden Data Boost)
    Query: ?q=<text>&project_id=<id>&doc_type=<cat>&top_k=10
    """
    query_text = request.args.get('q', '').strip()
    project_id = request.args.get('project_id', type=str)
    doc_type = request.args.get('doc_type', type=str)
    top_k = max(1, min(50, request.args.get('top_k', 10, type=int)))

    if not query_text:
        return jsonify({'error': 'กรุณาระบุคำค้นหา (q)'}), 400

    try:
        from db_ingestion import search_knowledge_base
        results = search_knowledge_base(
            query_text=query_text,
            doc_type=doc_type if doc_type else None,
            top_k=top_k,
            project_id=project_id if project_id else None,
            hybrid=True
        )
        return jsonify({'success': True, 'results': results, 'query': query_text})
    except Exception as e:
        logger.error(f"KB search error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/format_rules', methods=['GET'])
def get_format_rules_route():
    """ดึงกฎการจัดรูปแบบทั้งหมด"""
    try:
        rules = load_format_rules()
        return jsonify({'success': True, 'rules': rules})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/format_rules', methods=['POST'])
def save_format_rules_route():
    """บันทึกกฎการจัดรูปแบบทั้งหมด"""
    try:
        data = request.get_json()
        if not data or 'rules' not in data:
            return jsonify({'error': 'กรุณาส่ง JSON { "rules": [...] }'}), 400
        
        success = save_format_rules(data['rules'])
        if success:
            return jsonify({'success': True, 'message': 'บันทึกกฎการจัดรูปแบบสำเร็จ'})
        else:
            return jsonify({'error': 'ไม่สามารถบันทึกกฎได้'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/ingest', methods=['POST'])
def kb_ingest():
    """บันทึกเอกสารเข้า Project (Knowledge Base) ด้วยตัวเอง"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    filename = data.get('filename')
    markdown_text = data.get('markdown_text')
    project_id = data.get('project_id')
    doc_category = data.get('doc_category', 'Reference')
    doc_type = data.get('doc_type', 'PDF')
    is_golden_data = data.get('is_golden_data', False)

    session_id = data.get('session_id')

    if not filename or not markdown_text or not project_id:
        return jsonify({'error': 'กรุณาระบุ filename, markdown_text, และ project_id'}), 400

    auth_err = _check_kb_write_permission(project_id=project_id, allow_ocr=True)
    if auth_err:
        return auth_err

    try:
        from db_ingestion import ingest_markdown_document
        import shutil
        
        logger.info(f"Manual DB ingestion for {filename} (Project ID: {project_id})...")
        success, msg_or_err = ingest_markdown_document(
            filename=filename,
            markdown_text=markdown_text.strip(),
            project_id=project_id,
            doc_category=doc_category,
            doc_type=doc_type,
            is_golden_data=is_golden_data
        )
        if success:
            doc_id = msg_or_err
            
            # If session_id provided, copy images to permanent storage
            if session_id:
                src_dir = CACHE_FOLDER / session_id
                if src_dir.exists():
                    dest_dir = KB_IMAGES_FOLDER / doc_id
                    dest_dir.mkdir(exist_ok=True, parents=True)
                    for item in src_dir.glob("page_*.jpg"):
                        shutil.copy2(item, dest_dir / item.name)
                        
            return jsonify({'success': True, 'message': 'บันทึกเอกสารเข้าโครงการสำเร็จ', 'doc_id': doc_id})
        else:
            return jsonify({'error': f'การบันทึกเอกสารไม่สำเร็จ: {msg_or_err}'}), 500
    except Exception as e:
        logger.error(f"KB ingest error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/documents/<string:doc_id>', methods=['PUT'])
def kb_update_document(doc_id):
    """แก้ไขเนื้อหาเอกสาร (Markdown), หมวดหมู่, ชื่อเอกสาร และทำการ Chunk/Embed ใหม่"""
    auth_err = _check_kb_write_permission()
    if auth_err:
        return auth_err
    try:
        data = request.get_json() or {}
        new_markdown = data.get('markdown_text')
        new_category = data.get('doc_category')
        new_filename = data.get('filename')
        new_is_golden = data.get('is_golden_data')

        from db_ingestion import update_markdown_document
        success, msg = update_markdown_document(
            doc_id=doc_id, 
            new_markdown_text=new_markdown,
            new_category=new_category,
            new_filename=new_filename,
            new_is_golden=new_is_golden
        )
        if success:
            return jsonify({'success': True, 'message': 'อัปเดตเอกสารและ Chunks สำเร็จ'})
        else:
            return jsonify({'error': f'การอัปเดตไม่สำเร็จ: {msg}'}), 500
    except Exception as e:
        logger.error(f"Error updating doc {doc_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/view/<string:doc_id>/<int:page_num>')
def kb_view_page(doc_id, page_num):
    """Serve permanent page image from Knowledge Base"""
    from werkzeug.utils import secure_filename
    doc_id = secure_filename(doc_id)
    directory = KB_IMAGES_FOLDER / doc_id
    filename = f"page_{page_num}.jpg"
    full_path = directory / filename
    
    if not full_path.exists():
        return "Image not found", 404
        
    return send_from_directory(str(directory), filename)


@bp.route('/api/kb/documents/<string:doc_id>', methods=['DELETE'])
def kb_delete_document(doc_id):
    """ลบเอกสารออกจาก Knowledge Base"""
    auth_err = _check_kb_write_permission()
    if auth_err:
        return auth_err
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if doc exists
        cursor.execute("SELECT doc_id FROM documents WHERE doc_id = %s;", (doc_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'ไม่พบเอกสารที่ต้องการลบ'}), 404
            
        # Delete document (CASCADE will delete chunks)
        cursor.execute("DELETE FROM documents WHERE doc_id = %s;", (doc_id,))
        conn.commit()

        # Clean up orphaned preview images folder on disk
        try:
            import shutil
            img_dir = KB_IMAGES_FOLDER / secure_filename(str(doc_id))
            if img_dir.exists() and img_dir.is_dir():
                shutil.rmtree(img_dir, ignore_errors=True)
        except Exception as clean_err:
            logger.warning(f"Failed to remove kb_images dir for doc {doc_id}: {clean_err}")
        
        return jsonify({'success': True, 'message': 'ลบเอกสารเรียบร้อยแล้ว'})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"KB delete document error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@bp.route('/api/kb/reindex', methods=['POST'])
def reindex_kb_route():
    """
    Re-indexes all active documents in a project with Heading-Aware Semantic Chunking and Contextual Breadcrumbs.
    """
    try:
        from db_ingestion import reindex_project_documents
        data = request.get_json(silent=True) or {}
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({'error': 'project_id is required'}), 400

        auth_err = _check_kb_write_permission(project_id=project_id)
        if auth_err:
            return auth_err
            
        success, res = reindex_project_documents(project_id)
        if success:
            return jsonify({'success': True, 'result': res, 'message': f"Re-indexed {res.get('documents_count', 0)} documents into {res.get('total_chunks', 0)} contextual chunks."})
        return jsonify({'error': res}), 500
    except Exception as e:
        logger.error(f"Error reindexing KB: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/semantic-search', methods=['POST'])
def semantic_search_kb_route():
    """
    Performs Hybrid Knowledge Base search with Category filters and Keyword boosting.
    """
    try:
        from db_ingestion import search_knowledge_base
        data = request.json or {}
        query = data.get('query', '')
        project_id = data.get('project_id')
        doc_type = data.get('category') or data.get('doc_type')
        top_k = int(data.get('top_k', 5))
        hybrid = bool(data.get('hybrid', True))
        
        if not query:
            return jsonify({'success': True, 'results': []})
            
        results = search_knowledge_base(
            query_text=query,
            doc_type=doc_type,
            top_k=top_k,
            project_id=project_id,
            hybrid=hybrid
        )
        return jsonify({'success': True, 'results': results, 'count': len(results)})
    except Exception as e:
        logger.error(f"Error in semantic search: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/feedback', methods=['GET', 'POST', 'OPTIONS'])
def log_kb_feedback():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200

    if request.method == 'GET':
        try:
            from db_ingestion import get_kb_feedback_memories
            doc_id = request.args.get('doc_id') or request.args.get('context_id')
            project_id = request.args.get('project_id')
            limit = request.args.get('limit', 30, type=int)
            memories = get_kb_feedback_memories(project_id=project_id, doc_id=doc_id, limit=limit)
            return jsonify({'success': True, 'memories': memories})
        except Exception as e:
            logger.error(f"Error fetching KB feedback memories: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    auth_err = _check_kb_write_permission()
    if auth_err:
        return auth_err

    try:
        from db_ingestion import save_kb_feedback_memory
        data = request.get_json(silent=True) or {}
        rating = data.get('rating', 5)
        correction = str(data.get('correction') or '').strip()
        doc_id = data.get('doc_id') or data.get('context_id')
        project_id = data.get('project_id')
        req_payload = get_request_user_payload() or {}
        created_by = req_payload.get('username') or req_payload.get('email') or 'qa_user'

        saved = save_kb_feedback_memory(
            project_id=project_id,
            doc_id=doc_id if doc_id and doc_id != 'general' else None,
            rating=rating,
            correction=correction,
            created_by=created_by
        )
        logger.info(f"Saved KB feedback memory id={saved['memory_id']} doc={saved['doc_id']} rating={saved['rating']}")

        return jsonify({
            'success': True,
            'message': 'บันทึก AI Feedback & Self-Learning Memory ลงฐานข้อมูลเรียบร้อยแล้ว',
            'memory': saved,
            'rating': saved['rating']
        })
    except Exception as e:
        logger.error(f"Error logging KB feedback: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/kb/feedback/<string:memory_id>', methods=['DELETE', 'OPTIONS'])
def delete_kb_feedback_route(memory_id):
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    auth_err = _check_kb_write_permission()
    if auth_err:
        return auth_err
    try:
        from db_ingestion import delete_kb_feedback_memory
        deleted = delete_kb_feedback_memory(memory_id)
        if not deleted:
            return jsonify({'error': 'ไม่พบรายการ Memory ที่ต้องการลบ'}), 404
        return jsonify({'success': True, 'message': 'ลบ AI Memory เรียบร้อยแล้ว'})
    except Exception as e:
        logger.error(f"Error deleting KB feedback {memory_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

