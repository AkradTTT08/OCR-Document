<script>
  import { onMount } from 'svelte';
  import { toast } from './toastStore.js';
  import CustomSelect from './CustomSelect.svelte';
  const API = 'http://localhost:5000/api';

  const formatRuleOptions = [
    { value: 'preceded_by_space', label: 'ต้องมีช่องว่างข้างหน้า (Preceded by Space)', icon: '⬅️' },
    { value: 'followed_by_space', label: 'ต้องมีช่องว่างข้างหลัง (Followed by Space)', icon: '➡️' },
    { value: 'forbidden_pattern', label: 'คำต้องห้าม / คำผิดตรงตัว (Forbidden Word)', icon: '🚫' },
    { value: 'custom_regex', label: 'Regex กำหนดเอง (Custom Regex Pattern)', icon: '⚡' }
  ];

  /** @type {any[]} */
  let rules = [];
  let loading = true;
  let open = false;

  // Form State
  let name = '';
  let ruleType = 'preceded_by_space';
  let pattern = '';
  let suggestedFix = '';
  let message = '';
  let showAddForm = false;

  onMount(async () => {
    await fetchRules();
    loading = false;
  });

  async function fetchRules() {
    try {
      const res = await fetch(`${API}/format_rules`);
      const d = await res.json();
      if (d.success) {
        rules = d.rules;
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function addRule() {
    if (!name.trim() || !pattern.trim() || !message.trim()) {
      toast('กรุณากรอกข้อมูลให้ครบถ้วน (ชื่อกฎ, รูปแบบ, คำแนะนำ)', 'warning');
      return;
    }

    const newRule = {
      id: 'rule_' + Date.now(),
      name: name.trim(),
      rule_type: ruleType,
      pattern: pattern.trim(),
      suggested_fix: suggestedFix.trim(),
      message: message.trim()
    };

    const updatedRules = [...rules, newRule];

    try {
      const res = await fetch(`${API}/format_rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules: updatedRules })
      });
      const d = await res.json();
      if (d.success) {
        toast(`เพิ่มกฎ "${name}" สำเร็จ`, 'success');
        resetForm();
        await fetchRules();
      } else {
        toast(d.error || 'เกิดข้อผิดพลาดในการบันทึก', 'error');
      }
    } catch (err) {
      toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้', 'error');
    }
  }

  /**
   * @param {string} id
   * @param {string} ruleName
   */
  async function deleteRule(id, ruleName) {
    const updatedRules = rules.filter(r => r.id !== id);
    try {
      const res = await fetch(`${API}/format_rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules: updatedRules })
      });
      const d = await res.json();
      if (d.success) {
        toast(`ลบกฎ "${ruleName}" แล้ว`, 'success');
        await fetchRules();
      } else {
        toast(d.error || 'ไม่สามารถลบกฎได้', 'error');
      }
    } catch (err) {
      toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้', 'error');
    }
  }

  function resetForm() {
    name = '';
    pattern = '';
    suggestedFix = '';
    message = '';
    showAddForm = false;
  }

  // Helper translations
  /** @type {Record<string, string>} */
  const typeMap = {
    preceded_by_space: 'เว้นวรรคข้างหน้า',
    followed_by_space: 'เว้นวรรคข้างหลัง',
    forbidden_pattern: 'คำต้องห้าม / คำผิดตรงตัว',
    custom_regex: 'Regex กำหนดเอง'
  };

  function handleTypeChange() {
    if (ruleType === 'preceded_by_space') {
      message = `ควรเว้นวรรคหน้าคำว่า "${pattern}" เสมอ`;
      suggestedFix = ` ${pattern}`;
    } else if (ruleType === 'followed_by_space') {
      message = `ควรเว้นวรรคหลังคำว่า "${pattern}" เสมอ`;
      suggestedFix = `${pattern} `;
    } else {
      message = '';
      suggestedFix = '';
    }
  }
</script>

<div class="fmt-panel">
  <button class="fmt-toggle" on:click={() => open = true}>
    <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16" style="color:var(--warning)">
      <path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.533 1.533 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.533 1.533 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd" />
    </svg>
    <div class="fmt-title-wrap">
      <span>กฎการจัดฟอร์แมต</span>
      <span>เอกสาร</span>
    </div>
    <span class="count-badge">{rules.length}</span>
  </button>

  {#if open}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal-backdrop" on:click={() => open = false}>
      <div class="modal-content" on:click|stopPropagation>
        <div class="modal-header">
          <div class="modal-title">
            <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18"><path fill-rule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.533 1.533 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.533 1.533 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clip-rule="evenodd" /></svg>
            กฎการจัดฟอร์แมตเอกสาร
          </div>
          <button class="btn-close" on:click={() => open = false}>✕</button>
        </div>
    <div class="fmt-body">
      {#if loading}
        <div class="dots"><span></span><span></span><span></span></div>
      {:else}
        <!-- Rules list -->
        {#if rules.length === 0}
          <div class="empty-rules">ยังไม่มีกฎเกณฑ์ ลองสร้างกฎเกณฑ์แรกของคุณ!</div>
        {:else}
          <div class="rules-list">
            {#each rules as r}
              <div class="rule-item">
                <div class="rule-main">
                  <div class="rule-name">{r.name}</div>
                  <div class="rule-details">
                    <span class="badge-type">{typeMap[r.rule_type] || r.rule_type}</span>
                    <span class="badge-pattern">"{r.pattern}"</span>
                  </div>
                  <div class="rule-msg">{r.message}</div>
                </div>
                <button class="btn-del" on:click={() => deleteRule(r.id, r.name)} title="ลบกฎเกณฑ์">✕</button>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Add Form Toggle -->
        {#if !showAddForm}
          <button class="btn-toggle-add" on:click={() => showAddForm = true}>
            + เพิ่มกฎการตรวจรูปแบบใหม่
          </button>
        {:else}
          <div class="add-form">
            <div class="form-header">
              <span>เพิ่มกฎเกณฑ์การจัดฟอร์แมต</span>
              <button class="btn-close" on:click={resetForm}>✕</button>
            </div>
            
            <div class="form-group">
              <label for="fmt-name">ชื่อกฎเกณฑ์</label>
              <input id="fmt-name" bind:value={name} placeholder="เช่น เว้นวรรคหน้าคำว่า และ" />
            </div>

            <div class="form-group">
              <label for="fmt-type">ประเภทการเช็ค</label>
              <CustomSelect 
                id="fmt-type" 
                bind:value={ruleType} 
                options={formatRuleOptions} 
                on:change={handleTypeChange}
                width="100%"
              />
            </div>

            <div class="form-group">
              <label for="fmt-pattern">คำที่ค้นหา / รูปแบบ</label>
              <input id="fmt-pattern" bind:value={pattern} on:input={handleTypeChange} placeholder="เช่น และ" />
            </div>

            <div class="form-group">
              <label for="fmt-fix">คำที่แนะนำเพื่อแก้ไข (Suggested Fix)</label>
              <input id="fmt-fix" bind:value={suggestedFix} placeholder="เช่น  และ" />
            </div>

            <div class="form-group">
              <label for="fmt-message">ข้อความเตือนเมื่อผิดรูปแบบ</label>
              <input id="fmt-message" bind:value={message} placeholder="เช่น ควรเว้นวรรคหน้าคำว่า และ เสมอ" />
            </div>

            <div class="form-actions">
              <button class="btn-cancel" on:click={resetForm}>ยกเลิก</button>
              <button class="btn-submit" on:click={addRule}>บันทึกกฎ</button>
            </div>
          </div>
        {/if}
      {/if}
      </div>
      </div>
    </div>
  {/if}
</div>

<style>
.fmt-panel {
  display: inline-block;
}
.fmt-toggle {
  display: flex; align-items: center; gap: 12px;
  background: transparent; border: none; cursor: pointer;
  padding: 8px 12px; font-family: var(--font-th);
  font-size: 14px; font-weight: 700; color: #fff;
  transition: all 0.2s;
  border-radius: 8px;
}
.fmt-toggle:hover {
  background: rgba(255,255,255,0.05);
}

.fmt-title-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.2;
}

.count-badge {
  background: rgba(245, 158, 11, 0.15);
  color: var(--warning);
  font-size: 13px;
  font-weight: 700;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1px solid rgba(245, 158, 11, 0.3);
  margin-left: 4px;
}

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
  max-width: 500px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
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

.fmt-body { 
  padding: 20px;
  overflow-y: auto;
}

.empty-rules {
  font-size: 11.5px;
  color: var(--text3);
  text-align: center;
  padding: 12px;
  line-height: 1.5;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
  max-height: 250px;
  overflow-y: auto;
  padding-right: 4px;
}
.rule-item {
  display: flex;
  align-items: center;
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: 7px;
  padding: 8px 10px;
  gap: 10px;
}
.rule-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  text-align: left;
}
.rule-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
}
.rule-details {
  display: flex;
  gap: 5px;
  align-items: center;
}
.badge-type {
  font-size: 9px;
  font-weight: 700;
  background: rgba(108, 142, 251, 0.15);
  color: var(--primary2);
  border: 1px solid rgba(108, 142, 251, 0.25);
  border-radius: 4px;
  padding: 0 4px;
}
.badge-pattern {
  font-size: 10px;
  font-family: monospace;
  color: var(--text3);
}
.rule-msg {
  font-size: 10px;
  color: var(--warning);
}
.btn-del {
  background: rgba(248,113,113,0.08); border: 1px solid rgba(248,113,113,0.18);
  color: var(--danger); width: 22px; height: 22px; border-radius: 5px;
  cursor: pointer; font-size: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.btn-del:hover { background: rgba(248,113,113,0.2); }

.btn-toggle-add {
  display: block;
  width: 100%;
  text-align: center;
  background: none;
  border: 1px dashed var(--border);
  color: var(--primary2);
  font-family: var(--font-th);
  font-size: 11.5px;
  font-weight: 600;
  padding: 8px;
  border-radius: 7px;
  cursor: pointer;
  margin-top: 10px;
  transition: all 0.2s;
}
.btn-toggle-add:hover {
  background: rgba(108, 142, 251, 0.06);
  border-color: var(--primary);
}

.add-form {
  margin-top: 12px;
  padding: 12px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 9px;
  text-align: left;
}
.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
  color: var(--text2);
}
.btn-close {
  background: none; border: none; color: var(--text3); cursor: pointer; font-size: 11px;
}
.btn-close:hover { color: var(--text); }

.form-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.form-group label {
  font-size: 10px;
  color: var(--text3);
  font-weight: 600;
}
.form-group input, .form-group select {
  background: var(--bg3); border: 1px solid var(--border2);
  color: var(--text); font-family: var(--font-th); font-size: 12px;
  border-radius: 6px; padding: 6px 10px; outline: none;
  transition: border-color 0.2s;
}
.form-group input:focus, .form-group select:focus { border-color: var(--primary); }

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 5px;
}
.btn-cancel {
  background: none; border: 1px solid var(--border2);
  color: var(--text2); font-family: var(--font-th); font-size: 11.5px;
  padding: 5px 12px; border-radius: 6px; cursor: pointer;
}
.btn-cancel:hover { background: var(--bg3); }

.btn-submit {
  background: linear-gradient(135deg, var(--primary), var(--accent));
  border: none; color: #fff; font-family: var(--font-th); font-size: 11.5px;
  font-weight: 600; padding: 6px 14px; border-radius: 6px;
  cursor: pointer;
  box-shadow: 0 2px 8px var(--glow);
}
.btn-submit:hover { transform: translateY(-1px); }

.dots { display: flex; justify-content: center; gap: 5px; padding: 12px; }
.dots span {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--warning); animation: dp 1.2s infinite ease-in-out;
}
.dots span:nth-child(2) { animation-delay: .2s; }
.dots span:nth-child(3) { animation-delay: .4s; }
</style>
