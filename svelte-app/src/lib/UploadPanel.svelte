<script>
  import { createEventDispatcher } from 'svelte';
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

<!-- Drop Zone -->
<div class="upload-area"
     role="button"
     tabindex="0"
     on:dragover|preventDefault={() => isDragging = true}
     on:dragleave={() => isDragging = false}
     on:drop={onDrop}
     on:click={() => !file && document.getElementById('fileInput')?.click()}
     on:keydown={e => e.key === 'Enter' && !file && document.getElementById('fileInput')?.click()}
     class:dragging={isDragging}
     class:has-file={!!file}
>
  {#if !file}
    <div class="drop-icon" class:bounce={isDragging}>
      <svg viewBox="0 0 64 64" fill="none">
        <circle cx="32" cy="32" r="30" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3"/>
        <path d="M32 20v16M24 28l8-8 8 8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M22 44h20" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </div>
    <p class="drop-title">ลากไฟล์ PDF มาวางที่นี่</p>
    <p class="drop-hint">หรือ <span class="link-text">เลือกไฟล์</span> (สูงสุด 50 MB)</p>
    <input id="fileInput" type="file" accept=".pdf" hidden on:change={onFileChange}/>
  {:else}
    <div class="file-card">
      <div class="file-icon-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
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

<!-- Settings -->
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
  <div class="setting-row">
    <span class="setting-label">โหมด Auto ตรวจคำผิด</span>
    <label class="toggle-wrap">
      <input type="checkbox" bind:checked={autoSpellCheck}/>
      <span class="toggle-track"><span class="toggle-thumb"></span></span>
    </label>
  </div>
</div>

<!-- Process Button -->
<div class="btn-wrap">
  <button class="btn-process" on:click={process} disabled={!file}>
    <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
      <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/>
    </svg>
    ประมวลผล OCR + ตรวจคำ
  </button>
</div>

<!-- Dict stats mini -->
<DictStats />
<FormatRules />

<style>
/* ── Upload area ── */
.upload-area {
  margin: 16px 16px 0;
  border: 2px dashed rgba(108,142,251,0.28);
  border-radius: var(--radius2);
  padding: 32px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: rgba(108,142,251,0.02);
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.upload-area:hover, .upload-area.dragging {
  border-color: var(--primary);
  background: rgba(108,142,251,0.06);
  box-shadow: 0 0 0 3px var(--glow);
}
.upload-area.has-file {
  border-style: solid;
  border-color: rgba(108,142,251,0.25);
  padding: 16px 20px;
  min-height: auto;
  cursor: default;
}

.drop-icon {
  width: 60px; height: 60px; color: var(--primary);
  filter: drop-shadow(0 0 12px var(--glow));
  transition: transform 0.3s;
}
.drop-icon.bounce { transform: translateY(-6px); }

.drop-title {
  font-size: 15px; font-weight: 600; color: var(--text);
}
.drop-hint {
  font-size: 13px; color: var(--text3);
}
.link-text {
  color: var(--primary2); cursor: pointer; text-decoration: underline;
}

/* ── File card ── */
.file-card {
  display: flex; align-items: center; gap: 10px; width: 100%;
}
.file-icon-wrap {
  width: 38px; height: 38px; border-radius: 8px;
  background: rgba(108,142,251,0.14);
  display: flex; align-items: center; justify-content: center;
  color: var(--primary); flex-shrink: 0;
}
.file-info {
  flex: 1; min-width: 0; text-align: left;
  display: flex; flex-direction: column; gap: 2px;
}
.file-name { font-size: 13px; font-weight: 600; display: block; }
.file-size { font-size: 11px; color: var(--text3); }
.btn-remove {
  background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.2);
  color: var(--danger); width: 26px; height: 26px; border-radius: 5px;
  cursor: pointer; font-size: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  transition: background 0.2s;
}
.btn-remove:hover { background: rgba(248,113,113,0.22); }

/* ── Settings ── */
.settings-block {
  margin: 14px 16px 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius2);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.setting-row {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 13px; color: var(--text2);
}
.setting-label { font-weight: 500; }
select {
  background: var(--bg3); border: 1px solid var(--border2);
  color: var(--text); font-family: var(--font-th); font-size: 12px;
  border-radius: 6px; padding: 5px 8px; cursor: pointer; outline: none;
  transition: border-color 0.2s;
}
select:focus { border-color: var(--primary); }

/* ── Toggle ── */
.toggle-wrap { display: flex; align-items: center; cursor: pointer; }
.toggle-wrap input { display: none; }
.toggle-track {
  width: 36px; height: 20px; border-radius: 10px;
  background: var(--surface2); border: 1px solid var(--border2);
  position: relative; transition: all 0.25s;
}
.toggle-wrap input:checked + .toggle-track {
  background: var(--primary); border-color: var(--primary);
  box-shadow: 0 0 8px var(--glow);
}
.toggle-thumb {
  width: 14px; height: 14px; border-radius: 50%;
  background: var(--text3); position: absolute; top: 2px; left: 2px;
  transition: all 0.25s;
}
.toggle-wrap input:checked + .toggle-track .toggle-thumb {
  transform: translateX(16px); background: #fff;
}

/* ── Btn ── */
.btn-wrap {
  padding: 14px 16px 0;
}
.btn-process {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  width: 100%; padding: 13px;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  border: none; border-radius: var(--radius2);
  color: #fff; font-family: var(--font-th); font-size: 15px; font-weight: 600;
  cursor: pointer; transition: all 0.3s;
  box-shadow: 0 4px 20px var(--glow);
  letter-spacing: 0.01em;
}
.btn-process:hover:not(:disabled) {
  transform: translateY(-2px); box-shadow: 0 8px 28px var(--glow);
}
.btn-process:disabled {
  opacity: 0.35; cursor: not-allowed; transform: none;
}
</style>
