<script>
    import { onMount, onDestroy, tick } from 'svelte';
    import { toast } from './toastStore.js';
    import { authUser, updateAuthProfile } from './authStore.js';
    import CustomSelect from './CustomSelect.svelte';
    import MemberActivityDrawer from './MemberActivityDrawer.svelte';

    let users = [];
    let allProjects = [];
    let isLoading = true;
    let isSaving = false;
    let togglingUserIds = new Set();
    let failedAvatarIds = new Set();
    let previewAvatarError = false;
    let searchQuery = '';
    let roleFilter = 'all';
    let statusFilter = 'all'; // 'all' | 'active' | 'inactive'
    let departmentFilter = 'all';
    let projectFilter = 'all';
    let sortKey = 'user_id'; // 'user_id' | 'display_name' | 'role' | 'last_login_at' | 'login_count'
    let sortDir = 'asc'; // 'asc' | 'desc'
    let showPassword = false;
    let showSocialFields = false;
    let roleChangedNotice = '';
    let confirmDiscardOpen = false;
    let initialFormSnapshot = '';
    let formErrors = {};
    let lastTriggerEl = null;

    // Post-create Credential Handoff state
    let handoffModal = {
        show: false,
        display_name: '',
        username: '',
        email: '',
        password: '',
        role: 'user',
        menuCount: 0,
        projectSummary: ''
    };

    const USER_MENUS = [
        { id: 'qa_consult', label: 'QA Consult', desc: 'ให้คำปรึกษาและวิเคราะห์เอกสาร QA' },
        { id: 'qa_doc_creation', label: 'QA Document Creation', desc: 'สร้างเอกสาร QA & Test Scenarios' },
        { id: 'qa_analysis_diagram', label: 'QA Analysis Diagram', desc: 'ผัง Flow, Sitemap, Wireframe & Matrix' },
        { id: 'qa_board', label: 'QA Board Card', desc: 'จัดการและตรวจสอบการ์ด Trello / GitHub' },
        { id: 'qa_automate', label: 'QA Test Automation', desc: 'สร้าง & รันสคริปต์ Automated Test' },
        { id: 'qa_performance', label: 'QA Performance', desc: 'ทดสอบประสิทธิภาพ & k6 Script' },
        { id: 'qa_security', label: 'QA Security', desc: 'ตรวจสอบความปลอดภัย & OWASP' },
        { id: 'qa_research', label: 'QA Research', desc: 'ค้นคว้าและสรุปข้อมูล QA' },
        { id: 'master_agent', label: 'Master Agent', desc: 'AI ศูนย์กลางประสานงาน' },
        { id: 'workflow_builder', label: 'AI Workflow Builder', desc: 'สร้าง Flow การทำงานอัตโนมัติ' }
    ];

    const ADMIN_MENUS = [
        { id: 'ocr', label: 'Scan OCR', desc: 'สแกนและตรวจสอบคำผิดเอกสาร' },
        { id: 'project_management', label: 'Project Management', desc: 'จัดการรายชื่อโครงการในระบบ' },
        { id: 'kb', label: 'Knowledge Base', desc: 'คลังความรู้ RAG เอกสาร' },
        { id: 'skills', label: 'AI Skills', desc: 'จัดการทักษะและ Prompt AI' },
        { id: 'qa_member', label: 'QA Member Management', desc: 'จัดการสมาชิกและสิทธิ์ระบบ' },
        { id: 'exit_criteria', label: 'Exit Criteria', desc: 'กำหนดเกณฑ์คุณภาพงาน' },
        { id: 'api_collection', label: 'API Collections', desc: 'จัดการคลัง API Endpoint' },
        { id: 'api_usage', label: 'Token Usage', desc: 'สรุปการใช้งาน Token & Credit' }
    ];

    const ALL_MENU_LABEL_MAP = Object.fromEntries(
        [...USER_MENUS, ...ADMIN_MENUS].map((m) => [m.id, m.label])
    );

    const QA_PERMISSION_PRESETS = [
        {
            id: 'manual_qa',
            label: 'Manual QA',
            roles: ['user', 'admin'],
            menus: ['qa_consult', 'qa_doc_creation', 'qa_analysis_diagram', 'qa_board', 'qa_research']
        },
        {
            id: 'automation_qa',
            label: 'Automation QA',
            roles: ['user', 'admin'],
            menus: ['qa_consult', 'qa_board', 'qa_automate', 'qa_performance', 'workflow_builder']
        },
        {
            id: 'sec_perf',
            label: 'Security & Perf',
            roles: ['user', 'admin'],
            menus: ['qa_consult', 'qa_performance', 'qa_security', 'qa_research']
        },
        {
            id: 'qa_lead',
            label: 'QA Lead (Full QA)',
            roles: ['user', 'admin'],
            menus: USER_MENUS.map((m) => m.id)
        },
        {
            id: 'admin_full',
            label: 'Admin + Full QA',
            roles: ['admin'],
            menus: [...ADMIN_MENUS.map((m) => m.id), ...USER_MENUS.map((m) => m.id)]
        }
    ];

    const roleFilterOptions = [
        { value: 'all', label: 'ทุกระดับสิทธิ์ (All)' },
        { value: 'admin', label: 'ผู้ดูแลระบบ (Admin)' },
        { value: 'user', label: 'ผู้ใช้ทั่วไป (User)' }
    ];

    const statusFilterOptions = [
        { value: 'all', label: 'ทุกสถานะ (All)' },
        { value: 'active', label: 'เปิดใช้งาน (Active)' },
        { value: 'inactive', label: 'ปิดใช้งาน (Inactive)' }
    ];

    const roleFormOptions = [
        { value: 'user', label: 'ผู้ใช้ทั่วไป (Standard User)' },
        { value: 'admin', label: 'ผู้ดูแลระบบ (Admin)' }
    ];

    let avatarFile = null;
    let avatarPreview = null;
    let avatarBlobUrl = null;
    let isDragOverAvatar = false;

    // Modal state
    let showModal = false;
    let isEditMode = false;
    let activeModalTab = 'general'; // 'general' | 'permissions' | 'security'
    let modalProjectSearch = '';
    let editDialogEl = null;
    let confirmDialogEl = null;
    let handoffDialogEl = null;

    // Security tab (API Tokens & Session Revocation) state
    let memberTokens = [];
    let isLoadingTokens = false;
    let isCreatingToken = false;
    let isRevokingSessions = false;
    let revokingTokenIds = new Set();
    let newTokenName = '';
    let newTokenScopes = 'extension,mcp';
    let newlyCreatedToken = '';

    const tokenScopeOptions = [
        { value: 'extension,mcp', label: 'Chrome Extension + MCP Server' },
        { value: 'extension', label: 'Chrome Extension เท่านั้น' },
        { value: 'mcp', label: 'MCP Server เท่านั้น' }
    ];

    // Activity & Audit Drawer state
    let activityDrawerOpen = false;
    let activityDrawerUser = null;

    // Group 3: Bulk Selection, Custom Templates & Export CSV
    let customTemplates = [];
    let showSaveTemplateInput = false;
    let newTemplateName = '';
    let isSavingTemplate = false;
    let selectedUserIds = new Set();
    let bulkModal = {
        show: false,
        mode: 'projects', // 'projects' | 'preset'
        projectOp: 'add_projects', // 'add_projects' | 'remove_projects' | 'set_projects_all'
        selectedProjects: [],
        selectedPresetId: '',
        loading: false
    };

    function openActivityDrawer(user) {
        activityDrawerUser = user;
        activityDrawerOpen = true;
    }

    function formatCompactTokens(n) {
        const val = Number(n || 0);
        if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
        if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
        return String(val);
    }

    let formData = {
        user_id: null,
        username: '',
        email: '',
        display_name: '',
        password: '',
        role: 'user',
        avatar_path: null,
        phone: '',
        department: '',
        github_url: '',
        linkedin_url: '',
        line_id: '',
        allowed_menus: USER_MENUS.map(m => m.id),
        allowed_projects: ['all'],
        must_change_password: true,
        monthly_token_quota: 0,
        trello_username: '',
        github_username: ''
    };

    let confirmModal = {
        show: false,
        title: '',
        message: '',
        confirmText: 'ยืนยัน',
        variant: 'danger', // 'danger' | 'primary'
        loading: false,
        action: null
    };

    function getPasswordStrength(pw) {
        if (!pw) return null;
        let score = 0;
        if (pw.length >= 8) score++;
        if (pw.length >= 12) score++;
        if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
        if (/\d/.test(pw)) score++;
        if (/[^A-Za-z0-9]/.test(pw)) score++;
        if (score <= 2) return { level: 'weak', label: 'ความปลอดภัยต่ำ (ควรมีตัวพิมพ์ใหญ่ ตัวเลข และสัญลักษณ์)', percent: 33 };
        if (score <= 3) return { level: 'medium', label: 'ความปลอดภัยปานกลาง', percent: 66 };
        return { level: 'strong', label: 'ความปลอดภัยสูง', percent: 100 };
    }

    function isPresetActive(preset) {
        if (!preset || !Array.isArray(formData.allowed_menus)) return false;
        const current = new Set(formData.allowed_menus);
        if (formData.role === 'admin' && preset.id !== 'admin_full') {
            const qaCurrent = formData.allowed_menus.filter(id => USER_MENUS.some(m => m.id === id));
            return qaCurrent.length === preset.menus.length && preset.menus.every(id => current.has(id));
        }
        return current.size === preset.menus.length && preset.menus.every(id => current.has(id));
    }

    $: passwordStrength = getPasswordStrength(formData.password);

    function revokeAvatarBlob() {
        if (avatarBlobUrl) {
            URL.revokeObjectURL(avatarBlobUrl);
            avatarBlobUrl = null;
        }
    }

    onDestroy(() => {
        revokeAvatarBlob();
    });

    function getAuthHeaders(customHeaders = {}) {
        const token = localStorage.getItem('jwt_token');
        return {
            ...customHeaders,
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
    }

    function isSelfUser(user) {
        return Boolean(user && $authUser && String(user.username || '').toLowerCase() === String($authUser).toLowerCase());
    }

    function isLastActiveAdmin(user) {
        if (!user || user.role !== 'admin' || !user.is_active) return false;
        const activeAdmins = users.filter(u => u.role === 'admin' && u.is_active);
        return activeAdmins.length <= 1;
    }

    function generateStrongPassword(length = 12) {
        const upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
        const lower = 'abcdefghijkmnopqrstuvwxyz';
        const digits = '23456789';
        const symbols = '@#$%&*!';
        const all = upper + lower + digits + symbols;
        const pick = (pool) => pool[Math.floor(Math.random() * pool.length)];
        const chars = [pick(upper), pick(lower), pick(digits), pick(symbols)];
        for (let i = chars.length; i < length; i++) {
            chars.push(pick(all));
        }
        return chars.sort(() => Math.random() - 0.5).join('');
    }

    async function copyText(text, successMsg = 'คัดลอกไปยังคลิปบอร์ดแล้ว') {
        if (!text) return;
        try {
            await navigator.clipboard.writeText(text);
            toast(successMsg, 'success');
        } catch (e) {
            toast('ไม่สามารถคัดลอกอัตโนมัติได้ กรุณาคัดลอกด้วยตนเอง', 'warning');
        }
    }

    function getMenuTooltip(allowedMenus) {
        if (!Array.isArray(allowedMenus) || allowedMenus.length === 0) return 'ไม่ได้กำหนดสิทธิ์เมนู';
        return 'เมนูที่เข้าถึงได้: ' + allowedMenus.map(id => ALL_MENU_LABEL_MAP[id] || id).join(', ');
    }

    function getProjectTooltip(allowedProjects) {
        if (!Array.isArray(allowedProjects) || allowedProjects.includes('all')) {
            return 'เข้าถึงได้ทุกโครงการในระบบ';
        }
        if (allowedProjects.length === 0) return 'ไม่ได้กำหนดสิทธิ์โครงการ';
        const names = allowedProjects.map((pid) => {
            const key = String(pid).trim().toLowerCase();
            const found = allProjects.find(
                (p) =>
                    String(p.id || p.project_id || '').trim().toLowerCase() === key ||
                    String(p.project_code || '').trim().toLowerCase() === key
            );
            return found ? (found.name || found.project_name || found.project_code) : pid;
        });
        return 'โครงการที่เข้าถึงได้: ' + names.join(', ');
    }

    function serializeForm() {
        return JSON.stringify({
            ...formData,
            hasNewAvatar: Boolean(avatarFile)
        });
    }

    $: isFormDirty = showModal && initialFormSnapshot !== '' && serializeForm() !== initialFormSnapshot;

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

    onMount(async () => {
        await Promise.all([fetchUsers(), fetchProjects(), fetchCustomTemplates()]);
    });

    async function fetchCustomTemplates() {
        try {
            const res = await fetch('/api/permission-templates', { headers: getAuthHeaders() });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                customTemplates = data.templates || [];
            }
        } catch (_) {}
    }

    async function handleSaveCustomTemplate() {
        const cleanName = newTemplateName.trim();
        if (!cleanName || isSavingTemplate) {
            if (!cleanName) toast('กรุณาระบุชื่อ Template', 'warning');
            return;
        }
        isSavingTemplate = true;
        try {
            const res = await fetch('/api/permission-templates', {
                method: 'POST',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    name: cleanName,
                    target_role: formData.role,
                    allowed_menus: formData.allowed_menus,
                    allowed_projects: formData.allowed_projects
                })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                await fetchCustomTemplates();
                newTemplateName = '';
                showSaveTemplateInput = false;
                toast(`บันทึก Template "${cleanName}" เรียบร้อยแล้ว`, 'success');
            } else {
                toast(data.error || 'ไม่สามารถบันทึก Template ได้', 'error');
            }
        } catch (_) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            isSavingTemplate = false;
        }
    }

    async function handleDeleteCustomTemplate(tpl) {
        try {
            const res = await fetch(`/api/permission-templates/${tpl.template_id}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            if (res.ok) {
                customTemplates = customTemplates.filter((t) => t.template_id !== tpl.template_id);
                toast(`ลบ Template "${tpl.name}" แล้ว`, 'info');
            } else {
                toast('ไม่สามารถลบ Template ได้', 'error');
            }
        } catch (_) {
            toast('เกิดข้อผิดพลาดในการลบ Template', 'error');
        }
    }

    function applyCustomTemplate(tpl) {
        if (!tpl) return;
        if (formData.role === 'admin' && tpl.target_role !== 'admin') {
            const adminIds = formData.allowed_menus.filter((id) => ADMIN_MENUS.some((m) => m.id === id));
            const baseAdmin = adminIds.length > 0 ? adminIds : ADMIN_MENUS.map((m) => m.id);
            formData.allowed_menus = Array.from(new Set([...baseAdmin, ...(tpl.allowed_menus || [])]));
        } else {
            formData.allowed_menus = [...(tpl.allowed_menus || [])];
        }
        if (Array.isArray(tpl.allowed_projects) && tpl.allowed_projects.length > 0) {
            formData.allowed_projects = [...tpl.allowed_projects];
        }
        toast(`ใช้ Template "${tpl.name}" แล้ว`, 'info');
    }

    function toggleSelectUser(userId) {
        const next = new Set(selectedUserIds);
        if (next.has(userId)) next.delete(userId);
        else next.add(userId);
        selectedUserIds = next;
    }

    function toggleSelectAllVisible() {
        const visibleIds = filteredUsers.map((u) => u.user_id);
        const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedUserIds.has(id));
        if (allSelected) {
            const next = new Set(selectedUserIds);
            visibleIds.forEach((id) => next.delete(id));
            selectedUserIds = next;
        } else {
            selectedUserIds = new Set([...selectedUserIds, ...visibleIds]);
        }
    }

    function clearSelection() {
        selectedUserIds = new Set();
    }

    function openBulkModal(mode) {
        if (selectedUserIds.size === 0) return;
        bulkModal = {
            show: true,
            mode,
            projectOp: 'add_projects',
            selectedProjects: [],
            selectedPresetId: QA_PERMISSION_PRESETS[0].id,
            loading: false
        };
    }

    function toggleBulkProject(projKey) {
        if (bulkModal.selectedProjects.includes(projKey)) {
            bulkModal.selectedProjects = bulkModal.selectedProjects.filter((k) => k !== projKey);
        } else {
            bulkModal.selectedProjects = [...bulkModal.selectedProjects, projKey];
        }
    }

    async function executeBulkModalAction() {
        if (bulkModal.loading || selectedUserIds.size === 0) return;
        const user_ids = Array.from(selectedUserIds);
        let body = { user_ids };

        if (bulkModal.mode === 'projects') {
            body.action = bulkModal.projectOp;
            if (bulkModal.projectOp !== 'set_projects_all') {
                if (bulkModal.selectedProjects.length === 0) {
                    toast('กรุณาเลือกอย่างน้อย 1 โครงการ', 'warning');
                    return;
                }
                body.projects = bulkModal.selectedProjects;
            }
        } else {
            body.action = 'apply_menus';
            const builtIn = QA_PERMISSION_PRESETS.find((p) => p.id === bulkModal.selectedPresetId);
            const custom = customTemplates.find((t) => `tpl_${t.template_id}` === bulkModal.selectedPresetId);
            if (builtIn) {
                body.allowed_menus = builtIn.menus;
                body.template_name = builtIn.label;
            } else if (custom) {
                body.allowed_menus = custom.allowed_menus;
                body.template_name = custom.name;
            } else {
                toast('กรุณาเลือกชุดสิทธิ์ที่ต้องการใช้งาน', 'warning');
                return;
            }
        }

        bulkModal.loading = true;
        try {
            const res = await fetch('/api/users/bulk', {
                method: 'POST',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(body)
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                const skipMsg = data.skipped?.length ? ` (ข้าม ${data.skipped.length} รายการ)` : '';
                toast(`อัปเดตสำเร็จ ${data.updated_count} สมาชิก${skipMsg}`, 'success');
                bulkModal.show = false;
                clearSelection();
                await fetchUsers();
            } else {
                toast(data.error || 'ดำเนินการแบบกลุ่มไม่สำเร็จ', 'error');
            }
        } catch (_) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            bulkModal.loading = false;
        }
    }

    async function handleBulkStatus(action) {
        if (selectedUserIds.size === 0) return;
        const isDeactivate = action === 'deactivate';
        lastTriggerEl = document.activeElement;
        confirmModal = {
            show: true,
            title: isDeactivate ? `ยืนยันปิดใช้งาน ${selectedUserIds.size} บัญชี` : `ยืนยันเปิดใช้งาน ${selectedUserIds.size} บัญชี`,
            message: isDeactivate
                ? `ต้องการปิดใช้งานสมาชิกที่เลือกจำนวน ${selectedUserIds.size} บัญชีใช่หรือไม่? (ระบบจะข้ามบัญชีของคุณและ Admin คนสุดท้ายโดยอัตโนมัติ)`
                : `ต้องการเปิดใช้งานสมาชิกที่เลือกจำนวน ${selectedUserIds.size} บัญชีใช่หรือไม่?`,
            confirmText: isDeactivate ? 'ปิดใช้งานที่เลือก' : 'เปิดใช้งานที่เลือก',
            variant: isDeactivate ? 'danger' : 'primary',
            loading: false,
            action: async () => {
                confirmModal.loading = true;
                try {
                    const res = await fetch('/api/users/bulk', {
                        method: 'POST',
                        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                        body: JSON.stringify({ user_ids: Array.from(selectedUserIds), action })
                    });
                    const data = await res.json().catch(() => ({}));
                    if (res.ok && data.success) {
                        const skipMsg = data.skipped?.length ? ` (ข้าม ${data.skipped.length} รายการ)` : '';
                        toast(`อัปเดตสถานะสำเร็จ ${data.updated_count} สมาชิก${skipMsg}`, 'success');
                        clearSelection();
                        closeConfirmModal();
                        await fetchUsers();
                    } else {
                        toast(data.error || 'อัปเดตสถานะแบบกลุ่มไม่สำเร็จ', 'error');
                    }
                } catch (_) {
                    toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
                } finally {
                    confirmModal.loading = false;
                }
            }
        };
        await tick();
        confirmDialogEl?.focus();
    }

    function exportMembersCsv() {
        const targetList = selectedUserIds.size > 0
            ? users.filter((u) => selectedUserIds.has(u.user_id))
            : filteredUsers;
        if (targetList.length === 0) {
            toast('ไม่มีข้อมูลสมาชิกสำหรับส่งออก', 'warning');
            return;
        }
        const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
        const headers = [
            'Display Name', 'Username', 'Email', 'Department', 'Role', 'Status',
            'Menus Count', 'Allowed Menus', 'Allowed Projects',
            'Monthly Tokens Used', 'Monthly Token Quota', 'Last Login', 'Login Count'
        ];
        const lines = [headers.map(esc).join(',')];
        for (const u of targetList) {
            const menus = Array.isArray(u.allowed_menus) ? u.allowed_menus.map((id) => ALL_MENU_LABEL_MAP[id] || id).join('; ') : '';
            const projs = !u.allowed_projects || u.allowed_projects.includes('all')
                ? 'All Projects'
                : u.allowed_projects.join('; ');
            lines.push([
                u.display_name || '',
                u.username || '',
                u.email || '',
                u.department || '',
                (u.role || 'user').toUpperCase(),
                u.is_active ? 'Active' : 'Inactive',
                Array.isArray(u.allowed_menus) ? u.allowed_menus.length : 0,
                menus,
                projs,
                u.monthly_tokens_used || 0,
                u.monthly_token_quota > 0 ? u.monthly_token_quota : 'Unlimited',
                u.last_login_at ? formatDate(u.last_login_at) : '-',
                u.login_count || 0
            ].map(esc).join(','));
        }
        const blob = new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const dateStr = new Date().toISOString().slice(0, 10);
        a.href = url;
        a.download = `spectra-qa-members-${dateStr}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toast(`ส่งออกรายชื่อสมาชิก ${targetList.length} รายการเป็นไฟล์ CSV แล้ว`, 'success');
    }

    async function fetchUsers() {
        isLoading = true;
        try {
            const res = await fetch('/api/users', {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            if (res.ok && data.success) {
                users = data.users || [];
                failedAvatarIds = new Set();
            } else {
                toast(data.error || 'ไม่สามารถโหลดรายชื่อผู้ใช้งานได้', 'error');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเพื่อโหลดผู้ใช้งาน', 'error');
        } finally {
            isLoading = false;
        }
    }

    async function fetchProjects() {
        try {
            const res = await fetch('/api/projects', {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            if (res.ok && data.success) {
                allProjects = data.projects || [];
            } else {
                toast(data.error || 'ไม่สามารถโหลดรายชื่อโครงการได้', 'warning');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการโหลดรายชื่อโครงการ', 'warning');
        }
    }

    async function executeToggleStatus(user, newStatus) {
        if (togglingUserIds.has(user.user_id)) return;
        togglingUserIds = new Set([...togglingUserIds, user.user_id]);
        try {
            const res = await fetch(`/api/users/${user.user_id}`, {
                method: 'PUT',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ is_active: newStatus })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                user.is_active = newStatus;
                users = [...users];
                toast(`อัปเดตสถานะ ${user.username} เป็น ${newStatus ? 'เปิดใช้งาน' : 'ปิดใช้งาน'} แล้ว`, 'success');
                return true;
            } else {
                toast(data.error || 'อัปเดตสถานะไม่สำเร็จ', 'error');
                return false;
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
            return false;
        } finally {
            togglingUserIds.delete(user.user_id);
            togglingUserIds = new Set(togglingUserIds);
        }
    }

    async function handleToggleStatus(user, event) {
        if (isSelfUser(user)) {
            if (event?.target) event.target.checked = user.is_active;
            toast('ไม่สามารถปิดการใช้งานบัญชีตัวเองได้', 'warning');
            return;
        }
        if (user.is_active && isLastActiveAdmin(user)) {
            if (event?.target) event.target.checked = user.is_active;
            toast('ไม่สามารถปิดการใช้งานผู้ดูแลระบบ (Admin) คนสุดท้ายของระบบได้', 'warning');
            return;
        }
        const newStatus = !user.is_active;
        // Require confirmation before deactivating an active account
        if (!newStatus) {
            if (event?.target) event.target.checked = true;
            lastTriggerEl = document.activeElement;
            confirmModal = {
                show: true,
                title: 'ยืนยันการปิดใช้งานบัญชี',
                message: `ต้องการปิดการใช้งานบัญชี "${user.display_name || user.username}" (${user.username}) ใช่หรือไม่? ผู้ใช้นี้จะถูกบังคับออกจากระบบทันที`,
                confirmText: 'ปิดใช้งานบัญชี',
                variant: 'danger',
                loading: false,
                action: async () => {
                    confirmModal.loading = true;
                    const ok = await executeToggleStatus(user, false);
                    confirmModal.loading = false;
                    if (ok) closeConfirmModal();
                }
            };
            await tick();
            confirmDialogEl?.focus();
            return;
        }
        const ok = await executeToggleStatus(user, true);
        if (!ok && event?.target) {
            event.target.checked = user.is_active;
        }
    }

    async function handleToggleRole(user) {
        if (isSelfUser(user)) {
            toast('ไม่สามารถเปลี่ยนระดับสิทธิ์ของบัญชีตัวเองได้', 'warning');
            return;
        }
        if (user.role === 'admin' && isLastActiveAdmin(user)) {
            toast('ไม่สามารถลดสิทธิ์ผู้ดูแลระบบ (Admin) คนสุดท้ายของระบบได้', 'warning');
            return;
        }
        const newRole = user.role === 'admin' ? 'user' : 'admin';
        lastTriggerEl = document.activeElement;
        confirmModal = {
            show: true,
            title: 'ยืนยันการเปลี่ยนระดับสิทธิ์',
            message: `คุณต้องการเปลี่ยนสิทธิ์ของ "${user.display_name || user.username}" เป็น ${newRole.toUpperCase()} ใช่หรือไม่? ระบบจะรีเซ็ตเมนูเริ่มต้นตามสิทธิ์ใหม่และบังคับเข้าสู่ระบบใหม่`,
            confirmText: `เปลี่ยนเป็น ${newRole.toUpperCase()}`,
            variant: 'primary',
            loading: false,
            action: async () => {
                confirmModal.loading = true;
                try {
                    const defaultMenus = (newRole === 'admin' ? ADMIN_MENUS : USER_MENUS).map(m => m.id);
                    const res = await fetch(`/api/users/${user.user_id}`, {
                        method: 'PUT',
                        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                        body: JSON.stringify({
                            role: newRole,
                            allowed_menus: defaultMenus
                        })
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                        user.role = newRole;
                        user.allowed_menus = defaultMenus;
                        users = [...users];
                        toast(`เปลี่ยนสิทธิ์ของ ${user.username} เป็น ${newRole.toUpperCase()} แล้ว`, 'success');
                        closeConfirmModal();
                    } else {
                        toast(data.error || 'เปลี่ยนสิทธิ์ไม่สำเร็จ', 'error');
                    }
                } catch (err) {
                    toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
                } finally {
                    confirmModal.loading = false;
                }
            }
        };
        await tick();
        confirmDialogEl?.focus();
    }

    async function handleForceLogout(user) {
        if (!user || isSelfUser(user)) {
            toast('ไม่สามารถบังคับออกจากระบบบัญชีตัวเองจากหน้านี้ได้', 'warning');
            return;
        }
        lastTriggerEl = document.activeElement;
        confirmModal = {
            show: true,
            title: 'ยืนยันการบังคับออกจากระบบทุกอุปกรณ์',
            message: `ต้องการยกเลิก Session ปัจจุบันทั้งหมดของ "${user.display_name || user.username}" (${user.username}) ใช่หรือไม่? บัญชีจะยังคงเปิดใช้งานอยู่ แต่ผู้ใช้จะต้องเข้าสู่ระบบใหม่`,
            confirmText: 'บังคับออกจากระบบ',
            variant: 'danger',
            loading: false,
            action: async () => {
                confirmModal.loading = true;
                try {
                    const res = await fetch(`/api/users/${user.user_id}/revoke-sessions`, {
                        method: 'POST',
                        headers: getAuthHeaders()
                    });
                    const data = await res.json().catch(() => ({}));
                    if (res.ok && data.success) {
                        toast(data.message || `บังคับออกจากระบบของ ${user.username} เรียบร้อยแล้ว`, 'success');
                        closeConfirmModal();
                    } else {
                        toast(data.error || 'ไม่สามารถยกเลิก Session ได้', 'error');
                    }
                } catch (err) {
                    toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
                } finally {
                    confirmModal.loading = false;
                }
            }
        };
        await tick();
        confirmDialogEl?.focus();
    }

    async function fetchMemberTokens(userId) {
        if (!userId) return;
        isLoadingTokens = true;
        try {
            const res = await fetch(`/api/users/${userId}/tokens`, {
                headers: getAuthHeaders()
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                memberTokens = data.tokens || [];
            } else {
                toast(data.error || 'ไม่สามารถโหลดรายการ API Token ได้', 'warning');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการโหลดรายการ API Token', 'warning');
        } finally {
            isLoadingTokens = false;
        }
    }

    async function handleCreateMemberToken() {
        if (!formData.user_id || isCreatingToken) return;
        const cleanName = newTokenName.trim();
        if (!cleanName) {
            toast('กรุณาระบุชื่อ API Token ก่อนสร้าง', 'warning');
            return;
        }
        isCreatingToken = true;
        newlyCreatedToken = '';
        try {
            const res = await fetch(`/api/users/${formData.user_id}/tokens`, {
                method: 'POST',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ name: cleanName, scopes: newTokenScopes })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                newlyCreatedToken = data.token || '';
                newTokenName = '';
                if (data.token_info) {
                    memberTokens = [data.token_info, ...memberTokens];
                } else {
                    await fetchMemberTokens(formData.user_id);
                }
                users = users.map((u) =>
                    u.user_id === formData.user_id
                        ? { ...u, active_token_count: (u.active_token_count || 0) + 1 }
                        : u
                );
                toast('สร้าง Personal API Token เรียบร้อยแล้ว กรุณาคัดลอกเก็บไว้ทันที', 'success');
            } else {
                toast(data.error || 'ไม่สามารถสร้าง API Token ได้', 'error');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            isCreatingToken = false;
        }
    }

    async function handleRevokeMemberToken(tokenId) {
        if (!formData.user_id || revokingTokenIds.has(tokenId)) return;
        revokingTokenIds = new Set([...revokingTokenIds, tokenId]);
        try {
            const res = await fetch(`/api/users/${formData.user_id}/tokens/${tokenId}`, {
                method: 'DELETE',
                headers: getAuthHeaders()
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                memberTokens = memberTokens.map((t) =>
                    t.token_id === tokenId ? { ...t, is_active: false, revoked_at: new Date().toISOString() } : t
                );
                users = users.map((u) =>
                    u.user_id === formData.user_id
                        ? { ...u, active_token_count: Math.max(0, (u.active_token_count || 1) - 1) }
                        : u
                );
                toast('ยกเลิก API Token เรียบร้อยแล้ว', 'success');
            } else {
                toast(data.error || 'ไม่สามารถยกเลิก API Token ได้', 'error');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            revokingTokenIds.delete(tokenId);
            revokingTokenIds = new Set(revokingTokenIds);
        }
    }

    async function handleModalForceLogout() {
        if (!formData.user_id || isRevokingSessions || isSelfUser(formData)) return;
        isRevokingSessions = true;
        try {
            const res = await fetch(`/api/users/${formData.user_id}/revoke-sessions`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                toast(data.message || 'บังคับออกจากระบบทุกอุปกรณ์เรียบร้อยแล้ว', 'success');
            } else {
                toast(data.error || 'ไม่สามารถยกเลิก Session ได้', 'error');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            isRevokingSessions = false;
        }
    }

    async function handleDelete(user) {
        if (isSelfUser(user)) {
            toast('ไม่สามารถลบบัญชีของตัวเองได้', 'warning');
            return;
        }
        if (isLastActiveAdmin(user)) {
            toast('ไม่สามารถลบผู้ดูแลระบบ (Admin) คนสุดท้ายของระบบได้', 'warning');
            return;
        }
        lastTriggerEl = document.activeElement;
        confirmModal = {
            show: true,
            title: 'ยืนยันการลบผู้ใช้งานถาวร',
            message: `คุณต้องการลบผู้ใช้งาน "${user.display_name || user.username}" (${user.username}) ออกจากระบบอย่างถาวรใช่หรือไม่? การกระทำนี้ไม่สามารถย้อนกลับได้`,
            confirmText: 'ลบผู้ใช้งานถาวร',
            variant: 'danger',
            loading: false,
            action: async () => {
                confirmModal.loading = true;
                try {
                    const res = await fetch(`/api/users/${user.user_id}`, {
                        method: 'DELETE',
                        headers: getAuthHeaders()
                    });
                    const data = await res.json().catch(() => ({}));
                    if (res.ok && data.success !== false) {
                        users = users.filter(u => u.user_id !== user.user_id);
                        toast(`ลบผู้ใช้งาน ${user.username} เรียบร้อยแล้ว`, 'success');
                        closeConfirmModal();
                    } else {
                        toast(data.error || 'ลบผู้ใช้งานไม่สำเร็จ', 'error');
                    }
                } catch (err) {
                    toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
                } finally {
                    confirmModal.loading = false;
                }
            }
        };
        await tick();
        confirmDialogEl?.focus();
    }

    function closeConfirmModal() {
        confirmModal.show = false;
        confirmModal.loading = false;
        lastTriggerEl?.focus?.();
    }

    function requestCloseEditModal() {
        if (isSaving) return;
        if (isFormDirty && !confirmDiscardOpen) {
            confirmDiscardOpen = true;
            return;
        }
        forceCloseEditModal();
    }

    function forceCloseEditModal() {
        confirmDiscardOpen = false;
        showModal = false;
        roleChangedNotice = '';
        formErrors = {};
        revokeAvatarBlob();
        lastTriggerEl?.focus?.();
    }

    async function openCreateModal() {
        lastTriggerEl = document.activeElement;
        revokeAvatarBlob();
        isEditMode = false;
        activeModalTab = 'general';
        isDragOverAvatar = false;
        previewAvatarError = false;
        showPassword = true;
        showSocialFields = false;
        roleChangedNotice = '';
        confirmDiscardOpen = false;
        formErrors = {};
        modalProjectSearch = '';
        formData = {
            user_id: null,
            username: '',
            email: '',
            display_name: '',
            password: generateStrongPassword(12),
            role: 'user',
            avatar_path: null,
            phone: '',
            department: '',
            github_url: '',
            linkedin_url: '',
            line_id: '',
            allowed_menus: USER_MENUS.map(m => m.id),
            allowed_projects: ['all'],
            must_change_password: true,
            monthly_token_quota: 0,
            trello_username: '',
            github_username: ''
        };
        memberTokens = [];
        newlyCreatedToken = '';
        newTokenName = '';
        avatarFile = null;
        avatarPreview = null;
        initialFormSnapshot = serializeForm();
        showModal = true;
        await tick();
        editDialogEl?.focus();
    }

    async function openEditModal(user, initialTab = 'general') {
        lastTriggerEl = document.activeElement;
        revokeAvatarBlob();
        isEditMode = true;
        activeModalTab = initialTab;
        isDragOverAvatar = false;
        previewAvatarError = false;
        showPassword = false;
        roleChangedNotice = '';
        confirmDiscardOpen = false;
        formErrors = {};
        modalProjectSearch = '';
        const defaultMenus = (user.role === 'admin' ? ADMIN_MENUS : USER_MENUS).map(m => m.id);
        let initialProjects = ['all'];
        if (Array.isArray(user.allowed_projects)) {
            initialProjects = [...user.allowed_projects];
        }
        formData = {
            user_id: user.user_id,
            username: user.username || '',
            email: user.email || '',
            display_name: user.display_name || '',
            password: '',
            role: user.role || 'user',
            avatar_path: user.avatar_path || null,
            phone: user.phone || '',
            department: user.department || '',
            github_url: user.github_url || '',
            linkedin_url: user.linkedin_url || '',
            line_id: user.line_id || '',
            allowed_menus: Array.isArray(user.allowed_menus) ? [...user.allowed_menus] : defaultMenus,
            allowed_projects: initialProjects,
            must_change_password: Boolean(user.must_change_password),
            monthly_token_quota: Number(user.monthly_token_quota || 0),
            trello_username: user.trello_username || '',
            github_username: user.github_username || ''
        };
        showSocialFields = Boolean(formData.github_url || formData.linkedin_url || formData.line_id);
        avatarFile = null;
        avatarPreview = user.avatar_path ? `${user.avatar_path}` : null;
        memberTokens = [];
        newlyCreatedToken = '';
        newTokenName = '';
        initialFormSnapshot = serializeForm();
        showModal = true;
        if (initialTab === 'security') {
            fetchMemberTokens(user.user_id);
        }
        await tick();
        editDialogEl?.focus();
    }

    function setAvatarFile(file) {
        if (!file || !file.type.startsWith('image/')) {
            toast('กรุณาเลือกไฟล์รูปภาพเท่านั้น (JPG, PNG, WEBP)', 'warning');
            return;
        }
        if (file.size > 5 * 1024 * 1024) {
            toast('ขนาดไฟล์รูปภาพต้องไม่เกิน 5 MB', 'warning');
            return;
        }
        revokeAvatarBlob();
        avatarFile = file;
        avatarBlobUrl = URL.createObjectURL(file);
        avatarPreview = avatarBlobUrl;
        previewAvatarError = false;
        toast('เลือกรูปภาพใหม่สำเร็จ', 'success');
    }

    function handleAvatarDrop(e) {
        isDragOverAvatar = false;
        const file = e.dataTransfer?.files?.[0];
        if (file) setAvatarFile(file);
    }

    function removeAvatar() {
        revokeAvatarBlob();
        avatarFile = null;
        avatarPreview = null;
        previewAvatarError = false;
        formData.avatar_path = null;
        toast('ลบรูปโปรไฟล์แล้ว (กดบันทึกเพื่อยืนยัน)', 'info');
    }

    // Permission helpers
    function toggleMenuPermission(menuId) {
        if (formData.allowed_menus.includes(menuId)) {
            formData.allowed_menus = formData.allowed_menus.filter(id => id !== menuId);
        } else {
            formData.allowed_menus = [...formData.allowed_menus, menuId];
        }
    }

    function selectAllMenusForGroup(groupMenus) {
        const merged = new Set([...formData.allowed_menus, ...groupMenus.map(m => m.id)]);
        formData.allowed_menus = Array.from(merged);
    }

    function clearMenusForGroup(groupMenus) {
        const removeSet = new Set(groupMenus.map(m => m.id));
        formData.allowed_menus = formData.allowed_menus.filter(id => !removeSet.has(id));
    }

    function applyPermissionPreset(preset) {
        if (formData.role === 'admin' && preset.id !== 'admin_full') {
            // Keep current admin menus and apply the QA preset on top
            const adminIds = formData.allowed_menus.filter(id => ADMIN_MENUS.some(m => m.id === id));
            const baseAdmin = adminIds.length > 0 ? adminIds : ADMIN_MENUS.map(m => m.id);
            formData.allowed_menus = Array.from(new Set([...baseAdmin, ...preset.menus]));
        } else {
            formData.allowed_menus = [...preset.menus];
        }
        toast(`ใช้ชุดสิทธิ์ "${preset.label}" แล้ว`, 'info');
    }

    function setProjectAccessMode(mode) {
        if (mode === 'all') {
            formData.allowed_projects = ['all'];
        } else {
            if (formData.allowed_projects.includes('all')) {
                formData.allowed_projects = allProjects.length > 0 ? [String(allProjects[0].id || allProjects[0].project_id || allProjects[0].project_code)] : [];
            }
        }
    }

    function toggleProjectPermission(proj) {
        const pId = String(proj.id || proj.project_id || '').trim();
        const pCode = String(proj.project_code || '').trim();
        const targetKey = pId || pCode;
        if (!targetKey) return;

        if (formData.allowed_projects.includes('all')) {
            formData.allowed_projects = [targetKey];
            return;
        }

        const isCurrentlySelected = isProjectSelected(proj);
        if (isCurrentlySelected) {
            formData.allowed_projects = formData.allowed_projects.filter(id => {
                const s = String(id).trim().toLowerCase();
                return (!pId || s !== pId.toLowerCase()) && (!pCode || s !== pCode.toLowerCase());
            });
        } else {
            formData.allowed_projects = [...formData.allowed_projects, targetKey];
        }
    }

    function isProjectSelected(proj) {
        if (!proj) return false;
        if (formData.allowed_projects.includes('all')) return true;
        const pId = String(proj.id || proj.project_id || '').trim().toLowerCase();
        const pCode = String(proj.project_code || '').trim().toLowerCase();
        return formData.allowed_projects.some(id => {
            const s = String(id).trim().toLowerCase();
            return (pId && s === pId) || (pCode && s === pCode);
        });
    }

    function selectAllProjects() {
        formData.allowed_projects = allProjects.map(p => String(p.id || p.project_id || p.project_code));
    }

    function deselectAllProjects() {
        formData.allowed_projects = [];
    }

    function handleRoleChange(newRole) {
        if (isEditMode && isSelfUser(formData)) {
            toast('ไม่สามารถเปลี่ยนระดับสิทธิ์ของบัญชีตัวเองได้', 'warning');
            return;
        }
        if (newRole === formData.role) return;
        formData.role = newRole;
        if (newRole === 'admin') {
            // Additive: keep existing QA user menus and add admin default menus
            formData.allowed_menus = Array.from(new Set([...ADMIN_MENUS.map(m => m.id), ...formData.allowed_menus]));
            roleChangedNotice = 'เปลี่ยนเป็น Admin แล้ว — ระบบเพิ่มเมนูผู้ดูแลระบบให้โดยอัตโนมัติ (สามารถปรับเพิ่ม/ลดเมนูฝั่ง QA ได้ในแท็บกำหนดสิทธิ์)';
        } else {
            // Strip admin-only menus when demoting to user
            const userIds = new Set(USER_MENUS.map(m => m.id));
            const keptUserMenus = formData.allowed_menus.filter(id => userIds.has(id));
            formData.allowed_menus = keptUserMenus.length > 0 ? keptUserMenus : USER_MENUS.map(m => m.id);
            roleChangedNotice = 'เปลี่ยนเป็น User แล้ว — ระบบนำเมนูเฉพาะผู้ดูแลระบบออกและตั้งค่าเมนู QA ให้เรียบร้อย';
        }
    }

    function validateForm() {
        const errs = {};
        const cleanDisplay = (formData.display_name || '').trim();
        const cleanUsername = (formData.username || '').trim();
        const cleanEmail = (formData.email || '').trim();

        if (!cleanDisplay) errs.display_name = 'กรุณากรอกชื่อที่แสดงในระบบ';
        if (!cleanUsername) errs.username = 'กรุณากรอก Username';
        if (!cleanEmail) {
            errs.email = 'กรุณากรอกอีเมล';
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
            errs.email = 'รูปแบบอีเมลไม่ถูกต้อง';
        }
        if (!isEditMode && !formData.password) {
            errs.password = 'กรุณากรอกหรือสุ่มรหัสผ่านเริ่มต้น';
        } else if (formData.password && formData.password.length < 8) {
            errs.password = 'รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร';
        }

        formErrors = errs;
        return Object.keys(errs).length === 0;
    }

    async function handleSaveUser() {
        if (isSaving) return;
        if (!validateForm()) {
            activeModalTab = 'general';
            await tick();
            const firstErrKey = Object.keys(formErrors)[0];
            if (firstErrKey) {
                const targetId = firstErrKey === 'password' ? 'member_password' : firstErrKey;
                document.getElementById(targetId)?.focus();
            }
            toast('กรุณาตรวจสอบข้อมูลในช่องที่ระบุสีแดงให้ครบถ้วน', 'warning');
            return;
        }

        if (formData.allowed_menus.length === 0) {
            toast('คำเตือน: บัญชีนี้ไม่ได้เลือกสิทธิ์เมนูใดเลย (สามารถกลับมาเพิ่มภายหลังได้)', 'info');
        }
        if (!formData.allowed_projects.includes('all') && formData.allowed_projects.length === 0) {
            toast('คำเตือน: บัญชีนี้ยังไม่ได้เลือกโครงการที่อนุญาต', 'info');
        }

        const issuedPassword = formData.password;
        const wasCreate = !isEditMode;

        const payload = {
            ...formData,
            username: formData.username.trim(),
            email: formData.email.trim(),
            display_name: formData.display_name.trim()
        };
        if (isEditMode && isSelfUser(formData)) {
            delete payload.role;
        }

        const url = isEditMode ? `/api/users/${formData.user_id}` : '/api/users';
        const method = isEditMode ? 'PUT' : 'POST';

        isSaving = true;
        try {
            const res = await fetch(url, {
                method,
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (res.ok && data.success) {
                const userId = data.user.user_id;
                let finalAvatarPath = data.user.avatar_path;

                if (avatarFile) {
                    const uploadData = new FormData();
                    uploadData.append('avatar', avatarFile);
                    try {
                        const token = localStorage.getItem('jwt_token');
                        const avRes = await fetch(`/api/users/${userId}/avatar`, {
                            method: 'POST',
                            headers: { 'Authorization': `Bearer ${token}` },
                            body: uploadData
                        });
                        const avData = await avRes.json().catch(() => ({}));
                        if (avRes.ok && avData.success) {
                            finalAvatarPath = avData.avatar_path || finalAvatarPath;
                        } else {
                            toast(avData.error || 'บันทึกผู้ใช้สำเร็จ แต่อัปโหลดรูปโปรไฟล์ไม่สำเร็จ', 'warning');
                        }
                    } catch (e) {
                        toast('บันทึกผู้ใช้สำเร็จ แต่อัปโหลดรูปโปรไฟล์ไม่สำเร็จ', 'warning');
                    }
                }

                if (isEditMode && isSelfUser(data.user)) {
                    updateAuthProfile(
                        data.user.display_name,
                        finalAvatarPath || '',
                        data.user.email,
                        data.user.allowed_menus,
                        data.user.allowed_projects
                    );
                }

                toast(wasCreate ? 'สร้างผู้ใช้งานใหม่เรียบร้อยแล้ว' : 'อัปเดตข้อมูลและสิทธิ์ผู้ใช้งานเรียบร้อยแล้ว', 'success');
                forceCloseEditModal();
                await fetchUsers();

                // Show Post-Create Credential Handoff Card so Admin can copy credentials safely
                if (wasCreate && issuedPassword) {
                    handoffModal = {
                        show: true,
                        display_name: data.user.display_name,
                        username: data.user.username,
                        email: data.user.email,
                        password: issuedPassword,
                        role: data.user.role,
                        menuCount: Array.isArray(data.user.allowed_menus) ? data.user.allowed_menus.length : 0,
                        projectSummary: !data.user.allowed_projects || data.user.allowed_projects.includes('all')
                            ? 'ทุกโครงการ'
                            : `${data.user.allowed_projects.length} โครงการ`
                    };
                    await tick();
                    handoffDialogEl?.focus();
                }
            } else {
                toast(data.error || 'ไม่สามารถบันทึกข้อมูลได้', 'error');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์', 'error');
        } finally {
            isSaving = false;
        }
    }

    function copyFullCredentials() {
        const text = `บัญชีเข้าใช้งาน Spectra QA\nชื่อ: ${handoffModal.display_name}\nUsername: ${handoffModal.username}\nEmail: ${handoffModal.email}\nPassword: ${handoffModal.password}\nสิทธิ์: ${handoffModal.role.toUpperCase()} (${handoffModal.menuCount} เมนู · ${handoffModal.projectSummary})`;
        copyText(text, 'คัดลอกข้อมูลบัญชีและรหัสผ่านทั้งหมดแล้ว');
    }

    function closeHandoffModal() {
        handoffModal.show = false;
        lastTriggerEl?.focus?.();
    }

    function handleModalTabKeydown(e) {
        if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
        e.preventDefault();
        const tabs = isEditMode ? ['general', 'permissions', 'security'] : ['general', 'permissions'];
        const idx = tabs.indexOf(activeModalTab);
        const nextIdx = e.key === 'ArrowRight' ? (idx + 1) % tabs.length : (idx - 1 + tabs.length) % tabs.length;
        const nextTab = tabs[nextIdx];
        activeModalTab = nextTab;
        if (nextTab === 'security' && isEditMode && formData.user_id) {
            fetchMemberTokens(formData.user_id);
        }
    }

    function handleWindowKeydown(e) {
        if (e.key !== 'Escape') return;
        if (bulkModal.show && !bulkModal.loading) {
            bulkModal.show = false;
        } else if (handoffModal.show) {
            closeHandoffModal();
        } else if (confirmModal.show && !confirmModal.loading) {
            closeConfirmModal();
        } else if (showModal && !isSaving) {
            requestCloseEditModal();
        }
    }

    function markAvatarFailed(userId) {
        failedAvatarIds = new Set([...failedAvatarIds, userId]);
    }

    function formatDate(isoString) {
        if (!isoString) return '-';
        const d = new Date(isoString + (!isoString.endsWith('Z') && !isoString.includes('+') ? 'Z' : ''));
        return d.toLocaleString('th-TH', {
            day: '2-digit', month: '2-digit', year: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });
    }

    function resetFilters() {
        searchQuery = '';
        roleFilter = 'all';
        statusFilter = 'all';
        departmentFilter = 'all';
        projectFilter = 'all';
    }

    function toggleSort(key) {
        if (sortKey === key) {
            sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        } else {
            sortKey = key;
            sortDir = (key === 'last_login_at' || key === 'login_count') ? 'desc' : 'asc';
        }
    }

    function applyQuickStatFilter(type) {
        if (type === 'all') {
            roleFilter = 'all';
            statusFilter = 'all';
        } else if (type === 'admin' || type === 'user') {
            roleFilter = roleFilter === type ? 'all' : type;
            statusFilter = 'all';
        } else if (type === 'active') {
            statusFilter = statusFilter === 'active' ? 'all' : 'active';
        }
    }

    function userHasProject(user, projKey) {
        if (projKey === 'all') return true;
        const ap = user?.allowed_projects;
        if (!Array.isArray(ap) || ap.includes('all')) return true;
        const target = String(projKey).trim().toLowerCase();
        const projObj = allProjects.find(
            (p) => String(p.id || p.project_id || p.project_code).trim().toLowerCase() === target
        );
        const pId = projObj ? String(projObj.id || projObj.project_id || '').trim().toLowerCase() : target;
        const pCode = projObj ? String(projObj.project_code || '').trim().toLowerCase() : '';
        return ap.some((id) => {
            const s = String(id).trim().toLowerCase();
            return (pId && s === pId) || (pCode && s === pCode);
        });
    }

    $: departmentFilterOptions = [
        { value: 'all', label: 'ทุกแผนก (All)' },
        ...Array.from(new Set(users.map((u) => (u.department || '').trim()).filter(Boolean)))
            .sort((a, b) => a.localeCompare(b, 'th'))
            .map((d) => ({ value: d, label: d }))
    ];

    $: projectFilterOptions = [
        { value: 'all', label: 'ทุกโครงการ (All)' },
        ...allProjects.map((p) => ({
            value: String(p.id || p.project_id || p.project_code),
            label: p.name || p.project_name || p.project_code
        }))
    ];

    $: hasActiveFilters =
        searchQuery.trim() !== '' ||
        roleFilter !== 'all' ||
        statusFilter !== 'all' ||
        departmentFilter !== 'all' ||
        projectFilter !== 'all';

    $: filteredUsers = users
        .filter((u) => {
            const q = searchQuery.trim().toLowerCase();
            const matchSearch = !q || (
                String(u.username || '').toLowerCase().includes(q) ||
                String(u.email || '').toLowerCase().includes(q) ||
                String(u.display_name || '').toLowerCase().includes(q) ||
                String(u.department || '').toLowerCase().includes(q) ||
                String(u.trello_username || '').toLowerCase().includes(q) ||
                String(u.github_username || '').toLowerCase().includes(q)
            );
            const matchRole = roleFilter === 'all' || u.role === roleFilter;
            const matchStatus = statusFilter === 'all' || (statusFilter === 'active' ? Boolean(u.is_active) : !u.is_active);
            const matchDept = departmentFilter === 'all' || String(u.department || '').trim() === departmentFilter;
            const matchProj = userHasProject(u, projectFilter);
            return matchSearch && matchRole && matchStatus && matchDept && matchProj;
        })
        .sort((a, b) => {
            const mul = sortDir === 'asc' ? 1 : -1;
            if (sortKey === 'display_name') {
                return String(a.display_name || a.username || '').localeCompare(String(b.display_name || b.username || ''), 'th') * mul;
            }
            if (sortKey === 'role') {
                return String(a.role || '').localeCompare(String(b.role || '')) * mul;
            }
            if (sortKey === 'last_login_at') {
                const ta = a.last_login_at ? new Date(a.last_login_at).getTime() : 0;
                const tb = b.last_login_at ? new Date(b.last_login_at).getTime() : 0;
                return (ta - tb) * mul;
            }
            if (sortKey === 'login_count') {
                return ((a.login_count || 0) - (b.login_count || 0)) * mul;
            }
            return ((a.user_id || 0) - (b.user_id || 0)) * mul;
        });

    $: filteredModalProjects = allProjects.filter(p => {
        if (!modalProjectSearch) return true;
        const q = modalProjectSearch.toLowerCase();
        return (p.name || p.project_name || '').toLowerCase().includes(q) ||
               (p.project_code || '').toLowerCase().includes(q) ||
               (p.description || '').toLowerCase().includes(q);
    });

    $: allVisibleSelected = filteredUsers.length > 0 && filteredUsers.every((u) => selectedUserIds.has(u.user_id));

    $: availablePresets = QA_PERMISSION_PRESETS.filter(p => p.roles.includes(formData.role));

    $: stats = {
        total: users.length,
        admins: users.filter(u => u.role === 'admin').length,
        standard: users.filter(u => u.role === 'user').length,
        active: users.filter(u => u.is_active).length
    };
</script>

<svelte:window on:keydown={handleWindowKeydown} />

<div class="qa-member-container">
    <div class="header-section">
        <div>
            <h1 class="page-title">QA Member Management</h1>
            <p class="page-subtitle">จัดการข้อมูลสมาชิก สิทธิ์การเข้าถึงเมนู และสิทธิ์โครงการในระบบ</p>
        </div>
        <div class="header-actions-group">
            <button type="button" class="btn-secondary btn-export-csv" on:click={exportMembersCsv} title="ส่งออกรายชื่อและสิทธิ์สมาชิกเป็น CSV (User Access Review)">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                {selectedUserIds.size > 0 ? `Export CSV (${selectedUserIds.size})` : 'Export CSV'}
            </button>
            <button type="button" class="btn-primary" on:click={openCreateModal}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                เพิ่มผู้ใช้งาน
            </button>
        </div>
    </div>

    <!-- Stats Cards (clickable quick filters) -->
    <div class="stats-grid">
        <button type="button" class="stat-card" class:active={roleFilter === 'all' && statusFilter === 'all'} aria-pressed={roleFilter === 'all' && statusFilter === 'all'} on:click={() => applyQuickStatFilter('all')}>
            <div class="stat-icon icon-primary">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.total}</div>
                <div class="stat-label">สมาชิกทั้งหมด</div>
            </div>
        </button>
        <button type="button" class="stat-card" class:active={roleFilter === 'admin'} aria-pressed={roleFilter === 'admin'} on:click={() => applyQuickStatFilter('admin')}>
            <div class="stat-icon icon-secondary">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.admins}</div>
                <div class="stat-label">ผู้ดูแลระบบ (Admin)</div>
            </div>
        </button>
        <button type="button" class="stat-card" class:active={roleFilter === 'user'} aria-pressed={roleFilter === 'user'} on:click={() => applyQuickStatFilter('user')}>
            <div class="stat-icon icon-accent">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.standard}</div>
                <div class="stat-label">ผู้ใช้ทั่วไป (User)</div>
            </div>
        </button>
        <button type="button" class="stat-card" class:active={statusFilter === 'active'} aria-pressed={statusFilter === 'active'} on:click={() => applyQuickStatFilter('active')}>
            <div class="stat-icon icon-success">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.active}</div>
                <div class="stat-label">บัญชีที่เปิดใช้งาน</div>
            </div>
        </button>
    </div>

    <!-- Filters & Result Count -->
    <div class="filter-bar">
        <div class="search-box">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input type="text" bind:value={searchQuery} placeholder="ค้นหาชื่อ, อีเมล, Username หรือแผนก..." aria-label="ค้นหาผู้ใช้งาน" />
            {#if searchQuery}
                <button type="button" class="btn-clear-search" aria-label="ล้างคำค้นหา" on:click={() => (searchQuery = '')}>
                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="13" height="13"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            {/if}
        </div>
        <div class="role-filter" aria-label="กรองตามระดับสิทธิ์">
            <CustomSelect
                bind:value={roleFilter}
                options={roleFilterOptions}
                minWidth="190px"
            />
        </div>
        <div class="role-filter" aria-label="กรองตามสถานะบัญชี">
            <CustomSelect
                bind:value={statusFilter}
                options={statusFilterOptions}
                minWidth="170px"
            />
        </div>
        {#if departmentFilterOptions.length > 1}
            <div class="role-filter" aria-label="กรองตามแผนก">
                <CustomSelect
                    bind:value={departmentFilter}
                    options={departmentFilterOptions}
                    minWidth="165px"
                />
            </div>
        {/if}
        {#if allProjects.length > 0}
            <div class="role-filter" aria-label="กรองตามโครงการ">
                <CustomSelect
                    bind:value={projectFilter}
                    options={projectFilterOptions}
                    minWidth="175px"
                />
            </div>
        {/if}
        {#if hasActiveFilters}
            <button type="button" class="btn-reset-filters" on:click={resetFilters}>
                ล้างตัวกรอง
            </button>
        {/if}
        <button type="button" class="btn-refresh-users" on:click={fetchUsers} disabled={isLoading} title="รีเฟรชรายชื่อสมาชิก" aria-label="รีเฟรชรายชื่อสมาชิก">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" class:spinning={isLoading}>
                <path d="M23 4v6h-6"></path>
                <path d="M1 20v-6h6"></path>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
            </svg>
        </button>
    </div>

    <div class="table-meta-bar">
        <span>แสดง <strong>{filteredUsers.length}</strong> จากทั้งหมด <strong>{users.length}</strong> สมาชิก</span>
    </div>

    {#if selectedUserIds.size > 0}
        <div class="bulk-action-bar" role="region" aria-label="เครื่องมือจัดการแบบกลุ่ม">
            <div class="bulk-bar-left">
                <span class="bulk-count-pill">เลือกแล้ว {selectedUserIds.size} คน</span>
                <button type="button" class="btn-text-action" on:click={clearSelection}>ล้างการเลือก</button>
            </div>
            <div class="bulk-bar-actions">
                <button type="button" class="btn-bulk" on:click={() => openBulkModal('projects')}>กำหนดโครงการ</button>
                <button type="button" class="btn-bulk" on:click={() => openBulkModal('preset')}>ใช้ชุดสิทธิ์ / Template</button>
                <button type="button" class="btn-bulk success" on:click={() => handleBulkStatus('activate')}>เปิดใช้งาน</button>
                <button type="button" class="btn-bulk danger" on:click={() => handleBulkStatus('deactivate')}>ปิดใช้งาน</button>
            </div>
        </div>
    {/if}

    <!-- User Table -->
    <div class="table-container">
        {#if isLoading}
            <div class="skeleton-table" role="status" aria-live="polite" aria-label="กำลังโหลดข้อมูลผู้ใช้งาน">
                {#each [1, 2, 3, 4, 5] as _}
                    <div class="skeleton-row">
                        <div class="skeleton-avatar"></div>
                        <div class="skeleton-col wide">
                            <div class="skeleton-bar w-60"></div>
                            <div class="skeleton-bar w-40 sm"></div>
                        </div>
                        <div class="skeleton-col">
                            <div class="skeleton-bar w-70"></div>
                            <div class="skeleton-bar w-50 sm"></div>
                        </div>
                        <div class="skeleton-pill"></div>
                        <div class="skeleton-pill wide"></div>
                        <div class="skeleton-toggle"></div>
                    </div>
                {/each}
            </div>
        {:else if filteredUsers.length === 0}
            <div class="empty-state">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path><line x1="4" y1="4" x2="20" y2="20" opacity="0.5"></line></svg>
                <p>ไม่พบข้อมูลผู้ใช้งานที่ตรงกับเงื่อนไข</p>
                {#if hasActiveFilters}
                    <button type="button" class="btn-secondary" on:click={resetFilters}>ล้างตัวกรองทั้งหมด</button>
                {/if}
            </div>
        {:else}
            <table class="data-table">
                <thead>
                    <tr>
                        <th class="col-check">
                            <input
                                type="checkbox"
                                class="row-checkbox"
                                checked={allVisibleSelected}
                                aria-label="เลือกสมาชิกทั้งหมดที่แสดงอยู่"
                                on:change={toggleSelectAllVisible}
                            />
                        </th>
                        <th aria-sort={sortKey === 'display_name' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                            <button type="button" class="th-sort-btn" class:active={sortKey === 'display_name'} on:click={() => toggleSort('display_name')}>
                                ผู้ใช้งาน / แผนก
                                <svg class:desc={sortKey === 'display_name' && sortDir === 'desc'} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="12" height="12"><polyline points="6 15 12 9 18 15"></polyline></svg>
                            </button>
                        </th>
                        <th>อีเมล / Username</th>
                        <th aria-sort={sortKey === 'role' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                            <button type="button" class="th-sort-btn" class:active={sortKey === 'role'} on:click={() => toggleSort('role')}>
                                สิทธิ์ (Role)
                                <svg class:desc={sortKey === 'role' && sortDir === 'desc'} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="12" height="12"><polyline points="6 15 12 9 18 15"></polyline></svg>
                            </button>
                        </th>
                        <th>สิทธิ์เมนู & โครงการ</th>
                        <th>สถานะ</th>
                        <th aria-sort={sortKey === 'last_login_at' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                            <button type="button" class="th-sort-btn" class:active={sortKey === 'last_login_at'} on:click={() => toggleSort('last_login_at')}>
                                เข้าสู่ระบบล่าสุด
                                <svg class:desc={sortKey === 'last_login_at' && sortDir === 'desc'} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="12" height="12"><polyline points="6 15 12 9 18 15"></polyline></svg>
                            </button>
                        </th>
                        <th style="text-align: right;">จัดการ</th>
                    </tr>
                </thead>
                <tbody>
                    {#each filteredUsers as user (user.user_id)}
                        {@const selfAccount = isSelfUser(user)}
                        {@const lastAdmin = isLastActiveAdmin(user)}
                        <tr class:row-inactive={!user.is_active} class:row-selected={selectedUserIds.has(user.user_id)}>
                            <td class="col-check">
                                <input
                                    type="checkbox"
                                    class="row-checkbox"
                                    checked={selectedUserIds.has(user.user_id)}
                                    aria-label={`เลือก ${user.username}`}
                                    on:change={() => toggleSelectUser(user.user_id)}
                                />
                            </td>
                            <td>
                                <div class="user-cell">
                                    <div class="avatar">
                                        {#if user.avatar_path && !failedAvatarIds.has(user.user_id)}
                                            <img
                                                src={`${user.avatar_path}`}
                                                alt={user.display_name || user.username}
                                                on:error={() => markAvatarFailed(user.user_id)}
                                            />
                                        {:else}
                                            {(user.display_name || user.username || 'U').charAt(0).toUpperCase()}
                                        {/if}
                                    </div>
                                    <div class="user-info">
                                        <div class="d-name">
                                            <span>{user.display_name || 'No Display Name'}</span>
                                            {#if selfAccount}
                                                <span class="self-tag">คุณ</span>
                                            {/if}
                                            {#if !user.is_active}
                                                <span class="inactive-tag">ปิดใช้งาน</span>
                                            {/if}
                                            {#if user.must_change_password}
                                                <span class="pw-reset-tag" title="ระบบจะบังคับให้เปลี่ยนรหัสผ่านเมื่อเข้าสู่ระบบครั้งถัดไป">รอเปลี่ยนรหัส</span>
                                            {/if}
                                        </div>
                                        <div class="user-sub-meta">
                                            {#if user.department}
                                                <span class="dept-chip">{user.department}</span>
                                                <span class="meta-sep">·</span>
                                            {/if}
                                            <span class="c-date">สร้างเมื่อ {formatDate(user.created_at)}</span>
                                        </div>
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div class="email-cell">
                                    <div class="username-text">{user.username}</div>
                                    <div class="email-text">{user.email}</div>
                                    {#if user.trello_username || user.github_username}
                                        <div class="board-handle-chips">
                                            {#if user.trello_username}
                                                <span class="handle-chip trello" title="Trello Username (QA Board Card)">Trello: @{user.trello_username}</span>
                                            {/if}
                                            {#if user.github_username}
                                                <span class="handle-chip github" title="GitHub Username (QA Board Card)">GH: @{user.github_username}</span>
                                            {/if}
                                        </div>
                                    {/if}
                                </div>
                            </td>
                            <td>
                                <button
                                    type="button"
                                    class="role-badge"
                                    class:admin={user.role === 'admin'}
                                    disabled={selfAccount || lastAdmin}
                                    on:click={() => handleToggleRole(user)}
                                    title={selfAccount ? 'ไม่สามารถเปลี่ยนสิทธิ์บัญชีตัวเองได้' : lastAdmin ? 'Admin คนสุดท้ายของระบบ' : 'คลิกเพื่อสลับระดับสิทธิ์'}
                                >
                                    {#if user.role === 'admin'}
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>
                                        Admin
                                    {:else}
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                                        User
                                    {/if}
                                </button>
                            </td>
                            <td>
                                <div class="permission-summary-badges">
                                    <button
                                        type="button"
                                        class="perm-badge menu-perm"
                                        on:click={() => openEditModal(user, 'permissions')}
                                        title={getMenuTooltip(user.allowed_menus)}
                                    >
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
                                        {user.allowed_menus ? user.allowed_menus.length : 0} เมนู
                                    </button>
                                    <button
                                        type="button"
                                        class="perm-badge project-perm"
                                        on:click={() => openEditModal(user, 'permissions')}
                                        title={getProjectTooltip(user.allowed_projects)}
                                    >
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                                        {#if !user.allowed_projects || user.allowed_projects.includes('all')}
                                            ทุกโครงการ
                                        {:else}
                                            {user.allowed_projects.length} โครงการ
                                        {/if}
                                    </button>
                                    {#if user.active_token_count > 0}
                                        <button
                                            type="button"
                                            class="perm-badge token-perm"
                                            on:click={() => openEditModal(user, 'security')}
                                            title="ดูและจัดการ Personal API Tokens ของผู้ใช้นี้"
                                        >
                                            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path></svg>
                                            {user.active_token_count} Token
                                        </button>
                                    {/if}
                                    {#if user.monthly_tokens_used > 0 || user.monthly_token_quota > 0}
                                        {@const overQuota = user.monthly_token_quota > 0 && user.monthly_tokens_used >= user.monthly_token_quota}
                                        {@const nearQuota = !overQuota && user.monthly_token_quota > 0 && user.monthly_tokens_used >= user.monthly_token_quota * 0.8}
                                        <button
                                            type="button"
                                            class="perm-badge usage-perm"
                                            class:warn={nearQuota}
                                            class:danger={overQuota}
                                            on:click={() => openActivityDrawer(user)}
                                            title="ดูสรุปการใช้ AI Token เดือนนี้และประวัติ Audit"
                                        >
                                            {formatCompactTokens(user.monthly_tokens_used)}{user.monthly_token_quota > 0 ? ` / ${formatCompactTokens(user.monthly_token_quota)}` : ''} tok
                                        </button>
                                    {/if}
                                </div>
                            </td>
                            <td>
                                <label
                                    class="toggle-switch"
                                    class:disabled={selfAccount || (user.is_active && lastAdmin) || togglingUserIds.has(user.user_id)}
                                    title={selfAccount ? 'ไม่สามารถปิดการใช้งานบัญชีตัวเองได้' : (user.is_active && lastAdmin) ? 'ไม่สามารถปิด Admin คนสุดท้ายของระบบได้' : 'สลับสถานะเปิด/ปิดการใช้งาน'}
                                >
                                    <input
                                        type="checkbox"
                                        checked={user.is_active}
                                        disabled={selfAccount || (user.is_active && lastAdmin) || togglingUserIds.has(user.user_id)}
                                        aria-label={`สลับสถานะการใช้งานของ ${user.username}`}
                                        on:change={(e) => handleToggleStatus(user, e)}
                                    />
                                    <span class="slider"></span>
                                </label>
                            </td>
                            <td>
                                <div class="login-cell">
                                    <div class="last-login">{formatDate(user.last_login_at)}</div>
                                    <div class="login-count">{user.login_count || 0} ครั้ง</div>
                                </div>
                            </td>
                            <td style="text-align: right;">
                                <div class="action-buttons">
                                    <button type="button" class="icon-btn activity" on:click={() => openActivityDrawer(user)} title="ประวัติกิจกรรม & การใช้ AI Token" aria-label={`ดูประวัติกิจกรรมของ ${user.username}`}>
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                                    </button>
                                    <button type="button" class="icon-btn edit" on:click={() => openEditModal(user, 'general')} title="แก้ไขข้อมูลและสิทธิ์" aria-label={`แก้ไข ${user.username}`}>
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                                    </button>
                                    <button
                                        type="button"
                                        class="icon-btn revoke"
                                        on:click={() => handleForceLogout(user)}
                                        disabled={selfAccount || !user.is_active}
                                        title={selfAccount ? 'ไม่สามารถบังคับออกจากระบบบัญชีตัวเองได้' : !user.is_active ? 'บัญชีนี้ปิดใช้งานอยู่แล้ว' : 'บังคับออกจากระบบทุกอุปกรณ์ (Force Logout)'}
                                        aria-label={`บังคับออกจากระบบ ${user.username}`}
                                    >
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                                    </button>
                                    <button
                                        type="button"
                                        class="icon-btn delete"
                                        on:click={() => handleDelete(user)}
                                        disabled={selfAccount || lastAdmin}
                                        title={selfAccount ? 'ไม่สามารถลบบัญชีตัวเองได้' : lastAdmin ? 'ไม่สามารถลบ Admin คนสุดท้ายได้' : 'ลบผู้ใช้งาน'}
                                        aria-label={`ลบ ${user.username}`}
                                    >
                                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        {/if}
    </div>
</div>

<!-- Create / Edit Member Modal (Spectra Obsidian + Distilled IA + Focus Trap) -->
{#if showModal}
<div class="modal-backdrop" role="presentation" on:click={requestCloseEditModal}>
    <div
        bind:this={editDialogEl}
        class="modal-content modal-large"
        role="dialog"
        aria-modal="true"
        aria-labelledby="member-modal-title"
        tabindex="-1"
        on:keydown={trapFocus}
        on:click|stopPropagation
    >
        <div class="modal-header-bar">
            <div>
                <h2 id="member-modal-title" class="modal-title">
                    {isEditMode ? 'แก้ไขข้อมูลผู้ใช้งาน & สิทธิ์การเข้าถึง' : 'เพิ่มผู้ใช้งานใหม่ & กำหนดสิทธิ์'}
                </h2>
                <p class="modal-subtitle">
                    {isEditMode ? `กำลังจัดการบัญชี @${formData.username}` : 'กำหนดข้อมูลบัญชี รหัสผ่านเริ่มต้น และสิทธิ์เมนู/โครงการ'}
                </p>
            </div>
            <button type="button" class="close-btn" aria-label="ปิดหน้าต่าง" on:click={requestCloseEditModal} disabled={isSaving}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>

        {#if confirmDiscardOpen}
            <div class="discard-warning-bar" role="alert">
                <span>มีการแก้ไขที่ยังไม่ได้บันทึก ต้องการละทิ้งการเปลี่ยนแปลงและปิดหน้าต่างหรือไม่?</span>
                <div class="discard-actions">
                    <button type="button" class="btn-mini-ghost" on:click={() => (confirmDiscardOpen = false)}>กลับไปแก้ไข</button>
                    <button type="button" class="btn-mini-danger" on:click={forceCloseEditModal}>ละทิ้งและปิด</button>
                </div>
            </div>
        {/if}

        <!-- Modal Navigation Tabs (Proper ARIA Tablist + Arrow Key Support) -->
        <div class="modal-tab-bar" role="tablist" aria-label="หมวดการตั้งค่าผู้ใช้งาน" tabindex="0" on:keydown={handleModalTabKeydown}>
            <button
                type="button"
                role="tab"
                id="tab-general"
                aria-selected={activeModalTab === 'general'}
                aria-controls="member-modal-panel"
                class="modal-tab-btn"
                class:active={activeModalTab === 'general'}
                on:click={() => (activeModalTab = 'general')}
            >
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                ข้อมูลบัญชี & โปรไฟล์
            </button>
            <button
                type="button"
                role="tab"
                id="tab-permissions"
                aria-selected={activeModalTab === 'permissions'}
                aria-controls="member-modal-panel"
                class="modal-tab-btn"
                class:active={activeModalTab === 'permissions'}
                on:click={() => (activeModalTab = 'permissions')}
            >
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                สิทธิ์เมนู & โครงการ
                <span class="tab-badge">
                    {formData.allowed_menus.length} เมนู · {formData.allowed_projects.includes('all') ? 'ทุกโครงการ' : `${formData.allowed_projects.length} โครงการ`}
                </span>
            </button>
            {#if isEditMode}
                <button
                    type="button"
                    role="tab"
                    id="tab-security"
                    aria-selected={activeModalTab === 'security'}
                    aria-controls="member-modal-panel"
                    class="modal-tab-btn"
                    class:active={activeModalTab === 'security'}
                    on:click={() => { activeModalTab = 'security'; fetchMemberTokens(formData.user_id); }}
                >
                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path></svg>
                    ความปลอดภัย & Token
                </button>
            {/if}
        </div>

        <div id="member-modal-panel" class="modal-scroll-area" role="tabpanel" aria-labelledby={activeModalTab === 'general' ? 'tab-general' : activeModalTab === 'permissions' ? 'tab-permissions' : 'tab-security'}>
            {#if activeModalTab === 'general'}
                <!-- Compact Horizontal Avatar Strip -->
                <div
                    class="avatar-compact-strip"
                    class:drag-over={isDragOverAvatar}
                    role="region"
                    aria-label="อัปโหลดรูปโปรไฟล์"
                    on:dragover|preventDefault={() => (isDragOverAvatar = true)}
                    on:dragleave|preventDefault={() => (isDragOverAvatar = false)}
                    on:drop|preventDefault={handleAvatarDrop}
                >
                    <button
                        type="button"
                        class="avatar-compact-circle"
                        on:click={() => document.getElementById('qa_member_avatar_input')?.click()}
                        title="คลิกหรือลากวางไฟล์รูปภาพ (JPG, PNG, WEBP ไม่เกิน 5MB)"
                        aria-label="เปลี่ยนรูปโปรไฟล์"
                    >
                        {#if avatarPreview && !previewAvatarError}
                            <img src={avatarPreview} alt="Preview Avatar" on:error={() => (previewAvatarError = true)} />
                        {:else}
                            <span class="avatar-fallback-sm">
                                {(formData.display_name || formData.username || 'U').charAt(0).toUpperCase()}
                            </span>
                        {/if}
                    </button>

                    <div class="avatar-strip-meta">
                        <div class="avatar-strip-title">รูปโปรไฟล์ (ไม่บังคับ)</div>
                        <div class="avatar-strip-hint">รองรับ JPG, PNG, WEBP ขนาดไม่เกิน 5 MB (คลิกหรือลากวางได้)</div>
                    </div>

                    <div class="avatar-strip-actions">
                        <button type="button" class="btn-avatar-action upload" on:click={() => document.getElementById('qa_member_avatar_input')?.click()}>
                            อัปโหลดรูป
                        </button>
                        {#if avatarPreview}
                            <button type="button" class="btn-avatar-action remove" on:click={removeAvatar}>
                                ลบรูป
                            </button>
                        {/if}
                    </div>

                    <input
                        type="file"
                        id="qa_member_avatar_input"
                        accept="image/*"
                        style="display: none;"
                        on:change={(e) => {
                            const file = e.target.files?.[0];
                            if (file) setAvatarFile(file);
                            e.target.value = '';
                        }}
                    />
                </div>

                <!-- Section 1: Account & Credentials -->
                <div class="form-section-heading">ข้อมูลบัญชีและสิทธิ์ระดับระบบ</div>
                <div class="form-grid">
                    <div class="form-group full-width">
                        <label for="display_name">Display Name (ชื่อที่แสดงในระบบ) <span class="req">*</span></label>
                        <input
                            type="text"
                            id="display_name"
                            bind:value={formData.display_name}
                            class:is-invalid={formErrors.display_name}
                            aria-invalid={Boolean(formErrors.display_name)}
                            placeholder="เช่น สมชาย ใจดี"
                            on:input={() => { if (formErrors.display_name) formErrors = { ...formErrors, display_name: '' }; }}
                        />
                        {#if formErrors.display_name}<span class="field-err">{formErrors.display_name}</span>{/if}
                    </div>

                    <div class="form-group">
                        <label for="username">Username <span class="req">*</span></label>
                        <input
                            type="text"
                            id="username"
                            bind:value={formData.username}
                            disabled={isEditMode}
                            class:is-invalid={formErrors.username}
                            aria-invalid={Boolean(formErrors.username)}
                            placeholder="เช่น s.somchai"
                            on:input={() => { if (formErrors.username) formErrors = { ...formErrors, username: '' }; }}
                        />
                        {#if formErrors.username}<span class="field-err">{formErrors.username}</span>{/if}
                    </div>

                    <div class="form-group">
                        <label for="email">Email Address <span class="req">*</span></label>
                        <input
                            type="email"
                            id="email"
                            bind:value={formData.email}
                            disabled={isEditMode}
                            class:is-invalid={formErrors.email}
                            aria-invalid={Boolean(formErrors.email)}
                            placeholder="เช่น somchai@company.com"
                            on:input={() => { if (formErrors.email) formErrors = { ...formErrors, email: '' }; }}
                        />
                        {#if formErrors.email}<span class="field-err">{formErrors.email}</span>{/if}
                    </div>

                    <div class="form-group full-width">
                        <label for="member_password">
                            {isEditMode ? 'เปลี่ยนรหัสผ่านใหม่ (เว้นว่างหากไม่ต้องการเปลี่ยน)' : 'รหัสผ่านเริ่มต้น (อย่างน้อย 8 ตัวอักษร) *'}
                        </label>
                        <div class="password-input-row">
                            {#if showPassword}
                                <input
                                    type="text"
                                    id="member_password"
                                    bind:value={formData.password}
                                    class:is-invalid={formErrors.password}
                                    aria-invalid={Boolean(formErrors.password)}
                                    placeholder={isEditMode ? 'กรอกรหัสผ่านใหม่ หรือกดสุ่มรหัส...' : 'อย่างน้อย 8 ตัวอักษร'}
                                    autocomplete="new-password"
                                    on:input={() => { if (formErrors.password) formErrors = { ...formErrors, password: '' }; }}
                                />
                            {:else}
                                <input
                                    type="password"
                                    id="member_password"
                                    bind:value={formData.password}
                                    class:is-invalid={formErrors.password}
                                    aria-invalid={Boolean(formErrors.password)}
                                    placeholder={isEditMode ? 'กรอกรหัสผ่านใหม่ หรือกดสุ่มรหัส...' : 'อย่างน้อย 8 ตัวอักษร'}
                                    autocomplete="new-password"
                                    on:input={() => { if (formErrors.password) formErrors = { ...formErrors, password: '' }; }}
                                />
                            {/if}
                            <button type="button" class="btn-pw-mini" on:click={() => (showPassword = !showPassword)}>
                                {showPassword ? 'ซ่อน' : 'ดู'}
                            </button>
                            <button
                                type="button"
                                class="btn-pw-mini accent"
                                on:click={() => { formData.password = generateStrongPassword(12); showPassword = true; formErrors = { ...formErrors, password: '' }; toast('สุ่มรหัสผ่านใหม่ที่ปลอดภัยแล้ว', 'info'); }}
                            >
                                สุ่มรหัส
                            </button>
                            {#if formData.password}
                                <button type="button" class="btn-pw-mini" on:click={() => copyText(formData.password, 'คัดลอกรหัสผ่านแล้ว')}>
                                    คัดลอก
                                </button>
                            {/if}
                        </div>
                        {#if formErrors.password}
                            <span class="field-err">{formErrors.password}</span>
                        {:else if passwordStrength}
                            <div class="pw-strength-row" aria-live="polite">
                                <div class="pw-strength-track">
                                    <div class="pw-strength-fill {passwordStrength.level}" style="width: {passwordStrength.percent}%"></div>
                                </div>
                                <span class="pw-strength-label {passwordStrength.level}">{passwordStrength.label}</span>
                            </div>
                        {/if}
                        <label class="must-change-pw-check">
                            <input type="checkbox" bind:checked={formData.must_change_password} />
                            <span>บังคับให้ผู้ใช้งานเปลี่ยนรหัสผ่านใหม่เมื่อเข้าสู่ระบบครั้งถัดไป</span>
                        </label>
                    </div>

                    <div class="form-group">
                        <label for="role">ระดับสิทธิ์ (Role)</label>
                        {#if isEditMode && isSelfUser(formData)}
                            <div class="role-locked-notice">
                                {formData.role === 'admin' ? 'ผู้ดูแลระบบ (Admin)' : 'ผู้ใช้ทั่วไป (User)'} — ไม่สามารถเปลี่ยนสิทธิ์บัญชีตัวเองได้
                            </div>
                        {:else}
                            <CustomSelect
                                id="role"
                                value={formData.role}
                                options={roleFormOptions}
                                width="100%"
                                on:change={(e) => handleRoleChange(e.detail)}
                            />
                        {/if}
                    </div>

                    <div class="form-group">
                        <label for="department">แผนก / ตำแหน่งงาน (Department)</label>
                        <input type="text" id="department" bind:value={formData.department} placeholder="เช่น Senior QA Automation" />
                    </div>

                    <div class="form-group">
                        <label for="trello_username">Trello Username (เชื่อม QA Board Card)</label>
                        <input type="text" id="trello_username" bind:value={formData.trello_username} placeholder="เช่น somchai_qa (ไม่ต้องใส่ @)" />
                    </div>

                    <div class="form-group">
                        <label for="github_username">GitHub Username (เชื่อม QA Board Card)</label>
                        <input type="text" id="github_username" bind:value={formData.github_username} placeholder="เช่น somchai-dev (ไม่ต้องใส่ @)" />
                    </div>
                </div>

                {#if roleChangedNotice}
                    <div class="inline-info-banner">{roleChangedNotice}</div>
                {/if}

                <!-- Collapsible Contact & Social Section (Replaces nested sub-tabs) -->
                <div class="collapsible-contact-box">
                    <button
                        type="button"
                        class="btn-collapse-toggle"
                        aria-expanded={showSocialFields}
                        on:click={() => (showSocialFields = !showSocialFields)}
                    >
                        <span>ข้อมูลติดต่อ & โซเชียล (เบอร์โทร, GitHub, LinkedIn, Line)</span>
                        <svg class:rotated={showSocialFields} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>

                    {#if showSocialFields}
                        <div class="form-grid contact-grid-body">
                            <div class="form-group">
                                <label for="phone">เบอร์โทรศัพท์</label>
                                <input type="tel" id="phone" bind:value={formData.phone} placeholder="081-234-5678" />
                            </div>
                            <div class="form-group">
                                <label for="line_id">Line ID / Telegram</label>
                                <input type="text" id="line_id" bind:value={formData.line_id} placeholder="@line_id" />
                            </div>
                            <div class="form-group">
                                <label for="github_url">GitHub Profile URL</label>
                                <input type="url" id="github_url" bind:value={formData.github_url} placeholder="https://github.com/username" />
                            </div>
                            <div class="form-group">
                                <label for="linkedin_url">LinkedIn Profile URL</label>
                                <input type="url" id="linkedin_url" bind:value={formData.linkedin_url} placeholder="https://linkedin.com/in/username" />
                            </div>
                        </div>
                    {/if}
                </div>

            {:else if activeModalTab === 'permissions'}
                <!-- TAB 2: PERMISSIONS -->
                <!-- QA Permission Presets & Custom Templates Bar -->
                <div class="presets-bar">
                    <div class="presets-row-top">
                        <span class="presets-label">ชุดสิทธิ์สำเร็จรูป (Presets & Templates):</span>
                        <button type="button" class="btn-save-tpl-toggle" on:click={() => (showSaveTemplateInput = !showSaveTemplateInput)}>
                            {showSaveTemplateInput ? 'ยกเลิก' : '+ บันทึกเป็น Template'}
                        </button>
                    </div>
                    <div class="presets-pills">
                        {#each availablePresets as preset}
                            <button
                                type="button"
                                class="btn-preset-pill"
                                class:active={isPresetActive(preset)}
                                aria-pressed={isPresetActive(preset)}
                                on:click={() => applyPermissionPreset(preset)}
                            >
                                {preset.label}
                            </button>
                        {/each}
                        {#each customTemplates as tpl (tpl.template_id)}
                            <span class="custom-tpl-wrap">
                                <button
                                    type="button"
                                    class="btn-preset-pill custom"
                                    on:click={() => applyCustomTemplate(tpl)}
                                    title={`Template องค์กร (${tpl.allowed_menus?.length || 0} เมนู)`}
                                >
                                    {tpl.name}
                                </button>
                                <button
                                    type="button"
                                    class="btn-del-tpl"
                                    aria-label={`ลบ Template ${tpl.name}`}
                                    title="ลบ Template นี้"
                                    on:click={() => handleDeleteCustomTemplate(tpl)}
                                >
                                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" width="10" height="10"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                                </button>
                            </span>
                        {/each}
                    </div>
                    {#if showSaveTemplateInput}
                        <div class="save-tpl-row">
                            <input
                                type="text"
                                class="tpl-name-input"
                                bind:value={newTemplateName}
                                placeholder="ตั้งชื่อ Template เช่น Junior Manual QA หรือ External UAT"
                                aria-label="ชื่อ Permission Template"
                            />
                            <button type="button" class="btn-pw-mini accent" disabled={isSavingTemplate} on:click={handleSaveCustomTemplate}>
                                {isSavingTemplate ? 'กำลังบันทึก...' : 'บันทึก Template'}
                            </button>
                        </div>
                    {/if}
                </div>

                <!-- Admin Menus Section (Shown when role === 'admin') -->
                {#if formData.role === 'admin'}
                    <div class="permission-section">
                        <div class="section-header-row">
                            <div>
                                <h3 class="section-title">เมนูผู้ดูแลระบบ (Admin & Governance)</h3>
                                <p class="section-subtitle">เครื่องมือจัดการระบบ โครงการ คลังความรู้ และสมาชิก</p>
                            </div>
                            <div class="section-actions">
                                <button type="button" class="btn-text-action" on:click={() => selectAllMenusForGroup(ADMIN_MENUS)}>เลือกทั้งหมด</button>
                                <span class="action-divider">|</span>
                                <button type="button" class="btn-text-action" on:click={() => clearMenusForGroup(ADMIN_MENUS)}>ล้างกลุ่มนี้</button>
                            </div>
                        </div>

                        <div class="menu-permission-grid">
                            {#each ADMIN_MENUS as menu}
                                <label class="perm-card" class:active={formData.allowed_menus.includes(menu.id)}>
                                    <input
                                        type="checkbox"
                                        checked={formData.allowed_menus.includes(menu.id)}
                                        on:change={() => toggleMenuPermission(menu.id)}
                                    />
                                    <div class="perm-card-body">
                                        <div class="perm-card-title">{menu.label}</div>
                                        <div class="perm-card-desc">{menu.desc}</div>
                                    </div>
                                </label>
                            {/each}
                        </div>
                    </div>

                    <div class="section-divider"></div>
                {/if}

                <!-- QA Workspace Menus (Available for BOTH User and Admin!) -->
                <div class="permission-section">
                    <div class="section-header-row">
                        <div>
                            <h3 class="section-title">
                                {formData.role === 'admin' ? 'เมนูปฏิบัติงาน QA เพิ่มเติม (QA Workspace Modules)' : 'สิทธิ์การเข้าถึงเมนู (QA Workspace Modules)'}
                            </h3>
                            <p class="section-subtitle">
                                {formData.role === 'admin'
                                    ? 'Admin สามารถเลือกเปิดเมนูฝั่ง QA เพิ่มเติมเพื่อใช้งานร่วมกับเมนูผู้ดูแลระบบได้'
                                    : 'เลือกเมนูและโมดูล QA ที่ผู้ใช้งานคนนี้สามารถเข้าถึงได้'}
                            </p>
                        </div>
                        <div class="section-actions">
                            <button type="button" class="btn-text-action" on:click={() => selectAllMenusForGroup(USER_MENUS)}>เลือกทั้งหมด</button>
                            <span class="action-divider">|</span>
                            <button type="button" class="btn-text-action" on:click={() => clearMenusForGroup(USER_MENUS)}>ล้างกลุ่มนี้</button>
                        </div>
                    </div>

                    <div class="menu-permission-grid">
                        {#each USER_MENUS as menu}
                            <label class="perm-card" class:active={formData.allowed_menus.includes(menu.id)}>
                                <input
                                    type="checkbox"
                                    checked={formData.allowed_menus.includes(menu.id)}
                                    on:change={() => toggleMenuPermission(menu.id)}
                                />
                                <div class="perm-card-body">
                                    <div class="perm-card-title">{menu.label}</div>
                                    <div class="perm-card-desc">{menu.desc}</div>
                                </div>
                            </label>
                        {/each}
                    </div>
                </div>

                <div class="section-divider"></div>

                <!-- Project Permissions Section -->
                <div class="permission-section">
                    <div class="section-header-row">
                        <div>
                            <h3 class="section-title">สิทธิ์การเข้าถึงโครงการ (Project Access)</h3>
                            <p class="section-subtitle">กำหนดขอบเขตโครงการที่ผู้ใช้งานสามารถมองเห็นและทำงานได้</p>
                        </div>
                    </div>

                    <div class="project-access-options">
                        <label class="access-radio-card" class:active={formData.allowed_projects.includes('all')}>
                            <input
                                type="radio"
                                name="projectAccess"
                                checked={formData.allowed_projects.includes('all')}
                                on:change={() => setProjectAccessMode('all')}
                            />
                            <div class="radio-content">
                                <div class="radio-title">เข้าถึงได้ทุกโครงการ (All Projects)</div>
                                <div class="radio-desc">เข้าถึงทุกโครงการในระบบได้ตามปกติ รวมถึงโครงการที่สร้างใหม่ในอนาคต</div>
                            </div>
                        </label>

                        <label class="access-radio-card" class:active={!formData.allowed_projects.includes('all')}>
                            <input
                                type="radio"
                                name="projectAccess"
                                checked={!formData.allowed_projects.includes('all')}
                                on:change={() => setProjectAccessMode('specific')}
                            />
                            <div class="radio-content">
                                <div class="radio-title">ระบุเฉพาะโครงการที่อนุญาต (Specific Projects Only)</div>
                                <div class="radio-desc">จำกัดให้เข้าถึงได้เฉพาะโครงการที่เลือกด้านล่างนี้เท่านั้น</div>
                            </div>
                        </label>
                    </div>

                    {#if !formData.allowed_projects.includes('all')}
                        <div class="specific-projects-container">
                            <div class="specific-projects-toolbar">
                                <div class="search-mini">
                                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                                    <input type="text" bind:value={modalProjectSearch} placeholder="ค้นหาโครงการ..." aria-label="ค้นหาโครงการ" />
                                </div>
                                <div class="section-actions">
                                    <button type="button" class="btn-text-action" on:click={selectAllProjects}>เลือกทั้งหมด</button>
                                    <span class="action-divider">|</span>
                                    <button type="button" class="btn-text-action" on:click={deselectAllProjects}>ล้างทั้งหมด</button>
                                </div>
                            </div>

                            {#if filteredModalProjects.length === 0}
                                <div class="empty-mini">ไม่พบโครงการที่ค้นหา</div>
                            {:else}
                                <div class="project-checkbox-list">
                                    {#each filteredModalProjects as proj (proj.id || proj.project_id || proj.project_code)}
                                        <label class="project-check-item" class:selected={isProjectSelected(proj)}>
                                            <input
                                                type="checkbox"
                                                checked={isProjectSelected(proj)}
                                                on:change={() => toggleProjectPermission(proj)}
                                            />
                                            <div class="proj-code-badge">{proj.project_code || 'PROJ'}</div>
                                            <div class="proj-info-col">
                                                <div class="proj-name-text">{proj.name || proj.project_name || 'Project'}</div>
                                                {#if proj.description}
                                                    <div class="proj-desc-text">{proj.description}</div>
                                                {/if}
                                            </div>
                                            <span class="proj-status-badge" class:active={proj.status === 'Active'}>
                                                {proj.status || 'Active'}
                                            </span>
                                        </label>
                                    {/each}
                                </div>
                            {/if}
                        </div>
                    {/if}
                </div>
            {:else if activeModalTab === 'security'}
                <!-- TAB 3: SECURITY & PERSONAL API TOKENS -->
                <div class="security-card">
                    <div class="security-card-info">
                        <h3 class="section-title">โควตา AI Token รายเดือน (Monthly Token Quota)</h3>
                        <p class="section-subtitle">
                            กำหนดเพดานการใช้ AI Token ต่อเดือนของสมาชิกคนนี้ (ใส่ 0 = ไม่จำกัด)
                        </p>
                    </div>
                    <div class="quota-control-col">
                        <input
                            type="number"
                            min="0"
                            step="50000"
                            class="quota-number-input"
                            bind:value={formData.monthly_token_quota}
                            aria-label="โควตา AI Token รายเดือน"
                        />
                        <div class="quota-presets-row">
                            <button type="button" class="btn-quota-chip" class:active={Number(formData.monthly_token_quota) === 0} on:click={() => (formData.monthly_token_quota = 0)}>ไม่จำกัด</button>
                            <button type="button" class="btn-quota-chip" class:active={Number(formData.monthly_token_quota) === 500000} on:click={() => (formData.monthly_token_quota = 500000)}>500K</button>
                            <button type="button" class="btn-quota-chip" class:active={Number(formData.monthly_token_quota) === 2000000} on:click={() => (formData.monthly_token_quota = 2000000)}>2M</button>
                            <button type="button" class="btn-quota-chip" class:active={Number(formData.monthly_token_quota) === 5000000} on:click={() => (formData.monthly_token_quota = 5000000)}>5M</button>
                        </div>
                    </div>
                </div>

                <div class="section-divider"></div>

                <div class="security-card">
                    <div class="security-card-info">
                        <h3 class="section-title">Session Control (บังคับออกจากระบบ)</h3>
                        <p class="section-subtitle">
                            ยกเลิก JWT Session ทั้งหมดของบัญชีนี้ทันทีโดยไม่ปิดการใช้งานบัญชี ผู้ใช้จะต้องเข้าสู่ระบบใหม่ทุกอุปกรณ์
                        </p>
                    </div>
                    <button
                        type="button"
                        class="btn-danger-outline"
                        disabled={isRevokingSessions || isSelfUser(formData)}
                        on:click={handleModalForceLogout}
                    >
                        {isRevokingSessions ? 'กำลังยกเลิก Session...' : 'บังคับออกจากระบบทุกอุปกรณ์'}
                    </button>
                </div>

                <div class="section-divider"></div>

                <div class="permission-section">
                    <div class="section-header-row">
                        <div>
                            <h3 class="section-title">Personal API Keys / Extension Tokens</h3>
                            <p class="section-subtitle">สร้าง Token แยกสำหรับเชื่อมต่อ Chrome Extension (Network Sniffer) หรือ MCP Server โดยไม่ต้องใช้รหัสผ่านหลัก</p>
                        </div>
                    </div>

                    <div class="token-create-row">
                        <input
                            type="text"
                            class="token-name-input"
                            bind:value={newTokenName}
                            placeholder="ชื่อ Token เช่น Chrome Extension - เครื่องออฟฟิศ"
                            aria-label="ชื่อ API Token"
                        />
                        <div class="token-scope-select">
                            <CustomSelect bind:value={newTokenScopes} options={tokenScopeOptions} minWidth="210px" />
                        </div>
                        <button type="button" class="btn-primary btn-create-token" on:click={handleCreateMemberToken} disabled={isCreatingToken}>
                            {isCreatingToken ? 'กำลังสร้าง...' : 'สร้าง Token'}
                        </button>
                    </div>

                    {#if newlyCreatedToken}
                        <div class="new-token-banner" role="alert">
                            <div class="new-token-header">
                                <strong>คัดลอก API Token นี้เก็บไว้ทันที (ระบบจะแสดงเพียงครั้งเดียว)</strong>
                                <button type="button" class="btn-pw-mini compact" on:click={() => copyText(newlyCreatedToken, 'คัดลอก API Token แล้ว')}>
                                    คัดลอก Token
                                </button>
                            </div>
                            <code class="new-token-code">{newlyCreatedToken}</code>
                        </div>
                    {/if}

                    {#if isLoadingTokens}
                        <div class="empty-mini">กำลังโหลดรายการ API Token...</div>
                    {:else if memberTokens.length === 0}
                        <div class="empty-mini">ยังไม่มี Personal API Token สำหรับผู้ใช้งานนี้</div>
                    {:else}
                        <div class="token-list">
                            {#each memberTokens as tk (tk.token_id)}
                                <div class="token-item" class:revoked={!tk.is_active}>
                                    <div class="token-item-main">
                                        <div class="token-item-top">
                                            <span class="token-item-name">{tk.name}</span>
                                            <code class="token-prefix-pill">{tk.token_prefix}••••••••</code>
                                            <span class="token-scope-tag">{tk.scopes}</span>
                                            {#if !tk.is_active}
                                                <span class="inactive-tag">ยกเลิกแล้ว</span>
                                            {/if}
                                        </div>
                                        <div class="token-item-meta">
                                            <span>สร้างเมื่อ {formatDate(tk.created_at)}</span>
                                            <span class="meta-sep">·</span>
                                            <span>ใช้งานล่าสุด: {tk.last_used_at ? formatDate(tk.last_used_at) : 'ยังไม่เคยใช้งาน'}</span>
                                        </div>
                                    </div>
                                    {#if tk.is_active}
                                        <button
                                            type="button"
                                            class="btn-revoke-token"
                                            disabled={revokingTokenIds.has(tk.token_id)}
                                            on:click={() => handleRevokeMemberToken(tk.token_id)}
                                        >
                                            {revokingTokenIds.has(tk.token_id) ? 'กำลังยกเลิก...' : 'ยกเลิก Token'}
                                        </button>
                                    {/if}
                                </div>
                            {/each}
                        </div>
                    {/if}
                </div>
            {/if}
        </div>

        <div class="modal-actions modal-actions-split">
            <div class="modal-footer-status">
                {#if isFormDirty}
                    <span class="dirty-dot" aria-hidden="true"></span>
                    <span>มีการแก้ไขที่ยังไม่ได้บันทึก</span>
                {/if}
            </div>
            <div class="modal-footer-btns">
                <button type="button" class="btn-secondary" on:click={requestCloseEditModal} disabled={isSaving}>ยกเลิก</button>
                <button type="button" class="btn-primary" on:click={handleSaveUser} disabled={isSaving}>
                    {isSaving ? 'กำลังบันทึก...' : 'บันทึกข้อมูลและสิทธิ์'}
                </button>
            </div>
        </div>
    </div>
</div>
{/if}

<!-- Post-Create Credential Handoff Modal -->
{#if handoffModal.show}
<div class="modal-backdrop" role="presentation" style="z-index: calc(var(--z-modal, 10000) + 50);" on:click={closeHandoffModal}>
    <div
        bind:this={handoffDialogEl}
        class="modal-content handoff-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="handoff-modal-title"
        tabindex="-1"
        on:keydown={trapFocus}
        on:click|stopPropagation
    >
        <div class="handoff-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="22" height="22">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <h2 id="handoff-modal-title" class="modal-title" style="text-align: center;">สร้างบัญชีผู้ใช้งานสำเร็จ</h2>
        <p class="handoff-subtitle">คัดลอกข้อมูลด้านล่างเพื่อส่งให้ผู้ใช้งาน (รหัสผ่านนี้จะแสดงเพียงครั้งเดียว)</p>

        <div class="handoff-summary-box">
            <div class="handoff-row"><span>ชื่อที่แสดง</span><strong>{handoffModal.display_name}</strong></div>
            <div class="handoff-row"><span>Username</span><code>{handoffModal.username}</code></div>
            <div class="handoff-row"><span>Email</span><code>{handoffModal.email}</code></div>
            <div class="handoff-row">
                <span>รหัสผ่านเริ่มต้น</span>
                <div class="handoff-pw-val">
                    <code>{handoffModal.password}</code>
                    <button type="button" class="btn-pw-mini compact" on:click={() => copyText(handoffModal.password, 'คัดลอกรหัสผ่านแล้ว')}>คัดลอก</button>
                </div>
            </div>
            <div class="handoff-row">
                <span>สิทธิ์ที่กำหนด</span>
                <strong>{handoffModal.role.toUpperCase()} · {handoffModal.menuCount} เมนู · {handoffModal.projectSummary}</strong>
            </div>
        </div>

        <div class="modal-actions handoff-actions">
            <button type="button" class="btn-secondary" on:click={closeHandoffModal}>ปิดหน้าต่าง</button>
            <button type="button" class="btn-primary" on:click={copyFullCredentials}>คัดลอกข้อมูลเข้าสู่ระบบทั้งหมด</button>
        </div>
    </div>
</div>
{/if}

<!-- Confirm Dialog Modal (with Focus Trap & Async Loading) -->
{#if confirmModal.show}
<div class="modal-backdrop" role="presentation" style="z-index: calc(var(--z-modal, 10000) + 100);" on:click={() => { if (!confirmModal.loading) closeConfirmModal(); }}>
    <div
        bind:this={confirmDialogEl}
        class="modal-content confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        tabindex="-1"
        on:keydown={trapFocus}
        on:click|stopPropagation
    >
        <h2 id="confirm-modal-title" class="modal-title confirm-title" class:is-primary={confirmModal.variant === 'primary'}>{confirmModal.title}</h2>
        <p class="confirm-message">{confirmModal.message}</p>
        <div class="modal-actions" style="justify-content: center; gap: 12px;">
            <button type="button" class="btn-secondary" on:click={closeConfirmModal} disabled={confirmModal.loading}>ยกเลิก</button>
            <button
                type="button"
                class="btn-primary"
                class:btn-confirm-danger-solid={confirmModal.variant !== 'primary'}
                on:click={confirmModal.action}
                disabled={confirmModal.loading}
            >
                {confirmModal.loading ? 'กำลังดำเนินการ...' : confirmModal.confirmText}
            </button>
        </div>
    </div>
</div>
{/if}

<MemberActivityDrawer
    open={activityDrawerOpen}
    user={activityDrawerUser}
    on:close={() => (activityDrawerOpen = false)}
    on:editQuota={(e) => { activityDrawerOpen = false; openEditModal(e.detail, 'security'); }}
/>

<!-- Bulk Operation Modal (Assign Projects / Apply Preset) -->
{#if bulkModal.show}
<div class="modal-backdrop" role="presentation" style="z-index: calc(var(--z-modal, 10000) + 60);" on:click={() => { if (!bulkModal.loading) bulkModal.show = false; }}>
    <div
        class="modal-content bulk-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="bulk-modal-title"
        tabindex="-1"
        on:keydown={trapFocus}
        on:click|stopPropagation
    >
        <div class="modal-header-bar">
            <div>
                <h2 id="bulk-modal-title" class="modal-title">
                    {bulkModal.mode === 'projects' ? `กำหนดสิทธิ์โครงการแบบกลุ่ม (${selectedUserIds.size} คน)` : `ใช้ชุดสิทธิ์ / Template แบบกลุ่ม (${selectedUserIds.size} คน)`}
                </h2>
                <p class="modal-subtitle">การเปลี่ยนแปลงจะมีผลทันทีและยกเลิก Session เดิมของสมาชิกที่ถูกปรับสิทธิ์</p>
            </div>
            <button type="button" class="close-btn" aria-label="ปิดหน้าต่าง" disabled={bulkModal.loading} on:click={() => (bulkModal.show = false)}>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>

        <div class="modal-scroll-area">
            {#if bulkModal.mode === 'projects'}
                <div class="bulk-op-radios">
                    <label class="access-radio-card" class:active={bulkModal.projectOp === 'add_projects'}>
                        <input type="radio" name="bulkProjOp" value="add_projects" bind:group={bulkModal.projectOp} />
                        <div class="radio-content">
                            <div class="radio-title">เพิ่มโครงการที่เลือกเข้าในสิทธิ์เดิม</div>
                            <div class="radio-desc">เหมาะสำหรับเปิด Sprint หรือ Project ใหม่ให้ทีม QA</div>
                        </div>
                    </label>
                    <label class="access-radio-card" class:active={bulkModal.projectOp === 'remove_projects'}>
                        <input type="radio" name="bulkProjOp" value="remove_projects" bind:group={bulkModal.projectOp} />
                        <div class="radio-content">
                            <div class="radio-title">ถอดโครงการที่เลือกออกจากสิทธิ์เดิม</div>
                            <div class="radio-desc">จำกัดการเข้าถึงเมื่อจบโครงการ</div>
                        </div>
                    </label>
                    <label class="access-radio-card" class:active={bulkModal.projectOp === 'set_projects_all'}>
                        <input type="radio" name="bulkProjOp" value="set_projects_all" bind:group={bulkModal.projectOp} />
                        <div class="radio-content">
                            <div class="radio-title">ให้สิทธิ์เข้าถึงทุกโครงการ (All Projects)</div>
                            <div class="radio-desc">ปลดล็อกให้เข้าถึงทุกโครงการในระบบ</div>
                        </div>
                    </label>
                </div>

                {#if bulkModal.projectOp !== 'set_projects_all'}
                    <div class="project-checkbox-list" style="margin-top: 12px;">
                        {#each allProjects as proj (proj.id || proj.project_id || proj.project_code)}
                            {@const pKey = String(proj.id || proj.project_id || proj.project_code)}
                            <label class="project-check-item" class:selected={bulkModal.selectedProjects.includes(pKey)}>
                                <input type="checkbox" checked={bulkModal.selectedProjects.includes(pKey)} on:change={() => toggleBulkProject(pKey)} />
                                <div class="proj-code-badge">{proj.project_code || 'PROJ'}</div>
                                <div class="proj-info-col">
                                    <div class="proj-name-text">{proj.name || proj.project_name || 'Project'}</div>
                                </div>
                            </label>
                        {/each}
                    </div>
                {/if}
            {:else}
                <div class="bulk-preset-list">
                    {#each QA_PERMISSION_PRESETS as preset}
                        <label class="access-radio-card" class:active={bulkModal.selectedPresetId === preset.id}>
                            <input type="radio" name="bulkPreset" value={preset.id} bind:group={bulkModal.selectedPresetId} />
                            <div class="radio-content">
                                <div class="radio-title">{preset.label}</div>
                                <div class="radio-desc">{preset.menus.length} เมนูมาตรฐาน</div>
                            </div>
                        </label>
                    {/each}
                    {#each customTemplates as tpl (tpl.template_id)}
                        <label class="access-radio-card" class:active={bulkModal.selectedPresetId === `tpl_${tpl.template_id}`}>
                            <input type="radio" name="bulkPreset" value={`tpl_${tpl.template_id}`} bind:group={bulkModal.selectedPresetId} />
                            <div class="radio-content">
                                <div class="radio-title">{tpl.name} <span class="self-tag">Template</span></div>
                                <div class="radio-desc">{tpl.allowed_menus?.length || 0} เมนู (บันทึกโดย {tpl.created_by || 'admin'})</div>
                            </div>
                        </label>
                    {/each}
                </div>
            {/if}
        </div>

        <div class="modal-actions">
            <button type="button" class="btn-secondary" disabled={bulkModal.loading} on:click={() => (bulkModal.show = false)}>ยกเลิก</button>
            <button type="button" class="btn-primary" disabled={bulkModal.loading} on:click={executeBulkModalAction}>
                {bulkModal.loading ? 'กำลังดำเนินการ...' : `ยืนยันปรับสิทธิ์ (${selectedUserIds.size} คน)`}
            </button>
        </div>
    </div>
</div>
{/if}

<style>
    .qa-member-container {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        overflow-x: hidden;
        padding: 28px 32px 44px;
        color: var(--text-main);
        font-family: var(--font-th);
        width: 100%;
        scrollbar-gutter: stable;
        scrollbar-width: thin;
        scrollbar-color: rgba(129, 140, 248, 0.45) rgba(255, 255, 255, 0.03);
    }

    .header-section {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 24px;
    }
    .header-actions-group {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }
    .btn-export-csv {
        display: inline-flex;
        align-items: center;
        gap: 7px;
    }

    /* Bulk Action Bar */
    .bulk-action-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        padding: 10px 14px;
        margin-bottom: 12px;
        border-radius: var(--radius-md);
        background: rgba(99, 102, 241, 0.14);
        border: 1px solid rgba(129, 140, 248, 0.42);
    }
    .bulk-bar-left { display: flex; align-items: center; gap: 10px; }
    .bulk-count-pill {
        font-size: 12.5px;
        font-weight: 700;
        color: var(--primary-soft-text-hover);
        font-variant-numeric: tabular-nums;
    }
    .bulk-bar-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .btn-bulk {
        min-height: 32px;
        padding: 0 12px;
        border-radius: var(--radius-sm);
        background: var(--bg2);
        border: 1px solid var(--glass-border-light);
        color: var(--text-main);
        font-size: 12px;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
    }
    .btn-bulk:hover { background: var(--surface-card-hover); border-color: var(--primary); }
    .btn-bulk.success { color: var(--success-soft-text); border-color: rgba(16, 185, 129, 0.36); }
    .btn-bulk.danger { color: var(--danger-soft-text); border-color: rgba(244, 63, 94, 0.38); }
    .btn-bulk.danger:hover { background: var(--danger-solid); border-color: var(--danger-solid); color: #ffffff; }

    .col-check { width: 42px; text-align: center; padding-left: 14px !important; padding-right: 6px !important; }
    .row-checkbox { width: 15px; height: 15px; accent-color: var(--primary); cursor: pointer; vertical-align: middle; }
    .data-table tbody tr.row-selected { background: rgba(99, 102, 241, 0.09); }

    .presets-row-top {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        flex-wrap: wrap;
    }
    .btn-save-tpl-toggle {
        background: none; border: none; color: var(--primary-soft-text);
        font-size: 11.5px; font-weight: 600; cursor: pointer; font-family: inherit; padding: 2px 4px;
    }
    .btn-save-tpl-toggle:hover { color: var(--primary-soft-text-hover); text-decoration: underline; }
    .custom-tpl-wrap { display: inline-flex; align-items: center; gap: 2px; }
    .btn-preset-pill.custom {
        background: rgba(16, 185, 129, 0.14);
        border-color: rgba(16, 185, 129, 0.36);
        color: var(--success-soft-text);
    }
    .btn-preset-pill.custom:hover { background: rgba(16, 185, 129, 0.28); color: #ffffff; }
    .btn-del-tpl {
        width: 22px; height: 22px; border-radius: 50%;
        background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3);
        color: var(--danger-soft-text);
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; padding: 0;
    }
    .btn-del-tpl:hover { background: var(--danger-solid); color: #ffffff; }
    .save-tpl-row {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
    }
    .tpl-name-input {
        flex: 1; min-height: 34px;
        background: var(--bg); border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-sm); padding: 6px 10px;
        color: var(--text-main); font-size: 12.5px; font-family: var(--font-th);
    }
    .bulk-dialog { max-width: 560px; }
    .bulk-op-radios, .bulk-preset-list { display: flex; flex-direction: column; gap: 8px; }

    .page-title {
        font-size: 24px;
        font-family: var(--font-en);
        font-weight: 700;
        margin: 0 0 4px;
        color: var(--text-main);
    }

    .page-subtitle {
        color: var(--text-muted);
        margin: 0;
        font-size: 14px;
    }

    .btn-primary {
        background: var(--gradient-main);
        color: #ffffff;
        border: 1px solid rgba(129, 140, 248, 0.35);
        padding: 9px 18px;
        min-height: 38px;
        border-radius: var(--radius-md);
        font-family: var(--font-th);
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 4px 14px rgba(99, 102, 241, 0.28);
        transition: transform 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;
    }
    .btn-primary:hover:not(:disabled) {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    }
    .btn-primary:disabled { opacity: 0.45; cursor: not-allowed; }
    .btn-primary svg { width: 16px; height: 16px; }

    /* Stats Grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin-bottom: 22px;
    }

    .stat-card {
        background: var(--bg2);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        padding: 16px 18px;
        display: flex;
        align-items: center;
        gap: 14px;
        text-align: left;
        cursor: pointer;
        font-family: inherit;
        transition: border-color 0.18s ease, background-color 0.18s ease, transform 0.18s ease;
    }
    .stat-card:hover {
        border-color: rgba(129, 140, 248, 0.42);
        background: var(--surface-card);
        transform: translateY(-1px);
    }
    .stat-card.active {
        border-color: var(--primary);
        background: rgba(99, 102, 241, 0.12);
    }

    .stat-icon {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .stat-icon svg { width: 22px; height: 22px; }
    .stat-icon.icon-primary { background: rgba(99, 102, 241, 0.14); color: var(--primary-soft-text); }
    .stat-icon.icon-secondary { background: rgba(168, 85, 247, 0.14); color: #c084fc; }
    .stat-icon.icon-accent { background: rgba(14, 165, 233, 0.14); color: #38bdf8; }
    .stat-icon.icon-success { background: rgba(16, 185, 129, 0.14); color: var(--success-soft-text); }

    .stat-value {
        font-family: var(--font-en);
        font-size: 22px;
        font-weight: 700;
        color: var(--text-main);
        line-height: 1.1;
        margin-bottom: 3px;
        font-variant-numeric: tabular-nums;
    }
    .stat-label { font-size: 12.5px; color: var(--text-muted); }

    /* Filters */
    .filter-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 10px;
    }

    .search-box {
        flex: 1;
        min-width: 220px;
        position: relative;
        display: flex;
        align-items: center;
    }
    .search-box svg {
        position: absolute;
        left: 14px;
        color: var(--text-dim);
        width: 15px; height: 15px;
        pointer-events: none;
    }
    .search-box input {
        width: 100%;
        min-height: 40px;
        background: var(--bg2);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-md);
        padding: 9px 36px 9px 38px;
        color: var(--text-main);
        font-family: var(--font-th);
        font-size: 13.5px;
    }
    .search-box input:focus-visible {
        border-color: var(--primary);
        outline: 2px solid rgba(99, 102, 241, 0.35);
        outline-offset: 1px;
    }
    .btn-clear-search {
        position: absolute;
        right: 8px;
        width: 26px;
        height: 26px;
        border-radius: 6px;
        border: none;
        background: rgba(255, 255, 255, 0.06);
        color: var(--text-muted);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: background-color 0.16s ease, color 0.16s ease;
    }
    .btn-clear-search:hover {
        background: rgba(255, 255, 255, 0.12);
        color: var(--text-main);
    }

    .btn-reset-filters {
        min-height: 40px;
        padding: 0 14px;
        border-radius: var(--radius-md);
        background: rgba(244, 63, 94, 0.12);
        border: 1px solid rgba(244, 63, 94, 0.34);
        color: var(--danger-soft-text);
        font-size: 12.5px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }

    .btn-refresh-users {
        min-width: 40px;
        min-height: 40px;
        border-radius: var(--radius-md);
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        color: var(--text-muted);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: color 0.16s ease, border-color 0.16s ease, background-color 0.16s ease;
    }
    .btn-refresh-users:hover:not(:disabled) {
        color: var(--text-main);
        border-color: var(--glass-border-light);
        background: var(--surface-card-hover);
    }

    .table-meta-bar {
        font-size: 12.5px;
        color: var(--text-dim);
        margin-bottom: 10px;
    }
    .table-meta-bar strong { color: var(--text-main); font-variant-numeric: tabular-nums; }

    /* Table */
    .table-container {
        background: var(--bg2);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.28);
        overflow-x: auto;
        scrollbar-width: thin;
        scrollbar-color: rgba(129, 140, 248, 0.3) transparent;
    }

    .data-table {
        width: 100%;
        border-collapse: collapse;
        text-align: left;
    }
    .data-table th, .data-table td {
        padding: 14px 18px;
        border-bottom: 1px solid var(--glass-border);
    }
    .data-table tbody tr:last-child td {
        border-bottom: none;
    }
    .data-table th {
        color: var(--text-muted);
        font-weight: 600;
        font-size: 12.5px;
        background: var(--bg);
        white-space: nowrap;
    }
    .data-table tbody tr:hover { background: var(--surface-card); }
    .data-table tbody tr.row-inactive { opacity: 0.62; }

    .user-cell { display: flex; align-items: center; gap: 12px; }
    .avatar {
        width: 38px; height: 38px;
        border-radius: 50%;
        background: rgba(99, 102, 241, 0.22);
        border: 1px solid rgba(99, 102, 241, 0.4);
        color: var(--primary-soft-text-hover);
        display: flex; align-items: center; justify-content: center;
        font-family: var(--font-en); font-weight: 700; font-size: 14px;
        flex-shrink: 0;
        overflow: hidden;
    }
    .avatar img { width: 100%; height: 100%; object-fit: cover; }

    .d-name {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        font-weight: 600;
        color: var(--text-main);
        margin-bottom: 3px;
        font-size: 13.5px;
    }
    .self-tag {
        padding: 1px 6px;
        border-radius: 999px;
        font-size: 10.5px;
        font-weight: 600;
        background: rgba(99, 102, 241, 0.2);
        border: 1px solid rgba(99, 102, 241, 0.35);
        color: var(--primary-soft-text);
    }
    .inactive-tag {
        padding: 1px 6px;
        border-radius: 999px;
        font-size: 10.5px;
        font-weight: 600;
        background: rgba(244, 63, 94, 0.15);
        border: 1px solid rgba(244, 63, 94, 0.35);
        color: var(--danger-soft-text);
    }
    .pw-reset-tag {
        padding: 1px 6px;
        border-radius: 999px;
        font-size: 10.5px;
        font-weight: 600;
        background: rgba(245, 158, 11, 0.16);
        border: 1px solid rgba(245, 158, 11, 0.38);
        color: var(--warning-soft-text);
    }

    .user-sub-meta {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 5px;
        font-size: 11.5px;
        color: var(--text-dim);
    }
    .dept-chip {
        color: var(--primary-soft-text);
        font-weight: 500;
    }
    .meta-sep { opacity: 0.5; }

    .username-text { font-weight: 600; font-family: var(--font-en); font-size: 13px; color: var(--text-main); }
    .email-text { font-size: 12px; color: var(--text-muted); font-family: var(--font-en); }
    .board-handle-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
    .handle-chip {
        font-size: 10.5px;
        font-family: var(--font-en);
        padding: 1px 6px;
        border-radius: 4px;
        font-weight: 600;
    }
    .handle-chip.trello {
        background: rgba(14, 165, 233, 0.14);
        border: 1px solid rgba(14, 165, 233, 0.32);
        color: #7dd3fc;
    }
    .handle-chip.github {
        background: rgba(168, 85, 247, 0.14);
        border: 1px solid rgba(168, 85, 247, 0.32);
        color: #d8b4fe;
    }

    .th-sort-btn {
        background: none;
        border: none;
        padding: 0;
        color: inherit;
        font: inherit;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }
    .th-sort-btn:hover { color: var(--text-main); }
    .th-sort-btn svg { opacity: 0.35; transition: transform 0.16s ease, opacity 0.16s ease; }
    .th-sort-btn.active { color: var(--primary-soft-text-hover); }
    .th-sort-btn.active svg { opacity: 1; }
    .th-sort-btn svg.desc { transform: rotate(180deg); }

    .role-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: var(--surface-card);
        border: 1px solid var(--glass-border-light);
        padding: 5px 11px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted);
        cursor: pointer;
        font-family: inherit;
        transition: background-color 0.16s ease, border-color 0.16s ease;
    }
    .role-badge:hover:not(:disabled) { background: var(--surface-card-hover); color: var(--text-main); }
    .role-badge:disabled { opacity: 0.65; cursor: not-allowed; }
    .role-badge svg { width: 14px; height: 14px; }
    .role-badge.admin {
        background: rgba(168, 85, 247, 0.16);
        color: #d8b4fe;
        border-color: rgba(168, 85, 247, 0.35);
    }

    .permission-summary-badges { display: flex; flex-wrap: wrap; gap: 6px; }
    .perm-badge {
        font-size: 11.5px;
        padding: 4px 9px;
        border-radius: 6px;
        font-weight: 600;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        cursor: pointer;
        font-family: inherit;
        transition: background-color 0.16s ease, border-color 0.16s ease;
    }
    .perm-badge.menu-perm {
        background: rgba(168, 85, 247, 0.14);
        color: #d8b4fe;
        border: 1px solid rgba(168, 85, 247, 0.32);
    }
    .perm-badge.menu-perm:hover { background: rgba(168, 85, 247, 0.26); }
    .perm-badge.project-perm {
        background: rgba(59, 130, 246, 0.14);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.32);
    }
    .perm-badge.project-perm:hover { background: rgba(59, 130, 246, 0.26); }
    .perm-badge.token-perm {
        background: rgba(16, 185, 129, 0.14);
        color: var(--success-soft-text);
        border: 1px solid rgba(16, 185, 129, 0.32);
    }
    .perm-badge.token-perm:hover { background: rgba(16, 185, 129, 0.24); }
    .perm-badge.usage-perm {
        background: rgba(99, 102, 241, 0.12);
        color: var(--primary-soft-text-hover);
        border: 1px solid rgba(99, 102, 241, 0.3);
        font-family: var(--font-en);
        font-variant-numeric: tabular-nums;
    }
    .perm-badge.usage-perm.warn {
        background: rgba(245, 158, 11, 0.16);
        color: var(--warning-soft-text);
        border-color: rgba(245, 158, 11, 0.38);
    }
    .perm-badge.usage-perm.danger {
        background: rgba(244, 63, 94, 0.16);
        color: var(--danger-soft-text);
        border-color: rgba(244, 63, 94, 0.4);
    }

    /* Toggle Switch with WCAG Focus Visible */
    .toggle-switch {
        position: relative;
        display: inline-block;
        width: 44px;
        height: 24px;
    }
    .toggle-switch input { opacity: 0; width: 0; height: 0; }
    .slider {
        position: absolute;
        cursor: pointer;
        inset: 0;
        background-color: rgba(255, 255, 255, 0.14);
        transition: background-color 0.2s ease;
        border-radius: 999px;
    }
    .slider::before {
        position: absolute;
        content: "";
        height: 18px;
        width: 18px;
        left: 3px;
        bottom: 3px;
        background-color: #ffffff;
        transition: transform 0.2s ease;
        border-radius: 50%;
    }
    .toggle-switch input:checked + .slider { background-color: var(--success); }
    .toggle-switch input:checked + .slider::before { transform: translateX(20px); }
    .toggle-switch input:focus-visible + .slider {
        outline: 2px solid var(--primary-soft-text);
        outline-offset: 2px;
    }
    .toggle-switch.disabled { opacity: 0.45; cursor: not-allowed; }
    .toggle-switch.disabled .slider { cursor: not-allowed; }

    .last-login { font-size: 13px; margin-bottom: 2px; font-variant-numeric: tabular-nums; }
    .login-count { font-size: 11.5px; color: var(--text-dim); font-variant-numeric: tabular-nums; }

    .action-buttons { display: flex; justify-content: flex-end; gap: 6px; }
    .icon-btn {
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        width: 34px; height: 34px;
        border-radius: 8px;
        color: var(--text-muted);
        cursor: pointer;
        display: inline-flex; align-items: center; justify-content: center;
        transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
    }
    .icon-btn svg { width: 15px; height: 15px; }
    .icon-btn:hover:not(:disabled) { background: var(--surface-card-hover); color: var(--text-main); }
    .icon-btn:disabled { opacity: 0.3; cursor: not-allowed; }
    .icon-btn.activity:hover:not(:disabled) {
        background: rgba(99, 102, 241, 0.16);
        color: var(--primary-soft-text-hover);
        border-color: rgba(129, 140, 248, 0.4);
    }
    .icon-btn.revoke:hover:not(:disabled) {
        background: rgba(245, 158, 11, 0.16);
        color: var(--warning-soft-text);
        border-color: rgba(245, 158, 11, 0.38);
    }
    .icon-btn.delete:hover:not(:disabled) {
        background: rgba(244, 63, 94, 0.16);
        color: var(--danger-soft-text);
        border-color: rgba(244, 63, 94, 0.38);
    }

    /* Loading Table Skeleton */
    .skeleton-table {
        display: flex;
        flex-direction: column;
    }
    .skeleton-row {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 15px 18px;
        border-bottom: 1px solid var(--glass-border);
    }
    .skeleton-row:last-child { border-bottom: none; }
    .skeleton-avatar {
        width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
        background: rgba(255, 255, 255, 0.06);
        animation: shimmer 1.4s ease-in-out infinite;
    }
    .skeleton-col {
        display: flex; flex-direction: column; gap: 7px; flex: 1; min-width: 100px;
    }
    .skeleton-col.wide { flex: 1.4; }
    .skeleton-bar {
        height: 12px; border-radius: 6px;
        background: rgba(255, 255, 255, 0.07);
        animation: shimmer 1.4s ease-in-out infinite;
    }
    .skeleton-bar.sm { height: 9px; opacity: 0.7; }
    .skeleton-bar.w-60 { width: 60%; }
    .skeleton-bar.w-40 { width: 40%; }
    .skeleton-bar.w-70 { width: 70%; }
    .skeleton-bar.w-50 { width: 50%; }
    .skeleton-pill {
        width: 72px; height: 26px; border-radius: 999px; flex-shrink: 0;
        background: rgba(255, 255, 255, 0.06);
        animation: shimmer 1.4s ease-in-out infinite;
    }
    .skeleton-pill.wide { width: 120px; border-radius: 6px; }
    .skeleton-toggle {
        width: 44px; height: 24px; border-radius: 999px; flex-shrink: 0;
        background: rgba(255, 255, 255, 0.06);
        animation: shimmer 1.4s ease-in-out infinite;
    }
    @keyframes shimmer {
        0%, 100% { opacity: 0.45; }
        50% { opacity: 0.9; }
    }

    .empty-state {
        padding: 48px 24px;
        text-align: center;
        color: var(--text-muted);
        display: flex; flex-direction: column; align-items: center; gap: 12px;
    }
    .empty-state svg { width: 44px; height: 44px; color: var(--text-dim); }
    .spinning { animation: spin 0.9s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Modals (Spectra Obsidian + Proper --z-modal) */
    .modal-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(5, 5, 10, 0.78);
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: var(--z-modal, 10000);
        padding: 16px;
    }

    .modal-content {
        width: 100%;
        max-width: 460px;
        background: var(--bg2);
        border: 1px solid rgba(168, 85, 247, 0.26);
        border-radius: var(--radius-lg);
        box-shadow: 0 28px 72px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(255, 255, 255, 0.06);
        max-height: calc(100dvh - 32px);
        display: flex;
        flex-direction: column;
        overflow: hidden;
        outline: none;
    }
    .modal-content.modal-large { max-width: 720px; }
    .modal-content.confirm-dialog { padding: 26px 28px; text-align: center; }
    .modal-content.handoff-dialog { max-width: 500px; padding: 26px 26px 20px; }

    .modal-header-bar {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        padding: 18px 22px 14px;
        background: var(--bg);
        border-bottom: 1px solid var(--glass-border);
    }
    .modal-title { font-size: 18px; font-weight: 700; margin: 0; color: var(--text-main); }
    .modal-subtitle { margin: 3px 0 0; font-size: 12.5px; color: var(--text-muted); }

    .close-btn {
        width: 34px; height: 34px;
        border-radius: var(--radius-sm);
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid var(--glass-border);
        color: var(--text-muted);
        display: inline-flex; align-items: center; justify-content: center;
        cursor: pointer; flex-shrink: 0;
    }
    .close-btn:hover:not(:disabled) {
        color: var(--text-main);
        background: rgba(244, 63, 94, 0.16);
        border-color: rgba(244, 63, 94, 0.38);
    }
    .close-btn svg { width: 16px; height: 16px; }

    .discard-warning-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 10px 22px;
        background: rgba(245, 158, 11, 0.14);
        border-bottom: 1px solid rgba(245, 158, 11, 0.35);
        color: var(--warning-soft-text);
        font-size: 12.5px;
        flex-wrap: wrap;
    }
    .discard-actions { display: flex; gap: 8px; }
    .btn-mini-ghost, .btn-mini-danger {
        min-height: 28px; padding: 4px 10px; border-radius: 6px;
        font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit;
    }
    .btn-mini-ghost { background: var(--surface-card); border: 1px solid var(--glass-border-light); color: var(--text-main); }
    .btn-mini-danger { background: var(--danger-solid); border: 1px solid var(--danger-solid); color: #ffffff; }

    .modal-tab-bar {
        display: flex;
        gap: 8px;
        padding: 10px 22px;
        background: var(--bg);
        border-bottom: 1px solid var(--glass-border);
    }
    .modal-tab-btn {
        background: transparent;
        border: 1px solid transparent;
        color: var(--text-muted);
        padding: 7px 14px;
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        display: inline-flex; align-items: center; gap: 7px;
        border-radius: var(--radius-sm);
        font-family: inherit;
    }
    .modal-tab-btn:hover { color: var(--text-main); background: rgba(255, 255, 255, 0.04); }
    .modal-tab-btn.active {
        color: var(--text-main);
        background: rgba(99, 102, 241, 0.18);
        border-color: rgba(129, 140, 248, 0.45);
    }
    .tab-badge {
        font-size: 11px;
        background: rgba(99, 102, 241, 0.28);
        color: var(--primary-soft-text-hover);
        padding: 1px 7px;
        border-radius: 999px;
        font-variant-numeric: tabular-nums;
    }

    .modal-scroll-area {
        flex: 1;
        min-height: 0;
        overflow-y: auto;
        overscroll-behavior: contain;
        padding: 18px 22px;
        scrollbar-width: thin;
        scrollbar-color: rgba(129, 140, 248, 0.3) transparent;
    }

    /* Compact Horizontal Avatar Strip */
    .avatar-compact-strip {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 14px;
        border-radius: var(--radius-md);
        background: var(--surface-card);
        border: 1px dashed var(--glass-border-light);
        margin-bottom: 18px;
        flex-wrap: wrap;
    }
    .avatar-compact-strip.drag-over {
        border-color: var(--primary);
        background: rgba(99, 102, 241, 0.1);
    }
    .avatar-compact-circle {
        width: 58px; height: 58px;
        border-radius: 50%;
        background: rgba(99, 102, 241, 0.22);
        border: 2px solid rgba(168, 85, 247, 0.55);
        overflow: hidden;
        display: flex; align-items: center; justify-content: center;
        cursor: pointer;
        padding: 0;
        flex-shrink: 0;
    }
    .avatar-compact-circle img { width: 100%; height: 100%; object-fit: cover; }
    .avatar-fallback-sm { font-size: 22px; font-weight: 700; color: var(--text-main); font-family: var(--font-en); }
    .avatar-strip-meta { flex: 1; min-width: 180px; }
    .avatar-strip-title { font-size: 13px; font-weight: 600; color: var(--text-main); }
    .avatar-strip-hint { font-size: 11.5px; color: var(--text-dim); margin-top: 2px; }
    .avatar-strip-actions { display: flex; gap: 8px; }

    .btn-avatar-action {
        min-height: 32px;
        padding: 5px 12px;
        border-radius: var(--radius-sm);
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .btn-avatar-action.upload {
        background: rgba(99, 102, 241, 0.16);
        border: 1px solid rgba(99, 102, 241, 0.36);
        color: var(--primary-soft-text-hover);
    }
    .btn-avatar-action.remove {
        background: rgba(244, 63, 94, 0.12);
        border: 1px solid rgba(244, 63, 94, 0.32);
        color: var(--danger-soft-text);
    }

    .form-section-heading {
        font-size: 12.5px;
        font-weight: 700;
        color: var(--primary-soft-text);
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin-bottom: 12px;
    }

    .form-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 14px;
    }
    .form-grid .full-width { grid-column: 1 / -1; }

    .form-group { display: flex; flex-direction: column; gap: 6px; }
    .form-group label { font-size: 12.5px; font-weight: 600; color: var(--text-muted); }
    .req { color: var(--danger-soft-text); }

    .form-group input {
        width: 100%;
        min-height: 38px;
        background: var(--bg);
        border: 1px solid var(--glass-border-light);
        padding: 8px 12px;
        border-radius: var(--radius-sm);
        color: var(--text-main);
        font-family: var(--font-th);
        font-size: 13px;
    }
    .form-group input:focus-visible {
        border-color: var(--primary);
        outline: 2px solid rgba(99, 102, 241, 0.35);
        outline-offset: 1px;
    }
    .form-group input:disabled { opacity: 0.55; cursor: not-allowed; }
    .form-group input.is-invalid { border-color: var(--danger); }
    .field-err { font-size: 11.5px; color: var(--danger-soft-text); }

    .password-input-row {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
    }
    .password-input-row input { flex: 1; min-width: 180px; }

    .btn-pw-mini {
        min-height: 38px;
        padding: 0 11px;
        border-radius: var(--radius-sm);
        background: var(--surface-card);
        border: 1px solid var(--glass-border-light);
        color: var(--text-muted);
        font-size: 12px;
        font-weight: 600;
        font-family: var(--font-th);
        cursor: pointer;
        white-space: nowrap;
    }
    .btn-pw-mini.compact {
        min-height: 28px;
        padding: 0 10px;
        font-size: 11.5px;
    }
    .btn-pw-mini:hover { color: var(--text-main); background: var(--surface-card-hover); }
    .btn-pw-mini.accent {
        background: rgba(99, 102, 241, 0.16);
        border-color: rgba(99, 102, 241, 0.38);
        color: var(--primary-soft-text);
    }

    .pw-strength-row {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 2px;
    }
    .pw-strength-track {
        width: 88px;
        height: 4px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.09);
        overflow: hidden;
        flex-shrink: 0;
    }
    .pw-strength-fill {
        height: 100%;
        border-radius: 999px;
        transition: width 0.2s ease, background-color 0.2s ease;
    }
    .pw-strength-fill.weak { background: var(--danger); }
    .pw-strength-fill.medium { background: var(--warning); }
    .pw-strength-fill.strong { background: var(--success); }
    .pw-strength-label { font-size: 11px; font-weight: 500; }
    .pw-strength-label.weak { color: var(--danger-soft-text); }
    .pw-strength-label.medium { color: var(--warning-soft-text); }
    .pw-strength-label.strong { color: var(--success-soft-text); }

    .must-change-pw-check {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
        font-size: 12px;
        color: var(--text-muted);
        cursor: pointer;
    }
    .must-change-pw-check input {
        width: auto;
        min-height: auto;
        margin: 0;
        accent-color: var(--primary);
        cursor: pointer;
    }

    /* Security Tab & Personal API Tokens */
    .security-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        flex-wrap: wrap;
        padding: 14px 16px;
        border-radius: var(--radius-md);
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
    }
    .security-card-info { flex: 1; min-width: 220px; }
    .quota-control-col { display: flex; flex-direction: column; gap: 6px; min-width: 210px; }
    .quota-number-input {
        min-height: 36px;
        background: var(--bg);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-sm);
        padding: 6px 10px;
        color: var(--text-main);
        font-family: var(--font-en);
        font-size: 13px;
        font-variant-numeric: tabular-nums;
    }
    .quota-number-input:focus-visible { border-color: var(--primary); outline: 2px solid rgba(99, 102, 241, 0.35); }
    .quota-presets-row { display: flex; gap: 5px; flex-wrap: wrap; }
    .btn-quota-chip {
        min-height: 24px; padding: 2px 8px; border-radius: 999px;
        background: var(--bg); border: 1px solid var(--glass-border);
        color: var(--text-muted); font-size: 11px; font-weight: 600; cursor: pointer; font-family: inherit;
    }
    .btn-quota-chip.active {
        background: rgba(99, 102, 241, 0.24); border-color: rgba(129, 140, 248, 0.5); color: var(--text-main);
    }
    .btn-danger-outline {
        min-height: 36px;
        padding: 0 14px;
        border-radius: var(--radius-sm);
        background: rgba(244, 63, 94, 0.12);
        border: 1px solid rgba(244, 63, 94, 0.38);
        color: var(--danger-soft-text);
        font-size: 12.5px;
        font-weight: 600;
        font-family: inherit;
        cursor: pointer;
        white-space: nowrap;
        transition: background-color 0.16s ease, color 0.16s ease;
    }
    .btn-danger-outline:hover:not(:disabled) {
        background: var(--danger-solid);
        border-color: var(--danger-solid);
        color: #ffffff;
    }
    .btn-danger-outline:disabled { opacity: 0.45; cursor: not-allowed; }

    .token-create-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 12px;
    }
    .token-name-input {
        flex: 1;
        min-width: 190px;
        min-height: 38px;
        background: var(--bg);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-sm);
        padding: 8px 12px;
        color: var(--text-main);
        font-size: 13px;
        font-family: var(--font-th);
    }
    .token-name-input:focus-visible {
        border-color: var(--primary);
        outline: 2px solid rgba(99, 102, 241, 0.35);
    }
    .btn-create-token { min-height: 38px; padding: 0 14px; font-size: 13px; }

    .new-token-banner {
        padding: 12px 14px;
        border-radius: var(--radius-md);
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.38);
        margin-bottom: 12px;
    }
    .new-token-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 8px;
        font-size: 12px;
        color: var(--success-soft-text);
    }
    .new-token-code {
        display: block;
        width: 100%;
        padding: 8px 10px;
        border-radius: 6px;
        background: var(--bg);
        border: 1px solid var(--glass-border);
        color: var(--text-main);
        font-family: monospace;
        font-size: 12px;
        word-break: break-all;
    }

    .token-list { display: flex; flex-direction: column; gap: 8px; }
    .token-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        padding: 10px 12px;
        border-radius: var(--radius-sm);
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
    }
    .token-item.revoked { opacity: 0.55; }
    .token-item-main { flex: 1; min-width: 200px; }
    .token-item-top { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin-bottom: 4px; }
    .token-item-name { font-size: 13px; font-weight: 600; color: var(--text-main); }
    .token-prefix-pill {
        font-family: monospace;
        font-size: 11px;
        background: var(--bg);
        border: 1px solid var(--glass-border);
        padding: 1px 6px;
        border-radius: 4px;
        color: var(--primary-soft-text);
    }
    .token-scope-tag {
        font-size: 10.5px;
        padding: 1px 6px;
        border-radius: 999px;
        background: rgba(99, 102, 241, 0.16);
        color: var(--primary-soft-text-hover);
        font-family: var(--font-en);
    }
    .token-item-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; font-size: 11.5px; color: var(--text-dim); }
    .btn-revoke-token {
        min-height: 30px;
        padding: 0 11px;
        border-radius: 6px;
        background: rgba(244, 63, 94, 0.12);
        border: 1px solid rgba(244, 63, 94, 0.34);
        color: var(--danger-soft-text);
        font-size: 11.5px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .btn-revoke-token:hover:not(:disabled) {
        background: var(--danger-solid);
        border-color: var(--danger-solid);
        color: #ffffff;
    }
    .btn-revoke-token:disabled { opacity: 0.45; cursor: not-allowed; }

    .role-locked-notice {
        padding: 9px 12px;
        border-radius: var(--radius-sm);
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        color: var(--text-muted);
        font-size: 12.5px;
    }

    .inline-info-banner {
        margin-top: 12px;
        padding: 10px 12px;
        border-radius: var(--radius-sm);
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.32);
        color: var(--primary-soft-text-hover);
        font-size: 12.5px;
    }

    .collapsible-contact-box {
        margin-top: 18px;
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        background: var(--surface-card);
        overflow: hidden;
    }
    .btn-collapse-toggle {
        width: 100%;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 11px 14px;
        background: transparent;
        border: none;
        color: var(--text-main);
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .btn-collapse-toggle svg { transition: transform 0.2s ease; }
    .btn-collapse-toggle svg.rotated { transform: rotate(180deg); }
    .contact-grid-body { padding: 0 14px 14px; }

    /* Presets Bar */
    .presets-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        padding: 10px 12px;
        border-radius: var(--radius-md);
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        margin-bottom: 16px;
    }
    .presets-label { font-size: 12px; font-weight: 600; color: var(--text-muted); }
    .presets-pills { display: flex; flex-wrap: wrap; gap: 6px; }
    .btn-preset-pill {
        min-height: 28px;
        padding: 4px 11px;
        border-radius: 999px;
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.32);
        color: var(--primary-soft-text-hover);
        font-size: 11.5px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
        transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
    }
    .btn-preset-pill:hover { background: rgba(99, 102, 241, 0.24); color: #ffffff; }
    .btn-preset-pill.active {
        background: var(--primary);
        border-color: var(--primary-soft-text);
        color: #ffffff;
    }

    /* Permissions */
    .permission-section { margin-bottom: 16px; }
    .section-header-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 10px;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }
    .section-title { font-size: 14.5px; font-weight: 700; color: var(--text-main); margin: 0 0 3px; }
    .section-subtitle { font-size: 12px; color: var(--text-muted); margin: 0; }
    .section-actions { display: flex; align-items: center; gap: 6px; }
    .btn-text-action {
        background: none; border: none; color: var(--primary-soft-text);
        font-size: 12px; font-weight: 600; cursor: pointer; padding: 2px 4px; font-family: inherit;
    }
    .btn-text-action:hover { color: var(--primary-soft-text-hover); text-decoration: underline; }
    .action-divider { color: var(--glass-border-light); font-size: 12px; }
    .section-divider { height: 1px; background: var(--glass-border); margin: 16px 0; }

    .menu-permission-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(270px, 1fr));
        gap: 8px;
    }
    .perm-card {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 10px 12px;
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-sm);
        cursor: pointer;
        transition: background-color 0.16s ease, border-color 0.16s ease;
    }
    .perm-card:hover { background: var(--surface-card-hover); border-color: rgba(129, 140, 248, 0.35); }
    .perm-card.active { background: rgba(99, 102, 241, 0.14); border-color: rgba(129, 140, 248, 0.45); }
    .perm-card input { margin-top: 3px; cursor: pointer; accent-color: var(--primary); }
    .perm-card-body { flex: 1; min-width: 0; }
    .perm-card-title { font-size: 13px; font-weight: 600; color: var(--text-main); margin-bottom: 2px; }
    .perm-card-desc { font-size: 11.5px; color: var(--text-dim); line-height: 1.35; }

    .project-access-options { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
    .access-radio-card {
        display: flex; align-items: flex-start; gap: 10px;
        padding: 11px 14px;
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-sm);
        cursor: pointer;
    }
    .access-radio-card.active { background: rgba(59, 130, 246, 0.12); border-color: rgba(59, 130, 246, 0.42); }
    .access-radio-card input { margin-top: 3px; cursor: pointer; accent-color: var(--primary); }
    .radio-title { font-size: 13px; font-weight: 600; color: var(--text-main); margin-bottom: 2px; }
    .radio-desc { font-size: 11.5px; color: var(--text-dim); }

    .specific-projects-container {
        background: var(--bg);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 12px;
    }
    .specific-projects-toolbar {
        display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;
    }
    .search-mini { position: relative; flex: 1; min-width: 180px; max-width: 260px; display: flex; align-items: center; }
    .search-mini svg { position: absolute; left: 10px; color: var(--text-dim); pointer-events: none; }
    .search-mini input {
        width: 100%; background: var(--surface-card); border: 1px solid var(--glass-border-light);
        border-radius: 6px; padding: 6px 10px 6px 30px; font-size: 12px; color: var(--text-main);
    }
    .search-mini input:focus-visible { border-color: var(--primary); outline: 2px solid rgba(99, 102, 241, 0.35); }

    .project-checkbox-list {
        max-height: 200px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 6px;
        scrollbar-width: thin;
        scrollbar-color: rgba(129, 140, 248, 0.3) transparent;
    }
    .project-check-item {
        display: flex; align-items: center; gap: 10px; padding: 8px 10px;
        background: var(--surface-card); border: 1px solid var(--glass-border);
        border-radius: 8px; cursor: pointer;
    }
    .project-check-item.selected { background: rgba(59, 130, 246, 0.12); border-color: rgba(59, 130, 246, 0.36); }
    .project-check-item input { cursor: pointer; accent-color: var(--primary); }
    .proj-code-badge {
        font-family: monospace; font-size: 11px; font-weight: 700;
        background: rgba(99, 102, 241, 0.2); color: var(--primary-soft-text);
        padding: 2px 6px; border-radius: 4px; white-space: nowrap;
    }
    .proj-info-col { flex: 1; min-width: 0; }
    .proj-name-text { font-size: 12.5px; font-weight: 600; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .proj-desc-text { font-size: 11.5px; color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .proj-status-badge { font-size: 10.5px; padding: 2px 6px; border-radius: 4px; background: rgba(255, 255, 255, 0.06); color: var(--text-dim); }
    .proj-status-badge.active { background: rgba(16, 185, 129, 0.15); color: var(--success-soft-text); }
    .empty-mini { padding: 18px; text-align: center; color: var(--text-dim); font-size: 12.5px; }

    .modal-actions {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 10px;
        padding: 14px 22px;
        background: var(--bg);
        border-top: 1px solid var(--glass-border);
    }
    .modal-actions-split {
        justify-content: space-between;
        flex-wrap: wrap;
    }
    .modal-footer-status {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        font-size: 12px;
        color: var(--warning-soft-text);
    }
    .dirty-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--warning);
    }
    .modal-footer-btns {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .handoff-actions {
        justify-content: space-between;
        flex-wrap: wrap;
    }
    .confirm-dialog .modal-actions,
    .handoff-dialog .modal-actions {
        background: transparent;
        padding: 16px 0 0;
        margin-top: 12px;
    }

    .btn-secondary {
        background: var(--surface-card);
        border: 1px solid var(--glass-border-light);
        color: var(--text-main);
        padding: 9px 18px;
        min-height: 38px;
        border-radius: var(--radius-md);
        font-family: var(--font-th);
        font-size: 13.5px;
        font-weight: 500;
        cursor: pointer;
    }
    .btn-secondary:hover:not(:disabled) { background: var(--surface-card-hover); }
    .btn-secondary:disabled { opacity: 0.45; cursor: not-allowed; }

    .confirm-title { color: var(--danger-soft-text); margin-bottom: 10px; }
    .confirm-title.is-primary { color: var(--primary-soft-text-hover); }
    .confirm-message { color: var(--text-main); font-size: 14px; line-height: 1.55; margin: 0 0 18px; }
    .btn-confirm-danger-solid {
        background: var(--danger-solid);
        border-color: var(--danger-solid);
        box-shadow: 0 4px 14px rgba(190, 18, 60, 0.38);
    }
    .btn-confirm-danger-solid:hover:not(:disabled) {
        background: var(--danger-solid-hover);
        border-color: var(--danger-solid-hover);
    }

    /* Unified Keyboard Focus Rings (WCAG 2.2) */
    .qa-member-container button:focus-visible,
    .modal-content button:focus-visible {
        outline: 2px solid var(--primary-soft-text);
        outline-offset: 2px;
    }
    .perm-card:focus-within,
    .access-radio-card:focus-within,
    .project-check-item:focus-within {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.28);
    }

    /* Handoff Modal */
    .handoff-badge {
        width: 48px; height: 48px; border-radius: 50%; margin: 0 auto 12px;
        background: rgba(16, 185, 129, 0.16); border: 1px solid rgba(16, 185, 129, 0.4);
        color: var(--success-soft-text);
        display: flex; align-items: center; justify-content: center;
    }
    .handoff-subtitle { text-align: center; font-size: 12.5px; color: var(--text-muted); margin: 4px 0 16px; }
    .handoff-summary-box {
        background: var(--bg); border: 1px solid var(--glass-border);
        border-radius: var(--radius-md); padding: 12px 14px;
        display: flex; flex-direction: column; gap: 10px;
    }
    .handoff-row {
        display: flex; align-items: center; justify-content: space-between; gap: 10px;
        font-size: 13px; flex-wrap: wrap;
    }
    .handoff-row span { color: var(--text-dim); }
    .handoff-row code {
        background: var(--surface-card); padding: 2px 8px; border-radius: 5px;
        font-family: var(--font-en); color: var(--primary-soft-text-hover);
    }
    .handoff-pw-val { display: inline-flex; align-items: center; gap: 6px; }

    /* Responsive Breakpoints */
    @media (max-width: 900px) {
        .qa-member-container { padding: 20px; }
        .form-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 640px) {
        .qa-member-container { padding: 14px; }
        .filter-bar { flex-direction: column; align-items: stretch; }
        .role-filter { width: 100%; }
        .modal-header-bar, .modal-tab-bar, .modal-scroll-area, .modal-actions { padding-left: 14px; padding-right: 14px; }
        .modal-actions-split { justify-content: flex-end; }
    }
    @media (prefers-reduced-motion: reduce) {
        .spinning, .skeleton-avatar, .skeleton-bar, .skeleton-pill, .skeleton-toggle { animation: none; }
        .stat-card:hover, .btn-primary:hover { transform: none; }
        .slider, .slider::before, .btn-collapse-toggle svg, .pw-strength-fill { transition: none; }
    }
</style>
