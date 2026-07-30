import { writable } from 'svelte/store';

// Initialize from localStorage
const storedToken = localStorage.getItem('auth_token');
const storedUser = localStorage.getItem('auth_user');
const storedRole = localStorage.getItem('auth_role');

export const authToken = writable(storedToken || null);
export const authUser = writable(storedUser || null);
export const authRole = writable(storedRole || null);
export const showLogin = writable(!storedToken);

export function login(token, user, role) {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', user);
    localStorage.setItem('auth_role', role);
    updateActivity(); // reset timer
    authToken.set(token);
    authUser.set(user);
    authRole.set(role);
    showLogin.set(false);
}

export function logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('auth_role');
    localStorage.removeItem('last_activity');
    authToken.set(null);
    authUser.set(null);
    authRole.set(null);
    showLogin.set(true);
}

export function updateActivity() {
    localStorage.setItem('last_activity', Date.now().toString());
}

export function checkTimeout() {
    const lastActivity = localStorage.getItem('last_activity');
    if (lastActivity) {
        const now = Date.now();
        const diff = now - parseInt(lastActivity, 10);
        // 2 hours = 2 * 60 * 60 * 1000 = 7200000 ms
        if (diff > 7200000) {
            logout();
            return true;
        }
    }
    return false;
}

if (typeof window !== 'undefined') {
    window.addEventListener('auth_expired', () => {
        logout();
    });
    
    // Check timeout every 1 minute
    setInterval(checkTimeout, 60000);
    
    // Update activity on interactions
    window.addEventListener('mousemove', updateActivity);
    window.addEventListener('keydown', updateActivity);
    window.addEventListener('click', updateActivity);
}
