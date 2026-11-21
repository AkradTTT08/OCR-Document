<script>
  import { createEventDispatcher } from 'svelte';
  import { fade, scale } from 'svelte/transition';

  export let open = false;
  export let title = 'ยืนยันการดำเนินการ';
  export let message = '';
  export let confirmText = 'ยืนยัน';
  export let cancelText = 'ยกเลิก';
  export let danger = true;

  const dispatch = createEventDispatcher();
  const titleId = `cm-title-${Math.random().toString(36).slice(2, 9)}`;

  function handleConfirm() {
    open = false;
    dispatch('confirm');
  }

  function handleCancel() {
    open = false;
    dispatch('cancel');
  }

  function handleKeydown(e) {
    if (open && e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div class="cm-backdrop" transition:fade={{ duration: 150 }} on:click|self={handleCancel} role="presentation">
    <div
      class="cm-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      in:scale={{ start: 0.94, duration: 180 }}
    >
      <div class="cm-header">
        <div class="cm-icon" class:cm-icon-danger={danger} class:cm-icon-warn={!danger} aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>
        <h3 id={titleId} class="cm-title">{title}</h3>
      </div>

      {#if message}
        <p class="cm-message">{message}</p>
      {/if}

      <div class="cm-actions">
        <button type="button" class="cm-btn-cancel" on:click={handleCancel}>{cancelText}</button>
        <button
          type="button"
          class="cm-btn-confirm"
          class:cm-btn-danger={danger}
          class:cm-btn-warn={!danger}
          on:click={handleConfirm}
        >
          {confirmText}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .cm-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(5, 5, 5, 0.78);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: calc(var(--z-modal, 10000) + 200);
    padding: 16px;
  }

  .cm-dialog {
    width: 100%;
    max-width: 440px;
    max-height: 90vh;
    overflow-y: auto;
    background: var(--bg, #0a0b12);
    border: 1px solid var(--glass-border-light, rgba(255, 255, 255, 0.15));
    border-radius: var(--radius-lg, 20px);
    padding: 24px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
    color: var(--text-main, #f8fafc);
  }

  .cm-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .cm-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .cm-icon-danger {
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.35);
    color: var(--danger, #f43f5e);
  }

  .cm-icon-warn {
    background: rgba(245, 158, 11, 0.14);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: var(--warning, #f59e0b);
  }

  .cm-title {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 17px;
    font-weight: 600;
    color: var(--text-main, #f8fafc);
    margin: 0;
  }

  .cm-message {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-muted, #94a3b8);
    margin: 0 0 22px;
    white-space: pre-line;
  }

  .cm-actions {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 10px;
  }

  .cm-btn-cancel {
    min-height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    color: var(--text-main, #f8fafc);
    padding: 8px 18px;
    border-radius: var(--radius-md, 12px);
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s ease;
  }
  .cm-btn-cancel:hover {
    background: rgba(255, 255, 255, 0.1);
  }

  .cm-btn-confirm {
    min-height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid transparent;
    color: #ffffff;
    padding: 8px 20px;
    border-radius: var(--radius-md, 12px);
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13.5px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s ease, transform 0.2s ease;
  }
  .cm-btn-danger {
    background: var(--danger, #f43f5e);
  }
  .cm-btn-warn {
    background: var(--warning, #f59e0b);
    color: #0a0b12;
    font-weight: 600;
  }
  .cm-btn-confirm:hover {
    opacity: 0.92;
    transform: translateY(-1px);
  }
</style>

