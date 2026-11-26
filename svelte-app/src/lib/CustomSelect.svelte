<script>
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';

  export let value = '';
  export let options = []; // Array of { value, label, icon?, class?, description?, badge? } or simple strings
  export let placeholder = 'เลือกรายการ...';
  export let disabled = false;
  export let width = '100%';
  export let minWidth = '140px';
  export let dropdownMinWidth = '';
  export let size = 'md'; // 'sm' | 'md' | 'lg'
  export let id = '';
  export let ariaLabel = '';

  const dispatch = createEventDispatcher();
  const instanceUid = `cs-${Math.random().toString(36).slice(2, 9)}`;
  let isOpen = false;
  let selectEl;
  let triggerEl;
  let menuEl;
  let focusedIndex = -1;

  let menuTop = 0;
  let menuLeft = 0;
  let menuWidth = 0;
  let menuMaxHeight = 260;
  let dropUp = false;

  $: normalizedOptions = options.map(opt => {
    if (typeof opt === 'object' && opt !== null) {
      return {
        value: opt.value,
        label: opt.label !== undefined ? opt.label : opt.value,
        icon: opt.icon || '',
        badgeClass: opt.class || '',
        description: opt.description || '',
        badge: opt.badge || ''
      };
    }
    return { value: opt, label: String(opt), icon: '', badgeClass: '', description: '', badge: '' };
  });

  $: hasRichDescriptions = normalizedOptions.some(o => Boolean(o.description));
  $: selectedOption = normalizedOptions.find(o => String(o.value) === String(value)) || null;

  function portal(node) {
    document.body.appendChild(node);
    return {
      destroy() {
        if (node.parentNode) {
          node.parentNode.removeChild(node);
        }
      }
    };
  }

  async function updatePosition() {
    if (!selectEl) return;
    await tick();
    const rect = selectEl.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const maxCap = hasRichDescriptions ? 350 : 260;
    const rowEst = hasRichDescriptions ? 64 : 40;
    const estimatedMenuHeight = Math.min(normalizedOptions.length * rowEst + 16, maxCap);
    const parsedDropMin = parseInt(dropdownMinWidth, 10);
    const minMenuW = Number.isFinite(parsedDropMin) && parsedDropMin > 0 ? parsedDropMin : 140;

    let calculatedWidth = Math.min(Math.max(rect.width, minMenuW), window.innerWidth - 24);
    let calculatedLeft = rect.left;

    if (calculatedLeft + calculatedWidth > window.innerWidth - 12) {
      calculatedLeft = Math.max(12, window.innerWidth - calculatedWidth - 12);
    }
    if (calculatedLeft < 12) {
      calculatedLeft = 12;
    }

    menuWidth = calculatedWidth;
    menuLeft = calculatedLeft;

    if (spaceBelow < estimatedMenuHeight && spaceAbove > spaceBelow) {
      dropUp = true;
      menuTop = rect.top - 6;
      menuMaxHeight = Math.max(150, Math.min(maxCap, spaceAbove - 12));
    } else {
      dropUp = false;
      menuTop = rect.bottom + 6;
      menuMaxHeight = Math.max(150, Math.min(maxCap, spaceBelow - 12));
    }
  }

  async function toggleOpen() {
    if (disabled) return;
    isOpen = !isOpen;
    if (isOpen) {
      const curIdx = normalizedOptions.findIndex(o => String(o.value) === String(value));
      focusedIndex = curIdx >= 0 ? curIdx : 0;
      await updatePosition();
    } else {
      focusedIndex = -1;
    }
  }

  function selectOption(opt) {
    value = opt.value;
    isOpen = false;
    focusedIndex = -1;
    dispatch('change', opt.value);
    dispatch('select', opt);
    triggerEl?.focus();
  }

  function handleKeydown(e) {
    if (disabled) return;
    const len = normalizedOptions.length;
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleOpen();
      }
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      isOpen = false;
      focusedIndex = -1;
      triggerEl?.focus();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (len > 0) focusedIndex = (focusedIndex + 1) % len;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (len > 0) focusedIndex = (focusedIndex - 1 + len) % len;
    } else if (e.key === 'Home') {
      e.preventDefault();
      if (len > 0) focusedIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      if (len > 0) focusedIndex = len - 1;
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < len) {
        selectOption(normalizedOptions[focusedIndex]);
      }
    }
  }

  function handleOutsideClick(e) {
    if (isOpen) {
      if (selectEl && selectEl.contains(e.target)) return;
      if (menuEl && menuEl.contains(e.target)) return;
      isOpen = false;
    }
  }

  function handleScrollResize() {
    if (isOpen) {
      updatePosition();
    }
  }

  onMount(() => {
    window.addEventListener('click', handleOutsideClick, true);
    window.addEventListener('scroll', handleScrollResize, true);
    window.addEventListener('resize', handleScrollResize);
  });

  onDestroy(() => {
    window.removeEventListener('click', handleOutsideClick, true);
    window.removeEventListener('scroll', handleScrollResize, true);
    window.removeEventListener('resize', handleScrollResize);
  });
</script>

<div 
  bind:this={selectEl} 
  class="custom-select-wrapper size-{size}" 
  class:disabled 
  class:is-open={isOpen}
  style="width: {width}; min-width: {minWidth};"
>
  <button 
    bind:this={triggerEl}
    type="button" 
    class="select-trigger-btn" 
    {id}
    on:click={toggleOpen}
    on:keydown={handleKeydown}
    {disabled}
    aria-label={ariaLabel || undefined}
    aria-haspopup="listbox"
    aria-expanded={isOpen}
    aria-controls={isOpen ? `${instanceUid}-listbox` : undefined}
    aria-activedescendant={isOpen && focusedIndex >= 0 ? `${instanceUid}-opt-${focusedIndex}` : undefined}
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
    <div 
      use:portal 
      bind:this={menuEl}
      id="{instanceUid}-listbox"
      class="custom-dropdown-menu" 
      class:drop-up={dropUp}
      style="position: fixed; top: {menuTop}px; left: {menuLeft}px; width: {menuWidth}px; max-height: {menuMaxHeight}px; z-index: var(--z-portal, 10500);"
      role="listbox"
      aria-label={ariaLabel || placeholder}
    >
      {#each normalizedOptions as opt, idx}
        <button 
          type="button"
          id="{instanceUid}-opt-{idx}"
          class="custom-option-item" 
          class:has-desc={Boolean(opt.description)}
          class:is-selected={String(opt.value) === String(value)}
          class:is-focused={idx === focusedIndex}
          on:click|stopPropagation={() => selectOption(opt)}
          on:keydown={handleKeydown}
          role="option"
          aria-selected={String(opt.value) === String(value)}
        >
          {#if opt.icon}<span class="opt-icon">{opt.icon}</span>{/if}
          <div class="opt-body">
            <div class="opt-top-row">
              <span class="opt-text">{opt.label}</span>
              {#if opt.badge}
                <span class="opt-badge">{opt.badge}</span>
              {/if}
            </div>
            {#if opt.description}
              <span class="opt-desc">{opt.description}</span>
            {/if}
          </div>
          {#if String(opt.value) === String(value)}
            <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          {/if}
        </button>
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

  .custom-select-wrapper.is-open {
    z-index: 1000;
  }

  .select-trigger-btn {
    width: 100%;
    min-height: 40px;
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
    padding: 8px 14px;
    font-size: 13.5px;
    font-weight: 500;
    font-family: inherit;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 1px rgba(255, 255, 255, 0.08);
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .size-sm .select-trigger-btn { min-height: 34px; padding: 5px 10px; font-size: 12.5px; border-radius: 8px; }
  .size-lg .select-trigger-btn { min-height: 46px; padding: 11px 18px; font-size: 15px; border-radius: 14px; }

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
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .opt-label {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .opt-placeholder {
    color: #94a3b8;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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
    position: fixed !important;
    background: rgba(15, 17, 26, 0.96) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border: 1px solid rgba(168, 85, 247, 0.4) !important;
    border-radius: 12px;
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.88), 0 0 25px rgba(168, 85, 247, 0.25);
    z-index: var(--z-portal, 10500);
    max-height: 260px;
    max-width: calc(100vw - 24px);
    overflow-y: auto;
    overflow-x: hidden;
    padding: 6px;
    box-sizing: border-box;
    animation: dropdownFadeIn 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .custom-dropdown-menu.drop-up {
    transform: translateY(-100%);
    animation: dropdownFadeInUp 0.18s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes dropdownFadeIn {
    from { opacity: 0; transform: translateY(-8px) scale(0.97); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  @keyframes dropdownFadeInUp {
    from { opacity: 0; transform: translateY(calc(-100% + 8px)) scale(0.97); }
    to { opacity: 1; transform: translateY(-100%) scale(1); }
  }

  .custom-dropdown-menu::-webkit-scrollbar { width: 5px; }
  .custom-dropdown-menu::-webkit-scrollbar-thumb {
    background: rgba(168, 85, 247, 0.4);
    border-radius: 4px;
  }

  .custom-option-item {
    width: 100%;
    border: none;
    background: transparent;
    text-align: left;
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

  .custom-option-item:hover,
  .custom-option-item.is-focused {
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
  .opt-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .opt-top-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .opt-text { flex-grow: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .custom-option-item.has-desc {
    align-items: flex-start;
    padding: 10px 12px;
  }
  .custom-option-item.has-desc .opt-text {
    font-weight: 600;
    white-space: normal;
    line-height: 1.35;
  }
  .opt-badge {
    flex-shrink: 0;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.22);
    border: 1px solid rgba(129, 140, 248, 0.4);
    color: #e0e7ff;
  }
  .opt-desc {
    font-size: 12px;
    line-height: 1.45;
    color: #94a3b8;
    white-space: normal;
    font-weight: 400;
  }
  .custom-option-item:hover .opt-desc,
  .custom-option-item.is-focused .opt-desc,
  .custom-option-item.is-selected .opt-desc {
    color: rgba(248, 250, 252, 0.88);
  }

  .check-icon {
    width: 14px;
    height: 14px;
    color: #67e8f9;
    flex-shrink: 0;
    margin-top: 2px;
  }
</style>
