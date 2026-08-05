<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';

  export let value = '';
  export let options = []; // Array of { value, label, icon?, class? } or simple strings
  export let placeholder = 'เลือกรายการ...';
  export let disabled = false;
  export let width = '100%';
  export let minWidth = '140px';
  export let size = 'md'; // 'sm' | 'md' | 'lg'
  export let id = '';

  const dispatch = createEventDispatcher();
  let isOpen = false;
  let selectEl;

  $: normalizedOptions = options.map(opt => {
    if (typeof opt === 'object' && opt !== null) {
      return { value: opt.value, label: opt.label || opt.value, icon: opt.icon || '', badgeClass: opt.class || '' };
    }
    return { value: opt, label: String(opt), icon: '', badgeClass: '' };
  });

  $: selectedOption = normalizedOptions.find(o => String(o.value) === String(value)) || null;

  function toggleOpen() {
    if (disabled) return;
    isOpen = !isOpen;
  }

  function selectOption(opt) {
    value = opt.value;
    isOpen = false;
    dispatch('change', { value: opt.value, option: opt });
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
  class="custom-select-wrapper size-{size}" 
  class:disabled 
  class:is-open={isOpen}
  style="width: {width}; min-width: {minWidth};"
  {id}
>
  <button 
    type="button" 
    class="select-trigger-btn" 
    on:click={toggleOpen} 
    {disabled}
    aria-haspopup="listbox"
    aria-expanded={isOpen}
  >
    <div class="trigger-content">
      {#if selectedOption}
        {#if selectedOption.icon}<span class="opt-icon">{selectedOption.icon}</span>{/if}
        <span class="opt-label">{selectedOption.label}</span>
      {:else}
        <span class="opt-placeholder">{placeholder}</span>
      {/if}
    </div>
    <svg class="chevron-icon" class:rotated={isOpen} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  </button>

  {#if isOpen}
    <div class="custom-dropdown-menu" role="listbox">
      {#each normalizedOptions as opt}
        <div 
          class="custom-option-item" 
          class:is-selected={String(opt.value) === String(value)}
          on:click|stopPropagation={() => selectOption(opt)}
          role="option"
          aria-selected={String(opt.value) === String(value)}
        >
          {#if opt.icon}<span class="opt-icon">{opt.icon}</span>{/if}
          <span class="opt-text">{opt.label}</span>
          {#if String(opt.value) === String(value)}
            <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .custom-select-wrapper {
    position: relative;
    display: inline-block;
    user-select: none;
    font-family: var(--font-th, 'Prompt', sans-serif);
  }

  .custom-select-wrapper.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .select-trigger-btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    background: rgba(18, 20, 28, 0.85);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 12px;
    color: #f8fafc;
    padding: 9px 14px;
    font-size: 13.5px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.08);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .size-sm .select-trigger-btn { padding: 6px 10px; font-size: 12.5px; border-radius: 8px; }
  .size-lg .select-trigger-btn { padding: 12px 18px; font-size: 15px; border-radius: 14px; }

  .select-trigger-btn:hover:not(:disabled) {
    border-color: rgba(168, 85, 247, 0.75);
    background-color: rgba(28, 30, 46, 0.95);
    box-shadow: 0 6px 20px rgba(168, 85, 247, 0.3);
    transform: translateY(-1px);
  }

  .is-open .select-trigger-btn {
    border-color: #a855f7;
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.35), 0 8px 24px rgba(168, 85, 247, 0.35);
  }

  .trigger-content {
    display: flex;
    align-items: center;
    gap: 8px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .opt-placeholder {
    color: #94a3b8;
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
    min-width: 180px;
    background: rgba(15, 17, 26, 0.96);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(168, 85, 247, 0.4);
    border-radius: 12px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.85), 0 0 25px rgba(168, 85, 247, 0.2);
    z-index: 999;
    max-height: 260px;
    overflow-y: auto;
    padding: 6px;
    animation: dropdownFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes dropdownFadeIn {
    from { opacity: 0; transform: translateY(-8px) scale(0.97); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  .custom-dropdown-menu::-webkit-scrollbar { width: 5px; }
  .custom-dropdown-menu::-webkit-scrollbar-thumb {
    background: rgba(168, 85, 247, 0.4);
    border-radius: 4px;
  }

  .custom-option-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 9px 12px;
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 13.5px;
    font-weight: 400;
    cursor: pointer;
    transition: all 0.18s ease;
  }

  .custom-option-item:hover {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.35), rgba(168, 85, 247, 0.35));
    color: #ffffff;
    transform: translateX(3px);
  }

  .custom-option-item.is-selected {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.55), rgba(168, 85, 247, 0.55));
    color: #ffffff;
    font-weight: 600;
  }

  .opt-icon { font-size: 14px; flex-shrink: 0; }
  .opt-text { flex-grow: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .check-icon {
    width: 14px;
    height: 14px;
    color: #67e8f9;
    flex-shrink: 0;
  }
</style>
