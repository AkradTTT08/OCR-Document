<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { selectedProjectStore, qaRefinementFeedback, activeQAContext, activeSidebarGroup, allGroups } from './qaHistoryStore.js';
  import { toast } from './toastStore.js';
  import { fade, slide, scale } from 'svelte/transition';
  import ProjectSelection from './ProjectSelection.svelte';
  import CustomSelect from './CustomSelect.svelte';
  import CustomMultiSelect from './CustomMultiSelect.svelte';

  import { MASTER_DOC_TYPES } from './constants.js';

  const dispatch = createEventDispatcher();

  let panelContainerEl;
  let docName = "";
  let docType = "Test Case"; // Default
  let customPrompt = "";
  let refinementDirectives = "";
  let showOptionalSettings = false;
  let isFormCollapsed = false;
  let recentlyCreatedId = null;

  // History Search & Filter State
  let historySearch = "";
  let historyFilter = "all"; // 'all' | 'passed' | 'issues' | 'unscanned' | 'generating'

  // Error Details Modal State
  let showErrorModal = false;
  let selectedDocForError = null;
  
  // QA Consult Refinement Feedback State
  let activeFeedback = null;
  let sourceGroupName = "";
  let sourceGroupType = "";
  let sourceRawMarkdown = "";
  let sourceDocId = null;
  let showFindingsDrawer = false;

  $: {
    if ($qaRefinementFeedback && $qaRefinementFeedback !== activeFeedback) {
      activeFeedback = $qaRefinementFeedback;
      applyRefinementFeedback(activeFeedback);
    }
  }

  function applyRefinementFeedback(fb) {
    if (!fb) return;
    isFormCollapsed = false;
    
    // 1. Select project if provided
    if (fb.project_id && (!$selectedProjectStore || ($selectedProjectStore.id !== fb.project_id && $selectedProjectStore.project_id !== fb.project_id))) {
      const targetProj = projects.find(p => String(p.id || p.project_id) === String(fb.project_id) || (p.project_code && fb.project_code && p.project_code === fb.project_code));
      if (targetProj) {
        selectedProjectStore.set(targetProj);
      }
    }

    // 2. Set document name, type, source group, source doc ID, and baseline content
    if (fb.doc_name) {
      docName = fb.doc_name.replace(/^[\[\(].*?[\]\)]\s*/, '').trim();
    }
    if (fb.group_name) {
      sourceGroupName = fb.group_name.replace(/^[\[\(].*?[\]\)]\s*/, '').trim();
    }
    if (fb.group_type) {
      sourceGroupType = fb.group_type;
    }
    sourceDocId = fb.source_doc_id || null;
    if (fb.raw_markdown) {
      sourceRawMarkdown = fb.raw_markdown;
    } else if (fb.source_markdown) {
      sourceRawMarkdown = fb.source_markdown;
    } else if (fb.source_text) {
      sourceRawMarkdown = fb.source_text;
    }
    // Keep AI Skill optional: pre-fill only if explicitly passed, otherwise leave empty so user can optionally pick a template Skill
    if (Array.isArray(fb.skill_ids) && fb.skill_ids.length > 0) {
      selectedSkillIds = [...fb.skill_ids];
    } else {
      selectedSkillIds = [];
    }

    // Deduce Document Type intelligently from doc_type, group_type, or docName
    let resolvedDocType = "";
    const candidateTypes = [fb.doc_type, fb.group_type, sourceGroupType].filter(Boolean);
    for (const cand of candidateTypes) {
      if (MASTER_DOC_TYPES.includes(cand)) {
        resolvedDocType = cand;
        break;
      }
      const match = MASTER_DOC_TYPES.find(t => t.toLowerCase() === String(cand).toLowerCase());
      if (match) {
        resolvedDocType = match;
        break;
      }
    }

    if (!resolvedDocType) {
      const combinedName = `${docName} ${fb.source_filename || ''}`.toUpperCase();
      const detected = MASTER_DOC_TYPES.find(t => {
        const upperT = t.toUpperCase();
        return combinedName.startsWith(upperT) || 
               combinedName.includes(` ${upperT} `) || 
               combinedName.includes(`_${upperT}_`) || 
               combinedName.includes(`-${upperT}-`) || 
               combinedName.includes(`[${upperT}]`) ||
               combinedName.includes(`_${upperT}`) ||
               combinedName.includes(`${upperT}_`);
      });
      if (detected) resolvedDocType = detected;
    }

    if (resolvedDocType) {
      docType = resolvedDocType;
    }

    // 3. Build structured system refinement directives (locked separately from user's editable customPrompt)
    const directives = [];
    directives.push(`[QA Consult Quality Gate Refinement Mode - Mandatory Fix Directives]`);
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

    directives.push(`### ข้อกำหนดบังคับในการสร้างเอกสารรอบนี้เพื่อรับประกันว่าต้องผ่าน 100% (PASS Quality Gate):`);
    directives.push(`1. [แก้ทุกข้อผิดพลาด 100%]: นำรายการประเด็นข้อผิดพลาดทั้ง ${fb.findings?.length || 0} ข้อด้านบนไปแก้ไข ปรับปรุง และเติมเต็มลงในเนื้อหาเอกสารให้ครบถ้วนทุกจุด ห้ามตกหล่น`);
    directives.push(`2. [รักษาขอบเขตโครงการอย่างเคร่งครัด (Strict Project Isolation)]: ต้องสร้างเนื้อหา ขอบเขต และฟังก์ชันการทำงานเฉพาะของโครงการนี้ตาม Knowledge Base เท่านั้น ห้ามนำฟีเจอร์หรือข้อกำหนดของโครงการอื่นที่ไม่เกี่ยวข้องมารวมในเอกสารฉบับนี้โดยเด็ดขาด`);

    if (docType === 'Test Case') {
      directives.push(`3. [โครงสร้าง Test Case มาตรฐาน]: ทุกกรณีทดสอบต้องระบุข้อมูลครบถ้วน: รหัสทดสอบ (Test Case ID), ชื่อกรณีทดสอบ (Test Scenario), เงื่อนไขเริ่มต้น (Pre-conditions), ขั้นตอนการทดสอบ (Test Steps), ข้อมูลทดสอบ (Test Data), ผลลัพธ์ที่คาดหวัง (Expected Results), และเกณฑ์การยอมรับ (Acceptance Criteria Given... When... Then...) ให้ชัดเจน`);
      directives.push(`4. [ครอบคลุมทั้งกรณีปกติและกรณีผิดพลาด]: ทดสอบทั้ง Happy Path และ Unhappy Path / Exception Handling (กรณีข้อมูลผิดพลาด, การตรวจสอบสิทธิ์, และข้อความแจ้งเตือนผู้ใช้)`);
      directives.push(`5. [ตาราง Document Control & Revision History]: มีตาราง 1.1 Document Control และตาราง 1.2 Revision History & Audit Resolution Log บันทึกว่าเวอร์ชันนี้เป็นฉบับปรับปรุงที่ได้แก้ไขข้อผิดพลาดเรียบร้อยแล้ว`);
      directives.push(`6. [โหมดผ่าตัดแก้ไข]: คงกรณีทดสอบเดิมที่ถูกต้องไว้ทั้งหมด 100% และปรับปรุงเฉพาะจุดที่มีข้อผิดพลาด`);
    } else {
      directives.push(`3. [โครงสร้าง Requirement ทุกข้อ]: ทุกรหัส Requirement ต้องระบุข้อมูลครบถ้วนบริบูรณ์: วัตถุประสงค์ (Objective), กลุ่มผู้ใช้ (Actor), Pre-conditions และ Post-conditions, ขั้นตอนปกติ (Happy Path), ขั้นตอนกรณีผิดพลาด (Unhappy Path & Error Handling), และเกณฑ์การยอมรับ (Acceptance Criteria Given... When... Then...) ในตารางให้ชัดเจน`);
      directives.push(`4. [Section 1 ข้อมูลทั่วไป & Section 1.2 Revision History]:`);
      directives.push(`   - มีตาราง 1.1 Document Control: ระบุ Document Title, Version (เช่น Version 1.1.0), Project Name, Project Code, Baseline Date, Author, วัตถุประสงค์, และขอบเขตระบบ`);
      directives.push(`   - มีตาราง 1.2 Revision History & Audit Resolution Log: บันทึกว่าเวอร์ชันนี้เป็นฉบับปรับปรุงที่ได้แก้ไขประเด็นข้อสั่งการระดับ Critical/High จากรอบก่อนหน้าเรียบร้อยแล้ว 100% ตามข้อเสนอแนะ ห้ามตัดจบตาราง`);
      directives.push(`5. [Section 4 Non-Functional Requirements]: ต้องมีหมวด Section 4 Non-Functional Requirements สมบูรณ์ครบทุกหัวข้อ (Performance, Security, Reliability & Availability >= 99.9%, Compatibility)`);
      directives.push(`6. [โหมดผ่าตัดแก้ไข]: คงเนื้อหาและ Requirement เดิมที่ถูกต้องไว้ทั้งหมด 100% ห้ามตัดทอนออก`);
    }

    refinementDirectives = directives.join('\n');
    customPrompt = "";
    toast(`โหลดข้อผิดพลาด ${fb.findings?.length || 0} ประเด็นเข้าสู่โหมดปรับปรุงเอกสารแล้ว`, 'info', 4000);
  }

  function clearRefinementMode() {
    activeFeedback = null;
    sourceGroupName = "";
    sourceGroupType = "";
    sourceRawMarkdown = "";
    sourceDocId = null;
    refinementDirectives = "";
    qaRefinementFeedback.set(null);
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

  $: historyCounts = {
    all: generatedHistory.length,
    passed: generatedHistory.filter(d => d.qa_status === 'PASSED').length,
    issues: generatedHistory.filter(d => d.qa_status === 'REJECTED' || d.qa_status === 'CONDITIONAL_PASSED' || (d.qa_findings_count && d.qa_findings_count > 0)).length,
    unscanned: generatedHistory.filter(d => d.status === 'Completed' && !d.qa_status).length,
    generating: generatedHistory.filter(d => d.status === 'Generating' || d.qa_status === 'Scanning').length
  };

  $: filteredHistory = generatedHistory.filter(d => {
    const q = historySearch.trim().toLowerCase();
    if (q) {
      const hay = `${d.doc_name || ''} ${d.doc_type || ''} ${d.skill_name || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (historyFilter === 'passed') return d.qa_status === 'PASSED';
    if (historyFilter === 'issues') return d.qa_status === 'REJECTED' || d.qa_status === 'CONDITIONAL_PASSED' || (d.qa_findings_count && d.qa_findings_count > 0);
    if (historyFilter === 'unscanned') return d.status === 'Completed' && !d.qa_status;
    if (historyFilter === 'generating') return d.status === 'Generating' || d.qa_status === 'Scanning';
    return true;
  });
  
  $: totalPages = Math.max(1, Math.ceil(filteredHistory.length / itemsPerPage));
  $: paginatedHistory = filteredHistory.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

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
    label: `${skill.skill_name} (${skill.target_doc_type || 'General'})`
  }));
  $: kbDocOptions = kbDocuments.map(doc => ({ 
    value: String(doc.doc_id || doc.id), 
    label: `${doc.original_filename || doc.name} (${doc.doc_category || 'General'})`
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
      const res = await fetch('/api/skills?active_only=true');
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
        const hasActiveJob = generatedHistory.some(d => d.status === 'Generating' || d.qa_status === 'Scanning');
        if (hasActiveJob) {
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
  let saveFilename = '';
  let saveProjectId = '';
  let saveDocCategory = 'TestCase';
  let saveDocType = 'Test Case';
  let saveIsGoldenData = false;

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
    value: String(p.project_id || p.id || ''),
    label: `${p.project_code ? p.project_code + ' - ' : ''}${p.project_name || p.name || ''}`,
    icon: '📌'
  }));

  async function openSaveModal(doc) {
    if (!doc) {
      toast('ไม่พบข้อมูลเอกสาร', 'error');
      return;
    }
    selectedDocForSave = doc;
    saveFilename = `${doc.doc_name || 'Document'}.md`;

    if (!projects || projects.length === 0) {
      await fetchProjects();
    }
    
    // Set default project strictly: current store -> doc.project_id -> first available project
    const activeProj = $selectedProjectStore;
    if (activeProj && (activeProj.id || activeProj.project_id)) {
      saveProjectId = String(activeProj.id || activeProj.project_id);
    } else if (doc.project_id) {
      saveProjectId = String(doc.project_id);
    } else if (projects.length > 0) {
      saveProjectId = String(projects[0].project_id || projects[0].id || '');
    } else {
      saveProjectId = '';
    }

    if (doc.doc_type === 'Test Case') {
      saveDocCategory = 'TestCase';
    } else if (doc.doc_type === 'SRS' || doc.doc_type === 'Requirement') {
      saveDocCategory = 'Requirement';
    } else {
      saveDocCategory = 'QA Generated';
    }
    saveDocType = doc.doc_type || 'Test Case';
    saveIsGoldenData = false;
    showSaveModal = true;
  }

  async function handleSaveToProject() {
    if (!saveProjectId) {
      toast('กรุณาเลือกโครงการเป้าหมาย', 'warning');
      return;
    }
    if (!saveFilename || !saveFilename.trim()) {
      toast('กรุณาระบุชื่อไฟล์', 'warning');
      return;
    }
    if (!selectedDocForSave) {
      toast('ไม่พบข้อมูลเอกสารที่ต้องการบันทึก', 'error');
      return;
    }

    isSavingToProject = true;
    try {
      const payload = {
        doc_id: selectedDocForSave.id,
        project_id: saveProjectId,
        filename: saveFilename.trim(),
        doc_category: saveDocCategory,
        doc_type: saveDocType,
        markdown_content: selectedDocForSave.doc_markdown || selectedDocForSave.markdown_content || '',
        is_golden_data: Boolean(saveIsGoldenData),
        original_doc_name: selectedDocForSave.doc_name
      };

      const res = await fetch('/api/agent/save_generated_doc_to_project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        toast(`บันทึกเอกสารเข้า Knowledge Base เรียบร้อยแล้ว`, 'success', 4000);
        showSaveModal = false;
        
        // Update local document status in generatedHistory
        if (selectedDocForSave && selectedDocForSave.id) {
          const savedId = selectedDocForSave.id;
          generatedHistory = generatedHistory.map(d => 
            d.id === savedId ? { ...d, is_saved_to_project: true, saved_doc_id: data.doc_id } : d
          );
        }
        selectedDocForSave = null;

        if ($selectedProjectStore && String($selectedProjectStore.id || $selectedProjectStore.project_id) === String(saveProjectId)) {
          fetchKbDocuments(saveProjectId);
        }
      } else {
        toast(data.error || 'เกิดข้อผิดพลาดในการบันทึกเข้าโครงการ', 'error');
      }
    } catch(err) {
      console.error('[handleSaveToProject] Request error:', err);
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
    } finally {
      isSavingToProject = false;
    }
  }

  const handleSaveModalSubmit = handleSaveToProject;

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
      const resolvedGroupName = sourceGroupName || ($activeSidebarGroup && $activeSidebarGroup.group_name) || "";
      const resolvedGroupType = sourceGroupType || ($activeSidebarGroup && $activeSidebarGroup.group_type) || docType;

      const token = (typeof window !== 'undefined' && window.localStorage) ? (localStorage.getItem('jwt_token') || '') : '';
      const currentUsername = (typeof window !== 'undefined' && window.localStorage) ? (localStorage.getItem('auth_user') || '') : '';

      // AI Skill is optional in BOTH Normal Mode and Refinement Mode (user may choose a Skill to align structure/template or leave blank)
      const effectiveSkillIds = selectedSkillIds || [];

      // Merge locked refinement directives with user's optional additional prompt
      const combinedPrompt = [refinementDirectives.trim(), customPrompt.trim()].filter(Boolean).join('\n\n');

      const payload = {
        project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
        doc_type: docType,
        doc_name: docName.trim(),
        skill_id: effectiveSkillIds,
        reference_document_id: selectedKbDocIds,
        custom_prompt: combinedPrompt,
        source_markdown: sourceRawMarkdown,
        source_doc_id: sourceDocId,
        group_name: resolvedGroupName,
        group_type: resolvedGroupType,
        username: currentUsername
      };

      const headers = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const res = await fetch('/api/agent/create_document', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        currentPage = 1;
        historyFilter = 'all';
        historySearch = '';
        recentlyCreatedId = data.id || null;
        setTimeout(() => { recentlyCreatedId = null; }, 6000);

        if (activeFeedback) {
          toast('เริ่มการปรับปรุงและสร้างเอกสารใหม่ในเบื้องหลังแล้ว', 'success', 4500);
          clearRefinementMode();
        } else {
          toast('เริ่มการสร้างเอกสารในเบื้องหลังแล้ว', 'success', 4000);
        }
        docName = "";
        fetchHistory($selectedProjectStore.id || $selectedProjectStore.project_id);
      } else {
        toast(data.error || 'ไม่สามารถเริ่มการสร้างเอกสารได้', 'error');
      }
    } catch (e) {
      console.error(e);
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
    } finally {
      isGenerating = false;
    }
  }

  function openErrorModal(doc) {
    selectedDocForError = doc;
    showErrorModal = true;
  }

  function closeErrorModal() {
    showErrorModal = false;
    selectedDocForError = null;
  }

  async function copyErrorText() {
    if (!selectedDocForError?.error_message) return;
    try {
      await navigator.clipboard.writeText(selectedDocForError.error_message);
      toast('คัดลอกข้อความข้อผิดพลาดแล้ว', 'success');
    } catch {
      toast('ไม่สามารถคัดลอกข้อความได้', 'error');
    }
  }

  function retryFailedDoc(doc) {
    if (!doc) return;
    docName = doc.doc_name || '';
    if (doc.doc_type && MASTER_DOC_TYPES.includes(doc.doc_type)) {
      docType = doc.doc_type;
    }
    isFormCollapsed = false;
    closeErrorModal();
    panelContainerEl?.scrollTo({ top: 0, behavior: 'smooth' });
    toast(`นำข้อมูล "${doc.doc_name}" กลับเข้าฟอร์มแล้ว กดสร้างเอกสารเพื่อลองใหม่`, 'info', 4000);
  }

  function handleGlobalKeydown(e) {
    if (e.key === 'Escape') {
      if (showErrorModal) { closeErrorModal(); return; }
      if (showFindingsModal) { closeFindingsModal(); return; }
      if (showSaveModal && !isSavingToProject) { showSaveModal = false; return; }
      if (showDeleteModal && !isDeleting) { closeDeleteModal(); return; }
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

      // Determine project
      const proj = $selectedProjectStore || {
        id: doc.project_id,
        project_id: doc.project_id,
        project_code: doc.project_code || '',
        name: doc.project_name || doc.project_code || 'Project'
      };
      const pId = String(proj.id || proj.project_id || '');
      const projName = proj.project_code || proj.name || 'Project';

      // Determine target group & group type (preserves existing group, never uses filename as group name)
      let targetGroupType = doc.group_type || (activeFeedback && activeFeedback.group_type) || doc.doc_type || 'SRS';
      let targetGroupName = doc.group_name || (activeFeedback && activeFeedback.group_name) || sourceGroupName || ($activeSidebarGroup && $activeSidebarGroup.group_name) || '';

      // If no explicit group name, look up existing group in project matching targetGroupType
      if (!targetGroupName) {
        const matched = ($allGroups || []).find(g => 
          String(g.project_id || '') === pId && 
          String(g.group_type || '').toLowerCase() === String(targetGroupType).toLowerCase()
        );
        if (matched && matched.group_name) {
          targetGroupName = matched.group_name;
          targetGroupType = matched.group_type || targetGroupType;
        } else {
          targetGroupName = `${targetGroupType} - ${projName}`;
        }
      }

      // Clean group name
      const cleanGName = String(targetGroupName).replace(/^\[.*?\]\s*/, '').trim();

      // AI Skill selection is optional - do NOT force or carry over old skill when transferring to QA Consult
      let targetSkillIds = [];
      if (selectedSkillIds && selectedSkillIds.length > 0) {
        targetSkillIds = [...selectedSkillIds];
      }

      // Set active QA Context with pre-attached file and exact source_generated_doc_id for 1-to-1 status sync
      activeQAContext.set({
        project: proj,
        group_name: cleanGName,
        group_type: targetGroupType,
        file: fileObj,
        doc_types: doc.doc_type ? [doc.doc_type] : [targetGroupType],
        skill_ids: targetSkillIds,
        source_generated_doc_id: doc.id
      });

      // Also set activeSidebarGroup and selectedProjectStore
      selectedProjectStore.set(proj);
      activeSidebarGroup.set({
        project: proj,
        group_name: cleanGName,
        group_type: targetGroupType,
        project_id: proj.id || proj.project_id
      });

      // Mark document as Scanning immediately (send doc_id matching backend contract)
      doc.qa_status = 'Scanning';
      generatedHistory = [...generatedHistory];
      fetch('/api/agent/mark_document_scanning', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: doc.id, id: doc.id, doc_name: doc.doc_name })
      }).catch(e => console.error('Failed to mark document scanning:', e));

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

  let showFindingsModal = false;
  let selectedDocForFindings = null;

  function openFindingsModal(doc) {
    selectedDocForFindings = doc;
    showFindingsModal = true;
  }

  function closeFindingsModal() {
    showFindingsModal = false;
    selectedDocForFindings = null;
  }

  function applyDocFindingsToRefinement(doc) {
    if (!doc) return;
    const fList = doc.qa_findings || [];
    const nextVersionName = doc.doc_name
      ? (/_v(\d+)$/i.test(doc.doc_name)
          ? doc.doc_name.replace(/_v(\d+)$/i, (_, n) => `_v${Number(n) + 1}`)
          : `${doc.doc_name}_v2`)
      : docName;
    const feedbackObj = {
      project_id: doc.project_id,
      doc_name: nextVersionName,
      doc_type: doc.doc_type,
      findings: fList,
      exit_criteria_eval: {
        status: doc.qa_status || (fList.length > 0 ? 'REJECTED' : 'PASSED'),
        score_percentage: doc.qa_score ?? 0
      },
      source_doc_id: doc.id,
      raw_markdown: doc.markdown_content || '',
      source_filename: `${doc.doc_name}.${(doc.doc_type === 'Test Case' || doc.doc_type === 'TestCase') ? 'xlsx' : 'pdf'}`,
      group_name: doc.group_name,
      group_type: doc.group_type
    };

    qaRefinementFeedback.set(feedbackObj);
    activeFeedback = feedbackObj;
    applyRefinementFeedback(feedbackObj);
    closeFindingsModal();
    panelContainerEl?.scrollTo({ top: 0, behavior: 'smooth' });
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

<svelte:window on:keydown={handleGlobalKeydown} />

<div class="panel-container" bind:this={panelContainerEl} in:fade>
  {#if !$selectedProjectStore}
    <ProjectSelection 
      {projects} 
      on:select={(e) => selectProject(e.detail)} 
    />
  {:else}
    <div class="top-nav-bar">
      <button type="button" class="btn-back" on:click={() => selectedProjectStore.set(null)}>
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
        <span>ย้อนกลับไปหน้าเลือกโครงการ</span>
      </button>

      <div class="active-project-pill" title="โครงการที่กำลังทำงานอยู่">
        <span class="project-dot" aria-hidden="true"></span>
        {#if $selectedProjectStore.project_code}
          <span class="project-code">{$selectedProjectStore.project_code}</span>
        {/if}
        <span class="project-name">{$selectedProjectStore.name || $selectedProjectStore.project_name || 'Active Project'}</span>
        <span class="project-kb-count">KB {kbDocuments.length} ไฟล์</span>
      </div>
    </div>

    <div class="glass-panel form-panel">
      <div class="panel-header">
        <div class="panel-title-group">
          <h2>QA Document Creation</h2>
          <span class="badge-mode">AI Generator</span>
        </div>
        <button
          type="button"
          class="btn-collapse-form"
          on:click={() => isFormCollapsed = !isFormCollapsed}
          aria-expanded={!isFormCollapsed}
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            {#if isFormCollapsed}
              <polyline points="6 9 12 15 18 9"></polyline>
            {:else}
              <polyline points="18 15 12 9 6 15"></polyline>
            {/if}
          </svg>
          <span>{isFormCollapsed ? 'เปิดฟอร์มสร้างเอกสาร' : 'พับฟอร์มเพื่อดูประวัติ'}</span>
        </button>
      </div>

      {#if !isFormCollapsed}
        <p class="desc-text">สร้างเอกสาร QA (SRS, SDD, TOR, Test Case, UAT, คู่มือ) โดยระบบจะดึงข้อมูลจากคลังเอกสาร, Requirement, Diagram และเกณฑ์ Exit Criteria ของโครงการมาวิเคราะห์ร่วมกันอัตโนมัติ</p>

        {#if activeFeedback}
          <div class="refinement-banner" transition:slide>
            <div class="refinement-banner-header">
              <div class="refinement-badge">
                <span class="pulse-dot" aria-hidden="true"></span>
                <span>โหมดปรับปรุงเอกสารตามผลตรวจ QA Consult (ล็อกคำสั่งแก้ไขอัตโนมัติ)</span>
              </div>
              <div class="refinement-actions">
                <button type="button" class="btn-findings-toggle" on:click={() => showFindingsDrawer = !showFindingsDrawer}>
                  {showFindingsDrawer ? 'ซ่อนรายการประเด็น' : `ดูประเด็นข้อผิดพลาด (${activeFeedback.findings?.length || 0} ข้อ)`}
                </button>
                <button type="button" class="btn-clear-refine" on:click={clearRefinementMode}>
                  ยกเลิกโหมดนี้
                </button>
              </div>
            </div>
            
            <div class="refinement-banner-body">
              <div class="refinement-info-chip"><strong>เอกสารเดิม:</strong> {activeFeedback.source_filename || activeFeedback.doc_name}</div>
              <div class="refinement-info-chip"><strong>ประเภท:</strong> {activeFeedback.doc_type}</div>
              {#if activeFeedback.exit_criteria_eval}
                <div class="refinement-info-chip">
                  <strong>Gate ก่อนหน้า:</strong> 
                  <span class="refinement-gate-tag status-{(activeFeedback.exit_criteria_eval.status || 'rejected').toLowerCase()}">
                    {activeFeedback.exit_criteria_eval.status} ({activeFeedback.exit_criteria_eval.score_percentage}%)
                  </span>
                </div>
              {/if}
            </div>

            {#if showFindingsDrawer && activeFeedback.findings && activeFeedback.findings.length > 0}
              <div class="findings-drawer" transition:slide>
                <div class="findings-drawer-title">รายการข้อบกพร่องที่ระบบล็อกไว้เพื่อแก้ไขในรอบนี้ ({activeFeedback.findings.length} ข้อ):</div>
                <div class="findings-mini-list">
                  {#each activeFeedback.findings as f, i}
                    <div class="finding-mini-card sev-{(f.severity || 'medium').toLowerCase()}">
                      <div class="f-top">
                        <span class="f-num">#{i+1}</span>
                        <span class="f-type">[{f.check_type || 'Audit'}]</span>
                        <span class="f-issue">{f.issue}</span>
                        <span class="f-sev sev-pill-{(f.severity || 'medium').toLowerCase()}">{f.severity || 'Medium'}</span>
                      </div>
                      {#if f.found_incorrect && f.found_incorrect !== '-'}
                        <div class="f-evidence"><span class="f-evidence-lbl">ข้อความเดิม:</span> {f.found_incorrect}</div>
                      {/if}
                      {#if f.recommendation && f.recommendation !== '-'}
                        <div class="f-rec"><strong>แนวทางแก้ไข:</strong> {f.recommendation}</div>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}

        <div class="form-container">
          <div class="form-row">
            <div class="form-group half-width">
              <label for="docName">ชื่อเอกสาร (Document Name)</label>
              <input type="text" id="docName" bind:value={docName} placeholder="เช่น System Test Case Suite v1.0" class="text-input" />
            </div>

            <div class="form-group half-width" style="z-index: 80;">
              <label for="docType">ประเภทเอกสารที่ต้องการสร้าง (Document Type)</label>
              <CustomSelect id="docType" bind:value={docType} options={docTypeOptions} />
            </div>
          </div>

          <!-- Collapsible Optional Settings Bar -->
          <div class="optional-settings-bar">
            <button
              type="button"
              class="btn-optional-toggle"
              on:click={() => showOptionalSettings = !showOptionalSettings}
              aria-expanded={showOptionalSettings}
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                {#if showOptionalSettings}
                  <polyline points="18 15 12 9 6 15"></polyline>
                {:else}
                  <polyline points="6 9 12 15 18 9"></polyline>
                {/if}
              </svg>
              <span>ตัวเลือกเสริม (AI Skill Template · เอกสารอ้างอิง · Prompt เพิ่มเติม)</span>
              <span class="optional-summary-pill">
                Skill: {selectedSkillIds.length > 0 ? `${selectedSkillIds.length} รายการ` : 'Auto Standard'}
                &middot;
                KB: {selectedKbDocIds.length > 0 ? `${selectedKbDocIds.length} ไฟล์` : `ทั้งหมด (${kbDocuments.length})`}
                {#if customPrompt.trim()}
                  &middot; มี Prompt เพิ่มเติม
                {/if}
              </span>
            </button>
          </div>

          {#if showOptionalSettings || activeFeedback}
            <div class="optional-settings-body" transition:slide>
              <div class="form-row">
                <div class="form-group half-width" style="z-index: 75;">
                  <label for="skillSelect">
                    อ้างอิง AI Skill / Template โครงสร้างหัวข้อ <span class="opt-tag">(Optional)</span>
                  </label>
                  <CustomMultiSelect 
                    id="skillSelect" 
                    bind:values={selectedSkillIds} 
                    options={skillOptions} 
                    placeholder={activeFeedback ? "ไม่เลือก = แก้ตรงจุดตามผลตรวจ QA หรือเลือก Skill เพื่อคุมหัวข้อ..." : "ไม่เลือก = ใช้มาตรฐานสากล + Exit Criteria อัตโนมัติ..."} 
                    disabled={skills.length === 0} 
                  />
                  <span class="field-hint">
                    {#if activeFeedback}
                      โหมดปรับปรุง: ไม่เลือก Skill เพื่อผ่าตัดแก้ตรงจุด หรือเลือก Skill เพื่อจัดโครงสร้างหัวข้อให้ตรงตาม Template
                    {:else}
                      ระบบดึงข้อมูลทุกเมนูและเกณฑ์ Exit Criteria อัตโนมัติ การเลือก AI Skill จะช่วยคุมหัวข้อและรายละเอียดให้ตรงตาม Template
                    {/if}
                  </span>
                </div>

                <div class="form-group half-width" style="z-index: 70;">
                  <label for="kbDocSelect">อ้างอิงเอกสารในระบบ (Reference Documents) <span class="opt-tag">(Optional)</span></label>
                  <CustomMultiSelect 
                    id="kbDocSelect" 
                    bind:values={selectedKbDocIds} 
                    options={kbDocOptions} 
                    placeholder={kbDocuments.length === 0 ? "ยังไม่มีเอกสารใน Knowledge Base ของโครงการ" : "เว้นว่างเพื่อดึงทุกฉบับในคลัง หรือเลือกเฉพาะไฟล์..."} 
                    disabled={kbDocuments.length === 0} 
                  />
                  <span class="field-hint">
                    {#if kbDocuments.length === 0}
                      โครงการนี้ยังไม่มีไฟล์ใน Knowledge Base — สามารถอัปโหลดเอกสาร SRS/TOR ที่เมนู Knowledge Base เพื่อความแม่นยำสูงสุด
                    {:else}
                      พบเอกสารในคลัง {kbDocuments.length} ฉบับ หากเว้นว่าง AI จะวิเคราะห์รวมทั้งหมดโดยให้ความสำคัญกับ Golden Data และ SRS
                    {/if}
                  </span>
                </div>
              </div>

              <div class="form-group">
                <div class="label-row">
                  <label for="customPrompt">คำสั่งหรือ Prompt เพิ่มเติม <span class="opt-tag">(Optional)</span></label>
                  {#if customPrompt && customPrompt.trim()}
                    <button type="button" class="btn-text-clear" on:click={() => customPrompt = ""}>
                      ล้างข้อความเพิ่มเติม
                    </button>
                  {/if}
                </div>
                <textarea 
                  id="customPrompt" 
                  bind:value={customPrompt} 
                  placeholder={activeFeedback ? "ระบุคำสั่งเสริมเพิ่มเติมได้ทันที (คำสั่งแก้ไขข้อผิดพลาดจาก QA Consult ถูกล็อกไว้ในระบบแล้ว ไม่ต้องพิมพ์ซ้ำ)..." : "เช่น ระบุเงื่อนไข Edge Cases พิเศษ, เน้นการทดสอบกรณี Error Handling, หรือข้อกำหนดเฉพาะที่ต้องการ..."} 
                  rows="3" 
                  class="text-input custom-prompt-textarea"
                ></textarea>
              </div>
            </div>
          {/if}

          <div class="form-submit-row">
            <span class="format-hint">
              รูปแบบไฟล์ออก: <strong>{docType === 'Test Case' || docType === 'TestCase' ? 'Excel (.xlsx) แยกตามเมนู SRS' : 'PDF + Markdown มาตรฐาน'}</strong>
            </span>
            <button type="button" class="btn-primary" class:btn-refine-action={!!activeFeedback} on:click={handleGenerate} disabled={isGenerating || !$selectedProjectStore}>
              {#if isGenerating}
                <span class="spinner-small" aria-hidden="true"></span>
                <span>กำลังเริ่มสร้างเอกสาร...</span>
              {:else if activeFeedback}
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="23 4 23 10 17 10"></polyline>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                </svg>
                <span>ปรับปรุงและสร้างเอกสารใหม่ (Regenerate &amp; Fix)</span>
              {:else}
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z"></path>
                </svg>
                <span>สร้างเอกสาร (Generate Document)</span>
              {/if}
            </button>
          </div>
        </div>
      {/if}
    </div>

    <!-- History Table Area -->
    <div class="glass-panel history-panel">
      <div class="history-header-bar">
        <div class="panel-title-group">
          <h3>ประวัติการสร้างเอกสาร (Generation History)</h3>
          <span class="history-total-pill">{filteredHistory.length} / {generatedHistory.length}</span>
        </div>

        <div class="history-toolbar">
          <div class="search-input-wrap">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              class="history-search-input"
              bind:value={historySearch}
              on:input={() => currentPage = 1}
              placeholder="ค้นหาชื่อเอกสาร / ประเภท..."
              aria-label="ค้นหาชื่อเอกสารในประวัติ"
            />
          </div>

          <div class="filter-chips" role="group" aria-label="กรองตามสถานะเอกสาร">
            <button type="button" class="filter-chip" class:active={historyFilter === 'all'} on:click={() => { historyFilter = 'all'; currentPage = 1; }}>
              ทั้งหมด ({historyCounts.all})
            </button>
            <button type="button" class="filter-chip" class:active={historyFilter === 'passed'} on:click={() => { historyFilter = 'passed'; currentPage = 1; }}>
              ผ่าน ({historyCounts.passed})
            </button>
            <button type="button" class="filter-chip" class:active={historyFilter === 'issues'} on:click={() => { historyFilter = 'issues'; currentPage = 1; }}>
              ไม่ผ่าน/ข้อสังเกต ({historyCounts.issues})
            </button>
            <button type="button" class="filter-chip" class:active={historyFilter === 'unscanned'} on:click={() => { historyFilter = 'unscanned'; currentPage = 1; }}>
              ยังไม่ตรวจ ({historyCounts.unscanned})
            </button>
          </div>
        </div>
      </div>

      <div class="table-container">
        <table class="history-table">
          <thead>
            <tr>
              <th>วัน-เวลา</th>
              <th>ชื่อเอกสาร</th>
              <th>ประเภท</th>
              <th>Framework / Skill</th>
              <th>สถานะสร้างเอกสาร</th>
              <th>ผลการตรวจ QA</th>
              <th>การกระทำ</th>
            </tr>
          </thead>
          <tbody>
            {#if filteredHistory.length === 0}
              <tr>
                <td colspan="7" class="empty-table-cell">
                  {generatedHistory.length === 0 ? 'ยังไม่มีประวัติการสร้างเอกสารในโครงการนี้' : 'ไม่พบเอกสารที่ตรงกับเงื่อนไขการค้นหา'}
                </td>
              </tr>
            {:else}
              {#each paginatedHistory as doc (doc.id)}
                <tr class:row-highlight={recentlyCreatedId && String(doc.id) === String(recentlyCreatedId)}>
                  <td class="col-date">
                    {doc.created_at ? new Date(doc.created_at).toLocaleString('th-TH') : '-'}
                  </td>
                  <td class="col-docname">{doc.doc_name}</td>
                  <td><span class="doc-type-badge">{doc.doc_type}</span></td>
                  <td class="col-skill">{doc.skill_name || 'Auto Standard'}</td>
                  <td>
                    {#if doc.status === 'Generating'}
                      <div class="status-inline status-generating">
                        <span class="spinner-micro" aria-hidden="true"></span>
                        <span>กำลังสร้าง...</span>
                      </div>
                    {:else if doc.status === 'Completed'}
                      <span class="status-inline status-completed">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                        เสร็จสมบูรณ์
                      </span>
                    {:else if doc.status === 'Cancelled'}
                      <span class="status-inline status-cancelled">ยกเลิกแล้ว</span>
                    {:else if doc.status === 'Failed'}
                      <div class="status-failed-wrap">
                        <span class="status-inline status-failed">ล้มเหลว</span>
                        <button
                          type="button"
                          class="btn-error-detail"
                          on:click={() => openErrorModal(doc)}
                        >
                          ดูสาเหตุ / ลองใหม่
                        </button>
                      </div>
                    {:else}
                      <span>{doc.status}</span>
                    {/if}
                  </td>
                  <td>
                    {#if doc.qa_status === 'Scanning'}
                      <div class="qa-badge qa-scanning" title="กำลังดำเนินการตรวจประเมินคุณภาพ...">
                        <span class="spinner-micro" aria-hidden="true"></span>
                        <span>กำลังตรวจ...</span>
                      </div>
                    {:else if doc.qa_status === 'PASSED'}
                      <div class="qa-badge qa-pass" title="เอกสารผ่านเกณฑ์การตรวจสอบ QA ทั้งหมด">
                        <span>ผ่าน</span>
                        {#if doc.qa_score !== null && doc.qa_score !== undefined}
                          <span class="qa-score-chip">{doc.qa_score}%</span>
                        {/if}
                      </div>
                    {:else if doc.qa_status === 'REJECTED' || (doc.qa_findings_count && doc.qa_findings_count > 0)}
                      <button 
                        type="button"
                        class="qa-badge qa-fail clickable" 
                        title="คลิกเพื่อดูรายละเอียดข้อผิดพลาด"
                        on:click={() => openFindingsModal(doc)}
                      >
                        <span class="badge-main">ไม่ผ่าน ({doc.qa_findings_count || (doc.qa_findings && doc.qa_findings.length) || 0} ข้อ)</span>
                        <span class="view-detail-hint">ดูรายละเอียดและส่งแก้</span>
                      </button>
                    {:else if doc.qa_status === 'CONDITIONAL_PASSED'}
                      <button 
                        type="button"
                        class="qa-badge qa-warn clickable" 
                        title="คลิกเพื่อดูข้อสังเกต"
                        on:click={() => openFindingsModal(doc)}
                      >
                        <span class="badge-main">ข้อสังเกต ({doc.qa_findings_count || (doc.qa_findings && doc.qa_findings.length) || 0} ข้อ)</span>
                        <span class="view-detail-hint">ดูรายละเอียด</span>
                      </button>
                    {:else}
                      <span class="qa-badge qa-none" title="ยังไม่ได้ส่งตรวจที่เมนู QA Consult">
                        ยังไม่ตรวจ
                      </span>
                    {/if}
                  </td>
                  <td>
                    <div class="actions-group">
                      {#if doc.status === 'Generating'}
                        <button type="button" class="btn-action btn-cancel-action" title="ยกเลิกการสร้างเอกสาร" on:click={() => cancelDocument(doc)}>
                          ยกเลิก
                        </button>
                      {:else if doc.status === 'Completed'}
                        {#if doc.doc_type === 'Test Case' || doc.doc_type === 'TestCase'}
                          <button type="button" class="btn-action btn-excel" title="ดาวน์โหลดไฟล์ Excel (.xlsx)" on:click={() => downloadFile(doc, 'excel')}>
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                            Excel
                          </button>
                        {:else}
                          <button type="button" class="btn-action btn-pdf" title="ดาวน์โหลดไฟล์ PDF" on:click={() => downloadFile(doc, 'pdf')}>
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                            PDF
                          </button>
                        {/if}
                        <button 
                          type="button"
                          class="btn-action btn-qa-consult" 
                          title={doc.qa_status === 'Scanning' ? 'เอกสารนี้กำลังถูกตรวจสอบอยู่' : 'ส่งไฟล์เอกสารนี้ไปตรวจที่ QA Consult'}
                          disabled={(isTransferringToQA && transferringDocId === doc.id) || doc.qa_status === 'Scanning'}
                          on:click={() => sendToQAConsult(doc)}
                        >
                          {#if isTransferringToQA && transferringDocId === doc.id}
                            <span class="spinner-micro" aria-hidden="true"></span>
                            กำลังส่ง...
                          {:else}
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                            ส่งตรวจ QA
                          {/if}
                        </button>
                        {#if doc.is_saved_to_project}
                          <span class="badge-saved" title="เอกสารนี้ถูกบันทึกเข้า Knowledge Base ของโครงการแล้ว">
                            <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            อยู่ใน KB แล้ว
                          </span>
                        {:else}
                          <button 
                            type="button"
                            class="btn-action btn-save-kb" 
                            on:click={() => openSaveModal(doc)}
                            title="บันทึกเอกสารเข้า Knowledge Base ของโครงการ"
                          >
                            บันทึกเข้า KB
                          </button>
                        {/if}
                        <button type="button" class="btn-action btn-delete" aria-label="ลบประวัติเอกสาร {doc.doc_name}" title="ลบประวัติรายการนี้" on:click={() => openDeleteModal(doc)}>
                          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                      {:else}
                        {#if doc.status === 'Failed'}
                          <button type="button" class="btn-action btn-save-kb" on:click={() => retryFailedDoc(doc)}>
                            ลองใหม่
                          </button>
                        {/if}
                        <button type="button" class="btn-action btn-delete" aria-label="ลบประวัติเอกสาร {doc.doc_name}" title="ลบประวัติรายการนี้" on:click={() => openDeleteModal(doc)}>
                          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
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
          <button type="button" class="btn-page" disabled={currentPage === 1} on:click={() => goToPage(currentPage - 1)}>
            <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2" fill="none" aria-hidden="true"><polyline points="15 18 9 12 15 6"></polyline></svg>
            ก่อนหน้า
          </button>
          <span class="page-info">หน้า {currentPage} จาก {totalPages}</span>
          <button type="button" class="btn-page" disabled={currentPage === totalPages} on:click={() => goToPage(currentPage + 1)}>
            ถัดไป
            <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2" fill="none" aria-hidden="true"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </button>
        </div>
      {/if}
    </div>

  {/if}
</div>

<!-- ── Delete Confirmation Modal ── -->
{#if showDeleteModal && docToDelete}
  <div class="modal-backdrop" on:click|self={closeDeleteModal} in:fade={{ duration: 150 }}>
    <div class="modal-content modal-delete-content" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title" on:click|stopPropagation in:scale={{ duration: 200, start: 0.95 }}>
      <button type="button" class="modal-close-btn" on:click={closeDeleteModal} aria-label="ปิดหน้าต่าง" title="ปิด">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
      
      <div class="delete-icon-wrapper">
        <div class="delete-icon-pulse"></div>
        <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" class="delete-svg-icon" aria-hidden="true">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </div>

      <div class="modal-delete-header">
        <h3 id="delete-modal-title">ยืนยันการลบเอกสาร</h3>
        <p class="modal-delete-desc">
          คุณแน่ใจหรือไม่ว่าต้องการลบเอกสาร <span class="highlight-docname">"{docToDelete.doc_name}"</span> ออกจากประวัติ?
        </p>
        <div class="modal-delete-subdesc">
          การกระทำนี้ไม่สามารถย้อนกลับได้ และไฟล์ที่สร้างไว้จะถูกลบออกจากระบบ
        </div>
      </div>

      <div class="modal-actions modal-actions-center">
        <button type="button" class="btn-cancel" on:click={closeDeleteModal} disabled={isDeleting}>
          ยกเลิก
        </button>
        <button type="button" class="btn-confirm-delete" on:click={handleDeleteConfirmed} disabled={isDeleting}>
          {#if isDeleting}
            <span class="spinner-micro" aria-hidden="true"></span> กำลังลบ...
          {:else}
            ยืนยันลบเอกสาร
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Save to Project Modal ── -->
{#if showSaveModal}
  <div class="modal-backdrop" on:click|self={() => { if (!isSavingToProject) showSaveModal = false; }} in:fade={{ duration: 150 }}>
    <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="save-modal-title" on:click|stopPropagation in:scale={{ duration: 200, start: 0.95 }}>
      <button type="button" class="modal-close-btn" on:click={() => { if (!isSavingToProject) showSaveModal = false; }} aria-label="ปิดหน้าต่าง" title="ปิด">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
      
      <div class="modal-title-bar">
        <div class="modal-icon-badge">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
          </svg>
        </div>
        <div>
          <h3 id="save-modal-title">บันทึกเอกสารเข้า Project Knowledge Base</h3>
          <p class="modal-subtitle">บันทึกเนื้อหาเอกสารเพื่อให้ AI ในทุกเมนูใช้อ้างอิงร่วมกัน</p>
        </div>
      </div>
      
      <div class="form-group modal-field-top">
        <label for="save-filename">ชื่อไฟล์</label>
        <input id="save-filename" type="text" bind:value={saveFilename} class="form-input" />
      </div>

      <div class="form-group" style="z-index: 100;">
        <label for="save-project">โครงการ (Project)</label>
        <CustomSelect 
          id="save-project" 
          bind:value={saveProjectId} 
          options={projectSelectOptions} 
          width="100%"
        />
      </div>

      <div class="form-group" style="z-index: 90;">
        <label for="save-category">หมวดหมู่เอกสาร</label>
        <CustomSelect 
          id="save-category" 
          bind:value={saveDocCategory} 
          options={categorySelectOptions} 
          width="100%"
        />
      </div>

      <div class="toggle-card">
        <div>
          <span class="label-text toggle-title">กำหนดเป็น Golden Data</span>
          <span class="toggle-desc">เอกสารหลักที่มีความน่าเชื่อถือสูงสำหรับ AI ใช้อ้างอิงเป็นอันดับแรก</span>
        </div>
        <label class="toggle-wrap" aria-label="กำหนดเป็น Golden Data">
          <input type="checkbox" bind:checked={saveIsGoldenData}/>
          <span class="toggle-track"><span class="toggle-thumb"></span></span>
        </label>
      </div>

      {#if saveIsGoldenData && selectedDocForSave && selectedDocForSave.qa_status !== 'PASSED'}
        <div class="golden-warning-box" transition:slide>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          <span>คำเตือน: เอกสารนี้ยังมีสถานะ <strong>{selectedDocForSave.qa_status || 'ยังไม่ผ่านการตรวจ QA'}</strong> การตั้งเป็น Golden Data อาจส่งผลต่อความแม่นยำของเอกสารฉบับถัดไป</span>
        </div>
      {/if}

      <div class="modal-actions">
        <button type="button" class="btn-cancel" on:click={() => showSaveModal = false} disabled={isSavingToProject}>ยกเลิก</button>
        <button 
          type="button"
          class="btn-save" 
          on:click={handleSaveToProject} 
          disabled={isSavingToProject}
        >
          {#if isSavingToProject}
            <span class="spinner-micro" aria-hidden="true"></span> กำลังบันทึก...
          {:else}
            บันทึกเข้า Project
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── QA Audit Findings Modal ── -->
{#if showFindingsModal && selectedDocForFindings}
  <div class="modal-backdrop" on:click|self={closeFindingsModal} in:fade={{ duration: 150 }}>
    <div class="modal-content modal-findings-content" role="dialog" aria-modal="true" aria-labelledby="findings-modal-title" on:click|stopPropagation in:scale={{ duration: 200, start: 0.95 }}>
      <button type="button" class="modal-close-btn" on:click={closeFindingsModal} aria-label="ปิดหน้าต่าง" title="ปิด">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>
      
      <div class="modal-title-bar">
        <div class="modal-icon-badge modal-icon-danger">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="12" y1="18" x2="12" y2="12"></line>
            <line x1="12" y1="9" x2="12.01" y2="9"></line>
          </svg>
        </div>
        <div class="findings-header-main">
          <div class="findings-header-row">
            <h3 id="findings-modal-title">ผลการตรวจสอบ QA (QA Audit Findings)</h3>
            {#if selectedDocForFindings.qa_status === 'REJECTED' || (selectedDocForFindings.qa_findings_count > 0)}
              <span class="finding-status-tag tag-fail">ไม่ผ่านเกณฑ์</span>
            {:else if selectedDocForFindings.qa_status === 'CONDITIONAL_PASSED'}
              <span class="finding-status-tag tag-warn">ผ่านแบบมีข้อสังเกต</span>
            {:else}
              <span class="finding-status-tag tag-pass">ผ่านเกณฑ์สมบูรณ์</span>
            {/if}
          </div>
          <p class="modal-subtitle">
            เอกสาร: <strong class="meta-accent-primary">{selectedDocForFindings.doc_name}</strong> 
            {#if selectedDocForFindings.qa_score !== null && selectedDocForFindings.qa_score !== undefined}
              <span class="meta-sep">|</span> คะแนน: <strong class="meta-accent-score">{selectedDocForFindings.qa_score}%</strong>
            {/if}
            <span class="meta-sep">|</span> ประเด็นที่พบ: <strong class="meta-accent-danger">{(selectedDocForFindings.qa_findings && selectedDocForFindings.qa_findings.length) || selectedDocForFindings.qa_findings_count || 0} ข้อ</strong>
          </p>
        </div>
      </div>

      <!-- Findings List -->
      <div class="findings-list-container">
        {#if !selectedDocForFindings.qa_findings || selectedDocForFindings.qa_findings.length === 0}
          <div class="empty-findings">
            {#if selectedDocForFindings.qa_status === 'REJECTED' || selectedDocForFindings.qa_status === 'CONDITIONAL_PASSED' || selectedDocForFindings.qa_findings_count > 0}
              <p class="empty-findings-text">ไม่พบรายการข้อบกพร่องแบบแยกรายข้อในฐานข้อมูล — กรุณาตรวจสอบรายละเอียดฉบับเต็มในเมนู QA Consult หรือกดปุ่มส่งแก้ไขอัตโนมัติด้านล่าง</p>
            {:else}
              <p class="empty-findings-text">ไม่พบข้อผิดพลาดหรือข้อบกพร่องที่ต้องแก้ไขในเอกสารนี้</p>
            {/if}
          </div>
        {:else}
          {#each selectedDocForFindings.qa_findings as finding, idx}
            <div class="finding-card severity-{(finding.severity || 'medium').toLowerCase()}">
              <div class="finding-card-header">
                <div class="finding-title-left">
                  <span class="finding-number">#{idx + 1}</span>
                  <span class="severity-badge sev-{(finding.severity || 'medium').toLowerCase()}">
                    {finding.severity || 'Medium'}
                  </span>
                  <span class="category-badge">{finding.category || finding.check_type || 'General'}</span>
                </div>
              </div>

              <div class="finding-body">
                <div class="finding-row">
                  <div class="finding-label">ประเด็นข้อผิดพลาด</div>
                  <div class="finding-value problem-text">
                    {finding.problem || finding.issue || finding.finding || finding.description || '-'}
                  </div>
                </div>

                {#if finding.evidence || finding.detail || finding.location || finding.found_incorrect}
                  <div class="finding-row">
                    <div class="finding-label">จุดที่พบ / บริบท (Evidence)</div>
                    <div class="finding-value evidence-text">
                      {finding.evidence || finding.detail || finding.location || finding.found_incorrect}
                    </div>
                  </div>
                {/if}

                {#if finding.recommendation || finding.suggestion || finding.fix}
                  <div class="finding-row recommendation-row">
                    <div class="finding-label">คำแนะนำการแก้ไข (QA Suggestion)</div>
                    <div class="finding-value recommendation-text">
                      {finding.recommendation || finding.suggestion || finding.fix}
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>

      <div class="modal-actions modal-actions-split">
        <button type="button" class="btn-cancel" on:click={closeFindingsModal}>
          ปิดหน้าต่าง
        </button>
        <button 
          type="button"
          class="btn-refine-action" 
          on:click={() => applyDocFindingsToRefinement(selectedDocForFindings)}
        >
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
          </svg>
          ส่งข้อผิดพลาดเข้าโหมดปรับปรุงเอกสาร (Auto Refine)
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Generation Failure Diagnostics Modal ── -->
{#if showErrorModal && selectedDocForError}
  <div class="modal-backdrop" on:click|self={closeErrorModal} in:fade={{ duration: 150 }}>
    <div class="modal-content modal-error-content" role="dialog" aria-modal="true" aria-labelledby="error-modal-title" on:click|stopPropagation in:scale={{ duration: 200, start: 0.95 }}>
      <button type="button" class="modal-close-btn" on:click={closeErrorModal} aria-label="ปิดหน้าต่าง" title="ปิด">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
      </button>

      <div class="modal-title-bar">
        <div class="modal-icon-badge modal-icon-danger">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
        <div>
          <h3 id="error-modal-title">รายละเอียดข้อผิดพลาดในการสร้างเอกสาร</h3>
          <p class="modal-subtitle">เอกสาร: <strong class="meta-accent-primary">{selectedDocForError.doc_name}</strong> ({selectedDocForError.doc_type})</p>
        </div>
      </div>

      <pre class="error-log-box">{selectedDocForError.error_message || 'ไม่พบรายละเอียดข้อผิดพลาดจากเซิร์ฟเวอร์'}</pre>

      <div class="modal-actions modal-actions-split">
        <button type="button" class="btn-cancel" on:click={copyErrorText}>
          คัดลอกข้อความ Error
        </button>
        <div class="modal-actions-right">
          <button type="button" class="btn-cancel" on:click={closeErrorModal}>ปิด</button>
          <button type="button" class="btn-save" on:click={() => retryFailedDoc(selectedDocForError)}>
            นำกลับเข้าฟอร์มเพื่อลองใหม่
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .panel-container {
    display: flex;
    flex-direction: column;
    gap: 18px;
    height: 100%;
    overflow-y: auto;
    padding: 20px 24px 32px;
    max-width: 100%;
    margin: 0;
    width: 100%;
    box-sizing: border-box;
    font-family: 'Prompt', 'Outfit', sans-serif;
  }

  .top-nav-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .btn-back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(18, 20, 28, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.09);
    color: #cbd5e1;
    padding: 7px 14px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-back:hover {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.4);
    color: #f8fafc;
  }

  .active-project-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 12px;
    background: rgba(18, 20, 28, 0.72);
    border: 1px solid rgba(99, 102, 241, 0.28);
    font-size: 12.5px;
    color: #e2e8f0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .project-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #6366f1;
    box-shadow: 0 0 8px rgba(99, 102, 241, 0.7);
    flex-shrink: 0;
  }
  .project-code {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    color: #a5b4fc;
    letter-spacing: 0.02em;
    flex-shrink: 0;
  }
  .project-name {
    font-weight: 500;
    color: #f8fafc;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .project-kb-count {
    font-family: 'Outfit', 'Prompt', sans-serif;
    font-size: 11.5px;
    padding: 2px 8px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.16);
    color: #c7d2fe;
    border: 1px solid rgba(99, 102, 241, 0.25);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    white-space: nowrap;
  }
  
  .glass-panel {
    background: rgba(18, 20, 28, 0.62);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 22px 24px;
    color: #f8fafc;
  }

  .form-panel {
    position: relative;
    z-index: 50;
  }

  .history-panel {
    position: relative;
    z-index: 1;
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }

  .panel-title-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .panel-header h2 {
    margin: 0;
    font-family: 'Outfit', 'Prompt', sans-serif;
    font-size: 1.45rem;
    color: #f8fafc;
    font-weight: 700;
    letter-spacing: -0.02em;
  }

  .badge-mode {
    font-family: 'Outfit', sans-serif;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: #a5b4fc;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }

  .btn-collapse-form {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-collapse-form:hover {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.35);
    color: #f8fafc;
  }

  .desc-text {
    color: #94a3b8;
    font-size: 13.5px;
    margin: 0 0 18px 0;
    line-height: 1.55;
  }

  .form-container {
    position: relative;
    z-index: 60;
    display: flex;
    flex-direction: column;
    gap: 14px;
    background: rgba(10, 11, 18, 0.5);
    padding: 18px 20px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    position: relative;
  }

  .form-row {
    display: flex;
    gap: 14px;
    position: relative;
    z-index: 80;
  }

  .half-width {
    flex: 1;
    min-width: 0;
  }

  label {
    font-size: 13px;
    color: #cbd5e1;
    font-weight: 500;
  }

  .opt-tag {
    color: #94a3b8;
    font-weight: 400;
    font-size: 11.5px;
  }

  .field-hint {
    font-size: 11.5px;
    color: #94a3b8;
    line-height: 1.45;
  }

  .label-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .btn-text-clear {
    background: none;
    border: none;
    color: #94a3b8;
    font-size: 11.5px;
    font-family: inherit;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
  }
  .btn-text-clear:hover {
    color: #e2e8f0;
  }

  .optional-settings-bar {
    display: flex;
    align-items: center;
  }

  .btn-optional-toggle {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    padding: 9px 14px;
    border-radius: 10px;
    font-size: 12.5px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
  }
  .btn-optional-toggle:hover {
    background: rgba(99, 102, 241, 0.1);
    border-color: rgba(99, 102, 241, 0.35);
    color: #f8fafc;
  }

  .optional-summary-pill {
    margin-left: auto;
    font-size: 11.5px;
    color: #a5b4fc;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.25);
    padding: 2px 10px;
    border-radius: 8px;
    font-variant-numeric: tabular-nums;
  }

  .optional-settings-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding-top: 6px;
  }

  .text-input {
    background: rgba(10, 11, 18, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #f8fafc;
    min-height: 40px;
    padding: 9px 13px;
    border-radius: var(--radius-md);
    font-size: 13.5px;
    font-family: inherit;
    outline: none;
    box-sizing: border-box;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .text-input::placeholder {
    color: #94a3b8;
  }

  .custom-prompt-textarea {
    width: 100%;
    resize: vertical;
    min-height: 76px;
    line-height: 1.55;
    box-sizing: border-box;
  }

  .text-input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22);
  }

  .form-submit-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding-top: 4px;
    flex-wrap: wrap;
  }

  .format-hint {
    font-size: 12px;
    color: #94a3b8;
  }
  .format-hint strong {
    color: #cbd5e1;
    font-weight: 600;
  }

  .btn-primary {
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.14);
    min-height: 40px;
    padding: 9px 22px;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 13.5px;
    font-weight: 600;
    font-family: inherit;
    box-sizing: border-box;
    transition: all 0.2s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .btn-primary:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.35);
  }

  .btn-primary:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .spinner-small {
    width: 15px;
    height: 15px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: #ffffff;
    animation: spin 0.9s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* History Toolbar & Table */
  .history-header-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    margin-bottom: 14px;
    flex-wrap: wrap;
  }

  .history-header-bar h3 {
    margin: 0;
    font-family: 'Outfit', 'Prompt', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: #f8fafc;
  }

  .history-total-pill {
    font-family: 'Outfit', sans-serif;
    font-size: 11.5px;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: #cbd5e1;
    font-variant-numeric: tabular-nums;
  }

  .history-toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .search-input-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(10, 11, 18, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 0 10px;
    color: #94a3b8;
  }
  .search-input-wrap:focus-within {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }

  .history-search-input {
    background: transparent;
    border: none;
    color: #f8fafc;
    font-size: 12.5px;
    font-family: inherit;
    padding: 7px 0;
    width: 200px;
    outline: none;
  }
  .history-search-input::placeholder {
    color: #94a3b8;
  }

  .filter-chips {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .filter-chip {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #94a3b8;
    font-size: 12px;
    font-weight: 500;
    font-family: inherit;
    padding: 5px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    font-variant-numeric: tabular-nums;
  }
  .filter-chip:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
  }
  .filter-chip.active {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.45);
    color: #c7d2fe;
  }

  .table-container {
    max-height: 520px;
    overflow: auto;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    background: rgba(10, 11, 18, 0.45);
    flex: 1;
  }

  .history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13.5px;
    color: #e2e8f0;
  }

  .history-table th {
    text-align: left;
    padding: 11px 14px;
    background: #141724;
    font-weight: 600;
    font-size: 12px;
    color: #94a3b8;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    position: sticky;
    top: 0;
    z-index: 3;
    white-space: nowrap;
  }

  .history-table td {
    padding: 11px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    vertical-align: middle;
  }

  .history-table tr:hover {
    background: rgba(255, 255, 255, 0.025);
  }

  .history-table tr.row-highlight {
    background: rgba(99, 102, 241, 0.12);
  }

  .empty-table-cell {
    text-align: center;
    color: #94a3b8;
    padding: 28px 16px;
  }

  .col-date {
    color: #94a3b8;
    font-size: 12.5px;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .col-docname {
    font-weight: 500;
    color: #f8fafc;
    max-width: 280px;
    word-break: break-word;
  }

  .col-skill {
    color: #cbd5e1;
    font-size: 12.5px;
  }

  .doc-type-badge {
    display: inline-block;
    font-family: 'Outfit', 'Prompt', sans-serif;
    font-size: 11.5px;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: #c7d2fe;
    white-space: nowrap;
  }

  .status-inline {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12.5px;
    font-weight: 500;
    white-space: nowrap;
  }
  .status-generating { color: #fbbf24; }
  .status-completed { color: #4ade80; }
  .status-cancelled { color: #94a3b8; }
  .status-failed { color: #f87171; font-weight: 600; }

  .status-failed-wrap {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .btn-error-detail {
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #fca5a5;
    font-size: 11px;
    font-weight: 500;
    font-family: inherit;
    padding: 2px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-error-detail:hover {
    background: rgba(239, 68, 68, 0.25);
    color: #ffffff;
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
    justify-content: center;
    gap: 6px;
    min-height: 30px;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    box-sizing: border-box;
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
    min-height: 30px;
    padding: 5px 10px;
    border-radius: 6px;
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.35);
    color: #86efac;
    font-size: 12px;
    font-weight: 500;
    box-sizing: border-box;
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
    z-index: var(--z-modal, 10000);
    padding: 20px;
  }

  .modal-content {
    background: linear-gradient(145deg, #111827 0%, #0b0f19 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 26px 28px;
    width: 440px;
    max-width: 92vw;
    max-height: 88vh;
    overflow-y: auto;
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
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    cursor: pointer;
    z-index: 2;
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
    padding-right: 44px;
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
    min-height: 40px;
    padding: 9px 20px;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 13.5px;
    font-weight: 600;
    font-family: inherit;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-sizing: border-box;
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
    background: rgba(10, 11, 18, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #f8fafc;
    min-height: 40px;
    padding: 9px 13px;
    border-radius: var(--radius-md);
    font-family: inherit;
    font-size: 13.5px;
    outline: none;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
    width: 100%;
    box-sizing: border-box;
  }

  .form-input::placeholder {
    color: #94a3b8;
  }

  .form-input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22);
  }

  .modal-field-top {
    margin-top: 16px;
  }

  .toggle-card {
    margin: 14px 0;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 12px 14px;
    border-radius: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .label-text {
    font-size: 13px;
    color: #e2e8f0;
    font-weight: 600;
    display: block;
  }

  .toggle-desc {
    font-size: 11.5px;
    color: #94a3b8;
    display: block;
    margin-top: 2px;
  }

  .toggle-wrap {
    position: relative;
    display: inline-flex;
    align-items: center;
    cursor: pointer;
    flex-shrink: 0;
  }
  .toggle-wrap input {
    position: absolute;
    opacity: 0;
    width: 1px;
    height: 1px;
    margin: 0;
    pointer-events: none;
  }
  .toggle-track {
    width: 40px;
    height: 22px;
    border-radius: 11px;
    background: #334155;
    border: 1px solid #475569;
    position: relative;
    transition: all 0.22s ease;
  }
  .toggle-wrap input:focus-visible + .toggle-track {
    outline: 2px solid #818cf8;
    outline-offset: 2px;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    border-color: #6366f1;
    box-shadow: 0 0 10px rgba(99, 102, 241, 0.45);
  }
  .toggle-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #ffffff;
    position: absolute;
    top: 2px;
    left: 2px;
    transition: transform 0.22s ease;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb {
    transform: translateX(18px);
  }

  .golden-warning-box {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #fcd34d;
    font-size: 12px;
    line-height: 1.45;
    margin-bottom: 12px;
  }
  .golden-warning-box svg {
    flex-shrink: 0;
    margin-top: 2px;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 10px;
    margin-top: 22px;
    flex-wrap: wrap;
  }
  .modal-actions-center {
    justify-content: center;
  }
  .modal-actions-split {
    justify-content: space-between;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 16px;
    margin-top: 18px;
    flex-wrap: wrap;
  }
  .modal-actions-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn-cancel {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 40px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 9px 18px;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 13.5px;
    font-weight: 500;
    font-family: inherit;
    box-sizing: border-box;
    transition: all 0.2s ease;
  }

  .btn-cancel:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.24);
  }

  .btn-save {
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #ffffff;
    min-height: 40px;
    padding: 9px 20px;
    border-radius: var(--radius-md);
    cursor: pointer;
    font-size: 13.5px;
    font-weight: 600;
    font-family: inherit;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    box-sizing: border-box;
    transition: all 0.2s ease;
  }

  .btn-save:hover:not(:disabled) {
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.4);
    transform: translateY(-1px);
  }

  .btn-save:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .modal-icon-danger {
    background: rgba(239, 68, 68, 0.14);
    border: 1px solid rgba(239, 68, 68, 0.32);
    color: #f87171;
  }

  .findings-header-main {
    flex: 1;
    min-width: 0;
  }
  .findings-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    padding-right: 44px;
  }
  .findings-header-row h3 {
    margin: 0;
    font-size: 1.15rem;
  }
  .meta-accent-primary { color: #a5b4fc; }
  .meta-accent-score { color: #38bdf8; }
  .meta-accent-danger { color: #f87171; }
  .meta-sep { margin: 0 6px; color: #475569; }

  .modal-error-content {
    width: 640px;
    max-width: 94vw;
  }

  .error-log-box {
    margin: 16px 0 0;
    padding: 14px;
    border-radius: 10px;
    background: rgba(10, 11, 18, 0.85);
    border: 1px solid rgba(239, 68, 68, 0.28);
    color: #fca5a5;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 260px;
    overflow-y: auto;
  }

  /* Refinement Mode Styles */
  .refinement-banner {
    background: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(99, 102, 241, 0.34);
    border-radius: 12px;
    padding: 15px 18px;
    margin-bottom: 18px;
  }

  .refinement-banner-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 10px;
  }

  .refinement-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13.5px;
    font-weight: 600;
    color: #c7d2fe;
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    background: #a855f7;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 8px rgba(168, 85, 247, 0.8);
    animation: pulseDot 1.6s infinite;
  }

  @keyframes pulseDot {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.35); opacity: 0.55; }
  }

  .refinement-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-findings-toggle {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #e2e8f0;
    font-size: 12px;
    font-weight: 500;
    font-family: inherit;
    padding: 5px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-findings-toggle:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
  }

  .btn-clear-refine {
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #fca5a5;
    font-size: 12px;
    font-weight: 500;
    font-family: inherit;
    padding: 5px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-clear-refine:hover {
    background: rgba(239, 68, 68, 0.24);
    color: #ffffff;
  }

  .refinement-banner-body {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 12.5px;
    color: #cbd5e1;
  }

  .refinement-info-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(10, 11, 18, 0.65);
    padding: 4px 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .refinement-gate-tag {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 6px;
    font-size: 11px;
    text-transform: uppercase;
  }
  .refinement-gate-tag.status-rejected {
    background: rgba(239, 68, 68, 0.18);
    border: 1px solid rgba(239, 68, 68, 0.38);
    color: #fca5a5;
  }
  .refinement-gate-tag.status-conditional_passed {
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.38);
    color: #fcd34d;
  }
  .refinement-gate-tag.status-passed {
    background: rgba(34, 197, 94, 0.18);
    border: 1px solid rgba(34, 197, 94, 0.38);
    color: #86efac;
  }

  .findings-drawer {
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px dashed rgba(99, 102, 241, 0.3);
  }

  .findings-drawer-title {
    font-size: 12px;
    font-weight: 600;
    color: #c7d2fe;
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
    background: rgba(10, 11, 18, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 12px;
  }
  .finding-mini-card.sev-critical { border-color: rgba(239, 68, 68, 0.38); background: rgba(239, 68, 68, 0.05); }
  .finding-mini-card.sev-high { border-color: rgba(249, 115, 22, 0.38); background: rgba(249, 115, 22, 0.05); }
  .finding-mini-card.sev-medium { border-color: rgba(234, 179, 8, 0.34); background: rgba(234, 179, 8, 0.04); }
  .finding-mini-card.sev-low { border-color: rgba(99, 102, 241, 0.34); background: rgba(99, 102, 241, 0.04); }

  .f-top {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }
  .f-num { color: #94a3b8; font-weight: 700; font-family: 'Outfit', sans-serif; }
  .f-type { color: #a5b4fc; font-weight: 600; font-size: 11px; }
  .f-issue { color: #f8fafc; font-weight: 500; flex: 1; min-width: 0; }
  .f-sev {
    font-family: 'Outfit', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
  }
  .f-sev.sev-pill-critical { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  .f-sev.sev-pill-high { background: rgba(249, 115, 22, 0.2); color: #fdba74; }
  .f-sev.sev-pill-medium { background: rgba(234, 179, 8, 0.2); color: #fde047; }
  .f-sev.sev-pill-low { background: rgba(99, 102, 241, 0.2); color: #a5b4fc; }

  .f-evidence {
    color: #94a3b8;
    font-size: 11.5px;
    margin-bottom: 4px;
    padding-left: 20px;
  }
  .f-evidence-lbl {
    color: #f87171;
    font-weight: 500;
  }
  .f-rec {
    color: #7dd3fc;
    font-size: 11.5px;
    padding-left: 20px;
  }

  .btn-refine-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 40px;
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.18);
    padding: 9px 20px;
    border-radius: var(--radius-md);
    font-size: 13.5px;
    font-weight: 600;
    font-family: inherit;
    box-sizing: border-box;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-refine-action:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(99, 102, 241, 0.42);
  }
  .btn-refine-action:active:not(:disabled) {
    transform: translateY(0);
  }

  /* ── QA Result Badges in History Table ── */
  .qa-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    line-height: 1.2;
    border: 1px solid transparent;
    transition: all 0.2s ease;
    font-family: inherit;
    text-align: left;
  }

  .qa-badge.qa-scanning {
    background: rgba(234, 179, 8, 0.14);
    border-color: rgba(234, 179, 8, 0.32);
    color: #fbbf24;
  }

  .qa-badge.qa-pass {
    background: rgba(34, 197, 94, 0.14);
    border-color: rgba(34, 197, 94, 0.32);
    color: #4ade80;
  }

  .qa-score-chip {
    font-family: 'Outfit', sans-serif;
    background: rgba(34, 197, 94, 0.22);
    color: #86efac;
    padding: 1px 6px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  .qa-badge.qa-fail {
    background: rgba(239, 68, 68, 0.14);
    border-color: rgba(239, 68, 68, 0.32);
    color: #fca5a5;
  }

  .qa-badge.qa-warn {
    background: rgba(245, 158, 11, 0.14);
    border-color: rgba(245, 158, 11, 0.32);
    color: #fcd34d;
  }

  .qa-badge.qa-none {
    background: rgba(148, 163, 184, 0.08);
    border-color: rgba(148, 163, 184, 0.16);
    color: #94a3b8;
  }

  .qa-badge.clickable {
    cursor: pointer;
    flex-direction: column;
    align-items: flex-start;
    padding: 6px 10px;
  }

  .qa-badge.clickable:hover {
    transform: translateY(-1px);
  }

  .qa-badge.qa-fail.clickable:hover {
    background: rgba(239, 68, 68, 0.22);
    border-color: rgba(239, 68, 68, 0.55);
  }

  .qa-badge.qa-warn.clickable:hover {
    background: rgba(245, 158, 11, 0.22);
    border-color: rgba(245, 158, 11, 0.55);
  }

  .badge-main {
    font-weight: 600;
  }

  .view-detail-hint {
    font-size: 10.5px;
    color: #a5b4fc;
    text-decoration: underline;
    text-underline-offset: 2px;
    margin-top: 2px;
  }

  /* ── QA Findings Modal ── */
  .modal-findings-content {
    width: 760px;
    max-width: 95vw;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
  }

  .finding-status-tag {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 8px;
    text-transform: uppercase;
  }
  .finding-status-tag.tag-fail {
    background: rgba(239, 68, 68, 0.18);
    border: 1px solid rgba(239, 68, 68, 0.38);
    color: #fca5a5;
  }
  .finding-status-tag.tag-warn {
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.38);
    color: #fcd34d;
  }
  .finding-status-tag.tag-pass {
    background: rgba(34, 197, 94, 0.18);
    border: 1px solid rgba(34, 197, 94, 0.38);
    color: #86efac;
  }

  .findings-list-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow-y: auto;
    margin-top: 16px;
    padding-right: 4px;
    max-height: 52vh;
  }

  .empty-findings {
    text-align: center;
    padding: 32px 20px;
    background: rgba(10, 11, 18, 0.5);
    border-radius: 10px;
    border: 1px dashed rgba(255, 255, 255, 0.12);
  }
  .empty-findings-text {
    font-size: 13.5px;
    color: #94a3b8;
    margin: 0;
    line-height: 1.55;
  }

  .finding-card {
    background: rgba(10, 11, 18, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 15px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color 0.2s ease, background 0.2s ease;
  }
  .finding-card:hover {
    background: rgba(18, 20, 28, 0.9);
  }

  .finding-card.severity-critical { border-color: rgba(239, 68, 68, 0.38); }
  .finding-card.severity-high { border-color: rgba(249, 115, 22, 0.38); }
  .finding-card.severity-medium { border-color: rgba(234, 179, 8, 0.34); }
  .finding-card.severity-low { border-color: rgba(99, 102, 241, 0.34); }
  .finding-card.severity-info { border-color: rgba(6, 182, 212, 0.34); }

  .finding-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .finding-title-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .finding-number {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    color: #94a3b8;
    font-size: 12px;
  }

  .severity-badge {
    font-family: 'Outfit', sans-serif;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 2px 7px;
    border-radius: 6px;
    letter-spacing: 0.03em;
  }
  .severity-badge.sev-critical {
    background: rgba(239, 68, 68, 0.18);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.38);
  }
  .severity-badge.sev-high {
    background: rgba(249, 115, 22, 0.18);
    color: #fdba74;
    border: 1px solid rgba(249, 115, 22, 0.38);
  }
  .severity-badge.sev-medium {
    background: rgba(234, 179, 8, 0.18);
    color: #fde047;
    border: 1px solid rgba(234, 179, 8, 0.38);
  }
  .severity-badge.sev-low {
    background: rgba(99, 102, 241, 0.18);
    color: #a5b4fc;
    border: 1px solid rgba(99, 102, 241, 0.38);
  }
  .severity-badge.sev-info {
    background: rgba(6, 182, 212, 0.18);
    color: #67e8f9;
    border: 1px solid rgba(6, 182, 212, 0.38);
  }

  .category-badge {
    background: rgba(99, 102, 241, 0.14);
    color: #c7d2fe;
    border: 1px solid rgba(99, 102, 241, 0.28);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 6px;
  }

  .finding-body {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 13px;
    line-height: 1.5;
  }

  .finding-row {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .finding-label {
    font-size: 11px;
    font-weight: 600;
    color: #94a3b8;
    letter-spacing: 0.02em;
  }

  .problem-text {
    color: #f8fafc;
    font-weight: 500;
  }

  .evidence-text {
    color: #cbd5e1;
    background: rgba(255, 255, 255, 0.03);
    padding: 7px 10px;
    border-radius: 6px;
    border: 1px solid rgba(148, 163, 184, 0.2);
    font-size: 12px;
  }

  .recommendation-row {
    margin-top: 4px;
    background: rgba(99, 102, 241, 0.08);
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid rgba(99, 102, 241, 0.24);
  }

  .recommendation-text {
    color: #a5b4fc;
    font-size: 12.5px;
    font-weight: 500;
  }

  @media (max-width: 900px) {
    .panel-container {
      padding: 14px 14px 24px;
    }
    .form-row {
      flex-direction: column;
    }
    .history-search-input {
      width: 100%;
    }
    .search-input-wrap {
      flex: 1;
      min-width: 180px;
    }
    .optional-summary-pill {
      margin-left: 0;
    }
  }
</style>
