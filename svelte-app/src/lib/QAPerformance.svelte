<script>
  import { onMount } from "svelte";
  import { toast } from "./toastStore.js";
  import { fade, slide } from "svelte/transition";
  import { addPerfHistory, selectedPerfHistory } from "./perfHistoryStore.js";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import CustomSelect from "./CustomSelect.svelte";
  import ProjectSelection from "./ProjectSelection.svelte";

  let projects = [];
  $: selectedProjectId = $selectedProjectStore ? ($selectedProjectStore.id || $selectedProjectStore.project_id) : "";
  
  let testName = "";
  let scriptFileName = "";
  let vus = 10;
  let duration = 30;
  let rampUp = 10;
  let rampDown = 10;

  let scriptType = "single";
  let apiEndpoints = [];
  let selectedEndpointIds = [];
  
  let isGenerating = false;
  let generatedCode = "";
  
  // --- Performance Analytic Modal State ---
  let showAnalyticModal = false;
  let kbDocuments = [];
  let analyticSkills = [];
  let selectedDocs = [];
  let selectedAnalyticSkill = "";
  let isAnalyzing = false;
  let generatedAnalyticScripts = [];
  let showAnalyticResult = false;
  
  async function openAnalyticModal() {
    showAnalyticModal = true;
    selectedDocs = [];
    selectedAnalyticSkill = "";
    generatedAnalyticScripts = [];
    isAnalyzing = false;
    showAnalyticResult = false;
    
    if ($selectedProjectStore) {
      const pid = $selectedProjectStore.project_id || $selectedProjectStore.id;
      try {
        const res = await fetch(`http://127.0.0.1:5000/api/kb/documents?project_id=${pid}`);
        if (res.ok) {
          const data = await res.json();
          kbDocuments = data.documents || [];
        }
      } catch (e) {
        console.error("Failed to fetch documents", e);
      }
    }
    
    if (analyticSkills.length === 0) {
      try {
        const res = await fetch(`http://127.0.0.1:5000/api/skills`);
        if (res.ok) {
          const data = await res.json();
          analyticSkills = data.skills || [];
        }
      } catch (e) {
        console.error("Failed to fetch skills", e);
      }
    }
  }

  function runAnalytic() {
    if (selectedDocs.length === 0 || !selectedAnalyticSkill) return;
    isAnalyzing = true;
    
    // Mocking AI response for now
    setTimeout(() => {
      generatedAnalyticScripts = [
        { id: 1, name: "Login Load Test (Spike)", description: "ทดสอบการ Login เข้าสู่ระบบพร้อมกัน 100 users", selected: true },
        { id: 2, name: "Upload Document Stress Test", description: "ทดสอบการอัปโหลดไฟล์ขนาดใหญ่แบบต่อเนื่อง", selected: true },
        { id: 3, name: "Search API Endurance Test", description: "ทดสอบการค้นหาข้อมูลเป็นเวลา 1 ชั่วโมง", selected: false }
      ];
      isAnalyzing = false;
      showAnalyticResult = true;
    }, 2500);
  }
  
  function saveAnalyticScripts() {
    const selected = generatedAnalyticScripts.filter(s => s.selected);
    toast(`บันทึก Script จำนวน ${selected.length} รายการเรียบร้อยแล้ว`, "success");
    showAnalyticModal = false;
    showAnalyticResult = false;
  }
  // ----------------------------------------

  // Mock fetching endpoints when project changes
  $: if (selectedProjectId) {
      apiEndpoints = [
          { id: 1, method: "GET", path: "/api/users", name: "Get Users" },
          { id: 2, method: "POST", path: "/api/login", name: "User Login" },
          { id: 3, method: "POST", path: "/api/upload", name: "Upload Document" }
      ];
      if (scriptType === 'single') {
          selectedEndpointIds = [];
      }
  }

  $: if (scriptType === 'single' && selectedEndpointIds.length > 1) {
      selectedEndpointIds = [selectedEndpointIds[0]];
  }

  // React to selected history
  $: if ($selectedPerfHistory) {
      testName = $selectedPerfHistory.name;
      scriptFileName = $selectedPerfHistory.scriptFileName || "";
      selectedProjectId = $selectedPerfHistory.project_id;
      vus = $selectedPerfHistory.vus;
      duration = $selectedPerfHistory.duration;
      rampUp = $selectedPerfHistory.rampUp;
      rampDown = $selectedPerfHistory.rampDown || 10;
      generatedCode = $selectedPerfHistory.code;
  }

  $: projectOptions = projects.map(p => ({
      value: p.id || p.project_id,
      label: `[${p.project_code || 'N/A'}] ${p.project_name || p.name}`
  }));

  const scriptTypeOptions = [
      { value: 'single', label: 'Single Endpoint (1 เส้นต่อ 1 สคริปต์)' },
      { value: 'scenario', label: 'Scenario (ทดสอบหลายเส้นต่อเนื่องกัน)' }
  ];

  onMount(async () => {
    try {
      const res = await fetch("http://localhost:5000/api/projects");
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
      }
    } catch (e) {
      console.error("Failed to fetch projects:", e);
      toast("ไม่สามารถโหลดข้อมูลโปรเจกต์ได้", "error");
    }
  });

  async function generateScript() {
    if (!selectedProjectId) {
      toast("กรุณาเลือกโปรเจกต์", "error");
      return;
    }
    if (!testName.trim()) {
      toast("กรุณาระบุชื่อการทดสอบ (Test Name)", "error");
      return;
    }
    if (selectedEndpointIds.length === 0) {
      toast("กรุณาเลือก API อย่างน้อย 1 เส้น", "error");
      return;
    }
    
    isGenerating = true;
    generatedCode = "";
    
    // Simulate AI generation time
    setTimeout(() => {
    const selectedApis = apiEndpoints.filter(a => selectedEndpointIds.includes(a.id));
    const isScenario = scriptType === 'scenario';
    
    let httpImports = "import http from 'k6/http';\nimport { check, sleep } from 'k6';";
    let optionsCode = `export const options = {
  stages: [
    { duration: '${rampUp}s', target: ${vus} }, // Ramp-up
    { duration: '${duration}s', target: ${vus} }, // Sustained load
    { duration: '${rampDown}s', target: 0 }, // Ramp-down
  ],
};`;
    
    let defaultFuncCode = `export default function () {
  const BASE_URL = 'http://localhost:5000';\n`;

    if (isScenario) {
      defaultFuncCode += `  // Scenario: Execute multiple endpoints sequentially\n`;
      selectedApis.forEach((api, idx) => {
        defaultFuncCode += `
  // ${idx + 1}. ${api.name}
  let res${idx} = http.${api.method.toLowerCase()}('` + '${BASE_URL}' + api.path + `');
  check(res${idx}, {
    '${api.path} status is 200': (r) => r.status === 200,
    '${api.path} time OK': (r) => r.timings.duration < 500,
  });\n`;
      });
    } else {
      let api = selectedApis[0];
      defaultFuncCode += `  // Single Endpoint Test: ${api.name}
  const url = '` + '${BASE_URL}' + api.path + `';
  const res = http.${api.method.toLowerCase()}(url);
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'transaction time OK': (r) => r.timings.duration < 200,
  });\n`;
    }

    defaultFuncCode += `  
  sleep(1);
}`;

      generatedCode = `${httpImports}\n\n${optionsCode}\n\n${defaultFuncCode}`;
      isGenerating = false;
      
      const projCode = projects.find(p => p.project_id === selectedProjectId)?.project_code || 'Project';
      addPerfHistory({
          id: Date.now(),
          name: testName,
          scriptFileName: scriptFileName,
          project_id: selectedProjectId,
          project_code: projCode,
          vus, duration, rampUp, rampDown,
          code: generatedCode,
          date: new Date().toISOString()
      });
      
      toast("สร้างสคริปต์ K6 สำเร็จ และบันทึกประวัติแล้ว", "success");
    }, 2000);
  }

  function copyCode() {
    if (generatedCode) {
      navigator.clipboard.writeText(generatedCode);
      toast("คัดลอกสคริปต์ไปยังคลิปบอร์ดแล้ว", "success");
    }
  }

  function downloadCode() {
    if (generatedCode) {
      const blob = new Blob([generatedCode], { type: 'text/javascript' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const projCode = projects.find(p => p.project_id === selectedProjectId)?.project_code || 'test';
      a.download = scriptFileName.trim() ? (scriptFileName.trim().endsWith('.js') ? scriptFileName.trim() : `${scriptFileName.trim()}.js`) : `k6_performance_test_${projCode}.js`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  }
  function selectProject(p) {
    selectedProjectStore.set(p);
  }
</script>

<div class="perf-container" in:fade>
  {#if !$selectedProjectStore}
    <ProjectSelection 
      {projects} 
      subtitle="กรุณาเลือกโครงการที่ต้องการ เพื่อเริ่มสร้าง Performance Test Script" 
      on:select={(e) => selectProject(e.detail)} 
    />
  {:else}
  <!-- MAIN QA PERFORMANCE SCREEN -->
  <div class="top-nav" style="margin-bottom: 20px;">
    <button class="btn-back" style="background: transparent; border: none; color: #a78bfa; font-size: 14px; display: flex; align-items: center; gap: 8px; cursor: pointer;" on:click={() => { selectedProjectStore.set(null); }}>
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
        <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
      </svg>
      ย้อนกลับไปหน้าเลือกโครงการ
    </button>
  </div>

  <div class="perf-header" style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
    <div style="display: flex; align-items: center; gap: 16px;">
      <div class="header-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path></svg>
      </div>
      <div class="header-text" style="display: flex; flex-direction: column; justify-content: center;">
        <div style="display: flex; align-items: center; gap: 16px;">
          <h2>Performance AIAgent</h2>
          <div style="font-size: 13px; color: #cbd5e1; background: rgba(15, 23, 42, 0.4); padding: 4px 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); display: flex; align-items: center;">
            โครงการปัจจุบัน: <strong style="color: #a78bfa; margin-left: 6px;">{$selectedProjectStore.project_code} - {$selectedProjectStore.name || $selectedProjectStore.project_name}</strong>
          </div>
        </div>
        <p style="margin-top: 4px;">สร้าง K6 Performance Test Script แบบอัตโนมัติจาก API Collection ของคุณ</p>
      </div>
    </div>
    <button class="btn-primary analytic-btn" on:click={openAnalyticModal}>
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
        <path d="M12.5 10a.5.5 0 0 1 .5.5v3a.5.5 0 0 1-1 0v-3a.5.5 0 0 1 .5-.5zm-4-4a.5.5 0 0 1 .5.5v7a.5.5 0 0 1-1 0v-7a.5.5 0 0 1 .5-.5zm-4 2a.5.5 0 0 1 .5.5v5a.5.5 0 0 1-1 0v-5a.5.5 0 0 1 .5-.5z"/>
        <path d="M0 2a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2zm15 2h-4v3h4V4zm0 4h-4v3h4V8zm0 4h-4v3h3a1 1 0 0 0 1-1v-2zm-5 3v-3H6v3h4zm-5 0v-3H1v2a1 1 0 0 0 1 1h3zm-4-4h4V8H1v3zm0-4h4V4H1v3zm5-3v3h4V4H6z"/>
      </svg>
      Performance Analytic
    </button>
  </div>

  <div class="perf-content">
    <div class="config-panel glass-panel">
      <h3>การตั้งค่า (Test Configuration)</h3>
      
      <div class="form-group">
        <label>ชื่อการทดสอบ (Test Name)</label>
        <input type="text" bind:value={testName} placeholder="e.g. Load Test - Login Flow" />
      </div>

      <div class="form-group">
        <label>ชื่อไฟล์สคริปต์ (Script File Name)</label>
        <input type="text" bind:value={scriptFileName} placeholder="e.g. login_load_test.js" />
        <span class="help-text">ชื่อไฟล์ที่จะดาวน์โหลด (ค่าเริ่มต้น: k6_performance_test.js)</span>
      </div>

      <!-- Target Project is handled globally -->
        <div class="form-group" in:slide>
          <label>รูปแบบสคริปต์ (Script Type)</label>
          <CustomSelect 
            bind:value={scriptType} 
            options={scriptTypeOptions} 
          />
        </div>

        <div class="form-group" in:slide>
          <label>เลือก API ที่ต้องการนำไปสร้าง Script</label>
          <div class="api-list">
            {#each apiEndpoints as api}
              <label class="api-item">
                {#if scriptType === 'single'}
                  <input type="radio" name="api_selection" value={api.id} 
                         checked={selectedEndpointIds[0] === api.id} 
                         on:change={() => selectedEndpointIds = [api.id]} />
                {:else}
                  <input type="checkbox" value={api.id} bind:group={selectedEndpointIds} />
                {/if}
                <span class="method {api.method.toLowerCase()}">{api.method}</span>
                <span class="path">{api.path}</span>
                <span class="name">({api.name})</span>
              </label>
            {/each}
          </div>
        </div>

      <div class="params-grid">
        <div class="form-group">
          <label>Virtual Users (VUs)</label>
          <input type="number" bind:value={vus} min="1" placeholder="e.g. 100" />
          <span class="help-text">จำนวนผู้ใช้งานจำลองพร้อมกัน</span>
        </div>
        
        <div class="form-group">
          <label>Duration (วินาที)</label>
          <input type="number" bind:value={duration} min="1" placeholder="e.g. 60" />
          <span class="help-text">ระยะเวลาการยิงโหลดหลัก</span>
        </div>
        
        <div class="form-group">
          <label>Ramp-up (วินาที)</label>
          <input type="number" bind:value={rampUp} min="0" placeholder="e.g. 10" />
          <span class="help-text">เวลาไต่ระดับจาก 0 ไปถึง VUs ที่ตั้งไว้</span>
        </div>
        
        <div class="form-group">
          <label>Ramp-down (วินาที)</label>
          <input type="number" bind:value={rampDown} min="0" placeholder="e.g. 10" />
          <span class="help-text">เวลาลดระดับจาก VUs กลับเป็น 0</span>
        </div>
      </div>

      <button class="btn-primary generate-btn" on:click={generateScript} disabled={isGenerating}>
        {#if isGenerating}
          <div class="spinner"></div> กำลังสร้างสคริปต์ด้วย AI...
        {:else}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"></path></svg>
          สร้าง K6 Script
        {/if}
      </button>
    </div>

    <div class="result-panel glass-panel">
      <div class="result-header">
        <h3>สคริปต์ที่สร้าง (Generated K6 Script)</h3>
        {#if generatedCode}
          <div class="action-buttons" in:fade>
            <button class="btn-icon" on:click={copyCode} title="Copy Code">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              Copy
            </button>
            <button class="btn-icon primary" on:click={downloadCode} title="Download .js">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
              Download
            </button>
          </div>
        {/if}
      </div>

      <div class="code-container">
        {#if isGenerating}
          <div class="loading-state">
            <div class="spinner-large"></div>
            <p>AI กำลังวิเคราะห์ API Collection และเขียนโค้ด...</p>
          </div>
        {:else if generatedCode}
          <pre class="code-block"><code>{generatedCode}</code></pre>
        {:else}
          <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
            <p>กรุณากำหนดค่าและกด "สร้าง K6 Script"</p>
          </div>
        {/if}
      </div>
    </div>
  </div>
  {/if}
</div>

{#if showAnalyticModal}
  <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={() => { if (!isAnalyzing) showAnalyticModal = false; }}>
    <div class="analytic-modal" on:click|stopPropagation>
      <div class="modal-header">
        <h2><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg> Performance Analytic AI</h2>
        <button class="btn-close" on:click={() => { if (!isAnalyzing) showAnalyticModal = false; }}>&times;</button>
      </div>

      <div class="modal-content">
        {#if isAnalyzing}
          <div class="loading-state">
            <div class="spinner-large"></div>
            <h3>AI กำลังวิเคราะห์เอกสาร...</h3>
            <p>กรุณารอสักครู่ ระบบกำลังสร้างแบบทดสอบตาม Requirement</p>
          </div>
        {:else if showAnalyticResult}
          <div class="result-state">
            <div class="result-summary-box">
              <span class="highlight">{generatedAnalyticScripts.length}</span> Scripts Generated
            </div>
            <p class="subtitle">เลือก Script ที่ต้องการนำไปใช้งาน</p>
            
            <div class="scripts-list">
              {#each generatedAnalyticScripts as script}
                <label class="script-item" class:selected={script.selected}>
                  <input type="checkbox" bind:checked={script.selected} />
                  <div class="script-info">
                    <div class="script-name">{script.name}</div>
                    <div class="script-desc">{script.description}</div>
                  </div>
                </label>
              {/each}
            </div>
            
            <div class="modal-footer">
              <button class="btn-outline" on:click={() => showAnalyticResult = false}>ย้อนกลับ</button>
              <button class="btn-primary" on:click={saveAnalyticScripts}>บันทึก Script ({generatedAnalyticScripts.filter(s => s.selected).length})</button>
            </div>
          </div>
        {:else}
          <!-- Configuration State -->
          <div class="form-group">
            <label>เลือกเอกสารที่เกี่ยวข้อง (Requirement / UAT)</label>
            <div class="docs-list">
              {#if kbDocuments.length === 0}
                <div class="empty-list">ไม่พบเอกสารในโครงการนี้</div>
              {:else}
                {#each kbDocuments as doc}
                  <label class="doc-checkbox">
                    <input type="checkbox" value={doc.id} bind:group={selectedDocs} />
                    <span>{doc.name}</span>
                  </label>
                {/each}
              {/if}
            </div>
          </div>
          
          <div class="form-group" style="margin-top: 20px;">
            <label>เลือก Skill AI สำหรับการวิเคราะห์</label>
            <select class="custom-select" bind:value={selectedAnalyticSkill}>
              <option value="" disabled>-- เลือก Skill --</option>
              {#each analyticSkills as skill}
                <option value={skill.skill_id}>{skill.skill_name}</option>
              {/each}
            </select>
          </div>
          
          <div class="modal-footer" style="margin-top: 30px;">
            <button class="btn-primary" style="width: 100%;" disabled={selectedDocs.length === 0 || !selectedAnalyticSkill} on:click={runAnalytic}>
              วิเคราะห์และสร้าง Script อัตโนมัติ
            </button>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  /* Main QA Performance Styles */
  .perf-container {
    padding: 24px 32px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 24px;
    overflow-y: auto;
  }

  .analytic-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 600;
    border-radius: 8px;
    background: linear-gradient(135deg, #a855f7, #7c3aed);
    color: white;
    border: none;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.2);
    transition: all 0.2s ease;
  }
  .analytic-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(124, 58, 237, 0.3);
  }
  
  .perf-header {
    margin-bottom: 8px;
  }

  .header-icon {
    width: 48px;
    height: 48px;
    background: linear-gradient(135deg, rgba(234, 179, 8, 0.2), rgba(234, 179, 8, 0.05));
    border: 1px solid rgba(234, 179, 8, 0.3);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #facc15;
  }

  .header-icon svg {
    width: 24px;
    height: 24px;
  }

  .header-text h2 {
    margin: 0 0 4px 0;
    font-size: 24px;
    font-weight: 600;
    color: #fff;
    font-family: var(--font-en);
  }

  .header-text p {
    margin: 0;
    font-size: 14px;
    color: var(--text-muted);
  }

  .perf-content {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: 24px;
    flex: 1;
    min-height: 0;
  }

  .glass-panel {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  }

  .config-panel {
    overflow-y: auto;
    overflow-x: hidden;
  }
  
  .config-panel::-webkit-scrollbar {
    width: 6px;
  }
  
  .config-panel::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .config-panel::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.3);
    border-radius: 4px;
  }
  
  .config-panel::-webkit-scrollbar-thumb:hover {
    background: rgba(148, 163, 184, 0.5);
  }

  h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #e2e8f0;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
  }

  .form-group label {
    font-size: 13px;
    font-weight: 500;
    color: #cbd5e1;
  }

  .form-group select, .form-group input {
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: #fff;
    padding: 8px 12px;
    border-radius: var(--radius-md);
    font-size: 14px;
    transition: all 0.2s;
    width: 100%;
    box-sizing: border-box;
  }

  .form-group select:focus, .form-group input:focus {
    outline: none;
    border-color: #facc15;
    box-shadow: 0 0 0 2px rgba(234, 179, 8, 0.1);
  }

  .help-text {
    font-size: 11px;
    color: var(--text-muted);
  }

  .params-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    padding-top: 12px;
    border-top: 1px dashed var(--glass-border);
  }

  .generate-btn {
    margin-top: auto;
    padding: 12px;
    font-size: 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background: linear-gradient(135deg, #eab308, #ca8a04);
    border: none;
    color: #fff;
    font-weight: 600;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all 0.3s;
    box-shadow: 0 4px 14px rgba(234, 179, 8, 0.2);
  }

  .generate-btn:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(234, 179, 8, 0.3);
  }

  .generate-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
    background: linear-gradient(135deg, #94a3b8, #64748b);
    box-shadow: none;
  }

  .api-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    background: rgba(15, 23, 42, 0.3);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: var(--radius-md);
    padding: 12px;
    max-height: 200px;
    overflow-y: auto;
  }

  .api-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.03);
    border-radius: 6px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all 0.2s;
  }

  .api-item:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(148, 163, 184, 0.3);
  }

  .api-item input {
    margin: 0;
    width: auto;
    cursor: pointer;
  }

  .method {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    color: #fff;
    min-width: 40px;
    text-align: center;
  }
  .method.get { background: #3b82f6; }
  .method.post { background: #10b981; }
  .method.put { background: #f59e0b; }
  .method.delete { background: #ef4444; }

  .path {
    font-family: monospace;
    font-size: 13px;
    color: #e2e8f0;
  }

  .name {
    font-size: 12px;
    color: #94a3b8;
  }

  .result-panel {
    padding: 20px;
    overflow: hidden;
  }

  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0;
  }

  .action-buttons {
    display: flex;
    gap: 8px;
  }

  .btn-icon {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: #cbd5e1;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-icon:hover {
    background: rgba(30, 41, 59, 0.9);
    color: #fff;
  }

  .btn-icon.primary {
    background: rgba(234, 179, 8, 0.15);
    border-color: rgba(234, 179, 8, 0.3);
    color: #fde047;
  }
  
  .btn-icon.primary:hover {
    background: rgba(234, 179, 8, 0.25);
  }

  .code-container {
    flex: 1;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.15);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    position: relative;
  }

  .code-block {
    flex: 1;
    margin: 0;
    padding: 20px;
    overflow: auto;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.5;
    color: #a5b4fc;
  }

  .empty-state, .loading-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 16px;
    color: var(--text-muted);
  }

  .empty-state svg {
    width: 48px;
    height: 48px;
    opacity: 0.5;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .spinner-large {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(234, 179, 8, 0.2);
    border-top-color: #facc15;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @media (max-width: 900px) {
    .perf-content {
      grid-template-columns: 1fr;
    }
    
    .code-container {
      min-height: 400px;
    }
  }
  .custom-select {
    width: 100%;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    color: #fff;
    padding: 10px 16px;
    font-size: 14px;
    appearance: none;
    outline: none;
  }
  .custom-select:focus {
    border-color: #a855f7;
  }

  /* Analytic Modal Styles */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .analytic-modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    width: 100%;
    max-width: 600px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .modal-header {
    padding: 20px 24px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(255, 255, 255, 0.02);
  }
  .modal-header h2 {
    margin: 0;
    font-size: 18px;
    display: flex;
    align-items: center;
    gap: 10px;
    color: #c084fc;
  }
  .btn-close {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 24px;
    cursor: pointer;
    line-height: 1;
    padding: 0;
  }
  .btn-close:hover {
    color: #fff;
  }
  .modal-content {
    padding: 24px;
  }
  .docs-list {
    max-height: 200px;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .empty-list {
    color: var(--text-muted);
    text-align: center;
    padding: 20px;
  }
  .doc-checkbox {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 6px;
    cursor: pointer;
    background: rgba(255,255,255,0.03);
    transition: background 0.2s;
  }
  .doc-checkbox:hover {
    background: rgba(255,255,255,0.08);
  }
  .doc-checkbox input {
    accent-color: #a855f7;
    width: 16px;
    height: 16px;
  }
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
  }
  
  .result-summary-box {
    text-align: center;
    font-size: 20px;
    margin-bottom: 8px;
    color: #fff;
  }
  .result-summary-box .highlight {
    color: #a855f7;
    font-size: 28px;
    font-weight: bold;
  }
  .subtitle {
    text-align: center;
    color: var(--text-muted);
    margin-bottom: 20px;
  }
  
  .scripts-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 300px;
    overflow-y: auto;
  }
  .script-item {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    padding: 16px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .script-item:hover {
    background: rgba(255, 255, 255, 0.06);
  }
  .script-item.selected {
    background: rgba(168, 85, 247, 0.1);
    border-color: rgba(168, 85, 247, 0.5);
  }
  .script-item input {
    accent-color: #a855f7;
    width: 18px;
    height: 18px;
    margin-top: 2px;
  }
  .script-name {
    font-weight: 600;
    color: #fff;
    margin-bottom: 4px;
  }
  .script-desc {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.4;
  }
</style>
