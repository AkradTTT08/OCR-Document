<script>
  export let mode = 'knowledge_base'; // 'knowledge_base' or 'project_management'
  import { onMount, tick } from 'svelte';
  import { toast } from './toastStore.js';
  import { globalSearchQuery, triggerGlobalSearch } from './globalStore.js';
  import CustomSelect from './CustomSelect.svelte';

  const API = '/api';

  function getAuthHeaders(customHeaders = {}) {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('jwt_token') : null;
    return {
      ...customHeaders,
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
  }

  function trapModalFocus(node) {
    const previouslyFocused = document.activeElement;
    const focusableSelector =
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

    const timer = setTimeout(() => {
      const focusables = node.querySelectorAll(focusableSelector);
      if (focusables.length > 0) /** @type {HTMLElement} */ (focusables[0]).focus();
    }, 20);

    function handleKeydown(e) {
      if (e.key !== 'Tab') return;
      const focusables = Array.from(node.querySelectorAll(focusableSelector));
      if (focusables.length === 0) return;
      const first = /** @type {HTMLElement} */ (focusables[0]);
      const last = /** @type {HTMLElement} */ (focusables[focusables.length - 1]);
      if (e.shiftKey) {
        if (document.activeElement === first || !node.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else if (document.activeElement === last || !node.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      }
    }

    node.addEventListener('keydown', handleKeydown);
    return {
      destroy() {
        clearTimeout(timer);
        node.removeEventListener('keydown', handleKeydown);
        if (previouslyFocused && typeof previouslyFocused.focus === 'function') {
          previouslyFocused.focus();
        }
      }
    };
  }

  const categorySelectOptions = [
    { value: 'Requirements', label: 'Requirements (ความต้องการของระบบ)' },
    { value: 'SRS', label: 'SRS (Software Requirements)' },
    { value: 'TOR/SOW', label: 'TOR / SOW (ขอบเขตงาน)' },
    { value: 'SDD', label: 'SDD (System Design)' },
    { value: 'TestCase', label: 'TestCase (ชุดทดสอบ / Test Plan)' },
    { value: 'UAT', label: 'UAT (User Acceptance Test)' },
    { value: 'MOM', label: 'MOM (รายงานการประชุม)' },
    { value: 'Usermanual', label: 'User Manual (คู่มือการใช้งาน)' },
    { value: 'Admin manual', label: 'Admin Manual (คู่มือผู้ดูแลระบบ)' },
    { value: 'Installation system', label: 'Installation Guide (คู่มือติดตั้ง)' },
    { value: 'Reference', label: 'Reference (เอกสารอ้างอิง)' },
    { value: 'Other', label: 'อื่นๆ (กำหนดเอง)' }
  ];

  const sortSelectOptions = [
    { value: 'newest', label: 'ล่าสุดก่อน' },
    { value: 'name', label: 'ชื่อเอกสาร (ก-ฮ / A-Z)' },
    { value: 'chunks', label: 'จำนวน Chunks มากสุด' },
    { value: 'golden', label: 'Golden Data ก่อน' }
  ];

  // ── Core State ──
  let stats = null;
  let projects = [];
  let documents = [];
  let selectedProject = null;
  let selectedDoc = null;
  let docDetail = null;

  // ── Layout & View State ──
  let viewState = 'explorer'; // 'explorer' | 'search' | 'detail' | 'manual_add'
  let returnView = 'explorer'; // remembers 'search' when opening doc from Vector Search
  let viewMode = 'grid'; // 'grid' | 'list'
  let sortBy = 'newest';
  let sidebarCollapsed = false;

  // ── Search & Filter State ──
  let searchQuery = '';
  let searchResults = [];
  let isSearching = false;
  let searchExecutedQuery = '';
  let searchInputEl = null;

  let docFilterQuery = '';
  let docFilterCategory = 'all';
  let docFilterGoldenOnly = false;
  let projectSearchQuery = '';

  // ── Detail Inspector State ──
  let detailTab = 'preview'; // 'preview' | 'edit' | 'chunks'
  let showOriginalPages = true;
  let chunkSearchQuery = '';
  let showFeedbackPanel = false;
  let highlightChunkText = '';
  let failedPageImages = {};

  // ── Loading & Error State ──
  let isInitialLoading = true;
  let isLoadingDocs = false;
  let isLoadingDetail = false;
  let isReindexing = false;
  let dbError = null;
  let docsRequestSeq = 0;
  let detailRequestSeq = 0;
  let searchRequestSeq = 0;
  let togglingGoldenIds = new Set();

  // ── Edit Markdown State ──
  let editingMarkdown = '';
  let isSavingDoc = false;

  // ── Unsaved Changes & Reindex Confirm Modals ──
  let pendingLeaveAction = null;
  let showReindexConfirmModal = false;

  // ── Manual Doc Form State ──
  let isAddingManualDoc = false;
  let manualDocForm = {
    project_id: '',
    filename: '',
    doc_category: 'Reference',
    customCategory: '',
    doc_type: 'Markdown',
    is_golden_data: false,
    markdown_text: ''
  };

  // ── Edit Document Metadata Modal State ──
  let showEditDocMetaModal = false;
  let isUpdatingDocMeta = false;
  let editingDocForm = {
    id: '',
    filename: '',
    doc_category: 'Requirements',
    is_golden_data: false,
    customCategory: ''
  };

  // ── Delete Document Confirm State ──
  let docToDelete = null;
  let isDeletingDoc = false;

  // ── AI Feedback & Self-Learning Memory State ──
  let feedbackRating = 5;
  let feedbackCorrection = '';
  let isSubmittingFeedback = false;
  let feedbackMemories = [];
  let isLoadingMemories = false;
  let deletingMemoryId = null;

  // ── Derived Data ──
  $: isEditingDirty =
    viewState === 'detail' &&
    detailTab === 'edit' &&
    !!docDetail &&
    editingMarkdown !== (docDetail.document.content || '');

  $: isManualDirty =
    viewState === 'manual_add' &&
    (manualDocForm.filename.trim() !== '' || manualDocForm.markdown_text.trim() !== '');

  $: hasUnsavedChanges = isEditingDirty || isManualDirty;

  $: projectNameMap = Object.fromEntries(
    projects.map((p) => [String(p.id || p.project_id), p.name || p.project_name || ''])
  );

  $: projectSelectOptions = [
    { value: '', label: '-- เลือกโครงการ --' },
    ...projects.map((p) => ({
      value: p.id || p.project_id,
      label: `${p.project_code ? p.project_code + ' — ' : ''}${p.name || p.project_name || ''}`
    }))
  ];

  $: filteredProjects = (() => {
    const q = projectSearchQuery.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter(
      (p) =>
        String(p.name || '').toLowerCase().includes(q) ||
        String(p.project_code || '').toLowerCase().includes(q)
    );
  })();

  $: availableCategories = (() => {
    const cats = new Set();
    for (const d of documents) {
      if (d.doc_category) cats.add(d.doc_category);
    }
    return ['all', ...Array.from(cats).sort()];
  })();

  $: goldenDocsCount = documents.filter((d) => d.is_golden_data).length;
  $: hasActiveFilters = docFilterQuery.trim() !== '' || docFilterCategory !== 'all' || docFilterGoldenOnly;

  $: scopedChunksCount = selectedProject
    ? documents.reduce((sum, d) => sum + (Number(d.chunk_count) || 0), 0)
    : stats?.chunks ?? 0;

  $: filteredDocuments = (() => {
    const q = docFilterQuery.trim().toLowerCase();
    const list = documents.filter((d) => {
      if (docFilterGoldenOnly && !d.is_golden_data) return false;
      if (docFilterCategory !== 'all' && (d.doc_category || 'Reference') !== docFilterCategory) return false;
      if (!q) return true;
      const pName = projectNameMap[String(d.project_id || '')] || '';
      return (
        String(d.name || d.filename || '').toLowerCase().includes(q) ||
        String(d.doc_category || '').toLowerCase().includes(q) ||
        pName.toLowerCase().includes(q)
      );
    });

    return [...list].sort((a, b) => {
      if (sortBy === 'name') {
        return String(a.name || a.filename || '').localeCompare(String(b.name || b.filename || ''), 'th');
      }
      if (sortBy === 'chunks') {
        return (Number(b.chunk_count) || 0) - (Number(a.chunk_count) || 0);
      }
      if (sortBy === 'golden') {
        const gDiff = (b.is_golden_data ? 1 : 0) - (a.is_golden_data ? 1 : 0);
        if (gDiff !== 0) return gDiff;
      }
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
    });
  })();

  // Memoized XSS-safe Markdown rendering
  $: renderedDocHtml = docDetail?.document?.content ? parseMarkdownToHtml(docDetail.document.content) : '';

  $: filteredChunks = (() => {
    const list = docDetail?.chunks || [];
    const q = chunkSearchQuery.trim().toLowerCase();
    if (!q) return list;
    return list.filter((c) => String(c.text || '').toLowerCase().includes(q));
  })();

  $: selectedProjectObj = projects.find((p) => p.id === selectedProject) || null;

  // Global search trigger from Topbar
  $: if ($triggerGlobalSearch) {
    triggerGlobalSearch.set(false);
    if ($globalSearchQuery.trim()) {
      searchQuery = $globalSearchQuery;
      doSearch();
    }
  }

  function guardNavigation(action) {
    if (hasUnsavedChanges) {
      pendingLeaveAction = action;
    } else {
      action();
    }
  }

  function confirmPendingLeave() {
    const act = pendingLeaveAction;
    pendingLeaveAction = null;
    if (docDetail) editingMarkdown = docDetail.document.content || '';
    if (typeof act === 'function') act();
  }

  function clearAllDocFilters() {
    docFilterQuery = '';
    docFilterCategory = 'all';
    docFilterGoldenOnly = false;
  }

  function handleWindowKeydown(e) {
    if (e.key === 'Escape') {
      if (pendingLeaveAction) {
        pendingLeaveAction = null;
        return;
      }
      if (showReindexConfirmModal && !isReindexing) {
        showReindexConfirmModal = false;
        return;
      }
      if (showEditDocMetaModal && !isUpdatingDocMeta) showEditDocMetaModal = false;
      if (docToDelete && !isDeletingDoc) docToDelete = null;
      return;
    }

    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
      if (viewState === 'detail' && detailTab === 'edit' && docDetail) {
        e.preventDefault();
        saveDocEdit();
      } else if (viewState === 'manual_add') {
        e.preventDefault();
        saveManualDoc();
      }
      return;
    }

    if (
      e.key === '/' &&
      !e.ctrlKey &&
      !e.metaKey &&
      !e.altKey &&
      !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName || '')
    ) {
      if (viewState === 'explorer' || viewState === 'search') {
        e.preventDefault();
        searchInputEl?.focus();
      }
    }
  }

  onMount(async () => {
    isInitialLoading = true;
    await Promise.all([loadStats(), loadProjects(), loadDocuments(null)]);
    isInitialLoading = false;
  });

  async function refreshAll() {
    await Promise.all([loadStats(), loadProjects(), loadDocuments(selectedProject)]);
    if (selectedDoc && viewState === 'detail') {
      await loadDocDetail(selectedDoc, { from: returnView });
    }
  }

  async function loadStats() {
    try {
      const r = await fetch(`${API}/kb/stats`, { headers: getAuthHeaders() });
      const d = await r.json();
      if (r.ok && d.success) {
        stats = d.stats;
        dbError = null;
      } else {
        dbError = d.error || 'ไม่สามารถโหลดสถิติฐานข้อมูลได้';
      }
    } catch {
      dbError = 'ไม่สามารถเชื่อมต่อฐานข้อมูลได้ กรุณาตรวจสอบสถานะเซิร์ฟเวอร์';
    }
  }

  async function loadProjects() {
    try {
      const r = await fetch(`${API}/projects`, { headers: getAuthHeaders() });
      const d = await r.json();
      if (r.ok && d.success) projects = d.projects || [];
    } catch {
      /* handled by dbError */
    }
  }

  async function loadDocuments(projectId) {
    const reqId = ++docsRequestSeq;
    isLoadingDocs = true;
    try {
      const url = projectId
        ? `${API}/kb/documents?project_id=${encodeURIComponent(projectId)}&limit=200`
        : `${API}/kb/documents?limit=200`;
      const r = await fetch(url, { headers: getAuthHeaders() });
      const d = await r.json();
      if (reqId !== docsRequestSeq) return;
      if (r.ok && d.success) {
        documents = d.documents || [];
      } else {
        documents = [];
      }
    } catch {
      if (reqId !== docsRequestSeq) return;
      toast('โหลดรายการเอกสารไม่สำเร็จ', 'error');
    } finally {
      if (reqId === docsRequestSeq) isLoadingDocs = false;
    }
  }

  function selectProject(p) {
    guardNavigation(() => {
      selectedProject = p ? p.id : null;
      selectedDoc = null;
      docDetail = null;
      docFilterCategory = 'all';
      docFilterQuery = '';
      docFilterGoldenOnly = false;
      if (viewState === 'detail' || viewState === 'manual_add') {
        viewState = 'explorer';
      }
      loadDocuments(selectedProject);
      if (viewState === 'search' && searchQuery.trim()) {
        doSearch();
      }
    });
  }

  async function loadDocDetail(docId, opts = {}) {
    const reqId = ++detailRequestSeq;
    returnView = opts.from || (viewState === 'search' ? 'search' : 'explorer');
    highlightChunkText = opts.chunkText || '';
    failedPageImages = {};
    isLoadingDetail = true;
    selectedDoc = docId;
    docDetail = null;
    detailTab = 'preview';
    chunkSearchQuery = '';
    showFeedbackPanel = false;
    viewState = 'detail';
    try {
      const r = await fetch(`${API}/kb/documents/${encodeURIComponent(docId)}`, {
        headers: getAuthHeaders()
      });
      const d = await r.json();
      if (reqId !== detailRequestSeq) return;
      if (r.ok && d.success) {
        docDetail = d;
        editingMarkdown = d.document.content || '';
        loadFeedbackMemories(d.document.id);
      } else {
        toast(d.error || 'โหลดรายละเอียดเอกสารไม่สำเร็จ', 'error');
        viewState = returnView;
      }
    } catch {
      if (reqId !== detailRequestSeq) return;
      toast('เกิดข้อผิดพลาดในการโหลดรายละเอียดเอกสาร', 'error');
      viewState = returnView;
    } finally {
      if (reqId === detailRequestSeq) isLoadingDetail = false;
    }
  }

  async function jumpToMatchedChunk() {
    if (!highlightChunkText) return;
    detailTab = 'chunks';
    chunkSearchQuery = highlightChunkText.slice(0, 40).trim();
    await tick();
  }

  function handleDetailBack() {
    guardNavigation(() => {
      const dest = returnView === 'search' && searchResults.length > 0 ? 'search' : 'explorer';
      viewState = dest;
      selectedDoc = null;
      docDetail = null;
      highlightChunkText = '';
    });
  }

  function switchDetailTab(nextTab) {
    if (nextTab === detailTab) return;
    guardNavigation(() => {
      detailTab = nextTab;
      if (nextTab === 'edit' && docDetail) {
        editingMarkdown = docDetail.document.content || '';
      }
    });
  }

  async function doSearch() {
    const q = searchQuery.trim();
    if (!q) return;
    const reqId = ++searchRequestSeq;
    isSearching = true;
    viewState = 'search';
    searchExecutedQuery = q;
    searchResults = [];
    try {
      const pid = selectedProject ? `&project_id=${encodeURIComponent(selectedProject)}` : '';
      const r = await fetch(`${API}/kb/search?q=${encodeURIComponent(q)}${pid}&top_k=10`, {
        headers: getAuthHeaders()
      });
      const d = await r.json();
      if (reqId !== searchRequestSeq) return;
      if (r.ok && d.success) {
        searchResults = d.results || [];
      } else {
        toast(d.error || 'ค้นหา Vector ไม่สำเร็จ', 'error');
      }
    } catch {
      if (reqId !== searchRequestSeq) return;
      toast('เกิดข้อผิดพลาดในการค้นหา', 'error');
    } finally {
      if (reqId === searchRequestSeq) isSearching = false;
    }
  }

  async function saveDocEdit() {
    if (!docDetail || isSavingDoc) return;
    isSavingDoc = true;
    try {
      const r = await fetch(`${API}/kb/documents/${encodeURIComponent(docDetail.document.id)}`, {
        method: 'PUT',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ markdown_text: editingMarkdown })
      });
      const d = await r.json();
      if (r.ok && d.success) {
        toast('อัปเดตเนื้อหาและสร้าง Vector Chunks ใหม่เรียบร้อยแล้ว', 'success');
        docDetail = { ...docDetail, document: { ...docDetail.document, content: editingMarkdown } };
        detailTab = 'preview';
        await Promise.all([loadDocDetail(docDetail.document.id, { from: returnView }), loadStats(), loadDocuments(selectedProject)]);
      } else {
        toast(d.error || 'อัปเดตไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isSavingDoc = false;
    }
  }

  async function quickToggleGolden(doc, event) {
    event?.stopPropagation();
    const docId = doc.id || doc.doc_id;
    if (togglingGoldenIds.has(docId)) return;
    togglingGoldenIds = new Set([...togglingGoldenIds, docId]);
    const nextVal = !doc.is_golden_data;
    try {
      const res = await fetch(`${API}/kb/documents/${encodeURIComponent(docId)}`, {
        method: 'PUT',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ is_golden_data: nextVal })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        documents = documents.map((d) => (d.id === docId ? { ...d, is_golden_data: nextVal } : d));
        if (docDetail && docDetail.document.id === docId) {
          docDetail = { ...docDetail, document: { ...docDetail.document, is_golden_data: nextVal } };
        }
        toast(nextVal ? 'กำหนดเป็น Golden Data เรียบร้อยแล้ว' : 'ยกเลิกสถานะ Golden Data แล้ว', 'success', 2000);
      } else {
        toast(data.error || 'อัปเดตสถานะไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      const nextSet = new Set(togglingGoldenIds);
      nextSet.delete(docId);
      togglingGoldenIds = nextSet;
    }
  }

  function openEditDocCategoryModal(doc, event) {
    event?.stopPropagation();
    if (!doc) return;
    const cat = doc.doc_category || doc.category || 'Reference';
    const knownValues = categorySelectOptions.map((o) => o.value);
    const isKnown = knownValues.includes(cat);
    editingDocForm = {
      id: doc.id || doc.doc_id,
      filename: doc.filename || doc.name || doc.original_filename || '',
      doc_category: isKnown ? cat : 'Other',
      customCategory: isKnown ? '' : cat,
      is_golden_data: !!doc.is_golden_data
    };
    showEditDocMetaModal = true;
  }

  async function saveDocMeta() {
    if (!editingDocForm.id) return;
    const targetCategory =
      editingDocForm.doc_category === 'Other' && editingDocForm.customCategory.trim()
        ? editingDocForm.customCategory.trim()
        : editingDocForm.doc_category;

    if (!editingDocForm.filename.trim()) return toast('กรุณาระบุชื่อเอกสาร', 'warning');
    if (!targetCategory.trim()) return toast('กรุณาระบุหมวดหมู่', 'warning');

    isUpdatingDocMeta = true;
    try {
      const res = await fetch(`${API}/kb/documents/${encodeURIComponent(editingDocForm.id)}`, {
        method: 'PUT',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          filename: editingDocForm.filename.trim(),
          doc_category: targetCategory,
          is_golden_data: editingDocForm.is_golden_data
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(`อัปเดตหมวดหมู่เป็น "${targetCategory}" เรียบร้อยแล้ว`, 'success');
        showEditDocMetaModal = false;
        await loadDocuments(selectedProject);
        if (selectedDoc === editingDocForm.id && viewState === 'detail') {
          await loadDocDetail(editingDocForm.id, { from: returnView });
        }
      } else {
        toast(data.error || 'อัปเดตไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isUpdatingDocMeta = false;
    }
  }

  function openAddManualDoc() {
    guardNavigation(() => {
      manualDocForm = {
        project_id: selectedProject || (projects.length > 0 ? projects[0].id || projects[0].project_id : ''),
        filename: '',
        doc_category: 'Reference',
        customCategory: '',
        doc_type: 'Markdown',
        is_golden_data: false,
        markdown_text: ''
      };
      viewState = 'manual_add';
    });
  }

  function handleImportTextFile(event) {
    const input = event.target;
    const file = input?.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      toast('ไฟล์มีขนาดใหญ่เกิน 10 MB', 'warning');
      input.value = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      manualDocForm.filename = file.name;
      manualDocForm.markdown_text = String(reader.result || '');
      manualDocForm.doc_type = file.name.toLowerCase().endsWith('.md') ? 'Markdown' : 'Text';
      toast(`นำเข้าไฟล์ "${file.name}" เรียบร้อยแล้ว`, 'success', 2000);
      input.value = '';
    };
    reader.onerror = () => {
      toast('ไม่สามารถอ่านไฟล์ที่เลือกได้', 'error');
      input.value = '';
    };
    reader.readAsText(file, 'utf-8');
  }

  async function saveManualDoc() {
    const targetCategory =
      manualDocForm.doc_category === 'Other' && manualDocForm.customCategory.trim()
        ? manualDocForm.customCategory.trim()
        : manualDocForm.doc_category;

    if (!manualDocForm.project_id) return toast('กรุณาเลือกโครงการ', 'warning');
    if (!manualDocForm.filename.trim()) return toast('กรุณาระบุชื่อเอกสาร', 'warning');
    if (!targetCategory.trim()) return toast('กรุณาระบุหมวดหมู่', 'warning');
    if (!manualDocForm.markdown_text.trim()) return toast('กรุณาระบุเนื้อหาเอกสาร', 'warning');

    isAddingManualDoc = true;
    try {
      const payload = {
        project_id: manualDocForm.project_id,
        filename: manualDocForm.filename.trim(),
        doc_category: targetCategory,
        doc_type: manualDocForm.doc_type,
        is_golden_data: manualDocForm.is_golden_data,
        markdown_text: manualDocForm.markdown_text
      };
      const res = await fetch(`${API}/kb/ingest`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || 'เกิดข้อผิดพลาดในการบันทึก');

      toast(data.message || 'บันทึกเอกสารและสร้าง Vector Index เรียบร้อยแล้ว', 'success');
      manualDocForm = { ...manualDocForm, filename: '', markdown_text: '', customCategory: '' };
      viewState = 'explorer';
      await Promise.all([loadDocuments(selectedProject), loadStats(), loadProjects()]);
    } catch (err) {
      toast(`ข้อผิดพลาด: ${err instanceof Error ? err.message : String(err)}`, 'error');
    } finally {
      isAddingManualDoc = false;
    }
  }

  async function reindexProjectRAG() {
    if (!selectedProject || isReindexing) return;
    showReindexConfirmModal = false;
    isReindexing = true;
    try {
      toast('กำลังประมวลผล Re-index Semantic Chunks & Vector Embeddings...', 'info', 2500);
      const r = await fetch(`${API}/kb/reindex`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ project_id: selectedProject })
      });
      const d = await r.json();
      if (r.ok && d.success) {
        toast(d.message || 'Re-index Semantic Chunks สำเร็จ', 'success');
        await Promise.all([loadStats(), loadDocuments(selectedProject)]);
        if (selectedDoc && viewState === 'detail') await loadDocDetail(selectedDoc, { from: returnView });
      } else {
        toast(d.error || 'Re-index ไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isReindexing = false;
    }
  }

  async function executeDeleteDoc() {
    if (!docToDelete || isDeletingDoc) return;
    const targetId = docToDelete.id || docToDelete.doc_id;
    isDeletingDoc = true;
    try {
      const res = await fetch(`${API}/kb/documents/${encodeURIComponent(targetId)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('ลบเอกสารเรียบร้อยแล้ว', 'success');
        documents = documents.filter((d) => d.id !== targetId);
        if (selectedDoc === targetId) {
          selectedDoc = null;
          docDetail = null;
          viewState = 'explorer';
        }
        await Promise.all([loadStats(), loadProjects()]);
      } else {
        toast(data.error || 'ลบเอกสารไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isDeletingDoc = false;
      docToDelete = null;
    }
  }

  async function loadFeedbackMemories(docId) {
    if (!docId) {
      feedbackMemories = [];
      return;
    }
    isLoadingMemories = true;
    try {
      const res = await fetch(`${API}/kb/feedback?doc_id=${encodeURIComponent(docId)}&limit=20`, {
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok && data.success) {
        feedbackMemories = data.memories || [];
      }
    } catch {
      /* ignore transient fetch error */
    } finally {
      isLoadingMemories = false;
    }
  }

  async function submitAIFeedback() {
    if (isSubmittingFeedback) return;
    isSubmittingFeedback = true;
    try {
      const res = await fetch(`${API}/kb/feedback`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          rating: feedbackRating,
          correction: feedbackCorrection.trim(),
          doc_id: docDetail ? docDetail.document.id : null,
          project_id: docDetail ? docDetail.document.project_id : selectedProject,
          context_id: docDetail ? docDetail.document.id : 'general'
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('บันทึก AI Feedback & Self-Learning Memory ลงฐานข้อมูลแล้ว', 'success');
        feedbackCorrection = '';
        if (data.memory) {
          feedbackMemories = [data.memory, ...feedbackMemories];
        } else if (docDetail?.document?.id) {
          await loadFeedbackMemories(docDetail.document.id);
        }
      } else {
        toast(data.error || 'บันทึก AI Feedback ไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการบันทึก AI Feedback', 'error');
    } finally {
      isSubmittingFeedback = false;
    }
  }

  async function deleteFeedbackMemory(memoryId) {
    if (!memoryId || deletingMemoryId) return;
    deletingMemoryId = memoryId;
    try {
      const res = await fetch(`${API}/kb/feedback/${encodeURIComponent(memoryId)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok && data.success) {
        feedbackMemories = feedbackMemories.filter((m) => (m.id || m.memory_id) !== memoryId);
        toast('ลบรายการ AI Memory เรียบร้อยแล้ว', 'success', 2000);
      } else {
        toast(data.error || 'ลบรายการ Memory ไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      deletingMemoryId = null;
    }
  }

  async function copyToClipboard(text, label = 'ข้อความ') {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast(`คัดลอก ${label} เรียบร้อยแล้ว`, 'success', 2000);
    } catch {
      toast(`ไม่สามารถคัดลอก ${label} ได้`, 'error');
    }
  }

  function downloadMarkdownDoc() {
    if (!docDetail?.document) return;
    const name = (docDetail.document.filename || 'document').replace(/\.pdf$/i, '') + '.md';
    const blob = new Blob([docDetail.document.content || ''], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function formatDate(val) {
    if (!val) return '—';
    return new Date(val).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' });
  }

  function similarityColor(s) {
    if (s >= 0.72) return 'var(--success, #10b981)';
    if (s >= 0.48) return 'var(--warning, #f59e0b)';
    return 'var(--danger, #f43f5e)';
  }

  // ── XSS-Safe Markdown Renderer ──
  function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatSafeInlineMarkdown(rawLine) {
    let safe = escapeHtml(rawLine);
    safe = safe.replace(/(?:\.\s*){5,}\./g, ' ... ');
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/`([^`]+)`/g, '<code class="kb-inline-code">$1</code>');
    return safe;
  }

  function parseMarkdownToHtml(text) {
    if (!text) return '';
    const lines = String(text).split('\n');
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

      if (line.startsWith('```')) {
        if (!inCodeBlock) {
          inCodeBlock = true;
          codeLanguage = escapeHtml(line.substring(3).trim());
          codeBlockContent = [];
          continue;
        } else {
          inCodeBlock = false;
          html.push(
            `<div class="kb-code-block"><div class="kb-code-lang">${codeLanguage || 'code'}</div><pre><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre></div>`
          );
          continue;
        }
      }

      if (inCodeBlock) {
        codeBlockContent.push(rawLine);
        continue;
      }

      if (line.startsWith('|') && line.endsWith('|')) {
        const cells = line.slice(1, -1).split('|').map((c) => c.trim());
        if (!inTable) {
          const nextLine = (lines[i + 1] || '').trim();
          if (nextLine.startsWith('|') && /^[|:\s-]+$/.test(nextLine) && nextLine.includes('-')) {
            inTable = true;
            tableHeaders = cells;
            i++;
            continue;
          }
        }
        if (inTable) {
          if (!cells.every((c) => c === '')) tableRows.push(cells);
          continue;
        }
      }

      if (inTable) {
        html.push(renderHtmlTable(tableHeaders, tableRows));
        inTable = false;
        tableHeaders = [];
        tableRows = [];
      }

      if (line === '') {
        html.push('<div class="kb-md-spacer"></div>');
      } else if (line === '---' || line === '***') {
        html.push('<hr class="kb-md-hr" />');
      } else if (line.startsWith('### ')) {
        html.push(`<h3 class="kb-md-h3">${formatSafeInlineMarkdown(line.substring(4))}</h3>`);
      } else if (line.startsWith('## ')) {
        html.push(`<h2 class="kb-md-h2">${formatSafeInlineMarkdown(line.substring(3))}</h2>`);
      } else if (line.startsWith('# ')) {
        html.push(`<h1 class="kb-md-h1">${formatSafeInlineMarkdown(line.substring(2))}</h1>`);
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        html.push(`<div class="kb-md-li">• ${formatSafeInlineMarkdown(line.substring(2))}</div>`);
      } else if (/^(.+?)\s+\.\.\.\s+(\d+|[IVXLCDM]+)$/i.test(line)) {
        const tocMatch = line.match(/^(.+?)\s+\.\.\.\s+(\d+|[IVXLCDM]+)$/i);
        html.push(
          `<div class="kb-toc-row"><span class="kb-toc-title">${formatSafeInlineMarkdown(tocMatch[1])}</span><span class="kb-toc-dots"></span><span class="kb-toc-page">${escapeHtml(tocMatch[2])}</span></div>`
        );
      } else if (/^\d+\.\s/.test(line)) {
        const match = line.match(/^(\d+)\.\s(.*)/);
        if (match) {
          html.push(`<div class="kb-md-ol"><span class="kb-ol-num">${escapeHtml(match[1])}.</span><span>${formatSafeInlineMarkdown(match[2])}</span></div>`);
        } else {
          html.push(`<div class="kb-md-p">${formatSafeInlineMarkdown(line)}</div>`);
        }
      } else {
        html.push(`<div class="kb-md-p">${formatSafeInlineMarkdown(line)}</div>`);
      }
    }

    if (inTable) html.push(renderHtmlTable(tableHeaders, tableRows));
    if (inCodeBlock) {
      html.push(`<div class="kb-code-block"><pre><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre></div>`);
    }
    return html.join('\n');
  }

  function renderHtmlTable(headers, rows) {
    const html = ['<div class="kb-md-table-wrap"><table class="kb-md-table">'];
    if (headers.length > 0) {
      html.push('<thead><tr>');
      headers.forEach((h) => html.push(`<th>${formatSafeInlineMarkdown(h)}</th>`));
      html.push('</tr></thead>');
    }
    if (rows.length > 0) {
      html.push('<tbody>');
      rows.forEach((row) => {
        html.push('<tr>');
        row.forEach((cell) => html.push(`<td>${formatSafeInlineMarkdown(cell)}</td>`));
        html.push('</tr>');
      });
      html.push('</tbody>');
    }
    html.push('</table></div>');
    return html.join('');
  }
</script>

<svelte:window on:keydown={handleWindowKeydown} />

<div class="kb-shell" class:sidebar-collapsed={sidebarCollapsed}>
  <!-- ── Left Sidebar: Project Scope & Telemetry ── -->
  <aside class="kb-sidebar" class:collapsed={sidebarCollapsed} aria-label="ขอบเขตโครงการ Knowledge Base">
    <!-- Compact KPI Stats -->
    {#if dbError}
      <div class="db-error" role="alert">
        <div class="db-error-row">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <span>{dbError}</span>
        </div>
        <button type="button" class="btn-retry" on:click={refreshAll}>ลองเชื่อมต่อใหม่</button>
      </div>
    {:else if stats}
      <div class="stats-bar">
        <div class="stat-chip">
          <span class="stat-num">{stats.projects}</span>
          <span class="stat-lbl">โครงการ</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num accent">{selectedProject ? documents.length : stats.documents}</span>
          <span class="stat-lbl">{selectedProject ? 'ในโครงการ' : 'เอกสาร'}</span>
        </div>
        <div class="stat-chip">
          <span class="stat-num violet">{scopedChunksCount}</span>
          <span class="stat-lbl">Chunks</span>
        </div>
      </div>
    {:else}
      <div class="stats-bar">
        <div class="stat-chip skeleton-shimmer"></div>
        <div class="stat-chip skeleton-shimmer"></div>
        <div class="stat-chip skeleton-shimmer"></div>
      </div>
    {/if}

    <!-- Project Filter Search (only shown when > 8 projects to avoid competing search boxes) -->
    {#if projects.length > 8}
      <div class="sidebar-search-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <input
          type="text"
          bind:value={projectSearchQuery}
          placeholder="กรองโครงการ..."
          aria-label="กรองรายชื่อโครงการ"
        />
      </div>
    {/if}

    <div class="section-label-row">
      <span class="section-label">PROJECT SCOPE ({projects.length})</span>
      <button
        type="button"
        class="btn-collapse-sidebar"
        title="พับแถบโครงการ"
        aria-label="พับแถบโครงการ"
        on:click={() => (sidebarCollapsed = true)}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <polyline points="15 18 9 12 15 6"></polyline>
        </svg>
      </button>
    </div>

    <nav class="project-list" aria-label="เลือกโครงการ">
      <button
        type="button"
        class="project-btn"
        class:active={selectedProject === null}
        on:click={() => selectProject(null)}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="15" height="15">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
        <span class="truncate">ทุกโครงการ (ทั้งหมด)</span>
        <span class="proj-count">{stats?.documents ?? documents.length}</span>
      </button>

      {#each filteredProjects as p (p.id)}
        <button
          type="button"
          class="project-btn"
          class:active={selectedProject === p.id}
          on:click={() => selectProject(p)}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="15" height="15">
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
          </svg>
          <span class="truncate" title={p.name}>{p.name}</span>
          <span class="proj-count" class:nonzero={(p.doc_count || 0) > 0}>{p.doc_count || 0}</span>
        </button>
      {/each}
    </nav>

    <!-- Sidebar Quick Actions -->
    {#if mode === 'knowledge_base'}
      <div class="sidebar-footer-actions">
        <button type="button" class="btn-sidebar-primary" on:click={openAddManualDoc}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          <span>เพิ่มเอกสาร / นำเข้า .md</span>
        </button>
        {#if selectedProject}
          <button
            type="button"
            class="btn-sidebar-secondary"
            on:click={() => (showReindexConfirmModal = true)}
            disabled={isReindexing || documents.length === 0}
            title="สร้าง Vector Embeddings ใหม่ทั้งหมดให้เอกสารในโครงการนี้ (ปกติระบบอัปเดตอัตโนมัติเมื่อบันทึกเอกสาร)"
          >
            <svg class:spin-icon={isReindexing} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
              <path d="M3 3v5h5"></path>
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path>
            </svg>
            <span>{isReindexing ? 'กำลัง Re-index...' : 'Re-index RAG โครงการนี้'}</span>
          </button>
        {/if}
      </div>
    {/if}
  </aside>

  <!-- ── Main Workspace ── -->
  <main class="kb-main">
    <!-- Top Semantic Command Bar (shown in Explorer & Search; hidden in Detail & Manual Add to maximize reading canvas) -->
    {#if viewState === 'explorer' || viewState === 'search'}
      <header class="kb-command-bar">
        {#if sidebarCollapsed}
          <button
            type="button"
            class="btn-ghost btn-icon-only"
            title="แสดงแถบโครงการ"
            aria-label="แสดงแถบโครงการ"
            on:click={() => (sidebarCollapsed = false)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
              <polyline points="9 18 15 12 9 6"></polyline>
            </svg>
          </button>
        {/if}

        <form class="semantic-search-form" on:submit|preventDefault={doSearch}>
          <span class="ss-badge">AI VECTOR</span>
          <input
            bind:this={searchInputEl}
            type="text"
            bind:value={searchQuery}
            placeholder={`ค้นหาเชิงความหมายในเนื้อหาเอกสาร${selectedProjectObj ? ' (' + selectedProjectObj.name + ')' : ' (ทุกโครงการ)'}... กด / หรือ Enter`}
            aria-label="ค้นหาเนื้อหาเชิงความหมายด้วย AI Vector Search"
          />
          {#if searchQuery}
            <button
              type="button"
              class="btn-clear-ss"
              aria-label="ล้างคำค้นหา"
              on:click={() => {
                searchQuery = '';
                if (viewState === 'search') viewState = 'explorer';
              }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          {/if}
          <button type="submit" class="btn-ss-submit" disabled={isSearching || !searchQuery.trim()}>
            {isSearching ? 'กำลังค้นหา...' : 'ค้นหา Vector'}
          </button>
        </form>

        <div class="cmd-right-btns">
          {#if viewState === 'search'}
            <button type="button" class="btn-ghost" on:click={() => (viewState = 'explorer')}>
              คลังเอกสาร ({documents.length})
            </button>
          {/if}
          <button type="button" class="btn-ghost btn-icon-only" on:click={refreshAll} title="รีเฟรชข้อมูล" aria-label="รีเฟรชข้อมูล">
            <svg class:spin-icon={isLoadingDocs} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <polyline points="23 4 23 10 17 10"></polyline>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
            </svg>
          </button>
        </div>
      </header>
    {/if}

    <!-- ── VIEW 1: VECTOR SEARCH RESULTS ── -->
    {#if viewState === 'search'}
      <div class="kb-workspace-body stage-in">
        <div class="workspace-subhead">
          <div>
            <h2>ผลลัพธ์ Semantic Search: “{searchExecutedQuery}”</h2>
            <p aria-live="polite">
              พบ <strong class="num-font">{searchResults.length}</strong> Chunks ที่เกี่ยวข้องมากที่สุด
              {#if selectedProjectObj}ในโครงการ {selectedProjectObj.name}{:else}จากทุกโครงการ{/if}
            </p>
          </div>
          <button type="button" class="btn-ghost" on:click={() => (viewState = 'explorer')}>
            กลับไปคลังเอกสาร
          </button>
        </div>

        {#if isSearching}
          <div class="center-state">
            <span class="kb-spinner"></span>
            <p>กำลังค้นหาด้วย Vector Embeddings...</p>
          </div>
        {:else if searchResults.length === 0}
          <div class="center-state">
            <p class="cs-title">ไม่พบข้อมูลที่ตรงกับ “{searchExecutedQuery}”</p>
            <p class="cs-sub">ลองใช้คำค้นหาที่กว้างขึ้น หรือเลือกขอบเขตเป็น "ทุกโครงการ" ที่แถบด้านซ้าย</p>
          </div>
        {:else}
          <div class="search-results-grid">
            {#each searchResults as r, i}
              <article class="result-card stagger-item" style={`--stagger-i:${Math.min(i, 10)}`}>
                <div class="result-header">
                  <span class="result-rank">#{i + 1}</span>
                  <div class="result-doc-meta">
                    <span class="result-doc truncate" title={r.doc_name}>{r.doc_name}</span>
                    <div class="result-tags">
                      {#if r.project_name}
                        <span class="tag-proj">{r.project_name}</span>
                      {/if}
                      <span class="tag-cat">{r.doc_category || 'Reference'}</span>
                      {#if r.is_golden_data}
                        <span class="tag-golden">Golden Data</span>
                      {/if}
                    </div>
                  </div>
                  <span class="result-score" style="color:{similarityColor(r.similarity)}">
                    {(r.similarity * 100).toFixed(1)}% match
                  </span>
                </div>
                <div class="result-bar-wrap">
                  <div class="result-bar" style="width:{Math.max(4, Math.min(100, r.similarity * 100)).toFixed(1)}%; background:{similarityColor(r.similarity)}"></div>
                </div>
                <p class="result-text">{r.chunk_text}</p>
                <div class="result-footer">
                  <button type="button" class="btn-ghost btn-xs" on:click={() => copyToClipboard(r.chunk_text, 'ข้อความ Chunk')}>
                    คัดลอก Chunk
                  </button>
                  <button type="button" class="btn-open-doc" on:click={() => loadDocDetail(r.document_id, { from: 'search', chunkText: r.chunk_text })}>
                    <span>เปิดดูเอกสารเต็ม</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                      <line x1="5" y1="12" x2="19" y2="12"></line>
                      <polyline points="12 5 19 12 12 19"></polyline>
                    </svg>
                  </button>
                </div>
              </article>
            {/each}
          </div>
        {/if}
      </div>

    <!-- ── VIEW 2: MANUAL ADD / IMPORT MARKDOWN ── -->
    {:else if viewState === 'manual_add'}
      <div class="kb-workspace-body stage-in">
        <div class="workspace-subhead">
          <div class="subhead-title-group">
            {#if sidebarCollapsed}
              <button type="button" class="btn-ghost btn-icon-only" title="แสดงแถบโครงการ" aria-label="แสดงแถบโครงการ" on:click={() => (sidebarCollapsed = false)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><polyline points="9 18 15 12 9 6"></polyline></svg>
              </button>
            {/if}
            <div>
              <h2>เพิ่มเอกสารเข้า Knowledge Base</h2>
              <p>พิมพ์หรือวางเนื้อหา Markdown หรือนำเข้าจากไฟล์ .md / .txt เพื่อสร้าง Vector Index อัตโนมัติ (กด Ctrl+S เพื่อบันทึก)</p>
            </div>
          </div>
          <div class="subhead-actions">
            <label class="btn-ghost import-file-label">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <span>นำเข้าไฟล์ .md / .txt</span>
              <input type="file" accept=".md,.txt,.markdown" on:change={handleImportTextFile} hidden />
            </label>
            <button type="button" class="btn-ghost" on:click={() => guardNavigation(() => (viewState = 'explorer'))}>ยกเลิก</button>
          </div>
        </div>

        <div class="manual-form-card">
          <div class="form-grid-2">
            <div class="form-group">
              <label for="manual-project">โครงการ (Project) <span class="req">*</span></label>
              <CustomSelect id="manual-project" bind:value={manualDocForm.project_id} options={projectSelectOptions} width="100%" />
            </div>
            <div class="form-group">
              <label for="manual-category">หมวดหมู่เอกสาร</label>
              <CustomSelect id="manual-category" bind:value={manualDocForm.doc_category} options={categorySelectOptions} width="100%" />
            </div>
          </div>

          {#if manualDocForm.doc_category === 'Other'}
            <div class="form-group stage-in">
              <label for="manual_custom_cat">ระบุหมวดหมู่เอง <span class="req">*</span></label>
              <input id="manual_custom_cat" type="text" class="form-input" placeholder="เช่น API Spec, Business Rule..." bind:value={manualDocForm.customCategory} />
            </div>
          {/if}

          <div class="form-group">
            <label for="m_filename">ชื่อเอกสาร (Filename / Title) <span class="req">*</span></label>
            <input id="m_filename" type="text" class="form-input" placeholder="เช่น SRS_AirManifest_v1.0.md" bind:value={manualDocForm.filename} />
          </div>

          <div class="golden-toggle-card" class:active={manualDocForm.is_golden_data}>
            <div>
              <div class="gt-title">กำหนดเป็น Golden Data (เอกสารอ้างอิงหลัก)</div>
              <div class="gt-sub">ใช้เป็นมาตรฐานหลักสำหรับ AI QA Consult และการสร้าง Test Case</div>
            </div>
            <label class="toggle-wrap">
              <input type="checkbox" bind:checked={manualDocForm.is_golden_data} aria-label="กำหนดเป็น Golden Data" />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </label>
          </div>

          <div class="form-group">
            <div class="label-between">
              <label for="m_content">เนื้อหาเอกสาร (Markdown) <span class="req">*</span></label>
              <span class="char-counter">{manualDocForm.markdown_text.length.toLocaleString()} ตัวอักษร</span>
            </div>
            <textarea
              id="m_content"
              class="form-input code-textarea"
              rows="14"
              placeholder="# หัวข้อเอกสาร&#10;&#10;วางเนื้อหา Markdown ที่นี่..."
              bind:value={manualDocForm.markdown_text}
            ></textarea>
          </div>

          <div class="manual-form-footer">
            <button type="button" class="btn-ghost" on:click={() => guardNavigation(() => (viewState = 'explorer'))} disabled={isAddingManualDoc}>ยกเลิก</button>
            <button
              type="button"
              class="btn-primary"
              on:click={saveManualDoc}
              disabled={isAddingManualDoc || !manualDocForm.project_id || !manualDocForm.filename.trim() || !manualDocForm.markdown_text.trim()}
            >
              {isAddingManualDoc ? 'กำลังบันทึกและสร้าง Vector...' : 'บันทึกเข้า Knowledge Base'}
            </button>
          </div>
        </div>
      </div>

    <!-- ── VIEW 3: DOCUMENT INSPECTOR (PREVIEW / EDIT / CHUNKS) ── -->
    {:else if viewState === 'detail'}
      {#if isLoadingDetail}
        <div class="center-state">
          <span class="kb-spinner"></span>
          <p>กำลังโหลดรายละเอียดเอกสารและ Chunks...</p>
        </div>
      {:else if docDetail}
        <div class="detail-studio stage-in">
          <div class="detail-top-bar">
            <div class="detail-top-left">
              {#if sidebarCollapsed}
                <button type="button" class="btn-ghost btn-icon-only" title="แสดงแถบโครงการ" aria-label="แสดงแถบโครงการ" on:click={() => (sidebarCollapsed = false)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </button>
              {/if}
              <button type="button" class="btn-back" on:click={handleDetailBack}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
                <span>{returnView === 'search' && searchResults.length > 0 ? 'กลับไปผลค้นหา' : 'คลังเอกสาร'}</span>
              </button>
              <h2 class="detail-title truncate" title={docDetail.document.filename}>{docDetail.document.filename}</h2>
              {#if isEditingDirty}
                <span class="dirty-pill">ยังไม่บันทึก</span>
              {/if}
            </div>
            <div class="detail-top-actions">
              {#if mode === 'knowledge_base'}
                <button
                  type="button"
                  class="btn-ghost btn-xs golden-header-btn"
                  class:is-golden={docDetail.document.is_golden_data}
                  disabled={togglingGoldenIds.has(docDetail.document.id)}
                  on:click={(e) => quickToggleGolden(docDetail.document, e)}
                  title={docDetail.document.is_golden_data ? 'ยกเลิก Golden Data' : 'กำหนดเป็น Golden Data'}
                >
                  <svg viewBox="0 0 24 24" fill={docDetail.document.is_golden_data ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="1.8" width="13" height="13">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                  </svg>
                  <span>Golden</span>
                </button>
              {:else if docDetail.document.is_golden_data}
                <span class="tag-golden">Golden Data</span>
              {/if}
              <button type="button" class="btn-ghost btn-xs" on:click={() => copyToClipboard(docDetail.document.content, 'Markdown')}>
                คัดลอก MD
              </button>
              <button type="button" class="btn-ghost btn-xs" on:click={downloadMarkdownDoc}>
                ดาวน์โหลด .md
              </button>
              {#if mode === 'knowledge_base'}
                <button type="button" class="btn-ghost btn-xs" on:click={(e) => openEditDocCategoryModal(docDetail.document, e)}>
                  แก้ไขหมวดหมู่
                </button>
                <button type="button" class="btn-ghost btn-xs danger-outline" on:click={() => (docToDelete = docDetail.document)}>
                  ลบ
                </button>
              {/if}
            </div>
          </div>

          <!-- Metadata & Sub-Tab Strip -->
          <div class="detail-subbar">
            <div class="detail-tabs" role="tablist" aria-label="มุมมองเอกสาร">
              <button type="button" role="tab" aria-selected={detailTab === 'preview'} class="dtab" class:active={detailTab === 'preview'} on:click={() => switchDetailTab('preview')}>
                พรีวิวเอกสาร
              </button>
              {#if mode === 'knowledge_base'}
                <button type="button" role="tab" aria-selected={detailTab === 'edit'} class="dtab" class:active={detailTab === 'edit'} on:click={() => switchDetailTab('edit')}>
                  แก้ไข Markdown
                </button>
              {/if}
              <button type="button" role="tab" aria-selected={detailTab === 'chunks'} class="dtab" class:active={detailTab === 'chunks'} on:click={() => switchDetailTab('chunks')}>
                Vector Chunks <span class="tab-count">{docDetail.chunks?.length || 0}</span>
              </button>
            </div>

            <div class="detail-meta-inline">
              {#if docDetail.document.project_name}
                <span class="tag-proj">{docDetail.document.project_name}</span>
              {/if}
              <span class="tag-cat">{docDetail.document.doc_category || 'Reference'}</span>
              <span class="meta-date">{formatDate(docDetail.document.created_at)}</span>
              {#if detailTab === 'preview' && docDetail.document.total_pages > 0}
                <label class="inline-toggle-lbl">
                  <input type="checkbox" bind:checked={showOriginalPages} />
                  <span>เทียบภาพต้นฉบับ ({docDetail.document.total_pages} หน้า)</span>
                </label>
              {/if}
              <button type="button" class="btn-ghost btn-xs" on:click={() => (showFeedbackPanel = !showFeedbackPanel)}>
                {showFeedbackPanel ? 'ซ่อน AI Memory' : `AI Memory${feedbackMemories.length ? ` (${feedbackMemories.length})` : ''}`}
              </button>
            </div>
          </div>

          {#if highlightChunkText && detailTab === 'preview'}
            <div class="matched-chunk-banner stage-in">
              <span>เปิดจากผลค้นหา Vector: “{highlightChunkText.slice(0, 72)}{highlightChunkText.length > 72 ? '...' : ''}”</span>
              <div class="mcb-actions">
                <button type="button" class="btn-open-doc" on:click={jumpToMatchedChunk}>ดู Chunk ที่ตรงกัน</button>
                <button type="button" class="btn-clear-ss" aria-label="ปิดแถบแจ้งเตือน" on:click={() => (highlightChunkText = '')}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            </div>
          {/if}

          <!-- Optional Collapsible AI Feedback Panel -->
          {#if showFeedbackPanel}
            <div class="ai-feedback-drawer stage-in">
              <div class="afd-head">
                <div>
                  <strong>AI Feedback &amp; Self-Learning Memory</strong>
                  <span>ให้คะแนนหรือบันทึกข้อเสนอแนะเพื่อปรับปรุงบริบท RAG สำหรับโครงการนี้</span>
                </div>
                <div class="star-rating" role="radiogroup" aria-label="คะแนนความแม่นยำ">
                  {#each [1, 2, 3, 4, 5] as star}
                    <button
                      type="button"
                      role="radio"
                      aria-checked={star === feedbackRating}
                      class="star-btn"
                      class:filled={star <= feedbackRating}
                      aria-label={`ให้ ${star} ดาว`}
                      on:click={() => (feedbackRating = star)}
                    >
                      <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                        <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
                      </svg>
                    </button>
                  {/each}
                </div>
              </div>
              <div class="afd-row">
                <input
                  type="text"
                  class="form-input"
                  aria-label="ข้อเสนอแนะเพิ่มเติมสำหรับ AI"
                  bind:value={feedbackCorrection}
                  placeholder="ระบุข้อมูลเพิ่มเติมหรือคำแนะนำเฉพาะโดเมนเพื่อสอน AI (Agent QA Consult / Research / MCP จะดึงไปใช้อัตโนมัติ)..."
                />
                <button type="button" class="btn-primary" on:click={submitAIFeedback} disabled={isSubmittingFeedback}>
                  {isSubmittingFeedback ? 'กำลังบันทึก...' : 'บันทึก Memory'}
                </button>
              </div>
              {#if isLoadingMemories}
                <div class="afd-mem-empty">กำลังโหลดรายการ Memory...</div>
              {:else if feedbackMemories.length > 0}
                <div class="afd-mem-list">
                  {#each feedbackMemories as mem (mem.id || mem.memory_id)}
                    <div class="afd-mem-item">
                      <span class="afd-mem-rating num-font">★ {mem.rating}/5</span>
                      <span class="afd-mem-text">{mem.correction || 'ให้คะแนนความแม่นยำ (ไม่มีหมายเหตุ)'}</span>
                      <span class="afd-mem-date">{formatDate(mem.created_at)}</span>
                      {#if mode === 'knowledge_base'}
                        <button
                          type="button"
                          class="btn-clear-ss"
                          title="ลบ Memory นี้"
                          aria-label="ลบ AI Memory"
                          disabled={deletingMemoryId === (mem.id || mem.memory_id)}
                          on:click={() => deleteFeedbackMemory(mem.id || mem.memory_id)}
                        >
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          <!-- Detail Body -->
          <div class="detail-body-scroll">
            {#if detailTab === 'preview'}
              {#if showOriginalPages && docDetail.document.total_pages > 0}
                <div class="split-preview-grid stage-in">
                  <div class="orig-pages-pane">
                    <div class="pane-cap">ภาพหน้าเอกสารต้นฉบับ ({docDetail.document.total_pages} หน้า)</div>
                    <div class="orig-pages-list">
                      {#each Array(docDetail.document.total_pages) as _, i}
                        <div class="orig-page-card">
                          <span class="page-num-pill">PAGE {i + 1}</span>
                          {#if failedPageImages[i + 1]}
                            <div class="page-img-fallback">ไม่สามารถโหลดภาพหน้า {i + 1} ได้</div>
                          {:else}
                            <img
                              src={`/api/kb/view/${docDetail.document.id}/${i + 1}`}
                              alt={`หน้า ${i + 1}`}
                              loading="lazy"
                              decoding="async"
                              on:error={() => (failedPageImages = { ...failedPageImages, [i + 1]: true })}
                            />
                          {/if}
                        </div>
                      {/each}
                    </div>
                  </div>
                  <div class="md-preview-pane">
                    <div class="pane-cap">เนื้อหา Markdown ที่สกัดได้</div>
                    <div class="rendered-md-content">
                      {@html renderedDocHtml}
                    </div>
                  </div>
                </div>
              {:else}
                <div class="md-preview-single stage-in">
                  <div class="rendered-md-content">
                    {@html renderedDocHtml}
                  </div>
                </div>
              {/if}

            {:else if detailTab === 'edit'}
              <div class="edit-doc-pane stage-in">
                <div class="edit-toolbar">
                  <div class="edit-status-left">
                    <span class="char-counter">{editingMarkdown.length.toLocaleString()} ตัวอักษร</span>
                    <span class="shortcut-hint">Ctrl+S เพื่อบันทึก</span>
                  </div>
                  <div class="edit-btns">
                    <button type="button" class="btn-ghost" on:click={() => switchDetailTab('preview')} disabled={isSavingDoc}>
                      ยกเลิก
                    </button>
                    <button type="button" class="btn-primary" on:click={saveDocEdit} disabled={isSavingDoc}>
                      {isSavingDoc ? 'กำลังบันทึก & สร้าง Chunks...' : 'บันทึก & อัปเดต Vector Chunks'}
                    </button>
                  </div>
                </div>
                <textarea
                  class="form-input code-textarea full-editor"
                  aria-label="แก้ไขเนื้อหา Markdown ของเอกสาร"
                  placeholder="พิมพ์หรือแก้ไขเนื้อหา Markdown ที่นี่..."
                  bind:value={editingMarkdown}
                  disabled={isSavingDoc}
                ></textarea>
              </div>

            {:else if detailTab === 'chunks'}
              <div class="chunks-pane stage-in">
                <div class="chunks-toolbar">
                  <div class="inline-search">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                      <circle cx="11" cy="11" r="8"></circle>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                    <input type="text" bind:value={chunkSearchQuery} placeholder="ค้นหาข้อความภายใน Chunks..." aria-label="ค้นหาใน Chunks" />
                  </div>
                  <span class="chunk-count-lbl">แสดง {filteredChunks.length} / {docDetail.chunks?.length || 0} Chunks</span>
                </div>
                <div class="chunks-grid">
                  {#each filteredChunks as chunk, idx (chunk.id)}
                    <div
                      class="chunk-card stagger-item"
                      class:chunk-matched={highlightChunkText && String(chunk.text || '').includes(highlightChunkText.slice(0, 40))}
                      style={`--stagger-i:${Math.min(idx, 10)}`}
                    >
                      <div class="chunk-head">
                        <span class="chunk-badge">CHUNK #{idx + 1}</span>
                        <span class="chunk-len">{(chunk.text || '').length} chars</span>
                        <button type="button" class="btn-copy-chunk" on:click={() => copyToClipboard(chunk.text, `Chunk #${idx + 1}`)}>
                          คัดลอก
                        </button>
                      </div>
                      <p class="chunk-text">{chunk.text}</p>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        </div>
      {/if}

    <!-- ── VIEW 4: EXPLORER DASHBOARD (DEFAULT) ── -->
    {:else}
      <div class="kb-workspace-body stage-in">
        <div class="explorer-head">
          <div>
            <h2 aria-live="polite">
              {selectedProjectObj ? selectedProjectObj.name : 'คลังเอกสารทั้งหมด (Knowledge Base)'}
              <span class="head-count">({filteredDocuments.length}{#if filteredDocuments.length !== documents.length} / {documents.length}{/if})</span>
            </h2>
            <p>
              เลือกเอกสารเพื่ออ่านเนื้อหา Markdown, เทียบภาพ PDF ต้นฉบับ หรือกำหนดเป็น Golden Data สำหรับ AI QA
            </p>
          </div>
          <div class="explorer-filters">
            <div class="inline-search">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input type="text" bind:value={docFilterQuery} placeholder="กรองชื่อไฟล์..." aria-label="กรองชื่อไฟล์เอกสาร" />
            </div>

            <div class="sort-select-wrap">
              <CustomSelect bind:value={sortBy} options={sortSelectOptions} width="168px" />
            </div>

            <button
              type="button"
              class="filter-pill golden"
              class:active={docFilterGoldenOnly}
              aria-pressed={docFilterGoldenOnly}
              on:click={() => (docFilterGoldenOnly = !docFilterGoldenOnly)}
            >
              <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">
                <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
              </svg>
              <span>Golden ({goldenDocsCount})</span>
            </button>

            <div class="view-mode-switch" role="group" aria-label="รูปแบบการแสดงผล">
              <button
                type="button"
                class="vms-btn"
                class:active={viewMode === 'grid'}
                aria-label="แสดงแบบการ์ด"
                aria-pressed={viewMode === 'grid'}
                title="แสดงแบบการ์ด"
                on:click={() => (viewMode = 'grid')}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <rect x="3" y="3" width="7" height="7" rx="1"></rect>
                  <rect x="14" y="3" width="7" height="7" rx="1"></rect>
                  <rect x="3" y="14" width="7" height="7" rx="1"></rect>
                  <rect x="14" y="14" width="7" height="7" rx="1"></rect>
                </svg>
              </button>
              <button
                type="button"
                class="vms-btn"
                class:active={viewMode === 'list'}
                aria-label="แสดงแบบตารางรายชื่อ"
                aria-pressed={viewMode === 'list'}
                title="แสดงแบบตาราง (เห็นชื่อไฟล์เต็ม)"
                on:click={() => (viewMode = 'list')}
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <line x1="8" y1="6" x2="21" y2="6"></line>
                  <line x1="8" y1="12" x2="21" y2="12"></line>
                  <line x1="8" y1="18" x2="21" y2="18"></line>
                  <line x1="3" y1="6" x2="3.01" y2="6"></line>
                  <line x1="3" y1="12" x2="3.01" y2="12"></line>
                  <line x1="3" y1="18" x2="3.01" y2="18"></line>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Category Filter Strip -->
        {#if availableCategories.length > 2}
          <div class="category-pills-row" role="group" aria-label="กรองตามหมวดหมู่เอกสาร">
            {#each availableCategories as cat}
              <button
                type="button"
                class="filter-pill"
                class:active={docFilterCategory === cat}
                aria-pressed={docFilterCategory === cat}
                on:click={() => (docFilterCategory = cat)}
              >
                {cat === 'all' ? 'ทุกหมวดหมู่' : cat}
              </button>
            {/each}
          </div>
        {/if}

        {#if documents.length >= 200}
          <div class="limit-notice">
            แสดงสูงสุด 200 เอกสารล่าสุด — เลือกโครงการเฉพาะทางด้านซ้ายหรือใช้ AI Vector Search เพื่อค้นหาเอกสารที่เก่ากว่า
          </div>
        {/if}

        {#if isInitialLoading || isLoadingDocs}
          <div class="doc-cards-grid">
            {#each Array(6) as _, sIdx}
              <div class="kb-doc-card skeleton-card" style={`--stagger-i:${sIdx}`}>
                <div class="skeleton-line short"></div>
                <div class="skeleton-line title"></div>
                <div class="skeleton-line medium"></div>
              </div>
            {/each}
          </div>
        {:else if filteredDocuments.length === 0}
          <div class="center-state stage-in">
            <div class="empty-svg-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <p class="cs-title">{documents.length === 0 ? 'ยังไม่มีเอกสารในขอบเขตนี้' : 'ไม่พบเอกสารที่ตรงกับเงื่อนไขการกรอง'}</p>
            {#if hasActiveFilters && documents.length > 0}
              <p class="cs-sub">ลองล้างตัวกรองเพื่อแสดงเอกสารทั้งหมด ({documents.length} รายการ)</p>
              <button type="button" class="btn-ghost" on:click={clearAllDocFilters}>ล้างตัวกรองทั้งหมด</button>
            {:else}
              <p class="cs-sub">อัปโหลด PDF ในเมนู Scan OCR หรือกด "+ เพิ่มเอกสาร / นำเข้า .md" ที่แถบด้านซ้าย</p>
            {/if}
          </div>
        {:else if viewMode === 'list'}
          <div class="doc-table-wrap stage-in">
            <table class="doc-table">
              <thead>
                <tr>
                  <th>ชื่อเอกสาร</th>
                  {#if !selectedProject}<th>โครงการ</th>{/if}
                  <th>หมวดหมู่</th>
                  <th class="num-col">Chunks</th>
                  <th>อัปเดตเมื่อ</th>
                  {#if mode === 'knowledge_base'}<th class="act-col">จัดการ</th>{/if}
                </tr>
              </thead>
              <tbody>
                {#each filteredDocuments as doc, idx (doc.id)}
                  <tr class="stagger-item" style={`--stagger-i:${Math.min(idx, 10)}`}>
                    <td>
                      <button type="button" class="table-doc-link" on:click={() => loadDocDetail(doc.id, { from: 'explorer' })}>
                        <span class="tdl-name">{doc.name}</span>
                        {#if doc.is_golden_data}
                          <span class="tag-golden">Golden</span>
                        {/if}
                      </button>
                    </td>
                    {#if !selectedProject}
                      <td>
                        {#if projectNameMap[String(doc.project_id || '')]}
                          <span class="tag-proj truncate">{projectNameMap[String(doc.project_id || '')]}</span>
                        {:else}
                          <span class="muted-dash">—</span>
                        {/if}
                      </td>
                    {/if}
                    <td><span class="tag-cat">{doc.doc_category || 'Reference'}</span></td>
                    <td class="num-col num-font">{doc.chunk_count || 0}</td>
                    <td class="date-col">{formatDate(doc.created_at)}</td>
                    {#if mode === 'knowledge_base'}
                      <td class="act-col">
                        <div class="table-actions">
                          <button
                            type="button"
                            class="kdc-btn star"
                            class:is-golden={doc.is_golden_data}
                            disabled={togglingGoldenIds.has(doc.id)}
                            title={doc.is_golden_data ? 'ยกเลิก Golden Data' : 'กำหนดเป็น Golden Data'}
                            aria-label={`สลับสถานะ Golden Data ของ ${doc.name}`}
                            on:click={(e) => quickToggleGolden(doc, e)}
                          >
                            <svg viewBox="0 0 24 24" fill={doc.is_golden_data ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="1.8" width="14" height="14">
                              <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            class="kdc-btn"
                            title="แก้ไขชื่อและหมวดหมู่"
                            aria-label={`แก้ไขหมวดหมู่ ${doc.name}`}
                            on:click={(e) => openEditDocCategoryModal(doc, e)}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
                              <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                            </svg>
                          </button>
                          <button
                            type="button"
                            class="kdc-btn danger"
                            title="ลบเอกสาร"
                            aria-label={`ลบเอกสาร ${doc.name}`}
                            on:click={() => (docToDelete = doc)}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
                              <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    {/if}
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {:else}
          <div class="doc-cards-grid">
            {#each filteredDocuments as doc, idx (doc.id)}
              <article class="kb-doc-card stagger-item" class:golden-accent={doc.is_golden_data} style={`--stagger-i:${Math.min(idx, 10)}`}>
                <!-- Primary clickable overlay button (avoids nested interactive elements) -->
                <button
                  type="button"
                  class="kdc-open-trigger"
                  aria-label={`เปิดดูเอกสาร ${doc.name}`}
                  on:click={() => loadDocDetail(doc.id, { from: 'explorer' })}
                ></button>

                <div class="kdc-top">
                  <div class="kdc-top-left">
                    <div class="kdc-icon" class:is-golden={doc.is_golden_data}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                    </div>
                    {#if mode === 'knowledge_base'}
                      <button
                        type="button"
                        class="kdc-btn star"
                        class:is-golden={doc.is_golden_data}
                        disabled={togglingGoldenIds.has(doc.id)}
                        title={doc.is_golden_data ? 'ยกเลิก Golden Data' : 'กำหนดเป็น Golden Data'}
                        aria-label={`สลับสถานะ Golden Data ของ ${doc.name}`}
                        on:click={(e) => quickToggleGolden(doc, e)}
                      >
                        <svg viewBox="0 0 24 24" fill={doc.is_golden_data ? 'currentColor' : 'none'} stroke="currentColor" stroke-width="1.8" width="15" height="15">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                        </svg>
                      </button>
                    {/if}
                  </div>
                  {#if mode === 'knowledge_base'}
                    <div class="kdc-actions">
                      <button
                        type="button"
                        class="kdc-btn hover-reveal"
                        title="แก้ไขชื่อและหมวดหมู่"
                        aria-label={`แก้ไขหมวดหมู่ ${doc.name}`}
                        on:click={(e) => openEditDocCategoryModal(doc, e)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        class="kdc-btn danger hover-reveal sep-left"
                        title="ลบเอกสาร"
                        aria-label={`ลบเอกสาร ${doc.name}`}
                        on:click={() => (docToDelete = doc)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                      </button>
                    </div>
                  {/if}
                </div>

                <h3 class="kdc-title" title={doc.name}>{doc.name}</h3>

                <div class="kdc-tags">
                  {#if !selectedProject && projectNameMap[String(doc.project_id || '')]}
                    <span class="tag-proj truncate">{projectNameMap[String(doc.project_id || '')]}</span>
                  {/if}
                  <span class="tag-cat">{doc.doc_category || 'Reference'}</span>
                  {#if doc.is_golden_data}
                    <span class="tag-golden">Golden</span>
                  {/if}
                </div>

                <div class="kdc-footer">
                  <span>{doc.chunk_count || 0} chunks</span>
                  <span>{formatDate(doc.created_at)}</span>
                </div>
              </article>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </main>

  <!-- ── Edit Document Metadata Modal ── -->
  {#if showEditDocMetaModal}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => { if (!isUpdatingDocMeta) showEditDocMetaModal = false; }} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content" use:trapModalFocus on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="kb-edit-meta-title">
        <div class="modal-header">
          <h3 id="kb-edit-meta-title">แก้ไขชื่อและหมวดหมู่เอกสาร</h3>
          <button type="button" class="btn-close" aria-label="ปิด" on:click={() => (showEditDocMetaModal = false)} disabled={isUpdatingDocMeta}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="edit_doc_name">ชื่อเอกสาร <span class="req">*</span></label>
            <input id="edit_doc_name" type="text" class="form-input" bind:value={editingDocForm.filename} />
          </div>
          <div class="form-group">
            <label for="edit_doc_cat">หมวดหมู่เอกสาร <span class="req">*</span></label>
            <CustomSelect id="edit_doc_cat" bind:value={editingDocForm.doc_category} options={categorySelectOptions} width="100%" />
          </div>
          {#if editingDocForm.doc_category === 'Other'}
            <div class="form-group">
              <label for="edit_custom_cat">ระบุหมวดหมู่เอง</label>
              <input id="edit_custom_cat" type="text" class="form-input" bind:value={editingDocForm.customCategory} placeholder="เช่น User Journey, API Spec..." />
            </div>
          {/if}
          <div class="golden-toggle-card" class:active={editingDocForm.is_golden_data}>
            <div>
              <div class="gt-title">กำหนดเป็น Golden Data</div>
              <div class="gt-sub">ใช้เป็นเอกสารอ้างอิงหลักสำหรับ AI ตรวจสอบ</div>
            </div>
            <label class="toggle-wrap">
              <input type="checkbox" bind:checked={editingDocForm.is_golden_data} aria-label="กำหนดเป็น Golden Data" />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </label>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn-ghost" on:click={() => (showEditDocMetaModal = false)} disabled={isUpdatingDocMeta}>ยกเลิก</button>
          <button type="button" class="btn-primary" on:click={saveDocMeta} disabled={isUpdatingDocMeta || !editingDocForm.filename.trim()}>
            {isUpdatingDocMeta ? 'กำลังบันทึก...' : 'บันทึกการแก้ไข'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Delete Document Confirm Modal ── -->
  {#if docToDelete}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => { if (!isDeletingDoc) docToDelete = null; }} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content modal-sm" use:trapModalFocus on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="kb-del-doc-title">
        <div class="modal-header">
          <h3 id="kb-del-doc-title" class="danger-title">ยืนยันการลบเอกสาร</h3>
          <button type="button" class="btn-close" aria-label="ปิด" on:click={() => (docToDelete = null)} disabled={isDeletingDoc}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
        <div class="modal-body">
          <p class="confirm-msg">ต้องการลบเอกสาร <strong>"{docToDelete.name || docToDelete.filename}"</strong> ออกจาก Knowledge Base ใช่หรือไม่?</p>
          <p class="confirm-warn">Vector Chunks และภาพหน้าเอกสารต้นฉบับทั้งหมดของไฟล์นี้จะถูกลบถาวร</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn-ghost" on:click={() => (docToDelete = null)} disabled={isDeletingDoc}>ยกเลิก</button>
          <button type="button" class="btn-danger" on:click={executeDeleteDoc} disabled={isDeletingDoc}>
            {isDeletingDoc ? 'กำลังลบ...' : 'ลบเอกสารถาวร'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Unsaved Changes Guard Modal ── -->
  {#if pendingLeaveAction}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => (pendingLeaveAction = null)} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content modal-sm" use:trapModalFocus on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="kb-dirty-title">
        <div class="modal-header">
          <h3 id="kb-dirty-title">มีการแก้ไขที่ยังไม่บันทึก</h3>
          <button type="button" class="btn-close" aria-label="ปิด" on:click={() => (pendingLeaveAction = null)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
        <div class="modal-body">
          <p class="confirm-msg">คุณกำลังแก้ไขเอกสารอยู่ หากออกจากหน้านี้โดยไม่บันทึก การเปลี่ยนแปลงทั้งหมดจะหายไป</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn-ghost" on:click={() => (pendingLeaveAction = null)}>กลับไปแก้ไขต่อ</button>
          <button type="button" class="btn-danger" on:click={confirmPendingLeave}>ละทิ้งการแก้ไข</button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Re-index RAG Confirm Modal ── -->
  {#if showReindexConfirmModal}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-backdrop" on:click={() => (showReindexConfirmModal = false)} role="presentation">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="modal-content modal-sm" use:trapModalFocus on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="kb-reindex-title">
        <div class="modal-header">
          <h3 id="kb-reindex-title">ยืนยันการ Re-index RAG</h3>
          <button type="button" class="btn-close" aria-label="ปิด" on:click={() => (showReindexConfirmModal = false)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
        <div class="modal-body">
          <p class="confirm-msg">ต้องการสร้าง Vector Embeddings ใหม่ทั้งหมดสำหรับโครงการ <strong>"{selectedProjectObj?.name || ''}"</strong> ({documents.length} เอกสาร) ใช่หรือไม่?</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn-ghost" on:click={() => (showReindexConfirmModal = false)}>ยกเลิก</button>
          <button type="button" class="btn-primary" on:click={reindexProjectRAG}>เริ่ม Re-index</button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  /* ── Spectra QA Design System Tokens & Bilingual Typography ── */
  .kb-shell {
    display: flex;
    height: 100%;
    overflow: hidden;
    background: transparent;
    color: var(--text-main);
  }

  .num-font {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-variant-numeric: tabular-nums;
  }

  /* ── Left Sidebar ── */
  .kb-sidebar {
    width: 272px;
    flex-shrink: 0;
    background: rgba(12, 15, 26, 0.72);
    border-right: 1px solid var(--glass-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.28s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease, border-color 0.2s ease;
  }
  .kb-sidebar.collapsed {
    width: 0;
    opacity: 0;
    border-right-color: transparent;
    pointer-events: none;
  }

  .stats-bar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    padding: 14px 12px 12px;
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }
  .stat-chip {
    background: var(--surface-card, rgba(18, 20, 28, 0.65));
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 8px 6px;
    text-align: center;
    min-height: 52px;
    transition: border-color 0.2s ease, transform 0.2s ease;
  }
  .stat-chip:hover {
    border-color: rgba(99, 102, 241, 0.35);
    transform: translateY(-1px);
  }
  .stat-num {
    display: block;
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 17px;
    font-weight: 700;
    color: var(--primary-soft-text);
    font-variant-numeric: tabular-nums;
    line-height: 1.25;
  }
  .stat-num.accent { color: #38bdf8; }
  .stat-num.violet { color: #d8b4fe; }
  .stat-lbl {
    font-size: 10.5px;
    color: var(--text-muted);
  }

  .db-error {
    margin: 12px;
    padding: 10px 12px;
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.3);
    border-radius: 12px;
    font-size: 12px;
    color: #fda4af;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .db-error-row { display: flex; gap: 8px; align-items: flex-start; }
  .btn-retry {
    align-self: flex-start;
    background: rgba(244, 63, 94, 0.2);
    border: 1px solid rgba(244, 63, 94, 0.4);
    color: #ffffff;
    font-family: inherit;
    font-size: 11.5px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 8px;
    cursor: pointer;
  }
  .btn-retry:hover { background: rgba(244, 63, 94, 0.35); }

  .sidebar-search-wrap {
    display: flex;
    align-items: center;
    gap: 7px;
    margin: 10px 12px 4px;
    padding: 7px 11px;
    background: rgba(8, 10, 18, 0.55);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .sidebar-search-wrap:focus-within {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
  }
  .sidebar-search-wrap svg { color: var(--text-muted); flex-shrink: 0; }
  .sidebar-search-wrap input {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main);
    font-family: inherit;
    font-size: 12.5px;
  }

  .section-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px 6px 14px;
    flex-shrink: 0;
  }
  .section-label {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .btn-collapse-sidebar {
    min-width: 24px;
    min-height: 24px;
    border-radius: 8px;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease;
  }
  .btn-collapse-sidebar:hover { background: rgba(255, 255, 255, 0.06); color: #ffffff; }

  .project-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .project-btn {
    position: relative;
    width: 100%;
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 9px 12px;
    border-radius: 12px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-muted);
    font-family: inherit;
    font-size: 13px;
    text-align: left;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
  }
  .project-btn::before {
    content: '';
    position: absolute;
    left: 0;
    top: 20%;
    bottom: 20%;
    width: 4px;
    border-radius: 0 8px 8px 0;
    background: linear-gradient(180deg, var(--primary), var(--secondary));
    opacity: 0;
    transform: scaleY(0.4);
    transition: opacity 0.2s ease, transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .project-btn:hover {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-main);
  }
  .project-btn.active {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.32);
    color: #ffffff;
    font-weight: 600;
  }
  .project-btn.active::before {
    opacity: 1;
    transform: scaleY(1);
  }
  .project-btn svg { flex-shrink: 0; opacity: 0.85; transition: color 0.18s ease; }
  .project-btn.active svg { color: var(--secondary); opacity: 1; }
  .proj-count {
    margin-left: auto;
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    padding: 2px 8px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .proj-count.nonzero {
    background: rgba(99, 102, 241, 0.2);
    color: #c7d2fe;
  }

  .sidebar-footer-actions {
    padding: 12px;
    border-top: 1px solid var(--glass-border);
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-shrink: 0;
  }
  .btn-sidebar-primary {
    width: 100%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    padding: 10px 14px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: #ffffff;
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease, filter 0.18s ease;
  }
  .btn-sidebar-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.5);
    filter: brightness(1.06);
  }
  .btn-sidebar-primary:active { transform: translateY(0); }

  .btn-sidebar-secondary {
    width: 100%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    padding: 9px 12px;
    border-radius: 12px;
    border: 1px solid rgba(168, 85, 247, 0.35);
    background: rgba(168, 85, 247, 0.12);
    color: #e9d5ff;
    font-family: inherit;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
  }
  .btn-sidebar-secondary:hover:not(:disabled) {
    background: rgba(168, 85, 247, 0.24);
    border-color: rgba(168, 85, 247, 0.55);
    color: #ffffff;
  }
  .btn-sidebar-secondary:disabled { opacity: 0.45; cursor: not-allowed; }

  /* ── Main Workspace ── */
  .kb-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .kb-command-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 22px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(12, 15, 26, 0.65);
    flex-shrink: 0;
  }
  .semantic-search-form {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(8, 10, 18, 0.65);
    border: 1px solid var(--glass-border-light);
    border-radius: 12px;
    padding: 4px 5px 4px 10px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .semantic-search-form:focus-within {
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22);
  }
  .ss-badge {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 3px 8px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #c7d2fe;
    flex-shrink: 0;
  }
  .semantic-search-form input {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main);
    font-family: inherit;
    font-size: 13.5px;
    padding: 6px 0;
  }
  .btn-clear-ss {
    min-width: 26px;
    min-height: 26px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    transition: color 0.16s ease, background-color 0.16s ease;
  }
  .btn-clear-ss:hover { color: #ffffff; background: rgba(255, 255, 255, 0.08); }
  .btn-ss-submit {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border: none;
    color: #ffffff;
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 600;
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.28);
    transition: transform 0.18s ease, filter 0.18s ease, box-shadow 0.18s ease;
  }
  .btn-ss-submit:hover:not(:disabled) {
    filter: brightness(1.08);
    box-shadow: 0 6px 18px rgba(99, 102, 241, 0.45);
  }
  .btn-ss-submit:disabled { opacity: 0.45; cursor: not-allowed; }
  .cmd-right-btns { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .btn-icon-only { padding: 8px; min-width: 34px; min-height: 34px; justify-content: center; }

  .kb-workspace-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* Explorer Header & Filters */
  .explorer-head, .workspace-subhead {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
  }
  .subhead-title-group { display: flex; align-items: flex-start; gap: 10px; }
  .explorer-head h2, .workspace-subhead h2 {
    margin: 0 0 4px;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-main);
  }
  .head-count {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-muted);
    margin-left: 4px;
  }
  .explorer-head p, .workspace-subhead p {
    margin: 0;
    font-size: 12.5px;
    color: var(--text-muted);
  }
  .explorer-filters, .subhead-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .inline-search {
    display: flex;
    align-items: center;
    gap: 7px;
    background: rgba(8, 10, 18, 0.55);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 7px 12px;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
  }
  .inline-search:focus-within {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.18);
  }
  .inline-search svg { color: var(--text-muted); flex-shrink: 0; }
  .inline-search input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main);
    font-family: inherit;
    font-size: 12.5px;
    width: 155px;
  }
  .sort-select-wrap { min-width: 168px; }

  .view-mode-switch {
    display: inline-flex;
    background: rgba(8, 10, 18, 0.55);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 3px;
    gap: 2px;
  }
  .vms-btn {
    min-width: 30px;
    min-height: 28px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease;
  }
  .vms-btn:hover { color: var(--text-main); }
  .vms-btn.active {
    background: rgba(99, 102, 241, 0.22);
    color: #ffffff;
  }

  .category-pills-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .filter-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-height: 30px;
    padding: 5px 12px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-family: inherit;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
  }
  .filter-pill:hover { color: var(--text-main); border-color: var(--glass-border-light); transform: translateY(-1px); }
  .filter-pill.active {
    background: rgba(99, 102, 241, 0.2);
    border-color: rgba(99, 102, 241, 0.48);
    color: #ffffff;
    font-weight: 600;
  }
  .filter-pill.golden.active {
    background: rgba(245, 158, 11, 0.18);
    border-color: rgba(245, 158, 11, 0.48);
    color: #fcd34d;
  }

  .limit-notice {
    font-size: 12px;
    color: #fcd34d;
    background: rgba(245, 158, 11, 0.1);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 12px;
    padding: 8px 14px;
  }

  /* Document Cards Grid (Zero Nested Interactive Elements) */
  .doc-cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 14px;
  }
  .kb-doc-card {
    position: relative;
    background: var(--surface-card, rgba(18, 20, 28, 0.72));
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: border-color 0.22s ease, transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.22s ease, box-shadow 0.22s ease;
  }
  .kb-doc-card:hover, .kb-doc-card:focus-within {
    border-color: rgba(99, 102, 241, 0.48);
    background: rgba(22, 26, 44, 0.9);
    transform: translateY(-3px);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.38);
  }
  .kb-doc-card.golden-accent {
    border-color: rgba(245, 158, 11, 0.28);
  }
  .kb-doc-card.golden-accent:hover {
    border-color: rgba(245, 158, 11, 0.55);
  }
  .kdc-open-trigger {
    position: absolute;
    inset: 0;
    z-index: 1;
    background: transparent;
    border: none;
    border-radius: 20px;
    cursor: pointer;
  }
  .kdc-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .kdc-top-left {
    display: flex;
    align-items: center;
    gap: 8px;
    position: relative;
    z-index: 2;
  }
  .kdc-icon {
    width: 36px;
    height: 36px;
    border-radius: 12px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: var(--primary-soft-text);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .kb-doc-card:hover .kdc-icon { transform: scale(1.05); }
  .kdc-icon.is-golden {
    background: rgba(245, 158, 11, 0.14);
    border-color: rgba(245, 158, 11, 0.38);
    color: #fbbf24;
  }

  .kdc-actions {
    position: relative;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .kdc-btn {
    min-width: 30px;
    min-height: 30px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid transparent;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease, opacity 0.18s ease, transform 0.18s ease;
  }
  .kb-doc-card .kdc-btn.hover-reveal {
    opacity: 0;
    transform: translateY(-2px);
  }
  .kb-doc-card:hover .kdc-btn.hover-reveal,
  .kb-doc-card:focus-within .kdc-btn.hover-reveal {
    opacity: 1;
    transform: translateY(0);
  }
  .kdc-btn.sep-left { margin-left: 2px; }
  .kdc-btn:hover:not(:disabled) { background: rgba(255, 255, 255, 0.1); color: #ffffff; }
  .kdc-btn:disabled { opacity: 0.45; cursor: wait; }
  .kdc-btn.star.is-golden {
    color: #fbbf24;
    background: rgba(245, 158, 11, 0.16);
    border-color: rgba(245, 158, 11, 0.38);
    animation: kbStarPop 0.32s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .kdc-btn.danger:hover {
    background: rgba(244, 63, 94, 0.16);
    color: #fda4af;
    border-color: rgba(244, 63, 94, 0.4);
  }

  .kdc-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-main);
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .kdc-tags { display: flex; flex-wrap: wrap; gap: 6px; }
  .tag-proj {
    font-family: 'Outfit', 'Inter', 'Prompt', sans-serif;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 8px;
    background: rgba(6, 182, 212, 0.14);
    border: 1px solid rgba(6, 182, 212, 0.3);
    color: #67e8f9;
    max-width: 160px;
  }
  .tag-cat {
    font-family: 'Outfit', 'Inter', 'Prompt', sans-serif;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
  }
  .tag-golden {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 10.5px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 20px;
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: #fcd34d;
  }
  .kdc-footer {
    margin-top: auto;
    padding-top: 10px;
    border-top: 1px solid var(--glass-border);
    display: flex;
    justify-content: space-between;
    font-family: 'Outfit', 'Inter', 'Prompt', sans-serif;
    font-size: 11.5px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }

  /* List Table View */
  .doc-table-wrap {
    background: var(--surface-card, rgba(18, 20, 28, 0.72));
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    overflow-x: auto;
  }
  .doc-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    text-align: left;
  }
  .doc-table th {
    font-family: 'Outfit', 'Inter', 'Prompt', sans-serif;
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-muted);
    padding: 12px 16px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(8, 10, 18, 0.45);
    white-space: nowrap;
  }
  .doc-table td {
    padding: 11px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    vertical-align: middle;
  }
  .doc-table tbody tr {
    transition: background-color 0.16s ease;
  }
  .doc-table tbody tr:hover { background: rgba(99, 102, 241, 0.08); }
  .doc-table tbody tr:last-child td { border-bottom: none; }
  .table-doc-link {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: transparent;
    border: none;
    padding: 0;
    color: var(--text-main);
    font-family: inherit;
    font-size: 13.5px;
    font-weight: 600;
    text-align: left;
    cursor: pointer;
    transition: color 0.16s ease;
  }
  .table-doc-link:hover .tdl-name { color: #a5b4fc; text-decoration: underline; }
  .num-col { text-align: right; white-space: nowrap; color: var(--text-muted); }
  .date-col { white-space: nowrap; font-size: 12px; color: var(--text-muted); }
  .act-col { text-align: right; white-space: nowrap; }
  .table-actions { display: inline-flex; align-items: center; gap: 5px; }
  .muted-dash { color: var(--text-muted); }

  /* Skeleton Shimmer */
  .skeleton-card { min-height: 148px; pointer-events: none; }
  .skeleton-shimmer, .skeleton-line {
    background: linear-gradient(90deg, rgba(255, 255, 255, 0.04) 25%, rgba(255, 255, 255, 0.09) 50%, rgba(255, 255, 255, 0.04) 75%);
    background-size: 200% 100%;
    animation: kbShimmer 1.4s ease-in-out infinite;
    border-radius: 8px;
  }
  .skeleton-line { height: 14px; }
  .skeleton-line.short { width: 38%; height: 28px; border-radius: 12px; }
  .skeleton-line.title { width: 85%; height: 18px; margin-top: 6px; }
  .skeleton-line.medium { width: 60%; margin-top: auto; }

  /* Search Results */
  .search-results-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .result-card {
    background: var(--surface-card, rgba(18, 20, 28, 0.72));
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    transition: border-color 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .result-card:hover {
    border-color: rgba(99, 102, 241, 0.42);
    transform: translateY(-2px);
  }
  .result-header { display: flex; align-items: flex-start; gap: 10px; }
  .result-rank {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 11.5px;
    font-weight: 700;
    color: #c7d2fe;
    background: rgba(99, 102, 241, 0.2);
    padding: 3px 9px;
    border-radius: 8px;
    flex-shrink: 0;
  }
  .result-doc-meta { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
  .result-doc { font-size: 14px; font-weight: 600; color: var(--text-main); }
  .result-tags { display: flex; flex-wrap: wrap; gap: 6px; }
  .result-score {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .result-bar-wrap { height: 4px; background: rgba(255, 255, 255, 0.08); border-radius: 20px; overflow: hidden; }
  .result-bar {
    height: 100%;
    border-radius: 20px;
    transform-origin: left center;
    animation: kbBarGrow 0.55s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .result-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.65;
    color: #cbd5e1;
    white-space: pre-wrap;
    background: rgba(8, 10, 18, 0.5);
    padding: 12px 14px;
    border-radius: 12px;
    border: 1px solid var(--glass-border);
  }
  .result-footer { display: flex; justify-content: flex-end; gap: 8px; }
  .btn-open-doc {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.38);
    color: #c7d2fe;
    font-family: inherit;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
  }
  .btn-open-doc:hover { background: rgba(99, 102, 241, 0.28); color: #ffffff; transform: translateX(1px); }

  /* Document Detail Studio */
  .detail-studio {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
  .detail-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 22px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(12, 15, 26, 0.65);
    flex-shrink: 0;
  }
  .detail-top-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
  .detail-title { margin: 0; font-size: 15.5px; font-weight: 700; color: var(--text-main); }
  .dirty-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 20px;
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: #fcd34d;
    flex-shrink: 0;
  }
  .detail-top-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .golden-header-btn.is-golden {
    background: rgba(245, 158, 11, 0.18);
    border-color: rgba(245, 158, 11, 0.48);
    color: #fcd34d;
  }

  .btn-back {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--primary-soft-text);
    padding: 6px 12px;
    border-radius: 12px;
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    flex-shrink: 0;
    transition: border-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
  }
  .btn-back:hover { border-color: var(--primary); color: #ffffff; transform: translateX(-2px); }

  .detail-subbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    padding: 8px 22px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(8, 10, 18, 0.35);
    flex-shrink: 0;
  }
  .detail-tabs { display: flex; gap: 6px; }
  .dtab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
  }
  .dtab:hover { color: var(--text-main); background: rgba(255, 255, 255, 0.04); }
  .dtab.active {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.45);
    color: #ffffff;
    font-weight: 600;
  }
  .tab-count {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 11px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.08);
  }
  .detail-meta-inline { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
  .meta-date { font-family: 'Outfit', 'Inter', 'Prompt', sans-serif; color: var(--text-muted); }
  .inline-toggle-lbl { display: inline-flex; align-items: center; gap: 6px; color: var(--text-muted); cursor: pointer; font-size: 12px; }

  .matched-chunk-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 22px;
    background: rgba(99, 102, 241, 0.12);
    border-bottom: 1px solid rgba(99, 102, 241, 0.3);
    font-size: 12.5px;
    color: #e0e7ff;
    flex-shrink: 0;
  }
  .mcb-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }

  .ai-feedback-drawer {
    padding: 12px 22px;
    background: rgba(168, 85, 247, 0.08);
    border-bottom: 1px solid rgba(168, 85, 247, 0.28);
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex-shrink: 0;
  }
  .afd-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .afd-head strong { display: block; font-size: 13px; color: #f3e8ff; }
  .afd-head span { font-size: 11.5px; color: var(--text-muted); }
  .star-rating { display: flex; gap: 3px; }
  .star-btn {
    min-width: 28px;
    min-height: 28px;
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #475569;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.16s ease, color 0.16s ease;
  }
  .star-btn:hover { transform: scale(1.12); }
  .star-btn.filled { color: #fbbf24; }
  .afd-row { display: flex; gap: 8px; }
  .afd-mem-empty { font-size: 12px; color: var(--text-muted); }
  .afd-mem-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 150px;
    overflow-y: auto;
    padding-top: 6px;
    border-top: 1px solid rgba(168, 85, 247, 0.2);
  }
  .afd-mem-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-radius: 8px;
    background: rgba(10, 11, 18, 0.55);
    border: 1px solid rgba(168, 85, 247, 0.22);
    font-size: 12px;
  }
  .afd-mem-rating {
    color: #fbbf24;
    font-weight: 700;
    flex-shrink: 0;
  }
  .afd-mem-text { flex: 1; color: var(--text-main); line-height: 1.45; }
  .afd-mem-date { font-size: 11px; color: var(--text-muted); flex-shrink: 0; }

  .detail-body-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 18px 22px 28px;
  }
  .split-preview-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
    align-items: start;
  }
  .orig-pages-pane, .md-preview-pane, .md-preview-single {
    background: rgba(12, 15, 26, 0.72);
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    overflow: hidden;
  }
  .pane-cap {
    padding: 11px 16px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    background: rgba(8, 10, 18, 0.55);
    border-bottom: 1px solid var(--glass-border);
  }
  .orig-pages-list {
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    max-height: 78vh;
    overflow-y: auto;
  }
  .orig-page-card {
    position: relative;
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 6px;
  }
  .orig-page-card img { width: 100%; display: block; border-radius: 8px; }
  .page-img-fallback {
    padding: 36px 16px;
    text-align: center;
    font-size: 12.5px;
    color: var(--text-muted);
  }
  .page-num-pill {
    position: absolute;
    top: 12px;
    left: 12px;
    font-family: 'Outfit', 'Inter', sans-serif;
    background: rgba(10, 11, 18, 0.86);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #f8fafc;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 3px 9px;
    border-radius: 8px;
  }
  .rendered-md-content {
    padding: 20px 22px;
    line-height: 1.72;
    font-size: 14px;
    color: var(--text-main);
  }
  .md-preview-pane .rendered-md-content {
    max-height: 78vh;
    overflow-y: auto;
  }
  .rendered-md-content :global(.kb-md-h1) { font-size: 19px; font-weight: 700; color: #c7d2fe; margin: 16px 0 8px; }
  .rendered-md-content :global(.kb-md-h2) { font-size: 16.5px; font-weight: 700; color: #f8fafc; margin: 14px 0 6px; }
  .rendered-md-content :global(.kb-md-h3) { font-size: 14.5px; font-weight: 600; color: #e2e8f0; margin: 12px 0 5px; }
  .rendered-md-content :global(.kb-md-p) { margin-bottom: 6px; }
  .rendered-md-content :global(.kb-md-spacer) { height: 8px; }
  .rendered-md-content :global(.kb-md-hr) { border: none; border-top: 1px solid var(--glass-border); margin: 14px 0; }
  .rendered-md-content :global(.kb-md-li) { padding-left: 14px; margin-bottom: 4px; }
  .rendered-md-content :global(.kb-md-ol) { display: flex; gap: 8px; padding-left: 10px; margin-bottom: 4px; }
  .rendered-md-content :global(.kb-ol-num) { color: #a5b4fc; font-weight: 600; }
  .rendered-md-content :global(.kb-inline-code) {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    padding: 2px 6px;
    border-radius: 8px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 12.5px;
  }
  .rendered-md-content :global(.kb-code-block) {
    background: #0a0b12;
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 12px 14px;
    margin: 12px 0;
    overflow-x: auto;
  }
  .rendered-md-content :global(.kb-code-lang) {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 11px;
    color: #a5b4fc;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .rendered-md-content :global(.kb-code-block pre) { margin: 0; color: #cbd5e1; font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 12.5px; }
  .rendered-md-content :global(.kb-md-table-wrap) { overflow-x: auto; margin: 12px 0; border-radius: 12px; border: 1px solid var(--glass-border); }
  .rendered-md-content :global(.kb-md-table) { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
  .rendered-md-content :global(.kb-md-table th) { background: rgba(30, 41, 59, 0.85); padding: 9px 12px; border-bottom: 1px solid var(--glass-border); border-right: 1px solid var(--glass-border); color: #f8fafc; font-weight: 600; }
  .rendered-md-content :global(.kb-md-table td) { padding: 9px 12px; border-bottom: 1px solid var(--glass-border); border-right: 1px solid var(--glass-border); vertical-align: top; }
  .rendered-md-content :global(.kb-toc-row) { display: flex; align-items: baseline; gap: 8px; padding: 2px 0; }
  .rendered-md-content :global(.kb-toc-dots) { flex: 1; border-bottom: 1px dotted rgba(255, 255, 255, 0.25); min-width: 20px; }
  .rendered-md-content :global(.kb-toc-page) { font-family: 'Outfit', 'Inter', sans-serif; color: #a5b4fc; font-weight: 600; font-variant-numeric: tabular-nums; }

  /* Edit & Chunks Panes */
  .edit-doc-pane, .chunks-pane { display: flex; flex-direction: column; gap: 12px; }
  .edit-toolbar, .chunks-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .edit-status-left { display: flex; align-items: center; gap: 10px; }
  .shortcut-hint {
    font-family: 'Outfit', 'Inter', sans-serif;
    font-size: 11px;
    color: var(--text-muted);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    padding: 2px 8px;
    border-radius: 8px;
  }
  .edit-btns { display: flex; gap: 8px; }
  .full-editor { min-height: 540px; }
  .chunk-count-lbl, .char-counter {
    font-family: 'Outfit', 'Inter', 'Prompt', sans-serif;
    font-size: 12px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .chunks-grid { display: flex; flex-direction: column; gap: 10px; }
  .chunk-card {
    background: var(--surface-card, rgba(18, 20, 28, 0.72));
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color 0.18s ease;
  }
  .chunk-card.chunk-matched {
    border-color: rgba(99, 102, 241, 0.65);
    background: rgba(99, 102, 241, 0.1);
  }
  .chunk-head { display: flex; align-items: center; gap: 8px; font-size: 12px; }
  .chunk-badge {
    font-family: 'Outfit', 'Inter', sans-serif;
    background: rgba(99, 102, 241, 0.18);
    color: #c7d2fe;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 8px;
  }
  .chunk-len { font-family: 'Outfit', 'Inter', sans-serif; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .btn-copy-chunk {
    margin-left: auto;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-family: inherit;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: color 0.16s ease, border-color 0.16s ease;
  }
  .btn-copy-chunk:hover { color: #ffffff; border-color: var(--primary); }
  .chunk-text { margin: 0; font-size: 13px; line-height: 1.6; color: #cbd5e1; white-space: pre-wrap; }

  /* Manual Add Card & Forms */
  .manual-form-card {
    background: var(--surface-card, rgba(18, 20, 28, 0.72));
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 22px 24px;
    display: flex;
    flex-direction: column;
    gap: 15px;
  }
  .form-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .form-group { display: flex; flex-direction: column; gap: 6px; }
  .form-group label { font-size: 12.5px; font-weight: 500; color: #cbd5e1; }
  .label-between { display: flex; align-items: center; justify-content: space-between; }
  .req { color: var(--danger); }
  .form-input {
    width: 100%;
    box-sizing: border-box;
    padding: 10px 14px;
    background: rgba(8, 10, 18, 0.6);
    border: 1px solid var(--glass-border-light);
    border-radius: 12px;
    color: var(--text-main);
    font-family: inherit;
    font-size: 13.5px;
    outline: none;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
  }
  .form-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.22); }
  .code-textarea {
    font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Prompt', monospace;
    font-size: 13px;
    line-height: 1.65;
    resize: vertical;
  }
  .import-file-label { cursor: pointer; }
  .manual-form-footer { display: flex; justify-content: flex-end; gap: 10px; padding-top: 8px; border-top: 1px solid var(--glass-border); }

  .golden-toggle-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border);
    transition: background-color 0.2s ease, border-color 0.2s ease;
  }
  .golden-toggle-card.active {
    background: rgba(245, 158, 11, 0.08);
    border-color: rgba(245, 158, 11, 0.4);
  }
  .gt-title { font-size: 13px; font-weight: 600; color: var(--text-main); }
  .gt-sub { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; }
  .toggle-wrap { position: relative; display: inline-flex; cursor: pointer; }
  .toggle-wrap input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  .toggle-track {
    width: 42px;
    height: 22px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.16);
    position: relative;
    transition: background-color 0.2s ease, box-shadow 0.2s ease;
  }
  .toggle-wrap input:focus-visible + .toggle-track {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }
  .toggle-wrap input:checked + .toggle-track { background: linear-gradient(135deg, #f59e0b, var(--secondary)); }
  .toggle-thumb {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #ffffff;
    position: absolute;
    top: 2px;
    left: 2px;
    transition: transform 0.24s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .toggle-wrap input:checked + .toggle-track .toggle-thumb { transform: translateX(20px); }

  /* Shared Buttons & States */
  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #ffffff;
    padding: 9px 18px;
    border-radius: 12px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
  }
  .btn-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(99, 102, 241, 0.5);
    filter: brightness(1.06);
  }
  .btn-primary:active:not(:disabled) { transform: translateY(0); }
  .btn-primary:disabled { opacity: 0.45; cursor: not-allowed; }

  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-main);
    padding: 8px 13px;
    border-radius: 12px;
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
  }
  .btn-ghost:hover:not(:disabled) { background: rgba(255, 255, 255, 0.1); border-color: var(--glass-border-light); }
  .btn-ghost.danger-outline:hover { background: rgba(244, 63, 94, 0.15); border-color: rgba(244, 63, 94, 0.45); color: #fda4af; }
  .btn-xs { padding: 6px 10px; font-size: 11.5px; border-radius: 8px; }
  .btn-danger {
    background: linear-gradient(135deg, #e11d48, #f43f5e);
    border: none;
    color: #ffffff;
    padding: 9px 18px;
    border-radius: 12px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.18s ease, filter 0.18s ease;
  }
  .btn-danger:hover:not(:disabled) { transform: translateY(-1px); filter: brightness(1.08); }

  .center-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 48px 24px;
    text-align: center;
    color: var(--text-muted);
  }
  .empty-svg-box {
    width: 60px;
    height: 60px;
    border-radius: 20px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: var(--primary-soft-text);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .cs-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-main); }
  .cs-sub { margin: 0; font-size: 12.5px; max-width: 380px; line-height: 1.5; }
  .truncate { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ── Animations ── */
  .kb-spinner {
    width: 26px;
    height: 26px;
    border: 2.5px solid rgba(99, 102, 241, 0.22);
    border-top-color: var(--secondary);
    border-radius: 50%;
    animation: kbSpin 0.8s linear infinite;
  }
  .spin-icon { animation: kbSpin 0.85s linear infinite; }
  .stage-in { animation: kbStageIn 0.28s cubic-bezier(0.16, 1, 0.3, 1) both; }
  .stagger-item {
    animation: kbCardIn 0.34s cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--stagger-i, 0) * 32ms);
  }

  @keyframes kbSpin { to { transform: rotate(360deg); } }
  @keyframes kbStageIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes kbCardIn {
    from { opacity: 0; transform: translateY(10px) scale(0.985); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
  @keyframes kbBarGrow {
    from { transform: scaleX(0); }
    to { transform: scaleX(1); }
  }
  @keyframes kbStarPop {
    0% { transform: scale(1); }
    45% { transform: scale(1.28); }
    100% { transform: scale(1); }
  }
  @keyframes kbShimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  @keyframes kbModalBackdropIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes kbModalPopIn {
    from { opacity: 0; transform: translateY(12px) scale(0.96); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  /* Modals */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(5, 7, 15, 0.78);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    padding: 20px;
    animation: kbModalBackdropIn 0.18s ease-out both;
  }
  .modal-content {
    background: linear-gradient(165deg, rgba(24, 27, 44, 0.97), rgba(15, 17, 29, 0.99));
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: 20px;
    width: 94%;
    max-width: 500px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.55);
    overflow: visible;
    animation: kbModalPopIn 0.24s cubic-bezier(0.16, 1, 0.3, 1) both;
  }
  .modal-sm { max-width: 420px; }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid var(--glass-border);
  }
  .modal-header h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--text-main); }
  .danger-title { color: #fda4af !important; }
  .btn-close {
    min-width: 30px;
    min-height: 30px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.16s ease, color 0.16s ease;
  }
  .btn-close:hover { color: #ffffff; background: rgba(244, 63, 94, 0.15); }
  .modal-body { padding: 18px 20px; display: flex; flex-direction: column; gap: 14px; }
  .modal-footer { padding: 14px 20px; border-top: 1px solid var(--glass-border); display: flex; justify-content: flex-end; gap: 10px; }
  .confirm-msg { margin: 0; font-size: 13.5px; color: var(--text-main); line-height: 1.55; }
  .confirm-warn { margin: 0; font-size: 12.5px; color: #fda4af; background: rgba(244, 63, 94, 0.1); border: 1px solid rgba(244, 63, 94, 0.25); padding: 10px 12px; border-radius: 12px; }

  /* Focus Rings */
  button:focus-visible, .kdc-open-trigger:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }

  @media (max-width: 1024px) {
    .split-preview-grid { grid-template-columns: 1fr; }
    .kb-sidebar { width: 230px; }
  }
  @media (max-width: 768px) {
    .kb-shell { flex-direction: column; }
    .kb-sidebar { width: 100%; max-height: 300px; border-right: none; border-bottom: 1px solid var(--glass-border); }
    .kb-sidebar.collapsed { max-height: 0; width: 100%; border-bottom-color: transparent; }
    .kb-doc-card .kdc-btn.hover-reveal { opacity: 1; transform: none; }
    .form-grid-2 { grid-template-columns: 1fr; }
  }
  @media (prefers-reduced-motion: reduce) {
    .stage-in, .stagger-item, .kb-spinner, .spin-icon, .result-bar, .skeleton-shimmer, .skeleton-line, .modal-backdrop, .modal-content, .kdc-btn.star.is-golden {
      animation: none !important;
    }
    .kb-sidebar, .kb-doc-card, .btn-sidebar-primary, .btn-primary, .toggle-thumb, .project-btn::before, .kdc-btn {
      transition: none !important;
    }
  }
</style>
