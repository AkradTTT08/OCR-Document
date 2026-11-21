<script>
  import { createEventDispatcher } from 'svelte';
  import QAIcon from './QAIcon.svelte';
  import { toast } from './toastStore.js';

  // Traceability Matrix pane (extracted from QAAnalysisDiagram.svelte)
  export let rows = [];
  export let projectCode = 'Project';

  const dispatch = createEventDispatcher();

  let query = "";
  let docFilter = "All";
  let statusFilter = "All";

  function getUatStatusClass(val) {
    if (!val) return 'pending';
    const s = String(val).toLowerCase();
    if (s.includes('pass') || s.includes('approved') || s.includes('sign-off') || s.includes('success')) return 'passed';
    if (s.includes('ready') || s.includes('tested') || s.includes('active')) return 'ready';
    if (s.includes('fail') || s.includes('reject') || s.includes('block')) return 'failed';
    return 'pending';
  }

  function getUatItems(row) {
    if (!row) return [];
    if (Array.isArray(row.uat_item) && row.uat_item.length > 0) return row.uat_item;
    if (Array.isArray(row.uat_items) && row.uat_items.length > 0) return row.uat_items;
    if (Array.isArray(row.uat_clause) && row.uat_clause.length > 0) return row.uat_clause;
    if (row.uat_item && typeof row.uat_item === 'string' && row.uat_item.trim() && row.uat_item !== '-') return [row.uat_item];
    if (row.uat_clause && typeof row.uat_clause === 'string' && row.uat_clause.trim() && row.uat_clause !== '-') return [row.uat_clause];
    if (row.uat_ref && typeof row.uat_ref === 'string' && row.uat_ref.trim() && row.uat_ref !== '-') return [row.uat_ref];
    
    // Fallback: derive linked UAT item code from req_code and req_title
    const cleanCode = (row.req_code || 'REQ').replace(/^REQ-?/i, '');
    const titleSummary = row.req_title || row.sitemap_node_title || 'Acceptance Criteria';
    return [`UAT-${cleanCode}: ${titleSummary}`];
  }

  // Filtered Matrix
  $: uniqueDocs = rows 
    ? ['All', ...new Set(rows.map(m => m.doc_name).filter(Boolean))]
    : ['All'];

  $: filteredMatrix = (rows) ? rows.filter(item => {
    const uatMatches = getUatItems(item).join(' ').toLowerCase();
    const matchQuery = !query || 
      (item.req_code && item.req_code.toLowerCase().includes(query.toLowerCase())) ||
      (item.req_title && item.req_title.toLowerCase().includes(query.toLowerCase())) ||
      (item.use_case_id && item.use_case_id.toLowerCase().includes(query.toLowerCase())) ||
      (item.screen_name && item.screen_name.toLowerCase().includes(query.toLowerCase())) ||
      (item.defect_log && String(item.defect_log).toLowerCase().includes(query.toLowerCase())) ||
      (item.defects && String(item.defects).toLowerCase().includes(query.toLowerCase())) ||
      uatMatches.includes(query.toLowerCase()) ||
      (item.uat_status && String(item.uat_status).toLowerCase().includes(query.toLowerCase())) ||
      (item.uat && String(item.uat).toLowerCase().includes(query.toLowerCase()));
    
    const matchDoc = docFilter === 'All' || item.doc_name === docFilter;
    const matchStatus = statusFilter === 'All' || item.status === statusFilter;

    return matchQuery && matchDoc && matchStatus;
  }) : [];

  function exportMatrixCSV() {
    if (!filteredMatrix.length) return;
    const headers = ["Req Code", "Requirement Title", "Document", "Doc Type", "Sitemap Node", "Use Case", "Screen", "Test Cases", "Defect Log", "UAT Reference (ข้อเอกสาร UAT)", "UAT Status", "Status"];
    const rows = filteredMatrix.map(m => {
      const uatList = getUatItems(m).join('; ');
      return [
        `"${m.req_code || ''}"`,
        `"${(m.req_title || '').replace(/"/g, '""')}"`,
        `"${m.doc_name || ''}"`,
        `"${m.doc_type || ''}"`,
        `"${m.sitemap_node_title || ''}"`,
        `"${(m.use_case_id || '').replace(/"/g, '""')}"`,
        `"${m.screen_name || m.screen_id || ''}"`,
        `"${(Array.isArray(m.test_cases) ? m.test_cases.join('; ') : m.test_cases || '').replace(/"/g, '""')}"`,
        `"${(Array.isArray(m.defect_log) ? m.defect_log.join('; ') : (m.defect_log || m.defects || 'No Defects')).replace(/"/g, '""')}"`,
        `"${uatList.replace(/"/g, '""')}"`,
        `"${(m.uat_status || m.uat || (m.status === 'Covered' ? 'Ready for UAT' : 'Pending')).replace(/"/g, '""')}"`,
        `"${m.status || ''}"`
      ];
    });

    const csvContent = "\uFEFF" + [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `Traceability_Matrix_${projectCode}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast('ดาวน์โหลดตาราง Traceability Matrix (CSV) เรียบร้อย', 'success');
  }
</script>

<div class="matrix-workspace">
    <!-- Filter Controls -->
    <div class="glass-panel matrix-controls-panel">
      <div class="matrix-filter-row">
        <div class="search-box">
          <span class="search-icon" aria-hidden="true"><QAIcon name="search" size={14} /></span>
          <input 
            type="text" 
            bind:value={query} aria-label="ค้นหา Requirement, Use Case หรือหน้าจอ" 
            placeholder="ค้นหา Requirement Code, Use Case, หรือ หน้าจอ..." 
            class="matrix-search-input"
          />
        </div>

        <div class="filter-select-group">
          <label for="matrix-doc-filter">เอกสารต้นทาง:</label>
          <select id="matrix-doc-filter" bind:value={docFilter} class="filter-select">
            {#each uniqueDocs as doc}
              <option value={doc}>{doc}</option>
            {/each}
          </select>
        </div>

        <div class="filter-select-group">
          <label for="matrix-status-filter">สถานะ Coverage:</label>
          <select id="matrix-status-filter" bind:value={statusFilter} class="filter-select">
            <option value="All">ทั้งหมด (All Status)</option>
            <option value="Covered">Covered</option>
            <option value="Partially Covered">Partially Covered</option>
            <option value="Pending">Pending</option>
          </select>
        </div>

        <button type="button" class="btn-export-csv" on:click={exportMatrixCSV}>
          <QAIcon name="download" /> Export CSV
        </button>
      </div>
    </div>

    <!-- Matrix Table -->
    <div class="glass-panel matrix-table-panel">
      <div class="table-container">
        <table class="matrix-table">
          <thead>
            <tr>
              <th style="width: 7%;">Req Code</th>
              <th style="width: 14%;">Requirement Title</th>
              <th style="width: 10%;">Source Document</th>
              <th style="width: 10%;">Sitemap / Menu</th>
              <th style="width: 10%;">Use Case</th>
              <th style="width: 10%;">Screen Mockup</th>
              <th style="width: 10%;">Test Scenarios</th>
              <th style="width: 10%;">Defect Log</th>
              <th style="width: 11%;">ข้อเอกสาร UAT (UAT Reference)</th>
              <th style="width: 8%; text-align: center;">Coverage</th>
            </tr>
          </thead>
          <tbody>
            {#if filteredMatrix.length === 0}
              <tr>
                <td colspan="10" style="text-align: center; color: #94a3b8; padding: 30px;">
                  ไม่พบข้อมูล Traceability Matrix ที่ตรงกับเงื่อนไข
                </td>
              </tr>
            {:else}
              {#each filteredMatrix as row}
                <tr>
                  <td><span class="code-badge">{row.req_code}</span></td>
                  <td style="font-weight: 500; color: #f8fafc;">{row.req_title}</td>
                  <td>
                    <div class="doc-cell">
                      <span class="doc-icon" aria-hidden="true"><QAIcon name="file" size={14} /></span>
                      <span class="doc-name" title={row.doc_name}>{row.doc_name}</span>
                    </div>
                  </td>
                  <td><span class="sitemap-pill">{row.sitemap_node_title || '-'}</span></td>
                  <td><span class="usecase-pill">{row.use_case_id || '-'}</span></td>
                  <td>
                    <button
                      type="button"
                      class="screen-link-btn"
                      disabled={!row.screen_id}
                      on:click={() => row.screen_id && dispatch('openscreen', { screen_id: row.screen_id })}
                    >
                      <QAIcon name="monitor" /> {row.screen_name || row.screen_id || '-'}
                    </button>
                  </td>
                  <td>
                    {#if Array.isArray(row.test_cases)}
                      <div class="testcases-list">
                        {#each row.test_cases as tc}
                          <span class="tc-item">{tc}</span>
                        {/each}
                      </div>
                    {:else}
                      <span>{row.test_cases || '-'}</span>
                    {/if}
                  </td>
                  <td>
                    {#if Array.isArray(row.defect_log) && row.defect_log.length > 0}
                      <div class="defect-list">
                        {#each row.defect_log as d}
                          <span class="defect-pill open" title={d}><QAIcon name="bug" /><span class="defect-text">{d}</span></span>
                        {/each}
                      </div>
                    {:else if row.defect_log && String(row.defect_log).trim() && row.defect_log !== '-'}
                      <span class="defect-pill open" title={row.defect_log}><QAIcon name="bug" /><span class="defect-text">{row.defect_log}</span></span>
                    {:else if Array.isArray(row.defects) && row.defects.length > 0}
                      <div class="defect-list">
                        {#each row.defects as d}
                          <span class="defect-pill open" title={d}><QAIcon name="bug" /><span class="defect-text">{d}</span></span>
                        {/each}
                      </div>
                    {:else if row.defects && String(row.defects).trim() && row.defects !== '-'}
                      <span class="defect-pill open" title={row.defects}><QAIcon name="bug" /><span class="defect-text">{row.defects}</span></span>
                    {:else}
                      <span class="defect-pill clean" title="ไม่มี Defect ค้าง"><QAIcon name="checkCircle" size={12} /><span class="defect-text">No Defects</span></span>
                    {/if}
                  </td>
                  <td>
                    <div class="uat-list">
                      {#each getUatItems(row) as uatItem}
                        <div class="uat-item-row" title={uatItem}>
                          <span class="uat-code-tag"><QAIcon name="clipboard" /> {uatItem.includes(':') ? uatItem.split(':')[0] : 'UAT'}</span>
                          <span class="uat-title-text">{uatItem.includes(':') ? uatItem.split(':').slice(1).join(':').trim() : uatItem}</span>
                        </div>
                      {/each}
                      <div class="uat-status-sub">
                        <span class="uat-pill {getUatStatusClass(row.uat_status || row.uat || (row.status === 'Covered' ? 'Ready for UAT' : 'Pending'))}">
                          {row.uat_status || row.uat || (row.status === 'Covered' ? 'Ready for UAT' : 'UAT Pending')}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td style="text-align: center;">
                    <span class="status-badge {String(row.status || 'covered').trim().toLowerCase().replace(/\s+/g, '-')}">
                      {row.status || 'Covered'}
                    </span>
                  </td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
    </div>
</div>

<style>
  .matrix-workspace {
    display: flex;
    flex-direction: column;
    gap: 14px;
    flex: 1;
    min-width: 0;
    min-height: 0;
  }

  .glass-panel {
    background: rgba(18, 20, 28, 0.64);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 22px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.28);
  }

  .matrix-controls-panel { padding: 12px 16px; }

  .matrix-filter-row {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

  .search-box {
      position: relative;
      flex: 1;
      min-width: 240px;
    }

  .search-icon {
      position: absolute;
      left: 11px;
      top: 50%;
      transform: translateY(-50%);
      display: inline-flex;
      align-items: center;
      color: var(--text-muted, #94a3b8);
      pointer-events: none;
    }

  .matrix-search-input {
      width: 100%;
      height: 36px;
      background: rgba(11, 13, 21, 0.8);
      border: 1px solid var(--qa-border-strong, rgba(255, 255, 255, 0.14));
      color: var(--text-main, #f8fafc);
      padding: 0 12px 0 32px;
      border-radius: 8px;
      font-size: 12.5px;
      outline: none;
      box-sizing: border-box;
      transition: border-color 0.2s, box-shadow 0.2s;
    }

  .matrix-search-input:focus-visible {
      border-color: var(--primary, #6366f1);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
      outline: none;
    }

  .filter-select-group {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12.5px;
      color: var(--qa-text-soft, #cbd5e1);
      min-width: 0;
    }

  .filter-select-group label {
      white-space: nowrap;
      flex-shrink: 0;
    }

  .filter-select {
      height: 36px;
      background-color: rgba(11, 13, 21, 0.8);
      border: 1px solid var(--qa-border-strong, rgba(255, 255, 255, 0.14));
      color: var(--text-main, #f8fafc);
      padding: 0 32px 0 12px;
      border-radius: 8px;
      font-size: 12.5px;
      box-sizing: border-box;
    }

  #matrix-doc-filter {
      max-width: 240px;
    }

  .btn-export-csv {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      height: 36px;
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #6ee7b7;
      padding: 0 14px;
      border-radius: 8px;
      font-size: 12.5px;
      font-weight: 600;
      white-space: nowrap;
      flex-shrink: 0;
      cursor: pointer;
      transition: background-color 0.2s, border-color 0.2s, color 0.2s, box-shadow 0.2s, transform 0.2s, opacity 0.2s;
    }

  .btn-export-csv:hover {
      background: rgba(16, 185, 129, 0.35);
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.3);
    }

  .matrix-table-panel {
      padding: 0;
      overflow: hidden;
      min-width: 0;
    }

  .table-container {
      overflow: auto;
      max-height: 600px;
    }

  .matrix-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
    }

  .matrix-table th {
      background: var(--qa-surface-raised, #161b2a);
      padding: 12px 14px;
      color: var(--qa-text-muted, #94a3b8);
      font-weight: 600;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      position: sticky;
      top: 0;
      z-index: 3;
      text-align: left;
      white-space: nowrap;
    }

  .matrix-table td {
      padding: 10px 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      vertical-align: middle;
    }

  .matrix-table tr:hover { background: rgba(255, 255, 255, 0.03); }

  .code-badge {
      background: rgba(99, 102, 241, 0.2);
      border: 1px solid rgba(99, 102, 241, 0.4);
      color: var(--qa-iris-text, #a5b4fc);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
      font-weight: 700;
      font-size: 11px;
    }

  .doc-cell { display: flex; align-items: center; gap: 6px; min-width: 0; }
  .doc-icon { display: inline-flex; flex-shrink: 0; }

  .doc-name { font-size: 12px; color: var(--qa-text-soft, #cbd5e1); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .sitemap-pill, .usecase-pill {
      font-size: 11.5px;
      color: var(--qa-text, #f1f5f9);
    }

  .screen-link-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      background: rgba(139, 92, 246, 0.15);
      border: 1px solid rgba(139, 92, 246, 0.35);
      color: #c4b5fd;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 11.5px;
      cursor: pointer;
      transition: background-color 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s, opacity 0.15s;
      text-align: left;
    }

  .screen-link-btn:hover:not(:disabled) { background: rgba(139, 92, 246, 0.3); color: white; }
  .screen-link-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

  .testcases-list { display: flex; flex-direction: column; gap: 2px; }

  .tc-item { font-size: 11px; color: var(--qa-text-muted, #94a3b8); }

  /* Defect & UAT Badges in Matrix */
    .defect-list { display: flex; flex-direction: column; gap: 3px; }

  .defect-pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      max-width: 170px;
      vertical-align: middle;
    }

  .defect-text {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
    }

  .defect-pill.open {
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.4);
      color: #fca5a5;
    }

  .defect-pill.clean {
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: #86efac;
      font-weight: 500;
      font-size: 11px;
    }

  .uat-list {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

  .uat-item-row {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: rgba(22, 25, 38, 0.7);
      border: 1px solid rgba(99, 102, 241, 0.3);
      border-radius: 4px;
      padding: 2px 6px;
      max-width: 220px;
    }

  .uat-code-tag {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      font-size: 11px;
      font-weight: 700;
      color: var(--qa-iris-soft, #c7d2fe);
      white-space: nowrap;
      background: rgba(99, 102, 241, 0.18);
      padding: 1px 4px;
      border-radius: 3px;
      flex-shrink: 0;
    }

  .uat-title-text {
      font-size: 11px;
      color: var(--qa-text, #f1f5f9);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
    }

  .uat-status-sub {
      margin-top: 2px;
    }

  .status-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
    background: rgba(148, 163, 184, 0.14);
    border: 1px solid rgba(148, 163, 184, 0.35);
    color: #cbd5e1;
  }

  .status-badge.covered {
    background: rgba(16, 185, 129, 0.16);
    border-color: rgba(16, 185, 129, 0.42);
    color: #6ee7b7;
  }

  .status-badge.partially-covered {
    background: rgba(245, 158, 11, 0.16);
    border-color: rgba(245, 158, 11, 0.42);
    color: #fcd34d;
  }

  .status-badge.pending {
    background: rgba(148, 163, 184, 0.14);
    border-color: rgba(148, 163, 184, 0.35);
    color: #cbd5e1;
  }

  .status-badge.gap,
  .status-badge.missing {
    background: rgba(244, 63, 94, 0.16);
    border-color: rgba(244, 63, 94, 0.42);
    color: #fda4af;
  }

  .uat-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    white-space: nowrap;
  }

  .uat-pill.passed {
    background: rgba(16, 185, 129, 0.2);
    border: 1px solid rgba(16, 185, 129, 0.5);
    color: #6ee7b7;
  }

  .uat-pill.ready {
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(99, 102, 241, 0.5);
    color: var(--qa-iris-text, #a5b4fc);
  }

  .uat-pill.pending {
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #fcd34d;
  }

  .uat-pill.failed {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.5);
    color: #fca5a5;
  }

  @media (max-width: 768px) {
    .matrix-filter-row {
      flex-direction: column;
      align-items: stretch;
      gap: 10px;
    }

    .search-box {
      min-width: 0;
      width: 100%;
    }

    .filter-select-group {
      width: 100%;
      justify-content: space-between;
    }

    .filter-select,
    #matrix-doc-filter {
      flex: 1;
      max-width: none;
      min-width: 0;
    }

    .btn-export-csv {
      width: 100%;
    }
  }
</style>
