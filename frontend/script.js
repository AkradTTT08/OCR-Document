/**
 * Thai OCR Spell Check – Frontend Script
 * Handles: Upload, API calls, Spell highlighting, Export, Dictionary
 */

const API = 'http://localhost:5000/api';

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  file: null,
  result: null,
  currentPage: 0,
  currentView: 'highlight',   // 'highlight' | 'plain' | 'errors'
  activeErrorToken: null,
};

// ── DOM Refs ───────────────────────────────────────────────────────────────
const dropZone       = document.getElementById('dropZone');
const fileInput      = document.getElementById('fileInput');
const filePreview    = document.getElementById('filePreview');
const fileName       = document.getElementById('fileName');
const fileSize       = document.getElementById('fileSize');
const removeFile     = document.getElementById('removeFile');
const processBtn     = document.getElementById('processBtn');
const progressWrap   = document.getElementById('progressWrap');
const progressFill   = document.getElementById('progressFill');
const progressLabel  = document.getElementById('progressLabel');
const ps1            = document.getElementById('ps1');
const ps2            = document.getElementById('ps2');
const ps3            = document.getElementById('ps3');
const resultsSection = document.getElementById('resultsSection');
const summaryCards   = document.getElementById('summaryCards');
const pageTabs       = document.getElementById('pageTabs');
const contentArea    = document.getElementById('contentArea');
const uploadSection  = document.getElementById('uploadSection');
const projectSelect  = document.getElementById('projectSelect');
const addProjectBtn  = document.getElementById('addProjectBtn');
const langSelect     = document.getElementById('langSelect');
const dpiSelect      = document.getElementById('dpiSelect');
const suggestToggle  = document.getElementById('suggestToggle');
const tooltip        = document.getElementById('tooltip');
const tooltipWords   = document.getElementById('tooltipWords');
const tooltipAddWord = document.getElementById('tooltipAddWord');
const toastEl        = document.getElementById('toast');
const dictToggle     = document.getElementById('dictToggle');
const dictBody       = document.getElementById('dictBody');
const dictChevron    = document.getElementById('dictChevron');
const dictStats      = document.getElementById('dictStats');
const customWordInput = document.getElementById('customWordInput');
const addWordBtn     = document.getElementById('addWordBtn');
const exportTxt      = document.getElementById('exportTxt');
const exportReport   = document.getElementById('exportReport');

// ── Drag & Drop ─────────────────────────────────────────────────────────────
dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('dragging');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragging'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragging');
  const files = e.dataTransfer.files;
  if (files.length > 0) setFile(files[0]);
});
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files.length > 0) setFile(fileInput.files[0]);
});

function setFile(f) {
  if (!f.name.toLowerCase().endsWith('.pdf')) {
    showToast('รองรับเฉพาะไฟล์ PDF เท่านั้น', 'error');
    return;
  }
  if (f.size > 50 * 1024 * 1024) {
    showToast('ไฟล์ใหญ่เกิน 50 MB', 'error');
    return;
  }
  state.file = f;
  fileName.textContent = f.name;
  fileSize.textContent = formatBytes(f.size);
  filePreview.style.display = 'block';
  processBtn.disabled = false;
}

removeFile.addEventListener('click', () => {
  state.file = null;
  fileInput.value = '';
  filePreview.style.display = 'none';
  processBtn.disabled = true;
});

// ── Process ─────────────────────────────────────────────────────────────────
processBtn.addEventListener('click', async () => {
  if (!state.file) return;

  processBtn.classList.add('loading');
  processBtn.innerHTML = `<svg class="spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> กำลังประมวลผล...`;
  
  progressWrap.style.display = 'block';
  resultsSection.style.display = 'none';
  setProgress(10, 'แปลง PDF เป็นรูปภาพ...', 'ps1');

  const formData = new FormData();
  formData.append('file', state.file);
  
  const projectId = projectSelect.value;
  if (!projectId) {
    showToast('กรุณาเลือก Project ก่อนทำการสแกน', 'error');
    processBtn.classList.remove('loading');
    processBtn.innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/></svg> ประมวลผล OCR + ตรวจคำ`;
    progressWrap.style.display = 'none';
    resultsSection.style.display = 'none';
    return;
  }
  formData.append('project_id', projectId);

  const lang = langSelect.value;
  const dpi  = dpiSelect.value;

  try {
    setProgress(15, 'กำลัง OCR สกัดข้อความ...', 'ps2');

    const res = await fetch(`${API}/process?lang=${lang}&dpi=${dpi}`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'เกิดข้อผิดพลาด');
    }

    setProgress(85, 'ตรวจสอบคำถูกคำผิด...', 'ps3');
    const data = await res.json();

    await sleep(500);
    setProgress(100, 'เสร็จสิ้น!', null);

    await sleep(400);
    state.result = data;
    state.currentPage = 0;
    renderResults(data);

    progressWrap.style.display = 'none';
    showToast(`OCR สำเร็จ ${data.total_pages} หน้า`, 'success');
  } catch (err) {
    progressWrap.style.display = 'none';
    showToast(`ข้อผิดพลาด: ${err.message}`, 'error');
    console.error(err);
  } finally {
    processBtn.classList.remove('loading');
    processBtn.innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"/></svg> ประมวลผล OCR + ตรวจคำ`;
  }
});

// ── Progress helper ──────────────────────────────────────────────────────────
function setProgress(pct, label, activeStep) {
  progressFill.style.width = `${pct}%`;
  progressLabel.textContent = label;
  [ps1, ps2, ps3].forEach(el => {
    el.classList.remove('active', 'done');
  });
  if (activeStep) {
    const steps = ['ps1','ps2','ps3'];
    const idx   = steps.indexOf(activeStep);
    steps.forEach((s, i) => {
      const el = document.getElementById(s);
      if (i < idx) el.classList.add('done');
      else if (i === idx) el.classList.add('active');
    });
  } else {
    [ps1, ps2, ps3].forEach(el => el.classList.add('done'));
  }
}

// ── Render Results ───────────────────────────────────────────────────────────
function renderResults(data) {
  resultsSection.style.display = 'block';
  renderSummaryCards(data.summary);
  renderPageTabs(data.pages);
  renderContent();
  uploadSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderSummaryCards(summary) {
  // Aggregate thai/english token & error counts from all pages
  let thaiTokens = 0, engTokens = 0, thaiErrors = 0, engErrors = 0;
  if (state.result?.pages) {
    state.result.pages.forEach(p => {
      const s = p.spell_check?.summary || {};
      thaiTokens += s.thai_tokens    || 0;
      engTokens  += s.english_tokens || 0;
      thaiErrors += s.thai_errors    || 0;
      engErrors  += s.english_errors || 0;
    });
  }
  const totalErrors = thaiErrors + engErrors;
  const totalTokens = thaiTokens + engTokens;
  const errorRate = totalTokens > 0 ? ((totalErrors / totalTokens) * 100).toFixed(2) : 0;

  const cards = [
    { value: summary.total_pages,               label: 'หน้าทั้งหมด',     color: '#6c8efb' },
    { value: `${thaiTokens.toLocaleString()} / ${engTokens.toLocaleString()}`, label: 'คำไทย / อังกฤษ', color: '#a78bfa' },
    { value: `${thaiErrors} / ${engErrors}`,    label: 'คำผิดไทย / Eng',   color: '#f87171' },
    { value: `${errorRate}%`,                   label: 'อัตราคำผิด',       color: '#fbbf24' },
  ];
  summaryCards.innerHTML = cards.map(c => `
    <div class="stat-card">
      <div class="stat-value" style="color:${c.color}">${c.value}</div>
      <div class="stat-label">${c.label}</div>
    </div>
  `).join('');
}

function renderPageTabs(pages) {
  pageTabs.innerHTML = pages.map((p, i) => `
    <button class="page-tab ${i === state.currentPage ? 'active' : ''}"
            data-page="${i}">
      หน้า ${p.page_number}
      ${p.spell_check?.summary?.error_count > 0
        ? `<span style="color:#f87171;margin-left:4px">(${p.spell_check.summary.error_count})</span>`
        : ''}
    </button>
  `).join('');
  pageTabs.querySelectorAll('.page-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      state.currentPage = parseInt(btn.dataset.page);
      pageTabs.querySelectorAll('.page-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderContent();
    });
  });
}

function renderContent() {
  const page = state.result.pages[state.currentPage];
  switch (state.currentView) {
    case 'highlight': renderHighlight(page); break;
    case 'plain':     renderPlain(page);     break;
    case 'errors':    renderErrors(page);    break;
  }
}

// ── View: Highlight ──────────────────────────────────────────────────────────
function renderHighlight(page) {
  const tokens = page.spell_check?.tokens || [];
  if (!tokens.length) {
    contentArea.innerHTML = `<div class="plain-text">${escapeHtml(page.text)}</div>`;
    return;
  }
  const html = tokens.map(t => {
    // Whitespace / other – render as-is
    if (t.lang === 'other' || (!t.lang && !THAI_CHAR_RE_JS.test(t.token))) {
      return escapeHtml(t.token).replace(/\n/g, '<br>');
    }
    if (t.is_correct) {
      return `<span class="token-correct">${escapeHtml(t.token)}</span>`;
    }
    // Thai error = red, English error = orange
    const cls = t.lang === 'english' ? 'token-error-eng' : 'token-error';
    const suggs = JSON.stringify(t.suggestions);
    return `<span class="${cls}" data-word="${escapeHtml(t.token)}" data-suggestions='${suggs}'>${escapeHtml(t.token)}</span>`;
  }).join('');
  contentArea.innerHTML = `<div style="line-height:2.2">${html}</div>`;

  // Error token click → tooltip
  contentArea.querySelectorAll('.token-error, .token-error-eng').forEach(el => {
    el.addEventListener('click', e => {
      e.stopPropagation();
      const word = el.dataset.word;
      let suggestions = [];
      try { suggestions = JSON.parse(el.dataset.suggestions); } catch {}
      showTokenTooltip(el, word, suggestions);
    });
  });
}

const THAI_CHAR_RE_JS = /[\u0E00-\u0E7F]/

// ── View: Plain text ─────────────────────────────────────────────────────────
function renderPlain(page) {
  contentArea.innerHTML = `<pre class="plain-text">${escapeHtml(page.text)}</pre>`;
}

// ── View: Errors list ────────────────────────────────────────────────────────
function renderErrors(page) {
  const tokens = page.spell_check?.tokens || [];
  const errors = tokens.filter(t => (t.lang === 'thai' || t.lang === 'english') && !t.is_correct);
  if (!errors.length) {
    contentArea.innerHTML = `
      <div class="no-errors-msg">
        ✅ ไม่พบคำผิดในหน้านี้
      </div>`;
    return;
  }
  contentArea.innerHTML = `<div class="error-list">` + errors.map(t => {
    const langBadge = t.lang === 'english'
      ? `<span class="lang-badge-eng">EN</span>`
      : `<span class="lang-badge-th">TH</span>`;
    const wordColor = t.lang === 'english' ? 'var(--warning)' : 'var(--danger)';
    return `
    <div class="error-item">
      ${langBadge}
      <div class="error-word" style="color:${wordColor}">${escapeHtml(t.token)}</div>
      <div class="error-arrow">→</div>
      <div class="error-suggestions">
        ${t.suggestions.length
          ? t.suggestions.map(s => `<span class="sugg-chip">${escapeHtml(s)}</span>`).join('')
          : `<span style="color:var(--text3);font-size:13px">ไม่มีคำแนะนำ</span>`
        }
      </div>
    </div>`;
  }).join('') + `</div>`;
}

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.currentView = btn.dataset.view;
    if (state.result) renderContent();
  });
});

// ── Tooltip ──────────────────────────────────────────────────────────────────
let tooltipActiveWord = '';

function showTokenTooltip(el, word, suggestions) {
  tooltipActiveWord = word;
  tooltipWords.innerHTML = suggestions.length
    ? suggestions.map(s => `<span class="tt-chip">${escapeHtml(s)}</span>`).join('')
    : `<span style="color:var(--text3);font-size:13px">ไม่มีคำแนะนำ</span>`;

  const rect = el.getBoundingClientRect();
  tooltip.style.display = 'block';
  const ttW = tooltip.offsetWidth;
  let left = rect.left + rect.width / 2 - ttW / 2;
  left = Math.max(8, Math.min(left, window.innerWidth - ttW - 8));
  tooltip.style.left = `${left}px`;
  tooltip.style.top  = `${rect.bottom + 8 + window.scrollY}px`;
}

tooltipAddWord.addEventListener('click', () => {
  if (tooltipActiveWord) addWordToDictionary(tooltipActiveWord);
  hideTooltip();
});

function hideTooltip() {
  tooltip.style.display = 'none';
  tooltipActiveWord = '';
}
document.addEventListener('click', e => {
  if (!tooltip.contains(e.target)) hideTooltip();
});

// ── Dictionary Panel ──────────────────────────────────────────────────────────
dictToggle.addEventListener('click', async () => {
  const isOpen = dictBody.classList.toggle('open');
  dictChevron.classList.toggle('open', isOpen);
  if (isOpen) fetchDictStats();
});

async function fetchDictStats() {
  try {
    const res = await fetch(`${API}/dictionary/stats`);
    const data = await res.json();
    if (data.success) {
      const s = data.stats;
      dictStats.innerHTML = `
        <div class="dict-stat">
          <div class="dict-stat-val" style="color:var(--primary2)">${s.thai_words.toLocaleString()}</div>
          <div class="dict-stat-lbl">คำไทย (ราชบัณฑิตยสภา)</div>
        </div>
        <div class="dict-stat">
          <div class="dict-stat-val" style="color:var(--warning)">${(s.english_words||0).toLocaleString()}</div>
          <div class="dict-stat-lbl">คำอังกฤษ</div>
        </div>
        <div class="dict-stat">
          <div class="dict-stat-val" style="color:var(--success)">${s.custom_words}</div>
          <div class="dict-stat-lbl">Custom Words</div>
        </div>
      `;
    }
  } catch {
    dictStats.innerHTML = `<div style="color:var(--text3);font-size:13px;padding:8px">ไม่สามารถโหลดสถิติได้</div>`;
  }
}

addWordBtn.addEventListener('click', () => {
  const word = customWordInput.value.trim();
  if (word) {
    addWordToDictionary(word);
    customWordInput.value = '';
  }
});
customWordInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') addWordBtn.click();
});

async function addWordToDictionary(word) {
  try {
    const res = await fetch(`${API}/dictionary/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word }),
    });
    const data = await res.json();
    if (data.success) {
      showToast(`เพิ่มคำ "${word}" สำเร็จ`, 'success');
      fetchDictStats();
    } else {
      showToast(data.error || 'เพิ่มคำไม่สำเร็จ', 'error');
    }
  } catch {
    showToast('เชื่อมต่อ API ไม่ได้', 'error');
  }
}

// ── Export ────────────────────────────────────────────────────────────────────
exportTxt.addEventListener('click', () => {
  if (!state.result) return;
  const text = state.result.pages.map(p =>
    `=== หน้า ${p.page_number} ===\n${p.text}`
  ).join('\n\n');
  downloadFile(text, 'ocr_result.txt', 'text/plain');
  showToast('Export .txt สำเร็จ', 'success');
});

exportReport.addEventListener('click', () => {
  if (!state.result) return;
  const r = state.result;
  let thaiErr = 0, engErr = 0, thaiTok = 0, engTok = 0;
  r.pages.forEach(p => {
    const s = p.spell_check?.summary || {};
    thaiErr += s.thai_errors    || 0;
    engErr  += s.english_errors || 0;
    thaiTok += s.thai_tokens    || 0;
    engTok  += s.english_tokens || 0;
  });
  const totalErrors = thaiErr + engErr;
  const totalTokens = thaiTok + engTok;
  const errRate = totalTokens > 0 ? ((totalErrors/totalTokens)*100).toFixed(2) : 0;

  let report = `=== รายงาน OCR + ตรวจสอบคำ ===\n`;
  report += `ไฟล์: ${r.filename}\n`;
  report += `จำนวนหน้า: ${r.total_pages}\n`;
  report += `คำไทย: ${thaiTok.toLocaleString()} คำ | คำอังกฤษ: ${engTok.toLocaleString()} คำ\n`;
  report += `คำผิด(ไทย): ${thaiErr} | คำผิด(Eng): ${engErr}\n`;
  report += `อัตราคำผิด: ${errRate}%\n`;
  report += `\n${'─'.repeat(40)}\n\n`;

  r.pages.forEach(p => {
    report += `=== หน้า ${p.page_number} ===\n`;
    const tokens = p.spell_check?.tokens || [];
    const errors = tokens.filter(t => (t.lang === 'thai' || t.lang === 'english') && !t.is_correct);
    const thaiE  = errors.filter(t => t.lang === 'thai').length;
    const engE   = errors.filter(t => t.lang === 'english').length;
    report += `คำผิด: ไทย ${thaiE} | อังกฤษ ${engE}\n`;
    if (errors.length) {
      errors.forEach(t => {
        const langTag = t.lang === 'english' ? '[EN]' : '[TH]';
        const sugg = t.suggestions.length ? ` → ${t.suggestions.join(', ')}` : '';
        report += `  ${langTag} ${t.token}${sugg}\n`;
      });
    }
    report += `\n[ข้อความ OCR]\n${p.text}\n\n`;
  });

  downloadFile(report, 'ocr_report.txt', 'text/plain');
  showToast('Export รายงานสำเร็จ', 'success');
});

// ── Utilities ─────────────────────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/1024/1024).toFixed(1)} MB`;
}

function downloadFile(content, filename, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

let toastTimeout;
function showToast(msg, type = '') {
  toastEl.textContent = msg;
  toastEl.className = `toast ${type} show`;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => { toastEl.className = 'toast'; }, 3000);
}

// CSS for spin animation
const spinStyle = document.createElement('style');
spinStyle.textContent = `.spin { animation: spin 1s linear infinite; } @keyframes spin { to { transform: rotate(360deg); } }`;
document.head.appendChild(spinStyle);

// ── Projects Management ───────────────────────────────────────────────────────
async function fetchProjects() {
  try {
    const res = await fetch(`${API}/projects`);
    const data = await res.json();
    if (data.success) {
      const projects = data.projects;
      if (projects.length === 0) {
        projectSelect.innerHTML = `<option value="">-- ไม่มีโปรเจกต์ (กรุณาเพิ่ม) --</option>`;
      } else {
        projectSelect.innerHTML = `<option value="">-- เลือกโปรเจกต์ --</option>` + 
          projects.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
      }
    } else {
      projectSelect.innerHTML = `<option value="">ดึงข้อมูลโปรเจกต์ล้มเหลว</option>`;
    }
  } catch (e) {
    console.error("Error fetching projects:", e);
    projectSelect.innerHTML = `<option value="">โหลดโปรเจกต์ไม่สำเร็จ</option>`;
  }
}

addProjectBtn.addEventListener('click', async () => {
  const projectName = prompt("กรุณากรอกชื่อโปรเจกต์ใหม่:");
  if (!projectName || !projectName.trim()) return;
  
  try {
    const res = await fetch(`${API}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: projectName.trim() })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`สร้างโปรเจกต์ "${data.project.name}" สำเร็จ`, 'success');
      await fetchProjects();
      projectSelect.value = data.project.id;
    } else {
      showToast(data.error || 'สร้างโปรเจกต์ไม่สำเร็จ', 'error');
    }
  } catch (e) {
    console.error(e);
    showToast('ข้อผิดพลาดในการเชื่อมต่อ', 'error');
  }
});

// Load projects on startup
fetchProjects();

