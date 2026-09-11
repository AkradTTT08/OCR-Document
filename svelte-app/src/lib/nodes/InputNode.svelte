<script>
  import { Handle, Position, useSvelteFlow } from '@xyflow/svelte';
  export let id;
  export let data;

  const { deleteElements } = useSvelteFlow();

  function deleteNode() {
    deleteElements({ nodes: [{ id }] });
  }
</script>

<div class="custom-node input-node">
  <Handle type="target" position={Position.Left} isConnectable={true} />
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
    <span>Input Data</span>
    <button class="delete-btn" on:click|stopPropagation={deleteNode} title="ลบ Card นี้">✕</button>
  </div>
  <div class="node-content">
    <textarea bind:value={data.text} placeholder="ป้อนคำสั่งเริ่มต้น หรือเนื้อหา..."></textarea>
  </div>
  <Handle type="source" position={Position.Right} isConnectable={true} />
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
    position: relative;
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
