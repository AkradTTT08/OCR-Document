<script>
    import { onMount } from 'svelte';
    import { toast } from './toastStore.js';
    import { authUser } from './authStore.js';

    let users = [];
    let isLoading = true;
    let searchQuery = '';
    let roleFilter = 'all';

    let avatarFile = null;
    let avatarPreview = null;
    let showFullImage = false;

    // Modal state
    let showModal = false;
    let isEditMode = false;
    let formData = {
        user_id: null,
        username: '',
        email: '',
        display_name: '',
        password: '',
        role: 'user'
    };

    let confirmModal = {
        show: false,
        title: '',
        message: '',
        action: null
    };

    onMount(async () => {
        await fetchUsers();
    });

    async function fetchUsers() {
        isLoading = true;
        try {
            const res = await fetch('http://localhost:5000/api/users');
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

    async function handleToggleStatus(user) {
        const newStatus = !user.is_active;
        try {
            const res = await fetch(`http://localhost:5000/api/users/${user.user_id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
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
                    const res = await fetch(`http://localhost:5000/api/users/${user.user_id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ role: newRole })
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                        user.role = newRole;
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
                    const res = await fetch(`http://localhost:5000/api/users/${user.user_id}`, {
                        method: 'DELETE'
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
        formData = { user_id: null, username: '', email: '', display_name: '', password: 'Spectra123', role: 'user', avatar_path: null };
        avatarFile = null;
        avatarPreview = null;
        showModal = true;
    }

    function openEditModal(user) {
        isEditMode = true;
        formData = { 
            user_id: user.user_id, 
            username: user.username, 
            email: user.email, 
            display_name: user.display_name, 
            password: '', 
            role: user.role,
            avatar_path: user.avatar_path
        };
        avatarFile = null;
        avatarPreview = user.avatar_path ? `http://localhost:5000${user.avatar_path}` : null;
        showModal = true;
    }

    async function handleSaveUser() {
        if (!formData.username || !formData.email || !formData.display_name || (!isEditMode && !formData.password)) {
            toast('Please fill all required fields', 'warning');
            return;
        }

        const url = isEditMode ? `http://localhost:5000/api/users/${formData.user_id}` : 'http://localhost:5000/api/users';
        const method = isEditMode ? 'PUT' : 'POST';
        
        try {
            const res = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
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
                        await fetch(`http://localhost:5000/api/users/${userId}/avatar`, {
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
            <p class="page-subtitle">จัดการข้อมูลสมาชิก สิทธิ์การเข้าถึง และสถานะผู้ใช้งานในระบบ</p>
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
            <select bind:value={roleFilter}>
                <option value="all">ทุกระดับสิทธิ์ (All)</option>
                <option value="admin">ผู้ดูแลระบบ (Admin)</option>
                <option value="user">ผู้ใช้ทั่วไป (User)</option>
            </select>
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
                                            <img src={`http://localhost:5000${user.avatar_path}`} alt="Avatar" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;" />
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
                                    <button class="icon-btn edit" on:click={() => openEditModal(user)} title="แก้ไข">
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

<!-- Create / Edit Modal -->
{#if showModal}
<div class="modal-backdrop">
    <div class="modal-content glass-card">
        <button class="close-btn" on:click={() => showModal = false}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
        
        <h2 class="modal-title">{isEditMode ? 'แก้ไขข้อมูลผู้ใช้งาน' : 'เพิ่มผู้ใช้งานใหม่'}</h2>
        
        <div class="avatar-upload-container">
            <div class="avatar-preview">
                {#if avatarPreview}
                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                    <img src={avatarPreview} alt="Preview" style="cursor: zoom-in;" on:click={() => showFullImage = true} />
                {:else}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                {/if}
            </div>
            <div class="upload-btn-wrapper">
                <button class="btn-secondary btn-sm" type="button">อัปโหลดรูปโปรไฟล์</button>
                <input type="file" accept="image/*" on:change={(e) => {
                    const file = e.target.files[0];
                    if (file) {
                        avatarFile = file;
                        avatarPreview = URL.createObjectURL(file);
                    }
                }} />
            </div>
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
            <label for="display_name">Display Name *</label>
            <input type="text" id="display_name" bind:value={formData.display_name} placeholder="e.g. John Doe" />
        </div>
        
        <div class="form-group">
            <label>Password</label>
            <div style="display: flex; flex-direction: column; gap: 8px;">
                <button type="button" class="btn-warning" on:click={() => formData.password = 'Spectra123'}>
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
            <select id="role" bind:value={formData.role}>
                <option value="user">ผู้ใช้ทั่วไป (Standard User)</option>
                <option value="admin">ผู้ดูแลระบบ (Admin)</option>
            </select>
        </div>
        
        <div class="modal-actions">
            <button class="btn-secondary" on:click={() => showModal = false}>ยกเลิก</button>
            <button class="btn-primary" on:click={handleSaveUser}>บันทึกข้อมูล</button>
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

    /* Modal */
    .modal-backdrop {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.6); backdrop-filter: blur(5px);
        display: flex; align-items: center; justify-content: center;
        z-index: 100;
    }
    .modal-content {
        width: 100%; max-width: 450px;
        padding: 30px; position: relative;
        background: var(--bg-dark);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-xl);
    }
    .close-btn {
        position: absolute; top: 20px; right: 20px;
        background: none; border: none; color: var(--text-muted);
        cursor: pointer; transition: color 0.2s;
    }
    .close-btn:hover { color: white; }
    .close-btn svg { width: 24px; height: 24px; }
    
    .modal-title { font-size: 20px; margin: 0 0 20px; }
    
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

    .confirm-dialog {
        max-width: 400px; padding: 24px 32px; text-align: center;
    }
    .confirm-dialog .modal-title {
        color: var(--danger) !important;
    }
    
    .modal-actions {
        display: flex; justify-content: flex-end; gap: 10px; margin-top: 25px;
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

    .avatar-upload-container {
        display: flex; align-items: center; gap: 20px; margin-bottom: 20px;
    }
    .avatar-preview {
        width: 60px; height: 60px; border-radius: 50%;
        background: rgba(255,255,255,0.05); border: 1px dashed var(--glass-border);
        display: flex; align-items: center; justify-content: center; overflow: hidden;
    }
    .avatar-preview img { width: 100%; height: 100%; object-fit: cover; }
    .avatar-preview svg { width: 30px; height: 30px; color: var(--text-muted); }
    
    .upload-btn-wrapper { position: relative; overflow: hidden; display: inline-block; }
    .upload-btn-wrapper input[type=file] {
        font-size: 100px; position: absolute; left: 0; top: 0; opacity: 0; cursor: pointer;
    }
    .btn-sm { padding: 6px 12px; font-size: 13px; }
    
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
