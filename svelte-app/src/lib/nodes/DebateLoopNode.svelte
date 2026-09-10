<script>
  import { Handle, Position } from '@xyflow/svelte';
  export let data;
</script>

<div class="custom-node debate-node">
  <Handle type="target" position={Position.Left} />
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.92-10.26l1.08 1.08"></path></svg>
    <span>Iterative Debate Loop</span>
  </div>
  <div class="node-content">
    <div class="agent-row">
      <div>
        <label>Generator Agent:</label>
        <select bind:value={data.generator}>
          <option value="qa_doc_create">QA Doc Creator</option>
          <option value="qa_consult">QA Consult</option>
        </select>
      </div>
      <div class="vs-badge">VS</div>
      <div>
        <label>Critic Agent:</label>
        <select bind:value={data.critic}>
          <option value="qa_consult">QA Consult</option>
          <option value="qa_security_scan">QA Security Scanner</option>
        </select>
      </div>
    </div>
    
    <label>Max Loops (Iterations):</label>
    <input type="number" min="1" max="10" bind:value={data.max_loops} />
    
    <label>Project ID (Optional):</label>
    <input type="text" bind:value={data.project_id} placeholder="UUID" />
  </div>
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .custom-node {
    background: #1e1e2d;
    border: 1px solid #fbbf24;
    border-radius: 8px;
    padding: 10px;
    width: 280px;
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
    color: #fcd34d;
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
  .vs-badge {
    font-size: 10px;
    font-weight: bold;
    color: #fb7185;
    background: rgba(251, 113, 133, 0.2);
    padding: 2px 4px;
    border-radius: 4px;
  }
  label {
    font-size: 10px;
    color: #a1a1aa;
    display: block;
    margin-bottom: 2px;
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
