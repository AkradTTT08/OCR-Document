import { writable, derived, get } from 'svelte/store';

/** @type {import('svelte/store').Writable<any[]>} */
export const qaHistory = writable([]);
/** @type {import('svelte/store').Writable<any>} */
export const selectedHistory = writable(null);
/** @type {import('svelte/store').Writable<any>} */
export const selectedProjectStore = writable(null);
/** @type {import('svelte/store').Writable<any[]>} */
export const qaSessionGroups = writable([]);
/** @type {import('svelte/store').Writable<any>} */
export const activeQAContext = writable(null);
/** @type {import('svelte/store').Writable<any>} */
export const activeSidebarGroup = writable(null);
/** @type {import('svelte/store').Writable<any[]>} */
export const qaDbGroups = writable([]);
/** @type {import('svelte/store').Writable<any>} */
export const activeScanStatus = writable(null);
/** @type {import('svelte/store').Writable<any>} */
export const qaRefinementFeedback = writable(null);

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
      let pId = String(g.project_id || '');
      if (pId.toLowerCase() === 'none' || pId.toLowerCase() === 'null') pId = '';
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
      const normPid = (pId && pId.toLowerCase() !== 'none' && pId.toLowerCase() !== 'null') ? String(pId) : '';
      const normPCode = pCode ? String(pCode).trim().toLowerCase() : '';

      // Direct match
      if (normPid) {
        const directKey = `${normPid}::${cleanG}`;
        if (groupMap.has(directKey)) return groupMap.get(directKey);
      }

      // Match by group name and project code / ID
      for (const item of groupMap.values()) {
        const itemClean = cleanGroup(item.group_name).toLowerCase();
        const nameMatch = itemClean === cleanG || itemClean.includes(cleanG) || cleanG.includes(itemClean);
        if (!nameMatch) continue;

        const itemPid = String(item.project_id || '');
        const itemPCode = String(item.project_code || '').trim().toLowerCase();

        const projMatch = !normPid || !itemPid || itemPid === normPid || (normPCode && itemPCode && itemPCode === normPCode);
        if (projMatch) return item;
      }
      return null;
    };

    // From DB history (to count scans and get implicitly created groups)
    for (const h of $qaHistory) {
      const hName = cleanGroup(h.group_name);
      let pId = String(h.project_id || '');
      if (pId.toLowerCase() === 'none' || pId.toLowerCase() === 'null') pId = '';
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
      let pId = String(g.project_id || '');
      if (pId.toLowerCase() === 'none' || pId.toLowerCase() === 'null') pId = '';
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
          // Preserve any in-progress pending items
          const inProgress = current.filter(item => item.is_processing);
          // Preserve any newly completed items in current that aren't yet in DB response
          const dbIds = new Set(data.transactions.map(t => String(t.id)));
          const unpersisted = current.filter(item => !item.is_processing && item.id && !dbIds.has(String(item.id)));
          return [...inProgress, ...unpersisted, ...data.transactions];
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
        const sanitized = data.groups.map(g => {
          let pid = String(g.project_id || '');
          if (pid.toLowerCase() === 'none' || pid.toLowerCase() === 'null') pid = '';
          return { ...g, project_id: pid };
        });
        qaDbGroups.set(sanitized);
      }
    }
  } catch (err) {
    console.error("Failed to load QA groups from DB", err);
  }
}
