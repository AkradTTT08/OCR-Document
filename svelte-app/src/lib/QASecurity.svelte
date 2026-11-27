<script>
  import { onMount, onDestroy } from "svelte";
  import { fade } from "svelte/transition";
  import { toast, customConfirm } from "./toastStore.js";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";
  import CustomSelect from "./CustomSelect.svelte";

  let projects = [];
  $: selectedProjectObj = $selectedProjectStore;
  $: currentProjectId = selectedProjectObj
    ? (selectedProjectObj.id || selectedProjectObj.project_id || selectedProjectObj.project_code || selectedProjectObj.name)
    : "";

  // 4 Unified Scan Modes: 'web_url' | 'api_collection' | 'paste' | 'github'
  let scanMode = "web_url";
  let standard = "OWASP Top 10 (2021)";
  let useAiEnrichment = false;
  let isLoading = false;
  let scanError = "";
  let scanAbortController = null;
  let isExportingExcel = false;
  let excelExportDone = false;

  // Historical Snapshot State
  let isViewingHistorySnapshot = false;
  let activeHistoryTimestamp = "";

  // Collapsible Findings State
  let collapsedFindingIds = new Set();
  let copiedFindingId = "";

  // Live Scan Stage & Timer Telemetry
  let scanStageIndex = 0;
  let scanElapsedSec = 0;
  let scanTimerId = null;
  let scanStageTimerId = null;

  $: scanStages =
    scanMode === "web_url"
      ? [
          "เชื่อมต่อเป้าหมาย & ตรวจสอบใบรับรอง HTTPS / SSL / TLS",
          "วิเคราะห์ HTTP Security Headers (CSP, HSTS, X-Frame-Options) & CORS Policy",
          "ตรวจสอบ Cookie Flags, DOM Forms & สแกนหา Secret ในไฟล์ JavaScript Bundles",
          "สำรวจไฟล์อ่อนไหว (/.env, /.git) & ทดสอบ OWASP Active Safe Probes",
          "คำนวณคะแนน Security Posture, สรุปสถานะรายงาน & บันทึกประวัติ"
        ]
      : scanMode === "api_collection"
      ? [
          "โหลดรายการ API Endpoints จากคลัง API Collection ของโครงการ",
          "ทดสอบการเข้าถึง & ตรวจสอบ Authentication / Access Control",
          "ตรวจจับ Stack Trace Leakage (5xx) & Excessive Data Exposure ใน JSON",
          "ตรวจสอบ API Security Headers & Sensitive URL Parameters",
          "คำนวณคะแนน Security Posture, สรุปสถานะรายงาน & บันทึกประวัติ"
        ]
      : [
          "เตรียมโครงสร้างไฟล์ Source Code & แยกโมดูลที่ต้องการตรวจสอบ",
          "สแกนหาช่องโหว่ Injection (SQLi, OS Command Injection, Code Eval)",
          "สแกนหาช่องโหว่ XSS, Insecure Deserialization & Path Traversal",
          "ตรวจจับ Hardcoded Secrets, API Keys & Weak Cryptography (MD5/SHA1)",
          "คำนวณคะแนน Security Posture, สรุปสถานะรายงาน & บันทึกประวัติ"
        ];

  function startScanTelemetry() {
    stopScanTelemetry();
    scanStageIndex = 0;
    scanElapsedSec = 0;
    scanTimerId = setInterval(() => {
      scanElapsedSec += 1;
    }, 1000);
    scanStageTimerId = setInterval(() => {
      if (scanStageIndex < scanStages.length - 1) {
        scanStageIndex += 1;
      }
    }, 1400);
  }

  function stopScanTelemetry() {
    if (scanTimerId) {
      clearInterval(scanTimerId);
      scanTimerId = null;
    }
    if (scanStageTimerId) {
      clearInterval(scanStageTimerId);
      scanStageTimerId = null;
    }
  }

  onDestroy(() => {
    stopScanTelemetry();
    if (scanAbortController) {
      scanAbortController.abort();
    }
  });

  $: formattedElapsed = `${String(Math.floor(scanElapsedSec / 60)).padStart(2, "0")}:${String(
    scanElapsedSec % 60
  ).padStart(2, "0")}`;

  // Computed Post-Scan Report Status Verdict
  $: reportVerdict = (() => {
    if (!scanResult) return null;
    const counts = scanResult.severity_counts || {};
    const crit = Number(counts.Critical || 0);
    const high = Number(counts.High || 0);
    const med = Number(counts.Medium || 0);
    const low = Number(counts.Low || 0);
    const score = Number(scanResult.security_score ?? 100);

    if (crit > 0) {
      return {
        tone: "critical",
        badge: "CRITICAL RISK • ไม่ผ่านเกณฑ์",
        headline: "ไม่ผ่านเกณฑ์ความปลอดภัย — ตรวจพบช่องโหว่ระดับวิกฤต (Critical Action Required)",
        detail: `พบช่องโหว่ระดับวิกฤต (Critical) ${crit} รายการ และระดับสูง (High) ${high} รายการ ต้องดำเนินการแก้ไขก่อนนำระบบขึ้นใช้งานจริง`,
        timestamp: scanResult.scan_meta?.timestamp || new Date().toISOString()
      };
    }
    if (high > 0) {
      return {
        tone: "high",
        badge: "HIGH RISK • ต้องแก้ไขเร่งด่วน",
        headline: "ไม่ผ่านเกณฑ์มาตรฐาน — ตรวจพบช่องโหว่ความเสี่ยงสูง (High Severity Found)",
        detail: `พบช่องโหว่ระดับสูง (High) ${high} รายการ และระดับปานกลาง (Medium) ${med} รายการ แนะนำให้แก้ไขตามแนวทาง Remediation ด้านล่าง`,
        timestamp: scanResult.scan_meta?.timestamp || new Date().toISOString()
      };
    }
    if (med > 0) {
      return {
        tone: "warning",
        badge: "CONDITIONAL PASS • เฝ้าระวัง",
        headline: "ผ่านเกณฑ์ขั้นต้นแบบมีเงื่อนไข — พบความเสี่ยงระดับปานกลางที่ควรปรับปรุง",
        detail: `ไม่พบช่องโหว่ระดับวิกฤตหรือสูง แต่พบความเสี่ยงระดับปานกลาง (Medium) ${med} รายการ และระดับต่ำ (Low) ${low} รายการ`,
        timestamp: scanResult.scan_meta?.timestamp || new Date().toISOString()
      };
    }
    return {
      tone: "pass",
      badge: "VERIFIED PASS • ปลอดภัย",
      headline: "ผ่านเกณฑ์ความปลอดภัยมาตรฐาน (Security Assessment Verified Pass)",
      detail: `คะแนนความปลอดภัย ${score}/100 (Grade ${scanResult.grade || "A"}) ไม่พบช่องโหว่ระดับ Critical, High หรือ Medium${
        low > 0 ? ` (มีข้อเสนอแนะระดับต่ำ ${low} รายการ)` : ""
      }`,
      timestamp: scanResult.scan_meta?.timestamp || new Date().toISOString()
    };
  })();

  // 1. Live Web / SPA / Authenticated Web State
  let targetUrl = "";
  let scanProfile = "full_web"; // 'quick' | 'full_web' | 'spa_headless'
  let maxPages = 5;
  let showAuthConfig = false;
  let authType = "none"; // 'none' | 'bearer' | 'cookie' | 'basic' | 'apikey'
  let authBearerToken = "";
  let authCookieString = "";
  let authBasicUser = "";
  let authBasicPass = "";
  let authApiKeyName = "X-API-Key";
  let authApiKeyValue = "";
  let customHeaderRows = [{ key: "", value: "", enabled: true }];

  // 2. Project API Collection Security State
  let projectCollections = [];
  let selectedCollectionId = "ALL";
  let apiBaseUrlOverride = "";
  let isLoadingCollections = false;

  // 3. Source Code / File Upload SAST State
  let sourceCode = "";
  let language = "auto";
  let uploadedFileNames = [];
  let codeFileInput;
  let isDragOverCode = false;

  // 4. GitHub Repo State
  let githubUrl = "";

  // Scan Output & Interactive Explorer State
  let scanResult = null;
  let activeOutputTab = "findings"; // 'findings' | 'headers' | 'surface' | 'markdown' | 'history'
  let severityFilter = "ALL"; // 'ALL' | 'Critical' | 'High' | 'Medium' | 'Low' | 'Info'
  let findingSearch = "";
  let scanHistory = [];
  let isLoadingHistory = false;

  $: codeLineCount = sourceCode ? sourceCode.split("\n").length : 0;

  const stdOptions = [
    {
      value: "OWASP Top 10 (2021)",
      label: "OWASP Top 10 (2021) — มาตรฐานเว็บและแอปพลิเคชันสากล",
      description: "ครอบคลุม Broken Access Control, Injection, XSS, Misconfiguration และ Cryptographic Failures",
      badge: "Web & App"
    },
    {
      value: "OWASP API Security Top 10 (2023)",
      label: "OWASP API Security Top 10 (2023) — มาตรฐานความปลอดภัย API",
      description: "เน้นตรวจสอบ BOLA, Broken Authentication, Excessive Data Exposure และ CORS/Headers ของ API",
      badge: "REST / GraphQL"
    },
    {
      value: "OWASP ASVS 4.0.3",
      label: "OWASP ASVS 4.0.3 — เกณฑ์ตรวจสอบเชิงลึก (Level 2)",
      description: "ตรวจสอบความมั่นคงระดับสถาปัตยกรรม Session, Cookie Flags, TLS, CSP และ Input Validation",
      badge: "Deep Audit"
    },
    {
      value: "CWE Top 25 Most Dangerous",
      label: "CWE Top 25 — จุดอ่อนซอฟต์แวร์ที่อันตรายที่สุด",
      description: "เน้นตรวจ SQLi, OS Command Injection, Path Traversal, Hardcoded Secrets และ Deserialization",
      badge: "SAST & DAST"
    }
  ];

  const profileOptions = [
    {
      value: "full_web",
      label: "Full Web & Multi-Page Crawl (แนะนำ — ตรวจครบทุกมิติ)",
      description: "ตรวจ TLS, Security Headers, CORS, Cookies, DOM/Forms, สแกน JS Bundles หา Secret, สำรวจไฟล์อ่อนไหว และ Crawl หน้าภายใน",
      badge: "Recommended"
    },
    {
      value: "spa_headless",
      label: "SPA Headless Browser (React / Vue / Svelte / Next.js)",
      description: "จำลองเบราว์เซอร์จริงด้วย Headless Chromium เพื่อเรนเดอร์ SPA, ดักจับ XHR/Fetch API อัตโนมัติ และตรวจ DOM หลัง Hydration",
      badge: "SPA / Dynamic"
    },
    {
      value: "quick",
      label: "Quick Passive & Header Audit (รวดเร็ว 2–4 วินาที)",
      description: "ตรวจเฉพาะหน้าแรก: HTTPS/SSL, HTTP Security Headers, CORS, Cookies และฟอร์มพื้นฐานโดยไม่ Crawl หน้าอื่น",
      badge: "Fast"
    }
  ];

  const authTypeOptions = [
    {
      value: "none",
      label: "No Auth (หน้าเว็บหรือ API สาธารณะ)",
      description: "สแกนโดยไม่แนบ Token หรือ Cookie ยืนยันตัวตน"
    },
    {
      value: "bearer",
      label: "Bearer Token (JWT / OAuth2 Authorization Header)",
      description: "แนบ Authorization: Bearer <token> ทุกคำขอสำหรับระบบที่ใช้ JWT"
    },
    {
      value: "cookie",
      label: "Session Cookie (คัดลอก Cookie จากเบราว์เซอร์ที่ Login แล้ว)",
      description: "เหมาะสำหรับระบบที่ใช้ Session Cookie หลัง Login (ดูจาก DevTools > Network > Request Headers > Cookie)"
    },
    {
      value: "basic",
      label: "HTTP Basic Auth (Username / Password)",
      description: "เหมาะสำหรับเซิร์ฟเวอร์ Staging ที่ล็อกด้วย Basic Authentication"
    },
    {
      value: "apikey",
      label: "API Key Header (เช่น X-API-Key)",
      description: "แนบคีย์เฉพาะของระบบใน HTTP Header ที่กำหนด"
    }
  ];

  $: collectionSelectOptions = [
    {
      value: "ALL",
      label: isLoadingCollections
        ? "กำลังโหลดคลัง API ของโครงการ..."
        : `สแกนทุก API Collections ในโครงการ (${projectCollections.length} ชุด)`,
      description: "รวบรวมทุก Endpoint ในโครงการมาตรวจสอบความปลอดภัยพร้อมกัน",
      badge: "All APIs"
    },
    ...projectCollections.map((col) => ({
      value: col.id,
      label: `${col.name} (${col.endpoints_count || col.endpoint_count || 0} endpoints)`,
      description: col.base_url ? `Base URL: ${col.base_url}` : `Format: ${col.format_type || col.format || "API"}`,
      badge: `${col.endpoints_count || col.endpoint_count || 0} EPs`
    }))
  ];

  const langOptions = [
    { value: "auto", label: "ตรวจจับภาษาอัตโนมัติ (Auto Detect)" },
    { value: "javascript", label: "JavaScript / TypeScript / Node.js / Svelte" },
    { value: "python", label: "Python (Flask / FastAPI / Django)" },
    { value: "java", label: "Java (Spring Boot)" },
    { value: "php", label: "PHP (Laravel / WordPress)" },
    { value: "go", label: "Go (Golang)" },
    { value: "csharp", label: "C# (.NET Core)" }
  ];

  function getAuthHeaders(extra = {}) {
    const token = typeof localStorage !== "undefined" ? localStorage.getItem("jwt_token") : null;
    const headers = { ...extra };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }

  onMount(async () => {
    try {
      const resProjects = await fetch("/api/projects", { headers: getAuthHeaders() });
      if (resProjects.ok) {
        const pData = await resProjects.json();
        projects = pData.projects || [];
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  });

  $: if (currentProjectId) {
    loadProjectCollections(currentProjectId);
    loadScanHistory(currentProjectId);
  }

  async function loadProjectCollections(pid) {
    if (!pid) return;
    isLoadingCollections = true;
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(pid)}/api-collections`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        projectCollections = Array.isArray(data) ? data : (data.collections || []);
      }
    } catch (_) {
      projectCollections = [];
    } finally {
      isLoadingCollections = false;
    }
  }

  async function loadScanHistory(pid) {
    isLoadingHistory = true;
    try {
      const q = pid ? `?project_id=${encodeURIComponent(pid)}` : "";
      const res = await fetch(`/api/qa/security/history${q}`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        scanHistory = data.history || [];
      }
    } catch (_) {
      scanHistory = [];
    } finally {
      isLoadingHistory = false;
    }
  }

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  function resetProject() {
    selectedProjectStore.set(null);
    scanResult = null;
    scanError = "";
  }

  function clearCurrentScanResult() {
    scanResult = null;
    scanError = "";
    isViewingHistorySnapshot = false;
    activeHistoryTimestamp = "";
    collapsedFindingIds = new Set();
  }

  function buildAuthConfigPayload() {
    const cleanHeaders = customHeaderRows.filter((r) => r.enabled !== false && r.key && r.key.trim());
    return {
      type: authType,
      token: authBearerToken.trim(),
      cookie: authCookieString.trim(),
      username: authBasicUser.trim(),
      password: authBasicPass,
      key: authApiKeyName.trim(),
      value: authApiKeyValue.trim(),
      custom_headers: cleanHeaders
    };
  }

  function addCustomHeaderRow() {
    customHeaderRows = [...customHeaderRows, { key: "", value: "", enabled: true }];
  }

  function removeCustomHeaderRow(idx) {
    customHeaderRows = customHeaderRows.filter((_, i) => i !== idx);
    if (customHeaderRows.length === 0) {
      customHeaderRows = [{ key: "", value: "", enabled: true }];
    }
  }

  async function handleCodeFilesSelected(fileList) {
    if (!fileList || fileList.length === 0) return;
    const chunks = [];
    const names = [];
    for (const file of Array.from(fileList)) {
      try {
        const text = await file.text();
        names.push(file.name);
        chunks.push(`--- FILE: ${file.name} ---\n${text}`);
      } catch (_) {}
    }
    if (chunks.length > 0) {
      uploadedFileNames = names;
      sourceCode = chunks.join("\n\n");
      toast(`นำเข้าไฟล์โค้ด ${names.length} ไฟล์ (${sourceCode.split("\n").length} บรรทัด) เรียบร้อยแล้ว`, "success");
    }
  }

  function handleCodeDrop(e) {
    e.preventDefault();
    isDragOverCode = false;
    if (e.dataTransfer?.files?.length) {
      handleCodeFilesSelected(e.dataTransfer.files);
    }
  }

  function handleDropzoneKeydown(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      codeFileInput?.click();
    }
  }

  function handleInputShortcut(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      if (!isLoading) runSecurityScan();
    } else if (e.key === "Enter" && e.target?.tagName === "INPUT") {
      e.preventDefault();
      if (!isLoading) runSecurityScan();
    }
  }

  function loadSampleVulnerableCode() {
    sourceCode = `--- FILE: auth_controller.py ---
import os
import subprocess
import hashlib
import pickle

JWT_SECRET = "super_secret_hardcoded_prod_key_2026"

def login_user(cursor, username, password):
    # Vulnerable SQL string concatenation + weak MD5 hash
    pwd_hash = hashlib.md5(password.encode()).hexdigest()
    query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{pwd_hash}'"
    cursor.execute(query)
    return cursor.fetchone()

def ping_diagnostic(host_input):
    # Vulnerable OS Command Injection
    return subprocess.run(f"ping -c 1 {host_input}", shell=True)

def load_session_blob(raw_bytes):
    # Vulnerable Insecure Deserialization
    return pickle.loads(raw_bytes)
`;
    uploadedFileNames = ["auth_controller.py (Sample)"];
    toast("โหลดตัวอย่างโค้ดที่มีช่องโหว่สำหรับทดสอบ SAST แล้ว", "info");
  }

  function applyQuickUrlPreset(urlVal) {
    targetUrl = urlVal;
  }

  function cancelSecurityScan() {
    if (scanAbortController) {
      scanAbortController.abort();
      scanAbortController = null;
    }
    stopScanTelemetry();
    isLoading = false;
    toast("ยกเลิกการสแกนความปลอดภัยตามคำสั่งผู้ใช้แล้ว", "info");
  }

  async function runSecurityScan() {
    if (scanMode === "web_url" && !targetUrl.trim()) {
      toast("กรุณาระบุ URL ของเว็บไซต์ที่ต้องการตรวจสอบ (เช่น https://example.com หรือ http://localhost:5000)", "warning");
      return;
    }
    if (scanMode === "api_collection" && projectCollections.length === 0) {
      toast("ยังไม่มีคลัง API ในโครงการนี้ กรุณาเพิ่ม API ในเมนู API Collection ก่อน", "warning");
      return;
    }
    if (scanMode === "paste" && !sourceCode.trim()) {
      toast("กรุณาวาง Source Code หรืออัปโหลดไฟล์ก่อนเริ่มสแกน", "warning");
      return;
    }
    if (scanMode === "github" && !githubUrl.trim()) {
      toast("กรุณาระบุลิงก์ GitHub Repository", "warning");
      return;
    }

    if (scanAbortController) {
      scanAbortController.abort();
    }
    scanAbortController = new AbortController();

    isLoading = true;
    scanError = "";
    isViewingHistorySnapshot = false;
    activeHistoryTimestamp = "";
    collapsedFindingIds = new Set();
    severityFilter = "ALL";
    findingSearch = "";
    startScanTelemetry();

    try {
      const payload = {
        scan_mode: scanMode,
        project_id: currentProjectId,
        standard,
        use_ai: useAiEnrichment
      };

      if (scanMode === "web_url") {
        payload.target_url = targetUrl.trim();
        payload.scan_profile = scanProfile;
        payload.max_pages = Number(maxPages) || 5;
        payload.auth_config = buildAuthConfigPayload();
      } else if (scanMode === "api_collection") {
        payload.collection_id = selectedCollectionId;
        payload.base_url = apiBaseUrlOverride.trim();
        payload.auth_config = buildAuthConfigPayload();
      } else if (scanMode === "paste") {
        payload.source_code = sourceCode;
        payload.language = language;
        payload.target_label =
          uploadedFileNames.length > 0 ? uploadedFileNames.join(", ") : "Source Code Snippet";
      } else if (scanMode === "github") {
        payload.github_url = githubUrl.trim();
      }

      const response = await fetch("/api/qa/security/scan", {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
        signal: scanAbortController.signal
      });

      const data = await response.json();
      if (!response.ok || data.error) {
        throw new Error(data.error || "การสแกนความปลอดภัยล้มเหลว");
      }

      scanResult = data;
      activeOutputTab = "findings";
      loadScanHistory(currentProjectId);

      const vCount = data.vulnerabilities_found || 0;
      if (vCount > 0) {
        toast(`สแกนเสร็จสิ้น: คะแนน ${data.security_score}/100 (Grade ${data.grade}) • พบ ${vCount} ประเด็นความเสี่ยง`, "warning");
      } else {
        toast(`สแกนเสร็จสิ้น: คะแนน ${data.security_score}/100 (Grade ${data.grade}) • ไม่พบช่องโหว่ความเสี่ยงสูง`, "success");
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      scanError = err.message || "ไม่สามารถดำเนินการสแกนได้ กรุณาตรวจสอบ URL หรือการเชื่อมต่อเซิร์ฟเวอร์";
      toast(`เกิดข้อผิดพลาด: ${scanError}`, "error");
    } finally {
      stopScanTelemetry();
      isLoading = false;
      scanAbortController = null;
    }
  }

  function hydrateFormFromHistory(item) {
    if (!item) return;
    if (item.standard) standard = item.standard;
    const mode = item.scan_mode || "web_url";
    if (mode === "web_url") {
      scanMode = "web_url";
      targetUrl = item.target_label || "";
    } else if (mode === "api_collection") {
      scanMode = "api_collection";
    } else if (mode === "github") {
      scanMode = "github";
      githubUrl = item.target_label || "";
    } else {
      scanMode = "paste";
    }
  }

  function loadHistoryRecord(item) {
    scanResult = {
      ...item,
      target: item.target_label
    };
    scanError = "";
    isViewingHistorySnapshot = true;
    activeHistoryTimestamp = item.created_at
      ? new Date(item.created_at).toLocaleString("th-TH")
      : "รายงานย้อนหลัง";
    collapsedFindingIds = new Set();
    hydrateFormFromHistory(item);
    activeOutputTab = "findings";
    toast(`เปิดดูรายงานย้อนหลังของ "${item.target_label}" แล้ว`, "info");
  }

  function rescanHistoryItem(item, e) {
    if (e) e.stopPropagation();
    hydrateFormFromHistory(item);
    if (item.scan_mode === "paste" && !sourceCode.trim()) {
      toast("กรุณาวาง Source Code หรือเลือกไฟล์ที่ต้องการสแกนซ้ำทางด้านซ้าย", "info");
      return;
    }
    runSecurityScan();
  }

  async function deleteHistoryRecord(id, label, e) {
    if (e) e.stopPropagation();
    const ok = await customConfirm(`ยืนยันการลบประวัติการสแกน "${label}"?`);
    if (!ok) return;
    try {
      const res = await fetch(`/api/qa/security/history/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders()
      });
      if (res.ok) {
        scanHistory = scanHistory.filter((h) => h.id !== id);
        toast("ลบประวัติการสแกนเรียบร้อยแล้ว", "success");
      }
    } catch (_) {
      toast("ไม่สามารถลบประวัติการสแกนได้", "error");
    }
  }

  function toggleFindingCollapse(id) {
    const next = new Set(collapsedFindingIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    collapsedFindingIds = next;
  }

  function toggleCollapseAllFindings() {
    const allIds = filteredFindings.map((f) => f.id);
    if (collapsedFindingIds.size >= allIds.length && allIds.length > 0) {
      collapsedFindingIds = new Set();
    } else {
      collapsedFindingIds = new Set(allIds);
    }
  }

  async function copyFindingRemediation(f) {
    const text = [
      `[${f.severity}] ${f.title} (${f.id})`,
      `มาตรฐาน: ${f.owasp} | ${f.cwe} (${f.category})`,
      `ตำแหน่งที่พบ: ${f.target}`,
      `รายละเอียด: ${f.description}`,
      f.evidence ? `หลักฐาน: ${f.evidence}` : "",
      f.code_snippet ? `โค้ดที่พบ:\n${f.code_snippet}` : "",
      f.remediation ? `แนวทางแก้ไข (Remediation): ${f.remediation}` : ""
    ]
      .filter(Boolean)
      .join("\n");

    try {
      await navigator.clipboard.writeText(text);
      copiedFindingId = f.id;
      toast(`คัดลอกรายละเอียดและวิธีแก้ของ ${f.id} แล้ว`, "success");
      setTimeout(() => {
        if (copiedFindingId === f.id) copiedFindingId = "";
      }, 2000);
    } catch (_) {
      toast("ไม่สามารถคัดลอกข้อความได้", "error");
    }
  }

  async function exportExcelReport() {
    if (!scanResult || isExportingExcel) return;
    isExportingExcel = true;
    excelExportDone = false;
    try {
      const res = await fetch("/api/qa/security/export-excel", {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(scanResult)
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || `สร้างไฟล์ Excel ไม่สำเร็จ (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const safeTarget = String(scanResult.target || "security")
        .replace(/^https?:\/\//i, "")
        .replace(/[^a-zA-Z0-9_-]/g, "_")
        .slice(0, 32);
      a.download = `Spectra_Security_Report_${safeTarget}_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      excelExportDone = true;
      toast("ส่งออกรายงาน Excel (.xlsx ครบ 4 แผ่นงาน) เรียบร้อยแล้ว", "success");
      setTimeout(() => {
        excelExportDone = false;
      }, 2600);
    } catch (err) {
      toast(`ไม่สามารถออกรายงาน Excel ได้: ${err.message}`, "error");
    } finally {
      isExportingExcel = false;
    }
  }

  async function copyScanReport() {
    if (!scanResult?.report) return;
    try {
      await navigator.clipboard.writeText(scanResult.report);
      toast("คัดลอกรายงานความปลอดภัย (Markdown) เรียบร้อยแล้ว", "success");
    } catch (_) {
      toast("ไม่สามารถคัดลอกรายงานได้", "error");
    }
  }

  function exportReportFile(format = "json") {
    if (!scanResult) return;
    const isJson = format === "json";
    const content = isJson ? JSON.stringify(scanResult, null, 2) : (scanResult.report || "");
    const mime = isJson ? "application/json" : "text/markdown;charset=utf-8";
    const ext = isJson ? "json" : "md";
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `spectra-security-report-${new Date().toISOString().slice(0, 10)}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
    toast(`ดาวน์โหลดรายงาน .${ext.toUpperCase()} เรียบร้อยแล้ว`, "info");
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function formatSecurityMarkdown(md) {
    if (!md) return "";
    const codeBlocks = [];
    let text = String(md).replace(/```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)```/g, (_, lang, code) => {
      const idx = codeBlocks.length;
      codeBlocks.push(`<pre><code class="lang-${escapeHtml(lang)}">${escapeHtml(code.trimEnd())}</code></pre>`);
      return `@@CODEBLOCK_${idx}@@`;
    });

    const lines = text.split(/\r?\n/);
    const out = [];
    let inList = false;

    for (const rawLine of lines) {
      const trimmed = rawLine.trim();
      if (/^@@CODEBLOCK_\d+@@$/.test(trimmed)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(trimmed);
        continue;
      }
      if (!trimmed) {
        if (inList) { out.push("</ul>"); inList = false; }
        continue;
      }
      let safe = escapeHtml(rawLine)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

      if (/^###\s+/.test(safe)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<h3>${safe.replace(/^###\s+/, "")}</h3>`);
      } else if (/^##\s+/.test(safe)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<h2>${safe.replace(/^##\s+/, "")}</h2>`);
      } else if (/^#\s+/.test(safe)) {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<h1>${safe.replace(/^#\s+/, "")}</h1>`);
      } else if (/^\s*[-*]\s+/.test(safe)) {
        if (!inList) { out.push("<ul>"); inList = true; }
        out.push(`<li>${safe.replace(/^\s*[-*]\s+/, "")}</li>`);
      } else {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(`<p>${safe}</p>`);
      }
    }
    if (inList) out.push("</ul>");

    return out
      .join("\n")
      .replace(/@@CODEBLOCK_(\d+)@@/g, (_, i) => codeBlocks[Number(i)] || "");
  }

  $: filteredFindings = (scanResult?.findings || []).filter((f) => {
    const matchSev = severityFilter === "ALL" || f.severity === severityFilter;
    const q = findingSearch.trim().toLowerCase();
    const matchQuery =
      !q ||
      (f.title || "").toLowerCase().includes(q) ||
      (f.category || "").toLowerCase().includes(q) ||
      (f.owasp || "").toLowerCase().includes(q) ||
      (f.cwe || "").toLowerCase().includes(q) ||
      (f.target || "").toLowerCase().includes(q) ||
      (f.description || "").toLowerCase().includes(q);
    return matchSev && matchQuery;
  });
</script>

<div class="qa-security-container" in:fade>
  {#if !selectedProjectObj}
    <ProjectSelection
      {projects}
      on:select={(e) => selectProject(e.detail)}
    />
  {:else}
    <!-- Top Bar -->
    <div class="top-nav">
      <div class="nav-left">
        <button type="button" class="btn-back" on:click={resetProject}>
          <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true">
            <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
          </svg>
          เปลี่ยนโครงการ
        </button>

        <div class="active-project-badge">
          <span class="proj-dot" aria-hidden="true"></span>
          <span>โครงการ: <strong>{selectedProjectObj.project_code ? `${selectedProjectObj.project_code} - ` : ""}{selectedProjectObj.name}</strong></span>
        </div>
      </div>

      <div class="nav-right">
        {#if scanResult}
          <button type="button" class="btn-reset-result" on:click={clearCurrentScanResult}>
            ล้างผลลัพธ์ปัจจุบัน
          </button>
        {/if}
        <button
          type="button"
          class="btn-history-toggle"
          class:active={activeOutputTab === "history"}
          aria-pressed={activeOutputTab === "history"}
          on:click={() => (activeOutputTab = activeOutputTab === "history" && scanResult ? "findings" : "history")}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span>ประวัติการสแกน ({isLoadingHistory ? "..." : scanHistory.length})</span>
        </button>
      </div>
    </div>

    <div class="header-banner">
      <div class="header-title-wrap">
        <div class="shield-icon-box" aria-hidden="true">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            <path d="M9 12l2 2 4-4"/>
          </svg>
        </div>
        <div>
          <h2>QA Security Scanner — Universal Web DAST, API & Code Audit</h2>
          <p>
            ตรวจสอบความปลอดภัยครบวงจรทั้งเว็บไซต์จริงทุกสถาปัตยกรรม (SSR, SPA React/Vue/Svelte, ระบบหลัง Login), คลัง API ของโครงการ และ Source Code ตามมาตรฐาน OWASP
          </p>
        </div>
      </div>
    </div>

    <!-- 4-Mode Selector Bar -->
    <div class="mode-selector-grid" role="tablist" aria-label="เลือกรูปแบบการตรวจสอบความปลอดภัย">
      <button
        type="button"
        role="tab"
        id="tab-mode-web"
        aria-controls="security-config-panel"
        aria-selected={scanMode === "web_url"}
        class="mode-card"
        class:active={scanMode === "web_url"}
        on:click={() => (scanMode = "web_url")}
      >
        <div class="mode-icon cyan" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="2" y1="12" x2="22" y2="12"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
        </div>
        <div class="mode-copy">
          <span class="mode-name">สแกนเว็บไซต์จริง (Live Web & SPA)</span>
          <span class="mode-desc">ตรวจ HTTPS/TLS, Headers, CORS, Cookies, JS Secrets, Forms & Crawl ทุกหน้า</span>
        </div>
      </button>

      <button
        type="button"
        role="tab"
        id="tab-mode-api"
        aria-controls="security-config-panel"
        aria-selected={scanMode === "api_collection"}
        class="mode-card"
        class:active={scanMode === "api_collection"}
        on:click={() => (scanMode = "api_collection")}
      >
        <div class="mode-icon violet" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
        </div>
        <div class="mode-copy">
          <span class="mode-name">สแกนคลัง API โครงการ ({projectCollections.length})</span>
          <span class="mode-desc">ดึง API Collection ของโครงการมาตรวจ Auth, Data Leak และ Error Exposure</span>
        </div>
      </button>

      <button
        type="button"
        role="tab"
        id="tab-mode-paste"
        aria-controls="security-config-panel"
        aria-selected={scanMode === "paste"}
        class="mode-card"
        class:active={scanMode === "paste"}
        on:click={() => (scanMode = "paste")}
      >
        <div class="mode-icon emerald" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="16 18 22 12 16 6"/>
            <polyline points="8 6 2 12 8 18"/>
          </svg>
        </div>
        <div class="mode-copy">
          <span class="mode-name">สแกน Source Code / อัปโหลดไฟล์</span>
          <span class="mode-desc">ตรวจ SQLi, Command Injection, XSS, Hardcoded Secrets & Weak Crypto</span>
        </div>
      </button>

      <button
        type="button"
        role="tab"
        id="tab-mode-github"
        aria-controls="security-config-panel"
        aria-selected={scanMode === "github"}
        class="mode-card"
        class:active={scanMode === "github"}
        on:click={() => (scanMode = "github")}
      >
        <div class="mode-icon amber" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/>
          </svg>
        </div>
        <div class="mode-copy">
          <span class="mode-name">สแกน GitHub Repository</span>
          <span class="mode-desc">โคลนและสแกนไฟล์ทั้งหมดใน Repository อัตโนมัติ</span>
        </div>
      </button>
    </div>

    <!-- Main Two-Column Workspace -->
    <div class="workspace-grid">
      <!-- Left Column: Configuration & Target Input -->
      <section id="security-config-panel" class="config-panel" role="tabpanel">
        <div class="field-group">
          <label for="std-select">มาตรฐานความปลอดภัยที่ใช้อ้างอิง (Security Standard)</label>
          <CustomSelect id="std-select" options={stdOptions} bind:value={standard} />
        </div>

        {#if scanMode === "web_url"}
          <!-- MODE 1: UNIVERSAL WEB / SPA SCANNER -->
          <div class="field-group">
            <div class="label-row">
              <label for="web-target-url">URL เว็บไซต์เป้าหมาย (รองรับ Public, Staging, Localhost, SPA)</label>
            </div>
            <input
              id="web-target-url"
              type="text"
              class="spectra-input mono"
              placeholder="https://example.com หรือ http://localhost:5000 (กด Enter เพื่อสแกน)"
              bind:value={targetUrl}
              on:keydown={handleInputShortcut}
            />
            <div class="quick-presets">
              <span class="preset-label">ทดสอบด่วน:</span>
              <button type="button" class="preset-chip" on:click={() => applyQuickUrlPreset("http://localhost:5000")}>
                Local Backend (:5000)
              </button>
              <button type="button" class="preset-chip" on:click={() => applyQuickUrlPreset("http://localhost:5173")}>
                Local Frontend (:5173)
              </button>
              <button type="button" class="preset-chip" on:click={() => applyQuickUrlPreset("https://example.com")}>
                example.com
              </button>
            </div>
          </div>

          <div class="two-col-fields">
            <div class="field-group">
              <label for="scan-profile-select">ความลึกและเอนจินการสแกน (Scan Profile)</label>
              <CustomSelect id="scan-profile-select" options={profileOptions} bind:value={scanProfile} />
            </div>

            <div class="field-group small">
              <label for="max-pages-input">หน้าสูงสุดที่ Crawl</label>
              <input
                id="max-pages-input"
                type="number"
                min="1"
                max="15"
                class="spectra-input"
                bind:value={maxPages}
                disabled={scanProfile === "quick"}
              />
            </div>
          </div>

        {:else if scanMode === "api_collection"}
          <!-- MODE 2: PROJECT API COLLECTION SECURITY -->
          <div class="field-group">
            <label for="col-select">เลือกชุด API Collection ของโครงการ ({selectedProjectObj.name})</label>
            <CustomSelect
              id="col-select"
              options={collectionSelectOptions}
              bind:value={selectedCollectionId}
            />
          </div>

          <div class="field-group">
            <label for="api-base-override">Base URL ของเซิร์ฟเวอร์ API (กรณี Endpoint เก็บเป็น Path เช่น `/api/v1/...`)</label>
            <input
              id="api-base-override"
              type="text"
              class="spectra-input mono"
              placeholder="เช่น http://localhost:5000 หรือ https://api.staging.example.com"
              bind:value={apiBaseUrlOverride}
              on:keydown={handleInputShortcut}
            />
          </div>

          <div class="info-banner">
            ระบบจะทดสอบทุก Endpoint ในชุดที่เลือกเพื่อตรวจหา Stack Trace Leakage (HTTP 500), ข้อมูลความลับรั่วไหลใน JSON Response (รหัสผ่าน/Token), การตั้งค่า Security Headers และพารามิเตอร์อ่อนไหวใน URL
          </div>

        {:else if scanMode === "paste"}
          <!-- MODE 3: SOURCE CODE & FILE UPLOAD SAST -->
          <div class="field-group">
            <label for="sast-lang-select">ภาษาโปรแกรมมิ่ง (Language)</label>
            <CustomSelect id="sast-lang-select" options={langOptions} bind:value={language} />
          </div>

          <!-- Accessible Drag & Drop Multi-File Code Dropzone -->
          <div
            class="code-dropzone"
            class:drag-over={isDragOverCode}
            role="button"
            tabindex="0"
            aria-label="คลิกหรือกด Enter เพื่อเลือกไฟล์ Source Code หรือลากหลายไฟล์มาวาง"
            on:click={() => codeFileInput.click()}
            on:keydown={handleDropzoneKeydown}
            on:dragover|preventDefault={() => (isDragOverCode = true)}
            on:dragleave|preventDefault={() => (isDragOverCode = false)}
            on:drop={handleCodeDrop}
          >
            <input
              type="file"
              multiple
              accept=".py,.js,.ts,.svelte,.vue,.jsx,.tsx,.java,.php,.go,.cs,.rb,.sql,.html,.json,.yaml,.yml,.env"
              bind:this={codeFileInput}
              on:change={(e) => handleCodeFilesSelected(e.target.files)}
              style="display: none;"
            />
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <span>คลิกเลือกไฟล์ Source Code หรือลากหลายไฟล์มาวางที่นี่ (.py, .js, .ts, .svelte, .java, .php, .sql)</span>
          </div>

          {#if uploadedFileNames.length > 0}
            <div class="uploaded-files-bar" aria-label="ไฟล์ที่นำเข้าแล้ว">
              {#each uploadedFileNames as fname}
                <span class="file-chip">{fname}</span>
              {/each}
            </div>
          {/if}

          <div class="code-input-wrapper">
            <div class="label-row">
              <label for="code-textarea">Source Code ({codeLineCount} บรรทัด)</label>
              <div class="code-tools">
                <button type="button" class="btn-mini-action" on:click={loadSampleVulnerableCode}>
                  โหลดโค้ดตัวอย่าง
                </button>
                {#if sourceCode}
                  <button
                    type="button"
                    class="btn-mini-action danger"
                    on:click={() => {
                      sourceCode = "";
                      uploadedFileNames = [];
                    }}
                  >
                    ล้างโค้ด
                  </button>
                {/if}
              </div>
            </div>
            <textarea
              id="code-textarea"
              class="spectra-textarea mono"
              rows="11"
              bind:value={sourceCode}
              on:keydown={handleInputShortcut}
              placeholder="วาง Source Code ที่ต้องการสแกนหาช่องโหว่ที่นี่..."
              spellcheck="false"
            ></textarea>
          </div>

        {:else if scanMode === "github"}
          <!-- MODE 4: GITHUB REPOSITORY -->
          <div class="field-group">
            <label for="github-url-in">GitHub Repository URL</label>
            <input
              id="github-url-in"
              type="url"
              class="spectra-input mono"
              placeholder="https://github.com/organization/repository (Public Repo)"
              bind:value={githubUrl}
              on:keydown={handleInputShortcut}
            />
          </div>
          <div class="info-banner">
            ระบบจะโคลน Repository แบบชั่วคราว (`--depth 1`) และสแกนไฟล์ Source Code ทั้งหมดด้วยเอนจิน Deterministic SAST เพื่อระบุชื่อไฟล์และเลขบรรทัดที่พบช่องโหว่
          </div>
        {/if}

        <!-- Shared Authenticated Scan Accordion for BOTH web_url AND api_collection (P1 Fix) -->
        {#if scanMode === "web_url" || scanMode === "api_collection"}
          <div class="auth-accordion">
            <button
              type="button"
              class="auth-toggle-btn"
              aria-expanded={showAuthConfig}
              aria-controls="auth-config-body"
              on:click={() => (showAuthConfig = !showAuthConfig)}
            >
              <div class="auth-toggle-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
                <span>ตั้งค่าการยืนยันตัวตน (Authentication & Custom Headers)</span>
              </div>
              <div class="auth-toggle-right">
                <span class="auth-status-pill">{authType === "none" ? "ไม่ระบุ Auth" : authType.toUpperCase()}</span>
                <svg
                  class="chevron-icon"
                  class:open={showAuthConfig}
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2.2"
                  aria-hidden="true"
                >
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </div>
            </button>

            {#if showAuthConfig}
              <div id="auth-config-body" class="auth-body">
                <div class="field-group">
                  <label for="web-auth-type">รูปแบบ Authentication</label>
                  <CustomSelect id="web-auth-type" options={authTypeOptions} bind:value={authType} />
                </div>

                {#if authType === "bearer"}
                  <div class="field-group">
                    <label for="auth-bearer-in">Bearer Token</label>
                    <input
                      id="auth-bearer-in"
                      type="text"
                      class="spectra-input mono"
                      placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
                      bind:value={authBearerToken}
                    />
                  </div>
                {:else if authType === "cookie"}
                  <div class="field-group">
                    <label for="auth-cookie-in">Cookie Header String (คัดลอกจาก DevTools &gt; Network &gt; Cookie)</label>
                    <input
                      id="auth-cookie-in"
                      type="text"
                      class="spectra-input mono"
                      placeholder="session_id=xyz123; auth_token=abc456"
                      bind:value={authCookieString}
                    />
                  </div>
                {:else if authType === "basic"}
                  <div class="two-col-fields">
                    <div class="field-group">
                      <label for="auth-basic-u">Username</label>
                      <input id="auth-basic-u" type="text" class="spectra-input" bind:value={authBasicUser} />
                    </div>
                    <div class="field-group">
                      <label for="auth-basic-p">Password</label>
                      <input id="auth-basic-p" type="password" class="spectra-input" bind:value={authBasicPass} />
                    </div>
                  </div>
                {:else if authType === "apikey"}
                  <div class="two-col-fields">
                    <div class="field-group">
                      <label for="auth-ak-name">Header Name</label>
                      <input id="auth-ak-name" type="text" class="spectra-input mono" bind:value={authApiKeyName} />
                    </div>
                    <div class="field-group">
                      <label for="auth-ak-val">Key Value</label>
                      <input id="auth-ak-val" type="text" class="spectra-input mono" bind:value={authApiKeyValue} />
                    </div>
                  </div>
                {/if}

                <div class="custom-headers-box">
                  <div class="label-row">
                    <span>Custom HTTP Headers เพิ่มเติม</span>
                    <button type="button" class="btn-mini-action" on:click={addCustomHeaderRow}>+ เพิ่ม Header</button>
                  </div>
                  {#each customHeaderRows as row, idx}
                    <div class="kv-row">
                      <input type="checkbox" bind:checked={row.enabled} aria-label={`เปิดใช้ Header แถวที่ ${idx + 1}`} />
                      <input
                        type="text"
                        class="spectra-input mono"
                        placeholder="Header Name"
                        aria-label={`ชื่อ Header แถวที่ ${idx + 1}`}
                        bind:value={row.key}
                      />
                      <input
                        type="text"
                        class="spectra-input mono"
                        placeholder="Value"
                        aria-label={`ค่า Header แถวที่ ${idx + 1}`}
                        bind:value={row.value}
                      />
                      <button
                        type="button"
                        class="btn-del-row"
                        aria-label={`ลบ Header แถวที่ ${idx + 1}`}
                        on:click={() => removeCustomHeaderRow(idx)}
                      >
                        ลบ
                      </button>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Hybrid Engine Toggle (Deterministic + Optional Gemini AI) -->
        <label class="ai-toggle-bar">
          <input type="checkbox" bind:checked={useAiEnrichment} />
          <div class="ai-toggle-copy">
            <strong>เปิดใช้ AI Security Architect วิเคราะห์เชิงลึกเพิ่มเติม (Optional)</strong>
            <span>เอนจินหลักทำงานแบบ Deterministic 100% (รวดเร็วและไม่ต้องพึ่งโควตา AI) หากติ๊กเปิด ระบบจะเรียก Gemini ช่วยสรุปคำแนะนำเพิ่มเติม</span>
          </div>
        </label>

        <button
          type="button"
          class="btn-scan-primary"
          disabled={isLoading || (scanMode === "api_collection" && projectCollections.length === 0 && !isLoadingCollections)}
          on:click={runSecurityScan}
        >
          {#if isLoading}
            <span class="spinner" aria-hidden="true"></span>
            <span>
              กำลังตรวจสอบความปลอดภัย ({scanMode === "web_url"
                ? "Web DAST"
                : scanMode === "api_collection"
                ? "API Security"
                : scanMode === "github"
                ? "GitHub SAST"
                : "Code SAST"})...
            </span>
          {:else}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            <span>
              {scanMode === "web_url"
                ? "เริ่มสแกนความปลอดภัยเว็บไซต์"
                : scanMode === "api_collection"
                ? "เริ่มสแกนความปลอดภัยคลัง API"
                : scanMode === "github"
                ? "เริ่มสแกน GitHub Repository"
                : "เริ่มสแกนช่องโหว่ Source Code"}
            </span>
          {/if}
        </button>
      </section>

      <!-- Right Column: Security Telemetry & Interactive Findings Explorer -->
      <section class="results-panel">
        {#if isLoading}
          <div class="state-card loading">
            <div class="orbital-shield-stage" aria-hidden="true">
              <div class="radar-conic-beam"></div>
              <svg class="orbit-ring-svg outer-orbit" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="54" fill="none" stroke="rgba(168, 85, 247, 0.35)" stroke-width="1.5" stroke-dasharray="16 10 6 10" />
              </svg>
              <svg class="orbit-ring-svg inner-orbit" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="42" fill="none" stroke="rgba(6, 182, 212, 0.45)" stroke-width="1.5" stroke-dasharray="22 14" />
              </svg>
              <div class="shield-core-pulse">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  <path d="M9 12l2 2 4-4"/>
                </svg>
              </div>
            </div>

            <div class="scan-live-header">
              <span class="scan-elapsed-pill">เวลาที่สแกน {formattedElapsed}</span>
              <h3>กำลังตรวจสอบความปลอดภัยเชิงลึก (ระยะที่ {scanStageIndex + 1}/{scanStages.length})</h3>
            </div>

            <div class="shimmer-progress-track" aria-hidden="true">
              <div
                class="shimmer-progress-fill"
                style="width: {Math.min(92, (scanStageIndex + 1) * 18)}%"
              ></div>
            </div>

            <div class="live-stages-checklist" aria-live="polite">
              {#each scanStages as stageText, idx}
                <div
                  class="stage-step-row"
                  class:done={idx < scanStageIndex}
                  class:active={idx === scanStageIndex}
                >
                  <span class="stage-indicator" aria-hidden="true">
                    {#if idx < scanStageIndex}
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    {:else if idx === scanStageIndex}
                      <span class="stage-pulse-dot"></span>
                    {:else}
                      <span class="stage-num">{idx + 1}</span>
                    {/if}
                  </span>
                  <span class="stage-label">{stageText}</span>
                </div>
              {/each}
            </div>

            <button type="button" class="btn-cancel-scan" on:click={cancelSecurityScan}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
                <rect x="6" y="6" width="12" height="12" rx="2"/>
              </svg>
              <span>หยุดการสแกน (Cancel Scan)</span>
            </button>
          </div>

        {:else if scanError}
          <div class="state-card error" role="alert">
            <div class="error-icon-orb" aria-hidden="true">
              <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="8" x2="12" y2="12"/>
                <line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
            </div>
            <h3>ไม่สามารถดำเนินการสแกนเป้าหมายได้</h3>
            <p class="error-reason-box">{scanError}</p>
            <div class="error-recovery-actions">
              <button type="button" class="btn-secondary-sm" on:click={() => (scanError = "")}>
                กลับไปแก้ไขการตั้งค่า
              </button>
              <button type="button" class="btn-retry-scan" on:click={runSecurityScan}>
                ลองสแกนอีกครั้ง
              </button>
            </div>
          </div>

        {:else if activeOutputTab === "history"}
          <div class="history-view">
            <div class="results-top-bar">
              <h3>ประวัติการสแกนความปลอดภัยของโครงการ ({scanHistory.length})</h3>
              {#if scanResult}
                <button type="button" class="btn-secondary-sm" on:click={() => (activeOutputTab = "findings")}>
                  กลับไปดูผลสแกนปัจจุบัน
                </button>
              {/if}
            </div>

            {#if isLoadingHistory}
              <div class="state-card">
                <span class="spinner" aria-hidden="true"></span>
                <p>กำลังโหลดประวัติการสแกน...</p>
              </div>
            {:else if scanHistory.length === 0}
              <div class="state-card">
                <p>ยังไม่มีประวัติการสแกนความปลอดภัยในโครงการนี้</p>
              </div>
            {:else}
              <div class="history-list">
                {#each scanHistory as item (item.id)}
                  <div class="history-item">
                    <button
                      type="button"
                      class="history-item-main"
                      on:click={() => loadHistoryRecord(item)}
                    >
                      <div class="hist-grade grade-{(item.grade || 'A').toLowerCase()}">
                        <span class="g-letter">{item.grade || "A"}</span>
                        <span class="g-score">{item.security_score ?? 100}</span>
                      </div>
                      <div class="hist-main">
                        <div class="hist-target">{item.target_label}</div>
                        <div class="hist-meta">
                          <span class="mode-tag">{item.scan_mode}</span>
                          <span>{item.standard}</span>
                          <span>พบ {item.vulnerabilities_found || 0} ความเสี่ยง</span>
                          {#if item.created_at}
                            <span>{new Date(item.created_at).toLocaleString("th-TH")}</span>
                          {/if}
                        </div>
                      </div>
                    </button>

                    <div class="history-item-actions">
                      <button
                        type="button"
                        class="btn-rescan-row"
                        title="โหลดค่าเข้าฟอร์มและสแกนเป้าหมายนี้ซ้ำ"
                        on:click={(e) => rescanHistoryItem(item, e)}
                      >
                        สแกนซ้ำ
                      </button>
                      <button
                        type="button"
                        class="btn-del-row"
                        aria-label={`ลบประวัติการสแกน ${item.target_label}`}
                        on:click={(e) => deleteHistoryRecord(item.id, item.target_label, e)}
                      >
                        ลบ
                      </button>
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>

        {:else if scanResult}
          <!-- Historical Snapshot Notice Bar (if viewing a loaded history record) -->
          {#if isViewingHistorySnapshot}
            <div class="history-snapshot-notice">
              <div class="snapshot-notice-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                <span>กำลังแสดงรายงานย้อนหลังเมื่อ <strong>{activeHistoryTimestamp}</strong></span>
              </div>
              <button type="button" class="btn-rescan-inline" on:click={runSecurityScan}>
                สแกนเป้าหมายนี้ซ้ำอีกครั้ง (Re-scan Now)
              </button>
            </div>
          {/if}

          <!-- Post-Scan Report Status Verdict Banner -->
          {#if reportVerdict}
            <div class="report-verdict-banner tone-{reportVerdict.tone}">
              <div class="verdict-left">
                <div class="verdict-icon-orb" aria-hidden="true">
                  {#if reportVerdict.tone === "pass"}
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                      <polyline points="9 12 11 14 15 10"/>
                    </svg>
                  {:else}
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3">
                      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                      <line x1="12" y1="9" x2="12" y2="13"/>
                      <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                  {/if}
                </div>
                <div class="verdict-copy">
                  <div class="verdict-top-row">
                    <span class="verdict-pill">{reportVerdict.badge}</span>
                    <span class="verdict-target-chip" title={scanResult.target}>{scanResult.target}</span>
                    {#if scanResult.scan_meta?.duration_sec !== undefined}
                      <span class="verdict-time">ตรวจเสร็จใน {scanResult.scan_meta.duration_sec} วินาที</span>
                    {/if}
                  </div>
                  <h4 class="verdict-headline">{reportVerdict.headline}</h4>
                  <p class="verdict-detail">{reportVerdict.detail}</p>
                </div>
              </div>

              <div class="verdict-cta">
                <button
                  type="button"
                  class="btn-excel-export"
                  class:done={excelExportDone}
                  disabled={isExportingExcel}
                  on:click={exportExcelReport}
                >
                  {#if isExportingExcel}
                    <span class="spinner" aria-hidden="true"></span>
                    <span>กำลังสร้าง Excel...</span>
                  {:else if excelExportDone}
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
                    <span>ดาวน์โหลด Excel แล้ว</span>
                  {:else}
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="8" y1="13" x2="16" y2="13"/>
                      <line x1="8" y1="17" x2="16" y2="17"/>
                    </svg>
                    <span>ออกรายงาน Excel (.xlsx)</span>
                  {/if}
                </button>
              </div>
            </div>
          {/if}

          <!-- Security Posture Summary Bar (Focused strictly on Score Gauge + Severity Filter Pills) -->
          <div class="posture-summary-bar">
            <div class="score-badge-box grade-{(scanResult.grade || 'A').toLowerCase()}">
              <div class="score-ring-wrap">
                <svg class="score-ring-svg" viewBox="0 0 64 64" aria-hidden="true">
                  <circle class="ring-track" cx="32" cy="32" r="27" />
                  <circle
                    class="ring-progress"
                    cx="32"
                    cy="32"
                    r="27"
                    stroke-dasharray="169.65"
                    stroke-dashoffset={169.65 - (169.65 * Math.max(0, Math.min(100, scanResult.security_score ?? 100))) / 100}
                  />
                </svg>
                <div class="grade-circle">{scanResult.grade || "A"}</div>
              </div>
              <div class="score-meta">
                <span class="score-num">{scanResult.security_score ?? 100}<small>/100</small></span>
                <span class="score-caption">Security Posture Score</span>
              </div>
            </div>

            <div class="severity-counters" role="group" aria-label="กรองตามระดับความรุนแรง">
              {#each [
                { id: "ALL", label: "ทั้งหมด", count: (scanResult.findings || []).length, cls: "all" },
                { id: "Critical", label: "Critical", count: scanResult.severity_counts?.Critical || 0, cls: "critical" },
                { id: "High", label: "High", count: scanResult.severity_counts?.High || 0, cls: "high" },
                { id: "Medium", label: "Medium", count: scanResult.severity_counts?.Medium || 0, cls: "medium" },
                { id: "Low", label: "Low", count: scanResult.severity_counts?.Low || 0, cls: "low" },
                { id: "Info", label: "Info", count: scanResult.severity_counts?.Info || 0, cls: "info" }
              ] as pill}
                <button
                  type="button"
                  class="sev-counter-pill {pill.cls}"
                  class:active={severityFilter === pill.id}
                  aria-pressed={severityFilter === pill.id}
                  on:click={() => {
                    severityFilter = pill.id;
                    activeOutputTab = "findings";
                  }}
                >
                  <span class="s-count">{pill.count}</span>
                  <span class="s-label">{pill.label}</span>
                </button>
              {/each}
            </div>
          </div>

          <!-- Output View Switcher Tabs + Secondary Export Actions -->
          <div class="result-tabs-bar">
            <div class="result-tabs" role="tablist" aria-label="มุมมองผลลัพธ์การสแกน">
              <button
                type="button"
                role="tab"
                aria-selected={activeOutputTab === "findings"}
                class="res-tab"
                class:active={activeOutputTab === "findings"}
                on:click={() => (activeOutputTab = "findings")}
              >
                ช่องโหว่ & วิธีแก้ไข ({(scanResult.findings || []).length})
              </button>
              {#if (scanResult.header_checks || []).length > 0}
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeOutputTab === "headers"}
                  class="res-tab"
                  class:active={activeOutputTab === "headers"}
                  on:click={() => (activeOutputTab = "headers")}
                >
                  Security Headers & TLS ({scanResult.header_checks.length})
                </button>
              {/if}
              <button
                type="button"
                role="tab"
                aria-selected={activeOutputTab === "surface"}
                class="res-tab"
                class:active={activeOutputTab === "surface"}
                on:click={() => (activeOutputTab = "surface")}
              >
                Attack Surface & หน้าเว็บที่สำรวจ
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeOutputTab === "markdown"}
                class="res-tab"
                class:active={activeOutputTab === "markdown"}
                on:click={() => (activeOutputTab = "markdown")}
              >
                รายงานฉบับเต็ม (Markdown)
              </button>
            </div>

            <div class="export-actions">
              <button type="button" class="btn-secondary-sm" on:click={copyScanReport}>คัดลอก Markdown</button>
              <button type="button" class="btn-secondary-sm" on:click={() => exportReportFile("md")}>.MD</button>
              <button type="button" class="btn-secondary-sm" on:click={() => exportReportFile("json")}>JSON</button>
            </div>
          </div>

          <!-- TAB 1: STRUCTURED FINDINGS & REMEDIATION -->
          {#if activeOutputTab === "findings"}
            <div class="findings-toolbar">
              <input
                type="text"
                class="spectra-input"
                aria-label="ค้นหาช่องโหว่ตามชื่อ หมวดหมู่ OWASP CWE หรือ URL"
                placeholder="ค้นหาช่องโหว่ตามชื่อ, หมวดหมู่, OWASP, CWE หรือ URL..."
                bind:value={findingSearch}
              />
              {#if filteredFindings.length > 1}
                <button type="button" class="btn-collapse-all" on:click={toggleCollapseAllFindings}>
                  {collapsedFindingIds.size >= filteredFindings.length ? "ขยายทั้งหมด" : "ย่อทั้งหมด"}
                </button>
              {/if}
            </div>

            {#if filteredFindings.length === 0}
              <div class="state-card pass">
                <h4>ไม่พบรายการช่องโหว่ในหมวดที่เลือก</h4>
                <p>เป้าหมายที่ตรวจสอบผ่านเกณฑ์ความปลอดภัยในส่วนนี้ หรือลองเปลี่ยนตัวกรองระดับความรุนแรง</p>
              </div>
            {:else}
              <div class="findings-list">
                {#each filteredFindings as f, fIdx (f.id)}
                  {@const isCollapsed = collapsedFindingIds.has(f.id)}
                  <article
                    class="finding-card sev-{(f.severity || 'Info').toLowerCase()}"
                    style="--stagger-idx: {Math.min(fIdx, 8)};"
                  >
                    <div class="finding-top">
                      <div class="finding-badges">
                        <span class="sev-badge {(f.severity || 'Info').toLowerCase()}">{f.severity}</span>
                        <span class="std-chip">{f.owasp}</span>
                        <span class="std-chip cyan">{f.cwe}</span>
                        <span class="cat-label">{f.category}</span>
                      </div>
                      <div class="finding-card-tools">
                        <span class="finding-id">{f.id}</span>
                        <button
                          type="button"
                          class="btn-card-tool"
                          on:click={() => copyFindingRemediation(f)}
                        >
                          {copiedFindingId === f.id ? "คัดลอกแล้ว" : "คัดลอกวิธีแก้"}
                        </button>
                        <button
                          type="button"
                          class="btn-card-tool"
                          aria-expanded={!isCollapsed}
                          on:click={() => toggleFindingCollapse(f.id)}
                        >
                          {isCollapsed ? "ดูรายละเอียด" : "ย่อ"}
                        </button>
                      </div>
                    </div>

                    <h4 class="finding-title">{f.title}</h4>
                    <div class="finding-target">
                      <strong>ตำแหน่งที่ตรวจพบ:</strong> <code>{f.target}</code>
                    </div>

                    {#if !isCollapsed}
                      <p class="finding-desc">{f.description}</p>

                      {#if f.evidence}
                        <div class="evidence-box">
                          <span class="box-tag">หลักฐานที่ตรวจพบ (Evidence)</span>
                          <code>{f.evidence}</code>
                        </div>
                      {/if}

                      {#if f.code_snippet}
                        <pre class="code-snippet-pre">{f.code_snippet}</pre>
                      {/if}

                      {#if f.remediation}
                        <div class="remediation-box">
                          <strong>แนวทางแก้ไข (Remediation):</strong>
                          <span>{f.remediation}</span>
                        </div>
                      {/if}
                    {/if}
                  </article>
                {/each}
              </div>
            {/if}

          <!-- TAB 2: HTTP SECURITY HEADERS & TLS MATRIX -->
          {:else if activeOutputTab === "headers"}
            <div class="headers-matrix">
              {#each scanResult.header_checks || [] as hc}
                <div class="header-row status-{hc.status}">
                  <div class="h-status-pill {hc.status}">
                    {hc.status === "pass" ? "PASS" : hc.status === "warn" ? "WARN" : "FAIL"}
                  </div>
                  <div class="h-info">
                    <div class="h-name">{hc.header}</div>
                    <div class="h-val"><code>{hc.value}</code></div>
                    <div class="h-rec">{hc.recommendation}</div>
                  </div>
                </div>
              {/each}
            </div>

          <!-- TAB 3: ATTACK SURFACE (CRAWLED PAGES, DISCOVERED APIS, FORMS) -->
          {:else if activeOutputTab === "surface"}
            <div class="surface-view">
              <div class="surface-stats-grid">
                <div class="surf-stat">
                  <span class="surf-num">{scanResult.attack_surface?.framework_detected || "Web / HTML"}</span>
                  <span class="surf-lbl">สถาปัตยกรรมที่ตรวจพบ</span>
                </div>
                <div class="surf-stat">
                  <span class="surf-num">{(scanResult.attack_surface?.crawled_pages || []).length}</span>
                  <span class="surf-lbl">หน้าเว็บ / Endpoint ที่ตรวจสอบ</span>
                </div>
                <div class="surf-stat">
                  <span class="surf-num">{(scanResult.attack_surface?.discovered_apis || []).length}</span>
                  <span class="surf-lbl">API Routes ที่ค้นพบในระบบ</span>
                </div>
                <div class="surf-stat">
                  <span class="surf-num">{scanResult.scan_meta?.duration_sec || 0}s</span>
                  <span class="surf-lbl">เวลาที่ใช้สแกนทั้งหมด</span>
                </div>
              </div>

              {#if (scanResult.attack_surface?.crawled_pages || []).length > 0}
                <h4 class="sub-heading">หน้าเว็บและ Endpoints ที่ตรวจสอบ ({scanResult.attack_surface.crawled_pages.length})</h4>
                <div class="surface-list">
                  {#each scanResult.attack_surface.crawled_pages as pg}
                    <div class="surface-item">
                      <span class="http-code" class:ok={pg.status_code && pg.status_code < 400}>
                        {pg.status_code || "SPEC"}
                      </span>
                      <code class="surf-url">{pg.method ? `${pg.method} ` : ""}{pg.url}</code>
                      {#if pg.latency_ms}
                        <span class="surf-lat">{pg.latency_ms} ms</span>
                      {/if}
                    </div>
                  {/each}
                </div>
              {/if}

              {#if (scanResult.attack_surface?.discovered_apis || []).length > 0}
                <h4 class="sub-heading">API Endpoints ที่ค้นพบจาก DOM / JS Bundles ({scanResult.attack_surface.discovered_apis.length})</h4>
                <div class="surface-list">
                  {#each scanResult.attack_surface.discovered_apis as apiStr}
                    <div class="surface-item">
                      <code class="surf-url">{apiStr}</code>
                    </div>
                  {/each}
                </div>
              {/if}
            </div>

          <!-- TAB 4: FULL MARKDOWN REPORT -->
          {:else if activeOutputTab === "markdown"}
            <div class="markdown-preview">
              {@html formatSecurityMarkdown(scanResult.report)}
            </div>
          {/if}

        {:else}
          <!-- Empty Ready State -->
          <div class="state-card empty">
            <div class="empty-shield-orb" aria-hidden="true">
              <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <path d="M9 12l2 2 4-4"/>
              </svg>
            </div>
            <h3>พร้อมตรวจสอบความปลอดภัยเว็บไซต์ทุกรูปแบบ คลัง API และ Source Code</h3>
            <p>
              เลือกโหมดการสแกนด้านบน ระบุ URL เว็บไซต์ (รองรับทั้งเว็บทั่วไป, SPA React/Vue/Svelte และเว็บหลัง Login), เลือกคลัง API ของโครงการ หรือวาง Source Code แล้วกดเริ่มสแกนทันที
            </p>
            <div class="capability-matrix" aria-label="ขอบเขตการตรวจสอบความปลอดภัย">
              <div class="cap-item">HTTPS / TLS &amp; HSTS</div>
              <div class="cap-item">CSP &amp; Clickjacking</div>
              <div class="cap-item">CORS Misconfiguration</div>
              <div class="cap-item">Cookie Security Flags</div>
              <div class="cap-item">JS Bundle Secret Scanner</div>
              <div class="cap-item">Sensitive Path Probe (/.env, /.git)</div>
              <div class="cap-item">Reflected XSS &amp; Open Redirect</div>
              <div class="cap-item">SAST Code Vulnerability</div>
            </div>
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>

<style>
  .qa-security-container {
    display: flex;
    flex-direction: column;
    gap: 18px;
    height: 100%;
    padding: 20px 24px 48px;
    box-sizing: border-box;
    width: 100%;
    overflow-y: auto;
    color: var(--text, #f8fafc);
    font-family: 'Prompt', sans-serif;
  }

  /* Universal Keyboard Focus Ring (DESIGN.md Neon Iris) */
  button:focus-visible,
  .code-dropzone:focus-visible,
  input:focus-visible,
  textarea:focus-visible {
    outline: 2px solid var(--primary, #6366f1);
    outline-offset: 2px;
  }

  .top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }

  .nav-left,
  .nav-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn-back,
  .btn-history-toggle,
  .btn-reset-result {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--bg2, #12141c);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-secondary, #cbd5e1);
    padding: 9px 16px;
    border-radius: 12px;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 600;
    transition: all 0.18s ease;
  }

  .btn-back:hover,
  .btn-history-toggle:hover,
  .btn-history-toggle.active,
  .btn-reset-result:hover {
    border-color: var(--primary, #6366f1);
    background: rgba(99, 102, 241, 0.14);
    color: #ffffff;
  }

  .active-project-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    background: rgba(18, 20, 28, 0.85);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: #e2e8f0;
    border-radius: 20px;
    font-size: 0.82rem;
  }

  .proj-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #10b981;
  }

  /* Neutral Slate Panel Surfaces (DESIGN.md Flat-By-Default) */
  .header-banner {
    background: rgba(18, 20, 28, 0.68);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 18px 22px;
  }

  .header-title-wrap {
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }

  .shield-icon-box {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: #a855f7;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .header-title-wrap h2 {
    margin: 0;
    font-family: 'Outfit', 'Prompt', sans-serif;
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .header-title-wrap p {
    margin: 4px 0 0;
    font-size: 0.84rem;
    color: var(--text-muted, #94a3b8);
  }

  /* 4-Mode Selector Grid */
  .mode-selector-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .mode-card {
    text-align: left;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px;
    border-radius: 12px;
    background: rgba(18, 20, 28, 0.68);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text, #f8fafc);
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .mode-card:hover {
    border-color: rgba(99, 102, 241, 0.4);
    background: rgba(18, 20, 28, 0.9);
  }

  .mode-card.active {
    border-color: #6366f1;
    background: rgba(99, 102, 241, 0.14);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.2);
  }

  .mode-icon {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .mode-icon.cyan { background: rgba(6, 182, 212, 0.16); color: #22d3ee; }
  .mode-icon.violet { background: rgba(168, 85, 247, 0.16); color: #c084fc; }
  .mode-icon.emerald { background: rgba(16, 185, 129, 0.16); color: #34d399; }
  .mode-icon.amber { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }

  .mode-copy {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .mode-name {
    font-size: 0.86rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .mode-desc {
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
    line-height: 1.35;
  }

  /* Two-Column Workspace Grid (Natural Single Scroll + Sticky Left Panel) */
  .workspace-grid {
    display: grid;
    grid-template-columns: 440px minmax(0, 1fr);
    gap: 20px;
    align-items: start;
  }

  .config-panel,
  .results-panel {
    background: rgba(18, 20, 28, 0.68);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .config-panel {
    position: sticky;
    top: 8px;
  }

  .field-group,
  .code-input-wrapper {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
  }

  .field-group label,
  .label-row label,
  .label-row span {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-secondary, #cbd5e1);
  }

  .label-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }

  .code-tools {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .two-col-fields {
    display: grid;
    grid-template-columns: 1fr 130px;
    gap: 12px;
  }

  /* DESIGN.md input-default: #0a0b12 obsidian-surface, 12px radius, 12px 15px padding */
  .spectra-input,
  .spectra-textarea {
    width: 100%;
    padding: 12px 15px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: #0a0b12;
    color: var(--text, #f8fafc);
    font-family: 'Prompt', sans-serif;
    font-size: 0.85rem;
    box-sizing: border-box;
    outline: none;
    transition: border-color 0.18s ease, box-shadow 0.18s ease;
  }

  .spectra-input.mono,
  .spectra-textarea.mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.81rem;
  }

  .spectra-input:focus,
  .spectra-textarea:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25);
  }

  .quick-presets {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 2px;
  }

  .preset-label {
    font-size: 0.73rem;
    color: var(--text-muted, #94a3b8);
  }

  .preset-chip {
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: #c7d2fe;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    cursor: pointer;
    transition: all 0.16s ease;
  }

  .preset-chip:hover {
    background: rgba(99, 102, 241, 0.24);
    color: #ffffff;
  }

  /* Auth Accordion */
  .auth-accordion {
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    background: #0a0b12;
    overflow: hidden;
  }

  .auth-toggle-btn {
    width: 100%;
    padding: 12px 14px;
    background: transparent;
    border: none;
    color: var(--text, #f8fafc);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 600;
    text-align: left;
  }

  .auth-toggle-left,
  .auth-toggle-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .chevron-icon {
    color: var(--text-muted, #94a3b8);
    transition: transform 0.2s ease;
  }

  .chevron-icon.open {
    transform: rotate(180deg);
  }

  .auth-status-pill {
    font-family: 'Outfit', monospace;
    font-size: 0.7rem;
    padding: 3px 9px;
    border-radius: 8px;
    background: rgba(6, 182, 212, 0.15);
    color: #22d3ee;
  }

  .auth-body {
    padding: 12px 14px 14px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .custom-headers-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .kv-row {
    display: grid;
    grid-template-columns: 20px 1fr 1fr auto;
    gap: 6px;
    align-items: center;
  }

  .btn-mini-action {
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    padding: 4px 10px;
    border-radius: 8px;
    font-size: 0.73rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-mini-action.danger,
  .btn-del-row {
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.3);
    color: #fda4af;
    padding: 5px 10px;
    border-radius: 8px;
    font-size: 0.73rem;
    cursor: pointer;
  }

  .code-dropzone {
    border: 1.5px dashed rgba(99, 102, 241, 0.35);
    border-radius: 12px;
    padding: 12px;
    background: #0a0b12;
    color: var(--text-secondary, #cbd5e1);
    font-size: 0.78rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    text-align: center;
    transition: all 0.18s ease;
  }

  .code-dropzone:hover,
  .code-dropzone.drag-over {
    border-color: #6366f1;
    background: rgba(99, 102, 241, 0.1);
  }

  .uploaded-files-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .file-chip {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.72rem;
    padding: 3px 10px;
    border-radius: 8px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.32);
    color: #6ee7b7;
  }

  .info-banner {
    background: rgba(99, 102, 241, 0.1);
    border: 1px solid rgba(99, 102, 241, 0.24);
    border-radius: 12px;
    padding: 12px;
    font-size: 0.78rem;
    color: #e2e8f0;
    line-height: 1.5;
  }

  .ai-toggle-bar {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px;
    border-radius: 12px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    cursor: pointer;
  }

  .ai-toggle-copy {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 0.75rem;
    color: var(--text-muted, #94a3b8);
  }

  .ai-toggle-copy strong {
    color: var(--text, #f8fafc);
    font-size: 0.8rem;
  }

  /* DESIGN.md Primary CTA: 2-stop Indigo (#6366f1) to Plasma Violet (#a855f7) */
  .btn-scan-primary {
    width: 100%;
    padding: 12px 24px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    color: #ffffff;
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    transition: all 0.2s ease;
  }

  .btn-scan-primary:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.45);
  }

  .btn-scan-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Orbital Shield Telemetry & Live Stage Checklist */
  .orbital-shield-stage {
    width: 118px;
    height: 118px;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 6px;
  }

  .radar-conic-beam {
    position: absolute;
    inset: 10px;
    border-radius: 50%;
    background: conic-gradient(
      from 0deg,
      transparent 0deg,
      rgba(99, 102, 241, 0.04) 200deg,
      rgba(6, 182, 212, 0.32) 340deg,
      rgba(168, 85, 247, 0.5) 360deg
    );
    animation: orbitSpin 2.6s linear infinite;
  }

  .orbit-ring-svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .outer-orbit {
    animation: orbitSpin 9s linear infinite;
  }

  .inner-orbit {
    animation: orbitSpinReverse 6s linear infinite;
  }

  .shield-core-pulse {
    width: 56px;
    height: 56px;
    border-radius: 12px;
    background: #12141c;
    border: 1px solid rgba(168, 85, 247, 0.45);
    color: #c084fc;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    z-index: 2;
    box-shadow: 0 10px 28px rgba(99, 102, 241, 0.28);
    animation: coreBreath 2s cubic-bezier(0.16, 1, 0.3, 1) infinite alternate;
  }

  .scan-live-header {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }

  .scan-elapsed-pill {
    font-family: 'Outfit', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 20px;
    background: rgba(6, 182, 212, 0.14);
    border: 1px solid rgba(6, 182, 212, 0.35);
    color: #22d3ee;
  }

  .shimmer-progress-track {
    width: 100%;
    max-width: 440px;
    height: 8px;
    border-radius: 20px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.1);
    overflow: hidden;
  }

  .shimmer-progress-fill {
    height: 100%;
    border-radius: 20px;
    background: linear-gradient(90deg, #6366f1 0%, #a855f7 50%, #06b6d4 100%);
    transition: width 0.45s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .live-stages-checklist {
    width: 100%;
    max-width: 500px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 6px;
    text-align: left;
  }

  .stage-step-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 12px;
    border-radius: 12px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.07);
    color: var(--text-muted, #94a3b8);
    font-size: 0.8rem;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .stage-step-row.active {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.45);
    color: #ffffff;
    transform: translateX(4px);
  }

  .stage-step-row.done {
    background: rgba(16, 185, 129, 0.08);
    border-color: rgba(16, 185, 129, 0.28);
    color: #a7f3d0;
  }

  .stage-indicator {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-family: 'Outfit', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    background: rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
  }

  .stage-step-row.done .stage-indicator {
    background: rgba(16, 185, 129, 0.22);
    color: #34d399;
  }

  .stage-step-row.active .stage-indicator {
    background: rgba(6, 182, 212, 0.22);
    color: #22d3ee;
  }

  .stage-pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #22d3ee;
    animation: coreBreath 0.75s ease-in-out infinite alternate;
  }

  .btn-cancel-scan {
    margin-top: 8px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 9px 18px;
    border-radius: 12px;
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.4);
    color: #fda4af;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .btn-cancel-scan:hover {
    background: rgba(244, 63, 94, 0.26);
    color: #ffffff;
  }

  /* Error Recovery Card */
  .error-icon-orb {
    width: 60px;
    height: 60px;
    border-radius: 20px;
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.35);
    color: #fb7185;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .error-reason-box {
    background: rgba(244, 63, 94, 0.08);
    border: 1px solid rgba(244, 63, 94, 0.25);
    color: #fecdd3;
    padding: 12px 16px;
    border-radius: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.8rem;
  }

  .error-recovery-actions {
    display: flex;
    gap: 10px;
    margin-top: 6px;
  }

  .btn-retry-scan {
    background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
    border: none;
    color: #ffffff;
    padding: 8px 16px;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    cursor: pointer;
  }

  /* Historical Snapshot Notice Bar */
  .history-snapshot-notice {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    padding: 10px 14px;
    border-radius: 12px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.32);
    font-size: 0.8rem;
    color: #e2e8f0;
  }

  .snapshot-notice-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .btn-rescan-inline {
    background: rgba(99, 102, 241, 0.22);
    border: 1px solid rgba(99, 102, 241, 0.48);
    color: #ffffff;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 0.76rem;
    font-weight: 700;
    cursor: pointer;
  }

  .btn-rescan-inline:hover {
    background: #6366f1;
  }

  /* Post-Scan Report Status Verdict Banner */
  .report-verdict-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    padding: 16px 18px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: #0a0b12;
    animation: verdictArrival 0.42s cubic-bezier(0.16, 1, 0.3, 1) both;
  }

  .report-verdict-banner.tone-pass {
    background: rgba(16, 185, 129, 0.09);
    border-color: rgba(16, 185, 129, 0.38);
  }

  .report-verdict-banner.tone-warning {
    background: rgba(245, 158, 11, 0.09);
    border-color: rgba(245, 158, 11, 0.38);
  }

  .report-verdict-banner.tone-high {
    background: rgba(249, 115, 22, 0.1);
    border-color: rgba(249, 115, 22, 0.42);
  }

  .report-verdict-banner.tone-critical {
    background: rgba(244, 63, 94, 0.11);
    border-color: rgba(244, 63, 94, 0.48);
  }

  .verdict-left {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    flex: 1;
    min-width: 240px;
  }

  .verdict-icon-orb {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    background: rgba(16, 185, 129, 0.18);
    color: #34d399;
  }

  .tone-warning .verdict-icon-orb { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
  .tone-high .verdict-icon-orb { background: rgba(249, 115, 22, 0.2); color: #fb923c; }
  .tone-critical .verdict-icon-orb { background: rgba(244, 63, 94, 0.22); color: #fb7185; }

  .verdict-copy {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
  }

  .verdict-top-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .verdict-pill {
    font-family: 'Outfit', sans-serif;
    font-size: 0.7rem;
    font-weight: 800;
    padding: 3px 10px;
    border-radius: 8px;
    letter-spacing: 0.04em;
    background: rgba(16, 185, 129, 0.22);
    color: #6ee7b7;
  }

  .tone-warning .verdict-pill { background: rgba(245, 158, 11, 0.22); color: #fde047; }
  .tone-high .verdict-pill { background: rgba(249, 115, 22, 0.22); color: #fdba74; }
  .tone-critical .verdict-pill { background: rgba(244, 63, 94, 0.25); color: #fda4af; }

  .verdict-target-chip {
    font-family: monospace;
    font-size: 0.74rem;
    padding: 3px 9px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-secondary, #cbd5e1);
    max-width: 280px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .verdict-time {
    font-size: 0.73rem;
    color: var(--text-muted, #94a3b8);
  }

  .verdict-headline {
    margin: 0;
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .verdict-detail {
    margin: 0;
    font-size: 0.8rem;
    color: var(--text-secondary, #cbd5e1);
    line-height: 1.45;
  }

  .btn-excel-export {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    border-radius: 12px;
    border: 1px solid rgba(16, 185, 129, 0.45);
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.24) 0%, rgba(6, 182, 212, 0.22) 100%);
    color: #ecfdf5;
    font-weight: 700;
    font-size: 0.82rem;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.2);
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .btn-excel-export:hover:not(:disabled) {
    transform: translateY(-1px);
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.36) 0%, rgba(6, 182, 212, 0.32) 100%);
    border-color: #34d399;
    box-shadow: 0 10px 24px rgba(16, 185, 129, 0.3);
  }

  .btn-excel-export.done {
    background: rgba(16, 185, 129, 0.32);
    border-color: #34d399;
  }

  .btn-excel-export:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Animated SVG Security Score Ring */
  .score-ring-wrap {
    position: relative;
    width: 60px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .score-ring-svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }

  .ring-track {
    fill: none;
    stroke: rgba(255, 255, 255, 0.08);
    stroke-width: 4.5;
  }

  .ring-progress {
    fill: none;
    stroke: #34d399;
    stroke-width: 4.5;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.75s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .grade-b .ring-progress { stroke: #22d3ee; }
  .grade-c .ring-progress { stroke: #fbbf24; }
  .grade-d .ring-progress,
  .grade-f .ring-progress { stroke: #fb7185; }

  /* Results Panel Summary Bar */
  .posture-summary-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
    padding: 14px;
    border-radius: 12px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .score-badge-box {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .grade-circle {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    font-family: 'Outfit', sans-serif;
    font-size: 1.45rem;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
  }

  .grade-b .grade-circle { background: rgba(6, 182, 212, 0.16); color: #22d3ee; }
  .grade-c .grade-circle { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }
  .grade-d .grade-circle,
  .grade-f .grade-circle { background: rgba(244, 63, 94, 0.16); color: #fb7185; }

  .score-meta {
    display: flex;
    flex-direction: column;
  }

  .score-num {
    font-family: 'Outfit', sans-serif;
    font-size: 1.25rem;
    font-weight: 700;
  }

  .score-num small {
    font-size: 0.78rem;
    color: var(--text-muted, #94a3b8);
  }

  .score-caption {
    font-size: 0.72rem;
    color: var(--text-muted, #94a3b8);
  }

  .severity-counters {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .sev-counter-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 11px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-secondary, #cbd5e1);
    font-size: 0.76rem;
    cursor: pointer;
    transition: all 0.16s ease;
  }

  .sev-counter-pill.active {
    border-color: #6366f1;
    background: rgba(99, 102, 241, 0.18);
    color: #ffffff;
  }

  .sev-counter-pill.critical .s-count { color: #fb7185; font-weight: 700; }
  .sev-counter-pill.high .s-count { color: #f97316; font-weight: 700; }
  .sev-counter-pill.medium .s-count { color: #fbbf24; font-weight: 700; }
  .sev-counter-pill.low .s-count { color: #38bdf8; font-weight: 700; }

  .result-tabs-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 10px;
  }

  .result-tabs {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .res-tab {
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted, #94a3b8);
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.16s ease;
  }

  .res-tab.active {
    background: rgba(99, 102, 241, 0.18);
    border-color: #6366f1;
    color: #ffffff;
  }

  .export-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .btn-secondary-sm {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-secondary, #cbd5e1);
    padding: 6px 11px;
    border-radius: 8px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-secondary-sm:hover {
    border-color: #6366f1;
    color: #ffffff;
  }

  .findings-toolbar {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  .btn-collapse-all {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-secondary, #cbd5e1);
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
    cursor: pointer;
  }

  .btn-collapse-all:hover {
    border-color: #6366f1;
    color: #ffffff;
  }

  /* Natural Flow Findings List (No Nested Scroll Trap) */
  .findings-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .finding-card {
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    animation: findingStaggerIn 0.34s cubic-bezier(0.16, 1, 0.3, 1) both;
    animation-delay: calc(var(--stagger-idx, 0) * 35ms);
  }

  .finding-card.sev-critical { border-color: rgba(244, 63, 94, 0.42); }
  .finding-card.sev-high { border-color: rgba(249, 115, 22, 0.38); }
  .finding-card.sev-medium { border-color: rgba(245, 158, 11, 0.32); }

  .finding-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .finding-badges,
  .finding-card-tools {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .btn-card-tool {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-secondary, #cbd5e1);
    padding: 3px 9px;
    border-radius: 8px;
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-card-tool:hover {
    border-color: #6366f1;
    color: #ffffff;
  }

  .sev-badge {
    font-family: 'Outfit', sans-serif;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 8px;
    text-transform: uppercase;
  }

  .sev-badge.critical { background: rgba(244, 63, 94, 0.2); color: #fda4af; }
  .sev-badge.high { background: rgba(249, 115, 22, 0.2); color: #fdba74; }
  .sev-badge.medium { background: rgba(245, 158, 11, 0.2); color: #fde047; }
  .sev-badge.low { background: rgba(56, 189, 248, 0.18); color: #7dd3fc; }
  .sev-badge.info { background: rgba(148, 163, 184, 0.18); color: #cbd5e1; }

  .std-chip {
    font-family: 'Outfit', monospace;
    font-size: 0.7rem;
    padding: 3px 8px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.14);
    color: #c7d2fe;
  }

  .std-chip.cyan {
    background: rgba(6, 182, 212, 0.14);
    color: #67e8f9;
  }

  .cat-label,
  .finding-id {
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
  }

  .finding-title {
    margin: 0;
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--text, #f8fafc);
  }

  .finding-target {
    font-size: 0.78rem;
    color: var(--text-secondary, #cbd5e1);
  }

  .finding-target code {
    background: rgba(255, 255, 255, 0.06);
    padding: 2px 7px;
    border-radius: 8px;
    color: #67e8f9;
  }

  .finding-desc {
    margin: 0;
    font-size: 0.82rem;
    color: var(--text-secondary, #cbd5e1);
    line-height: 1.55;
  }

  .evidence-box {
    background: #050505;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 0.76rem;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .box-tag {
    font-size: 0.68rem;
    font-weight: 700;
    color: var(--text-muted, #94a3b8);
    text-transform: uppercase;
  }

  .code-snippet-pre {
    margin: 0;
    padding: 10px;
    border-radius: 8px;
    background: #050505;
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
    font-size: 0.76rem;
    overflow-x: auto;
  }

  .remediation-box {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.28);
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 0.8rem;
    color: #a7f3d0;
    line-height: 1.5;
  }

  /* Headers Matrix */
  .headers-matrix {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .header-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px;
    border-radius: 12px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .h-status-pill {
    font-family: 'Outfit', monospace;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 8px;
    min-width: 52px;
    text-align: center;
  }

  .h-status-pill.pass { background: rgba(16, 185, 129, 0.18); color: #34d399; }
  .h-status-pill.warn { background: rgba(245, 158, 11, 0.18); color: #fbbf24; }
  .h-status-pill.fail { background: rgba(244, 63, 94, 0.18); color: #fb7185; }

  .h-info {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .h-name {
    font-weight: 700;
    font-size: 0.86rem;
  }

  .h-val code {
    font-size: 0.76rem;
    color: #67e8f9;
    word-break: break-all;
  }

  .h-rec {
    font-size: 0.76rem;
    color: var(--text-muted, #94a3b8);
  }

  /* Attack Surface View */
  .surface-stats-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }

  .surf-stat {
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .surf-num {
    font-family: 'Outfit', sans-serif;
    font-size: 1rem;
    font-weight: 700;
    color: #c7d2fe;
  }

  .surf-lbl {
    font-size: 0.73rem;
    color: var(--text-muted, #94a3b8);
  }

  .sub-heading {
    margin: 14px 0 8px;
    font-size: 0.86rem;
    color: var(--text-secondary, #cbd5e1);
  }

  .surface-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .surface-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 8px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 0.78rem;
  }

  .http-code {
    font-family: 'Outfit', monospace;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 8px;
    background: rgba(245, 158, 11, 0.16);
    color: #fbbf24;
  }

  .http-code.ok {
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
  }

  .surf-url {
    flex: 1;
    color: var(--text, #f8fafc);
    word-break: break-all;
  }

  .surf-lat {
    color: var(--text-muted, #94a3b8);
    font-family: monospace;
  }

  /* History List (Semantic Buttons & Semantic Grade Colors) */
  .results-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }

  .results-top-bar h3 {
    margin: 0;
    font-size: 1rem;
  }

  .history-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .history-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 12px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: border-color 0.16s ease;
  }

  .history-item:hover {
    border-color: rgba(99, 102, 241, 0.45);
  }

  .history-item-main {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 12px;
    background: transparent;
    border: none;
    color: inherit;
    text-align: left;
    padding: 0;
    cursor: pointer;
    font-family: inherit;
  }

  .history-item-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .btn-rescan-row {
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: #c7d2fe;
    padding: 5px 10px;
    border-radius: 8px;
    font-size: 0.73rem;
    font-weight: 600;
    cursor: pointer;
  }

  .btn-rescan-row:hover {
    background: #6366f1;
    color: #ffffff;
  }

  .hist-grade {
    width: 46px;
    height: 46px;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(16, 185, 129, 0.16);
    color: #34d399;
    font-family: 'Outfit', sans-serif;
    flex-shrink: 0;
  }

  .hist-grade.grade-b { background: rgba(6, 182, 212, 0.16); color: #22d3ee; }
  .hist-grade.grade-c { background: rgba(245, 158, 11, 0.16); color: #fbbf24; }
  .hist-grade.grade-d,
  .hist-grade.grade-f { background: rgba(244, 63, 94, 0.18); color: #fb7185; }

  .g-letter { font-weight: 800; font-size: 1rem; line-height: 1; }
  .g-score { font-size: 0.68rem; }

  .hist-main {
    flex: 1;
    min-width: 0;
  }

  .hist-target {
    font-weight: 700;
    font-size: 0.86rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .hist-meta {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 0.74rem;
    color: var(--text-muted, #94a3b8);
    margin-top: 3px;
  }

  .mode-tag {
    color: #c7d2fe;
    font-weight: 600;
  }

  /* Empty / Loading State Cards */
  .state-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 380px;
    text-align: center;
    padding: 28px;
    color: var(--text-muted, #94a3b8);
    gap: 12px;
  }

  .empty-shield-orb {
    width: 68px;
    height: 68px;
    border-radius: 20px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: #a855f7;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .state-card h3,
  .state-card h4 {
    margin: 0;
    color: var(--text, #f8fafc);
    font-size: 1.05rem;
  }

  .state-card p {
    margin: 0;
    font-size: 0.84rem;
    max-width: 540px;
    line-height: 1.55;
  }

  /* Non-Interactive Capability Matrix (Distinguished from clickable preset pills) */
  .capability-matrix {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-top: 10px;
    width: 100%;
    max-width: 540px;
    text-align: left;
  }

  .cap-item {
    font-size: 0.75rem;
    padding: 7px 12px;
    border-radius: 8px;
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: var(--text-secondary, #cbd5e1);
  }

  /* Markdown Report Preview with Global Element Styling */
  .markdown-preview {
    background: #0a0b12;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 20px;
    line-height: 1.65;
    font-size: 0.85rem;
    color: #e2e8f0;
  }

  .markdown-preview :global(h1),
  .markdown-preview :global(h2),
  .markdown-preview :global(h3) {
    color: #f8fafc;
    font-family: 'Outfit', 'Prompt', sans-serif;
    margin: 1.1em 0 0.45em;
  }

  .markdown-preview :global(h1:first-child),
  .markdown-preview :global(h2:first-child),
  .markdown-preview :global(h3:first-child) {
    margin-top: 0;
  }

  .markdown-preview :global(p) {
    margin: 0 0 0.8em;
  }

  .markdown-preview :global(ul) {
    margin: 0 0 1em 20px;
  }

  .markdown-preview :global(li) {
    margin-bottom: 0.35em;
  }

  .markdown-preview :global(code) {
    background: rgba(99, 102, 241, 0.16);
    color: #c7d2fe;
    padding: 2px 6px;
    border-radius: 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }

  .markdown-preview :global(pre) {
    background: #050505;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 12px 14px;
    overflow-x: auto;
    margin: 0.8em 0;
  }

  .markdown-preview :global(pre code) {
    background: transparent;
    padding: 0;
    color: #e2e8f0;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.25);
    border-top-color: #ffffff;
    border-radius: 50%;
    display: inline-block;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  @keyframes orbitSpin {
    to { transform: rotate(360deg); }
  }

  @keyframes orbitSpinReverse {
    to { transform: rotate(-360deg); }
  }

  @keyframes coreBreath {
    from { transform: scale(0.96); opacity: 0.88; }
    to { transform: scale(1.04); opacity: 1; }
  }

  @keyframes verdictArrival {
    from { opacity: 0; transform: translateY(-6px) scale(0.99); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  @keyframes findingStaggerIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @media (prefers-reduced-motion: reduce) {
    .radar-conic-beam,
    .outer-orbit,
    .inner-orbit,
    .shield-core-pulse,
    .stage-pulse-dot,
    .report-verdict-banner,
    .finding-card {
      animation: none !important;
      transform: none !important;
    }
    .ring-progress,
    .shimmer-progress-fill,
    .stage-step-row {
      transition: opacity 0.15s ease, background-color 0.15s ease, border-color 0.15s ease !important;
    }
  }

  @media (max-width: 1180px) {
    .mode-selector-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .workspace-grid {
      grid-template-columns: 1fr;
    }
    .config-panel {
      position: static;
    }
  }

  @media (max-width: 640px) {
    .mode-selector-grid,
    .two-col-fields,
    .surface-stats-grid,
    .capability-matrix {
      grid-template-columns: 1fr;
    }
  }
</style>
