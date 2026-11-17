<script>
  import { createEventDispatcher } from 'svelte';
  import { authAllowedProjects } from './authStore.js';
  
  export let projects = [];
  export let title = "เลือกโครงการ (Project Selection)";
  export let subtitle = "กรุณาเลือกโครงการที่ต้องการ เพื่อให้ AI อ้างอิงข้อมูลเปรียบเทียบจาก Knowledge Base ที่ถูกต้อง";
  
  const dispatch = createEventDispatcher();

  let searchQuery = "";
  let statusFilter = "all"; // 'all' | 'Active' | 'Inactive'
  
  function selectProject(p) {
    dispatch('select', p);
  }

  $: allowedProjects = projects.filter(p => {
    if (!$authAllowedProjects || $authAllowedProjects.includes('all')) return true;
    const pId = String(p.id || p.project_id || '').trim().toLowerCase();
    const pCode = String(p.project_code || '').trim().toLowerCase();
    return $authAllowedProjects.some(allowed => {
      const a = String(allowed).trim().toLowerCase();
      return (pId && a === pId) || (pCode && a === pCode);
    });
  });

  $: activeCount = allowedProjects.filter(p => (p.status || 'Active') === 'Active').length;
  $: inactiveCount = allowedProjects.length - activeCount;

  $: filteredProjects = allowedProjects.filter(p => {
    const pStatus = p.status || 'Active';
    if (statusFilter === 'Active' && pStatus !== 'Active') return false;
    if (statusFilter === 'Inactive' && pStatus === 'Active') return false;
    const q = searchQuery.trim().toLowerCase();
    if (!q) return true;
    const code = String(p.project_code || '').toLowerCase();
    const name = String(p.name || p.project_name || '').toLowerCase();
    const desc = String(p.description || '').toLowerCase();
    return code.includes(q) || name.includes(q) || desc.includes(q);
  });
</script>

<div class="project-selection-wrapper">
  <header class="deck-header">
    <h2>{title}</h2>
    <p>{subtitle}</p>

    {#if allowedProjects.length > 0}
      <div class="deck-toolbar">
        <div class="deck-search">
          <svg class="search-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            bind:value={searchQuery}
            placeholder="ค้นหารหัสโครงการ หรือชื่อโครงการ..."
            aria-label="ค้นหาโครงการ"
          />
          {#if searchQuery}
            <button type="button" class="clear-search-btn" aria-label="ล้างคำค้นหา" on:click={() => (searchQuery = "")}>✕</button>
          {/if}
          <span class="search-beam" aria-hidden="true"></span>
        </div>

        <div class="status-filter-group" role="group" aria-label="กรองตามสถานะโครงการ">
          <button
            type="button"
            class="filter-pill"
            class:selected={statusFilter === 'all'}
            on:click={() => (statusFilter = 'all')}
          >
            ทั้งหมด <span class="pill-count">{allowedProjects.length}</span>
          </button>
          <button
            type="button"
            class="filter-pill"
            class:selected={statusFilter === 'Active'}
            on:click={() => (statusFilter = 'Active')}
          >
            <span class="dot active-dot" aria-hidden="true"></span>
            Active <span class="pill-count">{activeCount}</span>
          </button>
          {#if inactiveCount > 0}
            <button
              type="button"
              class="filter-pill"
              class:selected={statusFilter === 'Inactive'}
              on:click={() => (statusFilter = 'Inactive')}
            >
              <span class="dot inactive-dot" aria-hidden="true"></span>
              Inactive <span class="pill-count">{inactiveCount}</span>
            </button>
          {/if}
        </div>
      </div>
    {/if}
  </header>

  <div class="project-grid">
    {#if allowedProjects.length === 0}
      <div class="empty-state">
        <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
        <div class="empty-title">ไม่พบโครงการที่คุณมีสิทธิ์เข้าถึง</div>
        <div class="empty-sub">กรุณาติดต่อผู้ดูแลระบบเพื่อกำหนดสิทธิ์โครงการ หรือสร้างโครงการใหม่ในเมนู Project Management</div>
      </div>
    {:else if filteredProjects.length === 0}
      <div class="empty-state">
        <div class="empty-title">ไม่พบโครงการที่ตรงกับการค้นหา "{searchQuery}"</div>
        <button type="button" class="reset-filter-btn" on:click={() => { searchQuery = ""; statusFilter = "all"; }}>
          แสดงโครงการทั้งหมด
        </button>
      </div>
    {:else}
      {#each filteredProjects as p, idx (p.id || p.project_id || p.project_code || idx)}
        {@const isActive = (p.status || 'Active') === 'Active'}
        <button
          type="button"
          class="project-card"
          style="--idx: {Math.min(idx, 10)};"
          on:click={() => selectProject(p)}
        >
          <span class="card-glow" aria-hidden="true"></span>

          <div class="card-top-bar">
            <div class="code-cluster">
              <div class="project-emblem" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                  <polyline points="2 17 12 22 22 17"></polyline>
                  <polyline points="2 12 12 17 22 12"></polyline>
                </svg>
              </div>
              <span class="p-code">{p.project_code || 'PROJECT'}</span>
            </div>

            <span class="status-pill" class:active={isActive} class:inactive={!isActive}>
              <span class="status-dot" aria-hidden="true"></span>
              {p.status || 'Active'}
            </span>
          </div>

          <h3 class="p-name">{p.name || p.project_name}</h3>

          <div class="p-desc-box">
            {#if p.description}
              <p class="desc-text">{p.description}</p>
            {:else}
              <p class="desc-text empty-desc">ไม่มีรายละเอียดเพิ่มเติมสำหรับโครงการนี้</p>
            {/if}
          </div>

          <div class="card-action-footer">
            <span class="action-label">เข้าสู่พื้นที่ทำงานโครงการ</span>
            <span class="enter-arrow" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </span>
          </div>
        </button>
      {/each}
    {/if}
  </div>
</div>

<style>
  @keyframes cardRise {
    from {
      opacity: 0;
      transform: translateY(16px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .project-selection-wrapper {
    width: 100%;
    max-width: 100%;
    margin: 0;
    padding: 8px 0 40px;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    box-sizing: border-box;
  }

  /* ── Command Deck Header ── */
  .deck-header {
    width: 100%;
    max-width: 100%;
    text-align: center;
    margin-bottom: 28px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .deck-header h2 {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: clamp(28px, 3vw, 36px);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.2;
    margin: 0 0 10px;
    color: var(--text-main, #f8fafc);
  }

  .deck-header p {
    font-family: var(--font-th, 'Prompt', sans-serif);
    color: var(--text-muted, #94a3b8);
    font-size: 15px;
    line-height: 1.6;
    max-width: 65ch;
    margin: 0;
  }

  /* ── Search & Status Filter Toolbar ── */
  .deck-toolbar {
    margin-top: 24px;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .deck-search {
    position: relative;
    flex: 1 1 300px;
    max-width: 420px;
    display: flex;
    align-items: center;
    background: rgba(10, 11, 18, 0.65);
    border: 1px solid var(--glass-border-light, rgba(255, 255, 255, 0.15));
    border-radius: var(--radius-md, 12px);
    overflow: hidden;
    transition: border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .deck-search:focus-within {
    border-color: rgba(99, 102, 241, 0.75);
    box-shadow: 0 8px 24px -8px rgba(99, 102, 241, 0.35);
  }

  .search-icon {
    position: absolute;
    left: 14px;
    color: var(--text-dim, #475569);
    pointer-events: none;
    transition: color 0.22s ease;
  }

  .deck-search:focus-within .search-icon {
    color: var(--primary, #6366f1);
  }

  .deck-search input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main, #f8fafc);
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13.5px;
    padding: 10px 36px 10px 40px;
  }

  .deck-search input::placeholder {
    color: var(--text-dim, #475569);
  }

  .clear-search-btn {
    position: absolute;
    right: 8px;
    width: 24px;
    height: 24px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-muted, #94a3b8);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
  }

  .clear-search-btn:hover {
    color: var(--text-main, #f8fafc);
    background: rgba(255, 255, 255, 0.08);
  }

  .search-beam {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--primary, #6366f1), var(--secondary, #a855f7), var(--accent, #06b6d4));
    transform: scaleX(0);
    transform-origin: center;
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: none;
  }

  .deck-search:focus-within .search-beam {
    transform: scaleX(1);
  }

  .status-filter-group {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px;
    background: rgba(10, 11, 18, 0.65);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    border-radius: var(--radius-md, 12px);
  }

  .filter-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: var(--radius-sm, 8px);
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-muted, #94a3b8);
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .filter-pill:hover {
    color: var(--text-main, #f8fafc);
    background: rgba(255, 255, 255, 0.04);
  }

  .filter-pill.selected {
    color: var(--text-main, #f8fafc);
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.4);
  }

  .pill-count {
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.08);
    color: var(--text-main, #f8fafc);
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  .active-dot {
    background: var(--success, #10b981);
    box-shadow: 0 0 6px var(--success, #10b981);
  }

  .inactive-dot {
    background: var(--danger, #f43f5e);
  }

  /* ── Project Cards Grid ── */
  .project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
    width: 100%;
    max-width: 100%;
  }

  .project-card {
    font: inherit;
    color: inherit;
    background: rgba(18, 20, 28, 0.58);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: var(--radius-lg, 20px);
    padding: 24px;
    cursor: pointer;
    text-align: left;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    width: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 16px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1),
                border-color 0.28s cubic-bezier(0.16, 1, 0.3, 1),
                box-shadow 0.28s cubic-bezier(0.16, 1, 0.3, 1),
                background-color 0.28s ease;
    animation: cardRise 0.45s cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--idx, 0) * 45ms);
  }

  .project-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 8%;
    right: 8%;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
    transition: left 0.32s cubic-bezier(0.16, 1, 0.3, 1),
                right 0.32s cubic-bezier(0.16, 1, 0.3, 1),
                background 0.32s ease,
                height 0.2s ease;
    pointer-events: none;
  }

  .card-glow {
    position: absolute;
    top: -60px;
    right: -60px;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.22) 0%, rgba(168, 85, 247, 0.08) 45%, transparent 70%);
    opacity: 0.45;
    transition: opacity 0.32s ease, transform 0.32s cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: none;
  }

  .project-card:hover,
  .project-card:focus-visible {
    background: rgba(22, 25, 38, 0.78);
    border-color: rgba(99, 102, 241, 0.55);
    box-shadow: 0 20px 44px -12px rgba(99, 102, 241, 0.38);
    transform: translateY(-5px);
  }

  .project-card:hover::before,
  .project-card:focus-visible::before {
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--primary, #6366f1), var(--secondary, #a855f7), transparent);
  }

  .project-card:hover .card-glow,
  .project-card:focus-visible .card-glow {
    opacity: 1;
    transform: scale(1.25);
  }

  .project-card:active {
    transform: translateY(-2px);
  }

  /* ── Top Telemetry Bar ── */
  .card-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    position: relative;
    z-index: 1;
  }

  .code-cluster {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .project-emblem {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(168, 85, 247, 0.2));
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #c7d2fe;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1),
                background 0.28s ease,
                border-color 0.28s ease,
                color 0.28s ease;
  }

  .project-card:hover .project-emblem,
  .project-card:focus-visible .project-emblem {
    background: linear-gradient(135deg, var(--primary, #6366f1), var(--secondary, #a855f7));
    border-color: transparent;
    color: #ffffff;
    transform: scale(1.06);
  }

  .p-code {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 12.5px;
    color: #e0e7ff;
    font-weight: 700;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.3);
    padding: 5px 12px;
    border-radius: var(--radius-sm, 8px);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 11px;
    border-radius: 20px;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.03em;
    flex-shrink: 0;
  }

  .status-pill.active {
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.28);
    color: var(--success, #10b981);
  }

  .status-pill.inactive {
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.28);
    color: var(--danger, #f43f5e);
  }

  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 8px currentColor;
  }

  /* ── Project Title & Description ── */
  .p-name {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 20px;
    font-weight: 700;
    color: var(--text-main, #f8fafc);
    margin: 0;
    line-height: 1.35;
    letter-spacing: -0.01em;
    position: relative;
    z-index: 1;
  }

  .p-desc-box {
    background: rgba(10, 11, 18, 0.55);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    border-radius: var(--radius-md, 12px);
    padding: 12px 14px;
    flex: 1;
    display: flex;
    align-items: flex-start;
    min-height: 64px;
    position: relative;
    z-index: 1;
  }

  .desc-text {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13.5px;
    color: #cbd5e1;
    line-height: 1.55;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .empty-desc {
    color: var(--text-dim, #475569);
    font-style: italic;
  }

  /* ── Card Footer CTA ── */
  .card-action-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
    margin-top: auto;
    position: relative;
    z-index: 1;
  }

  .action-label {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 12.5px;
    font-weight: 500;
    color: var(--text-muted, #94a3b8);
    transition: color 0.22s ease;
  }

  .project-card:hover .action-label,
  .project-card:focus-visible .action-label {
    color: #e0e7ff;
  }

  .enter-arrow {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    color: var(--text-muted, #94a3b8);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.26s cubic-bezier(0.16, 1, 0.3, 1),
                background-color 0.26s ease,
                border-color 0.26s ease,
                color 0.26s ease;
  }

  .project-card:hover .enter-arrow,
  .project-card:focus-visible .enter-arrow {
    background: var(--primary, #6366f1);
    border-color: var(--primary, #6366f1);
    color: #ffffff;
    transform: translateX(4px);
  }

  /* ── Empty State ── */
  .empty-state {
    grid-column: 1 / -1;
    text-align: center;
    padding: 48px 24px;
    background: rgba(10, 11, 18, 0.55);
    border-radius: var(--radius-lg, 20px);
    color: var(--text-muted, #94a3b8);
    border: 1px dashed rgba(255, 255, 255, 0.16);
    max-width: 580px;
    margin: 0 auto;
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }

  .empty-title {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 16px;
    font-weight: 600;
    color: var(--text-main, #f8fafc);
  }

  .empty-sub {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13.5px;
    color: var(--text-muted, #94a3b8);
    max-width: 46ch;
    line-height: 1.5;
  }

  .reset-filter-btn {
    margin-top: 6px;
    padding: 8px 18px;
    border-radius: var(--radius-md, 12px);
    border: 1px solid rgba(99, 102, 241, 0.4);
    background: rgba(99, 102, 241, 0.15);
    color: #e0e7ff;
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s ease;
  }

  .reset-filter-btn:hover {
    background: rgba(99, 102, 241, 0.28);
  }

  @media (max-width: 640px) {
    .project-selection-wrapper {
      padding: 20px 14px 48px;
    }
    .project-grid {
      grid-template-columns: 1fr;
    }
    .deck-toolbar {
      flex-direction: column;
      align-items: stretch;
    }
    .deck-search {
      max-width: none;
    }
    .status-filter-group {
      justify-content: center;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .project-card {
      animation: none !important;
    }
    .project-card:hover,
    .project-card:focus-visible,
    .project-card:hover .project-emblem,
    .project-card:hover .enter-arrow,
    .search-beam {
      transform: none !important;
    }
  }
</style>
