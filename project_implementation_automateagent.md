# 🚀 Implementation Plan: Autonomous QA & Test Automation Synthesis Platform

แผนการปฏิบัติงาน (Implementation Plan) นี้จัดทำขึ้นเพื่อแปลงสถาปัตยกรรมระบบ Autonomous QA ให้กลายเป็นระบบที่ใช้งานได้จริง โดยจะผสานรวมเข้ากับโครงสร้างโปรเจกต์ปัจจุบัน (Python Backend + Svelte Frontend + PostgreSQL pgvector) 

---

## 🏗️ 1. ภาพรวมสถาปัตยกรรมและเทคโนโลยีที่ใช้ (Tech Stack)

*   **Backend & Orchestration:** Python (FastAPI / Flask) เป็นแกนหลักในการควบคุม Agents
*   **Frontend:** Svelte สำหรับ Dashboard จัดการโปรเจกต์, แสดง Defect Report และควบคุมการรัน Test
*   **Database & Vector Store:** PostgreSQL + `pgvector` (สำหรับ RAG และ Semantic Search)
*   **LLM Engine:** Gemini 3.1 Pro (สำหรับวิเคราะห์เอกสาร, จัดรูปแบบข้อมูล และ Test Generation)
*   **Browser Automation & Testing:** Playwright (TypeScript), Browser-use / Stagehand (สำหรับ Web Explorer Agent)

### 🗄️ 1.5 โครงสร้างการจัดเก็บข้อมูล (Database Separation)
ระบบถูกออกแบบให้มีการแยกฐานข้อมูลตามวัตถุประสงค์การใช้งานอย่างชัดเจน เพื่อความปลอดภัยและประสิทธิภาพ:
*   **`AIAgentQA` (Primary AI DB):** จัดเก็บข้อมูลหลักของระบบ ได้แก่ ข้อมูลโครงการ (Projects), ข้อมูลเอกสาร (Documents), ข้อมูลเวกเตอร์ (Document Chunks สำหรับ RAG), API Specs, และผลลัพธ์จาก AI (QA Transactions)
*   **`qa_agent_db` (OCR & Logging DB):** จัดเก็บข้อมูลระบบทั่วไปและ Log ได้แก่ ประวัติการทำ OCR แบบเดิม (OCR History), ประวัติการใช้งาน Token (API Usage Logs), และยอดเครดิต (Billing Credit)
*   **`postgres` (Auth DB - Port 8124):** ฐานข้อมูลแยกเฉพาะสำหรับดูแลระบบสมาชิก (Usernames, Passwords, Session)

### 🖥️ 1.6 ส่วนติดต่อผู้ใช้งานและการเชื่อมต่อ (UI & Integration)
*   **User Interface (ฝั่งผู้ใช้งานทั่วไป):** เมนูสำหรับเข้าถึงระบบ AI Agent ในการสร้าง Test Automation จะถูกจัดเก็บไว้ภายใต้เมนูชื่อ **"QA Test Automation"**
*   **Document Management (ฝั่ง Admin):** ระบบอัปโหลดและจัดการเอกสารโครงการ (Requirements, Specs) จะใช้โมดูลเดิมที่มีอยู่แล้วในฝั่ง Admin เพื่อลดความซ้ำซ้อน
*   **MCP Support (Model Context Protocol):** ระบบจะถูกออกแบบให้รองรับสถาปัตยกรรม MCP เพื่อเปิดทางให้ AI Agents (เช่น Agent 2, 3) สามารถดึงข้อมูลเอกสาร หรือควบคุม Browser Automation ผ่าน Tools/Resources ได้ตามมาตรฐาน MCP ของ Anthropic/Google

---

## 📅 2. แผนการพัฒนาและแบ่งการทำงาน (Phase Breakdown)

### 📌 Phase 1: Foundation & Document Ingestion (สัปดาห์ที่ 1 - 4)
**เป้าหมาย:** สร้างระบบย่อยความต้องการ (Agent 1) ให้อยู่ในรูปแบบที่ AI นำไปประมวลผลต่อได้ง่าย (Machine-Readable)

*   **1.1 Document Parsing Engine:**
    *   พัฒนาโมดูลอ่านไฟล์ PDF, Word (`.docx`), และ Swagger/OpenAPI (JSON/YAML)
    *   *Task:* สร้าง Script สกัดข้อความ, ตาราง, API Endpoint และจัดหมวดหมู่ข้อมูล
*   **1.2 RAG Pipeline (Retrieval-Augmented Generation):**
    *   นำข้อมูลที่สกัดได้แปลงเป็น Embeddings และเก็บลง `pgvector`
    *   *Task:* ปรับปรุงโครงสร้างตาราง `document_chunks` เพื่อรองรับ Context ของ Test Spec
*   **1.3 Standard JSON Schema (Structured Requirements):**
    *   ออกแบบ Schema มาตรฐานเพื่อแปลง Context ให้เป็น Business Rules และ Intent (เช่น Action, Expected Result)
    *   *Task:* ใช้ Gemini สกัด Requirement ดิบให้อยู่ในรูปแบบ JSON Schema ที่กำหนด

### 📌 Phase 2: Autonomous Web Exploration (สัปดาห์ที่ 5 - 8)
**เป้าหมาย:** สร้าง AI สำหรับท่องเว็บ (Agent 2) เพื่อดึงโครงสร้างหน้าเว็บจริงมาเทียบกับเอกสาร

*   **2.1 Browser Control Agent:**
    *   บูรณาการ Playwright ร่วมกับ LLM (เช่น การใช้ `browser-use` หรือ `stagehand`) เพื่อให้ AI สามารถนำทาง (Navigate), คลิก, และกรอกฟอร์มได้เองใน Sandbox Environment
*   **2.2 State & DOM Capture:**
    *   พัฒนาระบบสกัด Accessibility Tree (AOM), DOM Snapshot และบันทึก Interactive Elements
    *   บันทึก Network Logs (API Calls ที่เกิดขึ้นระหว่างการคลิก)
*   **2.3 Data Storage:**
    *   บันทึก State Transitions ของเว็บ (Live Web State) ให้อยู่ในรูปแบบ JSON เพื่อส่งต่อให้ Phase 3

### 📌 Phase 3: Semantic Alignment & Test Generation (สัปดาห์ที่ 9 - 12)
**เป้าหมาย:** วิเคราะห์ช่องโหว่ (Gap) และสร้างโค้ดทดสอบอัตโนมัติ (Agent 3 & 4)

*   **3.1 Discrepancy & Alignment Agent (Agent 3):**
    *   สร้าง Prompt Engine นำ `Structured Requirements (Phase 1)` มาเทียบกับ `Live Web State (Phase 2)`
    *   วิเคราะห์ความไม่สอดคล้อง เช่น "ปุ่มที่ระบุในเอกสารไม่มีบนเว็บ" หรือ "API ตอบกลับไม่ตรงกับ Swagger"
    *   สร้าง **Defect & Gap Report** (Markdown / JSON)
*   **3.2 Test Generator Agent (Agent 4):**
    *   รับข้อมูล Flow ที่ผ่านการตรวจสอบแล้ว (Intermediate Spec) มาแปลงเป็น Test Script
    *   สร้าง Code Generator ที่เขียนสคริปต์ **Playwright (TypeScript)** ตาม Design Pattern แบบ **Page Object Model (POM)**

### 📌 Phase 4: Execution Engine, CI/CD & Self-Healing (สัปดาห์ที่ 13 - 16)
**เป้าหมาย:** รันสคริปต์ ซ่อมแซมตัวเองเมื่อสคริปต์พัง และแจ้งเตือน (Agent 5)

*   **4.1 Test Runner Integration:**
    *   สร้างระบบรันคำสั่ง Playwright Test ผ่าน Backend (Python ควบคุม Node.js) และดึงผลลัพธ์มาแสดงบน Svelte Frontend
*   **4.2 Self-Healing Mechanism (Agent 5):**
    *   เมื่อสคริปต์พัง (Timeout หรือ ElementNotFound) ให้ดึง DOM ล่าสุด ณ จุดที่พัง ส่งให้ Gemini ค้นหา Selector ใหม่
    *   ให้ Agent ทำการ Patch โค้ด Playwright ชั่วคราวหรือถาวร เพื่อให้รันผ่าน
*   **4.3 Issue Tracker Integration:**
    *   เชื่อมต่อ API ของ Jira เพื่อสร้าง Defect/Bug Ticket อัตโนมัติจาก Report ใน Phase 3 และ Phase 4

---

## 🛡️ 5. การจัดการความเสี่ยง (Risk Management System)

ระบบจะถูกป้องกันด้วยกลไกต่อไปนี้เพื่อความปลอดภัย:
1.  **Whitelist / Blacklist URLs:** บังคับให้ Web Explorer Agent รันได้เฉพาะบน Domain หรือ Environment ที่กำหนด (เช่น `*.staging.mycompany.com`)
2.  **Selector Hierarchy Rule:** บังคับ Test Generator ให้เลือกใช้ Locator เรียงตามลำดับ: `Accessibility Role` -> `getByLabel` -> `data-testid` -> `CSS/XPath` เพื่อความทนทานต่อ UI เปลี่ยนแปลง (ลดโอกาสสคริปต์เปราะบาง)
3.  **Human-in-the-Loop (HITL):** มีหน้า UI (Svelte) ให้ QA/Developer กดยืนยัน Defect Report ก่อนระบบจะส่งต่อให้ Test Generator สร้างโค้ด

---

## 🛠️ 6. ขั้นตอนการลงมือทำทันที (Next Action Items)

เราสามารถเริ่มต้นพัฒนาจาก **Phase 2** ได้เลยเนื่องจาก Phase 1 เสร็จสมบูรณ์แล้ว:
1.  **[x]** ออกแบบ Standard JSON Schema สำหรับเก็บ Requirements เพื่อให้ Agent ทำงานง่ายขึ้น
2.  **[x]** เขียน Backend Module (Python) สำหรับอ่านและสกัดไฟล์ PDF/Docx/Swagger 
3.  **[x]** สร้าง/ปรับปรุงโครงสร้างตาราง Vector Database เพื่อรับรอง Document Chunks รูปแบบใหม่

**เป้าหมายถัดไป (Phase 2):**
94.  **[x]** ติดตั้งและคอนฟิก Playwright สำหรับ Browser Automation ในฝั่ง Backend
95.  **[x]** สร้าง Agent 2 สำหรับควบคุม Browser, จับภาพ Snapshot, และบันทึก Live Web State เป็น JSON

**เป้าหมายถัดไป (Phase 3):**
96.  **[x]** สร้าง Agent 3 สำหรับเปรียบเทียบ Structured Requirements กับ Live Web State
97.  **[x]** พัฒนาหน้าจอ UI (Phase 3) แสดงผล Gap Analysis Report ให้ผู้ใช้พิจารณา
98.  **[x]** สร้าง Agent 4 สำหรับแปลง Gap Analysis และ Requirement เป็น Playwright Test Script (POM)
99.  **[x]** พัฒนาหน้าจอ UI (Phase 4) เพื่อกดสร้าง Test Script และแสดงผลโค้ด

**เป้าหมายถัดไป (Phase 4): Execution & CI/CD**
100. **[x]** สร้างระบบรัน Playwright Script จากหน้าเว็บ และดึงผล Test Report มาแสดง
101. **[x]** สร้างระบบ Self-Healing (Agent 5) เพื่อแก้ Test Script เมื่อ UI มีการเปลี่ยนแปลง
