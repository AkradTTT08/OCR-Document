<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";
  import CustomSelect from "./CustomSelect.svelte";

  let projects = [];
  $: selectedProjectObj = $selectedProjectStore;

  let sourceCode = "";
  let githubUrl = "";
  let inputMode = "paste"; // 'paste' | 'github'
  let language = "auto";
  let standard = "OWASP Top 10 (2021)";
  let isLoading = false;
  let scanReport = null;
  let vulnFound = 0;

  $: codeLineCount = sourceCode ? sourceCode.split("\n").length : 0;

  const langOptions = [
    { value: 'auto', label: 'Auto Detect' },
    { value: 'python', label: 'Python' },
    { value: 'javascript', label: 'JavaScript / Node.js' },
    { value: 'java', label: 'Java' },
    { value: 'php', label: 'PHP' },
    { value: 'go', label: 'Go' },
    { value: 'csharp', label: 'C#' }
  ];

  const stdOptions = [
    { value: 'OWASP Top 10 (2021)', label: 'OWASP Top 10 (2021) - พื้นฐาน' },
    { value: 'OWASP ASVS 4.0.3', label: 'OWASP ASVS 4.0.3 - เชิงลึก' },
    { value: 'SANS Top 25', label: 'SANS Top 25 - ครอบคลุมช่องโหว่ทั่วไป' },
    { value: 'CWE Top 25 Most Dangerous', label: 'CWE Top 25 - จุดอ่อนที่อันตรายที่สุด' },
    { value: 'Auto / Best Practice', label: 'Auto / Best Practice' }
  ];

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatSecurityMarkdown(md) {
    if (!md) return "";
    const codeBlocks = [];
    let text = String(md).replace(/```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)```/g, (_, lang, code) => {
      const idx = codeBlocks.length;
      codeBlocks.push(`<pre><code class="lang-${escapeHtml(lang)}">${escapeHtml(code.trimEnd())}</code></pre>`);
      return `@@CODEBLOCK_${idx}@@`;
    });

    const lines = text.split(/\r?\n/);
    const out = [];
    let inList = false;

    for (const rawLine of lines) {
      const trimmed = rawLine.trim();
      if (/^@@CODEBLOCK_\d+@@$/.test(trimmed)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(trimmed);
        continue;
      }
      if (!trimmed) {
        if (inList) { out.push("</ul>"); inList = false; }
        continue;
      }
      let safe = escapeHtml(rawLine)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

      if (/^###\s+/.test(safe)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<h3>${safe.replace(/^###\s+/, "")}</h3>`);
      } else if (/^##\s+/.test(safe)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<h2>${safe.replace(/^##\s+/, "")}</h2>`);
      } else if (/^#\s+/.test(safe)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<h1>${safe.replace(/^#\s+/, "")}</h1>`);
      } else if (/^\s*[-*]\s+/.test(safe)) {
        if (!inList) { out.push("<ul>"); inList = true; }
        out.push(`<li>${safe.replace(/^\s*[-*]\s+/, "")}</li>`);
      } else {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<p>${safe}</p>`);
      }
    }
    if (inList) out.push("</ul>");

    return out
      .join("\n")
      .replace(/@@CODEBLOCK_(\d+)@@/g, (_, i) => codeBlocks[Number(i)] || "");
  }

  async function copyScanReport() {
    if (!scanReport) return;
    try {
      await navigator.clipboard.writeText(scanReport);
      toast("คัดลอกรายงานความปลอดภัยเรียบร้อยแล้ว", "success");
    } catch (e) {
      toast("ไม่สามารถคัดลอกรายงานได้", "error");
    }
  }

  onMount(async () => {
    try {
      const resProjects = await fetch("/api/projects");
      if (resProjects.ok) {
        const pData = await resProjects.json();
        projects = pData.projects || [];
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  });

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  function resetProject() {
    selectedProjectStore.set(null);
    scanReport = null;
    vulnFound = 0;
    sourceCode = "";
    githubUrl = "";
  }

  async function scanCode() {
    if (inputMode === 'paste' && !sourceCode.trim()) {
      toast("กรุณาใส่ Source Code เพื่อสแกน", "warning");
      return;
    }
    if (inputMode === 'github' && !githubUrl.trim()) {
      toast("กรุณาใส่ลิงก์ GitHub Repository", "warning");
      return;
    }

    isLoading = true;
    scanReport = null;
    vulnFound = 0;

    try {
      const payload = { 
        language: language,
        standard: standard 
      };
      if (inputMode === 'paste') {
        payload.source_code = sourceCode;
      } else {
        payload.github_url = githubUrl;
      }
      
      const response = await fetch("/api/qa/security/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to scan code");
      }

      scanReport = data.report;
      vulnFound = data.vulnerabilities_found;
      
      if (vulnFound > 0) {
        toast(`พบช่องโหว่ความปลอดภัย ${vulnFound} จุด!`, "warning");
      } else {
        toast("สแกนเสร็จสิ้น ไม่พบช่องโหว่ร้ายแรง", "success");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาด: ${err.message}`, "error");
    } finally {
      isLoading = false;
    }
  }
</script>

<div class="qa-security-container" in:fade>
  {#if !selectedProjectObj}
    <ProjectSelection 
      {projects} 
      on:select={(e) => selectProject(e.detail)} 
    />
  {:else}
    <div class="top-nav">
      <button type="button" class="btn-back" on:click={resetProject}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        เปลี่ยนโครงการ
      </button>

      <div class="active-project-badge">
        <span class="proj-dot" aria-hidden="true"></span>
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code} - {selectedProjectObj.name}</strong>
      </div>
    </div>

    <div class="header-text">
      <h2>QA Security Code Scanner</h2>
      <p>ตรวจสอบและวิเคราะห์ช่องโหว่ของ Source Code ด้วย AI ตามมาตรฐานสากล (OWASP, ASVS, SANS, CWE)</p>
    </div>

    <div class="main-card glass-panel flex-row">
      <!-- Left Column: Input -->
      <div class="input-section">
        <div class="form-group-row">
          <!-- Language Select -->
          <div class="select-field">
            <label for="lang-select">ภาษาโปรแกรมมิ่ง (Language)</label>
            <CustomSelect id="lang-select" options={langOptions} bind:value={language} />
          </div>

          <!-- Standard Select -->
          <div class="select-field">
            <label for="std-select">เกณฑ์การตรวจสอบ (Standard)</label>
            <CustomSelect id="std-select" options={stdOptions} bind:value={standard} />
          </div>
        </div>

        <div class="tabs-container">
          <div class="tabs" role="tablist" aria-label="รูปแบบการนำเข้าโค้ด">
            <button type="button" role="tab" aria-selected={inputMode === 'paste'} class="tab-btn {inputMode === 'paste' ? 'active' : ''}" on:click={() => inputMode = 'paste'}>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
              วาง Source Code
            </button>
            <button type="button" role="tab" aria-selected={inputMode === 'github'} class="tab-btn {inputMode === 'github' ? 'active' : ''}" on:click={() => inputMode = 'github'}>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
              ดึงจาก GitHub
            </button>
          </div>
        </div>

        {#if inputMode === 'paste'}
          <div class="code-input-wrapper">
            <div class="code-label-row">
              <label for="code-input">Source Code</label>
              <div class="code-meta-tools">
                {#if sourceCode}
                  <span class="line-count-pill">{codeLineCount} บรรทัด</span>
                  <button type="button" class="btn-clear-code" on:click={() => (sourceCode = "")}>ล้างโค้ด</button>
                {/if}
              </div>
            </div>
            <textarea 
              id="code-input" 
              bind:value={sourceCode} 
              placeholder="วาง Source Code ของคุณที่นี่..." 
              spellcheck="false"
            ></textarea>
          </div>
        {:else}
          <div class="github-input-wrapper">
            <label for="github-input">GitHub Repository URL</label>
            <input 
              type="url" 
              id="github-input" 
              bind:value={githubUrl} 
              placeholder="https://github.com/username/repo" 
            />
            <div class="info-box">
              <strong>หมายเหตุ:</strong> ระบบจะโคลน Repository แบบชั่วคราวและดึงเฉพาะไฟล์ Source Code ที่รองรับ หากโปรเจกต์มีขนาดใหญ่มาก ระบบจะคัดกรองเฉพาะไฟล์หลักให้อัตโนมัติ
            </div>
          </div>
        {/if}

        <button type="button" class="btn-primary scan-btn" on:click={scanCode} disabled={isLoading}>
          {#if isLoading}
            <span class="spinner" aria-hidden="true"></span> กำลังสแกนช่องโหว่...
          {:else}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
            เริ่มการสแกนโค้ด
          {/if}
        </button>
      </div>

      <!-- Right Column: Output -->
      <div class="output-section">
        <div class="output-header">
          <h3>ผลการวิเคราะห์ (Security Report)</h3>
          <div class="output-header-actions">
            {#if scanReport}
              <div class="badge {vulnFound > 0 ? 'badge-danger' : 'badge-success'}">
                {vulnFound > 0 ? `พบ ${vulnFound} จุดที่ควรระวัง` : 'ปลอดภัย'}
              </div>
              <button type="button" class="btn-copy-report" on:click={copyScanReport}>
                คัดลอกรายงาน
              </button>
            {/if}
          </div>
        </div>

        <div class="report-content" aria-live="polite">
          {#if isLoading}
            <div class="loading-state">
              <div class="loader-pulse"></div>
              <p>AI กำลังวิเคราะห์รูปแบบโค้ดและค้นหาช่องโหว่ตามเกณฑ์ {standard}...</p>
            </div>
          {:else if scanReport}
            <div class="markdown-preview">
              {@html formatSecurityMarkdown(scanReport)}
            </div>
          {:else}
            <div class="empty-state">
              <div class="empty-shield-orb" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="32" height="32"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
              </div>
              <div class="empty-title">พร้อมตรวจสอบความปลอดภัยของโค้ด</div>
              <p>วาง Source Code หรือระบุ GitHub URL ทางด้านซ้าย แล้วกดปุ่มเริ่มการสแกนโค้ด</p>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .qa-security-container {
    display: flex;
    flex-direction: column;
    gap: 18px;
    height: 100%;
    padding: 20px 24px 48px;
    box-sizing: border-box;
    max-width: 100%;
    margin: 0;
    width: 100%;
    overflow-y: auto;
  }

  .top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    width: 100%;
    flex-shrink: 0;
  }

  .btn-back {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    padding: 8px 16px;
    border-radius: var(--radius-sm, 8px);
    cursor: pointer;
    font-size: 13.5px;
    transition: all 0.2s;
    flex-shrink: 0;
  }
  .btn-back svg {
    flex-shrink: 0;
  }
  .btn-back:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-main);
  }

  .active-project-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    box-sizing: border-box;
  }
  .active-project-badge strong {
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }

  .proj-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--primary, #6366f1);
    box-shadow: 0 0 8px var(--primary, #6366f1);
    flex-shrink: 0;
  }

  .header-text {
    flex-shrink: 0;
  }

  .header-text h2 {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: clamp(22px, 2.4vw, 28px);
    font-weight: 700;
    color: var(--text-main, #f8fafc);
    margin: 0 0 6px 0;
  }

  .header-text p {
    font-size: 14.5px;
    color: var(--text-muted, #94a3b8);
    margin: 0;
  }

  .main-card {
    background: color-mix(in srgb, var(--bg2, #12141c) 72%, transparent);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg, 20px);
    padding: 24px;
    box-sizing: border-box;
    width: 100%;
    flex-shrink: 0;
  }

  .flex-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 0;
    align-items: stretch;
    min-height: 560px;
  }

  .input-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
    padding-right: 24px;
    border-right: 1px solid var(--glass-border);
    box-sizing: border-box;
  }

  .form-group-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 16px;
  }

  .select-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }
  
  .select-field label,
  .code-input-wrapper label,
  .github-input-wrapper label {
    font-size: 13.5px;
    color: var(--text-main, #f8fafc);
    font-weight: 600;
  }

  .code-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .code-meta-tools {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }

  .line-count-pill {
    font-size: 11px;
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.06);
    padding: 2px 8px;
    border-radius: 10px;
  }

  .btn-clear-code {
    background: transparent;
    border: none;
    color: #fda4af;
    font-size: 12px;
    cursor: pointer;
    text-decoration: underline;
    padding: 4px 8px;
    border-radius: 6px;
    transition: background-color 0.15s ease, color 0.15s ease;
  }
  .btn-clear-code:hover {
    background: rgba(244, 63, 94, 0.12);
    color: #fecdd3;
  }

  .tabs-container {
    margin-top: 2px;
  }

  .tabs {
    display: inline-flex;
    background: color-mix(in srgb, var(--bg, #0a0b12) 78%, transparent);
    padding: 4px;
    border-radius: var(--radius-md, 12px);
    border: 1px solid var(--glass-border);
    gap: 4px;
  }

  .tab-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 18px;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm, 8px);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13.5px;
    font-weight: 500;
    transition: all 0.2s ease;
  }
  .tab-btn svg {
    flex-shrink: 0;
  }
  .tab-btn:hover:not(.active) {
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-main);
  }
  .tab-btn.active {
    background: var(--primary, #6366f1);
    color: #ffffff;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
  }

  .code-input-wrapper {
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 8px;
    min-height: 280px;
  }

  .github-input-wrapper {
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 12px;
    min-height: 280px;
  }

  #github-input, #code-input {
    width: 100%;
    padding: 14px 16px;
    background: color-mix(in srgb, var(--bg, #0a0b12) 78%, transparent);
    border: 1px solid var(--glass-border-light);
    border-radius: var(--radius-md, 12px);
    color: var(--text-main);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    font-size: 13px;
    box-sizing: border-box;
  }
  
  #code-input {
    flex: 1;
    height: 300px;
    min-height: 240px;
    max-height: 520px;
    line-height: 1.6;
    resize: vertical;
  }
  
  #github-input:focus, #code-input:focus {
    outline: none;
    border-color: var(--primary, #6366f1);
    background: var(--bg, #0a0b12);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22);
  }

  .info-box {
    padding: 14px 16px;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.22);
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.55;
    color: #c7d2fe;
  }

  .scan-btn {
    width: 100%;
    padding: 13px 20px;
    font-weight: 600;
    font-size: 14.5px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border-radius: var(--radius-md, 12px);
    box-shadow: 0 6px 20px -4px rgba(99, 102, 241, 0.4);
  }
  .scan-btn svg {
    flex-shrink: 0;
  }
  .scan-btn .spinner {
    width: 16px;
    height: 16px;
    margin-right: 2px;
  }

  .output-section {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 480px;
    min-width: 0;
    padding-left: 24px;
    box-sizing: border-box;
  }

  .output-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--glass-border);
  }

  .output-header h3 {
    margin: 0;
    font-size: 15.5px;
    color: var(--text-main);
  }

  .output-header-actions {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .btn-copy-report {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 30px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #c7d2fe;
    padding: 0 12px;
    border-radius: var(--radius-sm, 8px);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    box-sizing: border-box;
    transition: all 0.2s ease;
  }
  .btn-copy-report:hover {
    background: var(--primary, #6366f1);
    color: #ffffff;
  }

  .report-content {
    flex: 1;
    height: 100%;
    min-height: 440px;
    max-height: 600px;
    overflow-y: auto;
    background: color-mix(in srgb, var(--bg, #0a0b12) 78%, transparent);
    border-radius: var(--radius-md, 12px);
    padding: 20px;
    border: 1px solid var(--glass-border);
    box-sizing: border-box;
  }
  
  /* Markdown Styles for Preview */
  .markdown-preview {
    line-height: 1.65;
    color: #e2e8f0;
    font-size: 13.5px;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .markdown-preview :global(h1),
  .markdown-preview :global(h2),
  .markdown-preview :global(h3) {
    color: var(--text-main, #f8fafc);
    margin-top: 1.1em;
    margin-bottom: 0.45em;
  }
  .markdown-preview :global(h1:first-child),
  .markdown-preview :global(h2:first-child),
  .markdown-preview :global(h3:first-child) {
    margin-top: 0;
  }
  .markdown-preview :global(p) {
    margin: 0 0 0.85em 0;
  }
  .markdown-preview :global(code) {
    background: rgba(99, 102, 241, 0.15);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #c7d2fe;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  .markdown-preview :global(pre) {
    background: rgba(5, 5, 5, 0.75);
    padding: 14px 16px;
    border-radius: var(--radius-sm, 8px);
    overflow-x: auto;
    border: 1px solid var(--glass-border);
    margin: 0.8em 0;
  }
  .markdown-preview :global(pre code) {
    background: transparent;
    padding: 0;
    color: #e2e8f0;
    overflow-wrap: normal;
    word-break: normal;
  }
  .markdown-preview :global(ul) {
    margin: 0 0 1em 20px;
  }
  .markdown-preview :global(li) {
    margin-bottom: 0.35em;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 30px;
    padding: 0 12px;
    border-radius: var(--radius-sm, 8px);
    font-size: 12px;
    font-weight: 600;
    box-sizing: border-box;
  }
  .badge-danger { background: rgba(244, 63, 94, 0.18); color: #fda4af; border: 1px solid rgba(244, 63, 94, 0.35); }
  .badge-success { background: rgba(16, 185, 129, 0.18); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.35); }

  .empty-state, .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 380px;
    color: var(--text-muted);
    text-align: center;
    gap: 12px;
  }

  .empty-shield-orb {
    width: 64px;
    height: 64px;
    border-radius: 18px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: #a5b4fc;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 4px;
  }

  .empty-title {
    font-size: 15.5px;
    font-weight: 600;
    color: var(--text-main);
  }

  .loader-pulse {
    width: 40px; height: 40px;
    background: var(--primary, #6366f1);
    border-radius: 50%;
    animation: pulse 1.5s infinite ease-in-out;
  }

  @keyframes pulse {
    0% { transform: scale(0.8); opacity: 0.5; }
    50% { transform: scale(1.2); opacity: 1; }
    100% { transform: scale(0.8); opacity: 0.5; }
  }

  /* Responsive Breakpoints */
  @media (max-width: 1024px) {
    .flex-row {
      grid-template-columns: 1fr;
      min-height: auto;
      gap: 24px;
    }
    .input-section {
      border-right: none;
      padding-right: 0;
      border-bottom: 1px solid var(--glass-border);
      padding-bottom: 24px;
    }
    .output-section {
      padding-left: 0;
      min-height: auto;
    }
    #code-input {
      height: 240px;
      min-height: 180px;
    }
    .report-content {
      min-height: 320px;
      max-height: 480px;
    }
    .empty-state, .loading-state {
      min-height: 280px;
    }
  }

  @media (max-width: 640px) {
    .qa-security-container {
      padding: 14px 12px;
      gap: 16px;
    }
    .main-card {
      padding: 16px;
    }
    .form-group-row {
      grid-template-columns: 1fr;
      gap: 12px;
    }
    .tabs {
      width: 100%;
      display: flex;
    }
    .tab-btn {
      flex: 1;
      justify-content: center;
      padding: 8px 10px;
      font-size: 13px;
    }
  }
</style>
