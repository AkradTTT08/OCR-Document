<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { selectedProjectStore, qaRefinementFeedback, activeQAContext, activeSidebarGroup } from './qaHistoryStore.js';
  import { toast } from './toastStore.js';
  import { fade, slide, scale } from 'svelte/transition';
  import ProjectSelection from './ProjectSelection.svelte';
  import CustomSelect from './CustomSelect.svelte';
  import CustomMultiSelect from './CustomMultiSelect.svelte';

  import { MASTER_DOC_TYPES } from './constants.js';

  const dispatch = createEventDispatcher();

  let docName = "";
  let docType = "Test Case"; // Default
  let customPrompt = "";
  
  // QA Consult Refinement Feedback State
  let activeFeedback = null;
  let showFindingsDrawer = false;

  $: {
    if ($qaRefinementFeedback && $qaRefinementFeedback !== activeFeedback) {
      activeFeedback = $qaRefinementFeedback;
      applyRefinementFeedback(activeFeedback);
    }
  }

  function applyRefinementFeedback(fb) {
    if (!fb) return;
    
    // 1. Select project if provided
    if (fb.project_id && (!$selectedProjectStore || ($selectedProjectStore.id !== fb.project_id && $selectedProjectStore.project_id !== fb.project_id))) {
      const targetProj = projects.find(p => String(p.id || p.project_id) === String(fb.project_id) || (p.project_code && fb.project_code && p.project_code === fb.project_code));
      if (targetProj) {
        selectedProjectStore.set(targetProj);
      }
    }

    // 2. Set document name and document type
    if (fb.doc_name) {
      docName = fb.doc_name.replace(/^[\[\(].*?[\]\)]\s*/, '').trim();
    }
    if (fb.doc_type && MASTER_DOC_TYPES.includes(fb.doc_type)) {
      docType = fb.doc_type;
    } else if (fb.doc_type) {
      const match = MASTER_DOC_TYPES.find(t => t.toLowerCase() === fb.doc_type.toLowerCase());
      if (match) docType = match;
    }

    // 3. Synthesize structured prompt for AI addressing each specific issue
    const directives = [];
    directives.push(`[🎯 QA Consult Quality Gate Refinement Mode - Mandatory Fix Directives]`);
    directives.push(`เอกสารนี้ได้รับการตรวจประเมินใน QA Consult และพบประเด็นที่ไม่ผ่านเกณฑ์ด้านล่าง คุณต้องปรับปรุงและสร้างเอกสารใหม่ให้สมบูรณ์ 100% ตามข้อเสนอแนะทุกข้อ เพื่อให้ตรวจซ้ำแล้วได้สถานะ PASS:\n`);

    if (fb.findings && fb.findings.length > 0) {
      directives.push(`### รายการข้อผิดพลาดที่พบจาก QA Audit (${fb.findings.length} รายการ):`);
      fb.findings.forEach((f, idx) => {
        directives.push(`${idx + 1}. [${f.check_type || 'Audit'}] ประเด็น: ${f.issue || ''}`);
        if (f.found_incorrect && f.found_incorrect !== '-') {
          directives.push(`   - ข้อความที่ผิดในเอกสารเดิม: "${f.found_incorrect}"`);
        }
        if (f.correct_value && f.correct_value !== '-') {
          directives.push(`   - สิ่งที่ควรเป็น (Standard): ${f.correct_value}`);
        }
        if (f.recommendation && f.recommendation !== '-') {
          directives.push(`   - ข้อเสนอแนะในการแก้ไข (Action): ${f.recommendation}`);
        }
      });
      directives.push('');
    }

    if (fb.exit_criteria_eval && fb.exit_criteria_eval.items) {
      const failedItems = fb.exit_criteria_eval.items.filter(it => it.status === 'FAIL');
      if (failedItems.length > 0) {
        directives.push(`### รายการ Exit Criteria Gate ที่ไม่ผ่าน (${failedItems.length} ข้อ):`);
        failedItems.forEach((it, idx) => {
          directives.push(`${idx + 1}. ข้อตรวจ ${it.item_code} (${it.category}): ${it.question_text}`);
          if (it.target_metric) directives.push(`   - ตัวชี้วัดเป้าหมาย: ${it.target_metric}`);
          if (it.remarks) directives.push(`   - ข้อสังเกตที่ทำให้ไม่ผ่าน: ${it.remarks}`);
        });
        directives.push('');
      }
    }

    directives.push(`### คำสั่งพิเศษสำหรับการสร้างเนื้อหา:`);
    directives.push(`1. ทุก Functional Requirement (REQ-xxx) ต้องระบุ Unhappy Path / Alternate Flows และ Error Handling อย่างชัดเจนครบถ้วน`);
    directives.push(`2. ย้ายรายละเอียดเชิงเทคนิค/SQL/PostGIS Query ออกจากส่วน Requirement ไปไว้ใน System Architecture หรือ Technical Spec แทน`);
    directives.push(`3. สูตรการคำนวณและตัวแปรทั้งหมด (เช่น R, v, C, m) ต้องระบุความหมายและที่มาของค่าคงที่ทุกตัว`);
    directives.push(`4. ปรับเปลี่ยนคำอธิบายเชิงธุรกิจ (Slogan) ให้กลายเป็น Acceptance Criteria ที่วัดผลการทดสอบได้ 100%`);

    customPrompt = directives.join('\n');
    toast(`โหลดข้อมูลข้อผิดพลาด ${fb.findings?.length || 0} ประเด็นเข้าสู่โหมดปรับปรุงเอกสารแล้ว`, 'info', 4000);
  }

  function clearRefinementMode() {
    activeFeedback = null;
    qaRefinementFeedback.set(null);
    customPrompt = "";
    toast('ยกเลิกโหมดปรับปรุงเอกสารแล้ว', 'info');
  }
  
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
  let selectedSkillIds = [];
  
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
  let selectedKbDocIds = [];
  
  let projects = [];

  $: skillOptions = skills.map(skill => ({ 
    value: String(skill.skill_id || skill.id), 
    label: `${skill.skill_name} (${skill.target_doc_type || 'General'})`, 
    icon: '💡' 
  }));
  $: kbDocOptions = kbDocuments.map(doc => ({ 
    value: String(doc.doc_id || doc.id), 
    label: `${doc.original_filename || doc.name} (${doc.doc_category || 'General'})`, 
    icon: '📄' 
  }));

  let lastLoadedProjectId = null;
  $: {
    const currentPId = $selectedProjectStore ? ($selectedProjectStore.id || $selectedProjectStore.project_id) : null;
    if (currentPId) {
      if (currentPId !== lastLoadedProjectId) {
        lastLoadedProjectId = currentPId;
        fetchKbDocuments(currentPId);
        fetchHistory(currentPId);
        startPolling();
      }
    } else {
      lastLoadedProjectId = null;
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
        const hasGenerating = generatedHistory.some(d => d.status === 'Generating');
        if (hasGenerating) {
          fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
        }
      }
    }, 3000);
  }

  function stopPolling() {
    if (pollingInterval) {
      clearInterval(pollingInterval);
      pollingInterval = null;
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
        skill_id: selectedSkillIds,
        reference_document_id: selectedKbDocIds,
        custom_prompt: customPrompt.trim()
      };

      const res = await fetch('/api/agent/create_document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        if (activeFeedback) {
          toast('เริ่มการปรับปรุงและสร้างเอกสารใหม่ในเบื้องหลังเรียบร้อยแล้ว...', 'success', 5000);
        } else {
          toast('เริ่มการสร้างเอกสารในเบื้องหลังแล้ว...', 'success', 4000);
        }
        fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
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

  let isTransferringToQA = false;
  let transferringDocId = null;

  async function sendToQAConsult(doc) {
    if (!doc || doc.status !== 'Completed') return;
    transferringDocId = doc.id;
    isTransferringToQA = true;
    try {
      toast('กำลังดึงไฟล์เอกสารเพื่อส่งต่อไปยัง QA Consult...', 'info', 2000);
      
      const format = (doc.doc_type === 'Test Case' || doc.doc_type === 'TestCase') ? 'excel' : 'pdf';
      const fileExt = format === 'excel' ? 'xlsx' : 'pdf';
      const mimeType = format === 'excel' ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : 'application/pdf';
      
      const res = await fetch(`/api/agent/download_generated_document/${doc.id}?format=${format}`);
      if (!res.ok) {
        throw new Error(`Failed to fetch document file (HTTP ${res.status})`);
      }
      
      const blob = await res.blob();
      const safeName = (doc.doc_name || 'Generated_Document').replace(/[^\w\u0E00-\u0E7F\-. ]/g, '_').trim();
      const fileName = `${safeName}.${fileExt}`;
      const fileObj = new File([blob], fileName, { type: mimeType });

      // Clean group name and group type
      const cleanGName = String(doc.doc_name || 'General').replace(/^\[.*?\]\s*/, '').trim();
      const groupType = doc.doc_type || 'Project Plan';
      
      // Determine project
      const proj = $selectedProjectStore || {
        id: doc.project_id,
        project_id: doc.project_id,
        project_code: doc.project_code || '',
        name: doc.project_name || doc.project_code || 'Project'
      };

      // Set active QA Context with pre-attached file
      activeQAContext.set({
        project: proj,
        group_name: cleanGName,
        group_type: groupType,
        file: fileObj,
        doc_types: doc.doc_type ? [doc.doc_type] : []
      });

      // Also set activeSidebarGroup and selectedProjectStore
      selectedProjectStore.set(proj);
      activeSidebarGroup.set({
        project: proj,
        group_name: cleanGName,
        group_type: groupType,
        project_id: proj.id || proj.project_id
      });

      toast(`โหลดไฟล์ "${fileName}" พร้อมส่งตรวจ QA Consult เรียบร้อยแล้ว`, 'success');
      
      // Dispatch navigate event to App.svelte to switch view
      dispatch('navigate', { view: 'qa_consult' });

    } catch (err) {
      console.error('Error transferring document to QA Consult:', err);
      toast(`ไม่สามารถส่งไฟล์ไป QA Consult ได้: ${err.message}`, 'error');
    } finally {
      isTransferringToQA = false;
      transferringDocId = null;
    }
  }

  async function cancelDocument(doc) {
    if (!doc || !doc.id) return;
    try {
      const res = await fetch(`/api/agent/cancel_generated_document/${doc.id}?action=cancel`, {
        method: 'POST'
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('ยกเลิกการสร้างเอกสารเรียบร้อยแล้ว', 'info');
        doc.status = 'Cancelled';
        generatedHistory = [...generatedHistory];
        if ($selectedProjectStore) {
          fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
        }
      } else {
        toast(data.error || 'ไม่สามารถยกเลิกได้', 'error');
      }
    } catch(err) {
      console.error('Cancel error:', err);
      toast('เกิดข้อผิดพลาดในการส่งคำขอยกเลิก', 'error');
    }
  }

  let showDeleteModal = false;
  let docToDelete = null;
  let isDeleting = false;

  function openDeleteModal(doc) {
    docToDelete = doc;
    showDeleteModal = true;
  }

  function closeDeleteModal(force = false) {
    if (isDeleting && !force) return;
    showDeleteModal = false;
    docToDelete = null;
  }

  async function handleDeleteConfirmed() {
    if (!docToDelete || !docToDelete.id) {
      showDeleteModal = false;
      docToDelete = null;
      return;
    }
    const targetId = docToDelete.id;
    isDeleting = true;
    try {
      const res = await fetch(`/api/agent/delete_generated_document/${targetId}?action=delete`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('ลบรายการเรียบร้อยแล้ว', 'success');
        generatedHistory = generatedHistory.filter(d => d.id !== targetId);
        if ($selectedProjectStore) {
          fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
        }
      } else {
        toast(data.error || 'ไม่สามารถลบรายการได้', 'error');
      }
    } catch(err) {
      console.error('Delete error:', err);
      toast('เกิดข้อผิดพลาดในการลบรายการ', 'error');
    } finally {
      isDeleting = false;
      showDeleteModal = false;
      docToDelete = null;
    }
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

      {#if activeFeedback}
        <div class="refinement-banner" transition:slide>
          <div class="refinement-banner-header">
            <div class="refinement-badge">
              <span class="pulse-dot"></span>
              🎯 โหมดปรับปรุงเอกสารตามผลตรวจ QA Consult
            </div>
            <div class="refinement-actions">
              <button class="btn-findings-toggle" on:click={() => showFindingsDrawer = !showFindingsDrawer}>
                {showFindingsDrawer ? '▲ ซ่อนรายการประเด็น' : `▼ ดูประเด็นข้อผิดพลาด (${activeFeedback.findings?.length || 0} ข้อ)`}
              </button>
              <button class="btn-clear-refine" on:click={clearRefinementMode}>
                ✕ ยกเลิกโหมดนี้
              </button>
            </div>
          </div>
          
          <div class="refinement-banner-body">
            <div class="refinement-info-chip"><strong>📄 เอกสารเดิม:</strong> {activeFeedback.source_filename || activeFeedback.doc_name}</div>
            <div class="refinement-info-chip"><strong>🏷️ ประเภท:</strong> {activeFeedback.doc_type}</div>
            {#if activeFeedback.exit_criteria_eval}
              <div class="refinement-info-chip">
                <strong>📋 Gate ก่อนหน้า:</strong> 
                <span class="refinement-gate-tag status-{(activeFeedback.exit_criteria_eval.status || 'rejected').toLowerCase()}">
                  {activeFeedback.exit_criteria_eval.status} ({activeFeedback.exit_criteria_eval.score_percentage}%)
                </span>
              </div>
            {/if}
          </div>

          {#if showFindingsDrawer && activeFeedback.findings && activeFeedback.findings.length > 0}
            <div class="findings-drawer" transition:slide>
              <div class="findings-drawer-title">📋 รายการข้อบกพร่องที่ต้องแก้ไขในการสร้างครั้งนี้ ({activeFeedback.findings.length} ข้อ):</div>
              <div class="findings-mini-list">
                {#each activeFeedback.findings as f, i}
                  <div class="finding-mini-card sev-{f.severity?.toLowerCase() || 'medium'}">
                    <div class="f-top">
                      <span class="f-num">#{i+1}</span>
                      <span class="f-type">[{f.check_type || 'Audit'}]</span>
                      <span class="f-issue">{f.issue}</span>
                      <span class="f-sev">{f.severity}</span>
                    </div>
                    {#if f.found_incorrect && f.found_incorrect !== '-'}
                      <div class="f-evidence"><span style="color: #f87171;">ข้อความเดิม:</span> {f.found_incorrect}</div>
                    {/if}
                    {#if f.recommendation && f.recommendation !== '-'}
                      <div class="f-rec"><strong>💡 แนวทางแก้ไข:</strong> {f.recommendation}</div>
                    {/if}
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}

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
          <label for="skillSelect">เลือก AI Skill / Framework (เลือกได้มากกว่า 1):</label>
          <CustomMultiSelect 
            id="skillSelect" 
            bind:values={selectedSkillIds} 
            options={skillOptions} 
            placeholder="เลือก AI Skill (เลือกได้มากกว่า 1)..." 
            disabled={skills.length === 0} 
          />
          <span style="font-size: 11px; color: #94a3b8; margin-top: 4px; display: block;">สามารถเลือกหลาย Skill พร้อมกันเพื่อผสาน Framework และโครงสร้างมาตรฐานในการสร้างเอกสาร</span>
        </div>
      </div>

      <div class="form-group" style="z-index: 70;">
        <label for="kbDocSelect">อ้างอิงเอกสารในระบบ (Reference Documents) - <i>Optional (เลือกได้มากกว่า 1)</i>:</label>
        <CustomMultiSelect 
          id="kbDocSelect" 
          bind:values={selectedKbDocIds} 
          options={kbDocOptions} 
          placeholder="เลือกเอกสารอ้างอิง (เลือกได้มากกว่า 1 หรือเว้นว่างเพื่อดึงทั้งหมด)..." 
          disabled={kbDocuments.length === 0} 
        />
        <span style="font-size: 11px; color: #60a5fa; margin-top: 4px; display: block;">💡 เลือกเอกสารเฉพาะที่ต้องการอ้างอิง หรือหากเว้นว่างไว้ AI จะรวบรวมเอกสารทุกฉบับใน Knowledge Base ของโครงการมาวิเคราะห์ร่วมกันทั้งหมด</span>
      </div>

      <div class="form-group">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <label for="customPrompt" style="margin-bottom: 0;">คำสั่งหรือ Prompt เพิ่มเติม (Additional Prompt / Custom Instructions) - <i>Optional</i>:</label>
          {#if customPrompt && customPrompt.trim()}
            <button 
              type="button" 
              on:click={() => customPrompt = ""} 
              style="background: none; border: none; color: #94a3b8; font-size: 11px; cursor: pointer; text-decoration: underline; padding: 0;"
              title="ล้างข้อความในกล่อง Prompt"
            >
              ล้างข้อความ Prompt
            </button>
          {/if}
        </div>
        <textarea 
          id="customPrompt" 
          bind:value={customPrompt} 
          placeholder="เช่น ระบุเงื่อนไข Edge Cases พิเศษ, เน้นการทดสอบกรณี Error Handling, หรือข้อกำหนดเฉพาะที่ต้องการ..." 
          rows={activeFeedback ? 6 : 3} 
          class="text-input custom-prompt-textarea"
        ></textarea>
      </div>

      <button class="btn-primary" class:btn-refine-action={!!activeFeedback} on:click={handleGenerate} disabled={isGenerating || !$selectedProjectStore} style="margin-top: 15px; width: 100%;">
        {#if isGenerating}
          <div class="spinner-small"></div> กำลังสร้างเอกสาร (Generating...)...
        {:else if activeFeedback}
          🔄 ปรับปรุงและสร้างเอกสารใหม่ (Regenerate & Fix Findings)
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
                    {:else if doc.status === 'Cancelled'}
                      <span style="color: #94a3b8;">🚫 ยกเลิกแล้ว</span>
                    {:else if doc.status === 'Failed'}
                      <div style="display: flex; align-items: center; gap: 4px;">
                        <span style="color: #f87171; font-weight: 600;" title={doc.error_message || 'เกิดข้อผิดพลาดในการประมวลผล'}>
                          ❌ ล้มเหลว
                        </span>
                        {#if doc.error_message}
                          <button 
                            style="background: transparent; border: none; color: #fca5a5; cursor: pointer; padding: 2px; font-size: 11px;"
                            title={doc.error_message}
                            on:click={() => toast(`ข้อผิดพลาด: ${doc.error_message}`, 'error', 8000)}
                          >
                            ℹ️
                          </button>
                        {/if}
                      </div>
                    {:else}
                      <span>{doc.status}</span>
                    {/if}
                  </td>
                  <td>
                    <div class="actions-group">
                      {#if doc.status === 'Generating'}
                        <button class="btn-action btn-cancel-action" title="ยกเลิกการวิเคราะห์/สร้างเอกสาร" on:click={() => cancelDocument(doc)}>
                          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
                          </svg>
                          ยกเลิก
                        </button>
                      {:else if doc.status === 'Completed'}
                        {#if doc.doc_type === 'Test Case' || doc.doc_type === 'TestCase'}
                          <button class="btn-action btn-excel" title="ดาวน์โหลดไฟล์ Excel (.xlsx)" on:click={() => downloadFile(doc, 'excel')}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                              <path d="M5.884 6.68a.5.5 0 1 0-.768.64L7.349 10l-2.233 2.68a.5.5 0 0 0 .768.64L8 10.748l2.116 2.572a.5.5 0 0 0 .768-.64L8.651 10l2.233-2.68a.5.5 0 0 0-.768-.64L8 9.252 5.884 6.68z"/>
                              <path d="M14 14V4.5L9.5 0H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2zM9.5 3A1.5 1.5 0 0 0 11 4.5h2V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h5.5v2z"/>
                            </svg>
                            Excel
                          </button>
                        {:else}
                          <button class="btn-action btn-pdf" title="ดาวน์โหลดไฟล์ PDF" on:click={() => downloadFile(doc, 'pdf')}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                              <path d="M14 14V4.5L9.5 0H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2zM9.5 3A1.5 1.5 0 0 0 11 4.5h2V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h5.5v2z"/>
                              <path d="M4.603 14.087a.81.81 0 0 1-.438-.42c-.195-.388-.13-.776.08-1.102.198-.307.526-.568.897-.787a7.68 7.68 0 0 1 1.482-.645 19.697 19.697 0 0 0 1.062-2.227 7.269 7.269 0 0 1-.43-1.295c-.086-.4-.119-.796-.046-1.136.075-.354.274-.672.65-.823.192-.077.4-.12.602-.077a.7.7 0 0 1 .477.422c.15.347.11.787-.04 1.258a12.57 12.57 0 0 1-1.077 2.192c.383.693.856 1.34 1.378 1.905.787-.197 1.636-.33 2.455-.33.393 0 .762.036 1.06.13.385.12.628.36.7.676.06.27.017.568-.136.837-.183.32-.497.518-.87.59-.444.086-.983-.02-1.572-.27a14.773 14.773 0 0 1-2.025-.99 17.587 17.587 0 0 0-2.474.966 6.883 6.883 0 0 1-1.15.485.81.81 0 0 1-.438-.016z"/>
                            </svg>
                            PDF
                          </button>
                        {/if}
                        <button 
                          class="btn-action btn-qa-consult" 
                          title="ส่งไฟล์เอกสารนี้ไปตรวจที่ QA Consult"
                          disabled={isTransferringToQA && transferringDocId === doc.id}
                          on:click={() => sendToQAConsult(doc)}
                        >
                          {#if isTransferringToQA && transferringDocId === doc.id}
                            <div class="spinner-micro"></div>
                            กำลังส่ง...
                          {:else}
                            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
                            </svg>
                            ส่งตรวจ QA
                          {/if}
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
                        <button class="btn-action btn-delete" title="ลบประวัติรายการนี้" on:click={() => openDeleteModal(doc)}>
                          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
                            <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
                          </svg>
                        </button>
                      {:else}
                        <button class="btn-action btn-delete" title="ลบประวัติรายการนี้" on:click={() => openDeleteModal(doc)}>
                          <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
                            <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
                          </svg>
                          ลบ
                        </button>
                      {/if}
                    </div>
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

<!-- ── Delete Confirmation Modal ── -->
{#if showDeleteModal && docToDelete}
  <div class="modal-backdrop" on:click|self={closeDeleteModal} in:fade={{ duration: 150 }}>
    <div class="modal-content modal-delete-content" on:click|stopPropagation in:scale={{ duration: 200, start: 0.95 }}>
      <button class="modal-close-btn" on:click={closeDeleteModal} title="ปิด">✕</button>
      
      <div class="delete-icon-wrapper">
        <div class="delete-icon-pulse"></div>
        <svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" fill="currentColor" viewBox="0 0 16 16" class="delete-svg-icon">
          <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
          <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
        </svg>
      </div>

      <div class="modal-delete-header">
        <h3>ยืนยันการลบเอกสาร</h3>
        <p class="modal-delete-desc">
          คุณแน่ใจหรือไม่ว่าต้องการลบเอกสาร <span class="highlight-docname">"{docToDelete.doc_name}"</span> ออกจากประวัติ?
        </p>
        <div class="modal-delete-subdesc">
          ⚠️ การกระทำนี้ไม่สามารถย้อนกลับได้ และไฟล์ที่สร้างไว้จะถูกลบออกจากระบบ
        </div>
      </div>

      <div class="modal-actions" style="margin-top: 24px; justify-content: center; gap: 12px;">
        <button class="btn-cancel" on:click={closeDeleteModal} disabled={isDeleting}>
          ยกเลิก
        </button>
        <button class="btn-confirm-delete" on:click={handleDeleteConfirmed} disabled={isDeleting}>
          {#if isDeleting}
            <span class="spinner-micro"></span> กำลังลบ...
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
              <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
              <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
            </svg>
            ยืนยันลบเอกสาร
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Save to Project Modal ── -->
{#if showSaveModal}
  <div class="modal-backdrop" on:click|self={() => showSaveModal = false} in:fade={{ duration: 150 }}>
    <div class="modal-content" on:click|stopPropagation in:scale={{ duration: 200, start: 0.95 }}>
      <button class="modal-close-btn" on:click={() => showSaveModal = false} title="ปิด">✕</button>
      
      <div class="modal-title-bar">
        <div class="modal-icon-badge">📁</div>
        <div>
          <h3>บันทึกเอกสารเข้า Project</h3>
          <p class="modal-subtitle">บันทึกเนื้อหาเอกสารเข้าสู่ Knowledge Base ประจำโครงการ</p>
        </div>
      </div>
      
      <div class="form-group" style="margin-top: 16px;">
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

      <div class="form-group toggle-group" style="margin: 16px 0; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); padding: 12px 14px; border-radius: 10px; display: flex; flex-direction: row; justify-content: space-between; align-items: center;">
        <div>
          <span class="label-text" style="font-weight: 600; display: block;">กำหนดเป็น Golden Data</span>
          <span style="font-size: 11.5px; color: #94a3b8;">เอกสารหลักที่มีความน่าเชื่อถือสูงสำหรับ AI ใช้อ้างอิง</span>
        </div>
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
            💾 บันทึกเข้า Project
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

  .btn-cancel-action {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    color: #fca5a5;
  }

  .btn-cancel-action:hover {
    background: rgba(239, 68, 68, 0.3);
    border-color: rgba(239, 68, 68, 0.7);
    color: #ffffff;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.35);
  }

  .btn-delete {
    background: rgba(148, 163, 184, 0.1);
    border-color: rgba(148, 163, 184, 0.2);
    color: #94a3b8;
    padding: 6px 9px;
  }

  .btn-delete:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.5);
    color: #fca5a5;
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.25);
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

  .btn-qa-consult {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.18), rgba(99, 102, 241, 0.22));
    border-color: rgba(168, 85, 247, 0.45);
    color: #d8b4fe;
    font-weight: 500;
  }

  .btn-qa-consult:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.38), rgba(99, 102, 241, 0.42));
    border-color: rgba(168, 85, 247, 0.8);
    color: #ffffff;
    box-shadow: 0 0 14px rgba(168, 85, 247, 0.38);
    transform: translateY(-1px);
  }

  .btn-qa-consult:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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

  /* ── Modal Backdrop & Card Styles ── */
  .modal-backdrop {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(8, 12, 22, 0.75);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    padding: 20px;
  }

  .modal-content {
    background: linear-gradient(145deg, #111827 0%, #0b0f19 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 26px 28px;
    width: 440px;
    max-width: 92vw;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 30px rgba(59, 130, 246, 0.1);
    color: #f8fafc;
    position: relative;
    box-sizing: border-box;
  }

  .modal-close-btn {
    position: absolute;
    top: 16px;
    right: 16px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .modal-close-btn:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.4);
    color: #fca5a5;
  }

  .modal-title-bar {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 18px;
  }

  .modal-icon-badge {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
  }

  .modal-title-bar h3 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 600;
    color: #f8fafc;
  }

  .modal-subtitle {
    margin: 4px 0 0 0;
    font-size: 12.5px;
    color: #94a3b8;
    line-height: 1.4;
  }

  /* ── Delete Modal Styles ── */
  .modal-delete-content {
    width: 420px;
    text-align: center;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.75), 0 0 35px rgba(239, 68, 68, 0.18);
    border-color: rgba(239, 68, 68, 0.3);
  }

  .delete-icon-wrapper {
    position: relative;
    width: 60px;
    height: 60px;
    margin: 4px auto 16px auto;
    border-radius: 50%;
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ef4444;
  }

  .delete-icon-pulse {
    position: absolute;
    inset: -5px;
    border-radius: 50%;
    border: 2px solid rgba(239, 68, 68, 0.25);
    animation: pulse-ring 2s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
  }

  @keyframes pulse-ring {
    0% { transform: scale(0.95); opacity: 0.8; }
    50% { transform: scale(1.12); opacity: 0.2; }
    100% { transform: scale(0.95); opacity: 0.8; }
  }

  .modal-delete-header h3 {
    margin: 0 0 10px 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: #f8fafc;
  }

  .modal-delete-desc {
    font-size: 14px;
    color: #cbd5e1;
    margin: 0 0 12px 0;
    line-height: 1.5;
  }

  .highlight-docname {
    font-weight: 600;
    color: #fca5a5;
    background: rgba(239, 68, 68, 0.15);
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid rgba(239, 68, 68, 0.25);
    word-break: break-word;
  }

  .modal-delete-subdesc {
    font-size: 12px;
    color: #fca5a5;
    margin: 0;
    background: rgba(239, 68, 68, 0.08);
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid rgba(239, 68, 68, 0.18);
    line-height: 1.4;
  }

  .btn-confirm-delete {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    border: 1px solid rgba(239, 68, 68, 0.6);
    color: #ffffff;
    padding: 9px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.4);
  }

  .btn-confirm-delete:hover:not(:disabled) {
    background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%);
    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.55);
    transform: translateY(-1px);
  }

  .btn-confirm-delete:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 8px 18px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  }

  .btn-cancel:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.25);
  }

  .btn-save {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    border: 1px solid rgba(59, 130, 246, 0.5);
    color: white;
    padding: 8px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
  }

  .btn-save:hover:not(:disabled) {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    box-shadow: 0 6px 18px rgba(59, 130, 246, 0.5);
    transform: translateY(-1px);
  }

  .btn-save:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Refinement Mode Styles */
  .refinement-banner {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(236, 72, 153, 0.15) 50%, rgba(139, 92, 246, 0.12) 100%);
    border: 1.5px solid rgba(245, 158, 11, 0.4);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 22px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.15);
  }

  .refinement-banner-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 12px;
  }

  .refinement-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 700;
    color: #fde047;
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
  }

  .pulse-dot {
    width: 10px;
    height: 10px;
    background: #f59e0b;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 10px #f59e0b;
    animation: pulseDot 1.5s infinite;
  }

  @keyframes pulseDot {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.4); opacity: 0.6; }
  }

  .refinement-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-findings-toggle {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #f1f5f9;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-findings-toggle:hover {
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
  }

  .btn-clear-refine {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #fca5a5;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-clear-refine:hover {
    background: #ef4444;
    color: #ffffff;
    border-color: transparent;
  }

  .refinement-banner-body {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 12.5px;
    color: #cbd5e1;
  }

  .refinement-info-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(15, 23, 42, 0.6);
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .refinement-gate-tag {
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    text-transform: uppercase;
  }
  .refinement-gate-tag.status-rejected { background: #fee2e2; color: #b91c1c; }
  .refinement-gate-tag.status-conditional_passed { background: #fef3c7; color: #b45309; }
  .refinement-gate-tag.status-passed { background: #dcfce7; color: #15803d; }

  .findings-drawer {
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px dashed rgba(245, 158, 11, 0.3);
  }

  .findings-drawer-title {
    font-size: 12px;
    font-weight: 700;
    color: #fde047;
    margin-bottom: 10px;
  }

  .findings-mini-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 240px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .finding-mini-card {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
  }
  .finding-mini-card.sev-critical { border-left: 4px solid #ef4444; }
  .finding-mini-card.sev-high { border-left: 4px solid #f97316; }
  .finding-mini-card.sev-medium { border-left: 4px solid #eab308; }
  .finding-mini-card.sev-low { border-left: 4px solid #3b82f6; }

  .f-top {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }
  .f-num { color: #94a3b8; font-weight: 700; }
  .f-type { color: #a78bfa; font-weight: 600; font-size: 11px; }
  .f-issue { color: #f8fafc; font-weight: 600; flex: 1; }
  .f-sev {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.1);
  }
  .f-evidence {
    color: #94a3b8;
    font-size: 11px;
    margin-bottom: 4px;
    padding-left: 20px;
  }
  .f-rec {
    color: #38bdf8;
    font-size: 11.5px;
    padding-left: 20px;
  }

  .btn-refine-action {
    background: linear-gradient(135deg, #f59e0b 0%, #ec4899 50%, #8b5cf6 100%) !important;
    box-shadow: 0 4px 18px rgba(236, 72, 153, 0.5) !important;
    font-weight: 700 !important;
  }
  .btn-refine-action:hover:not(:disabled) {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 24px rgba(236, 72, 153, 0.7) !important;
  }
</style>
