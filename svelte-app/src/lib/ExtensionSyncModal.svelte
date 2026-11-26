<script>
  import { createEventDispatcher, onMount, onDestroy } from "svelte";
  import { showToast } from "./toastStore.js";

  export let show = false;
  export let selectedProject = "";
  export let collections = [];

  const dispatch = createEventDispatcher();
  const API_BASE = "http://localhost:5001";

  let liveApis = [];
  let selectedKeys = new Set();
  let pollInterval = null;
  let isConnected = false;
  let isPolling = false;
  let isSaving = false;
  let lastSyncedAt = "";
  let syncError = "";

  // Grouped import config (A3)
  let importMode = "new"; // 'new' | 'append'
  let targetCollectionId = "";
  let customCollectionName = "";

  function getAuthHeaders(extra = {}) {
    const token =
      typeof localStorage !== "undefined"
        ? localStorage.getItem("jwt_token")
        : null;
    const headers = { ...extra };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }

  function defaultGroupName() {
    const stamp = new Date().toLocaleString("th-TH", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
    return `Chrome Live Capture (${stamp})`;
  }

  function endpointKey(api, idx) {
    return `${(api.method || "GET").toUpperCase()}::${api.url || api.path || idx}`;
  }

  $: if (show && !customCollectionName) {
    customCollectionName = defaultGroupName();
  }

  $: if (
    show &&
    importMode === "append" &&
    !targetCollectionId &&
    collections.length > 0
  ) {
    targetCollectionId = collections[0].id;
  }

  onMount(() => {
    if (show) startPolling();
  });

  $: if (show) {
    startPolling();
  } else {
    stopPolling();
  }

  onDestroy(() => {
    stopPolling();
  });

  function startPolling() {
    if (pollInterval) return;
    fetchLiveTraffic();
    pollInterval = setInterval(fetchLiveTraffic, 2500);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  async function fetchLiveTraffic() {
    if (isPolling) return;
    isPolling = true;
    try {
      const res = await fetch(
        `${API_BASE}/api/extension/latest?project_id=${encodeURIComponent(selectedProject || "")}`,
        {
          headers: getAuthHeaders(),
        },
      );
      if (!res.ok) {
        isConnected = false;
        syncError = `เซิร์ฟเวอร์ตอบกลับสถานะ ${res.status}`;
        return;
      }
      const data = await res.json();
      isConnected = true;
      syncError = "";
      lastSyncedAt = new Date().toLocaleTimeString("th-TH");
      const incoming = Array.isArray(data?.traffic)
        ? data.traffic
        : Array.isArray(data?.apis)
          ? data.apis
          : [];
      if (incoming) {
        const prevCount = liveApis.length;
        liveApis = incoming;
        if (prevCount === 0 && liveApis.length > 0 && selectedKeys.size === 0) {
          selectedKeys = new Set(
            liveApis.map((item, i) => endpointKey(item, i)),
          );
        }
      }
    } catch (e) {
      isConnected = false;
      syncError = "ยังไม่ได้เชื่อมต่อกับ Chrome Extension API Receiver";
    } finally {
      isPolling = false;
    }
  }

  async function clearTraffic() {
    try {
      await fetch(`${API_BASE}/api/extension/traffic/clear`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ project_id: selectedProject }),
      });
      liveApis = [];
      selectedKeys = new Set();
      showToast("ล้างรายการดักจับ Live Traffic เรียบร้อยแล้ว", "info");
    } catch (e) {
      showToast("ไม่สามารถล้างรายการดักจับได้", "error");
    }
  }

  function toggleSelect(api, idx) {
    const key = endpointKey(api, idx);
    const next = new Set(selectedKeys);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    selectedKeys = next;
  }

  function toggleSelectAll() {
    if (selectedKeys.size === liveApis.length) {
      selectedKeys = new Set();
    } else {
      selectedKeys = new Set(liveApis.map((api, idx) => endpointKey(api, idx)));
    }
  }

  async function importSelectedApis() {
    if (!selectedProject) {
      showToast("กรุณาเลือกโครงการก่อนนำเข้า API", "warning");
      return;
    }
    const chosen = liveApis.filter((api, idx) =>
      selectedKeys.has(endpointKey(api, idx)),
    );
    if (chosen.length === 0) {
      showToast("กรุณาเลือกอย่างน้อย 1 Endpoint ที่ต้องการนำเข้า", "warning");
      return;
    }
    if (importMode === "append" && !targetCollectionId) {
      showToast("กรุณาเลือก Collection ปลายทางที่ต้องการเพิ่มเข้า", "warning");
      return;
    }

    isSaving = true;
    try {
      const formatted = chosen.map((a) => {
        let parsedPath = a.path || a.url || "/";
        try {
          if (a.url && /^https?:\/\//i.test(a.url)) {
            const u = new URL(a.url);
            parsedPath = `${u.pathname}${u.search || ""}`;
          }
        } catch (_) {}

        return {
          method: (a.method || "GET").toUpperCase(),
          path: parsedPath,
          url: a.url || parsedPath,
          name: a.name || `${(a.method || "GET").toUpperCase()} ${parsedPath}`,
          summary:
            a.summary || `Captured from Chrome Extension (${a.status || 200})`,
          category: "Chrome Live Sync",
          headers: a.headers && typeof a.headers === "object" ? a.headers : {},
          body:
            typeof a.body === "string"
              ? a.body
              : a.body
                ? JSON.stringify(a.body, null, 2)
                : "",
          curl: a.curl || "",
          responseBody:
            typeof a.responseBody === "string"
              ? a.responseBody
              : a.responseBody
                ? JSON.stringify(a.responseBody, null, 2)
                : "",
          status: a.status || 200,
        };
      });

      const res = await fetch(`${API_BASE}/api/api-collections/save-sniffed`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          project_id: selectedProject,
          collection_name:
            importMode === "new"
              ? customCollectionName.trim() || defaultGroupName()
              : undefined,
          target_collection_id:
            importMode === "append" ? targetCollectionId : null,
          source_label: "Chrome Extension Live Sync",
          endpoints: formatted,
        }),
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || `บันทึกไม่สำเร็จ (HTTP ${res.status})`);
      }

      showToast(
        importMode === "append"
          ? `เพิ่ม ${chosen.length} Endpoints เข้า Collection เดิมเรียบร้อยแล้ว`
          : `สร้าง Collection ใหม่พร้อม ${chosen.length} Endpoints เรียบร้อยแล้ว`,
        "success",
      );
      dispatch("imported", data);
      close();
    } catch (e) {
      showToast(`เกิดข้อผิดพลาดในการนำเข้า: ${e.message}`, "error");
    } finally {
      isSaving = false;
    }
  }

  function close() {
    stopPolling();
    dispatch("close");
  }

  function handleKeydown(e) {
    if (show && e.key === "Escape") {
      close();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="ext-modal-backdrop" on:click|self={close}>
    <div
      class="ext-modal-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ext-sync-modal-title"
    >
      <div class="ext-modal-header">
        <div class="header-title-wrap">
          <div class="ext-icon-box" aria-hidden="true">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 14a4 4 0 1 1 4-4 4 4 0 0 1-4 4z"
              />
              <path d="M21.17 8H12" />
              <path d="M3.95 6.06L8.54 14" />
              <path d="M10.88 21.94L15.46 14" />
            </svg>
          </div>
          <div>
            <div class="title-row">
              <h3 id="ext-sync-modal-title">Chrome Extension Live Sync</h3>
              <span
                class="conn-pill"
                class:online={isConnected}
                class:offline={!isConnected}
              >
                <span class="conn-dot"></span>
                {isConnected ? "Receiver พร้อมรับข้อมูล" : "รอการเชื่อมต่อ"}
              </span>
            </div>
            <p class="subtitle">
              ดักจับ XHR / Fetch จริงจากเบราว์เซอร์ แล้วรวบเป็น 1 API Collection
              โดยไม่สูญเสีย Headers, Body และ Response
            </p>
          </div>
        </div>
        <button
          type="button"
          class="close-btn"
          on:click={close}
          aria-label="ปิดหน้าต่าง Chrome Extension Live Sync"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div class="ext-modal-body">
        <div class="guide-banner">
          <div class="guide-steps">
            <span class="step-tag">1</span>
            <span
              >เปิด Chrome Extension <strong>Spectra QA API Sniffer</strong>
              แล้วกด <strong>Start Recording</strong></span
            >
            <span class="step-sep" aria-hidden="true">/</span>
            <span class="step-tag">2</span>
            <span
              >ใช้งานหน้าเว็บที่ต้องการทดสอบ ระบบจะดึงรายการ API ขึ้นมาอัตโนมัติ</span
            >
          </div>
          {#if lastSyncedAt}
            <span class="sync-time">ซิงก์ล่าสุด {lastSyncedAt}</span>
          {/if}
        </div>

        <div class="target-config-box">
          <div
            class="target-mode-tabs"
            role="radiogroup"
            aria-label="รูปแบบการจัดเก็บ API Collection"
          >
            <button
              type="button"
              class="mode-tab"
              class:active={importMode === "new"}
              on:click={() => (importMode = "new")}
            >
              สร้างเป็น 1 Collection ใหม่
            </button>
            <button
              type="button"
              class="mode-tab"
              class:active={importMode === "append"}
              disabled={collections.length === 0}
              on:click={() => (importMode = "append")}
            >
              เพิ่มเข้า Collection เดิม ({collections.length})
            </button>
          </div>

          <div class="target-input-row">
            {#if importMode === "new"}
              <label class="field-label" for="ext-collection-name"
                >ชื่อ Collection ใหม่ที่จะบันทึก</label
              >
              <input
                id="ext-collection-name"
                type="text"
                class="spectra-input"
                bind:value={customCollectionName}
                placeholder="เช่น ระบบสั่งซื้อสินค้า - Chrome Live Capture"
              />
            {:else}
              <label class="field-label" for="ext-target-collection"
                >เลือก Collection ปลายทาง</label
              >
              <select
                id="ext-target-collection"
                class="spectra-input"
                bind:value={targetCollectionId}
              >
                {#each collections as col}
                  <option value={col.id}
                    >{col.name} ({col.endpoint_count || 0} endpoints)</option
                  >
                {/each}
              </select>
            {/if}
          </div>
        </div>

        <div class="traffic-monitor">
          <div class="monitor-header">
            <div class="monitor-left">
              <label class="select-all-label">
                <input
                  type="checkbox"
                  checked={liveApis.length > 0 &&
                    selectedKeys.size === liveApis.length}
                  disabled={liveApis.length === 0}
                  on:change={toggleSelectAll}
                />
                <span
                  >เลือกทั้งหมด ({selectedKeys.size}/{liveApis.length} รายการ)</span
                >
              </label>
            </div>
            <div class="monitor-actions">
              <button
                type="button"
                class="btn-ghost-sm"
                on:click={fetchLiveTraffic}
                disabled={isPolling}
              >
                รีเฟรชตอนนี้
              </button>
              {#if liveApis.length > 0}
                <button
                  type="button"
                  class="btn-ghost-sm danger"
                  on:click={clearTraffic}
                >
                  ล้างรายการดักจับ
                </button>
              {/if}
            </div>
          </div>

          <div class="traffic-list">
            {#if liveApis.length === 0}
              <div class="empty-traffic">
                <div class="radar-ring" aria-hidden="true">
                  <svg
                    width="26"
                    height="26"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                  >
                    <circle cx="12" cy="12" r="9" />
                    <circle cx="12" cy="12" r="4" />
                    <line x1="12" y1="3" x2="12" y2="12" />
                  </svg>
                </div>
                <p class="empty-title">
                  กำลังรอดักจับ API Traffic จาก Chrome Extension...
                </p>
                <span class="empty-sub">
                  {syncError ||
                    "เมื่อมีการเรียกใช้งาน XHR หรือ Fetch บนหน้าเว็บที่เปิด Recording รายการจะแสดงที่นี่ทันที"}
                </span>
              </div>
            {:else}
              {#each liveApis as api, idx (endpointKey(api, idx))}
                {@const isChecked = selectedKeys.has(endpointKey(api, idx))}
                <div
                  class="traffic-item"
                  class:selected={isChecked}
                  on:click={() => toggleSelect(api, idx)}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    on:click|stopPropagation
                    on:change={() => toggleSelect(api, idx)}
                    aria-label={`เลือก ${api.method || "GET"} ${api.url || api.path}`}
                  />
                  <span
                    class="method-badge {(api.method || 'GET').toLowerCase()}"
                  >
                    {(api.method || "GET").toUpperCase()}
                  </span>
                  <div class="traffic-main">
                    <div class="url-text" title={api.url || api.path}>
                      {api.url || api.path}
                    </div>
                    <div class="meta-tags">
                      {#if api.headers && Object.keys(api.headers).length > 0}
                        <span class="meta-chip"
                          >{Object.keys(api.headers).length} Headers</span
                        >
                      {/if}
                      {#if api.body}
                        <span class="meta-chip accent">มี Request Body</span>
                      {/if}
                      {#if api.responseBody}
                        <span class="meta-chip success">มี Response Sample</span
                        >
                      {/if}
                    </div>
                  </div>
                  <span
                    class="status-badge"
                    class:ok={!api.status || api.status < 400}
                    class:err={api.status >= 400}
                  >
                    {api.status || 200}
                  </span>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      </div>

      <div class="ext-modal-footer">
        <button type="button" class="btn-cancel" on:click={close}>ยกเลิก</button
        >
        <button
          type="button"
          class="btn-primary-spectra"
          disabled={selectedKeys.size === 0 || isSaving}
          on:click={importSelectedApis}
        >
          {#if isSaving}
            กำลังบันทึก...
          {:else if importMode === "append"}
            เพิ่ม {selectedKeys.size} Endpoints เข้า Collection เดิม
          {:else}
            บันทึกเป็น 1 Collection ({selectedKeys.size} Endpoints)
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .ext-modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(9, 7, 17, 0.78);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 2100;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .ext-modal-card {
    background: var(--bg2, #120f1d);
    border: 1px solid var(--surface-border, rgba(168, 85, 247, 0.22));
    border-radius: 20px;
    width: 100%;
    max-width: 780px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.65);
    overflow: hidden;
  }

  .ext-modal-header {
    padding: 20px 24px;
    border-bottom: 1px solid rgba(168, 85, 247, 0.14);
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    background: rgba(24, 19, 38, 0.55);
  }

  .header-title-wrap {
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }

  .ext-icon-box {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.32);
    color: var(--primary-light, #c084fc);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .header-title-wrap h3 {
    margin: 0;
    font-family: "Outfit", "Prompt", sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .subtitle {
    margin: 4px 0 0;
    font-size: 0.82rem;
    color: var(--text-muted, #94a3b8);
    line-height: 1.45;
  }

  .conn-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
  }

  .conn-pill.online {
    background: rgba(16, 185, 129, 0.12);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.28);
  }

  .conn-pill.offline {
    background: rgba(245, 158, 11, 0.12);
    color: #fbbf24;
    border: 1px solid rgba(245, 158, 11, 0.28);
  }

  .conn-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
  }

  .close-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(168, 85, 247, 0.18);
    color: var(--text-muted, #94a3b8);
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .close-btn:hover {
    color: var(--text, #f8fafc);
    border-color: rgba(168, 85, 247, 0.4);
    background: rgba(168, 85, 247, 0.12);
  }

  .ext-modal-body {
    padding: 20px 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .guide-banner {
    background: rgba(24, 19, 38, 0.7);
    border: 1px solid rgba(168, 85, 247, 0.18);
    border-radius: 12px;
    padding: 12px 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    font-size: 0.8rem;
    color: var(--text-secondary, #cbd5e1);
  }

  .guide-steps {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .step-tag {
    width: 20px;
    height: 20px;
    border-radius: 999px;
    background: rgba(168, 85, 247, 0.2);
    color: var(--primary-light, #c084fc);
    font-family: "Outfit", sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .step-sep {
    color: rgba(148, 163, 184, 0.4);
  }

  .sync-time {
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
  }

  .target-config-box {
    background: rgba(18, 15, 29, 0.85);
    border: 1px solid rgba(168, 85, 247, 0.16);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .target-mode-tabs {
    display: flex;
    gap: 8px;
  }

  .mode-tab {
    flex: 1;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(168, 85, 247, 0.18);
    background: rgba(24, 19, 38, 0.6);
    color: var(--text-muted, #94a3b8);
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .mode-tab.active {
    background: rgba(168, 85, 247, 0.18);
    color: var(--text, #f8fafc);
    border-color: rgba(168, 85, 247, 0.45);
  }

  .mode-tab:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .target-input-row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field-label {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-secondary, #cbd5e1);
  }

  .spectra-input {
    width: 100%;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid rgba(168, 85, 247, 0.22);
    background: var(--bg, #090711);
    color: var(--text, #f8fafc);
    font-family: "Prompt", sans-serif;
    font-size: 0.85rem;
    outline: none;
  }

  .spectra-input:focus {
    border-color: var(--primary, #a855f7);
    box-shadow: 0 0 0 2px rgba(168, 85, 247, 0.2);
  }

  .traffic-monitor {
    background: var(--bg, #090711);
    border: 1px solid rgba(168, 85, 247, 0.18);
    border-radius: 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-height: 240px;
    max-height: 320px;
  }

  .monitor-header {
    background: rgba(24, 19, 38, 0.75);
    padding: 10px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(168, 85, 247, 0.14);
  }

  .select-all-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary, #cbd5e1);
    cursor: pointer;
  }

  .monitor-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-ghost-sm {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(168, 85, 247, 0.18);
    color: var(--text-secondary, #cbd5e1);
    font-size: 0.74rem;
    padding: 4px 10px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.16s ease;
  }

  .btn-ghost-sm:hover:not(:disabled) {
    border-color: rgba(168, 85, 247, 0.4);
    color: var(--text, #f8fafc);
  }

  .btn-ghost-sm.danger {
    color: #f87171;
    border-color: rgba(239, 68, 68, 0.25);
  }

  .traffic-list {
    padding: 10px;
    overflow-y: auto;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .empty-traffic {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 190px;
    color: var(--text-muted, #94a3b8);
    text-align: center;
    padding: 20px;
    gap: 8px;
  }

  .radar-ring {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: rgba(168, 85, 247, 0.1);
    border: 1px solid rgba(168, 85, 247, 0.28);
    color: var(--primary-light, #c084fc);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .empty-title {
    margin: 4px 0 0;
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-secondary, #cbd5e1);
  }

  .empty-sub {
    font-size: 0.78rem;
    max-width: 460px;
    line-height: 1.45;
  }

  .traffic-item {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(24, 19, 38, 0.55);
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(168, 85, 247, 0.12);
    cursor: pointer;
    transition: all 0.16s ease;
  }

  .traffic-item.selected {
    border-color: rgba(168, 85, 247, 0.42);
    background: rgba(168, 85, 247, 0.1);
  }

  .method-badge {
    font-family: "Outfit", monospace;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
    min-width: 52px;
    text-align: center;
  }

  .method-badge.get {
    background: rgba(6, 182, 212, 0.15);
    color: #22d3ee;
  }
  .method-badge.post {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
  }
  .method-badge.put,
  .method-badge.patch {
    background: rgba(245, 158, 11, 0.15);
    color: #fbbf24;
  }
  .method-badge.delete {
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
  }

  .traffic-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .url-text {
    font-family: monospace;
    font-size: 0.8rem;
    color: var(--text, #f8fafc);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .meta-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .meta-chip {
    font-size: 0.68rem;
    padding: 1px 7px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted, #94a3b8);
  }

  .meta-chip.accent {
    background: rgba(168, 85, 247, 0.16);
    color: var(--primary-light, #c084fc);
  }

  .meta-chip.success {
    background: rgba(16, 185, 129, 0.14);
    color: #34d399;
  }

  .status-badge {
    font-family: "Outfit", monospace;
    font-size: 0.74rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
  }

  .status-badge.ok {
    color: #34d399;
    background: rgba(16, 185, 129, 0.12);
  }

  .status-badge.err {
    color: #f87171;
    background: rgba(239, 68, 68, 0.12);
  }

  .ext-modal-footer {
    padding: 16px 24px;
    border-top: 1px solid rgba(168, 85, 247, 0.14);
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    background: rgba(18, 15, 29, 0.9);
  }

  .btn-cancel {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(168, 85, 247, 0.2);
    color: var(--text-secondary, #cbd5e1);
    padding: 9px 18px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-primary-spectra {
    background: var(
      --gradient-main,
      linear-gradient(135deg, #a855f7 0%, #6366f1 50%, #06b6d4 100%)
    );
    border: none;
    color: #ffffff;
    padding: 9px 20px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 6px 20px rgba(168, 85, 247, 0.3);
    transition: all 0.18s ease;
  }

  .btn-primary-spectra:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    box-shadow: none;
  }
</style>
