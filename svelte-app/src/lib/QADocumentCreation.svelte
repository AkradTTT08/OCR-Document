<script>
  import { onMount, onDestroy } from 'svelte';
  import { selectedProjectStore } from './qaHistoryStore.js';
  import { toast } from './toastStore.js';
  import { fade, slide } from 'svelte/transition';
  import ProjectSelection from './ProjectSelection.svelte';
  import CustomSelect from './CustomSelect.svelte';

  let docName = "";
  let docType = "Test Case"; // Default
  let docTypes = ["SRS", "Test Case", "UAT", "Other"];
  
  let skills = [];
  let selectedSkillId = "";
  
  let isGenerating = false;

  let generatedHistory = [];
  let pollingInterval = null;
  
  let currentPage = 1;
  const itemsPerPage = 10;
  
  $: totalPages = Math.max(1, Math.ceil(generatedHistory.length / itemsPerPage));
  $: paginatedHistory = generatedHistory.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  // Reset to page 1 when history updates and we are out of bounds
  $: {
    if (currentPage > totalPages) {
      currentPage = totalPages;
    }
  }

  function goToPage(page) {
    if (page >= 1 && page <= totalPages) {
      currentPage = page;
    }
  }

  let kbDocuments = [];
  let selectedKbDocId = "";
  
  let projects = [];

  $: skillOptions = skills.length === 0 ? [{value: "", label: "-- ไม่พบ Skill ในระบบ --"}] : skills.map(skill => ({ value: skill.id, label: `${skill.skill_name} (${skill.target_doc_type})` }));
  $: kbDocOptions = [{value: "", label: "-- ไม่ระบุเอกสารอ้างอิง (Use general project knowledge) --"}].concat(kbDocuments.map(doc => ({ value: doc.id, label: `${doc.name} (${doc.doc_category})` })));

  $: {
    if ($selectedProjectStore) {
      fetchKbDocuments($selectedProjectStore.id || $selectedProjectStore.project_id);
      fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
      startPolling();
    } else {
      stopPolling();
    }
  }

  onMount(async () => {
    await fetchSkills();
    await fetchProjects();
  });

  onDestroy(() => {
    stopPolling();
  });

  async function fetchProjects() {
    try {
      const res = await fetch('http://127.0.0.1:5000/api/projects');
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
      }
    } catch(e) {
      console.error('Failed to load projects', e);
    }
  }

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  async function fetchSkills() {
    try {
      const res = await fetch('http://localhost:5000/api/skills');
      const data = await res.json();
      if (res.ok) {
        skills = data.skills || [];
      }
    } catch (e) {
      console.error('Failed to fetch skills:', e);
    }
  }

  async function fetchKbDocuments(projectId) {
    if (!projectId) return;
    try {
      const res = await fetch(`http://localhost:5000/api/kb/documents?project_id=${projectId}`);
      const data = await res.json();
      if (data.success) {
        kbDocuments = data.documents || [];
      } else {
        kbDocuments = [];
      }
    } catch (e) {
      console.error('Failed to fetch kb documents:', e);
      kbDocuments = [];
    }
  }

  async function fetchHistory(projectId) {
    if (!projectId) return;
    try {
      const res = await fetch(`http://localhost:5000/api/agent/generated_documents?project_id=${projectId}`);
      const data = await res.json();
      if (data.success) {
        generatedHistory = data.documents || [];
      }
    } catch (e) {
      console.error('Failed to fetch history:', e);
    }
  }

  function startPolling() {
    stopPolling();
    pollingInterval = setInterval(() => {
      if ($selectedProjectStore) {
        fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
      }
    }, 3000);
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
    }
  }

  // Auto-select a skill if it matches the docType (basic heuristic)
  $: {
    if (docType && skills.length > 0) {
      const matched = skills.find(s => s.target_doc_type === docType || s.skill_name.includes(docType));
      if (matched) {
        selectedSkillId = matched.id;
      } else {
        selectedSkillId = skills[0]?.id || "";
      }
    }
  }

  async function handleGenerate() {
    if (!$selectedProjectStore) {
      toast('Please select a project first from the top navigation.', 'error');
      return;
    }
    if (!docName.trim()) {
      toast('Please enter a Document Name.', 'error');
      return;
    }
    if (!selectedSkillId) {
      toast('Please select an AI Skill.', 'error');
      return;
    }

    isGenerating = true;

    try {
      const payload = {
        project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
        doc_type: docType,
        doc_name: docName,
        skill_id: parseInt(selectedSkillId),
        reference_document_id: selectedKbDocId ? parseInt(selectedKbDocId) : null
      };

      const res = await fetch('http://localhost:5000/api/agent/create_document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        toast('Generation started in background...', 'success');
        fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
        docName = ""; // reset
      } else {
        toast(data.error || 'Failed to start generation.', 'error');
      }
    } catch (e) {
      console.error(e);
      toast('Network error while starting generation.', 'error');
    } finally {
      isGenerating = false;
    }
  }

  function downloadFile(doc) {
    if (doc.status !== 'Completed') return;
    window.location.href = `http://localhost:5000/api/agent/download_generated_document/${doc.id}`;
  }
</script>

<div class="panel-container" in:fade>
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

    <div class="glass-panel">
      <div class="panel-header">
        <h2>QA Document Creation</h2>
        <span class="badge in-progress">AI Generator</span>
      </div>
      <p class="desc-text">สร้างเอกสาร QA อัตโนมัติ (เช่น SRS, Test Case, UAT) โดยอ้างอิงจาก Knowledge Base และ Skill ที่กำหนด</p>

    <div class="form-container">
      <div class="form-group">
        <label for="docName">ชื่อเอกสาร (Document Name):</label>
        <input type="text" id="docName" bind:value={docName} placeholder="เช่น Login Flow Test Cases" class="text-input" />
      </div>

      <div class="form-row">
        <div class="form-group half-width">
          <label for="docType">ประเภทเอกสาร (Document Type):</label>
          <CustomSelect id="docType" bind:value={docType} options={docTypes} />
        </div>

        <div class="form-group half-width">
          <label for="skillSelect">เลือก AI Skill (Framework):</label>
          <CustomSelect id="skillSelect" bind:value={selectedSkillId} options={skillOptions} disabled={skills.length === 0} />
        </div>
      </div>

      <div class="form-group">
        <label for="kbDocSelect">อ้างอิงจากเอกสารในระบบ (Reference Document) - <i>Optional</i>:</label>
        <CustomSelect id="kbDocSelect" bind:value={selectedKbDocId} options={kbDocOptions} disabled={kbDocuments.length === 0} />
      </div>

      <button class="btn-primary" on:click={handleGenerate} disabled={isGenerating || !$selectedProjectStore} style="margin-top: 15px; width: 100%;">
        {#if isGenerating}
          <div class="spinner-small"></div> กำลังสร้างเอกสาร (Generating...)...
        {:else}
          ✨ สร้างเอกสาร (Generate Document)
        {/if}
      </button>
    </div>
    </div>

    <!-- History Table Area -->
    <div class="glass-panel" style="flex: 1; display: flex; flex-direction: column;">
      <div class="panel-header">
        <h3>ประวัติการสร้างเอกสาร (Generation History)</h3>
      </div>
      <div class="table-container">
        <table class="history-table">
          <thead>
            <tr>
              <th>วัน-เวลา</th>
              <th>ชื่อเอกสาร</th>
              <th>ประเภท</th>
              <th>Framework/Skill</th>
              <th>สถานะ</th>
              <th>การกระทำ</th>
            </tr>
          </thead>
          <tbody>
            {#if generatedHistory.length === 0}
              <tr>
                <td colspan="6" style="text-align: center; color: #94a3b8; padding: 20px;">
                  ยังไม่มีประวัติการสร้างเอกสาร
                </td>
              </tr>
            {:else}
              {#each paginatedHistory as doc (doc.id)}
                <tr transition:slide>
                  <td style="color: #94a3b8;">
                    {doc.created_at ? new Date(doc.created_at).toLocaleString('th-TH') : '-'}
                  </td>
                  <td>{doc.doc_name}</td>
                  <td><span class="badge" style="background: rgba(139, 92, 246, 0.2); color: #c4b5fd;">{doc.doc_type}</span></td>
                  <td>{doc.skill_name}</td>
                  <td>
                    {#if doc.status === 'Generating'}
                      <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="spinner-small"></div>
                        <span style="color: #fbbf24;">กำลังวิเคราะห์...</span>
                      </div>
                    {:else if doc.status === 'Completed'}
                      <span style="color: #4ade80;">✅ เสร็จสมบูรณ์</span>
                    {:else if doc.status === 'Failed'}
                      <span style="color: #f87171;">❌ ล้มเหลว</span>
                    {:else}
                      <span>{doc.status}</span>
                    {/if}
                  </td>
                  <td>
                    {#if doc.status === 'Completed'}
                      <button class="btn-secondary btn-sm" on:click={() => downloadFile(doc)}>
                        ⬇️ Download Excel
                      </button>
                    {/if}
                  </td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
      
      {#if totalPages > 1}
        <div class="pagination-controls">
          <button class="btn-page" disabled={currentPage === 1} on:click={() => goToPage(currentPage - 1)}>
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><polyline points="15 18 9 12 15 6"></polyline></svg>
            ก่อนหน้า
          </button>
          <span class="page-info">หน้า {currentPage} จาก {totalPages}</span>
          <button class="btn-page" disabled={currentPage === totalPages} on:click={() => goToPage(currentPage + 1)}>
            ถัดไป
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        </div>
      {/if}
    </div>

  {/if}
</div>

<style>
  .panel-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    height: 100%;
    overflow-y: auto;
    padding: 10px;
  }
  
  .glass-panel {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 24px;
    color: #f8fafc;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  .panel-header h2 {
    margin: 0;
    font-size: 1.5rem;
    color: #f8fafc;
    font-weight: 600;
  }

  .desc-text {
    color: #94a3b8;
    margin-bottom: 24px;
    line-height: 1.5;
  }

  .form-container {
    display: flex;
    flex-direction: column;
    gap: 15px;
    background: rgba(15, 23, 42, 0.5);
    padding: 20px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.05);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-row {
    display: flex;
    gap: 15px;
  }

  .half-width {
    flex: 1;
  }

  label {
    font-size: 0.9rem;
    color: #cbd5e1;
    font-weight: 500;
  }

  .text-input, .select-input {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #334155;
    color: white;
    padding: 10px 12px;
    border-radius: 6px;
    font-size: 0.95rem;
    outline: none;
    transition: all 0.2s;
  }

  .text-input:focus, .select-input:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
  }

  .btn-primary {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    padding: 12px 20px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .btn-primary:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
  }

  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: rgba(51, 65, 85, 0.8);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    transition: all 0.2s;
  }

  .btn-secondary:hover {
    background: rgba(71, 85, 105, 0.9);
  }

  .spinner-small {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: white;
    animation: spin 1s ease-in-out infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .result-container {
    margin-top: 25px;
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid #334155;
    border-radius: 8px;
    overflow: hidden;
  }

  .result-header {
    background: rgba(30, 41, 59, 0.9);
    padding: 12px 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #334155;
  }

  .result-header h3 {
    margin: 0;
    font-size: 1.1rem;
    color: #60a5fa;
  }

  .btn-sm {
    padding: 6px 12px;
    font-size: 13px;
  }

  .table-container {
    overflow-x: auto;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.4);
    flex: 1;
  }

  .history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    color: #e2e8f0;
  }

  .history-table th {
    text-align: left;
    padding: 12px 16px;
    background: rgba(30, 41, 59, 0.8);
    font-weight: 600;
    color: #94a3b8;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    position: sticky;
    top: 0;
  }

  .history-table td {
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .history-table tr:hover {
    background: rgba(255, 255, 255, 0.03);
  }

  .pagination-controls {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 15px;
    margin-top: 15px;
    padding: 10px;
  }

  .btn-page {
    display: flex;
    align-items: center;
    gap: 5px;
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s ease;
  }

  .btn-page:hover:not(:disabled) {
    background: rgba(59, 130, 246, 0.2);
    border-color: rgba(59, 130, 246, 0.5);
    color: #60a5fa;
  }

  .btn-page:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .page-info {
    font-size: 13px;
    color: #94a3b8;
  }
</style>
