<script>
  import { fade, fly } from "svelte/transition";
  import UploadPanel from "./lib/UploadPanel.svelte";
  import ResultsPanel from "./lib/ResultsPanel.svelte";
  import KnowledgeBase from "./lib/KnowledgeBase.svelte";
  import SkillManager from "./lib/SkillManager.svelte";
  import Toast from "./lib/Toast.svelte";

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

<div class="shell">
  <!-- ── Left Panel ── -->
  <aside class="left-panel" class:collapsed-left={activeView === "skills"}>
    <header class="panel-header">
      <div class="logo">
        <div class="logo-icon">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            width="18"
            height="18"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polygon points="12 3 3 21 21 21"></polygon>
            <line x1="3" y1="14" x2="21" y2="14"></line>
            <line x1="8" y1="10" x2="16" y2="10"></line>
          </svg>
        </div>
        <div>
          <div class="logo-title">Spectra QA</div>
          <div class="logo-sub">Intelligent Document Analysis</div>
        </div>
      </div>

      <!-- Nav tabs -->
      <nav class="nav-tabs">
        <button
          id="nav-ocr"
          class="nav-tab"
          class:active={activeView === "ocr"}
          on:click={() => (activeView = "ocr")}
        >
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
            <path
              fill-rule="evenodd"
              d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
              clip-rule="evenodd"
            />
          </svg>
          Scan OCR
        </button>
        <button
          id="nav-kb"
          class="nav-tab"
          class:active={activeView === "kb"}
          on:click={() => (activeView = "kb")}
        >
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
            <path
              d="M3 12v3c0 1.657 3.134 3 7 3s7-1.343 7-3v-3c0 1.657-3.134 3-7 3s-7-1.343-7-3z"
            />
            <path
              d="M3 7v3c0 1.657 3.134 3 7 3s7-1.343 7-3V7c0 1.657-3.134 3-7 3S3 8.657 3 7z"
            />
            <path
              d="M17 5c0 1.657-3.134 3-7 3S3 6.657 3 5s3.134-3 7-3 7 1.343 7 3z"
            />
          </svg>
          Knowledge Base
        </button>
        <button
          id="nav-skills"
          class="nav-tab"
          class:active={activeView === "skills"}
          on:click={() => (activeView = "skills")}
        >
          <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
            <path
              d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 103.636 5.05l-.707.707a1 1 0 001.414 1.414l.707-.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1a1 1 0 112 0v1a1 1 0 11-2 0zM12 14a1 1 0 100-2 1 1 0 000 2z"
            />
          </svg>
          AI Skills
        </button>
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

  <!-- ── Right Panel ── -->
  <main class="right-panel">
    {#key activeView}
      <div style="width:100%; height:100%;" in:fly="{{ y: 20, duration: 400, delay: 150 }}" out:fade="{{ duration: 150 }}">
        {#if activeView === "ocr"}
          <ResultsPanel result={scanResult} {isProcessing} {progress} />
        {:else if activeView === "kb"}
          <KnowledgeBase />
        {:else if activeView === "skills"}
          <SkillManager />
        {/if}
      </div>
    {/key}
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
    width: 36px;
    height: 36px;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 16px var(--glow);
    flex-shrink: 0;
  }
  .logo-icon svg {
    color: #fff;
    stroke: #fff;
  }

  .logo-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
    line-height: 1.2;
  }
  .logo-sub {
    font-size: 11px;
    color: var(--text3);
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
    background: rgba(108, 142, 251, 0.07);
    color: var(--text2);
  }
  .nav-tab.active {
    background: rgba(108, 142, 251, 0.16);
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
    .shell {
      flex-direction: column;
      overflow: auto;
    }
    .left-panel {
      width: 100%;
      border-right: none;
      border-bottom: 1px solid var(--border);
    }
    .right-panel {
      flex: none;
      min-height: 60vh;
    }
  }
</style>
