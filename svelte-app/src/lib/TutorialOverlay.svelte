<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';

  export let userRole = 'admin'; // 'admin' | 'user'

  const dispatch = createEventDispatcher();
  let showMobileMenu = false;
  let direction = 1; // 1 = forward, -1 = backward

  // ── Detailed, Up-to-Date Tutorial Curriculum ─────────────────────────────
  const adminSteps = [
    {
      id: 'welcome',
      category: 'ภาพรวมระบบ',
      iconType: 'compass',
      title: 'ยินดีต้อนรับสู่ Spectra QA Platform',
      subtitle: 'Unified AI QA Automation & Document Verification (Admin Mode)',
      color: '#6366f1',
      overview:
        'Spectra QA คือแพลตฟอร์มประกันคุณภาพซอฟต์แวร์แบบครบวงจรที่ผสาน Multi-Agent AI, การสแกน OCR ภาษาไทย-อังกฤษ, ฐานความรู้ RAG, การสร้างและตรวจเอกสารด้วย Exit Criteria Gate, การทดสอบ API/Security/Performance และ Playwright MCP Automation ไว้ในโครงการเดียว',
      flow: ['Project Setup', 'Knowledge Base', 'Doc Creation', 'QA Consult Gate', 'Test Automation'],
      steps: [
        {
          title: 'ตั้งค่าโครงการและสิทธิ์ทีมงาน',
          detail: 'สร้างโครงการใน Project Management เพื่อแยกคลังเอกสาร, Requirement และประวัติการตรวจออกจากกัน 100% แล้วกำหนดสิทธิ์สมาชิกใน QA Member'
        },
        {
          title: 'นำเข้าเอกสารต้นทางเข้าสู่ Knowledge Base',
          detail: 'อัปโหลด SRS, TOR, SDD หรือสแกน PDF ผ่าน Scan OCR ระบบจะสกัดข้อความ, แบ่ง Chunk, สร้าง Vector Embedding และระบุ Golden Data'
        },
        {
          title: 'กำหนดมาตรฐานด้วย AI Skills & Exit Criteria',
          detail: 'ตั้งค่า Template หัวข้อเอกสารใน AI Skills และกำหนดเกณฑ์ผ่าน/ไม่ผ่าน (Mandatory / KPI) ใน Exit Criteria เพื่อคุมคุณภาพทุกเอกสาร'
        },
        {
          title: 'ผลิต-ตรวจ-ปรับปรุงเอกสารแบบ Closed-Loop',
          detail: 'สร้างเอกสารจาก QA Document Creation → ส่งตรวจที่ QA Consult → ส่งข้อบกพร่องกลับมาผ่าตัดแก้ไขอัตโนมัติจนผ่านเกณฑ์ 100%'
        },
        {
          title: 'ขยายสู่ Automation, Security, Performance & MCP',
          detail: 'ต่อยอด Requirement ไปยัง QA Test Automation (Playwright MCP), QA Security, QA Performance, AI Workflow Builder และ Master Agent'
        }
      ],
      tip: 'เริ่มจากการอัปโหลด SRS หรือ TOR ของโครงการและติ๊กเป็น Golden Data ใน Knowledge Base ก่อนเสมอ เพื่อให้ AI ทุกเมนูอ้างอิงขอบเขตงานได้อย่างแม่นยำสูงสุด'
    },
    {
      id: 'project_management',
      category: 'ตั้งค่าพื้นฐาน',
      iconType: 'folder',
      title: 'Project Management',
      subtitle: 'ศูนย์กลางจัดการโครงการและขอบเขตข้อมูล (Project Isolation)',
      color: '#6366f1',
      overview:
        'สร้างและบริหารโครงการทั้งหมดในระบบ ทุกเมนูใน Spectra QA จะยึดขอบเขตข้อมูลตามโครงการที่เลือก (Strict Project Isolation) เพื่อป้องกันข้อมูลข้ามโครงการปะปนกัน',
      flow: ['สร้าง Project Code', 'ระบุขอบเขต', 'ผูกสมาชิก', 'เชื่อมทุกเมนู QA'],
      steps: [
        {
          title: 'สร้างโครงการใหม่ (+ New Project)',
          detail: 'กำหนด Project Code (เช่น 69A, WMS-01), ชื่อโครงการ และคำอธิบายขอบเขตระบบให้ชัดเจน'
        },
        {
          title: 'ตรวจสอบความพร้อมของคลังข้อมูลโครงการ',
          detail: 'ดูภาพรวมจำนวนเอกสารใน Knowledge Base, ประวัติการสแกน และสถานะการใช้งานของแต่ละโครงการได้จากหน้าเดียว'
        },
        {
          title: 'ผูกสิทธิ์การเข้าถึงตามทีม',
          detail: 'กำหนดให้ QA หรือ BA แต่ละคนเห็นเฉพาะโครงการที่รับผิดชอบผ่านเมนู QA Member'
        }
      ],
      tip: 'ตั้ง Project Code ให้สั้นและสื่อความหมาย (เช่น PRJ-2026) เพราะรหัสนี้จะถูกนำไปแสดงบนหัวรายงาน PDF, ไฟล์ Excel และชื่อกลุ่มสแกนอัตโนมัติ'
    },
    {
      id: 'scan_ocr',
      category: 'นำเข้าข้อมูล',
      iconType: 'scan',
      title: 'Scan OCR & Bilingual Spell Check',
      subtitle: 'สแกนเอกสาร PDF ภาษาไทย-อังกฤษ พร้อมตรวจคำผิดด้วยพจนานุกรมเฉพาะทาง',
      color: '#818cf8',
      overview:
        'แปลงเอกสาร PDF สแกนหรือรูปภาพเป็นข้อความ Markdown โครงสร้างชัดเจน ตรวจคำผิดภาษาไทย-อังกฤษตามบริบท และนำเข้าฐานข้อมูลโครงการได้ทันที',
      flow: ['อัปโหลด PDF (<=50MB)', 'OCR Extraction', 'ตรวจคำผิด TH/EN', 'Export / บันทึก KB'],
      steps: [
        {
          title: 'อัปโหลดเอกสารต้นฉบับ',
          detail: 'ลากไฟล์ PDF (ขนาดสูงสุด 50MB) ลงในพื้นที่อัปโหลด เลือกโครงการเป้าหมายและโหมดการประมวลผล'
        },
        {
          title: 'ตรวจสอบผล OCR และรายการคำผิด',
          detail: 'ระบบจะแสดงข้อความที่สกัดได้คู่กับรายการคำผิดที่ตรวจพบ พร้อมคำแนะนำคำที่ถูกต้องและพจนานุกรมคำศัพท์เฉพาะทางขององค์กร'
        },
        {
          title: 'ส่งออกหรือนำเข้าสู่ Knowledge Base',
          detail: 'สามารถคัดลอก Markdown, ส่งออกรายงาน หรือจัดเก็บเข้าสู่ Knowledge Base ของโครงการเพื่อใช้เป็นแหล่งอ้างอิงให้ AI Agent ทันที'
        }
      ],
      tip: 'หากเอกสารมีคำศัพท์เฉพาะของธุรกิจ (เช่น ชื่อย่อระบบ) สามารถเพิ่มลงใน Custom Dictionary เพื่อให้ระบบไม่แจ้งเตือนเป็นคำผิดซ้ำ'
    },
    {
      id: 'knowledge_base',
      category: 'นำเข้าข้อมูล',
      iconType: 'database',
      title: 'Knowledge Base & Golden Data',
      subtitle: 'คลังข้อมูล RAG และระบบสืบค้นเชิงความหมาย (Vector Database)',
      color: '#8b5cf6',
      overview:
        'หัวใจสำคัญของความแม่นยำใน Spectra QA จัดเก็บเอกสารทั้งหมดของโครงการ (TOR, SRS, SDD, Test Case, คู่มือ) ในรูปแบบ Vector Chunks และ Structured Requirements',
      flow: ['อัปโหลดเอกสาร', 'แบ่ง Chunks & Vector', 'ตั้งค่า Golden Data', 'AI ทุกเมนูดึงใช้อัตโนมัติ'],
      steps: [
        {
          title: 'จัดหมวดหมู่เอกสารให้ถูกต้อง',
          detail: 'เลือกหมวดหมู่ให้ตรงกับเนื้อหา (SRS, Requirement, TOR/SOW, SDD, TestCase, User Manual) เพื่อให้ Multi-Source RAG ค้นหาได้แม่นยำ'
        },
        {
          title: 'กำหนด Golden Data สำหรับเอกสารหลัก',
          detail: 'เปิดสถานะ Golden Data ให้กับเอกสารฉบับอนุมัติ (Baseline) เพื่อให้ QA Consult และ QA Document Creation ยึดเป็นเกณฑ์อ้างอิงอันดับแรก'
        },
        {
          title: 'ทดสอบค้นหาเชิงความหมาย (Semantic Search)',
          detail: 'พิมพ์คำถามหรือฟังก์ชันที่ต้องการค้นหา ระบบจะดึง Chunk ที่เกี่ยวข้องมากที่สุดพร้อมเลขหน้าและชื่อไฟล์ต้นฉบับมาแสดงทันที'
        }
      ],
      tip: 'เมื่อมีการอัปเดต SRS เวอร์ชันใหม่ ควรอัปโหลดฉบับล่าสุดและปรับสถานะฉบับเก่าออก เพื่อไม่ให้ AI สับสนระหว่างข้อกำหนดเก่าและใหม่'
    },
    {
      id: 'ai_skills',
      category: 'มาตรฐาน AI',
      iconType: 'sparkles',
      title: 'AI Skills & Template Manager',
      subtitle: 'กำหนดโครงสร้างหัวข้อ, ตาราง และกฎการวิเคราะห์เฉพาะทางของ AI',
      color: '#a855f7',
      overview:
        'สร้างชุดคำสั่ง (Skill.md) สำหรับควบคุมรูปแบบเอกสารและเกณฑ์การวิเคราะห์ เช่น Template การเขียน SRS, โครงสร้างคอลัมน์ Test Case หรือแนวทางการตรวจเอกสารเฉพาะทาง',
      flow: ['สร้าง/เลือก Skill', 'ระบุ Target Doc Type', 'เขียน Markdown Template', 'เลือกใช้ได้ตามต้องการ'],
      steps: [
        {
          title: 'สร้าง Skill ใหม่และระบุประเภทเอกสารเป้าหมาย',
          detail: 'ตั้งชื่อ Skill ให้ชัดเจน (เช่น Create SRS Standard, Audit Test Case) และผูกกับ Target Doc Type หรือตั้งเป็น ALL'
        },
        {
          title: 'กำหนดหัวข้อและระดับรายละเอียด (Template Blueprint)',
          detail: 'เขียนโครงสร้างหัวข้อ, คอลัมน์ตาราง และข้อกำหนดที่ต้องการด้วย Markdown ยิ่งระบุโครงสร้างชัดเจน AI ยิ่งสร้างเอกสารได้ตรงใจ'
        },
        {
          title: 'ใช้งานแบบเลือกหรือไม่เลือกก็ได้ (Optional)',
          detail: 'ในเมนู QA Document Creation และ QA Consult ผู้ใช้สามารถเลือก Skill เพื่อคุม Template หรือเว้นว่างเพื่อใช้มาตรฐานสากลอัตโนมัติ'
        }
      ],
      tip: 'แยก Skill สำหรับ "สร้างเอกสาร (Create)" ออกจาก Skill สำหรับ "ตรวจเอกสาร (Audit)" เพื่อให้โครงสร้างไม่ตีกันเมื่อใช้งานจริง'
    },
    {
      id: 'exit_criteria',
      category: 'มาตรฐาน AI',
      iconType: 'shield',
      title: 'Exit Criteria Review Gate',
      subtitle: 'กำหนดเกณฑ์ตรวจรับเอกสาร (Quality Gate) ทั้งเกณฑ์กลางและเฉพาะประเภท',
      color: '#ec4899',
      overview:
        'ควบคุมมาตรฐานก่อนส่งมอบเอกสารทุกฉบับด้วย Checklist แยกหมวดหมู่ (Defect & Bug, Content Completeness, Formatting, Governance) พร้อมระดับความรุนแรงและเกณฑ์บังคับ (Mandatory)',
      flow: ['ตั้ง Template (ALL + Specific)', 'กำหนด KPI & Mandatory', 'ตรวจอัตโนมัติใน QA Consult', 'ตัดสิน PASSED / REJECTED'],
      steps: [
        {
          title: 'แยกเกณฑ์กลาง (ALL) และเกณฑ์เฉพาะประเภทเอกสาร',
          detail: 'สร้าง Template กลางสำหรับทุกเอกสาร และสร้าง Template เฉพาะเช่น SRS หรือ Test Case ระบบจะนำมาประเมินร่วมกันอัตโนมัติ'
        },
        {
          title: 'กำหนด KPI, Severity และ Mandatory ให้ชัดเจน',
          detail: 'ระบุว่าข้อใดเป็น Critical/Mandatory (หากไม่ผ่านจะได้ REJECTED) และข้อใดเป็น Minor/Formatting (หากไม่ผ่านเฉพาะหมวดจัดหน้าจะได้ CONDITIONAL_PASSED)'
        },
        {
          title: 'เชื่อมตรงกับ QA Document Creation และ QA Consult',
          detail: 'เกณฑ์ที่เปิดใช้งาน (Active) จะถูกส่งเข้าไปเป็นกรอบให้ AI ตอนสร้างเอกสารด้วย ทำให้เอกสารที่สร้างขึ้นผ่านเกณฑ์ได้ตั้งแต่รอบแรก'
        }
      ],
      tip: 'หากมีการปรับแก้ข้อตรวจใน Exit Criteria สามารถกลับไปกดปุ่ม "ประเมินเกณฑ์ใหม่" ในเมนู QA Consult ได้ทันทีโดยไม่ต้องอัปโหลดไฟล์ซ้ำ'
    },
    {
      id: 'qa_doc_and_consult',
      category: 'วงจรคุณภาพเอกสาร',
      iconType: 'workflow',
      title: 'QA Document Creation ↔ QA Consult',
      subtitle: 'วงจรสร้าง ตรวจ และผ่าตัดแก้ไขเอกสารอัตโนมัติ (Closed-Loop Quality)',
      color: '#6366f1',
      overview:
        'การทำงานร่วมกันแบบไร้รอยต่อระหว่างการสร้างเอกสารจากคลังทุกเมนู และการส่งตรวจเทียบกับ Baseline + Exit Criteria จนกว่าเอกสารจะผ่านเกณฑ์สมบูรณ์',
      flow: ['สร้างเอกสาร (Auto Context)', 'ส่งตรวจ QA (1 คลิก)', 'รับผล Gate & Findings', 'Auto Refine (_v2) จนผ่าน'],
      steps: [
        {
          title: 'สร้างเอกสารใน QA Document Creation',
          detail: 'ระบุชื่อและประเภทเอกสาร ระบบจะดึง Knowledge Base, Structured Requirements, System Diagram และ Exit Criteria ของโครงการมาสังเคราะห์อัตโนมัติ (เลือก AI Skill เพิ่มเติมได้)'
        },
        {
          title: 'ส่งตรวจ QA Consult ในคลิกเดียว',
          detail: 'กดปุ่ม "ส่งตรวจ QA" จากตารางประวัติ ระบบจะแนบไฟล์ (.xlsx สำหรับ Test Case / .pdf สำหรับเอกสารอื่น) ข้ามไป QA Consult พร้อมอัปเดตสถานะอัตโนมัติ'
        },
        {
          title: 'ตรวจสอบผล QA Findings และ Exit Criteria Gate',
          detail: 'ดูรายการข้อบกพร่อง, คะแนน Gate, ดาวน์โหลด Excel Report หรือกด "ประเมินเกณฑ์ใหม่" หลังปรับ Template'
        },
        {
          title: 'ส่งแก้ไขกลับอัตโนมัติ (Auto Refine)',
          detail: 'หากพบข้อบกพร่อง กด "ส่งแก้ไขใน QA Doc Creation" ระบบจะล็อกรายการที่ต้องแก้ไว้ใน Refinement Banner และรันเวอร์ชัน _v2 เพื่อให้ AI ผ่าตัดแก้ตรงจุด'
        }
      ],
      tip: 'เมื่อเอกสารผ่านสถานะ PASSED ใน QA Consult แล้ว กด "บันทึกเข้า KB" ในหน้าประวัติเพื่อยกระดับเป็นเอกสารอ้างอิงหลักของโครงการได้ทันที'
    },
    {
      id: 'api_and_extension',
      category: 'เครื่องมือทดสอบ',
      iconType: 'plug',
      title: 'API Collections, Usage & Chrome Extension',
      subtitle: 'ดักจับ API จริงจากเบราว์เซอร์ จัดการ Collection และติดตาม Token',
      color: '#06b6d4',
      overview:
        'รวบรวม API Endpoints จาก Chrome Extension (Spectra QA - Network & API Sniffer) หรือสร้างเองเพื่อใช้ทดสอบอัตโนมัติ พร้อมแดชบอร์ดติดตามปริมาณการใช้ Token และค่าใช้จ่าย AI',
      flow: ['Sniff API ผ่าน Extension', 'Sync เข้า API Collections', 'นำไปรัน Test / Workflow', 'ติดตาม Token Usage'],
      steps: [
        {
          title: 'ดักจับ Traffic จริงด้วย Chrome Extension',
          detail: 'เปิด Extension ขณะใช้งานเว็บเป้าหมายเพื่อบันทึก Request/Response จริง แล้ว Sync เข้าโครงการใน Spectra QA'
        },
        {
          title: 'จัดการและทดสอบใน API Collections',
          detail: 'แก้ไข Headers, Auth Token และ Payload แล้วทดสอบยิง Request ดู Response Status และ Schema ทันที'
        },
        {
          title: 'ตรวจสอบประสิทธิภาพและต้นทุนใน Token Usage',
          detail: 'ติดตามจำนวน Token และจำนวนการเรียกใช้ AI แยกตามโมดูลและโมเดลเพื่อวางแผนโควต้า API'
        }
      ],
      tip: 'การ Sync API จริงจาก Chrome Extension ช่วยให้ทั้ง QA Performance และ QA Test Automation มี Payload และ Endpoint ที่ตรงกับระบบจริง 100%'
    },
    {
      id: 'orchestration_and_mcp',
      category: 'ระบบอัตโนมัติขั้นสูง',
      iconType: 'cpu',
      title: 'Master Agent, Workflow Builder & MCP',
      subtitle: 'ศูนย์กลางสั่งการ Multi-Agent และเชื่อมต่อเครื่องมือภายนอกผ่าน MCP',
      color: '#a855f7',
      overview:
        'ประสานงานทุกความสามารถของ Spectra QA ผ่านแชทอัจฉริยะ (Master Agent), ออกแบบ Pipeline แบบ Visual Node (AI Workflow Builder) และเชื่อมต่อกับ Claude Desktop / IDE ผ่าน MCP Server',
      flow: ['Master Agent Chat', 'Visual Workflow Graph', 'Playwright & QA MCP Tools', 'ผลลัพธ์ครบวงจร'],
      steps: [
        {
          title: 'สั่งงานข้ามโมดูลผ่าน Master Agent',
          detail: 'พิมพ์คำสั่งภาษาไทยหรือเลือก Quick Prompt เช่น สรุปความเสี่ยงโครงการ, ตรวจเอกสาร หรือสร้างแผนทดสอบ Master Agent จะเลือกเรียก Agent ย่อยให้เอง'
        },
        {
          title: 'สร้าง Pipeline ซับซ้อนใน AI Workflow Builder',
          detail: 'ลากวาง Node (Input, Agent, Debate Loop, Output) เชื่อมเส้นทางการส่งต่อข้อมูลแล้วกด Run พร้อมดู Execution Logs แบบ Real-time'
        },
        {
          title: 'เชื่อมต่อ MCP Server จากภายนอก',
          detail: 'ผูก Spectra QA MCP Server กับ Claude Desktop หรือ Cursor เพื่อสั่งตรวจเอกสาร, ค้นหา KB และรัน Playwright Automation ได้จากภายนอก'
        }
      ],
      tip: 'ใช้ AI Workflow Builder เมื่อมีงานที่ต้องทำซ้ำหลายขั้นตอน (เช่น วิเคราะห์ SRS → สร้าง Test Case → ตรวจ Exit Criteria) เพื่อให้ได้ผลลัพธ์มาตรฐานเดียวกันทุกครั้ง'
    },
    {
      id: 'qa_member',
      category: 'จัดการทีม',
      iconType: 'users',
      title: 'QA Member & Role Access Control',
      subtitle: 'บริหารบัญชีผู้ใช้งาน สิทธิ์การมองเห็นเมนู และขอบเขตโครงการ',
      color: '#10b981',
      overview:
        'จัดการบัญชีสมาชิกทีม QA, BA และ Developer พร้อมกำหนดสิทธิ์แบบละเอียดทั้งระดับ Role (Admin / User), เมนูที่อนุญาตให้เข้าถึง และโครงการที่รับผิดชอบ',
      flow: ['เพิ่มสมาชิก (+ Add User)', 'กำหนด Role & เมนู', 'กำหนด Project Scope', 'ติดตาม Login Activity'],
      steps: [
        {
          title: 'สร้างบัญชีและกำหนดบทบาท',
          detail: 'ระบุ Username, รหัสผ่าน, Display Name, ตำแหน่งงาน และเลือกระดับสิทธิ์ System Admin หรือ Standard User'
        },
        {
          title: 'จำกัดสิทธิ์เมนูและโครงการ (Granular Scoping)',
          detail: 'เลือกเฉพาะเมนูและโครงการที่ผู้ใช้งานควรเข้าถึง เพื่อความปลอดภัยของข้อมูลลูกค้าแต่ละโครงการ'
        },
        {
          title: 'เปิด/ระงับบัญชีและตรวจสอบประวัติ',
          detail: 'สลับสถานะ Active / Inactive ได้ทันที พร้อมตรวจสอบจำนวนครั้งและเวลาที่เข้าสู่ระบบล่าสุด'
        }
      ],
      tip: 'ผู้ใช้งานทุกคนสามารถอัปเดตรูปโปรไฟล์, อีเมลสำหรับรับรายงาน และเปลี่ยนรหัสผ่านด้วยตนเองได้จากเมนูตั้งค่า Profile ที่มุมล่างซ้ายของแถบเมนู'
    }
  ];

  const userSteps = [
    {
      id: 'welcome_user',
      category: 'เริ่มต้นใช้งาน',
      iconType: 'compass',
      title: 'ยินดีต้อนรับสู่ Spectra QA Portal',
      subtitle: 'พื้นที่ทำงาน QA อัจฉริยะครบวงจร (User Mode)',
      color: '#6366f1',
      overview:
        'ศูนย์รวมเครื่องมือสำหรับ QA Engineer, Tester และ BA ครอบคลุมตั้งแต่การค้นคว้า Requirement, วิเคราะห์ Diagram, สร้างและตรวจเอกสาร, ไปจนถึง Playwright Automation, Security และ Performance Testing',
      flow: ['เลือกโครงการ', 'Research / Diagram', 'สร้าง & ตรวจเอกสาร', 'Automation / Security / Perf'],
      steps: [
        {
          title: 'เลือกโครงการที่รับผิดชอบก่อนเริ่มงาน',
          detail: 'ทุกเครื่องมือจะอ้างอิงเอกสารและ Requirement จากโครงการที่เลือกโดยอัตโนมัติ เพื่อความแม่นยำและไม่ปะปนกับโครงการอื่น'
        },
        {
          title: 'ทำความเข้าใจระบบด้วย QA Research & QA Diagram',
          detail: 'สอบถามข้อกำหนดเชิงลึก วิเคราะห์ผลกระทบการแก้ไข (Change Impact) และดูภาพรวม Flow การทำงานของระบบก่อนออกแบบการทดสอบ'
        },
        {
          title: 'สร้างและตรวจรับเอกสารแบบ Closed-Loop',
          detail: 'สร้าง Test Case / SRS ใน QA Document Creation แล้วส่งตรวจใน QA Consult พร้อมแก้ไขอัตโนมัติตาม Exit Criteria'
        },
        {
          title: 'ทดสอบระบบเชิงลึกด้วย Automation, Security & Performance',
          detail: 'สร้างสคริปต์ Playwright ผ่าน MCP, สแกนช่องโหว่โค้ดตามมาตรฐาน OWASP และทดสอบโหลดด้วย k6 ได้ในแพลตฟอร์มเดียว'
        }
      ],
      tip: 'ใช้คีย์บอร์ดปุ่มลูกศร ซ้าย/ขวา เพื่อเลื่อนอ่านคู่มือทีละเมนู หรือคลิกเลือกหัวข้อจากแถบสารบัญด้านซ้ายได้เลยครับ'
    },
    {
      id: 'qa_research',
      category: 'วิเคราะห์และค้นคว้า',
      iconType: 'search',
      title: 'QA Research Agent (5 Research Lenses)',
      subtitle: 'ผู้ช่วยสืบค้น วิเคราะห์ช่องโหว่ และประเมินผลกระทบจากคลังโครงการ',
      color: '#06b6d4',
      overview:
        'สืบค้นข้อมูลจากทุกแหล่งในโครงการ (Knowledge Base, Requirements, QA Documents, ผลตรวจ Consult และ Diagram) ผ่าน 5 โหมดวิเคราะห์เฉพาะทางพร้อมระบุแหล่งอ้างอิง',
      flow: ['เลือก Research Lens', 'เลือกขอบเขตเอกสาร', 'ถามคำถามเชิงลึก', 'ส่งออกรายงาน .md'],
      steps: [
        {
          title: 'เลือกโหมดการค้นคว้า (Research Lens) ให้ตรงงาน',
          detail: 'เลือกได้ 5 โหมด: Deep QA Research (วิเคราะห์เจาะลึก), Gap & Risk Audit (หาจุดเสี่ยง), Test Scenarios (ออกแบบกรณีทดสอบ), Change Impact (ประเมินผลกระทบ) และ Quick Lookup (ค้นหาด่วน)'
        },
        {
          title: 'ตรวจสอบจำนวนข้อมูลที่ระบบ Index ไว้',
          detail: 'ดูแถบ Indexed Knowledge ด้านซ้ายเพื่อเช็กว่าโครงการมีเอกสาร KB, Requirements หรือ Diagram พร้อมอ้างอิงกี่รายการ และสามารถเลือกกรองเฉพาะไฟล์ได้'
        },
        {
          title: 'ส่งออกหรือเชื่อมต่อไปยังเมนูอื่น',
          detail: 'สามารถส่งออกบทสนทนาเป็นไฟล์ Markdown (.md) หรือกดทางลัดด้านบนเพื่อไปยัง QA Consult, QA Diagram และ QA Automation ได้ทันที'
        }
      ],
      tip: 'ใช้โหมด "Change Impact" ทุกครั้งที่มี Change Request เพื่อดูว่าต้องแก้ไขเอกสารหรือ Regression Test จุดใดบ้างในโครงการ'
    },
    {
      id: 'qa_diagram',
      category: 'วิเคราะห์และค้นคว้า',
      iconType: 'diagram',
      title: 'QA Analysis Diagram',
      subtitle: 'สังเคราะห์แผนภาพสถาปัตยกรรม, Workflow และ Screen Flow อัตโนมัติ',
      color: '#818cf8',
      overview:
        'แปลงเอกสาร SRS และ Requirement ที่ซับซ้อนให้เป็นแผนภาพ Mermaid (Flowchart, Sequence Diagram, ER Diagram, System Architecture) เพื่อให้ทีมเห็นภาพตรงกันก่อนทดสอบ',
      flow: ['อ่านเอกสารโครงการ', 'เลือกชนิด Diagram', 'AI สร้าง Mermaid Diagram', 'บันทึกใช้ร่วมกับเมนูอื่น'],
      steps: [
        {
          title: 'เลือกประเภทแผนภาพที่ต้องการวิเคราะห์',
          detail: 'สร้างได้ทั้ง User Flow, Process Flowchart, Sequence Diagram และความสัมพันธ์ของข้อมูลจากเอกสารโครงการ'
        },
        {
          title: 'ตรวจสอบและปรับแต่งแผนภาพ',
          detail: 'ซูมดูรายละเอียด แก้ไขโค้ด Mermaid หรือสั่ง AI ปรับปรุงจุดที่ต้องการเพิ่มเติมได้แบบ Real-time'
        },
        {
          title: 'บันทึกเพื่อแชร์บริบทให้ AI ตัวอื่น',
          detail: 'Diagram ที่บันทึกไว้ในโครงการจะถูกดึงไปใช้อ้างอิงอัตโนมัติทั้งใน QA Document Creation และ QA Research'
        }
      ],
      tip: 'การสร้าง System Flow Diagram ไว้ก่อนจะช่วยให้ AI สร้าง Test Case และวิเคราะห์ Edge Cases ได้ครบถ้วนตามเส้นทางการทำงานจริง'
    },
    {
      id: 'qa_doc_creation',
      category: 'สร้างและตรวจเอกสาร',
      iconType: 'file',
      title: 'QA Document Creation',
      subtitle: 'สร้างและปรับปรุงเอกสาร QA อัตโนมัติจากคลังทุกเมนูในโครงการ',
      color: '#6366f1',
      overview:
        'สร้างเอกสารมาตรฐาน (Test Case .xlsx แยกชีทตามเมนู SRS, SRS, SDD, TOR, UAT, User Manual) โดยระบบดึงข้อมูล KB, Requirements, Diagram และเกณฑ์ Exit Criteria มาวิเคราะห์ให้อัตโนมัติ',
      flow: ['ระบุชื่อ & ประเภทเอกสาร', 'เลือก AI Skill (Optional)', 'สร้างเอกสารเบื้องหลัง', 'ส่งตรวจ QA / บันทึก KB'],
      steps: [
        {
          title: 'กรอกชื่อและเลือกประเภทเอกสาร',
          detail: 'ระบบจะปรับรูปแบบไฟล์ให้อัตโนมัติ: Test Case จะสร้างเป็นไฟล์ Excel (.xlsx) แยก Sheet ตามเมนูใน SRS ส่วนเอกสารอื่นจะเป็น PDF + Markdown'
        },
        {
          title: 'ตั้งค่าตัวเลือกเสริม (AI Skill / Reference Docs / Prompt)',
          detail: 'เปิดแถบตัวเลือกเสริมหากต้องการเลือก AI Skill เพื่อคุมหัวข้อและ Template ให้ตรงตามต้องการ (ไม่เลือกก็ได้ ระบบจะใช้มาตรฐานสากล + Exit Criteria อัตโนมัติ)'
        },
        {
          title: 'ส่งตรวจ QA Consult หรือแก้ไขจากประวัติ',
          detail: 'เมื่อสร้างเสร็จ กด "ส่งตรวจ QA" ได้ทันทีโดยไม่ต้องดาวน์โหลดใหม่ และหากงานไหนไม่ผ่านเกณฑ์ คลิกที่ป้ายผลตรวจเพื่อเปิดดูข้อผิดพลาดและกด Auto Refine ได้เลย'
        }
      ],
      tip: 'ในโหมดปรับปรุงเอกสาร (Auto Refine) คำสั่งแก้ไขจาก QA Consult จะถูกล็อกไว้ในระบบอัตโนมัติ คุณสามารถพิมพ์คำสั่งเสริมหรือเลือก AI Skill เพิ่มเติมได้โดยไม่กระทบรายการที่ต้องแก้'
    },
    {
      id: 'qa_consult',
      category: 'สร้างและตรวจเอกสาร',
      iconType: 'check',
      title: 'QA Consult & Exit Criteria Gate',
      subtitle: 'ตรวจคุณภาพเอกสารเทียบ Baseline โครงการและเกณฑ์ Exit Criteria',
      color: '#8b5cf6',
      overview:
        'ตรวจสอบความถูกต้อง, ความสอดคล้องกับ SRS/Requirements, จุดขัดแย้ง, ข้อมูลที่ขาดหาย และประเมินผ่าน/ไม่ผ่านตามเกณฑ์ Exit Criteria พร้อมส่งออกรายงาน Excel และส่งอีเมล',
      flow: ['เลือกกลุ่มตรวจ (Scan Group)', 'อัปโหลด PDF / Excel / MD', 'ตรวจเทียบ KB + Exit Criteria', 'Export Excel / Auto Refine'],
      steps: [
        {
          title: 'เลือกหรือสร้างกลุ่มการตรวจ (Scan Group)',
          detail: 'จัดกลุ่มการตรวจเอกสารแต่ละรอบ (เช่น SRS รอบที่ 1, Test Case Sprint 2) เพื่อเก็บประวัติเปรียบเทียบการแก้ไขย้อนหลัง (Revision Check)'
        },
        {
          title: 'อัปโหลดเอกสาร (รองรับ PDF, Excel, Markdown)',
          detail: 'ระบุประเภทเอกสาร (Explicit Mode) หรือปล่อยว่างให้ AI จำแนกอัตโนมัติ ระบบจะดึงทั้ง Structured Requirements และเอกสาร Baseline ของโครงการมาเทียบเสมอ'
        },
        {
          title: 'ตรวจสอบผล Gate, ประเมินเกณฑ์ใหม่ หรือส่งแก้',
          detail: 'ดูตาราง QA Audit Findings และ Exit Criteria Gate (PASSED / CONDITIONAL_PASSED / REJECTED) สามารถกด "ประเมินเกณฑ์ใหม่" ได้ในคลิกเดียว หรือกด "ส่งแก้ไขใน QA Doc Creation"'
        }
      ],
      tip: 'ควรส่งเอกสารเวอร์ชันปรับปรุงเข้าใน Scan Group เดิม เพื่อให้ AI เปรียบเทียบกับรอบก่อนหน้าและยืนยันว่าประเด็น Critical/High เดิมได้รับการแก้ไขแล้ว 100%'
    },
    {
      id: 'qa_automate',
      category: 'ทดสอบระบบอัตโนมัติ',
      iconType: 'code',
      title: 'QA Test Automation & Playwright MCP',
      subtitle: 'วิเคราะห์ความคุ้มค่า, บันทึก Flow บนเว็บจริง และสร้างสคริปต์ POM',
      color: '#10b981',
      overview:
        'วางแผนกลยุทธ์การทำ Automation (ROI & ข้อดี-ข้อเสีย), สกัด Test Case จากระบบ, เปิดเบราว์เซอร์เล่นจริงผ่าน Playwright MCP, สร้างสคริปต์ Page Object Model และวัดความแม่นยำเทียบ Business Flow',
      flow: ['วิเคราะห์ Feasibility / ROI', 'ดึง Test Case / เล่นเว็บจริง', 'Generate POM Script', 'Run & วัด Business Accuracy'],
      steps: [
        {
          title: 'วิเคราะห์ Requirement ว่าจุดไหนควรทำ Automate',
          detail: 'ใช้แท็บ Strategy Planner เพื่อวิเคราะห์ว่าฟังก์ชันใดคุ้มค่าในการเขียน Automate, จุดใดควรทำ Manual และมีข้อดี-ข้อเสียอย่างไร'
        },
        {
          title: 'เลือกโหมดสร้างสคริปต์ (Test Case / Live Web Play / Hybrid)',
          detail: 'สร้างจาก Test Case ในระบบ, ให้ Playwright MCP เปิดเว็บไซต์เล่นและบันทึก Action จริง หรือใช้โหมด Hybrid ผสานทั้งสองอย่างเพื่อความแม่นยำสูงสุด'
        },
        {
          title: 'รันทดสอบ, Self-Heal และตรวจ Accuracy Scorecard',
          detail: 'สั่งรันสคริปต์ผ่าน Playwright พร้อมระบบ Self-Healing แก้ Selector อัตโนมัติ และตรวจสอบคะแนนความตรงตาม Flow ธุรกิจของลูกค้า'
        }
      ],
      tip: 'แนะนำให้ใช้โหมด Hybrid (อ้างอิง Test Case ของโครงการ + บันทึก Selector จากหน้าเว็บจริงผ่าน MCP) เพื่อให้สคริปต์ทั้งรันผ่านจริงและครอบคลุม Business Rules ครบถ้วน'
    },
    {
      id: 'qa_security',
      category: 'ทดสอบความปลอดภัยและโหลด',
      iconType: 'lock',
      title: 'QA Security Audit',
      subtitle: 'ตรวจสอบช่องโหว่ซอร์สโค้ดตามมาตรฐาน OWASP Top 10, ASVS & SANS 25',
      color: '#f43f5e',
      overview:
        'วิเคราะห์ความเสี่ยงด้านความปลอดภัยของโค้ดและ API เพื่อระบุช่องโหว่ (SQL Injection, XSS, Broken Auth, Sensitive Data Exposure) พร้อมโค้ดตัวอย่างในการแก้ไข',
      flow: ['วางโค้ด / ระบุ GitHub URL', 'เลือกมาตรฐาน Security', 'AI Scan ช่องโหว่', 'รับแนวทาง Remediation'],
      steps: [
        {
          title: 'นำเข้าซอร์สโค้ดที่ต้องการตรวจสอบ',
          detail: 'วางซอร์สโค้ดโดยตรงหรือระบุลิงก์ Repository พร้อมเลือกภาษาโปรแกรมที่ใช้'
        },
        {
          title: 'เลือกมาตรฐานการประเมินความปลอดภัย',
          detail: 'กำหนดมาตรฐานที่ต้องการอ้างอิง เช่น OWASP Top 10, OWASP ASVS หรือ SANS Top 25'
        },
        {
          title: 'ตรวจสอบรายงานความเสี่ยงและโค้ดแก้ไข',
          detail: 'ดูรายการช่องโหว่แยกตามระดับความรุนแรง (Critical / High / Medium / Low) พร้อมคำแนะนำและตัวอย่างโค้ดที่ปลอดภัย'
        }
      ],
      tip: 'ตรวจซ้ำทุกครั้งก่อนขึ้น Production โดยเฉพาะโมดูลที่เกี่ยวกับการ Login, การจัดการ Token, การอัปโหลดไฟล์ และการเชื่อมต่อฐานข้อมูล'
    },
    {
      id: 'qa_performance',
      category: 'ทดสอบความปลอดภัยและโหลด',
      iconType: 'bolt',
      title: 'QA Performance Testing',
      subtitle: 'วางแผนและทดสอบประสิทธิภาพระบบ (Load / Stress Benchmark)',
      color: '#f59e0b',
      overview:
        'ออกแบบและรันสคริปต์ทดสอบโหลด (k6) เพื่อวัด Response Time (P95/P99), Throughput และ Error Rate เทียบกับเกณฑ์ SLA ของโครงการ',
      flow: ['เลือก API / สคริปต์ k6', 'ตั้งค่า VUs & Duration', 'รัน Load Test', 'วิเคราะห์ Bottleneck & SLA'],
      steps: [
        {
          title: 'กำหนด Endpoint และสคริปต์ทดสอบโหลด',
          detail: 'เลือกจาก API Collections ของโครงการหรือสร้างสคริปต์ k6 พร้อมตั้งค่า Virtual Users (VUs), Ramp-up และระยะเวลาทดสอบ'
        },
        {
          title: 'ติดตามตัวชี้วัดแบบ Real-time',
          detail: 'สังเกตกราฟ Response Time (P95 / P99), Requests per Second (RPS) และอัตราการเกิด Error ขณะระบบรับโหลด'
        },
        {
          title: 'สรุปจุดคอขวดเทียบกับเกณฑ์ SLA',
          detail: 'ให้ AI วิเคราะห์ผลลัพธ์และชี้จุดคอขวด (Bottleneck) พร้อมข้อเสนอแนะในการจูนประสิทธิภาพ'
        }
      ],
      tip: 'ควรเริ่มทดสอบจาก Smoke Test (VUs น้อย) ก่อนขยับไป Load Test และ Stress Test เพื่อป้องกันไม่ให้ระบบเป้าหมายล่มกะทันหัน'
    },
    {
      id: 'master_agent_user',
      category: 'ผู้ช่วยอัจฉริยะ',
      iconType: 'cpu',
      title: 'Master Agent & AI Workflow Builder',
      subtitle: 'สั่งงานผู้ช่วย AI กลางและรัน Pipeline แบบ Multi-Agent',
      color: '#a855f7',
      overview:
        'ศูนย์รวมการสั่งงานด้วยภาษาธรรมชาติที่เชื่อมทุกเครื่องมือ QA เข้าด้วยกัน รวมถึงการรัน Multi-Agent Workflow Pipeline ที่ตั้งค่าไว้สำหรับโครงการ',
      flow: ['พิมพ์คำสั่ง / Quick Prompt', 'Agent ประสานงานข้ามเมนู', 'รับผลวิเคราะห์ Markdown', 'คัดลอก / ใช้งานต่อ'],
      steps: [
        {
          title: 'สั่งงานภาษาไทยผ่าน Master Agent',
          detail: 'พิมพ์คำถามหรือเลือกคำสั่งด่วน Master Agent จะเรียกใช้ความรู้จาก KB และประสานงานกับเครื่องมือ QA ที่เกี่ยวข้องให้อัตโนมัติ'
        },
        {
          title: 'รัน Pipeline ใน AI Workflow Builder',
          detail: 'เลือก Workflow ของโครงการ ใส่ข้อมูลนำเข้า แล้วติดตามการทำงานของแต่ละ Agent Node แบบ Real-time จนได้ผลลัพธ์สุดท้าย'
        },
        {
          title: 'เชื่อมต่อ Claude Desktop ผ่าน MCP',
          detail: 'สามารถเรียกใช้เครื่องมือของ Spectra QA จาก Claude Desktop ได้โดยตรงหากติดตั้ง MCP Server ไว้ในเครื่อง'
        }
      ],
      tip: 'เมื่อไม่แน่ใจว่าควรเริ่มจากเมนูไหน สามารถถาม Master Agent ให้ช่วยวางแผนลำดับการทดสอบสำหรับโครงการของคุณได้ทันที'
    }
  ];

  $: steps = userRole === 'admin' ? adminSteps : userSteps;
  let currentStep = 0;
  $: if (currentStep >= steps.length) currentStep = 0;
  $: step = steps[currentStep];
  $: isFirst = currentStep === 0;
  $: isLast = currentStep === steps.length - 1;
  $: progressRatio = (currentStep + 1) / steps.length;
  $: progressPct = Math.round(progressRatio * 100);

  function goToStep(idx) {
    if (idx === currentStep || idx < 0 || idx >= steps.length) return;
    direction = idx > currentStep ? 1 : -1;
    currentStep = idx;
    showMobileMenu = false;
  }

  function next() {
    if (!isLast) {
      direction = 1;
      currentStep += 1;
    }
  }

  function prev() {
    if (!isFirst) {
      direction = -1;
      currentStep -= 1;
    }
  }

  function close() {
    dispatch('close');
  }

  function handleKeydown(e) {
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      next();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      prev();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      if (showMobileMenu) {
        showMobileMenu = false;
      } else {
        close();
      }
    }
  }

  onMount(() => window.addEventListener('keydown', handleKeydown));
  onDestroy(() => window.removeEventListener('keydown', handleKeydown));
</script>

<!-- ── Backdrop ── -->
<div
  class="tutorial-backdrop"
  role="presentation"
  transition:fade={{ duration: 220 }}
  on:click|self={close}
>
  <!-- ── 2-Pane Interactive Guide Deck ── -->
  <div
    class="tutorial-shell"
    role="dialog"
    aria-modal="true"
    aria-labelledby="tutorial-step-title"
    in:fly={{ y: 24, duration: 360, easing: cubicOut }}
    out:fade={{ duration: 160 }}
    style="--step-color: {step.color};"
  >
    <!-- Top Progress Accent Rail (GPU scaleX) -->
    <div class="top-progress-track" aria-hidden="true">
      <div class="top-progress-bar" style="transform: scaleX({progressRatio});"></div>
    </div>

    <!-- LEFT RAIL: Chapter Navigation (Desktop) -->
    <aside class="tutorial-sidebar" aria-label="สารบัญคู่มือการใช้งาน">
      <div class="sidebar-brand">
        <div class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-title">Spectra QA Guide</span>
          <span class="brand-role">{userRole === 'admin' ? 'System Admin Curriculum' : 'Standard User Curriculum'}</span>
        </div>
      </div>

      <nav class="chapter-list">
        {#each steps as s, idx}
          <button
            type="button"
            class="chapter-item"
            class:active={idx === currentStep}
            class:visited={idx < currentStep}
            on:click={() => goToStep(idx)}
            aria-current={idx === currentStep ? 'step' : undefined}
          >
            <span class="chapter-index">
              {#if idx < currentStep}
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.6" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              {:else}
                {idx + 1}
              {/if}
            </span>
            <span class="chapter-meta">
              <span class="chapter-cat">{s.category}</span>
              <span class="chapter-name">{s.title}</span>
            </span>
          </button>
        {/each}
      </nav>

      <div class="sidebar-footer">
        <div class="progress-readout">
          <span>ความคืบหน้าคู่มือ</span>
          <strong>{progressPct}%</strong>
        </div>
        <div class="sidebar-progress-track">
          <div class="sidebar-progress-fill" style="transform: scaleX({progressRatio});"></div>
        </div>
      </div>
    </aside>

    <!-- RIGHT STAGE: Step Content & Animated Flow -->
    <div class="tutorial-stage">
      <!-- Top Bar (Mobile Chapter Picker + Close) -->
      <header class="stage-topbar">
        <div class="stage-step-counter">
          <span class="step-dot" aria-hidden="true"></span>
          <span>บทที่ {currentStep + 1} จาก {steps.length}</span>
          <span class="step-category-pill">{step.category}</span>
        </div>

        <div class="topbar-right">
          <button
            type="button"
            class="btn-mobile-chapters"
            on:click={() => showMobileMenu = !showMobileMenu}
            aria-expanded={showMobileMenu}
          >
            <span>สารบัญ ({currentStep + 1}/{steps.length})</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>

          <button type="button" class="btn-close-tutorial" on:click={close} aria-label="ปิดคู่มือการใช้งาน" title="ปิด (Esc)">
            <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </header>

      <div class="stage-content-wrap">
        {#if showMobileMenu}
          <div class="mobile-chapter-drawer" transition:fly={{ y: -10, duration: 200, easing: cubicOut }}>
            {#each steps as s, idx}
              <button
                type="button"
                class="mobile-chapter-btn"
                class:active={idx === currentStep}
                on:click={() => goToStep(idx)}
              >
                <span class="mc-num">{idx + 1}.</span>
                <span class="mc-title">{s.title}</span>
              </button>
            {/each}
          </div>
        {/if}

        <!-- Scrollable Animated Stage Body -->
        <div class="stage-scroll-area">
        {#key currentStep}
          <div
            class="stage-body"
            in:fly={{ x: direction * 28, duration: 280, easing: cubicOut }}
          >
            <!-- Step Hero Header -->
            <div class="step-hero">
              <div class="step-icon-orb" aria-hidden="true">
                {#if step.iconType === 'compass'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><circle cx="12" cy="12" r="10"></circle><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"></polygon></svg>
                {:else if step.iconType === 'folder'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                {:else if step.iconType === 'scan'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M3 7V5a2 2 0 0 1 2-2h2"></path><path d="M17 3h2a2 2 0 0 1 2 2v2"></path><path d="M21 17v2a2 2 0 0 1-2 2h-2"></path><path d="M7 21H5a2 2 0 0 1-2-2v-2"></path><line x1="7" y1="12" x2="17" y2="12"></line></svg>
                {:else if step.iconType === 'database'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
                {:else if step.iconType === 'sparkles'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                {:else if step.iconType === 'shield'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>
                {:else if step.iconType === 'workflow'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                {:else if step.iconType === 'plug'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M12 22v-5"></path><path d="M9 8V2"></path><path d="M15 8V2"></path><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"></path></svg>
                {:else if step.iconType === 'cpu'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><rect x="4" y="4" width="16" height="16" rx="2"></rect><rect x="9" y="9" width="6" height="6"></rect><line x1="9" y1="1" x2="9" y2="4"></line><line x1="15" y1="1" x2="15" y2="4"></line><line x1="9" y1="20" x2="9" y2="23"></line><line x1="15" y1="20" x2="15" y2="23"></line><line x1="20" y1="9" x2="23" y2="9"></line><line x1="20" y1="14" x2="23" y2="14"></line><line x1="1" y1="9" x2="4" y2="9"></line><line x1="1" y1="14" x2="4" y2="14"></line></svg>
                {:else if step.iconType === 'users'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                {:else if step.iconType === 'search'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                {:else if step.iconType === 'diagram'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><rect x="3" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="3" width="7" height="7" rx="1.5"></rect><rect x="8.5" y="14" width="7" height="7" rx="1.5"></rect><path d="M6.5 10v2a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-2"></path></svg>
                {:else if step.iconType === 'file'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
                {:else if step.iconType === 'check'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                {:else if step.iconType === 'code'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
                {:else if step.iconType === 'lock'}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                {:else}
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                {/if}
              </div>
              <div class="step-hero-text">
                <h2 id="tutorial-step-title" class="stage-title">{step.title}</h2>
                <p class="stage-subtitle">{step.subtitle}</p>
              </div>
            </div>

            <!-- Overview -->
            <p class="overview-copy">{step.overview}</p>

            <!-- Mini Process Flow Strip (Animated Entrance) -->
            {#if step.flow && step.flow.length > 0}
              <div class="flow-pipeline" aria-label="ลำดับการทำงานโดยย่อ">
                {#each step.flow as node, nIdx}
                  <div class="flow-node" style="--node-delay: {nIdx * 45}ms;">
                    <span class="flow-node-num">{nIdx + 1}</span>
                    <span class="flow-node-label">{node}</span>
                  </div>
                  {#if nIdx < step.flow.length - 1}
                    <svg class="flow-arrow" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                      <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                  {/if}
                {/each}
              </div>
            {/if}

            <!-- Detailed Step-by-Step Cards (Staggered Reveal, capped <= 220ms) -->
            <div class="steps-section">
              <div class="section-heading">ขั้นตอนการใช้งานอย่างละเอียด (Step-by-Step)</div>
              <ol class="step-cards-list">
                {#each step.steps as item, sIdx}
                  <li class="step-card" style="--stagger: {Math.min(sIdx * 45, 180)}ms;">
                    <div class="step-card-num" aria-hidden="true">{sIdx + 1}</div>
                    <div class="step-card-body">
                      <div class="step-card-title">{item.title}</div>
                      <div class="step-card-detail">{item.detail}</div>
                    </div>
                  </li>
                {/each}
              </ol>
            </div>

            <!-- Pro Tip Callout -->
            {#if step.tip}
              <div class="pro-tip-box">
                <div class="pro-tip-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                </div>
                <div class="pro-tip-content">
                  <strong>คำแนะนำการใช้งานให้แม่นยำ:</strong> {step.tip}
                </div>
              </div>
            {/if}
          </div>
        {/key}
        </div>
      </div>

      <!-- Bottom Action Footer -->
      <footer class="stage-footer">
        <div class="footer-hint">
          <kbd>←</kbd> <kbd>→</kbd> เปลี่ยนบทเรียน &middot; <kbd>Esc</kbd> ปิด
        </div>

        <div class="footer-actions">
          <button type="button" class="btn-nav-secondary" on:click={prev} disabled={isFirst}>
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
            <span>ก่อนหน้า</span>
          </button>

          {#if isLast}
            <button type="button" class="btn-nav-primary btn-finish" on:click={close}>
              <span>เริ่มใช้งานระบบ</span>
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </button>
          {:else}
            <button type="button" class="btn-nav-primary" on:click={next}>
              <span>บทถัดไป</span>
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <polyline points="9 18 15 12 9 6"></polyline>
              </svg>
            </button>
          {/if}
        </div>
      </footer>
    </div>
  </div>
</div>

<style>
  .tutorial-backdrop {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal, 10000);
    background: rgba(5, 7, 14, 0.84);
    backdrop-filter: blur(12px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    font-family: 'Prompt', 'Outfit', sans-serif;
  }

  .tutorial-shell {
    position: relative;
    width: 100%;
    max-width: 1040px;
    height: min(86vh, 760px);
    display: grid;
    grid-template-columns: 280px 1fr;
    background: rgba(14, 16, 26, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.72);
  }

  /* Top GPU Progress Accent */
  .top-progress-track {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: rgba(255, 255, 255, 0.05);
    z-index: 20;
  }
  .top-progress-bar {
    height: 100%;
    width: 100%;
    transform-origin: left center;
    background: linear-gradient(90deg, var(--step-color, #6366f1), #a855f7);
    transition: transform 320ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* Left Sidebar Rail */
  .tutorial-sidebar {
    background: rgba(10, 11, 18, 0.85);
    border-right: 1px solid rgba(255, 255, 255, 0.07);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .sidebar-brand {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 20px 18px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .brand-mark {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #a5b4fc;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .brand-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .brand-title {
    font-family: 'Outfit', sans-serif;
    font-size: 14.5px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
  }

  .brand-role {
    font-size: 11px;
    color: #94a3b8;
  }

  .chapter-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .chapter-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 10px;
    border-radius: 10px;
    background: transparent;
    border: 1px solid transparent;
    color: #94a3b8;
    text-align: left;
    font-family: inherit;
    cursor: pointer;
    transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
  }

  .chapter-item:hover {
    background: rgba(255, 255, 255, 0.04);
    color: #e2e8f0;
  }

  .chapter-item.active {
    background: color-mix(in srgb, var(--step-color, #6366f1) 14%, transparent);
    border-color: color-mix(in srgb, var(--step-color, #6366f1) 36%, transparent);
    color: #f8fafc;
  }

  .chapter-index {
    width: 22px;
    height: 22px;
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.06);
    color: #94a3b8;
    font-family: 'Outfit', sans-serif;
    font-size: 11.5px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background-color 180ms ease, color 180ms ease;
  }

  .chapter-item.active .chapter-index {
    background: var(--step-color, #6366f1);
    color: #ffffff;
  }

  .chapter-item.visited .chapter-index {
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
  }

  .chapter-meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .chapter-cat {
    font-size: 10px;
    color: var(--text-muted, #94a3b8);
    line-height: 1.2;
  }

  .chapter-item.active .chapter-cat {
    color: #a5b4fc;
  }

  .chapter-name {
    font-size: 12.5px;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sidebar-footer {
    padding: 14px 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(10, 11, 18, 0.6);
  }

  .progress-readout {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11.5px;
    color: #94a3b8;
    margin-bottom: 7px;
  }
  .progress-readout strong {
    font-family: 'Outfit', sans-serif;
    color: #e2e8f0;
    font-variant-numeric: tabular-nums;
  }

  .sidebar-progress-track {
    height: 5px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
  }
  .sidebar-progress-fill {
    height: 100%;
    width: 100%;
    transform-origin: left center;
    background: linear-gradient(90deg, #6366f1, #a855f7);
    transition: transform 320ms cubic-bezier(0.16, 1, 0.3, 1);
  }

  /* Right Main Stage */
  .tutorial-stage {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    position: relative;
  }

  .stage-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px 12px;
    padding: 16px 26px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .stage-content-wrap {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .stage-step-counter {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: #94a3b8;
    font-variant-numeric: tabular-nums;
  }

  .step-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--step-color, #6366f1);
    transition: background-color 250ms ease;
  }

  .step-category-pill {
    padding: 2px 9px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.06);
    color: #cbd5e1;
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-mobile-chapters {
    display: none;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #e2e8f0;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-family: inherit;
    cursor: pointer;
  }

  .btn-close-tutorial {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 150ms ease, color 150ms ease;
  }
  .btn-close-tutorial:hover {
    background: rgba(239, 68, 68, 0.18);
    border-color: rgba(239, 68, 68, 0.36);
    color: #fca5a5;
  }

  .mobile-chapter-drawer {
    position: absolute;
    top: 8px;
    left: 16px;
    right: 16px;
    z-index: 30;
    max-height: 280px;
    overflow-y: auto;
    background: #121524;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mobile-chapter-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    background: transparent;
    border: none;
    color: #cbd5e1;
    font-size: 12.5px;
    font-family: inherit;
    text-align: left;
    cursor: pointer;
  }
  .mobile-chapter-btn.active {
    background: rgba(99, 102, 241, 0.2);
    color: #ffffff;
    font-weight: 600;
  }
  .mc-num {
    font-family: 'Outfit', sans-serif;
    color: #94a3b8;
    width: 18px;
  }

  .stage-scroll-area {
    flex: 1;
    overflow-y: auto;
    padding: 24px 28px;
    min-height: 0;
  }

  .stage-body {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }

  .step-hero {
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }

  .step-icon-orb {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--step-color, #6366f1) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--step-color, #6366f1) 38%, transparent);
    color: color-mix(in srgb, var(--step-color, #6366f1) 80%, #ffffff);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .step-hero-text {
    min-width: 0;
  }

  .stage-title {
    margin: 0;
    font-family: 'Outfit', 'Prompt', sans-serif;
    font-size: 1.4rem;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.02em;
    line-height: 1.25;
  }

  .stage-subtitle {
    margin: 4px 0 0;
    font-size: 13px;
    color: #94a3b8;
  }

  .overview-copy {
    margin: 0;
    font-size: 13.5px;
    line-height: 1.65;
    color: #cbd5e1;
    max-width: 70ch;
  }

  /* Animated Mini Flow Pipeline */
  .flow-pipeline {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    padding: 12px 14px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.07);
  }

  .flow-node {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--step-color, #6366f1) 12%, rgba(15, 23, 42, 0.8));
    border: 1px solid color-mix(in srgb, var(--step-color, #6366f1) 28%, transparent);
    font-size: 12px;
    font-weight: 500;
    color: #e2e8f0;
    animation: nodeSettle 260ms cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: var(--node-delay, 0ms);
  }

  .flow-node-num {
    width: 17px;
    height: 17px;
    border-radius: 5px;
    background: var(--step-color, #6366f1);
    color: #ffffff;
    font-family: 'Outfit', sans-serif;
    font-size: 10.5px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .flow-arrow {
    color: var(--text-muted, #94a3b8);
    flex-shrink: 0;
  }

  @keyframes nodeSettle {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  /* Step-by-Step Cards */
  .steps-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .section-heading {
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
    letter-spacing: 0.02em;
  }

  .step-cards-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 9px;
  }

  .step-card {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: rgba(18, 20, 32, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.07);
    animation: cardReveal 300ms cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: var(--stagger, 0ms);
    transition: border-color 180ms ease, background-color 180ms ease;
  }

  .step-card:hover {
    border-color: color-mix(in srgb, var(--step-color, #6366f1) 35%, transparent);
    background: rgba(24, 27, 44, 0.9);
  }

  @keyframes cardReveal {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .step-card-num {
    width: 24px;
    height: 24px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--step-color, #6366f1) 18%, transparent);
    border: 1px solid color-mix(in srgb, var(--step-color, #6366f1) 36%, transparent);
    color: color-mix(in srgb, var(--step-color, #6366f1) 80%, #ffffff);
    font-family: 'Outfit', sans-serif;
    font-size: 12px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
  }

  .step-card-body {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .step-card-title {
    font-size: 13.5px;
    font-weight: 600;
    color: #f8fafc;
  }

  .step-card-detail {
    font-size: 12.5px;
    line-height: 1.55;
    color: #94a3b8;
  }

  /* Pro Tip Box */
  .pro-tip-box {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 12px;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: #c7d2fe;
    font-size: 12.5px;
    line-height: 1.55;
  }

  .pro-tip-icon {
    color: #a5b4fc;
    flex-shrink: 0;
    margin-top: 2px;
  }

  .pro-tip-content strong {
    color: #e0e7ff;
    font-weight: 600;
  }

  /* Stage Footer */
  .stage-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 26px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
    background: rgba(10, 11, 18, 0.6);
  }

  .footer-hint {
    font-size: 11.5px;
    color: var(--text-muted, #94a3b8);
    display: flex;
    align-items: center;
    gap: 5px;
  }

  kbd {
    font-family: 'Outfit', monospace;
    font-size: 10.5px;
    padding: 2px 6px;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
  }

  .footer-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .btn-nav-secondary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 16px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    transition: background-color 150ms ease, color 150ms ease;
  }
  .btn-nav-secondary:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }
  .btn-nav-secondary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-nav-primary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 9px 20px;
    border-radius: 10px;
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: transform 150ms ease, box-shadow 180ms ease;
  }
  .btn-nav-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.38);
  }
  .btn-nav-primary.btn-finish {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  }
  .btn-nav-primary.btn-finish:hover {
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.35);
  }

  /* Responsive: Collapse Sidebar into Top Chapter Drawer */
  @media (max-width: 860px) {
    .tutorial-shell {
      grid-template-columns: 1fr;
      height: min(90vh, 780px);
    }
    .tutorial-sidebar {
      display: none;
    }
    .btn-mobile-chapters {
      display: inline-flex;
    }
    .stage-topbar {
      padding: 14px 16px;
    }
    .stage-scroll-area {
      padding: 18px 16px;
    }
    .stage-footer {
      padding: 12px 16px;
    }
    .footer-hint {
      display: none;
    }
  }

  /* Reduced Motion: Preserve opacity & color state feedback, remove spatial travel */
  @media (prefers-reduced-motion: reduce) {
    .flow-node,
    .step-card {
      animation: none !important;
    }
    .top-progress-bar,
    .sidebar-progress-fill,
    .btn-nav-primary {
      transition: opacity 150ms ease, background-color 150ms ease !important;
      transform: none;
    }
  }
</style>
