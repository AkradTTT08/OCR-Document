<script>
  import { onMount } from "svelte";
  import { fade, slide, fly } from "svelte/transition";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";
  import { toast } from "./toastStore.js";

  $: selectedProjectId = $selectedProjectStore ? ($selectedProjectStore.id || $selectedProjectStore.project_id) : "";

  // Mock data for Board columns
  let columns = [
    { id: 'todo', title: 'To Do', color: '#64748b' },
    { id: 'in_progress', title: 'In Progress', color: '#3b82f6' },
    { id: 'testing', title: 'Testing (Agent)', color: '#a855f7' },
    { id: 'done', title: 'Done', color: '#22c55e' }
  ];

  // Mock data for Cards
  let cards = [];
  let isLoading = false;

  $: if (selectedProjectId) {
    fetchCards();
  } else {
    cards = [];
  }

  async function fetchCards() {
    if (!selectedProjectId) return;
    isLoading = true;
    try {
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/cards`);
      const data = await res.json();
      if (data.success) {
        cards = data.cards;
      }
    } catch (err) {
      toast("เกิดข้อผิดพลาดในการดึงข้อมูล Card", "error");
    } finally {
      isLoading = false;
    }
  }

  async function syncBoard() {
    if (!selectedProjectId) return;
    toast("กำลัง Sync ข้อมูลจาก Board...", "info");
    try {
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/cards/sync`, {
        method: "POST"
      });
      const data = await res.json();
      if (data.success) {
        toast("Sync ข้อมูลสำเร็จ!", "success");
        fetchCards();
      } else {
        toast(data.error || "Sync ล้มเหลว", "error");
      }
    } catch (err) {
      toast("เกิดข้อผิดพลาดในการ Sync", "error");
    }
  }

  function getCardsByStatus(statusId) {
    return cards.filter(c => c.status === statusId);
  }

  async function handleAgentTest(cardId) {
    cards = cards.map(c => c.id === cardId ? { ...c, isTesting: true, status: 'testing' } : c);
    toast(`Agent is now testing card ${cardId}...`, "info");

    try {
      const res = await fetch(`http://localhost:5000/api/projects/${selectedProjectId}/cards/${cardId}/test`, {
        method: "POST"
      });
      const data = await res.json();
      if (data.success) {
        toast(`Agent completed testing card ${cardId}. Results passed!`, "success");
      } else {
        toast(data.error || "Test failed", "error");
      }
    } catch (err) {
      toast("Error testing card", "error");
    } finally {
      // Re-fetch to get latest status and result
      fetchCards();
    }
  }
</script>

<div class="board-container" in:fade>
  <div class="header-section">
    <div style="display: flex; justify-content: space-between; align-items: flex-end;">
      <div>
        <h2 class="title">QA Board Card (Agent Tester)</h2>
        <p class="subtitle">ดึงข้อมูล Card จาก Trello / GitHub และสั่งให้ Agent ตรวจสอบได้ทันที</p>
      </div>
      <div>
        <button class="btn-refresh" on:click={syncBoard} disabled={isLoading || !selectedProjectId}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16" style="margin-right: 4px;"><path d="M23 4v6h-6"></path><path d="M1 20v-6h6"></path><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
          Sync Board
        </button>
      </div>
    </div>
  </div>

  <div class="project-section">
    <ProjectSelection />
  </div>

  {#if !selectedProjectId}
    <div class="empty-state glass-panel">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48" style="color: #64748b; margin-bottom: 16px;"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
      <h3>กรุณาเลือกโปรเจกต์ (Select Project)</h3>
      <p>คุณต้องระบุโปรเจกต์ที่เมนูด้านบนก่อน เพื่อดึง Board Cards ของโปรเจกต์นั้นๆ</p>
    </div>
  {:else}
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
                  <span class="badge {card.type.toLowerCase().replace(' ', '-')}">{card.type}</span>
                  <span class="badge priority-{card.priority.toLowerCase()}">{card.priority}</span>
                </div>
                
                <h4 class="card-title">{card.title}</h4>
                <div class="card-footer">
                  <span class="card-id">{card.ext_card_id}</span>
                  
                  {#if card.isTesting || card.status === 'testing'}
                    <div class="testing-indicator">
                      <span class="spinner-small"></span> Agent is testing...
                    </div>
                  {:else if card.status !== 'done'}
                    <button class="btn-test" on:click={() => handleAgentTest(card.id)}>
                      🤖 Run Agent Test
                    </button>
                  {:else}
                    <span class="status-done">✅ Passed</span>
                  {/if}
                </div>
              </div>
            {/each}
            {#if getCardsByStatus(column.id).length === 0}
              <div class="empty-column">ไม่มีการ์ดในสถานะนี้</div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .board-container {
    padding: 24px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 20px;
    overflow: hidden;
  }
  
  .header-section {
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
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
  
  .btn-refresh {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    color: #e2e8f0;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    transition: all 0.2s;
  }
  .btn-refresh:hover {
    background: rgba(255,255,255,0.1);
  }
  
  .project-section {
    margin-bottom: 8px;
  }
  
  .glass-panel {
    background: rgba(30, 41, 59, 0.5);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    border-radius: 12px;
  }
  
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
    color: #94a3b8;
    flex: 1;
  }
  
  .board-layout {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    flex: 1;
    padding-bottom: 10px;
    min-height: 500px;
  }
  
  .board-column {
    min-width: 320px;
    width: 320px;
    display: flex;
    flex-direction: column;
    background: rgba(15, 23, 42, 0.6);
  }
  
  .column-header {
    display: flex;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    background: rgba(0,0,0,0.2);
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
  }
  
  .column-count {
    background: rgba(255,255,255,0.1);
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
    gap: 10px;
    overflow-y: auto;
    flex: 1;
  }
  
  .task-card {
    background: rgba(30, 41, 59, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 14px;
    cursor: default;
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  }
  .task-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 16px rgba(0,0,0,0.3);
    border-color: rgba(139, 92, 246, 0.3);
  }
  
  .card-badges {
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
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
  .badge.tech-debt { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
  
  .badge.priority-high { color: #f87171; }
  .badge.priority-critical { color: #ef4444; font-weight: 700; background: rgba(239,68,68,0.1); }
  .badge.priority-medium { color: #fbbf24; }
  .badge.priority-low { color: #34d399; }
  
  .card-title {
    margin: 0 0 14px 0;
    font-size: 0.95rem;
    font-weight: 500;
    color: #f8fafc;
    line-height: 1.4;
  }
  
  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid rgba(255,255,255,0.05);
    padding-top: 10px;
  }
  
  .card-id {
    font-size: 0.75rem;
    color: #64748b;
    font-family: monospace;
  }
  
  .btn-test {
    background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
    border: none;
    color: white;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 2px 10px rgba(139, 92, 246, 0.4);
    transition: all 0.2s;
  }
  .btn-test:hover {
    box-shadow: 0 4px 14px rgba(139, 92, 246, 0.6);
    transform: scale(1.02);
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
    color: #22c55e;
    font-weight: 600;
  }
  
  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(192, 132, 252, 0.3);
    border-top-color: #c084fc;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  .empty-column {
    padding: 20px;
    text-align: center;
    color: #64748b;
    font-size: 0.85rem;
    border: 1px dashed rgba(255,255,255,0.1);
    border-radius: 8px;
    margin-top: 10px;
  }
</style>
