<script>
  import { fade, fly } from "svelte/transition";
  import UploadPanel from "./lib/UploadPanel.svelte";
  import ResultsPanel from "./lib/ResultsPanel.svelte";
  import KnowledgeBase from "./lib/KnowledgeBase.svelte";
  import SkillManager from "./lib/SkillManager.svelte";
  import Toast from "./lib/Toast.svelte";
  import Login from "./lib/Login.svelte";
  import ComingSoon from "./lib/ComingSoon.svelte";
  import QAConsult from "./lib/QAConsult.svelte";
  import { showLogin, authRole, authUser, logout } from "./lib/authStore.js";

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
</script>

<div class="app-wrapper">
  <!-- Glowing Background Orbs -->
  <div class="bg-glow glow-1"></div>
  <div class="bg-glow glow-2"></div>
  <div class="bg-glow glow-3"></div>

  <div class="app-container">
  {#if $showLogin}
    <Login />
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
        {:else if $authRole === 'user'}
          <button class="nav-item" class:active={activeView === "qa_consult"} on:click={() => (activeView = "qa_consult")}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            QA Consult
          </button>
        {/if}
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
      <div class="content-scroll" id="main-content" class:no-padding={activeView === 'kb' || activeView === 'ocr' || activeView === 'qa_consult'}>
        {#key activeView}
          <div class="view-wrapper" in:fade="{{ duration: 300, delay: 150 }}">
            {#if activeView === "ocr" && $authRole === "admin"}
              <div style="display: {(!isProcessing && !scanResult) ? 'block' : 'none'}; width: 100%;">
                <div class="upload-container">
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

<style>
  .app-wrapper {
    position: relative;
    width: 100vw;
    height: 100vh;
    background-color: var(--bg-dark);
    overflow: hidden;
  }

  /* ── Ambient Background Glows ── */
  .bg-glow {
    position: absolute;
    border-radius: 50%;
    filter: blur(120px);
    opacity: 0.6;
    z-index: 0;
    pointer-events: none;
    animation: float 20s ease-in-out infinite alternate;
  }
  .glow-1 {
    top: -10%; left: -5%; width: 400px; height: 400px;
    background: rgba(99, 102, 241, 0.35); /* Primary */
  }
  .glow-2 {
    bottom: -10%; right: -5%; width: 500px; height: 500px;
    background: rgba(168, 85, 247, 0.25); /* Secondary */
    animation-delay: -5s;
  }
  .glow-3 {
    top: 40%; left: 50%; width: 300px; height: 300px;
    background: rgba(6, 182, 212, 0.2); /* Accent */
    animation-delay: -10s;
  }

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

  .avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--gradient-main);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; cursor: pointer;
    font-family: var(--font-en);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    transition: transform 0.3s;
  }
  .avatar:hover { transform: scale(1.05); }

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
</style>
