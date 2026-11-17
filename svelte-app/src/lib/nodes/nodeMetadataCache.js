let skillsPromise = null;
let skillsCacheTime = 0;
const docTypesPromises = new Map();
const docTypesCacheTime = new Map();
const CACHE_TTL_MS = 60000;

export function getCachedSkills() {
  const now = Date.now();
  if (!skillsPromise || now - skillsCacheTime > CACHE_TTL_MS) {
    skillsCacheTime = now;
    skillsPromise = fetch('/api/skills')
      .then((res) => (res.ok ? res.json() : { skills: [] }))
      .then((d) => d.skills || [])
      .catch((err) => {
        console.error('load skills error:', err);
        skillsPromise = null;
        return [];
      });
  }
  return skillsPromise;
}

export function getCachedDocTypes(projectId = '') {
  const key = String(projectId || '');
  const now = Date.now();
  const cachedAt = docTypesCacheTime.get(key) || 0;
  if (!docTypesPromises.has(key) || now - cachedAt > CACHE_TTL_MS) {
    docTypesCacheTime.set(key, now);
    const url = key ? `/api/doc_types?project_id=${encodeURIComponent(key)}` : '/api/doc_types';
    const p = fetch(url)
      .then((res) => (res.ok ? res.json() : []))
      .then((d) => (Array.isArray(d) ? d : []))
      .catch((err) => {
        console.error('load doc types error:', err);
        docTypesPromises.delete(key);
        return [];
      });
    docTypesPromises.set(key, p);
  }
  return docTypesPromises.get(key);
}

