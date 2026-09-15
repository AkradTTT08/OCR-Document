<script>
  import { onMount, afterUpdate } from "svelte";
  import { fade, fly, slide } from "svelte/transition";
  import { toast } from "./toastStore.js";

  const INITIAL_WELCOME = {
    role: 'assistant',
    content: `สวัสดีครับ ผมคือ **Master Agent (Orchestrator)** 🤖\n\nผมสามารถเชื่อมต่อและสั่งการ QA AI Agents ทุกตัวในระบบอัตโนมัติ (Security, Performance, SRS Consult, Test Automation)\n\nกรุณาเลือกเมนูด้านล่าง หรือพิมพ์สิ่งที่คุณต้องการให้ผมช่วยเหลือได้เลยครับ!`,
    timestamp: getFormattedTime()
  };

  let messages = [ INITIAL_WELCOME ];
  let currentInput = "";
  let isLoading = false;
  let chatContainer;
  let copiedIndex = null;

  function getFormattedTime() {
    const now = new Date();
    return now.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });
  }

  afterUpdate(() => {
    scrollToBottom();
  });

  function scrollToBottom() {
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  const QUICK_PROMPTS = [
    { icon: '🛡️', title: 'Security Audit', text: 'ช่วยตรวจสอบช่องโหว่ Security และ OWASP Top 10 ในโค้ด' },
    { icon: '⚡', title: 'Performance Plan', text: 'ช่วยวางแผนทดสอบ Load Testing & SLA ด้วย k6' },
    { icon: '📋', title: 'QA Test Cases', text: 'ช่วยสร้าง QA Test Cases และ Exit Criteria สำหรับฟีเจอร์ Login' },
    { icon: '🔍', title: 'Search KB', text: 'ช่วยค้นหาข้อมูลสรุปใน Knowledge Base ของระบบ' }
  ];

  function useQuickPrompt(text) {
    currentInput = text;
    sendMessage();
  }

  function clearChat() {
    messages = [ { ...INITIAL_WELCOME, timestamp: getFormattedTime() } ];
    toast("ล้างประวัติการสนทนาเรียบร้อยแล้ว", "info");
  }

  async function copyToClipboard(text, index) {
    try {
      await navigator.clipboard.writeText(text);
      copiedIndex = index;
      toast("คัดลอกข้อความลง Clipboard แล้ว", "success");
      setTimeout(() => { copiedIndex = null; }, 2000);
    } catch (err) {
      toast("ไม่สามารถคัดลอกข้อความได้", "error");
    }
  }

  async function sendMessage() {
    if (!currentInput.trim() || isLoading) return;
    
    const userMsgText = currentInput.trim();
    const userMsg = { role: 'user', content: userMsgText, timestamp: getFormattedTime() };
    messages = [...messages, userMsg];
    currentInput = "";
    isLoading = true;

    try {
      const response = await fetch("http://127.0.0.1:5000/api/qa/master", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to communicate with Master Agent");
      }

      messages = [...messages, { 
        role: 'assistant', 
        content: data.response || "ประมวลผลเสร็จสิ้น", 
        timestamp: getFormattedTime() 
      }];
    } catch (err) {
      toast(`Error: ${err.message}`, "error");
      messages = [...messages, { 
        role: 'assistant', 
        content: `เกิดข้อผิดพลาดในการเชื่อมต่อ: ${err.message}`, 
        timestamp: getFormattedTime() 
      }];
    } finally {
      isLoading = false;
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  // Lightweight Markdown Helper for Rich AI Responses
  function renderFormattedText(text) {
    if (!text) return "";
    let escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Code blocks ```code```
    escaped = escaped.replace(/```([\s\S]*?)```/g, (match, p1) => {
      return `<div class="code-block-wrapper"><div class="code-header"><span>CODE</span></div><pre><code>${p1.trim()}</code></pre></div>`;
    });

    // Inline code `code`
    escaped = escaped.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Bold **text**
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Bullet points
    escaped = escaped.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li class="list-item">$1</li>');
    escaped = escaped.replace(/(<li class="list-item">.*<\/li>)/s, '<ul class="custom-list">$1</ul>');

    // Paragraph linebreaks
    escaped = escaped.replace(/\n\n/g, '<br/><br/>');
    escaped = escaped.replace(/\n/g, '<br/>');

    return escaped;
  }
</script>

<div class="master-agent-outer-container">
  <div class="master-agent-container" in:fade={{ duration: 300 }}>
    <!-- Header Area -->
    <header class="agent-header">
      <div class="header-left">
        <div class="agent-avatar-glow">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24">
            <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h6z"></path>
            <path d="M22 10v6a2 2 0 0 1-2 2h-6l-4 4v-4H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
        </div>
        <div>
          <div class="title-row">
            <h2>Master Agent (Orchestrator)</h2>
            <span class="mcp-badge">
              <span class="pulse-dot"></span> MCP Ready
            </span>
          </div>
          <p class="subtitle">ศูนย์กลางระบบผู้ช่วยอัจฉริยะที่เชื่อมต่อ QA AI Agents ทุกโมดูลอัตโนมัติ</p>
        </div>
      </div>

      <div class="header-actions">
        <button class="btn-clear" on:click={clearChat} title="ล้างประวัติการสนทนา">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          <span>ล้างแชท</span>
        </button>
      </div>
    </header>

    <!-- Main Chat Card Floating Box -->
    <div class="chat-wrapper glass-panel">
      <!-- Chat Messages Area -->
      <div class="chat-messages" bind:this={chatContainer}>
        {#each messages as msg, i}
          <div class="message-row {msg.role}" in:fade={{ duration: 200 }}>
            <div class="message-bubble-wrapper">
              <div class="message-meta">
                <span class="role-name">{msg.role === 'assistant' ? 'Master Agent' : 'คุณ (User)'}</span>
                <span class="time-stamp">{msg.timestamp || ''}</span>
              </div>
              
              <div class="message-bubble {msg.role}">
                <div class="msg-icon-col">
                  {#if msg.role === 'assistant'}
                    <div class="msg-icon assistant-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                        <path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h6z"></path>
                        <path d="M22 10v6a2 2 0 0 1-2 2h-6l-4 4v-4H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                      </svg>
                    </div>
                  {:else}
                    <div class="msg-icon user-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                      </svg>
                    </div>
                  {/if}
                </div>

                <div class="msg-body">
                  <div class="markdown-preview">
                    {@html renderFormattedText(msg.content)}
                  </div>
                </div>

                {#if msg.role === 'assistant'}
                  <button 
                    class="btn-copy-msg" 
                    on:click={() => copyToClipboard(msg.content, i)} 
                    title="คัดลอกข้อความ"
                  >
                    {#if copiedIndex === i}
                      <svg viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" width="15" height="15"><polyline points="20 6 9 17 4 12"></polyline></svg>
                    {:else}
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    {/if}
                  </button>
                {/if}
              </div>
            </div>
          </div>
        {/each}

        {#if isLoading}
          <div class="message-row assistant" in:slide={{ duration: 200 }}>
            <div class="message-bubble-wrapper">
              <div class="message-meta">
                <span class="role-name">Master Agent</span>
                <span class="time-stamp">กำลังประมวลผล...</span>
              </div>
              <div class="message-bubble assistant loading-bubble">
                <div class="msg-icon assistant-icon pulse">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h6z"></path><path d="M22 10v6a2 2 0 0 1-2 2h-6l-4 4v-4H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                </div>
                <div class="msg-body">
                  <div class="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                  <div class="loading-label">กำลังวิเคราะห์ข้อมูลและประสานงานกับ QA Tools...</div>
                </div>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Quick Action Prompt Chips (Shown when messages are minimal or input empty) -->
      {#if messages.length <= 2 && !isLoading}
        <div class="quick-prompts-section" transition:slide>
          <div class="quick-prompts-title">คำสั่งแนะนำด่วน (Quick Suggestions):</div>
          <div class="quick-prompts-grid">
            {#each QUICK_PROMPTS as qp}
              <button class="quick-prompt-chip" on:click={() => useQuickPrompt(qp.text)}>
                <span class="qp-icon">{qp.icon}</span>
                <div class="qp-text">
                  <span class="qp-title">{qp.title}</span>
                  <span class="qp-desc">{qp.text}</span>
                </div>
              </button>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Bottom Floating Input Area -->
      <div class="chat-input-area">
        <div class="input-container">
          <textarea 
            bind:value={currentInput} 
            on:keydown={handleKeydown}
            placeholder="สั่งงาน Master Agent ได้ที่นี่... (เช่น ช่วยเช็ค Security โค้ด https://github.com/...)"
            disabled={isLoading}
            rows="1"
          ></textarea>
          
          <div class="input-actions">
            <span class="input-hint">Enter เพื่อส่ง • Shift+Enter ขึ้นบรรทัดใหม่</span>
            <button 
              class="btn-send {currentInput.trim() ? 'active' : ''}" 
              on:click={sendMessage} 
              disabled={isLoading || !currentInput.trim()}
              title="ส่งข้อความ"
            >
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  /* Outer container with generous padding to prevent screen edge clinging */
  .master-agent-outer-container {
    width: 100%;
    height: 100%;
    padding: 20px 24px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .master-agent-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
    height: 100%;
    width: 100%;
    max-width: 100%;
    margin: 0;
    min-height: 0;
  }

  /* Header Styling */
  .agent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(18, 20, 28, 0.5);
    border: 1px solid var(--glass-border);
    backdrop-filter: blur(12px);
    padding: 16px 24px;
    border-radius: 18px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .agent-avatar-glow {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.8), rgba(168, 85, 247, 0.8));
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    box-shadow: 0 0 18px rgba(168, 85, 247, 0.4);
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .title-row h2 {
    font-size: 20px;
    font-weight: 700;
    margin: 0;
    background: linear-gradient(135deg, #ffffff, #c7d2fe, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-family: var(--font-th);
  }

  .mcp-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    color: #34d399;
    background: rgba(52, 211, 153, 0.12);
    border: 1px solid rgba(52, 211, 153, 0.25);
    padding: 3px 10px;
    border-radius: 20px;
  }

  .pulse-dot {
    width: 6px;
    height: 6px;
    background: #34d399;
    border-radius: 50%;
    box-shadow: 0 0 8px #34d399;
    animation: pulseGlow 1.8s infinite ease-in-out;
  }

  @keyframes pulseGlow {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.8); }
  }

  .subtitle {
    margin: 4px 0 0 0;
    font-size: 13px;
    color: var(--text-muted);
    font-family: var(--font-th);
  }

  .btn-clear {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-clear:hover {
    background: rgba(244, 63, 94, 0.15);
    border-color: rgba(244, 63, 94, 0.3);
    color: #f43f5e;
  }

  /* Chat Wrapper Floating Box */
  .chat-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    border-radius: 22px;
    border: 1px solid var(--glass-border);
    background: rgba(18, 20, 28, 0.55);
    backdrop-filter: blur(20px);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 22px;
    scroll-behavior: smooth;
  }

  /* Message Rows & Bubbles */
  .message-row {
    display: flex;
    width: 100%;
  }

  .message-row.user {
    justify-content: flex-end;
  }

  .message-bubble-wrapper {
    max-width: 82%;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .message-row.user .message-bubble-wrapper {
    align-items: flex-end;
  }

  .message-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 4px;
    font-size: 11px;
  }

  .role-name {
    font-weight: 600;
    color: var(--secondary);
  }

  .message-row.user .role-name {
    color: #818cf8;
  }

  .time-stamp {
    color: var(--text-dim);
  }

  .message-bubble {
    display: flex;
    gap: 14px;
    padding: 16px 20px;
    border-radius: 18px;
    position: relative;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    border: 1px solid var(--glass-border);
    background: rgba(24, 27, 40, 0.85);
  }

  .message-bubble.assistant {
    border-top-left-radius: 4px;
    border-color: rgba(168, 85, 247, 0.2);
    background: rgba(24, 27, 42, 0.9);
  }

  .message-bubble.user {
    border-top-right-radius: 4px;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.25), rgba(168, 85, 247, 0.25));
    border: 1px solid rgba(99, 102, 241, 0.35);
  }

  .msg-icon-col {
    flex-shrink: 0;
    margin-top: 2px;
  }

  .msg-icon {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .assistant-icon {
    background: rgba(168, 85, 247, 0.15);
    color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.3);
  }

  .user-icon {
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.3);
  }

  .msg-body {
    flex: 1;
    min-width: 0;
    line-height: 1.6;
    font-size: 14px;
    color: #f1f5f9;
  }

  .btn-copy-msg {
    position: absolute;
    top: 12px;
    right: 12px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: var(--text-muted);
    border-radius: 8px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    opacity: 0.6;
    transition: all 0.2s ease;
  }

  .message-bubble:hover .btn-copy-msg {
    opacity: 1;
  }

  .btn-copy-msg:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #fff;
  }

  /* Quick Action Prompts Section */
  .quick-prompts-section {
    padding: 14px 24px;
    background: rgba(12, 14, 22, 0.6);
    border-top: 1px solid var(--glass-border);
  }

  .quick-prompts-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    margin-bottom: 10px;
  }

  .quick-prompts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 10px;
  }

  .quick-prompt-chip {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
  }

  .quick-prompt-chip:hover {
    background: rgba(168, 85, 247, 0.12);
    border-color: rgba(168, 85, 247, 0.35);
    transform: translateY(-2px);
  }

  .qp-icon {
    font-size: 18px;
  }

  .qp-text {
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .qp-title {
    font-size: 13px;
    font-weight: 600;
    color: #e2e8f0;
  }

  .qp-desc {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Chat Input Area */
  .chat-input-area {
    padding: 16px 24px 20px 24px;
    border-top: 1px solid var(--glass-border);
    background: rgba(10, 11, 18, 0.7);
  }

  .input-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px 18px;
    border-radius: 16px;
    background: rgba(20, 23, 34, 0.85);
    border: 1px solid rgba(168, 85, 247, 0.25);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    transition: all 0.3s ease;
  }

  .input-container:focus-within {
    border-color: rgba(168, 85, 247, 0.6);
    box-shadow: 0 0 20px rgba(168, 85, 247, 0.2);
  }

  textarea {
    width: 100%;
    background: transparent;
    border: none;
    color: var(--text-main);
    font-family: var(--font-th);
    font-size: 14px;
    line-height: 1.5;
    resize: none;
    min-height: 42px;
    max-height: 160px;
    outline: none;
  }

  .input-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 8px;
  }

  .input-hint {
    font-size: 11px;
    color: var(--text-dim);
  }

  .btn-send {
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
    border: none;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: not-allowed;
    transition: all 0.2s ease;
  }

  .btn-send.active {
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: #ffffff;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
  }

  .btn-send.active:hover {
    transform: scale(1.06);
    box-shadow: 0 6px 20px rgba(168, 85, 247, 0.5);
  }

  /* Typing & Loading State */
  .typing-indicator {
    display: flex;
    align-items: center;
    gap: 5px;
    height: 20px;
  }

  .typing-indicator span {
    width: 7px;
    height: 7px;
    background: var(--secondary);
    border-radius: 50%;
    animation: typingBounce 1.4s infinite ease-in-out both;
  }

  .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
  .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

  @keyframes typingBounce {
    0%, 80%, 100% { transform: scale(0.3); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
  }

  .loading-label {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  /* Global Markdown formatting inside messages */
  :global(.markdown-preview .code-block-wrapper) {
    margin: 10px 0;
    border-radius: 10px;
    overflow: hidden;
    background: #0d1117;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  :global(.markdown-preview .code-header) {
    background: rgba(255, 255, 255, 0.05);
    padding: 6px 12px;
    font-size: 10px;
    font-weight: 700;
    color: var(--secondary);
    letter-spacing: 1px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  :global(.markdown-preview pre) {
    margin: 0;
    padding: 12px;
    overflow-x: auto;
    font-family: 'Fira Code', 'Courier New', monospace;
    font-size: 13px;
    color: #e6edf3;
  }

  :global(.markdown-preview .inline-code) {
    background: rgba(168, 85, 247, 0.15);
    color: #c084fc;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 12.5px;
  }

  :global(.markdown-preview .custom-list) {
    margin: 8px 0;
    padding-left: 20px;
  }

  :global(.markdown-preview .list-item) {
    margin-bottom: 4px;
  }
</style>
