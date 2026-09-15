<script>
  import { onMount } from "svelte";
  import { fade, slide, fly, scale } from "svelte/transition";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";
  import { toast } from "./toastStore.js";

  let projects = [];

  $: selectedProjectId = $selectedProjectStore ? ($selectedProjectStore.id || $selectedProjectStore.project_id) : "";

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  onMount(async () => {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/projects");
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  });

  // Board columns
  let columns = [
    { id: 'todo', title: 'To Do', color: '#64748b' },
    { id: 'in_progress', title: 'In Progress', color: '#3b82f6' },
    { id: 'testing', title: 'Testing (Agent)', color: '#a855f7' },
    { id: 'done', title: 'Done', color: '#22c55e' }
  ];

  // Cards data & state
  let cards = [];
  let isLoading = false;

  // Board integration configuration state
  let showConfigModal = false;
  let currentIntegration = null;
  let configProvider = 'trello'; // 'trello' | 'github'
  let trelloApiKey = '';
  let trelloToken = '';
  let trelloBoardId = '';
  let githubToken = '';
  let githubOwner = '';
  let githubRepo = '';
  let isTestingConnection = false;
  let isSavingConfig = false;

  $: if (selectedProjectId) {
    fetchCards();
    fetchBoardIntegration();
  } else {
    cards = [];
    currentIntegration = null;
  }

  async function fetchCards() {
    if (!selectedProjectId) return;
    isLoading = true;
    try {
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/cards`);
      const data = await res.json();
      if (data.success) {
        cards = data.cards || [];
        if (data.columns && data.columns.length > 0) {
          columns = data.columns;
        }
      }
    } catch (err) {
      toast("เกิดข้อผิดพลาดในการดึงข้อมูล Card", "error");
    } finally {
      isLoading = false;
    }
  }

  async function fetchBoardIntegration() {
    if (!selectedProjectId) return;
    try {
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/board-integration`);
      const data = await res.json();
      if (data.success && data.integration) {
        currentIntegration = data.integration;
        configProvider = data.integration.provider || 'trello';
        trelloApiKey = data.integration.trello_api_key || '';
        trelloToken = data.integration.trello_token || '';
        trelloBoardId = data.integration.trello_board_id || '';
        githubToken = data.integration.github_token || '';
        githubOwner = data.integration.github_owner || '';
        githubRepo = data.integration.github_repo || '';
      } else {
        currentIntegration = null;
      }
    } catch (err) {
      console.error("Error fetching board integration:", err);
    }
  }

  async function testConnection() {
    if (!selectedProjectId) return;
    isTestingConnection = true;
    try {
      const payload = {
        provider: configProvider,
        trello_api_key: trelloApiKey,
        trello_token: trelloToken,
        trello_board_id: trelloBoardId,
        github_token: githubToken,
        github_owner: githubOwner,
        github_repo: githubRepo
      };
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/board-integration/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      let data = {};
      try { data = await res.json(); } catch(e) {}
      if (res.ok && data.success) {
        toast(data.message || "เชื่อมต่อสำเร็จ!", "success");
      } else {
        toast(data.error || `เชื่อมต่อไม่สำเร็จ (${res.status})`, "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการทดสอบเชื่อมต่อ: ${err.message}`, "error");
    } finally {
      isTestingConnection = false;
    }
  }

  async function saveBoardIntegration() {
    if (!selectedProjectId) return;
    isSavingConfig = true;
    try {
      const payload = {
        provider: configProvider,
        trello_api_key: trelloApiKey,
        trello_token: trelloToken,
        trello_board_id: trelloBoardId,
        github_token: githubToken,
        github_owner: githubOwner,
        github_repo: githubRepo
      };
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/board-integration`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      let data = {};
      try { data = await res.json(); } catch(e) {}
      if (res.ok && data.success) {
        toast("บันทึกการตั้งค่าการเชื่อมต่อสำเร็จ!", "success");
        await fetchBoardIntegration();
        showConfigModal = false;
        // Auto trigger sync
        syncBoard();
      } else {
        toast(data.error || `บันทึกไม่สำเร็จ (${res.status})`, "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการบันทึก: ${err.message}`, "error");
    } finally {
      isSavingConfig = false;
    }
  }

  async function syncBoard() {
    if (!selectedProjectId) return;
    isLoading = true;
    toast("กำลัง Sync ข้อมูลจาก Board...", "info");
    try {
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/cards/sync`, {
        method: "POST"
      });
      let data = {};
      try { data = await res.json(); } catch(e) {}
      if (res.ok && data.success) {
        toast(data.message || "Sync ข้อมูลสำเร็จ!", "success");
        fetchCards();
      } else {
        toast(data.error || `Sync ล้มเหลว (${res.status})`, "error");
        if (data.error && data.error.includes("ยังไม่ได้ตั้งค่า")) {
          showConfigModal = true;
        }
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการ Sync: ${err.message}`, "error");
    } finally {
      isLoading = false;
    }
  }

  function getCardsByStatus(statusId) {
    return cards.filter(c => c.status === statusId || (columns.length > 0 && statusId === columns[0].id && !c.status));
  }

  async function handleAgentTest(cardId) {
    cards = cards.map(c => c.id === cardId ? { ...c, isTesting: true, status: 'testing' } : c);
    toast(`AI Agent กำลังเริ่มตรวจสอบ Card ${cardId}...`, "info");

    try {
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/cards/${cardId}/test`, {
        method: "POST"
      });
      const data = await res.json();
      if (data.success) {
        toast(`Agent ตรวจสอบ Card สำเร็จและส่งรายงานแล้ว!`, "success");
      } else {
        toast(data.error || "Test failed", "error");
      }
    } catch (err) {
      toast("Error testing card", "error");
    } finally {
      fetchCards();
    }
  }
</script>

<div class="board-container" in:fade>
  {#if !$selectedProjectStore}
    <ProjectSelection 
      {projects} 
      subtitle="กรุณาเลือกโครงการที่ต้องการ เพื่อดูและจัดการ QA Board Cards" 
      on:select={(e) => selectProject(e.detail)} 
    />
  {:else}
    <div class="top-nav">
      <button class="btn-back" on:click={() => { selectedProjectStore.set(null); }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>
    </div>

    <div class="header-section">
      <div class="header-main-row">
        <div>
          <h2 class="title">QA Board Card (Agent Tester)</h2>
          <p class="subtitle">เชื่อมต่อ Board จาก Trello หรือ GitHub และสั่งให้ AI Agent ตรวจสอบ Card อัตโนมัติ</p>
          
          <div class="project-info-row">
            <div class="active-project-badge">
              โครงการ: <strong>{$selectedProjectStore.project_code || ''} - {$selectedProjectStore.name || $selectedProjectStore.project_name || ''}</strong>
            </div>

            {#if currentIntegration}
              <div class="integration-status-badge {currentIntegration.provider}">
                {#if currentIntegration.provider === 'trello'}
                  <span class="provider-pill trello">🔵 Trello</span> 
                  <span class="provider-detail">Board ID: {currentIntegration.trello_board_id}</span>
                {:else if currentIntegration.provider === 'github'}
                  <span class="provider-pill github">🐱 GitHub</span> 
                  <span class="provider-detail">{currentIntegration.github_owner}/{currentIntegration.github_repo}</span>
                {/if}
              </div>
            {:else}
              <div class="integration-status-badge unconfigured">
                ⚠️ ยังไม่ได้เชื่อมต่อบอร์ด (คลิกปุ่มตั้งค่าเพื่อเชื่อมต่อ)
              </div>
            {/if}
          </div>
        </div>

        <div class="header-actions">
          <button class="btn-config" on:click={() => showConfigModal = true} title="ตั้งค่าเชื่อมต่อกับ Trello หรือ GitHub">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            ⚙️ ตั้งค่า Board
          </button>
          
          <button class="btn-refresh" on:click={syncBoard} disabled={isLoading || !selectedProjectId}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" class:spinning={isLoading}><path d="M23 4v6h-6"></path><path d="M1 20v-6h6"></path><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
            {isLoading ? 'กำลัง Sync...' : 'Sync Board'}
          </button>
        </div>
      </div>
    </div>

    <!-- Board Columns Layout -->
    <div class="board-layout">
      {#each columns as column}
        <div class="board-column glass-panel">
          <div class="column-header">
            <span class="column-dot" style="background-color: {column.color};"></span>
            <span class="column-title">{column.title}</span>
            <span class="column-count">{getCardsByStatus(column.id).length}</span>
          </div>
          
          <div class="card-list">
            {#each getCardsByStatus(column.id) as card (card.id)}
              <div class="task-card" in:fly={{ y: 10, duration: 200 }}>
                <div class="card-badges">
                  <span class="badge {card.type ? card.type.toLowerCase().replace(' ', '-') : 'feature'}">{card.type || 'Feature'}</span>
                  <span class="badge priority-{card.priority ? card.priority.toLowerCase() : 'medium'}">{card.priority || 'Medium'}</span>
                </div>
                
                <h4 class="card-title">{card.title}</h4>
                {#if card.description}
                  <p class="card-desc">{card.description.slice(0, 100)}{card.description.length > 100 ? '...' : ''}</p>
                {/if}

                <div class="card-footer">
                  <span class="card-id">{card.ext_card_id}</span>
                  
                  {#if card.isTesting || card.status === 'testing'}
                    <div class="testing-indicator">
                      <span class="spinner-small"></span> Agent testing...
                    </div>
                  {:else if card.status !== 'done'}
                    <button class="btn-test" on:click={() => handleAgentTest(card.id)}>
                      🤖 Run Agent Test
                    </button>
                  {:else}
                    <span class="status-done">✅ Verified</span>
                  {/if}
                </div>
              </div>
            {/each}
            {#if getCardsByStatus(column.id).length === 0}
              <div class="empty-column">ไม่มี Card ในสถานะนี้</div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<!-- Modal ตั้งค่าการเชื่อมต่อบอร์ด (Board Integration Modal) -->
{#if showConfigModal}
  <div class="modal-backdrop" transition:fade={{ duration: 150 }}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="modal-card glass-panel" in:scale={{ start: 0.95, duration: 200 }} on:click|stopPropagation>
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-size: 24px;">🔌</span>
          <div>
            <h3 class="modal-title">ตั้งค่าการเชื่อมต่อบอร์ด (Board Integration)</h3>
            <p class="modal-subtitle">กำหนดค่าการเชื่อมต่อเพื่อดึงงานจาก Trello หรือ GitHub เข้าสู่ระบบ QA Agent</p>
          </div>
        </div>
        <button class="btn-close" on:click={() => showConfigModal = false}>✕</button>
      </div>

      <!-- Provider Tabs -->
      <div class="provider-tabs">
        <button class="tab-btn" class:active={configProvider === 'trello'} on:click={() => configProvider = 'trello'}>
          <span style="color: #38bdf8; font-weight: bold;">🔵 Trello Board</span>
        </button>
        <button class="tab-btn" class:active={configProvider === 'github'} on:click={() => configProvider = 'github'}>
          <span style="color: #f3f4f6; font-weight: bold;">🐱 GitHub Issues / Project</span>
        </button>
      </div>

      <div class="modal-body">
        {#if configProvider === 'trello'}
          <div class="provider-guide">
            <p><strong>วิธีรับค่าจาก Trello:</strong> ไปที่ <a href="https://trello.com/power-ups/admin" target="_blank" rel="noreferrer">Trello Power-Up Admin</a> เพื่อสร้าง Key & Token และดู Board ID จากลิงก์บอร์ดของคุณ</p>
          </div>

          <div class="form-group">
            <label for="trello_api_key">Trello API Key <span class="required">*</span></label>
            <input type="text" id="trello_api_key" bind:value={trelloApiKey} placeholder="เช่น a1b2c3d4e5f6..." />
          </div>

          <div class="form-group">
            <label for="trello_token">Trello API Token <span class="required">*</span></label>
            <input type="password" id="trello_token" bind:value={trelloToken} placeholder="เช่น ATATT..." />
          </div>

          <div class="form-group">
            <label for="trello_board_id">Trello Board ID <span class="required">*</span></label>
            <input type="text" id="trello_board_id" bind:value={trelloBoardId} placeholder="เช่น 64f1234abcd56789 (ดูจาก URL บอร์ดหลัง /b/)" />
          </div>

        {:else if configProvider === 'github'}
          <div class="provider-guide">
            <p><strong>วิธีรับค่าจาก GitHub:</strong> ไปที่ GitHub ➔ Settings ➔ Developer Settings ➔ <a href="https://github.com/settings/tokens" target="_blank" rel="noreferrer">Personal Access Tokens (classic หรือ fine-grained)</a> โดยเลือกสิทธิ์ <code>repo</code></p>
          </div>

          <div class="form-group">
            <label for="github_token">GitHub Personal Access Token (PAT) <span class="required">*</span></label>
            <input type="password" id="github_token" bind:value={githubToken} placeholder="เช่น ghp_xxxxxxxxxxxx หรือ github_pat_..." />
          </div>

          <div class="form-row">
            <div class="form-group" style="flex: 1;">
              <label for="github_owner">Repository Owner / Org <span class="required">*</span></label>
              <input type="text" id="github_owner" bind:value={githubOwner} placeholder="เช่น AkradTTT08 หรือ MyOrganization" />
            </div>

            <div class="form-group" style="flex: 1;">
              <label for="github_repo">Repository Name <span class="required">*</span></label>
              <input type="text" id="github_repo" bind:value={githubRepo} placeholder="เช่น OCR-Document" />
            </div>
          </div>
        {/if}
      </div>

      <div class="modal-footer">
        <button class="btn-test-conn" on:click={testConnection} disabled={isTestingConnection}>
          {#if isTestingConnection}
            <span class="spinner-small"></span> กำลังทดสอบ...
          {:else}
            ⚡ ทดสอบการเชื่อมต่อ (Test)
          {/if}
        </button>

        <div style="display: flex; gap: 8px;">
          <button class="btn-secondary" on:click={() => showConfigModal = false}>ยกเลิก</button>
          <button class="btn-primary" on:click={saveBoardIntegration} disabled={isSavingConfig}>
            {#if isSavingConfig}
              <span class="spinner-small"></span> กำลังบันทึก...
            {:else}
              💾 บันทึกและเชื่อมต่อ
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .board-container {
    padding: 24px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 16px;
    overflow-y: auto;
    box-sizing: border-box;
  }

  .top-nav {
    margin-bottom: 4px;
  }

  .btn-back {
    background: transparent;
    border: none;
    color: #a78bfa;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: color 0.2s;
  }
  .btn-back:hover {
    color: #c084fc;
  }
  
  .header-section {
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .header-main-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 16px;
  }
  
  .title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, #a855f7 0%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  
  .subtitle {
    margin: 4px 0 0 0;
    color: #94a3b8;
    font-size: 0.9rem;
  }

  .project-info-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
    flex-wrap: wrap;
  }

  .active-project-badge {
    padding: 4px 14px;
    background: rgba(139, 92, 246, 0.12);
    border-radius: 20px;
    border: 1px solid rgba(139, 92, 246, 0.3);
    font-size: 13px;
    color: #e2e8f0;
  }

  .integration-status-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 12px;
  }
  .integration-status-badge.trello {
    background: rgba(14, 165, 233, 0.15);
    border: 1px solid rgba(14, 165, 233, 0.4);
    color: #38bdf8;
  }
  .integration-status-badge.github {
    background: rgba(243, 244, 246, 0.1);
    border: 1px solid rgba(243, 244, 246, 0.3);
    color: #f3f4f6;
  }
  .integration-status-badge.unconfigured {
    background: rgba(234, 179, 8, 0.15);
    border: 1px solid rgba(234, 179, 8, 0.35);
    color: #facc15;
  }

  .provider-pill {
    font-weight: 700;
  }
  .provider-detail {
    opacity: 0.9;
    font-family: monospace;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .btn-config {
    background: rgba(139, 92, 246, 0.15);
    border: 1px solid rgba(139, 92, 246, 0.4);
    color: #c084fc;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .btn-config:hover {
    background: rgba(139, 92, 246, 0.3);
    color: #fff;
    transform: translateY(-1px);
  }

  .btn-refresh {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #e2e8f0;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .btn-refresh:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.15);
    transform: translateY(-1px);
  }
  .btn-refresh:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .spinning {
    animation: spin 1s linear infinite;
  }
  
  .glass-panel {
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    border-radius: 12px;
  }
  
  .board-layout {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    flex: 1;
    padding-bottom: 12px;
    min-height: 520px;
  }
  
  .board-column {
    min-width: 320px;
    width: 320px;
    display: flex;
    flex-direction: column;
    background: rgba(15, 23, 42, 0.7);
  }
  
  .column-header {
    display: flex;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(0, 0, 0, 0.25);
    border-radius: 12px 12px 0 0;
  }
  
  .column-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 10px;
  }
  
  .column-title {
    font-weight: 600;
    color: #f1f5f9;
    flex: 1;
    font-size: 0.95rem;
  }
  
  .column-count {
    background: rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  
  .card-list {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
    flex: 1;
  }
  
  .task-card {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px;
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  }
  .task-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
    border-color: rgba(139, 92, 246, 0.4);
  }
  
  .card-badges {
    display: flex;
    gap: 6px;
    margin-bottom: 8px;
  }
  
  .badge {
    font-size: 0.65rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 12px;
    text-transform: uppercase;
  }
  .badge.feature { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
  .badge.bug { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
  .badge.enhancement { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
  .badge.documentation { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
  .badge.tech-debt { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
  
  .badge.priority-high { color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.1); }
  .badge.priority-critical { color: #ff4d4f; border: 1px solid rgba(255, 77, 79, 0.6); background: rgba(255, 77, 79, 0.2); }
  .badge.priority-medium { color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); background: rgba(245, 158, 11, 0.1); }
  .badge.priority-low { color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.2); background: rgba(148, 163, 184, 0.05); }
  
  .card-title {
    margin: 0 0 6px 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: #f8fafc;
    line-height: 1.4;
  }
  
  .card-desc {
    margin: 0 0 12px 0;
    font-size: 0.8rem;
    color: #94a3b8;
    line-height: 1.35;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 10px;
  }
  
  .card-id {
    font-size: 0.75rem;
    color: #94a3b8;
    font-family: monospace;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.06);
    padding: 2px 6px;
    border-radius: 4px;
  }
  
  .btn-test {
    background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
    border: none;
    color: white;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
    transition: all 0.2s;
  }
  .btn-test:hover {
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.5);
    transform: translateY(-1px);
  }
  
  .testing-indicator {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    color: #c084fc;
    font-weight: 600;
  }
  
  .status-done {
    font-size: 0.75rem;
    color: #34d399;
    font-weight: 600;
  }
  
  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(192, 132, 252, 0.3);
    border-top-color: #c084fc;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    display: inline-block;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  .empty-column {
    padding: 24px 16px;
    text-align: center;
    color: #64748b;
    font-size: 0.85rem;
    border: 1px dashed rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    margin-top: 10px;
  }

  /* Modal Styling */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
    padding: 20px;
  }

  .modal-card {
    width: 100%;
    max-width: 580px;
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(139, 92, 246, 0.3);
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.8);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 24px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .modal-title {
    margin: 0;
    font-size: 1.2rem;
    color: #fff;
    font-weight: 700;
  }

  .modal-subtitle {
    margin: 2px 0 0;
    font-size: 0.85rem;
    color: #94a3b8;
  }

  .btn-close {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 6px;
    transition: all 0.2s;
  }
  .btn-close:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.1);
  }

  .provider-tabs {
    display: flex;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(0, 0, 0, 0.25);
  }

  .tab-btn {
    flex: 1;
    padding: 12px 16px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: #94a3b8;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  .tab-btn.active {
    border-bottom-color: #8b5cf6;
    background: rgba(139, 92, 246, 0.1);
    color: #fff;
  }

  .modal-body {
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .provider-guide {
    background: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(99, 102, 241, 0.2);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #c4b5fd;
    line-height: 1.4;
  }
  .provider-guide a {
    color: #60a5fa;
    text-decoration: underline;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .form-group label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #cbd5e1;
  }
  .form-group .required {
    color: #f87171;
  }
  .form-group input {
    background: rgba(0, 0, 0, 0.35);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 10px 14px;
    color: #fff;
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.2s;
  }
  .form-group input:focus {
    border-color: #8b5cf6;
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.2);
  }

  .form-row {
    display: flex;
    gap: 12px;
  }

  .modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(0, 0, 0, 0.2);
  }

  .btn-test-conn {
    background: rgba(14, 165, 233, 0.15);
    border: 1px solid rgba(14, 165, 233, 0.4);
    color: #38bdf8;
    padding: 9px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .btn-test-conn:hover:not(:disabled) {
    background: rgba(14, 165, 233, 0.25);
    color: #fff;
  }
  .btn-test-conn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    padding: 9px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-secondary:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #fff;
  }

  .btn-primary {
    background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);
    border: none;
    color: #fff;
    padding: 9px 20px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.4);
    transition: all 0.2s;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .btn-primary:hover:not(:disabled) {
    box-shadow: 0 6px 20px rgba(139, 92, 246, 0.6);
    transform: translateY(-1px);
  }
  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
