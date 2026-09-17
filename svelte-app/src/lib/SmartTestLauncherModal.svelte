<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { fade, scale, slide } from 'svelte/transition';

  export let projectId = '';
  export let projectName = '';
  export let cardData = null; // { id, title, description, ext_card_id, ... }
  export let isOpen = false;

  const dispatch = createEventDispatcher();

  let isLoadingMapping = true;
  let mappingError = null;

  // Configuration state
  let targetEnvironment = 'UAT';
  let userRole = 'Admin';
  let baseUrl = 'http://localhost:5173';
  let routePath = '/dashboard';
  let fullTargetUrl = 'http://localhost:5173/dashboard';

  let environments = [
    { name: 'DEV', url: 'http://localhost:5173', description: 'Local Dev Server' },
    { name: 'UAT', url: 'https://uat.example.com', description: 'UAT Testing Server' },
    { name: 'STAGING', url: 'https://staging.example.com', description: 'Staging Server' }
  ];

  let testCases = [];
  let testSteps = [];
  let matchedSitemapNode = null;
  let srsReferences = [];

  // Execution state
  let isExecuting = false;
  let executionProgressStep = 0;
  let executionResult = null;
  let executionError = null;
  let isLogsOpen = false;

  $: if (baseUrl && routePath) {
    const cleanRoute = routePath.startsWith('/') ? routePath : `/${routePath}`;
    fullTargetUrl = `${baseUrl.replace(/\/+$/, '')}${cleanRoute}`;
  }

  $: if (isOpen && cardData) {
    loadMapping();
  }

  function handleEnvChange(envName) {
    targetEnvironment = envName;
    const found = environments.find(e => e.name === envName);
    if (found && found.url) {
      baseUrl = found.url;
    }
  }

  async function loadMapping() {
    isLoadingMapping = true;
    mappingError = null;
    executionResult = null;
    executionError = null;

    try {
      const res = await fetch('http://localhost:5000/api/agent/map_test_card', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          card_data: cardData
        })
      });

      if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);
      const data = await res.json();

      if (data.success) {
        baseUrl = data.base_url || 'http://localhost:5173';
        routePath = data.target_route || '/';
        environments = data.environments || environments;
        testCases = (data.test_cases || []).map(tc => ({ 
          ...tc, 
          source: tc.source || 'srs',
          selected: true 
        }));
        testSteps = data.test_steps || [];
        matchedSitemapNode = data.matched_sitemap_node;
        srsReferences = data.srs_references || [];
      } else {
        mappingError = data.error || 'Failed to auto-map test card';
      }
    } catch (err) {
      console.error('Error auto-mapping test card:', err);
      mappingError = 'ไม่สามารถเชื่อมต่อ AI Mapping Engine ได้ กรุณาลองใหม่อีกครั้ง';
    } finally {
      isLoadingMapping = false;
    }
  }

  // Custom Test Case Management
  let showAddCustomTc = false;
  let newTcTitle = '';
  let newTcExpected = '';
  let newTcType = 'Positive';

  function addCustomTestCase() {
    if (!newTcTitle.trim()) return;
    const newId = `TC-CUSTOM-${testCases.length + 1}`;
    testCases = [
      ...testCases,
      {
        id: newId,
        title: newTcTitle.trim(),
        expected_result: newTcExpected.trim(),
        type: newTcType,
        source: 'custom',
        selected: true
      }
    ];
    newTcTitle = '';
    newTcExpected = '';
    newTcType = 'Positive';
    showAddCustomTc = false;
  }

  function removeTestCase(index) {
    testCases = testCases.filter((_, i) => i !== index);
  }

  function toggleAllTestCases(select) {
    testCases = testCases.map(tc => ({ ...tc, selected: select }));
  }

  $: selectedTestCasesCount = testCases.filter(tc => tc.selected).length;

  async function startExecution() {
    if (selectedTestCasesCount === 0) {
      alert('กรุณาเลือก Test Case อย่างน้อย 1 ข้อเพื่อทำการทดสอบ');
      return;
    }

    isExecuting = true;
    executionError = null;
    executionResult = null;
    executionProgressStep = 1;

    // Simulated progress steps during Playwright execution
    const interval = setInterval(() => {
      if (executionProgressStep < 3) {
        executionProgressStep += 1;
      }
    }, 2000);

    try {
      const selectedCases = testCases.filter(tc => tc.selected);
      const res = await fetch('http://localhost:5000/api/agent/execute_test_card', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          target_url: fullTargetUrl,
          environment: targetEnvironment,
          user_role: userRole,
          test_cases: selectedCases,
          test_steps: testSteps,
          card_id: cardData?.id || cardData?.saved_id,
          card_title: cardData?.title || 'Test Feature',
          description: cardData?.description || ''
        })
      });

      clearInterval(interval);
      if (!res.ok) throw new Error(`Server returned HTTP ${res.status}`);
      const data = await res.json();

      if (data.success) {
        executionResult = data;
        dispatch('test_completed', data);
      } else {
        executionError = data.error || 'Execution failed';
      }
    } catch (err) {
      clearInterval(interval);
      console.error('Test execution error:', err);
      executionError = 'เกิดข้อผิดพลาดในการรัน Playwright หรือ AI Evaluator: ' + err.message;
    } finally {
      isExecuting = false;
    }
  }

  function closeModal() {
    if (isExecuting) return;
    dispatch('close');
  }
</script>

{#if isOpen}
  <!-- Backdrop -->
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="test-modal-backdrop" transition:fade={{ duration: 180 }} on:click={closeModal}>
    <div class="test-modal-window" in:scale={{ start: 0.96, duration: 200 }} on:click|stopPropagation>
      
      <!-- Top Modal Header -->
      <div class="test-modal-header">
        <div class="header-left">
          <div class="agent-icon-badge">🚀</div>
          <div>
            <div class="modal-title-row">
              <h3 class="modal-main-title">Smart AI Test Agent Execution</h3>
              <span class="project-tag-pill">{projectName || 'Project'}</span>
            </div>
            <p class="modal-subtitle">AI Auto-Mapping: ระบุ Target URL, หน้าจอ, และ Test Cases จาก RAG & Traceability Matrix โดยอัตโนมัติ</p>
          </div>
        </div>

        <button class="btn-modal-close" on:click={closeModal} disabled={isExecuting}>✕</button>
      </div>

      <!-- Modal Body -->
      <div class="test-modal-body">
        
        <!-- Target Card Summary Card -->
        {#if cardData}
          <div class="target-feature-card">
            <div class="feature-info-row">
              <span class="feature-icon">🎯</span>
              <div class="feature-text">
                <div class="feature-label">Feature / Task ที่เลือกทดสอบ:</div>
                <div class="feature-title">{cardData.title}</div>
                {#if cardData.description}
                  <div class="feature-desc">{cardData.description}</div>
                {/if}
              </div>
            </div>
          </div>
        {/if}

        {#if isLoadingMapping}
          <div class="mapping-loading-state">
            <div class="spinner-large"></div>
            <h4>🧠 AI Agent กำลังวิเคราะห์ RAG Knowledge Base & Sitemap...</h4>
            <p>กำลังจับคู่ Route URL, เมนูหน้าจอ, Use Cases, และเลือก Test Cases ที่เกี่ยวข้อง</p>
          </div>

        {:else if mappingError}
          <div class="error-banner">
            <span>❌ {mappingError}</span>
            <button class="btn-retry" on:click={loadMapping}>🔄 ลองใหม่</button>
          </div>

        {:else}
          <!-- MAIN CONFIG & EXECUTION VIEW -->
          {#if !executionResult}
            <div class="config-grid-layout" transition:fade>
              
              <!-- LEFT COLUMN: ENVIRONMENT & TARGET URL -->
              <div class="config-col left">
                <div class="section-card">
                  <div class="section-card-title">
                    <span>🌐 1. กำหนด Environment & Target URL</span>
                  </div>

                  <!-- Environment Buttons -->
                  <div class="form-group">
                    <label class="form-label">เลือกสภาพแวดล้อม (Environment):</label>
                    <div class="env-button-group">
                      {#each environments as env}
                        <button 
                          class="btn-env-select" 
                          class:active={targetEnvironment === env.name} 
                          on:click={() => handleEnvChange(env.name)}>
                          <span class="env-code">{env.name}</span>
                          <span class="env-desc">{env.description}</span>
                        </button>
                      {/each}
                    </div>
                  </div>

                  <!-- Base URL & Route Path -->
                  <div class="form-group">
                    <label class="form-label" for="base-url-input">Base URL:</label>
                    <input 
                      id="base-url-input"
                      type="text" 
                      class="custom-text-input" 
                      bind:value={baseUrl} 
                      placeholder="เช่น http://localhost:5173 หรือ https://uat.example.com"
                    />
                  </div>

                  <div class="form-group">
                    <div class="label-with-badge">
                      <label class="form-label" for="route-path-input">Route Path (เส้นทางหน้าจอ):</label>
                      {#if matchedSitemapNode}
                        <span class="sitemap-match-tag">🗺️ Matched Sitemap: {matchedSitemapNode.title}</span>
                      {/if}
                    </div>
                    <input 
                      id="route-path-input"
                      type="text" 
                      class="custom-text-input" 
                      bind:value={routePath} 
                      placeholder="เช่น /transection-cert/table"
                    />
                  </div>

                  <!-- Full Resolved URL Preview Box -->
                  <div class="resolved-url-preview">
                    <div class="preview-label">👉 Target Full URL ที่ Agent จะเข้าไปทดสอบ:</div>
                    <div class="preview-url-text">{fullTargetUrl}</div>
                  </div>

                  <!-- User Role & Credentials -->
                  <div class="form-group mt-3">
                    <label class="form-label" for="user-role-select">สิทธิ์ผู้ใช้งาน (Role / Credentials):</label>
                    <select id="user-role-select" class="custom-select-input" bind:value={userRole}>
                      <option value="Admin">🛡️ Admin (ผู้ดูแลระบบสูงสุด)</option>
                      <option value="Operator">👷 Operator (เจ้าหน้าที่ปฏิบัติการ)</option>
                      <option value="Approver">✍️ Approver (ผู้อนุมัติเอกสาร)</option>
                      <option value="User">👤 Standard User (ผู้ใช้งานทั่วไป)</option>
                    </select>
                  </div>

                  {#if srsReferences && srsReferences.length > 0}
                    <div class="srs-refs-box">
                      <span class="srs-label">📚 อ้างอิงข้อกำหนดจาก RAG:</span>
                      {#each srsReferences as srs}
                        <span class="srs-tag">{srs}</span>
                      {/each}
                    </div>
                  {/if}
                </div>
              </div>

              <!-- RIGHT COLUMN: TEST CASES & STEPS -->
              <div class="config-col right">
                <div class="section-card">
                  <div class="section-card-title-row">
                    <div class="section-card-title">
                      <span>📋 2. รายการ Test Cases ({testCases.length})</span>
                    </div>
                    <div class="test-case-actions">
                      <button class="btn-toggle-tc" on:click={() => toggleAllTestCases(true)}>เลือกทั้งหมด</button>
                      <button class="btn-toggle-tc" on:click={() => toggleAllTestCases(false)}>ยกเลิกทั้งหมด</button>
                      <button class="btn-add-custom-tc" on:click={() => showAddCustomTc = !showAddCustomTc}>
                        {showAddCustomTc ? '✕ ปิดฟอร์ม' : '➕ เพิ่มเคสเอง'}
                      </button>
                    </div>
                  </div>

                  <div class="tc-source-explainer">
                    <span class="explainer-icon">💡</span>
                    <span>
                      เนื่องจากการ์ดนี้ยังไม่มีการเขียน Test Case ไว้ AI Agent จึงวิเคราะห์จากเอกสาร SRS & Sitemap ของโครงการเพื่อร่างเคสทดสอบตั้งต้นให้ ท่านสามารถกดลบ (🗑️) หรือกด <b>"➕ เพิ่มเคสเอง"</b> เพื่อกำหนดเคสที่ต้องการทดสอบจริงได้
                    </span>
                  </div>

                  <!-- Custom Test Case Inline Form -->
                  {#if showAddCustomTc}
                    <div class="custom-tc-form-box" transition:slide={{ duration: 160 }}>
                      <div class="custom-form-title">✍️ เพิ่ม Test Case กำหนดเอง</div>
                      <div class="custom-form-fields">
                        <div class="form-subgroup">
                          <label for="new-tc-type">ประเภท (Type):</label>
                          <div class="type-toggle-group" id="new-tc-type">
                            <button type="button" class="type-pill" class:active={newTcType === 'Positive'} on:click={() => newTcType = 'Positive'}>
                              ✅ Positive Case
                            </button>
                            <button type="button" class="type-pill" class:active={newTcType === 'Negative'} on:click={() => newTcType = 'Negative'}>
                              ⚠️ Negative Case
                            </button>
                          </div>
                        </div>
                        <div class="form-subgroup">
                          <label for="new-tc-title">ชื่อเคสทดสอบ (Title) *:</label>
                          <input id="new-tc-title" type="text" class="form-input-sm" placeholder="เช่น ทดสอบบันทึกข้อมูลแบบไม่กรอกข้อมูลบังคับ..." bind:value={newTcTitle} />
                        </div>
                        <div class="form-subgroup">
                          <label for="new-tc-expected">ผลลัพธ์ที่คาดหวัง (Expected Result):</label>
                          <input id="new-tc-expected" type="text" class="form-input-sm" placeholder="เช่น ระบบต้องแจ้งเตือนข้อผิดพลาดและไม่ให้บันทึก..." bind:value={newTcExpected} />
                        </div>
                        <div class="custom-form-buttons">
                          <button type="button" class="btn-save-custom-tc" on:click={addCustomTestCase} disabled={!newTcTitle.trim()}>
                            ➕ เพิ่มลงในรายการ
                          </button>
                          <button type="button" class="btn-cancel-custom-tc" on:click={() => showAddCustomTc = false}>
                            ยกเลิก
                          </button>
                        </div>
                      </div>
                    </div>
                  {/if}

                  <div class="test-cases-scroll-list">
                    {#if testCases.length === 0}
                      <div class="empty-tc-text">ไม่พบ Test Cases ในระบบ (กด "➕ เพิ่มเคสเอง" เพื่อสร้างเคสใหม่)</div>
                    {:else}
                      {#each testCases as tc, idx}
                        <div class="test-case-item-card" class:checked={tc.selected}>
                          <input type="checkbox" bind:checked={tc.selected} class="tc-checkbox" id={`tc-chk-${idx}`} />
                          <label for={`tc-chk-${idx}`} class="tc-info">
                            <div class="tc-header-row">
                              <span class="tc-id-badge">{tc.id || `TC-${idx+1}`}</span>
                              <span class="tc-type-badge {tc.type === 'Negative' ? 'neg' : 'pos'}">
                                {tc.type === 'Negative' ? '⚠️ Negative' : '✅ Positive'}
                              </span>
                              {#if tc.source === 'custom'}
                                <span class="tc-source-badge custom">✍️ กำหนดเอง</span>
                              {:else}
                                <span class="tc-source-badge srs" title="AI วิเคราะห์สร้างขึ้นจากข้อกำหนด SRS ในระบบ">🤖 จากเอกสาร SRS</span>
                              {/if}
                            </div>
                            <div class="tc-title">{tc.title}</div>
                            {#if tc.expected_result}
                              <div class="tc-expected"><b>Expected:</b> {tc.expected_result}</div>
                            {/if}
                          </label>
                          <button type="button" class="btn-tc-delete" title="ลบเคสนี้ออกจากการทดสอบ" on:click|preventDefault|stopPropagation={() => removeTestCase(idx)}>
                            🗑️
                          </button>
                        </div>
                      {/each}
                    {/if}
                  </div>

                  <!-- Suggested Test Steps Preview -->
                  {#if testSteps && testSteps.length > 0}
                    <div class="steps-preview-section">
                      <div class="steps-header">⚙️ ขั้นตอนการทดสอบ (Browser Action Steps):</div>
                      <div class="steps-list">
                        {#each testSteps as step}
                          <div class="step-row">
                            <span class="step-num">{step.step}</span>
                            <span class="step-action">{step.action}</span>
                            {#if step.target}
                              <span class="step-target">{step.target}</span>
                            {/if}
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              </div>

            </div>

          {:else}
            <!-- EXECUTION RESULT & EVIDENCE VIEW -->
            <div class="execution-result-view" transition:fade>
              
              <!-- Result Banner -->
              <div class="result-banner" class:passed={executionResult.is_passed} class:failed={!executionResult.is_passed}>
                <div class="result-badge-icon">{executionResult.is_passed ? '🎉' : '⚠️'}</div>
                <div class="result-summary-text">
                  <div class="result-verdict-title">
                    VERDICT: {executionResult.verdict} (คะแนนความสอดคล้อง: {executionResult.score_percent || 0}%)
                  </div>
                  <div class="result-summary-desc">{executionResult.summary}</div>
                </div>
              </div>

              <!-- 2-Col Layout: Left (Criteria & Defects), Right (Screenshot Evidence) -->
              <div class="result-details-grid">
                
                <!-- Left: Evaluation Details -->
                <div class="eval-details-box">
                  
                  <!-- Matched Criteria -->
                  <div class="eval-section">
                    <h4>✅ รายการที่ผ่านการตรวจสอบ (Passed Requirements):</h4>
                    <ul class="criteria-list">
                      {#each (executionResult.matched_criteria || []) as mc}
                        <li class="criteria-item pass">{mc}</li>
                      {/each}
                    </ul>
                  </div>

                  <!-- Defects & Discrepancies -->
                  {#if executionResult.discrepancies && executionResult.discrepancies.length > 0}
                    <div class="eval-section defects">
                      <h4>❌ ข้อบกพร่องที่ตรวจพบ (Defects Detected):</h4>
                      <div class="defects-stack">
                        {#each executionResult.discrepancies as def}
                          <div class="defect-card">
                            <div class="defect-header">
                              <span class="defect-severity {def.severity?.toLowerCase()}">[{def.severity || 'Defect'}]</span>
                              <span class="defect-item">{def.item}</span>
                            </div>
                            {#if def.impact}
                              <div class="defect-impact"><b>ผลกระทบ:</b> {def.impact}</div>
                            {/if}
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}

                  <!-- Recommendation -->
                  {#if executionResult.recommendation}
                    <div class="recommendation-card">
                      <b>💡 ข้อเสนอแนะสำหรับทีมพัฒนา/QA:</b>
                      <p>{executionResult.recommendation}</p>
                    </div>
                  {/if}

                  <!-- Execution Logs Accordion -->
                  {#if executionResult.logs}
                    <div class="logs-accordion">
                      <button class="btn-logs-toggle" on:click={() => isLogsOpen = !isLogsOpen}>
                        <span>📜 Browser Step Logs ({isLogsOpen ? 'ซ่อน' : 'แสดง'})</span>
                        <span>{isLogsOpen ? '▲' : '▼'}</span>
                      </button>
                      {#if isLogsOpen}
                        <pre class="logs-pre" transition:slide>{executionResult.logs}</pre>
                      {/if}
                    </div>
                  {/if}

                </div>

                <!-- Right: Screenshot Proof -->
                <div class="evidence-box">
                  <h4>📸 หลักฐานภาพถ่ายหน้าจอจริง (Live Proof Screenshot):</h4>
                  {#if executionResult.screenshot_url}
                    <div class="screenshot-frame">
                      <a href={executionResult.screenshot_url} target="_blank" rel="noreferrer" title="คลิกเพื่อดูภาพขนาดเต็ม">
                        <img src={executionResult.screenshot_url} alt="Test Evidence" class="proof-img" />
                      </a>
                      <div class="screenshot-caption">🔍 คลิกที่ภาพเพื่อเปิดดูความละเอียดสูงในแท็บใหม่</div>
                    </div>
                  {:else}
                    <div class="empty-shot">ไม่มีภาพถ่ายหน้าจอสำหรับรอบนี้</div>
                  {/if}
                </div>

              </div>

            </div>
          {/if}
        {/if}

      </div>

      <!-- Modal Footer -->
      <div class="test-modal-footer">
        {#if !executionResult}
          <div class="footer-left-info">
            <span class="tc-count-pill">เลือกแล้ว {selectedTestCasesCount} / {testCases.length} Test Cases</span>
            <span class="target-env-pill">🌐 {targetEnvironment} ({userRole})</span>
          </div>

          <div class="footer-actions">
            <button class="btn-cancel" on:click={closeModal} disabled={isExecuting}>ยกเลิก</button>
            <button 
              class="btn-start-run" 
              on:click={startExecution} 
              disabled={isExecuting || isLoadingMapping || selectedTestCasesCount === 0}>
              {#if isExecuting}
                <span class="spinner-small"></span>
                <span>กำลังเปิด Browser ทดสอบ (Step {executionProgressStep}/3)...</span>
              {:else}
                <span>🚀 เริ่มรันการทดสอบด้วย AI Agent</span>
              {/if}
            </button>
          </div>
        {:else}
          <div class="footer-left-info">
            <span class="test-done-pill">🎉 บันทึกผลการทดสอบลงประวัติโครงการเรียบร้อย</span>
          </div>
          <div class="footer-actions">
            <button class="btn-cancel" on:click={() => executionResult = null}>🔄 ปรับแต่งและรันใหม่</button>
            <button class="btn-finish" on:click={closeModal}>✅ เสร็จสิ้นและปิดหน้าต่าง</button>
          </div>
        {/if}
      </div>

    </div>
  </div>
{/if}

<style>
  .test-modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(3, 7, 18, 0.85);
    backdrop-filter: blur(8px);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .test-modal-window {
    background: #0b0f19;
    border: 1px solid rgba(139, 92, 246, 0.35);
    border-radius: 14px;
    width: 100%;
    max-width: 1100px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8), 0 0 30px rgba(124, 58, 237, 0.15);
    overflow: hidden;
  }

  /* Header */
  .test-modal-header {
    background: linear-gradient(90deg, rgba(30, 58, 138, 0.35), rgba(15, 23, 42, 0.8));
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding: 16px 22px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .agent-icon-badge {
    font-size: 26px;
    background: rgba(124, 58, 237, 0.25);
    border: 1px solid rgba(139, 92, 246, 0.5);
    border-radius: 10px;
    width: 46px;
    height: 46px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .modal-main-title {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: 0.3px;
  }

  .project-tag-pill {
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #93c5fd;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
  }

  .modal-subtitle {
    margin: 2px 0 0 0;
    font-size: 12px;
    color: #94a3b8;
  }

  .btn-modal-close {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #94a3b8;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
  }
  .btn-modal-close:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.4);
    color: #fca5a5;
  }

  /* Body */
  .test-modal-body {
    padding: 20px 24px;
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* Target Feature Card */
  .target-feature-card {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 16px;
  }

  .feature-info-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }
  .feature-icon { font-size: 20px; }
  .feature-label { font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase; }
  .feature-title { font-size: 14px; color: #f1f5f9; font-weight: 700; margin-top: 2px; }
  .feature-desc { font-size: 12px; color: #cbd5e1; margin-top: 4px; line-height: 1.4; }

  /* Loading State */
  .mapping-loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
    color: #94a3b8;
  }

  .spinner-large {
    width: 44px;
    height: 44px;
    border: 3px solid rgba(139, 92, 246, 0.2);
    border-top-color: #8b5cf6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 16px;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .mapping-loading-state h4 { color: #f8fafc; margin: 0 0 6px 0; font-size: 15px; }
  .mapping-loading-state p { margin: 0; font-size: 12.5px; }

  /* Error Banner */
  .error-banner {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #fca5a5;
    padding: 12px 16px;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
  }
  .btn-retry {
    background: #ef4444;
    color: white;
    border: none;
    padding: 5px 12px;
    border-radius: 5px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
  }

  /* Config Grid Layout */
  .config-grid-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
  }

  .section-card {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    box-sizing: border-box;
  }

  .section-card-title {
    font-size: 13px;
    font-weight: 700;
    color: #60a5fa;
  }

  .section-card-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .test-case-actions {
    display: flex;
    gap: 6px;
  }

  .btn-toggle-tc {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-toggle-tc:hover { background: rgba(255, 255, 255, 0.15); color: white; }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .form-label {
    font-size: 11.5px;
    color: #94a3b8;
    font-weight: 600;
  }

  .label-with-badge {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .sitemap-match-tag {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.35);
    color: #6ee7b7;
    font-size: 10.5px;
    padding: 1px 6px;
    border-radius: 4px;
    font-weight: 600;
  }

  .custom-text-input {
    background: #030712;
    border: 1px solid #334155;
    color: #f1f5f9;
    padding: 7px 10px;
    border-radius: 6px;
    font-size: 12.5px;
    outline: none;
    font-family: monospace;
  }
  .custom-text-input:focus { border-color: #8b5cf6; }

  .custom-select-input {
    background: #030712;
    border: 1px solid #334155;
    color: #f1f5f9;
    padding: 7px 10px;
    border-radius: 6px;
    font-size: 12px;
    outline: none;
  }

  .env-button-group {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  .btn-env-select {
    background: #030712;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-env-select:hover { border-color: #60a5fa; }
  .btn-env-select.active {
    background: rgba(59, 130, 246, 0.15);
    border-color: #3b82f6;
  }

  .env-code { font-weight: 700; color: #f8fafc; font-size: 12px; }
  .btn-env-select.active .env-code { color: #60a5fa; }
  .env-desc { font-size: 9.5px; color: #94a3b8; margin-top: 2px; }

  /* Resolved URL Preview */
  .resolved-url-preview {
    background: rgba(30, 58, 138, 0.2);
    border: 1px dashed rgba(96, 165, 250, 0.4);
    border-radius: 6px;
    padding: 8px 12px;
  }
  .preview-label { font-size: 11px; color: #93c5fd; font-weight: 600; margin-bottom: 3px; }
  .preview-url-text { font-size: 12px; color: #38bdf8; font-family: monospace; word-break: break-all; }

  .srs-refs-box {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 11px;
    color: #94a3b8;
    margin-top: 4px;
  }
  .srs-tag {
    background: rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
    padding: 1px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 10px;
  }

  /* Test Cases List */
  .tc-hint { font-size: 11.5px; color: #94a3b8; margin: 0; line-height: 1.4; }

  .test-cases-scroll-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 220px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .test-case-item-card {
    background: rgba(3, 7, 18, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 8px 12px;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    cursor: pointer;
    transition: all 0.15s;
  }
  .test-case-item-card:hover { border-color: rgba(255, 255, 255, 0.2); }
  .test-case-item-card.checked {
    background: rgba(139, 92, 246, 0.1);
    border-color: rgba(139, 92, 246, 0.4);
  }

  .tc-checkbox { margin-top: 3px; cursor: pointer; }
  .tc-info { flex: 1; }
  .tc-header-row { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
  .tc-id-badge { background: #1e293b; color: #cbd5e1; font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 3px; font-family: monospace; }
  .tc-type-badge { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 3px; }
  .tc-type-badge.pos { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  .tc-type-badge.neg { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
  .tc-title { font-size: 12px; color: #f1f5f9; font-weight: 600; }
  .tc-expected { font-size: 11px; color: #94a3b8; margin-top: 2px; }

  /* Custom Test Case Add & Badges */
  .btn-add-custom-tc {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #6ee7b7;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.15s;
  }
  .btn-add-custom-tc:hover {
    background: rgba(16, 185, 129, 0.3);
    color: white;
  }

  .tc-source-explainer {
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 11px;
    color: #93c5fd;
    line-height: 1.4;
    display: flex;
    gap: 6px;
    align-items: flex-start;
    margin-bottom: 8px;
  }

  .custom-tc-form-box {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(139, 92, 246, 0.4);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 10px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  }
  .custom-form-title {
    font-size: 11.5px;
    font-weight: 700;
    color: #c4b5fd;
    margin-bottom: 8px;
  }
  .custom-form-fields {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .form-subgroup {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .form-subgroup label {
    font-size: 10.5px;
    color: #cbd5e1;
    font-weight: 600;
  }
  .form-input-sm {
    background: #0b0f19;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 11.5px;
    color: white;
    outline: none;
  }
  .form-input-sm:focus {
    border-color: #8b5cf6;
  }
  .type-toggle-group {
    display: flex;
    gap: 6px;
  }
  .type-pill {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 11px;
    color: #94a3b8;
    cursor: pointer;
  }
  .type-pill.active {
    background: rgba(139, 92, 246, 0.25);
    border-color: #a78bfa;
    color: #f1f5f9;
    font-weight: 600;
  }
  .custom-form-buttons {
    display: flex;
    gap: 8px;
    margin-top: 4px;
  }
  .btn-save-custom-tc {
    background: #10b981;
    border: none;
    border-radius: 4px;
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 5px 12px;
    cursor: pointer;
  }
  .btn-save-custom-tc:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-cancel-custom-tc {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #94a3b8;
    border-radius: 4px;
    font-size: 11px;
    padding: 5px 10px;
    cursor: pointer;
  }

  .tc-source-badge {
    font-size: 9.5px;
    padding: 1px 5px;
    border-radius: 3px;
    font-weight: 500;
  }
  .tc-source-badge.srs {
    background: rgba(99, 102, 241, 0.2);
    color: #c7d2fe;
    border: 1px solid rgba(99, 102, 241, 0.3);
  }
  .tc-source-badge.custom {
    background: rgba(16, 185, 129, 0.2);
    color: #a7f3d0;
    border: 1px solid rgba(16, 185, 129, 0.3);
  }

  .btn-tc-delete {
    background: transparent;
    border: none;
    font-size: 13px;
    cursor: pointer;
    opacity: 0.5;
    padding: 2px 5px;
    border-radius: 4px;
    transition: all 0.15s;
    align-self: flex-start;
  }
  .btn-tc-delete:hover {
    opacity: 1;
    background: rgba(239, 68, 68, 0.25);
  }

  /* Steps Preview */
  .steps-preview-section {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .steps-header { font-size: 11.5px; font-weight: 700; color: #c084fc; }
  .steps-list { display: flex; flex-direction: column; gap: 4px; max-height: 120px; overflow-y: auto; }
  .step-row { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: #cbd5e1; }
  .step-num { width: 18px; height: 18px; background: rgba(139, 92, 246, 0.25); color: #d8b4fe; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; }
  .step-action { flex: 1; }
  .step-target { font-size: 9.5px; background: rgba(255, 255, 255, 0.06); padding: 1px 5px; border-radius: 3px; color: #94a3b8; }

  /* Execution Result View */
  .execution-result-view {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .result-banner {
    padding: 14px 18px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  .result-banner.passed {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #6ee7b7;
  }
  .result-banner.failed {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #fca5a5;
  }
  .result-badge-icon { font-size: 28px; }
  .result-verdict-title { font-size: 15px; font-weight: 700; color: #f8fafc; }
  .result-summary-desc { font-size: 12.5px; margin-top: 2px; }

  .result-details-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .eval-details-box { display: flex; flex-direction: column; gap: 12px; }
  .eval-section h4 { margin: 0 0 6px 0; font-size: 12.5px; color: #f1f5f9; }
  .criteria-list { margin: 0; padding-left: 20px; font-size: 12px; color: #cbd5e1; }
  .criteria-item { margin-bottom: 4px; }
  .criteria-item.pass { color: #a7f3d0; }

  .defects-stack { display: flex; flex-direction: column; gap: 6px; }
  .defect-card {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.25);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 12px;
  }
  .defect-severity { color: #f87171; font-weight: 700; margin-right: 4px; }
  .defect-item { color: #fca5a5; font-weight: 600; }
  .defect-impact { font-size: 11px; color: #fecaca; margin-top: 2px; }

  .recommendation-card {
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid rgba(245, 158, 11, 0.3);
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 12px;
    color: #fde68a;
  }
  .recommendation-card p { margin: 4px 0 0 0; }

  .logs-accordion { border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 8px; }
  .btn-logs-toggle {
    width: 100%;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #94a3b8;
    padding: 6px 12px;
    border-radius: 5px;
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    cursor: pointer;
  }
  .logs-pre {
    background: #030712;
    border: 1px solid #1f2937;
    color: #a5f3fc;
    padding: 10px;
    border-radius: 6px;
    font-size: 11px;
    white-space: pre-wrap;
    max-height: 140px;
    overflow-y: auto;
    margin-top: 6px;
  }

  /* Evidence Box */
  .evidence-box {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .evidence-box h4 { margin: 0; font-size: 12.5px; color: #93c5fd; }
  .screenshot-frame {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    overflow: hidden;
    background: #030712;
    text-align: center;
  }
  .proof-img {
    max-width: 100%;
    max-height: 320px;
    object-fit: contain;
    display: block;
    cursor: zoom-in;
    transition: transform 0.2s;
  }
  .proof-img:hover { transform: scale(1.02); }
  .screenshot-caption { font-size: 10.5px; color: #94a3b8; padding: 6px; background: #0f172a; }

  /* Footer */
  .test-modal-footer {
    background: #090d16;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding: 14px 22px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .footer-left-info { display: flex; align-items: center; gap: 8px; }
  .tc-count-pill { background: rgba(139, 92, 246, 0.2); color: #c4b5fd; font-size: 11.5px; font-weight: 600; padding: 3px 8px; border-radius: 4px; }
  .target-env-pill { background: rgba(59, 130, 246, 0.2); color: #93c5fd; font-size: 11.5px; font-weight: 600; padding: 3px 8px; border-radius: 4px; }
  .test-done-pill { color: #6ee7b7; font-size: 12px; font-weight: 600; }

  .footer-actions { display: flex; gap: 10px; }
  .btn-cancel {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-cancel:hover:not(:disabled) { background: rgba(255, 255, 255, 0.15); color: white; }

  .btn-start-run {
    background: linear-gradient(135deg, #7c3aed, #4f46e5);
    border: none;
    color: white;
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 14px rgba(124, 58, 237, 0.4);
    transition: all 0.15s;
  }
  .btn-start-run:hover:not(:disabled) {
    background: linear-gradient(135deg, #6d28d9, #4338ca);
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.6);
  }
  .btn-start-run:disabled { opacity: 0.5; cursor: not-allowed; }

  .btn-finish {
    background: #10b981;
    border: none;
    color: white;
    padding: 8px 20px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
  }
  .btn-finish:hover { background: #059669; }

  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    display: inline-block;
  }
</style>
