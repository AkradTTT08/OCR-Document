<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import { fade, slide, scale } from 'svelte/transition';
  import { selectedProjectStore } from './qaHistoryStore.js';
  import { toast } from './toastStore.js';
  import ProjectSelection from './ProjectSelection.svelte';
  import SmartTestLauncherModal from './SmartTestLauncherModal.svelte';
  import mermaid from 'mermaid';

  let projects = [];
  let isAnalyzing = false;
  let activeTab = 'sitemap'; // 'sitemap' | 'usecase' | 'activity' | 'sequence' | 'matrix'
  let customInstructions = "";
  let showInstructions = false;

  let isTestModalOpen = false;
  let testTargetCard = null;

  let flowData = null;
  let selectedScreenId = null;
  let selectedSitemapNode = null;

  // Wireframe / Mockup Source Modes: 'ai' | 'figma' | 'image'
  let activeWireframeTab = 'ai';
  let figmaUrlInput = '';
  let figmaTokenInput = localStorage.getItem('figma_token') || '';
  let showFigmaTokenInput = false;
  let isSyncingFigma = false;
  let isUploadingImage = false;
  let fileInputRef = null;
  let lightboxImage = null;

  // Traceability Matrix Filters
  let matrixSearchQuery = "";
  let selectedDocFilter = "All";
  let selectedStatusFilter = "All";

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
    }
  });

  // Reactive update when current selected screen changes
  $: if (currentScreenMockup) {
    activeWireframeTab = currentScreenMockup.wireframe_type || (currentScreenMockup.image_url ? 'image' : (currentScreenMockup.figma_url ? 'figma' : 'ai'));
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

  $: {
    if ($selectedProjectStore) {
      fetchAnalysis($selectedProjectStore.id || $selectedProjectStore.project_id);
    }
  }

  onMount(async () => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
      fontFamily: 'Segoe UI, Tahoma, sans-serif',
      themeVariables: {
        darkMode: true,
        background: '#0f172a',
        primaryColor: '#3b82f6',
        primaryTextColor: '#f8fafc',
        primaryBorderColor: '#60a5fa',
        lineColor: '#94a3b8',
        secondaryColor: '#8b5cf6',
        tertiaryColor: '#1e293b'
      }
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
        }
        await renderCurrentDiagram();
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
        }
        await renderCurrentDiagram();
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

  function copyCurrentMermaidCode() {
    let code = "";
    if (activeTab === 'flowchart') code = flowData?.system_flowchart || flowData?.activity_diagram || '';
    else if (activeTab === 'usecase') code = flowData?.usecase_diagram || '';
    else if (activeTab === 'activity') code = flowData?.activity_diagram || '';
    else if (activeTab === 'sequence') code = flowData?.sequence_diagram || '';

    if (!code) return;
    navigator.clipboard.writeText(code);
    toast('คัดลอกโค้ด Mermaid Diagram เรียบร้อย!', 'success');
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

  $: if (activeTab && flowData) {
    renderCurrentDiagram();
  }

  function sanitizeMermaidCode(raw) {
    if (!raw) return "";
    let text = raw.trim();

    // 1. Remove markdown code fences if present (```mermaid ... ```)
    text = text.replace(/^```(?:mermaid)?\s*/i, '').replace(/\s*```$/, '').trim();

    // 2. If it's a sequence diagram, preserve sequence syntax
    if (/^\s*sequenceDiagram/i.test(text)) {
      return text;
    }

    // Ensure header starts with flowchart
    if (!/^\s*(flowchart|graph)\b/i.test(text)) {
      text = `flowchart TD\n${text}`;
    }

    const lines = text.split(/\r?\n/);
    const resultLines = [];

    // Helper: clean and wrap text safely
    const cleanLabel = (s) => {
      if (!s) return "";
      let t = String(s).trim();
      if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
        t = t.slice(1, -1).trim();
      }
      return t.replace(/"/g, "'");
    };

    for (let line of lines) {
      let l = line.trimEnd();

      // Skip empty lines
      if (!l.trim()) {
        resultLines.push("");
        continue;
      }

      // Skip directives and comments
      if (/^\s*(%%|classDef|class|click|style|linkStyle|accTitle|accDescr)\b/i.test(l)) {
        resultLines.push(l);
        continue;
      }

      const indent = l.match(/^\s*/)[0];

      // A. Fix actor declaration in flowchart: `actor Customer as "ผู้ใช้งาน"` or `actor Customer`
      if (/^\s*actor\b/i.test(l)) {
        const actorMatch = l.match(/^\s*actor\s+([A-Za-z0-9_]+)(?:\s+(?:as\s+)?(.*))?$/i);
        if (actorMatch) {
          const id = actorMatch[1];
          const label = cleanLabel(actorMatch[2]) || id;
          resultLines.push(`${indent}${id}["👤 ${label}"]`);
          continue;
        }
      }

      // B. Fix Subgraph: `subgraph ID [Title]` or `subgraph ID ["Title"]` or `subgraph [Title]`
      const subgraphMatch = l.match(/^(\s*subgraph\s+[A-Za-z0-9_]+)\s*\[\s*([^\]]+?)\s*\]\s*$/i);
      if (subgraphMatch) {
        const title = cleanLabel(subgraphMatch[2]);
        resultLines.push(`${subgraphMatch[1]} ["${title}"]`);
        continue;
      }

      // C. Fix PlantUML / dotted arrows with colons:
      l = l.replace(/([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?/g, (m, left, right, label) => {
        return `${right} -.->|"${cleanLabel(label)}"| ${left}`;
      });
      l = l.replace(/([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?/g, (m, left, right, label) => {
        return `${left} -.->|"${cleanLabel(label)}"| ${right}`;
      });
      l = l.replace(/([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)/g, '$2 -.-> $1');
      l = l.replace(/([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)/g, '$1 -.-> $2');

      // D. Fix arrow with colon label: `A --> B : text`
      l = l.replace(/([A-Za-z0-9_]+)\s*(-->|-\.->|==>)\s*([A-Za-z0-9_]+)\s*:\s*([^\r\n]+)/g, (m, left, arrow, right, label) => {
        return `${left} ${arrow}|"${cleanLabel(label)}"| ${right}`;
      });

      // E. Fix inline arrow labels:
      // `-- (label) -->` or `-- label -->`
      l = l.replace(/--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*-->/g, (m, p1, p2) => {
        return `-->|"${cleanLabel(p1 || p2)}"|`;
      });
      l = l.replace(/--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*--\s*>/g, (m, p1, p2) => {
        return `-->|"${cleanLabel(p1 || p2)}"|`;
      });
      // `== (label) ==>` or `== label ==>`
      l = l.replace(/==\s*(?:\(([^()\r\n]+)\)|([^=>\r\n|]+?))\s*==>/g, (m, p1, p2) => {
        return `==>|"${cleanLabel(p1 || p2)}"|`;
      });
      // `-. (label) .->` or `-. label .->`
      l = l.replace(/-\.\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*\.->/g, (m, p1, p2) => {
        return `-.->|"${cleanLabel(p1 || p2)}"|`;
      });

      // F. Rename reserved node ID `End` or `end` to `EndNode` if not a standalone `end` line
      if (!/^\s*end\s*$/i.test(l)) {
        l = l.replace(/\bEnd\s*\(\[\s*(.*?)\s*\]\)/g, 'EndNode(["$1"])');
        l = l.replace(/\bEnd\s*\[\s*(.*?)\s*\]/g, 'EndNode["$1"]');
        l = l.replace(/\bEnd\s*\(\s*(.*?)\s*\)/g, 'EndNode("$1")');
        l = l.replace(/(-->|-\.->|==>)\s*End\b/g, '$1 EndNode');
        l = l.replace(/\bEnd\s*(-->|-\.->|==>)/g, 'EndNode $1');
      }

      // Step G: TOKENIZE & SAFELY QUOTE ALL NODES ON THIS LINE
      const nodeTokens = [];
      const addToken = (id, formattedNode) => {
        const idx = nodeTokens.length;
        nodeTokens.push({ id, formattedNode });
        return `__NODE_TOKEN_${idx}__`;
      };

      // 1. Stadium / Pill: `ID([ ... ])`
      l = l.replace(/([A-Za-z0-9_]+)\s*\(\[\s*([\s\S]*?)\s*\]\)/g, (m, id, inner) => {
        return addToken(id, `${id}(["${cleanLabel(inner)}"])`);
      });

      // 2. Circle: `ID(( ... ))`
      l = l.replace(/([A-Za-z0-9_]+)\s*\(\(\s*([\s\S]*?)\s*\)\)/g, (m, id, inner) => {
        return addToken(id, `${id}(("${cleanLabel(inner)}"))`);
      });

      // 3. Database Cylinder: `ID[( ... )]` or `ID[(" ... ")]`
      l = l.replace(/([A-Za-z0-9_]+)\s*\[\(\s*([\s\S]*?)\s*\)\]/g, (m, id, inner) => {
        return addToken(id, `${id}[("${cleanLabel(inner)}")]`);
      });

      // 4. Hexagon: `ID{{ ... }}`
      l = l.replace(/([A-Za-z0-9_]+)\s*\{\{\s*([\s\S]*?)\s*\}\}/g, (m, id, inner) => {
        return addToken(id, `${id}{{"${cleanLabel(inner)}"}}`);
      });

      // 5. Rhombus / Decision: `ID{ ... }`
      l = l.replace(/([A-Za-z0-9_]+)\s*\{\s*([\s\S]*?)\s*\}/g, (m, id, inner) => {
        return addToken(id, `${id}{"${cleanLabel(inner)}"}`);
      });

      // 6. Standard Box: `ID[ ... ]` (ignore subgraph lines)
      if (!/^\s*subgraph\b/i.test(l)) {
        l = l.replace(/([A-Za-z0-9_]+)\s*\[\s*([\s\S]*?)\s*\]/g, (m, id, inner) => {
          return addToken(id, `${id}["${cleanLabel(inner)}"]`);
        });
      }

      // 7. Rounded Box: `ID( ... )`
      l = l.replace(/([A-Za-z0-9_]+)\s*\(\s*([\s\S]*?)\s*\)/g, (m, id, inner) => {
        return addToken(id, `${id}("${cleanLabel(inner)}")`);
      });

      // H. Clean pipe labels |...|
      l = l.replace(/\|([^|]+)\|/g, (m, rawPipe) => {
        return `|"${cleanLabel(rawPipe)}"|`;
      });

      // I. Handle chained edges like `A -->|label| __NODE_TOKEN_0__ --> B`
      // Split into two lines: `A -->|label| __NODE_TOKEN_0__` and `TARGET_ID --> B`
      const chainMatch = l.match(/^(\s*)(.*?(?:-->|-\.->|==>).*?\s+)(__NODE_TOKEN_(\d+)__)\s*(-->|-\.->|==>)\s*(.+)$/);
      if (chainMatch) {
        const lineIndent = chainMatch[1];
        const tokenIdx = parseInt(chainMatch[4], 10);
        const middleNodeId = nodeTokens[tokenIdx] ? nodeTokens[tokenIdx].id : chainMatch[3];
        const firstPart = `${lineIndent}${chainMatch[2]}${chainMatch[3]}`;
        const secondPart = `${lineIndent}${middleNodeId} ${chainMatch[5]} ${chainMatch[6].trim()}`;

        // Restore tokens for firstPart
        let resFirst = firstPart.replace(/__NODE_TOKEN_(\d+)__/g, (tm, tIdx) => {
          return nodeTokens[parseInt(tIdx, 10)]?.formattedNode || tm;
        });
        // Restore tokens for secondPart
        let resSecond = secondPart.replace(/__NODE_TOKEN_(\d+)__/g, (tm, tIdx) => {
          return nodeTokens[parseInt(tIdx, 10)]?.formattedNode || tm;
        });

        resultLines.push(resFirst);
        resultLines.push(resSecond);
        continue;
      }

      // J. Restore all node tokens
      l = l.replace(/__NODE_TOKEN_(\d+)__/g, (tm, tIdx) => {
        return nodeTokens[parseInt(tIdx, 10)]?.formattedNode || tm;
      });

      resultLines.push(l);
    }

    // Auto-close any unclosed subgraphs
    let subgraphCount = 0;
    let endCount = 0;
    for (const line of resultLines) {
      if (/^\s*subgraph\b/i.test(line)) subgraphCount++;
      if (/^\s*end\s*$/i.test(line.trim())) endCount++;
    }
    while (subgraphCount > endCount) {
      resultLines.push('  end');
      endCount++;
    }

    return resultLines.join('\n');
  }

  async function renderCurrentDiagram() {
    await tick();
    if (!diagramContainer || !flowData) return;

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
      const id = `mermaid-svg-${Date.now()}`;
      diagramContainer.innerHTML = '<div class="diagram-loading"><span class="spinner-small"></span> กำลัง Render Flowchart...</div>';
      const { svg } = await mermaid.render(id, cleanCode);
      diagramContainer.innerHTML = svg;
      await tick();
      fitView();
    } catch (err) {
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

  function handleSelectSitemapNode(node) {
    selectedSitemapNode = node;
    if (node.screen_id) {
      selectedScreenId = node.screen_id;
    } else if (flowData && flowData.screen_mockups) {
      const matched = flowData.screen_mockups.find(s => s.screen_name === node.title || (s.route && s.route === node.path));
      if (matched) selectedScreenId = matched.screen_id;
    }
  }

  $: currentScreenMockup = (flowData && flowData.screen_mockups) 
    ? flowData.screen_mockups.find(s => s.screen_id === selectedScreenId) || flowData.screen_mockups[0]
    : null;

  // ── Prototype Interactive State ──
  let prototypeDevice = 'desktop'; // 'desktop' | 'tablet' | 'mobile'
  let activePrototypeTab = '';
  let isFavorite = false;
  let formValues = {};
  let isSimulatingSubmit = false;
  let activePrototypeModal = null; // null | { title: '...', content: '...', type: '...' }

  // Reactive default form values sync when screen changes
  $: if (currentScreenMockup) {
    if (currentScreenMockup.tabs && currentScreenMockup.tabs.length > 0 && !activePrototypeTab) {
      activePrototypeTab = currentScreenMockup.tabs[0];
    }
    const mockId = currentScreenMockup.screen_id || 'DEFAULT';
    if (!formValues[mockId]) {
      formValues[mockId] = {};
      if (currentScreenMockup.sections) {
        currentScreenMockup.sections.forEach(sec => {
          if (sec.fields) {
            sec.fields.forEach(f => {
              formValues[mockId][f.label] = f.default_value !== undefined ? f.default_value : (f.default !== undefined ? f.default : (f.placeholder || ''));
            });
          }
        });
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
    toast('⚡ เติมข้อมูลจำลองสำหรับทดสอบ Prototype เรียบร้อย', 'success');
  }

  function resetPrototype() {
    if (!currentScreenMockup) return;
    const mockId = currentScreenMockup.screen_id || 'DEFAULT';
    formValues[mockId] = {};
    isFavorite = false;
    toast('🔄 รีเซ็ตค่าฟอร์ม Prototype สำเร็จ', 'info');
  }

  function handlePrototypeButtonAction(btn) {
    const label = (btn.label || btn || '').toLowerCase();
    if (label.includes('สั่ง') || label.includes('บันทึก') || label.includes('save') || label.includes('submit') || label.includes('sign in') || label.includes('เข้าสู่ระบบ') || label.includes('claim')) {
      isSimulatingSubmit = true;
      setTimeout(() => {
        isSimulatingSubmit = false;
        activePrototypeModal = {
          title: '🎉 ดำเนินการสำเร็จ (Simulation Success)',
          content: `ระบบทำการประมวลผลคำขอ "${btn.label || 'Submit'}" และบันทึกข้อมูลเข้าสู่ฐานข้อมูลเรียบร้อยแล้ว`,
          type: 'success'
        };
      }, 500);
    } else if (label.includes('นำทาง') || label.includes('map') || label.includes('แผนที่')) {
      const addr = formValues[currentScreenMockup.screen_id]?.['ที่อยู่ / สถานที่ตั้ง'] || formValues[currentScreenMockup.screen_id]?.['ที่อยู่'] || 'จุดหมายปลายทาง';
      activePrototypeModal = {
        title: '🧭 จำลองระบบ GPS นำทาง (Route Simulator)',
        content: `กำลังเชื่อมต่อไปยัง: ${addr} (ระยะทาง 1.8 กม. ใช้เวลาเดินทางโดยรถยนต์ประมาณ 7 นาที)`,
        type: 'map'
      };
    } else if (label.includes('โทร') || label.includes('call') || label.includes('phone')) {
      const phone = formValues[currentScreenMockup.screen_id]?.['เบอร์โทรศัพท์ติดต่อ'] || formValues[currentScreenMockup.screen_id]?.['เบอร์โทร'] || '02-123-4567';
      toast(`📞 กำลังจำลองการโทรออกไปยังเบอร์: ${phone}`, 'info');
    } else if (label.includes('รีวิว') || label.includes('review')) {
      activePrototypeModal = {
        title: '⭐ ฟอร์มส่งรีวิวและความประทับใจ',
        content: 'คุณกำลังเขียนรีวิวและให้คะแนน 5 ดาวสำหรับ ' + (currentScreenMockup.header?.title || currentScreenMockup.screen_name),
        type: 'review'
      };
    } else {
      toast(`✨ คลิกปุ่ม Prototype: "${btn.label || btn}" สำเร็จ`, 'info');
    }
  }

  function handlePrototypeHeaderAction(act) {
    const s = String(act).toLowerCase();
    if (s.includes('แชร์') || s.includes('share')) {
      if (typeof navigator !== 'undefined' && navigator.clipboard) {
        navigator.clipboard.writeText(window.location.href);
      }
      toast('🔗 คัดลอกลิงก์หน้าจอ Prototype แล้ว!', 'success');
    } else if (s.includes('โปรด') || s.includes('favorite') || s.includes('like') || s.includes('บันทึกร้าน')) {
      isFavorite = !isFavorite;
      toast(isFavorite ? '❤️ เพิ่มในรายการโปรดแล้ว' : '🤍 นำออกจากรายการโปรดแล้ว', 'info');
    } else if (s.includes('ย้อนกลับ') || s.includes('back')) {
      if (flowData?.screen_mockups && flowData.screen_mockups.length > 1) {
        const currIdx = flowData.screen_mockups.findIndex(s => s.screen_id === selectedScreenId);
        const prevIdx = currIdx > 0 ? currIdx - 1 : flowData.screen_mockups.length - 1;
        selectedScreenId = flowData.screen_mockups[prevIdx].screen_id;
        toast(`◀ ย้อนกลับไปยังหน้า: ${flowData.screen_mockups[prevIdx].screen_name}`, 'info');
      } else {
        toast('◀ ย้อนกลับ', 'info');
      }
    } else {
      toast(`✨ คลิก: ${act}`, 'info');
    }
  }

  function handleTableActionClick(cellText, row) {
    toast(`⚡ ดำเนินการ Action: "${cellText}" สำหรับรายการ "${row[1] || row[0]}" สำเร็จ`, 'success');
  }

  function getUatStatusClass(val) {
    if (!val) return 'pending';
    const s = String(val).toLowerCase();
    if (s.includes('pass') || s.includes('approved') || s.includes('sign-off') || s.includes('success')) return 'passed';
    if (s.includes('ready') || s.includes('tested') || s.includes('active')) return 'ready';
    if (s.includes('fail') || s.includes('reject') || s.includes('block')) return 'failed';
    return 'pending';
  }

  function getUatItems(row) {
    if (!row) return [];
    if (Array.isArray(row.uat_item) && row.uat_item.length > 0) return row.uat_item;
    if (Array.isArray(row.uat_items) && row.uat_items.length > 0) return row.uat_items;
    if (Array.isArray(row.uat_clause) && row.uat_clause.length > 0) return row.uat_clause;
    if (row.uat_item && typeof row.uat_item === 'string' && row.uat_item.trim() && row.uat_item !== '-') return [row.uat_item];
    if (row.uat_clause && typeof row.uat_clause === 'string' && row.uat_clause.trim() && row.uat_clause !== '-') return [row.uat_clause];
    if (row.uat_ref && typeof row.uat_ref === 'string' && row.uat_ref.trim() && row.uat_ref !== '-') return [row.uat_ref];
    
    // Fallback: derive linked UAT item code from req_code and req_title
    const cleanCode = (row.req_code || 'REQ').replace(/^REQ-?/i, '');
    const titleSummary = row.req_title || row.sitemap_node_title || 'Acceptance Criteria';
    return [`UAT-${cleanCode}: ${titleSummary}`];
  }

  // Filtered Matrix
  $: uniqueDocs = flowData && flowData.traceability_matrix 
    ? ['All', ...new Set(flowData.traceability_matrix.map(m => m.doc_name).filter(Boolean))]
    : ['All'];

  $: filteredMatrix = (flowData && flowData.traceability_matrix) ? flowData.traceability_matrix.filter(item => {
    const uatMatches = getUatItems(item).join(' ').toLowerCase();
    const matchQuery = !matrixSearchQuery || 
      (item.req_code && item.req_code.toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.req_title && item.req_title.toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.use_case_id && item.use_case_id.toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.screen_name && item.screen_name.toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.defect_log && String(item.defect_log).toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.defects && String(item.defects).toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      uatMatches.includes(matrixSearchQuery.toLowerCase()) ||
      (item.uat_status && String(item.uat_status).toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.uat && String(item.uat).toLowerCase().includes(matrixSearchQuery.toLowerCase()));
    
    const matchDoc = selectedDocFilter === 'All' || item.doc_name === selectedDocFilter;
    const matchStatus = selectedStatusFilter === 'All' || item.status === selectedStatusFilter;

    return matchQuery && matchDoc && matchStatus;
  }) : [];

  function exportMatrixCSV() {
    if (!filteredMatrix.length) return;
    const headers = ["Req Code", "Requirement Title", "Document", "Doc Type", "Sitemap Node", "Use Case", "Screen", "Test Cases", "Defect Log", "UAT Reference (ข้อเอกสาร UAT)", "UAT Status", "Status"];
    const rows = filteredMatrix.map(m => {
      const uatList = getUatItems(m).join('; ');
      return [
        `"${m.req_code || ''}"`,
        `"${(m.req_title || '').replace(/"/g, '""')}"`,
        `"${m.doc_name || ''}"`,
        `"${m.doc_type || ''}"`,
        `"${m.sitemap_node_title || ''}"`,
        `"${(m.use_case_id || '').replace(/"/g, '""')}"`,
        `"${m.screen_name || m.screen_id || ''}"`,
        `"${(Array.isArray(m.test_cases) ? m.test_cases.join('; ') : m.test_cases || '').replace(/"/g, '""')}"`,
        `"${(Array.isArray(m.defect_log) ? m.defect_log.join('; ') : (m.defect_log || m.defects || 'No Defects')).replace(/"/g, '""')}"`,
        `"${uatList.replace(/"/g, '""')}"`,
        `"${(m.uat_status || m.uat || (m.status === 'Covered' ? 'Ready for UAT' : 'Pending')).replace(/"/g, '""')}"`,
        `"${m.status || ''}"`
      ];
    });

    const csvContent = "\uFEFF" + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Traceability_Matrix_${$selectedProjectStore?.project_code || 'Project'}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast('ดาวน์โหลดตาราง Traceability Matrix (CSV) เรียบร้อย', 'success');
  }
</script>

<div class="panel-container" in:fade>
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
      <button class="btn-back" on:click={() => selectedProjectStore.set(null)}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>

      <div class="project-pill">
        <span class="p-badge">{$selectedProjectStore.project_code || 'PROJ'}</span>
        <span class="p-title">{$selectedProjectStore.name || $selectedProjectStore.project_name}</span>
      </div>
    </div>

    <!-- Header & AI Control Banner -->
    <div class="glass-panel banner-panel">
      <div class="banner-header">
        <div>
          <div class="title-with-badge">
            <h2>QA Analysis Diagram & Flow Modeler</h2>
            <span class="badge-ai">Agent 7: Flow Architect</span>
          </div>
          <p class="desc-text">
            ประมวลผลและสร้างผัง Flow ระบบ, Sitemap โครงสร้างเมนู, UML Diagrams, Wireframe Mockups, และตาราง Traceability Matrix เชื่อมโยงทุก Markdown ในโครงการ
          </p>
        </div>

        <div class="action-buttons">
          <button class="btn-generate-ai" on:click={handleGenerateAnalysis} disabled={isAnalyzing}>
            {#if isAnalyzing}
              <div class="spinner-small"></div> กำลังวิเคราะห์ Flow & Diagrams...
            {:else}
              ⚡ วิเคราะห์และสร้าง Diagram ใหม่ (AI Synthesizer)
            {/if}
          </button>
        </div>
      </div>

      <!-- Optional Instruction Dropdown -->
      <div class="instructions-accordion">
        <button class="accordion-toggle" on:click={() => showInstructions = !showInstructions}>
          <span>{showInstructions ? '▼' : '▶'} คำสั่งเพิ่มเติม / Specific Focus Instructions (Optional)</span>
        </button>
        {#if showInstructions}
          <div class="accordion-content" transition:slide>
            <textarea 
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
        <div class="stats-grid" transition:fade>
          <div class="stat-card">
            <div class="stat-icon">📑</div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_modules || (flowData.sitemap ? flowData.sitemap.length : 0)}</div>
              <div class="stat-label">Modules / Menus</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">💻</div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_screens || (flowData.screen_mockups ? flowData.screen_mockups.length : 0)}</div>
              <div class="stat-label">Screen Mockups</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">👥</div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_use_cases || 0}</div>
              <div class="stat-label">Use Cases</div>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon">📋</div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.total_requirements || (flowData.traceability_matrix ? flowData.traceability_matrix.length : 0)}</div>
              <div class="stat-label">Requirements</div>
            </div>
          </div>
          <div class="stat-card highlight">
            <div class="stat-icon">🎯</div>
            <div class="stat-info">
              <div class="stat-val">{flowData.summary_stats.coverage_percentage || 100}%</div>
              <div class="stat-label">QA Traceability Coverage</div>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Main Navigation Tabs -->
    <div class="tabs-header">
      <button class="nav-tab" class:active={activeTab === 'sitemap'} on:click={() => activeTab = 'sitemap'}>
        🌐 Flow Sitemap & Wireframes
      </button>
      <button class="nav-tab" class:active={activeTab === 'flowchart'} on:click={() => activeTab = 'flowchart'}>
        🔀 System Flowchart
      </button>
      <button class="nav-tab" class:active={activeTab === 'usecase'} on:click={() => activeTab = 'usecase'}>
        👥 Use Case Diagram
      </button>
      <button class="nav-tab" class:active={activeTab === 'activity'} on:click={() => activeTab = 'activity'}>
        ⚡ Activity & Process Flow
      </button>
      <button class="nav-tab" class:active={activeTab === 'sequence'} on:click={() => activeTab = 'sequence'}>
        🔄 Sequence & Architecture
      </button>
      <button class="nav-tab" class:active={activeTab === 'matrix'} on:click={() => activeTab = 'matrix'}>
        📋 Traceability Matrix
      </button>
    </div>

    <!-- Tab Contents -->
    {#if !flowData}
      <div class="glass-panel empty-analysis-card">
        <div class="empty-icon">📊</div>
        <h3>ยังไม่มีข้อมูล Flow Analysis สำหรับโครงการนี้</h3>
        <p>กดปุ่ม <b>"⚡ วิเคราะห์และสร้าง Diagram ใหม่"</b> ด้านบน เพื่อให้ AI Agent ประมวลผลเอกสาร Markdown และสร้างผังระบบ</p>
      </div>
    {:else}
      <!-- TAB 1: SITEMAP & WIREFRAMES -->
      {#if activeTab === 'sitemap'}
        <div class="sitemap-workspace" transition:fade>
          <!-- Left: Sitemap Tree Navigation -->
          <div class="glass-panel sitemap-panel">
            <div class="panel-title-row">
              <h3>🗺️ Flow Sitemap (เมนูและโครงสร้างหน้า)</h3>
              <span class="count-badge">{flowData.sitemap ? flowData.sitemap.length : 0} Modules</span>
            </div>
            <p class="sub-hint">คลิกที่โหนดเมนูเพื่อดู Mockup จำลองหน้าจอ UI ที่เชื่อมโยง</p>

            <div class="sitemap-tree">
              {#if !flowData.sitemap || flowData.sitemap.length === 0}
                <div class="empty-hint">ไม่พบข้อมูล Sitemap</div>
              {:else}
                {#each flowData.sitemap as node}
                  <div class="sitemap-node-card" class:active={selectedScreenId === node.screen_id} on:click={() => handleSelectSitemapNode(node)}>
                    <div class="node-main">
                      <span class="node-icon">{node.icon || '📁'}</span>
                      <div class="node-text">
                        <div class="node-title">{node.title}</div>
                        <div class="node-path">{node.path}</div>
                      </div>
                      {#if node.category}
                        <span class="node-category">{node.category}</span>
                      {/if}
                      {#if flowData.screen_mockups?.find(s => s.screen_id === node.screen_id)?.figma_url}
                        <span class="node-source-badge figma" title="เชื่อมต่อ Figma Frame แล้ว">🎨 Figma</span>
                      {:else if flowData.screen_mockups?.find(s => s.screen_id === node.screen_id)?.image_url}
                        <span class="node-source-badge img" title="มีรูปภาพ Mockup แล้ว">🖼️ Image</span>
                      {/if}
                    </div>
                    {#if node.description}
                      <div class="node-desc">{node.description}</div>
                    {/if}

                    <!-- Children / Sub-pages -->
                    {#if node.children && node.children.length > 0}
                      <div class="node-children">
                        {#each node.children as child}
                          <div class="sitemap-child-card" class:active={selectedScreenId === child.screen_id} on:click|stopPropagation={() => handleSelectSitemapNode(child)}>
                            <span class="child-icon">{child.icon || '📄'}</span>
                            <div class="child-info">
                              <span class="child-title">{child.title}</span>
                              <span class="child-path">{child.path}</span>
                            </div>
                            {#if flowData.screen_mockups?.find(s => s.screen_id === child.screen_id)?.figma_url}
                              <span class="node-source-badge figma-sm">🎨</span>
                            {:else if flowData.screen_mockups?.find(s => s.screen_id === child.screen_id)?.image_url}
                              <span class="node-source-badge img-sm">🖼️</span>
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
                <h3>💻 Screen Mockup & UI Wireframe</h3>
                {#if currentScreenMockup}
                  <span class="screen-id-badge">{currentScreenMockup.screen_id}</span>
                {/if}
              </div>

              <!-- Wireframe Source Mode Selector Tabs -->
              {#if currentScreenMockup}
                <div class="wf-mode-tabs-header">
                  <button 
                    class="wf-mode-tab-btn" 
                    class:active={activeWireframeTab === 'ai'} 
                    on:click={() => handleSwitchWireframeTab('ai')}>
                    🤖 AI Wireframe
                  </button>
                  <button 
                    class="wf-mode-tab-btn" 
                    class:active={activeWireframeTab === 'figma'} 
                    on:click={() => handleSwitchWireframeTab('figma')}>
                    🎨 Figma MCP & Embed
                    {#if currentScreenMockup.figma_url}
                      <span class="dot-live green"></span>
                    {/if}
                  </button>
                  <button 
                    class="wf-mode-tab-btn" 
                    class:active={activeWireframeTab === 'image'} 
                    on:click={() => handleSwitchWireframeTab('image')}>
                    🖼️ Upload Image
                    {#if currentScreenMockup.image_url}
                      <span class="dot-live blue"></span>
                    {/if}
                  </button>
                </div>
              {/if}
            </div>

            {#if !currentScreenMockup}
              <div class="empty-mockup">
                <div style="font-size: 36px; margin-bottom: 12px;">🖥️</div>
                <div style="font-weight: 600; color: #f8fafc; font-size: 15px;">เลือกเมนูทางซ้ายเพื่อแสดง UI Prototype</div>
                <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">ระบบจะจำลองหน้าจอและส่วนประกอบ UI เสมือนจริงที่พร้อมโต้ตอบได้ทันที</div>
              </div>
            {:else}
              <!-- Prototype Toolbar: Viewport Frame Switcher & Utilities -->
              <div class="prototype-control-bar">
                <div class="device-switch-group">
                  <button 
                    class="btn-device-switch" 
                    class:active={prototypeDevice === 'desktop'} 
                    on:click={() => prototypeDevice = 'desktop'}
                    title="มุมมองหน้าจอ Desktop (100% Wide)">
                    🖥️ Desktop
                  </button>
                  <button 
                    class="btn-device-switch" 
                    class:active={prototypeDevice === 'tablet'} 
                    on:click={() => prototypeDevice = 'tablet'}
                    title="มุมมองหน้าจอ Tablet (768px)">
                    📱 Tablet
                  </button>
                  <button 
                    class="btn-device-switch" 
                    class:active={prototypeDevice === 'mobile'} 
                    on:click={() => prototypeDevice = 'mobile'}
                    title="มุมมองหน้าจอ Mobile Smartphone (375px)">
                    📲 Mobile
                  </button>
                </div>

                <div class="prototype-quick-actions">
                  <button class="btn-proto-action fill" on:click={fillSampleData} title="เติมข้อมูลจำลองอัตโนมัติลงในทุกช่องเพื่อทดสอบ">
                    ⚡ เติมข้อมูลตัวอย่าง (Sample Data)
                  </button>
                  <button class="btn-proto-action reset" on:click={resetPrototype} title="ล้างค่าฟอร์มกลับเป็นค่าเริ่มต้น">
                    🔄 รีเซ็ต
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
                      <div class="phone-icons">5G 📶 🔋</div>
                    </div>
                  {/if}

                  <!-- Mockup Browser Bar -->
                  <div class="mockup-browser-bar">
                    <div class="browser-dots">
                      <span class="dot red" on:click={resetPrototype} title="รีเซ็ต"></span>
                      <span class="dot yellow"></span>
                      <span class="dot green"></span>
                    </div>
                    <div class="browser-nav-arrows">
                      <button class="btn-nav-arrow" on:click={() => handlePrototypeHeaderAction('ย้อนกลับ')} title="ย้อนกลับ">◀</button>
                      <button class="btn-nav-arrow" on:click={fillSampleData} title="รีเฟรช">🔄</button>
                    </div>
                    <div class="browser-url-input">
                      <span class="lock-icon">🔒</span>
                      {#if activeWireframeTab === 'figma' && currentScreenMockup.figma_url}
                        {currentScreenMockup.figma_url}
                      {:else}
                        https://{($selectedProjectStore.project_code || 'foodsmile').toLowerCase()}.app{currentScreenMockup.route || '/'}
                      {/if}
                    </div>
                    <div class="browser-right-actions">
                      <button class="btn-run-agent-screen" on:click={() => handleTestScreenWithAgent(currentScreenMockup)} title="เปิดระบบ AI Test Agent เพื่อทดสอบหน้าจอนี้">
                        🚀 ทดสอบด้วย AI
                      </button>
                      {#if activeWireframeTab === 'figma' && currentScreenMockup.figma_url}
                        <a href={currentScreenMockup.figma_url} target="_blank" rel="noreferrer" class="browser-ext-link" title="เปิดใน Figma">
                          ↗️ Figma
                        </a>
                      {:else if activeWireframeTab === 'image' && currentScreenMockup.image_url}
                        <button class="browser-ext-link" on:click={() => lightboxImage = currentScreenMockup.image_url}>
                          🔍 Fullscreen
                        </button>
                      {/if}
                    </div>
                  </div>

                  <!-- MODE 1: FIGMA EMBED / MCP SYNC -->
                  {#if activeWireframeTab === 'figma'}
                    <div class="figma-container">
                      <div class="figma-config-panel">
                        <div class="figma-input-row">
                          <span class="figma-icon-tag">🎨 Figma Link:</span>
                          <input 
                            type="text" 
                            bind:value={figmaUrlInput} 
                            placeholder="https://www.figma.com/design/.../...?node-id=..." 
                            class="figma-text-input" 
                          />
                          <button class="btn-figma-action connect" on:click={handleSaveFigmaUrl}>
                            🔗 Connect & Save
                          </button>
                          <button class="btn-figma-action sync" on:click={handleSyncFigmaImage} disabled={isSyncingFigma}>
                            {#if isSyncingFigma}
                              <span class="spinner-small"></span> Syncing...
                            {:else}
                              🔄 Sync MCP / API
                            {/if}
                          </button>
                          <button class="btn-figma-action token" on:click={() => showFigmaTokenInput = !showFigmaTokenInput} title="Figma Personal Access Token">
                            ⚙️ Token
                          </button>
                        </div>

                        {#if showFigmaTokenInput}
                          <div class="figma-token-box" transition:slide>
                            <div class="token-title">🔑 Figma Access Token (สำหรับดึงภาพอัตโนมัติผ่าน Figma MCP/REST API):</div>
                            <div class="token-form-row">
                              <input 
                                type="password" 
                                bind:value={figmaTokenInput} 
                                placeholder="figd_xxxxxxxxx" 
                                class="figma-token-field"
                              />
                              <button class="btn-save-token" on:click={() => { localStorage.setItem('figma_token', figmaTokenInput.trim()); toast('บันทึก Figma Token แล้ว', 'success'); showFigmaTokenInput = false; }}>
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
                          <div class="figma-watermark-icon">🎨</div>
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
                            <span class="img-name-tag">📷 {currentScreenMockup.image_filename || 'Mockup Screenshot'}</span>
                            <div class="img-btn-group">
                              <button class="btn-img-ctrl zoom" on:click={() => lightboxImage = currentScreenMockup.image_url}>
                                🔍 ขยายเต็มจอ
                              </button>
                              <button class="btn-img-ctrl replace" on:click={() => fileInputRef?.click()} disabled={isUploadingImage}>
                                🔄 เปลี่ยนภาพ
                              </button>
                              <button class="btn-img-ctrl delete" on:click={handleRemoveImage}>
                                🗑️ ลบภาพ
                              </button>
                            </div>
                          </div>
                          <div class="image-display-area" on:click={() => lightboxImage = currentScreenMockup.image_url}>
                            <img src={`${currentScreenMockup.image_url}`} alt="Screen Wireframe Mockup" class="wireframe-img-render" />
                          </div>
                        </div>
                      {:else}
                        <div 
                          class="image-upload-dropzone" 
                          class:uploading={isUploadingImage}
                          on:click={() => fileInputRef?.click()}
                          on:dragover|preventDefault
                          on:drop|preventDefault={(e) => {
                            const file = e.dataTransfer?.files?.[0];
                            if (file) handleFileUpload({ target: { files: [file] } });
                          }}
                        >
                          <div class="drop-icon">🖼️</div>
                          <h4>อัปโหลดรูปภาพ Screen Mockup / Wireframe</h4>
                          <p>ลากรูปภาพมาวางที่นี่ หรือคลิกเพื่อเลือกไฟล์ (รองรับ PNG, JPG, WebP, SVG)</p>
                          {#if isUploadingImage}
                            <div class="uploading-spinner">
                              <span class="spinner-small"></span> กำลังอัปโหลดภาพ...
                            </div>
                          {:else}
                            <button class="btn-upload-browse">📁 เลือกไฟล์ภาพจากเครื่อง</button>
                          {/if}
                        </div>
                      {/if}
                    </div>

                  <!-- MODE 3: AI HIGH-FIDELITY INTERACTIVE PROTOTYPE -->
                  {:else}

                  <!-- Mockup Screen Body -->
                  <div class="mockup-screen-content interactive-proto">
                    
                    <!-- Screen Hero / Header Bar -->
                    <div class="proto-hero-card">
                      <div class="proto-hero-main">
                        <div class="proto-title-badge-row">
                          <h3 class="proto-screen-title">
                            {currentScreenMockup.header?.title || currentScreenMockup.screen_name}
                          </h3>
                          {#if currentScreenMockup.header?.badge}
                            <span class="proto-verified-badge {currentScreenMockup.header.badge_color || 'emerald'}">
                              ✨ {currentScreenMockup.header.badge}
                            </span>
                          {:else}
                            <span class="proto-verified-badge emerald">
                              ✨ Production Ready
                            </span>
                          {/if}
                        </div>
                        <p class="proto-desc-text">
                          {currentScreenMockup.description || 'Interactive prototype screen wired with live form inputs, dynamic state management, and functional UI components.'}
                        </p>
                      </div>

                      <div class="proto-header-action-toolbar">
                        {#if currentScreenMockup.header?.actions}
                          {#each currentScreenMockup.header.actions as act}
                            <button 
                              class="btn-proto-header-action" 
                              class:favorited={isFavorite && (act.includes('โปรด') || act.includes('favorite') || act.includes('like'))}
                              on:click={() => handlePrototypeHeaderAction(act)}>
                              {#if act.includes('แชร์') || act.includes('share')}
                                🔗 {act}
                              {:else if act.includes('โปรด') || act.includes('favorite') || act.includes('like')}
                                {isFavorite ? '❤️ เป็นร้านโปรดแล้ว' : '🤍 ' + act}
                              {:else if act.includes('ย้อน') || act.includes('back')}
                                ◀ {act}
                              {:else}
                                ⚙️ {act}
                              {/if}
                            </button>
                          {/each}
                        {:else}
                          <button class="btn-proto-header-action" on:click={() => handlePrototypeHeaderAction('แชร์หน้าร้าน')}>
                            🔗 แชร์
                          </button>
                          <button 
                            class="btn-proto-header-action" 
                            class:favorited={isFavorite}
                            on:click={() => handlePrototypeHeaderAction('บันทึกรายการโปรด')}>
                            {isFavorite ? '❤️ รายการโปรด' : '🤍 บันทึก'}
                          </button>
                        {/if}
                      </div>
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
                    {:else}
                      <!-- Fallback Smart Metric Grid for standard screens -->
                      <div class="proto-stats-grid">
                        <div class="proto-stat-card amber">
                          <div class="stat-card-label">คะแนนความพึงพอใจ</div>
                          <div class="stat-card-value">4.85 ★</div>
                          <div class="stat-card-sub">จาก 342 รีวิว</div>
                        </div>
                        <div class="proto-stat-card emerald">
                          <div class="stat-card-label">สถานะการทำงาน</div>
                          <div class="stat-card-value">เปิดบริการอยู่</div>
                          <div class="stat-card-sub">ปิด 22:00 น.</div>
                        </div>
                        <div class="proto-stat-card blue">
                          <div class="stat-card-label">เวลาจัดส่งเฉลี่ย</div>
                          <div class="stat-card-value">25-35 นาที</div>
                          <div class="stat-card-sub">ระยะทาง 1.8 กม.</div>
                        </div>
                        <div class="proto-stat-card purple">
                          <div class="stat-card-label">ระดับราคา</div>
                          <div class="stat-card-value">฿฿ (100-250)</div>
                          <div class="stat-card-sub">รับ PromptPay/บัตร</div>
                        </div>
                      </div>
                    {/if}

                    <!-- Interactive Tabs Bar -->
                    {#if currentScreenMockup.tabs && currentScreenMockup.tabs.length > 0}
                      <div class="proto-tabs-navbar">
                        {#each currentScreenMockup.tabs as tb}
                          <button 
                            class="proto-nav-tab-btn" 
                            class:active={activePrototypeTab === tb} 
                            on:click={() => { activePrototypeTab = tb; toast(`สลับไปยังแท็บ: ${tb}`, 'info'); }}>
                            {tb}
                          </button>
                        {/each}
                      </div>
                    {/if}

                    <!-- Dynamic Sections Stack -->
                    <div class="mockup-sections-stack">
                      {#if currentScreenMockup.sections}
                        {#each currentScreenMockup.sections as sec, secIdx}
                          
                          <!-- SECTION: GALLERY / BANNER -->
                          {#if sec.type === 'gallery' || sec.images}
                            <div class="proto-section-card gallery">
                              <div class="proto-sec-header">
                                <div class="mock-sec-title">🖼️ {sec.section_name || 'Image Gallery & Highlights'}</div>
                                {#if sec.banner_tag}
                                  <span class="proto-tag-highlight">{sec.banner_tag}</span>
                                {/if}
                              </div>
                              <div class="proto-gallery-grid">
                                {#each (sec.images || [{ title: 'ภาพบรรยากาศหลัก', desc: 'โซนที่นั่งสบาย มีที่จอดรถ' }, { title: 'โซน Dining Room', desc: 'ห้องปรับอากาศรองรับ 30 ที่นั่ง' }, { title: 'Open Kitchen', desc: 'มาตรฐานความสะอาด SHA Plus+' }]) as img, idx}
                                  <div class="gallery-photo-card" on:click={() => toast(`🔍 ดูภาพขยาย: ${img.title}`, 'info')}>
                                    <div class="photo-visual-placeholder grad-{idx % 4}">
                                      <span class="photo-cam-icon">📷</span>
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
                            <div class="proto-section-card form">
                              <div class="proto-sec-header">
                                <div class="mock-sec-title">📝 {sec.section_name || 'Interactive Form Details'}</div>
                                <span class="proto-interactive-tag">⚡ Live Editable</span>
                              </div>

                              <div class="mock-form-grid">
                                {#each (sec.fields || []) as f}
                                  <div class="mock-form-item" class:full-width={f.type === 'textarea' || (f.label && f.label.includes('ที่อยู่'))}>
                                    <label class="mock-label" for="fld-{secIdx}-{f.label}">
                                      {f.label} {#if f.required}<span class="req-star">*</span>{/if}
                                    </label>

                                    {#if f.type === 'toggle' || (f.label && f.label.includes('เปิดรับ'))}
                                      <div class="proto-toggle-wrap">
                                        <label class="proto-switch">
                                          <input 
                                            type="checkbox" 
                                            bind:checked={formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label]}
                                          />
                                          <span class="switch-slider"></span>
                                        </label>
                                        <span class="toggle-status-text">
                                          {formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label] ? '🟢 เปิดใช้งาน (Active)' : '⚪ ปิดใช้งาน (Disabled)'}
                                        </span>
                                      </div>

                                    {:else if f.type === 'select' || f.options}
                                      <div class="proto-input-wrapper">
                                        <select 
                                          id="fld-{secIdx}-{f.label}"
                                          class="proto-real-select"
                                          bind:value={formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label]}
                                        >
                                          {#each (f.options || ['ตัวเลือก 1', 'ตัวเลือก 2', 'ตัวเลือก 3']) as opt}
                                            <option value={opt}>{opt}</option>
                                          {/each}
                                        </select>
                                        <span class="select-chevron">▼</span>
                                      </div>

                                    {:else if f.type === 'textarea' || (f.label && f.label.includes('ที่อยู่'))}
                                      <textarea 
                                        id="fld-{secIdx}-{f.label}"
                                        class="proto-real-textarea"
                                        rows="3"
                                        placeholder={f.placeholder || f.label}
                                        bind:value={formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label]}
                                      ></textarea>

                                    {:else if f.type === 'checkbox'}
                                      <label class="proto-real-checkbox">
                                        <input 
                                          type="checkbox" 
                                          bind:checked={formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label]} 
                                        />
                                        <span>{f.label}</span>
                                      </label>

                                    {:else}
                                      <div class="proto-input-wrapper">
                                        <input 
                                          type={f.type === 'password' ? 'password' : 'text'}
                                          id="fld-{secIdx}-{f.label}"
                                          class="proto-real-input"
                                          placeholder={f.placeholder || f.label}
                                          bind:value={formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label]}
                                        />
                                        {#if formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label]}
                                          <button 
                                            class="btn-input-clear" 
                                            on:click={() => formValues[currentScreenMockup.screen_id || 'DEFAULT'][f.label] = ''} 
                                            title="ล้างข้อมูล">✕</button>
                                        {/if}
                                      </div>
                                    {/if}
                                  </div>
                                {/each}
                              </div>

                              <!-- Action Buttons Row -->
                              {#if sec.buttons && sec.buttons.length > 0}
                                <div class="mock-btn-row">
                                  {#each sec.buttons as btn}
                                    <button 
                                      class="proto-action-btn {btn.variant || 'primary'}"
                                      disabled={isSimulatingSubmit}
                                      on:click={() => handlePrototypeButtonAction(btn)}>
                                      {#if isSimulatingSubmit && (btn.variant === 'primary' || (btn.label && btn.label.includes('สั่ง')))}
                                        <span class="spinner-small"></span> กำลังประมวลผล...
                                      {:else}
                                        {#if btn.icon}<span>{btn.icon}</span>{/if}
                                        <span>{btn.label}</span>
                                      {/if}
                                    </button>
                                  {/each}
                                </div>
                              {/if}
                            </div>

                          <!-- SECTION: DATA TABLE -->
                          {:else if sec.type === 'table' || sec.table_headers}
                            <div class="proto-section-card table">
                              <div class="proto-sec-header">
                                <div class="mock-sec-title">📊 {sec.section_name || 'Data Table Overview'}</div>
                                <span class="proto-count-badge">{(sec.table_rows || []).length} รายการ</span>
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
                                    {#each (sec.table_rows || [['#01', 'สเต๊กแซลมอนนอร์เวย์', 'จานหลัก', '320.-', 'พร้อมเสิร์ฟ', 'สั่งซื้อเลย'], ['#02', 'สปาเก็ตตี้คาโบนาร่าทรัฟเฟิล', 'พาสต้า', '260.-', 'พร้อมเสิร์ฟ', 'สั่งซื้อเลย']]) as row}
                                      <tr class="proto-table-row">
                                        {#each row as cell, cellIdx}
                                          <td>
                                            {#if String(cell).includes('พร้อม') || String(cell).includes('Active') || String(cell).includes('สำเร็จ')}
                                              <span class="table-pill success">🟢 {cell}</span>
                                            {:else if String(cell).includes('รอ') || String(cell).includes('Pending')}
                                              <span class="table-pill warning">⏳ {cell}</span>
                                            {:else if String(cell).startsWith('#')}
                                              <span class="table-code-badge">{cell}</span>
                                            {:else if cellIdx === row.length - 1}
                                              <button class="btn-table-action" on:click={() => handleTableActionClick(cell, row)}>
                                                ⚡ {cell}
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
                                <div class="mock-sec-title">💬 {sec.section_name || 'Customer Reviews & Feedback'}</div>
                                <button class="btn-write-review-sm" on:click={() => handlePrototypeButtonAction({ label: 'เขียนรีวิว' })}>
                                  ✍️ เขียนรีวิว
                                </button>
                              </div>

                              <div class="proto-reviews-list">
                                {#each (sec.reviews || [{ user: 'นันทนา กุลสวัสดิ์', rating: 5, comment: 'อาหารอร่อยมาก บรรยากาศดี พนักงานบริการสุภาพ แนะนำเลยค่ะ!', time: '1 ชม. ที่แล้ว' }, { user: 'เอกรัฐ พัฒนา', rating: 5, comment: 'ที่จอดรถสะดวก อาหารเสิร์ฟรวดเร็ว คุ้มราคามากครับ', time: 'เมื่อวานนี้' }]) as rev}
                                  <div class="review-comment-card">
                                    <div class="rev-user-header">
                                      <div class="rev-avatar">👤</div>
                                      <div class="rev-user-meta">
                                        <div class="rev-name">{rev.user}</div>
                                        <div class="rev-time">{rev.time || 'เมื่อสักครู่'}</div>
                                      </div>
                                      <div class="rev-stars">
                                        {'⭐'.repeat(rev.rating || 5)}
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
                                <div class="mock-sec-title">📦 {sec.section_name}</div>
                              {/if}
                              <div class="proto-generic-content">
                                <p style="color: #cbd5e1; font-size: 12px; margin: 0 0 10px 0;">{sec.description || 'Interactive section component with dynamic controls.'}</p>
                              </div>
                            </div>
                          {/if}

                        {/each}
                      {/if}
                    </div>

                    <!-- Connected Entities Footbar -->
                    <div class="mockup-footbar">
                      <div class="conn-item">
                        <b>🔗 Connected Use Cases:</b> 
                        {#if currentScreenMockup.connected_use_cases}
                          {#each currentScreenMockup.connected_use_cases as uc}
                            <span class="tag-pill">{uc}</span>
                          {/each}
                        {:else}
                          <span style="color: #94a3b8;">-</span>
                        {/if}
                      </div>
                      <div class="conn-item">
                        <b>📋 Requirements:</b> 
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
          <div class="lightbox-backdrop" transition:fade on:click={() => activePrototypeModal = null}>
            <div class="prototype-dialog-modal" on:click|stopPropagation>
              <div class="proto-dialog-header {activePrototypeModal.type}">
                <div class="proto-dialog-title">{activePrototypeModal.title}</div>
                <button class="lightbox-close" on:click={() => activePrototypeModal = null}>✕</button>
              </div>
              <div class="proto-dialog-body">
                {#if activePrototypeModal.type === 'success'}
                  <div class="dialog-icon-huge">🎉</div>
                  <p class="dialog-body-text">{activePrototypeModal.content}</p>
                  <div class="dialog-success-badge">HTTP 200 OK • State Updated</div>
                {:else if activePrototypeModal.type === 'map'}
                  <div class="dialog-map-preview">
                    <div class="simulated-map-box">
                      <div class="map-route-line"></div>
                      <div class="map-pin start">📍 จุดเริ่มต้นของคุณ</div>
                      <div class="map-pin end">🏁 ร้านอาหารเป้าหมาย</div>
                    </div>
                  </div>
                  <p class="dialog-body-text">{activePrototypeModal.content}</p>
                {:else if activePrototypeModal.type === 'review'}
                  <div class="dialog-review-form">
                    <div class="star-rating-selector">
                      <span class="star-sel active">⭐</span>
                      <span class="star-sel active">⭐</span>
                      <span class="star-sel active">⭐</span>
                      <span class="star-sel active">⭐</span>
                      <span class="star-sel active">⭐</span>
                      <span class="star-score-tag">5.0 (ยอดเยี่ยม)</span>
                    </div>
                    <textarea class="proto-real-textarea" rows="3" placeholder="พิมพ์ความคิดเห็นของคุณที่นี่..."></textarea>
                  </div>
                {/if}
              </div>
              <div class="proto-dialog-footer">
                <button class="proto-btn-dialog-close" on:click={() => { toast('บันทึกการดำเนินการเรียบร้อย', 'success'); activePrototypeModal = null; }}>
                  ตกลง / ดำเนินการต่อ
                </button>
              </div>
            </div>
          </div>
        {/if}

      <!-- TAB 2, 3, 4, 5: SYSTEM FLOWCHART & UML DIAGRAMS -->
      {:else if activeTab === 'flowchart' || activeTab === 'usecase' || activeTab === 'activity' || activeTab === 'sequence'}
        <div class="diagram-workspace" class:fullscreen-diagram={isFullscreenDiagram} transition:fade>
          <!-- Controls bar -->
          <div class="diagram-toolbar" class:drawio-toolbar={activeTab === 'flowchart'}>
            <div class="diagram-title">
              {#if activeTab === 'flowchart'}
                <span class="drawio-tag-badge">📐 Draw.io Style</span>
                <span>🔀 System Workflow Flowchart (ผังการทำงานทั้งระบบ)</span>
              {:else if activeTab === 'usecase'}
                <span>👥 Use Case Diagram (Actors & Functional Boundaries)</span>
              {:else if activeTab === 'activity'}
                <span>⚡ Activity & Decision Flow Diagram</span>
              {:else if activeTab === 'sequence'}
                <span>🔄 Sequence & Component Architecture Flow</span>
              {/if}
            </div>

            <div class="diagram-toolbar-actions">
              {#if activeTab === 'flowchart'}
                <button 
                  class="btn-ctrl-action grid" 
                  class:active={showDrawioGrid} 
                  on:click={() => showDrawioGrid = !showDrawioGrid} 
                  title="เปิด/ปิดเส้นตาราง Grid แบบ Draw.io">
                  ▦ Grid {showDrawioGrid ? 'ON' : 'OFF'}
                </button>
              {/if}

              <button class="btn-ctrl-action copy" on:click={copyCurrentMermaidCode} title="คัดลอกโค้ด Mermaid">
                📋 Copy Code
              </button>

              <button class="btn-ctrl-action svg" on:click={exportDiagramSVG} title="บันทึกรูปภาพ SVG">
                💾 Export SVG
              </button>

              <div class="zoom-controls">
                <button class="btn-ctrl" on:click={zoomIn} title="ขยาย (Zoom In)">🔍+</button>
                <button class="btn-ctrl" on:click={zoomOut} title="ย่อ (Zoom Out)">🔍-</button>
                <button class="btn-ctrl" on:click={fitView} title="ปรับขนาดให้พอดีหน้าจอ (Fit to Screen)">🎯 Fit</button>
                <button class="btn-ctrl" on:click={zoomReset} title="ขนาด 100%">{Math.round(zoomLevel * 100)}%</button>
              </div>

              <button class="btn-ctrl-action fs" on:click={() => { isFullscreenDiagram = !isFullscreenDiagram; setTimeout(fitView, 200); }} title="ขยายเต็มหน้าจอ">
                {isFullscreenDiagram ? '✕ ย่อจอ' : '⛶ เต็มจอ'}
              </button>
            </div>
          </div>

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
              <span>🖱️ คลิกลากเมาส์เพื่อเลื่อนผัง (Pan)</span>
              <span class="sep">•</span>
              <span>🔄 สกอลล์เมาส์เพื่อซูม (Zoom)</span>
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
            <div class="drawio-legend-bar" transition:slide>
              <div class="legend-header">📐 สัญลักษณ์ผัง Flowchart (Draw.io Notation):</div>
              <div class="legend-items">
                <div class="legend-item"><span class="shape-sample pill"></span> 🏁 Start / Terminal Gate</div>
                <div class="legend-item"><span class="shape-sample rect"></span> ⚙️ Process Step / Action</div>
                <div class="legend-item"><span class="shape-sample diamond"></span> 🔀 Decision / Condition Gate</div>
                <div class="legend-item"><span class="shape-sample cylinder"></span> 💾 Database & Vector Store</div>
                <div class="legend-item"><span class="shape-sample group"></span> 🔲 Subgraph / Tier Swimlane</div>
              </div>
            </div>
          {/if}
        </div>

      <!-- TAB 5: TRACEABILITY MATRIX -->
      {:else if activeTab === 'matrix'}
        <div class="matrix-workspace" transition:fade>
          <!-- Filter Controls -->
          <div class="glass-panel matrix-controls-panel">
            <div class="matrix-filter-row">
              <div class="search-box">
                <span class="search-icon">🔍</span>
                <input 
                  type="text" 
                  bind:value={matrixSearchQuery} 
                  placeholder="ค้นหา Requirement Code, Use Case, หรือ หน้าจอ..." 
                  class="matrix-search-input"
                />
              </div>

              <div class="filter-select-group">
                <label>เอกสารต้นทาง:</label>
                <select bind:value={selectedDocFilter} class="filter-select">
                  {#each uniqueDocs as doc}
                    <option value={doc}>{doc}</option>
                  {/each}
                </select>
              </div>

              <div class="filter-select-group">
                <label>สถานะ Coverage:</label>
                <select bind:value={selectedStatusFilter} class="filter-select">
                  <option value="All">ทั้งหมด (All Status)</option>
                  <option value="Covered">✅ Covered</option>
                  <option value="Partially Covered">⚠️ Partially Covered</option>
                  <option value="Pending">⏳ Pending</option>
                </select>
              </div>

              <button class="btn-export-csv" on:click={exportMatrixCSV}>
                📥 Export CSV
              </button>
            </div>
          </div>

          <!-- Matrix Table -->
          <div class="glass-panel matrix-table-panel">
            <div class="table-container">
              <table class="matrix-table">
                <thead>
                  <tr>
                    <th style="width: 7%;">Req Code</th>
                    <th style="width: 15%;">Requirement Title</th>
                    <th style="width: 11%;">Source Document</th>
                    <th style="width: 10%;">Sitemap / Menu</th>
                    <th style="width: 10%;">Use Case</th>
                    <th style="width: 10%;">Screen Mockup</th>
                    <th style="width: 10%;">Test Scenarios</th>
                    <th style="width: 10%;">Defect Log</th>
                    <th style="width: 13%;">ข้อเอกสาร UAT (UAT Reference)</th>
                    <th style="width: 8%; text-align: center;">Coverage</th>
                  </tr>
                </thead>
                <tbody>
                  {#if filteredMatrix.length === 0}
                    <tr>
                      <td colspan="10" style="text-align: center; color: #94a3b8; padding: 30px;">
                        ไม่พบข้อมูล Traceability Matrix ที่ตรงกับเงื่อนไข
                      </td>
                    </tr>
                  {:else}
                    {#each filteredMatrix as row}
                      <tr>
                        <td><span class="code-badge">{row.req_code}</span></td>
                        <td style="font-weight: 500; color: #f8fafc;">{row.req_title}</td>
                        <td>
                          <div class="doc-cell">
                            <span class="doc-icon">📄</span>
                            <span class="doc-name" title={row.doc_name}>{row.doc_name}</span>
                          </div>
                        </td>
                        <td><span class="sitemap-pill">{row.sitemap_node_title || '-'}</span></td>
                        <td><span class="usecase-pill">{row.use_case_id || '-'}</span></td>
                        <td>
                          <button class="screen-link-btn" on:click={() => { activeTab = 'sitemap'; selectedScreenId = row.screen_id; }}>
                            💻 {row.screen_name || row.screen_id || '-'}
                          </button>
                        </td>
                        <td>
                          {#if Array.isArray(row.test_cases)}
                            <div class="testcases-list">
                              {#each row.test_cases as tc}
                                <span class="tc-item">{tc}</span>
                              {/each}
                            </div>
                          {:else}
                            <span>{row.test_cases || '-'}</span>
                          {/if}
                        </td>
                        <td>
                          {#if Array.isArray(row.defect_log) && row.defect_log.length > 0}
                            <div class="defect-list">
                              {#each row.defect_log as d}
                                <span class="defect-pill open" title={d}>🐛 {d}</span>
                              {/each}
                            </div>
                          {:else if row.defect_log && String(row.defect_log).trim() && row.defect_log !== '-'}
                            <span class="defect-pill open" title={row.defect_log}>🐛 {row.defect_log}</span>
                          {:else if Array.isArray(row.defects) && row.defects.length > 0}
                            <div class="defect-list">
                              {#each row.defects as d}
                                <span class="defect-pill open" title={d}>🐛 {d}</span>
                              {/each}
                            </div>
                          {:else if row.defects && String(row.defects).trim() && row.defects !== '-'}
                            <span class="defect-pill open" title={row.defects}>🐛 {row.defects}</span>
                          {:else}
                            <span class="defect-pill clean" title="ไม่มี Defect ค้าง">✨ No Defects</span>
                          {/if}
                        </td>
                        <td>
                          <div class="uat-list">
                            {#each getUatItems(row) as uatItem}
                              <div class="uat-item-row" title={uatItem}>
                                <span class="uat-code-tag">📋 {uatItem.includes(':') ? uatItem.split(':')[0] : 'UAT'}</span>
                                <span class="uat-title-text">{uatItem.includes(':') ? uatItem.split(':').slice(1).join(':').trim() : uatItem}</span>
                              </div>
                            {/each}
                            <div class="uat-status-sub">
                              <span class="uat-pill {getUatStatusClass(row.uat_status || row.uat || (row.status === 'Covered' ? 'Ready for UAT' : 'Pending'))}">
                                {row.uat_status || row.uat || (row.status === 'Covered' ? 'Ready for UAT' : '⏳ UAT Pending')}
                              </span>
                            </div>
                          </div>
                        </td>
                        <td style="text-align: center;">
                          <span class="status-badge {String(row.status || '').toLowerCase().replace(' ', '-')}">
                            {row.status || 'Covered'}
                          </span>
                        </td>
                      </tr>
                    {/each}
                  {/if}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      {/if}
    {/if}

  {/if}

  <!-- Fullscreen Image Lightbox Modal -->
  {#if lightboxImage}
    <div class="lightbox-backdrop" transition:fade on:click={() => lightboxImage = null}>
      <div class="lightbox-modal" on:click|stopPropagation>
        <div class="lightbox-header">
          <div class="lightbox-title">🖼️ Screen Mockup (Full Resolution)</div>
          <button class="lightbox-close" on:click={() => lightboxImage = null}>✕ ปิดหน้าต่าง</button>
        </div>
        <div class="lightbox-body">
          <img src={`${lightboxImage}`} alt="Full Resolution Mockup" class="lightbox-img" />
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
    background: linear-gradient(135deg, #7c3aed, #4f46e5);
    border: none;
    color: white;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 4px;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(124, 58, 237, 0.4);
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s;
    white-space: nowrap;
  }
  .btn-run-agent-screen:hover {
    background: linear-gradient(135deg, #6d28d9, #4338ca);
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.6);
  }
  .panel-container {
    display: flex;
    flex-direction: column;
    gap: 18px;
    height: 100%;
    overflow-y: auto;
    padding: 20px 24px;
    max-width: 100%;
    box-sizing: border-box;
    color: #f8fafc;
  }

  .top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .btn-back {
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    transition: color 0.2s;
  }

  .btn-back:hover { color: #f8fafc; }

  .project-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 13px;
  }

  .p-badge {
    background: #3b82f6;
    color: white;
    font-weight: 700;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .p-title { font-weight: 500; color: #e2e8f0; }

  .glass-panel {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 20px;
  }

  .banner-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .banner-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
  }

  .title-with-badge {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 6px;
  }

  .title-with-badge h2 {
    margin: 0;
    font-size: 1.45rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .badge-ai {
    background: linear-gradient(135deg, #8b5cf6, #ec4899);
    color: white;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    letter-spacing: 0.5px;
  }

  .desc-text {
    margin: 0;
    color: #94a3b8;
    font-size: 0.92rem;
    line-height: 1.5;
  }

  .btn-generate-ai {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    border: none;
    color: white;
    padding: 10px 20px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 13.5px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.35);
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .btn-generate-ai:hover:not(:disabled) {
    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.55);
    transform: translateY(-1px);
  }

  .btn-generate-ai:disabled { opacity: 0.6; cursor: not-allowed; }

  .instructions-accordion {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 10px;
  }

  .accordion-toggle {
    background: none;
    border: none;
    color: #a5b4fc;
    font-size: 13px;
    cursor: pointer;
    padding: 0;
    font-weight: 500;
  }

  .instructions-textarea {
    width: 100%;
    margin-top: 8px;
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #334155;
    color: white;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    box-sizing: border-box;
    outline: none;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin-top: 6px;
  }

  .stat-card {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .stat-card.highlight {
    border-color: rgba(34, 197, 94, 0.4);
    background: rgba(34, 197, 94, 0.08);
  }

  .stat-icon { font-size: 24px; }
  .stat-val { font-size: 1.25rem; font-weight: 700; color: #f8fafc; }
  .stat-label { font-size: 11px; color: #94a3b8; font-weight: 500; }

  .tabs-header {
    display: flex;
    gap: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding-bottom: 2px;
  }

  .nav-tab {
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: #94a3b8;
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .nav-tab:hover { color: #f8fafc; }
  .nav-tab.active {
    color: #60a5fa;
    border-bottom-color: #3b82f6;
  }

  /* ── SITEMAP & WIREFRAME LAYOUT ── */
  .sitemap-workspace {
    display: grid;
    grid-template-columns: 380px 1fr;
    gap: 18px;
    flex: 1;
    min-height: 550px;
  }

  .sitemap-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 750px;
    overflow-y: auto;
  }

  .panel-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .panel-title-row h3 { margin: 0; font-size: 1.1rem; color: #f8fafc; }

  .count-badge, .screen-id-badge {
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #93c5fd;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
  }

  .sub-hint { margin: 0; font-size: 12px; color: #94a3b8; }

  .sitemap-tree {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .sitemap-node-card {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 12px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .sitemap-node-card:hover {
    border-color: rgba(96, 165, 250, 0.5);
    background: rgba(30, 41, 59, 0.8);
  }

  .sitemap-node-card.active {
    border-color: #3b82f6;
    background: rgba(59, 130, 246, 0.15);
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.25);
  }

  .node-main {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .node-icon { font-size: 20px; }
  .node-text { flex: 1; min-width: 0; }
  .node-title { font-weight: 600; font-size: 13.5px; color: #f8fafc; }
  .node-path { font-size: 11px; color: #60a5fa; font-family: monospace; }

  .node-category {
    font-size: 10px;
    background: rgba(255, 255, 255, 0.1);
    padding: 2px 6px;
    border-radius: 4px;
    color: #cbd5e1;
  }

  .node-desc {
    margin-top: 6px;
    font-size: 11.5px;
    color: #94a3b8;
    line-height: 1.4;
  }

  .node-children {
    margin-top: 10px;
    padding-left: 14px;
    border-left: 2px solid rgba(255, 255, 255, 0.1);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .sitemap-child-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.2);
    font-size: 12px;
    transition: background 0.15s;
  }

  .sitemap-child-card:hover { background: rgba(59, 130, 246, 0.2); }
  .sitemap-child-card.active { background: rgba(59, 130, 246, 0.3); border-left: 3px solid #60a5fa; }
  .child-title { font-weight: 500; color: #e2e8f0; }
  .child-path { font-size: 10px; color: #93c5fd; margin-left: 6px; font-family: monospace; }

  /* ── MOCKUP WIREFRAME ── */
  .mockup-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .empty-mockup {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: #94a3b8;
  }

  .mockup-viewport {
    background: #090d16;
    border: 1px solid #1e293b;
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
  }

  .mockup-browser-bar {
    background: #1e293b;
    padding: 8px 14px;
    display: flex;
    align-items: center;
    gap: 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .browser-dots { display: flex; gap: 6px; }
  .dot { width: 10px; height: 10px; border-radius: 50%; }
  .dot.red { background: #ef4444; }
  .dot.yellow { background: #f59e0b; }
  .dot.green { background: #10b981; }

  .browser-url-input {
    flex: 1;
    background: #0f172a;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    color: #94a3b8;
    font-family: monospace;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  /* ── INTERACTIVE PROTOTYPE & WIREFRAME WORKSPACE ── */
  .prototype-control-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
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
    color: #94a3b8;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .btn-device-switch:hover { color: #f8fafc; }
  .btn-device-switch.active {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    color: white;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  }

  .proto-actions-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-proto-action {
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.12);
    display: flex;
    align-items: center;
    gap: 5px;
    transition: all 0.2s;
  }
  .btn-proto-action.fill-data {
    background: rgba(234, 179, 8, 0.15);
    border-color: rgba(234, 179, 8, 0.4);
    color: #fde047;
  }
  .btn-proto-action.fill-data:hover {
    background: rgba(234, 179, 8, 0.3);
    box-shadow: 0 0 10px rgba(234, 179, 8, 0.3);
  }
  .btn-proto-action.reset {
    background: rgba(255, 255, 255, 0.06);
    color: #94a3b8;
  }
  .btn-proto-action.reset:hover { background: rgba(255, 255, 255, 0.12); color: #f8fafc; }

  .prototype-badge-live {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.4);
    color: #86efac;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .prototype-badge-live .pulse-dot {
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
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    overflow-x: auto;
  }

  .prototype-outer-canvas.desktop {
    padding: 16px;
  }
  .prototype-outer-canvas.desktop .mockup-screen-content {
    width: 100%;
    max-width: 100%;
    border-radius: 8px;
  }

  .prototype-outer-canvas.tablet {
    padding: 24px 16px;
  }
  .prototype-outer-canvas.tablet .mockup-screen-content {
    width: 768px;
    max-width: 100%;
    border-radius: 16px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .prototype-outer-canvas.mobile {
    padding: 24px 12px;
  }
  .prototype-outer-canvas.mobile .mockup-screen-content {
    width: 390px;
    max-width: 100%;
    border-radius: 36px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 0 8px #1e293b;
    border: 2px solid rgba(255, 255, 255, 0.18);
    overflow: hidden;
  }

  .mobile-phone-notch-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 18px 4px 18px;
    font-size: 11px;
    color: #94a3b8;
    background: rgba(15, 23, 42, 0.95);
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }
  .phone-dynamic-island {
    width: 80px;
    height: 18px;
    background: #000;
    border-radius: 12px;
    margin: 0 auto;
  }
  .phone-status-icons { font-size: 10px; font-weight: 600; color: #cbd5e1; }

  .mockup-screen-content {
    background: #0f172a;
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 20px;
    transition: width 0.3s ease;
    box-sizing: border-box;
  }

  /* ── HERO BANNER CARD ── */
  .proto-hero-card {
    background: linear-gradient(135deg, rgba(30, 58, 138, 0.35), rgba(15, 23, 42, 0.8));
    border: 1px solid rgba(96, 165, 250, 0.25);
    border-radius: 12px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .proto-hero-main {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    flex-wrap: wrap;
  }

  .proto-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .proto-screen-title {
    margin: 0;
    font-size: 1.35rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .proto-verified-badge {
    background: linear-gradient(135deg, #059669, #10b981);
    color: white;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 20px;
    box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3);
  }

  .proto-header-action-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-proto-header-action {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .btn-proto-header-action:hover {
    background: rgba(255, 255, 255, 0.18);
    color: #ffffff;
  }
  .btn-proto-header-action.fav.active {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.5);
    color: #fca5a5;
  }

  .mockup-desc {
    margin: 0;
    font-size: 12.5px;
    color: #94a3b8;
    line-height: 1.5;
  }

  /* ── STATS KPI CARDS ── */
  .proto-stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;
  }

  .proto-stat-card {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    transition: transform 0.15s;
  }
  .proto-stat-card:hover {
    transform: translateY(-2px);
    border-color: rgba(96, 165, 250, 0.3);
  }

  .proto-stat-icon-wrap { font-size: 20px; }
  .proto-stat-body { display: flex; flex-direction: column; }
  .proto-stat-num { font-size: 1.15rem; font-weight: 700; color: #f8fafc; }
  .proto-stat-lbl { font-size: 10.5px; color: #94a3b8; font-weight: 500; }

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
    color: #94a3b8;
    padding: 6px 14px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .proto-nav-tab-btn:hover { color: #f8fafc; }
  .proto-nav-tab-btn.active {
    color: #60a5fa;
    border-bottom-color: #3b82f6;
  }

  /* ── SECTION STACK ── */
  .mockup-sections-stack {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .proto-section-card {
    background: rgba(30, 41, 59, 0.65);
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
    color: #93c5fd;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .proto-interactive-tag {
    background: rgba(59, 130, 246, 0.18);
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #93c5fd;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 12px;
  }

  .proto-tag-highlight {
    background: rgba(234, 179, 8, 0.15);
    border: 1px solid rgba(234, 179, 8, 0.4);
    color: #fde047;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 12px;
  }

  .proto-count-badge {
    background: rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    font-size: 10.5px;
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
    background: #090d16;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: transform 0.2s, border-color 0.2s;
  }
  .gallery-photo-card:hover {
    transform: translateY(-2px);
    border-color: rgba(96, 165, 250, 0.5);
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
    font-size: 9px;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 4px;
  }

  .photo-card-info { padding: 8px 10px; }
  .photo-title { font-size: 11.5px; font-weight: 600; color: #f8fafc; margin-bottom: 2px; }
  .photo-desc { font-size: 10.5px; color: #94a3b8; line-height: 1.3; }

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
    color: #cbd5e1;
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
    background: #030712;
    border: 1px solid #374151;
    color: #f8fafc;
    padding: 7px 10px;
    border-radius: 6px;
    font-size: 12.5px;
    box-sizing: border-box;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .proto-real-input:focus, .proto-real-select:focus, .proto-real-textarea:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25);
  }

  .proto-real-select {
    appearance: none;
    cursor: pointer;
    padding-right: 28px;
  }
  .select-chevron {
    position: absolute;
    right: 10px;
    font-size: 9px;
    color: #94a3b8;
    pointer-events: none;
  }

  .btn-input-clear {
    position: absolute;
    right: 8px;
    background: none;
    border: none;
    color: #94a3b8;
    font-size: 11px;
    cursor: pointer;
    padding: 2px 4px;
  }
  .btn-input-clear:hover { color: #f8fafc; }

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
    background-color: #334155;
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

  .toggle-status-text { font-size: 11.5px; color: #cbd5e1; font-weight: 500; }

  .proto-real-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #e2e8f0;
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
    transition: all 0.2s;
  }
  .proto-action-btn.primary {
    background: linear-gradient(135deg, #3b82f6, #6366f1);
    color: white;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
  }
  .proto-action-btn.primary:hover:not(:disabled) {
    box-shadow: 0 6px 18px rgba(59, 130, 246, 0.55);
    transform: translateY(-1px);
  }
  .proto-action-btn.secondary {
    background: rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
  .proto-action-btn.secondary:hover { background: rgba(255, 255, 255, 0.15); color: white; }
  .proto-action-btn.map {
    background: linear-gradient(135deg, #059669, #10b981);
    color: white;
  }
  .proto-action-btn:disabled { opacity: 0.6; cursor: not-allowed; }

  .spinner-small {
    width: 12px;
    height: 12px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: white;
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
    color: #94a3b8;
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
    font-size: 10.5px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-block;
  }
  .table-pill.success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; }
  .table-pill.warning { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }

  .table-code-badge {
    background: rgba(59, 130, 246, 0.15);
    color: #93c5fd;
    font-family: monospace;
    font-weight: 700;
    font-size: 10.5px;
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
    transition: all 0.15s;
  }
  .btn-table-action:hover {
    background: rgba(139, 92, 246, 0.4);
    color: white;
  }

  /* ── REVIEWS COMPONENT ── */
  .btn-write-review-sm {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
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
    background: rgba(15, 23, 42, 0.7);
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
    background: #334155;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
  }
  .rev-user-meta { flex: 1; display: flex; flex-direction: column; }
  .rev-name { font-size: 11.5px; font-weight: 600; color: #f8fafc; }
  .rev-time { font-size: 9.5px; color: #64748b; }
  .rev-stars { font-size: 11px; letter-spacing: 1px; }
  .rev-comment-text { margin: 0; font-size: 11.5px; color: #cbd5e1; line-height: 1.4; }

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
    font-size: 10.5px;
    font-family: monospace;
  }
  .tag-pill.req {
    background: rgba(16, 185, 129, 0.2);
    border-color: rgba(16, 185, 129, 0.4);
    color: #6ee7b7;
  }

  /* ── SIMULATION DIALOG MODAL ── */
  .prototype-dialog-modal {
    background: #0f172a;
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
  .proto-dialog-header.success { background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), #0f172a); }
  .proto-dialog-header.map { background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), #0f172a); }
  .proto-dialog-header.review { background: linear-gradient(135deg, rgba(234, 179, 8, 0.2), #0f172a); }

  .proto-dialog-title { font-size: 13.5px; font-weight: 700; color: #f8fafc; }

  .proto-dialog-body {
    padding: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 12px;
  }

  .dialog-icon-huge { font-size: 42px; }
  .dialog-body-text { font-size: 13px; color: #cbd5e1; margin: 0; line-height: 1.5; }

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
    background: #020617;
    border: 1px solid #1e293b;
    border-radius: 8px;
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    padding: 12px;
    box-sizing: border-box;
  }
  .map-pin { font-size: 12px; font-weight: 600; text-align: left; }
  .map-pin.start { color: #60a5fa; }
  .map-pin.end { color: #34d399; }
  .map-route-line {
    position: absolute;
    left: 20px;
    top: 30px;
    bottom: 30px;
    width: 2px;
    border-left: 2px dashed #3b82f6;
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
    cursor: pointer;
  }
  .star-score-tag {
    font-size: 12px;
    font-weight: 700;
    color: #fcd34d;
    margin-left: 8px;
  }

  .proto-dialog-footer {
    padding: 12px 16px;
    background: #111827;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: flex-end;
  }

  .proto-btn-dialog-close {
    background: #3b82f6;
    border: none;
    color: white;
    padding: 6px 16px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  }
  .proto-btn-dialog-close:hover { background: #2563eb; }

  /* ── DIAGRAMS (MERMAID & DRAW.IO STYLE) ── */
  .diagram-workspace {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1;
    transition: all 0.3s ease;
  }

  .diagram-workspace.fullscreen-diagram {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 9999;
    background: #090d16;
    padding: 18px 24px;
    gap: 12px;
    height: 100vh;
  }

  .diagram-workspace.fullscreen-diagram .diagram-canvas-panel {
    height: calc(100vh - 120px);
    min-height: 0;
  }

  .diagram-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(15, 23, 42, 0.7);
    backdrop-filter: blur(8px);
    padding: 10px 18px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .diagram-toolbar.drawio-toolbar {
    background: linear-gradient(90deg, rgba(30, 58, 138, 0.25), rgba(15, 23, 42, 0.8));
    border-color: rgba(96, 165, 250, 0.25);
  }

  .diagram-title { 
    font-weight: 600; 
    font-size: 13.5px; 
    color: #60a5fa; 
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
    gap: 8px;
  }

  .btn-ctrl-action {
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(30, 41, 59, 0.7);
    color: #cbd5e1;
    display: flex;
    align-items: center;
    gap: 5px;
    transition: all 0.15s ease;
  }

  .btn-ctrl-action:hover {
    background: rgba(51, 65, 85, 0.9);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.25);
  }

  .btn-ctrl-action.grid.active {
    background: rgba(59, 130, 246, 0.25);
    border-color: #3b82f6;
    color: #93c5fd;
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
    background: rgba(15, 23, 42, 0.6);
    padding: 2px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .btn-ctrl {
    background: transparent;
    border: none;
    color: #94a3b8;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    font-weight: 600;
    transition: all 0.15s;
  }
  .btn-ctrl:hover { background: #334155; color: white; }

  .diagram-canvas-panel {
    min-height: 580px;
    height: 680px;
    flex: 1;
    overflow: hidden;
    position: relative;
    padding: 0;
    background: #090d16;
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
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #94a3b8;
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
    color: #475569;
  }

  /* Draw.io Dot Grid Simulation */
  .diagram-canvas-panel.drawio-grid {
    background-color: #0b0f19;
    background-image: 
      radial-gradient(circle, rgba(255, 255, 255, 0.12) 1px, transparent 1px),
      radial-gradient(circle, rgba(96, 165, 250, 0.08) 1.5px, transparent 1.5px);
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

  .diagram-render-area svg {
    max-width: none !important;
    height: auto;
    filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.5));
    display: block;
  }

  .diagram-loading, .diagram-empty, .diagram-error {
    color: #94a3b8; 
    font-size: 13px; 
    padding: 40px; 
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  /* ── DRAW.IO NOTATION LEGEND BAR ── */
  .drawio-legend-bar {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
    font-size: 11.5px;
    color: #94a3b8;
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
    color: #cbd5e1;
  }

  .shape-sample {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 1.5px solid #60a5fa;
    background: rgba(59, 130, 246, 0.15);
  }

  .shape-sample.pill { border-radius: 10px; border-color: #10b981; background: rgba(16, 185, 129, 0.2); }
  .shape-sample.rect { border-radius: 2px; border-color: #3b82f6; background: rgba(59, 130, 246, 0.2); }
  .shape-sample.diamond { transform: rotate(45deg); width: 10px; height: 10px; margin: 2px; border-color: #f59e0b; background: rgba(245, 158, 11, 0.2); }
  .shape-sample.cylinder { border-radius: 4px; border-color: #ec4899; background: rgba(236, 72, 153, 0.2); }
  .shape-sample.group { border: 1.5px dashed #a855f7; background: rgba(168, 85, 247, 0.1); border-radius: 3px; }

  /* ── TRACEABILITY MATRIX ── */
  .matrix-workspace {
    display: flex;
    flex-direction: column;
    gap: 14px;
    flex: 1;
  }

  .matrix-controls-panel { padding: 12px 16px; }

  .matrix-filter-row {
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }

  .search-box {
    position: relative;
    flex: 1;
    min-width: 250px;
  }

  .search-icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 12px;
    opacity: 0.6;
  }

  .matrix-search-input {
    width: 100%;
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #334155;
    color: white;
    padding: 7px 10px 7px 30px;
    border-radius: 6px;
    font-size: 13px;
    outline: none;
    box-sizing: border-box;
  }

  .filter-select-group {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: #cbd5e1;
  }

  .filter-select {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid #334155;
    color: white;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 12.5px;
    outline: none;
  }

  .btn-export-csv {
    background: rgba(16, 185, 129, 0.2);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #6ee7b7;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-export-csv:hover {
    background: rgba(16, 185, 129, 0.35);
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
  }

  .matrix-table-panel {
    padding: 0;
    overflow: hidden;
  }

  .table-container {
    overflow-x: auto;
    max-height: 600px;
  }

  .matrix-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
  }

  .matrix-table th {
    background: #1e293b;
    padding: 12px 14px;
    color: #94a3b8;
    font-weight: 600;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    position: sticky;
    top: 0;
    text-align: left;
    white-space: nowrap;
  }

  .matrix-table td {
    padding: 10px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    vertical-align: middle;
  }

  .matrix-table tr:hover { background: rgba(255, 255, 255, 0.03); }

  .code-badge {
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #93c5fd;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-weight: 700;
    font-size: 11px;
  }

  .doc-cell { display: flex; align-items: center; gap: 6px; }
  .doc-name { font-size: 12px; color: #cbd5e1; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .sitemap-pill, .usecase-pill {
    font-size: 11.5px;
    color: #e2e8f0;
  }

  .screen-link-btn {
    background: rgba(139, 92, 246, 0.15);
    border: 1px solid rgba(139, 92, 246, 0.35);
    color: #c4b5fd;
    padding: 3px 8px;
    border-radius: 5px;
    font-size: 11.5px;
    cursor: pointer;
    transition: all 0.15s;
    text-align: left;
  }
  .screen-link-btn:hover { background: rgba(139, 92, 246, 0.3); color: white; }

  .testcases-list { display: flex; flex-direction: column; gap: 2px; }
  .tc-item { font-size: 11px; color: #94a3b8; }

  .status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10.5px;
    font-weight: 700;
  }

  /* Defect & UAT Badges in Matrix */
  .defect-list { display: flex; flex-direction: column; gap: 3px; }
  .defect-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 7px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    max-width: 170px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .defect-pill.open {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #fca5a5;
  }
  .defect-pill.clean {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.25);
    color: #86efac;
    font-weight: 500;
    font-size: 10.5px;
  }

  .uat-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .uat-item-row {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 4px;
    padding: 2px 6px;
    max-width: 220px;
  }
  .uat-code-tag {
    font-size: 10.5px;
    font-weight: 700;
    color: #60a5fa;
    white-space: nowrap;
    background: rgba(59, 130, 246, 0.18);
    padding: 1px 4px;
    border-radius: 3px;
    flex-shrink: 0;
  }
  .uat-title-text {
    font-size: 11px;
    color: #e2e8f0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .uat-status-sub {
    margin-top: 2px;
  }

  .uat-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10.5px;
    font-weight: 700;
    white-space: nowrap;
  }
  .uat-pill.passed {
    background: rgba(16, 185, 129, 0.2);
    border: 1px solid rgba(16, 185, 129, 0.5);
    color: #6ee7b7;
  }
  .uat-pill.ready {
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.5);
    color: #93c5fd;
  }
  .uat-pill.pending {
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #fcd34d;
  }
  .uat-pill.failed {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.5);
    color: #fca5a5;
  }

  /* ── Figma & Image Wireframe Extension Styles ── */
  .panel-title-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .node-source-badge {
    font-size: 10px;
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
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.5);
    color: #93c5fd;
  }
  .node-source-badge.figma-sm, .node-source-badge.img-sm {
    margin-left: auto;
    font-size: 11px;
  }

  .wf-mode-tabs-header {
    display: flex;
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 3px;
    gap: 4px;
  }

  .wf-mode-tab-btn {
    background: none;
    border: none;
    color: #94a3b8;
    padding: 5px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .wf-mode-tab-btn:hover { color: #f8fafc; background: rgba(255, 255, 255, 0.05); }
  .wf-mode-tab-btn.active {
    background: #3b82f6;
    color: white;
    box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
  }

  .dot-live {
    width: 7px;
    height: 7px;
    border-radius: 50%;
  }
  .dot-live.green { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
  .dot-live.blue { background: #60a5fa; box-shadow: 0 0 6px #60a5fa; }

  .browser-right-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .browser-ext-link {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 4px;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s;
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
    background: #111827;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .figma-input-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .figma-icon-tag {
    font-size: 12px;
    font-weight: 600;
    color: #c084fc;
    white-space: nowrap;
  }

  .figma-text-input {
    flex: 1;
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
    transition: all 0.15s;
  }
  .btn-figma-action.connect { background: #7c3aed; color: white; }
  .btn-figma-action.connect:hover { background: #6d28d9; }
  .btn-figma-action.sync { background: rgba(59, 130, 246, 0.2); border: 1px solid rgba(59, 130, 246, 0.4); color: #93c5fd; }
  .btn-figma-action.sync:hover:not(:disabled) { background: rgba(59, 130, 246, 0.35); }
  .btn-figma-action.token { background: rgba(255, 255, 255, 0.08); color: #cbd5e1; }
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
    background: #3b82f6;
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
    color: #94a3b8;
  }
  .figma-watermark-icon { font-size: 48px; margin-bottom: 12px; }
  .figma-empty-guide h4 { color: #f8fafc; margin: 0 0 8px 0; }
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
    background: #111827;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 8px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .img-name-tag { font-size: 12px; color: #cbd5e1; font-weight: 500; }
  .img-btn-group { display: flex; gap: 8px; }
  .btn-img-ctrl {
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: all 0.15s;
  }
  .btn-img-ctrl.zoom { background: rgba(59, 130, 246, 0.2); color: #93c5fd; border: 1px solid rgba(59, 130, 246, 0.4); }
  .btn-img-ctrl.zoom:hover { background: rgba(59, 130, 246, 0.4); }
  .btn-img-ctrl.replace { background: rgba(255, 255, 255, 0.08); color: #f8fafc; }
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
    background: radial-gradient(circle, #1e293b 10%, #090d16 90%);
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
    border: 2px dashed rgba(59, 130, 246, 0.4);
    border-radius: 10px;
    padding: 40px 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    cursor: pointer;
    background: rgba(15, 23, 42, 0.5);
    transition: all 0.2s;
  }
  .image-upload-dropzone:hover {
    border-color: #60a5fa;
    background: rgba(59, 130, 246, 0.08);
  }
  .drop-icon { font-size: 42px; margin-bottom: 10px; }
  .image-upload-dropzone h4 { color: #f8fafc; margin: 0 0 6px 0; }
  .image-upload-dropzone p { font-size: 12px; color: #94a3b8; margin: 0 0 16px 0; }
  .btn-upload-browse {
    background: #3b82f6;
    color: white;
    border: none;
    padding: 8px 18px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
  }
  .uploading-spinner {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #60a5fa;
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
    background: #0f172a;
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
    background: #1e293b;
    padding: 12px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  .lightbox-title { font-weight: 600; color: #f8fafc; font-size: 14px; }
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
</style>
