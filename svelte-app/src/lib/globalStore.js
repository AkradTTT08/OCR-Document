import { writable } from 'svelte/store';

export const globalSearchQuery = writable("");
export const triggerGlobalSearch = writable(false);
