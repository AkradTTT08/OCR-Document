<script>
    import { createEventDispatcher } from 'svelte';

    export let title = '';
    export let data = []; // Array of { time_group, model_name, value }
    export let formatValue = (v) => v;
    export let timeFilter = 'all';
    export let highlightedModel = '';

    const dispatch = createEventDispatcher();

    const MODEL_COLORS = {
        'gemini-3.1-pro': '#3b82f6',
        'gemini-3.1-pro-preview': '#818cf8',
        'gemini-3.1-flash': '#ec4899',
        'gemini-2.5-pro': '#a855f7',
        'gemini-2.5-flash': '#06b6d4',
        'gemini-2.5-flash-lite': '#10b981',
        'gemini-2.0-flash': '#f59e0b',
        'gemini-2.0-flash-lite': '#34d399',
        'default': '#94a3b8'
    };

    function getModelColor(model) {
        const key = String(model || '').toLowerCase();
        if (MODEL_COLORS[key]) return MODEL_COLORS[key];
        if (key.includes('3.1-pro-preview')) return MODEL_COLORS['gemini-3.1-pro-preview'];
        if (key.includes('3.1-pro')) return MODEL_COLORS['gemini-3.1-pro'];
        if (key.includes('2.5-pro')) return MODEL_COLORS['gemini-2.5-pro'];
        if (key.includes('2.5-flash-lite')) return MODEL_COLORS['gemini-2.5-flash-lite'];
        if (key.includes('2.5-flash')) return MODEL_COLORS['gemini-2.5-flash'];
        if (key.includes('2.0-flash')) return MODEL_COLORS['gemini-2.0-flash'];
        return MODEL_COLORS.default;
    }

    function pad2(n) {
        return String(n).padStart(2, '0');
    }

    function toBucketKey(rawTime) {
        if (!rawTime) return '';
        const s = String(rawTime);
        if (timeFilter === 'yearly') return s.slice(0, 7);
        if (timeFilter === 'daily') return s.slice(0, 13);
        return s.slice(0, 10);
    }

    function bucketToDate(key) {
        if (!key) return new Date(NaN);
        if (key.length === 7) return new Date(`${key}-01T00:00:00`);
        if (key.length === 13) return new Date(`${key}:00:00`);
        return new Date(`${key}T00:00:00`);
    }

    function dateToBucketKey(d) {
        const y = d.getFullYear();
        const m = pad2(d.getMonth() + 1);
        const day = pad2(d.getDate());
        const hr = pad2(d.getHours());
        if (timeFilter === 'yearly') return `${y}-${m}`;
        if (timeFilter === 'daily') return `${y}-${m}-${day}T${hr}`;
        return `${y}-${m}-${day}`;
    }

    $: normalizedMap = (() => {
        const map = new Map();
        for (const d of data || []) {
            const bk = toBucketKey(d.time_group);
            if (!bk) continue;
            const composite = `${bk}::${d.model_name}`;
            map.set(composite, (map.get(composite) || 0) + Number(d.value || 0));
        }
        return map;
    })();

    $: models = [...new Set((data || []).map(d => d.model_name))];

    $: activeData = highlightedModel
        ? (data || []).filter(d => d.model_name === highlightedModel)
        : (data || []);

    $: totalSum = activeData.reduce((acc, d) => acc + Number(d.value || 0), 0);

    let hoveredPoint = null;
    let tooltipX = 0;
    let tooltipY = 0;

    function clampTooltipPosition(rawX, rawY) {
        const estW = 190;
        const estH = 76;
        const pad = 12;
        const vw = typeof window !== 'undefined' ? window.innerWidth : 1280;
        const vh = typeof window !== 'undefined' ? window.innerHeight : 800;

        let x = rawX + 14;
        let y = rawY + 14;
        if (x + estW > vw - pad) x = Math.max(pad, rawX - estW - 12);
        if (y + estH > vh - pad) y = Math.max(pad, rawY - estH - 12);
        tooltipX = x;
        tooltipY = y;
    }

    function handleBarActivate(event, model, time, val) {
        hoveredPoint = { model, time, val };
        if (typeof event.clientX === 'number' && typeof event.clientY === 'number' && (event.clientX !== 0 || event.clientY !== 0)) {
            clampTooltipPosition(event.clientX, event.clientY);
        } else if (event.currentTarget && typeof event.currentTarget.getBoundingClientRect === 'function') {
            const rect = event.currentTarget.getBoundingClientRect();
            clampTooltipPosition(rect.left + rect.width / 2, rect.top);
        }
    }

    function handleMouseMove(event) {
        if (!hoveredPoint) return;
        clampTooltipPosition(event.clientX, event.clientY);
    }

    function handleBarDeactivate() {
        hoveredPoint = null;
    }

    function toggleModelHighlight(model) {
        dispatch('toggleModel', model);
    }

    $: timeGroups = (() => {
        const rawKeys = [...new Set((data || []).map(d => toBucketKey(d.time_group)).filter(Boolean))].sort();
        if (rawKeys.length < 2) return rawKeys;

        try {
            const first = bucketToDate(rawKeys[0]);
            const last = bucketToDate(rawKeys[rawKeys.length - 1]);
            const spanDays = (last - first) / (24 * 60 * 60 * 1000);
            if (!isNaN(first) && !isNaN(last) && spanDays >= 0 && spanDays <= 95) {
                const filled = [];
                const current = new Date(first);
                let guard = 0;
                while (current <= last && guard < 120) {
                    filled.push(dateToBucketKey(current));
                    if (timeFilter === 'yearly') current.setMonth(current.getMonth() + 1);
                    else if (timeFilter === 'daily') current.setHours(current.getHours() + 1);
                    else current.setDate(current.getDate() + 1);
                    guard++;
                }
                return [...new Set([...rawKeys, ...filled])].sort();
            }
        } catch (_) {}
        return rawKeys;
    })();

    $: maxValue = Math.max(...activeData.map(d => Number(d.value || 0)), 1);

    $: numModels = Math.max(1, models.length);
    $: numTimes = Math.max(1, timeGroups.length);

    $: bars = models.flatMap((model, mIdx) => {
        const gW = 100 / numTimes;
        const padding = gW * 0.24;
        const barW = Math.max(0.35, (gW - padding) / numModels);
        return timeGroups.map((bk, tIdx) => {
            const val = normalizedMap.get(`${bk}::${model}`) || 0;
            const y = 100 - (val / maxValue) * 90;
            const delayMs = Math.min(180, Math.round((tIdx / Math.max(1, numTimes)) * 160));
            return {
                id: `${bk}-${model}`,
                model,
                time: bk,
                val,
                color: getModelColor(model),
                x: tIdx * gW + (padding / 2) + (mIdx * barW),
                y,
                width: barW,
                height: Math.max(100 - y, 1.5),
                delayMs
            };
        });
    });

    function formatLabel(bk) {
        const d = bucketToDate(bk);
        if (isNaN(d)) return bk;
        if (timeFilter === 'yearly') return d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
        if (timeFilter === 'monthly') return `${d.getDate()} ${d.toLocaleDateString('en-US', { month: 'short' })}`;
        if (timeFilter === 'daily') return `${pad2(d.getHours())}:00`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
</script>

<div class="line-chart-card glass-card">
    <div class="chart-header">
        <h4>{title}</h4>
        <div class="chart-metrics">
            <span class="metric-total">Total {formatValue(totalSum)}</span>
            <span class="max-value">Peak {formatValue(maxValue)}</span>
        </div>
    </div>

    <div class="chart-body">
        {#if !data || data.length === 0}
            <div class="empty">ไม่มีข้อมูลในช่วงเวลานี้</div>
        {:else}
            {#key `${timeFilter}-${highlightedModel}`}
                <svg
                    class="chart-svg"
                    role="img"
                    aria-label={title}
                    viewBox="0 -6 100 112"
                    preserveAspectRatio="none"
                    style="width: 100%; height: 100%;"
                >
                    <line x1="0" y1="10" x2="100" y2="10" class="grid-line" />
                    <line x1="0" y1="55" x2="100" y2="55" class="grid-line" />
                    <line x1="0" y1="100" x2="100" y2="100" class="grid-line" />

                    {#each bars as bar (bar.id)}
                        {#if bar.val > 0}
                            {@const isDimmed = (highlightedModel && bar.model !== highlightedModel) || (hoveredPoint && (hoveredPoint.model !== bar.model || hoveredPoint.time !== bar.time))}
                            <rect
                                x={bar.x}
                                y={bar.y}
                                width={bar.width}
                                height={bar.height}
                                fill={bar.color}
                                rx={bar.width > 1.4 ? "0.6" : "0"}
                                tabindex="0"
                                role="graphics-symbol"
                                aria-label={`${bar.model} (${formatLabel(bar.time)}): ${formatValue(bar.val)}`}
                                class="data-bar"
                                class:dimmed={isDimmed}
                                style="animation-delay: {bar.delayMs}ms;"
                                on:mouseover={(e) => handleBarActivate(e, bar.model, bar.time, bar.val)}
                                on:focus={(e) => handleBarActivate(e, bar.model, bar.time, bar.val)}
                                on:mouseout={handleBarDeactivate}
                                on:blur={handleBarDeactivate}
                                on:mousemove={handleMouseMove}
                            />
                        {/if}
                    {/each}
                </svg>
            {/key}

            <div class="x-axis">
                <span class="x-label">{timeGroups.length > 0 ? formatLabel(timeGroups[0]) : ''}</span>
                <span class="x-label">{timeGroups.length > 2 ? formatLabel(timeGroups[Math.floor(timeGroups.length / 2)]) : ''}</span>
                <span class="x-label">{timeGroups.length > 1 ? formatLabel(timeGroups[timeGroups.length - 1]) : ''}</span>
            </div>
        {/if}
    </div>

    <div class="chart-legend" role="group" aria-label="คลิกเพื่อกรองตามโมเดล">
        {#each models as model}
            <button
                type="button"
                class="legend-item"
                class:active={highlightedModel === model}
                class:muted={highlightedModel && highlightedModel !== model}
                aria-pressed={highlightedModel === model}
                on:click={() => toggleModelHighlight(model)}
                title={highlightedModel === model ? 'คลิกอีกครั้งเพื่อแสดงทุกโมเดล' : `กรองแสดงเฉพาะ ${model}`}
            >
                <span class="legend-color" style="background-color: {getModelColor(model)}" aria-hidden="true"></span>
                <span class="legend-text">{model}</span>
            </button>
        {/each}
    </div>
</div>

{#if hoveredPoint}
    <div class="custom-tooltip" style="left: {tooltipX}px; top: {tooltipY}px; border-color: {getModelColor(hoveredPoint.model)}">
        <div class="tooltip-time">{formatLabel(hoveredPoint.time)}</div>
        <div class="tooltip-model">{hoveredPoint.model}</div>
        <div class="tooltip-value">{formatValue(hoveredPoint.val)}</div>
    </div>
{/if}

<style>
    .line-chart-card {
        background-color: rgba(18, 20, 28, 0.72);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        flex: 1;
        min-width: 260px;
        transition: border-color 0.2s ease;
    }

    .line-chart-card:hover {
        border-color: rgba(255, 255, 255, 0.15);
    }

    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 8px;
    }

    .chart-header h4 {
        margin: 0;
        font-size: 13px;
        color: #cbd5e1;
        font-weight: 600;
    }

    .chart-metrics {
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-variant-numeric: tabular-nums;
    }

    .metric-total {
        font-size: 12px;
        font-weight: 600;
        color: #e2e8f0;
    }

    .max-value {
        font-size: 11px;
        color: #8494aa;
    }

    .chart-body {
        height: 180px;
        position: relative;
        display: flex;
        flex-direction: column;
    }

    .chart-svg {
        width: 100%;
        flex: 1;
        overflow: hidden;
    }

    .grid-line {
        stroke: rgba(255, 255, 255, 0.08);
        stroke-width: 0.45;
        stroke-dasharray: 2 2;
    }

    .data-bar {
        opacity: 0.9;
        cursor: pointer;
        transform-box: fill-box;
        transform-origin: bottom;
        animation: barRise 0.36s cubic-bezier(0.16, 1, 0.3, 1) both;
        transition: opacity 0.15s ease, filter 0.15s ease;
        outline: none;
    }

    .data-bar.dimmed {
        opacity: 0.22;
    }

    .data-bar:hover,
    .data-bar:focus-visible {
        opacity: 1;
        filter: brightness(1.22);
    }

    @keyframes barRise {
        from { transform: scaleY(0); opacity: 0.3; }
        to { transform: scaleY(1); opacity: 0.9; }
    }

    .x-axis {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
    }

    .x-label {
        font-size: 10.5px;
        color: #8494aa;
        font-family: var(--font-en, 'Outfit', sans-serif);
    }

    .chart-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 6px 8px;
        margin-top: auto;
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 8px;
        border-radius: 8px;
        border: 1px solid transparent;
        background-color: transparent;
        cursor: pointer;
        transition: background-color 0.15s ease, border-color 0.15s ease, opacity 0.15s ease;
    }

    .legend-item:hover {
        background-color: rgba(255, 255, 255, 0.06);
    }

    .legend-item:focus-visible {
        outline: 2px solid #6366f1;
        outline-offset: 1px;
    }

    .legend-item.active {
        background-color: rgba(99, 102, 241, 0.16);
        border-color: rgba(99, 102, 241, 0.45);
    }

    .legend-item.muted {
        opacity: 0.45;
    }

    .legend-color {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .legend-text {
        font-size: 11px;
        color: #cbd5e1;
        font-family: var(--font-en, 'Outfit', sans-serif);
    }

    .empty {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #8494aa;
        font-size: 12.5px;
    }

    .custom-tooltip {
        position: fixed;
        z-index: var(--z-portal, 10500);
        background-color: #12141c;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        padding: 8px 11px;
        pointer-events: none;
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.65);
        font-family: var(--font-en, 'Outfit', sans-serif);
        font-variant-numeric: tabular-nums;
        max-width: 220px;
    }

    .tooltip-time {
        font-size: 11px;
        color: #94a3b8;
    }

    .tooltip-model {
        font-size: 12px;
        font-weight: 600;
        color: #f8fafc;
        margin-top: 2px;
    }

    .tooltip-value {
        font-size: 13px;
        font-weight: 700;
        color: #a5b4fc;
        margin-top: 2px;
    }

    @media (prefers-reduced-motion: reduce) {
        .data-bar {
            animation: none;
        }
    }
</style>
