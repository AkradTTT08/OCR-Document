<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import ConfirmModal from './ConfirmModal.svelte';
  import { toast } from './toastStore.js';
  
  export let projectId = "";
  
  let pipelines = [];
  let loading = true;
  let pendingDeletePipeline = null;
  let showDeleteConfirm = false;
  let lastFetchedProjectId = "";
  
  const dispatch = createEventDispatcher();
  
  async function fetchPipelines() {
    if (!projectId) {
      loading = false;
      pipelines = [];
      return;
    }
    loading = true;
    try {
      const res = await fetch(`/api/workflows?project_id=${projectId}`);
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

  $: if (projectId && projectId !== lastFetchedProjectId) {
    lastFetchedProjectId = projectId;
    fetchPipelines();
  } else if (!projectId) {
    lastFetchedProjectId = "";
    pipelines = [];
    loading = false;
  }

  onMount(() => {
    if (!projectId) {
      loading = false;
      pipelines = [];
    } else if (projectId !== lastFetchedProjectId) {
      lastFetchedProjectId = projectId;
      fetchPipelines();
    }
  });
  
  function selectPipeline(pl) {
    dispatch('select', pl);
  }

  function createNew() {
    dispatch('create');
  }

  function deletePipeline(e, pl) {
    e.stopPropagation();
    pendingDeletePipeline = pl;
    showDeleteConfirm = true;
  }

  async function confirmDeletePipeline() {
    const pl = pendingDeletePipeline;
    pendingDeletePipeline = null;
    if (!pl) return;
    
    try {
      const res = await fetch(`/api/workflows/${pl.id}`, {
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

{#if loading}
  <div class="empty-state" role="status" aria-live="polite">กำลังโหลดข้อมูล...</div>
{:else}
  <div class="pipeline-grid">
    <button type="button" class="pipeline-card create-card" on:click={createNew}>
      <div class="create-icon" aria-hidden="true">+</div>
      <div class="p-name">สร้าง Pipeline ใหม่</div>
    </button>

    {#each pipelines as pl}
      <div class="pipeline-card-wrap">
        <button
          type="button"
          class="pipeline-card"
          on:click={() => selectPipeline(pl)}
        >
          <div class="card-header-row">
            <div class="p-name">{pl.name}</div>
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
            <div class="p-updated-meta">
              อัปเดตล่าสุด: {new Date(pl.updated_at).toLocaleString('th-TH')}
            </div>
          {/if}
        </button>

        <button
          type="button"
          class="delete-btn"
          aria-label={`ลบ Pipeline ${pl.name}`}
          on:click={(e) => deletePipeline(e, pl)}
          title="Delete Pipeline"
        >
          ✕
        </button>
      </div>
    {/each}
  </div>
{/if}

<ConfirmModal
  bind:open={showDeleteConfirm}
  title="Delete Pipeline"
  message={`Are you sure you want to delete pipeline "${pendingDeletePipeline?.name || ''}"?`}
  confirmText="Delete"
  cancelText="Cancel"
  on:confirm={confirmDeletePipeline}
/>

<style>
  .header-text {
    text-align: center;
    margin-bottom: 30px;
  }
  .header-text h2 {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 10px;
    color: var(--text-main, #f8fafc);
  }
  .header-text p {
    color: var(--text-muted, #94a3b8);
    font-size: 16px;
  }
  
  .pipeline-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
    gap: 20px;
    width: 100%;
  }
  .pipeline-card-wrap {
    position: relative;
    display: flex;
    min-width: 0;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .pipeline-card-wrap:hover {
    transform: translateY(-4px);
  }
  .pipeline-card {
    font: inherit;
    color: inherit;
    width: 100%;
    height: 100%;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border-light, rgba(255, 255, 255, 0.12));
    border-radius: var(--radius-lg, 20px);
    padding: 24px;
    cursor: pointer;
    transition: background 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                border-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
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
    border-color: var(--primary, #6366f1);
    box-shadow: 0 12px 30px -10px rgba(99, 102, 241, 0.4);
  }
  .pipeline-card:focus-visible {
    outline: 2px solid var(--primary, #6366f1);
    outline-offset: 2px;
    border-color: var(--primary, #6366f1);
  }
  .create-card {
    min-height: 180px;
    align-items: center;
    justify-content: center;
    text-align: center;
    border: 1px dashed rgba(255, 255, 255, 0.3);
    background: rgba(0, 0, 0, 0.2);
  }
  .create-card:hover {
    border-color: var(--primary, #6366f1);
    background: rgba(99, 102, 241, 0.12);
    transform: translateY(-4px);
  }
  .create-icon {
    font-size: 48px;
    color: rgba(255,255,255,0.5);
    margin-bottom: 12px;
    line-height: 1;
  }
  .create-card:hover .create-icon {
    color: var(--primary, #6366f1);
  }
  .card-header-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    padding-right: 38px;
    margin-bottom: 16px;
    width: 100%;
  }
  .p-name {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-main, #f8fafc);
    line-height: 1.4;
    min-width: 0;
    overflow-wrap: break-word;
  }
  .delete-btn {
    position: absolute;
    top: 20px;
    right: 20px;
    z-index: 2;
    flex-shrink: 0;
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.35);
    color: #fda4af;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
  }
  .delete-btn:hover {
    background: var(--danger, #f43f5e);
    border-color: var(--danger, #f43f5e);
    color: #ffffff;
  }
  .delete-btn:focus-visible {
    outline: 2px solid var(--danger, #f43f5e);
    outline-offset: 2px;
  }
  .p-desc-section {
    margin-bottom: 0;
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    width: 100%;
  }
  .p-meta-label {
    font-size: 12px;
    color: var(--text-main, #f8fafc);
    font-weight: 700;
    margin-bottom: 6px;
  }
  .p-desc-box {
    flex: 1;
    background: rgba(255, 255, 255, 0.05);
    border-radius: var(--radius-sm, 8px);
    padding: 12px 16px;
    font-size: 14px;
    color: #e5e7eb;
    line-height: 1.5;
    min-height: 48px;
    overflow-wrap: break-word;
  }
  .p-updated-meta {
    margin-top: 12px;
    font-size: 11px;
    font-weight: 400;
    color: var(--text-muted, #94a3b8);
  }
  .empty-desc {
    color: var(--text-muted, #94a3b8);
  }
  .empty-state {
    text-align: center;
    padding: 40px;
    background: rgba(0,0,0,0.2);
    border-radius: var(--radius-lg, 20px);
    color: var(--text-muted, #94a3b8);
    border: 1px dashed rgba(255, 255, 255, 0.2);
  }
</style>
