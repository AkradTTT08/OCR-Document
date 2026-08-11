<script>
  import { toast } from "./toastStore.js";
  import CustomSelect from "./CustomSelect.svelte";
  /** @type {any} */
  export let result = null;
  export let isProcessing = false;
  export let progress = { pct: 0, label: "", step: 0 };

  // ── View state ──
  let activePageIdx = 0;
  let viewMode = "errors"; // 'errors' | 'highlight' | 'text'
  let filterLang = "all"; // 'all' | 'thai' | 'english'
  let tabsBarElement; // Reference for scrollable tabs

  // ── Derived ──
  $: pages = result?.pages ?? [];
  $: activePage = pages[activePageIdx] ?? null;
  $: allErrors = collectAllErrors(pages);
  $: pageErrors = activePage?.spell_check?.errors ?? [];
  $: filteredErrors =
    filterLang === "all"
      ? pageErrors
      : pageErrors.filter((/** @type {any} */ e) => e.lang === filterLang);

  // Total stats across all pages
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
  let projects = [];
  $: projectSelectOptions = [
    { value: '', label: '-- เลือกโครงการ --', icon: '📁' },
    ...(projects || []).map(p => ({ 
      value: p.id || p.project_id, 
      label: `${p.project_code || ''} - ${p.name || p.project_name || ''}`, 
      icon: '📌' 
    }))
  ];

  const categorySelectOptions = [
    { value: 'Reference', label: 'เอกสารอ้างอิง (Reference)', icon: '📚' },
    { value: 'TestCase', label: 'TestCase', icon: '🧪' },
    { value: 'Requirements', label: 'Requirements', icon: '📋' },
    { value: 'Other', label: 'อื่นๆ (Other)', icon: '📁' }
  ];
  let isSaving = false;
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
        // Auto-select first project if none selected
        if (projects.length > 0 && !saveForm.project_id) {
          saveForm.project_id = projects[0].id || projects[0].project_id || '';
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

  function scrollTabsToSelected() {
    if (!tabsBarElement) return;
    setTimeout(() => {
      const activeTab = tabsBarElement.querySelector('.page-tab.active');
      if (activeTab) {
        const containerWidth = tabsBarElement.clientWidth;
        const scrollLeft = activeTab.offsetLeft - (containerWidth / 2) + (activeTab.clientWidth / 2);
        tabsBarElement.scrollTo({ left: scrollLeft, behavior: 'smooth' });
      }
    }, 50);
  }
</script>

<!-- ── RIGHT PANEL ── -->
<div class="rp">
  <!-- ─── Empty / Processing State ─── -->
  {#if isProcessing}
    <div class="state-screen">
      <div class="processing-logo-container">
        <div class="logo-pulse-ring"></div>
        <div class="logo-pulse-ring delay"></div>
        <svg class="brand-logo-anim" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"></polygon>
          <line x1="12" y1="22" x2="12" y2="15.5"></line>
          <polyline points="22 8.5 12 15.5 2 8.5"></polyline>
          <polyline points="2 15.5 12 8.5 22 15.5"></polyline>
          <line x1="12" y1="2" x2="12" y2="8.5"></line>
        </svg>
      </div>
      <div class="prog-wrap">
        <div class="prog-label">{progress.label}</div>
        <div class="prog-track">
          <div class="prog-fill" style="width:{progress.pct}%"></div>
        </div>
        <div class="steps">
          {#each ["แปลง PDF", "OCR สกัดข้อความ", "ตรวจคำผิด"] as s, i}
            <div
              class="step"
              class:active={progress.step === i + 1}
              class:done={progress.step > i + 1}
            >
              <div class="step-dot"></div>
              <span>{s}</span>
            </div>
          {/each}
        </div>
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
    <div class="rp-header">
      <div class="rp-title">
        <svg
          viewBox="0 0 16 16"
          fill="currentColor"
          width="14"
          height="14"
          style="color:var(--success)"
        >
          <path
            fill-rule="evenodd"
            d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"
            clip-rule="evenodd"
          />
        </svg>
        <span class="truncate">{result.filename}</span>
      </div>
      <div class="header-actions">
        <button class="btn-sm" style="color:var(--primary2); border-color:rgba(108,142,251,0.4);" on:click={openSaveModal} title="บันทึกเข้า Project">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          บันทึกเข้า Project
        </button>
        <button class="btn-sm" on:click={exportTxt} title="Export ข้อความ">
          <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12"
            ><path
              d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75zM7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.97a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.779a.749.749 0 111.06-1.06l1.97 1.97z"
            /></svg
          >
          .txt
        </button>
        <button class="btn-sm" on:click={exportReport} title="Export รายงาน">
          <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12"
            ><path
              d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75zM7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.97a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.779a.749.749 0 111.06-1.06l1.97 1.97z"
            /></svg
          >
          รายงาน
        </button>
      </div>
    </div>

    <!-- ── Stat cards ── -->
    <div class="stat-bar">
      <div class="stat-card">
        <div class="stat-val" style="color:var(--primary2)">
          {result.total_pages}
        </div>
        <div class="stat-lbl">หน้า</div>
      </div>
      <div class="stat-card">
        <div class="stat-val" style="color:var(--accent)">
          {totalThai.toLocaleString()}<span class="stat-sep">/</span
          >{totalEng.toLocaleString()}
        </div>
        <div class="stat-lbl">คำไทย / EN</div>
      </div>
      <div class="stat-card">
        <div class="stat-val" style="color:var(--danger)">
          {totalThaiErr}<span class="stat-sep">/</span>{totalEngErr}<span
            class="stat-sep">/</span
          ><span style="color:var(--semantic)">{totalSemantic}</span>
        </div>
        <div class="stat-lbl">ผิดไทย / Eng / บริบท</div>
      </div>
      <div class="stat-card">
        <div class="stat-val" style="color:var(--warning)">{errRate}%</div>
        <div class="stat-lbl">อัตราคำผิด</div>
      </div>
    </div>

    <!-- ── Page tabs ── -->
    <div class="page-tabs-wrapper">
      <button class="nav-tab-btn" on:click={() => { activePageIdx = 0; scrollTabsToSelected(); }} disabled={activePageIdx === 0} title="ข้ามไปหน้าแรก">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5"/></svg>
      </button>
      
      <div class="page-tabs-bar" bind:this={tabsBarElement}>
        {#each pages as p, i}
          <button
            class="page-tab"
            class:active={activePageIdx === i}
            on:click={() => { activePageIdx = i; scrollTabsToSelected(); }}
          >
            <span>หน้า {p.page_number}</span>
            {#if (p.spell_check?.summary?.error_count ?? 0) > 0}
              <span class="err-badge">{p.spell_check.summary.error_count}</span>
            {/if}
          </button>
        {/each}
      </div>

      <button class="nav-tab-btn" on:click={() => { activePageIdx = pages.length - 1; scrollTabsToSelected(); }} disabled={activePageIdx === pages.length - 1} title="ข้ามไปหน้าสุดท้าย">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 17l5-5-5-5M6 17l5-5-5-5"/></svg>
      </button>
    </div>

    <!-- ── View mode tabs + filter ── -->
    <div class="toolbar">
      <div class="view-tabs">
        {#each [["errors", "คำผิด"], ["highlight", "ไฮไลท์"], ["markdown", "มาร์กดาวน์"], ["text", "ข้อความดิบ"], ["preview", "พรีวิว"]] as [v, label]}
          <button
            class="vtab"
            class:active={viewMode === v}
            on:click={() => (viewMode = v)}>{label}</button
          >
        {/each}
      </div>
      {#if viewMode === "errors"}
        <div class="lang-filter">
          {#each [["all", "ทั้งหมด"], ["thai", "🇹🇭 ไทย"], ["english", "🇬🇧 Eng"]] as [v, label]}
            <button
              class="filter-btn"
              class:active={filterLang === v}
              on:click={() => (filterLang = v)}>{label}</button
            >
          {/each}
        </div>
      {/if}
    </div>

    <!-- ── Content ── -->
    <div class="content-scroll" class:is-preview={viewMode === "preview"}>
      <!-- PREVIEW VIEW (NEW) -->
      {#if viewMode === "preview"}
        <div class="preview-container">
          {#if activePage}
            <div class="page-wrap">
              <img
                src="http://localhost:5000/api/view/{activePage.session_id}/{activePage.page_number}"
                alt="Page {activePage.page_number}"
                class="page-img"
              />

              <!-- Highlight Overlay -->
              <div class="overlay">
                {#each activePage.spell_check?.errors || [] as err}
                  {#if err.box}
                    <div
                      class="error-box"
                      class:th={err.lang === "thai" &&
                        err.error_type !== "format" &&
                        err.error_type !== "semantic"}
                      class:en={err.lang === "english"}
                      class:sm={err.error_type === "semantic"}
                      class:fmt={err.error_type === "format"}
                      style="
                        left: {err.box_norm
                        ? err.box_norm[0][0] * 100
                        : (err.box[0][0] / activePage.width) * 100}%;
                        top: {err.box_norm
                        ? err.box_norm[0][1] * 100
                        : (err.box[0][1] / activePage.height) * 100}%;
                        width: {err.box_norm
                        ? (err.box_norm[1][0] - err.box_norm[0][0]) * 100
                        : ((err.box[1][0] - err.box[0][0]) / activePage.width) *
                          100}%;
                        height: {err.box_norm
                        ? (err.box_norm[2][1] - err.box_norm[0][1]) * 100
                        : ((err.box[2][1] - err.box[0][1]) /
                            activePage.height) *
                          100}%;
                      "
                      title="{err.error_type === 'format'
                        ? 'ฟอร์แมตผิด: ' + (err.message || '')
                        : err.token} → {(err.suggestions || []).join(', ') ||
                        '—'}"
                    ></div>
                  {/if}
                {/each}
              </div>
            </div>
          {/if}
        </div>

        <!-- ERRORS VIEW -->
      {:else if viewMode === "errors"}
        {#if !activePage?.spell_check}
          <div class="manual-check-box">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              width="40"
              height="40"
              stroke-width="1.5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
              />
            </svg>
            <p>ยังไม่ได้ตรวจสอบคำผิดในหน้านี้</p>
            <button
              class="btn-check"
              on:click={runManualSpellCheck}
              disabled={checkingSpell}
            >
              {#if checkingSpell}
                <div class="spinner"></div>
                 กำลังตรวจสอบ...
              {:else}
                🔍 เริ่มตรวจสอบคำผิด
              {/if}
            </button>
          </div>
        {:else if filteredErrors.length === 0}
          <div class="no-errors">
            <svg
              viewBox="0 0 20 20"
              fill="currentColor"
              width="28"
              height="28"
              style="color:var(--success)"
            >
              <path
                fill-rule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clip-rule="evenodd"
              />
            </svg>
            <p>ไม่พบคำผิดในหน้านี้ ✨</p>
          </div>
        {:else}
          <div class="error-table">
            <div class="et-head">
              <span>บรรทัด</span>
              <span>คำที่ผิด</span>
              <span>ภาษา</span>
              <span>คำแนะนำ</span>
            </div>
            {#each filteredErrors as err}
              <div class="et-row">
                <span class="et-line">บรรทัด {err.line_number}</span>
                <span
                  class="et-word"
                  class:word-th={err.lang === "thai" &&
                    err.error_type !== "semantic" &&
                    err.error_type !== "format"}
                  class:word-en={err.lang === "english"}
                  class:word-sm={err.error_type === "semantic"}
                  class:word-fmt={err.error_type === "format"}
                >
                  {err.token}
                </span>
                <span>
                  {#if err.error_type === "format"}
                    <span class="badge-fmt">FMT</span>
                  {:else if err.error_type === "semantic"}
                    <span class="badge-sm">SEM</span>
                  {:else if err.lang === "thai"}
                    <span class="badge-th">TH</span>
                  {:else}
                    <span class="badge-en">EN</span>
                  {/if}
                </span>
                <span class="et-suggs">
                  {#if err.suggestions?.length}
                    {#each err.suggestions.slice(0, 4) as s}
                      <span class="sugg">{s}</span>
                    {/each}
                  {:else}
                    <span class="no-sugg">—</span>
                  {/if}
                </span>
              </div>
            {/each}
          </div>
        {/if}

        <!-- HIGHLIGHT VIEW -->
      {:else if viewMode === "highlight"}
        <div class="highlight-view rendered-html">
          {@html highlightedHtml}
        </div>

        <!-- MARKDOWN VIEW -->
      {:else if viewMode === "markdown"}
        <div class="markdown-view" style="padding: 16px; font-family: monospace; white-space: pre-wrap; font-size: 14px; line-height: 1.5; color: var(--text); user-select: text;">
          {activePage?.text ?? ""}
        </div>

        <!-- PLAIN TEXT VIEW (HTML/Markdown Rendered) -->
      {:else}
        <div class="plain-view rendered-html">
          {@html parseMarkdownToHtml(activePage?.text ?? "")}
        </div>
      {/if}
    </div>
    <!-- end results -->
  {/if}
</div>

<!-- ── All-errors sidebar (right of right panel) ── -->
<!-- removed: now in error-table grouped by page -->

<!-- ── Save Modal ── -->
{#if showSaveModal}
  <div class="modal-backdrop" on:click|self={() => showSaveModal = false}>
    <div class="modal-content" on:click|stopPropagation>
      <h3>บันทึกเอกสารเข้า Project</h3>
      
      <div class="form-group">
        <label for="save-filename">ชื่อไฟล์</label>
        <input id="save-filename" type="text" bind:value={saveForm.filename} class="form-input" />
      </div>

      <div class="form-group">
        <label for="save-project">โครงการ (Project)</label>
        <CustomSelect 
          id="save-project" 
          bind:value={saveForm.project_id} 
          options={projectSelectOptions} 
          width="100%"
        />
      </div>

      <div class="form-group">
        <label for="save-category">หมวดหมู่เอกสาร</label>
        <CustomSelect 
          id="save-category" 
          bind:value={saveForm.doc_category} 
          options={categorySelectOptions} 
          width="100%"
        />
      </div>

      <div class="form-group" style="display: none;">
        <!-- label hidden -->
        <select id="save-type" bind:value={saveForm.doc_type} class="form-input">
          <option value="PDF">PDF</option>
          <option value="Image">Image</option>
          <option value="Word">Word</option>
        </select>
      </div>

      <div class="form-group toggle-group" style="margin: 16px 0; background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; display: flex; flex-direction: row; justify-content: space-between; align-items: center;">
        <span class="label-text">กำหนดเป็น Golden Data</span>
        <label class="toggle-wrap">
          <input type="checkbox" bind:checked={saveForm.is_golden_data}/>
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
        </label>
      </div>

      <div class="modal-actions">
        <button class="btn-cancel" on:click={() => showSaveModal = false} disabled={isSaving}>ยกเลิก</button>
        <button 
          class="btn-save" 
          on:click={saveToProject} 
          disabled={isSaving || !saveForm.project_id}
        >
          {#if isSaving}
            <span class="save-spinner"></span> กำลังบันทึก...
          {:else}
            💾 บันทึก
          {/if}
        </button>
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
    background: transparent;
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
    font-family: var(--font-th);
    font-size: 17px;
    font-weight: 600;
    color: var(--text-main);
  }
  .empty-sub {
    font-family: var(--font-th);
    font-size: 13px;
    color: var(--text-muted);
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

  /* ── Animated Logo ── */
  .processing-logo-container {
    position: relative;
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 20px;
  }
  .brand-logo-anim {
    width: 50px;
    height: 50px;
    color: var(--primary2);
    filter: drop-shadow(0 0 10px var(--primary));
    animation: float 3s ease-in-out infinite, pulse-glow 2s infinite;
    z-index: 2;
  }
  .logo-pulse-ring {
    position: absolute;
    width: 100%;
    height: 100%;
    border: 2px solid var(--primary);
    border-radius: 50%;
    animation: ripple 2s linear infinite;
    opacity: 0;
  }
  .logo-pulse-ring.delay {
    animation-delay: 1s;
  }
  @keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
  }
  @keyframes pulse-glow {
    0%, 100% { filter: drop-shadow(0 0 10px var(--primary)); }
    50% { filter: drop-shadow(0 0 25px var(--accent)); color: var(--accent); }
  }
  @keyframes ripple {
    0% { transform: scale(0.8); opacity: 0.8; }
    100% { transform: scale(2); opacity: 0; }
  }

  /* ── Header ── */
  .rp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    gap: 12px;
  }
  .rp-title {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
    min-width: 0;
  }
  .header-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
  .btn-sm {
    display: flex;
    align-items: center;
    gap: 5px;
    background: var(--glass-bg-hover);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-family: var(--font-th);
    font-size: 12px;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-sm:hover {
    color: var(--success);
    border-color: rgba(52, 211, 153, 0.4);
  }
  .btn-copy {
    display: flex; align-items: center; gap: 6px;
    background: var(--glass-bg-hover); border: 1px solid var(--glass-border);
    color: var(--text-main); padding: 8px 16px; border-radius: var(--radius-sm);
    font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.3s;
    font-family: var(--font-th);
  }
  .btn-copy:hover { background: rgba(255,255,255,0.08); border-color: var(--glass-border-light); transform: translateY(-1px); }
  .btn-dl-md {
    display: flex; align-items: center; gap: 6px;
    background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3);
    color: var(--primary); padding: 8px 16px; border-radius: var(--radius-sm);
    font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.3s;
    font-family: var(--font-th);
  }
  .btn-dl-md:hover { background: rgba(99, 102, 241, 0.25); transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2); }

  /* ── Stat bar ── */
  .stat-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .stat-card {
    flex: 1;
    padding: 12px 16px;
    text-align: center;
    border-right: 1px solid var(--border);
  }
  .stat-card:last-child {
    border-right: none;
  }
  .stat-val {
    font-size: 20px;
    font-weight: 700;
    line-height: 1.1;
  }
  .stat-sep {
    font-size: 14px;
    color: var(--text3);
    margin: 0 2px;
  }
  .stat-lbl {
    font-size: 10px;
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 3px;
  }


  /* ── Page tabs ── */
  .page-tabs-wrapper {
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--border);
    background: transparent;
  }
  .nav-tab-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    padding: 10px 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    flex-shrink: 0;
  }
  .nav-tab-btn:hover:not(:disabled) {
    color: var(--primary2);
    background: rgba(108, 142, 251, 0.1);
  }
  .nav-tab-btn:disabled {
    opacity: 0.2;
    cursor: not-allowed;
  }
  .nav-tab-btn svg {
    width: 18px;
    height: 18px;
  }
  .page-tabs-bar {
    display: flex;
    gap: 6px;
    padding: 10px 8px;
    overflow-x: auto;
    flex-shrink: 1;
    scroll-behavior: smooth;
  }
  .page-tabs-bar::-webkit-scrollbar {
    height: 4px;
  }
  .page-tabs-bar::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  }
  .page-tabs-bar::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.2);
  }
  .page-tab {
    display: flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text2);
    font-family: var(--font-th);
    font-size: 12px;
    padding: 5px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.18s;
    flex-shrink: 0;
  }
  .page-tab.active {
    background: rgba(108, 142, 251, 0.13);
    border-color: var(--primary);
    color: var(--primary2);
    box-shadow: 0 0 8px var(--glow);
  }
  .err-badge {
    background: var(--danger);
    color: #fff;
    border-radius: 99px;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    min-width: 18px;
    text-align: center;
  }

  /* ── Toolbar ── */
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    border-bottom: 1px solid var(--border);
    gap: 10px;
    flex-shrink: 0;
  }
  .view-tabs {
    display: flex;
    gap: 4px;
  }
  .vtab {
    background: none;
    border: 1px solid transparent;
    color: var(--text3);
    font-family: var(--font-th);
    font-size: 12px;
    padding: 5px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .vtab.active {
    background: rgba(108, 142, 251, 0.12);
    border-color: var(--primary);
    color: var(--primary2);
  }
  .lang-filter {
    display: flex;
    gap: 4px;
  }
  .filter-btn {
    background: none;
    border: 1px solid var(--border);
    color: var(--text3);
    font-family: var(--font-th);
    font-size: 11px;
    padding: 4px 9px;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.18s;
  }
  .filter-btn.active {
    background: rgba(255, 255, 255, 0.06);
    border-color: var(--border2);
    color: var(--text);
  }

  /* ── Content scroll ── */
  .content-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }

  /* ── No errors ── */
  .no-errors {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    height: 100%;
    color: var(--text3);
    font-size: 15px;
    padding: 40px;
  }

  /* ── Error table ── */
  .error-table {
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .et-head {
    display: grid;
    grid-template-columns: 90px 1fr 50px 1fr;
    gap: 12px;
    padding: 8px 14px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
    color: var(--text3);
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .et-row {
    display: grid;
    grid-template-columns: 90px 1fr 50px 1fr;
    gap: 12px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    align-items: center;
    transition: background 0.15s;
  }
  .et-row:last-child {
    border-bottom: none;
  }
  .et-row:hover {
    background: var(--surface);
  }
  .et-line {
    font-size: 12px;
    color: var(--text3);
    font-variant-numeric: tabular-nums;
  }
  .et-word {
    font-size: 16px;
    font-weight: 600;
  }
  .word-th {
    color: var(--danger);
  }
  .word-en {
    color: var(--warning);
  }
  .word-fmt {
    color: var(--warning);
  }
  .badge-th,
  .badge-en,
  .badge-fmt {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.05em;
  }
  .badge-th {
    background: rgba(248, 113, 113, 0.14);
    color: var(--danger);
    border: 1px solid rgba(248, 113, 113, 0.3);
  }
  .badge-en {
    background: rgba(251, 191, 36, 0.14);
    color: var(--warning);
    border: 1px solid rgba(251, 191, 36, 0.3);
  }
  .badge-sm {
    background: rgba(168, 85, 247, 0.14);
    color: var(--semantic);
    border: 1px solid rgba(168, 85, 247, 0.3);
  }
  .badge-fmt {
    background: rgba(245, 158, 11, 0.14);
    color: var(--warning);
    border: 1px solid rgba(245, 158, 11, 0.3);
  }
  .et-suggs {
    display: flex;
    gap: 5px;
    flex-wrap: wrap;
  }
  .sugg {
    background: rgba(52, 211, 153, 0.1);
    border: 1px solid rgba(52, 211, 153, 0.22);
    color: var(--success);
    border-radius: 99px;
    font-size: 12px;
    padding: 2px 9px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .sugg:hover {
    background: rgba(52, 211, 153, 0.2);
  }

  .no-sugg {
    color: var(--text-muted);
    font-size: 14px;
    font-family: var(--font-th);
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
    background: #4b5563; border: 1px solid #6b7280;
    position: relative; transition: all 0.25s;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: var(--primary); border-color: var(--primary);
    box-shadow: 0 0 8px var(--glow);
  }
  .toggle-thumb {
    width: 14px; height: 14px; border-radius: 50%;
    background: #ffffff; position: absolute; top: 2px; left: 2px;
    transition: all 0.25s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
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
  .save-spinner {
    display: inline-block;
    width: 12px; height: 12px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin-save 0.7s linear infinite;
    vertical-align: middle;
    margin-right: 4px;
  }
  @keyframes spin-save { to { transform: rotate(360deg); } }

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
    color: var(--text-main);
  }
  .confirm-desc {
    font-size: 14px;
    color: var(--text-muted);
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
    font-size: 12px;
    font-weight: 700;
    color: var(--text-dim);
    letter-spacing: 1.5px;
    font-family: var(--font-en);
  }
  .proc-current-step {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-main);
    font-family: var(--font-en);
  }
  .lbl-pct {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-main);
    font-family: var(--font-en);
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
