<script>
  import UploadPanel from './lib/UploadPanel.svelte';
  import ResultsPanel from './lib/ResultsPanel.svelte';
  import Toast from './lib/Toast.svelte';

  let scanResult = null;    // { pages, summary, filename }
  let isProcessing = false;
  let progress = { pct: 0, label: '', step: 0 }; // step 1/2/3

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
    </header>

    <UploadPanel
      on:result={handleResult}
      on:processing={handleProcessing}
    />
  </aside>

  <!-- ── Right Panel ── -->
  <main class="right-panel">
    <ResultsPanel result={scanResult} {isProcessing} {progress} />
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

  /* ── Right ── */
  .right-panel {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: var(--bg);
  }

  /* Responsive: stack on narrow screens */
  @media (max-width: 780px) {
    .shell { flex-direction: column; overflow: auto; }
    .left-panel { width: 100%; border-right: none; border-bottom: 1px solid var(--border); }
    .right-panel { flex: none; min-height: 60vh; }
  }
</style>
