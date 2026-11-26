import { writable } from 'svelte/store';

let _id = 0;

export const toasts = writable([]);

/**
 * Show a toast notification
 * @param {string} message
 * @param {'success'|'error'|'warning'|'info'} type
 * @param {number} duration ms before auto-dismiss (0 = manual)
 */
const MAX_VISIBLE_TOASTS = 3;

export function toast(message, type = 'info', duration = 4000) {
  const id = ++_id;
  toasts.update(ts => {
    const next = [...ts, { id, message, type }];
    return next.length > MAX_VISIBLE_TOASTS ? next.slice(-MAX_VISIBLE_TOASTS) : next;
  });
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration);
  }
  return id;
}

export function dismissToast(id) {
  toasts.update(ts => ts.filter(t => t.id !== id));
}

export const showToast = toast;

/**
 * Global confirm modal state
 * @type {import('svelte/store').Writable<{
 *   open: boolean,
 *   title: string,
 *   message: string,
 *   detail: string,
 *   confirmText: string,
 *   cancelText: string,
 *   variant: 'danger' | 'warning' | 'primary'
 * } | null>}
 */
export const confirmDialog = writable(null);

let _confirmResolver = null;

/**
 * Show a themed Spectra QA confirmation modal instead of native window.confirm()
 * @param {string} message
 * @param {{
 *   title?: string,
 *   detail?: string,
 *   confirmText?: string,
 *   cancelText?: string,
 *   variant?: 'danger' | 'warning' | 'primary',
 *   danger?: boolean
 * }} [options]
 * @returns {Promise<boolean>}
 */
export function customConfirm(message, options = {}) {
  if (_confirmResolver) {
    _confirmResolver(false);
    _confirmResolver = null;
  }

  const inferredVariant =
    options.variant ||
    (options.danger === false ? 'warning' : 'danger');

  return new Promise((resolve) => {
    _confirmResolver = resolve;
    confirmDialog.set({
      open: true,
      title: options.title || 'ยืนยันการดำเนินการ',
      message: message || '',
      detail: options.detail || '',
      confirmText: options.confirmText || 'ยืนยัน',
      cancelText: options.cancelText || 'ยกเลิก',
      variant: inferredVariant
    });
  });
}

/**
 * Resolve the active global confirm modal
 * @param {boolean} accepted
 */
export function resolveConfirmDialog(accepted) {
  confirmDialog.set(null);
  if (_confirmResolver) {
    const fn = _confirmResolver;
    _confirmResolver = null;
    fn(Boolean(accepted));
  }
}
