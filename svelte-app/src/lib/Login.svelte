<script>
    import { onDestroy } from 'svelte';
    import { login } from './authStore.js';
    import { toast } from './toastStore.js';
    import LegalModal from "./LegalModal.svelte";
    import McpLogo from "./McpLogo.svelte";

    let email = localStorage.getItem('remembered_email') || '';
    let password = '';
    let showPassword = false;
    let remember = !!localStorage.getItem('remembered_email');
    let isLoading = false;
    let legalModalType = null;
    let shakeCard = false;
    let lockoutSeconds = 0;
    let lockoutTimer = null;

    function startLockoutCountdown(seconds) {
        if (lockoutTimer) clearInterval(lockoutTimer);
        lockoutSeconds = Math.max(1, Math.ceil(Number(seconds) || 30));
        lockoutTimer = setInterval(() => {
            lockoutSeconds -= 1;
            if (lockoutSeconds <= 0) {
                lockoutSeconds = 0;
                clearInterval(lockoutTimer);
                lockoutTimer = null;
            }
        }, 1000);
    }

    onDestroy(() => {
        if (lockoutTimer) clearInterval(lockoutTimer);
    });

    function triggerShake() {
        shakeCard = false;
        requestAnimationFrame(() => {
            shakeCard = true;
            setTimeout(() => { shakeCard = false; }, 450);
        });
    }
    
    // Generate lightweight ambient light particles for the background
    const particles = Array.from({ length: 16 }, (_, i) => ({
        id: i,
        left: Math.random() * 100,
        top: Math.random() * 100,
        size: Math.random() * 2.5 + 1.5,
        duration: Math.random() * 16 + 16,
        delay: Math.random() * 12,
        drift: (Math.random() - 0.5) * 80
    }));

    async function handleLogin() {
        if (lockoutSeconds > 0) {
            triggerShake();
            toast(`กรุณารอ ${lockoutSeconds} วินาทีก่อนลองเข้าสู่ระบบใหม่อีกครั้ง`, 'warning');
            return;
        }
        const loginId = email.trim();
        if (!loginId || !password) {
            triggerShake();
            toast('กรุณากรอก Email / Username และ Password', 'warning');
            return;
        }
        if (password.length > 72) {
            triggerShake();
            toast('รหัสผ่านมีความยาวเกินกำหนด (สูงสุด 72 ตัวอักษร)', 'warning');
            return;
        }

        isLoading = true;
        try {
            const res = await (window.originalFetch || window.fetch)('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: loginId, email: loginId, password })
            });

            const data = await res.json().catch(() => ({}));
            
            if (res.ok && data.success) {
                if (remember) {
                    localStorage.setItem('remembered_email', loginId);
                } else {
                    localStorage.removeItem('remembered_email');
                }
                password = '';
                const userEmail = data.email || (data.user && data.user.includes('@') ? data.user : '') || (loginId.includes('@') ? loginId : '');
                login(data.token, data.user, data.role, data.display_name, data.avatar_path, data.allowed_menus, data.allowed_projects, userEmail, Boolean(data.must_change_password));
                toast(`เข้าสู่ระบบสำเร็จ! ยินดีต้อนรับ ${data.display_name || data.user}`, 'success');
            } else if (res.status === 429) {
                password = '';
                triggerShake();
                const retrySec = data.retry_after || parseInt(res.headers.get('Retry-After') || '60', 10);
                startLockoutCountdown(retrySec);
                toast(data.error || `พยายามเข้าสู่ระบบผิดหลายครั้ง กรุณารอ ${retrySec} วินาที`, 'warning');
            } else {
                password = '';
                triggerShake();
                toast(data.error || 'อีเมล/ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error');
            }
        } catch (err) {
            triggerShake();
            toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ฐานข้อมูลได้', 'error');
        } finally {
            isLoading = false;
        }
    }
</script>

<div class="login-wrapper">
    <!-- Animated Spectrum Background -->
    <div class="spectrum-bg"></div>
    <div class="spectrum-bg layer-2"></div>
    
    <div class="split-layout">
        
        <!-- Left Side: Branding -->
        <div class="brand-panel">
            <div class="brand-content">
                <h3 class="welcome-text">Welcome to QA Agent</h3>
                
                <div class="logo-square">
                    <img src="/spectra-logo.png" alt="Spectra QA Logo" />
                </div>
                
                <h1 class="brand-title">Spectra QA</h1>
                <p class="brand-desc">
                    Intelligent Document Analysis and Knowledge Base System.
                </p>

                <div class="brand-pillars">
                    <span class="pillar-pill">AI QA Agents</span>
                    <span class="pillar-pill">API &amp; Security</span>
                    <span class="pillar-pill">Thai / EN OCR</span>
                    <span class="pillar-pill pillar-mcp" title="รองรับ Model Context Protocol (MCP)">
                        <McpLogo size={13} />
                        <span>MCP Supported</span>
                    </span>
                </div>
                
                <div class="footer-text">
                    <span>v1.0.4</span> <span class="dot">•</span> <span>AI AGENT</span>
                </div>
            </div>
        </div>

        <!-- Right Side: Login Form (Glassmorphism) -->
        <div class="form-panel">
            <!-- Animated Particles -->
            <div class="particles-container">
                {#each particles as p}
                    <div class="particle" 
                         style="left: {p.left}%; top: {p.top}%; width: {p.size}px; height: {p.size}px; 
                                animation-duration: {p.duration}s; animation-delay: -{p.delay}s; 
                                --drift: {p.drift}px;">
                    </div>
                {/each}
            </div>

            <div class="glass-card" class:shake={shakeCard}>
                <h2 class="form-title">Sign In</h2>
                <p class="form-subtitle">เข้าสู่ระบบด้วยบัญชีของคุณ</p>
                
                <form on:submit|preventDefault={handleLogin}>
                    
                    <div class="input-group stagger-1" class:has-value={email.trim().length > 0}>
                        <label for="email">E-mail Address / Username</label>
                        <div class="input-with-icon">
                            <svg class="field-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                                <polyline points="22,6 12,13 2,6"></polyline>
                            </svg>
                            <input type="text" id="email" bind:value={email} maxlength="254" placeholder="admin@domain.com หรือ username" autocomplete="username" />
                            <span class="focus-beam" aria-hidden="true"></span>
                            <span class="valid-dot" aria-hidden="true"></span>
                        </div>
                    </div>
                    
                    <div class="input-group stagger-2" class:has-value={password.length > 0} class:is-unlocked={showPassword}>
                        <label for="password">Password</label>
                        <div class="password-wrapper input-with-icon">
                            <svg class="field-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                                <path class="lock-shackle" d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                            </svg>
                            <input type={showPassword ? "text" : "password"} id="password" bind:value={password} maxlength="72" placeholder="••••••••" autocomplete="current-password" />
                            <span class="focus-beam" aria-hidden="true"></span>
                            <button type="button" class="eye-btn" class:active={showPassword} aria-label={showPassword ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน'} on:click={() => showPassword = !showPassword}>
                                {#if showPassword}
                                    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                                {:else}
                                    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                                {/if}
                            </button>
                        </div>
                    </div>
                    
                    <div class="remember-me stagger-3">
                        <label class="checkbox-container">
                            <input type="checkbox" bind:checked={remember} />
                            <span class="checkmark">
                                <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                                    <polyline points="20 6 9 17 4 12"></polyline>
                                </svg>
                            </span>
                            <span class="check-label">Remember me</span>
                        </label>
                    </div>
                    
                    <div class="action-buttons stagger-4">
                        <button type="submit" disabled={isLoading || lockoutSeconds > 0} class="btn-primary">
                            {#if isLoading}
                                <span class="spinner"></span> กำลังเข้าสู่ระบบ...
                            {:else if lockoutSeconds > 0}
                                รอสักครู่ ({lockoutSeconds}s)...
                            {:else}
                                เข้าสู่ระบบ
                            {/if}
                        </button>
                    </div>
                    
                </form>
            </div>
            
            <div class="form-footer">
                &copy; {new Date().getFullYear()} Spectra QA System. All rights reserved. <br/>
                <button type="button" class="legal-link-btn" on:click={() => legalModalType = 'privacy'}>Privacy Policy</button> &middot;
                <button type="button" class="legal-link-btn" on:click={() => legalModalType = 'terms'}>Terms of Service</button> &middot;
                <button type="button" class="legal-link-btn" on:click={() => legalModalType = 'security'}>Security Architecture</button>
            </div>
        </div>

    </div>
</div>

{#if legalModalType}
  <LegalModal type={legalModalType} on:close={() => legalModalType = null} />
{/if}

<style>
    .login-wrapper {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: var(--bg-dark);
        z-index: 9999;
        font-family: var(--font-th);
        overflow: hidden;
    }

    /* ── Static Obsidian / Neon Ambient Background ── */
    .spectrum-bg {
        position: absolute;
        inset: 0;
        background:
            radial-gradient(circle at 20% 28%, rgba(99, 102, 241, 0.18) 0%, transparent 48%),
            radial-gradient(circle at 80% 72%, rgba(168, 85, 247, 0.16) 0%, transparent 48%),
            radial-gradient(circle at 50% 50%, rgba(6, 182, 212, 0.08) 0%, transparent 60%);
        z-index: 1;
        pointer-events: none;
    }
    
    .spectrum-bg.layer-2 {
        background:
            radial-gradient(circle at 72% 24%, rgba(99, 102, 241, 0.14), transparent 42%),
            radial-gradient(circle at 26% 78%, rgba(168, 85, 247, 0.14), transparent 42%);
        z-index: 2;
        pointer-events: none;
    }

    /* ── Split Layout ── */
    .split-layout {
        position: relative;
        z-index: 10;
        display: flex;
        width: 100%;
        height: 100%;
    }

    /* ── Left Branding Panel ── */
    .brand-panel {
        position: relative;
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        padding: 40px;
        color: var(--text-main);
        overflow-y: auto;
    }

    .brand-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        width: 100%;
        max-width: 650px;
        min-height: 100%;
    }

    @keyframes riseIn {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }

    @keyframes cardReveal {
        from { opacity: 0; transform: translateY(20px) scale(0.985); }
        to { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes shakeError {
        0%, 100% { transform: translateX(0); }
        20% { transform: translateX(-7px); }
        40% { transform: translateX(7px); }
        60% { transform: translateX(-4px); }
        80% { transform: translateX(4px); }
    }

    .welcome-text {
        font-family: var(--font-en);
        font-size: clamp(26px, 3.6vw, 52px);
        font-weight: 800;
        margin-top: auto;
        margin-bottom: 36px;
        color: var(--text-main);
        letter-spacing: -0.5px;
        line-height: 1.15;
        animation: riseIn 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .logo-square {
        position: relative;
        width: 140px;
        height: 140px;
        padding: 0;
        background: #080912;
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-xl);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 30px;
        box-shadow: 0 12px 40px rgba(99, 102, 241, 0.35),
                    inset 0 0 20px rgba(255, 255, 255, 0.05);
        animation: cardReveal 0.6s 0.08s cubic-bezier(0.22, 1, 0.36, 1) both,
                   float 5.5s 0.7s ease-in-out infinite;
    }

    .logo-square img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: inherit;
        display: block;
    }

    @property --prism-angle {
        syntax: '<angle>';
        initial-value: 0deg;
        inherits: false;
    }

    @keyframes prismOrbit {
        to { --prism-angle: 360deg; }
    }

    .logo-square::before {
        content: "";
        position: absolute;
        inset: -1px;
        border-radius: inherit;
        padding: 1.5px;
        background: conic-gradient(
            from var(--prism-angle),
            transparent 0%,
            rgba(99, 102, 241, 0.75) 20%,
            rgba(168, 85, 247, 0.85) 38%,
            rgba(6, 182, 212, 0.65) 52%,
            transparent 70%
        );
        -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
        animation: prismOrbit 6s linear infinite;
        pointer-events: none;
    }
    
    @keyframes float { 
        0% { transform: translateY(0px); } 
        50% { transform: translateY(-10px); } 
        100% { transform: translateY(0px); } 
    }

    .brand-title {
        font-family: var(--font-en);
        font-size: 42px;
        font-weight: 800;
        margin-bottom: 15px;
        letter-spacing: 1px;
        color: var(--text-main);
        animation: riseIn 0.55s 0.14s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .brand-desc {
        font-family: var(--font-en);
        font-size: 16px;
        line-height: 1.6;
        color: var(--text-muted);
        font-weight: 400;
        animation: riseIn 0.55s 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .brand-pillars {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 10px;
        margin-top: 24px;
        animation: riseIn 0.55s 0.26s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .pillar-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: var(--font-en);
        font-size: 12px;
        font-weight: 500;
        color: #c7d2fe;
        background: rgba(99, 102, 241, 0.1);
        border: 1px solid rgba(99, 102, 241, 0.25);
        padding: 5px 14px;
        border-radius: 20px;
        letter-spacing: 0.3px;
    }

    .pillar-mcp {
        color: #a5f3fc;
        background: rgba(6, 182, 212, 0.12);
        border-color: rgba(6, 182, 212, 0.34);
    }
    
    .footer-text {
        position: static;
        margin-top: auto;
        padding-top: 28px;
        font-family: var(--font-en);
        font-size: 12px;
        font-weight: 600;
        color: var(--text-dim);
        letter-spacing: 2px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .dot { color: var(--primary); }

    /* ── Right Form Panel ── */
    .form-panel {
        position: relative;
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        padding: 36px 40px;
        background: var(--glass-bg);
        backdrop-filter: var(--glass-blur);
        border-left: 1px solid var(--glass-border);
        box-shadow: -20px 0 50px rgba(0, 0, 0, 0.4);
        overflow-x: hidden;
        overflow-y: auto;
    }

    /* ── Light Particles ── */
    .particles-container {
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        overflow: hidden;
        pointer-events: none;
        z-index: 1;
    }
    
    .particle {
        position: absolute;
        background: #ffffff;
        border-radius: 50%;
        box-shadow: 0 0 8px #ffffff, 0 0 15px var(--primary);
        animation: float-particle linear infinite;
        opacity: 0;
    }

    @keyframes float-particle {
        0% { transform: translateY(100vh) translateX(0) scale(0); opacity: 0; }
        10% { opacity: 0.8; transform: translateY(80vh) translateX(calc(var(--drift) * 0.2)) scale(1); }
        90% { opacity: 0.8; transform: translateY(10vh) translateX(calc(var(--drift) * 0.8)) scale(1); }
        100% { transform: translateY(-10vh) translateX(var(--drift)) scale(0); opacity: 0; }
    }

    .glass-card {
        width: 100%;
        max-width: 480px;
        flex-shrink: 0;
        margin-top: auto;
        background: rgba(10, 11, 18, 0.65);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-xl);
        padding: 46px 48px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
        position: relative;
        z-index: 10;
        backdrop-filter: blur(20px);
        overflow: hidden;
        animation: cardReveal 0.6s 0.06s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .glass-card::before {
        content: "";
        position: absolute;
        top: 0;
        left: 12%;
        right: 12%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(99, 102, 241, 0.75), rgba(168, 85, 247, 0.75), transparent);
        pointer-events: none;
    }

    .glass-card.shake {
        animation: shakeError 0.4s cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
    }

    .stagger-1 { animation: riseIn 0.45s 0.12s cubic-bezier(0.22, 1, 0.36, 1) both; }
    .stagger-2 { animation: riseIn 0.45s 0.18s cubic-bezier(0.22, 1, 0.36, 1) both; }
    .stagger-3 { animation: riseIn 0.45s 0.24s cubic-bezier(0.22, 1, 0.36, 1) both; }
    .stagger-4 { animation: riseIn 0.45s 0.30s cubic-bezier(0.22, 1, 0.36, 1) both; }
    
    .form-footer {
        position: static;
        flex-shrink: 0;
        z-index: 10;
        margin-top: 24px;
        margin-bottom: auto;
        text-align: center;
        width: 100%;
        font-size: 12px;
        color: var(--text-dim);
        line-height: 1.7;
        font-family: var(--font-en);
    }
    
    .legal-link-btn {
        background: none;
        border: none;
        padding: 0;
        font: inherit;
        color: var(--text-muted);
        cursor: pointer;
        text-decoration: none;
        transition: color 0.2s;
    }
    
    .legal-link-btn:hover {
        color: var(--primary);
        text-decoration: underline;
    }

    .form-title {
        font-family: var(--font-en);
        font-size: 32px;
        font-weight: 700;
        color: var(--text-main);
        margin-bottom: 8px;
    }
    
    .form-subtitle {
        font-size: 14px;
        color: var(--text-muted);
        margin-bottom: 40px;
    }

    .input-group {
        margin-bottom: 25px;
    }

    .input-group label {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-family: var(--font-en);
        font-size: 13px;
        font-weight: 600;
        color: var(--text-muted);
        margin-bottom: 10px;
        letter-spacing: 0.5px;
        transition: color 0.24s cubic-bezier(0.16, 1, 0.3, 1), transform 0.24s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .input-group label::before {
        content: "";
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--primary);
        box-shadow: 0 0 8px var(--primary);
        opacity: 0;
        transform: scale(0);
        transition: opacity 0.22s cubic-bezier(0.16, 1, 0.3, 1), transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .input-group:focus-within label {
        color: #e0e7ff;
        transform: translateX(3px);
    }

    .input-group:focus-within label::before {
        opacity: 1;
        transform: scale(1);
    }

    .input-group.has-value:not(:focus-within) label {
        color: var(--text-main);
    }

    .input-with-icon {
        position: relative;
        display: flex;
        align-items: center;
        border-radius: var(--radius-md);
        overflow: hidden;
        transition: transform 0.26s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .input-with-icon:focus-within {
        transform: translateY(-1px);
    }

    .field-icon {
        position: absolute;
        left: 16px;
        z-index: 2;
        color: var(--text-dim);
        pointer-events: none;
        transition: color 0.25s cubic-bezier(0.16, 1, 0.3, 1), transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), filter 0.25s ease;
    }

    .input-group.has-value .field-icon {
        color: var(--text-muted);
    }

    .input-with-icon:focus-within .field-icon {
        color: var(--primary);
        transform: scale(1.12);
        filter: drop-shadow(0 0 6px rgba(99, 102, 241, 0.55));
    }

    .lock-shackle {
        transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        transform-origin: 17px 11px;
    }

    .input-group.is-unlocked .lock-shackle {
        transform: translateY(-2px);
    }

    .focus-beam {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--primary), var(--secondary), var(--accent));
        transform: scaleX(0);
        transform-origin: center;
        transition: transform 0.32s cubic-bezier(0.16, 1, 0.3, 1);
        pointer-events: none;
        z-index: 3;
    }

    .input-with-icon:focus-within .focus-beam {
        transform: scaleX(1);
    }

    .valid-dot {
        position: absolute;
        right: 16px;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--success, #10b981);
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
        opacity: 0;
        transform: scale(0.4);
        transition: opacity 0.22s cubic-bezier(0.16, 1, 0.3, 1), transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
        pointer-events: none;
    }

    .input-group.has-value .valid-dot {
        opacity: 1;
        transform: scale(1);
    }

    .input-group input {
        width: 100%;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 14px 38px 14px 44px;
        font-size: 15px;
        color: var(--text-main);
        font-family: var(--font-en);
        outline: none;
        transition: border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.25s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }
    
    .input-group input::placeholder {
        color: var(--text-dim);
        transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s ease;
    }

    .input-group input:focus::placeholder {
        opacity: 0.45;
        transform: translateX(4px);
    }

    .input-group.has-value input:not(:focus) {
        border-color: rgba(99, 102, 241, 0.32);
        background: rgba(15, 18, 30, 0.45);
    }

    .input-group input:hover:not(:focus) {
        border-color: rgba(255, 255, 255, 0.18);
        background: rgba(10, 12, 22, 0.45);
    }

    .input-group input:focus {
        border-color: rgba(99, 102, 241, 0.75);
        background: rgba(12, 15, 28, 0.68);
        box-shadow: 0 8px 24px -6px rgba(99, 102, 241, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }

    /* ── Password Field ── */
    .password-wrapper {
        position: relative;
        display: flex;
        align-items: center;
    }
    .password-wrapper input {
        padding-right: 44px;
    }
    .eye-btn {
        position: absolute;
        right: 12px;
        z-index: 3;
        background: transparent;
        border: none;
        color: var(--text-muted);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 6px;
        border-radius: 6px;
        transition: color 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), background-color 0.2s ease;
    }
    .eye-btn:hover {
        color: var(--text-main);
        background: rgba(255, 255, 255, 0.06);
        transform: scale(1.08);
    }
    .eye-btn:active {
        transform: scale(0.94);
    }
    .eye-btn.active {
        color: var(--secondary);
    }

    /* ── Checkbox ── */
    .remember-me {
        margin-bottom: 40px;
    }

    .checkbox-container {
        position: relative;
        display: inline-flex;
        align-items: center;
        gap: 12px;
        cursor: pointer;
        user-select: none;
    }
    
    .checkbox-container input {
        position: absolute;
        opacity: 0;
        width: 1px;
        height: 1px;
        pointer-events: none;
    }

    .checkbox-container input:focus-visible ~ .checkmark {
        outline: 2px solid var(--primary);
        outline-offset: 2px;
    }

    .checkmark {
        width: 22px;
        height: 22px;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--glass-border-light);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }
    
    .check-icon {
        width: 14px;
        height: 14px;
        color: white;
        opacity: 0;
        transform: scale(0.5);
        transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
    }

    .checkbox-container input:checked ~ .checkmark {
        background: var(--primary);
        border-color: var(--primary);
    }

    .checkbox-container input:checked ~ .checkmark .check-icon {
        opacity: 1;
        transform: scale(1);
    }

    .check-label {
        font-family: var(--font-en);
        font-size: 14px;
        color: var(--text-muted);
        font-weight: 500;
        transition: color 0.2s;
    }
    
    .checkbox-container:hover .check-label {
        color: #cbd5e1;
    }

    /* ── Buttons ── */
    .btn-primary {
        position: relative;
        overflow: hidden;
        width: 100%;
        background: var(--gradient-main);
        color: white;
        border: none;
        padding: 16px;
        border-radius: var(--radius-md);
        font-family: var(--font-th);
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.28s ease, background 0.28s ease;
        box-shadow: 0 10px 25px -5px var(--primary-glow);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }

    .btn-primary::after {
        content: "";
        position: absolute;
        top: 0;
        left: -100%;
        width: 60%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.22), transparent);
        transform: skewX(-20deg);
        transition: left 0.55s cubic-bezier(0.22, 1, 0.36, 1);
        pointer-events: none;
    }

    .btn-primary:hover:not(:disabled)::after {
        left: 140%;
    }

    .btn-primary:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 15px 30px -5px rgba(99, 102, 241, 0.6);
        background: var(--gradient-glow);
    }

    .btn-primary:active:not(:disabled) {
        transform: translateY(0) scale(0.99);
    }

    .btn-primary:disabled {
        opacity: 0.7;
        cursor: not-allowed;
        transform: none;
    }
    
    .spinner {
        width: 18px;
        height: 18px;
        border: 3px solid rgba(255,255,255,0.3);
        border-radius: 50%;
        border-top-color: #fff;
        animation: spin-fast 1s ease-in-out infinite;
    }
    
    @keyframes spin-fast { to { transform: rotate(360deg); } }

    /* Responsive */
    @media (max-width: 900px) {
        .login-wrapper {
            overflow-y: auto;
        }
        .split-layout {
            flex-direction: column;
            height: auto;
            min-height: 100%;
        }
        .brand-panel {
            flex: none;
            padding: 36px 20px 20px;
            overflow-y: visible;
        }
        .brand-content {
            min-height: auto;
        }
        .welcome-text { font-size: 28px; margin-top: 0; margin-bottom: 20px; white-space: normal; }
        .brand-title { font-size: 32px; }
        .logo-square { width: 96px; height: 96px; margin-bottom: 18px; border-radius: 20px; }
        .logo-square img { width: 64px; height: 64px; }
        .brand-pillars { margin-top: 16px; }
        .footer-text { display: none; }
        
        .form-panel {
            padding: 20px;
            flex-direction: column;
            border-left: none;
            border-top: 1px solid var(--glass-border);
            overflow-y: visible;
        }
        .glass-card {
            margin-top: 0;
            padding: 36px 24px;
        }
        .form-footer {
            position: static;
            margin-top: 24px;
            margin-bottom: 0;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .particles-container {
            display: none;
        }
        .particle,
        .logo-square,
        .logo-square::before,
        .spectrum-bg,
        .spectrum-bg.layer-2,
        .welcome-text,
        .brand-title,
        .brand-desc,
        .brand-pillars,
        .glass-card,
        .glass-card.shake,
        .stagger-1,
        .stagger-2,
        .stagger-3,
        .stagger-4,
        .spinner {
            animation: none !important;
        }
        .btn-primary::after {
            display: none;
        }
        .input-group:focus-within label,
        .input-with-icon:focus-within,
        .input-with-icon:focus-within .field-icon,
        .input-group input:focus::placeholder,
        .focus-beam {
            transform: none !important;
            transition: opacity 0.15s ease, color 0.15s ease !important;
        }
    }
</style>
