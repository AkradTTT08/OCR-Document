<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import DictStats from './DictStats.svelte';
  import FormatRules from './FormatRules.svelte';
  import { toast } from './toastStore.js';
  const dispatch = createEventDispatcher();

  const API = 'http://localhost:5000/api';

  // ── State ──
  /** @type {any} */
  let file = null;
  let isDragging = false;
  let lang = 'tha+eng';
  let dpi = '300';
  let autoSpellCheck = false;

  // ── File ──
  /** @param {any} e */
  function onDrop(e) {
    e.preventDefault();
    isDragging = false;
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  }
  /** @param {any} e */
  function onFileChange(e) {
    const f = e.target.files[0];
    if (f) setFile(f);
  }
  /** @param {any} f */
  function setFile(f) {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      toast('รองรับเฉพาะไฟล์ PDF เท่านั้น', 'warning');
      return;
    }
    if (f.size > 50 * 1024 * 1024) {
      toast('ไฟล์ใหญ่เกิน 50 MB กรุณาเลือกไฟล์ที่เล็กกว่า', 'warning');
      return;
    }
    file = f;
    toast(`โหลดไฟล์ "${f.name}" สำเร็จ`, 'success', 2500);
  }
  function removeFile() { file = null; }

  /** @param {number} b */
  function formatBytes(b) {
    if (b < 1024) return `${b} B`;
    if (b < 1048576) return `${(b/1024).toFixed(1)} KB`;
    return `${(b/1048576).toFixed(1)} MB`;
  }

  // ── Process ──
  async function process() {
    if (!file) return;

    /**
     * @param {number} pct
     * @param {string} label
     * @param {number} step
     */
    const emitProgress = (pct, label, step) =>
      dispatch('processing', { active: true, progress: { pct, label, step } });

    const formData = new FormData();
    formData.append('file', file);

    try {
      emitProgress(5, 'เริ่มต้น...', 1);
      
      const res = await fetch(`${API}/process_stream?lang=${lang}&dpi=${dpi}&auto_spellcheck=${autoSpellCheck}`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'เกิดข้อผิดพลาด');
      }

      if (!res.body) {
        throw new Error('ไม่สามารถเชื่อมต่อข้อมูลสตรีมแบบเรียลไทม์ได้ (Response body is null)');
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let pages = [];
      let finalData = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() ?? ''; // keep last chunk

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.substring(6));
            
            if (data.type === 'start') {
              emitProgress(10, 'แปลง PDF เป็นรูปภาพ...', 1);
            }
            else if (data.type === 'progress') {
              const completed = data.page || 0;
              const total = data.total || 0;
              const elapsed = data.elapsed || 0;
              
              let pct = 10;
              let label = 'กำลังสกัดหน้า...';
              
              if (total > 0) {
                pct = 10 + Math.floor((completed / total) * 70);
                
                if (completed > 0) {
                  const timePerPage = elapsed / completed;
                  const remaining = total - completed;
                  const etaSeconds = Math.round(timePerPage * remaining);
                  
                  let etaText = '';
                  if (etaSeconds < 60) {
                    etaText = `${etaSeconds} วินาที`;
                  } else if (etaSeconds < 3600) {
                    const mins = Math.floor(etaSeconds / 60);
                    const secs = etaSeconds % 60;
                    etaText = `${mins} นาที ${secs} วินาที`;
                  } else {
                    const hrs = Math.floor(etaSeconds / 3600);
                    const mins = Math.floor((etaSeconds % 3600) / 60);
                    etaText = `${hrs} ชั่วโมง ${mins} นาที`;
                  }
                  
                  label = `กำลังสกัดหน้า ${completed}/${total} (ใช้เวลาไปแล้ว ${Math.round(elapsed)}s, คาดว่าจะเสร็จในอีกประมาณ ${etaText})...`;
                } else {
                  label = `กำลังสกัดหน้า ${completed}/${total} (กำลังโหลดหน้าแรก)...`;
                }
              } else {
                label = `กำลังโหลดโมเดลสแกนหน้า... (${Math.round(elapsed)}s)`;
              }
              
              emitProgress(pct, label, 2);
            }
            else if (data.type === 'page_result') {
              pages.push(data.page);
            }
            else if (data.type === 'complete') {
              finalData = data;
              finalData.pages = pages;
              finalData.filename = file.name;
              finalData.success = true;
            }
            else if (data.type === 'error') {
              throw new Error(data.message);
            }
          }
        }
      }

      if (finalData) {
        emitProgress(100, 'เสร็จสิ้น!', 3);
        await sleep(300);
        dispatch('result', finalData);
        dispatch('processing', { active: false, progress: { pct: 100, label: '', step: 3 } });
      } else if (pages.length > 0) {
        // แสดงผลบางส่วนที่ได้มาแม้ว่า stream จะจบโดยไม่มี complete event
        emitProgress(100, 'เสร็จสิ้น (บางส่วน)', 3);
        await sleep(300);
        dispatch('result', {
          pages,
          filename: file.name,
          success: true,
          summary: { total_pages: pages.length },
          total_pages: pages.length
        });
        dispatch('processing', { active: false, progress: { pct: 100, label: '', step: 3 } });
        toast('ประมวลผลเสร็จ (บางหน้าอาจไม่สมบูรณ์)', 'warning', 4000);
      }

    } catch (err) {
      dispatch('processing', { active: false, progress: { pct: 0, label: '', step: 0 } });
      const msg = err instanceof Error ? err.message : String(err);
      console.error("PROCESS ERROR:", err);
      toast(`ข้อผิดพลาด: ${msg}`, "error", 6000);
    }
  }

  /** @param {number} ms */
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
</script>

<!-- Layout Container -->
<div class="upload-container">
  
  <!-- Header Text -->
  <div class="header-section">
    <h1 class="main-title">ยินดีต้อนรับสู่ศูนย์วิเคราะห์เอกสารอัจฉริยะ</h1>
    <p class="sub-title">
      สัมผัสประสบการณ์การวิเคราะห์ข้อมูลเชิงลึกด้วยระบบ AI ที่มีความแม่นยำสูง 
      เปลี่ยนเอกสาร<br />ทึบให้เป็นข้อมูลที่มีโครงสร้างในพริบตา
    </p>
  </div>

  <!-- Main Grid -->
  <div class="content-grid">
    
    <!-- Left: Dropzone -->
    <div class="left-col">
      <div
        class="upload-area"
        role="button"
        tabindex="0"
        on:dragover|preventDefault={() => (isDragging = true)}
        on:dragleave={() => (isDragging = false)}
        on:drop={onDrop}
        on:click={() => !file && document.getElementById("fileInput")?.click()}
        on:keydown={(e) =>
          e.key === "Enter" && !file && document.getElementById("fileInput")?.click()}
        class:dragging={isDragging}
        class:has-file={!!file}
      >
        {#if !file}
          <div class="drop-icon-box" class:bounce={isDragging}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="12" y1="18" x2="12" y2="12"></line>
              <polyline points="9 15 12 12 15 15"></polyline>
            </svg>
          </div>
          <p class="drop-title">ลากไฟล์ PDF มาวางที่นี่</p>
          <p class="drop-hint">
            หรือ <span class="link-text">เลือกไฟล์จากเครื่อง</span> (สูงสุด 50 MB)
          </p>
          
          <div class="file-types">
            <span class="file-pill">.pdf</span>
            <span class="file-pill">.docx</span>
            <span class="file-pill">.png</span>
          </div>

          <input
            id="fileInput"
            type="file"
            accept=".pdf"
            hidden
            on:change={onFileChange}
          />
        {:else}
          <div class="file-card">
            <div class="file-icon-wrap">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                width="24"
                height="24"
              >
                <path
                  d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <div class="file-info">
              <span class="file-name truncate">{file.name}</span>
              <span class="file-size">{formatBytes(file.size)}</span>
            </div>
            <button
              class="btn-remove"
              on:click|stopPropagation={removeFile}
              title="ลบ">✕</button
            >
          </div>
        {/if}
      </div>
    </div>

    <!-- Right: Settings & Actions -->
    <div class="right-col">
      <div class="settings-card">
        <h3 class="settings-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3a9 9 0 0 0-9 9c0 4.97 4.03 9 9 9s9-4.03 9-9-4.03-9-9-9z"/><path d="M12 8v4l3 3"/></svg>
          OCR Settings
        </h3>
        
        <div class="settings-block">
          <div class="setting-row">
            <label class="setting-label" for="sel-lang">ภาษา OCR</label>
            <select id="sel-lang" bind:value={lang}>
              <option value="tha+eng">ไทย + อังกฤษ</option>
              <option value="tha">ไทยเท่านั้น</option>
              <option value="eng">อังกฤษเท่านั้น</option>
            </select>
          </div>
          <div class="setting-row">
            <label class="setting-label" for="sel-dpi">ความละเอียด</label>
            <select id="sel-dpi" bind:value={dpi}>
              <option value="200">200 DPI (เร็ว)</option>
              <option value="300">300 DPI (แนะนำ)</option>
              <option value="400">400 DPI (ละเอียด)</option>
            </select>
          </div>
          <div class="setting-row toggle-row">
            <div class="toggle-text">
              <span class="setting-label">โหมด Auto ตรวจคำผิด</span>
              <span class="setting-hint">ปรับแก้คำผิดอัตโนมัติด้วย AI</span>
            </div>
            <label class="toggle-wrap">
              <input type="checkbox" bind:checked={autoSpellCheck} />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </label>
          </div>
        </div>

        <!-- Process Button -->
        <div class="btn-wrap">
          <button type="button" class="btn-process-large" on:click={process} disabled={!file}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
              <polyline points="7.5 4.21 12 6.81 16.5 4.21"></polyline>
              <polyline points="7.5 19.79 7.5 14.6 3 12"></polyline>
              <polyline points="21 12 16.5 14.6 16.5 19.79"></polyline>
              <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
              <line x1="12" y1="22.08" x2="12" y2="12"></line>
            </svg>
            ประมวลผล OCR + ตรวจคำ
          </button>
        </div>
      </div>

      <!-- Stats Row -->
      <div class="stats-row">
        <DictStats />
        <FormatRules />
      </div>
    </div>
  </div>
</div>

<style>
  /* ── Main Layout ── */
  .upload-container {
    display: flex;
    flex-direction: column;
    gap: 24px;
    align-items: center;
    justify-content: center;
    max-width: 1000px;
    margin: 0 auto;
    width: 100%;
    height: 100%;
    padding: 10px 0;
  }

  /* ── Header ── */
  .header-section {
    text-align: center;
    max-width: 800px;
  }
  .main-title {
    font-size: 32px;
    font-weight: 700;
    color: var(--text-main);
    margin-bottom: 16px;
    font-family: var(--font-en);
    letter-spacing: -0.5px;
  }
  .sub-title {
    font-size: 15px;
    color: var(--text-dim);
    line-height: 1.6;
    font-family: var(--font-th);
  }

  /* ── Content Grid ── */
  .content-grid {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 32px;
    width: 100%;
  }

  /* ── Upload area ── */
  .upload-area {
    background: linear-gradient(135deg, #7484a0, #61738c);
    border: 2px dashed rgba(255,255,255,0.2);
    border-radius: 24px;
    padding: 60px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    height: 100%;
    min-height: 300px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    position: relative;
    overflow: hidden;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.1);
  }
  
  .upload-area:hover,
  .upload-area.dragging {
    border-color: rgba(255,255,255,0.5);
    background: linear-gradient(135deg, #7f8fae, #687a96);
    box-shadow: inset 0 0 30px rgba(0,0,0,0.15), 0 10px 30px rgba(0,0,0,0.2);
    transform: translateY(-2px);
  }

  .upload-area.has-file {
    border: 1px solid var(--glass-border);
    padding: 20px;
    cursor: default;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
  }

  .drop-icon-box {
    width: 80px;
    height: 80px;
    background: rgba(30, 41, 59, 0.6);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    margin-bottom: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    transition: transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .drop-icon-box svg {
    width: 32px;
    height: 32px;
  }
  .drop-icon-box.bounce {
    transform: translateY(-10px) scale(1.1);
  }

  .drop-title {
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    margin: 0;
    font-family: var(--font-en);
    text-shadow: 0 2px 4px rgba(0,0,0,0.2);
  }
  .drop-hint {
    font-size: 14px;
    color: rgba(255,255,255,0.8);
    margin: 0 0 16px;
    font-family: var(--font-th);
  }
  .link-text {
    color: #fff;
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  
  .file-types {
    display: flex;
    gap: 8px;
  }
  .file-pill {
    background: rgba(0, 0, 0, 0.2);
    color: rgba(255,255,255,0.7);
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
  }

  /* File Card */
  .file-card {
    display: flex;
    align-items: center;
    background: rgba(30, 41, 59, 0.8);
    padding: 16px 20px;
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    width: 90%;
    max-width: 400px;
  }
  .file-icon-wrap {
    width: 44px;
    height: 44px;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    margin-right: 16px;
    flex-shrink: 0;
  }
  .file-info {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    text-align: left;
  }
  .file-name {
    font-size: 15px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 4px;
  }
  .file-size {
    font-size: 13px;
    color: var(--text-dim);
  }
  .btn-remove {
    background: rgba(239, 68, 68, 0.1);
    color: #f87171;
    border: none;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }
  .btn-remove:hover {
    background: #ef4444;
    color: white;
  }

  /* ── Right Column: Settings Card ── */
  .right-col {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .settings-card {
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: 24px;
    padding: 32px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    flex: 1;
  }
  .settings-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    margin: 0 0 24px 0;
    font-family: var(--font-en);
  }
  .settings-title svg {
    color: #60a5fa;
  }

  .settings-block {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-bottom: 32px;
  }
  .setting-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .toggle-row {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    background: rgba(255,255,255,0.03);
    padding: 12px 16px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.05);
  }
  .toggle-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .setting-label {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-main);
    font-family: var(--font-th);
  }
  .setting-hint {
    font-size: 12px;
    color: var(--text-dim);
    font-family: var(--font-th);
  }
  
  select {
    width: 100%;
    padding: 12px 16px;
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(15, 23, 42, 0.6);
    color: #fff;
    font-size: 14px;
    font-family: var(--font-th);
    outline: none;
    appearance: none;
    cursor: pointer;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 16px center;
    background-size: 16px;
  }
  select:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }

  /* Toggle Switch */
  .toggle-wrap {
    display: flex;
    align-items: center;
    cursor: pointer;
  }
  .toggle-wrap input {
    display: none;
  }
  .toggle-track {
    width: 44px;
    height: 24px;
    border-radius: 12px;
    background: rgba(255,255,255,0.1);
    position: relative;
    transition: all 0.3s ease;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: #fff;
    box-shadow: 0 0 10px rgba(255,255,255,0.5);
  }
  .toggle-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #94a3b8;
    position: absolute;
    top: 3px;
    left: 3px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb {
    transform: translateX(20px);
    background: #8b5cf6;
  }

  /* Process Button */
  .btn-wrap {
    display: flex;
    width: 100%;
    margin-top: auto;
  }
  .btn-process-large {
    width: 100%;
    padding: 16px;
    border-radius: 16px;
    border: none;
    background: linear-gradient(90deg, #6366f1, #d946ef);
    color: white;
    font-size: 18px;
    font-weight: 700;
    font-family: var(--font-en);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    box-shadow: 0 10px 20px rgba(217, 70, 239, 0.3);
    transition: all 0.3s;
  }
  .btn-process-large:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 14px 28px rgba(217, 70, 239, 0.4);
  }
  .btn-process-large:disabled {
    background: rgba(255,255,255,0.05);
    color: rgba(255,255,255,0.3);
    box-shadow: none;
    cursor: not-allowed;
  }
  .btn-process-large svg {
    opacity: 0.9;
  }

  /* Stats Row */
  .stats-row {
    display: flex;
    gap: 24px;
    justify-content: center;
    margin-top: 8px;
  }
  
  :global(.stats-row > div) {
    display: flex;
    align-items: center;
  }

  /* Truncate text */
  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  @media (max-width: 900px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
  }

  /* ── Mini Stats Row ── */
  .mini-stats-row {
    display: flex;
    gap: 12px;
  }
  .mini-stats-row :global(> div) {
    flex: 1;
    margin: 0 !important;
  }
</style>
