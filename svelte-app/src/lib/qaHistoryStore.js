import { writable, derived, get } from 'svelte/store';

export const qaHistory = writable([]);
export const selectedHistory = writable(null);
export const selectedProjectStore = writable(null);
export const qaSessionGroups = writable([]);
export const activeQAContext = writable(null);
export const activeSidebarGroup = writable(null);
export const qaDbGroups = writable([]);
export const activeScanStatus = writable(null);

/**
 * Derived store: unique groups from DB groups, DB history, and session groups
 */
export const allGroups = derived(
  [qaHistory, qaSessionGroups, qaDbGroups],
  ([$qaHistory, $qaSessionGroups, $qaDbGroups]) => {
    const groupMap = new Map();

    const cleanGroup = (name) => String(name || 'General').replace(/^\[.*?\]\s*/, '').trim();

    // From DB Groups (the master source of explicitly created groups)
    for (const g of $qaDbGroups) {
      const gName = cleanGroup(g.group_name);
      const pId = String(g.project_id || '');
      const key = `${pId}::${gName.toLowerCase()}`;
      groupMap.set(key, {
        group_id: g.group_id,
        group_name: gName,
        group_type: g.group_type || 'Project Plan',
        project_id: pId,
        project_code: g.project_code || '',
        latest_date: g.created_at,
        scan_count: 0
      });
    }

    // Helper to find existing group entry in map
    const findGroup = (pId, pCode, gName) => {
      const cleanG = cleanGroup(gName).toLowerCase();
      const directKey = `${pId}::${cleanG}`;
      if (groupMap.has(directKey)) return groupMap.get(directKey);

      // Try finding by project_code or matching name within project
      for (const item of groupMap.values()) {
        const itemClean = cleanGroup(item.group_name).toLowerCase();
        const nameMatch = itemClean === cleanG || itemClean.includes(cleanG) || cleanG.includes(itemClean);
        const projMatch = (!pId && !item.project_id) || (pId && item.project_id === pId) || (pCode && item.project_code === pCode);
        if (nameMatch && projMatch) return item;
      }
      return null;
    };

    // From DB history (to count scans and get implicitly created groups)
    for (const h of $qaHistory) {
      const hName = cleanGroup(h.group_name);
      const pId = String(h.project_id || '');
      const pCode = String(h.project_code || '');
      
      const existing = findGroup(pId, pCode, hName);
      if (existing) {
        existing.scan_count = (existing.scan_count || 0) + 1;
        if (h.date && (!existing.latest_date || new Date(h.date) > new Date(existing.latest_date))) {
          existing.latest_date = h.date;
        }
        if (!existing.project_code && pCode) existing.project_code = pCode;
        if (!existing.project_id && pId) existing.project_id = pId;
      } else {
        const key = `${pId}::${hName.toLowerCase()}`;
        groupMap.set(key, {
          group_name: hName,
          group_type: h.group_type || h.docType || 'Project Plan',
          project_id: pId,
          project_code: pCode || '',
          latest_date: h.date,
          scan_count: 1
        });
      }
    }

    // From session groups (newly created in this session)
    for (const g of $qaSessionGroups) {
      const gName = cleanGroup(g.group_name);
      const pId = String(g.project_id || '');
      const pCode = String(g.project_code || '');
      
      const existing = findGroup(pId, pCode, gName);
      if (!existing) {
        const key = `${pId}::${gName.toLowerCase()}`;
        groupMap.set(key, {
          group_name: gName,
          group_type: g.group_type || 'Project Plan',
          project_id: pId,
          project_code: pCode || '',
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
    const res = await fetch("/api/qa_transactions");
    if (res.ok) {
      const data = await res.json();
      if (data.success && data.transactions) {
        qaHistory.update(current => {
          // Preserve any in-progress pending items that haven't finished
          const inProgress = current.filter(item => item.is_processing);
          return [...inProgress, ...data.transactions];
        });
      }
    }
  } catch (err) {
    console.error("Failed to load QA history from DB", err);
  }
}

export async function loadQAGroupsFromDB() {
  try {
    const res = await fetch("/api/qa_groups");
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
