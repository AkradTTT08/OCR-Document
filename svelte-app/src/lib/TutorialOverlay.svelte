<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { fade, fly, scale, slide } from 'svelte/transition';

  export let userRole = 'admin'; // 'admin' | 'user'

  const dispatch = createEventDispatcher();
  let showStepDropdown = false;

  // ── Tutorial Steps with Detailed Workflows ──────────────────────────────
  const adminSteps = [
    {
      id: 'welcome',
      title: '👋 ยินดีต้อนรับสู่ Spectra QA Platform',
      subtitle: 'Intelligent Document Analysis & QA Automation System (Admin Mode)',
      description: `📌 **ภาพรวมระบบ**
แพลตฟอร์มการตรวจเอกสารคุณภาพและเครื่องมือ QA อัจฉริยะแบบบูรณาการ ช่วยสแกน PDF, วิเคราะห์ด้วย AI, จัดการ Knowledge Base, ออกแบบ Workflow และสั่งการ Master Agent ครบวงจร

🔄 **ลำดับ Flow การทำงานโดยรวม (System Workflow)**
🔹 **ขั้นตอนที่ 1 (ตั้งค่าโครงการ):** สร้าง Project ในเมนู Project Management เพื่อกำหนดขอบเขตงาน
🔹 **ขั้นตอนที่ 2 (สแกนเอกสาร):** อัปโหลดไฟล์ PDF ในเมนู Scan OCR เพื่อทำ OCR และตรวจคำผิด
🔹 **ขั้นตอนที่ 3 (ตรวจสอบเกณฑ์):** ระบบ AI ประเมินคุณภาพเอกสารเทียบกับ Exit Criteria 13 ข้อ
🔹 **ขั้นตอนที่ 4 (จัดเก็บ RAG):** บันทึก Chunks ข้อความลงใน Knowledge Base เพื่อใช้สืบค้น
🔹 **ขั้นตอนที่ 5 (สั่งงานอัจฉริยะ):** ใช้ Master Agent หรือ AI Workflow Builder รันกระบวนการอัตโนมัติ`,
      icon: '🚀',
      target: null,
      role: 'admin',
      color: '#6366f1',
    },
    {
      id: 'scan_ocr',
      title: '📄 Scan OCR Engine',
      subtitle: 'เมนู: Scan OCR (Admin)',
      description: `📌 **หน้าที่ของเมนู**
อัปโหลดไฟล์ PDF แปลงข้อความสแกนด้วย OCR ตรวจสอบคำผิดภาษาไทย-อังกฤษ และประเมินคุณภาพเอกสารด้วย AI

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Input):** ลากและวางไฟล์ PDF (ขนาดสูงสุด 50MB) ลงใน Upload Area
🔹 **ขั้นตอนที่ 2 (OCR Processing):** ระบบประมวลผล OCR สกัดข้อความ และแบ่งเป็น Chunks
🔹 **ขั้นตอนที่ 3 (AI Audit):** Spell Checker ตรวจคำผิด + AI Evaluator วิเคราะห์คุณภาพเอกสาร
🔹 **ขั้นตอนที่ 4 (Output):** แสดง Audit Report, สรุปรายการคำผิด และบันทึกเข้า Knowledge Base อัตโนมัติ`,
      icon: '📄',
      target: 'nav-ocr',
      role: 'admin',
      color: '#6366f1',
    },
    {
      id: 'project_management',
      title: '📁 Project Management',
      subtitle: 'เมนู: Project Management (Admin)',
      description: `📌 **หน้าที่ของเมนู**
บริหารจัดการข้อมูลโครงการ (Projects) สำหรับใช้จัดหมวดหมู่เอกสาร สิทธิ์การเข้าถึง และการรัน Workflow

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Create Project):** กดปุ่ม "+ New Project" เพื่อเริ่มต้นสร้างโครงการใหม่
🔹 **ขั้นตอนที่ 2 (Config):** ระบุ Project Code (เช่น PROJ-001), Project Name และคำอธิบายโครงการ
🔹 **ขั้นตอนที่ 3 (Binding):** นำ Project Code ไปผูกกับการ Scan OCR, กลุ่มเอกสาร QA Consult และ Workflows
🔹 **ขั้นตอนที่ 4 (Manage):** ตรวจสอบสถิติจำนวนเอกสารในโครงการ แก้ไขข้อมูล หรือลบโครงการที่ไม่ใช้งาน`,
      icon: '📁',
      target: 'nav-project-mgmt',
      role: 'admin',
      color: '#3b82f6',
    },
    {
      id: 'knowledge_base',
      title: '📚 Knowledge Base & Vector Search',
      subtitle: 'เมนู: Knowledge Base (Admin)',
      description: `📌 **หน้าที่ของเมนู**
คลังจัดเก็บข้อมูล RAG (Retrieval-Augmented Generation) และระบบค้นหาเชิงความหมายผ่าน Vector Database

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Search):** พิมพ์คำค้นหาเชิงความหมาย (Semantic Query) หรือเลือกตัวกรองตาม Project
🔹 **ขั้นตอนที่ 2 (Vector Retrieval):** ระบบคำนวณ Embedding Vector ค้นหา Chunk ที่มี Similarity สูงสุด
🔹 **ขั้นตอนที่ 3 (Inspect Chunks):** แสดงเนื้อหา Chunk, Metadata, หน้าเอกสาร และไฟล์ต้นฉบับ
🔹 **ขั้นตอนที่ 4 (AI Context Sync):** ข้อมูลใน KB จะถูกส่งเป็นบริบท (Context) ให้ Master Agent ตอบคำถาม`,
      icon: '📚',
      target: 'nav-kb',
      role: 'admin',
      color: '#8b5cf6',
    },
    {
      id: 'ai_skills',
      title: '⚡ AI Skills Manager',
      subtitle: 'เมนู: AI Skills (Admin)',
      description: `📌 **หน้าที่ของเมนู**
สร้าง แก้ไข และควบคุมความสามารถ (Instructions & Prompts) ของ AI Agents ในระบบ

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Select/New Skill):** เลือก Skill ที่มีอยู่ หรือกดสร้าง AI Skill ใหม่
🔹 **ขั้นตอนที่ 2 (Define Target):** ระบุชื่อ Skill, คำอธิบาย และประเภทเอกสารเป้าหมาย (SRS, Test Case, SDD)
🔹 **ขั้นตอนที่ 3 (Write Instructions):** เขียน Prompt ในรูปแบบ Markdown กำหนดบทบาทและกฎการวิเคราะห์ของ AI
🔹 **ขั้นตอนที่ 4 (Sync & Activate):** กด Sync Exit Criteria เพื่อดึงเกณฑ์มาตรฐานสากลมารวมใน Skill แล้วเปิดใช้งาน`,
      icon: '⚡',
      target: 'nav-skills',
      role: 'admin',
      color: '#f59e0b',
    },
    {
      id: 'qa_member',
      title: '👥 QA Member Management',
      subtitle: 'เมนู: QA Member (Admin)',
      description: `📌 **หน้าที่ของเมนู**
บริหารจัดการสิทธิ์ผู้ใช้งาน สมาชิกในทีม QA และสถานะการเข้าถึงระบบ

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Add User):** กดปุ่ม "+ Add User" เพื่อลงทะเบียนสมาชิกใหม่ในทีม
🔹 **ขั้นตอนที่ 2 (Assign Role):** กำหนด Username, Password, Display Name และ Role (System Admin / Standard User)
🔹 **ขั้นตอนที่ 3 (Account Status):** สลับสถานะบัญชี Active / Inactive เมื่อต้องการเปิดหรือระงับสิทธิ์การใช้งาน
🔹 **ขั้นตอนที่ 4 (Audit Log):** ตรวจสอบสถิติการใช้งาน Login Count, วันเวลาที่เข้าใช้งานล่าสุด และจัดการรูป Avatar`,
      icon: '👥',
      target: 'nav-qa-member',
      role: 'admin',
      color: '#10b981',
    },
    {
      id: 'exit_criteria',
      title: '✅ Exit Criteria Rules Manager',
      subtitle: 'เมนู: Exit Criteria (Admin)',
      description: `📌 **หน้าที่ของเมนู**
ตั้งค่าและจัดการเกณฑ์มาตรฐานการตรวจรับเอกสารสากล 13 ข้อ (Quality Gate Decision)

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Category Setup):** จัดหมวดหมู่กฎ (Defect Resolution, Content Accuracy, Format, Governance)
🔹 **ขั้นตอนที่ 2 (Severity Rules):** กำหนดระดับความรุนแรง Critical, Major, Minor สำหรับแต่ละเกณฑ์
🔹 **ขั้นตอนที่ 3 (Evaluation):** ระบบ AI Evaluator นำกฎเหล่านี้ไปสแกนวิเคราะห์เอกสารทุกฉบับที่อัปโหลด
🔹 **ขั้นตอนที่ 4 (Gate Decision):** คำนวณสรุปสถานะ Gate Result: PASSED, CONDITIONAL PASSED หรือ REJECTED`,
      icon: '✅',
      target: 'nav-exit-criteria',
      role: 'admin',
      color: '#ef4444',
    },
    {
      id: 'api_collection',
      title: '🔌 API Collections Manager',
      subtitle: 'เมนู: API Collections (Admin)',
      description: `📌 **หน้าที่ของเมนู**
บันทึก จัดหมวดหมู่ และทดสอบ API Endpoints สำหรับใช้รัน Automation Test และ Workflow

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (New Endpoint):** สร้าง API Request ระบุ HTTP Method (GET, POST, PUT, DELETE) และ URL
🔹 **ขั้นตอนที่ 2 (Headers & Body):** กำหนด Headers, Authorization Token และ Body Payload (JSON format)
🔹 **ขั้นตอนที่ 3 (Test Run):** กดปุ่มทดสอบส่ง Request เพื่อเช็ค Response Code และ Data Payload
🔹 **ขั้นตอนที่ 4 (Integration):** นำ API Collection ไปผูกกับ AI Workflow Builder หรือ Test Automation`,
      icon: '🔌',
      target: 'nav-api-col',
      role: 'admin',
      color: '#06b6d4',
    },
    {
      id: 'api_usage',
      title: '📊 Token Usage & Cost Analytics',
      subtitle: 'เมนู: Token Usage (Admin)',
      description: `📌 **หน้าที่ของเมนู**
ติดตามปริมาณการใช้งาน AI API ควบคุมงบประมาณ Token และวิเคราะห์ประสิทธิภาพระบบ

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Summary Dashboard):** ดูยอดรวม Total Tokens, Total API Calls และประเมินค่าใช้จ่ายรวม
🔹 **ขั้นตอนที่ 2 (Trend Graphs):** ดูกราฟแนวโน้มปริมาณการใช้งานรายวัน/รายเดือน แยกตามประเภทโมเดล AI
🔹 **ขั้นตอนที่ 3 (Logs Audit):** ตรวจสอบประวัติ Log การประมวลผลย้อนหลัง แยกตามโมดูลเพื่อประเมินความคุ้มค่า`,
      icon: '📊',
      target: 'nav-api-usage',
      role: 'admin',
      color: '#ec4899',
    },
    {
      id: 'master_agent',
      title: '🤖 Master Agent (Orchestrator)',
      subtitle: 'เมนู: Master Agent (Admin/User)',
      description: `📌 **หน้าที่ของเมนู**
ศูนย์กลางผู้ช่วย AI สั่งการและประสานงานระหว่าง QA Tools ทุกโมดูลผ่านแชทโต้ตอบอัจฉริยะ

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (User Input):** พิมพ์คำถาม/คำสั่งภาษาไทย หรือเลือกกดปุ่มคำสั่งด่วน (Quick Prompt Chips)
🔹 **ขั้นตอนที่ 2 (Orchestration):** Master Agent วิเคราะห์คำสั่ง แล้วเลือกเรียกใช้ Tool ที่เหมาะสม (Security, Performance, Consult, RAG)
🔹 **ขั้นตอนที่ 3 (AI Response):** สังเคราะห์คำตอบพร้อมจัดฟอร์แมต Markdown, บล็อกโค้ด และตารางวิเคราะห์
🔹 **ขั้นตอนที่ 4 (Interactive Tools):** กดปุ่ม Copy ข้อความตอบกลับ หรือกดล้างแชทเพื่อเริ่มหัวข้อใหม่`,
      icon: '🤖',
      target: 'nav-master-agent',
      role: 'admin',
      color: '#c084fc',
    },
    {
      id: 'workflow_builder',
      title: '🔗 AI Workflow Builder',
      subtitle: 'เมนู: AI Workflow Builder (Admin/User)',
      description: `📌 **หน้าที่ของเมนู**
ออกแบบ ออกแบบและรัน Multi-Agent Pipeline ด้วย Visual Node Diagram (Nodes & Edges)

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Drag & Drop):** เลือก Project แล้ววาง Node ประเภทต่าง ๆ (Input, Agent, Debate Loop, Output)
🔹 **ขั้นตอนที่ 2 (Connect Edges):** ลากเส้นเชื่อมต่อ Edges เพื่อกำหนดทิศทางการส่งต่อข้อมูลระหว่าง Agents
🔹 **ขั้นตอนที่ 3 (Node Config):** กำหนด Prompt, AI Model และ Timeout ของแต่ละ Node
🔹 **ขั้นตอนที่ 4 (Execution):** กดปุ่ม "Run Workflow" เพื่อประมวลผลตาม Graph พร้อมติดตาม Real-time Execution Logs`,
      icon: '🔗',
      target: 'nav-workflow',
      role: 'admin',
      color: '#34d399',
    },
    {
      id: 'mcp_integration_admin',
      title: '⚙️ Claude Desktop & MCP Integration',
      subtitle: 'การทำงานแบบ Fully Autonomous ผ่าน MCP Server',
      description: `📌 **หน้าที่ของเมนู**
เชื่อมต่อระบบ Spectra QA เข้ากับ Claude Desktop app ผ่านโปรโตคอล MCP (Model Context Protocol)

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Config File):** ตั้งค่าไฟล์ claude_desktop_config.json ให้เชื่อมต่อ MCP Server ของ Spectra QA
🔹 **ขั้นตอนที่ 2 (Tool Verification):** เปิด Claude Desktop สังเกตไอคอน 🔨 (Tools) สแกนพบเครื่องมือใน Spectra QA
🔹 **ขั้นตอนที่ 3 (Prompt Execution):** สั่งงาน Claude ภาษาธรรมชาติ เช่น "ช่วยตรวจ SRS และสร้าง Test Cases"
🔹 **ขั้นตอนที่ 4 (Auto Loop):** Claude จะหมุนเรียกใช้ MCP Tools ใน Spectra QA ประมวลผลแบบอัตโนมัติ`,
      icon: '⚙️',
      target: null,
      role: 'admin',
      color: '#f43f5e',
    },
    {
      id: 'admin_done',
      title: '🎉 พร้อมเริ่มต้นใช้งาน!',
      subtitle: 'Admin Mode — All Systems Operational',
      description: `📌 **สรุปขั้นตอนการทำงานที่แนะนำ (Recommended Admin Journey)**
🔹 **1. ตั้งค่า:** สร้าง Project ใน Project Management
🔹 **2. สแกน:** สแกนและตรวจเอกสารใน Scan OCR
🔹 **3. ค้นคว้า:** ตรวจสอบผล RAG ใน Knowledge Base
🔹 **4. ควบคุม:** ควบคุมคุณภาพเอกสารผ่าน Exit Criteria
🔹 **5. อัตโนมัติ:** ใช้ Master Agent และ Workflow Builder เพื่อสั่งงานอัตโนมัติ

🚀 ปิดหน้าต่างนี้เพื่อเริ่มใช้งานระบบได้ทันทีครับ!`,
      icon: '🎉',
      target: null,
      role: 'admin',
      color: '#10b981',
    },
  ];

  const userSteps = [
    {
      id: 'welcome_user',
      title: '👋 ยินดีต้อนรับสู่ Spectra QA Portal',
      subtitle: 'Intelligent QA & Testing Workspace (User Mode)',
      description: `📌 **ภาพรวมระบบ**
ศูนย์รวมเครื่องมือตรวจสอบและสร้างเอกสารคุณภาพซอฟต์แวร์สำหรับ QA, Tester และ Developer

🔄 **ลำดับ Flow การทำงานโดยรวม (User Workflow)**
🔹 **ขั้นตอนที่ 1 (เลือกเครื่องมือ):** เลือกเครื่องมือ QA ทางแถบซ้ายมือ (QA Consult, Security, Performance, Automation)
🔹 **ขั้นตอนที่ 2 (ป้อนข้อมูล):** อัปโหลดไฟล์ PDF, วางซอร์สโค้ด หรือป้อนรายละเอียด Requirement
🔹 **ขั้นตอนที่ 3 (AI ประมวลผล):** AI Evaluator สแกน วิเคราะห์ช่องโหว่ และประเมินคุณภาพอัตโนมัติ
🔹 **ขั้นตอนที่ 4 (รับรายงาน):** ตรวจสอบ Audit Report, ดูผล Pass/Fail และดาวน์โหลดรายงานส่งให้ทีม`,
      icon: '🚀',
      target: null,
      role: 'user',
      color: '#8b5cf6',
    },
    {
      id: 'qa_consult',
      title: '📋 QA Consult & SRS Review',
      subtitle: 'เมนู: QA Consult (User)',
      description: `📌 **หน้าที่ของเมนู**
วิเคราะห์เอกสารความต้องการระบบ (SRS / Requirements) ตรวจสอบกับเกณฑ์ Exit Criteria 13 ข้อ และตรวจคำผิด

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Select Group):** เลือก Project และสร้าง/เลือก Group สำหรับรอบการตรวจเอกสารนี้
🔹 **ขั้นตอนที่ 2 (Upload File):** ลากและวางไฟล์ PDF (ขนาดสูงสุด 50MB) ลงในระบบ
🔹 **ขั้นตอนที่ 3 (AI Audit):** AI รัน OCR, ตรวจคำผิด, วิเคราะห์ Gap Analysis และประเมิน Exit Criteria
🔹 **ขั้นตอนที่ 4 (Review & Export):** ดู Audit Report, สรุปสถานะ Gate Result และดาวน์โหลด Excel Report`,
      icon: '📋',
      target: 'nav-qa-consult',
      role: 'user',
      color: '#8b5cf6',
    },
    {
      id: 'qa_security',
      title: '🛡️ QA Security Audit',
      subtitle: 'เมนู: QA Security (User)',
      description: `📌 **หน้าที่ของเมนู**
สแกนตรวจสอบช่องโหว่ความปลอดภัยของ Source Code ด้วยมาตรฐานสากล (OWASP Top 10, ASVS, SANS 25)

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Input Code):** วางซอร์สโค้ดในกล่องข้อความ หรือ ระบุลิงก์ GitHub Repository URL
🔹 **ขั้นตอนที่ 2 (Select Standard):** เลือกภาษาโปรแกรม และ มาตรฐานความปลอดภัยที่ต้องการตรวจวัด
🔹 **ขั้นตอนที่ 3 (Security Scan):** กดปุ่ม "Scan Code Security" ให้ AI ตรวจวิเคราะห์ช่องโหว่และจุดเสี่ยง
🔹 **ขั้นตอนที่ 4 (Remediation Report):** ดูรายการช่องโหว่ ระดับ Severity และโค้ดตัวอย่างวิธีแก้ไขที่ถูกต้อง`,
      icon: '🛡️',
      target: 'nav-qa-security',
      role: 'user',
      color: '#f43f5e',
    },
    {
      id: 'qa_performance',
      title: '⚡ QA Performance Testing',
      subtitle: 'เมนู: QA Performance (User)',
      description: `📌 **หน้าที่ของเมนู**
วางแผนและรันสคริปต์ทดสอบค่าน้ำหนักโหลด (Load Testing / Performance Benchmark)

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Script & Config):** เลือกสคริปต์ k6 หรือระบุจำนวน Virtual Users (VUs) และ Duration
🔹 **ขั้นตอนที่ 2 (Test Execution):** กดรันการทดสอบ Performance Test ผ่านระบบ
🔹 **ขั้นตอนที่ 3 (Real-time Metrics):** ติดตามผลผ่านกราฟ Real-time (Response Time, Throughput, Error Rate)
🔹 **ขั้นตอนที่ 4 (SLA Benchmark):** AI เปรียบเทียบผลลัพธ์กับ SLA และออกรายงานสรุปจุดคอขวด (Bottleneck)`,
      icon: '⚡',
      target: 'nav-qa-perf',
      role: 'user',
      color: '#f59e0b',
    },
    {
      id: 'qa_research',
      title: '🔍 QA Research Agent',
      subtitle: 'เมนู: QA Research (User)',
      description: `📌 **หน้าที่ของเมนู**
สืบค้น ค้นคว้า และวิเคราะห์ข้อมูลทางเทคนิคและข้อกำหนดซอฟต์แวร์ด้วย AI Research Agent

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Query):** พิมพ์คำถาม ข้อสงสัย หรือหัวข้อเทคโนโลยีที่ต้องการศึกษาวิจัย
🔹 **ขั้นตอนที่ 2 (Deep Research):** AI Research Agent ค้นหาข้อมูล รวบรวมแนวคิด และเปรียบเทียบข้อดี-ข้อเสีย
🔹 **ขั้นตอนที่ 3 (Synthesis):** สังเคราะห์ออกมาเป็นรายงานบทความสรุปที่กระชับ อ้างอิงแหล่งข้อมูลชัดเจน
🔹 **ขั้นตอนที่ 4 (Export):** คัดลอกรายงานนำไปใช้ประกอบเอกสารสถาปัตยกรรมและแผนการทดสอบ`,
      icon: '🔍',
      target: 'nav-qa-research',
      role: 'user',
      color: '#06b6d4',
    },
    {
      id: 'qa_automate',
      title: '🤖 QA Test Automation',
      subtitle: 'เมนู: QA Test Automation (User)',
      description: `📌 **หน้าที่ของเมนู**
สร้างและรันสคริปต์ทดสอบระบบอัตโนมัติ (Playwright / Cypress)

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Scenario Input):** ระบุ URL เว็บไซต์ หรือ รายละเอียด Test Scenario ที่ต้องการทดสอบ
🔹 **ขั้นตอนที่ 2 (Framework Selection):** เลือก Framework ที่ต้องการ ( Playwright หรือ Cypress )
🔹 **ขั้นตอนที่ 3 (Code Generation):** AI เจนเนอเรตสคริปต์ทดสอบอัตโนมัติพร้อมโครงสร้าง Assertions
🔹 **ขั้นตอนที่ 4 (Test Run):** กดทดสอบรันสคริปต์เพื่อตรวจสอบ Pass/Fail และดู Execution Output`,
      icon: '🤖',
      target: 'nav-qa-automate',
      role: 'user',
      color: '#10b981',
    },
    {
      id: 'qa_doc_creation',
      title: '📑 QA Document Creation',
      subtitle: 'เมนู: QA Document Creation (User)',
      description: `📌 **หน้าที่ของเมนู**
สร้างเอกสารมาตรฐานงาน QA อัตโนมัติ (Test Plan, Test Cases, UAT Acceptance, Summary Report)

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Doc Type):** เลือกประเภทเอกสารที่ต้องการสร้างจากเมนู
🔹 **ขั้นตอนที่ 2 (Project Context):** กรอกรายละเอียดโครงการ ขอบเขตฟีเจอร์ และข้อมูลประกอบ
🔹 **ขั้นตอนที่ 3 (AI Drafting):** AI ร่างเนื้อหาเอกสารตามโครงสร้างมาตรฐานอุตสาหกรรม
🔹 **ขั้นตอนที่ 4 (Export):** ตรวจสอบ ปรับแต่งเนื้อหา และดาวน์โหลดหรือคัดลอกเอกสารนำไปใช้งาน`,
      icon: '📑',
      target: 'nav-qa-doc',
      role: 'user',
      color: '#3b82f6',
    },
    {
      id: 'master_agent',
      title: '🤖 Master Agent (Orchestrator)',
      subtitle: 'เมนู: Master Agent (User)',
      description: `📌 **หน้าที่ของเมนู**
ศูนย์รวมผู้ช่วย AI สนทนาโต้ตอบและสั่งงานครอบคลุมทุกเครื่องมือ QA ในอินเทอร์เฟซเดียว

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Command Input):** พิมพ์คำถามภาษาไทย หรือคลิกเลือก Quick Prompt ด้านล่างช่องป้อนข้อความ
🔹 **ขั้นตอนที่ 2 (Tool Integration):** Master Agent ประสานงานระหว่าง Security, Performance, RAG, Consult
🔹 **ขั้นตอนที่ 3 (Markdown Output):** รับข้อความตอบกลับในรูปแบบ Markdown, Code Blocks และตารางวิเคราะห์
🔹 **ขั้นตอนที่ 4 (Copy/Reset):** กดคัดลอกข้อความคำตอบไปใช้งาน หรือ ล้างแชทเพื่อเปิดหัวข้อใหม่`,
      icon: '🤖',
      target: 'nav-master-agent',
      role: 'user',
      color: '#c084fc',
    },
    {
      id: 'workflow_builder',
      title: '🔗 AI Workflow Builder',
      subtitle: 'เมนู: AI Workflow Builder (User)',
      description: `📌 **หน้าที่ของเมนู**
รันและติดตามผลการทำงานของ AI Workflow Graph แบบ Multi-Agent

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Select Workflow):** เลือก Workflow Pipeline ของโครงการที่ต้องการทดสอบรัน
🔹 **ขั้นตอนที่ 2 (Provide Input):** ป้อนข้อมูลนำเข้า (Requirement / Data Context)
🔹 **ขั้นตอนที่ 3 (Track Execution):** ติดตามการทำงานของแต่ละ Node ใน Diagram แบบ Real-time
🔹 **ขั้นตอนที่ 4 (Final Result):** ตรวจสอบและรับผลลัพธ์การวิเคราะห์ขั้นสุดท้ายจาก Pipeline`,
      icon: '🔗',
      target: 'nav-workflow',
      role: 'user',
      color: '#34d399',
    },
    {
      id: 'mcp_integration_user',
      title: '⚙️ Claude Desktop Integration',
      subtitle: 'การสั่งงาน Spectra QA ผ่าน Claude Desktop app',
      description: `📌 **หน้าที่ของเมนู**
ใช้งานร่วมกับ Claude Desktop บนคอมพิวเตอร์เพื่อรันเครื่องมือใน Spectra QA อัตโนมัติ

🔄 **ลำดับ Flow การทำงาน (Step-by-Step Workflow)**
🔹 **ขั้นตอนที่ 1 (Verify Tools):** เปิด Claude Desktop สังเกตไอคอน 🔨 ขึ้นรายการ Spectra QA Tools
🔹 **ขั้นตอนที่ 2 (Natural Prompt):** พิมพ์สั่งงานปกติ เช่น "ช่วยตรวจ Security โค้ดนี้แล้วสร้าง Test Cases"
🔹 **ขั้นตอนที่ 3 (Automatic Execution):** Claude เรียกใช้ MCP Tools ใน Spectra QA ประมวลผลจนเสร็จ
🔹 **ขั้นตอนที่ 4 (Done):** รับผลลัพธ์รายงานสมบูรณ์ผ่าน Claude โดยไม่ต้องสลับหน้าจอ`,
      icon: '⚙️',
      target: null,
      role: 'user',
      color: '#f43f5e',
    },
    {
      id: 'user_done',
      title: '🎉 พร้อมเริ่มต้นใช้งาน!',
      subtitle: 'User Portal — Ready to Test',
      description: `📌 **สรุปขั้นตอนง่ายๆ ในการใช้งาน (Quick User Journey)**
🔹 **1. QA Consult:** ใช้สำหรับตรวจ SRS/Requirement
🔹 **2. QA Security:** ใช้สำหรับสแกนช่องโหว่โค้ด
🔹 **3. QA Performance:** ใช้สำหรับทดสอบ Load Test
🔹 **4. Master Agent:** ใช้สำหรับสอบถามและสั่งงานรวมทุก Tools

🚀 เลือกเมนูที่ต้องการทางแถบซ้ายมือเพื่อเริ่มใช้งานได้เลยครับ!`,
      icon: '🎉',
      target: null,
      role: 'user',
      color: '#10b981',
    },
  ];

  $: steps = userRole === 'admin' ? adminSteps : userSteps;
  let currentStep = 0;
  $: step = steps[currentStep];
  $: isFirst = currentStep === 0;
  $: isLast = currentStep === steps.length - 1;
  $: progress = ((currentStep + 1) / steps.length) * 100;

  function next() {
    if (!isLast) currentStep++;
  }
  function prev() {
    if (!isFirst) currentStep--;
  }
  function close() {
    dispatch('close');
  }

  function formatDescription(text) {
    if (!text) return '';

    // Split text by lines and parse structured blocks
    const lines = text.split('\n');
    let outputHtml = '';

    for (let line of lines) {
      let trimmed = line.trim();
      if (!trimmed) continue;

      if (trimmed.startsWith('📌')) {
        let titleText = trimmed.replace(/^📌\s*/, '').replace(/\*\*/g, '');
        outputHtml += `<div class="overview-badge-box"><span class="badge-icon">📌</span><span class="badge-title">${titleText}</span></div>`;
      } else if (trimmed.startsWith('🔄')) {
        let titleText = trimmed.replace(/^🔄\s*/, '').replace(/\*\*/g, '');
        outputHtml += `<div class="workflow-badge-box"><span class="badge-icon">🔄</span><span class="badge-title">${titleText}</span></div>`;
      } else if (trimmed.startsWith('🔹')) {
        // Step line format: 🔹 **ขั้นตอนที่ 1 (Title):** Details
        let content = trimmed.replace(/^🔹\s*/, '');
        let stepMatch = content.match(/\*\*(.*?)\*\*\s*(.*)/);
        if (stepMatch) {
          let stepHeader = stepMatch[1];
          let stepDesc = stepMatch[2];
          outputHtml += `
            <div class="flow-step-card">
              <div class="step-card-header">
                <span class="step-bullet-icon">🔹</span>
                <span class="step-title-text">${stepHeader}</span>
              </div>
              ${stepDesc ? `<div class="step-card-desc">${stepDesc}</div>` : ''}
            </div>
          `;
        } else {
          outputHtml += `<div class="flow-step-card"><div class="step-card-desc">${content}</div></div>`;
        }
      } else {
        let formattedLine = trimmed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        outputHtml += `<p class="normal-desc-para">${formattedLine}</p>`;
      }
    }

    return outputHtml;
  }

  function handleKeydown(e) {
    if (e.key === 'ArrowRight' || e.key === 'Enter') next();
    else if (e.key === 'ArrowLeft') prev();
    else if (e.key === 'Escape') close();
  }

  onMount(() => window.addEventListener('keydown', handleKeydown));
  onDestroy(() => window.removeEventListener('keydown', handleKeydown));
</script>

<!-- ── Backdrop ── -->
<div
  class="tutorial-backdrop"
  role="dialog"
  aria-modal="true"
  aria-label="Tutorial"
  transition:fade={{ duration: 250 }}
  on:click|self={close}
>

  <!-- ── Large Premium Tutorial Card ── -->
  <div
    class="tutorial-card glass-panel"
    in:fly={{ y: 40, duration: 300 }}
    style="--step-color: {step.color};"
  >
    <!-- Header: icon + custom step dropdown + close -->
    <div class="tc-header">
      <div class="tc-badge" style="background: color-mix(in srgb, {step.color} 20%, transparent); border-color: color-mix(in srgb, {step.color} 45%, transparent);">
        {#key currentStep}
          <span class="tc-icon" in:fade={{ duration: 200 }}>{step.icon}</span>
        {/key}
      </div>

      <!-- Custom Glass Dropdown (Replaces raw HTML select) -->
      <div class="custom-step-dropdown-container">
        <button 
          class="custom-dropdown-btn" 
          on:click={() => (showStepDropdown = !showStepDropdown)}
          title="เลือกคู่มือเมนูที่ต้องการ"
        >
          <span class="cd-num">{currentStep + 1}.</span>
          <span class="cd-text">{step.title.replace(/^[^\s]+\s+/, '')}</span>
          <svg class="cd-chevron" class:open={showStepDropdown} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>

        {#if showStepDropdown}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <div class="dropdown-overlay-bg" on:click={() => (showStepDropdown = false)}></div>
          <div class="custom-dropdown-menu" transition:fly={{ y: -8, duration: 200 }}>
            {#each steps as s, idx}
              <button
                class="dropdown-menu-item"
                class:active={idx === currentStep}
                on:click={() => { currentStep = idx; showStepDropdown = false; }}
              >
                <span class="item-icon">{s.icon}</span>
                <span class="item-idx">{idx + 1}.</span>
                <span class="item-name">{s.title.replace(/^[^\s]+\s+/, '')}</span>
                {#if idx === currentStep}
                  <span class="item-active-check">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  </span>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <button class="tc-close" on:click={close} title="ปิด (Esc)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="18" height="18">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <!-- Role Tag -->
    <div class="tc-role-tag">
      <span class="role-dot" style="background: {step.color}; shadow: 0 0 8px {step.color};"></span>
      {userRole === 'admin' ? '🛡 System Admin Mode' : '👤 Standard User Mode'} — ขั้นตอนที่ {currentStep + 1} จาก {steps.length}
    </div>

    <!-- Content area (large & scrollable) -->
    {#key currentStep}
      <div class="tc-content" in:fade={{ duration: 180, delay: 60 }}>
        <h2 class="tc-title">{step.title}</h2>
        <p class="tc-subtitle">{step.subtitle}</p>
        <div class="tc-divider"></div>
        <div class="tc-body">
          {@html formatDescription(step.description)}
        </div>
      </div>
    {/key}

    <!-- Progress Bar -->
    <div class="tc-progress-wrap">
      <div class="tc-progress-bar">
        <div class="tc-progress-fill" style="width: {progress}%; background: {step.color}; box-shadow: 0 0 12px {step.color};"></div>
      </div>
      <span class="tc-progress-label" style="color: {step.color};">{Math.round(progress)}%</span>
    </div>

    <!-- Step Dots -->
    <div class="tc-dots">
      {#each steps as _, i}
        <button
          class="tc-dot"
          class:active={i === currentStep}
          style={i === currentStep ? `background: ${step.color}; box-shadow: 0 0 10px ${step.color}; width: 26px;` : ''}
          on:click={() => (currentStep = i)}
          aria-label="Step {i + 1}"
        ></button>
      {/each}
    </div>

    <!-- Actions -->
    <div class="tc-actions">
      {#if !isFirst}
        <button class="tc-btn tc-btn-secondary" on:click={prev}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="15 18 9 12 15 6"/>
          </svg>
          ก่อนหน้า
        </button>
      {:else}
        <div></div>
      {/if}

      {#if isLast}
        <button class="tc-btn tc-btn-primary" style="background: linear-gradient(135deg, #10b981, #059669);" on:click={close}>
          🎉 เริ่มใช้งาน!
        </button>
      {:else}
        <button class="tc-btn tc-btn-primary" style="background: linear-gradient(135deg, {step.color}, #4f46e5);" on:click={next}>
          ถัดไป
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      {/if}
    </div>

    <!-- Keyboard hint -->
    <p class="tc-hint">← → นำทาง &nbsp;|&nbsp; Esc ปิด</p>
  </div>
</div>

<style>
  .tutorial-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(4, 6, 14, 0.85);
    backdrop-filter: blur(12px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  /* Premium Large Modal Card */
  .tutorial-card {
    background: linear-gradient(145deg, rgba(16, 18, 30, 0.95), rgba(24, 27, 44, 0.95));
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-top: 4px solid var(--step-color, #6366f1);
    border-radius: 24px;
    padding: 32px 38px;
    width: 100%;
    max-width: 820px;
    max-height: 86vh;
    display: flex;
    flex-direction: column;
    box-shadow:
      0 32px 90px rgba(0,0,0,0.75),
      0 0 30px color-mix(in srgb, var(--step-color, #6366f1) 20%, transparent);
    position: relative;
    overflow: visible;
  }

  /* Header */
  .tc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 14px;
    position: relative;
    z-index: 10;
  }

  .tc-badge {
    width: 50px; height: 50px;
    border-radius: 16px;
    border: 1px solid;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
    transition: all 0.4s ease;
  }
  .tc-icon { font-size: 26px; line-height: 1; display: block; }

  /* Custom Glass Dropdown */
  .custom-step-dropdown-container {
    flex: 1;
    min-width: 0;
    position: relative;
  }

  .custom-dropdown-btn {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    border-radius: 14px;
    background: rgba(10, 12, 22, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #f1f5f9;
    font-family: var(--font-th);
    font-size: 13.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s ease;
  }

  .custom-dropdown-btn:hover {
    background: rgba(24, 28, 48, 0.9);
    border-color: rgba(168, 85, 247, 0.4);
    box-shadow: 0 4px 16px rgba(168, 85, 247, 0.15);
  }

  .cd-num {
    color: var(--step-color, #a855f7);
    font-weight: 700;
  }

  .cd-text {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: left;
  }

  .cd-chevron {
    color: var(--text-muted);
    transition: transform 0.3s ease;
    flex-shrink: 0;
  }
  .cd-chevron.open {
    transform: rotate(180deg);
    color: var(--secondary);
  }

  .dropdown-overlay-bg {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 90;
  }

  .custom-dropdown-menu {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    margin-top: 6px;
    max-height: 280px;
    overflow-y: auto;
    background: rgba(15, 18, 30, 0.96);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: 16px;
    padding: 8px;
    z-index: 100;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6);
  }

  .dropdown-menu-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-radius: 10px;
    background: transparent;
    border: none;
    color: #cbd5e1;
    font-family: var(--font-th);
    font-size: 13px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
  }

  .dropdown-menu-item:hover {
    background: rgba(168, 85, 247, 0.15);
    color: #ffffff;
  }

  .dropdown-menu-item.active {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(168, 85, 247, 0.3));
    color: #ffffff;
    font-weight: 600;
    border: 1px solid rgba(168, 85, 247, 0.3);
  }

  .item-icon { font-size: 16px; }
  .item-idx { font-weight: 700; color: #a855f7; font-size: 12px; }
  .item-name { flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .item-active-check { color: #34d399; display: flex; align-items: center; }

  .tc-close {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    color: rgba(255,255,255,0.6);
    border-radius: 50%;
    width: 38px; height: 38px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.2s;
  }
  .tc-close:hover {
    background: rgba(244, 63, 94, 0.2);
    border-color: rgba(244, 63, 94, 0.4);
    color: #f43f5e;
    transform: rotate(90deg);
  }

  /* Role tag */
  .tc-role-tag {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding: 5px 14px;
    border-radius: 20px;
    border: 1px solid color-mix(in srgb, var(--step-color, #6366f1) 35%, transparent);
    background: color-mix(in srgb, var(--step-color, #6366f1) 14%, transparent);
    color: var(--step-color, #6366f1);
    margin-bottom: 16px;
    font-family: var(--font-en);
    align-self: flex-start;
  }

  .role-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
  }

  /* Scrollable Content Area */
  .tc-content {
    flex: 1;
    min-height: 280px;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding-right: 8px;
  }

  .tc-title {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    margin: 0 0 4px 0;
    line-height: 1.3;
    font-family: var(--font-th);
  }

  .tc-subtitle {
    font-size: 13px;
    color: var(--step-color, #a78bfa);
    margin: 0 0 16px 0;
    font-weight: 500;
    font-family: var(--font-en);
  }

  .tc-divider {
    height: 1px;
    background: linear-gradient(90deg, color-mix(in srgb, var(--step-color, #6366f1) 50%, transparent), transparent);
    margin-bottom: 16px;
  }

  /* Formatted Body Content Styles */
  .tc-body {
    font-size: 14px;
    line-height: 1.8;
    color: #cbd5e1;
    font-family: var(--font-th);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  :global(.tc-body .overview-badge-box) {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.25);
    padding: 8px 14px;
    border-radius: 12px;
    font-weight: 700;
    color: #e0e7ff;
    margin-bottom: 4px;
  }

  :global(.tc-body .workflow-badge-box) {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(168, 85, 247, 0.12);
    border: 1px solid rgba(168, 85, 247, 0.25);
    padding: 8px 14px;
    border-radius: 12px;
    font-weight: 700;
    color: #f3e8ff;
    margin-top: 8px;
    margin-bottom: 4px;
  }

  :global(.tc-body .flow-step-card) {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-left: 3px solid var(--step-color, #6366f1);
    padding: 10px 14px;
    border-radius: 12px;
    transition: all 0.2s ease;
  }

  :global(.tc-body .flow-step-card:hover) {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.15);
    transform: translateX(4px);
  }

  :global(.tc-body .step-card-header) {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13.5px;
    font-weight: 700;
    color: #f8fafc;
  }

  :global(.tc-body .step-bullet-icon) {
    color: var(--step-color, #a855f7);
  }

  :global(.tc-body .step-card-desc) {
    font-size: 13px;
    color: #cbd5e1;
    margin-top: 2px;
    line-height: 1.6;
  }

  :global(.tc-body .normal-desc-para) {
    margin: 4px 0;
  }

  /* Progress wrap */
  .tc-progress-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 18px;
    margin-bottom: 12px;
  }

  .tc-progress-bar {
    flex: 1;
    height: 6px;
    background: rgba(255,255,255,0.08);
    border-radius: 6px;
    overflow: hidden;
  }

  .tc-progress-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.3s ease;
  }

  .tc-progress-label {
    font-size: 12px;
    font-weight: 700;
    font-family: 'Inter', sans-serif;
    min-width: 34px;
    text-align: right;
  }

  /* Step Dots */
  .tc-dots {
    display: flex;
    justify-content: center;
    gap: 6px;
    margin-bottom: 18px;
    flex-wrap: wrap;
  }

  .tc-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    border: none;
    cursor: pointer;
    padding: 0;
    transition: all 0.25s ease;
  }

  /* Actions */
  .tc-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }

  .tc-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 14px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s ease;
    font-family: var(--font-th);
    border: none;
  }

  .tc-btn-secondary {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    color: #e2e8f0;
  }
  .tc-btn-secondary:hover {
    background: rgba(255,255,255,0.14);
    color: #fff;
  }

  .tc-btn-primary {
    color: #ffffff;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4);
    transition: all 0.25s ease;
  }
  .tc-btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  }

  .tc-hint {
    text-align: center;
    font-size: 11px;
    color: rgba(255,255,255,0.35);
    margin: 12px 0 0 0;
    font-family: 'Inter', sans-serif;
  }
</style>
