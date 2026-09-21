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

  // Diagram zoom/pan
  let diagramContainer;
  let zoomLevel = 1;

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

    try {
      const id = `mermaid-svg-${Date.now()}`;
      diagramContainer.innerHTML = '<div class="diagram-loading"><span class="spinner-small"></span> กำลัง Render Flowchart...</div>';
      const { svg } = await mermaid.render(id, diagramCode.trim());
      diagramContainer.innerHTML = svg;
    } catch (err) {
      console.error('Mermaid render error:', err);
      diagramContainer.innerHTML = `<div class="diagram-error"><div style="font-weight: bold; margin-bottom: 6px;">❌ เกิดข้อผิดพลาดในการ Render Diagram:</div><pre style="font-size: 11px; white-space: pre-wrap; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px;">${diagramCode}</pre></div>`;
    }
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

  // Filtered Matrix
  $: uniqueDocs = flowData && flowData.traceability_matrix 
    ? ['All', ...new Set(flowData.traceability_matrix.map(m => m.doc_name).filter(Boolean))]
    : ['All'];

  $: filteredMatrix = (flowData && flowData.traceability_matrix) ? flowData.traceability_matrix.filter(item => {
    const matchQuery = !matrixSearchQuery || 
      (item.req_code && item.req_code.toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.req_title && item.req_title.toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.use_case_id && item.use_case_id.toLowerCase().includes(matrixSearchQuery.toLowerCase())) ||
      (item.screen_name && item.screen_name.toLowerCase().includes(matrixSearchQuery.toLowerCase()));
    
    const matchDoc = selectedDocFilter === 'All' || item.doc_name === selectedDocFilter;
    const matchStatus = selectedStatusFilter === 'All' || item.status === selectedStatusFilter;

    return matchQuery && matchDoc && matchStatus;
  }) : [];

  function zoomIn() { zoomLevel = Math.min(zoomLevel + 0.2, 2.5); }
  function zoomOut() { zoomLevel = Math.max(zoomLevel - 0.2, 0.4); }
  function zoomReset() { zoomLevel = 1; }

  function exportMatrixCSV() {
    if (!filteredMatrix.length) return;
    const headers = ["Req Code", "Requirement Title", "Document", "Doc Type", "Sitemap Node", "Use Case", "Screen", "Test Cases", "Status"];
    const rows = filteredMatrix.map(m => [
      `"${m.req_code || ''}"`,
      `"${(m.req_title || '').replace(/"/g, '""')}"`,
      `"${m.doc_name || ''}"`,
      `"${m.doc_type || ''}"`,
      `"${m.sitemap_node_title || ''}"`,
      `"${(m.use_case_id || '').replace(/"/g, '""')}"`,
      `"${m.screen_name || m.screen_id || ''}"`,
      `"${(Array.isArray(m.test_cases) ? m.test_cases.join('; ') : m.test_cases || '').replace(/"/g, '""')}"`,
      `"${m.status || ''}"`
    ]);

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
                <div style="font-size: 32px; margin-bottom: 8px;">🖥️</div>
                <div>เลือกเมนูทางซ้ายเพื่อแสดง UI Wireframe จำลอง</div>
              </div>
            {:else}
              <div class="mockup-viewport" transition:scale={{ duration: 150 }}>
                <!-- Mockup Browser Bar -->
                <div class="mockup-browser-bar">
                  <div class="browser-dots">
                    <span class="dot red"></span>
                    <span class="dot yellow"></span>
                    <span class="dot green"></span>
                  </div>
                  <div class="browser-url-input">
                    <span class="lock-icon">🔒</span>
                    {#if activeWireframeTab === 'figma' && currentScreenMockup.figma_url}
                      {currentScreenMockup.figma_url}
                    {:else}
                      https://{($selectedProjectStore.project_code || 'system').toLowerCase()}.app{currentScreenMockup.route || '/'}
                    {/if}
                  </div>
                  <div class="browser-right-actions">
                    <button class="btn-run-agent-screen" on:click={() => handleTestScreenWithAgent(currentScreenMockup)} title="เปิดระบบ AI Test Agent เพื่อทดสอบหน้าจอนี้">
                      🚀 ทดสอบหน้าจอนี้ด้วย AI
                    </button>
                    {#if activeWireframeTab === 'figma' && currentScreenMockup.figma_url}
                      <a href={currentScreenMockup.figma_url} target="_blank" rel="noreferrer" class="browser-ext-link" title="เปิดใน Figma">
                        ↗️ Open Figma
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

                <!-- MODE 3: AI INTERACTIVE COMPONENT WIREFRAME -->
                {:else}

                <!-- Mockup Screen Body -->
                <div class="mockup-screen-content">
                  <!-- Header -->
                  <div class="mockup-header-section">
                    <div class="mockup-header-title">
                      <h4>{currentScreenMockup.header?.title || currentScreenMockup.screen_name}</h4>
                      {#if currentScreenMockup.header?.badge}
                        <span class="mock-badge">{currentScreenMockup.header.badge}</span>
                      {/if}
                    </div>
                    <div class="mockup-header-actions">
                      {#if currentScreenMockup.header?.actions}
                        {#each currentScreenMockup.header.actions as act}
                          <span class="mock-btn-sm">{act}</span>
                        {/each}
                      {/if}
                    </div>
                  </div>

                  <!-- Description -->
                  <p class="mockup-desc">{currentScreenMockup.description}</p>

                  <!-- Dynamic Sections -->
                  <div class="mockup-sections-stack">
                    {#if currentScreenMockup.sections}
                      {#each currentScreenMockup.sections as sec}
                        <div class="mock-section-card">
                          {#if sec.section_name}
                            <div class="mock-sec-title">{sec.section_name}</div>
                          {/if}

                          {#if sec.type === 'form' || sec.fields}
                            <div class="mock-form-grid">
                              {#each (sec.fields || []) as f}
                                <div class="mock-form-item">
                                  <label class="mock-label">
                                    {f.label} {#if f.required}<span style="color: #ef4444;">*</span>{/if}
                                  </label>
                                  {#if f.type === 'checkbox'}
                                    <div class="mock-checkbox"><input type="checkbox" checked={f.default} disabled /> {f.label}</div>
                                  {:else}
                                    <div class="mock-input">{f.placeholder || f.label}</div>
                                  {/if}
                                </div>
                              {/each}
                            </div>
                          {/if}

                          {#if sec.buttons}
                            <div class="mock-btn-row">
                              {#each sec.buttons as btn}
                                <div class="mock-button {btn.variant || 'primary'}">{btn.label}</div>
                              {/each}
                            </div>
                          {/if}

                          {#if sec.type === 'table' || sec.table_headers}
                            <div class="mock-table-wrap">
                              <table class="mock-table">
                                <thead>
                                  <tr>
                                    {#each (sec.table_headers || ['ID', 'Title', 'Status', 'Actions']) as th}
                                      <th>{th}</th>
                                    {/each}
                                  </tr>
                                </thead>
                                <tbody>
                                  {#each (sec.table_rows || [['#01', 'Sample Record Item', 'Active', 'Edit | View'], ['#02', 'Secondary Process Item', 'Completed', 'Edit | View']]) as row}
                                    <tr>
                                      {#each row as cell}
                                        <td>{cell}</td>
                                      {/each}
                                    </tr>
                                  {/each}
                                </tbody>
                              </table>
                            </div>
                          {/if}
                        </div>
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
          {/if}
        </div>
      </div>

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
                <button class="btn-ctrl" on:click={zoomIn} title="ขยาย">🔍+</button>
                <button class="btn-ctrl" on:click={zoomOut} title="ย่อ">🔍-</button>
                <button class="btn-ctrl" on:click={zoomReset} title="ขนาดดั้งเดิม">100%</button>
              </div>

              <button class="btn-ctrl-action fs" on:click={() => isFullscreenDiagram = !isFullscreenDiagram} title="ขยายเต็มหน้าจอ">
                {isFullscreenDiagram ? '✕ ย่อจอ' : '⛶ เต็มจอ'}
              </button>
            </div>
          </div>

          <!-- Mermaid Canvas Box with Draw.io style Grid -->
          <div class="glass-panel diagram-canvas-panel" class:drawio-grid={showDrawioGrid && activeTab === 'flowchart'}>
            <div 
              class="diagram-render-area" 
              bind:this={diagramContainer}
              style="transform: scale({zoomLevel}); transform-origin: top center; transition: transform 0.2s ease;"
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
                    <th style="width: 10%;">Req Code</th>
                    <th style="width: 20%;">Requirement Title</th>
                    <th style="width: 15%;">Source Document</th>
                    <th style="width: 14%;">Sitemap / Menu</th>
                    <th style="width: 14%;">Use Case</th>
                    <th style="width: 13%;">Screen Mockup</th>
                    <th style="width: 14%;">Test Scenarios</th>
                    <th style="width: 8%; text-align: center;">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {#if filteredMatrix.length === 0}
                    <tr>
                      <td colspan="8" style="text-align: center; color: #94a3b8; padding: 30px;">
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

  .mockup-screen-content {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    background: radial-gradient(circle at top right, rgba(30, 58, 138, 0.15), transparent 70%), #0f172a;
  }

  .mockup-header-section {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 10px;
  }

  .mockup-header-title { display: flex; align-items: center; gap: 8px; }
  .mockup-header-title h4 { margin: 0; font-size: 1.15rem; color: #f8fafc; }
  .mock-badge { background: #3b82f6; color: white; font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 600; }

  .mock-btn-sm {
    background: rgba(255, 255, 255, 0.08);
    color: #cbd5e1;
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 500;
  }

  .mockup-desc { margin: 0; font-size: 12.5px; color: #94a3b8; line-height: 1.5; }

  .mockup-sections-stack { display: flex; flex-direction: column; gap: 14px; }

  .mock-section-card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 14px;
  }

  .mock-sec-title {
    font-size: 12px;
    font-weight: 700;
    color: #93c5fd;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .mock-form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .mock-form-item { display: flex; flex-direction: column; gap: 4px; }
  .mock-label { font-size: 11px; color: #94a3b8; font-weight: 500; }

  .mock-input {
    background: #0f172a;
    border: 1px solid #334155;
    padding: 6px 10px;
    border-radius: 5px;
    font-size: 12px;
    color: #64748b;
  }

  .mock-checkbox { font-size: 12px; color: #cbd5e1; display: flex; align-items: center; gap: 6px; }

  .mock-btn-row { display: flex; gap: 10px; margin-top: 12px; }
  .mock-button {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
  }
  .mock-button.primary { background: #3b82f6; color: white; }
  .mock-button.link { background: transparent; color: #60a5fa; text-decoration: underline; }

  .mock-table-wrap { overflow-x: auto; margin-top: 8px; }
  .mock-table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
  .mock-table th, .mock-table td { border: 1px solid rgba(255, 255, 255, 0.08); padding: 6px 10px; text-align: left; }
  .mock-table th { background: rgba(15, 23, 42, 0.8); color: #94a3b8; font-weight: 600; }

  .mockup-footbar {
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 10px;
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
    min-height: 560px;
    flex: 1;
    overflow: auto;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding: 30px;
    background: #090d16;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    position: relative;
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
    width: 100%;
    display: flex;
    justify-content: center;
  }

  .diagram-render-area svg {
    max-width: 100%;
    height: auto;
    filter: drop-shadow(0 8px 24px rgba(0, 0, 0, 0.5));
  }

  .diagram-loading, .diagram-empty { color: #94a3b8; font-size: 13px; padding: 40px; }

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
