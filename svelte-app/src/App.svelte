<script>
  import UploadPanel from './lib/UploadPanel.svelte';
  import ResultsPanel from './lib/ResultsPanel.svelte';
  import KnowledgeBase from './lib/KnowledgeBase.svelte';
  import Toast from './lib/Toast.svelte';

  let scanResult = null;
  let isProcessing = false;
  let progress = { pct: 0, label: '', step: 0 };
  let activeView = 'ocr'; // 'ocr' | 'kb'

  function handleResult(event) {
    scanResult = event.detail;
  }
  function handleProcessing(event) {
    isProcessing = event.detail.active;
    if (event.detail.progress) progress = event.detail.progress;
  }
</script>

<div class="shell">
  <!-- ── Left Panel ── -->
  <aside class="left-panel">
    <header class="panel-header">
      <div class="logo">
        <div class="logo-icon">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18">
            <path d="M9 2H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8L13 2H9z"/>
            <path d="M13 2v6h6M7 13h6M7 10h3"/>
          </svg>
        </div>
        <div>
          <div class="logo-title">OCR ตรวจเอกสาร</div>
          <div class="logo-sub">พจนานุกรมราชบัณฑิตยสภา</div>
        </div>
      </div>

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
      </nav>
    </header>

    {#if activeView === 'ocr'}
      <UploadPanel on:result={handleResult} on:processing={handleProcessing} />
    {:else}
      <!-- KB view doesn't need left panel content -->
      <div class="kb-hint">
        <p>เลือกโครงการและเอกสารในพื้นที่หลัก เพื่อดูข้อมูล Knowledge Base</p>
      </div>
    {/if}
  </aside>

  <!-- ── Right Panel ── -->
  <main class="right-panel">
    {#if activeView === 'ocr'}
      <ResultsPanel result={scanResult} {isProcessing} {progress} />
    {:else}
      <KnowledgeBase />
    {/if}
  </main>
</div>

<!-- Global Toast Notifications -->
<Toast />

<style>
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
    flex: 1;
    min-width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: var(--bg);
  }

  /* Responsive */
  @media (max-width: 780px) {
    .shell { flex-direction: column; overflow: auto; }
    .left-panel { width: 100%; border-right: none; border-bottom: 1px solid var(--border); }
    .right-panel { flex: none; min-height: 60vh; }
  }
</style>
