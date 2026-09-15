import { writable, derived } from 'svelte/store';

const initialNotifications = [
  {
    id: 1,
    title: 'Master Agent MCP Ready 🤖',
    message: 'Master Agent พร้อมเชื่อมต่อกับ QA Tools ทุกโมดูลผ่าน MCP Server',
    type: 'info',
    time: 'เมื่อสักครู่',
    read: false,
    actionView: 'master_agent',
    icon: '🤖'
  },
  {
    id: 2,
    title: 'Exit Criteria Standard Updated ✅',
    message: 'อัปเดตเกณฑ์การตรวจรับเอกสารสากล 13 ข้อ พร้อมระบบ Quality Gate Decision',
    type: 'success',
    time: '10 นาทีที่แล้ว',
    read: false,
    actionView: 'exit_criteria',
    icon: '✅'
  },
  {
    id: 3,
    title: 'Security Scanner Ready 🛡️',
    message: 'ระบบพร้อมทำการสแกนช่องโหว่ซอร์สโค้ดตามมาตรฐาน OWASP Top 10 & ASVS',
    type: 'warning',
    time: '1 ชั่วโมงที่แล้ว',
    read: false,
    actionView: 'qa_security',
    icon: '🛡️'
  },
  {
    id: 4,
    title: 'System Backend Connected ⚡',
    message: 'เชื่อมต่อ Spectra QA Backend (Flask API) สมบูรณ์ พร้อมใช้งานทุกฟีเจอร์',
    type: 'success',
    time: '2 ชั่วโมงที่แล้ว',
    read: true,
    actionView: 'ocr',
    icon: '⚡'
  }
];

export const notifications = writable(initialNotifications);

export const unreadCount = derived(notifications, $notifications => {
  return $notifications.filter(n => !n.read).length;
});

export function markAsRead(id) {
  notifications.update(items => 
    items.map(n => n.id === id ? { ...n, read: true } : n)
  );
}

export function markAllAsRead() {
  notifications.update(items => 
    items.map(n => ({ ...n, read: true }))
  );
}

export function removeNotification(id) {
  notifications.update(items => items.filter(n => n.id !== id));
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
  notifications.update(items => [newNoti, ...items]);
}
