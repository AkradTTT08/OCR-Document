<script>
  import { tick } from "svelte";
  import { fade, fly } from "svelte/transition";
  import { cubicOut } from "svelte/easing";

  /** @type {Array<{page_number: number, label?: string, text?: string, has_image?: boolean, image_url?: string|null}>} */
  export let pages = [];
  /** @type {Array<any>} */
  export let findings = [];
  /** @type {Array<any>} */
  export let exitCriteriaItems = [];
  /** @type {any} */
  export let pageIssueSummary = null;
  export let filename = "";
  /** @type {number | 'global' | null} */
  export let selectedPageNumber = null;
  /** @type {number | null} */
  export let selectedFindingIndex = null;
  export let isLoadingPages = false;

  let onlyErrorPages = false;
  let viewMode = "split"; // 'split' | 'image' | 'highlight'
  let userPickedMode = false;
  let imageZoom = 100;
  let isExpanded = false;
  let textPaneEl;

  function handleWindowKeydown(e) {
    if (e.key === "Escape" && isExpanded) {
      isExpanded = false;
    }
  }

  $: indexedFindings = (findings || []).map((f, idx) => ({
    ...f,
    _idx: f.finding_index !== undefined ? f.finding_index : idx,
    _pageNum: f.page_number ? Number(f.page_number) : null,
    _sev: String(f.severity || "Info").toLowerCase()
  }));

  $: failedExitCriteria = (exitCriteriaItems || [])
    .filter(item => String(item.status || "").toUpperCase() === "FAIL")
    .map(item => {
      const nums = new Set();
      if (Array.isArray(item.page_numbers)) {
        item.page_numbers.forEach(n => { if (Number(n) > 0) nums.add(Number(n)); });
      }
      if (item.page_number && Number(item.page_number) > 0) nums.add(Number(item.page_number));
      const txt = `${item.page_ref || ""} ${item.evidence_text || ""} ${item.remarks || ""}`;
      const rx = /(?:หน้า|page|p\.)\s*[:#]?\s*(\d+)/gi;
      let m;
      while ((m = rx.exec(txt)) !== null) {
        if (Number(m[1]) > 0) nums.add(Number(m[1]));
      }
      return {
        ...item,
        _pageNums: Array.from(nums).sort((a, b) => a - b)
      };
    });

  $: activePageFailedCriteria = selectedPageNumber === "global"
    ? failedExitCriteria.filter(it => it._pageNums.length === 0)
    : failedExitCriteria.filter(it => it._pageNums.includes(Number(selectedPageNumber)));

  $: computedSummary = (() => {
    const byPage = new Map();
    const basePages = (pageIssueSummary && Array.isArray(pageIssueSummary.pages) && pageIssueSummary.pages.length > 0)
      ? pageIssueSummary.pages
      : (pages || []).map(p => ({ page_number: Number(p.page_number), label: p.label || `หน้า ${p.page_number}`, has_image: Boolean(p.has_image) }));

    basePages.forEach(p => {
      const pn = Number(p.page_number);
      byPage.set(pn, {
        page_number: pn,
        label: p.label || `หน้า ${pn}`,
        total_issues: 0,
        critical_high: 0,
        medium: 0,
        low_info: 0,
        has_image: Boolean(p.has_image)
      });
    });

    let globalCnt = 0;
    indexedFindings.forEach(f => {
      if (f._pageNum && byPage.has(f._pageNum)) {
        const slot = byPage.get(f._pageNum);
        slot.total_issues += 1;
        if (f._sev === "critical" || f._sev === "high") slot.critical_high += 1;
        else if (f._sev === "medium") slot.medium += 1;
        else slot.low_info += 1;
      } else if (f._pageNum) {
        byPage.set(f._pageNum, {
          page_number: f._pageNum,
          label: f.page_label || `หน้า ${f._pageNum}`,
          total_issues: 1,
          critical_high: (f._sev === "critical" || f._sev === "high") ? 1 : 0,
          medium: f._sev === "medium" ? 1 : 0,
          low_info: (f._sev !== "critical" && f._sev !== "high" && f._sev !== "medium") ? 1 : 0,
          has_image: false
        });
      } else {
        globalCnt += 1;
      }
    });

    // Also include failed Exit Criteria items in per-page error counters so users see exact failed pages immediately
    failedExitCriteria.forEach(ec => {
      if (ec._pageNums && ec._pageNums.length > 0) {
        ec._pageNums.forEach(pn => {
          if (!byPage.has(pn)) {
            byPage.set(pn, { page_number: pn, label: `หน้า ${pn}`, total_issues: 0, critical_high: 0, medium: 0, low_info: 0, has_image: false });
          }
          const slot = byPage.get(pn);
          slot.total_issues += 1;
          slot.critical_high += 1;
        });
      } else {
        globalCnt += 1;
      }
    });

    const ordered = Array.from(byPage.values()).sort((a, b) => a.page_number - b.page_number);
    return {
      total_pages: ordered.length,
      pages_with_issues_count: ordered.filter(p => p.total_issues > 0).length,
      global_issues_count: globalCnt,
      pages: ordered
    };
  })();

  $: errorPagesList = (computedSummary?.pages || []).filter(p => p.total_issues > 0);
  $: visiblePageChips = onlyErrorPages && errorPagesList.length > 0
    ? errorPagesList
    : (computedSummary?.pages || []);

  $: if (selectedPageNumber === null && (pages.length > 0 || indexedFindings.length > 0)) {
    if (errorPagesList.length > 0) {
      selectedPageNumber = errorPagesList[0].page_number;
    } else if (pages.length > 0) {
      selectedPageNumber = Number(pages[0].page_number);
    } else if (indexedFindings.length > 0) {
      selectedPageNumber = "global";
    }
  }

  $: activePageObj = typeof selectedPageNumber === "number"
    ? (pages || []).find(p => Number(p.page_number) === Number(selectedPageNumber)) || null
    : null;

  $: if (activePageObj) {
    if (!activePageObj.has_image || !activePageObj.image_url) {
      viewMode = "highlight";
    } else if (!userPickedMode) {
      viewMode = "split";
    }
  }

  $: activePageFindings = selectedPageNumber === "global"
    ? indexedFindings.filter(f => !f._pageNum)
    : indexedFindings.filter(f => f._pageNum === Number(selectedPageNumber));

  export function focusPage(pageNum) {
    selectedPageNumber = pageNum ? Number(pageNum) : "global";
    selectedFindingIndex = null;
  }

  function getPageSeverityLevel(pageStat) {
    if (!pageStat || pageStat.total_issues === 0) return "clean";
    if (pageStat.critical_high > 0) return "critical";
    if (pageStat.medium > 0) return "medium";
    return "low";
  }

  function escapeRegExp(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function formatTargetRuleLabel(rawQuestion) {
    const q = String(rawQuestion || "").trim();
    if (!q) return "-";
    if (q.startsWith("ไม่มี")) {
      return `ต้อง${q}`;
    }
    return q;
  }

  function buildHighlightedSegments(text, pageFindings) {
    const raw = String(text || "");
    if (!raw) return [];
    if (!pageFindings || pageFindings.length === 0) {
      return [{ text: raw, isMatch: false }];
    }

    const ranges = [];
    for (const f of pageFindings) {
      const rawQuote = String(f.highlight_snippet || f.found_incorrect || "").trim();
      const cleaned = rawQuote.replace(/^["'`“”]+|["'`“”]+$/g, "").trim();
      if (!cleaned || cleaned === "-" || cleaned.length < 2 || /^(ไม่มี|n\/a|ไม่ระบุ)$/i.test(cleaned)) {
        continue;
      }

      const candidates = [cleaned];
      if (cleaned.length >= 14) {
        const subParts = cleaned
          .split(/[,;\n|/()]+/)
          .map(s => s.trim())
          .filter(s => s.length >= 8)
          .sort((a, b) => b.length - a.length)
          .slice(0, 3);
        candidates.push(...subParts);
      }

      let matched = false;
      for (const cand of candidates) {
        const tokens = cand.split(/\s+/).filter(Boolean).map(escapeRegExp);
        if (tokens.length === 0) continue;
        const pattern = tokens.join("\\s+");
        try {
          const rx = new RegExp(pattern, "gi");
          let m;
          let count = 0;
          while ((m = rx.exec(raw)) !== null && count < 4) {
            if (m[0].length === 0) break;
            ranges.push({
              start: m.index,
              end: m.index + m[0].length,
              findingIdx: f._idx,
              severity: f._sev,
              issue: f.issue || ""
            });
            matched = true;
            count += 1;
          }
        } catch {
          // ignore
        }
        if (matched) break;
      }
    }

    if (ranges.length === 0) {
      return [{ text: raw, isMatch: false }];
    }

    ranges.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
    const merged = [];
    for (const r of ranges) {
      if (merged.length === 0 || r.start >= merged[merged.length - 1].end) {
        merged.push(r);
      }
    }

    const segments = [];
    let cursor = 0;
    for (const r of merged) {
      if (r.start > cursor) {
        segments.push({ text: raw.slice(cursor, r.start), isMatch: false });
      }
      segments.push({
        text: raw.slice(r.start, r.end),
        isMatch: true,
        findingIdx: r.findingIdx,
        severity: r.severity,
        issue: r.issue
      });
      cursor = r.end;
    }
    if (cursor < raw.length) {
      segments.push({ text: raw.slice(cursor), isMatch: false });
    }
    return segments;
  }

  $: highlightedSegments = activePageObj
    ? buildHighlightedSegments(activePageObj.text, activePageFindings)
    : [];

  $: matchedFindingIndicesOnPage = new Set(
    highlightedSegments.filter(s => s.isMatch).map(s => s.findingIdx)
  );

  export async function focusFinding(pageNum, findingIdx) {
    selectedPageNumber = pageNum ? Number(pageNum) : "global";
    selectedFindingIndex = findingIdx;
    if (viewMode === "image" && typeof selectedPageNumber === "number") {
      viewMode = activePageObj?.has_image ? "split" : "highlight";
    }
    await tick();
    scrollToActiveHighlight(findingIdx);
  }

  function scrollToActiveHighlight(findingIdx) {
    if (!textPaneEl || findingIdx === null || findingIdx === undefined) return;
    const markEl = textPaneEl.querySelector(`mark[data-finding-idx="${findingIdx}"]`);
    if (markEl) {
      markEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  function selectPage(pn) {
    selectedPageNumber = pn;
    selectedFindingIndex = null;
  }

  function goPrevPage() {
    if (!pages.length) return;
    if (selectedPageNumber === "global") {
      selectedPageNumber = Number(pages[pages.length - 1].page_number);
      return;
    }
    const idx = pages.findIndex(p => Number(p.page_number) === Number(selectedPageNumber));
    if (idx > 0) {
      selectedPageNumber = Number(pages[idx - 1].page_number);
      selectedFindingIndex = null;
    }
  }

  function goNextPage() {
    if (!pages.length) return;
    if (selectedPageNumber === "global") {
      selectedPageNumber = Number(pages[0].page_number);
      return;
    }
    const idx = pages.findIndex(p => Number(p.page_number) === Number(selectedPageNumber));
    if (idx >= 0 && idx < pages.length - 1) {
      selectedPageNumber = Number(pages[idx + 1].page_number);
      selectedFindingIndex = null;
    }
  }

  $: if (selectedFindingIndex !== null && (viewMode === "highlight" || viewMode === "split")) {
    tick().then(() => scrollToActiveHighlight(selectedFindingIndex));
  }
</script>

<svelte:window on:keydown={handleWindowKeydown} />

{#if isExpanded}
  <div class="inspector-expand-backdrop" role="presentation" on:click={() => isExpanded = false}></div>
{/if}

<section
  class="doc-inspector-card"
  class:is-expanded={isExpanded}
  id="qa-doc-inspector-section"
  aria-label="Document Page Focus and Error Highlighter"
>
  <div class="inspector-header">
    <div class="inspector-title-group">
      <div class="inspector-icon-badge" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <circle cx="11.5" cy="14.5" r="2.5"></circle>
          <path d="M13.3 16.3L16 19"></path>
        </svg>
      </div>
      <div>
        <h3>โฟกัสหน้าที่พบข้อผิดพลาด & ไฮไลต์จุดบกพร่องบนเอกสาร</h3>
        <p class="inspector-subtitle">
          {#if indexedFindings.length > 0}
            พบประเด็นทั้งหมด <strong>{indexedFindings.length} รายการ</strong>
            {#if computedSummary.pages_with_issues_count > 0}
              กระจายอยู่บน <strong class="accent-danger">{computedSummary.pages_with_issues_count} หน้า</strong> จากทั้งหมด {computedSummary.total_pages || pages.length} หน้า
            {/if}
            {#if computedSummary.global_issues_count > 0}
              (และภาพรวมทั้งเอกสาร {computedSummary.global_issues_count} รายการ)
            {/if}
            — คลิกเลือกหน้าด้านล่างเพื่อดูตำแหน่งที่ผิดพลาดทันที
          {:else}
            ไม่พบข้อผิดพลาดในเอกสาร {filename || ""} — สามารถเปิดตรวจเนื้อหาแต่ละหน้าได้ด้านล่าง
          {/if}
        </p>
      </div>
    </div>

    <div class="inspector-header-controls">
      {#if errorPagesList.length > 0 && computedSummary.total_pages > errorPagesList.length}
        <button
          type="button"
          class="btn-filter-toggle"
          class:active={onlyErrorPages}
          on:click={() => onlyErrorPages = !onlyErrorPages}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
          </svg>
          {onlyErrorPages ? `แสดงเฉพาะหน้าที่มีปัญหา (${errorPagesList.length})` : `เฉพาะหน้าที่มีปัญหา (${errorPagesList.length})`}
        </button>
      {/if}
    </div>
  </div>

  {#if isLoadingPages}
    <div class="inspector-loading" role="status" aria-live="polite">
      <span class="mini-spinner"></span>
      <span>กำลังโหลดเนื้อหาแต่ละหน้าและจับคู่ตำแหน่งไฮไลต์...</span>
    </div>
  {:else if computedSummary.pages.length > 0 || computedSummary.global_issues_count > 0}
    <div class="page-focus-strip" role="tablist" aria-label="เลือกหน้าเอกสารที่ต้องการตรวจสอบ">
      {#each visiblePageChips as pStat}
        {@const sevLevel = getPageSeverityLevel(pStat)}
        <button
          type="button"
          role="tab"
          aria-selected={selectedPageNumber === pStat.page_number}
          class="page-chip sev-{sevLevel}"
          class:active={selectedPageNumber === pStat.page_number}
          on:click={() => selectPage(pStat.page_number)}
          title={pStat.total_issues > 0 ? `${pStat.label}: พบ ${pStat.total_issues} ประเด็น` : `${pStat.label}: ไม่พบข้อผิดพลาด`}
        >
          <span class="page-chip-dot" aria-hidden="true"></span>
          <span class="page-chip-label">{pStat.label}</span>
          {#if pStat.total_issues > 0}
            <span class="page-chip-count">{pStat.total_issues}</span>
          {/if}
        </button>
      {/each}

      {#if computedSummary.global_issues_count > 0}
        <button
          type="button"
          role="tab"
          aria-selected={selectedPageNumber === "global"}
          class="page-chip sev-global"
          class:active={selectedPageNumber === "global"}
          on:click={() => selectPage("global")}
        >
          <span class="page-chip-dot" aria-hidden="true"></span>
          <span class="page-chip-label">ภาพรวมทั้งเอกสาร</span>
          <span class="page-chip-count">{computedSummary.global_issues_count}</span>
        </button>
      {/if}
    </div>

    <div class="inspector-split-grid">
      <div class="viewer-pane">
        <div class="viewer-toolbar">
          <div class="viewer-page-nav">
            <button
              type="button"
              class="btn-nav-step"
              on:click={goPrevPage}
              disabled={!pages.length || (typeof selectedPageNumber === "number" && Number(pages[0]?.page_number) === selectedPageNumber)}
              aria-label="หน้าก่อนหน้า"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </button>
            <span class="viewer-page-indicator">
              {#if selectedPageNumber === "global"}
                ภาพรวมทั้งเอกสาร (Document-wide)
              {:else if activePageObj}
                {activePageObj.label || `หน้า ${activePageObj.page_number}`}
                <span class="page-total-muted">/ {pages.length}</span>
              {:else}
                เลือกหน้าเอกสาร
              {/if}
            </span>
            <button
              type="button"
              class="btn-nav-step"
              on:click={goNextPage}
              disabled={!pages.length || (typeof selectedPageNumber === "number" && Number(pages[pages.length - 1]?.page_number) === selectedPageNumber)}
              aria-label="หน้าถัดไป"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </button>
          </div>

          <div class="viewer-mode-group">
            {#if activePageObj}
              {#if activePageObj.has_image && activePageObj.image_url}
                <button
                  type="button"
                  class="btn-mode"
                  class:active={viewMode === "split"}
                  on:click={() => { userPickedMode = true; viewMode = "split"; }}
                >
                  ภาพจริง + ไฮไลต์
                </button>
                <button
                  type="button"
                  class="btn-mode"
                  class:active={viewMode === "image"}
                  on:click={() => { userPickedMode = true; viewMode = "image"; }}
                >
                  ภาพหน้าเอกสารจริง
                </button>
              {/if}
              <button
                type="button"
                class="btn-mode"
                class:active={viewMode === "highlight"}
                on:click={() => { userPickedMode = true; viewMode = "highlight"; }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M12 20h9"></path>
                  <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                </svg>
                เนื้อหาพร้อมไฮไลต์
              </button>
            {/if}
            <button
              type="button"
              class="btn-mode btn-expand-viewer"
              class:active={isExpanded}
              on:click={() => isExpanded = !isExpanded}
              title={isExpanded ? "ย่อกลับขนาดปกติ (Esc)" : "ขยายเต็มหน้าจอเพื่อดูเอกสารชัดเจนขึ้น"}
              aria-label={isExpanded ? "ย่อกลับขนาดปกติ" : "ขยายเต็มหน้าจอ"}
            >
              {#if isExpanded}
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="4 14 10 14 10 20"></polyline>
                  <polyline points="20 10 14 10 14 4"></polyline>
                  <line x1="14" y1="10" x2="21" y2="3"></line>
                  <line x1="3" y1="21" x2="10" y2="14"></line>
                </svg>
                ย่อกลับ
              {:else}
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <polyline points="15 3 21 3 21 9"></polyline>
                  <polyline points="9 21 3 21 3 15"></polyline>
                  <line x1="21" y1="3" x2="14" y2="10"></line>
                  <line x1="3" y1="21" x2="10" y2="14"></line>
                </svg>
                ขยายเต็มจอ
              {/if}
            </button>
          </div>
        </div>

        {#if selectedPageNumber === "global"}
          <div class="global-overview-placeholder" in:fade={{ duration: 160 }}>
            <div class="global-icon" aria-hidden="true">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            </div>
            <h4>ประเด็นระดับภาพรวมทั้งเอกสาร ({activePageFindings.length + activePageFailedCriteria.length} รายการ)</h4>
            <p>รายการทางด้านขวาเป็นข้อสังเกตเชิงโครงสร้างหรือข้อมูลที่ขาดหายในระดับภาพรวมทั้งฉบับ (ไม่ได้ผูกกับหน้าใดหน้าหนึ่งโดยเฉพาะ)</p>
            {#if errorPagesList.length > 0}
              <button type="button" class="btn-jump-error" on:click={() => selectPage(errorPagesList[0].page_number)}>
                ไปยังหน้าแรกที่พบข้อผิดพลาด ({errorPagesList[0].label})
              </button>
            {/if}
          </div>
        {:else if activePageObj}
          {#if (viewMode === "image" || viewMode === "split") && activePageObj.has_image && activePageObj.image_url}
            <div class="image-viewer-stage" class:compact-split={viewMode === "split"} in:fade={{ duration: 160 }}>
              <div class="image-zoom-bar">
                {#if activePageFindings.length > 0 || activePageFailedCriteria.length > 0}
                  <span class="img-issue-callout">
                    พบ {activePageFindings.length} จุดผิดพลาด{activePageFailedCriteria.length > 0 ? ` และไม่ผ่านเกณฑ์ Gate ${activePageFailedCriteria.length} ข้อ` : ''} ในหน้านี้
                  </span>
                {:else}
                  <span class="img-clean-callout">ไม่พบข้อผิดพลาดในหน้านี้</span>
                {/if}
                <div class="zoom-btns">
                  <button type="button" on:click={() => imageZoom = Math.max(60, imageZoom - 20)} aria-label="ย่อภาพ">−</button>
                  <button type="button" class="zoom-reset-btn" on:click={() => imageZoom = 100} title="รีเซ็ตขนาดภาพเป็น 100%">{imageZoom}%</button>
                  <button type="button" on:click={() => imageZoom = Math.min(200, imageZoom + 20)} aria-label="ขยายภาพ">+</button>
                </div>
              </div>
              <div class="image-scroll-canvas">
                <div class="image-frame-wrapper" style="width: {imageZoom}%;">
                  <img
                    src={activePageObj.image_url}
                    alt={`เอกสาร ${filename} ${activePageObj.label}`}
                    class="page-preview-img"
                    loading="lazy"
                    decoding="async"
                  />
                  {#if activePageFindings.length > 0}
                    <div class="image-error-pin-strip" aria-label="จุดที่ผิดพลาดบนหน้านี้">
                      {#each activePageFindings.slice(0, 4) as ef}
                        <button
                          type="button"
                          class="img-error-pin sev-{ef._sev}"
                          on:click={() => focusFinding(ef._pageNum, ef._idx)}
                        >
                          <span class="pin-badge">#{ef._idx + 1} {ef.severity || 'Error'}</span>
                          <span class="pin-text">{ef.issue}</span>
                        </button>
                      {/each}
                    </div>
                  {/if}
                </div>
              </div>
            </div>
          {/if}

          {#if viewMode === "highlight" || viewMode === "split" || !activePageObj.has_image}
            <div class="text-highlight-stage" class:split-bottom={viewMode === "split" && activePageObj.has_image && activePageObj.image_url} bind:this={textPaneEl} in:fade={{ duration: 160 }}>
              {#if activePageFindings.length > 0}
                <div class="highlight-legend-bar">
                  <span class="legend-item"><span class="hl-swatch critical"></span> Critical / High</span>
                  <span class="legend-item"><span class="hl-swatch medium"></span> Medium</span>
                  <span class="legend-item"><span class="hl-swatch low"></span> Low / Info</span>
                  <span class="legend-hint">คลิกที่ข้อความไฮไลต์เพื่อดูคำแนะนำแก้ไขทางขวา</span>
                </div>
              {/if}

              <div class="document-paper-sheet">
                {#if highlightedSegments.length > 0}
                  <div class="document-text-content">
                    {#each highlightedSegments as seg}
                      {#if seg.isMatch}
                        <mark
                          class="qa-hl sev-{seg.severity}"
                          class:active={selectedFindingIndex === seg.findingIdx}
                          data-finding-idx={seg.findingIdx}
                          role="button"
                          tabindex="0"
                          title={seg.issue}
                          on:click={() => selectedFindingIndex = seg.findingIdx}
                          on:keydown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectedFindingIndex = seg.findingIdx; } }}
                        >{seg.text}</mark>
                      {:else}
                        {seg.text}
                      {/if}
                    {/each}
                  </div>
                {:else}
                  <div class="empty-page-text">ไม่พบข้อความที่สกัดได้ในหน้านี้</div>
                {/if}
              </div>
            </div>
          {/if}
        {/if}
      </div>

      <div class="findings-pane">
        <div class="findings-pane-header">
          <h4>
            {#if selectedPageNumber === "global"}
              ประเด็นภาพรวมทั้งเอกสาร
            {:else if activePageObj}
              จุดผิดพลาดใน {activePageObj.label || `หน้า ${activePageObj.page_number}`}
            {:else}
              ประเด็นที่พบ
            {/if}
          </h4>
          <span class="pane-count-pill" class:clean={activePageFindings.length === 0 && activePageFailedCriteria.length === 0}>
            {(activePageFindings.length + activePageFailedCriteria.length) > 0
              ? `${activePageFindings.length + activePageFailedCriteria.length} รายการ`
              : "ไม่พบข้อผิดพลาด"}
          </span>
        </div>

        <div class="findings-cards-list">
          {#if activePageFindings.length === 0 && activePageFailedCriteria.length === 0}
            <div class="clean-page-state" in:fly={{ y: 8, duration: 200, easing: cubicOut }}>
              <div class="clean-check-circle" aria-hidden="true">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </div>
              <div class="clean-title">หน้านี้ผ่านการตรวจสอบ</div>
              <p>ไม่พบประเด็นข้อผิดพลาดในหน้านี้</p>
              {#if errorPagesList.length > 0}
                <button type="button" class="btn-jump-error" on:click={() => selectPage(errorPagesList[0].page_number)}>
                  ข้ามไปยังหน้าที่มีปัญหา ({errorPagesList[0].label})
                </button>
              {/if}
            </div>
          {:else}
            {#if activePageFailedCriteria.length > 0}
              <div class="exit-fail-group">
                <div class="exit-fail-group-lbl">ไม่ผ่านเกณฑ์ Exit Criteria Gate ({activePageFailedCriteria.length} ข้อ)</div>
                {#each activePageFailedCriteria as ec}
                  <div class="exit-fail-card">
                    <div class="fc-top-row">
                      <span class="fc-sev-pill sev-critical">ไม่ผ่านข้อ {ec.item_code}</span>
                      <span class="fc-type">{ec.category || "Exit Criteria"}</span>
                      {#if ec.target_metric}
                        <span class="fc-kpi-pill">เป้าหมาย: {ec.target_metric}</span>
                      {/if}
                      {#if ec.location || ec.page_ref}
                        <span class="fc-loc-pill">{ec.location || ec.page_ref}</span>
                      {/if}
                    </div>
                    <div class="fc-issue">
                      {ec.remarks || `เอกสารยังไม่ผ่านเงื่อนไขของเกณฑ์ข้อ ${ec.item_code}`}
                    </div>
                    <div class="fc-box target-rule">
                      <span class="fc-box-lbl">เกณฑ์มาตรฐานที่ตั้งไว้ (สิ่งที่ต้องทำให้ผ่าน)</span>
                      <div class="fc-box-val">{formatTargetRuleLabel(ec.question_text)}</div>
                    </div>
                    {#if ec.evidence_text}
                      <div class="fc-box wrong">
                        <span class="fc-box-lbl">ร่องรอย / รายการข้อบกพร่องที่ตรวจพบในเอกสาร</span>
                        <div class="fc-box-val pre-lines">{ec.evidence_text}</div>
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}

            {#each activePageFindings as f}
              <div
                class="finding-focus-card sev-{f._sev}"
                class:selected={selectedFindingIndex === f._idx}
                role="button"
                tabindex="0"
                on:click={() => focusFinding(f._pageNum, f._idx)}
                on:keydown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); focusFinding(f._pageNum, f._idx); } }}
              >
                <div class="fc-top-row">
                  <span class="fc-num">#{f._idx + 1}</span>
                  <span class="fc-sev-pill sev-{f._sev}">{f.severity || "Info"}</span>
                  {#if f.check_type}
                    <span class="fc-type">{f.check_type}</span>
                  {/if}
                  {#if f.location}
                    <span class="fc-loc-pill">{f.location}</span>
                  {/if}
                  {#if matchedFindingIndicesOnPage.has(f._idx)}
                    <span class="fc-hl-tag" title="พบตำแหน่งข้อความและไฮไลต์ไว้บนหน้าเอกสารแล้ว">ไฮไลต์แล้ว</span>
                  {/if}
                </div>

                <div class="fc-issue">{f.issue || "-"}</div>

                {#if f.found_incorrect && f.found_incorrect !== "-"}
                  <div class="fc-box wrong">
                    <span class="fc-box-lbl">ข้อความที่ผิดในเอกสาร</span>
                    <div class="fc-box-val">{f.found_incorrect}</div>
                  </div>
                {/if}

                {#if f.correct_value && f.correct_value !== "-"}
                  <div class="fc-box correct">
                    <span class="fc-box-lbl">สิ่งที่ควรเป็น</span>
                    <div class="fc-box-val">{f.correct_value}</div>
                  </div>
                {/if}

                {#if f.recommendation && f.recommendation !== "-"}
                  <div class="fc-rec">
                    <span class="fc-rec-lbl">ข้อเสนอแนะ:</span> {f.recommendation}
                  </div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <div class="inspector-empty">
      ยังไม่มีข้อมูลแบ่งหน้าสำหรับเอกสารนี้ (สามารถกดสแกนใหม่เพื่อสร้างหน้าเอกสารพร้อมไฮไลต์ได้)
    </div>
  {/if}
</section>

<style>
  .doc-inspector-card {
    background: rgba(18, 20, 28, 0.68);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(129, 140, 248, 0.24);
    border-radius: 20px;
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.3);
    font-family: "Prompt", "Outfit", sans-serif;
  }

  .inspector-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    flex-wrap: wrap;
  }

  .inspector-title-group {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    flex: 1;
    min-width: 260px;
  }

  .inspector-icon-badge {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    color: #c7d2fe;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.26), rgba(168, 85, 247, 0.22));
    border: 1px solid rgba(129, 140, 248, 0.38);
  }

  .inspector-title-group h3 {
    margin: 0;
    font-size: 1.08rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .inspector-subtitle {
    margin: 4px 0 0;
    font-size: 12.8px;
    color: #94a3b8;
    line-height: 1.5;
  }

  .inspector-subtitle strong { color: #e2e8f0; }
  .inspector-subtitle strong.accent-danger { color: #fca5a5; }

  .btn-filter-toggle {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 7px 14px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    color: #cbd5e1;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
  }
  .btn-filter-toggle:hover,
  .btn-filter-toggle.active {
    background: rgba(239, 68, 68, 0.18);
    border-color: rgba(248, 113, 113, 0.5);
    color: #fecaca;
  }

  .inspector-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 36px 20px;
    color: #a5b4fc;
    font-size: 13px;
  }

  .mini-spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(129, 140, 248, 0.25);
    border-top-color: #818cf8;
    border-radius: 50%;
    animation: spinInspector 0.8s linear infinite;
  }
  @keyframes spinInspector { to { transform: rotate(360deg); } }

  .page-focus-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 12px;
    background: rgba(11, 13, 21, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
  }

  .page-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 12px;
    min-height: 32px;
    border-radius: 10px;
    font-size: 12.2px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.03);
    color: #94a3b8;
    transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease, transform 0.16s ease;
  }
  .page-chip:hover {
    transform: translateY(-1px);
    color: #f8fafc;
    border-color: rgba(255, 255, 255, 0.2);
  }
  .page-chip-dot { width: 7px; height: 7px; border-radius: 50%; background: #475569; }
  .page-chip.sev-critical { background: rgba(239, 68, 68, 0.12); border-color: rgba(248, 113, 113, 0.35); color: #fecaca; }
  .page-chip.sev-critical .page-chip-dot { background: #ef4444; }
  .page-chip.sev-medium { background: rgba(245, 158, 11, 0.12); border-color: rgba(251, 191, 36, 0.35); color: #fde68a; }
  .page-chip.sev-medium .page-chip-dot { background: #f59e0b; }
  .page-chip.sev-low,
  .page-chip.sev-global { background: rgba(99, 102, 241, 0.14); border-color: rgba(129, 140, 248, 0.35); color: #c7d2fe; }
  .page-chip.sev-low .page-chip-dot,
  .page-chip.sev-global .page-chip-dot { background: #818cf8; }
  .page-chip.sev-clean .page-chip-dot { background: #10b981; }
  .page-chip.active {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.38), rgba(168, 85, 247, 0.32));
    border-color: #a5b4fc;
    color: #ffffff;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.28);
  }
  .page-chip-count {
    font-family: "Outfit", sans-serif;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.35);
    font-variant-numeric: tabular-nums;
  }

  .inspector-expand-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(4, 6, 12, 0.78);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    z-index: calc(var(--z-modal, 10000) - 1);
  }

  .doc-inspector-card.is-expanded {
    position: fixed;
    inset: 14px;
    z-index: var(--z-modal, 10000);
    background: var(--bg2, #12141c);
    border-color: rgba(129, 140, 248, 0.42);
    box-shadow: 0 28px 80px rgba(0, 0, 0, 0.85);
    overflow: hidden;
  }

  .doc-inspector-card.is-expanded .inspector-split-grid {
    flex: 1;
    min-height: 0;
  }

  .doc-inspector-card.is-expanded .viewer-pane,
  .doc-inspector-card.is-expanded .findings-pane {
    height: 100%;
    min-height: 0;
    max-height: none;
  }

  .inspector-split-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.6fr) minmax(310px, 0.85fr);
    gap: 16px;
    align-items: stretch;
  }

  .viewer-pane,
  .findings-pane {
    background: rgba(11, 13, 21, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 640px;
    height: clamp(700px, 80vh, 940px);
    max-height: 940px;
  }

  .viewer-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding: 10px 14px;
    background: rgba(22, 25, 38, 0.85);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .viewer-page-nav { display: flex; align-items: center; gap: 8px; }
  .btn-nav-step {
    width: 30px; height: 30px; border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.04);
    color: #e2e8f0;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
  .btn-nav-step:hover:not(:disabled) { background: rgba(99, 102, 241, 0.22); border-color: rgba(129, 140, 248, 0.5); }
  .btn-nav-step:disabled { opacity: 0.35; cursor: not-allowed; }
  .viewer-page-indicator { font-size: 13px; font-weight: 600; color: #f8fafc; font-variant-numeric: tabular-nums; }
  .page-total-muted { color: #94a3b8; font-weight: 500; }

  .viewer-mode-group { display: flex; gap: 6px; flex-wrap: wrap; }
  .btn-mode {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 6px 12px; min-height: 30px; border-radius: 8px;
    font-size: 12px; font-weight: 600; font-family: inherit;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: transparent; color: #94a3b8;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .btn-mode:hover { color: #f8fafc; }
  .btn-mode.active { background: rgba(99, 102, 241, 0.25); border-color: rgba(129, 140, 248, 0.55); color: #e0e7ff; }

  .text-highlight-stage {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 14px 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .text-highlight-stage.split-bottom {
    flex: 0.9 1 0;
    min-height: 180px;
    max-height: 36%;
  }
  .highlight-legend-bar {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    font-size: 11.5px; color: #94a3b8; padding: 6px 10px;
    background: rgba(255, 255, 255, 0.03); border-radius: 8px;
  }
  .legend-item { display: inline-flex; align-items: center; gap: 5px; }
  .hl-swatch { width: 10px; height: 10px; border-radius: 3px; display: inline-block; }
  .hl-swatch.critical { background: rgba(239, 68, 68, 0.65); border: 1px solid #f87171; }
  .hl-swatch.medium { background: rgba(245, 158, 11, 0.6); border: 1px solid #fbbf24; }
  .hl-swatch.low { background: rgba(99, 102, 241, 0.6); border: 1px solid #818cf8; }
  .legend-hint { margin-left: auto; color: #a5b4fc; font-size: 11px; }

  .document-paper-sheet {
    background: rgba(16, 19, 30, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px; padding: 18px 20px; flex: 1;
  }
  .document-text-content {
    white-space: pre-wrap; word-break: break-word;
    font-size: 13.2px; line-height: 1.78; color: #e2e8f0;
  }

  mark.qa-hl {
    padding: 2px 5px; border-radius: 5px; cursor: pointer; font-weight: 600;
    transition: box-shadow 0.2s ease, background-color 0.2s ease;
  }
  mark.qa-hl.sev-critical,
  mark.qa-hl.sev-high { background: rgba(239, 68, 68, 0.34); color: #fee2e2; border-bottom: 2px solid #f87171; }
  mark.qa-hl.sev-medium { background: rgba(245, 158, 11, 0.3); color: #fef3c7; border-bottom: 2px solid #fbbf24; }
  mark.qa-hl.sev-low,
  mark.qa-hl.sev-info { background: rgba(99, 102, 241, 0.34); color: #e0e7ff; border-bottom: 2px solid #818cf8; }
  mark.qa-hl.active { box-shadow: 0 0 0 3px rgba(165, 180, 252, 0.75); animation: hlPulse 0.9s ease-out 1; }
  @keyframes hlPulse {
    0% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0.85); }
    100% { box-shadow: 0 0 0 4px rgba(165, 180, 252, 0.65); }
  }

  .image-viewer-stage { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
  .image-viewer-stage.compact-split {
    flex: 2.1 1 0;
    min-height: 420px;
    max-height: none;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  .image-zoom-bar {
    display: flex; justify-content: space-between; align-items: center; gap: 10px;
    padding: 8px 14px; background: rgba(15, 18, 28, 0.9);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06); flex-wrap: wrap;
    flex-shrink: 0;
  }
  .img-issue-callout { font-size: 12px; color: #fecaca; font-weight: 500; }
  .img-clean-callout { font-size: 12px; color: #6ee7b7; font-weight: 500; }
  .zoom-btns { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #cbd5e1; font-variant-numeric: tabular-nums; }
  .zoom-btns button {
    min-width: 26px; height: 26px; padding: 0 6px; border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.05); color: #f8fafc; cursor: pointer;
    font-family: inherit; font-size: 12px;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
  .zoom-btns button:hover {
    background: rgba(99, 102, 241, 0.24);
    border-color: rgba(129, 140, 248, 0.5);
  }
  .zoom-btns .zoom-reset-btn {
    min-width: 48px;
    font-weight: 600;
  }
  .image-scroll-canvas {
    flex: 1;
    min-height: 0;
    overflow: auto;
    overscroll-behavior: contain;
    padding: 16px;
    text-align: center;
    background: #07090f;
  }
  .image-frame-wrapper { position: relative; display: inline-block; min-width: 280px; }
  .page-preview-img {
    width: 100%; height: auto; display: block;
    border-radius: 8px; box-shadow: 0 10px 28px rgba(0, 0, 0, 0.6);
  }
  .image-error-pin-strip { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; text-align: left; }
  .img-error-pin {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 10px; border-radius: 8px; font-size: 11.5px; font-family: inherit;
    cursor: pointer; border: 1px solid rgba(248, 113, 113, 0.45);
    background: rgba(239, 68, 68, 0.16); color: #fee2e2; max-width: 100%;
    transition: background-color 0.15s ease;
  }
  .img-error-pin:hover { background: rgba(239, 68, 68, 0.28); }
  .img-error-pin.sev-medium { border-color: rgba(251, 191, 36, 0.45); background: rgba(245, 158, 11, 0.16); color: #fef3c7; }
  .img-error-pin.sev-low,
  .img-error-pin.sev-info { border-color: rgba(129, 140, 248, 0.45); background: rgba(99, 102, 241, 0.18); color: #e0e7ff; }
  .pin-badge { font-weight: 700; white-space: nowrap; }
  .pin-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 260px; }

  .findings-pane-header {
    display: flex; justify-content: space-between; align-items: center; gap: 10px;
    padding: 12px 16px; background: rgba(22, 25, 38, 0.85);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .findings-pane-header h4 { margin: 0; font-size: 13.5px; font-weight: 700; color: #f8fafc; }
  .pane-count-pill {
    font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 999px;
    background: rgba(239, 68, 68, 0.18); color: #fca5a5;
    border: 1px solid rgba(248, 113, 113, 0.35);
  }
  .pane-count-pill.clean { background: rgba(16, 185, 129, 0.16); color: #6ee7b7; border-color: rgba(52, 211, 153, 0.35); }

  .findings-cards-list { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
  .exit-fail-group {
    display: flex; flex-direction: column; gap: 8px;
    padding-bottom: 10px; margin-bottom: 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .exit-fail-group-lbl { font-size: 11.5px; font-weight: 700; color: #fca5a5; }
  .exit-fail-card {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(248, 113, 113, 0.32);
    border-radius: 12px; padding: 11px 13px;
    display: flex; flex-direction: column; gap: 7px;
  }

  .finding-focus-card {
    background: rgba(20, 23, 35, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px; padding: 12px 14px;
    display: flex; flex-direction: column; gap: 8px; cursor: pointer;
    transition: border-color 0.16s ease, background-color 0.16s ease, transform 0.16s ease;
  }
  .finding-focus-card:hover { border-color: rgba(129, 140, 248, 0.45); background: rgba(28, 32, 48, 0.92); transform: translateY(-1px); }
  .finding-focus-card.selected { border-color: #818cf8; background: rgba(99, 102, 241, 0.14); box-shadow: 0 4px 16px rgba(99, 102, 241, 0.22); }

  .fc-top-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
  .fc-num { font-family: "Outfit", sans-serif; font-size: 11.5px; font-weight: 700; color: #94a3b8; }
  .fc-sev-pill { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }
  .fc-sev-pill.sev-critical,
  .fc-sev-pill.sev-high { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  .fc-sev-pill.sev-medium { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
  .fc-sev-pill.sev-low,
  .fc-sev-pill.sev-info { background: rgba(99, 102, 241, 0.2); color: #c7d2fe; }
  .fc-type { font-size: 11px; color: #94a3b8; }
  .fc-loc-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(129, 140, 248, 0.35);
    color: #c7d2fe;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .fc-hl-tag {
    margin-left: auto; font-size: 10.5px; font-weight: 600; padding: 2px 7px; border-radius: 999px;
    background: rgba(16, 185, 129, 0.14); color: #6ee7b7; border: 1px solid rgba(52, 211, 153, 0.3);
  }
  .fc-issue { font-size: 13px; font-weight: 600; color: #f8fafc; line-height: 1.45; }
  .fc-kpi-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: var(--radius-lg, 20px);
    background: rgba(6, 182, 212, 0.14);
    border: 1px solid rgba(6, 182, 212, 0.34);
    color: #67e8f9;
  }
  .fc-box { padding: 8px 10px; border-radius: 8px; font-size: 12px; line-height: 1.45; }
  .fc-box.target-rule {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(129, 140, 248, 0.28);
    color: #e0e7ff;
  }
  .fc-box.wrong { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(248, 113, 113, 0.28); color: #fecaca; }
  .fc-box.correct { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(52, 211, 153, 0.28); color: #a7f3d0; }
  .fc-box-val.pre-lines { white-space: pre-line; }
  .fc-box-lbl { display: block; font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.85; margin-bottom: 3px; }
  .fc-rec { font-size: 12px; color: #cbd5e1; line-height: 1.45; }
  .fc-rec-lbl { color: #a5b4fc; font-weight: 600; }

  .clean-page-state,
  .global-overview-placeholder,
  .inspector-empty {
    flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center; padding: 36px 24px; gap: 10px; color: #94a3b8; font-size: 13px;
  }
  .clean-check-circle,
  .global-icon {
    width: 52px; height: 52px; border-radius: 16px;
    display: flex; align-items: center; justify-content: center;
    color: #6ee7b7; background: rgba(16, 185, 129, 0.14); border: 1px solid rgba(52, 211, 153, 0.3);
  }
  .global-icon { color: #a5b4fc; background: rgba(99, 102, 241, 0.16); border-color: rgba(129, 140, 248, 0.35); }
  .clean-title,
  .global-overview-placeholder h4 { margin: 0; font-size: 14.5px; font-weight: 700; color: #f8fafc; }
  .clean-page-state p,
  .global-overview-placeholder p { margin: 0; max-width: 38ch; line-height: 1.5; }
  .btn-jump-error {
    margin-top: 6px; padding: 8px 16px; border-radius: 10px;
    border: 1px solid rgba(248, 113, 113, 0.45);
    background: rgba(239, 68, 68, 0.16); color: #fecaca;
    font-size: 12.5px; font-weight: 600; font-family: inherit; cursor: pointer;
    transition: background-color 0.15s ease;
  }
  .btn-jump-error:hover { background: rgba(239, 68, 68, 0.28); }
  .empty-page-text { color: #94a3b8; text-align: center; padding: 36px 16px; font-size: 13px; }
  .doc-inspector-card :is(button, [role="button"], mark):focus-visible { outline: 2px solid #a5b4fc; outline-offset: 2px; }

  @media (max-width: 1024px) {
    .inspector-split-grid { grid-template-columns: 1fr; }
    .viewer-pane, .findings-pane { max-height: 480px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .mini-spinner, mark.qa-hl.active { animation: none !important; }
    .page-chip, .finding-focus-card { transition: none !important; }
  }
</style>

