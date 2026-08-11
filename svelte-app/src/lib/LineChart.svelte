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
    
    $: timeGroups = [...new Set(data.map(d => d.time_group))].sort();
    
    $: maxValue = Math.max(...data.map(d => d.value), 10);
    
    // Convert a value to Y coordinate (0 at bottom, 100 at top)
    const getY = (val) => 100 - (val / maxValue) * 90;
    
    // Convert index to X coordinate (0 at left, 100 at right)
    const getX = (idx) => timeGroups.length > 1 ? (idx / (timeGroups.length - 1)) * 100 : 50;

    $: lines = models.map(model => {
        let path = '';
        const modelData = timeGroups.map(t => {
            const point = data.find(d => d.time_group === t && d.model_name === model);
            return point ? point.value : 0;
        });
        
        modelData.forEach((val, i) => {
            const x = getX(i);
            const y = getY(val);
            if (i === 0) path += `${x},${y} `;
            else path += `${x},${y} `;
        });
        
        return {
            model,
            color: colors[model] || colors.default,
            path: path.trim()
        };
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
                
                <!-- Lines -->
                {#each lines as line}
                    <polyline points={line.path} fill="none" stroke={line.color} stroke-width="1.5" />
                    <!-- Points -->
                    {#each line.path.split(' ') as p, i}
                        {#if p}
                            <circle 
                                cx={p.split(',')[0]} 
                                cy={p.split(',')[1]} 
                                r="2.5" 
                                fill={line.color} 
                                title="{formatLabel(timeGroups[i])}: {formatValue(data.find(d => d.time_group === timeGroups[i] && d.model_name === line.model)?.value || 0)}"
                            />
                        {/if}
                    {/each}
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
</style>
