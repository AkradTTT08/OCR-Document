<script>
  import { onMount } from "svelte";
  import { toast } from "./toastStore.js";
  import CustomSelect from "./CustomSelect.svelte";
  import { fade, fly } from "svelte/transition";

  let projects = [];
  let selectedProjectId = null;
  let apiCollections = [];
  let isLoading = false;
  let isUploading = false;
  let uploadFile = null;

  onMount(async () => {
    await fetchProjects();
  });

  async function fetchProjects() {
    try {
      const res = await fetch("http://127.0.0.1:5000/api/projects");
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
        if (projects.length > 0) {
          selectedProjectId = projects[0].id || projects[0].project_id;
          fetchCollections(selectedProjectId);
        }
      }
    } catch (err) {
      console.error("Failed to fetch projects", err);
    }
  }

  async function fetchCollections(projectId) {
    if (!projectId) return;
    isLoading = true;
    try {
      // Mock API call to get collections for a project
      // const res = await fetch(`http://127.0.0.1:5000/api/projects/${projectId}/api-collections`);
      // const data = await res.json();
      // apiCollections = data.collections || [];
      
      // MOCK DATA for demonstration
      setTimeout(() => {
        apiCollections = [
          { id: 1, name: "WMS_API_v1.0.json", format: "Swagger/OpenAPI", uploaded_at: new Date().toISOString(), version: "1.0", file_size: "45 KB" },
          { id: 2, name: "PMRP_Postman_Collection.json", format: "Postman Collection", uploaded_at: new Date(Date.now() - 86400000).toISOString(), version: "1.1", file_size: "120 KB" }
        ];
        isLoading = false;
      }, 500);
    } catch (err) {
      console.error("Failed to fetch collections", err);
      isLoading = false;
    }
  }

  function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
      if (file.name.endsWith('.json') || file.name.endsWith('.yaml') || file.name.endsWith('.yml')) {
        uploadFile = file;
      } else {
        toast("Please upload a JSON or YAML file.", "error");
        e.target.value = null;
      }
    }
  }

  async function handleUpload() {
    if (!uploadFile) {
      toast("Please select a file first.", "warning");
      return;
    }
    if (!selectedProjectId) {
      toast("Please select a project.", "warning");
      return;
    }

    isUploading = true;
    try {
      // Mock upload process
      /*
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("project_id", selectedProjectId);
      const res = await fetch("http://127.0.0.1:5000/api/api-collections/upload", {
        method: "POST",
        body: formData
      });
      if (!res.ok) throw new Error("Upload failed");
      */
      
      await new Promise(r => setTimeout(r, 1200)); // simulate network
      
      // Add to list
      const newCol = {
        id: Date.now(),
        name: uploadFile.name,
        format: uploadFile.name.endsWith('.yaml') || uploadFile.name.endsWith('.yml') ? "OpenAPI (YAML)" : "OpenAPI / Postman",
        uploaded_at: new Date().toISOString(),
        version: "Draft",
        file_size: (uploadFile.size / 1024).toFixed(1) + " KB"
      };
      
      apiCollections = [newCol, ...apiCollections];
      toast("API Collection uploaded successfully", "success");
      uploadFile = null;
      document.getElementById('api-file-upload').value = '';
    } catch (err) {
      console.error(err);
      toast("Failed to upload file", "error");
    } finally {
      isUploading = false;
    }
  }

  let itemToDelete = null;
  let showDeleteModal = false;

  function confirmDelete(id) {
    itemToDelete = id;
    showDeleteModal = true;
  }

  function executeDelete() {
    if (itemToDelete) {
      apiCollections = apiCollections.filter(c => c.id !== itemToDelete);
      toast("Deleted successfully", "success");
      itemToDelete = null;
      showDeleteModal = false;
    }
  }
  
  function cancelDelete() {
    itemToDelete = null;
    showDeleteModal = false;
  }
  
  // Run API Test
  function runApiTest(id) {
    const col = apiCollections.find(c => c.id === id);
    if (!col) return;
    toast(`Running connection test for ${col.name}...`, "info");
    
    // Simulate API ping
    setTimeout(() => {
      const isSuccess = Math.random() > 0.2; // 80% success mock
      if (isSuccess) {
        toast(`✅ API "${col.name}" is reachable (200 OK)`, "success");
      } else {
        toast(`❌ Failed to reach "${col.name}" (Connection Timeout)`, "error");
      }
    }, 1500);
  }

  // Manual API Logic
  let showManualModal = false;
  let manualApiData = {
    name: "",
    url: "",
    method: "GET",
    headers: "{\n  \"Content-Type\": \"application/json\"\n}",
    body: ""
  };
  
  function handleNameInput(e) {
    const val = e.target.value.trim();
    if (val.toLowerCase().startsWith("curl ")) {
      try {
        let parsedUrl = "";
        // extract URL
        const urlMatch = val.match(/curl\s+(?:-X\s+[A-Z]+\s+)?['"]?([^'"\s]+)['"]?/i);
        if (urlMatch) {
            parsedUrl = urlMatch[1];
            manualApiData.url = parsedUrl;
        }
        
        // extract method
        const methodMatch = val.match(/-X\s+([A-Z]+)/i);
        if (methodMatch) {
            manualApiData.method = methodMatch[1].toUpperCase();
        } else if (val.includes('--data') || val.includes('-d ')) {
            manualApiData.method = "POST";
        }
        
        // extract headers
        const headerMatches = [...val.matchAll(/-H\s+['"]([^'"]+)['"]/gi)];
        if (headerMatches.length > 0) {
            const headers = {};
            headerMatches.forEach(m => {
                const parts = m[1].split(':');
                if (parts.length >= 2) {
                    headers[parts[0].trim()] = parts.slice(1).join(':').trim();
                }
            });
            manualApiData.headers = JSON.stringify(headers, null, 2);
        }
        
        // extract body
        const dataMatch = val.match(/(?:--data-raw|--data|-d)\s+['"](.*?)['"]/is);
        if (dataMatch) {
            manualApiData.body = dataMatch[1];
        }

        // Generate a name from URL
        try {
            const urlObj = new URL(parsedUrl);
            manualApiData.name = "cURL: " + (urlObj.pathname.split('/').pop() || "Endpoint");
        } catch {
            manualApiData.name = "Imported cURL API";
        }
        
        toast("cURL imported successfully!", "success");
      } catch (err) {
        console.error("Failed to parse cURL", err);
      }
    }
  }

  function saveManualApi() {
    if (!manualApiData.name || !manualApiData.url) {
      toast("Please provide both Name and URL", "warning");
      return;
    }
    
    const newCol = {
      id: Date.now(),
      name: manualApiData.name,
      format: `Manual (${manualApiData.method})`,
      uploaded_at: new Date().toISOString(),
      version: "1.0",
      file_size: "-",
      url: manualApiData.url,
      headers: manualApiData.headers,
      body: manualApiData.body
    };
    
    apiCollections = [newCol, ...apiCollections];
    toast("Manual API added successfully", "success");
    showManualModal = false;
    manualApiData = { name: "", url: "", method: "GET", headers: "{\n  \"Content-Type\": \"application/json\"\n}", body: "" };
  }

  function formatDate(isoString) {
    const d = new Date(isoString);
    return d.toLocaleDateString('th-TH') + ' ' + d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });
  }

  $: projectOptions = projects.map(p => ({
    value: p.id || p.project_id,
    label: p.project_code || p.name || `Project ${p.id}`
  }));

  function handleProjectChange(e) {
    selectedProjectId = e.detail;
    fetchCollections(selectedProjectId);
  }
</script>

<div class="api-admin-container" in:fade>
  <div class="header">
    <div class="title-area">
      <h2>API Collections / Specification</h2>
      <p>Manage API Specifications (Swagger/OpenAPI/Postman) as a Single Source of Truth for generating K6 Performance Test scripts.</p>
    </div>
  </div>

  <div class="main-content">
    <div class="left-panel">
      <!-- Project Selection -->
      <div class="card glass-panel">
        <h3>1. เลือกโปรเจกต์ (Select Project)</h3>
        <div class="form-group">
          {#if projectOptions.length > 0}
            <CustomSelect 
              options={projectOptions} 
              value={selectedProjectId} 
              placeholder="Select a project..."
              on:change={handleProjectChange} 
            />
          {:else}
            <div class="loading-text">Loading projects...</div>
          {/if}
        </div>
      </div>

      <!-- File Upload -->
      <div class="card glass-panel upload-card" class:disabled={!selectedProjectId}>
        <h3>2. อัปโหลด API Spec</h3>
        <p class="desc">รองรับไฟล์รูปแบบ <code>.json</code>, <code>.yaml</code> (Swagger, OpenAPI v2/v3, Postman Collection)</p>
        
        <div class="upload-area">
          <input type="file" id="api-file-upload" accept=".json,.yaml,.yml" class="hidden-input" on:change={handleFileSelect} disabled={!selectedProjectId}>
          <label for="api-file-upload" class="upload-dropzone" class:has-file={!!uploadFile}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="40" height="40" class="upload-icon">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <div class="upload-text">
              {#if uploadFile}
                <span class="file-name">{uploadFile.name}</span>
                <span class="file-size">({(uploadFile.size / 1024).toFixed(1)} KB)</span>
              {:else}
                <span class="primary-text">Click to browse</span> or drag and drop<br>
                <span class="sub-text">JSON, YAML only</span>
              {/if}
            </div>
          </label>
        </div>

        <button class="btn-primary upload-btn" disabled={!uploadFile || isUploading} on:click={handleUpload}>
          {#if isUploading}
            <span class="spinner"></span> Uploading...
          {:else}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            Save to Repository
          {/if}
        </button>
      </div>

      <!-- Add Manual API -->
      <div class="card glass-panel upload-card" class:disabled={!selectedProjectId} style="margin-top: -4px;">
        <h3 style="margin-bottom: 8px;">หรือเพิ่ม API แบบ Manual</h3>
        <p class="desc" style="margin-bottom: 12px;">ระบุ Endpoint ทีละรายการด้วยตัวเอง</p>
        <button class="btn-secondary upload-btn" style="background: rgba(255,255,255,0.05); color: #cbd5e1; border: 1px dashed rgba(255,255,255,0.2);" disabled={!selectedProjectId} on:click={() => showManualModal = true}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 5v14M5 12h14"></path></svg>
          Add API Manual
        </button>
      </div>
    </div>

    <div class="right-panel">
      <div class="card glass-panel full-height">
        <div class="card-header">
          <h3>Repository (Source of Truth)</h3>
          <span class="badge">{apiCollections.length} Files</span>
        </div>
        
        <div class="collection-list">
          {#if isLoading}
            <div class="loading-state">
              <div class="spinner"></div>
              <span>Loading collections...</span>
            </div>
          {:else if apiCollections.length === 0}
            <div class="empty-state">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" width="48" height="48">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="9" y1="15" x2="15" y2="15"></line>
              </svg>
              <p>ไม่มี API Collection สำหรับโปรเจกต์นี้</p>
            </div>
          {:else}
            {#each apiCollections as col (col.id)}
              <div class="collection-item" in:fly={{ y: 20, duration: 300 }}>
                <div class="col-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                </div>
                <div class="col-info">
                  <div class="col-name">{col.name}</div>
                  <div class="col-meta">
                    <span class="meta-tag">{col.format}</span>
                    <span class="meta-dot">•</span>
                    <span>Version {col.version}</span>
                    <span class="meta-dot">•</span>
                    <span>{col.file_size}</span>
                  </div>
                  <div class="col-date">Uploaded on {formatDate(col.uploaded_at)}</div>
                </div>
                <div class="col-actions">
                  <button class="btn-icon" title="Run / Test API" style="color: #10b981;" on:click={() => runApiTest(col.id)}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                  </button>
                  <button class="btn-icon" title="View/Edit" style="color: #60a5fa;">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                  </button>
                  <button class="btn-icon" title="Delete" style="color: #f87171;" on:click={() => confirmDelete(col.id)}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                  </button>
                </div>
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Delete Confirmation Modal -->
{#if showDeleteModal}
<div class="modal-backdrop" transition:fade={{duration: 200}}>
  <div class="modal-content glass-card" transition:fly={{y: -20, duration: 300}}>
    <div class="modal-icon-warning">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
        <line x1="12" y1="9" x2="12" y2="13"></line>
        <line x1="12" y1="17" x2="12.01" y2="17"></line>
      </svg>
    </div>
    <h3 class="modal-title">ยืนยันการลบข้อมูล</h3>
    <p class="modal-desc">
      คุณแน่ใจหรือไม่ว่าต้องการลบ <strong>API Collection</strong> นี้?<br>
      <span class="warning-text">การกระทำนี้อาจส่งผลกระทบต่อ Performance Testing Scripts ที่อ้างอิงอยู่ และไม่สามารถกู้คืนได้</span>
    </p>
    <div class="modal-actions">
      <button class="btn-cancel" on:click={cancelDelete}>ยกเลิก</button>
      <button class="btn-confirm-delete" on:click={executeDelete}>ใช่, ยืนยันการลบ</button>
    </div>
  </div>
</div>
{/if}

<!-- Add Manual API Modal -->
{#if showManualModal}
<div class="modal-backdrop" transition:fade={{duration: 200}}>
  <div class="modal-content glass-card" transition:fly={{y: -20, duration: 300}} style="text-align: left; align-items: stretch; max-width: 900px; width: 95%;">
    <h3 class="modal-title" style="margin-bottom: 20px; text-align: center;">Add API Manual</h3>
    
    <div style="display: grid; grid-template-columns: 1fr 1.5fr; gap: 24px;">
      <!-- Left Column: Basics -->
      <div class="modal-col">
        <div class="form-group">
          <label style="display: block; margin-bottom: 6px; font-size: 0.9rem; color: #cbd5e1;">API Name / Import cURL</label>
          <input type="text" class="manual-input" bind:value={manualApiData.name} on:input={handleNameInput} placeholder="e.g. Get User Profile (or paste cURL here)">
        </div>

        <div class="form-group">
          <label style="display: block; margin-bottom: 6px; font-size: 0.9rem; color: #cbd5e1;">Method</label>
          <CustomSelect 
            options={[
              { value: "GET", label: "GET" },
              { value: "POST", label: "POST" },
              { value: "PUT", label: "PUT" },
              { value: "PATCH", label: "PATCH" },
              { value: "DELETE", label: "DELETE" }
            ]}
            value={manualApiData.method}
            on:change={(e) => manualApiData.method = e.detail}
          />
        </div>
        
        <div class="form-group">
          <label style="display: block; margin-bottom: 6px; font-size: 0.9rem; color: #cbd5e1;">Endpoint URL</label>
          <input type="text" class="manual-input" bind:value={manualApiData.url} placeholder="https://api.example.com/v1/users">
        </div>
      </div>

      <!-- Right Column: Headers & Body -->
      <div class="modal-col" style="display: flex; flex-direction: column; gap: 16px;">
        <div class="form-group" style="margin: 0;">
          <label style="display: block; margin-bottom: 6px; font-size: 0.9rem; color: #cbd5e1;">Headers (JSON)</label>
          <textarea class="manual-input" style="height: 120px; font-family: monospace; resize: vertical;" bind:value={manualApiData.headers} placeholder="&#123;&quot;Content-Type&quot;: &quot;application/json&quot;&#125;"></textarea>
        </div>
        
        <div class="form-group" style="margin: 0; flex: 1; display: flex; flex-direction: column;">
          <label style="display: block; margin-bottom: 6px; font-size: 0.9rem; color: #cbd5e1;">Body</label>
          <textarea class="manual-input" style="flex: 1; min-height: 220px; font-family: monospace; resize: vertical;" bind:value={manualApiData.body} placeholder="&#123;&quot;key&quot;: &quot;value&quot;&#125;"></textarea>
        </div>
      </div>
    </div>

    <div class="modal-actions" style="margin-top: 24px; justify-content: flex-end;">
      <button class="btn-cancel" style="flex: none; width: 120px;" on:click={() => showManualModal = false}>Cancel</button>
      <button class="btn-confirm" style="flex: none; width: 160px;" on:click={saveManualApi}>Save API</button>
    </div>
  </div>
</div>
{/if}

<style>
  .api-admin-container {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 24px 32px;
    box-sizing: border-box;
    overflow-y: auto;
  }

  .header {
    margin-bottom: 24px;
  }
  
  .title-area h2 {
    font-size: 1.5rem;
    font-weight: 600;
    color: #fff;
    margin: 0 0 8px 0;
  }
  
  .title-area p {
    color: var(--text-muted, #94a3b8);
    font-size: 0.95rem;
    margin: 0;
  }

  .main-content {
    display: grid;
    grid-template-columns: 350px 1fr;
    gap: 24px;
    align-items: start;
    flex: 1;
    min-height: 0;
  }

  .left-panel {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .right-panel {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .glass-panel {
    background: rgba(30, 41, 59, 0.4);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  }
  
  .full-height {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  h3 {
    font-size: 1.1rem;
    color: #e2e8f0;
    margin: 0 0 16px 0;
    font-weight: 500;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .upload-card.disabled {
    opacity: 0.6;
    pointer-events: none;
  }

  .desc {
    font-size: 0.85rem;
    color: #94a3b8;
    margin: -8px 0 16px 0;
  }
  
  code {
    background: rgba(0,0,0,0.3);
    padding: 2px 6px;
    border-radius: 4px;
    color: #a78bfa;
    font-size: 0.8rem;
  }

  .hidden-input {
    display: none;
  }

  .upload-dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 30px 20px;
    border: 2px dashed rgba(99, 102, 241, 0.4);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.4);
    cursor: pointer;
    transition: all 0.2s;
    text-align: center;
  }

  .upload-dropzone:hover {
    border-color: rgba(99, 102, 241, 0.8);
    background: rgba(99, 102, 241, 0.05);
  }

  .upload-dropzone.has-file {
    border: 2px solid rgba(16, 185, 129, 0.5);
    background: rgba(16, 185, 129, 0.05);
  }
  
  .upload-dropzone.has-file .upload-icon {
    color: #10b981;
  }

  .upload-icon {
    color: #6366f1;
    margin-bottom: 12px;
  }

  .upload-text {
    font-size: 0.9rem;
    color: #cbd5e1;
  }

  .primary-text {
    color: #6366f1;
    font-weight: 500;
  }

  .sub-text {
    font-size: 0.8rem;
    color: #64748b;
    margin-top: 4px;
    display: block;
  }
  
  .file-name {
    display: block;
    font-weight: 500;
    color: #10b981;
    word-break: break-all;
  }
  
  .file-size {
    display: block;
    font-size: 0.8rem;
    color: #94a3b8;
    margin-top: 4px;
  }

  .upload-btn {
    width: 100%;
    margin-top: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px;
    border: none;
    border-radius: 8px;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white;
    font-weight: 500;
    cursor: pointer;
    transition: opacity 0.2s, transform 0.1s;
  }
  
  .upload-btn:hover:not(:disabled) {
    opacity: 0.9;
  }
  
  .upload-btn:active:not(:disabled) {
    transform: scale(0.98);
  }
  
  .upload-btn:disabled {
    background: #334155;
    color: #94a3b8;
    cursor: not-allowed;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    padding-bottom: 12px;
  }
  
  .card-header h3 {
    margin: 0;
  }
  
  .badge {
    background: rgba(99, 102, 241, 0.2);
    color: #c7d2fe;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid rgba(99, 102, 241, 0.3);
  }

  .collection-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .collection-item {
    display: flex;
    align-items: center;
    padding: 16px;
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px;
    transition: all 0.2s;
  }
  
  .collection-item:hover {
    background: rgba(30, 41, 59, 0.8);
    border-color: rgba(99, 102, 241, 0.3);
  }

  .col-icon {
    width: 40px;
    height: 40px;
    background: rgba(99, 102, 241, 0.1);
    color: #818cf8;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 16px;
    flex-shrink: 0;
  }

  .col-info {
    flex: 1;
    min-width: 0;
  }

  .col-name {
    font-weight: 500;
    color: #f1f5f9;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .col-meta {
    display: flex;
    align-items: center;
    font-size: 0.75rem;
    color: #94a3b8;
    margin-bottom: 4px;
  }
  
  .meta-tag {
    background: rgba(255,255,255,0.1);
    padding: 1px 6px;
    border-radius: 4px;
    color: #cbd5e1;
  }
  
  .meta-dot {
    margin: 0 6px;
    opacity: 0.5;
  }

  .col-date {
    font-size: 0.7rem;
    color: #64748b;
  }

  .col-actions {
    display: flex;
    gap: 8px;
    opacity: 0.6;
    transition: opacity 0.2s;
  }
  
  .collection-item:hover .col-actions {
    opacity: 1;
  }

  .btn-icon {
    background: rgba(0,0,0,0.2);
    border: 1px solid transparent;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .btn-icon:hover {
    background: rgba(255,255,255,0.1);
    border-color: rgba(255,255,255,0.1);
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #64748b;
    gap: 12px;
  }
  
  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #94a3b8;
    gap: 16px;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid rgba(255,255,255,0.1);
    border-top-color: #818cf8;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  /* Scrollbar for collection list */
  .collection-list::-webkit-scrollbar {
    width: 6px;
  }
  .collection-list::-webkit-scrollbar-track {
    background: rgba(0,0,0,0.1);
    border-radius: 4px;
  }
  .collection-list::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
  }
  .collection-list::-webkit-scrollbar-thumb:hover {
    background: rgba(255,255,255,0.2);
  }

  /* Modal Styles */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(15, 23, 42, 0.75);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content.glass-card {
    background: rgba(30, 41, 59, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    border-radius: 16px;
    padding: 32px;
    max-width: 400px;
    width: 90%;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .modal-icon-warning {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 20px;
    border: 2px solid rgba(239, 68, 68, 0.2);
  }

  .modal-title {
    font-size: 1.25rem;
    color: #f1f5f9;
    margin: 0 0 12px 0;
    font-weight: 600;
  }

  .modal-desc {
    font-size: 0.9rem;
    color: #94a3b8;
    margin: 0 0 24px 0;
    line-height: 1.5;
  }

  .warning-text {
    color: #ef4444;
    font-size: 0.85rem;
    display: block;
    margin-top: 8px;
    padding: 8px;
    background: rgba(239, 68, 68, 0.05);
    border-radius: 6px;
  }

  .modal-actions {
    display: flex;
    gap: 12px;
    width: 100%;
  }

  .modal-actions button {
    flex: 1;
    padding: 12px;
    border-radius: 8px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
  }

  .btn-cancel {
    background: rgba(255, 255, 255, 0.05);
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .btn-cancel:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
  }

  .btn-confirm-delete {
    background: #ef4444;
    color: white;
  }

  .btn-confirm-delete:hover {
    background: #dc2626;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
  }
  
  .manual-input {
    width: 100%;
    padding: 10px 12px;
    background: rgba(15, 23, 42, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    color: #f1f5f9;
    font-family: inherit;
    font-size: 0.95rem;
    box-sizing: border-box;
    transition: all 0.2s;
  }
  
  .manual-input:focus {
    outline: none;
    border-color: #6366f1;
    background: rgba(15, 23, 42, 0.8);
  }
  
  .btn-confirm {
    background: #3b82f6;
    color: white;
  }
  
  .btn-confirm:hover {
    background: #2563eb;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
  }
</style>
