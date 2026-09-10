<script>
  import { Handle, Position } from '@xyflow/svelte';
  export let data;
</script>

<div class="custom-node agent-node">
  <Handle type="target" position={Position.Left} />
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>
    <span>AI Agent</span>
  </div>
  <div class="node-content">
    <label>Agent Type:</label>
    <select bind:value={data.agent_type}>
      <option value="qa_doc_create">QA Doc Creator</option>
      <option value="qa_consult">QA Consult (Reviewer)</option>
      <option value="qa_security_scan">QA Security Scanner</option>
      <option value="qa_research">QA Researcher</option>
    </select>
    
    {#if ['qa_doc_create', 'qa_consult', 'qa_research'].includes(data.agent_type)}
      <label>Project ID (Optional):</label>
      <input type="text" bind:value={data.project_id} placeholder="UUID" />
    {/if}
  </div>
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .custom-node {
    background: #1e1e2d;
    border: 1px solid #6366f1;
    border-radius: 8px;
    padding: 10px;
    width: 220px;
    color: white;
    font-family: sans-serif;
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
  .node-content {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  label {
    font-size: 10px;
    color: #a1a1aa;
  }
  select, input {
    width: 100%;
    background: #0f111a;
    border: 1px solid #3f3f46;
    color: white;
    border-radius: 4px;
    padding: 4px 6px;
    font-size: 11px;
  }
</style>
