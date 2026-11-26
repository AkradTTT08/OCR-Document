<script>
  import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';

  export let value = '';
  export let options = []; // Array of { value, label, icon?, class?, color?, dotColor?, description?, badge? } or simple strings
  export let placeholder = 'เลือกรายการ...';
  export let disabled = false;
  export let width = '100%';
  export let minWidth = '140px';
  export let dropdownMinWidth = '';
  export let size = 'md'; // 'sm' | 'md' | 'lg'
  export let variant = 'default'; // 'default' | 'compact' | 'inline-method'
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
        color: opt.color || '',
        dotColor: opt.dotColor || '',
        description: opt.description || '',
        badge: opt.badge || ''
      };
    }
    return { value: opt, label: String(opt), icon: '', badgeClass: '', color: '', dotColor: '', description: '', badge: '' };
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

  async function scrollFocusedIntoView() {
    await tick();
    if (!menuEl || focusedIndex < 0) return;
    const optEl = menuEl.querySelector(`#${instanceUid}-opt-${focusedIndex}`);
    if (optEl && typeof optEl.scrollIntoView === 'function') {
      optEl.scrollIntoView({ block: 'nearest' });
    }
  }

  async function updatePosition() {
    if (!selectEl) return;
    await tick();
    const rect = selectEl.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const spaceAbove = rect.top;
    const maxCap = hasRichDescriptions ? 350 : 280;
    const rowEst = hasRichDescriptions ? 58 : (variant === 'compact' || variant === 'inline-method' ? 34 : 40);
    const estimatedMenuHeight = Math.min(normalizedOptions.length * rowEst + 14, maxCap);
    const parsedDropMin = parseInt(dropdownMinWidth, 10);
    const minMenuW = Number.isFinite(parsedDropMin) && parsedDropMin > 0 ? parsedDropMin : (variant === 'inline-method' ? 132 : 140);

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
      menuTop = rect.top - 5;
      menuMaxHeight = Math.max(150, Math.min(maxCap, spaceAbove - 12));
    } else {
      dropUp = false;
      menuTop = rect.bottom + 5;
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
      await scrollFocusedIntoView();
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
    if (e.key === 'Tab') {
      isOpen = false;
      focusedIndex = -1;
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
      if (len > 0) {
        focusedIndex = (focusedIndex + 1) % len;
        scrollFocusedIntoView();
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (len > 0) {
        focusedIndex = (focusedIndex - 1 + len) % len;
        scrollFocusedIntoView();
      }
    } else if (e.key === 'Home') {
      e.preventDefault();
      if (len > 0) {
        focusedIndex = 0;
        scrollFocusedIntoView();
      }
    } else if (e.key === 'End') {
      e.preventDefault();
      if (len > 0) {
        focusedIndex = len - 1;
        scrollFocusedIntoView();
      }
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < len) {
        selectOption(normalizedOptions[focusedIndex]);
      }
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const ch = e.key.toLowerCase();
      const start = (focusedIndex + 1) % Math.max(1, len);
      for (let step = 0; step < len; step++) {
        const idx = (start + step) % len;
        if (String(normalizedOptions[idx].label).toLowerCase().startsWith(ch)) {
          focusedIndex = idx;
          scrollFocusedIntoView();
          break;
        }
      }
    }
  }

  function handleOutsideClick(e) {
    if (isOpen) {
      if (selectEl && selectEl.contains(e.target)) return;
      if (menuEl && menuEl.contains(e.target)) return;
      isOpen = false;
      focusedIndex = -1;
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
  class="custom-select-wrapper size-{size} variant-{variant}"
  class:disabled
  class:is-open={isOpen}
  style="width: {width}; min-width: {minWidth};"
>
  <button
    bind:this={triggerEl}
    type="button"
    class="select-trigger-btn {selectedOption?.badgeClass || ''}"
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
        {#if selectedOption.dotColor}
          <span class="opt-dot" style="background-color: {selectedOption.dotColor};" aria-hidden="true"></span>
        {/if}
        {#if selectedOption.icon}<span class="opt-icon">{selectedOption.icon}</span>{/if}
        <span
          class="opt-label {selectedOption.badgeClass || ''}"
          style={selectedOption.color ? `color: ${selectedOption.color};` : undefined}
        >
          {selectedOption.label}
        </span>
      {:else}
        <span class="opt-placeholder">{placeholder}</span>
      {/if}
    </div>
    <svg class="chevron-icon" class:rotated={isOpen} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true">
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>
  </button>

  {#if isOpen}
    <div
      use:portal
      bind:this={menuEl}
      id="{instanceUid}-listbox"
      class="custom-dropdown-menu variant-{variant}"
      class:drop-up={dropUp}
      style="position: fixed; top: {menuTop}px; left: {menuLeft}px; width: {menuWidth}px; max-height: {menuMaxHeight}px; z-index: var(--z-portal, 10500);"
      role="listbox"
      aria-label={ariaLabel || placeholder}
    >
      {#each normalizedOptions as opt, idx}
        <button
          type="button"
          id="{instanceUid}-opt-{idx}"
          class="custom-option-item {opt.badgeClass || ''}"
          class:has-desc={Boolean(opt.description)}
          class:is-selected={String(opt.value) === String(value)}
          class:is-focused={idx === focusedIndex}
          on:mouseenter={() => (focusedIndex = idx)}
          on:click|stopPropagation={() => selectOption(opt)}
          on:keydown={handleKeydown}
          role="option"
          aria-selected={String(opt.value) === String(value)}
        >
          {#if opt.dotColor}
            <span class="opt-dot" style="background-color: {opt.dotColor};" aria-hidden="true"></span>
          {/if}
          {#if opt.icon}<span class="opt-icon">{opt.icon}</span>{/if}
          <div class="opt-body">
            <div class="opt-top-row">
              <span
                class="opt-text {opt.badgeClass || ''}"
                style={opt.color ? `color: ${opt.color};` : undefined}
              >
                {opt.label}
              </span>
              {#if opt.badge}
                <span class="opt-badge">{opt.badge}</span>
              {/if}
            </div>
            {#if opt.description}
              <span class="opt-desc">{opt.description}</span>
            {/if}
          </div>
          {#if String(opt.value) === String(value)}
            <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" aria-hidden="true">
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

  /* ── Default Spectra Trigger ── */
  .select-trigger-btn {
    width: 100%;
    min-height: 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    background-color: rgba(18, 20, 28, 0.85);
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
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.28), inset 0 1px 1px rgba(255, 255, 255, 0.06);
    transition: border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
  }

  .size-sm .select-trigger-btn { min-height: 34px; padding: 5px 10px; font-size: 12.5px; border-radius: 8px; }
  .size-lg .select-trigger-btn { min-height: 46px; padding: 11px 18px; font-size: 15px; border-radius: 12px; }

  .select-trigger-btn:hover:not(:disabled) {
    border-color: rgba(168, 85, 247, 0.72);
    background-color: rgba(24, 27, 40, 0.96);
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.2);
  }

  .is-open .select-trigger-btn,
  .select-trigger-btn:focus-visible {
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
  }

  /* ── Variant: Ultra-Compact Postman Dark ── */
  .variant-compact .select-trigger-btn {
    min-height: 34px;
    padding: 5px 10px;
    font-size: 12.5px;
    font-weight: 500;
    border-radius: 8px;
    background-color: #12141c;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    border: 1px solid rgba(255, 255, 255, 0.13);
    box-shadow: none;
  }

  .variant-compact.size-md .select-trigger-btn {
    min-height: 38px;
    padding: 7px 12px;
    font-size: 13px;
  }

  .variant-compact .select-trigger-btn:hover:not(:disabled) {
    border-color: rgba(255, 255, 255, 0.26);
    background-color: #171a26;
    box-shadow: none;
  }

  .variant-compact.is-open .select-trigger-btn,
  .variant-compact .select-trigger-btn:focus-visible {
    border-color: #6366f1;
    background-color: #171a26;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25);
  }

  .variant-compact .chevron-icon {
    width: 13px;
    height: 13px;
    color: #94a3b8;
  }

  .variant-compact.is-open .chevron-icon,
  .variant-compact .select-trigger-btn:hover:not(:disabled) .chevron-icon {
    color: #c7d2fe;
  }

  /* ── Variant: Inline HTTP Method Picker (inside Postman URL Bar) ── */
  .variant-inline-method {
    height: 100%;
    display: flex;
    align-items: stretch;
  }

  .variant-inline-method .select-trigger-btn {
    height: 100%;
    min-height: 40px;
    padding: 0 10px 0 14px;
    background-color: transparent;
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
    border: none;
    border-radius: 12px 0 0 12px;
    box-shadow: none;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.03em;
  }

  .variant-inline-method .select-trigger-btn:hover:not(:disabled),
  .variant-inline-method.is-open .select-trigger-btn {
    background-color: rgba(255, 255, 255, 0.04);
    box-shadow: none;
  }

  .variant-inline-method .select-trigger-btn:focus-visible {
    outline: none;
    background-color: rgba(99, 102, 241, 0.12);
    box-shadow: inset 0 0 0 1px rgba(99, 102, 241, 0.55);
  }

  .variant-inline-method .chevron-icon {
    width: 13px;
    height: 13px;
    color: #94a3b8;
  }

  .trigger-content {
    display: flex;
    align-items: center;
    gap: 7px;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .opt-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
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
    transition: transform 0.18s cubic-bezier(0.4, 0, 0.2, 1), color 0.15s ease;
  }

  .chevron-icon.rotated {
    transform: rotate(180deg);
  }

  /* ── Portaled Menu Surface ── */
  .custom-dropdown-menu {
    position: fixed !important;
    background-color: rgba(14, 16, 24, 0.98) !important;
    backdrop-filter: blur(20px) !important;
    -webkit-backdrop-filter: blur(20px) !important;
    border: 1px solid rgba(168, 85, 247, 0.35) !important;
    border-radius: 12px;
    box-shadow: 0 16px 38px rgba(0, 0, 0, 0.72), 0 0 0 1px rgba(255, 255, 255, 0.04);
    z-index: var(--z-portal, 10500);
    max-height: 280px;
    max-width: calc(100vw - 24px);
    overflow-y: auto;
    overflow-x: hidden;
    padding: 5px;
    box-sizing: border-box;
    animation: dropdownFadeIn 0.14s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .custom-dropdown-menu.variant-compact,
  .custom-dropdown-menu.variant-inline-method {
    background-color: #12141c !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 8px;
    padding: 4px;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.78), 0 0 0 1px rgba(99, 102, 241, 0.12);
  }

  .custom-dropdown-menu.drop-up {
    transform: translateY(-100%);
    animation: dropdownFadeInUp 0.14s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes dropdownFadeIn {
    from { opacity: 0; transform: translateY(-5px) scale(0.98); }
    to { opacity: 1; transform: translateY(0) scale(1); }
  }

  @keyframes dropdownFadeInUp {
    from { opacity: 0; transform: translateY(calc(-100% + 5px)) scale(0.98); }
    to { opacity: 1; transform: translateY(-100%) scale(1); }
  }

  .custom-dropdown-menu::-webkit-scrollbar { width: 5px; }
  .custom-dropdown-menu::-webkit-scrollbar-thumb {
    background: rgba(148, 163, 184, 0.35);
    border-radius: 8px;
  }

  /* ── Option Rows ── */
  .custom-option-item {
    width: 100%;
    border: none;
    background: transparent;
    text-align: left;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 8px 11px;
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 13px;
    font-weight: 400;
    font-family: var(--font-th, 'Prompt', sans-serif);
    cursor: pointer;
    transition: background-color 0.12s ease, color 0.12s ease;
  }

  .variant-compact .custom-option-item,
  .variant-inline-method .custom-option-item {
    padding: 6px 9px;
    font-size: 12.5px;
    border-radius: 8px;
  }

  .variant-inline-method .custom-option-item {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-weight: 700;
    letter-spacing: 0.03em;
  }

  .custom-option-item:hover,
  .custom-option-item.is-focused {
    background-color: rgba(99, 102, 241, 0.18);
    color: #ffffff;
  }

  .custom-option-item.is-selected {
    background-color: rgba(99, 102, 241, 0.28);
    color: #ffffff;
    font-weight: 600;
  }

  .opt-icon { font-size: 14px; flex-shrink: 0; }
  .opt-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
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
    padding: 8px 10px;
  }
  .custom-option-item.has-desc .opt-text {
    font-weight: 600;
    white-space: normal;
    line-height: 1.3;
  }
  .opt-badge {
    flex-shrink: 0;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 11px;
    font-weight: 600;
    padding: 1px 7px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(129, 140, 248, 0.35);
    color: #c7d2fe;
    font-variant-numeric: tabular-nums;
  }
  .opt-desc {
    font-size: 11.5px;
    line-height: 1.4;
    color: #94a3b8;
    white-space: normal;
    font-weight: 400;
  }
  .custom-option-item:hover .opt-desc,
  .custom-option-item.is-focused .opt-desc,
  .custom-option-item.is-selected .opt-desc {
    color: #cbd5e1;
  }

  .check-icon {
    width: 13px;
    height: 13px;
    color: #67e8f9;
    flex-shrink: 0;
    margin-top: 2px;
  }
</style>
