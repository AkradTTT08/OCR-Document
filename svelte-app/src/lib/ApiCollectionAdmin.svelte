<script>
  import { onMount } from "svelte";
  import { showToast, customConfirm } from "./toastStore.js";
  import CustomSelect from "./CustomSelect.svelte";
  import ExtensionSyncModal from "./ExtensionSyncModal.svelte";

  const API_BASE = "";
  const STORAGE_PROJECT_KEY = "spectra_api_selected_project";
  const HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];

  const METHOD_META = {
    GET: { short: "GET", color: "#34d399" },
    POST: { short: "POST", color: "#fbbf24" },
    PUT: { short: "PUT", color: "#38bdf8" },
    PATCH: { short: "PATCH", color: "#c084fc" },
    DELETE: { short: "DEL", color: "#fb7185" },
    HEAD: { short: "HEAD", color: "#94a3b8" },
    OPTIONS: { short: "OPT", color: "#94a3b8" },
  };

  function formatVerb(method) {
    const m = (method || "GET").toUpperCase();
    return METHOD_META[m]?.short || m.slice(0, 5);
  }

  function verbColor(method) {
    const m = (method || "GET").toUpperCase();
    return METHOD_META[m]?.color || "#94a3b8";
  }

  const METHOD_SELECT_OPTIONS = HTTP_METHODS.map((m) => ({
    value: m,
    label: m,
    color: METHOD_META[m].color,
    dotColor: METHOD_META[m].color,
  }));

  const SIDEBAR_METHOD_OPTIONS = [
    { value: "ALL", label: "All Methods", dotColor: "#94a3b8" },
    ...METHOD_SELECT_OPTIONS,
  ];

  const AUTH_TYPE_OPTIONS = [
    { value: "none", label: "No Auth", description: "ไม่ส่ง Header ยืนยันตัวตนเพิ่มเติม" },
    { value: "bearer", label: "Bearer Token", description: "แนบ Authorization: Bearer <token> (JWT / OAuth2)" },
    { value: "apikey", label: "API Key", description: "ส่ง Key-Value ผ่าน HTTP Header หรือ Query Param" },
    { value: "basic", label: "Basic Auth", description: "เข้ารหัส Base64 Username:Password อัตโนมัติ" },
  ];

  const API_KEY_IN_OPTIONS = [
    { value: "header", label: "HTTP Header" },
    { value: "query", label: "Query Params" },
  ];

  export let projectsList = [];
  export let selectedProject = "";

  // Core data state
  let isLoadingProjects = false;
  let projectsError = "";
  let collections = [];
  let isLoadingCollections = false;
  let expandedCollectionIds = new Set();
  let collapsedFolderKeys = new Set();

  // Environment / Base URL Switcher state (per project)
  let selectedEnvUrl = "";

  // Sidebar state
  let sidebarTab = "collections"; // 'collections' | 'history'
  let sidebarSearch = "";
  let sidebarMethodFilter = "ALL";
  let requestHistory = [];

  // Multi-tab Postman workbench state (preserved per project!)
  let tabsByProject = {};
  let tabs = [];
  let activeTabId = "";
  let activeAbortControllers = {}; // tabId -> AbortController

  // Secret visibility toggles
  let showBearerSecret = false;
  let showApiKeySecret = false;
  let showBasicPass = false;

  // Split pane height (Request vs Response)
  let responsePaneHeight = 290;
  let isResizingSplit = false;
  let workbenchRightEl;

  // Modals (scoped strictly to secondary workflows)
  let showImportModal = false;
  let importModalTab = "file"; // 'file' | 'curl'
  let importCurlTarget = "active"; // 'active' | 'new'
  let uploadFile = null;
  let fileInput;
  let customImportName = "";
  let isUploading = false;
  let isDragOver = false;
  let importCurlText = "";

  let showCollectionModal = false;
  let collectionModalMode = "create"; // 'create' | 'edit'
  let colModalId = "";
  let colModalName = "";
  let colModalBaseUrl = "";
  let colModalVersion = "1.0";
  let isSavingCollection = false;

  let showSaveModal = false;
  let saveModalMode = "existing"; // 'existing' | 'new'
  let saveModalTargetColId = "";
  let saveModalNewColName = "";
  let saveModalRequestName = "";
  let saveModalCategory = "General";

  let showSnifferModal = false;
  let isSniffing = false;
  let snifferUrl = "";
  let snifferShowAuth = false;
  let snifferUsername = "";
  let snifferPassword = "";
  let sniffedEndpoints = [];
  let selectedSniffedIndices = new Set();
  let snifferImportMode = "new";
  let snifferCollectionName = "";
  let snifferTargetCollectionId = "";

  let showExtensionModal = false;

  // Helpers
  function getAuthHeaders(extra = {}) {
    const token =
      typeof localStorage !== "undefined"
        ? localStorage.getItem("jwt_token")
        : null;
    const headers = { ...extra };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }

  function uid(prefix = "tab") {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
  }

  function ensureTrailingBlankRow(rows) {
    const list = Array.isArray(rows) ? rows : [];
    if (list.length === 0) return [{ key: "", value: "", enabled: true }];
    const last = list[list.length - 1];
    if ((last.key || "").trim() || (last.value || "").trim()) {
      return [...list, { key: "", value: "", enabled: true }];
    }
    return list;
  }

  function createBlankTab(overrides = {}) {
    return {
      id: uid("req"),
      collectionId: overrides.collectionId || "",
      endpointIndex:
        typeof overrides.endpointIndex === "number"
          ? overrides.endpointIndex
          : -1,
      name: overrides.name || "Untitled Request",
      category: overrides.category || "General",
      description: overrides.description || "",
      method: (overrides.method || "GET").toUpperCase(),
      url: overrides.url || "",
      baseUrl: overrides.baseUrl || "",
      queryParams: ensureTrailingBlankRow(overrides.queryParams || []),
      auth: {
        type: overrides.auth?.type || "none",
        token: overrides.auth?.token || "",
        key: overrides.auth?.key || "X-API-Key",
        value: overrides.auth?.value || "",
        in: overrides.auth?.in || "header",
        username: overrides.auth?.username || "",
        password: overrides.auth?.password || "",
      },
      headerMode: "table",
      headers: ensureTrailingBlankRow(
        overrides.headers || [
          { key: "Accept", value: "application/json", enabled: true },
        ],
      ),
      headersJson: overrides.headersJson || '{\n  "Accept": "application/json"\n}',
      bodyMode: overrides.bodyMode || "none", // 'none' | 'json' | 'urlencoded' | 'raw'
      bodyText: overrides.bodyText || "",
      formRows: ensureTrailingBlankRow(overrides.formRows || []),
      activeReqTab: overrides.activeReqTab || "params", // 'params' | 'auth' | 'headers' | 'body' | 'info'
      activeResTab: "body", // 'body' | 'headers' | 'curl'
      responseViewMode: "pretty", // 'pretty' | 'raw'
      isSending: false,
      isSaving: false,
      isDirty: overrides.isDirty ?? false,
      response: overrides.response || null,
    };
  }

  function endpointToTab(col, ep, index) {
    const rawHeaders =
      ep.headers && typeof ep.headers === "object" && !Array.isArray(ep.headers)
        ? ep.headers
        : {};
    const headerRows = Object.entries(rawHeaders).map(([key, value]) => ({
      key,
      value: String(value ?? ""),
      enabled: true,
    }));

    const qpRows = Array.isArray(ep.query_params)
      ? ep.query_params.map((q) => ({
          key: q.key || "",
          value: q.value ?? "",
          enabled: q.enabled !== false,
        }))
      : [];

    const rawUrl = ep.url || ep.path || "";
    if (qpRows.length === 0 && rawUrl.includes("?")) {
      try {
        const fakeBase = /^https?:\/\//i.test(rawUrl)
          ? rawUrl
          : `http://placeholder.local${rawUrl.startsWith("/") ? "" : "/"}${rawUrl}`;
        const parsed = new URL(fakeBase);
        parsed.searchParams.forEach((v, k) => {
          qpRows.push({ key: k, value: v, enabled: true });
        });
      } catch (_) {}
    }

    const bodyStr =
      typeof ep.body === "string"
        ? ep.body
        : ep.body
          ? JSON.stringify(ep.body, null, 2)
          : "";
    let bodyMode = "none";
    if (bodyStr.trim()) {
      try {
        JSON.parse(bodyStr);
        bodyMode = "json";
      } catch (_) {
        bodyMode = "raw";
      }
    }

    const auth = ep.auth_config && typeof ep.auth_config === "object" ? ep.auth_config : {};
    const effectiveBase = col.base_url || selectedEnvUrl || "";
    const fullDisplayUrl =
      rawUrl && !/^https?:\/\//i.test(rawUrl) && effectiveBase
        ? `${effectiveBase.replace(/\/+$/, "")}/${rawUrl.replace(/^\/+/, "")}`
        : rawUrl;

    return createBlankTab({
      collectionId: col.id,
      endpointIndex: index,
      name: ep.name || ep.summary || `${(ep.method || "GET").toUpperCase()} ${ep.path || ""}`,
      category: ep.category || ep.folder || "General",
      description: ep.description || "",
      method: (ep.method || "GET").toUpperCase(),
      url: fullDisplayUrl,
      baseUrl: col.base_url || "",
      queryParams: qpRows,
      auth,
      headers: headerRows.length > 0 ? headerRows : [{ key: "Accept", value: "application/json", enabled: true }],
      headersJson: JSON.stringify(rawHeaders, null, 2),
      bodyMode,
      bodyText: bodyStr,
      activeReqTab: bodyStr.trim() ? "body" : "params",
      isDirty: false,
    });
  }

  // Reactive derived data
  $: projectOptions = (projectsList || []).map((p) => ({
    value:
      typeof p === "string"
        ? p
        : String(p.id || p.project_id || p.project_name || p.name),
    label: typeof p === "string" ? p : p.name || p.project_name || String(p.id),
    badge:
      typeof p === "object" && p !== null && p.project_code
        ? p.project_code
        : "",
  }));

  $: selectedProjectObj = (projectsList || []).find(
    (p) =>
      typeof p === "object" &&
      p !== null &&
      String(p.id || p.project_id || p.name) === String(selectedProject),
  );

  // Environment / Base URL options built from project's site_urls & default_base_url
  $: envOptions = (() => {
    const opts = [];
    const seen = new Set();
    const sites = Array.isArray(selectedProjectObj?.site_urls)
      ? selectedProjectObj.site_urls
      : [];
    for (const s of sites) {
      const u = (s?.url || "").trim().replace(/\/+$/, "");
      if (!u || seen.has(u)) continue;
      seen.add(u);
      const envName = (s.env_type || s.label || "ENV").toUpperCase();
      const dot =
        envName.includes("PROD")
          ? "#fb7185"
          : envName.includes("STAG") || envName.includes("UAT")
            ? "#fbbf24"
            : "#34d399";
      opts.push({
        value: u,
        label: u.replace(/^https?:\/\//i, ""),
        badge: envName,
        dotColor: dot,
        description: u,
      });
    }
    const defUrl = (selectedProjectObj?.default_base_url || "").trim().replace(/\/+$/, "");
    if (defUrl && !seen.has(defUrl)) {
      seen.add(defUrl);
      opts.push({
        value: defUrl,
        label: defUrl.replace(/^https?:\/\//i, ""),
        badge: "DEFAULT",
        dotColor: "#38bdf8",
        description: defUrl,
      });
    }
    opts.push({
      value: "",
      label: "No Environment",
      dotColor: "#64748b",
      description: "ใช้ URL เต็มหรือ Base URL ของแต่ละ Collection",
    });
    return opts;
  })();

  $: collectionSelectOptions = collections.map((col) => ({
    value: col.id,
    label: col.name,
    badge: `${col.endpoints.length}`,
    description: col.base_url || "",
  }));

  $: totalEndpointsCount = collections.reduce(
    (acc, c) =>
      acc +
      (Array.isArray(c.endpoints)
        ? c.endpoints.length
        : c.endpoint_count || c.endpoints_count || 0),
    0,
  );

  $: activeTab = tabs.find((t) => t.id === activeTabId) || tabs[0] || null;

  $: activeTabCollection = activeTab?.collectionId
    ? collections.find((c) => c.id === activeTab.collectionId) || null
    : null;

  // Group filtered endpoints into nested Category folders per Collection
  $: filteredSidebarCollections = collections
    .map((col) => {
      const q = sidebarSearch.trim().toLowerCase();
      const eps = (Array.isArray(col.endpoints) ? col.endpoints : []).map(
        (ep, idx) => ({ ...ep, _idx: idx }),
      );
      const colNameMatch =
        !q ||
        (col.name || "").toLowerCase().includes(q) ||
        (col.base_url || "").toLowerCase().includes(q);
      const matchedEps = eps.filter((ep) => {
        const mOk =
          sidebarMethodFilter === "ALL" ||
          (ep.method || "GET").toUpperCase() === sidebarMethodFilter;
        if (!mOk) return false;
        if (!q || colNameMatch) return true;
        return (
          (ep.name || "").toLowerCase().includes(q) ||
          (ep.summary || "").toLowerCase().includes(q) ||
          (ep.path || "").toLowerCase().includes(q) ||
          (ep.url || "").toLowerCase().includes(q) ||
          (ep.category || "").toLowerCase().includes(q)
        );
      });

      const folderMap = new Map();
      for (const ep of matchedEps) {
        const cat = (ep.category || ep.folder || "General").trim() || "General";
        if (!folderMap.has(cat)) folderMap.set(cat, []);
        folderMap.get(cat).push(ep);
      }
      const folders = Array.from(folderMap.entries()).map(([category, items]) => ({
        key: `${col.id}::${category}`,
        category,
        items,
      }));

      return {
        ...col,
        _filteredEndpoints: matchedEps,
        _folders: folders,
        _totalEndpoints: eps.length,
      };
    })
    .filter((col) => {
      const q = sidebarSearch.trim().toLowerCase();
      if (sidebarMethodFilter !== "ALL") return col._filteredEndpoints.length > 0;
      if (!q) return true;
      return (
        (col.name || "").toLowerCase().includes(q) ||
        col._filteredEndpoints.length > 0
      );
    });

  $: activeParamsCount = activeTab
    ? activeTab.queryParams.filter((r) => r.enabled !== false && r.key.trim()).length
    : 0;

  $: activeHeadersCount = activeTab
    ? activeTab.headerMode === "json"
      ? (() => {
          try {
            return Object.keys(JSON.parse(activeTab.headersJson || "{}")).length;
          } catch (_) {
            return 0;
          }
        })()
      : activeTab.headers.filter((r) => r.enabled !== false && r.key.trim()).length
    : 0;

  $: activeJsonValidation = (() => {
    if (!activeTab || activeTab.bodyMode !== "json" || !activeTab.bodyText.trim()) {
      return { valid: true, message: "" };
    }
    try {
      JSON.parse(activeTab.bodyText);
      return { valid: true, message: "JSON ถูกต้อง" };
    } catch (e) {
      return { valid: false, message: e.message };
    }
  })();

  $: formattedResponseBody = (() => {
    const raw = activeTab?.response?.response_body ?? activeTab?.response?.preview ?? "";
    if (!raw) return "(Empty Response Body)";
    if (activeTab?.responseViewMode === "raw") {
      return raw;
    }
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch (_) {
      return raw;
    }
  })();

  // Lifecycle
  onMount(async () => {
    const initialTab = createBlankTab();
    tabs = [initialTab];
    activeTabId = initialTab.id;
    await loadProjects();
  });

  function syncDefaultEnvForProject(projObj) {
    if (!projObj) {
      selectedEnvUrl = "";
      return;
    }
    const sites = Array.isArray(projObj.site_urls) ? projObj.site_urls : [];
    const defSite = sites.find((s) => s?.is_default && s?.url) || sites[0];
    selectedEnvUrl = (defSite?.url || projObj.default_base_url || "").trim().replace(/\/+$/, "");
  }

  async function loadProjects() {
    isLoadingProjects = true;
    projectsError = "";
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      const list = Array.isArray(data.projects)
        ? data.projects
        : Array.isArray(data)
          ? data
          : [];
      projectsList = list;

      if (list.length > 0) {
        const savedPid =
          typeof localStorage !== "undefined"
            ? localStorage.getItem(STORAGE_PROJECT_KEY)
            : "";
        const validIds = list.map((p) =>
          typeof p === "string"
            ? p
            : String(p.id || p.project_id || p.project_name || p.name),
        );
        const targetPid =
          selectedProject && validIds.includes(String(selectedProject))
            ? String(selectedProject)
            : savedPid && validIds.includes(savedPid)
              ? savedPid
              : validIds[0];

        selectedProject = targetPid;
        const matchedProj = list.find(
          (p) =>
            typeof p === "object" &&
            p !== null &&
            String(p.id || p.project_id || p.name) === targetPid,
        );
        syncDefaultEnvForProject(matchedProj);
        await loadCollections(targetPid);
      } else {
        collections = [];
      }
    } catch (e) {
      projectsError = e.message || "ไม่สามารถโหลดรายการโครงการได้";
      showToast(`โหลดรายการโครงการไม่สำเร็จ: ${projectsError}`, "error");
    } finally {
      isLoadingProjects = false;
    }
  }

  function handleProjectChange(e) {
    const prevPid = selectedProject;
    const nextPid = String(e.detail ?? selectedProject ?? "");

    // Preserve open tabs for previous project so switching never loses unsaved work!
    if (prevPid && tabs.length > 0) {
      tabsByProject = {
        ...tabsByProject,
        [prevPid]: { tabs, activeTabId },
      };
    }

    selectedProject = nextPid;
    if (typeof localStorage !== "undefined" && nextPid) {
      localStorage.setItem(STORAGE_PROJECT_KEY, nextPid);
    }

    const nextProjObj = (projectsList || []).find(
      (p) =>
        typeof p === "object" &&
        p !== null &&
        String(p.id || p.project_id || p.name) === nextPid,
    );
    syncDefaultEnvForProject(nextProjObj);

    if (nextPid && tabsByProject[nextPid]?.tabs?.length > 0) {
      tabs = tabsByProject[nextPid].tabs;
      activeTabId = tabsByProject[nextPid].activeTabId || tabs[0].id;
    } else {
      const fresh = createBlankTab({
        baseUrl: selectedEnvUrl,
      });
      tabs = [fresh];
      activeTabId = fresh.id;
    }

    expandedCollectionIds = new Set();
    collapsedFolderKeys = new Set();
    if (nextPid) {
      loadCollections(nextPid);
    } else {
      collections = [];
    }
  }

  async function loadCollections(pid = selectedProject) {
    if (!pid) return;
    isLoadingCollections = true;
    try {
      const res = await fetch(
        `${API_BASE}/api/projects/${encodeURIComponent(pid)}/api-collections`,
        { headers: getAuthHeaders() },
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const rawList = Array.isArray(data) ? data : data.collections || [];
      collections = rawList.map((c) => ({
        ...c,
        format_type: c.format_type || c.format || "Manual Collection",
        endpoints: Array.isArray(c.endpoints) ? c.endpoints : [],
        endpoint_count: Array.isArray(c.endpoints)
          ? c.endpoints.length
          : (c.endpoint_count ?? c.endpoints_count ?? 0),
        created_at:
          c.updated_at || c.created_at || c.uploaded_at || new Date().toISOString(),
      }));

      if (expandedCollectionIds.size === 0 && collections.length > 0) {
        expandedCollectionIds = new Set([collections[0].id]);
      }
    } catch (_) {
      showToast("ไม่สามารถโหลดรายการ API Collections ของโครงการนี้ได้", "error");
    } finally {
      isLoadingCollections = false;
    }
  }

  // Tab mutations
  function patchActiveTab(updater) {
    if (!activeTab) return;
    tabs = tabs.map((t) => {
      if (t.id !== activeTab.id) return t;
      return typeof updater === "function" ? updater(t) : { ...t, ...updater };
    });
  }

  function openNewRequestTab(preselectedCollection = null, defaultCategory = "General") {
    const tab = createBlankTab({
      collectionId: preselectedCollection?.id || "",
      category: defaultCategory || "General",
      baseUrl: preselectedCollection?.base_url || selectedEnvUrl || "",
      isDirty: false,
    });
    tabs = [...tabs, tab];
    activeTabId = tab.id;
  }

  function openEndpointInTab(col, ep, index) {
    const existing = tabs.find(
      (t) => t.collectionId === col.id && t.endpointIndex === index,
    );
    if (existing) {
      activeTabId = existing.id;
      return;
    }
    const newTab = endpointToTab(col, ep, index);
    if (
      tabs.length === 1 &&
      !tabs[0].collectionId &&
      !tabs[0].url.trim() &&
      !tabs[0].isDirty
    ) {
      tabs = [newTab];
    } else {
      tabs = [...tabs, newTab];
    }
    activeTabId = newTab.id;
  }

  async function closeTab(tabId, e) {
    if (e) e.stopPropagation();
    const target = tabs.find((t) => t.id === tabId);
    if (!target) return;

    if (target.isDirty) {
      const ok = await customConfirm(
        `แท็บ "${target.name || "Untitled Request"}" มีการแก้ไขที่ยังไม่บันทึก ยืนยันการปิดแท็บ?`,
      );
      if (!ok) return;
    }

    if (activeAbortControllers[tabId]) {
      activeAbortControllers[tabId].abort();
      delete activeAbortControllers[tabId];
    }

    const idx = tabs.findIndex((t) => t.id === tabId);
    const remaining = tabs.filter((t) => t.id !== tabId);
    if (remaining.length === 0) {
      const fresh = createBlankTab({ baseUrl: selectedEnvUrl });
      tabs = [fresh];
      activeTabId = fresh.id;
      return;
    }
    tabs = remaining;
    if (activeTabId === tabId) {
      const nextIdx = Math.min(idx, remaining.length - 1);
      activeTabId = remaining[nextIdx].id;
    }
  }

  function handleTabKeydown(e, idx) {
    if (e.key === "ArrowRight") {
      e.preventDefault();
      activeTabId = tabs[(idx + 1) % tabs.length].id;
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      activeTabId = tabs[(idx - 1 + tabs.length) % tabs.length].id;
    } else if (e.key === "Home") {
      e.preventDefault();
      activeTabId = tabs[0].id;
    } else if (e.key === "End") {
      e.preventDefault();
      activeTabId = tabs[tabs.length - 1].id;
    }
  }

  function toggleCollectionExpand(colId) {
    const next = new Set(expandedCollectionIds);
    if (next.has(colId)) next.delete(colId);
    else next.add(colId);
    expandedCollectionIds = next;
  }

  function toggleFolderExpand(folderKey) {
    const next = new Set(collapsedFolderKeys);
    if (next.has(folderKey)) next.delete(folderKey);
    else next.add(folderKey);
    collapsedFolderKeys = next;
  }

  // Bidirectional URL <-> Query Params sync
  function syncParamsFromUrl(urlStr) {
    if (!urlStr || !urlStr.includes("?")) return null;
    try {
      const fake = /^https?:\/\//i.test(urlStr)
        ? urlStr
        : `http://placeholder.local${urlStr.startsWith("/") ? "" : "/"}${urlStr}`;
      const u = new URL(fake);
      const parsedRows = [];
      u.searchParams.forEach((value, key) => {
        parsedRows.push({ key, value, enabled: true });
      });
      return ensureTrailingBlankRow(parsedRows);
    } catch (_) {
      return null;
    }
  }

  function rebuildUrlWithParams(rawUrl, params) {
    const basePart = (rawUrl || "").split("?")[0];
    const active = (params || []).filter((p) => p.enabled !== false && p.key.trim());
    if (active.length === 0) return basePart;
    const qs = active
      .map((p) => `${encodeURIComponent(p.key.trim())}=${encodeURIComponent(p.value ?? "")}`)
      .join("&");
    return `${basePart}?${qs}`;
  }

  function handleUrlInput(val) {
    patchActiveTab((t) => {
      const updated = { ...t, url: val, isDirty: true };
      const synced = syncParamsFromUrl(val);
      if (synced) updated.queryParams = synced;
      return updated;
    });
  }

  function handleUrlPaste(e) {
    const pasted = e.clipboardData?.getData("text") || "";
    if (/^\s*curl\s+/i.test(pasted)) {
      e.preventDefault();
      applyCurlToActiveTab(pasted);
    }
  }

  function updateQueryParam(idx, field, val) {
    patchActiveTab((t) => {
      const next = t.queryParams.map((row, i) =>
        i === idx ? { ...row, [field]: val } : row,
      );
      const padded = ensureTrailingBlankRow(next);
      return {
        ...t,
        queryParams: padded,
        url: t.url.trim() ? rebuildUrlWithParams(t.url, padded) : t.url,
        isDirty: true,
      };
    });
  }

  function removeQueryParam(idx) {
    patchActiveTab((t) => {
      const next = ensureTrailingBlankRow(t.queryParams.filter((_, i) => i !== idx));
      return {
        ...t,
        queryParams: next,
        url: t.url.trim() ? rebuildUrlWithParams(t.url, next) : t.url,
        isDirty: true,
      };
    });
  }

  function updateHeaderRow(idx, field, val) {
    patchActiveTab((t) => ({
      ...t,
      headers: ensureTrailingBlankRow(
        t.headers.map((row, i) => (i === idx ? { ...row, [field]: val } : row)),
      ),
      isDirty: true,
    }));
  }

  function removeHeaderRow(idx) {
    patchActiveTab((t) => ({
      ...t,
      headers: ensureTrailingBlankRow(t.headers.filter((_, i) => i !== idx)),
      isDirty: true,
    }));
  }

  function updateFormRow(idx, field, val) {
    patchActiveTab((t) => ({
      ...t,
      formRows: ensureTrailingBlankRow(
        t.formRows.map((row, i) => (i === idx ? { ...row, [field]: val } : row)),
      ),
      isDirty: true,
    }));
  }

  function removeFormRow(idx) {
    patchActiveTab((t) => ({
      ...t,
      formRows: ensureTrailingBlankRow(t.formRows.filter((_, i) => i !== idx)),
      isDirty: true,
    }));
  }

  function switchHeaderMode(mode) {
    if (!activeTab || activeTab.headerMode === mode) return;
    if (mode === "json") {
      const obj = collectHeadersObject(activeTab) || {};
      patchActiveTab({ headerMode: "json", headersJson: JSON.stringify(obj, null, 2) });
    } else {
      try {
        const parsed = JSON.parse(activeTab.headersJson || "{}");
        const rows = Object.entries(parsed).map(([key, value]) => ({
          key,
          value: String(value ?? ""),
          enabled: true,
        }));
        patchActiveTab({ headerMode: "table", headers: ensureTrailingBlankRow(rows) });
      } catch (_) {
        showToast("รูปแบบ JSON ของ Headers ไม่ถูกต้อง กรุณาแก้ไขก่อนสลับเป็นตาราง", "warning");
      }
    }
  }

  function collectHeadersObject(tab) {
    if (!tab) return {};
    if (tab.headerMode === "json") {
      try {
        const parsed = JSON.parse(tab.headersJson || "{}");
        return typeof parsed === "object" && parsed !== null ? parsed : {};
      } catch (_) {
        return null;
      }
    }
    const obj = {};
    for (const row of tab.headers) {
      if (row.enabled !== false && row.key && row.key.trim()) {
        obj[row.key.trim()] = row.value ?? "";
      }
    }
    if (tab.bodyMode === "json" && !Object.keys(obj).some((k) => k.toLowerCase() === "content-type")) {
      obj["Content-Type"] = "application/json";
    }
    if (
      tab.bodyMode === "urlencoded" &&
      !Object.keys(obj).some((k) => k.toLowerCase() === "content-type")
    ) {
      obj["Content-Type"] = "application/x-www-form-urlencoded";
    }
    return obj;
  }

  function collectBodyString(tab) {
    if (!tab || tab.bodyMode === "none") return "";
    if (tab.bodyMode === "urlencoded") {
      const pairs = tab.formRows
        .filter((r) => r.enabled !== false && r.key.trim())
        .map((r) => `${encodeURIComponent(r.key.trim())}=${encodeURIComponent(r.value ?? "")}`);
      return pairs.join("&");
    }
    return tab.bodyText || "";
  }

  function collectAuthObject(tab) {
    const a = tab?.auth || { type: "none" };
    if (a.type === "bearer") return { type: "bearer", token: (a.token || "").trim() };
    if (a.type === "apikey") {
      return {
        type: "apikey",
        key: (a.key || "X-API-Key").trim(),
        value: (a.value || "").trim(),
        in: a.in || "header",
      };
    }
    if (a.type === "basic") {
      return { type: "basic", username: a.username || "", password: a.password || "" };
    }
    return { type: "none" };
  }

  function resolveEffectiveBaseUrl(tab) {
    return (tab?.baseUrl || "").trim() || (selectedEnvUrl || "").trim();
  }

  function buildCurlFromTab(tab) {
    if (!tab) return "";
    const method = (tab.method || "GET").toUpperCase();
    let fullUrl = (tab.url || "").trim();
    const effBase = resolveEffectiveBaseUrl(tab);
    if (fullUrl && !/^https?:\/\//i.test(fullUrl) && effBase) {
      fullUrl = `${effBase.replace(/\/+$/, "")}/${fullUrl.replace(/^\/+/, "")}`;
    }
    const headers = collectHeadersObject(tab) || {};
    const auth = collectAuthObject(tab);
    if (auth.type === "bearer" && auth.token) {
      headers["Authorization"] = auth.token.toLowerCase().startsWith("bearer ")
        ? auth.token
        : `Bearer ${auth.token}`;
    } else if (auth.type === "apikey" && auth.in === "header" && auth.key) {
      headers[auth.key] = auth.value;
    }

    const parts = [`curl -X ${method} "${fullUrl || "https://api.example.com"}"`];
    for (const [k, v] of Object.entries(headers)) {
      parts.push(`  -H "${k}: ${String(v).replace(/"/g, '\\"')}"`);
    }
    if (auth.type === "basic" && (auth.username || auth.password)) {
      parts.push(`  -u "${auth.username}:${auth.password}"`);
    }
    const body = collectBodyString(tab);
    if (body && ["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      parts.push(`  -d '${body.replace(/'/g, "'\\''")}'`);
    }
    return parts.join(" \\\n");
  }

  function parseCurlString(rawCurl) {
    const cmd = rawCurl
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

    let url = urlMatch ? urlMatch[1] : "";
    let baseUrl = "";
    let suggestedName = "";
    let queryParams = [];

    if (url) {
      try {
        const u = new URL(url);
        baseUrl = `${u.protocol}//${u.host}`;
        suggestedName = `${detectedMethod || "GET"} ${u.pathname}`;
        u.searchParams.forEach((v, k) => {
          queryParams.push({ key: k, value: v, enabled: true });
        });
      } catch (_) {}
    }

    const headers = {};
    const auth = {
      type: "none",
      token: "",
      key: "X-API-Key",
      value: "",
      in: "header",
      username: "",
      password: "",
    };
    const headerRegex = /(?:-H|--header)\s+(['"])(.*?)\1/gi;
    let m;
    while ((m = headerRegex.exec(cmd)) !== null) {
      const parts = m[2].split(":");
      if (parts.length >= 2) {
        const key = parts.shift().trim();
        const val = parts.join(":").trim();
        if (key.toLowerCase() === "authorization" && /^bearer\s+/i.test(val)) {
          auth.type = "bearer";
          auth.token = val.replace(/^bearer\s+/i, "").trim();
        } else {
          headers[key] = val;
        }
      }
    }

    const userMatch = cmd.match(/(?:-u|--user)\s+(['"]?)([^'"\s]+)\1/i);
    if (userMatch) {
      const [usr, pwd = ""] = userMatch[2].split(":");
      auth.type = "basic";
      auth.username = usr;
      auth.password = pwd;
    }

    const cookieMatch = cmd.match(/(?:-b|--cookie)\s+(['"])(.*?)\1/i);
    if (cookieMatch) {
      headers["Cookie"] = cookieMatch[2];
    }

    let bodyMode = "none";
    let bodyText = "";
    const dataMatch = cmd.match(
      /(?:-d|--data|--data-raw|--data-binary)\s+(['"])([\s\S]*?)\1/i,
    );
    if (dataMatch) {
      let rawData = dataMatch[2];
      try {
        rawData = JSON.stringify(JSON.parse(rawData), null, 2);
        bodyMode = "json";
      } catch (_) {
        bodyMode = "raw";
      }
      bodyText = rawData;
      if (!detectedMethod) detectedMethod = "POST";
    }

    const finalMethod = detectedMethod || "GET";
    if (suggestedName && !methodMatch && finalMethod !== "GET") {
      suggestedName = suggestedName.replace(/^GET\s+/, `${finalMethod} `);
    }

    const headerRows = Object.entries(headers).map(([key, value]) => ({
      key,
      value: String(value),
      enabled: true,
    }));

    return {
      method: finalMethod,
      url,
      baseUrl,
      name: suggestedName || "Imported cURL Request",
      queryParams: ensureTrailingBlankRow(queryParams),
      headers: ensureTrailingBlankRow(headerRows),
      headersJson: JSON.stringify(headers, null, 2),
      auth,
      bodyMode,
      bodyText,
    };
  }

  function applyCurlToActiveTab(rawCurl) {
    if (!rawCurl.trim()) {
      showToast("กรุณาวางคำสั่ง cURL ก่อนนำเข้า", "warning");
      return;
    }
    try {
      const parsed = parseCurlString(rawCurl);
      patchActiveTab((t) => ({
        ...t,
        method: parsed.method,
        url: parsed.url || t.url,
        baseUrl: parsed.baseUrl || t.baseUrl,
        name: !t.name || t.name === "Untitled Request" ? parsed.name : t.name,
        queryParams: parsed.queryParams,
        headers: parsed.headers,
        headersJson: parsed.headersJson,
        auth: parsed.auth,
        bodyMode: parsed.bodyMode,
        bodyText: parsed.bodyText,
        activeReqTab: parsed.bodyText ? "body" : "params",
        isDirty: true,
      }));
      showToast("แยกข้อมูล Method, URL, Headers, Auth และ Body จาก cURL แล้ว", "success");
    } catch (_) {
      showToast("ไม่สามารถแยกคำสั่ง cURL ได้ กรุณาตรวจสอบรูปแบบ", "error");
    }
  }

  function beautifyActiveBody() {
    if (!activeTab || !activeTab.bodyText.trim()) return;
    try {
      const formatted = JSON.stringify(JSON.parse(activeTab.bodyText), null, 2);
      patchActiveTab({ bodyText: formatted, bodyMode: "json", isDirty: true });
      showToast("จัดรูปแบบ JSON เรียบร้อยแล้ว", "success");
    } catch (e) {
      showToast(`JSON ไม่ถูกต้อง: ${e.message}`, "error");
    }
  }

  async function copyText(str, label = "ข้อความ") {
    try {
      await navigator.clipboard.writeText(str);
      showToast(`คัดลอก${label}ไปยังคลิปบอร์ดแล้ว`, "info");
    } catch (_) {
      showToast(`ไม่สามารถคัดลอก${label}ได้`, "error");
    }
  }

  // Live Request Send + AbortController Cancel
  function cancelActiveRequest() {
    if (!activeTab) return;
    const ctrl = activeAbortControllers[activeTab.id];
    if (ctrl) {
      ctrl.abort();
      delete activeAbortControllers[activeTab.id];
    }
    patchActiveTab({ isSending: false });
    showToast("ยกเลิกการส่งคำขอแล้ว", "info");
  }

  async function sendActiveRequest() {
    if (!activeTab) return;
    if (activeTab.isSending) {
      cancelActiveRequest();
      return;
    }
    if (!activeTab.url.trim()) {
      showToast("กรุณาระบุ URL หรือ Endpoint Path ก่อนกด Send", "warning");
      return;
    }
    const headersObj = collectHeadersObject(activeTab);
    if (headersObj === null) {
      showToast("รูปแบบ JSON ในแท็บ Headers ไม่ถูกต้อง", "error");
      return;
    }
    if (activeTab.bodyMode === "json" && activeTab.bodyText.trim() && !activeJsonValidation.valid) {
      const proceed = await customConfirm(
        `Request Body มีรูปแบบ JSON ไม่ถูกต้อง (${activeJsonValidation.message}) ต้องการส่งต่อหรือไม่?`,
      );
      if (!proceed) return;
    }

    const sendingTabId = activeTab.id;
    const reqSnapshot = JSON.parse(JSON.stringify(activeTab));
    const controller = new AbortController();
    activeAbortControllers[sendingTabId] = controller;
    patchActiveTab({ isSending: true, response: null });

    try {
      const res = await fetch(`${API_BASE}/api/api-collections/test-direct`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        signal: controller.signal,
        body: JSON.stringify({
          method: reqSnapshot.method,
          url: reqSnapshot.url.trim(),
          base_url: resolveEffectiveBaseUrl(reqSnapshot),
          headers: headersObj,
          query_params: reqSnapshot.queryParams.filter(
            (q) => q.enabled !== false && q.key.trim(),
          ),
          auth_config: collectAuthObject(reqSnapshot),
          body: collectBodyString(reqSnapshot),
        }),
      });
      const data = await res.json();
      delete activeAbortControllers[sendingTabId];

      tabs = tabs.map((t) =>
        t.id === sendingTabId ? { ...t, isSending: false, response: data } : t,
      );

      requestHistory = [
        {
          id: uid("hist"),
          method: reqSnapshot.method,
          url: data.url || reqSnapshot.url,
          name: reqSnapshot.name,
          status: data.status_code || (data.success ? 200 : "ERR"),
          latency: data.latency_ms ?? null,
          time: new Date().toLocaleTimeString("th-TH", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }),
          snapshot: reqSnapshot,
        },
        ...requestHistory,
      ].slice(0, 30);

      if (!data.success && !data.status_code) {
        showToast(data.error || "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ปลายทางได้", "warning");
      }
    } catch (e) {
      delete activeAbortControllers[sendingTabId];
      if (e.name === "AbortError") return;
      tabs = tabs.map((t) =>
        t.id === sendingTabId
          ? { ...t, isSending: false, response: { success: false, error: e.message } }
          : t,
      );
      showToast("เกิดข้อผิดพลาดระหว่างส่งคำขอ API", "error");
    }
  }

  async function clearHistory() {
    if (requestHistory.length === 0) return;
    const ok = await customConfirm(`ล้างประวัติการยิงทดสอบทั้งหมด ${requestHistory.length} รายการ?`);
    if (ok) {
      requestHistory = [];
      showToast("ล้างประวัติการทดสอบแล้ว", "info");
    }
  }

  function reopenFromHistory(item) {
    const snap = item.snapshot;
    if (!snap) return;
    const newTab = createBlankTab({
      name: snap.name,
      category: snap.category,
      description: snap.description,
      method: snap.method,
      url: snap.url,
      baseUrl: snap.baseUrl,
      queryParams: snap.queryParams,
      auth: snap.auth,
      headers: snap.headers,
      headersJson: snap.headersJson,
      bodyMode: snap.bodyMode,
      bodyText: snap.bodyText,
      formRows: snap.formRows,
      isDirty: true,
    });
    tabs = [...tabs, newTab];
    activeTabId = newTab.id;
  }

  // Save Active Request (Ctrl+S)
  function buildEndpointPayloadFromTab(tab) {
    const headersObj = collectHeadersObject(tab) || {};
    let pathPart = tab.url.trim();
    let derivedBase = (tab.baseUrl || "").trim();
    try {
      if (/^https?:\/\//i.test(pathPart)) {
        const parsed = new URL(pathPart);
        pathPart = `${parsed.pathname}${parsed.search || ""}`;
        if (!derivedBase) derivedBase = `${parsed.protocol}//${parsed.host}`;
      }
    } catch (_) {}

    return {
      endpoint: {
        method: tab.method,
        path: pathPart,
        url: tab.url.trim(),
        name: (tab.name || "").trim() || `${tab.method} ${pathPart}`,
        summary: (tab.name || "").trim() || `${tab.method} ${pathPart}`,
        description: (tab.description || "").trim(),
        category: (tab.category || "General").trim() || "General",
        headers: headersObj,
        query_params: tab.queryParams.filter((q) => q.key && q.key.trim()),
        auth_config: collectAuthObject(tab),
        body: collectBodyString(tab),
        curl: buildCurlFromTab(tab),
      },
      baseUrl: derivedBase,
    };
  }

  async function handleSaveActiveTab(forceChooseCollection = false) {
    if (!activeTab) return;
    if (!selectedProject) {
      showToast("กรุณาเลือกโครงการก่อนบันทึก API", "warning");
      return;
    }
    if (!activeTab.url.trim()) {
      showToast("กรุณาระบุ URL หรือ Endpoint Path ก่อนบันทึก", "warning");
      return;
    }
    if (collectHeadersObject(activeTab) === null) {
      showToast("รูปแบบ JSON ในแท็บ Headers ไม่ถูกต้อง", "error");
      return;
    }

    if (
      !forceChooseCollection &&
      activeTab.collectionId &&
      activeTab.endpointIndex >= 0
    ) {
      await persistUpdateExistingEndpoint(activeTab);
      return;
    }

    if (
      !forceChooseCollection &&
      activeTab.collectionId &&
      activeTab.endpointIndex < 0 &&
      collections.some((c) => c.id === activeTab.collectionId)
    ) {
      await persistAppendToCollection(activeTab, activeTab.collectionId);
      return;
    }

    saveModalRequestName =
      activeTab.name === "Untitled Request"
        ? `${activeTab.method} ${activeTab.url.replace(/^https?:\/\/[^/]+/, "") || "/"}`
        : activeTab.name;
    saveModalCategory = activeTab.category || "General";
    if (collections.length > 0) {
      saveModalMode = "existing";
      saveModalTargetColId = activeTab.collectionId || collections[0].id;
    } else {
      saveModalMode = "new";
      saveModalTargetColId = "";
    }
    saveModalNewColName = "";
    showSaveModal = true;
  }

  async function persistUpdateExistingEndpoint(tab) {
    const col = collections.find((c) => c.id === tab.collectionId);
    if (!col) {
      showToast("ไม่พบ Collection ปลายทาง", "error");
      return;
    }
    patchActiveTab({ isSaving: true });
    try {
      const { endpoint, baseUrl } = buildEndpointPayloadFromTab(tab);
      const nextEndpoints = [...(col.endpoints || [])];
      nextEndpoints[tab.endpointIndex] = endpoint;

      const res = await fetch(`${API_BASE}/api/api-collections/${col.id}`, {
        method: "PUT",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: col.name,
          version: col.version || "1.0",
          base_url: baseUrl || col.base_url || "",
          endpoints: nextEndpoints,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "บันทึกไม่สำเร็จ");

      patchActiveTab({
        name: endpoint.name,
        baseUrl: baseUrl || col.base_url || "",
        isDirty: false,
        isSaving: false,
      });
      await loadCollections();
      showToast(`บันทึก "${endpoint.name}" แล้ว`, "success");
    } catch (e) {
      patchActiveTab({ isSaving: false });
      showToast(e.message || "บันทึกการแก้ไขไม่สำเร็จ", "error");
    }
  }

  async function persistAppendToCollection(tab, targetColId) {
    patchActiveTab({ isSaving: true });
    try {
      const { endpoint, baseUrl } = buildEndpointPayloadFromTab(tab);
      const res = await fetch(`${API_BASE}/api/api-collections/manual`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          project_id: selectedProject,
          target_collection_id: targetColId,
          base_url: baseUrl,
          name: endpoint.name,
          category: endpoint.category,
          description: endpoint.description,
          method: endpoint.method,
          url: endpoint.url,
          headers: endpoint.headers,
          query_params: endpoint.query_params,
          auth_config: endpoint.auth_config,
          body: endpoint.body,
          curl: endpoint.curl,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "บันทึกไม่สำเร็จ");

      const updatedCol = data.collection;
      const newIdx = Math.max(0, (updatedCol?.endpoints?.length || 1) - 1);
      patchActiveTab({
        collectionId: targetColId,
        endpointIndex: newIdx,
        name: endpoint.name,
        baseUrl,
        isDirty: false,
        isSaving: false,
      });
      expandedCollectionIds = new Set([...expandedCollectionIds, targetColId]);
      await loadCollections();
      showToast(`เพิ่ม "${endpoint.name}" เข้า Collection แล้ว`, "success");
    } catch (e) {
      patchActiveTab({ isSaving: false });
      showToast(e.message || "บันทึก API ไม่สำเร็จ", "error");
    }
  }

  async function confirmSaveModal() {
    if (!activeTab) return;
    const reqName = saveModalRequestName.trim() || `${activeTab.method} ${activeTab.url}`;
    const cat = saveModalCategory.trim() || "General";

    patchActiveTab({ name: reqName, category: cat });
    const latestTab = tabs.find((t) => t.id === activeTab.id);

    if (saveModalMode === "existing" && saveModalTargetColId) {
      showSaveModal = false;
      await persistAppendToCollection(latestTab, saveModalTargetColId);
      return;
    }

    const newColName = saveModalNewColName.trim();
    if (!newColName) {
      showToast("กรุณาระบุชื่อ Collection ใหม่", "warning");
      return;
    }

    patchActiveTab({ isSaving: true });
    showSaveModal = false;
    try {
      const { endpoint, baseUrl } = buildEndpointPayloadFromTab(latestTab);
      const res = await fetch(`${API_BASE}/api/api-collections/manual`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          project_id: selectedProject,
          collection_name: newColName,
          base_url: baseUrl,
          name: endpoint.name,
          category: endpoint.category,
          description: endpoint.description,
          method: endpoint.method,
          url: endpoint.url,
          headers: endpoint.headers,
          query_params: endpoint.query_params,
          auth_config: endpoint.auth_config,
          body: endpoint.body,
          curl: endpoint.curl,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "สร้าง Collection ไม่สำเร็จ");

      const createdColId = data.collection?.id || "";
      patchActiveTab({
        collectionId: createdColId,
        endpointIndex: 0,
        name: endpoint.name,
        baseUrl,
        isDirty: false,
        isSaving: false,
      });
      if (createdColId) {
        expandedCollectionIds = new Set([...expandedCollectionIds, createdColId]);
      }
      await loadCollections();
      showToast(`สร้าง Collection "${newColName}" และบันทึก API แล้ว`, "success");
    } catch (e) {
      patchActiveTab({ isSaving: false });
      showToast(e.message || "บันทึกไม่สำเร็จ", "error");
    }
  }

  // Collection CRUD
  function openCreateCollectionModal() {
    if (!selectedProject) {
      showToast("กรุณาเลือกโครงการก่อนสร้าง Collection", "warning");
      return;
    }
    collectionModalMode = "create";
    colModalId = "";
    colModalName = "";
    colModalBaseUrl = selectedEnvUrl || "";
    colModalVersion = "1.0";
    showCollectionModal = true;
  }

  function openEditCollectionModal(col, e) {
    if (e) e.stopPropagation();
    collectionModalMode = "edit";
    colModalId = col.id;
    colModalName = col.name || "";
    colModalBaseUrl = col.base_url || "";
    colModalVersion = col.version || "1.0";
    showCollectionModal = true;
  }

  async function saveCollectionModal() {
    if (!colModalName.trim()) {
      showToast("กรุณาระบุชื่อ Collection", "warning");
      return;
    }
    isSavingCollection = true;
    try {
      if (collectionModalMode === "create") {
        const res = await fetch(`${API_BASE}/api/api-collections/manual`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            project_id: selectedProject,
            create_empty: true,
            collection_name: colModalName.trim(),
            base_url: colModalBaseUrl.trim(),
            version: colModalVersion.trim() || "1.0",
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || "สร้าง Collection ไม่สำเร็จ");
        if (data.collection?.id) {
          expandedCollectionIds = new Set([...expandedCollectionIds, data.collection.id]);
        }
        showToast(`สร้าง Collection "${colModalName.trim()}" แล้ว`, "success");
      } else {
        const col = collections.find((c) => c.id === colModalId);
        const res = await fetch(`${API_BASE}/api/api-collections/${colModalId}`, {
          method: "PUT",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            name: colModalName.trim(),
            base_url: colModalBaseUrl.trim(),
            version: colModalVersion.trim() || "1.0",
            endpoints: col?.endpoints || [],
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error || "อัปเดตไม่สำเร็จ");
        showToast(`อัปเดต Collection "${colModalName.trim()}" แล้ว`, "success");
      }
      showCollectionModal = false;
      await loadCollections();
    } catch (e) {
      showToast(e.message || "เกิดข้อผิดพลาดในการบันทึก Collection", "error");
    } finally {
      isSavingCollection = false;
    }
  }

  async function deleteCollection(col, e) {
    if (e) e.stopPropagation();
    const ok = await customConfirm(`ยืนยันการลบ Collection "${col.name}" (${col.endpoints.length} Endpoints)?`);
    if (!ok) return;
    try {
      const res = await fetch(`${API_BASE}/api/api-collections/${col.id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error("ลบไม่สำเร็จ");
      tabs = tabs.map((t) =>
        t.collectionId === col.id ? { ...t, collectionId: "", endpointIndex: -1, isDirty: true } : t,
      );
      await loadCollections();
      showToast(`ลบ "${col.name}" เรียบร้อยแล้ว`, "success");
    } catch (err) {
      showToast(err.message || "ไม่สามารถลบ Collection ได้", "error");
    }
  }

  async function duplicateEndpoint(col, ep, e) {
    if (e) e.stopPropagation();
    const copy = {
      ...JSON.parse(JSON.stringify(ep)),
      id: undefined,
      name: `${ep.name || ep.summary || ep.path} (Copy)`,
      summary: `${ep.name || ep.summary || ep.path} (Copy)`,
    };
    try {
      const res = await fetch(`${API_BASE}/api/api-collections/${col.id}`, {
        method: "PUT",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: col.name,
          version: col.version || "1.0",
          base_url: col.base_url || "",
          endpoints: [...col.endpoints, copy],
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "ทำสำเนาไม่สำเร็จ");
      await loadCollections();
      showToast(`ทำสำเนา "${copy.name}" แล้ว`, "success");
    } catch (err) {
      showToast(err.message || "ทำสำเนา Endpoint ไม่สำเร็จ", "error");
    }
  }

  async function deleteEndpoint(col, ep, index, e) {
    if (e) e.stopPropagation();
    const ok = await customConfirm(`ลบ Endpoint "${ep.method} ${ep.path || ep.url}" ออกจาก "${col.name}"?`);
    if (!ok) return;
    try {
      const nextEps = col.endpoints.filter((_, idx) => idx !== index);
      const res = await fetch(`${API_BASE}/api/api-collections/${col.id}`, {
        method: "PUT",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          name: col.name,
          version: col.version || "1.0",
          base_url: col.base_url || "",
          endpoints: nextEps,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "ลบ Endpoint ไม่สำเร็จ");

      tabs = tabs.map((t) => {
        if (t.collectionId !== col.id) return t;
        if (t.endpointIndex === index) {
          return { ...t, collectionId: "", endpointIndex: -1, isDirty: true };
        }
        if (t.endpointIndex > index) {
          return { ...t, endpointIndex: t.endpointIndex - 1 };
        }
        return t;
      });
      await loadCollections();
      showToast("ลบ Endpoint เรียบร้อยแล้ว", "success");
    } catch (err) {
      showToast(err.message || "ลบ Endpoint ไม่สำเร็จ", "error");
    }
  }

  function exportCollectionJson(col, e) {
    if (e) e.stopPropagation();
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
    showToast(`ส่งออก "${col.name}" เป็น JSON แล้ว`, "info");
  }

  // Import Modal (File Upload + Paste cURL)
  function openImportModal(defaultTab = "file", targetMode = "new") {
    importModalTab = defaultTab;
    importCurlTarget = targetMode;
    uploadFile = null;
    customImportName = "";
    importCurlText = "";
    showImportModal = true;
  }

  function applySelectedFile(file) {
    if (!file) return;
    uploadFile = file;
    if (!customImportName) {
      customImportName = file.name.replace(/\.(json|yaml|yml)$/i, "");
    }
  }

  function handleFileChange(e) {
    const files = e.target.files;
    if (files && files.length > 0) applySelectedFile(files[0]);
  }

  function handleFileDrop(e) {
    e.preventDefault();
    isDragOver = false;
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) applySelectedFile(files[0]);
  }

  async function handleUploadSpec() {
    if (!selectedProject) {
      showToast("กรุณาเลือกโครงการก่อนนำเข้าไฟล์", "warning");
      return;
    }
    if (!uploadFile) {
      showToast("กรุณาเลือกไฟล์ OpenAPI / Swagger / Postman (.json, .yaml)", "warning");
      return;
    }
    isUploading = true;
    const formData = new FormData();
    formData.append("project_id", selectedProject);
    formData.append("file", uploadFile);
    if (customImportName.trim()) formData.append("name", customImportName.trim());

    try {
      const res = await fetch(`${API_BASE}/api/api-collections/upload`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: formData,
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "นำเข้าไฟล์ไม่สำเร็จ");
      const saved = data.collection || data;
      if (saved.id) {
        expandedCollectionIds = new Set([...expandedCollectionIds, saved.id]);
      }
      showToast(
        `นำเข้า "${saved.name || customImportName}" (${saved.endpoints_count ?? saved.endpoint_count ?? 0} Endpoints) สำเร็จ`,
        "success",
      );
      showImportModal = false;
      await loadCollections();
    } catch (e) {
      showToast(e.message || "เกิดข้อผิดพลาดในการอัปโหลดไฟล์ Spec", "error");
    } finally {
      isUploading = false;
    }
  }

  function handleImportCurlSubmit() {
    if (!importCurlText.trim()) {
      showToast("กรุณาวางคำสั่ง cURL", "warning");
      return;
    }
    if (importCurlTarget === "active" && activeTab) {
      applyCurlToActiveTab(importCurlText);
      showImportModal = false;
      return;
    }
    const parsed = parseCurlString(importCurlText);
    const newTab = createBlankTab({ ...parsed, isDirty: true });
    tabs = [...tabs, newTab];
    activeTabId = newTab.id;
    showImportModal = false;
    showToast("นำเข้า cURL เปิดในแท็บใหม่พร้อมทดสอบแล้ว", "success");
  }

  // Web API Sniffer
  function openSnifferModal() {
    showSnifferModal = true;
    sniffedEndpoints = [];
    selectedSniffedIndices = new Set();
    snifferImportMode = "new";
    snifferCollectionName = "";
    snifferShowAuth = false;
    snifferUrl = snifferUrl || selectedEnvUrl || "";
    snifferTargetCollectionId = collections.length > 0 ? collections[0].id : "";
  }

  async function handleStartSniffing() {
    if (!snifferUrl.trim()) {
      showToast("กรุณาระบุ Target URL ของระบบเป้าหมาย", "warning");
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
      if (!res.ok || !data.success) throw new Error(data.error || "สำรวจ API ไม่สำเร็จ");
      sniffedEndpoints = data.endpoints || [];
      selectedSniffedIndices = new Set(sniffedEndpoints.map((_, i) => i));
      if (!snifferCollectionName) {
        try {
          snifferCollectionName = `Discovered (${new URL(snifferUrl.trim()).host})`;
        } catch (_) {
          snifferCollectionName = "Discovered APIs";
        }
      }
      showToast(`สำรวจพบ ${sniffedEndpoints.length} Endpoints`, "success");
    } catch (e) {
      showToast(e.message || "เกิดข้อผิดพลาดในการสำรวจ API", "error");
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
      selectedSniffedIndices = new Set(sniffedEndpoints.map((_, i) => i));
    }
  }

  async function handleSaveSniffed() {
    if (selectedSniffedIndices.size === 0) {
      showToast("กรุณาเลือกอย่างน้อย 1 Endpoint", "warning");
      return;
    }
    const toSave = Array.from(selectedSniffedIndices).map((i) => sniffedEndpoints[i]);
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
              ? snifferCollectionName.trim() || `Web Sniffer (${baseOrigin || "Target"})`
              : undefined,
          target_collection_id:
            snifferImportMode === "append" ? snifferTargetCollectionId : null,
          base_url: baseOrigin,
          source_label: "Web API Discovery",
          endpoints: toSave,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.error || "บันทึกไม่สำเร็จ");
      if (data.collection?.id) {
        expandedCollectionIds = new Set([...expandedCollectionIds, data.collection.id]);
      }
      showSnifferModal = false;
      await loadCollections();
      showToast(`บันทึก ${toSave.length} Endpoints เรียบร้อยแล้ว`, "success");
    } catch (e) {
      showToast(e.message || "เกิดข้อผิดพลาดในการบันทึก", "error");
    } finally {
      isSniffing = false;
    }
  }

  // Resizable vertical splitter (Mouse + Keyboard ArrowUp/ArrowDown)
  function startSplitResize(e) {
    e.preventDefault();
    isResizingSplit = true;
  }

  function handleSplitterKeydown(e) {
    if (e.key === "ArrowUp") {
      e.preventDefault();
      responsePaneHeight = Math.min(540, responsePaneHeight + 24);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      responsePaneHeight = Math.max(170, responsePaneHeight - 24);
    }
  }

  function handleWindowMouseMove(e) {
    if (!isResizingSplit || !workbenchRightEl) return;
    const rect = workbenchRightEl.getBoundingClientRect();
    const nextHeight = Math.round(rect.bottom - e.clientY);
    responsePaneHeight = Math.max(170, Math.min(rect.height - 220, nextHeight));
  }

  function handleWindowMouseUp() {
    isResizingSplit = false;
  }

  // Global keyboard shortcuts
  function handleGlobalKeydown(e) {
    if (e.key === "Escape") {
      if (showSaveModal) showSaveModal = false;
      else if (showCollectionModal) showCollectionModal = false;
      else if (showImportModal) showImportModal = false;
      else if (showSnifferModal) showSnifferModal = false;
      return;
    }
    const isModalOpen =
      showSaveModal || showCollectionModal || showImportModal || showSnifferModal || showExtensionModal;
    if (isModalOpen) return;

    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      sendActiveRequest();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      handleSaveActiveTab(false);
    }
  }
</script>

<svelte:window
  on:keydown={handleGlobalKeydown}
  on:mousemove={handleWindowMouseMove}
  on:mouseup={handleWindowMouseUp}
/>

<div class="pm-shell" class:resizing={isResizingSplit}>
  <!-- =========================================================================
       TOP WORKSPACE BAR (Project Scope + Environment Base URL + Quick Tools)
       ========================================================================= -->
  <header class="pm-topbar">
    <div class="pm-topbar-left">
      <div class="pm-picker-group">
        <label for="pm-project-select" class="pm-field-label">โครงการ</label>
        <div class="pm-project-select-wrap">
          <CustomSelect
            id="pm-project-select"
            ariaLabel="เลือกโครงการ"
            variant="compact"
            size="sm"
            options={projectOptions}
            bind:value={selectedProject}
            on:change={handleProjectChange}
            minWidth="190px"
            dropdownMinWidth="260px"
            placeholder={isLoadingProjects
              ? "กำลังโหลดโครงการ..."
              : projectOptions.length === 0
                ? "ยังไม่มีโครงการในระบบ"
                : "เลือกโครงการ"}
          />
        </div>
        <button
          type="button"
          class="pm-icon-btn"
          title="รีเฟรชรายการโครงการและ Collections"
          on:click={() => loadProjects()}
          aria-label="รีเฟรชข้อมูล"
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            class:spin={isLoadingProjects || isLoadingCollections}
          >
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      </div>

      {#if selectedProject}
        <div class="pm-divider-v" aria-hidden="true"></div>

        <!-- Environment / Base URL Switcher -->
        <div class="pm-picker-group env-group">
          <label for="pm-env-select" class="pm-field-label">Base URL</label>
          <div class="pm-env-select-wrap">
            <CustomSelect
              id="pm-env-select"
              ariaLabel="เลือก Environment / Base URL"
              variant="compact"
              size="sm"
              options={envOptions}
              bind:value={selectedEnvUrl}
              minWidth="170px"
              dropdownMinWidth="290px"
              placeholder="No Environment"
            />
          </div>
        </div>
      {/if}

      <div class="pm-telemetry-summary">
        <span class="pm-stat-chip">
          <strong>{collections.length}</strong> Col
        </span>
        <span class="pm-stat-chip">
          <strong>{totalEndpointsCount}</strong> APIs
        </span>
        {#if projectsError}
          <button type="button" class="pm-error-pill" on:click={loadProjects}>
            โหลดไม่สำเร็จ — ลองใหม่
          </button>
        {/if}
      </div>
    </div>

    <div class="pm-topbar-right">
      <div class="pm-tool-group" role="group" aria-label="เครื่องมือนำเข้าและสำรวจ API">
        <button
          type="button"
          class="pm-tool-btn"
          disabled={!selectedProject}
          on:click={() => openImportModal("file", "new")}
          title="นำเข้า OpenAPI 3.0, Swagger, Postman Collection หรือ cURL"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <span>Import</span>
        </button>

        <button
          type="button"
          class="pm-tool-btn"
          disabled={!selectedProject}
          on:click={openSnifferModal}
          title="สแกนหา OpenAPI / Swagger / Routes จาก URL ระบบเป้าหมาย"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span>Sniffer</span>
        </button>

        <button
          type="button"
          class="pm-tool-btn"
          disabled={!selectedProject}
          on:click={() => (showExtensionModal = true)}
          title="ดักจับ API จริงจากเบราว์เซอร์ผ่าน Chrome Extension"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="4" />
            <line x1="21.17" y1="8" x2="12" y2="8" />
          </svg>
          <span>Chrome Sync</span>
        </button>
      </div>

      <button
        type="button"
        class="pm-btn-secondary-accent"
        on:click={() => openNewRequestTab(null)}
        title="เปิดแท็บ Request ใหม่"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        <span>New Request</span>
      </button>
    </div>
  </header>

  <!-- =========================================================================
       POSTMAN 2-PANE WORKBENCH (Left Explorer + Right Request/Response Studio)
       ========================================================================= -->
  <div class="pm-body">
    <!-- LEFT SIDEBAR: Collections Tree (with Category Sub-Folders) & History -->
    <aside class="pm-sidebar">
      <div class="pm-sidebar-tabs" role="tablist" aria-label="มุมมอง Sidebar">
        <button
          type="button"
          role="tab"
          aria-selected={sidebarTab === "collections"}
          class="pm-side-tab"
          class:active={sidebarTab === "collections"}
          on:click={() => (sidebarTab = "collections")}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
          <span>Collections</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={sidebarTab === "history"}
          class="pm-side-tab"
          class:active={sidebarTab === "history"}
          on:click={() => (sidebarTab = "history")}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          <span>History {#if requestHistory.length > 0}({requestHistory.length}){/if}</span>
        </button>
      </div>

      {#if sidebarTab === "collections"}
        <div class="pm-sidebar-controls">
          <div class="pm-search-row">
            <div class="pm-search-input-wrap">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                aria-label="ค้นหา Collection หรือ Endpoint"
                placeholder="กรอง Collection, หมวดหมู่, URL..."
                bind:value={sidebarSearch}
              />
              {#if sidebarSearch}
                <button
                  type="button"
                  class="pm-clear-x"
                  on:click={() => (sidebarSearch = "")}
                  aria-label="ล้างคำค้นหา"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              {/if}
            </div>
            <button
              type="button"
              class="pm-new-col-btn"
              disabled={!selectedProject}
              title="สร้าง Collection ใหม่"
              aria-label="สร้าง Collection ใหม่"
              on:click={openCreateCollectionModal}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
          </div>

          <CustomSelect
            ariaLabel="กรองตาม HTTP Method"
            variant="compact"
            size="sm"
            options={SIDEBAR_METHOD_OPTIONS}
            bind:value={sidebarMethodFilter}
            minWidth="100%"
            dropdownMinWidth="220px"
          />
        </div>

        <div class="pm-tree-scroll" role="tree" aria-label="รายการ API Collections">
          {#if isLoadingCollections}
            <div class="pm-skeleton-list" aria-busy="true">
              <div class="pm-skel-row"></div>
              <div class="pm-skel-row short"></div>
              <div class="pm-skel-row"></div>
              <div class="pm-skel-row short"></div>
            </div>
          {:else if !selectedProject}
            <div class="pm-side-empty">
              <p>เลือกโครงการด้านบนเพื่อเปิดคลัง API Collection</p>
            </div>
          {:else if filteredSidebarCollections.length === 0}
            <div class="pm-side-empty">
              {#if collections.length === 0}
                <p>ยังไม่มี Collection ในโครงการนี้</p>
                <div class="pm-empty-actions">
                  <button type="button" class="pm-btn-ghost-sm" on:click={openCreateCollectionModal}>
                    + สร้าง Collection
                  </button>
                  <button type="button" class="pm-btn-ghost-sm" on:click={() => openImportModal("file", "new")}>
                    Import Spec
                  </button>
                </div>
              {:else}
                <p>ไม่พบ Endpoint ที่ตรงกับตัวกรอง</p>
              {/if}
            </div>
          {:else}
            {#each filteredSidebarCollections as col (col.id)}
              {@const isExpanded = expandedCollectionIds.has(col.id) || Boolean(sidebarSearch.trim())}
              <div class="pm-col-node" role="treeitem" aria-expanded={isExpanded} aria-selected="false">
                <div class="pm-tree-item-wrap pm-col-wrap" class:expanded={isExpanded}>
                  <button
                    type="button"
                    class="pm-col-trigger"
                    aria-expanded={isExpanded}
                    on:click={() => toggleCollectionExpand(col.id)}
                  >
                    <span class="pm-chevron" class:open={isExpanded} aria-hidden="true">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    </span>
                    <svg class="pm-folder-ico" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                    <span class="pm-col-title" title={col.name}>{col.name}</span>
                    <span class="pm-col-count">{col._totalEndpoints}</span>
                  </button>

                  <div class="pm-row-actions">
                    <button
                      type="button"
                      class="pm-mini-ico"
                      title="เพิ่ม Request ใหม่ใน Collection นี้"
                      aria-label={`เพิ่ม Request ใหม่ใน ${col.name}`}
                      on:click={() => openNewRequestTab(col)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                        <line x1="12" y1="5" x2="12" y2="19" />
                        <line x1="5" y1="12" x2="19" y2="12" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="pm-mini-ico"
                      title="ตั้งค่า Collection (ชื่อ / Base URL)"
                      aria-label={`ตั้งค่า ${col.name}`}
                      on:click={(e) => openEditCollectionModal(col, e)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="pm-mini-ico"
                      title="ส่งออก JSON"
                      aria-label={`ส่งออก JSON ของ ${col.name}`}
                      on:click={(e) => exportCollectionJson(col, e)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="pm-mini-ico danger"
                      title="ลบ Collection"
                      aria-label={`ลบ ${col.name}`}
                      on:click={(e) => deleteCollection(col, e)}
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                      </svg>
                    </button>
                  </div>
                </div>

                {#if isExpanded}
                  <div class="pm-ep-children" role="group">
                    {#if col._folders.length === 0}
                      <button
                        type="button"
                        class="pm-ep-add-inline"
                        on:click={() => openNewRequestTab(col)}
                      >
                        + เพิ่ม Request แรกในชุดนี้
                      </button>
                    {:else}
                      {#each col._folders as folder (folder.key)}
                        {@const folderOpen = !collapsedFolderKeys.has(folder.key) || Boolean(sidebarSearch.trim())}
                        <div class="pm-cat-node">
                          <div class="pm-tree-item-wrap pm-cat-wrap">
                            <button
                              type="button"
                              class="pm-cat-trigger"
                              aria-expanded={folderOpen}
                              on:click={() => toggleFolderExpand(folder.key)}
                            >
                              <span class="pm-chevron sm" class:open={folderOpen} aria-hidden="true">
                                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                                  <polyline points="9 18 15 12 9 6" />
                                </svg>
                              </span>
                              <svg class="pm-sub-folder-ico" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                              </svg>
                              <span class="pm-cat-name" title={folder.category}>{folder.category}</span>
                              <span class="pm-col-count">{folder.items.length}</span>
                            </button>
                            <div class="pm-row-actions">
                              <button
                                type="button"
                                class="pm-mini-ico"
                                title={`เพิ่ม Request ในหมวดหมู่ ${folder.category}`}
                                aria-label={`เพิ่ม Request ในหมวดหมู่ ${folder.category}`}
                                on:click={() => openNewRequestTab(col, folder.category)}
                              >
                                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                                  <line x1="12" y1="5" x2="12" y2="19" />
                                  <line x1="5" y1="12" x2="19" y2="12" />
                                </svg>
                              </button>
                            </div>
                          </div>

                          {#if folderOpen}
                            <div class="pm-cat-items">
                              {#each folder.items as ep (ep._idx)}
                                {@const isActive =
                                  activeTab &&
                                  activeTab.collectionId === col.id &&
                                  activeTab.endpointIndex === ep._idx}
                                <div class="pm-tree-item-wrap pm-ep-wrap" class:active={isActive}>
                                  <button
                                    type="button"
                                    class="pm-ep-trigger"
                                    aria-current={isActive ? "page" : undefined}
                                    on:click={() => openEndpointInTab(col, ep, ep._idx)}
                                    title={`${ep.method} ${ep.url || ep.path}`}
                                  >
                                    <span class="pm-verb" style="color: {verbColor(ep.method)};">
                                      {formatVerb(ep.method)}
                                    </span>
                                    <span class="pm-ep-label">
                                      {ep.name || ep.summary || ep.path || ep.url}
                                    </span>
                                  </button>
                                  <div class="pm-row-actions">
                                    <button
                                      type="button"
                                      class="pm-mini-ico"
                                      title="ทำสำเนา Request"
                                      aria-label={`ทำสำเนา ${ep.name || ep.path}`}
                                      on:click={(e) => duplicateEndpoint(col, ep, e)}
                                    >
                                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                                      </svg>
                                    </button>
                                    <button
                                      type="button"
                                      class="pm-mini-ico danger"
                                      title="ลบ Request"
                                      aria-label={`ลบ ${ep.name || ep.path}`}
                                      on:click={(e) => deleteEndpoint(col, ep, ep._idx, e)}
                                    >
                                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <polyline points="3 6 5 6 21 6" />
                                        <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                                      </svg>
                                    </button>
                                  </div>
                                </div>
                              {/each}
                            </div>
                          {/if}
                        </div>
                      {/each}
                    {/if}
                  </div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>
      {:else}
        <!-- History Sidebar -->
        <div class="pm-history-head">
          <span>ประวัติการยิงทดสอบล่าสุด</span>
          {#if requestHistory.length > 0}
            <button type="button" class="pm-link-btn" on:click={clearHistory}>
              ล้างทั้งหมด
            </button>
          {/if}
        </div>
        <div class="pm-tree-scroll">
          {#if requestHistory.length === 0}
            <div class="pm-side-empty">
              <p>ยังไม่มีประวัติการทดสอบ กด <strong>Send</strong> ที่ Request ใดก็ได้เพื่อบันทึกประวัติ</p>
            </div>
          {:else}
            {#each requestHistory as item (item.id)}
              <button
                type="button"
                class="pm-hist-row"
                on:click={() => reopenFromHistory(item)}
              >
                <div class="pm-hist-top">
                  <span class="pm-verb" style="color: {verbColor(item.method)};">
                    {formatVerb(item.method)}
                  </span>
                  <span class="pm-hist-url">{item.url}</span>
                </div>
                <div class="pm-hist-meta">
                  <span
                    class="pm-hist-status"
                    class:ok={typeof item.status === "number" && item.status < 400}
                    class:err={typeof item.status !== "number" || item.status >= 400}
                  >
                    {item.status}
                  </span>
                  {#if item.latency !== null}
                    <span>{item.latency} ms</span>
                  {/if}
                  <span>{item.time}</span>
                </div>
              </button>
            {/each}
          {/if}
        </div>
      {/if}
    </aside>

    <!-- RIGHT WORKBENCH: Tabs + Request Builder + Resizable Response Viewer -->
    <main class="pm-workbench" bind:this={workbenchRightEl}>
      <!-- Multi-Tab Strip (Full Keyboard Support) -->
      <div class="pm-tabbar" role="tablist" aria-label="แท็บ Request ที่เปิดอยู่">
        <div class="pm-tabs-scroll">
          {#each tabs as tab, idx (tab.id)}
            {@const isTabActive = activeTab && tab.id === activeTab.id}
            <div class="pm-tab-wrap" class:active={isTabActive}>
              <button
                type="button"
                class="pm-tab-trigger"
                role="tab"
                aria-selected={isTabActive}
                tabindex={isTabActive ? 0 : -1}
                on:click={() => (activeTabId = tab.id)}
                on:keydown={(e) => handleTabKeydown(e, idx)}
              >
                <span class="pm-verb" style="color: {verbColor(tab.method)};">
                  {formatVerb(tab.method)}
                </span>
                <span class="pm-tab-name" title={tab.name}>{tab.name || "Untitled Request"}</span>
                {#if tab.isDirty}
                  <span class="pm-dirty-dot" title="มีการเปลี่ยนแปลงที่ยังไม่บันทึก" aria-label="ยังไม่บันทึก"></span>
                {/if}
              </button>
              <button
                type="button"
                class="pm-tab-close"
                aria-label={`ปิดแท็บ ${tab.name || "Untitled Request"}`}
                on:click={(e) => closeTab(tab.id, e)}
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          {/each}
          <button
            type="button"
            class="pm-tab-add"
            title="เปิดแท็บ Request ใหม่"
            aria-label="เปิดแท็บ Request ใหม่"
            on:click={() => openNewRequestTab(null)}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        </div>
      </div>

      {#if activeTab}
        <!-- Request Identity Row -->
        <div class="pm-req-header">
          <div class="pm-req-identity">
            {#if activeTabCollection}
              <span class="pm-crumb">{activeTabCollection.name}</span>
              <span class="pm-crumb-sep" aria-hidden="true">/</span>
              <span class="pm-crumb cat">{activeTab.category || "General"}</span>
              <span class="pm-crumb-sep" aria-hidden="true">/</span>
            {:else}
              <span class="pm-crumb draft">Draft</span>
              <span class="pm-crumb-sep" aria-hidden="true">/</span>
            {/if}
            <input
              type="text"
              class="pm-req-name-input"
              aria-label="ชื่อ Request"
              value={activeTab.name}
              placeholder="ตั้งชื่อ Request (เช่น Get Users List)"
              on:input={(e) => patchActiveTab({ name: e.currentTarget.value, isDirty: true })}
            />
          </div>

          <div class="pm-req-actions">
            <button
              type="button"
              class="pm-subtle-btn"
              title="วางคำสั่ง cURL ลงในแท็บนี้"
              on:click={() => openImportModal("curl", "active")}
            >
              วาง cURL
            </button>
            <button
              type="button"
              class="pm-save-btn"
              disabled={activeTab.isSaving || !selectedProject}
              on:click={() => handleSaveActiveTab(false)}
              title="บันทึก Request (Ctrl+S)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                <polyline points="17 21 17 13 7 13 7 21" />
                <polyline points="7 3 7 8 15 8" />
              </svg>
              <span>{activeTab.isSaving ? "กำลังบันทึก..." : "บันทึก"}</span>
            </button>
            {#if activeTab.collectionId}
              <button
                type="button"
                class="pm-subtle-btn"
                title="บันทึกสำเนาลง Collection อื่น"
                on:click={() => handleSaveActiveTab(true)}
              >
                บันทึกเป็น...
              </button>
            {/if}
          </div>
        </div>

        <!-- Postman URL Bar: CustomSelect Method Picker + URL Input + Primary Send/Cancel Button -->
        <div class="pm-url-bar-row">
          <div class="pm-url-bar">
            <div class="pm-method-wrap">
              <CustomSelect
                ariaLabel="HTTP Method"
                variant="inline-method"
                options={METHOD_SELECT_OPTIONS}
                value={activeTab.method}
                minWidth="104px"
                dropdownMinWidth="136px"
                on:change={(e) => patchActiveTab({ method: e.detail, isDirty: true })}
              />
            </div>
            <div class="pm-url-sep" aria-hidden="true"></div>
            <input
              type="text"
              class="pm-url-input"
              aria-label="Endpoint URL"
              value={activeTab.url}
              placeholder="กรอก URL (เช่น https://api.example.com/v1/users หรือวางคำสั่ง curl ได้เลย)"
              on:input={(e) => handleUrlInput(e.currentTarget.value)}
              on:paste={handleUrlPaste}
              on:keydown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  sendActiveRequest();
                }
              }}
            />
            {#if activeTab.url.startsWith("/") && resolveEffectiveBaseUrl(activeTab)}
              <span class="pm-base-pill" title={`จะต่อท้าย ${resolveEffectiveBaseUrl(activeTab)}`}>
                {resolveEffectiveBaseUrl(activeTab).replace(/^https?:\/\//i, "")}
              </span>
            {/if}
          </div>

          <button
            type="button"
            class="pm-send-btn"
            class:canceling={activeTab.isSending}
            disabled={!activeTab.isSending && !activeTab.url.trim()}
            on:click={sendActiveRequest}
            title={activeTab.isSending ? "คลิกเพื่อยกเลิกคำขอ" : "ส่งคำขอ API (Ctrl+Enter)"}
          >
            {#if activeTab.isSending}
              <span class="pm-spinner"></span>
              <span>Cancel</span>
            {:else}
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
              <span>Send</span>
            {/if}
          </button>
        </div>

        <!-- REQUEST CONFIG PANE -->
        <section class="pm-request-pane">
          <div class="pm-subtabs" role="tablist" aria-label="การตั้งค่าคำขอ">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab.activeReqTab === "params"}
              class="pm-subtab"
              class:active={activeTab.activeReqTab === "params"}
              on:click={() => patchActiveTab({ activeReqTab: "params" })}
            >
              Params
              {#if activeParamsCount > 0}
                <span class="pm-badge-count">{activeParamsCount}</span>
              {/if}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab.activeReqTab === "auth"}
              class="pm-subtab"
              class:active={activeTab.activeReqTab === "auth"}
              on:click={() => patchActiveTab({ activeReqTab: "auth" })}
            >
              Authorization
              {#if activeTab.auth.type !== "none"}
                <span class="pm-active-dot" aria-label="เปิดใช้งาน"></span>
              {/if}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab.activeReqTab === "headers"}
              class="pm-subtab"
              class:active={activeTab.activeReqTab === "headers"}
              on:click={() => patchActiveTab({ activeReqTab: "headers" })}
            >
              Headers
              {#if activeHeadersCount > 0}
                <span class="pm-badge-count">{activeHeadersCount}</span>
              {/if}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab.activeReqTab === "body"}
              class="pm-subtab"
              class:active={activeTab.activeReqTab === "body"}
              on:click={() => patchActiveTab({ activeReqTab: "body" })}
            >
              Body
              {#if activeTab.bodyMode !== "none" && (activeTab.bodyText.trim() || activeTab.formRows.some((r) => r.key.trim()))}
                <span class="pm-active-dot" aria-label="มีเนื้อหา"></span>
              {/if}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab.activeReqTab === "info"}
              class="pm-subtab"
              class:active={activeTab.activeReqTab === "info"}
              on:click={() => patchActiveTab({ activeReqTab: "info" })}
            >
              Settings
            </button>
          </div>

          <div class="pm-req-content">
            {#if activeTab.activeReqTab === "params"}
              <div class="pm-kv-table">
                <div class="pm-kv-head">
                  <span class="col-chk"></span>
                  <span>KEY</span>
                  <span>VALUE</span>
                  <span class="col-act"></span>
                </div>
                {#each activeTab.queryParams as row, idx}
                  <div class="pm-kv-row" class:disabled={row.enabled === false}>
                    <div class="col-chk">
                      <input
                        type="checkbox"
                        checked={row.enabled !== false}
                        aria-label="เปิดใช้งานพารามิเตอร์"
                        on:change={(e) => updateQueryParam(idx, "enabled", e.currentTarget.checked)}
                      />
                    </div>
                    <input
                      type="text"
                      class="pm-cell-input mono"
                      aria-label="Query Parameter Key"
                      placeholder="Key (เช่น page)"
                      value={row.key}
                      on:input={(e) => updateQueryParam(idx, "key", e.currentTarget.value)}
                    />
                    <input
                      type="text"
                      class="pm-cell-input mono"
                      aria-label="Query Parameter Value"
                      placeholder="Value (เช่น 1)"
                      value={row.value}
                      on:input={(e) => updateQueryParam(idx, "value", e.currentTarget.value)}
                    />
                    <div class="col-act">
                      {#if row.key || row.value || activeTab.queryParams.length > 1}
                        <button
                          type="button"
                          class="pm-row-del"
                          aria-label="ลบแถวพารามิเตอร์"
                          on:click={() => removeQueryParam(idx)}
                        >
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        </button>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {:else if activeTab.activeReqTab === "auth"}
              <div class="pm-auth-split">
                <div class="pm-auth-left">
                  <label for="pm-auth-type">รูปแบบการยืนยันตัวตน (Auth Type)</label>
                  <CustomSelect
                    id="pm-auth-type"
                    ariaLabel="เลือกรูปแบบ Authorization"
                    variant="compact"
                    size="md"
                    options={AUTH_TYPE_OPTIONS}
                    value={activeTab.auth.type}
                    minWidth="100%"
                    dropdownMinWidth="280px"
                    on:change={(e) =>
                      patchActiveTab((t) => ({
                        ...t,
                        auth: { ...t.auth, type: e.detail },
                        isDirty: true,
                      }))}
                  />
                  <p class="pm-auth-hint">
                    ระบบจะแนบ Header หรือ Query Auth ให้อัตโนมัติเมื่อกด Send และบันทึกไว้กับ Endpoint
                  </p>
                </div>

                <div class="pm-auth-right">
                  {#if activeTab.auth.type === "none"}
                    <div class="pm-auth-empty">
                      Request นี้ไม่ได้ตั้งค่า Authorization — เลือกรูปแบบทางซ้ายหาก API ต้องการ Token หรือ Key
                    </div>
                  {:else if activeTab.auth.type === "bearer"}
                    <div class="pm-field">
                      <label for="pm-bearer-token">Bearer Token</label>
                      <div class="pm-secret-wrap">
                        <input
                          id="pm-bearer-token"
                          type={showBearerSecret ? "text" : "password"}
                          class="pm-input mono"
                          placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                          value={activeTab.auth.token}
                          on:input={(e) =>
                            patchActiveTab((t) => ({
                              ...t,
                              auth: { ...t.auth, token: e.currentTarget.value },
                              isDirty: true,
                            }))}
                        />
                        <button
                          type="button"
                          class="pm-eye-btn"
                          aria-label={showBearerSecret ? "ซ่อน Token" : "แสดง Token"}
                          on:click={() => (showBearerSecret = !showBearerSecret)}
                        >
                          {#if showBearerSecret}
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                              <line x1="1" y1="1" x2="23" y2="23" />
                            </svg>
                          {:else}
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                              <circle cx="12" cy="12" r="3" />
                            </svg>
                          {/if}
                        </button>
                      </div>
                    </div>
                  {:else if activeTab.auth.type === "apikey"}
                    <div class="pm-form-grid-3">
                      <div class="pm-field">
                        <label for="pm-apikey-key">Key</label>
                        <input
                          id="pm-apikey-key"
                          type="text"
                          class="pm-input mono"
                          value={activeTab.auth.key}
                          on:input={(e) =>
                            patchActiveTab((t) => ({
                              ...t,
                              auth: { ...t.auth, key: e.currentTarget.value },
                              isDirty: true,
                            }))}
                        />
                      </div>
                      <div class="pm-field">
                        <label for="pm-apikey-val">Value</label>
                        <div class="pm-secret-wrap">
                          <input
                            id="pm-apikey-val"
                            type={showApiKeySecret ? "text" : "password"}
                            class="pm-input mono"
                            value={activeTab.auth.value}
                            on:input={(e) =>
                              patchActiveTab((t) => ({
                                ...t,
                                auth: { ...t.auth, value: e.currentTarget.value },
                                isDirty: true,
                              }))}
                          />
                          <button
                            type="button"
                            class="pm-eye-btn"
                            aria-label={showApiKeySecret ? "ซ่อน API Key" : "แสดง API Key"}
                            on:click={() => (showApiKeySecret = !showApiKeySecret)}
                          >
                            {#if showApiKeySecret}
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                                <line x1="1" y1="1" x2="23" y2="23" />
                              </svg>
                            {:else}
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            {/if}
                          </button>
                        </div>
                      </div>
                      <div class="pm-field">
                        <label for="pm-apikey-in">ส่งไปที่</label>
                        <CustomSelect
                          id="pm-apikey-in"
                          ariaLabel="ตำแหน่งการส่ง API Key"
                          variant="compact"
                          size="md"
                          options={API_KEY_IN_OPTIONS}
                          value={activeTab.auth.in}
                          minWidth="100%"
                          on:change={(e) =>
                            patchActiveTab((t) => ({
                              ...t,
                              auth: { ...t.auth, in: e.detail },
                              isDirty: true,
                            }))}
                        />
                      </div>
                    </div>
                  {:else if activeTab.auth.type === "basic"}
                    <div class="pm-form-grid-2">
                      <div class="pm-field">
                        <label for="pm-basic-user">Username</label>
                        <input
                          id="pm-basic-user"
                          type="text"
                          class="pm-input"
                          value={activeTab.auth.username}
                          on:input={(e) =>
                            patchActiveTab((t) => ({
                              ...t,
                              auth: { ...t.auth, username: e.currentTarget.value },
                              isDirty: true,
                            }))}
                        />
                      </div>
                      <div class="pm-field">
                        <label for="pm-basic-pass">Password</label>
                        <div class="pm-secret-wrap">
                          <input
                            id="pm-basic-pass"
                            type={showBasicPass ? "text" : "password"}
                            class="pm-input"
                            value={activeTab.auth.password}
                            on:input={(e) =>
                              patchActiveTab((t) => ({
                                ...t,
                                auth: { ...t.auth, password: e.currentTarget.value },
                                isDirty: true,
                              }))}
                          />
                          <button
                            type="button"
                            class="pm-eye-btn"
                            aria-label={showBasicPass ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"}
                            on:click={() => (showBasicPass = !showBasicPass)}
                          >
                            {#if showBasicPass}
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                                <line x1="1" y1="1" x2="23" y2="23" />
                              </svg>
                            {:else}
                              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            {/if}
                          </button>
                        </div>
                      </div>
                    </div>
                  {/if}
                </div>
              </div>
            {:else if activeTab.activeReqTab === "headers"}
              <div class="pm-inline-toolbar">
                <div class="pm-segmented">
                  <button
                    type="button"
                    class:active={activeTab.headerMode === "table"}
                    on:click={() => switchHeaderMode("table")}
                  >
                    Key-Value
                  </button>
                  <button
                    type="button"
                    class:active={activeTab.headerMode === "json"}
                    on:click={() => switchHeaderMode("json")}
                  >
                    Bulk JSON
                  </button>
                </div>
              </div>

              {#if activeTab.headerMode === "table"}
                <div class="pm-kv-table">
                  <div class="pm-kv-head">
                    <span class="col-chk"></span>
                    <span>HEADER KEY</span>
                    <span>VALUE</span>
                    <span class="col-act"></span>
                  </div>
                  {#each activeTab.headers as row, idx}
                    <div class="pm-kv-row" class:disabled={row.enabled === false}>
                      <div class="col-chk">
                        <input
                          type="checkbox"
                          checked={row.enabled !== false}
                          aria-label="เปิดใช้งาน Header"
                          on:change={(e) => updateHeaderRow(idx, "enabled", e.currentTarget.checked)}
                        />
                      </div>
                      <input
                        type="text"
                        class="pm-cell-input mono"
                        aria-label="Header Key"
                        placeholder="Header (เช่น Content-Type)"
                        value={row.key}
                        on:input={(e) => updateHeaderRow(idx, "key", e.currentTarget.value)}
                      />
                      <input
                        type="text"
                        class="pm-cell-input mono"
                        aria-label="Header Value"
                        placeholder="Value (เช่น application/json)"
                        value={row.value}
                        on:input={(e) => updateHeaderRow(idx, "value", e.currentTarget.value)}
                      />
                      <div class="col-act">
                        {#if row.key || row.value || activeTab.headers.length > 1}
                          <button
                            type="button"
                            class="pm-row-del"
                            aria-label="ลบ Header"
                            on:click={() => removeHeaderRow(idx)}
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <line x1="18" y1="6" x2="6" y2="18" />
                              <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                          </button>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <textarea
                  class="pm-code-editor"
                  aria-label="Headers JSON"
                  spellcheck="false"
                  value={activeTab.headersJson}
                  on:input={(e) => patchActiveTab({ headersJson: e.currentTarget.value, isDirty: true })}
                ></textarea>
              {/if}
            {:else if activeTab.activeReqTab === "body"}
              <div class="pm-inline-toolbar">
                <div class="pm-radio-group" role="radiogroup" aria-label="รูปแบบ Request Body">
                  {#each [
                    { id: "none", label: "none" },
                    { id: "json", label: "raw (JSON)" },
                    { id: "urlencoded", label: "x-www-form-urlencoded" },
                    { id: "raw", label: "raw (Text)" },
                  ] as opt}
                    <label class="pm-radio-pill" class:active={activeTab.bodyMode === opt.id}>
                      <input
                        type="radio"
                        name={`body-mode-${activeTab.id}`}
                        checked={activeTab.bodyMode === opt.id}
                        on:change={() => patchActiveTab({ bodyMode: opt.id, isDirty: true })}
                      />
                      <span>{opt.label}</span>
                    </label>
                  {/each}
                </div>

                {#if activeTab.bodyMode === "json"}
                  <div class="pm-body-tools">
                    {#if activeTab.bodyText.trim()}
                      <span class="pm-json-badge" class:invalid={!activeJsonValidation.valid}>
                        {activeJsonValidation.valid ? "JSON ถูกต้อง" : "JSON ไม่ถูกต้อง"}
                      </span>
                    {/if}
                    <button type="button" class="pm-link-btn" on:click={beautifyActiveBody}>
                      จัดรูปแบบ (Beautify)
                    </button>
                  </div>
                {/if}
              </div>

              {#if activeTab.bodyMode === "json" && activeTab.bodyText.trim() && !activeJsonValidation.valid}
                <div class="pm-inline-error" role="alert">
                  ข้อผิดพลาด JSON: {activeJsonValidation.message}
                </div>
              {/if}

              {#if activeTab.bodyMode === "none"}
                <div class="pm-body-empty">Request นี้ไม่มี Body — เลือก <strong>raw (JSON)</strong> เพื่อส่งข้อมูล JSON</div>
              {:else if activeTab.bodyMode === "urlencoded"}
                <div class="pm-kv-table">
                  <div class="pm-kv-head">
                    <span class="col-chk"></span>
                    <span>KEY</span>
                    <span>VALUE</span>
                    <span class="col-act"></span>
                  </div>
                  {#each activeTab.formRows as row, idx}
                    <div class="pm-kv-row" class:disabled={row.enabled === false}>
                      <div class="col-chk">
                        <input
                          type="checkbox"
                          checked={row.enabled !== false}
                          aria-label="เปิดใช้งาน Form field"
                          on:change={(e) => updateFormRow(idx, "enabled", e.currentTarget.checked)}
                        />
                      </div>
                      <input
                        type="text"
                        class="pm-cell-input mono"
                        aria-label="Form Key"
                        placeholder="Field key"
                        value={row.key}
                        on:input={(e) => updateFormRow(idx, "key", e.currentTarget.value)}
                      />
                      <input
                        type="text"
                        class="pm-cell-input mono"
                        aria-label="Form Value"
                        placeholder="Field value"
                        value={row.value}
                        on:input={(e) => updateFormRow(idx, "value", e.currentTarget.value)}
                      />
                      <div class="col-act">
                        {#if row.key || row.value || activeTab.formRows.length > 1}
                          <button
                            type="button"
                            class="pm-row-del"
                            aria-label="ลบแถว"
                            on:click={() => removeFormRow(idx)}
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <line x1="18" y1="6" x2="6" y2="18" />
                              <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                          </button>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <textarea
                  class="pm-code-editor"
                  aria-label="Request Body"
                  spellcheck="false"
                  placeholder={activeTab.bodyMode === "json"
                    ? '{\n  "username": "qa_tester",\n  "action": "verify"\n}'
                    : "ระบุข้อความ Raw Body ที่ต้องการส่ง..."}
                  value={activeTab.bodyText}
                  on:input={(e) => patchActiveTab({ bodyText: e.currentTarget.value, isDirty: true })}
                ></textarea>
              {/if}
            {:else if activeTab.activeReqTab === "info"}
              <div class="pm-settings-form">
                <div class="pm-form-grid-2">
                  <div class="pm-field">
                    <label for="pm-info-cat">หมวดหมู่ / โฟลเดอร์ใน Sidebar (Category)</label>
                    <input
                      id="pm-info-cat"
                      type="text"
                      class="pm-input"
                      placeholder="เช่น Auth, Orders, Users"
                      value={activeTab.category}
                      on:input={(e) => patchActiveTab({ category: e.currentTarget.value, isDirty: true })}
                    />
                  </div>
                  <div class="pm-field">
                    <label for="pm-info-base">Base URL เฉพาะรายการ (ใช้เติมหน้า Path แบบ <code>/api/...</code>)</label>
                    <input
                      id="pm-info-base"
                      type="text"
                      class="pm-input mono"
                      placeholder={selectedEnvUrl || "https://api.example.com"}
                      value={activeTab.baseUrl}
                      on:input={(e) => patchActiveTab({ baseUrl: e.currentTarget.value, isDirty: true })}
                    />
                  </div>
                </div>
                <div class="pm-field">
                  <label for="pm-info-desc">คำอธิบาย Endpoint (ช่วยให้ AI QA วิเคราะห์ได้แม่นยำขึ้น)</label>
                  <textarea
                    id="pm-info-desc"
                    rows="3"
                    class="pm-input"
                    placeholder="อธิบายหน้าที่ เงื่อนไข หรือผลลัพธ์ที่คาดหวังของ API นี้..."
                    value={activeTab.description}
                    on:input={(e) => patchActiveTab({ description: e.currentTarget.value, isDirty: true })}
                  ></textarea>
                </div>
              </div>
            {/if}
          </div>
        </section>

        <!-- ACCESSIBLE DRAGGABLE SPLITTER -->
        <div
          class="pm-splitter"
          role="separator"
          tabindex="0"
          aria-orientation="horizontal"
          aria-label="ปรับขนาดพื้นที่ Response (กดลูกศรขึ้น/ลงได้)"
          aria-valuemin={170}
          aria-valuemax={540}
          aria-valuenow={responsePaneHeight}
          on:mousedown={startSplitResize}
          on:keydown={handleSplitterKeydown}
        >
          <span class="pm-splitter-grip" aria-hidden="true"></span>
        </div>

        <!-- RESPONSE INSPECTOR PANE -->
        <section class="pm-response-pane" style={`height: ${responsePaneHeight}px;`}>
          <div class="pm-res-header">
            <div class="pm-res-tabs" role="tablist" aria-label="ผลลัพธ์จากเซิร์ฟเวอร์">
              <button
                type="button"
                role="tab"
                aria-selected={activeTab.activeResTab === "body"}
                class="pm-subtab"
                class:active={activeTab.activeResTab === "body"}
                on:click={() => patchActiveTab({ activeResTab: "body" })}
              >
                Response Body
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab.activeResTab === "headers"}
                class="pm-subtab"
                class:active={activeTab.activeResTab === "headers"}
                on:click={() => patchActiveTab({ activeResTab: "headers" })}
              >
                Headers
                {#if activeTab.response?.response_headers}
                  <span class="pm-badge-count">
                    {Object.keys(activeTab.response.response_headers).length}
                  </span>
                {/if}
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab.activeResTab === "curl"}
                class="pm-subtab"
                class:active={activeTab.activeResTab === "curl"}
                on:click={() => patchActiveTab({ activeResTab: "curl" })}
              >
                cURL Snippet
              </button>
            </div>

            <div class="pm-res-meta">
              {#if activeTab.response && activeTab.response.status_code}
                <span
                  class="pm-status-badge"
                  class:ok={activeTab.response.status_code >= 200 && activeTab.response.status_code < 300}
                  class:redir={activeTab.response.status_code >= 300 && activeTab.response.status_code < 400}
                  class:warn={activeTab.response.status_code >= 400 && activeTab.response.status_code < 500}
                  class:err={activeTab.response.status_code >= 500}
                >
                  {activeTab.response.status_code} {activeTab.response.status_text || ""}
                </span>
                <span class="pm-metric">{activeTab.response.latency_ms} ms</span>
                {#if activeTab.response.response_size_bytes !== undefined}
                  <span class="pm-metric">
                    {(activeTab.response.response_size_bytes / 1024).toFixed(2)} KB
                  </span>
                {/if}
                {#if activeTab.activeResTab === "body"}
                  <div class="pm-segmented compact">
                    <button
                      type="button"
                      class:active={activeTab.responseViewMode === "pretty"}
                      on:click={() => patchActiveTab({ responseViewMode: "pretty" })}
                    >
                      Pretty
                    </button>
                    <button
                      type="button"
                      class:active={activeTab.responseViewMode === "raw"}
                      on:click={() => patchActiveTab({ responseViewMode: "raw" })}
                    >
                      Raw
                    </button>
                  </div>
                  <button
                    type="button"
                    class="pm-mini-copy"
                    on:click={() => copyText(formattedResponseBody, "Response Body")}
                  >
                    Copy
                  </button>
                {/if}
              {/if}
            </div>
          </div>

          <div class="pm-res-content">
            {#if activeTab.activeResTab === "curl"}
              <div class="pm-code-wrap">
                <button
                  type="button"
                  class="pm-floating-copy"
                  on:click={() => copyText(buildCurlFromTab(activeTab), "คำสั่ง cURL")}
                >
                  Copy cURL
                </button>
                <pre class="pm-response-pre">{buildCurlFromTab(activeTab)}</pre>
              </div>
            {:else if activeTab.isSending}
              <div class="pm-res-state">
                <span class="pm-spinner lg"></span>
                <span>กำลังส่งคำขอ {activeTab.method} ไปยังเซิร์ฟเวอร์เป้าหมาย...</span>
                <button type="button" class="pm-btn-ghost-sm" on:click={cancelActiveRequest}>
                  ยกเลิกคำขอ
                </button>
              </div>
            {:else if !activeTab.response}
              <div class="pm-res-state idle">
                <div class="pm-res-idle-title">กรอก URL แล้วกด Send เพื่อดูผลลัพธ์จริงทันที</div>
                <div class="pm-shortcuts-row">
                  <span><kbd>Ctrl</kbd> + <kbd>Enter</kbd> ยิงทดสอบ</span>
                  <span><kbd>Ctrl</kbd> + <kbd>S</kbd> บันทึกเข้า Collection</span>
                  <span>วางคำสั่ง <code>curl</code> ลงในช่อง URL ได้ทันที</span>
                </div>
              </div>
            {:else if !activeTab.response.status_code && activeTab.response.error}
              <div class="pm-res-error" role="alert">
                <div class="pm-res-error-head">
                  <strong>ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์เป้าหมายได้</strong>
                  <button type="button" class="pm-btn-ghost-sm" on:click={sendActiveRequest}>
                    ลองยิงใหม่ (Retry)
                  </button>
                </div>
                <p>{activeTab.response.error}</p>
                {#if activeTab.response.url}
                  <span class="pm-res-url">URL ที่เรียก: {activeTab.response.url}</span>
                {/if}
              </div>
            {:else if activeTab.activeResTab === "headers"}
              {@const rHeaders = Object.entries(activeTab.response.response_headers || {})}
              {#if rHeaders.length === 0}
                <div class="pm-res-state idle">ไม่มี Response Headers</div>
              {:else}
                <div class="pm-res-headers-table">
                  {#each rHeaders as [hk, hv]}
                    <div class="pm-res-h-row">
                      <span class="h-key">{hk}</span>
                      <span class="h-val">{hv}</span>
                    </div>
                  {/each}
                </div>
              {/if}
            {:else}
              <pre class="pm-response-pre">{formattedResponseBody}</pre>
            {/if}
          </div>
        </section>
      {/if}
    </main>
  </div>
</div>

<!-- =========================================================================
     MODAL: SAVE REQUEST TO COLLECTION
     ========================================================================= -->
{#if showSaveModal}
  <div class="pm-modal-backdrop" role="presentation" on:click|self={() => (showSaveModal = false)}>
    <div class="pm-modal sm" role="dialog" aria-modal="true" aria-labelledby="save-modal-title">
      <div class="pm-modal-head">
        <h3 id="save-modal-title">บันทึก Request เข้า Collection</h3>
        <button type="button" class="pm-modal-close" on:click={() => (showSaveModal = false)} aria-label="ปิด">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
      <div class="pm-modal-body">
        <div class="pm-field">
          <label for="save-req-name">ชื่อ Request</label>
          <input id="save-req-name" type="text" class="pm-input" bind:value={saveModalRequestName} />
        </div>
        <div class="pm-field">
          <label for="save-req-cat">หมวดหมู่ / โฟลเดอร์ใน Sidebar (Category)</label>
          <input id="save-req-cat" type="text" class="pm-input" bind:value={saveModalCategory} placeholder="General" />
        </div>

        <div class="pm-segmented full">
          <button
            type="button"
            class:active={saveModalMode === "existing"}
            disabled={collections.length === 0}
            on:click={() => (saveModalMode = "existing")}
          >
            บันทึกเข้า Collection เดิม ({collections.length})
          </button>
          <button
            type="button"
            class:active={saveModalMode === "new"}
            on:click={() => (saveModalMode = "new")}
          >
            สร้าง Collection ใหม่
          </button>
        </div>

        {#if saveModalMode === "existing"}
          <div class="pm-field">
            <label for="save-target-col">เลือก Collection ปลายทาง</label>
            <CustomSelect
              id="save-target-col"
              ariaLabel="เลือก Collection ปลายทาง"
              variant="compact"
              size="md"
              options={collectionSelectOptions}
              bind:value={saveModalTargetColId}
              minWidth="100%"
            />
          </div>
        {:else}
          <div class="pm-field">
            <label for="save-new-col">ชื่อ Collection ใหม่</label>
            <input
              id="save-new-col"
              type="text"
              class="pm-input"
              placeholder="เช่น Auth Service API"
              bind:value={saveModalNewColName}
            />
          </div>
        {/if}
      </div>
      <div class="pm-modal-foot">
        <button type="button" class="pm-tool-btn" on:click={() => (showSaveModal = false)}>ยกเลิก</button>
        <button type="button" class="pm-btn-primary-sm" on:click={confirmSaveModal}>บันทึก Request</button>
      </div>
    </div>
  </div>
{/if}

<!-- =========================================================================
     MODAL: CREATE / EDIT COLLECTION SETTINGS
     ========================================================================= -->
{#if showCollectionModal}
  <div class="pm-modal-backdrop" role="presentation" on:click|self={() => (showCollectionModal = false)}>
    <div class="pm-modal sm" role="dialog" aria-modal="true" aria-labelledby="col-modal-title">
      <div class="pm-modal-head">
        <h3 id="col-modal-title">
          {collectionModalMode === "create" ? "สร้าง API Collection ใหม่" : "ตั้งค่า API Collection"}
        </h3>
        <button type="button" class="pm-modal-close" on:click={() => (showCollectionModal = false)} aria-label="ปิด">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
      <div class="pm-modal-body">
        <div class="pm-field">
          <label for="col-m-name">ชื่อ Collection</label>
          <input
            id="col-m-name"
            type="text"
            class="pm-input"
            placeholder="เช่น Payment API v2"
            bind:value={colModalName}
          />
        </div>
        <div class="pm-field">
          <label for="col-m-base">Base URL (ทางเลือก)</label>
          <input
            id="col-m-base"
            type="text"
            class="pm-input mono"
            placeholder="https://api.example.com"
            bind:value={colModalBaseUrl}
          />
        </div>
        <div class="pm-field">
          <label for="col-m-ver">Version</label>
          <input id="col-m-ver" type="text" class="pm-input" bind:value={colModalVersion} />
        </div>
      </div>
      <div class="pm-modal-foot">
        <button type="button" class="pm-tool-btn" on:click={() => (showCollectionModal = false)}>ยกเลิก</button>
        <button
          type="button"
          class="pm-btn-primary-sm"
          disabled={isSavingCollection}
          on:click={saveCollectionModal}
        >
          {isSavingCollection ? "กำลังบันทึก..." : "บันทึก"}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- =========================================================================
     MODAL: IMPORT (OpenAPI / Swagger / Postman File OR Raw cURL)
     ========================================================================= -->
{#if showImportModal}
  <div class="pm-modal-backdrop" role="presentation" on:click|self={() => (showImportModal = false)}>
    <div class="pm-modal md" role="dialog" aria-modal="true" aria-labelledby="import-modal-title">
      <div class="pm-modal-head">
        <h3 id="import-modal-title">นำเข้า API (Import Spec หรือ cURL)</h3>
        <button type="button" class="pm-modal-close" on:click={() => (showImportModal = false)} aria-label="ปิด">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
      <div class="pm-modal-body">
        <div class="pm-segmented full">
          <button
            type="button"
            class:active={importModalTab === "file"}
            on:click={() => (importModalTab = "file")}
          >
            ไฟล์ OpenAPI / Swagger / Postman
          </button>
          <button
            type="button"
            class:active={importModalTab === "curl"}
            on:click={() => (importModalTab = "curl")}
          >
            วางคำสั่ง cURL (Raw Text)
          </button>
        </div>

        {#if importModalTab === "file"}
          <input
            id="pm-spec-file-input"
            type="file"
            accept=".json,.yaml,.yml"
            bind:this={fileInput}
            on:change={handleFileChange}
            class="sr-only-input"
          />
          <button
            type="button"
            class="pm-dropzone"
            class:drag-over={isDragOver}
            class:has-file={uploadFile !== null}
            on:click={() => fileInput.click()}
            on:dragover|preventDefault={() => (isDragOver = true)}
            on:dragleave|preventDefault={() => (isDragOver = false)}
            on:drop={handleFileDrop}
          >
            {#if uploadFile}
              <div class="pm-file-selected">
                <strong>{uploadFile.name}</strong>
                <span>{(uploadFile.size / 1024).toFixed(1)} KB • พร้อมนำเข้า</span>
              </div>
            {:else}
              <p>คลิกเลือกไฟล์ หรือลากไฟล์ <code>.json</code> / <code>.yaml</code> มาวางที่นี่</p>
              <span>รองรับ OpenAPI 3.0, Swagger 2.0 และ Postman Collection v2.1</span>
            {/if}
          </button>

          <div class="pm-field">
            <label for="imp-col-name">ตั้งชื่อ Collection (ทางเลือก)</label>
            <input
              id="imp-col-name"
              type="text"
              class="pm-input"
              placeholder="เว้นว่างเพื่อใช้ชื่อจากไฟล์ Spec"
              bind:value={customImportName}
            />
          </div>
        {:else}
          <div class="pm-segmented full">
            <button
              type="button"
              class:active={importCurlTarget === "active"}
              on:click={() => (importCurlTarget = "active")}
            >
              เติมลงแท็บปัจจุบัน
            </button>
            <button
              type="button"
              class:active={importCurlTarget === "new"}
              on:click={() => (importCurlTarget = "new")}
            >
              เปิดเป็นแท็บใหม่
            </button>
          </div>
          <div class="pm-field">
            <label for="imp-curl-area">วางคำสั่ง cURL จาก Chrome DevTools หรือ Postman</label>
            <textarea
              id="imp-curl-area"
              rows="6"
              class="pm-input mono"
              placeholder={'curl -X POST "https://api.example.com/v1/login" -H "Content-Type: application/json" -d \'{"username":"admin"}\''}
              bind:value={importCurlText}
            ></textarea>
          </div>
        {/if}
      </div>
      <div class="pm-modal-foot">
        <button type="button" class="pm-tool-btn" on:click={() => (showImportModal = false)}>ยกเลิก</button>
        {#if importModalTab === "file"}
          <button
            type="button"
            class="pm-btn-primary-sm"
            disabled={!uploadFile || isUploading}
            on:click={handleUploadSpec}
          >
            {isUploading ? "กำลังนำเข้า..." : "นำเข้าไฟล์ Spec"}
          </button>
        {:else}
          <button type="button" class="pm-btn-primary-sm" on:click={handleImportCurlSubmit}>
            {importCurlTarget === "active" ? "แยกข้อมูลลงแท็บปัจจุบัน" : "นำเข้าและเปิดในแท็บใหม่"}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- =========================================================================
     MODAL: WEB API DISCOVERY (SNIFFER)
     ========================================================================= -->
{#if showSnifferModal}
  <div class="pm-modal-backdrop" role="presentation" on:click|self={() => (showSnifferModal = false)}>
    <div class="pm-modal lg" role="dialog" aria-modal="true" aria-labelledby="sniffer-modal-title">
      <div class="pm-modal-head">
        <h3 id="sniffer-modal-title">Web API Discovery (OpenAPI / Route Sniffer)</h3>
        <button type="button" class="pm-modal-close" on:click={() => (showSnifferModal = false)} aria-label="ปิด">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div class="pm-modal-body">
        <div class="pm-sniffer-bar">
          <input
            type="text"
            aria-label="Target URL สำหรับสำรวจ API"
            class="pm-input mono"
            placeholder="https://api.example.com หรือ http://127.0.0.1:5000"
            bind:value={snifferUrl}
            on:keydown={(e) => e.key === "Enter" && handleStartSniffing()}
          />
          <button
            type="button"
            class="pm-btn-primary-sm"
            disabled={isSniffing || !snifferUrl.trim()}
            on:click={handleStartSniffing}
          >
            {isSniffing ? "กำลังสแกน..." : "เริ่มสำรวจ API"}
          </button>
        </div>

        <button
          type="button"
          class="pm-link-btn align-left"
          on:click={() => (snifferShowAuth = !snifferShowAuth)}
        >
          {snifferShowAuth ? "ซ่อนข้อมูลเข้าสู่ระบบ (Optional Auth)" : "+ เพิ่ม Username / Password หากระบบเป้าหมายต้องล็อกอิน"}
        </button>

        {#if snifferShowAuth}
          <div class="pm-form-grid-2">
            <div class="pm-field">
              <label for="sniff-user">Username (ทางเลือก)</label>
              <input id="sniff-user" type="text" class="pm-input" bind:value={snifferUsername} />
            </div>
            <div class="pm-field">
              <label for="sniff-pass">Password (ทางเลือก)</label>
              <input id="sniff-pass" type="password" class="pm-input" bind:value={snifferPassword} />
            </div>
          </div>
        {/if}

        {#if sniffedEndpoints.length > 0}
          <div class="pm-sniffer-toolbar">
            <label class="pm-chk-label">
              <input
                type="checkbox"
                checked={selectedSniffedIndices.size === sniffedEndpoints.length}
                on:change={toggleAllSniffed}
              />
              <span>เลือกทั้งหมด ({selectedSniffedIndices.size}/{sniffedEndpoints.length})</span>
            </label>
            <div class="pm-segmented compact">
              <button
                type="button"
                class:active={snifferImportMode === "new"}
                on:click={() => (snifferImportMode = "new")}
              >
                สร้างชุดใหม่
              </button>
              <button
                type="button"
                class:active={snifferImportMode === "append"}
                disabled={collections.length === 0}
                on:click={() => (snifferImportMode = "append")}
              >
                เพิ่มเข้าชุดเดิม
              </button>
            </div>
          </div>

          {#if snifferImportMode === "new"}
            <div class="pm-field">
              <label for="sniff-col-name">ชื่อ Collection ใหม่</label>
              <input
                id="sniff-col-name"
                type="text"
                class="pm-input"
                placeholder="ตั้งชื่อ Collection ใหม่..."
                bind:value={snifferCollectionName}
              />
            </div>
          {:else}
            <div class="pm-field">
              <label for="sniff-target-col">เลือก Collection ปลายทาง</label>
              <CustomSelect
                id="sniff-target-col"
                ariaLabel="เลือก Collection ปลายทางสำหรับบันทึกผล Sniffer"
                variant="compact"
                size="md"
                options={collectionSelectOptions}
                bind:value={snifferTargetCollectionId}
                minWidth="100%"
              />
            </div>
          {/if}

          <div class="pm-sniffer-list">
            {#each sniffedEndpoints as ep, idx}
              <label class="pm-sniffer-item">
                <input
                  type="checkbox"
                  checked={selectedSniffedIndices.has(idx)}
                  on:change={() => toggleSniffedSelection(idx)}
                />
                <span class="pm-verb" style="color: {verbColor(ep.method)};">
                  {formatVerb(ep.method)}
                </span>
                <span class="mono">{ep.path || ep.url}</span>
              </label>
            {/each}
          </div>
        {:else}
          <div class="pm-side-empty">
            <p>
              กรอก URL ของระบบเป้าหมายแล้วกด <strong>เริ่มสำรวจ API</strong> เพื่อค้นหา
              <code>/openapi.json</code>, <code>/swagger.json</code> และ API routes อัตโนมัติ
            </p>
          </div>
        {/if}
      </div>

      <div class="pm-modal-foot">
        <button type="button" class="pm-tool-btn" on:click={() => (showSnifferModal = false)}>ปิด</button>
        {#if sniffedEndpoints.length > 0}
          <button
            type="button"
            class="pm-btn-primary-sm"
            disabled={isSniffing || selectedSniffedIndices.size === 0}
            on:click={handleSaveSniffed}
          >
            บันทึกที่เลือก ({selectedSniffedIndices.size})
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Chrome Extension Live Sync Modal -->
<ExtensionSyncModal
  bind:show={showExtensionModal}
  {selectedProject}
  {collections}
  on:close={() => (showExtensionModal = false)}
  on:imported={() => loadCollections()}
/>

<style>
  .pm-shell {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 70px);
    width: 100%;
    background-color: transparent;
    color: var(--text-main, #f8fafc);
    font-family: var(--font-th, "Prompt", sans-serif);
    overflow: hidden;
  }

  .pm-shell.resizing {
    user-select: none;
    cursor: row-resize;
  }

  .mono {
    font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
  }

  .sr-only-input {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
  }

  code {
    font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
    font-size: 0.9em;
    padding: 1px 5px;
    border-radius: 8px;
    background-color: rgba(255, 255, 255, 0.07);
    color: #c7d2fe;
  }

  /* ── Top Workspace Bar (Spectra Frosted Obsidian) ── */
  .pm-topbar {
    min-height: 54px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 16px;
    background-color: rgba(18, 20, 28, 0.72);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .pm-topbar-left,
  .pm-topbar-right {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .pm-picker-group {
    display: flex;
    align-items: center;
    gap: 7px;
  }

  .pm-field-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #94a3b8);
    white-space: nowrap;
  }

  .pm-project-select-wrap {
    width: 210px;
  }

  .pm-env-select-wrap {
    width: 210px;
  }

  .pm-divider-v {
    width: 1px;
    height: 22px;
    background-color: rgba(255, 255, 255, 0.09);
  }

  .pm-telemetry-summary {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .pm-stat-chip {
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 4px 9px;
    border-radius: 8px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .pm-stat-chip strong {
    color: var(--text-main, #f8fafc);
    font-weight: 600;
    margin-right: 3px;
  }

  .pm-error-pill {
    font-size: 12px;
    color: #fda4af;
    background-color: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.35);
    padding: 4px 10px;
    border-radius: 8px;
    cursor: pointer;
  }

  .pm-tool-group {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .pm-icon-btn {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background-color: rgba(255, 255, 255, 0.04);
    color: var(--text-muted, #94a3b8);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }

  .pm-icon-btn:hover {
    background-color: rgba(255, 255, 255, 0.09);
    color: var(--text-main, #f8fafc);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .pm-tool-btn {
    height: 34px;
    padding: 0 11px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.11);
    background-color: rgba(255, 255, 255, 0.04);
    color: var(--text-main, #f8fafc);
    font-size: 12.5px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .pm-tool-btn:hover:not(:disabled) {
    background-color: rgba(255, 255, 255, 0.09);
    border-color: rgba(255, 255, 255, 0.22);
  }

  .pm-tool-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  /* Secondary Accent CTA (leaves Send as the sole primary gradient hero) */
  .pm-btn-secondary-accent {
    height: 34px;
    padding: 0 12px;
    border-radius: 8px;
    border: 1px solid rgba(99, 102, 241, 0.48);
    background-color: rgba(99, 102, 241, 0.16);
    color: #e0e7ff;
    font-size: 12.5px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .pm-btn-secondary-accent:hover {
    background-color: rgba(99, 102, 241, 0.28);
    border-color: rgba(129, 140, 248, 0.72);
  }

  /* Primary Gradient Button (Modals only) */
  .pm-btn-primary-sm {
    height: 36px;
    padding: 0 16px;
    border-radius: 8px;
    border: none;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: #ffffff;
    font-size: 12.5px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
    transition: filter 0.15s ease;
  }

  .pm-btn-primary-sm:hover:not(:disabled) {
    filter: brightness(1.08);
  }

  .pm-btn-primary-sm:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  /* ── 2-Pane Split Body ── */
  .pm-body {
    flex: 1;
    min-height: 0;
    display: flex;
    overflow: hidden;
  }

  /* ── Left Sidebar (Frosted Explorer) ── */
  .pm-sidebar {
    width: 304px;
    flex-shrink: 0;
    background-color: rgba(16, 18, 26, 0.78);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .pm-sidebar-tabs {
    display: flex;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 0 8px;
  }

  .pm-side-tab {
    flex: 1;
    height: 40px;
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted, #94a3b8);
    font-size: 12.5px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    cursor: pointer;
    transition: color 0.15s ease, border-color 0.15s ease;
  }

  .pm-side-tab:hover {
    color: var(--text-main, #f8fafc);
  }

  .pm-side-tab.active {
    color: #c7d2fe;
    border-bottom-color: #6366f1;
    font-weight: 600;
  }

  .pm-sidebar-controls {
    padding: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .pm-search-row {
    display: flex;
    gap: 6px;
  }

  .pm-search-input-wrap {
    flex: 1;
    position: relative;
    display: flex;
    align-items: center;
    background-color: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 0 8px;
    color: var(--text-muted, #94a3b8);
  }

  .pm-search-input-wrap:focus-within {
    border-color: #6366f1;
  }

  .pm-search-input-wrap input {
    width: 100%;
    height: 32px;
    background-color: transparent;
    border: none;
    outline: none;
    color: var(--text-main, #f8fafc);
    font-size: 12.5px;
    padding: 0 6px;
  }

  .pm-search-input-wrap input::placeholder {
    color: #8494aa;
  }

  .pm-clear-x {
    width: 24px;
    height: 24px;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: var(--text-muted, #94a3b8);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .pm-clear-x:hover {
    color: #ffffff;
  }

  .pm-new-col-btn {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    border: 1px solid rgba(99, 102, 241, 0.4);
    background-color: rgba(99, 102, 241, 0.14);
    color: #c7d2fe;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.15s ease;
  }

  .pm-new-col-btn:hover:not(:disabled) {
    background-color: rgba(99, 102, 241, 0.28);
  }

  .pm-new-col-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .pm-tree-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 6px;
  }

  .pm-col-node {
    margin-bottom: 3px;
  }

  .pm-tree-item-wrap {
    display: flex;
    align-items: center;
    gap: 2px;
    border-radius: 8px;
    position: relative;
    transition: background-color 0.14s ease;
  }

  .pm-tree-item-wrap:hover,
  .pm-tree-item-wrap:focus-within {
    background-color: rgba(255, 255, 255, 0.05);
  }

  .pm-ep-wrap.active {
    background-color: rgba(99, 102, 241, 0.2);
  }

  .pm-col-trigger,
  .pm-cat-trigger,
  .pm-ep-trigger {
    flex: 1;
    min-width: 0;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 7px;
    text-align: left;
    cursor: pointer;
    color: var(--text-main, #f8fafc);
  }

  .pm-col-trigger {
    padding: 7px 8px;
    font-size: 13px;
    font-weight: 500;
  }

  .pm-cat-trigger {
    padding: 5px 8px;
    font-size: 12px;
    font-weight: 500;
    color: #cbd5e1;
  }

  .pm-ep-trigger {
    padding: 6px 8px;
    font-size: 12.5px;
    color: #cbd5e1;
  }

  .pm-ep-wrap.active .pm-ep-trigger {
    color: #ffffff;
    font-weight: 500;
  }

  .pm-chevron {
    color: var(--text-muted, #94a3b8);
    display: inline-flex;
    transition: transform 0.16s ease;
    flex-shrink: 0;
  }

  .pm-chevron.open {
    transform: rotate(90deg);
    color: #a5b4fc;
  }

  .pm-folder-ico {
    color: #a5b4fc;
    flex-shrink: 0;
  }

  .pm-sub-folder-ico {
    color: #94a3b8;
    flex-shrink: 0;
  }

  .pm-col-title,
  .pm-cat-name,
  .pm-ep-label {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pm-col-count {
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
    font-variant-numeric: tabular-nums;
    padding-right: 4px;
  }

  /* Accessible Row Actions (Visible on Hover, Keyboard Focus, Active, and Touch) */
  .pm-row-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 2px 4px 2px 0;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.12s ease;
  }

  .pm-tree-item-wrap:hover .pm-row-actions,
  .pm-tree-item-wrap:focus-within .pm-row-actions,
  .pm-ep-wrap.active .pm-row-actions {
    opacity: 1;
    pointer-events: auto;
  }

  @media (hover: none), (pointer: coarse) {
    .pm-row-actions {
      opacity: 1;
      pointer-events: auto;
    }
  }

  .pm-mini-ico {
    width: 26px;
    height: 26px;
    border-radius: 8px;
    border: none;
    background-color: transparent;
    color: var(--text-muted, #94a3b8);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: background-color 0.12s ease, color 0.12s ease;
  }

  .pm-mini-ico:hover {
    background-color: rgba(255, 255, 255, 0.11);
    color: var(--text-main, #f8fafc);
  }

  .pm-mini-ico.danger:hover {
    background-color: rgba(244, 63, 94, 0.22);
    color: #fda4af;
  }

  .pm-ep-children {
    padding-left: 14px;
    margin-top: 2px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .pm-cat-items {
    padding-left: 14px;
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .pm-ep-add-inline {
    background-color: transparent;
    border: 1px dashed rgba(255, 255, 255, 0.16);
    border-radius: 8px;
    color: var(--text-muted, #94a3b8);
    font-size: 12px;
    padding: 7px 10px;
    text-align: left;
    cursor: pointer;
    margin: 4px 0;
  }

  .pm-ep-add-inline:hover {
    border-color: rgba(99, 102, 241, 0.55);
    color: #c7d2fe;
  }

  .pm-verb {
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.02em;
    min-width: 40px;
    text-align: left;
    flex-shrink: 0;
  }

  /* History List */
  .pm-history-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .pm-hist-row {
    width: 100%;
    text-align: left;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 4px;
    color: var(--text-main, #f8fafc);
  }

  .pm-hist-row:hover {
    background-color: rgba(255, 255, 255, 0.05);
  }

  .pm-hist-top {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .pm-hist-url {
    font-size: 12px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pm-hist-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: var(--text-muted, #94a3b8);
    font-variant-numeric: tabular-nums;
    padding-left: 46px;
  }

  .pm-hist-status.ok {
    color: #34d399;
    font-weight: 600;
  }
  .pm-hist-status.err {
    color: #fb7185;
    font-weight: 600;
  }

  .pm-side-empty {
    padding: 28px 16px;
    text-align: center;
    color: var(--text-muted, #94a3b8);
    font-size: 12.5px;
    line-height: 1.6;
  }

  .pm-empty-actions {
    margin-top: 12px;
    display: flex;
    gap: 8px;
    justify-content: center;
  }

  .pm-btn-ghost-sm {
    height: 32px;
    padding: 0 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background-color: rgba(255, 255, 255, 0.04);
    color: var(--text-main, #f8fafc);
    font-size: 12px;
    cursor: pointer;
  }

  .pm-btn-ghost-sm:hover {
    border-color: #6366f1;
    color: #c7d2fe;
  }

  .pm-skeleton-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px;
  }

  .pm-skel-row {
    height: 28px;
    border-radius: 8px;
    background-color: rgba(255, 255, 255, 0.05);
    animation: pmPulse 1.4s ease-in-out infinite;
  }

  .pm-skel-row.short {
    width: 72%;
    margin-left: 16px;
  }

  /* ── Right Main Workbench ── */
  .pm-workbench {
    flex: 1;
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background-color: rgba(10, 11, 18, 0.72);
  }

  /* Multi-Tab Bar */
  .pm-tabbar {
    height: 40px;
    flex-shrink: 0;
    background-color: rgba(13, 15, 23, 0.85);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: stretch;
  }

  .pm-tabs-scroll {
    display: flex;
    align-items: stretch;
    overflow-x: auto;
    flex: 1;
  }

  .pm-tab-wrap {
    display: flex;
    align-items: center;
    min-width: 148px;
    max-width: 230px;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    border-top: 2px solid transparent;
    flex-shrink: 0;
    padding-right: 6px;
    transition: background-color 0.14s ease;
  }

  .pm-tab-wrap:hover {
    background-color: rgba(255, 255, 255, 0.03);
  }

  .pm-tab-wrap.active {
    background-color: rgba(10, 11, 18, 0.95);
    border-top-color: #6366f1;
  }

  .pm-tab-trigger {
    flex: 1;
    min-width: 0;
    height: 100%;
    padding: 0 6px 0 12px;
    background-color: transparent;
    border: none;
    display: flex;
    align-items: center;
    gap: 7px;
    color: var(--text-muted, #94a3b8);
    font-size: 12.5px;
    cursor: pointer;
    text-align: left;
  }

  .pm-tab-wrap.active .pm-tab-trigger {
    color: #ffffff;
  }

  .pm-tab-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .pm-dirty-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background-color: #fbbf24;
    flex-shrink: 0;
  }

  .pm-tab-close {
    width: 24px;
    height: 24px;
    border-radius: 8px;
    border: none;
    background-color: transparent;
    color: var(--text-muted, #94a3b8);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
  }

  .pm-tab-close:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }

  .pm-tab-add {
    width: 38px;
    border: none;
    background-color: transparent;
    color: var(--text-muted, #94a3b8);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
  }

  .pm-tab-add:hover {
    color: #ffffff;
    background-color: rgba(255, 255, 255, 0.06);
  }

  /* Request Identity Header */
  .pm-req-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 16px 6px;
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .pm-req-identity {
    display: flex;
    align-items: center;
    gap: 7px;
    flex: 1;
    min-width: 220px;
  }

  .pm-crumb {
    font-size: 12px;
    color: #c7d2fe;
    background-color: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    padding: 2px 8px;
    border-radius: 8px;
    white-space: nowrap;
  }

  .pm-crumb.cat {
    color: #cbd5e1;
    background-color: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
  }

  .pm-crumb.draft {
    color: var(--text-muted, #94a3b8);
    background-color: rgba(255, 255, 255, 0.04);
    border-color: rgba(255, 255, 255, 0.08);
  }

  .pm-crumb-sep {
    color: #8494aa;
  }

  .pm-req-name-input {
    flex: 1;
    min-width: 140px;
    max-width: 420px;
    height: 32px;
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: var(--text-main, #f8fafc);
    font-size: 14px;
    font-weight: 600;
    padding: 0 8px;
    outline: none;
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .pm-req-name-input:hover {
    border-color: rgba(255, 255, 255, 0.12);
  }

  .pm-req-name-input:focus {
    background-color: #12141c;
    border-color: #6366f1;
  }

  .pm-req-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .pm-subtle-btn {
    height: 32px;
    padding: 0 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background-color: rgba(255, 255, 255, 0.03);
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.14s ease, color 0.14s ease;
  }

  .pm-subtle-btn:hover {
    background-color: rgba(255, 255, 255, 0.09);
    color: #ffffff;
  }

  .pm-save-btn {
    height: 32px;
    padding: 0 12px;
    border-radius: 8px;
    border: 1px solid rgba(99, 102, 241, 0.45);
    background-color: rgba(99, 102, 241, 0.16);
    color: #e0e7ff;
    font-size: 12.5px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    transition: background-color 0.14s ease;
  }

  .pm-save-btn:hover:not(:disabled) {
    background-color: rgba(99, 102, 241, 0.28);
  }

  .pm-save-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  /* Postman Hero URL Bar (DESIGN.md 12px radius) */
  .pm-url-bar-row {
    display: flex;
    align-items: stretch;
    gap: 10px;
    padding: 6px 16px 12px;
    flex-shrink: 0;
  }

  .pm-url-bar {
    flex: 1;
    min-width: 0;
    height: 44px;
    display: flex;
    align-items: center;
    background-color: #12141c;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 12px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  .pm-url-bar:focus-within {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
  }

  .pm-method-wrap {
    height: 100%;
    flex-shrink: 0;
    display: flex;
    align-items: stretch;
  }

  .pm-url-sep {
    width: 1px;
    height: 22px;
    background-color: rgba(255, 255, 255, 0.11);
  }

  .pm-url-input {
    flex: 1;
    min-width: 0;
    height: 100%;
    background-color: transparent;
    border: none;
    outline: none;
    color: var(--text-main, #f8fafc);
    font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
    font-size: 13px;
    padding: 0 14px;
  }

  .pm-url-input::placeholder {
    font-family: var(--font-th, "Prompt", sans-serif);
    color: #8494aa;
    font-size: 12.5px;
  }

  .pm-base-pill {
    margin-right: 10px;
    padding: 3px 8px;
    border-radius: 8px;
    background-color: rgba(6, 182, 212, 0.14);
    border: 1px solid rgba(6, 182, 212, 0.35);
    color: #67e8f9;
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
    white-space: nowrap;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .pm-send-btn {
    height: 44px;
    min-width: 112px;
    padding: 0 22px;
    border-radius: 12px;
    border: none;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    color: #ffffff;
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 14px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
    transition: filter 0.15s ease, transform 0.15s ease;
  }

  .pm-send-btn.canceling {
    background: linear-gradient(135deg, #be123c, #e11d48);
    box-shadow: 0 4px 14px rgba(244, 63, 94, 0.35);
  }

  .pm-send-btn:hover:not(:disabled) {
    filter: brightness(1.08);
    transform: translateY(-1px);
  }

  .pm-send-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    transform: none;
  }

  /* Request Config Pane */
  .pm-request-pane {
    flex: 1;
    min-height: 160px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .pm-subtabs {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 0 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
  }

  .pm-subtab {
    height: 36px;
    padding: 0 12px;
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted, #94a3b8);
    font-size: 12.5px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    transition: color 0.14s ease, border-color 0.14s ease;
  }

  .pm-subtab:hover {
    color: var(--text-main, #f8fafc);
  }

  .pm-subtab.active {
    color: #ffffff;
    border-bottom-color: #6366f1;
    font-weight: 600;
  }

  .pm-badge-count {
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 11px;
    font-weight: 600;
    color: #c7d2fe;
    background-color: rgba(99, 102, 241, 0.2);
    padding: 1px 7px;
    border-radius: 8px;
    font-variant-numeric: tabular-nums;
  }

  .pm-active-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background-color: #10b981;
  }

  .pm-req-content {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  /* Key-Value Table (12px radius) */
  .pm-kv-table {
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
    overflow: hidden;
    background-color: #0e1018;
  }

  .pm-kv-head,
  .pm-kv-row {
    display: grid;
    grid-template-columns: 40px 1fr 1.3fr 40px;
    align-items: center;
  }

  .pm-kv-head {
    background-color: #141722;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    height: 32px;
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    color: var(--text-muted, #94a3b8);
  }

  .pm-kv-head span {
    padding: 0 10px;
  }

  .pm-kv-row {
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    min-height: 36px;
  }

  .pm-kv-row:last-child {
    border-bottom: none;
  }

  .pm-kv-row.disabled {
    opacity: 0.5;
  }

  .col-chk,
  .col-act {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pm-cell-input {
    width: 100%;
    height: 36px;
    background-color: transparent;
    border: none;
    border-left: 1px solid rgba(255, 255, 255, 0.05);
    color: var(--text-main, #f8fafc);
    font-size: 12.5px;
    padding: 0 10px;
    outline: none;
  }

  .pm-cell-input:focus {
    background-color: rgba(99, 102, 241, 0.08);
  }

  .pm-cell-input::placeholder {
    color: #8494aa;
  }

  .pm-row-del {
    width: 26px;
    height: 26px;
    border-radius: 8px;
    border: none;
    background-color: transparent;
    color: #8494aa;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .pm-row-del:hover {
    color: #fda4af;
    background-color: rgba(244, 63, 94, 0.18);
  }

  /* Auth Layout + Secret Eye Toggle */
  .pm-auth-split {
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: 20px;
    align-items: start;
  }

  .pm-auth-left {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-right: 16px;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
  }

  .pm-auth-left label,
  .pm-field label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted, #94a3b8);
  }

  .pm-auth-hint {
    font-size: 12px;
    color: #8494aa;
    line-height: 1.5;
  }

  .pm-secret-wrap {
    position: relative;
    display: flex;
    align-items: center;
  }

  .pm-secret-wrap .pm-input {
    padding-right: 38px;
  }

  .pm-eye-btn {
    position: absolute;
    right: 6px;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    border: none;
    background-color: transparent;
    color: #94a3b8;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .pm-eye-btn:hover {
    color: #ffffff;
    background-color: rgba(255, 255, 255, 0.08);
  }

  .pm-auth-empty,
  .pm-body-empty {
    padding: 24px;
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    color: var(--text-muted, #94a3b8);
    font-size: 13px;
    text-align: center;
  }

  .pm-inline-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .pm-radio-group {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .pm-radio-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.09);
    background-color: rgba(255, 255, 255, 0.02);
    color: var(--text-muted, #94a3b8);
    font-size: 12px;
    cursor: pointer;
  }

  .pm-radio-pill.active {
    background-color: rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.45);
    color: #e0e7ff;
  }

  .pm-radio-pill input {
    accent-color: #6366f1;
  }

  .pm-body-tools {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .pm-json-badge {
    font-size: 11.5px;
    font-weight: 600;
    color: #6ee7b7;
    background-color: rgba(16, 185, 129, 0.15);
    padding: 3px 9px;
    border-radius: 8px;
  }

  .pm-json-badge.invalid {
    color: #fda4af;
    background-color: rgba(244, 63, 94, 0.18);
  }

  .pm-inline-error {
    font-family: "JetBrains Mono", monospace;
    font-size: 12px;
    color: #fda4af;
    background-color: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.3);
    border-radius: 8px;
    padding: 7px 11px;
  }

  .pm-link-btn {
    background-color: transparent;
    border: none;
    color: #a5b4fc;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }

  .pm-link-btn.align-left {
    align-self: flex-start;
  }

  .pm-link-btn:hover {
    color: #c7d2fe;
    text-decoration: underline;
  }

  .pm-code-editor {
    flex: 1;
    min-height: 130px;
    width: 100%;
    background-color: #0e1018;
    border: 1px solid rgba(255, 255, 255, 0.11);
    border-radius: 12px;
    padding: 12px;
    color: #e2e8f0;
    font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
    font-size: 12.5px;
    line-height: 1.55;
    resize: vertical;
    outline: none;
  }

  .pm-code-editor:focus {
    border-color: #6366f1;
  }

  .pm-segmented {
    display: inline-flex;
    background-color: #12141c;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 3px;
    gap: 2px;
  }

  .pm-segmented.full {
    display: flex;
    width: 100%;
  }

  .pm-segmented.full button {
    flex: 1;
  }

  .pm-segmented button {
    height: 28px;
    padding: 0 11px;
    border: none;
    border-radius: 8px;
    background-color: transparent;
    color: var(--text-muted, #94a3b8);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
  }

  .pm-segmented button.active {
    background-color: rgba(99, 102, 241, 0.25);
    color: #ffffff;
    font-weight: 600;
  }

  .pm-segmented button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .pm-segmented.compact button {
    height: 24px;
    padding: 0 8px;
    font-size: 11.5px;
  }

  /* Splitter */
  .pm-splitter {
    height: 8px;
    flex-shrink: 0;
    background-color: #0f111a;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: row-resize;
    transition: background-color 0.14s ease;
  }

  .pm-splitter:hover,
  .pm-splitter:focus-visible {
    background-color: rgba(99, 102, 241, 0.24);
  }

  .pm-splitter-grip {
    width: 36px;
    height: 3px;
    border-radius: 999px;
    background-color: rgba(255, 255, 255, 0.24);
  }

  /* Response Pane */
  .pm-response-pane {
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background-color: rgba(12, 13, 21, 0.9);
    min-height: 170px;
    overflow: hidden;
  }

  .pm-res-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .pm-res-tabs,
  .pm-res-meta {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .pm-status-badge {
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 12px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 8px;
    font-variant-numeric: tabular-nums;
  }

  .pm-status-badge.ok {
    color: #6ee7b7;
    background-color: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.35);
  }

  .pm-status-badge.redir {
    color: #67e8f9;
    background-color: rgba(6, 182, 212, 0.16);
    border: 1px solid rgba(6, 182, 212, 0.38);
  }

  .pm-status-badge.warn {
    color: #fcd34d;
    background-color: rgba(245, 158, 11, 0.16);
    border: 1px solid rgba(245, 158, 11, 0.35);
  }

  .pm-status-badge.err {
    color: #fda4af;
    background-color: rgba(244, 63, 94, 0.16);
    border: 1px solid rgba(244, 63, 94, 0.35);
  }

  .pm-metric {
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    font-variant-numeric: tabular-nums;
  }

  .pm-mini-copy,
  .pm-floating-copy {
    height: 26px;
    padding: 0 10px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.13);
    background-color: rgba(255, 255, 255, 0.05);
    color: #e2e8f0;
    font-size: 11.5px;
    cursor: pointer;
  }

  .pm-mini-copy:hover,
  .pm-floating-copy:hover {
    background-color: rgba(99, 102, 241, 0.24);
    border-color: rgba(99, 102, 241, 0.5);
  }

  .pm-res-content {
    flex: 1;
    min-height: 0;
    overflow: auto;
    padding: 12px 16px;
  }

  .pm-code-wrap {
    position: relative;
  }

  .pm-floating-copy {
    position: absolute;
    top: 8px;
    right: 8px;
  }

  .pm-response-pre {
    margin: 0;
    font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
    font-size: 12.5px;
    line-height: 1.6;
    color: #e2e8f0;
    white-space: pre-wrap;
    word-break: break-word;
    background-color: #10121b;
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 12px;
    padding: 12px 14px;
  }

  .pm-res-state {
    height: 100%;
    min-height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: var(--text-muted, #94a3b8);
    font-size: 13px;
    text-align: center;
  }

  .pm-res-idle-title {
    color: #cbd5e1;
    font-weight: 500;
  }

  .pm-shortcuts-row {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
    justify-content: center;
    font-size: 12px;
    color: #8494aa;
  }

  kbd {
    font-family: var(--font-en, "Outfit", sans-serif);
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 8px;
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.14);
    color: #e2e8f0;
  }

  .pm-res-error {
    background-color: rgba(244, 63, 94, 0.09);
    border: 1px solid rgba(244, 63, 94, 0.32);
    border-radius: 12px;
    padding: 14px 16px;
    color: #fda4af;
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 13px;
  }

  .pm-res-error-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .pm-res-url {
    font-family: "JetBrains Mono", monospace;
    font-size: 12px;
    color: #cbd5e1;
  }

  .pm-res-headers-table {
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    overflow: hidden;
  }

  .pm-res-h-row {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 12px;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    font-family: "JetBrains Mono", monospace;
    font-size: 12px;
  }

  .pm-res-h-row:last-child {
    border-bottom: none;
  }

  .pm-res-h-row .h-key {
    color: #a5b4fc;
    font-weight: 600;
    word-break: break-all;
  }

  .pm-res-h-row .h-val {
    color: #e2e8f0;
    word-break: break-all;
  }

  /* Shared Form Inputs */
  .pm-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .pm-input {
    width: 100%;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.13);
    background-color: #12141c;
    color: var(--text-main, #f8fafc);
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s ease;
  }

  .pm-input:focus {
    border-color: #6366f1;
  }

  .pm-form-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .pm-form-grid-3 {
    display: grid;
    grid-template-columns: 1fr 1.4fr 155px;
    gap: 10px;
  }

  .pm-settings-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 760px;
  }

  /* Secondary Modals (DESIGN.md 20px radius + Frosted Glass) */
  .pm-modal-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(5, 5, 10, 0.72);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    z-index: var(--z-modal, 10000);
  }

  .pm-modal {
    width: 100%;
    background-color: rgba(18, 20, 28, 0.94);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-radius: 20px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.62);
    display: flex;
    flex-direction: column;
    max-height: 86vh;
    overflow: hidden;
  }

  .pm-modal.sm {
    max-width: 460px;
  }
  .pm-modal.md {
    max-width: 580px;
  }
  .pm-modal.lg {
    max-width: 720px;
  }

  .pm-modal-head {
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .pm-modal-head h3 {
    font-size: 16px;
    font-weight: 600;
    color: #f8fafc;
  }

  .pm-modal-close {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    border: none;
    background-color: transparent;
    color: var(--text-muted, #94a3b8);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .pm-modal-close:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
  }

  .pm-modal-body {
    padding: 18px 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .pm-modal-foot {
    padding: 14px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }

  .pm-dropzone {
    width: 100%;
    border: 1.5px dashed rgba(255, 255, 255, 0.18);
    border-radius: 12px;
    padding: 28px 20px;
    text-align: center;
    cursor: pointer;
    background-color: rgba(255, 255, 255, 0.02);
    color: inherit;
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .pm-dropzone:hover,
  .pm-dropzone.drag-over {
    border-color: #6366f1;
    background-color: rgba(99, 102, 241, 0.08);
  }

  .pm-dropzone.has-file {
    border-color: #10b981;
    background-color: rgba(16, 185, 129, 0.08);
  }

  .pm-dropzone p {
    font-size: 13.5px;
    font-weight: 500;
    color: #f8fafc;
    margin-bottom: 4px;
  }

  .pm-dropzone span {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
  }

  .pm-file-selected {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .pm-sniffer-bar {
    display: flex;
    gap: 10px;
  }

  .pm-sniffer-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .pm-chk-label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: #e2e8f0;
    cursor: pointer;
  }

  .pm-sniffer-list {
    max-height: 260px;
    overflow-y: auto;
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .pm-sniffer-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 8px;
    font-size: 12.5px;
    cursor: pointer;
  }

  .pm-sniffer-item:hover {
    background-color: rgba(255, 255, 255, 0.05);
  }

  /* Spinner & Animations */
  .pm-spinner {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.25);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: pmSpin 0.7s linear infinite;
  }

  .pm-spinner.lg {
    width: 24px;
    height: 24px;
  }

  .spin {
    animation: pmSpin 0.8s linear infinite;
  }

  @keyframes pmSpin {
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes pmPulse {
    0%,
    100% {
      opacity: 0.45;
    }
    50% {
      opacity: 0.85;
    }
  }

  /* Keyboard Focus Rings */
  .pm-shell button:focus-visible,
  .pm-shell input:focus-visible,
  .pm-shell textarea:focus-visible,
  .pm-splitter:focus-visible {
    outline: 2px solid #6366f1;
    outline-offset: 1px;
  }

  /* Responsive Breakpoints */
  @media (max-width: 1180px) {
    .pm-telemetry-summary {
      display: none;
    }
    .pm-project-select-wrap,
    .pm-env-select-wrap {
      width: 180px;
    }
  }

  @media (max-width: 1024px) {
    .pm-topbar {
      flex-wrap: wrap;
    }
    .pm-sidebar {
      width: 260px;
    }
    .pm-auth-split {
      grid-template-columns: 1fr;
    }
    .pm-auth-left {
      border-right: none;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-right: 0;
      padding-bottom: 12px;
    }
  }

  @media (max-width: 768px) {
    .pm-shell {
      height: auto;
      min-height: calc(100vh - 64px);
      overflow: auto;
    }
    .pm-body {
      flex-direction: column;
      overflow: visible;
    }
    .pm-sidebar {
      width: 100%;
      max-height: 280px;
      border-right: none;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .pm-url-bar-row {
      flex-direction: column;
    }
    .pm-response-pane {
      height: auto !important;
      min-height: 260px;
    }
    .pm-form-grid-2,
    .pm-form-grid-3 {
      grid-template-columns: 1fr;
    }
  }
</style>
