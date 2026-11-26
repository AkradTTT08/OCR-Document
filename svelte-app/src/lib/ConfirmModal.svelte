<script>
  import { createEventDispatcher } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';

  export let open = false;
  export let title = 'ยืนยันการดำเนินการ';
  export let message = '';
  export let detail = '';
  export let confirmText = 'ยืนยัน';
  export let cancelText = 'ยกเลิก';
  export let danger = true;
  /** @type {'danger' | 'warning' | 'primary' | null} */
  export let variant = null;

  const dispatch = createEventDispatcher();
  const uid = Math.random().toString(36).slice(2, 9);
  const titleId = `cm-title-${uid}`;
  const descId = `cm-desc-${uid}`;

  $: resolvedVariant = variant || (danger ? 'danger' : 'warning');

  function prefersReducedMotion() {
    return (
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
  }

  function trapFocus(node) {
    const previouslyFocused = document.activeElement;
    const selector = 'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const timer = setTimeout(() => {
      const cancelBtn = node.querySelector('.cm-btn-cancel');
      if (cancelBtn && typeof /** @type {HTMLElement} */ (cancelBtn).focus === 'function') {
        /** @type {HTMLElement} */ (cancelBtn).focus();
        return;
      }
      const items = node.querySelectorAll(selector);
      if (items.length > 0) /** @type {HTMLElement} */ (items[0]).focus();
    }, 20);

    function onKeydown(e) {
      if (e.key !== 'Tab') return;
      const items = Array.from(node.querySelectorAll(selector));
      if (items.length === 0) return;
      const first = /** @type {HTMLElement} */ (items[0]);
      const last = /** @type {HTMLElement} */ (items[items.length - 1]);
      if (e.shiftKey) {
        if (document.activeElement === first || !node.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else if (document.activeElement === last || !node.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      }
    }

    node.addEventListener('keydown', onKeydown);
    return {
      destroy() {
        clearTimeout(timer);
        node.removeEventListener('keydown', onKeydown);
        if (previouslyFocused && typeof /** @type {HTMLElement} */ (previouslyFocused).focus === 'function') {
          /** @type {HTMLElement} */ (previouslyFocused).focus();
        }
      }
    };
  }

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
  <div
    class="cm-backdrop"
    transition:fade={{ duration: prefersReducedMotion() ? 0 : 150, easing: cubicOut }}
    on:click|self={handleCancel}
    role="presentation"
  >
    <div
      class="cm-dialog cm-variant-{resolvedVariant}"
      use:trapFocus
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={message ? descId : undefined}
      in:scale={{ start: 0.96, duration: prefersReducedMotion() ? 0 : 170, easing: cubicOut }}
      out:fade={{ duration: prefersReducedMotion() ? 0 : 110 }}
    >
      <div class="cm-accent-line" aria-hidden="true"></div>

      <div class="cm-body">
        <div class="cm-header">
          <div class="cm-icon cm-icon-{resolvedVariant}" aria-hidden="true">
            {#if resolvedVariant === 'primary'}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
              </svg>
            {:else if resolvedVariant === 'warning'}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20">
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            {:else}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="20" height="20">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
            {/if}
          </div>

          <h3 id={titleId} class="cm-title">{title}</h3>

          <button
            type="button"
            class="cm-close"
            on:click={handleCancel}
            aria-label="ปิดหน้าต่าง"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" width="16" height="16" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        {#if message}
          <p id={descId} class="cm-message">{message}</p>
        {/if}

        {#if detail}
          <div class="cm-detail">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
            <span>{detail}</span>
          </div>
        {/if}
      </div>

      <div class="cm-actions">
        <button type="button" class="cm-btn-cancel" on:click={handleCancel}>{cancelText}</button>
        <button
          type="button"
          class="cm-btn-confirm cm-btn-{resolvedVariant}"
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
    background: rgba(5, 6, 12, 0.78);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: calc(var(--z-modal, 10000) + 200);
    padding: 16px;
  }

  .cm-dialog {
    position: relative;
    width: 100%;
    max-width: 448px;
    max-height: 90vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    background: linear-gradient(180deg, #141724 0%, #0e101a 100%);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 18px;
    box-shadow:
      0 24px 64px -12px rgba(0, 0, 0, 0.78),
      0 0 0 1px rgba(255, 255, 255, 0.04) inset,
      0 1px 0 rgba(255, 255, 255, 0.08) inset;
    color: var(--text-main, #f8fafc);
  }

  .cm-accent-line {
    height: 2px;
    width: 100%;
    flex-shrink: 0;
  }

  .cm-variant-danger .cm-accent-line {
    background: linear-gradient(90deg, rgba(244, 63, 94, 0.1), #f43f5e 50%, rgba(244, 63, 94, 0.1));
  }

  .cm-variant-warning .cm-accent-line {
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.1), #f59e0b 50%, rgba(245, 158, 11, 0.1));
  }

  .cm-variant-primary .cm-accent-line {
    background: linear-gradient(90deg, rgba(99, 102, 241, 0.12), #6366f1 45%, #06b6d4 75%, rgba(6, 182, 212, 0.1));
  }

  .cm-body {
    padding: 22px 24px 20px;
    overflow-y: auto;
  }

  .cm-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
  }

  .cm-icon {
    width: 40px;
    height: 40px;
    border-radius: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .cm-icon-danger {
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.28);
    color: #fb7185;
  }

  .cm-icon-warning {
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.3);
    color: #fbbf24;
  }

  .cm-icon-primary {
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: #818cf8;
  }

  .cm-title {
    flex: 1;
    min-width: 0;
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 16.5px;
    font-weight: 600;
    line-height: 1.35;
    color: #f8fafc;
    margin: 0;
  }

  .cm-close {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    border: 1px solid transparent;
    background: transparent;
    color: #94a3b8;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
  }

  .cm-close:hover {
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(255, 255, 255, 0.1);
    color: #f8fafc;
  }

  .cm-close:focus-visible {
    outline: 2px solid #818cf8;
    outline-offset: 2px;
  }

  .cm-message {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 14px;
    line-height: 1.65;
    color: #cbd5e1;
    margin: 0;
    white-space: pre-line;
  }

  .cm-detail {
    margin-top: 14px;
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 12.5px;
    line-height: 1.45;
    color: #94a3b8;
  }

  .cm-detail svg {
    flex-shrink: 0;
    color: #64748b;
  }

  .cm-actions {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 14px 24px 18px;
    background: rgba(5, 6, 12, 0.35);
    border-top: 1px solid rgba(255, 255, 255, 0.07);
  }

  .cm-btn-cancel {
    min-height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.045);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #e2e8f0;
    padding: 8px 18px;
    border-radius: 10px;
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
  }

  .cm-btn-cancel:hover {
    background: rgba(255, 255, 255, 0.09);
    border-color: rgba(255, 255, 255, 0.2);
    color: #ffffff;
  }

  .cm-btn-cancel:focus-visible {
    outline: 2px solid #818cf8;
    outline-offset: 2px;
  }

  .cm-btn-confirm {
    min-height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid transparent;
    padding: 8px 20px;
    border-radius: 10px;
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 13.5px;
    font-weight: 600;
    cursor: pointer;
    transition: filter 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease;
  }

  .cm-btn-danger {
    background: #e11d48;
    border-color: rgba(251, 113, 133, 0.35);
    color: #ffffff;
    box-shadow: 0 4px 14px -2px rgba(225, 29, 72, 0.42);
  }

  .cm-btn-warning {
    background: #f59e0b;
    border-color: rgba(253, 224, 71, 0.35);
    color: #0b0d14;
    box-shadow: 0 4px 14px -2px rgba(245, 158, 11, 0.35);
  }

  .cm-btn-primary {
    background: #6366f1;
    border-color: rgba(165, 180, 252, 0.35);
    color: #ffffff;
    box-shadow: 0 4px 14px -2px rgba(99, 102, 241, 0.42);
  }

  .cm-btn-confirm:hover {
    filter: brightness(1.08);
    transform: translateY(-1px);
  }

  .cm-btn-confirm:active {
    transform: translateY(0);
  }

  .cm-btn-confirm:focus-visible {
    outline: 2px solid #f8fafc;
    outline-offset: 2px;
  }

  @media (max-width: 480px) {
    .cm-body {
      padding: 18px 18px 16px;
    }
    .cm-actions {
      padding: 12px 18px 16px;
    }
    .cm-btn-cancel,
    .cm-btn-confirm {
      flex: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .cm-close,
    .cm-btn-cancel,
    .cm-btn-confirm {
      transition: none;
    }
    .cm-btn-confirm:hover {
      transform: none;
    }
  }
</style>
