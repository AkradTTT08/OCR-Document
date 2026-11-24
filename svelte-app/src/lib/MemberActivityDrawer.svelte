<script>
    import { createEventDispatcher, tick } from 'svelte';
    import { toast } from './toastStore.js';

    export let open = false;
    export let user = null;

    const dispatch = createEventDispatcher();

    let drawerEl = null;
    let isLoading = false;
    let auditLogs = [];
    let usageSummary = {
        monthly_tokens_used: 0,
        monthly_cost_usd: 0,
        monthly_requests: 0,
        monthly_token_quota: 0,
        by_endpoint: []
    };
    let activeFilter = 'all'; // 'all' | 'login' | 'account' | 'security'
    let loadedUserId = null;

    const ACTION_META = {
        LOGIN_SUCCESS: { label: 'เข้าสู่ระบบสำเร็จ', cat: 'login', tone: 'success' },
        LOGIN_FAILED: { label: 'เข้าสู่ระบบไม่สำเร็จ', cat: 'login', tone: 'danger' },
        USER_CREATED: { label: 'สร้างบัญชีผู้ใช้', cat: 'account', tone: 'primary' },
        USER_UPDATED: { label: 'แก้ไขข้อมูลผู้ใช้', cat: 'account', tone: 'neutral' },
        PERMISSIONS_UPDATED: { label: 'ปรับสิทธิ์เมนู/โครงการ', cat: 'account', tone: 'primary' },
        ROLE_CHANGED: { label: 'เปลี่ยนระดับสิทธิ์', cat: 'security', tone: 'warning' },
        STATUS_CHANGED: { label: 'เปลี่ยนสถานะบัญชี', cat: 'security', tone: 'warning' },
        SESSION_REVOKED: { label: 'บังคับออกจากระบบ', cat: 'security', tone: 'danger' },
        PASSWORD_CHANGED: { label: 'เปลี่ยนรหัสผ่าน', cat: 'security', tone: 'success' },
        API_TOKEN_CREATED: { label: 'สร้าง API Token', cat: 'security', tone: 'primary' },
        API_TOKEN_REVOKED: { label: 'ยกเลิก API Token', cat: 'security', tone: 'danger' }
    };

    function getAuthHeaders() {
        const token = localStorage.getItem('jwt_token');
        return token ? { Authorization: `Bearer ${token}` } : {};
    }

    function formatTokens(n) {
        const val = Number(n || 0);
        if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`;
        if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
        return val.toLocaleString('en-US');
    }

    function formatDate(isoString) {
        if (!isoString) return '-';
        const d = new Date(isoString + (!isoString.endsWith('Z') && !isoString.includes('+') ? 'Z' : ''));
        return d.toLocaleString('th-TH', {
            day: '2-digit', month: '2-digit', year: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });
    }

    async function loadActivity(uid) {
        if (!uid) return;
        isLoading = true;
        try {
            const res = await fetch(`/api/users/${uid}/activity`, { headers: getAuthHeaders() });
            const data = await res.json().catch(() => ({}));
            if (res.ok && data.success) {
                auditLogs = data.audit_logs || [];
                usageSummary = data.usage_summary || usageSummary;
                loadedUserId = uid;
            } else {
                toast(data.error || 'ไม่สามารถโหลดประวัติการใช้งานได้', 'error');
            }
        } catch (err) {
            toast('เกิดข้อผิดพลาดในการเชื่อมต่อเพื่อโหลดประวัติการใช้งาน', 'error');
        } finally {
            isLoading = false;
        }
    }

    $: if (open && user && user.user_id && loadedUserId !== user.user_id) {
        activeFilter = 'all';
        loadActivity(user.user_id);
        tick().then(() => drawerEl?.focus());
    }

    $: if (!open) {
        loadedUserId = null;
    }

    $: filteredLogs = auditLogs.filter((log) => {
        if (activeFilter === 'all') return true;
        const meta = ACTION_META[log.action] || { cat: 'account' };
        return meta.cat === activeFilter;
    });

    $: quotaPercent = usageSummary.monthly_token_quota > 0
        ? Math.min(100, Math.round((usageSummary.monthly_tokens_used / usageSummary.monthly_token_quota) * 100))
        : 0;
    $: quotaTone = quotaPercent >= 100 ? 'danger' : quotaPercent >= 80 ? 'warning' : 'success';

    function close() {
        dispatch('close');
    }

    function handleKeydown(e) {
        if (e.key === 'Escape') close();
    }
</script>

{#if open && user}
<div class="drawer-backdrop" role="presentation" on:click={close} on:keydown={handleKeydown}>
    <aside
        bind:this={drawerEl}
        class="activity-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="activity-drawer-title"
        tabindex="-1"
        on:click|stopPropagation
    >
        <div class="drawer-header">
            <div class="drawer-user-meta">
                <div class="drawer-avatar">
                    {(user.display_name || user.username || 'U').charAt(0).toUpperCase()}
                </div>
                <div>
                    <h2 id="activity-drawer-title" class="drawer-title">{user.display_name || user.username}</h2>
                    <p class="drawer-sub">@{user.username} · {user.role?.toUpperCase()}</p>
                </div>
            </div>
            <div class="drawer-header-actions">
                <button
                    type="button"
                    class="drawer-icon-btn"
                    title="รีเฟรชข้อมูล"
                    aria-label="รีเฟรชประวัติการใช้งาน"
                    disabled={isLoading}
                    on:click={() => loadActivity(user.user_id)}
                >
                    <svg class:spinning={isLoading} aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                        <path d="M23 4v6h-6"></path><path d="M1 20v-6h6"></path>
                        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                    </svg>
                </button>
                <button type="button" class="drawer-icon-btn" aria-label="ปิดหน้าต่าง" on:click={close}>
                    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        </div>

        <div class="drawer-body">
            <!-- Monthly AI Token Usage & Quota -->
            <section class="drawer-card">
                <div class="card-head">
                    <h3>การใช้งาน AI Token เดือนนี้</h3>
                    <button type="button" class="btn-edit-quota-link" on:click={() => dispatch('editQuota', user)}>
                        ตั้งค่าโควตา
                    </button>
                </div>
                <div class="usage-kpis">
                    <div class="kpi-box">
                        <span class="kpi-label">ใช้งานแล้ว</span>
                        <strong class="kpi-val">{formatTokens(usageSummary.monthly_tokens_used)}</strong>
                    </div>
                    <div class="kpi-box">
                        <span class="kpi-label">โควตาต่อเดือน</span>
                        <strong class="kpi-val">
                            {usageSummary.monthly_token_quota > 0 ? formatTokens(usageSummary.monthly_token_quota) : 'ไม่จำกัด'}
                        </strong>
                    </div>
                    <div class="kpi-box">
                        <span class="kpi-label">ค่าใช้จ่ายประมาณการ</span>
                        <strong class="kpi-val">${Number(usageSummary.monthly_cost_usd || 0).toFixed(4)}</strong>
                    </div>
                </div>

                {#if usageSummary.monthly_token_quota > 0}
                    <div class="quota-bar-wrap">
                        <div class="quota-bar-track">
                            <div class="quota-bar-fill {quotaTone}" style="width: {quotaPercent}%"></div>
                        </div>
                        <span class="quota-pct {quotaTone}">{quotaPercent}%</span>
                    </div>
                {/if}

                {#if usageSummary.by_endpoint && usageSummary.by_endpoint.length > 0}
                    <div class="endpoint-breakdown">
                        <div class="breakdown-title">แยกตามโมดูล AI ({usageSummary.monthly_requests} ครั้ง)</div>
                        {#each usageSummary.by_endpoint as ep}
                            <div class="endpoint-row">
                                <span class="ep-name">{ep.endpoint}</span>
                                <span class="ep-val">{formatTokens(ep.tokens)} tok · {ep.requests}x</span>
                            </div>
                        {/each}
                    </div>
                {:else}
                    <div class="empty-note">ยังไม่มีบันทึกการใช้ AI Token ในเดือนนี้</div>
                {/if}
            </section>

            <!-- Audit & Login Timeline -->
            <section class="drawer-card">
                <div class="card-head">
                    <h3>ประวัติกิจกรรม & Audit Trail</h3>
                    <span class="count-pill">{filteredLogs.length} รายการ</span>
                </div>

                <div class="filter-pills" role="tablist" aria-label="กรองประเภทกิจกรรม">
                    <button type="button" class="filter-pill" class:active={activeFilter === 'all'} on:click={() => (activeFilter = 'all')}>ทั้งหมด</button>
                    <button type="button" class="filter-pill" class:active={activeFilter === 'login'} on:click={() => (activeFilter = 'login')}>การเข้าสู่ระบบ</button>
                    <button type="button" class="filter-pill" class:active={activeFilter === 'account'} on:click={() => (activeFilter = 'account')}>สิทธิ์ & บัญชี</button>
                    <button type="button" class="filter-pill" class:active={activeFilter === 'security'} on:click={() => (activeFilter = 'security')}>ความปลอดภัย</button>
                </div>

                {#if isLoading}
                    <div class="empty-note">กำลังโหลดประวัติกิจกรรม...</div>
                {:else if filteredLogs.length === 0}
                    <div class="empty-note">ยังไม่มีบันทึกกิจกรรมในหมวดนี้</div>
                {:else}
                    <div class="timeline-list">
                        {#each filteredLogs as log (log.audit_id)}
                            {@const meta = ACTION_META[log.action] || { label: log.action, tone: 'neutral' }}
                            <div class="timeline-item">
                                <div class="timeline-top">
                                    <span class="action-badge {meta.tone}">{meta.label}</span>
                                    <span class="timeline-time">{formatDate(log.created_at)}</span>
                                </div>
                                {#if log.details}
                                    <div class="timeline-detail">{log.details}</div>
                                {/if}
                                <div class="timeline-meta">
                                    <span>โดย: <strong>{log.actor_username}</strong></span>
                                    {#if log.ip_address}
                                        <span>· IP: {log.ip_address}</span>
                                    {/if}
                                </div>
                            </div>
                        {/each}
                    </div>
                {/if}
            </section>
        </div>
    </aside>
</div>
{/if}

<style>
    .drawer-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(5, 5, 10, 0.72);
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        z-index: calc(var(--z-modal, 10000) + 20);
        display: flex;
        justify-content: flex-end;
    }
    .activity-drawer {
        width: 100%;
        max-width: 460px;
        height: 100dvh;
        background: var(--bg2);
        border-left: 1px solid var(--glass-border-light);
        box-shadow: -16px 0 48px rgba(0, 0, 0, 0.75);
        display: flex;
        flex-direction: column;
        font-family: var(--font-th);
        color: var(--text-main);
        outline: none;
    }
    .drawer-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 18px 20px;
        background: var(--bg);
        border-bottom: 1px solid var(--glass-border);
    }
    .drawer-user-meta { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .drawer-avatar {
        width: 40px; height: 40px; border-radius: 50%; flex-shrink: 0;
        background: rgba(99, 102, 241, 0.22); border: 1px solid rgba(99, 102, 241, 0.45);
        color: var(--primary-soft-text-hover);
        display: flex; align-items: center; justify-content: center;
        font-family: var(--font-en); font-weight: 700; font-size: 16px;
    }
    .drawer-title { font-size: 16px; font-weight: 700; margin: 0; }
    .drawer-sub { font-size: 12px; color: var(--text-muted); margin: 2px 0 0; font-family: var(--font-en); }
    .drawer-header-actions { display: flex; gap: 6px; }
    .drawer-icon-btn {
        width: 34px; height: 34px; border-radius: var(--radius-sm);
        background: var(--surface-card); border: 1px solid var(--glass-border);
        color: var(--text-muted); cursor: pointer;
        display: inline-flex; align-items: center; justify-content: center;
    }
    .drawer-icon-btn:hover:not(:disabled) { color: var(--text-main); background: var(--surface-card-hover); }
    .drawer-icon-btn:focus-visible { outline: 2px solid var(--primary-soft-text); outline-offset: 2px; }

    .drawer-body {
        flex: 1;
        overflow-y: auto;
        padding: 16px 20px 24px;
        display: flex;
        flex-direction: column;
        gap: 14px;
        scrollbar-width: thin;
        scrollbar-color: rgba(129, 140, 248, 0.3) transparent;
    }
    .drawer-card {
        background: var(--surface-card);
        border: 1px solid var(--glass-border);
        border-radius: var(--radius-md);
        padding: 14px 16px;
    }
    .card-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 12px;
    }
    .card-head h3 { font-size: 14px; font-weight: 700; margin: 0; }
    .btn-edit-quota-link {
        background: none; border: none; color: var(--primary-soft-text);
        font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit; padding: 2px 4px;
    }
    .btn-edit-quota-link:hover { color: var(--primary-soft-text-hover); text-decoration: underline; }
    .count-pill {
        font-size: 11px; padding: 2px 8px; border-radius: 999px;
        background: rgba(99, 102, 241, 0.16); color: var(--primary-soft-text-hover);
        font-variant-numeric: tabular-nums;
    }

    .usage-kpis {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-bottom: 12px;
    }
    .kpi-box {
        background: var(--bg);
        border: 1px solid var(--glass-border);
        border-radius: 8px;
        padding: 8px 10px;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .kpi-label { font-size: 11px; color: var(--text-dim); }
    .kpi-val { font-size: 14px; font-weight: 700; font-family: var(--font-en); font-variant-numeric: tabular-nums; }

    .quota-bar-wrap { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
    .quota-bar-track { flex: 1; height: 6px; border-radius: 999px; background: rgba(255, 255, 255, 0.08); overflow: hidden; }
    .quota-bar-fill { height: 100%; border-radius: 999px; transition: width 0.25s ease; }
    .quota-bar-fill.success { background: var(--success); }
    .quota-bar-fill.warning { background: var(--warning); }
    .quota-bar-fill.danger { background: var(--danger); }
    .quota-pct { font-size: 11.5px; font-weight: 700; font-family: var(--font-en); font-variant-numeric: tabular-nums; }
    .quota-pct.success { color: var(--success-soft-text); }
    .quota-pct.warning { color: var(--warning-soft-text); }
    .quota-pct.danger { color: var(--danger-soft-text); }

    .endpoint-breakdown {
        border-top: 1px solid var(--glass-border);
        padding-top: 10px;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }
    .breakdown-title { font-size: 11.5px; color: var(--text-muted); font-weight: 600; margin-bottom: 2px; }
    .endpoint-row {
        display: flex; justify-content: space-between; align-items: center; gap: 8px;
        font-size: 12px;
    }
    .ep-name { color: var(--text-main); font-family: var(--font-en); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .ep-val { color: var(--text-dim); font-family: var(--font-en); font-variant-numeric: tabular-nums; flex-shrink: 0; }

    .filter-pills { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
    .filter-pill {
        min-height: 28px; padding: 3px 10px; border-radius: 999px;
        background: var(--bg); border: 1px solid var(--glass-border);
        color: var(--text-muted); font-size: 11.5px; font-weight: 600; cursor: pointer; font-family: inherit;
    }
    .filter-pill.active {
        background: rgba(99, 102, 241, 0.22); border-color: rgba(129, 140, 248, 0.45); color: var(--text-main);
    }

    .timeline-list { display: flex; flex-direction: column; gap: 8px; }
    .timeline-item {
        background: var(--bg);
        border: 1px solid var(--glass-border);
        border-radius: 8px;
        padding: 10px 12px;
    }
    .timeline-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 5px; }
    .timeline-time { font-size: 11px; color: var(--text-dim); font-variant-numeric: tabular-nums; }
    .action-badge {
        font-size: 11px; font-weight: 600; padding: 2px 7px; border-radius: 999px;
    }
    .action-badge.success { background: rgba(16, 185, 129, 0.16); color: var(--success-soft-text); }
    .action-badge.danger { background: rgba(244, 63, 94, 0.16); color: var(--danger-soft-text); }
    .action-badge.warning { background: rgba(245, 158, 11, 0.16); color: var(--warning-soft-text); }
    .action-badge.primary { background: rgba(99, 102, 241, 0.18); color: var(--primary-soft-text-hover); }
    .action-badge.neutral { background: rgba(255, 255, 255, 0.08); color: var(--text-muted); }

    .timeline-detail { font-size: 12.5px; color: var(--text-main); margin-bottom: 4px; line-height: 1.4; }
    .timeline-meta { font-size: 11px; color: var(--text-dim); display: flex; flex-wrap: wrap; gap: 4px; }
    .timeline-meta strong { color: var(--text-muted); font-family: var(--font-en); }
    .empty-note { font-size: 12.5px; color: var(--text-dim); text-align: center; padding: 14px 8px; }

    .spinning { animation: spin 0.9s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
</style>

