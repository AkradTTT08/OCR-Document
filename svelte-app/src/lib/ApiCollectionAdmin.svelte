<script>
  import { onMount } from "svelte";
  import { showToast, customConfirm } from "./toastStore.js";
  import CustomSelect from "./CustomSelect.svelte";
  import ExtensionSyncModal from "./ExtensionSyncModal.svelte";

  const API_BASE = "http://localhost:5001";

  export let projectsList = [];
  export let selectedProject = "";

  let collections = [];
  let isLoading = false;
  let isUploading = false;
  let isSniffing = false;
  let isDragOver = false;

  // Upload Form State
  let uploadFile = null;
  let fileInput;
  let customName = "";

  // Repository Filtering & Bulk Actions
  let repoSearchQuery = "";
  let repoFormatFilter = "ALL";
  let repoMethodFilter = "ALL";
  let selectedCollectionIds = new Set();

  // Sniffer Modal State
  let showSnifferModal = false;
  let snifferUrl = "";
  let snifferUsername = "";
  let snifferPassword = "";
  let sniffedEndpoints = [];
  let selectedSniffedIndices = new Set();
  let snifferImportMode = "new"; // 'new' | 'append'
  let snifferCollectionName = "";
  let snifferTargetCollectionId = "";

  // Chrome Extension Live Sync Modal
  let showExtensionModal = false;

  // Collection Workspace & Endpoint Inspector Modal
  let showWorkspaceModal = false;
  let activeCollection = null;
  let wsName = "";
  let wsVersion = "";
  let wsBaseUrl = "";
  let wsEndpoints = [];
  let wsSearch = "";
  let wsMethodFilter = "ALL";
  let isSavingWorkspace = false;
  let wsTestingIndex = null;
  let wsTestResult = null;
  let wsActiveTestEndpoint = null;

  // Spectra API Studio (Add / Edit API Manual & cURL Builder Modal)
  let showStudioModal = false;
  let studioMode = "create"; // 'create' | 'edit'
  let studioSaveMode = "new_collection"; // 'new_collection' | 'existing_collection'
  let studioCollectionName = "";
  let studioTargetCollectionId = "";
  let studioEditCollectionId = "";
  let studioEditEndpointIndex = -1;

  let studioName = "";
  let studioCategory = "General";
  let studioMethod = "GET";
  let studioUrl = "";
  let studioBaseUrl = "";
  let studioSummary = "";
  let studioActiveTab = "params"; // 'params' | 'auth' | 'headers' | 'body'
  let studioQueryParams = [{ key: "", value: "", enabled: true }];
  let studioAuthType = "none"; // 'none' | 'bearer' | 'apikey' | 'basic'
  let studioAuthBearer = "";
  let studioAuthApiKeyName = "X-API-Key";
  let studioAuthApiKeyValue = "";
  let studioAuthApiKeyIn = "header";
  let studioAuthBasicUser = "";
  let studioAuthBasicPass = "";
  let studioHeaderMode = "table"; // 'table' | 'json'
  let studioHeaderRows = [
    { key: "Content-Type", value: "application/json", enabled: true },
  ];
  let studioHeadersJson = '{\n  "Content-Type": "application/json"\n}';
  let studioBodyMode = "json"; // 'none' | 'json' | 'raw'
  let studioBodyText = "";
  let studioCurlInput = "";
  let showCurlDrawer = false;
  let isSavingStudio = false;
  let isTestingDirect = false;
  let studioDirectResult = null;

  const HTTP_METHODS = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
  ];

  function getAuthHeaders(extra = {}) {
    const token =
      typeof localStorage !== "undefined"
        ? localStorage.getItem("jwt_token")
        : null;
    const headers = { ...extra };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }

  $: projectOptions = (projectsList || []).map((p) => ({
    value:
      typeof p === "string"
        ? p
        : p.id || p.project_id || p.project_name || p.name,
    label: typeof p === "string" ? p : p.name || p.project_name || p.id,
  }));

  $: selectedProjectLabel = (() => {
    const found = projectOptions.find((o) => o.value === selectedProject);
    return found ? found.label : selectedProject;
  })();

  $: totalEndpointsCount = collections.reduce(
    (acc, c) =>
      acc +
      (c.endpoint_count ||
        c.endpoints_count ||
        (c.endpoints || []).length ||
        0),
    0,
  );

  $: filteredCollections = collections.filter((col) => {
    const q = repoSearchQuery.trim().toLowerCase();
    const eps = Array.isArray(col.endpoints) ? col.endpoints : [];
    const fmt = col.format_type || col.format || "";
    const matchesSearch =
      !q ||
      (col.name || "").toLowerCase().includes(q) ||
      fmt.toLowerCase().includes(q) ||
      (col.base_url || "").toLowerCase().includes(q) ||
      eps.some(
        (ep) =>
          (ep.path || "").toLowerCase().includes(q) ||
          (ep.url || "").toLowerCase().includes(q) ||
          (ep.summary || "").toLowerCase().includes(q) ||
          (ep.name || "").toLowerCase().includes(q),
      );

    const matchesFormat =
      repoFormatFilter === "ALL" ||
      fmt.toLowerCase().includes(repoFormatFilter.toLowerCase());

    const matchesMethod =
      repoMethodFilter === "ALL" ||
      eps.some((ep) => (ep.method || "GET").toUpperCase() === repoMethodFilter);

    return matchesSearch && matchesFormat && matchesMethod;
  });

  $: filteredWorkspaceEndpoints = wsEndpoints
    .map((ep, index) => ({ ...ep, _idx: index }))
    .filter((ep) => {
      const q = wsSearch.trim().toLowerCase();
      const matchesMethod =
        wsMethodFilter === "ALL" ||
        (ep.method || "GET").toUpperCase() === wsMethodFilter;
      const matchesQuery =
        !q ||
        (ep.path || "").toLowerCase().includes(q) ||
        (ep.url || "").toLowerCase().includes(q) ||
        (ep.summary || "").toLowerCase().includes(q) ||
        (ep.name || "").toLowerCase().includes(q) ||
        (ep.category || "").toLowerCase().includes(q);
      return matchesMethod && matchesQuery;
    });

  onMount(async () => {
    if (!projectsList || projectsList.length === 0) {
      try {
        const res = await fetch(`${API_BASE}/api/projects`, {
          headers: getAuthHeaders(),
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.projects)) {
            projectsList = data.projects;
          } else if (Array.isArray(data)) {
            projectsList = data;
          }
        }
      } catch (_) {}
    }
    if (!selectedProject && projectsList.length > 0) {
      const first = projectsList[0];
      selectedProject =
        typeof first === "string"
          ? first
          : first.id || first.project_id || first.project_name || first.name;
    }
    if (selectedProject) {
      loadCollections();
    }
  });

  $: if (selectedProject) {
    loadCollections();
  }

  async function loadCollections() {
    if (!selectedProject) return;
    isLoading = true;
    try {
      const res = await fetch(
        `${API_BASE}/api/projects/${encodeURIComponent(selectedProject)}/api-collections`,
        {
          headers: getAuthHeaders(),
        },
      );
      if (res.ok) {
        const data = await res.json();
        const rawList = Array.isArray(data) ? data : data.collections || [];
        collections = rawList.map((c) => ({
          ...c,
          format_type: c.format_type || c.format || "OpenAPI",
          endpoint_count:
            c.endpoint_count ?? c.endpoints_count ?? (c.endpoints || []).length,
          created_at:
            c.created_at ||
            c.updated_at ||
            c.uploaded_at ||
            new Date().toISOString(),
        }));
        selectedCollectionIds = new Set();
        if (activeCollection) {
          const refreshed = collections.find(
            (c) => c.id === activeCollection.id,
          );
          if (refreshed) syncWorkspaceFromCollection(refreshed);
        }
      } else {
        showToast("ไม่สามารถโหลดรายการ API Collection ได้", "error");
      }
    } catch (e) {
      showToast("ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ API Collections ได้", "error");
    } finally {
      isLoading = false;
    }
  }

  // --- Drag & Drop + File Upload (P0.2) ---
  function applySelectedFile(file) {
    if (!file) return;
    uploadFile = file;
    if (!customName) {
      customName = file.name.replace(/\.(json|yaml|yml)$/i, "");
    }
  }

  function handleFileChange(e) {
    const files = e.target.files;
    if (files && files.length > 0) {
      applySelectedFile(files[0]);
    }
  }

  function handleDragOver(e) {
    e.preventDefault();
    isDragOver = true;
  }

  function handleDragLeave(e) {
    e.preventDefault();
    isDragOver = false;
  }

  function handleFileDrop(e) {
    e.preventDefault();
    isDragOver = false;
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      applySelectedFile(files[0]);
    }
  }

  function clearSelectedFile(e) {
    if (e) e.stopPropagation();
    uploadFile = null;
    customName = "";
    if (fileInput) fileInput.value = "";
  }

  async function handleUpload() {
    if (!selectedProject) {
      showToast("กรุณาเลือกโครงการก่อนอัปโหลด", "warning");
      return;
    }
    if (!uploadFile) {
      showToast(
        "กรุณาเลือกไฟล์ OpenAPI / Swagger หรือ Postman (.json, .yaml)",
        "warning",
      );
      return;
    }

    isUploading = true;
    const formData = new FormData();
    formData.append("project_id", selectedProject);
    formData.append("file", uploadFile);
    if (customName.trim()) {
      formData.append("name", customName.trim());
    }

    try {
      const res = await fetch(`${API_BASE}/api/api-collections/upload`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.success) {
        const savedCol = data.collection || data;
        showToast(
          `นำเข้า "${savedCol.name || customName}" (${savedCol.endpoints_count ?? savedCol.endpoint_count ?? 0} Endpoints) สำเร็จ`,
          "success",
        );
        clearSelectedFile();
        await loadCollections();
      } else {
        showToast(data.error || "อัปโหลดไฟล์ API Spec ไม่สำเร็จ", "error");
      }
    } catch (e) {
      showToast("เกิดข้อผิดพลาดในการเชื่อมต่อเพื่ออัปโหลดไฟล์", "error");
    } finally {
      isUploading = false;
    }
  }

  // --- Repository Actions (Test / Delete / Bulk Delete / Export) ---
  function toggleCollectionCheck(id) {
    const next = new Set(selectedCollectionIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedCollectionIds = next;
  }

  function toggleSelectAllCollections() {
    if (selectedCollectionIds.size === filteredCollections.length) {
      selectedCollectionIds = new Set();
    } else {
      selectedCollectionIds = new Set(filteredCollections.map((c) => c.id));
    }
  }

  async function handleDeleteCollection(id, name) {
    const confirmed = await customConfirm(
      `ยืนยันการลบชุด API "${name}" ออกจากโครงการ ${selectedProject}?`,
    );
    if (!confirmed) return;

    try {
      const res = await fetch(`${API_BASE}/api/api-collections/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        showToast(`ลบ "${name}" เรียบร้อยแล้ว`, "success");
        if (activeCollection && activeCollection.id === id) {
          showWorkspaceModal = false;
          activeCollection = null;
        }
        await loadCollections();
      } else {
        showToast("ไม่สามารถลบ API Collection ได้", "error");
      }
    } catch (e) {
      showToast("เกิดข้อผิดพลาดในการลบ API Collection", "error");
    }
  }

  async function handleBulkDeleteCollections() {
    if (selectedCollectionIds.size === 0) return;
    const confirmed = await customConfirm(
      `ยืนยันการลบ API Collection ที่เลือกทั้งหมด ${selectedCollectionIds.size} รายการ?`,
    );
    if (!confirmed) return;

    let deletedCount = 0;
    for (const id of selectedCollectionIds) {
      try {
        const res = await fetch(`${API_BASE}/api/api-collections/${id}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        });
        if (res.ok) deletedCount++;
      } catch (_) {}
    }
    showToast(`ลบสำเร็จ ${deletedCount} Collection`, "success");
    selectedCollectionIds = new Set();
    await loadCollections();
  }

  function exportCollectionJson(col) {
    const payload = {
      name: col.name,
      project_id: col.project_id,
      format_type: col.format_type,
      version: col.version,
      base_url: col.base_url || "",
      endpoint_count: (col.endpoints || []).length,
      exported_at: new Date().toISOString(),
      endpoints: col.endpoints || [],
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(col.name || "api-collection").replace(/[^a-zA-Z0-9_-ก-๙]/g, "_")}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`ส่งออกไฟล์ JSON ของ "${col.name}" เรียบร้อยแล้ว`, "info");
  }

  // --- Interactive Collection Workspace & Endpoint Test Runner (A2) ---
  function openWorkspace(col) {
    syncWorkspaceFromCollection(col);
    wsSearch = "";
    wsMethodFilter = "ALL";
    wsTestResult = null;
    wsActiveTestEndpoint = null;
    showWorkspaceModal = true;
  }

  function syncWorkspaceFromCollection(col) {
    activeCollection = col;
    wsName = col.name || "";
    wsVersion = col.version || "1.0.0";
    wsBaseUrl = col.base_url || "";
    wsEndpoints = Array.isArray(col.endpoints)
      ? JSON.parse(JSON.stringify(col.endpoints))
      : [];
  }

  async function saveWorkspaceMetadata() {
    if (!activeCollection) return;
    isSavingWorkspace = true;
    try {
      const res = await fetch(
        `${API_BASE}/api/api-collections/${activeCollection.id}`,
        {
          method: "PUT",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            name: wsName.trim() || activeCollection.name,
            version: wsVersion.trim() || "1.0.0",
            base_url: wsBaseUrl.trim(),
            endpoints: wsEndpoints,
          }),
        },
      );
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(
          "บันทึกการตั้งค่า Collection และ Endpoints เรียบร้อยแล้ว",
          "success",
        );
        await loadCollections();
      } else {
        showToast(data.error || "บันทึกการแก้ไขไม่สำเร็จ", "error");
      }
    } catch (e) {
      showToast("เกิดข้อผิดพลาดในการบันทึกข้อมูล Collection", "error");
    } finally {
      isSavingWorkspace = false;
    }
  }

  async function testEndpointInWorkspace(ep, index) {
    if (!activeCollection) return;
    wsTestingIndex = index;
    wsActiveTestEndpoint = ep;
    wsTestResult = null;
    try {
      const res = await fetch(
        `${API_BASE}/api/api-collections/${activeCollection.id}/test`,
        {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            endpoint_index: index,
            base_url: wsBaseUrl.trim(),
          }),
        },
      );
      const data = await res.json();
      wsTestResult = data;
      if (data.success) {
        showToast(
          `ยิงทดสอบ ${ep.method} ${ep.path} สำเร็จ (${data.status_code} • ${data.latency_ms} ms)`,
          "success",
        );
      } else {
        showToast(data.error || "การยิงทดสอบไม่สำเร็จ", "warning");
      }
    } catch (e) {
      wsTestResult = { success: false, error: e.message };
      showToast("เกิดข้อผิดพลาดในการยิงทดสอบ API", "error");
    } finally {
      wsTestingIndex = null;
    }
  }

  async function deleteEndpointInWorkspace(index) {
    const target = wsEndpoints[index];
    if (!target) return;
    const confirmed = await customConfirm(
      `ลบ Endpoint "${target.method} ${target.path}" ออกจากชุดนี้?`,
    );
    if (!confirmed) return;

    wsEndpoints = wsEndpoints.filter((_, idx) => idx !== index);
    await saveWorkspaceMetadata();
  }

  function buildCurlFromEndpoint(ep, baseUrl = "") {
    const method = (ep.method || "GET").toUpperCase();
    let fullUrl = ep.url || ep.path || "";
    if (!/^https?:\/\//i.test(fullUrl) && baseUrl) {
      fullUrl = `${baseUrl.replace(/\/+$/, "")}/${fullUrl.replace(/^\/+/, "")}`;
    }
    const parts = [`curl -X ${method} "${fullUrl}"`];
    const headers =
      ep.headers && typeof ep.headers === "object" ? ep.headers : {};
    for (const [k, v] of Object.entries(headers)) {
      if (k) parts.push(`  -H "${k}: ${String(v).replace(/"/g, '\\"')}"`);
    }
    if (ep.body && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      const bodyStr =
        typeof ep.body === "string" ? ep.body : JSON.stringify(ep.body);
      parts.push(`  -d '${bodyStr.replace(/'/g, "'\\''")}'`);
    }
    return parts.join(" \\\n");
  }

  async function copyEndpointCurl(ep, baseUrl = "") {
    const cmd = ep.curl || buildCurlFromEndpoint(ep, baseUrl);
    try {
      await navigator.clipboard.writeText(cmd);
      showToast("คัดลอกคำสั่ง cURL ไปยังคลิปบอร์ดแล้ว", "info");
    } catch (_) {
      showToast("ไม่สามารถคัดลอก cURL ได้", "error");
    }
  }

  // --- Spectra API Studio (Manual & cURL Builder + Edit Endpoint + Live Test Send) ---
  function openStudioForNew(preselectedCollectionId = "") {
    studioMode = "create";
    if (preselectedCollectionId) {
      studioSaveMode = "existing_collection";
      studioTargetCollectionId = preselectedCollectionId;
    } else if (collections.length > 0) {
      studioSaveMode = "new_collection";
      studioTargetCollectionId = collections[0].id;
    } else {
      studioSaveMode = "new_collection";
      studioTargetCollectionId = "";
    }
    studioCollectionName = "";
    studioName = "";
    studioCategory = "General";
    studioMethod = "GET";
    studioUrl = "";
    studioBaseUrl = "";
    studioSummary = "";
    studioActiveTab = "params";
    studioQueryParams = [{ key: "", value: "", enabled: true }];
    studioAuthType = "none";
    studioAuthBearer = "";
    studioAuthApiKeyName = "X-API-Key";
    studioAuthApiKeyValue = "";
    studioAuthApiKeyIn = "header";
    studioAuthBasicUser = "";
    studioAuthBasicPass = "";
    studioHeaderMode = "table";
    studioHeaderRows = [
      { key: "Content-Type", value: "application/json", enabled: true },
    ];
    studioHeadersJson = '{\n  "Content-Type": "application/json"\n}';
    studioBodyMode = "json";
    studioBodyText = "";
    studioCurlInput = "";
    showCurlDrawer = false;
    studioDirectResult = null;
    showStudioModal = true;
  }

  function openStudioForEdit(collection, ep, index) {
    studioMode = "edit";
    studioEditCollectionId = collection.id;
    studioEditEndpointIndex = index;
    studioCollectionName = collection.name;
    studioBaseUrl = collection.base_url || "";

    studioName =
      ep.name || ep.summary || `${ep.method || "GET"} ${ep.path || ""}`;
    studioCategory = ep.category || "General";
    studioMethod = (ep.method || "GET").toUpperCase();
    studioUrl = ep.url || ep.path || "";
    studioSummary = ep.summary || ep.description || "";
    studioActiveTab = "headers";

    const qp =
      Array.isArray(ep.query_params) && ep.query_params.length > 0
        ? JSON.parse(JSON.stringify(ep.query_params))
        : [{ key: "", value: "", enabled: true }];
    studioQueryParams = qp;

    const auth =
      ep.auth_config && typeof ep.auth_config === "object"
        ? ep.auth_config
        : { type: "none" };
    studioAuthType = auth.type || "none";
    studioAuthBearer = auth.token || "";
    studioAuthApiKeyName = auth.key || "X-API-Key";
    studioAuthApiKeyValue = auth.value || "";
    studioAuthApiKeyIn = auth.in || "header";
    studioAuthBasicUser = auth.username || "";
    studioAuthBasicPass = auth.password || "";

    const hdrs =
      ep.headers && typeof ep.headers === "object"
        ? ep.headers
        : { "Content-Type": "application/json" };
    const rows = Object.entries(hdrs).map(([key, value]) => ({
      key,
      value: String(value),
      enabled: true,
    }));
    studioHeaderRows =
      rows.length > 0 ? rows : [{ key: "", value: "", enabled: true }];
    studioHeadersJson = JSON.stringify(hdrs, null, 2);
    studioHeaderMode = "table";

    studioBodyText =
      typeof ep.body === "string"
        ? ep.body
        : ep.body
          ? JSON.stringify(ep.body, null, 2)
          : "";
    studioBodyMode = studioBodyText ? "json" : "none";
    studioCurlInput = ep.curl || "";
    showCurlDrawer = false;
    studioDirectResult = null;
    showStudioModal = true;
  }

  function collectStudioHeadersObject() {
    if (studioHeaderMode === "json") {
      try {
        const parsed = JSON.parse(studioHeadersJson || "{}");
        return typeof parsed === "object" && parsed !== null ? parsed : {};
      } catch (_) {
        return null;
      }
    }
    const out = {};
    for (const row of studioHeaderRows) {
      if (row.enabled !== false && row.key && row.key.trim()) {
        out[row.key.trim()] = row.value ?? "";
      }
    }
    return out;
  }

  function collectStudioAuthConfig() {
    if (studioAuthType === "bearer") {
      return { type: "bearer", token: studioAuthBearer.trim() };
    }
    if (studioAuthType === "apikey") {
      return {
        type: "apikey",
        key: studioAuthApiKeyName.trim() || "X-API-Key",
        value: studioAuthApiKeyValue.trim(),
        in: studioAuthApiKeyIn,
      };
    }
    if (studioAuthType === "basic") {
      return {
        type: "basic",
        username: studioAuthBasicUser,
        password: studioAuthBasicPass,
      };
    }
    return { type: "none" };
  }

  function addQueryParamRow() {
    studioQueryParams = [
      ...studioQueryParams,
      { key: "", value: "", enabled: true },
    ];
  }

  function removeQueryParamRow(idx) {
    studioQueryParams = studioQueryParams.filter((_, i) => i !== idx);
    if (studioQueryParams.length === 0) {
      studioQueryParams = [{ key: "", value: "", enabled: true }];
    }
  }

  function addHeaderRow() {
    studioHeaderRows = [
      ...studioHeaderRows,
      { key: "", value: "", enabled: true },
    ];
  }

  function removeHeaderRow(idx) {
    studioHeaderRows = studioHeaderRows.filter((_, i) => i !== idx);
    if (studioHeaderRows.length === 0) {
      studioHeaderRows = [{ key: "", value: "", enabled: true }];
    }
  }

  function toggleHeaderViewMode(mode) {
    if (mode === studioHeaderMode) return;
    if (mode === "json") {
      const obj = collectStudioHeadersObject() || {};
      studioHeadersJson = JSON.stringify(obj, null, 2);
    } else {
      try {
        const parsed = JSON.parse(studioHeadersJson || "{}");
        const rows = Object.entries(parsed).map(([key, value]) => ({
          key,
          value: String(value),
          enabled: true,
        }));
        studioHeaderRows =
          rows.length > 0 ? rows : [{ key: "", value: "", enabled: true }];
      } catch (e) {
        showToast(
          "รูปแบบ JSON ของ Headers ไม่ถูกต้อง กรุณาแก้ไขก่อนสลับมุมมอง",
          "warning",
        );
        return;
      }
    }
    studioHeaderMode = mode;
  }

  function prettifyStudioBody() {
    if (!studioBodyText.trim()) return;
    try {
      const parsed = JSON.parse(studioBodyText);
      studioBodyText = JSON.stringify(parsed, null, 2);
      showToast("จัดรูปแบบและตรวจสอบ JSON เรียบร้อยแล้ว", "success");
    } catch (e) {
      showToast(`JSON ไม่ถูกต้อง: ${e.message}`, "error");
    }
  }

  function parseCurlCommand() {
    if (!studioCurlInput.trim()) {
      showToast("กรุณาวางคำสั่ง cURL ก่อนกดแปลงข้อมูล", "warning");
      return;
    }
    try {
      // Normalize bash line continuations and Windows CMD ^ continuations
      const cmd = studioCurlInput
        .replace(/\\\r?\n/g, " ")
        .replace(/\^\r?\n/g, " ")
        .trim();

      const methodMatch = cmd.match(
        /(?:-X|--request)\s+['"]?(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)['"]?/i,
      );
      let detectedMethod = methodMatch ? methodMatch[1].toUpperCase() : "";

      const urlMatch =
        cmd.match(/--url\s+['"]?(https?:\/\/[^\s'"]+)['"]?/i) ||
        cmd.match(/['"]?(https?:\/\/[^\s'"]+)['"]?/i);

      if (urlMatch) {
        const fullUrl = urlMatch[1];
        studioUrl = fullUrl;
        try {
          const u = new URL(fullUrl);
          if (!studioName) {
            studioName = `${detectedMethod || "API"} ${u.pathname}`;
          }
          if (!studioBaseUrl) {
            studioBaseUrl = `${u.protocol}//${u.host}`;
          }
          if (u.searchParams && Array.from(u.searchParams.keys()).length > 0) {
            const qRows = [];
            u.searchParams.forEach((v, k) =>
              qRows.push({ key: k, value: v, enabled: true }),
            );
            studioQueryParams = qRows;
          }
        } catch (_) {}
      }

      const headers = {};
      const headerRegex = /(?:-H|--header)\s+(['"])(.*?)\1/gi;
      let m;
      while ((m = headerRegex.exec(cmd)) !== null) {
        const parts = m[2].split(":");
        if (parts.length >= 2) {
          const key = parts.shift().trim();
          const val = parts.join(":").trim();
          headers[key] = val;
          if (
            key.toLowerCase() === "authorization" &&
            /^bearer\s+/i.test(val)
          ) {
            studioAuthType = "bearer";
            studioAuthBearer = val.replace(/^bearer\s+/i, "").trim();
          }
        }
      }

      const userMatch = cmd.match(/(?:-u|--user)\s+(['"]?)([^'"\s]+)\1/i);
      if (userMatch) {
        const [usr, pwd = ""] = userMatch[2].split(":");
        studioAuthType = "basic";
        studioAuthBasicUser = usr;
        studioAuthBasicPass = pwd;
      }

      const cookieMatch = cmd.match(/(?:-b|--cookie)\s+(['"])(.*?)\1/i);
      if (cookieMatch) {
        headers["Cookie"] = cookieMatch[2];
      }

      if (Object.keys(headers).length > 0) {
        studioHeaderRows = Object.entries(headers).map(([key, value]) => ({
          key,
          value: String(value),
          enabled: true,
        }));
        studioHeadersJson = JSON.stringify(headers, null, 2);
      }

      const dataMatch = cmd.match(
        /(?:-d|--data|--data-raw|--data-binary)\s+(['"])([\s\S]*?)\1/i,
      );
      if (dataMatch) {
        let rawData = dataMatch[2];
        try {
          rawData = JSON.stringify(JSON.parse(rawData), null, 2);
          studioBodyMode = "json";
        } catch (_) {
          studioBodyMode = "raw";
        }
        studioBodyText = rawData;
        if (!detectedMethod) detectedMethod = "POST";
      }

      studioMethod = detectedMethod || "GET";
      showCurlDrawer = false;
      showToast(
        "แยกข้อมูล Method, URL, Headers, Auth และ Body จาก cURL สำเร็จ!",
        "success",
      );
    } catch (e) {
      showToast("รูปแบบคำสั่ง cURL ไม่สมบูรณ์ กรุณาตรวจสอบอีกครั้ง", "error");
    }
  }

  async function handleStudioTestSend() {
    if (!studioUrl.trim()) {
      showToast("กรุณาระบุ URL หรือ Path ของ Endpoint ก่อนยิงทดสอบ", "warning");
      return;
    }
    const headersObj = collectStudioHeadersObject();
    if (headersObj === null) {
      showToast("รูปแบบ JSON ของ Headers ไม่ถูกต้อง", "error");
      return;
    }

    isTestingDirect = true;
    studioDirectResult = null;
    try {
      const res = await fetch(`${API_BASE}/api/api-collections/test-direct`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          method: studioMethod,
          url: studioUrl.trim(),
          base_url: studioBaseUrl.trim(),
          headers: headersObj,
          query_params: studioQueryParams.filter(
            (q) => q.enabled !== false && q.key.trim(),
          ),
          auth_config: collectStudioAuthConfig(),
          body: studioBodyMode === "none" ? "" : studioBodyText,
        }),
      });
      const data = await res.json();
      studioDirectResult = data;
      if (data.success) {
        showToast(
          `ผลทดสอบ: HTTP ${data.status_code} (${data.latency_ms} ms)`,
          "success",
        );
      } else {
        showToast(data.error || "ยิงทดสอบไม่สำเร็จ", "warning");
      }
    } catch (e) {
      studioDirectResult = { success: false, error: e.message };
      showToast("เกิดข้อผิดพลาดในการเชื่อมต่อเพื่อยิงทดสอบ", "error");
    } finally {
      isTestingDirect = false;
    }
  }

  async function handleSaveStudio() {
    if (!selectedProject) {
      showToast("กรุณาเลือกโครงการ", "warning");
      return;
    }
    if (!studioUrl.trim()) {
      showToast("กรุณาระบุ Endpoint URL หรือ Path", "warning");
      return;
    }
    const headersObj = collectStudioHeadersObject();
    if (headersObj === null) {
      showToast("รูปแบบ JSON ในแท็บ Headers ไม่ถูกต้อง", "error");
      return;
    }

    isSavingStudio = true;
    try {
      let pathPart = studioUrl.trim();
      try {
        if (/^https?:\/\//i.test(pathPart)) {
          const parsedUrl = new URL(pathPart);
          pathPart = `${parsedUrl.pathname}${parsedUrl.search || ""}`;
          if (!studioBaseUrl.trim()) {
            studioBaseUrl = `${parsedUrl.protocol}//${parsedUrl.host}`;
          }
        }
      } catch (_) {}

      const endpointRecord = {
        method: studioMethod,
        path: pathPart,
        url: studioUrl.trim(),
        name: studioName.trim() || `${studioMethod} ${pathPart}`,
        summary:
          studioSummary.trim() ||
          studioName.trim() ||
          `${studioMethod} ${pathPart}`,
        description: studioSummary.trim(),
        category: studioCategory.trim() || "General",
        headers: headersObj,
        query_params: studioQueryParams.filter((q) => q.key && q.key.trim()),
        auth_config: collectStudioAuthConfig(),
        body: studioBodyMode === "none" ? "" : studioBodyText,
        curl:
          studioCurlInput.trim() ||
          buildCurlFromEndpoint(
            {
              method: studioMethod,
              url: studioUrl.trim(),
              path: pathPart,
              headers: headersObj,
              body: studioBodyMode === "none" ? "" : studioBodyText,
            },
            studioBaseUrl.trim(),
          ),
      };

      if (studioMode === "edit" && studioEditCollectionId) {
        const col =
          collections.find((c) => c.id === studioEditCollectionId) ||
          activeCollection;
        if (!col) throw new Error("ไม่พบ Collection ที่ต้องการแก้ไข");
        const nextEndpoints = Array.isArray(col.endpoints)
          ? [...col.endpoints]
          : [];
        nextEndpoints[studioEditEndpointIndex] = endpointRecord;

        const res = await fetch(
          `${API_BASE}/api/api-collections/${studioEditCollectionId}`,
          {
            method: "PUT",
            headers: getAuthHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
              name: col.name,
              version: col.version,
              base_url: studioBaseUrl.trim() || col.base_url || "",
              endpoints: nextEndpoints,
            }),
          },
        );
        const data = await res.json();
        if (!res.ok || !data.success)
          throw new Error(data.error || "บันทึกการแก้ไขไม่สำเร็จ");
        showToast(
          `อัปเดต Endpoint "${endpointRecord.name}" เรียบร้อยแล้ว`,
          "success",
        );
      } else {
        const res = await fetch(`${API_BASE}/api/api-collections/manual`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            project_id: selectedProject,
            target_collection_id:
              studioSaveMode === "existing_collection"
                ? studioTargetCollectionId
                : null,
            collection_name:
              studioSaveMode === "new_collection"
                ? studioCollectionName.trim() ||
                  studioName.trim() ||
                  `Manual API Collection`
                : undefined,
            base_url: studioBaseUrl.trim(),
            name: endpointRecord.name,
            category: endpointRecord.category,
            description: endpointRecord.summary,
            method: endpointRecord.method,
            url: endpointRecord.url,
            headers: endpointRecord.headers,
            query_params: endpointRecord.query_params,
            auth_config: endpointRecord.auth_config,
            body: endpointRecord.body,
            curl: endpointRecord.curl,
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.success)
          throw new Error(data.error || "บันทึก API ไม่สำเร็จ");
        showToast(
          studioSaveMode === "existing_collection"
            ? `เพิ่ม Endpoint เข้า Collection เรียบร้อยแล้ว`
            : `สร้าง API Collection ใหม่เรียบร้อยแล้ว`,
          "success",
        );
      }

      showStudioModal = false;
      await loadCollections();
    } catch (e) {
      showToast(e.message || "เกิดข้อผิดพลาดในการบันทึก API", "error");
    } finally {
      isSavingStudio = false;
    }
  }

  // --- Web API Sniffer (Real OpenAPI/Swagger Probing + Grouped Save A3) ---
  function openSnifferModal() {
    showSnifferModal = true;
    sniffedEndpoints = [];
    selectedSniffedIndices = new Set();
    snifferImportMode = "new";
    snifferCollectionName = "";
    snifferTargetCollectionId = collections.length > 0 ? collections[0].id : "";
  }

  async function handleStartSniffing() {
    if (!snifferUrl.trim()) {
      showToast("กรุณาระบุ Target URL ของระบบที่ต้องการสำรวจ API", "warning");
      return;
    }
    isSniffing = true;
    sniffedEndpoints = [];
    selectedSniffedIndices = new Set();

    try {
      const res = await fetch(`${API_BASE}/api/api-collections/sniff`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          project_id: selectedProject,
          target_url: snifferUrl.trim(),
          username: snifferUsername,
          password: snifferPassword,
        }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        sniffedEndpoints = data.endpoints || [];
        selectedSniffedIndices = new Set(sniffedEndpoints.map((_, idx) => idx));
        if (!snifferCollectionName) {
          try {
            const host = new URL(snifferUrl.trim()).host;
            snifferCollectionName = `Discovered APIs (${host})`;
          } catch (_) {
            snifferCollectionName = `Discovered APIs (${snifferUrl.trim()})`;
          }
        }
        showToast(`สำรวจพบ ${sniffedEndpoints.length} Endpoints`, "success");
      } else {
        showToast(data.error || "สำรวจ API ไม่สำเร็จ", "error");
      }
    } catch (e) {
      showToast("เกิดข้อผิดพลาดในการเชื่อมต่อเพื่อสำรวจ API", "error");
    } finally {
      isSniffing = false;
    }
  }

  function toggleSniffedSelection(idx) {
    const next = new Set(selectedSniffedIndices);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    selectedSniffedIndices = next;
  }

  function toggleAllSniffed() {
    if (selectedSniffedIndices.size === sniffedEndpoints.length) {
      selectedSniffedIndices = new Set();
    } else {
      selectedSniffedIndices = new Set(sniffedEndpoints.map((_, idx) => idx));
    }
  }

  async function handleSaveSniffed() {
    if (selectedSniffedIndices.size === 0) {
      showToast("กรุณาเลือกอย่างน้อย 1 Endpoint", "warning");
      return;
    }
    const toSave = Array.from(selectedSniffedIndices).map(
      (idx) => sniffedEndpoints[idx],
    );
    isSniffing = true;
    try {
      let baseOrigin = "";
      try {
        const u = new URL(snifferUrl.trim());
        baseOrigin = `${u.protocol}//${u.host}`;
      } catch (_) {}

      const res = await fetch(`${API_BASE}/api/api-collections/save-sniffed`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          project_id: selectedProject,
          collection_name:
            snifferImportMode === "new"
              ? snifferCollectionName.trim() ||
                `Web Sniffer (${baseOrigin || "Target"})`
              : undefined,
          target_collection_id:
            snifferImportMode === "append" ? snifferTargetCollectionId : null,
          base_url: baseOrigin,
          source_label: "Web API Discovery",
          endpoints: toSave,
        }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(
          snifferImportMode === "append"
            ? `เพิ่ม ${toSave.length} Endpoints เข้า Collection เดิมเรียบร้อยแล้ว`
            : `บันทึกเป็น 1 Collection ใหม่ (${toSave.length} Endpoints) สำเร็จ`,
          "success",
        );
        showSnifferModal = false;
        await loadCollections();
      } else {
        showToast(data.error || "บันทึกผลการสำรวจ API ไม่สำเร็จ", "error");
      }
    } catch (e) {
      showToast("เกิดข้อผิดพลาดในการบันทึก API ที่สำรวจพบ", "error");
    } finally {
      isSniffing = false;
    }
  }

  function handleGlobalKeydown(e) {
    if (e.key === "Escape") {
      if (showStudioModal) showStudioModal = false;
      else if (showSnifferModal) showSnifferModal = false;
      else if (showWorkspaceModal) showWorkspaceModal = false;
    }
  }
</script>

<svelte:window on:keydown={handleGlobalKeydown} />

<div class="api-admin-container">
  <!-- Header Banner -->
  <header class="page-header">
    <div class="header-main">
      <div class="header-icon-box" aria-hidden="true">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path
            d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"
          />
          <path
            d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"
          />
        </svg>
      </div>
      <div>
        <div class="header-badge-row">
          <span class="eyebrow-pill">SPECTRA API REPOSITORY & LIVE STUDIO</span>
          <span class="stat-pill">{collections.length} Collections</span>
          <span class="stat-pill cyan">{totalEndpointsCount} Endpoints</span>
        </div>
        <h2>API Collection & Endpoint Studio</h2>
        <p class="subtitle">
          ศูนย์กลางจัดเก็บ สำรวจ และยิงทดสอบ API ประจำโครงการ เพื่อเชื่อมต่อกับ
          AI QA Analysis Diagram และสร้าง Test Case อัตโนมัติ
        </p>
      </div>
    </div>

    <div class="project-selector-box">
      <span class="selector-label">โครงการ (Project Scope)</span>
      <div class="select-wrapper">
        <CustomSelect
          options={projectOptions}
          bind:value={selectedProject}
          placeholder="-- เลือกโครงการ --"
        />
      </div>
    </div>
  </header>

  <div class="content-grid">
    <!-- Left Column: Unified Ingestion Hub -->
    <aside class="ingestion-panel">
      <div class="panel-card">
        <div class="card-head">
          <div>
            <h3>นำเข้า API Spec มาตรฐาน</h3>
            <p class="card-desc">
              รองรับ OpenAPI 3.0, Swagger 2.0 และ Postman Collection v2.1
              (.json, .yaml)
            </p>
          </div>
        </div>

        <!-- Drag & Drop Zone (P0.2 Fixed) -->
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div
          class="upload-dropzone"
          class:has-file={uploadFile !== null}
          class:drag-over={isDragOver}
          on:click={() => fileInput.click()}
          on:dragover={handleDragOver}
          on:dragleave={handleDragLeave}
          on:drop={handleFileDrop}
        >
          <input
            type="file"
            accept=".json,.yaml,.yml"
            bind:this={fileInput}
            on:change={handleFileChange}
            style="display: none;"
          />
          {#if uploadFile}
            <div class="file-picked">
              <div class="picked-icon" aria-hidden="true">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path
                    d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                  />
                  <polyline points="14 2 14 8 20 8" />
                  <polyline points="9 15 11 17 15 13" />
                </svg>
              </div>
              <div class="picked-meta">
                <span class="file-name">{uploadFile.name}</span>
                <span class="file-size"
                  >{(uploadFile.size / 1024).toFixed(1)} KB • พร้อมนำเข้า</span
                >
              </div>
              <button
                type="button"
                class="clear-file-btn"
                on:click={clearSelectedFile}
                title="ล้างไฟล์ที่เลือก"
              >
                ล้างไฟล์
              </button>
            </div>
          {:else}
            <div class="drop-prompt">
              <div class="drop-icon-circle" aria-hidden="true">
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <span class="prompt-title"
                >คลิกเลือกไฟล์ หรือลากไฟล์มาวางที่นี่</span
              >
              <span class="prompt-sub"
                >ระบบจะสกัด Base URL, Paths, Methods และ Parameters อัตโนมัติ</span
              >
            </div>
          {/if}
        </div>

        <div class="form-group">
          <label for="spec-custom-name"
            >ตั้งชื่อชุด API Collection (ทางเลือก)</label
          >
          <input
            id="spec-custom-name"
            type="text"
            class="spectra-input"
            placeholder="เช่น Payment Gateway API v2"
            bind:value={customName}
          />
        </div>

        <button
          type="button"
          class="btn-primary-gradient"
          disabled={!uploadFile || isUploading || !selectedProject}
          on:click={handleUpload}
        >
          {#if isUploading}
            <span class="spinner"></span> กำลังประมวลผลไฟล์ Spec...
          {:else}
            <svg
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.2"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            นำเข้าไฟล์ API Spec เข้าโครงการ
          {/if}
        </button>

        <div class="section-divider">
          <span>หรือสร้าง / ดักจับ API ด้วยเครื่องมือ Spectra</span>
        </div>

        <!-- Cohesive Secondary Tools (Spectra Obsidian Glass Cards) -->
        <div class="tools-stack">
          <button
            type="button"
            class="tool-action-card"
            disabled={!selectedProject}
            on:click={() => openStudioForNew("")}
          >
            <div class="tool-icon violet" aria-hidden="true">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <polyline points="16 18 22 12 16 6" />
                <polyline points="8 6 2 12 8 18" />
              </svg>
            </div>
            <div class="tool-copy">
              <span class="tool-title">API Studio (Manual & cURL Builder)</span>
              <span class="tool-sub"
                >สร้างหรือวาง cURL พร้อมตั้งค่า Params, Auth, Headers
                และกดยิงทดสอบสด</span
              >
            </div>
          </button>

          <button
            type="button"
            class="tool-action-card"
            disabled={!selectedProject}
            on:click={openSnifferModal}
          >
            <div class="tool-icon cyan" aria-hidden="true">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <div class="tool-copy">
              <span class="tool-title"
                >Web API Discovery (OpenAPI / Route Sniffer)</span
              >
              <span class="tool-sub"
                >สแกนหา /openapi.json, /swagger.json และ API Routes จาก URL
                ระบบเป้าหมาย</span
              >
            </div>
          </button>

          <button
            type="button"
            class="tool-action-card"
            disabled={!selectedProject}
            on:click={() => (showExtensionModal = true)}
          >
            <div class="tool-icon emerald" aria-hidden="true">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle cx="12" cy="12" r="10" />
                <circle cx="12" cy="12" r="4" />
                <line x1="21.17" y1="8" x2="12" y2="8" />
              </svg>
            </div>
            <div class="tool-copy">
              <span class="tool-title">Chrome Extension Live Sync</span>
              <span class="tool-sub"
                >ดักจับ XHR / Fetch จริงจากเบราว์เซอร์แล้วรวบเป็น 1 Collection
                ทันที</span
              >
            </div>
          </button>
        </div>
      </div>
    </aside>

    <!-- Right Column: Repository & Endpoint Explorer -->
    <section class="repository-panel">
      <div class="panel-card full-height">
        <div class="repo-header">
          <div class="repo-title-group">
            <h3>คลัง API Collections ของโครงการ</h3>
            <span class="project-tag"
              >{selectedProjectLabel || "ยังไม่ได้เลือกโครงการ"}</span
            >
          </div>

          <div class="repo-top-actions">
            {#if selectedCollectionIds.size > 0}
              <button
                type="button"
                class="btn-bulk-danger"
                on:click={handleBulkDeleteCollections}
              >
                ลบที่เลือก ({selectedCollectionIds.size})
              </button>
            {/if}
            <button
              type="button"
              class="btn-studio-quick"
              on:click={() => openStudioForNew("")}
            >
              + สร้าง API / วาง cURL
            </button>
          </div>
        </div>

        <!-- Search & Filter Toolbar -->
        <div class="repo-toolbar">
          <div class="search-box">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              placeholder="ค้นหาชื่อ Collection, Base URL หรือ Endpoint Path (/api/...)..."
              bind:value={repoSearchQuery}
            />
            {#if repoSearchQuery}
              <button
                type="button"
                class="clear-search"
                on:click={() => (repoSearchQuery = "")}>ล้าง</button
              >
            {/if}
          </div>

          <div class="filter-group">
            <select
              class="filter-select"
              bind:value={repoMethodFilter}
              aria-label="กรองตาม HTTP Method"
            >
              <option value="ALL">ทุก Method</option>
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="PATCH">PATCH</option>
              <option value="DELETE">DELETE</option>
            </select>

            <select
              class="filter-select"
              bind:value={repoFormatFilter}
              aria-label="กรองตามประเภทแหล่งที่มา"
            >
              <option value="ALL">ทุกประเภทแหล่งที่มา</option>
              <option value="OpenAPI">OpenAPI / Swagger</option>
              <option value="Postman">Postman</option>
              <option value="Manual">Manual / cURL</option>
              <option value="Chrome">Chrome Live Sync</option>
              <option value="Discovery">Web Discovery</option>
            </select>
          </div>
        </div>

        {#if collections.length > 0}
          <div class="bulk-bar">
            <label class="bulk-check-label">
              <input
                type="checkbox"
                checked={filteredCollections.length > 0 &&
                  selectedCollectionIds.size === filteredCollections.length}
                on:change={toggleSelectAllCollections}
              />
              <span
                >เลือกทั้งหมด ({filteredCollections.length} Collections)</span
              >
            </label>
            <span class="bulk-hint"
              >คลิกที่ปุ่ม "เปิดจัดการ & ทดสอบ Endpoints" เพื่อดูรายละเอียด
              แก้ไข หรือยิงทดสอบรายตัว</span
            >
          </div>
        {/if}

        {#if isLoading}
          <div class="state-box">
            <span class="spinner large"></span>
            <p>กำลังโหลดคลัง API Collection...</p>
          </div>
        {:else if filteredCollections.length === 0}
          <div class="state-box empty">
            <div class="empty-orb" aria-hidden="true">
              <svg
                width="32"
                height="32"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
              >
                <polyline points="16 18 22 12 16 6" />
                <polyline points="8 6 2 12 8 18" />
              </svg>
            </div>
            {#if collections.length === 0}
              <h4>ยังไม่มี API Collection ในโครงการ {selectedProject}</h4>
              <p>
                อัปโหลดไฟล์ OpenAPI/Postman ทางซ้าย หรือเปิด API Studio
                เพื่อสร้าง Endpoint ตัวแรกของโครงการ
              </p>
              <button
                type="button"
                class="btn-primary-inline"
                on:click={() => openStudioForNew("")}
              >
                + เปิด API Studio สร้าง Endpoint แรก
              </button>
            {:else}
              <h4>ไม่พบ API Collection ที่ตรงกับคำค้นหา</h4>
              <p>ลองเปลี่ยนคำค้นหาหรือรีเซ็ตตัวกรอง Method / แหล่งที่มา</p>
            {/if}
          </div>
        {:else}
          <div class="collections-list">
            {#each filteredCollections as col (col.id)}
              {@const eps = Array.isArray(col.endpoints) ? col.endpoints : []}
              <article
                class="collection-card"
                class:checked={selectedCollectionIds.has(col.id)}
              >
                <div class="col-card-top">
                  <div class="col-title-area">
                    <input
                      type="checkbox"
                      checked={selectedCollectionIds.has(col.id)}
                      on:change={() => toggleCollectionCheck(col.id)}
                      aria-label={`เลือกชุด API ${col.name}`}
                    />
                    <div>
                      <div class="col-name-row">
                        <h4>{col.name}</h4>
                        <span class="format-badge">{col.format_type}</span>
                        {#if col.version}
                          <span class="version-chip">v{col.version}</span>
                        {/if}
                      </div>
                      <div class="col-sub-meta">
                        <span class="ep-count-pill">{eps.length} Endpoints</span
                        >
                        {#if col.base_url}
                          <span
                            class="base-url-chip"
                            title="Base URL ของ Collection">{col.base_url}</span
                          >
                        {/if}
                        <span class="date-label">
                          อัปเดต {new Date(col.created_at).toLocaleDateString(
                            "th-TH",
                            {
                              day: "2-digit",
                              month: "short",
                              year: "numeric",
                            },
                          )}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div class="col-actions">
                    <button
                      type="button"
                      class="btn-workspace"
                      on:click={() => openWorkspace(col)}
                    >
                      เปิดจัดการ & ทดสอบ ({eps.length})
                    </button>
                    <button
                      type="button"
                      class="btn-icon-action"
                      title="เพิ่ม Endpoint เข้าชุดนี้"
                      on:click={() => openStudioForNew(col.id)}
                    >
                      + เพิ่ม API
                    </button>
                    <button
                      type="button"
                      class="btn-icon-action"
                      title="ส่งออกเป็นไฟล์ JSON"
                      on:click={() => exportCollectionJson(col)}
                    >
                      Export
                    </button>
                    <button
                      type="button"
                      class="btn-icon-action danger"
                      title="ลบชุด API Collection นี้"
                      on:click={() => handleDeleteCollection(col.id, col.name)}
                    >
                      ลบ
                    </button>
                  </div>
                </div>

                <!-- Preview up to 4 endpoints -->
                {#if eps.length > 0}
                  <div class="endpoints-preview-bar">
                    {#each eps.slice(0, 4) as ep, idx}
                      <button
                        type="button"
                        class="ep-preview-pill"
                        on:click={() => openWorkspace(col)}
                        title={`คลิกเพื่อเปิดจัดการและยิงทดสอบ ${ep.method} ${ep.path}`}
                      >
                        <span class="m-tag {(ep.method || 'GET').toLowerCase()}"
                          >{ep.method || "GET"}</span
                        >
                        <span class="p-text">{ep.path || ep.url}</span>
                      </button>
                    {/each}
                    {#if eps.length > 4}
                      <button
                        type="button"
                        class="ep-more-pill"
                        on:click={() => openWorkspace(col)}
                      >
                        ดูทั้งหมด +{eps.length - 4} รายการ
                      </button>
                    {/if}
                  </div>
                {/if}
              </article>
            {/each}
          </div>
        {/if}
      </div>
    </section>
  </div>
</div>

<!-- =========================================================================
     MODAL 1: INTERACTIVE COLLECTION WORKSPACE & LIVE ENDPOINT TEST RUNNER
     ========================================================================= -->
{#if showWorkspaceModal && activeCollection}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="modal-backdrop"
    on:click|self={() => (showWorkspaceModal = false)}
  >
    <div
      class="modal-window workspace-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ws-modal-title"
    >
      <div class="modal-header">
        <div class="modal-title-block">
          <span class="modal-eyebrow"
            >COLLECTION WORKSPACE & ENDPOINT RUNNER</span
          >
          <h3 id="ws-modal-title">{wsName || activeCollection.name}</h3>
        </div>
        <div class="modal-header-actions">
          <button
            type="button"
            class="btn-secondary-sm"
            on:click={() =>
              exportCollectionJson({
                ...activeCollection,
                name: wsName,
                version: wsVersion,
                base_url: wsBaseUrl,
                endpoints: wsEndpoints,
              })}
          >
            Export JSON
          </button>
          <button
            type="button"
            class="btn-primary-sm"
            on:click={() => openStudioForNew(activeCollection.id)}
          >
            + เพิ่ม Endpoint ในชุดนี้
          </button>
          <button
            type="button"
            class="modal-close-btn"
            on:click={() => (showWorkspaceModal = false)}
            aria-label="ปิดหน้าต่างจัดการ Collection"
          >
            ✕
          </button>
        </div>
      </div>

      <div class="modal-body workspace-body">
        <!-- Collection Settings Bar (Editable Name, Version, Base URL) -->
        <div class="ws-settings-grid">
          <div class="ws-field">
            <label for="ws-col-name">ชื่อชุด API Collection</label>
            <input
              id="ws-col-name"
              type="text"
              class="spectra-input"
              bind:value={wsName}
            />
          </div>
          <div class="ws-field">
            <label for="ws-col-base"
              >Base URL (ใช้เติมหน้า Path เช่น `/api/v1/...` เวลายิงทดสอบ)</label
            >
            <input
              id="ws-col-base"
              type="text"
              class="spectra-input mono"
              placeholder="https://api.example.com"
              bind:value={wsBaseUrl}
            />
          </div>
          <div class="ws-field small">
            <label for="ws-col-ver">Version</label>
            <input
              id="ws-col-ver"
              type="text"
              class="spectra-input"
              bind:value={wsVersion}
            />
          </div>
          <div class="ws-field action">
            <button
              type="button"
              class="btn-save-meta"
              disabled={isSavingWorkspace}
              on:click={saveWorkspaceMetadata}
            >
              {isSavingWorkspace ? "กำลังบันทึก..." : "บันทึกการตั้งค่าชุดนี้"}
            </button>
          </div>
        </div>

        <!-- Endpoint Filter Bar -->
        <div class="ws-filter-bar">
          <div class="ws-search">
            <input
              type="text"
              class="spectra-input"
              placeholder="ค้นหา Endpoint จาก Path, ชื่อ หรือหมวดหมู่..."
              bind:value={wsSearch}
            />
          </div>
          <div
            class="method-pills"
            role="group"
            aria-label="กรองตาม HTTP Method"
          >
            {#each ["ALL", "GET", "POST", "PUT", "PATCH", "DELETE"] as m}
              <button
                type="button"
                class="m-filter-pill"
                class:active={wsMethodFilter === m}
                on:click={() => (wsMethodFilter = m)}
              >
                {m}
              </button>
            {/each}
          </div>
        </div>

        <div class="ws-split-layout">
          <!-- Left: Endpoint List -->
          <div class="ws-endpoints-list">
            {#if filteredWorkspaceEndpoints.length === 0}
              <div class="ws-empty">
                <p>ไม่พบ Endpoint ตามเงื่อนไขที่ค้นหา</p>
              </div>
            {:else}
              {#each filteredWorkspaceEndpoints as ep (ep._idx)}
                <div
                  class="ws-ep-card"
                  class:active-test={wsActiveTestEndpoint === ep}
                >
                  <div class="ws-ep-main">
                    <span
                      class="method-badge {(ep.method || 'GET').toLowerCase()}"
                    >
                      {(ep.method || "GET").toUpperCase()}
                    </span>
                    <div class="ws-ep-info">
                      <div class="ws-ep-path">{ep.path || ep.url}</div>
                      <div class="ws-ep-summary">
                        <span>{ep.name || ep.summary || "ไม่มีคำอธิบาย"}</span>
                        {#if ep.category}
                          <span class="cat-chip">{ep.category}</span>
                        {/if}
                      </div>
                    </div>
                  </div>

                  <div class="ws-ep-actions">
                    <button
                      type="button"
                      class="btn-ep-test"
                      disabled={wsTestingIndex === ep._idx}
                      on:click={() => testEndpointInWorkspace(ep, ep._idx)}
                    >
                      {wsTestingIndex === ep._idx ? "กำลังยิง..." : "ยิงทดสอบ"}
                    </button>
                    <button
                      type="button"
                      class="btn-ep-sub"
                      on:click={() =>
                        openStudioForEdit(activeCollection, ep, ep._idx)}
                    >
                      แก้ไข
                    </button>
                    <button
                      type="button"
                      class="btn-ep-sub"
                      on:click={() => copyEndpointCurl(ep, wsBaseUrl)}
                    >
                      cURL
                    </button>
                    <button
                      type="button"
                      class="btn-ep-sub danger"
                      on:click={() => deleteEndpointInWorkspace(ep._idx)}
                    >
                      ลบ
                    </button>
                  </div>
                </div>
              {/each}
            {/if}
          </div>

          <!-- Right: Live Test Response Inspector -->
          <div class="ws-inspector-pane">
            <div class="inspector-head">
              <h4>Live Response Inspector</h4>
              {#if wsTestResult && wsTestResult.status_code}
                <div class="telemetry-pills">
                  <span
                    class="status-pill"
                    class:ok={wsTestResult.status_code < 400}
                    class:err={wsTestResult.status_code >= 400}
                  >
                    HTTP {wsTestResult.status_code}
                    {wsTestResult.status_text || ""}
                  </span>
                  <span class="metric-pill">{wsTestResult.latency_ms} ms</span>
                  {#if wsTestResult.response_size_bytes !== undefined}
                    <span class="metric-pill"
                      >{(wsTestResult.response_size_bytes / 1024).toFixed(2)} KB</span
                    >
                  {/if}
                </div>
              {/if}
            </div>

            {#if wsTestingIndex !== null}
              <div class="inspector-empty">
                <span class="spinner"></span>
                <p>กำลังส่งคำขอไปยัง Endpoint เป้าหมาย...</p>
              </div>
            {:else if !wsTestResult}
              <div class="inspector-empty">
                <p>
                  กดปุ่ม <strong>"ยิงทดสอบ"</strong> ที่ Endpoint ด้านซ้าย เพื่อตรวจสอบ
                  Status Code, Latency และ Response Body จริง
                </p>
              </div>
            {:else if !wsTestResult.success}
              <div class="inspector-error">
                <strong>การเชื่อมต่อล้มเหลวหรือต้องการ Base URL</strong>
                <p>{wsTestResult.error}</p>
                {#if wsTestResult.tested_url}
                  <span class="tested-url"
                    >URL ที่ใช้ทดสอบ: {wsTestResult.tested_url}</span
                  >
                {/if}
              </div>
            {:else}
              <div class="inspector-content">
                <div class="tested-url-bar">
                  <span
                    class="m-tag {(wsTestResult.method || 'GET').toLowerCase()}"
                    >{wsTestResult.method}</span
                  >
                  <code>{wsTestResult.tested_url}</code>
                </div>
                <div class="code-label">Response Body</div>
                <pre class="response-pre">{wsTestResult.response_body ||
                    wsTestResult.preview ||
                    "(Empty Response Body)"}</pre>

                {#if wsTestResult.response_headers && Object.keys(wsTestResult.response_headers).length > 0}
                  <div class="code-label">Response Headers</div>
                  <pre class="response-pre headers">{JSON.stringify(
                      wsTestResult.response_headers,
                      null,
                      2,
                    )}</pre>
                {/if}
              </div>
            {/if}
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- =========================================================================
     MODAL 2: SPECTRA API STUDIO (MANUAL / CURL BUILDER & LIVE TEST SEND)
     ========================================================================= -->
{#if showStudioModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-backdrop" on:click|self={() => (showStudioModal = false)}>
    <div
      class="modal-window studio-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="studio-modal-title"
    >
      <div class="modal-header">
        <div class="modal-title-block">
          <span class="modal-eyebrow">SPECTRA API STUDIO</span>
          <h3 id="studio-modal-title">
            {studioMode === "edit"
              ? `แก้ไข Endpoint: ${studioName}`
              : "สร้างหรือนำเข้า API Endpoint (Manual & cURL)"}
          </h3>
        </div>
        <div class="modal-header-actions">
          <button
            type="button"
            class="btn-secondary-sm"
            on:click={() => (showCurlDrawer = !showCurlDrawer)}
          >
            {showCurlDrawer
              ? "ซ่อนช่องวาง cURL"
              : "วางคำสั่ง cURL (Import cURL)"}
          </button>
          <button
            type="button"
            class="modal-close-btn"
            on:click={() => (showStudioModal = false)}
            aria-label="ปิดหน้าต่าง API Studio"
          >
            ✕
          </button>
        </div>
      </div>

      <div class="modal-body studio-body">
        {#if showCurlDrawer}
          <div class="curl-drawer">
            <div class="curl-drawer-head">
              <strong
                >นำเข้าจากคำสั่ง cURL (รองรับทั้ง Bash และ Windows
                PowerShell/CMD)</strong
              >
              <span
                >คัดลอกจาก Chrome DevTools (Copy as cURL) หรือ Postman
                แล้วกดแปลงข้อมูล</span
              >
            </div>
            <textarea
              rows="4"
              class="spectra-textarea mono"
              placeholder={'curl -X POST "https://api.example.com/v1/login" -H "Content-Type: application/json" -d \'{"username":"admin"}\''}
              bind:value={studioCurlInput}></textarea>
            <div class="curl-drawer-actions">
              <button
                type="button"
                class="btn-primary-sm"
                on:click={parseCurlCommand}
              >
                แยกข้อมูลจาก cURL เข้าฟอร์มอัตโนมัติ
              </button>
            </div>
          </div>
        {/if}

        <!-- Target Collection Selection (when creating new endpoint) -->
        {#if studioMode === "create"}
          <div class="studio-collection-bar">
            <div class="save-mode-switch">
              <button
                type="button"
                class="switch-pill"
                class:active={studioSaveMode === "new_collection"}
                on:click={() => (studioSaveMode = "new_collection")}
              >
                สร้างเป็น Collection ใหม่
              </button>
              <button
                type="button"
                class="switch-pill"
                class:active={studioSaveMode === "existing_collection"}
                disabled={collections.length === 0}
                on:click={() => (studioSaveMode = "existing_collection")}
              >
                เพิ่มเข้า Collection เดิมที่มีอยู่ ({collections.length})
              </button>
            </div>

            <div class="studio-meta-grid">
              {#if studioSaveMode === "new_collection"}
                <div class="form-field">
                  <label for="studio-col-name">ชื่อ Collection ใหม่</label>
                  <input
                    id="studio-col-name"
                    type="text"
                    class="spectra-input"
                    placeholder="เช่น Authentication Service API"
                    bind:value={studioCollectionName}
                  />
                </div>
              {:else}
                <div class="form-field">
                  <label for="studio-target-col">เลือก Collection ปลายทาง</label
                  >
                  <select
                    id="studio-target-col"
                    class="spectra-input"
                    bind:value={studioTargetCollectionId}
                  >
                    {#each collections as col}
                      <option value={col.id}
                        >{col.name} ({col.endpoint_count || 0} endpoints)</option
                      >
                    {/each}
                  </select>
                </div>
              {/if}

              <div class="form-field">
                <label for="studio-ep-name">ชื่อเรียก Endpoint</label>
                <input
                  id="studio-ep-name"
                  type="text"
                  class="spectra-input"
                  placeholder="เช่น เข้าสู่ระบบผู้ใช้งาน (User Login)"
                  bind:value={studioName}
                />
              </div>

              <div class="form-field">
                <label for="studio-ep-cat">หมวดหมู่ / โฟลเดอร์ (Category)</label
                >
                <input
                  id="studio-ep-cat"
                  type="text"
                  class="spectra-input"
                  placeholder="เช่น Auth, Orders, Users"
                  bind:value={studioCategory}
                />
              </div>
            </div>
          </div>
        {:else}
          <div class="studio-meta-grid">
            <div class="form-field">
              <label for="studio-edit-name">ชื่อเรียก Endpoint</label>
              <input
                id="studio-edit-name"
                type="text"
                class="spectra-input"
                bind:value={studioName}
              />
            </div>
            <div class="form-field">
              <label for="studio-edit-cat">หมวดหมู่ (Category)</label>
              <input
                id="studio-edit-cat"
                type="text"
                class="spectra-input"
                bind:value={studioCategory}
              />
            </div>
            <div class="form-field">
              <label for="studio-edit-base">Base URL ของชุดนี้</label>
              <input
                id="studio-edit-base"
                type="text"
                class="spectra-input mono"
                placeholder="https://api.example.com"
                bind:value={studioBaseUrl}
              />
            </div>
          </div>
        {/if}

        <!-- Request Bar: Method + URL + Live Test Send -->
        <div class="studio-request-bar">
          <select
            class="method-select {studioMethod.toLowerCase()}"
            bind:value={studioMethod}
            aria-label="HTTP Method"
          >
            {#each HTTP_METHODS as m}
              <option value={m}>{m}</option>
            {/each}
          </select>
          <input
            type="text"
            class="url-input mono"
            placeholder="https://api.example.com/v1/users หรือ /api/v1/users"
            bind:value={studioUrl}
          />
          <button
            type="button"
            class="btn-test-send"
            disabled={isTestingDirect || !studioUrl.trim()}
            on:click={handleStudioTestSend}
          >
            {isTestingDirect ? "กำลังยิง..." : "ยิงทดสอบสด (Test Send)"}
          </button>
        </div>

        <!-- Tabs: Params | Auth | Headers | Body -->
        <div class="studio-tabs-header">
          <button
            type="button"
            class="studio-tab"
            class:active={studioActiveTab === "params"}
            on:click={() => (studioActiveTab = "params")}
          >
            Query Params ({studioQueryParams.filter((q) => q.key.trim())
              .length})
          </button>
          <button
            type="button"
            class="studio-tab"
            class:active={studioActiveTab === "auth"}
            on:click={() => (studioActiveTab = "auth")}
          >
            Authorization ({studioAuthType.toUpperCase()})
          </button>
          <button
            type="button"
            class="studio-tab"
            class:active={studioActiveTab === "headers"}
            on:click={() => (studioActiveTab = "headers")}
          >
            Headers
          </button>
          <button
            type="button"
            class="studio-tab"
            class:active={studioActiveTab === "body"}
            on:click={() => (studioActiveTab = "body")}
          >
            Request Body
          </button>
        </div>

        <div class="studio-tab-panel">
          {#if studioActiveTab === "params"}
            <div class="kv-header">
              <span>พารามิเตอร์แนบท้าย URL (Query Parameters)</span>
              <button
                type="button"
                class="btn-add-row"
                on:click={addQueryParamRow}>+ เพิ่มพารามิเตอร์</button
              >
            </div>
            <div class="kv-rows">
              {#each studioQueryParams as row, idx}
                <div class="kv-row">
                  <input
                    type="checkbox"
                    bind:checked={row.enabled}
                    aria-label="เปิดใช้งานพารามิเตอร์"
                  />
                  <input
                    type="text"
                    class="spectra-input mono"
                    placeholder="Key (เช่น page)"
                    bind:value={row.key}
                  />
                  <input
                    type="text"
                    class="spectra-input mono"
                    placeholder="Value (เช่น 1)"
                    bind:value={row.value}
                  />
                  <button
                    type="button"
                    class="btn-del-row"
                    on:click={() => removeQueryParamRow(idx)}>ลบ</button
                  >
                </div>
              {/each}
            </div>
          {:else if studioActiveTab === "auth"}
            <div class="auth-config-box">
              <div class="form-field">
                <label for="studio-auth-type"
                  >รูปแบบการยืนยันตัวตน (Auth Type)</label
                >
                <select
                  id="studio-auth-type"
                  class="spectra-input"
                  bind:value={studioAuthType}
                >
                  <option value="none">No Auth (ไม่ระบุ)</option>
                  <option value="bearer">Bearer Token (JWT / OAuth2)</option>
                  <option value="apikey"
                    >API Key (Header หรือ Query Param)</option
                  >
                  <option value="basic">Basic Auth (Username / Password)</option
                  >
                </select>
              </div>

              {#if studioAuthType === "bearer"}
                <div class="form-field">
                  <label for="studio-bearer-token">Bearer Token</label>
                  <input
                    id="studio-bearer-token"
                    type="text"
                    class="spectra-input mono"
                    placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                    bind:value={studioAuthBearer}
                  />
                </div>
              {:else if studioAuthType === "apikey"}
                <div class="auth-grid">
                  <div class="form-field">
                    <label for="studio-apikey-name">ชื่อ Key</label>
                    <input
                      id="studio-apikey-name"
                      type="text"
                      class="spectra-input mono"
                      bind:value={studioAuthApiKeyName}
                    />
                  </div>
                  <div class="form-field">
                    <label for="studio-apikey-val">ค่า API Key</label>
                    <input
                      id="studio-apikey-val"
                      type="text"
                      class="spectra-input mono"
                      bind:value={studioAuthApiKeyValue}
                    />
                  </div>
                  <div class="form-field">
                    <label for="studio-apikey-in">ส่งไปที่</label>
                    <select
                      id="studio-apikey-in"
                      class="spectra-input"
                      bind:value={studioAuthApiKeyIn}
                    >
                      <option value="header">HTTP Header</option>
                      <option value="query">Query Parameter</option>
                    </select>
                  </div>
                </div>
              {:else if studioAuthType === "basic"}
                <div class="auth-grid">
                  <div class="form-field">
                    <label for="studio-basic-user">Username</label>
                    <input
                      id="studio-basic-user"
                      type="text"
                      class="spectra-input"
                      bind:value={studioAuthBasicUser}
                    />
                  </div>
                  <div class="form-field">
                    <label for="studio-basic-pass">Password</label>
                    <input
                      id="studio-basic-pass"
                      type="password"
                      class="spectra-input"
                      bind:value={studioAuthBasicPass}
                    />
                  </div>
                </div>
              {/if}
            </div>
          {:else if studioActiveTab === "headers"}
            <div class="kv-header">
              <div class="mode-pills">
                <button
                  type="button"
                  class="mini-pill"
                  class:active={studioHeaderMode === "table"}
                  on:click={() => toggleHeaderViewMode("table")}
                >
                  ตาราง Key-Value
                </button>
                <button
                  type="button"
                  class="mini-pill"
                  class:active={studioHeaderMode === "json"}
                  on:click={() => toggleHeaderViewMode("json")}
                >
                  Raw JSON
                </button>
              </div>
              {#if studioHeaderMode === "table"}
                <button
                  type="button"
                  class="btn-add-row"
                  on:click={addHeaderRow}>+ เพิ่ม Header</button
                >
              {/if}
            </div>

            {#if studioHeaderMode === "table"}
              <div class="kv-rows">
                {#each studioHeaderRows as row, idx}
                  <div class="kv-row">
                    <input
                      type="checkbox"
                      bind:checked={row.enabled}
                      aria-label="เปิดใช้งาน Header"
                    />
                    <input
                      type="text"
                      class="spectra-input mono"
                      placeholder="Header Name (เช่น Authorization)"
                      bind:value={row.key}
                    />
                    <input
                      type="text"
                      class="spectra-input mono"
                      placeholder="Header Value"
                      bind:value={row.value}
                    />
                    <button
                      type="button"
                      class="btn-del-row"
                      on:click={() => removeHeaderRow(idx)}>ลบ</button
                    >
                  </div>
                {/each}
              </div>
            {:else}
              <textarea
                rows="5"
                class="spectra-textarea mono"
                bind:value={studioHeadersJson}></textarea>
            {/if}
          {:else if studioActiveTab === "body"}
            <div class="kv-header">
              <div class="mode-pills">
                <button
                  type="button"
                  class="mini-pill"
                  class:active={studioBodyMode === "none"}
                  on:click={() => (studioBodyMode = "none")}
                >
                  ไม่มี Body
                </button>
                <button
                  type="button"
                  class="mini-pill"
                  class:active={studioBodyMode === "json"}
                  on:click={() => (studioBodyMode = "json")}
                >
                  JSON Payload
                </button>
                <button
                  type="button"
                  class="mini-pill"
                  class:active={studioBodyMode === "raw"}
                  on:click={() => (studioBodyMode = "raw")}
                >
                  Raw / Form Data
                </button>
              </div>
              {#if studioBodyMode === "json"}
                <button
                  type="button"
                  class="btn-add-row"
                  on:click={prettifyStudioBody}
                >
                  จัดรูปแบบ & ตรวจ JSON
                </button>
              {/if}
            </div>

            {#if studioBodyMode !== "none"}
              <textarea
                rows="6"
                class="spectra-textarea mono"
                placeholder={'{\n  "username": "qa_tester",\n  "role": "admin"\n}'}
                bind:value={studioBodyText}></textarea>
            {/if}
          {/if}
        </div>

        <!-- Live Test Result inside Studio Modal -->
        {#if studioDirectResult}
          <div class="studio-response-box">
            <div class="studio-res-head">
              <strong>ผลลัพธ์การยิงทดสอบสด (Live Response)</strong>
              {#if studioDirectResult.status_code}
                <div class="telemetry-pills">
                  <span
                    class="status-pill"
                    class:ok={studioDirectResult.status_code < 400}
                    class:err={studioDirectResult.status_code >= 400}
                  >
                    HTTP {studioDirectResult.status_code}
                    {studioDirectResult.status_text || ""}
                  </span>
                  <span class="metric-pill"
                    >{studioDirectResult.latency_ms} ms</span
                  >
                </div>
              {/if}
            </div>
            {#if studioDirectResult.success}
              <pre
                class="response-pre compact">{studioDirectResult.response_body ||
                  studioDirectResult.preview ||
                  "(Empty Response)"}</pre>
            {:else}
              <div class="inspector-error compact">
                {studioDirectResult.error}
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <div class="modal-footer">
        <button
          type="button"
          class="btn-cancel"
          on:click={() => (showStudioModal = false)}>ยกเลิก</button
        >
        <button
          type="button"
          class="btn-primary-spectra"
          disabled={isSavingStudio || !studioUrl.trim()}
          on:click={handleSaveStudio}
        >
          {#if isSavingStudio}
            กำลังบันทึก...
          {:else if studioMode === "edit"}
            บันทึกการแก้ไข Endpoint
          {:else if studioSaveMode === "existing_collection"}
            เพิ่ม Endpoint เข้า Collection ที่เลือก
          {:else}
            บันทึกเป็น API Collection ใหม่
          {/if}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- =========================================================================
     MODAL 3: WEB API DISCOVERY (OPENAPI / SWAGGER & ROUTE SNIFFER)
     ========================================================================= -->
{#if showSnifferModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="modal-backdrop" on:click|self={() => (showSnifferModal = false)}>
    <div
      class="modal-window sniffer-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sniffer-modal-title"
    >
      <div class="modal-header">
        <div class="modal-title-block">
          <span class="modal-eyebrow">AUTOMATED OPENAPI & ROUTE DISCOVERY</span>
          <h3 id="sniffer-modal-title">สำรวจและดึง API จาก URL ระบบเป้าหมาย</h3>
        </div>
        <button
          type="button"
          class="modal-close-btn"
          on:click={() => (showSnifferModal = false)}
          aria-label="ปิดหน้าต่าง Web API Discovery"
        >
          ✕
        </button>
      </div>

      <div class="modal-body">
        <div class="sniffer-form-grid">
          <div class="form-field full">
            <label for="sniffer-target-url"
              >Target System URL (ระบบจะสแกนหา `/openapi.json`, `/swagger.json`,
              `/v3/api-docs` และ API Routes)</label
            >
            <input
              id="sniffer-target-url"
              type="text"
              class="spectra-input mono"
              placeholder="https://api.example.com หรือ http://localhost:5001"
              bind:value={snifferUrl}
            />
          </div>
          <div class="form-field">
            <label for="sniffer-user">Username (ทางเลือก)</label>
            <input
              id="sniffer-user"
              type="text"
              class="spectra-input"
              bind:value={snifferUsername}
            />
          </div>
          <div class="form-field">
            <label for="sniffer-pass">Password (ทางเลือก)</label>
            <input
              id="sniffer-pass"
              type="password"
              class="spectra-input"
              bind:value={snifferPassword}
            />
          </div>
        </div>

        <button
          type="button"
          class="btn-primary-gradient"
          disabled={isSniffing || !snifferUrl.trim()}
          on:click={handleStartSniffing}
        >
          {isSniffing
            ? "กำลังสำรวจ OpenAPI Manifest และ API Routes..."
            : "เริ่มสำรวจ API บนระบบเป้าหมาย"}
        </button>

        {#if sniffedEndpoints.length > 0}
          <div class="sniffer-results-box">
            <!-- Grouped Target Configuration (A3) -->
            <div class="studio-collection-bar">
              <div class="save-mode-switch">
                <button
                  type="button"
                  class="switch-pill"
                  class:active={snifferImportMode === "new"}
                  on:click={() => (snifferImportMode = "new")}
                >
                  รวบเป็น 1 Collection ใหม่
                </button>
                <button
                  type="button"
                  class="switch-pill"
                  class:active={snifferImportMode === "append"}
                  disabled={collections.length === 0}
                  on:click={() => (snifferImportMode = "append")}
                >
                  เพิ่มเข้า Collection เดิม ({collections.length})
                </button>
              </div>

              {#if snifferImportMode === "new"}
                <div class="form-field">
                  <label for="sniffer-col-name"
                    >ชื่อ Collection ที่จะสร้าง</label
                  >
                  <input
                    id="sniffer-col-name"
                    type="text"
                    class="spectra-input"
                    bind:value={snifferCollectionName}
                  />
                </div>
              {:else}
                <div class="form-field">
                  <label for="sniffer-target-col"
                    >เลือก Collection ปลายทาง</label
                  >
                  <select
                    id="sniffer-target-col"
                    class="spectra-input"
                    bind:value={snifferTargetCollectionId}
                  >
                    {#each collections as col}
                      <option value={col.id}
                        >{col.name} ({col.endpoint_count || 0} endpoints)</option
                      >
                    {/each}
                  </select>
                </div>
              {/if}
            </div>

            <div class="sniffer-list-head">
              <label class="bulk-check-label">
                <input
                  type="checkbox"
                  checked={selectedSniffedIndices.size ===
                    sniffedEndpoints.length}
                  on:change={toggleAllSniffed}
                />
                <span
                  >เลือกทั้งหมด ({selectedSniffedIndices.size}/{sniffedEndpoints.length}
                  Endpoints)</span
                >
              </label>
            </div>

            <div class="sniffer-list">
              {#each sniffedEndpoints as ep, idx}
                <!-- svelte-ignore a11y-click-events-have-key-events -->
                <!-- svelte-ignore a11y-no-static-element-interactions -->
                <div
                  class="sniffer-item"
                  class:selected={selectedSniffedIndices.has(idx)}
                  on:click={() => toggleSniffedSelection(idx)}
                >
                  <input
                    type="checkbox"
                    checked={selectedSniffedIndices.has(idx)}
                    on:click|stopPropagation
                    on:change={() => toggleSniffedSelection(idx)}
                  />
                  <span
                    class="method-badge {(ep.method || 'GET').toLowerCase()}"
                    >{ep.method || "GET"}</span
                  >
                  <span class="sniffer-path">{ep.path}</span>
                  <span class="sniffer-summary">{ep.summary || ""}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      <div class="modal-footer">
        <button
          type="button"
          class="btn-cancel"
          on:click={() => (showSnifferModal = false)}>ปิด</button
        >
        {#if sniffedEndpoints.length > 0}
          <button
            type="button"
            class="btn-primary-spectra"
            disabled={isSniffing || selectedSniffedIndices.size === 0}
            on:click={handleSaveSniffed}
          >
            บันทึก {selectedSniffedIndices.size} Endpoints เป็น 1 ชุดข้อมูล
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<ExtensionSyncModal
  bind:show={showExtensionModal}
  {selectedProject}
  {collections}
  on:close={() => (showExtensionModal = false)}
  on:imported={loadCollections}
/>

<style>
  .api-admin-container {
    width: 100%;
    padding: 0 0 32px;
    color: var(--text, #f8fafc);
    font-family: "Prompt", sans-serif;
  }

  /* Header Banner */
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 24px;
    background: var(--surface-card, rgba(24, 19, 38, 0.72));
    padding: 20px 24px;
    border-radius: 20px;
    border: 1px solid var(--surface-border, rgba(168, 85, 247, 0.18));
    backdrop-filter: blur(16px);
  }

  .header-main {
    display: flex;
    align-items: flex-start;
    gap: 16px;
  }

  .header-icon-box {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: var(--primary-light, #c084fc);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .header-badge-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }

  .eyebrow-pill {
    font-family: "Outfit", sans-serif;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--primary-light, #c084fc);
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.28);
    padding: 2px 10px;
    border-radius: 999px;
  }

  .stat-pill {
    font-family: "Outfit", sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 2px 9px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-secondary, #cbd5e1);
  }

  .stat-pill.cyan {
    background: rgba(6, 182, 212, 0.14);
    color: #22d3ee;
    border: 1px solid rgba(6, 182, 212, 0.25);
  }

  .page-header h2 {
    margin: 0;
    font-family: "Outfit", "Prompt", sans-serif;
    font-size: 1.45rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .subtitle {
    margin: 4px 0 0;
    font-size: 0.85rem;
    color: var(--text-muted, #94a3b8);
  }

  .project-selector-box {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 240px;
  }

  .selector-label {
    font-size: 0.76rem;
    font-weight: 600;
    color: var(--text-secondary, #cbd5e1);
  }

  /* Two-Column Main Grid */
  .content-grid {
    display: grid;
    grid-template-columns: 380px minmax(0, 1fr);
    gap: 24px;
    align-items: start;
  }

  .panel-card {
    background: var(--surface-card, rgba(24, 19, 38, 0.72));
    border: 1px solid var(--surface-border, rgba(168, 85, 247, 0.18));
    border-radius: 20px;
    padding: 22px;
    backdrop-filter: blur(16px);
  }

  .card-head h3,
  .repo-title-group h3 {
    margin: 0;
    font-family: "Outfit", "Prompt", sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .card-desc {
    margin: 4px 0 16px;
    font-size: 0.8rem;
    color: var(--text-muted, #94a3b8);
    line-height: 1.45;
  }

  /* Drag & Drop Zone */
  .upload-dropzone {
    border: 1.5px dashed rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    padding: 22px 16px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s ease;
    background: rgba(9, 7, 17, 0.55);
    margin-bottom: 16px;
  }

  .upload-dropzone:hover,
  .upload-dropzone.drag-over {
    border-color: var(--primary, #a855f7);
    background: rgba(168, 85, 247, 0.1);
    box-shadow: 0 0 24px rgba(168, 85, 247, 0.18);
  }

  .upload-dropzone.has-file {
    border-style: solid;
    border-color: rgba(16, 185, 129, 0.45);
    background: rgba(16, 185, 129, 0.08);
  }

  .drop-prompt {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .drop-icon-circle {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    background: rgba(168, 85, 247, 0.14);
    color: var(--primary-light, #c084fc);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .prompt-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--text, #f8fafc);
  }

  .prompt-sub {
    font-size: 0.76rem;
    color: var(--text-muted, #94a3b8);
  }

  .file-picked {
    display: flex;
    align-items: center;
    gap: 12px;
    text-align: left;
  }

  .picked-icon {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .picked-meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .file-name {
    font-weight: 600;
    font-size: 0.86rem;
    color: #34d399;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .file-size {
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
  }

  .clear-file-btn {
    background: rgba(239, 68, 68, 0.14);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #f87171;
    font-size: 0.74rem;
    padding: 4px 10px;
    border-radius: 8px;
    cursor: pointer;
  }

  .form-group {
    margin-bottom: 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label,
  .form-field label,
  .ws-field label {
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-secondary, #cbd5e1);
  }

  .spectra-input,
  .spectra-textarea {
    width: 100%;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid rgba(168, 85, 247, 0.22);
    background: var(--bg, #090711);
    color: var(--text, #f8fafc);
    font-family: "Prompt", sans-serif;
    font-size: 0.85rem;
    outline: none;
    box-sizing: border-box;
  }

  .spectra-input.mono,
  .spectra-textarea.mono {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.81rem;
  }

  .spectra-input:focus,
  .spectra-textarea:focus {
    border-color: var(--primary, #a855f7);
    box-shadow: 0 0 0 2px rgba(168, 85, 247, 0.22);
  }

  .btn-primary-gradient {
    width: 100%;
    padding: 11px 16px;
    border: none;
    border-radius: 12px;
    background: var(
      --gradient-main,
      linear-gradient(135deg, #a855f7 0%, #6366f1 50%, #06b6d4 100%)
    );
    color: #ffffff;
    font-weight: 600;
    font-size: 0.88rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 8px 24px rgba(168, 85, 247, 0.28);
    transition: all 0.2s ease;
  }

  .btn-primary-gradient:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 12px 28px rgba(168, 85, 247, 0.4);
  }

  .btn-primary-gradient:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    box-shadow: none;
  }

  .section-divider {
    margin: 18px 0 14px;
    text-align: center;
    position: relative;
  }

  .section-divider::before {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 1px;
    background: rgba(168, 85, 247, 0.16);
  }

  .section-divider span {
    position: relative;
    background: #161124;
    padding: 0 10px;
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
  }

  .tools-stack {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .tool-action-card {
    width: 100%;
    text-align: left;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: rgba(18, 15, 29, 0.75);
    border: 1px solid rgba(168, 85, 247, 0.18);
    color: var(--text, #f8fafc);
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .tool-action-card:hover:not(:disabled) {
    border-color: rgba(168, 85, 247, 0.48);
    background: rgba(168, 85, 247, 0.1);
    transform: translateY(-1px);
  }

  .tool-action-card:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .tool-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .tool-icon.violet {
    background: rgba(168, 85, 247, 0.16);
    color: #c084fc;
  }

  .tool-icon.cyan {
    background: rgba(6, 182, 212, 0.16);
    color: #22d3ee;
  }

  .tool-icon.emerald {
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
  }

  .tool-copy {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .tool-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text, #f8fafc);
  }

  .tool-sub {
    font-size: 0.75rem;
    color: var(--text-muted, #94a3b8);
    line-height: 1.35;
  }

  /* Right Panel: Repository */
  .repo-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }

  .repo-title-group {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .project-tag {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 999px;
    background: rgba(168, 85, 247, 0.16);
    color: var(--primary-light, #c084fc);
    border: 1px solid rgba(168, 85, 247, 0.3);
  }

  .repo-top-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-studio-quick {
    background: rgba(168, 85, 247, 0.16);
    border: 1px solid rgba(168, 85, 247, 0.38);
    color: var(--primary-light, #c084fc);
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.16s ease;
  }

  .btn-studio-quick:hover {
    background: rgba(168, 85, 247, 0.28);
    color: #ffffff;
  }

  .btn-bulk-danger {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #f87171;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
  }

  .repo-toolbar {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }

  .search-box {
    flex: 1;
    min-width: 220px;
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg, #090711);
    border: 1px solid rgba(168, 85, 247, 0.22);
    border-radius: 8px;
    padding: 0 12px;
    color: var(--text-muted, #94a3b8);
  }

  .search-box input {
    flex: 1;
    border: none;
    background: transparent;
    color: var(--text, #f8fafc);
    padding: 9px 0;
    font-size: 0.84rem;
    outline: none;
  }

  .clear-search {
    background: none;
    border: none;
    color: var(--primary-light, #c084fc);
    font-size: 0.75rem;
    cursor: pointer;
  }

  .filter-group {
    display: flex;
    gap: 8px;
  }

  .filter-select {
    background: var(--bg, #090711);
    border: 1px solid rgba(168, 85, 247, 0.22);
    border-radius: 8px;
    color: var(--text, #f8fafc);
    padding: 8px 12px;
    font-size: 0.82rem;
    outline: none;
  }

  .bulk-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    padding: 8px 12px;
    border-radius: 8px;
    background: rgba(18, 15, 29, 0.65);
    border: 1px solid rgba(168, 85, 247, 0.12);
    margin-bottom: 14px;
    font-size: 0.78rem;
  }

  .bulk-check-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    color: var(--text-secondary, #cbd5e1);
    cursor: pointer;
  }

  .bulk-hint {
    color: var(--text-muted, #94a3b8);
    font-size: 0.75rem;
  }

  .collections-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .collection-card {
    background: rgba(18, 15, 29, 0.82);
    border: 1px solid rgba(168, 85, 247, 0.18);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.18s ease;
  }

  .collection-card:hover {
    border-color: rgba(168, 85, 247, 0.38);
  }

  .collection-card.checked {
    border-color: rgba(168, 85, 247, 0.55);
    background: rgba(168, 85, 247, 0.08);
  }

  .col-card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    flex-wrap: wrap;
  }

  .col-title-area {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }

  .col-name-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .col-name-row h4 {
    margin: 0;
    font-size: 1rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .format-badge {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(6, 182, 212, 0.14);
    color: #22d3ee;
    border: 1px solid rgba(6, 182, 212, 0.25);
  }

  .version-chip {
    font-family: "Outfit", monospace;
    font-size: 0.7rem;
    padding: 1px 7px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-muted, #94a3b8);
  }

  .col-sub-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 6px;
    font-size: 0.76rem;
    color: var(--text-muted, #94a3b8);
  }

  .ep-count-pill {
    font-weight: 600;
    color: var(--primary-light, #c084fc);
  }

  .base-url-chip {
    font-family: monospace;
    background: rgba(255, 255, 255, 0.04);
    padding: 1px 8px;
    border-radius: 6px;
    color: var(--text-secondary, #cbd5e1);
  }

  .col-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .btn-workspace {
    background: var(
      --gradient-main,
      linear-gradient(135deg, #a855f7 0%, #6366f1 50%, #06b6d4 100%)
    );
    border: none;
    color: #ffffff;
    padding: 7px 13px;
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(168, 85, 247, 0.25);
  }

  .btn-icon-action {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(168, 85, 247, 0.2);
    color: var(--text-secondary, #cbd5e1);
    padding: 6px 10px;
    border-radius: 8px;
    font-size: 0.76rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-icon-action:hover {
    border-color: rgba(168, 85, 247, 0.45);
    color: #ffffff;
  }

  .btn-icon-action.danger {
    color: #f87171;
    border-color: rgba(239, 68, 68, 0.25);
  }

  .endpoints-preview-bar {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(168, 85, 247, 0.12);
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .ep-preview-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 9px;
    border-radius: 8px;
    background: rgba(9, 7, 17, 0.7);
    border: 1px solid rgba(168, 85, 247, 0.16);
    color: var(--text-secondary, #cbd5e1);
    font-size: 0.75rem;
    cursor: pointer;
    max-width: 260px;
  }

  .ep-preview-pill:hover {
    border-color: rgba(168, 85, 247, 0.45);
  }

  .m-tag {
    font-family: "Outfit", monospace;
    font-size: 0.66rem;
    font-weight: 700;
    padding: 1px 5px;
    border-radius: 4px;
  }

  .m-tag.get {
    background: rgba(6, 182, 212, 0.18);
    color: #22d3ee;
  }
  .m-tag.post {
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
  }
  .m-tag.put,
  .m-tag.patch {
    background: rgba(245, 158, 11, 0.18);
    color: #fbbf24;
  }
  .m-tag.delete {
    background: rgba(239, 68, 68, 0.18);
    color: #f87171;
  }

  .p-text {
    font-family: monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .ep-more-pill {
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.3);
    color: var(--primary-light, #c084fc);
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 0.74rem;
    font-weight: 600;
    cursor: pointer;
  }

  /* Empty / Loading State */
  .state-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 280px;
    text-align: center;
    padding: 28px;
    color: var(--text-muted, #94a3b8);
    gap: 10px;
  }

  .empty-orb {
    width: 60px;
    height: 60px;
    border-radius: 16px;
    background: rgba(168, 85, 247, 0.12);
    border: 1px solid rgba(168, 85, 247, 0.28);
    color: var(--primary-light, #c084fc);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .state-box h4 {
    margin: 6px 0 0;
    color: var(--text, #f8fafc);
    font-size: 1.02rem;
  }

  .state-box p {
    margin: 0;
    font-size: 0.82rem;
    max-width: 420px;
  }

  .btn-primary-inline {
    margin-top: 8px;
    background: var(
      --gradient-main,
      linear-gradient(135deg, #a855f7 0%, #6366f1 50%, #06b6d4 100%)
    );
    border: none;
    color: #ffffff;
    padding: 9px 18px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
  }

  /* =========================================================================
     MODALS (Spectra Obsidian Glass Dialogs)
     ========================================================================= */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(9, 7, 17, 0.8);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    z-index: 2050;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }

  .modal-window {
    background: var(--bg2, #120f1d);
    border: 1px solid rgba(168, 85, 247, 0.25);
    border-radius: 20px;
    width: 100%;
    max-height: 92vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.7);
    overflow: hidden;
  }

  .workspace-modal {
    max-width: 1180px;
  }

  .studio-modal {
    max-width: 880px;
  }

  .sniffer-modal {
    max-width: 760px;
  }

  .modal-header {
    padding: 18px 24px;
    border-bottom: 1px solid rgba(168, 85, 247, 0.15);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    background: rgba(24, 19, 38, 0.65);
  }

  .modal-eyebrow {
    font-family: "Outfit", sans-serif;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--primary-light, #c084fc);
  }

  .modal-title-block h3 {
    margin: 2px 0 0;
    font-family: "Outfit", "Prompt", sans-serif;
    font-size: 1.15rem;
    color: var(--text, #f8fafc);
  }

  .modal-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-primary-sm {
    background: var(
      --gradient-main,
      linear-gradient(135deg, #a855f7 0%, #6366f1 50%, #06b6d4 100%)
    );
    border: none;
    color: #ffffff;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-secondary-sm {
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.32);
    color: var(--primary-light, #c084fc);
    padding: 7px 13px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }

  .modal-close-btn {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(168, 85, 247, 0.2);
    color: var(--text-muted, #94a3b8);
    width: 34px;
    height: 34px;
    border-radius: 8px;
    cursor: pointer;
  }

  .modal-body {
    padding: 20px 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .modal-footer {
    padding: 14px 24px;
    border-top: 1px solid rgba(168, 85, 247, 0.15);
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    background: rgba(18, 15, 29, 0.92);
  }

  /* Workspace Modal Details */
  .ws-settings-grid {
    display: grid;
    grid-template-columns: 1.2fr 1.6fr 110px auto;
    gap: 12px;
    align-items: end;
    background: rgba(24, 19, 38, 0.6);
    padding: 14px;
    border-radius: 12px;
    border: 1px solid rgba(168, 85, 247, 0.16);
  }

  .ws-field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .btn-save-meta {
    background: rgba(168, 85, 247, 0.2);
    border: 1px solid rgba(168, 85, 247, 0.45);
    color: #ffffff;
    padding: 9px 14px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.82rem;
    cursor: pointer;
    white-space: nowrap;
  }

  .ws-filter-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .ws-search {
    flex: 1;
    min-width: 240px;
  }

  .method-pills {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .m-filter-pill {
    background: rgba(24, 19, 38, 0.7);
    border: 1px solid rgba(168, 85, 247, 0.18);
    color: var(--text-muted, #94a3b8);
    padding: 6px 12px;
    border-radius: 8px;
    font-family: "Outfit", sans-serif;
    font-size: 0.76rem;
    font-weight: 700;
    cursor: pointer;
  }

  .m-filter-pill.active {
    background: rgba(168, 85, 247, 0.22);
    color: #ffffff;
    border-color: var(--primary, #a855f7);
  }

  .ws-split-layout {
    display: grid;
    grid-template-columns: 1.25fr 1fr;
    gap: 16px;
    min-height: 380px;
  }

  .ws-endpoints-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 440px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .ws-ep-card {
    background: rgba(24, 19, 38, 0.65);
    border: 1px solid rgba(168, 85, 247, 0.15);
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
  }

  .ws-ep-card.active-test {
    border-color: var(--secondary, #06b6d4);
    background: rgba(6, 182, 212, 0.08);
  }

  .ws-ep-main {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
    flex: 1;
  }

  .ws-ep-info {
    min-width: 0;
    flex: 1;
  }

  .ws-ep-path {
    font-family: monospace;
    font-size: 0.82rem;
    color: var(--text, #f8fafc);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .ws-ep-summary {
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 2px;
  }

  .cat-chip {
    background: rgba(168, 85, 247, 0.15);
    color: var(--primary-light, #c084fc);
    padding: 0 7px;
    border-radius: 999px;
    font-size: 0.68rem;
  }

  .ws-ep-actions {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-shrink: 0;
  }

  .btn-ep-test {
    background: rgba(6, 182, 212, 0.16);
    border: 1px solid rgba(6, 182, 212, 0.38);
    color: #22d3ee;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: 0.74rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-ep-sub {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(168, 85, 247, 0.18);
    color: var(--text-secondary, #cbd5e1);
    padding: 5px 8px;
    border-radius: 6px;
    font-size: 0.73rem;
    cursor: pointer;
  }

  .btn-ep-sub.danger {
    color: #f87171;
    border-color: rgba(239, 68, 68, 0.25);
  }

  .ws-inspector-pane {
    background: var(--bg, #090711);
    border: 1px solid rgba(168, 85, 247, 0.2);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    max-height: 440px;
    overflow-y: auto;
  }

  .inspector-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(168, 85, 247, 0.14);
    margin-bottom: 10px;
  }

  .inspector-head h4 {
    margin: 0;
    font-family: "Outfit", sans-serif;
    font-size: 0.92rem;
  }

  .telemetry-pills {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .status-pill {
    font-family: "Outfit", monospace;
    font-size: 0.74rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
  }

  .status-pill.ok {
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
  }

  .status-pill.err {
    background: rgba(239, 68, 68, 0.16);
    color: #f87171;
  }

  .metric-pill {
    font-family: "Outfit", monospace;
    font-size: 0.72rem;
    padding: 2px 8px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-secondary, #cbd5e1);
  }

  .inspector-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    color: var(--text-muted, #94a3b8);
    font-size: 0.82rem;
    padding: 20px;
  }

  .inspector-error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #fca5a5;
    padding: 12px;
    border-radius: 8px;
    font-size: 0.8rem;
  }

  .tested-url-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(24, 19, 38, 0.8);
    padding: 6px 10px;
    border-radius: 6px;
    margin-bottom: 10px;
    font-size: 0.76rem;
    overflow-x: auto;
  }

  .code-label {
    font-size: 0.73rem;
    font-weight: 600;
    color: var(--text-muted, #94a3b8);
    margin: 8px 0 4px;
  }

  .response-pre {
    margin: 0;
    padding: 10px;
    border-radius: 8px;
    background: rgba(18, 15, 29, 0.95);
    border: 1px solid rgba(168, 85, 247, 0.14);
    color: #e2e8f0;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.76rem;
    overflow-x: auto;
    max-height: 220px;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* Studio Modal Specifics */
  .curl-drawer {
    background: rgba(24, 19, 38, 0.85);
    border: 1px solid rgba(6, 182, 212, 0.32);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .curl-drawer-head {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
    color: var(--text-secondary, #cbd5e1);
    flex-wrap: wrap;
    gap: 6px;
  }

  .curl-drawer-actions {
    display: flex;
    justify-content: flex-end;
  }

  .studio-collection-bar {
    background: rgba(24, 19, 38, 0.55);
    border: 1px solid rgba(168, 85, 247, 0.16);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .save-mode-switch {
    display: flex;
    gap: 8px;
  }

  .switch-pill {
    flex: 1;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid rgba(168, 85, 247, 0.2);
    background: rgba(9, 7, 17, 0.6);
    color: var(--text-muted, #94a3b8);
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }

  .switch-pill.active {
    background: rgba(168, 85, 247, 0.2);
    color: #ffffff;
    border-color: var(--primary, #a855f7);
  }

  .studio-meta-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .form-field.full {
    grid-column: 1 / -1;
  }

  .studio-request-bar {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .method-select {
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(168, 85, 247, 0.3);
    background: var(--bg, #090711);
    color: #ffffff;
    font-family: "Outfit", monospace;
    font-weight: 700;
    font-size: 0.84rem;
  }

  .url-input {
    flex: 1;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(168, 85, 247, 0.25);
    background: var(--bg, #090711);
    color: var(--text, #f8fafc);
    font-size: 0.84rem;
  }

  .btn-test-send {
    background: rgba(6, 182, 212, 0.18);
    border: 1px solid rgba(6, 182, 212, 0.45);
    color: #22d3ee;
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 0.82rem;
    cursor: pointer;
    white-space: nowrap;
  }

  .studio-tabs-header {
    display: flex;
    gap: 6px;
    border-bottom: 1px solid rgba(168, 85, 247, 0.16);
    padding-bottom: 8px;
  }

  .studio-tab {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted, #94a3b8);
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }

  .studio-tab.active {
    background: rgba(168, 85, 247, 0.18);
    border-color: rgba(168, 85, 247, 0.4);
    color: #ffffff;
  }

  .studio-tab-panel {
    background: rgba(9, 7, 17, 0.55);
    border: 1px solid rgba(168, 85, 247, 0.15);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .kv-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.78rem;
    color: var(--text-secondary, #cbd5e1);
  }

  .mode-pills {
    display: flex;
    gap: 6px;
  }

  .mini-pill {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(168, 85, 247, 0.18);
    color: var(--text-muted, #94a3b8);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.74rem;
    font-weight: 600;
    cursor: pointer;
  }

  .mini-pill.active {
    background: rgba(168, 85, 247, 0.22);
    color: #ffffff;
    border-color: rgba(168, 85, 247, 0.45);
  }

  .btn-add-row {
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.3);
    color: var(--primary-light, #c084fc);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
  }

  .kv-rows {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .kv-row {
    display: grid;
    grid-template-columns: 22px 1fr 1.2fr auto;
    gap: 8px;
    align-items: center;
  }

  .btn-del-row {
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.25);
    color: #f87171;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 0.74rem;
    cursor: pointer;
  }

  .auth-grid,
  .sniffer-form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .studio-response-box {
    background: var(--bg, #090711);
    border: 1px solid rgba(6, 182, 212, 0.3);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .studio-res-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.8rem;
  }

  /* Sniffer Modal List */
  .sniffer-results-box {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .sniffer-list-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .sniffer-list {
    max-height: 240px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: var(--bg, #090711);
    padding: 10px;
    border-radius: 10px;
    border: 1px solid rgba(168, 85, 247, 0.16);
  }

  .sniffer-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(24, 19, 38, 0.65);
    border: 1px solid rgba(168, 85, 247, 0.12);
    cursor: pointer;
  }

  .sniffer-item.selected {
    border-color: rgba(168, 85, 247, 0.45);
    background: rgba(168, 85, 247, 0.12);
  }

  .sniffer-path {
    font-family: monospace;
    font-size: 0.8rem;
    color: var(--text, #f8fafc);
    flex: 1;
  }

  .sniffer-summary {
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
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
    background: rgba(6, 182, 212, 0.16);
    color: #22d3ee;
  }
  .method-badge.post {
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
  }
  .method-badge.put,
  .method-badge.patch {
    background: rgba(245, 158, 11, 0.16);
    color: #fbbf24;
  }
  .method-badge.delete {
    background: rgba(239, 68, 68, 0.16);
    color: #f87171;
  }

  .btn-cancel {
    background: rgba(255, 255, 255, 0.05);
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
    box-shadow: 0 6px 20px rgba(168, 85, 247, 0.28);
  }

  .btn-primary-spectra:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .spinner {
    width: 15px;
    height: 15px;
    border: 2px solid rgba(255, 255, 255, 0.25);
    border-top-color: #ffffff;
    border-radius: 50%;
    display: inline-block;
    animation: spin 0.8s linear infinite;
  }

  .spinner.large {
    width: 28px;
    height: 28px;
    border-width: 3px;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 1024px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
    .ws-settings-grid {
      grid-template-columns: 1fr 1fr;
    }
    .ws-split-layout {
      grid-template-columns: 1fr;
    }
    .studio-meta-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 640px) {
    .page-header {
      padding: 16px;
    }
    .ws-settings-grid,
    .auth-grid,
    .sniffer-form-grid {
      grid-template-columns: 1fr;
    }
    .studio-request-bar {
      flex-direction: column;
      align-items: stretch;
    }
  }
</style>
