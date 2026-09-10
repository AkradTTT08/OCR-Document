<script>
  import { Handle, Position } from '@xyflow/svelte';
  export let data;
</script>

<div class="custom-node input-node">
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
    <span>Input Data</span>
  </div>
  <div class="node-content">
    <textarea bind:value={data.text} placeholder="ป้อนคำสั่งเริ่มต้น หรือเนื้อหา..."></textarea>
  </div>
  <Handle type="source" position={Position.Right} />
</div>

<style>
  .custom-node {
    background: #1e1e2d;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 10px;
    width: 250px;
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
    color: #4ade80;
  }
  textarea {
    width: 100%;
    height: 60px;
    background: #0f111a;
    border: 1px solid #3f3f46;
    color: white;
    border-radius: 4px;
    padding: 6px;
    font-size: 12px;
    resize: none;
  }
</style>
