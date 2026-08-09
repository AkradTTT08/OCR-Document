import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
load_dotenv()

def add_exit_criteria_tables(force_reset=False):
    print("Connecting to DB (qa_agent_db)...")
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Creating table: exit_criteria_templates...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exit_criteria_templates (
                template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                doc_type VARCHAR(50) DEFAULT 'ALL',
                is_active BOOLEAN DEFAULT TRUE,
                max_loops INTEGER DEFAULT 3,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        print("Creating table: exit_criteria_items...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exit_criteria_items (
                item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                template_id UUID NOT NULL REFERENCES exit_criteria_templates(template_id) ON DELETE CASCADE,
                item_code VARCHAR(50) NOT NULL,
                category VARCHAR(100) NOT NULL,
                question_text TEXT NOT NULL,
                target_metric VARCHAR(100) DEFAULT '100% (ผ่านบริบูรณ์)',
                severity VARCHAR(20) DEFAULT 'Major',
                is_mandatory BOOLEAN DEFAULT TRUE,
                order_index INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("ALTER TABLE exit_criteria_items ADD COLUMN IF NOT EXISTS target_metric VARCHAR(100) DEFAULT '100% (ผ่านบริบูรณ์)';")

        print("Creating table: document_exit_evaluations...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_exit_evaluations (
                evaluation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                template_id UUID REFERENCES exit_criteria_templates(template_id) ON DELETE SET NULL,
                version INT DEFAULT 1,
                review_round INT DEFAULT 1,
                status VARCHAR(30) DEFAULT 'PENDING',
                total_items INT DEFAULT 0,
                passed_items INT DEFAULT 0,
                failed_items INT DEFAULT 0,
                na_items INT DEFAULT 0,
                score_percentage NUMERIC(5,2) DEFAULT 0.00,
                evaluated_by VARCHAR(100),
                evaluator_type VARCHAR(50) DEFAULT 'HYBRID',
                summary_remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        print("Creating table: document_exit_evaluation_items...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_exit_evaluation_items (
                result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                evaluation_id UUID NOT NULL REFERENCES document_exit_evaluations(evaluation_id) ON DELETE CASCADE,
                item_id UUID REFERENCES exit_criteria_items(item_id) ON DELETE SET NULL,
                item_code VARCHAR(50),
                category VARCHAR(100),
                question_text TEXT,
                target_metric VARCHAR(100),
                severity VARCHAR(20),
                is_mandatory BOOLEAN DEFAULT TRUE,
                status VARCHAR(20) NOT NULL DEFAULT 'NA',
                remarks TEXT,
                evidence_text TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("ALTER TABLE document_exit_evaluation_items ADD COLUMN IF NOT EXISTS target_metric VARCHAR(100);")

        # Indexes
        print("Creating indexes...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exit_items_template ON exit_criteria_items(template_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exit_eval_doc ON document_exit_evaluations(doc_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exit_eval_project ON document_exit_evaluations(project_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exit_eval_status ON document_exit_evaluations(status);")

        # Default Universal Template seed items
        default_items = [
            ('1.1', 'Defect & Comment Resolution', 'ข้อสั่งการ/Comment ระดับ Critical / High ในรอบก่อน ได้รับการแก้ไขเรียบร้อยแล้ว 100%', '100% Closed (แก้ไขครบ 100%)', 'Critical', True, 1),
            ('1.2', 'Defect & Comment Resolution', 'Comment ทุกข้อได้รับการตอบกลับครบถ้วน หากข้อใดไม่ได้แก้ มีการระบุเหตุผลที่ผู้ตรวจยอมรับได้', '100% Responded (ตอบครบทุกข้อ)', 'Major', True, 2),
            ('1.3', 'Defect & Comment Resolution', 'การแก้ไขตาม Comment ไม่ส่งผลกระทบให้เกิดข้อผิดพลาดใหม่ในส่วนอื่นของเอกสาร (No Side-effects)', '0 Defect Impact (0 ข้อผิดพลาดใหม่)', 'Major', True, 3),
            ('2.1', 'Content Accuracy & Completeness', 'ข้อมูล ตัวเลข สถิติ ข้อเท็จจริง และสูตรคำนวณ ตรวจสอบแล้วถูกต้องและมีแหล่งอ้างอิงน่าเชื่อถือ', '100% Verified Accuracy (ถูกต้อง 100%)', 'Critical', True, 4),
            ('2.2', 'Content Accuracy & Completeness', 'เนื้อหาครอบคลุมตามโจทย์/Scope/TOC ที่กำหนดไว้ ไม่มีส่วนสำคัญขาดหายไป', '100% Scope Coverage (ครบตาม Scope)', 'Major', True, 5),
            ('2.3', 'Content Accuracy & Completeness', 'ภาษาที่ใช้ชัดเจน ตรงประเด็น อ่านแล้วเข้าใจตรงกัน ไม่เกิดการตีความผิดพลาด', '0 Ambiguity (ไม่มีจุดคลุมเครือ)', 'Minor', False, 6),
            ('2.4', 'Content Accuracy & Completeness', 'มีเอกสารแนบ, รูปภาพ, ตาราง, และอภิธานศัพท์ (Glossary) ประกอบครบถ้วน', '100% Complete Attachments', 'Minor', False, 7),
            ('3.1', 'Format & Consistency', 'ฟอนต์, ขนาดตัวอักษร, ระยะขอบ, การเว้นบรรทัด และการใช้สี เป็นไปตาม Template / CI', '100% CI Compliance (ตรงตาม CI)', 'Minor', False, 8),
            ('3.2', 'Format & Consistency', 'เลขหัวข้อ, เลขหน้า, สารบัญ, สารบัญภาพ/ตาราง อัปเดตตรงกับเนื้อหาจริงทั้งฉบับ', '100% Page & TOC Match', 'Major', True, 9),
            ('3.3', 'Format & Consistency', 'ไม่มีคำผิด (Typo), ไวยากรณ์ถูกต้อง และใช้คำศัพท์เฉพาะ (Terminology) เป็นมาตรฐานเดียวกัน', '< 1% Typo Rate (คำผิด < 1%)', 'Minor', False, 10),
            ('4.1', 'Governance & Control', 'มีการระบุ Document Title, Version Number, วันที่อัปเดต และชื่อผู้แต่ง/ผู้แก้ไขชัดเจน', '100% Header & Metadata', 'Major', True, 11),
            ('4.2', 'Governance & Control', 'มีประวัติการแก้ไข (Document History / Revision Log) สรุปการเปลี่ยนแปลงในแต่ละเวอร์ชัน', '100% Logged History', 'Minor', False, 12),
            ('4.3', 'Governance & Control', 'จัดทำเอกสารฉบับสะอาด (Clean Version) ที่ปิด Track Changes และ Remove Comment ร่างออกเรียบร้อย', '0 Draft Comments (ฉบับสะอาด 100%)', 'Major', True, 13)
        ]

        # Seed Default Universal Template
        cur.execute("SELECT template_id FROM exit_criteria_templates WHERE title = 'Universal Document Exit Criteria';")
        res = cur.fetchone()
        
        if not res:
            print("Seeding Universal Exit Criteria Template...")
            cur.execute("""
                INSERT INTO exit_criteria_templates (title, description, doc_type, is_active, max_loops)
                VALUES (
                    'Universal Document Exit Criteria',
                    'เกณฑ์การผ่านมาตรฐานกลางสำหรับการตรวจเอกสารทุกประเภท (General Document Review Gate)',
                    'ALL',
                    TRUE,
                    3
                )
                RETURNING template_id;
            """)
            template_id = cur.fetchone()[0]

            for code, cat, q, metric, sev, mand, idx in default_items:
                cur.execute("""
                    INSERT INTO exit_criteria_items (template_id, item_code, category, question_text, target_metric, severity, is_mandatory, order_index)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """, (template_id, code, cat, q, metric, sev, mand, idx))
            print(f"Universal Template seeded successfully with ID: {template_id}")
        else:
            template_id = res[0]
            print("Universal Exit Criteria Template already exists.")

        # Sync template to agent_skills
        try:
            print("Syncing Exit Criteria to agent_skills table...")
            cur.execute("""
                SELECT item_code, category, question_text, target_metric, severity, is_mandatory, order_index
                FROM exit_criteria_items WHERE template_id = %s ORDER BY order_index ASC, item_code ASC;
            """, (template_id,))
            items = cur.fetchall()

            md_text = "# 📋 Universal Document Exit Criteria Checklist (Skill.md)\n\n"
            md_text += "> **Description:** เกณฑ์การผ่านมาตรฐานกลางสำหรับการตรวจเอกสารทุกประเภท (General Document Review Gate)\n"
            md_text += "> **Target Document Type:** ALL\n\n"
            md_text += "## 🎯 Objective\n"
            md_text += "Evaluate document content against the universal exit criteria checklist items prior to sign-off.\n\n"

            current_cat = None
            for item_code, category, question, metric, severity, is_mandatory, idx in items:
                if category != current_cat:
                    current_cat = category
                    md_text += f"\n### {category}\n"
                mand_str = "[Mandatory]" if is_mandatory else "[Optional]"
                md_text += f"- **{item_code}** ({severity} | KPI: {metric or '100%'} | {mand_str}): {question}\n"

            md_text += "\n## 🚦 Final Gate Assessment Rules\n"
            md_text += "1. **PASSED:** All relevant items evaluated as PASS.\n"
            md_text += "2. **CONDITIONAL PASSED:** Pass all items in Category 1, 2, and 4; fail only minor formatting/typo items in Category 3.\n"
            md_text += "3. **REJECTED:** Fail any item in Category 1 (Defect Resolution) or Category 2 (Content Accuracy).\n"

            skill_name = "[Exit Criteria] Universal Document Exit Criteria"
            cur.execute("SELECT skill_id FROM agent_skills WHERE skill_name = %s;", (skill_name,))
            existing_skill = cur.fetchone()

            if existing_skill:
                cur.execute("""
                    UPDATE agent_skills
                    SET skill_description = 'Universal Exit Criteria Standard Gate Checklist for ALL',
                        markdown_instructions = %s, target_doc_type = 'ALL', is_active = TRUE, version = version + 1
                    WHERE skill_id = %s;
                """, (md_text, existing_skill[0]))
            else:
                cur.execute("""
                    INSERT INTO agent_skills (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by)
                    VALUES (%s, %s, %s, 'ALL', 1, TRUE, 'Exit Criteria System');
                """, (skill_name, 'Universal Exit Criteria Standard Gate Checklist for ALL', md_text))
            print("Exit Criteria synced to agent_skills successfully!")
        except Exception as skill_err:
            print(f"Warning: Failed to sync skill: {skill_err}")

        cur.close()
        conn.close()
        print("Exit Criteria DB Migration Completed Successfully!")

    except Exception as e:
        print(f"Error setting up Exit Criteria DB: {e}")

if __name__ == '__main__':
    add_exit_criteria_tables()
