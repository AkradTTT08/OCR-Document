import { writable } from 'svelte/store';

export const qaHistory = writable([]);
export const selectedHistory = writable(null);
export const selectedProjectStore = writable(null);
export const qaSessionGroups = writable([]);
export const activeQAContext = writable(null);

export async function loadQAHistoryFromDB() {
  try {
    const res = await fetch("http://127.0.0.1:5000/api/qa_transactions");
    if (res.ok) {
      const data = await res.json();
      if (data.success && data.transactions) {
        qaHistory.set(data.transactions);
      }
    }
  } catch (err) {
    console.error("Failed to load QA history from DB", err);
  }
}
