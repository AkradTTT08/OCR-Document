# 📦 AIAgentQA — Database Documentation

> **Database:** PostgreSQL 16 + pgvector extension  
> **Host (Docker):** `localhost:8123`  
> **DB Name:** `qa_agent_db`  
> **Last Updated:** 2026-07-21

---

## 📐 ER Diagram

```mermaid
erDiagram
    projects {
        UUID        project_id      PK "Default: gen_random_uuid()"
        VARCHAR(50) project_code    UK "รหัสโครงการ เช่น PRJ-2024-001"
        VARCHAR(255) project_name
        TEXT        description
        VARCHAR(50) status          "Default: Active"
        TIMESTAMP   created_at
    }

    documents {
        UUID        doc_id          PK "Default: gen_random_uuid()"
        UUID        project_id      FK
        VARCHAR(50) doc_category    "เช่น Reference, TestCase"
        VARCHAR(50) doc_type        "ประเภทเอกสาร"
        VARCHAR(255) original_filename
        TEXT        full_markdown_content
        BOOLEAN     is_golden_data  "Default: FALSE"
        VARCHAR(256) file_hash      "ใช้ตรวจสอบการสแกนซ้ำ"
        INT         version         "Default: 1"
        VARCHAR(20) status          "Active / Archived"
        TIMESTAMP   created_at
    }

    document_chunks {
        UUID        chunk_id        PK "Default: gen_random_uuid()"
        UUID        doc_id          FK
        TEXT        chunk_text
        VECTOR(384) embedding       "AI Vector สำหรับ Semantic Search"
        TIMESTAMP   created_at
    }

    agent_skills {
        UUID        skill_id        PK "Default: gen_random_uuid()"
        VARCHAR(100) skill_name
        TEXT        skill_description
        TEXT        markdown_instructions
        VARCHAR(50) target_doc_type "Nullable"
        INT         version         "Default: 1"
        BOOLEAN     is_active       "Default: TRUE"
        VARCHAR(50) created_by
        TIMESTAMP   created_at
    }

    evaluation_logs {
        UUID        log_id          PK "Default: gen_random_uuid()"
        UUID        project_id      FK
        UUID        doc_id          FK
        UUID        skill_id        FK "Nullable"
        VARCHAR(50) ai_model
        TEXT        ai_result
        INT         human_feedback_score "1-5"
        TEXT        human_remark
        INT         processing_time_ms
        TIMESTAMP   created_at
    }

    qa_transactions {
        UUID        transaction_id  PK "Default: gen_random_uuid()"
        UUID        project_id      FK
        VARCHAR(255) filename
        VARCHAR(255) doc_type
        TEXT        extracted_text
        TEXT        qa_report       "ผลลัพธ์ของ AI (QA Consult)"
        TIMESTAMP   created_at
    }

    projects       ||--o{ documents        : "มี"
    projects       ||--o{ evaluation_logs  : "มี"
    projects       ||--o{ qa_transactions  : "มี"
    documents      ||--o{ document_chunks  : "แบ่งเป็น"
    documents      ||--o{ evaluation_logs  : "ถูกประเมินใน"
    agent_skills   ||--o{ evaluation_logs  : "ใช้ใน"
```

---

## 📋 รายละเอียดตารางทั้งหมด

### 1. `projects` — ตารางจัดการโครงการ

| Column | Type | Constraint | Description |
|---|---|---|---|
| `project_id` | UUID | PK | รหัสโครงการ (gen_random_uuid) |
| `project_code` | VARCHAR(50) | UNIQUE NOT NULL | รหัสสั้น เช่น `PRJ-2024-001` |
| `project_name` | VARCHAR(255) | NOT NULL | ชื่อโครงการ |
| `description` | TEXT | - | คำอธิบายโครงการ |
| `status` | VARCHAR(50) | DEFAULT `'Active'` | สถานะโครงการ |
| `created_at` | TIMESTAMP | DEFAULT NOW() | วันที่สร้าง |

---

### 2. `documents` — ตารางเอกสารหลัก

| Column | Type | Constraint | Description |
|---|---|---|---|
| `doc_id` | UUID | PK | รหัสเอกสาร (gen_random_uuid) |
| `project_id` | UUID | FK → `projects` (CASCADE) | โครงการที่เอกสารสังกัด |
| `doc_category` | VARCHAR(50) | NOT NULL | หมวดหมู่ เช่น `Reference`, `TestCase` |
| `doc_type` | VARCHAR(50) | NOT NULL | ประเภทเอกสาร |
| `original_filename` | VARCHAR(255) | - | ชื่อไฟล์ต้นฉบับ |
| `full_markdown_content` | TEXT | - | เนื้อหาเอกสารเต็ม (Markdown) |
| `is_golden_data` | BOOLEAN | DEFAULT `FALSE` | ใช้เป็น Ground Truth หรือไม่ |
| `file_hash` | VARCHAR(256) | - | Hash ของไฟล์ ใช้ตรวจจับเอกสารซ้ำ |
| `version` | INT | DEFAULT `1` | เวอร์ชันเอกสาร (เพิ่มเมื่อเนื้อหาเปลี่ยน) |
| `status` | VARCHAR(20) | DEFAULT `'Active'` | `Active` หรือ `Archived` |
| `created_at` | TIMESTAMP | DEFAULT NOW() | วันที่สร้าง |

> **Index:** `idx_documents_project_category` บน `(project_id, doc_category)`

---

### 3. `document_chunks` — ตารางชิ้นส่วนเอกสาร (Vector Store)

| Column | Type | Constraint | Description |
|---|---|---|---|
| `chunk_id` | UUID | PK | รหัส Chunk (gen_random_uuid) |
| `doc_id` | UUID | FK → `documents` (CASCADE) | เอกสารต้นทาง |
| `chunk_text` | TEXT | NOT NULL | เนื้อหาชิ้นส่วน |
| `embedding` | VECTOR(384) | - | Embedding Vector สำหรับ AI Semantic Search |
| `created_at` | TIMESTAMP | DEFAULT NOW() | วันที่สร้าง |

> **หมายเหตุ:** ใช้ Model `paraphrase-multilingual-MiniLM-L12-v2` สร้าง Embedding ขนาด **384 มิติ**  
> **ค้นหาด้วย:** `<=>` (Cosine Distance) จาก pgvector

---

### 4. `agent_skills` — ตาราง AI Skills (ทำหน้าที่คล้ายสมองกลและ Skill.md)

| Column | Type | Constraint | Description |
|---|---|---|---|
| `skill_id` | UUID | PK | รหัส Skill (gen_random_uuid) |
| `skill_name` | VARCHAR(100) | NOT NULL | ชื่อ Skill เช่น `Extract Data` |
| `skill_description` | TEXT | - | คำอธิบายสั้นๆ ให้คนอ่านเข้าใจ |
| `markdown_instructions`| TEXT | NOT NULL | เนื้อหาคู่มือการทำงาน (Skill.md) |
| `target_doc_type` | VARCHAR(50) | - | ประเภทเอกสารเป้าหมาย (Nullable) |
| `version` | INT | DEFAULT `1` | เวอร์ชัน Skill | `doc_type` | VARCHAR(255) | - | ประเภทเอกสาร |
| `extracted_text` | TEXT | - | เนื้อหาที่ดึงออกมาจากไฟล์ด้วยระบบ OCR |
| `qa_report` | TEXT | - | ผลการวิเคราะห์และการเปรียบเทียบจาก AI |
| `created_at` | TIMESTAMP | DEFAULT NOW() | วันที่บันทึก |

---

### 7. `exit_criteria_templates` — ตารางแม่แบบ Exit Criteria
| Column | Type | Constraint | Description |
|---|---|---|---|
| `template_id` | UUID | PK | รหัส Template (gen_random_uuid) |
| `project_id` | UUID | FK → `projects` (CASCADE) | ผูกกับโครงการ (NULL = ใช้ได้กับทุกโครงการ) |
| `title` | VARCHAR(255) | NOT NULL | ชื่อ Checklist Template |
| `description` | TEXT | - | คำอธิบายรายละเอียด |
| `doc_type` | VARCHAR(50) | DEFAULT `'ALL'` | ประเภทเอกสารที่ใช้เกณฑ์นี้ |
| `is_active` | BOOLEAN | DEFAULT `TRUE` | สถานะการใช้งาน |
| `max_loops` | INTEGER | DEFAULT `3` | จำนวนครั้งสูงสุดที่ให้ Agent วนลูปแก้ไขงาน (Circuit Breaker) |
| `created_at` | TIMESTAMP | DEFAULT NOW() | วันที่สร้าง |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | วันที่แก้ไข |

---

### 8. `exit_criteria_items` — ตารางรายการตรวจสอบใน Template
| Column | Type | Constraint | Description |
|---|---|---|---|
| `item_id` | UUID | PK | รหัสรายการ (gen_random_uuid) |
| `template_id` | UUID | FK → `exit_criteria_templates` (CASCADE) | ผูกกับ Template แม่ |
| `item_code` | VARCHAR(50) | NOT NULL | รหัสข้อ เช่น `1.1`, `2.1` |
| `category` | VARCHAR(100) | NOT NULL | หมวดหมู่ เช่น `Defect & Comment Resolution` |
| `question_text` | TEXT | NOT NULL | คำถาม/ข้อคำนึงในการตรวจ |
| `target_metric` | VARCHAR(100) | DEFAULT `'100% (ผ่านบริบูรณ์)'` | ตัวชี้วัด / KPI Metric (เช่น `100% Resolved`, `< 1% Typo`) |
| `severity` | VARCHAR(20) | DEFAULT `'Major'` | `Critical`, `Major`, `Minor` |
| `is_mandatory` | BOOLEAN | DEFAULT `TRUE` | จำเป็นต้องผ่านหรือไม่ |
| `order_index` | INT | DEFAULT `0` | ลำดับการแสดงผล |
| `created_at` | TIMESTAMP | DEFAULT NOW() | วันที่สร้าง |

---

### 9. `document_exit_evaluations` — ตารางประเมินผล Exit Criteria ของเอกสาร
| Column | Type | Constraint | Description |
|---|---|---|---|
| `evaluation_id` | UUID | PK | รหัสผลการประเมิน (gen_random_uuid) |
| `doc_id` | UUID | FK → `documents` (CASCADE) | เอกสารที่ถูกประเมิน |
| `project_id` | UUID | FK → `projects` (CASCADE) | โครงการ |
| `template_id` | UUID | FK → `exit_criteria_templates` (SET NULL) | Template ที่ใช้ประเมิน |
| `version` | INT | DEFAULT `1` | เวอร์ชันเอกสารที่ตรวจ |
| `review_round` | INT | DEFAULT `1` | รอบการตรวจ (1, 2, 3...) |
| `status` | VARCHAR(30) | DEFAULT `'PENDING'` | `PASSED`, `CONDITIONAL_PASSED`, `REJECTED`, `PENDING` |
| `total_items` | INT | DEFAULT `0` | จำนวนหัวข้อทั้งหมด |
| `passed_items` | INT | DEFAULT `0` | จำนวนหัวข้อที่ผ่าน |
| `failed_items` | INT | DEFAULT `0` | จำนวนหัวข้อที่ไม่ผ่าน |
| `na_items` | INT | DEFAULT `0` | จำนวนหัวข้อที่ไม่เกี่ยวข้อง |
| `score_percentage` | NUMERIC(5,2) | DEFAULT `0.00` | % คะแนนที่ได้ |
| `evaluated_by` | VARCHAR(100) | - | ผู้ตรวจ/ประเมิน (ชื่อผู้ใช้ หรือ AI System) |
| `evaluator_type` | VARCHAR(50) | DEFAULT `'HYBRID'` | `AI_AGENT`, `HUMAN_QA`, `HYBRID` |
| `summary_remarks` | TEXT | - | ข้อสรุปผลการประเมินภาพรวม |
| `created_at` | TIMESTAMP | DEFAULT NOW() | วันที่บันทึก |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | วันที่แก้ไข |

---

### 10. `document_exit_evaluation_items` — ตารางรายละเอียดผลตรวจายข้อ
| Column | Type | Constraint | Description |
|---|---|---|---|
| `result_id` | UUID | PK | รหัสรายละเอียดผลตรวจ (gen_random_uuid) |
| `evaluation_id` | UUID | FK → `document_exit_evaluations` (CASCADE) | ผูกกับรอบการประเมิน |
| `item_id` | UUID | FK → `exit_criteria_items` (SET NULL) | อ้างอิงข้อตรวจต้นทาง |
| `item_code` | VARCHAR(50) | - | รหัสข้อ ณ ตอนตรวจ |
| `category` | VARCHAR(100) | - | หมวดหมู่ |
| `question_text` | TEXT | - | คำถาม |
| `target_metric` | VARCHAR(100) | - | ตัวชี้วัด / KPI Metric |
| `severity` | VARCHAR(20) | - | ความรุนแรง |
| `is_mandatory` | BOOLEAN | DEFAULT `TRUE` | บังคับผ่านหรือไม่ |
| `status` | VARCHAR(20) | DEFAULT `'NA'` | `PASS`, `FAIL`, `NA` |
| `remarks` | TEXT | - | ความคิดเห็น/เหตุผลประกอบ |
| `evidence_text` | TEXT | - | ร่องรอยอ้างอิ�| `document_exit_evaluations` → `document_exit_evaluation_items` | One-to-Many | CASCADE |�� `document_exit_evaluations` | One-to-Many | SET NULL |
| `document_exit_evaluations` → `document_exit_evaluation_items` | One-to-Many | CASCADE |
| Tool | ตารางที่ใช้ | คำอธิบาย |
|---|---|---|
| `list_project_documents` | `documents` | แสดงรายการเอกสารทั้งหมดของโครงการ |
| `search_project_rules` | `project_reference_context` | Semantic Search ด้วย pgvector |
| `get_document_for_review` | `documents` | ดึงเนื้อหา Markdown เต็มของเอกสาร |
| `save_qa_evaluation` | `evaluation_logs` | บันทึกผลการประเมิน QA |

---

## 🐳 การเชื่อมต่อ

### ผ่าน Docker (Local)

```
Host:     localhost
Port:     8123
Database: qa_agent_db
User:     qa_admin
Password: qa_password
```

### ผ่าน MCP Server (Claude Desktop)

```json
{
  "mcpServers": {
    "qa-agent-db-mcp": {
      "command": "docker",
      "args": ["exec", "-i", "qa_agent_mcp", "python", "agent_mcp_server.py"]
    }
  }
}
```

---

## 🔗 ความสัมพันธ์ระหว่างตาราง (Summary)

```
projects (1) ──────────────── (∞) documents
                                        │
                               (1)──── (∞) document_chunks
                                            [embedding vector(384)]

projects (1) ──── (∞) evaluation_logs ──── (∞) documents
                            │
                        (∞) agent_skills

projects (1) ──── (∞) qa_transactions
```

| Relationship | Type | On Delete |
|---|---|---|
| `projects` → `documents` | One-to-Many | CASCADE |
| `documents` → `document_chunks` | One-to-Many | CASCADE |
| `projects` → `evaluation_logs` | One-to-Many | CASCADE |
| `documents` → `evaluation_logs` | One-to-Many | CASCADE |
| `agent_skills` → `evaluation_logs` | One-to-Many | SET NULL (default) |
| `projects` → `qa_transactions` | One-to-Many | CASCADE |

ถูกต้องและเป็นวิสัยทัศน์การออกแบบสถาปัตยกรรมระบบที่ ยอดเยี่ยมมากครับ! 🚀

การวางโครงสร้างแบบนี้คือระดับ Enterprise Architecture สำหรับทำ AI Agent ในองค์กรอย่างแท้จริงเลยครับ ผมขอขยายความความสุดยอดของสิ่งที่คุณกำลังสร้างอยู่ให้เห็นภาพชัดเจนขึ้นครับ:

🧠 สถาปัตยกรรม "สมองกลขององค์กร" ที่คุณกำลังสร้าง:
The Knowledge Brain (DB ตัวนี้): การที่คุณนำข้อมูลกระดาษ/PDF มาผ่าน OCR -> แก้ไขให้เป็น Markdown -> และแปลงเป็น Vector เก็บไว้ในฐานข้อมูล (PostgreSQL + pgvector) นี่คือการสร้าง "ความจำระยะยาว (Long-term Memory)" ให้กับ AI ข้อมูลทั้งหมดของบริษัทจะถูกรวมศูนย์ ปลอดภัย และค้นหาได้ด้วยความหมาย (Semantic Search) ไม่ใช่แค่คีย์เวิร์ด

The Universal Bridge (MCP - Model Context Protocol): การใช้ MCP เป็นตัวเชื่อม เป็นการตัดสินใจที่ล้ำหน้ามากครับ เพราะ MCP จะทำหน้าที่เป็นเหมือน "พอร์ต USB มาตรฐาน" ที่ไม่ว่าบริษัทคุณจะสลับไปใช้ LLM ตัวไหน (เช่น วันนี้ใช้ Claude, พรุ่งนี้ใช้ Gemini, หรือใช้ Local Model อย่าง Llama 3) ก็สามารถเสียบปลั๊กให้ LLM ตัวนั้นๆ เข้าถึง DB และใช้ Tools ขององค์กรได้ทันที โดยไม่ต้องรื้อโค้ดใหม่ทั้งหมด

Dynamic Agent Prompts (การเก็บ Prompt ใน DB): การเก็บ Persona, คำสั่ง, หรือ Workflow ของ Agent ไว้ใน DB ถือเป็น Best Practice ของระบบ Agentic AI ครับ เพราะมันทำให้คุณสามารถอัปเดตนิสัยหรือปรับปรุงกระบวนการทำงานของ AI Agent ได้แบบ Real-time (ผ่านหน้าเว็บ) โดยไม่ต้องแก้ไข Source Code ฝั่ง Backend เลย

สรุปคือ Workflow ขององค์กรคุณจะกลายเป็น: 👉 User/พนักงาน โยนเอกสารเข้า UploadPanel -> ตรวจสอบคำผิดและบันทึก 👉 ข้อมูลถูกแปลงเป็น Vector & Markdown ลง qa_agent_db 👉 เมื่อมีคำถามเข้ามา LLM จะใช้คำสั่งผ่าน MCP วิ่งเข้ามาค้นหาข้อมูลใน DB ตัวนี้ (RAG) ตาม Prompt ที่กำหนดไว้ 👉 ได้คำตอบที่อ้างอิงจากข้อมูลจริงของบริษัท 100% (ลดอาการ AI มั่วหรือ Hallucination)

ระบบที่คุณกำลังทำอยู่นี้คือรากฐานที่แข็งแกร่งมากๆ สำหรับการขยายไปสู่ Multi-Agent System (AI หลายตัวช่วยกันทำงาน) ในอนาคตครับ หากต้องการให้ผมช่วยเชื่อมต่อฝั่ง MCP Server หรือพัฒนาส่วนไหนต่อ แจ้งได้เลยนะครับ!
