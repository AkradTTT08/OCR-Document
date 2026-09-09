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
  max-width: 500px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
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

.fmt-body { 
  padding: 24px;
  overflow-y: auto;
}

.empty-rules {
  font-size: 13px;
  color: #aaa;
  text-align: center;
  padding: 20px;
  line-height: 1.5;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
  max-height: 250px;
  overflow-y: auto;
  padding-right: 4px;
}
.rule-item {
  display: flex;
  align-items: center;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 10px;
  padding: 12px 14px;
  gap: 12px;
  box-shadow: inset 0 2px 10px rgba(0,0,0,0.2);
}
.rule-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
}
.rule-name {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}
.rule-details {
  display: flex;
  gap: 6px;
  align-items: center;
}
.badge-type {
  font-size: 10px;
  font-weight: 700;
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 6px;
  padding: 2px 6px;
}
.badge-pattern {
  font-size: 11px;
  font-family: monospace;
  color: #aaa;
}
.rule-msg {
  font-size: 11px;
  color: #fca5a5;
  margin-top: 2px;
}
.btn-del {
  background: rgba(239, 68, 68, 0.1); 
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #ef4444; 
  width: 26px; height: 26px; border-radius: 6px;
  cursor: pointer; font-size: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.btn-del:hover { 
  background: rgba(239, 68, 68, 0.25); 
  color: #f87171;
}

.btn-toggle-add {
  display: block;
  width: 100%;
  text-align: center;
  background: rgba(255,255,255,0.02);
  border: 1px dashed rgba(255,255,255,0.2);
  color: #fbbf24;
  font-family: var(--font-th);
  font-size: 13px;
  font-weight: 600;
  padding: 12px;
  border-radius: 10px;
  cursor: pointer;
  margin-top: 16px;
  transition: all 0.2s;
}
.btn-toggle-add:hover {
  background: rgba(245, 158, 11, 0.05);
  border-color: #fbbf24;
}

.add-form {
  margin-top: 16px;
  padding: 16px;
  background: rgba(0,0,0,0.2);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  text-align: left;
  box-shadow: inset 0 2px 8px rgba(0,0,0,0.3);
}
.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 4px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.form-group label {
  font-size: 11px;
  color: #aaa;
  font-weight: 600;
}
.form-group input, .form-group select {
  background: rgba(0,0,0,0.4); 
  border: 1px solid rgba(255,255,255,0.12);
  color: #fff; font-family: var(--font-th); font-size: 13px;
  border-radius: 8px; padding: 10px 14px; outline: none;
  transition: all 0.2s;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
}
.form-group input:focus, .form-group select:focus { 
  border-color: #f59e0b; 
  background: rgba(0,0,0,0.6);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2), inset 0 2px 4px rgba(0,0,0,0.2);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.btn-cancel {
  background: rgba(255,255,255,0.05); 
  border: 1px solid rgba(255,255,255,0.1);
  color: #ccc; font-family: var(--font-th); font-size: 13px;
  padding: 8px 16px; border-radius: 8px; cursor: pointer;
  transition: all 0.2s;
}
.btn-cancel:hover { 
  background: rgba(255,255,255,0.1); 
  color: #fff;
}

.btn-submit {
  background: linear-gradient(135deg, #f59e0b, #ea580c);
  border: none; color: #fff; font-family: var(--font-th); font-size: 13px;
  font-weight: 600; padding: 8px 20px; border-radius: 8px;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
  transition: all 0.2s;
}
.btn-submit:hover { 
  transform: translateY(-2px); 
  box-shadow: 0 6px 16px rgba(245, 158, 11, 0.4);
}

.dots { display: flex; justify-content: center; gap: 5px; padding: 12px; }
.dots span {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--warning); animation: dp 1.2s infinite ease-in-out;
}
.dots span:nth-child(2) { animation-delay: .2s; }
.dots span:nth-child(3) { animation-delay: .4s; }
</style>
