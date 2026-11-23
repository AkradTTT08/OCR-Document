<script>
  import { onMount } from 'svelte';
  import { toast } from './toastStore.js';
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
    if (!word) {
      toast('กรุณาพิมพ์คำศัพท์ที่ต้องการเพิ่ม', 'warning');
      return;
    }
    try {
      const res = await fetch(`${API}/dictionary/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word })
      });
      const d = await res.json();
      if (d.success) {
        newWord = '';
        toast(`เพิ่มคำศัพท์ "${word}" เข้าพจนานุกรมสำเร็จ`, 'success');
        await fetchStats();
      } else {
        toast(d.error || 'ไม่สามารถเพิ่มคำศัพท์ได้', 'error');
      }
    } catch {
      toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้', 'error');
    }
  }

  async function removeWord(word) {
    if (!word) return;
    try {
      const res = await fetch(`${API}/dictionary/remove`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word })
      });
      const d = await res.json();
      if (d.success) {
        toast(`ลบคำศัพท์ "${word}" ออกจากพจนานุกรมแล้ว`, 'success');
        await fetchStats();
      } else {
        toast(d.error || 'ไม่สามารถลบคำศัพท์ได้', 'error');
      }
    } catch {
      toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้', 'error');
    }
  }

  function onKey(e) { if (e.key === 'Enter') addWord(); }
  function handleWindowKeydown(e) {
    if (open && e.key === 'Escape') {
      open = false;
    }
  }
</script>

<svelte:window on:keydown={handleWindowKeydown} />

<div class="dict-panel">
  <button type="button" class="dict-toggle" on:click={() => open = true} aria-haspopup="dialog" aria-expanded={open}>
    <div class="dict-toggle-left">
      <span class="dict-icon-box" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
        </svg>
      </span>
      <div class="dict-text-wrap">
        <span class="dict-title">พจนานุกรม</span>
        <span class="dict-sub">คำศัพท์เฉพาะทาง</span>
      </div>
    </div>
    <span class="dict-count-badge" title="จำนวนคำศัพท์ที่สอน AI เพิ่มเติม">
      {stats ? stats.custom_words.toLocaleString() : '0'}
    </span>
  </button>

  {#if open}
    <div class="modal-backdrop" role="presentation" on:click={() => open = false}>
      <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="dict-modal-title" on:click|stopPropagation>
        <div class="modal-header">
          <div class="modal-title" id="dict-modal-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            พจนานุกรมคำศัพท์
          </div>
          <button type="button" class="btn-close" aria-label="ปิดหน้าต่างพจนานุกรม" on:click={() => open = false}>✕</button>
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
            <input bind:value={newWord} on:keydown={onKey} placeholder="เพิ่มคำศัพท์เฉพาะ / ชื่อองค์กร..." aria-label="เพิ่มคำศัพท์ใหม่เข้าพจนานุกรม" />
            <button type="button" class="btn-add" on:click={addWord}>เพิ่ม</button>
          </div>
          {#if stats?.words?.length > 0}
            <div class="word-chips-section">
              <div class="word-chips-label">รายการคำศัพท์ที่บันทึกไว้ ({stats.words.length})</div>
              <div class="word-chips-list">
                {#each stats.words as w}
                  <span class="word-chip">
                    <span>{w}</span>
                    <button
                      type="button"
                      class="chip-del-btn"
                      title={`ลบ "${w}"`}
                      aria-label={`ลบคำศัพท์ ${w}`}
                      on:click={() => removeWord(w)}
                    >✕</button>
                  </span>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
.dict-panel {
  display: flex;
  width: 100%;
}
.dict-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: var(--glass-bg);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  border: 1px solid var(--glass-border);
  cursor: pointer;
  padding: 12px 14px;
  font-family: var(--font-th);
  color: var(--text-main);
  transition: border-color 0.2s ease, background-color 0.2s ease, transform 0.2s ease;
  border-radius: 16px;
}
.dict-toggle:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(168, 85, 247, 0.4);
  transform: translateY(-1px);
}
.dict-toggle-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.dict-icon-box {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.28);
  color: var(--success-soft-text);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.dict-text-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
  line-height: 1.25;
}
.dict-title {
  font-size: 13.5px;
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
}
.dict-sub {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}
.dict-count-badge {
  background: rgba(16, 185, 129, 0.14);
  color: var(--success-soft-text);
  border: 1px solid rgba(16, 185, 129, 0.3);
  font-family: var(--font-en);
  font-size: 12px;
  font-weight: 700;
  min-width: 26px;
  height: 24px;
  padding: 0 7px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

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

.word-chips-section {
  margin-top: 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 14px;
}
.word-chips-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.word-chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 160px;
  overflow-y: auto;
  padding-right: 4px;
}
.word-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-main);
  font-size: 12.5px;
  padding: 4px 10px;
  border-radius: 999px;
}
.chip-del-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  transition: color 0.15s ease;
}
.chip-del-btn:hover {
  color: var(--danger-soft-text);
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
