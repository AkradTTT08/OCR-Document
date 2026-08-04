<script>
  import { createEventDispatcher } from "svelte";
  import { fade } from "svelte/transition";
  import { toast } from "./toastStore.js"; // global toast if needed

  const dispatch = createEventDispatcher();

  let file = null;
  let docType = "Requirement";
  let email = "";
  
  let isDragging = false;
  let fileInput;

  let isProcessing = false;
  let processStatus = "";
  let progressPct = 0;
  let scanResult = null;

  function handleDragEnter(e) {
    e.preventDefault();
    isDragging = true;
  }
  function handleDragLeave(e) {
    e.preventDefault();
    isDragging = false;
  }
  function handleDrop(e) {
    e.preventDefault();
    isDragging = false;
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      file = e.dataTransfer.files[0];
    }
  }
  function handleFileSelect(e) {
    if (e.target.files && e.target.files.length > 0) {
      file = e.target.files[0];
    }
  }
  function triggerFileInput() {
    fileInput.click();
  }
  function removeFile() {
    file = null;
    if (fileInput) fileInput.value = "";
  }

  async function processQAConsult() {
    if (!file) {
      alert("กรุณาอัปโหลดไฟล์เอกสารก่อน");
      return;
    }
    if (!email) {
      alert("กรุณากรอกอีเมลสำหรับรับผลการตรวจสอบ");
      return;
    }

    isProcessing = true;
    scanResult = null;
    progressPct = 10;
    processStatus = "กำลังอัปโหลดเอกสารและเริ่มประมวลผล...";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);
    formData.append("email", email);

    try {
      // Create a stream request
      const response = await fetch("http://127.0.0.1:5000/api/qa_consult", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? ""; // keep incomplete chunk

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.substring(6);
            if (!dataStr.trim()) continue;
            
            let data;
            try {
              data = JSON.parse(dataStr);
            } catch(e) {
              console.warn("Parse error:", e);
              continue;
            }

            if (data.type === "progress") {
              processStatus = data.message;
              progressPct = data.pct;
            } else if (data.type === "complete") {
              progressPct = 100;
              scanResult = data.result;
            } else if (data.type === "error") {
              throw new Error(data.message);
            }
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(`เกิดข้อผิดพลาด: ${msg}`);
      isProcessing = false;
    }
  }

  function resetForm() {
    file = null;
    scanResult = null;
    isProcessing = false;
    if (fileInput) fileInput.value = "";
  }
</script>

<div class="qa-container" in:fade>
  {#if !isProcessing && !scanResult}
    <!-- INPUT FORM -->
    <div class="header-text">
      <h2>QA Consult - ระบบตรวจสอบเอกสารอัตโนมัติ</h2>
      <p>อัปโหลดเอกสารของคุณเพื่อเปรียบเทียบกับฐานข้อมูล Knowledge Base ของบริษัท และรับรายงานข้อผิดพลาดทางอีเมล</p>
    </div>

    <div class="main-card">
      <div class="form-grid">
        <!-- LEFT: File Upload -->
        <div class="upload-section">
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div
            class="drop-zone"
            class:dragging={isDragging}
            on:dragenter={handleDragEnter}
            on:dragleave={handleDragLeave}
            on:dragover|preventDefault
            on:drop={handleDrop}
            on:click={triggerFileInput}
            on:keydown={(e) => e.key === "Enter" && triggerFileInput()}
          >
            {#if file}
              <div class="file-info" on:click|stopPropagation>
                <div class="file-icon">
                  <svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                </div>
                <div class="file-details">
                  <div class="file-name">{file.name}</div>
                  <div class="file-size">{(file.size / 1024).toFixed(1)} KB</div>
                </div>
                <button class="btn-remove" on:click={removeFile}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            {:else}
              <div class="drop-content">
                <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                <p class="drop-title">ลากไฟล์ PDF มาวางที่นี่</p>
                <p class="drop-sub">หรือ <span>คลิกเพื่อเลือกไฟล์</span></p>
              </div>
            {/if}
          </div>
          <input
            type="file"
            accept=".pdf"
            bind:this={fileInput}
            on:change={handleFileSelect}
            style="display: none;"
          />
        </div>

        <!-- RIGHT: Settings -->
        <div class="settings-section">
          <div class="setting-group">
            <label>ประเภทเอกสาร (Document Type)</label>
            <select bind:value={docType}>
              <option value="Requirement">Requirement (ข้อกำหนดระบบ)</option>
              <option value="Design">Design (เอกสารออกแบบ)</option>
              <option value="Manual">User Manual (คู่มือการใช้งาน)</option>
              <option value="Other">อื่นๆ (ทั่วไป)</option>
            </select>
          </div>

          <div class="setting-group">
            <label>อีเมลผู้รับผลการตรวจสอบ</label>
            <input type="email" bind:value={email} placeholder="your.email@example.com" />
            <span class="hint-text">รายงานการเปรียบเทียบจะถูกจัดส่งไปยังอีเมลนี้</span>
          </div>

          <button class="btn-primary" on:click={processQAConsult} disabled={!file || !email}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            เริ่มตรวจสอบเอกสาร
          </button>
        </div>
      </div>
    </div>

  {:else if isProcessing && !scanResult}
    <!-- LOADING STATE -->
    <div class="loading-state">
      <div class="spinner-box">
        <!-- SVG Animation similar to ResultsPanel -->
        <svg class="pulse-ring" viewBox="0 0 100 100" width="120" height="120">
          <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="4"></circle>
          <circle cx="50" cy="50" r="45" fill="none" stroke="url(#gradient)" stroke-width="4" stroke-dasharray="283" stroke-dashoffset="100">
            <animateTransform attributeName="transform" type="rotate" from="0 50 50" to="360 50 50" dur="2s" repeatCount="indefinite" />
          </circle>
          <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#9333ea" />
              <stop offset="100%" stop-color="#3b82f6" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      <h2>กำลังวิเคราะห์ QA Consult...</h2>
      <p class="status-msg">{processStatus}</p>
      
      <div class="progress-bar-container">
        <div class="progress-fill" style="width: {progressPct}%"></div>
      </div>
    </div>

  {:else if scanResult}
    <!-- SUCCESS STATE -->
    <div class="result-state">
      <div class="success-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
      </div>
      <h2>ประมวลผลเสร็จสิ้น!</h2>
      <p>ระบบได้ทำการเปรียบเทียบเอกสารกับฐานข้อมูล ({docType}) และสร้างรายงานเรียบร้อยแล้ว</p>
      
      <div class="result-summary">
        <div class="summary-item">
          <span class="lbl">ส่งผลลัพธ์ไปที่:</span>
          <span class="val">{email}</span>
        </div>
        <div class="summary-item">
          <span class="lbl">จำนวนหน้าที่วิเคราะห์:</span>
          <span class="val">{scanResult.total_pages || 0} หน้า</span>
        </div>
        <div class="summary-item">
          <span class="lbl">สถานะการส่งอีเมล:</span>
          <span class="val success">สำเร็จ</span>
        </div>
      </div>

      <button class="btn-outline" on:click={resetForm}>
        ตรวจสอบเอกสารอื่นเพิ่มเติม
      </button>
    </div>
  {/if}
</div>

<style>
  .qa-container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 30px;
  }
  .header-text {
    text-align: center;
  }
  .header-text h2 {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 10px;
    background: linear-gradient(90deg, #fff, #9ca3af);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header-text p {
    color: var(--text3);
    font-size: 16px;
  }
  .main-card {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 30px;
  }
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 40px;
  }
  
  /* Upload Section */
  .drop-zone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    height: 100%;
    min-height: 250px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
    background: rgba(0,0,0,0.2);
  }
  .drop-zone.dragging, .drop-zone:hover {
    border-color: #9333ea;
    background: rgba(147, 51, 234, 0.05);
  }
  .drop-content {
    text-align: center;
  }
  .upload-icon {
    width: 48px;
    height: 48px;
    color: var(--text3);
    margin-bottom: 15px;
  }
  .drop-zone:hover .upload-icon {
    color: #9333ea;
  }
  .drop-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 5px;
  }
  .drop-sub {
    font-size: 14px;
    color: var(--text3);
  }
  .drop-sub span {
    color: #9333ea;
  }
  .file-info {
    display: flex;
    align-items: center;
    gap: 15px;
    background: var(--surface);
    padding: 20px;
    border-radius: 8px;
    border: 1px solid #9333ea;
    width: 80%;
  }
  .file-icon {
    width: 40px;
    height: 40px;
    background: rgba(147, 51, 234, 0.2);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #9333ea;
  }
  .file-details {
    flex: 1;
  }
  .file-name {
    font-weight: 500;
    font-size: 14px;
    margin-bottom: 4px;
    word-break: break-all;
  }
  .file-size {
    font-size: 12px;
    color: var(--text3);
  }
  .btn-remove {
    background: none;
    border: none;
    color: var(--text3);
    cursor: pointer;
    padding: 5px;
  }
  .btn-remove:hover {
    color: #ef4444;
  }

  /* Settings Section */
  .settings-section {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
  .setting-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .setting-group label {
    font-size: 14px;
    font-weight: 500;
    color: var(--text2);
  }
  select, input[type="email"] {
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 15px;
    outline: none;
    transition: border-color 0.2s;
  }
  select:focus, input[type="email"]:focus {
    border-color: #9333ea;
  }
  .hint-text {
    font-size: 12px;
    color: var(--text3);
  }
  .btn-primary {
    margin-top: auto;
    background: linear-gradient(135deg, #7c3aed, #3b82f6);
    color: white;
    border: none;
    padding: 16px;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    transition: opacity 0.2s, transform 0.1s;
  }
  .btn-primary:hover:not(:disabled) {
    opacity: 0.9;
  }
  .btn-primary:active:not(:disabled) {
    transform: scale(0.98);
  }
  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    background: var(--surface);
    color: var(--text3);
  }

  /* Loading State */
  .loading-state, .result-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    background: var(--surface2);
    border-radius: 16px;
    border: 1px solid var(--border);
    min-height: 400px;
  }
  .spinner-box {
    margin-bottom: 30px;
  }
  .loading-state h2 {
    font-size: 24px;
    margin-bottom: 10px;
  }
  .status-msg {
    color: var(--text2);
    margin-bottom: 30px;
  }
  .progress-bar-container {
    width: 100%;
    max-width: 400px;
    height: 8px;
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #9333ea, #3b82f6);
    transition: width 0.3s ease;
  }

  /* Result State */
  .success-icon {
    width: 64px;
    height: 64px;
    color: #10b981;
    margin-bottom: 20px;
  }
  .result-state h2 {
    font-size: 28px;
    color: #10b981;
    margin-bottom: 10px;
  }
  .result-state p {
    color: var(--text2);
    margin-bottom: 30px;
    text-align: center;
  }
  .result-summary {
    background: rgba(0,0,0,0.2);
    padding: 20px;
    border-radius: 8px;
    width: 100%;
    max-width: 400px;
    margin-bottom: 30px;
  }
  .summary-item {
    display: flex;
    justify-content: space-between;
    margin-bottom: 10px;
    font-size: 14px;
  }
  .summary-item:last-child {
    margin-bottom: 0;
  }
  .summary-item .lbl {
    color: var(--text3);
  }
  .summary-item .val {
    font-weight: 600;
  }
  .val.success {
    color: #10b981;
  }
  .btn-outline {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px 24px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s;
  }
  .btn-outline:hover {
    background: rgba(255,255,255,0.05);
  }
</style>
