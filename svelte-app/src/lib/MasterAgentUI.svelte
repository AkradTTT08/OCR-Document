<script>
  import { onMount, afterUpdate } from "svelte";
  import { fade } from "svelte/transition";
  import { toast } from "./toastStore.js";

  let messages = [
    { role: 'assistant', content: 'สวัสดีครับ ผมคือ Master Agent อัจฉริยะ (Orchestrator) 🤖\n\nผมสามารถเรียกใช้ Tool ในระบบได้ทั้งหมด (Security, Research, Consult)\nกรุณาพิมพ์สิ่งที่คุณต้องการให้ผมทำได้เลยครับ!' }
  ];
  let currentInput = "";
  let isLoading = false;
  let chatContainer;

  afterUpdate(() => {
    scrollToBottom();
  });

  function scrollToBottom() {
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  async function sendMessage() {
    if (!currentInput.trim() || isLoading) return;
    
    const userMsg = currentInput.trim();
    messages = [...messages, { role: 'user', content: userMsg }];
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

      messages = [...messages, { role: 'assistant', content: data.response }];
    } catch (err) {
      toast(`Error: ${err.message}`, "error");
      messages = [...messages, { role: 'assistant', content: `เกิดข้อผิดพลาด: ${err.message}` }];
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
</script>

<div class="master-agent-container" in:fade>
  <div class="header-text">
    <h2>Master Agent (Orchestrator) 🤖</h2>
    <p>ผู้ช่วยอัจฉริยะที่สามารถใช้งานและเชื่อมต่อกับ QA AI Agents ทุกตัวในระบบอัตโนมัติ (ผ่าน MCP & Tools)</p>
  </div>

  <div class="chat-wrapper main-card glass-panel">
    <!-- Chat Messages Area -->
    <div class="chat-messages" bind:this={chatContainer}>
      {#each messages as msg}
        <div class="message-row {msg.role}">
          <div class="message-bubble">
            {#if msg.role === 'assistant'}
              <div class="msg-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h6z"></path><path d="M22 10v6a2 2 0 0 1-2 2h-6l-4 4v-4H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              </div>
            {:else}
              <div class="msg-icon user">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
              </div>
            {/if}
            <div class="msg-content">
              <div class="markdown-preview">
                {msg.content}
              </div>
            </div>
          </div>
        </div>
      {/each}

      {#if isLoading}
        <div class="message-row assistant">
          <div class="message-bubble">
            <div class="msg-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h6z"></path><path d="M22 10v6a2 2 0 0 1-2 2h-6l-4 4v-4H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
            </div>
            <div class="msg-content">
              <div class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
              <div style="font-size: 12px; color: var(--text-muted); margin-top: 8px;">กำลังวิเคราะห์และเรียกใช้ Tool...</div>
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- Input Area -->
    <div class="chat-input-area">
      <div class="input-container glass-panel">
        <textarea 
          bind:value={currentInput} 
          on:keydown={handleKeydown}
          placeholder="สั่งงาน Master Agent ได้ที่นี่... (เช่น ช่วยเช็ค Security โค้ด https://github.com/...)"
          disabled={isLoading}
        ></textarea>
        
        <div class="input-actions">
          <button class="btn-send {currentInput.trim() ? 'active' : ''}" on:click={sendMessage} disabled={isLoading || !currentInput.trim()}>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .master-agent-container {
    display: flex;
    flex-direction: column;
    gap: 24px;
    height: 100%;
    animation: fadeIn 0.4s ease-out;
  }

  .chat-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    padding: 0;
    border-radius: 16px;
  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    scroll-behavior: smooth;
  }

  .message-row {
    display: flex;
    width: 100%;
  }

  .message-row.user {
    justify-content: flex-end;
  }

  .message-bubble {
    display: flex;
    gap: 16px;
    max-width: 80%;
    background: rgba(0, 0, 0, 0.2);
    padding: 20px;
    border-radius: 16px;
    border: 1px solid var(--glass-border);
  }

  .message-row.user .message-bubble {
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    flex-direction: row-reverse;
  }

  .msg-icon {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: var(--surface);
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--glass-border);
    color: var(--primary);
  }

  .msg-icon.user {
    background: rgba(0,0,0,0.2);
    color: #cbd5e1;
  }

  .msg-content {
    flex: 1;
    min-width: 0;
  }

  .markdown-preview {
    white-space: pre-wrap;
    line-height: 1.6;
    color: #e2e8f0;
    font-size: 15px;
  }

  /* Chat Input Area */
  .chat-input-area {
    padding: 20px;
    border-top: 1px solid var(--glass-border);
    background: rgba(0,0,0,0.1);
  }

  .input-container {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 16px;
    background: rgba(0,0,0,0.3);
    border: 1px solid rgba(255,255,255,0.1);
    transition: border-color 0.3s;
  }
  .input-container:focus-within {
    border-color: rgba(99, 102, 241, 0.5);
  }

  textarea {
    flex: 1;
    background: transparent;
    border: none;
    color: var(--text-light);
    font-family: inherit;
    font-size: 15px;
    line-height: 1.5;
    resize: none;
    min-height: 24px;
    max-height: 200px;
    padding: 8px 0;
  }
  textarea:focus {
    outline: none;
  }

  .input-actions {
    display: flex;
    gap: 8px;
    align-items: center;
    padding-bottom: 4px;
  }

  .btn-send {
    background: rgba(255,255,255,0.05);
    color: var(--text-muted);
    border: none;
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-send.active {
    background: var(--primary);
    color: white;
  }
  .btn-send:hover.active {
    transform: scale(1.05);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  }

  /* Typing Indicator */
  .typing-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 24px;
  }
  .typing-indicator span {
    width: 6px;
    height: 6px;
    background: var(--primary);
    border-radius: 50%;
    animation: bounce 1.4s infinite ease-in-out both;
  }
  .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
  .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
  
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0); }
    40% { transform: scale(1); }
  }
</style>
