import { writable, derived } from 'svelte/store';
import { toast } from './toastStore.js';

function parseStoredJson(key, defaultVal) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : defaultVal;
  } catch (e) {
    return defaultVal;
  }
}

export function parseJwt(token) {
  if (!token || typeof token !== 'string') return null;
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

export function isTokenExpired(token) {
  if (!token) return true;
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return false;
  return Date.now() >= payload.exp * 1000;
}

export const DEFAULT_USER_MENUS = [
  'qa_consult', 'qa_doc_creation', 'qa_analysis_diagram', 'qa_board',
  'qa_automate', 'qa_performance', 'qa_security', 'qa_research',
  'master_agent', 'workflow_builder'
];

export const DEFAULT_ADMIN_MENUS = [
  'ocr', 'project_management', 'kb', 'skills', 'qa_member',
  'exit_criteria', 'api_collection', 'api_usage'
];

// Check initial stored token expiration
const initialToken = localStorage.getItem('jwt_token') || '';
const isInitialExpired = initialToken ? isTokenExpired(initialToken) : true;
if (isInitialExpired && initialToken) {
  localStorage.removeItem('jwt_token');
  localStorage.removeItem('auth_user');
  localStorage.removeItem('auth_email');
  localStorage.removeItem('auth_role');
  localStorage.removeItem('auth_display_name');
  localStorage.removeItem('auth_avatar_path');
  localStorage.removeItem('auth_allowed_menus');
  localStorage.removeItem('auth_allowed_projects');
}

// ── Internal stores ──
const _token = writable(isInitialExpired ? '' : initialToken);
const _user  = writable(isInitialExpired ? '' : (localStorage.getItem('auth_user') || ''));
const _email = writable(isInitialExpired ? '' : (localStorage.getItem('auth_email') || ''));
const _role  = writable(isInitialExpired ? '' : (localStorage.getItem('auth_role') || ''));
const _displayName = writable(isInitialExpired ? '' : (localStorage.getItem('auth_display_name') || ''));
const _avatarPath = writable(isInitialExpired ? '' : (localStorage.getItem('auth_avatar_path') || ''));
const _allowedMenus = writable(isInitialExpired ? [] : parseStoredJson('auth_allowed_menus', []));
const _allowedProjects = writable(isInitialExpired ? ['all'] : parseStoredJson('auth_allowed_projects', ['all']));

// ── Derived readable stores for components ──
export const authUser = { subscribe: _user.subscribe };
export const authEmail = { subscribe: _email.subscribe };
export const authRole = { subscribe: _role.subscribe };
export const authDisplayName = { subscribe: _displayName.subscribe };
export const authAvatar = { subscribe: _avatarPath.subscribe };
export const authAllowedMenus = { subscribe: _allowedMenus.subscribe };
export const authAllowedProjects = { subscribe: _allowedProjects.subscribe };

/** showLogin is true when there is no valid token */
export const showLogin = derived(_token, ($t) => !$t);

let expiryTimeoutId = null;

function scheduleExpiryTimer(token) {
  if (expiryTimeoutId) {
    clearTimeout(expiryTimeoutId);
    expiryTimeoutId = null;
  }
  if (!token) return;
  const payload = parseJwt(token);
  if (!payload || !payload.exp) return;

  const msRemaining = payload.exp * 1000 - Date.now();
  if (msRemaining <= 0) {
    logout('เซสชันหมดอายุแล้ว กรุณาเข้าสู่ระบบใหม่');
    return;
  }

  expiryTimeoutId = setTimeout(() => {
    logout('เซสชันหมดอายุแล้ว กรุณาเข้าสู่ระบบใหม่');
  }, msRemaining);
}

// ── Actions ──

/**
 * Called after a successful login response.
 * Persists credentials and installs a fetch interceptor that
 * attaches the Authorization header to every subsequent request.
 */
export function login(token, user, role, displayName, avatarPath, allowedMenus, allowedProjects, email = '') {
  const finalMenus = allowedMenus || (role === 'admin' ? DEFAULT_ADMIN_MENUS : DEFAULT_USER_MENUS);
  const finalProjects = allowedProjects || ['all'];
  const finalEmail = (email || (user && user.includes('@') ? user : '') || localStorage.getItem('auth_email') || '').trim();

  _token.set(token);
  _user.set(user);
  _email.set(finalEmail);
  _role.set(role);
  _displayName.set(displayName || user);
  _avatarPath.set(avatarPath || '');
  _allowedMenus.set(finalMenus);
  _allowedProjects.set(finalProjects);

  localStorage.setItem('jwt_token', token);
  localStorage.setItem('auth_user', user);
  if (finalEmail) {
    localStorage.setItem('auth_email', finalEmail);
  }
  localStorage.setItem('auth_role', role);
  localStorage.setItem('auth_display_name', displayName || user);
  localStorage.setItem('auth_allowed_menus', JSON.stringify(finalMenus));
  localStorage.setItem('auth_allowed_projects', JSON.stringify(finalProjects));
  if (avatarPath) {
    localStorage.setItem('auth_avatar_path', avatarPath);
  } else {
    localStorage.removeItem('auth_avatar_path');
  }

  scheduleExpiryTimer(token);
  installFetchInterceptor();
}

/**
 * Dynamically updates the user's display name and/or avatar path in both
 * reactive stores and localStorage without requiring a full re-login.
 */
export function updateAuthProfile(displayName, avatarPath, email) {
  if (displayName) {
    _displayName.set(displayName);
    localStorage.setItem('auth_display_name', displayName);
  }
  if (email !== undefined) {
    _email.set(email || '');
    if (email) {
      localStorage.setItem('auth_email', email);
    } else {
      localStorage.removeItem('auth_email');
    }
  }
  if (avatarPath !== undefined) {
    _avatarPath.set(avatarPath || '');
    if (avatarPath) {
      localStorage.setItem('auth_avatar_path', avatarPath);
    } else {
      localStorage.removeItem('auth_avatar_path');
    }
  }
}

/**
 * Clears all auth state and triggers login screen.
 */
export function logout(reason = '') {
  if (expiryTimeoutId) {
    clearTimeout(expiryTimeoutId);
    expiryTimeoutId = null;
  }

  _token.set('');
  _user.set('');
  _email.set('');
  _role.set('');
  _displayName.set('');
  _avatarPath.set('');
  _allowedMenus.set([]);
  _allowedProjects.set(['all']);

  localStorage.removeItem('jwt_token');
  localStorage.removeItem('auth_user');
  localStorage.removeItem('auth_email');
  localStorage.removeItem('auth_role');
  localStorage.removeItem('auth_display_name');
  localStorage.removeItem('auth_avatar_path');
  localStorage.removeItem('auth_allowed_menus');
  localStorage.removeItem('auth_allowed_projects');

  if (reason) {
    toast(reason, 'warning');
  }
}

// ── Fetch interceptor ──
// Transparently adds the JWT token to every fetch() call and catches 401 Unauthorized
// to automatically log out expired sessions.

function installFetchInterceptor() {
  if (!window.originalFetch) {
    window.originalFetch = window.fetch;
  }

  window.fetch = async function (input, init = {}) {
    let url = '';
    if (typeof input === 'string') {
      url = input;
      input = input.replace(/^http:\/\/(localhost|127\.0\.0\.1):5000/i, '');
    } else if (input instanceof Request) {
      url = input.url;
      const cleanUrl = input.url.replace(/^http:\/\/(localhost|127\.0\.0\.1):5000/i, '');
      input = new Request(cleanUrl, input);
    }

    const isAuthEndpoint = typeof url === 'string' && (url.includes('/api/login') || url.includes('/api/auth/login'));
    const token = localStorage.getItem('jwt_token');

    // Pre-flight expiration check
    if (token && !isAuthEndpoint && isTokenExpired(token)) {
      logout('เซสชันหมดอายุแล้ว กรุณาเข้าสู่ระบบใหม่');
      return new Response(JSON.stringify({ error: 'Token expired' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    // Merge Authorization header
    const headers = new Headers(init.headers || {});
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    try {
      const response = await window.originalFetch(input, { ...init, headers });

      // If server returns 401 Unauthorized on protected routes, auto logout
      if (response.status === 401 && !isAuthEndpoint) {
        const activeToken = localStorage.getItem('jwt_token');
        if (activeToken) {
          logout('เซสชันหมดอายุหรือสิทธิ์ไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่');
        }
      }

      return response;
    } catch (err) {
      throw err;
    }
  };
}

// ── Bootstrap ──
if (!isInitialExpired && initialToken) {
  scheduleExpiryTimer(initialToken);
}
installFetchInterceptor();
