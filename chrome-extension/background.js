// Spectra QA Chrome Extension Background Worker
let isRecording = false;
let capturedApis = [];
let targetBackend = "http://localhost:5000";

// Listen to Chrome storage for backend URL or recording state
chrome.storage.local.get(["targetBackend", "isRecording"], (result) => {
  if (result.targetBackend) targetBackend = result.targetBackend;
  if (result.isRecording !== undefined) isRecording = result.isRecording;
});

// Helper to generate bash cURL command
function generateCurlCommand(method, url, headers, body) {
  let curl = `curl -X ${method} "${url}"`;
  
  // Default headers if empty
  curl += ` -H "Content-Type: application/json"`;
  
  if (headers && Array.isArray(headers)) {
    headers.forEach(h => {
      if (h.name && h.value && !h.name.toLowerCase().startsWith("sec-") && !h.name.toLowerCase().startsWith("accept-")) {
        curl += ` -H "${h.name}: ${h.value}"`;
      }
    });
  }

  if (method === "POST" || method === "PUT" || method === "PATCH") {
    const payload = body || '{"sample": "data"}';
    curl += ` -d '${payload}'`;
  }
  
  return curl;
}

// Helper mock response body generator for inspection
function getResponseBodySample(method, url, statusCode) {
  if (statusCode >= 500) {
    return JSON.stringify({
      status: "error",
      code: statusCode,
      message: "Internal Server Error / Destination Connection Refused",
      timestamp: new Date().toISOString()
    }, null, 2);
  }
  
  if (url.includes("/api/projects")) {
    return JSON.stringify({
      success: true,
      projects: [
        { id: 1, project_code: "69A - TIFFA-RGP", project_name: "TIFFA Cargo Import System", is_active: true },
        { id: 2, project_code: "WMS-CORE", project_name: "Warehouse Management System", is_active: true }
      ]
    }, null, 2);
  } else if (url.includes("/login") || url.includes("/signIn")) {
    return JSON.stringify({
      success: statusCode === 200,
      token: statusCode === 200 ? "eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9..." : null,
      message: statusCode === 200 ? "Authentication successful" : "Invalid credentials"
    }, null, 2);
  } else {
    return JSON.stringify({
      status: statusCode,
      url: url,
      method: method,
      response_time: "45ms",
      data: { message: "Request captured successfully by Spectra QA Sniffer" }
    }, null, 2);
  }
}

// Intercept network requests & scope to tabId
chrome.webRequest.onCompleted.addListener(
  (details) => {
    if (!isRecording) return;
    
    // Ignore static assets (.js, .css, .png, .jpg, .svg, .woff)
    const url = details.url;
    if (url.match(/\.(js|css|png|jpg|jpeg|svg|woff|ttf|ico|map)$/i)) return;
    if (url.includes("chrome-extension://") || url.includes("localhost:5173/@vite")) return;

    const method = details.method || "GET";
    const curlCommand = generateCurlCommand(method, url, details.responseHeaders);
    const responseBody = getResponseBodySample(method, url, details.statusCode);

    const apiItem = {
      id: Date.now() + Math.random(),
      tabId: details.tabId,
      method: method,
      url: url,
      statusCode: details.statusCode,
      type: details.type,
      timeStamp: new Date(details.timeStamp).toLocaleTimeString(),
      headers: details.responseHeaders || [],
      curl: curlCommand,
      responseBody: responseBody
    };

    capturedApis.unshift(apiItem);
    if (capturedApis.length > 200) capturedApis.pop();

    // Broadcast update with tabId to popup if open
    chrome.runtime.sendMessage({ action: "NEW_API_CAPTURED", api: apiItem, tabId: details.tabId }).catch(() => {});
  },
  { urls: ["<all_urls>"] }
);

// Listen for commands from Popup UI (Strict Tab Isolation)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  const currentTabId = request.tabId;

  if (request.action === "START_RECORDING") {
    isRecording = true;
    if (currentTabId !== undefined) {
      capturedApis = capturedApis.filter(a => a.tabId !== currentTabId);
    }
    chrome.storage.local.set({ isRecording: true });
    sendResponse({ status: "started", apis: [] });
  } else if (request.action === "STOP_RECORDING") {
    isRecording = false;
    chrome.storage.local.set({ isRecording: false });
    const tabApis = currentTabId !== undefined ? capturedApis.filter(a => a.tabId === currentTabId) : capturedApis;
    sendResponse({ status: "stopped", apis: tabApis });
  } else if (request.action === "GET_STATE") {
    const tabApis = currentTabId !== undefined ? capturedApis.filter(a => a.tabId === currentTabId) : capturedApis;
    sendResponse({ isRecording, apis: tabApis, targetBackend });
  } else if (request.action === "CLEAR_APIS") {
    if (currentTabId !== undefined) {
      capturedApis = capturedApis.filter(a => a.tabId !== currentTabId);
    } else {
      capturedApis = [];
    }
    sendResponse({ apis: [] });
  } else if (request.action === "SYNC_BACKEND") {
    const tabApis = currentTabId !== undefined ? capturedApis.filter(a => a.tabId === currentTabId) : capturedApis;
    syncToSpectraBackend(request.projectId, request.backendUrl, tabApis)
      .then((res) => sendResponse({ success: true, result: res }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // Keep message channel open for async response
  }
});

async function syncToSpectraBackend(projectId, backendUrl, apisToSync) {
  const target = backendUrl || targetBackend;
  const endpoint = `${target}/api/extension/sync-apis`;
  
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      captured_at: new Date().toISOString(),
      total_count: apisToSync.length,
      apis: apisToSync
    })
  });

  if (!response.ok) {
    throw new Error(`Server responded with ${response.status}`);
  }
  return await response.json();
}
