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
      toast(`ข้อผิดพลาด: ${msg}`, 'error', 6000);
    }
  }

  /** @param {number} ms */
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
</script>

<!-- Dashboard Container -->
<div class="dashboard-container">
  <div class="hero-section">
    <h1 class="hero-title">ยินดีต้อนรับสู่ศูนย์วิเคราะห์เอกสารอัจฉริยะ</h1>
    <p class="hero-subtitle">สัมผัสประสบการณ์การวิเคราะห์ข้อมูลเชิงลึกด้วยระบบ AI ที่มีความแม่นยำสูง เปลี่ยนเอกสารดิบให้เป็นข้อมูลที่มีโครงสร้างในพริบตา</p>
  </div>

  <div class="dashboard-grid">
    <!-- Left Column: Dropzone -->
    <div class="col-left">
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
          <div class="drop-icon-bg">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
          </div>
          <p class="drop-title">ลากไฟล์ PDF มาวางที่นี่</p>
          <p class="drop-hint">
            หรือ <span class="link-text">เลือกไฟล์จากเครื่อง</span> (สูงสุด 50 MB)
          </p>
          <div class="file-tags">
            <span class="file-tag">.pdf</span>
            <span class="file-tag">.docx</span>
            <span class="file-tag">.png</span>
          </div>
          <input
            id="fileInput"
            type="file"
            accept=".pdf"
            hidden
            on:change={onFileChange}
          />
        {:else}
          <!-- Has File State -->
          <div class="file-card">
            <div class="file-icon-wrap">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
            </div>
            <div class="file-info">
              <span class="file-name truncate">{file.name}</span>
              <span class="file-size">{formatBytes(file.size)}</span>
            </div>
            <button class="btn-remove" on:click|stopPropagation={removeFile} title="ลบ">✕</button>
          </div>
        {/if}
      </div>
    </div>
    <!-- Right Column: Settings -->
    <div class="col-right">
      <div class="settings-panel">
        <div class="settings-header">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
          </svg>
          <h2>OCR Settings</h2>
        </div>

        <div class="setting-row-group">
          <label class="setting-label-bold" for="sel-lang">ภาษา OCR</label>
          <select id="sel-lang" bind:value={lang}>
            <option value="tha+eng">ไทย + อังกฤษ</option>
            <option value="tha">ไทยเท่านั้น</option>
            <option value="eng">อังกฤษเท่านั้น</option>
          </select>
        </div>

        <div class="setting-row-group">
          <label class="setting-label-bold" for="sel-dpi">ความละเอียด</label>
          <select id="sel-dpi" bind:value={dpi}>
            <option value="200">200 DPI (เร็ว)</option>
            <option value="300">300 DPI (แม่นยำ)</option>
            <option value="400">400 DPI (ละเอียดสุด)</option>
          </select>
        </div>

        <div class="setting-row-toggle">
          <div class="toggle-text">
            <span class="setting-label-bold">โหมด Auto ตรวจคำผิด</span>
            <span class="setting-subtext">ปรับแก้คำผิดอัตโนมัติด้วย AI</span>
          </div>
          <label class="toggle-wrap">
            <input type="checkbox" bind:checked={autoSpellCheck} />
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
          </label>
        </div>

        <button class="btn-process-magic" on:click={process} disabled={!file}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
          </svg>
          ประมวลผล OCR + ตรวจคำผิด
        </button>
      </div>

      <div class="mini-stats-row">
        <DictStats />
        <FormatRules />
      </div>
    </div>
  </div>
</div>

<style>
  /* ── Layout ── */
  .dashboard-container {
    padding: 32px 48px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 40px;
    background: transparent;
    overflow-y: auto;
  }
  .hero-section {
    text-align: center;
  }
  .hero-title {
    font-size: 28px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 12px;
  }
  .hero-subtitle {
    font-size: 14px;
    color: #94a3b8;
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.6;
  }

  .dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 32px;
    flex: 1;
    min-height: 0;
  }

  /* ── Upload Area (Left) ── */
  .col-left {
    display: flex;
    flex-direction: column;
  }
  .upload-area {
    flex: 1;
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(167, 139, 250, 0.4), rgba(192, 132, 252, 0.2));
    border: 2px dashed rgba(255,255,255,0.1);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    cursor: pointer;
    transition: all 0.3s;
    padding: 32px;
    min-height: 400px;
  }
  .upload-area:hover, .upload-area.dragging {
    border-color: rgba(255,255,255,0.3);
    background: linear-gradient(135deg, rgba(167, 139, 250, 0.5), rgba(192, 132, 252, 0.3));
  }
  .upload-area.has-file {
    border: 1px solid rgba(255,255,255,0.1);
    cursor: default;
    background: rgba(30, 41, 59, 0.5);
  }

  .drop-icon-bg {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: rgba(15, 23, 42, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    margin-bottom: 8px;
  }
  .drop-title {
    font-size: 20px;
    font-weight: 700;
    color: #fff;
  }
  .drop-hint {
    font-size: 13px;
    color: rgba(255,255,255,0.8);
  }
  .link-text {
    text-decoration: underline;
    font-weight: 600;
  }
  .file-tags {
    display: flex;
    gap: 8px;
    margin-top: 12px;
  }
  .file-tag {
    background: rgba(15, 23, 42, 0.5);
    color: rgba(255,255,255,0.8);
    font-size: 11px;
    padding: 4px 12px;
    border-radius: 20px;
  }

  /* File Card (When Uploaded) */
  .file-card {
    display: flex;
    align-items: center;
    gap: 16px;
    width: 100%;
    max-width: 400px;
    background: rgba(255,255,255,0.05);
    padding: 16px;
    border-radius: 12px;
  }
  .file-icon-wrap {
    width: 48px;
    height: 48px;
    border-radius: 8px;
    background: rgba(139, 92, 246, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #a78bfa;
    flex-shrink: 0;
  }
  .file-info {
    flex: 1;
    min-width: 0;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .file-name {
    font-size: 14px;
    font-weight: 600;
    color: #fff;
    display: block;
  }
  .file-size {
    font-size: 12px;
    color: #94a3b8;
  }
  .btn-remove {
    background: rgba(248, 113, 113, 0.1);
    color: #f87171;
    border: none;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s;
  }
  .btn-remove:hover {
    background: rgba(248, 113, 113, 0.2);
  }

  /* ── Right Column: Settings ── */
  .col-right {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .settings-panel {
    background: rgba(30, 41, 59, 0.3);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 20px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .settings-header {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #93c5fd;
  }
  .settings-header h2 {
    font-size: 16px;
    font-weight: 700;
    margin: 0;
    color: #fff;
  }
  
  .setting-row-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .setting-label-bold {
    font-size: 13px;
    font-weight: 600;
    color: #e2e8f0;
  }
  select {
    background: #0f111a;
    border: 1px solid rgba(255,255,255,0.1);
    color: #fff;
    font-family: inherit;
    font-size: 13px;
    border-radius: 8px;
    padding: 10px 12px;
    cursor: pointer;
    outline: none;
    appearance: none;
  }
  select:focus {
    border-color: #8b5cf6;
  }

  .setting-row-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255,255,255,0.03);
    padding: 12px 16px;
    border-radius: 12px;
    margin-top: 8px;
  }
  .toggle-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .setting-subtext {
    font-size: 11px;
    color: #94a3b8;
  }

  /* ── Toggle ── */
  .toggle-wrap {
    display: flex;
    align-items: center;
    cursor: pointer;
  }
  .toggle-wrap input {
    display: none;
  }
  .toggle-track {
    width: 40px;
    height: 22px;
    border-radius: 12px;
    background: rgba(255,255,255,0.1);
    position: relative;
    transition: all 0.25s;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: #c4b5fd;
  }
  .toggle-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #fff;
    position: absolute;
    top: 3px;
    left: 3px;
    transition: all 0.25s;
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb {
    transform: translateX(18px);
  }

  /* ── Process Button ── */
  .btn-process-magic {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 16px;
    background: linear-gradient(135deg, #8b5cf6, #d946ef);
    border: none;
    border-radius: 12px;
    color: #fff;
    font-family: inherit;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.4);
    margin-top: 8px;
  }
  .btn-process-magic:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(139, 92, 246, 0.6);
  }
  .btn-process-magic:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
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
