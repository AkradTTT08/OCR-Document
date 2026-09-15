document.addEventListener("DOMContentLoaded", () => {
  const toggleBtn = document.getElementById("toggle-record-btn");
  const recordIcon = document.getElementById("record-icon");
  const recordText = document.getElementById("record-text");
  const clearBtn = document.getElementById("clear-btn");
  const syncBtn = document.getElementById("sync-btn");
  const container = document.getElementById("api-list-container");
  const countBadge = document.getElementById("count-badge");
  const backendInput = document.getElementById("backend-url-input");
  const projectSelect = document.getElementById("project-select");

  // Fetch available projects from backend
  async function loadProjects() {
    try {
      const url = `${backendInput.value.trim()}/api/projects`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        const projects = data.projects || [];
        if (projects.length > 0 && projectSelect) {
          projectSelect.innerHTML = projects.map(p => {
            const name = p.project_name || p.name || 'Unnamed Project';
            const code = p.project_code && !name.includes(p.project_code) ? ` (${p.project_code})` : '';
            return `<option value="${p.id || p.project_id}">${name}${code}</option>`;
          }).join('');
        }
      }
    } catch (e) {
      console.warn("Could not fetch projects from backend:", e);
    }
  }

  loadProjects();

  // Inspector Elements
  const inspPanel = document.getElementById("inspector-panel");
  const inspBackBtn = document.getElementById("insp-back-btn");
  const inspTitle = document.getElementById("insp-title");
  const tabRespBtn = document.getElementById("tab-resp-btn");
  const tabCurlBtn = document.getElementById("tab-curl-btn");
  const inspBodyContent = document.getElementById("insp-body-content");
  const btnCopyCurl = document.getElementById("btn-copy-curl");
  const btnCopyResp = document.getElementById("btn-copy-resp");

  // Custom Modal Elements
  const customModal = document.getElementById("custom-modal");
  const modalIconBadge = document.getElementById("modal-icon-badge");
  const modalIconSymbol = document.getElementById("modal-icon-symbol");
  const modalTitle = document.getElementById("modal-title");
  const modalMessage = document.getElementById("modal-message");
  const modalCloseBtn = document.getElementById("modal-close-btn");

  function showCustomModal(title, message, type = "error") {
    modalTitle.textContent = title;
    modalMessage.textContent = message;
    modalIconBadge.className = `modal-icon-badge ${type}`;
    
    if (type === "success") {
      modalIconSymbol.textContent = "✅";
    } else if (type === "info") {
      modalIconSymbol.textContent = "ℹ️";
    } else {
      modalIconSymbol.textContent = "❌";
    }

    customModal.classList.add("show");
  }

  function hideCustomModal() {
    customModal.classList.remove("show");
  }

  modalCloseBtn.addEventListener("click", hideCustomModal);
  customModal.addEventListener("click", (e) => {
    if (e.target === customModal) hideCustomModal();
  });

  let isRecording = false;
  let apis = [];
  let selectedApi = null;
  let activeInspTab = "response"; // 'response' | 'curl'
  let currentTabId = null;

  // 1. Get current active Chrome tab ID first
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs.length > 0) {
      currentTabId = tabs[0].id;
    }

    // 2. Fetch initial state scoped strictly to currentTabId
    chrome.runtime.sendMessage({ action: "GET_STATE", tabId: currentTabId }, (response) => {
      if (response) {
        isRecording = response.isRecording;
        apis = response.apis || [];
        if (response.targetBackend) backendInput.value = response.targetBackend;
        updateUI();
      }
    });
  });

  // Listen for new APIs captured on active tab
  chrome.runtime.onMessage.addListener((message) => {
    if (message.action === "NEW_API_CAPTURED") {
      if (currentTabId === null || message.tabId === currentTabId) {
        if (message.api) {
          apis.unshift(message.api);
          updateUI();
        }
      }
    }
  });

  toggleBtn.addEventListener("click", () => {
    const action = isRecording ? "STOP_RECORDING" : "START_RECORDING";
    chrome.runtime.sendMessage({ action, tabId: currentTabId }, (res) => {
      isRecording = !isRecording;
      updateUI();
    });
  });

  clearBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "CLEAR_APIS", tabId: currentTabId }, (res) => {
      apis = [];
      updateUI();
    });
  });

  syncBtn.addEventListener("click", () => {
    if (apis.length === 0) {
      showCustomModal("แจ้งเตือน", "ไม่มีรายการ API สำหรับ Sync กรุณาบันทึก Network ก่อน", "info");
      return;
    }
    syncBtn.disabled = true;
    syncBtn.textContent = "⏳ กำลัง Sync ข้อมูล...";

    const selectedProjId = projectSelect ? projectSelect.value : 1;
    chrome.runtime.sendMessage({
      action: "SYNC_BACKEND",
      tabId: currentTabId,
      projectId: selectedProjId,
      backendUrl: backendInput.value.trim()
    }, (res) => {
      syncBtn.disabled = false;
      syncBtn.textContent = "📥 Sync เข้าสู่ Spectra QA Repository";
      if (res && res.success) {
        showCustomModal(
          "Sync ข้อมูลสำเร็จ!",
          `นำเข้า API ทั้งหมด ${apis.length} รายการจาก Tab นี้เข้าสู่ Spectra QA Repository เรียบร้อยแล้ว`,
          "success"
        );
      } else {
        const errDetail = res ? res.error : "Network error หรือ Backend ปิดอยู่";
        showCustomModal("เกิดข้อผิดพลาดในการ Sync", errDetail, "error");
      }
    });
  });

  // Inspector Actions
  inspBackBtn.addEventListener("click", () => {
    inspPanel.classList.remove("open");
  });

  tabRespBtn.addEventListener("click", () => {
    activeInspTab = "response";
    tabRespBtn.classList.add("active");
    tabCurlBtn.classList.remove("active");
    renderInspectorContent();
  });

  tabCurlBtn.addEventListener("click", () => {
    activeInspTab = "curl";
    tabCurlBtn.classList.add("active");
    tabRespBtn.classList.remove("active");
    renderInspectorContent();
  });

  btnCopyCurl.addEventListener("click", () => {
    if (selectedApi && selectedApi.curl) {
      navigator.clipboard.writeText(selectedApi.curl);
      btnCopyCurl.textContent = "✅ Copied cURL!";
      setTimeout(() => { btnCopyCurl.textContent = "🐚 Copy cURL (bash)"; }, 1500);
    }
  });

  btnCopyResp.addEventListener("click", () => {
    if (selectedApi && selectedApi.responseBody) {
      navigator.clipboard.writeText(selectedApi.responseBody);
      btnCopyResp.textContent = "✅ Copied Response!";
      setTimeout(() => { btnCopyResp.textContent = "📋 Copy Response"; }, 1500);
    }
  });

  function openInspector(api) {
    selectedApi = api;
    const urlObj = new URL(api.url);
    inspTitle.textContent = `${api.method} ${urlObj.pathname}`;
    activeInspTab = "response";
    tabRespBtn.classList.add("active");
    tabCurlBtn.classList.remove("active");
    renderInspectorContent();
    inspPanel.classList.add("open");
  }

  function renderInspectorContent() {
    if (!selectedApi) return;

    if (activeInspTab === "response") {
      inspBodyContent.textContent = selectedApi.responseBody || "No response body captured.";
    } else {
      inspBodyContent.textContent = selectedApi.curl || "No cURL command available.";
    }
  }

  function updateUI() {
    if (isRecording) {
      toggleBtn.classList.add("recording");
      recordIcon.textContent = "⏹️";
      recordText.textContent = "หยุดบันทึก Network";
    } else {
      toggleBtn.classList.remove("recording");
      recordIcon.textContent = "🔴";
      recordText.textContent = "เริ่มบันทึก Network";
    }

    countBadge.textContent = `${apis.length} APIs`;

    if (apis.length === 0) {
      container.innerHTML = `<div class="empty-text">กดปุ่ม "เริ่มบันทึก Network"<br>และทดลองกดเล่นหน้าเว็บเพื่อแกะ API</div>`;
      return;
    }

    container.innerHTML = "";
    apis.forEach((api) => {
      const urlObj = new URL(api.url);
      const shortPath = urlObj.pathname + urlObj.search;
      const row = document.createElement("div");
      row.className = "api-item";
      
      const isErr = api.statusCode >= 400;
      const statusClass = isErr ? "err" : "ok";

      row.innerHTML = `
        <span class="method ${api.method}">${api.method}</span>
        <span class="url" title="${api.url}">${shortPath}</span>
        <span class="status ${statusClass}">${api.statusCode || 200}</span>
      `;

      row.addEventListener("click", () => openInspector(api));
      container.appendChild(row);
    });
  }
});
