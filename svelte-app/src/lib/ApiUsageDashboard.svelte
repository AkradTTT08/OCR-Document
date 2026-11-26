<script>
    import { onMount, onDestroy } from 'svelte';
    import { fade, slide } from 'svelte/transition';
    import { cubicOut } from 'svelte/easing';
    import { toast, customConfirm } from './toastStore.js';
    import LineChart from './LineChart.svelte';
    import CustomSelect from './CustomSelect.svelte';

    let stats = null;
    let loading = true;
    let recalculating = false;
    let savingCredit = false;
    let error = null;
    let creditThb = null;
    let creditError = false;
    let lastUpdatedAt = '';
    let isEditingCredit = false;
    let newCreditThb = '';
    let showPricingRef = false;
    let highlightedModel = '';

    let timeFilter = 'all';

    // Animated KPI display values (smooth cubic ease-out rolling counters)
    let animTotalTokens = 0;
    let animCostUsd = 0;
    let animCreditThb = 0;
    let animRemainingThb = 0;
    let rafId = null;

    const TIME_FILTER_OPTIONS = [
        { value: 'all', label: 'ทั้งหมด (All-time)' },
        { value: 'daily', label: 'วันนี้ (Today)' },
        { value: 'monthly', label: 'เดือนนี้ (This Month)' },
        { value: 'yearly', label: 'ปีนี้ (This Year)' },
    ];

    function prefersReducedMotion() {
        return (
            typeof window !== 'undefined' &&
            window.matchMedia &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches
        );
    }

    function animateKpis(targetTokens, targetUsd, targetCredit, targetRem) {
        if (rafId) cancelAnimationFrame(rafId);
        if (prefersReducedMotion()) {
            animTotalTokens = targetTokens;
            animCostUsd = targetUsd;
            animCreditThb = targetCredit;
            animRemainingThb = targetRem;
            return;
        }

        const startTokens = animTotalTokens;
        const startUsd = animCostUsd;
        const startCredit = animCreditThb;
        const startRem = animRemainingThb;
        const duration = 420;
        const t0 = performance.now();

        function step(now) {
            const p = Math.min(1, (now - t0) / duration);
            const ease = 1 - Math.pow(1 - p, 3);
            animTotalTokens = startTokens + (targetTokens - startTokens) * ease;
            animCostUsd = startUsd + (targetUsd - startUsd) * ease;
            animCreditThb = startCredit + (targetCredit - startCredit) * ease;
            animRemainingThb = startRem + (targetRem - startRem) * ease;
            if (p < 1) {
                rafId = requestAnimationFrame(step);
            } else {
                animTotalTokens = targetTokens;
                animCostUsd = targetUsd;
                animCreditThb = targetCredit;
                animRemainingThb = targetRem;
                rafId = null;
            }
        }
        rafId = requestAnimationFrame(step);
    }

    function handleCardPointerMove(e) {
        if (prefersReducedMotion()) return;
        const rect = e.currentTarget.getBoundingClientRect();
        e.currentTarget.style.setProperty('--mx', `${e.clientX - rect.left}px`);
        e.currentTarget.style.setProperty('--my', `${e.clientY - rect.top}px`);
    }

    function handleToggleModel(e) {
        const model = typeof e === 'string' ? e : e.detail;
        highlightedModel = highlightedModel === model ? '' : model;
    }

    function stampNow() {
        return new Date().toLocaleTimeString('th-TH', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    async function fetchStats() {
        loading = true;
        if (!stats) error = null;
        try {
            const token = localStorage.getItem('jwt_token');
            const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
            const [res, creditRes] = await Promise.all([
                fetch(`/api/admin/usage?time_filter=${timeFilter}`, { headers }),
                fetch('/api/admin/credit', { headers })
            ]);

            const data = await res.json();
            if (res.ok && data.success) {
                stats = data.stats;
                error = null;
                lastUpdatedAt = stampNow();
            } else {
                const msg = data.error || 'ไม่สามารถโหลดข้อมูลสถิติ Token Usage ได้';
                if (!stats) error = msg;
                toast(msg, 'error');
            }

            if (creditRes.ok) {
                const creditData = await creditRes.json();
                if (creditData.success) {
                    creditThb = Number(creditData.credit_thb || 0);
                    creditError = false;
                } else {
                    creditError = true;
                }
            } else {
                creditError = true;
            }
        } catch (e) {
            const msg = 'ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์เพื่อโหลดข้อมูลได้';
            if (!stats) error = msg;
            toast(msg, 'error');
        } finally {
            loading = false;
        }
    }

    async function updateCredit() {
        const parsed = parseFloat(newCreditThb);
        if (isNaN(parsed) || parsed < 0) {
            toast('กรุณาระบุยอดเครดิตสะสมเป็นตัวเลขตั้งแต่ 0 ขึ้นไป', 'warning');
            return;
        }
        savingCredit = true;
        try {
            const token = localStorage.getItem('jwt_token');
            const res = await fetch('/api/admin/credit', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ credit_thb: parsed })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                creditThb = Number(data.credit_thb);
                creditError = false;
                isEditingCredit = false;
                toast('บันทึกยอดเครดิตสะสมเรียบร้อยแล้ว', 'success');
            } else {
                toast(data.error || 'อัปเดตเครดิตไม่สำเร็จ', 'error');
            }
        } catch (e) {
            toast('เกิดข้อผิดพลาดระหว่างบันทึกเครดิต', 'error');
        } finally {
            savingCredit = false;
        }
    }

    function handleCreditKeydown(e) {
        if (e.key === 'Escape') {
            isEditingCredit = false;
        }
    }

    async function recalculateAllCosts() {
        const ok = await customConfirm(
            'ระบบจะคำนวณค่าใช้จ่ายย้อนหลังทั้งหมดใหม่ตามอัตราค่าบริการ Google Gemini ล่าสุด (รวม Thinking Tokens และ Cached Input)',
            {
                title: 'ยืนยันการคำนวณต้นทุนย้อนหลัง',
                detail: stats?.total_requests
                    ? `ครอบคลุมประวัติการเรียกใช้งานทั้งหมด ${formatNumber(stats.total_requests)} รายการในฐานข้อมูล`
                    : 'การคำนวณอาจใช้เวลาสักครู่ขึ้นอยู่กับจำนวนรายการในฐานข้อมูล',
                confirmText: 'คำนวณราคาใหม่',
                cancelText: 'ยกเลิก',
                variant: 'warning'
            }
        );
        if (!ok) return;

        recalculating = true;
        try {
            const token = localStorage.getItem('jwt_token');
            const res = await fetch('/api/admin/usage/recalculate', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok && data.success) {
                toast(`คำนวณค่าใช้จ่ายใหม่สำเร็จ (${formatNumber(data.updated_rows)} รายการ)`, 'success');
                await fetchStats();
            } else {
                toast(data.error || 'ไม่สามารถคำนวณค่าใช้จ่ายใหม่ได้', 'error');
            }
        } catch (e) {
            toast('เกิดข้อผิดพลาดระหว่างคำนวณค่าใช้จ่ายใหม่', 'error');
        } finally {
            recalculating = false;
        }
    }

    onMount(() => {
        fetchStats();
    });

    onDestroy(() => {
        if (rafId) cancelAnimationFrame(rafId);
    });

    function formatNumber(num) {
        if (num === undefined || num === null || isNaN(Number(num))) return '0';
        return Math.round(Number(num)).toLocaleString('en-US');
    }

    function formatDecimal(num, digits = 2) {
        if (num === undefined || num === null || isNaN(Number(num))) return '0.00';
        return Number(num).toLocaleString('en-US', {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits
        });
    }

    function formatCurrency(amount) {
        if (amount === undefined || amount === null || isNaN(Number(amount))) return '0.0000';
        const n = Number(amount);
        return n > 0 && n < 0.01 ? n.toFixed(6) : n.toFixed(4);
    }

    $: usdToThb = (stats && stats.usd_to_thb_rate) ? Number(stats.usd_to_thb_rate) : 35;

    function formatCurrencyTHB(amountUSD) {
        if (amountUSD === undefined || amountUSD === null || isNaN(Number(amountUSD))) return '0.00';
        return (Number(amountUSD) * usdToThb).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    $: periodCostUsd = (stats && stats.total_cost_usd != null && !isNaN(Number(stats.total_cost_usd)))
        ? Number(stats.total_cost_usd) : 0;
    $: allTimeCostUsd = (stats && stats.all_time_cost_usd != null && !isNaN(Number(stats.all_time_cost_usd)))
        ? Number(stats.all_time_cost_usd) : periodCostUsd;
    $: allTimeCostThb = allTimeCostUsd * usdToThb;
    $: safeCreditThb = (creditThb != null && !isNaN(Number(creditThb))) ? Number(creditThb) : 0;
    $: remainingBalance = creditError || creditThb === null ? null : (safeCreditThb - allTimeCostThb);
    $: previewCreditNum = parseFloat(newCreditThb);
    $: previewRemaining = !isNaN(previewCreditNum) ? previewCreditNum - allTimeCostThb : null;

    $: if (stats) {
        animateKpis(
            Number(stats.total_tokens || 0),
            periodCostUsd,
            safeCreditThb,
            remainingBalance !== null ? remainingBalance : 0
        );
    }

    // Proportional Token Composition (only render segments > 0)
    $: promptTok = Number(stats?.total_prompt_tokens || 0);
    $: compTok = Number(stats?.total_completion_tokens || 0);
    $: thinkTok = Number(stats?.total_thinking_tokens || 0);
    $: tokenTotalSafe = Math.max(1, Number(stats?.total_tokens || 0));
    $: inPct = Math.min(100, (promptTok / tokenTotalSafe) * 100);
    $: outPct = Math.min(100, (compTok / tokenTotalSafe) * 100);
    $: thinkPct = Math.min(100, (thinkTok / tokenTotalSafe) * 100);

    // Budget Burn Meter %
    $: burnPct = remainingBalance === null
        ? 0
        : safeCreditThb > 0
            ? Math.min(100, (allTimeCostThb / safeCreditThb) * 100)
            : (allTimeCostThb > 0 ? 100 : 0);

    $: maxFeatureCost = Math.max(...((stats?.by_endpoint || []).map(i => Number(i.cost_usd || 0))), 0.000001);
    $: maxModelCost = Math.max(...((stats?.by_model || []).map(i => Number(i.cost_usd || 0))), 0.000001);
</script>

<div class="usage-dashboard" in:fade={{ duration: prefersReducedMotion() ? 0 : 160 }}>
    <!-- Header with Calm-At-Rest Spectra Automation Telemetry Emblem -->
    <header class="header-area">
        <div class="header-title-wrap">
            <div class="spectra-emblem" class:is-active={loading || recalculating} aria-hidden="true">
                <svg viewBox="0 0 48 48" fill="none">
                    <circle
                        cx="24"
                        cy="24"
                        r="20"
                        stroke="rgba(99, 102, 241, 0.35)"
                        stroke-width="1.5"
                        stroke-dasharray="5 5"
                        class="orbit-ring"
                    />
                    <path
                        d="M 24 6 A 18 18 0 0 1 42 24"
                        stroke="#06b6d4"
                        stroke-width="2"
                        stroke-linecap="round"
                        class="orbit-arc"
                    />
                    <polygon
                        points="24,12 34,18 34,30 24,36 14,30 14,18"
                        fill="rgba(99, 102, 241, 0.16)"
                        stroke="#a5b4fc"
                        stroke-width="1.6"
                    />
                    <polyline
                        points="17,24 20.5,24 22.5,19 25.5,29 27.5,24 31,24"
                        stroke="#34d399"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        class="pulse-wave"
                    />
                </svg>
            </div>
            <div>
                <div class="title-row">
                    <h2>Gemini API Usage &amp; Cost Dashboard</h2>
                    {#if lastUpdatedAt}
                        <span class="updated-pill">อัปเดต {lastUpdatedAt}</span>
                    {/if}
                </div>
                <p class="subtitle">
                    ติดตามปริมาณ Input / Output / Thinking Tokens และค่าใช้จ่ายจริงจาก Agent ทุกตัวในระบบ (อัตราแลกเปลี่ยน ฿{usdToThb}/USD)
                </p>
            </div>
        </div>

        <div class="header-actions">
            {#if highlightedModel}
                <button
                    type="button"
                    class="btn-filter-clear"
                    on:click={() => (highlightedModel = '')}
                    title="ล้างการกรองโมเดลบนกราฟ"
                >
                    <span>กรอง: {highlightedModel}</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" width="12" height="12" aria-hidden="true">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            {/if}

            <div class="filter-select-wrap">
                <CustomSelect
                    ariaLabel="กรองช่วงเวลา"
                    variant="compact"
                    size="sm"
                    options={TIME_FILTER_OPTIONS}
                    bind:value={timeFilter}
                    on:change={fetchStats}
                    minWidth="180px"
                />
            </div>

            <button
                type="button"
                class="btn-action"
                class:active={showPricingRef}
                aria-expanded={showPricingRef}
                on:click={() => (showPricingRef = !showPricingRef)}
                title="ดูอัตราค่าบริการโมเดลปัจจุบันที่ใช้คำนวณ"
            >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                </svg>
                <span>ตารางราคา</span>
            </button>

            <button
                type="button"
                class="btn-action btn-warning-subtle"
                on:click={recalculateAllCosts}
                disabled={recalculating || loading}
            >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class:spinning={recalculating} aria-hidden="true">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4"></path>
                </svg>
                <span>{recalculating ? 'กำลังคำนวณ...' : 'คำนวณราคาใหม่'}</span>
            </button>

            <button type="button" class="btn-action" on:click={fetchStats} disabled={loading}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class:spinning={loading} aria-hidden="true">
                    <polyline points="23 4 23 10 17 10"></polyline>
                    <polyline points="1 20 1 14 7 14"></polyline>
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                </svg>
                <span>รีเฟรช</span>
            </button>
        </div>
    </header>

    {#if showPricingRef && stats?.pricing_table}
        <div class="pricing-ref-panel glass-card" transition:slide={{ duration: prefersReducedMotion() ? 0 : 200, easing: cubicOut }}>
            <div class="pricing-ref-head">
                <strong>อัตราค่าบริการ Google Gemini API ที่ใช้คำนวณ (USD / 1M Tokens)</strong>
                <span class="pricing-note">Thinking Tokens ถูกคิดราคาเท่า Output Token เต็มอัตรา และ Cached Input คิด 10% ตามมาตรฐาน Google AI</span>
            </div>
            <div class="pricing-grid">
                {#each stats.pricing_table as p}
                    <div class="pricing-chip">
                        <span class="p-model">{p.model}</span>
                        <span class="p-rates">
                            In <strong>${p.input_per_1m.toFixed(2)}</strong> · Out/Think <strong>${p.output_per_1m.toFixed(2)}</strong>
                            {#if p.long_ctx_input_per_1m > p.input_per_1m}
                                <span class="p-tier">(&gt;200K: ${p.long_ctx_input_per_1m.toFixed(2)}/${p.long_ctx_output_per_1m.toFixed(2)})</span>
                            {/if}
                        </span>
                    </div>
                {/each}
            </div>
        </div>
    {/if}

    {#if loading && !stats}
        <div class="loading-state">
            <div class="spinner"></div>
            <p>กำลังโหลดข้อมูลสถิติ Token Usage...</p>
        </div>
    {:else if error && !stats}
        <div class="error-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <p>{error}</p>
            <button type="button" class="btn-sm btn-primary" on:click={fetchStats}>ลองใหม่</button>
        </div>
    {:else if stats}
        <!-- 4 KPI Telemetry Cards (Calm at rest, subtle spotlight & icon motion on hover) -->
        <div class="overview-cards">
            <!-- Card 1: Total Tokens + Live Composition Spectrum Bar -->
            <div
                class="card glass-card total-card"
                role="region"
                aria-label="จำนวนโทเคนที่ใช้ทั้งหมด"
                on:mousemove={handleCardPointerMove}
            >
                <div class="card-header">
                    <div class="card-label">Total Tokens Consumed</div>
                    <div class="card-icon blue" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                            <circle cx="12" cy="12" r="9" stroke-dasharray="4 3" class="ico-orbit" />
                            <circle cx="12" cy="12" r="3.2" fill="currentColor" fill-opacity="0.22" />
                            <path d="M12 3v3M12 18v3M3 12h3M18 12h3" stroke-linecap="round" />
                        </svg>
                    </div>
                </div>
                <div class="card-value">{formatNumber(animTotalTokens)}</div>

                <div class="spectrum-bar" title={`Input ${inPct.toFixed(1)}% · Output ${outPct.toFixed(1)}% · Thinking ${thinkPct.toFixed(1)}%`}>
                    <div class="seg-stack">
                        {#if promptTok > 0}
                            <span class="seg-fill in" style="flex: {inPct}"></span>
                        {/if}
                        {#if compTok > 0}
                            <span class="seg-fill out" style="flex: {outPct}"></span>
                        {/if}
                        {#if thinkTok > 0}
                            <span class="seg-fill think" style="flex: {thinkPct}"></span>
                        {/if}
                    </div>
                </div>

                <div class="token-breakdown">
                    <span><i class="dot in" aria-hidden="true"></i>In <strong>{formatNumber(promptTok)}</strong></span>
                    <span><i class="dot out" aria-hidden="true"></i>Out <strong>{formatNumber(compTok)}</strong></span>
                    <span class="think-tag"><i class="dot think" aria-hidden="true"></i>Think <strong>{formatNumber(thinkTok)}</strong></span>
                </div>
            </div>

            <!-- Card 2: Estimated Cost USD -->
            <div
                class="card glass-card cost-card"
                role="region"
                aria-label="ประมาณการค่าใช้จ่าย"
                on:mousemove={handleCardPointerMove}
            >
                <div class="card-header">
                    <div class="card-label">Estimated Cost (USD)</div>
                    <div class="card-icon green" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                            <path d="M4.5 16.5A9 9 0 1 1 19.5 16.5" stroke-linecap="round" />
                            <line x1="12" y1="7" x2="12" y2="17" stroke-linecap="round" />
                            <path d="M14.8 9.2c0-1.1-1.2-1.8-2.8-1.8s-2.8.7-2.8 1.8c0 2.4 5.6 1.4 5.6 4.2 0 1.2-1.2 2-2.8 2s-2.8-.8-2.8-2" stroke-linecap="round" />
                        </svg>
                    </div>
                </div>
                <div class="card-value highlight">${formatCurrency(animCostUsd)}</div>
                <div class="card-sub">
                    <span>≈ ฿{formatCurrencyTHB(periodCostUsd)}</span>
                    <span class="req-pill">{formatNumber(stats.total_requests)} ครั้ง</span>
                </div>
            </div>

            <!-- Card 3: Top-up Credit THB -->
            <div
                class="card glass-card credit-card"
                role="region"
                aria-label="เครดิตสะสม"
                on:mousemove={handleCardPointerMove}
            >
                <div class="card-header">
                    <div class="card-label">Cumulative Credit (THB)</div>
                    <div class="card-icon purple" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                            <rect x="2.5" y="6" width="19" height="12" rx="3" />
                            <line x1="6.5" y1="14" x2="6.5" y2="11" stroke-linecap="round" class="ico-bar b1" />
                            <line x1="10.5" y1="14" x2="10.5" y2="9.5" stroke-linecap="round" class="ico-bar b2" />
                            <line x1="14.5" y1="14" x2="14.5" y2="10.5" stroke-linecap="round" class="ico-bar b3" />
                            <circle cx="18" cy="12" r="1.2" fill="currentColor" />
                        </svg>
                    </div>
                </div>
                {#if isEditingCredit}
                    <form class="credit-edit-form" on:submit|preventDefault={updateCredit}>
                        <label for="credit-thb-input" class="credit-edit-hint">เครดิตสะสมทั้งหมด (THB)</label>
                        <div class="credit-edit">
                            <input
                                id="credit-thb-input"
                                type="number"
                                bind:value={newCreditThb}
                                on:keydown={handleCreditKeydown}
                                placeholder="เช่น 1000"
                                step="10"
                                min="0"
                                disabled={savingCredit}
                            />
                            <button type="submit" class="btn-sm btn-primary" disabled={savingCredit}>
                                {savingCredit ? '...' : 'บันทึก'}
                            </button>
                            <button type="button" on:click={() => (isEditingCredit = false)} class="btn-sm btn-secondary" disabled={savingCredit}>
                                ยกเลิก
                            </button>
                        </div>
                        {#if previewRemaining !== null}
                            <div class="credit-preview">
                                ยอดคงเหลือใหม่: <strong class:danger={previewRemaining < 0}>฿{formatDecimal(previewRemaining, 2)}</strong>
                            </div>
                        {/if}
                    </form>
                {:else if creditError}
                    <div class="card-value muted">—</div>
                    <div class="card-sub">
                        <span>โหลดเครดิตไม่สำเร็จ</span>
                        <button type="button" on:click={fetchStats} class="btn-text">ลองใหม่</button>
                    </div>
                {:else}
                    <div class="card-value highlight">฿{formatNumber(animCreditThb)}</div>
                    <div class="card-sub">
                        <span>ใช้สะสม: ฿{formatCurrencyTHB(allTimeCostUsd)}</span>
                        <button
                            type="button"
                            on:click={() => { newCreditThb = safeCreditThb; isEditingCredit = true; }}
                            class="btn-text"
                        >
                            แก้ไขเครดิต
                        </button>
                    </div>
                {/if}
            </div>

            <!-- Card 4: Remaining Balance + Burn Rate Meter -->
            <div
                class="card glass-card balance-card"
                class:deficit={remainingBalance !== null && remainingBalance < 0}
                role="region"
                aria-label="ยอดเงินคงเหลือ"
                on:mousemove={handleCardPointerMove}
            >
                <div class="card-header">
                    <div class="card-label">Remaining Balance (THB)</div>
                    <div
                        class="card-icon"
                        class:warning={remainingBalance !== null && remainingBalance < 0}
                        class:amber={remainingBalance === null || remainingBalance >= 0}
                        aria-hidden="true"
                    >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                            <path d="M12 3l7.5 3v6c0 4.5-3.2 7.8-7.5 9-4.3-1.2-7.5-4.5-7.5-9V6L12 3z" />
                            {#if remainingBalance !== null && remainingBalance < 0}
                                <line x1="12" y1="8.5" x2="12" y2="12.5" stroke-linecap="round" />
                                <circle cx="12" cy="15.5" r="0.9" fill="currentColor" />
                            {:else}
                                <polyline points="9 12.2 11.2 14.4 15.5 9.8" stroke-linecap="round" stroke-linejoin="round" />
                            {/if}
                        </svg>
                    </div>
                </div>
                {#if remainingBalance === null}
                    <div class="card-value muted">—</div>
                    <div class="card-sub">
                        <span>รอข้อมูลเครดิตสะสม</span>
                        <span>All-time</span>
                    </div>
                {:else}
                    <div class="card-value" class:danger={remainingBalance < 0}>
                        ฿{formatDecimal(animRemainingThb, 2)}
                    </div>
                    <div class="burn-meter-wrap" title={`ใช้งบไปแล้ว ${burnPct.toFixed(0)}% ของเครดิตสะสม`}>
                        <div class="burn-track">
                            <div
                                class="burn-fill"
                                class:over={remainingBalance < 0}
                                style="transform: scaleX({burnPct / 100});"
                            ></div>
                        </div>
                        <div class="card-sub">
                            <span>{remainingBalance < 0 ? 'เกินงบเครดิตที่ตั้งไว้' : `ใช้ไปแล้ว ${burnPct.toFixed(0)}%`}</span>
                            <span>All-time</span>
                        </div>
                    </div>
                {/if}
            </div>
        </div>

        <!-- Interactive Cross-Highlighted Charts -->
        {#if stats.model_chart_data && stats.model_chart_data.length > 0}
            <div class="charts-row">
                <LineChart
                    title="Input Tokens per model"
                    data={stats.model_chart_data.map(d => ({ time_group: d.time_group, model_name: d.model_name, value: d.prompt_tokens }))}
                    {timeFilter}
                    formatValue={formatNumber}
                    {highlightedModel}
                    on:toggleModel={handleToggleModel}
                />

                <LineChart
                    title="Output + Thinking Tokens per model"
                    data={stats.model_chart_data.map(d => ({ time_group: d.time_group, model_name: d.model_name, value: d.completion_tokens }))}
                    {timeFilter}
                    formatValue={formatNumber}
                    {highlightedModel}
                    on:toggleModel={handleToggleModel}
                />

                <LineChart
                    title="Requests per model"
                    data={stats.model_chart_data.map(d => ({ time_group: d.time_group, model_name: d.model_name, value: d.requests }))}
                    {timeFilter}
                    formatValue={formatNumber}
                    {highlightedModel}
                    on:toggleModel={handleToggleModel}
                />
            </div>
        {/if}

        <div class="tables-container">
            <div class="table-section glass-card feature-usage">
                <div class="section-head">
                    <h3>การใช้งานแยกตามฟีเจอร์ / Agent</h3>
                    <span class="section-count">{(stats.by_endpoint || []).length} รายการ</span>
                </div>
                {#if stats.by_endpoint && stats.by_endpoint.length > 0}
                    <div class="table-responsive">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Feature / Agent</th>
                                    <th class="num">Requests</th>
                                    <th class="num">Tokens</th>
                                    <th class="num">Cost (USD)</th>
                                    <th class="num">Cost (THB)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each stats.by_endpoint as item}
                                    {@const share = Math.max(0.03, Number(item.cost_usd || 0) / maxFeatureCost)}
                                    <tr>
                                        <td>
                                            <div class="cell-with-bar">
                                                <span class="badge feature-badge">{item.endpoint}</span>
                                                <div class="micro-bar-track">
                                                    <span class="micro-bar-fill indigo" style="transform: scaleX({share});"></span>
                                                </div>
                                            </div>
                                        </td>
                                        <td class="num">{formatNumber(item.requests)}</td>
                                        <td class="num" title={`In: ${formatNumber(item.prompt_tokens)} | Out: ${formatNumber(item.completion_tokens)} | Think: ${formatNumber(item.thinking_tokens)}`}>
                                            {formatNumber(item.tokens)}
                                        </td>
                                        <td class="num cost-cell">${formatCurrency(item.cost_usd)}</td>
                                        <td class="num cost-cell-thb">฿{formatCurrencyTHB(item.cost_usd)}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {:else}
                    <div class="empty-state">ยังไม่มีข้อมูลการใช้งานแยกตามฟีเจอร์ในช่วงเวลานี้</div>
                {/if}
            </div>

            <div class="table-section glass-card model-usage">
                <div class="section-head">
                    <h3>การใช้งานแยกตามโมเดล AI</h3>
                    <span class="section-hint">คลิกชื่อโมเดลเพื่อกรองกราฟด้านบน</span>
                </div>
                {#if stats.by_model && stats.by_model.length > 0}
                    <div class="table-responsive">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>AI Model</th>
                                    <th class="num">Reqs</th>
                                    <th class="num">Input</th>
                                    <th class="num">Out + Think</th>
                                    <th class="num">Cost (USD)</th>
                                    <th class="num">Cost (THB)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each stats.by_model as item}
                                    {@const share = Math.max(0.03, Number(item.cost_usd || 0) / maxModelCost)}
                                    <tr class:selected-row={highlightedModel === item.model}>
                                        <td>
                                            <div class="cell-with-bar">
                                                <button
                                                    type="button"
                                                    class="model-filter-btn badge model-badge"
                                                    class:pro={item.model.includes('pro')}
                                                    class:flash={item.model.includes('flash')}
                                                    class:is-active={highlightedModel === item.model}
                                                    aria-pressed={highlightedModel === item.model}
                                                    on:click={() => handleToggleModel(item.model)}
                                                >
                                                    {item.model}
                                                </button>
                                                <div class="micro-bar-track">
                                                    <span class="micro-bar-fill cyan" style="transform: scaleX({share});"></span>
                                                </div>
                                            </div>
                                        </td>
                                        <td class="num">{formatNumber(item.requests)}</td>
                                        <td class="num">{formatNumber(item.prompt_tokens)}</td>
                                        <td class="num" title={`Output: ${formatNumber(item.completion_tokens)} | Thinking: ${formatNumber(item.thinking_tokens)}`}>
                                            {formatNumber((item.completion_tokens || 0) + (item.thinking_tokens || 0))}
                                        </td>
                                        <td class="num cost-cell">${formatCurrency(item.cost_usd)}</td>
                                        <td class="num cost-cell-thb">฿{formatCurrencyTHB(item.cost_usd)}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {:else}
                    <div class="empty-state">
                        <p>ยังไม่มีข้อมูลการใช้งานโมเดลในช่วงเวลานี้</p>
                    </div>
                {/if}
            </div>
        </div>

        <!-- Activity History Section -->
        <div class="tables-container">
            <div class="table-section glass-card doc-history" style="width: 100%;">
                <div class="section-head">
                    <h3>ประวัติการสแกนและการเรียกใช้ AI Agent</h3>
                    <span class="section-count">ล่าสุด {(stats.document_history || []).length} รายการ</span>
                </div>
                {#if stats.document_history && stats.document_history.length > 0}
                    <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>เวลา</th>
                                    <th>งาน / เอกสาร</th>
                                    <th>ระบบ / Agent</th>
                                    <th>โมเดล</th>
                                    <th class="num">Tokens</th>
                                    <th class="num">Cost (USD)</th>
                                    <th class="num">Cost (THB)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each stats.document_history as doc}
                                    <tr>
                                        <td class="time-cell">{doc.date ? new Date(doc.date).toLocaleString('th-TH') : '-'}</td>
                                        <td class="doc-name" title={doc.filename}>{doc.filename}</td>
                                        <td><span class="badge feature-badge">{doc.endpoint}</span></td>
                                        <td>
                                            <span
                                                class="badge model-badge"
                                                class:pro={(doc.model || '').includes('pro')}
                                                class:flash={(doc.model || '').includes('flash')}
                                            >
                                                {doc.model}
                                            </span>
                                        </td>
                                        <td class="num">{formatNumber(doc.tokens)}</td>
                                        <td class="num cost-cell">${formatCurrency(doc.cost_usd)}</td>
                                        <td class="num cost-cell-thb">฿{formatCurrencyTHB(doc.cost_usd)}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {:else}
                    <div class="empty-state">
                        <p>ไม่มีประวัติการใช้งานในช่วงเวลานี้</p>
                    </div>
                {/if}
            </div>
        </div>
    {/if}
</div>

<style>
    .usage-dashboard {
        padding: 24px;
        height: 100%;
        overflow-y: auto;
        color: var(--text-main, #f8fafc);
    }

    /* ── Header + Calm-at-Rest Spectra Emblem ── */
    .header-area {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 20px;
    }

    .header-title-wrap {
        display: flex;
        align-items: center;
        gap: 14px;
    }

    .spectra-emblem {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        background-color: rgba(18, 20, 28, 0.85);
        border: 1px solid rgba(99, 102, 241, 0.28);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .spectra-emblem:hover,
    .spectra-emblem.is-active {
        border-color: rgba(99, 102, 241, 0.6);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.22);
    }

    .spectra-emblem svg {
        width: 40px;
        height: 40px;
    }

    .orbit-ring,
    .orbit-arc {
        transform-origin: 24px 24px;
    }

    /* Animate emblem rings ONLY when loading/recalculating or hovered */
    .spectra-emblem:hover .orbit-ring,
    .spectra-emblem.is-active .orbit-ring {
        animation: emblemSpin 12s linear infinite;
    }

    .spectra-emblem:hover .orbit-arc,
    .spectra-emblem.is-active .orbit-arc {
        animation: emblemSpin 3.6s linear infinite reverse;
    }

    .spectra-emblem:hover .pulse-wave,
    .spectra-emblem.is-active .pulse-wave {
        stroke-dasharray: 28;
        animation: waveFlow 1.8s ease-in-out infinite;
    }

    @keyframes emblemSpin {
        to { transform: rotate(360deg); }
    }

    @keyframes waveFlow {
        0%, 100% { stroke-dashoffset: 0; opacity: 1; }
        50% { stroke-dashoffset: 10; opacity: 0.65; }
    }

    .title-row {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        margin-bottom: 4px;
    }

    .header-area h2 {
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-size: 22px;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
    }

    .updated-pill {
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 20px;
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.1);
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-size: 11px;
        font-weight: 500;
        color: #94a3b8;
        font-variant-numeric: tabular-nums;
    }

    .subtitle {
        color: var(--text-muted, #94a3b8);
        font-size: 13px;
        margin: 0;
    }

    .header-actions {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
    }

    .filter-select-wrap {
        width: 190px;
    }

    .btn-filter-clear {
        height: 34px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 0 10px;
        border-radius: 8px;
        border: 1px solid rgba(99, 102, 241, 0.48);
        background-color: rgba(99, 102, 241, 0.18);
        color: #e0e7ff;
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
    }

    .btn-filter-clear:hover {
        background-color: rgba(99, 102, 241, 0.3);
    }

    .btn-action {
        height: 34px;
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 0 12px;
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        color: var(--text-main, #f8fafc);
        font-size: 12.5px;
        font-weight: 500;
        cursor: pointer;
        transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    }

    .btn-action:hover:not(:disabled),
    .btn-action.active {
        background-color: rgba(99, 102, 241, 0.16);
        border-color: rgba(99, 102, 241, 0.45);
    }

    .btn-action.btn-warning-subtle {
        border-color: rgba(245, 158, 11, 0.35);
        background-color: rgba(245, 158, 11, 0.08);
        color: #fcd34d;
    }

    .btn-action.btn-warning-subtle:hover:not(:disabled) {
        background-color: rgba(245, 158, 11, 0.2);
        border-color: rgba(245, 158, 11, 0.6);
        color: #fef3c7;
    }

    .btn-action:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    .btn-action svg {
        width: 14px;
        height: 14px;
    }

    .spinning {
        animation: spin 0.9s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* ── Pricing Reference Drawer ── */
    .pricing-ref-panel {
        background-color: rgba(18, 20, 28, 0.82);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .pricing-ref-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 12px;
        flex-wrap: wrap;
        font-size: 13px;
    }

    .pricing-note {
        font-size: 12px;
        color: #94a3b8;
    }

    .pricing-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }

    .pricing-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border-radius: 8px;
        background-color: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        font-size: 12px;
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-variant-numeric: tabular-nums;
    }

    .p-model { font-weight: 600; color: #c7d2fe; }
    .p-rates { color: #cbd5e1; }
    .p-tier { color: #94a3b8; margin-left: 4px; }

    /* ── KPI Cards (Flat at rest, subtle spotlight & icon motion on hover) ── */
    .overview-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 16px;
        margin-bottom: 20px;
    }

    .card {
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
        padding: 20px;
        border-radius: 12px;
        background-color: rgba(18, 20, 28, 0.72);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        transition: border-color 0.2s ease;
        --spot-color: rgba(99, 102, 241, 0.12);
    }

    .card::before {
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(240px circle at var(--mx, 50%) var(--my, 0%), var(--spot-color), transparent 72%);
        opacity: 0;
        transition: opacity 0.25s ease;
        pointer-events: none;
    }

    .card:hover::before {
        opacity: 1;
    }

    .card:hover {
        border-color: rgba(255, 255, 255, 0.16);
    }

    .card.total-card { --spot-color: rgba(59, 130, 246, 0.14); }
    .card.cost-card { --spot-color: rgba(16, 185, 129, 0.14); }
    .card.credit-card { --spot-color: rgba(168, 85, 247, 0.14); }
    .card.balance-card { --spot-color: rgba(245, 158, 11, 0.14); }
    .card.balance-card.deficit {
        border-color: rgba(244, 63, 94, 0.38);
        --spot-color: rgba(244, 63, 94, 0.14);
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }

    .card-label {
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #94a3b8;
    }

    .card-icon {
        width: 38px;
        height: 38px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .card:hover .card-icon {
        transform: scale(1.06);
    }

    .card-icon svg { width: 20px; height: 20px; }
    .card-icon.blue { background-color: rgba(59, 130, 246, 0.14); color: #60a5fa; }
    .card-icon.green { background-color: rgba(16, 185, 129, 0.14); color: #34d399; }
    .card-icon.purple { background-color: rgba(168, 85, 247, 0.14); color: #c084fc; }
    .card-icon.amber { background-color: rgba(245, 158, 11, 0.14); color: #fbbf24; }
    .card-icon.warning { background-color: rgba(244, 63, 94, 0.16); color: #fb7185; }

    .ico-orbit {
        transform-origin: 12px 12px;
    }

    .card:hover .ico-orbit {
        animation: emblemSpin 9s linear infinite;
    }

    .card:hover .ico-bar.b1 { animation: cellLevel 0.55s cubic-bezier(0.16, 1, 0.3, 1) infinite alternate; }
    .card:hover .ico-bar.b2 { animation: cellLevel 0.55s 0.12s cubic-bezier(0.16, 1, 0.3, 1) infinite alternate; }
    .card:hover .ico-bar.b3 { animation: cellLevel 0.55s 0.24s cubic-bezier(0.16, 1, 0.3, 1) infinite alternate; }

    @keyframes cellLevel {
        from { transform: scaleY(0.78); transform-origin: 0 14px; }
        to { transform: scaleY(1.12); transform-origin: 0 14px; }
    }

    .card-value {
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-size: 28px;
        font-weight: 700;
        color: #f8fafc;
        font-variant-numeric: tabular-nums;
        line-height: 1.15;
    }

    .card-value.highlight { color: #34d399; }
    .card-value.danger { color: #fb7185; }
    .card-value.muted { color: #8494aa; }

    /* Token Composition Spectrum Bar */
    .spectrum-bar {
        width: 100%;
        height: 6px;
        border-radius: 20px;
        background-color: rgba(255, 255, 255, 0.06);
        overflow: hidden;
    }

    .seg-stack {
        display: flex;
        width: 100%;
        height: 100%;
        gap: 2px;
    }

    .seg-fill {
        height: 100%;
        border-radius: 20px;
        transition: flex 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .seg-fill.in { background-color: #06b6d4; }
    .seg-fill.out { background-color: #34d399; }
    .seg-fill.think { background-color: #a855f7; }

    .token-breakdown {
        display: flex;
        flex-wrap: wrap;
        gap: 6px 10px;
        font-size: 11.5px;
        color: #94a3b8;
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-variant-numeric: tabular-nums;
    }

    .token-breakdown span {
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }

    .dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        display: inline-block;
    }

    .dot.in { background-color: #06b6d4; }
    .dot.out { background-color: #34d399; }
    .dot.think { background-color: #a855f7; }

    .token-breakdown strong { color: #e2e8f0; }
    .think-tag strong { color: #d8b4fe; }

    /* Burn Meter */
    .burn-meter-wrap {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .burn-track {
        width: 100%;
        height: 6px;
        border-radius: 20px;
        background-color: rgba(255, 255, 255, 0.07);
        overflow: hidden;
    }

    .burn-fill {
        width: 100%;
        height: 100%;
        border-radius: 20px;
        background: linear-gradient(90deg, #10b981, #f59e0b);
        transform-origin: left;
        transition: transform 0.45s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .burn-fill.over {
        background: linear-gradient(90deg, #f59e0b, #f43f5e);
    }

    .card-sub {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        font-size: 12px;
        color: #94a3b8;
        font-variant-numeric: tabular-nums;
    }

    .req-pill {
        padding: 2px 8px;
        border-radius: 8px;
        background-color: rgba(255, 255, 255, 0.05);
        color: #cbd5e1;
        font-size: 11.5px;
    }

    .credit-edit-form {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .credit-edit-hint {
        font-size: 11.5px;
        color: #94a3b8;
    }

    .credit-edit {
        display: flex;
        gap: 6px;
        align-items: center;
    }

    .credit-edit input {
        flex: 1;
        min-width: 0;
        height: 34px;
        padding: 0 10px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        background-color: #0a0b12;
        color: #f8fafc;
        font-size: 13px;
    }

    .credit-preview {
        font-size: 11.5px;
        color: #94a3b8;
        font-variant-numeric: tabular-nums;
    }

    .credit-preview strong { color: #6ee7b7; }
    .credit-preview strong.danger { color: #fb7185; }

    .btn-sm {
        height: 34px;
        padding: 0 10px;
        border-radius: 8px;
        border: none;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
    }

    .btn-sm:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    .btn-primary {
        background: linear-gradient(135deg, #6366f1, #a855f7);
        color: #ffffff;
    }

    .btn-secondary {
        background-color: rgba(255, 255, 255, 0.08);
        color: #e2e8f0;
    }

    .btn-text {
        background-color: rgba(99, 102, 241, 0.14);
        border: 1px solid rgba(99, 102, 241, 0.35);
        border-radius: 8px;
        color: #c7d2fe;
        font-size: 11.5px;
        font-weight: 600;
        padding: 3px 9px;
        cursor: pointer;
        white-space: nowrap;
        transition: background-color 0.15s ease;
    }

    .btn-text:hover {
        background-color: rgba(99, 102, 241, 0.28);
    }

    .charts-row {
        display: flex;
        gap: 16px;
        margin-bottom: 20px;
        flex-wrap: wrap;
    }

    .tables-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr));
        gap: 16px;
        margin-bottom: 20px;
    }

    .table-section {
        background-color: rgba(18, 20, 28, 0.72);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 18px 20px;
    }

    .section-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 12px;
        margin-bottom: 14px;
    }

    .table-section h3 {
        font-size: 15px;
        font-weight: 600;
        color: #f8fafc;
        margin: 0;
    }

    .section-count,
    .section-hint {
        font-size: 11.5px;
        color: #8494aa;
    }

    .table-responsive {
        overflow-x: auto;
    }

    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    .data-table th {
        text-align: left;
        padding: 10px 10px;
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #94a3b8;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        white-space: nowrap;
    }

    .data-table td {
        padding: 10px 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        color: #e2e8f0;
        vertical-align: middle;
    }

    .data-table tbody tr {
        transition: background-color 0.14s ease;
    }

    .data-table tbody tr:hover {
        background-color: rgba(255, 255, 255, 0.03);
    }

    .selected-row {
        background-color: rgba(99, 102, 241, 0.14);
    }

    .cell-with-bar {
        display: flex;
        flex-direction: column;
        gap: 5px;
        align-items: flex-start;
    }

    .micro-bar-track {
        width: 100%;
        max-width: 150px;
        height: 3px;
        border-radius: 20px;
        background-color: rgba(255, 255, 255, 0.06);
        overflow: hidden;
    }

    .micro-bar-fill {
        display: block;
        width: 100%;
        height: 100%;
        border-radius: 20px;
        transform-origin: left;
        transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .micro-bar-fill.indigo { background: linear-gradient(90deg, #6366f1, #a855f7); }
    .micro-bar-fill.cyan { background: linear-gradient(90deg, #06b6d4, #6366f1); }

    .data-table th.num,
    .data-table td.num {
        text-align: right;
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }

    .badge {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 500;
        font-family: var(--font-en, 'Outfit', sans-serif);
    }

    .model-filter-btn {
        cursor: pointer;
        transition: filter 0.14s ease, box-shadow 0.14s ease;
    }

    .model-filter-btn:hover {
        filter: brightness(1.15);
    }

    .model-filter-btn.is-active {
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.6);
    }

    .feature-badge {
        background-color: rgba(99, 102, 241, 0.14);
        border: 1px solid rgba(99, 102, 241, 0.3);
        color: #c7d2fe;
    }

    .model-badge {
        background-color: rgba(148, 163, 184, 0.14);
        border: 1px solid rgba(148, 163, 184, 0.3);
        color: #e2e8f0;
    }

    .model-badge.pro {
        background-color: rgba(168, 85, 247, 0.16);
        border-color: rgba(168, 85, 247, 0.35);
        color: #e9d5ff;
    }

    .model-badge.flash {
        background-color: rgba(6, 182, 212, 0.14);
        border-color: rgba(6, 182, 212, 0.32);
        color: #a5f3fc;
    }

    .cost-cell { color: #6ee7b7; font-weight: 600; }
    .cost-cell-thb { color: #f8fafc; font-weight: 600; }
    .time-cell { color: #94a3b8; font-size: 12px; white-space: nowrap; }
    .doc-name { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .loading-state,
    .error-state,
    .empty-state {
        padding: 36px 20px;
        text-align: center;
        color: #94a3b8;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
    }

    .error-state svg { width: 32px; height: 32px; color: #fb7185; }

    .spinner {
        width: 28px;
        height: 28px;
        border: 3px solid rgba(255, 255, 255, 0.15);
        border-top-color: #6366f1;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }

    /* Keyboard Focus Rings */
    .usage-dashboard button:focus-visible,
    .usage-dashboard input:focus-visible {
        outline: 2px solid #6366f1;
        outline-offset: 2px;
    }

    @media (prefers-reduced-motion: reduce) {
        .orbit-ring,
        .orbit-arc,
        .pulse-wave,
        .ico-orbit,
        .ico-bar,
        .spinning,
        .spinner {
            animation: none !important;
        }
        .seg-fill,
        .burn-fill,
        .micro-bar-fill,
        .card-icon {
            transition: none !important;
        }
        .card:hover .card-icon {
            transform: none;
        }
        .card::before {
            display: none;
        }
    }

    @media (max-width: 768px) {
        .usage-dashboard { padding: 14px; }
    }
</style>
