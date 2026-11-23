<script>
  import { createEventDispatcher } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import { getLabelTextColor } from './qaBoardUtils.js';

  export let showConfigModal = false;
  export let configProvider = 'trello';
  export let trelloApiKey = '';
  export let trelloToken = '';
  export let trelloBoardId = '';
  export let githubToken = '';
  export let githubOwner = '';
  export let githubRepo = '';
  export let isTestingConnection = false;
  export let isSavingConfig = false;
  export let configErrors = {};

  export let showAgileSummaryModal = false;
  export let markUnestimated = false;
  export let agilePointsSummary = { totalPoints: 0, totalCards: 0, unestimatedCards: 0, columnsSummary: [] };

  export let showFilterModal = false;
  export let activeTab = 'live';
  export let cardSearchQuery = '';
  export let filterNoMembers = false;
  export let selectedMemberIds = new Set();
  export let filterNoLabels = false;
  export let selectedLabelNames = new Set();
  export let filterSavedStatus = 'all';
  export let filterCompletion = 'all';
  export let filterTypes = new Set();
  export let boardMembersList = [];
  export let boardLabelsList = [];
  export let boardTypesList = [];
  export let activeFilterCount = 0;
  export let totalFilteredCardsCount = 0;

  export let showImageModal = false;
  export let previewModalImage = null;
  export let previewModalAlt = 'Image Preview';

  const dispatch = createEventDispatcher();

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fadeDur = prefersReducedMotion ? 0 : 150;
  const scaleDur = prefersReducedMotion ? 0 : 180;

  function trapFocus(e) {
    if (e.key !== 'Tab') return;
    const dialog = e.currentTarget;
    if (!dialog) return;
    const focusables = dialog.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function handleAvatarError(e) {
    e.currentTarget.style.display = 'none';
    if (e.currentTarget.nextElementSibling) {
      e.currentTarget.nextElementSibling.style.display = 'inline-flex';
    }
  }
</script>

<!-- 1. Board Integration Config Modal -->
{#if showConfigModal}
  <div
    class="obs-modal-backdrop"
    role="presentation"
    transition:fade={{ duration: fadeDur }}
    on:click={() => dispatch('closeConfig')}
  >
    <div
      class="obs-modal-card config-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="board-config-title"
      tabindex="-1"
      on:keydown={trapFocus}
      on:click|stopPropagation
      in:scale={{ start: 0.96, duration: scaleDur }}
    >
      <div class="obs-modal-header">
        <div class="header-title-wrap">
          <div class="header-icon-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
            </svg>
          </div>
          <div>
            <h3 id="board-config-title" class="obs-modal-title">ตั้งค่าการเชื่อมต่อบอร์ด (Board Integration)</h3>
            <p class="obs-modal-subtitle">กำหนดค่าการเชื่อมต่อเพื่อดึงการ์ดงานจาก Trello หรือ GitHub เข้าสู่ระบบ QA Agent & RAG</p>
          </div>
        </div>
        <button type="button" class="btn-icon-close" aria-label="ปิดหน้าต่างตั้งค่า" on:click={() => dispatch('closeConfig')}>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="provider-tabs" role="tablist" aria-label="เลือกผู้ให้บริการบอร์ด">
        <button
          type="button"
          role="tab"
          aria-selected={configProvider === 'trello'}
          class="provider-tab-btn"
          class:active={configProvider === 'trello'}
          on:click={() => { configProvider = 'trello'; configErrors = {}; }}
        >
          <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19.5 2h-15A2.5 2.5 0 0 0 2 4.5v15A2.5 2.5 0 0 0 4.5 22h15a2.5 2.5 0 0 0 2.5-2.5v-15A2.5 2.5 0 0 0 19.5 2zm-8.25 15a1.25 1.25 0 0 1-1.25-1.25V6.75a1.25 1.25 0 0 1 1.25-1.25h3.5a1.25 1.25 0 0 1 1.25 1.25v9a1.25 1.25 0 0 1-1.25 1.25h-3.5zm-5.5-4a1.25 1.25 0 0 1-1.25-1.25V6.75A1.25 1.25 0 0 1 6 5.5h3.5A1.25 1.25 0 0 1 10.75 6.75v5A1.25 1.25 0 0 1 9.5 13H6z"/>
          </svg>
          <span>Trello Board</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={configProvider === 'github'}
          class="provider-tab-btn"
          class:active={configProvider === 'github'}
          on:click={() => { configProvider = 'github'; configErrors = {}; }}
        >
          <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path>
          </svg>
          <span>GitHub Issues & Projects</span>
        </button>
      </div>

      <div class="obs-modal-body">
        {#if configProvider === 'trello'}
          <div class="provider-guide">
            <p><strong>วิธีรับค่าจาก Trello:</strong> ไปที่ <a href="https://trello.com/power-ups/admin" target="_blank" rel="noreferrer">Trello Power-Ups Admin</a> เพื่อสร้าง API Key และคลิกลิงก์ <em>Token</em> เพื่ออนุมัติสิทธิ์ ส่วน <strong>Board ID</strong> ดูได้จาก URL ของบอร์ด เช่น <code>trello.com/b/<strong>AbCdEf12</strong>/board-name</code></p>
          </div>

          <div class="form-group">
            <label for="trello_api_key">Trello API Key <span class="required">*</span></label>
            <input
              type="text"
              id="trello_api_key"
              bind:value={trelloApiKey}
              class:input-error={configErrors.trelloApiKey}
              placeholder="กรอก Trello API Key (32 ตัวอักษร)..."
            />
            {#if configErrors.trelloApiKey}
              <span class="field-error-msg">{configErrors.trelloApiKey}</span>
            {/if}
          </div>

          <div class="form-group">
            <label for="trello_token">Trello API Token <span class="required">*</span></label>
            <input
              type="password"
              id="trello_token"
              bind:value={trelloToken}
              class:input-error={configErrors.trelloToken}
              placeholder="กรอก Trello Token (64 ตัวอักษร)..."
            />
            {#if configErrors.trelloToken}
              <span class="field-error-msg">{configErrors.trelloToken}</span>
            {/if}
          </div>

          <div class="form-group">
            <label for="trello_board_id">Trello Board ShortLink / ID <span class="required">*</span></label>
            <input
              type="text"
              id="trello_board_id"
              bind:value={trelloBoardId}
              class:input-error={configErrors.trelloBoardId}
              placeholder="เช่น d7aBcDeF หรือวาง URL เต็มของบอร์ด..."
            />
            {#if configErrors.trelloBoardId}
              <span class="field-error-msg">{configErrors.trelloBoardId}</span>
            {/if}
          </div>
        {:else}
          <div class="provider-guide">
            <p><strong>วิธีรับค่าจาก GitHub:</strong> ไปที่ GitHub ➔ Settings ➔ Developer Settings ➔ <a href="https://github.com/settings/tokens" target="_blank" rel="noreferrer">Personal Access Tokens</a> โดยเลือกสิทธิ์อ่าน/เขียน <code>repo</code> และ <code>issues</code></p>
          </div>

          <div class="form-group">
            <label for="github_token">GitHub Personal Access Token (PAT) <span class="required">*</span></label>
            <input
              type="password"
              id="github_token"
              bind:value={githubToken}
              class:input-error={configErrors.githubToken}
              placeholder="เช่น ghp_xxxxxxxxxxxx หรือ github_pat_..."
            />
            {#if configErrors.githubToken}
              <span class="field-error-msg">{configErrors.githubToken}</span>
            {/if}
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="github_owner">Repository Owner / Org <span class="required">*</span></label>
              <input
                type="text"
                id="github_owner"
                bind:value={githubOwner}
                class:input-error={configErrors.githubOwner}
                placeholder="เช่น AkradTTT08 หรือ MyOrg"
              />
              {#if configErrors.githubOwner}
                <span class="field-error-msg">{configErrors.githubOwner}</span>
              {/if}
            </div>

            <div class="form-group">
              <label for="github_repo">Repository Name <span class="required">*</span></label>
              <input
                type="text"
                id="github_repo"
                bind:value={githubRepo}
                class:input-error={configErrors.githubRepo}
                placeholder="เช่น OCR-Document"
              />
              {#if configErrors.githubRepo}
                <span class="field-error-msg">{configErrors.githubRepo}</span>
              {/if}
            </div>
          </div>
        {/if}
      </div>

      <div class="obs-modal-footer">
        <button type="button" class="btn-obs-outline" on:click={() => dispatch('testConnection')} disabled={isTestingConnection}>
          {#if isTestingConnection}
            <span class="spinner-small"></span> กำลังทดสอบ...
          {:else}
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
            </svg>
            ทดสอบการเชื่อมต่อ
          {/if}
        </button>

        <div class="footer-right-btns">
          <button type="button" class="btn-obs-ghost" on:click={() => dispatch('closeConfig')}>ยกเลิก</button>
          <button type="button" class="btn-obs-primary" on:click={() => dispatch('saveConfig')} disabled={isSavingConfig}>
            {#if isSavingConfig}
              <span class="spinner-small"></span> กำลังบันทึก...
            {:else}
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                <polyline points="17 21 17 13 7 13 7 21"></polyline>
                <polyline points="7 3 7 8 15 8"></polyline>
              </svg>
              บันทึกและเชื่อมต่อ
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- 2. Agile Tools & Story Points Modal -->
{#if showAgileSummaryModal}
  <div
    class="obs-modal-backdrop"
    role="presentation"
    transition:fade={{ duration: fadeDur }}
    on:click={() => dispatch('closeAgile')}
  >
    <div
      class="obs-modal-card agile-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="agile-tools-title"
      tabindex="-1"
      on:keydown={trapFocus}
      on:click|stopPropagation
      in:scale={{ start: 0.96, duration: scaleDur }}
    >
      <div class="obs-modal-header">
        <div class="header-title-wrap">
          <div class="header-icon-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
          </div>
          <div>
            <h3 id="agile-tools-title" class="obs-modal-title">สรุปแต้ม Story Points (Agile Tools)</h3>
            <p class="obs-modal-subtitle">คำนวณจากค่า Story Points ของการ์ดแต่ละคอลัมน์ในมุมมองปัจจุบัน</p>
          </div>
        </div>
        <button type="button" class="btn-icon-close" aria-label="ปิดหน้าต่าง Agile Tools" on:click={() => dispatch('closeAgile')}>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="obs-modal-body">
        <div class="agile-toggle-row">
          <div>
            <span class="toggle-label">ไฮไลต์การ์ดที่ยังไม่ได้ประเมินแต้ม (Mark Unestimated)</span>
            <p class="toggle-help">แสดงป้ายเตือนบนการ์ดที่ยังไม่มีค่า Story Points</p>
          </div>
          <label class="switch">
            <input type="checkbox" bind:checked={markUnestimated} aria-label="ไฮไลต์การ์ดที่ยังไม่ได้ประเมินแต้ม" />
            <span class="slider round"></span>
          </label>
        </div>

        <div class="points-counts-section">
          <h4 class="points-counts-title">แต้มรวมแยกตามคอลัมน์ (Column Story Points)</h4>
          <div class="points-list-container">
            {#each agilePointsSummary.columnsSummary as col}
              <div class="point-item-row">
                <span class="point-col-name">
                  <span class="point-dot" style="background-color: {col.color || '#6366f1'};"></span>
                  {col.title}
                  <small class="col-card-sub">({col.count} ใบ)</small>
                </span>
                <span class="point-val">{col.points} pts</span>
              </div>
            {/each}

            <div class="point-total-row">
              <span class="total-label">แต้มรวมทั้งหมด (TOTAL)</span>
              <span class="total-pts-highlight">{agilePointsSummary.totalPoints} pts</span>
            </div>
          </div>
        </div>

        <div class="agile-extra-stats">
          <div class="stat-badge">
            <span>การ์ดทั้งหมด:</span>
            <strong>{agilePointsSummary.totalCards} ใบ</strong>
          </div>
          <div class="stat-badge">
            <span>ยังไม่ประเมินแต้ม:</span>
            <strong>{agilePointsSummary.unestimatedCards} ใบ</strong>
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- 3. Filter Cards Modal -->
{#if showFilterModal}
  <div
    class="obs-modal-backdrop"
    role="presentation"
    transition:fade={{ duration: fadeDur }}
    on:click={() => dispatch('closeFilter')}
  >
    <div
      class="obs-modal-card filter-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="filter-modal-title"
      tabindex="-1"
      on:keydown={trapFocus}
      on:click|stopPropagation
      in:scale={{ start: 0.96, duration: scaleDur }}
    >
      <div class="obs-modal-header">
        <div class="header-title-wrap">
          <div class="header-icon-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
            </svg>
          </div>
          <div>
            <h3 id="filter-modal-title" class="obs-modal-title">ตัวกรองการ์ด (Filter Cards)</h3>
            <p class="obs-modal-subtitle">กรองตามคำค้นหา สมาชิก ป้ายกำกับ ประเภท และสถานะความคืบหน้า</p>
          </div>
        </div>
        <button type="button" class="btn-icon-close" aria-label="ปิดหน้าต่างตัวกรอง" on:click={() => dispatch('closeFilter')}>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="obs-modal-body filter-scroll-body">
        <!-- 1. Keyword -->
        <div class="filter-section">
          <label class="filter-section-title" for="filter-keyword-input">คำค้นหา (Keyword)</label>
          <div class="filter-input-wrapper">
            <input
              id="filter-keyword-input"
              type="text"
              placeholder="ค้นหาชื่อการ์ด, รหัส, สมาชิก, ป้ายกำกับ..."
              bind:value={cardSearchQuery}
              class="filter-text-input"
            />
            {#if cardSearchQuery}
              <button type="button" class="clear-input-inline" aria-label="ล้างคำค้นหา" on:click={() => (cardSearchQuery = '')}>✕</button>
            {/if}
          </div>
        </div>

        <!-- 2. Saved Status (in Live Tab) -->
        {#if activeTab === 'live'}
          <fieldset class="filter-section filter-fieldset">
            <legend class="filter-section-title">สถานะบันทึกในโครงการ & RAG</legend>
            <div class="filter-pill-group">
              <button
                type="button"
                class="filter-pill-btn"
                class:active={filterSavedStatus === 'all'}
                on:click={() => (filterSavedStatus = 'all')}
              >
                ทั้งหมด
              </button>
              <button
                type="button"
                class="filter-pill-btn"
                class:active={filterSavedStatus === 'saved'}
                on:click={() => (filterSavedStatus = 'saved')}
              >
                บันทึกแล้ว (RAG)
              </button>
              <button
                type="button"
                class="filter-pill-btn"
                class:active={filterSavedStatus === 'unsaved'}
                on:click={() => (filterSavedStatus = 'unsaved')}
              >
                ยังไม่บันทึก
              </button>
            </div>
          </fieldset>
        {/if}

        <!-- 3. Card Completion Status -->
        <fieldset class="filter-section filter-fieldset">
          <legend class="filter-section-title">สถานะความสมบูรณ์ (Completion)</legend>
          <div class="filter-pill-group">
            <button
              type="button"
              class="filter-pill-btn"
              class:active={filterCompletion === 'all'}
              on:click={() => (filterCompletion = 'all')}
            >
              ทั้งหมด
            </button>
            <button
              type="button"
              class="filter-pill-btn"
              class:active={filterCompletion === 'incomplete'}
              on:click={() => (filterCompletion = 'incomplete')}
            >
              กำลังดำเนินการ
            </button>
            <button
              type="button"
              class="filter-pill-btn"
              class:active={filterCompletion === 'complete'}
              on:click={() => (filterCompletion = 'complete')}
            >
              เสร็จสิ้น (Done)
            </button>
          </div>
        </fieldset>

        <!-- 4. Card Types (Exposes filterTypes!) -->
        {#if boardTypesList.length > 0}
          <fieldset class="filter-section filter-fieldset">
            <legend class="filter-section-title">ประเภทการ์ด / ความสำคัญ (Type)</legend>
            <div class="filter-pill-group">
              {#each boardTypesList as tName}
                <button
                  type="button"
                  class="filter-pill-btn"
                  class:active={filterTypes.has(tName)}
                  on:click={() => dispatch('toggleType', tName)}
                >
                  {tName}
                </button>
              {/each}
            </div>
          </fieldset>
        {/if}

        <!-- 5. Members -->
        <fieldset class="filter-section filter-fieldset">
          <legend class="filter-section-title">ผู้รับผิดชอบ (Members)</legend>
          <label class="filter-checkbox-item">
            <input
              type="checkbox"
              bind:checked={filterNoMembers}
              on:change={() => { if (filterNoMembers) dispatch('clearMembers'); }}
            />
            <span class="member-icon-circle" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
            </span>
            <span>ไม่มีผู้รับผิดชอบ (Unassigned)</span>
          </label>

          {#if !filterNoMembers && boardMembersList.length > 0}
            <div class="filter-members-sublist">
              {#each boardMembersList as member}
                {@const mKey = member.id || member.username || member.name}
                <label class="filter-checkbox-item member-item">
                  <input
                    type="checkbox"
                    checked={selectedMemberIds.has(mKey)}
                    on:change={() => dispatch('toggleMember', mKey)}
                  />
                  {#if member.avatar}
                    <img
                      src={member.avatar}
                      alt={member.name}
                      class="filter-member-avatar"
                      on:error={handleAvatarError}
                    />
                    <span class="filter-member-initials" style="display: none;">{member.initials || (member.name ? member.name[0].toUpperCase() : 'M')}</span>
                  {:else}
                    <span class="filter-member-initials">{member.initials || (member.name ? member.name[0].toUpperCase() : 'M')}</span>
                  {/if}
                  <span class="member-name-text">{member.name} {#if member.username}<small>@{member.username}</small>{/if}</span>
                </label>
              {/each}
            </div>
          {/if}
        </fieldset>

        <!-- 6. Labels -->
        <fieldset class="filter-section filter-fieldset">
          <legend class="filter-section-title">ป้ายกำกับ (Labels)</legend>
          <label class="filter-checkbox-item">
            <input
              type="checkbox"
              bind:checked={filterNoLabels}
              on:change={() => { if (filterNoLabels) dispatch('clearLabels'); }}
            />
            <span class="member-icon-circle" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
                <line x1="7" y1="7" x2="7.01" y2="7"></line>
              </svg>
            </span>
            <span>ไม่มีป้ายกำกับ (No labels)</span>
          </label>

          {#if !filterNoLabels && boardLabelsList.length > 0}
            <div class="filter-labels-sublist">
              {#each boardLabelsList as label}
                {@const lKey = label.name.toLowerCase()}
                {@const bg = label.color || '#6366f1'}
                {@const fg = getLabelTextColor(bg)}
                <label class="filter-label-pill-item">
                  <input
                    type="checkbox"
                    checked={selectedLabelNames.has(lKey)}
                    on:change={() => dispatch('toggleLabel', label.name)}
                  />
                  <span class="filter-label-bar" style="background-color: {bg}; color: {fg};">
                    <span class="label-text-bold">{label.name}</span>
                    <span class="label-count-tag">{label.count}</span>
                  </span>
                </label>
              {/each}
            </div>
          {/if}
        </fieldset>
      </div>

      <div class="obs-modal-footer">
        <button type="button" class="btn-obs-ghost" on:click={() => dispatch('resetFilters')} disabled={activeFilterCount === 0}>
          ล้างตัวกรองทั้งหมด
        </button>
        <button type="button" class="btn-obs-primary" on:click={() => dispatch('closeFilter')}>
          แสดงผลลัพธ์ ({totalFilteredCardsCount} การ์ด)
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- 4. Image Lightbox Modal -->
{#if showImageModal && previewModalImage}
  <div
    class="obs-modal-backdrop lightbox-backdrop"
    role="presentation"
    transition:fade={{ duration: fadeDur }}
    on:click={() => dispatch('closeImage')}
  >
    <div
      class="image-lightbox-content"
      role="dialog"
      aria-modal="true"
      aria-label="ดูรูปภาพขนาดเต็ม"
      tabindex="-1"
      on:keydown={trapFocus}
      on:click|stopPropagation
      in:scale={{ start: 0.96, duration: scaleDur }}
    >
      <button type="button" class="lightbox-close-btn" aria-label="ปิดรูปภาพขนาดเต็ม" on:click={() => dispatch('closeImage')} title="ปิด (Esc)">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="18" height="18">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
      <img src={previewModalImage} alt={previewModalAlt} class="lightbox-full-img" />
      <div class="lightbox-toolbar">
        <a href={previewModalImage} target="_blank" rel="noreferrer" class="btn-obs-outline">
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
            <polyline points="15 3 21 3 21 9"></polyline>
            <line x1="10" y1="14" x2="21" y2="3"></line>
          </svg>
          เปิดดูรูปภาพขนาดเต็มในแท็บใหม่
        </a>
      </div>
    </div>
  </div>
{/if}

<style>
  .obs-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(5, 5, 10, 0.78);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    z-index: var(--z-modal, 10000);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
  }

  .obs-modal-card {
    width: 100%;
    max-width: 560px;
    max-height: calc(100dvh - 32px);
    background: var(--bg2);
    border: 1px solid rgba(168, 85, 247, 0.26);
    border-radius: var(--radius-lg);
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    color: var(--text-main);
    font-family: var(--font-th);
  }

  .obs-modal-card.agile-card { max-width: 480px; }
  .obs-modal-card.filter-card { max-width: 500px; }

  .obs-modal-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 18px 20px;
    background: var(--bg);
    border-bottom: 1px solid var(--glass-border);
  }

  .header-title-wrap {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    min-width: 0;
  }

  .header-icon-badge {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: var(--primary-soft-text);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .obs-modal-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-main);
  }

  .obs-modal-subtitle {
    margin: 3px 0 0;
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.45;
  }

  .btn-icon-close {
    width: 34px;
    height: 34px;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: color 0.16s ease, background-color 0.16s ease, border-color 0.16s ease;
  }

  .btn-icon-close:hover {
    color: var(--text-main);
    background: rgba(244, 63, 94, 0.16);
    border-color: rgba(244, 63, 94, 0.38);
  }

  .provider-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    padding: 12px 20px 0;
    background: var(--bg2);
  }

  .provider-tab-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: 38px;
    padding: 8px 14px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border);
    background: var(--surface-card);
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
  }

  .provider-tab-btn.active {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(129, 140, 248, 0.55);
    color: var(--text-main);
  }

  .obs-modal-body {
    padding: 18px 20px;
    overflow-y: auto;
    overscroll-behavior: contain;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .provider-guide {
    padding: 12px 14px;
    border-radius: var(--radius-sm);
    background: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(99, 102, 241, 0.24);
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.55;
  }

  .provider-guide a {
    color: var(--primary-soft-text);
    text-decoration: underline;
  }

  .provider-guide code {
    background: rgba(0, 0, 0, 0.35);
    padding: 1px 5px;
    border-radius: 4px;
    color: var(--text-main);
    font-family: var(--font-en);
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-main);
  }

  .required { color: var(--danger-soft-text); }

  .form-group input,
  .filter-text-input {
    width: 100%;
    min-height: 38px;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border-light);
    background: var(--bg);
    color: var(--text-main);
    font-size: 13px;
    font-family: inherit;
    transition: border-color 0.16s ease;
  }

  .form-group input:focus,
  .filter-text-input:focus {
    border-color: var(--primary);
    outline: none;
  }

  .form-group input.input-error {
    border-color: var(--danger);
  }

  .field-error-msg {
    font-size: 11.5px;
    color: var(--danger-soft-text);
  }

  .obs-modal-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 14px 20px;
    background: var(--bg);
    border-top: 1px solid var(--glass-border);
    flex-wrap: wrap;
  }

  .footer-right-btns {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-obs-primary,
  .btn-obs-outline,
  .btn-obs-ghost {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    min-height: 36px;
    padding: 7px 14px;
    border-radius: var(--radius-sm);
    font-size: 12.8px;
    font-weight: 600;
    cursor: pointer;
    font-family: var(--font-th);
    transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
  }

  .btn-obs-primary {
    background: var(--gradient-main);
    border: 1px solid rgba(129, 140, 248, 0.4);
    color: #ffffff;
  }

  .btn-obs-primary:disabled,
  .btn-obs-outline:disabled,
  .btn-obs-ghost:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .btn-obs-outline {
    background: var(--surface-card);
    border: 1px solid var(--glass-border-light);
    color: var(--text-main);
    text-decoration: none;
  }

  .btn-obs-outline:hover:not(:disabled) {
    background: var(--surface-card-hover);
    border-color: var(--primary-soft-text);
  }

  .btn-obs-ghost {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
  }

  .btn-obs-ghost:hover:not(:disabled) {
    color: var(--text-main);
    background: rgba(255, 255, 255, 0.05);
  }

  /* Agile Modal */
  .agile-toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 12px 14px;
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
  }

  .toggle-label { font-size: 13px; font-weight: 600; color: var(--text-main); }
  .toggle-help { margin: 2px 0 0; font-size: 11.5px; color: var(--text-dim); }

  .switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
    flex-shrink: 0;
  }

  .switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }

  .slider {
    position: absolute;
    cursor: pointer;
    inset: 0;
    background-color: rgba(255, 255, 255, 0.14);
    border: 1px solid var(--glass-border-light);
    transition: background-color 0.2s ease;
    border-radius: 999px;
  }

  .slider::before {
    position: absolute;
    content: "";
    height: 18px;
    width: 18px;
    left: 2px;
    bottom: 2px;
    background-color: #ffffff;
    transition: transform 0.2s ease;
    border-radius: 50%;
  }

  .switch input:checked + .slider {
    background-color: var(--primary);
    border-color: var(--primary);
  }

  .switch input:checked + .slider::before {
    transform: translateX(20px);
  }

  .switch input:focus-visible + .slider {
    outline: 2px solid var(--primary-soft-text);
    outline-offset: 2px;
  }

  .points-counts-title {
    margin: 0 0 8px;
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-muted);
  }

  .points-list-container {
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 12px;
  }

  .point-item-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px;
    border-radius: var(--radius-sm);
    font-size: 13px;
  }

  .point-col-name {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
  }

  .point-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
  }

  .col-card-sub { color: var(--text-dim); font-size: 11.5px; }

  .point-val {
    font-family: var(--font-en);
    font-weight: 600;
    color: var(--primary-soft-text);
    font-variant-numeric: tabular-nums;
  }

  .point-total-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 8px 4px;
    margin-top: 4px;
    border-top: 1px solid var(--glass-border);
    font-weight: 700;
  }

  .total-pts-highlight {
    font-family: var(--font-en);
    font-size: 15px;
    color: var(--success-soft-text);
    font-variant-numeric: tabular-nums;
  }

  .agile-extra-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .stat-badge {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: var(--radius-sm);
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    font-size: 12.5px;
    color: var(--text-muted);
  }

  .stat-badge strong { color: var(--text-main); }

  /* Filter Modal */
  .filter-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .filter-fieldset {
    border: none;
    padding: 0;
    margin: 0;
  }

  .filter-section-title {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--text-main);
    margin-bottom: 4px;
    display: block;
  }

  .filter-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .clear-input-inline {
    position: absolute;
    right: 8px;
    width: 26px;
    height: 26px;
    border-radius: 6px;
    border: none;
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-muted);
    cursor: pointer;
  }

  .filter-pill-group {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .filter-pill-btn {
    min-height: 32px;
    padding: 5px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border);
    background: var(--surface-card);
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }

  .filter-pill-btn.active {
    background: rgba(99, 102, 241, 0.22);
    border-color: var(--primary-soft-text);
    color: var(--text-main);
  }

  .filter-checkbox-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 13px;
    color: var(--text-main);
  }

  .filter-checkbox-item:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  .member-icon-circle,
  .filter-member-initials {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: var(--primary-soft-text);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .filter-member-avatar {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }

  .member-name-text small {
    color: var(--text-dim);
    margin-left: 4px;
  }

  .filter-members-sublist,
  .filter-labels-sublist {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 180px;
    overflow-y: auto;
    padding-left: 4px;
  }

  .filter-label-pill-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 6px;
    cursor: pointer;
  }

  .filter-label-bar {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
  }

  .label-count-tag {
    padding: 1px 6px;
    border-radius: 999px;
    background: rgba(0, 0, 0, 0.25);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  /* Lightbox */
  .image-lightbox-content {
    position: relative;
    max-width: 92vw;
    max-height: 90dvh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  .lightbox-close-btn {
    position: absolute;
    top: -12px;
    right: -12px;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: var(--bg2);
    border: 1px solid var(--glass-border-light);
    color: var(--text-main);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
  }

  .lightbox-full-img {
    max-width: 90vw;
    max-height: 80dvh;
    object-fit: contain;
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border-light);
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.85);
  }

  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.28);
    border-top-color: currentColor;
    border-radius: 50%;
    display: inline-block;
    animation: spinModal 0.75s linear infinite;
  }

  @keyframes spinModal { to { transform: rotate(360deg); } }

  @media (prefers-reduced-motion: reduce) {
    .spinner-small { animation: none; }
    .slider, .slider::before { transition: none; }
  }
</style>

