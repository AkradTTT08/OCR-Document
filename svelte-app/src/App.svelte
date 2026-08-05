<script>
  import { fade, fly } from "svelte/transition";
  import UploadPanel from "./lib/UploadPanel.svelte";
  import ResultsPanel from "./lib/ResultsPanel.svelte";
  import KnowledgeBase from "./lib/KnowledgeBase.svelte";
  import SkillManager from "./lib/SkillManager.svelte";
  import { qaHistory, selectedHistory, loadQAHistoryFromDB, selectedProjectStore, qaSessionGroups, activeQAContext, allGroups, loadQAGroupsFromDB } from "./lib/qaHistoryStore.js";
  import Toast from "./lib/Toast.svelte";
  import Login from "./lib/Login.svelte";
  import ComingSoon from "./lib/ComingSoon.svelte";
  import QAConsult from "./lib/QAConsult.svelte";
  import QAMember from "./lib/QAMember.svelte";
  import ExitCriteriaManager from "./lib/ExitCriteriaManager.svelte";
  import { showLogin, authRole, authUser, authDisplayName, authAvatar, logout } from "./lib/authStore.js";
  import { globalSearchQuery, triggerGlobalSearch } from "./lib/globalStore.js";
  import { onMount } from "svelte";
  import { toast } from "./lib/toastStore.js";

  let sidebarProjects = [];

  onMount(async () => {
    loadQAHistoryFromDB();
    loadQAGroupsFromDB();
    // Load projects for sidebar group mapping
    try {
      const res = await fetch('http://127.0.0.1:5000/api/projects');
      if (res.ok) {
        const data = await res.json();
        sidebarProjects = data.projects || [];
      }
    } catch(e) {
      console.error('Failed to load projects for sidebar:', e);
    }
  });

  function handleGroupClick(group) {
    // Find the project for this group
    const proj = sidebarProjects.find(p => (p.id || p.project_id) === group.project_id);
    if (proj) {
      activeView = 'qa_consult';
      activeQAContext.set({ project: proj, group_name: group.group_name, group_type: group.group_type });
    } else {
      // If project not found in list, still try to navigate
      activeView = 'qa_consult';
      activeQAContext.set({ 
        project: { id: group.project_id, project_id: group.project_id, project_code: group.project_code || 'Unknown', name: group.project_code || 'Project' }, 
        group_name: group.group_name, 
        group_type: group.group_type 
      });
    }
  }

  let scanResult = null;
  let isProcessing = false;
  let progress = { pct: 0, label: "", step: 0 };
  let activeView = "ocr"; // 'ocr' | 'kb' | 'skills' | 'qa_consult'

  // Reactive statement to enforce default view based on role
  $: if ($authRole === 'user' && activeView !== 'qa_consult') {
    activeView = 'qa_consult';
  } else if ($authRole === 'admin' && activeView === 'qa_consult') {
    activeView = 'ocr';
  }

  function handleResult(event) {
    scanResult = event.detail;
  }
  function handleProcessing(event) {
    isProcessing = event.detail.active;
    if (event.detail.progress) progress = event.detail.progress;
  }

  function onGlobalSearchKey(e) {
    if (e.key === 'Enter' && $globalSearchQuery.trim()) {
      activeView = 'kb';
      triggerGlobalSearch.set(true);
    }
  }

  let showProfileMenu = false;
  let showMyProfileModal = false;
  let myProfileFormData = { display_name: '', password: '' };
  let showMyPassword = false;
  let myProfileAvatarFile = null;
  let myProfileAvatarPreview = null;
  
  function getUserIdFromToken() {
      const token = localStorage.getItem('jwt_token');
      if (!token) return null;
      try {
          const base64Url = token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const payload = JSON.parse(window.atob(base64));
          return payload.user_id;
      } catch(e) { return null; }
  }
  
  function openMyProfileModal() {
      showProfileMenu = false;
      let currentDisplayName = localStorage.getItem('auth_display_name') || localStorage.getItem('auth_user');
      let currentAvatar = localStorage.getItem('auth_avatar_path');
      myProfileFormData = { display_name: currentDisplayName, password: '' };
      myProfileAvatarFile = null;
      myProfileAvatarPreview = currentAvatar ? `http://localhost:5000${currentAvatar}` : null;
      showMyProfileModal = true;
  }
  
  async function saveMyProfile() {
      const userId = getUserIdFromToken();
      if (!userId) {
          toast('Session invalid. Please login again.', 'error');
          return;
      }
      
      try {
          const token = localStorage.getItem('jwt_token');
          const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
          
          const res = await fetch(`http://localhost:5000/api/users/${userId}`, {
              method: 'PUT',
              headers,
              body: JSON.stringify(myProfileFormData)
          });
          const data = await res.json();
          
          if (res.ok && data.success) {
              let newAvatarPath = data.user.avatar_path;
              if (myProfileAvatarFile) {
                  const fd = new FormData();
                  fd.append('avatar', myProfileAvatarFile);
                  const avaRes = await fetch(`http://localhost:5000/api/users/${userId}/avatar`, {
                      method: 'POST',
                      headers: { 'Authorization': `Bearer ${token}` },
                      body: fd
                  });
                  const avaData = await avaRes.json();
                  if (avaRes.ok && avaData.success) {
                      newAvatarPath = avaData.avatar_path;
                  }
              }
              
              localStorage.setItem('auth_display_name', data.user.display_name);
              if (newAvatarPath) {
                  localStorage.setItem('auth_avatar_path', newAvatarPath);
              }
              toast('Profile updated successfully!', 'success');
              setTimeout(() => { window.location.reload(); }, 1000);
          } else {
              toast(data.error || 'Failed to update profile', 'error');
          }
      } catch (e) {
          toast('Network error', 'error');
      }
  }
  
  function doLogout() {
      showProfileMenu = false;
      logout();
  }

  function formatHistoryDate(dateString) {
    if (!dateString) return "";
    // If the database returns UTC time without a timezone marker, append 'Z'
    // so JS parses it as UTC and correctly converts it to local time.
    let parsedString = dateString;
    if (!parsedString.endsWith('Z') && !parsedString.includes('+')) {
      parsedString += 'Z';
    }
    const d = new Date(parsedString);
    return d.toLocaleString('th-TH', { 
      day: '2-digit', 
      month: '2-digit', 
      year: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit'
    });
  }

  $: projectGroups = (() => {
    if (!$selectedProjectStore) return [];
    const pId = $selectedProjectStore.id || $selectedProjectStore.project_id;
    
    const sessionGs = $qaSessionGroups.filter(g => g.project_id === pId);
    
    const histGs = $qaHistory.filter(h => h.project_id === pId).map(h => ({
      group_name: h.group_name || 'General',
      group_type: h.group_type || 'Project Plan',
      project_id: pId
    }));
    
    const all = [...sessionGs, ...histGs];
    const unique = [];
    const seen = new Set();
    for (let g of all) {
      if (!seen.has(g.group_name)) {
        seen.add(g.group_name);
        unique.push(g);
      }
    }
    return unique;
  })();
</script>

<div class="app-wrapper">
  <!-- ── Animated Spectrum Background ── -->
  <div class="spectrum-bg"></div>
  <div class="spectrum-bg layer-2"></div>

  <div class="app-container">
  {#if $showLogin}
    <Login />
  {:else}
    <!-- ── Sidebar ── -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-icon" style="padding: 2px;">
          <img src="/spectra-favicon.svg" alt="Logo" style="width: 100%; height: 100%; object-fit: contain; border-radius: 4px;" />
        </div>
        <div>
          <div class="logo-title">Spectra QA</div>
          <div class="logo-sub">Intelligent Document Analysis</div>
        </div>
      </div>

      <nav class="sidebar-nav">
        {#if $authRole === 'admin'}
          <button class="nav-item" class:active={activeView === "ocr"} on:click={() => (activeView = "ocr")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"/></svg>
            Scan OCR
          </button>
          <button class="nav-item" class:active={activeView === "kb"} on:click={() => (activeView = "kb")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"></path></svg>
            Knowledge Base
          </button>
          <button class="nav-item" class:active={activeView === "skills"} on:click={() => (activeView = "skills")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"></path></svg>
            AI Skills
          </button>
          <button class="nav-item" class:active={activeView === "qa_member"} on:click={() => (activeView = "qa_member")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
            QA Member
          </button>
          <button class="nav-item" class:active={activeView === "exit_criteria"} on:click={() => (activeView = "exit_criteria")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
            Exit Criteria
          </button>
        {:else if $authRole === 'user'}
          <button class="nav-item" class:active={activeView === "qa_consult"} on:click={() => (activeView = "qa_consult")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            QA Consult
          </button>
          {#if $selectedProjectStore}
            <!-- Groups filtered by selected project -->
            {#if $allGroups.filter(g => g.project_id === ($selectedProjectStore.id || $selectedProjectStore.project_id)).length > 0}
              <div class="history-section">
                <div class="history-title">กลุ่มการตรวจสอบ (Groups)</div>
                <div class="history-list">
                  {#each $allGroups.filter(g => g.project_id === ($selectedProjectStore.id || $selectedProjectStore.project_id)) as group}
                    <button class="history-item group-item" on:click={() => handleGroupClick(group)}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" style="flex-shrink: 0;">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                      </svg>
                      <div class="history-details">
                        <span class="h-filename" style="color: #c4b5fd;">[{group.group_type || 'General'}] {group.group_name}</span>
                        <span class="h-project">{group.project_code}</span>
                        {#if group.scan_count > 0}
                          <span class="h-date">{group.scan_count} ไฟล์ที่ scan แล้ว</span>
                        {:else}
                          <span class="h-date" style="color: #f59e0b;">ยังไม่มีไฟล์</span>
                        {/if}
                      </div>
                    </button>
                  {/each}
                </div>
              </div>
            {/if}

            <!-- History filtered by selected project -->
            {#if $qaHistory.filter(h => h.project_id === ($selectedProjectStore.id || $selectedProjectStore.project_id)).length > 0}
              <div class="history-section">
                <div class="history-title">ประวัติการวิเคราะห์ (History)</div>
                <div class="history-list">
                  {#each $qaHistory.filter(h => h.project_id === ($selectedProjectStore.id || $selectedProjectStore.project_id)).slice(0, 10) as item}
                    <button class="history-item" on:click={() => { activeView = "qa_consult"; selectedHistory.set(item); }}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
                      <div class="history-details">
                        <span class="h-filename">{item.filename}</span>
                        <span class="h-project" style="color: #a78bfa;">
                          {#if item.group_type}[{item.group_type}] {/if}{item.group_name || 'General'}
                        </span>
                        {#if item.date}
                          <span class="h-date">{formatHistoryDate(item.date)}</span>
                        {/if}
                      </div>
                    </button>
                  {/each}
                </div>
              </div>
            {/if}
          {/if}
        {/if}
      </nav>

      <div class="sidebar-footer">
        <button class="btn-logout" on:click={logout}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          Logout
        </button>
      </div>
    </aside>

    <!-- ── Main Workspace ── -->
    <main class="workspace">
      <!-- Topbar -->
      <header class="topbar">
        <div class="breadcrumb">WORKSPACE / <span class="bc-active">{activeView.toUpperCase()}</span></div>
        <div class="topbar-right">
          <div class="search-box">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input type="text" bind:value={$globalSearchQuery} on:keydown={onGlobalSearchKey} placeholder="ค้นหาเอกสารหรือวิเคราะห์..." />
          </div>
          <button class="icon-btn" on:click={() => {
            if ($globalSearchQuery.trim()) {
              activeView = 'kb';
              triggerGlobalSearch.set(true);
            }
          }}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 01-3.46 0"></path></svg>
          </button>
          <div class="status-badge">
            <span class="dot"></span> System Ready
          </div>
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <div class="user-profile-container" style="position: relative;" on:click={() => showProfileMenu = !showProfileMenu}>
            <div class="user-info">
              <span class="user-name">{$authDisplayName || $authUser}</span>
              <span class="user-role">{$authRole === 'admin' ? 'System Admin' : 'Standard User'}</span>
            </div>
            <div class="avatar" title="{$authDisplayName || $authUser} ({$authRole})">
              {#if $authAvatar}
                <img src={`http://localhost:5000${$authAvatar}`} alt="Profile" />
              {:else}
                {$authDisplayName ? $authDisplayName.charAt(0).toUpperCase() : ($authUser ? $authUser.charAt(0).toUpperCase() : 'A')}
              {/if}
            </div>
            
            {#if showProfileMenu}
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <div class="dropdown-overlay" on:click|stopPropagation={() => showProfileMenu = false}></div>
              <div class="profile-dropdown">
                <button class="dropdown-item" on:click|stopPropagation={openMyProfileModal}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                  Profile
                </button>
                <button class="dropdown-item logout-btn" on:click|stopPropagation={doLogout}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                  Logout
                </button>
              </div>
            {/if}
          </div>
        </div>
      </header>

      <!-- Content Area -->
      <div class="content-scroll" id="main-content" class:no-padding={activeView === 'kb' || activeView === 'ocr' || activeView === 'qa_consult' || activeView === 'qa_member'}>
        {#key activeView}
          <div class="view-wrapper" in:fade="{{ duration: 300, delay: 150 }}">
            {#if activeView === "ocr" && $authRole === "admin"}
              <div style="display: {(!isProcessing && !scanResult) ? 'flex' : 'none'}; flex-direction: column; width: 100%; height: 100%;">
                <div class="upload-container" style="flex: 1; padding: 0;">
                  <UploadPanel on:result={handleResult} on:processing={handleProcessing} />
                </div>
              </div>
              {#if isProcessing || scanResult}
                <ResultsPanel result={scanResult} {isProcessing} {progress} on:close={() => {scanResult = null; isProcessing = false;}} />
              {/if}
            {:else if activeView === "kb" && $authRole === "admin"}
              <KnowledgeBase />
            {:else if activeView === "skills" && $authRole === "admin"}
              <SkillManager />
            {:else if activeView === "qa_member" && $authRole === "admin"}
              <QAMember />
            {:else if activeView === "exit_criteria" && $authRole === "admin"}
              <ExitCriteriaManager />
            {:else if activeView === "qa_consult" && $authRole === "user"}
              <QAConsult />
            {/if}
          </div>
        {/key}
      </div>

      <!-- ── Footer ── -->
      <footer class="app-footer">
        <div class="footer-left">
          &copy; 2026 Spectra QA v1.0.4. Powered by Prism AI.
        </div>
        <div class="footer-links">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
          <a href="#">Security Architecture</a>
        </div>
      </footer>
    </main>
  {/if}
  </div>
</div>

<!-- Global Toast Notifications -->
<Toast />

{#if showMyProfileModal}
<div class="modal-backdrop">
    <div class="modal-content glass-card">
        <button class="close-btn" on:click={() => showMyProfileModal = false}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
        
        <h2 class="modal-title">แก้ไขข้อมูลส่วนตัว</h2>
        
        <div class="avatar-upload-container">
            <div class="avatar-preview">
                {#if myProfileAvatarPreview}
                    <img src={myProfileAvatarPreview} alt="Preview" />
                {:else}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                {/if}
            </div>
            <div class="upload-btn-wrapper">
                <button class="btn-secondary btn-sm" type="button">เปลี่ยนรูปโปรไฟล์</button>
                <input type="file" accept="image/*" on:change={(e) => {
                    const file = e.target.files[0];
                    if (file) {
                        myProfileAvatarFile = file;
                        myProfileAvatarPreview = URL.createObjectURL(file);
                    }
                }} />
            </div>
        </div>
        
        <div class="form-group">
            <label for="my_display_name">Display Name</label>
            <input type="text" id="my_display_name" bind:value={myProfileFormData.display_name} placeholder="e.g. John Doe" />
        </div>
        
        <div class="form-group">
            <label>Password (ปล่อยว่างหากไม่ต้องการเปลี่ยน)</label>
            <div style="display: flex; gap: 8px; align-items: center; position: relative;">
                <input type={showMyPassword ? "text" : "password"} bind:value={myProfileFormData.password} placeholder="••••••••" style="flex: 1; padding-right: 40px;" />
                <button type="button" class="eye-btn" on:click={() => showMyPassword = !showMyPassword}>
                    {#if showMyPassword}
                        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                    {:else}
                        <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    {/if}
                </button>
            </div>
        </div>
        
        <div class="modal-actions">
            <button class="btn-secondary" on:click={() => showMyProfileModal = false}>ยกเลิก</button>
            <button class="btn-primary" on:click={saveMyProfile}>บันทึกข้อมูล</button>
        </div>
    </div>
</div>
{/if}

<style>
  .app-wrapper {
    position: relative;
    width: 100vw;
    height: 100vh;
    background-color: transparent; /* Changed from var(--bg-dark) to show body animated background */
    overflow: hidden;
  }

  /* ── Animated Spectrum Background ── */
  .spectrum-bg {
    position: absolute;
    width: 150vw;
    height: 150vh;
    top: -25vh;
    left: -25vw;
    background: conic-gradient(
        from 180deg at 50% 50%,
        var(--bg-dark) 0deg,
        var(--danger) 60deg,
        var(--warning) 120deg,
        var(--success) 180deg,
        var(--primary) 240deg,
        var(--secondary) 300deg,
        var(--bg-dark) 360deg
    );
    filter: blur(140px);
    opacity: 0.15;
    animation: spin 30s linear infinite;
    z-index: 0;
    pointer-events: none;
  }
  
  .spectrum-bg.layer-2 {
    background: radial-gradient(circle at 70% 30%, rgba(99, 102, 241, 0.25), transparent 40%),
                radial-gradient(circle at 30% 70%, rgba(168, 85, 247, 0.25), transparent 40%);
    filter: blur(90px);
    opacity: 0.6;
    animation: pulse 15s ease-in-out infinite alternate;
    z-index: 0;
  }

  @keyframes spin { 100% { transform: rotate(360deg); } }
  @keyframes pulse { 0% { transform: scale(1); } 100% { transform: scale(1.1); } }

  .app-container {
    position: relative;
    z-index: 1;
    display: flex;
    height: 100vh;
    color: var(--text-main);
    font-family: var(--font-th);
  }

  /* ── Sidebar ── */
  .sidebar {
    width: 260px;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border-right: 1px solid var(--glass-border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    z-index: 10;
    box-shadow: 4px 0 24px rgba(0,0,0,0.2);
  }

  .sidebar-logo {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 20px 20px 16px;
    border-bottom: 1px solid var(--glass-border);
  }

  .logo-icon {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }

  .logo-title {
    font-family: var(--font-en);
    font-size: 18px;
    font-weight: 700;
    background: var(--gradient-text);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    line-height: 1.2;
    letter-spacing: 0.5px;
  }
  
  .logo-sub {
    font-family: var(--font-en);
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 500;
    letter-spacing: 0.5px;
  }

  .sidebar-nav {
    flex: 1;
    padding: 10px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    color: var(--text-muted);
    font-family: var(--font-en);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    text-align: left;
    position: relative;
    overflow: hidden;
  }

  .nav-item:hover {
    color: var(--text-main);
    background: var(--glass-bg-hover);
    border-color: var(--glass-border);
  }

  .nav-item.active {
    color: #fff;
    background: rgba(99, 102, 241, 0.15); /* Primary tint */
    border-color: rgba(99, 102, 241, 0.3);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
  }

  .nav-item.active::before {
    content: '';
    position: absolute;
    left: 0; top: 0; height: 100%; width: 4px;
    background: var(--gradient-main);
    border-radius: 0 4px 4px 0;
  }
  
  .nav-item.active svg {
    color: var(--secondary);
    filter: drop-shadow(0 0 8px rgba(168, 85, 247, 0.5));
  }

  .history-section {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--glass-border);
  }
  .history-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    margin-bottom: 8px;
    padding-left: 8px;
  }
  .history-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .history-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    background: transparent;
    border: none;
    padding: 8px;
    border-radius: 6px;
    cursor: pointer;
    text-align: left;
    transition: background 0.2s;
    color: var(--text-muted);
  }
  .history-item:hover {
    background: var(--glass-bg-hover);
    color: var(--text-main);
  }
  .history-item.group-item {
    border-left: 3px solid transparent;
    padding-left: 10px;
    transition: all 0.2s ease;
  }
  .history-item.group-item:hover {
    border-left-color: #8b5cf6;
    background: rgba(139, 92, 246, 0.08);
  }
  .history-item svg {
    margin-top: 2px;
    flex-shrink: 0;
  }
  .history-details {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .h-filename {
    font-size: 13px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .h-project {
    font-size: 10px;
    color: var(--secondary);
    opacity: 0.8;
  }
  .h-date {
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .sidebar-footer {
    padding: 20px 16px;
    border-top: 1px solid var(--glass-border);
  }

  .btn-logout {
    display: flex; align-items: center; gap: 10px;
    width: 100%; padding: 12px;
    background: transparent; border: 1px solid transparent;
    color: var(--danger); font-size: 14px; font-weight: 500; cursor: pointer;
    border-radius: var(--radius-md); transition: all 0.3s;
  }
  .btn-logout:hover {
    background: rgba(244, 63, 94, 0.1);
    border-color: rgba(244, 63, 94, 0.2);
  }

  /* ── Main Workspace ── */
  .workspace {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-width: 0;
    position: relative;
    background: rgba(18, 20, 28, 0.2);
  }

  /* Topbar */
  .topbar {
    height: 70px;
    padding: 0 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--glass-border);
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    z-index: 5;
  }

  .breadcrumb {
    font-family: var(--font-en);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-dim);
    letter-spacing: 1.5px;
  }
  .bc-active { color: var(--text-muted); }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .search-box {
    display: flex; align-items: center; gap: 8px;
    background: var(--glass-bg-hover);
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 8px 16px;
    width: 260px;
    transition: border-color 0.3s;
  }
  .search-box:focus-within {
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 0 10px rgba(99, 102, 241, 0.15);
  }
  .search-box input {
    background: transparent; border: none; outline: none;
    color: var(--text-main); font-size: 13px; width: 100%;
    font-family: var(--font-th);
  }
  .search-box svg { color: var(--text-muted); }

  .icon-btn {
    background: var(--glass-bg-hover);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    border-radius: 50%;
    width: 36px; height: 36px;
    cursor: pointer; position: relative;
    display: flex; align-items: center; justify-content: center;
    transition: all 0.3s;
  }
  .icon-btn:hover {
    color: var(--text-main);
    border-color: var(--glass-border-light);
    transform: scale(1.05);
  }
  .icon-btn::after {
    content: ''; position: absolute; top: -1px; right: -1px;
    width: 10px; height: 10px; background: var(--danger); border-radius: 50%;
    border: 2px solid var(--bg-dark);
  }

  .status-badge {
    display: flex; align-items: center; gap: 6px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.2);
    padding: 6px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 500; color: var(--success);
    font-family: var(--font-en);
  }
  .dot {
    width: 8px; height: 8px; background: var(--success); border-radius: 50%;
    box-shadow: 0 0 8px var(--success);
  }

  .user-profile-container {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    padding: 4px 12px 4px 16px;
    border-radius: 30px;
    transition: background 0.3s;
    border: 1px solid transparent;
  }
  .user-profile-container:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
  }
  .user-info {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }
  .user-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-main);
    line-height: 1.2;
    font-family: var(--font-th);
  }
  .user-role {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-en);
  }

  .avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--gradient-main);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px;
    font-family: var(--font-en);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    transition: transform 0.3s;
    overflow: hidden;
  }
  .avatar img {
    width: 100%; height: 100%; object-fit: cover;
  }
  .user-profile-container:hover .avatar { transform: scale(1.05); }

  /* Content Scroll */
  .content-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 32px;
    position: relative;
    scroll-behavior: smooth;
    display: flex;
    flex-direction: column;
  }
  .content-scroll.no-padding {
    padding: 0;
    overflow: hidden;
  }
  .view-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .upload-container {
    padding: 32px;
    flex: 1;
  }

  /* Responsive */
  @media (max-width: 900px) {
    .app-container { flex-direction: column; }
    .sidebar { width: 100%; height: auto; border-right: none; border-bottom: 1px solid var(--glass-border); }
    .sidebar-nav { flex-direction: row; overflow-x: auto; }
    .nav-item.active::before { left: 10%; top: 100%; width: 80%; height: 4px; border-radius: 4px 4px 0 0; }
    .topbar { display: none; }
  }

  /* ── Footer ── */
  .app-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 32px;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border-top: 1px solid var(--glass-border);
    font-size: 12px;
    color: var(--text-dim);
    flex-shrink: 0;
    font-family: var(--font-en);
  }
  .footer-links {
    display: flex;
    gap: 24px;
  }
  .footer-links a {
    color: var(--text-dim);
    text-decoration: none;
    transition: color 0.2s;
  }
  .footer-links a:hover {
    color: var(--text-muted);
  }

  /* Profile Dropdown */
  .dropdown-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    z-index: 90;
  }
  .profile-dropdown {
    position: absolute; top: 100%; right: 0; margin-top: 10px;
    background: var(--bg-dark); border: 1px solid var(--glass-border);
    border-radius: var(--radius-md); box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    padding: 8px; z-index: 100; min-width: 160px;
    display: flex; flex-direction: column; gap: 4px;
  }
  .dropdown-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px; background: transparent; border: none;
    color: var(--text-main); font-size: 13px; font-family: var(--font-en);
    border-radius: 6px; cursor: pointer; transition: all 0.2s;
    text-align: left;
  }
  .dropdown-item:hover {
    background: rgba(255,255,255,0.05);
  }
  .dropdown-item svg { width: 16px; height: 16px; color: var(--text-muted); }
  .logout-btn:hover { background: rgba(239, 68, 68, 0.1); color: var(--danger); }
  .logout-btn:hover svg { color: var(--danger); }

  /* Modal Base */
  .modal-backdrop {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.75); z-index: 1000;
    display: flex; align-items: center; justify-content: center;
    backdrop-filter: blur(5px);
  }
  .modal-content {
    background: var(--bg-dark); border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg); padding: 32px; width: 100%; max-width: 500px;
    position: relative; box-shadow: 0 20px 50px rgba(0,0,0,0.5);
  }
  .close-btn {
    position: absolute; top: 20px; right: 20px;
    background: transparent; border: none; color: var(--text-muted);
    cursor: pointer; transition: color 0.2s;
  }
  .close-btn:hover { color: white; }
  .close-btn svg { width: 24px; height: 24px; }
  .modal-title {
    font-size: 20px; font-weight: 600; margin-top: 0; margin-bottom: 24px;
    color: white; font-family: var(--font-th);
  }

  /* Form & Avatar in Modal */
  .form-group {
    display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px;
    text-align: left;
  }
  .form-group label {
    font-size: 13px; color: var(--text-muted); font-weight: 500; font-family: var(--font-en);
  }
  .form-group input {
    background: rgba(0,0,0,0.2); border: 1px solid var(--glass-border);
    border-radius: var(--radius-md); padding: 12px 15px; color: white;
    font-size: 14px; font-family: var(--font-en); transition: border-color 0.3s;
  }
  .form-group input:focus { border-color: var(--primary); outline: none; }
  
  .eye-btn {
    position: absolute; right: 12px; background: transparent; border: none;
    color: var(--text-muted); cursor: pointer; display: flex; align-items: center;
    justify-content: center; padding: 4px; border-radius: 4px; transition: color 0.2s;
  }
  .eye-btn:hover { color: var(--text-main); }
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
  .modal-actions {
    display: flex; justify-content: flex-end; gap: 10px; margin-top: 25px;
  }
  .btn-secondary {
    background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border);
    color: white; padding: 10px 20px; border-radius: var(--radius-md);
    cursor: pointer; transition: background 0.2s; font-family: var(--font-th);
  }
  .btn-secondary:hover { background: rgba(255,255,255,0.1); }
  .btn-sm { padding: 6px 12px; font-size: 13px; }
</style>
