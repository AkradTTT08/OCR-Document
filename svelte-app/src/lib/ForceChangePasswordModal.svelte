<script>
    import { completeForcePasswordChange, logout, authUser } from './authStore.js';
    import { toast } from './toastStore.js';

    let currentPassword = '';
    let newPassword = '';
    let confirmPassword = '';
    let showPasswords = false;
    let isSubmitting = false;
    let errorMsg = '';

    function getStrength(pw) {
        if (!pw) return null;
        let score = 0;
        if (pw.length >= 8) score++;
        if (pw.length >= 12) score++;
        if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
        if (/\d/.test(pw)) score++;
        if (/[^A-Za-z0-9]/.test(pw)) score++;
        if (score <= 2) return { level: 'weak', label: 'ความปลอดภัยต่ำ', percent: 33 };
        if (score <= 3) return { level: 'medium', label: 'ความปลอดภัยปานกลาง', percent: 66 };
        return { level: 'strong', label: 'ความปลอดภัยสูง', percent: 100 };
    }

    $: strength = getStrength(newPassword);

    async function handleSubmit() {
        errorMsg = '';
        if (!currentPassword || !newPassword || !confirmPassword) {
            errorMsg = 'กรุณากรอกข้อมูลรหัสผ่านให้ครบทุกช่อง';
            return;
        }
        if (newPassword.length < 8) {
            errorMsg = 'รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 8 ตัวอักษร';
            return;
        }
        if (newPassword === currentPassword) {
            errorMsg = 'รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านชั่วคราวเดิม';
            return;
        }
        if (newPassword !== confirmPassword) {
            errorMsg = 'ยืนยันรหัสผ่านใหม่ไม่ตรงกัน';
            return;
        }

        isSubmitting = true;
        try {
            const token = localStorage.getItem('jwt_token');
            const res = await fetch('/api/auth/change-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { Authorization: `Bearer ${token}` } : {})
                },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                completeForcePasswordChange(data.token);
                toast('เปลี่ยนรหัสผ่านเรียบร้อยแล้ว ยินดีต้อนรับเข้าสู่ Spectra QA', 'success');
            } else {
                errorMsg = data.error || 'ไม่สามารถเปลี่ยนรหัสผ่านได้ กรุณาตรวจสอบรหัสผ่านปัจจุบัน';
            }
        } catch (err) {
            errorMsg = 'เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์';
        } finally {
            isSubmitting = false;
        }
    }
</script>

<div class="fcp-backdrop" role="presentation">
    <div class="fcp-dialog" role="dialog" aria-modal="true" aria-labelledby="fcp-title">
        <div class="fcp-icon-badge" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
            </svg>
        </div>
        <h2 id="fcp-title" class="fcp-title">ตั้งรหัสผ่านใหม่ก่อนเข้าใช้งาน</h2>
        <p class="fcp-subtitle">
            บัญชี <strong>@{$authUser}</strong> ถูกกำหนดให้เปลี่ยนรหัสผ่านเริ่มต้นเพื่อความปลอดภัยของระบบ
        </p>

        {#if errorMsg}
            <div class="fcp-error" role="alert">{errorMsg}</div>
        {/if}

        <form class="fcp-form" on:submit|preventDefault={handleSubmit}>
            <div class="fcp-field">
                <label for="fcp-current">รหัสผ่านปัจจุบัน (รหัสผ่านเริ่มต้น)</label>
                {#if showPasswords}
                    <input id="fcp-current" type="text" bind:value={currentPassword} autocomplete="current-password" placeholder="กรอกรหัสผ่านปัจจุบัน" />
                {:else}
                    <input id="fcp-current" type="password" bind:value={currentPassword} autocomplete="current-password" placeholder="กรอกรหัสผ่านปัจจุบัน" />
                {/if}
            </div>

            <div class="fcp-field">
                <label for="fcp-new">รหัสผ่านใหม่ (อย่างน้อย 8 ตัวอักษร)</label>
                {#if showPasswords}
                    <input id="fcp-new" type="text" bind:value={newPassword} autocomplete="new-password" placeholder="ตั้งรหัสผ่านใหม่ที่ปลอดภัย" />
                {:else}
                    <input id="fcp-new" type="password" bind:value={newPassword} autocomplete="new-password" placeholder="ตั้งรหัสผ่านใหม่ที่ปลอดภัย" />
                {/if}
                {#if strength}
                    <div class="fcp-strength">
                        <div class="fcp-track"><div class="fcp-fill {strength.level}" style="width: {strength.percent}%"></div></div>
                        <span class="fcp-strength-text {strength.level}">{strength.label}</span>
                    </div>
                {/if}
            </div>

            <div class="fcp-field">
                <label for="fcp-confirm">ยืนยันรหัสผ่านใหม่</label>
                {#if showPasswords}
                    <input id="fcp-confirm" type="text" bind:value={confirmPassword} autocomplete="new-password" placeholder="กรอกรหัสผ่านใหม่อีกครั้ง" />
                {:else}
                    <input id="fcp-confirm" type="password" bind:value={confirmPassword} autocomplete="new-password" placeholder="กรอกรหัสผ่านใหม่อีกครั้ง" />
                {/if}
            </div>

            <label class="fcp-show-toggle">
                <input type="checkbox" bind:checked={showPasswords} />
                <span>แสดงรหัสผ่าน</span>
            </label>

            <div class="fcp-actions">
                <button type="button" class="fcp-btn-ghost" on:click={() => logout('ออกจากระบบแล้ว')} disabled={isSubmitting}>
                    ออกจากระบบ
                </button>
                <button type="submit" class="fcp-btn-primary" disabled={isSubmitting}>
                    {isSubmitting ? 'กำลังบันทึก...' : 'บันทึกรหัสผ่านใหม่'}
                </button>
            </div>
        </form>
    </div>
</div>

<style>
    .fcp-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(5, 5, 10, 0.86);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: calc(var(--z-modal, 10000) + 500);
        padding: 16px;
    }
    .fcp-dialog {
        width: 100%;
        max-width: 440px;
        background: var(--bg2);
        border: 1px solid rgba(168, 85, 247, 0.32);
        border-radius: var(--radius-lg);
        box-shadow: 0 28px 72px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(255, 255, 255, 0.06);
        padding: 28px 26px 24px;
        font-family: var(--font-th);
        color: var(--text-main);
    }
    .fcp-icon-badge {
        width: 46px;
        height: 46px;
        border-radius: 50%;
        margin: 0 auto 12px;
        background: rgba(99, 102, 241, 0.16);
        border: 1px solid rgba(129, 140, 248, 0.4);
        color: var(--primary-soft-text-hover);
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .fcp-title {
        font-size: 19px;
        font-weight: 700;
        text-align: center;
        margin: 0 0 6px;
    }
    .fcp-subtitle {
        font-size: 13px;
        color: var(--text-muted);
        text-align: center;
        margin: 0 0 18px;
        line-height: 1.5;
    }
    .fcp-subtitle strong { color: var(--primary-soft-text-hover); font-family: var(--font-en); }
    .fcp-error {
        background: rgba(244, 63, 94, 0.14);
        border: 1px solid rgba(244, 63, 94, 0.36);
        color: var(--danger-soft-text);
        border-radius: var(--radius-sm);
        padding: 9px 12px;
        font-size: 12.5px;
        margin-bottom: 14px;
    }
    .fcp-form { display: flex; flex-direction: column; gap: 13px; }
    .fcp-field { display: flex; flex-direction: column; gap: 5px; }
    .fcp-field label { font-size: 12.5px; font-weight: 600; color: var(--text-muted); }
    .fcp-field input {
        min-height: 40px;
        background: var(--bg);
        border: 1px solid var(--glass-border-light);
        border-radius: var(--radius-sm);
        padding: 8px 12px;
        color: var(--text-main);
        font-size: 13.5px;
        font-family: var(--font-th);
    }
    .fcp-field input:focus-visible {
        border-color: var(--primary);
        outline: 2px solid rgba(99, 102, 241, 0.35);
        outline-offset: 1px;
    }
    .fcp-strength { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
    .fcp-track { width: 84px; height: 4px; border-radius: 999px; background: rgba(255, 255, 255, 0.1); overflow: hidden; }
    .fcp-fill { height: 100%; border-radius: 999px; transition: width 0.2s ease; }
    .fcp-fill.weak { background: var(--danger); }
    .fcp-fill.medium { background: var(--warning); }
    .fcp-fill.strong { background: var(--success); }
    .fcp-strength-text { font-size: 11px; font-weight: 600; }
    .fcp-strength-text.weak { color: var(--danger-soft-text); }
    .fcp-strength-text.medium { color: var(--warning-soft-text); }
    .fcp-strength-text.strong { color: var(--success-soft-text); }
    .fcp-show-toggle {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 12.5px;
        color: var(--text-muted);
        cursor: pointer;
    }
    .fcp-show-toggle input { accent-color: var(--primary); cursor: pointer; }
    .fcp-actions {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-top: 8px;
    }
    .fcp-btn-ghost {
        min-height: 40px;
        padding: 0 16px;
        border-radius: var(--radius-md);
        background: var(--surface-card);
        border: 1px solid var(--glass-border-light);
        color: var(--text-muted);
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .fcp-btn-ghost:hover:not(:disabled) { color: var(--text-main); background: var(--surface-card-hover); }
    .fcp-btn-primary {
        flex: 1;
        min-height: 40px;
        padding: 0 18px;
        border-radius: var(--radius-md);
        background: var(--gradient-main);
        border: 1px solid rgba(129, 140, 248, 0.35);
        color: #ffffff;
        font-size: 13.5px;
        font-weight: 600;
        cursor: pointer;
        font-family: inherit;
    }
    .fcp-btn-primary:disabled, .fcp-btn-ghost:disabled { opacity: 0.45; cursor: not-allowed; }
</style>

