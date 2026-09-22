import { writable } from 'svelte/store';

const STORAGE_KEY = 'spectra_ocr_history';

// Initialize from localStorage for instant display
function getInitialHistory() {
    try {
        const cached = localStorage.getItem(STORAGE_KEY);
        if (cached) {
            const parsed = JSON.parse(cached);
            if (Array.isArray(parsed)) return parsed;
        }
    } catch (e) {}
    return [];
}

export const ocrHistory = writable(getInitialHistory());

const API_BASE = '/api';

export async function loadOCRHistory() {
    try {
        const response = await fetch(`${API_BASE}/ocr_history`);
        if (response.ok) {
            const results = await response.json();
            // Parse result_json back to object and normalize date
            const formattedResults = results.map(row => ({
                id: row.id,
                date: row.created_at,
                filename: row.filename,
                ...(row.result_json || {}) // Spread the result back so it acts like the original scanResult
            }));
            ocrHistory.set(formattedResults);
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(formattedResults.slice(0, 30)));
            } catch (e) {}
            return formattedResults;
        }
    } catch (e) {
        console.error("Failed to load OCR history from DB, using cached history:", e);
    }
    return getInitialHistory();
}

export async function saveOCRResult(result) {
    if (!result) return null;
    
    let savedItem = null;
    try {
        const payload = {
            filename: result.filename || 'Unknown Document',
            result_json: result
        };
        
        const response = await fetch(`${API_BASE}/ocr_history`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            const data = await response.json();
            savedItem = {
                ...result,
                id: data.id,
                date: data.created_at
            };
        } else {
            console.warn("Server returned non-ok status for OCR history save:", response.status);
        }
    } catch (e) {
        console.error("Failed to save OCR result to DB, falling back to local storage:", e);
    }
    
    // If backend save failed, create a persistent local record
    if (!savedItem) {
        savedItem = {
            ...result,
            id: result.id || `local_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
            date: result.date || new Date().toISOString()
        };
    }
    
    // Update store and localStorage
    ocrHistory.update(list => {
        const filtered = list.filter(item => item.id !== savedItem.id);
        const updated = [savedItem, ...filtered];
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated.slice(0, 30)));
        } catch (e) {}
        return updated;
    });
    
    return savedItem;
}

export async function deleteOCRHistory(id) {
    try {
        await fetch(`${API_BASE}/ocr_history/${id}`, {
            method: 'DELETE'
        });
    } catch (e) {
        console.error("Failed to delete OCR history from DB:", e);
    }
    
    // Always update local store and storage
    ocrHistory.update(list => {
        const updated = list.filter(item => item.id !== id);
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(updated.slice(0, 30)));
        } catch (e) {}
        return updated;
    });
    return true;
}
