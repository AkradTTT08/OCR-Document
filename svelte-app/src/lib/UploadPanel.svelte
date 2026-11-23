<script>
  import { createEventDispatcher } from 'svelte';
  import DictStats from './DictStats.svelte';
  import FormatRules from './FormatRules.svelte';
  import { toast } from './toastStore.js';
  import CustomSelect from './CustomSelect.svelte';
  const dispatch = createEventDispatcher();

  const langOptions = [
    { value: 'tha+eng', label: 'ไทย + อังกฤษ (TH / EN)', icon: '🌐' },
    { value: 'tha', label: 'ภาษาไทยเท่านั้น (TH)', icon: 'ก' },
    { value: 'eng', label: 'ภาษาอังกฤษเท่านั้น (EN)', icon: 'A' }
  ];

  const dpiOptions = [
    { value: '200', label: '200 DPI (สแกนเร็ว)', icon: '⚡' },
    { value: '300', label: '300 DPI (แนะนำ • คมชัดสูง)', icon: '⭐' },
    { value: '400', label: '400 DPI (ละเอียดพิเศษ)', icon: '🔍' }
  ];

  const API = '/api';

  // ── State ──
  /** @type {any} */
  let file = null;
  let isDragging = false;
  let lang = 'tha+eng';
  let dpi = '300';
  let autoSpellCheck = true;
  let pageRangeMode = 'all'; // 'all' | 'custom'
  let startPage = 1;
  let endPage = 30;
  let detectedPageCount = 0;
  /** @type {AbortController | null} */
  let abortController = null;
  /** @type {'partial' | 'cancel' | null} */
  let abortReason = null;
  /** @type {any[]} */
  let activeStreamPages = [];

  export function cancelProcessing(keepPartial = false) {
    if (!abortController) return;
    abortReason = keepPartial ? 'partial' : 'cancel';
    abortController.abort();
  }

  $: activeLangLabel = langOptions.find(o => o.value === lang)?.label || 'ไทย + อังกฤษ';
  $: targetPageCount = (() => {
    if (!detectedPageCount) return 0;
    if (pageRangeMode === 'all') return detectedPageCount;
    const s = Math.max(1, parseInt(String(startPage), 10) || 1);
    const e = Math.min(detectedPageCount, Math.max(s, parseInt(String(endPage), 10) || s));
    return Math.max(1, e - s + 1);
  })();
  $: estimatedTimeText = (() => {
    const pages = targetPageCount || 1;
    const secPerPage = autoSpellCheck ? 4.5 : 2.8;
    const totalSec = Math.max(4, Math.round(pages * secPerPage));
    if (totalSec < 60) return `~${totalSec} วินาที`;
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return secs > 0 ? `~${mins} นาที ${secs} วินาที` : `~${mins} นาที`;
  })();

  // ── File ──
  /** @param {any} e */
  function onDrop(e) {
    e.preventDefault();
    isDragging = false;
    const f = e.dataTransfer?.files?.[0];
    if (f) setFile(f);
  }
  /** @param {any} e */
  function onFileChange(e) {
    const f = e.target?.files?.[0];
    if (f) setFile(f);
  }

  async function detectPdfPagesClientSide(f) {
    try {
      const buf = await f.arrayBuffer();
      const bytes = new Uint8Array(buf);
      // Verify %PDF- header
      const header = new TextDecoder('ascii').decode(bytes.slice(0, 1024));
      if (!header.includes('%PDF-')) {
        toast('ไฟล์ที่เลือกไม่ใช่โครงสร้างเอกสาร PDF ที่ถูกต้อง', 'error');
        file = null;
        detectedPageCount = 0;
        return;
      }
      const text = new TextDecoder('latin1').decode(bytes);
      const matches = text.match(/\/Type\s*\/Page\b(?!s)/g);
      const count = matches ? matches.length : 1;
      detectedPageCount = Math.max(1, count);
      startPage = 1;
      endPage = detectedPageCount > 50 ? 30 : detectedPageCount;
    } catch {
      detectedPageCount = 0;
    }
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
    detectedPageCount = 0;
    detectPdfPagesClientSide(f);
    toast(`โหลดไฟล์ "${f.name}" สำเร็จ`, 'success', 2500);
  }

  function removeFile() {
    file = null;
    detectedPageCount = 0;
  }

  function selectRangePreset(mode, s = 1, e = 30) {
    pageRangeMode = mode;
    if (mode === 'custom') {
      startPage = s;
      endPage = detectedPageCount ? Math.min(detectedPageCount, e) : e;
    }
  }

  /** @param {number} b */
  function formatBytes(b) {
    if (b < 1024) return `${b} B`;
    if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / 1048576).toFixed(2)} MB`;
  }

  // ── Process ──
  async function process() {
    if (!file) return;

    abortController = new AbortController();
    abortReason = null;
    activeStreamPages = [];

    const initialTotal = targetPageCount || detectedPageCount || 1;
    const baseMeta = () => ({
      filename: file?.name || 'document.pdf',
      fileSize: file ? formatBytes(file.size) : '',
      langLabel: activeLangLabel,
      dpi,
      autoSpellCheck,
    });

    /**
     * @param {number} pct
     * @param {string} label
     * @param {number} step
     * @param {Record<string, any>} [extra]
     */
    const emitProgress = (pct, label, step, extra = {}) =>
      dispatch('processing', {
        active: true,
        progress: {
          pct,
          label,
          step,
          ...baseMeta(),
          completedPages: activeStreamPages.length,
          totalPages: initialTotal,
          totalDocPages: detectedPageCount || initialTotal,
          elapsedSec: 0,
          etaText: estimatedTimeText,
          avgSecPerPage: null,
          latestPageNum: null,
          latestPageSnippet: '',
          latestPageErrors: null,
          ...extra,
        },
      });

    const formData = new FormData();
    formData.append('file', file);

    let url = `${API}/process_stream?lang=${lang}&dpi=${dpi}&auto_spellcheck=${autoSpellCheck}`;
    if (pageRangeMode === 'custom') {
      const s = Math.max(1, parseInt(String(startPage), 10) || 1);
      const e = Math.max(s, parseInt(String(endPage), 10) || s);
      url += `&start_page=${s}&end_page=${e}`;
    }

    let latestTotal = initialTotal;
    let latestDocTotal = detectedPageCount || initialTotal;
    let latestElapsed = 0;
    let latestEtaText = estimatedTimeText;
    let latestAvgSec = null;
    let latestSnippet = '';
    let latestPageNum = null;
    let latestPageErrors = null;

    try {
      emitProgress(5, 'เริ่มต้นเชื่อมต่อระบบ Multimodal OCR...', 1);

      const res = await fetch(url, {
        method: 'POST',
        body: formData,
        signal: abortController.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `HTTP Error: ${res.status}`);
      }

      if (!res.body) {
        throw new Error('ไม่สามารถเชื่อมต่อข้อมูลสตรีมแบบเรียลไทม์ได้ (Response body is null)');
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let pages = [];
      let finalData = null;

      const handleEventLine = (line) => {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith(':')) return;

        if (trimmed.startsWith('data: ')) {
          const jsonStr = trimmed.substring(6).trim();
          if (!jsonStr) return;

          let data;
          try {
            data = JSON.parse(jsonStr);
          } catch (pe) {
            console.warn('SSE Chunk JSON Parse Error:', pe, jsonStr);
            return;
          }

          if (data.type === 'start') {
            emitProgress(10, 'แปลงเอกสาร PDF เป็นภาพความละเอียดสูง...', 1);
          } else if (data.type === 'progress') {
            const currentProcessingPage = data.page || 0;
            const total = data.total || initialTotal;
            const elapsed = data.elapsed || 0;
            const totalDocPages = data.total_doc_pages || total;

            latestTotal = total;
            latestDocTotal = totalDocPages;
            latestElapsed = Math.round(elapsed);

            let pct = 10;
            let label = 'กำลังสกัดหน้าเอกสาร...';

            if (total > 0) {
              const finishedSoFar = activeStreamPages.length;
              pct = 10 + Math.floor(((finishedSoFar + 0.35) / total) * 78);
              pct = Math.min(92, Math.max(10, pct));

              if (finishedSoFar > 0 && elapsed > 0) {
                const timePerPage = elapsed / finishedSoFar;
                latestAvgSec = timePerPage.toFixed(1);
                const remaining = Math.max(0, total - finishedSoFar);
                const etaSeconds = Math.round(timePerPage * remaining);

                let etaText = '';
                if (etaSeconds <= 3) {
                  etaText = 'ไม่กี่วินาที';
                } else if (etaSeconds < 60) {
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
                latestEtaText = etaText;
                label = `กำลังสกัดและตรวจคำผิดหน้าที่ ${currentProcessingPage}/${total} ${totalDocPages > total ? `(จากทั้งหมด ${totalDocPages} หน้า)` : ''}`;
              } else {
                label = `กำลังสกัดข้อความหน้าที่ ${Math.max(1, currentProcessingPage)}/${total} ด้วย Gemini 2.5 Flash...`;
              }
            } else {
              label = `กำลังเตรียมเอนจิน OCR & ตรวจคำผิด 3 ชั้น...`;
            }

            emitProgress(pct, label, autoSpellCheck && activeStreamPages.length > 0 ? 3 : 2, {
              completedPages: activeStreamPages.length,
              totalPages: latestTotal,
              totalDocPages: latestDocTotal,
              elapsedSec: latestElapsed,
              etaText: latestEtaText,
              avgSecPerPage: latestAvgSec,
              latestPageNum,
              latestPageSnippet: latestSnippet,
              latestPageErrors,
            });
          } else if (data.type === 'page_result' && data.page) {
            pages.push(data.page);
            activeStreamPages = [...pages];
            latestPageNum = data.page.page_number;
            latestSnippet = String(data.page.text || '')
              .replace(/[#*|>`~_-]+/g, ' ')
              .replace(/\s+/g, ' ')
              .trim()
              .slice(0, 140);
            latestPageErrors = data.page.spell_check?.errors?.length ?? null;
            const donePct = latestTotal > 0 ? Math.min(96, 12 + Math.floor((pages.length / latestTotal) * 84)) : 50;
            emitProgress(
              donePct,
              `สกัดเสร็จแล้ว ${pages.length}/${latestTotal} หน้า • ล่าสุดหน้า ${latestPageNum}`,
              autoSpellCheck ? 3 : 2,
              {
                completedPages: pages.length,
                totalPages: latestTotal,
                totalDocPages: latestDocTotal,
                elapsedSec: latestElapsed,
                etaText: latestEtaText,
                avgSecPerPage: latestAvgSec,
                latestPageNum,
                latestPageSnippet: latestSnippet,
                latestPageErrors,
              }
            );
          } else if (data.type === 'complete') {
            finalData = data;
            finalData.pages = pages;
            finalData.filename = file.name;
            finalData.lang = lang;
            finalData.success = true;
            finalData.total_pages = data.total_pages || data.summary?.total_pages || pages.length;
          } else if (data.type === 'error') {
            console.error('Server OCR error:', data.message);
            toast(`แจ้งเตือน OCR: ${data.message}`, 'error', 6000);
          }
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          handleEventLine(line);
        }
      }

      if (buffer.trim()) {
        handleEventLine(buffer);
      }

      if (finalData) {
        emitProgress(100, 'ประมวลผลและตรวจสอบเอกสารเสร็จสมบูรณ์!', 4, {
          completedPages: pages.length,
          totalPages: pages.length,
          etaText: 'เสร็จสมบูรณ์',
        });
        await sleep(250);
        dispatch('result', finalData);
        dispatch('processing', { active: false, progress: { pct: 100, label: '', step: 4 } });
      } else if (pages.length > 0) {
        emitProgress(100, `เสร็จสิ้น (${pages.length} หน้า)`, 4);
        await sleep(250);
        dispatch('result', {
          pages,
          filename: file.name,
          lang,
          success: true,
          summary: { total_pages: pages.length },
          total_pages: pages.length
        });
        dispatch('processing', { active: false, progress: { pct: 100, label: '', step: 4 } });
        toast(`ประมวลผลเสร็จแล้ว ${pages.length} หน้า`, 'success', 5000);
      } else {
        throw new Error('ไม่พบข้อมูลผลลัพธ์จากการสแกน');
      }
    } catch (err) {
      if (err && (err.name === 'AbortError' || abortReason)) {
        if (abortReason === 'partial' && activeStreamPages.length > 0) {
          const partialPages = [...activeStreamPages];
          dispatch('result', {
            pages: partialPages,
            filename: file?.name || 'document.pdf',
            lang,
            success: true,
            summary: { total_pages: partialPages.length },
            total_pages: partialPages.length,
          });
          dispatch('processing', { active: false, progress: { pct: 100, label: '', step: 4 } });
          toast(`หยุดสแกนและแสดงผลลัพธ์ที่สกัดแล้ว ${partialPages.length} หน้า`, 'info', 4000);
        } else {
          dispatch('processing', { active: false, progress: { pct: 0, label: '', step: 0 } });
          toast('ยกเลิกการประมวลผล OCR แล้ว', 'info', 2500);
        }
        return;
      }
      dispatch('processing', { active: false, progress: { pct: 0, label: '', step: 0 } });
      const msg = err instanceof Error ? err.message : String(err);
      console.error('PROCESS ERROR:', err);
      toast(`ข้อผิดพลาด: ${msg}`, 'error', 6000);
    } finally {
      abortController = null;
      abortReason = null;
    }
  }

  /** @param {number} ms */
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
</script>

<!-- Layout Container -->
<div class="upload-container">
  <!-- Header Text -->
  <div class="header-section">
    <div class="header-ai-badge">
      <svg class="ai-badge-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true">
        <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z"></path>
      </svg>
      <span>3-Layer Hybrid OCR &amp; Linguistic Proofreader: <strong class="highlight-model">Gemini 2.5 Flash • PyThaiNLP • พจนานุกรมราชบัณฑิตฯ</strong></span>
    </div>
    <h1 class="main-title">ศูนย์สกัดข้อความและตรวจสอบคำผิดเอกสารอัจฉริยะ</h1>
    <p class="sub-title">
      แปลงเอกสาร PDF ตาราง และแผนผังเป็นข้อมูล Markdown โครงสร้างสูง พร้อมตรวจสอบคำสะกดผิด คำทับศัพท์ราชบัณฑิตยสภา 
      คำพ้องเสียงตามบริบท และไวยากรณ์ภาษาไทย–อังกฤษแบบ 3 ชั้น
    </p>
  </div>

  <!-- Main Grid -->
  <div class="content-grid">
    <!-- Left: Dropzone / Staged Document Studio -->
    <div class="left-col">
      <div
        class="upload-area"
        role={file ? "region" : "button"}
        tabindex={file ? undefined : 0}
        aria-label={file ? `ไฟล์ที่เลือก ${file.name}` : "อัปโหลดไฟล์ PDF คลิกหรือลากไฟล์มาวางที่นี่"}
        on:dragover|preventDefault={() => (isDragging = true)}
        on:dragleave={() => (isDragging = false)}
        on:drop={onDrop}
        on:click={() => !file && document.getElementById("fileInput")?.click()}
        on:keydown={(e) => {
          if (!file && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            document.getElementById("fileInput")?.click();
          }
        }}
        class:dragging={isDragging}
        class:has-file={!!file}
      >
        <input
          id="fileInput"
          type="file"
          accept=".pdf"
          hidden
          on:change={onFileChange}
        />

        <!-- Decorative Scanner Reticle Corners -->
        <span class="scan-corner tl" aria-hidden="true"></span>
        <span class="scan-corner tr" aria-hidden="true"></span>
        <span class="scan-corner bl" aria-hidden="true"></span>
        <span class="scan-corner br" aria-hidden="true"></span>

        {#if !file}
          <div class="drop-empty-content">
            <div class="drop-icon-box" class:bounce={isDragging}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="12" y1="18" x2="12" y2="12"></line>
                <polyline points="9 15 12 12 15 15"></polyline>
              </svg>
            </div>
            <p class="drop-title">ลากไฟล์ PDF มาวางที่นี่</p>
            <p class="drop-hint">
              หรือ <span class="link-text">คลิกเพื่อเลือกไฟล์จากเครื่อง</span> (รองรับไฟล์ขนาดสูงสุด 50 MB)
            </p>

            <div class="file-types">
              <span class="file-pill primary-pill">.PDF</span>
              <span class="file-pill">สกัดตาราง Markdown</span>
              <span class="file-pill">ตรวจคำผิด ไทย / EN</span>
              <span class="file-pill">เทียบภาพต้นฉบับ</span>
            </div>
          </div>

          <!-- 3-Step Workflow Footer inside Dropzone -->
          <div class="drop-workflow-strip" aria-hidden="true">
            <div class="wf-step">
              <span class="wf-num">1</span>
              <div class="wf-text">
                <strong>Multimodal OCR</strong>
                <span>สกัดข้อความ &amp; ตาราง</span>
              </div>
            </div>
            <span class="wf-arrow">→</span>
            <div class="wf-step">
              <span class="wf-num">2</span>
              <div class="wf-text">
                <strong>3-Layer Proofread</strong>
                <span>ราชบัณฑิตฯ + บริบท AI</span>
              </div>
            </div>
            <span class="wf-arrow">→</span>
            <div class="wf-step">
              <span class="wf-num">3</span>
              <div class="wf-text">
                <strong>1-Click Fix &amp; KB</strong>
                <span>แทนที่คำผิด &amp; บันทึก</span>
              </div>
            </div>
          </div>
        {:else}
          <!-- Staged Document Readiness Studio -->
          <div class="staged-doc-panel">
            <div class="staged-top-bar">
              <span class="staged-ready-pill">
                <span class="ready-dot"></span>
                พร้อมประมวลผลเอกสาร
              </span>
              <div class="file-actions">
                <button
                  type="button"
                  class="btn-change-file"
                  on:click|stopPropagation={() => document.getElementById("fileInput")?.click()}
                  title="เลือกไฟล์ PDF ใหม่"
                >เปลี่ยนไฟล์</button>
                <button
                  type="button"
                  class="btn-remove"
                  aria-label={`ลบไฟล์ ${file.name}`}
                  on:click|stopPropagation={removeFile}
                  title="นำไฟล์ออก">✕</button
                >
              </div>
            </div>

            <div class="file-card">
              <div class="file-icon-wrap">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" width="26" height="26">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </div>
              <div class="file-info">
                <span class="file-name truncate" title={file.name}>{file.name}</span>
                <span class="file-size">เอกสาร PDF • ตรวจสอบโครงสร้างไฟล์ผ่านแล้ว</span>
              </div>
            </div>

            <div class="staged-metrics-grid">
              <div class="staged-metric-box">
                <span class="sm-label">ขนาดไฟล์</span>
                <strong class="sm-val">{formatBytes(file.size)}</strong>
              </div>
              <div class="staged-metric-box">
                <span class="sm-label">จำนวนหน้าทั้งหมด</span>
                <strong class="sm-val">{detectedPageCount ? `${detectedPageCount} หน้า` : 'อัตโนมัติ'}</strong>
              </div>
              <div class="staged-metric-box">
                <span class="sm-label">เวลาประมวลผลคาดการณ์</span>
                <strong class="sm-val accent">{estimatedTimeText}</strong>
              </div>
            </div>

            {#if detectedPageCount > 5}
              <div class="staged-preset-row">
                <span class="preset-caption">เลือกช่วงหน้าด่วน:</span>
                <div class="preset-pills">
                  <button
                    type="button"
                    class="preset-pill"
                    class:active={pageRangeMode === 'all'}
                    on:click|stopPropagation={() => selectRangePreset('all')}
                  >ทุกหน้า ({detectedPageCount})</button>
                  <button
                    type="button"
                    class="preset-pill"
                    class:active={pageRangeMode === 'custom' && startPage === 1 && endPage === Math.min(5, detectedPageCount)}
                    on:click|stopPropagation={() => selectRangePreset('custom', 1, 5)}
                  >5 หน้าแรก (ทดสอบเร็ว)</button>
                  {#if detectedPageCount > 15}
                    <button
                      type="button"
                      class="preset-pill"
                      class:active={pageRangeMode === 'custom' && startPage === 1 && endPage === Math.min(30, detectedPageCount)}
                      on:click|stopPropagation={() => selectRangePreset('custom', 1, 30)}
                    >30 หน้าแรก</button>
                  {/if}
                </div>
              </div>
            {/if}

            <div class="staged-config-summary">
              <span class="cfg-chip">{activeLangLabel}</span>
              <span class="cfg-chip">{dpi} DPI</span>
              <span class="cfg-chip" class:highlight={autoSpellCheck}>
                {autoSpellCheck ? 'ตรวจคำผิด 3 ชั้น: เปิด' : 'เฉพาะ OCR (ข้ามตรวจคำ)'}
              </span>
              <span class="cfg-chip">
                {pageRangeMode === 'all' ? 'สแกนทุกหน้า' : `หน้า ${startPage} ถึง ${endPage}`}
              </span>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <!-- Right: Settings & Actions -->
    <div class="right-col">
      <div class="settings-card">
        <div class="settings-header-row">
          <h3 class="settings-title">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            ตั้งค่าการสแกน &amp; ตรวจคำผิด
          </h3>
          <span class="settings-sub-pill">OCR Studio</span>
        </div>

        <div class="settings-block">
          <div class="setting-grid-2col">
            <div class="setting-row">
              <label class="setting-label" for="sel-lang">ภาษาที่ต้องการตรวจ</label>
              <CustomSelect
                id="sel-lang"
                bind:value={lang}
                options={langOptions}
                minWidth="140px"
              />
            </div>
            <div class="setting-row">
              <label class="setting-label" for="sel-dpi">ความละเอียดภาพ (DPI)</label>
              <CustomSelect
                id="sel-dpi"
                bind:value={dpi}
                options={dpiOptions}
                minWidth="140px"
              />
            </div>
          </div>

          <div class="setting-row toggle-row">
            <div class="toggle-text">
              <label class="setting-label" for="auto-spellcheck-toggle">โหมดตรวจคำผิดอัตโนมัติ (3-Layer Proofread)</label>
              <span class="setting-hint">ตรวจคำสะกดผิดราชบัณฑิตฯ คำทับศัพท์ คำพ้องเสียง และไวยากรณ์</span>
            </div>
            <label class="toggle-wrap" for="auto-spellcheck-toggle">
              <input id="auto-spellcheck-toggle" type="checkbox" bind:checked={autoSpellCheck} />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </label>
          </div>

          <!-- Page Range Selection -->
          <div class="setting-row range-row">
            <div class="range-header-row">
              <span class="setting-label">ช่วงหน้าที่ต้องการสแกน</span>
              <div class="range-mode-toggle" role="group" aria-label="เลือกช่วงหน้าที่ต้องการสแกน">
                <button type="button" class="mode-pill-btn" class:active={pageRangeMode === 'all'} on:click={() => (pageRangeMode = 'all')}>ทั้งหมด</button>
                <button type="button" class="mode-pill-btn" class:active={pageRangeMode === 'custom'} on:click={() => (pageRangeMode = 'custom')}>กำหนดช่วง</button>
              </div>
            </div>
            {#if pageRangeMode === 'custom'}
              <div class="range-inputs-wrap">
                <label class="range-input-group">
                  <span>เริ่มหน้า</span>
                  <input type="number" min="1" max={detectedPageCount || 9999} bind:value={startPage} class="range-number-input" aria-label="เริ่มหน้า" />
                </label>
                <span class="range-sep">ถึง</span>
                <label class="range-input-group">
                  <span>ถึงหน้า</span>
                  <input type="number" min="1" max={detectedPageCount || 9999} bind:value={endPage} class="range-number-input" aria-label="ถึงหน้า" />
                </label>
              </div>
              <div class="range-tip">
                แนะนำสำหรับเอกสารหนา (เช่น 100+ หน้า): แบ่งสแกนรอบละ 30–50 หน้า เพื่อความรวดเร็วและเสถียรสูงสุด
              </div>
            {/if}
          </div>

          <!-- 3-Layer AI Engine Architecture Card -->
          <div class="ai-engine-info">
            <div class="ai-engine-header">
              <div class="ai-indicator-wrap">
                <span class="ai-online-dot"></span>
                <span class="ai-engine-title">สถาปัตยกรรม AI ที่ใช้งาน</span>
              </div>
              <span class="ai-model-badge">3-Layer Hybrid</span>
            </div>
            <div class="ai-model-details">
              <div class="model-spec-row">
                <span class="spec-label">Vision OCR:</span>
                <span class="spec-val">Google Gemini 2.5 Flash (Multimodal)</span>
              </div>
              <div class="model-spec-row">
                <span class="spec-label">ตรวจคำไทย:</span>
                <span class="spec-val">PyThaiNLP (newmm) + คลังคำราชบัณฑิตฯ</span>
              </div>
              <div class="model-spec-row">
                <span class="spec-label">ตรวจ EN &amp; บริบท:</span>
                <span class="spec-val">SpellChecker + Gemini 2.5 Context AI</span>
              </div>
            </div>
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
            {#if autoSpellCheck}
              <span>ประมวลผล OCR + ตรวจคำผิด (3-Layer AI)</span>
            {:else}
              <span>ประมวลผลสกัดข้อความ OCR</span>
            {/if}
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
    gap: 22px;
    align-items: center;
    justify-content: center;
    max-width: 1120px;
    margin: auto;
    width: 100%;
    min-height: 100%;
    padding: 24px 24px 28px;
  }

  /* ── Header ── */
  .header-section {
    text-align: center;
    max-width: 780px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .header-ai-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 15px;
    margin-bottom: 12px;
    background: rgba(168, 85, 247, 0.12);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 999px;
    font-size: 12.5px;
    color: #e9d5ff;
    backdrop-filter: blur(8px);
    box-shadow: 0 2px 10px rgba(168, 85, 247, 0.15);
  }
  .ai-badge-icon {
    color: #c084fc;
    flex-shrink: 0;
  }
  .highlight-model {
    color: #ffffff;
    font-weight: 600;
  }
  .main-title {
    font-size: clamp(22px, 2.2vw, 30px);
    font-weight: 700;
    color: var(--text-main);
    margin-bottom: 8px;
    font-family: var(--font-th);
    letter-spacing: -0.02em;
  }
  .sub-title {
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.65;
    font-family: var(--font-th);
    max-width: 64ch;
  }

  /* ── Content Grid ── */
  .content-grid {
    display: grid;
    grid-template-columns: 1.15fr 1fr;
    gap: 24px;
    width: 100%;
    align-items: stretch;
  }

  .left-col {
    display: flex;
    flex-direction: column;
  }

  /* ── Upload area (Dark Obsidian Glassmorphism Studio) ── */
  .upload-area {
    background:
      radial-gradient(circle at 50% 30%, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.06) 45%, transparent 72%),
      linear-gradient(160deg, rgba(23, 27, 44, 0.84) 0%, rgba(13, 15, 25, 0.92) 100%);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1.5px dashed rgba(168, 85, 247, 0.38);
    border-radius: 24px;
    padding: 32px 28px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.25s ease, background-color 0.25s ease, transform 0.25s ease, box-shadow 0.25s ease;
    flex: 1;
    min-height: 390px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  }

  .upload-area:hover:not(.has-file),
  .upload-area.dragging {
    border-color: rgba(168, 85, 247, 0.78);
    background:
      radial-gradient(circle at 50% 30%, rgba(99, 102, 241, 0.22) 0%, rgba(168, 85, 247, 0.1) 48%, transparent 75%),
      linear-gradient(160deg, rgba(28, 33, 54, 0.92) 0%, rgba(16, 19, 32, 0.96) 100%);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45), 0 0 24px rgba(168, 85, 247, 0.18);
    transform: translateY(-2px);
  }

  .upload-area.has-file {
    border: 1px solid rgba(168, 85, 247, 0.35);
    padding: 26px;
    cursor: default;
    justify-content: center;
  }

  /* Scanner Reticle Corners */
  .scan-corner {
    position: absolute;
    width: 16px;
    height: 16px;
    border-color: rgba(168, 85, 247, 0.45);
    border-style: solid;
    pointer-events: none;
    transition: border-color 0.25s ease;
  }
  .upload-area:hover:not(.has-file) .scan-corner {
    border-color: rgba(192, 132, 252, 0.85);
  }
  .scan-corner.tl { top: 16px; left: 16px; border-width: 2px 0 0 2px; border-top-left-radius: 6px; }
  .scan-corner.tr { top: 16px; right: 16px; border-width: 2px 2px 0 0; border-top-right-radius: 6px; }
  .scan-corner.bl { bottom: 16px; left: 16px; border-width: 0 0 2px 2px; border-bottom-left-radius: 6px; }
  .scan-corner.br { bottom: 16px; right: 16px; border-width: 0 2px 2px 0; border-bottom-right-radius: 6px; }

  .drop-empty-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin: auto 0;
  }

  .drop-icon-box {
    width: 82px;
    height: 82px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(168, 85, 247, 0.2));
    border: 1px solid rgba(168, 85, 247, 0.42);
    border-radius: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #c4b5fd;
    margin-bottom: 4px;
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.24), inset 0 1px 1px rgba(255, 255, 255, 0.14);
    transition: transform 0.3s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.25s ease, color 0.25s ease;
  }
  .upload-area:hover:not(.has-file) .drop-icon-box {
    color: #ffffff;
    border-color: rgba(168, 85, 247, 0.72);
    transform: translateY(-3px);
  }
  .drop-icon-box svg {
    width: 34px;
    height: 34px;
  }
  .drop-icon-box.bounce {
    transform: translateY(-8px) scale(1.06);
  }

  .drop-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-main);
    margin: 0;
    font-family: var(--font-th);
  }
  .drop-hint {
    font-size: 13.5px;
    color: var(--text-muted);
    margin: 0 0 4px;
    font-family: var(--font-th);
  }
  .link-text {
    color: var(--primary-soft-text);
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .upload-area:hover:not(.has-file) .link-text {
    color: var(--primary-soft-text-hover);
  }

  .file-types {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
  }
  .file-pill {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-muted);
    padding: 4px 11px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 500;
  }
  .file-pill.primary-pill {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.38);
    color: #c7d2fe;
    font-weight: 600;
    font-family: var(--font-en);
  }

  /* 3-Step Workflow Footer inside Dropzone */
  .drop-workflow-strip {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 12px 14px;
    background: rgba(10, 12, 20, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    text-align: left;
  }
  .wf-step {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .wf-num {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(168, 85, 247, 0.18);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #e9d5ff;
    font-family: var(--font-en);
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .wf-text {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
    min-width: 0;
  }
  .wf-text strong {
    font-size: 11.5px;
    color: var(--text-main);
    font-family: var(--font-en);
    white-space: nowrap;
  }
  .wf-text span {
    font-size: 10.5px;
    color: var(--text-muted);
    white-space: nowrap;
  }
  .wf-arrow {
    color: var(--text-dim);
    font-size: 13px;
    flex-shrink: 0;
  }

  /* ── Staged Document Readiness Panel ── */
  .staged-doc-panel {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 16px;
    text-align: left;
  }
  .staged-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .staged-ready-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 4px 12px;
    border-radius: 999px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.32);
    color: var(--success-soft-text);
    font-size: 12px;
    font-weight: 600;
  }
  .ready-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
  }

  .file-card {
    display: flex;
    align-items: center;
    gap: 14px;
    background: rgba(18, 21, 34, 0.92);
    padding: 16px 18px;
    border-radius: 16px;
    border: 1px solid rgba(168, 85, 247, 0.32);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    width: 100%;
  }
  .file-icon-wrap {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
  }
  .file-info {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    gap: 3px;
  }
  .file-name {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-main);
  }
  .file-size {
    font-size: 12px;
    color: var(--text-muted);
  }
  .file-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .btn-change-file {
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: var(--primary-soft-text);
    padding: 6px 12px;
    border-radius: 8px;
    font-family: var(--font-th);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.2s ease, color 0.2s ease;
  }
  .btn-change-file:hover {
    background: rgba(99, 102, 241, 0.26);
    color: #ffffff;
  }
  .btn-remove {
    background: rgba(244, 63, 94, 0.12);
    color: var(--danger-soft-text);
    border: 1px solid rgba(244, 63, 94, 0.25);
    width: 30px;
    height: 30px;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.2s ease, color 0.2s ease;
  }
  .btn-remove:hover {
    background: var(--danger-solid);
    color: white;
  }

  .staged-metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
  .staged-metric-box {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .sm-label {
    font-size: 11px;
    color: var(--text-muted);
  }
  .sm-val {
    font-size: 14.5px;
    font-weight: 700;
    color: var(--text-main);
    font-variant-numeric: tabular-nums;
  }
  .sm-val.accent {
    color: var(--primary-soft-text);
  }

  .staged-preset-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid rgba(255, 255, 255, 0.06);
    padding: 8px 12px;
    border-radius: 12px;
  }
  .preset-caption {
    font-size: 11.5px;
    color: var(--text-muted);
    font-weight: 500;
  }
  .preset-pills {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .preset-pill {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-muted);
    font-family: var(--font-th);
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .preset-pill:hover {
    color: var(--text-main);
    border-color: rgba(168, 85, 247, 0.4);
  }
  .preset-pill.active {
    background: rgba(168, 85, 247, 0.2);
    border-color: rgba(168, 85, 247, 0.55);
    color: #ffffff;
    font-weight: 600;
  }

  .staged-config-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .cfg-chip {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
    font-size: 11.5px;
    padding: 3px 10px;
    border-radius: 8px;
  }
  .cfg-chip.highlight {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.35);
    color: var(--primary-soft-text);
    font-weight: 500;
  }

  /* ── Right Column: Settings Card ── */
  .right-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .settings-card {
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: 24px;
    padding: 24px 26px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
    flex: 1;
  }
  .settings-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 18px;
  }
  .settings-title {
    display: flex;
    align-items: center;
    gap: 9px;
    font-size: 16.5px;
    font-weight: 700;
    color: var(--text-main);
    margin: 0;
    font-family: var(--font-th);
  }
  .settings-title svg {
    color: #818cf8;
    flex-shrink: 0;
  }
  .settings-sub-pill {
    font-family: var(--font-en);
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 2px 9px;
    border-radius: 999px;
  }

  .settings-block {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 20px;
  }
  .setting-grid-2col {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .setting-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .range-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  .range-header-row {
    display: flex;
    justify-content: space-between;
    width: 100%;
    align-items: center;
  }
  .toggle-row {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    background: rgba(255, 255, 255, 0.03);
    padding: 11px 14px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }
  .toggle-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .setting-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-main);
    font-family: var(--font-th);
    cursor: pointer;
  }
  .setting-hint {
    font-size: 11.5px;
    color: var(--text-muted);
    font-family: var(--font-th);
  }

  /* Accessible Toggle Switch */
  .toggle-wrap {
    position: relative;
    display: inline-flex;
    align-items: center;
    cursor: pointer;
    flex-shrink: 0;
  }
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
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.14);
    position: relative;
    transition: background-color 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
  }
  .toggle-wrap input:focus-visible + .toggle-track {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border-color: rgba(168, 85, 247, 0.6);
    box-shadow: 0 0 12px rgba(168, 85, 247, 0.35);
  }
  .toggle-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #cbd5e1;
    position: absolute;
    top: 2px;
    left: 2px;
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.25s ease;
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb {
    transform: translateX(20px);
    background: #ffffff;
  }

  /* ── AI Engine Info Card ── */
  .ai-engine-info {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.08), rgba(99, 102, 241, 0.05));
    border: 1px solid rgba(168, 85, 247, 0.25);
    border-radius: 14px;
    padding: 12px 15px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    backdrop-filter: blur(8px);
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
  }
  .ai-engine-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .ai-indicator-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .ai-online-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
  }
  .ai-engine-title {
    font-size: 12.5px;
    font-weight: 600;
    color: #e2e8f0;
    font-family: var(--font-th);
  }
  .ai-model-badge {
    background: rgba(168, 85, 247, 0.22);
    border: 1px solid rgba(168, 85, 247, 0.45);
    color: #e9d5ff;
    font-family: var(--font-en);
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 6px;
  }
  .ai-model-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 7px;
  }
  .model-spec-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    font-family: var(--font-th);
  }
  .spec-label {
    color: var(--text-muted);
  }
  .spec-val {
    color: var(--text-main);
    font-weight: 500;
  }

  /* Process Button */
  .btn-wrap {
    display: flex;
    width: 100%;
    margin-top: auto;
  }
  .btn-process-large {
    width: 100%;
    padding: 14px 18px;
    border-radius: 14px;
    border: none;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: white;
    font-size: 15.5px;
    font-weight: 700;
    font-family: var(--font-th);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    box-shadow: 0 8px 22px rgba(99, 102, 241, 0.35);
    transition: transform 0.22s ease, box-shadow 0.22s ease, opacity 0.22s ease;
  }
  .btn-process-large:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(168, 85, 247, 0.48);
  }
  .btn-process-large:disabled {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-dim);
    box-shadow: none;
    cursor: not-allowed;
  }

  /* Stats Row */
  .stats-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    width: 100%;
  }

  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  @media (max-width: 960px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
    .upload-area {
      min-height: 300px;
    }
  }

  @media (max-width: 560px) {
    .setting-grid-2col,
    .stats-row,
    .staged-metrics-grid {
      grid-template-columns: 1fr;
    }
    .drop-workflow-strip {
      flex-direction: column;
      align-items: flex-start;
    }
    .wf-arrow {
      display: none;
    }
  }

  /* ── Page Range Controls ── */
  .range-mode-toggle {
    display: flex;
    gap: 4px;
    background: rgba(0, 0, 0, 0.3);
    padding: 3px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .mode-pill-btn {
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 11.5px;
    padding: 3px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    font-family: var(--font-th);
  }
  .mode-pill-btn.active {
    background: rgba(99, 102, 241, 0.35);
    color: #ffffff;
    font-weight: 600;
  }
  .range-inputs-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    margin-top: 4px;
  }
  .range-input-group {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-th);
    flex: 1;
  }
  .range-number-input {
    width: 100%;
    max-width: 84px;
    padding: 6px 10px;
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 8px;
    color: #ffffff;
    font-size: 13px;
    text-align: center;
    outline: none;
    transition: border-color 0.2s;
  }
  .range-number-input:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }
  .range-sep {
    font-size: 12px;
    color: var(--text-dim);
    font-family: var(--font-th);
  }
  .range-tip {
    font-size: 11px;
    color: #7dd3fc;
    background: rgba(56, 189, 248, 0.08);
    border: 1px solid rgba(56, 189, 248, 0.22);
    border-radius: 8px;
    padding: 6px 10px;
    line-height: 1.45;
    font-family: var(--font-th);
    width: 100%;
  }
</style>
