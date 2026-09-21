import { writable, derived } from 'svelte/store';

const STORAGE_KEY = 'spectra_notifications';

// โหลดรายการแจ้งเตือนจาก LocalStorage (เริ่มต้นเป็น [] ถ้าไม่มีข้อมูล)
function loadNotifications() {
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (e) {
      console.error('Failed to load notifications from localStorage:', e);
    }
  }
  return [];
}

export const notifications = writable(loadNotifications());

// ซิงก์การเปลี่ยนแปลงไปยัง LocalStorage โดยอัตโนมัติ
if (typeof window !== 'undefined' && window.localStorage) {
  notifications.subscribe(items => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.error('Failed to save notifications to localStorage:', e);
    }
  });
}

export const unreadCount = derived(notifications, $notifications => {
  return Array.isArray($notifications) ? $notifications.filter(n => !n.read).length : 0;
});

export function markAsRead(id) {
  notifications.update(items => 
    (items || []).map(n => n.id === id ? { ...n, read: true } : n)
  );
}

export function markAllAsRead() {
  notifications.update(items => 
    (items || []).map(n => ({ ...n, read: true }))
  );
}

export function removeNotification(id) {
  notifications.update(items => (items || []).filter(n => n.id !== id));
}

export function clearAllNotifications() {
  notifications.set([]);
}

export function addNotification({ title, message, type = 'info', actionView = null, icon = '🔔' }) {
  const newNoti = {
    id: Date.now(),
    title,
    message,
    type,
    time: 'เมื่อสักครู่',
    read: false,
    actionView,
    icon
  };
  notifications.update(items => [newNoti, ...(items || [])]);
}
