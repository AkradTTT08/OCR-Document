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

  // Speech Recognition variables
  let isListening = false;
  let recognition;
  let originalInput = "";

  onMount(async () => {
    try {
      const resProjects = await fetch("http://127.0.0.1:5000/api/projects");
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
        // Optionally auto-send if you want, but better to let user review
      };
    }
  });

  afterUpdate(() => {
    scrollToBottom();
  });

  function selectProject(p) {
    selectedProjectStore.set(p);
    // Reset messages when project changes
    messages = [
      { role: 'assistant', content: `สวัสดีครับ! ผม Rainbow 🌈 ยินดีต้อนรับสู่โครงการ ${p.project_code} - ${p.name}\n\nคุณสามารถสอบถามข้อมูลใดๆ ที่เกี่ยวข้องกับโครงการนี้ได้เลยครับ` }
    ];
  }

  function scrollToBottom() {
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
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
      textareaElement.style.height = textareaElement.scrollHeight + 'px';
    }
  }

  $: {
    currentInput; // React to changes in currentInput
    if (textareaElement) {
      setTimeout(resizeTextarea, 0);
    }
  }

  async function sendMessage() {
    if (!currentInput.trim() || isLoading) return;
    
    const userMsg = currentInput.trim();
    currentInput = "";
    
    messages = [...messages, { role: 'user', content: userMsg }];
    isLoading = true;
    abortController = new AbortController();

    try {
      const projectId = selectedProjectObj.id || selectedProjectObj.project_id;
      
      const response = await fetch("http://127.0.0.1:5000/api/research/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortController.signal,
        body: JSON.stringify({
          project_id: projectId,
          message: userMsg,
          history: messages.slice(0, -1) // Send history excluding the current user message (or backend can handle)
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.error || `HTTP Error: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      // Add empty message placeholder for streaming
      messages = [...messages, { role: 'assistant', content: '' }];
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const textChunk = decoder.decode(value, { stream: true });
        messages[messages.length - 1].content += textChunk;
        messages = [...messages]; // trigger reactivity
        scrollToBottom();
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        toast("ยกเลิกการค้นหาข้อมูล", "info");
        // Remove the user's message so they can edit it
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
                <!-- Using basic pre-wrap for formatting, can be extended to render markdown -->
                <div class="msg-text" style="white-space: pre-wrap;">{msg.content}</div>
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
              </div>
            </div>
          </div>
        {/if}
      </div>

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
    max-width: 100%; /* Changed from 1400px to 100% */
    margin: 0; /* Removed auto margin */
    padding: 20px 32px; /* Increased side padding slightly so it doesn't touch the very edge */
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .top-nav {
    margin-bottom: 20px;
  }
  .btn-back {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-back:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }

  .header-text {
    text-align: center;
    margin-bottom: 30px;
  }
  .header-text h2 {
    font-size: 28px;
    font-weight: 700;
    margin: 0 0 8px 0;
    background: linear-gradient(135deg, #a78bfa, #3b82f6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header-text p {
    color: #9ca3af;
    margin: 0 0 16px 0;
    font-size: 15px;
  }
  
  .active-project-badge {
    display: inline-block;
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #93c5fd;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px;
  }
  .active-project-badge strong {
    color: white;
  }

  .chat-wrapper {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 500px;
    padding: 0;
    overflow: hidden;
  }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .chat-messages::-webkit-scrollbar {
    width: 6px;
  }
  .chat-messages::-webkit-scrollbar-track {
    background: transparent;
  }
  .chat-messages::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
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
  }

  .message-row.user .message-bubble {
    flex-direction: row-reverse;
  }

  .msg-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    /* 7-color dispersion effect */
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
  /* Optional: make the rainbow spin slowly */
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
    /* add a little drop shadow so the white icon pops against the rainbow */
    filter: drop-shadow(0px 1px 2px rgba(0,0,0,0.4));
  }
  .msg-icon.user {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
  }
  .msg-icon.user::before {
    display: none; /* no spin for user */
  }

  @keyframes spin {
    100% { transform: rotate(360deg); }
  }

  .msg-content {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 16px;
    border-radius: 12px;
    border-top-left-radius: 4px;
    color: #e2e8f0;
    font-size: 15px;
    line-height: 1.6;
  }

  .message-row.user .msg-content {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 12px;
    border-top-right-radius: 4px;
  }

  .chat-input-area {
    padding: 16px 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(0, 0, 0, 0.2);
    display: flex;
    gap: 12px;
    align-items: flex-end;
  }

  .chat-input-area textarea {
    flex: 1;
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: white;
    padding: 14px 16px;
    border-radius: 8px;
    font-family: inherit;
    font-size: 15px;
    resize: none;
    max-height: 150px;
    min-height: 48px;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    line-height: 1.5;
    overflow-y: auto;
  }
  .chat-input-area textarea:focus {
    border-color: rgba(59, 130, 246, 0.5);
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
  }

  .btn-mic {
    width: 48px;
    height: 48px;
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
    width: 22px;
    height: 22px;
  }
  .btn-mic:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.05);
    color: white;
  }
  .btn-mic.listening {
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.3);
    color: #ef4444;
    animation: pulse-mic 1.5s infinite;
  }
  
  @keyframes pulse-mic {
    0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
    100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
  }

  .btn-send {
    width: 48px;
    height: 48px;
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
    width: 20px;
    height: 20px;
    margin-right: 2px; /* optical center adjustment for send icon */
  }
  .btn-send:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
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
