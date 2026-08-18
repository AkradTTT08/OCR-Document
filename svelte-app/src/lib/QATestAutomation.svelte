<script>
  import { onMount } from 'svelte';
  import { fade, slide } from 'svelte/transition';
  import { selectedProjectStore } from './qaHistoryStore.js';
  import ProjectSelection from './ProjectSelection.svelte';
  
  let projects = [];
  let requirements = [];
  let isLoading = false;
  let expandedReqId = null;
  
  onMount(async () => {
    try {
      const res = await fetch('http://127.0.0.1:5000/api/projects');
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
      }
    } catch(e) {
      console.error('Failed to load projects', e);
    }
  });

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  $: if ($selectedProjectStore) {
    loadRequirements($selectedProjectStore.id || $selectedProjectStore.project_id);
  }

  async function loadRequirements(projectId) {
    isLoading = true;
    try {
      const res = await fetch(`http://127.0.0.1:5000/api/requirements?project_id=${projectId}`);
      if (res.ok) {
        const data = await res.json();
        requirements = data.requirements || [];
      }
    } catch(e) {
      console.error('Failed to load requirements', e);
    } finally {
      isLoading = false;
    }
  }

  function toggleExpand(reqId) {
    expandedReqId = expandedReqId === reqId ? null : reqId;
  }
  
  // Phase 2: Web Exploration state
  let exploreUrl = "";
  let isExploring = false;
  let exploreResult = null;
  let exploreError = null;
  
  async function startExploration() {
    isExploring = true;
    exploreResult = null;
    exploreError = null;
    
    try {
      const res = await fetch('http://127.0.0.1:5000/api/agent/explore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: exploreUrl })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        exploreResult = {
          title: data.web_state?.title || 'Unknown Title',
          interactive_elements: data.web_state?.interactive_elements || [],
          file_saved: data.file_saved
        };
      } else {
        exploreError = data.error || 'Failed to explore URL';
      }
    } catch(err) {
      console.error(err);
      exploreError = 'Network error or backend is not running properly.';
    } finally {
      isExploring = false;
    }
  }

  // Phase 3: Alignment state
  let isAligning = false;
  let alignResult = null;
  let alignError = null;

  async function startAlignment() {
    isAligning = true;
    alignResult = null;
    alignError = null;
    try {
      const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
      const res = await fetch('http://127.0.0.1:5000/api/agent/align', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          project_id: pid,
          web_state_file: exploreResult.file_saved
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alignResult = data.alignment_report;
      } else {
        alignError = data.error || 'Failed to perform alignment';
      }
    } catch(err) {
      console.error(err);
      alignError = 'Network error during alignment.';
    } finally {
      isAligning = false;
    }
  }

  // Phase 4: Test Generation state
  let isGenerating = false;
  let generateResult = null;
  let generateError = null;

  async function startTestGeneration() {
    isGenerating = true;
    generateResult = null;
    generateError = null;
    try {
      const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
      const res = await fetch('http://127.0.0.1:5000/api/agent/generate-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          project_id: pid,
          web_state_file: exploreResult?.file_saved,
          gap_analysis: alignResult
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        generateResult = data.test_script;
        if (generateResult.suites && generateResult.suites.length > 0) {
           selectedTestSuite = generateResult.suites[0];
        }
      } else {
        generateError = data.error || 'Failed to generate test script';
      }
    } catch(err) {
      console.error(err);
      generateError = 'Network error during generation.';
    } finally {
      isGenerating = false;
    }
  }

  function downloadAllTests() {
    const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
    if (pid) {
      window.open(`http://127.0.0.1:5000/api/agent/download-tests/${pid}`, '_blank');
    }
  }

  let selectedTestSuite = null;

  // Phase 5: Test Execution & Self-Healing state
  let isRunningTest = false;
  let runTestSuccess = null;
  let runTestOutput = null;
  let runTestError = null;

  let isHealing = false;
  let healResult = null;
  let healError = null;

  async function startTestExecution() {
    isRunningTest = true;
    runTestSuccess = null;
    runTestOutput = null;
    runTestError = null;
    healResult = null;
    healError = null;
    try {
      const res = await fetch('http://127.0.0.1:5000/api/agent/run-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ file_name: selectedTestSuite?.saved_path || generateResult?.file_name })
      });
      const data = await res.json();
      if (res.ok) {
        runTestSuccess = data.success;
        runTestOutput = data.output;
      } else {
        runTestError = data.error || 'Failed to run test';
      }
    } catch(err) {
      console.error(err);
      runTestError = 'Network error during execution.';
    } finally {
      isRunningTest = false;
    }
  }

  async function startSelfHealing() {
    isHealing = true;
    healResult = null;
    healError = null;
    try {
      const res = await fetch('http://127.0.0.1:5000/api/agent/heal-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          file_name: selectedTestSuite?.saved_path || generateResult?.file_name,
          test_output: runTestOutput,
          original_code: selectedTestSuite?.code || generateResult?.code
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        healResult = data.healing_result;
        if (selectedTestSuite) {
            selectedTestSuite.code = healResult.fixed_code;
        } else if (generateResult) {
            generateResult.code = healResult.fixed_code;
        }
      } else {
        healError = data.error || 'Failed to heal test';
      }
    } catch(err) {
      console.error(err);
      healError = 'Network error during self-healing.';
    } finally {
      isHealing = false;
    }
  }
</script>

<div class="qa-automate-wrapper">
<div class="qa-automate-container">
{#if !$selectedProjectStore}
  <ProjectSelection 
    {projects} 
    on:select={(e) => selectProject(e.detail)} 
  />
{:else}
  <div class="top-nav" style="margin-bottom: 20px;">
    <button class="btn-back" on:click={() => selectedProjectStore.set(null)} style="background: none; border: none; color: #94a3b8; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px;">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
        <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
      </svg>
      ย้อนกลับไปหน้าเลือกโครงการ
    </button>
  </div>
  
  <div class="header-section">
    <h2>QA Test Automation (Autonomous QA)</h2>
    <p class="subtitle">ระบบสร้างสคริปต์ทดสอบอัตโนมัติจากเอกสารและวิเคราะห์การทำงานของระบบจริง (MCP Support)</p>
    <div class="active-project-badge" style="margin-top: 12px; display: inline-block; padding: 6px 16px; background: rgba(139, 92, 246, 0.1); border-radius: 20px; border: 1px solid rgba(139, 92, 246, 0.3); font-size: 14px;">
      โครงการปัจจุบัน: <strong style="color: #a78bfa;">{$selectedProjectStore.project_code} - {$selectedProjectStore.name}</strong>
    </div>
  </div>
  
  <div class="glass-panel">
    <div class="panel-header">
      <h3>Phase 1: Structured Requirements (Agent 1)</h3>
      <span class="badge">Phase 1 Complete</span>
    </div>
    <p class="desc-text">ผลลัพธ์จากการสกัดเอกสาร Requirement (PDF/Docx) ด้วย AI เพื่อแปลงเป็นรูปแบบโครงสร้าง JSON ที่พร้อมนำไปสร้าง Test Script</p>
    
    {#if isLoading}
      <div class="loading-state">
        <div class="spinner"></div>
        <p>กำลังโหลดข้อมูล Requirement...</p>
      </div>
    {:else if requirements.length === 0}
      <div class="empty-state">
        <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
        <p>ยังไม่มีข้อมูล Requirement สำหรับ Project นี้</p>
        <p class="hint">ให้ Admin ทำการ Scan OCR เอกสาร Requirement ระบบจะสกัดข้อมูลให้โดยอัตโนมัติ</p>
      </div>
    {:else}
      <div class="requirements-list">
        {#each requirements as req (req.req_id)}
          <div class="req-card" class:expanded={expandedReqId === req.req_id} transition:fade>
            <div class="req-header" on:click={() => toggleExpand(req.req_id)}>
              <div class="req-title">
                <span class="req-code">{req.req_code}</span>
                <h4>{req.title}</h4>
              </div>
              <div class="req-actions">
                <span class="status-badge {req.status.toLowerCase()}">{req.status}</span>
                <button class="expand-btn">
                  <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" style="transform: rotate({expandedReqId === req.req_id ? 180 : 0}deg); transition: transform 0.3s;"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </button>
              </div>
            </div>
            
            {#if expandedReqId === req.req_id}
              <div class="req-body" transition:slide>
                <div class="req-desc">
                  <strong>Description:</strong>
                  <p>{req.description}</p>
                </div>
                <div class="req-grid">
                  <div class="grid-col">
                    <strong>Actors:</strong> <p>{req.actors || '-'}</p>
                  </div>
                  <div class="grid-col">
                    <strong>Preconditions:</strong> <p>{req.preconditions || '-'}</p>
                  </div>
                </div>
                
                <div class="req-lists">
                  <div class="list-box">
                    <strong>Steps:</strong>
                    <ul>
                      {#each (req.steps || []) as step}
                        <li>{step}</li>
                      {/each}
                    </ul>
                  </div>
                  <div class="list-box">
                    <strong>Expected Results:</strong>
                    <ul>
                      {#each (req.expected_results || []) as res}
                        <li>{res}</li>
                      {/each}
                    </ul>
                  </div>
                </div>
                
                <div class="req-meta">
                  <span class="meta-item">
                    <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>
                    UI Elements: {(req.ui_elements || []).length}
                  </span>
                  <span class="meta-item">
                    <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
                    API Endpoints: {(req.api_endpoints || []).length}
                  </span>
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
  
  <div class="glass-panel">
    <div class="panel-header">
      <h3>Phase 2: Autonomous Web Exploration (Agent 2)</h3>
      <span class="badge in-progress">Phase 2 In Progress</span>
    </div>
    <p class="desc-text">ให้ AI Agent ทดลองเข้าถึงหน้าเว็บจริง (URL) เพื่อจำลองการใช้งานและดึงโครงสร้าง (DOM/Accessibility) มาเปรียบเทียบกับ Requirement ด้านบน</p>
    
    <div class="explore-form">
      <input type="text" bind:value={exploreUrl} placeholder="https://example.com/login" class="url-input" />
      <button class="btn-primary" on:click={startExploration} disabled={isExploring || !exploreUrl}>
        {#if isExploring}
          <div class="spinner-small"></div> Exploring...
        {:else}
          Start Web Exploration
        {/if}
      </button>
    </div>

    {#if exploreResult}
      <div class="explore-result" transition:slide>
        <h4>Exploration Complete!</h4>
        <p><strong>Page Title:</strong> {exploreResult.title}</p>
        <p><strong>Interactive Elements Found:</strong> {exploreResult.interactive_elements?.length || 0}</p>
        <p class="success-msg">Data saved to: {exploreResult.file_saved || 'web_state.json'}</p>
      </div>
    {/if}
    {#if exploreError}
      <div class="explore-error" transition:slide>
        <p>{exploreError}</p>
      </div>
    {/if}
  </div>

  <div class="glass-panel" class:disabled={!exploreResult || !exploreResult.file_saved}>
    <div class="panel-header">
      <h3>Phase 3: Semantic Alignment & Gap Analysis (Agent 3)</h3>
      {#if alignResult}
        <span class="badge">Phase 3 Complete</span>
      {:else}
        <span class="badge in-progress">Phase 3 Ready</span>
      {/if}
    </div>
    <p class="desc-text">เปรียบเทียบ Requirements ที่สกัดได้จาก Phase 1 กับโครงสร้างเว็บจริงจาก Phase 2 เพื่อหาช่องโหว่ (Gap Analysis)</p>
    
    <div class="explore-form">
      <button class="btn-primary" on:click={startAlignment} disabled={isAligning || !exploreResult || !exploreResult.file_saved}>
        {#if isAligning}
          <div class="spinner-small"></div> Analyzing Gaps...
        {:else}
          Start Gap Analysis
        {/if}
      </button>
    </div>

    {#if alignResult}
      <div class="align-result" transition:slide>
        <h4>Analysis Complete!</h4>
        <div class="align-summary">
          <p><strong>Summary:</strong> {alignResult.analysis_summary}</p>
        </div>
        
        <div class="align-issues">
          <strong>Discrepancies / Gaps:</strong>
          {#if alignResult.discrepancies && alignResult.discrepancies.length > 0}
            <ul>
              {#each alignResult.discrepancies as issue}
                <li class="issue-item severity-{issue.severity?.toLowerCase() || 'low'}">
                  <span class="issue-req">[{issue.req_code}]</span> {issue.issue}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="no-issue">No discrepancies found! Requirements and Web State are perfectly aligned.</p>
          {/if}
        </div>
        
        <div class="align-recommendation">
          <p><strong>Recommendation:</strong> {alignResult.recommendation}</p>
        </div>
      </div>
    {/if}
    {#if alignError}
      <div class="explore-error" transition:slide>
        <p>{alignError}</p>
      </div>
    {/if}
  </div>

  <div class="glass-panel" class:disabled={!alignResult}>
    <div class="panel-header">
      <h3>Phase 4: Test Script Generation (Agent 4)</h3>
      {#if generateResult}
        <span class="badge">Phase 4 Complete</span>
      {:else}
        <span class="badge in-progress">Phase 4 Ready</span>
      {/if}
    </div>
    <p class="desc-text">สร้างสคริปต์ Playwright (TypeScript) ด้วยรูปแบบ Page Object Model (POM) ตาม Requirement และ Web State</p>
    
    <div class="explore-form">
      <button class="btn-primary" on:click={startTestGeneration} disabled={isGenerating || !alignResult}>
        {#if isGenerating}
          <div class="spinner-small"></div> Generating Script...
        {:else}
          Generate Playwright Script
        {/if}
      </button>
    </div>

    {#if generateResult}
      <div class="align-result" transition:slide>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h4>Script Generated Successfully! ({generateResult.suites ? generateResult.suites.length : 1} Files)</h4>
            <button class="btn-primary" style="padding: 8px 16px; background: #10b981;" on:click={downloadAllTests}>
                Download All (.zip)
            </button>
        </div>
        
        {#if generateResult.suites}
            <div class="suite-list">
                {#each generateResult.suites as suite}
                    <div class="suite-card" class:active={selectedTestSuite === suite} on:click={() => selectedTestSuite = suite}>
                        <div class="suite-header">
                            <strong>{suite.menu_name}</strong>
                            <span class="test-count">{suite.test_count} Tests</span>
                        </div>
                        <div class="suite-meta">
                            <span>{suite.req_code}</span> | <span>{suite.file_name}</span>
                        </div>
                    </div>
                {/each}
            </div>
            
            {#if selectedTestSuite}
                <div class="code-preview-container">
                    <div style="color: #94a3b8; font-size: 12px; margin-bottom: 8px;">{selectedTestSuite.saved_path}</div>
                    <pre class="code-preview"><code>{selectedTestSuite.code}</code></pre>
                </div>
            {/if}
        {:else}
            <p class="success-msg">Saved to: {generateResult.file_name}</p>
            <div class="code-preview-container">
            <pre class="code-preview"><code>{generateResult.code}</code></pre>
            </div>
        {/if}
      </div>
    {/if}
    {#if generateError}
      <div class="explore-error" transition:slide>
        <p>{generateError}</p>
      </div>
    {/if}
  </div>

  <div class="glass-panel" class:disabled={!generateResult}>
    <div class="panel-header">
      <h3>Phase 5: Test Execution & Self-Healing (Agent 5)</h3>
      {#if runTestSuccess === true}
        <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #10b981; border-color: #10b981;">Test Passed</span>
      {:else if runTestSuccess === false}
        <span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border-color: #ef4444;">Test Failed</span>
      {:else}
        <span class="badge in-progress">Phase 5 Ready</span>
      {/if}
    </div>
    <p class="desc-text">รันสคริปต์ทดสอบที่ได้ หากพบว่ามีข้อผิดพลาดสามารถสั่งให้ Agent ทำการซ่อมแซมโค้ด (Self-Healing) ได้อัตโนมัติ</p>
    
    <div class="explore-form">
      <button class="btn-primary" on:click={startTestExecution} disabled={isRunningTest || !generateResult}>
        {#if isRunningTest}
          <div class="spinner-small"></div> Running Playwright...
        {:else}
          Run Test Script
        {/if}
      </button>

      {#if runTestSuccess === false && runTestOutput}
        <button class="btn-primary" style="background: linear-gradient(90deg, #f59e0b, #ef4444);" on:click={startSelfHealing} disabled={isHealing}>
          {#if isHealing}
            <div class="spinner-small"></div> Healing Script...
          {:else}
            Fix with Agent 5 (Self-Healing)
          {/if}
        </button>
      {/if}
    </div>

    {#if runTestOutput}
      <div class="align-result" transition:slide>
        <h4>Test Execution Output</h4>
        <div class="code-preview-container" style={runTestSuccess ? 'border-left: 3px solid #10b981;' : 'border-left: 3px solid #ef4444;'}>
          <pre class="code-preview"><code>{runTestOutput}</code></pre>
        </div>
      </div>
    {/if}
    {#if runTestError}
      <div class="explore-error" transition:slide>
        <p>{runTestError}</p>
      </div>
    {/if}

    {#if healResult}
      <div class="align-result" transition:slide style="margin-top: 16px; border-left: 3px solid #f59e0b;">
        <h4>Healing Complete! Code Updated.</h4>
        <p><strong>Analysis:</strong> {healResult.analysis}</p>
        <p><strong>Fix:</strong> {healResult.fix_explanation}</p>
      </div>
    {/if}
    {#if healError}
      <div class="explore-error" transition:slide>
        <p>{healError}</p>
      </div>
    {/if}
  </div>
  {/if}
</div>
</div>

<style>
  .qa-automate-wrapper {
    width: 100%;
    height: 100%;
    overflow-y: auto;
  }

  .qa-automate-container {
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
    padding: 30px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    color: var(--text-main);
  }
  
  .header-section {
    margin-bottom: 8px;
  }
  
  h2 {
    font-size: 28px;
    font-weight: 700;
    margin: 0;
    background: linear-gradient(135deg, #a78bfa, #f472b6, #38bdf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  
  .subtitle {
    color: var(--text-muted);
    font-size: 15px;
    margin-top: 4px;
  }
  
  .glass-panel {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 16px;
    padding: 24px;
    backdrop-filter: var(--glass-blur);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  }
  
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  
  .panel-header h3 {
    margin: 0;
    font-size: 20px;
    color: #e2e8f0;
  }
  
  .badge {
    background: rgba(16, 185, 129, 0.2);
    color: #34d399;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }
  
  .desc-text {
    color: var(--text-muted);
    font-size: 14px;
    margin-bottom: 24px;
  }
  
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px;
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.02);
    border-radius: 12px;
    border: 1px dashed rgba(255, 255, 255, 0.1);
  }
  
  .empty-state svg {
    margin-bottom: 16px;
    color: rgba(255, 255, 255, 0.3);
  }
  
  .empty-state .hint {
    font-size: 13px;
    color: #8b5cf6;
    margin-top: 8px;
  }
  
  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px;
    color: var(--text-muted);
  }
  
  .spinner {
    width: 30px;
    height: 30px;
    border: 3px solid rgba(255,255,255,0.1);
    border-top-color: #a78bfa;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
  }
  
  @keyframes spin { 100% { transform: rotate(360deg); } }
  
  .requirements-list {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .req-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.2s ease;
  }
  
  .req-card:hover {
    border-color: rgba(167, 139, 250, 0.5);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  }
  
  .req-card.expanded {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(167, 139, 250, 0.4);
  }
  
  .req-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    cursor: pointer;
  }
  
  .req-title {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .req-code {
    background: rgba(167, 139, 250, 0.2);
    color: #c4b5fd;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
  }
  
  .req-title h4 {
    margin: 0;
    font-size: 16px;
    font-weight: 500;
  }
  
  .req-actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .status-badge {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    background: rgba(255, 255, 255, 0.1);
  }
  
  .expand-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .req-body {
    padding: 0 20px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    margin-top: 8px;
    padding-top: 16px;
  }
  
  .req-desc {
    margin-bottom: 16px;
  }
  
  .req-desc p {
    color: #cbd5e1;
    font-size: 14px;
    line-height: 1.5;
    margin: 8px 0 0;
  }
  
  .req-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }
  
  .grid-col p {
    color: #cbd5e1;
    font-size: 14px;
    margin: 4px 0 0;
  }
  
  .req-lists {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }
  
  .list-box {
    background: rgba(0, 0, 0, 0.2);
    padding: 16px;
    border-radius: 8px;
  }
  
  .list-box ul {
    margin: 8px 0 0;
    padding-left: 20px;
    color: #cbd5e1;
    font-size: 13px;
    line-height: 1.6;
  }
  
  .list-box li {
    margin-bottom: 4px;
  }
  
  .req-meta {
    display: flex;
    gap: 16px;
    padding-top: 12px;
    border-top: 1px dashed rgba(255, 255, 255, 0.1);
  }
  
  .meta-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #94a3b8;
  }
  
  .coming-soon {
    background: linear-gradient(180deg, rgba(255,255,255,0.02) 0%, rgba(56, 189, 248, 0.05) 100%);
    border: 1px solid rgba(56, 189, 248, 0.2);
    text-align: center;
    padding: 32px;
  }
  
  .coming-soon h3 {
    color: #38bdf8;
    margin: 0 0 12px;
  }
  
  .btn-primary {
    background: linear-gradient(90deg, #a78bfa, #f472b6);
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    font-size: 14px;
    margin-top: 16px;
    cursor: pointer;
  }
  
  .btn-primary.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: #475569;
  }
  
  .explore-form {
    display: flex;
    gap: 12px;
    margin-top: 16px;
  }
  
  .url-input {
    flex: 1;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 12px 16px;
    color: white;
    font-size: 14px;
    outline: none;
    transition: all 0.2s;
  }
  
  .url-input:focus {
    border-color: #a78bfa;
    box-shadow: 0 0 0 2px rgba(167, 139, 250, 0.2);
  }
  
  .explore-result {
    margin-top: 24px;
    padding: 20px;
    background: rgba(16, 185, 129, 0.05);
    border: 1px solid rgba(16, 185, 129, 0.2);
    border-radius: 12px;
  }
  
  .explore-result h4 {
    color: #34d399;
    margin: 0 0 12px 0;
    font-size: 16px;
  }
  
  .explore-result p {
    color: #cbd5e1;
    margin: 4px 0;
    font-size: 14px;
  }
  
  .success-msg {
    color: #a78bfa !important;
    margin-top: 12px !important;
    font-family: monospace;
    font-size: 13px !important;
  }
  
  .explore-error {
    margin-top: 24px;
    padding: 16px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    color: #fca5a5;
    font-size: 14px;
  }
  
  .badge.in-progress {
    background: rgba(56, 189, 248, 0.1);
    color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.3);
  }
  
  .spinner-small {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    display: inline-block;
    vertical-align: text-bottom;
    margin-right: 8px;
  }
  
  .btn-primary {
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(90deg, #a78bfa, #f472b6);
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    color: white;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    margin-top: 0;
  }
  
  .glass-panel.disabled {
    opacity: 0.5;
    pointer-events: none;
  }
  
  .align-result {
    margin-top: 24px;
    padding: 20px;
    background: rgba(56, 189, 248, 0.05);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 12px;
  }
  
  .align-result h4 {
    color: #38bdf8;
    margin: 0 0 16px 0;
    font-size: 16px;
  }
  
  .align-summary, .align-recommendation {
    background: rgba(255, 255, 255, 0.03);
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 16px;
    border-left: 3px solid #8b5cf6;
  }
  
  .align-summary p, .align-recommendation p {
    margin: 0;
    color: #e2e8f0;
    font-size: 14px;
    line-height: 1.5;
  }
  
  .align-issues {
    margin-bottom: 16px;
  }
  
  .align-issues strong {
    color: #cbd5e1;
    display: block;
    margin-bottom: 8px;
  }
  
  .align-issues ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .issue-item {
    padding: 10px 12px;
    border-radius: 6px;
    font-size: 14px;
    display: flex;
    align-items: flex-start;
    gap: 8px;
    background: rgba(255,255,255,0.02);
    border-left: 3px solid #94a3b8;
  }
  
  .issue-item.severity-high {
    background: rgba(239, 68, 68, 0.1);
    border-left-color: #ef4444;
    color: #fca5a5;
  }
  
  .issue-item.severity-medium {
    background: rgba(245, 158, 11, 0.1);
    border-left-color: #f59e0b;
    color: #fcd34d;
  }
  
  .issue-item.severity-low {
    background: rgba(59, 130, 246, 0.1);
    border-left-color: #3b82f6;
    color: #93c5fd;
  }
  
  .issue-req {
    font-weight: 700;
    white-space: nowrap;
    opacity: 0.8;
  }
  
  .no-issue {
    color: #10b981;
    padding: 12px;
    background: rgba(16, 185, 129, 0.1);
    border-radius: 6px;
    margin: 0;
  }
  
  .code-preview-container {
    margin-top: 16px;
    background: #1e293b;
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  
  .code-preview {
    margin: 0;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    color: #e2e8f0;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
  }
  
  .suite-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
    margin-top: 16px;
  }
  
  .suite-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  
  .suite-card:hover {
    background: rgba(255,255,255,0.05);
    border-color: #a78bfa;
  }
  
  .suite-card.active {
    background: rgba(167, 139, 250, 0.1);
    border-color: #a78bfa;
    box-shadow: 0 0 0 1px #a78bfa;
  }
  
  .suite-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  
  .suite-header strong {
    color: #f8fafc;
    font-size: 15px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    padding-right: 8px;
  }
  
  .test-count {
    background: #312e81;
    color: #818cf8;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
  }
  
  .suite-meta {
    font-size: 12px;
    color: #94a3b8;
  }
</style>
