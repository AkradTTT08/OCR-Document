<script>
  import { onMount, tick } from 'svelte';
  import { SvelteFlow, Controls, Background, MiniMap, addEdge } from '@xyflow/svelte';
  import '@xyflow/svelte/dist/style.css';
  import { toast } from './toastStore.js';
  import { selectedProjectStore } from './qaHistoryStore.js';
  import ProjectSelection from './ProjectSelection.svelte';
  import PipelineSelection from './PipelineSelection.svelte';
  
  import AgentNode from './nodes/AgentNode.svelte';
  import DebateLoopNode from './nodes/DebateLoopNode.svelte';
  import InputNode from './nodes/InputNode.svelte';
  import OutputNode from './nodes/OutputNode.svelte';

  const nodeTypes = {
    agent: AgentNode,
    debate: DebateLoopNode,
    input: InputNode,
    output: OutputNode
  };

  let projects = [];
  $: selectedProjectObj = $selectedProjectStore;

  let nodes = [];
  let edges = [];
  
  let workflowName = "Untitled Workflow";
  let currentStep = 'project'; // 'project', 'pipeline', 'canvas'
  let currentWorkflowId = null;
  
  // Chat logs from execution
  let chatLogs = [];
  let finalOutput = "";
  let isExecuting = false;
  let showChat = false;
  
  let chatScrollEl;

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

    if (selectedProjectObj) {
      currentStep = 'pipeline';
    }
  });

  function selectProject(p) {
    selectedProjectStore.set(p);
    currentStep = 'pipeline';
  }

  function resetProject() {
    selectedProjectStore.set(null);
    currentStep = 'project';
  }

  function backToPipeline() {
    currentStep = 'pipeline';
    currentWorkflowId = null;
  }

  function selectPipeline(pl) {
    currentWorkflowId = pl.id;
    workflowName = pl.name || "Untitled Workflow";
    try {
      nodes = typeof pl.nodes === 'string' ? JSON.parse(pl.nodes) : (pl.nodes || []);
      edges = typeof pl.edges === 'string' ? JSON.parse(pl.edges) : (pl.edges || []);
    } catch(e) {
      nodes = pl.nodes || [];
      edges = pl.edges || [];
    }
    currentStep = 'canvas';
  }

  function createNewPipeline() {
    currentWorkflowId = null;
    workflowName = "Untitled Workflow";
    const pId = selectedProjectObj?.id || selectedProjectObj?.project_id || '';
    nodes = [
      { id: 'start_1', type: 'input', position: { x: 60, y: 200 }, data: { text: "คำแนะนำสำหรับสร้างเอกสาร..." } },
      { id: 'debate_1', type: 'debate', position: { x: 380, y: 180 }, data: { generator: 'qa_doc_create', critic: 'qa_consult', max_loops: 2, project_id: pId } },
      { id: 'out_1', type: 'output', position: { x: 740, y: 200 }, data: { label: 'ผลลัพธ์สุดท้าย' } },
    ];
    edges = [
      { id: 'e1-2', source: 'start_1', target: 'debate_1' },
      { id: 'e2-3', source: 'debate_1', target: 'out_1' },
    ];
    currentStep = 'canvas';
  }

  function handleConnect(connection) {
    edges = addEdge(connection, edges);
  }

  // Scroll chat to bottom when new messages arrive
  $: if (chatLogs.length && chatScrollEl) {
    tick().then(() => {
      chatScrollEl.scrollTop = chatScrollEl.scrollHeight;
    });
  }

  // Avatar/color per speaker
  function getSpeakerStyle(speaker) {
    if (speaker.includes('System')) return { bg: '#374151', color: '#9ca3af', side: 'center' };
    if (speaker.includes('Input')) return { bg: '#064e3b', color: '#34d399', side: 'left' };
    if (speaker.includes('Output')) return { bg: '#1e3a5f', color: '#60a5fa', side: 'right' };
    if (speaker.includes('Creator')) return { bg: '#312e81', color: '#a78bfa', side: 'left' };
    if (speaker.includes('Consult')) return { bg: '#7c2d12', color: '#fb923c', side: 'right' };
    if (speaker.includes('Security')) return { bg: '#7f1d1d', color: '#f87171', side: 'left' };
    if (speaker.includes('Research')) return { bg: '#134e4a', color: '#2dd4bf', side: 'left' };
    return { bg: '#1f2937', color: '#e5e7eb', side: 'left' };
  }

  function getBubbleClass(log) {
    if (log.type === 'system') return 'bubble-system';
    if (log.type === 'pass') return 'bubble-pass';
    if (log.type === 'error') return 'bubble-error';
    if (log.type === 'info') return 'bubble-info';
    return 'bubble-speak';
  }

  const onDragStart = (event, nodeType) => {
    event.dataTransfer.setData('application/svelteflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  const onDrop = (event) => {
    event.preventDefault();
    const type = event.dataTransfer.getData('application/svelteflow');
    if (!type) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const newNode = {
      id: `node_${Date.now()}`,
      type,
      position: { x: event.clientX - bounds.left - 100, y: event.clientY - bounds.top - 40 },
      data: getDefaultDataForType(type)
    };
    nodes = [...nodes, newNode];
  };

  const onDragOver = (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  };
  
  function getDefaultDataForType(type) {
    const pId = selectedProjectObj?.id || selectedProjectObj?.project_id || '';
    if (type === 'agent') return { agent_type: 'qa_consult', project_id: pId };
    if (type === 'debate') return { generator: 'qa_doc_create', critic: 'qa_consult', max_loops: 2, project_id: pId };
    if (type === 'input') return { text: '' };
    if (type === 'output') return { label: 'Final Result' };
    return {};
  }

  async function executeWorkflow() {
    isExecuting = true;
    showChat = true;
    chatLogs = [{ speaker: '🔧 System', message: 'กำลังเตรียมรัน Pipeline...', type: 'system' }];
    finalOutput = "";

    const pId = selectedProjectObj?.id || selectedProjectObj?.project_id || '';
    
    try {
      const payload = {
        nodes: nodes.map(n => ({
          id: n.id,
          type: n.type,
          data: {
            ...n.data,
            project_id: n.data.project_id || pId
          }
        })),
        edges: edges.map(e => ({ source: e.source, target: e.target }))
      };
      
      const res = await fetch('http://127.0.0.1:5000/api/workflow/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Execution failed');
      
      chatLogs = data.result.chat_logs || [];
      finalOutput = data.result.final_output || "";
    } catch(e) {
      chatLogs = [...chatLogs, { speaker: '🔧 System', message: `❌ ERROR: ${e.message}`, type: 'error' }];
    } finally {
      isExecuting = false;
    }
  }
  
  async function saveWorkflow() {
    const pId = selectedProjectObj?.id || selectedProjectObj?.project_id || '';
    try {
      const payload = {
        name: workflowName,
        project_id: pId,
        nodes: nodes.map(n => ({ id: n.id, type: n.type, data: n.data, position: n.position })),
        edges: edges.map(e => ({ source: e.source, target: e.target }))
      };
      let url = 'http://127.0.0.1:5000/api/workflows';
      let method = 'POST';
      if (currentWorkflowId) {
        url = `http://127.0.0.1:5000/api/workflows/${currentWorkflowId}`;
        method = 'PUT';
      }
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Save failed');
      const data = await res.json();
      if (data.id) {
        currentWorkflowId = data.id;
      }
      toast('Workflow saved successfully!', 'success');
    } catch(e) {
      toast(`บันทึกไม่สำเร็จ: ${e.message}`, 'error');
    }
  }
</script>

<div class="workflow-outer-wrapper">
  {#if currentStep === 'project' || !selectedProjectObj}
    <div class="project-selection-wrapper">
      <ProjectSelection 
        {projects} 
        on:select={(e) => selectProject(e.detail)} 
      />
    </div>
  {:else if currentStep === 'pipeline'}
    <div class="top-nav">
      <button class="btn-back" on:click={resetProject}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        เปลี่ยนโครงการ
      </button>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code || selectedProjectObj.name}</strong>
      </div>
    </div>
    <div class="pipeline-selection-wrapper" style="padding: 40px; max-width: 1200px; margin: 0 auto; width: 100%;">
      <PipelineSelection 
        projectId={selectedProjectObj?.id || selectedProjectObj?.project_id}
        on:select={(e) => selectPipeline(e.detail)}
        on:create={createNewPipeline}
      />
    </div>
  {:else if currentStep === 'canvas'}
    <div class="top-nav">
      <button class="btn-back" on:click={backToPipeline}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        กลับไปเลือก Pipeline
      </button>
      <div class="active-project-badge">
        โครงการปัจจุบัน: <strong>{selectedProjectObj.project_code || selectedProjectObj.name}</strong>
      </div>
    </div>

    <div class="workflow-container">
      <!-- Left Node Palette -->
      <aside class="node-palette">
        <div class="palette-header">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
          AI Workflow Builder
        </div>

        <div class="palette-section-title">ลาก Node ลงบน Canvas</div>
        
        <div class="palette-nodes">
          <div class="palette-node type-input" draggable="true" on:dragstart={(e) => onDragStart(e, 'input')}>
            <span class="node-icon">📥</span>
            <div>
              <div class="node-label">Input</div>
              <div class="node-desc">จุดเริ่มต้น / ข้อมูลนำเข้า</div>
            </div>
          </div>
          <div class="palette-node type-agent" draggable="true" on:dragstart={(e) => onDragStart(e, 'agent')}>
            <span class="node-icon">🤖</span>
            <div>
              <div class="node-label">AI Agent</div>
              <div class="node-desc">Agent เดี่ยว ทำงาน 1 ครั้ง</div>
            </div>
          </div>
          <div class="palette-node type-debate" draggable="true" on:dragstart={(e) => onDragStart(e, 'debate')}>
            <span class="node-icon">🔄</span>
            <div>
              <div class="node-label">Debate Loop</div>
              <div class="node-desc">2 AI คุยกันวนจนสมบูรณ์</div>
            </div>
          </div>
          <div class="palette-node type-output" draggable="true" on:dragstart={(e) => onDragStart(e, 'output')}>
            <span class="node-icon">📤</span>
            <div>
              <div class="node-label">Output</div>
              <div class="node-desc">ผลลัพธ์สุดท้าย</div>
            </div>
          </div>
        </div>

        <div class="palette-controls">
          <input type="text" bind:value={workflowName} class="wf-name-input" placeholder="ชื่อ Workflow" />
          <button class="btn btn-save" on:click={saveWorkflow}>💾 บันทึก</button>
          <button class="btn btn-run" on:click={executeWorkflow} disabled={isExecuting}>
            {#if isExecuting}
              <span class="spinner"></span> กำลังรัน...
            {:else}
              🚀 รัน Pipeline
            {/if}
          </button>
        </div>
      </aside>

      <!-- Canvas -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="canvas-area" on:drop={onDrop} on:dragover={onDragOver}>
        <SvelteFlow 
          bind:nodes 
          bind:edges 
          {nodeTypes} 
          fitView 
          onconnect={handleConnect}
          on:connect={(e) => handleConnect(e.detail)}
        >
          <Background gap={20} size={1} color="#1f2937" />
          <Controls />
          <MiniMap nodeColor="#6366f1" maskColor="rgba(0,0,0,0.6)" />
        </SvelteFlow>
      </div>

      <!-- Chat Log Panel -->
      {#if showChat}
        <div class="chat-panel">
          <div class="chat-header">
            <div class="chat-title">
              <span>💬 AI Agent Conversation</span>
              {#if isExecuting}<span class="live-badge">● LIVE</span>{/if}
            </div>
            <button class="close-btn" on:click={() => showChat = false}>✕</button>
          </div>

          <div class="chat-messages" bind:this={chatScrollEl}>
            {#each chatLogs as log}
              {@const style = getSpeakerStyle(log.speaker)}
              {@const bubbleClass = getBubbleClass(log)}
              
              {#if log.type === 'system'}
                <div class="system-msg">{log.message}</div>
              {:else}
                <div class="chat-row {style.side === 'right' ? 'row-right' : 'row-left'}">
                  <!-- Avatar -->
                  <div class="avatar" style="background: {style.bg}; color: {style.color}">
                    {log.speaker.slice(0, 2)}
                  </div>
                  <div class="bubble-wrap {style.side === 'right' ? 'wrap-right' : 'wrap-left'}">
                    <div class="bubble-name" style="color: {style.color}">{log.speaker}</div>
                    <div class="bubble {bubbleClass}" style="border-color: {style.color}33">
                      {log.message}
                    </div>
                  </div>
                </div>
              {/if}
            {/each}

            {#if isExecuting}
              <div class="typing-indicator">
                <span></span><span></span><span></span>
                <span class="typing-text">กำลังประมวลผล...</span>
              </div>
            {/if}
          </div>

          {#if finalOutput && !isExecuting}
            <div class="final-output-bar">
              <span class="final-label">🎯 ผลลัพธ์พร้อมแล้ว</span>
              <button class="copy-btn" on:click={() => navigator.clipboard.writeText(finalOutput)}>📋 Copy</button>
            </div>
          {/if}
        </div>
      {/if}

      <!-- Toggle chat button -->
      <button class="chat-toggle-btn" on:click={() => showChat = !showChat}>
        💬
        {#if chatLogs.length > 0}
          <span class="badge">{chatLogs.length}</span>
        {/if}
      </button>
    </div>
  {/if}
</div>

<style>
  :global(.svelte-flow__node) {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
  }
  .workflow-outer-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 16px;
    background: rgba(15, 20, 32, 0.8);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .btn-back {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    transition: all 0.2s;
  }
  .btn-back:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-main);
  }

  .active-project-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #a5b4fc;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
  }

  .project-selection-wrapper {
    padding: 32px 40px;
    width: 100%;
    height: 100%;
    overflow-y: auto;
    box-sizing: border-box;
  }

  :global(.svelte-flow__background) { background: #0c0e16 !important; }
  :global(.svelte-flow__controls button) {
    background: #1f2937 !important;
    border-color: #374151 !important;
    color: #e5e7eb !important;
  }
  :global(.svelte-flow__minimap) {
    background: #0c0e16 !important;
    border: 1px solid #374151 !important;
    border-radius: 8px !important;
  }

  .workflow-container {
    display: flex;
    flex: 1;
    width: 100%;
    position: relative;
    overflow: hidden;
    background: #0c0e16;
  }

  /* ── Left Palette ── */
  .node-palette {
    width: 220px;
    flex-shrink: 0;
    background: rgba(17, 24, 39, 0.95);
    border-right: 1px solid #1f2937;
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 16px 12px;
    z-index: 5;
  }

  .palette-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
    font-size: 13px;
    color: #a78bfa;
    letter-spacing: 0.5px;
  }

  .palette-section-title {
    font-size: 10px;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
  }

  .palette-nodes { display: flex; flex-direction: column; gap: 8px; }

  .palette-node {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #374151;
    cursor: grab;
    transition: all 0.2s;
    background: #111827;
  }
  .palette-node:hover { border-color: #6366f1; transform: translateX(2px); }
  .palette-node:active { cursor: grabbing; }
  .type-input  { border-left: 3px solid #34d399; }
  .type-agent  { border-left: 3px solid #818cf8; }
  .type-debate { border-left: 3px solid #fbbf24; }
  .type-output { border-left: 3px solid #60a5fa; }

  .node-icon { font-size: 18px; }
  .node-label { font-size: 12px; font-weight: 600; color: #f9fafb; }
  .node-desc  { font-size: 10px; color: #9ca3af; margin-top: 1px; }

  .palette-controls {
    margin-top: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .wf-name-input {
    width: 100%;
    padding: 8px 10px;
    background: #0f1117;
    border: 1px solid #374151;
    border-radius: 6px;
    color: #f9fafb;
    font-size: 12px;
  }
  .wf-name-input:focus { outline: none; border-color: #6366f1; }

  .btn {
    padding: 9px 12px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-weight: 600;
    font-size: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .btn-save { background: #1f2937; color: #9ca3af; border: 1px solid #374151; }
  .btn-save:hover { background: #374151; color: #f9fafb; }
  .btn-run { background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; }
  .btn-run:hover:not(:disabled) { filter: brightness(1.1); transform: translateY(-1px); }
  .btn-run:disabled { opacity: 0.5; cursor: not-allowed; }

  /* ── Canvas ── */
  .canvas-area {
    flex: 1;
    height: 100%;
    position: relative;
  }

  /* ── Chat Panel ── */
  .chat-panel {
    position: absolute;
    right: 16px;
    top: 16px;
    bottom: 16px;
    width: 400px;
    background: rgba(10, 12, 20, 0.97);
    backdrop-filter: blur(20px);
    border: 1px solid #1f2937;
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    z-index: 20;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(99, 102, 241, 0.1);
    overflow: hidden;
  }

  .chat-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
    border-bottom: 1px solid #1f2937;
    background: rgba(15, 20, 32, 0.8);
  }

  .chat-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    font-weight: 700;
    color: #e5e7eb;
  }

  .live-badge {
    font-size: 10px;
    font-weight: 700;
    color: #4ade80;
    animation: pulse-text 1.2s ease-in-out infinite;
  }
  @keyframes pulse-text { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

  .close-btn {
    background: none;
    border: none;
    color: #6b7280;
    cursor: pointer;
    font-size: 14px;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.2s;
  }
  .close-btn:hover { background: #1f2937; color: #f9fafb; }

  .chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    scroll-behavior: smooth;
  }
  .chat-messages::-webkit-scrollbar { width: 4px; }
  .chat-messages::-webkit-scrollbar-track { background: transparent; }
  .chat-messages::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }

  /* System message - centered divider */
  .system-msg {
    text-align: center;
    font-size: 11px;
    color: #6b7280;
    padding: 4px 12px;
    border-radius: 100px;
    background: #111827;
    border: 1px solid #1f2937;
    align-self: center;
    max-width: 85%;
    font-style: italic;
  }

  /* Chat bubble rows */
  .chat-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    max-width: 95%;
  }
  .row-left { flex-direction: row; }
  .row-right { flex-direction: row-reverse; align-self: flex-end; }

  .avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
    text-transform: uppercase;
    border: 1px solid rgba(255,255,255,0.1);
  }

  .bubble-wrap { display: flex; flex-direction: column; gap: 3px; max-width: 300px; }
  .wrap-right { align-items: flex-end; }
  .bubble-name { font-size: 10px; font-weight: 700; padding: 0 4px; }

  .bubble {
    padding: 10px 12px;
    border-radius: 12px;
    font-size: 12px;
    line-height: 1.6;
    color: #e5e7eb;
    border: 1px solid;
    white-space: pre-wrap;
    word-break: break-word;
    background: #111827;
    max-width: 100%;
  }

  .bubble-speak { background: #141826; }
  .bubble-info { background: #0d1117; color: #9ca3af; font-style: italic; border-style: dashed; opacity: 0.8; }
  .bubble-pass { background: #052e16; border-color: #16a34a !important; color: #4ade80; }
  .bubble-error { background: #1c0e0e; border-color: #b91c1c !important; color: #fca5a5; }

  /* Typing indicator */
  .typing-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px 12px;
    align-self: flex-start;
  }
  .typing-indicator span:not(.typing-text) {
    width: 6px; height: 6px;
    background: #6366f1;
    border-radius: 50%;
    animation: typing-bounce 1.2s ease-in-out infinite;
  }
  .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
  .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
  .typing-text { font-size: 11px; color: #6b7280; margin-left: 4px; }
  @keyframes typing-bounce { 0%,60%,100% { transform: translateY(0); } 30% { transform: translateY(-6px); } }

  /* Final output bar */
  .final-output-bar {
    padding: 10px 14px;
    border-top: 1px solid #1f2937;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #052e16;
  }
  .final-label { font-size: 12px; color: #4ade80; font-weight: 600; }
  .copy-btn {
    background: #065f46;
    border: none;
    color: #4ade80;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
  }
  .copy-btn:hover { background: #047857; }

  /* Floating chat toggle */
  .chat-toggle-btn {
    position: absolute;
    bottom: 24px;
    right: 24px;
    z-index: 10;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border: none;
    color: white;
    font-size: 20px;
    cursor: pointer;
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.2s;
    position: absolute;
  }
  .chat-toggle-btn:hover { transform: scale(1.1); }
  
  .badge {
    position: absolute;
    top: -4px;
    right: -4px;
    background: #ef4444;
    color: white;
    font-size: 9px;
    font-weight: 700;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .spinner {
    width: 12px; height: 12px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
    display: inline-block;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
