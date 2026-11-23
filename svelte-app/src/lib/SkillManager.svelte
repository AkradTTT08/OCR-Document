<script>
  import { onMount, onDestroy, tick } from 'svelte';
  import CustomSelect from './CustomSelect.svelte';
  import ConfirmModal from './ConfirmModal.svelte';
  import { toast } from './toastStore.js';
  import { SKILL_DOC_TYPES } from './constants.js';

  function getAuthHeaders(customHeaders = {}) {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('jwt_token') : null;
    return {
      ...customHeaders,
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
  }

  async function safeParseJson(res) {
    try {
      return await res.json();
    } catch {
      return { error: `เซิร์ฟเวอร์ตอบกลับผิดปกติ (HTTP ${res.status})` };
    }
  }

  // ── Core State ──
  let skills = [];
  let loading = false;
  let saving = false;
  let deleting = false;
  let search = '';
  let filterDocType = '';
  let filterStatus = 'all'; // 'all' | 'active' | 'draft'
  let searchDebounceTimer = null;
  let fetchSeq = 0;

  let activeSkill = null;
  let isEditing = false;
  let editorTab = 'edit'; // 'edit' | 'preview' | 'payload'
  let splitPreview = false;
  let simTargetAgent = 'qa_consult'; // 'qa_consult' | 'doc_creator' | 'mcp'

  // Layout Ergonomics
  let sidebarCollapsed = false;
  let metaExpanded = false; // collapsed by default on existing skills to maximize Prompt Editor height
  let showTemplatesBar = false;
  let showOverflowMenu = false;

  // Modals & Guards
  let showDeleteConfirm = false;
  let showDirtyConfirm = false;
  let pendingNavigationAction = null;
  let pendingTemplate = null;
  let showTemplateConfirm = false;

  // Inline Validation State
  let fieldErrors = { skill_name: '', markdown_instructions: '' };
  let nameInputEl = null;
  let editorTextareaEl = null;

  // Form State
  let form = {
    skill_id: null,
    skill_name: '',
    skill_description: '',
    markdown_instructions: '',
    target_doc_type: 'General',
    version: 1,
    is_active: true,
    created_by: 'Admin',
    usage_count: 0
  };
  let initialFormSnapshot = '';

  const docTypes = SKILL_DOC_TYPES;

  // Remove redundant 'ALL' from filter dropdown so 'ทุกประเภทเอกสาร' is unambiguous
  $: filterDocTypeOptions = [
    { value: '', label: 'ทุกประเภทเอกสาร' },
    ...docTypes.filter((t) => t !== 'ALL').map((t) => ({ value: t, label: t }))
  ];
  $: targetDocTypeOptions = docTypes.map((t) => ({ value: t, label: t }));

  // Standardized Prompt Templates (matched to SKILL_DOC_TYPES)
  const templates = [
    {
      name: 'QA SRS Rule Inspector',
      docType: 'SRS',
      desc: 'ตรวจสอบข้อกำหนด Functional & Non-Functional, Acceptance Criteria และจุดเสี่ยงในเอกสาร SRS',
      instructions: `### มาตรฐานการตรวจสอบเอกสาร SRS (QA Rule Inspection)

1. **ความครบถ้วนของข้อกำหนด (Functional Completeness)**
   - ตรวจสอบว่าทุกโมดูลมีรหัสอ้างอิง (FR / REQ ID), Input, Process, Output และ Business Rules ชัดเจน
   - ตรวจหาคำคลุมเครือ (เช่น "รวดเร็ว", "ใช้งานง่าย", "TBD") ที่ไม่สามารถวัดผลทดสอบได้
2. **เงื่อนไขขอบเขตและกรณีผิดพลาด (Unhappy Path & Edge Cases)**
   - ตรวจสอบว่ามีการระบุ Validation Rules, Error Code และข้อความแจ้งเตือนเมื่อข้อมูลไม่ถูกต้อง
   - ตรวจสอบสิทธิ์การใช้งานตาม Role (RBAC) ของแต่ละหน้าจอ/API
3. **Traceability & Testability**
   - สรุปรายการจุดเสี่ยงที่ต้องเพิ่มเติมเพื่อให้ทีม QA สามารถนำไปเขียน Test Case ได้ครบ 100%`
    },
    {
      name: 'Test Case Coverage Standard',
      docType: 'Test Case',
      desc: 'โครงสร้างการเขียนและตรวจสอบ Test Case ให้ครอบคลุม Positive, Negative, Boundary และ Security',
      instructions: `### มาตรฐาน Test Case Specification

| หัวข้อ | ข้อกำหนดที่ต้องมี |
| --- | --- |
| Test Case ID | รหัสมาตรฐาน เช่น TC-MOD-001 ไม่ซ้ำกัน |
| Pre-conditions | ระบุ Role ผู้ใช้, สถานะข้อมูลตั้งต้น และ Environment |
| Test Steps | ขั้นตอนทีละขั้นชัดเจน พร้อมระบุ Test Data ตัวอย่างจริง |
| Expected Result | ผลลัพธ์ที่ตรวจสอบและวัดผลได้ทั้ง UI และ Database/API |

- [ ] Positive Flow (Happy Path)
- [ ] Validation Error & Boundary Value
- [ ] Duplicate Submission & Authorization Denial`
    },
    {
      name: 'System Architecture & API Reviewer',
      docType: 'SDD',
      desc: 'ตรวจสอบความสอดคล้องของสถาปัตยกรรมระบบ, ER Diagram, Sequence Flow และ REST API Contract',
      instructions: `### เกณฑ์ตรวจสอบเอกสารออกแบบระบบ (SDD)

1. **API Specification**: ต้องระบุ HTTP Method, Endpoint Path, Request/Response Schema และ Error Status Codes (400/401/403/404/409/500)
2. **Database Integrity**: ตรวจสอบ Primary Key, Foreign Key, Index และเงื่อนไขการลบข้อมูล (Cascade / Soft Delete)
3. **Sequence & Mermaid Diagram**: ระบุลำดับการทำงานของระบบและ Exception Flow ด้วย \`\`\`mermaid\` ให้ตรวจสอบได้ง่าย`
    },
    {
      name: 'Executive QA Summary Standard',
      docType: 'QA Report',
      desc: 'สรุปรายงานคุณภาพระบบ, Defect Severity, Risk Assessment และคำแนะนำ Go / No-Go',
      instructions: `### โครงสร้างรายงานสรุปผล QA (Go / No-Go Verdict)

> สรุปผลด้วยความชัดเจนเพื่อให้ Product Owner และทีมพัฒนาตัดสินใจปล่อยระบบได้ทันที

1. **Executive Summary**: สรุปสถานะภาพรวมและคำแนะนำ Go / Conditional Go / No-Go อย่างชัดเจน
2. **Defect Breakdown**: จำแนกตามระดับ Critical / High / Medium / Low พร้อมผลกระทบต่อธุรกิจ
3. **Exit Criteria Verification**: เปรียบเทียบผลทดสอบจริงกับเกณฑ์ผ่านที่กำหนดไว้ในโครงการ`
    }
  ];

  // ── Derived Telemetry & Dirty Tracking ──
  $: currentSnapshot = JSON.stringify({
    skill_name: form.skill_name,
    skill_description: form.skill_description,
    markdown_instructions: form.markdown_instructions,
    target_doc_type: form.target_doc_type,
    is_active: form.is_active,
    created_by: form.created_by
  });
  $: isDirty = isEditing && initialFormSnapshot !== '' && currentSnapshot !== initialFormSnapshot;

  $: instructionsChanged =
    !!form.skill_id &&
    !!activeSkill &&
    (form.markdown_instructions || '').trim() !== (activeSkill.markdown_instructions || '').trim();

  $: activeCount = skills.filter((s) => s.is_active).length;
  $: draftCount = skills.filter((s) => !s.is_active).length;

  $: visibleSkills = skills.filter((s) => {
    if (filterStatus === 'active' && !s.is_active) return false;
    if (filterStatus === 'draft' && s.is_active) return false;
    return true;
  });

  // Bilingual Thai/Latin token estimator (Thai chars tokenize ~1.8 chars/token; Latin ~3.8 chars/token)
  $: estimatedTokens = (() => {
    const txt = form.markdown_instructions || '';
    if (!txt) return 0;
    const thaiMatches = txt.match(/[\u0E00-\u0E7F]/g);
    const thaiLen = thaiMatches ? thaiMatches.length : 0;
    const otherLen = txt.length - thaiLen;
    return Math.ceil(thaiLen / 1.8 + otherLen / 3.8);
  })();

  $: isTokenHeavy = estimatedTokens > 2500;
  $: renderedPreviewHtml = parseMarkdownToHtml(form.markdown_instructions);

  // Saved server active status (for accurate Agent Payload banner)
  $: serverIsActive = Boolean(activeSkill && form.skill_id === activeSkill.skill_id && activeSkill.is_active);

  $: payloadPreviewText = (() => {
    const sName = form.skill_name.trim() || 'Untitled Skill';
    const sType = form.target_doc_type || 'General';
    const sBody = form.markdown_instructions.trim() || '(ยังไม่ได้กรอกเนื้อหา Instructions)';
    if (simTargetAgent === 'doc_creator') {
      return `### Skill / Template Guideline: ${sName} (${sType})\n${sBody}\n\n---\n[QA Document Creation จะแนบบล็อกนี้เข้า System Prompt เพื่อกำหนดโครงสร้างและมาตรฐานเอกสาร]`;
    }
    if (simTargetAgent === 'mcp') {
      return `Tool: qa_consult(project_id="...", skill_id="${form.skill_id || sName}")\n\n--- คำสั่งพิเศษเพิ่มเติมจาก AI Skill ---\n### Skill: ${sName} (${sType})\n${sBody}`;
    }
    return `--- คำสั่งพิเศษเพิ่มเติมจาก AI Skill ---\n### Skill: ${sName} (${sType})\n${sBody}\n\n[QA Consult จะฉีดบล็อกนี้ก่อน Knowledge Base Context เพื่อใช้เป็นเกณฑ์หลักในการตรวจเอกสาร]`;
  })();

  function captureSnapshot() {
    initialFormSnapshot = JSON.stringify({
      skill_name: form.skill_name,
      skill_description: form.skill_description,
      markdown_instructions: form.markdown_instructions,
      target_doc_type: form.target_doc_type,
      is_active: form.is_active,
      created_by: form.created_by
    });
  }

  function clearFieldErrors() {
    fieldErrors = { skill_name: '', markdown_instructions: '' };
  }

  function guardDirty(action) {
    showOverflowMenu = false;
    if (isDirty) {
      pendingNavigationAction = action;
      showDirtyConfirm = true;
    } else {
      action();
    }
  }

  function confirmDiscardAndProceed() {
    showDirtyConfirm = false;
    const act = pendingNavigationAction;
    pendingNavigationAction = null;
    if (typeof act === 'function') act();
  }

  function handleWindowKeydown(e) {
    if (e.key === 'Escape' && showOverflowMenu) {
      showOverflowMenu = false;
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && isEditing) {
      e.preventDefault();
      saveSkill();
    }
  }

  function handleTabKeydown(e) {
    const order = ['edit', 'preview', 'payload'];
    const idx = order.indexOf(editorTab);
    if (idx === -1) return;
    let nextIdx = idx;
    if (e.key === 'ArrowRight') nextIdx = (idx + 1) % order.length;
    else if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + order.length) % order.length;
    else if (e.key === 'Home') nextIdx = 0;
    else if (e.key === 'End') nextIdx = order.length - 1;
    else return;
    e.preventDefault();
    editorTab = order[nextIdx];
    const nextBtn = document.getElementById(`sm-tab-${editorTab}`);
    nextBtn?.focus();
  }

  function insertMarkdownSnippet(snippet) {
    const el = editorTextareaEl;
    if (!el) {
      form.markdown_instructions = `${form.markdown_instructions}${form.markdown_instructions ? '\n\n' : ''}${snippet}`;
      return;
    }
    const start = el.selectionStart ?? form.markdown_instructions.length;
    const end = el.selectionEnd ?? start;
    const before = form.markdown_instructions.slice(0, start);
    const after = form.markdown_instructions.slice(end);
    const needsLead = before.length > 0 && !before.endsWith('\n') ? '\n' : '';
    form.markdown_instructions = `${before}${needsLead}${snippet}${after}`;
    tick().then(() => {
      const cursorPos = start + needsLead.length + snippet.length;
      el.focus();
      el.setSelectionRange(cursorPos, cursorPos);
    });
  }

  // ── API Operations ──
  async function fetchSkills(keepSelectionId = null, forceSyncForm = false) {
    const reqId = ++fetchSeq;
    loading = true;
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      if (filterDocType && filterDocType !== 'ALL') params.set('target_doc_type', filterDocType);

      const res = await fetch(`/api/skills?${params.toString()}`, {
        headers: getAuthHeaders()
      });
      const data = await safeParseJson(res);
      if (reqId !== fetchSeq) return;
      if (res.ok && data.success) {
        skills = (data.skills || []).filter(
          (s) => !s.skill_name?.startsWith('[Exit Criteria]') && !s.skill_name?.includes('Exit Criteria')
        );

        // P0 Safety: Never overwrite unsaved form edits when filtering/searching sidebar
        if (isDirty && !forceSyncForm) {
          if (activeSkill) {
            const refreshed = skills.find((s) => s.skill_id === activeSkill.skill_id);
            if (refreshed) activeSkill = refreshed;
          }
          return;
        }

        const targetId = keepSelectionId || activeSkill?.skill_id;
        if (targetId) {
          const found = skills.find((s) => s.skill_id === targetId);
          if (found) {
            applySkillToForm(found);
            return;
          }
        }
        if (skills.length > 0 && !isEditing) {
          applySkillToForm(skills[0]);
        }
      } else {
        toast(data.error || 'โหลดรายการ AI Skills ไม่สำเร็จ', 'error');
      }
    } catch (e) {
      if (reqId !== fetchSeq) return;
      console.error('Failed to fetch skills:', e);
      toast('เชื่อมต่อเซิร์ฟเวอร์ AI Skills ไม่สำเร็จ', 'error');
    } finally {
      if (reqId === fetchSeq) loading = false;
    }
  }

  function onSearchInput() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => fetchSkills(), 240);
  }

  function clearSearchOnly() {
    clearTimeout(searchDebounceTimer);
    search = '';
    fetchSkills();
  }

  function clearAllFilters() {
    clearTimeout(searchDebounceTimer);
    search = '';
    filterDocType = '';
    filterStatus = 'all';
    fetchSkills();
  }

  function applySkillToForm(skill) {
    activeSkill = skill;
    isEditing = true;
    metaExpanded = false; // Collapsed by default on existing skills for maximum prompt authoring height
    showTemplatesBar = false;
    showOverflowMenu = false;
    clearFieldErrors();
    form = {
      skill_id: skill.skill_id,
      skill_name: skill.skill_name || '',
      skill_description: skill.skill_description || '',
      markdown_instructions: skill.markdown_instructions || '',
      target_doc_type: skill.target_doc_type || 'General',
      version: skill.version || 1,
      is_active: skill.is_active !== undefined ? Boolean(skill.is_active) : true,
      created_by: skill.created_by || 'Admin',
      usage_count: skill.usage_count || 0
    };
    captureSnapshot();
  }

  function selectSkill(skill) {
    if (activeSkill?.skill_id === skill.skill_id && isEditing) return;
    guardDirty(() => applySkillToForm(skill));
  }

  function startCreateNew() {
    guardDirty(() => {
      activeSkill = null;
      isEditing = true;
      editorTab = 'edit';
      metaExpanded = true;
      showTemplatesBar = true;
      showOverflowMenu = false;
      clearFieldErrors();
      form = {
        skill_id: null,
        skill_name: '',
        skill_description: '',
        markdown_instructions: '',
        target_doc_type: 'General',
        version: 1,
        is_active: true,
        created_by: typeof localStorage !== 'undefined' ? (localStorage.getItem('username') || 'Admin') : 'Admin',
        usage_count: 0
      };
      captureSnapshot();
    });
  }

  function duplicateCurrentSkill() {
    showOverflowMenu = false;
    if (!form.skill_name.trim()) return;
    guardDirty(() => {
      activeSkill = null;
      isEditing = true;
      editorTab = 'edit';
      metaExpanded = true;
      clearFieldErrors();
      form = {
        ...form,
        skill_id: null,
        skill_name: `${form.skill_name} (Copy)`.slice(0, 100),
        version: 1,
        is_active: false,
        usage_count: 0
      };
      // Keep marked dirty so clicking away won't silently drop the duplicated draft
      initialFormSnapshot = '__unsaved_draft__';
      toast('คัดลอกเป็นฉบับร่าง (Draft) แล้ว กดบันทึกเพื่อสร้าง Skill ใหม่', 'info');
    });
  }

  function requestApplyTemplate(tpl) {
    if (form.markdown_instructions.trim().length > 0) {
      pendingTemplate = tpl;
      showTemplateConfirm = true;
    } else {
      executeApplyTemplate(tpl);
    }
  }

  function executeApplyTemplate(tpl) {
    if (!tpl) return;
    form.skill_name = form.skill_name.trim() || tpl.name;
    form.target_doc_type = tpl.docType;
    form.skill_description = form.skill_description.trim() || tpl.desc;
    form.markdown_instructions = tpl.instructions;
    editorTab = 'edit';
    showTemplatesBar = false;
    clearFieldErrors();
    toast(`ใส่แม่แบบ "${tpl.name}" แล้ว`, 'success', 2000);
  }

  async function saveSkill() {
    if (saving) return;
    clearFieldErrors();

    const trimmedName = form.skill_name.trim();
    const trimmedMd = form.markdown_instructions.trim();

    if (!trimmedName) {
      fieldErrors = { ...fieldErrors, skill_name: 'กรุณาระบุชื่อ AI Skill' };
      metaExpanded = true;
      await tick();
      nameInputEl?.focus();
      toast('กรุณากรอกชื่อ AI Skill', 'warning');
      return;
    }
    if (/exit\s*criteria/i.test(trimmedName)) {
      fieldErrors = { ...fieldErrors, skill_name: 'ห้ามใช้คำสงวน "Exit Criteria" ในชื่อ AI Skill (จัดการได้ในเมนู Exit Criteria)' };
      metaExpanded = true;
      await tick();
      nameInputEl?.focus();
      return;
    }
    if (!trimmedMd) {
      fieldErrors = { ...fieldErrors, markdown_instructions: 'กรุณาระบุเนื้อหา Markdown Instructions' };
      editorTab = 'edit';
      await tick();
      editorTextareaEl?.focus();
      toast('กรุณากรอกเนื้อหา Markdown Instructions', 'warning');
      return;
    }

    saving = true;
    try {
      const isNew = !form.skill_id;
      const url = isNew ? '/api/skills' : `/api/skills/${encodeURIComponent(form.skill_id)}`;
      const method = isNew ? 'POST' : 'PUT';

      const payload = {
        skill_name: trimmedName,
        skill_description: form.skill_description.trim(),
        markdown_instructions: trimmedMd,
        target_doc_type: form.target_doc_type || 'General',
        version: Number(form.version) || 1,
        is_active: Boolean(form.is_active),
        created_by: form.created_by.trim() || 'Admin',
        auto_bump_version: !isNew
      };

      const res = await fetch(url, {
        method,
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });
      const data = await safeParseJson(res);

      if (res.ok && data.success) {
        const savedId = data.skill_id || form.skill_id;
        toast(
          isNew
            ? 'สร้าง AI Skill ใหม่สำเร็จ'
            : `อัปเดต AI Skill สำเร็จ (v${data.version || form.version})`,
          'success'
        );
        await fetchSkills(savedId, true);
      } else {
        toast(`ข้อผิดพลาด: ${data.error || 'บันทึกไม่สำเร็จ'}`, 'error');
      }
    } catch (e) {
      toast(`เกิดข้อผิดพลาด: ${e.message}`, 'error');
    } finally {
      saving = false;
    }
  }

  function deleteSkill() {
    showOverflowMenu = false;
    if (!form.skill_id) return;
    showDeleteConfirm = true;
  }

  async function confirmDeleteSkill() {
    if (!form.skill_id || deleting) return;
    deleting = true;
    try {
      const res = await fetch(`/api/skills/${encodeURIComponent(form.skill_id)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      const data = await safeParseJson(res);
      if (res.ok && data.success) {
        toast('ลบ AI Skill สำเร็จ', 'success');
        activeSkill = null;
        isEditing = false;
        initialFormSnapshot = '';
        await fetchSkills(null, true);
        if (skills.length === 0) startCreateNew();
      } else {
        toast(`ลบไม่สำเร็จ: ${data.error || 'เกิดข้อผิดพลาด'}`, 'error');
      }
    } catch (e) {
      toast(`เกิดข้อผิดพลาด: ${e.message}`, 'error');
    } finally {
      deleting = false;
    }
  }

  function handleImportSkillMd(event) {
    const input = event.target;
    const file = input?.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      toast('ไฟล์ SKILL.md มีขนาดใหญ่เกิน 2 MB', 'warning');
      input.value = '';
      return;
    }

    const runImport = () => {
      const reader = new FileReader();
      reader.onload = () => {
        const raw = String(reader.result || '').replace(/\r\n/g, '\n');
        let body = raw;
        let parsedName = file.name.replace(/(_skill)?\.(md|txt)$/i, '').replace(/[_-]+/g, ' ').trim();
        let parsedDesc = '';
        let parsedDocType = 'General';
        let parsedVer = 1;
        // Default imported skills to Draft (false) for safe review before publishing
        let parsedActive = false;
        let unknownDocType = '';

        const fmMatch = raw.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
        if (fmMatch) {
          const fm = fmMatch[1];
          body = fmMatch[2].trim();
          const getField = (k) => {
            const m = fm.match(new RegExp(`^${k}\\s*:\\s*(.+)$`, 'mi'));
            return m ? m[1].trim().replace(/^["']|["']$/g, '') : '';
          };
          if (getField('name')) parsedName = getField('name');
          if (getField('description')) parsedDesc = getField('description');
          const dt = getField('target_doc_type');
          if (dt) {
            if (docTypes.includes(dt)) parsedDocType = dt;
            else unknownDocType = dt;
          }
          const ver = parseInt(getField('version'), 10);
          if (!Number.isNaN(ver) && ver >= 1) parsedVer = ver;
          const actStr = getField('is_active').toLowerCase();
          if (actStr === 'true') parsedActive = true;
          else if (actStr === 'false') parsedActive = false;
        }

        const secMatch = body.match(/##\s*Skill Instructions.*?\n+([\s\S]*)$/i);
        if (secMatch && secMatch[1].trim()) {
          body = secMatch[1].trim();
        }

        activeSkill = null;
        isEditing = true;
        editorTab = 'edit';
        metaExpanded = true;
        clearFieldErrors();
        form = {
          skill_id: null,
          skill_name: parsedName.slice(0, 100),
          skill_description: parsedDesc,
          markdown_instructions: body,
          target_doc_type: parsedDocType,
          version: parsedVer,
          is_active: parsedActive,
          created_by: typeof localStorage !== 'undefined' ? (localStorage.getItem('username') || 'Admin') : 'Admin',
          usage_count: 0
        };
        // Keep unsaved state true until user clicks Save
        initialFormSnapshot = '__unsaved_draft__';
        if (unknownDocType) {
          toast(`นำเข้า "${file.name}" แล้ว (ไม่รู้จักประเภท "${unknownDocType}" จึงตั้งเป็น General)`, 'warning', 3500);
        } else {
          toast(`นำเข้า "${file.name}" เป็น Draft แล้ว ตรวจสอบและกดบันทึก`, 'success');
        }
        input.value = '';
      };
      reader.onerror = () => {
        toast('ไม่สามารถอ่านไฟล์ SKILL.md ได้', 'error');
        input.value = '';
      };
      reader.readAsText(file, 'utf-8');
    };

    if (isDirty) {
      pendingNavigationAction = runImport;
      showDirtyConfirm = true;
    } else {
      runImport();
    }
  }

  function downloadSkillMd() {
    showOverflowMenu = false;
    if (!form.skill_name.trim()) return;
    const content = `---
name: "${form.skill_name.replace(/"/g, '\\"')}"
description: "${(form.skill_description || '').replace(/"/g, '\\"')}"
target_doc_type: "${form.target_doc_type || 'General'}"
version: ${form.version || 1}
is_active: ${Boolean(form.is_active)}
created_by: "${(form.created_by || 'Admin').replace(/"/g, '\\"')}"
---

# ${form.skill_name}

${form.skill_description || ''}

## Skill Instructions (SKILL.md)

${form.markdown_instructions}
`;
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${form.skill_name.toLowerCase().replace(/[^a-z0-9\u0E00-\u0E7F]+/g, '_')}_SKILL.md`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function copyPayloadPrompt() {
    try {
      await navigator.clipboard.writeText(payloadPreviewText);
      toast('คัดลอกโครงสร้าง Prompt แล้ว', 'success', 2000);
    } catch {
      toast('คัดลอกไม่สำเร็จ', 'error');
    }
  }

  // ── XSS-Safe Markdown Renderer (supports Nested Lists, Checklists, Blockquotes, Tables, Code, Italic/Bold) ──
  function escapeHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function inlineMd(line) {
    let s = escapeHtml(line);
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    s = s.replace(/`([^`]+)`/g, '<code class="sm-inline-code">$1</code>');
    return s;
  }

  function parseMarkdownToHtml(raw) {
    if (!raw || !raw.trim()) return '<div class="empty-preview">ยังไม่มีเนื้อหา Markdown Instructions</div>';
    const lines = String(raw).split('\n');
    const out = [];
    let inCode = false;
    let codeLang = '';
    let codeBuf = [];
    let inTable = false;
    let tHead = [];
    let tRows = [];

    const flushTable = () => {
      if (!inTable) return;
      let html = '<div class="sm-table-wrap"><table class="sm-table"><thead><tr>';
      tHead.forEach((h) => (html += `<th>${inlineMd(h)}</th>`));
      html += '</tr></thead><tbody>';
      tRows.forEach((row) => {
        html += '<tr>';
        row.forEach((cell) => (html += `<td>${inlineMd(cell)}</td>`));
        html += '</tr>';
      });
      html += '</tbody></table></div>';
      out.push(html);
      inTable = false;
      tHead = [];
      tRows = [];
    };

    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i];
      const leadingSpaces = ln.match(/^(\s*)/)?.[1]?.replace(/\t/g, '  ').length || 0;
      const tr = ln.trim();

      if (tr.startsWith('```')) {
        flushTable();
        if (!inCode) {
          inCode = true;
          codeLang = escapeHtml(tr.slice(3).trim());
          codeBuf = [];
        } else {
          inCode = false;
          out.push(
            `<div class="sm-code-block"><div class="sm-code-lang">${codeLang || 'code'}</div><pre><code>${escapeHtml(codeBuf.join('\n'))}</code></pre></div>`
          );
        }
        continue;
      }
      if (inCode) {
        codeBuf.push(ln);
        continue;
      }

      if (tr.startsWith('|') && tr.endsWith('|')) {
        const cells = tr.slice(1, -1).split('|').map((c) => c.trim());
        if (!inTable) {
          const next = (lines[i + 1] || '').trim();
          if (next.startsWith('|') && /^[|:\s-]+$/.test(next) && next.includes('-')) {
            inTable = true;
            tHead = cells;
            i++;
            continue;
          }
        }
        if (inTable) {
          tRows.push(cells);
          continue;
        }
      } else {
        flushTable();
      }

      const indentPx = Math.min(3, Math.floor(leadingSpaces / 2)) * 18;

      if (tr === '') out.push('<div class="sm-spacer"></div>');
      else if (tr === '---' || tr === '***') out.push('<hr class="sm-hr" />');
      else if (tr.startsWith('> ')) out.push(`<blockquote class="sm-quote">${inlineMd(tr.slice(2))}</blockquote>`);
      else if (tr.startsWith('### ')) out.push(`<h3>${inlineMd(tr.slice(4))}</h3>`);
      else if (tr.startsWith('## ')) out.push(`<h2>${inlineMd(tr.slice(3))}</h2>`);
      else if (tr.startsWith('# ')) out.push(`<h1>${inlineMd(tr.slice(2))}</h1>`);
      else if (/^[-*]\s+\[( |x|X)\]\s+/.test(tr)) {
        const checked = /^[-*]\s+\[(x|X)\]/.test(tr);
        const bodyTxt = tr.replace(/^[-*]\s+\[( |x|X)\]\s+/, '');
        out.push(
          `<div class="sm-check" style="padding-left:${10 + indentPx}px"><span class="sm-chk-box ${checked ? 'checked' : ''}">${checked ? '✓' : ''}</span><span>${inlineMd(bodyTxt)}</span></div>`
        );
      } else if (tr.startsWith('- ') || tr.startsWith('* ')) {
        out.push(`<div class="sm-li" style="padding-left:${14 + indentPx}px">${indentPx > 0 ? '◦' : '•'} ${inlineMd(tr.slice(2))}</div>`);
      } else if (/^\d+\.\s/.test(tr)) {
        const m = tr.match(/^(\d+)\.\s(.*)/);
        out.push(`<div class="sm-ol" style="padding-left:${10 + indentPx}px"><span class="sm-ol-num">${escapeHtml(m[1])}.</span><span>${inlineMd(m[2])}</span></div>`);
      } else {
        out.push(`<p>${inlineMd(tr)}</p>`);
      }
    }
    flushTable();
    if (inCode) {
      out.push(`<div class="sm-code-block"><pre><code>${escapeHtml(codeBuf.join('\n'))}</code></pre></div>`);
    }
    return out.join('\n');
  }

  onMount(() => {
    fetchSkills();
  });

  onDestroy(() => {
    clearTimeout(searchDebounceTimer);
  });
</script>

<svelte:window on:keydown={handleWindowKeydown} on:click={() => { if (showOverflowMenu) showOverflowMenu = false; }} />

<div class="skills-shell" class:sidebar-collapsed={sidebarCollapsed}>
  <!-- ── Left Directory Rail (272px, inert when collapsed) ── -->
  <aside
    class="skills-sidebar"
    class:collapsed={sidebarCollapsed}
    inert={sidebarCollapsed || undefined}
    aria-label="รายการ AI Skills"
  >
    <div class="sidebar-top">
      <div class="title-row">
        <div class="title-wrap">
          <span class="title-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" width="16" height="16" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </span>
          <div class="title-text">
            <span class="sidebar-title">AI Skills Center</span>
            <span class="sidebar-sub">SKILL.md Prompt Registry</span>
          </div>
        </div>
        <div class="title-actions">
          <button type="button" class="btn-new" on:click={startCreateNew} title="สร้าง AI Skill ใหม่">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="13" height="13" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
            <span>สร้าง</span>
          </button>
          <button
            type="button"
            class="btn-rail-toggle"
            title="พับแถบรายการ Skills"
            aria-label="พับแถบรายการ Skills"
            on:click={() => (sidebarCollapsed = true)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
        </div>
      </div>

      <!-- Interactive KPI Filter Chips -->
      <div class="stats-bar" role="group" aria-label="กรองตามสถานะ AI Skill">
        <button
          type="button"
          class="stat-chip"
          class:selected={filterStatus === 'all'}
          aria-pressed={filterStatus === 'all'}
          on:click={() => (filterStatus = 'all')}
        >
          <span class="stat-num">{skills.length}</span>
          <span class="stat-lbl">ทั้งหมด</span>
        </button>
        <button
          type="button"
          class="stat-chip"
          class:selected={filterStatus === 'active'}
          aria-pressed={filterStatus === 'active'}
          on:click={() => (filterStatus = 'active')}
        >
          <span class="stat-num ok">{activeCount}</span>
          <span class="stat-lbl">Active</span>
        </button>
        <button
          type="button"
          class="stat-chip"
          class:selected={filterStatus === 'draft'}
          aria-pressed={filterStatus === 'draft'}
          on:click={() => (filterStatus = 'draft')}
        >
          <span class="stat-num warn">{draftCount}</span>
          <span class="stat-lbl">Draft</span>
        </button>
      </div>

      <!-- Search & DocType Filter -->
      <div class="filter-box">
        <div class="search-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13" aria-hidden="true">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            placeholder="ค้นหาชื่อ Skill หรือ Prompt..."
            aria-label="ค้นหา AI Skill"
            bind:value={search}
            on:input={onSearchInput}
          />
          {#if search}
            <button type="button" class="btn-clear-mini" aria-label="ล้างคำค้นหา" on:click={clearSearchOnly}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          {/if}
        </div>

        <label class="sr-only" for="sm-filter-doctype">กรองตามประเภทเอกสาร</label>
        <CustomSelect
          id="sm-filter-doctype"
          bind:value={filterDocType}
          options={filterDocTypeOptions}
          on:change={() => fetchSkills()}
          width="100%"
        />
      </div>
    </div>

    <!-- Skill List -->
    <div class="skills-list" aria-live="polite">
      {#if loading}
        {#each Array(4) as _, idx}
          <div class="skill-skeleton" style={`--stagger-i:${idx}`}></div>
        {/each}
      {:else if visibleSkills.length === 0}
        <div class="empty-state stage-in">
          <div class="empty-icon-box" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="22" height="22" aria-hidden="true">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
          </div>
          <p>ไม่พบ AI Skill ที่ตรงกับเงื่อนไข</p>
          {#if filterStatus !== 'all' || search || filterDocType}
            <button type="button" class="btn-ghost btn-xs" on:click={clearAllFilters}>
              ล้างตัวกรองทั้งหมด
            </button>
          {/if}
        </div>
      {:else}
        {#each visibleSkills as item, idx (item.skill_id)}
          <div class="skill-card-wrap stagger-item" style={`--stagger-i:${Math.min(idx, 10)}`}>
            <button
              type="button"
              class="skill-card"
              class:active={activeSkill && activeSkill.skill_id === item.skill_id}
              aria-current={activeSkill && activeSkill.skill_id === item.skill_id ? 'true' : undefined}
              on:click={() => selectSkill(item)}
            >
              <div class="card-head">
                <span class="card-name truncate" title={item.skill_name}>
                  <span class="mini-dot" class:is-active={item.is_active} aria-hidden="true"></span>
                  <span class="truncate">{item.skill_name}</span>
                </span>
                <span class="ver-chip">v{item.version}</span>
              </div>
              <p class="card-desc">{item.skill_description || 'ไม่มีคำอธิบาย'}</p>
              <div class="card-meta">
                <span class="tag-doctype">{item.target_doc_type || 'General'}</span>
                <div class="card-meta-right">
                  {#if item.usage_count > 0}
                    <span class="usage-chip" title="จำนวนครั้งที่ถูกใช้สร้างเอกสาร">{item.usage_count} uses</span>
                  {/if}
                  <span class="status-text" class:is-active={item.is_active}>
                    {item.is_active ? 'ACTIVE' : 'DRAFT'}
                  </span>
                </div>
              </div>
            </button>
          </div>
        {/each}
      {/if}
    </div>

    <div class="sidebar-footer">
      <label class="btn-import-md">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <span>นำเข้าไฟล์ SKILL.md</span>
        <input class="sr-only" type="file" accept=".md,.txt,.markdown" on:change={handleImportSkillMd} />
      </label>
    </div>
  </aside>

  <!-- ── Main Skill Studio Workspace ── -->
  <main class="main-editor">
    {#if isEditing}
      {#key form.skill_id || 'new-skill'}
        <div class="studio-surface panel-in">
          <!-- Top Studio Bar (Max 4 tidy controls: Templates, Settings, Overflow Menu, Primary Save) -->
          <header class="editor-header">
            <div class="header-left">
              {#if sidebarCollapsed}
                <button
                  type="button"
                  class="btn-ghost btn-icon-only"
                  title="แสดงแถบรายการ Skills"
                  aria-label="แสดงแถบรายการ Skills"
                  on:click={() => (sidebarCollapsed = false)}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15" aria-hidden="true">
                    <polyline points="9 18 15 12 9 6"></polyline>
                  </svg>
                </button>
              {/if}

              <div class="header-info">
                <div class="header-title-row">
                  <h2 class="truncate">{form.skill_id ? form.skill_name || 'แก้ไข AI Skill' : 'สร้าง AI Skill ใหม่'}</h2>
                  <span class="status-pill" class:is-active={form.is_active}>
                    <span class="status-dot" class:is-active={form.is_active} aria-hidden="true"></span>
                    <span>{form.is_active ? 'ACTIVE' : 'DRAFT'}</span>
                  </span>
                  {#if isDirty}
                    <span class="dirty-pill" role="status" aria-live="polite">ยังไม่บันทึก</span>
                  {/if}
                </div>

                <!-- Compact 1-Line Summary Bar when Metadata is collapsed -->
                <div class="agent-compat-row">
                  <span class="tag-doctype">{form.target_doc_type || 'General'}</span>
                  <span class="ver-pill">
                    v{form.version}{#if instructionsChanged} → v{Number(form.version) + 1}{/if}
                  </span>
                  <span class="meta-sep" aria-hidden="true">·</span>
                  <span class="compat-pill" class:muted={!form.is_active}>QA Consult</span>
                  <span class="compat-pill" class:muted={!form.is_active}>Doc Creator</span>
                  <span class="compat-pill" class:muted={!form.is_active}>MCP</span>
                  {#if form.skill_description && !metaExpanded}
                    <span class="meta-sep" aria-hidden="true">·</span>
                    <span class="sub-info truncate desc-inline" title={form.skill_description}>{form.skill_description}</span>
                  {/if}
                </div>
              </div>
            </div>

            <div class="header-actions">
              <button
                type="button"
                class="btn-ghost btn-xs"
                class:is-toggled={showTemplatesBar}
                aria-expanded={showTemplatesBar}
                on:click={() => (showTemplatesBar = !showTemplatesBar)}
              >
                <span>แม่แบบ QA</span>
              </button>

              <button
                type="button"
                class="btn-ghost btn-xs"
                class:is-toggled={metaExpanded}
                aria-expanded={metaExpanded}
                on:click={() => (metaExpanded = !metaExpanded)}
              >
                <span>ตั้งค่า Skill</span>
                <svg
                  class="chevron-ico"
                  class:rotated={metaExpanded}
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  width="12"
                  height="12"
                  aria-hidden="true"
                >
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              </button>

              {#if form.skill_id}
                <div class="overflow-wrap" on:click|stopPropagation>
                  <button
                    type="button"
                    class="btn-ghost btn-icon-only"
                    aria-label="ตัวเลือกเพิ่มเติม"
                    aria-expanded={showOverflowMenu}
                    aria-haspopup="menu"
                    on:click={() => (showOverflowMenu = !showOverflowMenu)}
                  >
                    <svg viewBox="0 0 24 24" fill="currentColor" width="15" height="15" aria-hidden="true">
                      <circle cx="5" cy="12" r="1.75"></circle>
                      <circle cx="12" cy="12" r="1.75"></circle>
                      <circle cx="19" cy="12" r="1.75"></circle>
                    </svg>
                  </button>
                  {#if showOverflowMenu}
                    <div class="overflow-menu drawer-in" role="menu">
                      <button type="button" class="om-item" role="menuitem" on:click={duplicateCurrentSkill}>
                        คัดลอกเป็น Skill ใหม่ (Draft)
                      </button>
                      <button type="button" class="om-item" role="menuitem" on:click={downloadSkillMd}>
                        ส่งออกเป็นไฟล์ SKILL.md
                      </button>
                      <div class="om-sep" role="separator"></div>
                      <button type="button" class="om-item danger" role="menuitem" on:click={deleteSkill}>
                        ลบ AI Skill นี้
                      </button>
                    </div>
                  {/if}
                </div>
              {/if}

              <button type="button" class="btn-primary" on:click={saveSkill} disabled={saving}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" width="14" height="14" aria-hidden="true">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                <span>{saving ? 'กำลังบันทึก...' : form.skill_id ? 'บันทึกการแก้ไข' : 'สร้าง Skill'}</span>
              </button>
            </div>
          </header>

          <!-- Collapsible Templates Drawer -->
          {#if showTemplatesBar}
            <div class="template-drawer drawer-in">
              <div class="td-head">
                <span class="tpl-title">เลือกแม่แบบ QA Prompt สำเร็จรูป</span>
                <button type="button" class="btn-clear-mini" aria-label="ปิดแถบแม่แบบ" on:click={() => (showTemplatesBar = false)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
              <div class="tpl-grid">
                {#each templates as tpl}
                  <button type="button" class="tpl-card" on:click={() => requestApplyTemplate(tpl)}>
                    <div class="tpl-card-top">
                      <span class="tpl-card-name">{tpl.name}</span>
                      <span class="tag-doctype">{tpl.docType}</span>
                    </div>
                    <p class="tpl-card-desc">{tpl.desc}</p>
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Collapsible 12-Col Metadata Strip (Single Source of Truth for Active/Draft + Read-Only Auto-Version) -->
          {#if metaExpanded}
            <section class="meta-strip drawer-in" aria-label="ข้อมูลพื้นฐานของ AI Skill">
              <div class="meta-grid-12">
                <div class="form-group col-5">
                  <label for="sk-name">ชื่อ Skill <span class="req">*</span></label>
                  <input
                    bind:this={nameInputEl}
                    id="sk-name"
                    type="text"
                    class="form-input"
                    class:input-invalid={!!fieldErrors.skill_name}
                    aria-invalid={!!fieldErrors.skill_name}
                    bind:value={form.skill_name}
                    on:input={() => (fieldErrors = { ...fieldErrors, skill_name: '' })}
                    placeholder="เช่น SRS Rule Inspector"
                  />
                  {#if fieldErrors.skill_name}
                    <span class="field-error" role="alert">{fieldErrors.skill_name}</span>
                  {/if}
                </div>
                <div class="form-group col-3">
                  <label for="sk-doctype">ประเภทเอกสารเป้าหมาย</label>
                  <div class="meta-select-align">
                    <CustomSelect
                      id="sk-doctype"
                      bind:value={form.target_doc_type}
                      options={targetDocTypeOptions}
                      width="100%"
                    />
                  </div>
                </div>
                <div class="form-group col-2">
                  <span class="field-lbl">เวอร์ชัน</span>
                  <div class="readonly-ver-box">
                    <span class="num-font">v{form.version}</span>
                    {#if instructionsChanged}
                      <span class="ver-next num-font">→ v{Number(form.version) + 1}</span>
                    {:else}
                      <span class="ver-auto">Auto</span>
                    {/if}
                  </div>
                </div>
                <div class="form-group col-2">
                  <span class="field-lbl">สถานะ (กดบันทึกเพื่อยืนยัน)</span>
                  <div class="active-switch-box" class:is-active={form.is_active}>
                    <span class="asb-state">{form.is_active ? 'Active' : 'Draft'}</span>
                    <label class="toggle-wrap">
                      <input type="checkbox" bind:checked={form.is_active} aria-label="เปิดใช้งาน Skill นี้" />
                      <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    </label>
                  </div>
                </div>

                <div class="form-group col-9">
                  <label for="sk-desc">คำอธิบายสั้นๆ (Description)</label>
                  <input id="sk-desc" type="text" class="form-input" bind:value={form.skill_description} placeholder="อธิบายหน้าที่และเกณฑ์หลักของ Skill นี้..." />
                </div>
                <div class="form-group col-3">
                  <label for="sk-author">ผู้สร้าง (Author)</label>
                  <input id="sk-author" type="text" class="form-input" bind:value={form.created_by} />
                </div>
              </div>
            </section>
          {/if}

          <!-- 3-Tab Prompt Studio (+ Split View & Markdown Quick Snippets) -->
          <section class="editor-container">
            <div class="editor-tabs-bar">
              <div class="tabs-left-group">
                <div class="editor-tabs" role="tablist" aria-label="มุมมองตัวจัดการ Skill" on:keydown={handleTabKeydown}>
                  <button
                    id="sm-tab-edit"
                    type="button"
                    role="tab"
                    aria-selected={editorTab === 'edit'}
                    aria-controls="sm-panel-edit"
                    tabindex={editorTab === 'edit' ? 0 : -1}
                    class="tab-btn"
                    class:active={editorTab === 'edit'}
                    on:click={() => (editorTab = 'edit')}
                  >
                    แก้ไข Instructions
                  </button>
                  <button
                    id="sm-tab-preview"
                    type="button"
                    role="tab"
                    aria-selected={editorTab === 'preview'}
                    aria-controls="sm-panel-preview"
                    tabindex={editorTab === 'preview' ? 0 : -1}
                    class="tab-btn"
                    class:active={editorTab === 'preview'}
                    on:click={() => (editorTab = 'preview')}
                  >
                    พรีวิว SKILL.md
                  </button>
                  <button
                    id="sm-tab-payload"
                    type="button"
                    role="tab"
                    aria-selected={editorTab === 'payload'}
                    aria-controls="sm-panel-payload"
                    tabindex={editorTab === 'payload' ? 0 : -1}
                    class="tab-btn"
                    class:active={editorTab === 'payload'}
                    on:click={() => (editorTab = 'payload')}
                  >
                    โครงสร้าง Prompt ที่ส่งให้ Agent
                  </button>
                </div>

                {#if editorTab === 'edit'}
                  <div class="md-snippet-bar" role="group" aria-label="แทรกโครงสร้าง Markdown">
                    <button type="button" class="snip-btn" title="แทรกหัวข้อ H3" on:click={() => insertMarkdownSnippet('### หัวข้อเกณฑ์การตรวจสอบ\n')}>H3</button>
                    <button type="button" class="snip-btn" title="แทรกรายการ Checklist" on:click={() => insertMarkdownSnippet('- [ ] เงื่อนไขที่ต้องตรวจสอบ\n')}>Checklist</button>
                    <button type="button" class="snip-btn" title="แทรกตาราง Markdown" on:click={() => insertMarkdownSnippet('| หัวข้อ | เกณฑ์มาตรฐาน |\n| --- | --- |\n| ... | ... |\n')}>Table</button>
                    <button type="button" class="snip-btn" title="แทรก Quote" on:click={() => insertMarkdownSnippet('> ตัวอย่างกฎหรือข้อกำหนดเฉพาะโดเมน\n')}>Quote</button>
                    <button type="button" class="snip-btn" title="แทรกบล็อกโค้ด" on:click={() => insertMarkdownSnippet('```mermaid\ngraph TD\n  A[Start] --> B[End]\n```\n')}>Code</button>
                  </div>
                {/if}
              </div>

              <div class="editor-metrics">
                {#if editorTab === 'edit'}
                  <button
                    type="button"
                    class="btn-ghost btn-xs split-toggle-btn"
                    class:is-toggled={splitPreview}
                    aria-pressed={splitPreview}
                    on:click={() => (splitPreview = !splitPreview)}
                  >
                    Split Preview
                  </button>
                {/if}
                <span class="metric-pill">{form.markdown_instructions.length.toLocaleString()} chars</span>
                <span class="metric-pill" class:token-warn={isTokenHeavy} title={isTokenHeavy ? 'Prompt ค่อนข้างยาว อาจใช้ Token สูงในทุกการเรียก Agent' : 'ประมาณการ Token (คำนวณแยกภาษาไทย/อังกฤษ)'}>
                  ~{estimatedTokens.toLocaleString()} tokens
                </span>
                <span class="metric-pill shortcut">Ctrl+S</span>
              </div>
            </div>

            {#if fieldErrors.markdown_instructions}
              <div class="editor-inline-err" role="alert">{fieldErrors.markdown_instructions}</div>
            {/if}

            {#key editorTab}
              {#if editorTab === 'edit'}
                <div id="sm-panel-edit" role="tabpanel" aria-labelledby="sm-tab-edit" class="edit-panel-wrap tab-in" class:is-split={splitPreview}>
                  <textarea
                    bind:this={editorTextareaEl}
                    class="code-editor"
                    aria-label="เนื้อหา Markdown Instructions ของ AI Skill"
                    bind:value={form.markdown_instructions}
                    on:input={() => (fieldErrors = { ...fieldErrors, markdown_instructions: '' })}
                    placeholder="# คู่มือการทำงานสำหรับ AI Agent&#10;&#10;1. กำหนดเกณฑ์ตรวจสอบหรือโครงสร้างเอกสารที่ต้องการ..."
                  ></textarea>
                  {#if splitPreview}
                    <div class="split-preview-pane">
                      <div class="split-cap">LIVE PREVIEW</div>
                      <div class="markdown-rendered split-md-pad">
                        {@html renderedPreviewHtml}
                      </div>
                    </div>
                  {/if}
                </div>
              {:else if editorTab === 'preview'}
                <div id="sm-panel-preview" role="tabpanel" aria-labelledby="sm-tab-preview" class="preview-box tab-in">
                  <div class="frontmatter">
                    <div>---</div>
                    <div>name: "{form.skill_name}"</div>
                    <div>description: "{form.skill_description}"</div>
                    <div>target_doc_type: "{form.target_doc_type}"</div>
                    <div>version: {form.version}</div>
                    <div>is_active: {form.is_active}</div>
                    <div>created_by: "{form.created_by}"</div>
                    <div>---</div>
                  </div>
                  <div class="markdown-rendered">
                    {@html renderedPreviewHtml}
                  </div>
                </div>
              {:else}
                <div id="sm-panel-payload" role="tabpanel" aria-labelledby="sm-tab-payload" class="simulate-box tab-in">
                  <div class="sim-toolbar">
                    <div class="sim-agent-pills" role="group" aria-label="เลือก Agent ที่รับ Prompt">
                      <button type="button" class="sp-btn" class:active={simTargetAgent === 'qa_consult'} aria-pressed={simTargetAgent === 'qa_consult'} on:click={() => (simTargetAgent = 'qa_consult')}>QA Consult</button>
                      <button type="button" class="sp-btn" class:active={simTargetAgent === 'doc_creator'} aria-pressed={simTargetAgent === 'doc_creator'} on:click={() => (simTargetAgent = 'doc_creator')}>QA Doc Creator</button>
                      <button type="button" class="sp-btn" class:active={simTargetAgent === 'mcp'} aria-pressed={simTargetAgent === 'mcp'} on:click={() => (simTargetAgent = 'mcp')}>MCP Server</button>
                    </div>
                    <button type="button" class="btn-ghost btn-xs" on:click={copyPayloadPrompt}>คัดลอก Payload</button>
                  </div>

                  {#if !form.skill_id || isDirty}
                    <div class="sim-warn" role="status" aria-live="polite">
                      <strong>ยังไม่ได้บันทึกการเปลี่ยนแปลงล่าสุด</strong> — กรุณากด <strong>บันทึก</strong> เพื่อให้สถานะและเนื้อหานี้มีผลจริงบนเซิร์ฟเวอร์ (สถานะปัจจุบันบนเซิร์ฟเวอร์: {form.skill_id ? (serverIsActive ? 'ACTIVE' : 'DRAFT') : 'ยังไม่สร้าง'})
                    </div>
                  {:else if !serverIsActive}
                    <div class="sim-warn" role="status" aria-live="polite">
                      Skill นี้อยู่ในสถานะ <strong>Draft (ปิดใช้งาน)</strong> — Agent จริงจะไม่เรียกใช้จนกว่าจะเปิดสถานะ <strong>Active</strong> และกดบันทึก
                    </div>
                  {:else}
                    <div class="sim-ok" role="status" aria-live="polite">
                      สถานะบนเซิร์ฟเวอร์: <strong>Active</strong> — Agent <strong>{simTargetAgent === 'qa_consult' ? 'QA Consult' : simTargetAgent === 'doc_creator' ? 'QA Document Creation' : 'MCP Server'}</strong> จะได้รับบล็อกคำสั่งด้านล่างนี้ทันทีเมื่อถูกเลือก
                    </div>
                  {/if}

                  <pre class="sim-pre"><code>{payloadPreviewText}</code></pre>
                </div>
              {/if}
            {/key}
          </section>
        </div>
      {/key}
    {:else}
      <div class="no-selection stage-in">
        <div class="empty-icon-box lg" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="30" height="30" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
          </svg>
        </div>
        <h3>เลือก AI Skill เพื่อแก้ไขหรือสร้างใหม่</h3>
        <p>คลิกเลือกจากรายการด้านซ้าย หรือกด "+ สร้าง" เพื่อสร้างคู่มือสมองกล (SKILL.md) สำหรับทีม QA</p>
        <button type="button" class="btn-primary" on:click={startCreateNew}>+ สร้าง AI Skill ใหม่</button>
      </div>
    {/if}
  </main>
</div>

<ConfirmModal
  bind:open={showDeleteConfirm}
  danger={true}
  title="ยืนยันการลบ AI Skill"
  message={`คุณต้องการลบ Skill "${form.skill_name}" ออกจากระบบถาวรใช่หรือไม่?`}
  confirmText="ลบ Skill ถาวร"
  on:confirm={confirmDeleteSkill}
/>

<ConfirmModal
  bind:open={showDirtyConfirm}
  danger={false}
  title="มีการแก้ไขที่ยังไม่บันทึก"
  message="คุณแก้ไขข้อมูล AI Skill ค้างไว้ หากเปลี่ยนหน้าตอนนี้การแก้ไขทั้งหมดจะหายไป ต้องการละทิ้งหรือไม่?"
  confirmText="ละทิ้งการแก้ไข"
  cancelText="กลับไปแก้ไขต่อ"
  on:confirm={confirmDiscardAndProceed}
/>

<ConfirmModal
  bind:open={showTemplateConfirm}
  danger={false}
  title="แทนที่เนื้อหาด้วยแม่แบบ QA"
  message={`ต้องการแทนที่เนื้อหา Instructions ปัจจุบันด้วยแม่แบบ "${pendingTemplate?.name || ''}" ใช่หรือไม่?`}
  confirmText="ใช้แม่แบบนี้"
  cancelText="ยกเลิก"
  on:confirm={() => {
    const tpl = pendingTemplate;
    pendingTemplate = null;
    executeApplyTemplate(tpl);
  }}
/>

<style>
  /* ── Spectra QA "The Spectrum Command Deck" Layout ── */
  .skills-shell {
    display: flex;
    height: 100%;
    width: 100%;
    background: transparent;
    color: var(--text-main);
    overflow: hidden;
  }

  .num-font {
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
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

  /* ── Left Directory Rail (272px) ── */
  .skills-sidebar {
    width: 272px;
    flex-shrink: 0;
    background: rgba(12, 15, 26, 0.72);
    border-right: 1px solid var(--glass-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.28s cubic-bezier(0.16, 1, 0.3, 1), max-height 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease, border-color 0.2s ease;
  }
  .skills-sidebar.collapsed {
    width: 0;
    opacity: 0;
    border-right-color: transparent;
    pointer-events: none;
  }

  .sidebar-top {
    padding: 14px 12px 12px;
    border-bottom: 1px solid var(--glass-border);
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex-shrink: 0;
  }

  .title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }
  .title-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .title-icon {
    width: 32px;
    height: 32px;
    border-radius: var(--radius-md);
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: var(--primary-soft-text);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .title-text { min-width: 0; }
  .sidebar-title {
    display: block;
    font-family: var(--font-en);
    font-weight: 700;
    font-size: 14px;
    color: var(--text-main);
    line-height: 1.2;
  }
  .sidebar-sub {
    display: block;
    font-family: var(--font-en);
    font-size: 10px;
    color: var(--text-muted);
  }

  .title-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }
  .btn-new {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--gradient-main);
    color: var(--text-main);
    border: 1px solid rgba(255, 255, 255, 0.16);
    padding: 6px 10px;
    border-radius: var(--radius-md);
    font-family: inherit;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.18s ease, filter 0.18s ease;
  }
  .btn-new:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(99, 102, 241, 0.48);
    filter: brightness(1.06);
  }

  .btn-rail-toggle {
    min-width: 32px;
    min-height: 32px;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease;
  }
  .btn-rail-toggle:hover { background: rgba(255, 255, 255, 0.1); color: var(--text-main); }

  /* Interactive KPI Chips */
  .stats-bar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }
  .stat-chip {
    background: rgba(18, 20, 28, 0.65);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 7px 6px;
    text-align: center;
    cursor: pointer;
    font-family: inherit;
    transition: border-color 0.18s ease, background-color 0.18s ease, transform 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .stat-chip:hover {
    border-color: var(--glass-border-light);
    background: rgba(25, 29, 46, 0.85);
    transform: translateY(-1px);
  }
  .stat-chip.selected {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(99, 102, 241, 0.48);
  }
  .stat-num {
    display: block;
    font-family: var(--font-en);
    font-size: 16px;
    font-weight: 700;
    color: var(--primary-soft-text);
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }
  .stat-num.ok { color: var(--success-soft-text); }
  .stat-num.warn { color: var(--warning-soft-text); }
  .stat-lbl { font-size: 10.5px; color: var(--text-muted); }

  .filter-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .search-wrap {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 6px 10px;
    background: rgba(8, 10, 18, 0.6);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
  }
  .search-wrap:focus-within {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22);
  }
  .search-wrap svg { color: var(--text-muted); flex-shrink: 0; }
  .search-wrap input {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main);
    font-family: inherit;
    font-size: 12.5px;
  }

  .btn-clear-mini {
    min-width: 32px;
    min-height: 32px;
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
  }
  .btn-clear-mini:hover { background: rgba(255, 255, 255, 0.1); color: var(--text-main); }

  .skills-list {
    flex: 1;
    overflow-y: auto;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 7px;
  }

  .skill-card {
    position: relative;
    width: 100%;
    text-align: left;
    padding: 11px 12px 10px 14px;
    background: rgba(18, 20, 28, 0.52);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    color: var(--text-main);
    font-family: inherit;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .skill-card::before {
    content: '';
    position: absolute;
    left: 0;
    top: 16%;
    bottom: 16%;
    width: 4px;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    background: linear-gradient(180deg, var(--primary), var(--secondary));
    opacity: 0;
    transform: scaleY(0.35);
    transition: opacity 0.2s ease, transform 0.24s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .skill-card:hover {
    background: rgba(24, 28, 46, 0.88);
    border-color: rgba(99, 102, 241, 0.38);
    transform: translateY(-1px);
  }
  .skill-card.active {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.45);
  }
  .skill-card.active::before { opacity: 1; transform: scaleY(1); }

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }
  .card-name {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
    font-weight: 600;
    font-size: 13px;
    color: var(--text-main);
  }
  .mini-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--warning);
    flex-shrink: 0;
  }
  .mini-dot.is-active { background: var(--success); }

  .card-desc {
    margin: 0 0 8px;
    font-size: 11.5px;
    color: var(--text-muted);
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .card-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
  }
  .card-meta-right { display: flex; align-items: center; gap: 7px; }
  .tag-doctype {
    font-family: var(--font-en);
    font-size: 10.5px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: var(--primary-soft-text-hover);
    flex-shrink: 0;
  }
  .usage-chip, .ver-chip, .ver-pill {
    font-family: var(--font-en);
    font-size: 10.5px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .usage-chip { color: var(--accent); }
  .status-text {
    font-family: var(--font-en);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: var(--warning-soft-text);
  }
  .status-text.is-active { color: var(--success-soft-text); }

  .sidebar-footer {
    padding: 10px 12px;
    border-top: 1px solid var(--glass-border);
    flex-shrink: 0;
  }
  .btn-import-md {
    position: relative;
    width: 100%;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    padding: 9px 12px;
    border-radius: var(--radius-md);
    border: 1px dashed rgba(99, 102, 241, 0.42);
    background: rgba(99, 102, 241, 0.07);
    color: var(--primary-soft-text-hover);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
  }
  .btn-import-md:hover {
    background: rgba(99, 102, 241, 0.16);
    border-color: var(--primary);
    color: var(--text-main);
  }
  .btn-import-md:focus-within {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }

  /* ── Main Studio Workspace ── */
  .main-editor {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 14px 18px;
  }

  .studio-surface {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background: rgba(14, 17, 27, 0.78);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--glass-shadow);
    overflow: hidden;
  }

  .editor-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    padding: 12px 18px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(10, 12, 20, 0.6);
    flex-shrink: 0;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    flex: 1;
  }
  .header-info { min-width: 0; flex: 1; }
  .header-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }
  .editor-header h2 {
    margin: 0;
    font-size: 16.5px;
    font-weight: 700;
    color: var(--text-main);
    max-width: 460px;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: var(--radius-lg);
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.35);
    font-family: var(--font-en);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    color: var(--warning-soft-text);
    flex-shrink: 0;
  }
  .status-pill.is-active {
    background: rgba(16, 185, 129, 0.12);
    border-color: rgba(16, 185, 129, 0.35);
    color: var(--success-soft-text);
  }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--warning);
  }
  .status-dot.is-active {
    background: var(--success);
    box-shadow: 0 0 8px rgba(16, 185, 129, 0.55);
  }

  .dirty-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: var(--radius-lg);
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: var(--warning-soft-text);
  }
  .agent-compat-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    min-width: 0;
  }
  .meta-sep { color: var(--text-muted); opacity: 0.5; }
  .sub-info { font-size: 11.5px; color: var(--text-muted); }
  .desc-inline { max-width: 340px; }
  .compat-pill {
    font-family: var(--font-en);
    font-size: 10px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: var(--radius-lg);
    background: rgba(6, 182, 212, 0.12);
    border: 1px solid rgba(6, 182, 212, 0.28);
    color: var(--accent);
    transition: opacity 0.2s ease;
  }
  .compat-pill.muted { opacity: 0.38; }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .chevron-ico { transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1); }
  .chevron-ico.rotated { transform: rotate(180deg); }

  /* Overflow Dropdown */
  .overflow-wrap { position: relative; }
  .overflow-menu {
    position: absolute;
    top: calc(100% + 6px);
    right: 0;
    min-width: 210px;
    background: var(--bg);
    border: 1px solid var(--glass-border-light);
    border-radius: var(--radius-md);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
    padding: 6px;
    z-index: 40;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .om-item {
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    color: var(--text-main);
    font-family: inherit;
    font-size: 12.5px;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;
  }
  .om-item:hover { background: rgba(255, 255, 255, 0.08); }
  .om-item.danger { color: var(--danger-soft-text); }
  .om-item.danger:hover { background: rgba(244, 63, 94, 0.16); }
  .om-sep { height: 1px; background: var(--glass-border); margin: 4px 2px; }

  /* Buttons */
  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--gradient-main);
    color: var(--text-main);
    border: 1px solid rgba(255, 255, 255, 0.16);
    padding: 8px 16px;
    border-radius: var(--radius-md);
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.18s ease, filter 0.18s ease;
  }
  .btn-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.48);
    filter: brightness(1.06);
  }
  .btn-primary:active:not(:disabled) { transform: translateY(0); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-main);
    padding: 7px 11px;
    border-radius: var(--radius-md);
    font-family: inherit;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
  }
  .btn-ghost:hover:not(:disabled) { background: rgba(255, 255, 255, 0.1); border-color: var(--glass-border-light); }
  .btn-ghost.is-toggled {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.45);
    color: var(--text-main);
  }
  .btn-xs { padding: 6px 10px; font-size: 11.5px; border-radius: var(--radius-sm); }
  .btn-icon-only { padding: 7px; min-width: 34px; min-height: 34px; justify-content: center; border-radius: var(--radius-sm); }

  /* Collapsible Template Drawer */
  .template-drawer {
    padding: 12px 18px 14px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(99, 102, 241, 0.06);
    flex-shrink: 0;
  }
  .td-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .tpl-title { font-size: 12px; font-weight: 600; color: var(--primary-soft-text-hover); }
  .tpl-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }
  .tpl-card {
    text-align: left;
    padding: 10px 12px;
    border-radius: var(--radius-md);
    background: rgba(14, 17, 28, 0.8);
    border: 1px solid var(--glass-border);
    color: var(--text-main);
    font-family: inherit;
    cursor: pointer;
    transition: border-color 0.18s ease, transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.18s ease;
  }
  .tpl-card:hover {
    border-color: var(--primary);
    background: rgba(24, 28, 48, 0.92);
    transform: translateY(-2px);
  }
  .tpl-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    margin-bottom: 4px;
  }
  .tpl-card-name { font-size: 12px; font-weight: 600; color: var(--text-main); }
  .tpl-card-desc {
    margin: 0;
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Collapsible 12-Col Metadata Strip */
  .meta-strip {
    padding: 14px 18px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(10, 11, 18, 0.45);
    flex-shrink: 0;
  }
  .meta-grid-12 {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 10px 12px;
    align-items: start;
  }
  .col-2 { grid-column: span 2; }
  .col-3 { grid-column: span 3; }
  .col-5 { grid-column: span 5; }
  .col-9 { grid-column: span 9; }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-width: 0;
  }
  .form-group label, .field-lbl {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 600;
  }
  .req { color: var(--danger); }
  .form-input {
    width: 100%;
    height: 38px;
    box-sizing: border-box;
    padding: 0 12px;
    background: rgba(8, 10, 18, 0.7);
    border: 1px solid var(--glass-border-light);
    border-radius: var(--radius-md);
    color: var(--text-main);
    font-family: inherit;
    font-size: 13px;
    outline: none;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
  }
  .form-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22); }
  .form-input.input-invalid { border-color: var(--danger); box-shadow: 0 0 0 2px rgba(244, 63, 94, 0.22); }
  .field-error { font-size: 11px; color: var(--danger-soft-text); }

  .meta-select-align :global(.select-trigger-btn) {
    min-height: 38px;
    height: 38px;
    border-color: var(--glass-border-light);
    box-shadow: none;
  }

  .readonly-ver-box {
    height: 38px;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 12px;
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border);
    font-size: 13px;
    font-weight: 600;
    color: var(--text-main);
  }
  .ver-next { font-size: 11.5px; color: var(--warning-soft-text); }
  .ver-auto { font-family: var(--font-en); font-size: 10.5px; color: var(--text-muted); }

  .active-switch-box {
    height: 38px;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 0 12px;
    border-radius: var(--radius-md);
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border-light);
    transition: background-color 0.18s ease, border-color 0.18s ease;
  }
  .active-switch-box.is-active {
    background: rgba(16, 185, 129, 0.08);
    border-color: rgba(16, 185, 129, 0.35);
  }
  .asb-state { font-family: var(--font-en); font-size: 12px; font-weight: 600; color: var(--text-main); }

  .toggle-wrap { position: relative; display: inline-flex; cursor: pointer; }
  .toggle-wrap input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .toggle-track {
    width: 38px;
    height: 20px;
    border-radius: var(--radius-lg);
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.16);
    position: relative;
    transition: background-color 0.2s ease;
  }
  .toggle-wrap input:focus-visible + .toggle-track { outline: 2px solid var(--primary); outline-offset: 2px; }
  .toggle-wrap input:checked + .toggle-track { background: linear-gradient(135deg, var(--success), var(--primary)); }
  .toggle-thumb {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--text-main);
    position: absolute;
    top: 2px;
    left: 2px;
    transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb { transform: translateX(18px); }

  /* 3-Tab Prompt Studio */
  .editor-container {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .editor-tabs-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    padding: 8px 16px;
    background: rgba(8, 10, 18, 0.58);
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }
  .tabs-left-group {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .editor-tabs { display: flex; gap: 5px; }
  .tab-btn {
    padding: 6px 13px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
  }
  .tab-btn:hover { color: var(--text-main); background: rgba(255, 255, 255, 0.05); }
  .tab-btn.active {
    background: rgba(99, 102, 241, 0.2);
    border-color: rgba(99, 102, 241, 0.45);
    color: var(--text-main);
    font-weight: 600;
  }

  .md-snippet-bar {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding-left: 10px;
    border-left: 1px solid var(--glass-border);
  }
  .snip-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-family: var(--font-en);
    font-size: 11px;
    font-weight: 600;
    padding: 4px 8px;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .snip-btn:hover { background: rgba(99, 102, 241, 0.18); border-color: rgba(99, 102, 241, 0.4); color: var(--text-main); }

  .editor-metrics { display: flex; align-items: center; gap: 6px; }
  .metric-pill {
    font-family: var(--font-en);
    font-size: 11px;
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    padding: 3px 9px;
    border-radius: var(--radius-sm);
    font-variant-numeric: tabular-nums;
  }
  .metric-pill.shortcut { color: var(--primary-soft-text); }
  .metric-pill.token-warn {
    color: var(--warning-soft-text);
    border-color: rgba(245, 158, 11, 0.45);
    background: rgba(245, 158, 11, 0.12);
  }

  .editor-inline-err {
    padding: 8px 18px;
    background: rgba(244, 63, 94, 0.12);
    border-bottom: 1px solid rgba(244, 63, 94, 0.35);
    color: var(--danger-soft-text);
    font-size: 12px;
  }

  .edit-panel-wrap {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 1fr;
  }
  .edit-panel-wrap.is-split {
    grid-template-columns: 1fr 1fr;
  }

  .code-editor {
    width: 100%;
    height: 100%;
    box-sizing: border-box;
    padding: 18px 20px;
    background: rgba(6, 8, 15, 0.55);
    color: var(--text-main);
    border: none;
    font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Prompt', monospace;
    font-size: 13px;
    line-height: 1.72;
    resize: none;
    outline: none;
    transition: box-shadow 0.18s ease;
  }
  .code-editor:focus-visible {
    box-shadow: inset 0 0 0 2px var(--primary);
  }

  .split-preview-pane {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow-y: auto;
    border-left: 1px solid var(--glass-border);
    background: rgba(10, 12, 22, 0.5);
  }
  .split-cap {
    padding: 8px 16px;
    font-family: var(--font-en);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    background: rgba(8, 10, 18, 0.5);
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }
  .split-md-pad { padding: 16px 20px; }

  .preview-box, .simulate-box {
    flex: 1;
    overflow-y: auto;
    padding: 18px 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .frontmatter {
    background: rgba(8, 10, 18, 0.72);
    border: 1px solid var(--glass-border);
    padding: 12px 16px;
    border-radius: var(--radius-md);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12px;
    color: var(--primary-soft-text);
    line-height: 1.55;
  }
  .markdown-rendered { font-size: 14px; line-height: 1.7; color: var(--text-main); }
  .markdown-rendered :global(h1) { font-size: 19px; color: var(--primary-soft-text-hover); margin: 12px 0 8px; }
  .markdown-rendered :global(h2) { font-size: 16.5px; color: var(--text-main); margin: 12px 0 6px; }
  .markdown-rendered :global(h3) { font-size: 14.5px; color: var(--text-main); margin: 10px 0 5px; }
  .markdown-rendered :global(p) { margin: 0 0 8px; }
  .markdown-rendered :global(.sm-spacer) { height: 6px; }
  .markdown-rendered :global(.sm-hr) { border: none; border-top: 1px solid var(--glass-border); margin: 12px 0; }
  .markdown-rendered :global(.sm-quote) {
    margin: 8px 0;
    padding: 9px 14px;
    border: 1px solid rgba(99, 102, 241, 0.28);
    background: rgba(99, 102, 241, 0.08);
    border-radius: var(--radius-md);
    color: var(--primary-soft-text-hover);
  }
  .markdown-rendered :global(.sm-li) { margin-bottom: 4px; }
  .markdown-rendered :global(.sm-ol) { display: flex; gap: 8px; margin-bottom: 4px; }
  .markdown-rendered :global(.sm-ol-num) { color: var(--primary-soft-text); font-weight: 600; }
  .markdown-rendered :global(.sm-check) { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
  .markdown-rendered :global(.sm-chk-box) {
    width: 15px;
    height: 15px;
    border-radius: 4px;
    border: 1px solid var(--glass-border-light);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    flex-shrink: 0;
  }
  .markdown-rendered :global(.sm-chk-box.checked) {
    background: rgba(16, 185, 129, 0.25);
    border-color: var(--success);
    color: var(--success-soft-text);
  }
  .markdown-rendered :global(.sm-inline-code) {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: var(--primary-soft-text-hover);
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12.5px;
  }
  .markdown-rendered :global(.sm-code-block) {
    background: var(--bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    margin: 10px 0;
    overflow-x: auto;
  }
  .markdown-rendered :global(.sm-code-lang) {
    font-family: var(--font-en);
    font-size: 11px;
    color: var(--primary-soft-text);
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .markdown-rendered :global(.sm-code-block pre) { margin: 0; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12.5px; color: var(--text-main); }
  .markdown-rendered :global(.sm-table-wrap) { overflow-x: auto; margin: 10px 0; border-radius: var(--radius-md); border: 1px solid var(--glass-border); }
  .markdown-rendered :global(.sm-table) { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
  .markdown-rendered :global(.sm-table th) { background: rgba(30, 41, 59, 0.85); padding: 8px 12px; border-bottom: 1px solid var(--glass-border); color: var(--text-main); }
  .markdown-rendered :global(.sm-table td) { padding: 8px 12px; border-bottom: 1px solid var(--glass-border); }

  /* Agent Payload Inspector */
  .sim-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .sim-agent-pills {
    display: inline-flex;
    gap: 4px;
    background: rgba(8, 10, 18, 0.55);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 3px;
  }
  .sp-btn {
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text-muted);
    font-family: var(--font-en);
    font-size: 11.5px;
    font-weight: 600;
    padding: 5px 10px;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease;
  }
  .sp-btn:hover { color: var(--text-main); }
  .sp-btn.active { background: rgba(99, 102, 241, 0.24); color: var(--text-main); }

  .sim-ok {
    font-size: 12.5px;
    color: var(--success-soft-text);
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: var(--radius-md);
    padding: 10px 14px;
  }
  .sim-warn {
    font-size: 12.5px;
    color: var(--warning-soft-text);
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.35);
    border-radius: var(--radius-md);
    padding: 10px 14px;
  }
  .sim-pre {
    margin: 0;
    flex: 1;
    background: rgba(8, 10, 18, 0.72);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 16px;
    font-family: 'JetBrains Mono', ui-monospace, 'Prompt', monospace;
    font-size: 12.5px;
    line-height: 1.65;
    color: var(--text-main);
    white-space: pre-wrap;
    overflow-y: auto;
  }

  /* Empty / Loading / Skeleton */
  .skill-skeleton {
    height: 80px;
    border-radius: var(--radius-md);
    background: linear-gradient(90deg, rgba(255, 255, 255, 0.03) 25%, rgba(255, 255, 255, 0.08) 50%, rgba(255, 255, 255, 0.03) 75%);
    background-size: 200% 100%;
    animation: smShimmer 1.4s ease-in-out infinite;
  }
  .empty-icon-box {
    width: 48px;
    height: 48px;
    border-radius: var(--radius-md);
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: var(--primary-soft-text);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .empty-icon-box.lg { width: 64px; height: 64px; border-radius: var(--radius-lg); }
  .empty-state, .no-selection {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    height: 100%;
    padding: 28px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }
  .no-selection h3 { margin: 0; font-size: 16px; color: var(--text-main); }
  .no-selection p { margin: 0; max-width: 380px; }
  .truncate { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ── GPU-Composited Animations ── */
  .stage-in { animation: smStageIn 0.24s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .panel-in { animation: smPanelIn 0.24s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .drawer-in { animation: smDrawerIn 0.2s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .tab-in { animation: smTabIn 0.18s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .stagger-item {
    animation: smCardIn 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--stagger-i, 0) * 26ms);
  }

  @keyframes smStageIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes smPanelIn {
    from { opacity: 0; transform: translateY(6px) scale(0.995); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes smDrawerIn {
    from { opacity: 0; transform: translateY(-6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes smTabIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes smCardIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes smShimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  button:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }

  @media (max-width: 1200px) {
    .tpl-grid { grid-template-columns: repeat(2, 1fr); }
    .col-5, .col-3, .col-9, .col-2 { grid-column: span 6; }
    .split-toggle-btn { display: none; }
    .edit-panel-wrap.is-split { grid-template-columns: 1fr; }
    .split-preview-pane { display: none; }
  }
  @media (max-width: 860px) {
    .skills-shell { flex-direction: column; }
    .skills-sidebar { width: 100%; max-height: 290px; border-right: none; border-bottom: 1px solid var(--glass-border); }
    .skills-sidebar.collapsed { max-height: 0; width: 100%; border-bottom-color: transparent; }
    .main-editor { padding: 10px; }
    .tpl-grid { grid-template-columns: 1fr; }
    .col-2, .col-3, .col-5, .col-9 { grid-column: span 12; }
    .md-snippet-bar { display: none; }
  }
  @media (prefers-reduced-motion: reduce) {
    .stage-in, .panel-in, .drawer-in, .tab-in, .stagger-item, .skill-skeleton {
      animation: none !important;
    }
    .skills-sidebar, .skill-card, .skill-card::before, .stat-chip, .btn-new, .btn-primary, .btn-ghost, .btn-rail-toggle, .btn-clear-mini, .btn-import-md, .tpl-card, .toggle-track, .toggle-thumb, .chevron-ico, .tab-btn, .snip-btn, .sp-btn, .om-item, .search-wrap, .form-input, .active-switch-box, .code-editor, .compat-pill {
      transition: none !important;
    }
  }
</style>
