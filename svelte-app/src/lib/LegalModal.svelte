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
  role="presentation"
  transition:fade={{ duration: 200 }}
  on:click|self={close}
>
  <div
    class="modal-card"
    role="dialog"
    aria-modal="true"
    aria-labelledby="legal-modal-title"
    in:fly={{ y: 20, duration: 300 }}
  >
    <div class="modal-header">
      <h2 id="legal-modal-title" class="modal-title">
        <span class="icon" aria-hidden="true">{currentContent.icon}</span>
        {currentContent.title}
      </h2>
      <button type="button" class="btn-close" aria-label="ปิดหน้าต่าง" on:click={close} title="ปิด (Esc)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
    
    <div class="modal-body">
      {@html currentContent.body}
    </div>

    <div class="modal-footer">
      <button type="button" class="btn-primary" on:click={close}>รับทราบและปิดหน้าต่าง</button>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    z-index: calc(var(--z-modal, 10000) + 100);
    background: rgba(5, 7, 14, 0.78);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
  }

  .modal-card {
    background: var(--bg2, #12141c);
    border: 1px solid var(--glass-border-light, rgba(255, 255, 255, 0.15));
    border-radius: var(--radius-lg, 20px);
    width: 100%;
    max-width: 650px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.65);
    overflow: hidden;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 20px 24px;
    border-bottom: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    background: rgba(255, 255, 255, 0.02);
  }

  .modal-title {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text-main, #f8fafc);
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .icon {
    font-size: 1.3rem;
    flex-shrink: 0;
  }

  .btn-close {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    color: var(--text-muted, #94a3b8);
    cursor: pointer;
    border-radius: var(--radius-sm, 8px);
    transition: background-color 0.2s, color 0.2s;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .btn-close:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-main, #f8fafc);
  }

  .modal-body {
    flex: 1;
    min-height: 0;
    padding: 24px;
    overflow-y: auto;
    color: #cbd5e1;
    font-size: 0.95rem;
    line-height: 1.7;
  }

  .modal-body :global(h3) {
    color: var(--text-main, #f8fafc);
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
    color: var(--text-main, #f8fafc);
  }

  .modal-footer {
    padding: 16px 24px;
    border-top: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    background: var(--bg2, #12141c);
    display: flex;
    justify-content: flex-end;
  }

  .btn-primary {
    background: var(--gradient-main, linear-gradient(135deg, #6366f1, #a855f7));
    color: #ffffff;
    border: 1px solid transparent;
    padding: 10px 20px;
    min-height: 40px;
    border-radius: var(--radius-md, 12px);
    font-size: 0.95rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.2s;
  }

  .btn-primary:hover {
    opacity: 0.92;
    transform: translateY(-1px);
  }
</style>
