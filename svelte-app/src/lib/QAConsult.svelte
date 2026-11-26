<script context="module">
  /** @type {AbortController | null} */
  let currentScanAbortController = null;
  let currentScanClientId = "";
  let currentScanPendingId = "";
  let currentScanStartedAt = 0;
  let userCancelledActiveScan = false;
</script>

<script>
  import { createEventDispatcher, onMount, onDestroy } from "svelte";
  import { fade } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { authUser, authEmail } from "./authStore.js";
  import { qaHistory, selectedHistory, loadQAHistoryFromDB, selectedProjectStore, qaSessionGroups, activeQAContext, loadQAGroupsFromDB, activeSidebarGroup, activeScanStatus, allGroups, qaRefinementFeedback } from "./qaHistoryStore.js";
  import GateResultModal from "./GateResultModal.svelte";
  import ProjectSelection from "./ProjectSelection.svelte";
  import SpectraLoading from "./SpectraLoading.svelte";
  import QADocumentInspector from "./QADocumentInspector.svelte";
  import { MASTER_DOC_TYPES } from "./constants.js";

  const dispatch = createEventDispatcher();

  const qaConsultStages = [
    { label: "1. อ่านหน้าเอกสาร", minPct: 0 },
    { label: "2. เทียบฐานความรู้โครงการ", minPct: 40 },
    { label: "3. AI วิเคราะห์ข้อบกพร่อง", minPct: 70 },
    { label: "4. ตรวจเกณฑ์ Exit Criteria", minPct: 85 }
  ];

  let isCancellingScan = false;
  let elapsedScanSec = 0;
  /** @type {any} */
  let elapsedInterval = null;

  function startElapsedClock(startTs) {
    if (elapsedInterval) clearInterval(elapsedInterval);
    const base = startTs || currentScanStartedAt || Date.now();
    elapsedScanSec = Math.max(0, Math.floor((Date.now() - base) / 1000));
    elapsedInterval = setInterval(() => {
      elapsedScanSec = Math.max(0, Math.floor((Date.now() - base) / 1000));
    }, 1000);
  }

  function stopElapsedClock() {
    if (elapsedInterval) {
      clearInterval(elapsedInterval);
      elapsedInterval = null;
    }
    elapsedScanSec = 0;
  }

  onDestroy(() => {
    if (elapsedInterval) {
      clearInterval(elapsedInterval);
      elapsedInterval = null;
    }
  });

  let inspectorRef;
  /** @type {number | 'global' | null} */
  let inspectorPageNumber = null;
  /** @type {number | null} */
  let inspectorFindingIndex = null;
  let isLoadingInspectorPages = false;

  async function loadInspectorPagesForTransaction(transactionId) {
    if (!transactionId || String(transactionId).startsWith('pending-') || String(transactionId).startsWith('scan-')) return;
    isLoadingInspectorPages = true;
    try {
      const res = await fetch(`/api/qa_consult/transaction/${encodeURIComponent(transactionId)}/pages`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && scanResult && (!scanResult.id || String(scanResult.id) === String(transactionId))) {
          scanResult = {
            ...scanResult,
            pages: data.pages || [],
            page_issue_summary: data.page_issue_summary || null,
            qa_findings: (data.qa_findings && data.qa_findings.length > 0) ? data.qa_findings : scanResult.qa_findings
          };
        }
      }
    } catch (err) {
      console.warn("Could not load document pages for inspector:", err);
    } finally {
      isLoadingInspectorPages = false;
    }
  }

  function jumpToFindingInInspector(finding, idx) {
    const pNum = finding?.page_number ? Number(finding.page_number) : "global";
    const fIdx = finding?.finding_index !== undefined ? finding.finding_index : idx;
    inspectorPageNumber = pNum;
    inspectorFindingIndex = fIdx;
    if (inspectorRef && typeof inspectorRef.focusFinding === "function") {
      inspectorRef.focusFinding(pNum, fIdx);
    }
    scrollToSection("qa-doc-inspector-section");
  }

  /** @param {any} item */
  function getExitItemPageNumbers(item) {
    if (!item) return [];
    const nums = new Set();
    if (Array.isArray(item.page_numbers)) {
      item.page_numbers.forEach(n => {
        const v = Number(n);
        if (Number.isInteger(v) && v > 0) nums.add(v);
      });
    }
    if (item.page_number !== null && item.page_number !== undefined && Number(item.page_number) > 0) {
      nums.add(Number(item.page_number));
    }
    const text = `${item.page_ref || ''} ${item.evidence_text || ''} ${item.remarks || ''}`;
    const rx = /(?:หน้า|page|p\.)\s*[:#]?\s*(\d+)/gi;
    let m;
    while ((m = rx.exec(text)) !== null) {
      const v = Number(m[1]);
      if (Number.isInteger(v) && v > 0) nums.add(v);
    }
    if (nums.size === 0 && item.status === 'FAIL' && Array.isArray(scanResult?.qa_findings)) {
      const baseCode = String(item.item_code || '').replace(/^.*-/, '').trim();
      if (baseCode === '1.1' || String(item.category || '').includes('Defect')) {
        scanResult.qa_findings.forEach(f => {
          const sev = String(f.severity || '').toLowerCase();
          if ((sev === 'critical' || sev === 'high') && f.page_number && Number(f.page_number) > 0) {
            nums.add(Number(f.page_number));
          }
        });
      }
    }
    return Array.from(nums).sort((a, b) => a - b);
  }

  function jumpToPageInInspector(pageNum) {
    inspectorPageNumber = pageNum ? Number(pageNum) : "global";
    inspectorFindingIndex = null;
    if (inspectorRef && typeof inspectorRef.focusPage === "function") {
      inspectorRef.focusPage(inspectorPageNumber);
    }
    scrollToSection("qa-doc-inspector-section");
  }

  let reportViewMode = "formatted"; // 'formatted' | 'raw'

  // Build structured Page-by-Page Summary grouped by page number for the Report Box
  $: reportPageGroups = (() => {
    if (!scanResult) return [];
    const map = new Map();
    const ensure = (key, label, pageNum) => {
      if (!map.has(key)) map.set(key, { key, label, pageNum, items: [] });
      return map.get(key);
    };
    (scanResult.qa_findings || []).forEach((f, idx) => {
      const pn = f.page_number ? Number(f.page_number) : null;
      const key = pn ? `p-${pn}` : "global";
      const lbl = pn ? `หน้า ${pn}` : "ภาพรวมทั้งเอกสาร";
      ensure(key, lbl, pn).items.push({
        kind: "finding",
        severity: f.severity || "Info",
        topic: f.check_type || "QA Finding",
        location: f.location || f.page_label || lbl,
        summary: f.issue || "-",
        idx
      });
    });
    (scanResult.exit_criteria_eval?.items || [])
      .filter(it => String(it.status || "").toUpperCase() === "FAIL")
      .forEach(it => {
        const pns = getExitItemPageNumbers(it);
        const targets = pns.length > 0 ? pns : [null];
        targets.forEach(pn => {
          const key = pn ? `p-${pn}` : "global";
          const lbl = pn ? `หน้า ${pn}` : "ภาพรวมทั้งเอกสาร";
          ensure(key, lbl, pn).items.push({
            kind: "exit_fail",
            severity: "FAIL",
            topic: `Exit Criteria [${it.item_code}]`,
            location: it.location || it.page_ref || lbl,
            summary: it.question_text || it.remarks || "-"
          });
        });
      });
    return Array.from(map.values()).sort((a, b) => {
      if (a.pageNum === null) return 1;
      if (b.pageNum === null) return -1;
      return a.pageNum - b.pageNum;
    });
  })();

  function escapeHtmlSafe(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /**
   * Convert QA Consult Markdown report into clean, structured HTML headings, bullets, and highlighted [หน้า N] chips.
   * Strictly escapes HTML first before applying safe inline formatting.
   */
  function formatConsultReportHtml(rawText) {
    const safe = escapeHtmlSafe(rawText);
    const lines = safe.split(/\r?\n/);
    const out = [];
    let inList = false;

    const inlineFormat = (s) => {
      return s
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\[(หน้า\s*\d+(?:\s*\|[^\]]+)?|Page\s*\d+(?:\s*\|[^\]]+)?)\]/gi, '<span class="rpt-page-badge">$1</span>');
    };

    for (const rawLine of lines) {
      const t = rawLine.trim();
      if (!t) {
        if (inList) { out.push("</ul>"); inList = false; }
        continue;
      }
      if (/^---+$/.test(t)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push('<hr class="rpt-divider" />');
        continue;
      }
      const hMatch = t.match(/^(#{1,4})\s+(.+)$/);
      if (hMatch) {
        if (inList) { out.push("</ul>"); inList = false; }
        const lvl = hMatch[1].length;
        const cleanTitle = hMatch[2].replace(/^\*\*|\*\*$/g, "");
        out.push(`<div class="rpt-heading rpt-h${Math.min(lvl, 3)}">${inlineFormat(cleanTitle)}</div>`);
        continue;
      }
      // Numbered bold section headers like "**1. ความสอดคล้อง**"
      const numHead = t.match(/^\*\*(\d+\..+?)\*\*$/);
      if (numHead) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<div class="rpt-heading rpt-h2">${inlineFormat(numHead[1])}</div>`);
        continue;
      }
      const bulletMatch = t.match(/^[\*\-\•]\s+(.+)$/);
      if (bulletMatch) {
        if (!inList) { out.push('<ul class="rpt-list">'); inList = true; }
        out.push(`<li>${inlineFormat(bulletMatch[1])}</li>`);
        continue;
      }
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<p class="rpt-para">${inlineFormat(t)}</p>`);
    }
    if (inList) out.push("</ul>");
    return out.join("\n");
  }

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
  $: if (selectedProjectObj && projects.length > 0) {
    const curName = String(selectedProjectObj.name || selectedProjectObj.project_name || '').trim();
    const curCode = String(selectedProjectObj.project_code || '').trim();
    if (!curName || curName === curCode) {
      const matchedProj = projects.find(p =>
        (selectedProjectObj.id && String(p.id) === String(selectedProjectObj.id)) ||
        (selectedProjectObj.project_id && String(p.project_id || p.id) === String(selectedProjectObj.project_id)) ||
        (curCode && String(p.project_code || '').trim().toLowerCase() === curCode.toLowerCase())
      );
      if (matchedProj && (matchedProj.name || matchedProj.project_name) && (matchedProj.name || matchedProj.project_name) !== curCode) {
        selectedProjectStore.set(matchedProj);
      }
    }
  }
  $: resolvedProjectLabel = (() => {
    if (!selectedProjectObj) return '';
    const code = String(selectedProjectObj.project_code || '').trim();
    const name = String(selectedProjectObj.name || selectedProjectObj.project_name || '').trim();
    if (code && name && code.toLowerCase() !== name.toLowerCase()) {
      return `${code} — ${name}`;
    }
    return code || name || 'Project';
  })();
  /** @param {any} p */
  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  onMount(async () => {
    loadQAGroupsFromDB();
    loadQAHistoryFromDB();

    // Load Skills (separate try/catch so failure won't block projects)
    try {
      const resSkills = await fetch("/api/skills?active_only=true");
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

  let sourceGeneratedDocId = null;

  $: if ($activeQAContext) {
    const ctx = $activeQAContext;
    activeQAContext.set(null); // Clear it
    
    if (ctx.project) {
      selectedProjectStore.set(ctx.project);
    }
    const cleanGName = String(ctx.group_name || '').replace(/^\[.*?\]\s*/, '').trim() || 'General';
    scanGroupName = cleanGName;
    scanGroupType = ctx.group_type || 'Project Plan';
    isGroupNameSet = true;
    sourceGeneratedDocId = ctx.source_generated_doc_id || null;

    // If file is passed from QA Document Creation or another module
    if (ctx.file) {
      file = ctx.file;
      isProcessing = false;
      scanResult = null;
      if (ctx.doc_types && Array.isArray(ctx.doc_types) && ctx.doc_types.length > 0) {
        selectedDocTypes = [...ctx.doc_types];
      } else if (ctx.group_type) {
        selectedDocTypes = [ctx.group_type];
      }
      if (ctx.skill_ids && Array.isArray(ctx.skill_ids) && ctx.skill_ids.length > 0) {
        selectedSkills = [...ctx.skill_ids];
      } else {
        selectedSkills = [];
      }
    } else {
      // Check if this group is currently scanning
      const scan = $activeScanStatus;
      const cleanCurrent = cleanGName.toLowerCase();
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
  }

  $: if ($activeScanStatus && $activeScanStatus.isProcessing) {
    const cleanCurrent = String(scanGroupName || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
    const cleanScanning = String($activeScanStatus.groupName || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
    if (cleanCurrent === cleanScanning) {
      isProcessing = true;
      processStatus = $activeScanStatus.processStatus || processStatus;
      progressPct = $activeScanStatus.progressPct || progressPct;
      if (!elapsedInterval) {
        startElapsedClock($activeScanStatus.startedAt);
      }
    }
  }

  $: if ($selectedHistory) {
    const item = $selectedHistory;
    selectedHistory.set(null); // Clear it so it doesn't re-trigger

    const cleanGName = String(item.group_name || 'General').replace(/^\[.*?\]\s*/, '').trim() || 'General';

    if (item.is_processing) {
      scanGroupName = cleanGName;
      scanGroupType = item.group_type || '';
      isGroupNameSet = true;
      
      const p = (projects || []).find(p => String(p.id) === String(item.project_id) || String(p.project_id) === String(item.project_id) || (p.project_code && item.project_code && p.project_code === item.project_code));
      if (p) {
        selectedProjectStore.set(p);
      } else if (item.project_id || item.project_code) {
        selectedProjectStore.set({ id: item.project_id, project_id: item.project_id, project_code: item.project_code || 'Project', name: item.project_code || 'Project' });
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

      inspectorPageNumber = null;
      inspectorFindingIndex = null;
      scanResult = {
        id: item.id,
        status: 'success',
        report: item.report,
        email: item.email || email, // If email is in DB, use it, otherwise use current
        total_pages: item.total_pages,
        doc_type: item.docType,
        filename: item.filename,
        emailSent: false,
        excel_url: computedExcelUrl,
        qa_findings: item.qa_findings,
        exit_criteria_eval: evalData,
        pages: item.pages || [],
        page_issue_summary: item.page_issue_summary || null
      };

      if (item.id && (!item.pages || item.pages.length === 0)) {
        loadInspectorPagesForTransaction(item.id);
      }

      scanGroupName = cleanGName;
      scanGroupType = item.group_type || '';
      isGroupNameSet = true;

      const p = (projects || []).find(p => String(p.id) === String(item.project_id) || String(p.project_id) === String(item.project_id) || (p.project_code && item.project_code && p.project_code === item.project_code));
      if (p) {
        selectedProjectStore.set(p);
      } else if (item.project_id || item.project_code) {
        selectedProjectStore.set({ id: item.project_id, project_id: item.project_id, project_code: item.project_code || 'Project', name: item.project_code || 'Project' });
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
      { item_code: '1.1', category: 'Defect & Comment Resolution', question_text: 'ต้องไม่มีข้อบกพร่อง (Defect) ระดับ Critical หรือ High คงค้างในเอกสาร', target_metric: '0 Critical/High Bugs (ผ่าน 100%)', severity: 'Critical', is_mandatory: true },
      { item_code: '1.2', category: 'Defect & Comment Resolution', question_text: 'ต้องไม่มีข้อผิดพลาดด้าน Logic การคำนวณ หรือการไหลของกระบวนการทำงาน (Process Flow)', target_metric: '100% Correct Logic', severity: 'Critical', is_mandatory: true },
      { item_code: '1.3', category: 'Defect & Comment Resolution', question_text: 'ต้องไม่มี Broken Links, รหัสอ้างอิงที่ไม่ตรงกัน หรือภาพประกอบที่ไม่ถูกต้อง', target_metric: '0 Broken Links/Refs', severity: 'Major', is_mandatory: true },
      { item_code: '2.1', category: 'Content Accuracy & Completeness', question_text: 'มีเนื้อหาครบถ้วนตาม Scope, Objective และ Requirement ที่ตกลงไว้', target_metric: '100% Scope Coverage', severity: 'Critical', is_mandatory: true },
      { item_code: '2.2', category: 'Content Accuracy & Completeness', question_text: 'มีรายละเอียด Input / Output / Data Dictionary ครบถ้วนชัดเจน', target_metric: '100% Data Specs', severity: 'Major', is_mandatory: true },
      { item_code: '2.3', category: 'Content Accuracy & Completeness', question_text: 'ครอบคลุม Exception Cases, Edge Cases และ Error Handling', target_metric: '100% Edge Cases Handling', severity: 'Major', is_mandatory: true },
      { item_code: '2.4', category: 'Content Accuracy & Completeness', question_text: 'มีเกณฑ์การยอมรับ (Acceptance Criteria / Definition of Done) ชัดเจนทุกหัวข้อ', target_metric: '100% Defined Criteria', severity: 'Major', is_mandatory: true },
      { item_code: '3.1', category: 'Format & Consistency', question_text: 'ต้องไม่มีคำผิด (Spelling / Typos) เกินเกณฑ์มาตรฐานทั้งภาษาไทยและภาษาอังกฤษ', target_metric: '< 1% Typo Rate (คำผิด < 1%)', severity: 'Minor', is_mandatory: false },
      { item_code: '3.2', category: 'Format & Consistency', question_text: 'รูปแบบฟอนต์, ขนาดตัวอักษร, ระยะย่อหน้า และหัวข้อ มีความสม่ำเสมอทั้งเอกสาร', target_metric: '100% Style Consistency', severity: 'Minor', is_mandatory: false },
      { item_code: '3.3', category: 'Format & Consistency', question_text: 'การจัดวางตาราง, รูปภาพ และ Diagram มีความชัดเจน อ่านง่าย ไม่ตกขอบ', target_metric: '100% Visual Clarity', severity: 'Minor', is_mandatory: false },
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
      /** @type {number[]} */
      let pageNums = [];

      if (d.item_code === '1.1' && highCritical.length > 0) {
        st = 'FAIL';
        rem = `ไม่ผ่านเกณฑ์ — ตรวจพบข้อบกพร่องความรุนแรงระดับ Critical/High ในเอกสารจำนวน ${highCritical.length} รายการ (เป้าหมายต้องเป็น 0 รายการ)`;
        const previewLines = highCritical.slice(0, 4).map((f, idx) => {
          const pTag = f.page_number ? ` (หน้า ${f.page_number})` : '';
          return `${idx + 1}. [${f.severity || 'High'}] ${f.issue || '-'}${pTag}`;
        });
        if (highCritical.length > 4) {
          previewLines.push(`...และอีก ${highCritical.length - 4} รายการ (ดูครบทั้งหมดในตาราง QA Audit Findings ด้านล่าง)`);
        }
        evid = previewLines.join('\n');
        pageNums = Array.from(new Set(highCritical.map(f => Number(f.page_number)).filter(n => Number.isFinite(n) && n > 0)));
      } else if (d.item_code === '3.1' && typos.length > 0) {
        st = 'FAIL';
        rem = `ไม่ผ่านเกณฑ์ — ตรวจพบคำผิดหรือการสะกดคำไม่ถูกต้องจำนวน ${typos.length} รายการ`;
        const typoLines = typos.slice(0, 4).map((f, idx) => `${idx + 1}. ${f.issue || '-'}`);
        if (typos.length > 4) {
          typoLines.push(`...และอีก ${typos.length - 4} รายการ`);
        }
        evid = typoLines.join('\n');
        pageNums = Array.from(new Set(typos.map(f => Number(f.page_number)).filter(n => Number.isFinite(n) && n > 0)));
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
        page_numbers: pageNums,
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
  }).sort((a, b) => {
    const tA = new Date(a.latest_date || 0).getTime();
    const tB = new Date(b.latest_date || 0).getTime();
    return tB - tA;
  });

  $: currentProjectHistory = $qaHistory.filter(h => {
    if (!selectedProjectObj) return false;
    const pId = String(selectedProjectObj.id || selectedProjectObj.project_id || '');
    const pCode = String(selectedProjectObj.project_code || '').trim().toLowerCase();
    const hPid = String(h.project_id || '');
    const hCode = String(h.project_code || '').trim().toLowerCase();
    // Strict match: records without a project (e.g. orphaned MCP transactions) must NOT leak into every project
    if (!pId && !pCode) return false;
    return (pId && hPid && hPid === pId) || (pCode && hCode && hCode === pCode);
  }).sort((a, b) => {
    if (a.is_processing && !b.is_processing) return -1;
    if (!a.is_processing && b.is_processing) return 1;
    const tA = new Date(a.date || a.created_at || 0).getTime();
    const tB = new Date(b.date || b.created_at || 0).getTime();
    return tB - tA;
  });

  // Recent Project History Pagination
  let historyCurrentPage = 1;
  const historyItemsPerPage = 6;
  let lastHistoryProjectId = null;

  $: historyTotalPages = Math.max(1, Math.ceil(currentProjectHistory.length / historyItemsPerPage));
  $: paginatedProjectHistory = currentProjectHistory.slice(
    (historyCurrentPage - 1) * historyItemsPerPage,
    historyCurrentPage * historyItemsPerPage
  );

  // Keep page within valid bounds
  $: {
    if (historyCurrentPage > historyTotalPages) {
      historyCurrentPage = historyTotalPages;
    }
    if (historyCurrentPage < 1) {
      historyCurrentPage = 1;
    }
  }

  // Reset page when switching projects
  $: {
    const curPId = selectedProjectObj ? String(selectedProjectObj.id || selectedProjectObj.project_id || selectedProjectObj.project_code || '') : null;
    if (curPId !== lastHistoryProjectId) {
      lastHistoryProjectId = curPId;
      historyCurrentPage = 1;
    }
  }

  function goToHistoryPage(page) {
    if (typeof page === 'number' && page >= 1 && page <= historyTotalPages) {
      historyCurrentPage = page;
    }
  }

  function getVisibleHistoryPages(current, total) {
    if (total <= 5) {
      return Array.from({ length: total }, (_, i) => i + 1);
    }
    if (current <= 3) {
      return [1, 2, 3, 4, '...', total];
    }
    if (current >= total - 2) {
      return [1, '...', total - 3, total - 2, total - 1, total];
    }
    return [1, '...', current - 1, current, current + 1, '...', total];
  }

  $: cleanTargetGroupName = (() => {
    let raw = scanGroupName || (scanResult && scanResult.group_name) || ($activeSidebarGroup && $activeSidebarGroup.group_name) || '';
    while (/^\[.*?\]\s*/.test(raw)) {
      raw = raw.replace(/^\[.*?\]\s*/, '').trim();
    }
    return raw.trim().toLowerCase();
  })();

  $: currentGroupHistory = $qaHistory.filter(h => {
    if (!selectedProjectObj) return false;
    const pId = String(selectedProjectObj.id || selectedProjectObj.project_id || '');
    const pCode = String(selectedProjectObj.project_code || '').trim().toLowerCase();
    const hPid = String(h.project_id || '');
    const hCode = String(h.project_code || '').trim().toLowerCase();
    const matchProj = !hPid || !pId || hPid === pId || (pCode && hCode && hCode === pCode);
    if (!matchProj) return false;

    if (cleanTargetGroupName) {
      let cleanHGroup = String(h.group_name || 'General').trim();
      while (/^\[.*?\]\s*/.test(cleanHGroup)) {
        cleanHGroup = cleanHGroup.replace(/^\[.*?\]\s*/, '').trim();
      }
      cleanHGroup = cleanHGroup.toLowerCase();
      return cleanHGroup === cleanTargetGroupName || cleanHGroup.includes(cleanTargetGroupName) || cleanTargetGroupName.includes(cleanHGroup);
    }
    return true;
  }).sort((a, b) => {
    if (a.is_processing && !b.is_processing) return -1;
    if (!a.is_processing && b.is_processing) return 1;
    const tA = new Date(a.date || a.created_at || 0).getTime();
    const tB = new Date(b.date || b.created_at || 0).getTime();
    return tB - tA;
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
  /** @type {any} */
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

  /** @type {any[]} */
  let selectedDocTypes = [];
  /** @type {any[]} */
  let selectedSkills = [];

  // All skills are available for selection
  $: filteredSkills = skills;

  /** @type {any} */
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
  /** @type {any} */
  let fileInput;

  let isProcessing = false;
  let processStatus = "";
  let progressPct = 0;
  /** @type {any} */
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
      
      const hasCat12Fail = g.items.some((/** @type {any} */ i) => {
        if (i.status !== 'FAIL') return false;
        const cat = i.category || '';
        const baseCode = String(i.item_code || '').replace(/^.*-/, '').trim();
        const sev = String(i.severity || '').toUpperCase();
        const isMand = i.is_mandatory !== false;
        const isCat3Formatting = baseCode.startsWith('3.') || (cat.includes('Formatting') && !cat.includes('Defect') && !cat.includes('Content'));
        return (
          cat.includes('Defect') ||
          cat.includes('Content') ||
          baseCode.startsWith('1.') ||
          baseCode.startsWith('2.') ||
          sev === 'CRITICAL' ||
          (isMand && !isCat3Formatting)
        );
      });

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

  function normalizeDocTypeKey(val) {
    const s = String(val || '').trim().replace(/\s+/g, '').toUpperCase();
    if (s === 'REQUIREMENTS' || s === 'REQUIREMENT') return 'SRS';
    return s;
  }

  $: matchedCriteriaTemplate = exitCriteriaTemplates.find(t => 
    t.is_active && 
    t.doc_type && 
    t.doc_type.trim().toUpperCase() !== 'ALL' &&
    (
      t.doc_type.trim().toUpperCase() === scanGroupType.trim().toUpperCase() ||
      normalizeDocTypeKey(t.doc_type) === normalizeDocTypeKey(scanGroupType)
    )
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
  function isExcelFile(fName) {
    if (!fName) return false;
    const lower = fName.toLowerCase();
    return lower.endsWith('.xlsx') || lower.endsWith('.xls') || lower.endsWith('.xlsm') || lower.endsWith('.csv');
  }

  function isMarkdownFile(fName) {
    if (!fName) return false;
    const lower = fName.toLowerCase();
    return lower.endsWith('.md') || lower.endsWith('.txt');
  }

  function isValidQAFile(fName) {
    if (!fName) return false;
    const lower = fName.toLowerCase();
    return lower.endsWith('.pdf') || isExcelFile(fName) || isMarkdownFile(fName);
  }

  function handleDrop(e) {
    e.preventDefault();
    isDragging = false;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const selected = e.dataTransfer.files[0];
      if (!isValidQAFile(selected.name)) {
        toast("กรุณาเลือกไฟล์ PDF, Excel (.xlsx, .xls, .csv) หรือ Markdown (.md, .txt) เท่านั้น", "warning");
        return;
      }
      file = selected;
      if (isExcelFile(file.name) && selectedDocTypes.length === 0) {
        selectedDocTypes = ['Test Case'];
      }
    }
  }

  function handleFileSelect(e) {
    if (e.target.files && e.target.files.length > 0) {
      const selected = e.target.files[0];
      if (!isValidQAFile(selected.name)) {
        toast("กรุณาเลือกไฟล์ PDF, Excel (.xlsx, .xls, .csv) หรือ Markdown (.md, .txt) เท่านั้น", "warning");
        return;
      }
      file = selected;
      if (isExcelFile(file.name) && selectedDocTypes.length === 0) {
        selectedDocTypes = ['Test Case'];
      }
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
    isCancellingScan = false;
    userCancelledActiveScan = false;
    scanResult = null;
    progressPct = 10;
    processStatus = "กำลังอัปโหลดเอกสารและเริ่มประมวลผล...";
    currentScanStartedAt = Date.now();
    startElapsedClock(currentScanStartedAt);

    const cleanGroupName = scanGroupName.replace(/^\[.*?\]\s*/, '').trim() || 'General';
    scanGroupName = cleanGroupName;
    const pId = selectedProjectObj?.id || selectedProjectObj?.project_id;
    const scanId = `qascan-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    currentScanClientId = scanId;

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
    currentScanPendingId = pendingItem.id;
    qaHistory.update(h => [pendingItem, ...h]);

    activeScanStatus.set({
      isProcessing: true,
      scanId,
      startedAt: currentScanStartedAt,
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
    formData.append("scan_id", scanId);
    formData.append("doc_type", JSON.stringify(selectedDocTypes));
    formData.append("email", finalEmail);
    formData.append("skill_id", JSON.stringify(selectedSkills));
    if (selectedProjectObj) {
      formData.append("project_id", pId);
      formData.append("project_name", `${selectedProjectObj.project_code || ''} ${selectedProjectObj.name || ''}`.trim() || 'Unknown Project');
    }
    formData.append("group_name", cleanGroupName);
    formData.append("group_type", scanGroupType);
    if (sourceGeneratedDocId) {
      formData.append("source_generated_doc_id", String(sourceGeneratedDocId));
    }

    const token = (typeof window !== 'undefined' && window.localStorage) ? (localStorage.getItem('jwt_token') || '') : '';
    const currentUsername = (typeof window !== 'undefined' && window.localStorage) ? (localStorage.getItem('auth_user') || '') : '';
    if (currentUsername) {
      formData.append("username", currentUsername);
    }

    const abortCtrl = new AbortController();
    currentScanAbortController = abortCtrl;

    try {
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      // Create a stream request
      const response = await fetch("/api/qa_consult", {
        method: "POST",
        headers,
        body: formData,
        signal: abortCtrl.signal
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
              inspectorPageNumber = null;
              inspectorFindingIndex = null;
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
            } else if (data.type === "cancelled") {
              isProcessing = false;
              isCancellingScan = false;
              stopElapsedClock();
              activeScanStatus.set(null);
              qaHistory.update(h => h.filter(item => item.id !== pendingItem.id));
              break;
            } else if (data.type === "error") {
              throw new Error(data.message);
            }
          }
        }
      }
    } catch (err) {
      const isAbort =
        userCancelledActiveScan ||
        (err && (err.name === "AbortError" || String(err).includes("AbortError")));
      if (!isAbort) {
        const msg = err instanceof Error ? err.message : String(err);
        toast(`เกิดข้อผิดพลาด: ${msg}`, "error");
      }
      isProcessing = false;
      isCancellingScan = false;
      stopElapsedClock();
      activeScanStatus.set(null);
      qaHistory.update(h => h.filter(item => item.id !== pendingItem.id));
    } finally {
      if (currentScanAbortController === abortCtrl) {
        currentScanAbortController = null;
      }
      stopElapsedClock();
      isCancellingScan = false;
      activeScanStatus.set(null);
      await loadQAHistoryFromDB();
      await loadQAGroupsFromDB();
    }
  }

  async function cancelQAConsultScan() {
    if (isCancellingScan) return;
    isCancellingScan = true;
    userCancelledActiveScan = true;

    const scanInfo = $activeScanStatus;
    const targetScanId = currentScanClientId || scanInfo?.scanId || "";
    const targetPendingId = currentScanPendingId || scanInfo?.pendingId || "";
    const token =
      typeof window !== "undefined" && window.localStorage
        ? localStorage.getItem("jwt_token") || ""
        : "";

    try {
      await fetch("/api/qa_consult/cancel", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ scan_id: targetScanId })
      });
    } catch (_) {
      // Ignore network error during cancellation
    }

    try {
      currentScanAbortController?.abort();
    } catch (_) {}
    currentScanAbortController = null;
    currentScanClientId = "";
    currentScanPendingId = "";

    stopElapsedClock();
    activeScanStatus.set(null);
    if (targetPendingId) {
      qaHistory.update(h => h.filter(item => item.id !== targetPendingId));
    } else {
      qaHistory.update(h => h.filter(item => !item.is_processing));
    }
    if ($selectedHistory && $selectedHistory.is_processing) {
      selectedHistory.set(null);
    }

    isProcessing = false;
    isCancellingScan = false;
    progressPct = 0;
    processStatus = "";
    toast("หยุดการสแกนเอกสารเรียบร้อยแล้ว", "info");
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

  /**
   * Compute total correction items: qa_findings + exit criteria FAIL items (de-duplicated)
   */
  function getTotalCorrectionCount() {
    if (!scanResult) return 0;
    const qaCount = (scanResult.qa_findings || []).length;
    const exitFailCount = getExitCriteriaFailedItems().length;
    return qaCount + exitFailCount;
  }

  /**
   * Extract FAIL items from exit criteria evaluation as structured findings
   */
  function getExitCriteriaFailedItems() {
    if (!scanResult?.exit_criteria_eval?.items) return [];
    return scanResult.exit_criteria_eval.items
      .filter(item => item.status === 'FAIL')
      .map(item => ({
        check_type: `Exit Criteria [${item.item_code}] - ${item.category || ''}`,
        issue: item.remarks || item.question_text || '',
        severity: item.severity || 'Major',
        found_incorrect: item.evidence_text || '',
        correct_value: item.target_metric || '',
        recommendation: `แก้ไขให้ผ่านเกณฑ์: ${item.question_text || ''}`
      }));
  }

  async function sendFindingsToDocCreation() {
    if (!scanResult) return;
    
    isSendingToDocCreation = true;
    try {
      const activeProj = $selectedProjectStore;
      const targetDocType = scanResult.doc_type || (selectedDocTypes && selectedDocTypes[0]) || scanGroupType || 'SRS';
      let cleanDocName = scanResult.filename || scanResult.doc_name || scanGroupName || 'Document';
      // Strip extension if present (.pdf, .docx, .md)
      cleanDocName = cleanDocName.replace(/\.[^/.]+$/, "");
      
      // Merge qa_findings + exit criteria failed items for a complete correction list
      const qaFindings = scanResult.qa_findings || [];
      const exitFailItems = getExitCriteriaFailedItems();
      const findingsList = [...qaFindings, ...exitFailItems];
      const exitEval = scanResult.exit_criteria_eval || null;

      const payload = {
        project_id: activeProj ? (activeProj.id || activeProj.project_id) : null,
        project_code: activeProj?.project_code || '',
        project_name: activeProj?.name || activeProj?.project_name || '',
        group_name: scanGroupName,
        group_type: scanGroupType,
        skill_ids: [],
        doc_name: cleanDocName,
        doc_type: targetDocType,
        findings: findingsList,
        exit_criteria_eval: exitEval,
        total_pages: scanResult.total_pages || 1,
        source_filename: scanResult.filename || cleanDocName,
        source_doc_id: sourceGeneratedDocId || null,
        raw_markdown: scanResult.markdown || scanResult.extracted_text || scanResult.raw_text || '',
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

  let isReevaluatingExitCriteria = false;

  async function reevaluateExitCriteria() {
    if (!scanResult || isReevaluatingExitCriteria) return;
    isReevaluatingExitCriteria = true;
    try {
      const activeProj = $selectedProjectStore;
      const pId = scanResult.project_id || (activeProj ? (activeProj.id || activeProj.project_id) : null);
      const targetDocType = (selectedDocTypes && selectedDocTypes.length > 0)
        ? selectedDocTypes.join(', ')
        : (scanResult.doc_type || scanGroupType || 'ALL');
      const res = await fetch('/api/qa_consult/reevaluate_exit_criteria', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transaction_id: scanResult.id || null,
          project_id: pId,
          doc_type: targetDocType,
          filename: scanResult.filename || 'Document.pdf',
          group_name: scanResult.group_name || scanGroupName || 'General',
          group_type: scanResult.group_type || scanGroupType || '',
          extracted_text: scanResult.extracted_text || scanResult.raw_text || '',
          report: scanResult.report || '',
          qa_findings: scanResult.qa_findings || []
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'ไม่สามารถประเมิน Exit Criteria ใหม่ได้');
      }
      scanResult = {
        ...scanResult,
        exit_criteria_eval: data.exit_criteria_eval,
        excel_url: data.excel_url || scanResult.excel_url
      };
      gateResultData = data.exit_criteria_eval;
      toast(`ประเมิน Exit Criteria Review Gate ใหม่สำเร็จ (${data.exit_criteria_eval?.status || 'DONE'} — ${data.exit_criteria_eval?.score_percentage ?? 100}%)`, 'success');
    } catch (err) {
      console.error('Re-evaluate exit criteria error:', err);
      toast('เกิดข้อผิดพลาดในการประเมิน Exit Criteria ใหม่: ' + err.message, 'error');
    } finally {
      isReevaluatingExitCriteria = false;
    }
  }
  function handleWindowKeydown(e) {
    if (e.key !== 'Escape') return;
    if (docTypeOpen || skillOpen || groupTypeOpen) {
      docTypeOpen = false;
      skillOpen = false;
      groupTypeOpen = false;
      return;
    }
    if (showCreateGroupModal) {
      closeCreateGroupModal();
    } else if (showDeleteGroupModal && !isDeletingGroup) {
      cancelDeleteGroup();
    } else if (showConfirmModal && !isSendingEmail) {
      showConfirmModal = false;
    } else if (showSuccessModal) {
      showSuccessModal = false;
    }
  }
</script>

  <svelte:window
    on:click={() => { docTypeOpen = false; skillOpen = false; groupTypeOpen = false; }}
    on:keydown={handleWindowKeydown}
  />

<div class="qa-container" in:fade class:full-width={!!scanResult}>
  {#if !selectedProjectObj}
    <ProjectSelection 
      {projects} 
      on:select={(e) => selectProject(e.detail)} 
    />

  {:else if !isGroupNameSet}
    <!-- GROUP MANAGEMENT & CREATION VIEW -->
    <div class="scan-group-view">
      <div class="scan-group-command-banner">
        <div class="banner-left">
          <button type="button" class="btn-back-pill" on:click={() => { selectedProjectStore.set(null); isGroupNameSet = false; scanGroupName = ""; }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
            </svg>
            <span>ย้อนกลับไปหน้าเลือกโครงการ</span>
          </button>
          <div class="banner-titles">
            <h2>QA Consult — เลือกกลุ่มการตรวจสอบ (Scan Group)</h2>
            <p>เลือกกลุ่มการตรวจสอบที่มีอยู่เพื่อทำการสแกนต่อ หรือสร้างกลุ่มการตรวจสอบใหม่สำหรับโครงการ</p>
          </div>
        </div>

        <div class="banner-right">
          <div class="active-project-pill">
            <span class="proj-live-dot" aria-hidden="true"></span>
            <span class="proj-lbl">โครงการปัจจุบัน:</span>
            <strong>{resolvedProjectLabel}</strong>
          </div>
          <div class="project-quick-stats">
            <span class="q-stat">
              <strong>{currentProjectGroups.length}</strong> กลุ่มตรวจ
            </span>
            <span class="q-divider" aria-hidden="true">•</span>
            <span class="q-stat">
              <strong>{currentProjectHistory.length}</strong> ประวัติสแกน
            </span>
          </div>
        </div>
      </div>

      <!-- EXISTING GROUPS SECTION (IF ANY) -->
      {#if currentProjectGroups.length > 0}
        <div class="group-management-section">
          <div class="section-title-bar">
            <div class="title-with-badge">
              <span class="section-icon-badge" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                </svg>
              </span>
              <h3>กลุ่มการตรวจสอบที่มีอยู่ในโครงการ</h3>
              <span class="section-count-pill">{currentProjectGroups.length}</span>
            </div>
            <button type="button" class="btn-create-group-trigger" on:click={openCreateGroupModal}>
              <svg class="plus-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="15" height="15">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
              <span>สร้างกลุ่มใหม่</span>
            </button>
          </div>

          <div class="existing-groups-grid">
            {#each currentProjectGroups as group, idx}
              {@const cleanGName = String(group.group_name || '').replace(/^\[.*?\]\s*/, '').trim() || group.group_name}
              {@const gType = group.group_type || 'Project Plan'}
              <div
                class="group-card-item"
                style="--card-idx: {idx};"
                data-gtype={gType.toLowerCase().includes('srs') ? 'srs' : gType.toLowerCase().includes('test') ? 'testcase' : 'plan'}
              >
                <button
                  type="button"
                  class="group-card-hitarea"
                  title={cleanGName}
                  aria-label={`เลือกกลุ่ม ${cleanGName}`}
                  on:click={() => selectExistingGroup(group)}
                ></button>
                <div class="group-card-top">
                  <div class="group-icon-wrap" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="19" height="19">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                  </div>
                  <div class="group-title-info">
                    <div class="group-type-tag">{gType}</div>
                    <div class="group-name-text" title={cleanGName}>{cleanGName}</div>
                  </div>
                  <button 
                    type="button"
                    class="btn-card-delete" 
                    title="ลบกลุ่มนี้" 
                    aria-label={`ลบกลุ่ม ${cleanGName}`}
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
                        <span class="active-stat-dot" aria-hidden="true"></span>
                        {group.scan_count} ไฟล์ตรวจแล้ว
                      </span>
                    {:else}
                      <span class="stat-badge count-empty">ยังไม่มีไฟล์</span>
                    {/if}
                    {#if group.latest_date}
                      <span class="stat-date">{formatHistoryTime(group.latest_date)}</span>
                    {/if}
                  </div>
                  <span class="btn-select-group" aria-hidden="true">
                    <span>เลือกกลุ่มนี้</span>
                    <span class="btn-arrow">&rarr;</span>
                  </span>
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
            <button type="button" class="btn-create-group-trigger lg" on:click={openCreateGroupModal}>
              <svg class="plus-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
              <span>สร้างกลุ่มการตรวจสอบใหม่</span>
            </button>
          </div>
        </div>
      {/if}

      <!-- MODAL: CREATE NEW GROUP -->
      {#if showCreateGroupModal}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={closeCreateGroupModal}>
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
          <div
            class="modal-group-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-group-modal-title"
            on:click|stopPropagation
          >
            <div class="modal-dialog-header">
              <div class="modal-dialog-title-wrap">
                <div class="modal-dialog-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                  </svg>
                </div>
                <div>
                  <h3 id="create-group-modal-title" class="modal-dialog-title">สร้างกลุ่มการตรวจสอบใหม่</h3>
                  <div class="modal-dialog-sub">โครงการ: <span class="sub-proj-name">{resolvedProjectLabel}</span></div>
                </div>
              </div>
              <button type="button" class="btn-dialog-close" title="ปิดหน้าต่าง" aria-label="ปิดหน้าต่าง" on:click={closeCreateGroupModal}>✕</button>
            </div>

            <div class="modal-dialog-body">
              <div class="setting-group relative">
                <label for="qa-scan-group-name">ชื่อการตรวจสอบ (Group Name) <span class="req-star">*</span></label>
                <input
                  id="qa-scan-group-name"
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
                <!-- svelte-ignore a11y-click-events-have-key-events -->
                <!-- svelte-ignore a11y-no-static-element-interactions -->
                <div class="custom-select" on:click|stopPropagation={() => { groupTypeOpen = !groupTypeOpen; }}>
                  <div
                    class="select-trigger"
                    class:open={groupTypeOpen}
                    role="button"
                    tabindex="0"
                    aria-haspopup="listbox"
                    aria-expanded={groupTypeOpen}
                    on:keydown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        groupTypeOpen = !groupTypeOpen;
                      } else if (e.key === 'Escape' && groupTypeOpen) {
                        e.stopPropagation();
                        groupTypeOpen = false;
                      }
                    }}
                  >
                    <span class="select-trigger-label">{scanGroupType}</span>
                    <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
                  </div>
                  {#if groupTypeOpen}
                    <div class="options-menu" role="listbox" transition:fade={{duration: 100}}>
                      {#each masterGroupTypes as type}
                        <div
                          class="option-item"
                          class:selected={scanGroupType === type}
                          role="option"
                          aria-selected={scanGroupType === type}
                          tabindex="0"
                          on:click|stopPropagation={() => { scanGroupType = type; groupTypeOpen = false; }}
                          on:keydown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              e.stopPropagation();
                              scanGroupType = type;
                              groupTypeOpen = false;
                            }
                          }}
                        >
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
              <button type="button" class="btn-dialog-cancel" on:click={closeCreateGroupModal}>ยกเลิก</button>
              <button 
                type="button"
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
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={() => !isDeletingGroup && cancelDeleteGroup()}>
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
          <div
            class="modal-delete-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-group-modal-title"
            on:click|stopPropagation
          >
            <div class="modal-delete-icon-wrap" aria-hidden="true">
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
              <h3 id="delete-group-modal-title" class="modal-delete-title">ยืนยันการลบกลุ่มการตรวจสอบ</h3>
              <p class="modal-delete-desc">
                คุณต้องการลบกลุ่ม <span class="delete-target-badge">[{groupToDelete.group_type || 'General'}] {groupToDelete.group_name}</span>
              </p>

              <div class="delete-warning-box">
                <div class="warning-icon" aria-hidden="true">⚠️</div>
                <div class="warning-text">
                  ประวัติการสแกนเอกสารและรายงานผล QA ทั้งหมดในกลุ่มนี้จะถูกลบอย่างถาวร
                </div>
              </div>
            </div>

            <div class="modal-delete-actions">
              <button type="button" class="btn-dialog-cancel" on:click={cancelDeleteGroup} disabled={isDeletingGroup}>
                ยกเลิก
              </button>
              <button type="button" class="btn-danger-confirm" on:click={executeDeleteGroup} disabled={isDeletingGroup}>
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
              <span class="section-icon-badge history-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                  <line x1="16" y1="13" x2="8" y2="13"></line>
                  <line x1="16" y1="17" x2="8" y2="17"></line>
                </svg>
              </span>
              <h3>ประวัติการตรวจสอบล่าสุดในโครงการนี้</h3>
              <span class="section-count-pill">{currentProjectHistory.length}</span>
            </div>
            <span class="sub-hint">คลิกเอกสารเพื่อเปิดดูรายงานผลการตรวจย้อนหลัง</span>
          </div>

          <div class="history-table-container">
            <table class="project-history-table">
              <thead>
                <tr>
                  <th>ชื่อไฟล์เอกสาร</th>
                  <th style="width: 190px;">กลุ่มการตรวจสอบ</th>
                  <th style="width: 140px;">ประเภท</th>
                  <th style="width: 150px;">วันที่ตรวจ</th>
                  <th style="width: 120px; text-align: right;">การจัดการ</th>
                </tr>
              </thead>
              <tbody>
                {#each paginatedProjectHistory as item, rIdx}
                  {@const cleanItemGroup = String(item.group_name || 'General').replace(/^\[.*?\]\s*/, '').trim() || 'General'}
                  <tr
                    class="history-table-row"
                    style="--row-idx: {rIdx};"
                    on:click={() => selectedHistory.set(item)}
                  >
                    <td class="td-filename">
                      <div class="file-name-cell">
                        <span class="file-row-icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                        </span>
                        <span class="file-row-name">{item.filename || 'Unknown Document'}</span>
                      </div>
                    </td>
                    <td>
                      <span class="group-pill">{cleanItemGroup}</span>
                    </td>
                    <td>
                      <span class="type-pill">{item.docType || item.group_type || 'General'}</span>
                    </td>
                    <td class="td-date">{formatHistoryTime(item.date)}</td>
                    <td style="text-align: right;">
                      <button type="button" class="btn-table-view" on:click|stopPropagation={() => selectedHistory.set(item)}>
                        <span>ดูรายงาน</span>
                        <span class="view-arrow" aria-hidden="true">&rarr;</span>
                      </button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          {#if historyTotalPages > 1}
            <div class="project-history-pagination">
              <span class="pagination-info">
                หน้า <strong>{historyCurrentPage}</strong> จาก <strong>{historyTotalPages}</strong> • แสดง {(historyCurrentPage - 1) * historyItemsPerPage + 1}–{Math.min(historyCurrentPage * historyItemsPerPage, currentProjectHistory.length)} จาก {currentProjectHistory.length} รายการ
              </span>
              <div class="pagination-nav">
                <button 
                  type="button"
                  class="btn-page-nav" 
                  disabled={historyCurrentPage === 1} 
                  on:click={() => goToHistoryPage(historyCurrentPage - 1)}
                  title="หน้าก่อนหน้า"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="15 18 9 12 15 6"></polyline></svg>
                  <span>ก่อนหน้า</span>
                </button>
                
                <div class="page-numbers">
                  {#each getVisibleHistoryPages(historyCurrentPage, historyTotalPages) as p}
                    {#if p === '...'}
                      <span class="page-ellipsis">...</span>
                    {:else}
                      <button 
                        type="button"
                        class="btn-page-num" 
                        class:active={historyCurrentPage === p} 
                        on:click={() => goToHistoryPage(p)}
                      >
                        {p}
                      </button>
                    {/if}
                  {/each}
                </div>

                <button 
                  type="button"
                  class="btn-page-nav" 
                  disabled={historyCurrentPage === historyTotalPages} 
                  on:click={() => goToHistoryPage(historyCurrentPage + 1)}
                  title="หน้าถัดไป"
                >
                  <span>ถัดไป</span>
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </button>
              </div>
            </div>
          {/if}
        </div>
      {/if}
    </div>

  {:else if !isProcessing && !scanResult}
    <!-- INPUT FORM -->
    <div class="top-nav upload-top-nav">
      <button type="button" class="btn-back" on:click={() => { isGroupNameSet = false; }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปเลือกกลุ่มการตรวจสอบ
      </button>

      <div class="active-context-pills">
        <span class="ctx-pill project-ctx">
          <span class="ctx-dot"></span>
          โครงการ: <strong>{resolvedProjectLabel}</strong>
        </span>
        <span class="ctx-pill group-ctx">
          กลุ่ม: <strong>[{scanGroupType}] {String(scanGroupName || '').replace(/^\[.*?\]\s*/, '').trim() || scanGroupName}</strong>
          <button type="button" class="btn-text-change" on:click={() => isGroupNameSet = false}>เปลี่ยนกลุ่ม</button>
        </span>
      </div>
    </div>

    <div class="header-text upload-header-text">
      <h2>QA Consult — ระบบตรวจสอบเอกสารอัตโนมัติ</h2>
      <p>อัปโหลดเอกสารของคุณเพื่อเปรียบเทียบกับฐานข้อมูล Knowledge Base ของโครงการ และรับรายงานผลการตรวจสอบทางอีเมล</p>
    </div>

    <div class="main-card upload-workspace-card">
      <div class="form-grid">
        <!-- LEFT: File Upload -->
        <div class="upload-section">
          <div class="pane-header">
            <span class="pane-step">1</span>
            <div>
              <h3 class="pane-title">อัปโหลดไฟล์เอกสาร</h3>
              <p class="pane-sub">รองรับเอกสารข้อกำหนด (.pdf) และตาราง Test Case (.xlsx, .xls)</p>
            </div>
          </div>

          <div
            class="drop-zone"
            class:dragging={isDragging}
            class:has-file={!!file}
            role="button"
            tabindex="0"
            aria-label="อัปโหลดไฟล์ PDF หรือ Excel"
            on:dragenter={handleDragEnter}
            on:dragleave={handleDragLeave}
            on:dragover|preventDefault
            on:drop={handleDrop}
            on:click={triggerFileInput}
            on:keydown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), triggerFileInput())}
          >
            {#if file}
              <div class="file-info" on:click|stopPropagation on:keydown|stopPropagation role="group">
                <div class="file-icon" class:excel-icon={isExcelFile(file.name)} class:markdown-icon={isMarkdownFile(file.name)}>
                  {#if isExcelFile(file.name)}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: #10b981; width: 28px; height: 28px;">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                      <polyline points="14 2 14 8 20 8"></polyline>
                      <line x1="8" y1="13" x2="16" y2="13"></line>
                      <line x1="8" y1="17" x2="16" y2="17"></line>
                      <line x1="10" y1="9" x2="8" y2="9"></line>
                    </svg>
                  {:else}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                  {/if}
                </div>
                <div class="file-details">
                  <div class="file-name" style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <span>{file.name}</span>
                    {#if isExcelFile(file.name)}
                      <span class="file-kind-badge excel">Excel Test Case</span>
                    {:else if isMarkdownFile(file.name)}
                      <span class="file-kind-badge markdown">Markdown / Text</span>
                    {:else}
                      <span class="file-kind-badge pdf">PDF Document</span>
                    {/if}
                  </div>
                  <div class="file-size">ขนาดไฟล์ {(file.size / 1024).toFixed(1)} KB • พร้อมตรวจสอบ</div>
                </div>
                <button type="button" class="btn-remove" aria-label="ลบไฟล์ที่เลือก" on:click={removeFile} title="ลบไฟล์">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            {:else}
              <div class="drop-content">
                <div class="upload-icon-orb" aria-hidden="true">
                  <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                </div>
                <p class="drop-title">ลากไฟล์ PDF, Excel หรือ Markdown มาวางที่นี่</p>
                <p class="drop-sub">หรือ <span>คลิกเพื่อเลือกไฟล์จากเครื่อง</span> สำหรับตรวจสอบกับ Knowledge Base</p>
                <div class="supported-formats" aria-hidden="true">
                  <span class="fmt-pill pdf">.PDF</span>
                  <span class="fmt-pill excel">.XLSX</span>
                  <span class="fmt-pill excel">.XLS</span>
                  <span class="fmt-pill markdown">.MD</span>
                </div>
              </div>
            {/if}
          </div>
          <input
            type="file"
            accept=".pdf, .xlsx, .xls, .xlsm, .csv, .md, .txt, application/pdf, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel, text/markdown, text/plain"
            bind:this={fileInput}
            on:change={handleFileSelect}
            style="display: none;"
          />
        </div>

        <!-- RIGHT: Settings -->
        <div class="settings-section">
          <div class="pane-header">
            <span class="pane-step">2</span>
            <div>
              <h3 class="pane-title">ตั้งค่าเงื่อนไขการตรวจสอบ &amp; ผู้รับรายงาน</h3>
              <p class="pane-sub">กำหนดมาตรฐานเอกสาร ทักษะ AI และอีเมลสำหรับรับผลการวิเคราะห์</p>
            </div>
          </div>
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
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="custom-select" on:click|stopPropagation={() => { docTypeOpen = !docTypeOpen; skillOpen = false; }}>
              <div
                class="select-trigger"
                class:open={docTypeOpen}
                role="button"
                tabindex="0"
                aria-haspopup="listbox"
                aria-expanded={docTypeOpen}
                on:keydown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    docTypeOpen = !docTypeOpen;
                    skillOpen = false;
                  } else if (e.key === 'Escape' && docTypeOpen) {
                    e.stopPropagation();
                    docTypeOpen = false;
                  }
                }}
              >
                <span class="select-trigger-label">
                  {#if selectedDocTypes.length === 0}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="color: #c4b5fd; flex-shrink: 0;" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    <span class="select-trigger-text" style="color: #c4b5fd;">
                      -- ไม่ระบุ (AI วิเคราะห์และตรวจเอกสาร MD ใน Project อัตโนมัติ) --
                    </span>
                  {:else if selectedDocTypes.length <= 2}
                    <span class="select-trigger-text" style="color: #6ee7b7; font-weight: 500;">
                      🎯 {selectedDocTypes.join(", ")}
                    </span>
                  {:else}
                    <span class="select-trigger-text" style="color: #6ee7b7; font-weight: 500;">
                      🎯 เลือกแล้ว {selectedDocTypes.length} รายการ
                    </span>
                  {/if}
                </span>
                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </div>
              {#if docTypeOpen}
                <div class="options-menu" role="listbox" aria-multiselectable="true" transition:fade={{duration: 100}}>
                  <div 
                    class="option-item" 
                    class:selected={selectedDocTypes.length === 0}
                    role="option"
                    aria-selected={selectedDocTypes.length === 0}
                    tabindex="0"
                    on:click|stopPropagation={() => { selectedDocTypes = []; docTypeOpen = false; }}
                    on:keydown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        e.stopPropagation();
                        selectedDocTypes = [];
                        docTypeOpen = false;
                      }
                    }}
                    style="color: #c4b5fd; font-style: italic; border-bottom: 1px solid rgba(255,255,255,0.08);"
                  >
                    <span style="margin-right: 8px;" aria-hidden="true">🤖</span>
                    -- ไม่ระบุ (AI Agent วิเคราะห์เนื้อหาและดึงเอกสาร MD ในโครงการอัตโนมัติ) --
                  </div>
                  {#each docTypes as type}
                    <div
                      class="option-item"
                      class:selected={selectedDocTypes.includes(type)}
                      role="option"
                      aria-selected={selectedDocTypes.includes(type)}
                      tabindex="0"
                      on:click|stopPropagation={() => toggleDocType(type)}
                      on:keydown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          e.stopPropagation();
                          toggleDocType(type);
                        }
                      }}
                    >
                      <input type="checkbox" checked={selectedDocTypes.includes(type)} tabindex="-1" aria-hidden="true" style="margin-right: 8px; cursor: pointer;" />
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
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12" style="flex-shrink: 0;" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  กำหนด Flow ชัดเจน: AI จะตรวจเจาะจงตาม Flow และมาตรฐานเอกสาร {selectedDocTypes.join(", ")} เพื่อความแม่นยำสูงสุด
                </span>
              {:else}
                <span style="color: #94a3b8; display: flex; align-items: center; gap: 4px;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12" style="flex-shrink: 0;" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                  โหมดอัตโนมัติ: AI Agent จะวิเคราะห์ประเภทเอกสาร และดึงเอกสาร MD ในโครงการมา Cross-check อัตโนมัติ
                </span>
              {/if}
            </div>
          </div>

          <div class="setting-group relative">
            <label>ทักษะ AI (AI Skill)</label>
            <!-- Custom Dropdown for Skill -->
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="custom-select" on:click|stopPropagation={() => { skillOpen = !skillOpen; docTypeOpen = false; }}>
              <div
                class="select-trigger"
                class:open={skillOpen}
                role="button"
                tabindex="0"
                aria-haspopup="listbox"
                aria-expanded={skillOpen}
                on:keydown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    skillOpen = !skillOpen;
                    docTypeOpen = false;
                  } else if (e.key === 'Escape' && skillOpen) {
                    e.stopPropagation();
                    skillOpen = false;
                  }
                }}
              >
                <span class="select-trigger-label">
                  {#if selectedSkills.length === 0}
                    <span class="select-trigger-text" style="color: #9ca3af;">-- ไม่ใช้ Skill --</span>
                  {:else if selectedSkills.length <= 2}
                    <span class="select-trigger-text">
                      {selectedSkills.map(id => skills.find(s => s.skill_id === id)?.skill_name).join(", ")}
                    </span>
                  {:else}
                    <span class="select-trigger-text">เลือกแล้ว {selectedSkills.length} ทักษะ</span>
                  {/if}
                </span>
                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </div>
              {#if skillOpen}
                <div class="options-menu" role="listbox" aria-multiselectable="true" transition:fade={{duration: 100}}>
                  {#if filteredSkills.length === 0}
                    <div class="option-item" style="color: #9ca3af; justify-content: center; cursor: default;">
                      -- ไม่มีทักษะ AI ที่เกี่ยวข้อง --
                    </div>
                  {:else}
                    {#each filteredSkills as skill}
                      <div
                        class="option-item"
                        class:selected={selectedSkills.includes(skill.skill_id)}
                        role="option"
                        aria-selected={selectedSkills.includes(skill.skill_id)}
                        tabindex="0"
                        on:click|stopPropagation={() => toggleSkill(skill.skill_id)}
                        on:keydown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            e.stopPropagation();
                            toggleSkill(skill.skill_id);
                          }
                        }}
                      >
                        <input type="checkbox" checked={selectedSkills.includes(skill.skill_id)} tabindex="-1" aria-hidden="true" style="margin-right: 8px; cursor: pointer;" />
                        {skill.skill_name}
                      </div>
                    {/each}
                  {/if}
                </div>
              {/if}
            </div>
          </div>

          <div class="setting-group">
            <label for="qa-email-input">อีเมลผู้รับผลการตรวจสอบ</label>
            <div class="email-input-container">
              <input 
                id="qa-email-input"
                type="text" 
                bind:value={emailInput} 
                placeholder="ระบุอีเมลแล้วกด Enter หรือปุ่ม +" 
                on:keydown={handleEmailKeydown}
              />
              <button type="button" class="btn-add-email" on:click={addEmail} disabled={!emailInput} title="เพิ่มอีเมล" aria-label="เพิ่มอีเมล">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              </button>
            </div>
            
            {#if emailList.length > 0}
              <div class="email-tags">
                {#each emailList as e, i}
                  <div class="email-tag">
                    {e}
                    <button type="button" class="remove-tag" aria-label="ลบอีเมล" title="ลบอีเมล" on:click={() => removeEmail(i)}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
            <span class="hint-text">รายงานการเปรียบเทียบจะถูกจัดส่งไปยังอีเมลทั้งหมดนี้</span>
          </div>

          <div class="submit-action-area">
            {#if !file}
              <div class="submit-readiness-hint">กรุณาอัปโหลดไฟล์เอกสารทางด้านซ้ายเพื่อเริ่มการตรวจสอบ</div>
            {/if}
            <button type="button" class="btn-primary btn-start-scan" on:click={processQAConsult} disabled={!file || (emailList.length === 0 && emailInput.trim() === '')}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              เริ่มตรวจสอบเอกสาร
            </button>
          </div>
        </div>
      </div>
    </div>

  {:else if isProcessing && !scanResult}
    <!-- SPECTRA QA LOADING STATE -->
    <div class="loading-state">
      <SpectraLoading 
        title="กำลังวิเคราะห์ QA Consult..." 
        subtitleChip={($activeScanStatus && $activeScanStatus.filename) || file?.name || ""}
        status={processStatus || "กำลังประมวลผลและตรวจสอบเกณฑ์ Exit Criteria..."} 
        progressPct={progressPct}
        elapsedSeconds={elapsedScanSec}
        stages={qaConsultStages}
        showCancel={true}
        cancelLabel="หยุดการสแกนเอกสาร"
        cancelling={isCancellingScan}
        on:cancel={cancelQAConsultScan}
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
      <div class="dashboard-top-bar" id="qa-top-header">
        <div class="left-content">
          <div class="header-text">
            <div class="result-title-row">
              <span class="result-title-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="20" height="20">
                  <path d="M9 12l2 2 4-4"></path>
                  <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path>
                </svg>
              </span>
              <h2>ผลการวิเคราะห์ QA & Exit Criteria Review Gate</h2>
            </div>
            <p class="result-subtitle">ตรวจสอบรายงานผลการวิเคราะห์ด้านล่าง ก่อนกดยืนยันการส่งรายงานเข้าอีเมล</p>
          </div>
          <div class="result-meta-strip">
            {#if scanResult.filename}
              <div class="meta-chip">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                <span class="lbl">ไฟล์:</span>
                <span class="val" title={scanResult.filename}>{scanResult.filename}</span>
              </div>
            {/if}
            <div class="meta-chip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                <polyline points="22,6 12,13 2,6"></polyline>
              </svg>
              <span class="lbl">ส่งผลลัพธ์ไปที่:</span>
              <span class="val">{scanResult.email || "- ไม่ระบุ -"}</span>
            </div>
            <div class="meta-chip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <rect x="3" y="4" width="18" height="16" rx="2"></rect>
                <line x1="7" y1="8" x2="17" y2="8"></line>
                <line x1="7" y1="12" x2="17" y2="12"></line>
                <line x1="7" y1="16" x2="12" y2="16"></line>
              </svg>
              <span class="lbl">{isExcelFile(scanResult.filename) ? 'จำนวนแผ่นงาน:' : 'จำนวนหน้า:'}</span>
              <span class="val">{scanResult.total_pages ? (isExcelFile(scanResult.filename) ? scanResult.total_pages + ' แผ่นงาน (Sheets)' : scanResult.total_pages + ' หน้า') : '- ไม่ทราบ -'}</span>
            </div>
            {#if scanResult.emailSent}
              <div class="meta-chip success">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span class="lbl">สถานะส่งอีเมล:</span>
                <span class="val success">ส่งสำเร็จแล้ว</span>
              </div>
            {/if}
          </div>
        </div>

        <div class="right-actions">
          {#if (scanResult.qa_findings && scanResult.qa_findings.length > 0) || (scanResult.exit_criteria_eval && scanResult.exit_criteria_eval.status !== 'PASSED')}
            <button type="button" class="btn-auto-fix-glow" on:click={sendFindingsToDocCreation} disabled={isSendingToDocCreation} title="ส่งข้อบกพร่องที่พบไปยัง QA Document Creation เพื่อปรับปรุงเอกสารให้ผ่าน และบันทึก Rule ปรับปรุง Agent">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                <path d="M12 8v4l3 3"/>
              </svg>
              {isSendingToDocCreation ? 'กำลังส่งข้อมูล...' : `ส่งแก้ไขใน QA Doc Creation (${getTotalCorrectionCount()} ข้อ)`}
            </button>
          {/if}

          {#if scanResult.exit_criteria_eval}
            <button type="button" class="btn-outline-glow" on:click={() => { gateResultData = scanResult.exit_criteria_eval; showGateModal = true; }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
              </svg>
              แสดง Modal Animation
            </button>
          {/if}

          {#if scanResult.excel_url}
            <a 
              href={scanResult.excel_url} 
              download 
              target="_blank" 
              rel="noopener noreferrer" 
              class="btn-download-excel"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              ดาวน์โหลด Excel
            </a>
          {/if}

          <button type="button" class="btn-outline-action" on:click={resetForm} disabled={isSendingEmail}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><polyline points="1 4 1 10 7 10"></polyline><polyline points="23 20 23 14 17 14"></polyline><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path></svg>
            เริ่มใหม่
          </button>

          <button type="button" class="btn-primary-action" on:click={sendEmail} disabled={isSendingEmail || scanResult.emailSent || !scanResult.email}>
            {#if isSendingEmail}
              กำลังส่ง...
            {:else if scanResult.emailSent}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><polyline points="20 6 9 17 4 12"></polyline></svg>
              ส่งแล้ว
            {:else}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
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
        <button type="button" class="btn-quick-nav highlight-btn" on:click={() => scrollToSection('qa-doc-inspector-section')}>
          โฟกัสรายหน้า & ไฮไลต์จุดผิดพลาด
          {#if scanResult.page_issue_summary?.pages_with_issues_count > 0}
            ({scanResult.page_issue_summary.pages_with_issues_count} หน้า)
          {/if}
        </button>
        {#if scanResult.qa_findings && scanResult.qa_findings.length > 0}
          <button type="button" class="btn-quick-nav" on:click={() => scrollToSection('qa-findings-section')}>
            📊 QA Audit Findings ({scanResult.qa_findings.length})
          </button>
        {:else}
          <button type="button" class="btn-quick-nav" on:click={() => scrollToSection('qa-findings-section')} style="border-color: rgba(52, 211, 153, 0.3);">
            ✅ QA Audit Findings (ผ่าน)
          </button>
        {/if}
        {#if scanResult.exit_criteria_eval}
          <button type="button" class="btn-quick-nav" on:click={() => scrollToSection('exit-criteria-section')}>
            📋 Exit Criteria Gate ({scanResult.exit_criteria_eval.score_percentage}%)
          </button>
        {/if}
        <button type="button" class="btn-quick-nav" on:click={() => scrollToSection('consult-report-section')}>
          📝 Spectra QA Consult Report (รายงานวิเคราะห์)
        </button>
      </div>

      <!-- Interactive Document Page Focus & Highlight Inspector -->
      <QADocumentInspector
        bind:this={inspectorRef}
        bind:selectedPageNumber={inspectorPageNumber}
        bind:selectedFindingIndex={inspectorFindingIndex}
        pages={scanResult.pages || []}
        findings={scanResult.qa_findings || []}
        exitCriteriaItems={scanResult.exit_criteria_eval?.items || []}
        pageIssueSummary={scanResult.page_issue_summary || null}
        filename={scanResult.filename || ""}
        isLoadingPages={isLoadingInspectorPages}
      />

      <!-- QA Findings Report Card (Always show) -->
      <div class="qa-findings-card glass-panel" id="qa-findings-section">
        <div class="gate-result-header">
          <div class="gate-header-title">
            <h3>📊 QA Audit Findings Report</h3>
            {#if scanResult.qa_findings && scanResult.qa_findings.length > 0}
              <span class="template-badge">ประเด็นที่พบจากการวิเคราะห์</span>
            {:else}
              <span class="template-badge" style="background: rgba(52, 211, 153, 0.15); color: #34d399; border-color: rgba(52, 211, 153, 0.3);">✅ ผ่านการตรวจสอบ</span>
            {/if}
          </div>
          <div class="gate-header-actions">
            {#if scanResult.qa_findings && scanResult.qa_findings.length > 0}
              <span class="gate-status-pill status-info">
                พบ {scanResult.qa_findings.length} รายการ
              </span>
              <button type="button" class="btn-mini-autofix" on:click={sendFindingsToDocCreation} disabled={isSendingToDocCreation}>
                🔄 ส่งแก้ไขใน QA Doc Creation
              </button>
            {:else}
              <span class="gate-status-pill status-passed">
                ✅ ไม่พบข้อผิดพลาด
              </span>
            {/if}
            <button type="button" class="btn-table-toggle" on:click={() => isFindingsTableExpanded = !isFindingsTableExpanded}>
              {isFindingsTableExpanded ? '🔽 ย่อตาราง' : '🔼 ขยายเต็ม'}
            </button>
          </div>
        </div>

        <div class="exit-checklist-table-wrapper" class:expanded={isFindingsTableExpanded}>
          <table class="exit-checklist-table">
            <thead>
              <tr>
                <th style="width: 56px; text-align: center;">ลำดับ</th>
                <th style="width: 118px; text-align: center;">หน้า / ตำแหน่ง</th>
                <th style="width: 150px;">ประเภทการตรวจ</th>
                <th style="width: 26%;">ประเด็นที่พบ (Issue)</th>
                <th style="width: 100px; text-align: center;">ความรุนแรง</th>
                <th style="width: 22%;">สิ่งที่ควรเป็น</th>
                <th>ข้อเสนอแนะ</th>
              </tr>
            </thead>
            <tbody>
              {#if scanResult.qa_findings && scanResult.qa_findings.length > 0}
                {#each scanResult.qa_findings as finding, i}
                  <tr class="row-status-{finding.severity === 'Critical' || finding.severity === 'High' ? 'fail' : finding.severity === 'Medium' ? 'na' : 'pass'}">
                    <td class="item-code-cell" style="text-align: center;"><strong>{i + 1}</strong></td>
                    <td style="text-align: center;">
                      <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                        <button
                          type="button"
                          class="btn-page-jump"
                          class:has-page={Boolean(finding.page_number)}
                          on:click={() => jumpToFindingInInspector(finding, i)}
                          title="คลิกเพื่อเปิดหน้าเอกสารและไฮไลต์จุดผิดพลาดนี้"
                        >
                          {finding.page_number ? (finding.page_label || `หน้า ${finding.page_number}`) : 'ภาพรวม'}
                        </button>
                        {#if finding.location && finding.location !== finding.page_label}
                          <span class="loc-sub-label" title={finding.location}>{finding.location}</span>
                        {/if}
                      </div>
                    </td>
                    <td class="category-cell">{finding.check_type || '-'}</td>
                    <td class="question-cell">
                      <strong class="issue-headline">{finding.issue || '-'}</strong>
                      {#if finding.found_incorrect && finding.found_incorrect !== '-'}
                        <div class="evidence-text" style="margin-top: 6px;">
                          <span class="evidence-lbl">ข้อความในเอกสาร:</span> {finding.found_incorrect}
                        </div>
                      {/if}
                    </td>
                    <td class="severity-cell" style="text-align: center;">
                      <span class="badge-sev badge-sev-{(finding.severity || 'info').toLowerCase()}">{finding.severity || 'Info'}</span>
                    </td>
                    <td class="remarks-cell">{finding.correct_value || '-'}</td>
                    <td class="remarks-cell">{finding.recommendation || '-'}</td>
                  </tr>
                {/each}
              {:else}
                <tr>
                  <td colspan="7" style="text-align: center; padding: 40px 20px;">
                    <div style="display: flex; flex-direction: column; align-items: center; gap: 12px;">
                      <div style="font-size: 48px; opacity: 0.9;">✅</div>
                      <div style="font-size: 16px; font-weight: 600; color: #34d399;">ไม่พบข้อผิดพลาดในเอกสาร</div>
                      <div style="font-size: 13px; color: #9ca3af; max-width: 400px;">เอกสารผ่านการตรวจสอบ QA Audit เรียบร้อย ไม่พบประเด็นข้อบกพร่องที่ต้องแก้ไข</div>
                    </div>
                  </td>
                </tr>
              {/if}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Exit Criteria Review Gate Card -->
      {#if scanResult.exit_criteria_eval}
        <div class="exit-criteria-gate-result-card glass-panel" id="exit-criteria-section">
          <div class="gate-result-header">
            <div class="gate-header-title">
              <h3>📋 ผลการประเมิน Exit Criteria Review Gate</h3>
              <span class="template-badge">{scanResult.exit_criteria_eval.template_title}</span>
            </div>
            <div class="gate-header-actions">
              <button
                type="button"
                class="btn-table-toggle"
                on:click={reevaluateExitCriteria}
                disabled={isReevaluatingExitCriteria}
                title="ประเมินเอกสารนี้เทียบกับเกณฑ์ Exit Criteria ล่าสุดใหม่อีกครั้งโดยไม่ต้องอัปโหลดไฟล์ใหม่"
              >
                {isReevaluatingExitCriteria ? '⏳ กำลังประเมินเกณฑ์ใหม่...' : '🔄 ประเมินเกณฑ์ใหม่'}
              </button>
              {#if activeTabStats.status !== 'PASSED'}
                <button type="button" class="btn-mini-autofix" on:click={sendFindingsToDocCreation} disabled={isSendingToDocCreation}>
                  🔄 ส่งแก้ไขตามเกณฑ์ Gate
                </button>
              {/if}
              <span class="gate-status-pill status-{activeTabStats.status.toLowerCase()}">
                {activeTabStats.status}
              </span>
              <button type="button" class="btn-table-toggle" on:click={() => isExitTableExpanded = !isExitTableExpanded}>
                {isExitTableExpanded ? '🔽 ย่อตาราง' : '🔼 ขยายเต็ม'}
              </button>
            </div>
          </div>

          <!-- Criteria Tabs Navigation -->
          {#if criteriaTabsList && criteriaTabsList.length > 1}
            <div class="criteria-nav-tabs">
              <button 
                type="button"
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
                  type="button"
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
                  <th style="width: 68px; text-align: center;">ข้อตรวจ</th>
                  <th style="width: 155px;">หมวดหมู่</th>
                  <th style="width: 22%;">รายการประเมิน (Checklist Item)</th>
                  <th style="width: 150px;">📊 ตัวชี้วัด (KPI Indicator)</th>
                  <th style="width: 90px; text-align: center;">ความรุนแรง</th>
                  <th style="width: 90px; text-align: center;">ผลการตรวจ</th>
                  <th style="width: 112px; text-align: center;">หน้า / ตำแหน่ง</th>
                  <th>ข้อสังเกต / ร่องรอยที่พบ</th>
                </tr>
              </thead>
              <tbody>
                {#if activeTabItems.length === 0}
                  <tr>
                    <td colspan="8" style="text-align: center; padding: 24px; color: #94a3b8;">
                      ไม่พบรายการข้อตรวจในเกณฑ์นี้
                    </td>
                  </tr>
                {:else}
                  {#each activeTabItems as item}
                    {@const itemPages = getExitItemPageNumbers(item)}
                    <tr class="row-status-{item.status.toLowerCase()}">
                      <td class="item-code-cell" style="text-align: center;"><strong>{item.item_code}</strong></td>
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
                      <td class="severity-cell" style="text-align: center;">
                        <span class="badge-sev badge-sev-{(item.severity || 'info').toLowerCase()}">{item.severity}</span>
                      </td>
                      <td class="status-cell" style="text-align: center;">
                        <span class="badge-status status-tag-{item.status.toLowerCase()}">
                          {item.status === 'PASS' ? '✅ PASS' : item.status === 'FAIL' ? '❌ FAIL' : '⚪ N/A'}
                        </span>
                      </td>
                      <td style="text-align: center;">
                        {#if itemPages.length > 0}
                          <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                            <div style="display: flex; flex-wrap: wrap; gap: 4px; justify-content: center;">
                              {#each itemPages as pn}
                                <button
                                  type="button"
                                  class="btn-page-jump has-page"
                                  on:click={() => jumpToPageInInspector(pn)}
                                  title="คลิกเพื่อเปิดดูหน้า {pn} ใน Document Inspector"
                                >
                                  หน้า {pn}
                                </button>
                              {/each}
                            </div>
                            {#if item.location && item.location !== item.page_ref}
                              <span class="loc-sub-label" title={item.location}>{item.location}</span>
                            {/if}
                          </div>
                        {:else}
                          <div style="display: flex; flex-direction: column; align-items: center; gap: 4px;">
                            <button
                              type="button"
                              class="btn-page-jump"
                              on:click={() => jumpToPageInInspector('global')}
                              title="คลิกเพื่อดูประเด็นภาพรวมทั้งเอกสาร"
                            >
                              {item.page_ref || 'ภาพรวม'}
                            </button>
                            {#if item.location && item.location !== item.page_ref}
                              <span class="loc-sub-label" title={item.location}>{item.location}</span>
                            {/if}
                          </div>
                        {/if}
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
          <div class="email-header-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
              <line x1="16" y1="13" x2="8" y2="13"></line>
              <line x1="16" y1="17" x2="8" y2="17"></line>
              <polyline points="10 9 9 9 8 9"></polyline>
            </svg>
            <h3>Spectra QA Consult Report</h3>
          </div>
          <div class="email-header-actions">
            {#if scanResult.report}
              <button
                type="button"
                class="btn-report-action"
                on:click={() => reportViewMode = reportViewMode === 'formatted' ? 'raw' : 'formatted'}
                title="สลับมุมมองรายงานแบบจัดหัวข้อ / ข้อความดิบ"
              >
                {reportViewMode === 'formatted' ? 'ดูข้อความดิบ (Raw)' : 'มุมมองอ่านง่าย'}
              </button>
              <button type="button" class="btn-report-action" on:click={copyReportText} title="คัดลอกข้อความรายงาน">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                คัดลอกรายงาน
              </button>
            {/if}
            <button type="button" class="btn-report-action" on:click={() => scrollToSection('qa-top-header')} title="เลื่อนกลับด้านบน">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="18 15 12 9 6 15"></polyline></svg>
              กลับด้านบน
            </button>
          </div>
        </div>
        <div class="email-body">
          <p>เรียนผู้ใช้งาน,</p>
          <p>ระบบ Spectra QA ได้ทำการตรวจสอบเอกสาร <b>{scanResult.filename || 'ไม่ระบุชื่อไฟล์'}</b> ประเภท <b>{scanResult.doc_type || 'ไม่ระบุประเภท'}</b> เรียบร้อยแล้ว</p>

          <!-- Structured Page-by-Page Summary Index -->
          {#if reportPageGroups.length > 0}
            <div class="report-page-index-box">
              <div class="rpi-header">
                <span class="rpi-title">สรุปหัวข้อที่พบข้อผิดพลาดแยกตามหมายเลขหน้าเอกสาร</span>
                <span class="rpi-count">{reportPageGroups.length} กลุ่มหน้า</span>
              </div>
              <div class="rpi-groups">
                {#each reportPageGroups as grp}
                  <div class="rpi-group-card">
                    <div class="rpi-group-head">
                      <button
                        type="button"
                        class="btn-page-jump"
                        class:has-page={grp.pageNum !== null}
                        on:click={() => jumpToPageInInspector(grp.pageNum)}
                        title="คลิกเพื่อเปิดดู {grp.label} ใน Document Inspector"
                      >
                        {grp.label}
                      </button>
                      <span class="rpi-group-cnt">พบ {grp.items.length} ประเด็น</span>
                    </div>
                    <ul class="rpi-item-list">
                      {#each grp.items as it}
                        <li>
                          <span class="rpi-tag" class:fail={it.kind === 'exit_fail' || it.severity === 'Critical' || it.severity === 'High'}>
                            {it.topic}
                          </span>
                          {#if it.location && it.location !== grp.label}
                            <span class="rpi-loc">({it.location})</span>
                          {/if}
                          <span class="rpi-summary">{it.summary}</span>
                        </li>
                      {/each}
                    </ul>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <hr>
          {#if scanResult.report}
            {#if reportViewMode === 'raw'}
              <pre>{scanResult.report}</pre>
            {:else}
              <div class="formatted-consult-report">
                {@html formatConsultReportHtml(scanResult.report)}
              </div>
            {/if}
          {:else}
            <div class="report-missing-error">
              ไม่พบเนื้อหารายงาน (AI ไม่ได้ส่งข้อความกลับมา หรือเกิดข้อผิดพลาดในการรับข้อมูล)<br>
              <pre style="font-size: 11px; margin-top: 10px;">{JSON.stringify(scanResult, null, 2)}</pre>
            </div>
          {/if}
          <hr>
          <p class="footer-note"><small>สร้างโดย Spectra QA Intelligent Analysis System</small></p>
        </div>
      </div>
    </div>
  {/if}
</div>

{#if showConfirmModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-backdrop" transition:fade={{duration: 200}} on:click={() => !isSendingEmail && (showConfirmModal = false)}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <div
      class="modal-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-email-modal-title"
      on:click|stopPropagation
    >
      <div class="modal-icon warning" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
      </div>
      <h3 id="confirm-email-modal-title">ยืนยันการส่งอีเมล</h3>
      <p class="modal-desc">คุณต้องการส่งรายงานผลการตรวจสอบนี้ ไปยังอีเมลต่อไปนี้ใช่หรือไม่?</p>
      <div class="modal-email-preview">
        {#each ((scanResult?.email || email) ? (scanResult?.email || email).split(',') : []).map(e => e.trim()).filter(Boolean) as itemEmail}
          <span class="modal-email-chip">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13" style="flex-shrink: 0;" aria-hidden="true"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path><polyline points="22,6 12,13 2,6"></polyline></svg>
            <span class="modal-email-text">{itemEmail}</span>
          </span>
        {/each}
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-outline" on:click={() => showConfirmModal = false} disabled={isSendingEmail}>ยกเลิก</button>
        <button type="button" class="btn-primary" on:click={executeSendEmail} disabled={isSendingEmail}>
          {#if isSendingEmail}กำลังส่ง...{:else}ยืนยันส่งอีเมล{/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showSuccessModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-backdrop" transition:fade={{duration: 200}} on:click={() => showSuccessModal = false}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <div
      class="modal-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="success-email-modal-title"
      on:click|stopPropagation
    >
      <div class="modal-icon success" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
      </div>
      <h3 id="success-email-modal-title">ส่งอีเมลสำเร็จ</h3>
      <p class="modal-desc">รายงานถูกส่งเรียบร้อยแล้ว ไปยังอีเมล:</p>
      <div class="modal-email-preview">
        {#each ((scanResult?.email || email) ? (scanResult?.email || email).split(',') : []).map(e => e.trim()).filter(Boolean) as itemEmail}
          <span class="modal-email-chip success">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13" style="flex-shrink: 0;" aria-hidden="true"><path d="M20 6L9 17l-5-5"></path></svg>
            <span class="modal-email-text">{itemEmail}</span>
          </span>
        {/each}
      </div>
      <div class="modal-actions centered">
        <button type="button" class="btn-primary" on:click={() => showSuccessModal = false}>ตกลง</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .qa-container {
    width: 100%;
    max-width: 100%;
    height: 100%;
    margin: 0;
    padding: 16px 24px 36px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    overflow-y: auto;
    scroll-behavior: smooth;
    box-sizing: border-box;
  }
  .qa-container.full-width {
    max-width: 100%;
    padding: 20px 24px 80px 24px;
  }
  .top-nav,
  .header-text,
  .group-management-section,
  .project-history-section,
  .main-card {
    max-width: 100%;
    width: 100%;
    margin-left: 0;
    margin-right: 0;
    box-sizing: border-box;
  }
  .top-nav.upload-top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 4px;
  }
  .active-context-pills {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .ctx-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    color: var(--text-muted, #94a3b8);
    background: rgba(18, 20, 28, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .ctx-pill strong {
    color: var(--text-main, #f8fafc);
    font-weight: 600;
  }
  .project-ctx {
    border-color: rgba(99, 102, 241, 0.35);
    background: rgba(99, 102, 241, 0.1);
  }
  .project-ctx strong {
    color: #c7d2fe;
  }
  .ctx-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--primary, #6366f1);
    box-shadow: 0 0 8px var(--primary, #6366f1);
  }
  .group-ctx {
    border-color: rgba(168, 85, 247, 0.35);
    background: rgba(168, 85, 247, 0.1);
  }
  .group-ctx strong {
    color: #e9d5ff;
  }
  .upload-header-text {
    text-align: left;
    margin-bottom: -8px;
  }
  .upload-header-text h2 {
    font-size: clamp(22px, 2.4vw, 28px);
    font-weight: 700;
    color: var(--text-main, #f8fafc);
    margin: 0 0 6px 0;
  }
  .upload-header-text p {
    font-size: 14.5px;
    color: var(--text-muted, #94a3b8);
    margin: 0;
  }
  .main-card {
    background: rgba(18, 20, 28, 0.58);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: var(--radius-lg, 20px);
    padding: 28px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.38);
  }
  .form-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 24px;
    align-items: stretch;
  }
  @media (max-width: 1120px) {
    .form-grid {
      grid-template-columns: 1fr;
    }
  }
  .upload-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-width: 0;
  }
  .pane-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }
  .pane-step {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(168, 85, 247, 0.25));
    border: 1px solid rgba(168, 85, 247, 0.45);
    color: #e0e7ff;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 13px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .pane-title {
    margin: 0 0 2px 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-main, #f8fafc);
  }
  .pane-sub {
    margin: 0;
    font-size: 12.5px;
    color: var(--text-muted, #94a3b8);
  }
  
  /* Upload Section */
  .drop-zone {
    flex: 1;
    border: 1.5px dashed rgba(168, 85, 247, 0.38);
    border-radius: 16px;
    min-height: 310px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.28s cubic-bezier(0.16, 1, 0.3, 1);
    background: radial-gradient(circle at 50% 35%, rgba(99, 102, 241, 0.08), rgba(10, 11, 18, 0.55) 70%);
    padding: 28px;
    position: relative;
    overflow: hidden;
  }
  .drop-zone.dragging,
  .drop-zone:hover,
  .drop-zone:focus-visible {
    border-color: var(--secondary, #a855f7);
    background: radial-gradient(circle at 50% 35%, rgba(168, 85, 247, 0.16), rgba(14, 16, 26, 0.72) 75%);
    box-shadow: 0 12px 32px -10px rgba(168, 85, 247, 0.28);
    transform: translateY(-2px);
  }
  .drop-zone.has-file {
    border-style: solid;
    border-color: rgba(99, 102, 241, 0.45);
  }
  .drop-content {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 420px;
  }
  .upload-icon-orb {
    width: 68px;
    height: 68px;
    border-radius: 20px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.18), rgba(168, 85, 247, 0.18));
    border: 1px solid rgba(168, 85, 247, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 18px;
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.22);
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.28s ease;
  }
  .drop-zone:hover .upload-icon-orb,
  .drop-zone.dragging .upload-icon-orb {
    transform: translateY(-4px) scale(1.05);
    border-color: rgba(168, 85, 247, 0.7);
  }
  .upload-icon {
    width: 30px;
    height: 30px;
    color: #c4b5fd;
    margin-bottom: 0;
    transition: color 0.22s ease;
  }
  .drop-zone:hover .upload-icon {
    color: #ffffff;
  }
  .drop-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-main, #f8fafc);
    margin: 0 0 6px 0;
  }
  .drop-sub {
    font-size: 13.5px;
    color: var(--text-muted, #94a3b8);
    margin: 0 0 18px 0;
    line-height: 1.5;
  }
  .drop-sub span {
    color: #c084fc;
    font-weight: 600;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .supported-formats {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .fmt-pill {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 4px 10px;
    border-radius: 6px;
  }
  .fmt-pill.pdf {
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.32);
    color: #fda4af;
  }
  .fmt-pill.excel {
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.32);
    color: #6ee7b7;
  }
  .fmt-pill.markdown {
    background: rgba(6, 182, 212, 0.14);
    border: 1px solid rgba(6, 182, 212, 0.35);
    color: #67e8f9;
  }
  .file-info {
    display: flex;
    align-items: center;
    gap: 16px;
    background: rgba(15, 18, 30, 0.85);
    padding: 20px 22px;
    border-radius: 14px;
    border: 1px solid rgba(168, 85, 247, 0.45);
    width: 100%;
    max-width: 520px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  }
  .file-icon {
    width: 48px;
    height: 48px;
    background: rgba(168, 85, 247, 0.16);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #c084fc;
    flex-shrink: 0;
  }
  .file-icon.excel-icon {
    background: rgba(16, 185, 129, 0.14);
    border-color: rgba(16, 185, 129, 0.35);
  }
  .file-icon.markdown-icon {
    background: rgba(6, 182, 212, 0.14);
    border-color: rgba(6, 182, 212, 0.35);
    color: #67e8f9;
  }
  .file-details {
    flex: 1;
    min-width: 0;
  }
  .file-name {
    font-weight: 600;
    font-size: 14.5px;
    color: var(--text-main, #f8fafc);
    margin-bottom: 4px;
    word-break: break-all;
  }
  .file-kind-badge {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 10.5px;
    font-weight: 700;
    border-radius: 5px;
    padding: 2px 7px;
  }
  .file-kind-badge.excel {
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.4);
  }
  .file-kind-badge.markdown {
    background: rgba(6, 182, 212, 0.16);
    color: #67e8f9;
    border: 1px solid rgba(6, 182, 212, 0.38);
  }
  .file-kind-badge.pdf {
    background: rgba(244, 63, 94, 0.18);
    color: #fda4af;
    border: 1px solid rgba(244, 63, 94, 0.4);
  }
  .file-size {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
  }
  .btn-remove {
    background: rgba(244, 63, 94, 0.1);
    border: 1px solid rgba(244, 63, 94, 0.25);
    color: #fda4af;
    cursor: pointer;
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.2s ease;
  }
  .btn-remove:hover {
    background: rgba(244, 63, 94, 0.25);
    color: #ffffff;
  }

  /* Settings Section */
  .settings-section {
    display: flex;
    flex-direction: column;
    gap: 20px;
    min-width: 0;
  }
  .setting-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
  }
  .setting-group label {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-main, #f8fafc);
  }
  
  /* Input Email */
  .email-input-container input {
    background: rgba(10, 11, 18, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: var(--text-main, #f8fafc);
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 14px;
    outline: none;
    min-width: 0;
    transition: border-color 0.22s ease, box-shadow 0.22s ease;
  }
  .email-input-container input::placeholder {
    color: var(--text-dim, #8494aa);
  }
  .email-input-container input:focus {
    border-color: var(--secondary, #a855f7);
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.25);
  }

  /* Custom Select Dropdowns */
  .relative {
    position: relative;
  }
  .custom-select {
    position: relative;
    user-select: none;
    cursor: pointer;
    min-width: 0;
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
    gap: 8px;
    min-width: 0;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.08);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .select-trigger-label {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .select-trigger-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
    flex-shrink: 0;
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
    background: rgba(15, 17, 26, 0.96); /* deep dark glass background */
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(168, 85, 247, 0.15);
    z-index: var(--z-dropdown, 500);
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
    color: var(--text-muted, #94a3b8);
  }

  .email-input-container {
    display: flex;
    gap: 8px;
    min-width: 0;
  }
  .email-input-container input {
    flex: 1;
    min-width: 0;
  }
  .btn-add-email {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.38);
    border-radius: 10px;
    color: var(--text-main, #f8fafc);
    width: 44px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-add-email:hover:not(:disabled) {
    background: var(--primary, #6366f1);
    border-color: var(--primary, #6366f1);
  }
  .btn-add-email:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .email-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 6px;
  }
  .email-tag {
    display: flex;
    align-items: center;
    gap: 4px;
    background: rgba(168, 85, 247, 0.16);
    border: 1px solid rgba(168, 85, 247, 0.4);
    padding: 3px 6px 3px 12px;
    border-radius: 16px;
    font-size: 13px;
    color: #e9d5ff;
  }
  .remove-tag {
    background: none;
    border: none;
    color: #d8b4fe;
    cursor: pointer;
    width: 24px;
    height: 24px;
    min-width: 24px;
    min-height: 24px;
    padding: 0;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: background 0.2s, color 0.2s;
  }
  .remove-tag:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }
  .submit-action-area {
    margin-top: auto;
    padding-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .submit-readiness-hint {
    font-size: 12px;
    color: #fbbf24;
    text-align: center;
  }
  .btn-primary {
    width: 100%;
    background: linear-gradient(135deg, var(--primary, #6366f1), var(--secondary, #a855f7));
    color: white;
    border: none;
    padding: 15px 20px;
    border-radius: 12px;
    font-size: 15.5px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    box-shadow: 0 8px 24px -4px rgba(99, 102, 241, 0.45);
    transition: transform 0.24s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.24s ease, opacity 0.2s ease;
  }
  .btn-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px -4px rgba(168, 85, 247, 0.55);
  }
  .btn-primary:active:not(:disabled) {
    transform: translateY(0);
  }
  .btn-primary:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted, #94a3b8);
    box-shadow: none;
  }

  /* Loading State */
  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    background: var(--glass-bg, rgba(18, 20, 28, 0.58));
    backdrop-filter: var(--glass-blur, blur(16px));
    -webkit-backdrop-filter: var(--glass-blur, blur(16px));
    border-radius: var(--radius-lg, 20px);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    box-shadow: var(--glass-shadow, 0 8px 32px 0 rgba(0, 0, 0, 0.37));
    min-height: 440px;
  }
  
  /* Result State */
  .result-state {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    justify-content: flex-start;
    gap: 18px;
    width: 100%;
    flex-shrink: 0;
    min-height: min-content;
    padding: 24px 28px 64px;
    background: rgba(18, 20, 28, 0.58);
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-sizing: border-box;
  }

  /* Result State Top Command Bar */
  .dashboard-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    flex-wrap: wrap;
    width: 100%;
    padding: 18px 22px;
    background: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    box-sizing: border-box;
    backdrop-filter: blur(12px);
  }
  .dashboard-top-bar .left-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1 1 420px;
    min-width: 0;
  }
  .dashboard-top-bar .header-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
    text-align: left;
  }
  .result-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .result-title-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.32);
    color: #34d399;
    flex-shrink: 0;
  }
  .result-state .dashboard-top-bar h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
    line-height: 1.3;
  }
  .result-state .result-subtitle {
    margin: 0;
    padding-left: 44px;
    font-size: 13px;
    color: #94a3b8;
    text-align: left;
    line-height: 1.45;
  }
  .result-meta-strip {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding-left: 44px;
  }
  .meta-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 8px;
    font-size: 12.5px;
    line-height: 1.3;
    color: #cbd5e1;
    max-width: 100%;
  }
  .meta-chip svg {
    color: #818cf8;
    flex-shrink: 0;
  }
  .meta-chip .lbl {
    color: #94a3b8;
    font-weight: 500;
    white-space: nowrap;
  }
  .meta-chip .val {
    color: #f8fafc;
    font-weight: 600;
    max-width: 260px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .meta-chip.success {
    background: rgba(16, 185, 129, 0.12);
    border-color: rgba(16, 185, 129, 0.3);
  }
  .meta-chip.success svg,
  .meta-chip .val.success {
    color: #34d399;
  }

  .dashboard-top-bar .right-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    flex-wrap: wrap;
    align-self: center;
  }

  .btn-outline-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    height: 38px;
    padding: 0 14px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #e2e8f0;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
  }
  .btn-outline-action:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.24);
    color: #ffffff;
    transform: translateY(-1px);
  }
  .btn-outline-action:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-primary-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    height: 38px;
    padding: 0 18px;
    width: auto;
    background: linear-gradient(135deg, #6366f1, #9333ea);
    border: 1px solid rgba(168, 85, 247, 0.45);
    color: #ffffff;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-primary-action:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(147, 51, 234, 0.5);
    filter: brightness(1.06);
  }
  .btn-primary-action:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: rgba(30, 41, 59, 0.7);
    border-color: rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    box-shadow: none;
  }

  .btn-outline {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: var(--text-main, #f8fafc);
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
    background: rgba(15, 23, 42, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 0;
    margin-bottom: 8px;
    text-align: left;
    max-height: 62vh;
    overflow-y: auto;
    width: 100%;
    color: #e2e8f0;
    backdrop-filter: blur(12px);
    box-sizing: border-box;
  }
  .email-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.22), rgba(124, 58, 237, 0.25));
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    color: #f8fafc;
    padding: 14px 22px;
    position: sticky;
    top: 0;
    z-index: 10;
    backdrop-filter: blur(14px);
  }
  .email-header-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #c4b5fd;
  }
  .email-header-title h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: #f8fafc;
  }
  .email-header-actions {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .email-body {
    padding: 22px 24px;
  }
  .email-body p {
    color: #cbd5e1;
    margin: 0 0 10px 0;
    font-size: 14px;
    text-align: left;
    line-height: 1.6;
  }
  .email-body b {
    color: #f8fafc;
  }
  .email-body hr {
    border: 0;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    margin: 16px 0;
  }
  .email-body pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 14px;
    line-height: 1.7;
    color: #e2e8f0;
    margin: 0;
    background: rgba(9, 11, 17, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 18px 20px;
  }
  .report-missing-error {
    color: #fca5a5;
    padding: 14px 16px;
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 10px;
  }
  .footer-note {
    margin-bottom: 0 !important;
    color: #64748b !important;
    text-align: left !important;
  }

  .report-box::-webkit-scrollbar {
    width: 8px;
  }
  .report-box::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.16);
    border-radius: 4px;
  }

  /* Modals */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.72);
    backdrop-filter: blur(4px);
    -webkit-backdrop-filter: blur(4px);
    display: flex;
    align-items: safe center;
    justify-content: center;
    overflow-y: auto;
    padding: 24px 16px;
    box-sizing: border-box;
    z-index: var(--z-modal, 10000);
  }
  .modal-card {
    background: #1e1e2d;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 28px 24px;
    width: 100%;
    max-width: 480px;
    max-height: 90vh;
    overflow-y: auto;
    margin: auto;
    text-align: center;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
    box-sizing: border-box;
    word-break: break-word;
    overflow-wrap: anywhere;
  }
  .modal-icon {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 16px;
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
    margin: 0 0 10px;
    font-size: 20px;
    font-weight: 700;
    color: white;
  }
  .modal-desc {
    color: #9ca3af;
    margin: 0 0 14px;
    font-size: 13.5px;
    line-height: 1.5;
  }
  .modal-email-preview {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    max-height: 140px;
    overflow-y: auto;
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    margin-bottom: 22px;
    scrollbar-width: thin;
    scrollbar-color: rgba(139, 92, 246, 0.5) transparent;
  }
  .modal-email-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 6px;
    max-width: 100%;
    word-break: break-all;
    overflow-wrap: anywhere;
  }
  .modal-email-chip.success {
    background: rgba(34, 197, 94, 0.15);
    border-color: rgba(34, 197, 94, 0.3);
    color: #86efac;
  }
  .modal-email-text {
    word-break: break-all;
    overflow-wrap: anywhere;
  }
  .modal-card p {
    color: #9ca3af;
    margin: 0 0 20px;
    line-height: 1.5;
    word-break: break-word;
    overflow-wrap: anywhere;
  }
  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: stretch;
    align-items: stretch;
    flex-wrap: wrap;
  }
  .modal-actions.centered {
    justify-content: center;
  }
  .modal-actions .btn-outline,
  .modal-actions .btn-primary {
    flex: 1 1 140px;
    width: auto;
    margin: 0;
    padding: 11px 20px;
    min-height: 42px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-sizing: border-box;
  }
  .modal-actions.centered .btn-primary,
  .modal-actions.centered .btn-outline {
    flex: none;
    min-width: 140px;
    width: auto;
  }

  /* Excel Download Button */
  .btn-download-excel {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    height: 38px;
    padding: 0 15px;
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
    text-decoration: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s ease;
    white-space: nowrap;
  }
  .btn-download-excel:hover {
    background: linear-gradient(135deg, #10b981, #059669);
    border-color: #34d399;
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.3);
  }

  /* Unified Card Containers: QA Findings & Exit Criteria Gate */
  .qa-findings-card,
  .exit-criteria-gate-result-card {
    background: rgba(15, 23, 42, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px 22px;
    backdrop-filter: blur(12px);
    box-sizing: border-box;
    width: 100%;
  }

  .gate-result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 14px;
    margin-bottom: 16px;
  }

  .gate-header-title {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .gate-header-title h3 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .gate-header-actions {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }

  .template-badge {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #a5b4fc;
    font-size: 0.75rem;
    font-weight: 500;
    padding: 3px 10px;
    border-radius: 999px;
  }

  .btn-outline-glow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    height: 38px;
    padding: 0 14px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.38);
    color: #c7d2fe;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
  }

  .btn-outline-glow:hover {
    background: rgba(99, 102, 241, 0.28);
    border-color: rgba(129, 140, 248, 0.6);
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  }

  .gate-status-pill {
    display: inline-flex;
    align-items: center;
    height: 30px;
    padding: 0 12px;
    border-radius: 8px;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    white-space: nowrap;
  }

  .gate-status-pill.status-info {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #c7d2fe;
  }
  .gate-status-pill.status-passed {
    background: rgba(16, 185, 129, 0.18);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
  }
  .gate-status-pill.status-conditional_passed {
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #fbbf24;
  }
  .gate-status-pill.status-rejected {
    background: rgba(239, 68, 68, 0.18);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #f87171;
  }

  .gate-summary-bar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }

  .summary-stat {
    background: rgba(30, 41, 59, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 14px 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
  }

  .summary-stat.green { background: rgba(16, 185, 129, 0.1); border-color: rgba(16, 185, 129, 0.28); }
  .summary-stat.red { background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.28); }
  .summary-stat.gray { background: rgba(148, 163, 184, 0.08); border-color: rgba(148, 163, 184, 0.22); }

  .stat-num {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 1.45rem;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.15;
  }
  .summary-stat.green .stat-num { color: #34d399; }
  .summary-stat.red .stat-num { color: #f87171; }
  .summary-stat.gray .stat-num { color: #94a3b8; }

  .stat-lbl { font-size: 0.76rem; color: #94a3b8; font-weight: 500; }

  /* Quick Navigation Bar */
  .quick-nav-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 16px;
    border-radius: 12px;
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
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-quick-nav:hover {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.4);
    color: #ffffff;
    transform: translateY(-1px);
  }
  .btn-quick-nav.highlight-btn {
    background: rgba(124, 58, 237, 0.2);
    border-color: rgba(168, 85, 247, 0.4);
    color: #ddd6fe;
    font-weight: 600;
  }
  .btn-quick-nav.highlight-btn:hover {
    background: rgba(124, 58, 237, 0.35);
    color: #ffffff;
  }

  .btn-table-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 30px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #cbd5e1;
    padding: 0 11px;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-table-toggle:hover {
    background: rgba(255, 255, 255, 0.14);
    color: #ffffff;
  }

  .btn-report-action {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 30px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #f8fafc;
    padding: 0 12px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-report-action:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);
  }

  /* Criteria Nav Tabs */
  .criteria-nav-tabs {
    display: flex;
    gap: 8px;
    margin: 0 0 16px 0;
    padding-bottom: 10px;
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
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(10, 14, 24, 0.45);
  }
  .exit-checklist-table-wrapper.expanded {
    max-height: none;
  }

  .exit-checklist-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.84rem;
    line-height: 1.55;
  }

  .exit-checklist-table th {
    background: rgba(30, 41, 59, 0.95);
    position: sticky;
    top: 0;
    z-index: 5;
    box-shadow: 0 1px 0 rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    font-weight: 600;
    font-size: 0.8rem;
    text-align: left;
    padding: 11px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    white-space: nowrap;
  }

  .exit-checklist-table td {
    padding: 13px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    color: #e2e8f0;
    vertical-align: top;
  }
  .exit-checklist-table tbody tr:last-child td {
    border-bottom: none;
  }

  .issue-headline {
    color: #f8fafc;
    font-weight: 600;
    display: block;
    line-height: 1.45;
  }
  .evidence-lbl {
    color: #f87171;
    font-weight: 600;
  }

  .row-status-fail { background: rgba(239, 68, 68, 0.05); }
  .row-status-pass { background: rgba(16, 185, 129, 0.015); }

  .badge-status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 0.73rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .status-tag-pass { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.38); }
  .status-tag-fail { background: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.38); }
  .status-tag-na { background: rgba(148, 163, 184, 0.16); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.35); }

  .badge-sev {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 600;
    white-space: nowrap;
  }
  .badge-sev-critical,
  .badge-sev-high {
    background: rgba(239, 68, 68, 0.18);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #f87171;
  }
  .badge-sev-major,
  .badge-sev-medium {
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: #fbbf24;
  }
  .badge-sev-minor,
  .badge-sev-low {
    background: rgba(59, 130, 246, 0.18);
    border: 1px solid rgba(59, 130, 246, 0.35);
    color: #60a5fa;
  }
  .badge-sev-info {
    background: rgba(148, 163, 184, 0.14);
    border: 1px solid rgba(148, 163, 184, 0.3);
    color: #cbd5e1;
  }

  .badge-metric {
    display: inline-block;
    padding: 4px 9px;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: #c7d2fe;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1.35;
  }

  .evidence-text {
    margin-top: 6px;
    font-size: 0.78rem;
    color: #fbbf24;
    line-height: 1.5;
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
  .scan-group-view {
    display: flex;
    flex-direction: column;
    gap: 16px;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
  }

  .scan-group-command-banner {
    position: relative;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    width: 100%;
    padding: 16px 22px;
    background: linear-gradient(135deg, rgba(18, 21, 34, 0.82), rgba(15, 18, 28, 0.68));
    border: 1px solid rgba(168, 85, 247, 0.24);
    border-radius: 16px;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.45);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-sizing: border-box;
    overflow: hidden;
    animation: scanBannerIn 0.38s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .scan-group-command-banner::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(168, 85, 247, 0.65), rgba(99, 102, 241, 0.65), transparent);
    pointer-events: none;
  }

  .banner-left {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    flex: 1 1 320px;
    min-width: 0;
  }

  .btn-back-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    padding: 4px 11px;
    border-radius: 999px;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-back-pill svg {
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-back-pill:hover {
    color: #f8fafc;
    background: rgba(168, 85, 247, 0.14);
    border-color: rgba(168, 85, 247, 0.38);
  }
  .btn-back-pill:hover svg {
    transform: translateX(-3px);
  }

  .banner-titles h2 {
    margin: 0 0 2px 0;
    font-size: clamp(19px, 1.8vw, 23px);
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
    line-height: 1.25;
  }
  .banner-titles p {
    margin: 0;
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.4;
  }

  .banner-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 7px;
    flex: 0 1 auto;
    min-width: 0;
    max-width: 100%;
  }
  @media (max-width: 820px) {
    .banner-right {
      align-items: flex-start;
      width: 100%;
    }
  }

  .active-project-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 14px;
    border-radius: 10px;
    background: rgba(147, 51, 234, 0.12);
    border: 1px solid rgba(168, 85, 247, 0.35);
    font-size: 13px;
    color: #cbd5e1;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
    min-width: 0;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    box-sizing: border-box;
  }
  .active-project-pill .proj-lbl {
    color: #94a3b8;
    font-weight: 500;
    flex-shrink: 0;
    white-space: nowrap;
  }
  .active-project-pill strong {
    color: #e9d5ff;
    font-weight: 700;
    letter-spacing: 0.01em;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .proj-live-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #a855f7;
    box-shadow: 0 0 10px #a855f7;
    animation: liveDotPulse 2.2s ease-in-out infinite;
    flex-shrink: 0;
  }

  .project-quick-stats {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #94a3b8;
    padding: 0 4px;
  }
  .project-quick-stats strong {
    font-family: var(--font-en, 'Outfit', sans-serif);
    color: #e2e8f0;
    font-weight: 700;
  }
  .project-quick-stats .q-divider {
    color: rgba(148, 163, 184, 0.45);
  }

  .group-management-section {
    max-width: 100%;
    margin: 0;
    width: 100%;
    animation: scanBannerIn 0.42s cubic-bezier(0.16, 1, 0.3, 1) 0.04s both;
  }
  .section-title-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 10px;
    padding: 0 2px;
  }
  .title-with-badge {
    display: flex;
    align-items: center;
    gap: 9px;
    color: #c084fc;
  }
  .section-icon-badge {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.3);
    color: #c084fc;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .section-icon-badge.history-icon {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.3);
    color: #818cf8;
  }
  .title-with-badge h3 {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    color: #f1f5f9;
  }
  .section-count-pill {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 11.5px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(168, 85, 247, 0.18);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #e9d5ff;
  }
  .sub-hint {
    font-size: 12px;
    color: #94a3b8;
  }
  .btn-create-group-trigger {
    position: relative;
    overflow: hidden;
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: linear-gradient(135deg, rgba(147, 51, 234, 0.28), rgba(99, 102, 241, 0.28));
    border: 1px solid rgba(168, 85, 247, 0.5);
    color: #f8fafc;
    padding: 7px 15px;
    font-size: 13px;
    font-weight: 600;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    box-shadow: 0 4px 12px rgba(147, 51, 234, 0.18);
  }
  .btn-create-group-trigger .plus-icon {
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-create-group-trigger:hover {
    background: linear-gradient(135deg, #9333ea, #6366f1);
    border-color: #d8b4fe;
    color: #ffffff;
    box-shadow: 0 6px 18px rgba(168, 85, 247, 0.38);
    transform: translateY(-1px);
  }
  .btn-create-group-trigger:hover .plus-icon {
    transform: rotate(90deg);
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
    padding: 32px 24px;
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
    width: 100%;
    max-width: 540px;
    margin: auto;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8), 0 0 30px rgba(147, 51, 234, 0.2);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    overflow: visible;
    animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    box-sizing: border-box;
  }
  @keyframes modalPop {
    from { opacity: 0; transform: scale(0.95) translateY(10px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
  }
  .modal-dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 20px 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px 18px 0 0;
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
    border-radius: 0 0 18px 18px;
    background: rgba(15, 23, 42, 0.8);
    display: flex;
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }
  .btn-dialog-cancel {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 10px 18px;
    min-height: 40px;
    font-size: 13.5px;
    font-weight: 600;
    border-radius: 10px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    white-space: nowrap;
    transition: all 0.2s;
  }
  .btn-dialog-cancel:hover {
    background: rgba(255, 255, 255, 0.12);
    color: white;
  }
  .modal-dialog-footer .btn-dialog-submit {
    width: auto;
    margin: 0;
    padding: 10px 20px;
    min-height: 40px;
    font-size: 13.5px;
    font-weight: 600;
    border-radius: 10px;
    flex-shrink: 0;
    white-space: nowrap;
  }

  /* Delete Group Confirmation Modal */
  .modal-delete-dialog {
    background: rgba(15, 23, 42, 0.96);
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 18px;
    width: 100%;
    max-width: 440px;
    max-height: 90vh;
    overflow-y: auto;
    margin: auto;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 35px rgba(239, 68, 68, 0.15);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    text-align: center;
    padding: 28px 24px;
    animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    box-sizing: border-box;
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

  /* Full-Width Auto-Fit Group Cards Grid */
  .existing-groups-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 14px;
    width: 100%;
  }

  .group-card-item {
    position: relative;
    overflow: hidden;
    background: linear-gradient(160deg, rgba(22, 25, 38, 0.78), rgba(14, 17, 26, 0.68));
    border: 1px solid rgba(139, 92, 246, 0.26);
    border-radius: 14px;
    padding: 15px 18px;
    cursor: pointer;
    transition: transform 0.26s cubic-bezier(0.16, 1, 0.3, 1),
                border-color 0.26s cubic-bezier(0.16, 1, 0.3, 1),
                box-shadow 0.26s cubic-bezier(0.16, 1, 0.3, 1),
                background 0.26s ease;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 14px;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    animation: scanCardPopIn 0.42s cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--card-idx, 0) * 65ms);
  }
  .group-card-item::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, #6366f1, #a855f7, #ec4899);
    opacity: 0.35;
    transform: scaleX(0.35);
    transform-origin: left center;
    transition: transform 0.32s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.32s ease;
  }
  .group-card-item[data-gtype="testcase"]::before {
    background: linear-gradient(90deg, #3b82f6, #6366f1, #a855f7);
  }
  .group-card-item[data-gtype="plan"]::before {
    background: linear-gradient(90deg, #10b981, #3b82f6, #6366f1);
  }
  .group-card-hitarea {
    position: absolute;
    inset: 0;
    z-index: 1;
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    border-radius: inherit;
    cursor: pointer;
    padding: 0;
  }
  .group-card-hitarea:focus-visible {
    outline: 2px solid var(--primary, #6366f1);
    outline-offset: -2px;
  }
  .group-card-item:hover,
  .group-card-item:focus-within {
    background: linear-gradient(160deg, rgba(28, 32, 50, 0.92), rgba(18, 22, 36, 0.85));
    border-color: rgba(168, 85, 247, 0.62);
    transform: translateY(-4px);
    box-shadow: 0 14px 30px -10px rgba(147, 51, 234, 0.32), 0 0 0 2px rgba(99, 102, 241, 0.45);
  }
  .group-card-item:hover::before,
  .group-card-item:focus-within::before {
    opacity: 1;
    transform: scaleX(1);
  }

  .group-card-top {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }
  .group-icon-wrap {
    color: #c084fc;
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.3);
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: transform 0.26s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.26s ease, border-color 0.26s ease, box-shadow 0.26s ease;
  }
  .group-card-item[data-gtype="testcase"] .group-icon-wrap {
    color: #93c5fd;
    background: rgba(59, 130, 246, 0.14);
    border-color: rgba(59, 130, 246, 0.3);
  }
  .group-card-item[data-gtype="plan"] .group-icon-wrap {
    color: #6ee7b7;
    background: rgba(16, 185, 129, 0.13);
    border-color: rgba(16, 185, 129, 0.28);
  }
  .group-card-item:hover .group-icon-wrap {
    transform: scale(1.07) rotate(-3deg);
    box-shadow: 0 6px 16px rgba(168, 85, 247, 0.25);
  }
  .group-title-info {
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }
  .group-type-tag {
    display: inline-block;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 10.5px;
    color: #d8b4fe;
    background: rgba(168, 85, 247, 0.16);
    border: 1px solid rgba(168, 85, 247, 0.32);
    padding: 1px 8px;
    border-radius: 6px;
    font-weight: 700;
    margin-bottom: 4px;
    letter-spacing: 0.03em;
  }
  .group-card-item[data-gtype="testcase"] .group-type-tag {
    color: #bfdbfe;
    background: rgba(59, 130, 246, 0.16);
    border-color: rgba(59, 130, 246, 0.34);
  }
  .group-card-item[data-gtype="plan"] .group-type-tag {
    color: #a7f3d0;
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.32);
  }
  .group-name-text {
    font-size: 15.5px;
    font-weight: 700;
    color: #f8fafc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .btn-card-delete {
    position: relative;
    z-index: 2;
    background: none;
    border: none;
    color: #ef4444;
    opacity: 0.55;
    cursor: pointer;
    padding: 5px;
    border-radius: 6px;
    flex-shrink: 0;
    transition: all 0.2s ease;
  }
  .btn-card-delete:hover {
    opacity: 1;
    background: rgba(239, 68, 68, 0.16);
    transform: scale(1.08);
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
    font-size: 11.5px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .stat-badge.count-active {
    color: #34d399;
  }
  .active-stat-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.8);
    animation: liveDotPulse 2s ease-in-out infinite;
  }
  .stat-badge.count-empty {
    color: #f59e0b;
  }
  .stat-date {
    font-size: 10.5px;
    color: #64748b;
  }
  .btn-select-group {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(147, 51, 234, 0.18);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #e9d5ff;
    padding: 6px 13px;
    font-size: 12px;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-select-group .btn-arrow {
    display: inline-block;
    transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .group-card-item:hover .btn-select-group,
  .btn-select-group:hover {
    background: linear-gradient(135deg, #9333ea, #6366f1);
    border-color: #c084fc;
    color: #ffffff;
    box-shadow: 0 4px 12px rgba(147, 51, 234, 0.35);
  }
  .group-card-item:hover .btn-select-group .btn-arrow,
  .btn-select-group:hover .btn-arrow {
    transform: translateX(3px);
  }

  /* Recent Project History Section */
  .project-history-section {
    max-width: 100%;
    margin: 0;
    width: 100%;
    animation: scanBannerIn 0.45s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both;
  }
  .history-table-container {
    background: rgba(15, 23, 42, 0.58);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 14px;
    overflow-x: auto;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 26px -8px rgba(0, 0, 0, 0.4);
  }
  .project-history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    text-align: left;
  }
  .project-history-table th {
    background: rgba(30, 41, 59, 0.85);
    color: #94a3b8;
    font-weight: 600;
    padding: 9px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 12px;
    white-space: nowrap;
  }
  .project-history-table td {
    padding: 9px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.045);
    color: #e2e8f0;
    vertical-align: middle;
  }
  .project-history-table tbody tr:last-child td {
    border-bottom: none;
  }
  .history-table-row {
    cursor: pointer;
    transition: background-color 0.18s ease;
    animation: historyRowSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--row-idx, 0) * 35ms + 80ms);
  }
  .history-table-row:hover {
    background: rgba(147, 51, 234, 0.1);
  }
  .file-name-cell {
    display: flex;
    align-items: center;
    gap: 9px;
    font-weight: 500;
    color: #60a5fa;
  }
  .file-row-icon {
    width: 26px;
    height: 26px;
    border-radius: 7px;
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid rgba(59, 130, 246, 0.25);
    color: #60a5fa;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.2s ease, color 0.2s ease;
  }
  .history-table-row:hover .file-row-icon {
    transform: translateX(2px) scale(1.05);
    background: rgba(99, 102, 241, 0.22);
    color: #93c5fd;
  }
  .file-row-name {
    transition: color 0.18s ease;
  }
  .history-table-row:hover .file-row-name {
    color: #93c5fd;
  }
  .group-pill {
    display: inline-block;
    background: rgba(168, 85, 247, 0.15);
    border: 1px solid rgba(168, 85, 247, 0.3);
    color: #d8b4fe;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
  }
  .type-pill {
    display: inline-block;
    background: rgba(59, 130, 246, 0.14);
    border: 1px solid rgba(59, 130, 246, 0.28);
    color: #93c5fd;
    padding: 2px 9px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
  }
  .td-date {
    color: #94a3b8;
    font-size: 12px;
    white-space: nowrap;
  }
  .btn-table-view {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(59, 130, 246, 0.14);
    border: 1px solid rgba(59, 130, 246, 0.32);
    color: #93c5fd;
    padding: 4px 11px;
    font-size: 11.5px;
    font-weight: 600;
    border-radius: 7px;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-table-view .view-arrow {
    display: inline-block;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .history-table-row:hover .btn-table-view,
  .btn-table-view:hover {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    border-color: #93c5fd;
    color: #ffffff;
    box-shadow: 0 3px 10px rgba(59, 130, 246, 0.3);
  }
  .history-table-row:hover .btn-table-view .view-arrow,
  .btn-table-view:hover .view-arrow {
    transform: translateX(2px);
  }

  /* Recent Project History Pagination */
  .project-history-pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 10px;
    padding: 8px 14px;
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 11px;
  }
  .pagination-info {
    font-size: 12.5px;
    color: #94a3b8;
  }
  .pagination-info strong {
    color: #e2e8f0;
    font-weight: 600;
  }
  .pagination-nav {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .btn-page-nav {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 5px 11px;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-page-nav:hover:not(:disabled) {
    background: rgba(147, 51, 234, 0.25);
    border-color: rgba(168, 85, 247, 0.5);
    color: #e9d5ff;
    transform: translateY(-1px);
  }
  .btn-page-nav:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
  }
  .page-numbers {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .btn-page-num {
    min-width: 30px;
    height: 30px;
    padding: 0 6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-page-num:hover:not(.active) {
    background: rgba(147, 51, 234, 0.2);
    border-color: rgba(168, 85, 247, 0.4);
    color: #ffffff;
  }
  .btn-page-num.active {
    background: linear-gradient(135deg, #7c3aed, #9333ea);
    border-color: #a855f7;
    color: #ffffff;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(147, 51, 234, 0.35);
  }
  .page-ellipsis {
    color: #64748b;
    font-size: 13px;
    padding: 0 4px;
  }

  @keyframes scanBannerIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  @keyframes scanCardPopIn {
    from {
      opacity: 0;
      transform: translateY(14px) scale(0.98);
    }
    to {
      opacity: 1;
      transform: translateY(0) scale(1);
    }
  }
  @keyframes historyRowSlideIn {
    from {
      opacity: 0;
      transform: translateX(-8px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  @keyframes liveDotPulse {
    0%, 100% {
      transform: scale(1);
      opacity: 1;
    }
    50% {
      transform: scale(1.25);
      opacity: 0.65;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .scan-group-command-banner,
    .group-management-section,
    .group-card-item,
    .project-history-section,
    .history-table-row,
    .proj-live-dot,
    .active-stat-dot {
      animation: none !important;
    }
  }

  .btn-auto-fix-glow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    height: 38px;
    padding: 0 15px;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.22), rgba(236, 72, 153, 0.22));
    border: 1px solid rgba(245, 158, 11, 0.48);
    color: #fde68a;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(245, 158, 11, 0.16);
    transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-auto-fix-glow:hover:not(:disabled) {
    background: linear-gradient(135deg, #f59e0b, #ec4899);
    border-color: rgba(253, 224, 71, 0.7);
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(245, 158, 11, 0.32);
  }
  .btn-auto-fix-glow:active:not(:disabled) {
    transform: translateY(0);
  }
  .btn-auto-fix-glow:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .btn-mini-autofix {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    height: 30px;
    padding: 0 11px;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.16), rgba(236, 72, 153, 0.18));
    border: 1px solid rgba(245, 158, 11, 0.42);
    color: #fde68a;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 8px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s ease;
  }
  .btn-mini-autofix:hover:not(:disabled) {
    background: linear-gradient(135deg, #f59e0b, #ec4899);
    color: #ffffff;
    border-color: transparent;
    transform: translateY(-1px);
    box-shadow: 0 3px 10px rgba(245, 158, 11, 0.3);
  }

  @media (max-width: 720px) {
    .gate-summary-bar {
      grid-template-columns: repeat(2, 1fr);
    }
    .result-state .result-subtitle,
    .result-meta-strip {
      padding-left: 0;
    }
  }
  .btn-page-jump {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 5px 10px;
    min-height: 28px;
    border-radius: 8px;
    font-size: 11.5px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.05);
    color: #cbd5e1;
    white-space: nowrap;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.15s ease;
  }
  .btn-page-jump.has-page {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(129, 140, 248, 0.45);
    color: #e0e7ff;
  }
  .btn-page-jump:hover {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.42), rgba(168, 85, 247, 0.36));
    border-color: #a5b4fc;
    color: #ffffff;
    transform: translateY(-1px);
  }
  .loc-sub-label {
    font-size: 10.8px;
    color: #a5b4fc;
    line-height: 1.3;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  /* Structured Page-by-Page Summary Index inside Consult Report */
  .report-page-index-box {
    margin: 16px 0 18px;
    padding: 16px 18px;
    border-radius: 14px;
    background: rgba(11, 13, 21, 0.72);
    border: 1px solid rgba(129, 140, 248, 0.28);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .rpi-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .rpi-title {
    font-size: 14px;
    font-weight: 700;
    color: #e0e7ff;
  }
  .rpi-count {
    font-size: 11.5px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.2);
    color: #c7d2fe;
    border: 1px solid rgba(129, 140, 248, 0.35);
  }
  .rpi-groups {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 12px;
  }
  .rpi-group-card {
    background: rgba(18, 21, 33, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .rpi-group-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .rpi-group-cnt {
    font-size: 11.5px;
    color: #94a3b8;
    font-weight: 600;
  }
  .rpi-item-list {
    margin: 0;
    padding-left: 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 12.5px;
    line-height: 1.5;
    color: #cbd5e1;
  }
  .rpi-tag {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 6px;
    margin-right: 5px;
    background: rgba(99, 102, 241, 0.2);
    color: #c7d2fe;
  }
  .rpi-tag.fail {
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
  }
  .rpi-loc {
    color: #a5b4fc;
    font-size: 11.5px;
    margin-right: 5px;
  }
  .rpi-summary {
    color: #e2e8f0;
  }

  /* Formatted Consult Report Body */
  .formatted-consult-report {
    font-size: 13.5px;
    line-height: 1.75;
    color: #e2e8f0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .formatted-consult-report :global(.rpt-heading) {
    font-weight: 700;
    color: #f8fafc;
    margin-top: 14px;
    padding-bottom: 5px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .formatted-consult-report :global(.rpt-h1) { font-size: 16px; color: #e0e7ff; }
  .formatted-consult-report :global(.rpt-h2) { font-size: 14.5px; color: #c7d2fe; }
  .formatted-consult-report :global(.rpt-h3) { font-size: 13.5px; color: #f8fafc; }
  .formatted-consult-report :global(.rpt-para) { margin: 2px 0; color: #cbd5e1; }
  .formatted-consult-report :global(.rpt-list) {
    margin: 4px 0 8px;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .formatted-consult-report :global(.rpt-list li) { color: #e2e8f0; }
  .formatted-consult-report :global(.rpt-page-badge) {
    display: inline-block;
    padding: 1px 8px;
    margin: 0 2px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 700;
    background: rgba(99, 102, 241, 0.24);
    border: 1px solid rgba(129, 140, 248, 0.45);
    color: #e0e7ff;
  }
  .formatted-consult-report :global(.rpt-divider) {
    border: none;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    margin: 12px 0;
  }
  .formatted-consult-report :global(code) {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 1px 6px;
    border-radius: 5px;
    font-size: 12px;
    color: #fcd34d;
  }
</style>
