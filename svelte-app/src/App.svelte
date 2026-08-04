<script>
<<<<<<< HEAD
  import { fade, fly } from 'svelte/transition';
  import UploadPanel from './lib/UploadPanel.svelte';
  import ResultsPanel from './lib/ResultsPanel.svelte';
  import KnowledgeBase from './lib/KnowledgeBase.svelte';
  import SkillManager from './lib/SkillManager.svelte';
  import Toast from './lib/Toast.svelte';

  let scanResult = null;
  let isProcessing = false;
  let progress = { pct: 0, label: '', step: 0 };
  let activeView = 'ocr'; // 'ocr' | 'kb' | 'skills'
=======
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
>>>>>>> df856a56efb793dd0e86bd37d93ef75eb31e12db

  function handleResult(event) {
    scanResult = event.detail;
  }
  function handleProcessing(event) {
    isProcessing = event.detail.active;
    if (event.detail.progress) progress = event.detail.progress;
  }
</script>

<<<<<<< HEAD
<div class="shell">
  <!-- ── Left Panel ── -->
  <aside class="left-panel" class:collapsed-left={activeView === 'skills'}>
    <header class="panel-header">
      <div class="logo">
        <div class="logo-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="12 3 3 21 21 21"></polygon>
            <line x1="3" y1="14" x2="21" y2="14"></line>
            <line x1="8" y1="10" x2="16" y2="10"></line>
          </svg>
=======
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
>>>>>>> df856a56efb793dd0e86bd37d93ef75eb31e12db
        </div>
        <div>
          <div class="logo-title">Spectra QA</div>
          <div class="logo-sub">Intelligent Document Analysis</div>
        </div>
      </div>

<<<<<<< HEAD
      <!-- Nav tabs -->
      <nav class="nav-tabs">
        <button
          id="nav-ocr"
          class="nav-tab"
          class:active={activeView === 'ocr'}
          on:click={() => activeView = 'ocr'}
        >
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
            <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clip-rule="evenodd"/>
          </svg>
          Scan OCR
        </button>
        <button
          id="nav-kb"
          class="nav-tab"
          class:active={activeView === 'kb'}
          on:click={() => activeView = 'kb'}
        >
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
            <path d="M3 12v3c0 1.657 3.134 3 7 3s7-1.343 7-3v-3c0 1.657-3.134 3-7 3s-7-1.343-7-3z"/>
            <path d="M3 7v3c0 1.657 3.134 3 7 3s7-1.343 7-3V7c0 1.657-3.134 3-7 3S3 8.657 3 7z"/>
            <path d="M17 5c0 1.657-3.134 3-7 3S3 6.657 3 5s3.134-3 7-3 7 1.343 7 3z"/>
          </svg>
          Knowledge Base
        </button>
        <button
          id="nav-skills"
          class="nav-tab"
          class:active={activeView === 'skills'}
          on:click={() => activeView = 'skills'}
        >
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
            <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 103.636 5.05l-.707.707a1 1 0 001.414 1.414l.707-.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1a1 1 0 112 0v1a1 1 0 11-2 0zM12 14a1 1 0 100-2 1 1 0 000 2z"/>
          </svg>
          AI Skills
        </button>
=======
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
>>>>>>> df856a56efb793dd0e86bd37d93ef75eb31e12db
      </nav>
    </header>

    {#key activeView}
      <div style="flex:1; display:flex; flex-direction:column; overflow:hidden;" in:fade="{{ duration: 300, delay: 150 }}">
        {#if activeView === "ocr"}
          <UploadPanel on:result={handleResult} on:processing={handleProcessing} />
        {:else if activeView === "kb"}
          <div class="kb-hint">
            <p>เลือกโครงการและเอกสารในพื้นที่หลัก เพื่อดูข้อมูล Knowledge Base</p>
          </div>
        {/if}
      </div>
    {/key}
  </aside>

<<<<<<< HEAD
  <!-- ── Right Panel ── -->
  <main class="right-panel">
    {#key activeView}
      <div style="width:100%; height:100%;" in:fly="{{ y: 20, duration: 400, delay: 150 }}" out:fade="{{ duration: 150 }}">
        {#if activeView === "ocr"}
          <ResultsPanel result={scanResult} {isProcessing} {progress} on:close={() => {scanResult = null; isProcessing = false;}} />
        {:else if activeView === "kb"}
          <KnowledgeBase />
        {:else if activeView === "skills"}
          <SkillManager />
        {/if}
      </div>
    {/key}
  </main>
=======
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
>>>>>>> df856a56efb793dd0e86bd37d93ef75eb31e12db
</div>

<!-- Global Toast Notifications -->
<Toast />

<style>
<<<<<<< HEAD
  .shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }

  /* ── Left ── */
  .left-panel {
    width: var(--panel-w);
    flex-shrink: 0;
    background: var(--bg2);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
=======
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
>>>>>>> df856a56efb793dd0e86bd37d93ef75eb31e12db
  }

  .panel-header {
    padding: 18px 22px 14px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }

  .logo-icon {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 16px var(--glow);
    flex-shrink: 0;
  }
  .logo-icon svg { color: #fff; stroke: #fff; }

  .logo-title {
    font-size: 15px; font-weight: 700; color: var(--text);
    line-height: 1.2;
  }
  .logo-sub {
    font-size: 11px; color: var(--text3);
    margin-top: 2px;
  }

  /* Nav tabs */
  .nav-tabs {
    display: flex;
    gap: 6px;
  }
  .nav-tab {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
<<<<<<< HEAD
    gap: 6px;
    padding: 8px 6px;
    border: 1px solid var(--border);
    border-radius: 9px;
    background: transparent;
    color: var(--text3);
    font-family: var(--font-th, inherit);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  .nav-tab:hover {
    background: rgba(108,142,251,0.07);
    color: var(--text2);
  }
  .nav-tab.active {
    background: rgba(108,142,251,0.16);
    border-color: var(--primary);
    color: var(--primary);
    font-weight: 700;
    box-shadow: 0 0 10px var(--glow);
  }

  /* KB hint when KB view active */
  .kb-hint {
    padding: 20px 18px;
    color: var(--text3);
    font-size: 13px;
    line-height: 1.6;
  }

  /* ── Right ── */
  .right-panel {
=======
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
>>>>>>> df856a56efb793dd0e86bd37d93ef75eb31e12db
    flex: 1;
    min-width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
<<<<<<< HEAD
    background: var(--bg);
  }

  /* Responsive */
  @media (max-width: 780px) {
    .shell { flex-direction: column; overflow: auto; }
    .left-panel { width: 100%; border-right: none; border-bottom: 1px solid var(--border); }
    .right-panel { flex: none; min-height: 60vh; }
=======
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
>>>>>>> df856a56efb793dd0e86bd37d93ef75eb31e12db
  }
</style>
