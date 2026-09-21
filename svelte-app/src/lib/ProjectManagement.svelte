<script>
  import { onMount } from 'svelte';
  import { toast } from './toastStore.js';
  import CustomSelect from './CustomSelect.svelte';

  const projectStatusOptions = [
    { value: 'Active', label: 'Active', icon: '🟢' },
    { value: 'Inactive', label: 'Inactive', icon: '🔴' }
  ];

  const API = '/api';

  let projects = [];
  let documents = [];
  let selectedProject = null;
  let selectedDoc = null;
  let docDetail = null;
  
  let expandedProjectId = null;
  let expandedDocs = [];
  let isExpanding = false;
  
  let isLoadingDocs = false;
  let isLoadingDetail = false;
  let dbError = null;

  // Form State
  let showAddProject = false;
  let isAddingProject = false;
  let isEditMode = false;
  let editingProjectId = null;
  let newProject = {
    project_code: '',
    project_name: '',
    description: '',
    status: 'Active'
  };

  // Delete State
  let projectToDelete = null;
  let showDeleteProjConfirm = false;
  let isDeletingProject = false;

  onMount(async () => {
    await loadProjects();
  });

  async function loadProjects() {
    try {
      const r = await fetch(`${API}/projects`);
      const d = await r.json();
      if (d.success) {
          projects = d.projects;
          dbError = null;
      }
    } catch (e) {
        dbError = 'ไม่สามารถเชื่อมต่อ Database ได้';
    }
  }

  async function loadDocuments(projectId) {
    isLoadingDocs = true;
    selectedDoc = null;
    docDetail = null;
    try {
      const url = `${API}/kb/documents?project_id=${projectId}`;
      const r = await fetch(url);
      const d = await r.json();
      if (d.success) documents = d.documents;
    } catch (e) {
      toast('โหลดเอกสารไม่สำเร็จ', 'error');
    }
    isLoadingDocs = false;
  }

  async function loadDocDetail(docId) {
    isLoadingDetail = true;
    selectedDoc = docId;
    docDetail = null;
    try {
      const r = await fetch(`${API}/kb/documents/${docId}`);
      const d = await r.json();
      if (d.success) {
        docDetail = d;
      }
      else toast(d.error || 'โหลดรายละเอียดไม่สำเร็จ', 'error');
    } catch (e) {
      toast('เกิดข้อผิดพลาด', 'error');
    }
    isLoadingDetail = false;
  }

  function selectProject(p) {
    selectedProject = p.id;
    selectedDoc = null;
    docDetail = null;
    loadDocuments(p.id);
  }

  async function toggleExpand(p, event) {
    event.stopPropagation();
    if (expandedProjectId === p.id) {
      expandedProjectId = null;
    } else {
      expandedProjectId = p.id;
      isExpanding = true;
      try {
        const r = await fetch(`${API}/kb/documents?project_id=${p.id}`);
        const d = await r.json();
        if (d.success) {
            expandedDocs = d.documents;
        } else {
            expandedDocs = [];
        }
      } catch (e) {
          expandedDocs = [];
      }
      isExpanding = false;
    }
  }

  function selectSubDoc(doc, p, event) {
    event.stopPropagation();
    selectedProject = p.id;
    documents = expandedDocs;
    loadDocDetail(doc.id);
  }

  function openAddProject() {
    isEditMode = false;
    editingProjectId = null;
    newProject = { 
      project_code: '', 
      project_name: '', 
      description: '', 
      status: 'Active', 
      site_urls: [
        { env_type: 'TEST', url: 'http://localhost:5173', is_default: true },
        { env_type: 'UAT', url: '', is_default: false },
        { env_type: 'PRD', url: '', is_default: false }
      ],
      default_base_url: 'http://localhost:5173' 
    };
    showAddProject = true;
  }

  function openEditProject(p) {
    isEditMode = true;
    editingProjectId = p.id;
    let sites = (p.site_urls && Array.isArray(p.site_urls) && p.site_urls.length > 0)
      ? JSON.parse(JSON.stringify(p.site_urls))
      : [
          { env_type: 'TEST', url: p.default_base_url || 'http://localhost:5173', is_default: true },
          { env_type: 'UAT', url: '', is_default: false },
          { env_type: 'PRD', url: '', is_default: false }
        ];

    // Ensure at least one is default
    if (!sites.some(s => s.is_default)) {
      sites[0].is_default = true;
    }

    newProject = {
      project_code: p.project_code || '',
      project_name: p.name || p.project_name || '',
      description: p.description || '',
      status: p.status || 'Active',
      site_urls: sites,
      default_base_url: p.default_base_url || 'http://localhost:5173'
    };
    showAddProject = true;
  }

  function setDefaultSite(index) {
    if (!newProject.site_urls || !newProject.site_urls[index]) return;
    newProject.site_urls = newProject.site_urls.map((s, i) => ({
      ...s,
      is_default: (i === index)
    }));
    if (newProject.site_urls[index].url) {
      newProject.default_base_url = newProject.site_urls[index].url;
    }
  }

  function addSiteUrlRow() {
    newProject.site_urls = [
      ...(newProject.site_urls || []),
      { env_type: 'CUSTOM', url: '', is_default: (newProject.site_urls || []).length === 0 }
    ];
  }

  function removeSiteUrlRow(index) {
    if (!newProject.site_urls || newProject.site_urls.length <= 1) {
      toast('ต้องมี Site URL อย่างน้อย 1 รายการ', 'warning');
      return;
    }
    const wasDefault = newProject.site_urls[index]?.is_default;
    newProject.site_urls = newProject.site_urls.filter((_, i) => i !== index);
    if (wasDefault && newProject.site_urls.length > 0) {
      newProject.site_urls[0].is_default = true;
      newProject.default_base_url = newProject.site_urls[0].url || 'http://localhost:5173';
    }
  }

  async function createProject() {
    if (!newProject.project_name.trim()) {
      toast('กรุณาระบุชื่อโครงการ', 'error');
      return;
    }

    // Determine default URL from site_urls
    if (newProject.site_urls && newProject.site_urls.length > 0) {
      const defSite = newProject.site_urls.find(s => s.is_default) || newProject.site_urls[0];
      newProject.default_base_url = defSite.url || 'http://localhost:5173';
    }

    isAddingProject = true;
    try {
      const endpoint = isEditMode ? `${API}/projects/${editingProjectId}` : `${API}/projects`;
      const method = isEditMode ? 'PUT' : 'POST';
      
      const r = await fetch(endpoint, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProject)
      });
      const d = await r.json();
      if (d.success) {
        toast(isEditMode ? 'อัปเดตโครงการสำเร็จ' : 'สร้างโครงการสำเร็จ', 'success');
        showAddProject = false;
        await loadProjects();
        if (selectedProject === editingProjectId) {
            // refresh docs if selected
            loadDocuments(selectedProject);
        }
      } else {
        toast(d.error || (isEditMode ? 'อัปเดตโครงการไม่สำเร็จ' : 'สร้างโครงการไม่สำเร็จ'), 'error');
      }
    } catch (e) {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + e.message, 'error');
    }
    isAddingProject = false;
  }

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
          selectedProject = null;
          documents = [];
          docDetail = null;
        }
        await loadProjects();
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

  function escapeHtml(unsafe) {
    if (!unsafe) return "";
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
        codeBlockContent.push(rawLine);
        continue;
      }

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
</script>

<div class="pm-wrapper">
  
  <div class="pm-header">
    <h2>การจัดการโครงการ (Project Management)</h2>
    <p>สร้าง แก้ไข ลบ โครงการ และดูเนื้อหาของเอกสารในแต่ละโครงการได้ที่นี่</p>
  </div>

  <div class="pm-grid">
    <!-- Left Panel: Project Table -->
    <div class="left-panel glass-card">
      <div class="panel-header">
        <h3 class="panel-title">รายชื่อโครงการ ({projects.length})</h3>
        <button class="btn-primary" on:click={openAddProject}>+ สร้างโครงการ</button>
      </div>
      
      {#if dbError}
        <div class="error-state">{dbError}</div>
      {:else}
        <div class="table-responsive">
          <table class="pm-table">
            <thead>
              <tr>
                <th style="width: 40px; text-align: center;"></th>
                <th>รหัสโครงการ</th>
                <th>ชื่อโครงการ</th>
                <th>จำนวนเอกสาร</th>
                <th>สถานะ</th>
                <th>การจัดการ</th>
              </tr>
            </thead>
            <tbody>
              {#each projects as p}
                <tr class:selected={selectedProject === p.id} on:click={() => selectProject(p)}>
                  <td style="text-align: center;" on:click|stopPropagation>
                    <button class="btn-expand" on:click={(e) => toggleExpand(p, e)}>
                      {expandedProjectId === p.id ? '▼' : '▶'}
                    </button>
                  </td>
                  <td>{p.project_code || '-'}</td>
                  <td class="proj-name">
                    <div class="truncate" title={p.name}>{p.name}</div>
                    {#if p.description}
                      <div class="proj-desc truncate" title={p.description}>{p.description}</div>
                    {/if}
                    {#if p.site_urls && p.site_urls.length > 0}
                      <div class="proj-sites-tags" style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px;">
                        {#each p.site_urls as s}
                          {#if s.url}
                            <span 
                              class="site-tag-pill" 
                              class:is-default={s.is_default}
                              title={`${s.env_type}: ${s.url} ${s.is_default ? '(Default Site)' : ''}`}
                            >
                              <span class="env-badge env-{s.env_type ? s.env_type.toLowerCase() : 'test'}">{s.env_type || 'TEST'}</span>
                              <span class="url-text truncate">{s.url}</span>
                              {#if s.is_default}
                                <span class="star-icon" title="Site Default หลัก">⭐</span>
                              {/if}
                            </span>
                          {/if}
                        {/each}
                      </div>
                    {:else if p.default_base_url}
                      <div class="proj-url truncate" style="font-size: 11px; color: #38bdf8; display: flex; align-items: center; gap: 4px; margin-top: 2px;" title={`Default Base URL: ${p.default_base_url}`}>
                        <span>🌐</span>
                        <span>{p.default_base_url}</span>
                      </div>
                    {/if}
                  </td>
                  <td>{p.doc_count || 0} รายการ</td>
                  <td>
                    <span class="status-badge" class:active={p.status === 'Active'}>{p.status || 'Active'}</span>
                  </td>
                  <td class="actions-cell" on:click|stopPropagation>
                    <div class="actions-wrapper">
                      <button class="btn-icon edit" on:click={() => openEditProject(p)} title="แก้ไข">✏️</button>
                      <button class="btn-icon delete" on:click={() => confirmDeleteProject(p)} title="ลบ">🗑️</button>
                    </div>
                  </td>
                </tr>
                {#if expandedProjectId === p.id}
                  <tr class="expanded-row">
                    <td colspan="6">
                      <div class="expanded-content">
                        {#if isExpanding}
                          <div class="sub-loading">กำลังโหลด...</div>
                        {:else if expandedDocs.length > 0}
                          <div class="sub-doc-list">
                            {#each expandedDocs as doc}
                              <button class="sub-doc-item" class:active={selectedDoc === doc.id} on:click={(e) => selectSubDoc(doc, p, e)}>
                                📄 {doc.name}
                              </button>
                            {/each}
                          </div>
                        {:else}
                          <div class="sub-empty">ไม่มีเอกสารในโครงการนี้</div>
                        {/if}
                      </div>
                    </td>
                  </tr>
                {/if}
              {/each}
              {#if projects.length === 0}
                <tr>
                  <td colspan="6" class="empty-table">ยังไม่มีโครงการในระบบ</td>
                </tr>
              {/if}
            </tbody>
          </table>
        </div>
      {/if}
    </div>

    <!-- Right Panel: Document Viewer -->
    <div class="right-panel glass-card">
      {#if selectedProject}
        {#if docDetail}
          <div class="doc-viewer">
            <div class="viewer-header">
              <button class="btn-back" on:click={() => { docDetail = null; selectedDoc = null; }}>← กลับไปรายการเอกสาร</button>
              <h3 class="viewer-title truncate">{docDetail.document.filename || docDetail.document.title || 'เอกสาร'}</h3>
            </div>
            
            <div class="viewer-meta">
              <div class="meta-item"><span class="lbl">หมวดหมู่:</span> {docDetail.document.doc_category || 'General'}</div>
              <div class="meta-item"><span class="lbl">Chunks:</span> {docDetail.chunks.length}</div>
              <div class="meta-item"><span class="lbl">วันที่:</span> {formatDate(docDetail.document.created_at)}</div>
            </div>

            <div class="viewer-content">
              {@html parseMarkdownToHtml(docDetail.document.content)}
            </div>
          </div>
        {:else}
          <div class="panel-header">
            <h3 class="panel-title">
              เอกสารในโครงการ: {projects.find(p => p.id === selectedProject)?.name || ''}
            </h3>
          </div>
          
          {#if isLoadingDocs}
            <div class="loading-state">กำลังโหลดเอกสาร...</div>
          {:else if documents.length > 0}
            <div class="doc-list">
              {#each documents as doc}
                <button class="doc-card" on:click={() => loadDocDetail(doc.id)}>
                  <div class="doc-icon">📄</div>
                  <div class="doc-info">
                    <div class="doc-name truncate">{doc.name}</div>
                    <div class="doc-sub">
                      {doc.doc_category || 'General'} • {doc.chunk_count} chunks
                    </div>
                  </div>
                  <div class="doc-arrow">→</div>
                </button>
              {/each}
            </div>
          {:else}
            <div class="empty-state">
              <div class="empty-icon">📂</div>
              <p>ไม่มีเอกสารในโครงการนี้</p>
            </div>
          {/if}
        {/if}
      {:else}
        <div class="empty-state">
          <div class="empty-icon">👈</div>
          <p>เลือกโครงการจากตารางด้านซ้าย<br/>เพื่อดูรายการเอกสาร</p>
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- ── Add/Edit Project Modal ── -->
{#if showAddProject}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-backdrop" on:click={() => showAddProject = false} on:keydown={(e) => e.key === 'Escape' && (showAddProject = false)} role="presentation">
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-content" on:click|stopPropagation on:keydown|stopPropagation role="dialog" aria-modal="true" aria-label={isEditMode ? "แก้ไขโครงการ" : "เพิ่มโครงการใหม่"}>
      <div class="modal-header">
        <h3>{isEditMode ? "แก้ไขโครงการ" : "เพิ่มโครงการใหม่"}</h3>
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
        <!-- Multi-Site Base URLs Manager -->
        <div class="form-group sites-manager-group">
          <div class="sites-manager-header">
            <label class="sites-label">
              <span>🌐</span>
              <span>Target Site Base URLs (สำหรับ AI Test Agent)</span>
            </label>
            <button type="button" class="btn-add-site" on:click={addSiteUrlRow}>
              + เพิ่ม Site
            </button>
          </div>
          <span class="sites-hint">
            กำหนด URL ของเซิร์ฟเวอร์ระบบทดสอบ (TEST, UAT, PRD) พร้อมคลิกเลือก <b>⭐ Default</b> เพื่อให้ AI Agent ใช้เป็น Site เริ่มต้น
          </span>

          <div class="site-urls-list">
            {#if newProject.site_urls && newProject.site_urls.length > 0}
              {#each newProject.site_urls as site, idx}
                <div class="site-url-row" class:is-default-row={site.is_default}>
                  <select class="site-env-select env-{site.env_type ? site.env_type.toLowerCase() : 'test'}" bind:value={site.env_type} on:change={() => { if (site.is_default) setDefaultSite(idx); }}>
                    <option value="TEST">TEST</option>
                    <option value="UAT">UAT</option>
                    <option value="PRD">PRD</option>
                    <option value="DEV">DEV</option>
                    <option value="STAGING">STAGING</option>
                    <option value="CUSTOM">CUSTOM</option>
                  </select>

                  <input 
                    type="text" 
                    class="form-input site-url-input" 
                    placeholder="เช่น http://localhost:5173 หรือ https://uat.example.com" 
                    bind:value={site.url}
                    on:input={() => { if (site.is_default) newProject.default_base_url = site.url; }}
                  />

                  <button 
                    type="button" 
                    class="btn-default-toggle" 
                    class:active={site.is_default}
                    on:click={() => setDefaultSite(idx)}
                    title={site.is_default ? "เป็น Site Default หลักที่ AI Agent จะใช้อัตโนมัติ" : "คลิกเพื่อตั้งเป็น Site Default"}
                  >
                    {#if site.is_default}
                      ⭐ Default
                    {:else}
                      ตั้ง Default
                    {/if}
                  </button>

                  <button 
                    type="button" 
                    class="btn-remove-site" 
                    on:click={() => removeSiteUrlRow(idx)}
                    title="ลบ Site นี้"
                    disabled={newProject.site_urls.length <= 1}
                  >
                    ✕
                  </button>
                </div>
              {/each}
            {/if}
          </div>
        </div>
        <div class="form-group">
          <label for="p_status">สถานะ (Status)</label>
          <CustomSelect 
            id="p_status" 
            bind:value={newProject.status} 
            options={projectStatusOptions} 
            width="100%"
          />
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" on:click={() => showAddProject = false}>ยกเลิก</button>
        <button class="btn-submit" on:click={createProject} disabled={isAddingProject || !newProject.project_name.trim()}>
          {isAddingProject ? 'กำลังบันทึก...' : (isEditMode ? 'บันทึกการแก้ไข' : 'สร้างโครงการ')}
        </button>
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
            กำลังลบ...
          {:else}
            ลบโครงการถาวร
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  :global(:root) {
    --pm-bg: #0b0f19;
    --pm-card: rgba(16, 24, 39, 0.7);
    --pm-border: rgba(255, 255, 255, 0.08);
    --pm-text: #e2e8f0;
    --pm-text-muted: #94a3b8;
    --pm-primary: #6366f1;
    --pm-primary-hover: #4f46e5;
    --pm-danger: #ef4444;
  }

  .pm-wrapper {
    padding: 24px 32px;
    height: 100vh;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    color: var(--pm-text);
  }

  .pm-header {
    margin-bottom: 24px;
  }

  .pm-header h2 {
    margin: 0 0 8px 0;
    font-size: 24px;
    color: #fff;
  }
  
  .pm-header p {
    margin: 0;
    color: var(--pm-text-muted);
    font-size: 14px;
  }

  .pm-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    flex: 1;
    min-height: 0; /* Important for scroll */
  }

  .glass-card {
    background: var(--pm-card);
    border: 1px solid var(--pm-border);
    border-radius: 12px;
    backdrop-filter: blur(12px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .panel-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--pm-border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(0,0,0,0.2);
  }

  .panel-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
  }

  .btn-primary {
    background: var(--pm-primary);
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-primary:hover {
    background: var(--pm-primary-hover);
  }

  /* Table Styles */
  .table-responsive {
    flex: 1;
    overflow-y: auto;
  }

  .pm-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }

  .pm-table th {
    position: sticky;
    top: 0;
    background: rgba(16, 24, 39, 0.95);
    padding: 14px 20px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--pm-text-muted);
    border-bottom: 1px solid var(--pm-border);
    z-index: 10;
  }

  .pm-table td {
    padding: 14px 20px;
    border-bottom: 1px solid var(--pm-border);
    font-size: 14px;
    cursor: pointer;
    transition: background 0.2s;
  }

  .pm-table tr:hover td {
    background: rgba(255, 255, 255, 0.03);
  }

  .pm-table tr.selected td {
    background: rgba(99, 102, 241, 0.1);
  }

  .proj-name {
    max-width: 200px;
  }

  .proj-desc {
    font-size: 12px;
    color: var(--pm-text-muted);
    margin-top: 4px;
  }

  .truncate {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .status-badge {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    background: rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
  }

  .status-badge.active {
    background: rgba(74, 222, 128, 0.15);
    color: #4ade80;
  }

  .actions-wrapper {
    display: flex;
    gap: 8px;
  }

  .btn-icon {
    background: transparent;
    border: none;
    font-size: 16px;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: background 0.2s;
    opacity: 0.7;
  }

  .btn-icon:hover {
    background: rgba(255, 255, 255, 0.1);
    opacity: 1;
  }

  .empty-table {
    text-align: center;
    padding: 40px !important;
    color: var(--pm-text-muted);
    font-style: italic;
  }

  .btn-expand {
    background: transparent;
    border: none;
    color: var(--pm-text-muted);
    cursor: pointer;
    font-size: 14px;
    padding: 4px;
    transition: color 0.2s;
  }
  
  .btn-expand:hover {
    color: var(--pm-text);
  }

  .expanded-row td {
    padding: 0 !important;
    background: rgba(0,0,0,0.2) !important;
  }

  .expanded-content {
    padding: 12px 20px 12px 70px;
  }

  .sub-doc-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .sub-doc-item {
    background: rgba(255,255,255,0.03);
    border: 1px solid transparent;
    color: var(--pm-text);
    text-align: left;
    padding: 8px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .sub-doc-item:hover {
    background: rgba(255,255,255,0.08);
  }

  .sub-doc-item.active {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.3);
    color: #fff;
  }

  .sub-loading, .sub-empty {
    font-size: 13px;
    color: var(--pm-text-muted);
    padding: 8px 0;
  }

  /* Right Panel */
  .right-panel {
    display: flex;
    flex-direction: column;
  }

  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: var(--pm-text-muted);
    text-align: center;
  }

  .empty-icon {
    font-size: 48px;
    margin-bottom: 16px;
    opacity: 0.5;
  }
  
  .loading-state {
    padding: 40px;
    text-align: center;
    color: var(--pm-text-muted);
  }

  .doc-list {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .doc-card {
    display: flex;
    align-items: center;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--pm-border);
    border-radius: 8px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
    color: var(--pm-text);
  }

  .doc-card:hover {
    background: rgba(99, 102, 241, 0.1);
    border-color: rgba(99, 102, 241, 0.3);
    transform: translateY(-2px);
  }

  .doc-icon {
    font-size: 24px;
    margin-right: 16px;
  }

  .doc-info {
    flex: 1;
    min-width: 0;
  }

  .doc-name {
    font-weight: 500;
    margin-bottom: 4px;
  }

  .doc-sub {
    font-size: 12px;
    color: var(--pm-text-muted);
  }

  .doc-arrow {
    font-size: 18px;
    color: var(--pm-text-muted);
    margin-left: 16px;
  }

  /* Document Viewer */
  .doc-viewer {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }

  .viewer-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--pm-border);
    background: rgba(0,0,0,0.2);
  }

  .btn-back {
    background: transparent;
    border: none;
    color: var(--pm-primary);
    cursor: pointer;
    font-size: 13px;
    padding: 0;
    margin-bottom: 8px;
    font-weight: 500;
  }
  
  .btn-back:hover {
    text-decoration: underline;
  }

  .viewer-title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }

  .viewer-meta {
    display: flex;
    gap: 16px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--pm-border);
    background: rgba(255,255,255,0.02);
    font-size: 12px;
  }

  .meta-item .lbl {
    color: var(--pm-text-muted);
    margin-right: 4px;
  }

  .viewer-content {
    flex: 1;
    overflow-y: auto;
    padding: 24px 20px;
    background: #0f172a;
    line-height: 1.6;
    font-size: 14px;
  }

  /* Modal Styles (Shared with KnowledgeBase) */
  .modal-backdrop {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content {
    background: #1e1e2e;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    width: 92%;
    max-width: 620px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
    overflow: hidden;
  }

  /* Multi-Site Base URLs Manager Styles */
  .sites-manager-group {
    background: rgba(15, 23, 42, 0.4);
    border: 1px solid rgba(56, 189, 248, 0.15);
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 16px;
  }

  .sites-manager-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .sites-label {
    margin: 0 !important;
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #38bdf8 !important;
  }

  .btn-add-site {
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-add-site:hover {
    background: rgba(56, 189, 248, 0.25);
    color: #fff;
    border-color: #38bdf8;
  }

  .sites-hint {
    font-size: 11px;
    color: #94a3b8;
    margin-bottom: 10px;
    display: block;
    line-height: 1.4;
  }

  .site-urls-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .site-url-row {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(0, 0, 0, 0.3);
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: all 0.2s;
  }

  .site-url-row.is-default-row {
    border-color: rgba(56, 189, 248, 0.4);
    background: rgba(56, 189, 248, 0.04);
  }

  .site-env-select {
    padding: 7px 8px;
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    color: #f1f5f9;
    font-size: 12px;
    font-weight: 600;
    width: 90px;
    cursor: pointer;
  }

  .site-url-input {
    flex: 1;
    padding: 7px 10px !important;
    font-size: 13px !important;
    background: rgba(15, 23, 42, 0.6) !important;
  }

  .btn-default-toggle {
    background: rgba(255, 255, 255, 0.06);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
  }

  .btn-default-toggle:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
  }

  .btn-default-toggle.active {
    background: rgba(245, 158, 11, 0.18);
    color: #fbbf24;
    border-color: rgba(245, 158, 11, 0.5);
    font-weight: 600;
  }

  .btn-remove-site {
    background: transparent;
    color: #64748b;
    border: none;
    font-size: 14px;
    cursor: pointer;
    padding: 4px 6px;
    border-radius: 4px;
    transition: all 0.2s;
  }

  .btn-remove-site:hover:not(:disabled) {
    color: #f87171;
    background: rgba(239, 68, 68, 0.1);
  }

  .btn-remove-site:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  /* Table Site Tags */
  .site-tag-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 11px;
    max-width: 280px;
  }

  .site-tag-pill.is-default {
    border-color: rgba(56, 189, 248, 0.35);
    background: rgba(56, 189, 248, 0.08);
  }

  .env-badge {
    font-size: 9px;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 3px;
    text-transform: uppercase;
  }

  .env-test, .env-dev {
    background: rgba(56, 189, 248, 0.2);
    color: #38bdf8;
  }

  .env-uat {
    background: rgba(245, 158, 11, 0.2);
    color: #fbbf24;
  }

  .env-prd {
    background: rgba(168, 85, 247, 0.2);
    color: #c084fc;
  }

  .env-staging, .env-custom {
    background: rgba(148, 163, 184, 0.2);
    color: #cbd5e1;
  }

  .url-text {
    color: #cbd5e1;
    max-width: 170px;
  }

  .site-tag-pill.is-default .url-text {
    color: #e0f2fe;
    font-weight: 500;
  }

  .star-icon {
    font-size: 10px;
    color: #fbbf24;
  }

  .modal-sm {
    max-width: 400px;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(0, 0, 0, 0.2);
  }

  .modal-header h3 {
    margin: 0;
    font-size: 16px;
    color: #e2e8f0;
  }

  .danger-text {
    color: var(--pm-danger) !important;
  }

  .btn-close {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 18px;
    cursor: pointer;
  }
  
  .btn-close:hover {
    color: #fff;
  }

  .modal-body {
    padding: 20px;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    margin-bottom: 6px;
    font-size: 13px;
    color: #cbd5e1;
  }

  .req {
    color: var(--pm-danger);
  }

  .form-input {
    width: 100%;
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: #fff;
    font-size: 14px;
    box-sizing: border-box;
    font-family: inherit;
  }

  .form-input:focus {
    outline: none;
    border-color: var(--pm-primary);
  }

  .modal-footer {
    padding: 16px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    background: rgba(0, 0, 0, 0.2);
  }

  .btn-cancel {
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #cbd5e1;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-cancel:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #fff;
  }

  .btn-submit {
    background: var(--pm-primary);
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-submit:hover:not(:disabled) {
    background: var(--pm-primary-hover);
  }

  .btn-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .danger-bg {
    background: var(--pm-danger);
  }
  
  .danger-bg:hover:not(:disabled) {
    background: #dc2626;
  }
</style>
