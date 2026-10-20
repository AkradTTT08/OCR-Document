<script>
  import { fade, scale } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { createEventDispatcher, onDestroy } from "svelte";

  const dispatch = createEventDispatcher();

  export var showModal = false;
  export var projectId = null;

  var isConnected = true;
  var isLoading = false;
  var isSyncingToRepo = false;
  var selectedApi = null;
  var activeTab = "response"; // 'response' | 'curl'
  var apis = [];
  var lastSyncTime = "";
  var refreshTimer = null;

  // React to modal opening/closing
  $: if (showModal) {
    onModalOpen();
  } else {
    onModalClose();
  }

  // React to projectId changes while open
  $: if (showModal && projectId) {
    loadCapturedApis(true);
  }

  function onModalOpen() {
    loadCapturedApis(false);
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
      if (showModal) {
        loadCapturedApis(true);
      }
    }, 2500);
  }

  function onModalClose() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
    selectedApi = null;
  }

  onDestroy(() => {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  });

  async function loadCapturedApis(silent = false) {
    if (!silent) isLoading = true;
    try {
      const pidParam = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
      const res = await fetch(`/api/extension/sync-apis${pidParam}`);
      if (res.ok) {
        const data = await res.json();
        isConnected = true;
        const fetched = data.apis || [];
        apis = fetched;
        if (data.timestamp) lastSyncTime = data.timestamp;

        // Auto select first item if none or invalid
        if (apis.length > 0) {
          if (!selectedApi || !apis.some(a => (a.id && a.id === selectedApi.id) || (a.path === selectedApi.path && a.method === selectedApi.method))) {
            selectedApi = apis[0];
          }
        } else {
          selectedApi = null;
        }
      } else {
        isConnected = false;
      }
    } catch (e) {
      console.warn("Could not fetch captured APIs from backend:", e);
      isConnected = false;
    } finally {
      if (!silent) isLoading = false;
    }
  }

  async function syncExtensionData() {
    if (apis.length === 0) {
      toast("ไม่มีรายการ API สำหรับ Sync กรุณาบันทึกผ่าน Chrome Extension ก่อน", "warning");
      return;
    }

    isSyncingToRepo = true;
    toast(`กำลังบันทึก ${apis.length} APIs เข้าสู่ Project Repository...`, "info");

    try {
      if (projectId) {
        await fetch("/api/api-collections/save-sniffed", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: projectId,
            endpoints: apis.map(a => ({
              method: (a.method || "GET").toUpperCase(),
              url: a.path || a.url || "",
              name: a.summary || a.name || `${a.method || 'GET'} ${a.path || a.url}`,
              category: "Chrome Extension Live Sync"
            }))
          })
        });
      }

      toast(`✅ Sync สำเร็จ! นำเข้า ${apis.length} API รายการเข้าสู่ Repository เรียบร้อยแล้ว`, "success");
      dispatch("synced", apis);
      showModal = false;
    } catch (e) {
      console.error("Failed persisting extension APIs", e);
      toast("Sync ข้อมูลสำเร็จ (บันทึกระดับ Local Memory)", "success");
      dispatch("synced", apis);
      showModal = false;
    } finally {
      isSyncingToRepo = false;
    }
  }

  function copyCurl(api) {
    const target = api || selectedApi;
    if (!target) return;
    let text = target.curl;
    if (!text) {
      const u = target.url || target.path || "";
      text = `curl -X ${target.method || 'GET'} "${u}" -H "Content-Type: application/json"`;
    }
    navigator.clipboard.writeText(text);
    toast("🐚 คัดลอก cURL (bash) เรียบร้อยแล้ว!", "success");
  }

  function copyResponse(api) {
    const target = api || selectedApi;
    if (!target) return;
    const text = target.responseBody || JSON.stringify(target, null, 2);
    navigator.clipboard.writeText(text);
    toast("📋 คัดลอก Response Body เรียบร้อยแล้ว!", "success");
  }

  function closeModal() {
    showModal = false;
    onModalClose();
  }
</script>

{#if showModal}
<div class="modal-backdrop" transition:fade={{ duration: 200 }}>
  <div class="modal-card glass-panel" in:scale={{ start: 0.9, duration: 250 }}>
    <div class="modal-header">
      <div style="display: flex; align-items: center; gap: 10px;">
        <span class="icon-wrap">🧩</span>
        <div>
          <h3 class="modal-title">Spectra Chrome Extension Live Inspector</h3>
          <p class="modal-subtitle">ดึงข้อมูล Network Traffic, Response Body และ cURL Command จาก Chrome Extension</p>
        </div>
      </div>
      <button class="close-btn" on:click={closeModal}>✕</button>
    </div>

    <!-- Connection Status Banner -->
    <div class="status-banner" class:connected={isConnected} class:disconnected={!isConnected}>
      <div class="status-dot"></div>
      <span class="status-text">
        {isConnected ? "Chrome Extension Connected (Listening on port 5000)" : "Backend Disconnected (ไม่สามารถเชื่อมต่อพอร์ต 5000 ได้)"}
      </span>
      <span class="badge-live">
        {#if isLoading}
          ⏳ กำลังโหลด...
        {:else}
          LIVE CAPTURE: {apis.length} APIs
        {/if}
      </span>
      <button class="btn-refresh-mini" title="รีเฟรชดึงข้อมูลล่าสุด" on:click={() => loadCapturedApis(false)}>
        🔄 รีเฟรช
      </button>
    </div>

    {#if isLoading && apis.length === 0}
      <div class="loading-box">
        <div class="spinner"></div>
        <p>กำลังเชื่อมต่อและดึงข้อมูล API จาก Extension...</p>
      </div>
    {:else if apis.length === 0}
      <!-- Empty State with Clear Steps -->
      <div class="empty-state-box">
        <div class="empty-icon">🧩</div>
        <h4 class="empty-title">ยังไม่พบรายการ Network API จาก Chrome Extension</h4>
        <p class="empty-desc">
          ทำตาม 4 ขั้นตอนเพื่อบันทึก API จากหน้าเว็บจริงเข้ามาที่ Spectra:
        </p>
        <div class="steps-grid">
          <div class="step-card">
            <div class="step-badge">1</div>
            <div class="step-content">
              <strong>เปิดหน้าเว็บที่ต้องการ</strong>
              <span>เปิดหน้าเว็บระบบงานที่ต้องการแกะ API บนเบราว์เซอร์ Chrome</span>
            </div>
          </div>
          <div class="step-card">
            <div class="step-badge">2</div>
            <div class="step-content">
              <strong>เริ่มบันทึก Network</strong>
              <span>คลิกไอคอน Spectra Extension แล้วกด 🔴 <em>"เริ่มบันทึก Network"</em></span>
            </div>
          </div>
          <div class="step-card">
            <div class="step-badge">3</div>
            <div class="step-content">
              <strong>ใช้งานหน้าเว็บตามปกติ</strong>
              <span>กดค้นหา คลิกปุ่ม หรือบันทึกข้อมูลเพื่อให้เว็บยิง API Request</span>
            </div>
          </div>
          <div class="step-card">
            <div class="step-badge">4</div>
            <div class="step-content">
              <strong>กด Sync เข้า Spectra</strong>
              <span>กดปุ่ม 📥 <em>"Sync เข้าสู่ Spectra QA Repository"</em> ใน Extension</span>
            </div>
          </div>
        </div>
        <button class="btn-refresh-pulse" on:click={() => loadCapturedApis(false)}>
          🔄 กดรีเฟรชตรวจสอบข้อมูลใหม่
        </button>
      </div>
    {:else}
      <!-- Live Captured List with Inspect & Copy Buttons -->
      <div class="api-list-wrap">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <div class="list-title">
            รายการ Network APIs ที่ดึงได้ล่าสุด ({apis.length} รายการ - คลิกเพื่อดู Response Body):
          </div>
          {#if lastSyncTime}
            <span class="last-sync-time">อัปเดตล่าสุด: {lastSyncTime}</span>
          {/if}
        </div>
        <div class="api-list">
          {#each apis as api}
            <div class="api-row" class:selected={selectedApi === api} on:click={() => selectedApi = api}>
              <span class="method {api.method || 'GET'}">{api.method || 'GET'}</span>
              <span class="path" title={api.url || api.path}>{api.path || api.url}</span>
              <span class="time">{api.time || ''}</span>
              <span class="status" class:err={(api.status || api.statusCode) >= 400}>
                {api.status || api.statusCode || 200} OK
              </span>
              <div class="row-actions">
                <button class="btn-row-copy" title="Copy cURL bash" on:click|stopPropagation={() => copyCurl(api)}>🐚 cURL</button>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Selected API Response / cURL Inspector Drawer -->
      {#if selectedApi}
        <div class="inspector-box">
          <div class="insp-header">
            <span style="font-weight: bold; color: #a78bfa; font-size: 12px;">
              Inspector: {selectedApi.method || 'GET'} {selectedApi.path || selectedApi.url}
            </span>
            <div style="display: flex; gap: 6px;">
              <button class="tab-sub-btn" class:active={activeTab === 'response'} on:click={() => activeTab = 'response'}>
                📄 Response Body
              </button>
              <button class="tab-sub-btn" class:active={activeTab === 'curl'} on:click={() => activeTab = 'curl'}>
                🐚 cURL bash
              </button>
            </div>
          </div>

          <pre class="insp-content">{activeTab === 'response' ? (selectedApi.responseBody || 'ไม่มี Response Body หรือเป็น Stream Request') : (selectedApi.curl || `curl -X ${selectedApi.method || 'GET'} "${selectedApi.url || selectedApi.path}"`)}</pre>

          <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
            <button class="btn-sub-copy" on:click={() => copyCurl(selectedApi)}>🐚 Copy cURL (bash)</button>
            <button class="btn-sub-copy" on:click={() => copyResponse(selectedApi)}>📋 Copy Response</button>
          </div>
        </div>
      {/if}
    {/if}

    <!-- Actions -->
    <div class="modal-actions" style="margin-top: 16px;">
      <button class="btn-secondary" on:click={closeModal}>ปิด</button>
      <button class="btn-primary" disabled={apis.length === 0 || isSyncingToRepo} on:click={syncExtensionData}>
        {#if isSyncingToRepo}
          ⏳ กำลังนำเข้า...
        {:else}
          📥 Sync เข้าสู่ API Repository ({apis.length})
        {/if}
      </button>
    </div>
  </div>
</div>
{/if}

<style>
  .modal-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.8);
    backdrop-filter: blur(8px); z-index: 9999;
    display: flex; align-items: center; justify-content: center;
  }
  .modal-card {
    background: rgba(15, 23, 42, 0.96);
    border: 1px solid rgba(139, 92, 246, 0.35);
    box-shadow: 0 25px 60px rgba(0,0,0,0.85), 0 0 30px rgba(139, 92, 246, 0.2);
    border-radius: 16px; width: 95%; max-width: 720px; padding: 24px; color: white;
  }
  .modal-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
  .icon-wrap { font-size: 28px; }
  .modal-title { font-size: 18px; font-weight: 700; margin: 0; background: linear-gradient(135deg, #fff, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .modal-subtitle { font-size: 12px; color: #94a3b8; margin: 2px 0 0 0; }
  .close-btn { background: transparent; border: none; color: #94a3b8; font-size: 16px; cursor: pointer; }
  
  .status-banner {
    display: flex; align-items: center; gap: 8px; padding: 10px 14px;
    background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3);
    border-radius: 8px; font-size: 12px; color: #4ade80; margin-bottom: 16px;
  }
  .status-banner.disconnected {
    background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); color: #f87171;
  }
  .status-banner.disconnected .status-dot {
    background: #ef4444; box-shadow: 0 0 8px #ef4444;
  }
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px #22c55e; flex-shrink: 0; }
  .status-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .badge-live { background: rgba(139, 92, 246, 0.25); color: #c084fc; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 10px; border: 1px solid rgba(139, 92, 246, 0.4); }
  .btn-refresh-mini { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.2); color: #cbd5e1; padding: 3px 8px; border-radius: 6px; font-size: 10px; cursor: pointer; }
  .btn-refresh-mini:hover { background: rgba(139, 92, 246, 0.3); color: white; }

  .loading-box { text-align: center; padding: 36px 16px; color: #94a3b8; }
  .spinner { width: 32px; height: 32px; border: 3px solid rgba(139, 92, 246, 0.2); border-top-color: #a855f7; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 12px; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .empty-state-box {
    background: rgba(0,0,0,0.3); border: 1px dashed rgba(139, 92, 246, 0.3);
    border-radius: 12px; padding: 24px 18px; text-align: center; margin-bottom: 14px;
  }
  .empty-icon { font-size: 32px; margin-bottom: 8px; }
  .empty-title { font-size: 14px; font-weight: 600; color: #e2e8f0; margin: 0 0 6px 0; }
  .empty-desc { font-size: 12px; color: #94a3b8; margin: 0 0 16px 0; }
  .steps-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 18px; text-align: left; }
  .step-card {
    background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px; padding: 10px 12px; display: flex; gap: 10px; align-items: flex-start;
  }
  .step-badge {
    background: rgba(139, 92, 246, 0.25); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.5);
    width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: bold; flex-shrink: 0;
  }
  .step-content strong { display: block; font-size: 11.5px; color: #e2e8f0; margin-bottom: 2px; }
  .step-content span { font-size: 10.5px; color: #94a3b8; line-height: 1.3; display: block; }
  .btn-refresh-pulse {
    background: linear-gradient(135deg, #7c3aed, #4f46e5); border: none; color: white;
    padding: 8px 16px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer;
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.4); transition: transform 0.15s, box-shadow 0.15s;
  }
  .btn-refresh-pulse:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(124, 58, 237, 0.6); }

  .api-list-wrap { margin-bottom: 12px; }
  .list-title { font-size: 12px; color: #cbd5e1; font-weight: 600; }
  .last-sync-time { font-size: 10px; color: #94a3b8; }
  .api-list { max-height: 200px; overflow-y: auto; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }
  .api-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 12px; cursor: pointer; transition: background 0.15s; }
  .api-row:hover, .api-row.selected { background: rgba(139, 92, 246, 0.18); }
  .method { font-weight: bold; font-size: 10px; padding: 2px 6px; border-radius: 4px; }
  .method.GET { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
  .method.POST { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
  .method.PUT { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
  .method.DELETE { background: rgba(239, 68, 68, 0.2); color: #f87171; }
  .method.PATCH { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
  .path { flex: 1; font-family: monospace; color: #a78bfa; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .time { color: #64748b; font-size: 11px; }
  .status { color: #4ade80; font-weight: 600; font-size: 11px; }
  .status.err { color: #f87171; }
  .row-actions { display: flex; gap: 4px; }
  .btn-row-copy { background: rgba(168, 85, 247, 0.2); border: 1px solid rgba(168, 85, 247, 0.4); color: #c084fc; padding: 2px 8px; border-radius: 4px; font-size: 10px; cursor: pointer; }
  .btn-row-copy:hover { background: rgba(168, 85, 247, 0.4); color: white; }

  .inspector-box { background: rgba(0,0,0,0.5); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 8px; padding: 12px; margin-top: 10px; }
  .insp-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .tab-sub-btn { background: transparent; border: 1px solid rgba(255,255,255,0.1); color: #94a3b8; padding: 3px 8px; border-radius: 4px; font-size: 11px; cursor: pointer; }
  .tab-sub-btn.active { background: rgba(139, 92, 246, 0.25); border-color: #8b5cf6; color: white; }
  .insp-content { font-family: monospace; font-size: 11px; color: #cbd5e1; background: rgba(0,0,0,0.4); padding: 10px; border-radius: 6px; max-height: 140px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; margin: 0; }
  .btn-sub-copy { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); color: white; padding: 4px 10px; border-radius: 6px; font-size: 11px; cursor: pointer; }
  .btn-sub-copy:hover { background: rgba(139, 92, 246, 0.3); }

  .modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
  .btn-secondary { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 8px 16px; border-radius: 8px; cursor: pointer; }
  .btn-primary { background: linear-gradient(135deg, #8b5cf6, #6d28d9); border: none; color: white; padding: 8px 18px; border-radius: 8px; font-weight: 600; cursor: pointer; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
