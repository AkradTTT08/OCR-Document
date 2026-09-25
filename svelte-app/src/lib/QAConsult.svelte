<script>
  import { createEventDispatcher, onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { authUser, authEmail } from "./authStore.js";
  import { qaHistory, selectedHistory, loadQAHistoryFromDB, selectedProjectStore, qaSessionGroups, activeQAContext, loadQAGroupsFromDB, activeSidebarGroup, activeScanStatus, allGroups, qaRefinementFeedback } from "./qaHistoryStore.js";
  import GateResultModal from "./GateResultModal.svelte";
  import ProjectSelection from "./ProjectSelection.svelte";
  import SpectraLoading from "./SpectraLoading.svelte";
  import { MASTER_DOC_TYPES } from "./constants.js";

  const dispatch = createEventDispatcher();

  let showGateModal = false;
  /** @type {any} */
  let gateResultData = null;

  /** @type {any[]} */
  let skills = [];
  let docTypes = MASTER_DOC_TYPES;
  let selectedSkill = "";
  
  /** @type {any[]} */
  let projects = [];
  /** @type {any[]} */
  let exitCriteriaTemplates = [];
  let isCheckingCriteria = false;

  async function loadExitCriteriaTemplates(projectId = null) {
    try {
      isCheckingCriteria = true;
      const url = projectId 
        ? `/api/exit-criteria/templates?project_id=${projectId}` 
        : `/api/exit-criteria/templates`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        exitCriteriaTemplates = data.templates || [];
      }
    } catch (err) {
      console.error("Failed to load Exit Criteria templates:", err);
    } finally {
      isCheckingCriteria = false;
    }
  }
  
  // Use store for selected project so App.svelte can filter history
  $: selectedProjectObj = $selectedProjectStore;
  /** @param {any} p */
  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  onMount(async () => {
    loadQAGroupsFromDB();
    loadQAHistoryFromDB();

    // Load Skills (separate try/catch so failure won't block projects)
    try {
      const resSkills = await fetch("/api/skills");
      if (resSkills.ok) {
        const data = await resSkills.json();
        skills = (data.skills || []).filter(s =>
          !s.skill_name?.startsWith('[Exit Criteria]') &&
          !s.skill_name?.includes('Exit Criteria')
        );
      }
    } catch (err) {
      console.error("Failed to load skills:", err);
    }

    // Load Doc Types & Exit Criteria
    try { await loadDocTypes(); } catch (err) { console.error("Failed to load doc types:", err); }
    try { await loadExitCriteriaTemplates(selectedProjectObj?.id || selectedProjectObj?.project_id); } catch (err) { console.error("Failed to load exit criteria:", err); }

    // Load Projects — must always run independently
    try {
      const resProjects = await fetch("/api/projects");
      if (resProjects.ok) {
        const pData = await resProjects.json();
        projects = pData.projects || [];
      } else {
        console.error("Projects API error:", resProjects.status);
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }

    // Auto-fill email from logged-in user or user profile API
    async function resolveUserEmail() {
      if (emailList.length > 0) return;
      
      const localCandidate = ($authEmail || localStorage.getItem('auth_email') || localStorage.getItem('last_qa_email') || localStorage.getItem('remembered_email') || '').trim();
      if (localCandidate && localCandidate.includes('@')) {
        const parts = localCandidate.split(',').map(p => p.trim()).filter(p => p.includes('@'));
        if (parts.length > 0) {
          emailList = [...parts];
          userEmailInitialized = true;
          return;
        }
      }

      // Query /api/users to find current logged-in user's email if not present in localStorage
      try {
        const uRes = await fetch("/api/users");
        if (uRes.ok) {
          const uData = await uRes.json();
          const curUser = ($authUser || localStorage.getItem('auth_user') || '').trim().toLowerCase();
          const matched = (uData || []).find((/** @type {any} */ u) => 
            (u.username && u.username.toLowerCase() === curUser) ||
            (u.display_name && u.display_name.toLowerCase() === curUser)
          );
          if (matched && matched.email && matched.email.includes('@')) {
            const foundEmail = matched.email.trim();
            localStorage.setItem('auth_email', foundEmail);
            if (!emailList.includes(foundEmail)) {
              emailList = [foundEmail];
              userEmailInitialized = true;
            }
          }
        }
      } catch (err) {
        console.warn("Could not fetch user profile for email auto-fill:", err);
      }
    }
    resolveUserEmail();
  });

  $: if ($activeQAContext && projects.length > 0) {
    const ctx = $activeQAContext;
    activeQAContext.set(null); // Clear it
    
    selectedProjectStore.set(ctx.project);
    scanGroupName = ctx.group_name;
    scanGroupType = ctx.group_type;
    isGroupNameSet = true;

    // Check if this group is currently scanning
    const scan = $activeScanStatus;
    const cleanCurrent = String(ctx.group_name || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
    const cleanScanning = scan ? String(scan.groupName || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase() : '';
    if (scan && cleanScanning === cleanCurrent) {
      isProcessing = true;
      scanResult = null;
      processStatus = scan.processStatus || "กำลังวิเคราะห์ข้อมูลเบื้องหลัง...";
      progressPct = scan.progressPct || 50;
    } else {
      isProcessing = false;
      scanResult = null;
      file = null;
    }
  }

  $: if ($activeScanStatus && $activeScanStatus.isProcessing) {
    const cleanCurrent = String(scanGroupName || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
    const cleanScanning = String($activeScanStatus.groupName || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
    if (cleanCurrent === cleanScanning) {
      isProcessing = true;
      processStatus = $activeScanStatus.processStatus || processStatus;
      progressPct = $activeScanStatus.progressPct || progressPct;
    }
  }

  $: if ($selectedHistory && projects.length > 0) {
    const item = $selectedHistory;
    selectedHistory.set(null); // Clear it so it doesn't re-trigger

    if (item.is_processing) {
      scanGroupName = item.group_name || 'General';
      scanGroupType = item.group_type || '';
      isGroupNameSet = true;
      
      const p = projects.find(p => String(p.id) === String(item.project_id) || String(p.project_id) === String(item.project_id) || (p.project_code && item.project_code && p.project_code === item.project_code));
      if (p) {
        selectedProjectStore.set(p);
      }
      
      isProcessing = true;
      scanResult = null;
      processStatus = ($activeScanStatus && $activeScanStatus.processStatus) || "กำลังวิเคราะห์ข้อมูลเบื้องหลัง...";
      progressPct = ($activeScanStatus && $activeScanStatus.progressPct) || 50;
    } else {
      const baseName = item.filename ? item.filename.replace(/\.[^/.]+$/, "") : "";
      const safeName = baseName.replace(/[^\w\-.]/g, '_');
      const computedExcelUrl = `/api/qa_report/download/QA_Report_${safeName}_${item.id}.xlsx`;

      const evalData = item.exit_criteria_eval || synthesizeExitCriteria({ qa_findings: item.qa_findings, report: item.report, doc_type: item.docType });

      scanResult = {
        status: 'success',
        report: item.report,
        email: item.email || email, // If email is in DB, use it, otherwise use current
        total_pages: item.total_pages,
        doc_type: item.docType,
        filename: item.filename,
        emailSent: false,
        excel_url: computedExcelUrl,
        qa_findings: item.qa_findings,
        exit_criteria_eval: evalData
      };

      scanGroupName = item.group_name || 'General';
      scanGroupType = item.group_type || '';
      isGroupNameSet = true;

      const p = projects.find(p => String(p.id) === String(item.project_id) || String(p.project_id) === String(item.project_id) || (p.project_code && item.project_code && p.project_code === item.project_code));
      if (p) {
        selectedProjectStore.set(p);
      }
    }
  }

  /** @param {any} res */
  function synthesizeExitCriteria(res) {
    if (!res) return null;
    const findings = res.qa_findings || [];
    const highCritical = findings.filter(f => {
      const sev = (f.severity || '').toLowerCase();
      return sev === 'critical' || sev === 'high';
    });
    const medium = findings.filter(f => (f.severity || '').toLowerCase() === 'medium');
    const typos = findings.filter(f => {
      const ct = (f.check_type || '').toLowerCase();
      const iss = (f.issue || '').toLowerCase();
      return ct.includes('spell') || ct.includes('คำผิด') || iss.includes('คำผิด') || iss.includes('สะกด');
    });

    const defaultItems = [
      { item_code: '1.1', category: 'Defect & Bug', question_text: 'ไม่มี Defect ระดับ Critical / High คงค้างในเอกสาร', target_metric: '0 Critical/High Bugs (ผ่าน 100%)', severity: 'Critical', is_mandatory: true },
      { item_code: '1.2', category: 'Defect & Bug', question_text: 'ไม่มีข้อผิดพลาดด้าน Logic การคำนวณ หรือการไหลของกระบวนการทำงาน (Process Flow)', target_metric: '100% Correct Logic', severity: 'Critical', is_mandatory: true },
      { item_code: '1.3', category: 'Defect & Bug', question_text: 'ไม่มี Broken Links, รหัสอ้างอิงที่ไม่ตรงกัน หรือภาพประกอบที่ไม่ถูกต้อง', target_metric: '0 Broken Links/Refs', severity: 'Major', is_mandatory: true },
      { item_code: '2.1', category: 'Content Completeness', question_text: 'มีเนื้อหาครบถ้วนตาม Scope, Objective และ Requirement ที่ตกลงไว้', target_metric: '100% Scope Coverage', severity: 'Critical', is_mandatory: true },
      { item_code: '2.2', category: 'Content Completeness', question_text: 'มีรายละเอียด Input / Output / Data Dictionary ครบถ้วนชัดเจน', target_metric: '100% Data Specs', severity: 'Major', is_mandatory: true },
      { item_code: '2.3', category: 'Content Completeness', question_text: 'ครอบคลุม Exception Cases, Edge Cases และ Error Handling', target_metric: '100% Edge Cases Handling', severity: 'Major', is_mandatory: true },
      { item_code: '2.4', category: 'Content Completeness', question_text: 'มีเกณฑ์การยอมรับ (Acceptance Criteria / Definition of Done) ชัดเจนทุกหัวข้อ', target_metric: '100% Defined Criteria', severity: 'Major', is_mandatory: true },
      { item_code: '3.1', category: 'Formatting & Quality', question_text: 'ไม่มีคำผิด (Spelling / Typos) ในคำศัพท์เฉพาะทาง, ภาษาไทย และภาษาอังกฤษ', target_metric: '0 Typos (ความถูกต้อง 100%)', severity: 'Minor', is_mandatory: false },
      { item_code: '3.2', category: 'Formatting & Quality', question_text: 'รูปแบบฟอนต์, ขนาดตัวอักษร, ระยะย่อหน้า และหัวข้อ มีความสม่ำเสมอทั้งเอกสาร', target_metric: '100% Style Consistency', severity: 'Minor', is_mandatory: false },
      { item_code: '3.3', category: 'Formatting & Quality', question_text: 'การจัดวางตาราง, รูปภาพ และ Diagram มีความชัดเจน อ่านง่าย ไม่ตกขอบ', target_metric: '100% Visual Clarity', severity: 'Minor', is_mandatory: false },
      { item_code: '4.1', category: 'Governance & Control', question_text: 'มีการระบุ Document Title, Version Number, วันที่อัปเดต และชื่อผู้แต่ง/ผู้แก้ไขชัดเจน', target_metric: '100% Header & Metadata', severity: 'Major', is_mandatory: true },
      { item_code: '4.2', category: 'Governance & Control', question_text: 'มีประวัติการแก้ไข (Document History / Revision Log) สรุปการเปลี่ยนแปลงในแต่ละเวอร์ชัน', target_metric: '100% Logged History', severity: 'Minor', is_mandatory: false },
      { item_code: '4.3', category: 'Governance & Control', question_text: 'จัดทำเอกสารฉบับสะอาด (Clean Version) ที่ปิด Track Changes และ Remove Comment ร่างออกเรียบร้อย', target_metric: '0 Draft Comments (ฉบับสะอาด 100%)', severity: 'Major', is_mandatory: true }
    ];

    let passedCnt = 0;
    let failedCnt = 0;
    let naCnt = 0;
    let hasCat12Fail = false;

    const items = defaultItems.map(d => {
      let st = 'PASS';
      let rem = 'ตรวจสอบแล้วตรงตามเกณฑ์มาตรฐาน';
      let evid = '';

      if (d.item_code === '1.1' && highCritical.length > 0) {
        st = 'FAIL';
        rem = `พบประเด็นความรุนแรง Critical/High จำนวน ${highCritical.length} รายการ`;
        evid = highCritical[0].issue || '';
      } else if (d.item_code === '3.1' && typos.length > 0) {
        st = 'FAIL';
        rem = `พบคำผิดหรือการสะกดคำไม่ถูกต้อง ${typos.length} รายการ`;
        evid = typos[0].issue || '';
      }

      if (st === 'PASS') passedCnt++;
      else if (st === 'FAIL') {
        failedCnt++;
        if (d.item_code.startsWith('1.') || d.item_code.startsWith('2.')) {
          hasCat12Fail = true;
        }
      } else {
        naCnt++;
      }

      return {
        ...d,
        item_id: `synth-${d.item_code}`,
        status: st,
        remarks: rem,
        evidence_text: evid
      };
    });

    let finalStatus = 'PASSED';
    let summaryRemarks = 'เอกสารผ่านเกณฑ์มาตรฐาน Exit Criteria ครบถ้วนบริบูรณ์ 100%';

    if (failedCnt > 0) {
      if (hasCat12Fail) {
        finalStatus = 'REJECTED';
        summaryRemarks = 'เอกสารไม่ผ่านเกณฑ์ Exit Criteria สาระสำคัญ (หมวด 1 หรือ 2) ต้องแก้ไขและส่งกลับมาตรวจใหม่';
      } else {
        finalStatus = 'CONDITIONAL_PASSED';
        summaryRemarks = 'เอกสารผ่านเกณฑ์สาระสำคัญ (หมวด 1, 2, 4) พบข้อสังเกตเล็กน้อยในหมวดจัดหน้า/คำผิด (หมวด 3) สามารถแก้ไขและส่ง Final Copy ได้เลย';
      }
    }

    const totalValid = items.length - naCnt;
    const scorePct = totalValid > 0 ? Math.round((passedCnt / totalValid) * 100) : 100;

    return {
      template_id: 'universal-default',
      template_title: 'Universal Document Exit Criteria',
      status: finalStatus,
      total_items: items.length,
      passed_items: passedCnt,
      failed_items: failedCnt,
      na_items: naCnt,
      score_percentage: scorePct,
      summary_remarks: summaryRemarks,
      items: items
    };
  }

  async function loadDocTypes(projectId = null) {
    try {
      let url = "/api/doc_types";
      if (projectId) url += `?project_id=${projectId}`;
      const res = await fetch(url);
      if (res.ok) {
        docTypes = await res.json();
      }
    } catch (err) {
      console.error("Failed to load doc types:", err);
    }
  }

  $: if (selectedProjectObj) {
    const pId = selectedProjectObj.id || selectedProjectObj.project_id;
    loadDocTypes(pId);
    loadExitCriteriaTemplates(pId);
    loadQAGroupsFromDB();
    loadQAHistoryFromDB();
  } else {
    loadDocTypes();
    loadExitCriteriaTemplates();
  }

  $: currentProjectGroups = $allGroups.filter(g => {
    if (!selectedProjectObj) return false;
    const pId = String(selectedProjectObj.id || selectedProjectObj.project_id || '');
    const pCode = String(selectedProjectObj.project_code || '').trim().toLowerCase();
    const gPid = String(g.project_id || '');
    const gCode = String(g.project_code || '').trim().toLowerCase();
    return !gPid || !pId || gPid === pId || (pCode && gCode && gCode === pCode);
  });

  $: currentProjectHistory = $qaHistory.filter(h => {
    if (!selectedProjectObj) return false;
    const pId = String(selectedProjectObj.id || selectedProjectObj.project_id || '');
    const pCode = String(selectedProjectObj.project_code || '').trim().toLowerCase();
    const hPid = String(h.project_id || '');
    const hCode = String(h.project_code || '').trim().toLowerCase();
    const matchProj = !hPid || !pId || hPid === pId || (pCode && hCode && hCode === pCode);
    if (!matchProj) return false;

    if ($activeSidebarGroup && $activeSidebarGroup.group_name) {
      const cleanHGroup = String(h.group_name || 'General').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
      const cleanCtxGroup = String($activeSidebarGroup.group_name || 'General').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
      const rawHGroup = String(h.group_name || 'General').trim().toLowerCase();
      const rawCtxGroup = String($activeSidebarGroup.group_name || 'General').trim().toLowerCase();
      return rawHGroup === rawCtxGroup || cleanHGroup === cleanCtxGroup || cleanHGroup.includes(cleanCtxGroup) || cleanCtxGroup.includes(cleanHGroup);
    }
    return true;
  });

  $: targetGroupName = scanGroupName || (scanResult && scanResult.group_name) || ($activeSidebarGroup && $activeSidebarGroup.group_name) || '';

  $: currentGroupHistory = $qaHistory.filter(h => {
    if (!selectedProjectObj) return false;
    const pId = String(selectedProjectObj.id || selectedProjectObj.project_id || '');
    const pCode = String(selectedProjectObj.project_code || '').trim().toLowerCase();
    const hPid = String(h.project_id || '');
    const hCode = String(h.project_code || '').trim().toLowerCase();
    const matchProj = !hPid || !pId || hPid === pId || (pCode && hCode && hCode === pCode);
    if (!matchProj) return false;

    if (targetGroupName) {
      const cleanHGroup = String(h.group_name || 'General').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
      const cleanTargetGroup = String(targetGroupName || 'General').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
      const rawHGroup = String(h.group_name || 'General').trim().toLowerCase();
      const rawTargetGroup = String(targetGroupName || 'General').trim().toLowerCase();
      return rawHGroup === rawTargetGroup || cleanHGroup === cleanTargetGroup || cleanHGroup.includes(cleanTargetGroup) || cleanTargetGroup.includes(cleanHGroup);
    }
    return true;
  });

  function selectExistingGroup(g) {
    const cleanName = String(g.group_name || 'General').replace(/^\[.*?\]\s*/, '').trim();
    scanGroupName = cleanName;
    scanGroupType = g.group_type || 'Project Plan';
    isGroupNameSet = true;
    activeSidebarGroup.set({
      project: selectedProjectObj,
      group_name: cleanName,
      group_type: scanGroupType,
      project_id: selectedProjectObj.id || selectedProjectObj.project_id
    });
  }

  let showDeleteGroupModal = false;
  let groupToDelete = null;
  let isDeletingGroup = false;

  function requestDeleteGroup(group) {
    groupToDelete = group;
    showDeleteGroupModal = true;
  }

  function cancelDeleteGroup() {
    showDeleteGroupModal = false;
    groupToDelete = null;
  }

  async function executeDeleteGroup() {
    if (!groupToDelete) return;
    const group = groupToDelete;
    const gName = group.group_name || 'General';
    isDeletingGroup = true;
    try {
      const res = await fetch("/api/qa_groups/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: group.project_id,
          group_name: gName
        })
      });
      if (res.ok) {
        toast(`ลบกลุ่ม "${gName}" เรียบร้อยแล้ว`, "success");
        qaSessionGroups.update(gs => gs.filter(g => !(g.project_id === group.project_id && g.group_name === gName)));
        if ($activeSidebarGroup && String($activeSidebarGroup.group_name || '').toLowerCase() === String(gName).toLowerCase()) {
          activeSidebarGroup.set(null);
        }
        await loadQAGroupsFromDB();
        await loadQAHistoryFromDB();
        showDeleteGroupModal = false;
        groupToDelete = null;
      } else {
        const err = await res.json();
        toast(err.error || "ไม่สามารถลบกลุ่มได้", "error");
      }
    } catch (e) {
      console.error(e);
      toast("เกิดข้อผิดพลาดในการลบกลุ่ม", "error");
    } finally {
      isDeletingGroup = false;
    }
  }

  function formatHistoryTime(dStr) {
    if (!dStr) return "";
    let parsed = dStr;
    if (!parsed.endsWith('Z') && !parsed.includes('+')) parsed += 'Z';
    const d = new Date(parsed);
    return d.toLocaleString('th-TH', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  let selectedDocTypes = [];
  let selectedSkills = [];

  // All skills are available for selection
  $: filteredSkills = skills;

  let file = null;

  const getInitialUserEmail = () => {
    const fromAuthEmail = ($authEmail || '').trim();
    if (fromAuthEmail && fromAuthEmail.includes('@')) return [fromAuthEmail];

    const storedAuthEmail = (localStorage.getItem('auth_email') || '').trim();
    if (storedAuthEmail && storedAuthEmail.includes('@')) return [storedAuthEmail];

    const lastQa = (localStorage.getItem('last_qa_email') || '').trim();
    if (lastQa && lastQa.includes('@')) {
      const parts = lastQa.split(',').map(p => p.trim()).filter(p => p.includes('@'));
      if (parts.length > 0) return parts;
    }

    const fromAuth = ($authUser || '').trim();
    if (fromAuth && fromAuth.includes('@')) return [fromAuth];

    const u = (localStorage.getItem('auth_user') || '').trim();
    if (u && u.includes('@')) return [u];

    const rem = (localStorage.getItem('remembered_email') || '').trim();
    if (rem && rem.includes('@')) return [rem];

    return [];
  };

  let emailInput = "";
  let emailList = getInitialUserEmail();
  let userEmailInitialized = emailList.length > 0;
  $: email = emailList.join(",");

  // Automatically keep user email in emailList if available
  $: if (($authEmail || $authUser) && emailList.length === 0) {
    const cand = ($authEmail || '').trim() || (localStorage.getItem('auth_email') || '').trim() || (($authUser || '').includes('@') ? ($authUser || '').trim() : '');
    if (cand && cand.includes('@') && !emailList.includes(cand)) {
      emailList = [cand];
      userEmailInitialized = true;
    }
  }

  // Save last used QA email to localStorage whenever emailList changes
  $: if (emailList.length > 0) {
    try {
      localStorage.setItem('last_qa_email', emailList.join(','));
    } catch(e) {}
  }

  function addEmail() {
    if (emailInput && emailInput.includes("@")) {
      const emailTrimmed = emailInput.trim();
      if (!emailList.includes(emailTrimmed)) {
        emailList = [...emailList, emailTrimmed];
      }
      emailInput = "";
    } else if (emailInput) {
      toast("รูปแบบอีเมลไม่ถูกต้อง", "warning");
    }
  }

  function removeEmail(index) {
    emailList = emailList.filter((_, i) => i !== index);
  }
  
  function handleEmailKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addEmail();
    }
  }

  let isDragging = false;
  let fileInput;

  let isProcessing = false;
  let processStatus = "";
  let progressPct = 0;
  let scanResult = null;
  let scanGroupName = "";
  let scanGroupType = "Project Plan";
  let isGroupNameSet = false;
  let showCreateGroupModal = false;

  function openCreateGroupModal() {
    scanGroupName = "";
    scanGroupType = "Project Plan";
    showCreateGroupModal = true;
  }

  function closeCreateGroupModal() {
    showCreateGroupModal = false;
  }

  let isSendingEmail = false;
  let showConfirmModal = false;
  let showSuccessModal = false;

  let selectedCriteriaTab = 'all';

  // Criteria Group Tabs extraction from scan result
  $: criteriaTabsList = (() => {
    const evalData = scanResult?.exit_criteria_eval;
    if (!evalData || !evalData.items || evalData.items.length === 0) return [];

    const groupMap = new Map();

    evalData.items.forEach((/** @type {any} */ item) => {
      let groupKey = 'universal';
      let groupTitle = 'เกณฑ์มาตรฐานกลาง (Universal Document)';
      let cleanCategory = item.category || '';

      const match = cleanCategory.match(/^\[(.*?)\]\s*(.*)$/);
      if (match) {
        const prefix = match[1].trim();
        cleanCategory = match[2].trim();
        if (prefix.includes('เกณฑ์กลาง') || prefix.toUpperCase() === 'ALL' || prefix.toLowerCase().includes('universal')) {
          groupKey = 'universal';
          groupTitle = 'เกณฑ์มาตรฐานกลาง (Universal Document)';
        } else {
          groupKey = prefix.toLowerCase().replace(/[^a-z0-9_\u0E00-\u0E7F]/gi, '_');
          groupTitle = prefix;
        }
      } else {
        groupKey = 'universal';
        groupTitle = 'เกณฑ์มาตรฐานกลาง (Universal Document)';
      }

      if (!groupMap.has(groupKey)) {
        groupMap.set(groupKey, {
          key: groupKey,
          title: groupTitle,
          items: []
        });
      }
      groupMap.get(groupKey).items.push({
        ...item,
        displayCategory: cleanCategory,
        groupTag: match ? match[1].trim() : ''
      });
    });

    const groups = Array.from(groupMap.values());

    return groups.map(g => {
      const passed = g.items.filter((/** @type {any} */ i) => i.status === 'PASS').length;
      const failed = g.items.filter((/** @type {any} */ i) => i.status === 'FAIL').length;
      const na = g.items.filter((/** @type {any} */ i) => i.status === 'NA' || i.status === 'N/A').length;
      const totalValid = g.items.length - na;
      const score = totalValid > 0 ? Math.round((passed / totalValid) * 100) : 100;
      
      const hasCat12Fail = g.items.some((/** @type {any} */ i) => i.status === 'FAIL' && (
        (i.category || '').includes('Defect') || 
        (i.category || '').includes('Content') || 
        (i.item_code || '').startsWith('1.') || 
        (i.item_code || '').startsWith('2.')
      ));

      let status = 'PASSED';
      if (failed > 0) {
        status = hasCat12Fail ? 'REJECTED' : 'CONDITIONAL_PASSED';
      }

      return {
        ...g,
        score,
        passed,
        failed,
        na,
        total: g.items.length,
        status
      };
    });
  })();

  $: activeTabItems = (() => {
    const evalData = scanResult?.exit_criteria_eval;
    if (!evalData || !evalData.items) return [];

    if (selectedCriteriaTab === 'all') {
      return evalData.items.map((/** @type {any} */ item) => {
        const match = (item.category || '').match(/^\[(.*?)\]\s*(.*)$/);
        return {
          ...item,
          displayCategory: match ? match[2].trim() : item.category,
          groupTag: match ? match[1].trim() : ''
        };
      });
    }

    const found = criteriaTabsList.find(g => g.key === selectedCriteriaTab);
    if (found) {
      return found.items;
    }

    return evalData.items;
  })();

  $: activeTabStats = (() => {
    const evalData = scanResult?.exit_criteria_eval;
    if (!evalData) return { score: 100, passed: 0, failed: 0, na: 0, status: 'PASSED' };

    if (selectedCriteriaTab === 'all') {
      return {
        score: evalData.score_percentage ?? 100,
        passed: evalData.passed_items ?? 0,
        failed: evalData.failed_items ?? 0,
        na: evalData.na_items ?? 0,
        status: evalData.status || 'PASSED'
      };
    }

    const found = criteriaTabsList.find(g => g.key === selectedCriteriaTab);
    if (found) {
      return {
        score: found.score,
        passed: found.passed,
        failed: found.failed,
        na: found.na,
        status: found.status
      };
    }

    return {
      score: evalData.score_percentage ?? 100,
      passed: evalData.passed_items ?? 0,
      failed: evalData.failed_items ?? 0,
      na: evalData.na_items ?? 0,
      status: evalData.status || 'PASSED'
    };
  })();

  let docTypeOpen = false;
  let skillOpen = false;
  let groupTypeOpen = false;
  const masterGroupTypes = MASTER_DOC_TYPES;

  $: matchedCriteriaTemplate = exitCriteriaTemplates.find(t => 
    t.is_active && 
    t.doc_type && 
    t.doc_type.trim().toUpperCase() === scanGroupType.trim().toUpperCase() &&
    t.doc_type.trim().toUpperCase() !== 'ALL'
  );
  $: hasUniversalTemplate = exitCriteriaTemplates.some(t => 
    t.is_active && 
    t.doc_type && 
    t.doc_type.trim().toUpperCase() === 'ALL'
  );

  function toggleDocType(type) {
    if (selectedDocTypes.includes(type)) {
      selectedDocTypes = selectedDocTypes.filter(t => t !== type);
    } else {
      selectedDocTypes = [...selectedDocTypes, type];
    }
  }

  function toggleSkill(skillId) {
    if (selectedSkills.includes(skillId)) {
      selectedSkills = selectedSkills.filter(s => s !== skillId);
    } else {
      selectedSkills = [...selectedSkills, skillId];
    }
  }

  function handleDragEnter(e) {
    e.preventDefault();
    isDragging = true;
  }
  function handleDragLeave(e) {
    e.preventDefault();
    isDragging = false;
  }
  
  async function confirmGroup() {
    if (!scanGroupName.trim()) return;
    
    const pId = selectedProjectObj?.id || selectedProjectObj?.project_id;
    // Clean group name by removing any leading bracketed type e.g. "[Project Plan] II" -> "II"
    const groupName = scanGroupName.replace(/^\[.*?\]\s*/, '').trim();
    scanGroupName = groupName;
    
    // Save to DB via API
    try {
      const res = await fetch("/api/qa_groups", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pId,
          group_name: groupName,
          group_type: scanGroupType
        })
      });
      if (res.ok) {
        // Reload groups from DB so sidebar updates immediately
        await loadQAGroupsFromDB();
      } else {
        console.error("Failed to save QA group to DB");
      }
    } catch (err) {
      console.error("Error saving QA group:", err);
    }
    
    // Fallback/immediate UI update
    qaSessionGroups.update(groups => {
      if (!groups.find(g => g.group_name === groupName && g.project_id === pId)) {
        return [...groups, { group_name: groupName, group_type: scanGroupType, project_id: pId, project_code: selectedProjectObj.project_code || '' }];
      }
      return groups;
    });
    
    activeSidebarGroup.set({
      project: selectedProjectObj,
      group_name: groupName,
      group_type: scanGroupType,
      project_id: pId
    });
    
    showCreateGroupModal = false;
    isGroupNameSet = true;
  }
  function handleDrop(e) {
    e.preventDefault();
    isDragging = false;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      file = e.dataTransfer.files[0];
    }
  }
  function handleFileSelect(e) {
    if (e.target.files && e.target.files.length > 0) {
      file = e.target.files[0];
    }
  }
  function triggerFileInput() {
    fileInput.click();
  }
  function removeFile() {
    file = null;
    if (fileInput) fileInput.value = "";
  }

  async function processQAConsult() {
    if (emailInput.trim() !== "") {
      const emailTrimmed = emailInput.trim();
      if (emailTrimmed.includes("@") && !emailList.includes(emailTrimmed)) {
        emailList = [...emailList, emailTrimmed];
      }
      emailInput = "";
    }

    const finalEmail = (emailList && emailList.length > 0) 
      ? emailList.join(",") 
      : (emailInput.trim() || email || "");

    if (!file) {
      toast("กรุณาอัปโหลดไฟล์เอกสารก่อน", "warning");
      return;
    }
    if (!finalEmail || finalEmail.trim() === "") {
      toast("กรุณากรอกอีเมลสำหรับรับผลการตรวจสอบ", "warning");
      return;
    }

    isProcessing = true;
    scanResult = null;
    progressPct = 10;
    processStatus = "กำลังอัปโหลดเอกสารและเริ่มประมวลผล...";

    const cleanGroupName = scanGroupName.replace(/^\[.*?\]\s*/, '').trim() || 'General';
    scanGroupName = cleanGroupName;
    const pId = selectedProjectObj?.id || selectedProjectObj?.project_id;

    // Keep sidebar active group in sync
    activeSidebarGroup.set({
      project: selectedProjectObj,
      group_name: cleanGroupName,
      group_type: scanGroupType,
      project_id: pId
    });

    const pendingItem = {
      id: 'pending-' + Date.now(),
      filename: file.name,
      group_name: cleanGroupName,
      group_type: scanGroupType,
      project_id: pId,
      date: new Date().toISOString(),
      is_processing: true
    };
    qaHistory.update(h => [pendingItem, ...h]);

    activeScanStatus.set({
      isProcessing: true,
      projectId: pId,
      groupName: cleanGroupName,
      groupType: scanGroupType,
      filename: file.name,
      processStatus: "กำลังอัปโหลดเอกสารและเริ่มประมวลผล...",
      progressPct: 10,
      pendingId: pendingItem.id
    });

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", JSON.stringify(selectedDocTypes));
    formData.append("email", finalEmail);
    formData.append("skill_id", JSON.stringify(selectedSkills));
    if (selectedProjectObj) {
      formData.append("project_id", pId);
      formData.append("project_name", `${selectedProjectObj.project_code || ''} ${selectedProjectObj.name || ''}`.trim() || 'Unknown Project');
    }
    formData.append("group_name", cleanGroupName);
    formData.append("group_type", scanGroupType);

    try {
      // Create a stream request
      const response = await fetch("/api/qa_consult", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? ""; // keep incomplete chunk

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.substring(6);
            if (!dataStr.trim()) continue;
            
            let data;
            try {
              data = JSON.parse(dataStr);
            } catch(e) {
              console.warn("Parse error:", e);
              continue;
            }

            if (data.type === "progress") {
              processStatus = data.message;
              progressPct = data.pct;
              activeScanStatus.update(s => s ? { ...s, processStatus: data.message, progressPct: data.pct } : s);
            } else if (data.type === "complete") {
              progressPct = 100;
              scanResult = data.result;
              isProcessing = false;
              activeScanStatus.set(null);

              // Immediately save completed transaction into qaHistory store
              const completedItem = {
                id: scanResult?.id || ('scan-' + Date.now()),
                filename: scanResult?.filename || file.name,
                group_name: cleanGroupName,
                group_type: scanGroupType,
                project_id: pId || (selectedProjectObj?.id || selectedProjectObj?.project_id),
                project_code: selectedProjectObj?.project_code || '',
                docType: scanResult?.doc_type || 'General',
                report: scanResult?.report,
                email: scanResult?.email || finalEmail,
                total_pages: scanResult?.total_pages,
                qa_findings: scanResult?.qa_findings,
                exit_criteria_eval: scanResult?.exit_criteria_eval,
                date: new Date().toISOString(),
                is_processing: false
              };

              qaHistory.update(h => [completedItem, ...h.filter(item => item.id !== pendingItem.id && item.id !== completedItem.id)]);
              
              await loadQAHistoryFromDB();
              await loadQAGroupsFromDB();
              if (scanResult) {
                if (!scanResult.exit_criteria_eval) {
                  scanResult.exit_criteria_eval = synthesizeExitCriteria(scanResult);
                }
                gateResultData = scanResult.exit_criteria_eval;
                showGateModal = true;
              }
            } else if (data.type === "error") {
              throw new Error(data.message);
            }
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast(`เกิดข้อผิดพลาด: ${msg}`, "error");
      isProcessing = false;
      activeScanStatus.set(null);
      qaHistory.update(h => h.filter(item => item.id !== pendingItem.id));
    } finally {
      activeScanStatus.set(null);
      await loadQAHistoryFromDB();
      await loadQAGroupsFromDB();
    }
  }

  function sendEmail() {
    showConfirmModal = true;
  }

  async function executeSendEmail() {
    isSendingEmail = true;
    try {
      const response = await fetch("/api/qa_send_email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: scanResult.email || email,
          docType: scanResult.doc_type || selectedDocTypes.join(", ") || 'General Document',
          filename: scanResult.filename,
          report: scanResult.report,
          excel_url: scanResult.excel_url || '',
          exit_criteria_eval: scanResult.exit_criteria_eval || null
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }

      const data = await response.json();
      if (data.success) {
        showConfirmModal = false;
        showSuccessModal = true;
        scanResult.emailSent = true;
      } else {
        throw new Error(data.error || "Unknown error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการส่งอีเมล: ${err.message}`, "error");
      showConfirmModal = false;
    } finally {
      isSendingEmail = false;
    }
  }

  function resetForm() {
    file = null;
    scanResult = null;
    isProcessing = false;
    isGroupNameSet = false;
    scanGroupName = "";
    scanGroupType = "Project Plan";
    processStatus = "";
    if (fileInput) fileInput.value = "";
    emailList = getInitialUserEmail();
    emailInput = "";
  }

  let isExitTableExpanded = false;
  let isFindingsTableExpanded = false;

  function scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  async function copyReportText() {
    if (scanResult && scanResult.report) {
      try {
        await navigator.clipboard.writeText(scanResult.report);
        toast("คัดลอกรายงานเรียบร้อยแล้ว", "success");
      } catch (err) {
        toast("ไม่สามารถคัดลอกได้: " + err.message, "error");
      }
    }
  }

  let isSendingToDocCreation = false;

  async function sendFindingsToDocCreation() {
    if (!scanResult) return;
    
    isSendingToDocCreation = true;
    try {
      const activeProj = $selectedProjectStore;
      const targetDocType = scanResult.doc_type || (selectedDocTypes && selectedDocTypes[0]) || scanGroupType || 'SRS';
      let cleanDocName = scanResult.filename || scanResult.doc_name || scanGroupName || 'Document';
      // Strip extension if present (.pdf, .docx, .md)
      cleanDocName = cleanDocName.replace(/\.[^/.]+$/, "");
      
      const findingsList = scanResult.qa_findings || [];
      const exitEval = scanResult.exit_criteria_eval || null;

      const payload = {
        project_id: activeProj ? (activeProj.id || activeProj.project_id) : null,
        project_code: activeProj?.project_code || '',
        project_name: activeProj?.name || activeProj?.project_name || '',
        doc_name: cleanDocName,
        doc_type: targetDocType,
        findings: findingsList,
        exit_criteria_eval: exitEval,
        total_pages: scanResult.total_pages || 1,
        source_filename: scanResult.filename || cleanDocName,
        raw_markdown: scanResult.markdown || scanResult.raw_text || '',
        source_text: scanResult.report || '',
        created_at: new Date().toISOString()
      };

      // 1. Train Agent in Background (save learned rules into backend memory)
      fetch('/api/agent/train_qa_rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(r => r.json()).then(res => {
        if (res.success && res.count > 0) {
          console.log(`Agent trained with ${res.count} quality rules.`);
        }
      }).catch(e => console.warn('Rule training background post error:', e));

      // 2. Set refinement feedback store
      qaRefinementFeedback.set(payload);

      // 3. Dispatch navigation event to App.svelte
      dispatch('navigate', { view: 'qa_doc_creation', feedback: payload });
      toast(`ส่งประเด็นข้อผิดพลาด (${findingsList.length} รายการ) ไปยัง QA Document Creation เรียบร้อยแล้ว พร้อมบันทึก Rule ปรับปรุง Agent`, 'success', 5000);
    } catch (err) {
      console.error('Error sending findings to doc creation:', err);
      toast('เกิดข้อผิดพลาดในการส่งข้อมูล: ' + err.message, 'error');
    } finally {
      isSendingToDocCreation = false;
    }
  }
</script>

  <svelte:window on:click={() => { docTypeOpen = false; skillOpen = false; groupTypeOpen = false; }} />

<div class="qa-container" in:fade class:full-width={!!scanResult}>
  {#if !selectedProjectObj}
    <ProjectSelection 
      {projects} 
      on:select={(e) => selectProject(e.detail)} 
    />

  {:else if !isGroupNameSet}
    <!-- GROUP MANAGEMENT & CREATION VIEW -->
    <div class="top-nav">
      <button class="btn-back" on:click={() => { selectedProjectStore.set(null); isGroupNameSet = false; scanGroupName = ""; }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>
    </div>

    <div class="header-text-local">
      <h2>QA Consult - เลือกกลุ่มการตรวจสอบ (Scan Group)</h2>
      <p>เลือกกลุ่มการตรวจสอบที่มีอยู่เพื่อทำการสแกนต่อ หรือสร้างกลุ่มการตรวจสอบใหม่สำหรับโครงการ</p>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code} - {selectedProjectObj.name}</strong>
      </div>
    </div>

    <!-- EXISTING GROUPS SECTION (IF ANY) -->
    {#if currentProjectGroups.length > 0}
      <div class="group-management-section">
        <div class="section-title-bar">
          <div class="title-with-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            </svg>
            <h3>กลุ่มการตรวจสอบที่มีอยู่ในโครงการ ({currentProjectGroups.length})</h3>
          </div>
          <button class="btn-create-group-trigger" on:click={openCreateGroupModal}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            สร้างกลุ่มใหม่
          </button>
        </div>

        <div class="existing-groups-grid">
          {#each currentProjectGroups as group}
            <div class="group-card-item" on:click={() => selectExistingGroup(group)}>
              <div class="group-card-top">
                <div class="group-icon-wrap">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                  </svg>
                </div>
                <div class="group-title-info">
                  <div class="group-type-tag">[{group.group_type || 'Project Plan'}]</div>
                  <div class="group-name-text" title={group.group_name}>{group.group_name}</div>
                </div>
                <button 
                  class="btn-card-delete" 
                  title="ลบกลุ่มนี้" 
                  on:click|stopPropagation={() => requestDeleteGroup(group)}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              </div>

              <div class="group-card-bottom">
                <div class="group-meta-stat">
                  {#if group.scan_count > 0}
                    <span class="stat-badge count-active">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="20 6 9 17 4 12"></polyline></svg>
                      {group.scan_count} ไฟล์ตรวจแล้ว
                    </span>
                  {:else}
                    <span class="stat-badge count-empty">ยังไม่มีไฟล์</span>
                  {/if}
                  {#if group.latest_date}
                    <span class="stat-date">{formatHistoryTime(group.latest_date)}</span>
                  {/if}
                </div>
                <button class="btn-select-group" on:click|stopPropagation={() => selectExistingGroup(group)}>
                  เลือกกลุ่มนี้ &rarr;
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <!-- EMPTY STATE WHEN NO GROUPS EXIST -->
      <div class="group-management-section">
        <div class="empty-groups-box">
          <div class="empty-groups-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="44" height="44">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
            </svg>
          </div>
          <h4>ยังไม่มีกลุ่มการตรวจสอบในโครงการนี้</h4>
          <p>สร้างกลุ่มการตรวจสอบ (Scan Group) แรก เพื่อจัดระเบียบเอกสารและเริ่มการตรวจ QA สำหรับโครงการนี้</p>
          <button class="btn-create-group-trigger lg" on:click={openCreateGroupModal}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            สร้างกลุ่มการตรวจสอบใหม่
          </button>
        </div>
      </div>
    {/if}

    <!-- MODAL: CREATE NEW GROUP -->
    {#if showCreateGroupModal}
      <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={closeCreateGroupModal}>
        <div class="modal-group-dialog" on:click|stopPropagation>
          <div class="modal-dialog-header">
            <div class="modal-dialog-title-wrap">
              <div class="modal-dialog-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </div>
              <div>
                <h3 class="modal-dialog-title">สร้างกลุ่มการตรวจสอบใหม่</h3>
                <div class="modal-dialog-sub">โครงการ: <span class="sub-proj-name">{selectedProjectObj.project_code} - {selectedProjectObj.name}</span></div>
              </div>
            </div>
            <button class="btn-dialog-close" title="ปิดหน้าต่าง" on:click={closeCreateGroupModal}>✕</button>
          </div>

          <div class="modal-dialog-body">
            <div class="setting-group relative">
              <label>ชื่อการตรวจสอบ (Group Name) <span class="req-star">*</span></label>
              <input
                type="text"
                class="modal-form-input"
                bind:value={scanGroupName}
                placeholder="เช่น ตรวจเอกสาร UAT รอบที่ 1, Sprint 2 Review..."
                autofocus
                on:keydown={(e) => {
                  if (e.key === 'Enter' && scanGroupName.trim() !== '') {
                    confirmGroup();
                  }
                }}
              />
            </div>

            <div class="setting-group relative" style="margin-top: 16px;">
              <label>ประเภทเอกสารหลัก (Group Type)</label>
              <!-- Custom Dropdown for Group Type -->
              <div class="custom-select" on:click|stopPropagation={() => { groupTypeOpen = !groupTypeOpen; }}>
                <div class="select-trigger" class:open={groupTypeOpen}>
                  {scanGroupType}
                  <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </div>
                {#if groupTypeOpen}
                  <div class="options-menu" transition:fade={{duration: 100}}>
                    {#each masterGroupTypes as type}
                      <div class="option-item" class:selected={scanGroupType === type} on:click|stopPropagation={() => { scanGroupType = type; groupTypeOpen = false; }}>
                        {type}
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>

            <!-- Exit Criteria Mapping Status / Missing Warning Alert -->
            <div class="criteria-mapping-status" style="margin-top: 16px;">
              {#if isCheckingCriteria}
                <div class="criteria-badge-box loading">
                  <div class="box-icon spin">⏳</div>
                  <div class="box-content">
                    <div class="box-title">กำลังตรวจสอบ Exit Criteria...</div>
                  </div>
                </div>
              {:else if matchedCriteriaTemplate}
                <div class="criteria-badge-box matched">
                  <div class="box-icon">🎯</div>
                  <div class="box-content">
                    <div class="box-title">เชื่อมโยง Exit Criteria: <span class="highlight">{matchedCriteriaTemplate.title}</span></div>
                    <div class="box-desc">
                      ระบบจะตรวจสอบด้วยเกณฑ์เฉพาะ <strong>"{scanGroupType}"</strong> ควบคู่กับเกณฑ์มาตรฐานกลาง <strong>(ALL)</strong> โดยอัตโนมัติ
                    </div>
                  </div>
                </div>
              {:else}
                <div class="criteria-badge-box warning">
                  <div class="box-icon">⚠️</div>
                  <div class="box-content">
                    <div class="box-title">ยังไม่มี Exit Criteria สำหรับประเภท <span class="highlight-warn">"{scanGroupType}"</span> ในการตรวจสอบ</div>
                    <div class="box-desc">
                      ระบบจะใช้เฉพาะเกณฑ์มาตรฐานกลาง (ALL) ในการตรวจสอบ หรือสามารถเพิ่มเกณฑ์เฉพาะได้ที่เมนู <strong>Exit Criteria</strong>
                    </div>
                  </div>
                </div>
              {/if}
            </div>
          </div>

          <div class="modal-dialog-footer">
            <button class="btn-dialog-cancel" on:click={closeCreateGroupModal}>ยกเลิก</button>
            <button 
              class="btn-primary btn-dialog-submit" 
              disabled={!scanGroupName.trim()}
              on:click={confirmGroup}
            >
              บันทึกกลุ่มและเข้าสู่หน้าสแกน &rarr;
            </button>
          </div>
        </div>
      </div>
    {/if}

    <!-- MODAL: DELETE GROUP CONFIRMATION -->
    {#if showDeleteGroupModal && groupToDelete}
      <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={cancelDeleteGroup}>
        <div class="modal-delete-dialog" on:click|stopPropagation>
          <div class="modal-delete-icon-wrap">
            <div class="delete-icon-circle">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                <line x1="10" y1="11" x2="10" y2="17"></line>
                <line x1="14" y1="11" x2="14" y2="17"></line>
              </svg>
            </div>
          </div>

          <div class="modal-delete-content">
            <h3 class="modal-delete-title">ยืนยันการลบกลุ่มการตรวจสอบ</h3>
            <p class="modal-delete-desc">
              คุณต้องการลบกลุ่ม <span class="delete-target-badge">[{groupToDelete.group_type || 'General'}] {groupToDelete.group_name}</span>
            </p>

            <div class="delete-warning-box">
              <div class="warning-icon">⚠️</div>
              <div class="warning-text">
                ประวัติการสแกนเอกสารและรายงานผล QA ทั้งหมดในกลุ่มนี้จะถูกลบอย่างถาวร
              </div>
            </div>
          </div>

          <div class="modal-delete-actions">
            <button class="btn-dialog-cancel" on:click={cancelDeleteGroup} disabled={isDeletingGroup}>
              ยกเลิก
            </button>
            <button class="btn-danger-confirm" on:click={executeDeleteGroup} disabled={isDeletingGroup}>
              {#if isDeletingGroup}
                <span>กำลังลบ...</span>
              {:else}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
                ยืนยันการลบกลุ่ม
              {/if}
            </button>
          </div>
        </div>
      </div>
    {/if}

    <!-- RECENT PROJECT SCAN HISTORY SECTION -->
    {#if currentProjectHistory.length > 0}
      <div class="project-history-section">
        <div class="section-title-bar">
          <div class="title-with-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
            <h3>ประวัติการตรวจสอบล่าสุดในโครงการนี้ ({currentProjectHistory.length})</h3>
          </div>
          <span class="sub-hint">คลิกเอกสารเพื่อเปิดดูรายงานผลการตรวจย้อนหลัง</span>
        </div>

        <div class="history-table-container">
          <table class="project-history-table">
            <thead>
              <tr>
                <th>ชื่อไฟล์เอกสาร</th>
                <th>กลุ่มการตรวจสอบ</th>
                <th>ประเภท</th>
                <th>วันที่ตรวจ</th>
                <th style="text-align: right;">การจัดการ</th>
              </tr>
            </thead>
            <tbody>
              {#each currentProjectHistory.slice(0, 15) as item}
                <tr class="history-table-row" on:click={() => selectedHistory.set(item)}>
                  <td class="td-filename">
                    <div class="file-name-cell">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color: #60a5fa; flex-shrink: 0;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
                      <span>{item.filename || 'Unknown Document'}</span>
                    </div>
                  </td>
                  <td>
                    <span class="group-pill">{item.group_name || 'General'}</span>
                  </td>
                  <td>
                    <span class="type-pill">{item.docType || item.group_type || 'General'}</span>
                  </td>
                  <td class="td-date">{formatHistoryTime(item.date)}</td>
                  <td style="text-align: right;">
                    <button class="btn-table-view" on:click|stopPropagation={() => selectedHistory.set(item)}>
                      ดูรายงาน
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

  {:else if !isProcessing && !scanResult}
    <!-- INPUT FORM -->
    <div class="top-nav">
      <button class="btn-back" on:click={() => { selectedProjectStore.set(null); isGroupNameSet = false; scanGroupName = ""; }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>
    </div>

    <div class="header-text">
      <h2>QA Consult - ระบบตรวจสอบเอกสารอัตโนมัติ</h2>
      <p>อัปโหลดเอกสารของคุณเพื่อเปรียบเทียบกับฐานข้อมูล Knowledge Base ของบริษัท และรับรายงานข้อผิดพลาดทางอีเมล</p>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code} - {selectedProjectObj.name}</strong>
        <span style="margin: 0 10px; color: #8b5cf6;">|</span>
        ชื่อการตรวจสอบ: <strong>[{scanGroupType}] {scanGroupName}</strong>
        <button class="btn-text-change" on:click={() => isGroupNameSet = false}>[ แก้ไข ]</button>
      </div>
    </div>

    <div class="main-card">
      <div class="form-grid">
        <!-- LEFT: File Upload -->
        <div class="upload-section">
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
            class="drop-zone"
            class:dragging={isDragging}
            on:dragenter={handleDragEnter}
            on:dragleave={handleDragLeave}
            on:dragover|preventDefault
            on:drop={handleDrop}
            on:click={triggerFileInput}
            on:keydown={(e) => e.key === "Enter" && triggerFileInput()}
          >
            {#if file}
              <div class="file-info" on:click|stopPropagation on:keydown|stopPropagation role="group">
                <div class="file-icon">
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                </div>
                <div class="file-details">
                  <div class="file-name">{file.name}</div>
                  <div class="file-size">{(file.size / 1024).toFixed(1)} KB</div>
                </div>
                <button class="btn-remove" on:click={removeFile}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            {:else}
              <div class="drop-content">
                <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                <p class="drop-title">ลากไฟล์ PDF มาวางที่นี่</p>
                <p class="drop-sub">หรือ <span>คลิกเพื่อเลือกไฟล์</span></p>
              </div>
            {/if}
          </div>
          <input
            type="file"
            accept=".pdf"
            bind:this={fileInput}
            on:change={handleFileSelect}
            style="display: none;"
          />
        </div>

        <!-- RIGHT: Settings -->
        <div class="settings-section">
          <div class="setting-group relative">
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px;">
              <label style="margin-bottom: 0;">ประเภทเอกสาร (Document Type) <span style="font-size: 11px; color: #94a3b8; font-weight: normal;">(เลือกหรือไม่เลือกก็ได้)</span></label>
              {#if selectedDocTypes.length > 0}
                <button 
                  type="button" 
                  class="btn-clear-doctype" 
                  on:click|stopPropagation={() => selectedDocTypes = []}
                  style="background: none; border: none; color: #f87171; font-size: 11px; cursor: pointer; text-decoration: underline; padding: 0;"
                >
                  ล้างค่า (ให้ AI ตรวจสอบอัตโนมัติ)
                </button>
              {/if}
            </div>
            <!-- Custom Dropdown for Doc Type -->
            <div class="custom-select" on:click|stopPropagation={() => { docTypeOpen = !docTypeOpen; skillOpen = false; }}>
              <div class="select-trigger" class:open={docTypeOpen}>
                {#if selectedDocTypes.length === 0}
                  <span style="color: #c4b5fd; display: flex; align-items: center; gap: 6px;">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    -- ไม่ระบุ (AI วิเคราะห์และตรวจเอกสาร MD ใน Project อัตโนมัติ) --
                  </span>
                {:else if selectedDocTypes.length <= 2}
                  <span style="color: #6ee7b7; font-weight: 500;">
                    🎯 {selectedDocTypes.join(", ")}
                  </span>
                {:else}
                  <span style="color: #6ee7b7; font-weight: 500;">
                    🎯 เลือกแล้ว {selectedDocTypes.length} รายการ
                  </span>
                {/if}
                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </div>
              {#if docTypeOpen}
                <div class="options-menu" transition:fade={{duration: 100}}>
                  <div 
                    class="option-item" 
                    class:selected={selectedDocTypes.length === 0} 
                    on:click|stopPropagation={() => { selectedDocTypes = []; docTypeOpen = false; }}
                    style="color: #c4b5fd; font-style: italic; border-bottom: 1px solid rgba(255,255,255,0.08);"
                  >
                    <span style="margin-right: 8px;">🤖</span>
                    -- ไม่ระบุ (AI Agent วิเคราะห์เนื้อหาและดึงเอกสาร MD ในโครงการอัตโนมัติ) --
                  </div>
                  {#each docTypes as type}
                    <div class="option-item" class:selected={selectedDocTypes.includes(type)} on:click|stopPropagation={() => toggleDocType(type)}>
                      <input type="checkbox" checked={selectedDocTypes.includes(type)} style="margin-right: 8px; cursor: pointer;" />
                      {type}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
            <!-- Dynamic flow description text -->
            <div style="font-size: 11px; margin-top: 5px; line-height: 1.4;">
              {#if selectedDocTypes.length > 0}
                <span style="color: #34d399; display: flex; align-items: center; gap: 4px;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  กำหนด Flow ชัดเจน: AI จะตรวจเจาะจงตาม Flow และมาตรฐานเอกสาร {selectedDocTypes.join(", ")} เพื่อความแม่นยำสูงสุด
                </span>
              {:else}
                <span style="color: #94a3b8; display: flex; align-items: center; gap: 4px;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                  โหมดอัตโนมัติ: AI Agent จะวิเคราะห์ประเภทเอกสาร และดึงเอกสาร MD ในโครงการมา Cross-check อัตโนมัติ
                </span>
              {/if}
            </div>
          </div>

          <div class="setting-group relative">
            <label>ทักษะ AI (AI Skill)</label>
            <!-- Custom Dropdown for Skill -->
            <div class="custom-select" on:click|stopPropagation={() => { skillOpen = !skillOpen; docTypeOpen = false; }}>
              <div class="select-trigger" class:open={skillOpen}>
                {#if selectedSkills.length === 0}
                  <span style="color: #9ca3af;">-- ไม่ใช้ Skill --</span>
                {:else if selectedSkills.length <= 2}
                  {selectedSkills.map(id => skills.find(s => s.skill_id === id)?.skill_name).join(", ")}
                {:else}
                  เลือกแล้ว {selectedSkills.length} ทักษะ
                {/if}
                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </div>
              {#if skillOpen}
                <div class="options-menu" transition:fade={{duration: 100}}>
                  {#if filteredSkills.length === 0}
                    <div class="option-item" style="color: #9ca3af; justify-content: center; cursor: default;">
                      -- ไม่มีทักษะ AI ที่เกี่ยวข้อง --
                    </div>
                  {:else}
                    {#each filteredSkills as skill}
                      <div class="option-item" class:selected={selectedSkills.includes(skill.skill_id)} on:click|stopPropagation={() => toggleSkill(skill.skill_id)}>
                        <input type="checkbox" checked={selectedSkills.includes(skill.skill_id)} style="margin-right: 8px; cursor: pointer;" />
                        {skill.skill_name}
                      </div>
                    {/each}
                  {/if}
                </div>
              {/if}
            </div>
          </div>

          <div class="setting-group">
            <label>อีเมลผู้รับผลการตรวจสอบ</label>
            <div class="email-input-container">
              <input 
                type="text" 
                bind:value={emailInput} 
                placeholder="ระบุอีเมลแล้วกด Enter หรือปุ่ม +" 
                on:keydown={handleEmailKeydown}
              />
              <button class="btn-add-email" on:click={addEmail} disabled={!emailInput} title="เพิ่มอีเมล">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              </button>
            </div>
            
            {#if emailList.length > 0}
              <div class="email-tags">
                {#each emailList as e, i}
                  <div class="email-tag">
                    {e}
                    <button class="remove-tag" on:click={() => removeEmail(i)}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
            <span class="hint-text">รายงานการเปรียบเทียบจะถูกจัดส่งไปยังอีเมลทั้งหมดนี้</span>
          </div>

          <button class="btn-primary" on:click={processQAConsult} disabled={!file || (emailList.length === 0 && emailInput.trim() === '')}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            เริ่มตรวจสอบเอกสาร
          </button>
        </div>
      </div>
    </div>

    <!-- RECENT TRANSACTIONS / SCAN HISTORY IN THIS GROUP -->
    {#if currentGroupHistory.length > 0}
      <div class="project-history-section" style="margin-top: 20px;">
        <div class="section-title-bar">
          <div class="title-with-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
            </svg>
            <h3>ประวัติเอกสารที่เคยตรวจในกลุ่มนี้ ({currentGroupHistory.length})</h3>
          </div>
          <span class="sub-hint">คลิกเอกสารเพื่อเปิดดูผลการวิเคราะห์ย้อนหลัง</span>
        </div>

        <div class="history-table-container">
          <table class="project-history-table">
            <thead>
              <tr>
                <th>ชื่อไฟล์เอกสาร</th>
                <th>กลุ่มการตรวจสอบ</th>
                <th>ประเภท</th>
                <th>วันที่ตรวจ</th>
                <th style="text-align: right;">การจัดการ</th>
              </tr>
            </thead>
            <tbody>
              {#each currentGroupHistory.slice(0, 15) as item}
                <tr class="history-table-row" on:click={() => selectedHistory.set(item)}>
                  <td class="td-filename">
                    <div class="file-name-cell">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color: #60a5fa; flex-shrink: 0;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
                      <span>{item.filename || 'Unknown Document'}</span>
                    </div>
                  </td>
                  <td>
                    <span class="group-pill">{item.group_name || 'General'}</span>
                  </td>
                  <td>
                    <span class="type-pill">{item.docType || item.group_type || 'General'}</span>
                  </td>
                  <td class="td-date">{formatHistoryTime(item.date)}</td>
                  <td style="text-align: right;">
                    <button class="btn-table-view" on:click|stopPropagation={() => selectedHistory.set(item)}>
                      ดูรายงาน
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}

  {:else if isProcessing && !scanResult}
    <!-- SPECTRA QA LOADING STATE -->
    <div class="loading-state">
      <SpectraLoading 
        title="กำลังวิเคราะห์ QA Consult..." 
        status={processStatus || "กำลังประมวลผลและตรวจสอบเกณฑ์ Exit Criteria..."} 
        progressPct={progressPct} 
      />
    </div>

  {:else if scanResult}
    <!-- Gate Result Modal Animation -->
    <GateResultModal 
      showModal={showGateModal} 
      resultData={gateResultData} 
      onClose={() => showGateModal = false} 
    />

    <!-- RESULT STATE -->
    <div class="result-state">
      <div class="dashboard-top-bar" id="qa-top-header" style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 8px; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); width: 100%; flex-wrap: wrap; gap: 16px;">
        <div class="left-content" style="display: flex; flex-direction: column; gap: 10px;">
          <div class="header-text" style="text-align: left; margin: 0;">
            <h2 style="font-size: 22px; margin-bottom: 2px;">ผลการวิเคราะห์ QA & Exit Criteria Review Gate</h2>
            <p style="font-size: 13px; margin: 0; color: #9ca3af;">ตรวจสอบรายงานด้านล่าง ก่อนกดยืนยันการส่งอีเมล</p>
          </div>
          <div class="result-summary" style="margin: 0; padding: 0; background: none; border: none; justify-content: flex-start; gap: 24px;">
            <div class="summary-item" style="flex-direction: row; align-items: baseline; gap: 8px;">
              <span class="lbl" style="margin: 0;">ส่งผลลัพธ์ไปที่:</span>
              <span class="val" style="margin: 0;">{scanResult.email || "- ไม่ระบุ -"}</span>
            </div>
            <div class="summary-item" style="flex-direction: row; align-items: baseline; gap: 8px;">
              <span class="lbl" style="margin: 0;">จำนวนหน้า:</span>
              <span class="val" style="margin: 0;">{scanResult.total_pages ? scanResult.total_pages + ' หน้า' : '- ไม่ทราบ -'}</span>
            </div>
            {#if scanResult.emailSent}
              <div class="summary-item" style="flex-direction: row; align-items: baseline; gap: 8px;">
                <span class="lbl" style="margin: 0;">สถานะส่งอีเมล:</span>
                <span class="val success" style="margin: 0;">ส่งสำเร็จแล้ว</span>
              </div>
            {/if}
          </div>
        </div>

        <div class="right-actions" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
          {#if (scanResult.qa_findings && scanResult.qa_findings.length > 0) || (scanResult.exit_criteria_eval && scanResult.exit_criteria_eval.status !== 'PASSED')}
            <button class="btn-auto-fix-glow" on:click={sendFindingsToDocCreation} disabled={isSendingToDocCreation} title="ส่งข้อบกพร่องที่พบไปยัง QA Document Creation เพื่อปรับปรุงเอกสารให้ผ่าน และบันทึก Rule ปรับปรุง Agent">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                <path d="M12 8v4l3 3"/>
              </svg>
              {isSendingToDocCreation ? 'กำลังส่งข้อมูล...' : `🔄 ส่งแก้ไขใน QA Doc Creation (${scanResult.qa_findings?.length || 0} ข้อ)`}
            </button>
          {/if}

          {#if scanResult.exit_criteria_eval}
            <button class="btn-outline-glow" on:click={() => { gateResultData = scanResult.exit_criteria_eval; showGateModal = true; }} style="height: 42px; font-weight: 600;">
              ✨ แสดง Modal Animation
            </button>
          {/if}

          <button class="btn-outline" on:click={resetForm} disabled={isSendingEmail} style="padding: 10px 16px; min-width: 0; height: 42px; margin: 0;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="1 4 1 10 7 10"></polyline><polyline points="23 20 23 14 17 14"></polyline><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path></svg>
            เริ่มใหม่
          </button>
          
          {#if scanResult.excel_url}
            <a 
              href={scanResult.excel_url} 
              download 
              target="_blank" 
              rel="noopener noreferrer" 
              class="btn-download-excel" 
              style="padding: 10px 16px; margin: 0; height: 42px; border-radius: 8px; font-size: 14px; box-shadow: none;"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              ดาวน์โหลด Excel
            </a>
          {/if}

          <button class="btn-primary" on:click={sendEmail} disabled={isSendingEmail || scanResult.emailSent || !scanResult.email} style="padding: 10px 20px; min-width: 0; height: 42px; margin: 0; border-radius: 8px; font-size: 14px;">
            {#if isSendingEmail}
              กำลังส่ง...
            {:else if scanResult.emailSent}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>
              ส่งแล้ว
            {:else}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
              ส่งรายงานเข้าอีเมล
            {/if}
          </button>
        </div>
      </div>

      <!-- Quick Navigation Bar -->
      <div class="quick-nav-bar">
        <span class="nav-label">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
          นำทางด่วน:
        </span>
        {#if scanResult.exit_criteria_eval}
          <button class="btn-quick-nav" on:click={() => scrollToSection('exit-criteria-section')}>
            📋 Exit Criteria Gate ({scanResult.exit_criteria_eval.score_percentage}%)
          </button>
        {/if}
        {#if scanResult.qa_findings && scanResult.qa_findings.length > 0}
          <button class="btn-quick-nav" on:click={() => scrollToSection('qa-findings-section')}>
            📊 QA Audit Findings ({scanResult.qa_findings.length})
          </button>
        {/if}
        <button class="btn-quick-nav highlight-btn" on:click={() => scrollToSection('consult-report-section')}>
          📝 Spectra QA Consult Report (รายงานวิเคราะห์)
        </button>
      </div>

      <!-- QA Findings Report Card -->
      {#if scanResult.qa_findings && scanResult.qa_findings.length > 0}
        <div class="qa-findings-card glass-panel" id="qa-findings-section" style="margin-bottom: 20px;">
          <div class="gate-result-header" style="margin-bottom: 16px;">
            <div class="gate-header-title">
              <h3>📊 QA Audit Findings Report</h3>
              <span class="template-badge">ประเด็นที่พบจากการวิเคราะห์</span>
            </div>
            <div class="gate-header-actions" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              <span class="gate-status-pill status-info">
                พบ {scanResult.qa_findings.length} รายการ
              </span>
              <button class="btn-mini-autofix" on:click={sendFindingsToDocCreation} disabled={isSendingToDocCreation}>
                🔄 ส่งแก้ไขใน QA Doc Creation
              </button>
              <button class="btn-table-toggle" on:click={() => isFindingsTableExpanded = !isFindingsTableExpanded}>
                {isFindingsTableExpanded ? '🔽 ย่อตาราง' : '🔼 ขยายเต็ม'}
              </button>
            </div>
          </div>

          <div class="exit-checklist-table-wrapper" class:expanded={isFindingsTableExpanded}>
            <table class="exit-checklist-table">
              <thead>
                <tr>
                  <th style="width: 50px;">ลำดับ</th>
                  <th style="width: 150px;">ประเภทการตรวจ</th>
                  <th>ประเด็นที่พบ (Issue)</th>
                  <th style="width: 100px;">ความรุนแรง</th>
                  <th>สิ่งที่ควรเป็น</th>
                  <th>ข้อเสนอแนะ</th>
                </tr>
              </thead>
              <tbody>
                {#each scanResult.qa_findings as finding, i}
                  <tr class="row-status-{finding.severity === 'Critical' || finding.severity === 'High' ? 'fail' : finding.severity === 'Medium' ? 'na' : 'pass'}">
                    <td class="item-code-cell" style="text-align: center;">{i + 1}</td>
                    <td class="category-cell">{finding.check_type || '-'}</td>
                    <td class="question-cell">
                      <strong>{finding.issue || '-'}</strong>
                      {#if finding.found_incorrect && finding.found_incorrect !== '-'}
                        <div class="evidence-text" style="margin-top: 8px;">
                          <span style="color: #f87171;">ข้อความในเอกสาร:</span> {finding.found_incorrect}
                        </div>
                      {/if}
                    </td>
                    <td class="severity-cell" style="text-align: center;">
                      <span class="badge-sev badge-sev-{finding.severity.toLowerCase()}">{finding.severity}</span>
                    </td>
                    <td class="remarks-cell">{finding.correct_value || '-'}</td>
                    <td class="remarks-cell">{finding.recommendation || '-'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      <!-- Exit Criteria Review Gate Card -->
      {#if scanResult.exit_criteria_eval}
        <div class="exit-criteria-gate-result-card glass-panel" id="exit-criteria-section" style="margin-bottom: 20px;">
          <div class="gate-result-header">
            <div class="gate-header-title">
              <h3>📋 ผลการประเมิน Exit Criteria Review Gate</h3>
              <span class="template-badge">{scanResult.exit_criteria_eval.template_title}</span>
            </div>
            <div class="gate-header-actions" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              {#if activeTabStats.status !== 'PASSED'}
                <button class="btn-mini-autofix" on:click={sendFindingsToDocCreation} disabled={isSendingToDocCreation}>
                  🔄 ส่งแก้ไขตามเกณฑ์ Gate
                </button>
              {/if}
              <span class="gate-status-pill status-{activeTabStats.status.toLowerCase()}">
                {activeTabStats.status}
              </span>
              <button class="btn-table-toggle" on:click={() => isExitTableExpanded = !isExitTableExpanded}>
                {isExitTableExpanded ? '🔽 ย่อตาราง' : '🔼 ขยายเต็ม'}
              </button>
            </div>
          </div>

          <!-- Criteria Tabs Navigation -->
          {#if criteriaTabsList && criteriaTabsList.length > 1}
            <div class="criteria-nav-tabs">
              <button 
                class="criteria-tab-btn" 
                class:active={selectedCriteriaTab === 'all'}
                on:click={() => selectedCriteriaTab = 'all'}
              >
                <span class="tab-icon">📑</span>
                <span class="tab-title">ทั้งหมด (All Criteria)</span>
                <span class="tab-badge">{scanResult.exit_criteria_eval.items ? scanResult.exit_criteria_eval.items.length : 0} ข้อ</span>
                {#if scanResult.exit_criteria_eval.failed_items > 0}
                  <span class="tab-status-dot red" title="มีข้อที่ไม่ผ่าน"></span>
                {:else}
                  <span class="tab-status-dot green" title="ผ่านทุกข้อ"></span>
                {/if}
              </button>

              {#each criteriaTabsList as grp}
                <button 
                  class="criteria-tab-btn" 
                  class:active={selectedCriteriaTab === grp.key}
                  on:click={() => selectedCriteriaTab = grp.key}
                >
                  <span class="tab-icon">{grp.key === 'universal' ? '🌐' : '📘'}</span>
                  <span class="tab-title">{grp.title}</span>
                  <span class="tab-badge" class:has-fail={grp.failed > 0}>
                    {grp.passed}/{grp.total} ผ่าน
                    {#if grp.failed > 0}
                      <span class="fail-count">({grp.failed} ไม่ผ่าน)</span>
                    {/if}
                  </span>
                  <span class="tab-status-pill status-{grp.status.toLowerCase()}">
                    {grp.status}
                  </span>
                </button>
              {/each}
            </div>
          {/if}

          <div class="gate-summary-bar">
            <div class="summary-stat">
              <span class="stat-num">{activeTabStats.score}%</span>
              <span class="stat-lbl">คะแนนสมบูรณ์</span>
            </div>
            <div class="summary-stat green">
              <span class="stat-num">{activeTabStats.passed}</span>
              <span class="stat-lbl">ผ่าน (PASS)</span>
            </div>
            <div class="summary-stat red">
              <span class="stat-num">{activeTabStats.failed}</span>
              <span class="stat-lbl">ไม่ผ่าน (FAIL)</span>
            </div>
            <div class="summary-stat gray">
              <span class="stat-num">{activeTabStats.na}</span>
              <span class="stat-lbl">ข้าม (N/A)</span>
            </div>
          </div>

          <!-- Categorized Checklist Items -->
          <div class="exit-checklist-table-wrapper" class:expanded={isExitTableExpanded}>
            <table class="exit-checklist-table">
              <thead>
                <tr>
                  <th style="width: 70px;">ข้อตรวจ</th>
                  <th style="width: 180px;">หมวดหมู่</th>
                  <th>รายการประเมิน (Checklist Item)</th>
                  <th style="width: 150px;">📊 ตัวชี้วัด (KPI Indicator)</th>
                  <th style="width: 90px;">ความรุนแรง</th>
                  <th style="width: 95px;">ผลการตรวจ</th>
                  <th>ข้อสังเกต / ร่องรอยที่พบ</th>
                </tr>
              </thead>
              <tbody>
                {#if activeTabItems.length === 0}
                  <tr>
                    <td colspan="7" style="text-align: center; padding: 24px; color: #94a3b8;">
                      ไม่พบรายการข้อตรวจในเกณฑ์นี้
                    </td>
                  </tr>
                {:else}
                  {#each activeTabItems as item}
                    <tr class="row-status-{item.status.toLowerCase()}">
                      <td class="item-code-cell"><strong>{item.item_code}</strong></td>
                      <td class="category-cell">
                        {#if selectedCriteriaTab === 'all' && item.groupTag}
                          <span class="group-prefix-badge">{item.groupTag}</span>
                        {/if}
                        {item.displayCategory || item.category}
                      </td>
                      <td class="question-cell">{item.question_text}</td>
                      <td class="metric-cell">
                        <span class="badge-metric">{item.target_metric || '100% (ผ่านบริบูรณ์)'}</span>
                      </td>
                      <td class="severity-cell">
                        <span class="badge-sev badge-sev-{item.severity.toLowerCase()}">{item.severity}</span>
                      </td>
                      <td class="status-cell">
                        <span class="badge-status status-tag-{item.status.toLowerCase()}">
                          {item.status === 'PASS' ? '✅ PASS' : item.status === 'FAIL' ? '❌ FAIL' : '⚪ N/A'}
                        </span>
                      </td>
                      <td class="remarks-cell">
                        <div class="remark-text">{item.remarks}</div>
                        {#if item.evidence_text}
                          <div class="evidence-text">🔎 <em>{item.evidence_text}</em></div>
                        {/if}
                      </td>
                    </tr>
                  {/each}
                {/if}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      <!-- Spectra QA Consult Report Box -->
      <div class="report-box email-preview" id="consult-report-section">
        <div class="email-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <h2 style="margin: 0; font-size: 1.15rem; font-weight: 700;">Spectra QA Consult Report</h2>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            {#if scanResult.report}
              <button class="btn-report-action" on:click={copyReportText} title="คัดลอกข้อความรายงาน">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                คัดลอกรายงาน
              </button>
            {/if}
            <button class="btn-report-action" on:click={() => scrollToSection('qa-top-header')} title="เลื่อนกลับด้านบน">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="18 15 12 9 6 15"></polyline></svg>
              กลับด้านบน
            </button>
          </div>
        </div>
        <div class="email-body">
          <p>เรียนผู้ใช้งาน,</p>
          <p>ระบบ Spectra QA ได้ทำการตรวจสอบเอกสาร <b>{scanResult.filename || 'ไม่ระบุชื่อไฟล์'}</b> ประเภท <b>{scanResult.doc_type || 'ไม่ระบุประเภท'}</b> เรียบร้อยแล้ว</p>
          <p>นี่คือผลการวิเคราะห์และเปรียบเทียบกับฐานข้อมูล Knowledge Base:</p>
          <hr>
          {#if scanResult.report}
            <pre>{scanResult.report}</pre>
          {:else}
            <div style="color: red; padding: 10px; background: #fee2e2; border-radius: 4px;">
              ไม่พบเนื้อหารายงาน (AI ไม่ได้ส่งข้อความกลับมา หรือเกิดข้อผิดพลาดในการรับข้อมูล)<br>
              <pre style="font-size: 11px; margin-top: 10px;">{JSON.stringify(scanResult, null, 2)}</pre>
            </div>
          {/if}
          <hr>
          <p class="footer-note"><small>สร้างโดย Spectra QA Intelligent Analysis System</small></p>
        </div>
      </div>

      <!-- GROUP SCAN TRANSACTIONS IN RESULT VIEW -->
      {#if currentGroupHistory.length > 0}
        <div class="project-history-section" style="margin-top: 24px;">
          <div class="section-title-bar">
            <div class="title-with-badge">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
              </svg>
              <h3>ประวัติเอกสารที่เคยตรวจในกลุ่มนี้ ({currentGroupHistory.length})</h3>
            </div>
            <button class="btn-outline" on:click={() => { scanResult = null; file = null; }} style="padding: 6px 14px; font-size: 13px; height: 34px;">
              ➕ สแกนเอกสารเพิ่มในกลุ่มนี้
            </button>
          </div>

          <div class="history-table-container">
            <table class="project-history-table">
              <thead>
                <tr>
                  <th>ชื่อไฟล์เอกสาร</th>
                  <th>กลุ่มการตรวจสอบ</th>
                  <th>ประเภท</th>
                  <th>วันที่ตรวจ</th>
                  <th style="text-align: right;">การจัดการ</th>
                </tr>
              </thead>
              <tbody>
                {#each currentGroupHistory.slice(0, 15) as item}
                  <tr class="history-table-row" class:active-row={item.filename === scanResult.filename} on:click={() => selectedHistory.set(item)}>
                    <td class="td-filename">
                      <div class="file-name-cell">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color: #60a5fa; flex-shrink: 0;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
                        <span>{item.filename || 'Unknown Document'}</span>
                        {#if item.filename === scanResult.filename}
                          <span style="font-size: 10px; background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 4px; padding: 1px 6px;">กำลังดู</span>
                        {/if}
                      </div>
                    </td>
                    <td>
                      <span class="group-pill">{item.group_name || 'General'}</span>
                    </td>
                    <td>
                      <span class="type-pill">{item.docType || item.group_type || 'General'}</span>
                    </td>
                    <td class="td-date">{formatHistoryTime(item.date)}</td>
                    <td style="text-align: right;">
                      <button class="btn-table-view" on:click|stopPropagation={() => selectedHistory.set(item)}>
                        ดูรายงาน
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

{#if showConfirmModal}
  <div class="modal-backdrop" transition:fade={{duration: 200}}>
    <div class="modal-card">
      <div class="modal-icon warning">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
      </div>
      <h3>ยืนยันการส่งอีเมล</h3>
      <p>คุณต้องการส่งรายงานผลการตรวจสอบนี้ ไปยังอีเมล <b>{email}</b> ใช่หรือไม่?</p>
      <div class="modal-actions">
        <button class="btn-outline" on:click={() => showConfirmModal = false} disabled={isSendingEmail}>ยกเลิก</button>
        <button class="btn-primary" on:click={executeSendEmail} disabled={isSendingEmail}>
          {#if isSendingEmail}กำลังส่ง...{:else}ยืนยันส่งอีเมล{/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showSuccessModal}
  <div class="modal-backdrop" transition:fade={{duration: 200}}>
    <div class="modal-card">
      <div class="modal-icon success">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
      </div>
      <h3>ส่งอีเมลสำเร็จ</h3>
      <p>รายงานถูกส่งไปยัง <b>{email}</b> เรียบร้อยแล้ว</p>
      <div class="modal-actions centered">
        <button class="btn-primary" on:click={() => showSuccessModal = false}>ตกลง</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .qa-container {
    width: 100%;
    max-width: 1400px;
    height: 100%;
    margin: 0 auto;
    padding: 20px 40px 60px;
    display: flex;
    flex-direction: column;
    gap: 30px;
    overflow-y: auto;
    scroll-behavior: smooth;
    box-sizing: border-box;
  }
  .qa-container.full-width {
    max-width: 100%;
    padding: 20px 24px 80px 24px;
  }
  .header-text-local {
    text-align: center;
  }
  .header-text-local h2 {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 10px;
    background: linear-gradient(90deg, #fff, #9ca3af);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header-text-local p {
    color: var(--text3);
    font-size: 16px;
  }
  .main-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 30px;
  }
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 40px;
  }
  
  /* Upload Section */
  .drop-zone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    height: 100%;
    min-height: 250px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    background: rgba(0,0,0,0.2);
  }
  .drop-zone.dragging, .drop-zone:hover {
    border-color: #9333ea;
    background: rgba(147, 51, 234, 0.05);
  }
  .drop-content {
    text-align: center;
  }
  .upload-icon {
    width: 48px;
    height: 48px;
    color: var(--text3);
    margin-bottom: 15px;
  }
  .drop-zone:hover .upload-icon {
    color: #9333ea;
  }
  .drop-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 5px;
  }
  .drop-sub {
    font-size: 14px;
    color: var(--text3);
  }
  .drop-sub span {
    color: #9333ea;
  }
  .file-info {
    display: flex;
    align-items: center;
    gap: 15px;
    background: var(--surface);
    padding: 20px;
    border-radius: 8px;
    border: 1px solid #9333ea;
    width: 80%;
  }
  .file-icon {
    width: 40px;
    height: 40px;
    background: rgba(147, 51, 234, 0.2);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9333ea;
  }
  .file-details {
    flex: 1;
  }
  .file-name {
    font-weight: 500;
    font-size: 14px;
    margin-bottom: 4px;
    word-break: break-all;
  }
  .file-size {
    font-size: 12px;
    color: var(--text3);
  }
  .btn-remove {
    background: none;
    border: none;
    color: var(--text3);
    cursor: pointer;
    padding: 5px;
  }
  .btn-remove:hover {
    color: #ef4444;
  }

  /* Settings Section */
  .settings-section {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
  .setting-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .setting-group label {
    font-size: 14px;
    font-weight: 500;
    color: var(--text2);
  }
  
  /* Input Email */
  .email-input-container input {
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 15px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .email-input-container input:focus {
    border-color: #9333ea;
    box-shadow: 0 0 0 2px rgba(147, 51, 234, 0.2);
  }

  /* Custom Select Dropdowns */
  .relative {
    position: relative;
  }
  .custom-select {
    position: relative;
    user-select: none;
    cursor: pointer;
  }
  .select-trigger {
    background: rgba(18, 20, 28, 0.85);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #f8fafc;
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    display: flex;
    justify-content: space-between;
    align-items: center;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.08);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .select-trigger:hover {
    border-color: rgba(168, 85, 247, 0.75);
    background-color: rgba(28, 30, 46, 0.95);
    box-shadow: 0 6px 20px rgba(168, 85, 247, 0.3);
    transform: translateY(-1px);
  }
  .select-trigger.open {
    border-color: var(--secondary);
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.35), 0 8px 24px rgba(168, 85, 247, 0.35);
  }
  .select-trigger .chevron {
    width: 18px;
    height: 18px;
    color: #a855f7;
    transition: transform 0.25s ease-in-out;
  }
  .select-trigger.open .chevron {
    transform: rotate(180deg);
  }
  .options-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    width: 100%;
    background: rgba(15, 17, 26, 0.95); /* deep dark glass background */
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(168, 85, 247, 0.15);
    z-index: 100;
    max-height: 240px;
    overflow-y: auto;
    padding: 6px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
  }
  /* Custom scrollbar for options menu */
  .options-menu::-webkit-scrollbar {
    width: 6px;
  }
  .options-menu::-webkit-scrollbar-thumb {
    background: rgba(168, 85, 247, 0.4);
    border-radius: 4px;
  }
  .option-item {
    padding: 10px 14px;
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 13.5px;
    display: flex;
    align-items: center;
    transition: all 0.2s ease;
  }
  .option-item:hover {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(168, 85, 247, 0.3));
    color: #ffffff;
    transform: translateX(3px);
  }
  .option-item.selected {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.5), rgba(168, 85, 247, 0.5));
    color: #ffffff;
    font-weight: 600;
  }

  .hint-text {
    font-size: 12px;
    color: var(--text3);
  }

  .email-input-container {
    display: flex;
    gap: 8px;
  }
  .email-input-container input {
    flex: 1;
  }
  .btn-add-email {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-main);
    width: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-add-email:hover:not(:disabled) {
    background: #9333ea;
    border-color: #9333ea;
  }
  .btn-add-email:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .email-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
  }
  .email-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(147, 51, 234, 0.2);
    border: 1px solid rgba(147, 51, 234, 0.5);
    padding: 4px 10px;
    border-radius: 16px;
    font-size: 13px;
    color: #d8b4fe;
  }
  .remove-tag {
    background: none;
    border: none;
    color: #d8b4fe;
    cursor: pointer;
    padding: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: background 0.2s;
  }
  .remove-tag:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }
  .btn-primary {
    margin-top: auto;
    background: linear-gradient(135deg, #7c3aed, #3b82f6);
    color: white;
    border: none;
    padding: 16px;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    transition: opacity 0.2s, transform 0.1s;
  }
  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }
  .btn-primary:active:not(:disabled) {
    transform: scale(0.98);
  }
  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: var(--surface);
    color: var(--text3);
  }

  /* Loading State */
  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    background: var(--surface2);
    border-radius: 16px;
    border: 1px solid var(--border);
    min-height: 400px;
  }
  
  /* Result State */
  .result-state {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    justify-content: flex-start;
    padding: 24px 32px;
    background: var(--surface2);
    border-radius: 16px;
    border: 1px solid var(--border);
    min-height: 400px;
  }
  .spinner-box {
    margin-bottom: 30px;
  }
  .loading-state h2 {
    font-size: 24px;
    margin-bottom: 10px;
  }
  .status-msg {
    color: var(--text2);
    margin-bottom: 30px;
  }
  .progress-bar-container {
    width: 100%;
    max-width: 400px;
    height: 8px;
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #9333ea, #3b82f6);
    transition: width 0.3s ease;
  }

  /* Result State */
  .success-icon {
    width: 64px;
    height: 64px;
    color: #10b981;
    margin-bottom: 20px;
  }
  .result-state h2 {
    font-size: 28px;
    color: #10b981;
    margin-bottom: 10px;
  }
  .result-state p {
    color: var(--text2);
    margin-bottom: 30px;
    text-align: center;
  }
  .result-summary {
    background: rgba(0,0,0,0.2);
    padding: 20px;
    border-radius: 8px;
    width: 100%;
    max-width: 400px;
    margin-bottom: 30px;
  }
  .summary-item {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;
    font-size: 14px;
  }
  .summary-item:last-child {
    margin-bottom: 0;
  }
  .summary-item .lbl {
    color: var(--text3);
  }
  .summary-item .val {
    font-weight: 600;
  }
  .val.success {
    color: #10b981;
  }
  .btn-outline {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px 24px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .btn-outline:hover {
    background: rgba(255,255,255,0.05);
  }
  
  /* Top Navigation / Back Button */
  .top-nav {
    margin-bottom: 20px;
  }
  .btn-back {
    display: flex;
    align-items: center;
    gap: 8px;
    background: transparent;
    border: none;
    color: #9ca3af;
    font-size: 14px;
    cursor: pointer;
    padding: 8px 12px;
    border-radius: 8px;
    transition: all 0.2s;
  }
  .btn-back:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.05);
  }

  /* Project Selection Styles Removed (Now in ProjectSelection.svelte) */
  .active-project-badge {
    margin-top: 15px;
    font-size: 14px;
    color: var(--text2);
    background: rgba(147, 51, 234, 0.1);
    padding: 8px 16px;
    border-radius: 8px;
    display: inline-block;
    border: 1px solid rgba(147, 51, 234, 0.3);
  }
  .active-project-badge strong {
    color: #d8b4fe;
    font-weight: 600;
  }
  .btn-text-change {
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    font-size: 13px;
    margin-left: 10px;
    padding: 0;
    transition: color 0.2s;
  }
  .btn-text-change:hover {
    color: #fff;
    text-decoration: underline;
  }

  .report-box.email-preview {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 0;
    margin-bottom: 24px;
    text-align: left;
    max-height: 60vh;
    overflow-y: auto;
    width: 100%;
    color: #333;
    font-family: Arial, sans-serif;
  }
  .email-header {
    background-color: #7c3aed;
    color: white;
    padding: 16px 24px;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .email-header h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }
  .email-body {
    padding: 24px;
  }
  .email-body p {
    color: #333;
    margin-bottom: 12px;
    font-size: 15px;
  }
  .email-body hr {
    border: 0;
    border-top: 1px solid #e5e7eb;
    margin: 20px 0;
  }
  .email-body pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 15px;
    line-height: 1.6;
    color: #333;
    margin: 0;
  }
  .footer-note {
    margin-bottom: 0 !important;
    color: #6b7280 !important;
  }

  .report-box::-webkit-scrollbar {
    width: 8px;
  }
  .report-box::-webkit-scrollbar-thumb {
    background: rgba(0,0,0,0.2);
    border-radius: 4px;
  }

  .result-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    background: rgba(255, 255, 255, 0.03);
    padding: 16px 24px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    margin-bottom: 20px;
    justify-content: center;
  }
  .summary-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .summary-item .lbl {
    font-size: 13px;
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .summary-item .val {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-main);
  }
  .summary-item .val.success {
    color: #10b981;
  }

  .action-buttons {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-top: 10px;
    width: 100%;
  }
  .action-buttons .btn-primary, .action-buttons .btn-outline {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 0;
    min-width: 180px;
    padding: 12px 24px;
  }

  /* Modals */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .modal-card {
    background: #1e1e2d;
    border: 1px solid #333;
    border-radius: 16px;
    padding: 32px;
    width: 90%;
    max-width: 400px;
    text-align: center;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  }
  .modal-icon {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px;
  }
  .modal-icon.warning {
    background: rgba(245, 158, 11, 0.1);
    color: #f59e0b;
  }
  .modal-icon.success {
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
  }
  .modal-card h3 {
    margin: 0 0 12px;
    font-size: 20px;
    color: white;
  }
  .modal-card p {
    color: #9ca3af;
    margin: 0 0 24px;
    line-height: 1.5;
  }
  .modal-card b {
    color: white;
  }
  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: stretch;
  }
  .modal-actions.centered {
    justify-content: center;
  }
  .modal-actions button {
    flex: 1;
    margin: 0;
  }
  .modal-actions.centered button {
    flex: none;
    min-width: 120px;
  }

  /* Excel Download Section */
  .excel-download-section {
    margin: 20px 0;
  }
  .excel-badge {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 18px 24px;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.08), rgba(59, 130, 246, 0.08));
    border: 1px solid rgba(124, 58, 237, 0.25);
    border-radius: 14px;
    transition: all 0.25s ease;
  }
  .excel-badge:hover {
    border-color: rgba(124, 58, 237, 0.45);
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.12), rgba(59, 130, 246, 0.12));
  }
  .excel-badge > svg {
    color: #10b981;
    flex-shrink: 0;
  }
  .excel-info {
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex: 1;
  }
  .excel-title {
    font-weight: 600;
    font-size: 14px;
    color: white;
  }
  .excel-desc {
    font-size: 12px;
    color: #9ca3af;
  }
  .btn-download-excel {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 22px;
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    text-decoration: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s ease;
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.25);
  }
  .btn-download-excel:hover {
    background: linear-gradient(135deg, #059669, #047857);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(16, 185, 129, 0.35);
  }

  /* Exit Criteria Gate Card & Table Styles */
  .exit-criteria-gate-result-card {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 20px 24px;
    backdrop-filter: blur(12px);
  }

  .gate-result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding-bottom: 14px;
    margin-bottom: 16px;
  }

  .gate-header-title {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .gate-header-title h3 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .template-badge {
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(99, 102, 241, 0.4);
    color: #a5b4fc;
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 14px;
  }

  .btn-outline-glow {
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.4);
    color: #c7d2fe;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-outline-glow:hover {
    background: rgba(99, 102, 241, 0.3);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
  }

  .gate-status-pill {
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .gate-status-pill.status-passed { background: #059669; color: #ffffff; }
  .gate-status-pill.status-conditional_passed { background: #d97706; color: #ffffff; }
  .gate-status-pill.status-rejected { background: #dc2626; color: #ffffff; }

  .gate-summary-bar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }

  .summary-stat {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .summary-stat.green { background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.3); }
  .summary-stat.red { background: rgba(239, 68, 68, 0.12); border-color: rgba(239, 68, 68, 0.3); }
  .summary-stat.gray { background: rgba(148, 163, 184, 0.12); border-color: rgba(148, 163, 184, 0.3); }

  .stat-num { font-size: 1.25rem; font-weight: 700; color: #f8fafc; }
  .summary-stat.green .stat-num { color: #34d399; }
  .summary-stat.red .stat-num { color: #f87171; }
  .summary-stat.gray .stat-num { color: #94a3b8; }

  .stat-lbl { font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }

  /* Result State Container */
  .result-state {
    display: flex;
    flex-direction: column;
    gap: 20px;
    width: 100%;
    flex-shrink: 0;
    min-height: min-content;
    padding-bottom: 80px;
  }

  /* Quick Navigation Bar */
  .quick-nav-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 16px;
    border-radius: 12px;
    margin-bottom: 8px;
    backdrop-filter: blur(8px);
  }
  .nav-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
    font-weight: 600;
    color: #94a3b8;
    margin-right: 4px;
  }
  .btn-quick-nav {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #e2e8f0;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-quick-nav:hover {
    background: rgba(99, 102, 241, 0.2);
    border-color: rgba(99, 102, 241, 0.4);
    color: #ffffff;
    transform: translateY(-1px);
  }
  .btn-quick-nav.highlight-btn {
    background: rgba(124, 58, 237, 0.25);
    border-color: rgba(124, 58, 237, 0.45);
    color: #c4b5fd;
    font-weight: 600;
  }
  .btn-quick-nav.highlight-btn:hover {
    background: rgba(124, 58, 237, 0.4);
    color: #ffffff;
  }

  .btn-table-toggle {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-table-toggle:hover {
    background: rgba(255, 255, 255, 0.18);
    color: #ffffff;
  }

  .btn-report-action {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #ffffff;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.78rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-report-action:hover {
    background: rgba(255, 255, 255, 0.28);
    transform: translateY(-1px);
  }

  /* Criteria Nav Tabs */
  .criteria-nav-tabs {
    display: flex;
    gap: 8px;
    margin: 14px 0 16px 0;
    padding-bottom: 8px;
    overflow-x: auto;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .criteria-tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    padding: 8px 14px;
    border-radius: 10px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }
  .criteria-tab-btn:hover {
    background: rgba(51, 65, 85, 0.8);
    color: #e2e8f0;
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }
  .criteria-tab-btn.active {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(124, 58, 237, 0.3));
    border-color: rgba(99, 102, 241, 0.6);
    color: #ffffff;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
  }
  .tab-icon {
    font-size: 0.95rem;
  }
  .tab-title {
    font-weight: 600;
  }
  .tab-badge {
    background: rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 2px 7px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 500;
  }
  .criteria-tab-btn.active .tab-badge {
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
  }
  .tab-badge.has-fail {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.3);
  }
  .tab-badge .fail-count {
    color: #f87171;
    font-weight: 700;
  }
  .tab-status-pill {
    padding: 2px 7px;
    border-radius: 6px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.3px;
  }
  .tab-status-pill.status-passed {
    background: rgba(16, 185, 129, 0.2);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.4);
  }
  .tab-status-pill.status-conditional_passed {
    background: rgba(245, 158, 11, 0.2);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.4);
  }
  .tab-status-pill.status-rejected {
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
  }
  .tab-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }
  .tab-status-dot.green {
    background: #10b981;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
  }
  .tab-status-dot.red {
    background: #ef4444;
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.6);
  }
  .group-prefix-badge {
    display: inline-block;
    padding: 2px 6px;
    margin-right: 4px;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #a5b4fc;
  }

  .exit-checklist-table-wrapper {
    overflow-x: auto;
    overflow-y: auto;
    max-height: 480px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(15, 23, 42, 0.4);
  }
  .exit-checklist-table-wrapper.expanded {
    max-height: none;
  }

  .exit-checklist-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  .exit-checklist-table th {
    background: #1e293b;
    position: sticky;
    top: 0;
    z-index: 5;
    box-shadow: 0 1px 0 rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  }

  .exit-checklist-table td {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    color: #e2e8f0;
    vertical-align: top;
  }

  .row-status-fail { background: rgba(239, 68, 68, 0.06); }
  .row-status-pass { background: rgba(16, 185, 129, 0.02); }

  .badge-status {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .status-tag-pass { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
  .status-tag-fail { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
  .status-tag-na { background: rgba(148, 163, 184, 0.2); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.4); }

  .badge-sev {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
  }
  .badge-sev-critical { background: rgba(239, 68, 68, 0.2); color: #f87171; }
  .badge-sev-major { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
  .badge-sev-minor { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }

  .badge-metric {
    display: inline-block;
    padding: 3px 8px;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #c7d2fe;
    border-radius: 6px;
    font-size: 0.76rem;
    font-weight: 600;
  }

  .evidence-text {
    margin-top: 4px;
    font-size: 0.78rem;
    color: #fbbf24;
  }

  /* Criteria Mapping Status Box */
  .criteria-badge-box {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 0.85rem;
    line-height: 1.45;
    transition: all 0.25s ease;
  }
  .criteria-badge-box.matched {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.35);
    box-shadow: 0 4px 16px rgba(16, 185, 129, 0.08);
  }
  .criteria-badge-box.warning {
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.35);
    box-shadow: 0 4px 16px rgba(245, 158, 11, 0.08);
  }
  .criteria-badge-box.loading {
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.25);
  }
  .box-icon {
    font-size: 1.25rem;
    line-height: 1;
    margin-top: 2px;
    flex-shrink: 0;
  }
  .box-content {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .box-title {
    font-weight: 600;
    color: #f1f5f9;
  }
  .box-desc {
    font-size: 0.8rem;
    color: #94a3b8;
  }
  .highlight {
    color: #34d399;
    font-weight: 700;
  }
  .highlight-warn {
    color: #fbbf24;
    font-weight: 700;
  }
  .spin {
    animation: spin 1.5s linear infinite;
  }
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  /* Group Management and Selection in QAConsult */
  .group-management-section {
    max-width: 900px;
    margin: 0 auto 24px auto;
    width: 100%;
  }
  .section-title-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    padding: 0 4px;
  }
  .title-with-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #c084fc;
  }
  .title-with-badge h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #f1f5f9;
  }
  .btn-create-group-trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, rgba(147, 51, 234, 0.25), rgba(99, 102, 241, 0.25));
    border: 1px solid rgba(168, 85, 247, 0.5);
    color: #f1f5f9;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.25s ease;
    box-shadow: 0 2px 10px rgba(147, 51, 234, 0.2);
  }
  .btn-create-group-trigger:hover {
    background: linear-gradient(135deg, #9333ea, #6366f1);
    border-color: #c084fc;
    color: #ffffff;
    box-shadow: 0 4px 16px rgba(168, 85, 247, 0.4);
    transform: translateY(-1px);
  }
  .btn-create-group-trigger.lg {
    padding: 10px 20px;
    font-size: 14px;
    margin-top: 14px;
    border-radius: 10px;
  }
  .empty-groups-box {
    background: rgba(15, 23, 42, 0.6);
    border: 1px dashed rgba(168, 85, 247, 0.35);
    border-radius: 16px;
    padding: 36px 24px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .empty-groups-icon {
    color: #a855f7;
    opacity: 0.8;
    margin-bottom: 12px;
  }
  .empty-groups-box h4 {
    margin: 0 0 6px 0;
    font-size: 16px;
    font-weight: 600;
    color: #f1f5f9;
  }
  .empty-groups-box p {
    margin: 0 0 8px 0;
    font-size: 13px;
    color: #94a3b8;
    max-width: 480px;
  }

  /* Group Modal Styles */
  .modal-group-dialog {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 18px;
    width: 90%;
    max-width: 540px;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8), 0 0 30px rgba(147, 51, 234, 0.2);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    overflow: hidden;
    animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes modalPop {
    from { opacity: 0; transform: scale(0.95) translateY(10px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
  }
  .modal-dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(30, 41, 59, 0.5);
  }
  .modal-dialog-title-wrap {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .modal-dialog-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: rgba(168, 85, 247, 0.15);
    border: 1px solid rgba(168, 85, 247, 0.3);
    color: #c084fc;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .modal-dialog-title {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
  }
  .modal-dialog-sub {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 2px;
  }
  .sub-proj-name {
    color: #c084fc;
    font-weight: 600;
  }
  .btn-dialog-close {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 14px;
    transition: all 0.2s;
  }
  .btn-dialog-close:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.4);
    color: #f87171;
  }
  .modal-dialog-body {
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .modal-form-input {
    width: 100%;
    padding: 12px 16px;
    border-radius: 12px;
    border: 1px solid rgba(139, 92, 246, 0.35);
    background: rgba(18, 20, 28, 0.85);
    color: #f8fafc;
    font-size: 14px;
    outline: none;
    box-sizing: border-box;
    transition: all 0.2s ease;
  }
  .modal-form-input:focus {
    border-color: #a855f7;
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.3);
  }
  .req-star {
    color: #f43f5e;
  }
  .modal-dialog-footer {
    padding: 16px 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(15, 23, 42, 0.8);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
  .btn-dialog-cancel {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 9px 18px;
    font-size: 13.5px;
    font-weight: 500;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-dialog-cancel:hover {
    background: rgba(255, 255, 255, 0.12);
    color: white;
  }
  .btn-dialog-submit {
    margin: 0;
    padding: 9px 20px;
    font-size: 13.5px;
  }

  /* Delete Group Confirmation Modal */
  .modal-delete-dialog {
    background: rgba(15, 23, 42, 0.96);
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 18px;
    width: 90%;
    max-width: 440px;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 35px rgba(239, 68, 68, 0.15);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    overflow: hidden;
    text-align: center;
    padding: 28px 24px;
    animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .modal-delete-icon-wrap {
    display: flex;
    justify-content: center;
    margin-bottom: 16px;
  }
  .delete-icon-circle {
    width: 58px;
    height: 58px;
    border-radius: 50%;
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #f87171;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
  }
  .modal-delete-title {
    margin: 0 0 8px 0;
    font-size: 18px;
    font-weight: 700;
    color: #f8fafc;
  }
  .modal-delete-desc {
    margin: 0 0 16px 0;
    font-size: 13.5px;
    color: #94a3b8;
    line-height: 1.5;
  }
  .delete-target-badge {
    display: inline-block;
    margin-top: 4px;
    background: rgba(168, 85, 247, 0.15);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #e9d5ff;
    padding: 3px 10px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 13px;
  }
  .delete-warning-box {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 10px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
    text-align: left;
    margin-bottom: 22px;
  }
  .warning-icon {
    font-size: 18px;
    flex-shrink: 0;
  }
  .warning-text {
    font-size: 12px;
    color: #fca5a5;
    line-height: 1.4;
  }
  .modal-delete-actions {
    display: flex;
    gap: 12px;
    justify-content: center;
  }
  .modal-delete-actions button {
    flex: 1;
    margin: 0;
  }
  .btn-danger-confirm {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    border: 1px solid #f87171;
    color: #ffffff;
    padding: 10px 18px;
    font-size: 13.5px;
    font-weight: 600;
    border-radius: 10px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s ease;
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3);
  }
  .btn-danger-confirm:hover:not(:disabled) {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    box-shadow: 0 6px 18px rgba(239, 68, 68, 0.5);
    transform: translateY(-1px);
  }
  .btn-danger-confirm:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .existing-groups-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
    gap: 14px;
  }
  .group-card-item {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(139, 92, 246, 0.25);
    border-radius: 12px;
    padding: 14px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 12px;
  }
  .group-card-item:hover {
    background: rgba(30, 41, 59, 0.9);
    border-color: rgba(168, 85, 247, 0.6);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(147, 51, 234, 0.15);
  }
  .group-card-top {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }
  .group-icon-wrap {
    color: #a855f7;
    background: rgba(168, 85, 247, 0.12);
    padding: 8px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .group-title-info {
    flex: 1;
    overflow: hidden;
  }
  .group-type-tag {
    font-size: 11px;
    color: #a855f7;
    font-weight: 600;
    margin-bottom: 2px;
  }
  .group-name-text {
    font-size: 14px;
    font-weight: 600;
    color: #f8fafc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .btn-card-delete {
    background: none;
    border: none;
    color: #ef4444;
    opacity: 0.6;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: opacity 0.2s;
  }
  .btn-card-delete:hover {
    opacity: 1;
    background: rgba(239, 68, 68, 0.15);
  }
  .group-card-bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 10px;
  }
  .group-meta-stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .stat-badge {
    font-size: 11px;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .stat-badge.count-active {
    color: #34d399;
  }
  .stat-badge.count-empty {
    color: #f59e0b;
  }
  .stat-date {
    font-size: 10px;
    color: #64748b;
  }
  .btn-select-group {
    background: rgba(147, 51, 234, 0.18);
    border: 1px solid rgba(147, 51, 234, 0.4);
    color: #d8b4fe;
    padding: 6px 12px;
    font-size: 12px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
  }
  .btn-select-group:hover {
    background: #9333ea;
    color: white;
  }

  /* Recent Project History Section */
  .project-history-section {
    max-width: 900px;
    margin: 0 auto;
    width: 100%;
  }
  .history-table-container {
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow-x: auto;
  }
  .project-history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    text-align: left;
  }
  .project-history-table th {
    background: rgba(30, 41, 59, 0.8);
    color: #94a3b8;
    font-weight: 600;
    padding: 10px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 12px;
  }
  .project-history-table td {
    padding: 12px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    color: #e2e8f0;
  }
  .history-table-row {
    cursor: pointer;
    transition: background 0.15s;
  }
  .history-table-row:hover {
    background: rgba(147, 51, 234, 0.08);
  }
  .file-name-cell {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
    color: #60a5fa;
  }
  .group-pill {
    background: rgba(168, 85, 247, 0.15);
    color: #d8b4fe;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
  }
  .type-pill {
    background: rgba(59, 130, 246, 0.15);
    color: #93c5fd;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 11px;
  }
  .td-date {
    color: #94a3b8;
    font-size: 12px;
  }
  .btn-table-view {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #60a5fa;
    padding: 4px 10px;
    font-size: 11px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-table-view:hover {
    background: #2563eb;
    color: white;
  }

  .btn-auto-fix-glow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #f59e0b 0%, #ec4899 50%, #8b5cf6 100%);
    color: #ffffff;
    border: none;
    padding: 10px 18px;
    border-radius: 8px;
    font-size: 13.5px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(236, 72, 153, 0.4), 0 0 20px rgba(245, 158, 11, 0.25);
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    animation: pulseAutoFix 2.5s infinite;
  }
  .btn-auto-fix-glow:hover {
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 6px 20px rgba(236, 72, 153, 0.6), 0 0 25px rgba(245, 158, 11, 0.4);
    filter: brightness(1.1);
  }
  .btn-auto-fix-glow:active {
    transform: translateY(0);
  }
  .btn-auto-fix-glow:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    animation: none;
  }

  .btn-mini-autofix {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(236, 72, 153, 0.25));
    border: 1px solid rgba(245, 158, 11, 0.5);
    color: #fde047;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .btn-mini-autofix:hover {
    background: linear-gradient(135deg, #f59e0b, #ec4899);
    color: #ffffff;
    border-color: transparent;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.4);
  }

  @keyframes pulseAutoFix {
    0%, 100% {
      box-shadow: 0 4px 14px rgba(236, 72, 153, 0.4), 0 0 20px rgba(245, 158, 11, 0.25);
    }
    50% {
      box-shadow: 0 4px 22px rgba(236, 72, 153, 0.7), 0 0 30px rgba(245, 158, 11, 0.5);
    }
  }
</style>
