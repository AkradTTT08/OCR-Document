<script>
  import { createEventDispatcher, onDestroy } from "svelte";
  import { toast } from "./toastStore.js";
  import CustomSelect from "./CustomSelect.svelte";
  import { saveOCRResult } from "./ocrHistoryStore.js";
  const dispatch = createEventDispatcher();
  /** @type {any} */
  export let result = null;
  export let isProcessing = false;
  /** @type {any} */
  export let progress = { pct: 0, label: "", step: 0 };

  // ── Live Elapsed Clock during Processing ──
  let liveElapsedSec = 0;
  /** @type {any} */
  let elapsedTimer = null;

  $: if (isProcessing) {
    if (typeof progress?.elapsedSec === "number" && progress.elapsedSec > liveElapsedSec) {
      liveElapsedSec = progress.elapsedSec;
    }
    if (!elapsedTimer) {
      liveElapsedSec = progress?.elapsedSec || 0;
      elapsedTimer = setInterval(() => {
        liveElapsedSec += 1;
      }, 1000);
    }
  } else {
    if (elapsedTimer) {
      clearInterval(elapsedTimer);
      elapsedTimer = null;
    }
    liveElapsedSec = 0;
  }

  onDestroy(() => {
    if (elapsedTimer) clearInterval(elapsedTimer);
  });

  function formatElapsedTime(sec) {
    const s = Math.max(0, Math.floor(sec || 0));
    const mins = Math.floor(s / 60);
    const rem = s % 60;
    if (mins === 0) return `${rem} วินาที`;
    return `${mins} นาที ${String(rem).padStart(2, "0")} วินาที`;
  }

  $: gaugeCircumference = 2 * Math.PI * 64;
  $: gaugeDashoffset = gaugeCircumference * (1 - Math.min(100, Math.max(0, progress?.pct || 0)) / 100);

  const loadingPipelineStages = [
    { id: 1, title: "เตรียมโครงสร้าง PDF", sub: "แปลงหน้าเอกสารความละเอียดสูง" },
    { id: 2, title: "Vision OCR สกัดข้อความ", sub: "Gemini 2.5 Flash Multimodal" },
    { id: 3, title: "ตรวจคำผิด 3 ชั้น (TH/EN)", sub: "ราชบัณฑิตฯ + PyThaiNLP + AI" },
    { id: 4, title: "สรุปผล & จัดตาราง", sub: "สร้าง Markdown & พิกัดคำผิด" }
  ];

  function handleWindowKeydown(e) {
    if (showSaveModal && !isSaving && e.key === "Escape") {
      showSaveModal = false;
    }
  }

  // ── View state ──
  let activePageIdx = 0;
  let viewMode = "errors"; // 'errors' | 'split' | 'highlight' | 'text' | 'markdown' | 'preview'
  let filterLang = "all"; // 'all' | 'thai' | 'english' | 'semantic_fmt'
  let errorSearchQuery = "";
  let previewZoom = 100;
  let showPreviewBoxes = true;
  let tabsBarElement; // Reference for scrollable tabs
  /** @type {any} */
  let hoveredErr = null;
  /** @type {any} */
  let focusedErr = null;
  /** @type {HTMLElement | null} */
  let splitLeftScrollEl = null;
  /** @type {HTMLElement | null} */
  let splitRightScrollEl = null;

  function getErrKey(err) {
    if (!err) return "";
    return `${err.line_number ?? 0}_${err.position ?? -1}_${err.token ?? ""}`;
  }

  function isSameError(a, b) {
    if (!a || !b) return false;
    return getErrKey(a) === getErrKey(b);
  }

  function focusErrorOnPage(err) {
    focusedErr = err;
    hoveredErr = err;
    const key = getErrKey(err);
    // Scroll left image preview to the bounding box
    if (splitLeftScrollEl) {
      const boxEl = splitLeftScrollEl.querySelector(`[data-err-key="${CSS.escape(key)}"]`);
      if (boxEl) {
        boxEl.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
      }
    }
    // Scroll right text panel to the highlighted token or error card
    if (splitRightScrollEl) {
      const tokEl = splitRightScrollEl.querySelector(`[data-tok-key="${CSS.escape(key)}"]`);
      if (tokEl) {
        tokEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }

  // ── Derived ──
  $: pages = result?.pages ?? [];
  $: totalPages = result?.total_pages ?? result?.summary?.total_pages ?? pages.length ?? 0;
  $: activePage = pages[activePageIdx] ?? null;
  $: allErrors = collectAllErrors(pages);
  $: pageErrors = activePage?.spell_check?.errors ?? [];
  $: filteredErrors = (() => {
    let list =
      filterLang === "all"
        ? pageErrors
        : filterLang === "semantic_fmt"
          ? pageErrors.filter((/** @type {any} */ e) => e.error_type === "semantic" || e.error_type === "format")
          : pageErrors.filter((/** @type {any} */ e) => e.lang === filterLang);
    const q = errorSearchQuery.trim().toLowerCase();
    if (!q) return list;
    return list.filter((/** @type {any} */ e) =>
      String(e.token || "").toLowerCase().includes(q) ||
      String(e.message || "").toLowerCase().includes(q) ||
      (e.suggestions || []).some((s) => String(s).toLowerCase().includes(q))
    );
  })();
  $: fixableCount = filteredErrors.filter((/** @type {any} */ e) => e.suggestions && e.suggestions.length > 0).length;

  // Total stats across all pages (with fallback client-side word counter when spell_check wasn't run)
  function countPageTokensFallback(page, field) {
    const fromSpell = page?.spell_check?.summary?.[field];
    if (typeof fromSpell === "number" && fromSpell > 0) return fromSpell;
    const fromCounts = page?.token_counts?.[field];
    if (typeof fromCounts === "number" && fromCounts > 0) return fromCounts;
    const txt = String(page?.text || "");
    if (!txt.trim()) return 0;
    if (field === "thai_tokens") {
      const thChunks = txt.match(/[\u0E00-\u0E7F]+/g) || [];
      const totalChars = thChunks.reduce((acc, c) => acc + c.length, 0);
      return totalChars > 0 ? Math.max(1, Math.round(totalChars / 4.2)) : 0;
    }
    if (field === "english_tokens") {
      const enWords = txt.match(/\b[A-Za-z]{2,}\b/g) || [];
      return enWords.length;
    }
    return 0;
  }

  $: totalThai = pages.reduce((acc, p) => acc + countPageTokensFallback(p, "thai_tokens"), 0);
  $: totalEng = pages.reduce((acc, p) => acc + countPageTokensFallback(p, "english_tokens"), 0);
  $: totalThaiErr = sumSummaryField(pages, "thai_errors");
  $: totalEngErr = sumSummaryField(pages, "english_errors");
  $: totalSemantic = sumSummaryField(pages, "semantic_errors");
  $: totalFormat = pages.reduce(
    (acc, p) =>
      acc +
      (p.spell_check?.summary?.format_errors ??
        (p.spell_check?.errors || []).filter((e) => e.error_type === "format").length),
    0
  );
  $: totalErr = totalThaiErr + totalEngErr + totalSemantic + totalFormat;
  $: errRate =
    totalThai + totalEng > 0
      ? ((totalErr / (totalThai + totalEng)) * 100).toFixed(1)
      : "0.0";
  $: accuracyRate =
    totalThai + totalEng > 0
      ? Math.max(0, 100 - parseFloat(errRate)).toFixed(1)
      : "100.0";

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

  function escapeHtmlAttr(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /**
   * Single-pass interval highlighter that prevents recursive HTML attribute corruption
   * and avoids substring false-positives inside other words.
   * @param {string} text
   * @param {any[]} errors
   */
  function generateHighlightedHtml(text, errors) {
    if (!text) return "";
    if (!errors || errors.length === 0) return text;

    /** @type {Array<{start: number, end: number, err: any}>} */
    const spans = [];

    for (const err of errors) {
      const tok = err?.token;
      if (!tok || !tok.trim()) continue;

      if (
        typeof err.position === "number" &&
        err.position >= 0 &&
        text.slice(err.position, err.position + tok.length) === tok
      ) {
        spans.push({ start: err.position, end: err.position + tok.length, err });
      } else {
        const safeToken = tok.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const regexStr =
          err.lang === "english" ? `(?<![A-Za-z'-])${safeToken}(?![A-Za-z'-])` : safeToken;
        try {
          const rx = new RegExp(regexStr, "g");
          let m;
          while ((m = rx.exec(text)) !== null) {
            spans.push({ start: m.index, end: m.index + tok.length, err });
            if (m.index === rx.lastIndex) rx.lastIndex++;
          }
        } catch {
          const idx = text.indexOf(tok);
          if (idx !== -1) spans.push({ start: idx, end: idx + tok.length, err });
        }
      }
    }

    if (spans.length === 0) return text;

    // Sort by start position, prefer longer spans on tie
    spans.sort((a, b) => a.start - b.start || b.end - a.end);

    /** @type {Array<{start: number, end: number, err: any}>} */
    const nonOverlapping = [];
    let lastEnd = 0;
    for (const sp of spans) {
      if (sp.start >= lastEnd) {
        nonOverlapping.push(sp);
        lastEnd = sp.end;
      }
    }

    let out = "";
    let cursor = 0;
    for (const { start, end, err } of nonOverlapping) {
      if (start > cursor) {
        out += text.slice(cursor, start);
      }
      let cssClass = "tok-err-th";
      const suggStr = (err.suggestions || []).join(", ") || "—";
      const reasonStr = err.message ? `${err.message} | ` : "";
      let title = `สะกดผิด | ${reasonStr}แนะนำ: ${suggStr}`;

      if (err.error_type === "format") {
        cssClass = "tok-err-fmt";
        title = `รูปแบบ | ${reasonStr}แนะนำ: ${suggStr}`;
      } else if (err.error_type === "semantic") {
        cssClass = "tok-err-sm";
        title = `บริบท | ${reasonStr}แนะนำ: ${suggStr}`;
      } else if (err.lang === "english") {
        cssClass = "tok-err-en";
        title = `ภาษาอังกฤษ | ${reasonStr}แนะนำ: ${suggStr}`;
      }

      const sliceText = text.slice(start, end);
      const errKey = escapeHtmlAttr(getErrKey(err));
      out += `<span class="${cssClass}" data-tok-key="${errKey}" title="${escapeHtmlAttr(title)}">${sliceText}</span>`;
      cursor = end;
    }
    if (cursor < text.length) {
      out += text.slice(cursor);
    }
    return out;
  }

  function recalculatePageSpellSummary(page) {
    if (!page?.spell_check) return;
    const errs = page.spell_check.errors || [];
    const sum = page.spell_check.summary || {};
    let thErr = 0;
    let enErr = 0;
    let smErr = 0;
    let fmtErr = 0;
    for (const e of errs) {
      if (e.error_type === "format") fmtErr++;
      else if (e.error_type === "semantic") smErr++;
      else if (e.lang === "english") enErr++;
      else thErr++;
    }
    sum.thai_errors = thErr;
    sum.english_errors = enErr;
    sum.semantic_errors = smErr;
    sum.format_errors = fmtErr;
    sum.error_count = errs.length;
    const totalTok = (sum.thai_tokens || 0) + (sum.english_tokens || 0);
    sum.error_rate = totalTok > 0 ? Number(((errs.length / totalTok) * 100).toFixed(2)) : 0;
    page.spell_check.summary = sum;
  }

  async function applySuggestion(err, suggestion) {
    if (!activePage || !suggestion) return;
    const oldToken = err.token;
    let pageText = activePage.text || "";
    let replaced = false;
    let replacePos = -1;

    if (
      typeof err.position === "number" &&
      err.position >= 0 &&
      pageText.slice(err.position, err.position + oldToken.length) === oldToken
    ) {
      replacePos = err.position;
      pageText =
        pageText.slice(0, replacePos) +
        suggestion +
        pageText.slice(replacePos + oldToken.length);
      replaced = true;
    } else {
      const idx = pageText.indexOf(oldToken);
      if (idx !== -1) {
        replacePos = idx;
        pageText =
          pageText.slice(0, idx) +
          suggestion +
          pageText.slice(idx + oldToken.length);
        replaced = true;
      }
    }

    if (!replaced) {
      toast(`ไม่พบตำแหน่งคำว่า "${oldToken}" ในข้อความปัจจุบัน`, "warning");
      return;
    }

    const delta = suggestion.length - oldToken.length;
    activePage.text = pageText;

    // Remove the resolved error and shift positions of subsequent errors
    const remaining = [];
    let removedOne = false;
    for (const item of activePage.spell_check?.errors || []) {
      if (
        !removedOne &&
        item.token === oldToken &&
        item.position === err.position &&
        item.line_number === err.line_number
      ) {
        removedOne = true;
        continue;
      }
      if (typeof item.position === "number" && replacePos >= 0 && item.position > replacePos) {
        remaining.push({ ...item, position: item.position + delta });
      } else {
        remaining.push(item);
      }
    }

    activePage.spell_check.errors = remaining;
    recalculatePageSpellSummary(activePage);
    result.pages[activePageIdx] = activePage;
    result = { ...result };

    toast(`แก้ไข "${oldToken}" → "${suggestion}" เรียบร้อยแล้ว`, "success", 2200);
    try {
      await saveOCRResult(result);
    } catch {}
  }

  async function applyAllSuggestions() {
    if (!activePage?.spell_check?.errors?.length) return;
    const candidates = [...filteredErrors].filter(
      (e) => e.suggestions && e.suggestions.length > 0
    );
    if (candidates.length === 0) return;

    // Sort from end of text to start so character offsets stay valid during batch replacement
    candidates.sort((a, b) => (b.position ?? 0) - (a.position ?? 0));

    let pageText = activePage.text || "";
    const resolvedSet = new Set();
    let count = 0;

    for (const err of candidates) {
      const best = err.suggestions[0];
      const tok = err.token;
      if (!best || !tok) continue;

      if (
        typeof err.position === "number" &&
        err.position >= 0 &&
        pageText.slice(err.position, err.position + tok.length) === tok
      ) {
        pageText =
          pageText.slice(0, err.position) +
          best +
          pageText.slice(err.position + tok.length);
        resolvedSet.add(err);
        count++;
      } else {
        const idx = pageText.lastIndexOf(tok);
        if (idx !== -1) {
          pageText = pageText.slice(0, idx) + best + pageText.slice(idx + tok.length);
          resolvedSet.add(err);
          count++;
        }
      }
    }

    if (count > 0) {
      activePage.text = pageText;
      activePage.spell_check.errors = (activePage.spell_check.errors || []).filter(
        (e) => !resolvedSet.has(e)
      );
      recalculatePageSpellSummary(activePage);
      result.pages[activePageIdx] = activePage;
      result = { ...result };
      toast(`แก้ไขอัตโนมัติ ${count} จุดในหน้า ${activePage.page_number} เรียบร้อยแล้ว`, "success");
      try {
        await saveOCRResult(result);
      } catch {}
    }
  }

  async function ignoreAndAddToDict(err) {
    const word = (err?.token || "").trim();
    if (!word) return;
    try {
      const res = await fetch("/api/dictionary/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word }),
      });
      const d = await res.json();
      if (!res.ok || !d.success) {
        throw new Error(d.error || "ไม่สามารถเพิ่มเข้าพจนานุกรมได้");
      }

      // Remove this word from errors across all pages in current result
      const lower = word.toLowerCase();
      for (const p of result.pages || []) {
        if (p.spell_check?.errors) {
          p.spell_check.errors = p.spell_check.errors.filter(
            (e) => String(e.token || "").trim().toLowerCase() !== lower
          );
          recalculatePageSpellSummary(p);
        }
      }
      result = { ...result };
      toast(`เพิ่ม "${word}" เข้าพจนานุกรมและนำออกจากรายการคำผิดแล้ว`, "success");
      try {
        await saveOCRResult(result);
      } catch {}
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast(`ข้อผิดพลาด: ${msg}`, "error");
    }
  }

  /**
   * ทำความสะอาดจุดไข่ปลาสารบัญ (.....) และเส้นตาราง (-----) ที่ซ้ำยาวเกินไปก่อนแสดงผล
   * @param {string} rawText
   */
  function normalizeOcrDisplayMarkdown(rawText) {
    if (!rawText) return "";
    return rawText
      .replace(/(?:\.\s*){5,}\./g, " ... ")
      .replace(/…{3,}/g, " ... ")
      .replace(/-{8,}/g, "---")
      .replace(/_{8,}/g, "_____");
  }

  function formatInlineMarkdown(line) {
    if (!line) return "";
    return formatCellContent(line)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, '<code class="inline-md-code">$1</code>');
  }

  /**
   * @param {string} text
   * @returns {string}
   */
  function parseMarkdownToHtml(text) {
    if (!text) return "";

    const cleanedText = normalizeOcrDisplayMarkdown(text);
    const lines = cleanedText.split("\n");
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
          .slice(1, -1)
          .split(/(?<!\\)\|/)
          .map((c) => c.replace(/\\\|/g, "|").trim());

        if (!inTable) {
          const nextLine = (lines[i + 1] || "").trim();
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

      if (inTable) {
        html.push(renderHtmlTable(tableHeaders, tableRows));
        inTable = false;
        tableHeaders = [];
        tableRows = [];
      }

      // ประมวลผลบรรทัดข้อความปกติ & Markdown Headings / TOC rows
      if (line === "") {
        html.push("<br/>");
      } else if (line === "---" || line === "***") {
        html.push('<hr class="md-hr" />');
      } else if (line.startsWith("### ")) {
        html.push(`<h4 class="md-h3">${formatInlineMarkdown(line.substring(4))}</h4>`);
      } else if (line.startsWith("## ")) {
        html.push(`<h3 class="md-h2">${formatInlineMarkdown(line.substring(3))}</h3>`);
      } else if (line.startsWith("# ")) {
        html.push(`<h2 class="md-h1">${formatInlineMarkdown(line.substring(2))}</h2>`);
      } else if (line.startsWith("- ") || line.startsWith("* ")) {
        html.push(`<ul><li>${formatInlineMarkdown(line.substring(2))}</li></ul>`);
      } else if (/^(.+?)\s+\.\.\.\s+(\d+|[IVXLCDM]+)$/i.test(line)) {
        // แถวสารบัญ (Table of Contents) เช่น "1. บทนำ ... 6"
        const tocMatch = line.match(/^(.+?)\s+\.\.\.\s+(\d+|[IVXLCDM]+)$/i);
        if (tocMatch) {
          html.push(
            `<div class="md-toc-row"><span class="md-toc-title">${formatInlineMarkdown(tocMatch[1])}</span><span class="md-toc-dots"></span><span class="md-toc-page">${tocMatch[2]}</span></div>`
          );
        } else {
          html.push(`<div>${formatInlineMarkdown(line)}</div>`);
        }
      } else if (/^\d+\.\s/.test(line)) {
        const match = line.match(/^(\d+)\.\s(.*)/);
        if (match) {
          html.push(`<ol start="${match[1]}"><li>${formatInlineMarkdown(match[2])}</li></ol>`);
        } else {
          html.push(`<div>${formatInlineMarkdown(line)}</div>`);
        }
      } else {
        html.push(`<div>${formatInlineMarkdown(line)}</div>`);
      }
    }

    if (inTable) {
      html.push(renderHtmlTable(tableHeaders, tableRows));
    }

    return html.join("\n");
  }

  /**
   * แปลง markdown links/images และ URLs ใน cell ตารางให้ออกมาเป็น HTML
   * @param {string} cell
   * @returns {string}
   */
  function formatCellContent(cell) {
    if (!cell) return "";
    let formatted = cell
      .replace(
        /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g,
        '<img src="$2" alt="$1" style="max-width: 220px; max-height: 140px; border-radius: 6px; display: block; margin: 4px 0; border: 1px solid rgba(255,255,255,0.15);" />'
      )
      .replace(
        /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: var(--accent, #38bdf8); text-decoration: underline; word-break: break-all;">$1</a>'
      );
    return formatted;
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
        html.push(`<th>${formatCellContent(h)}</th>`);
      });
      html.push("</tr></thead>");
    }
    if (rows.length > 0) {
      html.push("<tbody>");
      rows.forEach((row) => {
        html.push("<tr>");
        row.forEach((cell) => {
          html.push(`<td>${formatCellContent(cell)}</td>`);
        });
        html.push("</tr>");
      });
      html.push("</tbody>");
    }
    html.push("</table></div>");
    return html.join("");
  }

  // ── Export & Clipboard Utilities ──
  async function copyActivePageText() {
    const txt = activePage?.text ?? "";
    if (!txt.trim()) {
      toast("ไม่มีข้อความในหน้านี้ให้คัดลอก", "warning");
      return;
    }
    try {
      await navigator.clipboard.writeText(txt);
      toast(`คัดลอกข้อความหน้า ${activePage.page_number} ไปยังคลิปบอร์ดแล้ว`, "success", 2200);
    } catch {
      toast("ไม่สามารถคัดลอกข้อความได้", "error");
    }
  }

  function exportMarkdown() {
    if (!result) return;
    const baseName = (result.filename || "document").replace(/\.pdf$/i, "");
    const md = result.pages
      .map((/** @type {any} */ p) => `## หน้า ${p.page_number}\n\n${p.text || ""}`)
      .join("\n\n---\n\n");
    downloadFile(md, `${baseName}_ocr.md`);
  }

  async function saveManualTextEdit() {
    if (!activePage) return;
    result.pages[activePageIdx] = activePage;
    result = { ...result };
    try {
      await saveOCRResult(result);
      toast(`บันทึกข้อความหน้า ${activePage.page_number} เรียบร้อยแล้ว`, "success", 2200);
    } catch {
      toast("บันทึกข้อความในหน่วยความจำแล้ว", "info");
    }
  }

  function exportTxt() {
    if (!result) return;
    const text = result.pages
      .map((/** @type {any} */ p) => `=== หน้า ${p.page_number} ===\n${p.text}`)
      .join("\n\n");
    downloadFile(text, "ocr_result.txt");
  }
  function exportReport() {
    if (!result) return;
    let r = `=== รายงาน OCR + ตรวจสอบคำ ===\nไฟล์: ${result.filename}\nหน้าทั้งหมด: ${totalPages}\n`;
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
    const url = URL.createObjectURL(new Blob([content], { type: "text/plain" }));
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: name,
    });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  let checkingSpell = false;
  let reprocessingPage = false;

  async function reprocessActivePage() {
    if (!activePage || reprocessingPage) return;
    const sessId = activePage.session_id || result?.session_id;
    if (!sessId) {
      toast("ไม่พบรหัสเซสชันภาพต้นฉบับสำหรับสแกนซ้ำ", "warning");
      return;
    }
    reprocessingPage = true;
    try {
      toast(`กำลังสแกน OCR หน้าที่ ${activePage.page_number} ใหม่จากภาพต้นฉบับ...`, "info", 2500);
      const res = await fetch("/api/ocr/reprocess_page", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessId,
          page_number: activePage.page_number,
          lang: result?.lang || "tha+eng",
          auto_spellcheck: !!activePage.spell_check,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "ไม่สามารถสแกนหน้านี้ใหม่ได้");
      }
      result.pages[activePageIdx] = {
        ...activePage,
        ...data.page,
      };
      result = { ...result };
      try {
        await saveOCRResult(result);
      } catch {}
      toast(`สแกน OCR หน้าที่ ${activePage.page_number} ใหม่เรียบร้อยแล้ว`, "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast(`ข้อผิดพลาด: ${msg}`, "error");
    } finally {
      reprocessingPage = false;
    }
  }

  async function runManualSpellCheck() {
    if (!activePage || checkingSpell) return;

    checkingSpell = true;
    try {
      toast(`เริ่มตรวจสอบคำผิด 3-Layer หน้า ${activePage.page_number}...`, "info", 2000);
      const API = "/api";
      const res = await fetch(`${API}/spellcheck`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: activePage.text,
          words: activePage.words,
          session_id: activePage.session_id || result?.session_id,
          page_number: activePage.page_number,
          lang: result?.lang || "tha+eng",
          include_suggestions: true,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "เกิดข้อผิดพลาด");

      // Update page data
      result.pages[activePageIdx].spell_check = data.result;

      // Trigger reactivity & save
      result = { ...result };
      try {
        await saveOCRResult(result);
      } catch {}
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
    { value: '', label: '-- เลือกโครงการ --' },
    ...(projects || []).map(p => ({ 
      value: p.id || p.project_id, 
      label: `${p.project_code ? p.project_code + ' — ' : ''}${p.name || p.project_name || ''}`
    }))
  ];

  const categorySelectOptions = [
    { value: 'Reference', label: 'เอกสารอ้างอิง (Reference)' },
    { value: 'TOR/SOW', label: 'TOR / SOW' },
    { value: 'SRS', label: 'SRS (System Requirements)' },
    { value: 'SDD', label: 'SDD (System Design)' },
    { value: 'TestCase', label: 'Test Case / Test Plan' },
    { value: 'Requirements', label: 'Requirements' },
    { value: 'UAT', label: 'UAT / Sign-off' },
    { value: 'Usermanual', label: 'User Manual' },
    { value: 'Admin manual', label: 'Admin Manual' },
    { value: 'Installation system', label: 'Installation Guide' },
    { value: 'Other', label: 'อื่นๆ (Other)' }
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
      const res = await fetch("/api/projects");
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
      const markdownText = (result?.pages && Array.isArray(result.pages) && result.pages.length > 0)
        ? result.pages.map((p) => p.text || "").join("\n\n")
        : (result?.full_markdown_content || result?.markdown_text || result?.text || result?.markdown || "");

      if (!markdownText || !markdownText.trim()) {
        toast("ไม่พบข้อความในเอกสารสำหรับการบันทึก", "warning");
        isSaving = false;
        return;
      }

      const res = await fetch("/api/kb/ingest", {
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

<svelte:window on:keydown={handleWindowKeydown} />

<!-- ── RIGHT PANEL ── -->
<div class="rp">
  <!-- ─── Empty / Processing State ─── -->
  {#if isProcessing}
    <div class="state-screen loading-screen-wrap">
      <div class="ocr-loading-studio" role="status" aria-live="polite">
        <!-- Top File & Engine Identity Bar -->
        <div class="loading-studio-top">
          <div class="loading-file-pill">
            <span class="file-pulse-dot"></span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            <span class="lf-name truncate">{progress.filename || "กำลังประมวลผลเอกสาร PDF"}</span>
            {#if progress.fileSize}
              <span class="lf-size">({progress.fileSize})</span>
            {/if}
          </div>
          <div class="loading-engine-tags">
            {#if progress.dpi}
              <span class="le-tag">{progress.dpi} DPI</span>
            {/if}
            <span class="le-tag accent">
              {progress.autoSpellCheck !== false ? "3-Layer Hybrid Proofread" : "Fast Vision OCR"}
            </span>
          </div>
        </div>

        <!-- Animated 3D Crystal Prism & Orbital Quantum Scanner Centerpiece -->
        <div class="spectra-quantum-loader" aria-hidden="true">
          <!-- Ambient Multi-Layer Glow -->
          <div class="quantum-aura-outer"></div>
          <div class="quantum-aura-inner"></div>

          <!-- Outer Rotating Orbital Ring (210x210) -->
          <svg class="orbit-svg-outer" viewBox="0 0 210 210" fill="none">
            <defs>
              <linearGradient id="spectraOrbitGrad1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#6366f1" stop-opacity="0.95" />
                <stop offset="50%" stop-color="#a855f7" stop-opacity="0.75" />
                <stop offset="100%" stop-color="#06b6d4" stop-opacity="0.1" />
              </linearGradient>
              <linearGradient id="spectraOrbitGrad2" x1="100%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stop-color="#06b6d4" stop-opacity="0.9" />
                <stop offset="60%" stop-color="#a855f7" stop-opacity="0.4" />
                <stop offset="100%" stop-color="#6366f1" stop-opacity="0" />
              </linearGradient>
            </defs>
            <circle cx="105" cy="105" r="98" stroke="rgba(255,255,255,0.05)" stroke-width="1" />
            <circle
              cx="105"
              cy="105"
              r="98"
              stroke="url(#spectraOrbitGrad1)"
              stroke-width="2"
              stroke-linecap="round"
              stroke-dasharray="145 160"
            />
            <circle cx="105" cy="7" r="3.5" fill="#c084fc" />
            <circle cx="105" cy="203" r="3" fill="#38bdf8" />
          </svg>

          <!-- Middle Counter-Rotating Precision Radar Ring (174x174) -->
          <svg class="orbit-svg-mid" viewBox="0 0 174 174" fill="none">
            <circle
              cx="87"
              cy="87"
              r="80"
              stroke="url(#spectraOrbitGrad2)"
              stroke-width="1.75"
              stroke-linecap="round"
              stroke-dasharray="55 35 18 35"
            />
            <circle
              cx="87"
              cy="87"
              r="72"
              stroke="rgba(168, 85, 247, 0.22)"
              stroke-width="1"
              stroke-dasharray="3 7"
            />
            <circle cx="167" cy="87" r="3" fill="#22d3ee" />
            <circle cx="7" cy="87" r="2.5" fill="#818cf8" />
          </svg>

          <!-- Dynamic SVG Progress Gauge Ring (144x144) -->
          <svg class="orbit-svg-progress" viewBox="0 0 144 144" fill="none">
            <circle
              cx="72"
              cy="72"
              r="64"
              stroke="rgba(255, 255, 255, 0.07)"
              stroke-width="3.5"
            />
            <circle
              class="gauge-progress-arc"
              cx="72"
              cy="72"
              r="64"
              stroke="url(#spectraOrbitGrad1)"
              stroke-width="3.5"
              stroke-linecap="round"
              stroke-dasharray={gaugeCircumference}
              stroke-dashoffset={gaugeDashoffset}
              transform="rotate(-90 72 72)"
            />
          </svg>

          <!-- Floating Quantum Particles -->
          <span class="q-spark s1"></span>
          <span class="q-spark s2"></span>
          <span class="q-spark s3"></span>
          <span class="q-spark s4"></span>

          <!-- Inner 3D Crystal Prism & Laser Scan Stage -->
          <div class="prism-core-stage">
            <!-- Sweeping OCR Laser Scan Beam & Light Curtain -->
            <div class="prism-laser-beam"></div>

            <!-- Animated Multi-Faceted 3D Crystal Prism SVG -->
            <svg class="spectra-animated-prism" viewBox="0 0 120 120" fill="none">
              <defs>
                <linearGradient id="prismTopGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.75" />
                  <stop offset="50%" stop-color="#818cf8" stop-opacity="0.65" />
                  <stop offset="100%" stop-color="#c084fc" stop-opacity="0.8" />
                </linearGradient>
                <linearGradient id="prismLeftGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#6366f1" stop-opacity="0.65" />
                  <stop offset="100%" stop-color="#3b0764" stop-opacity="0.45" />
                </linearGradient>
                <linearGradient id="prismRightGrad" x1="100%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stop-color="#a855f7" stop-opacity="0.7" />
                  <stop offset="100%" stop-color="#06b6d4" stop-opacity="0.4" />
                </linearGradient>
                <linearGradient id="prismEdgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#ffffff" />
                  <stop offset="50%" stop-color="#c4b5fd" />
                  <stop offset="100%" stop-color="#67e8f9" />
                </linearGradient>
              </defs>

              <!-- Outer Hexagonal Halo -->
              <polygon
                class="prism-outer-halo"
                points="60,10 103,35 103,85 60,110 17,85 17,35"
                stroke="rgba(168, 85, 247, 0.35)"
                stroke-width="1.2"
                stroke-dasharray="4 4"
                fill="none"
              />

              <!-- Shimmering 3D Isometric Facets -->
              <!-- Left Outer Facet -->
              <polygon
                class="prism-facet facet-left"
                points="60,16 60,60 22,82 22,38"
                fill="url(#prismLeftGrad)"
              />
              <!-- Right Outer Facet -->
              <polygon
                class="prism-facet facet-right"
                points="60,16 98,38 98,82 60,60"
                fill="url(#prismRightGrad)"
              />
              <!-- Bottom Facet -->
              <polygon
                class="prism-facet facet-bottom"
                points="22,82 60,60 98,82 60,104"
                fill="rgba(99, 102, 241, 0.32)"
              />
              <!-- Inner Elevated Diamond Core -->
              <polygon
                class="prism-inner-diamond"
                points="60,34 83,47 60,60 37,47"
                fill="url(#prismTopGrad)"
              />
              <polygon
                class="prism-inner-left"
                points="37,47 60,60 60,87 37,73"
                fill="rgba(56, 189, 248, 0.35)"
              />
              <polygon
                class="prism-inner-right"
                points="60,60 83,47 83,73 60,87"
                fill="rgba(192, 132, 252, 0.42)"
              />

              <!-- Crisp Illuminated Structural Edges -->
              <polygon
                points="60,16 98,38 98,82 60,104 22,82 22,38"
                stroke="url(#prismEdgeGrad)"
                stroke-width="2.6"
                stroke-linejoin="round"
              />
              <polygon
                points="60,34 83,47 60,60 37,47"
                stroke="#ffffff"
                stroke-width="2.2"
                stroke-linejoin="round"
              />
              <line x1="60" y1="16" x2="60" y2="34" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" />
              <line x1="98" y1="38" x2="83" y2="47" stroke="#67e8f9" stroke-width="2.2" stroke-linecap="round" />
              <line x1="22" y1="38" x2="37" y2="47" stroke="#c4b5fd" stroke-width="2.2" stroke-linecap="round" />
              <line x1="60" y1="60" x2="60" y2="104" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round" />
              <line x1="83" y1="47" x2="98" y2="82" stroke="#c4b5fd" stroke-width="2" stroke-linecap="round" />
              <line x1="37" y1="47" x2="22" y2="82" stroke="#67e8f9" stroke-width="2" stroke-linecap="round" />

              <!-- Glowing Vertex Nodes -->
              <circle class="vertex-node v1" cx="60" cy="16" r="3" fill="#ffffff" />
              <circle class="vertex-node v2" cx="98" cy="38" r="2.8" fill="#67e8f9" />
              <circle class="vertex-node v3" cx="22" cy="38" r="2.8" fill="#c084fc" />
              <circle class="vertex-node v4" cx="60" cy="60" r="3.4" fill="#ffffff" />
              <circle class="vertex-node v5" cx="60" cy="104" r="2.8" fill="#a855f7" />
            </svg>
          </div>

          <!-- Floating Percentage Pill on Ring Bottom -->
          <div class="loader-pct-pill">
            <span>{progress.pct || 0}%</span>
          </div>
        </div>

        <!-- Primary Headline & Dynamic Step Label -->
        <div class="loading-headline-block">
          <h2 class="loading-main-title">กำลังสกัดข้อความและตรวจสอบคำผิดอัจฉริยะ</h2>
          <p class="loading-sub-label">{progress.label || "กำลังประมวลผลหน้าเอกสารด้วย Google Gemini 2.5 Flash..."}</p>
        </div>

        <!-- 4-Card Live Telemetry Grid -->
        <div class="loading-telemetry-grid">
          <div class="lt-card">
            <span class="lt-label">ความคืบหน้าหน้าเอกสาร</span>
            <strong class="lt-val primary">
              {progress.completedPages ?? 0} <span class="lt-sep">/</span> {progress.totalPages || "—"} หน้า
            </strong>
            <span class="lt-sub">
              {#if progress.totalDocPages && progress.totalDocPages > (progress.totalPages || 0)}
                จากเอกสารทั้งหมด {progress.totalDocPages} หน้า
              {:else}
                สกัดและตรวจแบบ Streaming
              {/if}
            </span>
          </div>

          <div class="lt-card">
            <span class="lt-label">เวลาที่ใช้ไป (Elapsed)</span>
            <strong class="lt-val">{formatElapsedTime(liveElapsedSec)}</strong>
            <span class="lt-sub">นับเวลาแบบเรียลไทม์</span>
          </div>

          <div class="lt-card">
            <span class="lt-label">เวลาที่เหลือคาดการณ์ (ETA)</span>
            <strong class="lt-val accent">{progress.etaText || "กำลังคำนวณ..."}</strong>
            <span class="lt-sub">ประเมินจากความเร็วหน้าล่าสุด</span>
          </div>

          <div class="lt-card">
            <span class="lt-label">ความเร็วเฉลี่ย</span>
            <strong class="lt-val">
              {progress.avgSecPerPage ? `${progress.avgSecPerPage} วินาที/หน้า` : "กำลังประเมิน..."}
            </strong>
            <span class="lt-sub">{progress.langLabel || "ไทย + อังกฤษ (TH / EN)"}</span>
          </div>
        </div>

        <!-- Illuminated Shimmer Progress Bar -->
        <div class="prog-wrap">
          <div class="prog-track">
            <div class="prog-fill" style="width:{Math.max(4, progress.pct || 0)}%">
              <div class="prog-shimmer"></div>
            </div>
          </div>

          <!-- 4-Stage Pipeline Stepper -->
          <div class="loading-pipeline-stepper">
            {#each loadingPipelineStages as st}
              {@const isDone = (progress.step || 1) > st.id || (st.id === 3 && (progress.completedPages ?? 0) > 0 && (progress.step || 1) >= 3)}
              {@const isActive = (progress.step || 1) === st.id || (st.id === 2 && (progress.step || 1) === 3)}
              <div class="lp-step" class:active={isActive} class:done={isDone}>
                <div class="lp-step-indicator">
                  {#if isDone && !isActive}
                    <svg viewBox="0 0 16 16" fill="currentColor" width="11" height="11">
                      <path fill-rule="evenodd" d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" clip-rule="evenodd" />
                    </svg>
                  {:else}
                    <span>{st.id}</span>
                  {/if}
                </div>
                <div class="lp-step-text">
                  <span class="lp-step-title">{st.title}</span>
                  <span class="lp-step-sub">{st.sub}</span>
                </div>
              </div>
            {/each}
          </div>
        </div>

        <!-- Live Extracted Page Preview Ticker (Appears as soon as Page 1 finishes) -->
        {#if progress.latestPageNum}
          <div class="loading-live-stream-box">
            <div class="lls-header">
              <span class="lls-badge">
                <span class="lls-dot"></span>
                สกัดเสร็จล่าสุด: หน้า {progress.latestPageNum}
              </span>
              {#if progress.latestPageErrors !== null && progress.latestPageErrors !== undefined}
                <span class="lls-err-count" class:clean={progress.latestPageErrors === 0}>
                  {progress.latestPageErrors === 0
                    ? "ไม่พบคำผิดในหน้านี้"
                    : `พบคำผิด/ฟอร์แมต ${progress.latestPageErrors} จุด`}
                </span>
              {/if}
            </div>
            {#if progress.latestPageSnippet}
              <p class="lls-snippet">“{progress.latestPageSnippet}...”</p>
            {/if}
          </div>
        {/if}

        <!-- Interactive Control Footer (View Partial Results Now or Cancel) -->
        <div class="loading-studio-actions">
          {#if (progress.completedPages ?? 0) > 0}
            <button
              type="button"
              class="btn-view-partial"
              on:click={() => dispatch("cancel", { keepPartial: true })}
              title="หยุดสแกนหน้าถัดไปและเปิดดูผลลัพธ์หน้าที่สกัดเสร็จแล้วทันที"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
              <span>หยุดและดูผลลัพธ์ที่ได้ทันที ({progress.completedPages} หน้า)</span>
            </button>
          {/if}
          <button
            type="button"
            class="btn-cancel-scan"
            on:click={() => dispatch("cancel", { keepPartial: false })}
            title="ยกเลิกการสแกนและกลับไปหน้าอัปโหลด"
          >
            ยกเลิกการสแกน
          </button>
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
      <div class="rp-title-group">
        <button
          type="button"
          class="btn-back-upload"
          on:click={() => dispatch("close")}
          title="กลับไปหน้าอัปโหลดเพื่อสแกนไฟล์ใหม่"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="15 18 9 12 15 6"></polyline>
          </svg>
          <span>สแกนไฟล์ใหม่</span>
        </button>
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
          <span class="truncate" title={result.filename}>{result.filename}</span>
          <span class="engine-mode-pill">3-Layer Hybrid OCR</span>
        </div>
      </div>
      <div class="header-actions">
        <button
          type="button"
          class="btn-sm"
          on:click={reprocessActivePage}
          disabled={reprocessingPage || checkingSpell}
          title="สแกน OCR หน้านี้ใหม่จากภาพต้นฉบับ (กรณีข้อความหรือตารางหน้านี้เพี้ยน)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
            <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
            <path d="M3 3v5h5"></path>
            <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path>
            <path d="M16 16h5v5"></path>
          </svg>
          <span>{reprocessingPage ? "กำลังสแกนใหม่..." : "สแกนหน้านี้ใหม่"}</span>
        </button>
        <button
          type="button"
          class="btn-sm"
          on:click={runManualSpellCheck}
          disabled={checkingSpell || reprocessingPage}
          title="รันระบบตรวจคำผิดและฟอร์แมตหน้านี้ใหม่"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          <span>{checkingSpell ? "กำลังตรวจ..." : "ตรวจคำซ้ำ"}</span>
        </button>
        <button type="button" class="btn-sm" on:click={copyActivePageText} title="คัดลอกข้อความหน้านี้ไปยังคลิปบอร์ด">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          <span>คัดลอก</span>
        </button>
        <button type="button" class="btn-sm btn-save-proj" on:click={openSaveModal} title="บันทึกเข้า Project Knowledge Base">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" width="14" height="14">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </svg>
          บันทึกเข้า Project
        </button>
        <button type="button" class="btn-sm" on:click={exportMarkdown} title="ดาวน์โหลดไฟล์ Markdown (.md)">
          <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12"><path d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75zM7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.97a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.779a.749.749 0 111.06-1.06l1.97 1.97z" /></svg>
          .md
        </button>
        <button type="button" class="btn-sm" on:click={exportTxt} title="Export ข้อความ (.txt)">
          <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12"
            ><path
              d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75zM7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.97a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.779a.749.749 0 111.06-1.06l1.97 1.97z"
            /></svg
          >
          .txt
        </button>
        <button type="button" class="btn-sm" on:click={exportReport} title="Export รายงานผลการตรวจคำผิด">
          <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12"
            ><path
              d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75zM7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.97a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.779a.749.749 0 111.06-1.06l1.97 1.97z"
            /></svg
          >
          รายงาน
        </button>
      </div>
    </div>

    <!-- ── 5-Card KPI Stat Ribbon ── -->
    <div class="stat-bar">
      <div class="stat-card">
        <div class="stat-val" style="color:var(--primary-soft-text)">
          {totalPages}
        </div>
        <div class="stat-lbl">หน้าเอกสาร (หน้า {activePage?.page_number ?? 1}/{totalPages})</div>
      </div>
      <div class="stat-card">
        <div class="stat-val" style="color:var(--accent)">
          {totalThai.toLocaleString()}<span class="stat-sep">/</span
          >{totalEng.toLocaleString()}
        </div>
        <div class="stat-lbl">จำนวนคำไทย / อังกฤษ</div>
      </div>
      <div class="stat-card">
        <div class="stat-val" style="color:var(--danger-soft-text)">
          {totalThaiErr}<span class="stat-sep">/</span><span style="color:var(--warning-soft-text)">{totalEngErr}</span>
        </div>
        <div class="stat-lbl">คำสะกดผิด (ไทย / EN)</div>
      </div>
      <div class="stat-card">
        <div class="stat-val" style="color:#d8b4fe">
          {totalSemantic}<span class="stat-sep">/</span><span style="color:#38bdf8">{totalFormat}</span>
        </div>
        <div class="stat-lbl">ผิดบริบท / ผิดฟอร์แมต</div>
      </div>
      <div class="stat-card">
        <div class="stat-val" style="color:{parseFloat(accuracyRate) >= 98 ? 'var(--success-soft-text)' : parseFloat(accuracyRate) >= 93 ? 'var(--warning-soft-text)' : 'var(--danger-soft-text)'}">
          {accuracyRate}%
        </div>
        <div class="stat-lbl">ความแม่นยำ (อัตราผิด {errRate}%)</div>
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

      {#if pages.length > 5}
        <div class="page-jump-wrap">
          <select 
            class="page-jump-select"
            aria-label="ข้ามไปยังหน้าที่ต้องการ"
            value={activePageIdx}
            on:change={(e) => { activePageIdx = parseInt(e.currentTarget.value, 10); scrollTabsToSelected(); }}
          >
            {#each pages as p, i}
              <option value={i}>หน้า {p.page_number} ({i + 1}/{pages.length})</option>
            {/each}
          </select>
        </div>
      {/if}
    </div>


    <!-- ── View mode tabs + filter ── -->
    <div class="toolbar">
      <div class="view-tabs" role="tablist" aria-label="โหมดการแสดงผล OCR">
        {#each [
          ["errors", `คำผิด (${pageErrors.length})`],
          ["split", "เทียบต้นฉบับ (Split)"],
          ["highlight", "ไฮไลท์ข้อความ"],
          ["text", "ตาราง & ข้อความ"],
          ["markdown", "แก้ไขมาร์กดาวน์"],
          ["preview", "ภาพต้นฉบับ"]
        ] as [v, label]}
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === v}
            class="vtab"
            class:active={viewMode === v}
            on:click={() => (viewMode = v)}>{label}</button
          >
        {/each}
      </div>
      {#if viewMode === "errors" || viewMode === "split"}
        <div class="toolbar-right-controls">
          <div class="highlight-legend" aria-label="คำอธิบายสีไฮไลท์">
            <span class="hl-item"><span class="hl-dot th"></span>ไทย</span>
            <span class="hl-item"><span class="hl-dot en"></span>อังกฤษ</span>
            <span class="hl-item"><span class="hl-dot sm"></span>บริบท</span>
            <span class="hl-item"><span class="hl-dot fmt"></span>ฟอร์แมต</span>
          </div>
          {#if pageErrors.length > 3}
            <div class="err-search-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <input
                type="text"
                bind:value={errorSearchQuery}
                placeholder="ค้นหาคำผิด..."
                aria-label="ค้นหาในรายการคำผิด"
              />
              {#if errorSearchQuery}
                <button type="button" class="err-search-clear" on:click={() => (errorSearchQuery = "")} aria-label="ล้างคำค้นหา">✕</button>
              {/if}
            </div>
          {/if}
          {#if fixableCount > 0}
            <button
              type="button"
              class="btn-autofix-all"
              on:click={applyAllSuggestions}
              title="แทนที่คำผิดทั้งหมดในหน้านี้ด้วยคำแนะนำอันดับแรก"
            >
              แก้ไขอัตโนมัติ ({fixableCount})
            </button>
          {/if}
          <div class="lang-filter" role="group" aria-label="กรองภาษาคำผิด">
            {#each [["all", "ทั้งหมด"], ["thai", "ไทย (TH)"], ["english", "อังกฤษ (EN)"], ["semantic_fmt", "บริบท / ฟอร์แมต"]] as [v, label]}
              <button
                type="button"
                class="filter-btn"
                class:active={filterLang === v}
                on:click={() => (filterLang = v)}>{label}</button
              >
            {/each}
          </div>
        </div>
      {:else if viewMode === "highlight"}
        <div class="highlight-legend" aria-label="คำอธิบายสีไฮไลท์">
          <span class="hl-item"><span class="hl-dot th"></span>สะกดผิดไทย</span>
          <span class="hl-item"><span class="hl-dot en"></span>สะกดผิดอังกฤษ</span>
          <span class="hl-item"><span class="hl-dot sm"></span>คำผิดบริบท</span>
          <span class="hl-item"><span class="hl-dot fmt"></span>ผิดฟอร์แมต</span>
        </div>
      {:else if viewMode === "preview"}
        <div class="toolbar-right-controls">
          <label class="box-toggle-pill">
            <input type="checkbox" bind:checked={showPreviewBoxes} />
            <span>แสดงกรอบคำผิดบนภาพ</span>
          </label>
          <div class="zoom-controls" role="group" aria-label="ปรับขนาดภาพ">
            {#each [75, 100, 125, 150] as z}
              <button type="button" class="filter-btn" class:active={previewZoom === z} on:click={() => (previewZoom = z)}>{z}%</button>
            {/each}
          </div>
        </div>
      {:else if viewMode === "markdown"}
        <div class="toolbar-right-controls">
          <button type="button" class="btn-autofix-all" on:click={saveManualTextEdit}>
            บันทึกการแก้ไขข้อความ
          </button>
          <button type="button" class="filter-btn" on:click={runManualSpellCheck} disabled={checkingSpell}>
            {checkingSpell ? "กำลังตรวจ..." : "ตรวจคำผิดหลังแก้ไข"}
          </button>
        </div>
      {/if}
    </div>

    <!-- ── Content ── -->
    <div class="content-scroll" class:is-preview={viewMode === "preview"} class:is-split={viewMode === "split"}>
      <!-- PREVIEW VIEW -->
      {#if viewMode === "preview"}
        <div class="preview-container mode-transition-stage">
          {#if activePage}
            <div class="page-wrap" class:zoom-100={previewZoom === 100} style="width: {previewZoom}%;">
              <img
                src="/api/view/{activePage.session_id}/{activePage.page_number}"
                alt="Page {activePage.page_number}"
                class="page-img"
              />

              {#if showPreviewBoxes}
                <!-- Highlight Overlay -->
                <div class="overlay">
                  {#each filteredErrors as err}
                    {#if err.box}
                      <button
                        type="button"
                        class="error-box"
                        data-err-key={getErrKey(err)}
                        class:is-linked={isSameError(hoveredErr, err) || isSameError(focusedErr, err)}
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
                        aria-label={`จุดที่พบ: ${err.token}`}
                        on:mouseenter={() => (hoveredErr = err)}
                        on:mouseleave={() => { if (isSameError(hoveredErr, err)) hoveredErr = null; }}
                        on:click={() => focusErrorOnPage(err)}
                      >
                        <span class="error-box-tooltip">
                          <strong>{err.token}</strong>
                          {#if err.suggestions?.length}
                            <span class="eb-arrow">→</span>
                            <span class="eb-sugg">{err.suggestions.slice(0, 2).join(", ")}</span>
                          {:else if err.message}
                            <span class="eb-msg">{err.message}</span>
                          {/if}
                        </span>
                      </button>
                    {/if}
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>

      <!-- SPLIT VIEW (Original Image + Highlighted Text & Quick Fixer Side-by-Side) -->
      {:else if viewMode === "split"}
        <div class="split-workbench mode-transition-stage">
          <div class="split-pane split-left">
            <div class="split-pane-header">
              <div class="sph-title-wrap">
                <span class="sph-dot"></span>
                <span>ภาพเอกสารต้นฉบับ (หน้า {activePage?.page_number ?? 1})</span>
              </div>
              <label class="box-toggle-pill">
                <input type="checkbox" bind:checked={showPreviewBoxes} />
                <span>กรอบไฮไลต์ ({filteredErrors.length})</span>
              </label>
            </div>
            <div class="split-pane-body preview-bg" bind:this={splitLeftScrollEl}>
              {#if activePage}
                <div class="page-wrap">
                  <img
                    src="/api/view/{activePage.session_id}/{activePage.page_number}"
                    alt="Page {activePage.page_number}"
                    class="page-img"
                  />
                  {#if showPreviewBoxes}
                    <div class="overlay">
                      {#each filteredErrors as err}
                        {#if err.box}
                          <button
                            type="button"
                            class="error-box"
                            data-err-key={getErrKey(err)}
                            class:is-linked={isSameError(hoveredErr, err) || isSameError(focusedErr, err)}
                            class:th={err.lang === "thai" && err.error_type !== "format" && err.error_type !== "semantic"}
                            class:en={err.lang === "english"}
                            class:sm={err.error_type === "semantic"}
                            class:fmt={err.error_type === "format"}
                            style="
                              left: {err.box_norm ? err.box_norm[0][0] * 100 : (err.box[0][0] / activePage.width) * 100}%;
                              top: {err.box_norm ? err.box_norm[0][1] * 100 : (err.box[0][1] / activePage.height) * 100}%;
                              width: {err.box_norm ? (err.box_norm[1][0] - err.box_norm[0][0]) * 100 : ((err.box[1][0] - err.box[0][0]) / activePage.width) * 100}%;
                              height: {err.box_norm ? (err.box_norm[2][1] - err.box_norm[0][1]) * 100 : ((err.box[2][1] - err.box[0][1]) / activePage.height) * 100}%;
                            "
                            aria-label={`จุดที่พบ: ${err.token}`}
                            on:mouseenter={() => (hoveredErr = err)}
                            on:mouseleave={() => { if (isSameError(hoveredErr, err)) hoveredErr = null; }}
                            on:click={() => focusErrorOnPage(err)}
                          >
                            <span class="error-box-tooltip">
                              <strong>{err.token}</strong>
                              {#if err.suggestions?.length}
                                <span class="eb-arrow">→</span>
                                <span class="eb-sugg">{err.suggestions.slice(0, 2).join(", ")}</span>
                              {:else if err.message}
                                <span class="eb-msg">{err.message}</span>
                              {/if}
                            </span>
                          </button>
                        {/if}
                      {/each}
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          </div>

          <div class="split-pane split-right">
            <div class="split-pane-header">
              <div class="sph-title-wrap">
                <span class="sph-dot accent"></span>
                <span>ข้อความที่สกัดได้ &amp; จุดที่ตรวจพบ ({filteredErrors.length} รายการ)</span>
              </div>
              {#if !activePage?.spell_check}
                <button
                  type="button"
                  class="btn-inline-check"
                  on:click={runManualSpellCheck}
                  disabled={checkingSpell}
                >
                  {checkingSpell ? "กำลังตรวจ..." : "ตรวจคำผิดหน้านี้"}
                </button>
              {/if}
            </div>
            <div class="split-pane-body" bind:this={splitRightScrollEl}>
              {#if filteredErrors.length > 0}
                <div class="split-quick-errors">
                  {#each filteredErrors as err}
                    <div
                      class="split-err-card"
                      role="button"
                      tabindex="0"
                      class:is-linked={isSameError(hoveredErr, err) || isSameError(focusedErr, err)}
                      on:mouseenter={() => (hoveredErr = err)}
                      on:mouseleave={() => { if (isSameError(hoveredErr, err)) hoveredErr = null; }}
                      on:click={() => focusErrorOnPage(err)}
                      on:keydown={(e) => { if (e.key === "Enter" || e.key === " ") focusErrorOnPage(err); }}
                    >
                      <div class="split-err-top">
                        <span class="et-line">บรรทัด {err.line_number}</span>
                        <strong
                          class="et-word"
                          class:word-th={err.lang === "thai" && err.error_type !== "semantic" && err.error_type !== "format"}
                          class:word-en={err.lang === "english"}
                          class:word-sm={err.error_type === "semantic"}
                          class:word-fmt={err.error_type === "format"}
                        >{err.token}</strong>
                        {#if err.error_type === "format"}
                          <span class="badge-fmt">FMT</span>
                        {:else if err.error_type === "semantic"}
                          <span class="badge-sm">SEM</span>
                        {:else if err.lang === "thai"}
                          <span class="badge-th">TH</span>
                        {:else}
                          <span class="badge-en">EN</span>
                        {/if}
                        {#if err.message}
                          <span class="et-reason">({err.message})</span>
                        {/if}
                      </div>
                      <div class="et-suggs">
                        {#each (err.suggestions || []).slice(0, 3) as s}
                          <button type="button" class="sugg" on:click|stopPropagation={() => applySuggestion(err, s)}>→ {s}</button>
                        {/each}
                        {#if err.error_type !== "format"}
                          <button type="button" class="btn-ignore-dict" on:click|stopPropagation={() => ignoreAndAddToDict(err)}>+ พจนานุกรม</button>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
              <div class="highlight-view rendered-html">
                {@html highlightedHtml}
              </div>
            </div>
          </div>
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
              <span>คำที่พบ &amp; คำอธิบาย</span>
              <span>ประเภท</span>
              <span>คลิกคำแนะนำเพื่อแทนที่ / จัดการ</span>
            </div>
            {#each filteredErrors as err}
              <div class="et-row">
                <span class="et-line">บรรทัด {err.line_number}</span>
                <div class="et-word-col">
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
                  {#if err.message}
                    <span class="et-reason">{err.message}</span>
                  {/if}
                </div>
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
                <div class="et-suggs">
                  {#if err.suggestions?.length}
                    {#each err.suggestions.slice(0, 4) as s}
                      <button
                        type="button"
                        class="sugg"
                        title={`คลิกเพื่อแทนที่ "${err.token}" ด้วย "${s}"`}
                        on:click={() => applySuggestion(err, s)}
                      >
                        → {s}
                      </button>
                    {/each}
                  {:else}
                    <span class="no-sugg">—</span>
                  {/if}
                  {#if err.error_type !== "format"}
                    <button
                      type="button"
                      class="btn-ignore-dict"
                      title={`เพิ่ม "${err.token}" เข้าพจนานุกรมคำเฉพาะและไม่นับเป็นคำผิด`}
                      on:click={() => ignoreAndAddToDict(err)}
                    >
                      + พจนานุกรม
                    </button>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}

        <!-- HIGHLIGHT VIEW -->
      {:else if viewMode === "highlight"}
        <div class="highlight-view rendered-html">
          {@html highlightedHtml}
        </div>

        <!-- MARKDOWN EDITOR VIEW -->
      {:else if viewMode === "markdown"}
        <div class="markdown-editor-wrap">
          {#if activePage}
            <textarea
              class="markdown-editor-textarea"
              bind:value={activePage.text}
              aria-label={`แก้ไขข้อความมาร์กดาวน์หน้า ${activePage.page_number}`}
              placeholder="ข้อความ OCR ในหน้านี้..."
            ></textarea>
          {/if}
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
  <div class="modal-backdrop" role="presentation" on:click|self={() => { if (!isSaving) showSaveModal = false; }}>
    <div class="modal-content save-project-modal" class:is-saving={isSaving} role="dialog" aria-modal="true" aria-labelledby="save-project-modal-title" on:click|stopPropagation>
      <div class="modal-top-accent" aria-hidden="true"></div>

      <div class="modal-header-row">
        <div class="modal-title-block">
          <div class="modal-icon-badge" aria-hidden="true">
            <span class="modal-icon-ring"></span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="20" height="20">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
            </svg>
          </div>
          <div class="modal-title-texts">
            <h3 id="save-project-modal-title">บันทึกเอกสารเข้า Project</h3>
            <p class="modal-subtitle">จัดเก็บเป็นฐานความรู้ (Knowledge Base) พร้อมสร้าง Vector Index สำหรับ AI QA</p>
          </div>
        </div>
        <button type="button" class="btn-modal-close" aria-label="ปิดหน้าต่างบันทึกเอกสาร" on:click={() => showSaveModal = false} disabled={isSaving}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <!-- Document Telemetry Strip -->
      <div class="save-doc-meta-strip">
        <div class="sdm-item">
          <span class="sdm-lbl">ประเภทไฟล์</span>
          <span class="sdm-val badge-type">{saveForm.doc_type || 'PDF'}</span>
        </div>
        <div class="sdm-divider"></div>
        <div class="sdm-item">
          <span class="sdm-lbl">จำนวนหน้า</span>
          <span class="sdm-val">{totalPages} หน้า</span>
        </div>
        <div class="sdm-divider"></div>
        <div class="sdm-item">
          <span class="sdm-lbl">คำไทย / อังกฤษ</span>
          <span class="sdm-val">{totalThai.toLocaleString()} / {totalEng.toLocaleString()}</span>
        </div>
        <div class="sdm-divider"></div>
        <div class="sdm-item">
          <span class="sdm-lbl">ความแม่นยำ</span>
          <span class="sdm-val accent">{accuracyRate}%</span>
        </div>
      </div>

      <div class="modal-form-body">
        <div class="form-group">
          <label for="save-filename">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
            <span>ชื่อไฟล์เอกสาร</span>
          </label>
          <div class="input-icon-wrap">
            <input
              id="save-filename"
              type="text"
              bind:value={saveForm.filename}
              class="form-input"
              placeholder="ระบุชื่อไฟล์เอกสาร..."
              disabled={isSaving}
            />
          </div>
        </div>

        <div class="form-grid-2">
          <div class="form-group">
            <label for="save-project">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
              </svg>
              <span>โครงการ (Project)</span>
            </label>
            <CustomSelect 
              id="save-project" 
              bind:value={saveForm.project_id} 
              options={projectSelectOptions} 
              width="100%"
            />
          </div>

          <div class="form-group">
            <label for="save-category">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="13" height="13">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 6h.008v.008H6V6z" />
              </svg>
              <span>หมวดหมู่เอกสาร</span>
            </label>
            <CustomSelect 
              id="save-category" 
              bind:value={saveForm.doc_category} 
              options={categorySelectOptions} 
              width="100%"
            />
          </div>
        </div>

        <div class="form-group toggle-group" class:is-golden={saveForm.is_golden_data}>
          <div class="golden-info">
            <div class="golden-icon-box" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
              </svg>
            </div>
            <div class="golden-texts">
              <label class="label-text" for="save-golden-toggle">กำหนดเป็น Golden Data</label>
              <span class="golden-desc">ใช้เป็นเอกสารมาตรฐานหลักสำหรับ AI วิเคราะห์และอ้างอิง Test Case</span>
            </div>
          </div>
          <label class="toggle-wrap" for="save-golden-toggle">
            <input id="save-golden-toggle" type="checkbox" bind:checked={saveForm.is_golden_data} disabled={isSaving}/>
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
          </label>
        </div>

        {#if isSaving}
          <div class="saving-progress-banner" role="status" aria-live="polite">
            <div class="spb-bar">
              <div class="spb-shimmer"></div>
            </div>
            <div class="spb-text">
              <span class="save-spinner"></span>
              <span>กำลังแบ่ง Chunk, สร้าง Vector Embeddings และบันทึกเข้าโครงการ...</span>
            </div>
          </div>
        {/if}
      </div>

      <div class="modal-actions">
        <button type="button" class="btn-cancel" on:click={() => showSaveModal = false} disabled={isSaving}>ยกเลิก</button>
        <button 
          type="button"
          class="btn-save" 
          on:click={saveToProject} 
          disabled={isSaving || !saveForm.project_id || !saveForm.filename?.trim()}
        >
          {#if isSaving}
            <span class="save-spinner"></span>
            <span>กำลังบันทึก...</span>
          {:else}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <span>บันทึกเข้าโครงการ</span>
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

  /* ── OCR Loading Studio & Animated 3D Crystal Prism Logo ── */
  .loading-screen-wrap {
    overflow-y: auto;
    padding: 24px 20px;
  }
  .ocr-loading-studio {
    width: 100%;
    max-width: 800px;
    box-sizing: border-box;
    overflow: hidden;
    background:
      radial-gradient(circle at 50% 18%, rgba(168, 85, 247, 0.14) 0%, rgba(99, 102, 241, 0.06) 45%, transparent 72%),
      linear-gradient(165deg, rgba(20, 23, 38, 0.88) 0%, rgba(12, 14, 24, 0.94) 100%);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: 26px;
    padding: 24px 28px 26px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    box-shadow: 0 20px 56px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    margin: auto;
  }

  .loading-studio-top {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }
  .loading-file-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 12.5px;
    color: var(--text-main);
    min-width: 0;
    max-width: 420px;
  }
  .loading-file-pill svg {
    color: #c084fc;
    flex-shrink: 0;
  }
  .file-pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
    flex-shrink: 0;
  }
  .lf-name {
    font-weight: 600;
  }
  .lf-size {
    color: var(--text-muted);
    font-size: 11.5px;
    flex-shrink: 0;
  }
  .loading-engine-tags {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .le-tag {
    font-family: var(--font-en);
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
  }
  .le-tag.accent {
    background: rgba(168, 85, 247, 0.15);
    border-color: rgba(168, 85, 247, 0.38);
    color: #e9d5ff;
  }

  /* ── Animated 3D Crystal Prism & Orbital Quantum Scanner ── */
  .spectra-quantum-loader {
    position: relative;
    width: 210px;
    height: 210px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 4px 0 6px;
    flex-shrink: 0;
  }
  .quantum-aura-outer {
    position: absolute;
    width: 190px;
    height: 190px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.24) 0%, rgba(99, 102, 241, 0.08) 55%, transparent 75%);
    filter: blur(14px);
    animation: auraBreathe 3.6s ease-in-out infinite alternate;
    pointer-events: none;
  }
  .quantum-aura-inner {
    position: absolute;
    width: 116px;
    height: 116px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.22) 0%, rgba(168, 85, 247, 0.18) 60%, transparent 80%);
    filter: blur(8px);
    animation: auraBreathe 2.4s ease-in-out infinite alternate-reverse;
    pointer-events: none;
  }

  .orbit-svg-outer {
    position: absolute;
    width: 210px;
    height: 210px;
    animation: orbitSpinCW 11s linear infinite;
    pointer-events: none;
  }
  .orbit-svg-mid {
    position: absolute;
    width: 174px;
    height: 174px;
    animation: orbitSpinCCW 8.5s linear infinite;
    pointer-events: none;
  }
  .orbit-svg-progress {
    position: absolute;
    width: 144px;
    height: 144px;
    pointer-events: none;
  }
  .gauge-progress-arc {
    transition: stroke-dashoffset 0.5s cubic-bezier(0.22, 1, 0.36, 1);
    filter: drop-shadow(0 0 6px rgba(168, 85, 247, 0.65));
  }

  /* Floating Quantum Light Particles */
  .q-spark {
    position: absolute;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    pointer-events: none;
  }
  .q-spark.s1 {
    top: 24px;
    left: 38px;
    background: #38bdf8;
    box-shadow: 0 0 10px #38bdf8;
    animation: sparkFloat1 3.2s ease-in-out infinite;
  }
  .q-spark.s2 {
    top: 36px;
    right: 28px;
    background: #c084fc;
    box-shadow: 0 0 10px #c084fc;
    animation: sparkFloat2 3.8s ease-in-out infinite;
  }
  .q-spark.s3 {
    bottom: 34px;
    left: 30px;
    background: #818cf8;
    box-shadow: 0 0 10px #818cf8;
    animation: sparkFloat2 3.4s ease-in-out infinite reverse;
  }
  .q-spark.s4 {
    bottom: 28px;
    right: 36px;
    background: #22d3ee;
    box-shadow: 0 0 10px #22d3ee;
    animation: sparkFloat1 2.9s ease-in-out infinite reverse;
  }

  .prism-core-stage {
    position: relative;
    width: 112px;
    height: 112px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, rgba(30, 35, 62, 0.92), rgba(11, 13, 24, 0.96));
    border: 1px solid rgba(168, 85, 247, 0.42);
    box-shadow:
      0 8px 28px rgba(0, 0, 0, 0.55),
      inset 0 0 18px rgba(168, 85, 247, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    z-index: 2;
  }

  /* Sweeping Laser OCR Scan Beam */
  .prism-laser-beam {
    position: absolute;
    left: 8px;
    right: 8px;
    height: 2px;
    background: linear-gradient(90deg, transparent 0%, #38bdf8 20%, #ffffff 50%, #c084fc 80%, transparent 100%);
    box-shadow: 0 0 12px 2px rgba(56, 189, 248, 0.85), 0 -10px 20px rgba(168, 85, 247, 0.45);
    z-index: 4;
    animation: laserSweep 2.6s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
    pointer-events: none;
  }

  .spectra-animated-prism {
    width: 82px;
    height: 82px;
    z-index: 3;
    filter: drop-shadow(0 0 14px rgba(168, 85, 247, 0.65));
    animation: prism3DFloat 4s ease-in-out infinite;
  }
  .prism-outer-halo {
    transform-origin: 60px 60px;
    animation: orbitSpinCCW 14s linear infinite;
  }
  .prism-facet.facet-left {
    animation: facetPulse 2.4s ease-in-out infinite alternate;
  }
  .prism-facet.facet-right {
    animation: facetPulse 2.4s ease-in-out infinite alternate-reverse;
  }
  .prism-inner-diamond {
    transform-origin: 60px 47px;
    animation: innerCorePulse 2s ease-in-out infinite alternate;
  }
  .vertex-node {
    animation: vertexTwinkle 1.8s ease-in-out infinite alternate;
  }
  .vertex-node.v2,
  .vertex-node.v4 {
    animation-delay: 0.9s;
  }

  .loader-pct-pill {
    position: absolute;
    bottom: -4px;
    z-index: 5;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    border: 1px solid rgba(255, 255, 255, 0.35);
    color: #ffffff;
    font-family: var(--font-en);
    font-size: 12.5px;
    font-weight: 700;
    padding: 2px 12px;
    border-radius: 999px;
    box-shadow: 0 4px 14px rgba(168, 85, 247, 0.55);
    font-variant-numeric: tabular-nums;
  }

  @keyframes orbitSpinCW {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  @keyframes orbitSpinCCW {
    from { transform: rotate(360deg); }
    to { transform: rotate(0deg); }
  }
  @keyframes auraBreathe {
    0% { transform: scale(0.92); opacity: 0.65; }
    100% { transform: scale(1.08); opacity: 1; }
  }
  @keyframes laserSweep {
    0% { top: 14%; opacity: 0.2; }
    15% { opacity: 1; }
    50% { top: 84%; opacity: 1; }
    85% { opacity: 1; }
    100% { top: 14%; opacity: 0.2; }
  }
  @keyframes prism3DFloat {
    0%, 100% { transform: translateY(0) scale(1) rotate(0deg); }
    25% { transform: translateY(-4px) scale(1.04) rotate(2.5deg); }
    50% { transform: translateY(0) scale(1.06) rotate(0deg); }
    75% { transform: translateY(4px) scale(1.03) rotate(-2.5deg); }
  }
  @keyframes facetPulse {
    0% { opacity: 0.55; }
    100% { opacity: 0.95; }
  }
  @keyframes innerCorePulse {
    0% { opacity: 0.7; transform: scale(0.96); }
    100% { opacity: 1; transform: scale(1.04); }
  }
  @keyframes vertexTwinkle {
    0% { opacity: 0.5; transform: scale(0.85); }
    100% { opacity: 1; transform: scale(1.2); }
  }
  @keyframes sparkFloat1 {
    0%, 100% { transform: translate(0, 0) scale(0.9); opacity: 0.55; }
    50% { transform: translate(6px, -8px) scale(1.25); opacity: 1; }
  }
  @keyframes sparkFloat2 {
    0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.6; }
    50% { transform: translate(-7px, -6px) scale(1.3); opacity: 1; }
  }

  /* Headline Block */
  .loading-headline-block {
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 5px;
    max-width: 580px;
  }
  .loading-main-title {
    font-size: 19px;
    font-weight: 700;
    color: var(--text-main);
    margin: 0;
    font-family: var(--font-th);
  }
  .loading-sub-label {
    font-size: 13.5px;
    color: var(--primary-soft-text);
    margin: 0;
    line-height: 1.5;
  }

  /* 4-Tile Live Telemetry Grid */
  .loading-telemetry-grid {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }
  .lt-card {
    min-width: 0;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 11px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    text-align: left;
  }
  .lt-label {
    font-size: 11px;
    color: var(--text-muted);
  }
  .lt-val {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-main);
    font-variant-numeric: tabular-nums;
  }
  .lt-val.primary {
    color: #c7d2fe;
  }
  .lt-val.accent {
    color: #67e8f9;
  }
  .lt-sep {
    color: var(--text-dim);
    font-weight: 400;
  }
  .lt-sub {
    font-size: 10.5px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Progress Bar & 4-Stage Pipeline Stepper */
  .prog-wrap {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .prog-track {
    height: 8px;
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    overflow: hidden;
    position: relative;
  }
  .prog-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary), var(--secondary), var(--accent));
    transition: width 0.45s cubic-bezier(0.22, 1, 0.36, 1);
    box-shadow: 0 0 14px var(--primary-glow);
    position: relative;
    overflow: hidden;
  }
  .prog-shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.45) 50%, transparent 100%);
    animation: barShimmer 1.6s linear infinite;
  }
  @keyframes barShimmer {
    from { transform: translateX(-100%); }
    to { transform: translateX(100%); }
  }

  .loading-pipeline-stepper {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
  }
  .lp-step {
    min-width: 0;
    overflow: hidden;
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 8px 9px;
    border-radius: 11px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    text-align: left;
    transition: border-color 0.25s ease, background-color 0.25s ease;
  }
  .lp-step.active {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.45);
  }
  .lp-step.done {
    background: rgba(16, 185, 129, 0.08);
    border-color: rgba(16, 185, 129, 0.28);
  }
  .lp-step-indicator {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.07);
    color: var(--text-muted);
    font-family: var(--font-en);
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .lp-step.active .lp-step-indicator {
    background: var(--primary);
    color: #ffffff;
    box-shadow: 0 0 10px rgba(99, 102, 241, 0.65);
  }
  .lp-step.done .lp-step-indicator {
    background: var(--success);
    color: #051b11;
  }
  .lp-step-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
    line-height: 1.25;
  }
  .lp-step-title {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .lp-step.active .lp-step-title,
  .lp-step.done .lp-step-title {
    color: var(--text-main);
  }
  .lp-step-sub {
    font-size: 10px;
    color: var(--text-dim);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Live Extracted Page Preview Stream */
  .loading-live-stream-box {
    width: 100%;
    background: rgba(10, 12, 22, 0.65);
    border: 1px solid rgba(168, 85, 247, 0.25);
    border-radius: 14px;
    padding: 11px 14px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    text-align: left;
  }
  .lls-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }
  .lls-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #e9d5ff;
  }
  .lls-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #a855f7;
    box-shadow: 0 0 8px #a855f7;
  }
  .lls-err-count {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--warning-soft-text);
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.28);
    padding: 2px 8px;
    border-radius: 999px;
  }
  .lls-err-count.clean {
    color: var(--success-soft-text);
    background: rgba(16, 185, 129, 0.12);
    border-color: rgba(16, 185, 129, 0.28);
  }
  .lls-snippet {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Interactive Actions Footer */
  .loading-studio-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
    width: 100%;
    padding-top: 4px;
  }
  .btn-view-partial {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: var(--success-soft-text);
    font-family: var(--font-th);
    font-size: 12.5px;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 10px;
    cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  }
  .btn-view-partial:hover {
    background: rgba(16, 185, 129, 0.28);
    border-color: rgba(16, 185, 129, 0.65);
    color: #ffffff;
  }
  .btn-cancel-scan {
    background: rgba(244, 63, 94, 0.1);
    border: 1px solid rgba(244, 63, 94, 0.28);
    color: var(--danger-soft-text);
    font-family: var(--font-th);
    font-size: 12.5px;
    font-weight: 500;
    padding: 8px 16px;
    border-radius: 10px;
    cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  }
  .btn-cancel-scan:hover {
    background: var(--danger-solid);
    border-color: var(--danger-solid);
    color: #ffffff;
  }

  @media (max-width: 720px) {
    .loading-telemetry-grid,
    .loading-pipeline-stepper {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .orbit-svg-outer,
    .orbit-svg-mid,
    .prism-outer-halo,
    .spectra-animated-prism,
    .prism-laser-beam,
    .prog-shimmer,
    .q-spark,
    .mode-transition-stage,
    .error-box,
    .modal-backdrop,
    .modal-content,
    .modal-icon-ring,
    .spb-shimmer {
      animation: none !important;
    }
    .split-err-card,
    .error-box,
    .error-box-tooltip,
    .btn-modal-close,
    .btn-save,
    .btn-save::after,
    .golden-icon-box,
    .toggle-thumb {
      transition: none !important;
    }
  }

  /* ── Header ── */
  .rp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(18, 20, 28, 0.4);
    flex-shrink: 0;
    gap: 12px;
  }
  .rp-title-group {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }
  .btn-back-upload {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: var(--primary-soft-text);
    font-family: var(--font-th);
    font-size: 12.5px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  }
  .btn-back-upload:hover {
    background: rgba(99, 102, 241, 0.28);
    border-color: rgba(99, 102, 241, 0.6);
    color: #ffffff;
  }
  .rp-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-main);
    min-width: 0;
  }
  .engine-mode-pill {
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #e9d5ff;
    font-family: var(--font-en);
    font-size: 10.5px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .header-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
  .btn-sm {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--glass-bg-hover);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-family: var(--font-th);
    font-size: 12.5px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
  }
  .btn-sm:hover {
    color: var(--text-main);
    border-color: var(--glass-border-light);
    background: rgba(255, 255, 255, 0.08);
  }
  .btn-sm.btn-save-proj {
    color: var(--primary-soft-text);
    border-color: rgba(99, 102, 241, 0.38);
    background: rgba(99, 102, 241, 0.12);
  }
  .btn-sm.btn-save-proj:hover {
    color: #ffffff;
    border-color: rgba(99, 102, 241, 0.65);
    background: rgba(99, 102, 241, 0.25);
  }

  /* ── Stat bar ── */
  .stat-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(18, 20, 28, 0.28);
    flex-shrink: 0;
  }
  .stat-card {
    flex: 1;
    padding: 12px 16px;
    text-align: center;
    border-right: 1px solid var(--glass-border);
  }
  .stat-card:last-child {
    border-right: none;
  }
  .stat-val {
    font-size: 20px;
    font-weight: 700;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
  }
  .stat-sep {
    font-size: 14px;
    color: var(--text-dim);
    margin: 0 3px;
  }
  .stat-lbl {
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.03em;
    margin-top: 4px;
  }


  /* ── Page tabs ── */
  .page-tabs-wrapper {
    display: flex;
    align-items: center;
    border-bottom: 1px solid var(--glass-border);
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
    transition: color 0.2s ease, background-color 0.2s ease;
    flex-shrink: 0;
  }
  .nav-tab-btn:hover:not(:disabled) {
    color: var(--primary-soft-text);
    background: rgba(99, 102, 241, 0.12);
  }
  .nav-tab-btn:disabled {
    opacity: 0.25;
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
    background: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
  }
  .page-tabs-bar::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.24);
  }
  .page-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-family: var(--font-th);
    font-size: 12px;
    padding: 5px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.18s ease;
    flex-shrink: 0;
  }
  .page-tab:hover {
    color: var(--text-main);
    border-color: var(--glass-border-light);
  }
  .page-tab.active {
    background: rgba(99, 102, 241, 0.16);
    border-color: var(--primary);
    color: #ffffff;
    font-weight: 600;
    box-shadow: 0 2px 10px rgba(99, 102, 241, 0.22);
  }
  .page-jump-wrap {
    display: flex;
    align-items: center;
    gap: 6px;
    padding-left: 10px;
    padding-right: 12px;
    border-left: 1px solid var(--glass-border);
    margin-left: 4px;
    flex-shrink: 0;
  }
  .page-jump-select {
    background: rgba(12, 14, 24, 0.72);
    border: 1px solid var(--glass-border-light);
    color: var(--text-main);
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 12px;
    font-family: var(--font-th);
    font-variant-numeric: tabular-nums;
    cursor: pointer;
    outline: none;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .page-jump-select:hover,
  .page-jump-select:focus-visible {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.22);
  }
  .page-jump-select option {
    background: #141726;
    color: var(--text-main);
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
    border-bottom: 1px solid var(--glass-border);
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
    color: var(--text-muted);
    font-family: var(--font-th);
    font-size: 12.5px;
    padding: 5px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .vtab:hover {
    color: var(--text-main);
    background: rgba(255, 255, 255, 0.04);
  }
  .vtab.active {
    background: rgba(99, 102, 241, 0.16);
    border-color: var(--primary);
    color: #ffffff;
    font-weight: 600;
  }
  .toolbar-right-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .err-search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    padding: 3px 10px;
  }
  .err-search-box svg {
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .err-search-box input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main);
    font-family: var(--font-th);
    font-size: 12px;
    width: 130px;
  }
  .err-search-clear {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 11px;
    cursor: pointer;
    padding: 0 2px;
  }
  .highlight-legend {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    font-size: 11.5px;
    color: var(--text-muted);
  }
  .hl-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .hl-dot {
    width: 10px;
    height: 10px;
    border-radius: 3px;
  }
  .hl-dot.th { background: #f43f5e; }
  .hl-dot.en { background: #f59e0b; }
  .hl-dot.sm { background: #a855f7; }
  .hl-dot.fmt { border: 1.5px dashed #38bdf8; background: rgba(56, 189, 248, 0.25); }

  .box-toggle-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted);
    cursor: pointer;
    user-select: none;
  }
  .zoom-controls {
    display: flex;
    gap: 4px;
  }

  /* ── Split Workbench View ── */
  .content-scroll.is-split {
    padding: 0;
    overflow: hidden;
  }
  .split-workbench {
    display: grid;
    grid-template-columns: 1fr 1fr;
    height: 100%;
    width: 100%;
    overflow: hidden;
  }
  .split-pane {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-width: 0;
    overflow: hidden;
  }
  .split-left {
    border-right: 1px solid var(--glass-border);
  }
  .split-pane-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    background: rgba(18, 20, 28, 0.55);
    border-bottom: 1px solid var(--glass-border);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .split-pane-body {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }
  .split-pane-body.preview-bg {
    background: var(--bg2);
    display: flex;
    justify-content: center;
    align-items: flex-start;
  }
  .split-quick-errors {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--glass-border);
  }
  .sph-title-wrap {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .sph-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--primary);
    box-shadow: 0 0 8px rgba(99, 102, 241, 0.75);
  }
  .sph-dot.accent {
    background: var(--secondary);
    box-shadow: 0 0 8px rgba(168, 85, 247, 0.75);
  }
  .btn-inline-check {
    background: rgba(168, 85, 247, 0.16);
    border: 1px solid rgba(168, 85, 247, 0.42);
    color: #e9d5ff;
    font-family: var(--font-th);
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 999px;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
  }
  .btn-inline-check:hover:not(:disabled) {
    background: rgba(168, 85, 247, 0.3);
    border-color: rgba(168, 85, 247, 0.7);
    color: #ffffff;
  }
  .split-err-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    cursor: pointer;
    transition: background-color 0.2s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .split-err-card:hover,
  .split-err-card.is-linked {
    background: rgba(168, 85, 247, 0.1);
    border-color: rgba(168, 85, 247, 0.45);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28);
  }
  .split-err-top {
    display: flex;
    align-items: baseline;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* ── Markdown Live Editor ── */
  .markdown-editor-wrap {
    height: 100%;
    min-height: 420px;
    display: flex;
    flex-direction: column;
  }
  .markdown-editor-textarea {
    flex: 1;
    width: 100%;
    min-height: 420px;
    background: rgba(12, 14, 22, 0.75);
    border: 1px solid var(--glass-border-light);
    border-radius: 12px;
    padding: 16px;
    color: var(--text-main);
    font-family: 'Prompt', monospace;
    font-size: 14px;
    line-height: 1.75;
    resize: vertical;
    outline: none;
  }
  .markdown-editor-textarea:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
  }
  .btn-autofix-all {
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.35);
    color: var(--success-soft-text);
    font-family: var(--font-th);
    font-size: 11.5px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
  }
  .btn-autofix-all:hover {
    background: rgba(16, 185, 129, 0.28);
    border-color: rgba(16, 185, 129, 0.6);
    color: #ffffff;
  }
  .lang-filter {
    display: flex;
    gap: 4px;
  }
  .filter-btn {
    background: none;
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-family: var(--font-th);
    font-size: 11.5px;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .filter-btn.active {
    background: rgba(168, 85, 247, 0.16);
    border-color: rgba(168, 85, 247, 0.45);
    color: #ffffff;
    font-weight: 600;
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
    color: var(--text-muted);
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
    grid-template-columns: 90px 1fr 64px 1fr;
    gap: 12px;
    padding: 8px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    text-transform: uppercase;
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }
  .et-row {
    display: grid;
    grid-template-columns: 90px 1fr 64px 1fr;
    gap: 12px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--glass-border);
    align-items: center;
    transition: background-color 0.15s ease;
  }
  .et-row:last-child {
    border-bottom: none;
  }
  .et-row:hover {
    background: rgba(255, 255, 255, 0.03);
  }
  .et-line {
    font-size: 12px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .et-word-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .et-word {
    font-size: 15.5px;
    font-weight: 600;
  }
  .et-reason {
    font-size: 11.5px;
    color: var(--text-muted);
    line-height: 1.4;
  }
  .word-th {
    color: var(--danger-soft-text);
  }
  .word-en {
    color: var(--warning-soft-text);
  }
  .word-fmt {
    color: #7dd3fc;
  }
  .badge-th,
  .badge-en,
  .badge-sm,
  .badge-fmt {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    letter-spacing: 0.05em;
  }
  .badge-th {
    background: rgba(244, 63, 94, 0.14);
    color: var(--danger-soft-text);
    border: 1px solid rgba(244, 63, 94, 0.3);
  }
  .badge-en {
    background: rgba(245, 158, 11, 0.14);
    color: var(--warning-soft-text);
    border: 1px solid rgba(245, 158, 11, 0.3);
  }
  .badge-sm {
    background: rgba(168, 85, 247, 0.14);
    color: #d8b4fe;
    border: 1px solid rgba(168, 85, 247, 0.3);
  }
  .badge-fmt {
    background: rgba(56, 189, 248, 0.14);
    color: #7dd3fc;
    border: 1px solid rgba(56, 189, 248, 0.35);
  }
  .et-suggs {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .sugg {
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.28);
    color: var(--success-soft-text);
    border-radius: 99px;
    font-family: var(--font-th);
    font-size: 12px;
    font-weight: 500;
    padding: 3px 10px;
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }
  .sugg:hover {
    background: rgba(16, 185, 129, 0.26);
    border-color: rgba(16, 185, 129, 0.55);
    color: #ffffff;
  }
  .btn-ignore-dict {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    border-radius: 99px;
    font-family: var(--font-th);
    font-size: 11px;
    padding: 3px 9px;
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }
  .btn-ignore-dict:hover {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(99, 102, 241, 0.45);
    color: var(--primary-soft-text);
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
    color: #7dd3fc;
    background: rgba(56, 189, 248, 0.14);
    border-bottom: 2px dashed #38bdf8;
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  :global(.tok-err-th) {
    color: var(--danger-soft-text);
    background: rgba(244, 63, 94, 0.12);
    border-bottom: 2px solid var(--danger);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  :global(.tok-err-en) {
    color: var(--warning-soft-text);
    background: rgba(245, 158, 11, 0.12);
    border-bottom: 2px solid var(--warning);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  :global(.tok-err-sm) {
    color: #d8b4fe;
    background: rgba(168, 85, 247, 0.14);
    border-bottom: 2px solid var(--secondary);
    border-radius: 3px;
    padding: 0 2px;
    cursor: help;
  }
  .word-sm {
    color: #d8b4fe;
  }

  /* ── Plain text ── */
  .plain-view {
    font-family: var(--font-th);
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text-main);
    line-height: 1.9;
  }

  /* ── HTML Rendered ── */
  .rendered-html :global(.table-container) {
    width: 100%;
    overflow-x: auto;
    margin: 16px 0;
    border-radius: var(--radius-md, 12px);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.1));
    background: rgba(15, 23, 42, 0.7);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  }
  .rendered-html :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 0;
    color: var(--text-main, #f8fafc);
    background: transparent;
    font-size: 13.5px;
    line-height: 1.6;
  }
  .rendered-html :global(th),
  .rendered-html :global(td) {
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 14px;
    text-align: left;
    vertical-align: top;
    min-width: 120px;
    word-break: break-word;
  }
  .rendered-html :global(th) {
    background: rgba(30, 41, 59, 0.95);
    font-weight: 600;
    color: #e2e8f0;
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 2;
    border-bottom: 2px solid rgba(255, 255, 255, 0.15);
  }
  .rendered-html :global(tr:hover td) {
    background: rgba(255, 255, 255, 0.03);
  }
  .rendered-html :global(div[align="center"]) {
    text-align: center;
    font-weight: bold;
    margin: 12px 0;
  }
  .rendered-html :global(ol),
  .rendered-html :global(ul) {
    padding-left: 28px;
    margin: 8px 0;
  }
  .rendered-html :global(li) {
    margin-bottom: 4px;
  }
  .rendered-html :global(.md-h1),
  .rendered-html :global(.md-h2),
  .rendered-html :global(.md-h3) {
    color: var(--text-main);
    font-weight: 700;
    margin: 12px 0 6px;
    line-height: 1.4;
  }
  .rendered-html :global(.md-h1) { font-size: 18px; }
  .rendered-html :global(.md-h2) { font-size: 16px; }
  .rendered-html :global(.md-h3) { font-size: 14.5px; }
  .rendered-html :global(.md-hr) {
    border: none;
    border-top: 1px solid rgba(255, 255, 255, 0.12);
    margin: 12px 0;
  }
  .rendered-html :global(.inline-md-code) {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    padding: 1px 6px;
    border-radius: 5px;
    font-size: 12.5px;
  }
  .rendered-html :global(.md-toc-row) {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 3px 0;
  }
  .rendered-html :global(.md-toc-title) {
    color: var(--text-main);
    flex-shrink: 0;
    max-width: 78%;
  }
  .rendered-html :global(.md-toc-dots) {
    flex: 1;
    border-bottom: 1px dotted rgba(255, 255, 255, 0.28);
    min-width: 24px;
  }
  .rendered-html :global(.md-toc-page) {
    color: var(--primary-soft-text);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  /* ── Preview View ── */
  .content-scroll.is-preview {
    padding: 0;
    background: var(--bg2);
  }
  .preview-container {
    display: flex;
    justify-content: center;
    padding: 20px;
    min-height: 100%;
  }
  .mode-transition-stage {
    animation: stageReveal 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes stageReveal {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  .page-wrap {
    position: relative;
    box-shadow: 0 12px 34px rgba(0, 0, 0, 0.38);
    background: white;
    line-height: 0;
    border-radius: 6px;
  }
  .page-wrap.zoom-100 {
    max-width: 880px;
  }
  .page-img {
    max-width: 100%;
    height: auto;
    display: block;
    border-radius: 6px;
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
    padding: 0;
    margin: 0;
    border: 1.5px solid transparent;
    border-radius: 3px;
    mix-blend-mode: multiply;
    opacity: 0.78;
    transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    cursor: pointer;
    animation: boxPopIn 0.32s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes boxPopIn {
    from {
      opacity: 0;
      transform: scale(0.92);
    }
    to {
      opacity: 0.78;
      transform: scale(1);
    }
  }
  .error-box.th {
    background: rgba(244, 63, 94, 0.32);
    border-color: #f43f5e;
  }
  .error-box.en {
    background: rgba(245, 158, 11, 0.32);
    border-color: #f59e0b;
  }
  .error-box.sm {
    background: rgba(168, 85, 247, 0.32);
    border-color: #a855f7;
  }
  .error-box.fmt {
    background: rgba(56, 189, 248, 0.3);
    border: 1.5px dashed #0284c7;
  }
  .error-box:hover,
  .error-box:focus-visible,
  .error-box.is-linked {
    opacity: 1;
    mix-blend-mode: normal;
    z-index: 20;
    transform: scale(1.06);
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.35), 0 6px 18px rgba(0, 0, 0, 0.35);
    outline: none;
  }
  .error-box-tooltip {
    position: absolute;
    bottom: calc(100% + 6px);
    left: 50%;
    transform: translateX(-50%) translateY(4px);
    background: rgba(15, 18, 30, 0.96);
    border: 1px solid rgba(168, 85, 247, 0.48);
    color: #f8fafc;
    font-family: var(--font-th);
    font-size: 11.5px;
    line-height: 1.35;
    padding: 4px 9px;
    border-radius: 7px;
    white-space: nowrap;
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.45);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.18s ease, transform 0.18s cubic-bezier(0.16, 1, 0.3, 1);
    z-index: 30;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .error-box:hover .error-box-tooltip,
  .error-box:focus-visible .error-box-tooltip,
  .error-box.is-linked .error-box-tooltip {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
  .eb-arrow {
    color: var(--text-muted);
  }
  .eb-sugg {
    color: var(--success-soft-text);
    font-weight: 600;
  }
  .eb-msg {
    color: #cbd5e1;
  }

  /* ── Manual Spellcheck ── */
  .manual-check-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    gap: 16px;
    color: var(--text-muted);
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
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: white;
    border: none;
    border-radius: var(--radius-md);
    font-size: 14px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  .btn-check:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.45);
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
    inset: 0;
    background: rgba(5, 7, 15, 0.76);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal, 10000);
    padding: 20px;
    animation: modalBackdropIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes modalBackdropIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  .modal-content {
    position: relative;
    background: linear-gradient(165deg, rgba(24, 27, 44, 0.96) 0%, rgba(15, 17, 29, 0.98) 100%);
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: 20px;
    padding: 24px 26px 22px;
    width: 540px;
    max-width: 94vw;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.68), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    animation: modalCardRise 0.32s cubic-bezier(0.16, 1, 0.3, 1);
    overflow: visible;
  }
  @keyframes modalCardRise {
    from {
      opacity: 0;
      transform: translateY(14px) scale(0.97);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  .modal-top-accent {
    position: absolute;
    top: 0;
    left: 24px;
    right: 24px;
    height: 2px;
    border-radius: 0 0 4px 4px;
    background: linear-gradient(90deg, transparent, var(--primary), var(--secondary), var(--accent), transparent);
    opacity: 0.85;
  }
  .modal-header-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 18px;
  }
  .modal-title-block {
    display: flex;
    align-items: center;
    gap: 13px;
    min-width: 0;
  }
  .modal-icon-badge {
    position: relative;
    width: 42px;
    height: 42px;
    border-radius: 13px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.22), rgba(168, 85, 247, 0.24));
    border: 1px solid rgba(168, 85, 247, 0.42);
    color: #e9d5ff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.22);
  }
  .modal-icon-ring {
    position: absolute;
    inset: -4px;
    border-radius: 16px;
    border: 1px solid rgba(168, 85, 247, 0.35);
    animation: modalIconPulse 2.8s ease-in-out infinite;
    pointer-events: none;
  }
  @keyframes modalIconPulse {
    0%, 100% { transform: scale(1); opacity: 0.55; }
    50% { transform: scale(1.06); opacity: 0.15; }
  }
  .modal-title-texts {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }
  .modal-content h3 {
    margin: 0;
    font-size: 17px;
    font-weight: 700;
    color: var(--text-main);
    letter-spacing: -0.01em;
  }
  .modal-subtitle {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.4;
  }
  .btn-modal-close {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
    width: 30px;
    height: 30px;
    border-radius: 9px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background-color 0.2s ease, color 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.2s ease;
  }
  .btn-modal-close:hover:not(:disabled) {
    background: rgba(244, 63, 94, 0.14);
    border-color: rgba(244, 63, 94, 0.38);
    color: #fda4af;
    transform: rotate(90deg);
  }
  .btn-modal-close:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  /* Document Telemetry Summary Strip */
  .save-doc-meta-strip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 14px;
    margin-bottom: 18px;
    border-radius: 12px;
    background: rgba(10, 12, 22, 0.58);
    border: 1px solid rgba(255, 255, 255, 0.07);
  }
  .sdm-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .sdm-lbl {
    font-size: 10.5px;
    color: var(--text-dim);
  }
  .sdm-val {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-main);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .sdm-val.badge-type {
    display: inline-block;
    width: fit-content;
    font-family: var(--font-en);
    font-size: 10.5px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 5px;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.38);
    color: #c7d2fe;
  }
  .sdm-val.accent {
    color: var(--success-soft-text);
  }
  .sdm-divider {
    width: 1px;
    height: 24px;
    background: rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
  }

  .modal-form-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .form-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .form-group {
    margin-bottom: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .form-group label, .label-text {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12.5px;
    color: var(--text-muted);
    font-weight: 500;
  }
  .form-group label svg {
    color: var(--primary-soft-text);
    opacity: 0.85;
  }
  .input-icon-wrap {
    position: relative;
    display: flex;
  }
  .form-input {
    width: 100%;
    box-sizing: border-box;
    background: rgba(8, 10, 18, 0.55);
    border: 1px solid var(--glass-border-light);
    color: var(--text-main);
    padding: 10px 13px;
    border-radius: 11px;
    font-family: inherit;
    font-size: 13.5px;
    outline: none;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
  }
  .form-input:hover:not(:disabled) {
    border-color: rgba(168, 85, 247, 0.38);
  }
  .form-input:focus {
    background: rgba(8, 10, 18, 0.8);
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22);
  }
  .toggle-group {
    margin: 2px 0 0;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border);
    padding: 13px 15px;
    border-radius: 13px;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    transition: background-color 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
  }
  .toggle-group.is-golden {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(168, 85, 247, 0.08));
    border-color: rgba(245, 158, 11, 0.42);
    box-shadow: 0 6px 20px rgba(245, 158, 11, 0.12);
  }
  .golden-info {
    display: flex;
    align-items: center;
    gap: 11px;
    min-width: 0;
  }
  .golden-icon-box {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background-color 0.25s ease, border-color 0.25s ease, color 0.25s ease, transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .toggle-group.is-golden .golden-icon-box {
    background: rgba(245, 158, 11, 0.18);
    border-color: rgba(245, 158, 11, 0.45);
    color: #fbbf24;
    transform: scale(1.06) rotate(-8deg);
  }
  .golden-texts {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .toggle-group .label-text {
    color: var(--text-main);
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
  }
  .golden-desc {
    font-size: 11.5px;
    color: var(--text-muted);
    line-height: 1.35;
  }
  .toggle-wrap { position: relative; display: inline-flex; align-items: center; cursor: pointer; flex-shrink: 0; }
  .toggle-wrap input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  .toggle-track {
    width: 44px;
    height: 24px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.16);
    position: relative;
    transition: background-color 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
  }
  .toggle-wrap input:focus-visible + .toggle-track {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: linear-gradient(135deg, #f59e0b, #a855f7);
    border-color: rgba(251, 191, 36, 0.6);
    box-shadow: 0 0 12px rgba(245, 158, 11, 0.38);
  }
  .toggle-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #ffffff;
    position: absolute;
    top: 2px;
    left: 2px;
    transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb {
    transform: translateX(20px);
    background: #ffffff;
  }

  /* Animated Ingestion Progress Banner */
  .saving-progress-banner {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 11px 13px;
    border-radius: 11px;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.32);
    animation: stageReveal 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .spb-bar {
    height: 4px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
    position: relative;
  }
  .spb-shimmer {
    position: absolute;
    inset: 0;
    width: 45%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--primary), var(--secondary), var(--accent));
    animation: saveIndeterminate 1.4s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }
  @keyframes saveIndeterminate {
    0% { transform: translateX(-110%); }
    100% { transform: translateX(240%); }
  }
  .spb-text {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #e0e7ff;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 22px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
  }
  .btn-cancel {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border-light);
    color: var(--text-muted);
    padding: 9px 18px;
    border-radius: 11px;
    cursor: pointer;
    font-family: inherit;
    font-size: 13.5px;
    font-weight: 500;
    transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
  }
  .btn-cancel:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.22);
    color: var(--text-main);
  }
  .btn-save {
    position: relative;
    overflow: hidden;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: white;
    padding: 9px 20px;
    border-radius: 11px;
    cursor: pointer;
    font-family: inherit;
    font-size: 13.5px;
    font-weight: 600;
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.35);
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease, filter 0.2s ease;
  }
  .btn-save::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(110deg, transparent 25%, rgba(255, 255, 255, 0.24) 50%, transparent 75%);
    transform: translateX(-120%);
    transition: transform 0.55s cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: none;
  }
  .btn-save:hover:not(:disabled) {
    transform: translateY(-1.5px);
    box-shadow: 0 10px 24px rgba(168, 85, 247, 0.45);
    filter: brightness(1.06);
  }
  .btn-save:hover:not(:disabled)::after {
    transform: translateX(120%);
  }
  .btn-save:active:not(:disabled) {
    transform: translateY(0);
  }
  .btn-save:disabled {
    opacity: 0.48;
    cursor: not-allowed;
    box-shadow: none;
  }
  .save-spinner {
    display: inline-block;
    width: 13px;
    height: 13px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: spin-save 0.7s linear infinite;
    flex-shrink: 0;
  }
  @keyframes spin-save { to { transform: rotate(360deg); } }

  @media (max-width: 560px) {
    .form-grid-2 {
      grid-template-columns: 1fr;
    }
    .save-doc-meta-strip {
      flex-wrap: wrap;
      gap: 10px 14px;
    }
    .sdm-divider {
      display: none;
    }
  }
</style>
