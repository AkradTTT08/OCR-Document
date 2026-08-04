<script>
  import { onMount } from 'svelte';
  const API = 'http://localhost:5000/api';

  let stats = null;
  let loading = true;
  let open = false;
  let newWord = '';

  onMount(async () => {
    await fetchStats();
    loading = false;
  });

  async function fetchStats() {
    try {
      const res = await fetch(`${API}/dictionary/stats`);
      const d = await res.json();
      if (d.success) stats = d.stats;
    } catch {}
  }

  async function addWord() {
    const word = newWord.trim();
    if (!word) return;
    try {
      const res = await fetch(`${API}/dictionary/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word })
      });
      const d = await res.json();
      if (d.success) {
        newWord = '';
        await fetchStats();
      }
    } catch {}
  }

  function onKey(e) { if (e.key === 'Enter') addWord(); }
</script>

<div class="dict-panel">
  <button class="dict-toggle" on:click={() => open = true}>
    <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16" style="color:var(--text-main)">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
    </svg>
    <span>พจนานุกรม</span>
    <svg class="chev" viewBox="0 0 16 16" fill="currentColor" width="10" height="10" style="color:var(--text3)">
      <path d="M4.22 10.28a.75.75 0 001.06 0L8 7.56l2.72 2.72a.75.75 0 101.06-1.06l-3.25-3.25a.75.75 0 00-1.06 0L4.22 9.22a.75.75 0 000 1.06z"/>
    </svg>
  </button>

  {#if open}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal-backdrop" on:click={() => open = false}>
      <div class="modal-content" on:click|stopPropagation>
        <div class="modal-header">
          <div class="modal-title">
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            พจนานุกรมคำศัพท์
          </div>
          <button class="btn-close" on:click={() => open = false}>✕</button>
        </div>
        <div class="dict-body">
          {#if loading}
            <div class="dots"><span></span><span></span><span></span></div>
          {:else if stats}
            <div class="stat-row">
              <div class="ds">
                <div class="dv" style="color:var(--success)">{stats.custom_words.toLocaleString()}</div>
                <div class="dl">คำศัพท์ที่สอน AI เพิ่มเติม (Custom)</div>
              </div>
            </div>
          {/if}
          <div class="add-row">
            <input bind:value={newWord} on:keydown={onKey} placeholder="เพิ่มคำใหม่..." />
            <button class="btn-add" on:click={addWord}>เพิ่ม</button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
.dict-panel {
  display: inline-block;
}
.dict-toggle {
  display: flex; align-items: center; gap: 8px;
  background: transparent; border: none; cursor: pointer;
  padding: 8px 12px; font-family: var(--font-th);
  font-size: 14px; font-weight: 700; color: #fff;
  transition: all 0.2s;
  border-radius: 8px;
}
.dict-toggle:hover {
  background: rgba(255,255,255,0.05);
}
.chev { opacity: 0.7; }

/* Modal */
.modal-backdrop {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}
.modal-content {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 400px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
@keyframes slideUp {
  0% { transform: translateY(20px) scale(0.95); opacity: 0; }
  100% { transform: translateY(0) scale(1); opacity: 1; }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: rgba(255,255,255,0.02);
}
.modal-title {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}
.btn-close {
  background: none; border: none; color: var(--text3);
  font-size: 14px; cursor: pointer; padding: 4px;
  transition: color 0.2s;
}
.btn-close:hover { color: #fff; }

.dict-body { padding: 20px; }
.stat-row { display: flex; gap: 8px; margin-bottom: 16px; }
.ds { flex: 1; background: var(--surface2); border: 1px solid var(--border2); border-radius: 12px; padding: 12px; text-align: center; }
.dv { font-size: 24px; font-weight: 700; font-family: var(--font-en); }
.dl { font-size: 12px; color: var(--text3); margin-top: 4px; }

.add-row { display: flex; gap: 8px; }
.add-row input {
  flex: 1; background: var(--bg3); border: 1px solid var(--border2);
  color: var(--text); font-family: var(--font-th); font-size: 14px;
  border-radius: 8px; padding: 10px 14px; outline: none;
  transition: border-color 0.2s;
}
.add-row input:focus { border-color: var(--primary); }
.add-row input::placeholder { color: var(--text3); }
.btn-add {
  background: var(--gradient-main);
  border: none; color: #fff; font-family: var(--font-th); font-size: 14px;
  font-weight: 600; padding: 10px 20px; border-radius: 8px;
  cursor: pointer; white-space: nowrap;
  box-shadow: 0 4px 12px var(--primary-glow);
  transition: transform 0.2s;
}
.btn-add:hover { transform: translateY(-2px); }

.dots { display: flex; justify-content: center; gap: 5px; padding: 20px; }
.dots span {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--primary); animation: dp 1.2s infinite ease-in-out;
}
.dots span:nth-child(2) { animation-delay: .2s; }
.dots span:nth-child(3) { animation-delay: .4s; }
@keyframes dp { 0%,60%,100%{transform:scale(.6);opacity:.4} 30%{transform:scale(1);opacity:1} }
</style>
