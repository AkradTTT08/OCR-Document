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
    <button type="button" class="delete-btn" aria-label="ลบ Node นี้" on:click|stopPropagation={deleteNode} title="ลบ Card นี้">✕</button>
  </div>
  <div class="node-content">
    <div class="label-text">{data.label || 'Result will be shown here'}</div>
  </div>
</div>

<style>
  .custom-node {
    background: var(--bg2, #12141c);
    border: 1px solid rgba(56, 189, 248, 0.45);
    border-radius: var(--radius-sm, 8px);
    padding: 12px;
    width: 200px;
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
    color: var(--accent, #06b6d4);
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
  .label-text {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    text-align: center;
    padding: 10px 0;
  }
</style>
