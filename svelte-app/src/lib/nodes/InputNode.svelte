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
  <div class="node-header">
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
    <span>Input Data</span>
    <button type="button" class="delete-btn" aria-label="ลบ Node นี้" on:click|stopPropagation={deleteNode} title="ลบ Card นี้">✕</button>
  </div>
  <div class="node-content">
    <textarea id="{id}-input-text" aria-label="ข้อมูลนำเข้า (Input Data)" class="nodrag" bind:value={data.text} placeholder="ป้อนคำสั่งเริ่มต้น หรือเนื้อหา..."></textarea>
  </div>
  <Handle type="source" position={Position.Right} isConnectable={true} />
</div>

<style>
  .custom-node {
    background: var(--bg2, #12141c);
    border: 1px solid rgba(52, 211, 153, 0.45);
    border-radius: var(--radius-sm, 8px);
    padding: 12px;
    width: 250px;
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
    color: var(--success, #10b981);
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
  textarea {
    width: 100%;
    min-height: 64px;
    background: var(--bg, #0a0b12);
    border: 1px solid var(--glass-border-light, rgba(255, 255, 255, 0.15));
    color: var(--text-main, #f8fafc);
    font-family: var(--font-th, 'Prompt', sans-serif);
    border-radius: 6px;
    padding: 8px;
    font-size: 12px;
    resize: vertical;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  textarea:focus-visible {
    outline: none;
    border-color: var(--success, #10b981);
    box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.25);
  }
</style>
