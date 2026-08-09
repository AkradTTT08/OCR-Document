<script>
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { toast } from './toastStore.js';
  import CustomSelect from './CustomSelect.svelte';

  const severityOptions = [
    { value: 'Critical', label: 'Critical', icon: '🔴' },
    { value: 'Major', label: 'Major', icon: '🟠' },
    { value: 'Minor', label: 'Minor', icon: '🟢' }
  ];

  let templates = [];
  let loading = false;
  let saving = false;
  let search = '';
  let filterDocType = '';

  let activeTemplate = null;
  let isEditing = true;
  let showHelpModal = false;

  // Custom Dropdown States
  let showFilterDropdown = false;
  let showDocTypeDropdown = false;

  function closeDropdowns() {
    showFilterDropdown = false;
    showDocTypeDropdown = false;
  }

  // Template Form State
  let form = {
    template_id: null,
    title: '',
    description: '',
    doc_type: 'ALL',
    is_active: true,
    max_loops: 3,
    items: []
  };

  const docTypes = [
    'ALL',
    'Test Case',
    'UAT',
    'Project Plan',
    'SRS Document',
    'SDD',
    'Technical Spec',
    'SOP',
    'Contract',
    'Project Proposal',
    'Summary Report',
    'General'
  ];
  const categories = [
    'Defect & Comment Resolution',
    'Content Accuracy & Completeness',
    'Format & Consistency',
    'Governance & Control'
  ];

  const categoryTitles = {
    'Defect & Comment Resolution': 'หมวดที่ 1: การตอบสนองรายการแก้ไข (Defect & Comment Resolution)',
    'Content Accuracy & Completeness': 'หมวดที่ 2: ความถูกต้องและครบถ้วนของเนื้อหา (Content Accuracy & Completeness)',
    'Format & Consistency': 'หมวดที่ 3: รูปแบบและความเป็นเอกภาพ (Format & Consistency)',
    'Governance & Control': 'หมวดที่ 4: การกำกับดูแลและเวอร์ชัน (Governance & Control)'
  };

  const severities = ['Critical', 'Major', 'Minor'];

  onMount(() => {
    fetchTemplates();
  });

  async function fetchTemplates() {
    loading = true;
    try {
      let url = 'http://localhost:5000/api/exit-criteria/templates';
      const res = await fetch(url);
      const data = await res.json();
      if (res.ok && data.success) {
        templates = data.templates || [];
        if (templates.length > 0) {
          selectTemplate(templates[0].template_id);
        }
      } else {
        toast('Failed to load exit criteria templates', 'error');
      }
    } catch (e) {
      console.error('Fetch exit criteria templates error:', e);
      toast('Network error loading templates', 'error');
    } finally {
      loading = false;
    }
  }

  async function selectTemplate(templateId) {
    loading = true;
    try {
      const res = await fetch(`http://localhost:5000/api/exit-criteria/templates/${templateId}`);
      const data = await res.json();
      if (res.ok && data.success) {
        activeTemplate = data.template;
        form = {
          template_id: data.template.template_id,
          title: data.template.title || '',
          description: data.template.description || '',
          doc_type: data.template.doc_type || 'ALL',
          is_active: data.template.is_active !== undefined ? data.template.is_active : true,
          max_loops: data.template.max_loops !== undefined ? data.template.max_loops : 3,
          items: data.template.items ? data.template.items.map(it => ({
            ...it,
            target_metric: it.target_metric || (
              it.category === 'Defect & Comment Resolution' ? '100% Closed (แก้ไขครบ 100%)' :
              it.category === 'Content Accuracy & Completeness' ? '100% Verified (ถูกต้อง 100%)' :
              it.category === 'Format & Consistency' ? '< 1% Typo Rate (คำผิด < 1%)' :
              '100% Complete (สมบูรณ์ 100%)'
            )
          })) : []
        };
      }
    } catch (e) {
      console.error('Fetch template details error:', e);
      toast('Error loading template details', 'error');
    } finally {
      loading = false;
    }
  }

  function startNewTemplate() {
    activeTemplate = null;
    form = {
      template_id: null,
      title: 'New Document Exit Criteria Template',
      description: 'เกณฑ์การตรวจสอบคุณภาพเอกสาร',
      doc_type: 'ALL',
      is_active: true,
      max_loops: 3,
      items: [
        { item_code: '1.1', category: 'Defect & Comment Resolution', question_text: 'ข้อสั่งการ/Comment ระดับ Critical / High ในรอบก่อน ได้รับการแก้ไขเรียบร้อยแล้ว 100%', target_metric: '100% Closed (แก้ไขครบ 100%)', severity: 'Critical', is_mandatory: true, order_index: 1 },
        { item_code: '2.1', category: 'Content Accuracy & Completeness', question_text: 'ข้อมูล ตัวเลข สถิติ ข้อเท็จจริง และสูตรคำนวณ ตรวจสอบแล้วถูกต้องและมีแหล่งอ้างอิงน่าเชื่อถือ', target_metric: '100% Verified Accuracy (ถูกต้อง 100%)', severity: 'Critical', is_mandatory: true, order_index: 2 },
        { item_code: '3.1', category: 'Format & Consistency', question_text: 'ฟอนต์, ขนาดตัวอักษร, ระยะขอบ, การเว้นบรรทัด และการใช้สี เป็นไปตาม Template / CI', target_metric: '100% CI Compliance (ตรงตาม CI)', severity: 'Minor', is_mandatory: false, order_index: 3 },
        { item_code: '4.1', category: 'Governance & Control', question_text: 'มีการระบุ Document Title, Version Number, วันที่อัปเดต และชื่อผู้แต่ง/ผู้แก้ไขในหน้าแรกอย่างชัดเจน', target_metric: '100% Header & Metadata', severity: 'Major', is_mandatory: true, order_index: 4 }
      ]
    };
  }

  function addItem(cat) {
    const catItems = form.items.filter(i => i.category === cat);
    const prefix = cat === 'Defect & Comment Resolution' ? '1' : cat === 'Content Accuracy & Completeness' ? '2' : cat === 'Format & Consistency' ? '3' : '4';
    const subIdx = catItems.length + 1;
    const newCode = `${prefix}.${subIdx}`;
    
    let defaultMetric = '100% Closed (แก้ไขครบ 100%)';
    if (cat === 'Content Accuracy & Completeness') defaultMetric = '100% Verified (ถูกต้อง 100%)';
    else if (cat === 'Format & Consistency') defaultMetric = '< 1% Typo Rate (คำผิด < 1%)';
    else if (cat === 'Governance & Control') defaultMetric = '100% Complete (สมบูรณ์ 100%)';

    form.items = [
      ...form.items,
      {
        item_code: newCode,
        category: cat,
        question_text: 'ระบุรายการประเมินใหม่...',
        target_metric: defaultMetric,
        severity: 'Major',
        is_mandatory: true,
        order_index: form.items.length + 1
      }
    ];
  }

  function removeItem(index) {
    form.items = form.items.filter((_, idx) => idx !== index);
  }

  async function saveTemplate() {
    if (!form.title.trim()) {
      toast('กรุณาระบุชื่อ Template', 'warning');
      return;
    }
    saving = true;
    try {
      const isNew = !form.template_id;
      const url = isNew 
        ? 'http://localhost:5000/api/exit-criteria/templates'
        : `http://localhost:5000/api/exit-criteria/templates/${form.template_id}`;
      
      const method = isNew ? 'POST' : 'PUT';

      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form)
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('บันทึกเกณฑ์ Exit Criteria เรียบร้อยแล้ว!', 'success');
        await fetchTemplates();
        if (isNew && data.template_id) {
          selectTemplate(data.template_id);
        }
      } else {
        toast(data.error || 'เกิดข้อผิดพลาดในการบันทึก', 'error');
      }
    } catch (e) {
      console.error('Save template error:', e);
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
    } finally {
      saving = false;
    }
  }

  // Custom Confirm Modal State
  let showConfirmModal = false;
  let confirmModalData = {
    title: '',
    message: '',
    confirmText: 'ยืนยัน',
    cancelText: 'ยกเลิก',
    type: 'danger',
    onConfirm: () => {}
  };

  function askConfirmation({ title, message, confirmText = 'ยืนยัน', cancelText = 'ยกเลิก', type = 'danger', onConfirm }) {
    confirmModalData = { title, message, confirmText, cancelText, type, onConfirm };
    showConfirmModal = true;
  }

  function handleConfirmAction() {
    showConfirmModal = false;
    if (confirmModalData.onConfirm) {
      confirmModalData.onConfirm();
    }
  }

  function resetUniversalGate() {
    askConfirmation({
      title: 'คืนค่าเกณฑ์มาตรฐาน (Reset Template)',
      message: 'คุณต้องการคืนค่า Universal Document Exit Criteria Checklist เป็นค่ามาตรฐานเริ่มต้นใช่หรือไม่?',
      confirmText: 'รีเซ็ตค่ามาตรฐาน',
      type: 'warning',
      onConfirm: async () => {
        loading = true;
        try {
          const res = await fetch('http://localhost:5000/api/exit-criteria/reset-universal', { method: 'POST' });
          const data = await res.json();
          if (res.ok && data.success) {
            toast('รีเซ็ตเกณฑ์มาตรฐานกลางเรียบร้อยแล้ว!', 'success');
            await fetchTemplates();
          } else {
            toast(data.error || 'รีเซ็ตไม่สำเร็จ', 'error');
          }
        } catch (e) {
          toast('เกิดข้อผิดพลาดในการรีเซ็ต', 'error');
        } finally {
          loading = false;
        }
      }
    });
  }

  function deleteTemplate(templateId) {
    askConfirmation({
      title: 'ยืนยันการลบ Template',
      message: 'คุณแน่ใจหรือไม่ที่จะลบ Template นี้? ข้อมูลเกณฑ์ทั้งหมดใน Template นี้จะถูกลบอย่างถาวร',
      confirmText: 'ลบ Template',
      type: 'danger',
      onConfirm: async () => {
        try {
          const res = await fetch(`http://localhost:5000/api/exit-criteria/templates/${templateId}`, { method: 'DELETE' });
          const data = await res.json();
          if (res.ok && data.success) {
            toast('ลบ Template เรียบร้อยแล้ว', 'success');
            await fetchTemplates();
          } else {
            toast(data.error || 'ลบไม่สำเร็จ', 'error');
          }
        } catch (e) {
          toast('เกิดข้อผิดพลาดในการลบ', 'error');
        }
      }
    });
  }

  $: filteredTemplates = templates.filter(t => {
    const matchSearch = t.title.toLowerCase().includes(search.toLowerCase()) || (t.description && t.description.toLowerCase().includes(search.toLowerCase()));
    const matchDoc = !filterDocType || t.doc_type === filterDocType || t.doc_type === 'ALL';
    return matchSearch && matchDoc;
  });
</script>

<svelte:window on:click={closeDropdowns} />

<div class="exit-criteria-container">
  <!-- Header -->
  <header class="page-header">
    <div class="header-title">
      <div class="title-with-badge">
        <h2>📋 กำหนดเกณฑ์การผ่านการตรวจเอกสารมาตรฐาน (Exit Criteria)</h2>
        <span class="standard-badge">Universal Document Gate</span>
      </div>
      <p class="subtitle">จัดการเกณฑ์ Exit Criteria มาตรฐานกลางสำหรับตรวจสอบคุณภาพเอกสารทุกประเภทในองค์กร และใช้ร่วมกับ AIAgentQA</p>
    </div>
    <div class="header-actions">
      <button class="btn btn-info-glow" on:click={() => showHelpModal = true}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        คู่มือ & คำแนะนำการใช้งาน
      </button>

      <button class="btn btn-secondary" on:click={resetUniversalGate}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>
        Reset Standard Checklist
      </button>
      <button class="btn btn-primary" on:click={startNewTemplate}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        สร้าง Template ใหม่
      </button>
    </div>
  </header>

  <div class="main-layout">
    <!-- Sidebar / Template Selector -->
    <aside class="templates-sidebar">
      <div class="filter-box">
        <input type="text" bind:value={search} placeholder="ค้นหา Template..." class="search-input" />
        <div class="custom-dropdown-container">
          <button type="button" class="custom-dropdown-trigger" on:click|stopPropagation={() => showFilterDropdown = !showFilterDropdown}>
            <span>{filterDocType ? filterDocType : 'ทุกประเภทเอกสาร'}</span>
            <svg class="chevron" class:open={showFilterDropdown} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          {#if showFilterDropdown}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <div class="custom-dropdown-menu glass-panel" in:fade={{ duration: 120 }}>
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <div class="dropdown-item-opt" class:active={filterDocType === ''} on:click={() => { filterDocType = ''; showFilterDropdown = false; }}>
                <span>ทุกประเภทเอกสาร</span>
                {#if filterDocType === ''}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14" style="color: #6366f1;"><polyline points="20 6 9 17 4 12"></polyline></svg>{/if}
              </div>
              {#each docTypes as dt}
                <!-- svelte-ignore a11y-click-events-have-key-events -->
                <div class="dropdown-item-opt" class:active={filterDocType === dt} on:click={() => { filterDocType = dt; showFilterDropdown = false; }}>
                  <span>{dt}</span>
                  {#if filterDocType === dt}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14" style="color: #6366f1;"><polyline points="20 6 9 17 4 12"></polyline></svg>{/if}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="template-list">
        {#if loading && templates.length === 0}
          <div class="loading-state">กำลังโหลดข้อมูล...</div>
        {:else if filteredTemplates.length === 0}
          <div class="empty-state">ไม่พบ Template</div>
        {:else}
          {#each filteredTemplates as t}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <div 
              class="template-card" 
              class:active={form.template_id === t.template_id}
              on:click={() => selectTemplate(t.template_id)}
            >
              <div class="card-header-row">
                <span class="template-title">{t.title}</span>
                {#if t.doc_type === 'ALL'}
                  <span class="tag tag-purple">Universal</span>
                {:else}
                  <span class="tag tag-blue">{t.doc_type}</span>
                {/if}
              </div>
              <p class="template-desc">{t.description || 'ไม่มีคำอธิบาย'}</p>
              <div class="card-footer-row">
                <span class="item-count">{t.item_count || 0} รายการประเมิน</span>
                {#if t.template_id !== activeTemplate?.template_id && templates.length > 1}
                  <button class="icon-btn-danger" on:click|stopPropagation={() => deleteTemplate(t.template_id)} title="ลบ Template">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        {/if}
      </div>
    </aside>

    <!-- Main Content Editor -->
    <main class="editor-workspace">
      {#if loading}
        <div class="loading-overlay">กำลังโหลดรายละเอียด...</div>
      {:else}
        <!-- Form Header -->
        <div class="editor-card glass-panel">
          <div class="panel-header">
            <h3>⚙️ รายละเอียด Template</h3>
            <button class="btn btn-success" on:click={saveTemplate} disabled={saving}>
              {#if saving}
                กำลังบันทึก...
              {:else}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
                บันทึกเกณฑ์ Exit Criteria
              {/if}
            </button>
          </div>

          <div class="form-grid">
            <div class="form-group span-2">
              <label for="form_title">ชื่อ Template (Document Checklist Title):</label>
              <input type="text" id="form_title" bind:value={form.title} placeholder="เช่น Universal Document Exit Criteria" class="form-control" />
            </div>

            <div class="form-group">
              <label for="form_doc_type">ประเภทเอกสารเป้าหมาย (Doc Type):</label>
              <div class="custom-dropdown-container">
                <button type="button" class="custom-dropdown-trigger" on:click|stopPropagation={() => showDocTypeDropdown = !showDocTypeDropdown}>
                  <span>{form.doc_type}</span>
                  <svg class="chevron" class:open={showDocTypeDropdown} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>
                {#if showDocTypeDropdown}
                  <!-- svelte-ignore a11y-click-events-have-key-events -->
                  <div class="custom-dropdown-menu glass-panel" in:fade={{ duration: 120 }}>
                    {#each docTypes as dt}
                      <!-- svelte-ignore a11y-click-events-have-key-events -->
                      <div class="dropdown-item-opt" class:active={form.doc_type === dt} on:click={() => { form.doc_type = dt; showDocTypeDropdown = false; }}>
                        <span>{dt}</span>
                        {#if form.doc_type === dt}<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14" style="color: #6366f1;"><polyline points="20 6 9 17 4 12"></polyline></svg>{/if}
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            </div>

            <div class="form-group">
              <label>สถานะการใช้งาน:</label>
              <label class="toggle-switch">
                <input type="checkbox" bind:checked={form.is_active} />
                <span class="slider"></span>
                <span class="toggle-label">{form.is_active ? 'เปิดใช้งาน (Active)' : 'ปิดใช้งาน (Inactive)'}</span>
              </label>
            </div>

            <div class="form-group">
              <label for="form_max_loops">แก้ไขสูงสุด (Circuit Breaker):</label>
              <input type="number" id="form_max_loops" bind:value={form.max_loops} min="1" max="10" class="form-control" title="จำนวนครั้งสูงสุดที่ให้ Agent วนลูปแก้ไข (ป้องกันลูปค้าง)" />
            </div>

            <div class="form-group span-2">
              <label>คำอธิบายวัตถุประสงค์:</label>
              <textarea bind:value={form.description} rows="2" placeholder="อธิบายวัตถุประสงค์และขอบเขตของเกณฑ์นี้..." class="form-control"></textarea>
            </div>
          </div>
        </div>

        <!-- Checklist Categories -->
        {#each categories as cat}
          {@const catItems = form.items.filter(i => i.category === cat)}
          <div class="editor-card glass-panel category-panel">
            <div class="category-header">
              <div class="cat-title-group">
                <h4>{categoryTitles[cat]}</h4>
                <span class="cat-count">{catItems.length} ข้อ</span>
              </div>
              <button class="btn btn-sm btn-secondary" on:click={() => addItem(cat)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                เพิ่มข้อตรวจในหมวดนี้
              </button>
            </div>

            {#if catItems.length === 0}
              <div class="empty-category">ยังไม่มีรายการประเมินในหมวดนี้ คลิก "เพิ่มข้อตรวจในหมวดนี้" เพื่อเพิ่มข้อแรก</div>
            {:else}
              <div class="items-table-wrapper">
                <table class="items-table">
                  <thead>
                    <tr>
                      <th style="width: 80px;">รหัส</th>
                      <th>รายการประเมิน (Checklist Item)</th>
                      <th style="width: 170px;">📊 ตัวชี้วัด (KPI Indicator)</th>
                      <th style="width: 110px;">Severity</th>
                      <th style="width: 100px; text-align: center;">บังคับผ่าน</th>
                      <th style="width: 60px; text-align: center;">จัดการ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each form.items as item, itemIdx}
                      {#if item.category === cat}
                        <tr>
                          <td>
                            <input type="text" bind:value={item.item_code} class="input-inline code-input" />
                          </td>
                          <td>
                            <textarea bind:value={item.question_text} rows="2" class="input-inline text-input"></textarea>
                          </td>
                          <td>
                            <input 
                              type="text" 
                              bind:value={item.target_metric} 
                              placeholder="เช่น 100% / < 1% Typo" 
                              class="input-inline metric-input" 
                            />
                          </td>
                          <td>
                            <CustomSelect 
                              bind:value={item.severity} 
                              options={severityOptions} 
                              size="sm"
                              width="115px"
                              minWidth="105px"
                            />
                          </td>
                          <td style="text-align: center;">
                            <label class="checkbox-container">
                              <input type="checkbox" bind:checked={item.is_mandatory} />
                              <span class="checkmark"></span>
                            </label>
                          </td>
                          <td style="text-align: center;">
                            <button class="btn-icon-delete" on:click={() => removeItem(itemIdx)} title="ลบรายการ">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2 2v2"></path></svg>
                            </button>
                          </td>
                        </tr>
                      {/if}
                    {/each}
                  </tbody>
                </table>
              </div>
            {/if}
          </div>
        {/each}

        <!-- Final Gate Assessment Rules & Implementation Tips Card -->
        <div class="editor-card glass-panel rules-card">
          <h4>🚦 กฎการตัดสินผลการตรวจ (Final Gate Assessment Rules)</h4>
          <div class="rules-grid">
            <div class="rule-box rule-pass">
              <div class="rule-badge badge-pass">1. PASSED (ผ่านบริบูรณ์)</div>
              <p>ติ๊ก "ผ่าน (Pass)" ทุกข้อที่เกี่ยวข้องทั้งหมดในเอกสาร</p>
            </div>
            <div class="rule-box rule-cond">
              <div class="rule-badge badge-cond">2. CONDITIONAL PASSED (ผ่านแบบมีเงื่อนไข)</div>
              <p>ผ่านทุกข้อในหมวด 1, 2, 4 ทั้งหมด ตกเฉพาะหมวด 3 (คำผิดเล็กน้อย/จัดหน้า)</p>
              <div class="action-note"><strong>แอ็กชัน:</strong> แก้ตามจุดที่ระบุแล้วส่ง Final Clean Copy ได้เลย โดยไม่ต้องส่งตรวจซ้ำ</div>
            </div>
            <div class="rule-box rule-reject">
              <div class="rule-badge badge-reject">3. REJECTED (ไม่ผ่าน - ต้องส่งตรวจใหม่)</div>
              <p>ตกข้อใดข้อหนึ่งในหมวด 1 หรือ หมวด 2 (สาระสำคัญ/ความถูกต้องไม่ผ่าน)</p>
              <div class="action-note"><strong>แอ็กชัน:</strong> แก้ไขและส่งกลับมาตรวจใหม่ในรอบถัดไป</div>
            </div>
          </div>

          <div class="tips-section">
            <h5>💡 ทริคสำหรับการนำไปใช้งานจริง (Implementation Tips)</h5>
            <ul>
              <li><strong>เอกสารร่างแรก (First Draft):</strong> ข้ามหมวดที่ 1 (ตั้งค่าเป็น N/A) แล้วตรวจเฉพาะหมวด 2-4</li>
              <li><strong>เอกสารส่งแก้ (Re-review):</strong> เน้นตรวจหมวดที่ 1 เป็นหลัก ร่วมกับหมวด 4 ข้อ 4.3 (Clean Version)</li>
              <li><strong>ตัดลด/เพิ่มข้อ N/A:</strong> ข้อที่ไม่เกี่ยวข้องกับประเภทเอกสารนั้นๆ (เช่น เอกสาร 1 หน้าไม่มีสารบัญ) ให้กา N/A เพื่อไม่ให้กระทบการประเมินผล</li>
            </ul>
          </div>
        </div>
      {/if}
    </main>
  </div>
</div>

<!-- Help Guide Information Modal -->
{#if showHelpModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="confirm-modal-backdrop" in:fade={{ duration: 180 }} out:fade={{ duration: 150 }} on:click={() => showHelpModal = false}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="glass-panel help-guide-modal-box" in:fly={{ y: 20, duration: 250 }} on:click|stopPropagation>
      <div class="help-modal-header">
        <div class="modal-title-group">
          <div class="info-badge-icon">ℹ️</div>
          <div>
            <h3>คู่มือคำแนะนำการใช้งานและกำหนดเกณฑ์ Exit Criteria</h3>
            <p class="modal-sub">แนวทางการกำหนดเกณฑ์ ตัวชี้วัด (KPI Indicator) และกฎการตัดสินผลการตรวจเอกสาร</p>
          </div>
        </div>
        <button class="btn-close-modal" on:click={() => showHelpModal = false}>✕</button>
      </div>

      <div class="help-modal-body">
        <div class="guide-block">
          <h4>📌 1. Exit Criteria Review Gate คืออะไร?</h4>
          <p>
            คือ **เกณฑ์การผ่านมาตรฐานกลาง** สำหรับประเมินคุณภาพเอกสารก่อนส่งมอบอนุมัติ เพื่อลดข้อผิดพลาดซ้ำซ้อน 
            สร้างมาตรฐานการตรวจเอกสารกลางขององค์กร และทำงานร่วมกับระบบ **AIAgentQA** ในการตรวจประเมินอัตโนมัติ
          </p>
        </div>

        <div class="guide-block">
          <h4>📊 2. ตัวอย่างการกำหนดตัวชี้วัด (KPI Indicator) ตามหัวข้อตรวจ</h4>
          <div class="kpi-grid">
            <div class="kpi-card-box border-blue">
              <span class="kpi-tag tag-blue">เปอร์เซ็นต์ %</span>
              <h5>การแก้ไขข้อผิดพลาด</h5>
              <p>ใช้กับรายการแก้ไข Comment หรือการทำตามโจทย์</p>
              <code>100% Closed, 100% Resolved</code>
            </div>

            <div class="kpi-card-box border-green">
              <span class="kpi-tag tag-green">จำนวนรายการ (Count)</span>
              <h5>จุดที่ไม่ยอมรับข้อผิดพลาด</h5>
              <p>ใช้เมื่อต้องการให้ข้อผิดพลาดใหม่เป็น 0 รายการ</p>
              <code>0 Defect Impact, 0 Ambiguity</code>
            </div>

            <div class="kpi-card-box border-purple">
              <span class="kpi-tag tag-purple">อัตราส่วน (Ratio)</span>
              <h5>คำผิดและการจัดหน้า</h5>
              <p>ใช้กับความเป๊ะของฟอนต์ คำผิด ไวยากรณ์</p>
              <code>&lt; 1% Typo Rate, 100% CI Match</code>
            </div>

            <div class="kpi-card-box border-amber">
              <span class="kpi-tag tag-amber">ความสมบูรณ์</span>
              <h5>Metadata & Attachments</h5>
              <p>ใช้กับการระบุผู้เขียน เวอร์ชัน ประวัติแก้ไข</p>
              <code>100% Header & Metadata</code>
            </div>
          </div>
        </div>

        <div class="guide-block">
          <h4>🚦 3. กฎการตัดสินผลการตรวจ (Final Gate Rules)</h4>
          <div class="rules-mini-list">
            <div class="rule-mini pass">
              <strong>🟢 PASSED (ผ่านบริบูรณ์):</strong> ผ่านข้อตรวจทุกข้อ 100% พร้อมใช้งานอนุมัติทันที
            </div>
            <div class="rule-mini cond">
              <strong>🟡 CONDITIONAL PASSED (ผ่านแบบมีเงื่อนไข):</strong> ผ่านหมวด 1, 2, 4 แต่มีคำผิดหรือการจัดหน้าในหมวด 3 ติดขัดเล็กน้อย สามารถส่ง Final Clean Copy ได้เลย
            </div>
            <div class="rule-mini reject">
              <strong>🔴 REJECTED (ไม่ผ่าน - ต้องส่งตรวจใหม่):</strong> ตกข้อตรวจในหมวด 1 (รายการแก้ไข) หรือหมวด 2 (ความถูกต้อง) ต้องนำไปแก้ไขและส่งตรวจใหม่
            </div>
          </div>
        </div>
      </div>

      <div class="help-modal-footer">
        <button class="btn btn-primary btn-know-more" on:click={() => showHelpModal = false}>
          เข้าใจแล้ว เริ่มต้นใช้งาน
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Custom Glassmorphic Confirmation Modal -->
{#if showConfirmModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="confirm-modal-backdrop" in:fade={{ duration: 200 }} out:fade={{ duration: 150 }} on:click={() => showConfirmModal = false}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="confirm-modal-box glass-panel" in:fly={{ y: 20, duration: 250 }} on:click|stopPropagation>
      <div class="confirm-icon-wrapper type-{confirmModalData.type}">
        {#if confirmModalData.type === 'danger'}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        {:else}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
          </svg>
        {/if}
      </div>
      <h3 class="confirm-title">{confirmModalData.title}</h3>
      <p class="confirm-message">{confirmModalData.message}</p>
      <div class="confirm-actions">
        <button class="btn btn-secondary" on:click={() => showConfirmModal = false}>
          {confirmModalData.cancelText}
        </button>
        <button class="btn btn-confirm-{confirmModalData.type}" on:click={handleConfirmAction}>
          {confirmModalData.confirmText}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .exit-criteria-container {
    display: flex;
    flex-direction: column;
    gap: 20px;
    color: #f1f5f9;
    width: 100%;
    box-sizing: border-box;
    padding-bottom: 40px;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(12px);
    padding: 20px 24px;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .title-with-badge {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-title h2 {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 700;
    color: #ffffff;
  }

  .standard-badge {
    background: linear-gradient(135deg, #6366f1, #a855f7);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 20px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .subtitle {
    margin: 6px 0 0 0;
    font-size: 0.88rem;
    color: #94a3b8;
  }

  .header-actions {
    display: flex;
    gap: 12px;
  }

  .main-layout {
    display: grid;
    grid-template-columns: 320px 1fr;
    gap: 24px;
  }

  /* Sidebar */
  .templates-sidebar {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .filter-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .search-input {
    width: 100%;
    padding: 10px 14px;
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #fff;
    font-size: 0.9rem;
  }

  /* Custom Glassmorphic Dropdown */
  .custom-dropdown-container {
    position: relative;
    width: 100%;
  }

  .custom-dropdown-trigger {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    color: #f8fafc;
    font-size: 0.9rem;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .custom-dropdown-trigger:hover {
    background: rgba(30, 41, 59, 1);
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.15);
  }

  .chevron {
    transition: transform 0.2s ease;
    color: #94a3b8;
  }

  .chevron.open {
    transform: rotate(180deg);
    color: #6366f1;
  }

  .custom-dropdown-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    background: rgba(15, 23, 42, 0.95) !important;
    backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 12px;
    padding: 6px;
    z-index: 100;
    max-height: 260px;
    overflow-y: auto;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6), 0 0 20px rgba(99, 102, 241, 0.15);
  }

  .dropdown-item-opt {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 9px 12px;
    border-radius: 8px;
    font-size: 0.88rem;
    color: #cbd5e1;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .dropdown-item-opt:hover {
    background: rgba(99, 102, 241, 0.2);
    color: #ffffff;
  }

  .dropdown-item-opt.active {
    background: rgba(99, 102, 241, 0.25);
    color: #818cf8;
    font-weight: 600;
  }

  select option {
    background-color: #0f172a;
    color: #f8fafc;
    padding: 8px;
  }

  .template-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: calc(100vh - 220px);
    overflow-y: auto;
  }

  .template-card {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .template-card:hover {
    background: rgba(30, 41, 59, 0.8);
    border-color: rgba(99, 102, 241, 0.4);
    transform: translateY(-2px);
  }

  .template-card.active {
    background: rgba(99, 102, 241, 0.15);
    border-color: #6366f1;
    box-shadow: 0 0 15px rgba(99, 102, 241, 0.2);
  }

  .card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .template-title {
    font-weight: 600;
    font-size: 0.95rem;
    color: #f8fafc;
  }

  .tag {
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 600;
  }
  .tag-purple { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
  .tag-blue { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }

  .template-desc {
    font-size: 0.82rem;
    color: #94a3b8;
    margin: 0 0 12px 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .card-footer-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.78rem;
    color: #64748b;
  }

  /* Main Workspace */
  .editor-workspace {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .glass-panel {
    background: rgba(15, 23, 42, 0.6);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px 24px;
  }

  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .panel-header h3 {
    margin: 0;
    font-size: 1.15rem;
    color: #38bdf8;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .span-2 {
    grid-column: span 2;
  }

  .form-group label {
    display: block;
    font-size: 0.85rem;
    color: #cbd5e1;
    margin-bottom: 6px;
    font-weight: 500;
  }

  .form-control {
    width: 100%;
    padding: 10px 14px;
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    color: #fff;
    font-size: 0.9rem;
  }

  .form-control:focus {
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 10px rgba(99, 102, 241, 0.3);
  }

  /* Category Panels */
  .category-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }

  .cat-title-group {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .cat-title-group h4 {
    margin: 0;
    font-size: 1.05rem;
    color: #f1f5f9;
  }

  .cat-count {
    background: rgba(99, 102, 241, 0.2);
    color: #818cf8;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  /* Table */
  .items-table-wrapper {
    overflow-x: auto;
  }

  .items-table {
    width: 100%;
    border-collapse: collapse;
  }

  .items-table th {
    background: rgba(30, 41, 59, 0.7);
    color: #94a3b8;
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    padding: 10px 12px;
    text-align: left;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .items-table td {
    padding: 8px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    vertical-align: middle;
  }

  .input-inline {
    width: 100%;
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: #fff;
    padding: 6px 10px;
    font-size: 0.88rem;
  }

  .code-input {
    font-weight: 700;
    color: #38bdf8;
    text-align: center;
  }

  .text-input {
    resize: vertical;
  }

  .metric-input {
    color: #a5b4fc;
    font-size: 0.82rem;
    font-weight: 500;
  }

  .select-severity {
    font-weight: 600;
  }
  .class-Critical { color: #ef4444; }
  .class-Major { color: #f59e0b; }
  .class-Minor { color: #10b981; }

  /* Rules & Tips */
  .rules-card h4 {
    margin: 0 0 16px 0;
    font-size: 1.1rem;
    color: #fbbf24;
  }

  .rules-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 20px;
  }

  .rule-box {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .rule-badge {
    font-weight: 700;
    font-size: 0.8rem;
    padding: 4px 10px;
    border-radius: 8px;
    display: inline-block;
  }
  .badge-pass { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
  .badge-cond { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
  .badge-reject { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }

  .rule-box p {
    margin: 0;
    font-size: 0.85rem;
    color: #cbd5e1;
    line-height: 1.4;
  }

  .action-note {
    font-size: 0.78rem;
    color: #94a3b8;
    background: rgba(15, 23, 42, 0.4);
    padding: 6px 10px;
    border-radius: 6px;
    margin-top: 4px;
  }

  .tips-section {
    background: rgba(30, 41, 59, 0.4);
    border-radius: 12px;
    padding: 16px;
  }

  .tips-section h5 {
    margin: 0 0 10px 0;
    color: #38bdf8;
    font-size: 0.95rem;
  }

  .tips-section ul {
    margin: 0;
    padding-left: 20px;
    color: #cbd5e1;
    font-size: 0.85rem;
    line-height: 1.6;
  }

  /* Buttons & Controls */
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.88rem;
    cursor: pointer;
    border: none;
    transition: all 0.2s ease;
  }

  .btn-primary { background: linear-gradient(135deg, #6366f1, #4f46e5); color: #fff; }
  .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }

  .btn-secondary { background: rgba(51, 65, 85, 0.8); color: #e2e8f0; border: 1px solid rgba(255, 255, 255, 0.1); }
  .btn-secondary:hover { background: rgba(71, 85, 105, 0.9); }

  .btn-success { background: linear-gradient(135deg, #10b981, #059669); color: #fff; }
  .btn-success:hover { opacity: 0.9; transform: translateY(-1px); }

  .btn-sm { padding: 6px 12px; font-size: 0.8rem; }

  .btn-icon-delete, .icon-btn-danger {
    background: transparent;
    border: none;
    color: #ef4444;
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: background 0.2s;
  }

  .btn-icon-delete:hover, .icon-btn-danger:hover {
    background: rgba(239, 68, 68, 0.2);
  }

  /* Toggle Switch */
  .toggle-switch {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    user-select: none;
    padding: 8px 14px;
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    width: 100%;
    box-sizing: border-box;
  }
  .toggle-switch input { display: none; }
  .slider {
    display: inline-block;
    flex-shrink: 0;
    width: 46px;
    height: 24px;
    background-color: #334155;
    border-radius: 24px;
    position: relative;
    transition: background-color 0.3s ease;
  }
  .slider:before {
    content: "";
    position: absolute;
    height: 18px;
    width: 18px;
    left: 3px;
    top: 3px;
    background-color: #ffffff;
    border-radius: 50%;
    transition: transform 0.3s ease;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  }
  input:checked + .slider { background-color: #10b981; }
  input:checked + .slider:before { transform: translateX(22px); }
  .toggle-label { font-size: 0.9rem; font-weight: 500; color: #e2e8f0; }

  /* Custom Checkbox */
  .checkbox-container {
    display: inline-block;
    position: relative;
    cursor: pointer;
    font-size: 16px;
    user-select: none;
  }
  .checkbox-container input { position: absolute; opacity: 0; cursor: pointer; height: 0; width: 0; }
  .checkmark {
    display: block;
    height: 20px;
    width: 20px;
    background-color: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
  }
  .checkbox-container:hover input ~ .checkmark { background-color: #334155; }
  .checkbox-container input:checked ~ .checkmark { background-color: #6366f1; border-color: #6366f1; }
  .checkmark:after {
    content: "";
    position: absolute;
    display: none;
  }
  .checkbox-container input:checked ~ .checkmark:after { display: block; }
  .checkbox-container .checkmark:after {
    left: 7px;
    top: 3px;
    width: 5px;
    height: 10px;
    border: solid white;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
  }

  .empty-state, .loading-state, .empty-category, .loading-overlay {
    text-align: center;
    padding: 30px;
    color: #94a3b8;
    font-size: 0.9rem;
  }

  /* Confirmation Modal */
  .confirm-modal-backdrop {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(5, 5, 10, 0.75);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .confirm-modal-box {
    background: rgba(15, 23, 42, 0.95) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 20px;
    padding: 28px 32px;
    width: 100%;
    max-width: 440px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), 0 0 30px rgba(99, 102, 241, 0.15);
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }

  .confirm-icon-wrapper {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 4px;
  }

  .confirm-icon-wrapper.type-danger {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
  }

  .confirm-icon-wrapper.type-warning {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.3);
    box-shadow: 0 0 20px rgba(245, 158, 11, 0.2);
  }

  .confirm-title {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
    color: #ffffff;
  }

  .confirm-message {
    margin: 0;
    font-size: 0.9rem;
    color: #cbd5e1;
    line-height: 1.5;
  }

  .confirm-actions {
    display: flex;
    gap: 12px;
    width: 100%;
    justify-content: center;
    margin-top: 8px;
  }

  .confirm-actions .btn {
    flex: 1;
    justify-content: center;
  }

  .btn-confirm-danger {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: #ffffff;
    border: none;
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
    cursor: pointer;
  }
  .btn-confirm-danger:hover {
    background: linear-gradient(135deg, #f87171, #ef4444);
    transform: translateY(-1px);
  }

  .btn-confirm-warning {
    background: linear-gradient(135deg, #f59e0b, #d97706);
    color: #ffffff;
    border: none;
    box-shadow: 0 4px 15px rgba(245, 158, 11, 0.4);
    cursor: pointer;
  }
  .btn-confirm-warning:hover {
    background: linear-gradient(135deg, #fbbf24, #f59e0b);
    transform: translateY(-1px);
  }

  /* Information / Help Guide Button & Modal */
  .btn-info-glow {
    background: rgba(56, 189, 248, 0.15);
    border: 1px solid rgba(56, 189, 248, 0.4);
    color: #38bdf8;
    padding: 8px 16px;
    border-radius: 10px;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
  }
  .btn-info-glow:hover {
    background: rgba(56, 189, 248, 0.28);
    color: #ffffff;
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.4);
    transform: translateY(-1px);
  }

  .help-guide-modal-box {
    max-width: 720px;
    width: 90%;
    max-height: 85vh;
    overflow-y: auto;
    background: rgba(15, 23, 42, 0.95) !important;
    border: 1px solid rgba(255, 255, 255, 0.18) !important;
    border-radius: 20px;
    padding: 24px 28px !important;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
  }

  .help-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    padding-bottom: 16px;
    margin-bottom: 20px;
  }

  .modal-title-group {
    display: flex;
    gap: 14px;
    align-items: flex-start;
  }

  .info-badge-icon {
    font-size: 28px;
    line-height: 1;
    background: rgba(56, 189, 248, 0.15);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 10px;
    border-radius: 12px;
  }

  .modal-title-group h3 {
    margin: 0 0 4px 0;
    font-size: 1.25rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .modal-sub {
    margin: 0;
    font-size: 0.85rem;
    color: #94a3b8;
  }

  .btn-close-modal {
    background: none;
    border: none;
    color: #94a3b8;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 6px;
    transition: all 0.2s ease;
  }
  .btn-close-modal:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.1);
  }

  .help-modal-body {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .guide-block h4 {
    margin: 0 0 8px 0;
    font-size: 1rem;
    color: #38bdf8;
  }

  .guide-block p {
    margin: 0;
    font-size: 0.88rem;
    color: #cbd5e1;
    line-height: 1.5;
  }

  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin-top: 10px;
  }

  .kpi-card-box {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 14px;
  }
  .kpi-card-box.border-blue { border-left: 3px solid #38bdf8; }
  .kpi-card-box.border-green { border-left: 3px solid #34d399; }
  .kpi-card-box.border-purple { border-left: 3px solid #a855f7; }
  .kpi-card-box.border-amber { border-left: 3px solid #fbbf24; }

  .kpi-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .tag-blue { background: rgba(56, 189, 248, 0.2); color: #38bdf8; }
  .tag-green { background: rgba(52, 211, 153, 0.2); color: #34d399; }
  .tag-purple { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
  .tag-amber { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }

  .kpi-card-box h5 {
    margin: 0 0 4px 0;
    font-size: 0.9rem;
    color: #f8fafc;
  }

  .kpi-card-box p {
    font-size: 0.8rem;
    color: #94a3b8;
    margin-bottom: 8px;
  }

  .kpi-card-box code {
    display: block;
    background: rgba(15, 23, 42, 0.8);
    color: #a5b4fc;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.78rem;
    font-family: monospace;
  }

  .rules-mini-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 8px;
  }

  .rule-mini {
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 0.84rem;
    line-height: 1.4;
  }
  .rule-mini.pass { background: rgba(16, 185, 129, 0.12); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }
  .rule-mini.cond { background: rgba(245, 158, 11, 0.12); color: #fde047; border: 1px solid rgba(245, 158, 11, 0.3); }
  .rule-mini.reject { background: rgba(239, 68, 68, 0.12); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); }

  .help-modal-footer {
    display: flex;
    justify-content: flex-end;
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .btn-know-more {
    padding: 10px 24px;
    font-weight: 600;
  }
</style>
