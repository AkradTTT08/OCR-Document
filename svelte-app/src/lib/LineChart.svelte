<script>
    export let title = '';
    export let data = []; // Array of { time_group, model_name, value }
    export let formatValue = (v) => v;
    export let timeFilter = 'all';

    // Group by model
    $: models = [...new Set(data.map(d => d.model_name))];
    $: colors = {
        'gemini-3.1-pro': '#3b82f6',
        'gemini-3.1-flash': '#ec4899',
        'gemini-2.5-flash': '#06b6d4',
        'gemini-2.5-flash-lite': '#10b981',
        'default': '#a855f7'
    };
    
    let hoveredPoint = null;
    let tooltipX = 0;
    let tooltipY = 0;

    function handleMouseOver(event, model, time, val) {
        hoveredPoint = { model, time, val };
        tooltipX = event.clientX;
        tooltipY = event.clientY;
    }

    function handleMouseOut() {
        hoveredPoint = null;
    }
    
    // Fill gaps in timeGroups so X-axis is proportional
    $: timeGroups = (() => {
        const times = [...new Set(data.map(d => d.time_group))].sort();
        if (times.length < 2) return times;
        
        try {
            const first = new Date(times[0]);
            const last = new Date(times[times.length - 1]);
            if (!isNaN(first) && !isNaN(last) && (last - first) < 100 * 24 * 60 * 60 * 1000) {
                const filled = [];
                let current = new Date(first);
                while (current <= last) {
                    filled.push(current.toISOString());
                    if (timeFilter === 'yearly') current.setMonth(current.getMonth() + 1);
                    else if (timeFilter === 'daily') current.setHours(current.getHours() + 1);
                    else current.setDate(current.getDate() + 1);
                }
                // Merge and sort
                return [...new Set([...times, ...filled])].sort();
            }
        } catch(e) {}
        return times;
    })();
    
    $: maxValue = Math.max(...data.map(d => d.value), 10);
    
    // Convert a value to Y coordinate (0 at bottom, 100 at top)
    const getY = (val) => 100 - (val / maxValue) * 90;
    
    // Bar Chart coordinates
    $: numModels = models.length || 1;
    $: numTimes = timeGroups.length || 1;
    
    const getGroupWidth = () => 100 / numTimes;
    const getGroupX = (timeIdx) => timeIdx * getGroupWidth();
    
    const getBarWidth = () => {
        const gW = getGroupWidth();
        const padding = gW * 0.3; // 30% padding between groups
        return (gW - padding) / numModels;
    };
    
    const getBarX = (timeIdx, modelIdx) => {
        const gX = getGroupX(timeIdx);
        const gW = getGroupWidth();
        const padding = gW * 0.3;
        const availableW = gW - padding;
        const barW = availableW / numModels;
        return gX + (padding/2) + (modelIdx * barW);
    };

    $: bars = models.flatMap((model, mIdx) => {
        return timeGroups.map((t, tIdx) => {
            const point = data.find(d => d.time_group === t && d.model_name === model);
            const val = point ? point.value : 0;
            return {
                model,
                time: t,
                val,
                color: colors[model] || colors.default,
                x: getBarX(tIdx, mIdx),
                y: getY(val),
                width: getBarWidth(),
                height: 100 - getY(val)
            };
        });
    });
    
    function formatLabel(t) {
        const d = new Date(t);
        if (timeFilter === 'yearly') return d.toLocaleDateString('en-US', { month: 'short' });
        if (timeFilter === 'monthly') return `${d.getDate()} ${d.toLocaleDateString('en-US', { month: 'short' })}`;
        if (timeFilter === 'daily') return `${d.getHours()}:00`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
</script>

<div class="line-chart-card glass-card">
    <div class="chart-header">
        <h4>{title}</h4>
        <span class="max-value">{formatValue(maxValue)}</span>
    </div>
    
    <div class="chart-body">
        {#if data.length === 0}
            <div class="empty">No data</div>
        {:else}
            <svg class="chart-svg" viewBox="0 -10 100 120" preserveAspectRatio="none" style="width: 100%; height: 100%;">
                <!-- Grid lines -->
                <line x1="0" y1="10" x2="100" y2="10" class="grid-line" />
                <line x1="0" y1="55" x2="100" y2="55" class="grid-line" />
                <line x1="0" y1="100" x2="100" y2="100" class="grid-line" />
                
                <!-- Bars -->
                {#each bars as bar}
                    {#if bar.val > 0}
                        <rect 
                            x={bar.x}
                            y={bar.y}
                            width={bar.width}
                            height={Math.max(bar.height, 1)}
                            fill={bar.color}
                            rx={bar.width > 2 ? "1" : "0"}
                            class="data-bar"
                            on:mouseover={(e) => handleMouseOver(e, bar.model, bar.time, bar.val)}
                            on:mouseout={handleMouseOut}
                            on:mousemove={(e) => { tooltipX = e.clientX; tooltipY = e.clientY; }}
                        />
                    {/if}
                {/each}
            </svg>
            
            <div class="x-axis">
                <span class="x-label">{timeGroups.length > 0 ? formatLabel(timeGroups[0]) : ''}</span>
                <span class="x-label">{timeGroups.length > 1 ? formatLabel(timeGroups[Math.floor(timeGroups.length/2)]) : ''}</span>
                <span class="x-label">{timeGroups.length > 2 ? formatLabel(timeGroups[timeGroups.length-1]) : ''}</span>
            </div>
        {/if}
    </div>
    
    <div class="chart-legend">
        {#each models as model}
            <div class="legend-item">
                <span class="legend-color" style="background-color: {colors[model] || colors.default}"></span>
                <span class="legend-text">{model}</span>
            </div>
        {/each}
    </div>
</div>

{#if hoveredPoint}
    <div class="custom-tooltip" style="left: {tooltipX + 15}px; top: {tooltipY + 15}px; border-color: {colors[hoveredPoint.model] || colors.default}">
        <div class="tooltip-time">{formatLabel(hoveredPoint.time)}</div>
        <div class="tooltip-model">{hoveredPoint.model}</div>
        <div class="tooltip-value">{formatValue(hoveredPoint.val)}</div>
    </div>
{/if}

<style>
    .line-chart-card {
        background: rgba(20, 20, 25, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        flex: 1;
        min-width: 250px;
    }
    
    .chart-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .chart-header h4 {
        margin: 0;
        font-size: 13px;
        color: var(--text-muted);
        font-weight: 500;
    }
    
    .max-value {
        font-size: 11px;
        color: var(--text-muted);
        font-family: var(--font-en);
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
        stroke: rgba(255, 255, 255, 0.1);
        stroke-width: 0.5;
        stroke-dasharray: 2 2;
    }
    
    .x-axis {
        display: flex;
        justify-content: space-between;
        margin-top: 8px;
    }
    
    .x-label {
        font-size: 10px;
        color: var(--text-muted);
        font-family: var(--font-en);
    }
    
    .chart-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-top: auto;
    }
    
    .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    .legend-color {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    
    .legend-text {
        font-size: 11px;
        color: var(--text-main);
    }
    
    .empty {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: var(--text-muted);
        font-size: 12px;
    }
    
    .data-bar {
        cursor: crosshair;
        transition: fill 0.2s ease, opacity 0.2s ease;
    }
    .data-bar:hover {
        opacity: 0.8;
    }
    
    .custom-tooltip {
        position: fixed;
        background: rgba(15, 20, 35, 0.95);
        border-left: 4px solid;
        padding: 10px 14px;
        border-radius: 6px;
        pointer-events: none;
        z-index: 9999;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
        color: white;
        min-width: 120px;
    }
    
    .tooltip-time {
        font-size: 11px;
        color: #9ca3af;
        margin-bottom: 4px;
    }
    
    .tooltip-model {
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 2px;
    }
    
    .tooltip-value {
        font-size: 16px;
        font-weight: 700;
        font-family: var(--font-en);
        color: #10b981;
    }
</style>
