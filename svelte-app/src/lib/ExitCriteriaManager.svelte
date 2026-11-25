<script>
    import { onMount, onDestroy, tick } from 'svelte';
    import { toast } from './toastStore.js';
    import CustomSelect from './CustomSelect.svelte';
    import { EXIT_CRITERIA_DOC_TYPES } from './constants.js';
    import { selectedProjectStore } from './qaHistoryStore.js';

    const CATEGORIES = [
        {
            id: 'Defect & Comment Resolution',
            prefix: '1',
            shortLabel: 'หมวด 1: Defect & Comment',
            title: 'หมวดที่ 1: การตอบสนองรายการแก้ไข (Defect & Comment Resolution)',
            defaultMetric: '100% Closed (แก้ไขครบ 100%)',
            defaultSeverity: 'Critical',
            defaultMandatory: true
        },
        {
            id: 'Content Accuracy & Completeness',
            prefix: '2',
            shortLabel: 'หมวด 2: Content Accuracy',
            title: 'หมวดที่ 2: ความถูกต้องและครบถ้วนของเนื้อหา (Content Accuracy & Completeness)',
            defaultMetric: '100% Verified (ถูกต้อง 100%)',
            defaultSeverity: 'Major',
            defaultMandatory: true
        },
        {
            id: 'Format & Consistency',
            prefix: '3',
            shortLabel: 'หมวด 3: Format & Typo',
            title: 'หมวดที่ 3: รูปแบบและความเป็นเอกภาพ (Format & Consistency)',
            defaultMetric: '< 1% Typo Rate (คำผิด < 1%)',
            defaultSeverity: 'Minor',
            defaultMandatory: false
        },
        {
            id: 'Governance & Control',
            prefix: '4',
            shortLabel: 'หมวด 4: Governance',
            title: 'หมวดที่ 4: การกำกับดูแลและเวอร์ชัน (Governance & Control)',
            defaultMetric: '100% Header & Metadata',
            defaultSeverity: 'Major',
            defaultMandatory: true
        }
    ];

    const categoryMoveOptions = CATEGORIES.map((c) => ({ value: c.id, label: c.shortLabel }));

    const severityOptions = [
        { value: 'Critical', label: 'Critical (วิกฤต)' },
        { value: 'Major', label: 'Major (สำคัญ)' },
        { value: 'Minor', label: 'Minor (ทั่วไป)' }
    ];

    const statusFilterOptions = [
        { value: 'all', label: 'ทุกสถานะ (All)' },
        { value: 'active', label: 'เปิดใช้งาน (Active)' },
        { value: 'inactive', label: 'ปิดใช้งาน (Inactive)' }
    ];

    let templates = [];
    let projects = [];
    let loading = false;
    let loadingDetail = false;
    let saving = false;
    let togglingIds = new Set();

    // Sidebar Filters
    let search = '';
    let filterDocType = '';
    let filterStatus = 'all';
    let filterProjectScope = 'all'; // 'all' | 'global' | project_id

    let activeTemplate = null;
    let initialSnapshot = '';
    let isClonedUnsavedDraft = false;
    let invalidItemIndex = -1;
    let invalidTitleField = false;

    // Collapsible sections
    let collapsedCategories = {};
    let showRulesSection = false;

    // Undo deleted item state
    let lastDeletedItem = null; // { item, index }
    let undoTimer = null;

    // Effective Gate Preview (debounced & AbortController-protected)
    let effectivePreview = null;
    let loadingPreview = false;
    let lastFetchedPreviewKey = '';
    let previewAbortCtrl = null;

    // Modals & Refs
    let showHelpModal = false;
    let showConfirmModal = false;
    let showAiSuggestModal = false;
    let showSandboxModal = false;
    let lastTriggerEl = null;
    let helpDialogEl = null;
    let confirmDialogEl = null;
    let aiDialogEl = null;
    let sandboxDialogEl = null;

    // AI Suggest state
    let aiDocType = 'SRS';
    let aiHint = '';
    let aiMode = 'replace'; // 'replace' | 'append'
    let isGeneratingAi = false;

    // Sandbox Dry-Run state
    let sandboxSampleText = '';
    let sandboxUseDraft = true;
    let isRunningSandbox = false;
    let sandboxResult = null;

    let confirmModalData = {
        title: '',
        message: '',
        confirmText: 'ยืนยัน',
        cancelText: 'ยกเลิก',
        type: 'danger',
        loading: false,
        onConfirm: null
    };

    let form = {
        template_id: null,
        project_id: '',
        title: '',
        description: '',
        doc_type: 'ALL',
        is_active: true,
        max_loops: 3,
        items: []
    };

    const docTypes = EXIT_CRITERIA_DOC_TYPES;

    function getAuthHeaders(extra = {}) {
        const token = localStorage.getItem('jwt_token');
        return {
            ...extra,
            ...(token ? { Authorization: `Bearer ${token}` } : {})
        };
    }

    function getActiveTopbarProjectId() {
        const p = $selectedProjectStore;
        if (!p) return '';
        return String(p.project_id || p.id || '').trim();
    }

    function normalizeCategory(rawCat, itemCode = '') {
        const c = String(rawCat || '').trim();
        if (CATEGORIES.some((cat) => cat.id === c)) return c;
        const cl = c.toLowerCase();
        if (['defect', 'bug', 'comment', 'แก้ไข'].some((k) => cl.includes(k))) return 'Defect & Comment Resolution';
        if (['content', 'accuracy', 'completeness', 'เนื้อหา', 'ครบถ้วน'].some((k) => cl.includes(k))) return 'Content Accuracy & Completeness';
        if (['format', 'consistency', 'typo', 'quality', 'รูปแบบ', 'คำผิด'].some((k) => cl.includes(k))) return 'Format & Consistency';
        if (['governance', 'control', 'version', 'metadata', 'กำกับ'].some((k) => cl.includes(k))) return 'Governance & Control';
        const codeStr = String(itemCode || '').trim();
        if (codeStr.startsWith('1')) return 'Defect & Comment Resolution';
        if (codeStr.startsWith('2')) return 'Content Accuracy & Completeness';
        if (codeStr.startsWith('3')) return 'Format & Consistency';
        if (codeStr.startsWith('4')) return 'Governance & Control';
        return 'Content Accuracy & Completeness';
    }

    function normalizeItemsList(rawItems = []) {
        return rawItems.map((it, idx) => {
            const normCat = normalizeCategory(it.category, it.item_code);
            const catMeta = CATEGORIES.find((c) => c.id === normCat) || CATEGORIES[1];
            const validSev = ['Critical', 'Major', 'Minor'].includes(it.severity)
                ? it.severity
                : catMeta.defaultSeverity;
            return {
                ...it,
                item_code: String(it.item_code || `${catMeta.prefix}.${idx + 1}`).trim(),
                category: normCat,
                question_text: String(it.question_text || ''),
                target_metric: String(it.target_metric || catMeta.defaultMetric),
                severity: validSev,
                is_mandatory: it.is_mandatory !== undefined ? Boolean(it.is_mandatory) : catMeta.defaultMandatory,
                order_index: idx + 1
            };
        });
    }

    function serializeForm(f) {
        return JSON.stringify({
            project_id: f.project_id || '',
            title: f.title || '',
            description: f.description || '',
            doc_type: f.doc_type || 'ALL',
            is_active: Boolean(f.is_active),
            max_loops: Number(f.max_loops || 3),
            items: (f.items || []).map((it) => ({
                item_code: it.item_code,
                category: it.category,
                question_text: it.question_text,
                target_metric: it.target_metric,
                severity: it.severity,
                is_mandatory: Boolean(it.is_mandatory)
            }))
        });
    }

    $: isFormDirty = isClonedUnsavedDraft || (initialSnapshot !== '' && serializeForm(form) !== initialSnapshot);

    $: hasSidebarFilters =
        search.trim() !== '' || filterDocType !== '' || filterStatus !== 'all' || filterProjectScope !== 'all';

    function resetSidebarFilters() {
        search = '';
        filterDocType = '';
        filterStatus = 'all';
        filterProjectScope = 'all';
    }

    $: projectScopeOptions = [
        { value: '', label: 'มาตรฐานกลางองค์กร (Global — ทุกโครงการ)' },
        ...projects.map((p) => ({
            value: String(p.project_id || p.id),
            label: `เฉพาะโครงการ: ${p.project_name || p.name}${p.project_code ? ` (${p.project_code})` : ''}`
        }))
    ];

    $: sidebarProjectFilterOptions = [
        { value: 'all', label: 'ทุกขอบเขตโครงการ (All)' },
        { value: 'global', label: 'เฉพาะเกณฑ์กลาง (Global)' },
        ...projects.map((p) => ({
            value: String(p.project_id || p.id),
            label: p.project_name || p.name || p.project_code
        }))
    ];

    $: activeProjectName = form.project_id
        ? projects.find((p) => String(p.project_id || p.id) === String(form.project_id))?.project_name ||
          projects.find((p) => String(p.project_id || p.id) === String(form.project_id))?.name ||
          'เฉพาะโครงการ'
        : 'Global ทั้งองค์กร';

    $: filteredTemplates = templates.filter((t) => {
        const q = search.trim().toLowerCase();
        const matchSearch =
            !q ||
            String(t.title || '').toLowerCase().includes(q) ||
            String(t.description || '').toLowerCase().includes(q) ||
            String(t.doc_type || '').toLowerCase().includes(q) ||
            String(t.project_code || t.project_name || '').toLowerCase().includes(q);
        const matchDoc = !filterDocType || t.doc_type === filterDocType;
        const matchStatus =
            filterStatus === 'all' || (filterStatus === 'active' ? Boolean(t.is_active) : !t.is_active);
        const matchProj =
            filterProjectScope === 'all' ||
            (filterProjectScope === 'global'
                ? !t.project_id
                : !t.project_id || String(t.project_id) === filterProjectScope);
        return matchSearch && matchDoc && matchStatus && matchProj;
    });

    // Only fire /api/exit-criteria/effective-preview when doc_type or project_id primitives actually change!
    $: currentPreviewKey = `${form.doc_type || 'ALL'}::${form.project_id || ''}`;
    $: if (currentPreviewKey && currentPreviewKey !== lastFetchedPreviewKey) {
        lastFetchedPreviewKey = currentPreviewKey;
        fetchEffectivePreview(form.doc_type, form.project_id);
    }

    // Live Draft-Aware Effective Gate Calculation (updates instantaneously without hitting Save!)
    $: liveEffectiveSummary = (() => {
        if (!effectivePreview) return null;
        const otherTemplates = (effectivePreview.matched_templates || []).filter(
            (m) => String(m.template_id) !== String(form.template_id)
        );
        const currentDraftActive = Boolean(form.is_active);
        const currentDraftCount = currentDraftActive ? form.items.length : 0;
        const list = [
            ...otherTemplates.map((m) => ({ title: m.title, count: m.item_count, isDraft: false })),
            ...(currentDraftActive
                ? [{ title: `${form.title || 'ร่างปัจจุบัน'}${isFormDirty ? '*' : ''}`, count: currentDraftCount, isDraft: isFormDirty }]
                : [])
        ];
        const total = list.reduce((sum, item) => sum + item.count, 0);
        const universalOn =
            form.doc_type === 'ALL' && form.template_id
                ? currentDraftActive || otherTemplates.some((m) => m.doc_type === 'ALL')
                : effectivePreview.universal_active;
        return {
            totalItems: total,
            usingFallback: total === 0,
            universalActive: universalOn,
            breakdown: list
        };
    })();

    function trapFocus(e) {
        if (e.key !== 'Tab') return;
        const dialog = e.currentTarget;
        if (!dialog) return;
        const focusables = dialog.querySelectorAll(
            'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    }

    function handleWindowKeydown(e) {
        // Ctrl/Cmd + S accelerator to save Exit Criteria
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            if (!showConfirmModal && !showSandboxModal && !showAiSuggestModal && !showHelpModal) {
                e.preventDefault();
                if (!saving) saveTemplate();
                return;
            }
        }
        if (e.key !== 'Escape') return;
        if (showConfirmModal && !confirmModalData.loading) {
            closeConfirmModal();
        } else if (showSandboxModal && !isRunningSandbox) {
            closeSandboxModal();
        } else if (showAiSuggestModal && !isGeneratingAi) {
            closeAiModal();
        } else if (showHelpModal) {
            closeHelpModal();
        }
    }

    onMount(async () => {
        await Promise.all([fetchProjects(), fetchTemplates(true)]);
        const topbarPid = getActiveTopbarProjectId();
        if (topbarPid) {
            filterProjectScope = topbarPid;
        }
    });

    onDestroy(() => {
        if (undoTimer) clearTimeout(undoTimer);
        if (previewAbortCtrl) previewAbortCtrl.abort();
    });

    async function fetchProjects() {
        try {
            const res = await fetch('/api/projects', { headers: getAuthHeaders() });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                projects = data.projects || [];
            }
        } catch (_) {}
    }

    async function fetchEffectivePreview(docType, projectId) {
        if (previewAbortCtrl) previewAbortCtrl.abort();
        previewAbortCtrl = new AbortController();
        loadingPreview = true;
        try {
            const params = new URLSearchParams({ doc_type: docType || 'ALL' });
            if (projectId) params.set('project_id', projectId);
            const res = await fetch(`/api/exit-criteria/effective-preview?${params.toString()}`, {
                headers: getAuthHeaders(),
                signal: previewAbortCtrl.signal
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                effectivePreview = data;
            }
        } catch (err) {
            if (err?.name !== 'AbortError') {
                // Non-fatal preview error
            }
        } finally {
            loadingPreview = false;
        }
    }

    async function fetchTemplates(selectFirst = false, preferredId = null) {
        loading = true;
        try {
            const res = await fetch('/api/exit-criteria/templates', { headers: getAuthHeaders() });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                templates = data.templates || [];
                const targetId =
                    preferredId ||
                    (form.template_id && templates.some((t) => t.template_id === form.template_id)
                        ? form.template_id
                        : selectFirst && templates.length > 0
                          ? templates[0].template_id
                          : null);
                if (targetId) {
                    await loadTemplateDetail(targetId);
                } else if (templates.length === 0) {
                    applyNewTemplateDraft();
                }
            } else {
                toast(data.error || 'ไม่สามารถโหลดรายการ Exit Criteria ได้', 'error');
            }
        } catch (e) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเพื่อโหลด Template', 'error');
        } finally {
            loading = false;
        }
    }

    async function loadTemplateDetail(templateId) {
        loadingDetail = true;
        clearUndoBanner();
        invalidItemIndex = -1;
        invalidTitleField = false;
        try {
            const res = await fetch(`/api/exit-criteria/templates/${templateId}`, {
                headers: getAuthHeaders()
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                activeTemplate = data.template;
                form = {
                    template_id: data.template.template_id,
                    project_id: data.template.project_id || '',
                    title: data.template.title || '',
                    description: data.template.description || '',
                    doc_type: data.template.doc_type || 'ALL',
                    is_active: data.template.is_active !== undefined ? Boolean(data.template.is_active) : true,
                    max_loops: Math.max(1, Math.min(10, Number(data.template.max_loops ?? 3))),
                    items: normalizeItemsList(data.template.items || [])
                };
                isClonedUnsavedDraft = false;
                initialSnapshot = serializeForm(form);
                lastFetchedPreviewKey = '';
            } else {
                toast(data.error || 'ไม่สามารถโหลดรายละเอียด Template ได้', 'error');
            }
        } catch (e) {
            toast('เกิดข้อผิดพลาดในการโหลดรายละเอียด Template', 'error');
        } finally {
            loadingDetail = false;
        }
    }

    function guardUnsavedThenRun(actionFn) {
        if (!isFormDirty) {
            actionFn();
            return;
        }
        askConfirmation({
            title: 'มีการแก้ไขที่ยังไม่ได้บันทึก',
            message: `คุณได้แก้ไขเกณฑ์ใน "${form.title || 'ร่างปัจจุบัน'}" ค้างไว้ ต้องการละทิ้งการเปลี่ยนแปลงหรือไม่?`,
            confirmText: 'ละทิ้งการแก้ไข',
            cancelText: 'กลับไปแก้ไขต่อ',
            type: 'warning',
            onConfirm: async () => {
                isClonedUnsavedDraft = false;
                initialSnapshot = '';
                await actionFn();
            }
        });
    }

    function selectTemplate(templateId) {
        if (form.template_id === templateId && !isFormDirty) return;
        guardUnsavedThenRun(() => loadTemplateDetail(templateId));
    }

    function revertChanges() {
        if (form.template_id) {
            loadTemplateDetail(form.template_id);
            toast('คืนค่าข้อมูลตามที่บันทึกไว้ล่าสุดแล้ว', 'info');
        } else {
            applyNewTemplateDraft();
            toast('รีเซ็ตร่าง Template ใหม่แล้ว', 'info');
        }
    }

    function applyNewTemplateDraft() {
        activeTemplate = null;
        clearUndoBanner();
        invalidItemIndex = -1;
        invalidTitleField = false;
        const inheritedProjectId = getActiveTopbarProjectId();
        form = {
            template_id: null,
            project_id: inheritedProjectId,
            title: 'New Document Exit Criteria Template',
            description: 'เกณฑ์การตรวจสอบคุณภาพเอกสาร',
            doc_type: 'SRS',
            is_active: true,
            max_loops: 3,
            items: [
                { item_code: '1.1', category: 'Defect & Comment Resolution', question_text: 'ข้อสั่งการ/Comment ระดับ Critical / High ในรอบก่อน ได้รับการแก้ไขเรียบร้อยแล้ว 100%', target_metric: '100% Closed (แก้ไขครบ 100%)', severity: 'Critical', is_mandatory: true, order_index: 1 },
                { item_code: '2.1', category: 'Content Accuracy & Completeness', question_text: 'ข้อมูล ตัวเลข ข้อเท็จจริง และขอบเขตเนื้อหาครบถ้วนถูกต้องตามโจทย์', target_metric: '100% Verified Accuracy', severity: 'Critical', is_mandatory: true, order_index: 2 },
                { item_code: '3.1', category: 'Format & Consistency', question_text: 'รูปแบบฟอนต์ การจัดตาราง และไม่มีคำผิดเกินเกณฑ์มาตรฐาน', target_metric: '< 1% Typo Rate', severity: 'Minor', is_mandatory: false, order_index: 3 },
                { item_code: '4.1', category: 'Governance & Control', question_text: 'ระบุ Document Title, Version Number, วันที่อัปเดต และชื่อผู้จัดทำชัดเจน', target_metric: '100% Header & Metadata', severity: 'Major', is_mandatory: true, order_index: 4 }
            ]
        };
        isClonedUnsavedDraft = false;
        initialSnapshot = serializeForm(form);
        lastFetchedPreviewKey = '';
    }

    function startNewTemplate() {
        guardUnsavedThenRun(applyNewTemplateDraft);
    }

    function duplicateCurrentTemplate() {
        guardUnsavedThenRun(() => {
            activeTemplate = null;
            const inheritedPid = form.project_id || getActiveTopbarProjectId();
            form = {
                ...form,
                template_id: null,
                project_id: inheritedPid,
                title: `${form.title || 'Template'} (Copy)`,
                is_active: true,
                items: form.items.map((it, idx) => ({ ...it, item_id: undefined, order_index: idx + 1 }))
            };
            isClonedUnsavedDraft = true;
            initialSnapshot = '__CLONED_DRAFT__';
            lastFetchedPreviewKey = '';
            toast('คัดลอกเป็นร่าง Template ใหม่แล้ว (กดบันทึกเพื่อสร้างจริง)', 'info');
        });
    }

    async function handleQuickToggleActive(tpl, e) {
        e?.stopPropagation();
        if (togglingIds.has(tpl.template_id)) return;
        const nextActive = !tpl.is_active;
        togglingIds = new Set([...togglingIds, tpl.template_id]);
        try {
            const res = await fetch(`/api/exit-criteria/templates/${tpl.template_id}`, {
                method: 'PATCH',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ is_active: nextActive })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                templates = templates.map((t) =>
                    t.template_id === tpl.template_id ? { ...t, is_active: nextActive } : t
                );
                if (form.template_id === tpl.template_id) {
                    form.is_active = nextActive;
                    if (!isClonedUnsavedDraft) {
                        initialSnapshot = serializeForm(form);
                    }
                }
                fetchEffectivePreview(form.doc_type, form.project_id);
                toast(`อัปเดต "${tpl.title}" เป็น ${nextActive ? 'เปิดใช้งาน' : 'ปิดใช้งาน'} แล้ว`, 'success');
            } else {
                toast(data.error || 'เปลี่ยนสถานะไม่สำเร็จ', 'error');
            }
        } catch (_) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            togglingIds.delete(tpl.template_id);
            togglingIds = new Set(togglingIds);
        }
    }

    function computeNextCodeForCategory(catId) {
        const catMeta = CATEGORIES.find((c) => c.id === catId) || CATEGORIES[1];
        const catItems = form.items.filter((i) => i.category === catId);
        let maxSub = 0;
        for (const it of catItems) {
            const m = String(it.item_code || '').match(/^\d+\.(\d+)$/);
            if (m) {
                maxSub = Math.max(maxSub, parseInt(m[1], 10));
            }
        }
        const nextSub = Math.max(catItems.length + 1, maxSub + 1);
        return `${catMeta.prefix}.${nextSub}`;
    }

    async function addItem(catId) {
        collapsedCategories = { ...collapsedCategories, [catId]: false };
        const catMeta = CATEGORIES.find((c) => c.id === catId) || CATEGORIES[1];
        const nextCode = computeNextCodeForCategory(catId);
        form.items = [
            ...form.items,
            {
                item_code: nextCode,
                category: catId,
                question_text: '',
                target_metric: catMeta.defaultMetric,
                severity: catMeta.defaultSeverity,
                is_mandatory: catMeta.defaultMandatory,
                order_index: form.items.length + 1
            }
        ];
        const newIdx = form.items.length - 1;
        await tick();
        document.getElementById(`ec-q-${newIdx}`)?.focus();
    }

    function clearUndoBanner() {
        lastDeletedItem = null;
        if (undoTimer) {
            clearTimeout(undoTimer);
            undoTimer = null;
        }
    }

    function removeItem(index) {
        const removed = form.items[index];
        if (!removed) return;
        clearUndoBanner();
        lastDeletedItem = { item: { ...removed }, index };
        form.items = form.items.filter((_, idx) => idx !== index);
        undoTimer = setTimeout(() => {
            lastDeletedItem = null;
        }, 8000);
    }

    function undoRemoveItem() {
        if (!lastDeletedItem) return;
        const copy = [...form.items];
        const insertAt = Math.min(lastDeletedItem.index, copy.length);
        copy.splice(insertAt, 0, lastDeletedItem.item);
        form.items = copy.map((it, i) => ({ ...it, order_index: i + 1 }));
        clearUndoBanner();
        toast('กู้คืนข้อตรวจที่เพิ่งลบกลับมาแล้ว', 'success');
    }

    function renumberCategoryInPlace(itemsArr, catId) {
        const catMeta = CATEGORIES.find((c) => c.id === catId);
        if (!catMeta) return itemsArr;
        let sub = 1;
        return itemsArr.map((it) => {
            if (it.category !== catId) return it;
            const autoMatch = /^\d+\.\d+$/.test(String(it.item_code || '').trim());
            return {
                ...it,
                item_code: autoMatch ? `${catMeta.prefix}.${sub++}` : it.item_code
            };
        });
    }

    function moveItemInCategory(itemIdx, direction) {
        const cat = form.items[itemIdx]?.category;
        if (!cat) return;
        const catIndices = form.items
            .map((it, idx) => (it.category === cat ? idx : -1))
            .filter((idx) => idx !== -1);
        const pos = catIndices.indexOf(itemIdx);
        const swapPos = pos + direction;
        if (swapPos < 0 || swapPos >= catIndices.length) return;
        const targetIdx = catIndices[swapPos];
        const copy = [...form.items];
        const tmp = copy[itemIdx];
        copy[itemIdx] = copy[targetIdx];
        copy[targetIdx] = tmp;
        form.items = renumberCategoryInPlace(copy, cat).map((it, i) => ({ ...it, order_index: i + 1 }));
    }

    function changeItemCategory(itemIdx, newCatId) {
        const oldCat = form.items[itemIdx]?.category;
        if (!oldCat || oldCat === newCatId) return;
        const catMeta = CATEGORIES.find((c) => c.id === newCatId) || CATEGORIES[1];
        collapsedCategories = { ...collapsedCategories, [newCatId]: false };
        const copy = form.items.map((it, idx) => {
            if (idx !== itemIdx) return it;
            return {
                ...it,
                category: newCatId,
                item_code: `${catMeta.prefix}.999`,
                is_mandatory: newCatId === 'Format & Consistency' ? false : it.is_mandatory
            };
        });
        const renumOld = renumberCategoryInPlace(copy, oldCat);
        const renumBoth = renumberCategoryInPlace(renumOld, newCatId);
        form.items = renumBoth.map((it, i) => ({ ...it, order_index: i + 1 }));
        toast(`ย้ายข้อตรวจไปยัง "${catMeta.shortLabel}" และจัดรหัสใหม่แล้ว`, 'info');
    }

    function renumberAllCodes(silent = false) {
        const ordered = [];
        let globalOrder = 1;
        for (const catMeta of CATEGORIES) {
            const group = form.items.filter((it) => it.category === catMeta.id);
            group.forEach((it, idx) => {
                ordered.push({
                    ...it,
                    item_code: `${catMeta.prefix}.${idx + 1}`,
                    order_index: globalOrder++
                });
            });
        }
        form.items = ordered;
        if (!silent) {
            toast('จัดเรียงรหัสข้อตรวจ (1.1, 1.2 ... 4.x) ใหม่เรียบร้อยแล้ว', 'info');
        }
    }

    function clampMaxLoops() {
        const n = parseInt(String(form.max_loops), 10);
        form.max_loops = Number.isNaN(n) ? 3 : Math.max(1, Math.min(10, n));
    }

    async function saveTemplate() {
        invalidTitleField = false;
        invalidItemIndex = -1;
        clampMaxLoops();

        if (!form.title.trim()) {
            invalidTitleField = true;
            toast('กรุณาระบุชื่อ Template', 'warning');
            await tick();
            document.getElementById('ec_title')?.focus();
            return;
        }
        if (form.is_active && form.items.length === 0) {
            toast('ไม่สามารถบันทึก Template ที่เปิดใช้งานโดยไม่มีข้อตรวจได้ กรุณาเพิ่มข้อตรวจอย่างน้อย 1 ข้อ หรือสลับเป็นปิดใช้งาน', 'warning');
            return;
        }
        const emptyIdx = form.items.findIndex((it) => !String(it.question_text || '').trim());
        if (emptyIdx !== -1) {
            const badItem = form.items[emptyIdx];
            collapsedCategories = { ...collapsedCategories, [badItem.category]: false };
            invalidItemIndex = emptyIdx;
            toast(`กรุณากรอกข้อความรายการประเมินของข้อ ${badItem.item_code} ให้ครบถ้วน`, 'warning');
            await tick();
            const el = document.getElementById(`ec-q-${emptyIdx}`);
            el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el?.focus();
            return;
        }

        saving = true;
        try {
            const isNew = !form.template_id;
            const url = isNew
                ? '/api/exit-criteria/templates'
                : `/api/exit-criteria/templates/${form.template_id}`;
            const method = isNew ? 'POST' : 'PUT';

            const payload = {
                ...form,
                project_id: form.project_id || null,
                items: form.items.map((it, idx) => ({ ...it, order_index: idx + 1 }))
            };

            const res = await fetch(url, {
                method,
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(payload)
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                isClonedUnsavedDraft = false;
                toast('บันทึกเกณฑ์ Exit Criteria และอัปเดต AI Skill เรียบร้อยแล้ว', 'success');
                const savedId = isNew ? data.template_id : form.template_id;
                await fetchTemplates(false, savedId);
            } else {
                toast(data.error || 'เกิดข้อผิดพลาดในการบันทึก', 'error');
            }
        } catch (e) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            saving = false;
        }
    }

    async function askConfirmation({ title, message, confirmText = 'ยืนยัน', cancelText = 'ยกเลิก', type = 'danger', onConfirm }) {
        lastTriggerEl = document.activeElement;
        confirmModalData = { title, message, confirmText, cancelText, type, loading: false, onConfirm };
        showConfirmModal = true;
        await tick();
        confirmDialogEl?.focus();
    }

    function closeConfirmModal() {
        showConfirmModal = false;
        confirmModalData.loading = false;
        lastTriggerEl?.focus?.();
    }

    async function handleConfirmAction() {
        if (!confirmModalData.onConfirm || confirmModalData.loading) return;
        confirmModalData.loading = true;
        try {
            await confirmModalData.onConfirm();
            closeConfirmModal();
        } finally {
            confirmModalData.loading = false;
        }
    }

    function resetUniversalGate() {
        askConfirmation({
            title: 'กู้คืนเกณฑ์มาตรฐานกลาง 13 ข้อ (Reset Universal Gate)',
            message: 'ระบบจะเขียนทับ "Universal Document Exit Criteria" ให้กลับมาเป็น 13 ข้อมาตรฐานเริ่มต้น พร้อมเปิดสถานะใช้งาน (Active) รายการที่เคยปรับแต่งไว้ใน Universal Gate จะถูกรีเซ็ตทั้งหมด ต้องการดำเนินการหรือไม่?',
            confirmText: 'ยืนยันกู้คืน 13 ข้อมาตรฐาน',
            type: 'warning',
            onConfirm: async () => {
                const res = await fetch('/api/exit-criteria/reset-universal', {
                    method: 'POST',
                    headers: getAuthHeaders()
                });
                const data = await res.json().catch(() => ({}));
                if (res.ok && data.success) {
                    isClonedUnsavedDraft = false;
                    toast('กู้คืนเกณฑ์มาตรฐานกลาง 13 ข้อ และเปิดใช้งานเรียบร้อยแล้ว!', 'success');
                    const uni = templates.find((t) => t.title === 'Universal Document Exit Criteria');
                    await fetchTemplates(true, uni?.template_id || null);
                } else {
                    toast(data.error || 'กู้คืนไม่สำเร็จ', 'error');
                }
            }
        });
    }

    function deleteTemplate(tpl, e) {
        e?.stopPropagation();
        if (templates.length <= 1) {
            toast('ต้องมีอย่างน้อย 1 Template ในระบบ', 'warning');
            return;
        }
        askConfirmation({
            title: 'ยืนยันการลบ Template',
            message: `ต้องการลบ "${tpl.title}" (${tpl.doc_type}) ออกจากระบบอย่างถาวรใช่หรือไม่? ระบบจะลบ AI Skill ที่ผูกไว้ออกให้อัตโนมัติ`,
            confirmText: 'ลบ Template ถาวร',
            type: 'danger',
            onConfirm: async () => {
                const res = await fetch(`/api/exit-criteria/templates/${tpl.template_id}`, {
                    method: 'DELETE',
                    headers: getAuthHeaders()
                });
                const data = await res.json().catch(() => ({}));
                if (res.ok && data.success) {
                    toast(`ลบ "${tpl.title}" เรียบร้อยแล้ว`, 'success');
                    if (form.template_id === tpl.template_id) {
                        form.template_id = null;
                        isClonedUnsavedDraft = false;
                        initialSnapshot = '';
                    }
                    await fetchTemplates(true);
                } else {
                    toast(data.error || 'ลบไม่สำเร็จ', 'error');
                }
            }
        });
    }

    function toggleCategoryCollapse(catId) {
        collapsedCategories = { ...collapsedCategories, [catId]: !collapsedCategories[catId] };
    }

    // Help Modal
    async function openHelpModal() {
        lastTriggerEl = document.activeElement;
        showHelpModal = true;
        await tick();
        helpDialogEl?.focus();
    }
    function closeHelpModal() {
        showHelpModal = false;
        lastTriggerEl?.focus?.();
    }

    // AI Suggest Modal
    async function openAiModal() {
        lastTriggerEl = document.activeElement;
        aiDocType = form.doc_type === 'ALL' ? 'SRS' : form.doc_type;
        aiHint = '';
        aiMode = form.items.length === 0 ? 'replace' : 'append';
        showAiSuggestModal = true;
        await tick();
        aiDialogEl?.focus();
    }
    function closeAiModal() {
        showAiSuggestModal = false;
        lastTriggerEl?.focus?.();
    }

    async function handleRunAiSuggest() {
        if (isGeneratingAi) return;
        isGeneratingAi = true;
        try {
            const res = await fetch('/api/exit-criteria/ai-suggest', {
                method: 'POST',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ doc_type: aiDocType, hint: aiHint })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success && Array.isArray(data.items)) {
                const normalizedSuggested = normalizeItemsList(data.items);
                if (aiMode === 'replace') {
                    form.items = normalizedSuggested;
                } else {
                    form.items = [...form.items, ...normalizedSuggested];
                }
                renumberAllCodes(true);
                collapsedCategories = {};
                toast(`AI สร้างรายการประเมิน ${normalizedSuggested.length} ข้อให้เรียบร้อยแล้ว (กดบันทึกเพื่อใช้งานจริง)`, 'success');
                closeAiModal();
            } else {
                toast(data.error || 'AI ไม่สามารถสร้างเกณฑ์ได้', 'error');
            }
        } catch (_) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อ AI', 'error');
        } finally {
            isGeneratingAi = false;
        }
    }

    // Dry-Run Sandbox Modal
    async function openSandboxModal() {
        lastTriggerEl = document.activeElement;
        sandboxResult = null;
        sandboxUseDraft = true;
        if (!sandboxSampleText.trim()) {
            const now = new Date();
            const thaiDate = `${String(now.getDate()).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')}/${now.getFullYear() + 543}`;
            sandboxSampleText = `--- [หน้า 1] ---\n# เอกสาร ${form.doc_type === 'ALL' ? 'SRS' : form.doc_type}: ระบบจัดการคำสั่งซื้อ\nVersion: 1.2 | วันที่อัปเดต: ${thaiDate} | ผู้จัดทำ: ทีม QA\n\n## 1. วัตถุประสงค์และขอบเขต (Scope)\nเอกสารนี้ระบุความต้องการทางธุรกิจและฟังก์ชันหลักของระบบ\n\n## 2. รายละเอียดความต้องการ (Requirements)\n- REQ-001: ผู้ใช้เข้าสู่ระบบด้วย Email และ Password พร้อมตรวจสอบกรณีรหัสผิด\n- REQ-002: ระบบบันทึกประวัติการสั่งซื้อและส่งอีเมลยืนยัน`;
        }
        showSandboxModal = true;
        await tick();
        sandboxDialogEl?.focus();
    }
    function closeSandboxModal() {
        showSandboxModal = false;
        lastTriggerEl?.focus?.();
    }

    async function handleRunSandbox() {
        if (!sandboxSampleText.trim() || isRunningSandbox) {
            if (!sandboxSampleText.trim()) toast('กรุณาวางข้อความตัวอย่างเอกสารก่อนทดลองตรวจ', 'warning');
            return;
        }
        isRunningSandbox = true;
        sandboxResult = null;
        try {
            const res = await fetch('/api/exit-criteria/test-evaluate', {
                method: 'POST',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    sample_text: sandboxSampleText,
                    doc_type: form.doc_type,
                    project_id: form.project_id || null,
                    use_draft: sandboxUseDraft,
                    items: form.items
                })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                sandboxResult = data.evaluation;
            } else {
                toast(data.error || 'ทดลองประเมินไม่สำเร็จ', 'error');
            }
        } catch (_) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            isRunningSandbox = false;
        }
    }
</script>

<svelte:window on:keydown={handleWindowKeydown} />

<div class="ec-container">
    <!-- Compact Page Header -->
    <header class="ec-header ec-glass">
        <div class="ec-header-left">
            <div class="ec-title-row">
                <h1 class="ec-title">Exit Criteria Quality Gate</h1>
                <span class="ec-gate-pill">Document Review Gate</span>
            </div>
            <p class="ec-subtitle">กำหนดเกณฑ์มาตรฐานกลางและเกณฑ์รายโครงการ สำหรับประเมินเอกสารใน QA Consult และ AI Document Creation</p>
        </div>
        <div class="ec-header-actions">
            <button type="button" class="ec-btn ec-btn-secondary" on:click={openHelpModal}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                คู่มือการใช้งาน
            </button>
            <button type="button" class="ec-btn ec-btn-secondary" on:click={resetUniversalGate} title="กู้คืน Universal Document Exit Criteria ให้ครบ 13 ข้อมาตรฐานและเปิดใช้งาน">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>
                กู้คืนเกณฑ์กลาง (13 ข้อ)
            </button>
        </div>
    </header>

    <div class="ec-layout">
        <!-- Left Sidebar: Template Selector -->
        <aside class="ec-sidebar ec-glass">
            <div class="ec-sidebar-head">
                <span class="ec-sidebar-title">รายการ Template ({filteredTemplates.length})</span>
                <button type="button" class="ec-btn ec-btn-tonal ec-btn-sm" on:click={startNewTemplate}>
                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                    สร้างใหม่
                </button>
            </div>

            <div class="ec-sidebar-filters">
                <div class="ec-search-wrap">
                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <input type="text" bind:value={search} placeholder="ค้นหาชื่อ, ประเภท หรือโครงการ..." aria-label="ค้นหา Template" />
                </div>
                <CustomSelect
                    bind:value={filterDocType}
                    ariaLabel="กรองตามประเภทเอกสาร"
                    options={[{ value: '', label: 'ทุกประเภทเอกสาร (All Types)' }, ...docTypes.map((dt) => ({ value: dt, label: dt }))]}
                    width="100%"
                />
                <CustomSelect
                    bind:value={filterStatus}
                    ariaLabel="กรองตามสถานะเปิด/ปิดใช้งาน"
                    options={statusFilterOptions}
                    width="100%"
                />
                {#if projects.length > 0}
                    <CustomSelect
                        bind:value={filterProjectScope}
                        ariaLabel="กรองตามขอบเขตโครงการ"
                        options={sidebarProjectFilterOptions}
                        width="100%"
                    />
                {/if}
            </div>

            <div class="ec-template-list">
                {#if loading && templates.length === 0}
                    <div class="ec-empty-side">กำลังโหลดรายการ Template...</div>
                {:else if filteredTemplates.length === 0}
                    <div class="ec-empty-side">
                        <p>ไม่พบ Template ที่ตรงกับตัวกรอง</p>
                        {#if hasSidebarFilters}
                            <button type="button" class="ec-btn ec-btn-secondary ec-btn-sm" on:click={resetSidebarFilters}>
                                ล้างตัวกรองทั้งหมด
                            </button>
                        {/if}
                    </div>
                {:else}
                    {#each filteredTemplates as t (t.template_id)}
                        <div class="ec-tpl-card" class:selected={form.template_id === t.template_id} class:is-off={!t.is_active}>
                            <button type="button" class="ec-tpl-select-btn" on:click={() => selectTemplate(t.template_id)}>
                                <div class="ec-tpl-top">
                                    <span class="ec-tpl-title">{t.title}</span>
                                    <span class="ec-doc-tag" class:universal={t.doc_type === 'ALL'}>
                                        {t.doc_type === 'ALL' ? 'Universal' : t.doc_type}
                                    </span>
                                </div>
                                <p class="ec-tpl-desc">{t.description || 'ไม่มีคำอธิบาย'}</p>
                                <div class="ec-tpl-badges">
                                    <span class="ec-meta-chip">{t.item_count || 0} ข้อ</span>
                                    {#if t.project_id}
                                        <span class="ec-meta-chip project">{t.project_code || t.project_name || 'Project'}</span>
                                    {:else}
                                        <span class="ec-meta-chip global">Global</span>
                                    {/if}
                                    <span class="ec-status-tag" class:on={t.is_active}>
                                        {t.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </div>
                            </button>

                            <div class="ec-tpl-card-actions">
                                <label class="mini-switch" title={t.is_active ? 'คลิกเพื่อปิดใช้งาน Template นี้' : 'คลิกเพื่อเปิดใช้งาน Template นี้'}>
                                    <input
                                        type="checkbox"
                                        checked={t.is_active}
                                        disabled={togglingIds.has(t.template_id)}
                                        aria-label={`เปิด/ปิดใช้งาน ${t.title}`}
                                        on:change={(e) => handleQuickToggleActive(t, e)}
                                    />
                                    <span class="mini-slider"></span>
                                </label>
                                {#if templates.length > 1}
                                    <button
                                        type="button"
                                        class="ec-icon-btn danger"
                                        title="ลบ Template นี้"
                                        aria-label={`ลบ ${t.title}`}
                                        on:click={(e) => deleteTemplate(t, e)}
                                    >
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                    </button>
                                {/if}
                            </div>
                        </div>
                    {/each}
                {/if}
            </div>
        </aside>

        <!-- Main Editor Workspace -->
        <main class="ec-workspace">
            {#if loadingDetail}
                <div class="ec-panel ec-glass ec-loading-box">กำลังโหลดรายละเอียดเกณฑ์...</div>
            {:else}
                <!-- Sticky Editor Command Bar (Always visible when scrolling long categories) -->
                <div class="ec-sticky-bar ec-glass">
                    <div class="ec-sticky-left">
                        <h2 class="ec-active-heading">{form.title || 'ร่าง Template ใหม่'}</h2>
                        <span class="ec-scope-pill" class:is-global={!form.project_id}>
                            {activeProjectName}
                        </span>
                        <span class="ec-sync-note" title="เมื่อกดบันทึก ระบบจะซิงก์เป็น [Exit Criteria] Skill ในหน้า AI Skills โดยอัตโนมัติ">
                            ซิงก์อัตโนมัติกับ AI Skills
                        </span>
                        {#if isFormDirty}
                            <span class="dirty-pill" role="status"><span class="dirty-dot"></span>ยังไม่ได้บันทึก</span>
                        {/if}
                    </div>

                    <div class="ec-sticky-actions">
                        <button type="button" class="ec-btn ec-btn-secondary ec-btn-sm" on:click={openAiModal} title="ให้ AI ช่วยร่างข้อตรวจตามประเภทเอกสาร">
                            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                            AI ร่างเกณฑ์
                        </button>
                        <button type="button" class="ec-btn ec-btn-secondary ec-btn-sm" on:click={openSandboxModal} title="ทดลองนำข้อความเอกสารมาประเมินกับเกณฑ์ชุดนี้">
                            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            ทดลองตรวจ
                        </button>
                        {#if form.template_id}
                            <button type="button" class="ec-btn ec-btn-secondary ec-btn-sm" on:click={duplicateCurrentTemplate} title="คัดลอกไปสร้างเป็น Template ใหม่">
                                คัดลอก
                            </button>
                        {/if}
                        {#if isFormDirty}
                            <button type="button" class="ec-btn ec-btn-secondary ec-btn-sm" on:click={revertChanges} title="ยกเลิกการแก้ไขและคืนค่าที่บันทึกไว้ล่าสุด">
                                คืนค่าเดิม
                            </button>
                        {/if}
                        <button type="button" class="ec-btn ec-btn-primary" on:click={saveTemplate} disabled={saving} title="บันทึกเกณฑ์ Exit Criteria (Ctrl+S)">
                            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
                            {saving ? 'กำลังบันทึก...' : 'บันทึกเกณฑ์ Exit Criteria'}
                        </button>
                    </div>
                </div>

                {#if lastDeletedItem}
                    <div class="ec-undo-bar" role="status" aria-live="polite">
                        <span>ลบข้อตรวจ <strong>{lastDeletedItem.item.item_code}</strong> แล้ว</span>
                        <button type="button" class="ec-btn ec-btn-tonal ec-btn-sm" on:click={undoRemoveItem}>
                            เลิกทำ (Undo)
                        </button>
                    </div>
                {/if}

                <!-- Template Metadata Panel -->
                <section class="ec-panel ec-glass">
                    <div class="ec-form-grid">
                        <div class="ec-field span-2">
                            <label for="ec_title">ชื่อ Template (Document Checklist Title)</label>
                            <input
                                id="ec_title"
                                type="text"
                                class="ec-control"
                                class:is-invalid={invalidTitleField}
                                bind:value={form.title}
                                on:input={() => (invalidTitleField = false)}
                                placeholder="เช่น Universal Document Exit Criteria หรือ SRS โครงการ e-Manifest"
                            />
                        </div>

                        <div class="ec-field">
                            <label for="ec_doc_type">ประเภทเอกสารเป้าหมาย (Doc Type)</label>
                            <CustomSelect
                                id="ec_doc_type"
                                ariaLabel="ประเภทเอกสารเป้าหมาย"
                                bind:value={form.doc_type}
                                options={docTypes.map((dt) => ({ value: dt, label: dt === 'ALL' ? 'ALL (เกณฑ์มาตรฐานกลางทุกเอกสาร)' : dt }))}
                                width="100%"
                            />
                        </div>

                        <div class="ec-field">
                            <label for="ec_project_scope">ขอบเขตโครงการ (Project Scope)</label>
                            <CustomSelect
                                id="ec_project_scope"
                                ariaLabel="ขอบเขตโครงการ"
                                bind:value={form.project_id}
                                options={projectScopeOptions}
                                width="100%"
                            />
                        </div>

                        <div class="ec-field">
                            <span class="ec-field-label">สถานะการใช้งาน (Active Status)</span>
                            <label class="ec-status-toggle-box">
                                <input type="checkbox" bind:checked={form.is_active} aria-label="เปิดหรือปิดใช้งานเกณฑ์ชุดนี้" />
                                <span class="ec-switch-track"></span>
                                <span class="ec-switch-text" class:active={form.is_active}>
                                    {form.is_active ? 'เปิดใช้งาน (Active — นำไปตรวจจริง)' : 'ปิดใช้งาน (Inactive — ข้ามการตรวจ)'}
                                </span>
                            </label>
                        </div>

                        <div class="ec-field">
                            <label for="ec_max_loops">จำกัดรอบส่งแก้ของ AI อัตโนมัติ (1–10 รอบ)</label>
                            <input
                                id="ec_max_loops"
                                type="number"
                                min="1"
                                max="10"
                                class="ec-control"
                                bind:value={form.max_loops}
                                on:blur={clampMaxLoops}
                            />
                            <span class="ec-field-hint">ใช้คุมจำนวนรอบสูงสุดที่ AI แก้เอกสารซ้ำอัตโนมัติใน QA Document Creation</span>
                        </div>

                        <div class="ec-field span-2">
                            <label for="ec_desc">คำอธิบายวัตถุประสงค์</label>
                            <textarea id="ec_desc" rows="2" class="ec-control" bind:value={form.description} placeholder="ระบุขอบเขตและวัตถุประสงค์ของชุดเกณฑ์นี้..."></textarea>
                        </div>
                    </div>

                    <!-- Live Draft-Aware Effective Gate Simulator -->
                    {#if liveEffectiveSummary}
                        <div class="ec-effective-banner" class:warn={!liveEffectiveSummary.universalActive}>
                            <div class="eff-main">
                                <strong>จำลองเกณฑ์ตรวจจริงสำหรับเอกสาร "{form.doc_type}" ({activeProjectName}):</strong>
                                {#if liveEffectiveSummary.usingFallback}
                                    <span>ไม่มีเกณฑ์ที่เปิดใช้งาน — ระบบจะดึงเกณฑ์สำรองมาตรฐาน 13 ข้อมาตรวจให้อัตโนมัติ</span>
                                {:else}
                                    <span>
                                        รวมทั้งหมด <strong>{liveEffectiveSummary.totalItems} ข้อตรวจ</strong> จาก
                                        {liveEffectiveSummary.breakdown.map((b) => `${b.title} (${b.count} ข้อ)`).join(' + ')}
                                    </span>
                                {/if}
                                {#if !liveEffectiveSummary.universalActive}
                                    <div class="eff-warn-note">
                                        เกณฑ์กลาง "Universal Document Exit Criteria (ALL)" ถูกปิดใช้งานอยู่ เอกสารทั่วไปที่ไม่มี Template เฉพาะจะไม่ถูกตรวจด้วยเกณฑ์กลางขององค์กร
                                    </div>
                                {/if}
                            </div>
                            <div class="eff-actions">
                                <button type="button" class="ec-btn ec-btn-secondary ec-btn-sm" on:click={() => renumberAllCodes(false)}>
                                    จัดรหัสข้อ 1.1–4.x
                                </button>
                                {#if !liveEffectiveSummary.universalActive}
                                    <button type="button" class="ec-btn ec-btn-tonal ec-btn-sm" on:click={resetUniversalGate}>
                                        เปิดใช้ & กู้คืน 13 ข้อ
                                    </button>
                                {/if}
                            </div>
                        </div>
                    {/if}
                </section>

                <!-- 4 Collapsible Standard Checklist Categories with Full-Width 2-Row Rule Cards -->
                {#each CATEGORIES as catMeta (catMeta.id)}
                    {@const catEntries = form.items.map((item, idx) => ({ item, idx })).filter((x) => x.item.category === catMeta.id)}
                    {@const isCollapsed = Boolean(collapsedCategories[catMeta.id])}
                    <section class="ec-panel ec-glass ec-cat-section">
                        <div class="ec-cat-header">
                            <button
                                type="button"
                                class="ec-cat-collapse-btn"
                                aria-expanded={!isCollapsed}
                                on:click={() => toggleCategoryCollapse(catMeta.id)}
                            >
                                <svg class="ec-chevron" class:collapsed={isCollapsed} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="16" height="16"><polyline points="6 9 12 15 18 9"></polyline></svg>
                                <h3>{catMeta.title}</h3>
                                <span class="ec-count-badge">{catEntries.length} ข้อ</span>
                                {#if catMeta.id === 'Format & Consistency'}
                                    <span class="ec-cond-hint" title="ข้อที่ไม่บังคับผ่านในหมวด 3 หากไม่ผ่านจะได้สถานะ CONDITIONAL PASSED แทน REJECTED">
                                        หมวดผ่อนปรน (Conditional Pass)
                                    </span>
                                {/if}
                            </button>
                            <button type="button" class="ec-btn ec-btn-tonal ec-btn-sm" on:click={() => addItem(catMeta.id)}>
                                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                                เพิ่มข้อตรวจ
                            </button>
                        </div>

                        {#if !isCollapsed}
                            {#if catEntries.length === 0}
                                <div class="ec-empty-cat">
                                    ยังไม่มีรายการประเมินในหมวดนี้ — คลิก "เพิ่มข้อตรวจ" หรือใช้ปุ่ม "AI ร่างเกณฑ์" ด้านบน
                                </div>
                            {:else}
                                <div class="ec-rule-cards-list">
                                    {#each catEntries as entry, posInCat (entry.idx)}
                                        {@const item = entry.item}
                                        {@const itemIdx = entry.idx}
                                        <div class="ec-rule-item-card" class:is-invalid={invalidItemIndex === itemIdx}>
                                            <!-- Row 1: Code + Full-Width Question Textarea + Reorder / Delete -->
                                            <div class="rule-row-top">
                                                <input
                                                    type="text"
                                                    bind:value={item.item_code}
                                                    class="ec-control rule-code-in"
                                                    aria-label={`รหัสข้อตรวจลำดับที่ ${posInCat + 1}`}
                                                />
                                                <textarea
                                                    id="ec-q-{itemIdx}"
                                                    rows="2"
                                                    bind:value={item.question_text}
                                                    on:input={() => { if (invalidItemIndex === itemIdx) invalidItemIndex = -1; }}
                                                    class="ec-control rule-question-in"
                                                    aria-label={`คำถามเกณฑ์ข้อ ${item.item_code}`}
                                                    placeholder="ระบุเงื่อนไขที่ต้องการให้ AI ตรวจสอบในเอกสารอย่างชัดเจน (รองรับทั้งภาษาไทยและอังกฤษ)..."
                                                ></textarea>
                                                <div class="rule-row-actions">
                                                    <button
                                                        type="button"
                                                        class="ec-icon-btn"
                                                        disabled={posInCat === 0}
                                                        title="เลื่อนขึ้น"
                                                        aria-label={`เลื่อนข้อ ${item.item_code} ขึ้น`}
                                                        on:click={() => moveItemInCategory(itemIdx, -1)}
                                                    >
                                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><polyline points="18 15 12 9 6 15"></polyline></svg>
                                                    </button>
                                                    <button
                                                        type="button"
                                                        class="ec-icon-btn"
                                                        disabled={posInCat === catEntries.length - 1}
                                                        title="เลื่อนลง"
                                                        aria-label={`เลื่อนข้อ ${item.item_code} ลง`}
                                                        on:click={() => moveItemInCategory(itemIdx, 1)}
                                                    >
                                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><polyline points="6 9 12 15 18 9"></polyline></svg>
                                                    </button>
                                                    <button
                                                        type="button"
                                                        class="ec-icon-btn danger"
                                                        title="ลบข้อตรวจนี้"
                                                        aria-label={`ลบข้อตรวจ ${item.item_code}`}
                                                        on:click={() => removeItem(itemIdx)}
                                                    >
                                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                                    </button>
                                                </div>
                                            </div>

                                            <!-- Row 2: KPI Indicator + Severity + Mandatory Switch + Move Category -->
                                            <div class="rule-row-bottom">
                                                <div class="rule-meta-field kpi">
                                                    <span class="meta-mini-lbl">KPI / เป้าหมาย:</span>
                                                    <input
                                                        type="text"
                                                        bind:value={item.target_metric}
                                                        class="ec-control rule-metric-in"
                                                        aria-label={`ตัวชี้วัด KPI ข้อ ${item.item_code}`}
                                                        placeholder="เช่น 100% Verified"
                                                    />
                                                </div>

                                                <div class="rule-meta-field">
                                                    <span class="meta-mini-lbl">ความรุนแรง:</span>
                                                    <CustomSelect
                                                        bind:value={item.severity}
                                                        ariaLabel={`ความรุนแรงข้อ ${item.item_code}`}
                                                        options={severityOptions}
                                                        size="sm"
                                                        width="150px"
                                                        minWidth="140px"
                                                    />
                                                </div>

                                                <div class="rule-meta-field">
                                                    <span class="meta-mini-lbl">หมวดหมู่:</span>
                                                    <CustomSelect
                                                        value={item.category}
                                                        ariaLabel={`ย้ายหมวดหมู่ข้อ ${item.item_code}`}
                                                        options={categoryMoveOptions}
                                                        size="sm"
                                                        width="185px"
                                                        minWidth="165px"
                                                        on:change={(e) => changeItemCategory(itemIdx, e.detail)}
                                                    />
                                                </div>

                                                <label class="rule-mand-pill" class:active={item.is_mandatory}>
                                                    <input
                                                        type="checkbox"
                                                        bind:checked={item.is_mandatory}
                                                        aria-label={`บังคับผ่านข้อ ${item.item_code}`}
                                                    />
                                                    <span>{item.is_mandatory ? 'บังคับผ่าน (Mandatory)' : 'ผ่อนปรนได้ (Optional)'}</span>
                                                </label>
                                            </div>
                                        </div>
                                    {/each}
                                </div>
                            {/if}
                        {/if}
                    </section>
                {/each}

                <!-- Collapsible Final Gate Rules Summary -->
                <section class="ec-panel ec-glass ec-rules-panel">
                    <button
                        type="button"
                        class="ec-cat-collapse-btn full"
                        aria-expanded={showRulesSection}
                        on:click={() => (showRulesSection = !showRulesSection)}
                    >
                        <svg class="ec-chevron" class:collapsed={!showRulesSection} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="16" height="16"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        <h3>กฎการตัดสินผลการตรวจอัตโนมัติ (Quality Gate Verdict Rules)</h3>
                    </button>
                    {#if showRulesSection}
                        <div class="ec-rules-grid">
                            <div class="ec-rule-card">
                                <span class="verdict-pill pass">PASSED (ผ่านบริบูรณ์)</span>
                                <p>ผ่านข้อตรวจที่เกี่ยวข้องครบทุกข้อ และไม่มี Critical / High Findings คงค้าง</p>
                            </div>
                            <div class="ec-rule-card">
                                <span class="verdict-pill cond">CONDITIONAL PASSED (ผ่านแบบมีเงื่อนไข)</span>
                                <p>ผ่านข้อบังคับ (Mandatory / Critical) ทุกข้อในหมวด 1, 2, 4 ตกเฉพาะข้อ Minor ที่ผ่อนปรนได้ในหมวด 3</p>
                            </div>
                            <div class="ec-rule-card">
                                <span class="verdict-pill reject">REJECTED (ไม่ผ่าน — ต้องแก้ไข)</span>
                                <p>ตกข้อที่ตั้งเป็น "บังคับผ่าน" หรือระดับ Critical ข้อใดข้อหนึ่ง หรือยังมี Critical/High Defect คงค้าง</p>
                            </div>
                        </div>
                    {/if}
                </section>
            {/if}
        </main>
    </div>
</div>

<!-- AI Suggest Criteria Modal -->
{#if showAiSuggestModal}
<div class="ec-modal-backdrop" role="presentation" on:click={() => { if (!isGeneratingAi) closeAiModal(); }}>
    <div bind:this={aiDialogEl} class="ec-modal-box" role="dialog" aria-modal="true" aria-labelledby="ai-suggest-title" tabindex="-1" on:keydown={trapFocus} on:click|stopPropagation>
        <div class="ec-modal-head">
            <div>
                <h2 id="ai-suggest-title">AI ช่วยร่างรายการ Exit Criteria</h2>
                <p>สร้างรายการตรวจสอบเฉพาะทางครบทั้ง 4 หมวด พร้อมตั้งค่า KPI และความรุนแรงให้อัตโนมัติ</p>
            </div>
            <button type="button" class="ec-icon-btn" aria-label="ปิดหน้าต่าง" disabled={isGeneratingAi} on:click={closeAiModal}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="ec-modal-body">
            <div class="ec-field">
                <label for="ai_doc_type">ประเภทเอกสารที่ต้องการสร้างเกณฑ์</label>
                <CustomSelect id="ai_doc_type" ariaLabel="ประเภทเอกสารที่ต้องการสร้างเกณฑ์" bind:value={aiDocType} options={docTypes.filter((d) => d !== 'ALL').map((d) => ({ value: d, label: d }))} width="100%" />
            </div>
            <div class="ec-field">
                <label for="ai_hint">โจทย์หรือเงื่อนไขเฉพาะของโครงการ (ไม่บังคับ)</label>
                <textarea id="ai_hint" rows="3" class="ec-control" bind:value={aiHint} placeholder="เช่น เน้นตรวจ API Security OWASP, ต้องมีตาราง Data Dictionary และ PDPA Masking"></textarea>
            </div>
            <div class="ec-radio-row">
                <label class="ec-radio-opt" class:active={aiMode === 'replace'}>
                    <input type="radio" name="aiMode" value="replace" bind:group={aiMode} />
                    <span>แทนที่รายการเดิมในฟอร์ม</span>
                </label>
                <label class="ec-radio-opt" class:active={aiMode === 'append'}>
                    <input type="radio" name="aiMode" value="append" bind:group={aiMode} />
                    <span>เพิ่มต่อท้ายรายการเดิม (พร้อมรันเลขข้อใหม่)</span>
                </label>
            </div>
        </div>
        <div class="ec-modal-foot">
            <button type="button" class="ec-btn ec-btn-secondary" disabled={isGeneratingAi} on:click={closeAiModal}>ยกเลิก</button>
            <button type="button" class="ec-btn ec-btn-primary" disabled={isGeneratingAi} on:click={handleRunAiSuggest}>
                {isGeneratingAi ? 'AI กำลังร่างเกณฑ์...' : 'สร้างรายการด้วย AI'}
            </button>
        </div>
    </div>
</div>
{/if}

<!-- Dry-Run Sandbox Modal -->
{#if showSandboxModal}
<div class="ec-modal-backdrop" role="presentation" on:click={() => { if (!isRunningSandbox) closeSandboxModal(); }}>
    <div bind:this={sandboxDialogEl} class="ec-modal-box large" role="dialog" aria-modal="true" aria-labelledby="sandbox-title" tabindex="-1" on:keydown={trapFocus} on:click|stopPropagation>
        <div class="ec-modal-head">
            <div>
                <h2 id="sandbox-title">ทดลองตรวจเอกสารด้วย Exit Criteria (Dry-Run Sandbox)</h2>
                <p>ทดสอบว่าเกณฑ์ที่ตั้งไว้ประเมินผลลัพธ์ตรงตามความต้องการหรือไม่ โดยไม่กระทบประวัติงานจริง</p>
            </div>
            <button type="button" class="ec-icon-btn" aria-label="ปิดหน้าต่าง" disabled={isRunningSandbox} on:click={closeSandboxModal}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="ec-modal-body">
            <div class="ec-radio-row">
                <label class="ec-radio-opt" class:active={sandboxUseDraft}>
                    <input type="radio" name="sbMode" value={true} bind:group={sandboxUseDraft} />
                    <span>ตรวจด้วยร่างเกณฑ์ในหน้าจอนี้ ({form.items.length} ข้อ)</span>
                </label>
                <label class="ec-radio-opt" class:active={!sandboxUseDraft}>
                    <input type="radio" name="sbMode" value={false} bind:group={sandboxUseDraft} />
                    <span>ตรวจด้วยเกณฑ์รวมที่บันทึกไว้ในระบบ ({form.doc_type})</span>
                </label>
            </div>

            <div class="ec-field">
                <label for="sb_text">ข้อความตัวอย่างเอกสารสำหรับทดสอบ</label>
                <textarea id="sb_text" rows="6" class="ec-control" bind:value={sandboxSampleText} placeholder="วางเนื้อหาเอกสาร Markdown หรือข้อความที่ต้องการทดลองตรวจ..."></textarea>
            </div>

            {#if sandboxResult}
                <div class="sb-result-card">
                    <div class="sb-result-head">
                        <span class="verdict-pill" class:pass={sandboxResult.status === 'PASSED'} class:cond={sandboxResult.status === 'CONDITIONAL_PASSED'} class:reject={sandboxResult.status === 'REJECTED'}>
                            {sandboxResult.status}
                        </span>
                        <strong class="sb-score">{sandboxResult.score_percentage}%</strong>
                        <span class="sb-counts">
                            (ผ่าน {sandboxResult.passed_items} · ไม่ผ่าน {sandboxResult.failed_items} · N/A {sandboxResult.na_items})
                        </span>
                    </div>
                    <p class="sb-summary">{sandboxResult.summary_remarks}</p>
                    <div class="sb-items-list">
                        {#each sandboxResult.items || [] as it}
                            <div class="sb-item-row" class:fail={it.status === 'FAIL'}>
                                <span class="sb-code">{it.item_code}</span>
                                <span class="sb-st {it.status.toLowerCase()}">{it.status}</span>
                                <div class="sb-detail">
                                    <div class="sb-q">{it.question_text}</div>
                                    <div class="sb-rem">{it.remarks}</div>
                                </div>
                            </div>
                        {/each}
                    </div>
                </div>
            {/if}
        </div>
        <div class="ec-modal-foot">
            <button type="button" class="ec-btn ec-btn-secondary" disabled={isRunningSandbox} on:click={closeSandboxModal}>ปิดหน้าต่าง</button>
            <button type="button" class="ec-btn ec-btn-primary" disabled={isRunningSandbox} on:click={handleRunSandbox}>
                {isRunningSandbox ? 'กำลังประเมินด้วย AI...' : 'รันทดสอบเกณฑ์'}
            </button>
        </div>
    </div>
</div>
{/if}

<!-- Help Guide Modal -->
{#if showHelpModal}
<div class="ec-modal-backdrop" role="presentation" on:click={closeHelpModal}>
    <div bind:this={helpDialogEl} class="ec-modal-box large" role="dialog" aria-modal="true" aria-labelledby="help-modal-title" tabindex="-1" on:keydown={trapFocus} on:click|stopPropagation>
        <div class="ec-modal-head">
            <div>
                <h2 id="help-modal-title">คู่มือการตั้งค่าและใช้งาน Exit Criteria Quality Gate</h2>
                <p>หลักการทำงานของการรวมเกณฑ์กลาง (ALL) + เกณฑ์เฉพาะประเภทเอกสาร และกฎการตัดสินผลอัตโนมัติ</p>
            </div>
            <button type="button" class="ec-icon-btn" aria-label="ปิดหน้าต่าง" on:click={closeHelpModal}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        <div class="ec-modal-body">
            <div class="help-section">
                <h3>1. ระบบเลือกเกณฑ์ไปตรวจเอกสารอย่างไร?</h3>
                <p>เมื่อส่งเอกสารเข้าตรวจใน <strong>QA Consult</strong> หรือสร้างเอกสารใน <strong>QA Document Creation</strong> ระบบจะรวมรายการจาก:</p>
                <ul>
                    <li><strong>เกณฑ์กลาง (Doc Type = ALL)</strong> ที่เปิดใช้งานอยู่ (Active) เพื่อคุมมาตรฐานพื้นฐานทุกฉบับ</li>
                    <li><strong>เกณฑ์เฉพาะประเภทเอกสาร (เช่น SRS, UAT, Test Case)</strong> ที่ตรงกับเอกสารนั้น โดยให้ความสำคัญกับเกณฑ์ที่ผูกเฉพาะโครงการก่อน</li>
                </ul>
            </div>
            <div class="help-section">
                <h3>2. ตั้งค่าอย่างไรให้ได้ผลลัพธ์ตรงใจ?</h3>
                <ul>
                    <li><strong>บังคับผ่าน (Mandatory) + Critical/Major:</strong> ใช้กับหมวด 1, 2, 4 หากเอกสารตกข้อใดข้อหนึ่ง ผลรวมจะเป็น <strong>REJECTED</strong> ทันที</li>
                    <li><strong>ผ่อนปรนได้ (Optional) + Minor (หมวด 3):</strong> ใช้กับเรื่องคำผิดเล็กน้อยหรือการจัดหน้า หากหมวด 1, 2, 4 ผ่านครบแต่ตกเฉพาะข้อนี้ ผลรวมจะเป็น <strong>CONDITIONAL PASSED</strong></li>
                    <li>กด <strong>Ctrl+S</strong> เพื่อบันทึกได้ทุกเวลา และใช้ปุ่ม <strong>ทดลองตรวจ</strong> เพื่อจำลองผลประเมินจากร่างปัจจุบันก่อนบันทึกใช้งานจริง</li>
                </ul>
            </div>
        </div>
        <div class="ec-modal-foot">
            <button type="button" class="ec-btn ec-btn-primary" on:click={closeHelpModal}>เข้าใจแล้ว</button>
        </div>
    </div>
</div>
{/if}

<!-- Confirmation Modal -->
{#if showConfirmModal}
<div class="ec-modal-backdrop" role="presentation" style="z-index: calc(var(--z-modal, 10000) + 80);" on:click={() => { if (!confirmModalData.loading) closeConfirmModal(); }}>
    <div bind:this={confirmDialogEl} class="ec-modal-box confirm" role="dialog" aria-modal="true" aria-labelledby="ec-confirm-title" tabindex="-1" on:keydown={trapFocus} on:click|stopPropagation>
        <h2 id="ec-confirm-title" class="ec-confirm-title" class:warn={confirmModalData.type === 'warning'}>
            {confirmModalData.title}
        </h2>
        <p class="ec-confirm-msg">{confirmModalData.message}</p>
        <div class="ec-modal-foot center">
            <button type="button" class="ec-btn ec-btn-secondary" disabled={confirmModalData.loading} on:click={closeConfirmModal}>
                {confirmModalData.cancelText}
            </button>
            <button
                type="button"
                class={confirmModalData.type === 'danger' ? 'ec-btn ec-btn-danger' : 'ec-btn ec-btn-primary'}
                disabled={confirmModalData.loading}
                on:click={handleConfirmAction}
            >
                {confirmModalData.loading ? 'กำลังดำเนินการ...' : confirmModalData.confirmText}
            </button>
        </div>
    </div>
</div>
{/if}

<style>
    /* Spectra Obsidian System Alignment (DESIGN.md: 8px / 12px / 20px radii, 5-tier type scale, Neon Iris primary) */
    .ec-container {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 24px 28px 48px;
        color: var(--text-main);
        font-family: var(--font-th);
        width: 100%;
        scrollbar-gutter: stable;
        scrollbar-width: thin;
        scrollbar-color: rgba(129, 140, 248, 0.45) rgba(255, 255, 255, 0.03);
    }

    .ec-glass {
        background: var(--glass-bg);
        backdrop-filter: var(--glass-blur);
        -webkit-backdrop-filter: var(--glass-blur);
        border: 1px solid var(--glass-border);
        box-shadow: var(--shadow-glass);
    }

    .ec-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
        padding: 18px 22px;
        margin-bottom: 20px;
        border-radius: var(--radius-lg);
    }
    .ec-title-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .ec-title { font-size: 20px; font-weight: 700; font-family: var(--font-en); margin: 0; color: var(--text-main); }
    .ec-gate-pill {
        font-size: 12px; font-weight: 600; font-family: var(--font-en);
        padding: 4px 12px; border-radius: var(--radius-lg);
        background: rgba(99, 102, 241, 0.18); border: 1px solid rgba(129, 140, 248, 0.36);
        color: var(--primary-soft-text-hover);
    }
    .ec-subtitle { margin: 4px 0 0; font-size: 14px; color: var(--text-muted); }
    .ec-header-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

    /* Scoped Spectra Buttons (No global .btn-primary collision, no #059669 green override) */
    .ec-btn {
        min-height: 40px; padding: 0 16px; border-radius: var(--radius-md);
        font-size: 14px; font-weight: 600; font-family: var(--font-th);
        display: inline-flex; align-items: center; justify-content: center; gap: 8px;
        cursor: pointer; transition: background-color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease;
    }
    .ec-btn-sm { min-height: 34px; padding: 0 12px; font-size: 12px; border-radius: var(--radius-sm); }
    .ec-btn-primary {
        background: var(--gradient-main); color: #ffffff;
        border: 1px solid rgba(168, 85, 247, 0.45);
        box-shadow: 0 4px 16px rgba(99, 102, 241, 0.32);
    }
    .ec-btn-primary:hover:not(:disabled) {
        box-shadow: 0 6px 22px rgba(168, 85, 247, 0.48);
    }
    .ec-btn-secondary {
        background: var(--surface-card); color: var(--text-main);
        border: 1px solid var(--glass-border-light);
    }
    .ec-btn-secondary:hover:not(:disabled) {
        background: var(--surface-card-hover);
        border-color: rgba(129, 140, 248, 0.42);
    }
    .ec-btn-tonal {
        background: rgba(99, 102, 241, 0.16); color: var(--primary-soft-text-hover);
        border: 1px solid rgba(129, 140, 248, 0.38);
    }
    .ec-btn-tonal:hover:not(:disabled) {
        background: rgba(99, 102, 241, 0.28); color: #ffffff;
    }
    .ec-btn-danger {
        background: var(--danger-solid); color: #ffffff;
        border: 1px solid var(--danger-solid);
    }
    .ec-btn-danger:hover:not(:disabled) { background: var(--danger-solid-hover); }
    .ec-btn:disabled { opacity: 0.45; cursor: not-allowed; }

    .ec-icon-btn {
        width: 34px; height: 34px; border-radius: var(--radius-sm);
        background: var(--surface-card); border: 1px solid var(--glass-border);
        color: var(--text-muted); display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; flex-shrink: 0; transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
    }
    .ec-icon-btn:hover:not(:disabled) { background: var(--surface-card-hover); color: var(--text-main); border-color: var(--glass-border-light); }
    .ec-icon-btn.danger:hover:not(:disabled) {
        background: rgba(244, 63, 94, 0.16); border-color: rgba(244, 63, 94, 0.4); color: var(--danger-soft-text);
    }
    .ec-icon-btn:disabled { opacity: 0.32; cursor: not-allowed; }

    /* Layout (280px sidebar + roomy main workspace; stacks cleanly at <= 1180px) */
    .ec-layout {
        display: grid;
        grid-template-columns: 280px minmax(0, 1fr);
        gap: 20px;
        align-items: start;
    }

    /* Sidebar */
    .ec-sidebar {
        position: sticky;
        top: 12px;
        border-radius: var(--radius-lg);
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .ec-sidebar-head {
        display: flex; align-items: center; justify-content: space-between; gap: 8px;
    }
    .ec-sidebar-title { font-size: 14px; font-weight: 700; color: var(--text-main); }
    .ec-sidebar-filters { display: flex; flex-direction: column; gap: 8px; }
    .ec-search-wrap { position: relative; display: flex; align-items: center; }
    .ec-search-wrap svg { position: absolute; left: 12px; color: var(--text-dim); pointer-events: none; }
    .ec-search-wrap input {
        width: 100%; min-height: 40px;
        background: rgba(0, 0, 0, 0.26); border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-md); padding: 8px 12px 8px 36px;
        color: var(--text-main); font-size: 14px; font-family: var(--font-th);
    }

    .ec-template-list {
        display: flex; flex-direction: column; gap: 10px;
        max-height: calc(100dvh - 420px); min-height: 180px; overflow-y: auto;
        padding-right: 4px;
        scrollbar-width: thin; scrollbar-color: rgba(129, 140, 248, 0.4) transparent;
    }
    .ec-tpl-card {
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        display: flex;
        flex-direction: column;
        transition: border-color 0.16s ease, background-color 0.16s ease;
    }
    .ec-tpl-card:hover { border-color: rgba(129, 140, 248, 0.4); background: var(--surface-card-hover); }
    .ec-tpl-card.selected { background: rgba(99, 102, 241, 0.15); border-color: var(--primary); }
    .ec-tpl-card.is-off { border-style: dashed; }

    .ec-tpl-select-btn {
        background: none; border: none; text-align: left;
        padding: 12px 12px 10px; cursor: pointer; color: inherit; font: inherit; width: 100%;
    }
    .ec-tpl-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 6px; }
    .ec-tpl-title { font-size: 14px; font-weight: 700; color: var(--text-main); line-height: 1.35; }
    .ec-doc-tag {
        font-size: 12px; font-weight: 600; font-family: var(--font-en);
        padding: 2px 8px; border-radius: var(--radius-lg); flex-shrink: 0;
        background: rgba(6, 182, 212, 0.14); border: 1px solid rgba(6, 182, 212, 0.35); color: var(--accent-soft-text);
    }
    .ec-doc-tag.universal {
        background: rgba(168, 85, 247, 0.18); border-color: rgba(168, 85, 247, 0.4); color: var(--primary-soft-text-hover);
    }
    .ec-tpl-desc {
        margin: 0 0 8px; font-size: 12px; color: var(--text-muted); line-height: 1.45;
        display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }
    .ec-tpl-badges { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
    .ec-meta-chip {
        font-size: 12px; padding: 2px 8px; border-radius: var(--radius-sm);
        background: var(--bg); border: 1px solid var(--glass-border); color: var(--text-muted);
        font-variant-numeric: tabular-nums;
    }
    .ec-meta-chip.project { color: var(--accent-soft-text); border-color: rgba(6, 182, 212, 0.32); }
    .ec-meta-chip.global { color: var(--primary-soft-text); }
    .ec-status-tag {
        font-size: 12px; font-weight: 600; font-family: var(--font-en);
        padding: 2px 8px; border-radius: var(--radius-lg);
        background: rgba(255, 255, 255, 0.06); color: var(--text-muted);
    }
    .ec-status-tag.on { background: rgba(16, 185, 129, 0.16); color: var(--success-soft-text); }

    .ec-tpl-card-actions {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 12px; border-top: 1px solid var(--glass-border);
    }
    .mini-switch { position: relative; display: inline-flex; align-items: center; width: 40px; height: 22px; cursor: pointer; }
    .mini-switch input { position: absolute; opacity: 0; width: 0; height: 0; }
    .mini-slider {
        position: absolute; inset: 0; background: rgba(255, 255, 255, 0.16);
        border-radius: var(--radius-lg); transition: background-color 0.18s ease;
    }
    .mini-slider::before {
        content: ''; position: absolute; width: 16px; height: 16px; left: 3px; top: 3px;
        background: #ffffff; border-radius: 50%; transition: transform 0.18s ease;
    }
    .mini-switch input:checked + .mini-slider { background: var(--success); }
    .mini-switch input:checked + .mini-slider::before { transform: translateX(18px); }
    .mini-switch input:focus-visible + .mini-slider {
        outline: 2px solid var(--primary-soft-text-hover);
        outline-offset: 2px;
    }

    /* Workspace & Sticky Command Bar */
    .ec-workspace { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
    .ec-sticky-bar {
        position: sticky;
        top: 12px;
        z-index: 25;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
        padding: 14px 20px;
        border-radius: var(--radius-lg);
        background: rgba(18, 20, 28, 0.88);
    }
    .ec-sticky-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-width: 0; }
    .ec-active-heading { margin: 0; font-size: 16px; font-weight: 700; color: var(--text-main); }
    .ec-scope-pill {
        font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: var(--radius-lg);
        background: rgba(6, 182, 212, 0.14); border: 1px solid rgba(6, 182, 212, 0.34); color: var(--accent-soft-text);
    }
    .ec-scope-pill.is-global {
        background: rgba(168, 85, 247, 0.16); border-color: rgba(168, 85, 247, 0.38); color: var(--primary-soft-text-hover);
    }
    .ec-sync-note { font-size: 12px; color: var(--text-dim); }
    .dirty-pill {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: var(--radius-lg);
        background: rgba(245, 158, 11, 0.16); border: 1px solid rgba(245, 158, 11, 0.38); color: var(--warning-soft-text);
    }
    .dirty-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--warning); }
    .ec-sticky-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

    .ec-undo-bar {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        padding: 10px 16px; border-radius: var(--radius-md);
        background: rgba(99, 102, 241, 0.14); border: 1px solid rgba(129, 140, 248, 0.38);
        font-size: 14px; color: var(--text-main);
    }

    .ec-panel {
        border-radius: var(--radius-lg);
        padding: 20px 22px;
    }

    /* Form Controls (Unified 12px radius & 40px height matching CustomSelect) */
    .ec-form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .ec-field { display: flex; flex-direction: column; gap: 6px; }
    .ec-field.span-2 { grid-column: 1 / -1; }
    .ec-field label, .ec-field-label { font-size: 14px; font-weight: 600; color: var(--text-muted); }
    .ec-field-hint { font-size: 12px; color: var(--text-dim); }

    .ec-control {
        width: 100%;
        min-height: 40px;
        background: rgba(0, 0, 0, 0.25);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-md);
        padding: 9px 14px;
        color: var(--text-main);
        font-size: 14px;
        font-family: var(--font-th);
        transition: border-color 0.16s ease, box-shadow 0.16s ease;
    }
    .ec-control:hover { border-color: rgba(168, 85, 247, 0.42); }
    .ec-control.is-invalid { border-color: var(--danger); box-shadow: 0 0 0 2px rgba(244, 63, 94, 0.25); }

    .ec-status-toggle-box {
        min-height: 40px; padding: 6px 14px; border-radius: var(--radius-md);
        background: rgba(0, 0, 0, 0.25); border: 1px solid var(--glass-border-light);
        display: flex; align-items: center; gap: 10px; cursor: pointer; position: relative;
    }
    .ec-status-toggle-box input { opacity: 0; width: 0; height: 0; position: absolute; }
    .ec-switch-track {
        width: 42px; height: 22px; border-radius: var(--radius-lg); background: rgba(255, 255, 255, 0.16);
        position: relative; flex-shrink: 0; transition: background-color 0.18s ease;
    }
    .ec-switch-track::before {
        content: ''; position: absolute; width: 16px; height: 16px; left: 3px; top: 3px;
        border-radius: 50%; background: #ffffff; transition: transform 0.18s ease;
    }
    .ec-status-toggle-box input:checked + .ec-switch-track { background: var(--success); }
    .ec-status-toggle-box input:checked + .ec-switch-track::before { transform: translateX(20px); }
    .ec-status-toggle-box input:focus-visible + .ec-switch-track {
        outline: 2px solid var(--primary-soft-text-hover);
        outline-offset: 2px;
    }
    .ec-switch-text { font-size: 14px; color: var(--text-muted); font-weight: 600; }
    .ec-switch-text.active { color: var(--success-soft-text); }

    /* Effective Gate Banner */
    .ec-effective-banner {
        margin-top: 18px; padding: 14px 16px; border-radius: var(--radius-md);
        background: rgba(99, 102, 241, 0.11); border: 1px solid rgba(129, 140, 248, 0.34);
        display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
        font-size: 14px; color: var(--text-main);
    }
    .ec-effective-banner.warn {
        background: rgba(245, 158, 11, 0.11); border-color: rgba(245, 158, 11, 0.38);
    }
    .eff-main { flex: 1; min-width: 240px; line-height: 1.5; }
    .eff-warn-note { margin-top: 4px; font-size: 12px; color: var(--warning-soft-text); font-weight: 500; }
    .eff-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

    /* Collapsible Categories & 2-Row Rule Cards */
    .ec-cat-header {
        display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
    }
    .ec-cat-collapse-btn {
        background: none; border: none; padding: 4px 0; color: inherit; font: inherit;
        display: inline-flex; align-items: center; gap: 10px; flex-wrap: wrap; cursor: pointer; text-align: left;
    }
    .ec-cat-collapse-btn.full { width: 100%; }
    .ec-cat-collapse-btn h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--text-main); }
    .ec-chevron { color: var(--text-muted); transition: transform 0.18s ease; flex-shrink: 0; }
    .ec-chevron.collapsed { transform: rotate(-90deg); }

    .ec-count-badge {
        font-size: 12px; font-weight: 700; padding: 2px 10px; border-radius: var(--radius-lg);
        background: rgba(99, 102, 241, 0.18); color: var(--primary-soft-text-hover);
        font-variant-numeric: tabular-nums;
    }
    .ec-cond-hint {
        font-size: 12px; padding: 2px 10px; border-radius: var(--radius-lg);
        background: rgba(245, 158, 11, 0.14); color: var(--warning-soft-text);
    }

    .ec-rule-cards-list {
        display: flex; flex-direction: column; gap: 12px; margin-top: 14px;
    }
    .ec-rule-item-card {
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        transition: border-color 0.16s ease;
    }
    .ec-rule-item-card:hover { border-color: rgba(129, 140, 248, 0.36); }
    .ec-rule-item-card.is-invalid { border-color: var(--danger); }

    .rule-row-top {
        display: flex; align-items: flex-start; gap: 10px;
    }
    .rule-code-in {
        width: 72px; flex-shrink: 0; text-align: center;
        font-family: var(--font-en); font-weight: 700; color: var(--accent-soft-text);
        padding: 8px 6px;
    }
    .rule-question-in {
        flex: 1; min-width: 0; resize: vertical; line-height: 1.5;
    }
    .rule-row-actions {
        display: flex; align-items: center; gap: 6px; flex-shrink: 0;
    }

    .rule-row-bottom {
        display: flex; align-items: center; flex-wrap: wrap; gap: 12px;
        padding-left: 82px;
    }
    .rule-meta-field { display: inline-flex; align-items: center; gap: 8px; }
    .rule-meta-field.kpi { flex: 1; min-width: 220px; }
    .meta-mini-lbl { font-size: 12px; font-weight: 600; color: var(--text-dim); white-space: nowrap; }
    .rule-metric-in { min-height: 34px; padding: 5px 10px; font-size: 12px; border-radius: var(--radius-sm); color: var(--primary-soft-text-hover); }

    .rule-mand-pill {
        min-height: 34px; padding: 0 12px; border-radius: var(--radius-sm);
        background: rgba(255, 255, 255, 0.04); border: 1px solid var(--glass-border-light);
        color: var(--text-muted); font-size: 12px; font-weight: 600;
        display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
    }
    .rule-mand-pill.active {
        background: rgba(99, 102, 241, 0.16); border-color: rgba(129, 140, 248, 0.42); color: var(--primary-soft-text-hover);
    }
    .rule-mand-pill input { width: 16px; height: 16px; accent-color: var(--primary); cursor: pointer; margin: 0; }

    .ec-empty-cat, .ec-empty-side, .ec-loading-box {
        padding: 22px 16px; text-align: center; color: var(--text-dim); font-size: 14px;
    }
    .ec-empty-side p { margin: 0 0 10px; }

    /* Rules Panel */
    .ec-rules-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px; }
    .ec-rule-card {
        background: var(--surface-card); border: 1px solid var(--glass-border);
        border-radius: var(--radius-md); padding: 14px;
    }
    .ec-rule-card p { margin: 8px 0 0; font-size: 14px; color: var(--text-muted); line-height: 1.5; }
    .verdict-pill {
        display: inline-block; font-size: 12px; font-weight: 700; font-family: var(--font-en);
        padding: 4px 10px; border-radius: var(--radius-lg);
    }
    .verdict-pill.pass { background: rgba(16, 185, 129, 0.16); color: var(--success-soft-text); border: 1px solid rgba(16, 185, 129, 0.35); }
    .verdict-pill.cond { background: rgba(245, 158, 11, 0.16); color: var(--warning-soft-text); border: 1px solid rgba(245, 158, 11, 0.35); }
    .verdict-pill.reject { background: rgba(244, 63, 94, 0.16); color: var(--danger-soft-text); border: 1px solid rgba(244, 63, 94, 0.35); }

    /* Modals (Opaque --bg2 per craft-floor) */
    .ec-modal-backdrop {
        position: fixed; inset: 0; background: rgba(5, 5, 10, 0.78);
        backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
        display: flex; align-items: center; justify-content: center;
        z-index: var(--z-modal, 10000); padding: 16px;
    }
    .ec-modal-box {
        width: 100%; max-width: 520px; max-height: calc(100dvh - 32px);
        background: var(--bg2); border: 1px solid rgba(168, 85, 247, 0.28);
        border-radius: var(--radius-lg); box-shadow: 0 28px 72px rgba(0, 0, 0, 0.85);
        display: flex; flex-direction: column; overflow: hidden; outline: none;
        font-family: var(--font-th); color: var(--text-main);
    }
    .ec-modal-box.large { max-width: 720px; }
    .ec-modal-box.confirm { max-width: 440px; padding: 26px 28px; text-align: center; }

    .ec-modal-head {
        display: flex; justify-content: space-between; align-items: flex-start; gap: 12px;
        padding: 18px 22px 14px; background: var(--bg); border-bottom: 1px solid var(--glass-border);
    }
    .ec-modal-head h2 { margin: 0; font-size: 18px; font-weight: 700; }
    .ec-modal-head p { margin: 4px 0 0; font-size: 14px; color: var(--text-muted); }
    .ec-modal-body {
        flex: 1; overflow-y: auto; padding: 18px 22px;
        display: flex; flex-direction: column; gap: 14px;
        scrollbar-width: thin; scrollbar-color: rgba(129, 140, 248, 0.3) transparent;
    }
    .ec-modal-foot {
        display: flex; justify-content: flex-end; gap: 10px;
        padding: 14px 22px; background: var(--bg); border-top: 1px solid var(--glass-border);
    }
    .ec-modal-foot.center { justify-content: center; background: transparent; border-top: none; padding: 8px 0 0; }

    .ec-radio-row { display: flex; gap: 8px; flex-wrap: wrap; }
    .ec-radio-opt {
        flex: 1; min-width: 200px; padding: 10px 12px; border-radius: var(--radius-md);
        background: var(--surface-card); border: 1px solid var(--glass-border);
        font-size: 14px; display: flex; align-items: center; gap: 8px; cursor: pointer;
    }
    .ec-radio-opt.active { background: rgba(99, 102, 241, 0.14); border-color: var(--primary); }
    .ec-radio-opt input { accent-color: var(--primary); }

    /* Sandbox Results */
    .sb-result-card {
        background: var(--bg); border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-md); padding: 14px;
    }
    .sb-result-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
    .sb-score { font-family: var(--font-en); font-size: 16px; }
    .sb-counts { font-size: 12px; color: var(--text-dim); }
    .sb-summary { font-size: 14px; color: var(--text-muted); margin: 0 0 10px; }
    .sb-items-list { display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto; }
    .sb-item-row {
        display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px;
        background: var(--surface-card); border: 1px solid var(--glass-border); border-radius: var(--radius-sm);
        font-size: 14px;
    }
    .sb-item-row.fail { border-color: rgba(244, 63, 94, 0.42); }
    .sb-code { font-family: var(--font-en); font-weight: 700; color: var(--accent-soft-text); min-width: 36px; }
    .sb-st { font-family: var(--font-en); font-weight: 700; font-size: 12px; padding: 2px 8px; border-radius: var(--radius-sm); }
    .sb-st.pass { background: rgba(16, 185, 129, 0.16); color: var(--success-soft-text); }
    .sb-st.fail { background: rgba(244, 63, 94, 0.16); color: var(--danger-soft-text); }
    .sb-st.na { background: rgba(255, 255, 255, 0.08); color: var(--text-dim); }
    .sb-q { font-weight: 600; color: var(--text-main); margin-bottom: 2px; }
    .sb-rem { font-size: 12px; color: var(--text-muted); }

    .help-section h3 { margin: 0 0 6px; font-size: 16px; color: var(--accent-soft-text); }
    .help-section p, .help-section li { font-size: 14px; color: var(--text-muted); line-height: 1.55; }
    .help-section ul { margin: 6px 0 0; padding-left: 18px; }

    .ec-confirm-title { margin: 0 0 10px; font-size: 18px; color: var(--danger-soft-text); }
    .ec-confirm-title.warn { color: var(--warning-soft-text); }
    .ec-confirm-msg { margin: 0 0 14px; font-size: 14px; color: var(--text-muted); line-height: 1.55; }

    /* Unified Keyboard Focus Rings (WCAG 2.2) */
    .ec-container button:focus-visible,
    .ec-modal-box button:focus-visible,
    .ec-container input:focus-visible,
    .ec-container textarea:focus-visible,
    .ec-modal-box input:focus-visible,
    .ec-modal-box textarea:focus-visible {
        outline: 2px solid var(--primary-soft-text-hover);
        outline-offset: 2px;
    }

    @media (max-width: 1180px) {
        .ec-layout { grid-template-columns: 1fr; }
        .ec-sidebar { position: static; }
        .ec-template-list { max-height: 260px; }
        .ec-rules-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
        .ec-container { padding: 14px; }
        .ec-form-grid { grid-template-columns: 1fr; }
        .rule-row-top { flex-wrap: wrap; }
        .rule-row-bottom { padding-left: 0; }
    }
    @media (prefers-reduced-motion: reduce) {
        .mini-slider, .mini-slider::before, .ec-switch-track, .ec-switch-track::before, .ec-chevron { transition: none; }
    }
</style>
