<script>
  import { createEventDispatcher, onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { authUser } from "./authStore.js";
  import { qaHistory, selectedHistory, loadQAHistoryFromDB, selectedProjectStore, qaSessionGroups, activeQAContext, loadQAGroupsFromDB } from "./qaHistoryStore.js";
  import GateResultModal from "./GateResultModal.svelte";

  const dispatch = createEventDispatcher();

  let showGateModal = false;
  let gateResultData = null;

  let skills = [];
  let docTypes = ["Requirement", "Design", "Manual", "Other"];
  let selectedSkill = "";
  
  let projects = [];
  
  // Use store for selected project so App.svelte can filter history
  $: selectedProjectObj = $selectedProjectStore;
  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  onMount(async () => {
    // Load Skills (separate try/catch so failure won't block projects)
    try {
      const resSkills = await fetch("http://127.0.0.1:5000/api/skills");
      if (resSkills.ok) {
        const data = await resSkills.json();
        skills = (data.skills || []).filter(s =>
          !s.skill_name?.startsWith('[Exit Criteria]') &&
          !s.skill_name?.includes('Exit Criteria')
        );
      }
    } catch (err) {
      console.error("Failed to load skills:", err);
    }

    // Load Doc Types
    try { await loadDocTypes(); } catch (err) { console.error("Failed to load doc types:", err); }

    // Load Projects — must always run independently
    try {
      const resProjects = await fetch("http://127.0.0.1:5000/api/projects");
      if (resProjects.ok) {
        const pData = await resProjects.json();
        projects = pData.projects || [];
      } else {
        console.error("Projects API error:", resProjects.status);
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }

    // Auto-fill email from logged-in user
    const currentUser = $authUser;
    if (currentUser && currentUser.includes('@') && !emailList.includes(currentUser)) {
      emailList = [currentUser];
    }
  });

  $: if ($activeQAContext && projects.length > 0) {
    const ctx = $activeQAContext;
    activeQAContext.set(null); // Clear it
    
    selectedProjectStore.set(ctx.project);
    scanGroupName = ctx.group_name;
    scanGroupType = ctx.group_type;
    isGroupNameSet = true;
    scanResult = null;
    isProcessing = false;
    file = null;
  }

  $: if ($selectedHistory && projects.length > 0) {
    const item = $selectedHistory;
    selectedHistory.set(null); // Clear it so it doesn't re-trigger

    const baseName = item.filename ? item.filename.replace(/\.[^/.]+$/, "") : "";
    const safeName = baseName.replace(/[^\w\-.]/g, '_');
    const computedExcelUrl = `http://127.0.0.1:5000/api/qa_report/download/QA_Report_${safeName}_${item.id}.xlsx`;

    scanResult = {
      status: 'success',
      report: item.report,
      email: item.email || email, // If email is in DB, use it, otherwise use current
      total_pages: item.total_pages,
      doc_type: item.docType,
      filename: item.filename,
      emailSent: false,
      excel_url: computedExcelUrl
    };

    scanGroupName = item.group_name || 'General';
    scanGroupType = item.group_type || '';
    isGroupNameSet = true;

    const p = projects.find(p => p.id === item.project_id || p.project_id === item.project_id);
    if (p) {
      selectedProjectStore.set(p);
    }
  }

  async function loadDocTypes(projectId = null) {
    try {
      let url = "http://127.0.0.1:5000/api/doc_types";
      if (projectId) url += `?project_id=${projectId}`;
      const res = await fetch(url);
      if (res.ok) {
        docTypes = await res.json();
        if (docTypes.length > 0 && !docTypes.includes(docType)) {
          docType = docTypes[0];
        }
      }
    } catch (err) {
      console.error("Failed to load doc types:", err);
    }
  }

  $: if (selectedProjectObj) {
    loadDocTypes(selectedProjectObj.id || selectedProjectObj.project_id);
  } else {
    loadDocTypes();
  }

  let selectedDocTypes = [];
  let selectedSkills = [];

  // All skills are available for selection
  $: filteredSkills = skills;

  let file = null;
  let emailInput = "";
  let emailList = [];
  $: email = emailList.join(",");

  function addEmail() {
    if (emailInput && emailInput.includes("@")) {
      const emailTrimmed = emailInput.trim();
      if (!emailList.includes(emailTrimmed)) {
        emailList = [...emailList, emailTrimmed];
      }
      emailInput = "";
    } else if (emailInput) {
      toast.error("รูปแบบอีเมลไม่ถูกต้อง");
    }
  }

  function removeEmail(index) {
    emailList = emailList.filter((_, i) => i !== index);
  }
  
  function handleEmailKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addEmail();
    }
  }

  let isDragging = false;
  let fileInput;

  let isProcessing = false;
  let processStatus = "";
  let progressPct = 0;
  let scanResult = null;
  let scanGroupName = "";
  let scanGroupType = "Project Plan";
  let isGroupNameSet = false;

  let isSendingEmail = false;
  let showConfirmModal = false;
  let showSuccessModal = false;

  let docTypeOpen = false;
  let skillOpen = false;
  let groupTypeOpen = false;
  const masterGroupTypes = ["Project Plan", "SRS", "SDD", "UAT", "Test case"];

  function toggleDocType(type) {
    if (selectedDocTypes.includes(type)) {
      selectedDocTypes = selectedDocTypes.filter(t => t !== type);
    } else {
      selectedDocTypes = [...selectedDocTypes, type];
    }
  }

  function toggleSkill(skillId) {
    if (selectedSkills.includes(skillId)) {
      selectedSkills = selectedSkills.filter(s => s !== skillId);
    } else {
      selectedSkills = [...selectedSkills, skillId];
    }
  }

  function handleDragEnter(e) {
    e.preventDefault();
    isDragging = true;
  }
  function handleDragLeave(e) {
    e.preventDefault();
    isDragging = false;
  }
  
  async function confirmGroup() {
    if (!scanGroupName.trim()) return;
    
    const pId = selectedProjectObj.id || selectedProjectObj.project_id;
    const groupName = scanGroupName.trim();
    
    // Save to DB via API
    try {
      const res = await fetch("http://127.0.0.1:5000/api/qa_groups", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: pId,
          group_name: groupName,
          group_type: scanGroupType
        })
      });
      if (res.ok) {
        // Reload groups from DB so sidebar updates immediately
        await loadQAGroupsFromDB();
      } else {
        console.error("Failed to save QA group to DB");
      }
    } catch (err) {
      console.error("Error saving QA group:", err);
    }
    
    // Fallback/immediate UI update
    qaSessionGroups.update(groups => {
      if (!groups.find(g => g.group_name === groupName && g.project_id === pId)) {
        return [...groups, { group_name: groupName, group_type: scanGroupType, project_id: pId, project_code: selectedProjectObj.project_code || '' }];
      }
      return groups;
    });
    
    isGroupNameSet = true;
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
    if (emailInput.trim() !== "") {
      addEmail();
    }
    if (!file) {
      toast("กรุณาอัปโหลดไฟล์เอกสารก่อน", "warning");
      return;
    }
    if (!email) {
      toast("กรุณากรอกอีเมลสำหรับรับผลการตรวจสอบ", "warning");
      return;
    }

    isProcessing = true;
    scanResult = null;
    progressPct = 10;
    processStatus = "กำลังอัปโหลดเอกสารและเริ่มประมวลผล...";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", JSON.stringify(selectedDocTypes));
    formData.append("email", email);
    formData.append("skill_id", JSON.stringify(selectedSkills));
    if (selectedProjectObj) {
      formData.append("project_id", selectedProjectObj.id || selectedProjectObj.project_id);
      formData.append("project_name", `${selectedProjectObj.project_code || ''} ${selectedProjectObj.name || ''}`.trim() || 'Unknown Project');
    }
    if (scanGroupName.trim()) {
      formData.append("group_name", scanGroupName.trim());
    }
    formData.append("group_type", scanGroupType);

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
              if (scanResult && scanResult.exit_criteria_eval) {
                gateResultData = scanResult.exit_criteria_eval;
                showGateModal = true;
              }
              // Refresh history from DB
              loadQAHistoryFromDB();
            } else if (data.type === "error") {
              throw new Error(data.message);
            }
          }
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      toast(`เกิดข้อผิดพลาด: ${msg}`, "error");
      isProcessing = false;
    }
  }

  function sendEmail() {
    showConfirmModal = true;
  }

  async function executeSendEmail() {
    isSendingEmail = true;
    try {
      const response = await fetch("http://127.0.0.1:5000/api/qa_send_email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          docType: selectedDocTypes.join(", "),
          filename: scanResult.filename,
          report: scanResult.report,
          excel_url: scanResult.excel_url || ''
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP Error: ${response.status}`);
      }

      const data = await response.json();
      if (data.success) {
        showConfirmModal = false;
        showSuccessModal = true;
        scanResult.emailSent = true;
      } else {
        throw new Error(data.error || "Unknown error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการส่งอีเมล: ${err.message}`, "error");
      showConfirmModal = false;
    } finally {
      isSendingEmail = false;
    }
  }

  function resetForm() {
    file = null;
    scanResult = null;
    isProcessing = false;
    isGroupNameSet = false;
    scanGroupName = "";
    scanGroupType = "Project Plan";
    processStatus = "";
    if (fileInput) fileInput.value = "";
  }
</script>

  <svelte:window on:click={() => { docTypeOpen = false; skillOpen = false; groupTypeOpen = false; }} />

<div class="qa-container" in:fade class:full-width={!!scanResult}>
  {#if !selectedProjectObj}
    <!-- PROJECT SELECTION STATE -->
    <div class="header-text">
      <h2>เลือกโครงการ (Project Selection)</h2>
      <p>กรุณาเลือกโครงการที่ต้องการ เพื่อให้ AI อ้างอิงข้อมูลเปรียบเทียบจาก Knowledge Base ที่ถูกต้อง</p>
    </div>

    <div class="project-grid">
      {#if projects.length === 0}
        <div class="empty-state">
          ไม่พบโครงการในระบบ กรุณาสร้างโครงการที่หน้า Knowledge Base ก่อน
        </div>
      {:else}
        {#each projects as p}
          <!-- svelte-ignore a11y-click-events-have-key-events -->
          <!-- svelte-ignore a11y-no-static-element-interactions -->
          <div class="project-card" on:click={() => selectProject(p)}>
            <div class="card-header-row">
              <div class="p-code">{p.project_code}</div>
            </div>
            <div class="p-name">{p.name}</div>
            
            <div class="p-status-section">
              <div class="p-meta-label">สถานะ (STATUS)</div>
              <div class="p-status-value" class:active={p.status === 'Active'} class:inactive={p.status !== 'Active'}>{p.status || 'Active'}</div>
            </div>
            
            <div class="p-desc-section">
              <div class="p-meta-label">รายละเอียด (DESCRIPTION)</div>
              <div class="p-desc-box">
                {#if p.description}
                  {p.description}
                {:else}
                  <span class="empty-desc">ไม่มีรายละเอียด</span>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      {/if}
    </div>

  {:else if !isGroupNameSet}
    <!-- GROUP NAME FORM -->
    <div class="top-nav">
      <button class="btn-back" on:click={() => { selectedProjectStore.set(null); isGroupNameSet = false; scanGroupName = ""; }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>
    </div>

    <div class="header-text">
      <h2>กำหนดชื่อการตรวจสอบ (Scan Group)</h2>
      <p>กรุณาระบุชื่อการตรวจสอบนี้เพื่อใช้จัดกลุ่มประวัติการตรวจสอบ (ตัวอย่าง: ตรวจเอกสาร UAT)</p>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code} - {selectedProjectObj.name}</strong>
      </div>
    </div>

    <div class="main-card" style="max-width: 600px; margin: 0 auto;">
      <div class="setting-group relative">
        <label>ชื่อการตรวจสอบ</label>
        <input
          type="text"
          class="custom-select"
          style="padding: 12px 16px; border: 1px solid rgba(139, 92, 246, 0.3); color: white; background: rgba(15, 23, 42, 0.6);"
          bind:value={scanGroupName}
          placeholder="เช่น ตรวจเอกสาร UAT รอบที่ 1..."
          on:keydown={(e) => {
            if (e.key === 'Enter' && scanGroupName.trim() !== '') {
              confirmGroup();
            }
          }}
        />
      </div>

      <div class="setting-group relative" style="margin-top: 15px;">
        <label>ประเภท (Type)</label>
        <!-- Custom Dropdown for Group Type -->
        <div class="custom-select" on:click|stopPropagation={() => { groupTypeOpen = !groupTypeOpen; }}>
          <div class="select-trigger" class:open={groupTypeOpen}>
            {scanGroupType}
            <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </div>
          {#if groupTypeOpen}
            <div class="options-menu" transition:fade={{duration: 100}}>
              {#each masterGroupTypes as type}
                <div class="option-item" class:selected={scanGroupType === type} on:click|stopPropagation={() => { scanGroupType = type; groupTypeOpen = false; }}>
                  {type}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>
      
      <button 
        class="btn-primary" 
        style="width: 100%; margin-top: 20px;"
        disabled={!scanGroupName.trim()}
        on:click={confirmGroup}
      >
        ดำเนินการต่อ
      </button>
    </div>

  {:else if !isProcessing && !scanResult}
    <!-- INPUT FORM -->
    <div class="top-nav">
      <button class="btn-back" on:click={() => { selectedProjectStore.set(null); isGroupNameSet = false; scanGroupName = ""; }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>
    </div>

    <div class="header-text">
      <h2>QA Consult - ระบบตรวจสอบเอกสารอัตโนมัติ</h2>
      <p>อัปโหลดเอกสารของคุณเพื่อเปรียบเทียบกับฐานข้อมูล Knowledge Base ของบริษัท และรับรายงานข้อผิดพลาดทางอีเมล</p>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code} - {selectedProjectObj.name}</strong>
        <span style="margin: 0 10px; color: #8b5cf6;">|</span>
        ชื่อการตรวจสอบ: <strong>[{scanGroupType}] {scanGroupName}</strong>
        <button class="btn-text-change" on:click={() => isGroupNameSet = false}>[ แก้ไข ]</button>
      </div>
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
              <div class="file-info" on:click|stopPropagation on:keydown|stopPropagation role="group">
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
          <div class="setting-group relative">
            <label>ประเภทเอกสาร (Document Type)</label>
            <!-- Custom Dropdown for Doc Type -->
            <div class="custom-select" on:click|stopPropagation={() => { docTypeOpen = !docTypeOpen; skillOpen = false; }}>
              <div class="select-trigger" class:open={docTypeOpen}>
                {#if selectedDocTypes.length === 0}
                  <span style="color: #9ca3af;">-- เลือกประเภทเอกสาร --</span>
                {:else if selectedDocTypes.length <= 2}
                  {selectedDocTypes.join(", ")}
                {:else}
                  เลือกแล้ว {selectedDocTypes.length} รายการ
                {/if}
                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </div>
              {#if docTypeOpen}
                <div class="options-menu" transition:fade={{duration: 100}}>
                  {#each docTypes as type}
                    <div class="option-item" class:selected={selectedDocTypes.includes(type)} on:click|stopPropagation={() => toggleDocType(type)}>
                      <input type="checkbox" checked={selectedDocTypes.includes(type)} style="margin-right: 8px; cursor: pointer;" />
                      {type}
                    </div>
                  {/each}
                </div>
              {/if}
            </div>
          </div>

          <div class="setting-group relative">
            <label>ทักษะ AI (AI Skill)</label>
            <!-- Custom Dropdown for Skill -->
            <div class="custom-select" on:click|stopPropagation={() => { skillOpen = !skillOpen; docTypeOpen = false; }}>
              <div class="select-trigger" class:open={skillOpen}>
                {#if selectedSkills.length === 0}
                  <span style="color: #9ca3af;">-- ไม่ใช้ Skill --</span>
                {:else if selectedSkills.length <= 2}
                  {selectedSkills.map(id => skills.find(s => s.skill_id === id)?.skill_name).join(", ")}
                {:else}
                  เลือกแล้ว {selectedSkills.length} ทักษะ
                {/if}
                <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </div>
              {#if skillOpen}
                <div class="options-menu" transition:fade={{duration: 100}}>
                  {#if filteredSkills.length === 0}
                    <div class="option-item" style="color: #9ca3af; justify-content: center; cursor: default;">
                      -- ไม่มีทักษะ AI ที่เกี่ยวข้อง --
                    </div>
                  {:else}
                    {#each filteredSkills as skill}
                      <div class="option-item" class:selected={selectedSkills.includes(skill.skill_id)} on:click|stopPropagation={() => toggleSkill(skill.skill_id)}>
                        <input type="checkbox" checked={selectedSkills.includes(skill.skill_id)} style="margin-right: 8px; cursor: pointer;" />
                        {skill.skill_name}
                      </div>
                    {/each}
                  {/if}
                </div>
              {/if}
            </div>
          </div>

          <div class="setting-group">
            <label>อีเมลผู้รับผลการตรวจสอบ</label>
            <div class="email-input-container">
              <input 
                type="text" 
                bind:value={emailInput} 
                placeholder="ระบุอีเมลแล้วกด Enter หรือปุ่ม +" 
                on:keydown={handleEmailKeydown}
              />
              <button class="btn-add-email" on:click={addEmail} disabled={!emailInput} title="เพิ่มอีเมล">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              </button>
            </div>
            
            {#if emailList.length > 0}
              <div class="email-tags">
                {#each emailList as e, i}
                  <div class="email-tag">
                    {e}
                    <button class="remove-tag" on:click={() => removeEmail(i)}>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
                  </div>
                {/each}
              </div>
            {/if}
            <span class="hint-text">รายงานการเปรียบเทียบจะถูกจัดส่งไปยังอีเมลทั้งหมดนี้</span>
          </div>

          <button class="btn-primary" on:click={processQAConsult} disabled={!file || (emailList.length === 0 && emailInput.trim() === '')}>
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
    <!-- Gate Result Modal Animation -->
    <GateResultModal 
      showModal={showGateModal} 
      resultData={gateResultData} 
      onClose={() => showGateModal = false} 
    />

    <!-- RESULT STATE -->
    <div class="result-state">
      <div class="dashboard-top-bar" style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1); width: 100%; flex-wrap: wrap; gap: 16px;">
        <div class="left-content" style="display: flex; flex-direction: column; gap: 10px;">
          <div class="header-text" style="text-align: left; margin: 0;">
            <h2 style="font-size: 22px; margin-bottom: 2px;">ผลการวิเคราะห์ QA & Exit Criteria Review Gate</h2>
            <p style="font-size: 13px; margin: 0; color: #9ca3af;">ตรวจสอบรายงานด้านล่าง ก่อนกดยืนยันการส่งอีเมล</p>
          </div>
          <div class="result-summary" style="margin: 0; padding: 0; background: none; border: none; justify-content: flex-start; gap: 24px;">
            <div class="summary-item" style="flex-direction: row; align-items: baseline; gap: 8px;">
              <span class="lbl" style="margin: 0;">ส่งผลลัพธ์ไปที่:</span>
              <span class="val" style="margin: 0;">{scanResult.email || "- ไม่ระบุ -"}</span>
            </div>
            <div class="summary-item" style="flex-direction: row; align-items: baseline; gap: 8px;">
              <span class="lbl" style="margin: 0;">จำนวนหน้า:</span>
              <span class="val" style="margin: 0;">{scanResult.total_pages ? scanResult.total_pages + ' หน้า' : '- ไม่ทราบ -'}</span>
            </div>
            {#if scanResult.emailSent}
              <div class="summary-item" style="flex-direction: row; align-items: baseline; gap: 8px;">
                <span class="lbl" style="margin: 0;">สถานะส่งอีเมล:</span>
                <span class="val success" style="margin: 0;">ส่งสำเร็จแล้ว</span>
              </div>
            {/if}
          </div>
        </div>

        <div class="right-actions" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
          {#if scanResult.exit_criteria_eval}
            <button class="btn-outline-glow" on:click={() => { gateResultData = scanResult.exit_criteria_eval; showGateModal = true; }} style="height: 42px; font-weight: 600;">
              ✨ แสดง Modal Animation
            </button>
          {/if}

          <button class="btn-outline" on:click={resetForm} disabled={isSendingEmail} style="padding: 10px 16px; min-width: 0; height: 42px; margin: 0;">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="1 4 1 10 7 10"></polyline><polyline points="23 20 23 14 17 14"></polyline><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"></path></svg>
            เริ่มใหม่
          </button>
          
          {#if scanResult.excel_url}
            <a href={scanResult.excel_url} target="_blank" rel="noopener noreferrer" class="btn-download-excel" style="padding: 10px 16px; margin: 0; height: 42px; border-radius: 8px; font-size: 14px; box-shadow: none;">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              ดาวน์โหลด Excel
            </a>
          {/if}

          <button class="btn-primary" on:click={sendEmail} disabled={isSendingEmail || scanResult.emailSent || !scanResult.email} style="padding: 10px 20px; min-width: 0; height: 42px; margin: 0; border-radius: 8px; font-size: 14px;">
            {#if isSendingEmail}
              กำลังส่ง...
            {:else if scanResult.emailSent}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="20 6 9 17 4 12"></polyline></svg>
              ส่งแล้ว
            {:else}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
              ส่งรายงานเข้าอีเมล
            {/if}
          </button>
        </div>
      </div>

      <!-- QA Findings Report Card -->
      {#if scanResult.qa_findings && scanResult.qa_findings.length > 0}
        <div class="qa-findings-card glass-panel" style="margin-bottom: 24px; overflow-x: auto;">
          <div class="gate-result-header" style="margin-bottom: 16px;">
            <div class="gate-header-title">
              <h3>📊 QA Audit Findings Report</h3>
              <span class="template-badge">ประเด็นที่พบจากการวิเคราะห์</span>
            </div>
            <div class="gate-header-actions">
              <span class="gate-status-pill status-info">
                พบ {scanResult.qa_findings.length} รายการ
              </span>
            </div>
          </div>

          <div class="exit-checklist-table-wrapper">
            <table class="exit-checklist-table">
              <thead>
                <tr>
                  <th style="width: 50px;">ลำดับ</th>
                  <th style="width: 150px;">ประเภทการตรวจ</th>
                  <th>ประเด็นที่พบ (Issue)</th>
                  <th style="width: 100px;">ความรุนแรง</th>
                  <th>สิ่งที่ควรเป็น</th>
                  <th>ข้อเสนอแนะ</th>
                </tr>
              </thead>
              <tbody>
                {#each scanResult.qa_findings as finding, i}
                  <tr class="row-status-{finding.severity === 'Critical' || finding.severity === 'High' ? 'fail' : finding.severity === 'Medium' ? 'na' : 'pass'}">
                    <td class="item-code-cell" style="text-align: center;">{i + 1}</td>
                    <td class="category-cell">{finding.check_type || '-'}</td>
                    <td class="question-cell">
                      <strong>{finding.issue || '-'}</strong>
                      {#if finding.found_incorrect && finding.found_incorrect !== '-'}
                        <div class="evidence-text" style="margin-top: 8px;">
                          <span style="color: #f87171;">ข้อความในเอกสาร:</span> {finding.found_incorrect}
                        </div>
                      {/if}
                    </td>
                    <td class="severity-cell" style="text-align: center;">
                      <span class="badge-sev badge-sev-{finding.severity.toLowerCase()}">{finding.severity}</span>
                    </td>
                    <td class="remarks-cell">{finding.correct_value || '-'}</td>
                    <td class="remarks-cell">{finding.recommendation || '-'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      <!-- Exit Criteria Review Gate Card -->
      {#if scanResult.exit_criteria_eval}
        <div class="exit-criteria-gate-result-card glass-panel" style="margin-bottom: 24px;">
          <div class="gate-result-header">
            <div class="gate-header-title">
              <h3>📋 ผลการประเมิน Exit Criteria Review Gate</h3>
              <span class="template-badge">{scanResult.exit_criteria_eval.template_title}</span>
            </div>
            <div class="gate-header-actions">
              <span class="gate-status-pill status-{scanResult.exit_criteria_eval.status.toLowerCase()}">
                {scanResult.exit_criteria_eval.status}
              </span>
            </div>
          </div>

          <div class="gate-summary-bar">
            <div class="summary-stat">
              <span class="stat-num">{scanResult.exit_criteria_eval.score_percentage}%</span>
              <span class="stat-lbl">คะแนนสมบูรณ์</span>
            </div>
            <div class="summary-stat green">
              <span class="stat-num">{scanResult.exit_criteria_eval.passed_items}</span>
              <span class="stat-lbl">ผ่าน (PASS)</span>
            </div>
            <div class="summary-stat red">
              <span class="stat-num">{scanResult.exit_criteria_eval.failed_items}</span>
              <span class="stat-lbl">ไม่ผ่าน (FAIL)</span>
            </div>
            <div class="summary-stat gray">
              <span class="stat-num">{scanResult.exit_criteria_eval.na_items}</span>
              <span class="stat-lbl">ข้าม (N/A)</span>
            </div>
          </div>

          <!-- Categorized Checklist Items -->
          <div class="exit-checklist-table-wrapper">
            <table class="exit-checklist-table">
              <thead>
                <tr>
                  <th style="width: 70px;">ข้อตรวจ</th>
                  <th style="width: 180px;">หมวดหมู่</th>
                  <th>รายการประเมิน (Checklist Item)</th>
                  <th style="width: 150px;">📊 ตัวชี้วัด (KPI Indicator)</th>
                  <th style="width: 90px;">ความรุนแรง</th>
                  <th style="width: 95px;">ผลการตรวจ</th>
                  <th>ข้อสังเกต / ร่องรอยที่พบ</th>
                </tr>
              </thead>
              <tbody>
                {#each scanResult.exit_criteria_eval.items as item}
                  <tr class="row-status-{item.status.toLowerCase()}">
                    <td class="item-code-cell"><strong>{item.item_code}</strong></td>
                    <td class="category-cell">{item.category}</td>
                    <td class="question-cell">{item.question_text}</td>
                    <td class="metric-cell">
                      <span class="badge-metric">{item.target_metric || '100% (ผ่านบริบูรณ์)'}</span>
                    </td>
                    <td class="severity-cell">
                      <span class="badge-sev badge-sev-{item.severity.toLowerCase()}">{item.severity}</span>
                    </td>
                    <td class="status-cell">
                      <span class="badge-status status-tag-{item.status.toLowerCase()}">
                        {item.status === 'PASS' ? '✅ PASS' : item.status === 'FAIL' ? '❌ FAIL' : '⚪ N/A'}
                      </span>
                    </td>
                    <td class="remarks-cell">
                      <div class="remark-text">{item.remarks}</div>
                      {#if item.evidence_text}
                        <div class="evidence-text">🔎 <em>{item.evidence_text}</em></div>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      <div class="report-box email-preview" style="max-height: none;">
        <div class="email-header">
          <h2>Spectra QA Consult Report</h2>
        </div>
        <div class="email-body">
          <p>เรียนผู้ใช้งาน,</p>
          <p>ระบบ Spectra QA ได้ทำการตรวจสอบเอกสาร <b>{scanResult.filename || 'ไม่ระบุชื่อไฟล์'}</b> ประเภท <b>{scanResult.doc_type || 'ไม่ระบุประเภท'}</b> เรียบร้อยแล้ว</p>
          <p>นี่คือผลการวิเคราะห์และเปรียบเทียบกับฐานข้อมูล Knowledge Base:</p>
          <hr>
          {#if scanResult.report}
            <pre>{scanResult.report}</pre>
          {:else}
            <div style="color: red; padding: 10px; background: #fee2e2; border-radius: 4px;">
              ไม่พบเนื้อหารายงาน (AI ไม่ได้ส่งข้อความกลับมา หรือเกิดข้อผิดพลาดในการรับข้อมูล)<br>
              <pre style="font-size: 11px; margin-top: 10px;">{JSON.stringify(scanResult, null, 2)}</pre>
            </div>
          {/if}
          <hr>
          <p class="footer-note"><small>สร้างโดย Spectra QA Intelligent Analysis System</small></p>
        </div>
      </div>
    </div>
  {/if}
</div>

{#if showConfirmModal}
  <div class="modal-backdrop" transition:fade={{duration: 200}}>
    <div class="modal-card">
      <div class="modal-icon warning">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
      </div>
      <h3>ยืนยันการส่งอีเมล</h3>
      <p>คุณต้องการส่งรายงานผลการตรวจสอบนี้ ไปยังอีเมล <b>{email}</b> ใช่หรือไม่?</p>
      <div class="modal-actions">
        <button class="btn-outline" on:click={() => showConfirmModal = false} disabled={isSendingEmail}>ยกเลิก</button>
        <button class="btn-primary" on:click={executeSendEmail} disabled={isSendingEmail}>
          {#if isSendingEmail}กำลังส่ง...{:else}ยืนยันส่งอีเมล{/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showSuccessModal}
  <div class="modal-backdrop" transition:fade={{duration: 200}}>
    <div class="modal-card">
      <div class="modal-icon success">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="32" height="32"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
      </div>
      <h3>ส่งอีเมลสำเร็จ</h3>
      <p>รายงานถูกส่งไปยัง <b>{email}</b> เรียบร้อยแล้ว</p>
      <div class="modal-actions centered">
        <button class="btn-primary" on:click={() => showSuccessModal = false}>ตกลง</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .qa-container {
    width: 100%;
    max-width: 1400px;
    height: 100%;
    margin: 0 auto;
    padding: 20px 40px;
    display: flex;
    flex-direction: column;
    gap: 30px;
    overflow-y: auto;
  }
  .qa-container.full-width {
    max-width: 100%;
    padding: 20px 20px;
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
  
  /* Input Email */
  .email-input-container input {
    background: rgba(0,0,0,0.2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 15px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .email-input-container input:focus {
    border-color: #9333ea;
    box-shadow: 0 0 0 2px rgba(147, 51, 234, 0.2);
  }

  /* Custom Select Dropdowns */
  .relative {
    position: relative;
  }
  .custom-select {
    position: relative;
    user-select: none;
    cursor: pointer;
  }
  .select-trigger {
    background: rgba(18, 20, 28, 0.85);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #f8fafc;
    padding: 12px 16px;
    border-radius: 12px;
    font-size: 14px;
    font-weight: 500;
    display: flex;
    justify-content: space-between;
    align-items: center;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.08);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .select-trigger:hover {
    border-color: rgba(168, 85, 247, 0.75);
    background-color: rgba(28, 30, 46, 0.95);
    box-shadow: 0 6px 20px rgba(168, 85, 247, 0.3);
    transform: translateY(-1px);
  }
  .select-trigger.open {
    border-color: var(--secondary);
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.35), 0 8px 24px rgba(168, 85, 247, 0.35);
  }
  .select-trigger .chevron {
    width: 18px;
    height: 18px;
    color: #a855f7;
    transition: transform 0.25s ease-in-out;
  }
  .select-trigger.open .chevron {
    transform: rotate(180deg);
  }
  .options-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    width: 100%;
    background: rgba(15, 17, 26, 0.95); /* deep dark glass background */
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(168, 85, 247, 0.15);
    z-index: 100;
    max-height: 240px;
    overflow-y: auto;
    padding: 6px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
  }
  /* Custom scrollbar for options menu */
  .options-menu::-webkit-scrollbar {
    width: 6px;
  }
  .options-menu::-webkit-scrollbar-thumb {
    background: rgba(168, 85, 247, 0.4);
    border-radius: 4px;
  }
  .option-item {
    padding: 10px 14px;
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 13.5px;
    display: flex;
    align-items: center;
    transition: all 0.2s ease;
  }
  .option-item:hover {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(168, 85, 247, 0.3));
    color: #ffffff;
    transform: translateX(3px);
  }
  .option-item.selected {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.5), rgba(168, 85, 247, 0.5));
    color: #ffffff;
    font-weight: 600;
  }

  .hint-text {
    font-size: 12px;
    color: var(--text3);
  }

  .email-input-container {
    display: flex;
    gap: 8px;
  }
  .email-input-container input {
    flex: 1;
  }
  .btn-add-email {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-main);
    width: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-add-email:hover:not(:disabled) {
    background: #9333ea;
    border-color: #9333ea;
  }
  .btn-add-email:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .email-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
  }
  .email-tag {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(147, 51, 234, 0.2);
    border: 1px solid rgba(147, 51, 234, 0.5);
    padding: 4px 10px;
    border-radius: 16px;
    font-size: 13px;
    color: #d8b4fe;
  }
  .remove-tag {
    background: none;
    border: none;
    color: #d8b4fe;
    cursor: pointer;
    padding: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: background 0.2s;
  }
  .remove-tag:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
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
  .loading-state {
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
  
  /* Result State */
  .result-state {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    justify-content: flex-start;
    padding: 24px 32px;
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
  
  /* Top Navigation / Back Button */
  .top-nav {
    position: absolute;
    top: 30px;
    left: 40px;
    z-index: 50;
  }
  .btn-back {
    display: flex;
    align-items: center;
    gap: 8px;
    background: transparent;
    border: none;
    color: #9ca3af;
    font-size: 14px;
    cursor: pointer;
    padding: 8px 12px;
    border-radius: 8px;
    transition: all 0.2s;
  }
  .btn-back:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.05);
  }

  /* Project Selection Styles */
  .project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px;
    width: 100%;
  }
  .project-card {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    text-align: left;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(10px);
  }
  .project-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent);
  }
  .project-card:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(147, 51, 234, 0.5);
    box-shadow: 0 12px 30px -10px rgba(147, 51, 234, 0.4);
    transform: translateY(-4px);
  }
  .p-code {
    font-size: 12px;
    color: #c084fc;
    font-weight: 700;
    margin-bottom: 12px;
    background: rgba(147, 51, 234, 0.15);
    padding: 6px 12px;
    border-radius: 6px;
    display: inline-block;
    letter-spacing: 0.5px;
  }
  .p-name {
    font-size: 18px;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 20px;
    line-height: 1.4;
  }
  .p-status-section {
    margin-bottom: 16px;
  }
  .p-desc-section {
    margin-bottom: 0;
  }
  .p-meta-label {
    font-size: 12px;
    color: #ffffff;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .p-status-value {
    font-size: 15px;
    font-weight: 600;
  }
  .p-status-value.active {
    color: #22c55e; /* Green */
  }
  .p-status-value.inactive {
    color: #ef4444; /* Red */
  }
  .p-desc-box {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 14px;
    color: #e5e7eb;
    line-height: 1.5;
    min-height: 48px;
  }
  .empty-desc {
    color: #9ca3af;
  }
  .empty-state {
    grid-column: 1 / -1;
    text-align: center;
    padding: 40px;
    background: rgba(0,0,0,0.2);
    border-radius: 12px;
    color: var(--text3);
    border: 1px dashed var(--border);
  }
  .active-project-badge {
    margin-top: 15px;
    font-size: 14px;
    color: var(--text2);
    background: rgba(147, 51, 234, 0.1);
    padding: 8px 16px;
    border-radius: 8px;
    display: inline-block;
    border: 1px solid rgba(147, 51, 234, 0.3);
  }
  .active-project-badge strong {
    color: #d8b4fe;
    font-weight: 600;
  }
  .btn-text-change {
    background: none;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    font-size: 13px;
    margin-left: 10px;
    padding: 0;
    transition: color 0.2s;
  }
  .btn-text-change:hover {
    color: #fff;
    text-decoration: underline;
  }

  .report-box.email-preview {
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 0;
    margin-bottom: 24px;
    text-align: left;
    max-height: 60vh;
    overflow-y: auto;
    width: 100%;
    color: #333;
    font-family: Arial, sans-serif;
  }
  .email-header {
    background-color: #7c3aed;
    color: white;
    padding: 16px 24px;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .email-header h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }
  .email-body {
    padding: 24px;
  }
  .email-body p {
    color: #333;
    margin-bottom: 12px;
    font-size: 15px;
  }
  .email-body hr {
    border: 0;
    border-top: 1px solid #e5e7eb;
    margin: 20px 0;
  }
  .email-body pre {
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
    font-size: 15px;
    line-height: 1.6;
    color: #333;
    margin: 0;
  }
  .footer-note {
    margin-bottom: 0 !important;
    color: #6b7280 !important;
  }

  .report-box::-webkit-scrollbar {
    width: 8px;
  }
  .report-box::-webkit-scrollbar-thumb {
    background: rgba(0,0,0,0.2);
    border-radius: 4px;
  }

  .result-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    background: rgba(255, 255, 255, 0.03);
    padding: 16px 24px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.05);
    margin-bottom: 20px;
    justify-content: center;
  }
  .summary-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .summary-item .lbl {
    font-size: 13px;
    color: var(--text3);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .summary-item .val {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-main);
  }
  .summary-item .val.success {
    color: #10b981;
  }

  .action-buttons {
    display: flex;
    justify-content: center;
    gap: 16px;
    margin-top: 10px;
    width: 100%;
  }
  .action-buttons .btn-primary, .action-buttons .btn-outline {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 0;
    min-width: 180px;
    padding: 12px 24px;
  }

  /* Modals */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .modal-card {
    background: #1e1e2d;
    border: 1px solid #333;
    border-radius: 16px;
    padding: 32px;
    width: 90%;
    max-width: 400px;
    text-align: center;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
  }
  .modal-icon {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 20px;
  }
  .modal-icon.warning {
    background: rgba(245, 158, 11, 0.1);
    color: #f59e0b;
  }
  .modal-icon.success {
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
  }
  .modal-card h3 {
    margin: 0 0 12px;
    font-size: 20px;
    color: white;
  }
  .modal-card p {
    color: #9ca3af;
    margin: 0 0 24px;
    line-height: 1.5;
  }
  .modal-card b {
    color: white;
  }
  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: stretch;
  }
  .modal-actions.centered {
    justify-content: center;
  }
  .modal-actions button {
    flex: 1;
    margin: 0;
  }
  .modal-actions.centered button {
    flex: none;
    min-width: 120px;
  }

  /* Excel Download Section */
  .excel-download-section {
    margin: 20px 0;
  }
  .excel-badge {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 18px 24px;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.08), rgba(59, 130, 246, 0.08));
    border: 1px solid rgba(124, 58, 237, 0.25);
    border-radius: 14px;
    transition: all 0.25s ease;
  }
  .excel-badge:hover {
    border-color: rgba(124, 58, 237, 0.45);
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.12), rgba(59, 130, 246, 0.12));
  }
  .excel-badge > svg {
    color: #10b981;
    flex-shrink: 0;
  }
  .excel-info {
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex: 1;
  }
  .excel-title {
    font-weight: 600;
    font-size: 14px;
    color: white;
  }
  .excel-desc {
    font-size: 12px;
    color: #9ca3af;
  }
  .btn-download-excel {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 22px;
    background: linear-gradient(135deg, #10b981, #059669);
    color: white;
    text-decoration: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s ease;
    white-space: nowrap;
    box-shadow: 0 4px 14px rgba(16, 185, 129, 0.25);
  }
  .btn-download-excel:hover {
    background: linear-gradient(135deg, #059669, #047857);
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(16, 185, 129, 0.35);
  }

  /* Exit Criteria Gate Card & Table Styles */
  .exit-criteria-gate-result-card {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 20px 24px;
    backdrop-filter: blur(12px);
  }

  .gate-result-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    padding-bottom: 14px;
    margin-bottom: 16px;
  }

  .gate-header-title {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .gate-header-title h3 {
    margin: 0;
    font-size: 1.15rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .template-badge {
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(99, 102, 241, 0.4);
    color: #a5b4fc;
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 14px;
  }

  .btn-outline-glow {
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.4);
    color: #c7d2fe;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-outline-glow:hover {
    background: rgba(99, 102, 241, 0.3);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
  }

  .gate-status-pill {
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .gate-status-pill.status-passed { background: #059669; color: #ffffff; }
  .gate-status-pill.status-conditional_passed { background: #d97706; color: #ffffff; }
  .gate-status-pill.status-rejected { background: #dc2626; color: #ffffff; }

  .gate-summary-bar {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }

  .summary-stat {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .summary-stat.green { background: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.3); }
  .summary-stat.red { background: rgba(239, 68, 68, 0.12); border-color: rgba(239, 68, 68, 0.3); }
  .summary-stat.gray { background: rgba(148, 163, 184, 0.12); border-color: rgba(148, 163, 184, 0.3); }

  .stat-num { font-size: 1.25rem; font-weight: 700; color: #f8fafc; }
  .summary-stat.green .stat-num { color: #34d399; }
  .summary-stat.red .stat-num { color: #f87171; }
  .summary-stat.gray .stat-num { color: #94a3b8; }

  .stat-lbl { font-size: 0.75rem; color: #94a3b8; margin-top: 2px; }

  .exit-checklist-table-wrapper {
    overflow-x: auto;
  }

  .exit-checklist-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  .exit-checklist-table th {
    background: rgba(30, 41, 59, 0.9);
    color: #cbd5e1;
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  }

  .exit-checklist-table td {
    padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    color: #e2e8f0;
    vertical-align: top;
  }

  .row-status-fail { background: rgba(239, 68, 68, 0.06); }
  .row-status-pass { background: rgba(16, 185, 129, 0.02); }

  .badge-status {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .status-tag-pass { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
  .status-tag-fail { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
  .status-tag-na { background: rgba(148, 163, 184, 0.2); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.4); }

  .badge-sev {
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.72rem;
    font-weight: 600;
  }
  .badge-sev-critical { background: rgba(239, 68, 68, 0.2); color: #f87171; }
  .badge-sev-major { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
  .badge-sev-minor { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }

  .badge-metric {
    display: inline-block;
    padding: 3px 8px;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #c7d2fe;
    border-radius: 6px;
    font-size: 0.76rem;
    font-weight: 600;
  }

  .evidence-text {
    margin-top: 4px;
    font-size: 0.78rem;
    color: #fbbf24;
  }
</style>
