<script>
  import { onMount } from 'svelte';
  import { toast } from './toastStore.js';

  const API = 'http://localhost:5000/api';

  // ── State ──
  let stats = null;
  let projects = [];
  let documents = [];
  let selectedProject = null;
  let selectedDoc = null;
  let docDetail = null;
  let searchQuery = '';
  let searchResults = [];
  let isSearching = false;
  let isLoadingDocs = false;
  let isLoadingDetail = false;
  let activeTab = 'browse'; // 'browse' | 'search'
  let dbError = null;

  // ── New Project Form State ──
  let showAddProject = false;
  let isAddingProject = false;
  let newProject = {
    project_code: '',
    project_name: '',
    description: '',
    status: 'Active'
  };

  // ── View Project Info State ──
  let showProjectInfo = false;
  let viewingProject = null;

  // ── Load on mount ──
  let isInitialLoading = true;
  onMount(async () => {
    isInitialLoading = true;
    await Promise.all([loadStats(), loadProjects()]);
    isInitialLoading = false;
  });

  async function loadStats() {
    try {
      const r = await fetch(`${API}/kb/stats`);
      const d = await r.json();
      if (d.success) stats = d.stats;
    } catch (e) {
      dbError = 'ไม่สามารถเชื่อมต่อ Database ได้ กรุณาตรวจสอบว่า DB กำลังทำงาน';
    }
  }

  async function loadProjects() {
    try {
      const r = await fetch(`${API}/projects`);
      const d = await r.json();
      if (d.success) projects = d.projects;
    } catch (e) { /* handled by dbError */ }
  }

  async function loadDocuments(projectId) {
    isLoadingDocs = true;
    selectedDoc = null;
    docDetail = null;
    isEditingDoc = false;
    try {
      const url = projectId
        ? `${API}/kb/documents?project_id=${projectId}`
        : `${API}/kb/documents`;
      const r = await fetch(url);
      const d = await r.json();
      if (d.success) documents = d.documents;
    } catch (e) {
      toast('โหลดเอกสารไม่สำเร็จ', 'error');
    }
    isLoadingDocs = false;
  }

  let isEditingDoc = false;
  let editingMarkdown = '';
  let isSavingDoc = false;

  async function loadDocDetail(docId) {
    isLoadingDetail = true;
    selectedDoc = docId;
    docDetail = null;
    isEditingDoc = false;
    showAddDocPanel = false;
    try {
      const r = await fetch(`${API}/kb/documents/${docId}`);
      const d = await r.json();
      if (d.success) {
        docDetail = d;
        editingMarkdown = d.document.content || '';
      }
      else toast(d.error || 'โหลดรายละเอียดไม่สำเร็จ', 'error');
    } catch (e) {
      toast('เกิดข้อผิดพลาด', 'error');
    }
    isLoadingDetail = false;
  }

  async function saveDocEdit() {
    if (!docDetail) return;
    isSavingDoc = true;
    try {
      const r = await fetch(`${API}/kb/documents/${docDetail.document.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ markdown_text: editingMarkdown })
      });
      const d = await r.json();
      if (d.success) {
        toast('อัปเดตเอกสารสำเร็จ!', 'success');
        isEditingDoc = false;
        // Reload detail to get new chunks
        await loadDocDetail(docDetail.document.id);
      } else {
        toast(d.error || 'อัปเดตไม่สำเร็จ', 'error');
      }
    } catch (e) {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isSavingDoc = false;
    }
  }

  async function doSearch() {
    if (!searchQuery.trim()) return;
    isSearching = true;
    searchResults = [];
    try {
      const pid = selectedProject ? `&project_id=${selectedProject}` : '';
      const r = await fetch(`${API}/kb/search?q=${encodeURIComponent(searchQuery)}${pid}&top_k=8`);
      const d = await r.json();
      if (d.success) searchResults = d.results;
      else toast(d.error || 'ค้นหาไม่สำเร็จ', 'error');
    } catch (e) {
      toast('เกิดข้อผิดพลาดในการค้นหา', 'error');
    }
    isSearching = false;
  }

  // --- Markdown Parser for Preview ---
  function escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function parseMarkdownToHtml(text) {
    if (!text) return "";
    const lines = text.split("\n");
    const html = [];
    let inTable = false;
    let tableHeaders = [];
    let tableRows = [];
    
    let inCodeBlock = false;
    let codeBlockContent = [];
    let codeLanguage = '';

    for (let i = 0; i < lines.length; i++) {
      const rawLine = lines[i];
      const line = rawLine.trim();

      if (line.startsWith("```")) {
        if (!inCodeBlock) {
          inCodeBlock = true;
          codeLanguage = line.substring(3).trim();
          codeBlockContent = [];
          continue;
        } else {
          inCodeBlock = false;
          html.push(`<div class="code-block" style="background:#1e1e2e; border-radius:8px; padding:12px; margin:12px 0; overflow-x:auto; border: 1px solid var(--border2);"><div style="font-size:12px; color:#a6accd; margin-bottom:8px; font-weight:600; text-transform:uppercase;">${codeLanguage || 'code'}</div><pre style="margin:0; color:#cdd6f4; font-family:monospace; font-size:13px;"><code>${escapeHtml(codeBlockContent.join("\n"))}</code></pre></div>`);
          continue;
        }
      }
      
      if (inCodeBlock) {
        codeBlockContent.push(rawLine); // keep original indent
        continue;
      }

      // ตรวจสอบว่าเป็นบรรทัดของตารางหรือไม่
      if (line.startsWith("|") && line.endsWith("|")) {
        const cells = line.split("|").map((c) => c.trim()).slice(1, -1);
        if (!inTable) {
          const nextLine = (lines[i + 1] || "").trim();
          if (nextLine.startsWith("|") && /^[|:\s-]+$/.test(nextLine) && nextLine.includes("-")) {
            inTable = true;
            tableHeaders = cells;
            i++; 
            continue;
          }
        }
        if (inTable) {
          const isRowEmpty = cells.every((c) => c === "");
          if (!isRowEmpty) {
            tableRows.push(cells);
          }
          continue;
        }
      }

      if (inTable) {
        html.push(renderHtmlTable(tableHeaders, tableRows));
        inTable = false;
        tableHeaders = [];
        tableRows = [];
      }

      if (line === "") {
        html.push("<br/>");
      } else if (line.startsWith("- ") || line.startsWith("* ")) {
        html.push(`<li style="margin-left: 20px;">${line.substring(2)}</li>`);
      } else if (/^\d+\.\s/.test(line)) {
        const match = line.match(/^(\d+)\.\s(.*)/);
        if (match) html.push(`<ol start="${match[1]}" style="margin-left: 20px; margin-bottom: 4px;"><li>${match[2]}</li></ol>`);
        else html.push(`<div>${line}</div>`);
      } else if (line.startsWith("### ")) {
        html.push(`<h3 style="margin-top:16px; margin-bottom:8px; color:var(--text); font-size:16px;">${line.substring(4)}</h3>`);
      } else if (line.startsWith("## ")) {
        html.push(`<h2 style="margin-top:20px; margin-bottom:12px; color:var(--text); font-size:18px;">${line.substring(3)}</h2>`);
      } else if (line.startsWith("# ")) {
        html.push(`<h1 style="margin-top:24px; margin-bottom:16px; color:var(--primary); font-size:22px;">${line.substring(2)}</h1>`);
      } else {
        html.push(`<div style="margin-bottom:6px;">${line}</div>`);
      }
    }

    if (inTable) html.push(renderHtmlTable(tableHeaders, tableRows));
    if (inCodeBlock) {
      // Unclosed code block
      html.push(`<div class="code-block" style="background:#1e1e2e; border-radius:8px; padding:12px; margin:12px 0; overflow-x:auto;"><pre style="margin:0; color:#cdd6f4; font-family:monospace; font-size:13px;"><code>${escapeHtml(codeBlockContent.join("\n"))}</code></pre></div>`);
    }

    return html.join("\n");
  }

  function renderHtmlTable(headers, rows) {
    const html = ['<div style="overflow-x:auto; margin: 12px 0;"><table style="width:100%; border-collapse:collapse; font-size:14px; text-align:left;">'];
    if (headers.length > 0) {
      html.push('<thead><tr style="background:var(--surface2); border-bottom:1px solid var(--border2);">');
      headers.forEach((h) => html.push(`<th style="padding:10px 12px; border-right:1px solid var(--border2);">${h}</th>`));
      html.push("</tr></thead>");
    }
    if (rows.length > 0) {
      html.push("<tbody>");
      rows.forEach((row, idx) => {
        const bg = idx % 2 === 0 ? 'background:transparent;' : 'background:rgba(255,255,255,0.02);';
        html.push(`<tr style="${bg} border-bottom:1px solid var(--border2);">`);
        row.forEach((cell) => html.push(`<td style="padding:10px 12px; border-right:1px solid var(--border2);">${cell}</td>`));
        html.push("</tr>");
      });
      html.push("</tbody>");
    }
    html.push("</table></div>");
    return html.join("");
  }
  // ---------------------------------

  // ── Add / Import Markdown Document ──
  let showAddDocPanel = false;
  let isSubmittingDoc = false;
  let addDocTab = 'edit'; // 'edit' | 'preview'
  let addDocForm = {
    filename: '',
    markdown_text: '',
    doc_category: 'Reference',
    doc_type: 'Markdown',
    is_golden_data: false
  };

  function openAddDocPanel() {
    addDocForm = { filename: '', markdown_text: '', doc_category: 'Reference', doc_type: 'Markdown', is_golden_data: false };
    addDocTab = 'edit';
    showAddDocPanel = true;
    selectedDoc = null;
    docDetail = null;
    viewingProject = null;
    activeTab = 'browse';
  }

  function handleImportMd(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!file.name.endsWith('.md')) {
      toast('กรุณาเลือกไฟล์ .md เท่านั้น', 'error');
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      addDocForm = {
        filename: file.name.replace('.md', ''),
        markdown_text: ev.target.result,
        doc_category: 'Reference',
        doc_type: 'Markdown',
        is_golden_data: false
      };
      addDocTab = 'preview'; // Show preview automatically on import
      showAddDocPanel = true;
      selectedDoc = null;
      docDetail = null;
      viewingProject = null;
      activeTab = 'browse';
    };
    reader.readAsText(file);
    e.target.value = ''; // reset input
  }

  async function submitAddDoc() {
    if (!addDocForm.filename.trim() || !addDocForm.markdown_text.trim()) {
      toast('กรุณาระบุชื่อไฟล์และเนื้อหา Markdown', 'error');
      return;
    }
    if (!selectedProject) {
      toast('กรุณาเลือกโครงการก่อน', 'error');
      return;
    }
    
    isSubmittingDoc = true;
    try {
      const payload = {
        ...addDocForm,
        project_id: selectedProject
      };
      const res = await fetch(`${API}/kb/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        toast('บันทึกและประมวลผล Chunk สำเร็จ!', 'success');
        showAddDocPanel = false;
        loadDocuments(selectedProject);
        await loadStats(); // Update global stats
      } else {
        toast(data.error || 'เกิดข้อผิดพลาดในการบันทึก', 'error');
      }
    } catch (e) {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isSubmittingDoc = false;
    }
  }

  function selectProject(p) {
    selectedProject = p ? p.id : null;
    showAddDocPanel = false;
    loadDocuments(selectedProject);
  }

  async function createProject() {
    if (!newProject.project_name.trim()) {
      toast('กรุณาระบุชื่อโครงการ', 'error');
      return;
    }
    isAddingProject = true;
    try {
      const r = await fetch(`${API}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProject)
      });
      const d = await r.json();
      console.log('Create project response:', d);
      if (d.success) {
        toast('สร้างโครงการสำเร็จ', 'success');
        showAddProject = false;
        newProject = { project_code: '', project_name: '', description: '', status: 'Active' };
        await Promise.all([loadStats(), loadProjects()]);
        selectProject(d.project);
      } else {
        console.error('Create project error:', d.error);
        toast(d.error || 'สร้างโครงการไม่สำเร็จ', 'error');
      }
    } catch (e) {
      console.error('Create project network error:', e);
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + e.message, 'error');
    }
    isAddingProject = false;
  }

  function openProjectInfo(p) {
    viewingProject = p;
    showProjectInfo = true;
  }

  let projectToDelete = null;
  let showDeleteProjConfirm = false;
  let isDeletingProject = false;

  function confirmDeleteProject(p) {
    projectToDelete = p;
    showDeleteProjConfirm = true;
  }

  async function executeDeleteProject() {
    if (!projectToDelete) return;
    isDeletingProject = true;
    try {
      const res = await fetch(`${API}/projects/${projectToDelete.id}`, { method: 'DELETE' });
      const data = await res.json();
      if (res.ok) {
        toast('ลบโครงการสำเร็จ', 'success');
        if (selectedProject === projectToDelete.id) {
          selectProject(null);
        }
        await Promise.all([loadStats(), loadProjects()]);
      } else {
        toast(data.error || 'ลบโครงการไม่สำเร็จ', 'error');
      }
    } catch (e) {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isDeletingProject = false;
    }
    showDeleteProjConfirm = false;
    projectToDelete = null;
  }

  function formatDate(val) {
    if (!val) return '—';
    return new Date(val).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' });
  }

  function similarityColor(s) {
    if (s >= 0.75) return '#4ade80';
    if (s >= 0.5)  return '#facc15';
    return '#f87171';
  }

  let docToDelete = null;
  let showDeleteDocConfirm = false;
  let isDeletingDoc = false;

  function confirmDeleteDoc(docId) {
    docToDelete = docId;
    showDeleteDocConfirm = true;
  }

  async function executeDeleteDoc() {
    if (!docToDelete) return;
    isDeletingDoc = true;
    try {
      const res = await fetch(`${API}/kb/documents/${docToDelete}`, { method: 'DELETE' });
      const data = await res.json();
      if (res.ok) {
        toast('ลบเอกสารสำเร็จ', 'success');
        if (selectedDoc === docToDelete) {
          selectedDoc = null;
          docDetail = null;
        }
        await loadProjects(); // reload docs
      } else {
        toast(data.error || 'ลบเอกสารไม่สำเร็จ', 'error');
      }
    } catch (e) {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isDeletingDoc = false;
    }
    showDeleteDocConfirm = false;
    docToDelete = null;
  }
</script>

<div class="kb-shell">
  <!-- ── Left sidebar ── -->
  <aside class="kb-sidebar">
    <!-- Stats banner -->
    {#if dbError}
      <div class="db-error">
        <span class="err-icon">⚠️</span>
        <span>{dbError}</span>
      </div>
    {:else if stats}
      <div class="stats-bar">
        <div class="stat-chip">
          <span class="stat-num">{stats.projects}</span>
          <span class="stat-lbl">โครงการ</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num">{stats.documents}</span>
          <span class="stat-lbl">เอกสาร</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num">{stats.chunks}</span>
          <span class="stat-lbl">Chunks</span>
        </div>
      </div>
    {:else}
      <div class="stats-bar loading-pulse">กำลังโหลด...</div>
    {/if}

    <!-- Tab toggle -->
    <div class="tab-bar">
      <button class="tab-btn" class:active={activeTab==='browse'} on:click={() => activeTab='browse'}>
        🗂 เรียกดู
      </button>
      <button class="tab-btn" class:active={activeTab==='search'} on:click={() => activeTab='search'}>
        🔍 ค้นหา Vector
      </button>
    </div>

    {#if activeTab === 'browse'}
      <!-- Project list -->
      <div class="section-label" style="display: flex; justify-content: space-between; align-items: center;">
        <span>โครงการ</span>
        <button class="btn-icon-add" on:click={() => showAddProject = true} title="เพิ่มโครงการใหม่">
          + เพิ่ม
        </button>
      </div>
      <div class="project-list">
        <div class="project-item" class:active={selectedProject === null}>
          <button class="project-item-content" on:click={() => selectProject(null)}>
            <span class="proj-icon">📁</span>
            <span>ทั้งหมด</span>
          </button>
        </div>
        {#each projects as p}
          <div class="project-item" class:active={selectedProject === p.id}>
            <button class="project-item-content" on:click={() => selectProject(p)}>
              <span class="proj-icon">📂</span>
              <span class="truncate">{p.name}</span>
            </button>
            <div class="project-actions">
              <button class="btn-view-proj" on:click|stopPropagation={() => openProjectInfo(p)} title="ดูรายละเอียดโครงการ">ℹ️</button>
              <button class="btn-del-proj" on:click|stopPropagation={() => confirmDeleteProject(p)} title="ลบโครงการ">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
          </div>
        {/each}
        {#if projects.length === 0 && !dbError}
          <div class="empty-hint">ยังไม่มีโครงการ</div>
        {/if}
      </div>

      <!-- Document list -->
      <div class="section-label" style="display: flex; justify-content: space-between; align-items: center; padding-right: 8px;">
        <span>เอกสาร ({documents.length})</span>
        {#if selectedProject}
          <div style="display: flex; gap: 6px;">
            <input type="file" id="import-md-input" accept=".md" style="display:none" on:change={handleImportMd} />
            <button class="btn-icon" style="font-size: 11px; padding: 4px 8px; border-radius: 4px; background: var(--surface2); color: var(--text); border: 1px solid var(--border2); cursor: pointer;" on:click={() => document.getElementById('import-md-input').click()} title="นำเข้าไฟล์ Markdown (.md)">📥 Import</button>
            <button class="btn-icon" style="font-size: 11px; padding: 4px 8px; border-radius: 4px; background: var(--primary); color: #fff; border: none; cursor: pointer;" on:click={openAddDocPanel} title="เพิ่มเอกสารใหม่">➕ Add</button>
          </div>
        {/if}
      </div>
      <div class="doc-list">
        {#if isLoadingDocs}
          <div class="loading-pulse" style="text-align: center; padding: 20px 0;">กำลังโหลด...</div>
        {:else if documents.length === 0}
          <div class="empty-hint" style="text-align: center; color: var(--text3); font-size: 13px; margin-top: 16px;">
            ไม่พบเอกสารที่เกี่ยวข้อง
          </div>
        {:else}
          {#each documents as doc}
            <div class="doc-item-wrap" class:active={selectedDoc === doc.id}>
              <button
                class="doc-item"
                on:click={() => loadDocDetail(doc.id)}
              >
                <span class="doc-icon">📄</span>
                <div class="doc-meta">
                  <span class="doc-name truncate">
                    {doc.name}
                    {#if doc.is_golden_data}
                      <span class="badge-golden" title="Golden Data">⭐</span>
                    {/if}
                  </span>
                  <span class="doc-info">
                    <span class="badge-cat">{doc.doc_category || 'General'}</span>
                    {doc.chunk_count} chunks · {formatDate(doc.created_at)}
                  </span>
                </div>
              </button>
              <button class="btn-del" title="ลบเอกสาร" on:click={() => confirmDeleteDoc(doc.id)}>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
          {/each}
        {/if}
      </div>

    {:else}
      <!-- Vector Search -->
      <div class="search-area">
        <div class="section-label">ค้นหาด้วย Semantic Search</div>
        <textarea
          class="search-input"
          placeholder="พิมพ์คำถามหรือข้อความเพื่อค้นหา..."
          bind:value={searchQuery}
          rows="3"
        ></textarea>
        <button class="btn-search" on:click={doSearch} disabled={isSearching || !searchQuery.trim()}>
          {isSearching ? '🔄 กำลังค้นหา...' : '🔍 ค้นหา'}
        </button>
      </div>
    {/if}
  </aside>

  <!-- ── Main content ── -->
  <main class="kb-main">
    {#if activeTab === 'search'}
      <!-- Search results -->
      <div class="content-header">
        <h2 class="content-title">ผลลัพธ์การค้นหา</h2>
        {#if searchResults.length > 0}
          <span class="result-badge">{searchResults.length} รายการ</span>
        {/if}
      </div>

      {#if searchResults.length === 0 && !isSearching}
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <p>พิมพ์คำค้นหาแล้วกดปุ่ม "ค้นหา" เพื่อค้นหาด้วย Vector Similarity</p>
        </div>
      {:else}
        <div class="search-results">
          {#each searchResults as r, i}
            <div class="result-card">
              <div class="result-header">
                <span class="result-rank">#{i+1}</span>
                <span class="result-doc">{r.doc_name}</span>
                <span class="result-score" style="color:{similarityColor(r.similarity)}">
                  {(r.similarity * 100).toFixed(1)}% match
                </span>
              </div>
              <div class="result-bar-wrap">
                <div class="result-bar" style="width:{(r.similarity*100).toFixed(1)}%; background:{similarityColor(r.similarity)}"></div>
              </div>
              <p class="result-text">{r.chunk_text}</p>
              <button class="btn-view-doc" on:click={() => { activeTab='browse'; loadDocDetail(r.document_id); }}>
                ดูเอกสาร →
              </button>
            </div>
          {/each}
        </div>
      {/if}

    {:else if docDetail}
      <!-- Document detail -->
      <div class="content-header">
        <button class="btn-back" on:click={() => { selectedDoc = null; docDetail = null; }}>← กลับ</button>
        <h2 class="content-title truncate">{docDetail.document.filename || docDetail.document.title || 'เอกสาร'}</h2>
      </div>

      <div class="doc-detail-wrap">
        <!-- Meta -->
        <div class="detail-meta-grid">
          <div class="meta-chip"><span class="meta-k">ชื่อเอกสาร</span><span class="meta-v">{docDetail.document.filename}</span></div>
          {#if docDetail.document.project_name}
            <div class="meta-chip"><span class="meta-k">โครงการ</span><span class="meta-v">{docDetail.document.project_name}</span></div>
          {/if}
          <div class="meta-chip"><span class="meta-k">Chunks</span><span class="meta-v">{docDetail.chunks.length}</span></div>
          {#if docDetail.document.created_at}
            <div class="meta-chip"><span class="meta-k">วันที่</span><span class="meta-v">{formatDate(docDetail.document.created_at)}</span></div>
          {/if}
        </div>

        <!-- View Mode Tabs -->
        {#if docDetail.document.content !== undefined}
          <div class="view-mode-tabs" style="display: flex; gap: 8px; margin-top: 24px; margin-bottom: 12px; border-bottom: 1px solid var(--border2); padding-bottom: 8px;">
            <button 
              class="tab-btn {isEditingDoc ? '' : 'active'}" 
              style="padding: 6px 16px; border-radius: 6px; border: none; background: {!isEditingDoc ? 'var(--primary)' : 'transparent'}; color: {!isEditingDoc ? '#fff' : 'var(--text2)'}; cursor: pointer; font-size: 14px; transition: all 0.2s;"
              on:click={() => isEditingDoc = false}
            >
              👁️ พรีวิว (Preview)
            </button>
            <button 
              class="tab-btn {isEditingDoc ? 'active' : ''}" 
              style="padding: 6px 16px; border-radius: 6px; border: none; background: {isEditingDoc ? 'var(--primary)' : 'transparent'}; color: {isEditingDoc ? '#fff' : 'var(--text2)'}; cursor: pointer; font-size: 14px; transition: all 0.2s;"
              on:click={() => { isEditingDoc = true; editingMarkdown = docDetail.document.content; }}
            >
              ✎ แก้ไขเนื้อหา (Markdown)
            </button>
          </div>

          {#if !isEditingDoc}
            <!-- Preview Mode -->
            {#if docDetail.document.total_pages && docDetail.document.total_pages > 0}
              <div style="display: flex; gap: 20px; align-items: flex-start; margin-bottom: 24px;">
                <!-- Original Images Panel -->
                <div style="flex: 1; background: var(--surface2); padding: 16px; border-radius: 8px; border: 1px solid var(--border2); max-height: 800px; overflow-y: auto;">
                  <h4 style="margin-top: 0; margin-bottom: 12px; color: var(--text2); font-size: 14px; font-weight: 500;">ไฟล์ต้นฉบับ ({docDetail.document.total_pages} หน้า)</h4>
                  <div style="display: flex; flex-direction: column; gap: 16px;">
                    {#each Array(docDetail.document.total_pages) as _, i}
                      <div style="position: relative; background: #fff; padding: 4px; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                        <div style="position: absolute; top: 8px; left: 8px; background: rgba(0,0,0,0.6); color: #fff; font-size: 11px; padding: 2px 6px; border-radius: 4px; backdrop-filter: blur(4px);">หน้า {i + 1}</div>
                        <img 
                          src={`http://localhost:5000/api/kb/view/${docDetail.document.id}/${i + 1}`} 
                          alt={`หน้า ${i + 1}`} 
                          style="width: 100%; border-radius: 4px; display: block;"
                        />
                      </div>
                    {/each}
                  </div>
                </div>
                
                <!-- Markdown Rendered Panel -->
                <div class="rendered-html" style="flex: 1; background: var(--bg3); border: 1px solid var(--border2); color: var(--text); padding: 24px; border-radius: 8px; line-height: 1.6; font-size: 15px; max-height: 800px; overflow-y: auto;">
                  {@html parseMarkdownToHtml(docDetail.document.content)}
                </div>
              </div>
            {:else}
              <div class="rendered-html" style="background: var(--bg3); border: 1px solid var(--border2); color: var(--text); padding: 24px; border-radius: 8px; line-height: 1.6; font-size: 15px;">
                {@html parseMarkdownToHtml(docDetail.document.content)}
              </div>
            {/if}
          {:else}
            <!-- Edit Mode -->
            <div style="margin-bottom: 12px; display: flex; justify-content: flex-end; gap: 8px;">
              <button class="btn-sm" style="background: transparent; border: 1px solid var(--border2); color: var(--text2); padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px;" on:click={() => { isEditingDoc = false; editingMarkdown = docDetail.document.content; }} disabled={isSavingDoc}>
                ยกเลิก
              </button>
              <button class="btn-sm" style="background: var(--primary); border: none; color: #fff; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500;" on:click={saveDocEdit} disabled={isSavingDoc}>
                {isSavingDoc ? 'กำลังบันทึก...' : '💾 บันทึก & อัปเดต Chunk'}
              </button>
            </div>
            <textarea class="markdown-editor" bind:value={editingMarkdown} disabled={isSavingDoc} style="width: 100%; min-height: 500px; background: #1e1e2e; border: 1px solid var(--primary); color: #cdd6f4; padding: 16px; border-radius: 8px; font-family: monospace; font-size: 14px; resize: vertical; line-height: 1.6; outline: none; box-shadow: 0 0 0 2px rgba(108,142,251,0.2);"></textarea>
          {/if}
        {/if}

        <!-- Chunks -->
        <div class="section-label" style="margin-top:20px">Chunks ({docDetail.chunks.length})</div>
        <div class="chunks-list">
          {#each docDetail.chunks as chunk, idx}
            <div class="chunk-card">
              <div class="chunk-head">Chunk #{idx+1} <span class="chunk-id">(id: {chunk.id})</span></div>
              <p class="chunk-text">{chunk.text}</p>
            </div>
          {/each}
        </div>
      </div>

    {:else if isLoadingDetail}
      <div class="empty-state"><div class="loading-spin"></div><p>กำลังโหลด...</p></div>

    {:else if showAddDocPanel}
      <!-- Add / Import Document Panel (Redesigned like Add Skill) -->
      <div style="display: flex; flex-direction: column; height: 100%; width: 100%;">
        <header class="editor-header" style="padding: 16px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: var(--bg2); flex-shrink: 0;">
          <div class="header-info" style="display: flex; align-items: center; gap: 16px;">
            <button class="btn-back" style="background:transparent; border:none; color:var(--text2); font-size: 20px; cursor: pointer; padding: 4px;" on:click={() => showAddDocPanel = false} title="กลับ">←</button>
            <div>
              <h2 style="margin: 0; font-size: 18px; color: var(--primary);">➕ เพิ่มเอกสาร (Manual / Markdown)</h2>
              <span style="font-size: 12px; color: var(--text3);">ระบบจะบันทึกและแปลงเป็น Vector Chunks ให้อัตโนมัติ</span>
            </div>
          </div>
          <div class="header-actions">
            <button class="btn-submit" style="display: flex; gap: 8px; align-items: center; padding: 8px 16px; font-size: 14px; border-radius: 6px; font-weight: 600; background: var(--primary); color: #fff; border: none; cursor: pointer; transition: 0.2s;" on:click={submitAddDoc} disabled={isSubmittingDoc || !addDocForm.filename.trim() || !addDocForm.markdown_text.trim()}>
              {#if isSubmittingDoc}
                <div class="spinner" style="width: 14px; height: 14px; border-width: 2px;"></div> กำลังบันทึก...
              {:else}
                💾 บันทึกเอกสาร
              {/if}
            </button>
          </div>
        </header>

        <div class="meta-grid" style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 20px; padding: 20px 24px; background: var(--bg2); border-bottom: 1px solid var(--border); flex-shrink: 0;">
          <div class="form-group" style="display: flex; flex-direction: column; gap: 8px; margin: 0;">
            <label for="md_filename" style="font-size: 12px; color: var(--text2);">ชื่อเอกสาร (Filename) <span style="color:var(--danger)">*</span></label>
            <input id="md_filename" type="text" style="background: var(--bg3); border: 1px solid var(--border2); padding: 10px 12px; border-radius: 6px; font-size: 14px; color: var(--text); outline: none;" placeholder="เช่น API_Documentation..." bind:value={addDocForm.filename} />
          </div>
          
          <div class="form-group" style="display: flex; flex-direction: column; gap: 8px; margin: 0;">
            <label for="md_category" style="font-size: 12px; color: var(--text2);">หมวดหมู่ (Category)</label>
            <select id="md_category" style="background: var(--bg3); border: 1px solid var(--border2); padding: 10px 12px; border-radius: 6px; font-size: 14px; color: var(--text); outline: none;" bind:value={addDocForm.doc_category}>
              <option value="Reference">Reference</option>
              <option value="Requirements">Requirements</option>
              <option value="TestCase">TestCase</option>
              <option value="Other">Other</option>
            </select>
          </div>
          
          <div class="form-group checkbox-group" style="display: flex; align-items: center; padding-top: 24px; margin: 0;">
            <label class="toggle-wrap" style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 8px 12px; border-radius: 6px; background: rgba(255, 215, 0, 0.05); border: 1px solid rgba(255, 215, 0, 0.1);">
              <input type="checkbox" bind:checked={addDocForm.is_golden_data} style="width: 18px; height: 18px; accent-color: #fbbf24; cursor: pointer;" />
              <span class="label-text" style="font-weight: 600; color: #fbbf24; font-size: 14px; line-height: 1;">⭐ Golden Data</span>
            </label>
          </div>
        </div>

        <div class="editor-container" style="flex: 1; display: flex; flex-direction: column; padding: 20px 24px; overflow: hidden; background: var(--bg);">
          <div class="view-mode-tabs" style="display: flex; gap: 8px; margin-bottom: 12px; border-bottom: 1px solid var(--border2); padding-bottom: 8px;">
            <button 
              class="tab-btn {addDocTab === 'edit' ? 'active' : ''}" 
              style="padding: 6px 16px; border-radius: 6px; border: none; background: {addDocTab === 'edit' ? 'var(--primary)' : 'transparent'}; color: {addDocTab === 'edit' ? '#fff' : 'var(--text2)'}; cursor: pointer; font-size: 14px; transition: all 0.2s;"
              on:click={() => addDocTab = 'edit'}
            >
              ✎ แก้ไขเนื้อหา (Markdown)
            </button>
            <button 
              class="tab-btn {addDocTab === 'preview' ? 'active' : ''}" 
              style="padding: 6px 16px; border-radius: 6px; border: none; background: {addDocTab === 'preview' ? 'var(--primary)' : 'transparent'}; color: {addDocTab === 'preview' ? '#fff' : 'var(--text2)'}; cursor: pointer; font-size: 14px; transition: all 0.2s;"
              on:click={() => addDocTab = 'preview'}
            >
              👁️ พรีวิวข้อมูล
            </button>
          </div>
          
          {#if addDocTab === 'edit'}
            <textarea id="md_content" style="flex: 1; background: #0d1117; border: 1px solid var(--border); color: #c9d1d9; font-family: 'Consolas', 'Courier New', monospace; font-size: 14px; padding: 16px; border-radius: 8px; resize: none; outline: none; box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);" placeholder="พิมพ์เนื้อหา Markdown หรือ Import ข้อมูลที่นี่..." bind:value={addDocForm.markdown_text}></textarea>
          {:else}
            <div class="rendered-html" style="flex: 1; background: var(--bg3); border: 1px solid var(--border2); color: var(--text); padding: 24px; border-radius: 8px; line-height: 1.6; font-size: 15px; overflow-y: auto;">
              {@html addDocForm.markdown_text ? parseMarkdownToHtml(addDocForm.markdown_text) : '<span style="color:var(--text3);">ไม่มีเนื้อหา</span>'}
            </div>
          {/if}
        </div>
      </div>

    {:else}
      <!-- Welcome state -->
      <div class="empty-state">
        <div class="empty-icon">🗄️</div>
        <h3>Knowledge Base Explorer</h3>
        <p>เลือกโครงการ → คลิกเอกสาร เพื่อดูข้อมูล<br/>หรือใช้แท็บ "ค้นหา Vector" เพื่อ Semantic Search</p>
        {#if stats}
          <div class="welcome-stats">
            <span>📁 {stats.projects} โครงการ</span>
            <span>📄 {stats.documents} เอกสาร</span>
            <span>🧩 {stats.chunks} chunks</span>
          </div>
        {/if}
      </div>
    {/if}
  </main>

  <!-- ── Add Project Modal ── -->
  {#if showAddProject}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => showAddProject = false} on:keydown={(e) => e.key === 'Escape' && (showAddProject = false)} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content" on:click|stopPropagation on:keydown|stopPropagation role="dialog" aria-modal="true" aria-label="เพิ่มโครงการใหม่">
        <div class="modal-header">
          <h3>เพิ่มโครงการใหม่</h3>
          <button class="btn-close" on:click={() => showAddProject = false}>✕</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="p_code">รหัสโครงการ (Project Code)</label>
            <input id="p_code" type="text" class="form-input" placeholder="เช่น PRJ-2024-001 (เว้นว่างไว้เพื่อสร้างอัตโนมัติ)" bind:value={newProject.project_code} />
          </div>
          <div class="form-group">
            <label for="p_name">ชื่อโครงการ (Project Name) <span class="req">*</span></label>
            <input id="p_name" type="text" class="form-input" placeholder="ระบุชื่อโครงการ..." bind:value={newProject.project_name} />
          </div>
          <div class="form-group">
            <label for="p_desc">รายละเอียด (Description)</label>
            <textarea id="p_desc" class="form-input" rows="3" placeholder="คำอธิบายโครงการ..." bind:value={newProject.description}></textarea>
          </div>
          <div class="form-group">
            <label for="p_status">สถานะ (Status)</label>
            <select id="p_status" class="form-input" bind:value={newProject.status}>
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" on:click={() => showAddProject = false}>ยกเลิก</button>
          <button class="btn-submit" on:click={createProject} disabled={isAddingProject || !newProject.project_name.trim()}>
            {isAddingProject ? 'กำลังสร้าง...' : 'สร้างโครงการ'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── View Project Modal ── -->
  {#if showProjectInfo && viewingProject}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => showProjectInfo = false} on:keydown={(e) => e.key === 'Escape' && (showProjectInfo = false)} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content" on:click|stopPropagation on:keydown|stopPropagation role="dialog" aria-modal="true" aria-label="รายละเอียดโครงการ">
        <div class="modal-header">
          <h3>รายละเอียดโครงการ</h3>
          <button class="btn-close" on:click={() => showProjectInfo = false}>✕</button>
        </div>
        <div class="modal-body">
          <div class="info-group">
            <span class="info-label">รหัสโครงการ (Project Code)</span>
            <span class="info-value">{viewingProject.project_code || '-'}</span>
          </div>
          <div class="info-group">
            <span class="info-label">ชื่อโครงการ (Project Name)</span>
            <span class="info-value">{viewingProject.name || '-'}</span>
          </div>
          <div class="info-group">
            <span class="info-label">สถานะ (Status)</span>
            <span class="info-value" class:status-active={viewingProject.status === 'Active'} class:status-inactive={viewingProject.status !== 'Active'}>
              {viewingProject.status || 'Active'}
            </span>
          </div>
          <div class="info-group">
            <span class="info-label">รายละเอียด (Description)</span>
            <div class="info-desc">{viewingProject.description || 'ไม่มีรายละเอียด'}</div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" on:click={() => showProjectInfo = false}>ปิดหน้าต่าง</button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Delete Project Confirm Modal ── -->
  {#if showDeleteProjConfirm && projectToDelete}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => showDeleteProjConfirm = false} on:keydown={(e) => e.key === 'Escape' && (showDeleteProjConfirm = false)} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content modal-sm" on:click|stopPropagation on:keydown|stopPropagation role="dialog" aria-modal="true" aria-label="ยืนยันการลบโครงการ">
        <div class="modal-header">
          <h3 class="danger-text" style="display: flex; align-items: center; gap: 8px;">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
            ยืนยันการลบโครงการ
          </h3>
          <button class="btn-close" on:click={() => showDeleteProjConfirm = false}>✕</button>
        </div>
        <div class="modal-body">
          <p style="margin: 0; font-size: 14px; color: var(--text);">
            คุณต้องการลบโครงการ <strong style="color: var(--primary);">"{projectToDelete.name}"</strong> ใช่หรือไม่?
          </p>
          <p style="margin: 0; font-size: 13px; color: #f87171; background: rgba(239,68,68,0.1); padding: 10px; border-radius: 6px; border: 1px solid rgba(239,68,68,0.2);">
            ข้อมูลเอกสารและ Chunks ทั้งหมดในโครงการนี้จะถูกลบทิ้งอย่างถาวร และไม่สามารถกู้คืนได้
          </p>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" on:click={() => showDeleteProjConfirm = false} disabled={isDeletingProject}>ยกเลิก</button>
          <button class="btn-submit danger-bg" on:click={executeDeleteProject} disabled={isDeletingProject}>
            {#if isDeletingProject}
              <div class="loading-spin" style="width: 14px; height: 14px; margin-right: 6px; border-color: rgba(255,255,255,0.3); border-top-color: #fff; display: inline-block; vertical-align: middle;"></div> กำลังลบ...
            {:else}
              ลบโครงการถาวร
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Delete Document Confirm Modal ── -->
  {#if showDeleteDocConfirm && docToDelete}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => showDeleteDocConfirm = false} on:keydown={(e) => e.key === 'Escape' && (showDeleteDocConfirm = false)} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content modal-sm" on:click|stopPropagation on:keydown|stopPropagation role="dialog" aria-modal="true" aria-label="ยืนยันการลบเอกสาร">
        <div class="modal-header">
          <h3 class="danger-text" style="display: flex; align-items: center; gap: 8px;">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
            ยืนยันการลบเอกสาร
          </h3>
          <button class="btn-close" on:click={() => showDeleteDocConfirm = false}>✕</button>
        </div>
        <div class="modal-body">
          <p style="margin: 0; font-size: 14px; color: var(--text);">
            คุณต้องการลบเอกสารนี้ใช่หรือไม่?
          </p>
          <p style="margin: 0; font-size: 13px; color: #f87171; background: rgba(239,68,68,0.1); padding: 10px; border-radius: 6px; border: 1px solid rgba(239,68,68,0.2);">
            ข้อมูลเอกสารนี้จะถูกลบทิ้งอย่างถาวร และไม่สามารถกู้คืนได้
          </p>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" on:click={() => showDeleteDocConfirm = false} disabled={isDeletingDoc}>ยกเลิก</button>
          <button class="btn-submit danger-bg" on:click={executeDeleteDoc} disabled={isDeletingDoc}>
            {#if isDeletingDoc}
              <div class="loading-spin" style="width: 14px; height: 14px; margin-right: 6px; border-color: rgba(255,255,255,0.3); border-top-color: #fff; display: inline-block; vertical-align: middle;"></div> กำลังลบ...
            {:else}
              ลบเอกสารถาวร
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Initial Loading Modal ── -->
  {#if isInitialLoading}
    <div class="modal-backdrop" style="z-index: 9999; display: flex; flex-direction: column; gap: 16px;">
      <div class="loading-spin" style="width: 40px; height: 40px; border-width: 4px; border-color: rgba(108,142,251,0.2); border-top-color: var(--primary);"></div>
      <div style="color: var(--text); font-size: 16px; font-weight: 500;">กำลังโหลดข้อมูล Knowledge Base...</div>
    </div>
  {/if}

</div>

<style>
.kb-shell {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: var(--bg);
}

/* ── Sidebar ── */
.kb-sidebar {
  width: 300px;
  flex-shrink: 0;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.stats-bar {
  display: flex;
  gap: 8px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.stat-chip {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 8px 6px;
  text-align: center;
}
.stat-num { display: block; font-size: 18px; font-weight: 700; color: var(--primary); }
.stat-lbl { font-size: 10px; color: var(--text3); }

.db-error {
  margin: 12px;
  padding: 10px 12px;
  background: rgba(248,113,113,0.1);
  border: 1px solid rgba(248,113,113,0.25);
  border-radius: 8px;
  font-size: 12px;
  color: var(--danger, #f87171);
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.err-icon { flex-shrink: 0; }

.tab-bar {
  display: flex;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.tab-btn {
  flex: 1;
  padding: 7px 4px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text3);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: var(--font-th, inherit);
}
.tab-btn.active {
  background: rgba(108,142,251,0.15);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  color: var(--text3);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 10px 14px 4px;
}

.project-list, .doc-list {
  overflow-y: auto;
  flex-shrink: 0;
}
.project-list { max-height: 200px; }
.doc-list { flex: 1; overflow-y: auto; }

.project-item {
  width: 100%;
  display: flex;
  align-items: center;
  background: transparent;
  border-left: 3px solid transparent;
  text-align: left;
  font-family: var(--font-th, inherit);
  font-size: 13px;
  color: var(--text2);
  transition: all 0.15s;
  padding: 0 8px 0 0;
}
.project-item-content {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  cursor: pointer;
  min-width: 0;
  background: transparent;
  border: none;
  color: inherit;
  font: inherit;
  text-align: left;
}
.doc-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  background: transparent;
  border: none;
  border-left: 3px solid transparent;
  cursor: pointer;
  text-align: left;
  font-family: var(--font-th, inherit);
  font-size: 13px;
  color: var(--text2);
  transition: all 0.15s;
}
.project-item:hover, .doc-item:hover {
  background: rgba(108,142,251,0.06);
  color: var(--text);
}
.project-item.active, .doc-item.active {
  background: rgba(108,142,251,0.12);
  border-left-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}
.proj-icon, .doc-icon { flex-shrink: 0; font-size: 14px; }
.project-actions {
  display: flex;
  align-items: center;
  opacity: 0;
  transition: opacity 0.2s;
  padding-right: 4px;
}
.project-item:hover .project-actions {
  opacity: 1;
}
.btn-view-proj, .btn-del-proj {
  background: transparent;
  border: none;
  color: var(--text3);
  cursor: pointer;
  padding: 6px;
  border-radius: 4px;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.btn-view-proj:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text);
}
.btn-del-proj:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.doc-meta { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.doc-name { font-size: 12px; font-weight: 600; display: block; }
.doc-info { font-size: 10px; color: var(--text3); }

.empty-hint { padding: 10px 14px; font-size: 12px; color: var(--text3); }

/* Search area */
.search-area { padding: 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
.search-input {
  width: 100%;
  background: var(--bg3, #1a1a2e);
  border: 1px solid var(--border2);
  border-radius: 8px;
  padding: 10px;
  color: var(--text);
  font-family: var(--font-th, inherit);
  font-size: 13px;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.search-input:focus { border-color: var(--primary); }
.btn-search {
  width: 100%;
  padding: 10px;
  background: linear-gradient(135deg, var(--primary), var(--accent));
  border: none;
  border-radius: 8px;
  color: #fff;
  font-family: var(--font-th, inherit);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-search:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Main ── */
.kb-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.content-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--bg2);
}
.content-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
  margin: 0;
  flex: 1;
  min-width: 0;
}
.result-badge {
  background: rgba(108,142,251,0.18);
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
}
.btn-back {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text2);
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-th, inherit);
  transition: all 0.15s;
}
.btn-back:hover { border-color: var(--primary); color: var(--primary); }

/* Empty / Loading */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text3);
  text-align: center;
  padding: 40px;
}
.empty-icon { font-size: 56px; opacity: 0.5; }
.empty-state h3 { font-size: 18px; color: var(--text2); margin: 0; }
.empty-state p { font-size: 14px; line-height: 1.6; max-width: 360px; }
.welcome-stats {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 13px;
  color: var(--primary);
  font-weight: 600;
}
.loading-pulse { animation: pulse 1.5s ease infinite; color: var(--text3); font-size: 13px; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
.loading-spin {
  width: 36px; height: 36px;
  border: 3px solid var(--border);
  border-top-color: var(--primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Search results */
.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.result-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px 16px;
  transition: border-color 0.2s;
}
.result-card:hover { border-color: rgba(108,142,251,0.4); }
.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.result-rank {
  background: rgba(108,142,251,0.18);
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
}
.result-doc { flex: 1; font-size: 13px; font-weight: 600; color: var(--text2); }
.result-score { font-size: 12px; font-weight: 700; }
.result-bar-wrap { height: 4px; background: var(--bg3, #1a1a2e); border-radius: 2px; margin-bottom: 8px; }
.result-bar { height: 100%; border-radius: 2px; transition: width 0.5s; }
.result-text {
  font-size: 13px;
  color: var(--text2);
  line-height: 1.6;
  white-space: pre-wrap;
  margin: 0 0 10px;
  max-height: 120px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}
.btn-view-doc {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--primary);
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-view-doc:hover { background: rgba(108,142,251,0.1); }

/* Doc detail */
.doc-detail-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.detail-meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.meta-chip {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 6px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.meta-k { font-size: 10px; color: var(--text3); font-weight: 600; text-transform: uppercase; }
.meta-v { font-size: 13px; color: var(--text); font-weight: 700; }

.markdown-content {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  font-size: 13px;
  color: var(--text2);
  line-height: 1.7;
  white-space: pre-wrap;
  font-family: monospace;
  max-height: 280px;
  overflow-y: auto;
}

.chunks-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 20px;
}
.chunk-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 14px;
}
.chunk-head {
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: 6px;
}
.chunk-id { color: var(--text3); font-weight: 400; }
.chunk-text {
  font-size: 12px;
  color: var(--text2);
  line-height: 1.6;
  white-space: pre-wrap;
  margin: 0;
}

.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Add Project Modal & Button */
.btn-icon-add {
  background: rgba(108,142,251,0.1);
  color: var(--primary);
  border: 1px solid rgba(108,142,251,0.3);
  border-radius: 4px;
  font-size: 10px;
  padding: 2px 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 600;
  font-family: var(--font-th, inherit);
}
.btn-icon-add:hover {
  background: var(--primary);
  color: #fff;
}

.modal-backdrop {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 90%;
  max-width: 450px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 30px rgba(0,0,0,0.3);
  font-family: var(--font-th, inherit);
}

.modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.modal-header h3 { margin: 0; font-size: 16px; color: var(--text); }
.btn-close { background: transparent; border: none; color: var(--text3); cursor: pointer; font-size: 16px; padding: 4px; border-radius: 4px; }
.btn-close:hover { background: var(--surface); color: var(--text); }

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 13px; font-weight: 600; color: var(--text2); }
.form-group .req { color: var(--danger, #f87171); }

.form-input {
  background: var(--bg3, #1a1a2e);
  border: 1px solid var(--border2);
  border-radius: 8px;
  padding: 10px;
  color: var(--text);
  font-family: var(--font-th, inherit);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.form-input:focus { border-color: var(--primary); }
textarea.form-input { resize: vertical; }

.modal-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  background: var(--bg2);
  border-radius: 0 0 12px 12px;
}

.btn-cancel {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text2);
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-th, inherit);
  transition: all 0.2s;
}
.btn-cancel:hover { background: var(--surface); color: var(--text); }

.btn-submit {
  background: linear-gradient(135deg, var(--primary), var(--accent));
  border: none;
  color: #fff;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-th, inherit);
  transition: all 0.2s;
}
.btn-submit:hover { opacity: 0.9; transform: translateY(-1px); }

.danger-bg {
  background: linear-gradient(135deg, #ef4444, #dc2626);
}
.danger-text {
  color: #ef4444 !important;
}
.modal-sm {
  max-width: 380px;
}
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

/* Info Group styles for viewing project */
.info-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 4px;
}
.info-label {
  font-size: 11px;
  color: var(--text3);
  font-weight: 600;
  text-transform: uppercase;
}
.info-value {
  font-size: 14px;
  color: var(--text);
  font-weight: 500;
}
.info-desc {
  font-size: 13px;
  color: var(--text2);
  line-height: 1.6;
  white-space: pre-wrap;
  background: var(--bg3, #1a1a2e);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--border2);
  margin-top: 4px;
}
.status-active { color: #4ade80; font-weight: 600; }
.status-inactive { color: #f87171; font-weight: 600; }

.badge-cat {
  background: rgba(108, 142, 251, 0.15);
  color: var(--primary2);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  margin-right: 6px;
  border: 1px solid rgba(108, 142, 251, 0.3);
}

.doc-item-wrap {
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--border2);
}
.doc-item-wrap.active {
  background: var(--bg3);
}
.doc-item-wrap:hover .btn-del {
  opacity: 1;
}
.doc-item-wrap .doc-item {
  flex: 1;
  border-bottom: none;
}
.btn-del {
  background: transparent;
  border: none;
  color: var(--text3);
  padding: 8px;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
  border-radius: 6px;
}
.btn-del:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}
.badge-golden {
  font-size: 12px;
  margin-left: 4px;
  filter: drop-shadow(0 0 4px rgba(250, 204, 21, 0.5));
}
</style>
