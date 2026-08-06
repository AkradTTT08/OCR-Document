<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { fade, fly, scale } from 'svelte/transition';

  export let userRole = 'admin'; // 'admin' | 'user'

  const dispatch = createEventDispatcher();

  // ── Tutorial Steps ──────────────────────────────────────────────
  const adminSteps = [
    {
      id: 'welcome',
      title: '👋 ยินดีต้อนรับสู่ Spectra QA',
      subtitle: 'Intelligent Document Analysis System',
      description: 'ระบบนี้ช่วยให้คุณสามารถ scan เอกสาร PDF, ตรวจสอบคุณภาพด้วย AI, จัดการ Knowledge Base และควบคุมมาตรฐานการตรวจเอกสารได้ครบวงจร\n\nมาเรียนรู้การใช้งานแต่ละเมนูกันเลย!',
      icon: '🚀',
      target: null,
      role: 'admin',
      color: '#6366f1',
    },
    {
      id: 'scan_ocr',
      title: '📄 Scan OCR',
      subtitle: 'Menu: Scan OCR (Admin)',
      description: '**อัปโหลดและวิเคราะห์เอกสาร PDF**\n\n✅ อัปโหลดไฟล์ PDF ขนาดสูงสุด 50MB\n✅ ระบบทำ OCR แปลงรูปเป็นข้อความอัตโนมัติ\n✅ ตรวจสอบคำผิด (Spell Check) ภาษาไทย-อังกฤษ\n✅ AI วิเคราะห์คุณภาพเอกสารและออก Audit Report\n✅ บันทึกผลลง Knowledge Base อัตโนมัติ',
      icon: '🔍',
      target: 'nav-ocr',
      role: 'admin',
      color: '#6366f1',
    },
    {
      id: 'knowledge_base',
      title: '📚 Knowledge Base',
      subtitle: 'Menu: Knowledge Base (Admin)',
      description: '**คลังเก็บเอกสารและข้อมูลทั้งหมด**\n\n✅ ดูเอกสารทั้งหมดที่ผ่านการ scan แล้ว\n✅ ค้นหาเชิงความหมาย (Semantic Search) ด้วย Vector DB\n✅ ดูรายละเอียด Chunk ของแต่ละเอกสาร\n✅ กรองตาม Project และประเภทเอกสาร\n✅ ใช้เป็นข้อมูลฐานให้ AI Agent ตอบคำถาม',
      icon: '📚',
      target: 'nav-kb',
      role: 'admin',
      color: '#8b5cf6',
    },
    {
      id: 'ai_skills',
      title: '⚡ AI Skills',
      subtitle: 'Menu: AI Skills (Admin)',
      description: '**จัดการความสามารถ AI Agent**\n\n✅ สร้าง Skill ใหม่ด้วย Markdown Instructions\n✅ กำหนด Target Document Type สำหรับแต่ละ Skill\n✅ เปิด/ปิด Skill ที่ต้องการให้ AI ใช้\n✅ ดู Exit Criteria Skill ที่ sync จากระบบอัตโนมัติ\n✅ ควบคุม AI Behavior ผ่าน Skill versioning',
      icon: '⚡',
      target: 'nav-skills',
      role: 'admin',
      color: '#f59e0b',
    },
    {
      id: 'qa_member',
      title: '👥 QA Member',
      subtitle: 'Menu: QA Member (Admin)',
      description: '**จัดการทีมผู้ใช้งาน**\n\n✅ เพิ่ม/แก้ไข/ลบ User ในระบบ\n✅ กำหนด Role: Admin หรือ User\n✅ เปิด/ปิดการใช้งานบัญชี\n✅ ดูสถิติ Login Count และ Last Login\n✅ อัปโหลดรูป Avatar ของแต่ละ User',
      icon: '👥',
      target: 'nav-qa-member',
      role: 'admin',
      color: '#10b981',
    },
    {
      id: 'exit_criteria',
      title: '✅ Exit Criteria',
      subtitle: 'Menu: Exit Criteria (Admin)',
      description: '**มาตรฐานการตรวจรับเอกสาร**\n\n✅ จัดการ Template เกณฑ์การผ่าน (13 ข้อมาตรฐานสากล)\n✅ แบ่งเป็น 4 หมวด: Defect Resolution, Content Accuracy, Format, Governance\n✅ ระบบ AI จะประเมินเอกสารตามเกณฑ์เหล่านี้อัตโนมัติ\n✅ กำหนด Severity: Critical / Major / Minor\n✅ ผล Gate: PASSED / CONDITIONAL PASSED / REJECTED',
      icon: '✅',
      target: 'nav-exit-criteria',
      role: 'admin',
      color: '#ef4444',
    },
    {
      id: 'admin_profile',
      title: '👤 Profile & Settings',
      subtitle: 'Topbar: User Menu (Admin)',
      description: '**จัดการข้อมูลส่วนตัว**\n\n✅ คลิกรูป Avatar มุมบนขวาเพื่อเปิดเมนู\n✅ แก้ไข Display Name\n✅ เปลี่ยน Password\n✅ อัปโหลดรูปโปรไฟล์\n✅ Logout ออกจากระบบ',
      icon: '👤',
      target: null,
      role: 'admin',
      color: '#6366f1',
    },
    {
      id: 'admin_done',
      title: '🎉 พร้อมใช้งานแล้ว!',
      subtitle: 'Admin Mode — All Systems Go',
      description: 'คุณได้เรียนรู้ทุกฟีเจอร์ของ **Admin** ครบแล้ว!\n\n**สรุป Workflow ที่แนะนำ:**\n1. สร้าง Project ใน QA Consult\n2. Upload PDF ใน Scan OCR\n3. AI วิเคราะห์และบันทึกใน Knowledge Base\n4. ตรวจสอบ Exit Criteria ผ่าน/ไม่ผ่าน\n5. Export Report ให้ทีม\n\n🚀 เริ่มใช้งานได้เลย!',
      icon: '🎉',
      target: null,
      role: 'admin',
      color: '#10b981',
    },
  ];

  const userSteps = [
    {
      id: 'welcome_user',
      title: '👋 ยินดีต้อนรับสู่ Spectra QA',
      subtitle: 'QA Document Review Portal',
      description: 'ระบบนี้ช่วยให้คุณสามารถ **ส่งเอกสารเพื่อตรวจสอบคุณภาพ** และ **ดูผลการวิเคราะห์ AI** ได้อย่างสะดวกและรวดเร็ว\n\nมาเรียนรู้การใช้งานกันเลย!',
      icon: '🚀',
      target: null,
      role: 'user',
      color: '#8b5cf6',
    },
    {
      id: 'qa_consult_project',
      title: '📁 เลือก Project',
      subtitle: 'QA Consult — Step 1: Select Project',
      description: '**เลือกโครงการที่ต้องการส่งเอกสาร**\n\n✅ เลือก Project จาก Dropdown ด้านบน\n✅ กด "+ New Project" เพื่อสร้างโปรเจกต์ใหม่\n✅ เลือก Group Type: Project Plan / SRS / SDD / UAT / Test Case\n✅ ตั้งชื่อ Group สำหรับรอบการตรวจสอบนี้\n\n💡 ทุก Group จะปรากฏใน Sidebar ด้านซ้ายสำหรับเข้าถึงได้ง่าย',
      icon: '📁',
      target: 'nav-qa-consult',
      role: 'user',
      color: '#8b5cf6',
    },
    {
      id: 'qa_consult_upload',
      title: '📤 อัปโหลดเอกสาร',
      subtitle: 'QA Consult — Step 2: Upload Document',
      description: '**ส่งไฟล์ PDF เพื่อให้ AI ตรวจสอบ**\n\n✅ ลากและวางไฟล์ PDF หรือคลิกเพื่อเลือก\n✅ ขนาดสูงสุด 50MB ต่อไฟล์\n✅ รองรับเฉพาะไฟล์ PDF\n✅ AI จะเริ่ม Scan และวิเคราะห์อัตโนมัติทันที\n✅ แสดง Progress Bar ระหว่างประมวลผล',
      icon: '📤',
      target: 'nav-qa-consult',
      role: 'user',
      color: '#6366f1',
    },
    {
      id: 'qa_consult_result',
      title: '📊 ดูผลการวิเคราะห์',
      subtitle: 'QA Consult — Step 3: View Results',
      description: '**AI สรุปผลการตรวจสอบครบทุกด้าน**\n\n✅ **Audit Report** — สรุปผลการตรวจสอบโดย AI\n✅ **Exit Criteria** — ผ่าน/ไม่ผ่านแต่ละเกณฑ์ (13 ข้อ)\n✅ **Spell Check** — รายการคำผิดพร้อมคำแนะนำ\n✅ **สถานะ Gate**: PASSED / CONDITIONAL PASSED / REJECTED\n✅ **Download Excel Report** ส่งให้ทีม',
      icon: '📊',
      target: 'nav-qa-consult',
      role: 'user',
      color: '#10b981',
    },
    {
      id: 'qa_consult_history',
      title: '📜 ประวัติการตรวจสอบ',
      subtitle: 'QA Consult — Sidebar History',
      description: '**เข้าถึงประวัติได้จาก Sidebar ซ้าย**\n\n✅ ดู Groups ทั้งหมดที่สร้างไว้\n✅ คลิก Group เพื่อดูเอกสารในรอบนั้น\n✅ ดูประวัติการ scan แต่ละไฟล์\n✅ กลับมาดูผล Audit Report ได้ตลอด\n✅ เรียงตาม Project ที่เลือก',
      icon: '📜',
      target: null,
      role: 'user',
      color: '#f59e0b',
    },
    {
      id: 'user_done',
      title: '🎉 พร้อมใช้งานแล้ว!',
      subtitle: 'User Mode — Ready to Review',
      description: 'คุณได้เรียนรู้การใช้งาน **QA Consult** ครบแล้ว!\n\n**Workflow ง่ายๆ 3 ขั้นตอน:**\n1. 📁 เลือก Project และตั้งชื่อ Group\n2. 📤 อัปโหลดไฟล์ PDF\n3. 📊 ดูผล AI Audit Report\n\n✅ ดาวน์โหลด Excel Report\n✅ ดูประวัติจาก Sidebar\n\n🚀 เริ่มส่งเอกสารได้เลย!',
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
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
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

  <!-- ── Tutorial Card (always mounted, no flicker) ── -->
  <div
    class="tutorial-card"
    in:fly={{ y: 40, duration: 300 }}
    style="--step-color: {step.color};"
  >
    <!-- Header: icon + close (CSS transition on color/bg) -->
    <div class="tc-header">
      <div class="tc-badge">
        {#key currentStep}
          <span class="tc-icon" in:fade={{ duration: 200 }}>{step.icon}</span>
        {/key}
      </div>
      <button class="tc-close" on:click={close} title="ปิด (Esc)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>

    <!-- Role Tag -->
    <div class="tc-role-tag">
      {userRole === 'admin' ? '🛡 Admin' : '👤 User'} — Step {currentStep + 1} / {steps.length}
    </div>

    <!-- Content area: fade only this block on step change -->
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

    <!-- Progress Bar (always visible, smooth width transition via CSS) -->
    <div class="tc-progress-wrap">
      <div class="tc-progress-bar">
        <div class="tc-progress-fill" style="width: {progress}%;"></div>
      </div>
      <span class="tc-progress-label">{Math.round(progress)}%</span>
    </div>

    <!-- Step Dots -->
    <div class="tc-dots">
      {#each steps as _, i}
        <button
          class="tc-dot"
          class:active={i === currentStep}
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
        <button class="tc-btn tc-btn-primary" on:click={close}>
          🎉 เริ่มใช้งาน!
        </button>
      {:else}
        <button class="tc-btn tc-btn-primary" on:click={next}>
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
    background: rgba(5, 7, 15, 0.75);
    backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .tutorial-card {
    background: linear-gradient(145deg, rgba(18, 20, 35, 0.98), rgba(25, 27, 45, 0.98));
    border: 1px solid rgba(255,255,255,0.08);
    border-top: 2px solid var(--step-color, #6366f1);
    border-radius: 20px;
    padding: 32px;
    width: 100%;
    max-width: 520px;
    box-shadow:
      0 30px 80px rgba(0,0,0,0.6),
      0 0 0 1px rgba(255,255,255,0.04),
      inset 0 1px 0 rgba(255,255,255,0.06);
    position: relative;
    overflow: hidden;
    transition: border-color 0.4s ease;
  }

  .tutorial-card::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 180px; height: 180px;
    background: radial-gradient(circle, var(--step-color, #6366f1) 0%, transparent 70%);
    opacity: 0.08;
    pointer-events: none;
    border-radius: 50%;
    transition: background 0.4s;
  }

  /* Header */
  .tc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .tc-badge {
    width: 52px; height: 52px;
    border-radius: 14px;
    background: color-mix(in srgb, var(--step-color, #6366f1) 15%, transparent);
    border: 1px solid color-mix(in srgb, var(--step-color, #6366f1) 35%, transparent);
    display: flex; align-items: center; justify-content: center;
    transition: background 0.4s ease, border-color 0.4s ease;
  }
  .tc-icon { font-size: 26px; line-height: 1; display: block; }

  .tc-close {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    color: rgba(255,255,255,0.4);
    border-radius: 50%;
    width: 34px; height: 34px;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  .tc-close:hover {
    background: rgba(244, 63, 94, 0.15);
    border-color: rgba(244, 63, 94, 0.3);
    color: #f43f5e;
    transform: rotate(90deg);
  }

  /* Role tag */
  .tc-role-tag {
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid color-mix(in srgb, var(--step-color, #6366f1) 30%, transparent);
    background: color-mix(in srgb, var(--step-color, #6366f1) 12%, transparent);
    color: var(--step-color, #6366f1);
    margin-bottom: 12px;
    font-family: 'Inter', sans-serif;
    transition: all 0.4s ease;
  }

  /* Title */
  .tc-title {
    font-size: 22px;
    font-weight: 700;
    color: #fff;
    margin: 0 0 4px;
    line-height: 1.3;
    font-family: 'Inter', 'Noto Sans Thai', sans-serif;
  }
  .tc-subtitle {
    font-size: 13px;
    color: rgba(255,255,255,0.4);
    margin: 0 0 16px;
    font-family: 'Inter', sans-serif;
  }

  /* Divider */
  .tc-divider {
    height: 1px;
    width: 100%;
    margin-bottom: 16px;
    opacity: 0.4;
    background: linear-gradient(90deg, var(--step-color, #6366f1), transparent);
    transition: background 0.4s ease;
  }

  /* Content area wrapper */
  .tc-content {
    min-height: 195px;
  }

  /* Body */
  .tc-body {
    font-size: 14px;
    line-height: 1.8;
    color: rgba(255,255,255,0.7);
    font-family: 'Noto Sans Thai', 'Inter', sans-serif;
    min-height: 120px;
  }
  .tc-body :global(strong) {
    color: #fff;
    font-weight: 600;
  }

  /* Progress */
  .tc-progress-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 20px 0 14px;
  }
  .tc-progress-bar {
    flex: 1;
    height: 4px;
    background: rgba(255,255,255,0.08);
    border-radius: 99px;
    overflow: hidden;
  }
  .tc-progress-fill {
    height: 100%;
    border-radius: 99px;
    background: var(--step-color, #6366f1);
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1), background 0.4s ease;
  }
  .tc-progress-label {
    font-size: 11px;
    color: rgba(255,255,255,0.3);
    font-family: 'Inter', monospace;
    min-width: 30px;
    text-align: right;
  }

  /* Dots */
  .tc-dots {
    display: flex;
    gap: 6px;
    justify-content: center;
    margin-bottom: 20px;
  }
  .tc-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: rgba(255,255,255,0.15);
    border: none;
    cursor: pointer;
    transition: all 0.3s;
    padding: 0;
  }
  .tc-dot:hover { background: rgba(255,255,255,0.35); transform: scale(1.2); }
  .tc-dot.active {
    width: 22px;
    border-radius: 4px;
    background: var(--step-color, #6366f1);
    box-shadow: 0 0 8px color-mix(in srgb, var(--step-color, #6366f1) 60%, transparent);
    transition: width 0.3s ease, background 0.4s ease;
  }

  /* Actions */
  .tc-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .tc-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    border-radius: 10px;
    border: none;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    font-family: 'Noto Sans Thai', 'Inter', sans-serif;
  }
  .tc-btn-primary {
    color: #fff;
    background: var(--step-color, #6366f1);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    transition: filter 0.2s, transform 0.2s, box-shadow 0.2s, background 0.4s ease;
  }
  .tc-btn-primary:hover {
    filter: brightness(1.15);
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.4);
  }
  .tc-btn-secondary {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    color: rgba(255,255,255,0.6);
  }
  .tc-btn-secondary:hover {
    background: rgba(255,255,255,0.1);
    color: #fff;
  }

  /* Hint */
  .tc-hint {
    text-align: center;
    font-size: 11px;
    color: rgba(255,255,255,0.2);
    margin: 14px 0 0;
    font-family: 'Inter', monospace;
  }
</style>
