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
  <button class="dict-toggle" on:click={() => open = !open}>
    <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14" style="color:var(--primary2)">
      <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.396 0 2.698.37 3.8 1.018A7.968 7.968 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.969 7.969 0 0014.5 4c-1.396 0-2.698.37-3.8 1.018A7.979 7.979 0 009 4.804z"/>
    </svg>
    <span>พจนานุกรม</span>
    <svg class="chev" class:open viewBox="0 0 16 16" fill="currentColor" width="11" height="11" style="margin-left:auto;color:var(--text3)">
      <path d="M4.22 6.22a.75.75 0 011.06 0L8 8.94l2.72-2.72a.75.75 0 111.06 1.06l-3.25 3.25a.75.75 0 01-1.06 0L4.22 7.28a.75.75 0 010-1.06z"/>
    </svg>
  </button>

  {#if open}
    <div class="dict-body">
      {#if loading}
        <div class="dots"><span></span><span></span><span></span></div>
      {:else if stats}
        <div class="stat-row">
          <div class="ds"><div class="dv" style="color:var(--success)">{stats.custom_words.toLocaleString()}</div><div class="dl">คำศัพท์ที่สอน AI เพิ่มเติม (Custom)</div></div>
        </div>
      {/if}
      <div class="add-row">
        <input bind:value={newWord} on:keydown={onKey} placeholder="เพิ่มคำใหม่..." />
        <button class="btn-add" on:click={addWord}>เพิ่ม</button>
      </div>
    </div>
  {/if}
</div>

<style>
.dict-panel {
  margin: 12px 16px 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius2);
  overflow: hidden;
}
.dict-toggle {
  display: flex; align-items: center; gap: 7px; width: 100%;
  background: none; border: none; cursor: pointer;
  padding: 10px 14px; font-family: var(--font-th);
  font-size: 13px; font-weight: 600; color: var(--text2);
  transition: background 0.2s;
}
.dict-toggle:hover { background: var(--surface2); }
.chev { transition: transform 0.25s; }
.chev.open { transform: rotate(180deg); }

.dict-body { padding: 0 14px 14px; }
.stat-row { display: flex; gap: 8px; margin-bottom: 12px; margin-top: 10px; }
.ds { flex: 1; background: var(--surface2); border: 1px solid var(--border); border-radius: 7px; padding: 8px; text-align: center; }
.dv { font-size: 16px; font-weight: 700; }
.dl { font-size: 10px; color: var(--text3); margin-top: 2px; }

.add-row { display: flex; gap: 8px; }
.add-row input {
  flex: 1; background: var(--bg3); border: 1px solid var(--border2);
  color: var(--text); font-family: var(--font-th); font-size: 13px;
  border-radius: 7px; padding: 7px 11px; outline: none;
  transition: border-color 0.2s;
}
.add-row input:focus { border-color: var(--primary); }
.add-row input::placeholder { color: var(--text3); }
.btn-add {
  background: linear-gradient(135deg, var(--primary), var(--accent));
  border: none; color: #fff; font-family: var(--font-th); font-size: 13px;
  font-weight: 600; padding: 7px 14px; border-radius: 7px;
  cursor: pointer; white-space: nowrap;
  box-shadow: 0 2px 8px var(--glow);
  transition: transform 0.15s;
}
.btn-add:hover { transform: translateY(-1px); }

.dots { display: flex; justify-content: center; gap: 5px; padding: 12px; }
.dots span {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--primary); animation: dp 1.2s infinite ease-in-out;
}
.dots span:nth-child(2) { animation-delay: .2s; }
.dots span:nth-child(3) { animation-delay: .4s; }
@keyframes dp { 0%,60%,100%{transform:scale(.6);opacity:.4} 30%{transform:scale(1);opacity:1} }
</style>
