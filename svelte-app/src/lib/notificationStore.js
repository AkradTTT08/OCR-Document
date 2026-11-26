import { writable, derived } from 'svelte/store';
import { toast } from './toastStore.js';

const STORAGE_KEY = 'spectra_notifications';

// Load fallback notifications from localStorage
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

// Sync notifications to localStorage as backup
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

// Set of already-seen notification IDs to avoid alerting repeatedly
const seenNotificationIds = new Set();
let isInitialFetch = true;
let syncedUsername = '';
let syncInterval = null;
let isFetching = false;
let visibilityListener = null;

function getAuthHeaders() {
  const headers = {};
  if (typeof window !== 'undefined' && window.localStorage) {
    const token = localStorage.getItem('jwt_token');
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

function getCurrentUsername() {
  if (typeof window !== 'undefined' && window.localStorage) {
    return localStorage.getItem('auth_user') || '';
  }
  return '';
}

/**
 * Fetch notifications from backend specifically for the currently logged in user
 */
export async function fetchUserNotifications() {
  const username = getCurrentUsername();
  if (!username) {
    if (syncedUsername) {
      syncedUsername = '';
      isInitialFetch = true;
      seenNotificationIds.clear();
      notifications.set([]);
    }
    return;
  }
  if (isFetching) return;

  // Reset initial-fetch baseline whenever a user logs in or switches accounts
  // so historical unread notifications populate the bell badge silently without flooding toasts
  if (username !== syncedUsername) {
    syncedUsername = username;
    isInitialFetch = true;
    seenNotificationIds.clear();
  }

  isFetching = true;
  try {
    const res = await fetch(`/api/user/notifications?username=${encodeURIComponent(username)}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) return;

    const data = await res.json();
    if (data.success && Array.isArray(data.notifications)) {
      // Guard against account switch while request was in flight
      if (getCurrentUsername() !== username) return;

      const incoming = data.notifications;

      // Only toast genuinely new notifications arriving after the initial login sync
      if (!isInitialFetch) {
        const newlyArrived = incoming.filter(
          item => !item.read && !seenNotificationIds.has(item.id)
        );
        if (newlyArrived.length > 2) {
          const hasError = newlyArrived.some(n => n.type === 'error');
          const hasWarn = newlyArrived.some(n => n.type === 'warning');
          const summaryType = hasError ? 'error' : hasWarn ? 'warning' : 'info';
          toast(
            `มีการแจ้งเตือนใหม่ ${newlyArrived.length} รายการ (ดูรายละเอียดที่ไอคอนกระดิ่ง)`,
            summaryType,
            5000
          );
        } else {
          for (const item of newlyArrived) {
            const toastType = item.type === 'error' ? 'error' : item.type === 'warning' ? 'warning' : 'success';
            toast(`${item.title}: ${item.message}`, toastType, 6000);
          }
        }
      }

      // Record seen IDs
      incoming.forEach(n => seenNotificationIds.add(n.id));
      isInitialFetch = false;

      // Update store
      notifications.set(incoming);
    }
  } catch (err) {
    console.debug('Failed to sync user notifications:', err);
  } finally {
    isFetching = false;
  }
}

/**
 * Start background polling for user notifications (pauses when tab is hidden)
 */
export function startNotificationSync(intervalMs = 6000) {
  stopNotificationSync();
  fetchUserNotifications();
  syncInterval = setInterval(() => {
    if (typeof document !== 'undefined' && document.hidden) return;
    fetchUserNotifications();
  }, intervalMs);

  if (typeof document !== 'undefined') {
    visibilityListener = () => {
      if (!document.hidden) {
        fetchUserNotifications();
      }
    };
    document.addEventListener('visibilitychange', visibilityListener);
  }
}

export function stopNotificationSync() {
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }
  if (visibilityListener && typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', visibilityListener);
    visibilityListener = null;
  }
  syncedUsername = '';
  isInitialFetch = true;
  seenNotificationIds.clear();
}

export async function markAsRead(id) {
  notifications.update(items => 
    (items || []).map(n => n.id === id ? { ...n, read: true } : n)
  );

  try {
    const username = getCurrentUsername();
    await fetch('/api/user/notifications/mark_read', {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, username })
    });
  } catch (e) {
    console.error('Failed to mark notification read on backend:', e);
  }
}

export async function markAllAsRead() {
  notifications.update(items => 
    (items || []).map(n => ({ ...n, read: true }))
  );

  try {
    const username = getCurrentUsername();
    await fetch('/api/user/notifications/mark_read', {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    });
  } catch (e) {
    console.error('Failed to mark all notifications read on backend:', e);
  }
}

export async function removeNotification(id) {
  notifications.update(items => (items || []).filter(n => n.id !== id));

  try {
    const username = getCurrentUsername();
    await fetch(`/api/user/notifications/${id}?username=${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
  } catch (e) {
    console.error('Failed to delete notification on backend:', e);
  }
}

export async function clearAllNotifications() {
  notifications.set([]);

  try {
    const username = getCurrentUsername();
    await fetch(`/api/user/notifications/clear?username=${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers: getAuthHeaders()
    });
  } catch (e) {
    console.error('Failed to clear notifications on backend:', e);
  }
}

export function addNotification({ title, message, type = 'info', actionView = null, actionPayload = {}, icon = '🔔' }) {
  const newNoti = {
    id: Date.now(),
    title,
    message,
    type,
    time: 'เมื่อสักครู่',
    read: false,
    actionView,
    actionPayload,
    icon
  };
  notifications.update(items => [newNoti, ...(items || [])]);
  seenNotificationIds.add(newNoti.id);
  const toastType = type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'success';
  toast(`${title}: ${message}`, toastType, 6000);
}
