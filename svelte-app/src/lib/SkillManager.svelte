<script>
  import { onMount } from 'svelte';
  import CustomSelect from './CustomSelect.svelte';

  // ── States ──
  let skills = [];
  let loading = false;
  let saving = false;
  let search = '';
  let filterDocType = '';

  let activeSkill = null;
  let isEditing = false;
  let editorTab = 'edit'; // 'edit' | 'preview'

  // Form State
  let form = {
    skill_id: null,
    skill_name: '',
    skill_description: '',
    markdown_instructions: '',
    target_doc_type: 'General',
    version: 1,
    is_active: true,
    created_by: 'Admin'
  };

  const docTypes = ['General', 'Flowchart', 'Table', 'SRS Document', 'PDF', 'Image', 'Word', 'Other'];

  $: filterDocTypeOptions = [
    { value: '', label: 'ทุกประเภท (Doc Type)', icon: '📁' },
    ...docTypes.map(t => ({ value: t, label: t, icon: '📄' }))
  ];
  $: targetDocTypeOptions = docTypes.map(t => ({ value: t, label: t, icon: '📄' }));

  // Prompt Templates
  const templates = [
    {
      name: 'Flowchart to Mermaid',
      docType: 'Flowchart',
      desc: 'แปลงรูปภาพหรือคำบรรยาย Flowchart ให้เป็นโค้ด Mermaid.js',
      instructions: `### Flowchart to Mermaid Conversion Instructions\n\n1. อ่านและวิเคราะห์ความสัมพันธ์ของกระบวนการทำงานในเอกสาร\n2. แปลงขั้นตอนทั้งหมดให้เป็นโค้ด Mermaid.js ในรูปแบบ graph TD หรือ flowchart LR\n3. กำหนดเงื่อนไขการตัดสินใจ (Decision Point) เช่น Yes / No ให้ชัดเจน\n4. แสดงผลลัพธ์เป็นบล็อกโค้ด \`\`\`mermaid เท่านั้น\n\n\`\`\`mermaid\ngraph TD\n    A[เริ่มต้น] --> B{ตรวจสอบเงื่อนไข}\n    B -- ผ่าน --> C[ดำเนินการต่อ]\n    B -- ไม่ผ่าน --> D[แจ้งเตือนข้อผิดพลาด]\n\`\`\``
    },
    {
      name: 'Table Data Extractor',
      docType: 'Table',
      desc: 'สกัดข้อมูลตารางจากเอกสารสแกนให้อยู่ในฟอร์แมต Markdown Table',
      instructions: `### Table Extraction Guidelines\n\n1. สกัดตารางทั้งหมดในเอกสารสแกนให้อยู่ในรูปแบบ Markdown Table (| Header 1 | Header 2 |)\n2. ห้ามข้ามแถวหรือคอลัมน์ แม้ว่าจะเป็นช่องว่าง\n3. จัดรูปอักขระตัวเลขและวันที่ให้ถูกต้องตามต้นฉบับ`
    },
    {
      name: 'QA Rule Inspector',
      docType: 'SRS Document',
      desc: 'ตรวจสอบข้อกำหนด Functional & Non-Functional ในเอกสาร SRS',
      instructions: `### QA Rule Inspection Skill\n\n1. ตรวจสอบข้อกำหนดระบบ (Functional Requirements: FR)\n2. ระบุจุดเสี่ยง หรือเงื่อนไขที่ขาดหายไปในเอกสาร\n3. สรุปรายการ Test Case ที่ต้องทดสอบ`
    }
  ];

  // ── Functions ──
  async function fetchSkills() {
    loading = true;
    try {
      let url = 'http://localhost:5000/api/skills?';
      if (search) url += `search=${encodeURIComponent(search)}&`;
      if (filterDocType) url += `target_doc_type=${encodeURIComponent(filterDocType)}&`;

      const res = await fetch(url);
      const data = await res.json();
      if (res.ok) {
        skills = (data.skills || []).filter(s => 
          !s.skill_name?.startsWith('[Exit Criteria]') && 
          !s.skill_name?.includes('Exit Criteria')
        );
        if (skills.length > 0 && !activeSkill) {
          selectSkill(skills[0]);
        }
      }
    } catch (e) {
      console.error('Failed to fetch skills:', e);
    } finally {
      loading = false;
    }
  }

  function selectSkill(skill) {
    activeSkill = skill;
    isEditing = true;
    form = {
      skill_id: skill.skill_id,
      skill_name: skill.skill_name || '',
      skill_description: skill.skill_description || '',
      markdown_instructions: skill.markdown_instructions || '',
      target_doc_type: skill.target_doc_type || 'General',
      version: skill.version || 1,
      is_active: skill.is_active !== undefined ? skill.is_active : true,
      created_by: skill.created_by || 'Admin'
    };
  }

  function startCreateNew() {
    activeSkill = null;
    isEditing = true;
    form = {
      skill_id: null,
      skill_name: '',
      skill_description: '',
      markdown_instructions: '',
      target_doc_type: 'General',
      version: 1,
      is_active: true,
      created_by: 'Admin'
    };
  }

  function applyTemplate(tpl) {
    form.skill_name = form.skill_name || tpl.name;
    form.target_doc_type = tpl.docType;
    form.skill_description = form.skill_description || tpl.desc;
    form.markdown_instructions = tpl.instructions;
  }

  async function saveSkill() {
    if (!form.skill_name.trim() || !form.markdown_instructions.trim()) {
      alert('กรุณากรอก ชื่อ Skill และ เนื้อหา Markdown Instructions');
      return;
    }

    saving = true;
    try {
      const isNew = !form.skill_id;
      const url = isNew ? 'http://localhost:5000/api/skills' : `http://localhost:5000/api/skills/${form.skill_id}`;
      const method = isNew ? 'POST' : 'PUT';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      });
      const data = await res.json();

      if (res.ok) {
        alert(isNew ? 'สร้าง Skill ใหม่สำเร็จ' : 'อัปเดต Skill สำเร็จ');
        await fetchSkills();
        if (data.skill_id) {
          const created = skills.find(s => s.skill_id === data.skill_id);
          if (created) selectSkill(created);
        }
      } else {
        alert(`ข้อผิดพลาด: ${data.error}`);
      }
    } catch (e) {
      alert(`เกิดข้อผิดพลาด: ${e.message}`);
    } finally {
      saving = false;
    }
  }

  async function deleteSkill() {
    if (!form.skill_id) return;
    if (!confirm(`คุณต้องการลบ Skill "${form.skill_name}" ใช่หรือไม่?`)) return;

    try {
      const res = await fetch(`http://localhost:5000/api/skills/${form.skill_id}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (res.ok) {
        alert('ลบ Skill สำเร็จ');
        activeSkill = null;
        await fetchSkills();
        if (skills.length > 0) selectSkill(skills[0]);
        else startCreateNew();
      } else {
        alert(`ลบไม่สำเร็จ: ${data.error}`);
      }
    } catch (e) {
      alert(`เกิดข้อผิดพลาด: ${e.message}`);
    }
  }

  function downloadSkillMd() {
    if (!form.skill_name) return;
    const content = `---
name: "${form.skill_name}"
description: "${form.skill_description || ''}"
target_doc_type: "${form.target_doc_type || 'General'}"
version: ${form.version || 1}
created_by: "${form.created_by || 'Admin'}"
---

# ${form.skill_name}

${form.skill_description || ''}

## Skill Instructions (SKILL.md)

${form.markdown_instructions}
`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${form.skill_name.toLowerCase().replace(/\s+/g, '_')}_SKILL.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Simple Markdown to HTML preview helper
  function renderMarkdownPreview(str) {
    if (!str) return '<div class="empty-preview">ไม่มีเนื้อหา Markdown</div>';
    let html = str
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n\n/g, '<br/><br/>');
    return html;
  }

  onMount(() => {
    fetchSkills();
  });
</script>

<div class="skills-container">
  <!-- ── Left Sidebar (List & Search) ── -->
  <aside class="sidebar">
    <div class="sidebar-header">
      <div class="header-top">
        <div class="title-wrap">
          <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
            <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 103.636 5.05l-.707.707a1 1 0 001.414 1.414l.707-.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1a1 1 0 112 0v1a1 1 0 11-2 0zM12 14a1 1 0 100-2 1 1 0 000 2z"/>
          </svg>
          <span class="sidebar-title">AI Skills Center</span>
        </div>
        <button class="btn-new" on:click={startCreateNew}>
          + สร้าง Skill
        </button>
      </div>

      <!-- Search & Filter -->
      <div class="filter-box">
        <input
          type="text"
          placeholder="ค้นหา Skill / Prompt..."
          bind:value={search}
          on:input={fetchSkills}
          class="search-input"
        />
        <CustomSelect 
          bind:value={filterDocType} 
          options={filterDocTypeOptions} 
          on:change={fetchSkills}
          minWidth="190px"
        />
      </div>
    </div>

    <!-- Skill List -->
    <div class="skills-list">
      {#if loading}
        <div class="loading-state">กำลังโหลดรายการ Skills...</div>
      {:else if skills.length === 0}
        <div class="empty-state">ไม่พบ AI Skill ในระบบ</div>
      {:else}
        {#each skills as item}
          <div
            class="skill-card"
            class:active={activeSkill && activeSkill.skill_id === item.skill_id}
            on:click={() => selectSkill(item)}
          >
            <div class="card-head">
              <span class="card-name">{item.skill_name}</span>
              <span class="badge" class:active-badge={item.is_active}>
                {item.is_active ? 'Active' : 'Draft'}
              </span>
            </div>
            <p class="card-desc">{item.skill_description || 'ไม่มีคำอธิบาย'}</p>
            <div class="card-meta">
              <span class="tag">{item.target_doc_type || 'General'}</span>
              <span class="version">v{item.version}</span>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </aside>

  <!-- ── Main Content / Editor Panel ── -->
  <main class="main-editor">
    {#if isEditing}
      <!-- Header / Action Bar -->
      <header class="editor-header">
        <div class="header-info">
          <h2>{form.skill_id ? `แก้ไข: ${form.skill_name}` : '✨ สร้าง AI Skill ใหม่'}</h2>
          <span class="sub-info">จัดการ Prompt คู่มือสมองกล (SKILL.md)</span>
        </div>
        <div class="header-actions">
          {#if form.skill_id}
            <button class="btn-danger" on:click={deleteSkill}>🗑️ ลบ</button>
            <button class="btn-secondary" on:click={downloadSkillMd}>📥 ดาวน์โหลด SKILL.md</button>
          {/if}
          <button class="btn-primary" on:click={saveSkill} disabled={saving}>
            {saving ? 'กำลังบันทึก...' : '💾 บันทึก Skill'}
          </button>
        </div>
      </header>

      <!-- Metadata Inputs Grid -->
      <div class="meta-grid">
        <div class="form-group">
          <label>ชื่อ Skill (Skill Name) *</label>
          <input type="text" bind:value={form.skill_name} placeholder="เช่น Flowchart Analyzer" />
        </div>
        <div class="form-group">
          <label>ประเภทเอกสารเป้าหมาย (Target Doc Type)</label>
          <CustomSelect 
            bind:value={form.target_doc_type} 
            options={targetDocTypeOptions} 
            width="100%"
          />
        </div>
        <div class="form-group">
          <label>เวอร์ชัน (Version)</label>
          <input type="number" min="1" bind:value={form.version} />
        </div>
        <div class="form-group">
          <label>ผู้สร้าง (Created By)</label>
          <input type="text" bind:value={form.created_by} />
        </div>
        <div class="form-group full-width">
          <label>คำอธิบายสั้นๆ (Description)</label>
          <input type="text" bind:value={form.skill_description} placeholder="อธิบายหน้าที่ของ Skill นี้สั้นๆ" />
        </div>
        <div class="form-group checkbox-group">
          <label class="toggle-label">
            <input type="checkbox" bind:checked={form.is_active} />
            <span>เปิดใช้งาน Skill นี้ (Active Status)</span>
          </label>
        </div>
      </div>

      <!-- Template Selector Snippets -->
      <div class="template-selector">
        <span class="tpl-title">💡 ใช้แม่แบบ Prompt สำเร็จรูป:</span>
        <div class="tpl-buttons">
          {#each templates as tpl}
            <button class="tpl-chip" on:click={() => applyTemplate(tpl)}>
              + {tpl.name} ({tpl.docType})
            </button>
          {/each}
        </div>
      </div>

      <!-- Dual Tab Editor & Preview -->
      <div class="editor-container">
        <div class="editor-tabs">
          <button
            class="tab-btn"
            class:active={editorTab === 'edit'}
            on:click={() => editorTab = 'edit'}
          >
            ✎ คู่มือการทำงาน (Markdown Instructions)
          </button>
          <button
            class="tab-btn"
            class:active={editorTab === 'preview'}
            on:click={() => editorTab = 'preview'}
          >
            👁️ พรีวิว SKILL.md
          </button>
        </div>

        {#if editorTab === 'edit'}
          <textarea
            class="code-editor"
            bind:value={form.markdown_instructions}
            placeholder="กรอกคู่มือ Prompt และเงื่อนไขการทำงานสำหรับ AI Agent (SKILL.md) ที่นี่..."
          ></textarea>
        {:else}
          <div class="preview-box">
            <div class="frontmatter">
              <div>---</div>
              <div>name: "{form.skill_name}"</div>
              <div>description: "{form.skill_description}"</div>
              <div>target_doc_type: "{form.target_doc_type}"</div>
              <div>version: {form.version}</div>
              <div>created_by: "{form.created_by}"</div>
              <div>---</div>
            </div>
            <div class="markdown-rendered">
              {@html renderMarkdownPreview(form.markdown_instructions)}
            </div>
          </div>
        {/if}
      </div>
    {:else}
      <div class="no-selection">
        <p>กรุณาเลือก Skill จากรายการด้านซ้าย หรือกดปุ่ม "+ สร้าง Skill" เพื่อเริ่มต้น</p>
      </div>
    {/if}
  </main>
</div>

<style>
  .skills-container {
    display: flex;
    height: 100%;
    width: 100%;
    background: var(--bg);
    color: var(--text);
    overflow: hidden;
  }

  /* ── Sidebar ── */
  .sidebar {
    width: 320px;
    background: var(--bg2);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .sidebar-header {
    padding: 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .header-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .title-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--primary);
    font-weight: 700;
    font-size: 15px;
  }

  .btn-new {
    background: var(--primary);
    color: #fff;
    border: none;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-new:hover {
    box-shadow: 0 0 10px var(--glow);
    transform: translateY(-1px);
  }

  .filter-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .search-input, .filter-select {
    width: 100%;
    padding: 8px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-size: 12px;
  }

  .skills-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .skill-card {
    padding: 12px;
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--border);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .skill-card:hover {
    background: rgba(108,142,251,0.06);
    border-color: var(--border2);
  }
  .skill-card.active {
    background: rgba(108,142,251,0.15);
    border-color: var(--primary);
    box-shadow: 0 0 12px rgba(108,142,251,0.2);
  }

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }
  .card-name {
    font-weight: 600;
    font-size: 13px;
    color: var(--text);
  }

  .badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(255,255,255,0.1);
    color: var(--text3);
  }
  .badge.active-badge {
    background: rgba(52, 211, 153, 0.2);
    color: #34d399;
  }

  .card-desc {
    font-size: 11px;
    color: var(--text3);
    line-height: 1.4;
    margin-bottom: 8px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-meta {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--text3);
  }
  .tag {
    background: rgba(108,142,251,0.1);
    color: var(--primary);
    padding: 1px 6px;
    border-radius: 4px;
  }

  /* ── Main Editor ── */
  .main-editor {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 20px;
    gap: 16px;
  }

  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .editor-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
  }
  .sub-info {
    font-size: 12px;
    color: var(--text3);
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  .btn-primary {
    background: var(--primary);
    color: #fff;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-secondary {
    background: rgba(255,255,255,0.06);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
  }
  .btn-danger {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 8px 14px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
  }

  /* Meta Grid */
  .meta-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    background: var(--bg2);
    padding: 16px;
    border-radius: 10px;
    border: 1px solid var(--border);
  }
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .form-group.full-width {
    grid-column: span 3;
  }
  .form-group label {
    font-size: 11px;
    color: var(--text3);
    font-weight: 600;
  }
  .form-group input, .form-group select {
    padding: 8px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-size: 13px;
  }
  .checkbox-group {
    grid-column: span 1;
    justify-content: center;
  }
  .toggle-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    cursor: pointer;
  }

  /* Template selector */
  .template-selector {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 12px;
  }
  .tpl-title {
    color: var(--text3);
  }
  .tpl-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .tpl-chip {
    background: rgba(108,142,251,0.1);
    border: 1px solid rgba(108,142,251,0.2);
    color: var(--primary);
    padding: 4px 10px;
    border-radius: 14px;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .tpl-chip:hover {
    background: rgba(108,142,251,0.25);
  }

  /* Editor & Preview Tabs */
  .editor-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .editor-tabs {
    display: flex;
    background: rgba(0,0,0,0.2);
    border-bottom: 1px solid var(--border);
  }
  .tab-btn {
    padding: 10px 18px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text3);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
  }
  .tab-btn.active {
    color: var(--primary);
    border-bottom-color: var(--primary);
    font-weight: 700;
    background: rgba(108,142,251,0.06);
  }

  .code-editor {
    flex: 1;
    width: 100%;
    padding: 16px;
    background: var(--bg);
    color: var(--text);
    border: none;
    font-family: 'Consolas', 'Fira Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    resize: none;
    outline: none;
  }

  .preview-box {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    background: var(--bg);
    font-size: 14px;
    line-height: 1.7;
  }
  .frontmatter {
    background: rgba(0,0,0,0.4);
    padding: 12px 16px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 12px;
    color: #a78bfa;
    margin-bottom: 20px;
  }

  .loading-state, .empty-state, .no-selection {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text3);
    font-size: 13px;
  }
</style>
