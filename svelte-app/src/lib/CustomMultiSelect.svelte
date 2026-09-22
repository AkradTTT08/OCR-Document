<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';

  export let values = []; // Array of strings/numbers
  export let options = []; // Array of { value, label, icon?, group? } or simple strings
  export let placeholder = 'เลือกรายการ (เลือกได้มากกว่า 1)...';
  export let disabled = false;
  export let width = '100%';
  export let minWidth = '140px';
  export let size = 'md'; // 'sm' | 'md' | 'lg'
  export let id = '';
  export let maxDisplayBadges = 2;
  export let showSearch = true;

  const dispatch = createEventDispatcher();
  let isOpen = false;
  let selectEl;
  let searchQuery = '';

  $: normalizedOptions = options.map(opt => {
    if (typeof opt === 'object' && opt !== null) {
      return { 
        value: String(opt.value), 
        label: opt.label || String(opt.value), 
        icon: opt.icon || '', 
        group: opt.group || '' 
      };
    }
    return { value: String(opt), label: String(opt), icon: '', group: '' };
  });

  $: filteredOptions = searchQuery.trim() 
    ? normalizedOptions.filter(o => o.label.toLowerCase().includes(searchQuery.toLowerCase()))
    : normalizedOptions;

  $: selectedOptions = normalizedOptions.filter(o => values.map(String).includes(String(o.value)));

  function toggleOpen() {
    if (disabled) return;
    isOpen = !isOpen;
    if (isOpen) {
      searchQuery = '';
    }
  }

  function toggleOption(optVal) {
    const valStr = String(optVal);
    const curValues = values.map(String);
    let newValues;
    if (curValues.includes(valStr)) {
      newValues = curValues.filter(v => v !== valStr);
    } else {
      newValues = [...curValues, valStr];
    }
    values = newValues;
    dispatch('change', { values: newValues });
  }

  function removeValue(e, optVal) {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    const valStr = String(optVal);
    values = values.map(String).filter(v => v !== valStr);
    dispatch('change', { values });
  }

  function selectAll(e) {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    values = normalizedOptions.map(o => String(o.value)).filter(v => v !== "");
    dispatch('change', { values });
  }

  function clearAll(e) {
    if (e) {
      e.stopPropagation();
      e.preventDefault();
    }
    values = [];
    dispatch('change', { values: [] });
  }

  function handleOutsideClick(e) {
    if (isOpen && selectEl && !selectEl.contains(e.target)) {
      isOpen = false;
    }
  }

  onMount(() => {
    window.addEventListener('click', handleOutsideClick);
  });

  onDestroy(() => {
    window.removeEventListener('click', handleOutsideClick);
  });
</script>

<div 
  bind:this={selectEl} 
  class="custom-multiselect-wrapper size-{size}" 
  class:disabled 
  class:is-open={isOpen}
  style="width: {width}; min-width: {minWidth};"
  {id}
>
  <div 
    class="select-trigger-btn" 
    on:click={toggleOpen} 
    role="button"
    tabindex={disabled ? -1 : 0}
    on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggleOpen(); }}
    aria-haspopup="listbox"
    aria-expanded={isOpen}
  >
    <div class="trigger-content">
      {#if selectedOptions.length > 0}
        <div class="badge-list">
          {#each selectedOptions.slice(0, maxDisplayBadges) as opt (opt.value)}
            <span class="selected-badge" title={opt.label}>
              {#if opt.icon}<span class="badge-icon">{opt.icon}</span>{/if}
              <span class="badge-text">{opt.label}</span>
              <button 
                type="button" 
                class="badge-remove-btn" 
                on:click|stopPropagation|preventDefault={(e) => removeValue(e, opt.value)}
                title="ลบรายการนี้"
              >
                ×
              </button>
            </span>
          {/each}
          {#if selectedOptions.length > maxDisplayBadges}
            <span class="more-badge" title="มีรายการที่เลือกเพิ่มเติม">
              +{selectedOptions.length - maxDisplayBadges} รายการ
            </span>
          {/if}
        </div>
      {:else}
        <span class="opt-placeholder">{placeholder}</span>
      {/if}
    </div>

    <div class="trigger-actions">
      {#if selectedOptions.length > 0}
        <button 
          type="button" 
          class="clear-all-btn" 
          on:click|stopPropagation|preventDefault={clearAll}
          title="ล้างการเลือกทั้งหมด"
        >
          ✕
        </button>
      {/if}
      <svg class="chevron-icon" class:rotated={isOpen} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </div>
  </div>

  {#if isOpen}
    <div class="custom-dropdown-menu" role="listbox" on:click|stopPropagation>
      {#if showSearch && normalizedOptions.length > 5}
        <div class="dropdown-search-box">
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input 
            type="text" 
            placeholder="ค้นหา..." 
            bind:value={searchQuery}
            class="search-input"
            on:click|stopPropagation
          />
          {#if searchQuery}
            <button class="clear-search-btn" on:click={() => searchQuery = ''}>×</button>
          {/if}
        </div>
      {/if}

      <div class="dropdown-header-actions">
        <button type="button" class="action-link-btn" on:click={selectAll}>✓ เลือกทั้งหมด</button>
        <span class="divider">|</span>
        <button type="button" class="action-link-btn" on:click={() => clearAll(null)}>✕ ล้างการเลือก</button>
        <span class="selected-count-label">เลือก {selectedOptions.length}/{normalizedOptions.length}</span>
      </div>

      <div class="options-scroll-area">
        {#if filteredOptions.length === 0}
          <div class="no-options-text">ไม่พบรายการที่ค้นหา</div>
        {:else}
          {#each filteredOptions as opt (opt.value)}
            {@const isChecked = values.map(String).includes(String(opt.value))}
            <div 
              class="custom-option-item" 
              class:is-selected={isChecked}
              on:click|stopPropagation={() => toggleOption(opt.value)}
              role="option"
              aria-selected={isChecked}
            >
              <div class="checkbox-box" class:checked={isChecked}>
                {#if isChecked}
                  <svg class="check-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                {/if}
              </div>
              {#if opt.icon}<span class="opt-icon">{opt.icon}</span>{/if}
              <span class="opt-text" title={opt.label}>{opt.label}</span>
            </div>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .custom-multiselect-wrapper {
    position: relative;
    display: inline-block;
    user-select: none;
    font-family: var(--font-th, 'Prompt', sans-serif);
  }

  .custom-multiselect-wrapper.disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
  }

  .custom-multiselect-wrapper.is-open {
    z-index: 1000;
  }

  .select-trigger-btn {
    width: 100%;
    min-height: 42px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    background: rgba(18, 20, 28, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    color: #f8fafc;
    padding: 6px 12px;
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.08);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .size-sm .select-trigger-btn { min-height: 36px; padding: 4px 8px; font-size: 12px; border-radius: 8px; }
  .size-lg .select-trigger-btn { min-height: 48px; padding: 8px 16px; font-size: 15px; border-radius: 14px; }

  .select-trigger-btn:hover {
    border-color: rgba(168, 85, 247, 0.75);
    background-color: rgba(28, 30, 46, 0.95);
    box-shadow: 0 6px 20px rgba(168, 85, 247, 0.3);
  }

  .is-open .select-trigger-btn {
    border-color: #a855f7;
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.35), 0 8px 24px rgba(168, 85, 247, 0.35);
  }

  .trigger-content {
    display: flex;
    align-items: center;
    flex-grow: 1;
    overflow: hidden;
  }

  .badge-list {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    max-width: 100%;
  }

  .selected-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(168, 85, 247, 0.4));
    border: 1px solid rgba(168, 85, 247, 0.5);
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    color: #f1f5f9;
    max-width: 220px;
  }

  .badge-icon {
    font-size: 11px;
    flex-shrink: 0;
  }

  .badge-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .badge-remove-btn {
    background: none;
    border: none;
    color: #cbd5e1;
    cursor: pointer;
    padding: 0 2px;
    font-size: 14px;
    line-height: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: color 0.15s, background 0.15s;
  }

  .badge-remove-btn:hover {
    color: #f87171;
    background: rgba(248, 113, 113, 0.2);
  }

  .more-badge {
    display: inline-flex;
    align-items: center;
    background: rgba(148, 163, 184, 0.2);
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 11px;
    color: #cbd5e1;
    white-space: nowrap;
  }

  .opt-placeholder {
    color: #94a3b8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .trigger-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .clear-all-btn {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #f87171;
    border-radius: 50%;
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .clear-all-btn:hover {
    background: rgba(239, 68, 68, 0.35);
    color: #ffffff;
  }

  .chevron-icon {
    width: 15px;
    height: 15px;
    color: #a855f7;
    flex-shrink: 0;
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .chevron-icon.rotated {
    transform: rotate(180deg);
  }

  .custom-dropdown-menu {
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    width: 100%;
    min-width: 240px;
    background: rgba(15, 17, 26, 0.98);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(168, 85, 247, 0.4);
    border-radius: 12px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.85), 0 0 25px rgba(168, 85, 247, 0.2);
    z-index: 999;
    padding: 8px;
    animation: dropdownFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  @keyframes dropdownFadeIn {
    from { opacity: 0; transform: translateY(-8px) scale(0.97); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  .dropdown-search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(30, 34, 53, 0.8);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: 8px;
    padding: 4px 8px;
  }

  .search-icon {
    width: 14px;
    height: 14px;
    color: #94a3b8;
    flex-shrink: 0;
  }

  .search-input {
    background: none;
    border: none;
    color: #f8fafc;
    font-size: 12.5px;
    width: 100%;
    outline: none;
    font-family: inherit;
  }

  .clear-search-btn {
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    font-size: 14px;
    padding: 0 4px;
  }

  .dropdown-header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    font-size: 11.5px;
  }

  .action-link-btn {
    background: none;
    border: none;
    color: #a855f7;
    cursor: pointer;
    font-size: 11.5px;
    padding: 2px 4px;
    border-radius: 4px;
    transition: all 0.15s;
  }

  .action-link-btn:hover {
    color: #d8b4fe;
    background: rgba(168, 85, 247, 0.15);
  }

  .divider {
    color: rgba(255, 255, 255, 0.2);
  }

  .selected-count-label {
    margin-left: auto;
    color: #94a3b8;
    font-size: 11px;
  }

  .options-scroll-area {
    max-height: 240px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .options-scroll-area::-webkit-scrollbar { width: 5px; }
  .options-scroll-area::-webkit-scrollbar-thumb {
    background: rgba(168, 85, 247, 0.4);
    border-radius: 4px;
  }

  .no-options-text {
    padding: 16px;
    text-align: center;
    color: #94a3b8;
    font-size: 12.5px;
  }

  .custom-option-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 400;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .custom-option-item:hover {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(168, 85, 247, 0.25));
    color: #ffffff;
    transform: translateX(2px);
  }

  .custom-option-item.is-selected {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(168, 85, 247, 0.4));
    color: #ffffff;
    font-weight: 500;
  }

  .checkbox-box {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1.5px solid rgba(168, 85, 247, 0.6);
    background: rgba(15, 17, 26, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.15s ease;
  }

  .checkbox-box.checked {
    background: #a855f7;
    border-color: #c084fc;
    box-shadow: 0 0 8px rgba(168, 85, 247, 0.6);
  }

  .check-svg {
    width: 12px;
    height: 12px;
    color: #ffffff;
  }

  .opt-icon { font-size: 13.5px; flex-shrink: 0; }
  .opt-text { flex-grow: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
