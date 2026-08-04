<script>
    import { login } from './authStore.js';
    import { toast } from './toastStore.js';

    let email = localStorage.getItem('remembered_email') || '';
    let password = '';
    let remember = !!localStorage.getItem('remembered_email');
    let isLoading = false;
    
    // Generate random light particles for the background
    const particles = Array.from({ length: 40 }, (_, i) => ({
        id: i,
        left: Math.random() * 100,
        top: Math.random() * 100,
        size: Math.random() * 3 + 1,
        duration: Math.random() * 15 + 15,
        delay: Math.random() * 10,
        drift: (Math.random() - 0.5) * 100
    }));

    async function handleLogin() {
        if (!email || !password) {
            toast('กรุณากรอก Email และ Password', 'warning');
            return;
        }

        isLoading = true;
        try {
            const res = await (window.originalFetch || window.fetch)('http://localhost:5000/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: email, password })
            });

            const data = await res.json();
            
            if (res.ok && data.success) {
                if (remember) {
                    localStorage.setItem('remembered_email', email);
                } else {
                    localStorage.removeItem('remembered_email');
                }
                login(data.token, data.user, data.role);
                toast(`เข้าสู่ระบบสำเร็จ! ยินดีต้อนรับ ${data.user}`, 'success');
            } else {
                toast(data.error || 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'error');
            }
        } catch (err) {
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
                
                <div class="logo-square" style="padding: 10px;">
                    <img src="/screen.png" alt="Spectra QA Logo" style="width: 100%; height: 100%; object-fit: contain; border-radius: 12px;" />
                </div>
                
                <h1 class="brand-title">Spectra QA</h1>
                <p class="brand-desc">
                    Intelligent Document Analysis and Knowledge Base System.
                </p>
                
                <div class="footer-text">
                    <span>V 1.0.0</span> <span class="dot">•</span> <span>AI AGENT</span>
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

            <div class="glass-card">
                <h2 class="form-title">Sign In</h2>
                <p class="form-subtitle">เข้าสู่ระบบด้วยบัญชีของคุณ</p>
                
                <form on:submit|preventDefault={handleLogin}>
                    
                    <div class="input-group">
                        <label for="email">E-mail Address</label>
                        <input type="text" id="email" bind:value={email} placeholder="admin@domain.com" autocomplete="email" />
                    </div>
                    
                    <div class="input-group">
                        <label for="password">Password</label>
                        <input type="password" id="password" bind:value={password} placeholder="••••••••" autocomplete="current-password" />
                    </div>
                    
                    <div class="remember-me">
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
                    
                    <div class="action-buttons">
                        <button type="submit" disabled={isLoading} class="btn-primary">
                            {#if isLoading}
                                <span class="spinner"></span> กำลังเข้าสู่ระบบ...
                            {:else}
                                เข้าสู่ระบบ
                            {/if}
                        </button>
                    </div>
                    
                </form>
            </div>
            
            <div class="form-footer">
                &copy; {new Date().getFullYear()} Spectra QA System. All rights reserved. <br/>
                <a href="#">Privacy Policy</a> &middot; <a href="#">Terms of Service</a>
            </div>
        </div>

    </div>
</div>

<style>
    .login-wrapper {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: var(--bg-dark);
        z-index: 9999;
        font-family: var(--font-th);
        overflow: hidden;
    }

    /* ── Animated Spectrum Background ── */
    .spectrum-bg {
        position: absolute;
        width: 150vw;
        height: 150vh;
        top: -25vh;
        left: -25vw;
        background: conic-gradient(
            from 180deg at 50% 50%,
            var(--bg-dark) 0deg,
            var(--danger) 60deg,
            var(--warning) 120deg,
            var(--success) 180deg,
            var(--primary) 240deg,
            var(--secondary) 300deg,
            var(--bg-dark) 360deg
        );
        filter: blur(140px);
        opacity: 0.15;
        animation: spin 30s linear infinite;
        z-index: 1;
        pointer-events: none;
    }
    
    .spectrum-bg.layer-2 {
        background: radial-gradient(circle at 70% 30%, rgba(99, 102, 241, 0.25), transparent 40%),
                    radial-gradient(circle at 30% 70%, rgba(168, 85, 247, 0.25), transparent 40%);
        filter: blur(90px);
        opacity: 0.6;
        animation: pulse 15s ease-in-out infinite alternate;
        z-index: 2;
        pointer-events: none;
    }

    @keyframes spin { 100% { transform: rotate(360deg); } }
    @keyframes pulse { 0% { transform: scale(1); } 100% { transform: scale(1.1); } }

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
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px;
        color: var(--text-main);
    }

    .brand-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        max-width: 650px;
    }

    .welcome-text {
        font-family: var(--font-en);
        font-size: clamp(32px, 4vw, 56px);
        font-weight: 800;
        margin-bottom: 40px;
        color: var(--text-main);
        letter-spacing: -0.5px;
        line-height: 1.1;
        white-space: nowrap;
    }

    .logo-square {
        width: 140px;
        height: 140px;
        background: var(--glass-bg);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-xl);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 30px;
        box-shadow: 0 0 40px var(--primary-glow),
                    inset 0 0 20px rgba(255, 255, 255, 0.05);
        backdrop-filter: var(--glass-blur);
        animation: float 5s ease-in-out infinite;
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
        background: var(--gradient-text);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .brand-desc {
        font-family: var(--font-en);
        font-size: 16px;
        line-height: 1.6;
        color: var(--text-muted);
        font-weight: 400;
    }
    
    .footer-text {
        position: absolute;
        bottom: 40px;
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
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px;
        background: var(--glass-bg);
        backdrop-filter: var(--glass-blur);
        border-left: 1px solid var(--glass-border);
        box-shadow: -20px 0 50px rgba(0, 0, 0, 0.4);
        overflow: hidden;
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
        background: rgba(10, 11, 18, 0.6);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-xl);
        padding: 50px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
        position: relative;
        z-index: 10;
        backdrop-filter: blur(20px);
    }
    
    .form-footer {
        position: absolute;
        bottom: 30px;
        text-align: center;
        width: 100%;
        font-size: 12px;
        color: var(--text-dim);
        line-height: 1.6;
        font-family: var(--font-en);
    }
    
    .form-footer a {
        color: var(--text-muted);
        text-decoration: none;
        transition: color 0.2s;
    }
    
    .form-footer a:hover {
        color: var(--primary);
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
        display: block;
        font-family: var(--font-en);
        font-size: 13px;
        font-weight: 600;
        color: var(--text-main);
        margin-bottom: 10px;
        letter-spacing: 0.5px;
    }

    .input-group input {
        width: 100%;
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 14px 18px;
        font-size: 15px;
        color: var(--text-main);
        font-family: var(--font-en);
        outline: none;
        transition: all 0.3s;
    }
    
    .input-group input::placeholder {
        color: var(--text-dim);
    }

    .input-group input:focus {
        border-color: var(--primary);
        background: rgba(0, 0, 0, 0.5);
        box-shadow: 0 0 0 4px var(--primary-glow);
    }

    /* ── Checkbox ── */
    .remember-me {
        margin-bottom: 40px;
    }

    .checkbox-container {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        cursor: pointer;
        user-select: none;
    }
    
    .checkbox-container input {
        display: none;
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
        transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
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
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        box-shadow: 0 10px 25px -5px var(--primary-glow);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
    }

    .btn-primary:hover:not(:disabled) {
        transform: translateY(-2px);
        box-shadow: 0 15px 30px -5px rgba(99, 102, 241, 0.6);
        background: var(--gradient-glow);
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
        .split-layout {
            flex-direction: column;
        }
        .brand-panel {
            flex: none;
            padding: 40px 20px 20px;
        }
        .welcome-text { font-size: 32px; margin-bottom: 25px; }
        .brand-title { font-size: 32px; }
        .logo-square { width: 100px; height: 100px; margin-bottom: 20px; border-radius: 20px; }
        .logo-square img { width: 70px; height: 70px; }
        .footer-text { display: none; }
        
        .form-panel {
            padding: 20px;
            align-items: flex-start;
        }
        .glass-card {
            padding: 40px 30px;
        }
    }
</style>
