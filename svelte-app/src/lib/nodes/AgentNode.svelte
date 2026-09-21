<script>
  import { Handle, Position, useSvelteFlow } from '@xyflow/svelte';
  import { onMount } from 'svelte';
  import { selectedProjectStore } from '../qaHistoryStore.js';
  export let id;
  export let data;

  const { deleteElements } = useSvelteFlow();
  
  let showConfig = false;
  let skills = [];
  let docTypes = [];

  onMount(async () => {
    // Load Skills
    try {
      const resSkills = await fetch("/api/skills");
      if (resSkills.ok) {
        const d = await resSkills.json();
        skills = d.skills || [];
      }
    } catch (e) { console.error("AgentNode load skills error:", e); }

    // Load Doc Types
    try {
      let url = "/api/doc_types";
      if ($selectedProjectStore) {
        const pid = $selectedProjectStore.id || $selectedProjectStore.project_id;
        url += `?project_id=${pid}`;
      }
      const resDoc = await fetch(url);
      if (resDoc.ok) {
        docTypes = await resDoc.json();
      }
    } catch (e) { console.error("AgentNode load doc types error:", e); }
  });

  function deleteNode() {
    deleteElements({ nodes: [{ id }] });
  }
</script>

<div class="custom-node agent-node">
  <Handle type="target" position={Position.Left} isConnectable={true} />
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>
    <span>AI Agent</span>
    <button class="delete-btn" on:click|stopPropagation={deleteNode} title="ลบ Card นี้">✕</button>
  </div>
  <div class="node-content">
    <label>Agent Type:</label>
    <div class="agent-select-row">
      <select bind:value={data.agent_type} class="nodrag">
        <option value="qa_doc_create">QA Doc Creator</option>
        <option value="qa_consult">QA Consult (Reviewer)</option>
        <option value="qa_security_scan">QA Security Scanner</option>
        <option value="qa_research">QA Researcher</option>
      </select>
      <button class="btn-config nodrag" on:click={() => showConfig = !showConfig} title="ตั้งค่ากระบวนการทำงาน">
        ⚙️
      </button>
    </div>

    {#if showConfig}
      <div class="config-area nodrag">
        <label>ประเภทเอกสาร (Document Type):</label>
        <select bind:value={data.doc_type} class="config-select">
          <option value="">-- ไม่ระบุ --</option>
          {#each docTypes as dt}
            <option value={dt}>{dt}</option>
          {/each}
        </select>
        
        <label>ทักษะ AI (AI Skill):</label>
        <select bind:value={data.skill_id} class="config-select">
          <option value="">-- ไม่ใช้ Skill --</option>
          {#each skills as s}
            <option value={s.skill_id}>{s.skill_name}</option>
          {/each}
        </select>

        <label>อีเมลผู้รับผลการตรวจสอบ (คั่นด้วยลูกน้ำ):</label>
        <input type="text" bind:value={data.emails} placeholder="เช่น user@domain.com, admin@domain.com" class="config-input" />

        <label>คำสั่งเพิ่มเติม (Instructions):</label>
        <textarea bind:value={data.instructions} placeholder="กรุณากรอกกระบวนการหรือคำสั่งสำหรับ Agent นี้..."></textarea>
      </div>
    {/if}
  </div>
  <Handle type="source" position={Position.Right} isConnectable={true} />
</div>

<style>
  .custom-node {
    background: #1e1e2d;
    border: 1px solid #6366f1;
    border-radius: 8px;
    padding: 10px;
    width: 320px;
    color: white;
    font-family: sans-serif;
    position: relative;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: bold;
    font-size: 12px;
    margin-bottom: 10px;
    color: #a78bfa;
  }
  .delete-btn {
    margin-left: auto;
    background: transparent;
    border: none;
    color: #ef4444;
    cursor: pointer;
    font-size: 14px;
    font-weight: bold;
    padding: 0 4px;
    border-radius: 4px;
    transition: background 0.2s;
  }
  .delete-btn:hover {
    background: rgba(239, 68, 68, 0.2);
  }
  .node-content {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  label {
    font-size: 11px;
    color: #a1a1aa;
    margin-bottom: 4px;
    display: block;
  }
  input {
    width: 100%;
    background: #0f111a;
    border: 1px solid #3f3f46;
    color: white;
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 12px;
    outline: none;
    transition: all 0.2s;
  }
  input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }
  select {
    width: 100%;
    background: #0f111a;
    border: 1px solid #3f3f46;
    color: #e5e7eb;
    border-radius: 6px;
    padding: 6px 24px 6px 8px; /* space for arrow */
    font-size: 12px;
    font-weight: 500;
    appearance: none;
    background-image: url("data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a1a1aa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    background-size: 14px;
    outline: none;
    transition: all 0.2s;
    cursor: pointer;
    text-overflow: ellipsis;
  }
  select:hover {
    border-color: #6366f1;
  }
  select:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }
  select option {
    background: #1e1e2d;
    color: white;
  }
  .agent-select-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .btn-config {
    background: #374151;
    border: 1px solid #4b5563;
    color: white;
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }
  .btn-config:hover {
    background: #4b5563;
    border-color: #6366f1;
  }
  .config-area {
    margin-top: 8px;
    background: rgba(0,0,0,0.3);
    padding: 10px;
    border-radius: 6px;
    border: 1px solid #3f3f46;
  }
  .config-area textarea {
    width: 100%;
    height: 80px;
    background: #0f111a;
    border: 1px solid #3f3f46;
    color: white;
    border-radius: 4px;
    padding: 8px;
    font-size: 11px;
    resize: vertical;
    outline: none;
    transition: all 0.2s;
  }
  .config-area textarea:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }
  .config-area .config-input {
    width: 100%;
    background: #0f111a;
    border: 1px solid #3f3f46;
    color: white;
    border-radius: 4px;
    padding: 8px;
    font-size: 11px;
    outline: none;
    transition: all 0.2s;
    margin-bottom: 8px;
  }
  .config-area .config-input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }
  .config-area .config-select {
    width: 100%;
    background: #0f111a;
    border: 1px solid #3f3f46;
    color: #e5e7eb;
    border-radius: 4px;
    padding: 8px 24px 8px 8px;
    font-size: 11px;
    appearance: none;
    background-image: url("data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a1a1aa' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    background-size: 12px;
    outline: none;
    transition: all 0.2s;
    cursor: pointer;
    margin-bottom: 8px;
  }
  .config-area .config-select:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
  }
</style>
