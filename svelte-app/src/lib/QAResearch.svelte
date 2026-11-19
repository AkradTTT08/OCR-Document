<script>
  import { onMount, afterUpdate, createEventDispatcher } from "svelte";
  import { fade, slide } from "svelte/transition";
  import { toast } from "./toastStore.js";
  import { selectedProjectStore, qaRefinementFeedback } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";

  const dispatch = createEventDispatcher();

  let projects = [];
  $: selectedProjectObj = $selectedProjectStore;

  const RESEARCH_MODES = [
    {
      id: "deep_research",
      label: "Deep QA Research",
      thaiLabel: "วิเคราะห์เอกสารเชิงลึก",
      desc: "สังเคราะห์ข้อมูลจากเอกสารทุกแหล่งและ Cross-Agent พร้อมแหล่งอ้างอิง",
      prompts: [
        "สรุปภาพรวมฟังก์ชันหลัก กลุ่มผู้ใช้งาน และ Business Flow ทั้งหมดของโครงการนี้",
        "สรุปรายการเอกสารทั้งหมดในโครงการ พร้อมขอบเขตเนื้อหาของแต่ละไฟล์",
        "วิเคราะห์เงื่อนไขการยืนยันตัวตน สิทธิ์ผู้ใช้งาน (Role/Permission) และ Security Validation",
        "สรุปความเชื่อมโยงระหว่าง Requirement หลักและเงื่อนไขทางธุรกิจที่ต้องตรวจสอบ"
      ]
    },
    {
      id: "gap_risk_audit",
      label: "Gap & Risk Audit",
      thaiLabel: "ตรวจหาช่องโหว่และความเสี่ยง",
      desc: "เปรียบเทียบ Requirement, Test Case และผล QA Consult เพื่อหาจุดขัดแย้ง",
      prompts: [
        "เปรียบเทียบ Requirement กับ Test Case และผลตรวจ QA Consult ว่ามีจุดใดขาดหายหรือขัดแย้ง",
        "ระบุความเสี่ยงระดับสูง (High Risk) ที่อาจกระทบกระบวนการธุรกิจของลูกค้า",
        "ตรวจสอบว่ามี Requirement ข้อใดที่ยังขาด Error Handling หรือ Validation Rule ในเอกสาร",
        "สรุปประเด็นที่ต้องประสานงานขอความชัดเจนเพิ่มเติมจาก BA หรือทีมพัฒนา"
      ]
    },
    {
      id: "test_brainstorm",
      label: "Test Scenarios",
      thaiLabel: "ออกแบบกรณีทดสอบ",
      desc: "สร้างชุด Positive, Negative และ Boundary Test Cases จาก Business Rules จริง",
      prompts: [
        "ออกแบบชุด Test Scenarios (Positive, Negative, Boundary) สำหรับฟีเจอร์หลักเป็นตาราง",
        "คิดชุด Negative และ Security Test Cases สำหรับหน้าฟอร์มและการบันทึกข้อมูลสำคัญ",
        "สรุป Acceptance Criteria และ Exit Criteria ที่สำคัญทั้งหมดของโครงการ",
        "เสนอชุด Regression Test ที่ควรทำ Automate สำหรับการทดสอบก่อนปล่อยงาน"
      ]
    },
    {
      id: "impact_analysis",
      label: "Change Impact",
      thaiLabel: "วิเคราะห์ผลกระทบการแก้ไข",
      desc: "ประเมินผลกระทบต่อหน้าจอ Sitemap, API และชุด Test Case เมื่อมีการแก้ไข",
      prompts: [
        "หากแก้ไขเงื่อนไขการเข้าสู่ระบบหรือสิทธิ์ผู้ใช้งาน จะกระทบหน้าจอและ Test Case ใดบ้าง",
        "สรุปความสัมพันธ์ระหว่าง Requirement หน้าจอ Sitemap และชุดการทดสอบหลัก",
        "จัดลำดับความสำคัญของโมดูลที่ต้องรัน Regression Test ด่วนก่อน Release",
        "วิเคราะห์จุดเชื่อมต่อระหว่างโมดูลที่มีความเสี่ยงเกิดผลกระทบต่อเนื่องสูง"
      ]
    },
    {
      id: "quick_lookup",
      label: "Quick Lookup",
      thaiLabel: "ค้นหาข้อเท็จจริงแบบกระชับ",
      desc: "คำตอบสั้นตรงประเด็นเป็นตารางหรือรายการ พร้อมระบุชื่อเอกสารอ้างอิงทันที",
      prompts: [
        "สรุปรายการ API Endpoints หรือหน้าจอสำคัญทั้งหมดที่ระบุในเอกสารเป็นตารางสั้นๆ",
        "แสดงรายการรหัส Requirement ทั้งหมดในโครงการแบบกระชับ",
        "สรุปผลตรวจ QA Consult ล่าสุดและรายการที่ต้องแก้ไขเร่งด่วน",
        "ระบุ URL สภาพแวดล้อมและข้อกำหนดเบื้องต้นของระบบที่มีในเอกสาร"
      ]
    }
  ];

  let researchMode = "deep_research";
  let showSidebar = true;
  let showLedgerDetails = false;
  let knowledgeDocs = [];
  let docSearchQuery = "";
  let knowledgeStats = {
    docs_count: 0,
    reqs_count: 0,
    generated_docs_count: 0,
    audits_count: 0,
    has_diagram: false,
    testcases_count: 0
  };
  let isLoadingKnowledge = false;
  let knowledgeError = null;
  let selectedDocIds = [];

  let messages = [];
  let currentInput = "";
  let isLoading = false;
  let chatContainer;
  let textareaElement;
  let abortController = null;
  let userScrolledUp = false;
  let copiedIndex = null;
  let lastLoadedProjectId = null;

  // Safe Clear Confirmation & Undo Buffer
  let confirmClearPending = false;
  let undoBufferMessages = null;
  let undoTimer = null;

  // Interactive Source & Citation Inspector
  let expandedSourcesMsgIdx = {};
  let inspectedSource = null;

  // Speech Recognition (Bilingual TH / EN)
  let isListening = false;
  let speechLang = "th-TH";
  let recognition;
  let originalInput = "";

  $: activeModeObj = RESEARCH_MODES.find(m => m.id === researchMode) || RESEARCH_MODES[0];
  $: filteredKnowledgeDocs = (knowledgeDocs || []).filter(d => {
    if (!docSearchQuery.trim()) return true;
    const q = docSearchQuery.toLowerCase();
    return (
      (d.filename || "").toLowerCase().includes(q) ||
      (d.category || "").toLowerCase().includes(q)
    );
  });
  $: hasConversation = messages.length > 0;
  $: isEmptyKnowledge =
    !isLoadingKnowledge &&
    !knowledgeError &&
    knowledgeStats.docs_count === 0 &&
    knowledgeStats.reqs_count === 0 &&
    knowledgeStats.generated_docs_count === 0 &&
    knowledgeStats.audits_count === 0;

  function getHistoryStorageKey(pid) {
    return `spectra_qa_research_v2_${pid}`;
  }

  function saveChatHistory(pid, msgs) {
    if (!pid || typeof window === "undefined") return;
    try {
      // Never persist transient error placeholders into localStorage
      const clean = (msgs || []).filter(m => !m.isError).slice(-30);
      localStorage.setItem(getHistoryStorageKey(pid), JSON.stringify(clean));
    } catch (e) {}
  }

  function loadChatHistory(proj) {
    const pid = proj?.id || proj?.project_id;
    if (!pid || typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem(getHistoryStorageKey(pid));
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) return parsed.filter(m => !m.isError);
      }
    } catch (e) {}
    return [];
  }

  $: if (selectedProjectObj) {
    const pid = selectedProjectObj.id || selectedProjectObj.project_id;
    if (pid && pid !== lastLoadedProjectId) {
      lastLoadedProjectId = pid;
      selectedDocIds = [];
      docSearchQuery = "";
      confirmClearPending = false;
      undoBufferMessages = null;
      inspectedSource = null;
      messages = loadChatHistory(selectedProjectObj);
      loadKnowledgeOverview(pid);
      setTimeout(() => scrollToBottom(true), 60);
    }
  }

  async function loadKnowledgeOverview(projectId) {
    isLoadingKnowledge = true;
    knowledgeError = null;
    try {
      const res = await fetch(`/api/research/knowledge-overview?project_id=${projectId}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.success) {
        knowledgeDocs = data.documents || [];
        knowledgeStats = data.stats || knowledgeStats;
      } else {
        throw new Error(data.error || "ไม่สามารถโหลดข้อมูลฐานความรู้ได้");
      }
    } catch (err) {
      console.warn("Failed to load research knowledge overview:", err);
      knowledgeError = "ไม่สามารถดึงดัชนีเอกสารของโครงการได้ในขณะนี้";
    } finally {
      isLoadingKnowledge = false;
    }
  }

  function toggleDocScope(docId) {
    if (selectedDocIds.includes(docId)) {
      selectedDocIds = selectedDocIds.filter(id => id !== docId);
    } else {
      selectedDocIds = [...selectedDocIds, docId];
    }
  }

  function selectAllFilteredDocs() {
    const allIds = filteredKnowledgeDocs.map(d => d.doc_id);
    selectedDocIds = Array.from(new Set([...selectedDocIds, ...allIds]));
  }

  function requestClearSession() {
    if (!hasConversation) return;
    if (!confirmClearPending) {
      confirmClearPending = true;
      setTimeout(() => { confirmClearPending = false; }, 4500);
      return;
    }
    confirmClearPending = false;
    const pid = selectedProjectObj?.id || selectedProjectObj?.project_id;
    undoBufferMessages = [...messages];
    messages = [];
    inspectedSource = null;
    saveChatHistory(pid, []);
    if (undoTimer) clearTimeout(undoTimer);
    undoTimer = setTimeout(() => { undoBufferMessages = null; }, 7000);
    toast("ล้างประวัติเซสชันแล้ว (สามารถกดกู้คืนได้ภายใน 7 วินาที)", "info");
  }

  function undoClearSession() {
    if (!undoBufferMessages || !selectedProjectObj) return;
    const pid = selectedProjectObj.id || selectedProjectObj.project_id;
    messages = [...undoBufferMessages];
    undoBufferMessages = null;
    if (undoTimer) clearTimeout(undoTimer);
    saveChatHistory(pid, messages);
    toast("กู้คืนประวัติการค้นคว้าเรียบร้อยแล้ว", "success");
  }

  function exportResearchMarkdown() {
    if (!messages.length) {
      toast("ยังไม่มีบทสนทนาสำหรับส่งออก", "warning");
      return;
    }
    const pCode = selectedProjectObj?.project_code || "PROJECT";
    const pName = selectedProjectObj?.name || selectedProjectObj?.project_name || "";
    const lines = [
      `# QA Research Brief — ${pCode} ${pName}`,
      `> Mode: ${activeModeObj.label} | Generated: ${new Date().toLocaleString("th-TH")}`,
      ""
    ];
    for (const m of messages.filter(x => !x.isError)) {
      lines.push(m.role === "user" ? `## Query\n\n${m.content}\n` : `## Research Findings (${getModeLabel(m.mode)})\n\n${m.content}\n`);
      if (m.sources?.sources?.length) {
        lines.push(`**Sources Referenced:** ${m.sources.sources.map(s => s.name).join(", ")}\n`);
      }
      lines.push("---\n");
    }
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `QA_Research_${pCode}_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
    toast("ส่งออกรายงาน QA Research (.md) เรียบร้อยแล้ว", "success");
  }

  function sendInsightToDocCreation(msg) {
    const pid = selectedProjectObj?.id || selectedProjectObj?.project_id;
    const pName = selectedProjectObj?.name || selectedProjectObj?.project_name || "Project";
    // Use the message's own mode rather than the currently selected lens
    const msgMode = msg?.mode || researchMode;
    const modeLabel = getModeLabel(msgMode);
    const isTestCaseMode = msgMode === "test_brainstorm";
    const payload = {
      project_id: pid,
      project_name: pName,
      doc_type: isTestCaseMode ? "TestCase" : "SRS",
      group_name: `QA Research (${modeLabel})`,
      group_type: isTestCaseMode ? "Test Case" : "SRS",
      source_filename: `QA_Research_${msgMode}.md`,
      findings: [
        {
          severity: "Info",
          category: `QA Research (${modeLabel})`,
          issue: "สรุปผลการวิเคราะห์จาก QA Research",
          recommendation: (msg?.content || "").slice(0, 1200)
        }
      ],
      raw_markdown: msg?.content || ""
    };
    qaRefinementFeedback.set(payload);
    dispatch("navigate", { view: "qa_doc_creation", feedback: payload });
    toast(`ส่งผลวิเคราะห์ (${modeLabel}) ไปยัง QA Document Creation แล้ว`, "success");
  }

  function sendInsightToAutomation(msg) {
    const pid = selectedProjectObj?.id || selectedProjectObj?.project_id;
    const pName = selectedProjectObj?.name || selectedProjectObj?.project_name || "Project";
    const msgMode = msg?.mode || researchMode;
    qaRefinementFeedback.set({
      project_id: pid,
      project_name: pName,
      source: "qa_research",
      mode: msgMode,
      raw_markdown: msg?.content || ""
    });
    dispatch("navigate", { view: "qa_automate" });
    toast("ส่งบริบทผลวิจัยไปยัง QA Test Automation แล้ว", "success");
  }

  function navigateToAgent(viewName) {
    dispatch("navigate", { view: viewName });
  }

  function handleInspectSource(src) {
    inspectedSource = inspectedSource?.name === src.name ? null : src;
  }

  function filterToInspectedDocument(src) {
    const match = knowledgeDocs.find(d => d.filename === src.name);
    if (match) {
      selectedDocIds = [match.doc_id];
      inspectedSource = null;
      toast(`จำกัดขอบเขตการค้นหาเฉพาะไฟล์ "${match.filename}" แล้ว`, "info");
    } else {
      navigateToAgent("kb");
    }
  }

  function handleCanvasClick(e) {
    // Handle per-block Copy Code button clicks
    const copyBtn = e.target.closest?.(".btn-copy-code-block");
    if (copyBtn) {
      const wrapper = copyBtn.closest(".code-block-wrapper");
      const codeEl = wrapper?.querySelector("pre code");
      if (codeEl) {
        navigator.clipboard.writeText(codeEl.textContent || "").then(() => {
          const orig = copyBtn.textContent;
          copyBtn.textContent = "คัดลอกแล้ว";
          toast("คัดลอกโค้ดลง Clipboard แล้ว", "success");
          setTimeout(() => { copyBtn.textContent = orig; }, 1800);
        }).catch(() => toast("ไม่สามารถคัดลอกโค้ดได้", "error"));
      }
      return;
    }

    // Handle clickable citation pills ([REQ-001], [TC-01], [อ้างอิง:...])
    const citBtn = e.target.closest?.(".citation-pill");
    if (citBtn) {
      const citText = (citBtn.textContent || "").trim();
      if (citText && !isLoading) {
        currentInput = `ช่วยเจาะลึกรายละเอียดและเงื่อนไขทั้งหมดของ ${citText} พร้อมระบุข้อความอ้างอิงจากเอกสารต้นฉบับ`;
        textareaElement?.focus();
        toast(`เตรียมคำถามเจาะลึกสำหรับ ${citText} ในช่องพิมพ์แล้ว`, "info");
      }
    }
  }

  function handleGlobalKeydown(e) {
    if (e.key === "Escape") {
      if (inspectedSource) {
        inspectedSource = null;
      } else if (typeof window !== "undefined" && window.innerWidth <= 900 && showSidebar) {
        showSidebar = false;
      }
    }
  }

  onMount(async () => {
    if (typeof window !== "undefined" && window.innerWidth <= 1180) {
      showSidebar = false;
    }

    try {
      const resProjects = await fetch("/api/projects");
      if (resProjects.ok) {
        const pData = await resProjects.json();
        projects = pData.projects || [];
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognition = new SpeechRecognition();
      recognition.lang = speechLang;
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        isListening = true;
      };
      recognition.onresult = (event) => {
        let interimTranscript = "";
        let finalTranscript = "";
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
        isListening = false;
        if (event?.error && event.error !== "no-speech" && event.error !== "aborted") {
          toast(`ระบบรับเสียงขัดข้อง (${event.error}) กรุณาตรวจสอบสิทธิ์ไมโครโฟน`, "warning");
        }
      };
      recognition.onend = () => {
        isListening = false;
      };
    }
  });

  function toggleSpeechLang() {
    speechLang = speechLang === "th-TH" ? "en-US" : "th-TH";
    if (recognition) recognition.lang = speechLang;
    toast(`เปลี่ยนภาษาการรับเสียงเป็น ${speechLang === "th-TH" ? "ภาษาไทย (TH)" : "English (EN)"}`, "info");
  }

  function handleScroll() {
    if (!chatContainer) return;
    const distanceToBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight;
    userScrolledUp = distanceToBottom > 60;
  }

  function scrollToBottom(force = false) {
    if (chatContainer && (force || !userScrolledUp)) {
      chatContainer.scrollTop = chatContainer.scrollHeight;
      if (force) userScrolledUp = false;
    }
  }

  afterUpdate(() => {
    if (isLoading && !userScrolledUp) {
      scrollToBottom();
    }
  });

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  function toggleListen() {
    if (!recognition) {
      toast("เบราว์เซอร์ของคุณไม่รองรับการสั่งงานด้วยเสียง (แนะนำ Google Chrome)", "warning");
      return;
    }
    if (isListening) {
      recognition.stop();
    } else {
      recognition.lang = speechLang;
      originalInput = currentInput.trim();
      recognition.start();
    }
  }

  function handleKeydown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) sendMessage();
    }
  }

  function resizeTextarea() {
    if (textareaElement) {
      textareaElement.style.height = "auto";
      textareaElement.style.height = Math.min(textareaElement.scrollHeight, 150) + "px";
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
      toast("คัดลอกเนื้อหาลง Clipboard แล้ว", "success");
      setTimeout(() => { copiedIndex = null; }, 2000);
    } catch (err) {
      toast("ไม่สามารถคัดลอกข้อความได้", "error");
    }
  }

  function formatTime(ts) {
    if (!ts) return "";
    try {
      return new Date(ts).toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  }

  function getModeLabel(modeId) {
    const found = RESEARCH_MODES.find(m => m.id === modeId);
    return found ? found.label : "Deep QA Research";
  }

  // Full, Safe Markdown Renderer supporting Headings, Tables, Lists, Code Blocks (+Copy), Blockquotes & Interactive Citations
  function renderInline(str) {
    return str
      .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(
        /\[(อ้างอิง:[^\]]+|ความต้องการ:[^\]]+|REQ-[A-Za-z0-9\-]+|TC-[A-Za-z0-9\-]+|API-[A-Za-z0-9\-]+|US-[A-Za-z0-9\-]+|BUG-[A-Za-z0-9\-]+)\]/g,
        '<button type="button" class="citation-pill" title="คลิกเพื่อเจาะลึกข้อมูลอ้างอิงนี้">$1</button>'
      );
  }

  function renderFormattedText(text) {
    if (!text) return "";

    const codeBlocks = [];
    let working = text.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const idx = codeBlocks.length;
      const safeCode = code.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").trim();
      codeBlocks.push(
        `<div class="code-block-wrapper"><div class="code-header"><span>${lang || "CODE"}</span><button type="button" class="btn-copy-code-block">คัดลอกโค้ด</button></div><pre><code>${safeCode}</code></pre></div>`
      );
      return `@@CODEBLOCK_${idx}@@`;
    });

    working = working.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

    const lines = working.split("\n");
    const out = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      const cbMatch = trimmed.match(/^@@CODEBLOCK_(\d+)@@$/);
      if (cbMatch) {
        out.push(codeBlocks[Number(cbMatch[1])]);
        i++;
        continue;
      }

      if (!trimmed) {
        i++;
        continue;
      }

      const hMatch = trimmed.match(/^(#{1,4})\s+(.*)$/);
      if (hMatch) {
        const level = Math.min(4, hMatch[1].length + 1);
        out.push(`<h${level} class="md-heading md-h${hMatch[1].length}">${renderInline(hMatch[2])}</h${level}>`);
        i++;
        continue;
      }

      if (/^---+$/.test(trimmed)) {
        out.push('<hr class="md-hr" />');
        i++;
        continue;
      }

      if (trimmed.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(lines[i + 1].trim())) {
        const headerCells = trimmed.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
        i += 2;
        const bodyRows = [];
        while (i < lines.length && lines[i].trim().includes("|")) {
          const cells = lines[i].trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
          bodyRows.push(cells);
          i++;
        }
        const thHtml = headerCells.map(c => `<th>${renderInline(c)}</th>`).join("");
        const trHtml = bodyRows
          .map(row => `<tr>${row.map(c => `<td>${renderInline(c)}</td>`).join("")}</tr>`)
          .join("");
        out.push(`<div class="md-table-wrap"><table class="md-table"><thead><tr>${thHtml}</tr></thead><tbody>${trHtml}</tbody></table></div>`);
        continue;
      }

      if (trimmed.startsWith("&gt;")) {
        const qLines = [];
        while (i < lines.length && lines[i].trim().startsWith("&gt;")) {
          qLines.push(renderInline(lines[i].trim().replace(/^&gt;\s?/, "")));
          i++;
        }
        out.push(`<blockquote class="md-quote">${qLines.join("<br/>")}</blockquote>`);
        continue;
      }

      if (/^[-*•]\s+/.test(trimmed)) {
        const items = [];
        while (i < lines.length && /^[-*•]\s+/.test(lines[i].trim())) {
          items.push(`<li class="list-item">${renderInline(lines[i].trim().replace(/^[-*•]\s+/, ""))}</li>`);
          i++;
        }
        out.push(`<ul class="custom-list">${items.join("")}</ul>`);
        continue;
      }

      if (/^\d+\.\s+/.test(trimmed)) {
        const items = [];
        while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
          items.push(`<li class="list-item">${renderInline(lines[i].trim().replace(/^\d+\.\s+/, ""))}</li>`);
          i++;
        }
        out.push(`<ol class="custom-olist">${items.join("")}</ol>`);
        continue;
      }

      const pLines = [];
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        !/^(#{1,4})\s+/.test(lines[i].trim()) &&
        !/^[-*•]\s+/.test(lines[i].trim()) &&
        !/^\d+\.\s+/.test(lines[i].trim()) &&
        !lines[i].trim().startsWith("&gt;") &&
        !/^@@CODEBLOCK_(\d+)@@$/.test(lines[i].trim())
      ) {
        if (lines[i].trim().includes("|") && i + 1 < lines.length && /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(lines[i + 1].trim())) {
          break;
        }
        pLines.push(renderInline(lines[i].trim()));
        i++;
      }
      if (pLines.length) {
        out.push(`<p class="md-para">${pLines.join("<br/>")}</p>`);
      }
    }

    return out.join("");
  }

  function decodeBase64Utf8(b64) {
    try {
      const bin = atob(b64);
      const bytes = Uint8Array.from(bin, c => c.charCodeAt(0));
      return JSON.parse(new TextDecoder("utf-8").decode(bytes));
    } catch (e) {
      return null;
    }
  }

  let hasReceivedFirstChunk = false;

  async function retryFailedMessage(errIndex, originalQuery) {
    if (isLoading || !originalQuery) return;
    // Remove the error bubble before retrying
    messages = messages.filter((_, idx) => idx !== errIndex);
    await executeResearchQuery(originalQuery, true);
  }

  async function sendMessage() {
    if (!currentInput.trim() || isLoading) return;
    const userMsg = currentInput.trim();
    currentInput = "";
    await executeResearchQuery(userMsg, false);
  }

  async function executeResearchQuery(userMsg, isRetry = false) {
    const projectId = selectedProjectObj.id || selectedProjectObj.project_id;
    const nowTs = Date.now();
    const activeModeAtSend = researchMode;

    if (!isRetry) {
      messages = [...messages, { role: "user", content: userMsg, mode: activeModeAtSend, timestamp: nowTs }];
      saveChatHistory(projectId, messages);
    }

    isLoading = true;
    hasReceivedFirstChunk = false;
    userScrolledUp = false;
    setTimeout(() => scrollToBottom(true), 50);
    abortController = new AbortController();

    const timeoutId = setTimeout(() => {
      if (abortController && isLoading && !hasReceivedFirstChunk) {
        abortController.abort();
        toast("การเชื่อมต่อใช้เวลานานเกินไป กรุณาลองส่งคำถามใหม่อีกครั้ง", "warning");
      }
    }, 90000);

    try {
      // Exclude any error entries from conversation history sent to LLM
      const cleanHistory = messages
        .filter(m => !m.isError)
        .slice(-11, -1)
        .map(m => ({ role: m.role, content: m.content }));

      const response = await fetch("/api/research/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortController.signal,
        body: JSON.stringify({
          project_id: projectId,
          message: userMsg,
          research_mode: activeModeAtSend,
          doc_ids: selectedDocIds,
          history: cleanHistory
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.error || `HTTP Error: ${response.status}`);
      }

      const rawSourcesHeader = response.headers.get("X-Research-Sources");
      const retrievedSources = rawSourcesHeader ? decodeBase64Utf8(rawSourcesHeader) : null;

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const textChunk = decoder.decode(value, { stream: true });
        if (!textChunk) continue;

        if (!hasReceivedFirstChunk) {
          hasReceivedFirstChunk = true;
          messages = [
            ...messages,
            {
              role: "assistant",
              content: textChunk,
              mode: activeModeAtSend,
              sources: retrievedSources,
              timestamp: Date.now(),
              isStreaming: true
            }
          ];
        } else {
          messages[messages.length - 1].content += textChunk;
          messages = [...messages];
        }

        if (!userScrolledUp) {
          scrollToBottom();
        }
      }

      if (messages.length > 0 && messages[messages.length - 1].isStreaming) {
        messages[messages.length - 1].isStreaming = false;
        messages = [...messages];
      }
      saveChatHistory(projectId, messages);
    } catch (err) {
      if (err.name === "AbortError") {
        toast("ยกเลิกการสืบค้นข้อมูลแล้ว", "info");
        if (!hasReceivedFirstChunk && !isRetry) {
          currentInput = userMsg;
          messages = messages.slice(0, -1);
          saveChatHistory(projectId, messages);
        } else if (messages.length > 0 && messages[messages.length - 1].isStreaming) {
          messages[messages.length - 1].isStreaming = false;
          messages = [...messages];
          saveChatHistory(projectId, messages);
        }
      } else {
        toast(`เกิดข้อผิดพลาด: ${err.message}`, "error");
        if (!hasReceivedFirstChunk) {
          messages = [
            ...messages,
            {
              role: "assistant",
              content: `ไม่สามารถเชื่อมต่อระบบสืบค้นได้ในขณะนี้ (${err.message})`,
              mode: activeModeAtSend,
              sources: null,
              timestamp: Date.now(),
              isError: true,
              originalQuery: userMsg
            }
          ];
        }
      }
    } finally {
      clearTimeout(timeoutId);
      isLoading = false;
      hasReceivedFirstChunk = false;
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

<svelte:window on:keydown={handleGlobalKeydown} />

<div class="research-shell" in:fade={{ duration: 160 }}>
  {#if !selectedProjectObj}
    <div class="project-select-wrap">
      <ProjectSelection
        {projects}
        on:select={(e) => selectProject(e.detail)}
      />
    </div>
  {:else}
    <!-- Mobile Backdrop Scrim for Drawer -->
    {#if showSidebar}
      <button
        type="button"
        class="mobile-drawer-backdrop"
        aria-label="ปิดแถบเครื่องมือ"
        on:click={() => (showSidebar = false)}
      ></button>
    {/if}

    <!-- Left Inspector Rail -->
    {#if showSidebar}
      <aside class="inspector-rail" aria-label="Research Controls" transition:slide={{ axis: "x", duration: 180 }}>
        <!-- Project Switcher Header -->
        <div class="rail-header">
          <button type="button" class="btn-project-switch" on:click={resetProject} title="เปลี่ยนโครงการ">
            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
            <div class="project-switch-meta">
              <span class="project-code">{selectedProjectObj.project_code}</span>
              <span class="project-name">{selectedProjectObj.name || selectedProjectObj.project_name}</span>
            </div>
          </button>
        </div>

        <div class="rail-scroll">
          <!-- Research Lens Selector -->
          <section class="rail-section">
            <div class="rail-section-head">
              <span>โหมดการวิเคราะห์ (Lens)</span>
            </div>
            <div class="lens-list" role="radiogroup" aria-label="โหมดการวิเคราะห์">
              {#each RESEARCH_MODES as m}
                <button
                  type="button"
                  role="radio"
                  aria-checked={researchMode === m.id}
                  class="lens-btn"
                  class:active={researchMode === m.id}
                  on:click={() => (researchMode = m.id)}
                >
                  <span class="lens-icon" aria-hidden="true">
                    {#if m.id === "deep_research"}
                      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="11" cy="11" r="7"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    {:else if m.id === "gap_risk_audit"}
                      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    {:else if m.id === "test_brainstorm"}
                      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M9 3h6"></path><path d="M10 3v6.5L4.8 18.2A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-2.8L14 9.5V3"></path></svg>
                    {:else if m.id === "impact_analysis"}
                      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
                    {:else}
                      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                    {/if}
                  </span>
                  <div class="lens-copy">
                    <span class="lens-title">{m.label}</span>
                    <span class="lens-sub">{m.thaiLabel}</span>
                  </div>
                </button>
              {/each}
            </div>
          </section>

          <!-- Collapsible Indexed Knowledge Ledger (keeps Document Scope above the fold) -->
          <section class="rail-section">
            <div class="rail-section-head">
              <button
                type="button"
                class="ledger-toggle-head"
                aria-expanded={showLedgerDetails}
                on:click={() => (showLedgerDetails = !showLedgerDetails)}
              >
                <span>ดัชนีฐานความรู้</span>
                <svg class="chevron-icon" class:open={showLedgerDetails} viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </button>
              <button
                type="button"
                class="rail-inline-btn"
                on:click={() => loadKnowledgeOverview(selectedProjectObj.id || selectedProjectObj.project_id)}
                disabled={isLoadingKnowledge}
                title="อัปเดตดัชนีเอกสาร"
                aria-label="อัปเดตดัชนีเอกสาร"
              >
                <svg class:spin-icon={isLoadingKnowledge} viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
              </button>
            </div>

            {#if knowledgeError}
              <div class="kb-error-banner">
                <span>{knowledgeError}</span>
                <button type="button" class="rail-inline-btn" on:click={() => loadKnowledgeOverview(selectedProjectObj.id || selectedProjectObj.project_id)}>
                  ลองใหม่
                </button>
              </div>
            {:else if !showLedgerDetails}
              <button type="button" class="ledger-compact-summary" on:click={() => (showLedgerDetails = true)}>
                <span>{knowledgeStats.docs_count} เอกสาร · {knowledgeStats.reqs_count} Reqs · {knowledgeStats.audits_count} Audits</span>
                <span class="summary-more">ดูทั้งหมด</span>
              </button>
            {:else}
              <div class="index-ledger" transition:slide={{ duration: 150 }}>
                <div class="ledger-row">
                  <span class="ledger-key">Knowledge Base</span>
                  <span class="ledger-val">{knowledgeStats.docs_count} ไฟล์</span>
                </div>
                <div class="ledger-row">
                  <span class="ledger-key">Requirements</span>
                  <span class="ledger-val">{knowledgeStats.reqs_count} ข้อ</span>
                </div>
                <div class="ledger-row">
                  <span class="ledger-key">QA Documents</span>
                  <span class="ledger-val">{knowledgeStats.generated_docs_count} ฉบับ</span>
                </div>
                <div class="ledger-row">
                  <span class="ledger-key">Consult Audits</span>
                  <span class="ledger-val">{knowledgeStats.audits_count} รอบ</span>
                </div>
                <div class="ledger-row">
                  <span class="ledger-key">System Diagram</span>
                  <span class="ledger-val" class:ok={knowledgeStats.has_diagram}>
                    {knowledgeStats.has_diagram ? "เชื่อมโยงแล้ว" : "ยังไม่พบ"}
                  </span>
                </div>
                <div class="ledger-row">
                  <span class="ledger-key">Test Cases</span>
                  <span class="ledger-val">{knowledgeStats.testcases_count} ข้อ</span>
                </div>
              </div>
            {/if}
          </section>

          <!-- Document Scope Selector -->
          <section class="rail-section rail-docs-section">
            <div class="rail-section-head">
              <span>ขอบเขตเอกสาร ({selectedDocIds.length === 0 ? "ทั้งหมด" : selectedDocIds.length})</span>
              {#if knowledgeDocs.length > 0}
                <div class="scope-quick-actions">
                  {#if selectedDocIds.length > 0}
                    <button type="button" class="rail-inline-btn" on:click={() => (selectedDocIds = [])}>ล้าง</button>
                  {:else}
                    <button type="button" class="rail-inline-btn" on:click={selectAllFilteredDocs}>เลือกทั้งหมด</button>
                  {/if}
                </div>
              {/if}
            </div>

            {#if knowledgeDocs.length > 3}
              <div class="rail-search-wrap">
                <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                <input
                  type="text"
                  bind:value={docSearchQuery}
                  placeholder="กรองชื่อเอกสาร..."
                  class="rail-search-input"
                  aria-label="กรองชื่อเอกสาร"
                />
              </div>
            {/if}

            <div class="doc-scope-list">
              {#if filteredKnowledgeDocs.length === 0}
                <p class="empty-doc-hint">
                  {knowledgeDocs.length === 0 ? "ยังไม่มีเอกสารในโครงการนี้" : "ไม่พบเอกสารที่ตรงกับคำค้นหา"}
                </p>
              {:else}
                {#each filteredKnowledgeDocs as d}
                  <label class="doc-scope-row" class:checked={selectedDocIds.includes(d.doc_id)}>
                    <input
                      type="checkbox"
                      checked={selectedDocIds.includes(d.doc_id)}
                      on:change={() => toggleDocScope(d.doc_id)}
                    />
                    <span class="doc-scope-name" title={d.filename}>{d.filename}</span>
                    <span class="doc-scope-tag">{d.category}</span>
                  </label>
                {/each}
              {/if}
            </div>
            <p class="scope-note">
              การเลือกเอกสารจะจำกัดการค้นหาเฉพาะไฟล์ที่ติ๊ก (ผล QA Consult และ Diagram ยังคงเชื่อมโยงประกอบ)
            </p>
          </section>
        </div>

        <!-- Rail Footer Actions (Safely Separated) -->
        <div class="rail-footer">
          <button type="button" class="rail-footer-btn" on:click={exportResearchMarkdown} disabled={!hasConversation}>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            <span>ส่งออก .md</span>
          </button>
          <button
            type="button"
            class="rail-footer-btn danger-action"
            class:confirming={confirmClearPending}
            on:click={requestClearSession}
            disabled={!hasConversation}
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.75"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path></svg>
            <span>{confirmClearPending ? "ยืนยันล้างแชท?" : "ล้างประวัติ"}</span>
          </button>
        </div>
      </aside>
    {/if}

    <!-- Main Editorial Research Canvas -->
    <main class="research-canvas">
      <!-- Slim Top Utility Bar (Zero redundant sidebar nav duplication) -->
      <header class="canvas-topbar">
        <div class="topbar-left">
          <button
            type="button"
            class="icon-toggle-btn"
            on:click={() => (showSidebar = !showSidebar)}
            title={showSidebar ? "ซ่อนแถบเครื่องมือซ้าย" : "แสดงแถบเครื่องมือซ้าย"}
            aria-label={showSidebar ? "ซ่อนแถบเครื่องมือซ้าย" : "แสดงแถบเครื่องมือซ้าย"}
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.75"><rect x="3" y="3" width="18" height="18" rx="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg>
          </button>

          <div class="topbar-title-group">
            <h1>QA Research</h1>
            <span class="topbar-divider" aria-hidden="true">/</span>
            <span class="topbar-lens-label">{activeModeObj.label}</span>
          </div>

          {#if selectedDocIds.length > 0}
            <span class="scope-indicator">โฟกัส {selectedDocIds.length} เอกสาร</span>
          {/if}
        </div>

        <div class="topbar-right">
          {#if undoBufferMessages}
            <button type="button" class="undo-banner-btn" on:click={undoClearSession} transition:fade={{ duration: 140 }}>
              กู้คืนประวัติที่ล้างไป
            </button>
          {/if}
          {#if !showSidebar}
            <button type="button" class="topbar-utility-btn" on:click={exportResearchMarkdown} disabled={!hasConversation}>
              ส่งออก .md
            </button>
          {/if}
        </div>
      </header>

      <!-- Scrollable Reading Area -->
      <div class="canvas-scroll" bind:this={chatContainer} on:scroll={handleScroll} on:click={handleCanvasClick}>
        <div class="reading-column">
          {#if !hasConversation}
            {#if isEmptyKnowledge}
              <!-- Dedicated Empty Knowledge Onboarding State -->
              <div class="empty-kb-card" in:fade={{ duration: 180 }}>
                <div class="empty-kb-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="12" y1="18" x2="12" y2="12"></line><line x1="9" y1="15" x2="15" y2="15"></line></svg>
                </div>
                <h2>โครงการ {selectedProjectObj.project_code} ยังไม่มีเอกสารในฐานความรู้</h2>
                <p>
                  เพื่อให้การค้นคว้าและอ้างอิงใน QA Research มีความแม่นยำตามเอกสารจริง กรุณาอัปโหลดหรือสแกนเอกสาร (SRS, TOR, Test Case) เข้าสู่คลังข้อมูลของโครงการก่อนเริ่มสอบถาม
                </p>
                <div class="empty-kb-actions">
                  <button type="button" class="btn-primary-cta" on:click={() => navigateToAgent("kb")}>
                    ไปอัปโหลดเอกสารที่ Knowledge Base
                  </button>
                  <button type="button" class="btn-secondary-cta" on:click={() => loadKnowledgeOverview(selectedProjectObj.id || selectedProjectObj.project_id)}>
                    ตรวจสอบดัชนีเอกสารอีกครั้ง
                  </button>
                </div>
              </div>
            {:else}
              <!-- Clean Editorial Launchpad -->
              <div class="launchpad" in:fade={{ duration: 180 }}>
                <div class="launchpad-head">
                  <h2>ค้นคว้าและตรวจสอบข้อมูลโครงการ {selectedProjectObj.project_code}</h2>
                  <p>
                    {activeModeObj.desc} — อ้างอิงตรงจากฐานข้อมูลโครงการ ({knowledgeStats.docs_count} เอกสาร, {knowledgeStats.reqs_count} ข้อกำหนด, {knowledgeStats.audits_count} ผลตรวจ)
                  </p>
                </div>

                <div class="starter-list">
                  {#each activeModeObj.prompts as promptText}
                    <button
                      type="button"
                      class="starter-row"
                      disabled={isLoading}
                      on:click={() => sendPrompt(promptText)}
                    >
                      <span class="starter-text">{promptText}</span>
                      <svg class="starter-arrow" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                    </button>
                  {/each}
                </div>
              </div>
            {/if}
          {:else}
            <!-- Conversation Feed -->
            <div class="feed-list">
              {#each messages as msg, i}
                {#if msg.role === "user"}
                  <article class="query-entry">
                    <div class="query-meta">
                      <span class="entry-author">คำถาม</span>
                      {#if msg.timestamp}
                        <span class="entry-time">{formatTime(msg.timestamp)}</span>
                      {/if}
                    </div>
                    <div class="query-body">{msg.content}</div>
                  </article>
                {:else}
                  <article class="brief-entry" class:error-entry={msg.isError}>
                    <div class="brief-header">
                      <div class="brief-identity">
                        <span class="brief-mark" aria-hidden="true">S</span>
                        <span class="brief-author">Spectra Research</span>
                        <span class="brief-mode-tag">{getModeLabel(msg.mode)}</span>
                        {#if msg.isStreaming}
                          <span class="streaming-badge">กำลังสืบค้น...</span>
                        {/if}
                      </div>
                      {#if msg.timestamp}
                        <span class="entry-time">{formatTime(msg.timestamp)}</span>
                      {/if}
                    </div>

                    <div class="brief-body markdown-preview">
                      {@html renderFormattedText(msg.content)}{#if msg.isStreaming}<span class="stream-cursor" aria-hidden="true"></span>{/if}
                    </div>

                    {#if msg.isError && msg.originalQuery}
                      <div class="error-recovery-bar">
                        <button type="button" class="btn-retry-query" on:click={() => retryFailedMessage(i, msg.originalQuery)} disabled={isLoading}>
                          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                          <span>ลองส่งคำถามนี้อีกครั้ง</span>
                        </button>
                      </div>
                    {/if}

                    <!-- Interactive Grounded Sources Strip (No Silent Truncation) -->
                    {#if msg.sources && (msg.sources.sources?.length > 0 || msg.sources.chunks_matched > 0)}
                      {@const allSources = msg.sources.sources || []}
                      {@const isExpanded = !!expandedSourcesMsgIdx[i]}
                      {@const visibleSources = isExpanded ? allSources : allSources.slice(0, 6)}
                      <div class="sources-strip">
                        <span class="sources-label">
                          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                          แหล่งอ้างอิง ({allSources.length} แหล่ง · {msg.sources.chunks_matched || 0} ส่วนข้อความ) — คลิกเพื่อดูรายละเอียด
                        </span>
                        <div class="sources-list">
                          {#each visibleSources as src}
                            <button
                              type="button"
                              class="source-tag type-{src.type}"
                              class:active={inspectedSource?.name === src.name}
                              on:click={() => handleInspectSource(src)}
                            >
                              {src.name}
                            </button>
                          {/each}
                          {#if allSources.length > 6}
                            <button
                              type="button"
                              class="source-tag more-toggle"
                              on:click={() => { expandedSourcesMsgIdx = { ...expandedSourcesMsgIdx, [i]: !isExpanded }; }}
                            >
                              {isExpanded ? "ย่อรายการ" : `+${allSources.length - 6} เพิ่มเติม`}
                            </button>
                          {/if}
                        </div>

                        {#if inspectedSource && allSources.some(s => s.name === inspectedSource.name)}
                          <div class="source-inspector-popover" transition:slide={{ duration: 140 }}>
                            <div class="inspector-pop-info">
                              <strong>{inspectedSource.name}</strong>
                              <span>หมวดหมู่: {inspectedSource.category || inspectedSource.type}</span>
                            </div>
                            <div class="inspector-pop-actions">
                              {#if inspectedSource.type === "document"}
                                <button type="button" class="pop-action-btn" on:click={() => filterToInspectedDocument(inspectedSource)}>
                                  จำกัดการค้นหาเฉพาะไฟล์นี้
                                </button>
                              {:else if inspectedSource.type === "diagram"}
                                <button type="button" class="pop-action-btn" on:click={() => navigateToAgent("qa_analysis_diagram")}>
                                  เปิดผัง QA Diagram
                                </button>
                              {:else if inspectedSource.type === "qa_consult"}
                                <button type="button" class="pop-action-btn" on:click={() => navigateToAgent("qa_consult")}>
                                  เปิดผลตรวจ QA Consult
                                </button>
                              {/if}
                              <button type="button" class="pop-close-btn" on:click={() => (inspectedSource = null)} aria-label="ปิด">✕</button>
                            </div>
                          </div>
                        {/if}
                      </div>
                    {/if}

                    <!-- Understated Action Row -->
                    {#if msg.content && !msg.isError && !msg.isStreaming}
                      <div class="brief-actions">
                        <button
                          type="button"
                          class="brief-action-btn"
                          on:click={() => copyToClipboard(msg.content, i)}
                        >
                          {#if copiedIndex === i}
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>
                            <span>คัดลอกแล้ว</span>
                          {:else}
                            <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75"><rect x="9" y="9" width="13" height="13" rx="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                            <span>คัดลอก</span>
                          {/if}
                        </button>

                        <button
                          type="button"
                          class="brief-action-btn"
                          on:click={() => sendInsightToDocCreation(msg)}
                        >
                          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="12" y1="18" x2="12" y2="12"></line><line x1="9" y1="15" x2="15" y2="15"></line></svg>
                          <span>ส่งไปสร้างเอกสาร</span>
                        </button>

                        <button
                          type="button"
                          class="brief-action-btn"
                          on:click={() => sendInsightToAutomation(msg)}
                        >
                          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.75"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
                          <span>ส่งต่อไปวางแผน Automate</span>
                        </button>
                      </div>
                    {/if}
                  </article>
                {/if}
              {/each}

              {#if isLoading && !hasReceivedFirstChunk}
                <article class="brief-entry loading" transition:fade={{ duration: 140 }}>
                  <div class="brief-header">
                    <div class="brief-identity">
                      <span class="brief-mark" aria-hidden="true">S</span>
                      <span class="brief-author">Spectra Research</span>
                      <span class="brief-mode-tag">{activeModeObj.label}</span>
                    </div>
                  </div>
                  <div class="loading-row">
                    <span class="status-pulse" aria-hidden="true"></span>
                    <span class="loading-copy">กำลังสืบค้นคลังเอกสารและประมวลผลคำตอบ...</span>
                    <button type="button" class="btn-abort-text" on:click={cancelMessage}>ยกเลิก</button>
                  </div>
                </article>
              {/if}
            </div>
          {/if}
        </div>
      </div>

      <!-- Jump-to-Latest Pill when user scrolled up -->
      {#if userScrolledUp && hasConversation}
        <div class="jump-latest-wrap" transition:fade={{ duration: 140 }}>
          <button type="button" class="btn-jump-latest" on:click={() => scrollToBottom(true)}>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
            <span>{isLoading ? "กำลังสตรีมคำตอบ — เลื่อนลงล่างสุด" : "เลื่อนลงล่างสุด"}</span>
          </button>
        </div>
      {/if}

      <!-- Anchored Composer Dock (Editable while streaming so user can draft next query) -->
      <div class="composer-dock">
        <div class="composer-shell">
          <textarea
            bind:this={textareaElement}
            bind:value={currentInput}
            on:keydown={handleKeydown}
            on:input={resizeTextarea}
            placeholder={isListening
              ? `กำลังรับเสียง (${speechLang === "th-TH" ? "ไทย" : "EN"})...`
              : `พิมพ์คำถามเพื่อค้นคว้าในโหมด ${activeModeObj.label}...`}
            rows="1"
          ></textarea>

          <div class="composer-bar">
            <div class="composer-context-tags">
              <span class="ctx-tag">{activeModeObj.thaiLabel}</span>
              <span class="ctx-sep" aria-hidden="true">·</span>
              <span class="ctx-tag muted">
                {selectedDocIds.length === 0 ? `ทุกเอกสาร (${knowledgeStats.docs_count})` : `เฉพาะ ${selectedDocIds.length} เอกสาร`}
              </span>
              <span class="ctx-sep hide-sm" aria-hidden="true">·</span>
              <span class="ctx-hint hide-sm">Shift+Enter ขึ้นบรรทัดใหม่</span>
            </div>

            <div class="composer-controls">
              <button
                type="button"
                class="composer-lang-btn"
                on:click={toggleSpeechLang}
                title="สลับภาษาการรับเสียง (ไทย / อังกฤษ)"
              >
                {speechLang === "th-TH" ? "TH" : "EN"}
              </button>

              <button
                type="button"
                class="composer-icon-btn"
                class:listening={isListening}
                on:click={toggleListen}
                disabled={isLoading}
                title="ป้อนคำถามด้วยเสียง"
                aria-label="ป้อนคำถามด้วยเสียง"
              >
                {#if isListening}
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="7" y="7" width="10" height="10" rx="2"></rect></svg>
                {:else}
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
                {/if}
              </button>

              <button
                type="button"
                class="composer-submit-btn"
                class:stop={isLoading}
                on:click={isLoading ? cancelMessage : sendMessage}
                disabled={!isLoading && !currentInput.trim()}
                title={isLoading ? "หยุดสร้างคำตอบ" : "ส่งคำถาม (Enter)"}
                aria-label={isLoading ? "หยุดสร้างคำตอบ" : "ส่งคำถาม"}
              >
                {#if isLoading}
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2"></rect></svg>
                  <span>หยุด</span>
                {:else}
                  <span>ค้นคว้า</span>
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                {/if}
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  {/if}
</div>

<style>
  .research-shell {
    width: 100%;
    height: 100%;
    display: flex;
    position: relative;
    min-height: 0;
    overflow: hidden;
    background: #141928;
    color: #f8fafc;
    font-family: "Prompt", "Inter", sans-serif;
  }

  .research-shell ::selection {
    background: rgba(99, 102, 241, 0.38);
    color: #ffffff;
  }

  /* Universal accessible keyboard focus ring */
  .research-shell button:focus-visible,
  .research-shell input[type="checkbox"]:focus-visible {
    outline: 2px solid #818cf8;
    outline-offset: 2px;
  }

  .project-select-wrap {
    width: 100%;
    height: 100%;
    overflow-y: auto;
    padding: 20px 28px;
    box-sizing: border-box;
  }

  .mobile-drawer-backdrop {
    display: none;
  }

  /* ========================================
     LEFT INSPECTOR RAIL (Bright Twilight Slate)
     ======================================== */
  .inspector-rail {
    width: 280px;
    flex-shrink: 0;
    background: #192136;
    border-right: 1px solid rgba(148, 163, 184, 0.2);
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .rail-header {
    padding: 14px 14px 12px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.16);
    flex-shrink: 0;
  }

  .btn-project-switch {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    background: #212b45;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
    padding: 9px 11px;
    color: #e2e8f0;
    cursor: pointer;
    text-align: left;
    transition: background-color 0.16s ease, border-color 0.16s ease;
  }

  .btn-project-switch:hover {
    background: #283454;
    border-color: rgba(129, 140, 248, 0.45);
    color: #ffffff;
  }

  .project-switch-meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .project-code {
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    color: #93c5fd;
  }

  .project-name {
    font-size: 13px;
    font-weight: 500;
    color: #f8fafc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rail-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    scrollbar-width: thin;
    scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
  }

  .rail-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .rail-section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
  }

  .ledger-toggle-head {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: transparent;
    border: none;
    color: #94a3b8;
    font-family: "Prompt", sans-serif;
    font-size: 12px;
    font-weight: 600;
    padding: 0;
    cursor: pointer;
  }

  .ledger-toggle-head:hover {
    color: #f8fafc;
  }

  .chevron-icon {
    transition: transform 0.16s ease;
  }

  .chevron-icon.open {
    transform: rotate(180deg);
  }

  .rail-inline-btn {
    background: transparent;
    border: none;
    color: #cbd5e1;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 6px;
    display: inline-flex;
    align-items: center;
    font-size: 12px;
    font-family: "Prompt", sans-serif;
  }

  .rail-inline-btn:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.1);
  }

  .spin-icon {
    animation: spin360 0.8s linear infinite;
  }

  @keyframes spin360 {
    to { transform: rotate(360deg); }
  }

  /* Research Lens List */
  .lens-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .lens-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid transparent;
    background: transparent;
    color: #cbd5e1;
    cursor: pointer;
    text-align: left;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }

  .lens-btn:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #ffffff;
  }

  .lens-btn.active {
    background: rgba(99, 102, 241, 0.22);
    border-color: rgba(129, 140, 248, 0.48);
    color: #ffffff;
  }

  .lens-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.07);
    color: #cbd5e1;
    flex-shrink: 0;
  }

  .lens-btn.active .lens-icon {
    background: linear-gradient(135deg, #6366f1, #a855f7);
    color: #ffffff;
  }

  .lens-copy {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .lens-title {
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 13px;
    font-weight: 600;
    line-height: 1.25;
  }

  .lens-sub {
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.3;
  }

  .lens-btn.active .lens-sub {
    color: #c7d2fe;
  }

  /* Compact Knowledge Index Summary & Ledger */
  .kb-error-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.35);
    border-radius: 8px;
    font-size: 12px;
    color: #fecdd3;
  }

  .ledger-compact-summary {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 8px 10px;
    background: #212b45;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 8px;
    color: #e2e8f0;
    font-size: 12px;
    font-family: "Prompt", sans-serif;
    font-variant-numeric: tabular-nums;
    cursor: pointer;
    text-align: left;
  }

  .ledger-compact-summary:hover {
    background: #283454;
  }

  .summary-more {
    color: #93c5fd;
    font-weight: 500;
  }

  .index-ledger {
    display: flex;
    flex-direction: column;
    border-top: 1px solid rgba(148, 163, 184, 0.15);
  }

  .ledger-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 2px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    font-size: 12.5px;
  }

  .ledger-key {
    color: #cbd5e1;
    font-family: "Outfit", "Inter", sans-serif;
  }

  .ledger-val {
    color: #f8fafc;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .ledger-val.ok {
    color: #34d399;
  }

  /* Document Scope */
  .rail-search-wrap {
    display: flex;
    align-items: center;
    gap: 7px;
    background: #212b45;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 8px;
    padding: 7px 10px;
    color: #94a3b8;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  .rail-search-wrap:focus-within {
    border-color: #818cf8;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.22);
  }

  .rail-search-input {
    flex: 1;
    background: transparent;
    border: none;
    color: #f8fafc;
    font-size: 12.5px;
    outline: none;
    min-width: 0;
    font-family: "Prompt", sans-serif;
  }

  .rail-search-input::placeholder {
    color: #94a3b8;
  }

  .doc-scope-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 220px;
    overflow-y: auto;
  }

  .doc-scope-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 8px;
    border-radius: 8px;
    border: 1px solid transparent;
    cursor: pointer;
    transition: background-color 0.14s ease;
  }

  .doc-scope-row:hover {
    background: rgba(255, 255, 255, 0.06);
  }

  .doc-scope-row.checked {
    background: rgba(99, 102, 241, 0.2);
    border-color: rgba(129, 140, 248, 0.42);
  }

  .doc-scope-row input {
    accent-color: #6366f1;
    flex-shrink: 0;
  }

  .doc-scope-name {
    flex: 1;
    font-size: 12.5px;
    color: #e2e8f0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .doc-scope-tag {
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 12px;
    font-weight: 500;
    color: #94a3b8;
    flex-shrink: 0;
  }

  .empty-doc-hint,
  .scope-note {
    margin: 2px 0 0;
    font-size: 12px;
    color: #94a3b8;
    line-height: 1.45;
  }

  /* Rail Footer */
  .rail-footer {
    padding: 12px 14px;
    border-top: 1px solid rgba(148, 163, 184, 0.16);
    display: flex;
    justify-content: space-between;
    gap: 8px;
    flex-shrink: 0;
  }

  .rail-footer-btn {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: #212b45;
    border: 1px solid rgba(148, 163, 184, 0.22);
    color: #e2e8f0;
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-family: "Prompt", sans-serif;
    cursor: pointer;
    transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
  }

  .rail-footer-btn:hover:not(:disabled) {
    background: #2a3759;
    color: #ffffff;
  }

  .rail-footer-btn.danger-action:hover:not(:disabled) {
    background: rgba(244, 63, 94, 0.16);
    border-color: rgba(244, 63, 94, 0.45);
    color: #fecdd3;
  }

  .rail-footer-btn.confirming {
    background: #e11d48;
    border-color: #fb7185;
    color: #ffffff;
    font-weight: 600;
  }

  .rail-footer-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  /* ========================================
     MAIN EDITORIAL RESEARCH CANVAS
     ======================================== */
  .research-canvas {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    min-height: 0;
    position: relative;
    background: radial-gradient(ellipse at 65% 0%, rgba(99, 102, 241, 0.13), transparent 58%), #141928;
  }

  .canvas-topbar {
    height: 52px;
    padding: 0 20px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
    background: rgba(25, 33, 54, 0.88);
  }

  .topbar-left,
  .topbar-right {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .icon-toggle-btn {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: #212b45;
    border: 1px solid rgba(148, 163, 184, 0.22);
    color: #cbd5e1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .icon-toggle-btn:hover {
    background: #2b3859;
    color: #ffffff;
  }

  .topbar-title-group {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .topbar-title-group h1 {
    margin: 0;
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
  }

  .topbar-divider {
    color: #94a3b8;
  }

  .topbar-lens-label {
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 13.5px;
    font-weight: 500;
    color: #cbd5e1;
  }

  .scope-indicator {
    font-size: 12px;
    color: #c7d2fe;
    background: rgba(99, 102, 241, 0.22);
    border: 1px solid rgba(129, 140, 248, 0.4);
    padding: 2px 10px;
    border-radius: 20px;
  }

  .undo-banner-btn {
    background: rgba(245, 158, 11, 0.18);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: #fde68a;
    padding: 5px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    font-family: "Prompt", sans-serif;
    cursor: pointer;
  }

  .topbar-utility-btn {
    background: #212b45;
    border: 1px solid rgba(148, 163, 184, 0.22);
    color: #e2e8f0;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-family: "Prompt", sans-serif;
    cursor: pointer;
  }

  /* Reading Scroll Column */
  .canvas-scroll {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
    padding: 28px 24px 24px;
    scrollbar-width: thin;
    scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
  }

  .reading-column {
    max-width: 820px;
    margin: 0 auto;
    width: 100%;
  }

  /* Empty Knowledge Onboarding State */
  .empty-kb-card {
    margin-top: 48px;
    padding: 32px;
    background: #1b243b;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 20px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }

  .empty-kb-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(129, 140, 248, 0.38);
    color: #a5b4fc;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .empty-kb-card h2 {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: #ffffff;
  }

  .empty-kb-card p {
    margin: 0;
    font-size: 14px;
    color: #cbd5e1;
    line-height: 1.65;
    max-width: 64ch;
  }

  .empty-kb-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 6px;
  }

  .btn-primary-cta {
    background: linear-gradient(135deg, #6366f1, #a855f7);
    border: none;
    color: #ffffff;
    padding: 10px 20px;
    border-radius: 12px;
    font-family: "Prompt", sans-serif;
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-secondary-cta {
    background: #232f4d;
    border: 1px solid rgba(148, 163, 184, 0.28);
    color: #e2e8f0;
    padding: 10px 18px;
    border-radius: 12px;
    font-family: "Prompt", sans-serif;
    font-size: 13.5px;
    cursor: pointer;
  }

  /* Launchpad Empty State */
  .launchpad {
    padding-top: 38px;
    display: flex;
    flex-direction: column;
    gap: 26px;
  }

  .launchpad-head h2 {
    margin: 0 0 8px;
    font-size: 26px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: -0.02em;
    line-height: 1.3;
  }

  .launchpad-head p {
    margin: 0;
    font-size: 14.5px;
    color: #cbd5e1;
    line-height: 1.6;
    max-width: 68ch;
  }

  .starter-list {
    display: flex;
    flex-direction: column;
    background: #1b243b;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 12px;
    overflow: hidden;
  }

  .starter-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    padding: 15px 16px;
    background: transparent;
    border: none;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    color: #e2e8f0;
    font-family: "Prompt", sans-serif;
    font-size: 14px;
    text-align: left;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease, padding-left 0.15s ease;
  }

  .starter-row:last-child {
    border-bottom: none;
  }

  .starter-row:hover:not(:disabled) {
    background: rgba(99, 102, 241, 0.16);
    color: #ffffff;
    padding-left: 20px;
  }

  .starter-arrow {
    color: #94a3b8;
    flex-shrink: 0;
    transition: transform 0.15s ease, color 0.15s ease;
  }

  .starter-row:hover .starter-arrow {
    color: #a5b4fc;
    transform: translateX(3px);
  }

  /* Editorial Conversation Feed */
  .feed-list {
    display: flex;
    flex-direction: column;
    gap: 26px;
  }

  .query-entry {
    padding: 14px 18px;
    background: #1f2a44;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
  }

  .query-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .entry-author {
    font-size: 12px;
    font-weight: 600;
    color: #93c5fd;
  }

  .entry-time {
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 12px;
    color: #94a3b8;
    font-variant-numeric: tabular-nums;
  }

  .query-body {
    font-size: 14.5px;
    color: #ffffff;
    line-height: 1.6;
    white-space: pre-wrap;
  }

  .brief-entry {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding-bottom: 24px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.16);
  }

  .brief-entry.error-entry {
    background: rgba(244, 63, 94, 0.08);
    border: 1px solid rgba(244, 63, 94, 0.3);
    border-radius: 12px;
    padding: 16px;
  }

  .brief-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .brief-identity {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .brief-mark {
    width: 24px;
    height: 24px;
    border-radius: 8px;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    color: #ffffff;
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 12px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .brief-author {
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 13.5px;
    font-weight: 600;
    color: #ffffff;
  }

  .brief-mode-tag {
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 12px;
    color: #cbd5e1;
    background: #212b45;
    border: 1px solid rgba(148, 163, 184, 0.24);
    padding: 2px 10px;
    border-radius: 20px;
  }

  .streaming-badge {
    font-size: 12px;
    color: #93c5fd;
  }

  .brief-body {
    font-size: 14.5px;
    line-height: 1.74;
    color: #f1f5f9;
    max-width: 74ch;
  }

  .stream-cursor {
    display: inline-block;
    width: 7px;
    height: 15px;
    background: #818cf8;
    margin-left: 3px;
    vertical-align: middle;
    border-radius: 2px;
    animation: pulseFade 0.8s ease-in-out infinite;
  }

  .error-recovery-bar {
    display: flex;
    gap: 8px;
  }

  .btn-retry-query {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(244, 63, 94, 0.2);
    border: 1px solid rgba(244, 63, 94, 0.45);
    color: #ffe4e6;
    padding: 6px 12px;
    border-radius: 8px;
    font-family: "Prompt", sans-serif;
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
  }

  .btn-retry-query:hover:not(:disabled) {
    background: rgba(244, 63, 94, 0.32);
  }

  /* Interactive Grounded Sources Strip */
  .sources-strip {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 14px;
    background: #1a2338;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 12px;
  }

  .sources-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #cbd5e1;
  }

  .sources-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .source-tag {
    font-size: 12px;
    font-family: "Prompt", sans-serif;
    padding: 3px 10px;
    border-radius: 8px;
    background: #24304d;
    border: 1px solid rgba(148, 163, 184, 0.24);
    color: #e2e8f0;
    cursor: pointer;
    transition: background-color 0.14s ease, border-color 0.14s ease;
  }

  .source-tag:hover,
  .source-tag.active {
    background: rgba(99, 102, 241, 0.25);
    border-color: #818cf8;
    color: #ffffff;
  }

  .source-tag.type-qa_consult {
    border-color: rgba(245, 158, 11, 0.42);
    color: #fde68a;
  }

  .source-tag.type-diagram {
    border-color: rgba(16, 185, 129, 0.42);
    color: #6ee7b7;
  }

  .source-tag.more-toggle {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(129, 140, 248, 0.4);
    color: #c7d2fe;
    font-weight: 600;
  }

  .source-inspector-popover {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    padding: 10px 12px;
    background: #212b45;
    border: 1px solid rgba(129, 140, 248, 0.35);
    border-radius: 8px;
  }

  .inspector-pop-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 12.5px;
    color: #f8fafc;
  }

  .inspector-pop-info span {
    font-size: 12px;
    color: #cbd5e1;
  }

  .inspector-pop-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .pop-action-btn {
    background: #6366f1;
    border: none;
    color: #ffffff;
    padding: 5px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-family: "Prompt", sans-serif;
    cursor: pointer;
  }

  .pop-close-btn {
    background: transparent;
    border: 1px solid rgba(148, 163, 184, 0.28);
    color: #cbd5e1;
    width: 26px;
    height: 26px;
    border-radius: 6px;
    cursor: pointer;
  }

  /* Brief Footer Actions */
  .brief-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    padding-top: 2px;
  }

  .brief-action-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #1d263e;
    border: 1px solid rgba(148, 163, 184, 0.22);
    color: #cbd5e1;
    padding: 6px 12px;
    border-radius: 8px;
    font-family: "Prompt", sans-serif;
    font-size: 12px;
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }

  .brief-action-btn:hover {
    background: #283556;
    border-color: rgba(129, 140, 248, 0.45);
    color: #ffffff;
  }

  /* Loading Row */
  .loading-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
  }

  .status-pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #818cf8;
    animation: pulseFade 1.2s ease-in-out infinite;
  }

  @keyframes pulseFade {
    0%, 100% { opacity: 0.35; }
    50% { opacity: 1; }
  }

  .loading-copy {
    font-size: 13.5px;
    color: #cbd5e1;
  }

  .btn-abort-text {
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.42);
    color: #fecdd3;
    padding: 4px 10px;
    border-radius: 8px;
    font-size: 12px;
    cursor: pointer;
  }

  /* Jump to Latest Floating Button */
  .jump-latest-wrap {
    position: absolute;
    bottom: 108px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
  }

  .btn-jump-latest {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #232f4d;
    border: 1px solid rgba(129, 140, 248, 0.45);
    color: #f8fafc;
    padding: 7px 14px;
    border-radius: 20px;
    font-family: "Prompt", sans-serif;
    font-size: 12.5px;
    cursor: pointer;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.38);
  }

  /* ========================================
     MARKDOWN CONTENT TYPOGRAPHY
     ======================================== */
  :global(.markdown-preview .md-heading) {
    margin: 20px 0 8px;
    color: #ffffff;
    font-weight: 600;
    line-height: 1.35;
  }
  :global(.markdown-preview .md-h1) { font-size: 19px; }
  :global(.markdown-preview .md-h2) { font-size: 16.5px; color: #c7d2fe; }
  :global(.markdown-preview .md-h3) { font-size: 15px; color: #93c5fd; }
  :global(.markdown-preview .md-para) {
    margin: 0 0 12px;
  }
  :global(.markdown-preview .md-para:last-child) {
    margin-bottom: 0;
  }
  :global(.markdown-preview .md-hr) {
    border: none;
    border-top: 1px solid rgba(148, 163, 184, 0.2);
    margin: 16px 0;
  }
  :global(.markdown-preview .md-quote) {
    margin: 10px 0;
    padding: 10px 14px;
    background: #1b243b;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 8px;
    color: #e2e8f0;
  }
  :global(.markdown-preview .md-table-wrap) {
    overflow-x: auto;
    margin: 12px 0;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
  }
  :global(.markdown-preview .md-table) {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    background: #1a2338;
  }
  :global(.markdown-preview .md-table th),
  :global(.markdown-preview .md-table td) {
    padding: 9px 12px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    text-align: left;
  }
  :global(.markdown-preview .md-table th) {
    background: #232f4d;
    color: #f8fafc;
    font-weight: 600;
  }
  :global(.markdown-preview .md-table tbody tr:hover) {
    background: rgba(255, 255, 255, 0.04);
  }
  :global(.markdown-preview .citation-pill) {
    display: inline-block;
    background: rgba(16, 185, 129, 0.18);
    border: 1px solid rgba(16, 185, 129, 0.42);
    color: #6ee7b7;
    padding: 1px 7px;
    border-radius: 6px;
    font-family: "Prompt", sans-serif;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    vertical-align: baseline;
  }
  :global(.markdown-preview .citation-pill:hover) {
    background: rgba(16, 185, 129, 0.3);
    color: #ffffff;
  }
  :global(.markdown-preview .inline-code) {
    background: #232f4d;
    border: 1px solid rgba(148, 163, 184, 0.24);
    color: #bfdbfe;
    padding: 1px 6px;
    border-radius: 6px;
    font-size: 12.5px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  :global(.markdown-preview .code-block-wrapper) {
    margin: 12px 0;
    background: #111827;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
    overflow: hidden;
  }
  :global(.markdown-preview .code-header) {
    background: #1e293b;
    padding: 6px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 12px;
    color: #cbd5e1;
    text-transform: uppercase;
    font-weight: 600;
    border-bottom: 1px solid rgba(148, 163, 184, 0.16);
  }
  :global(.markdown-preview .btn-copy-code-block) {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: #e2e8f0;
    padding: 2px 9px;
    border-radius: 6px;
    font-family: "Prompt", sans-serif;
    font-size: 12px;
    text-transform: none;
    cursor: pointer;
  }
  :global(.markdown-preview .btn-copy-code-block:hover) {
    background: rgba(99, 102, 241, 0.3);
    color: #ffffff;
  }
  :global(.markdown-preview pre) {
    margin: 0;
    padding: 12px 14px;
    overflow-x: auto;
  }
  :global(.markdown-preview pre code) {
    color: #f1f5f9;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12.5px;
  }
  :global(.markdown-preview .custom-list),
  :global(.markdown-preview .custom-olist) {
    margin: 6px 0 12px;
    padding-left: 22px;
  }
  :global(.markdown-preview .list-item) {
    margin-bottom: 5px;
  }

  /* ========================================
     ANCHORED COMPOSER DOCK (Brighter Slate)
     ======================================== */
  .composer-dock {
    padding: 12px 24px 18px;
    background: rgba(20, 25, 40, 0.92);
    border-top: 1px solid rgba(148, 163, 184, 0.16);
    flex-shrink: 0;
  }

  .composer-shell {
    max-width: 820px;
    margin: 0 auto;
    background: #1e273f;
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 12px;
    padding: 10px 12px 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color 0.16s ease, box-shadow 0.16s ease;
  }

  .composer-shell:focus-within {
    border-color: rgba(129, 140, 248, 0.72);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
  }

  .composer-shell textarea {
    width: 100%;
    box-sizing: border-box;
    background: transparent;
    border: none;
    color: #ffffff;
    caret-color: #93c5fd;
    font-family: "Prompt", sans-serif;
    font-size: 14px;
    line-height: 1.55;
    resize: none;
    outline: none;
    min-height: 26px;
    max-height: 150px;
    padding: 2px 4px;
  }

  .composer-shell textarea::placeholder {
    color: #94a3b8;
  }

  .composer-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding-top: 6px;
    border-top: 1px solid rgba(148, 163, 184, 0.16);
  }

  .composer-context-tags {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #cbd5e1;
    flex-wrap: wrap;
  }

  .ctx-tag.muted,
  .ctx-hint {
    color: #94a3b8;
  }

  .ctx-sep {
    color: #64748b;
  }

  .composer-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .composer-lang-btn {
    height: 34px;
    padding: 0 9px;
    border-radius: 8px;
    background: #273352;
    border: 1px solid rgba(148, 163, 184, 0.24);
    color: #cbd5e1;
    font-family: "Outfit", "Inter", sans-serif;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
  }

  .composer-lang-btn:hover {
    background: #324166;
    color: #ffffff;
  }

  .composer-icon-btn {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    background: #273352;
    border: 1px solid rgba(148, 163, 184, 0.24);
    color: #cbd5e1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .composer-icon-btn:hover:not(:disabled) {
    background: #324166;
    color: #ffffff;
  }

  .composer-icon-btn.listening {
    background: rgba(244, 63, 94, 0.22);
    border-color: rgba(244, 63, 94, 0.55);
    color: #fecdd3;
  }

  .composer-submit-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    border: none;
    color: #ffffff;
    padding: 7px 15px;
    border-radius: 8px;
    font-family: "Prompt", sans-serif;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: filter 0.15s ease;
  }

  .composer-submit-btn:hover:not(:disabled) {
    filter: brightness(1.08);
  }

  .composer-submit-btn.stop {
    background: #e11d48;
  }

  .composer-submit-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  @media (max-width: 900px) {
    .mobile-drawer-backdrop {
      display: block;
      position: absolute;
      inset: 0;
      background: rgba(5, 8, 18, 0.62);
      border: none;
      z-index: 15;
      cursor: pointer;
    }

    .inspector-rail {
      position: absolute;
      z-index: 20;
      height: 100%;
      box-shadow: 12px 0 32px rgba(0, 0, 0, 0.45);
    }

    .hide-sm {
      display: none;
    }

    .canvas-scroll,
    .composer-dock {
      padding-left: 16px;
      padding-right: 16px;
    }
  }
</style>
