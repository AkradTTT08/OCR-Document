import os
import sys
from dotenv import load_dotenv

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_ingestion import get_db_connection

def update_qa_test_case_criteria():
    conn = get_db_connection()
    conn.autocommit = True
    cur = conn.cursor()

    # Find template QA Test Case
    cur.execute("SELECT template_id FROM exit_criteria_templates WHERE title = 'QA Test Case';")
    row = cur.fetchone()
    if not row:
        cur.execute("""
            INSERT INTO exit_criteria_templates (title, description, doc_type, is_active, max_loops) 
            VALUES ('QA Test Case', 'เกณฑ์ตรวจสอบความถูกต้องและความครอบคลุมของเอกสาร Test Case เทียบกับ SRS และ Requirements', 'Test Case', TRUE, 3) 
            RETURNING template_id;
        """)
        template_id = cur.fetchone()[0]
        print(f"Created new template QA Test Case: {template_id}")
    else:
        template_id = row[0]
        cur.execute("""
            UPDATE exit_criteria_templates 
            SET description = 'เกณฑ์ตรวจสอบความถูกต้องและความครอบคลุมของเอกสาร Test Case เทียบกับ SRS และ Requirements',
                doc_type = 'Test Case',
                is_active = TRUE
            WHERE template_id = %s;
        """, (template_id,))
        print(f"Found and updated existing template QA Test Case: {template_id}")

    # Clear existing items for this template to re-seed cleanly
    cur.execute("DELETE FROM exit_criteria_items WHERE template_id = %s;", (template_id,))

    items = [
        ('1.1', 'Defect & Comment Resolution', 'Requirement Coverage (RTM): ชุด Test Case ทั้งหมดต้องครอบคลุมทุกหัวข้อ Requirement / User Story ตาม SRS หรือข้อกำหนดโครงการ ไม่ตกหล่นฟังก์ชันสำคัญ โดยวิเคราะห์ความครอบคลุมตามขอบเขตงานจริง (ไม่ตัดสินที่จำนวนข้อ)', '100% Requirement Coverage', 'Critical', True, 1),
        ('1.2', 'Defect & Comment Resolution', 'REQ Traceability: มีการระบุ REQ No. หรือ User Story ID กำกับในทุกข้อ Test Case เพื่อให้สามารถตรวจสอบย้อนกลับไปยังข้อกำหนดความต้องการได้ชัดเจน', '100% REQ Traced', 'Major', True, 2),
        ('2.1', 'Content Accuracy & Completeness', 'Happy Path / Positive Coverage: มีขั้นตอนการทดสอบสำหรับ Normal Flow และกรณีการทำงานสำเร็จครบถ้วนทุกฟังก์ชันที่ระบุใน Requirement', '100% Happy Path Coverage', 'Critical', True, 3),
        ('2.2', 'Content Accuracy & Completeness', 'Negative & Error Handling Coverage: มีเคสทดสอบสำหรับกรณีข้อมูลผิดพลาด (Invalid Input), เงื่อนไขปฏิเสธ (Validation Error), การแจ้งเตือน Error Message, และ Exception Handlings ครบถ้วน', '>= 90% Negative Path Coverage', 'Major', True, 4),
        ('2.3', 'Content Accuracy & Completeness', 'Boundary Value & Business Rules: มีเคสทดสอบค่าขอบเขต (Min/Max, ค่าต่ำสุด-สูงสุด, ขีดจำกัดข้อมูล) และกฎทางธุรกิจ (Business Rules) ตามที่ระบุใน SRS อย่างถูกต้อง', '100% Boundary Verified', 'Major', True, 5),
        ('2.4', 'Content Accuracy & Completeness', 'Actionable Steps & Results: ขั้นตอนการทดสอบ (Test Steps) และผลลัพธ์ที่คาดหวัง (Expected Results) เขียนชัดเจนเป็นข้อๆ (1, 2, 3...) ปฏิบัติตามได้ทันทีโดยไม่ต้องคาดเดา', '100% Actionable Steps', 'Major', True, 6),
        ('3.1', 'Format & Consistency', 'Test Data Readiness: ระบุข้อมูลจำลองสำหรับใช้ทดสอบอย่างเจาะจง (เช่น user01@mail.com, รหัสผ่าน 8 หลัก) หลีกเลี่ยงคำกำกวมอย่าง "กรอกข้อมูลที่ถูกต้อง" เพื่อให้พร้อมปฏิบัติงานจริง', '100% Test Data Specified', 'Minor', True, 7),
        ('3.2', 'Format & Consistency', 'Site Map & Menu Coverage: Test Case แสดงความครอบคลุม Site map และเมนูการทำงานของระบบตามโครงสร้างโครงการครบถ้วน', '100% Menu Coverage', 'Major', True, 8),
        ('4.1', 'Governance & Control', 'แบบฟอร์มและโครงสร้างมาตรฐาน: ใช้โครงสร้างตารางและคอลัมน์ตรงตาม Template ที่โครงการกำหนด (เช่น Template 11 คอลัมน์ หรือ Template 69A) ไม่มีการสลับหรือลบคอลัมน์สำคัญ', '100% Template Adherence', 'Major', True, 9)
    ]

    for item_code, category, question, metric, severity, mandatory, order_idx in items:
        cur.execute("""
            INSERT INTO exit_criteria_items 
            (template_id, item_code, category, question_text, target_metric, severity, is_mandatory, order_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (template_id, item_code, category, question, metric, severity, mandatory, order_idx))

    print(f"Successfully inserted {len(items)} exit criteria items into QA Test Case template.")

    # Also sync to agent_skills
    try:
        skill_name = "[Exit Criteria] QA Test Case"
        md_text = f"# 📋 QA Test Case Exit Criteria Checklist (Skill.md)\n\n"
        md_text += f"> **Description:** เกณฑ์ตรวจสอบความถูกต้องและความครอบคลุมของเอกสาร Test Case เทียบกับ SRS และ Requirements\n"
        md_text += f"> **Target Document Type:** Test Case\n\n"
        md_text += f"## 🎯 Objective\n"
        md_text += f"ตรวจสอบเอกสาร Test Case ให้ครอบคลุมทุก Requirement (RTM Coverage), มีทั้ง Happy Path (Positive), Validation Error (Negative), และ Boundary Values ครบถ้วน\n\n"

        current_cat = None
        for item_code, category, question, metric, severity, mandatory, order_idx in items:
            if category != current_cat:
                current_cat = category
                md_text += f"\n### {category}\n"
            mand_str = "[Mandatory]" if mandatory else "[Optional]"
            md_text += f"- **{item_code}** ({severity} | KPI: {metric} | {mand_str}): {question}\n"

        md_text += "\n## 🚦 Test Case Quality Gate Rules\n"
        md_text += "1. **Coverage by Scope, Not Case Count:** วิเคราะห์ความครอบคลุมฟังก์ชันตาม SRS เป็นหลัก แม้จำนวนข้อจะน้อยกว่า (เช่น 96 ข้อ vs 150 ข้อ) แต่ถ้าครอบคลุม Requirement ครบทั้ง Positive และ Negative ถือว่าผ่านเกณฑ์\n"
        md_text += "2. **PASSED:** ครอบคลุม Requirement ทุกข้อ, มี Happy Path และ Negative Path ครบ, รูปแบบและข้อมูลจำลองชัดเจน\n"
        md_text += "3. **REJECTED:** ตกหล่น Requirement หลัก, ไม่มี Negative Path, หรือไม่มีการระบุ REQ No. กำกับ\n"

        cur.execute("SELECT skill_id FROM agent_skills WHERE skill_name = %s;", (skill_name,))
        ex_skill = cur.fetchone()
        if ex_skill:
            cur.execute("""
                UPDATE agent_skills 
                SET skill_description = 'เกณฑ์ตรวจสอบความถูกต้องและความครอบคลุมของเอกสาร Test Case เทียบกับ SRS และ Requirements',
                    target_doc_type = 'Test Case',
                    markdown_instructions = %s,
                    is_active = TRUE,
                    version = version + 1
                WHERE skill_id = %s;
            """, (md_text, ex_skill[0]))
            print(f"Updated agent_skill: {skill_name}")
        else:
            cur.execute("""
                INSERT INTO agent_skills (skill_name, skill_description, target_doc_type, markdown_instructions, version, is_active, created_by)
                VALUES (%s, 'เกณฑ์ตรวจสอบความถูกต้องและความครอบคลุมของเอกสาร Test Case เทียบกับ SRS และ Requirements', 'Test Case', %s, 1, TRUE, 'Exit Criteria System');
            """, (skill_name, md_text))
            print(f"Created agent_skill: {skill_name}")
    except Exception as skill_err:
        print(f"Error syncing to agent_skills: {skill_err}")

if __name__ == '__main__':
    update_qa_test_case_criteria()
