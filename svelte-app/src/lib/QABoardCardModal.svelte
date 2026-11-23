<script>
  import { createEventDispatcher } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import {
    getCleanLabels,
    getCardVerdict,
    getPriorityMeta,
    parseCommentSegments
  } from './qaBoardUtils.js';

  export let showDetailModal = false;
  export let selectedCard = null;
  export let columns = [];
  export let currentIntegration = null;
  export let selectedProjectId = '';
  export let isSavingSelected = false;

  export let newCommentText = '';
  export let commentAttachments = [];
  export let isSendingComment = false;
  export let isUploadingAttachment = false;

  const dispatch = createEventDispatcher();

  let showComments = true;
  let commentFileInput = null;
  let commentTextareaRef = null;
  let confirmDiscardDraft = false;

  // Inline link popover state (replaces window.prompt!)
  let showLinkPopover = false;
  let linkUrlInput = '';
  let linkTextInput = '';
  let linkUrlError = '';

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const fadeDur = prefersReducedMotion ? 0 : 150;
  const scaleDur = prefersReducedMotion ? 0 : 180;

  $: providerLabel = currentIntegration?.provider === 'github' ? 'GitHub' : 'Trello';
  $: hasDraft = Boolean(newCommentText.trim() || commentAttachments.length > 0);
  $: verdict = getCardVerdict(selectedCard);
  $: prioMeta = getPriorityMeta(selectedCard);

  export function requestClose() {
    if (hasDraft && !confirmDiscardDraft) {
      confirmDiscardDraft = true;
      return;
    }
    confirmDiscardDraft = false;
    showLinkPopover = false;
    dispatch('close');
  }

  function forceCloseDiscard() {
    confirmDiscardDraft = false;
    showLinkPopover = false;
    dispatch('close');
  }

  function getExternalUrl(card) {
    if (!card || !currentIntegration) return null;
    if (currentIntegration.provider === 'trello' && card.raw_ext_id) {
      return `https://trello.com/c/${card.raw_ext_id}`;
    }
    if (currentIntegration.provider === 'github' && card.raw_ext_id) {
      return `https://github.com/${currentIntegration.github_owner}/${currentIntegration.github_repo}/issues/${card.raw_ext_id}`;
    }
    return null;
  }

  function handleStatusSelectChange(e) {
    const newStatus = e.currentTarget.value;
    if (selectedCard && newStatus && newStatus !== selectedCard.status) {
      dispatch('moveCard', { card: selectedCard, targetColumnId: newStatus });
    }
  }

  function openLinkPopover() {
    showLinkPopover = !showLinkPopover;
    linkUrlError = '';
    if (showLinkPopover && !linkUrlInput) {
      linkUrlInput = 'https://';
    }
  }

  function applyInsertLink() {
    const cleanUrl = (linkUrlInput || '').trim();
    if (!cleanUrl || cleanUrl === 'https://' || cleanUrl === 'http://') {
      linkUrlError = 'กรุณาระบุ URL ที่ถูกต้อง';
      return;
    }
    const label = (linkTextInput || '').trim() || cleanUrl;
    const insertion = ` [${label}](${cleanUrl}) `;
    if (commentTextareaRef) {
      const start = commentTextareaRef.selectionStart ?? newCommentText.length;
      const end = commentTextareaRef.selectionEnd ?? newCommentText.length;
      newCommentText = newCommentText.slice(0, start) + insertion + newCommentText.slice(end);
    } else {
      newCommentText = (newCommentText ? newCommentText + ' ' : '') + insertion;
    }
    linkUrlInput = '';
    linkTextInput = '';
    linkUrlError = '';
    showLinkPopover = false;
    setTimeout(() => commentTextareaRef?.focus(), 30);
  }

  function handleAvatarError(e) {
    e.currentTarget.style.display = 'none';
    if (e.currentTarget.nextElementSibling) {
      e.currentTarget.nextElementSibling.style.display = 'inline-flex';
    }
  }

  function trapFocus(e) {
    if (e.key !== 'Tab') return;
    const dialog = e.currentTarget;
    if (!dialog) return;
    const focusables = dialog.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
</script>

{#if showDetailModal && selectedCard}
  <div
    class="obs-detail-backdrop"
    role="presentation"
    transition:fade={{ duration: fadeDur }}
    on:click={requestClose}
  >
    <div
      class="obs-detail-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="detail-card-title"
      tabindex="-1"
      on:keydown={trapFocus}
      on:click|stopPropagation
      in:scale={{ start: 0.96, duration: scaleDur }}
    >
      <!-- Top Bar: Real Status Select + RAG Action + External Link + Close -->
      <div class="detail-topbar">
        <div class="detail-top-left">
          <label class="status-select-wrap">
            <span class="sr-only">เปลี่ยนสถานะคอลัมน์</span>
            <select
              class="column-status-select"
              value={selectedCard.status || (columns[0]?.id ?? 'todo')}
              on:change={handleStatusSelectChange}
              aria-label="สถานะคอลัมน์ของการ์ด"
            >
              {#each columns as col}
                <option value={col.id}>{col.title}</option>
              {/each}
            </select>
          </label>

          {#if selectedCard.is_saved}
            <span class="saved-rag-pill">
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="13" height="13">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              บันทึกในโครงการ & RAG Indexed
            </span>
          {/if}
        </div>

        <div class="detail-top-right">
          {#if !selectedCard.is_saved}
            <button
              type="button"
              class="btn-top-save-rag"
              on:click={() => dispatch('saveSingle', selectedCard)}
              disabled={isSavingSelected}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                <polyline points="17 21 17 13 7 13 7 21"></polyline>
              </svg>
              บันทึกเข้าโครงการ & RAG
            </button>
          {:else}
            <button
              type="button"
              class="btn-top-unsave"
              on:click={(e) => dispatch('unsave', { card: selectedCard, event: e })}
            >
              ยกเลิกบันทึก
            </button>
          {/if}

          {#if getExternalUrl(selectedCard)}
            <a
              href={getExternalUrl(selectedCard)}
              target="_blank"
              rel="noreferrer"
              class="btn-ext-link"
            >
              <span>เปิดใน {providerLabel}</span>
              <svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
            </a>
          {/if}

          <button type="button" class="btn-icon-close" aria-label="ปิดรายละเอียดการ์ด" on:click={requestClose}>
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <!-- Unsaved Comment / Attachment Draft Warning Banner -->
      {#if confirmDiscardDraft}
        <div class="draft-warning-banner" role="alert">
          <span>มีข้อความคอมเมนต์หรือไฟล์แนบที่ยังไม่ได้บันทึก ต้องการละทิ้งและปิดหน้าต่างนี้หรือไม่?</span>
          <div class="draft-warning-actions">
            <button type="button" class="btn-draft-keep" on:click={() => (confirmDiscardDraft = false)}>กลับไปเขียนต่อ</button>
            <button type="button" class="btn-draft-discard" on:click={forceCloseDiscard}>ละทิ้งและปิด</button>
          </div>
        </div>
      {/if}

      <!-- Card Title & Metadata Grid -->
      <div class="detail-title-section">
        <div class="detail-title-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <rect x="3" y="4" width="18" height="16" rx="2"></rect>
            <line x1="7" y1="8" x2="17" y2="8"></line>
            <line x1="7" y1="12" x2="13" y2="12"></line>
          </svg>
        </div>
        <h2 id="detail-card-title" class="detail-card-title">{selectedCard.title}</h2>
      </div>

      <div class="detail-meta-grid">
        <div class="meta-group">
          <span class="meta-group-title">ผู้รับผิดชอบ (Members)</span>
          <div class="meta-group-content">
            {#if selectedCard.members && selectedCard.members.length > 0}
              {#each selectedCard.members as member}
                {#if member.avatar}
                  <img
                    src={member.avatar}
                    alt={member.name}
                    class="member-avatar-large"
                    title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}"
                    on:error={handleAvatarError}
                  />
                  <span class="member-initials-large" style="display: none;" title={member.name}>{member.initials || 'M'}</span>
                {:else}
                  <span class="member-initials-large" title={member.name}>{member.initials || 'M'}</span>
                {/if}
              {/each}
            {:else}
              <span class="no-meta-text">ไม่ได้ระบุ</span>
            {/if}
          </div>
        </div>

        <div class="meta-group">
          <span class="meta-group-title">ป้ายกำกับ (Labels)</span>
          <div class="meta-group-content">
            {#if getCleanLabels(selectedCard.labels).length > 0}
              {#each getCleanLabels(selectedCard.labels) as label}
                <span
                  class="label-pill-large"
                  style="background-color: {label.color}; color: {label.textColor};"
                >
                  {label.name}
                </span>
              {/each}
            {:else}
              <span class="no-meta-text">ไม่มีป้ายกำกับ</span>
            {/if}
          </div>
        </div>

        <div class="meta-group">
          <span class="meta-group-title">Story Points</span>
          <div class="meta-group-content">
            <span class="points-pill-large">{selectedCard.story_points || '1'} pts</span>
          </div>
        </div>

        <div class="meta-group">
          <span class="meta-group-title">ความสำคัญ / ประเภท</span>
          <div class="meta-group-content">
            <span class="priority-pill-large prio-{prioMeta.level}">
              {prioMeta.label}
            </span>
          </div>
        </div>
      </div>

      <!-- 2-Column Body: Left (Description + Single AI Agent Test Suite), Right (Comments & Activity) -->
      <div class="detail-2col-body">
        <div class="detail-col-main">
          <div class="section-header-row">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
              <line x1="17" y1="10" x2="3" y2="10"></line>
              <line x1="21" y1="6" x2="3" y2="6"></line>
              <line x1="21" y1="14" x2="3" y2="14"></line>
              <line x1="17" y1="18" x2="3" y2="18"></line>
            </svg>
            <h3 class="section-title">รายละเอียด (Description)</h3>
          </div>

          <div class="description-box">
            {#if selectedCard.description}
              <div class="desc-content">
                {#each parseCommentSegments(selectedCard.description, selectedProjectId) as segment}
                  {#if segment.type === 'text'}
                    <span>{segment.content}</span>
                  {:else if segment.type === 'image'}
                    <button
                      type="button"
                      class="comment-image-btn"
                      on:click={() => dispatch('previewImage', { url: segment.url, alt: segment.alt })}
                    >
                      <img src={segment.url} alt={segment.alt} class="comment-attached-image" loading="lazy" />
                    </button>
                  {:else if segment.type === 'video'}
                    <div class="comment-video-container">
                      <video src={segment.url} controls class="comment-video-player" preload="metadata">
                        <track kind="captions" />
                      </video>
                      <div class="video-meta-bar">
                        <span>{segment.alt || 'Video attachment'}</span>
                        <a href={segment.url} target="_blank" rel="noreferrer" class="video-open-link">เปิดในแท็บใหม่ ↗</a>
                      </div>
                    </div>
                  {:else if segment.type === 'link'}
                    <a href={segment.url} target="_blank" rel="noopener noreferrer" class="comment-rich-link">
                      {segment.text || segment.url}
                    </a>
                  {/if}
                {/each}
              </div>
            {:else}
              <div class="desc-content no-data-text">ไม่มีรายละเอียดระบุไว้สำหรับการ์ดนี้</div>
            {/if}
          </div>

          <!-- Consolidated AI Agent Tester & Verification Suite -->
          <div class="agent-suite-box">
            <div class="agent-box-header">
              <div class="agent-title-wrap">
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                  <rect x="3" y="11" width="18" height="10" rx="2"></rect>
                  <circle cx="12" cy="5" r="2"></circle>
                  <path d="M12 7v4"></path>
                  <line x1="8" y1="16" x2="8" y2="16"></line>
                  <line x1="16" y1="16" x2="16" y2="16"></line>
                </svg>
                <h4>AI Agent Tester & Verification</h4>
              </div>

              <button
                type="button"
                class="btn-run-agent"
                on:click={() => dispatch('runAgentTest', selectedCard)}
                disabled={verdict === 'testing'}
              >
                {#if verdict === 'testing'}
                  <span class="spinner-small"></span> กำลังรันการทดสอบ...
                {:else}
                  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="14" height="14">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                  </svg>
                  รันทดสอบด้วย AI Agent
                {/if}
              </button>
            </div>

            <div class="agent-box-content">
              {#if verdict === 'testing' || selectedCard.status === 'testing'}
                <div class="testing-indicator-large">
                  <span class="spinner-small"></span> AI Agent กำลังทดสอบระบบอัตโนมัติสำหรับการ์ดนี้...
                </div>
              {:else if selectedCard.test_result}
                <div class="agent-report-container">
                  {#if verdict === 'failed'}
                    <div class="test-verdict-badge failed">
                      FAILED — พบข้อบกพร่องจากการทดสอบ (Defect Detected)
                    </div>
                  {:else}
                    <div class="test-verdict-badge passed">
                      PASSED — ตรวจสอบผ่านตามเกณฑ์ทั้งหมด
                    </div>
                  {/if}
                  {#each parseCommentSegments(typeof selectedCard.test_result === 'object' ? JSON.stringify(selectedCard.test_result, null, 2) : selectedCard.test_result, selectedProjectId) as segment}
                    {#if segment.type === 'text'}
                      <pre class="test-result-pre" class:failed={verdict === 'failed'}>{segment.content}</pre>
                    {:else if segment.type === 'image'}
                      <button
                        type="button"
                        class="comment-image-btn"
                        on:click={() => dispatch('previewImage', { url: segment.url, alt: segment.alt })}
                      >
                        <img src={segment.url} alt={segment.alt} class="comment-attached-image" loading="lazy" />
                      </button>
                    {:else if segment.type === 'link'}
                      <a href={segment.url} target="_blank" rel="noopener noreferrer" class="comment-rich-link">
                        {segment.text || segment.url}
                      </a>
                    {/if}
                  {/each}
                </div>
              {:else}
                <p class="untested-hint">ยังไม่ได้รันการทดสอบอัตโนมัติสำหรับการ์ดใบนี้ กดปุ่ม <strong>"รันทดสอบด้วย AI Agent"</strong> ด้านบนเพื่อเริ่มตรวจสอบ</p>
              {/if}
            </div>
          </div>
        </div>

        <!-- Right Column: Comments & Activity -->
        <div class="detail-col-sidebar">
          <div class="section-header-row">
            <div class="sidebar-title-left">
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
              <h3 class="section-title">ความคิดเห็นและกิจกรรม</h3>
              {#if selectedCard.actions && selectedCard.actions.length > 0}
                <span class="comment-count-badge">{selectedCard.actions.length}</span>
              {/if}
            </div>

            <button
              type="button"
              class="btn-toggle-comments"
              on:click={() => (showComments = !showComments)}
            >
              {showComments ? 'ซ่อน' : `แสดง (${selectedCard.actions ? selectedCard.actions.length : 0})`}
            </button>
          </div>

          {#if showComments}
            <div class="comment-input-area">
              <div class="comment-box-wrapper" class:is-uploading={isUploadingAttachment}>
                <textarea
                  bind:this={commentTextareaRef}
                  bind:value={newCommentText}
                  on:paste={(e) => dispatch('commentPaste', e)}
                  placeholder="พิมพ์ความคิดเห็น หรือกด Ctrl+V เพื่อวางภาพหน้าจอ / วิดีโอ..."
                  aria-label="พิมพ์ความคิดเห็น"
                  rows="3"
                ></textarea>

                {#if commentAttachments.length > 0}
                  <div class="composer-attachments-grid">
                    {#each commentAttachments as att (att.id)}
                      <div class="composer-media-card">
                        <button
                          type="button"
                          class="btn-del-media-card"
                          aria-label={`ลบไฟล์แนบ ${att.filename || ''}`}
                          on:click={() => dispatch('removeAttachment', att.id)}
                          title="ลบไฟล์แนบนี้"
                        >
                          ✕
                        </button>
                        {#if att.type === 'image'}
                          <button
                            type="button"
                            class="composer-img-btn"
                            on:click={() => dispatch('previewImage', { url: att.url, alt: att.filename || 'Attached Image' })}
                          >
                            <img src={att.url} alt={att.filename || 'Attached Image'} class="composer-preview-img" />
                          </button>
                        {:else}
                          <video src={att.url} controls class="composer-preview-video">
                            <track kind="captions" />
                          </video>
                        {/if}
                      </div>
                    {/each}
                  </div>
                {/if}

                {#if isUploadingAttachment}
                  <div class="comment-uploading-overlay">
                    <span class="spinner-small"></span> กำลังอัปโหลดไฟล์แนบ...
                  </div>
                {/if}

                <!-- Inline Link Popover (replaces window.prompt!) -->
                {#if showLinkPopover}
                  <div class="inline-link-popover" role="region" aria-label="แทรกลิงก์">
                    <div class="link-popover-row">
                      <input
                        type="url"
                        placeholder="URL เช่น https://example.com"
                        aria-label="URL ลิงก์"
                        bind:value={linkUrlInput}
                        on:keydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); applyInsertLink(); } }}
                      />
                      <input
                        type="text"
                        placeholder="ข้อความแสดงผล (ไม่บังคับ)"
                        aria-label="ข้อความแสดงผลสำหรับลิงก์"
                        bind:value={linkTextInput}
                        on:keydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); applyInsertLink(); } }}
                      />
                    </div>
                    {#if linkUrlError}
                      <span class="field-error-msg">{linkUrlError}</span>
                    {/if}
                    <div class="link-popover-actions">
                      <button type="button" class="btn-link-cancel" on:click={() => (showLinkPopover = false)}>ยกเลิก</button>
                      <button type="button" class="btn-link-insert" on:click={applyInsertLink}>แทรกลิงก์</button>
                    </div>
                  </div>
                {/if}

                <div class="comment-toolbar">
                  <div class="toolbar-actions">
                    <input
                      type="file"
                      accept="image/*,video/*"
                      bind:this={commentFileInput}
                      on:change={(e) => dispatch('fileChange', e)}
                      style="display: none;"
                    />
                    <button
                      type="button"
                      class="btn-comment-tool"
                      on:click={() => commentFileInput?.click()}
                      title="แนบไฟล์รูปภาพหรือวิดีโอ"
                    >
                      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                        <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                      </svg>
                      แนบไฟล์
                    </button>
                    <button
                      type="button"
                      class="btn-comment-tool"
                      class:active={showLinkPopover}
                      on:click={openLinkPopover}
                      title="แทรกลิงก์"
                    >
                      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
                        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
                      </svg>
                      แทรกลิงก์
                    </button>
                    <span class="clipboard-paste-hint">
                      <kbd>Ctrl</kbd>+<kbd>V</kbd> วางรูปแคปจอ
                    </span>
                  </div>

                  {#if hasDraft}
                    <button
                      type="button"
                      class="btn-save-comment"
                      on:click={() => dispatch('postComment')}
                      disabled={isSendingComment || isUploadingAttachment}
                    >
                      {isSendingComment ? 'กำลังส่ง...' : `ส่งความคิดเห็นไปยัง ${providerLabel}`}
                    </button>
                  {/if}
                </div>
              </div>
            </div>

            <div class="activity-timeline">
              {#if selectedCard.actions && selectedCard.actions.length > 0}
                {#each selectedCard.actions as act}
                  <div class="activity-item">
                    {#if act.user_avatar}
                      <img
                        src={act.user_avatar}
                        alt={act.user_name || 'User'}
                        class="act-avatar"
                        on:error={handleAvatarError}
                      />
                      <div class="act-initials" style="display: none;">
                        {act.user_name ? act.user_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'U'}
                      </div>
                    {:else}
                      <div class="act-initials">
                        {act.user_name ? act.user_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'U'}
                      </div>
                    {/if}
                    <div class="act-details">
                      <div class="act-text">
                        <strong>{act.user_name || 'User'}</strong>
                        {#each parseCommentSegments(act.text, selectedProjectId) as segment}
                          {#if segment.type === 'text'}
                            <span>{segment.content}</span>
                          {:else if segment.type === 'image'}
                            <button
                              type="button"
                              class="comment-image-btn"
                              on:click={() => dispatch('previewImage', { url: segment.url, alt: segment.alt })}
                            >
                              <img src={segment.url} alt={segment.alt} class="comment-attached-image" loading="lazy" />
                            </button>
                          {:else if segment.type === 'video'}
                            <div class="comment-video-container">
                              <video src={segment.url} controls class="comment-video-player" preload="metadata">
                                <track kind="captions" />
                              </video>
                            </div>
                          {:else if segment.type === 'link'}
                            <a href={segment.url} target="_blank" rel="noopener noreferrer" class="comment-rich-link">
                              {segment.text || segment.url}
                            </a>
                          {/if}
                        {/each}
                      </div>
                      <span class="act-date">
                        {act.date ? new Date(act.date).toLocaleString('th-TH', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                      </span>
                    </div>
                  </div>
                {/each}
              {:else}
                <div class="empty-activity-text">ยังไม่มีประวัติความคิดเห็นในการ์ดใบนี้</div>
              {/if}
            </div>
          {:else}
            <button type="button" class="comments-collapsed-placeholder" on:click={() => (showComments = true)}>
              ความคิดเห็นถูกซ่อนอยู่ — คลิกเพื่อแสดง ({selectedCard.actions ? selectedCard.actions.length : 0} รายการ)
            </button>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
  }

  .obs-detail-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(5, 5, 10, 0.8);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    z-index: var(--z-modal, 10000);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
  }

  .obs-detail-dialog {
    width: 100%;
    max-width: 1080px;
    max-height: calc(100dvh - 32px);
    background: var(--bg2);
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: var(--radius-lg);
    box-shadow: 0 28px 72px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    color: var(--text-main);
    font-family: var(--font-th);
  }

  .detail-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 20px;
    background: var(--bg);
    border-bottom: 1px solid var(--glass-border);
    flex-wrap: wrap;
  }

  .detail-top-left,
  .detail-top-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .column-status-select {
    min-height: 34px;
    padding: 6px 32px 6px 12px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 600;
    background-color: var(--surface-card);
    border: 1px solid rgba(129, 140, 248, 0.4);
    color: var(--text-main);
  }

  .saved-rag-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border-radius: 999px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.35);
    color: var(--success-soft-text);
    font-size: 12px;
    font-weight: 600;
  }

  .btn-top-save-rag,
  .btn-top-unsave,
  .btn-ext-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    text-decoration: none;
    transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
  }

  .btn-top-save-rag {
    background: var(--gradient-main);
    border: 1px solid rgba(129, 140, 248, 0.45);
    color: #ffffff;
  }

  .btn-top-unsave {
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.34);
    color: var(--danger-soft-text);
  }

  .btn-top-unsave:hover {
    background: rgba(244, 63, 94, 0.22);
  }

  .btn-ext-link {
    background: var(--surface-card);
    border: 1px solid var(--glass-border-light);
    color: var(--primary-soft-text);
  }

  .btn-ext-link:hover {
    background: var(--surface-card-hover);
    color: var(--primary-soft-text-hover);
  }

  .btn-icon-close {
    width: 34px;
    height: 34px;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .btn-icon-close:hover {
    color: var(--text-main);
    background: rgba(244, 63, 94, 0.16);
    border-color: rgba(244, 63, 94, 0.38);
  }

  .draft-warning-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 20px;
    background: rgba(245, 158, 11, 0.14);
    border-bottom: 1px solid rgba(245, 158, 11, 0.35);
    color: var(--warning-soft-text);
    font-size: 12.5px;
    flex-wrap: wrap;
  }

  .draft-warning-actions {
    display: flex;
    gap: 8px;
  }

  .btn-draft-keep,
  .btn-draft-discard {
    min-height: 30px;
    padding: 4px 12px;
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .btn-draft-keep {
    background: var(--surface-card);
    border: 1px solid var(--glass-border-light);
    color: var(--text-main);
  }

  .btn-draft-discard {
    background: var(--danger-solid);
    border: 1px solid var(--danger-solid);
    color: #ffffff;
  }

  .detail-title-section {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 18px 22px 10px;
  }

  .detail-title-icon {
    width: 34px;
    height: 34px;
    border-radius: var(--radius-sm);
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: var(--primary-soft-text);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
  }

  .detail-card-title {
    margin: 0;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-main);
    line-height: 1.4;
  }

  .detail-meta-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    padding: 6px 22px 16px;
    border-bottom: 1px solid var(--glass-border);
  }

  .meta-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .meta-group-title {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--text-dim);
  }

  .meta-group-content {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .member-avatar-large {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    object-fit: cover;
    border: 1px solid var(--glass-border-light);
  }

  .member-initials-large,
  .act-initials {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: var(--primary-soft-text);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 11.5px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .label-pill-large {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
  }

  .points-pill-large {
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: var(--primary-soft-text);
    font-size: 12px;
    font-weight: 700;
    font-family: var(--font-en);
  }

  .priority-pill-large {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
  }

  .priority-pill-large.prio-high {
    background: rgba(244, 63, 94, 0.15);
    border-color: rgba(244, 63, 94, 0.35);
    color: var(--danger-soft-text);
  }

  .no-meta-text {
    font-size: 12px;
    color: var(--text-dim);
  }

  .detail-2col-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.95fr);
    gap: 20px;
    padding: 18px 22px 22px;
  }

  .detail-col-main,
  .detail-col-sidebar {
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-width: 0;
  }

  .section-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    color: var(--text-main);
  }

  .sidebar-title-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
  }

  .description-box {
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 14px 16px;
  }

  .desc-content {
    font-size: 13px;
    line-height: 1.65;
    color: var(--text-main);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .no-data-text {
    color: var(--text-dim);
    font-style: italic;
  }

  .agent-suite-box {
    background: var(--surface-card);
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .agent-box-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 12px 16px;
    background: rgba(168, 85, 247, 0.1);
    border-bottom: 1px solid rgba(168, 85, 247, 0.22);
    flex-wrap: wrap;
  }

  .agent-title-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--primary-soft-text-hover);
  }

  .agent-title-wrap h4 {
    margin: 0;
    font-size: 13.5px;
    font-weight: 600;
  }

  .btn-run-agent {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    background: var(--gradient-main);
    border: 1px solid rgba(168, 85, 247, 0.45);
    color: #ffffff;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .btn-run-agent:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .agent-box-content {
    padding: 14px 16px;
  }

  .untested-hint {
    margin: 0;
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .test-verdict-badge {
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    font-size: 12.5px;
    font-weight: 600;
    margin-bottom: 10px;
  }

  .test-verdict-badge.passed {
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.35);
    color: var(--success-soft-text);
  }

  .test-verdict-badge.failed {
    background: rgba(244, 63, 94, 0.15);
    border: 1px solid rgba(244, 63, 94, 0.38);
    color: var(--danger-soft-text);
  }

  .test-result-pre {
    margin: 0;
    padding: 12px;
    border-radius: var(--radius-sm);
    background: var(--bg);
    border: 1px solid var(--glass-border);
    font-size: 12px;
    line-height: 1.6;
    color: var(--text-main);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 300px;
    overflow-y: auto;
  }

  /* Comments & Activity */
  .comment-count-badge {
    font-size: 11px;
    font-weight: 700;
    padding: 1px 7px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.18);
    color: var(--primary-soft-text);
  }

  .btn-toggle-comments {
    min-height: 30px;
    padding: 4px 10px;
    border-radius: var(--radius-sm);
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
  }

  .comment-box-wrapper {
    background: var(--surface-card);
    border: 1px solid var(--glass-border-light);
    border-radius: var(--radius-md);
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .comment-box-wrapper textarea {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-sm);
    padding: 10px 12px;
    color: var(--text-main);
    font-size: 13px;
    resize: vertical;
    font-family: inherit;
  }

  .comment-box-wrapper textarea:focus {
    border-color: var(--primary);
    outline: none;
  }

  .composer-attachments-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .composer-media-card {
    position: relative;
    width: 96px;
    height: 72px;
    border-radius: var(--radius-sm);
    overflow: hidden;
    border: 1px solid var(--glass-border-light);
    background: var(--bg);
  }

  .btn-del-media-card {
    position: absolute;
    top: 4px;
    right: 4px;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: rgba(10, 11, 18, 0.85);
    border: 1px solid rgba(244, 63, 94, 0.45);
    color: var(--danger-soft-text);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    z-index: 2;
  }

  .composer-img-btn,
  .comment-image-btn {
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    display: block;
    width: 100%;
    height: 100%;
  }

  .composer-preview-img,
  .composer-preview-video {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .comment-attached-image {
    max-width: 100%;
    max-height: 220px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border);
    margin-top: 6px;
  }

  .inline-link-popover {
    padding: 10px;
    border-radius: var(--radius-sm);
    background: var(--bg);
    border: 1px solid rgba(129, 140, 248, 0.4);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .link-popover-row {
    display: grid;
    grid-template-columns: 1.2fr 1fr;
    gap: 8px;
  }

  .link-popover-row input {
    min-height: 34px;
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid var(--glass-border-light);
    background: var(--surface-card);
    color: var(--text-main);
    font-size: 12.5px;
  }

  .link-popover-actions {
    display: flex;
    justify-content: flex-end;
    gap: 6px;
  }

  .btn-link-cancel,
  .btn-link-insert {
    min-height: 30px;
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .btn-link-cancel {
    background: transparent;
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
  }

  .btn-link-insert {
    background: var(--primary);
    border: 1px solid var(--primary);
    color: #ffffff;
  }

  .field-error-msg {
    font-size: 11.5px;
    color: var(--danger-soft-text);
  }

  .comment-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
  }

  .toolbar-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .btn-comment-tool {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-height: 32px;
    padding: 5px 10px;
    border-radius: var(--radius-sm);
    background: var(--bg);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
  }

  .btn-comment-tool:hover,
  .btn-comment-tool.active {
    color: var(--text-main);
    border-color: var(--primary-soft-text);
  }

  .clipboard-paste-hint {
    font-size: 11px;
    color: var(--text-dim);
  }

  .clipboard-paste-hint kbd {
    padding: 1px 5px;
    border-radius: 4px;
    background: var(--bg);
    border: 1px solid var(--glass-border);
    font-family: var(--font-en);
  }

  .btn-save-comment {
    min-height: 34px;
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    background: var(--gradient-main);
    border: 1px solid rgba(129, 140, 248, 0.4);
    color: #ffffff;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .activity-timeline {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 380px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .activity-item {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 12px;
    border-radius: var(--radius-md);
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
  }

  .act-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    object-fit: cover;
    flex-shrink: 0;
  }

  .act-details {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .act-text {
    font-size: 12.5px;
    line-height: 1.5;
    color: var(--text-main);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .act-text strong {
    color: var(--primary-soft-text-hover);
    margin-right: 6px;
  }

  .act-date {
    font-size: 11px;
    color: var(--text-dim);
  }

  .comment-rich-link {
    color: var(--primary-soft-text);
    text-decoration: underline;
  }

  .empty-activity-text {
    font-size: 12.5px;
    color: var(--text-dim);
    font-style: italic;
    padding: 12px 4px;
  }

  .comments-collapsed-placeholder {
    width: 100%;
    min-height: 40px;
    padding: 10px;
    border-radius: var(--radius-md);
    background: var(--surface-card);
    border: 1px dashed var(--glass-border-light);
    color: var(--text-muted);
    font-size: 12.5px;
    cursor: pointer;
    font-family: inherit;
  }

  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.28);
    border-top-color: currentColor;
    border-radius: 50%;
    display: inline-block;
    animation: spinDetail 0.75s linear infinite;
  }

  @keyframes spinDetail { to { transform: rotate(360deg); } }

  @media (max-width: 860px) {
    .detail-2col-body {
      grid-template-columns: 1fr;
    }
    .link-popover-row {
      grid-template-columns: 1fr;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner-small { animation: none; }
  }
</style>

