<script>
  import { createEventDispatcher } from 'svelte';
  import { fade, fly, slide } from 'svelte/transition';
  import { 
    notifications, 
    unreadCount, 
    markAsRead, 
    markAllAsRead, 
    removeNotification, 
    clearAllNotifications 
  } from './notificationStore.js';

  const dispatch = createEventDispatcher();

  function handleNotiClick(noti) {
    markAsRead(noti.id);
    if (noti.actionView) {
      dispatch('navigate', { view: noti.actionView });
    }
  }
</script>

<!-- Backdrop overlay to dismiss when clicking outside -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="noti-overlay" on:click|stopPropagation={() => dispatch('close')}></div>

<!-- Main Notification Popup Container -->
<div class="noti-panel glass-panel" in:fly={{ y: -10, duration: 220 }} out:fade={{ duration: 150 }}>
  <!-- Header -->
  <div class="noti-header">
    <div class="header-title-row">
      <div class="header-icon-box">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
          <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 01-3.46 0"></path>
        </svg>
      </div>
      <h3>การแจ้งเตือน</h3>
      {#if $unreadCount > 0}
        <span class="unread-pill">{$unreadCount} ใหม่</span>
      {/if}
    </div>

    {#if $notifications.length > 0}
      <button class="btn-mark-all" on:click={markAllAsRead} title="ทำเครื่องหมายว่าอ่านแล้วทั้งหมด">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        อ่านทั้งหมด
      </button>
    {/if}
  </div>

  <!-- Notification List -->
  <div class="noti-list">
    {#if $notifications.length === 0}
      <div class="empty-noti">
        <div class="empty-icon">🔕</div>
        <p class="empty-text">ไม่มีรายการแจ้งเตือนในขณะนี้</p>
      </div>
    {:else}
      {#each $notifications as item (item.id)}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <div 
          class="noti-item {item.type}" 
          class:unread={!item.read}
          on:click={() => handleNotiClick(item)}
          transition:slide={{ duration: 180 }}
        >
          <div class="item-icon-wrapper {item.type}">
            <span>{item.icon || '🔔'}</span>
          </div>

          <div class="item-content">
            <div class="item-top">
              <span class="item-title">{item.title}</span>
              <span class="item-time">{item.time}</span>
            </div>
            <p class="item-msg">{item.message}</p>
            {#if item.actionView}
              <span class="item-action-link">คลิกเพื่อไปที่เมนู →</span>
            {/if}
          </div>

          <button 
            class="btn-remove-noti" 
            on:click|stopPropagation={() => removeNotification(item.id)}
            title="ลบรายการนี้"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      {/each}
    {/if}
  </div>

  <!-- Footer -->
  {#if $notifications.length > 0}
    <div class="noti-footer">
      <button class="btn-clear-all" on:click={clearAllNotifications}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
        ล้างรายการทั้งหมด
      </button>
    </div>
  {/if}
</div>

<style>
  .noti-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 100;
  }

  .noti-panel {
    position: absolute;
    top: calc(100% + 12px);
    right: 0;
    width: 380px;
    max-height: 520px;
    background: rgba(16, 18, 30, 0.95);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(168, 85, 247, 0.25);
    border-radius: 20px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), 0 0 20px rgba(168, 85, 247, 0.15);
    z-index: 101;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* Header */
  .noti-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.02);
  }

  .header-title-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .header-icon-box {
    color: var(--secondary);
    display: flex;
    align-items: center;
  }

  .header-title-row h3 {
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    margin: 0;
    font-family: var(--font-th);
  }

  .unread-pill {
    font-size: 11px;
    font-weight: 700;
    background: rgba(244, 63, 94, 0.2);
    border: 1px solid rgba(244, 63, 94, 0.4);
    color: #f43f5e;
    padding: 2px 8px;
    border-radius: 12px;
  }

  .btn-mark-all {
    display: flex;
    align-items: center;
    gap: 4px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    font-family: var(--font-th);
    transition: color 0.2s;
  }

  .btn-mark-all:hover {
    color: var(--primary);
  }

  /* Notification List */
  .noti-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .empty-noti {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    color: var(--text-dim);
  }

  .empty-icon { font-size: 32px; margin-bottom: 8px; }
  .empty-text { font-size: 13px; font-family: var(--font-th); margin: 0; }

  /* Notification Item */
  .noti-item {
    display: flex;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.05);
    cursor: pointer;
    position: relative;
    transition: all 0.2s ease;
  }

  .noti-item:hover {
    background: rgba(168, 85, 247, 0.1);
    border-color: rgba(168, 85, 247, 0.25);
    transform: translateY(-1px);
  }

  .noti-item.unread {
    background: rgba(99, 102, 241, 0.08);
    border-color: rgba(99, 102, 241, 0.2);
  }

  .noti-item.unread::before {
    content: '';
    position: absolute;
    top: 14px;
    left: 6px;
    width: 6px;
    height: 6px;
    background: #f43f5e;
    border-radius: 50%;
    box-shadow: 0 0 8px #f43f5e;
  }

  .item-icon-wrapper {
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.05);
  }

  .item-content {
    flex: 1;
    min-width: 0;
  }

  .item-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 2px;
  }

  .item-title {
    font-size: 13px;
    font-weight: 600;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: var(--font-th);
  }

  .item-time {
    font-size: 10px;
    color: var(--text-dim);
    flex-shrink: 0;
  }

  .item-msg {
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.4;
    margin: 0 0 4px 0;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-family: var(--font-th);
  }

  .item-action-link {
    font-size: 11px;
    color: #818cf8;
    font-weight: 500;
  }

  .btn-remove-noti {
    background: transparent;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    opacity: 0;
    padding: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    align-self: flex-start;
  }

  .noti-item:hover .btn-remove-noti {
    opacity: 1;
  }

  .btn-remove-noti:hover {
    color: #f43f5e;
  }

  /* Footer */
  .noti-footer {
    padding: 12px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: center;
    background: rgba(0, 0, 0, 0.2);
  }

  .btn-clear-all {
    display: flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: none;
    color: var(--danger);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: var(--font-th);
    transition: opacity 0.2s;
  }

  .btn-clear-all:hover {
    opacity: 0.8;
  }
</style>
