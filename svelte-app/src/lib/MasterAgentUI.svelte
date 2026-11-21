<script>
  import { createEventDispatcher, onMount, onDestroy, afterUpdate } from "svelte";
  import { fade, slide } from "svelte/transition";
  import { toast } from "./toastStore.js";

  const dispatch = createEventDispatcher();

  // ── 6 Specialist QA Agents (Spectrum Channels) ──
  const SPECTRUM_AGENTS = [
    {
      id: "diagram",
      name: "QA Analysis Diagram",
      shortName: "Analysis Diagram",
      view: "qa_analysis_diagram",
      wavelength: "λ 410nm • VIOLET",
      color: "#a855f7",
      colorLight: "#e9d5ff",
      colorSecondary: "#ec4899",
      positionClass: "pos-top-left",
      beamStart: { x: 335, y: 165 },
      beamEnd: { x: 215, y: 88 },
      relayFromCore: { x: 335, y: 165 },
      roleDesc: "วิเคราะห์ Flow, Sequence & Architecture Diagram จาก Requirement",
      promptTemplate: "ช่วยวิเคราะห์และออกแบบ Sequence Diagram และ System Flow สำหรับระบบ Authentication & Token Refresh",
      keywords: ["diagram", "flow", "sequence", "architecture", "flowchart", "แผนผัง", "ไดอะแกรม", "โครงสร้าง"]
    },
    {
      id: "doc_creation",
      name: "QA Document Creation",
      shortName: "Doc Creation",
      view: "qa_doc_creation",
      wavelength: "λ 620nm • ROSE-CRIMSON",
      color: "#ec4899",
      colorLight: "#fbcfe8",
      colorSecondary: "#f43f5e",
      positionClass: "pos-mid-left",
      beamStart: { x: 500, y: 245 },
      beamEnd: { x: 215, y: 250 },
      relayFromCore: null,
      roleDesc: "สร้างและปรับปรุงเอกสาร SRS, Test Case, UAT & Exit Criteria",
      promptTemplate: "ช่วยร่างเอกสาร SRS และตาราง Test Case มาตรฐานสำหรับฟีเจอร์ชำระเงินผ่าน QR PromptPay",
      keywords: ["document", "doc", "create", "draft", "srs", "uat", "สร้างเอกสาร", "ร่างเอกสาร", "เขียนเอกสาร", "ปรับปรุงเอกสาร"]
    },
    {
      id: "consult",
      name: "QA Consult",
      shortName: "QA Consult",
      view: "qa_consult",
      wavelength: "λ 580nm • AMBER-GOLD",
      color: "#f59e0b",
      colorLight: "#fde68a",
      colorSecondary: "#eab308",
      positionClass: "pos-bottom-left",
      beamStart: { x: 390, y: 295 },
      beamEnd: { x: 215, y: 412 },
      relayFromCore: { x: 390, y: 295 },
      roleDesc: "ตรวจสอบเอกสารเทียบ Knowledge Base & ประเมิน Exit Criteria Gate",
      promptTemplate: "ช่วยตรวจสอบความครบถ้วนของ Requirement เทียบกับเกณฑ์ Exit Criteria Review Gate และหา Gap Analysis",
      keywords: ["consult", "audit", "exit criteria", "review", "gap", "knowledge base", "kb", "ตรวจเอกสาร", "ตรวจสอบ", "เกณฑ์"]
    },
    {
      id: "automation",
      name: "QA Test Automation",
      shortName: "Test Automation",
      view: "qa_automate",
      wavelength: "λ 520nm • EMERALD-MINT",
      color: "#10b981",
      colorLight: "#a7f3d0",
      colorSecondary: "#06b6d4",
      positionClass: "pos-mid-right",
      beamStart: { x: 500, y: 255 },
      beamEnd: { x: 785, y: 250 },
      relayFromCore: null,
      roleDesc: "สร้างและรัน Automated Test Script (Playwright / Robot / API)",
      promptTemplate: "ช่วยเขียน Automated Test Script ด้วย Playwright สำหรับทดสอบ Login, Session Timeout และ Error Handling",
      keywords: ["automate", "automation", "playwright", "robot", "selenium", "cypress", "test case", "test script", "ออโตเมท", "สคริปต์", "ทดสอบอัตโนมัติ"]
    },
    {
      id: "performance",
      name: "QA Performance",
      shortName: "QA Performance",
      view: "qa_performance",
      wavelength: "λ 480nm • CYAN-SKY",
      color: "#06b6d4",
      colorLight: "#bae6fd",
      colorSecondary: "#3b82f6",
      positionClass: "pos-top-right",
      beamStart: { x: 665, y: 165 },
      beamEnd: { x: 785, y: 88 },
      relayFromCore: { x: 665, y: 165 },
      roleDesc: "วิเคราะห์ Load Testing, Stress Test, SLA & สร้างสคริปต์ k6",
      promptTemplate: "ช่วยวางแผนทดสอบ Load Testing 1,000 Concurrent Users ด้วย k6 และกำหนดเกณฑ์ SLA P95 < 400ms",
      keywords: ["performance", "load", "stress", "spike", "k6", "jmeter", "sla", "latency", "throughput", "โหลด", "ความเร็ว", "ประสิทธิภาพ"]
    },
    {
      id: "security",
      name: "QA Security & Research",
      shortName: "Security & Research",
      view: "qa_security",
      wavelength: "λ 450nm • ELECTRIC INDIGO",
      color: "#6366f1",
      colorLight: "#c7d2fe",
      colorSecondary: "#a855f7",
      positionClass: "pos-bottom-right",
      beamStart: { x: 500, y: 265 },
      beamEnd: { x: 785, y: 412 },
      relayFromCore: null,
      roleDesc: "ตรวจสอบช่องโหว่ OWASP Top 10, Pen-Test & Deep QA Research",
      promptTemplate: "ช่วยตรวจสอบช่องโหว่ Security ตามมาตรฐาน OWASP Top 10 (SQLi, XSS, Broken Auth) และแนวทางป้องกัน",
      keywords: ["security", "owasp", "vulnerability", "pentest", "sql", "xss", "jwt", "auth", "research", "ความปลอดภัย", "ช่องโหว่", "วิจัย"]
    }
  ];

  // Symmetric 3-left / 3-right columns for collision-free Prism Arena grid
  const LEFT_AGENTS = ["diagram", "doc_creation", "consult"]
    .map(id => SPECTRUM_AGENTS.find(a => a.id === id))
    .filter(Boolean);
  const RIGHT_AGENTS = ["performance", "automation", "security"]
    .map(id => SPECTRUM_AGENTS.find(a => a.id === id))
    .filter(Boolean);

  // Input Conduit Types (White Beam Source)
  const INPUT_SOURCES = [
    { id: "requirement", label: "Requirement", icon: "📄", desc: "เอกสารข้อกำหนดระบบ / SRS" },
    { id: "code_commit", label: "Code Commit", icon: "💻", desc: "ชุดแก้ไขโค้ด / Pull Request" },
    { id: "user_story", label: "User Story", icon: "🎯", desc: "Acceptance Criteria / Sprint Task" }
  ];

  let selectedInputSource = "requirement";
  let routingMode = "auto"; // 'auto' | 'manual'
  let manualSelectedAgents = ["diagram", "doc_creation", "consult", "automation", "performance", "security"];

  // Active Beam & Refraction Animation State
  let activeAgentIds = ["diagram", "doc_creation", "consult", "automation", "performance", "security"];
  let isWhiteCommandFiring = false;
  let isSpectrumRefracting = false;
  let activeCommandSummary = "PRISM STANDBY • READY FOR WHITE BEAM INPUT";
  let totalDispatchedCount = 6;
  let pulseTimer = null;

  const INITIAL_WELCOME = {
    role: "assistant",
    content: "ยินดีต้อนรับสู่ **Spectra QA — Prism Core Orchestration** 💎\n\nศูนย์กลางปริซึมอัจฉริยะพร้อมรับ Input (**Requirement / Code Commit / User Story**) เป็น **ลำแสงสีขาวบริสุทธิ์ (White Command Beam)** และหักเหกระจายออกเป็น **สเปกตรัมแสง 6 เฉดสี** ส่งตรงไปยัง Agent ผู้เชี่ยวชาญทั้ง 6 สายงานแบบ Real-time:\n- 🟣 **QA Analysis Diagram**: วิเคราะห์ Flow & Sequence Diagram\n- 🩷 **QA Document Creation**: สร้างเอกสาร SRS, Test Case & UAT\n- 🟠 **QA Consult**: ตรวจเอกสารเทียบ Knowledge Base & Exit Gate\n- 🟢 **QA Test Automation**: สร้าง Automated Script (Playwright / API)\n- 🔵 **QA Performance**: วางแผน Load Test & k6 SLA\n- 🔷 **QA Security & Research**: ตรวจช่องโหว่ OWASP Top 10 & Deep Research\n\nพิมพ์คำสั่งทางช่อง Prompt ด้านขวา หรือคลิกที่สถานี Agent บนหน้าจอเพื่อยิงลำแสงคำสั่งได้ทันทีครับ!",
    timestamp: getFormattedTime(),
    agents: ["diagram", "doc_creation", "consult", "automation", "performance", "security"],
    inputSource: "requirement"
  };

  let messages = [INITIAL_WELCOME];
  let currentInput = "";
  let isLoading = false;
  let chatContainer;
  let copiedIndex = null;
  let prevMessageCount = messages.length;
  let prevLoadingState = false;

  function getFormattedTime() {
    const now = new Date();
    return now.toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" });
  }

  function isNearBottom() {
    if (!chatContainer) return true;
    return chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 120;
  }

  afterUpdate(() => {
    const messageAdded = messages.length > prevMessageCount;
    const loadingStarted = isLoading && !prevLoadingState;
    if (messageAdded) {
      scrollToBottom();
    } else if (loadingStarted && isNearBottom()) {
      scrollToBottom();
    }
    prevMessageCount = messages.length;
    prevLoadingState = isLoading;
  });

  function scrollToBottom() {
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    }
  }

  // Detect which Specialist Agents should be activated by a prompt text
  function detectAgentsFromPrompt(text) {
    if (routingMode === "manual" && manualSelectedAgents.length > 0) {
      return [...manualSelectedAgents];
    }
    const lower = String(text || "").toLowerCase();
    if (!lower.trim()) {
      return SPECTRUM_AGENTS.map(a => a.id);
    }
    if (
      lower.includes("ทั้งหมด") ||
      lower.includes("ทุก agent") ||
      lower.includes("all agent") ||
      lower.includes("full spectrum") ||
      lower.includes("ครบวงจร") ||
      lower.includes("end-to-end")
    ) {
      return SPECTRUM_AGENTS.map(a => a.id);
    }

    const matched = [];
    for (const agent of SPECTRUM_AGENTS) {
      if (agent.keywords.some(kw => lower.includes(kw))) {
        matched.push(agent.id);
      }
    }
    return matched.length > 0 ? matched : SPECTRUM_AGENTS.map(a => a.id);
  }

  // Live preview of which agents will be triggered as the user types
  $: previewTargetAgents = currentInput.trim()
    ? detectAgentsFromPrompt(currentInput)
    : routingMode === "manual"
      ? manualSelectedAgents
      : activeAgentIds;

  function triggerPrismRefractionSequence(targetIds, labelText = "DISPATCHING WHITE COMMAND BEAM", durationMs = 4200) {
    if (pulseTimer) clearTimeout(pulseTimer);
    activeAgentIds = targetIds && targetIds.length > 0 ? [...targetIds] : SPECTRUM_AGENTS.map(a => a.id);
    activeCommandSummary = labelText;
    isWhiteCommandFiring = true;
    isSpectrumRefracting = true;
    totalDispatchedCount += activeAgentIds.length;

    if (!isLoading && durationMs > 0) {
      pulseTimer = setTimeout(() => {
        if (!isLoading) {
          isWhiteCommandFiring = false;
        }
      }, durationMs);
    }
  }

  function simulateFullSpectrumPulse() {
    const allIds = SPECTRUM_AGENTS.map(a => a.id);
    routingMode = "auto";
    triggerPrismRefractionSequence(
      allIds,
      `FULL 6-SPECTRUM REFRACTION • [${selectedInputSource.toUpperCase()}]`,
      4500
    );
    toast("ยิงลำแสงสีขาวเข้าสู่ Prism Core และหักเหออกเป็น 6 สเปกตรัมครบทุก Agent แล้ว", "info");
  }

  function handleStationClick(agent) {
    if (routingMode === "manual") {
      if (manualSelectedAgents.includes(agent.id)) {
        if (manualSelectedAgents.length > 1) {
          manualSelectedAgents = manualSelectedAgents.filter(id => id !== agent.id);
        }
      } else {
        manualSelectedAgents = [...manualSelectedAgents, agent.id];
      }
      triggerPrismRefractionSequence(
        manualSelectedAgents,
        `TARGETING ${manualSelectedAgents.length} AGENT(S) • WHITE COMMAND LOCKED`,
        3200
      );
    } else {
      triggerPrismRefractionSequence(
        [agent.id],
        `WHITE COMMAND → ${agent.name.toUpperCase()} (${agent.wavelength})`,
        3600
      );
    }
  }

  function dispatchAgentPrompt(agent) {
    routingMode = "auto";
    currentInput = agent.promptTemplate;
    sendMessage([agent.id]);
  }

  function navigateToAgentModule(agent) {
    dispatch("navigate", { view: agent.view });
  }

  const QUICK_PROMPTS = [
    {
      icon: "🌈",
      title: "Full 6-Spectrum Audit",
      agents: ["diagram", "doc_creation", "consult", "automation", "performance", "security"],
      text: "วิเคราะห์ User Story ระบบโอนเงินแบบครบวงจรทั้ง 6 สายงาน (Diagram, SRS, Consult Gate, Playwright, k6 Load Test และ OWASP Security)"
    },
    {
      icon: "🛡️",
      title: "Security & OWASP",
      agents: ["security"],
      text: "ช่วยตรวจสอบช่องโหว่ Security และ OWASP Top 10 ในโค้ด API Authentication"
    },
    {
      icon: "⚡",
      title: "Performance & k6",
      agents: ["performance"],
      text: "ช่วยวางแผนทดสอบ Load Testing & SLA ด้วย k6 สำหรับ API รองรับ 1,500 VUs"
    },
    {
      icon: "📋",
      title: "SRS + Test Automation",
      agents: ["doc_creation", "consult", "automation"],
      text: "ช่วยสร้าง QA Test Cases, Exit Criteria และ Playwright Script สำหรับฟีเจอร์ Login 2FA"
    }
  ];

  function useQuickPrompt(qp) {
    currentInput = qp.text;
    sendMessage(qp.agents);
  }

  function clearChat() {
    messages = [{ ...INITIAL_WELCOME, timestamp: getFormattedTime() }];
    activeAgentIds = SPECTRUM_AGENTS.map(a => a.id);
    isWhiteCommandFiring = false;
    activeCommandSummary = "PRISM STANDBY • READY FOR WHITE BEAM INPUT";
    toast("ล้างประวัติคอนโซลและรีเซ็ตสถานะ Prism Core เรียบร้อยแล้ว", "info");
  }

  async function copyToClipboard(text, index) {
    try {
      await navigator.clipboard.writeText(text);
      copiedIndex = index;
      toast("คัดลอกข้อความลง Clipboard แล้ว", "success");
      setTimeout(() => {
        copiedIndex = null;
      }, 2000);
    } catch (err) {
      toast("ไม่สามารถคัดลอกข้อความได้", "error");
    }
  }

  async function sendMessage(explicitAgentIds = null) {
    if (!currentInput.trim() || isLoading) return;

    const userMsgText = currentInput.trim();
    const targetIds =
      explicitAgentIds && explicitAgentIds.length > 0
        ? explicitAgentIds
        : detectAgentsFromPrompt(userMsgText);

    const srcObj = INPUT_SOURCES.find(s => s.id === selectedInputSource) || INPUT_SOURCES[0];
    const targetNames = SPECTRUM_AGENTS.filter(a => targetIds.includes(a.id)).map(a => a.name);

    // 1. Ignite White Command Beam + Refract to Target Spectrum Agents
    if (pulseTimer) clearTimeout(pulseTimer);
    activeAgentIds = [...targetIds];
    isWhiteCommandFiring = true;
    isSpectrumRefracting = true;
    activeCommandSummary = `WHITE BEAM [${srcObj.label.toUpperCase()}]: "${userMsgText.slice(0, 46)}${userMsgText.length > 46 ? "..." : ""}"`;
    totalDispatchedCount += targetIds.length;

    const userMsg = {
      role: "user",
      content: userMsgText,
      timestamp: getFormattedTime(),
      inputSource: selectedInputSource,
      agents: [...targetIds]
    };
    messages = [...messages, userMsg];
    currentInput = "";
    isLoading = true;

    try {
      const apiMessages = messages.map((m, idx) => {
        if (idx === messages.length - 1 && m.role === "user") {
          return {
            role: "user",
            content: `[Input Source: ${srcObj.label}] [Target QA Agents: ${targetNames.join(", ")}]\n${m.content}`
          };
        }
        return { role: m.role, content: m.content };
      });

      const response = await fetch("/api/qa/master", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: apiMessages })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to communicate with Prism Core Orchestrator");
      }

      messages = [
        ...messages,
        {
          role: "assistant",
          content: data.response || "ประมวลผลเสร็จสิ้น",
          timestamp: getFormattedTime(),
          agents: [...targetIds],
          inputSource: selectedInputSource
        }
      ];
    } catch (err) {
      toast(`Error: ${err.message}`, "error");
      messages = [
        ...messages,
        {
          role: "assistant",
          content: `เกิดข้อผิดพลาดในการเชื่อมต่อ: ${err.message}`,
          timestamp: getFormattedTime(),
          agents: [...targetIds],
          inputSource: selectedInputSource
        }
      ];
    } finally {
      isLoading = false;
      pulseTimer = setTimeout(() => {
        isWhiteCommandFiring = false;
      }, 2800);
    }
  }

  function handleKeydown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  function getAgentById(id) {
    return SPECTRUM_AGENTS.find(a => a.id === id);
  }

  // Lightweight Markdown Helper for Rich AI Responses
  function renderFormattedText(text) {
    if (!text) return "";
    let escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    escaped = escaped.replace(/```([\s\S]*?)```/g, (match, p1) => {
      return `<div class="code-block-wrapper"><div class="code-header"><span>SPECTRUM OUTPUT CODE</span></div><pre><code>${p1.trim()}</code></pre></div>`;
    });

    escaped = escaped.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    escaped = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    escaped = escaped.replace(/^[\s]*[-*]\s+(.*)$/gm, '<li class="list-item">$1</li>');
    escaped = escaped.replace(/(<li class="list-item">.*<\/li>)/s, '<ul class="custom-list">$1</ul>');
    escaped = escaped.replace(/\n\n/g, "<br/><br/>");
    escaped = escaped.replace(/\n/g, "<br/>");

    return escaped;
  }

  onMount(() => {
    triggerPrismRefractionSequence(
      SPECTRUM_AGENTS.map(a => a.id),
      "PRISM CORE INITIALIZED • 6 SPECTRUM CHANNELS SYNCHRONIZED",
      3000
    );
  });

  onDestroy(() => {
    if (pulseTimer) clearTimeout(pulseTimer);
  });
</script>

<div class="spectra-orchestration-shell" in:fade={{ duration: 250 }}>
  <!-- ── TOP COMMAND HEADER BAR ── -->
  <header class="orchestration-top-bar">
    <div class="top-bar-brand">
      <div class="prism-emblem" class:core-blazing={isWhiteCommandFiring || isLoading}>
        <svg viewBox="0 0 32 32" width="24" height="24" fill="none">
          <polygon points="16,3 29,10 29,22 16,29 3,22 3,10" stroke="currentColor" stroke-width="1.8" fill="rgba(255,255,255,0.08)" />
          <polygon points="16,7 25,19 7,19" stroke="#ffffff" stroke-width="1.8" fill="rgba(255,255,255,0.22)" />
          <line x1="16" y1="3" x2="16" y2="7" stroke="#ffffff" stroke-width="1.6" />
        </svg>
      </div>
      <div class="brand-titles">
        <div class="brand-title-row">
          <h2>SPECTRA QA — ORCHESTRATION</h2>
          <span class="prism-status-pill" class:firing={isWhiteCommandFiring || isLoading}>
            <span class="status-dot"></span>
            {isLoading ? "REFRACTING WHITE COMMAND..." : isWhiteCommandFiring ? "WHITE BEAM ACTIVE" : "PRISM CORE READY"}
          </span>
        </div>
        <p class="brand-sub">
          Prism Core Orchestrator (ศูนย์กลางปริซึม): รับ Input เป็นลำแสงสีขาวบริสุทธิ์ หักเหกระจายออกเป็นสเปกตรัม 6 เฉดสีไปยัง Agent ผู้เชี่ยวชาญแบบ Real-time
        </p>
      </div>
    </div>

    <div class="top-bar-controls">
      <div class="input-conduit-selector" role="group" aria-label="เลือกประเภท Input ลำแสงสีขาว">
        <span class="conduit-label">Input Beam:</span>
        {#each INPUT_SOURCES as src}
          <button
            type="button"
            class="conduit-pill"
            class:active={selectedInputSource === src.id}
            on:click={() => {
              selectedInputSource = src.id;
              triggerPrismRefractionSequence(
                previewTargetAgents,
                `INPUT CONDUIT SWITCHED → [${src.label.toUpperCase()}] WHITE BEAM`,
                2400
              );
            }}
            title={src.desc}
          >
            <span>{src.icon}</span>
            <span>{src.label}</span>
          </button>
        {/each}
      </div>

      <button type="button" class="btn-simulate-prism" on:click={simulateFullSpectrumPulse} title="ทดสอบยิงลำแสงสีขาวและหักเห 6 สเปกตรัม">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
        </svg>
        <span>ยิงลำแสง 6 สเปกตรัม</span>
      </button>
    </div>
  </header>

  <!-- ── MAIN 2-COLUMN WORKSPACE: PRISM STAGE (LEFT) + COMPACT PROMPT DOCK (RIGHT) ── -->
  <div class="orchestration-deck-grid">
    <!-- ═══════════════════════════════════════════════════════════════════
         LEFT / CENTER STAGE: HOLOGRAPHIC PRISM CORE & 6 AGENT STATIONS
         ═══════════════════════════════════════════════════════════════════ -->
    <section class="prism-stage-card" aria-label="Prism Core Orchestration Visual Stage">
      <!-- Top Dual Angled Holographic Telemetry Monitors -->
      <div class="hud-monitors-row">
        <!-- Left Monitor: Input Conduit & Spectrum Refraction Matrix -->
        <div class="hud-monitor left-monitor">
          <div class="hud-monitor-bar">
            <span class="hud-title">SPECTRA QA — INPUT &amp; REFRACTION TELEMETRY</span>
            <span class="hud-tag white-beam-tag">λ WHITE 380–750nm</span>
          </div>
          <div class="hud-monitor-body">
            <div class="hud-beam-readout" class:active={isWhiteCommandFiring || isLoading}>
              <span class="white-laser-dot"></span>
              <span class="readout-text">{activeCommandSummary}</span>
            </div>
            <div class="hud-spectrum-bars">
              {#each SPECTRUM_AGENTS as ag}
                {@const isAgActive = previewTargetAgents.includes(ag.id)}
                <div
                  class="hud-spec-bar"
                  class:active={isAgActive}
                  style="--ag-color: {ag.color};"
                  title={ag.name}
                >
                  <span class="spec-dot"></span>
                  <span class="spec-name">{ag.shortName}</span>
                  <span class="spec-state">{isAgActive ? (isLoading || isWhiteCommandFiring ? "ACTIVE" : "LOCKED") : "IDLE"}</span>
                </div>
              {/each}
            </div>
          </div>
        </div>

        <!-- Right Monitor: Exit Criteria & Orchestration Gate Matrix -->
        <div class="hud-monitor right-monitor">
          <div class="hud-monitor-bar">
            <span class="hud-title">ORCHESTRATION GATE &amp; EXIT CRITERIA MATRIX</span>
            <span class="hud-tag gate-pass-tag">PASSED • MCP ONLINE</span>
          </div>
          <div class="hud-kpi-grid">
            <div class="hud-kpi-box">
              <span class="kpi-val">100%</span>
              <span class="kpi-lbl">Beam Coherence</span>
            </div>
            <div class="hud-kpi-box green">
              <span class="kpi-val">{previewTargetAgents.length}/6</span>
              <span class="kpi-lbl">Active Agents</span>
            </div>
            <div class="hud-kpi-box cyan">
              <span class="kpi-val">{totalDispatchedCount}</span>
              <span class="kpi-lbl">Dispatched</span>
            </div>
            <div class="hud-kpi-box violet">
              <span class="kpi-val">{routingMode === "auto" ? "AUTO" : "MANUAL"}</span>
              <span class="kpi-lbl">Routing Mode</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ── CENTRAL HOLOGRAPHIC PRISM CORE ARENA ── -->
      <div class="prism-arena-viewport" class:command-blazing={isWhiteCommandFiring || isLoading}>
        <div class="arena-grid-floor" aria-hidden="true"></div>
        <div class="arena-ambient-core" aria-hidden="true"></div>

        <!-- SVG Optical Laser & Refraction Engine -->
        <svg class="prism-optical-svg" viewBox="0 0 1000 500" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <defs>
            <!-- Lightweight Single-Pass White Command Glow Filter -->
            <filter id="whiteBeamGlow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="4.5" result="blur1" />
              <feMerge>
                <feMergeNode in="blur1" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <!-- Lightweight Single-Pass Spectrum Laser Glow Filter -->
            <filter id="spectrumLaserGlow" x="-25%" y="-25%" width="150%" height="150%">
              <feGaussianBlur stdDeviation="3.5" result="specBlur1" />
              <feMerge>
                <feMergeNode in="specBlur1" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <!-- Rainbow Dispersion Gradient for Upper Sky Beams -->
            <linearGradient id="rainbowDispersionLeft" x1="100%" y1="50%" x2="0%" y2="0%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95" />
              <stop offset="22%" stop-color="#f43f5e" stop-opacity="0.75" />
              <stop offset="45%" stop-color="#f59e0b" stop-opacity="0.7" />
              <stop offset="68%" stop-color="#10b981" stop-opacity="0.7" />
              <stop offset="85%" stop-color="#38bdf8" stop-opacity="0.75" />
              <stop offset="100%" stop-color="#a855f7" stop-opacity="0.1" />
            </linearGradient>

            <linearGradient id="rainbowDispersionRight" x1="0%" y1="50%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.95" />
              <stop offset="22%" stop-color="#ec4899" stop-opacity="0.75" />
              <stop offset="45%" stop-color="#eab308" stop-opacity="0.7" />
              <stop offset="68%" stop-color="#10b981" stop-opacity="0.7" />
              <stop offset="85%" stop-color="#06b6d4" stop-opacity="0.75" />
              <stop offset="100%" stop-color="#6366f1" stop-opacity="0.1" />
            </linearGradient>

            <!-- Pure White Vertical Input Beam Gradient -->
            <linearGradient id="pureWhiteConduit" x1="50%" y1="0%" x2="50%" y2="100%">
              <stop offset="0%" stop-color="#e0f2fe" stop-opacity="0.2" />
              <stop offset="45%" stop-color="#ffffff" stop-opacity="0.98" />
              <stop offset="100%" stop-color="#ffffff" stop-opacity="1" />
            </linearGradient>

            <!-- 3D Prism Facet Gradients -->
            <linearGradient id="prismFacetTop" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.75" />
              <stop offset="50%" stop-color="#bae6fd" stop-opacity="0.35" />
              <stop offset="100%" stop-color="#c084fc" stop-opacity="0.45" />
            </linearGradient>
            <linearGradient id="prismFacetLeft" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.45" />
              <stop offset="50%" stop-color="#818cf8" stop-opacity="0.3" />
              <stop offset="100%" stop-color="#f43f5e" stop-opacity="0.4" />
            </linearGradient>
            <linearGradient id="prismFacetRight" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.55" />
              <stop offset="50%" stop-color="#34d399" stop-opacity="0.3" />
              <stop offset="100%" stop-color="#f59e0b" stop-opacity="0.45" />
            </linearGradient>
          </defs>

          <!-- 1. UPPER AMBIENT RAINBOW DISPERSION CONES -->
          <g class="ambient-rainbow-wings" class:active={isWhiteCommandFiring || isLoading}>
            <polygon points="335,165 20,0 135,0" fill="url(#rainbowDispersionLeft)" opacity={isWhiteCommandFiring || isLoading ? "0.62" : "0.24"} />
            <polygon points="665,165 865,0 980,0" fill="url(#rainbowDispersionRight)" opacity={isWhiteCommandFiring || isLoading ? "0.62" : "0.24"} />
          </g>

          <!-- 2. PURE WHITE INPUT COMMAND BEAM (ลำแสงสีขาวบริสุทธิ์เข้าสู่ศูนย์กลางปริซึม) -->
          <g class="white-input-beam-group" class:firing={isWhiteCommandFiring || isLoading}>
            <line
              x1="500" y1="8"
              x2="500" y2="255"
              stroke="#bae6fd"
              stroke-width={isWhiteCommandFiring || isLoading ? "22" : "10"}
              stroke-linecap="round"
              opacity={isWhiteCommandFiring || isLoading ? "0.35" : "0.14"}
            />
            <line
              x1="500" y1="8"
              x2="500" y2="255"
              stroke="url(#pureWhiteConduit)"
              stroke-width={isWhiteCommandFiring || isLoading ? "9" : "4"}
              stroke-linecap="round"
              filter="url(#whiteBeamGlow)"
            />
            <line
              class="white-photon-stream"
              x1="500" y1="8"
              x2="500" y2="255"
              stroke="#ffffff"
              stroke-width={isWhiteCommandFiring || isLoading ? "5" : "2"}
              stroke-dasharray="18 26"
              stroke-linecap="round"
            />
          </g>

          <!-- 3. RELAY BRIDGES FROM CENTRAL CUBE & CORE TO SECONDARY PRISMS -->
          <g class="relay-prism-bridges">
            <line
              x1="500" y1="145" x2="335" y2="165"
              stroke="#ffffff"
              stroke-width={previewTargetAgents.includes("diagram") ? "4.5" : "2"}
              opacity={previewTargetAgents.includes("diagram") ? "0.9" : "0.25"}
            />
            <line
              x1="500" y1="255" x2="335" y2="165"
              stroke="#ec4899"
              stroke-width={previewTargetAgents.includes("diagram") ? "3.5" : "1.5"}
              opacity={previewTargetAgents.includes("diagram") ? "0.75" : "0.2"}
            />

            <line
              x1="500" y1="145" x2="665" y2="165"
              stroke="#ffffff"
              stroke-width={previewTargetAgents.includes("performance") ? "4.5" : "2"}
              opacity={previewTargetAgents.includes("performance") ? "0.9" : "0.25"}
            />
            <line
              x1="500" y1="255" x2="665" y2="165"
              stroke="#06b6d4"
              stroke-width={previewTargetAgents.includes("performance") ? "3.5" : "1.5"}
              opacity={previewTargetAgents.includes("performance") ? "0.75" : "0.2"}
            />

            <line
              x1="500" y1="255" x2="390" y2="295"
              stroke="#ffffff"
              stroke-width={previewTargetAgents.includes("consult") ? "4.5" : "2"}
              opacity={previewTargetAgents.includes("consult") ? "0.9" : "0.25"}
            />
          </g>

          <!-- 4. THE 6 REFRACTED SPECTRUM BEAMS TO SPECIALIST AGENTS -->
          {#each SPECTRUM_AGENTS as agent}
            {@const isTargeted = previewTargetAgents.includes(agent.id)}
            {@const isFiringNow = isTargeted && (isWhiteCommandFiring || isLoading)}
            <g class="agent-spectrum-beam-group" class:targeted={isTargeted} class:firing={isFiringNow}>
              <!-- Wide Spectrum Dispersion Halo -->
              <line
                x1={agent.beamStart.x}
                y1={agent.beamStart.y}
                x2={agent.beamEnd.x}
                y2={agent.beamEnd.y}
                stroke={agent.color}
                stroke-width={isFiringNow ? "20" : isTargeted ? "10" : "4"}
                stroke-linecap="round"
                opacity={isFiringNow ? "0.26" : isTargeted ? "0.14" : "0.05"}
              />

              <!-- Secondary Spectrum Harmonic Ray -->
              <line
                x1={agent.beamStart.x}
                y1={agent.beamStart.y}
                x2={agent.beamEnd.x}
                y2={agent.beamEnd.y - 8}
                stroke={agent.colorSecondary}
                stroke-width={isFiringNow ? "5" : isTargeted ? "2.5" : "1"}
                stroke-linecap="round"
                opacity={isFiringNow ? "0.6" : isTargeted ? "0.32" : "0.1"}
              />

              <!-- Primary Colored Spectrum Beam -->
              <line
                x1={agent.beamStart.x}
                y1={agent.beamStart.y}
                x2={agent.beamEnd.x}
                y2={agent.beamEnd.y}
                stroke={agent.color}
                stroke-width={isFiringNow ? "8" : isTargeted ? "4" : "1.5"}
                stroke-linecap="round"
                opacity={isFiringNow ? "0.98" : isTargeted ? "0.68" : "0.18"}
                filter={isTargeted ? "url(#spectrumLaserGlow)" : undefined}
              />

              <!-- PURE WHITE COMMAND CORE INSIDE THE ACTIVE BEAM ("เมื่อ Agent มีการใช้งาน แสดงสีขาวเปรียบเหมือนคำสั่ง") -->
              <line
                class="white-command-core-ray"
                x1={agent.beamStart.x}
                y1={agent.beamStart.y}
                x2={agent.beamEnd.x}
                y2={agent.beamEnd.y}
                stroke="#ffffff"
                stroke-width={isFiringNow ? "3.8" : isTargeted ? "1.8" : "0"}
                stroke-linecap="round"
                opacity={isFiringNow ? "1" : isTargeted ? "0.75" : "0"}
              />

              {#if isTargeted}
                <line
                  class="spectrum-photon-pulse"
                  x1={agent.beamStart.x}
                  y1={agent.beamStart.y}
                  x2={agent.beamEnd.x}
                  y2={agent.beamEnd.y}
                  stroke="#ffffff"
                  stroke-width={isFiringNow ? "4.5" : "2.5"}
                  stroke-dasharray="14 34"
                  stroke-linecap="round"
                />
              {/if}

              <!-- Target Impact Flare at Agent Endpoint -->
              <circle
                cx={agent.beamEnd.x}
                cy={agent.beamEnd.y}
                r={isFiringNow ? "14" : isTargeted ? "8" : "4"}
                fill={agent.color}
                opacity={isFiringNow ? "0.55" : isTargeted ? "0.28" : "0.12"}
              />
              <circle
                cx={agent.beamEnd.x}
                cy={agent.beamEnd.y}
                r={isFiringNow ? "6" : isTargeted ? "3.5" : "2"}
                fill="#ffffff"
                opacity={isFiringNow ? "1" : isTargeted ? "0.85" : "0.3"}
              />
            </g>
          {/each}

          <!-- 5. SECONDARY DISPERSION PRISMS -->
          <g class="secondary-prism left-prism" transform="translate(335, 165)">
            <polygon points="-28,-36 26,-16 -12,34" fill="url(#prismFacetLeft)" stroke="#ffffff" stroke-width="1.5" opacity="0.88" />
            <polygon points="-28,-36 8,-2 -12,34" fill="rgba(255,255,255,0.22)" stroke="#e0f2fe" stroke-width="1" />
            <circle cx="0" cy="0" r="6" fill="#ffffff" filter="url(#whiteBeamGlow)" />
          </g>

          <g class="secondary-prism right-prism" transform="translate(665, 165)">
            <polygon points="18,-38 30,28 -26,12" fill="url(#prismFacetRight)" stroke="#ffffff" stroke-width="1.5" opacity="0.88" />
            <polygon points="18,-38 -4,4 -26,12" fill="rgba(255,255,255,0.22)" stroke="#bae6fd" stroke-width="1" />
            <circle cx="0" cy="0" r="6" fill="#ffffff" filter="url(#whiteBeamGlow)" />
          </g>

          <g class="secondary-prism lower-left-prism" transform="translate(390, 295)">
            <polygon points="-32,-12 12,-28 32,10 -12,26" fill="url(#prismFacetTop)" stroke="#fde68a" stroke-width="1.4" opacity="0.88" />
            <line x1="-32" y1="-12" x2="32" y2="10" stroke="#ffffff" stroke-width="1.2" opacity="0.8" />
            <circle cx="0" cy="0" r="5" fill="#ffffff" filter="url(#whiteBeamGlow)" />
          </g>

          <!-- 6. CENTRAL 3D CRYSTALLINE PRISM CUBE -->
          <g class="central-prism-cube" transform="translate(500, 142)">
            <circle
              class="cube-orbital-ring"
              cx="0" cy="0"
              r={isWhiteCommandFiring || isLoading ? "64" : "54"}
              fill="none"
              stroke="rgba(255,255,255,0.28)"
              stroke-width="1.2"
              stroke-dasharray="6 8"
            />
            <polygon points="0,-46 44,-22 0,2 -44,-22" fill="url(#prismFacetTop)" stroke="#ffffff" stroke-width="2" />
            <polygon points="-44,-22 0,2 0,50 -44,24" fill="url(#prismFacetLeft)" stroke="#e0f2fe" stroke-width="1.8" />
            <polygon points="0,2 44,-22 44,24 0,50" fill="url(#prismFacetRight)" stroke="#ffffff" stroke-width="1.8" />
            <polygon points="0,-46 44,24 -44,24" fill="rgba(255,255,255,0.14)" stroke="rgba(255,255,255,0.55)" stroke-width="1" />
            <circle cx="0" cy="2" r={isWhiteCommandFiring || isLoading ? "18" : "11"} fill="#ffffff" filter="url(#whiteBeamGlow)" />
            <line x1="-28" y1="2" x2="28" y2="2" stroke="#ffffff" stroke-width="2.5" filter="url(#whiteBeamGlow)" />
            <line x1="0" y1="-26" x2="0" y2="30" stroke="#ffffff" stroke-width="2.5" filter="url(#whiteBeamGlow)" />
          </g>

          <!-- 7. LOWER PRISM CORE SINGULARITY & REACTOR PEDESTAL -->
          <g class="central-reactor-pedestal" transform="translate(500, 255)">
            <path d="M-54,48 L54,48 L66,115 L-66,115 Z" fill="rgba(15, 23, 42, 0.92)" stroke="rgba(148, 163, 184, 0.4)" stroke-width="1.5" />
            <ellipse cx="0" cy="48" rx="54" ry="14" fill="rgba(30, 41, 59, 0.95)" stroke="rgba(186, 230, 253, 0.5)" stroke-width="1.5" />
            <ellipse cx="0" cy="22" rx="40" ry="12" fill="rgba(15, 23, 42, 0.9)" stroke="#38bdf8" stroke-width="1.5" />

            {#if isWhiteCommandFiring || isLoading}
              <circle class="shockwave-ring r1" cx="0" cy="0" r="24" fill="none" stroke="#ffffff" stroke-width="2.5" />
              <circle class="shockwave-ring r2" cx="0" cy="0" r="24" fill="none" stroke="#38bdf8" stroke-width="1.8" />
            {/if}

            <circle cx="0" cy="0" r="32" fill="rgba(15, 23, 42, 0.75)" stroke="#bae6fd" stroke-width="2" />
            <circle
              cx="0" cy="0"
              r={isWhiteCommandFiring || isLoading ? "24" : "16"}
              fill="#ffffff"
              filter="url(#whiteBeamGlow)"
            />
            <line x1="-42" y1="0" x2="42" y2="0" stroke="#ffffff" stroke-width="3" filter="url(#whiteBeamGlow)" />
            <line x1="0" y1="-42" x2="0" y2="42" stroke="#ffffff" stroke-width="3" filter="url(#whiteBeamGlow)" />
          </g>
        </svg>

        <!-- ── SYMMETRIC 3-COLUMN ARENA: 3 LEFT STATIONS | PRISM CORE | 3 RIGHT STATIONS ── -->
        <div class="arena-symmetric-grid">
          <!-- Left Column: 3 Stacked Specialist Agent Cards -->
          <div class="agent-stations-column col-left">
            {#each LEFT_AGENTS as agent}
              {@const isTargeted = previewTargetAgents.includes(agent.id)}
              {@const isFiringNow = isTargeted && (isWhiteCommandFiring || isLoading)}
              <div
                class="agent-station-card {agent.positionClass}"
                class:is-targeted={isTargeted}
                class:is-firing={isFiringNow}
                style="--agent-color: {agent.color}; --agent-light: {agent.colorLight}; --agent-sec: {agent.colorSecondary};"
              >
                <button
                  type="button"
                  class="station-select-body"
                  aria-pressed={isTargeted}
                  on:click={() => handleStationClick(agent)}
                >
                  <div class="station-command-bar">
                    <span class="wavelength-tag">{agent.wavelength}</span>
                    <span class="station-live-pill" class:firing={isFiringNow} class:targeted={isTargeted}>
                      {#if isFiringNow}
                        <span class="white-cmd-dot"></span> CMD ACTIVE
                      {:else if isTargeted}
                        <span class="spec-ready-dot"></span> READY
                      {:else}
                        STANDBY
                      {/if}
                    </span>
                  </div>

                  <div class="station-main-row">
                    <div class="station-avatar-orb" aria-hidden="true">
                      {#if agent.id === "diagram"}
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                          <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                          <polyline points="2 17 12 22 22 17"></polyline>
                          <polyline points="2 12 12 17 22 12"></polyline>
                        </svg>
                      {:else if agent.id === "doc_creation"}
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                          <polyline points="14 2 14 8 20 8"></polyline>
                          <line x1="12" y1="18" x2="12" y2="12"></line>
                          <line x1="9" y1="15" x2="15" y2="15"></line>
                        </svg>
                      {:else}
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M9 11l3 3L22 4"></path>
                          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path>
                        </svg>
                      {/if}
                    </div>
                    <div class="station-info">
                      <h4 class="station-title">{agent.name}</h4>
                      <p class="station-desc">{agent.roleDesc}</p>
                    </div>
                  </div>
                </button>

                <div class="station-actions-row">
                  <button
                    type="button"
                    class="btn-station-prompt"
                    on:click={() => dispatchAgentPrompt(agent)}
                    disabled={isLoading}
                    title="ยิงลำแสงคำสั่งไปยัง {agent.name}"
                  >
                    ⚡ สั่งงาน Agent
                  </button>
                  <button
                    type="button"
                    class="btn-station-open"
                    on:click={() => navigateToAgentModule(agent)}
                    title="เปิดหน้าเมนู {agent.name}"
                  >
                    เปิดโมดูล &nearr;
                  </button>
                </div>
              </div>
            {/each}
          </div>

          <!-- Center Column: Input Conduit Badge + Open Prism Core Visual + Core Label -->
          <div class="arena-core-column">
            <div class="white-conduit-floating-badge" class:active={isWhiteCommandFiring || isLoading}>
              <span class="beam-spark"></span>
              <span class="conduit-title">
                WHITE COMMAND INPUT: <strong>{INPUT_SOURCES.find(s => s.id === selectedInputSource)?.label}</strong>
              </span>
            </div>

            <div class="core-visual-spacer" aria-hidden="true"></div>

            <div class="prism-core-center-label" class:active={isWhiteCommandFiring || isLoading}>
              <span class="core-badge-title">PRISM CORE ORCHESTRATOR</span>
              <span class="core-badge-sub">
                {isLoading ? "⚡ กำลังหักเหคำสั่งสีขาวสู่ Agent..." : isWhiteCommandFiring ? "🌈 กระจายลำแสงสเปกตรัม Real-time" : "ศูนย์กลางปริซึม • คลิก Agent เพื่อล็อกเป้าหมาย"}
              </span>
            </div>
          </div>

          <!-- Right Column: 3 Stacked Specialist Agent Cards -->
          <div class="agent-stations-column col-right">
            {#each RIGHT_AGENTS as agent}
              {@const isTargeted = previewTargetAgents.includes(agent.id)}
              {@const isFiringNow = isTargeted && (isWhiteCommandFiring || isLoading)}
              <div
                class="agent-station-card {agent.positionClass}"
                class:is-targeted={isTargeted}
                class:is-firing={isFiringNow}
                style="--agent-color: {agent.color}; --agent-light: {agent.colorLight}; --agent-sec: {agent.colorSecondary};"
              >
                <button
                  type="button"
                  class="station-select-body"
                  aria-pressed={isTargeted}
                  on:click={() => handleStationClick(agent)}
                >
                  <div class="station-command-bar">
                    <span class="wavelength-tag">{agent.wavelength}</span>
                    <span class="station-live-pill" class:firing={isFiringNow} class:targeted={isTargeted}>
                      {#if isFiringNow}
                        <span class="white-cmd-dot"></span> CMD ACTIVE
                      {:else if isTargeted}
                        <span class="spec-ready-dot"></span> READY
                      {:else}
                        STANDBY
                      {/if}
                    </span>
                  </div>

                  <div class="station-main-row">
                    <div class="station-avatar-orb" aria-hidden="true">
                      {#if agent.id === "automation"}
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="16 18 22 12 16 6"></polyline>
                          <polyline points="8 6 2 12 8 18"></polyline>
                        </svg>
                      {:else if agent.id === "performance"}
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                        </svg>
                      {:else}
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                        </svg>
                      {/if}
                    </div>
                    <div class="station-info">
                      <h4 class="station-title">{agent.name}</h4>
                      <p class="station-desc">{agent.roleDesc}</p>
                    </div>
                  </div>
                </button>

                <div class="station-actions-row">
                  <button
                    type="button"
                    class="btn-station-prompt"
                    on:click={() => dispatchAgentPrompt(agent)}
                    disabled={isLoading}
                    title="ยิงลำแสงคำสั่งไปยัง {agent.name}"
                  >
                    ⚡ สั่งงาน Agent
                  </button>
                  <button
                    type="button"
                    class="btn-station-open"
                    on:click={() => navigateToAgentModule(agent)}
                    title="เปิดหน้าเมนู {agent.name}"
                  >
                    เปิดโมดูล &nearr;
                  </button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      </div>
    </section>

    <!-- ═══════════════════════════════════════════════════════════════════
         RIGHT DOCKED PANEL: COMPACT AI PROMPT & COMMAND CONSOLE
         ═══════════════════════════════════════════════════════════════════ -->
    <aside class="prism-prompt-dock" aria-label="Prism AI Command Prompt Console">
      <div class="dock-header">
        <div class="dock-header-left">
          <div class="dock-prism-icon">
            <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.2">
              <polygon points="12 2 2 20 22 20 12 2"></polygon>
              <line x1="12" y1="2" x2="12" y2="20"></line>
            </svg>
          </div>
          <div>
            <h3>Prism Command Prompt</h3>
            <p>สั่งการด้วยลำแสงสีขาว • หักเหสู่ Agent อัตโนมัติ</p>
          </div>
        </div>
        <button type="button" class="btn-dock-clear" on:click={clearChat} title="ล้างประวัติการสนทนา">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          <span>ล้างแชท</span>
        </button>
      </div>

      <!-- Target Agent Routing Bar -->
      <div class="dock-routing-strip">
        <div class="routing-strip-top">
          <span class="routing-lbl">เป้าหมายการหักเหแสง (Target Agents):</span>
          <div class="routing-mode-switch">
            <button
              type="button"
              class="mode-btn"
              class:active={routingMode === "auto"}
              on:click={() => {
                routingMode = "auto";
                activeAgentIds = SPECTRUM_AGENTS.map(a => a.id);
              }}
            >
              Auto-Route
            </button>
            <button
              type="button"
              class="mode-btn"
              class:active={routingMode === "manual"}
              on:click={() => {
                routingMode = "manual";
              }}
            >
              ล็อกเอง ({manualSelectedAgents.length})
            </button>
          </div>
        </div>

        <div class="agent-mini-pills">
          {#each SPECTRUM_AGENTS as ag}
            {@const isTargeted = previewTargetAgents.includes(ag.id)}
            <button
              type="button"
              class="agent-mini-pill"
              class:active={isTargeted}
              style="--pill-color: {ag.color};"
              on:click={() => handleStationClick(ag)}
              title="คลิกเพื่อเลือก/ทดสอบลำแสง {ag.name}"
            >
              <span class="pill-dot"></span>
              <span>{ag.shortName}</span>
            </button>
          {/each}
        </div>
      </div>

      <!-- Chat Messages Stream -->
      <div class="dock-chat-messages" bind:this={chatContainer}>
        {#each messages as msg, i}
          <div class="dock-msg-row {msg.role}" in:fade={{ duration: 180 }}>
            <div class="dock-msg-meta">
              {#if msg.role === "user"}
                <span class="white-cmd-badge">
                  <span class="w-dot"></span>
                  WHITE COMMAND • {(msg.inputSource || "requirement").toUpperCase()}
                </span>
              {:else}
                <span class="role-label">💎 Prism Core Orchestrator</span>
              {/if}
              <span class="msg-time">{msg.timestamp || ""}</span>
            </div>

            <div class="dock-msg-bubble {msg.role}">
              <div class="markdown-preview">
                {@html renderFormattedText(msg.content)}
              </div>

              {#if msg.agents && msg.agents.length > 0}
                <div class="msg-spectrum-tags">
                  {#each msg.agents as agId}
                    {@const agObj = getAgentById(agId)}
                    {#if agObj}
                      <span class="msg-ag-chip" style="--chip-color: {agObj.color};">
                        <span class="c-dot"></span>
                        {agObj.shortName}
                      </span>
                    {/if}
                  {/each}
                </div>
              {/if}

              {#if msg.role === "assistant"}
                <button
                  type="button"
                  class="btn-copy-msg"
                  aria-label="คัดลอกข้อความ"
                  on:click={() => copyToClipboard(msg.content, i)}
                  title="คัดลอกข้อความ"
                >
                  {#if copiedIndex === i}
                    <svg viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2" width="14" height="14" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>
                  {:else}
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                  {/if}
                </button>
              {/if}
            </div>
          </div>
        {/each}

        {#if isLoading}
          <div class="dock-msg-row assistant" in:slide={{ duration: 180 }}>
            <div class="dock-msg-meta">
              <span class="role-label">💎 Prism Core Orchestrator</span>
              <span class="msg-time">กำลังหักเหสเปกตรัม...</span>
            </div>
            <div class="dock-msg-bubble assistant loading-bubble">
              <div class="prism-loading-row">
                <div class="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
                <span class="loading-label">กำลังยิงลำแสงสีขาวและประมวลผลร่วมกับ {activeAgentIds.length} QA Agent(s)...</span>
              </div>
            </div>
          </div>
        {/if}
      </div>

      <!-- Compact Quick Prompt Chips -->
      <div class="dock-quick-prompts">
        <div class="qp-scroll-row">
          {#each QUICK_PROMPTS as qp}
            <button
              type="button"
              class="dock-qp-chip"
              on:click={() => useQuickPrompt(qp)}
              disabled={isLoading}
              title={qp.text}
            >
              <span class="qp-ico">{qp.icon}</span>
              <span class="qp-lbl">{qp.title}</span>
            </button>
          {/each}
        </div>
      </div>

      <!-- Bottom Prompt Input Box -->
      <div class="dock-input-area">
        <div class="dock-input-box" class:has-text={!!currentInput.trim()}>
          <textarea
            bind:value={currentInput}
            on:keydown={handleKeydown}
            aria-label="พิมพ์คำสั่งถึง Master Agent"
            placeholder="พิมพ์คำสั่ง ({INPUT_SOURCES.find(s => s.id === selectedInputSource)?.label}) เพื่อยิงลำแสงสีขาวเข้าสู่ Prism Core..."
            disabled={isLoading}
            rows="2"
          ></textarea>
          <div class="dock-input-footer">
            <span class="input-hint">
              ลำแสงคำสั่งสีขาว &rarr; หักเหสู่ <strong>{previewTargetAgents.length} Agent(s)</strong>
            </span>
            <button
              type="button"
              class="btn-dispatch-beam"
              class:active={!!currentInput.trim() && !isLoading}
              on:click={() => sendMessage()}
              disabled={isLoading || !currentInput.trim()}
              title="ยิงลำแสงคำสั่งเข้าสู่ Prism Core (Enter)"
            >
              <span>ยิงลำแสงคำสั่ง</span>
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </aside>
  </div>
</div>

<style>
  .spectra-orchestration-shell {
    width: 100%;
    height: 100%;
    padding: 12px 18px 16px;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
    overflow: hidden;
  }

  @media (max-width: 1220px) {
    .spectra-orchestration-shell {
      overflow-y: auto;
    }
  }

  /* ── TOP COMMAND HEADER BAR ── */
  .orchestration-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    padding: 12px 18px;
    background: linear-gradient(135deg, rgba(16, 19, 32, 0.88), rgba(12, 15, 26, 0.78));
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: 16px;
    backdrop-filter: blur(14px);
    box-shadow: 0 8px 28px -8px rgba(0, 0, 0, 0.45);
    flex-shrink: 0;
  }

  .top-bar-brand {
    display: flex;
    align-items: center;
    gap: 14px;
    min-width: 0;
    flex: 1 1 420px;
  }

  .prism-emblem {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    background: radial-gradient(circle at 50% 45%, rgba(255, 255, 255, 0.25), rgba(99, 102, 241, 0.28) 55%, rgba(168, 85, 247, 0.35));
    border: 1px solid rgba(255, 255, 255, 0.45);
    color: #e0f2fe;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: 0 0 18px rgba(168, 85, 247, 0.35);
    transition: all 0.3s ease;
  }
  .prism-emblem.core-blazing {
    background: radial-gradient(circle at 50% 45%, #ffffff, rgba(56, 189, 248, 0.65) 55%, rgba(168, 85, 247, 0.75));
    border-color: #ffffff;
    box-shadow: 0 0 26px rgba(255, 255, 255, 0.85), 0 0 40px rgba(168, 85, 247, 0.6);
    transform: scale(1.05);
  }

  .brand-titles {
    min-width: 0;
  }
  .brand-title-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .brand-title-row h2 {
    margin: 0;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 18px;
    font-weight: 800;
    letter-spacing: 0.04em;
    color: #f8fafc;
  }
  .prism-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 3px 10px;
    border-radius: 999px;
    color: #34d399;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.35);
    transition: all 0.25s ease;
  }
  .prism-status-pill.firing {
    color: #ffffff;
    background: linear-gradient(90deg, rgba(56, 189, 248, 0.35), rgba(168, 85, 247, 0.45));
    border-color: #ffffff;
    box-shadow: 0 0 14px rgba(255, 255, 255, 0.45);
  }
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 8px currentColor;
    animation: pulseOrb 1.6s infinite ease-in-out;
  }

  .brand-sub {
    margin: 2px 0 0 0;
    font-size: 12px;
    color: #94a3b8;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .top-bar-controls {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }

  .input-conduit-selector {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
    background: rgba(9, 11, 19, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 4px 6px;
    border-radius: 11px;
  }
  .conduit-label {
    font-size: 11px;
    font-weight: 600;
    color: #94a3b8;
    padding: 0 6px;
  }
  .conduit-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border-radius: 8px;
    border: 1px solid transparent;
    background: transparent;
    color: #cbd5e1;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .conduit-pill:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.06);
  }
  .conduit-pill.active {
    background: rgba(255, 255, 255, 0.16);
    border-color: rgba(255, 255, 255, 0.65);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(255, 255, 255, 0.22);
  }

  .btn-simulate-prism {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 34px;
    padding: 0 14px;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.45);
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.18), rgba(99, 102, 241, 0.32), rgba(236, 72, 153, 0.32));
    color: #ffffff;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(168, 85, 247, 0.28);
    transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-simulate-prism:hover {
    transform: translateY(-1px);
    border-color: #ffffff;
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.45), 0 6px 18px rgba(168, 85, 247, 0.45);
  }

  /* ── MAIN 2-COLUMN WORKSPACE GRID ── */
  .orchestration-deck-grid {
    flex: 1;
    display: grid;
    grid-template-columns: minmax(0, 1.75fr) minmax(340px, 410px);
    gap: 14px;
    min-height: 0;
    align-items: stretch;
  }

  @media (max-width: 1220px) {
    .orchestration-deck-grid {
      grid-template-columns: 1fr;
    }
  }

  /* ═══════════════════════════════════════════════════════════════════
     LEFT / CENTER STAGE: PRISM CORE & 6 AGENT STATIONS
     ═══════════════════════════════════════════════════════════════════ */
  .prism-stage-card {
    display: flex;
    flex-direction: column;
    gap: 10px;
    background: radial-gradient(circle at 50% 48%, rgba(30, 27, 75, 0.55), rgba(8, 10, 18, 0.94) 75%);
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: 18px;
    padding: 12px 14px;
    box-shadow: inset 0 0 60px rgba(0, 0, 0, 0.65), 0 12px 32px rgba(0, 0, 0, 0.4);
    min-height: 0;
    min-width: 0;
    height: 100%;
    overflow: hidden;
    position: relative;
  }

  /* Top Dual Holographic HUD Monitors */
  .hud-monitors-row {
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
    gap: 12px;
    z-index: 3;
    flex-shrink: 0;
  }
  @media (max-width: 860px) {
    .hud-monitors-row {
      grid-template-columns: 1fr;
    }
  }

  .hud-monitor {
    min-width: 0;
    background: rgba(11, 15, 28, 0.82);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 12px;
    padding: 8px 12px;
    backdrop-filter: blur(10px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
  }
  .hud-monitor-body {
    min-width: 0;
  }
  .left-monitor {
    border-color: rgba(56, 189, 248, 0.3);
  }
  .right-monitor {
    border-color: rgba(168, 85, 247, 0.3);
  }

  .hud-monitor-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding-bottom: 6px;
    margin-bottom: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }
  .hud-title {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 10.5px;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: #cbd5e1;
    min-width: 0;
  }
  .hud-tag {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 9.5px;
    font-weight: 700;
    padding: 1.5px 7px;
    border-radius: 6px;
    flex-shrink: 0;
  }
  .white-beam-tag {
    background: rgba(255, 255, 255, 0.14);
    border: 1px solid rgba(255, 255, 255, 0.4);
    color: #ffffff;
  }
  .gate-pass-tag {
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.4);
    color: #34d399;
  }

  .hud-beam-readout {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
    padding: 4px 8px;
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 6px;
    font-size: 11px;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .hud-beam-readout.active {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.55);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(255, 255, 255, 0.18);
  }
  .white-laser-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 0 8px #ffffff;
    flex-shrink: 0;
  }
  .readout-text {
    min-width: 0;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-weight: 600;
    font-size: 10.5px;
  }

  .hud-spectrum-bars {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 4px;
  }
  .hud-spec-bar {
    display: flex;
    align-items: center;
    gap: 5px;
    min-width: 0;
    padding: 3px 6px;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 10px;
    color: #94a3b8;
    transition: all 0.2s ease;
  }
  .hud-spec-bar.active {
    background: rgba(255, 255, 255, 0.07);
    border-color: var(--ag-color);
    color: #f8fafc;
  }
  .spec-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ag-color);
    box-shadow: 0 0 6px var(--ag-color);
    flex-shrink: 0;
  }
  .spec-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 600;
  }
  .spec-state {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 9px;
    font-weight: 700;
    color: var(--ag-color);
    flex-shrink: 0;
  }

  .hud-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 6px;
  }
  @media (max-width: 1024px) {
    .hud-kpi-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  @media (max-width: 640px) {
    .hud-spectrum-bars {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  .hud-kpi-box {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 6px 4px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .hud-kpi-box.green {
    background: rgba(16, 185, 129, 0.1);
    border-color: rgba(16, 185, 129, 0.3);
  }
  .hud-kpi-box.cyan {
    background: rgba(6, 182, 212, 0.1);
    border-color: rgba(6, 182, 212, 0.3);
  }
  .hud-kpi-box.violet {
    background: rgba(168, 85, 247, 0.1);
    border-color: rgba(168, 85, 247, 0.3);
  }
  .kpi-val {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 14px;
    font-weight: 800;
    color: #f8fafc;
    line-height: 1.1;
  }
  .hud-kpi-box.green .kpi-val { color: #34d399; }
  .hud-kpi-box.cyan .kpi-val { color: #38bdf8; }
  .hud-kpi-box.violet .kpi-val { color: #c084fc; }
  .kpi-lbl {
    font-size: 9.5px;
    color: #94a3b8;
    margin-top: 2px;
  }

  /* ── CENTRAL HOLOGRAPHIC PRISM ARENA VIEWPORT ── */
  .prism-arena-viewport {
    position: relative;
    flex: 1;
    width: 100%;
    min-height: 410px;
    border-radius: 14px;
    background: radial-gradient(ellipse at 50% 45%, rgba(56, 189, 248, 0.1), rgba(15, 23, 42, 0.4) 55%, rgba(6, 8, 15, 0.85));
    border: 1px solid rgba(255, 255, 255, 0.08);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .prism-arena-viewport.command-blazing {
    border-color: rgba(255, 255, 255, 0.35);
    box-shadow: inset 0 0 50px rgba(255, 255, 255, 0.08);
  }

  .arena-grid-floor {
    position: absolute;
    inset: 48% -10% -15% -10%;
    background: radial-gradient(ellipse at 50% 20%, rgba(99, 102, 241, 0.22), rgba(168, 85, 247, 0.08) 55%, transparent 80%);
    transform: perspective(420px) rotateX(62deg);
    opacity: 0.65;
    pointer-events: none;
  }

  .arena-ambient-core {
    position: absolute;
    width: 340px;
    height: 340px;
    left: 50%;
    top: 46%;
    transform: translate(-50%, -50%);
    background: radial-gradient(circle, rgba(255, 255, 255, 0.22) 0%, rgba(56, 189, 248, 0.14) 35%, rgba(168, 85, 247, 0.12) 60%, transparent 75%);
    filter: blur(18px);
    pointer-events: none;
  }

  .prism-optical-svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 1;
  }

  /* Animated SVG Laser Streams */
  .white-photon-stream {
    animation: whiteBeamFlow 0.7s linear infinite;
  }
  .spectrum-photon-pulse {
    animation: spectrumBeamFlow 0.85s linear infinite;
  }
  .cube-orbital-ring {
    transform-origin: 0px 0px;
    animation: slowOrbitSpin 16s linear infinite;
  }
  .central-prism-cube {
    animation: prismFloat 4s ease-in-out infinite;
  }
  .secondary-prism.left-prism {
    animation: prismFloatLeft 4.8s ease-in-out infinite;
  }
  .secondary-prism.right-prism {
    animation: prismFloatRight 5.2s ease-in-out infinite;
  }
  .shockwave-ring {
    transform-box: fill-box;
    transform-origin: center;
    will-change: transform, opacity;
  }
  .shockwave-ring.r1 {
    animation: shockwaveExpand 1.5s cubic-bezier(0.16, 1, 0.3, 1) infinite;
  }
  .shockwave-ring.r2 {
    animation: shockwaveExpand 1.5s cubic-bezier(0.16, 1, 0.3, 1) 0.45s infinite;
  }

  @keyframes whiteBeamFlow {
    from { stroke-dashoffset: 44; }
    to { stroke-dashoffset: 0; }
  }
  @keyframes spectrumBeamFlow {
    from { stroke-dashoffset: 48; }
    to { stroke-dashoffset: 0; }
  }
  @keyframes slowOrbitSpin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  @keyframes prismFloat {
    0%, 100% { transform: translate(500px, 142px) translateY(0px); }
    50% { transform: translate(500px, 142px) translateY(-6px); }
  }
  @keyframes prismFloatLeft {
    0%, 100% { transform: translate(335px, 165px) translateY(0px); }
    50% { transform: translate(335px, 165px) translateY(-5px); }
  }
  @keyframes prismFloatRight {
    0%, 100% { transform: translate(665px, 165px) translateY(0px); }
    50% { transform: translate(665px, 165px) translateY(5px); }
  }
  @keyframes shockwaveExpand {
    0% { transform: scale(0.7); opacity: 0.95; }
    100% { transform: scale(3.25); opacity: 0; }
  }

  /* ── SYMMETRIC 3-COLUMN ARENA GRID (ZERO OVERLAP) ── */
  .arena-symmetric-grid {
    position: relative;
    z-index: 2;
    flex: 1;
    display: grid;
    grid-template-columns: minmax(195px, 228px) minmax(160px, 1fr) minmax(195px, 228px);
    gap: 12px;
    padding: 12px;
    align-items: stretch;
    min-height: 0;
  }

  .agent-stations-column {
    display: grid;
    grid-template-rows: repeat(3, minmax(0, 1fr));
    gap: 10px;
    min-width: 0;
    min-height: 0;
  }

  .arena-core-column {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
    min-width: 0;
    padding: 2px 4px;
    pointer-events: none;
  }

  .core-visual-spacer {
    flex: 1;
    min-height: 180px;
  }

  /* Center Badges on Arena */
  .white-conduit-floating-badge {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    max-width: 100%;
    padding: 4px 12px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.35);
    color: #e2e8f0;
    font-size: 11px;
    backdrop-filter: blur(8px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    pointer-events: none;
  }
  .white-conduit-floating-badge.active {
    background: rgba(255, 255, 255, 0.18);
    border-color: #ffffff;
    color: #ffffff;
    box-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
  }
  .beam-spark {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 0 10px #ffffff;
    flex-shrink: 0;
  }

  .prism-core-center-label {
    display: flex;
    flex-direction: column;
    align-items: center;
    max-width: 100%;
    padding: 6px 14px;
    border-radius: 10px;
    background: rgba(10, 14, 26, 0.88);
    border: 1px solid rgba(186, 230, 253, 0.38);
    backdrop-filter: blur(10px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.55);
    pointer-events: none;
    text-align: center;
  }
  .prism-core-center-label.active {
    border-color: #ffffff;
    box-shadow: 0 0 24px rgba(255, 255, 255, 0.38), 0 8px 24px rgba(0, 0, 0, 0.6);
  }
  .core-badge-title {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 10.5px;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: #ffffff;
  }
  .core-badge-sub {
    font-size: 10px;
    color: #bae6fd;
  }

  /* ── 6 SPECIALIST AGENT STATION CARDS ── */
  .agent-station-card {
    width: 100%;
    min-width: 0;
    background: rgba(13, 17, 30, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 13px;
    padding: 8px 10px;
    backdrop-filter: blur(12px);
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.45);
    pointer-events: auto;
    transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1),
                border-color 0.25s ease,
                box-shadow 0.25s ease,
                background-color 0.25s ease;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 6px;
  }

  .station-select-body {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
    min-width: 0;
    background: transparent;
    border: none;
    padding: 0;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    border-radius: 8px;
  }
  .station-select-body:focus-visible {
    outline: 2px solid var(--agent-color, #ffffff);
    outline-offset: 2px;
  }

  .agent-station-card.is-targeted {
    border-color: var(--agent-color);
    box-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.6), 0 0 16px -4px var(--agent-color);
  }
  .agent-station-card.is-firing {
    background: linear-gradient(155deg, rgba(255, 255, 255, 0.14), rgba(15, 20, 36, 0.92) 45%);
    border-color: #ffffff;
    box-shadow: 0 0 22px rgba(255, 255, 255, 0.45), 0 0 32px -4px var(--agent-color);
  }
  .agent-station-card:hover {
    border-color: #ffffff;
    transform: translateY(-2px);
    z-index: 5;
  }

  .station-command-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 4px;
    width: 100%;
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
  }
  .wavelength-tag {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 9px;
    font-weight: 700;
    color: var(--agent-light);
    letter-spacing: 0.04em;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .station-live-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 8.5px;
    font-weight: 800;
    padding: 1.5px 6px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.06);
    color: #94a3b8;
  }
  .station-live-pill.targeted {
    background: rgba(255, 255, 255, 0.1);
    color: var(--agent-light);
  }
  .station-live-pill.firing {
    background: #ffffff;
    color: #090b10;
    box-shadow: 0 0 10px #ffffff;
  }
  .white-cmd-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #090b10;
  }
  .spec-ready-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--agent-color);
    box-shadow: 0 0 6px var(--agent-color);
  }

  .station-main-row {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }
  .station-avatar-orb {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--agent-color);
    color: var(--agent-light);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    box-shadow: inset 0 0 10px rgba(255, 255, 255, 0.08);
  }
  .agent-station-card.is-firing .station-avatar-orb {
    background: #ffffff;
    color: #090b10;
    border-color: #ffffff;
    box-shadow: 0 0 14px #ffffff;
  }
  .station-info {
    min-width: 0;
    flex: 1;
  }
  .station-title {
    margin: 0 0 2px 0;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 12.5px;
    font-weight: 700;
    color: #f8fafc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .station-desc {
    margin: 0;
    font-size: 10.5px;
    color: #94a3b8;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .station-actions-row {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-top: 2px;
  }
  .btn-station-prompt {
    flex: 1;
    padding: 4px 7px;
    border-radius: 6px;
    border: 1px solid var(--agent-color);
    background: rgba(255, 255, 255, 0.06);
    color: #f8fafc;
    font-size: 10.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .btn-station-prompt:hover:not(:disabled) {
    background: var(--agent-color);
    color: #ffffff;
  }
  .btn-station-open {
    padding: 4px 7px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: rgba(255, 255, 255, 0.04);
    color: #cbd5e1;
    font-size: 10px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .btn-station-open:hover {
    background: rgba(255, 255, 255, 0.14);
    color: #ffffff;
  }

  @media (max-width: 1180px) {
    .prism-arena-viewport {
      min-height: auto;
    }
    .prism-optical-svg {
      display: none;
    }
    .arena-symmetric-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .arena-core-column {
      grid-column: 1 / -1;
      order: -1;
      flex-direction: row;
      flex-wrap: wrap;
      justify-content: center;
      gap: 8px;
      padding: 2px 0 4px;
    }
    .core-visual-spacer {
      display: none;
    }
    .agent-stations-column {
      display: contents;
    }
  }

  @media (max-width: 768px) {
    .arena-symmetric-grid {
      grid-template-columns: 1fr;
    }
  }

  /* ═══════════════════════════════════════════════════════════════════
     RIGHT DOCKED PANEL: COMPACT AI PROMPT & COMMAND CONSOLE
     ═══════════════════════════════════════════════════════════════════ */
  .prism-prompt-dock {
    display: flex;
    flex-direction: column;
    background: rgba(14, 17, 28, 0.86);
    border: 1px solid rgba(168, 85, 247, 0.28);
    border-radius: 18px;
    backdrop-filter: blur(18px);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.42);
    min-height: 0;
    min-width: 0;
    height: 100%;
    overflow: hidden;
  }

  @media (max-width: 1220px) {
    .prism-stage-card {
      height: auto;
    }
    .prism-prompt-dock {
      height: 560px;
      min-height: 460px;
    }
  }

  .dock-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 12px 16px;
    background: rgba(20, 24, 38, 0.85);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .dock-header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .dock-prism-icon {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.2), rgba(168, 85, 247, 0.35));
    border: 1px solid rgba(255, 255, 255, 0.4);
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .dock-header h3 {
    margin: 0;
    font-size: 14.5px;
    font-weight: 700;
    color: #f8fafc;
  }
  .dock-header p {
    margin: 1px 0 0 0;
    font-size: 11px;
    color: #94a3b8;
  }

  .btn-dock-clear {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 10px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94a3b8;
    font-size: 11.5px;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  .btn-dock-clear:hover {
    background: rgba(244, 63, 94, 0.15);
    border-color: rgba(244, 63, 94, 0.35);
    color: #fda4af;
  }

  /* Target Agent Routing Bar */
  .dock-routing-strip {
    padding: 8px 14px;
    background: rgba(10, 12, 22, 0.65);
    border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .routing-strip-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }
  .routing-lbl {
    font-size: 11px;
    font-weight: 600;
    color: #94a3b8;
  }
  .routing-mode-switch {
    display: inline-flex;
    gap: 4px;
    background: rgba(255, 255, 255, 0.04);
    padding: 2px;
    border-radius: 7px;
  }
  .mode-btn {
    border: none;
    background: transparent;
    color: #94a3b8;
    font-size: 10.5px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 5px;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .mode-btn.active {
    background: rgba(168, 85, 247, 0.28);
    color: #ffffff;
  }

  .agent-mini-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .agent-mini-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #94a3b8;
    font-size: 10.5px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.18s ease;
  }
  .agent-mini-pill.active {
    background: rgba(255, 255, 255, 0.09);
    border-color: var(--pill-color);
    color: #f8fafc;
  }
  .pill-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--pill-color);
    box-shadow: 0 0 6px var(--pill-color);
  }

  /* Chat Messages Feed */
  .dock-chat-messages {
    flex: 1;
    min-height: 0;
    min-width: 0;
    overflow-y: auto;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    scroll-behavior: smooth;
  }

  .dock-msg-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .dock-msg-row.user {
    align-items: flex-end;
  }
  .dock-msg-row.assistant {
    align-items: flex-start;
  }

  .dock-msg-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 10.5px;
    padding: 0 4px;
  }
  .white-cmd-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 1.5px 8px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.16);
    border: 1px solid rgba(255, 255, 255, 0.55);
    color: #ffffff;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 9.5px;
    font-weight: 700;
  }
  .w-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #ffffff;
    box-shadow: 0 0 6px #ffffff;
  }
  .role-label {
    font-weight: 700;
    color: #c084fc;
  }
  .msg-time {
    color: #94a3b8;
  }

  .dock-msg-bubble {
    position: relative;
    max-width: 94%;
    padding: 11px 14px;
    border-radius: 14px;
    font-size: 13px;
    line-height: 1.55;
    color: #f1f5f9;
    background: rgba(22, 26, 42, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.09);
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
  }
  .dock-msg-bubble.assistant {
    border-top-left-radius: 4px;
    border-color: rgba(168, 85, 247, 0.24);
    padding-right: 38px;
  }
  .dock-msg-bubble.user {
    border-top-right-radius: 4px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.14), rgba(99, 102, 241, 0.24));
    border-color: rgba(255, 255, 255, 0.45);
    color: #ffffff;
  }

  .msg-spectrum-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 8px;
    padding-top: 7px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
  }
  .msg-ag-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 1.5px 7px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--chip-color);
    color: #e2e8f0;
    font-size: 10px;
    font-weight: 600;
  }
  .c-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--chip-color);
  }

  .btn-copy-msg {
    position: absolute;
    top: 8px;
    right: 8px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #94a3b8;
    border-radius: 6px;
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    opacity: 0;
    transition: all 0.2s ease;
  }
  .dock-msg-bubble:hover .btn-copy-msg,
  .dock-msg-bubble:focus-within .btn-copy-msg,
  .btn-copy-msg:focus-visible {
    opacity: 1;
  }
  .btn-copy-msg:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
  }
  .btn-copy-msg:focus-visible {
    outline: 2px solid var(--primary, #6366f1);
    outline-offset: 2px;
  }
  @media (hover: none), (pointer: coarse) {
    .btn-copy-msg {
      opacity: 1;
    }
  }

  /* Quick Prompt Chips Bar */
  .dock-quick-prompts {
    padding: 8px 12px;
    background: rgba(10, 12, 20, 0.72);
    border-top: 1px solid rgba(255, 255, 255, 0.07);
  }
  .qp-scroll-row {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;
  }
  .dock-qp-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 9px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.035);
    border: 1px solid rgba(255, 255, 255, 0.09);
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
    transition: all 0.18s ease;
    overflow: hidden;
  }
  .dock-qp-chip:hover:not(:disabled) {
    background: rgba(168, 85, 247, 0.15);
    border-color: rgba(255, 255, 255, 0.4);
    transform: translateY(-1px);
  }
  .qp-ico {
    flex-shrink: 0;
  }
  .qp-lbl {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Bottom Prompt Input Box */
  .dock-input-area {
    padding: 10px 12px 12px;
    background: rgba(9, 11, 18, 0.9);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }
  .dock-input-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border-radius: 13px;
    background: rgba(18, 22, 36, 0.92);
    border: 1px solid rgba(168, 85, 247, 0.3);
    transition: all 0.25s ease;
  }
  .dock-input-box:focus-within,
  .dock-input-box.has-text {
    border-color: rgba(255, 255, 255, 0.65);
    box-shadow: 0 0 18px rgba(255, 255, 255, 0.12), 0 0 24px rgba(168, 85, 247, 0.2);
  }
  .dock-input-box textarea {
    width: 100%;
    background: transparent;
    border: none;
    color: #f8fafc;
    font-family: var(--font-th);
    font-size: 13px;
    line-height: 1.45;
    resize: none;
    min-height: 38px;
    max-height: 110px;
    outline: none;
  }
  .dock-input-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
  .input-hint {
    font-size: 10.5px;
    color: #94a3b8;
  }
  .input-hint strong {
    color: #ffffff;
  }

  .btn-dispatch-beam {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 13px;
    border-radius: 9px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.06);
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
    cursor: not-allowed;
    transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .btn-dispatch-beam.active {
    background: linear-gradient(135deg, #ffffff 0%, #c7d2fe 30%, #818cf8 65%, #a855f7 100%);
    border-color: #ffffff;
    color: #090b10;
    cursor: pointer;
    box-shadow: 0 0 18px rgba(255, 255, 255, 0.45), 0 4px 14px rgba(168, 85, 247, 0.4);
  }
  .btn-dispatch-beam.active:hover {
    transform: translateY(-1px) scale(1.02);
    box-shadow: 0 0 24px rgba(255, 255, 255, 0.7), 0 6px 18px rgba(168, 85, 247, 0.55);
  }

  /* Loading & Typing Indicator */
  .prism-loading-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .typing-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .typing-indicator span {
    width: 6px;
    height: 6px;
    background: #ffffff;
    box-shadow: 0 0 8px #ffffff;
    border-radius: 50%;
    animation: typingPulseWave 1.4s infinite ease-in-out both;
  }
  .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
  .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

  @keyframes typingPulseWave {
    0%, 80%, 100% { transform: scale(0.35); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
  }
  @keyframes pulseOrb {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.85); }
  }

  .loading-label {
    font-size: 11.5px;
    color: #e2e8f0;
  }

  /* Markdown Preview inside Chat Dock */
  :global(.markdown-preview .code-block-wrapper) {
    margin: 8px 0;
    border-radius: 8px;
    overflow: hidden;
    background: #090b10;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }
  :global(.markdown-preview .code-header) {
    background: rgba(255, 255, 255, 0.05);
    padding: 4px 10px;
    font-size: 9.5px;
    font-weight: 700;
    color: #c084fc;
    letter-spacing: 0.08em;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }
  :global(.markdown-preview pre) {
    margin: 0;
    padding: 10px;
    overflow-x: auto;
    font-family: 'Fira Code', 'Courier New', monospace;
    font-size: 12px;
    color: #e6edf3;
  }
  :global(.markdown-preview .inline-code) {
    background: rgba(168, 85, 247, 0.16);
    color: #d8b4fe;
    padding: 1px 5px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 12px;
  }
  :global(.markdown-preview .custom-list) {
    margin: 6px 0;
    padding-left: 18px;
  }
  :global(.markdown-preview .list-item) {
    margin-bottom: 3px;
  }

  @media (prefers-reduced-motion: reduce) {
    .white-photon-stream,
    .spectrum-photon-pulse,
    .cube-orbital-ring,
    .central-prism-cube,
    .secondary-prism.left-prism,
    .secondary-prism.right-prism,
    .shockwave-ring.r1,
    .shockwave-ring.r2,
    .status-dot,
    .typing-indicator span {
      animation: none !important;
    }
  }
</style>
