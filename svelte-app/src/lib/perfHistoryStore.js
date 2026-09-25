import { writable } from 'svelte/store';

/** @type {import('svelte/store').Writable<any[]>} */
export const perfHistory = writable([]);
/** @type {import('svelte/store').Writable<any>} */
export const selectedPerfHistory = writable(null);

export function loadPerfHistory() {
    try {
        const saved = localStorage.getItem('spectra_perf_history');
        if (saved) {
            perfHistory.set(JSON.parse(saved));
        }
    } catch(e) {
        console.error("Failed to load perf history", e);
    }
}

export function addPerfHistory(item) {
    perfHistory.update(current => {
        const updated = [item, ...current];
        localStorage.setItem('spectra_perf_history', JSON.stringify(updated));
        return updated;
    });
}
