<script>
  import { Handle, Position, useSvelteFlow } from '@xyflow/svelte';
  export let id;
  export let data;

  const { deleteElements } = useSvelteFlow();

  function deleteNode() {
    deleteElements({ nodes: [{ id }] });
  }
</script>

<div class="custom-node output-node">
  <Handle type="target" position={Position.Left} isConnectable={true} />
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path></svg>
    <span>Final Output</span>
    <button class="delete-btn" on:click|stopPropagation={deleteNode} title="ลบ Card นี้">✕</button>
  </div>
  <div class="node-content">
    <div class="label-text">{data.label || 'Result will be shown here'}</div>
  </div>
  <Handle type="source" position={Position.Right} isConnectable={true} />
</div>

<style>
  .custom-node {
    background: #1e1e2d;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 10px;
    width: 200px;
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
    color: #60a5fa;
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
  .label-text {
    font-size: 12px;
    color: #a1a1aa;
    text-align: center;
    padding: 10px 0;
  }
</style>
