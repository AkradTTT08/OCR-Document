<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { fade, fly, slide, scale } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { selectedProjectStore } from './qaHistoryStore.js';
  import { toast } from './toastStore.js';
  import ProjectSelection from './ProjectSelection.svelte';
  import SmartTestLauncherModal from './SmartTestLauncherModal.svelte';
  import QAIcon from './QAIcon.svelte';
  import TraceabilityMatrixPane from './TraceabilityMatrixPane.svelte';
  import { sanitizeMermaidCode, mermaidThemeVariables } from './qaMermaid.js';
  import mermaid from 'mermaid';

  let projects = [];
  let isAnalyzing = false;
  let activeTab = 'sitemap'; // 'sitemap' | 'flowchart' | 'usecase' | 'activity' | 'sequence' | 'matrix'
  let customInstructions = "";
  let showInstructions = false;

  // Live Mermaid Code Editor state
  let showMermaidEditor = false;
  let editableMermaidCode = "";
  let isSavingDiagram = false;

  let isTestModalOpen = false;
  let testTargetCard = null;

  let flowData = null;
  let selectedScreenId = null;
  let selectedSitemapNode = null;
  let selectedNodeId = null;

  // Wireframe / Mockup Source Modes: 'stitch' | 'ai' | 'figma' | 'image'
  let activeWireframeTab = 'ai';
  let figmaUrlInput = '';
  let figmaTokenInput = localStorage.getItem('figma_token') || '';
  let showFigmaTokenInput = false;
  let isSyncingFigma = false;
  let isUploadingImage = false;
  let fileInputRef = null;
  let lightboxImage = null;

  // Google Stitch MCP + Gemini Live HTML UI Generator state
  let stitchPromptInput = '';
  let stitchEngine = 'auto'; // 'auto' | 'stitch' | 'gemini'
  let stitchApiKeyInput = localStorage.getItem('stitch_api_key') || '';
  let showStitchKeyInput = false;
  let showStitchCodeInspector = false;
  let isGeneratingStitch = false;
  let isSavingStitchKey = false;


  // Diagram zoom/pan state
  let diagramContainer;
  let canvasPanelRef;
  let zoomLevel = 1;
  let panX = 0;
  let panY = 0;
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let startPanX = 0;
  let startPanY = 0;

  onDestroy(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerUp);
      window.removeEventListener('blur', onPointerUp);
    }
  });

  // Reactive update when current selected screen changes
  $: if (currentScreenMockup) {
    activeWireframeTab = currentScreenMockup.wireframe_type || (currentScreenMockup.stitch_html ? 'stitch' : (currentScreenMockup.image_url ? 'image' : (currentScreenMockup.figma_url ? 'figma' : 'ai')));
    figmaUrlInput = currentScreenMockup.figma_url || '';
  }

  function getFigmaEmbedUrl(url) {
    if (!url) return '';
    return `https://www.figma.com/embed?embed_host=spectra_qa&url=${encodeURIComponent(url.trim())}`;
  }

  async function handleSwitchWireframeTab(mode) {
    activeWireframeTab = mode;
    if (!currentScreenMockup || !$selectedProjectStore) return;
    
    currentScreenMockup.wireframe_type = mode;
    try {
      await fetch('/api/agent/update_screen_wireframe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
          screen_id: currentScreenMockup.screen_id,
          wireframe_type: mode
        })
      });
    } catch(e) {
      console.error(e);
    }
  }

  async function handleSaveFigmaUrl() {
    if (!currentScreenMockup || !$selectedProjectStore) return;
    if (!figmaUrlInput.trim()) {
      toast('กรุณาระบุ URL ของ Figma Frame หรือ Design', 'warning');
      return;
    }
    
    if (figmaTokenInput.trim()) {
      localStorage.setItem('figma_token', figmaTokenInput.trim());
    }

    currentScreenMockup.figma_url = figmaUrlInput.trim();
    currentScreenMockup.wireframe_type = 'figma';
    activeWireframeTab = 'figma';

    try {
      const res = await fetch('/api/agent/update_screen_wireframe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
          screen_id: currentScreenMockup.screen_id,
          wireframe_type: 'figma',
          figma_url: figmaUrlInput.trim()
        })
      });
      if (res.ok) {
        toast('เชื่อมต่อ Figma Frame สำเร็จ!', 'success');
        flowData = { ...flowData };
      }
    } catch(e) {
      console.error(e);
      toast('ไม่สามารถบันทึก Figma URL ได้', 'error');
    }
  }

  async function handleSyncFigmaImage() {
    if (!figmaUrlInput.trim()) {
      toast('กรุณาระบุ Figma URL ก่อนกด Sync', 'warning');
      return;
    }
    isSyncingFigma = true;
    try {
      const res = await fetch('/api/agent/figma/sync_frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
          screen_id: currentScreenMockup.screen_id,
          figma_url: figmaUrlInput.trim(),
          figma_token: figmaTokenInput.trim()
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('เชื่อมต่อและดึงข้อมูล Figma สำเร็จ!', 'success');
        if (data.synced_image_url) {
          currentScreenMockup.image_url = data.synced_image_url;
        }
        currentScreenMockup.wireframe_type = 'figma';
        flowData = { ...flowData };
      } else {
        toast(data.error || 'ไม่สามารถ Sync จาก Figma API ได้ (แสดงผลแบบ Live Embed แทน)', 'warning');
      }
    } catch(e) {
      console.error(e);
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ Figma API', 'error');
    } finally {
      isSyncingFigma = false;
    }
  }

  async function handleFileUpload(event) {
    const file = event.target.files?.[0];
    if (!file || !currentScreenMockup || !$selectedProjectStore) return;
    
    isUploadingImage = true;
    try {
      const formData = new FormData();
      formData.append('project_id', $selectedProjectStore.id || $selectedProjectStore.project_id);
      formData.append('screen_id', currentScreenMockup.screen_id);
      formData.append('file', file);

      const res = await fetch('/api/agent/upload_wireframe_image', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('อัปโหลดรูปภาพ Wireframe สำเร็จ!', 'success');
        currentScreenMockup.image_url = data.image_url;
        currentScreenMockup.image_filename = file.name;
        currentScreenMockup.wireframe_type = 'image';
        activeWireframeTab = 'image';
        flowData = { ...flowData };
      } else {
        toast(data.error || 'อัปโหลดรูปภาพไม่สำเร็จ', 'error');
      }
    } catch(e) {
      console.error(e);
      toast('Network error during image upload', 'error');
    } finally {
      isUploadingImage = false;
      if (fileInputRef) fileInputRef.value = '';
    }
  }

  async function handleRemoveImage() {
    if (!currentScreenMockup || !$selectedProjectStore) return;
    currentScreenMockup.image_url = null;
    currentScreenMockup.image_filename = null;
    currentScreenMockup.wireframe_type = 'ai';
    activeWireframeTab = 'ai';
    try {
      await fetch('/api/agent/update_screen_wireframe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
          screen_id: currentScreenMockup.screen_id,
          wireframe_type: 'ai',
          image_url: ''
        })
      });
      toast('ลบรูปภาพ Mockup เรียบร้อย', 'info');
      flowData = { ...flowData };
    } catch(e) {
      console.error(e);
    }
  }

  async function handleSaveStitchKey() {
    if (!stitchApiKeyInput.trim()) {
      toast('กรุณาวาง Stitch API Key ก่อนกดบันทึก', 'warning');
      return;
    }
    isSavingStitchKey = true;
    try {
      localStorage.setItem('stitch_api_key', stitchApiKeyInput.trim());
      const res = await fetch('/api/agent/stitch/save_key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stitch_api_key: stitchApiKeyInput.trim() })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.stitch_status || 'บันทึก Stitch API Key สำเร็จ', data.stitch_verified ? 'success' : 'info');
        if (data.stitch_verified) showStitchKeyInput = false;
      } else {
        toast(data.error || 'ไม่สามารถบันทึก Stitch API Key ได้', 'error');
      }
    } catch (e) {
      console.error(e);
      toast('เกิดข้อผิดพลาดในการบันทึก Stitch API Key', 'error');
    } finally {
      isSavingStitchKey = false;
    }
  }

  async function handleGenerateStitchScreen() {
    if (!currentScreenMockup || !$selectedProjectStore) return;
    isGeneratingStitch = true;
    try {
      const deviceMap = { desktop: 'DESKTOP', tablet: 'TABLET', mobile: 'MOBILE' };
      const res = await fetch('/api/agent/stitch/generate_screen', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
          screen_id: currentScreenMockup.screen_id,
          device_type: deviceMap[prototypeDevice] || 'DESKTOP',
          custom_prompt: stitchPromptInput.trim(),
          engine: stitchEngine,
          stitch_api_key: stitchApiKeyInput.trim()
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        currentScreenMockup.stitch_html = data.stitch_html;
        currentScreenMockup.stitch_screen_id = data.stitch_screen_id;
        currentScreenMockup.stitch_project_id = data.stitch_project_id;
        currentScreenMockup.stitch_engine = data.stitch_engine;
        currentScreenMockup.stitch_device = data.stitch_device;
        currentScreenMockup.stitch_updated_at = data.stitch_updated_at;
        currentScreenMockup.wireframe_type = 'stitch';
        if (data.image_url) {
          currentScreenMockup.image_url = data.image_url;
        }
        activeWireframeTab = 'stitch';
        flowData = { ...flowData };
        const engineLabel = data.stitch_engine === 'google_stitch_mcp' ? 'Google Stitch MCP' : 'Gemini Live HTML/Tailwind';
        toast(`สร้าง High-Fi UI สำหรับ ${currentScreenMockup.screen_id} ด้วย ${engineLabel} สำเร็จ!`, 'success');
      } else {
        toast(data.error || 'ไม่สามารถสร้าง High-Fi UI ได้', 'error');
      }
    } catch (e) {
      console.error(e);
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อระบบสร้าง UI', 'error');
    } finally {
      isGeneratingStitch = false;
    }
  }

  function copyStitchHtml() {
    if (!currentScreenMockup?.stitch_html) return;
    navigator.clipboard.writeText(currentScreenMockup.stitch_html);
    toast('คัดลอกโค้ด HTML/Tailwind เรียบร้อยแล้ว', 'success');
  }

  function downloadStitchHtml() {
    if (!currentScreenMockup?.stitch_html) return;
    const blob = new Blob([currentScreenMockup.stitch_html], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(currentScreenMockup.screen_id || 'screen').toLowerCase()}_ui.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('ดาวน์โหลดไฟล์ HTML สำเร็จ', 'success');
  }

  let lastLoadedProjectId = null;

  $: {
    const currentPId = $selectedProjectStore ? ($selectedProjectStore.id || $selectedProjectStore.project_id) : null;
    if (currentPId && currentPId !== lastLoadedProjectId) {
      lastLoadedProjectId = currentPId;
      selectedScreenId = null;
      selectedNodeId = null;
      selectedSitemapNode = null;
      flowData = null;
      fetchAnalysis(currentPId);
    } else if (!currentPId) {
      lastLoadedProjectId = null;
      flowData = null;
    }
  }

  onMount(async () => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
      fontFamily: "'Prompt', 'Outfit', 'Segoe UI', sans-serif",
      themeVariables: mermaidThemeVariables
    });
    await fetchProjects();
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

  async function fetchAnalysis(projectId) {
    if (!projectId) return;
    try {
      const res = await fetch(`/api/agent/flow_analysis?project_id=${projectId}`);
      const data = await res.json();
      if (data.success && data.analysis) {
        flowData = data.analysis;
        if (flowData.screen_mockups && flowData.screen_mockups.length > 0 && !selectedScreenId) {
          selectedScreenId = flowData.screen_mockups[0].screen_id;
          selectedNodeId = flowData.screen_mockups[0].screen_id;
        }
      } else {
        flowData = null;
      }
    } catch (e) {
      console.error('Failed to fetch flow analysis:', e);
    }
  }

  async function handleGenerateAnalysis() {
    if (!$selectedProjectStore) {
      toast('กรุณาเลือกโครงการก่อนเริ่มการวิเคราะห์', 'warning');
      return;
    }

    isAnalyzing = true;
    try {
      const payload = {
        project_id: $selectedProjectStore.id || $selectedProjectStore.project_id,
        custom_instructions: customInstructions.trim()
      };

      const res = await fetch('/api/agent/generate_flow_analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (res.ok && data.success) {
        toast('วิเคราะห์และสร้าง QA Flow Diagrams สำเร็จ!', 'success');
        flowData = data.analysis;
        if (flowData.screen_mockups && flowData.screen_mockups.length > 0) {
          selectedScreenId = flowData.screen_mockups[0].screen_id;
          selectedNodeId = flowData.screen_mockups[0].screen_id;
        }
      } else {
        toast(data.error || 'ไม่สามารถวิเคราะห์ Flow ได้', 'error');
      }
    } catch (e) {
      console.error(e);
      toast('Network error during flow analysis.', 'error');
    } finally {
      isAnalyzing = false;
    }
  }

  let showDrawioGrid = true;
  let isFullscreenDiagram = false;

  function getActiveDiagramCode() {
    if (activeTab === 'flowchart') return flowData?.system_flowchart || flowData?.activity_diagram || '';
    if (activeTab === 'usecase') return flowData?.usecase_diagram || '';
    if (activeTab === 'activity') return flowData?.activity_diagram || '';
    if (activeTab === 'sequence') return flowData?.sequence_diagram || '';
    return '';
  }

  function copyCurrentMermaidCode() {
    const code = getActiveDiagramCode();
    if (!code) return;
    navigator.clipboard.writeText(code);
    toast('คัดลอกโค้ด Mermaid Diagram เรียบร้อย', 'success');
  }

  function toggleMermaidEditor() {
    if (!showMermaidEditor) {
      editableMermaidCode = getActiveDiagramCode();
      showMermaidEditor = true;
    } else {
      showMermaidEditor = false;
    }
  }

  $: if (activeTab) {
    showMermaidEditor = false;
  }

  function formatUpdatedAt(ts) {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return String(ts);
      return d.toLocaleString('th-TH', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return String(ts);
    }
  }

  async function saveEditedDiagram() {
    if (!flowData || !$selectedProjectStore || isSavingDiagram) return;
    isSavingDiagram = true;
    try {
      const updated = { ...flowData };
      if (activeTab === 'flowchart') updated.system_flowchart = editableMermaidCode;
      else if (activeTab === 'usecase') updated.usecase_diagram = editableMermaidCode;
      else if (activeTab === 'activity') updated.activity_diagram = editableMermaidCode;
      else if (activeTab === 'sequence') updated.sequence_diagram = editableMermaidCode;

      const pId = $selectedProjectStore.id || $selectedProjectStore.project_id;
      const res = await fetch('/api/agent/save_flow_analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pId,
          sitemap: updated.sitemap || [],
          system_flowchart: updated.system_flowchart || '',
          usecase_diagram: updated.usecase_diagram || '',
          activity_diagram: updated.activity_diagram || '',
          sequence_diagram: updated.sequence_diagram || '',
          screen_mockups: updated.screen_mockups || [],
          traceability_matrix: updated.traceability_matrix || [],
          summary_stats: updated.summary_stats || {}
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        updated.updated_at = new Date().toISOString();
        flowData = updated;
        showMermaidEditor = false;
        toast('บันทึกการแก้ไข Diagram ลงฐานข้อมูลโครงการแล้ว (ซิงค์กับ Agent ทุกตัวอัตโนมัติ)', 'success', 4000);
      } else {
        throw new Error(data.error || 'ไม่สามารถบันทึก Diagram ได้');
      }
    } catch (err) {
      console.error('Save diagram error:', err);
      toast('เกิดข้อผิดพลาดในการบันทึก: ' + err.message, 'error');
    } finally {
      isSavingDiagram = false;
    }
  }

  // Modal focus management: move focus into dialog on open, restore to trigger on close, trap Tab inside
  function modalFocus(node) {
    const previouslyFocused = typeof document !== 'undefined' ? document.activeElement : null;
    const focusableSelector = 'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

    tick().then(() => {
      const first = node.querySelector(focusableSelector);
      (first || node).focus?.();
    });

    function trapTab(e) {
      if (e.key !== 'Tab') return;
      const items = Array.from(node.querySelectorAll(focusableSelector));
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    node.addEventListener('keydown', trapTab);
    return {
      destroy() {
        node.removeEventListener('keydown', trapTab);
        if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
      }
    };
  }

  const TAB_ORDER = ['sitemap', 'flowchart', 'usecase', 'activity', 'sequence', 'matrix'];
  async function handleTabsKeydown(e) {
    const keys = ['ArrowRight', 'ArrowLeft', 'Home', 'End'];
    if (!keys.includes(e.key)) return;
    e.preventDefault();
    let idx = TAB_ORDER.indexOf(activeTab);
    if (e.key === 'ArrowRight') idx = (idx + 1) % TAB_ORDER.length;
    else if (e.key === 'ArrowLeft') idx = (idx - 1 + TAB_ORDER.length) % TAB_ORDER.length;
    else if (e.key === 'Home') idx = 0;
    else if (e.key === 'End') idx = TAB_ORDER.length - 1;
    activeTab = TAB_ORDER[idx];
    await tick();
    document.getElementById('qa-tab-' + activeTab)?.focus();
  }

  $: liveMessage = isAnalyzing
    ? 'กำลังวิเคราะห์ Flow และ Diagram'
    : isSavingDiagram
      ? 'กำลังบันทึก Diagram'
      : '';

  function handleDiagramKeydown(e) {
    if (e.key === 'Escape') {
      if (lightboxImage) { lightboxImage = null; return; }
      if (activePrototypeModal) { activePrototypeModal = null; return; }
      if (showMermaidEditor) { showMermaidEditor = false; return; }
      if (isFullscreenDiagram) { isFullscreenDiagram = false; setTimeout(fitView, 160); return; }
    }
  }

  function exportDiagramSVG() {
    if (!diagramContainer) return;
    const svgEl = diagramContainer.querySelector('svg');
    if (!svgEl) {
      toast('ไม่พบข้อมูล SVG สำหรับ Export', 'warning');
      return;
    }
    const svgData = new XMLSerializer().serializeToString(svgEl);
    const blob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${$selectedProjectStore?.project_code || 'System'}_${activeTab}_flowchart.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('ดาวน์โหลด Diagram (SVG) เรียบร้อย', 'success');
  }

  function handleTestScreenWithAgent(screen) {
    if (!screen) return;
    testTargetCard = {
      id: screen.screen_id,
      title: `${screen.screen_name || screen.screen_id} => ${screen.route || ''}`,
      description: screen.description || `ตรวจสอบและทดสอบหน้าจอ ${screen.screen_name} (Route: ${screen.route})`,
      target_url: screen.route
    };
    isTestModalOpen = true;
  }

  function handleTestCompleted(e) {
    const result = e.detail;
    toast(`รันการทดสอบหน้าจอสำเร็จ: ${result.verdict}`, result.is_passed ? 'success' : 'warning');
  }

  const DIAGRAM_TABS = new Set(['flowchart', 'usecase', 'activity', 'sequence']);
  let diagramRenderSeq = 0;

  $: if (flowData && DIAGRAM_TABS.has(activeTab)) {
    renderCurrentDiagram();
  }

  async function renderCurrentDiagram() {
    if (!DIAGRAM_TABS.has(activeTab) || !flowData) return;
    const seq = ++diagramRenderSeq;
    await tick();
    if (seq !== diagramRenderSeq || !diagramContainer || !flowData || !DIAGRAM_TABS.has(activeTab)) return;

    let diagramCode = "";
    if (activeTab === 'flowchart') diagramCode = flowData.system_flowchart || flowData.activity_diagram;
    else if (activeTab === 'usecase') diagramCode = flowData.usecase_diagram;
    else if (activeTab === 'activity') diagramCode = flowData.activity_diagram;
    else if (activeTab === 'sequence') diagramCode = flowData.sequence_diagram;

    if (!diagramCode || !diagramCode.trim()) {
      diagramContainer.innerHTML = '<div class="diagram-empty">ไม่มีข้อมูล Diagram สำหรับหน้านี้ กรุณากดปุ่มวิเคราะห์ด้านบน</div>';
      return;
    }

    const cleanCode = sanitizeMermaidCode(diagramCode);

    try {
      const id = `mermaid-svg-${Date.now()}-${seq}`;
      diagramContainer.innerHTML = '<div class="diagram-loading"><span class="spinner-small"></span> กำลัง Render Flowchart...</div>';
      const { svg } = await mermaid.render(id, cleanCode);
      if (seq !== diagramRenderSeq || !diagramContainer) return;
      diagramContainer.innerHTML = svg;
      await tick();
      if (seq !== diagramRenderSeq) return;
      fitView();
    } catch (err) {
      if (seq !== diagramRenderSeq || !diagramContainer) return;
      console.error('Mermaid render error:', err);
      diagramContainer.innerHTML = `<div class="diagram-error"><div style="font-weight: bold; margin-bottom: 6px;">❌ เกิดข้อผิดพลาดในการ Render Diagram:</div><pre style="font-size: 11px; white-space: pre-wrap; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px;">${cleanCode || diagramCode}</pre></div>`;
    }
  }

  function onPointerDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    if (e.target && e.target.closest && e.target.closest('button, a, input, select, textarea')) return;

    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    startPanX = panX;
    startPanY = panY;

    if (typeof window !== 'undefined') {
      window.addEventListener('pointermove', onPointerMove);
      window.addEventListener('pointerup', onPointerUp);
      window.addEventListener('pointercancel', onPointerUp);
      window.addEventListener('blur', onPointerUp);
    }
  }

  function onPointerMove(e) {
    if (!isDragging) return;
    panX = startPanX + (e.clientX - dragStartX);
    panY = startPanY + (e.clientY - dragStartY);
  }

  function onPointerUp() {
    if (!isDragging) return;
    isDragging = false;
    if (typeof window !== 'undefined') {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('pointercancel', onPointerUp);
      window.removeEventListener('blur', onPointerUp);
    }
  }

  function handleWheel(e) {
    if (!canvasPanelRef) return;
    e.preventDefault();

    const rect = canvasPanelRef.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.87;
    const newZoom = Math.min(Math.max(zoomLevel * zoomFactor, 0.08), 5.0);

    panX = mouseX - ((mouseX - panX) / zoomLevel) * newZoom;
    panY = mouseY - ((mouseY - panY) / zoomLevel) * newZoom;
    zoomLevel = Number(newZoom.toFixed(3));
  }

  function zoomIn() {
    const newZoom = Math.min(zoomLevel * 1.25, 5.0);
    if (canvasPanelRef) {
      const rect = canvasPanelRef.getBoundingClientRect();
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      panX = cx - ((cx - panX) / zoomLevel) * newZoom;
      panY = cy - ((cy - panY) / zoomLevel) * newZoom;
    }
    zoomLevel = Number(newZoom.toFixed(3));
  }

  function zoomOut() {
    const newZoom = Math.max(zoomLevel / 1.25, 0.08);
    if (canvasPanelRef) {
      const rect = canvasPanelRef.getBoundingClientRect();
      const cx = rect.width / 2;
      const cy = rect.height / 2;
      panX = cx - ((cx - panX) / zoomLevel) * newZoom;
      panY = cy - ((cy - panY) / zoomLevel) * newZoom;
    }
    zoomLevel = Number(newZoom.toFixed(3));
  }

  function zoomReset() {
    zoomLevel = 1;
    centerDiagram();
  }

  function centerDiagram() {
    if (!canvasPanelRef || !diagramContainer) return;
    const svg = diagramContainer.querySelector('svg');
    if (!svg) {
      panX = 0;
      panY = 0;
      return;
    }
    const svgWidth = parseFloat(svg.style.width) || svg.clientWidth || 1000;
    const svgHeight = parseFloat(svg.style.height) || svg.clientHeight || 600;
    panX = (canvasPanelRef.clientWidth - (svgWidth * zoomLevel)) / 2;
    panY = Math.max(20, (canvasPanelRef.clientHeight - (svgHeight * zoomLevel)) / 2);
  }

  function fitView() {
    if (!canvasPanelRef || !diagramContainer) return;
    const svg = diagramContainer.querySelector('svg');
    if (!svg) {
      zoomReset();
      return;
    }

    let svgWidth = 0;
    let svgHeight = 0;

    const vb = svg.getAttribute('viewBox');
    if (vb) {
      const parts = vb.trim().split(/[\s,]+/).map(Number);
      if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
        svgWidth = parts[2];
        svgHeight = parts[3];
      }
    }

    if (!svgWidth || !svgHeight) {
      try {
        const bbox = svg.getBBox ? svg.getBBox() : svg.getBoundingClientRect();
        svgWidth = bbox.width || 1000;
        svgHeight = bbox.height || 600;
      } catch (e) {
        svgWidth = 1000;
        svgHeight = 600;
      }
    }

    svg.style.width = `${svgWidth}px`;
    svg.style.height = `${svgHeight}px`;
    svg.style.maxWidth = 'none';

    const pad = 40;
    const panelWidth = Math.max(canvasPanelRef.clientWidth - pad, 200);
    const panelHeight = Math.max(canvasPanelRef.clientHeight - pad, 200);

    const scaleX = panelWidth / svgWidth;
    const scaleY = panelHeight / svgHeight;
    const idealScale = Math.min(scaleX, scaleY, 1.0);
    const clampedScale = Math.max(Math.min(idealScale, 2.0), 0.1);

    zoomLevel = Number(clampedScale.toFixed(2));
    panX = (canvasPanelRef.clientWidth - (svgWidth * zoomLevel)) / 2;
    panY = Math.max(20, (canvasPanelRef.clientHeight - (svgHeight * zoomLevel)) / 2);
  }

  function synthesizeMockupForNode(node) {
    if (!node) return null;
    const nid = node.id || 'page';
    const title = node.title || 'Screen';
    const path = node.path || '/';
    const sid = node.screen_id || ('SCR-' + String(nid).toUpperCase().replace(/[^A-Z0-9]/g, '_').slice(0, 24));
    const desc = node.description || `หน้าจอสำหรับโมดูล ${title} ในระบบโครงการ`;
    const category = node.category || 'Core Module';
    const projName = $selectedProjectStore?.name || $selectedProjectStore?.project_name || 'System Workspace';
    const projCode = $selectedProjectStore?.project_code || 'PROJ';
    const useCases = Array.isArray(node.use_case_ids) && node.use_case_ids.length > 0
      ? node.use_case_ids
      : [`UC-${sid.replace(/^SCR-/, '').slice(0, 12)}`];
    const reqCodes = Array.isArray(node.req_codes) && node.req_codes.length > 0
      ? node.req_codes
      : [`REQ-${projCode}-001`];

    const lowerPath = path.toLowerCase();
    const lowerTitle = title.toLowerCase();
    const isFormLayout = /login|auth|register|create|new|edit|setting|config|profile|consent|form/.test(lowerPath + ' ' + lowerTitle);

    return {
      screen_id: sid,
      screen_name: title,
      route: path,
      layout_type: isFormLayout ? 'form' : 'dashboard',
      description: desc,
      header: {
        title: title,
        badge: category,
        badge_color: 'indigo',
        actions: ['บันทึกข้อมูล', 'รีเฟรชสถานะ', 'ส่งออกรายงาน']
      },
      stats: [
        { label: 'รหัสหน้าจอ', value: sid, sub: projName, color: 'blue' },
        { label: 'หมวดหมู่โมดูล', value: category, sub: path, color: 'purple' },
        { label: 'Use Cases ที่เชื่อมโยง', value: `${useCases.length} รายการ`, sub: useCases[0] || '-', color: 'emerald' },
        { label: 'สถานะการออกแบบ', value: 'Synthesized Preview', sub: 'อัปโหลดรูปหรือเชื่อม Figma ได้', color: 'amber' }
      ],
      tabs: ['ภาพรวมหน้าจอ (Overview)', 'ข้อมูลและฟอร์ม (Fields & Actions)', 'ความเชื่อมโยง QA (Traceability)'],
      sections: [
        {
          section_name: `ข้อมูลหลักและการดำเนินการ — ${title}`,
          type: 'form',
          fields: [
            { label: 'ชื่อหน้าจอ / โมดูล (Screen Name)', type: 'text', default_value: title, required: true },
            { label: 'เส้นทาง Route / Endpoint', type: 'text', default_value: path, required: true },
            { label: 'คำอธิบายขอบเขตการทำงาน (Scope Description)', type: 'textarea', default_value: desc, required: false },
            { label: 'เปิดใช้งานการตรวจสอบสิทธิ์ (Role & Permission Guard)', type: 'toggle', default_value: true }
          ],
          buttons: [
            { label: 'บันทึกการเปลี่ยนแปลง', variant: 'primary', icon: '✓' },
            { label: 'ตรวจสอบ Validation', variant: 'secondary', icon: '⚡' },
            { label: 'รีเซ็ตค่าเริ่มต้น', variant: 'outline', icon: '↺' }
          ]
        },
        {
          section_name: `รายการตรวจสอบความเชื่อมโยง (Linked Requirements & Test Scope)`,
          type: 'table',
          table_headers: ['รหัสอ้างอิง', 'ประเภท', 'ขอบเขตที่ครอบคลุม', 'สถานะ QA'],
          table_rows: [
            [sid, 'Screen UI', `ตรวจสอบ Layout, Validation และ Navigation ของ ${title}`, 'Ready for QA'],
            [useCases[0] || 'UC-001', 'Use Case', desc.slice(0, 72), 'Mapped'],
            [reqCodes[0] || 'REQ-001', 'Requirement', `รองรับการทำงานบน Route ${path}`, 'Tracked']
          ]
        }
      ],
      connected_use_cases: useCases,
      connected_req_codes: reqCodes
    };
  }

  // ── Prototype Interactive State ──
  let prototypeDevice = 'desktop'; // 'desktop' | 'tablet' | 'mobile'
  let activePrototypeTab = '';
  let isFavorite = false;
  let formValues = {};
  let currentFormValues = {};
  let isSimulatingSubmit = false;
  let activePrototypeModal = null; // null | { title: '...', content: '...', type: '...' }
  let revealedPasswords = {};
  let tableSearchQuery = '';
  let mutatedTableRows = {}; // key: `${screen_id}_${secIdx}` -> rows array
  let interactiveRating = 5;
  let discoveryCategory = 'ทั้งหมด';
  let showSimulatedMap = true;

  function cleanMockupLabel(raw) {
    if (!raw) return '';
    return String(raw)
      .replace(/^[\p{Emoji}\p{Emoji_Presentation}\p{Extended_Pictographic}\uFE0F\u200D\s•·\-]+/gu, '')
      .trim() || String(raw).trim();
  }

  function detectScreenArchetype(mockup) {
    if (!mockup) return 'standard';
    const text = `${mockup.screen_id || ''} ${mockup.screen_name || ''} ${mockup.route || ''} ${mockup.header?.title || ''} ${mockup.layout_type || ''}`.toLowerCase();
    if (/login|signin|sign-in|register|signup|auth|forgot|otp|sso|เข้าสู่ระบบ|สมัครสมาชิก|ยืนยันตัวตน/.test(text) && !/pdpa|consent|account|profile|setting|จัดการบัญชี/.test(text)) {
      return 'auth';
    }
    if (/review|rating|รีวิว|ให้คะแนน|ความคิดเห็น/.test(text)) {
      return 'review';
    }
    if (/home|map|search|explore|favorite|discover|restaurant|catalog|menu|ค้นหา|แผนที่|ร้านอาหาร|รายการโปรด/.test(text)) {
      return 'discovery';
    }
    return 'standard';
  }

  function detectAuthTabMode(tabName) {
    const t = String(tabName || '').toLowerCase();
    if (/register|sign up|signup|สมัครสมาชิก|สร้างบัญชี/.test(t)) return 'register';
    if (/forgot|reset|recover|otp|ลืมรหัส|กู้คืน/.test(t)) return 'forgot';
    if (/policy|sso|security|2fa|นโยบาย|ความปลอดภัย/.test(t)) return 'security';
    return 'signin';
  }

  function classifyActionButton(btn, isAuthScreen = false) {
    const rawLabel = String(btn?.label || btn || '').toLowerCase();
    if (rawLabel.includes('line')) return 'brand-line';
    if (rawLabel.includes('google')) return 'brand-google';
    if (/ลบ|delete|remove|ยกเลิกบัญชี|ระงับ|ออกจากระบบ/.test(rawLabel)) return 'danger';
    if (/นำทาง|แผนที่|map|gps/.test(rawLabel)) return 'map';
    if (btn?.variant === 'primary' || /เข้าสู่ระบบทันที|sign in|login|บันทึก|ยืนยัน|ส่ง|สมัคร|สร้าง/.test(rawLabel)) {
      return isAuthScreen ? 'primary auth-submit-full' : 'primary';
    }
    if (btn?.variant === 'outline') return 'outline';
    return btn?.variant || 'secondary';
  }

  function togglePasswordVisibility(key) {
    revealedPasswords = { ...revealedPasswords, [key]: !revealedPasswords[key] };
  }

  function getInteractiveTableRows(sec, secIdx) {
    const sid = currentScreenMockup?.screen_id || 'DEFAULT';
    const key = `${sid}_${secIdx}`;
    const baseRows = mutatedTableRows[key] || sec?.table_rows || [];
    const q = tableSearchQuery.trim().toLowerCase();
    if (!q) return baseRows;
    return baseRows.filter(r => Array.isArray(r) && r.some(c => String(c).toLowerCase().includes(q)));
  }

  function handleSelectSitemapNode(node) {
    if (!node) return;
    selectedSitemapNode = node;
    selectedNodeId = node.id || node.screen_id || node.path || node.title;

    // Search for existing mockup by screen_id, route, title, or node_id
    let matched = null;
    if (flowData && flowData.screen_mockups && flowData.screen_mockups.length > 0) {
      matched = flowData.screen_mockups.find(s => 
        (node.screen_id && s.screen_id === node.screen_id) ||
        (node.path && s.route === node.path) ||
        (node.title && (s.screen_name === node.title || s.screen_name?.toLowerCase().includes(node.title.toLowerCase())))
      );
    }

    if (!matched) {
      // Synthesize a dedicated interactive mockup so it NEVER stays stuck on screen 0
      matched = synthesizeMockupForNode(node);
      if (flowData) {
        if (!flowData.screen_mockups) flowData.screen_mockups = [];
        flowData.screen_mockups = [...flowData.screen_mockups, matched];
      }
    }

    // Synchronously initialize formValues for this screen BEFORE changing selectedScreenId
    const sid = matched.screen_id || 'DEFAULT';
    if (!formValues[sid]) {
      formValues[sid] = {};
    }
    if (matched.sections) {
      matched.sections.forEach(sec => {
        if (sec.fields) {
          sec.fields.forEach(f => {
            if (formValues[sid][f.label] === undefined) {
              formValues[sid][f.label] = f.default_value !== undefined ? f.default_value : (f.default !== undefined ? f.default : (f.placeholder || ''));
            }
          });
        }
      });
    }
    currentFormValues = formValues[sid];

    // Reset prototype tab and scroll position
    activePrototypeTab = (matched.tabs && matched.tabs[0]) || '';
    isFavorite = false;
    selectedScreenId = matched.screen_id;
  }

  $: currentScreenMockup = (flowData && flowData.screen_mockups && flowData.screen_mockups.length > 0) 
    ? (flowData.screen_mockups.find(s => s.screen_id === selectedScreenId) ||
       (selectedSitemapNode ? (flowData.screen_mockups.find(s => 
         (selectedSitemapNode.screen_id && s.screen_id === selectedSitemapNode.screen_id) ||
         (selectedSitemapNode.path && s.route === selectedSitemapNode.path) ||
         (selectedSitemapNode.title && s.screen_name === selectedSitemapNode.title)
       ) || synthesizeMockupForNode(selectedSitemapNode)) : flowData.screen_mockups[0]))
    : null;

  // Reactive default form values sync when screen changes
  $: if (currentScreenMockup) {
    const mockId = currentScreenMockup.screen_id || 'DEFAULT';
    if (!formValues[mockId]) {
      formValues[mockId] = {};
    }
    if (currentScreenMockup.sections) {
      currentScreenMockup.sections.forEach(sec => {
        if (sec.fields) {
          sec.fields.forEach(f => {
            if (formValues[mockId][f.label] === undefined) {
              formValues[mockId][f.label] = f.default_value !== undefined ? f.default_value : (f.default !== undefined ? f.default : (f.placeholder || ''));
            }
          });
        }
      });
    }
    currentFormValues = formValues[mockId];

    if (currentScreenMockup.tabs && currentScreenMockup.tabs.length > 0) {
      if (!activePrototypeTab || !currentScreenMockup.tabs.includes(activePrototypeTab)) {
        activePrototypeTab = currentScreenMockup.tabs[0];
      }
    }
  }

  function fillSampleData() {
    if (!currentScreenMockup) return;
    const mockId = currentScreenMockup.screen_id || 'DEFAULT';
    if (!formValues[mockId]) formValues[mockId] = {};
    if (currentScreenMockup.sections) {
      currentScreenMockup.sections.forEach(sec => {
        if (sec.fields) {
          sec.fields.forEach(f => {
            if (f.type === 'toggle' || f.type === 'checkbox') {
              formValues[mockId][f.label] = true;
            } else if (f.default_value) {
              formValues[mockId][f.label] = f.default_value;
            } else if (f.placeholder && f.placeholder !== f.label) {
              formValues[mockId][f.label] = f.placeholder;
            } else if (f.options && f.options.length > 0) {
              formValues[mockId][f.label] = f.options[0];
            } else {
              formValues[mockId][f.label] = `Sample ${f.label}`;
            }
          });
        }
      });
    }
    currentFormValues = { ...formValues[mockId] };
    toast('เติมข้อมูลจำลองสำหรับทดสอบ Prototype เรียบร้อย', 'success');
  }

  function resetPrototype() {
    if (!currentScreenMockup) return;
    const mockId = currentScreenMockup.screen_id || 'DEFAULT';
    formValues[mockId] = {};
    currentFormValues = {};
    mutatedTableRows = {};
    tableSearchQuery = '';
    revealedPasswords = {};
    isFavorite = false;
    toast('รีเซ็ตค่าฟอร์มและตาราง Prototype กลับเป็นค่าเริ่มต้นสำเร็จ', 'info');
  }

  function handleTableActionClick(cellText, row, secIdx = 0, rowIdx = -1) {
    const sid = currentScreenMockup?.screen_id || 'DEFAULT';
    const key = `${sid}_${secIdx}`;
    const sec = currentScreenMockup?.sections?.[secIdx];
    const currentRows = (mutatedTableRows[key] || sec?.table_rows || []).map(r => [...r]);
    const act = cleanMockupLabel(cellText).toLowerCase();

    if (rowIdx >= 0 && rowIdx < currentRows.length) {
      if (act.includes('ลบ') || act.includes('delete') || act.includes('remove')) {
        currentRows.splice(rowIdx, 1);
        mutatedTableRows = { ...mutatedTableRows, [key]: currentRows };
        toast(`ลบรายการ "${row[0]}" ออกจากตารางแล้ว (กดรีเซ็ตเพื่อกู้คืน)`, 'info');
        return;
      }
      if (act.includes('ออกจากระบบ') || act.includes('logout') || act.includes('revoke')) {
        currentRows[rowIdx] = currentRows[rowIdx].map((c, idx) =>
          idx === currentRows[rowIdx].length - 2 ? 'ออกจากระบบแล้ว' : (idx === currentRows[rowIdx].length - 1 ? 'ลบประวัติ' : c)
        );
        mutatedTableRows = { ...mutatedTableRows, [key]: currentRows };
        toast(`บังคับออกจากระบบสำหรับอุปกรณ์ "${row[0]}" เรียบร้อย`, 'success');
        return;
      }
    }
    toast(`ดำเนินการ "${cleanMockupLabel(cellText)}" สำหรับ "${row[1] || row[0]}" สำเร็จ`, 'success');
  }

  function handlePrototypeButtonAction(btn) {
    const label = (btn.label || btn || '').toLowerCase();
    if (label.includes('สั่ง') || label.includes('บันทึก') || label.includes('save') || label.includes('submit') || label.includes('sign in') || label.includes('เข้าสู่ระบบ') || label.includes('claim')) {
      isSimulatingSubmit = true;
      setTimeout(() => {
        isSimulatingSubmit = false;
        activePrototypeModal = {
          title: 'ดำเนินการสำเร็จ (Simulation Success)',
          content: `ระบบทำการประมวลผลคำขอ "${btn.label || 'Submit'}" และบันทึกข้อมูลเข้าสู่ฐานข้อมูลเรียบร้อยแล้ว`,
          type: 'success'
        };
      }, 500);
    } else if (label.includes('นำทาง') || label.includes('map') || label.includes('แผนที่')) {
      const addr = formValues[currentScreenMockup.screen_id]?.['ที่อยู่ / สถานที่ตั้ง'] || formValues[currentScreenMockup.screen_id]?.['ที่อยู่'] || 'จุดหมายปลายทาง';
      activePrototypeModal = {
        title: 'จำลองระบบ GPS นำทาง (Route Simulator)',
        content: `กำลังเชื่อมต่อไปยัง: ${addr} (ระยะทาง 1.8 กม. ใช้เวลาเดินทางโดยรถยนต์ประมาณ 7 นาที)`,
        type: 'map'
      };
    } else if (label.includes('โทร') || label.includes('call') || label.includes('phone')) {
      const phone = formValues[currentScreenMockup.screen_id]?.['เบอร์โทรศัพท์ติดต่อ'] || formValues[currentScreenMockup.screen_id]?.['เบอร์โทร'] || '02-123-4567';
      toast(`กำลังจำลองการโทรออกไปยังเบอร์: ${phone}`, 'info');
    } else if (label.includes('รีวิว') || label.includes('review')) {
      activePrototypeModal = {
        title: 'ฟอร์มส่งรีวิวและความประทับใจ',
        content: 'คุณกำลังเขียนรีวิวและให้คะแนน 5 ดาวสำหรับ ' + (currentScreenMockup.header?.title || currentScreenMockup.screen_name),
        type: 'review'
      };
    } else {
      toast(`คลิกปุ่ม Prototype: "${btn.label || btn}" สำเร็จ`, 'info');
    }
  }

  function handlePrototypeHeaderAction(act) {
    const s = String(act).toLowerCase();
    if (s.includes('แชร์') || s.includes('share')) {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        navigator.clipboard.writeText(window.location.href);
      }
      toast('คัดลอกลิงก์หน้าจอ Prototype แล้ว!', 'success');
    } else if (s.includes('โปรด') || s.includes('favorite') || s.includes('like') || s.includes('บันทึกรายการ')) {
      isFavorite = !isFavorite;
      toast(isFavorite ? 'เพิ่มในรายการโปรดแล้ว' : 'นำออกจากรายการโปรดแล้ว', 'info');
    } else if (s.includes('ย้อนกลับ') || s.includes('back')) {
      if (flowData?.screen_mockups && flowData.screen_mockups.length > 1) {
        const currIdx = flowData.screen_mockups.findIndex(s => s.screen_id === selectedScreenId);
        const prevIdx = currIdx > 0 ? currIdx - 1 : flowData.screen_mockups.length - 1;
        selectedScreenId = flowData.screen_mockups[prevIdx].screen_id;
        toast(`ย้อนกลับไปยังหน้า: ${flowData.screen_mockups[prevIdx].screen_name}`, 'info');
      } else {
        toast('ย้อนกลับ', 'info');
      }
    } else {
      toast(`คลิก: ${act}`, 'info');
    }
  }

</script>

<svelte:window on:keydown={handleDiagramKeydown} />

<div class="panel-container" in:fade={{ duration: 220 }}>
  <div class="sr-only" role="status" aria-live="polite" aria-atomic="true">{liveMessage}</div>
  {#if !$selectedProjectStore}
    <ProjectSelection 
      {projects} 
      title="QA Analysis Diagram & Flow Architecture"
      subtitle="เลือกโครงการเพื่อวิเคราะห์และจำลอง Flow Sitemap, UML Diagrams, Screen Mockups และ Traceability Matrix จาก Knowledge Base"
      on:select={(e) => selectProject(e.detail)} 
    />
  {:else}
    <!-- Top Nav & Breadcrumb -->
    <div class="top-nav">
      <button type="button" class="btn-back" on:click={() => selectedProjectStore.set(null)}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>

      <div class="top-nav-right">
        {#if flowData?.updated_at}
          <div class="sync-timestamp" title="อัปเดตฐานข้อมูล Flow ล่าสุด">
            <span class="sync-pulse-dot" aria-hidden="true"></span>
            <span>ซิงค์ล่าสุด {formatUpdatedAt(flowData.updated_at)}</span>
          </div>
        {/if}
        <div class="project-pill">
          <span class="p-badge">{$selectedProjectStore.project_code || 'PROJ'}</span>
          <span class="p-title">{$selectedProjectStore.name || $selectedProjectStore.project_name}</span>
        </div>
      </div>
    </div>

    <!-- Header & AI Control Banner -->
    <div class="glass-panel banner-panel">
      <div class="banner-header">
        <div class="banner-title-block">
          <div class="title-with-badge">
            <h2>QA Analysis Diagram & Flow Modeler</h2>
            <span class="badge-ai">Agent 7 · Flow Architect</span>
          </div>
          <p class="desc-text">
            ประมวลผลและสร้างผัง Flow ระบบ, Sitemap โครงสร้างเมนู, UML Diagrams, Wireframe Mockups และตาราง Traceability Matrix โดยเชื่อมโยงเอกสารจากคลังและซิงค์บริบทให้ Agent ทุกตัวในโครงการ
          </p>
        </div>

        <div class="action-buttons">
          <button type="button" class="btn-generate-ai" on:click={handleGenerateAnalysis} disabled={isAnalyzing}>
            {#if isAnalyzing}
              <div class="spinner-small"></div> กำลังวิเคราะห์ Flow & Diagrams...
            {:else}
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
              </svg>
              วิเคราะห์และสร้าง Diagram ใหม่ (AI Synthesizer)
            {/if}
          </button>
        </div>
      </div>

      <!-- Executive Architecture Summary + Cross-Agent Sync Strip -->
      {#if flowData}
        <div class="executive-summary-bar" in:fly={{ y: 8, duration: 240, easing: cubicOut }}>
          <div class="exec-summary-main">
            <span class="exec-label">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
              </svg>
              Architecture Context
            </span>
            <p class="exec-text">
              {flowData.summary_stats?.executive_summary || 'โครงสร้าง Flow, Sitemap, UML Diagrams และ Traceability Matrix พร้อมใช้งานและซิงค์เป็นแหล่งอ้างอิงกลางให้ Agent อื่นในโครงการแล้ว'}
            </p>
          </div>
          <div class="cross-agent-sync" aria-label="Agent ที่เชื่อมต่อข้อมูลนี้">
            <span class="cross-sync-label">Shared with</span>
            <div class="cross-agent-pills">
              <span class="agent-sync-pill">QA Doc Creation</span>
              <span class="agent-sync-pill">QA Consult</span>
              <span class="agent-sync-pill">QA Research</span>
              <span class="agent-sync-pill">Playwright Auto</span>
            </div>
          </div>
        </div>
      {/if}

      <!-- Optional Instruction Dropdown -->
      <div class="instructions-accordion">
        <button type="button" class="accordion-toggle" on:click={() => showInstructions = !showInstructions} aria-expanded={showInstructions}>
          <svg class="accordion-chevron" class:rotated={showInstructions} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="9 18 15 12 9 6"></polyline>
          </svg>
          <span>คำสั่งเพิ่มเติม / Specific Focus Instructions (Optional)</span>
        </button>
        {#if showInstructions}
          <div class="accordion-content" transition:slide={{ duration: 200 }}>
            <textarea 
              aria-label="คำสั่งเพิ่มเติมสำหรับ AI"
              bind:value={customInstructions} 
              placeholder="ระบุสิ่งที่ต้องการให้ AI เน้นเป็นพิเศษ เช่น 'เน้น Flow การชำระเงินและ Payment Gateway', 'แจกแจง Use Case ให้ละเอียดสำหรับ Admin', หรือ 'สร้าง Mockup เฉพาะหน้าจัดการสมาชิก'..."
              rows="2"
              class="instructions-textarea"
            ></textarea>
          </div>
        {/if}
      </div>

      <!-- Summary Stats Counter -->
      {#if flowData && flowData.summary_stats}
        <div class="stats-grid" in:fade={{ duration: 220 }}>
          <div class="stat-card" style="--stagger: 0;">
            <div class="stat-icon-box indigo" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="7" rx="1"></rect>
                <rect x="14" y="3" width="7" height="7" rx="1"></rect>
                <rect x="14" y="14" width="7" height="7" rx="1"></rect>
                <rect x="3" y="14" width="7" height="7" rx="1"></rect>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_modules || (flowData.sitemap ? flowData.sitemap.length : 0)}</div>
              <div class="stat-label">Modules / Menus</div>
            </div>
          </div>
          <div class="stat-card" style="--stagger: 1;">
            <div class="stat-icon-box violet" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="2" y="3" width="20" height="14" rx="2"></rect>
                <line x1="8" y1="21" x2="16" y2="21"></line>
                <line x1="12" y1="17" x2="12" y2="21"></line>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_screens || (flowData.screen_mockups ? flowData.screen_mockups.length : 0)}</div>
              <div class="stat-label">Screen Mockups</div>
            </div>
          </div>
          <div class="stat-card" style="--stagger: 2;">
            <div class="stat-icon-box sky" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="9" cy="7" r="4"></circle>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_use_cases || 0}</div>
              <div class="stat-label">Use Cases</div>
            </div>
          </div>
          <div class="stat-card" style="--stagger: 3;">
            <div class="stat-icon-box amber" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_requirements || (flowData.traceability_matrix ? flowData.traceability_matrix.length : 0)}</div>
              <div class="stat-label">Requirements</div>
            </div>
          </div>
          <div class="stat-card highlight" style="--stagger: 4;">
            <div class="stat-icon-box emerald" aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
              </svg>
            </div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.coverage_percentage || 100}%</div>
              <div class="stat-label">QA Traceability Coverage</div>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Main Navigation Tabs -->
    <div class="tabs-header" role="tablist" aria-label="หมวดหมู่ผัง Flow และ Diagram" on:keydown={handleTabsKeydown}>
      <button type="button" class="nav-tab" role="tab" id="qa-tab-sitemap" aria-controls="qa-tabpanel" tabindex={activeTab === 'sitemap' ? 0 : -1} aria-selected={activeTab === 'sitemap'} class:active={activeTab === 'sitemap'} on:click={() => activeTab = 'sitemap'}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="2"></rect>
          <line x1="3" y1="9" x2="21" y2="9"></line>
          <line x1="9" y1="21" x2="9" y2="9"></line>
        </svg>
        <span>Flow Sitemap & Wireframes</span>
      </button>
      <button type="button" class="nav-tab" role="tab" id="qa-tab-flowchart" aria-controls="qa-tabpanel" tabindex={activeTab === 'flowchart' ? 0 : -1} aria-selected={activeTab === 'flowchart'} class:active={activeTab === 'flowchart'} on:click={() => activeTab = 'flowchart'}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="3" width="6" height="6" rx="1"></rect>
          <rect x="15" y="15" width="6" height="6" rx="1"></rect>
          <path d="M9 6h4a2 2 0 0 1 2 2v7"></path>
          <path d="M6 9v6a2 2 0 0 0 2 2h7"></path>
        </svg>
        <span>System Flowchart</span>
      </button>
      <button type="button" class="nav-tab" role="tab" id="qa-tab-usecase" aria-controls="qa-tabpanel" tabindex={activeTab === 'usecase' ? 0 : -1} aria-selected={activeTab === 'usecase'} class:active={activeTab === 'usecase'} on:click={() => activeTab = 'usecase'}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
          <circle cx="9" cy="7" r="4"></circle>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
        </svg>
        <span>Use Case Diagram</span>
      </button>
      <button type="button" class="nav-tab" role="tab" id="qa-tab-activity" aria-controls="qa-tabpanel" tabindex={activeTab === 'activity' ? 0 : -1} aria-selected={activeTab === 'activity'} class:active={activeTab === 'activity'} on:click={() => activeTab = 'activity'}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
        <span>Activity & Process Flow</span>
      </button>
      <button type="button" class="nav-tab" role="tab" id="qa-tab-sequence" aria-controls="qa-tabpanel" tabindex={activeTab === 'sequence' ? 0 : -1} aria-selected={activeTab === 'sequence'} class:active={activeTab === 'sequence'} on:click={() => activeTab = 'sequence'}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="17 1 21 5 17 9"></polyline>
          <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
          <polyline points="7 23 3 19 7 15"></polyline>
          <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
        </svg>
        <span>Sequence & Architecture</span>
      </button>
      <button type="button" class="nav-tab" role="tab" id="qa-tab-matrix" aria-controls="qa-tabpanel" tabindex={activeTab === 'matrix' ? 0 : -1} aria-selected={activeTab === 'matrix'} class:active={activeTab === 'matrix'} on:click={() => activeTab = 'matrix'}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9 11l3 3L22 4"></path>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
        </svg>
        <span>Traceability Matrix</span>
      </button>
    </div>

    <!-- Tab Contents -->
    {#if !flowData}
      <div class="glass-panel empty-analysis-card" in:fly={{ y: 12, duration: 260, easing: cubicOut }}>
        <div class="empty-icon-ring" aria-hidden="true">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="3" width="6" height="6" rx="1"></rect>
            <rect x="15" y="15" width="6" height="6" rx="1"></rect>
            <path d="M9 6h4a2 2 0 0 1 2 2v7"></path>
            <path d="M6 9v6a2 2 0 0 0 2 2h7"></path>
          </svg>
        </div>
        <h3>ยังไม่มีข้อมูล Flow Analysis สำหรับโครงการนี้</h3>
        <p>กดปุ่ม <b>"วิเคราะห์และสร้าง Diagram ใหม่ (AI Synthesizer)"</b> ด้านบน เพื่อให้ Agent 7 ประมวลผลเอกสารคลังข้อมูล, API Collection และสร้างผังสถาปัตยกรรมครบชุด</p>
      </div>
    {:else}
      <!-- TAB 1: SITEMAP & WIREFRAMES -->
      {#if activeTab === 'sitemap'}
        <div class="sitemap-workspace" role="tabpanel" id="qa-tabpanel" aria-labelledby="qa-tab-sitemap" in:fly={{ y: 12, duration: 240, easing: cubicOut }}>
          <!-- Left: Sitemap Tree Navigation -->
          <div class="glass-panel sitemap-panel">
            <div class="panel-title-row">
              <h3><QAIcon name="map" /> Flow Sitemap (เมนูและโครงสร้างหน้า)</h3>
              <span class="count-badge">{flowData.sitemap ? flowData.sitemap.length : 0} Modules</span>
            </div>
            <p class="sub-hint">คลิกที่โหนดเมนูเพื่อดู Mockup จำลองหน้าจอ UI ที่เชื่อมโยง</p>

            <div class="sitemap-tree">
              {#if !flowData.sitemap || flowData.sitemap.length === 0}
                <div class="empty-hint">ไม่พบข้อมูล Sitemap</div>
              {:else}
                {#each flowData.sitemap as node}
                  <div
                    class="sitemap-node-card"
                    role="button"
                    tabindex="0"
                    class:active={selectedNodeId ? selectedNodeId === (node.id || node.screen_id || node.path || node.title) : (selectedScreenId && selectedScreenId === node.screen_id)}
                    on:click={() => handleSelectSitemapNode(node)}
                    on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectSitemapNode(node); } }}
                  >
                    <div class="node-main">
                      <span class="node-icon" aria-hidden="true">{#if node.icon}{node.icon}{:else}<QAIcon name="folder" size={16} />{/if}</span>
                      <div class="node-text">
                        <div class="node-title">{node.title}</div>
                        <div class="node-path">{node.path}</div>
                      </div>
                      {#if node.category}
                        <span class="node-category">{node.category}</span>
                      {/if}
                      {#if flowData.screen_mockups?.find(s => s.screen_id === node.screen_id)?.stitch_html}
                        <span class="node-source-badge stitch" title="สร้าง High-Fi UI (Stitch / Live HTML) แล้ว">Stitch UI</span>
                      {:else if flowData.screen_mockups?.find(s => s.screen_id === node.screen_id)?.figma_url}
                        <span class="node-source-badge figma" title="เชื่อมต่อ Figma Frame แล้ว">Figma</span>
                      {:else if flowData.screen_mockups?.find(s => s.screen_id === node.screen_id)?.image_url}
                        <span class="node-source-badge img" title="มีรูปภาพ Mockup แล้ว">Image</span>
                      {/if}
                    </div>
                    {#if node.description}
                      <div class="node-desc">{node.description}</div>
                    {/if}

                    <!-- Children / Sub-pages -->
                    {#if node.children && node.children.length > 0}
                      <div class="node-children">
                        {#each node.children as child}
                          <div
                            class="sitemap-child-card"
                            role="button"
                            tabindex="0"
                            class:active={selectedNodeId ? selectedNodeId === (child.id || child.screen_id || child.path || child.title) : (selectedScreenId && selectedScreenId === child.screen_id)}
                            on:click|stopPropagation={() => handleSelectSitemapNode(child)}
                            on:keydown|stopPropagation={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelectSitemapNode(child); } }}
                          >
                            <span class="child-icon" aria-hidden="true">{#if child.icon}{child.icon}{:else}<QAIcon name="file" size={14} />{/if}</span>
                            <div class="child-info">
                              <span class="child-title">{child.title}</span>
                              <span class="child-path">{child.path}</span>
                            </div>
                            {#if flowData.screen_mockups?.find(s => s.screen_id === child.screen_id)?.stitch_html}
                              <span class="node-source-badge stitch-sm" title="High-Fi UI">Stitch</span>
                            {:else if flowData.screen_mockups?.find(s => s.screen_id === child.screen_id)?.figma_url}
                              <span class="node-source-badge figma-sm" title="Figma">Figma</span>
                            {:else if flowData.screen_mockups?.find(s => s.screen_id === child.screen_id)?.image_url}
                              <span class="node-source-badge img-sm" title="Image">Img</span>
                            {/if}
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/each}
              {/if}
            </div>
          </div>

          <!-- Right: Interactive Screen Mockup -->
          <div class="glass-panel mockup-panel">
            <div class="panel-title-row">
              <div class="panel-title-group">
                <h3><QAIcon name="monitor" /> Screen Mockup & UI Wireframe</h3>
                {#if currentScreenMockup}
                  <span class="screen-id-badge">{currentScreenMockup.screen_id}</span>
                {/if}
              </div>

              <!-- Wireframe Source Mode Selector Tabs -->
              {#if currentScreenMockup}
                <div class="wf-mode-tabs-header">
                  <button 
                    type="button"
                    class="wf-mode-tab-btn" 
                    class:active={activeWireframeTab === 'stitch'} 
                    on:click={() => handleSwitchWireframeTab('stitch')}>
                    <QAIcon name="zap" /> Stitch / Live UI
                    {#if currentScreenMockup.stitch_html}
                      <span class="dot-live cyan"></span>
                    {/if}
                  </button>
                  <button 
                    type="button"
                    class="wf-mode-tab-btn" 
                    class:active={activeWireframeTab === 'ai'} 
                    on:click={() => handleSwitchWireframeTab('ai')}>
                    <QAIcon name="sparkles" /> AI Wireframe
                  </button>
                  <button 
                    type="button"
                    class="wf-mode-tab-btn" 
                    class:active={activeWireframeTab === 'figma'} 
                    on:click={() => handleSwitchWireframeTab('figma')}>
                    <QAIcon name="palette" /> Figma MCP & Embed
                    {#if currentScreenMockup.figma_url}
                      <span class="dot-live green"></span>
                    {/if}
                  </button>
                  <button 
                    type="button"
                    class="wf-mode-tab-btn" 
                    class:active={activeWireframeTab === 'image'} 
                    on:click={() => handleSwitchWireframeTab('image')}>
                    <QAIcon name="image" /> Upload Image
                    {#if currentScreenMockup.image_url}
                      <span class="dot-live blue"></span>
                    {/if}
                  </button>
                </div>
              {/if}
            </div>

            {#if !currentScreenMockup}
              <div class="empty-mockup">
                <div class="empty-mockup-icon" aria-hidden="true"><QAIcon name="monitor" size={40} strokeWidth={1.5} /></div>
                <div style="font-weight: 600; color: #f8fafc; font-size: 15px;">เลือกเมนูทางซ้ายเพื่อแสดง UI Prototype</div>
                <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">ระบบจะจำลองหน้าจอและส่วนประกอบ UI เสมือนจริงที่พร้อมโต้ตอบได้ทันที</div>
              </div>
            {:else}
              <!-- Prototype Toolbar: Viewport Frame Switcher & Utilities -->
              <div class="prototype-control-bar">
                <div class="device-switch-group">
                  <button 
                    type="button"
                    class="btn-device-switch" 
                    class:active={prototypeDevice === 'desktop'} 
                    on:click={() => prototypeDevice = 'desktop'}
                    title="มุมมองหน้าจอ Desktop (100% Wide)">
                    <QAIcon name="monitor" /> Desktop
                  </button>
                  <button 
                    type="button"
                    class="btn-device-switch" 
                    class:active={prototypeDevice === 'tablet'} 
                    on:click={() => prototypeDevice = 'tablet'}
                    title="มุมมองหน้าจอ Tablet (768px)">
                    <QAIcon name="tablet" /> Tablet
                  </button>
                  <button 
                    type="button"
                    class="btn-device-switch" 
                    class:active={prototypeDevice === 'mobile'} 
                    on:click={() => prototypeDevice = 'mobile'}
                    title="มุมมองหน้าจอ Mobile Smartphone (375px)">
                    <QAIcon name="smartphone" /> Mobile
                  </button>
                </div>

                <div class="prototype-quick-actions">
                  <button type="button" class="btn-proto-action fill" on:click={fillSampleData} title="เติมข้อมูลจำลองอัตโนมัติลงในทุกช่องเพื่อทดสอบ">
                    <QAIcon name="zap" /> เติมข้อมูลตัวอย่าง (Sample Data)
                  </button>
                  <button type="button" class="btn-proto-action reset" on:click={resetPrototype} title="ล้างค่าฟอร์มกลับเป็นค่าเริ่มต้น">
                    <QAIcon name="refresh" /> รีเซ็ต
                  </button>
                  <div class="prototype-badge-live">
                    <span class="live-dot pulse"></span>
                    <span>Interactive Prototype</span>
                  </div>
                </div>
              </div>

              <!-- Device Outer Wrap for Responsive Simulation -->
              <div class="prototype-outer-canvas {prototypeDevice}">
                <div class="mockup-viewport" transition:scale={{ duration: 150 }}>
                  
                  {#if prototypeDevice === 'mobile'}
                    <!-- Smartphone Notch & Status Bar -->
                    <div class="mobile-phone-notch-bar">
                      <span class="phone-time">9:41</span>
                      <div class="phone-dynamic-island"></div>
                      <div class="phone-icons">5G</div>
                    </div>
                  {/if}

                  <!-- Mockup Browser Bar -->
                  <div class="mockup-browser-bar">
                    <div class="browser-dots" aria-hidden="true">
                      <span class="dot red"></span>
                      <span class="dot yellow"></span>
                      <span class="dot green"></span>
                    </div>
                    <div class="browser-nav-arrows">
                      <button type="button" class="btn-nav-arrow" on:click={() => handlePrototypeHeaderAction('ย้อนกลับ')} title="ย้อนกลับ" aria-label="ย้อนกลับ"><QAIcon name="back" size={14} /></button>
                      <button type="button" class="btn-nav-arrow" on:click={resetPrototype} title="รีเซ็ตค่า Prototype" aria-label="รีเซ็ตค่า Prototype"><QAIcon name="undo" size={14} /></button>
                      <button type="button" class="btn-nav-arrow" on:click={fillSampleData} title="เติมข้อมูลตัวอย่าง" aria-label="เติมข้อมูลตัวอย่าง"><QAIcon name="refresh" size={14} /></button>
                    </div>
                    <div class="browser-url-input" title={activeWireframeTab === 'figma' && currentScreenMockup.figma_url ? currentScreenMockup.figma_url : `https://${($selectedProjectStore.project_code || 'project').toLowerCase()}.app${currentScreenMockup.route || '/'}`}>
                      <span class="lock-icon" aria-hidden="true"><QAIcon name="lock" size={12} /></span>
                      <span class="browser-url-text">
                        {#if activeWireframeTab === 'figma' && currentScreenMockup.figma_url}
                          {currentScreenMockup.figma_url}
                        {:else}
                          https://{($selectedProjectStore.project_code || 'project').toLowerCase()}.app{currentScreenMockup.route || '/'}
                        {/if}
                      </span>
                    </div>
                    <div class="browser-right-actions">
                      <button type="button" class="btn-run-agent-screen" on:click={() => handleTestScreenWithAgent(currentScreenMockup)} title="เปิดระบบ AI Test Agent เพื่อทดสอบหน้าจอนี้">
                        <QAIcon name="play" /> ทดสอบด้วย AI
                      </button>
                      {#if activeWireframeTab === 'figma' && currentScreenMockup.figma_url}
                        <a href={currentScreenMockup.figma_url} target="_blank" rel="noreferrer" class="browser-ext-link" title="เปิดใน Figma">
                          <QAIcon name="external" /> Figma
                        </a>
                      {:else if activeWireframeTab === 'image' && currentScreenMockup.image_url}
                        <button type="button" class="browser-ext-link" on:click={() => lightboxImage = currentScreenMockup.image_url}>
                          <QAIcon name="search" /> Fullscreen
                        </button>
                      {/if}
                    </div>
                  </div>

                  <!-- MODE 0: GOOGLE STITCH MCP & GEMINI LIVE HTML/TAILWIND UI -->
                  {#if activeWireframeTab === 'stitch'}
                    <div class="stitch-container">
                      <div class="stitch-config-panel">
                        <div class="stitch-top-meta-row">
                          <div class="stitch-isolation-badges">
                            <span class="stitch-space-pill" title="แยก Container และ Design DNA แบบ 1-ต่อ-1 ตามโครงการ">
                              <QAIcon name="folder" size={12} />
                              Project Space: {currentScreenMockup.stitch_project_id || flowData?.summary_stats?.stitch_project_id || ($selectedProjectStore.project_code || 'Isolated')}
                            </span>
                            {#if currentScreenMockup.stitch_engine}
                              <span class="stitch-engine-pill {currentScreenMockup.stitch_engine}">
                                {currentScreenMockup.stitch_engine === 'google_stitch_mcp' ? 'Google Stitch MCP' : 'Gemini Live HTML/Tailwind'}
                              </span>
                            {/if}
                          </div>

                          <div class="stitch-utility-btns">
                            <select bind:value={stitchEngine} class="stitch-engine-select" aria-label="เลือก Engine สร้าง UI">
                              <option value="auto">Auto (Stitch MCP + Gemini Fallback)</option>
                              <option value="stitch">Google Stitch MCP เท่านั้น</option>
                              <option value="gemini">Gemini Live HTML/Tailwind (ฟรีทันที)</option>
                            </select>

                            {#if currentScreenMockup.stitch_html}
                              <button type="button" class="btn-figma-action token" on:click={() => showStitchCodeInspector = !showStitchCodeInspector} title="ดูหรือคัดลอกโค้ด HTML/Tailwind">
                                <QAIcon name="code" /> {showStitchCodeInspector ? 'ซ่อนโค้ด' : 'โค้ด HTML'}
                              </button>
                              <button type="button" class="btn-figma-action token" on:click={downloadStitchHtml} title="ดาวน์โหลดไฟล์ HTML">
                                <QAIcon name="download" /> .html
                              </button>
                            {/if}

                            <button type="button" class="btn-figma-action token" on:click={() => showStitchKeyInput = !showStitchKeyInput} title="ตั้งค่า Google Stitch API Key">
                              <QAIcon name="key" /> Stitch Key
                            </button>
                          </div>
                        </div>

                        <div class="figma-input-row">
                          <span class="figma-icon-tag stitch-tag"><QAIcon name="sparkles" /> Design Prompt:</span>
                          <input
                            type="text"
                            bind:value={stitchPromptInput}
                            placeholder="สั่งปรับดีไซน์เพิ่มเติม (เว้นว่างได้ ระบบจะออกแบบตามโดเมนโครงการและ Requirements อัตโนมัติ)..."
                            class="figma-text-input"
                            aria-label="คำสั่งออกแบบ UI สำหรับ Google Stitch หรือ Gemini"
                            on:keydown={(e) => { if (e.key === 'Enter' && !isGeneratingStitch) handleGenerateStitchScreen(); }}
                          />
                          <button type="button" class="btn-figma-action stitch-gen" on:click={handleGenerateStitchScreen} disabled={isGeneratingStitch}>
                            {#if isGeneratingStitch}
                              <span class="spinner-small"></span> กำลังสร้าง High-Fi UI...
                            {:else}
                              <QAIcon name="zap" /> {currentScreenMockup.stitch_html ? 'สร้างใหม่ / ปรับดีไซน์' : 'สร้าง High-Fi UI'}
                            {/if}
                          </button>
                        </div>

                        {#if showStitchKeyInput}
                          <div class="figma-token-box" transition:slide>
                            <div class="token-title">
                              <QAIcon name="key" /> Google Stitch API Key (`X-Goog-Api-Key` จาก stitch.withgoogle.com &gt; Setup MCP &gt; กดปุ่ม Copy key):
                            </div>
                            <div class="token-form-row">
                              <input
                                type="password"
                                bind:value={stitchApiKeyInput}
                                placeholder="วาง Stitch API Key ที่กด Copy key มาจากหน้า Setup MCP..."
                                class="figma-token-field"
                                aria-label="Google Stitch API Key"
                              />
                              <button type="button" class="btn-save-token" on:click={handleSaveStitchKey} disabled={isSavingStitchKey}>
                                {isSavingStitchKey ? 'กำลังตรวจสอบ...' : 'บันทึก & ตรวจสอบคีย์'}
                              </button>
                            </div>
                          </div>
                        {/if}

                        {#if showStitchCodeInspector && currentScreenMockup.stitch_html}
                          <div class="stitch-code-drawer" transition:slide>
                            <div class="stitch-code-header">
                              <span>Generated Standalone HTML5 + Tailwind CSS ({currentScreenMockup.stitch_html.length.toLocaleString()} chars)</span>
                              <button type="button" class="btn-save-token" on:click={copyStitchHtml}>คัดลอกโค้ด HTML</button>
                            </div>
                            <pre class="stitch-code-pre">{currentScreenMockup.stitch_html}</pre>
                          </div>
                        {/if}
                      </div>

                      {#if isGeneratingStitch}
                        <div class="stitch-empty-guide">
                          <div class="spinner-small" style="width: 32px; height: 32px; border-width: 3px;"></div>
                          <h4>กำลังออกแบบ High-Fidelity UI สำหรับ "{currentScreenMockup.screen_name}"</h4>
                          <p>ระบบกำลังสร้างหน้าจอที่ตรงตามธุรกิจของโครงการ ({$selectedProjectStore.name || $selectedProjectStore.project_code}) พร้อมผูก Requirements และบันทึกแยกตามโครงการ...</p>
                        </div>
                      {:else if currentScreenMockup.stitch_html}
                        <div class="stitch-iframe-box">
                          <iframe
                            srcdoc={currentScreenMockup.stitch_html}
                            title={`High-Fidelity UI — ${currentScreenMockup.screen_name}`}
                            class="stitch-live-iframe"
                            sandbox="allow-scripts allow-forms allow-modals"
                          ></iframe>
                        </div>
                      {:else}
                        <div class="stitch-empty-guide">
                          <div class="figma-watermark-icon" style="color: #06b6d4;"><QAIcon name="zap" size={38} /></div>
                          <h4>สร้างหน้าจอ High-Fidelity UI เฉพาะทางของโครงการ ({$selectedProjectStore.project_code || 'Project'})</h4>
                          <p>
                            เชื่อมต่อกับ <strong>Google Stitch MCP</strong> (`stitch.googleapis.com/mcp`) พร้อมระบบ <strong>Gemini Live HTML/Tailwind</strong> อัตโนมัติ — แยกดีไซน์และชุดสีแบบ 1-ต่อ-1 ตามโครงการ และเรนเดอร์เป็นหน้าเว็บที่คลิกโต้ตอบได้จริง
                          </p>
                          <button type="button" class="btn-figma-action stitch-gen" style="margin-top: 8px; padding: 9px 18px; font-size: 13px;" on:click={handleGenerateStitchScreen}>
                            <QAIcon name="zap" /> สร้าง High-Fi UI สำหรับหน้าจอนี้ทันที
                          </button>
                        </div>
                      {/if}
                    </div>

                  <!-- MODE 1: FIGMA EMBED / MCP SYNC -->
                  {:else if activeWireframeTab === 'figma'}
                    <div class="figma-container">
                      <div class="figma-config-panel">
                        <div class="figma-input-row">
                          <span class="figma-icon-tag"><QAIcon name="palette" /> Figma Link:</span>
                          <input 
                            type="text" 
                            bind:value={figmaUrlInput} 
                            placeholder="https://www.figma.com/design/.../...?node-id=..." 
                            class="figma-text-input" aria-label="Figma Frame URL" 
                          />
                          <button type="button" class="btn-figma-action connect" on:click={handleSaveFigmaUrl}>
                            <QAIcon name="link" /> Connect & Save
                          </button>
                          <button type="button" class="btn-figma-action sync" on:click={handleSyncFigmaImage} disabled={isSyncingFigma}>
                            {#if isSyncingFigma}
                              <span class="spinner-small"></span> Syncing...
                            {:else}
                              <QAIcon name="refresh" /> Sync MCP / API
                            {/if}
                          </button>
                          <button type="button" class="btn-figma-action token" on:click={() => showFigmaTokenInput = !showFigmaTokenInput} title="Figma Personal Access Token">
                            <QAIcon name="settings" /> Token
                          </button>
                        </div>

                        {#if showFigmaTokenInput}
                          <div class="figma-token-box" transition:slide>
                            <div class="token-title"><QAIcon name="key" /> Figma Access Token (สำหรับดึงภาพอัตโนมัติผ่าน Figma MCP/REST API):</div>
                            <div class="token-form-row">
                              <input 
                                type="password" 
                                bind:value={figmaTokenInput} 
                                placeholder="figd_xxxxxxxxx" 
                                class="figma-token-field" aria-label="Figma Personal Access Token"
                              />
                              <button type="button" class="btn-save-token" on:click={() => { localStorage.setItem('figma_token', figmaTokenInput.trim()); toast('บันทึก Figma Token แล้ว', 'success'); showFigmaTokenInput = false; }}>
                                บันทึก
                              </button>
                            </div>
                          </div>
                        {/if}
                      </div>

                      {#if currentScreenMockup.figma_url}
                        <div class="figma-iframe-box">
                          <iframe 
                            src={getFigmaEmbedUrl(currentScreenMockup.figma_url)} 
                            title="Figma Live Frame" 
                            class="figma-embed-frame"
                            allowfullscreen
                          ></iframe>
                        </div>
                      {:else}
                        <div class="figma-empty-guide">
                          <div class="figma-watermark-icon"><QAIcon name="palette" /></div>
                          <h4>เชื่อมต่อกับ Figma MCP & Live Frame Embed</h4>
                          <p>คัดลอก URL ของ Frame ใน Figma (คลิกขวาที่ Frame ใน Figma &gt; Copy Link) แล้ววางในช่องด้านบน</p>
                        </div>
                      {/if}
                    </div>

                  <!-- MODE 2: UPLOAD IMAGE MOCKUP -->
                  {:else if activeWireframeTab === 'image'}
                    <div class="image-mockup-container">
                      <input 
                        type="file" 
                        accept="image/png, image/jpeg, image/webp, image/svg+xml" 
                        style="display: none;" 
                        bind:this={fileInputRef} 
                        on:change={handleFileUpload} 
                      />

                      {#if currentScreenMockup.image_url}
                        <div class="image-viewport-box">
                          <div class="image-action-toolbar">
                            <span class="img-name-tag" title={currentScreenMockup.image_filename || 'Mockup Screenshot'}><QAIcon name="camera" /><span class="img-name-text">{currentScreenMockup.image_filename || 'Mockup Screenshot'}</span></span>
                            <div class="img-btn-group">
                              <button type="button" class="btn-img-ctrl zoom" on:click={() => lightboxImage = currentScreenMockup.image_url}>
                                <QAIcon name="search" /> ขยายเต็มจอ
                              </button>
                              <button type="button" class="btn-img-ctrl replace" on:click={() => fileInputRef?.click()} disabled={isUploadingImage}>
                                <QAIcon name="refresh" /> เปลี่ยนภาพ
                              </button>
                              <button type="button" class="btn-img-ctrl delete" on:click={handleRemoveImage}>
                                <QAIcon name="trash" /> ลบภาพ
                              </button>
                            </div>
                          </div>
                          <div
                            class="image-display-area"
                            role="button"
                            tabindex="0"
                            aria-label="เปิดดูรูป Wireframe ขนาดเต็ม"
                            on:click={() => lightboxImage = currentScreenMockup.image_url}
                            on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); lightboxImage = currentScreenMockup.image_url; } }}
                          >
                            <img src={`${currentScreenMockup.image_url}`} alt="Screen Wireframe Mockup" class="wireframe-img-render" loading="lazy" decoding="async" />
                          </div>
                        </div>
                      {:else}
                        <div 
                          class="image-upload-dropzone" 
                          class:uploading={isUploadingImage}
                          role="button"
                          tabindex="0"
                          aria-label="อัปโหลดรูปภาพ Screen Mockup"
                          on:click={() => fileInputRef?.click()}
                          on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInputRef?.click(); } }}
                          on:dragover|preventDefault
                          on:drop|preventDefault={(e) => {
                            const file = e.dataTransfer?.files?.[0];
                            if (file) handleFileUpload({ target: { files: [file] } });
                          }}
                        >
                          <div class="drop-icon"><QAIcon name="image" /></div>
                          <h4>อัปโหลดรูปภาพ Screen Mockup / Wireframe</h4>
                          <p>ลากรูปภาพมาวางที่นี่ หรือคลิกเพื่อเลือกไฟล์ (รองรับ PNG, JPG, WebP, SVG)</p>
                          {#if isUploadingImage}
                            <div class="uploading-spinner">
                              <span class="spinner-small"></span> กำลังอัปโหลดภาพ...
                            </div>
                          {:else}
                            <button type="button" class="btn-upload-browse"><QAIcon name="folder" /> เลือกไฟล์ภาพจากเครื่อง</button>
                          {/if}
                        </div>
                      {/if}
                    </div>

                  <!-- MODE 3: AI HIGH-FIDELITY INTERACTIVE PROTOTYPE -->
                  {:else}
                  {@const screenArchetype = detectScreenArchetype(currentScreenMockup)}
                  {@const authTabMode = detectAuthTabMode(activePrototypeTab)}

                  <!-- Mockup Screen Body -->
                  <div class="mockup-screen-content interactive-proto archetype-{screenArchetype}">

                    {#if screenArchetype === 'auth'}
                      <!-- ── ARCHETYPE A: DEDICATED SPLIT AUTHENTICATION UX ── -->
                      <div class="auth-ux-layout">
                        <!-- Left: Brand Identity & Security Trust Panel -->
                        <div class="auth-brand-showcase">
                          <div class="auth-brand-top">
                            <div class="auth-app-logo-row">
                              <div class="auth-app-emblem"><QAIcon name="shield" size={18} /></div>
                              <div>
                                <div class="auth-app-name">{$selectedProjectStore.name || $selectedProjectStore.project_code || 'Application'}</div>
                                <div class="auth-app-route">{currentScreenMockup.route || '/auth/login'}</div>
                              </div>
                              <span class="proto-verified-badge emerald" style="margin-left: auto;">
                                <QAIcon name="sparkles" /> {cleanMockupLabel(currentScreenMockup.header?.badge || 'Security & Auth')}
                              </span>
                            </div>

                            <h3 class="auth-showcase-title">
                              {cleanMockupLabel(currentScreenMockup.header?.title || currentScreenMockup.screen_name)}
                            </h3>
                            <p class="auth-showcase-desc">
                              {currentScreenMockup.description || 'ระบบยืนยันตัวตนและจัดการสิทธิ์การเข้าถึง รองรับผู้ใช้งานทั่วไป ร้านค้าพาร์ทเนอร์ และ Social Login มาตรฐานความปลอดภัยระดับสากล'}
                            </p>
                          </div>

                          {#if currentScreenMockup.stats && currentScreenMockup.stats.length > 0}
                            <div class="auth-trust-grid">
                              {#each currentScreenMockup.stats as st}
                                <div class="auth-trust-item {st.color || 'blue'}">
                                  <div class="trust-lbl">{st.label}</div>
                                  <div class="trust-val">{st.value}</div>
                                  {#if st.sub}<div class="trust-sub">{st.sub}</div>{/if}
                                </div>
                              {/each}
                            </div>
                          {/if}
                        </div>

                        <!-- Right: Focused Single-Column Auth Card -->
                        <div class="auth-card-panel">
                          {#if currentScreenMockup.tabs && currentScreenMockup.tabs.length > 0}
                            <div class="auth-segmented-tabs" role="tablist">
                              {#each currentScreenMockup.tabs as tb}
                                <button
                                  type="button"
                                  role="tab"
                                  aria-selected={activePrototypeTab === tb}
                                  class="auth-seg-tab-btn"
                                  class:active={activePrototypeTab === tb}
                                  on:click={() => { activePrototypeTab = tb; }}>
                                  {cleanMockupLabel(tb)}
                                </button>
                              {/each}
                            </div>
                          {/if}

                          {#if authTabMode === 'register'}
                            <!-- Dynamic Register Tab UX -->
                            <div class="auth-card-head">
                              <h4>สร้างบัญชีผู้ใช้งานใหม่ (Create Account)</h4>
                              <p>กรอกข้อมูลเพื่อสมัครสมาชิกและเริ่มใช้งานระบบ {$selectedProjectStore.name || ''}</p>
                            </div>
                            <div class="auth-vertical-form">
                              <div class="mock-form-item">
                                <label class="mock-label" for="auth-reg-name">ชื่อ-นามสกุล หรือ ชื่อร้านค้า (Full Name / Store) <span class="req-star">*</span></label>
                                <input id="auth-reg-name" type="text" class="proto-real-input" placeholder="เช่น คุณสมชาย ใจดี" bind:value={currentFormValues['reg_name']} />
                              </div>
                              <div class="mock-form-item">
                                <label class="mock-label" for="auth-reg-email">อีเมล หรือ เบอร์โทรศัพท์ (Email / Phone) <span class="req-star">*</span></label>
                                <input id="auth-reg-email" type="text" class="proto-real-input" placeholder="name@example.com หรือ 08x-xxx-xxxx" bind:value={currentFormValues['reg_email']} />
                              </div>
                              <div class="auth-2col-row">
                                <div class="mock-form-item">
                                  <label class="mock-label" for="auth-reg-pw">รหัสผ่าน (Password) <span class="req-star">*</span></label>
                                  <input id="auth-reg-pw" type="password" class="proto-real-input" placeholder="อย่างน้อย 8 ตัวอักษร" bind:value={currentFormValues['reg_pw']} />
                                </div>
                                <div class="mock-form-item">
                                  <label class="mock-label" for="auth-reg-pw2">ยืนยันรหัสผ่าน <span class="req-star">*</span></label>
                                  <input id="auth-reg-pw2" type="password" class="proto-real-input" placeholder="ยืนยันรหัสผ่านอีกครั้ง" bind:value={currentFormValues['reg_pw2']} />
                                </div>
                              </div>
                              <label class="proto-real-checkbox">
                                <input type="checkbox" checked />
                                <span>ยอมรับข้อกำหนดการใช้งานและนโยบายคุ้มครองข้อมูลส่วนบุคคล (PDPA)</span>
                              </label>
                              <button type="button" class="proto-action-btn primary auth-submit-full" on:click={() => handlePrototypeButtonAction({ label: 'สมัครสมาชิกใหม่ (Create Account)', variant: 'primary' })}>
                                <QAIcon name="check" /> สมัครสมาชิกใหม่ (Create Account)
                              </button>
                            </div>

                          {:else if authTabMode === 'forgot'}
                            <!-- Dynamic Forgot Password / OTP Tab UX -->
                            <div class="auth-card-head">
                              <h4>กู้คืนรหัสผ่านด้วย OTP (Password Recovery)</h4>
                              <p>ระบุอีเมลหรือเบอร์โทรศัพท์ที่ลงทะเบียนไว้เพื่อรับรหัส OTP 6 หลัก</p>
                            </div>
                            <div class="auth-vertical-form">
                              <div class="mock-form-item">
                                <label class="mock-label" for="auth-forgot-id">อีเมล หรือ เบอร์โทรศัพท์ที่ลงทะเบียน <span class="req-star">*</span></label>
                                <input id="auth-forgot-id" type="text" class="proto-real-input" placeholder="user@foodsmile.app หรือ 081-234-5678" bind:value={currentFormValues['forgot_identity']} />
                              </div>
                              <div class="mock-form-item">
                                <label class="mock-label" for="auth-forgot-otp">รหัสยืนยัน OTP (6 หลัก)</label>
                                <input id="auth-forgot-otp" type="text" maxlength="6" class="proto-real-input" placeholder="• • • • • •" bind:value={currentFormValues['forgot_otp']} />
                              </div>
                              <button type="button" class="proto-action-btn primary auth-submit-full" on:click={() => handlePrototypeButtonAction({ label: 'ส่งรหัสยืนยัน OTP (Send Recovery Code)', variant: 'primary' })}>
                                <QAIcon name="zap" /> ส่งรหัสยืนยัน OTP (Send Recovery Code)
                              </button>
                              <button type="button" class="proto-action-btn outline auth-submit-full" on:click={() => { activePrototypeTab = currentScreenMockup.tabs?.[0] || ''; }}>
                                <QAIcon name="back" /> กลับไปหน้าเข้าสู่ระบบ (Back to Sign In)
                              </button>
                            </div>

                          {:else}
                            <!-- Primary Sign In Tab UX (Single-Column Clean Auth Flow) -->
                            {@const authFormSec = (currentScreenMockup.sections || []).find(s => s.type === 'form' || s.fields) || { fields: [], buttons: [] }}
                            {@const textFields = (authFormSec.fields || []).filter(f => f.type !== 'toggle' && f.type !== 'checkbox')}
                            {@const toggleFields = (authFormSec.fields || []).filter(f => f.type === 'toggle' || f.type === 'checkbox')}
                            {@const allBtns = authFormSec.buttons || []}
                            {@const primaryAuthBtns = allBtns.filter(b => !/google|line|facebook|apple/i.test(String(b.label || '')))}
                            {@const socialAuthBtns = allBtns.filter(b => /google|line|facebook|apple/i.test(String(b.label || '')))}

                            <div class="auth-card-head">
                              <div class="auth-card-title-row">
                                <h4>{cleanMockupLabel(authFormSec.section_name || 'เข้าสู่ระบบ (Sign In)')}</h4>
                                <span class="proto-interactive-tag"><QAIcon name="zap" /> Live Editable</span>
                              </div>
                              <p>กรอกข้อมูลบัญชีของคุณเพื่อเข้าใช้งานระบบ</p>
                            </div>

                            <div class="auth-vertical-form">
                              {#each textFields as f, fIdx}
                                {@const pwKey = `auth_${fIdx}`}
                                {@const isPw = f.type === 'password' || /password|รหัสผ่าน/i.test(f.label || '')}
                                <div class="mock-form-item">
                                  <label class="mock-label" for="auth-fld-{fIdx}">
                                    {cleanMockupLabel(f.label)} {#if f.required}<span class="req-star">*</span>{/if}
                                  </label>
                                  <div class="proto-input-wrapper">
                                    <input
                                      type={isPw && !revealedPasswords[pwKey] ? 'password' : 'text'}
                                      id="auth-fld-{fIdx}"
                                      class="proto-real-input"
                                      class:has-two-icons={isPw}
                                      placeholder={f.placeholder || cleanMockupLabel(f.label)}
                                      bind:value={currentFormValues[f.label]}
                                    />
                                    {#if isPw}
                                      <button
                                        type="button"
                                        class="btn-input-eye"
                                        on:click={() => togglePasswordVisibility(pwKey)}
                                        title={revealedPasswords[pwKey] ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'}
                                        aria-label={revealedPasswords[pwKey] ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'}>
                                        <QAIcon name="eye" size={13} />
                                      </button>
                                    {/if}
                                    {#if currentFormValues[f.label]}
                                      <button
                                        type="button"
                                        class="btn-input-clear"
                                        on:click={() => currentFormValues[f.label] = ''}
                                        title="ล้างข้อมูล" aria-label="ล้างข้อมูล">
                                        <QAIcon name="close" size={12} />
                                      </button>
                                    {/if}
                                  </div>
                                </div>
                              {/each}

                              <div class="auth-utility-row">
                                {#if toggleFields.length > 0}
                                  {#each toggleFields as tf}
                                    <label class="proto-switch-inline">
                                      <span class="proto-switch">
                                        <input type="checkbox" bind:checked={currentFormValues[tf.label]} />
                                        <span class="switch-slider"></span>
                                      </span>
                                      <span class="toggle-status-text">{cleanMockupLabel(tf.label)}</span>
                                    </label>
                                  {/each}
                                {:else}
                                  <label class="proto-switch-inline">
                                    <span class="proto-switch">
                                      <input type="checkbox" checked />
                                      <span class="switch-slider"></span>
                                    </span>
                                    <span class="toggle-status-text">จดจำการเข้าสู่ระบบ</span>
                                  </label>
                                {/if}

                                <button
                                  type="button"
                                  class="auth-forgot-link"
                                  on:click={() => {
                                    const forgotTab = (currentScreenMockup.tabs || []).find(t => /forgot|ลืมรหัส/i.test(t));
                                    if (forgotTab) activePrototypeTab = forgotTab;
                                    else handlePrototypeHeaderAction('ลืมรหัสผ่าน');
                                  }}>
                                  ลืมรหัสผ่าน?
                                </button>
                              </div>

                              {#each (primaryAuthBtns.length > 0 ? primaryAuthBtns : [{ label: 'เข้าสู่ระบบทันที (Sign In)', variant: 'primary' }]) as btn}
                                <button
                                  type="button"
                                  class="proto-action-btn primary auth-submit-full"
                                  disabled={isSimulatingSubmit}
                                  on:click={() => handlePrototypeButtonAction(btn)}>
                                  {#if isSimulatingSubmit}
                                    <span class="spinner-small"></span> กำลังตรวจสอบสิทธิ์...
                                  {:else}
                                    <QAIcon name="lock" size={14} />
                                    <span>{cleanMockupLabel(btn.label)}</span>
                                  {/if}
                                </button>
                              {/each}

                              {#if socialAuthBtns.length > 0}
                                <div class="auth-social-divider">
                                  <span>หรือเชื่อมต่อด้วยบัญชีโซเชียล (Social Login)</span>
                                </div>
                                <div class="auth-social-grid">
                                  {#each socialAuthBtns as sbtn}
                                    {@const sClass = classifyActionButton(sbtn, true)}
                                    <button
                                      type="button"
                                      class="proto-action-btn {sClass}"
                                      on:click={() => handlePrototypeButtonAction(sbtn)}>
                                      {#if sClass === 'brand-google'}
                                        <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true">
                                          <path fill="#EA4335" d="M12 10.2v3.9h5.4c-.2 1.3-1.6 3.8-5.4 3.8-3.3 0-6-2.7-6-6s2.7-6 6-6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.4 14.6 2.5 12 2.5 6.8 2.5 2.5 6.8 2.5 12s4.3 9.5 9.5 9.5c5.5 0 9.1-3.9 9.1-9.3 0-.6-.1-1.1-.2-1.6H12z"/>
                                          <path fill="#34A853" d="M3.6 7.4l3.2 2.4C7.7 7.6 9.7 6 12 6c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.8 3.4 14.6 2.5 12 2.5 8.3 2.5 5.1 4.6 3.6 7.4z"/>
                                          <path fill="#FBBC05" d="M12 21.5c2.5 0 4.7-.8 6.2-2.3l-2.9-2.4c-.8.6-1.9 1-3.3 1-2.5 0-4.7-1.7-5.4-4l-3.2 2.5c1.5 3.1 4.8 5.2 8.6 5.2z"/>
                                          <path fill="#4285F4" d="M21.1 12.2c0-.6-.1-1.1-.2-1.6H12v3.9h5.4c-.3 1.3-1 2.3-2.1 3l2.9 2.4c1.7-1.6 2.9-4.1 2.9-7.7z"/>
                                        </svg>
                                      {:else if sClass === 'brand-line'}
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                          <path d="M19.365 9.863c.349 0 .63.285.63.631 0 .345-.281.63-.63.63H17.61v1.125h1.755c.349 0 .63.283.63.63 0 .344-.281.629-.63.629h-2.386c-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63h2.386c.346 0 .627.285.627.63 0 .349-.281.63-.63.63H17.61v1.125h1.755zm-3.855 3.016c0 .27-.174.51-.432.596-.064.021-.133.031-.199.031-.211 0-.391-.09-.51-.25l-2.443-3.317v2.94c0 .344-.279.629-.631.629-.346 0-.626-.285-.626-.629V8.108c0-.27.173-.51.43-.595.06-.023.136-.033.194-.033.195 0 .375.104.495.254l2.462 3.33V8.108c0-.345.282-.63.63-.63.345 0 .63.285.63.63v4.771zm-5.741 0c0 .344-.282.629-.631.629-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63.346 0 .628.285.628.63v4.771zm-2.466.629H4.917c-.345 0-.63-.285-.63-.629V8.108c0-.345.285-.63.63-.63.348 0 .63.285.63.63v4.141h1.756c.348 0 .629.283.629.63 0 .344-.282.629-.629.629M24 10.314C24 4.943 18.615.572 12 .572S0 4.943 0 10.314c0 4.811 4.27 8.842 10.035 9.608.391.082.923.258 1.058.59.12.301.079.766.038 1.08l-.164 1.02c-.045.301-.24 1.186 1.049.645 1.291-.539 6.916-4.078 9.436-6.975C23.176 14.393 24 12.458 24 10.314"/>
                                        </svg>
                                      {:else}
                                        <QAIcon name="key" size={14} />
                                      {/if}
                                      <span>{cleanMockupLabel(sbtn.label)}</span>
                                    </button>
                                  {/each}
                                </div>
                              {/if}
                            </div>
                          {/if}
                        </div>
                      </div>

                      <!-- Secondary Audit / Active Sessions Tables on Auth Screen -->
                      {#each (currentScreenMockup.sections || []).filter(s => s.type === 'table' || s.table_headers) as sec, tIdx}
                        {@const realSecIdx = (currentScreenMockup.sections || []).indexOf(sec)}
                        {@const rowsList = getInteractiveTableRows(sec, realSecIdx)}
                        <div class="proto-section-card table">
                          <div class="proto-sec-header">
                            <div class="mock-sec-title"><QAIcon name="shield" /> {cleanMockupLabel(sec.section_name || 'Active Sessions & Security Log')}</div>
                            <div class="table-header-tools">
                              <input
                                type="text"
                                class="proto-table-search"
                                placeholder="ค้นหาอุปกรณ์ / IP / สถานะ..."
                                bind:value={tableSearchQuery}
                                aria-label="ค้นหาในตาราง"
                              />
                              <span class="proto-count-badge">{rowsList.length} รายการ</span>
                            </div>
                          </div>
                          <div class="mock-table-wrap">
                            <table class="mock-table proto-table">
                              <thead>
                                <tr>
                                  {#each (sec.table_headers || ['อุปกรณ์', 'ระบบปฏิบัติการ', 'IP / ที่ตั้ง', 'สถานะ', 'การจัดการ']) as th}
                                    <th>{th}</th>
                                  {/each}
                                </tr>
                              </thead>
                              <tbody>
                                {#each rowsList as row, rIdx}
                                  <tr class="proto-table-row">
                                    {#each row as cell, cellIdx}
                                      <td>
                                        {#if /ออนไลน์|ใช้งานเมื่อ|พร้อม|Active|สำเร็จ/i.test(String(cell))}
                                          <span class="table-pill success"><QAIcon name="dot" size={10} /> {cleanMockupLabel(cell)}</span>
                                        {:else if /ออกจากระบบแล้ว|หมดอายุ|ปิด/i.test(String(cell))}
                                          <span class="table-pill muted">{cleanMockupLabel(cell)}</span>
                                        {:else if /รอ|Pending/i.test(String(cell))}
                                          <span class="table-pill warning"><QAIcon name="clock" size={12} /> {cleanMockupLabel(cell)}</span>
                                        {:else if cellIdx === row.length - 1}
                                          <button type="button" class="btn-table-action" on:click={() => handleTableActionClick(cell, row, realSecIdx, rIdx)}>
                                            <QAIcon name="zap" /> {cleanMockupLabel(cell)}
                                          </button>
                                        {:else}
                                          <span class="table-cell-text">{cell}</span>
                                        {/if}
                                      </td>
                                    {/each}
                                  </tr>
                                {/each}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      {/each}

                    {:else}
                      <!-- ── ARCHETYPES B/C/D: DISCOVERY, REVIEW & STANDARD APP SCREENS ── -->
                      <!-- Screen Hero / Header Bar -->
                      <div class="proto-hero-card">
                        <div class="proto-hero-top-flex">
                          <div class="proto-hero-main">
                            <div class="proto-title-badge-row">
                              <h3 class="proto-screen-title">
                                {cleanMockupLabel(currentScreenMockup.header?.title || currentScreenMockup.screen_name)}
                              </h3>
                              {#if currentScreenMockup.header?.badge}
                                <span class="proto-verified-badge {currentScreenMockup.header.badge_color || 'emerald'}">
                                  <QAIcon name="sparkles" /> {cleanMockupLabel(currentScreenMockup.header.badge)}
                                </span>
                              {:else}
                                <span class="proto-verified-badge emerald">
                                  <QAIcon name="sparkles" /> Production Ready
                                </span>
                              {/if}
                            </div>
                            <p class="proto-desc-text">
                              {currentScreenMockup.description || 'Interactive prototype screen wired with live form inputs, dynamic state management, and functional UI components.'}
                            </p>
                          </div>

                          <div class="proto-header-action-toolbar">
                            {#if currentScreenMockup.header?.actions && currentScreenMockup.header.actions.length > 0}
                              {#each currentScreenMockup.header.actions as rawAct}
                                {@const act = cleanMockupLabel(rawAct)}
                                <button 
                                  type="button"
                                  class="btn-proto-header-action" 
                                  class:fav={act.includes('โปรด') || act.includes('favorite') || act.includes('like')}
                                  class:favorited={isFavorite && (act.includes('โปรด') || act.includes('favorite') || act.includes('like'))}
                                  on:click={() => handlePrototypeHeaderAction(act)}>
                                  {#if act.includes('แชร์') || act.includes('share')}
                                    <QAIcon name="link" /> {act}
                                  {:else if act.includes('โปรด') || act.includes('favorite') || act.includes('like')}
                                    <QAIcon name="star" size={14} filled={isFavorite} /> {isFavorite ? 'บันทึกเป็นรายการโปรดแล้ว' : act}
                                  {:else if act.includes('ย้อน') || act.includes('back')}
                                    <QAIcon name="back" /> {act}
                                  {:else if act.includes('เข้าสู่ระบบ') || act.includes('login') || act.includes('sign in')}
                                    <QAIcon name="play" /> {act}
                                  {:else if act.includes('ค้นหา') || act.includes('search')}
                                    <QAIcon name="search" /> {act}
                                  {:else if act.includes('บันทึก') || act.includes('save')}
                                    <QAIcon name="save" /> {act}
                                  {:else if act.includes('แผนที่') || act.includes('นำทาง') || act.includes('map')}
                                    <QAIcon name="compass" /> {act}
                                  {:else}
                                    <QAIcon name="zap" /> {act}
                                  {/if}
                                </button>
                              {/each}
                            {:else}
                              <button type="button" class="btn-proto-header-action" on:click={() => handlePrototypeHeaderAction('รีเฟรช')}>
                                <QAIcon name="refresh" /> รีเฟรช
                              </button>
                            {/if}
                          </div>
                        </div>

                        {#if screenArchetype === 'discovery'}
                          <!-- Discovery Category & Map/List Filter Bar -->
                          <div class="discovery-filter-strip">
                            <div class="discovery-chips">
                              {#each ['ทั้งหมด', 'ยอดนิยม ★ 4.5+', 'ใกล้ฉัน (< 3 กม.)', 'เปิดอยู่ตอนนี้', 'โปรโมชันพิเศษ'] as cat}
                                <button
                                  type="button"
                                  class="discovery-chip"
                                  class:active={discoveryCategory === cat}
                                  on:click={() => { discoveryCategory = cat; toast(`กรองหมวดหมู่: ${cat}`, 'info'); }}>
                                  {cat}
                                </button>
                              {/each}
                            </div>
                            <button
                              type="button"
                              class="btn-proto-header-action"
                              on:click={() => showSimulatedMap = !showSimulatedMap}>
                              <QAIcon name="compass" /> {showSimulatedMap ? 'ซ่อนแผนที่ GPS' : 'แสดงแผนที่ GPS'}
                            </button>
                          </div>
                        {:else if screenArchetype === 'review'}
                          <!-- Interactive Live 5-Star Rating Picker Banner -->
                          <div class="live-rating-banner">
                            <span class="rating-banner-label">ให้คะแนนความพึงพอใจ (คลิกเลือกดาว):</span>
                            <div class="interactive-stars-row">
                              {#each [1, 2, 3, 4, 5] as starNum}
                                <button
                                  type="button"
                                  class="star-pick-btn"
                                  class:active={starNum <= interactiveRating}
                                  aria-label={`ให้คะแนน ${starNum} ดาว`}
                                  on:click={() => { interactiveRating = starNum; toast(`เลือกคะแนน ${starNum}.0 ดาว`, 'info'); }}>
                                  <QAIcon name="star" size={18} filled={starNum <= interactiveRating} />
                                </button>
                              {/each}
                              <span class="rating-score-pill">{interactiveRating}.0 / 5.0</span>
                            </div>
                          </div>
                        {/if}
                      </div>

                      <!-- KPI / Summary Metric Cards Grid -->
                      {#if currentScreenMockup.stats && currentScreenMockup.stats.length > 0}
                        <div class="proto-stats-grid">
                          {#each currentScreenMockup.stats as st}
                            <div class="proto-stat-card {st.color || 'blue'}">
                              <div class="stat-card-label">{st.label}</div>
                              <div class="stat-card-value">{st.value}</div>
                              {#if st.sub}
                                <div class="stat-card-sub">{st.sub}</div>
                              {/if}
                            </div>
                          {/each}
                        </div>
                      {/if}

                      {#if screenArchetype === 'discovery' && showSimulatedMap}
                        <!-- Interactive GPS Map Radar Strip for Discovery / Home & Map Search -->
                        <div class="discovery-map-card">
                          <div class="discovery-map-header">
                            <span><QAIcon name="compass" /> แผนที่พิกัดและการค้นหาในพื้นที่ ({discoveryCategory})</span>
                            <span class="proto-interactive-tag">GPS Live Radar</span>
                          </div>
                          <div class="discovery-map-canvas">
                            <div class="map-grid-lines"></div>
                            <button type="button" class="map-pin-chip p1" on:click={() => toast('เลือกพิกัด: สาขาสยามพารากอน (★ 4.9 • 0.8 กม.)', 'info')}>
                              📍 สาขาสยาม (★ 4.9)
                            </button>
                            <button type="button" class="map-pin-chip p2" on:click={() => toast('เลือกพิกัด: สาขาอารีย์ (★ 4.7 • 1.5 กม.)', 'info')}>
                              📍 สาขาอารีย์ (★ 4.7)
                            </button>
                            <button type="button" class="map-pin-chip p3" on:click={() => toast('เลือกพิกัด: สาขาทองหล่อ (★ 4.8 • 2.4 กม.)', 'info')}>
                              📍 สาขาทองหล่อ (★ 4.8)
                            </button>
                            <div class="map-user-you">ตำแหน่งของคุณ</div>
                          </div>
                        </div>
                      {/if}

                      <!-- Interactive Tabs Bar -->
                      {#if currentScreenMockup.tabs && currentScreenMockup.tabs.length > 0}
                        <div class="proto-tabs-navbar" role="tablist">
                          {#each currentScreenMockup.tabs as tb}
                            <button 
                              type="button"
                              role="tab"
                              aria-selected={activePrototypeTab === tb}
                              class="proto-nav-tab-btn" 
                              class:active={activePrototypeTab === tb} 
                              on:click={() => { activePrototypeTab = tb; }}>
                              {cleanMockupLabel(tb)}
                            </button>
                          {/each}
                        </div>
                      {/if}

                      <!-- Dynamic Sections Stack -->
                      <div class="mockup-sections-stack">
                        {#if currentScreenMockup.sections}
                          {#each currentScreenMockup.sections as sec, secIdx}
                            
                            <!-- SECTION: GALLERY / BANNER -->
                            {#if (sec.type === 'gallery' || sec.images) && sec.images && sec.images.length > 0}
                              <div class="proto-section-card gallery">
                                <div class="proto-sec-header">
                                  <div class="mock-sec-title"><QAIcon name="image" /> {cleanMockupLabel(sec.section_name || 'Image Gallery & Highlights')}</div>
                                  {#if sec.banner_tag}
                                    <span class="proto-tag-highlight">{sec.banner_tag}</span>
                                  {/if}
                                </div>
                                <div class="proto-gallery-grid">
                                  {#each sec.images as img, idx}
                                    <div
                                      class="gallery-photo-card"
                                      role="button"
                                      tabindex="0"
                                      on:click={() => toast(`ดูภาพขยาย: ${img.title}`, 'info')}
                                      on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toast(`ดูภาพขยาย: ${img.title}`, 'info'); } }}
                                    >
                                      <div class="photo-visual-placeholder grad-{idx % 4}">
                                        <span class="photo-cam-icon"><QAIcon name="camera" /></span>
                                        <span class="photo-badge">HD View</span>
                                      </div>
                                      <div class="photo-card-info">
                                        <div class="photo-title">{img.title}</div>
                                        <div class="photo-desc">{img.desc}</div>
                                      </div>
                                    </div>
                                  {/each}
                                </div>
                              </div>

                            <!-- SECTION: INTERACTIVE FORM -->
                            {:else if sec.type === 'form' || sec.fields}
                              {@const fieldCount = (sec.fields || []).length}
                              <div class="proto-section-card form">
                                <div class="proto-sec-header">
                                  <div class="mock-sec-title"><QAIcon name="edit" /> {cleanMockupLabel(sec.section_name || 'Interactive Form Details')}</div>
                                  <span class="proto-interactive-tag"><QAIcon name="zap" /> Live Editable</span>
                                </div>

                                <div class="mock-form-grid" class:single-col-form={fieldCount <= 2}>
                                  {#each (sec.fields || []) as f, fIdx}
                                    {@const pwKey = `${secIdx}_${fIdx}`}
                                    {@const isPw = f.type === 'password' || /password|รหัสผ่าน/i.test(f.label || '')}
                                    <div
                                      class="mock-form-item"
                                      class:full-width={f.type === 'textarea' || f.type === 'toggle' || f.type === 'checkbox' || (f.label && /ที่อยู่|รายละเอียด|หมายเหตุ|ความเห็น/.test(f.label)) || (fieldCount % 2 === 1 && fIdx === fieldCount - 1)}
                                    >
                                      <label class="mock-label" for="fld-{secIdx}-{fIdx}">
                                        {cleanMockupLabel(f.label)} {#if f.required}<span class="req-star">*</span>{/if}
                                      </label>

                                      {#if f.type === 'toggle' || (f.label && f.label.includes('เปิดรับ'))}
                                        <div class="proto-toggle-wrap">
                                          <label class="proto-switch">
                                            <input 
                                              type="checkbox" 
                                              bind:checked={currentFormValues[f.label]}
                                            />
                                            <span class="switch-slider"></span>
                                          </label>
                                          <span class="toggle-status-text">
                                            {currentFormValues[f.label] ? 'เปิดใช้งาน (Active)' : 'ปิดใช้งาน (Disabled)'}
                                          </span>
                                        </div>

                                      {:else if f.type === 'select' || f.options}
                                        <div class="proto-input-wrapper">
                                          <select 
                                            id="fld-{secIdx}-{fIdx}"
                                            class="proto-real-select"
                                            bind:value={currentFormValues[f.label]}
                                          >
                                            {#each (f.options || ['ตัวเลือก 1', 'ตัวเลือก 2', 'ตัวเลือก 3']) as opt}
                                              <option value={opt}>{opt}</option>
                                            {/each}
                                          </select>
                                        </div>

                                      {:else if f.type === 'textarea' || (f.label && f.label.includes('ที่อยู่'))}
                                        <textarea 
                                          id="fld-{secIdx}-{fIdx}"
                                          class="proto-real-textarea"
                                          rows="3"
                                          placeholder={f.placeholder || cleanMockupLabel(f.label)}
                                          bind:value={currentFormValues[f.label]}
                                        ></textarea>

                                      {:else if f.type === 'checkbox'}
                                        <label class="proto-real-checkbox">
                                          <input 
                                            type="checkbox" 
                                            bind:checked={currentFormValues[f.label]} 
                                          />
                                          <span>{cleanMockupLabel(f.label)}</span>
                                        </label>

                                      {:else}
                                        <div class="proto-input-wrapper">
                                          <input 
                                            type={isPw && !revealedPasswords[pwKey] ? 'password' : 'text'}
                                            id="fld-{secIdx}-{fIdx}"
                                            class="proto-real-input"
                                            class:has-two-icons={isPw}
                                            placeholder={f.placeholder || cleanMockupLabel(f.label)}
                                            bind:value={currentFormValues[f.label]}
                                          />
                                          {#if isPw}
                                            <button
                                              type="button"
                                              class="btn-input-eye"
                                              on:click={() => togglePasswordVisibility(pwKey)}
                                              title={revealedPasswords[pwKey] ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'}
                                              aria-label={revealedPasswords[pwKey] ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'}>
                                              <QAIcon name="eye" size={13} />
                                            </button>
                                          {/if}
                                          {#if currentFormValues[f.label]}
                                            <button 
                                              type="button"
                                              class="btn-input-clear" 
                                              on:click={() => currentFormValues[f.label] = ''} 
                                              title="ล้างข้อมูล" aria-label="ล้างข้อมูล"><QAIcon name="close" size={12} /></button>
                                          {/if}
                                        </div>
                                      {/if}
                                    </div>
                                  {/each}
                                </div>

                                <!-- Action Buttons Row (Zero Duplicate Emojis!) -->
                                {#if sec.buttons && sec.buttons.length > 0}
                                  <div class="mock-btn-row">
                                    {#each sec.buttons as btn}
                                      {@const btnVariant = classifyActionButton(btn, false)}
                                      {@const cleanBtnText = cleanMockupLabel(btn.label)}
                                      <button 
                                        type="button"
                                        class="proto-action-btn {btnVariant}"
                                        disabled={isSimulatingSubmit}
                                        on:click={() => handlePrototypeButtonAction(btn)}>
                                        {#if isSimulatingSubmit && (btnVariant.includes('primary') || cleanBtnText.includes('สั่ง'))}
                                          <span class="spinner-small"></span> กำลังประมวลผล...
                                        {:else}
                                          {#if btnVariant === 'brand-google'}
                                            <QAIcon name="globe" size={14} />
                                          {:else if btnVariant === 'brand-line'}
                                            <QAIcon name="send" size={14} />
                                          {:else if btnVariant === 'danger'}
                                            <QAIcon name="trash" size={14} />
                                          {:else if btnVariant === 'map'}
                                            <QAIcon name="compass" size={14} />
                                          {:else if btnVariant.includes('primary')}
                                            <QAIcon name="check" size={14} />
                                          {:else}
                                            <QAIcon name="zap" size={14} />
                                          {/if}
                                          <span>{cleanBtnText}</span>
                                        {/if}
                                      </button>
                                    {/each}
                                  </div>
                                {/if}
                              </div>

                            <!-- SECTION: DATA TABLE -->
                            {:else if sec.type === 'table' || sec.table_headers}
                              {@const rowsList = getInteractiveTableRows(sec, secIdx)}
                              <div class="proto-section-card table">
                                <div class="proto-sec-header">
                                  <div class="mock-sec-title"><QAIcon name="chart" /> {cleanMockupLabel(sec.section_name || 'Data Table Overview')}</div>
                                  <div class="table-header-tools">
                                    {#if (sec.table_rows || []).length > 1}
                                      <input
                                        type="text"
                                        class="proto-table-search"
                                        placeholder="ค้นหาในตาราง..."
                                        bind:value={tableSearchQuery}
                                        aria-label="ค้นหาในตาราง"
                                      />
                                    {/if}
                                    <span class="proto-count-badge">{rowsList.length} รายการ</span>
                                  </div>
                                </div>

                                <div class="mock-table-wrap">
                                  <table class="mock-table proto-table">
                                    <thead>
                                      <tr>
                                        {#each (sec.table_headers || ['รหัส', 'ชื่อรายการ', 'หมวดหมู่', 'ราคา', 'สถานะ', 'จัดการ']) as th}
                                          <th>{th}</th>
                                        {/each}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {#each rowsList as row, rIdx}
                                        <tr class="proto-table-row">
                                          {#each row as cell, cellIdx}
                                            <td>
                                              {#if /ออนไลน์|ใช้งานเมื่อ|พร้อม|Active|สำเร็จ/i.test(String(cell))}
                                                <span class="table-pill success"><QAIcon name="dot" size={10} /> {cleanMockupLabel(cell)}</span>
                                              {:else if /ออกจากระบบแล้ว|หมดอายุ|ปิด/i.test(String(cell))}
                                                <span class="table-pill muted">{cleanMockupLabel(cell)}</span>
                                              {:else if /รอ|Pending/i.test(String(cell))}
                                                <span class="table-pill warning"><QAIcon name="clock" size={12} /> {cleanMockupLabel(cell)}</span>
                                              {:else if String(cell).startsWith('#')}
                                                <span class="table-code-badge">{cell}</span>
                                              {:else if cellIdx === row.length - 1}
                                                <button type="button" class="btn-table-action" on:click={() => handleTableActionClick(cell, row, secIdx, rIdx)}>
                                                  <QAIcon name="zap" /> {cleanMockupLabel(cell)}
                                                </button>
                                              {:else}
                                                <span class="table-cell-text">{cell}</span>
                                              {/if}
                                            </td>
                                          {/each}
                                        </tr>
                                      {/each}
                                    </tbody>
                                  </table>
                                </div>
                              </div>

                            <!-- SECTION: REVIEWS & FEEDBACK -->
                            {:else if sec.type === 'reviews' || sec.reviews}
                              <div class="proto-section-card reviews">
                                <div class="proto-sec-header">
                                  <div class="mock-sec-title">{cleanMockupLabel(sec.section_name || 'User Feedback & Notes')}</div>
                                  <button type="button" class="btn-write-review-sm" on:click={() => handlePrototypeButtonAction({ label: 'เพิ่มความคิดเห็น' })}>
                                    + เพิ่มความคิดเห็น
                                  </button>
                                </div>

                                <div class="proto-reviews-list">
                                  {#each (sec.reviews || [{ user: 'QA Reviewer', rating: 5, comment: 'ตรวจสอบการแสดงผลและ Flow การทำงานของหน้าจอนี้เรียบร้อย', time: '1 ชม. ที่แล้ว' }, { user: 'Product Owner', rating: 5, comment: 'โครงสร้างข้อมูลและ Validation สอดคล้องกับ Requirement ของโครงการ', time: 'เมื่อวานนี้' }]) as rev}
                                    <div class="review-comment-card">
                                      <div class="rev-user-header">
                                        <div class="rev-avatar" aria-hidden="true"><QAIcon name="user" size={16} /></div>
                                        <div class="rev-user-meta">
                                          <div class="rev-name">{rev.user}</div>
                                          <div class="rev-time">{rev.time || 'เมื่อสักครู่'}</div>
                                        </div>
                                        <div class="rev-stars">
                                          {#each Array(Math.max(0, Math.min(5, Number(rev.rating) || 5))) as _}<QAIcon name="star" size={12} filled />{/each}
                                        </div>
                                      </div>
                                      <p class="rev-comment-text">{rev.comment}</p>
                                    </div>
                                  {/each}
                                </div>
                              </div>

                            <!-- FALLBACK SECTION CARD -->
                            {:else}
                              <div class="proto-section-card generic">
                                {#if sec.section_name}
                                  <div class="mock-sec-title"><QAIcon name="package" /> {cleanMockupLabel(sec.section_name)}</div>
                                {/if}
                                <div class="proto-generic-content">
                                  <p style="color: #cbd5e1; font-size: 12px; margin: 0 0 10px 0;">{sec.description || 'Interactive section component with dynamic controls.'}</p>
                                </div>
                              </div>
                            {/if}

                          {/each}
                        {/if}
                      </div>
                    {/if}

                    <!-- Connected Entities Footbar -->
                    <div class="mockup-footbar">
                      <div class="conn-item">
                        <b><QAIcon name="link" /> Connected Use Cases:</b> 
                        {#if currentScreenMockup.connected_use_cases}
                          {#each currentScreenMockup.connected_use_cases as uc}
                            <span class="tag-pill">{uc}</span>
                          {/each}
                        {:else}
                          <span style="color: #94a3b8;">-</span>
                        {/if}
                      </div>
                      <div class="conn-item">
                        <b><QAIcon name="clipboard" /> Requirements:</b> 
                        {#if currentScreenMockup.connected_req_codes}
                          {#each currentScreenMockup.connected_req_codes as req}
                            <span class="tag-pill req">{req}</span>
                          {/each}
                        {:else}
                          <span style="color: #94a3b8;">-</span>
                        {/if}
                      </div>
                    </div>
                  </div>
                {/if}
                </div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Prototype Simulation Dialog Modal -->
        {#if activePrototypeModal}
          <div class="lightbox-backdrop" transition:fade={{ duration: 160 }} role="presentation" on:click={() => activePrototypeModal = null}>
            <div class="prototype-dialog-modal" role="dialog" aria-modal="true" aria-labelledby="proto-dialog-title" tabindex="-1" use:modalFocus on:click|stopPropagation>
              <div class="proto-dialog-header {activePrototypeModal.type}">
                <div class="proto-dialog-title" id="proto-dialog-title">{activePrototypeModal.title}</div>
                <button type="button" class="lightbox-close" aria-label="ปิดหน้าต่าง" on:click={() => activePrototypeModal = null}><QAIcon name="close" size={14} /></button>
              </div>
              <div class="proto-dialog-body">
                {#if activePrototypeModal.type === 'success'}
                  <div class="dialog-icon-huge" aria-hidden="true"><QAIcon name="check" size={40} strokeWidth={2.4} /></div>
                  <p class="dialog-body-text">{activePrototypeModal.content}</p>
                  <div class="dialog-success-badge">HTTP 200 OK • State Updated</div>
                {:else if activePrototypeModal.type === 'map'}
                  <div class="dialog-map-preview">
                    <div class="simulated-map-box">
                      <div class="map-route-line"></div>
                      <div class="map-pin start">จุดเริ่มต้นของคุณ</div>
                      <div class="map-pin end">จุดหมายปลายทาง</div>
                    </div>
                  </div>
                  <p class="dialog-body-text">{activePrototypeModal.content}</p>
                {:else if activePrototypeModal.type === 'review'}
                  <div class="dialog-review-form">
                    <div class="star-rating-selector" aria-label="คะแนน 5 จาก 5">
                      <span class="star-sel active" aria-hidden="true"><QAIcon name="star" size={22} filled /></span>
                      <span class="star-sel active" aria-hidden="true"><QAIcon name="star" size={22} filled /></span>
                      <span class="star-sel active" aria-hidden="true"><QAIcon name="star" size={22} filled /></span>
                      <span class="star-sel active" aria-hidden="true"><QAIcon name="star" size={22} filled /></span>
                      <span class="star-sel active" aria-hidden="true"><QAIcon name="star" size={22} filled /></span>
                      <span class="star-score-tag">5.0 (ยอดเยี่ยม)</span>
                    </div>
                    <textarea class="proto-real-textarea" rows="3" aria-label="ความคิดเห็น" placeholder="พิมพ์ความคิดเห็นของคุณที่นี่..."></textarea>
                  </div>
                {/if}
              </div>
              <div class="proto-dialog-footer">
                <button type="button" class="proto-btn-dialog-close" on:click={() => { toast('บันทึกการดำเนินการเรียบร้อย', 'success'); activePrototypeModal = null; }}>
                  ตกลง / ดำเนินการต่อ
                </button>
              </div>
            </div>
          </div>
        {/if}

      <!-- TAB 2, 3, 4, 5: SYSTEM FLOWCHART & UML DIAGRAMS -->
      {:else if activeTab === 'flowchart' || activeTab === 'usecase' || activeTab === 'activity' || activeTab === 'sequence'}
        <div class="diagram-workspace" role="tabpanel" id="qa-tabpanel" aria-labelledby="qa-tab-{activeTab}" class:fullscreen-diagram={isFullscreenDiagram} in:fly={{ y: 12, duration: 240, easing: cubicOut }}>
          <!-- Controls bar -->
          <div class="diagram-toolbar" class:drawio-toolbar={activeTab === 'flowchart'}>
            <div class="diagram-title">
              {#if activeTab === 'flowchart'}
                <span class="drawio-tag-badge">Draw.io Canvas</span>
                <span>System Workflow Flowchart (ผังการทำงานทั้งระบบ)</span>
              {:else if activeTab === 'usecase'}
                <span>Use Case Diagram (Actors & Functional Boundaries)</span>
              {:else if activeTab === 'activity'}
                <span>Activity & Decision Flow Diagram</span>
              {:else if activeTab === 'sequence'}
                <span>Sequence & Component Architecture Flow</span>
              {/if}
            </div>

            <div class="diagram-toolbar-actions">
              {#if activeTab === 'flowchart'}
                <button 
                  type="button"
                  class="btn-ctrl-action grid" 
                  class:active={showDrawioGrid} 
                  on:click={() => showDrawioGrid = !showDrawioGrid} 
                  title="เปิด/ปิดเส้นตาราง Grid แบบ Draw.io">
                  Grid {showDrawioGrid ? 'ON' : 'OFF'}
                </button>
              {/if}

              <button 
                type="button"
                class="btn-ctrl-action edit-code" 
                class:active={showMermaidEditor} 
                on:click={toggleMermaidEditor} 
                title="เปิดแก้ไขโค้ด Mermaid และบันทึกลงฐานข้อมูลโครงการ">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="16 18 22 12 16 6"></polyline>
                  <polyline points="8 6 2 12 8 18"></polyline>
                </svg>
                {showMermaidEditor ? 'ปิดตัวแก้ไข' : 'แก้ไขโค้ด Mermaid'}
              </button>

              <button type="button" class="btn-ctrl-action copy" on:click={copyCurrentMermaidCode} title="คัดลอกโค้ด Mermaid">
                Copy Code
              </button>

              <button type="button" class="btn-ctrl-action svg" on:click={exportDiagramSVG} title="บันทึกรูปภาพ SVG">
                Export SVG
              </button>

              <div class="zoom-controls">
                <button type="button" class="btn-ctrl" on:click={zoomIn} title="ขยาย (Zoom In)" aria-label="ขยาย (Zoom In)">+</button>
                <button type="button" class="btn-ctrl" on:click={zoomOut} title="ย่อ (Zoom Out)" aria-label="ย่อ (Zoom Out)">−</button>
                <button type="button" class="btn-ctrl" on:click={fitView} title="ปรับขนาดให้พอดีหน้าจอ (Fit to Screen)">Fit</button>
                <button type="button" class="btn-ctrl" on:click={zoomReset} title="ขนาด 100%">{Math.round(zoomLevel * 100)}%</button>
              </div>

              <button type="button" class="btn-ctrl-action fs" on:click={() => { isFullscreenDiagram = !isFullscreenDiagram; setTimeout(fitView, 200); }} title="ขยายเต็มหน้าจอ (กด Esc เพื่อออก)">
                <QAIcon name={isFullscreenDiagram ? 'close' : 'maximize'} size={13} /> {isFullscreenDiagram ? 'ย่อจอ' : 'เต็มจอ'}
              </button>
            </div>
          </div>

          <!-- Live Mermaid Code Editor Drawer -->
          {#if showMermaidEditor}
            <div class="glass-panel mermaid-editor-drawer" transition:slide={{ duration: 220 }}>
              <div class="editor-drawer-head">
                <div class="editor-drawer-title">
                  <span class="editor-badge">LIVE MERMAID EDITOR</span>
                  <span class="editor-hint">แก้ไขโค้ด Mermaid แล้วกดบันทึกเพื่อ Render ใหม่และซิงค์ลงฐานข้อมูลโครงการให้ Agent ทุกตัวใช้งานร่วมกัน</span>
                </div>
                <div class="editor-drawer-actions">
                  <button type="button" class="btn-editor-cancel" on:click={() => showMermaidEditor = false} disabled={isSavingDiagram}>
                    ยกเลิก
                  </button>
                  <button type="button" class="btn-editor-save" on:click={saveEditedDiagram} disabled={isSavingDiagram}>
                    {#if isSavingDiagram}
                      <span class="spinner-small"></span> กำลังบันทึก...
                    {:else}
                      บันทึกและซิงค์ Agent
                    {/if}
                  </button>
                </div>
              </div>
              <textarea
                class="mermaid-code-textarea" aria-label="โค้ด Mermaid Diagram"
                bind:value={editableMermaidCode}
                rows="10"
                spellcheck="false"
                placeholder="flowchart TD&#10;  Start([เริ่มต้น]) --> Step1[ขั้นตอนที่ 1]"
              ></textarea>
            </div>
          {/if}

          <!-- Mermaid Canvas Box with Draw.io style Grid -->
          <div 
            class="glass-panel diagram-canvas-panel" 
            class:drawio-grid={showDrawioGrid && activeTab === 'flowchart'}
            class:is-dragging={isDragging}
            bind:this={canvasPanelRef}
            on:pointerdown={onPointerDown}
            on:wheel={handleWheel}
          >
            <div class="canvas-help-badge">
              <span>คลิกลากเมาส์เพื่อเลื่อนผัง (Pan)</span>
              <span class="sep">•</span>
              <span>สกอลล์เมาส์เพื่อซูม (Zoom)</span>
              {#if isFullscreenDiagram}
                <span class="sep">•</span>
                <span>กด Esc เพื่อออกจากเต็มจอ</span>
              {/if}
            </div>

            <div 
              class="diagram-render-area" 
              bind:this={diagramContainer}
              style="transform: translate({panX}px, {panY}px) scale({zoomLevel}); transform-origin: 0 0; transition: {isDragging ? 'none' : 'transform 0.12s ease-out'};"
            >
              <!-- Mermaid SVG is injected here -->
            </div>
          </div>

          <!-- Draw.io Flowchart Legend -->
          {#if activeTab === 'flowchart'}
            <div class="drawio-legend-bar" transition:slide={{ duration: 200 }}>
              <div class="legend-header">สัญลักษณ์ผัง Flowchart (Draw.io Notation):</div>
              <div class="legend-items">
                <div class="legend-item"><span class="shape-sample pill"></span> Start / Terminal Gate</div>
                <div class="legend-item"><span class="shape-sample rect"></span> Process Step / Action</div>
                <div class="legend-item"><span class="shape-sample diamond"></span> Decision / Condition Gate</div>
                <div class="legend-item"><span class="shape-sample cylinder"></span> Database & Vector Store</div>
                <div class="legend-item"><span class="shape-sample group"></span> Subgraph / Tier Swimlane</div>
              </div>
            </div>
          {/if}
        </div>

      <!-- TAB 5: TRACEABILITY MATRIX (extracted component) -->
      {:else if activeTab === 'matrix'}
        <div class="matrix-pane-host" role="tabpanel" id="qa-tabpanel" aria-labelledby="qa-tab-matrix" in:fly={{ y: 12, duration: 240, easing: cubicOut }}>
          <TraceabilityMatrixPane
            rows={flowData.traceability_matrix || []}
            projectCode={$selectedProjectStore?.project_code || 'Project'}
            on:openscreen={(e) => { activeTab = 'sitemap'; selectedScreenId = e.detail.screen_id; selectedNodeId = e.detail.screen_id; }}
          />
        </div>
      {/if}
    {/if}

  {/if}

  <!-- Fullscreen Image Lightbox Modal -->
  {#if lightboxImage}
    <div class="lightbox-backdrop" transition:fade={{ duration: 160 }} role="presentation" on:click={() => lightboxImage = null}>
      <div class="lightbox-modal" role="dialog" aria-modal="true" aria-labelledby="lightbox-dialog-title" tabindex="-1" use:modalFocus on:click|stopPropagation>
        <div class="lightbox-header">
          <div class="lightbox-title" id="lightbox-dialog-title">Screen Mockup (Full Resolution)</div>
          <button type="button" class="lightbox-close" on:click={() => lightboxImage = null}><QAIcon name="close" size={12} /> ปิดหน้าต่าง</button>
        </div>
        <div class="lightbox-body">
          <img src={`${lightboxImage}`} alt="Full Resolution Mockup" class="lightbox-img" decoding="async" />
        </div>
      </div>
    </div>
  {/if}

  <!-- Smart AI Test Launcher Modal -->
  {#if isTestModalOpen}
    <SmartTestLauncherModal 
      projectId={$selectedProjectStore?.id || $selectedProjectStore?.project_id}
      projectName={$selectedProjectStore?.name || $selectedProjectStore?.project_name || 'Project'}
      cardData={testTargetCard}
      isOpen={isTestModalOpen}
      on:close={() => isTestModalOpen = false}
      on:test_completed={handleTestCompleted}
    />
  {/if}
</div>

<style>
  .btn-run-agent-screen {
    background: linear-gradient(135deg, #8b5cf6, #6366f1);
    border: none;
    color: white;
    font-size: 11.5px;
    font-weight: 700;
    padding: 5px 12px;
    min-height: 28px;
    border-radius: 8px;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
    display: flex;
    align-items: center;
    gap: 4px;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
    white-space: nowrap;
  }

  .btn-run-agent-screen:hover {
    background: linear-gradient(135deg, #6d28d9, #4338ca);
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.6);
  }

  .panel-container {
    --qa-iris: #6366f1;
    --qa-iris-soft: #818cf8;
    --qa-iris-text: #c7d2fe;
    --qa-violet: #a855f7;
    --qa-surface-deep: #0b0d15;
    --qa-surface-raised: #161926;
    --qa-text-muted: #94a3b8;
    --qa-text-strong: #f8fafc;
    --qa-text: #e2e8f0;
    --qa-text-soft: #cbd5e1;
    --qa-border-strong: #334155;
    --qa-focus-ring: #a5b4fc;
    display: flex;
    flex-direction: column;
    gap: 18px;
    height: 100%;
    overflow-y: auto;
    padding: 20px 24px 32px;
    max-width: 100%;
    box-sizing: border-box;
    color: var(--qa-text-strong);
    font-family: 'Prompt', 'Outfit', sans-serif;
  }

  .top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    flex-shrink: 0;
  }

  .top-nav-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .sync-timestamp {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 12px;
    border-radius: 999px;
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.25);
    color: #6ee7b7;
    font-size: 12px;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
  }

  .sync-pulse-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6);
    animation: syncPulse 2.4s ease-out infinite;
  }

  @keyframes syncPulse {
    0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.55); }
    70% { box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
    100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
  }

  .btn-back {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--qa-text-muted);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 14px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 500;
    font-family: inherit;
    transition: color 0.18s ease, background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
  }

  .btn-back:hover {
    color: var(--qa-text-strong);
    background: rgba(99, 102, 241, 0.12);
    border-color: rgba(99, 102, 241, 0.32);
    transform: translateX(-2px);
  }

  .project-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(18, 20, 28, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 5px 14px 5px 8px;
    border-radius: 999px;
    font-size: 13px;
    backdrop-filter: blur(12px);
  }

  .p-badge {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    font-weight: 700;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 999px;
    font-family: 'Outfit', sans-serif;
    letter-spacing: 0.04em;
  }

  .p-title { font-weight: 500; color: var(--qa-text); }

  .glass-panel {
    background: rgba(18, 20, 28, 0.64);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.28);
  }

  .banner-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
    flex-shrink: 0;
    background:
      radial-gradient(circle at top right, rgba(99, 102, 241, 0.14), transparent 42%),
      radial-gradient(circle at bottom left, rgba(168, 85, 247, 0.08), transparent 40%),
      rgba(18, 20, 28, 0.7);
  }

  .banner-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    flex-wrap: wrap;
  }

  .banner-title-block {
    flex: 1;
    min-width: 280px;
  }

  .title-with-badge {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 6px;
  }

  .title-with-badge h2 {
    margin: 0;
    font-family: 'Outfit', 'Prompt', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--qa-text-strong);
  }

  .badge-ai {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.24), rgba(168, 85, 247, 0.28));
    border: 1px solid rgba(165, 180, 252, 0.35);
    color: #e0e7ff;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 999px;
    letter-spacing: 0.04em;
    font-family: 'Outfit', sans-serif;
  }

  .desc-text {
    margin: 0;
    color: var(--qa-text-muted);
    font-size: 0.9rem;
    line-height: 1.55;
    max-width: 78ch;
  }

  .btn-generate-ai {
    background: linear-gradient(135deg, #6366f1, #a855f7);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: white;
    padding: 11px 22px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 13.5px;
    font-family: inherit;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 9px;
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.35);
    transition: transform 0.2s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.2s ease, filter 0.2s ease;
    white-space: nowrap;
  }

  .btn-generate-ai:hover:not(:disabled) {
    box-shadow: 0 10px 28px rgba(139, 92, 246, 0.48);
    transform: translateY(-2px);
    filter: brightness(1.06);
  }

  .btn-generate-ai:active:not(:disabled) {
    transform: translateY(0);
  }

  .btn-generate-ai:disabled { opacity: 0.6; cursor: not-allowed; }

  .executive-summary-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    padding: 12px 16px;
    border-radius: 14px;
    background: rgba(11, 13, 21, 0.56);
    border: 1px solid rgba(99, 102, 241, 0.22);
  }

  .exec-summary-main {
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex: 1;
    min-width: 260px;
    flex-wrap: wrap;
  }

  .exec-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #a5b4fc;
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-family: 'Outfit', sans-serif;
    white-space: nowrap;
  }

  .exec-text {
    margin: 0;
    color: var(--qa-text-soft);
    font-size: 12.8px;
    line-height: 1.5;
  }

  .cross-agent-sync {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .cross-sync-label {
    font-size: 11px;
    color: var(--qa-text-muted);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-family: 'Outfit', sans-serif;
  }

  .cross-agent-pills {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .agent-sync-pill {
    font-size: 11px;
    font-weight: 500;
    color: #c7d2fe;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
  }

  .instructions-accordion {
    border-top: 1px solid rgba(255, 255, 255, 0.07);
    padding-top: 10px;
  }

  .accordion-toggle {
    background: none;
    border: none;
    color: #a5b4fc;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
    padding: 2px 0;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: color 0.18s ease;
  }

  .accordion-toggle:hover { color: #c7d2fe; }

  .accordion-chevron {
    transition: transform 0.2s cubic-bezier(0.22, 1, 0.36, 1);
  }

  .accordion-chevron.rotated {
    transform: rotate(90deg);
  }

  .instructions-textarea {
    width: 100%;
    margin-top: 8px;
    background: rgba(11, 13, 21, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: var(--qa-text-strong);
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 13px;
    font-family: inherit;
    box-sizing: border-box;
    outline: none;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .instructions-textarea:focus {
    border-color: rgba(99, 102, 241, 0.65);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 12px;
    margin-top: 2px;
  }

  @keyframes statRise {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .stat-card {
    background: rgba(11, 13, 21, 0.56);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 13px 15px;
    display: flex;
    align-items: center;
    gap: 12px;
    animation: statRise 0.36s cubic-bezier(0.22, 1, 0.36, 1) both;
    animation-delay: calc(var(--stagger, 0) * 55ms);
    transition: transform 0.2s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.2s ease, background 0.2s ease;
  }

  .stat-card:hover {
    transform: translateY(-2px);
    border-color: rgba(99, 102, 241, 0.35);
    background: rgba(18, 22, 34, 0.8);
  }

  .stat-card.highlight {
    border-color: rgba(16, 185, 129, 0.36);
    background: rgba(16, 185, 129, 0.08);
  }

  .stat-icon-box {
    width: 38px;
    height: 38px;
    border-radius: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .stat-icon-box.indigo { background: rgba(99, 102, 241, 0.16); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.28); }

  .stat-icon-box.violet { background: rgba(168, 85, 247, 0.16); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.28); }

  .stat-icon-box.sky { background: rgba(56, 189, 248, 0.14); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.26); }

  .stat-icon-box.amber { background: rgba(245, 158, 11, 0.14); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.26); }

  .stat-icon-box.emerald { background: rgba(16, 185, 129, 0.16); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }

  .stat-val {
    font-family: 'Outfit', sans-serif;
    font-size: 1.32rem;
    font-weight: 700;
    color: var(--qa-text-strong);
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
  }

  .stat-label { font-size: 11.5px; color: var(--qa-text-muted); font-weight: 500; margin-top: 2px; }

  .tabs-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    padding: 6px;
    flex-shrink: 0;
    background: rgba(18, 20, 28, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    overflow: visible;
  }

  .nav-tab {
    background: transparent;
    border: 1px solid transparent;
    color: var(--qa-text-muted);
    padding: 9px 15px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
    flex-shrink: 0;
    transition: color 0.18s ease, background 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
  }

  .nav-tab:hover {
    color: var(--qa-text-strong);
    background: rgba(255, 255, 255, 0.04);
  }

  .nav-tab.active {
    color: #ffffff;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.28), rgba(168, 85, 247, 0.24));
    border-color: rgba(129, 140, 248, 0.45);
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.22);
  }

  /* ── SITEMAP & WIREFRAME LAYOUT ── */
  .sitemap-workspace {
    display: grid;
    grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
    align-items: stretch;
    gap: 18px;
    flex: 1;
    min-height: 550px;
  }

  .sitemap-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
    max-height: 780px;
    overflow-y: auto;
  }

  .panel-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .panel-title-row h3 { margin: 0; font-size: 1.05rem; color: var(--qa-text-strong); font-weight: 600; }

  .count-badge, .screen-id-badge {
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(129, 140, 248, 0.35);
    color: #c7d2fe;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'Outfit', monospace;
  }

  .sub-hint { margin: 0; font-size: 12px; color: var(--qa-text-muted); }

  .sitemap-tree {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .sitemap-node-card {
    background: rgba(11, 13, 21, 0.56);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px;
    cursor: pointer;
    transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
  }

  .sitemap-node-card:hover {
    border-color: rgba(129, 140, 248, 0.45);
    background: rgba(24, 28, 42, 0.85);
    transform: translateY(-1px);
  }

  .sitemap-node-card.active {
    border-color: rgba(129, 140, 248, 0.72);
    background: rgba(99, 102, 241, 0.16);
    box-shadow: 0 0 16px rgba(99, 102, 241, 0.22);
  }

  .node-main {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .node-icon { font-size: 20px; }

  .node-text { flex: 1; min-width: 0; }

  .node-title { font-weight: 600; font-size: 13.5px; color: var(--qa-text-strong); }

  .node-path { font-size: 11px; color: #a5b4fc; font-family: monospace; }

  .node-category {
    font-size: 11px;
    background: rgba(255, 255, 255, 0.08);
    padding: 2px 7px;
    border-radius: 999px;
    color: var(--qa-text-soft);
  }

  .node-desc {
    margin-top: 6px;
    font-size: 11.5px;
    color: var(--qa-text-muted);
    line-height: 1.45;
  }

  .node-children {
    margin-top: 10px;
    padding-left: 14px;
    border-left: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .sitemap-child-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 10px;
    border-radius: 8px;
    background: rgba(0, 0, 0, 0.24);
    border: 1px solid transparent;
    font-size: 12px;
    transition: background 0.15s ease, border-color 0.15s ease;
  }

  .sitemap-child-card:hover {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(129, 140, 248, 0.28);
  }

  .sitemap-child-card.active {
    background: rgba(99, 102, 241, 0.26);
    border: 1px solid rgba(129, 140, 248, 0.65);
    box-shadow: 0 2px 10px rgba(99, 102, 241, 0.2);
  }

  .child-title { font-weight: 500; color: var(--qa-text); }

  .child-path { font-size: 11px; color: #a5b4fc; margin-left: 6px; font-family: monospace; }

  /* ── MOCKUP WIREFRAME ── */
  .mockup-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
  }

  .empty-mockup {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--qa-text-muted);
  }

  .mockup-viewport {
    width: 100%;
    background: var(--qa-surface-deep);
    border: 1px solid var(--qa-surface-raised);
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
    transition: max-width 0.3s ease, border-radius 0.3s ease;
  }

  .mockup-browser-bar {
    background: var(--qa-surface-raised);
    padding: 8px 14px;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .browser-dots { display: flex; gap: 6px; flex-shrink: 0; }

  .browser-nav-arrows {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .btn-nav-arrow {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: var(--qa-text-soft);
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    min-width: 28px;
    min-height: 28px;
    padding: 0;
    flex-shrink: 0;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
  }

  .btn-nav-arrow:hover {
    background: rgba(255, 255, 255, 0.14);
    border-color: rgba(255, 255, 255, 0.24);
    color: #ffffff;
  }

  .dot { width: 10px; height: 10px; border-radius: 50%; }

  .dot.red { background: #ef4444; }

  .dot.yellow { background: #f59e0b; }

  .dot.green { background: #10b981; }

  .browser-url-input {
    flex: 1;
    min-width: 120px;
    overflow: hidden;
    background: var(--qa-surface-deep);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    color: var(--qa-text-muted);
    font-family: monospace;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .lock-icon {
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
  }

  .browser-url-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ── INTERACTIVE PROTOTYPE & WIREFRAME WORKSPACE ── */
  .prototype-control-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, rgba(11, 13, 21, 0.95), rgba(22, 25, 38, 0.9));
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 8px 16px;
    flex-wrap: wrap;
    gap: 10px;
  }

  .device-switch-group {
    display: flex;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 2px;
    gap: 2px;
  }

  .btn-device-switch {
    background: transparent;
    border: none;
    color: var(--qa-text-muted);
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s, opacity 0.2s;
  }

  .btn-device-switch:hover { color: var(--qa-text-strong); }

  .btn-device-switch.active {
    background: linear-gradient(135deg, var(--qa-iris), #6366f1);
    color: white;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
  }

  .prototype-quick-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .btn-proto-action {
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
    transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s, opacity 0.2s;
  }

  .btn-proto-action.fill {
    background: rgba(234, 179, 8, 0.15);
    border-color: rgba(234, 179, 8, 0.4);
    color: #fde047;
  }

  .btn-proto-action.fill:hover {
    background: rgba(234, 179, 8, 0.3);
    box-shadow: 0 0 10px rgba(234, 179, 8, 0.3);
  }

  .btn-proto-action.reset {
    background: rgba(255, 255, 255, 0.06);
    color: var(--qa-text-muted);
  }

  .btn-proto-action.reset:hover { background: rgba(255, 255, 255, 0.12); color: var(--qa-text-strong); }

  .prototype-badge-live {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.4);
    color: #86efac;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }

  .prototype-badge-live .live-dot.pulse {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #22c55e;
    box-shadow: 0 0 8px #22c55e;
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.8); }
  }

  /* ── OUTER PROTOTYPE CANVAS WRAPPER ── */
  .prototype-outer-canvas {
    padding: 24px;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    min-height: 520px;
    background: radial-gradient(circle at 50% 0%, #172554 0%, #0b0f19 75%);
    transition: background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1), color 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1), transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    overflow-x: auto;
  }

  .prototype-outer-canvas.desktop {
    padding: 16px;
  }

  .prototype-outer-canvas.desktop .mockup-viewport {
    width: 100%;
    max-width: 100%;
    border-radius: 10px;
  }

  .prototype-outer-canvas.tablet {
    padding: 24px 16px;
  }

  .prototype-outer-canvas.tablet .mockup-viewport {
    width: 100%;
    max-width: 768px;
    border-radius: 16px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .prototype-outer-canvas.mobile {
    padding: 24px 12px;
  }

  .prototype-outer-canvas.mobile .mockup-viewport {
    width: 100%;
    max-width: 390px;
    border-radius: 36px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 0 8px var(--qa-surface-raised);
    border: 2px solid rgba(255, 255, 255, 0.18);
  }

  .prototype-outer-canvas.mobile .mock-form-grid {
    grid-template-columns: 1fr;
  }

  .mobile-phone-notch-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 18px 4px 18px;
    font-size: 11px;
    color: var(--qa-text-muted);
    background: rgba(11, 13, 21, 0.95);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .phone-dynamic-island {
    width: 80px;
    height: 18px;
    background: #000;
    border-radius: 12px;
    margin: 0 auto;
  }

  .phone-icons { font-size: 11px; font-weight: 600; color: var(--qa-text-soft); }

  .mockup-screen-content {
    width: 100%;
    background: var(--qa-surface-deep);
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 20px;
    box-sizing: border-box;
  }

  /* ── HERO BANNER CARD ── */
  .proto-hero-card {
    background: linear-gradient(135deg, rgba(67, 56, 202, 0.35), rgba(11, 13, 21, 0.8));
    border: 1px solid rgba(129, 140, 248, 0.25);
    border-radius: 12px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .proto-hero-main {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .proto-title-badge-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .proto-screen-title {
    margin: 0;
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--qa-text-strong);
  }

  .proto-verified-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: linear-gradient(135deg, #059669, #10b981);
    color: white;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 20px;
    box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3);
  }

  .proto-header-action-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .btn-proto-header-action {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: var(--qa-text-soft);
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .btn-proto-header-action:hover {
    background: rgba(255, 255, 255, 0.18);
    color: #ffffff;
  }

  .btn-proto-header-action.fav.favorited,
  .btn-proto-header-action.favorited {
    background: rgba(245, 158, 11, 0.2);
    border-color: rgba(245, 158, 11, 0.5);
    color: #fcd34d;
  }

  .proto-desc-text {
    margin: 0;
    font-size: 12.5px;
    color: var(--qa-text-muted);
    line-height: 1.5;
  }

  /* ── STATS KPI CARDS ── */
  .proto-stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
  }

  .proto-stat-card {
    background: rgba(11, 13, 21, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    min-width: 0;
    transition: transform 0.15s, border-color 0.15s;
  }

  .proto-stat-card:hover {
    transform: translateY(-2px);
    border-color: rgba(129, 140, 248, 0.35);
  }

  .proto-stat-card.blue { border-color: rgba(99, 102, 241, 0.28); }
  .proto-stat-card.purple { border-color: rgba(168, 85, 247, 0.28); }
  .proto-stat-card.emerald { border-color: rgba(16, 185, 129, 0.28); }
  .proto-stat-card.amber { border-color: rgba(245, 158, 11, 0.28); }

  .stat-card-label {
    font-size: 11px;
    color: var(--qa-text-muted);
    font-weight: 500;
  }

  .stat-card-value {
    font-size: 1rem;
    font-weight: 700;
    color: var(--qa-text-strong);
    line-height: 1.25;
    word-break: break-word;
  }

  .stat-card-sub {
    font-size: 11px;
    color: var(--qa-iris-text);
    opacity: 0.85;
    word-break: break-word;
  }

  /* ── NAVIGATION TABS ── */
  .proto-tabs-navbar {
    display: flex;
    gap: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding-bottom: 2px;
    overflow-x: auto;
  }

  .proto-nav-tab-btn {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--qa-text-muted);
    padding: 6px 14px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s, opacity 0.2s;
    white-space: nowrap;
  }

  .proto-nav-tab-btn:hover { color: var(--qa-text-strong); }

  .proto-nav-tab-btn.active {
    color: var(--qa-iris-soft);
    border-bottom-color: var(--qa-iris);
  }

  /* ── SECTION STACK ── */
  .mockup-sections-stack {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .proto-section-card {
    background: rgba(22, 25, 38, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .proto-sec-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .mock-sec-title {
    font-size: 12.5px;
    font-weight: 700;
    color: var(--qa-iris-text);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .proto-interactive-tag {
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.4);
    color: var(--qa-iris-text);
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 12px;
  }

  .proto-tag-highlight {
    background: rgba(234, 179, 8, 0.15);
    border: 1px solid rgba(234, 179, 8, 0.4);
    color: #fde047;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 12px;
  }

  .proto-count-badge {
    background: rgba(255, 255, 255, 0.08);
    color: var(--qa-text-soft);
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
  }

  /* ── GALLERY SECTION ── */
  .proto-gallery-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
  }

  .gallery-photo-card {
    background: var(--qa-surface-deep);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.2s, border-color 0.2s;
  }

  .gallery-photo-card:hover {
    transform: translateY(-2px);
    border-color: rgba(129, 140, 248, 0.5);
  }

  .photo-visual-placeholder {
    height: 90px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .photo-visual-placeholder.grad-0 { background: linear-gradient(135deg, #1e3a8a, #0284c7); }

  .photo-visual-placeholder.grad-1 { background: linear-gradient(135deg, #4c1d95, #9333ea); }

  .photo-visual-placeholder.grad-2 { background: linear-gradient(135deg, #065f46, #059669); }

  .photo-visual-placeholder.grad-3 { background: linear-gradient(135deg, #9a3412, #ea580c); }

  .photo-cam-icon { font-size: 26px; }

  .photo-badge {
    position: absolute;
    bottom: 6px;
    right: 8px;
    background: rgba(0, 0, 0, 0.6);
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 4px;
  }

  .photo-card-info { padding: 8px 10px; }

  .photo-title { font-size: 11.5px; font-weight: 600; color: var(--qa-text-strong); margin-bottom: 2px; }

  .photo-desc { font-size: 11px; color: var(--qa-text-muted); line-height: 1.3; }

  /* ── FORM INPUTS & INTERACTION ── */
  .mock-form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .mock-form-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .mock-form-item.full-width { grid-column: 1 / -1; }

  .mock-label {
    font-size: 11.5px;
    color: var(--qa-text-soft);
    font-weight: 600;
  }

  .req-star { color: #f87171; }

  .proto-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .proto-real-input, .proto-real-select, .proto-real-textarea {
    width: 100%;
    background-color: #030712;
    border: 1px solid #374151;
    color: var(--qa-text-strong);
    border-radius: 8px;
    font-size: 12.5px;
    box-sizing: border-box;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }

  .proto-real-input, .proto-real-select {
    height: 36px;
  }

  .proto-real-input {
    padding: 0 30px 0 10px;
  }

  .proto-real-select {
    padding: 0 32px 0 10px;
    cursor: pointer;
  }

  .proto-real-textarea {
    padding: 8px 10px;
  }

  .proto-real-input:focus, .proto-real-select:focus, .proto-real-textarea:focus {
    border-color: var(--qa-iris);
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25);
  }

  .btn-input-clear {
    position: absolute;
    right: 6px;
    background: none;
    border: none;
    color: var(--qa-text-muted);
    font-size: 11px;
    cursor: pointer;
    padding: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .btn-input-clear:hover { color: var(--qa-text-strong); }

  /* iOS Switch Toggle */
  .proto-toggle-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 0;
  }

  .proto-switch {
    position: relative;
    display: inline-block;
    width: 38px;
    height: 20px;
  }

  .proto-switch input { opacity: 0; width: 0; height: 0; }

  .switch-slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background-color: var(--qa-border-strong);
    transition: 0.3s;
    border-radius: 20px;
  }

  .switch-slider:before {
    position: absolute;
    content: "";
    height: 14px;
    width: 14px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: 0.3s;
    border-radius: 50%;
  }

  .proto-switch input:checked + .switch-slider { background-color: #10b981; }

  .proto-switch input:checked + .switch-slider:before { transform: translateX(18px); }

  .toggle-status-text { font-size: 11.5px; color: var(--qa-text-soft); font-weight: 500; }

  .proto-real-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--qa-text);
    cursor: pointer;
    margin-top: 4px;
  }

  /* ── ACTION BUTTONS ── */
  .mock-btn-row {
    display: flex;
    gap: 8px;
    margin-top: 8px;
    flex-wrap: wrap;
  }

  .proto-action-btn {
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    border: none;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s, opacity 0.2s;
  }

  .proto-action-btn.primary {
    background: linear-gradient(135deg, var(--qa-iris), #6366f1);
    color: white;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
  }

  .proto-action-btn.primary:hover:not(:disabled) {
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.55);
    transform: translateY(-1px);
  }

  .proto-action-btn.secondary {
    background: rgba(255, 255, 255, 0.08);
    color: var(--qa-text-soft);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .proto-action-btn.secondary:hover { background: rgba(255, 255, 255, 0.15); color: white; }

  .proto-action-btn.outline {
    background: rgba(255, 255, 255, 0.03);
    color: var(--qa-text-soft);
    border: 1px solid rgba(255, 255, 255, 0.22);
  }

  .proto-action-btn.outline:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.36);
    color: #ffffff;
  }

  .proto-action-btn.map {
    background: linear-gradient(135deg, #059669, #10b981);
    color: white;
  }

  .proto-action-btn.brand-line {
    background: #06c755;
    color: #ffffff;
    border: 1px solid #05b34c;
    box-shadow: 0 3px 10px rgba(6, 199, 85, 0.25);
  }

  .proto-action-btn.brand-line:hover:not(:disabled) {
    background: #05b34c;
    transform: translateY(-1px);
  }

  .proto-action-btn.brand-google {
    background: #181f32;
    color: #f8fafc;
    border: 1px solid rgba(148, 163, 184, 0.3);
  }

  .proto-action-btn.brand-google:hover:not(:disabled) {
    background: #232d47;
    border-color: rgba(148, 163, 184, 0.5);
  }

  .proto-action-btn.danger {
    background: rgba(244, 63, 94, 0.14);
    color: #fda4af;
    border: 1px solid rgba(244, 63, 94, 0.38);
  }

  .proto-action-btn.danger:hover:not(:disabled) {
    background: rgba(244, 63, 94, 0.25);
    color: #ffffff;
  }

  .proto-action-btn.auth-submit-full {
    width: 100%;
    justify-content: center;
    padding: 10px 18px;
    font-size: 13px;
    border-radius: 10px;
  }

  /* ── DEDICATED AUTHENTICATION ARCHETYPE UX ── */
  .auth-ux-layout {
    display: grid;
    grid-template-columns: minmax(260px, 0.92fr) minmax(300px, 1.08fr);
    gap: 18px;
    align-items: stretch;
  }

  .prototype-outer-canvas.mobile .auth-ux-layout,
  .prototype-outer-canvas.tablet .auth-ux-layout {
    grid-template-columns: 1fr;
  }

  @media (max-width: 980px) {
    .auth-ux-layout {
      grid-template-columns: 1fr;
    }
  }

  .auth-brand-showcase {
    background: linear-gradient(155deg, rgba(67, 56, 202, 0.28), rgba(15, 23, 42, 0.85));
    border: 1px solid rgba(129, 140, 248, 0.24);
    border-radius: 14px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 16px;
  }

  .auth-app-logo-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 14px;
  }

  .auth-app-emblem {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
  }

  .auth-app-name {
    font-size: 13px;
    font-weight: 700;
    color: #f8fafc;
  }

  .auth-app-route {
    font-size: 11px;
    color: #94a3b8;
    font-family: monospace;
  }

  .auth-showcase-title {
    margin: 0 0 8px 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: #f8fafc;
    line-height: 1.3;
  }

  .auth-showcase-desc {
    margin: 0;
    font-size: 12.5px;
    color: #cbd5e1;
    line-height: 1.55;
  }

  .auth-trust-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .auth-trust-item {
    background: rgba(11, 13, 21, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .auth-trust-item.blue { border-color: rgba(99, 102, 241, 0.3); }
  .auth-trust-item.purple { border-color: rgba(168, 85, 247, 0.3); }
  .auth-trust-item.emerald { border-color: rgba(16, 185, 129, 0.3); }
  .auth-trust-item.amber { border-color: rgba(245, 158, 11, 0.3); }

  .trust-lbl { font-size: 10.5px; color: #94a3b8; }
  .trust-val { font-size: 13px; font-weight: 700; color: #f8fafc; }
  .trust-sub { font-size: 10.5px; color: #a5b4fc; }

  .auth-card-panel {
    background: rgba(17, 21, 34, 0.92);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
  }

  .auth-segmented-tabs {
    display: flex;
    background: #070a12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 4px;
    gap: 4px;
    overflow-x: auto;
  }

  .auth-seg-tab-btn {
    flex: 1;
    background: transparent;
    border: none;
    color: #94a3b8;
    padding: 7px 10px;
    border-radius: 7px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.18s, color 0.18s;
  }

  .auth-seg-tab-btn:hover { color: #f8fafc; }
  .auth-seg-tab-btn.active {
    background: rgba(99, 102, 241, 0.24);
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
  }

  .auth-card-head h4 {
    margin: 0 0 4px 0;
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
  }

  .auth-card-head p {
    margin: 0;
    font-size: 12px;
    color: #94a3b8;
  }

  .auth-card-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }

  .auth-vertical-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .auth-2col-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .auth-utility-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }

  .proto-switch-inline {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  .auth-forgot-link {
    background: none;
    border: none;
    color: #a5b4fc;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    padding: 2px 4px;
  }

  .auth-forgot-link:hover {
    color: #c7d2fe;
    text-decoration: underline;
  }

  .auth-social-divider {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #94a3b8;
    font-size: 11px;
    margin: 2px 0;
  }

  .auth-social-divider::before,
  .auth-social-divider::after {
    content: "";
    flex: 1;
    height: 1px;
    background: rgba(255, 255, 255, 0.1);
  }

  .auth-social-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 8px;
  }

  .auth-social-grid .proto-action-btn {
    justify-content: center;
    padding: 9px 12px;
    border-radius: 9px;
  }

  /* ── PASSWORD EYE & DISCOVERY / REVIEW ARCHETYPE HELPERS ── */
  .proto-real-input.has-two-icons {
    padding-right: 54px;
  }

  .btn-input-eye {
    position: absolute;
    right: 26px;
    background: none;
    border: none;
    color: var(--qa-text-muted);
    cursor: pointer;
    padding: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .btn-input-eye:hover { color: var(--qa-text-strong); }

  .proto-hero-top-flex {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    flex-wrap: wrap;
  }

  .discovery-filter-strip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    padding-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .discovery-chips {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .discovery-chip {
    background: rgba(11, 13, 21, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 20px;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
  }

  .discovery-chip.active {
    background: rgba(99, 102, 241, 0.25);
    border-color: #818cf8;
    color: #ffffff;
  }

  .discovery-map-card {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 10px;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .discovery-map-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 12px;
    font-weight: 600;
    color: #bae6fd;
  }

  .discovery-map-canvas {
    position: relative;
    height: 125px;
    border-radius: 8px;
    background: radial-gradient(circle at 40% 50%, rgba(14, 116, 144, 0.35), rgba(7, 10, 18, 0.95));
    border: 1px solid rgba(255, 255, 255, 0.08);
    overflow: hidden;
  }

  .map-grid-lines {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
    background-size: 24px 24px;
  }

  .map-pin-chip {
    position: absolute;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(56, 189, 248, 0.5);
    color: #f8fafc;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 9px;
    border-radius: 16px;
    cursor: pointer;
    box-shadow: 0 4px 10px rgba(0,0,0,0.45);
    transition: transform 0.15s, border-color 0.15s;
  }

  .map-pin-chip:hover { transform: scale(1.05); border-color: #38bdf8; }
  .map-pin-chip.p1 { top: 20px; left: 16%; }
  .map-pin-chip.p2 { top: 68px; left: 48%; }
  .map-pin-chip.p3 { top: 26px; right: 14%; }

  .map-user-you {
    position: absolute;
    bottom: 14px;
    left: 24%;
    font-size: 10.5px;
    font-weight: 700;
    color: #6ee7b7;
    background: rgba(16, 185, 129, 0.18);
    border: 1px solid rgba(16, 185, 129, 0.45);
    padding: 2px 8px;
    border-radius: 12px;
  }

  .live-rating-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    padding-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .rating-banner-label {
    font-size: 12px;
    font-weight: 600;
    color: #fde68a;
  }

  .interactive-stars-row {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .star-pick-btn {
    background: transparent;
    border: none;
    color: #475569;
    cursor: pointer;
    padding: 3px;
    display: inline-flex;
    transition: transform 0.15s, color 0.15s;
  }

  .star-pick-btn.active { color: #fbbf24; }
  .star-pick-btn:hover { transform: scale(1.15); }

  .rating-score-pill {
    margin-left: 6px;
    font-size: 11.5px;
    font-weight: 700;
    color: #fde68a;
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.4);
    padding: 2px 8px;
    border-radius: 12px;
  }

  .mock-form-grid.single-col-form {
    grid-template-columns: 1fr;
  }

  .table-header-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .proto-table-search {
    background: #030712;
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #f8fafc;
    border-radius: 6px;
    padding: 4px 9px;
    font-size: 11.5px;
    width: 170px;
    outline: none;
  }

  .proto-table-search:focus {
    border-color: var(--qa-iris);
  }

  .table-pill.muted {
    background: rgba(148, 163, 184, 0.14);
    color: #94a3b8;
  }

  .proto-action-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .spinner-small {
    width: 12px;
    height: 12px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: white;
    display: inline-block;
    flex-shrink: 0;
    animation: spin 0.8s linear infinite;
  }

  /* ── TABLE IN PROTOTYPE ── */
  .mock-table-wrap { overflow-x: auto; }

  .proto-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  .proto-table th {
    background: #030712;
    color: var(--qa-text-muted);
    padding: 8px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    font-weight: 600;
  }

  .proto-table td {
    padding: 8px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    color: #f1f5f9;
  }

  .proto-table-row:hover { background: rgba(255, 255, 255, 0.03); }

  .table-pill {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-block;
  }

  .table-pill.success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }

  .table-pill.warning { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }

  .table-code-badge {
    background: rgba(99, 102, 241, 0.15);
    color: var(--qa-iris-text);
    font-family: monospace;
    font-weight: 700;
    font-size: 11px;
    padding: 1px 5px;
    border-radius: 3px;
  }

  .btn-table-action {
    background: rgba(139, 92, 246, 0.2);
    border: 1px solid rgba(139, 92, 246, 0.4);
    color: #d8b4fe;
    padding: 3px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
  }

  .btn-table-action:hover {
    background: rgba(139, 92, 246, 0.4);
    color: white;
  }

  /* ── REVIEWS COMPONENT ── */
  .btn-write-review-sm {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: var(--qa-text-soft);
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    cursor: pointer;
  }

  .btn-write-review-sm:hover { background: rgba(255, 255, 255, 0.18); color: white; }

  .proto-reviews-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .review-comment-card {
    background: rgba(11, 13, 21, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 10px 12px;
  }

  .rev-user-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
  }

  .rev-avatar {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--qa-border-strong);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
  }

  .rev-user-meta { flex: 1; display: flex; flex-direction: column; }

  .rev-name { font-size: 11.5px; font-weight: 600; color: var(--qa-text-strong); }

  .rev-time { font-size: 11px; color: var(--qa-text-muted); }

  .rev-stars {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    color: #fbbf24;
    font-size: 11px;
  }

  .rev-comment-text { margin: 0; font-size: 11.5px; color: var(--qa-text-soft); line-height: 1.4; }

  /* ── FOOTBAR ── */
  .mockup-footbar {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-size: 11.5px;
  }

  .conn-item { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

  .tag-pill {
    background: rgba(139, 92, 246, 0.2);
    border: 1px solid rgba(139, 92, 246, 0.4);
    color: #c4b5fd;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 11px;
    font-family: monospace;
  }

  .tag-pill.req {
    background: rgba(16, 185, 129, 0.2);
    border-color: rgba(16, 185, 129, 0.4);
    color: #6ee7b7;
  }

  /* ── SIMULATION DIALOG MODAL ── */
  .prototype-dialog-modal {
    background: var(--qa-surface-deep);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    width: 440px;
    max-width: 90vw;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
  }

  .proto-dialog-header {
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .proto-dialog-header.success { background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), var(--qa-surface-deep)); }

  .proto-dialog-header.map { background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), var(--qa-surface-deep)); }

  .proto-dialog-header.review { background: linear-gradient(135deg, rgba(234, 179, 8, 0.2), var(--qa-surface-deep)); }

  .proto-dialog-title { font-size: 13.5px; font-weight: 700; color: var(--qa-text-strong); }

  .proto-dialog-body {
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 12px;
  }

  .dialog-icon-huge { font-size: 42px; }

  .dialog-body-text { font-size: 13px; color: var(--qa-text-soft); margin: 0; line-height: 1.5; }

  .dialog-success-badge {
    background: rgba(16, 185, 129, 0.15);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #6ee7b7;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 12px;
  }

  .simulated-map-box {
    width: 100%;
    height: 140px;
    background: var(--qa-surface-deep);
    border: 1px solid var(--qa-surface-raised);
    border-radius: 8px;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    padding: 12px;
    box-sizing: border-box;
  }

  .map-pin { font-size: 12px; font-weight: 600; text-align: left; }

  .map-pin.start { color: var(--qa-iris-soft); }

  .map-pin.end { color: #34d399; }

  .map-route-line {
    position: absolute;
    left: 20px;
    top: 30px;
    bottom: 30px;
    width: 2px;
    border-left: 2px dashed var(--qa-iris);
  }

  .dialog-review-form {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .star-rating-selector {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-size: 22px;
    cursor: default;
  }

  .star-score-tag {
    font-size: 12px;
    font-weight: 700;
    color: #fcd34d;
    margin-left: 8px;
  }

  .proto-dialog-footer {
    padding: 12px 16px;
    background: var(--qa-surface-raised);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: flex-end;
  }

  .proto-btn-dialog-close {
    background: var(--qa-iris);
    border: none;
    color: white;
    padding: 6px 16px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
  }

  .proto-btn-dialog-close:hover { background: var(--qa-iris); }

  /* ── DIAGRAMS (MERMAID & DRAW.IO STYLE) ── */
  .diagram-workspace {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1;
    transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease, opacity 0.3s ease;
  }

  .diagram-workspace.fullscreen-diagram {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: var(--z-modal, 10000);
    background: var(--qa-surface-deep);
    padding: 18px 24px;
    gap: 12px;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
    box-sizing: border-box;
  }

  .diagram-workspace.fullscreen-diagram .diagram-canvas-panel {
    flex: 1;
    min-height: 0;
    height: auto;
  }

  .diagram-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px 16px;
    background: rgba(11, 13, 21, 0.7);
    backdrop-filter: blur(8px);
    padding: 10px 18px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .diagram-toolbar.drawio-toolbar {
    background: linear-gradient(90deg, rgba(67, 56, 202, 0.25), rgba(11, 13, 21, 0.8));
    border-color: rgba(129, 140, 248, 0.25);
  }

  .diagram-title { 
    font-weight: 600; 
    font-size: 13.5px; 
    color: var(--qa-iris-soft); 
    display: flex; 
    align-items: center; 
    gap: 10px; 
  }

  .drawio-tag-badge {
    background: linear-gradient(135deg, #f97316, #ea580c);
    color: white;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: 0.5px;
    box-shadow: 0 2px 6px rgba(249, 115, 22, 0.4);
  }

  .diagram-toolbar-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .btn-ctrl-action {
    padding: 6px 12px;
    min-height: 32px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(22, 25, 38, 0.7);
    color: var(--qa-text-soft);
    display: flex;
    align-items: center;
    gap: 5px;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease, opacity 0.15s ease;
  }

  .btn-ctrl-action:hover {
    background: rgba(51, 65, 85, 0.9);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.25);
  }

  .btn-ctrl-action.grid.active {
    background: rgba(99, 102, 241, 0.25);
    border-color: var(--qa-iris);
    color: var(--qa-iris-text);
  }

  .btn-ctrl-action.copy:hover {
    background: rgba(139, 92, 246, 0.25);
    border-color: #8b5cf6;
    color: #d8b4fe;
  }

  .btn-ctrl-action.svg:hover {
    background: rgba(16, 185, 129, 0.25);
    border-color: #10b981;
    color: #6ee7b7;
  }

  .btn-ctrl-action.fs {
    background: rgba(255, 255, 255, 0.06);
  }

  .zoom-controls { 
    display: flex; 
    gap: 4px; 
    background: rgba(11, 13, 21, 0.6);
    padding: 2px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .btn-ctrl {
    background: transparent;
    border: none;
    color: var(--qa-text-muted);
    padding: 4px 10px;
    min-width: 32px;
    min-height: 28px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
  }

  .btn-ctrl:hover { background: var(--qa-surface-raised); color: white; }

  .diagram-canvas-panel {
    min-height: 580px;
    height: 680px;
    flex: 1;
    overflow: hidden;
    position: relative;
    padding: 0;
    background: var(--qa-surface-deep);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    cursor: grab;
    user-select: none;
    touch-action: none;
  }

  .diagram-canvas-panel.is-dragging {
    cursor: grabbing;
  }

  .canvas-help-badge {
    position: absolute;
    bottom: 12px;
    right: 14px;
    background: rgba(11, 13, 21, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: var(--qa-text-muted);
    font-size: 11px;
    padding: 5px 12px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: none;
    z-index: 10;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  .canvas-help-badge .sep {
    color: var(--qa-text-muted);
  }

  /* Draw.io Dot Grid Simulation */
  .diagram-canvas-panel.drawio-grid {
    background-color: #0b0f19;
    background-image: 
      radial-gradient(circle, rgba(255, 255, 255, 0.12) 1px, transparent 1px),
      radial-gradient(circle, rgba(129, 140, 248, 0.08) 1.5px, transparent 1.5px);
    background-size: 20px 20px, 100px 100px;
    background-position: 0 0, 0 0;
  }

  .diagram-render-area {
    position: absolute;
    top: 0;
    left: 0;
    display: inline-block;
    will-change: transform;
    pointer-events: auto;
  }

  .diagram-render-area :global(svg) {
    max-width: none !important;
    height: auto;
    filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.5));
    display: block;
  }

  .diagram-render-area :global(.diagram-loading),
  .diagram-render-area :global(.diagram-empty),
  .diagram-render-area :global(.diagram-error) {
    color: var(--qa-text-muted);
    font-size: 13px;
    padding: 40px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }

  .diagram-render-area :global(.spinner-small) {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: #ffffff;
    display: inline-block;
    animation: spin 0.8s linear infinite;
  }

  /* ── DRAW.IO NOTATION LEGEND BAR ── */
  .drawio-legend-bar {
    background: rgba(11, 13, 21, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 11.5px;
    color: var(--qa-text-muted);
  }

  .legend-header {
    font-weight: 600;
    color: #f1f5f9;
  }

  .legend-items {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--qa-text-soft);
  }

  .shape-sample {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 1.5px solid var(--qa-iris-soft);
    background: rgba(99, 102, 241, 0.15);
  }

  .shape-sample.pill { border-radius: 10px; border-color: #10b981; background: rgba(16, 185, 129, 0.2); }

  .shape-sample.rect { border-radius: 2px; border-color: var(--qa-iris); background: rgba(99, 102, 241, 0.2); }

  .shape-sample.diamond { transform: rotate(45deg); width: 10px; height: 10px; margin: 2px; border-color: #f59e0b; background: rgba(245, 158, 11, 0.2); }

  .shape-sample.cylinder { border-radius: 4px; border-color: #ec4899; background: rgba(236, 72, 153, 0.2); }

  .shape-sample.group { border: 1.5px dashed #a855f7; background: rgba(168, 85, 247, 0.1); border-radius: 3px; }

  /* ── Figma & Image Wireframe Extension Styles ── */
  .panel-title-group {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }

  .node-source-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: auto;
  }

  .node-source-badge.figma {
    background: rgba(168, 85, 247, 0.2);
    border: 1px solid rgba(168, 85, 247, 0.5);
    color: #d8b4fe;
  }

  .node-source-badge.img {
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(99, 102, 241, 0.5);
    color: var(--qa-iris-text);
  }

  .node-source-badge.stitch,
  .node-source-badge.stitch-sm {
    background: rgba(6, 182, 212, 0.18);
    border: 1px solid rgba(6, 182, 212, 0.5);
    color: #67e8f9;
  }

  .node-source-badge.figma-sm, .node-source-badge.img-sm, .node-source-badge.stitch-sm {
    margin-left: auto;
    font-size: 11px;
  }

  .dot-live.cyan {
    background: #06b6d4;
    box-shadow: 0 0 6px #06b6d4;
  }

  /* ── STITCH / LIVE HTML HIGH-FI UI CONTAINER ── */
  .stitch-container {
    display: flex;
    flex-direction: column;
    background: #0b0f19;
    min-height: 620px;
  }

  .stitch-config-panel {
    background: var(--qa-surface-raised, #161b2a);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .stitch-top-meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }

  .stitch-isolation-badges {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .stitch-space-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 6px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #c7d2fe;
  }

  .stitch-engine-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 9px;
    border-radius: 6px;
    background: rgba(6, 182, 212, 0.15);
    border: 1px solid rgba(6, 182, 212, 0.4);
    color: #67e8f9;
  }

  .stitch-utility-btns {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .stitch-engine-select {
    height: 30px;
    padding: 0 28px 0 10px;
    border-radius: 6px;
    font-size: 11.5px;
    background-color: #030712;
    border: 1px solid rgba(148, 163, 184, 0.28);
    color: #e2e8f0;
  }

  .figma-icon-tag.stitch-tag {
    color: #67e8f9;
  }

  .btn-figma-action.stitch-gen {
    background: linear-gradient(135deg, #06b6d4, #6366f1);
    color: #ffffff;
    box-shadow: 0 2px 10px rgba(6, 182, 212, 0.28);
  }

  .btn-figma-action.stitch-gen:hover:not(:disabled) {
    filter: brightness(1.08);
  }

  .btn-figma-action.stitch-gen:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .stitch-iframe-box {
    flex: 1;
    width: 100%;
    min-height: 640px;
    background: #ffffff;
    display: flex;
    flex-direction: column;
  }

  .stitch-live-iframe {
    width: 100%;
    height: 680px;
    border: none;
    display: block;
    background: #ffffff;
  }

  .stitch-empty-guide {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    gap: 10px;
    padding: 64px 24px;
    min-height: 520px;
    color: #94a3b8;
  }

  .stitch-empty-guide h4 {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 600;
    margin: 0;
  }

  .stitch-empty-guide p {
    font-size: 12.5px;
    max-width: 56ch;
    line-height: 1.6;
    margin: 0;
  }

  .stitch-code-drawer {
    background: #030712;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 8px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .stitch-code-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 11.5px;
    color: #94a3b8;
  }

  .stitch-code-pre {
    max-height: 200px;
    overflow: auto;
    font-size: 11px;
    line-height: 1.45;
    color: #cbd5e1;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .wf-mode-tabs-header {
    display: flex;
    background: rgba(11, 13, 21, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 3px;
    gap: 4px;
  }

  .wf-mode-tab-btn {
    background: none;
    border: none;
    color: var(--qa-text-muted);
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s, opacity 0.2s;
  }

  .wf-mode-tab-btn:hover { color: var(--qa-text-strong); background: rgba(255, 255, 255, 0.05); }

  .wf-mode-tab-btn.active {
    background: var(--qa-iris);
    color: white;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
  }

  .dot-live {
    width: 7px;
    height: 7px;
    border-radius: 50%;
  }

  .dot-live.green { background: #22c55e; box-shadow: 0 0 6px #22c55e; }

  .dot-live.blue { background: var(--qa-iris-soft); box-shadow: 0 0 6px var(--qa-iris-soft); }

  .browser-right-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .browser-ext-link {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: var(--qa-text-soft);
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    text-decoration: none;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
    white-space: nowrap;
  }

  .browser-ext-link:hover {
    background: rgba(255, 255, 255, 0.2);
    color: white;
  }

  /* ── FIGMA CONTAINER ── */
  .figma-container {
    display: flex;
    flex-direction: column;
    background: #0b0f19;
    min-height: 520px;
  }

  .figma-config-panel {
    background: var(--qa-surface-raised);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .figma-input-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .figma-icon-tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 12px;
    font-weight: 600;
    color: #c084fc;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .figma-text-input {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    background: #030712;
    border: 1px solid #374151;
    color: #f3f4f6;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12px;
    outline: none;
  }

  .figma-text-input:focus { border-color: #8b5cf6; }

  .btn-figma-action {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    display: flex;
    align-items: center;
    gap: 4px;
    white-space: nowrap;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
  }

  .btn-figma-action.connect { background: #8b5cf6; color: white; }

  .btn-figma-action.connect:hover { background: #6d28d9; }

  .btn-figma-action.sync { background: rgba(99, 102, 241, 0.2); border: 1px solid rgba(99, 102, 241, 0.4); color: var(--qa-iris-text); }

  .btn-figma-action.sync:hover:not(:disabled) { background: rgba(99, 102, 241, 0.35); }

  .btn-figma-action.token { background: rgba(255, 255, 255, 0.08); color: var(--qa-text-soft); }

  .btn-figma-action.token:hover { background: rgba(255, 255, 255, 0.15); }

  .figma-token-box {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 6px;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .token-title { font-size: 11px; color: #d8b4fe; font-weight: 500; }

  .token-form-row { display: flex; gap: 8px; }

  .figma-token-field {
    flex: 1;
    background: #030712;
    border: 1px solid #4b5563;
    color: white;
    padding: 5px 8px;
    border-radius: 4px;
    font-size: 11.5px;
  }

  .btn-save-token {
    background: var(--qa-iris);
    color: white;
    border: none;
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
  }

  .figma-iframe-box {
    flex: 1;
    min-height: 520px;
    position: relative;
    background: #1e1e1e;
  }

  .figma-embed-frame {
    width: 100%;
    height: 100%;
    min-height: 520px;
    border: none;
  }

  .figma-empty-guide {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
    color: var(--qa-text-muted);
  }

  .figma-watermark-icon { font-size: 48px; margin-bottom: 12px; }

  .figma-empty-guide h4 { color: var(--qa-text-strong); margin: 0 0 8px 0; }

  .figma-empty-guide p { max-width: 450px; font-size: 12.5px; line-height: 1.5; margin: 0; }

  /* ── IMAGE MOCKUP CONTAINER ── */
  .image-mockup-container {
    display: flex;
    flex-direction: column;
    min-height: 480px;
    background: #0b0f19;
  }

  .image-viewport-box {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }

  .image-action-toolbar {
    background: var(--qa-surface-raised);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 8px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .img-name-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    max-width: 100%;
    font-size: 12px;
    color: var(--qa-text-soft);
    font-weight: 500;
  }

  .img-name-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .img-btn-group { display: flex; flex-wrap: wrap; gap: 8px; flex-shrink: 0; }

  .btn-img-ctrl {
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
  }

  .btn-img-ctrl.zoom { background: rgba(99, 102, 241, 0.2); color: var(--qa-iris-text); border: 1px solid rgba(99, 102, 241, 0.4); }

  .btn-img-ctrl.zoom:hover { background: rgba(99, 102, 241, 0.4); }

  .btn-img-ctrl.replace { background: rgba(255, 255, 255, 0.08); color: var(--qa-text-strong); }

  .btn-img-ctrl.replace:hover { background: rgba(255, 255, 255, 0.15); }

  .btn-img-ctrl.delete { background: rgba(239, 68, 68, 0.15); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); }

  .btn-img-ctrl.delete:hover { background: rgba(239, 68, 68, 0.3); }

  .image-display-area {
    padding: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: auto;
    cursor: zoom-in;
    background: radial-gradient(circle, var(--qa-surface-raised) 10%, var(--qa-surface-deep) 90%);
  }

  .wireframe-img-render {
    max-width: 100%;
    max-height: 520px;
    object-fit: contain;
    border-radius: 6px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .image-upload-dropzone {
    flex: 1;
    margin: 20px;
    border: 2px dashed rgba(99, 102, 241, 0.4);
    border-radius: 10px;
    padding: 40px 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    cursor: pointer;
    background: rgba(11, 13, 21, 0.5);
    transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s, opacity 0.2s;
  }

  .image-upload-dropzone:hover {
    border-color: var(--qa-iris-soft);
    background: rgba(99, 102, 241, 0.08);
  }

  .drop-icon { font-size: 42px; margin-bottom: 10px; }

  .image-upload-dropzone h4 { color: var(--qa-text-strong); margin: 0 0 6px 0; }

  .image-upload-dropzone p { font-size: 12px; color: var(--qa-text-muted); margin: 0 0 16px 0; }

  .btn-upload-browse {
    background: var(--qa-iris);
    color: white;
    border: none;
    padding: 8px 18px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
  }

  .uploading-spinner {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--qa-iris-soft);
    font-size: 13px;
    font-weight: 600;
  }

  /* ── LIGHTBOX MODAL ── */
  .lightbox-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(8px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .lightbox-modal {
    background: var(--qa-surface-deep);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    max-width: 92vw;
    max-height: 92vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
  }

  .lightbox-header {
    background: var(--qa-surface-raised);
    padding: 12px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .lightbox-title { font-weight: 600; color: var(--qa-text-strong); font-size: 14px; }

  .lightbox-close {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #fca5a5;
    padding: 4px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
  }

  .lightbox-close:hover { background: rgba(239, 68, 68, 0.3); color: white; }

  .lightbox-body {
    padding: 16px;
    overflow: auto;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .lightbox-img {
    max-width: 100%;
    max-height: 80vh;
    object-fit: contain;
    border-radius: 8px;
  }

  /* ── EMPTY ANALYSIS CARD & ICON RING ── */
  .empty-analysis-card {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 48px 28px;
    background: rgba(18, 20, 28, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
  }

  .empty-analysis-card h3 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--qa-text-strong);
  }

  .empty-analysis-card p {
    margin: 0;
    max-width: 560px;
    font-size: 13px;
    color: var(--qa-text-muted);
    line-height: 1.6;
  }

  .empty-icon-ring {
    width: 68px;
    height: 68px;
    margin: 0 auto 6px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #a5b4fc;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.18), rgba(168, 85, 247, 0.14));
    border: 1px solid rgba(129, 140, 248, 0.35);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.16);
  }

  /* ── LIVE MERMAID CODE EDITOR DRAWER ── */
  .btn-ctrl-action.edit-code {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border-color: rgba(129, 140, 248, 0.36);
    color: #c7d2fe;
    background: rgba(99, 102, 241, 0.12);
  }

  .btn-ctrl-action.edit-code:hover,
  .btn-ctrl-action.edit-code.active {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.35), rgba(168, 85, 247, 0.3));
    border-color: rgba(165, 180, 252, 0.7);
    color: #ffffff;
  }

  .mermaid-editor-drawer {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px 18px;
    border-radius: 16px;
    border-color: rgba(99, 102, 241, 0.35);
    background: rgba(11, 13, 21, 0.88);
  }

  .editor-drawer-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .editor-drawer-title {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .editor-badge {
    font-family: 'Outfit', monospace;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #e0e7ff;
    background: rgba(99, 102, 241, 0.28);
    border: 1px solid rgba(129, 140, 248, 0.45);
    padding: 3px 9px;
    border-radius: 999px;
  }

  .editor-hint {
    font-size: 12px;
    color: var(--qa-text-muted);
  }

  .editor-drawer-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-editor-cancel {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: var(--qa-text-soft);
    padding: 7px 14px;
    border-radius: 10px;
    font-size: 12.5px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    transition: background 0.15s ease, color 0.15s ease;
  }

  .btn-editor-cancel:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }

  .btn-editor-save {
    background: linear-gradient(135deg, #6366f1, #a855f7);
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #ffffff;
    padding: 7px 16px;
    border-radius: 10px;
    font-size: 12.5px;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
    transition: transform 0.15s ease, filter 0.15s ease;
  }

  .btn-editor-save:hover:not(:disabled) {
    transform: translateY(-1px);
    filter: brightness(1.08);
  }

  .btn-editor-save:disabled { opacity: 0.6; cursor: not-allowed; }

  .mermaid-code-textarea {
    width: 100%;
    box-sizing: border-box;
    background: rgba(6, 8, 14, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    color: var(--qa-text);
    padding: 12px 14px;
    font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
    font-size: 12.5px;
    line-height: 1.55;
    resize: vertical;
    outline: none;
  }

  .mermaid-code-textarea:focus {
    border-color: rgba(129, 140, 248, 0.65);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.16);
  }

  /* ── RESPONSIVE LAYOUT ── */
  @media (max-width: 1180px) {
    .stats-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  @media (max-width: 1080px) {
    .sitemap-workspace {
      grid-template-columns: 1fr;
    }
    .sitemap-panel {
      max-height: 380px;
    }
  }

  @media (max-width: 960px) {
    .panel-container {
      padding: 14px 14px 28px;
    }
    .stats-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .executive-summary-bar {
      flex-direction: column;
      align-items: flex-start;
    }
  }

  @media (max-width: 640px) {
    .mock-form-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 520px) {
    .stats-grid {
      grid-template-columns: 1fr;
    }
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .empty-mockup-icon {
    color: var(--qa-text-muted);
    margin-bottom: 12px;
    display: flex;
    justify-content: center;
  }

  /* ── KEYBOARD FOCUS & TOUCH TARGETS (a11y) ── */
  .panel-container :is(button, [role="button"], a, input, textarea, select, [tabindex="0"]):focus-visible,
  .lightbox-modal:focus-visible,
  .prototype-dialog-modal:focus-visible {
    outline: 2px solid var(--qa-focus-ring);
    outline-offset: 2px;
    border-radius: 8px;
  }

  .sitemap-node-card[role="button"],
  .sitemap-child-card[role="button"],
  .image-display-area[role="button"],
  .image-upload-dropzone[role="button"],
  .gallery-photo-card[role="button"] {
    cursor: pointer;
  }

  @media (pointer: coarse) {
    .btn-ctrl,
    .btn-ctrl-action,
    .btn-nav-arrow,
    .btn-run-agent-screen,
    .btn-editor-save,
    .btn-editor-cancel,
    .nav-tab {
      min-height: 44px;
      min-width: 44px;
    }
  }

  /* ── REDUCED MOTION ── */
  @media (prefers-reduced-motion: reduce) {
    .stat-card,
    .sync-pulse-dot,
    .btn-generate-ai,
    .btn-back,
    .sitemap-node-card,
    .accordion-chevron {
      animation: none !important;
      transition: none !important;
    }
  }

  .matrix-pane-host {
    display: flex;
    flex-direction: column;
    flex: 1;
  }
</style>
