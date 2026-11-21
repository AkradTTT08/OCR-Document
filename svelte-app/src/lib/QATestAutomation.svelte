<script>
  import { onMount, createEventDispatcher } from 'svelte';
  import { slide } from 'svelte/transition';
  import { toast } from './toastStore.js';
  import { selectedProjectStore, qaRefinementFeedback } from './qaHistoryStore.js';
  import ProjectSelection from './ProjectSelection.svelte';

  const dispatch = createEventDispatcher();

  let projects = [];
  let requirements = [];
  let projectDocuments = [];
  let isLoading = false;
  let isSyncingReqs = false;
  let reqSearchText = '';
  let expandedReqId = null;

  // Cross-Agent Ecosystem & MCP State
  let ecosystemStatus = null;
  let showMcpDrawer = false;
  let mcpBrowserType = 'chromium';
  let mcpTransportMode = 'builtin_playwright_mcp';

  // Phase 1.5: Requirement Automation Strategy & ROI Planner
  let strategyData = null;
  let isAnalyzingStrategy = false;
  let strategyCustomFocus = '';
  let strategyFilter = 'ALL'; // 'ALL' | 'MUST_AUTOMATE' | 'SELECTIVE' | 'MANUAL_ONLY'

  // Phase 2: Dual-Source Input (System Test Cases + Playwright MCP Live Web Play)
  let inputSourceMode = 'hybrid'; // 'testcase' | 'web_play' | 'hybrid'
  let projectTestCases = [];
  let isLoadingTestCases = false;
  let tcSearchText = '';
  let tcTypeFilter = 'ALL';
  let showAddTcModal = false;
  let newTcForm = {
    tc_id: 'TC-CUSTOM-01',
    req_code: 'REQ-001',
    module: 'Core Flow',
    title: '',
    type: 'Positive',
    priority: 'P0',
    test_steps_text: '1. เปิดหน้าเว็บเป้าหมาย\n2. กรอกข้อมูลและกดปุ่มยืนยัน\n3. ตรวจสอบผลลัพธ์ทางธุรกิจ',
    test_data: 'Valid Input',
    expected_result: '',
    business_rule: ''
  };

  // Phase 2B: Playwright MCP Live Web Play state
  let exploreUrl = '';
  let exploreUsername = '';
  let explorePassword = '';
  let playInstructions = '';
  let isExploring = false;
  let exploreResult = null;
  let exploreError = null;

  // Phase 3: Alignment state
  let isAligning = false;
  let alignResult = null;
  let alignError = null;

  // Phase 4: Script Generation state
  let generationMode = 'hybrid'; // 'testcase' | 'web_play' | 'hybrid'
  let isGenerating = false;
  let generateResult = null;
  let generateError = null;
  let selectedTestSuite = null;
  let isSavingCode = false;

  // Phase 5: Execution, Self-Healing & Business/Flow Accuracy Evaluation state
  let activePhase = 1; // 1 | 2 | 3 | 4 | 5 | 'all'
  let isRunningTest = false;
  let runTestSuccess = null;
  let runTestOutput = null;
  let runTestError = null;

  let isHealing = false;
  let healResult = null;
  let healError = null;

  let isEvaluatingAccuracy = false;
  let accuracyReport = null;

  let flowAnalysisData = null;
  let lastLoadedPid = null;

  onMount(async () => {
    try {
      const res = await fetch('/api/projects');
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
      }
    } catch (e) {
      console.error('Failed to load projects', e);
    }
  });

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  $: if ($selectedProjectStore) {
    const pid = $selectedProjectStore.id || $selectedProjectStore.project_id;
    if (pid && pid !== lastLoadedPid) {
      lastLoadedPid = pid;
      // Reset transient workflow state so previous project results never bleed across projects
      exploreResult = null;
      exploreError = null;
      alignResult = null;
      alignError = null;
      generateResult = null;
      generateError = null;
      selectedTestSuite = null;
      runTestSuccess = null;
      runTestOutput = null;
      runTestError = null;
      healResult = null;
      healError = null;
      accuracyReport = null;
      expandedReqId = null;
      selectedDocFilter = 'ALL';
      exploreUrl = $selectedProjectStore?.default_base_url || '';
      loadProjectWorkspace(pid);
    }
  }

  function handleActivateKeydown(event, callback) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      callback();
    }
  }

  async function loadProjectWorkspace(pid) {
    if (!exploreUrl && $selectedProjectStore?.default_base_url) {
      exploreUrl = $selectedProjectStore.default_base_url;
    }
    await Promise.all([
      loadRequirements(pid),
      loadProjectDocuments(pid),
      loadFlowAnalysis(pid),
      loadEcosystemStatus(pid),
      loadSavedStrategy(pid),
      loadProjectTestCases(pid, false)
    ]);
  }

  async function loadEcosystemStatus(projectId) {
    try {
      const res = await fetch(`/api/agent/ecosystem-status?project_id=${projectId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success) ecosystemStatus = data.ecosystem;
      }
    } catch (e) {
      console.warn('Ecosystem status error', e);
    }
  }

  async function loadSavedStrategy(projectId) {
    try {
      const res = await fetch(`/api/agent/automation-strategy?project_id=${projectId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.strategy) {
          strategyData = data.strategy;
        } else {
          strategyData = null;
        }
      }
    } catch (e) {
      console.warn('Saved strategy load skipped', e);
    }
  }

  async function runAutomationStrategyAnalysis() {
    const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
    if (!pid) return;
    isAnalyzingStrategy = true;
    try {
      toast('กำลังวิเคราะห์ Requirement ทั้งโครงการเพื่อวางแผน Automate Test และประเมินข้อดี-ข้อเสีย...', 'info');
      const res = await fetch('/api/agent/automation-strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pid,
          custom_focus: strategyCustomFocus
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        strategyData = data.strategy;
        toast('วิเคราะห์แผนกลยุทธ์ Automate Test และประเมิน ROI สำเร็จ', 'success');
        loadEcosystemStatus(pid);
      } else {
        toast(`เกิดข้อผิดพลาด: ${data.error || 'ไม่สามารถวิเคราะห์แผนได้'}`, 'error');
      }
    } catch (e) {
      console.error(e);
      toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์เพื่อวิเคราะห์กลยุทธ์ได้', 'error');
    } finally {
      isAnalyzingStrategy = false;
    }
  }

  async function loadProjectTestCases(projectId, forceRefresh = false) {
    isLoadingTestCases = true;
    try {
      const res = await fetch(`/api/agent/project-testcases?project_id=${projectId}&force_refresh=${forceRefresh}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success) {
          projectTestCases = data.test_cases || [];
          if (forceRefresh) {
            toast(`ดึงและสกัด Test Case จากระบบสำเร็จ ${projectTestCases.length} รายการ`, 'success');
            loadEcosystemStatus(projectId);
          }
        }
      }
    } catch (e) {
      console.warn('Failed to load project test cases', e);
    } finally {
      isLoadingTestCases = false;
    }
  }

  function addCustomTestCase() {
    if (!newTcForm.title.trim()) {
      toast('กรุณาระบุชื่อกรณีทดสอบ (Test Case Title)', 'warning');
      return;
    }
    const stepsArr = newTcForm.test_steps_text
      .split('\n')
      .map(s => s.trim())
      .filter(Boolean);
    const created = {
      id: `custom-${Date.now()}`,
      tc_id: newTcForm.tc_id || `TC-${projectTestCases.length + 1}`,
      req_code: newTcForm.req_code || 'REQ-001',
      module: newTcForm.module || 'Custom Module',
      title: newTcForm.title,
      type: newTcForm.type,
      priority: newTcForm.priority,
      source_doc: 'Manual / Custom Input',
      preconditions: 'ผู้ใช้งานพร้อมทดสอบบนหน้าเว็บ',
      test_steps: stepsArr,
      test_data: newTcForm.test_data || '-',
      expected_result: newTcForm.expected_result || 'ระบบทำงานถูกต้องตามข้อกำหนด',
      business_rule: newTcForm.business_rule || newTcForm.expected_result || 'ตรงตามเกณฑ์ธุรกิจลูกค้า',
      automatable: true,
      selected: true
    };
    projectTestCases = [created, ...projectTestCases];
    showAddTcModal = false;
    newTcForm.title = '';
    newTcForm.expected_result = '';
    newTcForm.business_rule = '';
    toast(`เพิ่ม Test Case ${created.tc_id} เข้าสู่รายการสร้างสคริปต์แล้ว`, 'success');
  }

  async function loadFlowAnalysis(projectId) {
    flowAnalysisData = null;
    try {
      const res = await fetch(`/api/agent/flow_analysis?project_id=${projectId}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.analysis) {
          flowAnalysisData = data.analysis;
        }
      }
    } catch (e) {
      console.warn('Flow analysis not available for project', e);
    }
  }

  async function loadRequirements(projectId) {
    isLoading = true;
    try {
      const res = await fetch(`/api/requirements?project_id=${projectId}`);
      if (res.ok) {
        const data = await res.json();
        requirements = data.requirements || [];
      }
    } catch (e) {
      console.error('Failed to load requirements', e);
    } finally {
      isLoading = false;
    }
  }

  async function loadProjectDocuments(projectId) {
    try {
      const res = await fetch(`/api/kb/documents?project_id=${projectId}`);
      if (res.ok) {
        const data = await res.json();
        projectDocuments = data.documents || [];
      }
    } catch (e) {
      console.error('Failed to load project documents', e);
    }
  }

  async function syncRequirementsFromProject() {
    const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
    if (!pid) return;

    isSyncingReqs = true;
    try {
      toast('กำลังสกัดและซิงค์ Requirement จากเอกสารในโครงการ...', 'info');
      const res = await fetch('/api/requirements/sync-from-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: pid })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        requirements = data.requirements || [];
        toast(`สกัด Requirement สำเร็จแล้ว ${requirements.length} รายการ`, 'success');
        loadEcosystemStatus(pid);
      } else {
        toast(`เกิดข้อผิดพลาด: ${data.error || 'ไม่สามารถสกัดข้อมูลได้'}`, 'error');
      }
    } catch (err) {
      console.error(err);
      toast('ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์', 'error');
    } finally {
      isSyncingReqs = false;
    }
  }

  let selectedDocFilter = 'ALL';
  let viewMode = 'grouped';

  function getReqDocInfo(req) {
    if (req.doc_name && req.doc_name !== 'ไม่ระบุเอกสาร') {
      return {
        name: req.doc_name,
        category: req.doc_category || req.doc_type || 'Requirements',
        docId: req.doc_id
      };
    }
    const matched = (projectDocuments || []).find(
      d => String(d.id || d.doc_id) === String(req.doc_id)
    );
    if (matched) {
      return {
        name: matched.original_filename || matched.name || matched.filename || 'เอกสารโครงการ',
        category: matched.doc_category || matched.doc_type || 'Requirements',
        docId: matched.id || matched.doc_id
      };
    }
    return {
      name: 'ไม่ระบุเอกสาร',
      category: 'General',
      docId: null
    };
  }

  function getDocReqCount(doc) {
    const docId = String(doc.id || doc.doc_id || '');
    const docName = (doc.original_filename || doc.name || doc.filename || '').trim();
    return requirements.filter(r => {
      if (docId && String(r.doc_id || '') === docId) return true;
      if (docName && r.doc_name && r.doc_name === docName) return true;
      return false;
    }).length;
  }

  function toggleDocFilter(doc) {
    const docKey = String(doc.id || doc.doc_id || doc.original_filename || doc.name);
    selectedDocFilter = selectedDocFilter === docKey ? 'ALL' : docKey;
  }

  $: filteredRequirements = requirements.filter(req => {
    if (selectedDocFilter !== 'ALL') {
      const docInfo = getReqDocInfo(req);
      const matchId = req.doc_id && String(req.doc_id) === String(selectedDocFilter);
      const matchName = docInfo.name === selectedDocFilter;
      if (!matchId && !matchName) return false;
    }
    if (!reqSearchText.trim()) return true;
    const q = reqSearchText.toLowerCase();
    const docInfo = getReqDocInfo(req);
    return (
      (req.req_code && req.req_code.toLowerCase().includes(q)) ||
      (req.title && req.title.toLowerCase().includes(q)) ||
      (req.description && req.description.toLowerCase().includes(q)) ||
      (docInfo.name && docInfo.name.toLowerCase().includes(q))
    );
  });

  $: groupedRequirements = (() => {
    const groupMap = new Map();
    for (const req of filteredRequirements) {
      const docInfo = getReqDocInfo(req);
      const groupKey = docInfo.docId || docInfo.name || 'OTHER';
      if (!groupMap.has(groupKey)) {
        groupMap.set(groupKey, {
          docId: docInfo.docId,
          docName: docInfo.name,
          docCategory: docInfo.category,
          items: []
        });
      }
      groupMap.get(groupKey).items.push(req);
    }
    return Array.from(groupMap.values()).sort((a, b) => b.items.length - a.items.length);
  })();

  $: filteredStrategyEvals = (strategyData?.requirement_evaluations || []).filter(item => {
    if (strategyFilter === 'ALL') return true;
    return item.decision === strategyFilter;
  });

  $: selectedStrategyReqCodes = (strategyData?.requirement_evaluations || [])
    .filter(item => item.selected_for_script)
    .map(item => item.req_code);

  $: filteredTestCases = (projectTestCases || []).filter(tc => {
    if (tcTypeFilter !== 'ALL' && (tc.type || '').toLowerCase() !== tcTypeFilter.toLowerCase()) {
      return false;
    }
    if (!tcSearchText.trim()) return true;
    const q = tcSearchText.toLowerCase();
    return (
      (tc.tc_id && tc.tc_id.toLowerCase().includes(q)) ||
      (tc.req_code && tc.req_code.toLowerCase().includes(q)) ||
      (tc.title && tc.title.toLowerCase().includes(q)) ||
      (tc.module && tc.module.toLowerCase().includes(q)) ||
      (tc.business_rule && tc.business_rule.toLowerCase().includes(q))
    );
  });

  $: selectedTestCasesList = (projectTestCases || []).filter(tc => tc.selected);

  function toggleAllTestCases(selectVal) {
    projectTestCases = projectTestCases.map(tc => ({ ...tc, selected: selectVal }));
  }

  function toggleExpand(reqId) {
    expandedReqId = expandedReqId === reqId ? null : reqId;
  }

  // Phase 2B: Start Playwright MCP Live Web Exploration & Interactive Play
  async function startExploration() {
    if (!exploreUrl || !exploreUrl.trim()) {
      toast('กรุณาระบุ Target URL ที่ต้องการให้ Playwright MCP เข้าเล่นระบบ', 'warning');
      return;
    }
    isExploring = true;
    exploreResult = null;
    exploreError = null;

    try {
      const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
      toast(`กำลังส่ง Playwright MCP (${mcpBrowserType}) เข้าสำรวจและเล่นระบบบนเว็บจริง...`, 'info');
      const res = await fetch('/api/agent/mcp-play-web', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: exploreUrl,
          project_id: pid,
          username: exploreUsername,
          password: explorePassword,
          play_instructions: playInstructions,
          selected_test_cases: selectedTestCasesList.slice(0, 12),
          browser_type: mcpBrowserType
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        const ws = data.web_state || {};
        exploreResult = {
          title: ws.title || 'Target Web Application',
          url: ws.url || exploreUrl,
          browser_engine: ws.browser_engine || mcpBrowserType,
          mcp_protocol: ws.mcp_protocol || 'Playwright MCP v1',
          interactive_elements: ws.interactive_elements || [],
          recorded_actions: ws.recorded_actions || [],
          mcp_tool_calls: ws.mcp_tool_calls || [],
          screenshot_url: ws.screenshot_url || null,
          screenshot_filename: ws.screenshot_filename || null,
          file_saved: data.file_saved,
          total_crawled_pages: ws.total_crawled_pages || 1,
          total_elements_all: ws.total_interactive_elements_across_pages || (ws.interactive_elements || []).length,
          ai_analysis: ws.ai_analysis
        };
        toast(`Playwright MCP เล่นระบบบนเว็บจริงสำเร็จ (${exploreResult.recorded_actions.length} ขั้นตอน)`, 'success');
      } else {
        exploreError = data.error || 'ไม่สามารถเข้าถึง URL เป้าหมายได้';
        toast(exploreError, 'error');
      }
    } catch (err) {
      console.error(err);
      exploreError = 'เกิดข้อผิดพลาดในการเชื่อมต่อกับ Playwright MCP Server';
    } finally {
      isExploring = false;
    }
  }

  // Phase 3: Alignment & Gap Analysis
  async function startAlignment() {
    isAligning = true;
    alignResult = null;
    alignError = null;
    try {
      const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
      const res = await fetch('/api/agent/align', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pid,
          web_state_file: exploreResult?.file_saved
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        alignResult = data.alignment_report;
        toast('วิเคราะห์ความสอดคล้องของ Flow & Business สำเร็จ', 'success');
      } else {
        alignError = data.error || 'ไม่สามารถวิเคราะห์ความสอดคล้องได้';
      }
    } catch (err) {
      console.error(err);
      alignError = 'Network error during alignment.';
    } finally {
      isAligning = false;
    }
  }

  // Phase 4: Multi-Mode Test Script Generation (From Test Cases, From Live Web Play, or Hybrid)
  async function startTestGeneration(customMode = null) {
    if (customMode) generationMode = customMode;
    isGenerating = true;
    generateResult = null;
    generateError = null;
    try {
      const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
      toast(`กำลังสร้างสคริปต์ Playwright (.spec.ts) ในโหมด ${generationMode.toUpperCase()}...`, 'info');
      const res = await fetch('/api/agent/generate-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pid,
          mode: generationMode,
          selected_test_cases: selectedTestCasesList,
          selected_req_codes: selectedStrategyReqCodes,
          web_state_file: exploreResult?.file_saved,
          recorded_actions: exploreResult?.recorded_actions || [],
          gap_analysis: alignResult || {},
          target_url: exploreUrl || $selectedProjectStore?.default_base_url || 'http://localhost:5173'
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        generateResult = data.test_script;
        if (generateResult.suites && generateResult.suites.length > 0) {
          selectedTestSuite = generateResult.suites[0];
        }
        activePhase = 4;
        toast(`สร้างสคริปต์ Playwright สำเร็จ (${generateResult.suites?.length || 1} ไฟล์)`, 'success');
      } else {
        generateError = data.error || 'ไม่สามารถสร้างสคริปต์ทดสอบได้';
        toast(generateError, 'error');
      }
    } catch (err) {
      console.error(err);
      generateError = 'Network error during script generation.';
    } finally {
      isGenerating = false;
    }
  }

  async function saveEditedSuiteCode() {
    if (!selectedTestSuite) return;
    isSavingCode = true;
    try {
      const res = await fetch('/api/agent/save-test-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_name: selectedTestSuite.saved_path,
          code: selectedTestSuite.code
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('บันทึกโค้ด Playwright (.spec.ts) ลงไฟล์เรียบร้อยแล้ว', 'success');
      } else {
        toast(data.error || 'บันทึกโค้ดไม่สำเร็จ', 'error');
      }
    } catch (e) {
      toast('ไม่สามารถบันทึกโค้ดได้', 'error');
    } finally {
      isSavingCode = false;
    }
  }

  function downloadAllTests() {
    const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
    if (pid) {
      window.open(`/api/agent/download-tests/${pid}`, '_blank');
    }
  }

  // Phase 5: Execute Test & Evaluate Flow + Business Accuracy
  async function startTestExecution() {
    isRunningTest = true;
    runTestSuccess = null;
    runTestOutput = null;
    runTestError = null;
    healResult = null;
    healError = null;
    try {
      const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
      toast('กำลังรันสคริปต์ Playwright และวัดผลความแม่นยำเทียบกับ Flow และ Business ของลูกค้า...', 'info');
      const res = await fetch('/api/agent/run-test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pid,
          file_name: selectedTestSuite?.saved_path || generateResult?.file_name,
          code: selectedTestSuite?.code || generateResult?.code || '',
          selected_test_cases: selectedTestCasesList,
          recorded_actions: exploreResult?.recorded_actions || [],
          evaluate_accuracy: true
        })
      });
      const data = await res.json();
      if (res.ok) {
        runTestSuccess = data.success;
        runTestOutput = data.output;
        if (data.accuracy_report) {
          accuracyReport = data.accuracy_report;
        }
        toast(
          runTestSuccess
            ? 'รันสคริปต์ Playwright ผ่านสำเร็จ พร้อมประเมินความแม่นยำแล้ว'
            : 'รันสคริปต์พบจุดที่ต้องปรับปรุง สามารถกด Self-Healing เพื่อให้ AI ซ่อมโค้ดได้',
          runTestSuccess ? 'success' : 'warning'
        );
      } else {
        runTestError = data.error || 'Failed to run test';
      }
    } catch (err) {
      console.error(err);
      runTestError = 'Network error during execution.';
    } finally {
      isRunningTest = false;
    }
  }

  async function runStandaloneAccuracyEvaluation() {
    const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
    if (!pid || (!selectedTestSuite && !generateResult)) return;
    isEvaluatingAccuracy = true;
    try {
      toast('กำลังวิเคราะห์ความแม่นยำของสคริปต์เทียบกับ Flow การทำงานและ Business ของลูกค้า...', 'info');
      const res = await fetch('/api/agent/evaluate-automation-accuracy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pid,
          file_name: selectedTestSuite?.file_name || generateResult?.file_name || 'suite.spec.ts',
          code: selectedTestSuite?.code || generateResult?.code || '',
          test_output: runTestOutput || '',
          run_passed: runTestSuccess,
          selected_test_cases: selectedTestCasesList,
          recorded_actions: exploreResult?.recorded_actions || []
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        accuracyReport = data.accuracy_report;
        toast(`ประเมินความแม่นยำสำเร็จ: คะแนนรวม ${accuracyReport.overall_accuracy_score}%`, 'success');
      } else {
        toast(data.error || 'ไม่สามารถประเมินความแม่นยำได้', 'error');
      }
    } catch (e) {
      console.error(e);
      toast('เกิดข้อผิดพลาดในการประเมินความแม่นยำ', 'error');
    } finally {
      isEvaluatingAccuracy = false;
    }
  }

  async function startSelfHealing() {
    isHealing = true;
    healResult = null;
    healError = null;
    try {
      toast('กำลังใช้ Agent 5 วิเคราะห์ Error Log และซ่อมแซมโค้ด Playwright อัตโนมัติ...', 'info');
      const res = await fetch('/api/agent/heal-test', {
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
          selectedTestSuite = { ...selectedTestSuite };
        } else if (generateResult) {
          generateResult.code = healResult.fixed_code;
        }
        toast('ซ่อมแซมโค้ดและบันทึกทับไฟล์เดิมสำเร็จ สามารถกดรันทดสอบซ้ำได้ทันที', 'success');
      } else {
        healError = data.error || 'Failed to heal test';
      }
    } catch (err) {
      console.error(err);
      healError = 'Network error during self-healing.';
    } finally {
      isHealing = false;
    }
  }

  // Cross-Agent Handoff Actions
  function sendStrategyOrReportToDocCreation(mode = 'strategy') {
    const pid = $selectedProjectStore?.id || $selectedProjectStore?.project_id;
    const pName = $selectedProjectStore?.name || $selectedProjectStore?.project_name || 'Project';
    let findings = [];
    let rawMd = '';

    if (mode === 'strategy' && strategyData) {
      findings = (strategyData.requirement_evaluations || [])
        .filter(e => e.decision !== 'MANUAL_ONLY')
        .map(e => ({
          severity: e.priority === 'P0' ? 'Critical' : 'Major',
          category: e.decision_label || e.decision,
          issue: `[${e.req_code}] ${e.title} (ROI: ${e.roi_score}%)`,
          recommendation: `${e.why_or_why_not} — แนวทาง: ${e.recommended_approach || ''}`
        }));
      rawMd = `# แผนกลยุทธ์การทำ Automate Test (${pName})\n\n${strategyData.executive_summary}\n\n` +
        (strategyData.requirement_evaluations || [])
          .map(e => `## ${e.req_code}: ${e.title}\n- การตัดสินใจ: ${e.decision_label}\n- Priority: ${e.priority} | ROI: ${e.roi_score}%\n- ข้อดี: ${(e.pros || []).join(', ')}\n- ข้อเสีย/ข้อควรระวัง: ${(e.cons || []).join(', ')}\n- เหตุผล: ${e.why_or_why_not}`)
          .join('\n\n');
    } else if (accuracyReport) {
      findings = (accuracyReport.traceability_matrix || []).map(m => ({
        severity: m.execution_status === 'FAILED' ? 'High' : 'Info',
        category: 'Automation Accuracy Verification',
        issue: `[${m.tc_id} / ${m.req_code}] ${m.scenario_title} (ความแม่นยำ ${m.accuracy_percent}%)`,
        recommendation: m.remark || m.business_expectation
      }));
      rawMd = `# รายงานผลการวัดความแม่นยำ Automate Test (${pName})\n\n- คะแนนความแม่นยำรวม: ${accuracyReport.overall_accuracy_score}%\n- ความถูกต้องตาม Flow: ${accuracyReport.flow_alignment_score}%\n- ความตรงตาม Business ลูกค้า: ${accuracyReport.business_compliance_score}%\n\n${accuracyReport.summary}`;
    }

    const payload = {
      project_id: pid,
      project_name: pName,
      doc_type: 'TestCase',
      group_name: 'Automation Test Plan',
      group_type: 'Test Case',
      source_filename: mode === 'strategy' ? 'Automation_Strategy_Plan.md' : 'Automation_Accuracy_Report.md',
      findings,
      raw_markdown: rawMd
    };

    qaRefinementFeedback.set(payload);
    dispatch('navigate', { view: 'qa_doc_creation', feedback: payload });
    toast('ส่งข้อมูลไปยัง Agent QA Document Creation เรียบร้อยแล้ว', 'success');
  }

  function navigateToOtherAgent(viewName) {
    dispatch('navigate', { view: viewName });
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
      <!-- Top Bar: Back Button + Playwright MCP Bridge Status -->
      <div class="top-command-bar">
        <button type="button" class="btn-back" on:click={() => selectedProjectStore.set(null)}>
          <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">
            <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
          </svg>
          <span>เปลี่ยนโครงการ</span>
        </button>

        <div class="mcp-status-cluster">
          <div class="mcp-live-pill">
            <span class="pulse-dot"></span>
            <span>Playwright MCP Connected</span>
            <span class="mcp-tag">@playwright/mcp • {mcpBrowserType.toUpperCase()}</span>
          </div>

          <select
            bind:value={mcpBrowserType}
            class="mcp-browser-select"
            title="เลือก Browser Engine สำหรับ Playwright MCP"
            aria-label="เลือก Browser Engine สำหรับ Playwright MCP"
          >
            <option value="chromium">🌐 Chromium Engine</option>
            <option value="firefox">🦊 Firefox Engine</option>
            <option value="webkit">🧭 WebKit Engine</option>
          </select>

          <button type="button" class="btn-mcp-config" on:click={() => (showMcpDrawer = !showMcpDrawer)}>
            🔌 ตั้งค่า & ดู MCP Tools ({showMcpDrawer ? 'ซ่อน' : '5 Tools'})
          </button>
        </div>
      </div>

      <!-- Header & Cross-Agent Ecosystem Hub -->
      <div class="header-section">
        <div class="header-title-row">
          <div>
            <h2>QA Test Automation & Playwright MCP Studio</h2>
            <p class="subtitle">
              วิเคราะห์ความคุ้มค่าในการทำ Automate จาก Requirement • สร้างสคริปต์จาก Test Case ระบบ หรือส่ง Playwright MCP เข้าเล่นระบบบนเว็บจริง • วัดผลความแม่นยำตาม Flow และ Business ของลูกค้า
            </p>
          </div>
          <div class="active-project-badge">
            <span>โครงการ:</span>
            <strong>{$selectedProjectStore.project_code} — {$selectedProjectStore.name}</strong>
          </div>
        </div>

        <!-- Playwright MCP Configuration & Tools Drawer -->
        {#if showMcpDrawer}
          <div class="mcp-drawer-card" transition:slide>
            <div class="mcp-drawer-header">
              <div>
                <h4>🔌 Playwright MCP Architecture & External Agent Bridge</h4>
                <p>เชื่อมต่อการทำงานทั้งภายในระบบ Spectra QA และเปิดให้ AI Agent ภายนอก (Claude Desktop / Cursor / Playwright MCP Client) เรียกใช้งานได้โดยตรง</p>
              </div>
              <select
                bind:value={mcpTransportMode}
                class="mcp-browser-select"
                aria-label="เลือกโหมดการเชื่อมต่อ Playwright MCP"
              >
                <option value="builtin_playwright_mcp">Built-in Playwright MCP Engine (Active)</option>
                <option value="sse_endpoint">Spectra MCP SSE Server (Port 8000)</option>
              </select>
            </div>
            <div class="mcp-tools-grid">
              <div class="mcp-tool-chip">
                <code>analyze_automation_strategy</code>
                <span>วิเคราะห์ Requirement ควรทำ/ไม่ควรทำ Automate + ข้อดีข้อเสีย</span>
              </div>
              <div class="mcp-tool-chip">
                <code>get_project_test_cases</code>
                <span>ดึง Test Case จาก QA Doc Creation, KB และ Diagram</span>
              </div>
              <div class="mcp-tool-chip">
                <code>playwright_mcp_play_website</code>
                <span>เข้าเล่นเว็บจริง ดึง Accessibility Tree & บันทึก Locators</span>
              </div>
              <div class="mcp-tool-chip">
                <code>generate_playwright_automation_script</code>
                <span>สร้างสคริปต์ .spec.ts รูปแบบ Page Object Model</span>
              </div>
              <div class="mcp-tool-chip">
                <code>run_and_evaluate_playwright_script</code>
                <span>รันสคริปต์จริง & วัดคะแนนความแม่นยำตาม Flow/Business</span>
              </div>
            </div>
          </div>
        {/if}

        <!-- Cross-Agent Live Ecosystem Hub -->
        <div class="ecosystem-hub-bar">
          <div class="eco-card" class:linked={ecosystemStatus?.requirements_count > 0}>
            <div class="eco-card-top">
              <span class="eco-icon">📋</span>
              <span class="eco-name">QA Consult & KB</span>
              <span class="eco-status-dot" class:on={ecosystemStatus?.kb_documents_count > 0}></span>
            </div>
            <div class="eco-metric">
              {projectDocuments.length} เอกสาร • {requirements.length} Requirements • {ecosystemStatus?.qa_consult_audits_count || 0} ผลตรวจ
            </div>
            <div class="eco-btn-group">
              <button type="button" class="eco-link-btn" on:click={() => navigateToOtherAgent('qa_consult')}>
                เปิด QA Consult ↗
              </button>
            </div>
          </div>

          <div class="eco-card" class:linked={projectTestCases.length > 0}>
            <div class="eco-card-top">
              <span class="eco-icon">📝</span>
              <span class="eco-name">QA Document Creation</span>
              <span class="eco-status-dot" class:on={projectTestCases.length > 0}></span>
            </div>
            <div class="eco-metric">
              {ecosystemStatus?.generated_docs_count || 0} เอกสารที่สร้าง • พร้อมดึง {projectTestCases.length} Test Cases
            </div>
            <div class="eco-btn-group">
              <button type="button" class="eco-link-btn" on:click={() => loadProjectTestCases($selectedProjectStore.id || $selectedProjectStore.project_id, true)}>
                🔄 ซิงค์ Test Case
              </button>
              <button type="button" class="eco-link-btn" on:click={() => navigateToOtherAgent('qa_doc_creation')}>
                เปิดโมดูล ↗
              </button>
            </div>
          </div>

          <div class="eco-card" class:linked={!!flowAnalysisData}>
            <div class="eco-card-top">
              <span class="eco-icon">📊</span>
              <span class="eco-name">QA Analysis Diagram</span>
              <span class="eco-status-dot" class:on={!!flowAnalysisData}></span>
            </div>
            <div class="eco-metric">
              {#if flowAnalysisData}
                เชื่อม Sitemap ({ecosystemStatus?.sitemap_nodes_count || 0} หน้า) & Flowchart แล้ว
              {:else}
                ยังไม่มีผัง Flowchart (คลิกเพื่อไปสร้างผังระบบ)
              {/if}
            </div>
            <div class="eco-btn-group">
              <button type="button" class="eco-link-btn" on:click={() => navigateToOtherAgent('qa_analysis_diagram')}>
                เปิด QA Diagram ↗
              </button>
            </div>
          </div>

          <div class="eco-card linked">
            <div class="eco-card-top">
              <span class="eco-icon">💎</span>
              <span class="eco-name">Spectra Agents Bridge</span>
              <span class="eco-status-dot on"></span>
            </div>
            <div class="eco-metric">
              ส่งต่อ URL และ Flow ไปยัง Performance, Security & Prism Core
            </div>
            <div class="eco-btn-group">
              <button type="button" class="eco-link-btn" on:click={() => navigateToOtherAgent('qa_performance')}>
                ⚡ Performance
              </button>
              <button type="button" class="eco-link-btn" on:click={() => navigateToOtherAgent('qa_security')}>
                🛡️ Security
              </button>
              <button type="button" class="eco-link-btn" on:click={() => navigateToOtherAgent('master_agent')}>
                💎 Prism Core
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Stepped Phase Navigation Bar -->
      <div class="phase-stepper" role="tablist" aria-label="QA Automation Phases">
        <button
          type="button"
          role="tab"
          aria-selected={activePhase === 1}
          class="phase-step-btn"
          class:active={activePhase === 1}
          class:done={requirements.length > 0 || !!strategyData}
          on:click={() => (activePhase = 1)}
        >
          1. วิเคราะห์ Requirement & วางแผน Automate
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activePhase === 2}
          class="phase-step-btn"
          class:active={activePhase === 2}
          class:done={projectTestCases.length > 0 || !!(exploreResult && exploreResult.file_saved)}
          on:click={() => (activePhase = 2)}
        >
          2. ดึง Test Case ระบบ & เล่นเว็บจริง (MCP)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activePhase === 3}
          class="phase-step-btn"
          class:active={activePhase === 3}
          class:done={!!alignResult}
          on:click={() => (activePhase = 3)}
        >
          3. ตรวจสอบ Flow & Gap Analysis
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activePhase === 4}
          class="phase-step-btn"
          class:active={activePhase === 4}
          class:done={!!generateResult}
          on:click={() => (activePhase = 4)}
        >
          4. สร้าง Playwright Script (.spec.ts)
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activePhase === 5}
          class="phase-step-btn"
          class:active={activePhase === 5}
          class:done={runTestSuccess === true || !!accuracyReport}
          on:click={() => (activePhase = 5)}
        >
          5. รันทดสอบ & วัดความแม่นยำ Business/Flow
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activePhase === 'all'}
          class="phase-step-btn phase-all-btn"
          class:active={activePhase === 'all'}
          on:click={() => (activePhase = 'all')}
        >
          แสดงทุก Phase
        </button>
      </div>

      <!-- ===================================================================== -->
      <!-- PHASE 1: REQUIREMENT EXTRACTION & AUTOMATION STRATEGY PLANNER         -->
      <!-- ===================================================================== -->
      {#if activePhase === 'all' || activePhase === 1}
        <div class="glass-panel">
          <div class="panel-header">
            <div class="header-left-cluster">
              <h3>Phase 1: วิเคราะห์ Requirement & วางแผนกลยุทธ์การทำ Automate Test</h3>
              {#if requirements.length > 0}
                <span class="badge">✓ สกัดแล้ว {requirements.length} ข้อกำหนด</span>
              {/if}
              {#if strategyData}
                <span class="badge badge-cyan">
                  🎯 แนะนำทำ Automate {strategyData.summary_metrics?.recommended_coverage_percent || 75}% (ROI {strategyData.summary_metrics?.estimated_roi_score || 88}%)
                </span>
              {/if}
            </div>
            <div class="header-actions-cluster">
              <button type="button" class="btn-secondary-sm" on:click={syncRequirementsFromProject} disabled={isSyncingReqs}>
                {#if isSyncingReqs}
                  <div class="spinner-small"></div> กำลังสกัด Requirement...
                {:else}
                  🔄 สกัด Requirement จากเอกสาร ({projectDocuments.length} ไฟล์)
                {/if}
              </button>
            </div>
          </div>
          <p class="desc-text">
            วิเคราะห์เอกสารและ Requirement ของโครงการร่วมกับข้อมูลจาก QA Consult และ QA Analysis Diagram เพื่อประเมินว่า <strong>ส่วนไหนควรทำ Automate</strong>, <strong>ข้อดี-ข้อเสียคืออะไร</strong> และ <strong>ส่วนไหนไม่จำเป็นต้องเขียน Automate</strong> พร้อมจัดทำแผน Roadmap ให้ผู้ใช้งาน
          </p>

          <!-- AI AUTOMATION STRATEGY & ROI PLANNER BOX -->
          <div class="strategy-planner-box">
            <div class="strategy-box-top">
              <div>
                <h4>🧠 AI Automation Feasibility, Pros/Cons & Test Strategy Planner</h4>
                <p>ให้ AI วิเคราะห์ความคุ้มค่า (ROI), ความซับซ้อน, ผลกระทบต่อ Business ลูกค้า และคัดแยกฟีเจอร์ที่ควรทำ vs ไม่จำเป็นต้องเขียน Automate</p>
              </div>
              <div class="strategy-controls">
                <input
                  type="text"
                  bind:value={strategyCustomFocus}
                  placeholder="ระบุโฟกัสเพิ่มเติม (เช่น เน้นระบบชำระเงิน, ลดเวลา Regression ก่อน UAT)..."
                  aria-label="ระบุโฟกัสเพิ่มเติมสำหรับการวิเคราะห์กลยุทธ์ Automate"
                  class="strategy-focus-input"
                />
                <button
                  type="button"
                  class="btn-primary-action"
                  on:click={runAutomationStrategyAnalysis}
                  disabled={isAnalyzingStrategy}
                >
                  {#if isAnalyzingStrategy}
                    <div class="spinner-small"></div> กำลังวิเคราะห์และวางแผน...
                  {:else}
                    ⚡ วิเคราะห์ Requirement & วางแผน Automate
                  {/if}
                </button>
              </div>
            </div>

            {#if strategyData}
              <div class="strategy-dashboard" transition:slide>
                <!-- Executive Summary Banner -->
                <div class="exec-summary-banner">
                  <div class="exec-summary-text">
                    <strong>📋 สรุปแผนกลยุทธ์การทำ Automate Test ของโครงการ:</strong>
                    <p>{strategyData.executive_summary}</p>
                  </div>
                  <div class="exec-summary-actions">
                    <button type="button" class="btn-doc-handoff" on:click={() => sendStrategyOrReportToDocCreation('strategy')}>
                      📄 ส่งแผนไปสร้างเอกสารใน QA Doc Creation
                    </button>
                    <button type="button" class="btn-next-phase" on:click={() => (activePhase = 2)}>
                      นำแผนที่เลือก ({selectedStrategyReqCodes.length} ข้อ) ไปสร้างสคริปต์ต่อ →
                    </button>
                  </div>
                </div>

                <!-- 4 KPI Decision Cards -->
                <div class="strategy-kpi-grid">
                  <button
                    type="button"
                    class="strat-kpi-card must"
                    class:active={strategyFilter === 'MUST_AUTOMATE'}
                    on:click={() => (strategyFilter = strategyFilter === 'MUST_AUTOMATE' ? 'ALL' : 'MUST_AUTOMATE')}
                  >
                    <span class="kpi-title">🟢 ควรทำ Automate เต็มรูปแบบ (High ROI)</span>
                    <span class="kpi-num">{strategyData.summary_metrics?.must_automate_count || 0} ข้อกำหนด</span>
                    <span class="kpi-sub">Core Business Flow & Regression หลัก</span>
                  </button>

                  <button
                    type="button"
                    class="strat-kpi-card selective"
                    class:active={strategyFilter === 'SELECTIVE'}
                    on:click={() => (strategyFilter = strategyFilter === 'SELECTIVE' ? 'ALL' : 'SELECTIVE')}
                  >
                    <span class="kpi-title">🟡 ทำ Automate เฉพาะจุดหลัก (Selective)</span>
                    <span class="kpi-num">{strategyData.summary_metrics?.selective_count || 0} ข้อกำหนด</span>
                    <span class="kpi-sub">ทำเฉพาะ Happy Path / ตรวจร่วมกับ Manual</span>
                  </button>

                  <button
                    type="button"
                    class="strat-kpi-card manual"
                    class:active={strategyFilter === 'MANUAL_ONLY'}
                    on:click={() => (strategyFilter = strategyFilter === 'MANUAL_ONLY' ? 'ALL' : 'MANUAL_ONLY')}
                  >
                    <span class="kpi-title">⚪ ไม่จำเป็นต้องเขียน Automate (Manual)</span>
                    <span class="kpi-num">{strategyData.summary_metrics?.manual_only_count || 0} ข้อกำหนด</span>
                    <span class="kpi-sub">Static UI / Visual UX / เปลี่ยนแปลงบ่อย</span>
                  </button>

                  <div class="strat-kpi-card roi">
                    <span class="kpi-title">🎯 สัดส่วน Automate ที่เหมาะสม & ROI</span>
                    <span class="kpi-num">{strategyData.summary_metrics?.recommended_coverage_percent || 75}% Coverage</span>
                    <span class="kpi-sub">ประหยัดเวลาทดสอบซ้ำ ~{strategyData.summary_metrics?.estimated_time_saved_percent || 65}%</span>
                  </div>
                </div>

                <!-- Phased Automation Roadmap -->
                {#if strategyData.automation_plan_phases && strategyData.automation_plan_phases.length > 0}
                  <div class="roadmap-section">
                    <h5>🗺️ แผนการดำเนินงาน Automate Test แบ่งตามระยะ (Automation Execution Roadmap)</h5>
                    <div class="roadmap-grid">
                      {#each strategyData.automation_plan_phases as phase}
                        <div class="roadmap-card">
                          <div class="roadmap-header">
                            <span class="phase-pill">ระยะที่ {phase.phase_no}</span>
                            <strong>{phase.phase_name}</strong>
                          </div>
                          <p class="roadmap-goal">{phase.goal}</p>
                          <div class="roadmap-meta">
                            <span>📌 เป้าหมาย: {(phase.target_reqs || []).join(', ') || 'Core Flows'}</span>
                            <span>📦 ผลลัพธ์: {phase.deliverable}</span>
                          </div>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}

                <!-- Detailed Requirement-by-Requirement Pros & Cons Matrix -->
                <div class="eval-list-header">
                  <h5>🔍 ตารางวิเคราะห์ราย Requirement: ควรทำตรงไหน ข้อดี-ข้อเสีย และส่วนไหนไม่จำเป็นต้องเขียน ({filteredStrategyEvals.length} รายการ)</h5>
                  <div class="filter-pills">
                    <button type="button" class="pill-btn" class:active={strategyFilter === 'ALL'} on:click={() => (strategyFilter = 'ALL')}>ทั้งหมด</button>
                    <button type="button" class="pill-btn" class:active={strategyFilter === 'MUST_AUTOMATE'} on:click={() => (strategyFilter = 'MUST_AUTOMATE')}>🟢 ควรทำ Automate</button>
                    <button type="button" class="pill-btn" class:active={strategyFilter === 'SELECTIVE'} on:click={() => (strategyFilter = 'SELECTIVE')}>🟡 ทำเฉพาะจุด</button>
                    <button type="button" class="pill-btn" class:active={strategyFilter === 'MANUAL_ONLY'} on:click={() => (strategyFilter = 'MANUAL_ONLY')}>⚪ ไม่จำเป็นต้องเขียน</button>
                  </div>
                </div>

                <div class="eval-cards-list">
                  {#each filteredStrategyEvals as item (item.req_code + item.title)}
                    <div class="eval-item-card decision-{item.decision?.toLowerCase()}">
                      <div class="eval-item-top">
                        <label class="eval-checkbox-label">
                          <input
                            type="checkbox"
                            bind:checked={item.selected_for_script}
                            on:change={() => { strategyData = strategyData; }}
                          />
                          <span class="req-code">{item.req_code}</span>
                          <strong>{item.title}</strong>
                        </label>
                        <div class="eval-badges">
                          <span class="priority-tag prio-{item.priority?.toLowerCase()}">{item.priority}</span>
                          <span class="roi-tag">ROI {item.roi_score}%</span>
                          <span class="decision-badge dec-{item.decision?.toLowerCase()}">
                            {item.decision_label || item.decision}
                          </span>
                        </div>
                      </div>

                      <p class="eval-why">
                        <strong>💡 เหตุผลและผลกระทบต่อ Business ลูกค้า ({item.business_impact || 'High'}):</strong> {item.why_or_why_not}
                      </p>

                      <div class="pros-cons-grid">
                        <div class="pros-box">
                          <strong>✅ ข้อดีของการทำ Automate ส่วนนี้ (Pros):</strong>
                          <ul>
                            {#each (item.pros || []) as pro}
                              <li>{pro}</li>
                            {/each}
                          </ul>
                        </div>
                        <div class="cons-box">
                          <strong>⚠️ ข้อเสีย / ข้อควรระวังในการดูแลรักษา (Cons & Trade-offs):</strong>
                          <ul>
                            {#each (item.cons || []) as con}
                              <li>{con}</li>
                            {/each}
                          </ul>
                        </div>
                      </div>

                      {#if item.recommended_approach}
                        <div class="eval-approach">
                          <span>🛠️ <strong>แนวทางที่แนะนำ:</strong> {item.recommended_approach}</span>
                          <div class="test-type-chips">
                            {#each (item.recommended_test_types || []) as tt}
                              <span class="tt-chip">{tt}</span>
                            {/each}
                          </div>
                        </div>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>

          <!-- Project Resources & Structured Requirements Browser -->
          <div class="project-resources-box" style="margin-top: 20px;">
            <div class="res-box-header">
              <div style="display: flex; align-items: center; gap: 8px;">
                <strong style="color: #f1f5f9; font-size: 14px;">📄 เอกสารต้นทางและ Structured Requirements ในโครงการ:</strong>
                <span class="doc-count-badge">{projectDocuments.length} ไฟล์ • {requirements.length} ข้อกำหนด</span>
              </div>
            </div>

            {#if projectDocuments.length > 0}
              <div class="doc-chips-list">
                <button
                  type="button"
                  class="doc-chip-btn"
                  class:active={selectedDocFilter === 'ALL'}
                  on:click={() => (selectedDocFilter = 'ALL')}
                >
                  <span class="doc-type-tag all">ALL</span>
                  <span class="doc-name">เอกสารทั้งหมด</span>
                  <span class="doc-req-count">{requirements.length} ข้อ</span>
                </button>
                {#each projectDocuments as doc}
                  {@const count = getDocReqCount(doc)}
                  <button
                    type="button"
                    class="doc-chip-btn"
                    class:active={selectedDocFilter === String(doc.id || doc.doc_id) || selectedDocFilter === (doc.original_filename || doc.name)}
                    on:click={() => toggleDocFilter(doc)}
                  >
                    <span class="doc-type-tag">{doc.doc_category || doc.doc_type || 'DOC'}</span>
                    <span class="doc-name">{doc.original_filename || doc.name || doc.filename}</span>
                    <span class="doc-req-count" class:has-reqs={count > 0}>{count} ข้อ</span>
                  </button>
                {/each}
              </div>
            {/if}

            {#if requirements.length > 0}
              <div class="req-toolbar" style="margin-top: 14px;">
                <div class="search-box">
                  <input
                    type="text"
                    bind:value={reqSearchText}
                    placeholder="ค้นหา Requirement (รหัส, ชื่อหัวข้อ, รายละเอียด)..."
                    aria-label="ค้นหา Requirement"
                    class="search-input"
                  />
                </div>
              </div>

              <div class="requirements-list" style="margin-top: 12px; max-height: 360px; overflow-y: auto;">
                {#each filteredRequirements as req (req.req_id)}
                  {@const docInfo = getReqDocInfo(req)}
                  <div class="req-card" class:expanded={expandedReqId === req.req_id}>
                    <div
                      class="req-header"
                      role="button"
                      tabindex="0"
                      aria-expanded={expandedReqId === req.req_id}
                      on:click={() => toggleExpand(req.req_id)}
                      on:keydown={(e) => handleActivateKeydown(e, () => toggleExpand(req.req_id))}
                    >
                      <div class="req-title">
                        <span class="req-code">{req.req_code}</span>
                        <h4>{req.title}</h4>
                        <span class="req-doc-chip">{docInfo.name}</span>
                      </div>
                      <span class="status-badge">{req.status || 'Active'}</span>
                    </div>
                    {#if expandedReqId === req.req_id}
                      <div class="req-body" transition:slide>
                        <p>{req.description}</p>
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
                      </div>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- ===================================================================== -->
      <!-- PHASE 2: DUAL-SOURCE INPUT (SYSTEM TEST CASES & PLAYWRIGHT MCP PLAY)  -->
      <!-- ===================================================================== -->
      {#if activePhase === 'all' || activePhase === 2}
        <div class="glass-panel">
          <div class="panel-header">
            <div class="header-left-cluster">
              <h3>Phase 2: เลือกแหล่งข้อมูลสร้าง Automate — จาก Test Case ของระบบ หรือ เข้าเล่นระบบบน Web จริง (Playwright MCP)</h3>
              <span class="badge badge-cyan">Dual-Engine Ready</span>
            </div>
          </div>
          <p class="desc-text">
            สามารถเลือกสร้างสคริปต์จากการดู <strong>Test Case ของระบบ</strong> (ดึงจาก QA Document Creation / Knowledge Base / Diagram), หรือสั่งให้ <strong>Playwright MCP เข้าไปเล่นระบบบน Website จริง</strong> เพื่อดึง Locators และบันทึกขั้นตอนการทำงานจริง หรือใช้ทั้งสองส่วนผสานกัน (Hybrid)
          </p>

          <!-- Mode Selector Tabs -->
          <div class="mode-selector-grid">
            <button
              type="button"
              class="mode-card-btn"
              class:active={inputSourceMode === 'testcase'}
              on:click={() => { inputSourceMode = 'testcase'; generationMode = 'testcase'; }}
            >
              <div class="mode-card-title">📋 โหมดที่ 1: สร้างจาก Test Case ของระบบ</div>
              <p>ดึงเอกสาร Test Case ของโครงการมาแตกขั้นตอน Steps & Expected Results แล้วแปลงเป็น Playwright Script พร้อมรัน</p>
            </button>

            <button
              type="button"
              class="mode-card-btn"
              class:active={inputSourceMode === 'web_play'}
              on:click={() => { inputSourceMode = 'web_play'; generationMode = 'web_play'; }}
            >
              <div class="mode-card-title">🌐 โหมดที่ 2: เข้า Website และให้เล่นระบบบน Web (Playwright MCP)</div>
              <p>ส่ง Playwright MCP เข้าหน้าเว็บจริง ทดลองคลิก กรอกข้อมูล ดึง Accessibility Locators และบันทึกเป็นสคริปต์</p>
            </button>

            <button
              type="button"
              class="mode-card-btn"
              class:active={inputSourceMode === 'hybrid'}
              on:click={() => { inputSourceMode = 'hybrid'; generationMode = 'hybrid'; }}
            >
              <div class="mode-card-title">⚡ โหมดที่ 3: Hybrid (Test Case ระบบ + เล่นเว็บจริงด้วย MCP)</div>
              <p>แนะนำสูงสุด: ใช้ Test Case ของระบบเป็นเกณฑ์ Business แล้วให้ Playwright MCP เข้าเว็บจริงเพื่อจับคู่ Selector ที่แม่นยำ 100%</p>
            </button>
          </div>

          <!-- SECTION 2A: SYSTEM TEST CASES REPOSITORY -->
          {#if inputSourceMode === 'testcase' || inputSourceMode === 'hybrid'}
            <div class="sub-panel-box" transition:slide>
              <div class="sub-panel-header">
                <div>
                  <h4>📋 คลัง Test Case ของระบบ (System Test Cases — เลือกแล้ว {selectedTestCasesList.length} / {projectTestCases.length} ข้อ)</h4>
                  <p>รวบรวมจาก QA Document Creation, เอกสาร Test Case ใน Knowledge Base, Traceability Matrix และ Structured Requirements</p>
                </div>
                <div class="sub-panel-actions">
                  <button
                    type="button"
                    class="btn-secondary-sm"
                    on:click={() => (showAddTcModal = !showAddTcModal)}
                  >
                    + เพิ่ม Test Case เอง
                  </button>
                  <button
                    type="button"
                    class="btn-secondary-sm"
                    on:click={() => loadProjectTestCases($selectedProjectStore.id || $selectedProjectStore.project_id, true)}
                    disabled={isLoadingTestCases}
                  >
                    {#if isLoadingTestCases}
                      <div class="spinner-small"></div> กำลังดึง Test Case...
                    {:else}
                      🔄 ดึง/สกัด Test Case ใหม่จากทุก Agent
                    {/if}
                  </button>
                  <button
                    type="button"
                    class="btn-primary-action"
                    on:click={() => startTestGeneration('testcase')}
                    disabled={isGenerating || selectedTestCasesList.length === 0}
                  >
                    ⚡ สร้าง Playwright Script จาก Test Case ที่เลือก ({selectedTestCasesList.length})
                  </button>
                </div>
              </div>

              {#if showAddTcModal}
                <div class="add-tc-form" transition:slide>
                  <h5>+ เพิ่ม Test Case สำหรับสร้าง Automate Script</h5>
                  <div class="tc-form-grid">
                    <input type="text" bind:value={newTcForm.tc_id} placeholder="รหัส TC (เช่น TC-LOGIN-01)" aria-label="รหัส Test Case" class="url-input" />
                    <input type="text" bind:value={newTcForm.req_code} placeholder="รหัส Req (เช่น REQ-001)" aria-label="รหัส Requirement" class="url-input" />
                    <input type="text" bind:value={newTcForm.module} placeholder="โมดูล/หน้าจอ" aria-label="โมดูลหรือหน้าจอ" class="url-input" />
                    <select bind:value={newTcForm.type} aria-label="ประเภท Test Case" class="url-input">
                      <option value="Positive">Positive (Happy Path)</option>
                      <option value="Negative">Negative (Validation / Error)</option>
                      <option value="Boundary">Boundary Check</option>
                    </select>
                  </div>
                  <input type="text" bind:value={newTcForm.title} placeholder="ชื่อกรณีทดสอบ (Test Case Title)..." aria-label="ชื่อกรณีทดสอบ" class="url-input" style="margin-top: 8px; width: 100%;" />
                  <textarea bind:value={newTcForm.test_steps_text} rows="3" placeholder="ขั้นตอนการทดสอบ (บรรทัดละ 1 ขั้นตอน)..." aria-label="ขั้นตอนการทดสอบ" class="url-input" style="margin-top: 8px; width: 100%;"></textarea>
                  <div class="tc-form-grid" style="margin-top: 8px;">
                    <input type="text" bind:value={newTcForm.expected_result} placeholder="ผลลัพธ์ที่คาดหวัง (Expected Result)..." aria-label="ผลลัพธ์ที่คาดหวัง" class="url-input" />
                    <input type="text" bind:value={newTcForm.business_rule} placeholder="กฎทางธุรกิจของลูกค้า (Business Rule)..." aria-label="กฎทางธุรกิจของลูกค้า" class="url-input" />
                  </div>
                  <div style="display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; margin-top: 10px;">
                    <button type="button" class="btn-secondary-sm" on:click={() => (showAddTcModal = false)}>ยกเลิก</button>
                    <button type="button" class="btn-primary-action" on:click={addCustomTestCase}>บันทึก Test Case</button>
                  </div>
                </div>
              {/if}

              <div class="tc-filter-bar">
                <input
                  type="text"
                  bind:value={tcSearchText}
                  placeholder="ค้นหา Test Case (TC-ID, REQ-ID, ชื่อกรณีทดสอบ, กฎธุรกิจ)..."
                  aria-label="ค้นหา Test Case"
                  class="search-input"
                  style="flex: 1; min-width: 220px;"
                />
                <div class="filter-pills">
                  <button type="button" class="pill-btn" class:active={tcTypeFilter === 'ALL'} on:click={() => (tcTypeFilter = 'ALL')}>ทั้งหมด ({projectTestCases.length})</button>
                  <button type="button" class="pill-btn" class:active={tcTypeFilter === 'Positive'} on:click={() => (tcTypeFilter = 'Positive')}>Positive</button>
                  <button type="button" class="pill-btn" class:active={tcTypeFilter === 'Negative'} on:click={() => (tcTypeFilter = 'Negative')}>Negative</button>
                  <button type="button" class="pill-btn" on:click={() => toggleAllTestCases(true)}>✓ เลือกทั้งหมด</button>
                  <button type="button" class="pill-btn" on:click={() => toggleAllTestCases(false)}>ล้างที่เลือก</button>
                </div>
              </div>

              {#if isLoadingTestCases}
                <div class="loading-state">
                  <div class="spinner"></div>
                  <p>กำลังสกัดและรวบรวม Test Case จากเอกสารของระบบ...</p>
                </div>
              {:else if filteredTestCases.length === 0}
                <div class="empty-state">
                  <p>ยังไม่มีรายการ Test Case ที่ดึงไว้สำหรับโครงการนี้</p>
                  <button
                    type="button"
                    class="btn-primary-action"
                    on:click={() => loadProjectTestCases($selectedProjectStore.id || $selectedProjectStore.project_id, true)}
                  >
                    ⚡ สกัด Test Case จากเอกสารและ Requirement ในระบบทันที
                  </button>
                </div>
              {:else}
                <div class="tc-cards-grid">
                  {#each filteredTestCases as tc (tc.id || tc.tc_id)}
                    <div class="tc-item-card" class:selected={tc.selected}>
                      <div class="tc-item-top">
                        <label class="tc-check-wrap">
                          <input
                            type="checkbox"
                            bind:checked={tc.selected}
                            on:change={() => { projectTestCases = [...projectTestCases]; }}
                          />
                          <span class="tc-id-badge">{tc.tc_id}</span>
                          <span class="req-code">{tc.req_code}</span>
                          <strong>{tc.title}</strong>
                        </label>
                        <div class="tc-tags">
                          <span class="tc-type-badge type-{(tc.type || 'Positive').toLowerCase()}">{tc.type || 'Positive'}</span>
                          <span class="priority-tag prio-{(tc.priority || 'P1').toLowerCase()}">{tc.priority || 'P1'}</span>
                          <span class="tc-src-tag">{tc.source_doc}</span>
                        </div>
                      </div>

                      <div class="tc-details-grid">
                        <div>
                          <strong>ขั้นตอนการทดสอบ (Test Steps):</strong>
                          <ol class="tc-steps-ol">
                            {#each (tc.test_steps || []) as st}
                              <li>{st}</li>
                            {/each}
                          </ol>
                        </div>
                        <div>
                          <strong>ผลลัพธ์ที่คาดหวัง (Expected Result):</strong>
                          <p>{tc.expected_result}</p>
                          <strong>🎯 เกณฑ์ Business ของลูกค้าที่ต้องวัดผล:</strong>
                          <p class="biz-rule-highlight">{tc.business_rule || tc.expected_result}</p>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          <!-- SECTION 2B: PLAYWRIGHT MCP INTERACTIVE LIVE WEB EXPLORER & RECORDER -->
          {#if inputSourceMode === 'web_play' || inputSourceMode === 'hybrid'}
            <div class="sub-panel-box mcp-web-box" style="margin-top: 20px;" transition:slide>
              <div class="sub-panel-header">
                <div>
                  <h4>🌐 ส่ง Playwright MCP เข้า Website และเล่นระบบบน Web จริง (Live Web Play & Action Recorder)</h4>
                  <p>AI จะเปิดบราวเซอร์ผ่าน Playwright MCP เข้าไปยัง URL เป้าหมาย ทดลองเล่นตาม Flow ดึง Accessibility Tree และบันทึก Playwright Locators จริงพร้อมภาพหลักฐาน</p>
                </div>
              </div>

              <div class="mcp-play-form">
                <div class="mcp-form-row">
                  <input
                    type="text"
                    bind:value={exploreUrl}
                    placeholder="Target Website URL (เช่น http://localhost:5173 หรือ https://example.com)"
                    aria-label="Target Website URL"
                    class="url-input"
                    style="flex: 2.5;"
                  />
                  <input
                    type="text"
                    bind:value={exploreUsername}
                    placeholder="Username สำหรับ Login (ถ้ามี)"
                    aria-label="Username สำหรับ Login"
                    class="url-input"
                    style="flex: 1;"
                  />
                  <input
                    type="password"
                    bind:value={explorePassword}
                    placeholder="Password (ถ้ามี)"
                    aria-label="Password สำหรับ Login"
                    class="url-input"
                    style="flex: 1;"
                  />
                </div>
                <div class="mcp-form-row" style="margin-top: 10px;">
                  <input
                    type="text"
                    bind:value={playInstructions}
                    placeholder="สั่งให้ AI เล่น Flow อะไรบนเว็บ (เช่น ล็อกอินแล้วเข้าเมนูค้นหา กรอกข้อมูลทดสอบ และกดปุ่มตรวจสอบตาราง)..."
                    aria-label="คำสั่งให้ AI เล่น Flow บนเว็บ"
                    class="url-input"
                    style="flex: 1;"
                  />
                  <button
                    type="button"
                    class="btn-primary-action"
                    on:click={startExploration}
                    disabled={isExploring || !exploreUrl}
                  >
                    {#if isExploring}
                      <div class="spinner-small"></div> Playwright MCP กำลังเปิดเว็บและเล่นระบบ...
                    {:else}
                      ▶️ ส่ง Playwright MCP เข้าเล่นระบบบนเว็บจริง
                    {/if}
                  </button>
                </div>
              </div>

              {#if exploreResult}
                <div class="explore-result" transition:slide>
                  <div class="result-header">
                    <div class="status-title">
                      <span class="check-icon">✓</span>
                      <h4>Playwright MCP เล่นระบบบนเว็บจริงและบันทึก Locators สำเร็จ ({exploreResult.title})</h4>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                      <span class="saved-tag">💾 {exploreResult.file_saved}</span>
                      <button
                        type="button"
                        class="btn-primary-action"
                        on:click={() => startTestGeneration(inputSourceMode === 'web_play' ? 'web_play' : 'hybrid')}
                        disabled={isGenerating}
                      >
                        ⚡ นำผลการเล่นเว็บไปสร้าง Playwright Script ทันที →
                      </button>
                    </div>
                  </div>

                  <div class="metrics-grid">
                    <div class="metric-card">
                      <span class="metric-label">🌐 หน้าที่สำรวจและเล่นจริง</span>
                      <span class="metric-value">{exploreResult.total_crawled_pages || 1} หน้าจอ</span>
                    </div>
                    <div class="metric-card">
                      <span class="metric-label">🎬 ขั้นตอนที่เล่นและบันทึกได้</span>
                      <span class="metric-value highlight-green">{exploreResult.recorded_actions?.length || 0} Actions</span>
                    </div>
                    <div class="metric-card">
                      <span class="metric-label">🎯 Playwright Locators ที่สกัดได้</span>
                      <span class="metric-value highlight-blue">{exploreResult.total_elements_all || 0} จุด</span>
                    </div>
                    <div class="metric-card">
                      <span class="metric-label">🔌 โปรโตคอลเชื่อมต่อ</span>
                      <span class="metric-value highlight-purple">{exploreResult.browser_engine?.toUpperCase()} MCP</span>
                    </div>
                  </div>

                  <!-- Recorded Actions Timeline + Live Screenshot Grid -->
                  <div class="mcp-evidence-split" class:single-col={!exploreResult.screenshot_url}>
                    <div class="recorded-timeline-box">
                      <h5>🎬 บันทึกลำดับการเล่นระบบบนเว็บจริง (Playwright MCP Recorded Actions & Locators)</h5>
                      <div class="recorded-steps-list">
                        {#each (exploreResult.recorded_actions || []) as act}
                          <div class="recorded-step-item">
                            <div class="rec-step-badge">Step {act.step_no}</div>
                            <div class="rec-step-content">
                              <div class="rec-step-top">
                                <span class="mcp-tool-tag">{act.mcp_tool}</span>
                                <strong>{act.description}</strong>
                              </div>
                              <code class="rec-pw-code">{act.playwright_code}</code>
                            </div>
                          </div>
                        {/each}
                      </div>
                    </div>

                    {#if exploreResult.screenshot_url}
                      <div class="mcp-screenshot-box">
                        <h5>📸 ภาพหลักฐานหน้าจอจากการเข้าเล่นระบบจริง</h5>
                        <img src={exploreResult.screenshot_url} alt="Playwright MCP Live Web Play Evidence" class="mcp-shot-img" />
                      </div>
                    {/if}
                  </div>

                  {#if exploreResult.ai_analysis}
                    <div class="ai-analysis-panel" style="margin-top: 16px; padding: 15px; background: rgba(30, 41, 59, 0.7); border-radius: 10px; border: 1px solid rgba(147, 197, 253, 0.2);">
                      <h5 style="margin: 0 0 8px 0; color: #93c5fd;">🧠 AI วิเคราะห์การทำงานของหน้าเว็บเทียบกับ Business ลูกค้า</h5>
                      <p style="margin: 0 0 8px 0; font-size: 13.5px; color: #e2e8f0;">{exploreResult.ai_analysis.system_overview}</p>
                      {#if exploreResult.ai_analysis.flow_play_summary}
                        <p style="margin: 0; font-size: 13px; color: #34d399;">✓ {exploreResult.ai_analysis.flow_play_summary}</p>
                      {/if}
                    </div>
                  {/if}
                </div>
              {/if}

              {#if exploreError}
                <div class="explore-error" transition:slide>
                  <p>{exploreError}</p>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/if}

      <!-- ===================================================================== -->
      <!-- PHASE 3: SEMANTIC ALIGNMENT & FLOW GAP ANALYSIS                       -->
      <!-- ===================================================================== -->
      {#if activePhase === 'all' || activePhase === 3}
        <div class="glass-panel">
          <div class="panel-header">
            <h3>Phase 3: ตรวจสอบความสอดคล้องของ Flow การทำงาน & Business Gap Analysis (Agent 3)</h3>
            {#if alignResult}
              <span class="badge">✓ ตรวจสอบความสอดคล้องแล้ว</span>
            {:else}
              <span class="badge badge-cyan">พร้อมเปรียบเทียบ</span>
            {/if}
          </div>
          <p class="desc-text">
            เปรียบเทียบ Requirements, Test Cases และผัง QA Analysis Diagram กับโครงสร้างหน้าเว็บจริงที่ Playwright MCP สำรวจพบ เพื่อค้นหาจุดที่ตรงกันและจุดต่าง (Gap Analysis) ก่อนสร้างสคริปต์
          </p>

          <div style="display: flex; gap: 12px; flex-wrap: wrap;">
            <button
              type="button"
              class="btn-primary-action"
              on:click={startAlignment}
              disabled={isAligning || !exploreResult || !exploreResult.file_saved}
            >
              {#if isAligning}
                <div class="spinner-small"></div> กำลังเปรียบเทียบ Flow & Business Gaps...
              {:else}
                🔍 เริ่มวิเคราะห์ความสอดคล้อง (Run Flow & Business Alignment)
              {/if}
            </button>
            <button
              type="button"
              class="btn-secondary-sm"
              on:click={() => (activePhase = 4)}
            >
              ข้ามไป Phase 4 (สร้างสคริปต์จาก Test Case / ผลสำรวจทันที) →
            </button>
          </div>

          {#if alignResult}
            <div class="align-result" transition:slide>
              <h4>ผลการตรวจสอบความสอดคล้อง (Flow & Business Alignment Report)</h4>
              <div class="align-summary">
                <p><strong>สรุปผล:</strong> {alignResult.analysis_summary}</p>
              </div>

              {#if alignResult.matched_elements && alignResult.matched_elements.length > 0}
                <div class="matched-elements-box" style="margin-bottom: 14px;">
                  <strong style="color: #34d399;">✅ องค์ประกอบและ Flow ที่ตรงตาม Requirement ({alignResult.matched_elements.length}):</strong>
                  <ul style="margin: 6px 0 0 0; padding-left: 20px; color: #cbd5e1; font-size: 13.5px;">
                    {#each alignResult.matched_elements as m}
                      <li>{m}</li>
                    {/each}
                  </ul>
                </div>
              {/if}

              <div class="align-issues">
                <strong>⚠️ จุดต่างหรือข้อควรระวังที่พบ (Discrepancies / Gaps):</strong>
                {#if alignResult.discrepancies && alignResult.discrepancies.length > 0}
                  <ul>
                    {#each alignResult.discrepancies as issue}
                      <li class="issue-item severity-{issue.severity?.toLowerCase() || 'low'}">
                        <span class="issue-req">[{issue.req_code}]</span> {issue.issue}
                      </li>
                    {/each}
                  </ul>
                {:else}
                  <p class="no-issue">✓ ไม่พบจุดขัดแย้ง! โครงสร้างหน้าเว็บจริงสอดคล้องกับ Requirement และ Flow การทำงาน</p>
                {/if}
              </div>

              <div class="align-recommendation">
                <p><strong>💡 ข้อเสนอแนะในการสร้าง Automate Script:</strong> {alignResult.recommendation}</p>
              </div>
            </div>
          {/if}
          {#if alignError}
            <div class="explore-error" transition:slide>
              <p>{alignError}</p>
            </div>
          {/if}
        </div>
      {/if}

      <!-- ===================================================================== -->
      <!-- PHASE 4: MULTI-MODE PLAYWRIGHT SCRIPT GENERATION (.spec.ts POM)       -->
      <!-- ===================================================================== -->
      {#if activePhase === 'all' || activePhase === 4}
        <div class="glass-panel">
          <div class="panel-header">
            <div class="header-left-cluster">
              <h3>Phase 4: สร้าง Automate Script มาตรฐาน Playwright TypeScript (Page Object Model)</h3>
              {#if generateResult}
                <span class="badge">✓ สร้างสคริปต์สำเร็จ ({generateResult.suites?.length || 1} ไฟล์)</span>
              {/if}
            </div>
            {#if generateResult}
              <button type="button" class="btn-secondary-sm" on:click={downloadAllTests}>
                📦 ดาวน์โหลดสคริปต์ทั้งหมด (.zip)
              </button>
            {/if}
          </div>
          <p class="desc-text">
            สร้างสคริปต์ Playwright (`.spec.ts`) รูปแบบ Page Object Model (POM) พร้อมฝัง <strong>Business Assertions</strong> และ <strong>Traceability Tags (`@tc_id`, `@req_code`, `@business_rule`)</strong> เพื่อใช้วัดผลความถูกต้อง
          </p>

          <div class="gen-mode-bar">
            <label class="gen-radio">
              <input type="radio" bind:group={generationMode} value="testcase" />
              <span>📋 สร้างจาก Test Case ระบบ ({selectedTestCasesList.length} ข้อ)</span>
            </label>
            <label class="gen-radio">
              <input type="radio" bind:group={generationMode} value="web_play" />
              <span>🌐 สร้างจากการเล่นเว็บจริงด้วย Playwright MCP ({exploreResult?.recorded_actions?.length || 0} Steps)</span>
            </label>
            <label class="gen-radio">
              <input type="radio" bind:group={generationMode} value="hybrid" />
              <span>⚡ สร้างแบบ Hybrid (ผสาน Test Case + เล่นเว็บจริง + ผัง Diagram)</span>
            </label>

            <button
              type="button"
              class="btn-primary-action"
              on:click={() => startTestGeneration()}
              disabled={isGenerating}
            >
              {#if isGenerating}
                <div class="spinner-small"></div> กำลังสร้างโค้ด Playwright POM...
              {:else}
                🚀 สร้าง Playwright Automate Script (.spec.ts)
              {/if}
            </button>
          </div>

          {#if generateResult}
            <div class="align-result" transition:slide>
              {#if generateResult.suites}
                <div class="suite-list">
                  {#each generateResult.suites as suite}
                    <div
                      class="suite-card"
                      class:active={selectedTestSuite === suite}
                      role="button"
                      tabindex="0"
                      aria-pressed={selectedTestSuite === suite}
                      on:click={() => (selectedTestSuite = suite)}
                      on:keydown={(e) => handleActivateKeydown(e, () => (selectedTestSuite = suite))}
                    >
                      <div class="suite-header">
                        <strong>{suite.menu_name}</strong>
                        <span class="test-count">{suite.test_count} Tests</span>
                      </div>
                      <div class="suite-meta">
                        <span>{suite.req_code}</span> • <span>{suite.file_name}</span>
                      </div>
                      <div class="suite-mini-scores">
                        <span>Flow: <strong>{suite.flow_alignment_score || 94}%</strong></span>
                        <span>Business: <strong>{suite.business_compliance_score || 92}%</strong></span>
                        <span>Locator: <strong>{suite.locator_resilience_score || 94}%</strong></span>
                      </div>
                    </div>
                  {/each}
                </div>

                {#if selectedTestSuite}
                  <div class="suite-editor-box">
                    <div class="suite-editor-toolbar">
                      <div>
                        <strong style="color: #f8fafc;">📄 {selectedTestSuite.saved_path}</strong>
                        {#if selectedTestSuite.business_flow_summary}
                          <span style="color: #94a3b8; font-size: 12.5px; margin-left: 10px;">— {selectedTestSuite.business_flow_summary}</span>
                        {/if}
                      </div>
                      <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button type="button" class="btn-secondary-sm" on:click={saveEditedSuiteCode} disabled={isSavingCode}>
                          {isSavingCode ? 'กำลังบันทึก...' : '💾 บันทึกการแก้ไขโค้ด'}
                        </button>
                        <button
                          type="button"
                          class="btn-primary-action"
                          on:click={() => { activePhase = 5; startTestExecution(); }}
                        >
                          ▶️ รันสคริปต์นี้ & วัดผลความแม่นยำ →
                        </button>
                      </div>
                    </div>
                    <textarea
                      bind:value={selectedTestSuite.code}
                      rows="18"
                      aria-label="โค้ดสคริปต์ Playwright (.spec.ts)"
                      class="code-editor-textarea"
                      spellcheck="false"
                    ></textarea>
                  </div>
                {/if}
              {/if}
            </div>
          {/if}
          {#if generateError}
            <div class="explore-error" transition:slide>
              <p>{generateError}</p>
            </div>
          {/if}
        </div>
      {/if}

      <!-- ===================================================================== -->
      <!-- PHASE 5: TEST EXECUTION, SELF-HEALING & BUSINESS/FLOW ACCURACY AUDIT  -->
      <!-- ===================================================================== -->
      {#if activePhase === 'all' || activePhase === 5}
        <div class="glass-panel" class:disabled={!generateResult}>
          <div class="panel-header">
            <div class="header-left-cluster">
              <h3>Phase 5: รันทดสอบ, ซ่อมแซมอัตโนมัติ (Self-Healing) & วัดผลความแม่นยำตาม Flow และ Business ลูกค้า</h3>
              {#if runTestSuccess === true}
                <span class="badge">✓ Test Execution Passed</span>
              {:else if runTestSuccess === false}
                <span class="badge badge-danger">✕ Test Failed (พร้อมซ่อมด้วย Self-Healing)</span>
              {/if}
              {#if accuracyReport}
                <span class="badge badge-cyan">
                  🎯 ความแม่นยำรวม {accuracyReport.overall_accuracy_score}% ({accuracyReport.verdict_label || accuracyReport.verdict_status})
                </span>
              {/if}
            </div>
          </div>
          <p class="desc-text">
            รันสคริปต์ Playwright จริงและประเมินว่าสคริปต์ที่สร้างขึ้นมีความถูกต้องตาม <strong>ลำดับ Flow การทำงานของระบบ</strong> และตรงตาม <strong>เงื่อนไขทางธุรกิจ (Business Rules & Expected Results)</strong> ของลูกค้ากี่เปอร์เซ็นต์
          </p>

          <div class="execution-action-bar">
            <button
              type="button"
              class="btn-primary-action"
              on:click={startTestExecution}
              disabled={isRunningTest || !generateResult}
            >
              {#if isRunningTest}
                <div class="spinner-small"></div> กำลังรัน Playwright & วัดผลความแม่นยำ...
              {:else}
                ▶️ รันสคริปต์ทดสอบ & วัดผลความแม่นยำ (Run & Evaluate)
              {/if}
            </button>

            <button
              type="button"
              class="btn-secondary-sm"
              on:click={runStandaloneAccuracyEvaluation}
              disabled={isEvaluatingAccuracy || !generateResult}
            >
              {#if isEvaluatingAccuracy}
                <div class="spinner-small"></div> กำลังวัดผลความแม่นยำ...
              {:else}
                📊 วัดผลความแม่นยำเทียบ Flow & Business ลูกค้า
              {/if}
            </button>

            {#if runTestSuccess === false && runTestOutput}
              <button
                type="button"
                class="btn-heal-action"
                on:click={startSelfHealing}
                disabled={isHealing}
              >
                {#if isHealing}
                  <div class="spinner-small"></div> กำลังซ่อมแซมโค้ดอัตโนมัติ...
                {:else}
                  🛠️ ซ่อมแซมสคริปต์ด้วย Agent 5 (Self-Healing & Auto-Save)
                {/if}
              </button>
            {/if}
          </div>

          <!-- BUSINESS & FLOW ACCURACY SCORECARD -->
          {#if accuracyReport}
            <div class="accuracy-scorecard" transition:slide>
              <div class="scorecard-header">
                <div>
                  <h4>📊 รายงานการวัดผลความแม่นยำของ Automate Script (Flow & Business Accuracy Scorecard)</h4>
                  <p>{accuracyReport.summary}</p>
                </div>
                <div class="scorecard-actions">
                  <button type="button" class="btn-doc-handoff" on:click={() => sendStrategyOrReportToDocCreation('accuracy')}>
                    📄 ส่งผลวัดความแม่นยำไปสร้างรายงานใน QA Doc Creation
                  </button>
                </div>
              </div>

              <!-- 4 Core Accuracy Gauges -->
              <div class="accuracy-metrics-grid">
                <div class="acc-gauge-card primary">
                  <span class="acc-label">🎯 ความแม่นยำรวม (Overall Accuracy)</span>
                  <span class="acc-score">{accuracyReport.overall_accuracy_score}%</span>
                  <div class="acc-bar"><div class="acc-fill" style="width: {accuracyReport.overall_accuracy_score}%;"></div></div>
                  <span class="acc-sub">{accuracyReport.verdict_label || 'ผ่านเกณฑ์มาตรฐาน QA'}</span>
                </div>

                <div class="acc-gauge-card">
                  <span class="acc-label">🔄 ความถูกต้องตาม Flow การทำงาน (Flow Alignment)</span>
                  <span class="acc-score">{accuracyReport.flow_alignment_score}%</span>
                  <div class="acc-bar"><div class="acc-fill" style="width: {accuracyReport.flow_alignment_score}%;"></div></div>
                  <span class="acc-sub">เทียบกับ User Journey, Test Steps & Sitemap</span>
                </div>

                <div class="acc-gauge-card">
                  <span class="acc-label">💼 ความตรงกับ Business ลูกค้า (Business Compliance)</span>
                  <span class="acc-score">{accuracyReport.business_compliance_score}%</span>
                  <div class="acc-bar"><div class="acc-fill" style="width: {accuracyReport.business_compliance_score}%;"></div></div>
                  <span class="acc-sub">เทียบกับ Expected Results & Business Rules</span>
                </div>

                <div class="acc-gauge-card">
                  <span class="acc-label">🛡️ ความแม่นยำและเสถียรของ Locator (Locator Resilience)</span>
                  <span class="acc-score">{accuracyReport.locator_resilience_score}%</span>
                  <div class="acc-bar"><div class="acc-fill" style="width: {accuracyReport.locator_resilience_score}%;"></div></div>
                  <span class="acc-sub">Playwright getByRole / getByLabel / getByTestId</span>
                </div>
              </div>

              <!-- Requirement & Test Case Business Traceability Matrix -->
              {#if accuracyReport.traceability_matrix && accuracyReport.traceability_matrix.length > 0}
                <div class="trace-matrix-section">
                  <h5>🔗 ตารางตรวจสอบความถูกต้องรายข้อ (Test Case ↔ Business Rule ↔ Script Assertion Traceability)</h5>
                  <div class="trace-table-wrap">
                    <table class="trace-table">
                      <thead>
                        <tr>
                          <th>TC / Req ID</th>
                          <th>กรณีทดสอบ (Scenario)</th>
                          <th>สิ่งที่ธุรกิจลูกค้าคาดหวัง (Business Expectation)</th>
                          <th>การตรวจสอบในสคริปต์ (Script Assertion)</th>
                          <th>ตรงตาม Flow</th>
                          <th>ตรงตาม Business</th>
                          <th>ความแม่นยำ</th>
                        </tr>
                      </thead>
                      <tbody>
                        {#each accuracyReport.traceability_matrix as row}
                          <tr>
                            <td>
                              <span class="tc-id-badge">{row.tc_id}</span>
                              <span class="req-code">{row.req_code}</span>
                            </td>
                            <td><strong>{row.scenario_title}</strong></td>
                            <td>{row.business_expectation}</td>
                            <td><code class="inline-code">{row.script_assertion}</code></td>
                            <td>
                              <span class="match-pill" class:ok={row.flow_matched}>
                                {row.flow_matched ? '✓ ตรงตาม Flow' : '⚠ ตรวจสอบ'}
                              </span>
                            </td>
                            <td>
                              <span class="match-pill" class:ok={row.business_matched}>
                                {row.business_matched ? '✓ ตรง Business' : '⚠ ตรวจสอบ'}
                              </span>
                            </td>
                            <td><strong style="color: #34d399;">{row.accuracy_percent}%</strong></td>
                          </tr>
                        {/each}
                      </tbody>
                    </table>
                  </div>
                </div>
              {/if}

              <!-- Improvement Recommendations -->
              {#if accuracyReport.improvement_recommendations && accuracyReport.improvement_recommendations.length > 0}
                <div class="acc-recommendations">
                  <strong>💡 ข้อเสนอแนะเพื่อยกระดับความแม่นยำของ Automate Test:</strong>
                  <ul>
                    {#each accuracyReport.improvement_recommendations as rec}
                      <li>{rec}</li>
                    {/each}
                  </ul>
                </div>
              {/if}
            </div>
          {/if}

          {#if runTestOutput}
            <div class="align-result" transition:slide>
              <h4>ผลลัพธ์การรันสคริปต์ (Playwright Runner Console Output)</h4>
              <div class="code-preview-container" style={runTestSuccess ? 'border-color: rgba(16, 185, 129, 0.45);' : 'border-color: rgba(239, 68, 68, 0.45);'}>
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
            <div class="align-result" transition:slide style="margin-top: 16px; border: 1px solid rgba(245, 158, 11, 0.4);">
              <h4>✨ Self-Healing สำเร็จ! อัปเดตและบันทึกสคริปต์ลงไฟล์เรียบร้อยแล้ว</h4>
              <p><strong>สาเหตุที่ตรวจพบ (Analysis):</strong> {healResult.analysis}</p>
              <p><strong>สิ่งที่แก้ไข (Fix Applied):</strong> {healResult.fix_explanation}</p>
            </div>
          {/if}
          {#if healError}
            <div class="explore-error" transition:slide>
              <p>{healError}</p>
            </div>
          {/if}
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .qa-automate-wrapper {
    width: 100%;
    height: 100%;
    overflow-y: auto;
    overflow-x: hidden;
  }

  .qa-automate-container {
    max-width: 100%;
    width: 100%;
    margin: 0;
    padding: 18px 24px 36px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 18px;
    color: var(--text-main);
  }

  .top-command-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }

  .btn-back {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 7px 14px;
    color: #cbd5e1;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    transition: all 0.2s ease;
  }

  .btn-back:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #ffffff;
  }

  .mcp-status-cluster {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .mcp-live-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 34px;
    padding: 4px 12px;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 999px;
    font-size: 12.5px;
    color: #34d399;
    font-weight: 600;
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 8px #10b981;
    flex-shrink: 0;
  }

  .mcp-tag {
    background: rgba(15, 23, 42, 0.6);
    padding: 2px 8px;
    border-radius: 999px;
    color: #a7f3d0;
    font-family: monospace;
    font-size: 11.5px;
  }

  .mcp-browser-select {
    height: 34px;
    background-color: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #e2e8f0;
    padding: 0 28px 0 10px;
    border-radius: 8px;
    font-size: 12.5px;
    cursor: pointer;
  }

  .btn-mcp-config {
    min-height: 34px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #c7d2fe;
    padding: 0 12px;
    border-radius: 8px;
    font-size: 12.5px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-mcp-config:hover {
    background: rgba(99, 102, 241, 0.25);
    color: #ffffff;
  }

  .header-title-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    flex-wrap: wrap;
  }

  h2 {
    font-size: 24px;
    font-weight: 700;
    margin: 0;
    color: var(--text-main);
  }

  .subtitle {
    color: var(--text-muted);
    font-size: 13.5px;
    margin: 4px 0 0;
  }

  .active-project-badge {
    padding: 7px 14px;
    background: rgba(139, 92, 246, 0.12);
    border-radius: 999px;
    border: 1px solid rgba(139, 92, 246, 0.35);
    font-size: 13px;
    color: #cbd5e1;
    white-space: nowrap;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .active-project-badge strong {
    color: #c4b5fd;
  }

  /* MCP Drawer */
  .mcp-drawer-card {
    margin-top: 14px;
    padding: 16px;
    background: rgba(15, 23, 42, 0.78);
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 12px;
  }

  .mcp-drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .mcp-drawer-header h4 {
    margin: 0;
    font-size: 15px;
    color: #38bdf8;
  }

  .mcp-drawer-header p {
    margin: 3px 0 0;
    font-size: 12.5px;
    color: #94a3b8;
  }

  .mcp-tools-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr));
    gap: 10px;
  }

  .mcp-tool-chip {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 12px;
    border-radius: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .mcp-tool-chip code {
    color: #34d399;
    font-size: 12px;
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .mcp-tool-chip span {
    color: #cbd5e1;
    font-size: 12px;
  }

  /* Cross-Agent Ecosystem Bar */
  .ecosystem-hub-bar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr));
    gap: 12px;
    margin-top: 14px;
  }

  .eco-card {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 12px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 8px;
  }

  .eco-card.linked {
    border-color: rgba(16, 185, 129, 0.3);
  }

  .eco-card-top {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .eco-name {
    font-size: 13.5px;
    font-weight: 600;
    color: #f1f5f9;
    flex: 1;
  }

  .eco-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #64748b;
  }

  .eco-status-dot.on {
    background: #10b981;
    box-shadow: 0 0 6px #10b981;
  }

  .eco-metric {
    font-size: 12px;
    color: #94a3b8;
    font-variant-numeric: tabular-nums;
  }

  .eco-btn-group {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .eco-link-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11.5px;
    cursor: pointer;
    align-self: flex-start;
    transition: all 0.18s ease;
  }

  .eco-link-btn:hover {
    background: rgba(99, 102, 241, 0.2);
    border-color: rgba(99, 102, 241, 0.45);
    color: #ffffff;
  }

  /* Phase Stepper */
  .phase-stepper {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
  }

  .phase-step-btn {
    flex: 1 1 auto;
    min-width: 140px;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-muted);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: center;
  }

  .phase-step-btn:hover {
    color: var(--text-main);
    background: rgba(255, 255, 255, 0.04);
  }

  .phase-step-btn.done {
    color: #34d399;
    border-color: rgba(16, 185, 129, 0.25);
  }

  .phase-step-btn.active {
    color: #ffffff;
    background: rgba(99, 102, 241, 0.22);
    border-color: rgba(99, 102, 241, 0.5);
  }

  .glass-panel {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 16px;
    padding: 22px;
    backdrop-filter: var(--glass-blur);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  }

  .glass-panel.disabled {
    opacity: 0.6;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 8px;
  }

  .header-left-cluster,
  .header-actions-cluster {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .panel-header h3 {
    margin: 0;
    font-size: 18.5px;
    color: #f1f5f9;
  }

  .badge {
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    border: 1px solid rgba(16, 185, 129, 0.35);
  }

  .badge-cyan {
    background: rgba(6, 182, 212, 0.16);
    color: #22d3ee;
    border-color: rgba(6, 182, 212, 0.35);
  }

  .badge-danger {
    background: rgba(239, 68, 68, 0.18);
    color: #f87171;
    border-color: rgba(239, 68, 68, 0.4);
  }

  .desc-text {
    color: var(--text-muted);
    font-size: 13.5px;
    margin: 0 0 18px;
    line-height: 1.55;
  }

  /* Strategy Planner Box */
  .strategy-planner-box {
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 14px;
    padding: 18px;
  }

  .strategy-box-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .strategy-box-top h4 {
    margin: 0;
    font-size: 16px;
    color: #c4b5fd;
  }

  .strategy-box-top p {
    margin: 4px 0 0;
    font-size: 12.5px;
    color: #94a3b8;
  }

  .strategy-controls {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    flex: 1;
    min-width: 0;
    justify-content: flex-end;
  }

  .strategy-focus-input {
    flex: 1;
    min-width: min(220px, 100%);
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 9px 12px;
    color: #f8fafc;
    font-size: 13px;
  }

  .btn-primary-action {
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    border: 1px solid rgba(167, 139, 250, 0.4);
    min-height: 36px;
    padding: 8px 16px;
    border-radius: 8px;
    color: #ffffff;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .btn-primary-action:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-primary-action:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary-sm {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #e2e8f0;
    min-height: 36px;
    padding: 7px 13px;
    border-radius: 8px;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: all 0.2s ease;
  }

  .btn-secondary-sm:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
  }

  .strategy-dashboard {
    margin-top: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .exec-summary-banner {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 10px;
    padding: 14px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }

  .exec-summary-text strong {
    color: #a5b4fc;
    font-size: 13.5px;
  }

  .exec-summary-text p {
    margin: 4px 0 0;
    color: #e2e8f0;
    font-size: 13px;
    line-height: 1.5;
  }

  .exec-summary-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .btn-doc-handoff {
    background: rgba(245, 158, 11, 0.16);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #fcd34d;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-next-phase {
    background: rgba(16, 185, 129, 0.2);
    border: 1px solid rgba(16, 185, 129, 0.45);
    color: #6ee7b7;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
  }

  .strategy-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(210px, 100%), 1fr));
    gap: 12px;
  }

  .strat-kpi-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    text-align: left;
    cursor: pointer;
    color: inherit;
  }

  .strat-kpi-card.must {
    border-color: rgba(16, 185, 129, 0.35);
    background: rgba(16, 185, 129, 0.05);
  }

  .strat-kpi-card.selective {
    border-color: rgba(245, 158, 11, 0.35);
    background: rgba(245, 158, 11, 0.05);
  }

  .strat-kpi-card.manual {
    border-color: rgba(148, 163, 184, 0.25);
    background: rgba(148, 163, 184, 0.04);
  }

  .strat-kpi-card.roi {
    border-color: rgba(56, 189, 248, 0.35);
    background: rgba(56, 189, 248, 0.05);
    cursor: default;
  }

  .strat-kpi-card.active {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(99, 102, 241, 0.5);
  }

  .kpi-title {
    font-size: 12px;
    color: #cbd5e1;
    font-weight: 600;
  }

  .kpi-num {
    font-size: 20px;
    font-weight: 700;
    color: #f8fafc;
    font-variant-numeric: tabular-nums;
  }

  .kpi-sub {
    font-size: 11.5px;
    color: #94a3b8;
  }

  .roadmap-section h5,
  .eval-list-header h5 {
    margin: 0 0 10px;
    font-size: 14px;
    color: #e2e8f0;
  }

  .roadmap-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(250px, 100%), 1fr));
    gap: 12px;
  }

  .roadmap-card {
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
  }

  .roadmap-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .phase-pill {
    background: rgba(56, 189, 248, 0.16);
    color: #38bdf8;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
  }

  .roadmap-goal {
    margin: 0 0 8px;
    font-size: 12.5px;
    color: #cbd5e1;
  }

  .roadmap-meta {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 11.5px;
    color: #94a3b8;
  }

  .eval-list-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .filter-pills {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .pill-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 5px 10px;
    border-radius: 999px;
    font-size: 12px;
    cursor: pointer;
  }

  .pill-btn.active {
    background: rgba(99, 102, 241, 0.25);
    border-color: rgba(99, 102, 241, 0.55);
    color: #ffffff;
  }

  .eval-cards-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 520px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .eval-item-card {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px;
  }

  .eval-item-card.decision-must_automate {
    border-color: rgba(16, 185, 129, 0.35);
    background: rgba(15, 23, 42, 0.82);
  }

  .eval-item-card.decision-selective {
    border-color: rgba(245, 158, 11, 0.35);
    background: rgba(15, 23, 42, 0.82);
  }

  .eval-item-card.decision-manual_only {
    border-color: rgba(100, 116, 139, 0.3);
    opacity: 0.9;
  }

  .eval-item-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  .eval-checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 14px;
    color: #f8fafc;
  }

  .eval-badges {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .priority-tag {
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 700;
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
  }

  .priority-tag.prio-p1 {
    background: rgba(245, 158, 11, 0.2);
    color: #fcd34d;
  }

  .priority-tag.prio-p2,
  .priority-tag.prio-p3 {
    background: rgba(148, 163, 184, 0.2);
    color: #cbd5e1;
  }

  .roi-tag {
    background: rgba(56, 189, 248, 0.16);
    color: #7dd3fc;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .decision-badge {
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
  }

  .decision-badge.dec-must_automate {
    background: rgba(16, 185, 129, 0.2);
    color: #6ee7b7;
  }

  .decision-badge.dec-selective {
    background: rgba(245, 158, 11, 0.2);
    color: #fde68a;
  }

  .decision-badge.dec-manual_only {
    background: rgba(148, 163, 184, 0.18);
    color: #cbd5e1;
  }

  .eval-why {
    margin: 0 0 10px;
    font-size: 13px;
    color: #cbd5e1;
    line-height: 1.5;
  }

  .pros-cons-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .pros-cons-grid > div {
    min-width: 0;
  }

  .pros-box,
  .cons-box {
    background: rgba(255, 255, 255, 0.025);
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 12.5px;
  }

  .pros-box strong {
    color: #34d399;
  }

  .cons-box strong {
    color: #fbbf24;
  }

  .pros-box ul,
  .cons-box ul {
    margin: 6px 0 0;
    padding-left: 18px;
    color: #cbd5e1;
    line-height: 1.45;
  }

  .eval-approach {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px dashed rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 12.5px;
    color: #93c5fd;
  }

  .test-type-chips {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .tt-chip {
    background: rgba(99, 102, 241, 0.16);
    color: #c7d2fe;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
  }

  /* Phase 2 Dual-Source Styles */
  .mode-selector-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(250px, 100%), 1fr));
    gap: 12px;
    margin-bottom: 18px;
  }

  .mode-card-btn {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 12px;
    padding: 14px 16px;
    text-align: left;
    color: inherit;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .mode-card-btn.active {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(99, 102, 241, 0.55);
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.15);
  }

  .mode-card-title {
    font-size: 14px;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 6px;
  }

  .mode-card-btn p {
    margin: 0;
    font-size: 12.5px;
    color: #94a3b8;
    line-height: 1.45;
  }

  .sub-panel-box {
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 18px;
  }

  .mcp-web-box {
    border-color: rgba(56, 189, 248, 0.3);
  }

  .sub-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    flex-wrap: wrap;
    margin-bottom: 14px;
  }

  .sub-panel-header h4 {
    margin: 0;
    font-size: 16px;
    color: #f1f5f9;
  }

  .sub-panel-header p {
    margin: 4px 0 0;
    font-size: 12.5px;
    color: #94a3b8;
  }

  .sub-panel-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .add-tc-form {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(139, 92, 246, 0.35);
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 14px;
  }

  .add-tc-form h5 {
    margin: 0 0 10px;
    color: #c4b5fd;
  }

  .tc-form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
    gap: 8px;
  }

  .tc-form-grid input.url-input,
  .tc-form-grid select.url-input {
    height: 38px;
    border-radius: 8px;
    font-size: 13px;
    border: 1px solid var(--glass-border);
    background-color: rgba(15, 23, 42, 0.7);
    color: #ffffff;
  }

  .tc-form-grid select.url-input {
    padding: 0 32px 0 12px;
  }

  .tc-filter-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 14px;
  }

  .tc-cards-grid {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 440px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .tc-item-card {
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
  }

  .tc-item-card.selected {
    border-color: rgba(99, 102, 241, 0.45);
    background: rgba(99, 102, 241, 0.06);
  }

  .tc-item-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  .tc-check-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    font-size: 13.5px;
    color: #f8fafc;
  }

  .tc-id-badge {
    background: rgba(56, 189, 248, 0.18);
    color: #7dd3fc;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
    font-family: monospace;
  }

  .tc-tags {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }

  .tc-type-badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    background: rgba(16, 185, 129, 0.18);
    color: #6ee7b7;
  }

  .tc-type-badge.type-negative {
    background: rgba(245, 158, 11, 0.2);
    color: #fcd34d;
  }

  .tc-src-tag {
    font-size: 11px;
    color: #94a3b8;
    background: rgba(255, 255, 255, 0.05);
    padding: 2px 8px;
    border-radius: 6px;
  }

  .tc-details-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    font-size: 12.5px;
    color: #cbd5e1;
  }

  .tc-details-grid > div {
    min-width: 0;
  }

  .tc-steps-ol {
    margin: 4px 0 0;
    padding-left: 18px;
    line-height: 1.5;
  }

  .biz-rule-highlight {
    margin: 4px 0 0;
    color: #a5b4fc;
    background: rgba(99, 102, 241, 0.1);
    padding: 6px 10px;
    border-radius: 6px;
  }

  /* MCP Live Web Play Timeline & Screenshot */
  .mcp-form-row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  .mcp-evidence-split {
    display: grid;
    grid-template-columns: 1.4fr 1fr;
    gap: 16px;
    margin-top: 14px;
  }

  .mcp-evidence-split.single-col {
    grid-template-columns: 1fr;
  }

  .recorded-timeline-box,
  .mcp-screenshot-box {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px;
    min-width: 0;
  }

  .recorded-timeline-box h5,
  .mcp-screenshot-box h5 {
    margin: 0 0 10px;
    font-size: 13.5px;
    color: #e2e8f0;
  }

  .recorded-steps-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 320px;
    overflow-y: auto;
  }

  .recorded-step-item {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 8px 10px;
  }

  .rec-step-badge {
    background: rgba(16, 185, 129, 0.2);
    color: #34d399;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
    white-space: nowrap;
  }

  .rec-step-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
    flex: 1;
    min-width: 0;
  }

  .rec-step-top {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    font-size: 12.5px;
  }

  .mcp-tool-tag {
    background: rgba(56, 189, 248, 0.16);
    color: #38bdf8;
    font-family: monospace;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 4px;
  }

  .rec-pw-code {
    font-family: monospace;
    font-size: 11.5px;
    color: #a5b4fc;
    background: rgba(0, 0, 0, 0.35);
    padding: 4px 8px;
    border-radius: 5px;
    display: block;
    overflow-x: auto;
  }

  .mcp-shot-img {
    width: 100%;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    object-fit: cover;
  }

  /* Phase 4 & 5 Script Editor & Accuracy Scorecard */
  .gen-mode-bar {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 12px 16px;
    border-radius: 10px;
  }

  .gen-radio {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #e2e8f0;
    cursor: pointer;
  }

  .suite-mini-scores {
    display: flex;
    gap: 10px;
    font-size: 11.5px;
    color: #94a3b8;
    margin-top: 6px;
    font-variant-numeric: tabular-nums;
  }

  .suite-mini-scores strong {
    color: #34d399;
  }

  .suite-editor-box {
    margin-top: 14px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 10px;
    overflow: hidden;
  }

  .suite-editor-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 10px 14px;
    background: rgba(30, 41, 59, 0.8);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .code-editor-textarea {
    width: 100%;
    box-sizing: border-box;
    background: #090d16;
    color: #e2e8f0;
    border: none;
    padding: 14px;
    font-family: 'Fira Code', Consolas, monospace;
    font-size: 12.5px;
    line-height: 1.55;
    resize: vertical;
  }

  .code-editor-textarea:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: -2px;
  }

  .execution-action-bar {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }

  .btn-heal-action {
    background: linear-gradient(90deg, #f59e0b, #ef4444);
    border: none;
    color: #ffffff;
    min-height: 36px;
    padding: 8px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
  }

  .accuracy-scorecard {
    background: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 18px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .scorecard-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    flex-wrap: wrap;
  }

  .scorecard-header h4 {
    margin: 0;
    font-size: 16px;
    color: #34d399;
  }

  .scorecard-header p {
    margin: 4px 0 0;
    font-size: 13px;
    color: #cbd5e1;
  }

  .accuracy-metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(210px, 100%), 1fr));
    gap: 12px;
  }

  .acc-gauge-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .acc-gauge-card.primary {
    border-color: rgba(16, 185, 129, 0.45);
    background: rgba(16, 185, 129, 0.06);
  }

  .acc-label {
    font-size: 12px;
    color: #cbd5e1;
    font-weight: 600;
  }

  .acc-score {
    font-size: 24px;
    font-weight: 800;
    color: #34d399;
    font-variant-numeric: tabular-nums;
  }

  .acc-bar {
    height: 6px;
    background: rgba(255, 255, 255, 0.08);
    border-radius: 999px;
    overflow: hidden;
  }

  .acc-fill {
    height: 100%;
    background: linear-gradient(90deg, #10b981, #38bdf8);
    border-radius: 999px;
  }

  .acc-sub {
    font-size: 11.5px;
    color: #94a3b8;
  }

  .trace-matrix-section h5 {
    margin: 0 0 10px;
    font-size: 14px;
    color: #f1f5f9;
  }

  .trace-table-wrap {
    overflow-x: auto;
    min-width: 0;
  }

  .trace-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
  }

  .trace-table th,
  .trace-table td {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    text-align: left;
  }

  .trace-table th {
    background: rgba(30, 41, 59, 0.7);
    color: #94a3b8;
    font-weight: 600;
  }

  .inline-code {
    font-family: monospace;
    font-size: 11.5px;
    color: #a5b4fc;
    background: rgba(0, 0, 0, 0.3);
    padding: 2px 6px;
    border-radius: 4px;
  }

  .match-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    background: rgba(245, 158, 11, 0.16);
    color: #fcd34d;
  }

  .match-pill.ok {
    background: rgba(16, 185, 129, 0.18);
    color: #6ee7b7;
  }

  .acc-recommendations {
    background: rgba(56, 189, 248, 0.08);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 12.5px;
    color: #e2e8f0;
  }

  .acc-recommendations ul {
    margin: 6px 0 0;
    padding-left: 20px;
  }

  /* Shared existing cards & utilities */
  .empty-state,
  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 32px;
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.02);
    border-radius: 12px;
    border: 1px dashed rgba(255, 255, 255, 0.1);
    gap: 10px;
  }

  .spinner {
    width: 28px;
    height: 28px;
    border: 3px solid rgba(255, 255, 255, 0.1);
    border-top-color: #a78bfa;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    100% {
      transform: rotate(360deg);
    }
  }

  .req-toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .search-box {
    flex: 1;
    min-width: 220px;
    display: flex;
  }

  .requirements-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .req-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    overflow: hidden;
  }

  .req-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding: 12px 16px;
    cursor: pointer;
  }

  .req-header:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: -2px;
  }

  .req-title {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .req-code {
    background: rgba(167, 139, 250, 0.2);
    color: #c4b5fd;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    font-family: monospace;
  }

  .req-title h4 {
    margin: 0;
    font-size: 14.5px;
    font-weight: 600;
  }

  .req-doc-chip {
    font-size: 11.5px;
    color: #93c5fd;
    background: rgba(59, 130, 246, 0.12);
    padding: 2px 8px;
    border-radius: 999px;
  }

  .status-badge {
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11.5px;
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
  }

  .req-body {
    padding: 12px 16px 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 13px;
    color: #cbd5e1;
  }

  .req-lists {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-top: 10px;
  }

  .req-lists > .list-box {
    min-width: 0;
  }

  .list-box {
    background: rgba(0, 0, 0, 0.22);
    padding: 12px;
    border-radius: 8px;
  }

  .list-box ul {
    margin: 6px 0 0;
    padding-left: 18px;
  }

  .url-input,
  .search-input {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 10px 14px;
    color: #ffffff;
    font-size: 13px;
  }

  .search-input {
    width: 100%;
  }

  .url-input:focus,
  .search-input:focus {
    border-color: #a78bfa;
  }

  .url-input:focus-visible,
  .search-input:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
    border-color: #a78bfa;
  }

  .explore-result,
  .align-result {
    margin-top: 18px;
    padding: 18px;
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(16, 185, 129, 0.28);
    border-radius: 12px;
  }

  /* Phase 3 Alignment Report Styles */
  .align-result h4 {
    margin: 0 0 12px;
    font-size: 15.5px;
    color: #f8fafc;
  }

  .align-summary {
    background: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(99, 102, 241, 0.28);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 14px;
    font-size: 13.5px;
    color: #e2e8f0;
    line-height: 1.55;
  }

  .align-summary p {
    margin: 0;
  }

  .matched-elements-box {
    background: rgba(16, 185, 129, 0.07);
    border: 1px solid rgba(16, 185, 129, 0.28);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 14px;
    font-size: 13px;
    color: #cbd5e1;
  }

  .align-issues {
    background: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 14px;
  }

  .align-issues strong {
    display: block;
    color: #fbbf24;
    font-size: 13.5px;
    margin-bottom: 8px;
  }

  .align-issues ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .issue-item {
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.03);
    font-size: 13px;
    color: #e2e8f0;
    line-height: 1.5;
  }

  .issue-item.severity-low {
    background: rgba(56, 189, 248, 0.08);
    border-color: rgba(56, 189, 248, 0.3);
    color: #e0f2fe;
  }

  .issue-item.severity-medium {
    background: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.35);
    color: #fef3c7;
  }

  .issue-item.severity-high {
    background: rgba(244, 63, 94, 0.12);
    border-color: rgba(244, 63, 94, 0.4);
    color: #ffe4e6;
  }

  .issue-req {
    display: inline-block;
    font-family: monospace;
    font-size: 11.5px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 4px;
    margin-right: 6px;
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #c4b5fd;
  }

  .no-issue {
    margin: 0;
    padding: 10px 12px;
    border-radius: 8px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: #6ee7b7;
    font-size: 13px;
  }

  .align-recommendation {
    background: rgba(56, 189, 248, 0.08);
    border: 1px solid rgba(56, 189, 248, 0.28);
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 13px;
    color: #e2e8f0;
    line-height: 1.55;
  }

  .align-recommendation p {
    margin: 0;
  }

  .align-recommendation strong {
    color: #7dd3fc;
  }

  .result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 14px;
  }

  .status-title {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .check-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    background: #10b981;
    color: #042f2e;
    font-weight: 700;
    border-radius: 50%;
    font-size: 13px;
  }

  .saved-tag {
    font-family: monospace;
    font-size: 12px;
    color: #a78bfa;
    background: rgba(167, 139, 250, 0.12);
    padding: 4px 10px;
    border-radius: 6px;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(160px, 100%), 1fr));
    gap: 12px;
  }

  .metric-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 10px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .metric-label {
    font-size: 12px;
    color: #94a3b8;
  }

  .metric-value {
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
    font-variant-numeric: tabular-nums;
  }

  .highlight-green { color: #34d399; }
  .highlight-blue { color: #38bdf8; }
  .highlight-purple { color: #c084fc; }

  .project-resources-box {
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 12px;
    padding: 14px 16px;
  }

  .doc-count-badge {
    background: rgba(59, 130, 246, 0.18);
    color: #93c5fd;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 999px;
  }

  .doc-chips-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
  }

  .doc-chip-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 8px;
    color: #cbd5e1;
    font-size: 12.5px;
    cursor: pointer;
    max-width: 100%;
  }

  .doc-chip-btn.active {
    background: rgba(59, 130, 246, 0.2);
    border-color: #60a5fa;
    color: #ffffff;
  }

  .doc-name {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .doc-type-tag {
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(148, 163, 184, 0.2);
    flex-shrink: 0;
  }

  .doc-req-count {
    font-size: 11px;
    padding: 1px 7px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.6);
    flex-shrink: 0;
  }

  .doc-req-count.has-reqs {
    color: #34d399;
  }

  .suite-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(250px, 100%), 1fr));
    gap: 12px;
  }

  .suite-card {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 14px;
    cursor: pointer;
    min-width: 0;
  }

  .suite-card:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }

  .suite-card.active {
    background: rgba(99, 102, 241, 0.18);
    border-color: #818cf8;
  }

  .suite-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 6px;
  }

  .test-count {
    background: rgba(16, 185, 129, 0.2);
    color: #34d399;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11.5px;
    flex-shrink: 0;
  }

  .suite-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    font-size: 12px;
    color: #94a3b8;
  }

  .code-preview-container {
    margin-top: 12px;
    background: #090d16;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 14px;
    max-height: 360px;
    overflow-y: auto;
    overflow-x: auto;
  }

  .code-preview {
    margin: 0;
    font-family: monospace;
    font-size: 12.5px;
    color: #e2e8f0;
    white-space: pre-wrap;
  }

  .explore-error {
    margin-top: 14px;
    padding: 12px 16px;
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 8px;
    color: #fca5a5;
    font-size: 13px;
  }

  @media (max-width: 900px) {
    .qa-automate-container {
      padding: 14px 16px 28px;
    }

    .glass-panel {
      padding: 16px;
    }

    .pros-cons-grid,
    .tc-details-grid,
    .mcp-evidence-split,
    .req-lists {
      grid-template-columns: 1fr;
    }

    .strategy-controls {
      width: 100%;
      justify-content: stretch;
    }
  }

  @media (max-width: 640px) {
    .qa-automate-container {
      padding: 12px 12px 24px;
      gap: 14px;
    }

    .glass-panel {
      padding: 14px;
      border-radius: 12px;
    }

    h2 {
      font-size: 20px;
    }

    .panel-header h3 {
      font-size: 16px;
    }

    .btn-primary-action {
      white-space: normal;
      text-align: center;
      line-height: 1.35;
    }

    .mcp-form-row {
      flex-direction: column;
    }

    .mcp-form-row .url-input {
      width: 100%;
    }

    .search-box {
      min-width: 0;
      width: 100%;
    }

    .doc-name {
      max-width: 150px;
    }
  }
</style>
