<script>
  import { onMount } from 'svelte';
  import { toast } from './toastStore.js';
  import CustomSelect from './CustomSelect.svelte';

  const projectStatusOptions = [
    { value: 'Active', label: 'Active (เปิดใช้งาน)' },
    { value: 'Inactive', label: 'Inactive (ปิดชั่วคราว)' }
  ];

  const sortOptions = [
    { value: 'recent', label: 'เรียงตามล่าสุด' },
    { value: 'name', label: 'เรียงตามชื่อ (ก-ฮ / A-Z)' },
    { value: 'docs', label: 'เอกสารมากสุด' }
  ];

  const pageSizeSelectOptions = [
    { value: 5, label: '5 / หน้า' },
    { value: 10, label: '10 / หน้า' },
    { value: 20, label: '20 / หน้า' },
    { value: 50, label: '50 / หน้า' }
  ];

  function trapModalFocus(node) {
    const previouslyFocused = document.activeElement;
    const focusableSelector =
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

    const focusFirst = () => {
      const focusables = node.querySelectorAll(focusableSelector);
      if (focusables.length > 0) {
        /** @type {HTMLElement} */ (focusables[0]).focus();
      }
    };
    const timer = setTimeout(focusFirst, 20);

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

  const API = '/api';

  function getAuthHeaders(customHeaders = {}) {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('jwt_token') : null;
    return {
      ...customHeaders,
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
  }

  let projects = [];
  let documents = [];
  let selectedProject = null;
  let selectedDoc = null;
  let docDetail = null;

  let expandedProjectId = null;
  let expandedDocs = [];
  let isExpanding = false;

  let isLoadingProjects = false;
  let isLoadingDocs = false;
  let isLoadingDetail = false;
  let isReindexing = false;
  let dbError = null;

  // Monotonic request sequence counters to prevent stale async responses on rapid switching
  let docsRequestSeq = 0;
  let detailRequestSeq = 0;

  // Search, Filter & Sort State
  let searchQuery = '';
  let statusFilter = 'all'; // 'all' | 'Active' | 'Inactive'
  let sortBy = 'recent'; // 'recent' | 'name' | 'docs'
  let docSearchQuery = '';
  let docFilterGolden = false;

  // Form State
  let showAddProject = false;
  let isAddingProject = false;
  let isEditMode = false;
  let editingProjectId = null;
  let newProject = {
    project_code: '',
    project_name: '',
    description: '',
    status: 'Active',
    site_urls: [],
    default_base_url: 'http://localhost:5173'
  };

  // Delete Project State
  let projectToDelete = null;
  let showDeleteProjConfirm = false;
  let isDeletingProject = false;

  // Delete Document State
  let docToDelete = null;
  let isDeletingDoc = false;

  // Pagination State
  let currentPage = 1;
  let pageSize = 10;

  // Memoized Markdown HTML so large documents do not re-parse on unrelated state updates
  $: renderedDocHtml = docDetail?.document?.content ? parseMarkdownToHtml(docDetail.document.content) : '';

  // Derived KPI Metrics
  $: totalProjectsCount = projects.length;
  $: activeProjectsCount = projects.filter((p) => (p.status || 'Active') === 'Active').length;
  $: inactiveProjectsCount = totalProjectsCount - activeProjectsCount;
  $: totalDocumentsCount = projects.reduce((acc, p) => acc + (Number(p.doc_count) || 0), 0);
  $: totalConfiguredSites = projects.reduce(
    (acc, p) => acc + ((p.site_urls || []).filter((s) => s?.url && s.url.trim()).length || (p.default_base_url ? 1 : 0)),
    0
  );

  // Filtered & Sorted Projects
  $: filteredProjects = (() => {
    const q = searchQuery.trim().toLowerCase();
    let list = projects.filter((p) => {
      if (statusFilter !== 'all' && (p.status || 'Active') !== statusFilter) return false;
      if (!q) return true;
      const inCode = String(p.project_code || '').toLowerCase().includes(q);
      const inName = String(p.name || p.project_name || '').toLowerCase().includes(q);
      const inDesc = String(p.description || '').toLowerCase().includes(q);
      const inUrl =
        String(p.default_base_url || '').toLowerCase().includes(q) ||
        (p.site_urls || []).some((s) => String(s?.url || '').toLowerCase().includes(q));
      return inCode || inName || inDesc || inUrl;
    });

    if (sortBy === 'name') {
      list = [...list].sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'th'));
    } else if (sortBy === 'docs') {
      list = [...list].sort((a, b) => (Number(b.doc_count) || 0) - (Number(a.doc_count) || 0));
    }
    return list;
  })();

  $: totalPages = Math.max(1, Math.ceil(filteredProjects.length / pageSize));
  $: if (currentPage > totalPages) currentPage = totalPages;
  $: if (currentPage < 1) currentPage = 1;
  $: pageStart = (currentPage - 1) * pageSize;
  $: pagedProjects = filteredProjects.slice(pageStart, pageStart + pageSize);
  $: pageNumbers = buildPageNumbers(currentPage, totalPages);

  $: selectedProjectObj = projects.find((p) => p.id === selectedProject) || null;

  $: filteredDocuments = (() => {
    const q = docSearchQuery.trim().toLowerCase();
    return documents.filter((d) => {
      if (docFilterGolden && !d.is_golden_data) return false;
      if (!q) return true;
      return (
        String(d.name || d.filename || '').toLowerCase().includes(q) ||
        String(d.doc_category || '').toLowerCase().includes(q)
      );
    });
  })();

  function buildPageNumbers(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages = [1];
    const start = Math.max(2, current - 1);
    const end = Math.min(total - 1, current + 1);
    if (start > 2) pages.push('...');
    for (let i = start; i <= end; i++) pages.push(i);
    if (end < total - 1) pages.push('...');
    pages.push(total);
    return pages;
  }

  function goToPage(page) {
    if (page < 1 || page > totalPages || page === currentPage) return;
    currentPage = page;
    expandedProjectId = null;
  }

  function onPageSizeChange() {
    currentPage = 1;
    expandedProjectId = null;
  }

  function handleWindowKeydown(e) {
    if (e.key === 'Escape') {
      if (showAddProject && !isAddingProject) showAddProject = false;
      if (showDeleteProjConfirm && !isDeletingProject) showDeleteProjConfirm = false;
      if (docToDelete && !isDeletingDoc) docToDelete = null;
    }
  }

  onMount(async () => {
    await loadProjects();
  });

  async function loadProjects() {
    isLoadingProjects = true;
    try {
      const r = await fetch(`${API}/projects`, { headers: getAuthHeaders() });
      const d = await r.json();
      if (r.ok && d.success) {
        projects = d.projects || [];
        dbError = null;
      } else {
        dbError = d.error || 'ไม่สามารถโหลดรายชื่อโครงการได้';
      }
    } catch {
      dbError = 'ไม่สามารถเชื่อมต่อฐานข้อมูลได้ กรุณาตรวจสอบสถานะเซิร์ฟเวอร์';
    } finally {
      isLoadingProjects = false;
    }
  }

  async function loadDocuments(projectId) {
    const reqId = ++docsRequestSeq;
    isLoadingDocs = true;
    selectedDoc = null;
    docDetail = null;
    docSearchQuery = '';
    docFilterGolden = false;
    try {
      const url = `${API}/kb/documents?project_id=${encodeURIComponent(projectId)}&limit=200`;
      const r = await fetch(url, { headers: getAuthHeaders() });
      const d = await r.json();
      if (reqId !== docsRequestSeq) return;
      if (r.ok && d.success) {
        documents = d.documents || [];
      } else {
        documents = [];
        toast(d.error || 'โหลดรายการเอกสารไม่สำเร็จ', 'error');
      }
    } catch {
      if (reqId !== docsRequestSeq) return;
      documents = [];
      toast('โหลดเอกสารไม่สำเร็จ', 'error');
    } finally {
      if (reqId === docsRequestSeq) isLoadingDocs = false;
    }
  }

  async function loadDocDetail(docId) {
    const reqId = ++detailRequestSeq;
    isLoadingDetail = true;
    selectedDoc = docId;
    docDetail = null;
    try {
      const r = await fetch(`${API}/kb/documents/${encodeURIComponent(docId)}`, {
        headers: getAuthHeaders()
      });
      const d = await r.json();
      if (reqId !== detailRequestSeq) return;
      if (r.ok && d.success) {
        docDetail = d;
      } else {
        toast(d.error || 'โหลดรายละเอียดเอกสารไม่สำเร็จ', 'error');
      }
    } catch {
      if (reqId !== detailRequestSeq) return;
      toast('เกิดข้อผิดพลาดในการโหลดรายละเอียดเอกสาร', 'error');
    } finally {
      if (reqId === detailRequestSeq) isLoadingDetail = false;
    }
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
      return;
    }
    expandedProjectId = p.id;
    isExpanding = true;
    try {
      const r = await fetch(`${API}/kb/documents?project_id=${encodeURIComponent(p.id)}&limit=100`, {
        headers: getAuthHeaders()
      });
      const d = await r.json();
      if (expandedProjectId === p.id) {
        expandedDocs = r.ok && d.success ? d.documents || [] : [];
      }
    } catch {
      if (expandedProjectId === p.id) expandedDocs = [];
    } finally {
      isExpanding = false;
    }
  }

  function selectSubDoc(doc, p, event) {
    event.stopPropagation();
    selectedProject = p.id;
    documents = expandedDocs;
    loadDocDetail(doc.id);
  }

  async function copyText(text, label = 'URL') {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      toast(`คัดลอก ${label} เรียบร้อยแล้ว`, 'success', 2000);
    } catch {
      toast(`ไม่สามารถคัดลอก ${label} ได้`, 'error');
    }
  }

  function isValidHttpUrl(val) {
    if (!val || !val.trim()) return true; // optional blank row
    return /^https?:\/\/.+/i.test(val.trim());
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
    let sites =
      p.site_urls && Array.isArray(p.site_urls) && p.site_urls.length > 0
        ? JSON.parse(JSON.stringify(p.site_urls))
        : [
            { env_type: 'TEST', url: p.default_base_url || 'http://localhost:5173', is_default: true },
            { env_type: 'UAT', url: '', is_default: false },
            { env_type: 'PRD', url: '', is_default: false }
          ];

    if (!sites.some((s) => s.is_default)) {
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
      is_default: i === index
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
    const trimmedName = newProject.project_name.trim();
    if (!trimmedName) {
      toast('กรุณาระบุชื่อโครงการ', 'error');
      return;
    }

    // Validate all non-empty URLs before submitting
    const invalidSite = (newProject.site_urls || []).find((s) => s.url && s.url.trim() && !isValidHttpUrl(s.url));
    if (invalidSite) {
      toast(`URL ของ ${invalidSite.env_type} ต้องขึ้นต้นด้วย http:// หรือ https://`, 'error');
      return;
    }

    const validSites = (newProject.site_urls || [])
      .map((s) => ({ ...s, url: (s.url || '').trim() }))
      .filter((s) => s.url.length > 0);

    let defaultUrl = 'http://localhost:5173';
    if (validSites.length > 0) {
      if (!validSites.some((s) => s.is_default)) validSites[0].is_default = true;
      const defSite = validSites.find((s) => s.is_default) || validSites[0];
      defaultUrl = defSite.url;
    }

    const payload = {
      project_code: (newProject.project_code || '').trim(),
      project_name: trimmedName,
      description: (newProject.description || '').trim(),
      status: newProject.status || 'Active',
      site_urls: validSites,
      default_base_url: defaultUrl
    };

    isAddingProject = true;
    try {
      const endpoint = isEditMode ? `${API}/projects/${editingProjectId}` : `${API}/projects`;
      const method = isEditMode ? 'PUT' : 'POST';

      const r = await fetch(endpoint, {
        method,
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      if (r.ok && d.success) {
        toast(isEditMode ? 'อัปเดตโครงการสำเร็จ' : 'สร้างโครงการสำเร็จ', 'success');
        showAddProject = false;
        await loadProjects();
        if (selectedProject === editingProjectId) {
          loadDocuments(selectedProject);
        }
      } else {
        toast(d.error || (isEditMode ? 'อัปเดตโครงการไม่สำเร็จ' : 'สร้างโครงการไม่สำเร็จ'), 'error');
      }
    } catch (e) {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ: ' + (e?.message || ''), 'error');
    } finally {
      isAddingProject = false;
    }
  }

  function confirmDeleteProject(p) {
    projectToDelete = p;
    showDeleteProjConfirm = true;
  }

  async function executeDeleteProject() {
    if (!projectToDelete) return;
    isDeletingProject = true;
    try {
      const res = await fetch(`${API}/projects/${projectToDelete.id}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('ลบโครงการและเอกสารทั้งหมดสำเร็จ', 'success');
        if (selectedProject === projectToDelete.id) {
          selectedProject = null;
          documents = [];
          docDetail = null;
        }
        if (expandedProjectId === projectToDelete.id) {
          expandedProjectId = null;
          expandedDocs = [];
        }
        await loadProjects();
      } else {
        toast(data.error || 'ลบโครงการไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการเชื่อมต่อ', 'error');
    } finally {
      isDeletingProject = false;
      showDeleteProjConfirm = false;
      projectToDelete = null;
    }
  }

  async function reindexSelectedProject() {
    if (!selectedProject || isReindexing) return;
    isReindexing = true;
    try {
      const res = await fetch(`${API}/kb/reindex`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ project_id: selectedProject })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.message || 'อัปเดต Vector Index ของโครงการเรียบร้อยแล้ว', 'success');
        await loadDocuments(selectedProject);
      } else {
        toast(data.error || 'ไม่สามารถ Re-index โครงการได้', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการ Re-index โครงการ', 'error');
    } finally {
      isReindexing = false;
    }
  }

  async function executeDeleteDocument() {
    if (!docToDelete || isDeletingDoc) return;
    isDeletingDoc = true;
    const targetId = docToDelete.id;
    try {
      const res = await fetch(`${API}/kb/documents/${encodeURIComponent(targetId)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast('ลบเอกสารเรียบร้อยแล้ว', 'success');
        if (selectedDoc === targetId) {
          selectedDoc = null;
          docDetail = null;
        }
        documents = documents.filter((d) => d.id !== targetId);
        expandedDocs = expandedDocs.filter((d) => d.id !== targetId);
        await loadProjects();
      } else {
        toast(data.error || 'ลบเอกสารไม่สำเร็จ', 'error');
      }
    } catch {
      toast('เกิดข้อผิดพลาดในการลบเอกสาร', 'error');
    } finally {
      isDeletingDoc = false;
      docToDelete = null;
    }
  }

  function formatDate(val) {
    if (!val) return '—';
    return new Date(val).toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' });
  }

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
    // Escape ALL HTML first to eliminate XSS, then apply safe Markdown inline formatting
    let safe = escapeHtml(rawLine);
    safe = safe.replace(/(?:\.\s*){5,}\./g, ' ... ');
    safe = safe.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    safe = safe.replace(/`([^`]+)`/g, '<code class="pm-inline-code">$1</code>');
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
            `<div class="pm-code-block"><div class="pm-code-lang">${codeLanguage || 'code'}</div><pre><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre></div>`
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
          if (!cells.every((c) => c === '')) {
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

      if (line === '') {
        html.push('<div class="pm-md-spacer"></div>');
      } else if (line === '---' || line === '***') {
        html.push('<hr class="pm-md-hr" />');
      } else if (line.startsWith('### ')) {
        html.push(`<h3 class="pm-md-h3">${formatSafeInlineMarkdown(line.substring(4))}</h3>`);
      } else if (line.startsWith('## ')) {
        html.push(`<h2 class="pm-md-h2">${formatSafeInlineMarkdown(line.substring(3))}</h2>`);
      } else if (line.startsWith('# ')) {
        html.push(`<h1 class="pm-md-h1">${formatSafeInlineMarkdown(line.substring(2))}</h1>`);
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        html.push(`<div class="pm-md-li">• ${formatSafeInlineMarkdown(line.substring(2))}</div>`);
      } else if (/^(.+?)\s+\.\.\.\s+(\d+|[IVXLCDM]+)$/i.test(line)) {
        const tocMatch = line.match(/^(.+?)\s+\.\.\.\s+(\d+|[IVXLCDM]+)$/i);
        html.push(
          `<div class="pm-toc-row"><span class="pm-toc-title">${formatSafeInlineMarkdown(tocMatch[1])}</span><span class="pm-toc-dots"></span><span class="pm-toc-page">${escapeHtml(tocMatch[2])}</span></div>`
        );
      } else if (/^\d+\.\s/.test(line)) {
        const match = line.match(/^(\d+)\.\s(.*)/);
        if (match) {
          html.push(`<div class="pm-md-ol"><span class="pm-ol-num">${escapeHtml(match[1])}.</span><span>${formatSafeInlineMarkdown(match[2])}</span></div>`);
        } else {
          html.push(`<div class="pm-md-p">${formatSafeInlineMarkdown(line)}</div>`);
        }
      } else {
        html.push(`<div class="pm-md-p">${formatSafeInlineMarkdown(line)}</div>`);
      }
    }

    if (inTable) html.push(renderHtmlTable(tableHeaders, tableRows));
    if (inCodeBlock) {
      html.push(
        `<div class="pm-code-block"><pre><code>${escapeHtml(codeBlockContent.join('\n'))}</code></pre></div>`
      );
    }

    return html.join('\n');
  }

  function renderHtmlTable(headers, rows) {
    const html = ['<div class="pm-md-table-wrap"><table class="pm-md-table">'];
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

<div class="pm-wrapper">
  <!-- Header & Action Row -->
  <div class="pm-header">
    <div class="pm-header-left">
      <h2>การจัดการโครงการ (Project Management)</h2>
      <p>สร้าง แก้ไข จัดการสภาพแวดล้อม (TEST / UAT / PRD) และตรวจสอบคลังเอกสารในแต่ละโครงการ</p>
    </div>
    <div class="pm-header-actions">
      <button type="button" class="btn-ghost" on:click={loadProjects} disabled={isLoadingProjects} title="รีเฟรชข้อมูลโครงการ">
        <svg class:spin-icon={isLoadingProjects} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
        <span>รีเฟรช</span>
      </button>
      <button type="button" class="btn-primary" on:click={openAddProject}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        <span>สร้างโครงการ</span>
      </button>
    </div>
  </div>

  <!-- 4-Card KPI Overview Ribbon -->
  <div class="pm-kpi-grid">
    <div class="kpi-tile">
      <div class="kpi-icon indigo">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18">
          <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
        </svg>
      </div>
      <div class="kpi-body">
        <span class="kpi-val">{totalProjectsCount}</span>
        <span class="kpi-lbl">โครงการทั้งหมด</span>
      </div>
    </div>

    <div class="kpi-tile">
      <div class="kpi-icon emerald">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div class="kpi-body">
        <span class="kpi-val">{activeProjectsCount} <span class="kpi-sub-num">/ {inactiveProjectsCount} ปิด</span></span>
        <span class="kpi-lbl">สถานะ Active</span>
      </div>
    </div>

    <div class="kpi-tile">
      <div class="kpi-icon violet">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
        </svg>
      </div>
      <div class="kpi-body">
        <span class="kpi-val">{totalDocumentsCount}</span>
        <span class="kpi-lbl">เอกสารในฐานความรู้</span>
      </div>
    </div>

    <div class="kpi-tile">
      <div class="kpi-icon cyan">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253" />
        </svg>
      </div>
      <div class="kpi-body">
        <span class="kpi-val">{totalConfiguredSites}</span>
        <span class="kpi-lbl">Target Sites (TEST/UAT/PRD)</span>
      </div>
    </div>
  </div>

  <div class="pm-grid">
    <!-- Left Panel: Project Table -->
    <div class="left-panel glass-card">
      <div class="panel-header toolbar-stack">
        <div class="panel-header-top">
          <h3 class="panel-title" aria-live="polite">รายชื่อโครงการ ({filteredProjects.length}{#if filteredProjects.length !== projects.length} / {projects.length}{/if})</h3>
          <div class="filter-pills" role="group" aria-label="กรองสถานะโครงการ">
            {#each [['all', 'ทั้งหมด'], ['Active', 'Active'], ['Inactive', 'Inactive']] as [val, lbl]}
              <button
                type="button"
                class="pill-btn"
                class:active={statusFilter === val}
                aria-pressed={statusFilter === val}
                on:click={() => { statusFilter = val; currentPage = 1; }}
              >{lbl}</button>
            {/each}
          </div>
        </div>
        <div class="panel-search-row">
          <div class="search-input-wrap">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              bind:value={searchQuery}
              on:input={() => (currentPage = 1)}
              placeholder="ค้นหารหัสโครงการ, ชื่อ, คำอธิบาย หรือ URL..."
              aria-label="ค้นหาโครงการ"
            />
            {#if searchQuery}
              <button type="button" class="clear-search-btn" on:click={() => { searchQuery = ''; currentPage = 1; }} aria-label="ล้างคำค้นหา">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </button>
            {/if}
          </div>
          <div class="sort-select-wrap">
            <CustomSelect
              id="pm-sort-select"
              bind:value={sortBy}
              options={sortOptions}
              width="190px"
            />
          </div>
        </div>
      </div>

      {#if dbError}
        <div class="error-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="22" height="22">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <span>{dbError}</span>
          <button type="button" class="btn-ghost" on:click={loadProjects}>ลองเชื่อมต่อใหม่</button>
        </div>
      {:else}
        <div class="table-responsive">
          <table class="pm-table">
            <thead>
              <tr>
                <th class="col-expand"></th>
                <th class="col-code">รหัส</th>
                <th>ชื่อโครงการ &amp; Target Sites</th>
                <th class="col-docs">เอกสาร</th>
                <th class="col-status">สถานะ</th>
                <th class="col-actions">จัดการ</th>
              </tr>
            </thead>
            <tbody>
              {#if isLoadingProjects && projects.length === 0}
                <tr>
                  <td colspan="6" class="empty-table">กำลังโหลดรายชื่อโครงการ...</td>
                </tr>
              {:else}
                {#each pagedProjects as p (p.id)}
                  <tr
                    class:selected={selectedProject === p.id}
                    tabindex="0"
                    aria-selected={selectedProject === p.id}
                    on:click={() => selectProject(p)}
                    on:keydown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        selectProject(p);
                      }
                    }}
                  >
                    <td class="col-expand" on:click|stopPropagation>
                      <button
                        type="button"
                        class="btn-expand"
                        class:expanded={expandedProjectId === p.id}
                        aria-label={expandedProjectId === p.id ? 'ซ่อนรายการเอกสาร' : 'แสดงรายการเอกสาร'}
                        on:click={(e) => toggleExpand(p, e)}
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="13" height="13">
                          <polyline points="9 18 15 12 9 6"></polyline>
                        </svg>
                      </button>
                    </td>
                    <td class="col-code">
                      <span class="code-pill">{p.project_code || '—'}</span>
                    </td>
                    <td class="proj-name">
                      <div class="proj-title-line truncate" title={p.name}>{p.name}</div>
                      {#if p.description}
                        <div class="proj-desc truncate" title={p.description}>{p.description}</div>
                      {/if}
                      {#if p.site_urls && p.site_urls.length > 0}
                        <div class="proj-sites-tags">
                          {#each p.site_urls as s}
                            {#if s.url}
                              <button
                                type="button"
                                class="site-tag-pill"
                                class:is-default={s.is_default}
                                title={`คลิกเพื่อคัดลอก ${s.env_type}: ${s.url}${s.is_default ? ' (Default Site)' : ''}`}
                                on:click|stopPropagation={() => copyText(s.url, `${s.env_type} URL`)}
                              >
                                <span class="env-badge env-{s.env_type ? s.env_type.toLowerCase() : 'test'}">{s.env_type || 'TEST'}</span>
                                <span class="url-text truncate">{s.url}</span>
                                {#if s.is_default}
                                  <svg class="star-svg" viewBox="0 0 24 24" fill="currentColor" width="10" height="10" aria-label="Default Site">
                                    <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
                                  </svg>
                                {/if}
                              </button>
                            {/if}
                          {/each}
                        </div>
                      {:else if p.default_base_url}
                        <div class="proj-sites-tags">
                          <button
                            type="button"
                            class="site-tag-pill is-default"
                            title={`คลิกเพื่อคัดลอก: ${p.default_base_url}`}
                            on:click|stopPropagation={() => copyText(p.default_base_url, 'URL')}
                          >
                            <span class="env-badge env-test">TEST</span>
                            <span class="url-text truncate">{p.default_base_url}</span>
                          </button>
                        </div>
                      {/if}
                    </td>
                    <td class="col-docs">
                      <span class="doc-count-chip" class:has-docs={(p.doc_count || 0) > 0}>
                        {p.doc_count || 0} รายการ
                      </span>
                    </td>
                    <td class="col-status">
                      <span class="status-badge" class:active={(p.status || 'Active') === 'Active'}>
                        <span class="status-dot"></span>
                        {p.status || 'Active'}
                      </span>
                    </td>
                    <td class="actions-cell" on:click|stopPropagation>
                      <div class="actions-wrapper">
                        <button type="button" class="btn-icon edit" on:click={() => openEditProject(p)} title="แก้ไขโครงการ" aria-label={`แก้ไขโครงการ ${p.name}`}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" width="15" height="15">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                          </svg>
                        </button>
                        <button type="button" class="btn-icon delete" on:click={() => confirmDeleteProject(p)} title="ลบโครงการ" aria-label={`ลบโครงการ ${p.name}`}>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" width="15" height="15">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                  {#if expandedProjectId === p.id}
                    <tr class="expanded-row">
                      <td colspan="6">
                        <div class="expanded-content">
                          {#if isExpanding}
                            <div class="sub-loading">กำลังโหลดเอกสารในโครงการ...</div>
                          {:else if expandedDocs.length > 0}
                            <div class="sub-doc-list">
                              {#each expandedDocs as doc}
                                <button type="button" class="sub-doc-item" class:active={selectedDoc === doc.id} on:click={(e) => selectSubDoc(doc, p, e)}>
                                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                                  </svg>
                                  <span class="truncate">{doc.name}</span>
                                  {#if doc.is_golden_data}
                                    <span class="mini-golden-tag">Golden</span>
                                  {/if}
                                  <span class="sub-doc-cat">{doc.doc_category || 'Reference'}</span>
                                </button>
                              {/each}
                            </div>
                          {:else}
                            <div class="sub-empty">ยังไม่มีเอกสารในโครงการนี้</div>
                          {/if}
                        </div>
                      </td>
                    </tr>
                  {/if}
                {/each}
                {#if filteredProjects.length === 0}
                  <tr>
                    <td colspan="6" class="empty-table">
                      {projects.length === 0 ? 'ยังไม่มีโครงการในระบบ กด "+ สร้างโครงการ" เพื่อเริ่มต้น' : 'ไม่พบโครงการที่ตรงกับเงื่อนไขการค้นหา'}
                    </td>
                  </tr>
                {/if}
              {/if}
            </tbody>
          </table>
        </div>

        {#if filteredProjects.length > 0}
          <div class="pagination-bar">
            <div class="pagination-info">
              แสดง {pageStart + 1}–{Math.min(pageStart + pageSize, filteredProjects.length)} จาก {filteredProjects.length} รายการ
            </div>
            <div class="pagination-controls">
              <button type="button" class="page-btn" on:click={() => goToPage(1)} disabled={currentPage === 1} title="หน้าแรก">«</button>
              <button type="button" class="page-btn" on:click={() => goToPage(currentPage - 1)} disabled={currentPage === 1} title="ก่อนหน้า">‹</button>
              {#each pageNumbers as n}
                {#if n === '...'}
                  <span class="page-ellipsis">…</span>
                {:else}
                  <button type="button" class="page-btn" class:active={n === currentPage} on:click={() => goToPage(n)}>{n}</button>
                {/if}
              {/each}
              <button type="button" class="page-btn" on:click={() => goToPage(currentPage + 1)} disabled={currentPage === totalPages} title="ถัดไป">›</button>
              <button type="button" class="page-btn" on:click={() => goToPage(totalPages)} disabled={currentPage === totalPages} title="หน้าสุดท้าย">»</button>
            </div>
            <div class="page-size">
              <CustomSelect
                id="pm-page-size"
                bind:value={pageSize}
                options={pageSizeSelectOptions}
                width="108px"
                on:change={onPageSizeChange}
              />
            </div>
          </div>
        {/if}
      {/if}
    </div>

    <!-- Right Panel: Project Inspector & Document Viewer -->
    <div class="right-panel glass-card">
      {#if selectedProject}
        {#if isLoadingDetail}
          <div class="loading-state-panel">
            <span class="pm-spinner"></span>
            <p>กำลังโหลดเนื้อหาเอกสาร...</p>
          </div>
        {:else if docDetail}
          <div class="doc-viewer stage-in">
            <div class="viewer-header">
              <div class="viewer-header-top">
                <button type="button" class="btn-back" on:click={() => { docDetail = null; selectedDoc = null; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <polyline points="15 18 9 12 15 6"></polyline>
                  </svg>
                  <span>กลับไปรายการเอกสาร</span>
                </button>
                <div class="viewer-actions">
                  <button
                    type="button"
                    class="btn-ghost btn-xs"
                    on:click={() => copyText(docDetail.document.content, 'Markdown เอกสาร')}
                    title="คัดลอกเนื้อหา Markdown"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                    <span>คัดลอก MD</span>
                  </button>
                </div>
              </div>
              <div class="viewer-title-row">
                <h3 class="viewer-title truncate" title={docDetail.document.filename || docDetail.document.title || 'เอกสาร'}>
                  {docDetail.document.filename || docDetail.document.title || 'เอกสาร'}
                </h3>
                {#if docDetail.document.is_golden_data}
                  <span class="golden-badge-lg">Golden Data</span>
                {/if}
              </div>
            </div>

            <div class="viewer-meta">
              <div class="meta-item"><span class="lbl">หมวดหมู่:</span> <span class="val">{docDetail.document.doc_category || 'General'}</span></div>
              <div class="meta-item"><span class="lbl">Chunks:</span> <span class="val">{docDetail.chunks?.length || 0}</span></div>
              <div class="meta-item"><span class="lbl">วันที่บันทึก:</span> <span class="val">{formatDate(docDetail.document.created_at)}</span></div>
            </div>

            <div class="viewer-content">
              {@html renderedDocHtml}
            </div>
          </div>
        {:else}
          <!-- Project Overview Header + Document List -->
          <div class="project-inspector-head stage-in">
            <div class="pi-top">
              <div class="pi-title-group">
                <span class="code-pill">{selectedProjectObj?.project_code || '—'}</span>
                <h3 class="panel-title truncate">{selectedProjectObj?.name || ''}</h3>
                <span class="status-badge" class:active={(selectedProjectObj?.status || 'Active') === 'Active'}>
                  <span class="status-dot"></span>
                  {selectedProjectObj?.status || 'Active'}
                </span>
              </div>
              <div class="pi-actions">
                <button
                  type="button"
                  class="btn-ghost btn-xs"
                  on:click={reindexSelectedProject}
                  disabled={isReindexing || documents.length === 0}
                  title="สร้าง Vector Embeddings ใหม่ให้เอกสารทั้งหมดในโครงการนี้"
                >
                  <svg class:spin-icon={isReindexing} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                    <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
                    <path d="M3 3v5h5"></path>
                    <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"></path>
                  </svg>
                  <span>{isReindexing ? 'กำลัง Re-index...' : 'Re-index'}</span>
                </button>
                {#if selectedProjectObj}
                  <button type="button" class="btn-ghost btn-xs" on:click={() => openEditProject(selectedProjectObj)}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z" />
                    </svg>
                    <span>แก้ไข</span>
                  </button>
                {/if}
              </div>
            </div>
            {#if selectedProjectObj?.description}
              <p class="pi-desc">{selectedProjectObj.description}</p>
            {/if}

            <!-- Document Filter Bar -->
            {#if documents.length > 0}
              <div class="doc-filter-bar">
                <div class="search-input-wrap compact">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                  </svg>
                  <input type="text" bind:value={docSearchQuery} placeholder="ค้นหาเอกสารในโครงการ..." aria-label="ค้นหาเอกสารในโครงการ" />
                </div>
                <button
                  type="button"
                  class="pill-btn golden-pill"
                  class:active={docFilterGolden}
                  on:click={() => (docFilterGolden = !docFilterGolden)}
                  title="แสดงเฉพาะเอกสาร Golden Data"
                >
                  <svg viewBox="0 0 24 24" fill="currentColor" width="11" height="11">
                    <path fill-rule="evenodd" d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z" clip-rule="evenodd" />
                  </svg>
                  <span>Golden Data</span>
                </button>
              </div>
            {/if}
          </div>

          {#if isLoadingDocs}
            <div class="loading-state-panel">
              <span class="pm-spinner"></span>
              <p>กำลังโหลดเอกสารในโครงการ...</p>
            </div>
          {:else if filteredDocuments.length > 0}
            <div class="doc-list stage-in">
              {#each filteredDocuments as doc (doc.id)}
                <div
                  class="doc-card"
                  role="button"
                  tabindex="0"
                  on:click={() => loadDocDetail(doc.id)}
                  on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') loadDocDetail(doc.id); }}
                >
                  <div class="doc-icon-box">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                  </div>
                  <div class="doc-info">
                    <div class="doc-name-row">
                      <span class="doc-name truncate" title={doc.name}>{doc.name}</span>
                      {#if doc.is_golden_data}
                        <span class="mini-golden-tag">Golden</span>
                      {/if}
                    </div>
                    <div class="doc-sub">
                      <span class="doc-cat-chip">{doc.doc_category || 'Reference'}</span>
                      <span>•</span>
                      <span>{doc.chunk_count || 0} chunks</span>
                      {#if doc.created_at}
                        <span>•</span>
                        <span>{formatDate(doc.created_at)}</span>
                      {/if}
                    </div>
                  </div>
                  <div class="doc-card-actions" on:click|stopPropagation>
                    <button
                      type="button"
                      class="btn-icon delete"
                      title="ลบเอกสารนี้ออกจากโครงการ"
                      aria-label={`ลบเอกสาร ${doc.name}`}
                      on:click={() => (docToDelete = doc)}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" width="14" height="14">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                </div>
              {/each}
            </div>
          {:else}
            <div class="empty-state">
              <div class="empty-svg-badge">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
              </div>
              <p class="empty-title">{documents.length === 0 ? 'ยังไม่มีเอกสารในโครงการนี้' : 'ไม่พบเอกสารที่ตรงกับตัวกรอง'}</p>
              <p class="empty-sub">อัปโหลดและสแกนเอกสารจากเมนู Scan OCR แล้วกด "บันทึกเข้า Project" เพื่อเพิ่มเอกสารที่นี่</p>
            </div>
          {/if}
        {/if}
      {:else}
        <div class="empty-state">
          <div class="empty-svg-badge accent">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="34" height="34">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
            </svg>
          </div>
          <p class="empty-title">เลือกโครงการเพื่อตรวจสอบเอกสาร</p>
          <p class="empty-sub">คลิกที่โครงการใดก็ได้จากตารางด้านซ้ายเพื่อดูรายการเอกสาร, Golden Data, เนื้อหา Markdown และจัดการ Vector Index</p>
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- ── Add/Edit Project Modal ── -->
{#if showAddProject}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-backdrop" on:click={() => { if (!isAddingProject) showAddProject = false; }} role="presentation">
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-content" use:trapModalFocus on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="pm-add-modal-title">
      <div class="modal-top-accent" aria-hidden="true"></div>
      <div class="modal-header">
        <div class="modal-head-left">
          <div class="modal-head-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="18" height="18">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
            </svg>
          </div>
          <div>
            <h3 id="pm-add-modal-title">{isEditMode ? 'แก้ไขโครงการ' : 'สร้างโครงการใหม่'}</h3>
            <p class="modal-sub">กำหนดข้อมูลโครงการและ URL ของเซิร์ฟเวอร์ทดสอบ</p>
          </div>
        </div>
        <button type="button" class="btn-close" aria-label="ปิดหน้าต่าง" on:click={() => (showAddProject = false)} disabled={isAddingProject}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="modal-grid-2">
          <div class="form-group">
            <label for="p_code">รหัสโครงการ (Project Code)</label>
            <input id="p_code" type="text" class="form-input" placeholder="เช่น PRJ-2026-001 (เว้นว่างเพื่อสร้างอัตโนมัติ)" bind:value={newProject.project_code} />
          </div>
          <div class="form-group">
            <label for="p_status">สถานะ (Status)</label>
            <CustomSelect id="p_status" bind:value={newProject.status} options={projectStatusOptions} width="100%" />
          </div>
        </div>

        <div class="form-group">
          <label for="p_name">ชื่อโครงการ (Project Name) <span class="req">*</span></label>
          <input id="p_name" type="text" class="form-input" placeholder="ระบุชื่อโครงการ..." bind:value={newProject.project_name} />
        </div>

        <div class="form-group">
          <label for="p_desc">รายละเอียด (Description)</label>
          <textarea id="p_desc" class="form-input" rows="2" placeholder="คำอธิบายขอบเขตหรือรายละเอียดโครงการ..." bind:value={newProject.description}></textarea>
        </div>

        <!-- Multi-Site Base URLs Manager -->
        <div class="form-group sites-manager-group">
          <div class="sites-manager-header">
            <span class="sites-label">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="14" height="14">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3" />
              </svg>
              <span>Target Site Base URLs (สำหรับ AI Test Agent)</span>
            </span>
            <button type="button" class="btn-add-site" on:click={addSiteUrlRow}>+ เพิ่ม Site</button>
          </div>
          <span class="sites-hint">
            รองรับเฉพาะ URL ที่ขึ้นต้นด้วย <code>http://</code> หรือ <code>https://</code> คลิกเลือก <b>Default</b> เพื่อใช้เป็น Site เริ่มต้น
          </span>

          <div class="site-urls-list">
            {#if newProject.site_urls && newProject.site_urls.length > 0}
              {#each newProject.site_urls as site, idx}
                {@const isBadUrl = site.url && site.url.trim() && !isValidHttpUrl(site.url)}
                <div class="site-url-row" class:is-default-row={site.is_default} class:is-invalid-row={isBadUrl}>
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
                    title={site.is_default ? 'Site Default หลัก' : 'คลิกเพื่อตั้งเป็น Site Default'}
                  >
                    {site.is_default ? 'Default' : 'ตั้งหลัก'}
                  </button>

                  <button
                    type="button"
                    class="btn-remove-site"
                    on:click={() => removeSiteUrlRow(idx)}
                    title="ลบ Site นี้"
                    disabled={newProject.site_urls.length <= 1}
                    aria-label="ลบ Site"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                  </button>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn-cancel" on:click={() => (showAddProject = false)} disabled={isAddingProject}>ยกเลิก</button>
        <button type="button" class="btn-submit" on:click={createProject} disabled={isAddingProject || !newProject.project_name.trim()}>
          {isAddingProject ? 'กำลังบันทึก...' : isEditMode ? 'บันทึกการแก้ไข' : 'สร้างโครงการ'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- ── Delete Project Confirm Modal ── -->
{#if showDeleteProjConfirm && projectToDelete}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="modal-backdrop" on:click={() => { if (!isDeletingProject) showDeleteProjConfirm = false; }} role="presentation">
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="modal-content modal-sm" use:trapModalFocus on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="pm-del-proj-title">
      <div class="modal-header">
        <h3 id="pm-del-proj-title" class="danger-text modal-danger-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          <span>ยืนยันการลบโครงการ</span>
        </h3>
        <button type="button" class="btn-close" on:click={() => (showDeleteProjConfirm = false)} disabled={isDeletingProject} aria-label="ปิด">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="modal-body">
        <p class="confirm-text">
          คุณต้องการลบโครงการ <strong class="confirm-highlight">"{projectToDelete.name}"</strong> ใช่หรือไม่?
        </p>
        <p class="confirm-warning-box">
          ข้อมูลเอกสาร ({projectToDelete.doc_count || 0} รายการ), Vector Chunks และภาพหน้าเอกสารทั้งหมดในโครงการนี้จะถูกลบทิ้งอย่างถาวร และไม่สามารถกู้คืนได้
        </p>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn-cancel" on:click={() => (showDeleteProjConfirm = false)} disabled={isDeletingProject}>ยกเลิก</button>
        <button type="button" class="btn-submit danger-bg" on:click={executeDeleteProject} disabled={isDeletingProject}>
          {isDeletingProject ? 'กำลังลบ...' : 'ลบโครงการถาวร'}
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
    <div class="modal-content modal-sm" use:trapModalFocus on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="pm-del-doc-title">
      <div class="modal-header">
        <h3 id="pm-del-doc-title" class="danger-text modal-danger-title">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          <span>ยืนยันการลบเอกสาร</span>
        </h3>
        <button type="button" class="btn-close" on:click={() => (docToDelete = null)} disabled={isDeletingDoc} aria-label="ปิด">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="modal-body">
        <p class="confirm-text">
          ต้องการลบเอกสาร <strong class="confirm-highlight">"{docToDelete.name}"</strong> ออกจากโครงการนี้ใช่หรือไม่?
        </p>
        <p class="confirm-warning-box">
          Vector Chunks ทั้งหมด ({docToDelete.chunk_count || 0} chunks) ของเอกสารนี้จะถูกลบออกจาก Knowledge Base ถาวร
        </p>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn-cancel" on:click={() => (docToDelete = null)} disabled={isDeletingDoc}>ยกเลิก</button>
        <button type="button" class="btn-submit danger-bg" on:click={executeDeleteDocument} disabled={isDeletingDoc}>
          {isDeletingDoc ? 'กำลังลบ...' : 'ลบเอกสารถาวร'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .pm-wrapper {
    padding: 20px 28px 24px;
    height: 100%;
    min-height: 0;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    color: var(--text-main);
    gap: 16px;
  }

  /* Header */
  .pm-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    flex-shrink: 0;
  }
  .pm-header h2 {
    margin: 0 0 4px 0;
    font-size: 21px;
    font-weight: 700;
    color: var(--text-main);
    letter-spacing: -0.01em;
  }
  .pm-header p {
    margin: 0;
    color: var(--text-muted);
    font-size: 13px;
  }
  .pm-header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  /* 4-Card KPI Overview Ribbon */
  .pm-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    flex-shrink: 0;
  }
  .kpi-tile {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 15px;
    border-radius: 13px;
    background: var(--surface-card, rgba(16, 20, 34, 0.86));
    border: 1px solid var(--glass-border);
    transition: border-color 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .kpi-tile:hover {
    border-color: rgba(168, 85, 247, 0.32);
    transform: translateY(-1px);
  }
  .kpi-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .kpi-icon.indigo { background: rgba(99, 102, 241, 0.16); color: var(--primary-soft-text); border: 1px solid rgba(99, 102, 241, 0.3); }
  .kpi-icon.emerald { background: rgba(16, 185, 129, 0.15); color: var(--success-soft-text); border: 1px solid rgba(16, 185, 129, 0.3); }
  .kpi-icon.violet { background: rgba(168, 85, 247, 0.16); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.3); }
  .kpi-icon.cyan { background: rgba(56, 189, 248, 0.15); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.3); }
  .kpi-body {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .kpi-val {
    font-size: 19px;
    font-weight: 700;
    color: var(--text-main);
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
  }
  .kpi-sub-num {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
  }
  .kpi-lbl {
    font-size: 11.5px;
    color: var(--text-muted);
    margin-top: 2px;
  }

  /* Main Split Grid */
  .pm-grid {
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 18px;
    flex: 1;
    min-height: 0;
  }

  .glass-card {
    background: var(--surface-card, rgba(16, 20, 34, 0.86));
    border: 1px solid var(--glass-border);
    border-radius: 15px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }

  .panel-header {
    padding: 14px 18px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(8, 10, 18, 0.45);
    flex-shrink: 0;
  }
  .toolbar-stack {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .panel-header-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .panel-title {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: #f8fafc;
  }

  .filter-pills {
    display: inline-flex;
    gap: 4px;
    background: rgba(0, 0, 0, 0.28);
    padding: 3px;
    border-radius: 8px;
    border: 1px solid var(--glass-border);
  }
  .pill-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    font-family: inherit;
    font-size: 11.5px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
  }
  .pill-btn:hover {
    color: #f8fafc;
  }
  .pill-btn.active {
    background: rgba(99, 102, 241, 0.22);
    border-color: rgba(99, 102, 241, 0.45);
    color: #ffffff;
    font-weight: 600;
  }
  .pill-btn.golden-pill {
    border: 1px solid var(--glass-border);
    background: rgba(255, 255, 255, 0.03);
    padding: 5px 10px;
  }
  .pill-btn.golden-pill.active {
    background: rgba(245, 158, 11, 0.18);
    border-color: rgba(245, 158, 11, 0.45);
    color: #fcd34d;
  }

  .panel-search-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .search-input-wrap {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(8, 10, 18, 0.55);
    border: 1px solid var(--glass-border);
    border-radius: 9px;
    padding: 6px 11px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .search-input-wrap:focus-within {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }
  .search-input-wrap svg {
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .search-input-wrap input {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    outline: none;
    color: #f8fafc;
    font-family: inherit;
    font-size: 13px;
  }
  .clear-search-btn {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    min-height: 24px;
    border-radius: 6px;
    padding: 2px;
  }
  .clear-search-btn:hover { color: #ffffff; background: rgba(255, 255, 255, 0.08); }

  .sort-select-wrap {
    flex-shrink: 0;
  }

  /* Buttons */
  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: linear-gradient(135deg, var(--primary), #a855f7);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.16);
    padding: 8px 16px;
    border-radius: 10px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
    transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease, filter 0.2s ease;
  }
  .btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 20px rgba(168, 85, 247, 0.45);
    filter: brightness(1.06);
  }
  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-main);
    padding: 7px 13px;
    border-radius: 9px;
    font-family: inherit;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
  }
  .btn-ghost:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.09);
    border-color: rgba(255, 255, 255, 0.2);
    color: #ffffff;
  }
  .btn-ghost:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .btn-xs {
    padding: 5px 10px;
    font-size: 11.5px;
    border-radius: 7px;
  }

  /* Table Styles */
  .table-responsive {
    flex: 1;
    overflow: auto;
  }
  .pm-table {
    width: 100%;
    min-width: 640px;
    border-collapse: collapse;
    text-align: left;
  }
  .pm-table th {
    position: sticky;
    top: 0;
    background: rgba(15, 19, 32, 0.96);
    padding: 11px 14px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    border-bottom: 1px solid var(--glass-border);
    z-index: 10;
  }
  .pm-table td {
    padding: 12px 14px;
    border-bottom: 1px solid var(--glass-border);
    font-size: 13.5px;
    cursor: pointer;
    vertical-align: top;
    transition: background-color 0.18s ease;
  }
  .pm-table tbody tr:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: -2px;
  }
  .pm-table tr:hover td {
    background: rgba(255, 255, 255, 0.03);
  }
  .pm-table tr.selected td {
    background: rgba(99, 102, 241, 0.13);
  }
  .col-expand { width: 34px; text-align: center; }
  .col-code { width: 92px; white-space: nowrap; }
  .col-docs { width: 88px; white-space: nowrap; }
  .col-status { width: 88px; white-space: nowrap; }
  .col-actions { width: 74px; white-space: nowrap; }

  .code-pill {
    display: inline-block;
    font-family: var(--font-en, monospace);
    font-size: 11.5px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 6px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: #c7d2fe;
  }

  .proj-name { max-width: 260px; }
  .proj-title-line {
    font-weight: 600;
    color: #f8fafc;
  }
  .proj-desc {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
  }
  .proj-sites-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 6px;
  }
  .truncate {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .doc-count-chip {
    font-size: 12px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }
  .doc-count-chip.has-docs {
    color: #e2e8f0;
    font-weight: 600;
  }

  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
    background: rgba(148, 163, 184, 0.12);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #cbd5e1;
  }
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #94a3b8;
  }
  .status-badge.active {
    background: rgba(16, 185, 129, 0.14);
    border-color: rgba(16, 185, 129, 0.35);
    color: #6ee7b7;
  }
  .status-badge.active .status-dot {
    background: #10b981;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.7);
  }

  .actions-wrapper {
    display: flex;
    gap: 4px;
  }
  .btn-icon {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    min-width: 30px;
    min-height: 30px;
    border-radius: 7px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
  }
  .btn-icon.edit:hover {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(99, 102, 241, 0.4);
    color: #c7d2fe;
  }
  .btn-icon.delete:hover {
    background: rgba(244, 63, 94, 0.15);
    border-color: rgba(244, 63, 94, 0.4);
    color: #fda4af;
  }

  .btn-expand {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    min-width: 28px;
    min-height: 28px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), color 0.2s ease, background-color 0.2s ease;
  }
  .btn-expand:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.08);
  }
  .btn-expand.expanded {
    transform: rotate(90deg);
    color: #a5b4fc;
  }

  .expanded-row td {
    padding: 0 !important;
    background: rgba(8, 10, 18, 0.42) !important;
  }
  .expanded-content {
    padding: 10px 18px 12px 54px;
  }
  .sub-doc-list {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .sub-doc-item {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    color: var(--text-main);
    text-align: left;
    padding: 7px 11px;
    border-radius: 8px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12.5px;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: background-color 0.18s ease, border-color 0.18s ease;
  }
  .sub-doc-item:hover {
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(255, 255, 255, 0.12);
  }
  .sub-doc-item.active {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.45);
    color: #ffffff;
  }
  .sub-doc-cat {
    margin-left: auto;
    font-size: 11px;
    color: var(--text-muted);
    flex-shrink: 0;
  }
  .sub-loading, .sub-empty {
    font-size: 12.5px;
    color: var(--text-muted);
    padding: 6px 0;
  }

  /* Site Tags */
  .site-tag-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-height: 24px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.09);
    padding: 3px 8px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 11px;
    max-width: 240px;
    cursor: pointer;
    transition: border-color 0.18s ease, background-color 0.18s ease;
  }
  .site-tag-pill:hover {
    border-color: rgba(56, 189, 248, 0.55);
    background: rgba(56, 189, 248, 0.12);
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
    flex-shrink: 0;
  }
  .env-test, .env-dev { background: rgba(56, 189, 248, 0.2); color: #38bdf8; }
  .env-uat { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
  .env-prd { background: rgba(168, 85, 247, 0.22); color: #d8b4fe; }
  .env-staging, .env-custom { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }
  .url-text { color: #cbd5e1; max-width: 150px; }
  .site-tag-pill.is-default .url-text { color: #e0f2fe; font-weight: 500; }
  .star-svg { color: #fbbf24; flex-shrink: 0; }

  /* Pagination */
  .pagination-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
    padding: 10px 16px;
    border-top: 1px solid var(--glass-border);
    background: rgba(8, 10, 18, 0.45);
    font-size: 12.5px;
    flex-shrink: 0;
  }
  .pagination-info { color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .pagination-controls { display: flex; align-items: center; gap: 4px; }
  .page-btn {
    min-width: 30px;
    height: 30px;
    padding: 0 8px;
    border-radius: 7px;
    border: 1px solid var(--glass-border);
    background: rgba(255, 255, 255, 0.03);
    color: var(--text-main);
    font-size: 12.5px;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease;
  }
  .page-btn:hover:not(:disabled):not(.active) {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(99, 102, 241, 0.42);
  }
  .page-btn.active {
    background: linear-gradient(135deg, var(--primary), #8b5cf6);
    border-color: transparent;
    color: #ffffff;
    font-weight: 600;
  }
  .page-btn:disabled { opacity: 0.32; cursor: not-allowed; }
  .page-ellipsis { color: var(--text-muted); padding: 0 4px; }
  .page-size { display: flex; align-items: center; gap: 6px; color: var(--text-muted); }
  .page-size select {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-main);
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12.5px;
    cursor: pointer;
  }
  .page-size select option { background: #141726; }

  .empty-table {
    text-align: center;
    padding: 42px 20px !important;
    color: var(--text-muted);
  }
  .error-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 36px;
    color: #fda4af;
    text-align: center;
    font-size: 13.5px;
  }

  /* Right Panel: Project Inspector & Document Viewer */
  .project-inspector-head {
    padding: 14px 18px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(8, 10, 18, 0.45);
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex-shrink: 0;
  }
  .pi-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
  }
  .pi-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .pi-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }
  .pi-desc {
    margin: 0;
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.5;
  }
  .doc-filter-bar {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .search-input-wrap.compact {
    padding: 5px 10px;
  }

  .doc-list {
    flex: 1;
    overflow-y: auto;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 9px;
  }
  .doc-card {
    display: flex;
    align-items: center;
    gap: 12px;
    background: rgba(10, 13, 24, 0.55);
    border: 1px solid var(--glass-border);
    border-radius: 11px;
    padding: 12px 14px;
    cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .doc-card:hover {
    background: rgba(99, 102, 241, 0.11);
    border-color: rgba(99, 102, 241, 0.38);
    transform: translateY(-1px);
  }
  .doc-icon-box {
    width: 36px;
    height: 36px;
    border-radius: 9px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: #a5b4fc;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .doc-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .doc-name-row {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
  }
  .doc-name {
    font-weight: 600;
    font-size: 13.5px;
    color: #f8fafc;
  }
  .mini-golden-tag {
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 999px;
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.42);
    color: #fcd34d;
    flex-shrink: 0;
  }
  .golden-badge-lg {
    font-size: 11px;
    font-weight: 700;
    padding: 2px 9px;
    border-radius: 999px;
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: #fcd34d;
    flex-shrink: 0;
  }
  .doc-sub {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 11.5px;
    color: var(--text-muted);
  }
  .doc-cat-chip {
    background: rgba(255, 255, 255, 0.06);
    padding: 1px 6px;
    border-radius: 4px;
    color: #cbd5e1;
  }
  .doc-card-actions {
    flex-shrink: 0;
  }

  /* Empty & Loading States */
  .empty-state, .loading-state-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 36px 24px;
    text-align: center;
    gap: 10px;
    color: var(--text-muted);
  }
  .empty-svg-badge {
    width: 64px;
    height: 64px;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 4px;
  }
  .empty-svg-badge.accent {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.16), rgba(168, 85, 247, 0.14));
    border-color: rgba(168, 85, 247, 0.32);
    color: #c4b5fd;
  }
  .empty-title {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    color: #f8fafc;
  }
  .empty-sub {
    margin: 0;
    font-size: 12.5px;
    color: var(--text-muted);
    max-width: 320px;
    line-height: 1.55;
  }

  /* Document Viewer */
  .doc-viewer {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }
  .viewer-header {
    padding: 14px 18px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(8, 10, 18, 0.45);
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-shrink: 0;
  }
  .viewer-header-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }
  .btn-back {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: transparent;
    border: none;
    color: #a5b4fc;
    cursor: pointer;
    font-family: inherit;
    font-size: 12.5px;
    padding: 0;
    font-weight: 600;
  }
  .btn-back:hover { color: #ffffff; }
  .viewer-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .viewer-title {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
  }
  .viewer-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    padding: 10px 18px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(255, 255, 255, 0.02);
    font-size: 12px;
    flex-shrink: 0;
  }
  .meta-item .lbl { color: var(--text-muted); margin-right: 4px; }
  .meta-item .val { color: #e2e8f0; font-weight: 500; }

  .viewer-content {
    flex: 1;
    overflow-y: auto;
    padding: 20px 22px;
    background: rgba(10, 14, 26, 0.65);
    line-height: 1.7;
    font-size: 13.5px;
    color: #e2e8f0;
  }
  .viewer-content :global(.pm-md-h1) { font-size: 18px; font-weight: 700; color: #c7d2fe; margin: 16px 0 8px; }
  .viewer-content :global(.pm-md-h2) { font-size: 16px; font-weight: 700; color: #f8fafc; margin: 14px 0 6px; }
  .viewer-content :global(.pm-md-h3) { font-size: 14.5px; font-weight: 600; color: #e2e8f0; margin: 12px 0 5px; }
  .viewer-content :global(.pm-md-p) { margin-bottom: 6px; }
  .viewer-content :global(.pm-md-spacer) { height: 8px; }
  .viewer-content :global(.pm-md-hr) { border: none; border-top: 1px solid var(--glass-border); margin: 14px 0; }
  .viewer-content :global(.pm-md-li) { padding-left: 14px; margin-bottom: 4px; }
  .viewer-content :global(.pm-md-ol) { display: flex; gap: 8px; padding-left: 10px; margin-bottom: 4px; }
  .viewer-content :global(.pm-ol-num) { color: #a5b4fc; font-weight: 600; }
  .viewer-content :global(.pm-inline-code) {
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    padding: 1px 6px;
    border-radius: 5px;
    font-size: 12px;
  }
  .viewer-content :global(.pm-code-block) {
    background: #121524;
    border: 1px solid var(--glass-border);
    border-radius: 10px;
    padding: 12px 14px;
    margin: 12px 0;
    overflow-x: auto;
  }
  .viewer-content :global(.pm-code-lang) {
    font-size: 11px;
    color: #a5b4fc;
    font-weight: 600;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .viewer-content :global(.pm-code-block pre) {
    margin: 0;
    color: #cbd5e1;
    font-family: monospace;
    font-size: 12.5px;
  }
  .viewer-content :global(.pm-md-table-wrap) {
    overflow-x: auto;
    margin: 12px 0;
    border-radius: 10px;
    border: 1px solid var(--glass-border);
  }
  .viewer-content :global(.pm-md-table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    text-align: left;
  }
  .viewer-content :global(.pm-md-table th) {
    background: rgba(30, 41, 59, 0.85);
    padding: 9px 12px;
    border-bottom: 1px solid var(--glass-border);
    border-right: 1px solid var(--glass-border);
    color: #f8fafc;
    font-weight: 600;
  }
  .viewer-content :global(.pm-md-table td) {
    padding: 9px 12px;
    border-bottom: 1px solid var(--glass-border);
    border-right: 1px solid var(--glass-border);
    vertical-align: top;
  }
  .viewer-content :global(.pm-toc-row) {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 2px 0;
  }
  .viewer-content :global(.pm-toc-dots) {
    flex: 1;
    border-bottom: 1px dotted rgba(255, 255, 255, 0.24);
    min-width: 20px;
  }
  .viewer-content :global(.pm-toc-page) {
    color: #a5b4fc;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  /* Animations */
  .stage-in {
    animation: pmStageIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes pmStageIn {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .pm-spinner {
    width: 24px;
    height: 24px;
    border: 2.5px solid rgba(99, 102, 241, 0.22);
    border-top-color: #a855f7;
    border-radius: 50%;
    animation: pmSpin 0.8s linear infinite;
  }
  .spin-icon {
    animation: pmSpin 0.85s linear infinite;
  }
  @keyframes pmSpin { to { transform: rotate(360deg); } }

  /* Modals */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(5, 7, 15, 0.76);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10000;
    padding: 20px;
    animation: pmFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes pmFadeIn { from { opacity: 0; } to { opacity: 1; } }

  .modal-content {
    position: relative;
    background: linear-gradient(165deg, rgba(24, 27, 44, 0.97) 0%, rgba(15, 17, 29, 0.99) 100%);
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: 18px;
    width: 94%;
    max-width: 640px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.65);
    overflow: visible;
    animation: pmModalRise 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes pmModalRise {
    from { opacity: 0; transform: translateY(12px) scale(0.97); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }
  .modal-sm { max-width: 440px; }
  .modal-top-accent {
    position: absolute;
    top: 0;
    left: 24px;
    right: 24px;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--primary), #a855f7, #38bdf8, transparent);
    border-radius: 0 0 4px 4px;
  }
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 18px 22px 14px;
    border-bottom: 1px solid var(--glass-border);
  }
  .modal-head-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .modal-head-icon {
    width: 38px;
    height: 38px;
    border-radius: 11px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.22), rgba(168, 85, 247, 0.22));
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #e9d5ff;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal-header h3 {
    margin: 0;
    font-size: 16.5px;
    font-weight: 700;
    color: #f8fafc;
  }
  .modal-sub {
    margin: 2px 0 0;
    font-size: 12px;
    color: var(--text-muted);
  }
  .modal-danger-title {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .danger-text { color: #fb7185 !important; }

  .btn-close {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
    width: 30px;
    height: 30px;
    border-radius: 9px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.18s ease, color 0.18s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-close:hover:not(:disabled) {
    background: rgba(244, 63, 94, 0.15);
    color: #fda4af;
    transform: rotate(90deg);
  }

  .modal-body {
    padding: 18px 22px;
    max-height: 70vh;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .modal-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .form-group label {
    font-size: 12.5px;
    font-weight: 500;
    color: #cbd5e1;
  }
  .req { color: var(--danger); }
  .form-input {
    width: 100%;
    padding: 9px 12px;
    background: rgba(8, 10, 18, 0.55);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 9px;
    color: #ffffff;
    font-size: 13.5px;
    box-sizing: border-box;
    font-family: inherit;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }
  .form-input:focus {
    outline: none;
    border-color: var(--primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
  }

  /* Sites Manager */
  .sites-manager-group {
    background: rgba(10, 14, 26, 0.55);
    border: 1px solid rgba(56, 189, 248, 0.2);
    border-radius: 12px;
    padding: 12px 14px;
  }
  .sites-manager-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .sites-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12.5px;
    font-weight: 600;
    color: #7dd3fc;
  }
  .btn-add-site {
    background: rgba(56, 189, 248, 0.14);
    color: #7dd3fc;
    border: 1px solid rgba(56, 189, 248, 0.32);
    border-radius: 6px;
    padding: 3px 10px;
    font-family: inherit;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease;
  }
  .btn-add-site:hover {
    background: rgba(56, 189, 248, 0.28);
    color: #ffffff;
  }
  .sites-hint {
    font-size: 11.5px;
    color: var(--text-muted);
    line-height: 1.45;
  }
  .sites-hint code {
    color: #bae6fd;
    font-size: 11px;
  }
  .site-urls-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 4px;
  }
  .site-url-row {
    display: flex;
    align-items: center;
    gap: 7px;
    background: rgba(0, 0, 0, 0.32);
    padding: 6px 8px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: border-color 0.18s ease;
  }
  .site-url-row.is-default-row {
    border-color: rgba(56, 189, 248, 0.42);
    background: rgba(56, 189, 248, 0.05);
  }
  .site-url-row.is-invalid-row {
    border-color: rgba(244, 63, 94, 0.65);
    background: rgba(244, 63, 94, 0.08);
  }
  .site-env-select {
    appearance: none;
    -webkit-appearance: none;
    padding: 7px 24px 7px 9px;
    background-color: #0f172a;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 7px center;
    border: 1px solid var(--glass-border-light, rgba(255, 255, 255, 0.15));
    border-radius: 7px;
    color: var(--text-main);
    font-family: var(--font-en, inherit);
    font-size: 11.5px;
    font-weight: 700;
    width: 92px;
    cursor: pointer;
  }
  .site-env-select:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 1px;
  }
  .site-url-input {
    flex: 1;
    padding: 7px 10px !important;
    font-size: 12.5px !important;
  }
  .btn-default-toggle {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 6px 10px;
    font-family: inherit;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
  }
  .btn-default-toggle.active {
    background: rgba(245, 158, 11, 0.18);
    color: #fcd34d;
    border-color: rgba(245, 158, 11, 0.48);
  }
  .btn-remove-site {
    background: transparent;
    color: var(--text-muted);
    border: none;
    cursor: pointer;
    padding: 5px;
    border-radius: 6px;
    display: flex;
  }
  .btn-remove-site:hover:not(:disabled) {
    color: #fda4af;
    background: rgba(244, 63, 94, 0.14);
  }
  .btn-remove-site:disabled { opacity: 0.28; cursor: not-allowed; }

  .confirm-text { margin: 0; font-size: 14px; color: #e2e8f0; }
  .confirm-highlight { color: #c7d2fe; }
  .confirm-warning-box {
    margin: 0;
    font-size: 12.5px;
    color: #fda4af;
    background: rgba(244, 63, 94, 0.1);
    padding: 11px 13px;
    border-radius: 9px;
    border: 1px solid rgba(244, 63, 94, 0.25);
    line-height: 1.5;
  }

  .modal-footer {
    padding: 14px 22px 18px;
    border-top: 1px solid var(--glass-border);
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }
  .btn-cancel {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #cbd5e1;
    padding: 8px 16px;
    border-radius: 9px;
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
    transition: background-color 0.18s ease, color 0.18s ease;
  }
  .btn-cancel:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }
  .btn-submit {
    background: linear-gradient(135deg, var(--primary), #a855f7);
    color: #ffffff;
    border: none;
    padding: 8px 18px;
    border-radius: 9px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.18s ease, filter 0.18s ease;
  }
  .btn-submit:hover:not(:disabled) {
    transform: translateY(-1px);
    filter: brightness(1.06);
  }
  .btn-submit:disabled { opacity: 0.48; cursor: not-allowed; }
  .danger-bg { background: linear-gradient(135deg, #e11d48, #f43f5e); }

  /* Consistent Keyboard Focus Rings (WCAG 2.1 AA SC 2.4.7) */
  .btn-primary:focus-visible,
  .btn-ghost:focus-visible,
  .btn-icon:focus-visible,
  .btn-expand:focus-visible,
  .pill-btn:focus-visible,
  .page-btn:focus-visible,
  .doc-card:focus-visible,
  .site-tag-pill:focus-visible,
  .sub-doc-item:focus-visible,
  .btn-back:focus-visible,
  .clear-search-btn:focus-visible,
  .btn-close:focus-visible,
  .btn-add-site:focus-visible,
  .btn-default-toggle:focus-visible,
  .btn-remove-site:focus-visible,
  .btn-cancel:focus-visible,
  .btn-submit:focus-visible {
    outline: 2px solid var(--primary);
    outline-offset: 2px;
  }

  @media (max-width: 1100px) {
    .pm-grid { grid-template-columns: 1fr; }
    .pm-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 600px) {
    .pm-wrapper { padding: 14px 16px; }
    .modal-grid-2 { grid-template-columns: 1fr; }
  }
  @media (prefers-reduced-motion: reduce) {
    .stage-in, .modal-backdrop, .modal-content, .pm-spinner, .spin-icon {
      animation: none !important;
    }
    .kpi-tile, .doc-card, .btn-primary, .btn-close, .btn-expand {
      transition: none !important;
    }
  }
</style>
