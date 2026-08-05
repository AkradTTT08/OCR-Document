<script>
  import { fade, scale } from 'svelte/transition';

  export let showModal = false;
  export let resultData = null;
  export let onClose = () => {};

  $: status = resultData?.status || 'PASSED';
  $: isPassed = status === 'PASSED';
  $: isConditional = status === 'CONDITIONAL_PASSED';
  $: isRejected = status === 'REJECTED';

  // Generate random particles for animations
  const particles = Array.from({ length: 24 }).map((_, i) => ({
    id: i,
    left: Math.random() * 92 + 4 + '%',
    delay: Math.random() * 2.5 + 's',
    duration: (Math.random() * 2 + 2.5) + 's',
    size: (Math.random() * 12 + 18) + 'px',
    rotation: (Math.random() * 360) + 'deg'
  }));

  const sideConfettiLeft = Array.from({ length: 18 }).map((_, i) => ({
    id: i,
    left: Math.random() * 25 + '%',
    delay: Math.random() * 1.5 + 's',
    duration: (Math.random() * 1.5 + 2) + 's',
    color: ['#10b981', '#6366f1', '#f59e0b', '#3b82f6', '#ec4899', '#8b5cf6'][i % 6]
  }));

  const sideConfettiRight = Array.from({ length: 18 }).map((_, i) => ({
    id: i,
    right: Math.random() * 25 + '%',
    delay: Math.random() * 1.5 + 's',
    duration: (Math.random() * 1.5 + 2) + 's',
    color: ['#10b981', '#6366f1', '#f59e0b', '#3b82f6', '#ec4899', '#8b5cf6'][i % 6]
  }));

  function handleBackdropClick() {
    onClose();
  }
</script>

{#if showModal && resultData}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="gate-modal-backdrop" in:fade={{ duration: 250 }} out:fade={{ duration: 200 }} on:click={handleBackdropClick}>
    
    <!-- Animation Particles Layer -->
    <div class="animation-container">
      {#if isPassed}
        <!-- Side Fireworks & Confetti Burst -->
        <div class="confetti-side-wrapper left-side">
          {#each sideConfettiLeft as p}
            <div 
              class="confetti-piece"
              style="left: {p.left}; animation-delay: {p.delay}; animation-duration: {p.duration}; background-color: {p.color};"
            ></div>
          {/each}
        </div>
        <div class="confetti-side-wrapper right-side">
          {#each sideConfettiRight as p}
            <div 
              class="confetti-piece"
              style="right: {p.right}; animation-delay: {p.delay}; animation-duration: {p.duration}; background-color: {p.color};"
            ></div>
          {/each}
        </div>
      {:else if isConditional}
        <!-- Raining Smileys & Stars -->
        {#each particles as p}
          <div 
            class="falling-smiley"
            style="left: {p.left}; animation-delay: {p.delay}; animation-duration: {p.duration}; font-size: {p.size}; transform: rotate({p.rotation});"
          >
            {p.id % 4 === 0 ? '😊' : p.id % 4 === 1 ? '✨' : p.id % 4 === 2 ? '⭐' : '👍'}
          </div>
        {/each}
      {:else if isRejected}
        <!-- Falling Red Crosses & Warning Signs -->
        {#each particles as p}
          <div 
            class="falling-cross"
            style="left: {p.left}; animation-delay: {p.delay}; animation-duration: {p.duration}; font-size: {p.size};"
          >
            {p.id % 3 === 0 ? '❌' : p.id % 3 === 1 ? '⚠️' : '🚫'}
          </div>
        {/each}
      {/if}
    </div>

    <!-- Glassmorphic Modal Box -->
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div 
      class="gate-modal-card status-{status.toLowerCase()}" 
      in:scale={{ start: 0.85, duration: 300 }} 
      out:scale={{ start: 0.95, duration: 150 }} 
      on:click|stopPropagation
    >
      <div class="modal-badge-wrapper">
        <div class="icon-ring">
          {#if isPassed}
            <span class="main-icon">🎉</span>
          {:else if isConditional}
            <span class="main-icon">😊</span>
          {:else}
            <span class="main-icon">❌</span>
          {/if}
        </div>
      </div>

      <div class="modal-body">
        <div class="gate-tag">Final Gate Assessment Rule</div>
        
        {#if isPassed}
          <h2 class="status-title text-passed">PASSED (ผ่านบริบูรณ์)</h2>
          <p class="status-subtitle">เอกสารผ่านเกณฑ์การประเมินมาตรฐานกลาง Exit Criteria ทั้งหมด 100%</p>
        {:else if isConditional}
          <h2 class="status-title text-conditional">CONDITIONAL PASSED (ผ่านแบบมีเงื่อนไข)</h2>
          <p class="status-subtitle">ผ่านเกณฑ์สาระสำคัญ (หมวด 1, 2, 4) สามารถส่ง Final Clean Copy ได้เลย</p>
        {:else}
          <h2 class="status-title text-rejected">REJECTED (ไม่ผ่าน - ต้องส่งตรวจใหม่)</h2>
          <p class="status-subtitle">พบข้อผิดพลาดในสาระสำคัญ (หมวด 1 หรือ หมวด 2) จำเป็นต้องแก้ไขและส่งตรวจใหม่</p>
        {/if}

        <div class="metrics-grid">
          <div class="metric-box">
            <span class="metric-val">{resultData.score_percentage || 100}%</span>
            <span class="metric-lbl">คะแนนสมบูรณ์</span>
          </div>
          <div class="metric-box green">
            <span class="metric-val">{resultData.passed_items || 0}</span>
            <span class="metric-lbl">ผ่าน (PASS)</span>
          </div>
          <div class="metric-box red">
            <span class="metric-val">{resultData.failed_items || 0}</span>
            <span class="metric-lbl">ไม่ผ่าน (FAIL)</span>
          </div>
          <div class="metric-box gray">
            <span class="metric-val">{resultData.na_items || 0}</span>
            <span class="metric-lbl">ข้าม (N/A)</span>
          </div>
        </div>

        {#if resultData.summary_remarks}
          <div class="remarks-box">
            📌 <strong>ข้อสรุปจากระบบ AI Auditor:</strong> {resultData.summary_remarks}
          </div>
        {/if}

        {#if resultData.failed_items > 0 && resultData.items}
          <div class="failed-preview-box">
            <div class="failed-header">⚠️ รายการข้อตรวจที่ไม่ผ่าน ({resultData.failed_items} ข้อ):</div>
            <div class="failed-list">
              {#each resultData.items.filter(i => i.status === 'FAIL') as fi}
                <div class="failed-item-row">
                  <span class="item-code badge-sev-{(fi.severity || 'major').toLowerCase()}">[{fi.item_code}]</span>
                  <span class="item-text">{fi.question_text}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <div class="modal-footer-btns">
          <button class="btn btn-close-modal" on:click={onClose}>
            ดูรายละเอียดผลการตรวจทั้งหมด
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .gate-modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(10, 15, 30, 0.78);
    backdrop-filter: blur(16px);
    z-index: 9999;
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
  }

  .animation-container {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 10000;
  }

  /* Confetti Side Fireworks Animation */
  .confetti-side-wrapper {
    position: absolute;
    bottom: 0;
    width: 300px;
    height: 100%;
  }

  .confetti-side-wrapper.left-side { left: 0; }
  .confetti-side-wrapper.right-side { right: 0; }

  .confetti-piece {
    position: absolute;
    bottom: -20px;
    width: 10px;
    height: 14px;
    border-radius: 3px;
    animation: shootUpConfetti linear infinite;
  }

  @keyframes shootUpConfetti {
    0% {
      transform: translateY(0) rotate(0deg) scale(1);
      opacity: 1;
    }
    50% {
      opacity: 0.9;
    }
    100% {
      transform: translateY(-95vh) rotate(720deg) scale(0.6);
      opacity: 0;
    }
  }

  /* Raining Smileys Animation */
  .falling-smiley {
    position: absolute;
    top: -40px;
    animation: rainSmiley linear infinite;
    user-select: none;
  }

  @keyframes rainSmiley {
    0% {
      transform: translateY(0) rotate(0deg);
      opacity: 1;
    }
    100% {
      transform: translateY(105vh) rotate(360deg);
      opacity: 0.2;
    }
  }

  /* Falling Red Crosses Animation */
  .falling-cross {
    position: absolute;
    top: -40px;
    animation: rainCross ease-in infinite;
    user-select: none;
    filter: drop-shadow(0 0 6px rgba(239, 68, 68, 0.8));
  }

  @keyframes rainCross {
    0% {
      transform: translateY(0) scale(0.8) rotate(-10deg);
      opacity: 1;
    }
    50% {
      transform: translateY(50vh) scale(1.1) rotate(15deg);
    }
    100% {
      transform: translateY(105vh) scale(0.9) rotate(-20deg);
      opacity: 0.1;
    }
  }

  /* Modal Container Card */
  .gate-modal-card {
    position: relative;
    width: 90%;
    max-width: 520px;
    background: rgba(15, 23, 42, 0.92);
    border-radius: 24px;
    padding: 32px 28px 24px 28px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.7), 0 0 40px rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.15);
    z-index: 10001;
    text-align: center;
    color: #ffffff;
  }

  .gate-modal-card.status-passed {
    border-color: rgba(16, 185, 129, 0.4);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(16, 185, 129, 0.25);
  }

  .gate-modal-card.status-conditional_passed {
    border-color: rgba(245, 158, 11, 0.4);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(245, 158, 11, 0.25);
  }

  .gate-modal-card.status-rejected {
    border-color: rgba(239, 68, 68, 0.4);
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8), 0 0 40px rgba(239, 68, 68, 0.25);
  }

  .modal-badge-wrapper {
    position: absolute;
    top: -42px;
    left: 50%;
    transform: translateX(-50%);
  }

  .icon-ring {
    width: 84px;
    height: 84px;
    border-radius: 50%;
    background: #0f172a;
    border: 3px solid rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  }

  .status-passed .icon-ring { border-color: #10b981; background: #064e3b; }
  .status-conditional_passed .icon-ring { border-color: #f59e0b; background: #78350f; }
  .status-rejected .icon-ring { border-color: #ef4444; background: #7f1d1d; }

  .main-icon {
    font-size: 2.5rem;
  }

  .modal-body {
    margin-top: 24px;
  }

  .gate-tag {
    display: inline-block;
    padding: 3px 12px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #94a3b8;
    margin-bottom: 8px;
  }

  .status-title {
    margin: 4px 0 8px 0;
    font-size: 1.35rem;
    font-weight: 700;
  }

  .text-passed { color: #34d399; }
  .text-conditional { color: #fbbf24; }
  .text-rejected { color: #f87171; }

  .status-subtitle {
    margin: 0 0 20px 0;
    font-size: 0.88rem;
    color: #cbd5e1;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 16px;
  }

  .metric-box {
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 10px 6px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .metric-box.green { background: rgba(16, 185, 129, 0.15); border-color: rgba(16, 185, 129, 0.3); }
  .metric-box.red { background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.3); }
  .metric-box.gray { background: rgba(148, 163, 184, 0.15); border-color: rgba(148, 163, 184, 0.3); }

  .metric-val {
    font-size: 1.1rem;
    font-weight: 700;
  }

  .metric-lbl {
    font-size: 0.7rem;
    color: #94a3b8;
    margin-top: 2px;
  }

  .remarks-box {
    background: rgba(30, 41, 59, 0.6);
    border-left: 3px solid #6366f1;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 0.82rem;
    color: #e2e8f0;
    text-align: left;
    margin-bottom: 16px;
    line-height: 1.4;
  }

  .failed-preview-box {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    margin-bottom: 16px;
    max-height: 110px;
    overflow-y: auto;
  }

  .failed-header {
    font-size: 0.78rem;
    font-weight: 700;
    color: #f87171;
    margin-bottom: 6px;
  }

  .failed-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .failed-item-row {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.78rem;
    color: #cbd5e1;
  }

  .item-code {
    font-weight: bold;
    color: #ef4444;
  }

  .modal-footer-btns {
    margin-top: 12px;
  }

  .btn-close-modal {
    width: 100%;
    padding: 12px 20px;
    border-radius: 12px;
    border: none;
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    color: #ffffff;
    font-size: 0.92rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
    transition: all 0.2s ease;
  }

  .btn-close-modal:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.5);
  }
</style>
