import { writable, derived, get } from 'svelte/store';

export const qaHistory = writable([]);
export const selectedHistory = writable(null);
export const selectedProjectStore = writable(null);
export const qaSessionGroups = writable([]);
export const activeQAContext = writable(null);
export const activeSidebarGroup = writable(null);
export const qaDbGroups = writable([]);

/**
 * Derived store: unique groups from DB groups, DB history, and session groups
 */
export const allGroups = derived(
  [qaHistory, qaSessionGroups, qaDbGroups],
  ([$qaHistory, $qaSessionGroups, $qaDbGroups]) => {
    const groupMap = new Map();

    // From DB Groups (the master source of explicitly created groups)
    for (const g of $qaDbGroups) {
      const key = `${g.project_id}::${g.group_name}`;
      groupMap.set(key, {
        group_id: g.group_id,
        group_name: g.group_name,
        group_type: g.group_type,
        project_id: g.project_id,
        project_code: g.project_code || 'Unknown',
        latest_date: g.created_at,
        scan_count: 0
      });
    }

    // From DB history (to count scans and get implicitly created groups)
    for (const h of $qaHistory) {
      const key = `${h.project_id}::${h.group_name}`;
      if (!groupMap.has(key)) {
        groupMap.set(key, {
          group_name: h.group_name || 'General',
          group_type: h.group_type || 'Project Plan',
          project_id: h.project_id,
          project_code: h.project_code || 'Unknown',
          latest_date: h.date,
          scan_count: 1
        });
      } else {
        groupMap.get(key).scan_count++;
      }
    }

    // From session groups (newly created in this session)
    for (const g of $qaSessionGroups) {
      const key = `${g.project_id}::${g.group_name}`;
      if (!groupMap.has(key)) {
        groupMap.set(key, {
          group_name: g.group_name,
          group_type: g.group_type || 'Project Plan',
          project_id: g.project_id,
          project_code: g.project_code || '',
          latest_date: null,
          scan_count: 0
        });
      }
    }

    return Array.from(groupMap.values());
  }
);

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

export async function loadQAGroupsFromDB() {
  try {
    const res = await fetch("http://127.0.0.1:5000/api/qa_groups");
    if (res.ok) {
      const data = await res.json();
      if (data.success && data.groups) {
        qaDbGroups.set(data.groups);
      }
    }
  } catch (err) {
    console.error("Failed to load QA groups from DB", err);
  }
}
