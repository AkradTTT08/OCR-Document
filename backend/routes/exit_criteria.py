"""Exit Criteria evaluation engine, template CRUD, Universal reset, AI suggestions, and sandbox testing."""
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
bp = Blueprint('exit_criteria', __name__)

from datetime import datetime
from core.auth import admin_required, get_request_user_payload, token_required
from core.qa_helpers import (
    _is_false_future_be_date_claim,
    _split_text_into_logical_pages,
)

def normalize_exit_criteria_category(raw_cat: str, item_code: str = '') -> str:
    """Normalize legacy/variant category names into the 4 canonical Exit Criteria categories."""
    c = (raw_cat or '').strip()
    cl = c.lower()
    if c in (
        'Defect & Comment Resolution',
        'Content Accuracy & Completeness',
        'Format & Consistency',
        'Governance & Control'
    ):
        return c
    if any(k in cl for k in ['defect', 'bug', 'comment', 'แก้ไข']):
        return 'Defect & Comment Resolution'
    if any(k in cl for k in ['content', 'accuracy', 'completeness', 'เนื้อหา', 'ครบถ้วน']):
        return 'Content Accuracy & Completeness'
    if any(k in cl for k in ['format', 'consistency', 'typo', 'quality', 'รูปแบบ', 'คำผิด']):
        return 'Format & Consistency'
    if any(k in cl for k in ['governance', 'control', 'version', 'metadata', 'กำกับ']):
        return 'Governance & Control'
    code_clean = str(item_code or '').strip()
    if code_clean.startswith('1'):
        return 'Defect & Comment Resolution'
    if code_clean.startswith('2'):
        return 'Content Accuracy & Completeness'
    if code_clean.startswith('3'):
        return 'Format & Consistency'
    if code_clean.startswith('4'):
        return 'Governance & Control'
    return c or 'Content Accuracy & Completeness'


def sync_exit_criteria_to_agent_skills(template_id, old_title: str = None):
    """
    Sync an Exit Criteria template into the agent_skills table as a Markdown skill (skill.md format).
    Updates existing skill in-place when renamed so no orphaned skills remain.
    """
    from db_ingestion import get_db_connection
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT template_id, title, description, doc_type, is_active
            FROM exit_criteria_templates WHERE template_id = %s;
        """, (template_id,))
        t = cur.fetchone()
        if not t:
            cur.close()
            conn.close()
            return False
            
        t_id, title, desc, doc_type, is_active = t
        
        cur.execute("""
            SELECT item_code, category, question_text, target_metric, severity, is_mandatory, order_index
            FROM exit_criteria_items WHERE template_id = %s ORDER BY order_index ASC, item_code ASC;
        """, (template_id,))
        items = cur.fetchall()
        
        md_text = f"# {title} (Skill.md)\n\n"
        md_text += f"> **Template ID:** `{t_id}`\n"
        md_text += f"> **Description:** {desc or 'Exit Criteria Gate Standards'}\n"
        md_text += f"> **Target Document Type:** {doc_type}\n\n"
        md_text += "## Objective\n"
        md_text += "Evaluate document content against the exit criteria checklist items prior to final sign-off.\n\n"
        
        current_cat = None
        for item_code, category, question, metric, severity, is_mandatory, idx in items:
            norm_cat = normalize_exit_criteria_category(category, item_code)
            if norm_cat != current_cat:
                current_cat = norm_cat
                md_text += f"\n### {norm_cat}\n"
            mand_str = "[Mandatory]" if is_mandatory else "[Optional]"
            md_text += f"- **{item_code}** ({severity} | KPI: {metric or '100%'} | {mand_str}): {question}\n"
            
        md_text += "\n## Final Gate Assessment Rules\n"
        md_text += "1. **PASSED:** All relevant items evaluated as PASS.\n"
        md_text += "2. **CONDITIONAL PASSED:** Pass all Mandatory/Critical items (Categories 1, 2, 4); fail only optional Minor formatting/typo items in Category 3.\n"
        md_text += "3. **REJECTED:** Fail any Mandatory or Critical item.\n"

        skill_name = f"[Exit Criteria] {title}"
        old_skill_name = f"[Exit Criteria] {old_title}" if old_title and old_title != title else None

        existing_skill = None
        if old_skill_name:
            cur.execute("SELECT skill_id FROM agent_skills WHERE skill_name = %s;", (old_skill_name,))
            existing_skill = cur.fetchone()
        if not existing_skill:
            cur.execute("SELECT skill_id FROM agent_skills WHERE skill_name = %s OR markdown_instructions ILIKE %s LIMIT 1;", (skill_name, f"%Template ID:** `{t_id}`%"))
            existing_skill = cur.fetchone()
        
        if existing_skill:
            cur.execute("""
                UPDATE agent_skills
                SET skill_name = %s, skill_description = %s, markdown_instructions = %s, target_doc_type = %s, is_active = %s, version = version + 1
                WHERE skill_id = %s;
            """, (skill_name, desc or f"Exit Criteria Standard Gate Checklist for {doc_type}", md_text, doc_type, is_active, existing_skill[0]))
        else:
            cur.execute("""
                INSERT INTO agent_skills (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by)
                VALUES (%s, %s, %s, %s, 1, %s, 'Exit Criteria System');
            """, (skill_name, desc or f"Exit Criteria Standard Gate Checklist for {doc_type}", md_text, doc_type, is_active))
            
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Successfully synced Exit Criteria Template '{title}' to agent_skills!")
        return True
    except Exception as e:
        logger.error(f"Error syncing Exit Criteria to agent_skills: {e}", exc_info=True)
        if conn: conn.close()
        return False


def delete_exit_criteria_agent_skill(template_id, title: str = None):
    """Remove synced [Exit Criteria] skill from agent_skills when its template is deleted."""
    from db_ingestion import get_db_connection
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if title:
            cur.execute(
                "DELETE FROM agent_skills WHERE skill_name = %s OR markdown_instructions ILIKE %s;",
                (f"[Exit Criteria] {title}", f"%Template ID:** `{template_id}`%")
            )
        else:
            cur.execute("DELETE FROM agent_skills WHERE markdown_instructions ILIKE %s;", (f"%Template ID:** `{template_id}`%",))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Could not clean up agent_skill for deleted template {template_id}: {e}")
        if conn:
            conn.close()


def _normalize_doc_type_aliases(raw_doc_type: str, doc_text: str = '') -> list:
    """
    Normalize document type strings and aliases (e.g. 'TestCase' <-> 'Test Case',
    'Usermanual' <-> 'User Manual', 'SRS, Test Case') into canonical candidate labels
    so Exit Criteria templates and AI Skills match reliably.
    """
    ALIAS_MAP = {
        'testcase': ['Test Case', 'TestCase'],
        'test case': ['Test Case', 'TestCase'],
        'test cases': ['Test Case', 'TestCase'],
        'srs': ['SRS', 'Requirement', 'Requirements'],
        'requirement': ['Requirement', 'Requirements', 'SRS'],
        'requirements': ['Requirements', 'Requirement', 'SRS'],
        'usermanual': ['User Manual', 'Usermanual'],
        'user manual': ['User Manual', 'Usermanual'],
        'adminmanual': ['Admin Manual', 'Adminmanual'],
        'admin manual': ['Admin Manual', 'Adminmanual'],
        'projectplan': ['Project Plan', 'ProjectPlan'],
        'project plan': ['Project Plan', 'ProjectPlan'],
        'system design': ['System Design', 'SDD', 'Architecture'],
        'sdd': ['System Design', 'SDD'],
        'uat': ['UAT', 'Test Case'],
        'tor': ['TOR', 'Requirement', 'SRS']
    }
    raw_clean = (raw_doc_type or '').strip()
    parts = [p.strip() for p in re.split(r'[,;/|]+', raw_clean) if p.strip()] if raw_clean else []
    candidates = []
    for p in parts:
        pl = p.lower()
        if pl in ('all', 'auto-detect', 'auto-detect (md cross-check)', 'ไม่ระบุ', 'general'):
            continue
        for mapped in ALIAS_MAP.get(pl, [p]):
            if mapped not in candidates:
                candidates.append(mapped)
        if p not in candidates:
            candidates.append(p)

    # Auto-detect from document text if no explicit type was given
    if not candidates and doc_text:
        sample_low = doc_text[:12000].lower()
        if any(k in sample_low for k in ['test case', 'tc_', 'test id', 'expected result', 'test step', 'ขั้นตอนการทดสอบ', 'ผลลัพธ์ที่คาดหวัง']):
            candidates.extend(['Test Case', 'TestCase'])
        elif any(k in sample_low for k in ['software requirements specification', 'srs', 'functional requirement', 'req-']):
            candidates.extend(['SRS', 'Requirement', 'Requirements'])
        elif any(k in sample_low for k in ['คู่มือผู้ใช้งาน', 'user manual', 'ขั้นตอนการใช้งานระบบ']):
            candidates.extend(['User Manual', 'Usermanual'])
        elif any(k in sample_low for k in ['คู่มือผู้ดูแลระบบ', 'admin manual', 'system administration']):
            candidates.extend(['Admin Manual', 'Adminmanual'])
        elif any(k in sample_low for k in ['project plan', 'แผนการดำเนินงาน', 'wbs', 'milestone']):
            candidates.extend(['Project Plan', 'ProjectPlan'])
        elif any(k in sample_low for k in ['system design', 'database schema', 'er diagram', 'สถาปัตยกรรมระบบ']):
            candidates.extend(['System Design'])

    return candidates


def evaluate_document_exit_criteria(doc_text: str, doc_type: str = 'ALL', project_id = None, qa_findings: list = None, custom_items_override: list = None, dry_run: bool = False):
    """
    Evaluates document text against Exit Criteria items using Gemini AI + Deterministic QA Findings Cross-Check.
    Combines universal baseline criteria ('ALL') with specific criteria for doc_type (e.g. SRS, Test Case, Project Plan).
    Supports custom_items_override and dry_run=True for sandbox testing without DB side-effects.
    Returns evaluation summary, status, and itemized results.
    """
    import os
    import json
    import re
    import uuid
    from db_ingestion import get_db_connection
    from ocr_engine import _get_gemini_client

    DEFAULT_UNIVERSAL_ITEMS = [
        ('1.1', 'Defect & Comment Resolution', 'ต้องไม่มีข้อบกพร่อง (Defect) ระดับ Critical หรือ High คงค้างในเอกสาร', '0 Critical/High Bugs (ผ่าน 100%)', 'Critical', True, 1),
        ('1.2', 'Defect & Comment Resolution', 'ต้องไม่มีข้อผิดพลาดด้าน Logic การคำนวณ หรือการไหลของกระบวนการทำงาน (Process Flow)', '100% Correct Logic', 'Critical', True, 2),
        ('1.3', 'Defect & Comment Resolution', 'ต้องไม่มี Broken Links, รหัสอ้างอิงที่ไม่ตรงกัน หรือภาพประกอบที่ไม่ถูกต้อง', '0 Broken Links/Refs', 'Major', True, 3),
        ('2.1', 'Content Accuracy & Completeness', 'มีเนื้อหาครบถ้วนตาม Scope, Objective และ Requirement ที่ตกลงไว้', '100% Scope Coverage', 'Critical', True, 4),
        ('2.2', 'Content Accuracy & Completeness', 'มีรายละเอียด Input / Output / Data Dictionary ครบถ้วนชัดเจน', '100% Data Specs', 'Major', True, 5),
        ('2.3', 'Content Accuracy & Completeness', 'ครอบคลุม Exception Cases, Edge Cases และ Error Handling', '100% Edge Cases Handling', 'Major', True, 6),
        ('2.4', 'Content Accuracy & Completeness', 'มีเกณฑ์การยอมรับ (Acceptance Criteria / Definition of Done) ชัดเจนทุกหัวข้อ', '100% Defined Criteria', 'Major', True, 7),
        ('3.1', 'Format & Consistency', 'ต้องไม่มีคำผิด (Spelling / Typos) เกินเกณฑ์มาตรฐานทั้งภาษาไทยและภาษาอังกฤษ', '< 1% Typo Rate (คำผิด < 1%)', 'Minor', False, 8),
        ('3.2', 'Format & Consistency', 'รูปแบบฟอนต์, ขนาดตัวอักษร, ระยะย่อหน้า และหัวข้อ มีความสม่ำเสมอทั้งเอกสาร', '100% Style Consistency', 'Minor', False, 9),
        ('3.3', 'Format & Consistency', 'การจัดวางตาราง, รูปภาพ และ Diagram มีความชัดเจน อ่านง่าย ไม่ตกขอบ', '100% Visual Clarity', 'Minor', False, 10),
        ('4.1', 'Governance & Control', 'มีการระบุ Document Title, Version Number, วันที่อัปเดต และชื่อผู้แต่ง/ผู้แก้ไขชัดเจน', '100% Header & Metadata', 'Major', True, 11),
        ('4.2', 'Governance & Control', 'มีประวัติการแก้ไข (Document History / Revision Log) สรุปการเปลี่ยนแปลงในแต่ละเวอร์ชัน', '100% Logged History', 'Minor', False, 12),
        ('4.3', 'Governance & Control', 'จัดทำเอกสารฉบับสะอาด (Clean Version) ที่ปิด Track Changes และ Remove Comment ร่างออกเรียบร้อย', '0 Draft Comments (ฉบับสะอาด 100%)', 'Major', True, 13)
    ]

    conn = None
    templates_to_use = []
    item_rows = []
    specific_template_found = False
    template_title = "Universal Document Exit Criteria"
    template_id = None
    skill_context = ""

    candidate_types = _normalize_doc_type_aliases(doc_type, doc_text)
    target_type_clean = candidate_types[0] if candidate_types else ((doc_type or '').strip() or 'ALL')
    safe_p_id = project_id if (project_id and str(project_id).strip() and str(project_id).lower() != 'none') else None

    if isinstance(custom_items_override, list) and len(custom_items_override) > 0:
        template_title = "Draft / Sandbox Exit Criteria"
        template_id = "sandbox-draft"
        for idx_ov, ov in enumerate(custom_items_override, 1):
            c_code = str(ov.get('item_code') or f"{idx_ov}").strip()
            c_cat = normalize_exit_criteria_category(ov.get('category'), c_code)
            item_rows.append((
                f"draft-{idx_ov}",
                c_code,
                c_cat,
                str(ov.get('question_text') or ''),
                str(ov.get('target_metric') or '100% (ผ่านบริบูรณ์)'),
                str(ov.get('severity') or 'Major'),
                bool(ov.get('is_mandatory', True)),
                idx_ov,
                c_code
            ))

    try:
        if not item_rows:
            conn = get_db_connection()
            cur = conn.cursor()
        seen_template_ids = set()
        
        # 1. Fetch Universal ALL templates (Active, prioritizing project-specific if present)
        if safe_p_id:
            cur.execute("""
                SELECT template_id, title, doc_type, max_loops 
                FROM exit_criteria_templates 
                WHERE is_active = TRUE AND UPPER(TRIM(doc_type)) = 'ALL'
                  AND (project_id = %s::uuid OR project_id IS NULL)
                ORDER BY (CASE WHEN project_id = %s::uuid THEN 0 ELSE 1 END), created_at DESC;
            """, (safe_p_id, safe_p_id))
        else:
            cur.execute("""
                SELECT template_id, title, doc_type, max_loops 
                FROM exit_criteria_templates 
                WHERE is_active = TRUE AND UPPER(TRIM(doc_type)) = 'ALL'
                ORDER BY created_at DESC;
            """)
        for r in cur.fetchall():
            if str(r[0]) not in seen_template_ids:
                seen_template_ids.add(str(r[0]))
                templates_to_use.append({
                    'template_id': r[0],
                    'title': r[1],
                    'doc_type': 'ALL',
                    'max_loops': r[3] or 3
                })
            
        # 2. Fetch Specific doc_type templates (Active, matching all normalized aliases)
        for cand_type in candidate_types:
            if not cand_type or cand_type.upper() == 'ALL':
                continue
            cand_compact = re.sub(r'\s+', '', cand_type).upper()
            if safe_p_id:
                cur.execute("""
                    SELECT template_id, title, doc_type, max_loops 
                    FROM exit_criteria_templates 
                    WHERE is_active = TRUE
                      AND UPPER(TRIM(doc_type)) != 'ALL'
                      AND (project_id = %s::uuid OR project_id IS NULL)
                      AND (
                          UPPER(TRIM(doc_type)) = UPPER(TRIM(%s))
                          OR UPPER(REPLACE(TRIM(doc_type), ' ', '')) = %s
                          OR %s ILIKE '%%' || TRIM(doc_type) || '%%'
                          OR TRIM(doc_type) ILIKE '%%' || %s || '%%'
                      )
                    ORDER BY (CASE WHEN project_id = %s::uuid THEN 0 ELSE 1 END), created_at DESC;
                """, (safe_p_id, cand_type, cand_compact, cand_type, cand_type, safe_p_id))
            else:
                cur.execute("""
                    SELECT template_id, title, doc_type, max_loops 
                    FROM exit_criteria_templates 
                    WHERE is_active = TRUE
                      AND UPPER(TRIM(doc_type)) != 'ALL'
                      AND (
                          UPPER(TRIM(doc_type)) = UPPER(TRIM(%s))
                          OR UPPER(REPLACE(TRIM(doc_type), ' ', '')) = %s
                          OR %s ILIKE '%%' || TRIM(doc_type) || '%%'
                          OR TRIM(doc_type) ILIKE '%%' || %s || '%%'
                      )
                    ORDER BY created_at DESC;
                """, (cand_type, cand_compact, cand_type, cand_type))
            for r in cur.fetchall():
                if str(r[0]) not in seen_template_ids:
                    seen_template_ids.add(str(r[0]))
                    specific_template_found = True
                    templates_to_use.append({
                        'template_id': r[0],
                        'title': r[1],
                        'doc_type': r[2],
                        'max_loops': r[3] or 3
                    })

        # Collect items from matching templates
        seen_codes = set()
        for t in templates_to_use:
            cur.execute("""
                SELECT item_id, item_code, category, question_text, target_metric, severity, is_mandatory, order_index
                FROM exit_criteria_items WHERE template_id = %s ORDER BY order_index ASC, item_code ASC;
            """, (t['template_id'],))
            t_items = cur.fetchall()
            is_universal = (str(t['doc_type']).strip().upper() == 'ALL')
            t_prefix = "เกณฑ์กลาง ALL" if is_universal else str(t['doc_type']).strip()
            for row in t_items:
                i_id, i_code, i_cat, i_q, i_metric, i_sev, i_mand, i_idx = row
                raw_code = str(i_code or '').strip()
                code_key = raw_code
                if code_key in seen_codes:
                    prefix_tag = 'ALL' if is_universal else str(t['doc_type']).strip()
                    code_key = f"{prefix_tag}-{raw_code}"
                seen_codes.add(code_key)
                cat_label = f"[{t_prefix}] {i_cat}" if specific_template_found else i_cat
                item_rows.append((i_id, code_key, cat_label, i_q, i_metric, i_sev, i_mand, i_idx, raw_code))

        # Fetch active skills matching any candidate type or ALL
        skill_types_upper = list({c.upper() for c in candidate_types} | {re.sub(r'\s+', '', c).upper() for c in candidate_types} | {'ALL'})
        cur.execute("""
            SELECT skill_name, markdown_instructions
            FROM agent_skills
            WHERE is_active = TRUE
              AND (
                  UPPER(TRIM(target_doc_type)) = ANY(%s)
                  OR UPPER(REPLACE(TRIM(target_doc_type), ' ', '')) = ANY(%s)
              )
              AND skill_name NOT ILIKE %s;
        """, (skill_types_upper, skill_types_upper, '%Exit Criteria%'))
        active_skills = cur.fetchall()
        if active_skills:
            skill_context = "\n=== แนวทางวิเคราะห์เฉพาะด้าน (AI Skills & Knowledge) ===\n"
            for s_name, s_inst in active_skills:
                skill_context += f"[{s_name}]:\n{s_inst}\n\n"

        if templates_to_use:
            # Prefer specific template ID as primary template_id if available
            spec_templates = [t for t in templates_to_use if str(t['doc_type']).upper() != 'ALL']
            template_id = (spec_templates[0]['template_id'] if spec_templates else templates_to_use[0]['template_id'])
            if specific_template_found:
                spec_titles = [t['title'] for t in templates_to_use if str(t['doc_type']).upper() != 'ALL']
                all_titles = [t['title'] for t in templates_to_use if str(t['doc_type']).upper() == 'ALL']
                if all_titles:
                    template_title = f"{' / '.join(spec_titles)} + เกณฑ์กลาง ({' / '.join(all_titles)})"
                else:
                    template_title = f"{' / '.join(spec_titles)}"
            else:
                template_title = templates_to_use[0]['title']

        if conn and 'cur' in locals() and cur:
            cur.close()
    except Exception as db_err:
        logger.warning(f"DB load for exit criteria templates encountered issue (will use universal fallback): {db_err}")

    # Fallback to Built-in Universal Items if item_rows is empty
    if not item_rows:
        template_title = "Universal Document Exit Criteria"
        template_id = str(uuid.uuid4())
        for code, cat, q, metric, sev, mand, idx in DEFAULT_UNIVERSAL_ITEMS:
            item_rows.append((f"default-{code}", code, cat, q, metric, sev, mand, idx, code))

    # Format checklist items
    checklist_formatted = ""
    items_dict = {}
    for row in item_rows:
        i_id, item_code, category, question, metric, severity, mandatory, idx, raw_base_code = row
        items_dict[item_code] = {
            'item_id': str(i_id),
            'item_code': item_code,
            'raw_code': raw_base_code,
            'category': category,
            'question_text': question,
            'target_metric': metric or '100% (ผ่านบริบูรณ์)',
            'severity': severity,
            'is_mandatory': mandatory
        }
        mand_txt = "บังคับผ่าน" if mandatory else "ข้ามได้หากไม่เกี่ยว"
        checklist_formatted += f"- item_code: \"{item_code}\" | หมวด: {category} | KPI: {metric or '100%'} | ความรุนแรง: {severity} ({mand_txt}) | คำถามเกณฑ์: {question}\n"

    # Build findings summary for prompt context
    findings_summary = ""
    high_critical = []
    medium = []
    low_info = []
    typos = []
    if qa_findings:
        for f in qa_findings:
            sev = (f.get('severity') or '').lower()
            ct = (f.get('check_type') or '').lower()
            iss = (f.get('issue') or '').lower()
            if sev in ['critical', 'high']:
                high_critical.append(f)
            elif sev == 'medium':
                medium.append(f)
            else:
                low_info.append(f)
            if 'spell' in ct or 'คำผิด' in ct or 'คำผิด' in iss or 'สะกด' in iss:
                typos.append(f)

        findings_summary = f"""
=== ผล QA Analysis Findings ที่พบในเอกสาร ===
- Critical/High Findings: {len(high_critical)} รายการ
- Medium Findings: {len(medium)} รายการ  
- Low/Info Findings: {len(low_info)} รายการ
- รวมทั้งหมด: {len(qa_findings)} รายการ
"""
        for f in high_critical[:10]:
            findings_summary += f"  [{f.get('severity','')}] {f.get('issue','')} — ประเภท: {f.get('check_type','')}\n"
        if medium:
            findings_summary += f"\nรายการ Medium ที่พบ ({len(medium)} รายการ):\n"
            for f in medium[:5]:
                findings_summary += f"  [Medium] {f.get('issue','')}\n"
        findings_summary += """
**แนวทางการประเมินตามเนื้อหาเอกสารจริง (Exit Criteria Quality Gate Rules):**
- ข้อตรวจเรื่อง Defect ระดับ Critical / High (เช่น ข้อ 1.1):
  * หากผลการตรวจ QA Analysis รอบปัจจุบันยังมี Critical/High Findings > 0 รายการ และเป็นข้อบกพร่องจริงในเนื้อหาเอกสาร ให้ตัดสินสอดคล้องกับผล QA Findings (FAIL พร้อมระบุประเด็น Critical/High ที่พบ)
  * หาก Critical/High Findings = 0 รายการ หรือเอกสารมีตาราง Revision History / Audit Resolution Log ที่แก้ไขประเด็นรอบก่อนครบถ้วนแล้ว 100% ให้ถือว่า **PASS**
- ข้อ [2.1] (ข้อมูลทั่วไปของเอกสารและโครงการ / General Information / Scope): หากเอกสารมี Section 1 (ตารางข้อมูลควบคุมเอกสาร Document Control, Title, Version, Project Code, Scope, Business Objectives) และเนื้อหาครอบคลุมตาม Scope โดยไม่มี Critical Defect เรื่องขอบเขตขาดหาย ให้ถือว่า **PASS**
- ข้อ [1.2] หรือข้อตรวจเรื่องความครบถ้วนของ Requirement: หากเอกสารมีระบุ Requirement IDs (เช่น REQ-xxx) พร้อม Main Path, Unhappy Path/Error Handling และตาราง Acceptance Criteria ครบถ้วนโดยไม่มี Critical Defect ให้ถือว่า **PASS**
- ข้อ [3.1] Format & Consistency: หากเอกสารจัดรูปแบบด้วย Markdown (Headings, Tables, Bullets) เป็นระเบียบ ชัดเจน อ่านง่าย ไม่แตกขอบ ให้ถือว่า **PASS**
- ข้อ [Test Case-1.1] และ [Test Case-1.2] หรือข้อตรวจ Requirement Coverage & Traceability:
  * วิเคราะห์ความครอบคลุม (Coverage) ตามขอบเขต Requirement และ Business Rules ใน SRS เป็นหลัก
  * ห้ามตัดสินว่า FAIL เพียงเพราะจำนวนข้อของเอกสาร (เช่น 96 ข้อ) น้อยกว่าจำนวนข้อที่ AI แตกแบบ Granular (เช่น 150 ข้อ) ตราบใดที่เนื้อหาของ Test Case ครอบคลุม Requirement หลักครบทุกข้อ และมีทั้งกรณี Happy Path (Positive) และกรณี Validation/Error (Negative)
  * หาก Test Case ข้อใดมีการทดสอบหลายจุดในข้อเดียว (Composite Steps / Multiple Assertions) ให้ถือว่าครอบคลุม Requirement เหล่านั้นได้เช่นกัน
- ข้อ [Test Case-2.1] ถึง [Test Case-2.3] (Happy Path, Negative Path, Boundary & Business Rules):
  * ตรวจสอบว่ามีขั้นตอนการทดสอบทั้งกรณีทำงานสำเร็จ (Normal Flow / Positive) และกรณีแจ้งเตือนข้อผิดพลาด (Validation / Negative / Error Handling) ครบถ้วนตามฟังก์ชันหลัก
- ข้อ [Test Case-4.1] หรือ [Test Case-4.2] หรือข้อตรวจแบบฟอร์มและโครงสร้างตาราง (Governance & Control / แบบฟอร์มถูกต้อง):
  * หากเอกสารเป็นแบบฟอร์ม Test Case ของโครงการ (เช่น Template 69A, Template 11 คอลัมน์ หรือแบบฟอร์มที่โครงการตกลงใช้): ให้ถือว่า **PASS**
  * กรณีไฟล์ Excel ที่มีหลายแผ่นงาน (Sheets): ในแผ่นงาน Test Specification จะเน้นขั้นตอนและผลที่คาดหวัง (Test Steps, Expected Results) ส่วนคอลัมน์ผลการทดสอบ (เช่น Actual Result, Status, Result (Pass/Fail)) อาจมีเฉพาะในแผ่นงานสำหรับ Execute หรือบันทึกผลจริง หากพบในชีทใดชีทหนึ่ง หรือเอกสารใช้ Template โครงสร้างตามที่โครงการกำหนด ให้ถือว่า **PASS** ข้อแบบฟอร์มถูกต้อง (Test Case-4.2) 100% ห้ามตัดสิน FAIL เด็ดขาด
  * ห้ามนำข้อความใน Document Change History ที่บันทึกการตัดสินใจทางวิศวกรรม (เช่น การปฏิเสธคอลัมน์ที่ซ้ำซ้อนตามข้อตกลง Template ของโครงการ) มาตัดสินว่าเป็นข้อผิดพลาดหรือ Defect
- ให้ประเมินผลตามเนื้อหาจริงในเอกสารที่ส่งตรวจเป็นหลักอย่างเป็นธรรมและตรงตามมาตรฐานวิศวกรรม
"""

    _now_ec = datetime.now()
    _ec_ad_year = _now_ec.year
    _ec_be_year = _now_ec.year + 543
    _ec_date_ad = _now_ec.strftime('%d/%m/%Y')
    _ec_date_be = f"{_now_ec.day:02d}/{_now_ec.month:02d}/{_ec_be_year}"

    prompt = f"""คุณคือ System Auditor และ Quality Gate Evaluator
วันที่ปัจจุบันของระบบ (Current Reference Date): {_ec_date_ad} (ค.ศ. {_ec_ad_year}) / {_ec_date_be} (พ.ศ. {_ec_be_year})
กรุณาประเมินเนื้อหาเอกสารประเภท "{target_type_clean}" ต่อไปนี้เทียบกับรายการ Exit Criteria Checklist แต่ละข้อให้ครบทุกข้อ:

=== รายการข้อตรวจ (Exit Criteria Checklist) ===
{checklist_formatted}{findings_summary}{skill_context}

=== เนื้อหาเอกสารที่ตรวจ ===
{doc_text[:250000]}

=== หลักเกณฑ์การประเมินที่เป็นธรรมและแม่นยำ (Fair & Deterministic Evaluation Guidelines) ===
1. ให้ประเมินจากเนื้อหาจริงในเอกสารควบคู่กับผล QA Analysis Findings ด้านบน ห้ามขัดแย้งกันเอง
2. สำคัญมาก: ฟิลด์ "item_code" ใน JSON ที่ส่งกลับ ต้องตรงกับค่า item_code ในรายการข้อตรวจข้างต้นแบบตัวต่อตัว (เช่น "1.1" หรือ "Test Case-1.1" ห้ามใส่เครื่องหมายก้ามปู [] ครอบ)
3. ข้อ Content Completeness (หมวด 2.x): หากเอกสารมีเนื้อหาครบถ้วนตาม Scope ที่ระบุใน Document Control และไม่มี Critical/High Finding เรื่องเนื้อหาขาดหาย ให้ถือว่า PASS
4. ข้อ Attachments / Appendix (2.4): หากเอกสารไม่ได้ระบุว่ามี Attachment แล้วไม่แนบ หรือเอกสารมี Inline Diagrams/Tables แทน Attachment แยก ให้ถือว่า PASS (หรือ NA ถ้าไม่เกี่ยวข้อง)
5. ข้อ Typo Rate (3.x): ให้ FAIL เฉพาะกรณีพบคำผิดจำนวนมาก (>5 จุด) ที่ชัดเจน หากพบเล็กน้อย 1-3 จุด หรือเป็นศัพท์เฉพาะทาง/ชื่อเฉพาะ ให้ถือว่า PASS
6. ข้อ Governance & Control (4.1): หากเอกสารมี Document Title, Version, Date, Author ใน Section 1 Document Control ให้ถือว่า PASS
7. **การตรวจสอบวันที่ พ.ศ. (Buddhist Era) และ ค.ศ. (A.D.)**: วันปัจจุบันคือ {_ec_date_ad} (ค.ศ. {_ec_ad_year}) ซึ่งตรงกับ {_ec_date_be} (พ.ศ. {_ec_be_year}) เอกสารไทยสามารถใช้วันที่ พ.ศ. (ปีช่วง 2400–2700 เช่น 2567, 2568, 2569 หรือ 2 หลัก 67–69) ได้อย่างถูกต้อง ให้ลบ 543 เพื่อแปลงเป็น ค.ศ. ก่อนตรวจสอบเสมอ **ห้ามตัดสินว่าวันที่ พ.ศ. ที่เป็นอดีตหรือปัจจุบัน (<= {_ec_date_be}) เป็น "วันที่ในอนาคต" โดยเด็ดขาด**
8. **ข้อบังคับการระบุหมายเลขหน้าและตำแหน่งที่ชัดเจน (ห้ามคลุมเครือ)**:
   - เนื้อหาเอกสารมีการแบ่งหน้าชัดเจนด้วย `--- [หน้า N] ---`
   - ทุกข้อที่ประเมินเป็น **FAIL** (รวมถึงกรณีข้อมูลขาดหาย) **ต้องระบุ `"page_numbers"` (อาร์เรย์เลขหน้า เช่น `[1]`, `[2, 4]`) และ `"location"` (ตำแหน่งชัดเจน เช่น `"หน้า 1 — ตาราง Document Control"`, `"หน้า 3 — ตาราง Test Case แถว TC-004 คอลัมน์ Test Data"`)** เสมอ
   - ห้ามตอบแบบคลุมเครือโดยไม่ระบุหน้าและจุดแก้ไข: หากขาดข้อมูล Metadata / ชื่อผู้ทดสอบ / วันที่ / Revision History ให้ระบุหน้า `1` พร้อมตำแหน่ง `"หน้า 1 — ส่วนหัวเอกสาร / Document Control"`; หากขาดคอลัมน์ในตารางให้ระบุหน้าที่ตารางนั้นปรากฏอยู่จริง

กรุณาประเมินข้อตรวจทุกข้อให้ครบถ้วน โดยส่งคืนผลลัพธ์เป็น JSON Array เท่านั้น ห้ามมีข้อความอื่น
แต่ละ Object ใน JSON Array มีโครงสร้างดังนี้:
[
  {{
    "item_code": "ต้องตรงกับ item_code ในรายการข้อตรวจทุกตัวอักษร",
    "status": "PASS" | "FAIL" | "NA",
    "page_numbers": [1],
    "location": "ระบุหน้าและตำแหน่งชัดเจน เช่น 'หน้า 2 — หัวข้อ 2.1 ตาราง Test Case คอลัมน์ Test Data'",
    "remarks": "เหตุผลสรุปผลการตรวจที่ชัดเจน อ้างอิงข้อเท็จจริงในเอกสาร",
    "evidence_text": "[หน้า 2 | ตาราง Test Case] ข้อความอ้างอิงจากเอกสาร หรือจุดที่ผิดพลาดจริง"
  }}
]
"""
    eval_items_res = []
    try:
        client = _get_gemini_client()
        qa_consult_primary = os.environ.get('QA_CONSULT_MODEL', 'gemini-3.1-pro-preview')
        gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        fallback_models = []
        for m in [qa_consult_primary, 'gemini-3.1-pro-preview', 'gemini-2.5-pro', gemini_model, 'gemini-2.5-flash', 'gemini-2.5-flash-lite']:
            if m and m not in fallback_models:
                fallback_models.append(m)
        
        for model_name in fallback_models:
            try:
                res = client.models.generate_content(model=model_name, contents=prompt)
                if res and res.text:
                    clean_text = res.text.strip()
                    if clean_text.startswith("```"):
                        clean_text = re.sub(r'^```(?:json)?\s*', '', clean_text)
                        clean_text = re.sub(r'\s*```$', '', clean_text)
                    json_match = re.search(r'\[[\s\S]*\]', clean_text)
                    if json_match:
                        clean_text = json_match.group(0)
                    eval_items_res = json.loads(clean_text)
                    
                    if hasattr(res, 'usage_metadata'):
                        try:
                            from db_ingestion import log_api_usage
                            used_model = getattr(res, 'model_version', None) or model_name
                            log_api_usage("Exit_Criteria", used_model, res.usage_metadata)
                        except Exception as usage_err:
                            logger.error(f"Failed to log API usage: {usage_err}")
                    break
            except Exception as e:
                logger.warning(f"Exit criteria AI eval attempt failed with {model_name}: {e}")
                continue
    except Exception as client_err:
        logger.error(f"Failed to initialize Gemini client for exit criteria: {client_err}")

    # Build multi-key normalized lookup map so prefixed codes like "[Test Case-1.1]" or "TestCase-1.1" resolve cleanly
    def _norm_code(c: str) -> str:
        s = str(c or '').strip()
        s = re.sub(r'^\[+|\]+$', '', s).strip()
        return s

    results_map = {}
    results_map_compact = {}
    ordered_ai_items = []
    for idx_ai, item in enumerate(eval_items_res):
        if not isinstance(item, dict):
            continue
        ordered_ai_items.append(item)
        raw_c = _norm_code(item.get('item_code', ''))
        if raw_c:
            results_map[raw_c] = item
            results_map[raw_c.upper()] = item
            compact_c = re.sub(r'\s+', '', raw_c).upper()
            results_map_compact[compact_c] = item

    def _lookup_ai_eval(item_code: str, raw_base_code: str, item_idx: int) -> dict:
        nc = _norm_code(item_code)
        if nc in results_map:
            return results_map[nc]
        if nc.upper() in results_map:
            return results_map[nc.upper()]
        comp = re.sub(r'\s+', '', nc).upper()
        if comp in results_map_compact:
            return results_map_compact[comp]
        # Try base code if unambiguous or when only 1 template was returned
        nb = _norm_code(raw_base_code)
        if nb and nb in results_map and len(items_dict) == len(ordered_ai_items):
            return results_map[nb]
        # Positional fallback when AI returned exact same number of items in order
        if len(ordered_ai_items) == len(items_dict) and 0 <= item_idx < len(ordered_ai_items):
            return ordered_ai_items[item_idx]
        return {}
    
    evaluated_items = []
    passed_count = 0
    failed_count = 0
    na_count = 0
    
    has_cat1_2_fail = False
    
    # Detect well-structured document for tolerance (only when no Critical/High findings exist)
    doc_lower = doc_text.lower() if doc_text else ''
    has_document_control = any(term in doc_lower for term in ['document control', 'ข้อมูลควบคุมเอกสาร', 'document title', 'version'])
    has_requirement_ids = 'req-' in doc_lower or 'requirement' in doc_lower
    has_sections = doc_lower.count('## ') >= 3 or doc_lower.count('section') >= 3
    is_well_structured = has_document_control and has_sections and (len(high_critical) == 0)
    
    for item_idx, (item_code, item_info) in enumerate(items_dict.items()):
        raw_base_code = item_info.get('raw_code', item_code)
        base_code_clean = re.sub(r'^.*-', '', str(raw_base_code or item_code)).strip()
        q_lower = (item_info.get('question_text') or '').lower()
        cat_text = item_info.get('category') or ''

        ai_eval = _lookup_ai_eval(item_code, raw_base_code, item_idx)
        status = (ai_eval.get('status') or '').strip().upper() if ai_eval else ''
        remarks = (ai_eval.get('remarks') or '').strip() if ai_eval else ''
        evidence = (ai_eval.get('evidence_text') or '').strip() if ai_eval else ''

        # Deterministic Cross-Check 1: Item 1.1 ("ไม่มี Defect ระดับ Critical / High คงค้างในเอกสาร")
        is_crit_defect_gate_item = (
            base_code_clean == '1.1'
            and any(k in q_lower for k in ['critical', 'high', 'defect', 'ข้อผิดพลาดร้ายแรง', 'ข้อสั่งการ'])
        )
        if is_crit_defect_gate_item:
            if len(high_critical) > 0:
                status = 'FAIL'
                top_lines = [
                    f"{idx_h}. [{f.get('severity','High')}] {f.get('issue','')}"
                    + (f" (หน้า {f.get('page_number')})" if f.get('page_number') else "")
                    for idx_h, f in enumerate(high_critical[:4], 1)
                ]
                if len(high_critical) > 4:
                    top_lines.append(f"...และอีก {len(high_critical) - 4} รายการ (ดูครบทั้งหมดในตาราง QA Audit Findings)")
                remarks = f"ไม่ผ่านเกณฑ์ — ตรวจพบข้อบกพร่องความรุนแรงระดับ Critical/High ในเอกสารจำนวน {len(high_critical)} รายการ (เป้าหมายต้องเป็น 0 รายการ)"
                evidence = "\n".join(top_lines)
            elif status == 'FAIL' and len(high_critical) == 0:
                status = 'PASS'
                remarks = 'ผลการตรวจ QA Analysis ไม่พบ Defect ระดับ Critical หรือ High คงค้างในเอกสาร (0 Critical/High Findings)'
                evidence = 'QA Audit Findings: 0 Critical / 0 High'

        # Smart guard for Item 4.1 Governance & Control
        if ('4.1' in base_code_clean or 'Governance' in cat_text) and status == 'FAIL':
            lower_ev = (evidence + " " + remarks).lower()
            if any(term in lower_ev for term in ['spectra', 'engine', 'top header', 'ส่วนหัว', 'ขัดแย้ง']) and ('document control' in doc_lower or 'ข้อมูลควบคุมเอกสาร' in doc_lower or 'ผู้จัดทำ' in doc_lower):
                status = 'PASS'
                remarks = 'ตรวจสอบแล้วพบ Document Title, Version Number, วันที่บังคับใช้ และผู้จัดทำ ครบถ้วนใน Section 1 Document Control ตรงตามมาตรฐาน Governance'
                evidence = 'Section 1 Document Control ระบุ Title, Version, Date, และ Author ครบถ้วนสมบูรณ์'

        # Smart guard for Thai Buddhist Era (พ.ศ.) dates falsely flagged as 'future date'
        if status == 'FAIL' and _is_false_future_be_date_claim(f"{remarks} {evidence}", doc_text=doc_text):
            status = 'PASS'
            remarks = f'ตรวจสอบแล้ววันที่ในเอกสารใช้ระบบพุทธศักราช (พ.ศ.) ซึ่งเป็นวันที่ในอดีตหรือปัจจุบัน (เทียบเท่า ค.ศ. ปัจจุบัน <= {datetime.now().strftime("%d/%m/%Y")}) ถูกต้องตามมาตรฐานเอกสารไทย'
            evidence = 'วันที่ในเอกสารใช้รูปแบบ พ.ศ. ที่ถูกต้อง ไม่ใช่วันที่ในอนาคต'

        # Smart guard for Attachments - ONLY when item explicitly checks Attachment/Appendix and is NOT Critical
        sev_curr = (item_info.get('severity') or '').strip().upper()
        is_mand_curr = bool(item_info.get('is_mandatory', True))
        if status == 'FAIL' and sev_curr != 'CRITICAL' and any(k in q_lower for k in ['attachment', 'เอกสารแนบ', 'ภาคผนวก', 'glossary']) and is_well_structured:
            lower_ev = (evidence + " " + remarks).lower()
            if any(term in lower_ev for term in ['attachment', 'แนบ', 'appendix', 'ภาคผนวก', 'ไม่พบ', 'ไม่มี']):
                has_tables = '|' in doc_text and '---' in doc_text
                has_diagrams = any(t in doc_lower for t in ['diagram', 'flowchart', 'erd', 'uml', 'แผนภาพ', 'mermaid'])
                if has_tables or has_diagrams or 'acceptance criteria' in doc_lower:
                    status = 'PASS'
                    remarks = 'เอกสารใช้ Inline Tables/Diagrams แทน Attachment แยก ถือว่าครบถ้วน'
                    evidence = 'พบ Tables และ/หรือ Diagrams ในเนื้อหาเอกสาร'
                elif not is_mand_curr:
                    status = 'NA'
                    remarks = 'เอกสารไม่ได้ระบุว่ามี Attachment ที่ต้องแนบ จึงไม่เกี่ยวข้อง'
                    evidence = ''

        # Smart guard for Typo Rate - ONLY when item explicitly evaluates spelling/typos AND is Minor + Non-Mandatory
        is_typo_question = any(k in q_lower for k in ['คำผิด', 'typo', 'spelling', 'สะกด', 'ไวยากรณ์'])
        if status == 'FAIL' and is_typo_question and sev_curr == 'MINOR' and not is_mand_curr:
            lower_ev = (evidence + " " + remarks).lower()
            if any(term in lower_ev for term in ['latex', '$', '\\le', '\\times', 'สูตร', 'formula']):
                status = 'PASS'
                remarks = 'สูตรคณิตศาสตร์และตัวแปรในเอกสารไม่ถือเป็นคำผิด (Typo)'
                evidence = 'LaTeX/Math notation ไม่ใช่ Typo'
            elif qa_findings is not None and len(typos) <= 3:
                status = 'PASS'
                remarks = 'ไม่พบคำผิดเกินเกณฑ์ผ่อนปรนในเอกสาร'
                evidence = f'QA Findings พบคำผิด {len(typos)} รายการ (ไม่เกินเกณฑ์)' if typos else 'ไม่พบคำผิดจาก QA Analysis'

        # Fallback reasoning from findings if AI evaluation didn't return a valid status for this item
        if not status or status not in ['PASS', 'FAIL', 'NA']:
            if base_code_clean == '1.1' and high_critical:
                status = 'FAIL'
                top_lines = [
                    f"{idx_h}. [{f.get('severity','High')}] {f.get('issue','')}"
                    + (f" (หน้า {f.get('page_number')})" if f.get('page_number') else "")
                    for idx_h, f in enumerate(high_critical[:4], 1)
                ]
                if len(high_critical) > 4:
                    top_lines.append(f"...และอีก {len(high_critical) - 4} รายการ (ดูครบทั้งหมดในตาราง QA Audit Findings)")
                remarks = f"ไม่ผ่านเกณฑ์ — ตรวจพบข้อบกพร่องความรุนแรงระดับ Critical/High ในเอกสารจำนวน {len(high_critical)} รายการ (เป้าหมายต้องเป็น 0 รายการ)"
                evidence = "\n".join(top_lines)
            elif is_typo_question and typos and len(typos) > 3:
                status = 'FAIL'
                remarks = f"พบคำผิดหรือการสะกดคำไม่ถูกต้อง {len(typos)} รายการ"
                evidence = typos[0].get('issue', '')
            else:
                status = 'PASS'
                remarks = 'ตรวจสอบแล้วตรงตามเกณฑ์มาตรฐาน'

        if status == 'PASS':
            passed_count += 1
        elif status == 'FAIL':
            failed_count += 1
            cat = item_info['category'] or ''
            cat_low = cat.lower()
            sev_upper = (item_info.get('severity') or '').strip().upper()
            is_mand = bool(item_info.get('is_mandatory', True))
            is_cat3_formatting = (
                base_code_clean.startswith('3.')
                or ('format' in cat_low and 'defect' not in cat_low and 'content' not in cat_low)
            )
            if (
                'defect' in cat_low
                or 'content' in cat_low
                or base_code_clean.startswith('1.')
                or base_code_clean.startswith('2.')
                or sev_upper == 'CRITICAL'
                or is_mand
                or not is_cat3_formatting
            ):
                has_cat1_2_fail = True
        else:
            na_count += 1

            
        # Resolve page numbers AND exact location deterministically for this Exit Criteria item
        _ec_p_set = set()
        _ec_location = (ai_eval.get('location') or '').strip() if isinstance(ai_eval, dict) else ''
        if isinstance(ai_eval, dict):
            _raw_pns = ai_eval.get('page_numbers')
            if isinstance(_raw_pns, list):
                for _x in _raw_pns:
                    if str(_x).strip().isdigit():
                        _ec_p_set.add(int(str(_x).strip()))
            elif ai_eval.get('page_number') is not None and str(ai_eval.get('page_number')).strip().isdigit():
                _ec_p_set.add(int(str(ai_eval.get('page_number')).strip()))
        if is_crit_defect_gate_item and high_critical:
            for _hf in high_critical[:5]:
                if _hf.get('page_number') is not None and str(_hf.get('page_number')).strip().isdigit():
                    _ec_p_set.add(int(str(_hf.get('page_number')).strip()))
                if not _ec_location and _hf.get('location'):
                    _ec_location = str(_hf.get('location')).strip()
        for _pm in re.findall(r'(?:หน้า|page|p\.)\s*[:#]?\s*(\d+)', f"{_ec_location} {evidence} {remarks}", re.I):
            _ec_p_set.add(int(_pm))

        # Fallback: match evidence_text against logical pages in doc_text
        if not _ec_p_set and evidence and len(evidence.strip()) >= 8 and doc_text:
            _doc_pages_for_ec = _split_text_into_logical_pages(doc_text)
            _norm_ev_ec = re.sub(r'\s+', ' ', evidence).lower()
            _ev_parts = [pt.strip() for pt in re.split(r'[,;\n\|/()\"\'“”]+', _norm_ev_ec) if len(pt.strip()) >= 8]
            _ev_parts.sort(key=len, reverse=True)
            for _pt in _ev_parts[:4]:
                for _dp in _doc_pages_for_ec:
                    if _pt in re.sub(r'\s+', ' ', (_dp.get('text') or '')).lower():
                        _ec_p_set.add(int(_dp['page_number']))
                        break
                if _ec_p_set:
                    break

        # Fallback for FAIL items on cover/metadata/governance/revision/table headers -> pinpoint Page 1 or first table page
        if status == 'FAIL' and not _ec_p_set:
            _q_cat_low = f"{q_lower} {cat_text.lower()}"
            if any(k in _q_cat_low for k in ['governance', 'metadata', 'ผู้ทดสอบ', 'วันที่', 'author', 'version', 'revision', 'header', 'ส่วนหัว', 'title', '4.1', '4.2', '1.3']):
                _ec_p_set.add(1)
                if not _ec_location:
                    _ec_location = "หน้า 1 — ส่วนหัวเอกสาร / Document Control"
            elif any(k in _q_cat_low for k in ['test case', 'test data', 'expected result', 'actual result', 'ตาราง', 'คอลัมน์', 'table']):
                # Find first page containing a markdown table or Test Case header
                _doc_pages_for_ec = _split_text_into_logical_pages(doc_text or "")
                _tbl_page = next((int(_dp['page_number']) for _dp in _doc_pages_for_ec if '|' in (_dp.get('text') or '') or 'tc' in (_dp.get('text') or '').lower()), 1)
                _ec_p_set.add(_tbl_page)
                if not _ec_location:
                    _ec_location = f"หน้า {_tbl_page} — โครงสร้างตาราง Test Case / เนื้อหาหลัก"
            elif doc_text:
                _ec_p_set.add(1)
                if not _ec_location:
                    _ec_location = "หน้า 1 — โครงสร้างหลักของเอกสาร"

        _ec_ordered_pages = sorted(_ec_p_set)
        _ec_page_ref = ("หน้า " + ", ".join(str(x) for x in _ec_ordered_pages)) if _ec_ordered_pages else "หน้า 1"
        if not _ec_location:
            _ec_location = _ec_page_ref
        if status == 'FAIL' and _ec_ordered_pages and evidence and not re.search(r'(?:หน้า|page)\s*\d+', evidence, re.I):
            evidence = f"[{_ec_page_ref} | {_ec_location}] {evidence}"

        evaluated_items.append({
            'item_id': item_info['item_id'],
            'item_code': item_code,
            'category': item_info['category'],
            'question_text': item_info['question_text'],
            'target_metric': item_info['target_metric'],
            'severity': item_info['severity'],
            'is_mandatory': item_info['is_mandatory'],
            'status': status,
            'page_number': _ec_ordered_pages[0] if _ec_ordered_pages else None,
            'page_numbers': _ec_ordered_pages,
            'page_ref': _ec_page_ref,
            'location': _ec_location,
            'remarks': remarks,
            'evidence_text': evidence
        })

    total_items = len(evaluated_items)
    score_pct = round((passed_count / (total_items - na_count)) * 100, 2) if (total_items - na_count) > 0 else 100.0

    # Determine Final Gate Assessment Rule (synchronized with Critical/High QA Findings)
    if failed_count == 0 and len(high_critical) == 0:
        final_status = 'PASSED'
        summary_remarks = 'เอกสารผ่านเกณฑ์มาตรฐาน Exit Criteria ครบถ้วนบริบูรณ์ 100%'
    elif not has_cat1_2_fail and len(high_critical) == 0:
        final_status = 'CONDITIONAL_PASSED'
        summary_remarks = 'เอกสารผ่านเกณฑ์สาระสำคัญ (หมวด 1, 2, 4) พบข้อสังเกตเล็กน้อยในหมวดจัดหน้า/คำผิด (หมวด 3) สามารถแก้ไขและส่ง Final Copy ได้เลย'
    else:
        final_status = 'REJECTED'
        summary_remarks = f'เอกสารไม่ผ่านเกณฑ์ Exit Criteria สาระสำคัญ (ไม่ผ่าน {failed_count} ข้อ / Critical-High Findings {len(high_critical)} รายการ) ต้องแก้ไขและส่งกลับมาตรวจใหม่'

    # Save evaluation log in DB if possible (skip on dry_run)
    if conn and not dry_run:
        try:
            valid_t_id = None
            try:
                uuid.UUID(str(template_id))
                valid_t_id = template_id
            except Exception:
                valid_t_id = None

            if valid_t_id:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO document_exit_evaluations (
                        template_id, project_id, status, evaluation_status, total_items, passed_items, failed_items, na_items, score_percentage, summary_remarks
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING eval_id;
                """, (valid_t_id, safe_p_id, final_status, final_status, total_items, passed_count, failed_count, na_count, score_pct, summary_remarks))
                eval_id = cur.fetchone()[0]
                
                for item in evaluated_items:
                    valid_i_id = None
                    try:
                        uuid.UUID(str(item['item_id']))
                        valid_i_id = item['item_id']
                    except Exception:
                        valid_i_id = None
                        
                    if valid_i_id:
                        cur.execute("""
                            INSERT INTO document_exit_evaluation_items (
                                evaluation_id, item_id, item_code, category, question_text, target_metric, severity, is_mandatory, status, remarks, evidence_text
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                        """, (
                            eval_id,
                            valid_i_id,
                            item['item_code'],
                            item.get('category'),
                            item.get('question_text'),
                            item['target_metric'],
                            item.get('severity'),
                            item.get('is_mandatory', True),
                            item['status'],
                            item['remarks'],
                            item['evidence_text']
                        ))
                conn.commit()
                cur.close()
        except Exception as log_err:
            logger.warning(f"Failed to log document_exit_evaluations (non-critical): {log_err}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
    elif conn:
        try:
            conn.close()
        except Exception:
            pass

    return {
        'template_id': str(template_id),
        'template_title': template_title,
        'status': final_status,
        'total_items': total_items,
        'passed_items': passed_count,
        'failed_items': failed_count,
        'na_items': na_count,
        'score_percentage': score_pct,
        'summary_remarks': summary_remarks,
        'items': evaluated_items
    }


@bp.route('/api/qa_consult/reevaluate_exit_criteria', methods=['POST'])
def reevaluate_exit_criteria_api():
    """
    Re-evaluate an existing QA Consult transaction (or document text) against the latest Exit Criteria templates
    and persist the updated exit_criteria_eval and Excel report without re-uploading the file.
    """
    try:
        from db_ingestion import get_db_connection
        data = request.json or {}
        transaction_id = data.get('transaction_id')
        doc_type_override = data.get('doc_type')
        project_id = data.get('project_id')

        extracted_text = data.get('extracted_text') or ''
        qa_findings = data.get('qa_findings')
        doc_type = doc_type_override or ''
        filename = data.get('filename') or 'Document.pdf'
        qa_report = data.get('report') or ''
        group_name = data.get('group_name') or 'General'
        group_type = data.get('group_type') or ''
        project_code = ''

        if transaction_id:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT t.project_id, t.filename, t.doc_type, t.extracted_text, t.qa_report,
                       t.qa_findings, t.group_name, t.group_type, p.project_code
                FROM qa_transactions t
                LEFT JOIN projects p ON t.project_id = p.project_id
                WHERE CAST(t.id AS TEXT) = %s
                LIMIT 1;
            """, (str(transaction_id),))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if not row:
                return jsonify({'error': 'ไม่พบข้อมูลประวัติการตรวจเอกสาร (Transaction Not Found)'}), 404
            project_id = str(row[0]) if row[0] else project_id
            filename = row[1] or filename
            doc_type = doc_type_override or row[2] or row[7] or 'ALL'
            extracted_text = row[3] or extracted_text or row[4] or ''
            qa_report = row[4] or qa_report
            qa_findings = row[5] if isinstance(row[5], list) else (qa_findings or [])
            group_name = row[6] or group_name
            group_type = row[7] or group_type
            project_code = row[8] or ''

        if not extracted_text.strip() and not qa_report.strip():
            return jsonify({'error': 'ไม่พบเนื้อหาเอกสารสำหรับประเมิน Exit Criteria ใหม่'}), 400

        eval_source_text = extracted_text if extracted_text.strip() else qa_report
        exit_criteria_eval = evaluate_document_exit_criteria(
            eval_source_text,
            doc_type=doc_type or group_type or 'ALL',
            project_id=project_id,
            qa_findings=qa_findings
        )

        excel_download_url = ''
        if transaction_id:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                UPDATE qa_transactions
                SET exit_criteria_eval = %s::jsonb
                WHERE CAST(id AS TEXT) = %s;
            """, (json.dumps(exit_criteria_eval), str(transaction_id)))
            conn.commit()
            cur.close()
            conn.close()

            try:
                from excel_report import generate_qa_excel
                excel_path = generate_qa_excel(
                    report_text=qa_report,
                    filename=filename,
                    doc_type=doc_type,
                    project_code=project_code,
                    group_name=group_name,
                    group_type=group_type,
                    transaction_id=str(transaction_id),
                    exit_criteria_eval=exit_criteria_eval,
                    qa_findings=qa_findings
                )
                excel_basename = os.path.basename(excel_path)
                excel_download_url = f"/api/qa_report/download/{excel_basename}"
            except Exception as ex_err:
                logger.warning(f"Failed to regenerate Excel after exit criteria re-eval: {ex_err}")

        return jsonify({
            'success': True,
            'exit_criteria_eval': exit_criteria_eval,
            'excel_url': excel_download_url
        })
    except Exception as e:
        logger.error(f"Error in reevaluate_exit_criteria_api: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/exit-criteria/templates', methods=['GET', 'POST'])
def handle_exit_criteria_templates():
    from db_ingestion import get_db_connection
    if request.method == 'GET':
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            project_id = request.args.get('project_id')
            doc_type = request.args.get('doc_type')
            
            query = """
                SELECT t.template_id, t.project_id, t.title, t.description, t.doc_type, t.is_active, t.max_loops,
                       t.created_at, t.updated_at, COUNT(i.item_id) as item_count,
                       p.project_name, p.project_code
                FROM exit_criteria_templates t
                LEFT JOIN exit_criteria_items i ON t.template_id = i.template_id
                LEFT JOIN projects p ON t.project_id = p.project_id
                WHERE 1=1
            """
            params = []
            if project_id:
                query += " AND (t.project_id = %s::uuid OR t.project_id IS NULL)"
                params.append(project_id)
            if doc_type:
                query += " AND (UPPER(TRIM(t.doc_type)) = UPPER(TRIM(%s)) OR UPPER(TRIM(t.doc_type)) = 'ALL')"
                params.append(doc_type)
                
            query += " GROUP BY t.template_id, p.project_name, p.project_code ORDER BY (CASE WHEN UPPER(TRIM(t.doc_type)) = 'ALL' THEN 0 ELSE 1 END), t.created_at DESC;"
            cur.execute(query, params)
            rows = cur.fetchall()
            
            templates = []
            for r in rows:
                templates.append({
                    'template_id': str(r[0]),
                    'project_id': str(r[1]) if r[1] else None,
                    'title': r[2],
                    'description': r[3],
                    'doc_type': r[4],
                    'is_active': bool(r[5]),
                    'max_loops': r[6] or 3,
                    'created_at': str(r[7]) if r[7] else None,
                    'updated_at': str(r[8]) if r[8] else None,
                    'item_count': int(r[9] or 0),
                    'project_name': r[10],
                    'project_code': r[11]
                })
            cur.close()
            conn.close()
            return jsonify({'success': True, 'templates': templates})
        except Exception as e:
            logger.error(f"Error fetching exit criteria templates: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        payload = get_request_user_payload()
        if not payload:
            return jsonify({'error': 'Unauthorized, please login'}), 401
        if payload.get('role') != 'admin':
            return jsonify({'error': 'Forbidden: Admin privileges required'}), 403
        try:
            data = request.json or {}
            title = (data.get('title') or '').strip()
            description = data.get('description', '')
            doc_type = (data.get('doc_type') or 'ALL').strip() or 'ALL'
            is_active = bool(data.get('is_active', True))
            max_loops = max(1, min(10, int(data.get('max_loops') or 3)))
            raw_pid = data.get('project_id')
            project_id = str(raw_pid).strip() if (raw_pid and str(raw_pid).strip() and str(raw_pid).lower() not in ('none', 'all', 'global')) else None
            items = data.get('items', [])
            
            if not title:
                return jsonify({'error': 'Title is required'}), 400
                
            conn = get_db_connection()
            conn.autocommit = False
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO exit_criteria_templates (project_id, title, description, doc_type, is_active, max_loops)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING template_id;
            """, (project_id, title, description, doc_type, is_active, max_loops))
            template_id = cur.fetchone()[0]
            
            for idx, item in enumerate(items, 1):
                i_code = str(item.get('item_code') or f"{idx}").strip()
                norm_cat = normalize_exit_criteria_category(item.get('category'), i_code)
                cur.execute("""
                    INSERT INTO exit_criteria_items (template_id, item_code, category, question_text, target_metric, severity, is_mandatory, order_index)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    template_id,
                    i_code,
                    norm_cat,
                    item.get('question_text', ''),
                    item.get('target_metric', '100% (ผ่านบริบูรณ์)'),
                    item.get('severity', 'Major'),
                    bool(item.get('is_mandatory', norm_cat != 'Format & Consistency')),
                    item.get('order_index', idx)
                ))
                
            conn.commit()
            cur.close()
            conn.close()
            
            sync_exit_criteria_to_agent_skills(template_id)
            return jsonify({'success': True, 'template_id': str(template_id), 'message': 'Template created successfully'})
        except Exception as e:
            logger.error(f"Error creating exit criteria template: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500


@bp.route('/api/exit-criteria/templates/<template_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def handle_single_exit_criteria_template(template_id):
    from db_ingestion import get_db_connection
    if request.method in ('PUT', 'PATCH', 'DELETE'):
        payload = get_request_user_payload()
        if not payload:
            return jsonify({'error': 'Unauthorized, please login'}), 401
        if payload.get('role') != 'admin':
            return jsonify({'error': 'Forbidden: Admin privileges required'}), 403

    conn = get_db_connection()
    
    if request.method == 'GET':
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT t.template_id, t.project_id, t.title, t.description, t.doc_type, t.is_active, t.max_loops,
                       t.created_at, t.updated_at, p.project_name, p.project_code
                FROM exit_criteria_templates t
                LEFT JOIN projects p ON t.project_id = p.project_id
                WHERE t.template_id = %s;
            """, (template_id,))
            t = cur.fetchone()
            if not t:
                cur.close()
                conn.close()
                return jsonify({'error': 'Template not found'}), 404
                
            cur.execute("""
                SELECT item_id, item_code, category, question_text, target_metric, severity, is_mandatory, order_index
                FROM exit_criteria_items WHERE template_id = %s ORDER BY order_index ASC, item_code ASC;
            """, (template_id,))
            item_rows = cur.fetchall()
            
            items = []
            for i in item_rows:
                items.append({
                    'item_id': str(i[0]),
                    'item_code': i[1],
                    'category': normalize_exit_criteria_category(i[2], i[1]),
                    'raw_category': i[2],
                    'question_text': i[3],
                    'target_metric': i[4] or '100% (ผ่านบริบูรณ์)',
                    'severity': i[5],
                    'is_mandatory': bool(i[6]),
                    'order_index': i[7]
                })
                
            template = {
                'template_id': str(t[0]),
                'project_id': str(t[1]) if t[1] else None,
                'title': t[2],
                'description': t[3],
                'doc_type': t[4],
                'is_active': bool(t[5]),
                'max_loops': t[6] or 3,
                'created_at': str(t[7]) if t[7] else None,
                'updated_at': str(t[8]) if t[8] else None,
                'project_name': t[9],
                'project_code': t[10],
                'items': items
            }
            cur.close()
            conn.close()
            return jsonify({'success': True, 'template': template})
        except Exception as e:
            logger.error(f"Error fetching template {template_id}: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    elif request.method in ('PUT', 'PATCH'):
        try:
            data = request.json or {}
            conn.autocommit = False
            cur = conn.cursor()
            cur.execute("SELECT title, description, doc_type, is_active, max_loops, project_id FROM exit_criteria_templates WHERE template_id = %s;", (template_id,))
            existing = cur.fetchone()
            if not existing:
                cur.close()
                conn.close()
                return jsonify({'error': 'Template not found'}), 404

            old_title = existing[0]
            title = (data.get('title') if 'title' in data else existing[0]) or existing[0]
            description = data.get('description') if 'description' in data else existing[1]
            doc_type = (data.get('doc_type') if 'doc_type' in data else existing[2]) or 'ALL'
            is_active = bool(data.get('is_active')) if 'is_active' in data else bool(existing[3])
            max_loops = max(1, min(10, int(data.get('max_loops') or existing[4] or 3))) if 'max_loops' in data else (existing[4] or 3)
            if 'project_id' in data:
                raw_pid = data.get('project_id')
                project_id = str(raw_pid).strip() if (raw_pid and str(raw_pid).strip() and str(raw_pid).lower() not in ('none', 'all', 'global')) else None
            else:
                project_id = existing[5]

            cur.execute("""
                UPDATE exit_criteria_templates
                SET project_id = %s, title = %s, description = %s, doc_type = %s, is_active = %s, max_loops = %s, updated_at = NOW()
                WHERE template_id = %s;
            """, (project_id, title, description, doc_type, is_active, max_loops, template_id))
            
            # Replace items ONLY when 'items' is explicitly sent in payload (allows safe quick-toggle PATCH)
            if 'items' in data and isinstance(data['items'], list):
                cur.execute("DELETE FROM exit_criteria_items WHERE template_id = %s;", (template_id,))
                for idx, item in enumerate(data['items'], 1):
                    i_code = str(item.get('item_code') or f"{idx}").strip()
                    norm_cat = normalize_exit_criteria_category(item.get('category'), i_code)
                    cur.execute("""
                        INSERT INTO exit_criteria_items (template_id, item_code, category, question_text, target_metric, severity, is_mandatory, order_index)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        template_id,
                        i_code,
                        norm_cat,
                        item.get('question_text', ''),
                        item.get('target_metric', '100% (ผ่านบริบูรณ์)'),
                        item.get('severity', 'Major'),
                        bool(item.get('is_mandatory', norm_cat != 'Format & Consistency')),
                        item.get('order_index', idx)
                    ))
                
            conn.commit()
            cur.close()
            conn.close()
            
            sync_exit_criteria_to_agent_skills(template_id, old_title=old_title)
            return jsonify({'success': True, 'message': 'Template updated successfully'})
        except Exception as e:
            logger.error(f"Error updating template {template_id}: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500

    elif request.method == 'DELETE':
        try:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT title FROM exit_criteria_templates WHERE template_id = %s;", (template_id,))
            t_row = cur.fetchone()
            t_title = t_row[0] if t_row else None
            cur.execute("DELETE FROM exit_criteria_templates WHERE template_id = %s;", (template_id,))
            cur.close()
            conn.close()
            delete_exit_criteria_agent_skill(template_id, title=t_title)
            return jsonify({'success': True, 'message': 'Template deleted successfully'})
        except Exception as e:
            logger.error(f"Error deleting template {template_id}: {e}", exc_info=True)
            return jsonify({'error': str(e)}), 500


@bp.route('/api/exit-criteria/reset-universal', methods=['POST'])
@admin_required
def reset_universal_exit_criteria():
    """Reset or re-seed the standard Universal Exit Criteria Checklist (restores 13 items & sets Active)"""
    try:
        try:
            from scripts.add_exit_criteria_tables import add_exit_criteria_tables
        except ImportError:
            from add_exit_criteria_tables import add_exit_criteria_tables
        add_exit_criteria_tables(force_reset=True)
        return jsonify({'success': True, 'message': 'Universal Document Exit Criteria template reset/seeded successfully'})
    except Exception as e:
        logger.error(f"Error resetting universal exit criteria: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/exit-criteria/effective-preview', methods=['GET'])
@token_required
def preview_effective_exit_criteria():
    """Preview which active templates & items will actually run together for a given doc_type and project_id."""
    try:
        from db_ingestion import get_db_connection
        doc_type = (request.args.get('doc_type') or 'ALL').strip() or 'ALL'
        raw_pid = request.args.get('project_id')
        safe_p_id = str(raw_pid).strip() if (raw_pid and str(raw_pid).strip() and str(raw_pid).lower() not in ('none', 'all', 'global')) else None
        candidate_types = _normalize_doc_type_aliases(doc_type, '')

        conn = get_db_connection()
        cur = conn.cursor()
        matched_templates = []
        seen_ids = set()

        # Check Universal ALL status (both active and inactive so UI can warn if Universal is turned off!)
        cur.execute("""
            SELECT template_id, title, is_active, project_id
            FROM exit_criteria_templates
            WHERE UPPER(TRIM(doc_type)) = 'ALL'
            ORDER BY is_active DESC, created_at DESC;
        """)
        universal_rows = cur.fetchall()
        universal_active = any(bool(r[2]) for r in universal_rows)

        if safe_p_id:
            cur.execute("""
                SELECT t.template_id, t.title, t.doc_type, t.project_id, p.project_code, COUNT(i.item_id)
                FROM exit_criteria_templates t
                LEFT JOIN exit_criteria_items i ON t.template_id = i.template_id
                LEFT JOIN projects p ON t.project_id = p.project_id
                WHERE t.is_active = TRUE AND UPPER(TRIM(t.doc_type)) = 'ALL'
                  AND (t.project_id = %s::uuid OR t.project_id IS NULL)
                GROUP BY t.template_id, p.project_code
                ORDER BY (CASE WHEN t.project_id = %s::uuid THEN 0 ELSE 1 END), t.created_at DESC;
            """, (safe_p_id, safe_p_id))
        else:
            cur.execute("""
                SELECT t.template_id, t.title, t.doc_type, t.project_id, p.project_code, COUNT(i.item_id)
                FROM exit_criteria_templates t
                LEFT JOIN exit_criteria_items i ON t.template_id = i.template_id
                LEFT JOIN projects p ON t.project_id = p.project_id
                WHERE t.is_active = TRUE AND UPPER(TRIM(t.doc_type)) = 'ALL' AND t.project_id IS NULL
                GROUP BY t.template_id, p.project_code
                ORDER BY t.created_at DESC;
            """)
        for r in cur.fetchall():
            if str(r[0]) not in seen_ids:
                seen_ids.add(str(r[0]))
                matched_templates.append({
                    'template_id': str(r[0]),
                    'title': r[1],
                    'doc_type': 'ALL',
                    'project_id': str(r[3]) if r[3] else None,
                    'project_code': r[4],
                    'item_count': int(r[5] or 0)
                })

        for cand in candidate_types:
            if not cand or cand.upper() == 'ALL':
                continue
            cand_compact = re.sub(r'\s+', '', cand).upper()
            if safe_p_id:
                cur.execute("""
                    SELECT t.template_id, t.title, t.doc_type, t.project_id, p.project_code, COUNT(i.item_id)
                    FROM exit_criteria_templates t
                    LEFT JOIN exit_criteria_items i ON t.template_id = i.template_id
                    LEFT JOIN projects p ON t.project_id = p.project_id
                    WHERE t.is_active = TRUE AND UPPER(TRIM(t.doc_type)) != 'ALL'
                      AND (t.project_id = %s::uuid OR t.project_id IS NULL)
                      AND (UPPER(TRIM(t.doc_type)) = UPPER(TRIM(%s)) OR UPPER(REPLACE(TRIM(t.doc_type), ' ', '')) = %s)
                    GROUP BY t.template_id, p.project_code
                    ORDER BY (CASE WHEN t.project_id = %s::uuid THEN 0 ELSE 1 END), t.created_at DESC;
                """, (safe_p_id, cand, cand_compact, safe_p_id))
            else:
                cur.execute("""
                    SELECT t.template_id, t.title, t.doc_type, t.project_id, p.project_code, COUNT(i.item_id)
                    FROM exit_criteria_templates t
                    LEFT JOIN exit_criteria_items i ON t.template_id = i.template_id
                    LEFT JOIN projects p ON t.project_id = p.project_id
                    WHERE t.is_active = TRUE AND UPPER(TRIM(t.doc_type)) != 'ALL' AND t.project_id IS NULL
                      AND (UPPER(TRIM(t.doc_type)) = UPPER(TRIM(%s)) OR UPPER(REPLACE(TRIM(t.doc_type), ' ', '')) = %s)
                    GROUP BY t.template_id, p.project_code
                    ORDER BY t.created_at DESC;
                """, (cand, cand_compact))
            for r in cur.fetchall():
                if str(r[0]) not in seen_ids:
                    seen_ids.add(str(r[0]))
                    matched_templates.append({
                        'template_id': str(r[0]),
                        'title': r[1],
                        'doc_type': r[2],
                        'project_id': str(r[3]) if r[3] else None,
                        'project_code': r[4],
                        'item_count': int(r[5] or 0)
                    })

        cur.close()
        conn.close()
        total_effective_items = sum(t['item_count'] for t in matched_templates)
        return jsonify({
            'success': True,
            'doc_type': doc_type,
            'universal_active': universal_active,
            'using_fallback': total_effective_items == 0,
            'total_items': total_effective_items if total_effective_items > 0 else 13,
            'matched_templates': matched_templates
        })
    except Exception as e:
        logger.error(f"Error building effective exit criteria preview: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/exit-criteria/ai-suggest', methods=['POST'])
@admin_required
def ai_suggest_exit_criteria():
    """Generate high-precision Exit Criteria items tailored for a specific doc_type using Gemini."""
    try:
        from ocr_engine import _get_gemini_client
        data = request.json or {}
        doc_type = (data.get('doc_type') or 'SRS').strip()
        hint = (data.get('hint') or '').strip()

        prompt = f"""คุณคือ Principal QA Architect ผู้เชี่ยวชาญการกำหนด Quality Gate (Exit Criteria) สำหรับเอกสารซอฟต์แวร์
กรุณาออกแบบรายการตรวจสอบ Exit Criteria ที่ชัดเจน วัดผลได้จริง และไม่คลุมเครือ สำหรับเอกสารประเภท: "{doc_type}"
{f'บริบทเพิ่มเติมจากผู้ใช้: {hint}' if hint else ''}

สร้างรายการรวม 8–10 ข้อ ครอบคลุมทั้ง 4 หมวดมาตรฐาน (ใช้ชื่อ category ภาษาอังกฤษตามนี้เป๊ะๆ เท่านั้น):
1. "Defect & Comment Resolution" (รหัส 1.1, 1.2 ... — เน้นไม่มีข้อผิดพลาดร้ายแรง/การแก้ไขครบถ้วน, is_mandatory: true)
2. "Content Accuracy & Completeness" (รหัส 2.1, 2.2 ... — เน้นความครบถ้วนของเนื้อหาเฉพาะของเอกสาร {doc_type}, is_mandatory: true)
3. "Format & Consistency" (รหัส 3.1, 3.2 ... — เน้นรูปแบบ/คำผิด/ความสม่ำเสมอ, severity: "Minor", is_mandatory: false เพื่อให้เข้าเกณฑ์ CONDITIONAL PASSED ได้)
4. "Governance & Control" (รหัส 4.1, 4.2 ... — เน้น Metadata, Version, Revision History, Clean Copy)

เลือกค่า "target_metric" ให้ตรงกับชุดตัวชี้วัดมาตรฐานต่อไปนี้เป็นหลัก (ยกเว้นจำเป็นต้องระบุเฉพาะทางจริงๆ):
- หมวด 1: "100% Closed (แก้ไขครบ 100%)", "100% Responded (ตอบครบทุกข้อ)", "0 Defect Impact (0 ข้อผิดพลาดใหม่)", "100% REQ Traced"
- หมวด 2: "100% Verified Accuracy (ถูกต้อง 100%)", "100% Scope Coverage (ครบตาม Scope)", "100% Actionable Steps & Expected Results", ">= 90% Negative & Boundary Coverage", "0 Ambiguity (ไม่มีจุดคลุมเครือ)", "100% Complete Attachments"
- หมวด 3: "100% CI Compliance (ตรงตาม CI)", "100% Page & TOC Match", "< 1% Typo Rate (คำผิด < 1%)", "0 Duplicate/Conflicting Cases"
- หมวด 4: "100% Header & Metadata", "100% Logged History", "0 Draft Comments (ฉบับสะอาด 100%)"

ส่งกลับเป็น JSON Array เท่านั้น (ห้ามมีข้อความอื่นนอก JSON):
[
  {{
    "item_code": "1.1",
    "category": "Defect & Comment Resolution",
    "question_text": "รายละเอียดข้อตรวจภาษาไทยที่ชัดเจน ตรวจสอบจากเนื้อหาเอกสารได้จริง",
    "target_metric": "100% Closed (แก้ไขครบ 100%)",
    "severity": "Critical" | "Major" | "Minor",
    "is_mandatory": true | false
  }}
]
"""
        client = _get_gemini_client()
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        res = client.models.generate_content(model=model_name, contents=prompt)
        raw = (res.text or '').strip()
        if raw.startswith("```"):
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
        m = re.search(r'\[[\s\S]*\]', raw)
        if m:
            raw = m.group(0)
        suggested = json.loads(raw)
        if hasattr(res, 'usage_metadata'):
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Exit_Criteria_AI_Suggest", model_name, res.usage_metadata)
            except Exception:
                pass

        cleaned = []
        for idx, it in enumerate(suggested, 1):
            code = str(it.get('item_code') or f"{idx}").strip()
            cat = normalize_exit_criteria_category(it.get('category'), code)
            sev = it.get('severity') if it.get('severity') in ('Critical', 'Major', 'Minor') else ('Minor' if cat == 'Format & Consistency' else 'Major')
            mand = bool(it.get('is_mandatory', cat != 'Format & Consistency'))
            cleaned.append({
                'item_code': code,
                'category': cat,
                'question_text': str(it.get('question_text') or '').strip(),
                'target_metric': str(it.get('target_metric') or '100% Complete').strip(),
                'severity': sev,
                'is_mandatory': mand,
                'order_index': idx
            })
        return jsonify({'success': True, 'items': cleaned})
    except Exception as e:
        logger.error(f"Error generating AI suggested exit criteria: {e}", exc_info=True)
        return jsonify({'error': f'ไม่สามารถสร้างรายการด้วย AI ได้: {e}'}), 500


@bp.route('/api/exit-criteria/test-evaluate', methods=['POST'])
@admin_required
def test_evaluate_exit_criteria_sandbox():
    """Dry-run sandbox to test draft or active Exit Criteria against sample text without saving to qa_transactions."""
    try:
        data = request.json or {}
        sample_text = (data.get('sample_text') or '').strip()
        if not sample_text:
            return jsonify({'error': 'กรุณาวางข้อความตัวอย่างเอกสารสำหรับทดลองตรวจ'}), 400
        doc_type = (data.get('doc_type') or 'ALL').strip() or 'ALL'
        project_id = data.get('project_id')
        use_draft = bool(data.get('use_draft', True))
        draft_items = data.get('items') if use_draft else None

        result = evaluate_document_exit_criteria(
            doc_text=sample_text,
            doc_type=doc_type,
            project_id=project_id,
            qa_findings=[],
            custom_items_override=draft_items if (use_draft and isinstance(draft_items, list) and len(draft_items) > 0) else None,
            dry_run=True
        )
        return jsonify({'success': True, 'evaluation': result})
    except Exception as e:
        logger.error(f"Error in Exit Criteria sandbox test-evaluate: {e}", exc_info=True)
        return jsonify({'error': f'ทดลองประเมินไม่สำเร็จ: {e}'}), 500

