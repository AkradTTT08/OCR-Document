"""AI Skills (SKILL.md) CRUD, export, and table seeding endpoints."""
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
bp = Blueprint('skills', __name__)

from core.auth import get_request_user_payload

_SKILLS_TABLE_ENSURED = False

def _validate_skill_uuid(val: str) -> bool:
    import uuid as _uuid
    if not val:
        return False
    try:
        _uuid.UUID(str(val).strip())
        return True
    except Exception:
        return False


def _check_skill_write_permission():
    """Verify JWT authentication and AI Skills write permission."""
    req_payload = get_request_user_payload()
    if not req_payload:
        return jsonify({'error': 'กรุณาเข้าสู่ระบบก่อนจัดการ AI Skills'}), 401
    role = str(req_payload.get('role') or '').lower()
    if role == 'admin':
        return None
    allowed_menus = req_payload.get('allowed_menus') or []
    required = {'ai_skills', 'skills', 'skill_manager'}
    if isinstance(allowed_menus, list) and not any(m in required for m in allowed_menus):
        return jsonify({'error': 'คุณไม่มีสิทธิ์สร้าง แก้ไข หรือลบ AI Skills'}), 403
    return None


def ensure_skills_table(force: bool = False):
    """Ensure agent_skills table exists in PostgreSQL and seed standard skills if empty (cached per process)."""
    global _SKILLS_TABLE_ENSURED
    if _SKILLS_TABLE_ENSURED and not force:
        return
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_skills (
                skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                skill_name VARCHAR(100) NOT NULL,
                skill_description TEXT,
                markdown_instructions TEXT NOT NULL,
                target_doc_type VARCHAR(50),
                version INT DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Check if table is empty
        cursor.execute("SELECT COUNT(*) FROM agent_skills WHERE skill_name NOT ILIKE '%Exit Criteria%';")
        count = cursor.fetchone()[0]
        if count == 0:
            logger.info("Seeding standard AI skills for QA document creation...")
            seed_skills = [
                ("Standard Test Case Specification", "โครงสร้างสร้าง Test Case มาตรฐานระดับสากล ครอบคลุม Positive, Negative, Boundary Value และ Edge Cases", "Test Case", """# มาตรฐานการสร้าง Test Case
1. **Header Information**: ระบุ Module/Feature, Pre-conditions, และ Test Environment
2. **Test Cases Breakdown**:
   - Test Case ID (เช่น TC-001, TC-002)
   - Test Objective (วัตถุประสงค์การทดสอบ)
   - Pre-conditions (เงื่อนไขก่อนทดสอบ)
   - Step-by-Step Procedure (ขั้นตอนการทดสอบอย่างละเอียด)
   - Test Data (ข้อมูลตัวอย่างที่ใช้ทดสอบ)
   - Expected Result (ผลลัพธ์ที่คาดหวังแบบชัดเจน วัดผลได้)
   - Priority (High/Medium/Low)
3. **Coverage Requirement**: ต้องครอบคลุมทั้ง Positive Flow, Validation Error, Authorization Check, Boundary Value และ Exception Handling"""),
                ("Software Requirements Specification (SRS)", "โครงสร้างเอกสารข้อกำหนดความต้องการระบบตามมาตรฐาน IEEE 830 สำหรับวิศวกรรมซอฟต์แวร์", "SRS", """# โครงสร้างเอกสาร SRS มาตรฐาน
1. **Introduction**: วัตถุประสงค์ของระบบ, ขอบเขตโครงการ (Scope), คำจำกัดความ (Definitions)
2. **Overall Description**: ภาพรวมการทำงาน, สิทธิ์ผู้ใช้งาน (User Persona/Roles), ข้อจำกัดทั่วไป (General Constraints)
3. **Functional Requirements**: ข้อกำหนดเชิงฟังก์ชัน แบ่งตามโมดูลอย่างละเอียด ระบุ Input/Process/Output และ Business Rules
4. **Non-Functional Requirements**: ประสิทธิภาพ (Performance), ความปลอดภัย (Security), ความพร้อมใช้งาน (Availability)
5. **External Interface Requirements**: User Interface, Hardware/Software Interfaces, API Contracts"""),
                ("Software Design Document (SDD)", "โครงสร้างการออกแบบสถาปัตยกรรมระบบ, โครงสร้างฐานข้อมูล, API และ Integration Flow", "SDD", """# โครงสร้างเอกสาร SDD มาตรฐาน
1. **Architecture Overview**: สถาปัตยกรรมระบบ (System Architecture), Tech Stack และ Component Diagrams
2. **Database Design & Schema**: โครงสร้างตาราง (Entity Relationships), Data Dictionary, Indexing และ Constraints
3. **API & Interface Specifications**: RESTful / GraphQL Endpoints, Request/Response Payloads, Status Codes
4. **Data Flow & Sequence Logic**: แผนภาพลำดับการทำงาน (Sequence Flow) ของ Core Features
5. **Security & Error Handling Strategy**: Authentication/Authorization Flow, Logging, Fallback & Exception Handling"""),
                ("Terms of Reference & Scope of Work (TOR/SOW)", "โครงสร้างเอกสารขอบเขตงานและข้อกำหนดการส่งมอบงานโครงการอย่างเป็นทางการ", "TOR/SOW", """# โครงสร้างเอกสาร TOR / SOW มาตรฐาน
1. **ความเป็นมาและวัตถุประสงค์ (Background & Objectives)**: เหตุผลความจำเป็นและเป้าหมายโครงการ
2. **ขอบเขตของงาน (Scope of Work)**: รายละเอียดฟังก์ชันและระบบงานที่ต้องพัฒนาให้แล้วเสร็จ
3. **คุณสมบัติและข้อกำหนดทางเทคนิค (Technical Specifications)**: เทคโนโลยี, มาตรฐานความปลอดภัย และข้อกำหนดโครงสร้างพื้นฐาน
4. **งวดงานและการส่งมอบ (Deliverables & Milestones)**: รายการสิ่งส่งมอบในแต่ละงวดงาน
5. **เกณฑ์การตรวจรับงาน (Acceptance Criteria & SLA)**: ตัวชี้วัดคุณภาพและเงื่อนไขการตรวจรับ"""),
                ("User Acceptance Testing (UAT) Framework", "แผนการทดสอบยอมรับสำหรับผู้ใช้งานและลูกค้า พร้อมเกณฑ์ Sign-off ทางธุรกิจ", "UAT", """# โครงสร้างเอกสาร UAT มาตรฐาน
1. **UAT Scope & Objectives**: วัตถุประสงค์การทดสอบทางธุรกิจและขอบเขตที่ครอบคลุม
2. **Business Scenario Matrix**: ตารางจำลองสถานการณ์การใช้งานจริงจากมุมมอง End-User / Customer
3. **Step-by-Step Test Procedure**: ขั้นตอนการทดสอบตาม User Journey พร้อมข้อมูลทดสอบ
4. **Acceptance Criteria & Evaluation**: เกณฑ์การตัดสินผ่าน/ไม่ผ่านสำหรับแต่ละ Scenario
5. **UAT Sign-off Form**: แบบฟอร์มสรุปผลการยอมรับและลงนามตรวจรับระบบ"""),
                ("User Manual Standard Guide", "แนวทางการเขียนคู่มือการใช้งานสำหรับผู้ใช้งานทั่วไป อ่านง่าย ชัดเจน พร้อมตัวอย่างการทำงาน", "User Manual", """# โครงสร้างคู่มือการใช้งาน (User Manual)
1. **บทนำและเริ่มต้นใช้งาน (Getting Started)**: วิธีเข้าสู่ระบบ, การตั้งค่าเริ่มต้น, และภาพรวมหน้าจอหลัก
2. **ฟังก์ชันการทำงานหลัก (Core Features Step-by-Step)**: วิธีการใช้งานแต่ละเมนูอย่างละเอียดทีละขั้นตอน
3. **ตัวอย่างการใช้งานจริง (Use Case Walkthrough)**: Scenario จำลองพร้อมรูปภาพประกอบและคำแนะนำ
4. **ข้อควรระวังและ FAQ**: ปัญหาที่พบบ่อยและแนวทางแก้ไขเบื้องต้น
5. **ช่องทางการติดต่อสนับสนุน (Support & Contact)**"""),
                ("Admin & Operations Manual", "คู่มือการบริหารจัดการระบบ การจัดการสิทธิ์ผู้ใช้งาน และการตรวจสอบ Audit Logs", "Admin Manual", """# โครงสร้างคู่มือผู้ดูแลระบบ (Admin Manual)
1. **Admin Dashboard Overview**: เมนูและเครื่องมือสำหรับผู้ดูแลระบบ
2. **User & Role Management**: การจัดการผู้ใช้, การกำหนดสิทธิ์ (RBAC), และการเปิด/ปิดสิทธิ์เข้าถึง
3. **System Configuration**: การตั้งค่าพารามิเตอร์ระบบ, API Keys, และ Environment Settings
4. **Monitoring & Audit Logs**: การตรวจสอบประวัติการใช้งาน (Audit Trails) และรายงานข้อผิดพลาด
5. **Security & Backup Procedures**: รอบการสำรองข้อมูล (Backup) และขั้นตอนการกู้คืน (Disaster Recovery)"""),
                ("System Installation & Deployment Guide", "คู่มือการติดตั้ง Deploy ระบบ ซอฟต์แวร์พื้นฐาน ฐานข้อมูล และการตั้งค่าเน็ตเวิร์ก", "Installation System", """# โครงสร้างคู่มือการติดตั้งระบบ (Installation Guide)
1. **System Requirements & Prerequisites**: ข้อกำหนด Hardware, OS, Docker/Node.js/Python Versions
2. **Pre-installation Steps**: การเตรียม Environment, พอร์ตไฟร์วอลล์, และ Network Configuration
3. **Step-by-step Installation**: คำสั่งติดตั้ง Service, Database Setup, Docker Compose Commands
4. **Configuration & Verification**: การตั้งค่าไฟล์ .env, การทดสอบการเชื่อมต่อ (Healthcheck)
5. **Troubleshooting**: แนวทางแก้ไขข้อผิดพลาดระหว่างการติดตั้งและการ Rollback"""),
                ("Comprehensive QA Summary Report", "รายงานสรุปผลการประกันคุณภาพ การทดสอบระบบ และการประเมินความพร้อมก่อนปล่อยสู่ Production", "QA Report", """# โครงสร้างรายงานผลการทดสอบ QA (QA Report)
1. **Executive Summary**: สรุปภาพรวมผลการทดสอบและสถานะความพร้อม (Go / No-Go Verdict)
2. **Test Execution Statistics**: สถิติจำนวน Test Case ทั้งหมด, ผ่าน (Pass), ไม่ผ่าน (Fail), รอดำเนินการ (Block)
3. **Defect & Bug Analysis**: รายการข้อบกพร่องที่พบ แยกตามระดับความรุนแรง (Critical, Major, Minor)
4. **Risk Assessment**: การประเมินความเสี่ยงที่ยังคงค้างและมาตรการรับมือ
5. **Recommendations & Sign-off**: ข้อเสนอแนะในการปรับปรุงและการลงนามอนุมัติปล่อยระบบ"""),
                ("Security Assessment & Test Plan", "แผนและเกณฑ์การทดสอบความปลอดภัย การตรวจสอบช่องโหว่ OWASP Top 10 และ Data Protection", "Security Plan", """# โครงสร้างแผนการทดสอบความปลอดภัย (Security Test Plan)
1. **Security Testing Objectives**: เป้าหมายและขอบเขตการประเมินความปลอดภัย
2. **Threat Modeling & Risk Areas**: จุดเสี่ยงที่ต้องทดสอบ (Auth, Injection, Broken Access Control)
3. **Security Test Cases**: กรณีทดสอบเฉพาะทางตามแนวทาง OWASP Top 10
4. **Data Privacy & Encryption Compliance**: การตรวจสอบการเข้ารหัสข้อมูล (At-rest / In-transit)
5. **Vulnerability Reporting & Remediation SLA**: ขั้นตอนการรายงานและกำหนดระยะเวลาแก้ไขช่องโหว่"""),
                ("Performance & Load Testing Strategy", "กลยุทธ์การทดสอบประสิทธิภาพ Stress Test, Concurrency, Latency และ Throughput", "Performance Plan", """# โครงสร้างแผนการทดสอบประสิทธิภาพ (Performance Plan)
1. **Performance Objectives & Baseline**: ค่าเป้าหมาย SLA (Response Time < 2s, TPS, 95th Percentile)
2. **Test Scenarios**: แผนการทดสอบ Load Test, Stress Test, Endurance Test และ Spike Test
3. **Virtual User (VU) Configuration**: การจำลองจำนวนผู้ใช้งานพร้อมกัน (Concurrent Users)
4. **Resource Monitoring**: การตรวจสอบ CPU, Memory, DB Connection Pool และ Network IO
5. **Bottleneck Analysis & Optimization Guidelines**: แนวทางการระบุคอขวดและเกณฑ์การปรับแต่ง""")
            ]
            for s_name, s_desc, s_doc_type, s_instructions in seed_skills:
                cursor.execute("""
                    INSERT INTO agent_skills (skill_name, skill_description, target_doc_type, markdown_instructions, created_by)
                    VALUES (%s, %s, %s, %s, 'System Seed');
                """, (s_name, s_desc, s_doc_type, s_instructions))
        
        conn.commit()
        cursor.close()
        _SKILLS_TABLE_ENSURED = True
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error ensuring agent_skills table: {e}", exc_info=True)
    finally:
        if conn: conn.close()


@bp.route('/api/skills', methods=['GET'])
def get_skills():
    """ดึงรายการ AI Skills ทั้งหมด (รองรับ active_only, status, search, target_doc_type พร้อม usage_count)"""
    ensure_skills_table()
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        search = request.args.get('search', '').strip()
        target_type = request.args.get('target_doc_type', '').strip()
        include_system = request.args.get('include_system', 'false').lower() == 'true'
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        status_filter = request.args.get('status', '').strip().lower()

        query = """
            SELECT skill_id, skill_name, skill_description, markdown_instructions,
                   target_doc_type, version, is_active, created_by, created_at
            FROM agent_skills
            WHERE 1=1
        """
        params = []

        if not include_system:
            query += " AND skill_name NOT ILIKE %s"
            params.append('%Exit Criteria%')

        if active_only or status_filter == 'active':
            query += " AND COALESCE(is_active, TRUE) = TRUE"
        elif status_filter == 'draft':
            query += " AND COALESCE(is_active, TRUE) = FALSE"

        if search:
            query += " AND (skill_name ILIKE %s OR skill_description ILIKE %s OR markdown_instructions ILIKE %s)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])

        if target_type and target_type.upper() != 'ALL':
            query += " AND UPPER(TRIM(COALESCE(target_doc_type, ''))) = UPPER(TRIM(%s))"
            params.append(target_type)

        query += " ORDER BY COALESCE(is_active, TRUE) DESC, created_at DESC;"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Fetch lightweight usage counts from qa_generated_documents in a single query
        usage_map = {}
        try:
            cursor.execute("SELECT skill_id FROM qa_generated_documents WHERE skill_id IS NOT NULL AND skill_id <> '';")
            for (raw_sid,) in cursor.fetchall():
                for part in str(raw_sid).split(','):
                    tok = part.strip()
                    if tok:
                        usage_map[tok] = usage_map.get(tok, 0) + 1
        except Exception:
            conn.rollback()

        skills = []
        for r in rows:
            sid_str = str(r[0])
            sname = r[1] or ''
            skills.append({
                'skill_id': sid_str,
                'skill_name': sname,
                'skill_description': r[2] or '',
                'markdown_instructions': r[3] or '',
                'target_doc_type': r[4] or 'General',
                'version': int(r[5]) if r[5] is not None else 1,
                'is_active': bool(r[6]) if r[6] is not None else True,
                'created_by': r[7] or 'Admin',
                'created_at': r[8].isoformat() if r[8] else None,
                'usage_count': usage_map.get(sid_str, 0) + usage_map.get(sname, 0)
            })

        return jsonify({'success': True, 'skills': skills, 'total': len(skills)})
    except Exception as e:
        logger.error(f"Get skills error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@bp.route('/api/skills/<string:skill_id>', methods=['GET'])
def get_skill_detail(skill_id):
    """ดูรายละเอียด AI Skill รายรายการ"""
    ensure_skills_table()
    if not _validate_skill_uuid(skill_id):
        return jsonify({'error': 'รหัส Skill (UUID) ไม่ถูกต้อง'}), 400
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT skill_id, skill_name, skill_description, markdown_instructions,
                   target_doc_type, version, is_active, created_by, created_at
            FROM agent_skills
            WHERE skill_id = %s::uuid;
        """, (skill_id,))
        r = cursor.fetchone()
        if not r:
            return jsonify({'error': 'ไม่พบ Skill ที่ต้องการ'}), 404

        skill = {
            'skill_id': str(r[0]),
            'skill_name': r[1],
            'skill_description': r[2],
            'markdown_instructions': r[3],
            'target_doc_type': r[4],
            'version': r[5],
            'is_active': r[6],
            'created_by': r[7],
            'created_at': r[8].isoformat() if r[8] else None
        }

        return jsonify({'success': True, 'skill': skill})
    except Exception as e:
        logger.error(f"Get skill detail error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@bp.route('/api/skills', methods=['POST'])
def create_skill():
    """สร้าง AI Skill ใหม่"""
    ensure_skills_table()
    auth_err = _check_skill_write_permission()
    if auth_err:
        return auth_err

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No payload provided'}), 400

    skill_name = str(data.get('skill_name') or '').strip()
    markdown_instructions = str(data.get('markdown_instructions') or '').strip()

    if not skill_name or not markdown_instructions:
        return jsonify({'error': 'กรุณาระบุชื่อ Skill และเนื้อหา Markdown Instructions'}), 400
    if len(skill_name) > 100:
        return jsonify({'error': 'ชื่อ Skill ต้องไม่เกิน 100 ตัวอักษร'}), 400

    skill_description = str(data.get('skill_description') or '').strip()
    target_doc_type = str(data.get('target_doc_type') or 'General').strip()[:50]
    try:
        version = max(1, int(data.get('version') or 1))
    except Exception:
        version = 1
    is_active = bool(data.get('is_active', True))
    req_payload = get_request_user_payload() or {}
    created_by = str(data.get('created_by') or req_payload.get('username') or 'Admin').strip()[:50]

    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT skill_id FROM agent_skills WHERE LOWER(TRIM(skill_name)) = LOWER(TRIM(%s)) LIMIT 1;", (skill_name,))
        if cursor.fetchone():
            return jsonify({'error': f'มี AI Skill ชื่อ "{skill_name}" อยู่ในระบบแล้ว กรุณาใช้ชื่ออื่น'}), 409

        cursor.execute("""
            INSERT INTO agent_skills (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING skill_id;
        """, (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by))

        new_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({'success': True, 'message': 'สร้าง AI Skill สำเร็จ', 'skill_id': str(new_id)})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Create skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@bp.route('/api/skills/<string:skill_id>', methods=['PUT'])
def update_skill(skill_id):
    """แก้ไข AI Skill"""
    ensure_skills_table()
    auth_err = _check_skill_write_permission()
    if auth_err:
        return auth_err
    if not _validate_skill_uuid(skill_id):
        return jsonify({'error': 'รหัส Skill (UUID) ไม่ถูกต้อง'}), 400

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'No payload provided'}), 400

    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT skill_id, markdown_instructions, COALESCE(version, 1) FROM agent_skills WHERE skill_id = %s::uuid;", (skill_id,))
        existing_row = cursor.fetchone()
        if not existing_row:
            return jsonify({'error': 'ไม่พบ Skill ที่ต้องการแก้ไข'}), 404

        old_instructions = existing_row[1] or ''
        old_version = int(existing_row[2] or 1)

        skill_name = data.get('skill_name')
        if skill_name is not None:
            skill_name = str(skill_name).strip()
            if not skill_name:
                return jsonify({'error': 'ชื่อ Skill ห้ามเป็นค่าว่าง'}), 400
            if len(skill_name) > 100:
                return jsonify({'error': 'ชื่อ Skill ต้องไม่เกิน 100 ตัวอักษร'}), 400
            cursor.execute(
                "SELECT skill_id FROM agent_skills WHERE LOWER(TRIM(skill_name)) = LOWER(TRIM(%s)) AND skill_id <> %s::uuid LIMIT 1;",
                (skill_name, skill_id)
            )
            if cursor.fetchone():
                return jsonify({'error': f'มี AI Skill ชื่อ "{skill_name}" อยู่ในระบบแล้ว'}), 409

        skill_description = str(data.get('skill_description')).strip() if data.get('skill_description') is not None else None
        markdown_instructions = str(data.get('markdown_instructions')).strip() if data.get('markdown_instructions') is not None else None
        if markdown_instructions is not None and not markdown_instructions:
            return jsonify({'error': 'เนื้อหา Markdown Instructions ห้ามเป็นค่าว่าง'}), 400
        target_doc_type = str(data.get('target_doc_type')).strip()[:50] if data.get('target_doc_type') is not None else None

        version = data.get('version')
        if version is not None:
            try:
                version = max(1, int(version))
            except Exception:
                version = old_version
        # Auto-bump version if instructions changed and caller left version unchanged
        if data.get('auto_bump_version') and markdown_instructions is not None and markdown_instructions != old_instructions:
            if version is None or version <= old_version:
                version = old_version + 1

        is_active = data.get('is_active')
        created_by = str(data.get('created_by')).strip()[:50] if data.get('created_by') is not None else None

        cursor.execute("""
            UPDATE agent_skills
            SET skill_name = COALESCE(%s, skill_name),
                skill_description = COALESCE(%s, skill_description),
                markdown_instructions = COALESCE(%s, markdown_instructions),
                target_doc_type = COALESCE(%s, target_doc_type),
                version = COALESCE(%s, version),
                is_active = COALESCE(%s, is_active),
                created_by = COALESCE(%s, created_by)
            WHERE skill_id = %s::uuid
            RETURNING version;
        """, (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by, skill_id))

        updated_ver = cursor.fetchone()[0]
        conn.commit()
        return jsonify({'success': True, 'message': 'อัปเดต AI Skill สำเร็จ', 'version': updated_ver})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Update skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@bp.route('/api/skills/<string:skill_id>', methods=['DELETE'])
def delete_skill(skill_id):
    """ลบ AI Skill"""
    ensure_skills_table()
    auth_err = _check_skill_write_permission()
    if auth_err:
        return auth_err
    if not _validate_skill_uuid(skill_id):
        return jsonify({'error': 'รหัส Skill (UUID) ไม่ถูกต้อง'}), 400

    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT skill_id FROM agent_skills WHERE skill_id = %s::uuid;", (skill_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'ไม่พบ Skill ที่ต้องการลบ'}), 404

        cursor.execute("DELETE FROM agent_skills WHERE skill_id = %s::uuid;", (skill_id,))
        conn.commit()

        return jsonify({'success': True, 'message': 'ลบ AI Skill เรียบร้อยแล้ว'})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Delete skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@bp.route('/api/skills/<string:skill_id>/export', methods=['GET'])
def export_skill_md(skill_id):
    """Export AI Skill เป็นไฟล์ SKILL.md"""
    ensure_skills_table()
    if not _validate_skill_uuid(skill_id):
        return jsonify({'error': 'รหัส Skill (UUID) ไม่ถูกต้อง'}), 400
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT skill_name, skill_description, markdown_instructions, target_doc_type, version, created_by
            FROM agent_skills
            WHERE skill_id = %s::uuid;
        """, (skill_id,))
        r = cursor.fetchone()
        if not r:
            return jsonify({'error': 'ไม่พบ Skill'}), 404

        name, desc, instructions, target_type, version, created_by = r

        md_content = f"""---
name: "{name}"
description: "{desc or ''}"
target_doc_type: "{target_type or 'General'}"
version: {version or 1}
created_by: "{created_by or 'Admin'}"
---

# {name}

{desc or ''}

## Skill Instructions (Skill.md)

{instructions}
"""
        from flask import Response
        filename = f"{name.lower().replace(' ', '_')}_SKILL.md"
        return Response(
            md_content,
            mimetype="text/markdown",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Export skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

