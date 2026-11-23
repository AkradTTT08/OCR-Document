<script>
  import { onMount } from "svelte";
  import { fade } from "svelte/transition";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";
  import { toast } from "./toastStore.js";
  import SmartTestLauncherModal from "./SmartTestLauncherModal.svelte";
  import ConfirmModal from "./ConfirmModal.svelte";
  import QABoardCardModal from "./QABoardCardModal.svelte";
  import QABoardModals from "./QABoardModals.svelte";
  import {
    isHeaderCard,
    getCleanLabels,
    getLabelTextColor,
    getCardVerdict,
    getPriorityMeta,
    resolveMemberName
  } from "./qaBoardUtils.js";

  let projects = [];
  let isTestModalOpen = false;
  let testTargetCard = null;
  let confirmOpen = false;
  let confirmTitle = "";
  let confirmMessage = "";
  let confirmAction = null;
  let cardModalRef = null;

  $: selectedProjectId = $selectedProjectStore ? ($selectedProjectStore.id || $selectedProjectStore.project_id) : "";

  function selectProject(p) {
    selectedProjectStore.set(p);
  }

  onMount(async () => {
    try {
      const res = await fetch("/api/projects");
      if (res.ok) {
        const data = await res.json();
        projects = data.projects || [];
      }
    } catch (err) {
      console.error("Failed to load projects:", err);
    }
  });

  // Active Tab: 'live' | 'saved'
  let activeTab = "live";
  // Saved Tab View Mode: 'kanban' | 'table'
  let savedViewMode = "kanban";

  let columns = [
    { id: "todo", title: "To Do", color: "#64748b" },
    { id: "in_progress", title: "In Progress", color: "#3b82f6" },
    { id: "testing", title: "Testing (Agent)", color: "#a855f7" },
    { id: "done", title: "Done", color: "#22c55e" }
  ];

  let liveCards = [];
  let savedCards = [];
  let isLoadingLive = false;
  let isLoadingSaved = false;
  let isSavingSelected = false;
  let liveLoadError = "";
  let cardSearchQuery = "";

  // Selection state for Live Board
  let selectedCardIds = new Set();

  // Detail Modal state
  let showDetailModal = false;
  let selectedCard = null;

  // Image Lightbox state
  let showImageModal = false;
  let previewModalImage = null;
  let previewModalAlt = "Image Preview";

  function openImagePreview(url, alt = "Image Preview") {
    previewModalImage = url;
    previewModalAlt = alt;
    showImageModal = true;
  }

  // Board integration configuration state
  let showConfigModal = false;
  let currentIntegration = null;
  let configProvider = "trello";
  let trelloApiKey = "";
  let trelloToken = "";
  let trelloBoardId = "";
  let githubToken = "";
  let githubOwner = "";
  let githubRepo = "";
  let isTestingConnection = false;
  let isSavingConfig = false;
  let configErrors = {};

  $: providerLabel = currentIntegration?.provider === "github" ? "GitHub" : "Trello";

  $: if (selectedProjectId) {
    fetchLiveCards();
    fetchSavedCards();
    fetchBoardIntegration();
  } else {
    liveCards = [];
    savedCards = [];
    selectedCardIds = new Set();
    currentIntegration = null;
  }

  async function fetchLiveCards() {
    if (!selectedProjectId) return;
    isLoadingLive = true;
    liveLoadError = "";
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/live`);
      const data = await res.json();
      if (data.success) {
        liveCards = data.cards || [];
        if (data.columns && data.columns.length > 0) {
          columns = data.columns;
        }
        if (selectedCard) {
          const updated = liveCards.find(c => (c.ext_card_id && c.ext_card_id === selectedCard.ext_card_id) || c.id === selectedCard.id);
          if (updated) selectedCard = { ...selectedCard, ...updated };
        }
      } else {
        if (data.error && data.error.includes("ยังไม่ได้ตั้งค่า")) {
          liveCards = [];
        } else {
          liveLoadError = data.error || "เกิดข้อผิดพลาดในการดึงข้อมูลบอร์ดสด";
          toast(liveLoadError, "error");
        }
      }
    } catch (err) {
      liveLoadError = "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์เพื่อดึงข้อมูลบอร์ดสดได้";
      toast(liveLoadError, "error");
    } finally {
      isLoadingLive = false;
    }
  }

  async function fetchSavedCards() {
    if (!selectedProjectId) return;
    isLoadingSaved = true;
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards`);
      const data = await res.json();
      if (data.success) {
        savedCards = data.cards || [];
        if (data.columns && data.columns.length > 0 && liveCards.length === 0) {
          columns = data.columns;
        }
        if (selectedCard) {
          const updated = savedCards.find(c => c.id === selectedCard.id || (c.ext_card_id && c.ext_card_id === selectedCard.ext_card_id));
          if (updated) selectedCard = { ...selectedCard, ...updated };
        }
      } else if (data.error) {
        toast(data.error, "error");
      }
    } catch (err) {
      toast("ไม่สามารถดึงข้อมูลการ์ดที่บันทึกไว้ได้", "error");
    } finally {
      isLoadingSaved = false;
    }
  }

  async function fetchCards() {
    await Promise.all([fetchLiveCards(), fetchSavedCards()]);
  }

  // Visible non-header cards in Live & Saved
  $: colTitleList = columns.map(c => c.title);
  $: validLiveCards = liveCards.filter(c => !isHeaderCard(c.title, colTitleList));
  $: validSavedCards = savedCards.filter(c => !isHeaderCard(c.title, colTitleList));

  // Selection handlers
  function getCardKey(card) {
    return card.ext_card_id || card.raw_ext_id || card.id;
  }

  function toggleSelectCard(card, event) {
    if (event) event.stopPropagation();
    const key = getCardKey(card);
    if (selectedCardIds.has(key)) {
      selectedCardIds.delete(key);
    } else {
      selectedCardIds.add(key);
    }
    selectedCardIds = new Set(selectedCardIds);
  }

  function isCardSelected(card, _tracker = null) {
    return selectedCardIds.has(getCardKey(card));
  }

  // Select ONLY currently visible/filtered cards on Live Board
  function selectAllLiveCards() {
    const visibleList = Object.values(liveCardsByCol).flat();
    visibleList.forEach(c => {
      selectedCardIds.add(getCardKey(c));
    });
    selectedCardIds = new Set(selectedCardIds);
  }

  function clearCardSelection() {
    selectedCardIds = new Set();
  }

  async function saveSelectedCardsToProject() {
    if (selectedCardIds.size === 0) {
      toast("กรุณาเลือกการ์ดที่ต้องการบันทึกอย่างน้อย 1 ใบ", "warning");
      return;
    }

    const chosenCards = validLiveCards.filter(c => isCardSelected(c));
    if (chosenCards.length === 0) {
      toast("ไม่พบข้อมูลการ์ดที่เลือก", "error");
      return;
    }

    isSavingSelected = true;
    toast(`กำลังบันทึก ${chosenCards.length} การ์ดเข้าโครงการ & RAG...`, "info");
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/save-selected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cards: chosenCards })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.message || `บันทึกสำเร็จ ${chosenCards.length} ใบ!`, "success");
        clearCardSelection();
        await fetchCards();
      } else {
        toast(data.error || "บันทึกการ์ดไม่สำเร็จ", "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการบันทึก: ${err.message}`, "error");
    } finally {
      isSavingSelected = false;
    }
  }

  async function saveSingleCard(card) {
    isSavingSelected = true;
    toast(`กำลังบันทึก "${card.title}" เข้าโครงการ & RAG...`, "info");
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/save-selected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cards: [card] })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.message || "บันทึกการ์ดสำเร็จ!", "success");
        await fetchCards();
        if (selectedCard) {
          selectedCard = { ...selectedCard, is_saved: true };
        }
      } else {
        toast(data.error || "บันทึกการ์ดไม่สำเร็จ", "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการบันทึก: ${err.message}`, "error");
    } finally {
      isSavingSelected = false;
    }
  }

  function unsaveCard(card, event) {
    if (event) event.stopPropagation();
    const cTitle = card.title || "การ์ดใบนี้";
    confirmTitle = "ยืนยันการยกเลิกบันทึกการ์ด";
    confirmMessage = `ต้องการยกเลิกการบันทึก "${cTitle}" ออกจากโครงการนี้และลบออกจากดัชนี RAG ใช่หรือไม่?`;
    confirmAction = async () => {
      const cardId = card.saved_id || card.id;
      try {
        const res = await fetch(`/api/projects/${selectedProjectId}/cards/${cardId}`, {
          method: "DELETE"
        });
        const data = await res.json();
        if (res.ok && data.success) {
          toast(data.message || "ยกเลิกการบันทึกการ์ดสำเร็จ", "success");
          await fetchCards();
          if (selectedCard && (selectedCard.id === cardId || selectedCard.saved_id === cardId)) {
            selectedCard = { ...selectedCard, is_saved: false };
          }
        } else {
          toast(data.error || "ยกเลิกการบันทึกไม่สำเร็จ", "error");
        }
      } catch (err) {
        toast(`เกิดข้อผิดพลาดในการลบ: ${err.message}`, "error");
      }
    };
    confirmOpen = true;
  }

  function clearAllSavedCards() {
    if (validSavedCards.length === 0) return;
    confirmTitle = "ยืนยันการล้างการ์ดทั้งหมด";
    confirmMessage = `ต้องการลบการ์ดที่บันทึกไว้ทั้งหมด ${validSavedCards.length} ใบออกจากโครงการนี้และ RAG ใช่หรือไม่?`;
    confirmAction = async () => {
      try {
        const res = await fetch(`/api/projects/${selectedProjectId}/cards/clear-all`, {
          method: "POST"
        });
        const data = await res.json();
        if (res.ok && data.success) {
          toast(data.message || "ล้างการ์ดที่บันทึกทั้งหมดเรียบร้อยแล้ว", "success");
          await fetchCards();
        } else {
          toast(data.error || "ล้างการ์ดไม่สำเร็จ", "error");
        }
      } catch (err) {
        toast(`เกิดข้อผิดพลาด: ${err.message}`, "error");
      }
    };
    confirmOpen = true;
  }

  function handleAgentTest(cardOrId) {
    if (typeof cardOrId === "object" && cardOrId !== null) {
      testTargetCard = cardOrId;
    } else if (selectedCard) {
      testTargetCard = selectedCard;
    } else {
      testTargetCard = { title: "Feature Testing", description: "" };
    }
    const targetId = testTargetCard.id || testTargetCard.raw_ext_id;
    if (targetId) {
      savedCards = savedCards.map(c => (c.id === targetId || c.raw_ext_id === targetId) ? { ...c, isTesting: true } : c);
      if (selectedCard && (selectedCard.id === targetId || selectedCard.raw_ext_id === targetId)) {
        selectedCard = { ...selectedCard, isTesting: true };
      }
    }
    isTestModalOpen = true;
  }

  function handleTestModalClose() {
    isTestModalOpen = false;
    if (testTargetCard) {
      const targetId = testTargetCard.id || testTargetCard.raw_ext_id;
      savedCards = savedCards.map(c => (c.id === targetId || c.raw_ext_id === targetId) ? { ...c, isTesting: false } : c);
      if (selectedCard && (selectedCard.id === targetId || selectedCard.raw_ext_id === targetId)) {
        selectedCard = { ...selectedCard, isTesting: false };
      }
    }
  }

  function handleTestCompleted(e) {
    const result = e.detail;
    if (selectedCard) {
      selectedCard = {
        ...selectedCard,
        test_result: result.test_result_markdown,
        verdict: result.verdict,
        isTesting: false
      };
    }
    fetchCards();
    toast(`รันการทดสอบเสร็จสิ้น: ${result.verdict}`, result.is_passed ? "success" : "warning");
  }

  async function fetchBoardIntegration() {
    if (!selectedProjectId) return;
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/board-integration`);
      const data = await res.json();
      if (data.success && data.integration) {
        currentIntegration = data.integration;
        configProvider = data.integration.provider || "trello";
        trelloApiKey = data.integration.trello_api_key || "";
        trelloToken = data.integration.trello_token || "";
        trelloBoardId = data.integration.trello_board_id || "";
        githubToken = data.integration.github_token || "";
        githubOwner = data.integration.github_owner || "";
        githubRepo = data.integration.github_repo || "";
      } else {
        currentIntegration = null;
      }
    } catch (err) {
      console.error("Error fetching board integration:", err);
    }
  }

  function validateConfigFields() {
    const errs = {};
    if (configProvider === "trello") {
      if (!trelloApiKey.trim()) errs.trelloApiKey = "กรุณากรอก Trello API Key";
      if (!trelloToken.trim()) errs.trelloToken = "กรุณากรอก Trello API Token";
      if (!trelloBoardId.trim()) errs.trelloBoardId = "กรุณากรอก Trello Board ID หรือ URL";
    } else {
      if (!githubToken.trim()) errs.githubToken = "กรุณากรอก GitHub Personal Access Token";
      if (!githubOwner.trim()) errs.githubOwner = "กรุณากรอกชื่อ Owner หรือ Organization";
      if (!githubRepo.trim()) errs.githubRepo = "กรุณากรอกชื่อ Repository";
    }
    configErrors = errs;
    return Object.keys(errs).length === 0;
  }

  async function testConnection() {
    if (!selectedProjectId || !validateConfigFields()) return;
    isTestingConnection = true;
    try {
      const payload = {
        provider: configProvider,
        trello_api_key: trelloApiKey.trim(),
        trello_token: trelloToken.trim(),
        trello_board_id: trelloBoardId.trim(),
        github_token: githubToken.trim(),
        github_owner: githubOwner.trim(),
        github_repo: githubRepo.trim()
      };
      const res = await fetch(`/api/projects/${selectedProjectId}/board-integration/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      let data = {};
      try { data = await res.json(); } catch (e) {}
      if (res.ok && data.success) {
        toast(data.message || "เชื่อมต่อสำเร็จ!", "success");
      } else {
        toast(data.error || `เชื่อมต่อไม่สำเร็จ (${res.status})`, "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการทดสอบเชื่อมต่อ: ${err.message}`, "error");
    } finally {
      isTestingConnection = false;
    }
  }

  async function saveBoardIntegration() {
    if (!selectedProjectId || !validateConfigFields()) return;
    isSavingConfig = true;
    try {
      const payload = {
        provider: configProvider,
        trello_api_key: trelloApiKey.trim(),
        trello_token: trelloToken.trim(),
        trello_board_id: trelloBoardId.trim(),
        github_token: githubToken.trim(),
        github_owner: githubOwner.trim(),
        github_repo: githubRepo.trim()
      };
      const res = await fetch(`/api/projects/${selectedProjectId}/board-integration`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      let data = {};
      try { data = await res.json(); } catch (e) {}
      if (res.ok && data.success) {
        toast("บันทึกการตั้งค่าการเชื่อมต่อสำเร็จ!", "success");
        await fetchBoardIntegration();
        showConfigModal = false;
        fetchLiveCards();
      } else {
        toast(data.error || `บันทึกไม่สำเร็จ (${res.status})`, "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการบันทึก: ${err.message}`, "error");
    } finally {
      isSavingConfig = false;
    }
  }

  // Filter & Agile Tools state
  let showFilterModal = false;
  let showAgileSummaryModal = false;
  let markUnestimated = false;

  let filterNoMembers = false;
  let selectedMemberIds = new Set();
  let filterNoLabels = false;
  let selectedLabelNames = new Set();
  let filterSavedStatus = "all";
  let filterCompletion = "all";
  let filterTypes = new Set();

  function toggleMemberFilter(mId) {
    if (selectedMemberIds.has(mId)) selectedMemberIds.delete(mId);
    else selectedMemberIds.add(mId);
    selectedMemberIds = new Set(selectedMemberIds);
  }

  function toggleLabelFilter(lName) {
    const lLow = (lName || "").toLowerCase();
    if (selectedLabelNames.has(lLow)) selectedLabelNames.delete(lLow);
    else selectedLabelNames.add(lLow);
    selectedLabelNames = new Set(selectedLabelNames);
  }

  function toggleTypeFilter(tName) {
    if (filterTypes.has(tName)) filterTypes.delete(tName);
    else filterTypes.add(tName);
    filterTypes = new Set(filterTypes);
  }

  function resetAllFilters() {
    cardSearchQuery = "";
    filterNoMembers = false;
    selectedMemberIds = new Set();
    filterNoLabels = false;
    selectedLabelNames = new Set();
    filterSavedStatus = "all";
    filterCompletion = "all";
    filterTypes = new Set();
  }

  $: boardMembersList = (() => {
    const map = new Map();
    const source = [...liveCards, ...savedCards];
    source.forEach(c => {
      (c.members || []).forEach(m => {
        const id = m.id || m.username || m.name;
        if (id && !map.has(id)) map.set(id, m);
      });
    });
    return Array.from(map.values());
  })();

  $: boardLabelsList = (() => {
    const map = new Map();
    const source = activeTab === "live" ? validLiveCards : validSavedCards;
    source.forEach(c => {
      (c.labels || []).forEach(l => {
        const rawName = typeof l === "string" ? l : (l.name || "");
        const cleanName = rawName.replace(/[*_`~#]/g, "").trim();
        const lower = cleanName.toLowerCase();
        if (cleanName && !map.has(lower)) {
          map.set(lower, { name: cleanName, color: l.color || "#6366f1", count: 0 });
        }
        if (cleanName && map.has(lower)) {
          map.get(lower).count += 1;
        }
      });
    });
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  })();

  $: boardTypesList = (() => {
    const set = new Set();
    const source = [...validLiveCards, ...validSavedCards];
    source.forEach(c => {
      const t = (c.type && c.type !== "Main Card") ? c.type : (c.priority || "");
      if (t) set.add(t);
    });
    return Array.from(set);
  })();

  $: agilePointsSummary = (() => {
    let totalPoints = 0;
    let totalCards = 0;
    let unestimatedCards = 0;
    const byColumn = {};

    columns.forEach(col => {
      byColumn[col.id] = { id: col.id, title: col.title, color: col.color, points: 0, count: 0 };
    });

    const targetList = activeTab === "live" ? validLiveCards : validSavedCards;
    targetList.forEach(c => {
      const pts = parseFloat(c.story_points);
      const pointsVal = !isNaN(pts) ? pts : 0;
      if (isNaN(pts) || pts === 0) unestimatedCards += 1;
      totalPoints += pointsVal;
      totalCards += 1;

      const colId = c.status && byColumn[c.status] ? c.status : (columns[0] ? columns[0].id : "todo");
      if (byColumn[colId]) {
        byColumn[colId].points = Math.round((byColumn[colId].points + pointsVal) * 10) / 10;
        byColumn[colId].count += 1;
      }
    });

    return {
      totalPoints: Math.round(totalPoints * 10) / 10,
      totalCards,
      unestimatedCards,
      columnsSummary: Object.values(byColumn),
      byColumn
    };
  })();

  $: activeFilterCount =
    (cardSearchQuery.trim() ? 1 : 0) +
    (filterNoMembers ? 1 : 0) +
    selectedMemberIds.size +
    (filterNoLabels ? 1 : 0) +
    selectedLabelNames.size +
    (activeTab === "live" && filterSavedStatus !== "all" ? 1 : 0) +
    (filterCompletion !== "all" ? 1 : 0) +
    filterTypes.size;

  function isCardUnestimated(card) {
    const pts = parseFloat(card?.story_points);
    return isNaN(pts) || pts === 0;
  }

  function computeCardsByColumn(cardsList, cols, query, noMembers, memberIds, noLabels, labelNames, savedStatus, completion, types) {
    const colTitles = cols.map(c => c.title);
    const q = (query || "").trim().toLowerCase();
    const result = {};
    cols.forEach(c => { result[c.id] = []; });
    const defaultColId = cols.length > 0 ? cols[0].id : "todo";

    for (let i = 0; i < cardsList.length; i++) {
      const c = cardsList[i];
      if (isHeaderCard(c.title, colTitles)) continue;

      if (q) {
        const matchTitle = (c.title || "").toLowerCase().includes(q);
        const matchDesc = (c.description || "").toLowerCase().includes(q);
        const matchId = (c.ext_card_id || "").toLowerCase().includes(q);
        const matchLabels = (c.labels || []).some(l => ((typeof l === "string" ? l : l.name) || "").toLowerCase().includes(q));
        const matchMembers = (c.members || []).some(m => ((m.name || "") + " " + (m.username || "")).toLowerCase().includes(q));
        if (!matchTitle && !matchDesc && !matchId && !matchLabels && !matchMembers) continue;
      }

      if (noMembers) {
        if (c.members && c.members.length > 0) continue;
      } else if (memberIds && memberIds.size > 0) {
        if (!c.members || c.members.length === 0) continue;
        const hasMatch = c.members.some(m => memberIds.has(m.id) || memberIds.has(m.username) || memberIds.has(m.name));
        if (!hasMatch) continue;
      }

      if (noLabels) {
        if (c.labels && c.labels.length > 0) continue;
      } else if (labelNames && labelNames.size > 0) {
        if (!c.labels || c.labels.length === 0) continue;
        const hasMatch = c.labels.some(l => {
          const rawName = typeof l === "string" ? l : (l.name || "");
          const cleanName = rawName.replace(/[*_`~#]/g, "").trim().toLowerCase();
          return labelNames.has(cleanName);
        });
        if (!hasMatch) continue;
      }

      if (savedStatus === "saved" && !c.is_saved) continue;
      if (savedStatus === "unsaved" && c.is_saved) continue;

      if (completion === "complete") {
        const isDone = c.status === "done" || (c.status && c.status.toLowerCase().includes("done"));
        if (!isDone) continue;
      } else if (completion === "incomplete") {
        const isDone = c.status === "done" || (c.status && c.status.toLowerCase().includes("done"));
        if (isDone) continue;
      }

      if (types && types.size > 0) {
        const cardTypeVal = (c.type && c.type !== "Main Card") ? c.type : (c.priority || "");
        if (!types.has(cardTypeVal)) continue;
      }

      const colId = c.status && result[c.status] ? c.status : defaultColId;
      if (!result[colId]) result[colId] = [];
      result[colId].push(c);
    }
    return result;
  }

  $: liveCardsByCol = computeCardsByColumn(liveCards, columns, cardSearchQuery, filterNoMembers, selectedMemberIds, filterNoLabels, selectedLabelNames, filterSavedStatus, filterCompletion, filterTypes);
  $: savedCardsByCol = computeCardsByColumn(savedCards, columns, cardSearchQuery, filterNoMembers, selectedMemberIds, filterNoLabels, selectedLabelNames, "all", filterCompletion, filterTypes);

  $: totalFilteredLiveCardsCount = Object.values(liveCardsByCol).reduce((acc, list) => acc + list.length, 0);
  $: totalFilteredSavedCardsCount = Object.values(savedCardsByCol).reduce((acc, list) => acc + list.length, 0);
  $: totalFilteredCardsCount = activeTab === "live" ? totalFilteredLiveCardsCount : totalFilteredSavedCardsCount;
  $: flatFilteredSavedCards = Object.values(savedCardsByCol).flat();

  function getColumnPoints(cardsInCol = []) {
    let sum = 0;
    for (const c of cardsInCol) {
      const p = parseFloat(c.story_points);
      if (!isNaN(p)) sum += p;
    }
    return Math.round(sum * 10) / 10;
  }

  // Comment & attachment handlers
  let newCommentText = "";
  let commentAttachments = [];
  let isSendingComment = false;
  let isUploadingAttachment = false;

  async function uploadFileAttachment(file, fallbackFilename = "attachment") {
    if (!file || !selectedProjectId || isUploadingAttachment) return;
    isUploadingAttachment = true;
    try {
      const formData = new FormData();
      formData.append("file", file, file.name || fallbackFilename);
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/upload-attachment`, {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (res.ok && data.success) {
        const newAtt = {
          id: "att_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8),
          url: data.url,
          filename: data.filename || fallbackFilename || (data.is_video ? "video.mp4" : "screenshot.png"),
          type: data.type || (data.is_video ? "video" : "image")
        };
        commentAttachments = [...commentAttachments, newAtt];
        toast(data.is_video ? "แนบวิดีโอเรียบร้อยแล้ว!" : "แนบรูปภาพเรียบร้อยแล้ว!", "success");
      } else {
        toast(data.error || "เกิดข้อผิดพลาดในการอัปโหลดไฟล์", "error");
      }
    } catch (e) {
      toast("เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์", "error");
    } finally {
      isUploadingAttachment = false;
    }
  }

  function removeCommentAttachment(attId) {
    commentAttachments = commentAttachments.filter(a => a.id !== attId);
  }

  function handleCommentPaste(e) {
    const items = (e.clipboardData || window.clipboardData)?.items;
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.indexOf("image") !== -1) {
          e.preventDefault();
          const blob = item.getAsFile();
          if (blob) uploadFileAttachment(blob, `screenshot_${Date.now()}.png`);
          return;
        } else if (item.type.indexOf("video") !== -1) {
          e.preventDefault();
          const blob = item.getAsFile();
          if (blob) uploadFileAttachment(blob, `video_${Date.now()}.mp4`);
          return;
        }
      }
    }
    const files = e.clipboardData?.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.type.startsWith("image/") || file.type.startsWith("video/")) {
        e.preventDefault();
        uploadFileAttachment(file, file.name);
      }
    }
  }

  function handleFileInputChange(e) {
    if (e.target?.files?.length > 0) {
      const file = e.target.files[0];
      uploadFileAttachment(file, file.name);
      e.target.value = "";
    }
  }

  async function postComment() {
    let fullComment = newCommentText.trim();
    if (commentAttachments.length > 0) {
      const attsMd = commentAttachments.map(a => `![${a.type === "video" ? "Video" : "Image"}](${a.url})`).join("\n\n");
      fullComment = fullComment ? `${fullComment}\n\n${attsMd}` : attsMd;
    }
    if (!selectedCard || !fullComment || isSendingComment) return;
    const cardId = selectedCard.saved_id || selectedCard.id;
    isSendingComment = true;
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/${cardId}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          comment: fullComment,
          raw_ext_id: selectedCard.raw_ext_id || selectedCard.ext_card_id || selectedCard.id,
          attachments: commentAttachments,
          current_actions: selectedCard.actions || []
        })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        selectedCard = { ...selectedCard, actions: data.actions };
        savedCards = savedCards.map(c => (c.id === cardId || (c.raw_ext_id && c.raw_ext_id === selectedCard.raw_ext_id)) ? { ...c, actions: data.actions } : c);
        liveCards = liveCards.map(c => (c.id === cardId || (c.raw_ext_id && c.raw_ext_id === selectedCard.raw_ext_id)) ? { ...c, actions: data.actions } : c);
        newCommentText = "";
        commentAttachments = [];
        toast(data.message || `เพิ่มความคิดเห็นและซิงก์ไปยัง ${providerLabel} เรียบร้อยแล้ว!`, "success");
      } else {
        toast(data.error || "เกิดข้อผิดพลาดในการบันทึกความคิดเห็น", "error");
      }
    } catch (e) {
      toast("เกิดข้อผิดพลาดในการส่งความคิดเห็น", "error");
    } finally {
      isSendingComment = false;
    }
  }

  function openCardDetail(card) {
    selectedCard = card;
    showDetailModal = true;
  }

  function closeCardDetail() {
    showDetailModal = false;
    selectedCard = null;
    newCommentText = "";
    commentAttachments = [];
  }

  // Move card (used by both Drag & Drop AND Keyboard/Select dropdown!)
  async function moveCardToColumn(cardToMove, targetColumnId) {
    if (!cardToMove || !targetColumnId || cardToMove.status === targetColumnId) return;

    const prevStatus = cardToMove.status;
    const cardId = cardToMove.saved_id || cardToMove.id;
    const rawExtId = cardToMove.raw_ext_id || cardToMove.ext_card_id || cardToMove.id;

    liveCards = liveCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: targetColumnId } : c);
    savedCards = savedCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: targetColumnId } : c);
    if (selectedCard && (selectedCard.id === cardId || selectedCard.raw_ext_id === rawExtId)) {
      selectedCard = { ...selectedCard, status: targetColumnId };
    }

    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/${cardId}/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status: targetColumnId,
          raw_ext_id: rawExtId
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        toast(data.error || "ไม่สามารถย้ายการ์ดได้", "error");
        liveCards = liveCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
        savedCards = savedCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
        if (selectedCard && (selectedCard.id === cardId || selectedCard.raw_ext_id === rawExtId)) {
          selectedCard = { ...selectedCard, status: prevStatus };
        }
      } else {
        const destTitle = columns.find(c => c.id === targetColumnId)?.title || targetColumnId;
        toast(`ย้ายการ์ดไปยัง "${destTitle}" เรียบร้อยแล้ว`, "success");
      }
    } catch (err) {
      toast("เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์", "error");
      liveCards = liveCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
      savedCards = savedCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
      if (selectedCard && (selectedCard.id === cardId || selectedCard.raw_ext_id === rawExtId)) {
        selectedCard = { ...selectedCard, status: prevStatus };
      }
    }
  }

  // Drag & Drop handlers
  let draggedCard = null;
  let sourceColumnId = null;
  let dragOverColumnId = null;

  function handleDragStart(card, colId, e) {
    draggedCard = card;
    sourceColumnId = colId;
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", card.id || card.raw_ext_id);
    }
  }

  function handleDragOver(colId, e) {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    if (dragOverColumnId !== colId) dragOverColumnId = colId;
  }

  function handleDragLeave(colId) {
    if (dragOverColumnId === colId) dragOverColumnId = null;
  }

  function handleDragEnd() {
    draggedCard = null;
    sourceColumnId = null;
    dragOverColumnId = null;
  }

  async function handleDrop(targetColumnId, e) {
    e.preventDefault();
    if (!draggedCard || sourceColumnId === targetColumnId) {
      handleDragEnd();
      return;
    }
    const cardToMove = { ...draggedCard };
    handleDragEnd();
    await moveCardToColumn(cardToMove, targetColumnId);
  }

  function handleCardKeydown(card, e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openCardDetail(card);
    }
  }

  function handleAvatarError(e) {
    e.currentTarget.style.display = "none";
    if (e.currentTarget.nextElementSibling) {
      e.currentTarget.nextElementSibling.style.display = "inline-flex";
    }
  }

  // Guarded Escape handler (does not collide with ConfirmModal or SmartTestLauncherModal!)
  function handleWindowKeydown(e) {
    if (e.key !== "Escape") return;
    if (confirmOpen || isTestModalOpen) return;
    if (showImageModal) {
      showImageModal = false;
    } else if (showFilterModal) {
      showFilterModal = false;
    } else if (showAgileSummaryModal) {
      showAgileSummaryModal = false;
    } else if (showConfigModal) {
      showConfigModal = false;
    } else if (showDetailModal) {
      if (cardModalRef?.requestClose) cardModalRef.requestClose();
      else closeCardDetail();
    }
  }
</script>

<svelte:window on:keydown={handleWindowKeydown} />

<div class="board-container" in:fade={{ duration: 150 }}>
  {#if !$selectedProjectStore}
    <ProjectSelection
      {projects}
      subtitle="กรุณาเลือกโครงการที่ต้องการ เพื่อดูและจัดการ QA Board Cards"
      on:select={(e) => selectProject(e.detail)}
    />
  {:else}
    <!-- Distilled 2-Row Top Chrome -->
    <header class="board-chrome-shell">
      <!-- Row 1: Navigation + Project/Provider Identity + Main Tabs + Board Settings -->
      <div class="chrome-row-primary">
        <div class="chrome-brand-group">
          <button
            type="button"
            class="btn-back-compact"
            on:click={() => selectedProjectStore.set(null)}
            title="ย้อนกลับไปหน้าเลือกโครงการ"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="15" height="15">
              <polyline points="15 18 9 12 15 6"></polyline>
            </svg>
            <span>เปลี่ยนโครงการ</span>
          </button>

          <div class="project-identity-block">
            <div class="project-title-line">
              <h2 class="board-title">QA Board & RAG Workspace</h2>
              <span class="active-project-pill">
                {$selectedProjectStore.project_code ? `${$selectedProjectStore.project_code} · ` : ""}{$selectedProjectStore.name || $selectedProjectStore.project_name || "Project"}
              </span>
              {#if currentIntegration}
                <span class="integration-pill connected">
                  <span class="status-dot"></span>
                  {#if currentIntegration.provider === "github"}
                    GitHub: {currentIntegration.github_owner}/{currentIntegration.github_repo}
                  {:else}
                    Trello: {currentIntegration.trello_board_id}
                  {/if}
                </span>
              {:else}
                <button
                  type="button"
                  class="integration-pill unconfigured"
                  on:click={() => (showConfigModal = true)}
                >
                  ยังไม่ได้เชื่อมต่อบอร์ด — คลิกเพื่อตั้งค่า
                </button>
              {/if}
            </div>
          </div>
        </div>

        <!-- Center/Right: Main Tab Switcher + Agile Tools + Board Config -->
        <div class="chrome-primary-right">
          <div class="main-tab-switcher" role="tablist" aria-label="สลับมุมมองบอร์ด">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "live"}
              class="main-tab-btn"
              class:active={activeTab === "live"}
              on:click={() => (activeTab = "live")}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                <rect x="3" y="3" width="18" height="18" rx="2"></rect>
                <line x1="9" y1="3" x2="9" y2="21"></line>
                <line x1="15" y1="3" x2="15" y2="21"></line>
              </svg>
              <span>บอร์ด {providerLabel} สด</span>
              <span class="tab-count-pill">{validLiveCards.length}</span>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={activeTab === "saved"}
              class="main-tab-btn"
              class:active={activeTab === "saved"}
              on:click={() => (activeTab = "saved")}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
              </svg>
              <span>การ์ดในโครงการ & RAG</span>
              <span class="tab-count-pill saved">{validSavedCards.length}</span>
            </button>
          </div>

          <button
            type="button"
            class="btn-chrome-tool"
            on:click={() => (showAgileSummaryModal = true)}
            title="ดูสรุปแต้ม Story Points (Agile Tools)"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            <span>Agile</span>
            <span class="pts-chip">{agilePointsSummary.totalPoints} pts</span>
          </button>

          <button
            type="button"
            class="btn-chrome-tool"
            on:click={() => (showConfigModal = true)}
            title="ตั้งค่าเชื่อมต่อ Trello หรือ GitHub"
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
            <span>ตั้งค่า Board</span>
          </button>
        </div>
      </div>

      <!-- Row 2: Contextual Action & Filter Toolbar -->
      <div class="chrome-row-secondary">
        <div class="secondary-left">
          {#if activeTab === "live"}
            <span class="selection-readout">
              เลือกแล้ว <strong>{selectedCardIds.size}</strong> / {totalFilteredLiveCardsCount} การ์ด
            </span>
            <button
              type="button"
              class="btn-toolbar-sub"
              on:click={selectAllLiveCards}
              disabled={totalFilteredLiveCardsCount === 0}
              title="เลือกการ์ดทั้งหมดที่แสดงอยู่ในขณะนี้"
            >
              เลือกทั้งหมดที่แสดง
            </button>
            {#if selectedCardIds.size > 0}
              <button
                type="button"
                class="btn-toolbar-sub"
                on:click={clearCardSelection}
              >
                ล้างที่เลือก
              </button>
            {/if}
          {:else}
            <!-- Saved Tab: View Switcher (Kanban vs QA Execution Table) -->
            <div class="view-mode-segmented" role="group" aria-label="รูปแบบการแสดงผลการ์ดที่บันทึก">
              <button
                type="button"
                class="seg-btn"
                class:active={savedViewMode === "kanban"}
                on:click={() => (savedViewMode = "kanban")}
              >
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <rect x="3" y="3" width="18" height="18" rx="2"></rect>
                  <line x1="9" y1="3" x2="9" y2="21"></line>
                  <line x1="15" y1="3" x2="15" y2="21"></line>
                </svg>
                Kanban Board
              </button>
              <button
                type="button"
                class="seg-btn"
                class:active={savedViewMode === "table"}
                on:click={() => (savedViewMode = "table")}
              >
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <line x1="8" y1="6" x2="21" y2="6"></line>
                  <line x1="8" y1="12" x2="21" y2="12"></line>
                  <line x1="8" y1="18" x2="21" y2="18"></line>
                  <line x1="3" y1="6" x2="3.01" y2="6"></line>
                  <line x1="3" y1="12" x2="3.01" y2="12"></line>
                  <line x1="3" y1="18" x2="3.01" y2="18"></line>
                </svg>
                QA Execution Table
              </button>
            </div>
            <span class="rag-ready-hint">
              พร้อมใช้งาน RAG Vector Search ({validSavedCards.length} ใบ)
            </span>
          {/if}
        </div>

        <div class="secondary-right">
          <div class="search-box-compact">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <circle cx="11" cy="11" r="8"></circle>
              <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
            </svg>
            <input
              type="text"
              placeholder="ค้นหาชื่อการ์ด, รหัส, ป้ายกำกับ..."
              aria-label="ค้นหาชื่อการ์ด, รหัส, ป้ายกำกับ"
              bind:value={cardSearchQuery}
            />
            {#if cardSearchQuery}
              <button type="button" class="btn-clear-query" aria-label="ล้างคำค้นหา" on:click={() => (cardSearchQuery = "")}>✕</button>
            {/if}
          </div>

          <!-- Single Unified Filter Button -->
          <button
            type="button"
            class="btn-toolbar-sub"
            class:active-filter={activeFilterCount > 0}
            on:click={() => (showFilterModal = true)}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
            </svg>
            <span>ตัวกรอง</span>
            {#if activeFilterCount > 0}
              <span class="filter-badge-count">{activeFilterCount}</span>
            {/if}
          </button>

          {#if activeTab === "live"}
            <button
              type="button"
              class="btn-toolbar-sub"
              on:click={fetchLiveCards}
              disabled={isLoadingLive}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" class:spinning={isLoadingLive}>
                <path d="M23 4v6h-6"></path>
                <path d="M1 20v-6h6"></path>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
              </svg>
              <span>{isLoadingLive ? "กำลังโหลด..." : "รีเฟรช"}</span>
            </button>

            <button
              type="button"
              class="btn-primary-cta"
              on:click={saveSelectedCardsToProject}
              disabled={selectedCardIds.size === 0 || isSavingSelected}
            >
              {#if isSavingSelected}
                <span class="spinner-small"></span> กำลังบันทึก & Index RAG...
              {:else}
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                  <polyline points="17 21 17 13 7 13 7 21"></polyline>
                </svg>
                <span>บันทึกเข้าโครงการ & RAG ({selectedCardIds.size})</span>
              {/if}
            </button>
          {:else}
            <button
              type="button"
              class="btn-toolbar-sub"
              on:click={fetchSavedCards}
              disabled={isLoadingSaved}
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" class:spinning={isLoadingSaved}>
                <path d="M23 4v6h-6"></path>
                <path d="M1 20v-6h6"></path>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
              </svg>
              <span>{isLoadingSaved ? "กำลังโหลด..." : "รีเฟรช"}</span>
            </button>

            <button
              type="button"
              class="btn-toolbar-sub"
              on:click={() => (activeTab = "live")}
            >
              + เลือกการ์ดเพิ่มจากบอร์ดสด
            </button>

            {#if validSavedCards.length > 0}
              <button
                type="button"
                class="btn-toolbar-danger"
                on:click={clearAllSavedCards}
              >
                ล้างทั้งหมด
              </button>
            {/if}
          {/if}
        </div>
      </div>

      <!-- Active Filter Strip (with human member names & types!) -->
      {#if activeFilterCount > 0}
        <div class="active-filters-strip">
          <span class="strip-label">
            กำลังกรอง ({totalFilteredCardsCount} / {activeTab === "live" ? validLiveCards.length : validSavedCards.length} การ์ด):
          </span>
          {#if cardSearchQuery}
            <span class="filter-chip">คำค้น: "{cardSearchQuery}" <button type="button" aria-label="ลบคำค้น" on:click={() => (cardSearchQuery = "")}>✕</button></span>
          {/if}
          {#if filterNoMembers}
            <span class="filter-chip">ไม่มีผู้รับผิดชอบ <button type="button" aria-label="ลบตัวกรองไม่มีผู้รับผิดชอบ" on:click={() => (filterNoMembers = false)}>✕</button></span>
          {/if}
          {#each Array.from(selectedMemberIds) as mId}
            <span class="filter-chip">สมาชิก: {resolveMemberName(mId, boardMembersList)} <button type="button" aria-label="ลบตัวกรองสมาชิก" on:click={() => toggleMemberFilter(mId)}>✕</button></span>
          {/each}
          {#if filterNoLabels}
            <span class="filter-chip">ไม่มีป้ายกำกับ <button type="button" aria-label="ลบตัวกรองไม่มีป้ายกำกับ" on:click={() => (filterNoLabels = false)}>✕</button></span>
          {/if}
          {#each Array.from(selectedLabelNames) as lName}
            <span class="filter-chip">Label: {lName} <button type="button" aria-label="ลบตัวกรองป้ายกำกับ" on:click={() => toggleLabelFilter(lName)}>✕</button></span>
          {/each}
          {#each Array.from(filterTypes) as tName}
            <span class="filter-chip">ประเภท: {tName} <button type="button" aria-label="ลบตัวกรองประเภท" on:click={() => toggleTypeFilter(tName)}>✕</button></span>
          {/each}
          {#if activeTab === "live" && filterSavedStatus !== "all"}
            <span class="filter-chip">สถานะ: {filterSavedStatus === "saved" ? "บันทึกแล้ว" : "ยังไม่บันทึก"} <button type="button" aria-label="ลบตัวกรองสถานะบันทึก" on:click={() => (filterSavedStatus = "all")}>✕</button></span>
          {/if}
          {#if filterCompletion !== "all"}
            <span class="filter-chip">ความคืบหน้า: {filterCompletion === "complete" ? "เสร็จสิ้น" : "กำลังดำเนินการ"} <button type="button" aria-label="ลบตัวกรองความคืบหน้า" on:click={() => (filterCompletion = "all")}>✕</button></span>
          {/if}
          <button type="button" class="btn-clear-all-filters" on:click={resetAllFilters}>ล้างตัวกรองทั้งหมด</button>
        </div>
      {/if}
    </header>

    <!-- MAIN BOARD WORKSPACE -->
    {#if activeTab === "live"}
      {#if isLoadingLive && validLiveCards.length === 0}
        <!-- Loading Skeleton Grid -->
        <div class="board-layout" aria-live="polite" aria-busy="true">
          {#each columns as col}
            <div class="board-column">
              <div class="column-header">
                <span class="column-dot" style="background-color: {col.color};"></span>
                <span class="column-title">{col.title}</span>
                <span class="column-count">...</span>
              </div>
              <div class="card-list">
                {#each [1, 2, 3] as _}
                  <div class="skeleton-card">
                    <div class="sk-line sk-pill"></div>
                    <div class="sk-line sk-title"></div>
                    <div class="sk-line sk-meta"></div>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      {:else if !currentIntegration && validLiveCards.length === 0}
        <!-- Unconfigured Board Onboarding Empty State -->
        <div class="board-onboarding-state">
          <div class="onboarding-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="32" height="32">
              <rect x="3" y="3" width="18" height="18" rx="2"></rect>
              <line x1="9" y1="3" x2="9" y2="21"></line>
              <line x1="15" y1="3" x2="15" y2="21"></line>
            </svg>
          </div>
          <h3>ยังไม่ได้เชื่อมต่อบอร์ดภายนอกสำหรับโครงการนี้</h3>
          <p>เชื่อมต่อ <strong>Trello Board</strong> หรือ <strong>GitHub Issues</strong> เพื่อดึงการ์ดงานเข้ามาคัดเลือกจัดทำดัชนี RAG และรัน AI Agent Test อัตโนมัติ</p>
          <button type="button" class="btn-primary-cta" on:click={() => (showConfigModal = true)}>
            ตั้งค่าการเชื่อมต่อบอร์ด (Trello / GitHub)
          </button>
        </div>
      {:else if liveLoadError && validLiveCards.length === 0}
        <div class="board-onboarding-state">
          <h3>ไม่สามารถโหลดข้อมูลบอร์ดสดได้</h3>
          <p>{liveLoadError}</p>
          <div style="display: flex; gap: 10px;">
            <button type="button" class="btn-toolbar-sub" on:click={fetchLiveCards}>ลองใหม่อีกครั้ง</button>
            <button type="button" class="btn-primary-cta" on:click={() => (showConfigModal = true)}>ตรวจสอบการตั้งค่า Board</button>
          </div>
        </div>
      {:else}
        <div class="board-layout">
          {#each columns as column}
            {@const colCards = liveCardsByCol[column.id] || []}
            {@const colPts = getColumnPoints(colCards)}
            <div
              class="board-column"
              class:drag-over={dragOverColumnId === column.id}
              on:dragover={(e) => handleDragOver(column.id, e)}
              on:dragleave={() => handleDragLeave(column.id)}
              on:drop={(e) => handleDrop(column.id, e)}
            >
              <div class="column-header">
                <span class="column-dot" style="background-color: {column.color};"></span>
                <span class="column-title">{column.title}</span>
                <div class="column-metrics">
                  <span class="column-pts-pill" title="แต้มรวม Story Points ในคอลัมน์นี้">{colPts} pts</span>
                  <span class="column-count">{colCards.length}</span>
                </div>
              </div>

              <div class="card-list">
                {#each colCards as card (card.id || card.ext_card_id)}
                  {@const prio = getPriorityMeta(card)}
                  {@const selected = isCardSelected(card, selectedCardIds)}
                  <div
                    class="task-card"
                    class:selected
                    class:is-saved={card.is_saved}
                    class:is-unestimated={markUnestimated && isCardUnestimated(card)}
                    class:is-dragging={draggedCard && (draggedCard.id === card.id || draggedCard.raw_ext_id === card.raw_ext_id)}
                    role="button"
                    tabindex="0"
                    draggable="true"
                    on:dragstart={(e) => handleDragStart(card, column.id, e)}
                    on:dragend={handleDragEnd}
                    on:click={() => openCardDetail(card)}
                    on:keydown={(e) => handleCardKeydown(card, e)}
                    aria-label={`การ์ด ${card.title}`}
                  >
                    <div class="card-top-row">
                      <div class="card-labels-group">
                        {#each getCleanLabels(card.labels) as label}
                          <span
                            class="label-pill"
                            style="background-color: {label.color}; color: {label.textColor};"
                          >
                            {label.name}
                          </span>
                        {/each}
                        {#if card.is_saved}
                          <span class="saved-status-pill" title="บันทึกและจัดทำดัชนี RAG แล้ว">
                            บันทึกแล้ว (RAG)
                          </span>
                        {/if}
                      </div>

                      <button
                        type="button"
                        role="checkbox"
                        aria-checked={selected}
                        aria-label={`เลือกการ์ด ${card.title}`}
                        class="card-checkbox-btn"
                        class:checked={selected}
                        on:click|stopPropagation={(e) => toggleSelectCard(card, e)}
                      >
                        {#if selected}
                          <svg aria-hidden="true" viewBox="0 0 16 16" fill="currentColor" width="11" height="11">
                            <path fill-rule="evenodd" d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" clip-rule="evenodd"/>
                          </svg>
                        {/if}
                      </button>
                    </div>

                    <h4 class="card-title">{card.title}</h4>

                    <div class="card-footer">
                      <div class="footer-left-meta">
                        {#if card.description}
                          <span class="desc-indicator" title="มีคำอธิบายรายละเอียด" aria-hidden="true">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
                              <line x1="17" y1="10" x2="3" y2="10"></line>
                              <line x1="21" y1="6" x2="3" y2="6"></line>
                              <line x1="21" y1="14" x2="3" y2="14"></line>
                            </svg>
                          </span>
                        {/if}
                        {#if markUnestimated && isCardUnestimated(card)}
                          <span class="unestimated-pill">Unestimated</span>
                        {:else}
                          <span class="story-points-pill">{card.story_points || "1"} pts</span>
                        {/if}
                        <span class="prio-badge prio-{prio.level}">{prio.label}</span>
                      </div>

                      <div class="footer-right-members">
                        {#each (card.members || []) as member}
                          {#if member.avatar}
                            <img
                              src={member.avatar}
                              alt={member.name}
                              class="member-avatar"
                              loading="lazy"
                              decoding="async"
                              title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}"
                              on:error={handleAvatarError}
                            />
                            <span class="member-initials" style="display: none;" title={member.name}>{member.initials || "M"}</span>
                          {:else}
                            <span class="member-initials" title={member.name}>{member.initials || "M"}</span>
                          {/if}
                        {/each}
                      </div>
                    </div>
                  </div>
                {/each}

                {#if colCards.length === 0}
                  <div class="empty-column">ไม่มีการ์ดในสถานะนี้</div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}

    {:else}
      <!-- TAB 2: SAVED PROJECT CARDS & RAG WORKSPACE -->
      {#if isLoadingSaved && validSavedCards.length === 0}
        <div class="board-layout" aria-live="polite" aria-busy="true">
          {#each columns as col}
            <div class="board-column">
              <div class="column-header">
                <span class="column-dot" style="background-color: {col.color};"></span>
                <span class="column-title">{col.title}</span>
              </div>
              <div class="card-list">
                {#each [1, 2] as _}
                  <div class="skeleton-card">
                    <div class="sk-line sk-pill"></div>
                    <div class="sk-line sk-title"></div>
                    <div class="sk-line sk-meta"></div>
                  </div>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      {:else if validSavedCards.length === 0}
        <div class="board-onboarding-state">
          <div class="onboarding-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="32" height="32">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
            </svg>
          </div>
          <h3>ยังไม่มีการ์ดที่บันทึกในโครงการนี้</h3>
          <p>สลับไปที่แท็บ <strong>"บอร์ด {providerLabel} สด"</strong> เพื่อเลือกการ์ดที่เกี่ยวข้องกับโครงการนี้แล้วกดบันทึกเข้าสู่ระบบ RAG Vector Search</p>
          <button type="button" class="btn-primary-cta" on:click={() => (activeTab = "live")}>
            ไปยังแท็บเลือกการ์ดจากบอร์ด {providerLabel} สด
          </button>
        </div>
      {:else if savedViewMode === "table"}
        <!-- QA EXECUTION TABLE VIEW -->
        <div class="qa-table-shell">
          <table class="qa-exec-table">
            <thead>
              <tr>
                <th>ชื่อการ์ด / ป้ายกำกับ</th>
                <th>สถานะคอลัมน์</th>
                <th>แต้ม / ความสำคัญ</th>
                <th>สถานะ RAG</th>
                <th>ผลทดสอบ AI Agent</th>
                <th class="col-actions-head">การจัดการ</th>
              </tr>
            </thead>
            <tbody>
              {#each flatFilteredSavedCards as card (card.id)}
                {@const verdict = getCardVerdict(card)}
                {@const prio = getPriorityMeta(card)}
                <tr>
                  <td class="cell-title-col">
                    <button type="button" class="table-card-title-btn" on:click={() => openCardDetail(card)}>
                      {card.title}
                    </button>
                    {#if getCleanLabels(card.labels).length > 0}
                      <div class="table-labels-row">
                        {#each getCleanLabels(card.labels) as label}
                          <span class="label-pill" style="background-color: {label.color}; color: {label.textColor};">
                            {label.name}
                          </span>
                        {/each}
                      </div>
                    {/if}
                  </td>
                  <td>
                    <select
                      class="table-status-select"
                      value={card.status || (columns[0]?.id ?? "todo")}
                      aria-label={`เปลี่ยนสถานะของ ${card.title}`}
                      on:change={(e) => moveCardToColumn(card, e.currentTarget.value)}
                    >
                      {#each columns as col}
                        <option value={col.id}>{col.title}</option>
                      {/each}
                    </select>
                  </td>
                  <td>
                    <div class="table-pts-prio">
                      <span class="story-points-pill">{card.story_points || "1"} pts</span>
                      <span class="prio-badge prio-{prio.level}">{prio.label}</span>
                    </div>
                  </td>
                  <td>
                    <span class="rag-indexed-pill">RAG Indexed</span>
                  </td>
                  <td>
                    {#if verdict === "testing"}
                      <span class="verdict-pill testing">กำลังทดสอบ...</span>
                    {:else if verdict === "failed"}
                      <span class="verdict-pill failed">FAILED</span>
                    {:else if verdict === "passed"}
                      <span class="verdict-pill passed">PASSED</span>
                    {:else}
                      <span class="verdict-pill untested">ยังไม่ทดสอบ</span>
                    {/if}
                  </td>
                  <td class="cell-actions-col">
                    <div class="table-action-btns">
                      <button
                        type="button"
                        class="btn-card-action test"
                        on:click={() => handleAgentTest(card)}
                        disabled={verdict === "testing"}
                      >
                        Test Agent
                      </button>
                      <button
                        type="button"
                        class="btn-card-action view"
                        on:click={() => openCardDetail(card)}
                      >
                        เปิดดู
                      </button>
                      <button
                        type="button"
                        class="btn-card-action unsave-table"
                        on:click={(e) => unsaveCard(card, e)}
                        title="ยกเลิกบันทึกออกจากโครงการ"
                      >
                        ยกเลิก
                      </button>
                    </div>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <!-- SAVED KANBAN BOARD VIEW -->
        <div class="board-layout">
          {#each columns as column}
            {@const colCards = savedCardsByCol[column.id] || []}
            {@const colPts = getColumnPoints(colCards)}
            <div
              class="board-column"
              class:drag-over={dragOverColumnId === column.id}
              on:dragover={(e) => handleDragOver(column.id, e)}
              on:dragleave={() => handleDragLeave(column.id)}
              on:drop={(e) => handleDrop(column.id, e)}
            >
              <div class="column-header">
                <span class="column-dot" style="background-color: {column.color};"></span>
                <span class="column-title">{column.title}</span>
                <div class="column-metrics">
                  <span class="column-pts-pill">{colPts} pts</span>
                  <span class="column-count">{colCards.length}</span>
                </div>
              </div>

              <div class="card-list">
                {#each colCards as card (card.id)}
                  {@const verdict = getCardVerdict(card)}
                  {@const prio = getPriorityMeta(card)}
                  <div
                    class="task-card saved-card-item"
                    class:is-unestimated={markUnestimated && isCardUnestimated(card)}
                    class:is-dragging={draggedCard && (draggedCard.id === card.id || draggedCard.raw_ext_id === card.raw_ext_id)}
                    role="button"
                    tabindex="0"
                    draggable="true"
                    on:dragstart={(e) => handleDragStart(card, column.id, e)}
                    on:dragend={handleDragEnd}
                    on:click={() => openCardDetail(card)}
                    on:keydown={(e) => handleCardKeydown(card, e)}
                    aria-label={`การ์ดที่บันทึก ${card.title}`}
                  >
                    <div class="saved-top-badge-row">
                      <span class="rag-indexed-pill">RAG Indexed</span>
                      {#if verdict === "testing"}
                        <span class="verdict-pill testing">กำลังทดสอบ...</span>
                      {:else if verdict === "failed"}
                        <span class="verdict-pill failed">FAILED</span>
                      {:else if verdict === "passed"}
                        <span class="verdict-pill passed">PASSED</span>
                      {/if}
                    </div>

                    {#if getCleanLabels(card.labels).length > 0}
                      <div class="card-labels-group">
                        {#each getCleanLabels(card.labels) as label}
                          <span class="label-pill" style="background-color: {label.color}; color: {label.textColor};">
                            {label.name}
                          </span>
                        {/each}
                      </div>
                    {/if}

                    <h4 class="card-title">{card.title}</h4>

                    <div class="card-footer">
                      <div class="footer-left-meta">
                        {#if markUnestimated && isCardUnestimated(card)}
                          <span class="unestimated-pill">Unestimated</span>
                        {:else}
                          <span class="story-points-pill">{card.story_points || "1"} pts</span>
                        {/if}
                        <span class="prio-badge prio-{prio.level}">{prio.label}</span>
                      </div>

                      <div class="footer-right-members">
                        {#each (card.members || []) as member}
                          {#if member.avatar}
                            <img
                              src={member.avatar}
                              alt={member.name}
                              class="member-avatar"
                              loading="lazy"
                              decoding="async"
                              title={member.name}
                              on:error={handleAvatarError}
                            />
                            <span class="member-initials" style="display: none;" title={member.name}>{member.initials || "M"}</span>
                          {:else}
                            <span class="member-initials" title={member.name}>{member.initials || "M"}</span>
                          {/if}
                        {/each}
                      </div>
                    </div>

                    <div class="saved-card-actions-bar">
                      <button
                        type="button"
                        class="btn-card-action test"
                        on:click|stopPropagation={() => handleAgentTest(card)}
                        disabled={verdict === "testing"}
                      >
                        {#if verdict === "testing"}
                          <span class="spinner-small"></span> กำลังทดสอบ...
                        {:else}
                          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" width="12" height="12">
                            <polygon points="5 3 19 12 5 21 5 3"></polygon>
                          </svg>
                          Test Agent
                        {/if}
                      </button>
                      <button
                        type="button"
                        class="btn-card-action unsave"
                        on:click|stopPropagation={(e) => unsaveCard(card, e)}
                        title="ยกเลิกการบันทึกการ์ดออกจากโครงการ"
                      >
                        ยกเลิก
                      </button>
                    </div>
                  </div>
                {/each}

                {#if colCards.length === 0}
                  <div class="empty-column">ไม่มีการ์ดในสถานะนี้</div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</div>

<!-- Modular Card Detail Modal -->
<QABoardCardModal
  bind:this={cardModalRef}
  {showDetailModal}
  {selectedCard}
  {columns}
  {currentIntegration}
  {selectedProjectId}
  {isSavingSelected}
  bind:newCommentText
  bind:commentAttachments
  {isSendingComment}
  {isUploadingAttachment}
  on:close={closeCardDetail}
  on:saveSingle={(e) => saveSingleCard(e.detail)}
  on:unsave={(e) => unsaveCard(e.detail.card, e.detail.event)}
  on:moveCard={(e) => moveCardToColumn(e.detail.card, e.detail.targetColumnId)}
  on:runAgentTest={(e) => handleAgentTest(e.detail)}
  on:previewImage={(e) => openImagePreview(e.detail.url, e.detail.alt)}
  on:commentPaste={(e) => handleCommentPaste(e.detail)}
  on:fileChange={(e) => handleFileInputChange(e.detail)}
  on:removeAttachment={(e) => removeCommentAttachment(e.detail)}
  on:postComment={postComment}
/>

<!-- Modular Secondary Modals (Config, Agile Tools, Filter, Lightbox) -->
<QABoardModals
  {showConfigModal}
  bind:configProvider
  bind:trelloApiKey
  bind:trelloToken
  bind:trelloBoardId
  bind:githubToken
  bind:githubOwner
  bind:githubRepo
  {isTestingConnection}
  {isSavingConfig}
  bind:configErrors
  {showAgileSummaryModal}
  bind:markUnestimated
  {agilePointsSummary}
  {showFilterModal}
  {activeTab}
  bind:cardSearchQuery
  bind:filterNoMembers
  {selectedMemberIds}
  bind:filterNoLabels
  {selectedLabelNames}
  bind:filterSavedStatus
  bind:filterCompletion
  {filterTypes}
  {boardMembersList}
  {boardLabelsList}
  {boardTypesList}
  {activeFilterCount}
  {totalFilteredCardsCount}
  {showImageModal}
  {previewModalImage}
  {previewModalAlt}
  on:closeConfig={() => (showConfigModal = false)}
  on:testConnection={testConnection}
  on:saveConfig={saveBoardIntegration}
  on:closeAgile={() => (showAgileSummaryModal = false)}
  on:closeFilter={() => (showFilterModal = false)}
  on:toggleMember={(e) => toggleMemberFilter(e.detail)}
  on:clearMembers={() => (selectedMemberIds = new Set())}
  on:toggleLabel={(e) => toggleLabelFilter(e.detail)}
  on:clearLabels={() => (selectedLabelNames = new Set())}
  on:toggleType={(e) => toggleTypeFilter(e.detail)}
  on:resetFilters={resetAllFilters}
  on:closeImage={() => (showImageModal = false)}
/>

<!-- Smart AI Test Launcher Modal -->
{#if isTestModalOpen}
  <SmartTestLauncherModal
    projectId={selectedProjectId}
    projectName={$selectedProjectStore?.name || $selectedProjectStore?.project_name || "Project"}
    cardData={testTargetCard}
    isOpen={isTestModalOpen}
    on:close={handleTestModalClose}
    on:test_completed={handleTestCompleted}
  />
{/if}

<ConfirmModal
  bind:open={confirmOpen}
  title={confirmTitle}
  message={confirmMessage}
  confirmText="ยืนยันการลบ"
  on:confirm={() => confirmAction && confirmAction()}
/>

<style>
  .board-container {
    padding: 16px 20px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 14px;
    overflow-y: auto;
    box-sizing: border-box;
    font-family: var(--font-th);
    color: var(--text-main);
  }

  /* Distilled 2-Row Top Chrome */
  .board-chrome-shell {
    background: var(--bg2);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: 12px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex-shrink: 0;
  }

  .chrome-row-primary,
  .chrome-row-secondary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .chrome-row-secondary {
    padding-top: 10px;
    border-top: 1px solid var(--glass-border);
  }

  .chrome-brand-group,
  .chrome-primary-right,
  .secondary-left,
  .secondary-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .btn-back-compact {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-height: 34px;
    padding: 6px 11px;
    border-radius: var(--radius-sm);
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: color 0.16s ease, border-color 0.16s ease, background-color 0.16s ease;
  }

  .btn-back-compact:hover {
    color: var(--text-main);
    background: var(--surface-card-hover);
    border-color: var(--glass-border-light);
  }

  .project-title-line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .board-title {
    margin: 0;
    font-size: 16px;
    font-weight: 700;
    color: var(--text-main);
    font-family: var(--font-en);
  }

  .active-project-pill {
    padding: 3px 10px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: var(--primary-soft-text);
    font-size: 12px;
    font-weight: 600;
  }

  .integration-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11.5px;
    font-weight: 600;
    font-family: inherit;
  }

  .integration-pill.connected {
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.32);
    color: var(--success-soft-text);
  }

  .integration-pill .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--success);
  }

  .integration-pill.unconfigured {
    background: rgba(245, 158, 11, 0.14);
    border: 1px solid rgba(245, 158, 11, 0.36);
    color: var(--warning-soft-text);
    cursor: pointer;
  }

  /* Main Tab Switcher */
  .main-tab-switcher {
    display: inline-flex;
    background: var(--bg);
    padding: 3px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border);
    gap: 4px;
  }

  .main-tab-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 32px;
    padding: 5px 12px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: background-color 0.16s ease, color 0.16s ease;
  }

  .main-tab-btn.active {
    background: rgba(99, 102, 241, 0.22);
    color: var(--text-main);
  }

  .tab-count-pill {
    padding: 1px 7px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    font-size: 11px;
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
  }

  .tab-count-pill.saved {
    background: rgba(168, 85, 247, 0.22);
    color: var(--primary-soft-text-hover);
  }

  .btn-chrome-tool,
  .btn-toolbar-sub,
  .btn-toolbar-danger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    font-size: 12.5px;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: color 0.16s ease, border-color 0.16s ease, background-color 0.16s ease;
  }

  .btn-chrome-tool:hover,
  .btn-toolbar-sub:hover:not(:disabled) {
    color: var(--text-main);
    background: var(--surface-card-hover);
    border-color: var(--glass-border-light);
  }

  .btn-toolbar-sub:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .btn-toolbar-sub.active-filter {
    background: rgba(99, 102, 241, 0.18);
    border-color: var(--primary-soft-text);
    color: var(--text-main);
  }

  .btn-toolbar-danger {
    color: var(--danger-soft-text);
    border-color: rgba(244, 63, 94, 0.3);
  }

  .btn-toolbar-danger:hover {
    background: rgba(244, 63, 94, 0.16);
    color: var(--danger-soft-text-hover);
  }

  .pts-chip,
  .filter-badge-count {
    padding: 1px 7px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.22);
    color: var(--primary-soft-text-hover);
    font-size: 11px;
    font-weight: 700;
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
  }

  .selection-readout,
  .rag-ready-hint {
    font-size: 12.5px;
    color: var(--text-muted);
  }

  .selection-readout strong {
    color: var(--primary-soft-text-hover);
    font-variant-numeric: tabular-nums;
  }

  .view-mode-segmented {
    display: inline-flex;
    background: var(--bg);
    padding: 3px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border);
    gap: 3px;
  }

  .seg-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .seg-btn.active {
    background: var(--surface-card-hover);
    color: var(--text-main);
  }

  .search-box-compact {
    position: relative;
    display: flex;
    align-items: center;
    gap: 7px;
    background: var(--bg);
    border: 1px solid var(--glass-border-light);
    border-radius: var(--radius-sm);
    padding: 0 10px;
    min-height: 34px;
    width: clamp(190px, 20vw, 270px);
    color: var(--text-muted);
  }

  .search-box-compact:focus-within {
    border-color: var(--primary);
  }

  .search-box-compact input {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main);
    font-size: 12.5px;
    font-family: inherit;
  }

  .btn-clear-query {
    background: transparent;
    border: none;
    color: var(--text-dim);
    cursor: pointer;
    padding: 2px 4px;
  }

  .btn-primary-cta {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    min-height: 34px;
    padding: 6px 14px;
    border-radius: var(--radius-sm);
    background: var(--gradient-main);
    border: 1px solid rgba(129, 140, 248, 0.45);
    color: #ffffff;
    font-size: 12.5px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .btn-primary-cta:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  /* Active Filter Strip */
  .active-filters-strip {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding-top: 8px;
    border-top: 1px solid var(--glass-border);
    font-size: 12px;
  }

  .strip-label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .filter-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 9px;
    border-radius: 999px;
    background: var(--surface-card);
    border: 1px solid var(--glass-border-light);
    color: var(--text-main);
    font-size: 11.5px;
  }

  .filter-chip button {
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 2px;
  }

  .btn-clear-all-filters {
    background: transparent;
    border: none;
    color: var(--danger-soft-text);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    margin-left: auto;
    font-family: inherit;
  }

  /* Kanban Board Columns */
  .board-layout {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(4, minmax(260px, 1fr));
    gap: 14px;
    overflow-x: auto;
    align-items: stretch;
  }

  .board-column {
    background: var(--bg2);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
    min-height: 460px;
    max-height: calc(100dvh - 235px);
    overflow: hidden;
    transition: border-color 0.16s ease, background-color 0.16s ease;
  }

  .board-column.drag-over {
    border-color: var(--primary);
    background: rgba(99, 102, 241, 0.06);
  }

  .column-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 14px;
    background: var(--bg);
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }

  .column-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .column-title {
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-main);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .column-metrics {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .column-pts-pill {
    padding: 2px 7px;
    border-radius: 999px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: var(--primary-soft-text);
    font-size: 11px;
    font-weight: 600;
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
  }

  .column-count {
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--surface-card);
    color: var(--text-muted);
    font-size: 11.5px;
    font-weight: 700;
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
  }

  .card-list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  /* Task Cards */
  .task-card {
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 9px;
    cursor: pointer;
    transition: background-color 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
  }

  .task-card:hover {
    background: var(--surface-card-hover);
    border-color: rgba(168, 85, 247, 0.34);
    transform: translateY(-1px);
  }

  .task-card.selected {
    background: var(--surface-card-unread);
    border-color: var(--primary);
    box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.35);
  }

  .task-card.is-unestimated {
    border-color: rgba(245, 158, 11, 0.45);
  }

  .task-card.is-dragging {
    opacity: 0.45;
  }

  .card-top-row,
  .saved-top-badge-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
  }

  .card-labels-group {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    flex: 1;
    min-width: 0;
  }

  .label-pill {
    padding: 2px 8px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .saved-status-pill,
  .rag-indexed-pill {
    padding: 2px 8px;
    border-radius: 999px;
    background: rgba(16, 185, 129, 0.14);
    border: 1px solid rgba(16, 185, 129, 0.32);
    color: var(--success-soft-text);
    font-size: 10.5px;
    font-weight: 600;
    white-space: nowrap;
  }

  .verdict-pill {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 10.5px;
    font-weight: 700;
    font-family: var(--font-en);
    white-space: nowrap;
  }

  .verdict-pill.passed {
    background: rgba(16, 185, 129, 0.16);
    border: 1px solid rgba(16, 185, 129, 0.38);
    color: var(--success-soft-text);
  }

  .verdict-pill.failed {
    background: rgba(244, 63, 94, 0.16);
    border: 1px solid rgba(244, 63, 94, 0.4);
    color: var(--danger-soft-text);
  }

  .verdict-pill.testing {
    background: rgba(168, 85, 247, 0.18);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: var(--primary-soft-text-hover);
  }

  .verdict-pill.untested {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-dim);
  }

  .card-checkbox-btn {
    width: 24px;
    height: 24px;
    border-radius: 6px;
    background: var(--bg);
    border: 1px solid var(--glass-border-light);
    color: #ffffff;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    padding: 0;
  }

  .card-checkbox-btn.checked {
    background: var(--primary);
    border-color: var(--primary);
  }

  .card-title {
    margin: 0;
    font-size: 13.2px;
    font-weight: 600;
    color: var(--text-main);
    line-height: 1.45;
    word-break: break-word;
  }

  .card-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-top: 2px;
  }

  .footer-left-meta {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }

  .desc-indicator {
    color: var(--text-dim);
    display: inline-flex;
    align-items: center;
  }

  .story-points-pill {
    padding: 2px 7px;
    border-radius: 5px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.28);
    color: var(--primary-soft-text);
    font-size: 11px;
    font-weight: 600;
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
  }

  .unestimated-pill {
    padding: 2px 7px;
    border-radius: 5px;
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.38);
    color: var(--warning-soft-text);
    font-size: 11px;
    font-weight: 600;
  }

  .prio-badge {
    padding: 2px 7px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 500;
    background: rgba(255, 255, 255, 0.05);
    color: var(--text-muted);
  }

  .prio-badge.prio-high {
    background: rgba(244, 63, 94, 0.14);
    color: var(--danger-soft-text);
  }

  .footer-right-members {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .member-avatar {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    object-fit: cover;
    border: 1px solid var(--glass-border-light);
  }

  .member-initials {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(99, 102, 241, 0.34);
    color: var(--primary-soft-text);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 10.5px;
    font-weight: 700;
  }

  /* Saved Card Progressive Action Bar */
  .saved-card-actions-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
    padding-top: 8px;
    border-top: 1px solid var(--glass-border);
  }

  .btn-card-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    transition: opacity 0.16s ease, background-color 0.16s ease, color 0.16s ease;
  }

  .btn-card-action.test {
    background: rgba(168, 85, 247, 0.16);
    border: 1px solid rgba(168, 85, 247, 0.36);
    color: var(--primary-soft-text-hover);
  }

  .btn-card-action.test:hover:not(:disabled) {
    background: rgba(168, 85, 247, 0.28);
  }

  .btn-card-action.view {
    background: var(--surface-card);
    border: 1px solid var(--glass-border-light);
    color: var(--text-main);
  }

  .btn-card-action.unsave {
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-dim);
    opacity: 0;
  }

  .task-card:hover .btn-card-action.unsave,
  .task-card:focus-within .btn-card-action.unsave,
  .btn-card-action.unsave:focus-visible {
    opacity: 1;
  }

  .btn-card-action.unsave:hover,
  .btn-card-action.unsave-table:hover {
    color: var(--danger-soft-text);
    background: rgba(244, 63, 94, 0.14);
    border-color: rgba(244, 63, 94, 0.3);
  }

  .btn-card-action.unsave-table {
    background: transparent;
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
  }

  /* QA Execution Table View */
  .qa-table-shell {
    flex: 1;
    min-height: 0;
    overflow: auto;
    background: var(--bg2);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-md);
  }

  .qa-exec-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    text-align: left;
  }

  .qa-exec-table th {
    position: sticky;
    top: 0;
    background: var(--bg);
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 600;
    padding: 12px 14px;
    border-bottom: 1px solid var(--glass-border);
    z-index: 2;
  }

  .qa-exec-table td {
    padding: 12px 14px;
    border-bottom: 1px solid var(--glass-border);
    vertical-align: middle;
  }

  .qa-exec-table tbody tr:hover {
    background: var(--surface-card);
  }

  .table-card-title-btn {
    background: transparent;
    border: none;
    color: var(--text-main);
    font-size: 13.5px;
    font-weight: 600;
    text-align: left;
    cursor: pointer;
    padding: 0;
    font-family: inherit;
  }

  .table-card-title-btn:hover {
    color: var(--primary-soft-text-hover);
    text-decoration: underline;
  }

  .table-labels-row {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 6px;
  }

  .table-status-select {
    min-height: 32px;
    padding: 4px 28px 4px 10px;
    font-size: 12.5px;
    background-color: var(--surface-card);
  }

  .table-pts-prio,
  .table-action-btns {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .col-actions-head,
  .cell-actions-col {
    text-align: right;
  }

  .cell-actions-col .table-action-btns {
    justify-content: flex-end;
  }

  /* Empty & Onboarding & Skeleton States */
  .empty-column {
    padding: 28px 12px;
    text-align: center;
    color: var(--text-dim);
    font-size: 12.5px;
    border: 1px dashed var(--glass-border);
    border-radius: var(--radius-sm);
  }

  .board-onboarding-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 48px 24px;
    background: var(--bg2);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    gap: 12px;
  }

  .onboarding-icon {
    width: 60px;
    height: 60px;
    border-radius: 16px;
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(99, 102, 241, 0.32);
    color: var(--primary-soft-text);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .board-onboarding-state h3 {
    margin: 0;
    font-size: 17px;
    font-weight: 700;
    color: var(--text-main);
  }

  .board-onboarding-state p {
    margin: 0;
    max-width: 48ch;
    font-size: 13.5px;
    color: var(--text-muted);
    line-height: 1.55;
  }

  .skeleton-card {
    padding: 14px;
    border-radius: var(--radius-md);
    background: var(--surface-card);
    border: 1px solid var(--glass-border);
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .sk-line {
    height: 12px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.06);
  }

  .sk-pill { width: 38%; height: 16px; }
  .sk-title { width: 88%; height: 14px; }
  .sk-meta { width: 55%; }

  .spinning {
    animation: spinBoard 0.9s linear infinite;
  }

  .spinner-small {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.28);
    border-top-color: currentColor;
    border-radius: 50%;
    display: inline-block;
    animation: spinBoard 0.75s linear infinite;
  }

  @keyframes spinBoard { to { transform: rotate(360deg); } }

  @media (hover: none), (pointer: coarse) {
    .btn-card-action.unsave {
      opacity: 0.9;
    }
    .card-checkbox-btn {
      width: 32px;
      height: 32px;
    }
  }

  @media (max-width: 1100px) {
    .board-layout {
      grid-template-columns: repeat(2, minmax(260px, 1fr));
    }
  }

  @media (max-width: 640px) {
    .board-layout {
      grid-template-columns: 1fr;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinning,
    .spinner-small {
      animation: none;
    }
    .task-card,
    .task-card:hover {
      transform: none;
      transition: none;
    }
  }
</style>
