import { writable } from 'svelte/store';

export const ocrHistory = writable([]);

const API_BASE = 'http://127.0.0.1:5000/api';

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
            return formattedResults;
        }
    } catch (e) {
        console.error("Failed to load OCR history from DB:", e);
    }
}

export async function saveOCRResult(result) {
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
            // Update local store with ID and date
            const item = {
                ...result,
                id: data.id,
                date: data.created_at
            };
            ocrHistory.update(list => [item, ...list]);
            return item;
        }
    } catch (e) {
        console.error("Failed to save OCR result to DB:", e);
    }
}

export async function deleteOCRHistory(id) {
    try {
        const response = await fetch(`${API_BASE}/ocr_history/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            ocrHistory.update(list => list.filter(item => item.id !== id));
            return true;
        }
    } catch (e) {
        console.error("Failed to delete OCR history from DB:", e);
    }
}
