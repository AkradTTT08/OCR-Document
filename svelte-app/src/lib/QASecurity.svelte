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
    { value: 'SANS Top 25', label: 'SANS Top 25 - คลอบคลุมช่องโหว่ทั่วไป' },
    { value: 'CWE Top 25 Most Dangerous', label: 'CWE Top 25 - จุดอ่อนที่อันตรายที่สุด' },
    { value: 'Auto / Best Practice', label: 'Auto / Best Practice' }
  ];

  onMount(async () => {
    try {
      const resProjects = await fetch("http://127.0.0.1:5000/api/projects");
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
      toast("กรุณาใส่ Source Code เพื่อแสกน", "warning");
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
      
      const response = await fetch("http://127.0.0.1:5000/api/qa/security/scan", {
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
        toast("แสกนเสร็จสิ้น ไม่พบช่องโหว่ร้ายแรง", "success");
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
      <button class="btn-back" on:click={resetProject}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        เปลี่ยนโครงการ
      </button>
    </div>

    <div class="header-text">
      <h2>QA Security Code Scanner 🛡️</h2>
      <p>ตรวจสอบและวิเคราะห์ช่องโหว่ของ Source Code ด้วย AI ตามมาตรฐานสากล (เช่น OWASP)</p>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code} - {selectedProjectObj.name}</strong>
      </div>
    </div>

    <div class="main-card glass-panel flex-row" style="padding: 24px;">
      <!-- Left Column: Input -->
    <div class="input-section">
      <div class="form-group" style="display: flex; gap: 16px;">
        <!-- Language Select -->
        <div style="flex: 1;">
          <label for="lang-select">ภาษาโปรแกรมมิ่ง (Language)</label>
          <CustomSelect id="lang-select" options={langOptions} bind:value={language} />
        </div>

        <!-- Standard Select -->
        <div style="flex: 1;">
          <label for="std-select">เกณฑ์การตรวจสอบ (Standard)</label>
          <CustomSelect id="std-select" options={stdOptions} bind:value={standard} />
        </div>
      </div>

      <div class="tabs-container">
        <div class="tabs">
          <button class="tab-btn {inputMode === 'paste' ? 'active' : ''}" on:click={() => inputMode = 'paste'}>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            วาง Source Code
          </button>
          <button class="tab-btn {inputMode === 'github' ? 'active' : ''}" on:click={() => inputMode = 'github'}>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
            ดึงจาก GitHub
          </button>
        </div>
      </div>

      {#if inputMode === 'paste'}
        <div class="form-group" style="flex: 1; display: flex; flex-direction: column;">
          <label for="code-input">Source Code</label>
          <textarea 
            id="code-input" 
            bind:value={sourceCode} 
            placeholder="วาง Source Code ของคุณที่นี่..." 
            style="flex: 1; min-height: 340px; font-family: monospace; resize: vertical;"
          ></textarea>
        </div>
      {:else}
        <div class="form-group" style="flex: 1; display: flex; flex-direction: column;">
          <label for="github-input">GitHub Repository URL</label>
          <input 
            type="text" 
            id="github-input" 
            bind:value={githubUrl} 
            placeholder="https://github.com/username/repo" 
            style="margin-bottom: 16px;"
          />
          <div class="info-box" style="padding: 12px; background: rgba(99, 102, 241, 0.1); border-radius: 8px; font-size: 13px; color: var(--text-muted);">
            <strong>หมายเหตุ:</strong> ระบบจะโคลน Repository แบบชั่วคราวและดึงเฉพาะไฟล์ Source Code ที่รองรับ หากโปรเจกต์มีขนาดใหญ่มาก ระบบอาจจะตัดข้อมูลบางส่วนออกอัตโนมัติเพื่อป้องกัน Error จาก AI
          </div>
        </div>
      {/if}

      <button class="btn-primary" on:click={scanCode} disabled={isLoading} style="margin-top: 16px;">
        {#if isLoading}
          <div class="spinner"></div> กำลังแสกนช่องโหว่...
        {:else}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          เริ่มการแสกนโค้ด
        {/if}
      </button>
    </div>

    <!-- Right Column: Output -->
    <div class="output-section">
      <div class="output-header">
        <h3>ผลการวิเคราะห์ (Security Report)</h3>
        {#if scanReport}
          <div class="badge {vulnFound > 0 ? 'badge-danger' : 'badge-success'}">
            {vulnFound > 0 ? `พบ ${vulnFound} จุดที่ควรระวัง` : 'ปลอดภัย'}
          </div>
        {/if}
      </div>

      <div class="report-content">
        {#if isLoading}
          <div class="loading-state">
            <div class="loader-pulse"></div>
            <p>AI กำลังวิเคราะห์รูปแบบโค้ดและค้นหาช่องโหว่...</p>
          </div>
        {:else if scanReport}
          <!-- Render Markdown in production we'd use marked.js -->
          <div class="markdown-preview" style="white-space: pre-wrap; line-height: 1.6;">
            {scanReport}
          </div>
        {:else}
          <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="var(--border-color)" stroke-width="1" width="48" height="48"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
            <p>วางโค้ดและกดแสกนเพื่อดูผลลัพธ์</p>
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
    gap: 24px;
    height: 100%;
    padding: 20px 24px;
    box-sizing: border-box;
    max-width: 100%;
    margin: 0;
    width: 100%;
    animation: fadeIn 0.4s ease-out;
  }

  .top-nav {
    display: flex;
    justify-content: flex-start;
  }

  .btn-back {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-dim);
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  }
  .btn-back:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-light);
  }

  .active-project-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 12px;
    padding: 6px 14px;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.25);
    color: #a5b4fc;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
  }

  .flex-row {
    display: flex;
    gap: 24px;
    flex: 1;
    min-height: 0;
  }

  .input-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding-right: 24px;
    border-right: 1px solid var(--glass-border);
  }
  
  .form-group {
    margin-bottom: 24px;
  }
  
  .form-group label {
    font-size: 14px;
    color: var(--text-muted);
    margin-bottom: 8px;
    display: block;
    font-weight: 500;
  }
  
  #github-input, #code-input {
    width: 100%;
    padding: 16px 20px;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    color: var(--text-light);
    font-family: var(--font-en);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    font-size: 14px;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
    box-sizing: border-box;
  }
  
  #code-input {
    line-height: 1.6;
  }
  
  #github-input:focus, #code-input:focus {
    outline: none;
    border-color: rgba(99, 102, 241, 0.6);
    background: rgba(0, 0, 0, 0.4);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
  }

  .tabs-container {
    margin-bottom: 20px;
  }

  .tabs {
    display: inline-flex;
    background: rgba(0, 0, 0, 0.3);
    padding: 4px;
    border-radius: 12px;
    border: 1px solid var(--glass-border);
  }

  .tab-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: transparent;
    border: none;
    border-radius: 8px;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.2s ease;
  }
  .tab-btn:hover:not(.active) {
    background: rgba(255,255,255,0.05);
    color: var(--text-light);
  }
  .tab-btn.active {
    background: var(--primary);
    color: #ffffff;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  }

  .output-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .output-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--glass-border);
  }

  .output-header h3 {
    margin: 0;
    font-size: 16px;
  }

  .report-content {
    flex: 1;
    overflow-y: auto;
    background: rgba(0,0,0,0.2);
    border-radius: 8px;
    padding: 20px;
    border: 1px solid var(--glass-border);
  }
  
  /* Markdown Styles for Preview */
  .markdown-preview {
    white-space: pre-wrap;
    line-height: 1.6;
    color: #e2e8f0;
    font-size: 14px;
  }
  .markdown-preview h1, .markdown-preview h2, .markdown-preview h3 {
    color: #f8fafc;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
  }
  .markdown-preview p {
    margin-bottom: 1em;
  }
  .markdown-preview code {
    background: rgba(0,0,0,0.3);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    color: #a5b4fc;
  }
  .markdown-preview pre {
    background: rgba(0,0,0,0.4) !important;
    padding: 16px;
    border-radius: 8px;
    overflow-x: auto;
    border: 1px solid var(--glass-border);
  }
  .markdown-preview pre code {
    background: transparent;
    padding: 0;
    color: #e2e8f0;
  }
  .markdown-preview ul, .markdown-preview ol {
    margin-left: 20px;
    margin-bottom: 1em;
  }
  .markdown-preview li {
    margin-bottom: 0.5em;
  }

  .badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  .badge-success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }

  .empty-state, .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-dim);
    text-align: center;
    gap: 16px;
  }

  .loader-pulse {
    width: 40px; height: 40px;
    background: var(--primary);
    border-radius: 50%;
    animation: pulse 1.5s infinite ease-in-out;
  }

  @keyframes pulse {
    0% { transform: scale(0.8); opacity: 0.5; }
    50% { transform: scale(1.2); opacity: 1; }
    100% { transform: scale(0.8); opacity: 0.5; }
  }

  @media (max-width: 900px) {
    .flex-row { flex-direction: column; }
    .input-section { border-right: none; padding-right: 0; border-bottom: 1px solid var(--glass-border); padding-bottom: 24px; }
  }
</style>
