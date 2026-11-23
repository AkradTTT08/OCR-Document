<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { fade, fly, slide } from 'svelte/transition';
  import {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAllNotifications
  } from './notificationStore.js';
  import { activeSidebarGroup, selectedProjectStore } from './qaHistoryStore.js';

  const dispatch = createEventDispatcher();

  let panelEl = null;
  let confirmClearAll = false;

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const flyDuration = prefersReducedMotion ? 0 : 200;
  const fadeDuration = prefersReducedMotion ? 0 : 140;
  const slideDuration = prefersReducedMotion ? 0 : 170;

  $: if ($notifications.length === 0) {
    confirmClearAll = false;
  }

  onMount(() => {
    panelEl?.focus({ preventScroll: true });
  });

  function resolveVariant(item) {
    const rawType = String(item?.type || '').toLowerCase();
    const msg = String(item?.message || '').toUpperCase();
    if (rawType === 'error' || msg.includes('REJECTED') || msg.includes('FAILED')) return 'error';
    if (rawType === 'success' || msg.includes('COMPLETED (100%)') || msg.includes('PASSED')) return 'success';
    if (rawType === 'warning') return 'warning';
    return 'info';
  }

  function handleNotiClick(noti) {
    markAsRead(noti.id);
    if (noti.actionView) {
      if (noti.actionPayload && (noti.actionPayload.group_name || noti.actionPayload.project_id)) {
        if (noti.actionPayload.project_id) {
          selectedProjectStore.set({
            id: noti.actionPayload.project_id,
            project_id: noti.actionPayload.project_id
          });
        }
        if (noti.actionPayload.group_name) {
          activeSidebarGroup.set({
            group_name: noti.actionPayload.group_name,
            group_type: noti.actionPayload.group_type || 'General',
            project_id: noti.actionPayload.project_id
          });
        }
      }
      dispatch('navigate', { view: noti.actionView, payload: noti.actionPayload });
    }
  }

  function handleConfirmClearAll() {
    confirmClearAll = false;
    clearAllNotifications();
  }

  function handlePanelKeydown(e) {
    if (e.key !== 'Tab' || !panelEl) return;
    const focusables = panelEl.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) {
      e.preventDefault();
      panelEl.focus({ preventScroll: true });
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first || document.activeElement === panelEl) {
        e.preventDefault();
        last.focus();
      }
    } else if (document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
</script>

<!-- Full-viewport backdrop overlay to dismiss when clicking outside -->
<div
  class="noti-overlay"
  role="presentation"
  on:click|stopPropagation={() => dispatch('close')}
></div>

<!-- Main Notification Dialog Container -->
<div
  bind:this={panelEl}
  id="noti-panel"
  class="noti-panel"
  role="dialog"
  aria-labelledby="noti-heading"
  tabindex="-1"
  on:keydown={handlePanelKeydown}
  in:fly={{ y: -8, duration: flyDuration }}
  out:fade={{ duration: fadeDuration }}
>
  <!-- Header -->
  <div class="noti-header">
    <div class="header-title-row">
      <div class="header-icon-box" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 01-3.46 0"></path>
        </svg>
      </div>
      <h3 id="noti-heading">การแจ้งเตือน</h3>
      {#if $unreadCount > 0}
        <span class="unread-pill">{$unreadCount} ใหม่</span>
      {/if}
    </div>

    {#if $unreadCount > 0}
      <button
        type="button"
        class="btn-mark-all"
        on:click={markAllAsRead}
        title="ทำเครื่องหมายว่าอ่านแล้วทั้งหมด"
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        อ่านทั้งหมด
      </button>
    {/if}
  </div>

  <!-- Notification List -->
  {#if $notifications.length === 0}
    <div class="empty-noti">
      <div class="empty-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" width="28" height="28">
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          <path d="M18.63 13A17.89 17.89 0 0 1 18 8"></path>
          <path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"></path>
          <path d="M18 8a6 6 0 0 0-9.33-5"></path>
          <line x1="1" y1="1" x2="23" y2="23"></line>
        </svg>
      </div>
      <p class="empty-title">ไม่มีรายการแจ้งเตือน</p>
      <p class="empty-text">เมื่อระบบวิเคราะห์เอกสารเสร็จสิ้น รายการจะแสดงที่นี่</p>
    </div>
  {:else}
    <ul class="noti-list">
      {#each $notifications as item (item.id)}
        {@const variant = resolveVariant(item)}
        <li
          class="noti-item variant-{variant}"
          class:unread={!item.read}
          transition:slide={{ duration: slideDuration }}
        >
          <button
            type="button"
            class="noti-item-main"
            on:click={() => handleNotiClick(item)}
          >
            <div class="item-icon-wrapper variant-{variant}" aria-hidden="true">
              {#if variant === 'error'}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="15" y1="9" x2="9" y2="15"></line>
                  <line x1="9" y1="9" x2="15" y2="15"></line>
                </svg>
              {:else if variant === 'success'}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                  <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
              {:else if variant === 'warning'}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                  <line x1="12" y1="9" x2="12" y2="13"></line>
                  <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
              {:else}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="17" height="17">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="16" x2="12" y2="12"></line>
                  <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
              {/if}
            </div>

            <div class="item-content">
              <div class="item-title-row">
                {#if !item.read}
                  <span class="unread-dot variant-{variant}" aria-hidden="true"></span>
                {/if}
                <span class="item-title" title={item.title}>{item.title}</span>
              </div>
              <p class="item-msg">{item.message}</p>
              <div class="item-meta">
                <span class="item-time">{item.time}</span>
                {#if item.actionView}
                  <span class="item-action-link">
                    เปิดดูรายละเอียด
                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="12" height="12">
                      <line x1="5" y1="12" x2="19" y2="12"></line>
                      <polyline points="12 5 19 12 12 19"></polyline>
                    </svg>
                  </span>
                {/if}
              </div>
            </div>
          </button>

          <button
            type="button"
            class="btn-remove-noti"
            on:click={() => removeNotification(item.id)}
            title="ลบรายการนี้"
            aria-label={`ลบการแจ้งเตือน ${item.title}`}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </li>
      {/each}
    </ul>
  {/if}

  <!-- Footer -->
  {#if $notifications.length > 0}
    <div class="noti-footer">
      {#if confirmClearAll}
        <div class="clear-confirm-row" role="alert">
          <span class="clear-confirm-text">ล้างทั้งหมด {$notifications.length} รายการ?</span>
          <div class="clear-confirm-actions">
            <button
              type="button"
              class="btn-confirm-cancel"
              on:click={() => (confirmClearAll = false)}
            >
              ยกเลิก
            </button>
            <button
              type="button"
              class="btn-confirm-danger"
              on:click={handleConfirmClearAll}
            >
              ยืนยันลบ
            </button>
          </div>
        </div>
      {:else}
        <button
          type="button"
          class="btn-clear-all"
          on:click={() => (confirmClearAll = true)}
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          ล้างรายการทั้งหมด
        </button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .noti-overlay {
    position: fixed;
    inset: 0;
    z-index: 9998;
    background: transparent;
  }

  .noti-panel {
    position: absolute;
    top: calc(100% + 12px);
    right: 0;
    width: 410px;
    max-width: calc(100vw - 24px);
    max-height: min(540px, calc(100dvh - 96px));
    background: var(--bg2);
    border: 1px solid rgba(168, 85, 247, 0.24);
    border-radius: var(--radius-lg);
    box-shadow:
      0 24px 60px rgba(0, 0, 0, 0.78),
      0 0 0 1px rgba(255, 255, 255, 0.04),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    outline: none;
  }

  /* Header */
  .noti-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 18px;
    border-bottom: 1px solid var(--glass-border);
    background: var(--bg);
    flex-shrink: 0;
  }

  .header-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .header-icon-box {
    width: 30px;
    height: 30px;
    border-radius: var(--radius-sm);
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.28);
    color: var(--secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .header-title-row h3 {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-main);
    margin: 0;
    font-family: var(--font-th);
    letter-spacing: 0.1px;
  }

  .unread-pill {
    font-size: 11px;
    font-weight: 600;
    background: rgba(244, 63, 94, 0.16);
    border: 1px solid rgba(244, 63, 94, 0.36);
    color: var(--danger-soft-text);
    padding: 2px 8px;
    border-radius: 999px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .btn-mark-all {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: var(--font-th);
    padding: 6px 10px;
    min-height: 32px;
    border-radius: var(--radius-sm);
    white-space: nowrap;
    transition: color 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
  }

  .btn-mark-all:hover {
    color: var(--text-main);
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.3);
  }

  /* Notification List */
  .noti-list {
    list-style: none;
    margin: 0;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .empty-noti {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 44px 24px;
    text-align: center;
    gap: 6px;
  }

  .empty-icon {
    width: 52px;
    height: 52px;
    border-radius: 16px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-dim);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 6px;
  }

  .empty-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-main);
    font-family: var(--font-th);
    margin: 0;
  }

  .empty-text {
    font-size: 12px;
    color: var(--text-dim);
    font-family: var(--font-th);
    margin: 0;
  }

  /* Notification Item */
  .noti-item {
    position: relative;
    display: flex;
    align-items: stretch;
    border-radius: var(--radius-md);
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
  }

  .noti-item:hover {
    background: var(--surface-card-hover);
    border-color: rgba(168, 85, 247, 0.32);
    transform: translateY(-1px);
  }

  .noti-item.unread {
    background: var(--surface-card-unread);
    border-color: rgba(99, 102, 241, 0.3);
  }

  .item-title-row {
    display: flex;
    align-items: flex-start;
    gap: 7px;
  }

  .unread-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--primary);
    flex-shrink: 0;
    margin-top: 6px;
  }

  .unread-dot.variant-error {
    background: var(--danger);
  }

  .unread-dot.variant-warning {
    background: var(--warning);
  }

  .unread-dot.variant-success {
    background: var(--success);
  }

  .noti-item-main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 6px 12px 14px;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    color: inherit;
    font-family: var(--font-th);
    border-radius: var(--radius-md);
  }

  .item-icon-wrapper {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 1px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: var(--primary-soft-text);
  }

  .item-icon-wrapper.variant-error {
    background: rgba(244, 63, 94, 0.14);
    border-color: rgba(244, 63, 94, 0.32);
    color: var(--danger-soft-text);
  }

  .item-icon-wrapper.variant-warning {
    background: rgba(245, 158, 11, 0.14);
    border-color: rgba(245, 158, 11, 0.32);
    color: var(--warning-soft-text);
  }

  .item-icon-wrapper.variant-success {
    background: rgba(16, 185, 129, 0.14);
    border-color: rgba(16, 185, 129, 0.32);
    color: var(--success-soft-text);
  }

  .item-content {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .item-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-main);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    word-break: break-word;
    font-family: var(--font-th);
  }

  .item-msg {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.45;
    margin: 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-family: var(--font-th);
  }

  .item-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-top: 2px;
    flex-wrap: wrap;
  }

  .item-time {
    font-size: 11px;
    color: var(--text-dim);
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }

  .item-action-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 11.5px;
    color: var(--primary-soft-text);
    font-weight: 500;
  }

  .noti-item:hover .item-action-link {
    color: var(--primary-soft-text-hover);
  }

  .btn-remove-noti {
    background: transparent;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    opacity: 0;
    min-width: 28px;
    min-height: 28px;
    margin: 8px 8px 0 0;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    align-self: flex-start;
    transition: opacity 0.2s ease, color 0.2s ease, background-color 0.2s ease;
  }

  .noti-item:hover .btn-remove-noti,
  .noti-item:focus-within .btn-remove-noti,
  .btn-remove-noti:focus-visible {
    opacity: 1;
  }

  .btn-remove-noti:hover {
    color: var(--danger-soft-text);
    background: rgba(244, 63, 94, 0.14);
  }

  /* Footer */
  .noti-footer {
    padding: 10px 16px;
    border-top: 1px solid var(--glass-border);
    display: flex;
    justify-content: center;
    align-items: center;
    background: var(--bg);
    flex-shrink: 0;
  }

  .btn-clear-all {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: 1px solid transparent;
    color: var(--danger-soft-text);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: var(--font-th);
    padding: 6px 12px;
    min-height: 32px;
    border-radius: var(--radius-sm);
    transition: color 0.2s ease, background-color 0.2s ease, border-color 0.2s ease;
  }

  .btn-clear-all:hover {
    color: var(--danger-soft-text-hover);
    background: rgba(244, 63, 94, 0.14);
    border-color: rgba(244, 63, 94, 0.3);
  }

  .clear-confirm-row {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .clear-confirm-text {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-main);
    font-family: var(--font-th);
  }

  .clear-confirm-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-confirm-cancel,
  .btn-confirm-danger {
    font-size: 12px;
    font-weight: 500;
    font-family: var(--font-th);
    padding: 5px 12px;
    min-height: 30px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
  }

  .btn-confirm-cancel {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border-light);
    color: var(--text-muted);
  }

  .btn-confirm-cancel:hover {
    color: var(--text-main);
    background: rgba(255, 255, 255, 0.1);
  }

  .btn-confirm-danger {
    background: var(--danger-solid);
    border: 1px solid var(--danger-solid);
    color: #ffffff;
  }

  .btn-confirm-danger:hover {
    background: var(--danger-solid-hover);
    border-color: var(--danger-solid-hover);
  }

  @media (prefers-reduced-motion: reduce) {
    .noti-item,
    .noti-item:hover {
      transform: none;
      transition: none;
    }
    .btn-mark-all,
    .btn-remove-noti,
    .btn-clear-all,
    .btn-confirm-cancel,
    .btn-confirm-danger {
      transition: none;
    }
  }

  @media (hover: none), (pointer: coarse) {
    .btn-remove-noti {
      opacity: 0.85;
      min-width: 44px;
      min-height: 44px;
      margin: 4px 4px 0 0;
    }
    .btn-mark-all,
    .btn-clear-all,
    .btn-confirm-cancel,
    .btn-confirm-danger {
      min-height: 40px;
    }
  }

  @media (max-width: 520px) {
    .noti-panel {
      position: fixed;
      top: 64px;
      right: 12px;
      left: 12px;
      width: auto;
      max-width: none;
      max-height: calc(100dvh - 80px);
    }
  }
</style>
