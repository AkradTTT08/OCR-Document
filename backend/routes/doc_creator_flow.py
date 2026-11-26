"""QA Document Creation, learned QA rules, Flow Analysis diagrams, wireframes, Stitch/Figma sync, and Vision diagram analyzer."""
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
bp = Blueprint('doc_creator_flow', __name__)

from core.config import BASE_DIR, UPLOAD_FOLDER, WIREFRAMES_FOLDER
from core.auth import get_request_user

@bp.route('/api/agent/create_document', methods=['POST'])
def create_document():
    data = request.json
    project_id = data.get('project_id')
    doc_type = data.get('doc_type')
    doc_name = data.get('doc_name')
    skill_id = data.get('skill_id') # Single ID or list of IDs
    reference_document_id = data.get('reference_document_id') # Single ID or list of IDs
    custom_prompt = data.get('custom_prompt', '')
    source_markdown = data.get('source_markdown', '')
    source_doc_id = data.get('source_doc_id') or None
    group_name = data.get('group_name', '')
    group_type = data.get('group_type', '')
    
    if not all([project_id, doc_type, doc_name]):
        return jsonify({'error': 'Missing required fields (project_id, doc_type, doc_name)'}), 400
        
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        req_user = get_request_user() or data.get('username')

        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_generated_documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                doc_name VARCHAR(255),
                doc_type VARCHAR(255),
                skill_id VARCHAR(500),
                status VARCHAR(50) DEFAULT 'Generating',
                file_url VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS group_name VARCHAR(255);
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS group_type VARCHAR(255);
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS username VARCHAR(100);
            ALTER TABLE qa_generated_documents ALTER COLUMN skill_id TYPE VARCHAR(500);
        """)
        
        # Serialize skill_id for storage
        if isinstance(skill_id, (list, tuple)):
            skill_id_str = ','.join([str(x).strip() for x in skill_id if x and str(x).strip()])
        else:
            skill_id_str = str(skill_id).strip() if skill_id else ''

        # Insert initial record
        cursor.execute("""
            INSERT INTO qa_generated_documents (project_id, doc_name, doc_type, skill_id, status, group_name, group_type, username)
            VALUES (%s::uuid, %s, %s, %s, 'Generating', %s, %s, %s)
            RETURNING id
        """, (project_id, doc_name, doc_type, skill_id_str, group_name or None, group_type or None, req_user or None))
        gen_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()

        # Run generation in background with dedicated user notification target
        from agent_6_doc_creator import create_qa_document_async
        import threading
        thread = threading.Thread(
            target=create_qa_document_async, 
            args=(gen_id, project_id, doc_type, doc_name, skill_id, reference_document_id, custom_prompt, source_markdown),
            kwargs={'username': req_user, 'source_doc_id': source_doc_id}
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'id': str(gen_id), 'status': 'Generating'})
            
    except Exception as e:
        logger.error(f"Error starting document creation: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/generated_documents', methods=['GET'])
def get_generated_documents():
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
        
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure table exists and has required columns
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_generated_documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                doc_name VARCHAR(255),
                doc_type VARCHAR(255),
                skill_id VARCHAR(500),
                status VARCHAR(50) DEFAULT 'Generating',
                file_url VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS markdown_content TEXT;
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS pdf_url VARCHAR(255);
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS error_message TEXT;
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS is_saved_to_project BOOLEAN DEFAULT FALSE;
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS saved_doc_id UUID;
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS group_name VARCHAR(255);
            ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS group_type VARCHAR(255);
            ALTER TABLE qa_generated_documents ALTER COLUMN skill_id TYPE VARCHAR(500);
        """)
        conn.commit()

        # Fetch skills lookup map
        cursor.execute("SELECT skill_id, skill_name FROM agent_skills")
        skills_map = {str(r[0]): r[1] for r in cursor.fetchall()}

        cursor.execute("""
            SELECT q.id, q.doc_name, q.doc_type, q.skill_id, q.status, q.file_url, q.pdf_url, 
                   q.is_saved_to_project, q.saved_doc_id, q.created_at, q.project_id, q.error_message, 
                   q.group_name, q.group_type, q.qa_status, q.qa_score, q.qa_findings_count, 
                   q.qa_findings, q.last_scanned_at, q.last_transaction_id
            FROM qa_generated_documents q
            WHERE q.project_id = %s::uuid
            ORDER BY q.created_at DESC
        """, (project_id,))
        
        rows = cursor.fetchall()
        docs = []
        for row in rows:
            raw_skill = str(row[3] or '')
            resolved_names = []
            if raw_skill:
                skill_keys = []
                if raw_skill.startswith('['):
                    try:
                        parsed = json.loads(raw_skill)
                        if isinstance(parsed, list):
                            skill_keys = [str(x).strip() for x in parsed]
                    except:
                        pass
                if not skill_keys:
                    skill_keys = [x.strip() for x in raw_skill.split(',') if x.strip()]
                
                for k in skill_keys:
                    if k in skills_map:
                        resolved_names.append(skills_map[k])
                    elif k and k not in ['undefined', 'null']:
                        resolved_names.append(k)

            # Parse qa_findings safely
            parsed_findings = []
            if len(row) > 17 and row[17]:
                if isinstance(row[17], list):
                    parsed_findings = row[17]
                elif isinstance(row[17], str):
                    try:
                        parsed_findings = json.loads(row[17])
                    except:
                        parsed_findings = []

            docs.append({
                'id': str(row[0]),
                'doc_name': row[1],
                'doc_type': row[2],
                'skill_name': ', '.join(resolved_names) if resolved_names else 'General Framework',
                'status': row[4],
                'file_url': row[5],
                'pdf_url': row[6],
                'is_saved_to_project': bool(row[7]) if row[7] is not None else False,
                'saved_doc_id': str(row[8]) if row[8] else None,
                'created_at': row[9].isoformat() if row[9] else None,
                'project_id': str(row[10]) if row[10] else str(project_id),
                'error_message': row[11] if len(row) > 11 else None,
                'group_name': row[12] if len(row) > 12 else None,
                'group_type': row[13] if len(row) > 13 else None,
                'qa_status': row[14] if len(row) > 14 else None,
                'qa_score': float(row[15]) if len(row) > 15 and row[15] is not None else None,
                'qa_findings_count': int(row[16]) if len(row) > 16 and row[16] is not None else len(parsed_findings),
                'qa_findings': parsed_findings,
                'last_scanned_at': row[18].isoformat() if len(row) > 18 and row[18] else None,
                'last_transaction_id': row[19] if len(row) > 19 else None
            })
            
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'documents': docs})
        
    except Exception as e:
        logger.error(f"Error fetching generated documents: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/mark_document_scanning', methods=['POST', 'OPTIONS'])
def mark_document_scanning():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.json or {}
    doc_id = data.get('doc_id') or data.get('id')
    if not doc_id:
        return jsonify({'error': 'Missing doc_id'}), 400
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE qa_generated_documents SET qa_status = 'Scanning' WHERE id = %s::uuid", (doc_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error marking document scanning: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/train_qa_rules', methods=['POST'])
def train_qa_rules():
    data = request.json or {}
    project_id = data.get('project_id')
    doc_type = data.get('doc_type', 'General')
    doc_name = data.get('doc_name', '')
    findings = data.get('findings', [])
    exit_criteria_eval = data.get('exit_criteria_eval', {})
    
    if not findings and not exit_criteria_eval:
        return jsonify({'success': True, 'message': 'No findings to train', 'count': 0})
        
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_agent_learned_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID,
                doc_type VARCHAR(255),
                source_doc_name VARCHAR(255),
                rule_category VARCHAR(255),
                issue_description TEXT,
                found_incorrect TEXT,
                correct_expectation TEXT,
                recommendation TEXT,
                severity VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                times_referenced INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        saved_count = 0
        for f in findings:
            issue = (f.get('issue') or '').strip()
            if not issue:
                continue
            cat = f.get('check_type') or 'QA Audit'
            found_inc = f.get('found_incorrect') or ''
            correct_val = f.get('correct_value') or ''
            rec = f.get('recommendation') or ''
            sev = f.get('severity') or 'Medium'
            
            # Check for duplicate rule in this project/doc_type
            cursor.execute("""
                SELECT id FROM qa_agent_learned_rules 
                WHERE doc_type = %s AND issue_description = %s AND is_active = TRUE
                LIMIT 1
            """, (doc_type, issue))
            existing = cursor.fetchone()
            if not existing:
                cursor.execute("""
                    INSERT INTO qa_agent_learned_rules 
                    (project_id, doc_type, source_doc_name, rule_category, issue_description, found_incorrect, correct_expectation, recommendation, severity)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (project_id if project_id else None, doc_type, doc_name, cat, issue, found_inc, correct_val, rec, sev))
                saved_count += 1
                
        # Also extract failed items from exit criteria
        if exit_criteria_eval and isinstance(exit_criteria_eval, dict):
            failed_items = [it for it in exit_criteria_eval.get('items', []) if it.get('status') == 'FAIL']
            for fit in failed_items:
                q_text = (fit.get('question_text') or '').strip()
                remarks = fit.get('remarks') or ''
                cat = fit.get('category') or 'Exit Criteria'
                sev = fit.get('severity') or 'High'
                evidence = fit.get('evidence_text') or ''
                
                if q_text:
                    cursor.execute("""
                        SELECT id FROM qa_agent_learned_rules 
                        WHERE doc_type = %s AND issue_description = %s AND is_active = TRUE
                        LIMIT 1
                    """, (doc_type, q_text))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO qa_agent_learned_rules 
                            (project_id, doc_type, source_doc_name, rule_category, issue_description, found_incorrect, correct_expectation, recommendation, severity)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (project_id if project_id else None, doc_type, doc_name, cat, q_text, evidence, fit.get('target_metric', '100% (ผ่านบริบูรณ์)'), remarks, sev))
                        saved_count += 1

        # Continuous Skill Evolution: Update base skill instructions in agent_skills
        if saved_count > 0 and doc_type:
            try:
                cursor.execute("""
                    SELECT skill_id, skill_name, markdown_instructions 
                    FROM agent_skills 
                    WHERE is_active = TRUE AND (UPPER(TRIM(target_doc_type)) = UPPER(TRIM(%s)) OR skill_name ILIKE %s)
                      AND skill_name NOT ILIKE '%%Exit Criteria%%' AND skill_name NOT ILIKE '%%QA SRS%%'
                    ORDER BY version DESC LIMIT 1;
                """, (doc_type, f"%{doc_type}%"))
                skill_to_evolve = cursor.fetchone()
                if skill_to_evolve:
                    s_id, s_name, s_inst = skill_to_evolve
                    crit_high_rules = [f for f in findings if (f.get('severity') or '').upper() in ['CRITICAL', 'HIGH'] and f.get('recommendation')]
                    evolved_notes = []
                    for cr in crit_high_rules[:3]:
                        rec = (cr.get('recommendation') or '').strip()
                        if rec and rec not in s_inst and not any(rec in n for n in evolved_notes):
                            evolved_notes.append(f"- [QA Audit Evolution]: {rec}")
                    if evolved_notes:
                        header_tag = "\n\n### 🛡️ กฎเกณฑ์ที่ได้รับการปรับปรุงจากผลตรวจ QA (Continuous Learned Directives)\n"
                        if header_tag not in s_inst:
                            new_inst = s_inst + header_tag + "\n".join(evolved_notes)
                        else:
                            new_inst = s_inst + "\n" + "\n".join(evolved_notes)
                        cursor.execute("UPDATE agent_skills SET markdown_instructions = %s, version = COALESCE(version, 1) + 1 WHERE skill_id = %s;", (new_inst, s_id))
                        logger.info(f"Skill '{s_name}' evolved with {len(evolved_notes)} new directives from QA findings!")
            except Exception as ev_err:
                logger.warning(f"Continuous skill evolution warning: {ev_err}")
                        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Trained Agent with {saved_count} new quality rules from QA Consult for {doc_type} ({doc_name})")
        return jsonify({'success': True, 'count': saved_count, 'message': f'Learned {saved_count} new rules for Agent 6'})
    except Exception as e:
        logger.error(f"Error training QA rules: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/learned_rules', methods=['GET'])
def get_learned_rules():
    project_id = request.args.get('project_id')
    doc_type = request.args.get('doc_type')
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_agent_learned_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID,
                doc_type VARCHAR(255),
                source_doc_name VARCHAR(255),
                rule_category VARCHAR(255),
                issue_description TEXT,
                found_incorrect TEXT,
                correct_expectation TEXT,
                recommendation TEXT,
                severity VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                times_referenced INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        
        query = "SELECT id, project_id, doc_type, source_doc_name, rule_category, issue_description, found_incorrect, correct_expectation, recommendation, severity, created_at FROM qa_agent_learned_rules WHERE is_active = TRUE"
        params = []
        if doc_type:
            query += " AND (doc_type = %s OR doc_type = 'General')"
            params.append(doc_type)
        if project_id:
            query += " AND (project_id = %s::uuid OR project_id IS NULL)"
            params.append(project_id)
            
        query += " ORDER BY created_at DESC LIMIT 50"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        rules = []
        for r in rows:
            rules.append({
                "id": str(r[0]),
                "project_id": str(r[1]) if r[1] else None,
                "doc_type": r[2],
                "source_doc_name": r[3],
                "rule_category": r[4],
                "issue_description": r[5],
                "found_incorrect": r[6],
                "correct_expectation": r[7],
                "recommendation": r[8],
                "severity": r[9],
                "created_at": r[10].isoformat() if r[10] else None
            })
            
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'rules': rules})
    except Exception as e:
        logger.error(f"Error fetching learned rules: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/download_generated_document/<string:doc_id>', methods=['GET'])
def download_generated_document(doc_id):
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        download_format = request.args.get('format', 'pdf').lower() # 'pdf', 'excel', 'xlsx', 'md'
        
        cursor.execute("SELECT file_url, pdf_url, doc_name, markdown_content, doc_type FROM qa_generated_documents WHERE id = %s::uuid", (doc_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Document not found'}), 404
            
        excel_path, pdf_path, doc_name, markdown_content, doc_type = row
        safe_name = "".join([c if c.isalnum() or c in (' ', '_', '-') else '_' for c in (doc_name or 'Document')]).strip().replace(' ', '_')
        
        if download_format in ['excel', 'xlsx']:
            file_path = excel_path
            if not file_path or not os.path.exists(file_path):
                return jsonify({'error': 'Excel file does not exist on disk'}), 404
            
            # Automatically apply corporate styling, borders, and layouts
            try:
                from testcase_excel_styler import beautify_workbook_file
                beautify_workbook_file(file_path)
            except Exception as b_err:
                logger.warning(f"Auto-beautify on download: {b_err}")

            return send_file(
                file_path, 
                as_attachment=True, 
                download_name=f"{safe_name}.xlsx",
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif download_format in ['md', 'markdown']:
            import io
            content = markdown_content or f"# {doc_name}\n(No markdown content)"
            return send_file(
                io.BytesIO(content.encode('utf-8')),
                mimetype='text/markdown',
                as_attachment=True,
                download_name=f"{safe_name}.md"
            )
        else: # Default: pdf
            file_path = pdf_path
            # If pdf_path is missing or not found on disk, generate on-the-fly using System Template
            if not file_path or not os.path.exists(file_path):
                if markdown_content and markdown_content.strip():
                    from agent_6_doc_creator import render_html_to_pdf, simple_markdown_to_html, build_generic_document_html
                    import uuid
                    import datetime
                    upload_dir = os.path.join(os.getcwd(), 'uploads', 'qa_generated')
                    os.makedirs(upload_dir, exist_ok=True)
                    gen_pdf_path = os.path.join(upload_dir, f"{safe_name}_{uuid.uuid4().hex[:6]}.pdf")
                    today_str = datetime.datetime.now().strftime("%d/%m/%Y")
                    rendered_body = simple_markdown_to_html(markdown_content)
                    html_content = build_generic_document_html(doc_name, doc_type or "Document", "QA Project", "-", "Standard QA Framework", today_str, rendered_body)
                    if render_html_to_pdf(html_content, gen_pdf_path) and os.path.exists(gen_pdf_path):
                        file_path = gen_pdf_path
                        try:
                            c2 = get_db_connection()
                            cur2 = c2.cursor()
                            cur2.execute("UPDATE qa_generated_documents SET pdf_url = %s WHERE id = %s::uuid", (gen_pdf_path, doc_id))
                            c2.commit()
                            cur2.close()
                            c2.close()
                        except:
                            pass
            
            if not file_path or not os.path.exists(file_path):
                return jsonify({'error': 'PDF file is not available for this document'}), 404
                
            return send_file(
                file_path, 
                as_attachment=True, 
                download_name=f"{safe_name}.pdf",
                mimetype='application/pdf'
            )
        
    except Exception as e:
        logger.error(f"Error downloading generated document: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/save_generated_doc_to_project', methods=['POST'])
@bp.route('/api/qa/save_generated_doc', methods=['POST'])
def save_generated_doc_to_project():
    data = request.json or {}
    doc_id = data.get('doc_id')
    target_project_id = data.get('project_id')
    raw_filename = data.get('filename') or ''
    doc_category = data.get('doc_category', 'Reference')
    doc_type = data.get('doc_type', 'Test Case')
    is_golden_data = bool(data.get('is_golden_data', False))
    req_markdown = data.get('markdown_content') or ''

    if not target_project_id:
        return jsonify({'error': 'project_id is required'}), 400

    try:
        from db_ingestion import get_db_connection, ingest_markdown_document
        conn = get_db_connection()
        cursor = conn.cursor()
        
        row_doc_name = ''
        row_doc_type = ''
        markdown_content = ''

        # 1. If doc_id provided, look up in qa_generated_documents
        if doc_id:
            try:
                cursor.execute("""
                    SELECT doc_name, doc_type, project_id, markdown_content, is_saved_to_project, saved_doc_id
                    FROM qa_generated_documents
                    WHERE id = %s::uuid
                """, (doc_id,))
                row = cursor.fetchone()
                if row:
                    row_doc_name, row_doc_type, row_proj_id, db_md, _, _ = row
                    markdown_content = db_md or ''
            except Exception as e_lookup:
                logger.warning(f"Lookup by doc_id failed: {e_lookup}")

        # 2. If doc_id was not found or not provided, try finding by original_doc_name or filename
        if not markdown_content:
            orig_name = data.get('original_doc_name') or raw_filename.replace('.md', '').strip()
            if orig_name:
                try:
                    cursor.execute("""
                        SELECT id, doc_name, doc_type, markdown_content
                        FROM qa_generated_documents
                        WHERE project_id = %s::uuid AND doc_name = %s
                        ORDER BY created_at DESC LIMIT 1
                    """, (target_project_id, orig_name))
                    row2 = cursor.fetchone()
                    if row2:
                        doc_id = str(row2[0])
                        row_doc_name = row2[1]
                        row_doc_type = row2[2]
                        markdown_content = row2[3] or ''
                except Exception as e_lookup2:
                    logger.warning(f"Lookup by doc_name failed: {e_lookup2}")

        # 3. Fallback to direct markdown provided in request payload
        if not markdown_content or not markdown_content.strip():
            markdown_content = req_markdown

        if not markdown_content or not markdown_content.strip():
            cursor.close()
            conn.close()
            return jsonify({'error': 'ไม่พบเนื้อหา Markdown สำหรับบันทึกเอกสารนี้'}), 400

        # Determine filename
        if not raw_filename:
            raw_filename = f"{row_doc_name or 'Document'}.md"
        filename = raw_filename if (raw_filename.endswith('.md') or '.' in raw_filename) else f"{raw_filename}.md"
        eff_doc_type = doc_type or row_doc_type or 'Test Case'

        logger.info(f"Ingesting QA generated document '{filename}' into project {target_project_id} (Category: {doc_category}, Golden: {is_golden_data})...")
        success, msg_or_id = ingest_markdown_document(
            filename=filename,
            markdown_text=markdown_content.strip(),
            project_id=target_project_id,
            doc_category=doc_category,
            doc_type=eff_doc_type,
            is_golden_data=is_golden_data
        )

        if success:
            ingested_doc_id = msg_or_id
            if doc_id:
                try:
                    cursor.execute("""
                        UPDATE qa_generated_documents
                        SET is_saved_to_project = TRUE,
                            saved_doc_id = %s::uuid
                        WHERE id = %s::uuid
                    """, (ingested_doc_id, doc_id))
                    conn.commit()
                except Exception as e_up:
                    logger.warning(f"Could not update qa_generated_documents flag: {e_up}")

            cursor.close()
            conn.close()
            return jsonify({
                'success': True,
                'message': 'บันทึกเอกสารเข้าโครงการสำเร็จ',
                'doc_id': str(ingested_doc_id)
            })
        else:
            cursor.close()
            conn.close()
            return jsonify({'error': msg_or_id or 'บันทึกเอกสารไม่สำเร็จ'}), 500
    except Exception as e:
        logger.error(f"Error saving generated doc to project: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/cancel_generated_document/<string:doc_id>', methods=['POST', 'DELETE'])
@bp.route('/api/agent/delete_generated_document/<string:doc_id>', methods=['POST', 'DELETE'])
def cancel_or_delete_generated_document(doc_id):
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        action = request.args.get('action', 'cancel')
        if action == 'delete' or request.method == 'DELETE' or 'delete' in request.path:
            cursor.execute("DELETE FROM qa_generated_documents WHERE id = %s::uuid", (doc_id,))
        else:
            cursor.execute("UPDATE qa_generated_documents SET status = 'Cancelled' WHERE id = %s::uuid AND status = 'Generating'", (doc_id,))
            if cursor.rowcount == 0:
                cursor.execute("DELETE FROM qa_generated_documents WHERE id = %s::uuid", (doc_id,))
                
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'ยกเลิก / ลบรายการสำเร็จ'})
    except Exception as e:
        logger.error(f"Error cancelling/deleting generated document: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/flow_analysis', methods=['GET'])
def get_flow_analysis():
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
        
    try:
        from agent_7_flow_analyzer import get_project_flow_analysis
        result = get_project_flow_analysis(project_id)
        if result:
            return jsonify({'success': True, 'analysis': result})
        return jsonify({'success': False, 'message': 'No flow analysis found for this project'})
    except Exception as e:
        logger.error(f"Error fetching flow analysis: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/generate_flow_analysis', methods=['POST'])
def generate_flow_analysis():
    data = request.json or {}
    project_id = data.get('project_id')
    custom_instructions = data.get('custom_instructions', '')
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
        
    try:
        from agent_7_flow_analyzer import analyze_project_flow_and_diagrams
        success, res_or_err = analyze_project_flow_and_diagrams(project_id, custom_instructions)
        if success:
            return jsonify({'success': True, 'analysis': res_or_err})
        else:
            return jsonify({'error': f"Flow analysis failed: {res_or_err}"}), 500
    except Exception as e:
        logger.error(f"Error generating flow analysis: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/save_flow_analysis', methods=['POST'])
def save_flow_analysis():
    data = request.json or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
        
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sitemap_data = data.get('sitemap', [])
        system_flowchart = data.get('system_flowchart', '')
        usecase_diagram = data.get('usecase_diagram', '')
        activity_diagram = data.get('activity_diagram', '')
        sequence_diagram = data.get('sequence_diagram', '')
        screen_mockups = data.get('screen_mockups', [])
        traceability_matrix = data.get('traceability_matrix', [])
        summary_stats = data.get('summary_stats', {})
        
        cursor.execute("SELECT id FROM qa_analysis_diagrams WHERE project_id = %s::uuid ORDER BY updated_at DESC LIMIT 1", (project_id,))
        existing_row = cursor.fetchone()
        
        if existing_row:
            analysis_id = existing_row[0]
            cursor.execute("""
                UPDATE qa_analysis_diagrams
                SET sitemap_data = %s,
                    system_flowchart = %s,
                    usecase_diagram = %s,
                    activity_diagram = %s,
                    sequence_diagram = %s,
                    screen_mockups = %s,
                    traceability_matrix = %s,
                    summary_stats = %s,
                    status = 'Completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
            """, (
                json.dumps(sitemap_data, ensure_ascii=False),
                system_flowchart,
                usecase_diagram,
                activity_diagram,
                sequence_diagram,
                json.dumps(screen_mockups, ensure_ascii=False),
                json.dumps(traceability_matrix, ensure_ascii=False),
                json.dumps(summary_stats, ensure_ascii=False),
                analysis_id
            ))
        else:
            cursor.execute("""
                INSERT INTO qa_analysis_diagrams (
                    project_id, sitemap_data, system_flowchart, usecase_diagram, activity_diagram,
                    sequence_diagram, screen_mockups, traceability_matrix, summary_stats, status
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'Completed'
                ) RETURNING id
            """, (
                project_id,
                json.dumps(sitemap_data, ensure_ascii=False),
                system_flowchart,
                usecase_diagram,
                activity_diagram,
                sequence_diagram,
                json.dumps(screen_mockups, ensure_ascii=False),
                json.dumps(traceability_matrix, ensure_ascii=False),
                json.dumps(summary_stats, ensure_ascii=False)
            ))
            analysis_id = cursor.fetchone()[0]
            
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'id': str(analysis_id), 'message': 'บันทึกข้อมูล Flow Analysis เรียบร้อยแล้ว'})
    except Exception as e:
        logger.error(f"Error saving flow analysis: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/upload_wireframe_image', methods=['POST'])
def upload_wireframe_image():
    """
    Uploads a custom UI Wireframe / Mockup image for a specific screen in a project.
    """
    project_id = request.form.get('project_id')
    screen_id = request.form.get('screen_id')
    file = request.files.get('file')
    
    if not project_id or not screen_id:
        return jsonify({'error': 'project_id and screen_id are required'}), 400
        
    if not file or file.filename == '':
        return jsonify({'error': 'No file uploaded'}), 400
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif']:
        return jsonify({'error': 'Unsupported file format. Please upload PNG, JPG, WebP, SVG, or GIF.'}), 400
        
    try:
        import uuid
        wireframe_dir = Path(__file__).parent.parent / 'uploads' / 'wireframes'
        wireframe_dir.mkdir(exist_ok=True, parents=True)
        
        safe_proj = "".join([c if c.isalnum() else '_' for c in str(project_id)[:8]])
        safe_screen = "".join([c if c.isalnum() else '_' for c in str(screen_id)])
        filename = f"wf_{safe_proj}_{safe_screen}_{uuid.uuid4().hex[:6]}{ext}"
        save_path = wireframe_dir / filename
        file.save(str(save_path))
        
        image_url = f"/uploads/wireframes/{filename}"
        
        # Update in database qa_analysis_diagrams table
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, screen_mockups FROM qa_analysis_diagrams WHERE project_id = %s::uuid ORDER BY updated_at DESC LIMIT 1", (project_id,))
        row = cursor.fetchone()
        
        if row:
            analysis_id, screen_mockups_data = row
            mockups = screen_mockups_data if isinstance(screen_mockups_data, list) else []
            updated = False
            for m in mockups:
                if m.get('screen_id') == screen_id:
                    m['wireframe_type'] = 'image'
                    m['image_url'] = image_url
                    m['image_filename'] = file.filename
                    updated = True
                    break
                    
            if not updated:
                mockups.append({
                    'screen_id': screen_id,
                    'screen_name': screen_id,
                    'wireframe_type': 'image',
                    'image_url': image_url,
                    'image_filename': file.filename
                })
                
            cursor.execute("""
                UPDATE qa_analysis_diagrams
                SET screen_mockups = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
            """, (json.dumps(mockups, ensure_ascii=False), analysis_id))
            conn.commit()
            
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'image_url': image_url,
            'screen_id': screen_id,
            'message': 'อัปโหลดรูปภาพ Wireframe สำเร็จ'
        })
        
    except Exception as e:
        logger.error(f"Error uploading wireframe image: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/agent/update_screen_wireframe', methods=['POST'])
def update_screen_wireframe():
    """
    Updates screen wireframe mode (AI, Figma, Image) and settings for a screen.
    """
    data = request.json or {}
    project_id = data.get('project_id')
    screen_id = data.get('screen_id')
    wireframe_type = data.get('wireframe_type', 'ai') # 'ai' | 'figma' | 'image'
    figma_url = data.get('figma_url', '')
    image_url = data.get('image_url', '')
    
    if not project_id or not screen_id:
        return jsonify({'error': 'project_id and screen_id are required'}), 400
        
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, screen_mockups FROM qa_analysis_diagrams WHERE project_id = %s::uuid ORDER BY updated_at DESC LIMIT 1", (project_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Analysis record not found for this project'}), 404
            
        analysis_id, screen_mockups_data = row
        mockups = screen_mockups_data if isinstance(screen_mockups_data, list) else []
        
        for m in mockups:
            if m.get('screen_id') == screen_id:
                m['wireframe_type'] = wireframe_type
                if figma_url is not None and 'figma_url' in data:
                    m['figma_url'] = figma_url
                if image_url is not None and 'image_url' in data:
                    m['image_url'] = image_url
                break
                
        cursor.execute("""
            UPDATE qa_analysis_diagrams
            SET screen_mockups = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s::uuid
        """, (json.dumps(mockups, ensure_ascii=False), analysis_id))
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'บันทึกการตั้งค่า Wireframe เรียบร้อย'})
        
    except Exception as e:
        logger.error(f"Error updating screen wireframe: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _persist_stitch_api_key(new_key: str):
    """Persists STITCH_API_KEY in memory and .env file."""
    clean_key = (new_key or '').strip()
    if not clean_key:
        return
    os.environ['STITCH_API_KEY'] = clean_key
    try:
        env_file = BASE_DIR / '.env'
        existing = env_file.read_text(encoding='utf-8') if env_file.exists() else ''
        lines = [l for l in existing.splitlines() if not l.strip().startswith(('STITCH_API_KEY=', 'STITCH_MCP_URL='))]
        lines.append(f'STITCH_API_KEY={clean_key}')
        lines.append('STITCH_MCP_URL=https://stitch.googleapis.com/mcp')
        env_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    except Exception as err:
        logger.warning(f"Could not write STITCH_API_KEY to .env: {err}")


@bp.route('/api/agent/stitch/save_key', methods=['POST'])
def save_stitch_api_key():
    data = request.json or {}
    api_key = (data.get('stitch_api_key') or '').strip()
    if not api_key:
        return jsonify({'error': 'กรุณาระบุ Stitch API Key'}), 400
    _persist_stitch_api_key(api_key)
    from agent_7_flow_analyzer import _call_stitch_mcp
    ok, res = _call_stitch_mcp('list_projects', {'pageSize': 1}, api_key, timeout=15)
    return jsonify({
        'success': True,
        'stitch_verified': ok,
        'stitch_status': 'เชื่อมต่อ Google Stitch MCP สำเร็จ!' if ok else f'บันทึกคีย์แล้ว แต่ Stitch ตอบกลับ: {res} (ระบบจะใช้ Gemini Live HTML เป็น Fallback อัตโนมัติ)',
        'masked_key': f"...{api_key[-10:]}" if len(api_key) > 10 else "***"
    })


@bp.route('/api/agent/stitch/generate_screen', methods=['POST'])
def generate_stitch_screen_endpoint():
    """
    Generates a High-Fidelity interactive screen UI via Google Stitch MCP
    (isolated 1-to-1 per project) with automatic fallback to Gemini Live HTML/Tailwind.
    """
    data = request.json or {}
    project_id = data.get('project_id')
    screen_id = data.get('screen_id')
    device_type = data.get('device_type', 'DESKTOP')
    custom_prompt = (data.get('custom_prompt') or '').strip()
    engine = (data.get('engine') or 'auto').strip().lower()
    stitch_api_key = (data.get('stitch_api_key') or '').strip()

    if stitch_api_key:
        _persist_stitch_api_key(stitch_api_key)

    from agent_7_flow_analyzer import generate_highfi_screen_ui
    ok, result = generate_highfi_screen_ui(
        project_id=project_id,
        screen_id=screen_id,
        device_type=device_type,
        custom_prompt=custom_prompt,
        engine=engine,
        stitch_api_key=stitch_api_key
    )
    if not ok:
        return jsonify({'success': False, 'error': str(result)}), 400
    return jsonify({'success': True, **result})


@bp.route('/api/agent/figma/sync_frame', methods=['POST'])
def sync_figma_frame():
    """
    Parses Figma URL, provides Embed URL, and optionally syncs high-res PNG image via Figma API.
    """
    data = request.json or {}
    figma_url = data.get('figma_url', '').strip()
    figma_token = data.get('figma_token', '').strip() or os.environ.get('FIGMA_ACCESS_TOKEN', '')
    project_id = data.get('project_id')
    screen_id = data.get('screen_id')
    
    if not figma_url:
        return jsonify({'error': 'figma_url is required'}), 400
        
    try:
        import re
        import urllib.parse
        import requests
        import uuid
        
        # Parse file key and node id
        file_key_match = re.search(r'figma\.com/(?:file|design|proto)/([a-zA-Z0-9]+)', figma_url)
        file_key = file_key_match.group(1) if file_key_match else None
        
        node_id_match = re.search(r'node-id=([a-zA-Z0-9%:-]+)', figma_url)
        node_id_raw = node_id_match.group(1) if node_id_match else None
        node_id = urllib.parse.unquote(node_id_raw) if node_id_raw else None
        # Convert colon or hyphen for Figma API (API expects e.g. 1:2 or 1-2)
        api_node_id = node_id.replace('-', ':') if node_id else None
        
        # Standard Figma Live Embed URL
        encoded_url = urllib.parse.quote(figma_url, safe='')
        embed_url = f"https://www.figma.com/embed?embed_host=spectra_qa&url={encoded_url}"
        
        image_url = None
        # If Figma Token is provided and we have file_key & node_id, fetch rendered frame image
        if figma_token and file_key and api_node_id:
            try:
                api_res = requests.get(
                    f"https://api.figma.com/v1/images/{file_key}",
                    headers={"X-Figma-Token": figma_token},
                    params={"ids": api_node_id, "format": "png", "scale": 2},
                    timeout=15
                )
                if api_res.ok:
                    res_data = api_res.json()
                    images_dict = res_data.get('images', {})
                    remote_img_url = images_dict.get(api_node_id) or list(images_dict.values())[0] if images_dict else None
                    if remote_img_url:
                        # Download and save locally
                        img_res = requests.get(remote_img_url, timeout=20)
                        if img_res.ok:
                            wireframe_dir = Path(__file__).parent.parent / 'uploads' / 'wireframes'
                            wireframe_dir.mkdir(exist_ok=True, parents=True)
                            safe_proj = "".join([c if c.isalnum() else '_' for c in str(project_id)[:8]]) if project_id else 'proj'
                            safe_screen = "".join([c if c.isalnum() else '_' for c in str(screen_id)]) if screen_id else 'screen'
                            local_fname = f"figma_{safe_proj}_{safe_screen}_{uuid.uuid4().hex[:6]}.png"
                            with open(wireframe_dir / local_fname, 'wb') as f:
                                f.write(img_res.content)
                            image_url = f"/uploads/wireframes/{local_fname}"
            except Exception as figma_err:
                logger.warning(f"Figma API image sync warning (fallback to live embed): {figma_err}")
                
        return jsonify({
            'success': True,
            'figma_url': figma_url,
            'file_key': file_key,
            'node_id': node_id,
            'embed_url': embed_url,
            'synced_image_url': image_url,
            'message': 'ดึงข้อมูล Figma Frame สำเร็จ'
        })
        
    except Exception as e:
        logger.error(f"Error syncing Figma frame: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/vision/analyze-diagram', methods=['POST', 'OPTIONS'])
def analyze_vision_diagram():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    try:
        data = request.get_json() or {}
        image_base64 = data.get('image', '')
        diagram_type = data.get('diagram_type', 'wireframe')
        
        if not image_base64:
            return jsonify({'error': 'Image data required'}), 400
            
        from vision_analyzer import VisionDiagramAnalyzer
        res = VisionDiagramAnalyzer.analyze_diagram_image(image_base64, diagram_type)
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error analyzing vision diagram: {e}")
        return jsonify({'error': str(e)}), 500

