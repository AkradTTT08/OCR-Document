"""QA Consult SSE audit pipeline, MCP submit, page image viewer, email/Excel reports, transactions, and groups."""
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
bp = Blueprint('qa_consult', __name__)

from core.config import MASTER_DOC_TYPES, UPLOAD_FOLDER, _QA_CONSULT_PAGES_DIR
from core.auth import get_request_user
from core.qa_helpers import (
    _attach_finding_pages,
    _build_page_issue_summary,
    _filter_false_future_be_date_findings,
    _is_false_future_be_date_claim,
    _split_text_into_logical_pages,
)
from db_ingestion import search_knowledge_base
from email_service import send_qa_report
from excel_report import generate_qa_excel
from ocr_engine import ocr_pdf_bytes
from routes.exit_criteria import evaluate_document_exit_criteria

_ACTIVE_QA_CONSULT_CANCELS = {}

@bp.route('/api/doc_types', methods=['GET'])
def get_doc_types():
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        project_id = request.args.get('project_id')
        if project_id:
            cursor.execute("SELECT DISTINCT doc_category FROM documents WHERE doc_category IS NOT NULL AND doc_category != '' AND project_id = %s;", (project_id,))
        else:
            cursor.execute("SELECT DISTINCT doc_category FROM documents WHERE doc_category IS NOT NULL AND doc_category != '';")
            
        rows = cursor.fetchall()
        db_categories = [r[0] for r in rows if r[0]]
        
        combined = list(MASTER_DOC_TYPES)
        for cat in db_categories:
            if cat not in combined:
                combined.append(cat)
        return jsonify(combined)
    except Exception as e:
        logger.error(f"Error fetching doc categories: {e}")
        return jsonify(MASTER_DOC_TYPES)
    finally:
        if conn: conn.close()


@bp.route('/api/mcp/submit_document', methods=['POST', 'OPTIONS'])
def mcp_submit_document():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        if not data:
            return jsonify({"status": "ERROR", "message": "Missing JSON body"}), 400
            
        doc_content = data.get('document_content')
        doc_type = data.get('document_type') or data.get('doc_type') or 'ALL'
        skill_id_raw = data.get('ai_skill') or data.get('skill_id')
        target_email = data.get('target_email') or data.get('email')
        session_id = data.get('session_id')
        raw_project_id = data.get('project_id')
        group_name = data.get('group_name') or 'General'
        group_type = data.get('group_type') or 'Project Plan'
        filename = data.get('filename') or 'MCP_Automated_Evaluation.md'
        
        if not doc_content:
            return jsonify({"status": "ERROR", "message": "document_content is required"}), 400
            
        from db_ingestion import get_db_connection, get_projects, save_qa_transaction
        
        # Resolve Project
        resolved_pid = None
        project_name = "General Project"
        project_code = ""
        if raw_project_id:
            try:
                projects = get_projects()
                clean_target = str(raw_project_id).strip().lower()
                for p in projects:
                    p_id = str(p.get("id") or p.get("project_id", "")).strip().lower()
                    p_code = str(p.get("project_code", "")).strip().lower()
                    p_name = str(p.get("name") or p.get("project_name", "")).strip().lower()
                    if clean_target in [p_id, p_code, p_name]:
                        resolved_pid = str(p.get("id") or p.get("project_id"))
                        project_name = p.get("name") or p.get("project_name") or "Project"
                        project_code = p.get("project_code") or ""
                        break
                if not resolved_pid:
                    resolved_pid = str(raw_project_id)
            except Exception as p_err:
                logger.warning(f"Project resolution note in mcp submit: {p_err}")
                resolved_pid = str(raw_project_id)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Fetch Exit Criteria Template and max_loops
        cur.execute("SELECT template_id, max_loops FROM exit_criteria_templates WHERE is_active = TRUE AND (doc_type = %s OR doc_type = 'ALL') ORDER BY CASE WHEN doc_type = %s THEN 1 ELSE 2 END, created_at DESC LIMIT 1;", (doc_type, doc_type))
        template_row = cur.fetchone()
        
        template_id = None
        max_loops = 3
        if template_row:
            template_id, max_loops_db = template_row
            max_loops = max_loops_db if max_loops_db else 3
            
        # 2. Track Session and Circuit Breaker
        attempt_count = 1
        is_new_session = True
        
        if session_id:
            cur.execute("SELECT attempt_count FROM agent_evaluation_sessions WHERE session_id = %s", (session_id,))
            session_row = cur.fetchone()
            if session_row:
                attempt_count = session_row[0] + 1
                cur.execute("UPDATE agent_evaluation_sessions SET attempt_count = %s, updated_at = NOW() WHERE session_id = %s", (attempt_count, session_id))
                is_new_session = False
                
        if is_new_session:
            skill_uuid = None
            if skill_id_raw:
                try:
                    import uuid
                    uuid.UUID(skill_id_raw)
                    skill_uuid = skill_id_raw
                except:
                    cur.execute("SELECT skill_id FROM agent_skills WHERE skill_name ILIKE %s LIMIT 1", (skill_id_raw,))
                    row = cur.fetchone()
                    if row: skill_uuid = row[0]
            
            cur.execute("""
                INSERT INTO agent_evaluation_sessions (target_email, document_type, skill_id, attempt_count) 
                VALUES (%s, %s, %s, %s) RETURNING session_id
            """, (target_email, doc_type, skill_uuid, attempt_count))
            session_id = str(cur.fetchone()[0])
            
        conn.commit()
        cur.close()
        conn.close()
        
        # 3. Check Circuit Breaker hit
        if attempt_count > max_loops:
            return jsonify({
                "status": "REJECTED",
                "session_id": session_id,
                "circuit_breaker_hit": True,
                "failed_criteria": [],
                "recommendation": f"Circuit breaker hit. Max loops ({max_loops}) exceeded. Please review the document manually."
            }), 200
            
        # 4. Evaluate document against Exit Criteria (Scoped by project if available)
        eval_result = evaluate_document_exit_criteria(doc_content, doc_type=doc_type, project_id=resolved_pid, qa_findings=[])
        
        if not eval_result:
            return jsonify({"status": "ERROR", "message": "Evaluation failed internally."}), 500
            
        final_status = eval_result.get('status') # 'PASSED', 'CONDITIONAL_PASSED', 'REJECTED'
        failed_criteria_list = []
        
        for item in eval_result.get('items', []):
            if item.get('status') == 'FAIL':
                failed_criteria_list.append(f"ข้อ {item.get('item_code')}: {item.get('question_text')} - {item.get('remarks')}")
                
        recommendation = eval_result.get('summary_remarks', '')
        if final_status == 'REJECTED':
            recommendation += "\nกรุณาแก้ไขเอกสารในจุดที่ไม่ผ่านเกณฑ์ และส่งเข้ามาตรวจใหม่"
        
        # 5. Save QA transaction into QA Database
        transaction_id = None
        if resolved_pid:
            try:
                qa_report_md = f"# MCP Automated Evaluation Report\n\n**Status:** {final_status}\n**Project:** {project_name} ({project_code})\n**Group:** {group_name}\n**Document Type:** {doc_type}\n\n### Recommendation\n{recommendation}\n\n### Exit Criteria Checklist Items\n"
                for item in eval_result.get('items', []):
                    status_icon = "✅ PASS" if item.get('status') == 'PASS' else ("❌ FAIL" if item.get('status') == 'FAIL' else "⚪ N/A")
                    qa_report_md += f"- **[{status_icon}]** ข้อ {item.get('item_code')}: {item.get('question_text')} (ผล: {item.get('remarks') or '-'})\n"
                    
                transaction_id = save_qa_transaction(
                    project_id=resolved_pid,
                    group_name=group_name,
                    group_type=group_type,
                    filename=filename,
                    doc_type=doc_type,
                    extracted_text=doc_content[:250000],
                    qa_report=qa_report_md,
                    total_pages=1,
                    email=target_email,
                    qa_findings=[],
                    exit_criteria_eval=eval_result,
                    project_code=project_code,
                    project_name=project_name
                )
            except Exception as save_err:
                logger.warning(f"Could not save QA transaction in mcp submit: {save_err}")
        
        # 6. Trigger email notification
        if target_email:
            try:
                from email_service import send_qa_report
                report_content = f"Final Status: {final_status}\n\nRemarks: {recommendation}\n\nFailed Items:\n"
                for i, fail in enumerate(failed_criteria_list, 1):
                    report_content += f"{i}. {fail}\n"
                send_qa_report(target_email, doc_type, filename, report_content, exit_criteria_eval=eval_result)
            except Exception as email_err:
                logger.error(f"Failed to send email inside mcp_submit_document: {email_err}")
                
        return jsonify({
            "status": "PASS" if final_status in ['PASSED', 'CONDITIONAL_PASSED'] else "REJECTED",
            "session_id": session_id,
            "project_id": resolved_pid,
            "project_code": project_code,
            "project_name": project_name,
            "group_name": group_name,
            "group_type": group_type,
            "doc_type": doc_type,
            "transaction_id": transaction_id,
            "circuit_breaker_hit": False,
            "failed_criteria": failed_criteria_list,
            "recommendation": recommendation,
            "attempt_count": attempt_count,
            "max_loops": max_loops
        }), 200

    except Exception as e:
        logger.error(f"Error in MCP submit_document: {e}", exc_info=True)
        return jsonify({"status": "ERROR", "message": str(e)}), 500


@bp.route('/api/qa_consult/page_image/<string:scan_id>/<int:page_num>', methods=['GET'])
def qa_consult_page_image(scan_id, page_num):
    """Serve saved preview JPEG image for a QA Consult document page."""
    import re
    safe_id = re.sub(r'[^a-zA-Z0-9_\-]', '', str(scan_id or ''))
    if not safe_id or page_num < 1:
        return jsonify({'error': 'Invalid parameters'}), 400
    img_path = os.path.join(_QA_CONSULT_PAGES_DIR, safe_id, f"page_{page_num}.jpg")
    if not os.path.exists(img_path):
        return jsonify({'error': 'Page image not found'}), 404
    return send_file(img_path, mimetype='image/jpeg')


@bp.route('/api/qa_consult/transaction/<string:transaction_id>/pages', methods=['GET'])
def qa_consult_transaction_pages(transaction_id):
    """Load extracted pages + page-attributed findings for a saved QA Consult transaction."""
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, filename, extracted_text, qa_findings, total_pages
            FROM qa_transactions
            WHERE id::text = %s
            LIMIT 1
        """, (str(transaction_id),))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return jsonify({'success': False, 'error': 'Transaction not found'}), 404

        tx_id, fname, extracted_text, qa_findings, total_pages = row
        tx_id_str = str(tx_id)
        pages_list = _split_text_into_logical_pages(extracted_text or "", filename=fname or "")
        img_dir = os.path.join(_QA_CONSULT_PAGES_DIR, tx_id_str)
        for p in pages_list:
            p_num = int(p["page_number"])
            has_img = os.path.exists(os.path.join(img_dir, f"page_{p_num}.jpg"))
            p["has_image"] = has_img
            p["image_url"] = f"/api/qa_consult/page_image/{tx_id_str}/{p_num}" if has_img else None

        findings_list = qa_findings if isinstance(qa_findings, list) else []
        enriched_findings = _attach_finding_pages(findings_list, pages_list)
        summary = _build_page_issue_summary(enriched_findings, pages_list)
        return jsonify({
            'success': True,
            'transaction_id': tx_id_str,
            'pages': pages_list,
            'qa_findings': enriched_findings,
            'page_issue_summary': summary
        }), 200
    except Exception as e:
        logger.error(f"Error loading QA transaction pages for {transaction_id}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


class _QAConsultCancelledError(Exception):
    pass


@bp.route('/api/qa_consult/cancel', methods=['POST', 'OPTIONS'])
def cancel_qa_consult_scan():
    """Explicitly cancel an in-flight QA Consult document scan so background work and DB saves stop immediately."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        data = request.get_json(silent=True) or {}
        scan_id = str(data.get('scan_id') or '').strip()
        cancelled = False
        if scan_id and scan_id in _ACTIVE_QA_CONSULT_CANCELS:
            _ACTIVE_QA_CONSULT_CANCELS[scan_id].set()
            cancelled = True
            logger.info(f"QA Consult scan '{scan_id}' marked as cancelled by user.")
        elif not scan_id:
            for sid, ev in list(_ACTIVE_QA_CONSULT_CANCELS.items()):
                ev.set()
                cancelled = True
            logger.info("All active QA Consult scans marked as cancelled by user.")
        return jsonify({'success': True, 'cancelled': cancelled}), 200
    except Exception as e:
        logger.error(f"Error cancelling QA Consult scan: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/qa_consult', methods=['POST', 'OPTIONS'])
def qa_consult_api():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        file = request.files.get('file')
        doc_type_raw = request.form.get('doc_type', 'Requirement')
        email = request.form.get('email', '')
        skill_id_raw = request.form.get('skill_id', '')
        project_id = request.form.get('project_id', '')
        project_name = request.form.get('project_name', 'โครงการนี้')
        group_name_raw = request.form.get('group_name', 'General')
        import re
        group_name = re.sub(r'^\[.*?\]\s*', '', group_name_raw).strip() if group_name_raw else 'General'
        if not group_name:
            group_name = 'General'
        group_type = request.form.get('group_type', 'Project Plan')

        # parse doc_type array
        try:
            doc_type = json.loads(doc_type_raw)
        except:
            doc_type = [doc_type_raw] if doc_type_raw else []

        # parse skill_id array safely (handles JSON array, comma-separated IDs/names, or single string)
        skill_ids = []
        if skill_id_raw and str(skill_id_raw).strip() not in ("undefined", "null", "[]"):
            try:
                parsed_skills = json.loads(skill_id_raw)
                if isinstance(parsed_skills, list):
                    skill_ids = [str(s).strip() for s in parsed_skills if s and str(s).strip() not in ("undefined", "null")]
                elif parsed_skills:
                    skill_ids = [str(parsed_skills).strip()]
            except Exception:
                skill_ids = [s.strip() for s in str(skill_id_raw).split(',') if s.strip() and s.strip() not in ("undefined", "null")]

        if not file or not email:
            return jsonify({'type': 'error', 'message': 'Missing file or email'}), 400

        skill_instructions = ""
        if skill_ids:
            conn = None
            cursor = None
            try:
                from db_ingestion import get_db_connection
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT skill_name, target_doc_type, markdown_instructions
                    FROM agent_skills
                    WHERE (skill_id::text = ANY(%s) OR skill_name = ANY(%s))
                      AND COALESCE(is_active, TRUE) = TRUE
                    """,
                    (skill_ids, skill_ids)
                )
                rows = cursor.fetchall()
                if rows:
                    for r in rows:
                        skill_instructions += f"### Skill: {r[0]} ({r[1] or 'General'})\n{r[2]}\n\n"
                    logger.info(f"QA Consult injected {len(rows)} active AI Skill(s): {[r[0] for r in rows]}")
                else:
                    logger.warning(f"No active AI Skills matched requested IDs: {skill_ids}")
            except Exception as e:
                logger.error(f"Failed to fetch skill: {e}", exc_info=True)
            finally:
                if cursor: cursor.close()
                if conn: conn.close()

        # Read file bytes before background worker starts to avoid I/O on closed file
        raw_original_filename = (getattr(file, 'filename', None) or 'document.pdf').strip()
        _, raw_ext = os.path.splitext(raw_original_filename)
        raw_ext_lower = (raw_ext or '.pdf').lower()
        safe_base = secure_filename(raw_original_filename)
        if not safe_base or not os.path.splitext(safe_base)[1]:
            doc_filename = f"document{raw_ext_lower}"
        else:
            doc_filename = safe_base
        file_bytes = file.read()
        req_user = get_request_user() or request.form.get('username')
        source_generated_doc_id = (request.form.get('source_generated_doc_id') or '').strip() or None
        client_scan_id = (request.form.get('scan_id') or '').strip() or f"qascan-{int(time.time() * 1000)}"

        from excel_extractor import is_excel_file, extract_text_from_excel_bytes
        file_is_excel = is_excel_file(raw_original_filename) or is_excel_file(doc_filename)
        file_is_markdown = raw_ext_lower in ('.md', '.txt')

        import queue
        import threading
        msg_queue = queue.Queue()
        cancel_event = threading.Event()
        _ACTIVE_QA_CONSULT_CANCELS[client_scan_id] = cancel_event

        def _ensure_not_cancelled():
            if cancel_event.is_set():
                raise _QAConsultCancelledError("ผู้ใช้สั่งหยุดการสแกนเอกสาร")

        def run_qa_worker():
            nonlocal doc_type
            import uuid as _uuid
            import shutil as _shutil
            temp_scan_key = f"tmp_{_uuid.uuid4().hex[:12]}"
            temp_img_dir = os.path.join(_QA_CONSULT_PAGES_DIR, temp_scan_key)
            pages_list = []
            try:
                _ensure_not_cancelled()
                if file_is_excel:
                    msg_queue.put({'type': 'progress', 'pct': 10, 'message': 'กำลังวิเคราะห์และแปลงข้อมูลจากเอกสาร Excel (Sheets & Test Cases)...' })
                    try:
                        raw_excel_text, total_pages = extract_text_from_excel_bytes(file_bytes, filename=raw_original_filename)
                        pages_list = _split_text_into_logical_pages(raw_excel_text, filename=raw_original_filename)
                        if pages_list:
                            extracted_text = "\n\n".join(f"--- [หน้า {p['page_number']}: {p['label']}] ---\n{p['text']}" for p in pages_list)
                            total_pages = len(pages_list)
                        else:
                            extracted_text = raw_excel_text
                    except Exception as ex_err:
                        logger.error(f"Failed to parse Excel file: {ex_err}", exc_info=True)
                        msg_queue.put({'type': 'error', 'message': f'ไม่สามารถอ่านไฟล์ Excel ได้: {str(ex_err)}'})
                        msg_queue.put(None)
                        return
                elif file_is_markdown:
                    msg_queue.put({'type': 'progress', 'pct': 10, 'message': 'กำลังอ่านเนื้อหาเอกสาร Markdown / Text...' })
                    try:
                        raw_md_text = file_bytes.decode('utf-8', errors='replace')
                        pages_list = _split_text_into_logical_pages(raw_md_text, filename=raw_original_filename)
                        if pages_list:
                            extracted_text = "\n\n".join(f"--- [หน้า {p['page_number']}] ---\n{p['text']}" for p in pages_list)
                            total_pages = len(pages_list)
                        else:
                            extracted_text = raw_md_text
                            total_pages = 1
                    except Exception as md_err:
                        logger.error(f"Failed to read Markdown/Text file: {md_err}", exc_info=True)
                        msg_queue.put({'type': 'error', 'message': f'ไม่สามารถอ่านไฟล์ข้อความได้: {str(md_err)}'})
                        msg_queue.put(None)
                        return
                else:
                    msg_queue.put({'type': 'progress', 'pct': 10, 'message': 'กำลังวิเคราะห์ข้อความและสร้างภาพตัวอย่างหน้าเอกสาร PDF...' })
                    from ocr_engine import ocr_pdf_bytes
                    def _pdf_progress_cb(p_curr, p_tot, stage, elapsed):
                        if cancel_event.is_set():
                            raise _QAConsultCancelledError("ผู้ใช้สั่งหยุดการสแกนเอกสาร")
                        pct_val = 10 + int((p_curr / max(p_tot, 1)) * 28)
                        msg_queue.put({'type': 'progress', 'pct': min(pct_val, 38), 'message': f'กำลังอ่านและสร้างภาพหน้าเอกสาร PDF ({p_curr}/{p_tot})...'})
                    ocr_results = ocr_pdf_bytes(
                        file_bytes,
                        filename=doc_filename,
                        progress_callback=_pdf_progress_cb,
                        save_images_dir=temp_img_dir,
                        prefer_native_text=True,
                        max_workers=3
                    )
                    extracted_chunks = []
                    total_pages = len(ocr_results)
                    for idx_p, page in enumerate(ocr_results):
                        p_num = int(page.get('page_number') or (idx_p + 1))
                        p_text = (page.get('text') or '').strip() if ('error' not in page or not page['error']) else ''
                        pages_list.append({
                            'page_number': p_num,
                            'label': f'หน้า {p_num}',
                            'text': p_text,
                            'has_image': bool(page.get('has_image'))
                        })
                        if p_text:
                            extracted_chunks.append(f"--- [หน้า {p_num}] ---\n{p_text}")
                    extracted_text = "\n\n".join(extracted_chunks)
                
                _ensure_not_cancelled()
                if not extracted_text.strip():
                    msg_queue.put({'type': 'error', 'message': 'ไม่พบเนื้อหาข้อความในเอกสารที่อัปโหลด'})
                    msg_queue.put(None)
                    return

                # Check if explicit doc_type flow is selected or auto-discovery
                is_explicit = bool(doc_type and ((isinstance(doc_type, list) and len(doc_type) > 0) or (isinstance(doc_type, str) and doc_type.strip())))

                # Auto-classify Excel files containing Test Cases if user did not specify
                if file_is_excel and not is_explicit:
                    lower_text = extracted_text.lower()
                    if any(kw in lower_text for kw in ["test id", "tc_", "test case", "test objective", "expected result", "test procedure", "วัตถุประสงค์การทดสอบ", "ขั้นตอนการทดสอบ"]):
                        doc_type = ["Test Case"]
                        is_explicit = True
                        logger.info(f"Auto-classified Excel document '{raw_original_filename}' as 'Test Case'")

                doc_type_display = ', '.join(doc_type) if isinstance(doc_type, list) and doc_type else (doc_type if isinstance(doc_type, str) and doc_type else "")

                # 2. Multi-Source Vector Search, Structured Requirements & Project MD Inventory
                from db_ingestion import (
                    search_knowledge_base,
                    get_latest_qa_transaction,
                    save_qa_transaction,
                    get_project_markdown_documents_summary,
                    get_db_connection as _get_kb_conn
                )
                
                available_md_docs = []
                structured_reqs_context = ""
                if project_id:
                    try:
                        available_md_docs = get_project_markdown_documents_summary(project_id)
                    except Exception as e:
                        logger.error(f"Failed to fetch available project MD docs: {e}")
                    try:
                        _rconn = _get_kb_conn()
                        _rcur = _rconn.cursor()
                        _rcur.execute("""
                            SELECT req_code, title, status, description, expected_results
                            FROM structured_requirements
                            WHERE project_id = %s::uuid
                            ORDER BY req_code ASC
                            LIMIT 60
                        """, (project_id,))
                        _rrows = _rcur.fetchall()
                        if _rrows:
                            structured_reqs_context = "=== รายการ Requirement มาตรฐานของโครงการ (Structured Requirements Baseline) ===\n"
                            for rr in _rrows:
                                r_code, r_title, r_status, r_desc, r_expected = rr
                                exp_short = f" | Expected: {str(r_expected)[:180]}" if r_expected else ""
                                structured_reqs_context += f"- [{r_code}] ({r_status or 'Active'}) {r_title}: {str(r_desc or '')[:220]}{exp_short}\n"
                            structured_reqs_context += "\n"
                        _rcur.close()
                        _rconn.close()
                    except Exception as req_err:
                        logger.warning(f"Failed to load structured_requirements for QA Consult: {req_err}")

                # Sample multiple slices of the document (header/scope, middle core content, tail/appendix)
                text_len = len(extracted_text)
                mid_start = max(0, (text_len // 2) - 1000)
                tail_start = max(0, text_len - 2000)
                search_samples = [extracted_text[:2000]]
                if text_len > 3500:
                    search_samples.append(extracted_text[mid_start:mid_start + 2000])
                if text_len > 7000:
                    search_samples.append(extracted_text[tail_start:])
                combined_query = "\n".join(search_samples)[:4500]

                kb_results = []
                seen_chunks = set()
                def _add_kb_rows(rows):
                    for r in (rows or []):
                        key = (r.get('filename', ''), (r.get('chunk_text') or '')[:160])
                        if key not in seen_chunks:
                            seen_chunks.add(key)
                            kb_results.append(r)

                if is_explicit:
                    msg_queue.put({'type': 'progress', 'pct': 40, 'message': f'กำลังสืบค้นฐานข้อมูลตามประเภทเอกสาร [{doc_type_display}] พร้อม Baseline SRS/Requirement ของโครงการ...' })
                    # 1) Search matching doc_type
                    _add_kb_rows(search_knowledge_base(combined_query, doc_type=doc_type, top_k=5, project_id=project_id if project_id else None))
                    # 2) Always include project baseline documents (SRS / Requirement / TOR / System Design) for cross-checking accuracy
                    _add_kb_rows(search_knowledge_base(combined_query, doc_type=None, top_k=6, project_id=project_id if project_id else None))
                else:
                    msg_queue.put({'type': 'progress', 'pct': 40, 'message': 'กำลังสำรวจเอกสาร Markdown ในโครงการและค้นหาข้อมูลอ้างอิงอัตโนมัติ...' })
                    _add_kb_rows(search_knowledge_base(combined_query, doc_type=None, top_k=10, project_id=project_id if project_id else None))
                
                diagram_context = ""
                if project_id:
                    try:
                        from agent_7_flow_analyzer import get_diagram_context_for_agents
                        diagram_context = get_diagram_context_for_agents(project_id, include_mockups=True, include_matrix=True)
                    except Exception as diag_err:
                        logger.warning(f"Failed to load QA Analysis Diagram context for QA Consult: {diag_err}")

                kb_context = structured_reqs_context
                if project_id:
                    try:
                        from db_ingestion import format_kb_feedback_memory_context
                        feedback_memory_ctx = format_kb_feedback_memory_context(project_id, limit=12)
                        if feedback_memory_ctx:
                            kb_context += "\n" + feedback_memory_ctx + "\n"
                    except Exception as fm_err:
                        logger.warning(f"Failed to load KB feedback memory for QA Consult: {fm_err}")
                if diagram_context:
                    kb_context += diagram_context + "\n"
                for res in kb_results[:12]:
                    golden_mark = " | Golden Data" if res.get('is_golden_data') else ""
                    cat_label = res.get('doc_category') or res.get('doc_type', '')
                    kb_context += f"[Source: {res['filename']} | Category: {cat_label}{golden_mark}]\n{res['chunk_text']}\n\n"
                
                # Fetch previous transaction if exists
                prev_transaction = None
                original_filename = raw_original_filename or 'document.pdf'
                if project_id:
                    try:
                        prev_transaction = get_latest_qa_transaction(project_id, filename=original_filename, group_name=group_name)
                    except Exception as e:
                        logger.error(f"Failed to fetch previous transaction: {e}")

                _ensure_not_cancelled()
                msg_queue.put({'type': 'progress', 'pct': 70, 'message': 'กำลังใช้ AI วิเคราะห์และเปรียบเทียบข้อมูล...' })
                
                # 3. Analyze with Multi-Agent Pipeline
                try:
                    from orchestrator.state import QAState
                    from orchestrator.pipeline import run_qa_consult
                except ImportError:
                    from backend.orchestrator.state import QAState
                    from backend.orchestrator.pipeline import run_qa_consult
                
                prev_report_context = ""
                if prev_transaction:
                    prev_findings_text = ""
                    if prev_transaction.get('qa_findings'):
                        prev_findings_text = "\n### รายการประเด็นที่พบในรอบก่อนหน้า:\n" + "\n".join([
                            f"- [{f.get('severity','Info')}] {f.get('issue','')} (ข้อเสนอแนะ: {f.get('recommendation','-')})"
                            for f in (prev_transaction.get('qa_findings') or [])[:10]
                        ])
                    prev_report_context = f"""
=== ประวัติการตรวจสอบครั้งก่อนหน้าในกลุ่มนี้ (Previous QA Audit in Group '{group_name}') ===
(ใช้อ้างอิงเพื่อตรวจสอบว่าผู้ใช้ได้ปรับปรุงแก้ไขตามข้อเสนอแนะเดิมครบถ้วน 100% หรือไม่ หากแก้ไขแล้วให้ระบุชัดเจนว่าปัญหาเดิมได้รับการแก้ไขเรียบร้อยแล้ว)
{prev_findings_text}

รายงานผลรอบก่อนหน้า:
{prev_transaction['qa_report']}
"""
                
                instruction = "กรุณาวิเคราะห์และจัดทำรายงาน QA Audit Report อย่างละเอียด:\n\n"
                
                if is_explicit:
                    instruction += f"=== โหมดการตรวจสอบ: กำหนดประเภทเอกสารชัดเจน (Explicit Flow Mode) ===\n"
                    instruction += f"ผู้ใช้ระบุประเภทเอกสารเป้าหมายเป็น: '{doc_type_display}'\n"
                    instruction += f"ให้ AI ตรวจสอบและประเมินเจาะจงตามมาตรฐานและ Lifecycle/Flow การทำงานของเอกสารประเภทนี้โดยเฉพาะ เพื่อความแม่นยำสูงสุด\n\n"
                else:
                    instruction += f"=== โหมดการตรวจสอบ: ตรวจสอบและเลือกเอกสาร MD ในโครงการอัตโนมัติ (Autonomous Project MD Discovery Mode) ===\n"
                    instruction += f"ผู้ใช้ไม่ได้ระบุประเภทเอกสารเจาะจง ให้ AI Agent ใช้ความฉลาดในการวินิจฉัย:\n"
                    instruction += f"1. วิเคราะห์เนื้อหาของ 'เอกสารที่อัปโหลด' เพื่อระบุว่าคือเอกสารประเภทใด (Detected Document Type)\n"
                    if available_md_docs:
                        instruction += f"2. รายการเอกสาร Markdown (MD) ที่มีอยู่ในโครงการนี้ ({len(available_md_docs)} รายการ):\n"
                        for idx, d in enumerate(available_md_docs, 1):
                            golden_tag = " [Golden Data]" if d.get('is_golden_data') else ""
                            instruction += f"   - {idx}. {d['filename']}{golden_tag} (หมวดหมู่: {d['category']}, ประเภท: {d['doc_type']})\n"
                            if d.get('preview'):
                                instruction += f"     เนื้อหาโดยสังเขป: {d['preview'][:120]}...\n"
                        instruction += f"3. วินิจฉัยและระบุอย่างชัดเจนว่า 'ต้องใช้เอกสาร MD ใดบ้างในโครงการ' มาเป็นคู่เทียบในการ Cross-check ตรวจสอบความถูกต้องและสมบูรณ์ พร้อมระบุเหตุผลในการเลือก\n\n"
                    else:
                        instruction += f"2. พิจารณาโครงสร้างและมาตรฐานที่ควรมีของเอกสารประเภทนี้\n\n"

                instruction += "รายละเอียดโครงสร้างหัวข้อที่ต้องจัดทำในรายงาน (จัดเป็นหัวข้อชัดเจนและระบุหมายเลขหน้าเอกสารทุกจุด):\n"
                if not is_explicit:
                    instruction += "## 0. ข้อมูลการจำแนกอัตโนมัติ (Autonomous Classification)\n"
                    instruction += "   - ประเภทเอกสารที่ตรวจพบ (Detected Document Type)\n"
                    instruction += "   - เอกสาร MD ในโครงการที่เลือกมาใช้ตรวจสอบ (Cross-referenced MD Documents in Project) พร้อมเหตุผล\n"
                instruction += "## สรุปภาพรวมประเด็นแยกตามหมายเลขหน้า (Page-by-Page Summary)\n"
                instruction += "   - สรุปเป็นหัวข้อย่อยเรียงตามหมายเลขหน้า (`หน้า 1`, `หน้า 2`, ...) ว่าแต่ละหน้าพบข้อผิดพลาดกี่ข้อและอยู่ตรงหัวข้อ/ตารางใด เช่น:\n"
                instruction += "     * **[หน้า 1 | ตาราง Document Control]**: สรุปประเด็นที่ต้องแก้ไขในหน้านี้\n"
                instruction += "     * **[หน้า 3 | หัวข้อ 2.2 ตาราง Test Case แถว TC-004]**: สรุปประเด็นที่ต้องแก้ไขในหน้านี้\n"
                instruction += "## 1. ความสอดคล้อง (Conformity)\n"
                instruction += "   - ระบุหัวข้อและ `[หน้า N]` ของเอกสารที่สอดคล้องกับมาตรฐานและเอกสารอ้างอิงในโครงการ\n"
                instruction += "## 2. จุดที่พบข้อขัดแย้ง หรือข้อผิดพลาด (Discrepancies / Errors)\n"
                instruction += "   - แยกเป็นหัวข้อย่อยชัดเจน ทุกข้อต้องขึ้นต้นด้วย **`[หน้า N | ตำแหน่งชัดเจน]`** พร้อมระบุ **ข้อความที่ผิดพลาดในเอกสาร** (คัดลอกตรงตัวใน \"...\") และ **สิ่งที่ควรเป็น**\n"
                instruction += "## 3. สิ่งที่ขาดหายไป (Missing Information)\n"
                instruction += "   - แยกเป็นหัวข้อย่อยชัดเจน ทุกข้อต้องระบุ **`[หน้า N | หัวข้อ/ตำแหน่งที่ควรเพิ่ม]`** ห้ามเขียนแบบคลุมเครือ\n"
                if prev_transaction:
                    instruction += "## 4. การแก้ไขจากครั้งก่อน (Revision Check)\n"
                    instruction += "   - เปรียบเทียบกับประวัติการตรวจสอบครั้งก่อนว่าปัญหาเดิมได้รับการแก้ไขแล้วหรือไม่ (ระบุ `[หน้า N]` ที่ตรวจสอบ)\n"
                    instruction += "## 5. ข้อเสนอแนะแนวทางแก้ไข (Recommendations — เรียงตามหมายเลขหน้า)\n"
                    instruction += "   - เรียงลำดับคำแนะนำตามหมายเลขหน้า `หน้า 1 → หน้า N` เพื่อให้ผู้ใช้เปิดแก้ตามลำดับหน้าได้ทันที\n"
                else:
                    instruction += "## 4. ข้อเสนอแนะแนวทางแก้ไข (Recommendations — เรียงตามหมายเลขหน้า)\n"
                    instruction += "   - เรียงลำดับคำแนะนำตามหมายเลขหน้า `หน้า 1 → หน้า N` เพื่อให้ผู้ใช้เปิดแก้ตามลำดับหน้าได้ทันที\n"

                qa_state = QAState(
                    project_id=project_id or "",
                    project_name=project_name,
                    doc_type=doc_type_display if is_explicit else "ไม่ระบุ (Auto-detect / Autonomous MD Discovery)",
                    skill_instructions=skill_instructions or "",
                    kb_context=kb_context or "",
                    prev_report_context=prev_report_context,
                    original_text=extracted_text[:250000],
                    instruction=instruction
                )
                
                qa_state = run_qa_consult(qa_state)
                _ensure_not_cancelled()
                
                if qa_state.status == "failed":
                    err_raw = str(qa_state.error or "")
                    user_err = f"ไม่สามารถสร้างรายงาน QA ได้: {err_raw}"
                    if '402' in err_raw or 'prepayment credits are depleted' in err_raw.lower():
                        user_err = "เครดิต Google AI Studio (402 Prepayment Credits Depleted) ของ GOOGLE_API_KEY ปัจจุบันหมดแล้ว กรุณาเติมเครดิตที่ https://ai.studio/projects หรือเปลี่ยน GOOGLE_API_KEY ใหม่ในไฟล์ .env"
                    elif 'API_KEY_INVALID' in err_raw or '403' in err_raw:
                        user_err = f"GOOGLE_API_KEY ไม่ถูกต้องหรือไม่มีสิทธิ์ใช้งาน (403/Invalid Key): {err_raw}"
                    elif '429' in err_raw or 'RESOURCE_EXHAUSTED' in err_raw:
                        user_err = "โควต้า Gemini API (429 Rate Limit) เต็มชั่วคราว กรุณารอสักครู่ (ประมาณ 30-60 วินาที) แล้วกดสแกนใหม่อีกครั้ง"
                    logger.error(f"QA Consult Agent failed: {qa_state.error}")
                    msg_queue.put({'type': 'error', 'message': user_err})
                    msg_queue.put(None)
                    return
                
                report = qa_state.report
                
                # 3b. Parse QA findings for Exit Criteria context and web display
                from excel_report import parse_qa_report_with_ai as _parse_findings
                qa_findings = []
                try:
                    qa_findings = _parse_findings(report, original_filename)
                    qa_findings = _filter_false_future_be_date_findings(qa_findings, doc_text=extracted_text)
                    qa_findings = _attach_finding_pages(qa_findings, pages_list)
                except Exception as pf_err:
                    logger.error(f"Failed to parse QA findings: {pf_err}")

                page_issue_summary = _build_page_issue_summary(qa_findings, pages_list)

                # 4. Evaluate Exit Criteria Checklist Gate (with QA findings context)
                _ensure_not_cancelled()
                exit_criteria_eval = None
                try:
                    msg_queue.put({'type': 'progress', 'pct': 85, 'message': 'กำลังตรวจสอบเกณฑ์ Exit Criteria Review Gate...' })
                    doc_type_str = ', '.join(doc_type) if isinstance(doc_type, list) else (doc_type or '')
                    doc_type_eval = doc_type_str if doc_type_str else (group_type or 'ALL')
                    exit_criteria_eval = evaluate_document_exit_criteria(extracted_text, doc_type=doc_type_eval, project_id=project_id, qa_findings=qa_findings)
                except Exception as eval_err:
                    logger.error(f"Failed to evaluate document exit criteria: {eval_err}")

                _ensure_not_cancelled()
                # Save transaction to DB with parsed findings and exit criteria
                transaction_id = None
                try:
                    transaction_id = save_qa_transaction(
                        project_id=project_id,
                        group_name=group_name,
                        group_type=group_type,
                        filename=original_filename,
                        doc_type=', '.join(doc_type) if isinstance(doc_type, list) else doc_type,
                        extracted_text=extracted_text[:250000],
                        qa_report=report,
                        total_pages=total_pages,
                        email=email,
                        qa_findings=qa_findings,
                        exit_criteria_eval=exit_criteria_eval,
                        project_name=project_name
                    )
                except Exception as e:
                    logger.error(f"Failed to save QA transaction: {e}")

                # Persist PDF page preview images under transaction_id (or keep temp_scan_key)
                final_scan_key = str(transaction_id) if transaction_id else temp_scan_key
                if os.path.isdir(temp_img_dir):
                    final_img_dir = os.path.join(_QA_CONSULT_PAGES_DIR, final_scan_key)
                    if final_img_dir != temp_img_dir:
                        try:
                            if os.path.exists(final_img_dir):
                                _shutil.rmtree(final_img_dir, ignore_errors=True)
                            os.replace(temp_img_dir, final_img_dir)
                        except Exception as mv_err:
                            logger.warning(f"Could not move page images to {final_img_dir}: {mv_err}")
                            final_scan_key = temp_scan_key
                for p in pages_list:
                    p_num = int(p['page_number'])
                    p['image_url'] = f"/api/qa_consult/page_image/{final_scan_key}/{p_num}" if p.get('has_image') else None

                # Update linked qa_generated_documents record with audit findings and status
                try:
                    if project_id:
                        from db_ingestion import get_db_connection as _gdc
                        _conn = _gdc()
                        _cur = _conn.cursor()
                        clean_fbase = original_filename.rsplit('.', 1)[0]
                        qf_count = len(qa_findings) if qa_findings else 0
                        qf_json = json.dumps(qa_findings) if qa_findings else '[]'
                        
                        has_crit_high = any((f.get('severity') or '').lower() in ['critical', 'high'] for f in (qa_findings or []))
                        gate_eval_status = (exit_criteria_eval.get('status') if exit_criteria_eval else None)
                        if has_crit_high or gate_eval_status == 'REJECTED':
                            eff_status = 'REJECTED'
                        elif gate_eval_status == 'CONDITIONAL_PASSED' or qf_count > 0:
                            eff_status = 'CONDITIONAL_PASSED'
                        else:
                            eff_status = gate_eval_status or 'PASSED'

                        score_v = (exit_criteria_eval.get('score_percentage') if exit_criteria_eval else 100)

                        if source_generated_doc_id:
                            _cur.execute("""
                                UPDATE qa_generated_documents
                                SET qa_status = %s,
                                    qa_score = %s,
                                    qa_findings_count = %s,
                                    qa_findings = %s::jsonb,
                                    last_scanned_at = NOW(),
                                    last_transaction_id = %s
                                WHERE id = %s::uuid
                            """, (eff_status, score_v, qf_count, qf_json, transaction_id, source_generated_doc_id))
                        else:
                            _cur.execute("""
                                UPDATE qa_generated_documents
                                SET qa_status = %s,
                                    qa_score = %s,
                                    qa_findings_count = %s,
                                    qa_findings = %s::jsonb,
                                    last_scanned_at = NOW(),
                                    last_transaction_id = %s
                                WHERE id = (
                                    SELECT id FROM qa_generated_documents
                                    WHERE project_id = %s::uuid
                                      AND (doc_name = %s OR doc_name = %s)
                                    ORDER BY created_at DESC
                                    LIMIT 1
                                )
                            """, (eff_status, score_v, qf_count, qf_json, transaction_id, project_id, original_filename, clean_fbase))
                        _conn.commit()
                        _cur.close()
                        _conn.close()
                        logger.info(f"Linked scan results (status={eff_status}, findings={qf_count}) to qa_generated_documents for {original_filename}")
                except Exception as up_err:
                    logger.warning(f"Could not link qa_generated_documents to scan: {up_err}")

                msg_queue.put({'type': 'progress', 'pct': 90, 'message': 'กำลังสร้าง Excel QA Report...' })

                # Generate Excel Report
                excel_download_url = ''
                try:
                    doc_type_str = ', '.join(doc_type) if isinstance(doc_type, list) else doc_type
                    p_code = ''
                    if project_id:
                        try:
                            from db_ingestion import get_db_connection as _gdc
                            _conn = _gdc()
                            _cur = _conn.cursor()
                            _cur.execute("SELECT project_code FROM projects WHERE project_id = %s", (project_id,))
                            _row = _cur.fetchone()
                            if _row: p_code = _row[0]
                            _cur.close()
                            _conn.close()
                        except:
                            pass
                    from excel_report import generate_qa_excel
                    excel_path = generate_qa_excel(
                        report_text=report,
                        filename=original_filename,
                        doc_type=doc_type_str,
                        project_code=p_code,
                        group_name=group_name,
                        group_type=group_type,
                        transaction_id=transaction_id,
                        exit_criteria_eval=exit_criteria_eval,
                        qa_findings=qa_findings
                    )
                    # Create download URL from filename
                    import os as _os
                    excel_basename = _os.path.basename(excel_path)
                    excel_download_url = f"/api/qa_report/download/{excel_basename}"
                    logger.info(f"Excel report generated: {excel_path}")
                except Exception as excel_err:
                    logger.error(f"Failed to generate Excel report: {excel_err}")

                msg_queue.put({'type': 'progress', 'pct': 100, 'message': 'ประมวลผลเสร็จสมบูรณ์ เตรียมแสดงรายงาน...' })
                
                # Return report and exit criteria evaluation
                result_payload = {
                    'id': transaction_id or None,
                    'project_id': project_id,
                    'group_name': group_name,
                    'group_type': group_type,
                    'total_pages': total_pages,
                    'status': 'success',
                    'report': report,
                    'email': email,
                    'doc_type': doc_type_display if is_explicit else 'Auto-detect (MD Cross-Check)',
                    'filename': original_filename,
                    'excel_url': excel_download_url,
                    'exit_criteria_eval': exit_criteria_eval,
                    'qa_findings': qa_findings,
                    'pages': pages_list,
                    'page_issue_summary': page_issue_summary,
                    'extracted_text': extracted_text,
                    'raw_text': extracted_text
                }
                
                # Notify strictly the user who initiated the document scan
                if req_user:
                    gate_status = (exit_criteria_eval.get('status') if exit_criteria_eval else 'COMPLETED')
                    score_pct = (exit_criteria_eval.get('score_percentage', 0) if exit_criteria_eval else 100)
                    noti_title = f"วิเคราะห์เอกสาร '{original_filename}' เสร็จสิ้น"
                    noti_msg = f"กลุ่ม '{group_name}' ผลประเมิน Gate: {gate_status} ({score_pct}%) พบประเด็น {len(qa_findings)} ข้อ"
                    noti_type = "success" if str(gate_status).upper() == "PASSED" else "warning"
                    noti_icon = "✅" if str(gate_status).upper() == "PASSED" else "⚠️"
                    try:
                        from notification_service import send_user_notification
                        send_user_notification(
                            username=req_user,
                            title=noti_title,
                            message=noti_msg,
                            noti_type=noti_type,
                            icon=noti_icon,
                            action_view="qa_consult",
                            action_payload={
                                "project_id": project_id,
                                "group_name": group_name,
                                "group_type": group_type,
                                "transaction_id": transaction_id,
                                "filename": original_filename
                            }
                        )
                    except Exception as noti_err:
                        logger.error(f"Failed to dispatch consult completion notification to {req_user}: {noti_err}")

                msg_queue.put({'type': 'complete', 'result': result_payload })
                msg_queue.put(None)

            except _QAConsultCancelledError:
                logger.info(f"QA Consult scan '{client_scan_id}' for '{raw_original_filename}' stopped cleanly upon user request.")
                if os.path.isdir(temp_img_dir):
                    try:
                        _shutil.rmtree(temp_img_dir, ignore_errors=True)
                    except Exception:
                        pass
                msg_queue.put({'type': 'cancelled', 'message': 'ยกเลิกการสแกนเอกสารเรียบร้อยแล้ว'})
                msg_queue.put(None)

            except Exception as e:
                import traceback
                traceback.print_exc()
                logger.error(f"Error in QA Consult background worker: {e}", exc_info=True)
                msg_queue.put({'type': 'error', 'message': str(e) })
                if req_user and not cancel_event.is_set():
                    try:
                        from notification_service import send_user_notification
                        send_user_notification(
                            username=req_user,
                            title=f"การวิเคราะห์เอกสาร '{original_filename}' ไม่สำเร็จ",
                            message=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)[:150]}",
                            noti_type="error",
                            icon="❌",
                            action_view="qa_consult",
                            action_payload={"project_id": project_id, "group_name": group_name}
                        )
                    except Exception:
                        pass
                msg_queue.put(None)
            finally:
                _ACTIVE_QA_CONSULT_CANCELS.pop(client_scan_id, None)

        # Launch background worker thread: continues running even if client navigates away
        worker_thread = threading.Thread(target=run_qa_worker, daemon=True)
        worker_thread.start()

        def generate():
            try:
                while True:
                    try:
                        item = msg_queue.get(timeout=2.0)
                        if item is None:
                            break
                        yield f"data: {json.dumps(item)}\n\n"
                        if item.get('type') in ['complete', 'error', 'cancelled']:
                            break
                    except queue.Empty:
                        if not worker_thread.is_alive():
                            break
                        yield ": keepalive\n\n"
            except GeneratorExit:
                logger.info(f"Client disconnected from SSE stream for '{original_filename}'. Background worker continues analyzing uninterrupted.")

        from flask import Response
        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'type': 'error', 'message': str(e)}), 500


@bp.route('/api/qa_send_email', methods=['POST'])
def qa_send_email():
    """
    รับ Report ที่ประมวลผลเสร็จแล้ว ส่งอีเมลแจ้งเตือน
    """
    try:
        import os, urllib.parse
        from pathlib import Path

        data = request.json
        email = data.get('email')
        doc_type = data.get('docType')
        filename = data.get('filename')
        report = data.get('report')
        excel_url = data.get('excel_url', '')
        exit_criteria_eval = data.get('exit_criteria_eval')

        if not all([email, doc_type, filename, report]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Build absolute URL for email links (supports PUBLIC_BASE_URL or dynamic request.host_url)
        public_base = os.environ.get('PUBLIC_BASE_URL') or os.environ.get('SERVER_URL') or request.host_url.rstrip('/')
        if excel_url and not excel_url.startswith(('http://', 'https://')):
            excel_url = f"{public_base.rstrip('/')}{'/' if not excel_url.startswith('/') else ''}{excel_url}"

        # Resolve excel file path on server to attach directly
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        excel_file_path = None
        if excel_url:
            url_path = urllib.parse.urlparse(excel_url).path
            fname = os.path.basename(url_path)
            candidate = reports_dir / fname
            if candidate.exists():
                excel_file_path = str(candidate)

        # If excel file doesn't exist on disk, generate it on-the-fly
        if not excel_file_path:
            try:
                from excel_report import generate_qa_excel
                doc_type_str = ', '.join(doc_type) if isinstance(doc_type, list) else (doc_type or 'Requirement')
                generated_path = generate_qa_excel(
                    report_text=report,
                    filename=filename,
                    doc_type=doc_type_str,
                    exit_criteria_eval=exit_criteria_eval
                )
                if os.path.exists(generated_path):
                    excel_file_path = generated_path
                    if not excel_url:
                        excel_url = f"{request.host_url.rstrip('/')}/api/qa_report/download/{os.path.basename(generated_path)}"
            except Exception as gen_err:
                logger.warning(f"Could not auto-generate Excel for email attachment: {gen_err}")

        from email_service import send_qa_report
        email_sent = send_qa_report(
            recipient_email=email,
            doc_type=doc_type,
            filename=filename,
            report_content=report,
            excel_download_url=excel_url,
            exit_criteria_eval=exit_criteria_eval,
            excel_file_path=excel_file_path
        )

        if email_sent:
            return jsonify({'success': True, 'message': 'ส่งอีเมลสำเร็จ'})
        else:
            return jsonify({'error': 'ไม่สามารถส่งอีเมลได้ กรุณาตรวจสอบการตั้งค่า GMAIL_APP_PASSWORD ใน .env'}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/api/qa_report/download/<path:filename>', methods=['GET'])
def download_qa_excel(filename):
    """Download generated QA Excel report with on-the-fly regeneration fallback"""
    try:
        import os, re, urllib.parse
        from pathlib import Path
        
        reports_dir = Path(__file__).parent.parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        raw_name = os.path.basename(urllib.parse.unquote(filename))
        
        # 1. Direct match on disk
        target_path = reports_dir / raw_name
        if not target_path.exists():
            # Try secure_filename version
            safe_name = secure_filename(raw_name)
            if (reports_dir / safe_name).exists():
                target_path = reports_dir / safe_name

        # 2. Check case-insensitively for matching file in reports directory
        if not target_path.exists():
            for f in os.listdir(reports_dir):
                if f.lower() == raw_name.lower():
                    target_path = reports_dir / f
                    break

        # 3. If still not found, try to find transaction in DB and generate on the fly
        if not target_path.exists():
            # Try to extract UUID / transaction_id from filename
            uuid_match = re.search(r'([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})', raw_name)
            row = None
            try:
                from db_ingestion import get_db_connection
                conn = get_db_connection()
                cur = conn.cursor()
                if uuid_match:
                    tid = uuid_match.group(1)
                    cur.execute("""
                        SELECT t.id, t.filename, t.doc_type, t.qa_report, t.group_name, t.group_type, p.project_code, t.qa_findings, t.exit_criteria_eval
                        FROM qa_transactions t
                        LEFT JOIN projects p ON t.project_id = p.project_id
                        WHERE CAST(t.id AS TEXT) = %s
                        LIMIT 1
                    """, (tid,))
                    row = cur.fetchone()
                else:
                    # Try matching by filename inside QA_Report_<filename>_<id>.xlsx
                    name_parts = raw_name.replace('QA_Report_', '').rsplit('_', 1)
                    doc_cand = name_parts[0] if name_parts else raw_name
                    cur.execute("""
                        SELECT t.id, t.filename, t.doc_type, t.qa_report, t.group_name, t.group_type, p.project_code, t.qa_findings, t.exit_criteria_eval
                        FROM qa_transactions t
                        LEFT JOIN projects p ON t.project_id = p.project_id
                        WHERE t.filename ILIKE %s OR %s ILIKE ('%' || REPLACE(t.filename, '.pdf', '') || '%')
                        ORDER BY t.created_at DESC
                        LIMIT 1
                    """, (f"%{doc_cand}%", raw_name))
                    row = cur.fetchone()
                cur.close()
                conn.close()
            except Exception as db_err:
                logger.warning(f"DB search fallback in download_qa_excel: {db_err}")

            if row:
                try:
                    from excel_report import generate_qa_excel
                    gen_path = generate_qa_excel(
                        report_text=row[3] or '',
                        filename=row[1] or 'Document',
                        doc_type=row[2] or 'Requirement',
                        project_code=row[6] or '',
                        group_name=row[4] or 'General',
                        group_type=row[5] or 'Project Plan',
                        transaction_id=str(row[0]),
                        exit_criteria_eval=row[8],
                        qa_findings=row[7] if isinstance(row[7], list) else None
                    )
                    if os.path.exists(gen_path):
                        target_path = Path(gen_path)
                except Exception as gen_err:
                    logger.error(f"Failed to on-the-fly generate excel in download: {gen_err}")

        if not target_path.exists():
            return jsonify({'error': 'ไม่พบไฟล์รายงาน Excel'}), 404
        
        final_filename = target_path.name
        return send_from_directory(
            str(target_path.parent),
            final_filename,
            as_attachment=True,
            download_name=final_filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Error downloading Excel report: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/qa_transactions', methods=['GET'])
def get_qa_transactions():
    """Fetch recent QA transactions"""
    try:
        from db_ingestion import get_db_connection, init_qa_transactions
        try:
            init_qa_transactions()
        except Exception as schema_err:
            logger.warning(f"Note: init_qa_transactions warning: {schema_err}")
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        limit = request.args.get('limit', 500, type=int)
        project_id = request.args.get('project_id')
        
        sql = """
            SELECT t.id, t.project_id, t.group_name, t.group_type, t.filename, t.doc_type, t.qa_report, t.created_at, p.project_code, t.total_pages, t.email, t.qa_findings, t.exit_criteria_eval, t.extracted_text
            FROM qa_transactions t
            LEFT JOIN projects p ON t.project_id = p.project_id
        """
        params = []
        if project_id:
            sql += " WHERE t.project_id = %s::uuid"
            params.append(project_id)
            
        sql += " ORDER BY t.created_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(sql, params)
        
        rows = cursor.fetchall()
        transactions = []
        for r in rows:
            p_id_str = str(r[1]) if r[1] is not None and str(r[1]).lower() != 'none' else None
            transactions.append({
                'id': str(r[0]),
                'project_id': p_id_str,
                'group_name': r[2] or 'General',
                'group_type': r[3] or '',
                'filename': r[4],
                'docType': r[5],
                'report': r[6],
                'date': r[7].isoformat() if r[7] else None,
                'project_code': r[8] or '',
                'total_pages': r[9] if len(r) > 9 else None,
                'email': r[10] if len(r) > 10 else None,
                'qa_findings': r[11] if len(r) > 11 else None,
                'exit_criteria_eval': r[12] if len(r) > 12 else None,
                'extracted_text': r[13] if len(r) > 13 else None,
                'raw_text': r[13] if len(r) > 13 else None
            })
            
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'transactions': transactions})
    except Exception as e:
        logger.error(f"Error fetching qa_transactions: {e}", exc_info=True)
        return jsonify({'success': True, 'transactions': [], 'warning': str(e)}), 200


@bp.route('/api/qa_transactions/<string:transaction_id>', methods=['DELETE'])
def delete_qa_transaction_api(transaction_id):
    """Delete a QA transaction by ID"""
    try:
        from db_ingestion import delete_qa_transaction
        success, msg = delete_qa_transaction(transaction_id)
        if success:
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'error': msg}), 500
    except Exception as e:
        logger.error(f"Error deleting qa_transaction {transaction_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/qa_groups', methods=['GET', 'POST', 'DELETE'])
def handle_qa_groups():
    """Handle QA groups (create, list, and delete)"""
    from db_ingestion import get_qa_groups, save_qa_group, delete_qa_group
    
    if request.method == 'GET':
        try:
            project_id = request.args.get('project_id')
            groups = get_qa_groups(project_id)
            return jsonify({'success': True, 'groups': groups})
        except Exception as e:
            logger.error(f"Error fetching qa_groups: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500
            
    elif request.method == 'POST':
        try:
            data = request.json
            if not data or not data.get('project_id') or not data.get('group_name'):
                return jsonify({'error': 'project_id and group_name are required'}), 400
                
            success, msg = save_qa_group(data['project_id'], data['group_name'], data.get('group_type', 'Project Plan'))
            if success:
                return jsonify({'success': True, 'message': msg})
            else:
                return jsonify({'error': msg}), 500
        except Exception as e:
            logger.error(f"Error creating qa_group: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            data = request.json or {}
            project_id = data.get('project_id') or request.args.get('project_id')
            group_name = data.get('group_name') or request.args.get('group_name')
            if not project_id or not group_name:
                return jsonify({'error': 'project_id and group_name are required'}), 400
                
            success, msg = delete_qa_group(project_id, group_name, delete_history=True)
            if success:
                return jsonify({'success': True, 'message': msg})
            else:
                return jsonify({'error': msg}), 500
        except Exception as e:
            logger.error(f"Error deleting qa_group: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500


@bp.route('/api/qa_groups/delete', methods=['POST'])
def delete_qa_group_post():
    """Alternative POST endpoint to delete a QA group and its history"""
    try:
        from db_ingestion import delete_qa_group
        data = request.json or {}
        project_id = data.get('project_id')
        group_name = data.get('group_name')
        if not project_id or not group_name:
            return jsonify({'error': 'project_id and group_name are required'}), 400
            
        success, msg = delete_qa_group(project_id, group_name, delete_history=True)
        if success:
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'error': msg}), 500
    except Exception as e:
        logger.error(f"Error deleting qa_group: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

