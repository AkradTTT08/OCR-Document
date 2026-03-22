import { writable } from 'svelte/store';

let _id = 0;

export const toasts = writable([]);

/**
 * Show a toast notification
 * @param {string} message
 * @param {'success'|'error'|'warning'|'info'} type
 * @param {number} duration ms before auto-dismiss (0 = manual)
 */
export function toast(message, type = 'info', duration = 4000) {
  const id = ++_id;
  toasts.update(ts => [...ts, { id, message, type }]);
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration);
  }
  return id;
}

export function dismissToast(id) {
  toasts.update(ts => ts.filter(t => t.id !== id));
}
