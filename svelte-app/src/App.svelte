<script>
  import { fade, fly } from "svelte/transition";
  import UploadPanel from "./lib/UploadPanel.svelte";
  import ResultsPanel from "./lib/ResultsPanel.svelte";
  import KnowledgeBase from "./lib/KnowledgeBase.svelte";
  import SkillManager from "./lib/SkillManager.svelte";
  import Toast from "./lib/Toast.svelte";
  import Login from "./lib/Login.svelte";
  import ComingSoon from "./lib/ComingSoon.svelte";
  import { showLogin, authRole, authUser, logout } from "./lib/authStore.js";

  let scanResult = null;
  let isProcessing = false;
  let progress = { pct: 0, label: "", step: 0 };
  let activeView = "ocr"; // 'ocr' | 'kb' | 'skills'

  function handleResult(event) {
    scanResult = event.detail;
  }
  function handleProcessing(event) {
    isProcessing = event.detail.active;
    if (event.detail.progress) progress = event.detail.progress;
  }
</script>

<div class="app-container">
  {#if $showLogin}
    <Login />
  {:else if $authRole !== 'admin'}
    <ComingSoon />
  {:else}
    <!-- ── Sidebar ── -->
    <aside class="sidebar">
      <div class="sidebar-logo">
        <div class="logo-icon" style="padding: 2px;">
          <img src="/screen.png" alt="Logo" style="width: 100%; height: 100%; object-fit: contain; border-radius: 4px;" />
        </div>
        <div class="logo-text">
          <div class="logo-title">Spectra QA</div>
          <div class="logo-sub">Intelligent Analysis</div>
        </div>
      </div>

      <nav class="sidebar-nav">
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
      </nav>

      <div class="sidebar-footer">
        <button class="btn-logout" on:click={logout}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
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
            <input type="text" placeholder="ค้นหาเอกสารหรือวิเคราะห์..." />
          </div>
          <button class="icon-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 01-3.46 0"></path></svg>
          </button>
          <div class="status-badge">
            <span class="dot"></span> System Ready
          </div>
          <div class="avatar" title="{$authUser} ({$authRole})">
            {$authUser ? $authUser.charAt(0).toUpperCase() : 'A'}
          </div>
        </div>
      </header>

      <!-- Content Area -->
      <div class="content-scroll" id="main-content">
        {#key activeView}
          <div in:fade="{{ duration: 300, delay: 150 }}">
            {#if activeView === "ocr"}
              {#if isProcessing || scanResult}
                <ResultsPanel result={scanResult} {isProcessing} {progress} on:close={() => {scanResult = null; isProcessing = false;}} />
              {/if}
              <div style:display={isProcessing || scanResult ? 'none' : 'contents'}>
                <UploadPanel on:result={handleResult} on:processing={handleProcessing} />
              </div>
            {:else if activeView === "kb"}
              <KnowledgeBase />
            {:else if activeView === "skills"}
              <SkillManager />
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

<!-- Global Toast Notifications -->
<Toast />

<style>
  .app-container {
    display: flex;
    height: 100vh;
    background: #090a0f;
    color: #f1f5f9;
    font-family: 'Prompt', sans-serif;
    overflow: hidden;
  }

  /* ── Sidebar ── */
  .sidebar {
    width: 260px;
    background: #0f111a;
    border-right: 1px solid rgba(255,255,255,0.05);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    z-index: 10;
  }

  .sidebar-logo {
    padding: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .logo-icon {
    width: 32px;
    height: 32px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .logo-title {
    font-size: 16px;
    font-weight: 700;
    color: #fff;
    line-height: 1.2;
  }
  
  .logo-sub {
    font-size: 11px;
    color: #64748b;
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
    border: none;
    border-radius: 10px;
    color: #94a3b8;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
    position: relative;
  }

  .nav-item:hover {
    color: #fff;
    background: rgba(255,255,255,0.03);
  }

  .nav-item.active {
    color: #fff;
    background: rgba(139, 92, 246, 0.1);
  }

  .nav-item.active::before {
    content: '';
    position: absolute;
    left: 0; top: 10%; height: 80%; width: 4px;
    background: linear-gradient(to bottom, #a855f7, #ec4899);
    border-radius: 0 4px 4px 0;
  }
  
  .nav-item.active svg {
    color: #c084fc;
  }

  .sidebar-footer {
    padding: 20px 16px;
    border-top: 1px solid rgba(255,255,255,0.05);
  }

  .btn-logout {
    display: flex; align-items: center; gap: 10px;
    width: 100%; padding: 12px;
    background: transparent; border: none;
    color: #ef4444; font-size: 14px; cursor: pointer;
    border-radius: 8px; transition: background 0.2s;
  }
  .btn-logout:hover {
    background: rgba(239, 68, 68, 0.1);
  }

  /* ── Main Workspace ── */
  .workspace {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    position: relative;
  }

  /* Topbar */
  .topbar {
    height: 70px;
    padding: 0 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    background: rgba(9, 10, 15, 0.8);
    backdrop-filter: blur(10px);
    z-index: 5;
  }

  .breadcrumb {
    font-size: 12px;
    font-weight: 600;
    color: #475569;
    letter-spacing: 1px;
  }
  .bc-active { color: #94a3b8; }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 20px;
  }

  .search-box {
    display: flex; align-items: center; gap: 8px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    padding: 6px 14px;
    width: 250px;
  }
  .search-box input {
    background: transparent; border: none; outline: none;
    color: #fff; font-size: 13px; width: 100%;
  }
  .search-box svg { color: #64748b; }

  .icon-btn {
    background: transparent; border: none; color: #94a3b8;
    cursor: pointer; position: relative;
    display: flex; align-items: center; justify-content: center;
  }
  .icon-btn::after {
    content: ''; position: absolute; top: -2px; right: -2px;
    width: 8px; height: 8px; background: #ec4899; border-radius: 50%;
  }

  .status-badge {
    display: flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,0.05);
    padding: 6px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 500; color: #cbd5e1;
  }
  .dot {
    width: 8px; height: 8px; background: #10b981; border-radius: 50%;
    box-shadow: 0 0 8px #10b981;
  }

  .avatar {
    width: 32px; height: 32px; border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6, #a855f7);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; cursor: pointer;
  }

  /* Content Scroll */
  .content-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 32px;
    position: relative;
  }

  /* Responsive */
  @media (max-width: 900px) {
    .app-container { flex-direction: column; }
    .sidebar { width: 100%; height: auto; border-right: none; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .sidebar-nav { flex-direction: row; overflow-x: auto; }
    .nav-item.active::before { left: 10%; top: 100%; width: 80%; height: 4px; border-radius: 4px 4px 0 0; }
    .topbar { display: none; }
  }

  /* ── Footer ── */
  .app-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 32px;
    background: #0f111a;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 11px;
    color: #64748b;
    flex-shrink: 0;
  }
  .footer-links {
    display: flex;
    gap: 24px;
  }
  .footer-links a {
    color: #64748b;
    text-decoration: none;
    transition: color 0.2s;
  }
  .footer-links a:hover {
    color: #94a3b8;
  }
</style>
