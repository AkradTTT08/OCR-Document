<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { fade, fly } from 'svelte/transition';

  export let type = 'privacy'; // 'privacy' | 'terms' | 'security'

  const dispatch = createEventDispatcher();

  const content = {
    privacy: {
      title: 'นโยบายความเป็นส่วนตัว (Privacy Policy)',
      icon: '🔒',
      body: `
        <h3>1. การเก็บรวบรวมข้อมูล (Data Collection)</h3>
        <p>Spectra QA จะเก็บรวบรวมข้อมูลเอกสาร (PDF, รูปภาพ) ที่คุณอัปโหลดเข้าระบบเพื่อใช้ในการวิเคราะห์และตรวจสอบคุณภาพเท่านั้น โดยข้อมูลที่สกัดได้จะถูกแปลงเป็น Vector Embeddings และจัดเก็บในฐานข้อมูล Knowledge Base (RAG) ภายในเครือข่ายจำกัด</p>
        
        <h3>2. การใช้ข้อมูล AI (AI Processing)</h3>
        <p>ข้อมูลเอกสารจะถูกส่งผ่านระบบ Model Context Protocol (MCP) ไปยัง Claude API แบบชั่วคราวเพื่อทำการประเมิน (Exit Criteria) ทั้งนี้ ผู้พัฒนา AI จะไม่นำข้อมูลของคุณไปใช้เทรนโมเดล (Zero Data Retention Policy ในระดับ API)</p>

        <h3>3. สิทธิของผู้ใช้งาน (User Rights)</h3>
        <p>คุณมีสิทธิในการขอลบเอกสาร ประวัติการตรวจสอบ (Audit Logs) และจัดการข้อมูลบัญชีผู้ใช้ (QA Member) ของตนเองได้ตลอดเวลาผ่านผู้ดูแลระบบ (Admin)</p>
      `
    },
    terms: {
      title: 'ข้อตกลงการให้บริการ (Terms of Service)',
      icon: '📜',
      body: `
        <h3>1. เงื่อนไขการใช้งาน (Acceptable Use)</h3>
        <p>Spectra QA ถูกออกแบบมาเพื่อการตรวจสอบเอกสารภายในองค์กร ผู้ใช้ตกลงที่จะไม่อัปโหลดไฟล์ที่มีมัลแวร์ ข้อมูลผิดกฎหมาย หรือข้อมูลที่ละเมิดทรัพย์สินทางปัญญาของบุคคลที่สาม</p>

        <h3>2. ข้อจำกัดความรับผิดชอบของระบบ AI (AI Disclaimer)</h3>
        <p>ผลการตรวจสอบและข้อเสนอแนะที่สร้างโดย AI (รวมถึง Spell Check และ Exit Criteria) มีวัตถุประสงค์เพื่อช่วยคัดกรองข้อมูลเท่านั้น ผู้ใช้งานควรใช้วิจารณญาณและตรวจสอบความถูกต้องอีกครั้งก่อนนำไปใช้งานจริง (Human-in-the-loop)</p>

        <h3>3. นโยบายการระงับบัญชี (Account Suspension)</h3>
        <p>ผู้ดูแลระบบ (Admin) สงวนสิทธิ์ในการระงับการเข้าถึง (Deactivate) บัญชีผู้ใช้ที่พบพฤติกรรมการใช้งานที่สุ่มเสี่ยงต่อความปลอดภัยของระบบโดยไม่ต้องแจ้งล่วงหน้า</p>
      `
    },
    security: {
      title: 'สถาปัตยกรรมความปลอดภัย (Security Architecture)',
      icon: '🛡️',
      body: `
        <h3>1. การปกป้องข้อมูล (Data Protection)</h3>
        <ul>
          <li><strong>Encryption in Transit:</strong> ข้อมูลทั้งหมดถูกเข้ารหัสผ่านโปรโตคอล TLS/SSL 1.2+ ระหว่างผู้ใช้และเซิร์ฟเวอร์</li>
          <li><strong>Authentication:</strong> รหัสผ่าน (Passwords) จะถูก Hash ด้วยอัลกอริทึม bcrypt เสมอ</li>
        </ul>

        <h3>2. ความปลอดภัยระดับ AI (AI Safety)</h3>
        <ul>
          <li><strong>Circuit Breaker System:</strong> ระบบป้องกัน AI ติดลูปอัตโนมัติ (Infinite Loop Prevention) เมื่อพบว่า AI ไม่สามารถแก้ไขเอกสารให้ผ่านเกณฑ์ได้เกินจำนวนครั้งที่กำหนด</li>
          <li><strong>SSRF Protection:</strong> การใช้โมดูล SSRF Proxy ช่วยป้องกัน AI เข้าถึงเครือข่ายภายในองค์กรโดยพลการ</li>
        </ul>

        <h3>3. โครงสร้างพื้นฐาน (Infrastructure)</h3>
        <p>Database (PostgreSQL + pgvector) สำหรับจัดการ Knowledge Base ทำงานอยู่ใน Network ที่แยกส่วน (Isolated VPC) และจำกัดการเชื่อมต่อเฉพาะผ่าน MCP Server (FastMCP) เพื่อรับรองความเสถียรและความปลอดภัย</p>
      `
    }
  };

  $: currentContent = content[type] || content.privacy;

  function close() {
    dispatch('close');
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') close();
  }

  onMount(() => window.addEventListener('keydown', handleKeydown));
  onDestroy(() => window.removeEventListener('keydown', handleKeydown));
</script>

<div
  class="modal-backdrop"
  role="dialog"
  aria-modal="true"
  transition:fade={{ duration: 200 }}
  on:click|self={close}
>
  <div class="modal-card" in:fly={{ y: 20, duration: 300 }}>
    <div class="modal-header">
      <div class="modal-title">
        <span class="icon">{currentContent.icon}</span>
        {currentContent.title}
      </div>
      <button class="btn-close" on:click={close} title="ปิด (Esc)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
    
    <div class="modal-body">
      {@html currentContent.body}
    </div>

    <div class="modal-footer">
      <button class="btn-primary" on:click={close}>รับทราบและปิดหน้าต่าง</button>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9999;
    background: rgba(10, 15, 30, 0.7);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .modal-card {
    background: #1a1c29;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    width: 100%;
    max-width: 650px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    background: #202336;
  }

  .modal-title {
    font-size: 1.15rem;
    font-weight: 600;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .icon {
    font-size: 1.3rem;
  }

  .btn-close {
    background: transparent;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .btn-close:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }

  .modal-body {
    padding: 24px;
    overflow-y: auto;
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.7;
  }

  .modal-body :global(h3) {
    color: #fff;
    font-size: 1.05rem;
    margin-top: 24px;
    margin-bottom: 12px;
    font-weight: 600;
  }
  
  .modal-body :global(h3:first-child) {
    margin-top: 0;
  }

  .modal-body :global(p) {
    margin-bottom: 16px;
  }

  .modal-body :global(ul) {
    padding-left: 20px;
    margin-bottom: 16px;
  }

  .modal-body :global(li) {
    margin-bottom: 8px;
  }
  
  .modal-body :global(strong) {
    color: #e2e8f0;
  }

  .modal-footer {
    padding: 16px 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    background: #1a1c29;
    display: flex;
    justify-content: flex-end;
  }

  .btn-primary {
    background: #6366f1;
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-primary:hover {
    background: #4f46e5;
  }
</style>
