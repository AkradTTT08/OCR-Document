<script>
  import { Handle, Position, useSvelteFlow } from '@xyflow/svelte';
  import { onMount } from 'svelte';
  import { selectedProjectStore } from '../qaHistoryStore.js';
  import { getCachedSkills, getCachedDocTypes } from './nodeMetadataCache.js';
  export let id;
  export let data;

  const { deleteElements } = useSvelteFlow();
  
  let showGenConfig = false;
  let showCriticConfig = false;
  let skills = [];
  let docTypes = [];

  onMount(async () => {
    const pid = $selectedProjectStore ? ($selectedProjectStore.id || $selectedProjectStore.project_id) : '';
    const [loadedSkills, loadedDocTypes] = await Promise.all([
      getCachedSkills(),
      getCachedDocTypes(pid)
    ]);
    skills = loadedSkills;
    docTypes = loadedDocTypes;
  });

  function deleteNode() {
    deleteElements({ nodes: [{ id }] });
  }
</script>

<div class="custom-node debate-node">
  <Handle type="target" position={Position.Left} isConnectable={true} />
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.92-10.26l1.08 1.08"></path></svg>
    <span>Iterative Debate Loop</span>
    <button type="button" class="delete-btn" aria-label="ลบ Node นี้" on:click|stopPropagation={deleteNode} title="ลบ Card นี้">✕</button>
  </div>
  <div class="node-content">
    <div class="agent-row">
      <div class="agent-select-wrapper">
        <label for="{id}-gen-agent">Generator Agent:</label>
        <div class="agent-select-inner">
          <select id="{id}-gen-agent" bind:value={data.generator} class="nodrag">
            <option value="qa_doc_create">QA Doc Creator</option>
            <option value="qa_consult">QA Consult</option>
          </select>
          <button type="button" class="btn-config nodrag" aria-label="ตั้งค่า Generator" aria-expanded={showGenConfig} on:click={() => {showGenConfig = !showGenConfig; showCriticConfig = false;}} title="ตั้งค่า Generator">⚙️</button>
        </div>
      </div>
      <div class="vs-badge">VS</div>
      <div class="agent-select-wrapper">
        <label for="{id}-critic-agent">Critic Agent:</label>
        <div class="agent-select-inner">
          <select id="{id}-critic-agent" bind:value={data.critic} class="nodrag">
            <option value="qa_consult">QA Consult</option>
            <option value="qa_security_scan">QA Security Scanner</option>
          </select>
          <button type="button" class="btn-config nodrag" aria-label="ตั้งค่า Critic" aria-expanded={showCriticConfig} on:click={() => {showCriticConfig = !showCriticConfig; showGenConfig = false;}} title="ตั้งค่า Critic">⚙️</button>
        </div>
      </div>
    </div>
    
    {#if showGenConfig}
      <div class="config-area nodrag">
        <div style="margin-bottom: 8px; color: #a78bfa; font-weight: bold; font-size: 12px;">ตั้งค่า Generator Agent</div>
        
        <label for="{id}-gen-doc-type">ประเภทเอกสาร (Document Type):</label>
        <select id="{id}-gen-doc-type" bind:value={data.generator_doc_type} class="config-select">
          <option value="">-- ไม่ระบุ --</option>
          {#each docTypes as dt}
            <option value={dt}>{dt}</option>
          {/each}
        </select>
        
        <label for="{id}-gen-skill-id">ทักษะ AI (AI Skill):</label>
        <select id="{id}-gen-skill-id" bind:value={data.generator_skill_id} class="config-select">
          <option value="">-- ไม่ใช้ Skill --</option>
          {#each skills as s}
            <option value={s.skill_id}>{s.skill_name}</option>
          {/each}
        </select>

        <label for="{id}-gen-emails">อีเมลผู้รับผลการตรวจสอบ:</label>
        <input id="{id}-gen-emails" type="text" bind:value={data.generator_emails} placeholder="เช่น user@domain.com" class="config-input" />

        <label for="{id}-gen-instructions">คำสั่งเพิ่มเติม (Instructions):</label>
        <textarea id="{id}-gen-instructions" bind:value={data.generator_instructions} placeholder="กรอกคำสั่งหรือหน้าที่ของ Generator Agent..."></textarea>
      </div>
    {/if}
    {#if showCriticConfig}
      <div class="config-area nodrag">
        <div style="margin-bottom: 8px; color: #fb7185; font-weight: bold; font-size: 12px;">ตั้งค่า Critic Agent</div>

        <label for="{id}-critic-doc-type">ประเภทเอกสาร (Document Type):</label>
        <select id="{id}-critic-doc-type" bind:value={data.critic_doc_type} class="config-select">
          <option value="">-- ไม่ระบุ --</option>
          {#each docTypes as dt}
            <option value={dt}>{dt}</option>
          {/each}
        </select>
        
        <label for="{id}-critic-skill-id">ทักษะ AI (AI Skill):</label>
        <select id="{id}-critic-skill-id" bind:value={data.critic_skill_id} class="config-select">
          <option value="">-- ไม่ใช้ Skill --</option>
          {#each skills as s}
            <option value={s.skill_id}>{s.skill_name}</option>
          {/each}
        </select>

        <label for="{id}-critic-emails">อีเมลผู้รับผลการตรวจสอบ:</label>
        <input id="{id}-critic-emails" type="text" bind:value={data.critic_emails} placeholder="เช่น user@domain.com" class="config-input" />

        <label for="{id}-critic-instructions">คำสั่งเพิ่มเติม (Instructions):</label>
        <textarea id="{id}-critic-instructions" bind:value={data.critic_instructions} placeholder="กรอกคำสั่งหรือหน้าที่ของ Critic Agent..."></textarea>
      </div>
    {/if}
    
    <label for="{id}-max-loops">Max Loops (Iterations):</label>
    <input id="{id}-max-loops" class="nodrag" type="number" min="1" max="10" bind:value={data.max_loops} />
  </div>
  <Handle type="source" position={Position.Right} isConnectable={true} />
</div>

<style>
  .custom-node {
    background: var(--bg2, #12141c);
    border: 1px solid var(--warning, #f59e0b);
    border-radius: var(--radius-sm, 8px);
    padding: 12px;
    width: 450px;
    max-width: calc(100vw - 48px);
    color: var(--text-main, #f8fafc);
    font-family: var(--font-th, 'Prompt', sans-serif);
    position: relative;
  }
  .node-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 12px;
    margin-bottom: 10px;
    color: #fcd34d;
  }
  .delete-btn {
    margin-left: auto;
    background: transparent;
    border: none;
    color: var(--danger, #f43f5e);
    cursor: pointer;
    font-size: 13px;
    font-weight: 700;
    width: 28px;
    height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    transition: background 0.2s;
  }
  .delete-btn:hover {
    background: rgba(244, 63, 94, 0.18);
  }
  .node-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .agent-row {
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(0,0,0,0.2);
    padding: 8px;
    border-radius: 4px;
  }
  .agent-row > div:not(.vs-badge) {
    flex: 1;
    min-width: 0;
  }
  .vs-badge {
    font-size: 10px;
    font-weight: bold;
    color: #fb7185;
    background: rgba(251, 113, 133, 0.2);
    padding: 2px 4px;
    border-radius: 4px;
    flex-shrink: 0;
  }
  label {
    font-size: 11px;
    color: #a1a1aa;
    display: block;
    margin-bottom: 4px;
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
    border-color: #fbbf24;
    box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.2);
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
    border-color: #fbbf24;
  }
  select:focus {
    border-color: #fbbf24;
    box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.2);
  }
  select option {
    background: #1e1e2d;
    color: white;
  }
  .agent-select-inner {
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
    border-color: #fbbf24;
  }
  .config-area {
    margin-top: 8px;
    margin-bottom: 8px;
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
    border-color: #fbbf24;
    box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.2);
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
    border-color: #fbbf24;
    box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.2);
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
    border-color: #fbbf24;
    box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.2);
  }
</style>
