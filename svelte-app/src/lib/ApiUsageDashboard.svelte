<script>
    import { onMount } from 'svelte';
    import { fade } from 'svelte/transition';
    import { toast } from './toastStore.js';
    import LineChart from './LineChart.svelte';

    let stats = null;
    let loading = true;
    let error = null;
    let creditThb = 0;
    let isEditingCredit = false;
    let newCreditThb = '';

    let timeFilter = 'all';

    async function fetchStats() {
        loading = true;
        error = null;
        try {
            const token = localStorage.getItem('jwt_token');
            const res = await fetch(`http://127.0.0.1:5000/api/admin/usage?time_filter=${timeFilter}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();
            if (res.ok && data.success) {
                stats = data.stats;
            } else {
                error = data.error || 'Failed to load usage stats';
                toast(error, 'error');
            }
            
            // Fetch credit
            const creditRes = await fetch('http://127.0.0.1:5000/api/admin/credit', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (creditRes.ok) {
                const creditData = await creditRes.json();
                if (creditData.success) creditThb = creditData.credit_thb;
            }
        } catch (e) {
            error = 'Network error loading stats';
            toast(error, 'error');
        } finally {
            loading = false;
        }
    }

    async function updateCredit() {
        try {
            const token = localStorage.getItem('jwt_token');
            const res = await fetch('http://127.0.0.1:5000/api/admin/credit', {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ credit_thb: parseFloat(newCreditThb) })
            });
            const data = await res.json();
            if (res.ok && data.success) {
                creditThb = data.credit_thb;
                isEditingCredit = false;
                toast('Credit updated successfully', 'success');
            } else {
                toast(data.error || 'Failed to update credit', 'error');
            }
        } catch(e) {
            toast('Network error updating credit', 'error');
        }
    }

    onMount(() => {
        fetchStats();
    });

    function formatNumber(num) {
        if (num === undefined || num === null) return '0';
        return num.toLocaleString('en-US');
    }

    function formatCurrency(amount) {
        if (amount === undefined || amount === null) return '0.000000';
        return amount.toFixed(6);
    }
    
    function formatCurrencyTHB(amountUSD) {
        if (amountUSD === undefined || amountUSD === null) return '0.00';
        return (amountUSD * 35).toFixed(2); // Approximate THB conversion
    }
</script>

<div class="usage-dashboard" in:fade>
    <div class="header-area">
        <div>
            <h2>Gemini API Usage & Cost Dashboard</h2>
            <p class="subtitle">Monitor token consumption and estimated costs across all features</p>
        </div>
        <div class="header-actions">
            <select bind:value={timeFilter} on:change={fetchStats} class="time-filter-select">
                <option value="all">ทั้งหมด (All-time)</option>
                <option value="daily">รายวัน (Today)</option>
                <option value="monthly">รายเดือน (This Month)</option>
                <option value="yearly">รายปี (This Year)</option>
            </select>
            <button class="btn-refresh" on:click={fetchStats} disabled={loading}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class:spinning={loading}>
                    <polyline points="23 4 23 10 17 10"></polyline>
                    <polyline points="1 20 1 14 7 14"></polyline>
                    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                </svg>
                Refresh
            </button>
        </div>
    </div>

    {#if loading && !stats}
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Loading API usage statistics...</p>
        </div>
    {:else if error}
        <div class="error-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <p>{error}</p>
            <button class="btn-primary" on:click={fetchStats}>Try Again</button>
        </div>
    {:else if stats}
        <div class="overview-cards">
            <div class="card glass-card total-card">
                <div class="card-header">
                    <div class="card-label">Total Tokens Consumed</div>
                    <div class="card-icon blue">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                    </div>
                </div>
                <div class="card-value">{formatNumber(stats.total_tokens)}</div>
            </div>

            <div class="card glass-card cost-card">
                <div class="card-header">
                    <div class="card-label">Estimated Cost (USD)</div>
                    <div class="card-icon green">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                    </div>
                </div>
                <div class="card-value highlight">${formatCurrency(stats.total_cost_usd)}</div>
            </div>
            
            <div class="card glass-card credit-card">
                <div class="card-header">
                    <div class="card-label">Top-up Credit (THB)</div>
                    <div class="card-icon purple">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="2"></rect><path d="M12 12h.01"></path><path d="M17 12h.01"></path><path d="M7 12h.01"></path></svg>
                    </div>
                </div>
                {#if isEditingCredit}
                    <div class="credit-edit">
                        <input type="number" bind:value={newCreditThb} placeholder="Amount" step="10" />
                        <button on:click={updateCredit} class="btn-sm btn-primary">Save</button>
                        <button on:click={() => isEditingCredit = false} class="btn-sm btn-secondary">Cancel</button>
                    </div>
                {:else}
                    <div class="card-value highlight">฿{formatNumber(creditThb)}</div>
                    <div class="card-sub" style="display:flex; justify-content:space-between; align-items:center;">
                        <span>Cost: ฿{formatCurrencyTHB(stats.total_cost_usd)}</span>
                        <button on:click={() => { newCreditThb = creditThb; isEditingCredit = true; }} class="btn-text">Edit Credit</button>
                    </div>
                {/if}
            </div>
            
            <div class="card glass-card balance-card">
                <div class="card-header">
                    <div class="card-label">Remaining Balance (THB)</div>
                    <div class="card-icon" class:warning={(creditThb - (stats.total_cost_usd * 35)) < 0} style="background: rgba(245, 158, 11, 0.1); color: #fbbf24;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
                    </div>
                </div>
                <div class="card-value" class:danger={(creditThb - (stats.total_cost_usd * 35)) < 0}>
                    ฿{formatNumber(creditThb - (stats.total_cost_usd * 35))}
                </div>
            </div>
        </div>

        <!-- Chart Section -->
        {#if stats.model_chart_data && stats.model_chart_data.length > 0}
            <div class="charts-row" style="display: flex; gap: 16px; margin-top: 24px; flex-wrap: wrap;">
                <LineChart 
                    title="Input Tokens per model" 
                    data={stats.model_chart_data.map(d => ({ time_group: d.time_group, model_name: d.model_name, value: d.prompt_tokens }))}
                    timeFilter={timeFilter}
                    formatValue={formatNumber}
                />
                
                <LineChart 
                    title="Output Tokens per model" 
                    data={stats.model_chart_data.map(d => ({ time_group: d.time_group, model_name: d.model_name, value: d.completion_tokens }))}
                    timeFilter={timeFilter}
                    formatValue={formatNumber}
                />
                
                <LineChart 
                    title="Requests per model" 
                    data={stats.model_chart_data.map(d => ({ time_group: d.time_group, model_name: d.model_name, value: d.requests }))}
                    timeFilter={timeFilter}
                    formatValue={formatNumber}
                />
            </div>
        {/if}

        <div class="tables-container" style="margin-top: 24px;">
            <div class="table-section glass-card feature-usage">
                <h3>Usage by Feature (Endpoint)</h3>
                {#if stats.by_endpoint && stats.by_endpoint.length > 0}
                    <div class="table-responsive">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Feature</th>
                                    <th>API Requests</th>
                                    <th>Tokens Used</th>
                                    <th>Est. Cost (USD)</th>
                                    <th>Est. Cost (THB)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each stats.by_endpoint as item}
                                    <tr>
                                        <td>
                                            <span class="badge feature-badge">{item.endpoint}</span>
                                        </td>
                                        <td>{formatNumber(item.requests)}</td>
                                        <td>{formatNumber(item.tokens)}</td>
                                        <td class="cost-cell">${formatCurrency(item.cost_usd)}</td>
                                        <td class="cost-cell-thb">฿{formatCurrencyTHB(item.cost_usd)}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {:else}
                    <div class="empty-state">No usage data by feature yet.</div>
                {/if}
            </div>

            <div class="table-section glass-card model-usage">
                <h3>Usage by Model</h3>
                {#if stats.by_model && stats.by_model.length > 0}
                    <div class="table-responsive">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>AI Model</th>
                                    <th>API Requests</th>
                                    <th>Tokens Used</th>
                                    <th>Est. Cost (USD)</th>
                                    <th>Est. Cost (THB)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each stats.by_model as item}
                                    <tr>
                                        <td>
                                            <span class="badge model-badge" class:pro={item.model.includes('pro')} class:flash={item.model.includes('flash')}>{item.model}</span>
                                        </td>
                                        <td>{formatNumber(item.requests)}</td>
                                        <td>{formatNumber(item.tokens)}</td>
                                        <td class="cost-cell">${formatCurrency(item.cost_usd)}</td>
                                        <td class="cost-cell-thb">฿{formatCurrencyTHB(item.cost_usd)}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {:else}
                    <div class="empty-state">
                        <p>No model usage data available.</p>
                    </div>
                {/if}
            </div>
        </div>

        <!-- Document History Section -->
        <div class="tables-container" style="margin-top: 24px;">
            <div class="table-section glass-card doc-history" style="width: 100%;">
                <h3>ประวัติการสแกนและการวิเคราะห์เอกสาร (Document History)</h3>
                {#if stats.document_history && stats.document_history.length > 0}
                    <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>เวลา (Time)</th>
                                    <th>ชื่อเอกสาร (Document)</th>
                                    <th>ระบบ (Feature)</th>
                                    <th>โมเดล (Model)</th>
                                    <th>Tokens Used</th>
                                    <th>Est. Cost (USD)</th>
                                    <th>Est. Cost (THB)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each stats.document_history as doc}
                                    <tr>
                                        <td class="time-cell">{new Date(doc.date).toLocaleString('th-TH')}</td>
                                        <td class="doc-name">{doc.filename}</td>
                                        <td><span class="badge feature-badge">{doc.endpoint}</span></td>
                                        <td><span class="badge model-badge">{doc.model}</span></td>
                                        <td>{formatNumber(doc.tokens)}</td>
                                        <td class="cost-cell">${formatCurrency(doc.cost_usd)}</td>
                                        <td class="cost-cell-thb">฿{formatCurrencyTHB(doc.cost_usd)}</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {:else}
                    <div class="empty-state">
                        <p>ไม่มีประวัติการใช้งานในช่วงเวลานี้ (No documents processed in this period)</p>
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
        color: var(--text-main);
    }
    
    .header-area {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 28px;
    }
    
    .header-actions {
        display: flex;
        gap: 12px;
        align-items: center;
    }

    .time-filter-select {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--glass-border);
        color: var(--text-main);
        padding: 8px 16px;
        border-radius: var(--radius-md);
        font-family: var(--font-th);
        font-size: 14px;
        cursor: pointer;
        outline: none;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    
    .time-filter-select:hover {
        border-color: rgba(255, 255, 255, 0.2);
    }
    .time-filter-select:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
    }
    
    .header-area h2 {
        font-size: 24px;
        margin: 0 0 8px 0;
        background: var(--gradient-text);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .subtitle {
        color: var(--text-muted);
        font-size: 14px;
        margin: 0;
    }
    
    .btn-refresh {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid var(--glass-border);
        border-radius: 8px;
        color: var(--text-main);
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn-refresh:hover {
        background: rgba(255, 255, 255, 0.1);
    }
    
    .btn-refresh svg {
        width: 16px;
        height: 16px;
    }
    
    .spinning {
        animation: spin 1s linear infinite;
    }
    
    .overview-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        margin-bottom: 24px;
    }
    
    .card {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
        padding: 24px;
        border-radius: 12px;
        background: rgba(10, 15, 30, 0.4);
    }
    
    .card.total-card, .table-section.feature-usage {
        border: 1px solid rgba(59, 130, 246, 0.4);
        box-shadow: 0 0 20px rgba(59, 130, 246, 0.08), inset 0 0 15px rgba(59, 130, 246, 0.05);
    }
    
    .card.cost-card {
        border: 1px solid rgba(16, 185, 129, 0.4);
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.08), inset 0 0 15px rgba(16, 185, 129, 0.05);
    }
    
    .card.credit-card, .table-section.model-usage {
        border: 1px solid rgba(167, 139, 250, 0.4);
        box-shadow: 0 0 20px rgba(167, 139, 250, 0.08), inset 0 0 15px rgba(167, 139, 250, 0.05);
    }
    
    .card.balance-card {
        border: 1px solid rgba(245, 158, 11, 0.4);
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.08), inset 0 0 15px rgba(245, 158, 11, 0.05);
    }
    
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
    }
    
    .card-icon {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    
    .card-icon svg {
        width: 20px;
        height: 20px;
    }
    
    .card-icon.blue {
        background: rgba(59, 130, 246, 0.1);
        color: #60a5fa;
    }
    
    .card-icon.green {
        background: rgba(16, 185, 129, 0.1);
        color: #34d399;
    }
    
    .card-icon.purple {
        background: rgba(139, 92, 246, 0.1);
        color: #a78bfa;
    }
    
    .card-label {
        font-size: 13px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    
    .card-value {
        font-size: 28px;
        font-weight: 700;
        font-family: var(--font-en);
    }
    
    .card-value.highlight {
        color: #10b981;
    }
    
    .card-sub {
        font-size: 11px;
        color: var(--text-muted);
        margin-top: 4px;
    }
    
    .tables-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 24px;
    }
    
    @media (max-width: 1024px) {
        .tables-container {
            grid-template-columns: 1fr;
        }
    }
    
    .table-section {
        padding: 20px;
        border-radius: 12px;
        background: rgba(10, 15, 30, 0.4);
    }
    
    .table-section h3 {
        margin: 0 0 16px 0;
        font-size: 16px;
        color: var(--text-main);
    }
    
    .table-responsive {
        overflow-x: auto;
    }
    
    .data-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-size: 14px;
    }
    
    .data-table th {
        padding: 12px 16px;
        text-align: left;
        color: var(--text-muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        border-bottom: 1px solid var(--glass-border);
    }
    
    .data-table td {
        padding: 14px 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        color: var(--text-main);
    }
    
    .data-table tr:last-child td {
        border-bottom: none;
    }
    
    .data-table tbody tr:hover td {
        background: rgba(255, 255, 255, 0.02);
    }
    
    
    .data-table th {
        text-align: left;
        padding: 12px;
        color: var(--text-muted);
        font-weight: 500;
        border-bottom: 1px solid var(--glass-border);
    }
    
    .data-table td {
        padding: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .data-table tr:last-child td {
        border-bottom: none;
    }
    
    .cost-cell {
        font-family: var(--font-en);
        font-weight: 600;
        color: #34d399;
    }
    
    .cost-cell-thb {
        font-family: var(--font-en);
        font-weight: 600;
        color: #fbbf24;
    }
    
    .badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
        background: rgba(255, 255, 255, 0.1);
    }
    
    .feature-badge {
        background: rgba(99, 102, 241, 0.15);
        color: #818cf8;
        border: 1px solid rgba(99, 102, 241, 0.3);
    }
    
    .model-badge {
        background: rgba(75, 85, 99, 0.3);
        color: #d1d5db;
        border: 1px solid rgba(75, 85, 99, 0.5);
    }
    
    .model-badge.pro {
        background: rgba(139, 92, 246, 0.15);
        color: #a78bfa;
        border-color: rgba(139, 92, 246, 0.3);
    }
    
    .model-badge.flash {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border-color: rgba(245, 158, 11, 0.3);
    }
    
    .loading-state, .error-state, .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 60px 20px;
        color: var(--text-muted);
        background: var(--glass-bg);
        border: 1px dashed var(--glass-border);
        border-radius: 12px;
        text-align: center;
    }
    
    .error-state svg {
        width: 48px;
        height: 48px;
        margin-bottom: 16px;
        color: var(--danger);
    }
    
    .error-state .btn-primary {
        margin-top: 16px;
        padding: 8px 16px;
        background: var(--primary);
        border: none;
        border-radius: 8px;
        color: #fff;
        cursor: pointer;
    }
    
    .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255, 255, 255, 0.1);
        border-radius: 50%;
        border-top-color: var(--primary);
        animation: spin 1s ease-in-out infinite;
        margin-bottom: 16px;
    }
    
    .credit-edit {
        display: flex;
        gap: 6px;
        margin-top: 6px;
        align-items: center;
        background: rgba(0, 0, 0, 0.2);
        padding: 4px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .credit-edit input {
        width: 90px;
        background: transparent;
        border: none;
        color: #10b981;
        padding: 6px 8px;
        font-size: 16px;
        font-family: var(--font-en);
        font-weight: 700;
        outline: none;
    }
    
    .credit-edit input:focus {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 6px;
    }
    
    /* hide arrows in input number */
    .credit-edit input::-webkit-outer-spin-button,
    .credit-edit input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    .credit-edit input[type=number] {
        -moz-appearance: textfield;
    }

    .btn-sm {
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
        border-radius: 6px;
        border: none;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .btn-primary {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: #fff;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    }
    
    .btn-primary:hover {
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        transform: translateY(-1px);
    }
    
    .btn-secondary {
        background: rgba(255, 255, 255, 0.1);
        color: #e5e7eb;
    }
    
    .btn-secondary:hover {
        background: rgba(255, 255, 255, 0.15);
    }
    
    .btn-text {
        background: none;
        border: none;
        color: #818cf8;
        font-size: 11px;
        cursor: pointer;
        padding: 0;
        text-decoration: underline;
    }
    
    .card-value.danger {
        color: #ef4444;
    }
    
    .card-icon.warning {
        background: rgba(239, 68, 68, 0.1) !important;
        color: #ef4444 !important;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    .time-cell {
        font-size: 12px;
        color: var(--text-muted);
        white-space: nowrap;
    }
    .doc-name {
        max-width: 250px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-weight: 500;
        color: var(--text-main);
    }
</style>
