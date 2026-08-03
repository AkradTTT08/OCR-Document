<script>
  import { toast } from "./toastStore.js";
  import { createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher();

  let showConfirmModal = false;

  function closeResults() {
    showConfirmModal = true;
  }

  function confirmClose() {
    showConfirmModal = false;
    dispatch('close');
  }

  function cancelClose() {
    showConfirmModal = false;
  }

  /** @type {any} */
  export let result = null;
  export let isProcessing = false;
  export let progress = { pct: 0, label: "", step: 0 };

  // ── ETA Calculation ──
  let startTime = null;
  let estimatedTimeLeft = "กำลังเริ่มระบบ...";

  $: if (isProcessing && !startTime) {
    startTime = Date.now();
  } else if (!isProcessing) {
    startTime = null;
    estimatedTimeLeft = "กำลังเริ่มระบบ...";
  }

  $: if (isProcessing && progress.pct > 0 && progress.pct < 100 && startTime) {
    const elapsed = Date.now() - startTime;
    const totalTimeEst = elapsed / (progress.pct / 100);
    const timeLeft = totalTimeEst - elapsed;
    if (timeLeft < 0) {
      estimatedTimeLeft = "ใกล้เสร็จสมบูรณ์...";
    } else {
      const secs = Math.ceil(timeLeft / 1000);
      if (secs > 60) {
        estimatedTimeLeft = `~${Math.floor(secs/60)} นาที ${secs%60} วินาที`;
      } else {
        estimatedTimeLeft = `~${secs} วินาที`;
      }
    }
  } else if (progress.pct === 100) {
    estimatedTimeLeft = "กำลังประมวลผลขั้นตอนสุดท้าย...";
  }

  // ── View state ──
  let viewMode = "markdown"; // 'markdown' | 'json' | 'vector'

  // ── Derived ──
  $: pages = result?.pages ?? [];
  $: activePage = pages[activePageIdx] ?? null;
  $: allErrors = collectAllErrors(pages);
  $: pageErrors = activePage?.spell_check?.errors ?? [];
  $: filteredErrors =
    filterLang === "all"
      ? pageErrors
      : pageErrors.filter((/** @type {any} */ e) => e.lang === filterLang);

  $: totalThai = sumSummaryField(pages, "thai_tokens");
  $: totalEng = sumSummaryField(pages, "english_tokens");
  $: totalThaiErr = sumSummaryField(pages, "thai_errors");
  $: totalEngErr = sumSummaryField(pages, "english_errors");
  $: totalSemantic = sumSummaryField(pages, "semantic_errors");
  $: totalErr = totalThaiErr + totalEngErr + totalSemantic;
  $: errRate =
    totalThai + totalEng > 0
      ? ((totalErr / (totalThai + totalEng)) * 100).toFixed(1)
      : "0";
  $: ocrAccuracy = errRate ? (100 - parseFloat(errRate)).toFixed(1) : "100.0";

  $: combinedText = pages.map(p => p.text || "").join('\n\n');
  $: markdownHtml = syntaxHighlightMarkdown(combinedText);

  function syntaxHighlightMarkdown(text) {
    if (!text) return '';
    let html = text
      .replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/^(\s*#+\s+)(.*)$/gm, '<span style="color: #38bdf8;">$1$2</span>')
      .replace(/(\*\*.*?\*\*)/g, '<span style="color: #4ade80;">$1</span>')
      .replace(/(`.*?`)/g, '<span style="color: #f472b6;">$1</span>')
      .replace(/^(\s*[-*]\s+)/gm, '<span style="color: #f472b6;">$1</span>');
    return html;
  }

  /**
   * @param {any[]} pages
   * @param {string} field
   */
  function sumSummaryField(pages, field) {
    return pages.reduce(
      (acc, p) => acc + (p.spell_check?.summary?.[field] ?? 0),
      0,
    );
  }

  /**
   * @param {any[]} pages
   */
  function collectAllErrors(pages) {
    return pages.flatMap((p) =>
      (p.spell_check?.errors ?? []).map((/** @type {any} */ e) => ({
        ...e,
        page: p.page_number,
      })),
    );
  }

  $: highlightedHtml = parseMarkdownToHtml(
    generateHighlightedHtml(activePage?.text, activePage?.spell_check?.errors),
  );

  /**
   * @param {string} text
   * @param {any[]} errors
   */
  function generateHighlightedHtml(text, errors) {
    if (!text) return "";
    if (!errors || errors.length === 0) return text;

    // 1. Extract all HTML tags and replace them with a unique placeholder
    /** @type {string[]} */
    const tags = [];
    let safeText = text.replace(/<[^>]+>/g, (match) => {
      tags.push(match);
      return `__TAG_${tags.length - 1}__`;
    });

    // 2. Replace errors in the safeText
    errors.forEach((err) => {
      if (!err.token || err.token.trim() === "") return;
      const safeToken = err.token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

      let cssClass = "tok-err-th";
      let title = `สะกดผิด | แนะนำ: ${(err.suggestions || []).join(", ")}`;

      if (err.error_type === "format") {
        cssClass = "tok-err-fmt";
        title = `รูปแบบ | ${err.message || "รูปแบบไม่ถูกต้อง"} | แนะนำ: ${(err.suggestions || []).join(", ")}`;
      } else if (err.error_type === "semantic") {
        cssClass = "tok-err-sm";
        title = `บริบท | แนะนำ: ${(err.suggestions || []).join(", ")}`;
      } else if (err.lang === "english") {
        cssClass = "tok-err-en";
        title = `Misspelled | Suggestions: ${(err.suggestions || []).join(", ")}`;
      }

      let regexStr = safeToken;
      if (err.lang === "english") {
        regexStr = `\\b${safeToken}\\b`;
      }

      const regex = new RegExp(regexStr, "g");
      const replacement = `<span class="${cssClass}" title="${title}">${err.token}</span>`;

      safeText = safeText.replace(regex, replacement);
    });

    // 3. Restore HTML tags
    let finalHtml = safeText.replace(/__TAG_(\d+)__/g, (match, p1) => {
      return tags[parseInt(p1, 10)];
    });

    return finalHtml;
  }

  /**
   * @param {string} text
   * @returns {string}
   */
  function parseMarkdownToHtml(text) {
    if (!text) return "";

    const lines = text.split("\n");
    /** @type {string[]} */
    const html = [];
    let inTable = false;
    /** @type {string[]} */
    let tableHeaders = [];
    /** @type {string[][]} */
    let tableRows = [];

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();

      // ตรวจสอบว่าเป็นบรรทัดของตารางหรือไม่
      if (line.startsWith("|") && line.endsWith("|")) {
        const cells = line
          .split("|")
          .map((c) => c.trim())
          .slice(1, -1);

        if (!inTable) {
          const nextLine = (lines[i + 1] || "").trim();
          // ปรับปรุง Regex ให้ตรวจจับขีดแบ่งหัวตาราง ยืดหยุ่นขึ้น (รองรับช่องว่าง และเครื่องหมาย :)
          if (
            nextLine.startsWith("|") &&
            /^[|:\s-]+$/.test(nextLine) &&
            nextLine.includes("-")
          ) {
            inTable = true;
            tableHeaders = cells;
            i++; // ข้ามแถวขีดแบ่งไป
            continue;
          }
        }

        if (inTable) {
          const isRowEmpty = cells.every((c) => c === "");
          if (!isRowEmpty) {
            tableRows.push(cells);
          }
          continue;
        }
      }

      // ถ้าเจอบรรทัดที่ไม่ใช่ตาราง แต่ก่อนหน้านี้ค้างตารางไว้ ให้เรนเดอร์ตารางออกมาก่อน
      if (inTable) {
        html.push(renderHtmlTable(tableHeaders, tableRows));
        inTable = false;
        tableHeaders = [];
        tableRows = [];
      }

      // ประมวลผลบรรทัดข้อความปกติ
      if (line === "") {
        html.push("<br/>");
      } else if (line.startsWith("- ") || line.startsWith("* ")) {
        html.push(`<ul><li>${line.substring(2)}</li></ul>`);
      } else if (/^\d+\.\s/.test(line)) {
        const match = line.match(/^(\d+)\.\s(.*)/);
        if (match) {
          html.push(`<ol start="${match[1]}"><li>${match[2]}</li></ol>`);
        } else {
          html.push(`<div>${line}</div>`);
        }
      } else {
        html.push(`<div>${line}</div>`);
      }
    }

    // 🌟 [จุดสำคัญที่แก้บั๊ก] หากลูปจบแล้ว แต่ข้อมูลตารางยังค้างอยู่ (ตารางอยู่ท้ายหน้าพอดี) ให้พ่นออกไปด้วย
    if (inTable) {
      html.push(renderHtmlTable(tableHeaders, tableRows));
    }

    return html.join("\n");
  }

  /**
   * @param {string[]} headers
   * @param {string[][]} rows
   * @returns {string}
   */
  function renderHtmlTable(headers, rows) {
    const html = ['<div class="table-container"><table class="ocr-table">'];
    if (headers.length > 0) {
      html.push("<thead><tr>");
      headers.forEach((h) => {
        html.push(`<th>${h}</th>`);
      });
      html.push("</tr></thead>");
    }
    if (rows.length > 0) {
      html.push("<tbody>");
      rows.forEach((row) => {
        html.push("<tr>");
        row.forEach((cell) => {
          html.push(`<td>${cell}</td>`);
        });
        html.push("</tr>");
      });
      html.push("</tbody>");
    }
    html.push("</table></div>");
    return html.join("");
  }

  // ── Export ──
  function exportTxt() {
    if (!result) return;
    const text = result.pages
      .map((/** @type {any} */ p) => `=== หน้า ${p.page_number} ===\n${p.text}`)
      .join("\n\n");
    downloadFile(text, "ocr_result.txt");
  }
  function exportReport() {
    if (!result) return;
    let r = `=== รายงาน OCR + ตรวจสอบคำ ===\nไฟล์: ${result.filename}\nหน้าทั้งหมด: ${result.total_pages}\n`;
    r += `คำไทย: ${totalThai.toLocaleString()} | คำอังกฤษ: ${totalEng.toLocaleString()}\n`;
    r += `คำผิด(ไทย): ${totalThaiErr} | คำผิด(Eng): ${totalEngErr} | อัตรา: ${errRate}%\n`;
    r += `\n${"─".repeat(44)}\n\n`;
    result.pages.forEach((/** @type {any} */ p) => {
      r += `=== หน้า ${p.page_number} ===\n`;
      const errors = p.spell_check?.errors ?? [];
      errors.forEach((/** @type {any} */ e) => {
        const tag = e.lang === "english" ? "[EN]" : "[TH]";
        const sugg = e.suggestions?.length
          ? ` → ${e.suggestions.join(", ")}`
          : "";
        r += `  บรรทัด ${e.line_number}: ${tag} "${e.token}"${sugg}\n`;
      });
      r += `\n[ข้อความ OCR]\n${p.text}\n\n`;
    });
    downloadFile(r, "ocr_report.txt");
  }
  /**
   * @param {string} content
   * @param {string} name
   */
  function downloadFile(content, name) {
    const a = Object.assign(document.createElement("a"), {
      href: URL.createObjectURL(new Blob([content], { type: "text/plain" })),
      download: name,
    });
    a.click();
    a.click();
  }

  let checkingSpell = false;
  async function runManualSpellCheck() {
    if (!activePage || checkingSpell) return;

    checkingSpell = true;
    try {
      toast(`เริ่มตรวจสอบคำผิดหน้า ${activePage.page_number}...`, "info", 2000);
      const API = "http://localhost:5000/api";
      const res = await fetch(`${API}/spellcheck`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: activePage.text,
          words: activePage.words,
          include_suggestions: true,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "เกิดข้อผิดพลาด");

      // Update page data
      result.pages[activePageIdx].spell_check = data.result;

      // Trigger reactivity
      result = result;
      toast(`ตรวจสอบคำผิดหน้า ${activePage.page_number} เสร็จสิ้น`, "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast(`ข้อผิดพลาด: ${msg}`, "error");
    } finally {
      checkingSpell = false;
    }
  }

  // ── Save to DB State ──
  let showSaveModal = false;
  let isSaving = false;
  let projects = [];
  let saveForm = {
    project_id: '',
    filename: '',
    doc_category: 'Reference',
    doc_type: 'PDF',
    is_golden_data: false
  };

  async function openSaveModal() {
    if (!result) return;
    saveForm.filename = result.filename;
    const ext = result.filename.split('.').pop()?.toLowerCase();
    if (ext === 'pdf') saveForm.doc_type = 'PDF';
    else if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) saveForm.doc_type = 'Image';
    else if (['doc', 'docx'].includes(ext)) saveForm.doc_type = 'Word';
    else saveForm.doc_type = 'Other';
    showSaveModal = true;
    try {
      const res = await fetch("http://localhost:5000/api/projects");
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
        if (projects.length > 0 && !saveForm.project_id) {
          saveForm.project_id = projects[0].id;
        }
      }
    } catch (e) {
      console.error("Failed to load projects:", e);
    }
  }

  async function saveToProject() {
    if (!saveForm.project_id) {
      toast("กรุณาเลือกโครงการ", "warning");
      return;
    }
    isSaving = true;
    try {
      const markdownText = result.pages.map((p) => p.text).join("\n\n");
      const res = await fetch("http://localhost:5000/api/kb/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: saveForm.filename,
          markdown_text: markdownText,
          project_id: saveForm.project_id,
          doc_category: saveForm.doc_category,
          doc_type: saveForm.doc_type,
          is_golden_data: saveForm.is_golden_data,
          session_id: result.session_id
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "เกิดข้อผิดพลาดในการบันทึก");
      
      toast(data.message || "บันทึกเอกสารเข้าโครงการสำเร็จ", "success");
      showSaveModal = false;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast(`ข้อผิดพลาด: ${msg}`, "error");
    } finally {
      isSaving = false;
    }
  }
</script>

<!-- ── RIGHT PANEL ── -->
<div class="rp">
  <!-- ─── Empty / Processing State ─── -->
  {#if isProcessing}
    <div class="processing-screen">
      <div class="proc-header">
        <div style="width: 140px; height: 140px; margin: 0 auto 16px auto;">
          <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:100%;">
            <!-- Glow Effect -->
            <defs>
              <filter height="140%" id="glow" width="140%" x="-20%" y="-20%">
                <feGaussianBlur result="blur" stdDeviation="3"></feGaussianBlur>
                <feComposite in="SourceGraphic" in2="blur" operator="over"></feComposite>
              </filter>
              <linearGradient id="spectrum" x1="0%" x2="100%" y1="0%" y2="0%">
                <stop offset="0%" stop-color="#6366f1">
                  <animate attributeName="stop-color" dur="4s" repeatCount="indefinite" values="#6366f1;#ec4899;#8b5cf6;#6366f1"></animate>
                </stop>
                <stop offset="50%" stop-color="#8b5cf6">
                  <animate attributeName="stop-color" dur="4s" repeatCount="indefinite" values="#8b5cf6;#6366f1;#ec4899;#8b5cf6"></animate>
                </stop>
                <stop offset="100%" stop-color="#ec4899">
                  <animate attributeName="stop-color" dur="4s" repeatCount="indefinite" values="#ec4899;#8b5cf6;#6366f1;#ec4899"></animate>
                </stop>
              </linearGradient>
            </defs>
            <!-- Background Circle (Dark Navy) -->
            <circle cx="100" cy="100" fill="#0b1326" r="80"></circle>
            <!-- Prism Base -->
            <path d="M100 45 L155 140 L45 140 Z" fill="none" stroke="white" stroke-opacity="0.3" stroke-width="1.5"></path>
            <!-- Prism Detail Lines -->
            <path d="M100 45 L100 140 M100 45 L155 140 M100 45 L45 140" stroke="white" stroke-opacity="0.2" stroke-width="0.8"></path>
            <!-- Incoming Light Beam -->
            <line stroke="white" stroke-width="2" x1="20" x2="80" y1="100" y2="100">
              <animate attributeName="x2" dur="2s" repeatCount="indefinite" values="20;80;80;20"></animate>
              <animate attributeName="opacity" dur="2s" repeatCount="indefinite" values="0;1;1;0"></animate>
            </line>
            <!-- Refracted Spectrum -->
            <path d="M105 95 Q130 90 180 80" fill="none" filter="url(#glow)" stroke="url(#spectrum)" stroke-width="6">
              <animate attributeName="stroke-dasharray" dur="2s" repeatCount="indefinite" values="0,100;100,0"></animate>
            </path>
            <path d="M105 100 Q130 100 180 100" fill="none" filter="url(#glow)" opacity="0.7" stroke="url(#spectrum)" stroke-width="6">
              <animate attributeName="stroke-dasharray" begin="0.2s" dur="2s" repeatCount="indefinite" values="0,100;100,0"></animate>
            </path>
            <path d="M105 105 Q130 110 180 120" fill="none" filter="url(#glow)" opacity="0.5" stroke="url(#spectrum)" stroke-width="6">
              <animate attributeName="stroke-dasharray" begin="0.4s" dur="2s" repeatCount="indefinite" values="0,100;100,0"></animate>
            </path>
            <!-- Pulse Effect -->
            <circle cx="100" cy="100" fill="none" r="80" stroke="url(#spectrum)" stroke-width="2">
              <animate attributeName="r" dur="2s" repeatCount="indefinite" values="80;90"></animate>
              <animate attributeName="opacity" dur="2s" repeatCount="indefinite" values="0.5;0"></animate>
            </circle>
          </svg>
        </div>
        <h2 class="proc-title">Intelligence Processing...</h2>
        <p class="proc-subtitle">กำลังวิเคราะห์เอกสารและสร้าง Vector Data ด้วย Prism AI</p>
      </div>

      <div class="proc-box">
        <div class="proc-box-top">
          <div class="proc-status-col">
            <span class="lbl-status">STATUS</span>
            <span class="proc-current-step">{progress.label || 'Refracting Data Streams...'}</span>
          </div>
          <div class="lbl-pct">{progress.pct}%</div>
        </div>
        <div class="proc-track-bg">
          <div class="proc-track-fill" style="width: {progress.pct}%"></div>
        </div>
        <div class="proc-eta">
          ⏱️ ระยะเวลาโดยประมาณ: {estimatedTimeLeft}
        </div>
      </div>

      <div class="proc-logs">
        <div class="log-line" class:active={progress.pct >= 0} class:current={progress.pct >= 0 && progress.pct <= 15}>• Validating entity relationships...</div>
        <div class="log-line" class:active={progress.pct > 15} class:current={progress.pct > 15 && progress.pct <= 35}>• Syncing with Prism Core database...</div>
        <div class="log-line" class:active={progress.pct > 35} class:current={progress.pct > 35 && progress.pct <= 60}>• Re-calculating embedding weights...</div>
        <div class="log-line" class:active={progress.pct > 60} class:current={progress.pct > 60 && progress.pct <= 80}>• Filtering noise from spectral data...</div>
        <div class="log-line" class:active={progress.pct > 80} class:current={progress.pct > 80}>• Contextualizing cross-references...</div>
      </div>
    </div>
  {:else if !result}
    <div class="state-screen empty">
      <div class="empty-icon">
        <svg viewBox="0 0 80 80" fill="none">
          <circle
            cx="40"
            cy="40"
            r="38"
            stroke="rgba(108,142,251,0.18)"
            stroke-width="2"
            stroke-dasharray="5 4"
          />
          <path
            d="M28 52V30a2 2 0 012-2h16l6 6v18a2 2 0 01-2 2H30a2 2 0 01-2-2z"
            stroke="rgba(108,142,251,0.4)"
            stroke-width="1.5"
          />
          <path
            d="M46 28v8h8M34 44h12M34 49h8"
            stroke="rgba(108,142,251,0.4)"
            stroke-width="1.5"
            stroke-linecap="round"
          />
        </svg>
      </div>
      <p class="empty-title">ยังไม่มีผลลัพธ์</p>
      <p class="empty-sub">อัปโหลด PDF และกด "ประมวลผล" เพื่อดูผลการตรวจสอบ</p>
    </div>
  {:else}
    <!-- ─── Results ─── -->
    <!-- ── Header bar ── -->
    <div class="result-header">
      <div style="display: flex; align-items: center; justify-content: space-between;">
        <div class="result-title-section">
          <div class="badge-success">
            <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
               <path fill-rule="evenodd" d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" clip-rule="evenodd" />
            </svg>
            สำเร็จเรียบร้อย
          </div>
          <div class="result-id">ID: SPX-2024-0822</div>
        </div>
        <button class="btn-back" on:click={closeResults} title="ยกเลิก/กลับไปหน้า Scan" style="display: flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); color: var(--text2); padding: 6px 12px; border-radius: 6px; cursor: pointer; font-family: inherit; font-size: 12px; font-weight: 500; transition: all 0.2s;" on:mouseover={e => e.currentTarget.style.background='rgba(239, 68, 68, 0.15)'} on:mouseout={e => e.currentTarget.style.background='rgba(255,255,255,0.05)'}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          กลับหน้าหลัก
        </button>
      </div>

      <div class="result-file-section">
        <h2 class="filename" title={result.filename}>{result.filename}</h2>
        <svg viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" width="18" height="18" style="cursor: pointer;"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
        <div class="spacer"></div>
        <div class="header-actions">
          <button class="btn-copy">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            คัดลอก
          </button>
          <button class="btn-dl-md" on:click={exportTxt}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            ดาวน์โหลด Markdown
          </button>
        </div>
      </div>
    </div>

    <!-- ── Main Grid ── -->
    <div class="result-grid">
      <!-- Left Column (Markdown) -->
      <div class="left-panel">
        <div class="panel-header">
          <div class="tabs">
            <button class="tab" class:active={viewMode === 'markdown'} on:click={() => viewMode = 'markdown'}>พรีวิว Markdown</button>
            <button class="tab" class:active={viewMode === 'json'} on:click={() => viewMode = 'json'}>ข้อมูล JSON</button>
            <button class="tab" class:active={viewMode === 'vector'} on:click={() => viewMode = 'vector'}>ข้อมูล Vector</button>
          </div>
          <div class="header-right">
            <span class="time-taken">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
              ใช้เวลา 1.2 วินาที
            </span>
            <button class="icon-btn-sm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg></button>
          </div>
        </div>
        <div class="markdown-content">
          {#if viewMode === 'markdown'}
            {@html markdownHtml}
          {:else if viewMode === 'json'}
            <pre style="color: var(--text); font-family: monospace; font-size: 13px;">{JSON.stringify(result, null, 2)}</pre>
          {:else}
            <div style="color: var(--text3); padding: 32px; text-align: center;">Vector Data Mockup...</div>
          {/if}
        </div>
      </div>

      <!-- Right Column (Sidebar) -->
      <div class="right-panel">
        <div class="status-section">
           <div class="status-label">สถานะการประมวลผล</div>
           <div class="accuracy-row">
             <span>ความถูกต้องของ OCR</span>
             <span class="accuracy-val">{ocrAccuracy}%</span>
           </div>
           <div class="progress-bar">
             <div class="progress-fill" style="width: {ocrAccuracy}%"></div>
           </div>
        </div>

        <div class="entities-section">
          <div class="entities-label">เอนทิตีที่ตรวจพบ (ENTITIES)</div>
          <div class="entities-tags">
            <span class="tag">ERP-Super</span>
            <span class="tag">Microservices</span>
            <span class="tag pink">PostgreSQL</span>
            <span class="tag">React</span>
            <span class="tag">GraphQL</span>
          </div>
        </div>

        <div class="ai-suggestion-card">
          <div class="ai-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>
            AI Suggestion
          </div>
          <div class="ai-body">
            ตรวจพบส่วนที่เป็น Code/Architecture แนะนำให้จัดเก็บในหมวดหมู่ Technical Documentation
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<!-- ── All-errors sidebar (right of right panel) ── -->
<!-- removed: now in error-table grouped by page -->

<!-- ── Save Modal ── -->
{#if showSaveModal}
  <div class="modal-backdrop" on:click={() => showSaveModal = false}>
    <div class="modal-content" on:click|stopPropagation>
      <h3>บันทึกเอกสารเข้า Project</h3>
      
      <div class="form-group">
        <label for="save-filename">ชื่อไฟล์</label>
        <input id="save-filename" type="text" bind:value={saveForm.filename} class="form-input" />
      </div>

      <div class="form-group">
        <label for="save-project">โครงการ (Project)</label>
        <select id="save-project" bind:value={saveForm.project_id} class="form-input">
          <option value="" disabled>-- เลือกโครงการ --</option>
          {#each projects as p}
            <option value={p.id}>{p.project_code} - {p.name}</option>
          {/each}
        </select>
      </div>

      <div class="form-group">
        <label for="save-category">หมวดหมู่เอกสาร</label>
        <select id="save-category" bind:value={saveForm.doc_category} class="form-input">
          <option value="Reference">เอกสารอ้างอิง (Reference)</option>
          <option value="TestCase">TestCase</option>
          <option value="Requirements">Requirements</option>
          <option value="Other">อื่นๆ (Other)</option>
        </select>
      </div>

      <div class="form-group" style="display: none;">
        <!-- label hidden -->
        <select id="save-type" bind:value={saveForm.doc_type} class="form-input">
          <option value="PDF">PDF</option>
          <option value="Image">Image</option>
          <option value="Word">Word</option>
        </select>
      </div>

      <div class="form-group toggle-group">
        <span class="label-text">กำหนดเป็น Golden Data</span>
        <label class="toggle-wrap">
          <input type="checkbox" bind:checked={saveForm.is_golden_data}/>
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
        </label>
      </div>

      <div class="modal-actions">
        <button class="btn-cancel" on:click={() => showSaveModal = false} disabled={isSaving}>ยกเลิก</button>
        <button class="btn-save" on:click={saveToProject} disabled={isSaving || !saveForm.project_id || !saveForm.filename}>
          {#if isSaving} กำลังบันทึก... {:else} บันทึก {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Confirm Close Modal ── -->
{#if showConfirmModal}
  <div class="modal-backdrop" on:click={cancelClose}>
    <div class="modal-content confirm-modal" on:click|stopPropagation>
      <div class="modal-icon warning-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 class="confirm-title">ยืนยันการออกจากหน้าผลลัพธ์?</h3>
      <p class="confirm-desc">ข้อมูลผลลัพธ์ที่คุณยังไม่ได้บันทึกเข้า Project อาจสูญหาย คุณต้องการกลับไปหน้า Scan OCR ใช่หรือไม่?</p>
      <div class="modal-actions confirm-actions">
        <button class="btn-cancel" on:click={cancelClose}>ยกเลิก</button>
        <button class="btn-confirm-danger" on:click={confirmClose}>ออกจากหน้านี้</button>
      </div>
    </div>
  </div>
{/if}

<style>
  /* ── Shell ── */
  .rp {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    background: var(--bg);
  }

  /* ── State screens ── */
  .state-screen {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 16px;
    padding: 40px;
  }
  .empty-icon {
    opacity: 0.6;
    margin-bottom: 8px;
  }
  .empty-title {
    font-size: 17px;
    font-weight: 600;
    color: var(--text2);
  }
  .empty-sub {
    font-size: 13px;
    color: var(--text3);
    text-align: center;
    max-width: 320px;
    line-height: 1.7;
  }

  /* ── Progress ── */
  .prog-wrap {
    width: 100%;
    max-width: 400px;
    text-align: center;
  }
  .prog-label {
    font-size: 15px;
    font-weight: 600;
    color: var(--primary2);
    margin-bottom: 14px;
  }
  .prog-track {
    height: 5px;
    background: var(--surface2);
    border-radius: 3px;
    overflow: hidden;
    margin-bottom: 20px;
  }
  .prog-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--accent));
    transition: width 0.5s ease;
    box-shadow: 0 0 10px var(--glow);
  }
  .steps {
    display: flex;
    justify-content: center;
    gap: 24px;
  }
  .step {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text3);
  }
  .step.active {
    color: var(--primary2);
  }
  .step.done {
    color: var(--success);
  }
  .step-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: currentColor;
    flex-shrink: 0;
  }
  .step.active .step-dot {
    animation: pulse 1.4s infinite;
  }
  @keyframes pulse {
    0%,
    100% {
      transform: scale(1);
    }
    50% {
      transform: scale(1.5);
    }
  }

  /* ── Result Dashboard Header ── */
  .result-header {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px 24px;
    background: transparent;
  }
  .result-title-section {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .badge-success {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(14, 165, 233, 0.15); /* light blue bg */
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 11px;
    font-weight: 600;
  }
  .result-id {
    font-size: 12px;
    color: #94a3b8;
    font-family: monospace;
  }
  .result-file-section {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .filename {
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    margin: 0;
  }
  .spacer {
    flex: 1;
  }
  .header-actions {
    display: flex;
    gap: 12px;
  }
  .btn-copy {
    display: flex; align-items: center; gap: 6px;
    background: transparent; border: 1px solid #334155;
    color: #e2e8f0; padding: 6px 14px; border-radius: 8px;
    font-size: 12px; font-weight: 600; cursor: pointer;
  }
  .btn-copy:hover { background: rgba(255,255,255,0.05); }
  .btn-dl-md {
    display: flex; align-items: center; gap: 6px;
    background: rgba(30, 41, 59, 0.5); border: 1px solid #3b82f6;
    color: #93c5fd; padding: 6px 14px; border-radius: 8px;
    font-size: 12px; font-weight: 600; cursor: pointer;
  }
  .btn-dl-md:hover { background: rgba(59, 130, 246, 0.1); }

  /* ── Main Grid ── */
  .result-grid {
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 24px;
    padding: 0 24px 24px;
    flex: 1;
    min-height: 0;
  }

  /* Left Panel */
  .left-panel {
    background: #0f111a;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.05);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .panel-header {
    display: flex; justify-content: space-between; align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding: 0 24px;
  }
  .tabs {
    display: flex; gap: 24px;
  }
  .tab {
    background: none; border: none; padding: 16px 4px;
    color: #94a3b8; font-size: 13px; font-weight: 600;
    cursor: pointer; border-bottom: 2px solid transparent;
  }
  .tab.active {
    color: #c4b5fd; border-bottom: 2px solid #8b5cf6;
  }
  .header-right {
    display: flex; align-items: center; gap: 16px;
  }
  .time-taken {
    display: flex; align-items: center; gap: 6px;
    font-size: 11px; color: #94a3b8;
  }
  .icon-btn-sm {
    background: none; border: none; color: #94a3b8; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }
  .icon-btn-sm:hover { color: #fff; }
  .markdown-content {
    flex: 1; overflow-y: auto;
    padding: 32px; background: #1a1c23;
    font-family: monospace; font-size: 14px; line-height: 1.6;
    color: #cbd5e1; white-space: pre-wrap;
  }
  .markdown-content::-webkit-scrollbar { width: 6px; }
  .markdown-content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

  /* Right Panel */
  .right-panel {
    display: flex; flex-direction: column; gap: 32px;
    padding-top: 12px;
  }
  .status-section {
    display: flex; flex-direction: column; gap: 12px;
  }
  .status-label { font-size: 12px; font-weight: 600; color: #94a3b8; }
  .accuracy-row { display: flex; justify-content: space-between; font-size: 13px; color: #e2e8f0; }
  .accuracy-val { font-weight: 700; color: #fff; }
  .progress-bar { width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
  .progress-fill { height: 100%; background: #c4b5fd; }

  .entities-section { display: flex; flex-direction: column; gap: 12px; margin-top: 8px;}
  .entities-label { font-size: 12px; font-weight: 600; color: #94a3b8; text-transform: uppercase; }
  .entities-tags { display: flex; flex-wrap: wrap; gap: 8px; }
  .tag {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    color: #94a3b8; padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 500;
  }
  .tag.pink {
    background: rgba(236, 72, 153, 0.1); border: 1px solid rgba(236, 72, 153, 0.3); color: #f472b6;
  }

  .ai-suggestion-card {
    background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px; padding: 16px;
  }
  .ai-header {
    display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; color: #c4b5fd; margin-bottom: 8px;
  }
  .ai-body { font-size: 13px; color: #94a3b8; line-height: 1.5; }
  .no-sugg {
    color: var(--text3);
    font-size: 13px;
  }

  /* ── Highlight view ── */
  .highlight-view {
    line-height: 2.2;
    font-size: 15px;
    white-space: pre-wrap;
    word-break: break-word;
  }
  :global(.tok-err-fmt) {
    color: var(--warning);
    background: rgba(245, 158, 11, 0.08);
    border-bottom: 2px dashed var(--warning);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  :global(.tok-err-th) {
    color: var(--danger);
    background: rgba(248, 113, 113, 0.1);
    border-bottom: 2px solid var(--danger);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  :global(.tok-err-en) {
    color: var(--warning);
    background: rgba(251, 191, 36, 0.1);
    border-bottom: 2px solid var(--warning);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  :global(.tok-err-sm) {
    color: var(--semantic);
    background: rgba(168, 85, 247, 0.1);
    border-bottom: 2px solid var(--semantic);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  .word-sm {
    color: var(--semantic);
  }

  /* ── Plain text ── */
  .plain-view {
    font-family: var(--font-en);
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text);
    line-height: 1.9;
  }

  /* ── HTML Rendered ── */
  .rendered-html :global(.table-container) {
    width: 100%;
    overflow-x: auto;
    margin: 16px 0;
    border-radius: 8px;
    border: 1px solid var(--border2);
  }
  .rendered-html :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    color: var(--text);
    background: var(--surface);
  }
  .rendered-html :global(th),
  .rendered-html :global(td) {
    border: 1px solid var(--border2);
    padding: 8px 12px;
    text-align: left;
  }
  .rendered-html :global(th) {
    background: var(--surface2);
    font-weight: bold;
  }
  .rendered-html :global(div[align="center"]) {
    text-align: center;
    font-weight: bold;
    margin: 12px 0;
  }

  /* ── Preview View ── */
  .content-scroll.is-preview {
    padding: 0;
    background: var(--bg3);
  }
  .preview-container {
    display: flex;
    justify-content: center;
    padding: 20px;
    min-height: 100%;
  }
  .page-wrap {
    position: relative;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
    background: white;
    line-height: 0;
  }
  .page-img {
    max-width: 100%;
    height: auto;
    display: block;
  }
  .overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }
  .error-box {
    position: absolute;
    pointer-events: auto;
    border: 1px solid transparent;
    border-radius: 2px;
    mix-blend-mode: multiply;
    opacity: 0.4;
    transition: all 0.2s;
    cursor: help;
  }
  .error-box.th {
    background: #f87171;
    border-color: #ef4444;
  }
  .error-box.en {
    background: #fbbf24;
    border-color: #f59e0b;
  }
  .error-box.sm {
    background: #a855f7;
    border-color: #8b5cf6;
  }
  .error-box.fmt {
    background: #fbbf24;
    border: 1px dashed #d97706;
  }

  .error-box:hover {
    opacity: 0.8;
    z-index: 10;
    transform: scale(1.05);
    box-shadow: 0 0 12px rgba(0, 0, 0, 0.2);
  }

  /* ── Manual Spellcheck ── */
  .manual-check-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    gap: 16px;
    color: var(--text2);
    text-align: center;
  }
  .manual-check-box svg {
    color: var(--primary);
    opacity: 0.8;
    margin-bottom: 8px;
  }
  .manual-check-box p {
    font-size: 15px;
    margin: 0;
  }
  .btn-check {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 24px;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    color: white;
    border: none;
    border-radius: var(--radius);
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    box-shadow: 0 4px 12px var(--glow);
    transition: all 0.2s;
  }
  .btn-check:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px var(--glow);
  }
  .btn-check:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* ── Save Modal ── */
  .modal-backdrop {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(10, 15, 30, 0.6);
    backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center;
    z-index: 9999;
  }
  .modal-content {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    width: 400px;
    max-width: 90vw;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  }
  .modal-content h3 {
    margin: 0 0 20px 0;
    font-size: 16px;
    color: var(--text);
  }
  .form-group {
    margin-bottom: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .form-group label, .label-text {
    font-size: 13px;
    color: var(--text2);
    font-weight: 500;
  }
  .form-input {
    background: var(--bg3);
    border: 1px solid var(--border2);
    color: var(--text);
    padding: 8px 12px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
  }
  .form-input:focus {
    border-color: var(--primary);
  }
  .toggle-group {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
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
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
  }
  .btn-cancel {
    background: transparent;
    border: 1px solid var(--border2);
    color: var(--text2);
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
  }
  .btn-save {
    background: var(--primary);
    border: none;
    color: white;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-weight: 500;
  }
  .btn-save:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ── Confirm Modal ── */
  .confirm-modal {
    max-width: 400px;
    text-align: center;
    padding: 32px 24px;
  }
  .modal-icon.warning-icon {
    width: 64px;
    height: 64px;
    margin: 0 auto 16px;
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .confirm-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--text);
  }
  .confirm-desc {
    font-size: 14px;
    color: var(--text2);
    margin-bottom: 24px;
    line-height: 1.5;
  }
  .confirm-actions {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-top: 0;
  }
  .btn-confirm-danger {
    background: #ef4444;
    border: none;
    color: white;
    padding: 8px 24px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-weight: 500;
    transition: background 0.2s;
  }
  .btn-confirm-danger:hover {
    background: #dc2626;
  }

  /* ── Processing Screen ── */
  .processing-screen {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 500px;
    font-family: 'Prompt', monospace;
  }

  .proc-header {
    text-align: center;
    margin-bottom: 40px;
  }
  .proc-title {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 8px 0;
    background: linear-gradient(90deg, #fcd34d, #38bdf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .proc-subtitle {
    font-size: 14px;
    color: #94a3b8;
    margin: 0;
  }

  .proc-box {
    width: 100%;
    max-width: 500px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 0 40px rgba(0, 0, 0, 0.3), inset 0 0 20px rgba(255,255,255,0.02);
    margin-bottom: 30px;
  }

  .proc-box-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 16px;
  }
  .proc-status-col {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .lbl-status {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
    letter-spacing: 1.5px;
  }
  .proc-current-step {
    font-size: 16px;
    font-weight: 700;
    color: #e2e8f0;
  }
  .lbl-pct {
    font-size: 18px;
    font-weight: 700;
    color: #e2e8f0;
  }

  .proc-track-bg {
    width: 100%;
    height: 8px;
    background: #1e293b;
    border-radius: 4px;
    overflow: hidden;
  }
  .proc-track-fill {
    height: 100%;
    background: linear-gradient(90deg, #38bdf8, #c084fc, #ec4899);
    border-radius: 4px;
    transition: width 0.3s ease;
    box-shadow: 0 0 10px rgba(192, 132, 252, 0.5);
  }
  .proc-eta {
    margin-top: 16px;
    font-size: 12px;
    color: #94a3b8;
    text-align: right;
  }

  .proc-logs {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
    max-width: 460px;
  }
  .log-line {
    font-size: 13px;
    color: rgba(255, 255, 255, 0.1);
    font-family: monospace;
    transition: color 0.3s;
  }
  .log-line.active {
    color: rgba(255, 255, 255, 0.4);
  }
  .log-line.current {
    color: #94a3b8;
    text-shadow: 0 0 5px rgba(255,255,255,0.2);
  }
</style>
