<script>
  import { fade, scale } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { createEventDispatcher } from "svelte";

  const dispatch = createEventDispatcher();

  export var showModal = false;
  export var projectId = null;

  var isConnected = true;
  var selectedApi = null;
  var activeTab = "response"; // 'response' | 'curl'

  var sampleApis = [
    { 
      method: "GET", 
      path: "/api/projects", 
      status: 200, 
      time: "14:28:10",
      curl: "curl -X GET \"/api/projects\" -H \"Authorization: Bearer token_sample\"",
      responseBody: "{\n  \"success\": true,\n  \"projects\": [\n    {\n      \"id\": 1,\n      \"project_code\": \"69A - TIFFA-RGP\",\n      \"name\": \"TIFFA Cargo Import System\"\n    }\n  ]\n}"
    },
    { 
      method: "POST", 
      path: "/api/login", 
      status: 200, 
      time: "14:28:15",
      curl: "curl -X POST \"/api/login\" -H \"Content-Type: application/json\" -d '{\"username\":\"admin@domain.com\",\"password\":\"••••••••\"}'",
      responseBody: "{\n  \"success\": true,\n  \"token\": \"eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9...\",\n  \"user\": {\n    \"username\": \"admin@domain.com\",\n    \"role\": \"admin\"\n  }\n}"
    },
    { 
      method: "POST", 
      path: "/api/upload", 
      status: 200, 
      time: "14:28:22",
      curl: "curl -X POST \"/api/upload\" -H \"Content-Type: multipart/form-data\"",
      responseBody: "{\n  \"success\": true,\n  \"filename\": \"cargo_manifest.pdf\",\n  \"pages_processed\": 4\n}"
    },
    { 
      method: "GET", 
      path: "/api/users", 
      status: 200, 
      time: "14:28:30",
      curl: "curl -X GET \"/api/users\" -H \"Authorization: Bearer token_sample\"",
      responseBody: "{\n  \"success\": true,\n  \"users\": [\n    {\n      \"user_id\": 1,\n      \"username\": \"admin@domain.com\",\n      \"role\": \"admin\"\n    }\n  ]\n}"
    }
  ];

  function syncExtensionData() {
    toast(`Syncing ${sampleApis.length} APIs from Chrome Extension...`, "info");
    setTimeout(() => {
      toast(`✅ Sync สำเร็จ! นำเข้า ${sampleApis.length} API รายการเข้าสู่ Repository เรียบร้อยแล้ว`, "success");
      dispatch("synced", sampleApis);
      showModal = false;
    }, 1200);
  }

  function copyCurl(api) {
    const text = api ? api.curl : (selectedApi ? selectedApi.curl : "");
    if (text) {
      navigator.clipboard.writeText(text);
      toast("🐚 คัดลอก cURL (bash) เรียบร้อยแล้ว!", "success");
    }
  }

  function copyResponse(api) {
    const text = api ? api.responseBody : (selectedApi ? selectedApi.responseBody : "");
    if (text) {
      navigator.clipboard.writeText(text);
      toast("📋 คัดลอก Response Body เรียบร้อยแล้ว!", "success");
    }
  }

  function closeModal() {
    showModal = false;
    selectedApi = null;
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
    <div class="status-banner" class:connected={isConnected}>
      <div class="status-dot"></div>
      <span>{isConnected ? "Chrome Extension Connected (Listening on port 5000)" : "Extension Disconnected"}</span>
      <span class="badge-live">LIVE CAPTURE: {sampleApis.length} APIs</span>
    </div>

    <!-- Live Captured List with Inspect & Copy Buttons -->
    <div class="api-list-wrap">
      <div class="list-title">รายการ Network APIs ที่ดึงได้ล่าสุด (คลิกเพื่อดู Response Body):</div>
      <div class="api-list">
        {#each sampleApis as api}
          <div class="api-row" class:selected={selectedApi === api} on:click={() => selectedApi = api}>
            <span class="method {api.method}">{api.method}</span>
            <span class="path">{api.path}</span>
            <span class="time">{api.time}</span>
            <span class="status">200 OK</span>
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
          <span style="font-weight: bold; color: #a78bfa; font-size: 12px;">Inspector: {selectedApi.method} {selectedApi.path}</span>
          <div style="display: flex; gap: 6px;">
            <button class="tab-sub-btn" class:active={activeTab === 'response'} on:click={() => activeTab = 'response'}>📄 Response Body</button>
            <button class="tab-sub-btn" class:active={activeTab === 'curl'} on:click={() => activeTab = 'curl'}>🐚 cURL bash</button>
          </div>
        </div>

        <pre class="insp-content">{activeTab === 'response' ? selectedApi.responseBody : selectedApi.curl}</pre>

        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
          <button class="btn-sub-copy" on:click={() => copyCurl(selectedApi)}>🐚 Copy cURL (bash)</button>
          <button class="btn-sub-copy" on:click={() => copyResponse(selectedApi)}>📋 Copy Response</button>
        </div>
      </div>
    {/if}

    <!-- Actions -->
    <div class="modal-actions" style="margin-top: 16px;">
      <button class="btn-secondary" on:click={closeModal}>ปิด</button>
      <button class="btn-primary" on:click={syncExtensionData}>
        📥 Sync เข้าสู่ API Repository
      </button>
    </div>
  </div>
</div>
{/if}

<style>
  .modal-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.75);
    backdrop-filter: blur(8px); z-index: 9999;
    display: flex; align-items: center; justify-content: center;
  }
  .modal-card {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(139, 92, 246, 0.3);
    box-shadow: 0 25px 60px rgba(0,0,0,0.8), 0 0 30px rgba(139, 92, 246, 0.2);
    border-radius: 16px; width: 95%; max-width: 680px; padding: 24px; color: white;
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
  .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px #22c55e; }
  .badge-live { margin-left: auto; background: rgba(139, 92, 246, 0.2); color: #c084fc; padding: 2px 8px; border-radius: 12px; font-weight: 600; font-size: 10px; }

  .api-list-wrap { margin-bottom: 12px; }
  .list-title { font-size: 12px; color: #cbd5e1; margin-bottom: 8px; font-weight: 600; }
  .api-list { max-height: 180px; overflow-y: auto; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; }
  .api-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 12px; cursor: pointer; transition: background 0.15s; }
  .api-row:hover, .api-row.selected { background: rgba(139, 92, 246, 0.15); }
  .method { font-weight: bold; font-size: 10px; padding: 2px 6px; border-radius: 4px; }
  .method.GET { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
  .method.POST { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
  .path { flex: 1; font-family: monospace; color: #a78bfa; }
  .time { color: #64748b; font-size: 11px; }
  .status { color: #4ade80; font-weight: 600; font-size: 11px; }
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
</style>
