<script>
  import { onMount, afterUpdate } from "svelte";
  import { fade } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";

  let projects = [];
  $: selectedProjectObj = $selectedProjectStore;

  let messages = [
    { role: 'assistant', content: 'สวัสดีครับ! ผมคือ Rainbow 🌈\n\nผมสามารถช่วยคุณค้นหาและตอบคำถามเกี่ยวกับโครงการนี้ได้ โดยอ้างอิงจากเอกสารทั้งหมดที่เคยสแกนและจัดเก็บไว้ในฐานข้อมูลของเราครับ มีอะไรให้ผมช่วยไหมครับ?' }
  ];
  let currentInput = "";
  let isLoading = false;
  let chatContainer;
  let textareaElement;
  let abortController = null;
  let userScrolledUp = false;
  let copiedIndex = null;

  // Speech Recognition variables
  let isListening = false;
  let recognition;
  let originalInput = "";

  onMount(async () => {
    try {
      const resProjects = await fetch("/api/projects");
      if (resProjects.ok) {
        const pData = await resProjects.json();
        projects = pData.projects || [];
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }

    // Initialize SpeechRecognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognition = new SpeechRecognition();
      recognition.lang = 'th-TH'; // Set language to Thai
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        isListening = true;
      };

      recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }
        
        currentInput = originalInput + (originalInput ? " " : "") + (finalTranscript || interimTranscript);
      };

      recognition.onerror = (event) => {
        console.error("Speech recognition error", event.error);
        isListening = false;
      };

      recognition.onend = () => {
        isListening = false;
      };
    }
  });

  function handleScroll() {
    if (!chatContainer) return;
    const distanceToBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight;
    // If user scrolled up more than 60px from bottom, keep their scroll position
    userScrolledUp = distanceToBottom > 60;
  }

  function scrollToBottom(force = false) {
    if (chatContainer && (force || !userScrolledUp)) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  afterUpdate(() => {
    if (isLoading && !userScrolledUp) {
      scrollToBottom();
    }
  });

  function selectProject(p) {
    selectedProjectStore.set(p);
    messages = [
      { role: 'assistant', content: `สวัสดีครับ! ผม Rainbow 🌈 ยินดีต้อนรับสู่โครงการ **${p.project_code} - ${p.name}**\n\nคุณสามารถสอบถามข้อมูลใดๆ ที่เกี่ยวข้องกับโครงการนี้ได้เลยครับ` }
    ];
    userScrolledUp = false;
    setTimeout(() => scrollToBottom(true), 50);
  }

  function toggleListen() {
    if (!recognition) {
      toast("เบราว์เซอร์ของคุณไม่รองรับระบบสั่งงานด้วยเสียง (แนะนำ Google Chrome)", "warning");
      return;
    }
    if (isListening) {
      recognition.stop();
    } else {
      originalInput = currentInput.trim();
      recognition.start();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function resizeTextarea() {
    if (textareaElement) {
      textareaElement.style.height = 'auto';
      textareaElement.style.height = Math.min(textareaElement.scrollHeight, 140) + 'px';
    }
  }

  $: {
    currentInput;
    if (textareaElement) {
      setTimeout(resizeTextarea, 0);
    }
  }

  function sendPrompt(text) {
    if (isLoading) return;
    currentInput = text;
    sendMessage();
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

  // Lightweight Markdown Helper for Rich AI Responses
  function renderFormattedText(text) {
    if (!text) return "";
    let escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // Code blocks ```code```
    escaped = escaped.replace(/```([a-zA-Z]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
      return `<div class="code-block-wrapper"><div class="code-header"><span>${lang || 'CODE'}</span></div><pre><code>${code.trim()}</code></pre></div>`;
    });

    // Inline code `code`
    escaped = escaped.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

    // Bold **text**
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Bullet points
    escaped = escaped.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li class="list-item">$1</li>');
    escaped = escaped.replace(/(<li class="list-item">[\s\S]*?<\/li>)/g, '<ul class="custom-list">$1</ul>');

    // Paragraph linebreaks
    escaped = escaped.replace(/\n\n/g, '<br/><br/>');
    escaped = escaped.replace(/\n/g, '<br/>');

    return escaped;
  }

  async function sendMessage() {
    if (!currentInput.trim() || isLoading) return;
    
    const userMsg = currentInput.trim();
    currentInput = "";
    
    messages = [...messages, { role: 'user', content: userMsg }];
    isLoading = true;
    userScrolledUp = false;
    setTimeout(() => scrollToBottom(true), 50);
    abortController = new AbortController();

    try {
      const projectId = selectedProjectObj.id || selectedProjectObj.project_id;
      
      const response = await fetch("/api/research/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortController.signal,
        body: JSON.stringify({
          project_id: projectId,
          message: userMsg,
          history: messages.slice(0, -1)
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.error || `HTTP Error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      messages = [...messages, { role: 'assistant', content: '' }];
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const textChunk = decoder.decode(value, { stream: true });
        messages[messages.length - 1].content += textChunk;
        messages = [...messages];
        if (!userScrolledUp) {
          scrollToBottom();
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        toast("ยกเลิกการค้นหาข้อมูล", "info");
        messages = messages.slice(0, -1);
        currentInput = userMsg;
      } else {
        toast(`เกิดข้อผิดพลาด: ${err.message}`, "error");
        messages = [...messages, { role: 'assistant', content: 'ขออภัยครับ เกิดข้อผิดพลาดในการเชื่อมต่อกับระบบ AI' }];
      }
    } finally {
      isLoading = false;
      abortController = null;
    }
  }

  function cancelMessage() {
    if (abortController) {
      abortController.abort();
    }
  }

  function resetProject() {
    selectedProjectStore.set(null);
  }
</script>

<div class="qa-research-container" in:fade>
  {#if !selectedProjectObj}
    <ProjectSelection 
      {projects} 
      on:select={(e) => selectProject(e.detail)} 
    />
  {:else}
    <!-- Chat Interface -->
    <div class="top-nav">
      <button class="btn-back" on:click={resetProject}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        เปลี่ยนโครงการ
      </button>
    </div>

    <div class="header-text">
      <h2>QA Research (Rainbow AI) 🌈</h2>
      <p>ค้นหาและสอบถามข้อมูลเชิงลึกจากเอกสารทั้งหมดในโครงการด้วย Rainbow (Gemini Flash)</p>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code} - {selectedProjectObj.name}</strong>
      </div>
    </div>

    <div class="chat-wrapper main-card glass-panel">
      <!-- Chat Messages Area -->
      <div class="chat-messages" bind:this={chatContainer} on:scroll={handleScroll}>
        {#each messages as msg, i}
          <div class="message-row {msg.role}">
            <div class="message-bubble {msg.role}">
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
                <div class="msg-text markdown-preview">
                  {@html renderFormattedText(msg.content)}
                </div>
              </div>

              {#if msg.role === 'assistant' && msg.content}
                <button 
                  class="btn-copy-msg" 
                  on:click={() => copyToClipboard(msg.content, i)} 
                  title="คัดลอกข้อความ"
                >
                  {#if copiedIndex === i}
                    <svg viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" width="14" height="14"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  {:else}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  {/if}
                </button>
              {/if}
            </div>
          </div>
        {/each}

        {#if isLoading}
          <div class="message-row assistant">
            <div class="message-bubble assistant">
              <div class="msg-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h6z"></path><path d="M22 10v6a2 2 0 0 1-2 2h-6l-4 4v-4H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              </div>
              <div class="msg-content">
                <div class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              </div>
            </div>
          </div>
        {/if}
      </div>

      {#if messages.length <= 1}
        <div class="suggestions-container" in:fade>
          <div class="suggestions-title">💡 คำถามแนะนำเพื่อค้นหาข้อมูลเชิงลึก:</div>
          <div class="suggestion-chips">
            <button type="button" class="suggestion-chip" on:click={() => sendPrompt("สรุปภาพรวมและฟังก์ชันหลักทั้งหมดของระบบนี้ให้หน่อย")}>
              📋 สรุปภาพรวมและฟังก์ชันหลักทั้งหมด
            </button>
            <button type="button" class="suggestion-chip" on:click={() => sendPrompt("มีเอกสารอะไรบ้างในโครงการนี้ และแต่ละเอกสารมีเนื้อหาเกี่ยวกับอะไร")}>
              📄 เอกสารทั้งหมดในโครงการ
            </button>
            <button type="button" class="suggestion-chip" on:click={() => sendPrompt("เงื่อนไขการ Login, สิทธิ์ผู้ใช้งาน และ Security Validation มีอะไรบ้าง")}>
              🔐 เงื่อนไข Login & Security
            </button>
            <button type="button" class="suggestion-chip" on:click={() => sendPrompt("สรุป Test Scenarios และ Acceptance Criteria ที่สำคัญของโครงการ")}>
              🧪 Test Scenarios & เกณฑ์ผ่าน
            </button>
          </div>
        </div>
      {/if}

      <!-- Chat Input Area -->
      <div class="chat-input-area">
        <textarea
          bind:this={textareaElement}
          bind:value={currentInput}
          on:keydown={handleKeydown}
          on:input={resizeTextarea}
          placeholder={isListening ? "กำลังฟังเสียงของคุณ..." : "พิมพ์คำถามของคุณที่นี่... (Shift + Enter เพื่อขึ้นบรรทัดใหม่, Enter เพื่อส่ง)"}
          disabled={isLoading}
          rows="1"
        ></textarea>
        
        <button class="btn-mic {isListening ? 'listening' : ''}" on:click={toggleListen} disabled={isLoading} title="พูดด้วยเสียง">
          {#if isListening}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="6" height="6" rx="1"></rect></svg>
          {:else}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
          {/if}
        </button>

        <button 
          class="btn-send {isLoading ? 'btn-stop' : ''}" 
          on:click={isLoading ? cancelMessage : sendMessage} 
          disabled={!isLoading && !currentInput.trim()}
          title={isLoading ? "ยกเลิก" : "ส่งข้อความ"}
        >
          {#if isLoading}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="6" y="6" width="12" height="12" rx="2" ry="2"></rect>
            </svg>
          {:else}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          {/if}
        </button>
      </div>
    </div>
  {/if}
</div>

<style>
  .qa-research-container {
    width: 100%;
    max-width: 100%;
    margin: 0;
    padding: 16px 28px;
    display: flex;
    flex-direction: column;
    height: 100%;
    box-sizing: border-box;
    min-height: 0;
    overflow: hidden;
  }

  .top-nav {
    margin-bottom: 8px;
    flex-shrink: 0;
  }
  .btn-back {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 12.5px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-back:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }

  .header-text {
    text-align: center;
    margin-bottom: 12px;
    flex-shrink: 0;
  }
  .header-text h2 {
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 4px 0;
    background: linear-gradient(135deg, #a78bfa, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header-text p {
    color: #9ca3af;
    margin: 0 0 8px 0;
    font-size: 13px;
  }
  
  .active-project-badge {
    display: inline-block;
    background: rgba(59, 130, 246, 0.12);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #93c5fd;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 12px;
  }
  .active-project-badge strong {
    color: white;
  }

  .chat-wrapper {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    padding: 0;
    overflow: hidden;
    border-radius: 18px;
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.4);
  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 20px;
    scroll-behavior: smooth;
    scrollbar-width: thin;
    scrollbar-color: rgba(168, 85, 247, 0.6) rgba(15, 23, 42, 0.5);
  }

  .chat-messages::-webkit-scrollbar {
    width: 8px;
  }
  .chat-messages::-webkit-scrollbar-track {
    background: rgba(15, 23, 42, 0.5);
    border-radius: 4px;
  }
  .chat-messages::-webkit-scrollbar-thumb {
    background: rgba(168, 85, 247, 0.55);
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  .chat-messages::-webkit-scrollbar-thumb:hover {
    background: rgba(168, 85, 247, 0.85);
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
    gap: 12px;
    max-width: 90%;
    position: relative;
    align-items: flex-start;
  }

  .message-row.user .message-bubble {
    flex-direction: row-reverse;
  }

  .msg-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: conic-gradient(
      #ff0000, 
      #ff7f00, 
      #ffff00, 
      #00ff00, 
      #0000ff, 
      #4b0082, 
      #9400d3, 
      #ff0000
    );
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    position: relative;
    overflow: hidden;
  }
  .msg-icon::before {
    content: '';
    position: absolute;
    inset: -50%;
    background: inherit;
    animation: spin 6s linear infinite;
    z-index: 0;
  }
  .msg-icon svg {
    width: 18px;
    height: 18px;
    color: white;
    z-index: 1;
    filter: drop-shadow(0px 1px 2px rgba(0,0,0,0.4));
  }
  .msg-icon.user {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
  }
  .msg-icon.user::before {
    display: none;
  }

  @keyframes spin {
    100% { transform: rotate(360deg); }
  }

  .msg-content {
    background: rgba(15, 23, 42, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 16px 20px;
    border-radius: 14px;
    border-top-left-radius: 4px;
    color: #e2e8f0;
    font-size: 14.5px;
    line-height: 1.65;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
    position: relative;
    word-break: break-word;
  }

  .message-row.user .msg-content {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.3), rgba(168, 85, 247, 0.3));
    border-color: rgba(168, 85, 247, 0.3);
    border-top-left-radius: 14px;
    border-top-right-radius: 4px;
    color: #f8fafc;
  }

  .btn-copy-msg {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    border-radius: 6px;
    padding: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0.7;
    transition: all 0.2s;
    margin-top: 4px;
    flex-shrink: 0;
  }
  .btn-copy-msg:hover {
    opacity: 1;
    color: white;
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(168, 85, 247, 0.4);
  }

  /* Rich Markdown Styling */
  :global(.markdown-preview) {
    line-height: 1.7;
  }
  :global(.markdown-preview strong) {
    color: #f8fafc;
    font-weight: 600;
  }
  :global(.markdown-preview .inline-code) {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #67e8f9;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    font-family: monospace;
  }
  :global(.markdown-preview .code-block-wrapper) {
    margin: 10px 0;
    background: rgba(10, 15, 28, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    overflow: hidden;
  }
  :global(.markdown-preview .code-header) {
    background: rgba(255, 255, 255, 0.05);
    padding: 4px 12px;
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    font-weight: 600;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  :global(.markdown-preview pre) {
    margin: 0;
    padding: 12px 16px;
    overflow-x: auto;
  }
  :global(.markdown-preview pre code) {
    color: #a5f3fc;
    font-family: 'Fira Code', monospace;
    font-size: 13px;
  }
  :global(.markdown-preview .custom-list) {
    margin: 8px 0;
    padding-left: 20px;
    list-style-type: disc;
  }
  :global(.markdown-preview .list-item) {
    margin-bottom: 4px;
  }

  .suggestions-container {
    padding: 12px 24px 8px 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(15, 23, 42, 0.35);
    flex-shrink: 0;
  }

  .suggestions-title {
    font-size: 12px;
    color: #94a3b8;
    font-weight: 500;
  }

  .suggestion-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .suggestion-chip {
    background: rgba(168, 85, 247, 0.12);
    border: 1px solid rgba(168, 85, 247, 0.3);
    color: #d8b4fe;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
  }

  .suggestion-chip:hover {
    background: rgba(168, 85, 247, 0.25);
    border-color: #c084fc;
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(168, 85, 247, 0.2);
  }

  .chat-input-area {
    padding: 14px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(0, 0, 0, 0.25);
    display: flex;
    gap: 12px;
    align-items: flex-end;
    flex-shrink: 0;
  }

  .chat-input-area textarea {
    flex: 1;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: white;
    padding: 12px 16px;
    border-radius: 10px;
    font-family: inherit;
    font-size: 14.5px;
    resize: none;
    max-height: 140px;
    min-height: 44px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    line-height: 1.5;
    overflow-y: auto;
  }
  .chat-input-area textarea:focus {
    border-color: rgba(168, 85, 247, 0.6);
    box-shadow: 0 0 0 2px rgba(168, 85, 247, 0.15);
  }

  .btn-mic {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: transparent;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.2s;
    flex-shrink: 0;
  }
  .btn-mic svg {
    width: 20px;
    height: 20px;
  }
  .btn-mic:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.08);
    color: white;
  }
  .btn-mic.listening {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #ef4444;
    animation: pulse-mic 1.5s infinite;
  }
  
  @keyframes pulse-mic {
    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
  }

  .btn-send {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: linear-gradient(135deg, #8b5cf6, #3b82f6);
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    cursor: pointer;
    transition: all 0.2s;
    flex-shrink: 0;
  }
  .btn-send svg {
    width: 18px;
    height: 18px;
    margin-right: 2px;
  }
  .btn-send:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
  }
  .btn-send.btn-stop {
    background: rgba(239, 68, 68, 0.2);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.4);
  }
  .btn-send.btn-stop:hover {
    background: rgba(239, 68, 68, 0.3);
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
  }
  .btn-send.btn-stop svg {
    margin-right: 0;
  }
  .btn-send:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    background: rgba(255, 255, 255, 0.1);
    box-shadow: none;
    color: rgba(255,255,255,0.4);
  }

  .typing-indicator {
    display: flex;
    gap: 4px;
    padding: 4px 8px;
  }
  .typing-indicator span {
    width: 8px;
    height: 8px;
    background-color: #9ca3af;
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
