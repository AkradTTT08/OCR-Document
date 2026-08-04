import { writable, derived } from 'svelte/store';

// ── Internal stores ──
const _token = writable(localStorage.getItem('jwt_token') || '');
const _user  = writable(localStorage.getItem('auth_user')  || '');
const _role  = writable(localStorage.getItem('auth_role')  || '');

// ── Derived readable stores for components ──
export const authUser = { subscribe: _user.subscribe };
export const authRole = { subscribe: _role.subscribe };

/** showLogin is true when there is no valid token */
export const showLogin = derived(_token, ($t) => !$t);

// ── Actions ──

/**
 * Called after a successful login response.
 * Persists credentials and installs a fetch interceptor that
 * attaches the Authorization header to every subsequent request.
 */
export function login(token, user, role) {
  _token.set(token);
  _user.set(user);
  _role.set(role);

  localStorage.setItem('jwt_token', token);
  localStorage.setItem('auth_user', user);
  localStorage.setItem('auth_role', role);

  installFetchInterceptor(token);
}

/**
 * Clears all auth state and removes the fetch interceptor.
 */
export function logout() {
  _token.set('');
  _user.set('');
  _role.set('');

  localStorage.removeItem('jwt_token');
  localStorage.removeItem('auth_user');
  localStorage.removeItem('auth_role');

  // Restore the original fetch if we patched it
  if (window.originalFetch) {
    window.fetch = window.originalFetch;
    delete window.originalFetch;
  }
}

// ── Fetch interceptor ──
// Transparently adds the JWT token to every fetch() call so that
// components don't need to worry about auth headers.

function installFetchInterceptor(token) {
  // Only patch once
  if (!window.originalFetch) {
    window.originalFetch = window.fetch;
  }

  window.fetch = function (input, init = {}) {
    // Merge Authorization header
    const headers = new Headers(init.headers || {});
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    return window.originalFetch(input, { ...init, headers });
  };
}

// ── Bootstrap ──
// If a token already exists in localStorage (page refresh), re-install
// the interceptor so authenticated requests keep working.
const savedToken = localStorage.getItem('jwt_token');
if (savedToken) {
  installFetchInterceptor(savedToken);
}
