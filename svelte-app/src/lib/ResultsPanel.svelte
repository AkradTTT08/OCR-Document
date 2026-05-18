<script>
  import { toast } from './toastStore.js';
  export let result = null;
  export let isProcessing = false;
  export let progress = { pct: 0, label: "", step: 0 };

  // ── View state ──
  let activePageIdx = 0;
  let viewMode = "errors"; // 'errors' | 'highlight' | 'text'
  let filterLang = "all"; // 'all' | 'thai' | 'english'

  // ── Derived ──
  $: pages = result?.pages ?? [];
  $: activePage = pages[activePageIdx] ?? null;
  $: allErrors = collectAllErrors(pages);
  $: pageErrors = activePage?.spell_check?.errors ?? [];
  $: filteredErrors =
    filterLang === "all"
      ? pageErrors
      : pageErrors.filter((e) => e.lang === filterLang);

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

  function sumSummaryField(pages, field) {
    return pages.reduce(
      (acc, p) => acc + (p.spell_check?.summary?.[field] ?? 0),
      0,
    );
  }

  function collectAllErrors(pages) {
    return pages.flatMap((p) =>
      (p.spell_check?.errors ?? []).map((e) => ({ ...e, page: p.page_number })),
    );
  }

  $: highlightedHtml = generateHighlightedHtml(activePage?.text, activePage?.spell_check?.errors);

  function generateHighlightedHtml(text, errors) {
    if (!text) return "";
    if (!errors || errors.length === 0) return text;

    // 1. Extract all HTML tags and replace them with a unique placeholder
    const tags = [];
    let safeText = text.replace(/<[^>]+>/g, (match) => {
      tags.push(match);
      return `__TAG_${tags.length - 1}__`;
    });

    // 2. Replace errors in the safeText
    errors.forEach(err => {
      if (!err.token || err.token.trim() === "") return;
      const safeToken = err.token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      
      let cssClass = 'tok-err-th';
      let title = `สะกดผิด | แนะนำ: ${(err.suggestions || []).join(', ')}`;
      
      if (err.error_type === "semantic") {
        cssClass = 'tok-err-sm';
        title = `บริบท | แนะนำ: ${(err.suggestions || []).join(', ')}`;
      } else if (err.lang === "english") {
        cssClass = 'tok-err-en';
        title = `Misspelled | Suggestions: ${(err.suggestions || []).join(', ')}`;
      }
      
      let regexStr = safeToken;
      if (err.lang === "english") {
        regexStr = `\\b${safeToken}\\b`;
      }
      
      const regex = new RegExp(regexStr, 'g');
      const replacement = `<span class="${cssClass}" title="${title}">${err.token}</span>`;
      
      safeText = safeText.replace(regex, replacement);
    });

    // 3. Restore HTML tags
    let finalHtml = safeText.replace(/__TAG_(\d+)__/g, (match, p1) => {
      return tags[parseInt(p1, 10)];
    });

    return finalHtml;
  }

  // ── Export ──
  function exportTxt() {
    if (!result) return;
    const text = result.pages
      .map((p) => `=== หน้า ${p.page_number} ===\n${p.text}`)
      .join("\n\n");
    downloadFile(text, "ocr_result.txt");
  }
  function exportReport() {
    if (!result) return;
    let r = `=== รายงาน OCR + ตรวจสอบคำ ===\nไฟล์: ${result.filename}\nหน้าทั้งหมด: ${result.total_pages}\n`;
    r += `คำไทย: ${totalThai.toLocaleString()} | คำอังกฤษ: ${totalEng.toLocaleString()}\n`;
    r += `คำผิด(ไทย): ${totalThaiErr} | คำผิด(Eng): ${totalEngErr} | อัตรา: ${errRate}%\n`;
    r += `\n${"─".repeat(44)}\n\n`;
    result.pages.forEach((p) => {
      r += `=== หน้า ${p.page_number} ===\n`;
      const errors = p.spell_check?.errors ?? [];
      errors.forEach((e) => {
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
      toast(`เริ่มตรวจสอบคำผิดหน้า ${activePage.page_number}...`, 'info', 2000);
      const API = 'http://localhost:5000/api';
      const res = await fetch(`${API}/spellcheck`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text: activePage.text, 
          words: activePage.words,
          include_suggestions: true 
        })
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'เกิดข้อผิดพลาด');
      
      // Update page data
      result.pages[activePageIdx].spell_check = data.result;
      
      // Trigger reactivity
      result = result; 
      toast(`ตรวจสอบคำผิดหน้า ${activePage.page_number} เสร็จสิ้น`, 'success');
    } catch (err) {
      toast(`ข้อผิดพลาด: ${err.message}`, 'error');
    } finally {
      checkingSpell = false;
    }
  }
</script>

<!-- ── RIGHT PANEL ── -->
<div class="rp">
  <!-- ─── Empty / Processing State ─── -->
  {#if isProcessing}
    <div class="state-screen">
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
    <div class="page-tabs-bar">
      {#each pages as p, i}
        <button
          class="page-tab"
          class:active={activePageIdx === i}
          on:click={() => (activePageIdx = i)}
        >
          <span>หน้า {p.page_number}</span>
          {#if (p.spell_check?.summary?.error_count ?? 0) > 0}
            <span class="err-badge">{p.spell_check.summary.error_count}</span>
          {/if}
        </button>
      {/each}
    </div>

    <!-- ── View mode tabs + filter ── -->
    <div class="toolbar">
      <div class="view-tabs">
        {#each [["errors", "คำผิด"], ["highlight", "ไฮไลท์"], ["text", "ข้อความดิบ"], ["preview", "พรีวิว"]] as [v, label]}
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
                      class:th={err.lang === "thai"}
                      class:en={err.lang === "english"}
                      class:sm={err.error_type === "semantic"}
                      style="
                        left: {err.box_norm
                          ? err.box_norm[0][0] * 100
                          : (err.box[0][0] / activePage.width) * 100}%;
                        top: {err.box_norm
                          ? err.box_norm[0][1] * 100
                          : (err.box[0][1] / activePage.height) * 100}%;
                        width: {err.box_norm
                          ? (err.box_norm[1][0] - err.box_norm[0][0]) * 100
                          : ((err.box[1][0] - err.box[0][0]) /
                              activePage.width) *
                            100}%;
                        height: {err.box_norm
                          ? (err.box_norm[2][1] - err.box_norm[0][1]) * 100
                          : ((err.box[2][1] - err.box[0][1]) /
                              activePage.height) *
                            100}%;
                      "
                      title="{err.token} → {(err.suggestions || []).join(
                        ', ',
                      ) || '—'}"
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
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="40" height="40" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
            <p>ยังไม่ได้ตรวจสอบคำผิดในหน้านี้</p>
            <button class="btn-check" on:click={runManualSpellCheck} disabled={checkingSpell}>
              {#if checkingSpell}
                <div class="spinner"></div> กำลังตรวจสอบ...
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
                    err.error_type !== "semantic"}
                  class:word-en={err.lang === "english"}
                  class:word-sm={err.error_type === "semantic"}
                >
                  {err.token}
                </span>
                <span>
                  {#if err.error_type === "semantic"}
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

        <!-- PLAIN TEXT VIEW (HTML/Markdown Rendered) -->
      {:else}
        <div class="plain-view rendered-html">
          {@html activePage?.text ?? ""}
        </div>
      {/if}
    </div>
    <!-- end results -->
  {/if}
</div>

<!-- ── All-errors sidebar (right of right panel) ── -->
<!-- removed: now in error-table grouped by page -->

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
    color: var(--text2);
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
    background: var(--surface2);
    border: 1px solid var(--border2);
    color: var(--text2);
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
  .page-tabs-bar {
    display: flex;
    gap: 6px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    overflow-x: auto;
    flex-shrink: 0;
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
  .badge-th,
  .badge-en {
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
  .tok-err-th {
    color: var(--danger);
    background: rgba(248, 113, 113, 0.1);
    border-bottom: 2px solid var(--danger);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  .tok-err-en {
    color: var(--warning);
    background: rgba(251, 191, 36, 0.1);
    border-bottom: 2px solid var(--warning);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  .tok-err-sm {
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
  .rendered-html :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0;
    color: var(--text);
    background: var(--surface);
  }
  .rendered-html :global(th), .rendered-html :global(td) {
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
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
