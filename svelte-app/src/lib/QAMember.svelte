<script>
    import { onMount } from 'svelte';
    import { toast } from './toastStore.js';
    import { authUser } from './authStore.js';
    import CustomSelect from './CustomSelect.svelte';

    let users = [];
    let allProjects = [];
    let isLoading = true;
    let searchQuery = '';
    let roleFilter = 'all';

    const USER_MENUS = [
        { id: 'qa_consult', label: 'QA Consult', icon: '💬', desc: 'ให้คำปรึกษาและวิเคราะห์เอกสาร QA' },
        { id: 'qa_performance', label: 'QA Performance', icon: '⚡', desc: 'ทดสอบประสิทธิภาพ & k6 Script' },
        { id: 'qa_research', label: 'QA Research', icon: '🔍', desc: 'ค้นคว้าและสรุปข้อมูล QA' },
        { id: 'qa_security', label: 'QA Security', icon: '🛡️', desc: 'ตรวจสอบความปลอดภัย & OWASP' },
        { id: 'qa_automate', label: 'QA Test Automation', icon: '⚙️', desc: 'สร้าง & รันสคริปต์ Automated Test' },
        { id: 'qa_doc_creation', label: 'QA Document Creation', icon: '📄', desc: 'สร้างเอกสาร QA & Test Scenarios' },
        { id: 'qa_analysis_diagram', label: 'QA Analysis Diagram', icon: '📊', desc: 'ผัง Flow, Sitemap, Wireframe & Matrix' },
        { id: 'qa_board', label: 'QA Board Card', icon: '📋', desc: 'จัดการและตรวจสอบการ์ด Trello' },
        { id: 'master_agent', label: 'Master Agent', icon: '🤖', desc: 'AI ศูนย์กลางประสานงาน' },
        { id: 'workflow_builder', label: 'AI Workflow Builder', icon: '🔗', desc: 'สร้าง Flow การทำงานอัตโนมัติ' }
    ];

    const ADMIN_MENUS = [
        { id: 'ocr', label: 'Scan OCR', icon: '📑', desc: 'สแกนและตรวจสอบคำผิดเอกสาร' },
        { id: 'project_management', label: 'Project Management', icon: '📁', desc: 'จัดการรายชื่อโครงการในระบบ' },
        { id: 'kb', label: 'Knowledge Base', icon: '📚', desc: 'คลังความรู้ RAG เอกสาร' },
        { id: 'skills', label: 'AI Skills', icon: '🧠', desc: 'จัดการทักษะและ Prompt AI' },
        { id: 'qa_member', label: 'QA Member Management', icon: '👥', desc: 'จัดการสมาชิกและสิทธิ์ระบบ' },
        { id: 'exit_criteria', label: 'Exit Criteria', icon: '🎯', desc: 'กำหนดเกณฑ์คุณภาพงาน' },
        { id: 'api_collection', label: 'API Collections', icon: '🔌', desc: 'จัดการคลัง API Endpoint' },
        { id: 'api_usage', label: 'Token Usage', icon: '📊', desc: 'สรุปการใช้งาน Token & Credit' }
    ];

    const roleFilterOptions = [
        { value: 'all', label: 'ทุกระดับสิทธิ์ (All)', icon: '👥' },
        { value: 'admin', label: 'ผู้ดูแลระบบ (Admin)', icon: '🛡️' },
        { value: 'user', label: 'ผู้ใช้ทั่วไป (User)', icon: '👤' }
    ];

    const roleFormOptions = [
        { value: 'user', label: 'ผู้ใช้ทั่วไป (Standard User)', icon: '👤' },
        { value: 'admin', label: 'ผู้ดูแลระบบ (Admin)', icon: '🛡️' }
    ];

    let avatarFile = null;
    let avatarPreview = null;
    let showFullImage = false;
    let activeInfoSubTab = 'general'; // 'general' | 'social'
    let isDragOverAvatar = false;

    // Modal state
    let showModal = false;
    let isEditMode = false;
    let activeModalTab = 'general'; // 'general' | 'permissions'
    let modalProjectSearch = '';

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
        allowed_projects: ['all']
    };

    let confirmModal = {
        show: false,
        title: '',
        message: '',
        action: null
    };

    function getAuthHeaders(customHeaders = {}) {
        const token = localStorage.getItem('jwt_token');
        return {
            ...customHeaders,
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        };
    }

    onMount(async () => {
        await Promise.all([fetchUsers(), fetchProjects()]);
    });

    async function fetchUsers() {
        isLoading = true;
        try {
            const res = await fetch('/api/users', {
                headers: getAuthHeaders()
            });
            const data = await res.json();
            if (res.ok && data.success) {
                users = data.users;
            } else {
                toast(data.error || 'Failed to fetch users', 'error');
            }
        } catch (err) {
            toast('Network error while fetching users', 'error');
        } finally {
            isLoading = false;
        }
    }

    async function fetchProjects() {
        try {
            const res = await fetch('/api/projects');
            const data = await res.json();
            if (res.ok && data.success) {
                allProjects = data.projects || [];
            }
        } catch (err) {
            console.error('Failed to load projects', err);
        }
    }

    async function handleToggleStatus(user) {
        const newStatus = !user.is_active;
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
                toast(`User ${user.username} is now ${newStatus ? 'Active' : 'Inactive'}`, 'success');
            } else {
                toast(data.error || 'Update failed', 'error');
            }
        } catch (err) {
            toast('Network error', 'error');
        }
    }

    function handleToggleRole(user) {
        if (user.username === $authUser) {
            toast('Cannot change your own role', 'warning');
            return;
        }
        const newRole = user.role === 'admin' ? 'user' : 'admin';
        confirmModal = {
            show: true,
            title: 'ยืนยันการเปลี่ยนสิทธิ์',
            message: `คุณต้องการเปลี่ยนสิทธิ์ของ ${user.username} เป็น ${newRole.toUpperCase()} ใช่หรือไม่?`,
            action: async () => {
                confirmModal.show = false;
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
                        toast(`Role updated to ${newRole}`, 'success');
                    } else {
                        toast(data.error || 'Update failed', 'error');
                    }
                } catch (err) {
                    toast('Network error', 'error');
                }
            }
        };
    }

    function handleDelete(user) {
        if (user.username === $authUser) {
            toast('Cannot delete your own account', 'warning');
            return;
        }
        confirmModal = {
            show: true,
            title: 'ยืนยันการลบผู้ใช้งาน',
            message: `คุณต้องการลบผู้ใช้งาน ${user.username} อย่างถาวร ใช่หรือไม่?`,
            action: async () => {
                confirmModal.show = false;
                try {
                    const res = await fetch(`/api/users/${user.user_id}`, {
                        method: 'DELETE',
                        headers: getAuthHeaders()
                    });
                    if (res.ok) {
                        users = users.filter(u => u.user_id !== user.user_id);
                        toast('User deleted', 'success');
                    } else {
                        toast('Delete failed', 'error');
                    }
                } catch (err) {
                    toast('Network error', 'error');
                }
            }
        };
    }

    function openCreateModal() {
        isEditMode = false;
        activeModalTab = 'general';
        activeInfoSubTab = 'general';
        isDragOverAvatar = false;
        modalProjectSearch = '';
        formData = { 
            user_id: null, 
            username: '', 
            email: '', 
            display_name: '', 
            password: 'Spectra123', 
            role: 'user', 
            avatar_path: null,
            phone: '',
            department: '',
            github_url: '',
            linkedin_url: '',
            line_id: '',
            allowed_menus: USER_MENUS.map(m => m.id),
            allowed_projects: ['all']
        };
        avatarFile = null;
        avatarPreview = null;
        showModal = true;
    }

    function openEditModal(user) {
        isEditMode = true;
        activeModalTab = 'general';
        activeInfoSubTab = 'general';
        isDragOverAvatar = false;
        modalProjectSearch = '';
        const defaultMenus = (user.role === 'admin' ? ADMIN_MENUS : USER_MENUS).map(m => m.id);
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
            allowed_menus: Array.isArray(user.allowed_menus) && user.allowed_menus.length > 0 ? user.allowed_menus : defaultMenus,
            allowed_projects: Array.isArray(user.allowed_projects) && user.allowed_projects.length > 0 ? user.allowed_projects : ['all']
        };
        avatarFile = null;
        avatarPreview = user.avatar_path ? `${user.avatar_path}` : null;
        showModal = true;
    }

    function handleAvatarDrop(e) {
        isDragOverAvatar = false;
        const file = e.dataTransfer?.files?.[0];
        if (file && file.type.startsWith('image/')) {
            avatarFile = file;
            avatarPreview = URL.createObjectURL(file);
            toast('เลือกรูปภาพใหม่สำเร็จ', 'success');
        } else {
            toast('กรุณาเลือกไฟล์รูปภาพเท่านั้น', 'warning');
        }
    }

    function removeAvatar() {
        avatarFile = null;
        avatarPreview = null;
        formData.avatar_path = null;
        toast('ลบรูปโปรไฟล์แล้ว', 'info');
    }

    // Permission helpers for Modal
    function toggleMenuPermission(menuId) {
        if (formData.allowed_menus.includes(menuId)) {
            formData.allowed_menus = formData.allowed_menus.filter(id => id !== menuId);
        } else {
            formData.allowed_menus = [...formData.allowed_menus, menuId];
        }
    }

    function selectAllMenus() {
        const currentList = formData.role === 'admin' ? ADMIN_MENUS : USER_MENUS;
        formData.allowed_menus = currentList.map(m => m.id);
    }

    function deselectAllMenus() {
        formData.allowed_menus = [];
    }

    function setProjectAccessMode(mode) {
        if (mode === 'all') {
            formData.allowed_projects = ['all'];
        } else {
            if (formData.allowed_projects.includes('all')) {
                formData.allowed_projects = allProjects.length > 0 ? [String(allProjects[0].id || allProjects[0].project_code)] : [];
            }
        }
    }

    function toggleProjectPermission(proj) {
        const pId = String(proj.id || proj.project_id || proj.project_code);
        if (formData.allowed_projects.includes('all')) {
            formData.allowed_projects = [pId];
            return;
        }
        if (formData.allowed_projects.includes(pId)) {
            formData.allowed_projects = formData.allowed_projects.filter(id => id !== pId);
        } else {
            formData.allowed_projects = [...formData.allowed_projects, pId];
        }
    }

    function isProjectSelected(proj) {
        if (formData.allowed_projects.includes('all')) return true;
        const pId = String(proj.id || proj.project_id || proj.project_code);
        const pCode = String(proj.project_code || '');
        return formData.allowed_projects.includes(pId) || (pCode && formData.allowed_projects.includes(pCode));
    }

    function selectAllProjects() {
        formData.allowed_projects = allProjects.map(p => String(p.id || p.project_id || p.project_code));
    }

    function deselectAllProjects() {
        formData.allowed_projects = [];
    }

    // Role change auto-switch menus
    function handleRoleChange(newRole) {
        formData.role = newRole;
        formData.allowed_menus = (newRole === 'admin' ? ADMIN_MENUS : USER_MENUS).map(m => m.id);
    }

    async function handleSaveUser() {
        if (!formData.username || !formData.email || !formData.display_name || (!isEditMode && !formData.password)) {
            toast('Please fill all required fields', 'warning');
            return;
        }

        const url = isEditMode ? `/api/users/${formData.user_id}` : '/api/users';
        const method = isEditMode ? 'PUT' : 'POST';
        
        try {
            const res = await fetch(url, {
                method,
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(formData)
            });
            const data = await res.json();
            if (res.ok && data.success) {
                const userId = data.user.user_id;
                
                if (avatarFile) {
                    const uploadData = new FormData();
                    uploadData.append('avatar', avatarFile);
                    try {
                        const token = localStorage.getItem('jwt_token');
                        await fetch(`/api/users/${userId}/avatar`, {
                            method: 'POST',
                            headers: { 'Authorization': `Bearer ${token}` },
                            body: uploadData
                        });
                    } catch (e) {
                        toast('Avatar upload failed', 'error');
                    }
                }
                
                toast(isEditMode ? 'User updated successfully' : 'User created successfully', 'success');
                showModal = false;
                await fetchUsers(); // Refresh list
            } else {
                toast(data.error || 'Operation failed', 'error');
            }
        } catch (err) {
            toast('Network error', 'error');
        }
    }

    function formatDate(isoString) {
        if (!isoString) return '-';
        const d = new Date(isoString + (!isoString.endsWith('Z') && !isoString.includes('+') ? 'Z' : ''));
        return d.toLocaleString('th-TH', { 
            day: '2-digit', month: '2-digit', year: '2-digit', 
            hour: '2-digit', minute: '2-digit' 
        });
    }

    // Computed properties for UI
    $: filteredUsers = users.filter(u => {
        const matchSearch = (u.username.toLowerCase().includes(searchQuery.toLowerCase()) || 
                             u.email.toLowerCase().includes(searchQuery.toLowerCase()) || 
                             (u.display_name || '').toLowerCase().includes(searchQuery.toLowerCase()));
        const matchRole = roleFilter === 'all' || u.role === roleFilter;
        return matchSearch && matchRole;
    });

    $: filteredModalProjects = allProjects.filter(p => {
        if (!modalProjectSearch) return true;
        const q = modalProjectSearch.toLowerCase();
        return (p.name || p.project_name || '').toLowerCase().includes(q) || 
               (p.project_code || '').toLowerCase().includes(q) ||
               (p.description || '').toLowerCase().includes(q);
    });

    $: activeMenuList = formData.role === 'admin' ? ADMIN_MENUS : USER_MENUS;

    $: stats = {
        total: users.length,
        admins: users.filter(u => u.role === 'admin').length,
        standard: users.filter(u => u.role === 'user').length,
        active: users.filter(u => u.is_active).length
    };
</script>

<div class="qa-member-container">
    <div class="header-section">
        <div>
            <h1 class="page-title">QA Member Management</h1>
            <p class="page-subtitle">จัดการข้อมูลสมาชิก สิทธิ์การเข้าถึงเมนู และสิทธิ์โครงการในระบบ</p>
        </div>
        <button class="btn-primary" on:click={openCreateModal}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
            เพิ่มผู้ใช้งาน
        </button>
    </div>

    <!-- Stats Cards -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(99, 102, 241, 0.1); color: var(--primary);">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.total}</div>
                <div class="stat-label">สมาชิกทั้งหมด</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(168, 85, 247, 0.1); color: #a855f7;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.admins}</div>
                <div class="stat-label">ผู้ดูแลระบบ (Admin)</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(14, 165, 233, 0.1); color: #0ea5e9;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.standard}</div>
                <div class="stat-label">ผู้ใช้ทั่วไป (User)</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(34, 197, 94, 0.1); color: var(--success);">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            </div>
            <div class="stat-info">
                <div class="stat-value">{stats.active}</div>
                <div class="stat-label">บัญชีที่เปิดใช้งาน</div>
            </div>
        </div>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
        <div class="search-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input type="text" bind:value={searchQuery} placeholder="ค้นหาชื่อ, อีเมล หรือ Username..." />
        </div>
        <div class="role-filter">
            <CustomSelect 
                bind:value={roleFilter} 
                options={roleFilterOptions} 
                minWidth="200px" 
            />
        </div>
    </div>

    <!-- User Table -->
    <div class="table-container">
        {#if isLoading}
            <div class="loading-state">
                <div class="spinner"></div>
                <p>กำลังโหลดข้อมูลผู้ใช้งาน...</p>
            </div>
        {:else if filteredUsers.length === 0}
            <div class="empty-state">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path><line x1="4" y1="4" x2="20" y2="20" opacity="0.5"></line></svg>
                <p>ไม่พบข้อมูลผู้ใช้งาน</p>
            </div>
        {:else}
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ผู้ใช้งาน</th>
                        <th>อีเมล / Username</th>
                        <th>สิทธิ์ (Role)</th>
                        <th>สิทธิ์เมนู & โครงการ</th>
                        <th>สถานะ</th>
                        <th>เข้าสู่ระบบล่าสุด</th>
                        <th style="text-align: right;">จัดการ</th>
                    </tr>
                </thead>
                <tbody>
                    {#each filteredUsers as user}
                        <tr>
                            <td>
                                <div class="user-cell">
                                    <div class="avatar" class:online={user.is_active}>
                                        {#if user.avatar_path}
                                            <img src={`${user.avatar_path}`} alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;" />
                                        {:else}
                                            {user.display_name ? user.display_name.charAt(0).toUpperCase() : user.username.charAt(0).toUpperCase()}
                                        {/if}
                                    </div>
                                    <div class="user-info">
                                        <div class="d-name">{user.display_name || 'No Display Name'}</div>
                                        <div class="c-date">สร้างเมื่อ: {formatDate(user.created_at)}</div>
                                    </div>
                                </div>
                            </td>
                            <td>
                                <div class="email-cell">
                                    <div class="username-text">{user.username}</div>
                                    <div class="email-text">{user.email}</div>
                                </div>
                            </td>
                            <td>
                                <button class="role-badge" class:admin={user.role === 'admin'} on:click={() => handleToggleRole(user)} title="คลิกเพื่อเปลี่ยนสิทธิ์">
                                    {#if user.role === 'admin'}
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"></path></svg>
                                        Admin
                                    {:else}
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                                        User
                                    {/if}
                                </button>
                            </td>
                            <td>
                                <div class="permission-summary-badges">
                                    <span class="perm-badge menu-perm" title="เมนูที่เข้าถึงได้: {(user.allowed_menus || []).join(', ')}">
                                        📱 {user.allowed_menus ? user.allowed_menus.length : 0} เมนู
                                    </span>
                                    <span class="perm-badge project-perm" title="โครงการที่เข้าถึงได้">
                                        {#if !user.allowed_projects || user.allowed_projects.includes('all')}
                                            📁 ทุกโครงการ
                                        {:else}
                                            📁 {user.allowed_projects.length} โครงการ
                                        {/if}
                                    </span>
                                </div>
                            </td>
                            <td>
                                <label class="toggle-switch">
                                    <input type="checkbox" checked={user.is_active} on:change={() => handleToggleStatus(user)} />
                                    <span class="slider"></span>
                                </label>
                            </td>
                            <td>
                                <div class="login-cell">
                                    <div class="last-login">{formatDate(user.last_login_at)}</div>
                                    <div class="login-count">{user.login_count} ครั้ง</div>
                                </div>
                            </td>
                            <td style="text-align: right;">
                                <div class="action-buttons">
                                    <button class="icon-btn edit" on:click={() => openEditModal(user)} title="แก้ไขข้อมูลและสิทธิ์">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                                    </button>
                                    <button class="icon-btn delete" on:click={() => handleDelete(user)} disabled={user.username === $authUser} title="ลบ">
                                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
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

<!-- Create / Edit Modal with Permission Configuration -->
{#if showModal}
<div class="modal-backdrop">
    <div class="modal-content glass-card modal-large">
        <button class="close-btn" on:click={() => showModal = false}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
        
        <h2 class="modal-title">{isEditMode ? 'แก้ไขข้อมูลผู้ใช้งาน & สิทธิ์การเข้าถึง' : 'เพิ่มผู้ใช้งานใหม่ & กำหนดสิทธิ์'}</h2>
        
        <!-- Modal Navigation Tabs -->
        <div class="modal-tab-bar">
            <button 
                class="modal-tab-btn" 
                class:active={activeModalTab === 'general'} 
                on:click={() => activeModalTab = 'general'}
            >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                ข้อมูลผู้ใช้งาน (General Info)
            </button>
            <button 
                class="modal-tab-btn" 
                class:active={activeModalTab === 'permissions'} 
                on:click={() => activeModalTab = 'permissions'}
            >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                กำหนดสิทธิ์การเข้าถึง (Permissions)
                <span class="tab-badge">{formData.allowed_menus.length} เมนู</span>
            </button>
        </div>

        <div class="modal-scroll-area">
            {#if activeModalTab === 'general'}
                <!-- Avatar Upload Hero Card -->
                <div class="avatar-hero-container">
                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                    <!-- svelte-ignore a11y-no-static-element-interactions -->
                    <div 
                      class="avatar-hero-circle" 
                      class:drag-over={isDragOverAvatar}
                      on:dragover|preventDefault={() => isDragOverAvatar = true}
                      on:dragleave|preventDefault={() => isDragOverAvatar = false}
                      on:drop|preventDefault={handleAvatarDrop}
                      on:click={() => document.getElementById('qa_member_avatar_input').click()}
                      title="คลิกเพื่อเปลี่ยนรูป หรือลากวางไฟล์รูปภาพตรงนี้"
                    >
                        {#if avatarPreview}
                            <img src={avatarPreview} alt="Preview Avatar" />
                        {:else}
                            <div class="avatar-fallback-text">
                                {formData.display_name ? formData.display_name.charAt(0).toUpperCase() : (formData.username ? formData.username.charAt(0).toUpperCase() : 'U')}
                            </div>
                        {/if}
                        
                        <div class="avatar-hover-overlay">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>
                            <span>เปลี่ยนรูปภาพ</span>
                        </div>
                        <div class="camera-badge" title="อัปโหลดรูปภาพ">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>
                        </div>
                    </div>

                    <input 
                      type="file" 
                      id="qa_member_avatar_input" 
                      accept="image/*" 
                      style="display: none;" 
                      on:change={(e) => {
                          const file = e.target.files[0];
                          if (file) {
                              avatarFile = file;
                              avatarPreview = URL.createObjectURL(file);
                              toast('เลือกรูปภาพใหม่สำเร็จ', 'success');
                          }
                      }} 
                    />

                    <div class="avatar-controls">
                        <button class="btn-avatar-action upload" type="button" on:click={() => document.getElementById('qa_member_avatar_input').click()}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                            อัปโหลดรูปภาพใหม่
                        </button>

                        {#if avatarPreview}
                            <button class="btn-avatar-action remove" type="button" on:click={removeAvatar}>
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                ลบรูปโปรไฟล์
                            </button>
                        {/if}
                    </div>
                    <span class="drag-hint-text">รองรับไฟล์ JPG, PNG, WEBP (คลิกหรือลากวางรูปภาพ)</span>
                </div>

                <!-- Sub-tab Navigation (General vs Social) -->
                <div class="profile-tabs-header">
                    <button class="ptab-btn" class:active={activeInfoSubTab === 'general'} on:click={() => activeInfoSubTab = 'general'}>
                        📌 ข้อมูลทั่วไป
                    </button>
                    <button class="ptab-btn" class:active={activeInfoSubTab === 'social'} on:click={() => activeInfoSubTab = 'social'}>
                        🌐 โซเชียล & ช่องทางติดต่อ
                    </button>
                </div>

                <!-- Sub-tab Form Body -->
                {#if activeInfoSubTab === 'general'}
                    <div class="form-grid">
                        <div class="form-group full-width">
                            <label for="display_name">Display Name (ชื่อที่แสดงในระบบ) *</label>
                            <input type="text" id="display_name" bind:value={formData.display_name} placeholder="เช่น John Doe" />
                        </div>

                        <div class="form-group">
                            <label for="username">Username *</label>
                            <input type="text" id="username" bind:value={formData.username} disabled={isEditMode} placeholder="e.g. jdoe123" />
                        </div>
                        
                        <div class="form-group">
                            <label for="email">Email Address *</label>
                            <input type="email" id="email" bind:value={formData.email} disabled={isEditMode} placeholder="e.g. john@domain.com" />
                        </div>

                        <div class="form-group">
                            <label for="department">แผนก / ตำแหน่งงาน (Department / Position)</label>
                            <input type="text" id="department" bind:value={formData.department} placeholder="เช่น Senior QA Automation Lead" />
                        </div>

                        <div class="form-group">
                            <label for="phone">เบอร์โทรศัพท์ (Phone Number)</label>
                            <div class="input-with-icon">
                                <span class="field-icon">📞</span>
                                <input type="tel" id="phone" bind:value={formData.phone} placeholder="081-234-5678" />
                            </div>
                        </div>

                        <div class="form-group">
                            <label>Password</label>
                            <div style="display: flex; flex-direction: column; gap: 8px;">
                                <button type="button" class="btn-warning" on:click={() => { formData.password = 'Spectra123'; toast('ตั้งรหัสผ่านชั่วคราวเป็น Spectra123 แล้ว', 'info'); }}>
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>
                                    Reset Password
                                </button>
                                {#if formData.password === 'Spectra123'}
                                    <small style="color: var(--success);">รหัสผ่านจะถูกตั้งค่าเป็น: <b>Spectra123</b></small>
                                {/if}
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label for="role">ระดับสิทธิ์ (Role)</label>
                            <CustomSelect 
                                id="role"
                                value={formData.role} 
                                options={roleFormOptions} 
                                width="100%" 
                                on:change={(e) => handleRoleChange(e.detail)}
                            />
                        </div>
                    </div>

                {:else if activeInfoSubTab === 'social'}
                    <div class="form-grid">
                        <div class="form-group">
                            <label for="github_url">GitHub Profile URL</label>
                            <div class="input-with-icon">
                                <span class="field-icon">🐙</span>
                                <input type="url" id="github_url" bind:value={formData.github_url} placeholder="https://github.com/username" />
                            </div>
                        </div>

                        <div class="form-group">
                            <label for="linkedin_url">LinkedIn Profile URL</label>
                            <div class="input-with-icon">
                                <span class="field-icon">💼</span>
                                <input type="url" id="linkedin_url" bind:value={formData.linkedin_url} placeholder="https://linkedin.com/in/username" />
                            </div>
                        </div>

                        <div class="form-group full-width">
                            <label for="line_id">Line ID / Telegram Contact</label>
                            <div class="input-with-icon">
                                <span class="field-icon">💬</span>
                                <input type="text" id="line_id" bind:value={formData.line_id} placeholder="@line_id / @telegram" />
                            </div>
                        </div>
                    </div>
                {/if}
            {:else if activeModalTab === 'permissions'}
                <!-- Menu Permissions Section -->
                <div class="permission-section">
                    <div class="section-header-row">
                        <div>
                            <h3 class="section-title">📱 สิทธิ์การเข้าถึงเมนู (Menu Permissions)</h3>
                            <p class="section-subtitle">
                                เลือกเมนูและโมดูลที่ผู้ใช้คนนี้สามารถมองเห็นและใช้งานได้ในโหมด ({formData.role === 'admin' ? '🛡️ Admin' : '👤 Standard User'})
                            </p>
                        </div>
                        <div class="section-actions">
                            <button type="button" class="btn-text-action" on:click={selectAllMenus}>เลือกทั้งหมด</button>
                            <span class="action-divider">|</span>
                            <button type="button" class="btn-text-action" on:click={deselectAllMenus}>ล้างทั้งหมด</button>
                        </div>
                    </div>

                    <div class="menu-permission-grid">
                        {#each activeMenuList as menu}
                            <!-- svelte-ignore a11y-click-events-have-key-events -->
                            <!-- svelte-ignore a11y-no-static-element-interactions -->
                            <div 
                                class="perm-card" 
                                class:active={formData.allowed_menus.includes(menu.id)}
                                on:click={() => toggleMenuPermission(menu.id)}
                            >
                                <div class="perm-card-check">
                                    <input 
                                        type="checkbox" 
                                        checked={formData.allowed_menus.includes(menu.id)} 
                                        on:change|stopPropagation={() => toggleMenuPermission(menu.id)} 
                                    />
                                </div>
                                <div class="perm-card-icon">{menu.icon}</div>
                                <div class="perm-card-body">
                                    <div class="perm-card-title">{menu.label}</div>
                                    <div class="perm-card-desc">{menu.desc}</div>
                                </div>
                            </div>
                        {/each}
                    </div>
                </div>

                <div class="section-divider"></div>

                <!-- Project Permissions Section -->
                <div class="permission-section">
                    <div class="section-header-row">
                        <div>
                            <h3 class="section-title">📁 สิทธิ์การเข้าถึงโครงการ (Project Access)</h3>
                            <p class="section-subtitle">
                                กำหนดว่าผู้ใช้สามารถเข้าถึงข้อมูลของโครงการใดได้บ้างในระบบ
                            </p>
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
                                <div class="radio-title">🌐 เข้าถึงได้ทุกโครงการ (All Projects)</div>
                                <div class="radio-desc">ผู้ใช้สามารถเข้าถึงและเลือกทุกโครงการในระบบได้ตามปกติ (รวมถึงโครงการที่สร้างใหม่ในอนาคต)</div>
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
                                <div class="radio-title">🔒 ระบุเฉพาะโครงการที่อนุญาต (Specific Projects Only)</div>
                                <div class="radio-desc">จำกัดให้ผู้ใช้เข้าถึงได้เฉพาะโครงการที่ถูกเลือกด้านล่างนี้เท่านั้น</div>
                            </div>
                        </label>
                    </div>

                    {#if !formData.allowed_projects.includes('all')}
                        <div class="specific-projects-container">
                            <div class="specific-projects-toolbar">
                                <div class="search-mini">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                                    <input type="text" bind:value={modalProjectSearch} placeholder="ค้นหาโครงการ..." />
                                </div>
                                <div class="section-actions">
                                    <button type="button" class="btn-text-action" on:click={selectAllProjects}>เลือกทุกโครงการ</button>
                                    <span class="action-divider">|</span>
                                    <button type="button" class="btn-text-action" on:click={deselectAllProjects}>ล้างทั้งหมด</button>
                                </div>
                            </div>

                            {#if filteredModalProjects.length === 0}
                                <div class="empty-mini">ไม่พบโครงการที่ค้นหา</div>
                            {:else}
                                <div class="project-checkbox-list">
                                    {#each filteredModalProjects as proj}
                                        <!-- svelte-ignore a11y-click-events-have-key-events -->
                                        <!-- svelte-ignore a11y-no-static-element-interactions -->
                                        <div 
                                            class="project-check-item" 
                                            class:selected={isProjectSelected(proj)}
                                            on:click={() => toggleProjectPermission(proj)}
                                        >
                                            <input 
                                                type="checkbox" 
                                                checked={isProjectSelected(proj)} 
                                                on:change|stopPropagation={() => toggleProjectPermission(proj)}
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
                                        </div>
                                    {/each}
                                </div>
                            {/if}
                        </div>
                    {/if}
                </div>
            {/if}
        </div>
        
        <div class="modal-actions">
            <button class="btn-secondary" on:click={() => showModal = false}>ยกเลิก</button>
            <button class="btn-primary" on:click={handleSaveUser}>บันทึกข้อมูลและสิทธิ์</button>
        </div>
    </div>
</div>
{/if}

{#if showFullImage && avatarPreview}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="full-image-overlay" on:click={() => showFullImage = false}>
        <img src={avatarPreview} alt="Full Preview" />
    </div>
{/if}

{#if confirmModal.show}
<div class="modal-backdrop" style="z-index: 2000;">
    <div class="modal-content glass-card confirm-dialog">
        <h2 class="modal-title" style="margin-bottom: 12px; font-size: 20px; color: white;">{confirmModal.title}</h2>
        <p style="color: var(--text-main); font-size: 15px; margin-bottom: 24px;">{confirmModal.message}</p>
        <div class="modal-actions" style="justify-content: center; gap: 15px;">
            <button class="btn-secondary" on:click={() => confirmModal.show = false}>ยกเลิก</button>
            <button class="btn-primary" style="background: var(--danger); box-shadow: 0 4px 15px rgba(244, 63, 94, 0.4);" on:click={confirmModal.action}>ยืนยัน</button>
        </div>
    </div>
</div>
{/if}

<style>
    .qa-member-container {
        padding: 40px;
        color: var(--text-main);
        font-family: var(--font-th);
        width: 100%;
    }

    .header-section {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 30px;
    }

    .page-title {
        font-size: 28px;
        font-family: var(--font-en);
        font-weight: 700;
        margin: 0 0 5px;
    }

    .page-subtitle {
        color: var(--text-muted);
        margin: 0;
        font-size: 15px;
    }

    .btn-primary {
        background: var(--gradient-main);
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: var(--radius-md);
        font-family: var(--font-th);
        font-size: 15px;
        font-weight: 600;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
        transition: all 0.2s;
    }

    .btn-primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    }
    
    .btn-primary svg { width: 16px; height: 16px; }

    /* Stats Grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }

    .stat-card {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        padding: 20px;
        display: flex;
        align-items: center;
        gap: 15px;
        backdrop-filter: var(--glass-blur);
    }

    .stat-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .stat-icon svg { width: 24px; height: 24px; }

    .stat-value {
        font-family: var(--font-en);
        font-size: 24px;
        font-weight: 700;
        color: var(--text-main);
        line-height: 1;
        margin-bottom: 5px;
    }

    .stat-label {
        font-size: 13px;
        color: var(--text-muted);
    }

    /* Filters */
    .filter-bar {
        display: flex;
        gap: 15px;
        margin-bottom: 25px;
    }

    .search-box {
        flex: 1;
        position: relative;
        display: flex;
        align-items: center;
    }

    .search-box svg {
        position: absolute;
        left: 15px;
        color: var(--text-dim);
        width: 16px; height: 16px;
    }

    .search-box input {
        width: 100%;
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 12px 15px 12px 40px;
        color: var(--text-main);
        font-family: var(--font-th);
        outline: none;
    }
    .search-box input:focus {
        border-color: var(--primary);
    }

    .role-filter select {
        background: rgba(0, 0, 0, 0.2);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 12px 15px;
        color: var(--text-main);
        font-family: var(--font-th);
        outline: none;
        appearance: none;
        min-width: 180px;
        cursor: pointer;
        background-image: url("data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: right 15px center;
        background-size: 16px;
        padding-right: 40px;
    }

    /* Table */
    .table-container {
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-lg);
        overflow-x: auto;
        backdrop-filter: var(--glass-blur);
    }

    .data-table {
        width: 100%;
        border-collapse: collapse;
        text-align: left;
    }

    .data-table th, .data-table td {
        padding: 15px 20px;
        border-bottom: 1px solid var(--glass-border);
    }

    .data-table th {
        color: var(--text-muted);
        font-weight: 600;
        font-size: 13px;
        letter-spacing: 0.5px;
    }

    .user-cell { display: flex; align-items: center; gap: 12px; }
    
    .avatar {
        width: 36px; height: 36px;
        border-radius: 50%;
        background: var(--primary);
        color: white;
        display: flex; align-items: center; justify-content: center;
        font-family: var(--font-en); font-weight: 700;
        position: relative;
    }
    .avatar.online::after {
        content: '';
        position: absolute;
        bottom: 0; right: 0;
        width: 10px; height: 10px;
        border-radius: 50%;
        background: var(--success);
        border: 2px solid var(--bg-dark);
    }

    .d-name { font-weight: 600; color: var(--text-main); margin-bottom: 3px; }
    .c-date { font-size: 11px; color: var(--text-dim); }
    
    .username-text { font-weight: 500; font-family: var(--font-en); font-size: 13px; }
    .email-text { font-size: 12px; color: var(--text-muted); font-family: var(--font-en); }

    .role-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(255,255,255,0.05);
        border: 1px solid var(--glass-border-light);
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 12px;
        color: var(--text-muted);
        cursor: pointer;
        transition: all 0.2s;
    }
    .role-badge:hover { background: rgba(255,255,255,0.1); }
    .role-badge svg { width: 14px; height: 14px; }
    
    .role-badge.admin {
        background: rgba(168, 85, 247, 0.15);
        color: #d8b4fe;
        border-color: rgba(168, 85, 247, 0.3);
    }

    .last-login { font-size: 13px; margin-bottom: 3px; }
    .login-count { font-size: 11px; color: var(--text-dim); }

    .action-buttons {
        display: flex; justify-content: flex-end; gap: 8px;
    }
    .icon-btn {
        background: rgba(255,255,255,0.05); border: none;
        width: 32px; height: 32px; border-radius: 8px;
        color: var(--text-muted); cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        transition: all 0.2s;
    }
    .icon-btn:hover:not(:disabled) { background: rgba(255,255,255,0.15); color: white; }
    .icon-btn:disabled { opacity: 0.3; cursor: not-allowed; }
    .icon-btn.delete:hover:not(:disabled) { background: rgba(239, 68, 68, 0.2); color: var(--danger); }

    /* Toggle Switch */
    .toggle-switch {
        position: relative; display: inline-block;
        width: 44px; height: 24px;
    }
    .toggle-switch input { opacity: 0; width: 0; height: 0; }
    .slider {
        position: absolute; cursor: pointer;
        top: 0; left: 0; right: 0; bottom: 0;
        background-color: rgba(255,255,255,0.1);
        transition: .4s; border-radius: 34px;
    }
    .slider:before {
        position: absolute; content: "";
        height: 18px; width: 18px;
        left: 3px; bottom: 3px;
        background-color: white;
        transition: .4s; border-radius: 50%;
    }
    input:checked + .slider { background-color: var(--success); }
    input:checked + .slider:before { transform: translateX(20px); }

    /* Loading / Empty State */
    .loading-state, .empty-state {
        padding: 50px; text-align: center; color: var(--text-muted);
        display: flex; flex-direction: column; align-items: center; gap: 15px;
    }
    .empty-state svg { width: 48px; height: 48px; color: var(--text-dim); }
    .spinner {
        width: 30px; height: 30px; border: 3px solid rgba(255,255,255,0.1);
        border-radius: 50%; border-top-color: var(--primary);
        animation: spin 1s linear infinite;
    }
    @keyframes spin { 100% { transform: rotate(360deg); } }

    /* Permission Badges in Table */
    .permission-summary-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
    }
    .perm-badge {
        font-size: 11px;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .perm-badge.menu-perm {
        background: rgba(168, 85, 247, 0.15);
        color: #c084fc;
        border: 1px solid rgba(168, 85, 247, 0.3);
    }
    .perm-badge.project-perm {
        background: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    /* Modal Styling */
    .modal-backdrop {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.7); backdrop-filter: blur(8px);
        display: flex; align-items: center; justify-content: center;
        z-index: 1000;
        padding: 20px;
    }
    .modal-content {
        width: 100%; max-width: 450px;
        padding: 28px; position: relative;
        background: #0f172a;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: var(--radius-xl, 16px);
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
        max-height: 90vh;
        display: flex;
        flex-direction: column;
    }
    .modal-content.modal-large {
        max-width: 680px;
    }
    .modal-scroll-area {
        overflow-y: auto;
        padding-right: 6px;
        margin-right: -6px;
        max-height: calc(85vh - 170px);
    }
    .modal-scroll-area::-webkit-scrollbar {
        width: 6px;
    }
    .modal-scroll-area::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.15);
        border-radius: 3px;
    }

    .close-btn {
        position: absolute; top: 20px; right: 20px;
        background: none; border: none; color: var(--text-muted);
        cursor: pointer; transition: color 0.2s;
    }
    .close-btn:hover { color: white; }
    .close-btn svg { width: 22px; height: 22px; }
    
    .modal-title { font-size: 20px; font-weight: 700; margin: 0 0 16px; color: white; }

    /* Modal Tabs */
    .modal-tab-bar {
        display: flex;
        gap: 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
        padding-bottom: 4px;
    }
    .modal-tab-btn {
        background: transparent;
        border: none;
        color: var(--text-muted, #94a3b8);
        padding: 8px 14px;
        font-size: 13.5px;
        font-weight: 600;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 8px;
        transition: all 0.2s;
    }
    .modal-tab-btn:hover {
        color: white;
        background: rgba(255, 255, 255, 0.05);
    }
    .modal-tab-btn.active {
        color: white;
        background: rgba(99, 102, 241, 0.2);
        border-bottom: 2px solid #818cf8;
    }
    .tab-badge {
        font-size: 11px;
        background: rgba(99, 102, 241, 0.3);
        color: #c7d2fe;
        padding: 2px 6px;
        border-radius: 10px;
    }

    .form-grid-2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 15px;
    }
    
    .form-group { margin-bottom: 15px; }
    .form-group label {
        display: block; margin-bottom: 8px; font-size: 13px; color: var(--text-muted);
    }
    .form-group input, .form-group select {
        width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--glass-border);
        padding: 10px 15px; border-radius: var(--radius-md); color: white;
        outline: none; font-family: var(--font-th);
    }
    .form-group select {
        appearance: none;
        background-image: url("data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: right 15px center;
        background-size: 16px;
        padding-right: 40px;
        cursor: pointer;
    }
    .form-group input:focus, .form-group select:focus { border-color: var(--primary); }
    .form-group input:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Permission Section Styles */
    .permission-section {
        margin-bottom: 20px;
    }
    .section-header-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 12px;
    }
    .section-title {
        font-size: 15px;
        font-weight: 700;
        color: white;
        margin: 0 0 4px;
    }
    .section-subtitle {
        font-size: 12px;
        color: #94a3b8;
        margin: 0;
    }
    .section-actions {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .btn-text-action {
        background: none;
        border: none;
        color: #818cf8;
        font-size: 12px;
        cursor: pointer;
        padding: 2px 4px;
        border-radius: 4px;
    }
    .btn-text-action:hover {
        color: #a5b4fc;
        text-decoration: underline;
    }
    .action-divider {
        color: rgba(255, 255, 255, 0.2);
        font-size: 12px;
    }
    .section-divider {
        height: 1px;
        background: rgba(255, 255, 255, 0.08);
        margin: 18px 0;
    }

    /* Menu Permission Cards */
    .menu-permission-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 10px;
    }
    .perm-card {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 10px 12px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .perm-card:hover {
        background: rgba(255, 255, 255, 0.06);
        border-color: rgba(99, 102, 241, 0.3);
    }
    .perm-card.active {
        background: rgba(99, 102, 241, 0.12);
        border-color: rgba(99, 102, 241, 0.4);
    }
    .perm-card-check {
        padding-top: 2px;
    }
    .perm-card-check input {
        cursor: pointer;
        accent-color: var(--primary);
    }
    .perm-card-icon {
        font-size: 18px;
        line-height: 1;
        padding-top: 2px;
    }
    .perm-card-body {
        flex: 1;
        min-width: 0;
    }
    .perm-card-title {
        font-size: 13px;
        font-weight: 600;
        color: white;
        margin-bottom: 2px;
    }
    .perm-card-desc {
        font-size: 11px;
        color: #94a3b8;
        line-height: 1.3;
    }

    /* Project Access Radio Cards */
    .project-access-options {
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-bottom: 14px;
    }
    .access-radio-card {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .access-radio-card:hover {
        background: rgba(255, 255, 255, 0.06);
    }
    .access-radio-card.active {
        background: rgba(59, 130, 246, 0.12);
        border-color: rgba(59, 130, 246, 0.4);
    }
    .access-radio-card input {
        margin-top: 3px;
        cursor: pointer;
        accent-color: #3b82f6;
    }
    .radio-content {
        flex: 1;
    }
    .radio-title {
        font-size: 13.5px;
        font-weight: 600;
        color: white;
        margin-bottom: 2px;
    }
    .radio-desc {
        font-size: 11.5px;
        color: #94a3b8;
        line-height: 1.3;
    }

    /* Specific Projects Container */
    .specific-projects-container {
        background: rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 12px;
    }
    .specific-projects-toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
    }
    .search-mini {
        position: relative;
        flex: 1;
        max-width: 260px;
        display: flex;
        align-items: center;
    }
    .search-mini svg {
        position: absolute;
        left: 10px;
        color: #64748b;
    }
    .search-mini input {
        width: 100%;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 6px;
        padding: 6px 10px 6px 30px;
        font-size: 12px;
        color: white;
        outline: none;
    }
    .search-mini input:focus {
        border-color: #3b82f6;
    }
    .project-checkbox-list {
        max-height: 200px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 6px;
        padding-right: 4px;
    }
    .project-check-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 10px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }
    .project-check-item:hover {
        background: rgba(255, 255, 255, 0.05);
    }
    .project-check-item.selected {
        background: rgba(59, 130, 246, 0.1);
        border-color: rgba(59, 130, 246, 0.3);
    }
    .project-check-item input {
        cursor: pointer;
        accent-color: #3b82f6;
    }
    .proj-code-badge {
        font-family: monospace;
        font-size: 11px;
        font-weight: 700;
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
        padding: 2px 6px;
        border-radius: 4px;
        white-space: nowrap;
    }
    .proj-info-col {
        flex: 1;
        min-width: 0;
    }
    .proj-name-text {
        font-size: 12.5px;
        font-weight: 600;
        color: white;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .proj-desc-text {
        font-size: 11px;
        color: #64748b;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .proj-status-badge {
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 4px;
        background: rgba(255, 255, 255, 0.05);
        color: #94a3b8;
    }
    .proj-status-badge.active {
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
    }
    .empty-mini {
        padding: 20px;
        text-align: center;
        color: #64748b;
        font-size: 12px;
    }

    .confirm-dialog {
        max-width: 400px; padding: 24px 32px; text-align: center;
    }
    .confirm-dialog .modal-title {
        color: var(--danger) !important;
    }
    
    .modal-actions {
        display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;
        padding-top: 15px; border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
    .btn-secondary {
        background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border);
        color: white; padding: 10px 20px; border-radius: var(--radius-md);
        cursor: pointer; transition: background 0.2s;
    }
    .btn-secondary:hover { background: rgba(255,255,255,0.1); }
    
    select option {
        background-color: var(--bg-dark, #0f172a);
        color: white;
        font-family: var(--font-th);
        padding: 10px;
    }

    /* Avatar Hero Card (User Side Style) */
    .avatar-hero-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.02);
        border: 1px dashed rgba(255, 255, 255, 0.12);
        border-radius: 16px;
        transition: all 0.3s ease;
    }
    .avatar-hero-container:hover {
        border-color: rgba(139, 92, 246, 0.3);
        background: rgba(139, 92, 246, 0.02);
    }
    .avatar-hero-circle {
        position: relative;
        width: 104px;
        height: 104px;
        border-radius: 50%;
        background: linear-gradient(135deg, #1e1b4b 0%, #311b92 100%);
        border: 3px solid #8b5cf6;
        box-shadow: 0 8px 24px rgba(139, 92, 246, 0.3);
        cursor: pointer;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .avatar-hero-circle:hover {
        transform: scale(1.04);
        box-shadow: 0 12px 32px rgba(139, 92, 246, 0.45);
        border-color: #a78bfa;
    }
    .avatar-hero-circle.drag-over {
        border-color: #3b82f6;
        box-shadow: 0 0 25px rgba(59, 130, 246, 0.6);
        transform: scale(1.06);
    }
    .avatar-hero-circle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .avatar-fallback-text {
        font-size: 40px;
        font-weight: 800;
        color: #f3e8ff;
        text-shadow: 0 2px 10px rgba(0,0,0,0.5);
    }
    .avatar-hover-overlay {
        position: absolute;
        inset: 0;
        background: rgba(15, 23, 42, 0.75);
        backdrop-filter: blur(2px);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 4px;
        color: #f3e8ff;
        font-size: 11px;
        font-weight: 600;
        opacity: 0;
        transition: opacity 0.25s ease;
    }
    .avatar-hero-circle:hover .avatar-hover-overlay {
        opacity: 1;
    }
    .camera-badge {
        position: absolute;
        bottom: 2px;
        right: 2px;
        background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        border: 2px solid #0f172a;
        box-shadow: 0 2px 6px rgba(0,0,0,0.4);
        z-index: 2;
        transition: transform 0.2s;
    }
    .avatar-hero-circle:hover .camera-badge {
        transform: scale(1.1);
    }
    .avatar-controls {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .btn-avatar-action {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 7px 14px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        font-family: var(--font-th);
    }
    .btn-avatar-action.upload {
        background: rgba(139, 92, 246, 0.15);
        border: 1px solid rgba(139, 92, 246, 0.35);
        color: #c084fc;
    }
    .btn-avatar-action.upload:hover {
        background: rgba(139, 92, 246, 0.3);
        border-color: rgba(139, 92, 246, 0.6);
        color: #ffffff;
        transform: translateY(-1px);
    }
    .btn-avatar-action.remove {
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #fca5a5;
    }
    .btn-avatar-action.remove:hover {
        background: rgba(239, 68, 68, 0.25);
        border-color: rgba(239, 68, 68, 0.5);
        color: #ffffff;
        transform: translateY(-1px);
    }
    .drag-hint-text {
        font-size: 11px;
        color: var(--text-muted);
        font-family: var(--font-th);
    }

    /* Sub-tabs Navigation inside General Info */
    .profile-tabs-header {
        display: flex;
        gap: 6px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 20px;
        padding-bottom: 8px;
    }
    .ptab-btn {
        background: transparent;
        border: none;
        color: var(--text-muted);
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        border-radius: 10px;
        transition: all 0.2s ease;
        font-family: var(--font-th);
    }
    .ptab-btn:hover {
        color: white;
        background: rgba(255, 255, 255, 0.05);
    }
    .ptab-btn.active {
        color: white;
        background: rgba(139, 92, 246, 0.2);
        border: 1px solid rgba(139, 92, 246, 0.4);
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.15);
    }

    /* Form Grid & Input with Icon */
    .form-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }
    .form-grid .full-width {
        grid-column: 1 / -1;
    }
    .input-with-icon {
        position: relative;
        display: flex;
        align-items: center;
        width: 100%;
    }
    .field-icon {
        position: absolute;
        left: 14px;
        font-size: 15px;
        pointer-events: none;
        z-index: 1;
    }
    .input-with-icon input {
        padding-left: 42px !important;
        width: 100%;
    }

    .full-image-overlay {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.85); z-index: 2000;
        display: flex; align-items: center; justify-content: center;
        cursor: zoom-out; backdrop-filter: blur(5px);
    }
    .full-image-overlay img {
        max-width: 90vw; max-height: 90vh; border-radius: var(--radius-md);
        box-shadow: 0 10px 40px rgba(0,0,0,0.5); object-fit: contain;
    }
</style>
