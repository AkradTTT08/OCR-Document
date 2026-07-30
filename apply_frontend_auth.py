import os
import re

BASE_DIR = r"d:\OCR-Github\OCR-Document\svelte-app"
LIB_DIR = os.path.join(BASE_DIR, "src", "lib")

# 1. Create authStore.js with Role support
auth_store_code = """import { writable } from 'svelte/store';

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
    authToken.set(token);
    authUser.set(user);
    authRole.set(role);
    showLogin.set(false);
}

export function logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('auth_role');
    authToken.set(null);
    authUser.set(null);
    authRole.set(null);
    showLogin.set(true);
}

// Listen to global auth expired events
if (typeof window !== 'undefined') {
    window.addEventListener('auth_expired', () => {
        logout();
    });
}
"""
with open(os.path.join(LIB_DIR, "authStore.js"), "w", encoding="utf-8") as f:
    f.write(auth_store_code)

# 2. Create Login.svelte
login_svelte_code = """<script>
    import { login } from './authStore.js';
    import { toast } from './toastStore.js';

    let username = '';
    let password = '';
    let isLoading = false;

    async function handleLogin() {
        if (!username || !password) {
            toast('กรุณากรอก Username และ Password', 'warning');
            return;
        }

        isLoading = true;
        try {
            const res = await (window.originalFetch || window.fetch)('http://localhost:5000/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await res.json();
            
            if (res.ok && data.success) {
                login(data.token, data.user, data.role);
                toast(`ยินดีต้อนรับ ${data.user} (${data.role})`, 'success');
            } else {
                toast(data.error || 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error');
            }
        } catch (err) {
            toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้', 'error');
        } finally {
            isLoading = false;
        }
    }
</script>

<div class="login-container">
    <div class="login-box">
        <div class="logo">
            <div class="logo-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 3 3 21 21 21"></polygon>
                    <line x1="3" y1="14" x2="21" y2="14"></line>
                    <line x1="8" y1="10" x2="16" y2="10"></line>
                </svg>
            </div>
            <h2>Spectra QA</h2>
            <p>กรุณาเข้าสู่ระบบเพื่อใช้งาน</p>
        </div>

        <form on:submit|preventDefault={handleLogin}>
            <div class="input-group">
                <label for="username">Username</label>
                <input type="text" id="username" bind:value={username} placeholder="admin" autocomplete="username" />
            </div>
            <div class="input-group">
                <label for="password">Password</label>
                <input type="password" id="password" bind:value={password} placeholder="••••••••" autocomplete="current-password" />
            </div>
            
            <button type="submit" disabled={isLoading} class="login-btn">
                {#if isLoading}กำลังเข้าสู่ระบบ...{:else}เข้าสู่ระบบ{/if}
            </button>
        </form>
    </div>
</div>

<style>
    .login-container {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        display: flex; align-items: center; justify-content: center;
        background: var(--bg, #0a0a0c); z-index: 9999;
    }
    .login-box {
        background: var(--surface, #121216); border: 1px solid var(--border, #2a2a35);
        border-radius: 16px; padding: 40px; width: 100%; max-width: 400px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    }
    .logo { text-align: center; margin-bottom: 30px; }
    .logo-icon {
        width: 50px; height: 50px; background: linear-gradient(135deg, var(--primary, #6C8EFB), var(--accent, #9B6Cfb));
        border-radius: 12px; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; color: white;
    }
    .logo h2 { color: var(--text, #f0f0f5); font-size: 24px; margin: 0 0 8px; }
    .logo p { color: var(--text3, #8a8a9a); font-size: 14px; margin: 0; }
    .input-group { margin-bottom: 20px; }
    .input-group label { display: block; margin-bottom: 8px; color: var(--text2, #b4b4c4); font-size: 13px; font-weight: 500; }
    .input-group input {
        width: 100%; padding: 12px 16px; background: var(--bg2, #18181d);
        border: 1px solid var(--border, #2a2a35); border-radius: 8px; color: var(--text, #f0f0f5); font-size: 15px; outline: none; transition: all 0.2s;
    }
    .input-group input:focus { border-color: var(--primary, #6C8EFB); box-shadow: 0 0 0 2px rgba(108,142,251,0.2); }
    .login-btn {
        width: 100%; padding: 14px; background: linear-gradient(135deg, var(--primary, #6C8EFB), var(--accent, #9B6Cfb));
        color: white; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s; margin-top: 10px;
    }
    .login-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(108,142,251,0.4); }
    .login-btn:disabled { opacity: 0.7; cursor: not-allowed; }
</style>
"""
with open(os.path.join(LIB_DIR, "Login.svelte"), "w", encoding="utf-8") as f:
    f.write(login_svelte_code)

# 3. Create ComingSoon.svelte
coming_soon_svelte = """<script>
    import { logout, authUser } from './authStore.js';
</script>

<div class="coming-soon">
    <div class="content">
        <div class="icon">🚀</div>
        <h2>Coming Soon</h2>
        <p>สวัสดีคุณ <strong>{$authUser}</strong></p>
        <p class="desc">ฟีเจอร์สำหรับผู้ใช้งานทั่วไป (User) กำลังอยู่ระหว่างการพัฒนา<br>กรุณารอติดตามการอัปเดตในเวอร์ชันถัดไปครับ</p>
        <button class="logout-btn" on:click={logout}>ออกจากระบบ</button>
    </div>
</div>

<style>
    .coming-soon {
        width: 100vw; height: 100vh;
        display: flex; align-items: center; justify-content: center;
        background: var(--bg, #0a0a0c);
        color: var(--text, #f0f0f5);
        text-align: center;
    }
    .content {
        background: var(--surface, #121216);
        padding: 50px; border-radius: 20px;
        border: 1px solid var(--border, #2a2a35);
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .icon { font-size: 60px; margin-bottom: 20px; animation: float 3s ease-in-out infinite; }
    h2 { font-size: 32px; margin-bottom: 10px; background: linear-gradient(135deg, var(--primary, #6C8EFB), var(--accent, #9B6Cfb)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .desc { color: var(--text3, #8a8a9a); margin-top: 10px; font-size: 15px; line-height: 1.6; }
    .logout-btn {
        margin-top: 30px; padding: 10px 24px;
        background: transparent; color: var(--danger, #f87171);
        border: 1px solid rgba(248,113,113,0.3); border-radius: 8px;
        cursor: pointer; font-size: 14px; transition: all 0.2s;
    }
    .logout-btn:hover { background: rgba(248,113,113,0.1); }
    @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }
</style>
"""
with open(os.path.join(LIB_DIR, "ComingSoon.svelte"), "w", encoding="utf-8") as f:
    f.write(coming_soon_svelte)


# 4. Update main.js to intercept fetch
main_js_path = os.path.join(BASE_DIR, "src", "main.js")
with open(main_js_path, "r", encoding="utf-8") as f:
    main_js_content = f.read()

fetch_interceptor = """// --- Auth Interceptor ---
window.originalFetch = window.fetch;
window.fetch = async (resource, config) => {
  const token = localStorage.getItem('auth_token');
  
  if (typeof resource === 'string' && resource.includes('/api/') && !resource.includes('/api/login')) {
    config = config || {};
    config.headers = config.headers || {};
    
    if (config.headers instanceof Headers) {
      config.headers.set('Authorization', `Bearer ${token}`);
    } else {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
  }
  
  try {
    const response = await window.originalFetch(resource, config);
    if (response.status === 401 && resource.includes('/api/')) {
        window.dispatchEvent(new Event('auth_expired'));
    }
    return response;
  } catch (err) {
    throw err;
  }
};
// -----------------------
"""
if "Auth Interceptor" not in main_js_content:
    main_js_content = fetch_interceptor + "\n" + main_js_content
    with open(main_js_path, "w", encoding="utf-8") as f:
        f.write(main_js_content)


# 5. Update App.svelte to handle Login, Role checks, and Coming Soon
app_svelte_path = os.path.join(BASE_DIR, "src", "App.svelte")
with open(app_svelte_path, "r", encoding="utf-8") as f:
    app_svelte_content = f.read()

if "import Login" not in app_svelte_content:
    app_svelte_content = app_svelte_content.replace(
        'import Toast from "./lib/Toast.svelte";',
        'import Toast from "./lib/Toast.svelte";\n  import Login from "./lib/Login.svelte";\n  import ComingSoon from "./lib/ComingSoon.svelte";\n  import { showLogin, authUser, authRole, logout } from "./lib/authStore.js";'
    )

if "{#if $showLogin}" not in app_svelte_content:
    # We will inject the condition around the <div class="shell">
    shell_pattern = r'(<div class="shell">[\s\S]+?</div>\n\n<!-- Global Toast)'
    
    replacement = """{#if $showLogin}
  <Login />
{:else if $authRole !== 'admin'}
  <ComingSoon />
{:else}
  \\1"""
    app_svelte_content = re.sub(shell_pattern, replacement, app_svelte_content)
    
    # Close the block after Toast
    app_svelte_content = app_svelte_content.replace(
        '<Toast />',
        '<Toast />\n{/if}'
    )

logout_button = """
        <div class="user-profile" style="margin-left: auto; display: flex; align-items: center; gap: 10px; padding-right: 20px;">
          <span style="color: var(--text2); font-size: 13px;">🧑‍💻 {$authUser} <span style="opacity:0.5; font-size:11px;">({$authRole})</span></span>
          <button on:click={logout} style="background: rgba(248,113,113,0.1); color: var(--danger); border: 1px solid rgba(248,113,113,0.2); padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer;">Logout</button>
        </div>
      </nav>
"""
if "user-profile" not in app_svelte_content:
    app_svelte_content = app_svelte_content.replace('</nav>', logout_button)

with open(app_svelte_path, "w", encoding="utf-8") as f:
    f.write(app_svelte_content)

print("✅ Svelte Frontend successfully patched with Auth & Coming Soon Page!")
