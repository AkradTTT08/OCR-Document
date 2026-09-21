<script>
  import { onMount } from 'svelte';
  const API = '/api';

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
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}
.modal-content {
  background: rgba(24, 24, 27, 0.98);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.05) inset;
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
  border-bottom: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03);
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
  background: rgba(255,255,255,0.05); 
  border: 1px solid transparent; 
  color: #aaa;
  font-size: 14px; 
  cursor: pointer; 
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.btn-close:hover { 
  background: rgba(255,255,255,0.1); 
  color: #fff; 
}

.dict-body { padding: 24px; }
.stat-row { display: flex; gap: 8px; margin-bottom: 24px; }
.ds { 
  flex: 1; 
  background: rgba(255,255,255,0.04); 
  border: 1px solid rgba(255,255,255,0.08); 
  border-radius: 12px; 
  padding: 16px; 
  text-align: center;
  box-shadow: inset 0 2px 10px rgba(0,0,0,0.2);
}
.dv { font-size: 32px; font-weight: 700; font-family: var(--font-en); text-shadow: 0 2px 10px rgba(16, 185, 129, 0.3); }
.dl { font-size: 13px; color: #aaa; margin-top: 6px; }

.add-row { display: flex; gap: 10px; }
.add-row input {
  flex: 1; 
  background: rgba(0,0,0,0.4); 
  border: 1px solid rgba(255,255,255,0.12);
  color: #fff; 
  font-family: var(--font-th); 
  font-size: 14px;
  border-radius: 10px; 
  padding: 12px 16px; 
  outline: none;
  transition: all 0.2s;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
}
.add-row input:focus { 
  border-color: #8b5cf6; 
  background: rgba(0,0,0,0.6);
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.25), inset 0 2px 4px rgba(0,0,0,0.2);
}
.add-row input::placeholder { color: #666; }
.btn-add {
  background: linear-gradient(135deg, #a855f7, #6366f1);
  border: none; 
  color: #fff; 
  font-family: var(--font-th); 
  font-size: 14px;
  font-weight: 600; 
  padding: 0 24px; 
  border-radius: 10px;
  cursor: pointer; 
  white-space: nowrap;
  box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.btn-add:hover { 
  transform: translateY(-2px); 
  box-shadow: 0 6px 20px rgba(139, 92, 246, 0.6);
  filter: brightness(1.1);
}

.dots { display: flex; justify-content: center; gap: 5px; padding: 20px; }
.dots span {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--primary); animation: dp 1.2s infinite ease-in-out;
}
.dots span:nth-child(2) { animation-delay: .2s; }
.dots span:nth-child(3) { animation-delay: .4s; }
@keyframes dp { 0%,60%,100%{transform:scale(.6);opacity:.4} 30%{transform:scale(1);opacity:1} }
</style>
