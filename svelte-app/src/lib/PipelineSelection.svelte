<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { toast } from './toastStore.js';
  
  export let projectId = "";
  
  let pipelines = [];
  let loading = true;
  
  const dispatch = createEventDispatcher();
  
  async function fetchPipelines() {
    loading = true;
    try {
      const res = await fetch(`http://127.0.0.1:5000/api/workflows?project_id=${projectId}`);
      if (res.ok) {
        const data = await res.json();
        pipelines = data.workflows || [];
      } else {
        toast('Failed to fetch pipelines', 'error');
      }
    } catch (err) {
      console.error(err);
      toast('Error fetching pipelines', 'error');
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    if (projectId) {
      fetchPipelines();
    }
  });
  
  function selectPipeline(pl) {
    dispatch('select', pl);
  }

  function createNew() {
    dispatch('create');
  }

  async function deletePipeline(e, pl) {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete pipeline "${pl.name}"?`)) return;
    
    try {
      const res = await fetch(`http://127.0.0.1:5000/api/workflows/${pl.id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        toast('Pipeline deleted', 'success');
        fetchPipelines();
      } else {
        toast('Failed to delete pipeline', 'error');
      }
    } catch (err) {
      toast('Error deleting pipeline', 'error');
    }
  }
</script>

<div class="header-text">
  <h2>เลือก Pipeline (Pipeline Selection)</h2>
  <p>กรุณาเลือก Pipeline ที่ต้องการใช้งาน หรือสร้างใหม่</p>
</div>

<div class="pipeline-grid">
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="pipeline-card create-card" on:click={createNew}>
    <div class="create-icon">+</div>
    <div class="p-name">สร้าง Pipeline ใหม่</div>
  </div>

  {#if loading}
    <div class="empty-state">กำลังโหลดข้อมูล...</div>
  {:else if pipelines.length === 0}
    <!-- Empty state not strictly needed since create card is always there, but good to have -->
  {:else}
    {#each pipelines as pl}
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="pipeline-card" on:click={() => selectPipeline(pl)}>
        <div class="card-header-row">
          <div class="p-name">{pl.name}</div>
          <button class="delete-btn" on:click={(e) => deletePipeline(e, pl)} title="Delete Pipeline">
            ✕
          </button>
        </div>
        
        <div class="p-desc-section">
          <div class="p-meta-label">รายละเอียด (DESCRIPTION)</div>
          <div class="p-desc-box">
            {#if pl.description}
              {pl.description}
            {:else}
              <span class="empty-desc">ไม่มีรายละเอียด</span>
            {/if}
          </div>
        </div>

        {#if pl.updated_at}
          <div class="p-meta-label" style="margin-top: 12px; font-weight: normal; font-size: 11px; opacity: 0.7;">
            อัปเดตล่าสุด: {new Date(pl.updated_at).toLocaleString('th-TH')}
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</div>

<style>
  .header-text {
    text-align: center;
    margin-bottom: 30px;
  }
  .header-text h2 {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 10px;
    background: linear-gradient(90deg, #fff, #9ca3af);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header-text p {
    color: var(--text3, #9ca3af);
    font-size: 16px;
  }
  
  .pipeline-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px;
    width: 100%;
  }
  .pipeline-card {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    text-align: left;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(10px);
    display: flex;
    flex-direction: column;
  }
  .pipeline-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  }
  .pipeline-card:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(59, 130, 246, 0.5); /* Blueish border for pipelines */
    box-shadow: 0 12px 30px -10px rgba(59, 130, 246, 0.4);
    transform: translateY(-4px);
  }
  .create-card {
    align-items: center;
    justify-content: center;
    border: 1px dashed rgba(255, 255, 255, 0.3);
    background: rgba(0, 0, 0, 0.2);
  }
  .create-card:hover {
    border-color: rgba(59, 130, 246, 0.8);
    background: rgba(59, 130, 246, 0.1);
  }
  .create-icon {
    font-size: 48px;
    color: rgba(255,255,255,0.5);
    margin-bottom: 12px;
  }
  .create-card:hover .create-icon {
    color: rgba(59, 130, 246, 1);
  }
  .card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
  }
  .p-name {
    font-size: 18px;
    font-weight: 600;
    color: #ffffff;
    line-height: 1.4;
  }
  .delete-btn {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #f87171;
    border-radius: 50%;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
  }
  .delete-btn:hover {
    background: #ef4444;
    color: white;
  }
  .p-desc-section {
    margin-bottom: 0;
    flex-grow: 1;
  }
  .p-meta-label {
    font-size: 12px;
    color: #ffffff;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .p-desc-box {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 14px;
    color: #e5e7eb;
    line-height: 1.5;
    min-height: 48px;
  }
  .empty-desc {
    color: #9ca3af;
  }
  .empty-state {
    grid-column: 1 / -1;
    text-align: center;
    padding: 40px;
    background: rgba(0,0,0,0.2);
    border-radius: 12px;
    color: var(--text-muted, #9ca3af);
    border: 1px dashed rgba(255, 255, 255, 0.2);
  }
</style>
