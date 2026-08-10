<script>
  import { createEventDispatcher } from 'svelte';
  
  export let projects = [];
  export let title = "เลือกโครงการ (Project Selection)";
  export let subtitle = "กรุณาเลือกโครงการที่ต้องการ เพื่อให้ AI อ้างอิงข้อมูลเปรียบเทียบจาก Knowledge Base ที่ถูกต้อง";
  
  const dispatch = createEventDispatcher();
  
  function selectProject(p) {
    dispatch('select', p);
  }
</script>

<div class="header-text">
  <h2>{title}</h2>
  <p>{subtitle}</p>
</div>

<div class="project-grid">
  {#if projects.length === 0}
    <div class="empty-state">
      ไม่พบโครงการในระบบ กรุณาสร้างโครงการที่หน้า Knowledge Base ก่อน
    </div>
  {:else}
    {#each projects as p}
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="project-card" on:click={() => selectProject(p)}>
        <div class="card-header-row">
          <div class="p-code">{p.project_code}</div>
        </div>
        <div class="p-name">{p.name || p.project_name}</div>
        
        <div class="p-status-section">
          <div class="p-meta-label">สถานะ (STATUS)</div>
          <div class="p-status-value" class:active={p.status === 'Active'} class:inactive={p.status !== 'Active'}>{p.status || 'Active'}</div>
        </div>
        
        <div class="p-desc-section">
          <div class="p-meta-label">รายละเอียด (DESCRIPTION)</div>
          <div class="p-desc-box">
            {#if p.description}
              {p.description}
            {:else}
              <span class="empty-desc">ไม่มีรายละเอียด</span>
            {/if}
          </div>
        </div>
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
  
  .project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px;
    width: 100%;
  }
  .project-card {
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
  }
  .project-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  }
  .project-card:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(147, 51, 234, 0.5);
    box-shadow: 0 12px 30px -10px rgba(147, 51, 234, 0.4);
    transform: translateY(-4px);
  }
  .card-header-row {
    margin-bottom: 12px;
  }
  .p-code {
    font-size: 12px;
    color: #c084fc;
    font-weight: 700;
    background: rgba(147, 51, 234, 0.15);
    padding: 6px 12px;
    border-radius: 6px;
    display: inline-block;
    letter-spacing: 0.5px;
  }
  .p-name {
    font-size: 18px;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 20px;
    line-height: 1.4;
  }
  .p-status-section {
    margin-bottom: 16px;
  }
  .p-desc-section {
    margin-bottom: 0;
  }
  .p-meta-label {
    font-size: 12px;
    color: #ffffff;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .p-status-value {
    font-size: 15px;
    font-weight: 600;
  }
  .p-status-value.active {
    color: #22c55e;
  }
  .p-status-value.inactive {
    color: #ef4444;
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
