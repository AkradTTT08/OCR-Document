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
          <div class="code-input-wrapper">
            <label for="code-input">Source Code</label>
            <textarea 
              id="code-input" 
              bind:value={sourceCode} 
              placeholder="วาง Source Code ของคุณที่นี่..." 
            ></textarea>
          </div>
        {:else}
          <div class="github-input-wrapper">
            <label for="github-input">GitHub Repository URL</label>
            <input 
              type="text" 
              id="github-input" 
              bind:value={githubUrl} 
              placeholder="https://github.com/username/repo" 
            />
            <div class="info-box">
              <strong>หมายเหตุ:</strong> ระบบจะโคลน Repository แบบชั่วคราวและดึงเฉพาะไฟล์ Source Code ที่รองรับ หากโปรเจกต์มีขนาดใหญ่มาก ระบบอาจจะตัดข้อมูลบางส่วนออกอัตโนมัติเพื่อป้องกัน Error จาก AI
            </div>
          </div>
        {/if}

        <button class="btn-primary scan-btn" on:click={scanCode} disabled={isLoading}>
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
            <div class="markdown-preview">
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
    gap: 20px;
    min-height: 100%;
    height: auto;
    padding: 20px 24px;
    box-sizing: border-box;
    max-width: 1600px;
    margin: 0 auto;
    width: 100%;
    overflow-y: auto;
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

  .main-card {
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(16px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg, 16px);
    padding: 24px;
    box-sizing: border-box;
    width: 100%;
  }

  .flex-row {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 28px;
    align-items: stretch;
    min-height: 580px;
  }

  .input-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-right: 28px;
    border-right: 1px solid var(--glass-border);
    box-sizing: border-box;
  }

  .form-group-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .select-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  
  .select-field label,
  .code-input-wrapper label,
  .github-input-wrapper label {
    font-size: 13.5px;
    color: var(--text-muted);
    font-weight: 500;
  }

  .tabs-container {
    margin-top: 2px;
  }

  .tabs {
    display: inline-flex;
    background: rgba(0, 0, 0, 0.35);
    padding: 4px;
    border-radius: 12px;
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
    border-radius: 8px;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13.5px;
    font-weight: 500;
    transition: all 0.2s ease;
  }
  .tab-btn:hover:not(.active) {
    background: rgba(255,255,255,0.06);
    color: var(--text-light);
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
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    color: var(--text-light);
    font-family: var(--font-en, monospace);
    transition: all 0.2s ease;
    font-size: 13.5px;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.15);
    box-sizing: border-box;
  }
  
  #code-input {
    flex: 1;
    height: 300px;
    min-height: 220px;
    max-height: 520px;
    line-height: 1.6;
    resize: vertical;
  }
  
  #github-input:focus, #code-input:focus {
    outline: none;
    border-color: rgba(99, 102, 241, 0.6);
    background: rgba(0, 0, 0, 0.45);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
  }

  .info-box {
    padding: 14px 16px;
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.5;
    color: #c7d2fe;
  }

  .scan-btn {
    width: 100%;
    padding: 12px 20px;
    font-weight: 600;
    font-size: 14.5px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border-radius: 10px;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
    transition: all 0.2s ease;
  }

  .output-section {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 480px;
    box-sizing: border-box;
  }

  .output-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--glass-border);
  }

  .output-header h3 {
    margin: 0;
    font-size: 15.5px;
    color: #f1f5f9;
  }

  .report-content {
    flex: 1;
    height: 100%;
    min-height: 440px;
    max-height: 600px;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--glass-border);
    box-sizing: border-box;
  }
  
  /* Markdown Styles for Preview */
  .markdown-preview {
    white-space: pre-wrap;
    line-height: 1.65;
    color: #e2e8f0;
    font-size: 13.5px;
  }
  .markdown-preview h1, .markdown-preview h2, .markdown-preview h3 {
    color: #f8fafc;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
  }
  .markdown-preview p {
    margin-bottom: 0.9em;
  }
  .markdown-preview code {
    background: rgba(0,0,0,0.4);
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    color: #a5b4fc;
  }
  .markdown-preview pre {
    background: rgba(0,0,0,0.5) !important;
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
    margin-bottom: 0.4em;
  }

  .badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }
  .badge-danger { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); }
  .badge-success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }

  .empty-state, .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 380px;
    color: var(--text-dim);
    text-align: center;
    gap: 16px;
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
