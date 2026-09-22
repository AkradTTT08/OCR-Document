<script>
  import { onMount, onDestroy } from 'svelte';
  import { selectedProjectStore } from './qaHistoryStore.js';
  import { toast } from './toastStore.js';
  import { fade, slide } from 'svelte/transition';
  import ProjectSelection from './ProjectSelection.svelte';
  import CustomSelect from './CustomSelect.svelte';

  import { MASTER_DOC_TYPES } from './constants.js';

  let docName = "";
  let docType = "Test Case"; // Default
  let customPrompt = "";
  
  const docTypeMetadata = {
    'Test Case': { label: 'Test Case (แบบทดสอบและกรณีทดสอบ)', icon: '🧪' },
    'SRS': { label: 'SRS (Software Requirements Specification / ข้อกำหนดความต้องการ)', icon: '📝' },
    'SDD': { label: 'SDD (Software Design Document / สถาปัตยกรรมและออกแบบระบบ)', icon: '🏗️' },
    'TOR/SOW': { label: 'TOR / SOW (ขอบเขตงานและข้อกำหนดโครงการ)', icon: '📄' },
    'UAT': { label: 'UAT (User Acceptance Testing / แผนและเกณฑ์การทดสอบยอมรับ)', icon: '✅' },
    'User Manual': { label: 'User Manual (คู่มือการใช้งานสำหรับผู้ใช้ทั่วไป)', icon: '📖' },
    'Admin Manual': { label: 'Admin Manual (คู่มือสำหรับผู้ดูแลระบบ)', icon: '⚙️' },
    'Installation System': { label: 'Installation System (คู่มือการติดตั้งและ Deploy ระบบ)', icon: '💻' },
    'QA Report': { label: 'QA Report (รายงานสรุปผลการทดสอบและการประกันคุณภาพ)', icon: '📊' },
    'Security Plan': { label: 'Security Plan (แผนการทดสอบความปลอดภัย)', icon: '🛡️' },
    'Performance Plan': { label: 'Performance Plan (แผนการทดสอบประสิทธิภาพ)', icon: '⚡' },
    'Project Plan': { label: 'Project Plan (แผนงานโครงการ)', icon: '📅' },
    'Technical Spec': { label: 'Technical Spec (ข้อกำหนดทางเทคนิค)', icon: '📐' },
    'SOP': { label: 'SOP (Standard Operating Procedure)', icon: '📋' },
    'Contract': { label: 'Contract (สัญญาและข้อตกลง)', icon: '📜' },
    'General': { label: 'General (เอกสารทั่วไป)', icon: '📁' }
  };

  $: docTypeOptions = MASTER_DOC_TYPES.map(t => ({
    value: t,
    label: docTypeMetadata[t]?.label || t,
    icon: docTypeMetadata[t]?.icon || '📄'
  }));
  
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

  $: skillOptions = skills.length === 0 ? [{value: "", label: "-- ไม่พบ Skill ในระบบ --"}] : skills.map(skill => ({ value: String(skill.skill_id || skill.id), label: `${skill.skill_name} (${skill.target_doc_type || 'General'})`, icon: '💡' }));
  $: kbDocOptions = [{value: "", label: "-- ไม่ระบุเอกสารอ้างอิง (AI จะดึงเอกสารทั้งหมดใน Knowledge Base ของโครงการมาวิเคราะห์รวมกัน) --", icon: '🌐'}].concat(kbDocuments.map(doc => ({ value: String(doc.doc_id || doc.id), label: `${doc.original_filename || doc.name} (${doc.doc_category || 'General'})`, icon: '📄' })));

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
      const res = await fetch('/api/projects');
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
      const res = await fetch('/api/skills');
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
      const res = await fetch(`/api/kb/documents?project_id=${projectId}`);
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
      const res = await fetch(`/api/agent/generated_documents?project_id=${projectId}`);
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

  // Auto-select matching AI Skill when docType changes
  $: {
    if (docType && skills.length > 0) {
      const cleanDocType = docType.toLowerCase().replace(/[^a-z0-9]/g, '');
      const matched = skills.find(s => {
        const sTarget = (s.target_doc_type || '').toLowerCase().replace(/[^a-z0-9]/g, '');
        const sName = (s.skill_name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
        return sTarget === cleanDocType || sName.includes(cleanDocType) || (cleanDocType === 'testcase' && (sName.includes('test') || sTarget.includes('test')));
      });
      if (matched) {
        selectedSkillId = String(matched.skill_id || matched.id);
      } else if (!selectedSkillId) {
        selectedSkillId = String(skills[0]?.skill_id || skills[0]?.id || "");
      }
    }
  }

  let showSaveModal = false;
  let selectedDocForSave = null;
  let isSavingToProject = false;
  let saveForm = {
    filename: '',
    project_id: '',
    doc_category: 'Reference',
    doc_type: 'Test Case',
    is_golden_data: false
  };

  const categorySelectOptions = [
    { value: 'Reference', label: 'เอกสารอ้างอิง (Reference)', icon: '📑' },
    { value: 'TOR/SOW', label: 'TOR/SOW', icon: '📄' },
    { value: 'SRS', label: 'SRS', icon: '📝' },
    { value: 'SDD', label: 'SDD', icon: '🏗️' },
    { value: 'TestCase', label: 'แบบทดสอบ (TestCase)', icon: '🧪' },
    { value: 'Requirement', label: 'ความต้องการ (Requirement)', icon: '📋' },
    { value: 'UAT', label: 'UAT', icon: '✅' },
    { value: 'Usermanual', label: 'Usermanual', icon: '📖' },
    { value: 'Admin manual', label: 'Admin manual', icon: '⚙️' },
    { value: 'Installation system', label: 'Installation system', icon: '💻' },
    { value: 'QA Generated', label: 'เอกสารจาก QA (QA Generated)', icon: '✨' },
    { value: 'Other', label: 'อื่นๆ (Other)', icon: '📁' }
  ];

  $: projectSelectOptions = projects.map(p => ({
    value: String(p.id || p.project_id || ''),
    label: `${p.project_code ? p.project_code + ' - ' : ''}${p.name || p.project_name || ''}`,
    icon: '📌'
  }));

  function openSaveModal(doc) {
    selectedDocForSave = doc;
    saveForm.filename = `${doc.doc_name}.md`;
    
    // Set default project strictly to currently selected project
    const activeProj = $selectedProjectStore;
    if (activeProj) {
      saveForm.project_id = String(activeProj.id || activeProj.project_id || '');
    } else {
      saveForm.project_id = projects.length > 0 ? String(projects[0].id || projects[0].project_id || '') : '';
    }

    if (doc.doc_type === 'Test Case') {
      saveForm.doc_category = 'TestCase';
    } else if (doc.doc_type === 'SRS' || doc.doc_type === 'Requirement') {
      saveForm.doc_category = 'Requirement';
    } else {
      saveForm.doc_category = 'QA Generated';
    }
    saveForm.doc_type = doc.doc_type || 'Test Case';
    saveForm.is_golden_data = false;
    showSaveModal = true;
  }

  async function handleSaveToProject() {
    if (!saveForm.project_id) {
      toast('กรุณาเลือกโครงการเป้าหมาย', 'warning');
      return;
    }
    if (!saveForm.filename.trim()) {
      toast('กรุณาระบุชื่อไฟล์', 'warning');
      return;
    }

    isSavingToProject = true;
    try {
      const res = await fetch('/api/qa/save_generated_doc', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: saveForm.project_id,
          filename: saveForm.filename.trim(),
          doc_category: saveForm.doc_category,
          doc_type: saveForm.doc_type,
          markdown_content: selectedDocForSave.doc_markdown,
          is_golden_data: saveForm.is_golden_data,
          original_doc_name: selectedDocForSave.doc_name
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(`บันทึกเอกสารเข้า Knowledge Base เรียบร้อยแล้ว (Doc ID: ${data.doc_id})`, 'success', 4000);
        showSaveModal = false;
        selectedDocForSave = null;
        if ($selectedProjectStore && String($selectedProjectStore.id || $selectedProjectStore.project_id) === String(saveForm.project_id)) {
          fetchKbDocuments(saveForm.project_id);
        }
      } else {
        toast(data.error || 'เกิดข้อผิดพลาดในการบันทึกเข้าโครงการ', 'error');
      }
    } catch(err) {
      console.error(err);
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
    } finally {
      isSavingToProject = false;
    }
  }

  async function handleGenerate() {
    if (!docName.trim()) {
      toast('กรุณาระบุชื่อเอกสาร', 'warning');
      return;
    }

    if (!$selectedProjectStore) {
      toast('กรุณาเลือกโครงการก่อนสร้างเอกสาร', 'warning');
      return;
    }

    isGenerating = true;
    try {
      const payload = {
        project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
        doc_type: docType,
        doc_name: docName.trim(),
        skill_id: selectedSkillId || null,
        reference_document_id: selectedKbDocId || null,
        custom_prompt: customPrompt.trim()
      };

      const res = await fetch('/api/agent/create_document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        toast('เริ่มการสร้างเอกสารในเบื้องหลังแล้ว...', 'success');
        fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
        docName = ""; // reset
        customPrompt = ""; // reset
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

  function downloadFile(doc, format = 'pdf') {
    if (doc.status !== 'Completed') return;
    window.location.href = `/api/agent/download_generated_document/${doc.id}?format=${format}`;
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

    <div class="glass-panel form-panel">
      <div class="panel-header">
        <h2>QA Document Creation</h2>
        <span class="badge in-progress">AI Generator</span>
      </div>
      <p class="desc-text">สร้างเอกสาร QA อัจฉริยะ (เช่น SRS, SDD, TOR, Test Case, UAT, คู่มือ) โดย AI จะดึงและวิเคราะห์ข้อมูลทั้งหมดใน Knowledge Base ของโครงการมาประมวลผลรวมกันอย่างแม่นยำ</p>

    <div class="form-container">
      <div class="form-group">
        <label for="docName">ชื่อเอกสาร (Document Name):</label>
        <input type="text" id="docName" bind:value={docName} placeholder="เช่น ระบบสั่งอาหารออนไลน์ - Test Case Suite" class="text-input" />
      </div>

      <div class="form-row">
        <div class="form-group half-width">
          <label for="docType">ประเภทเอกสารที่ต้องการสร้าง (Document Type):</label>
          <CustomSelect id="docType" bind:value={docType} options={docTypeOptions} />
          <span style="font-size: 11px; color: #94a3b8; margin-top: 4px; display: block;">ระบุชนิดเอกสารเพื่อให้ AI หยิบและวิเคราะห์ข้อมูลในโครงการมาสร้างได้อย่างตรงเป้าหมาย</span>
        </div>

        <div class="form-group half-width">
          <label for="skillSelect">เลือก AI Skill (โครงสร้างและแนวทางสร้างเอกสาร):</label>
          <CustomSelect id="skillSelect" bind:value={selectedSkillId} options={skillOptions} disabled={skills.length === 0} />
          <span style="font-size: 11px; color: #94a3b8; margin-top: 4px; display: block;">กำหนดโครงสร้าง, มาตรฐานหัวข้อ, และกรอบการสร้างเอกสาร</span>
        </div>
      </div>

      <div class="form-group" style="z-index: 70;">
        <label for="kbDocSelect">เอกสารอ้างอิงหลักในระบบ (Reference Document) - <i>Optional</i>:</label>
        <CustomSelect id="kbDocSelect" bind:value={selectedKbDocId} options={kbDocOptions} disabled={kbDocuments.length === 0} />
        <span style="font-size: 11px; color: #60a5fa; margin-top: 4px; display: block;">💡 หากไม่ระบุเอกสารอ้างอิง AI จะรวบรวมเอกสารทุกฉบับใน Knowledge Base ของโครงการนี้มาวิเคราะห์ประมวลผลรวมกันทั้งหมด</span>
      </div>

      <div class="form-group">
        <label for="customPrompt">คำสั่งหรือ Prompt เพิ่มเติม (Additional Prompt / Custom Instructions) - <i>Optional</i>:</label>
        <textarea 
          id="customPrompt" 
          bind:value={customPrompt} 
          placeholder="เช่น ระบุเงื่อนไข Edge Cases พิเศษ, เน้นการทดสอบกรณี Error Handling, หรือข้อกำหนดเฉพาะที่ต้องการ..." 
          rows="3" 
          class="text-input custom-prompt-textarea"
        ></textarea>
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
    <div class="glass-panel history-panel" style="flex: 1; display: flex; flex-direction: column;">
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
                      <div class="actions-group">
                        <button class="btn-action btn-pdf" title="ดาวน์โหลดไฟล์ PDF" on:click={() => downloadFile(doc, 'pdf')}>
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M14 14V4.5L9.5 0H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2zM9.5 3A1.5 1.5 0 0 0 11 4.5h2V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h5.5v2z"/>
                            <path d="M4.603 14.087a.81.81 0 0 1-.438-.42c-.195-.388-.13-.776.08-1.102.198-.307.526-.568.897-.787a7.68 7.68 0 0 1 1.482-.645 19.697 19.697 0 0 0 1.062-2.227 7.269 7.269 0 0 1-.43-1.295c-.086-.4-.119-.796-.046-1.136.075-.354.274-.672.65-.823.192-.077.4-.12.602-.077a.7.7 0 0 1 .477.422c.15.347.11.787-.04 1.258a12.57 12.57 0 0 1-1.077 2.192c.383.693.856 1.34 1.378 1.905.787-.197 1.636-.33 2.455-.33.393 0 .762.036 1.06.13.385.12.628.36.7.676.06.27.017.568-.136.837-.183.32-.497.518-.87.59-.444.086-.983-.02-1.572-.27a14.773 14.773 0 0 1-2.025-.99 17.587 17.587 0 0 0-2.474.966 6.883 6.883 0 0 1-1.15.485.81.81 0 0 1-.438-.016z"/>
                          </svg>
                          PDF
                        </button>
                        <button class="btn-action btn-excel" title="ดาวน์โหลดไฟล์ Excel (.xlsx)" on:click={() => downloadFile(doc, 'excel')}>
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M5.884 6.68a.5.5 0 1 0-.768.64L7.349 10l-2.233 2.68a.5.5 0 0 0 .768.64L8 10.748l2.116 2.572a.5.5 0 0 0 .768-.64L8.651 10l2.233-2.68a.5.5 0 0 0-.768-.64L8 9.252 5.884 6.68z"/>
                            <path d="M14 14V4.5L9.5 0H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2zM9.5 3A1.5 1.5 0 0 0 11 4.5h2V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h5.5v2z"/>
                          </svg>
                          Excel
                        </button>
                        {#if doc.is_saved_to_project}
                          <span class="badge-saved" title="เอกสารนี้ถูกบันทึกเข้า Knowledge Base ของโครงการแล้ว">
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" viewBox="0 0 16 16">
                              <path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/>
                            </svg>
                            บันทึกใน Project แล้ว
                          </span>
                        {:else}
                          <button 
                            class="btn-action btn-save-kb" 
                            on:click={() => openSaveModal(doc)}
                            title="บันทึกเอกสารเข้า Knowledge Base ของโครงการ"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" viewBox="0 0 16 16">
                              <path d="M2 1a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1H9.5a1 1 0 0 0-1 1v7.293l2.146-2.147a.5.5 0 0 1 .708.708l-3 3a.5.5 0 0 1-.708 0l-3-3a.5.5 0 1 1 .708-.708L7.5 9.293V2a2 2 0 0 1 2-2H14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2h2.5a.5.5 0 0 1 0 1H2z"/>
                            </svg>
                            บันทึกเข้า Project
                          </button>
                        {/if}
                      </div>
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

<!-- ── Save to Project Modal ── -->
{#if showSaveModal}
  <div class="modal-backdrop" on:click|self={() => showSaveModal = false} in:fade={{ duration: 150 }}>
    <div class="modal-content" on:click|stopPropagation>
      <h3>บันทึกเอกสารเข้า Project</h3>
      
      <div class="form-group">
        <label for="save-filename">ชื่อไฟล์</label>
        <input id="save-filename" type="text" bind:value={saveForm.filename} class="form-input" />
      </div>

      <div class="form-group" style="z-index: 100;">
        <label for="save-project">โครงการ (Project)</label>
        <CustomSelect 
          id="save-project" 
          bind:value={saveForm.project_id} 
          options={projectSelectOptions} 
          width="100%"
        />
      </div>

      <div class="form-group" style="z-index: 90;">
        <label for="save-category">หมวดหมู่เอกสาร</label>
        <CustomSelect 
          id="save-category" 
          bind:value={saveForm.doc_category} 
          options={categorySelectOptions} 
          width="100%"
        />
      </div>

      <div class="form-group toggle-group" style="margin: 16px 0; background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; display: flex; flex-direction: row; justify-content: space-between; align-items: center;">
        <span class="label-text">กำหนดเป็น Golden Data</span>
        <label class="toggle-wrap">
          <input type="checkbox" bind:checked={saveForm.is_golden_data}/>
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
        </label>
      </div>

      <div class="modal-actions">
        <button class="btn-cancel" on:click={() => showSaveModal = false} disabled={isSavingToProject}>ยกเลิก</button>
        <button 
          class="btn-save" 
          on:click={handleSaveModalSubmit} 
          disabled={isSavingToProject || !saveForm.project_id}
        >
          {#if isSavingToProject}
            <span class="spinner-micro"></span> กำลังบันทึก...
          {:else}
            💾 บันทึก
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .panel-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    height: 100%;
    overflow-y: auto;
    padding: 20px 24px;
    max-width: 100%;
    margin: 0;
    width: 100%;
    box-sizing: border-box;
  }
  
  .glass-panel {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 24px;
    color: #f8fafc;
  }

  .form-panel {
    position: relative;
    z-index: 50;
  }

  .history-panel {
    position: relative;
    z-index: 1;
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
    position: relative;
    z-index: 60;
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
    position: relative;
  }

  .form-row {
    display: flex;
    gap: 15px;
    position: relative;
    z-index: 80;
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

  .custom-prompt-textarea {
    width: 100%;
    resize: vertical;
    min-height: 80px;
    font-family: inherit;
    font-size: 0.9rem;
    line-height: 1.5;
    box-sizing: border-box;
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

  .actions-group {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-action {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;
  }

  .btn-pdf {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.35);
    color: #fca5a5;
  }

  .btn-pdf:hover {
    background: rgba(239, 68, 68, 0.25);
    border-color: rgba(239, 68, 68, 0.6);
    color: #ffffff;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
  }

  .btn-excel {
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.35);
    color: #6ee7b7;
  }

  .btn-excel:hover {
    background: rgba(16, 185, 129, 0.25);
    border-color: rgba(16, 185, 129, 0.6);
    color: #ffffff;
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
  }

  .btn-save-kb {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(99, 102, 241, 0.2));
    border-color: rgba(99, 102, 241, 0.4);
    color: #93c5fd;
  }

  .btn-save-kb:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(59, 130, 246, 0.35), rgba(99, 102, 241, 0.35));
    border-color: rgba(99, 102, 241, 0.7);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.35);
  }

  .btn-save-kb:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .badge-saved {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border-radius: 6px;
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.35);
    color: #86efac;
    font-size: 12px;
    font-weight: 500;
  }

  .spinner-micro {
    width: 12px;
    height: 12px;
    border: 2px solid rgba(255,255,255,0.3);
    border-radius: 50%;
    border-top-color: white;
    animation: spin 0.8s linear infinite;
  }

  /* ── Save Modal Styles ── */
  .modal-backdrop {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(10, 15, 30, 0.7);
    backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }

  .modal-content {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 24px;
    width: 420px;
    max-width: 90vw;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
    color: #f8fafc;
  }

  .modal-content h3 {
    margin: 0 0 18px 0;
    font-size: 1.15rem;
    color: #f8fafc;
    font-weight: 600;
  }

  .form-input {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #334155;
    color: white;
    padding: 9px 12px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
    width: 100%;
    box-sizing: border-box;
  }

  .form-input:focus {
    border-color: #3b82f6;
  }

  .toggle-group {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .label-text {
    font-size: 13px;
    color: #cbd5e1;
    font-weight: 500;
  }

  .toggle-wrap { display: flex; align-items: center; cursor: pointer; }
  .toggle-wrap input { display: none; }
  .toggle-track {
    width: 38px; height: 22px; border-radius: 11px;
    background: #334155; border: 1px solid #475569;
    position: relative; transition: all 0.25s;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: #3b82f6; border-color: #3b82f6;
    box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
  }
  .toggle-thumb {
    width: 16px; height: 16px; border-radius: 50%;
    background: #ffffff; position: absolute; top: 2px; left: 2px;
    transition: all 0.25s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb {
    transform: translateX(16px);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
  }

  .btn-cancel {
    background: transparent;
    border: 1px solid #475569;
    color: #94a3b8;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  }

  .btn-cancel:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.05);
    color: #f8fafc;
  }

  .btn-save {
    background: #3b82f6;
    border: none;
    color: white;
    padding: 8px 18px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }

  .btn-save:hover:not(:disabled) {
    background: #2563eb;
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
  }

  .btn-save:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
