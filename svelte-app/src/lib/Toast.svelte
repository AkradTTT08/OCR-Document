<script>
  import { toasts, dismissToast } from './toastStore.js';

  const ICONS = {
    success: `<svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>`,
    error:   `<svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>`,
    warning: `<svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>`,
    info:    `<svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>`,
  };
</script>

<div class="toast-container">
  {#each $toasts as t (t.id)}
    <div class="toast toast-{t.type}" role="alert">
      <span class="toast-icon" class:success={t.type==='success'} class:error={t.type==='error'} class:warning={t.type==='warning'} class:info={t.type==='info'}>
        {@html ICONS[t.type] ?? ICONS.info}
      </span>
      <span class="toast-msg">{t.message}</span>
      <button class="toast-close" on:click={() => dismissToast(t.id)} aria-label="ปิด">
        <svg viewBox="0 0 16 16" fill="currentColor" width="12" height="12">
          <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z"/>
        </svg>
      </button>
    </div>
  {/each}
</div>

<style>
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 380px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 13px 14px;
  border-radius: 11px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid;
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  animation: slideIn 0.3s cubic-bezier(0.34,1.56,0.64,1);
  pointer-events: all;
  font-family: var(--font-th);
  font-size: 13.5px;
  line-height: 1.5;
  max-width: 380px;
}

@keyframes slideIn {
  from { transform: translateX(120%); opacity: 0; }
  to   { transform: translateX(0);    opacity: 1; }
}

.toast-success {
  background: rgba(20, 50, 38, 0.92);
  border-color: rgba(52, 211, 153, 0.35);
  color: #6ee7b7;
}
.toast-error {
  background: rgba(50, 20, 20, 0.92);
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}
.toast-warning {
  background: rgba(50, 40, 10, 0.92);
  border-color: rgba(251, 191, 36, 0.35);
  color: #fde68a;
}
.toast-info {
  background: rgba(15, 30, 55, 0.92);
  border-color: rgba(108, 142, 251, 0.35);
  color: #a5b4fc;
}

.toast-icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.toast-icon.success { color: #34d399; }
.toast-icon.error   { color: #f87171; }
.toast-icon.warning { color: #fbbf24; }
.toast-icon.info    { color: #6c8efb; }

.toast-msg {
  flex: 1;
  word-break: break-word;
  color: var(--text);
}

.toast-close {
  flex-shrink: 0;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text3);
  padding: 2px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
  margin-top: 1px;
}
.toast-close:hover { color: var(--text); }
</style>
