<script>
  import { onMount, onDestroy } from "svelte";
  import { fade, slide, fly, scale } from "svelte/transition";
  import { selectedProjectStore } from "./qaHistoryStore.js";
  import ProjectSelection from "./ProjectSelection.svelte";
  import { toast } from "./toastStore.js";
  import SmartTestLauncherModal from "./SmartTestLauncherModal.svelte";

  let projects = [];
  let isTestModalOpen = false;
  let testTargetCard = null;

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

  // Active Tab state: 'live' (Trello Board Selector) | 'saved' (Saved Project Cards & RAG)
  let activeTab = 'live';

  // Board columns
  let columns = [
    { id: 'todo', title: 'To Do', color: '#64748b' },
    { id: 'in_progress', title: 'In Progress', color: '#3b82f6' },
    { id: 'testing', title: 'Testing (Agent)', color: '#a855f7' },
    { id: 'done', title: 'Done', color: '#22c55e' }
  ];

  // Cards data
  let liveCards = [];
  let savedCards = [];
  let isLoadingLive = false;
  let isLoadingSaved = false;
  let isSavingSelected = false;
  let cardSearchQuery = "";

  // Selection state for Live Board
  let selectedCardIds = new Set();

  // Detail Modal state
  let showDetailModal = false;
  let selectedCard = null;
  let showComments = true;

  // Image Lightbox Preview state
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
  let configProvider = 'trello'; // 'trello' | 'github'
  let trelloApiKey = '';
  let trelloToken = '';
  let trelloBoardId = '';
  let githubToken = '';
  let githubOwner = '';
  let githubRepo = '';
  let isTestingConnection = false;
  let isSavingConfig = false;

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
          // Unconfigured board
        } else {
          toast(data.error || "เกิดข้อผิดพลาดในการดึงข้อมูล Live Board", "error");
        }
      }
    } catch (err) {
      console.error("Error fetching live cards:", err);
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
      }
    } catch (err) {
      console.error("Error fetching saved cards:", err);
    } finally {
      isLoadingSaved = false;
    }
  }

  async function fetchCards() {
    await Promise.all([fetchLiveCards(), fetchSavedCards()]);
  }

  // Selection handlers
  function toggleSelectCard(card, event) {
    if (event) event.stopPropagation();
    const key = card.ext_card_id || card.raw_ext_id || card.id;
    if (selectedCardIds.has(key)) {
      selectedCardIds.delete(key);
    } else {
      selectedCardIds.add(key);
    }
    selectedCardIds = new Set(selectedCardIds);
  }

  function isCardSelected(card, _tracker = null) {
    const key = card.ext_card_id || card.raw_ext_id || card.id;
    return selectedCardIds.has(key);
  }

  function selectAllLiveCards() {
    const colTitles = columns.map(c => c.title);
    liveCards.forEach(c => {
      if (!isHeaderCard(c.title, colTitles)) {
        const key = c.ext_card_id || c.raw_ext_id || c.id;
        selectedCardIds.add(key);
      }
    });
    selectedCardIds = new Set(selectedCardIds);
  }

  function clearCardSelection() {
    selectedCardIds = new Set();
  }

  // Save selected cards into project and ingest to RAG
  async function saveSelectedCardsToProject() {
    if (selectedCardIds.size === 0) {
      toast("กรุณาเลือก Card ที่ต้องการบันทึกอย่างน้อย 1 ใบ", "warning");
      return;
    }

    const chosenCards = liveCards.filter(c => isCardSelected(c));
    if (chosenCards.length === 0) {
      toast("ไม่พบข้อมูล Card ที่เลือก", "error");
      return;
    }

    isSavingSelected = true;
    toast(`กำลังบันทึก ${chosenCards.length} Card เข้าโครงการ & RAG...`, "info");
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/save-selected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cards: chosenCards })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.message || `บันทึก Card สำเร็จ ${chosenCards.length} ใบ!`, "success");
        clearCardSelection();
        await fetchCards();
      } else {
        toast(data.error || "บันทึก Card ไม่สำเร็จ", "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการบันทึก: ${err.message}`, "error");
    } finally {
      isSavingSelected = false;
    }
  }

  // Save single card from modal
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
        toast(data.message || "บันทึก Card สำเร็จ!", "success");
        await fetchCards();
        if (selectedCard) {
          selectedCard = { ...selectedCard, is_saved: true };
        }
      } else {
        toast(data.error || "บันทึก Card ไม่สำเร็จ", "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาดในการบันทึก: ${err.message}`, "error");
    } finally {
      isSavingSelected = false;
    }
  }

  // Unsave card from project and remove from RAG
  async function unsaveCard(card, event) {
    if (event) event.stopPropagation();
    const cTitle = card.title || 'Card นี้';
    if (!confirm(`คุณต้องการยกเลิกการบันทึก "${cTitle}" ออกจากโครงการนี้ใช่หรือไม่? (จะนำออกจาก RAG ด้วย)`)) {
      return;
    }

    const cardId = card.saved_id || card.id;
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/${cardId}`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.message || "ยกเลิกการบันทึก Card สำเร็จ", "success");
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
  }

  // Clear all saved cards from project and RAG
  async function clearAllSavedCards() {
    if (savedCards.length === 0) return;
    if (!confirm(`คุณต้องการลบ Card ที่บันทึกไว้ทั้งหมด ${savedCards.length} ใบออกจากโครงการนี้และ RAG ใช่หรือไม่?`)) {
      return;
    }
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/clear-all`, {
        method: "POST"
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.message || "ล้าง Card ที่บันทึกทั้งหมดเรียบร้อยแล้ว", "success");
        await fetchCards();
      } else {
        toast(data.error || "ล้าง Card ไม่สำเร็จ", "error");
      }
    } catch (err) {
      toast(`เกิดข้อผิดพลาด: ${err.message}`, "error");
    }
  }

  // Smart AI Test Launcher handlers
  function handleAgentTest(cardOrId) {
    if (typeof cardOrId === 'object' && cardOrId !== null) {
      testTargetCard = cardOrId;
    } else if (selectedCard) {
      testTargetCard = selectedCard;
    } else {
      testTargetCard = { title: "Feature Testing", description: "" };
    }
    isTestModalOpen = true;
  }

  function handleTestCompleted(e) {
    const result = e.detail;
    if (selectedCard) {
      selectedCard.test_result = result.test_result_markdown;
      selectedCard.verdict = result.verdict;
      selectedCard.isTesting = false;
      selectedCard = { ...selectedCard };
    }
    fetchCards();
    toast(`รันการทดสอบสำเร็จ: ${result.verdict}`, result.is_passed ? "success" : "warning");
  }

  async function fetchBoardIntegration() {
    if (!selectedProjectId) return;
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/board-integration`);
      const data = await res.json();
      if (data.success && data.integration) {
        currentIntegration = data.integration;
        configProvider = data.integration.provider || 'trello';
        trelloApiKey = data.integration.trello_api_key || '';
        trelloToken = data.integration.trello_token || '';
        trelloBoardId = data.integration.trello_board_id || '';
        githubToken = data.integration.github_token || '';
        githubOwner = data.integration.github_owner || '';
        githubRepo = data.integration.github_repo || '';
      } else {
        currentIntegration = null;
      }
    } catch (err) {
      console.error("Error fetching board integration:", err);
    }
  }

  async function testConnection() {
    if (!selectedProjectId) return;
    isTestingConnection = true;
    try {
      const payload = {
        provider: configProvider,
        trello_api_key: trelloApiKey,
        trello_token: trelloToken,
        trello_board_id: trelloBoardId,
        github_token: githubToken,
        github_owner: githubOwner,
        github_repo: githubRepo
      };
      const res = await fetch(`/api/projects/${selectedProjectId}/board-integration/test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      let data = {};
      try { data = await res.json(); } catch(e) {}
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
    if (!selectedProjectId) return;
    isSavingConfig = true;
    try {
      const payload = {
        provider: configProvider,
        trello_api_key: trelloApiKey,
        trello_token: trelloToken,
        trello_board_id: trelloBoardId,
        github_token: githubToken,
        github_owner: githubOwner,
        github_repo: githubRepo
      };
      const res = await fetch(`/api/projects/${selectedProjectId}/board-integration`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      let data = {};
      try { data = await res.json(); } catch(e) {}
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

  function isHeaderCard(title, colTitles = []) {
    const t = (title || '').trim().toLowerCase();
    if (!t) return true;

    const defaultHeaders = [
      'deploy', 'review', 'to do', 'todo', 'doing', 'in progress', 'testing', 
      'testing (agent)', 'template & plan', 'done', 'backlog', 'done back log',
      'done (current sprint card)', 'done (back log card)'
    ];
    if (defaultHeaders.includes(t)) return true;

    for (const c of colTitles) {
      const cLow = (c || '').trim().toLowerCase();
      if (cLow && (t === cLow || t.startsWith(cLow + ' (') || t.startsWith(cLow + '('))) {
        return true;
      }
    }

    const headerKeywords = ['sprint card', 'back log card', 'backlog card', 'header card', 'placeholder card', 'section header', 'separator'];
    if (headerKeywords.some(kw => t.includes(kw))) {
      return true;
    }

    return false;
  }

  // Filter & Agile Tools Modal state
  let showFilterModal = false;
  let showAgileSummaryModal = false;
  let markUnestimated = false;

  let filterNoMembers = false;
  let selectedMemberIds = new Set();
  let filterNoLabels = false;
  let selectedLabelNames = new Set();
  let filterSavedStatus = 'all'; // 'all' | 'saved' | 'unsaved'
  let filterCompletion = 'all'; // 'all' | 'complete' | 'incomplete'
  let filterTypes = new Set();

  function toggleMemberFilter(mId) {
    if (selectedMemberIds.has(mId)) {
      selectedMemberIds.delete(mId);
    } else {
      selectedMemberIds.add(mId);
    }
    selectedMemberIds = new Set(selectedMemberIds);
  }

  function toggleLabelFilter(lName) {
    const lLow = (lName || '').toLowerCase();
    if (selectedLabelNames.has(lLow)) {
      selectedLabelNames.delete(lLow);
    } else {
      selectedLabelNames.add(lLow);
    }
    selectedLabelNames = new Set(selectedLabelNames);
  }

  function toggleTypeFilter(tName) {
    if (filterTypes.has(tName)) {
      filterTypes.delete(tName);
    } else {
      filterTypes.add(tName);
    }
    filterTypes = new Set(filterTypes);
  }

  function resetAllFilters() {
    cardSearchQuery = "";
    filterNoMembers = false;
    selectedMemberIds = new Set();
    filterNoLabels = false;
    selectedLabelNames = new Set();
    filterSavedStatus = 'all';
    filterCompletion = 'all';
    filterTypes = new Set();
  }

  // Board members list with unique members from loaded cards
  $: boardMembersList = (() => {
    const map = new Map();
    const source = liveCards.length > 0 ? liveCards : savedCards;
    source.forEach(c => {
      (c.members || []).forEach(m => {
        const id = m.id || m.username || m.name;
        if (id && !map.has(id)) {
          map.set(id, m);
        }
      });
    });
    return Array.from(map.values());
  })();

  // Board labels list with colors & counts
  $: boardLabelsList = (() => {
    const map = new Map();
    const source = liveCards.length > 0 ? liveCards : savedCards;
    source.forEach(c => {
      (c.labels || []).forEach(l => {
        const rawName = typeof l === 'string' ? l : (l.name || '');
        const cleanName = rawName.replace(/[*_`~#]/g, '').trim();
        const lower = cleanName.toLowerCase();
        if (cleanName && !map.has(lower)) {
          map.set(lower, {
            name: cleanName,
            color: l.color || '#38bdf8',
            count: 0
          });
        }
        if (cleanName && map.has(lower)) {
          map.get(lower).count += 1;
        }
      });
    });
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  })();

  // Agile Tools Story Points summary calculation
  $: agilePointsSummary = (() => {
    let totalPoints = 0;
    let totalCards = 0;
    let unestimatedCards = 0;
    const byColumn = {};

    columns.forEach(col => {
      byColumn[col.id] = { id: col.id, title: col.title, color: col.color, points: 0, count: 0 };
    });

    const targetList = activeTab === 'live' ? liveCards : savedCards;
    const colTitles = columns.map(c => c.title);

    targetList.forEach(c => {
      if (isHeaderCard(c.title, colTitles)) return;
      const pts = parseFloat(c.story_points);
      const pointsVal = !isNaN(pts) ? pts : 0;
      if (isNaN(pts) || pts === 0) {
        unestimatedCards += 1;
      }
      totalPoints += pointsVal;
      totalCards += 1;

      const colId = c.status && byColumn[c.status] ? c.status : (columns[0] ? columns[0].id : 'todo');
      if (byColumn[colId]) {
        byColumn[colId].points += pointsVal;
        byColumn[colId].count += 1;
      }
    });

    return {
      totalPoints: Math.round(totalPoints * 10) / 10,
      totalCards,
      unestimatedCards,
      columnsSummary: Object.values(byColumn)
    };
  })();

  // Active filter count
  $: activeFilterCount = (cardSearchQuery.trim() ? 1 : 0)
    + (filterNoMembers ? 1 : 0)
    + selectedMemberIds.size
    + (filterNoLabels ? 1 : 0)
    + selectedLabelNames.size
    + (filterSavedStatus !== 'all' ? 1 : 0)
    + (filterCompletion !== 'all' ? 1 : 0)
    + filterTypes.size;

  // Memoized card mapping by column with rich filters
  function computeCardsByColumn(cardsList, cols, query, noMembers, memberIds, noLabels, labelNames, savedStatus, completion, types) {
    const colTitles = cols.map(c => c.title);
    const q = (query || '').trim().toLowerCase();
    const result = {};
    cols.forEach(c => { result[c.id] = []; });
    const defaultColId = cols.length > 0 ? cols[0].id : 'todo';

    for (let i = 0; i < cardsList.length; i++) {
      const c = cardsList[i];
      if (isHeaderCard(c.title, colTitles)) continue;

      if (q) {
        const matchTitle = (c.title || '').toLowerCase().includes(q);
        const matchDesc = (c.description || '').toLowerCase().includes(q);
        const matchId = (c.ext_card_id || '').toLowerCase().includes(q);
        const matchLabels = (c.labels || []).some(l => ((typeof l === 'string' ? l : l.name) || '').toLowerCase().includes(q));
        const matchMembers = (c.members || []).some(m => ((m.name || '') + ' ' + (m.username || '')).toLowerCase().includes(q));
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
          const rawName = typeof l === 'string' ? l : (l.name || '');
          const cleanName = rawName.replace(/[*_`~#]/g, '').trim().toLowerCase();
          return labelNames.has(cleanName);
        });
        if (!hasMatch) continue;
      }

      if (savedStatus === 'saved' && !c.is_saved) continue;
      if (savedStatus === 'unsaved' && c.is_saved) continue;

      if (completion === 'complete') {
        const isDone = c.status === 'done' || (c.status && c.status.toLowerCase().includes('done'));
        if (!isDone) continue;
      } else if (completion === 'incomplete') {
        const isDone = c.status === 'done' || (c.status && c.status.toLowerCase().includes('done'));
        if (isDone) continue;
      }

      if (types && types.size > 0) {
        if (!types.has(c.type || 'Feature')) continue;
      }

      const colId = c.status && result[c.status] ? c.status : defaultColId;
      if (!result[colId]) result[colId] = [];
      result[colId].push(c);
    }
    return result;
  }

  $: liveCardsByCol = computeCardsByColumn(liveCards, columns, cardSearchQuery, filterNoMembers, selectedMemberIds, filterNoLabels, selectedLabelNames, filterSavedStatus, filterCompletion, filterTypes);
  $: savedCardsByCol = computeCardsByColumn(savedCards, columns, cardSearchQuery, filterNoMembers, selectedMemberIds, filterNoLabels, selectedLabelNames, 'all', filterCompletion, filterTypes);

  $: totalFilteredLiveCardsCount = Object.values(liveCardsByCol).reduce((acc, list) => acc + list.length, 0);
  $: totalFilteredSavedCardsCount = Object.values(savedCardsByCol).reduce((acc, list) => acc + list.length, 0);
  $: totalFilteredCardsCount = activeTab === 'live' ? totalFilteredLiveCardsCount : totalFilteredSavedCardsCount;

  function getCleanLabels(labels) {
    if (!labels || !Array.isArray(labels)) return [];
    const seen = new Set();
    const result = [];
    for (const l of labels) {
      const rawName = typeof l === 'string' ? l : (l.name || '');
      const name = rawName.replace(/[*_`~#]/g, '').trim();
      const lower = name.toLowerCase();
      if (name && !seen.has(lower)) {
        seen.add(lower);
        result.push(typeof l === 'string' ? { name, color: '#38bdf8' } : { ...l, name });
      }
    }
    return result;
  }

  function parseCommentSegments(rawText, pId) {
    if (!rawText) return [];

    const isVideoExt = (url) => {
      const u = url.toLowerCase().split('?')[0];
      return u.endsWith('.mp4') || u.endsWith('.webm') || u.endsWith('.mov') || u.endsWith('.mkv') || u.endsWith('.avi');
    };

    const isImageExt = (url) => {
      const u = url.toLowerCase().split('?')[0];
      return u.endsWith('.png') || u.endsWith('.jpg') || u.endsWith('.jpeg') || u.endsWith('.gif') || u.endsWith('.webp') || u.endsWith('.svg') || u.endsWith('.bmp');
    };

    const processUrl = (url) => {
      if (url.includes('trello.com/') || url.includes('trello-attachments.s3.amazonaws.com/')) {
        return `/api/projects/${pId}/attachment-proxy?url=${encodeURIComponent(url)}`;
      }
      return url;
    };

    // Master regex for Markdown Images ![], Markdown Links [], and raw URLs
    const masterRegex = /!\[([^\]]*)\]\((https?:\/\/[^\s\)]+)\)|\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)|(https?:\/\/[^\s\)]+)/g;

    const segments = [];
    let lastIdx = 0;
    let match;

    while ((match = masterRegex.exec(rawText)) !== null) {
      if (match.index > lastIdx) {
        const textPart = rawText.slice(lastIdx, match.index);
        if (textPart) {
          segments.push({ type: 'text', content: textPart });
        }
      }

      if (match[2]) {
        // Markdown Image: ![alt](url)
        const alt = match[1] || 'Attached image';
        const rawUrl = match[2];
        const finalUrl = processUrl(rawUrl);
        if (isVideoExt(rawUrl)) {
          segments.push({ type: 'video', alt: alt || 'Attached video', url: finalUrl, originalUrl: rawUrl });
        } else {
          segments.push({ type: 'image', alt, url: finalUrl, originalUrl: rawUrl });
        }
      } else if (match[4]) {
        // Markdown Link: [text](url)
        const linkText = match[3];
        const rawUrl = match[4];
        const finalUrl = processUrl(rawUrl);
        if (isVideoExt(rawUrl)) {
          segments.push({ type: 'video', alt: linkText || 'Attached video', url: finalUrl, originalUrl: rawUrl });
        } else if (isImageExt(rawUrl)) {
          segments.push({ type: 'image', alt: linkText || 'Attached image', url: finalUrl, originalUrl: rawUrl });
        } else {
          segments.push({ type: 'link', text: linkText, url: finalUrl, originalUrl: rawUrl });
        }
      } else if (match[5]) {
        // Raw URL
        const rawUrl = match[5];
        const finalUrl = processUrl(rawUrl);
        if (isVideoExt(rawUrl)) {
          segments.push({ type: 'video', alt: 'Attached video', url: finalUrl, originalUrl: rawUrl });
        } else if (isImageExt(rawUrl) || rawUrl.includes('trello-attachments.s3.amazonaws.com') || rawUrl.includes('trello.com/1/cards/')) {
          segments.push({ type: 'image', alt: 'Attached image', url: finalUrl, originalUrl: rawUrl });
        } else {
          segments.push({ type: 'link', text: rawUrl, url: finalUrl, originalUrl: rawUrl });
        }
      }

      lastIdx = masterRegex.lastIndex;
    }

    if (lastIdx < rawText.length) {
      const remaining = rawText.slice(lastIdx);
      if (remaining) {
        segments.push({ type: 'text', content: remaining });
      }
    }

    return segments.length > 0 ? segments : [{ type: 'text', content: rawText }];
  }

  let newCommentText = "";
  let commentAttachments = [];
  let isSendingComment = false;
  let commentFileInput;
  let commentTextareaRef;
  let isUploadingAttachment = false;

  async function uploadFileAttachment(file, fallbackFilename = 'attachment') {
    if (!file || !selectedProjectId || isUploadingAttachment) return;
    isUploadingAttachment = true;
    try {
      const formData = new FormData();
      formData.append('file', file, file.name || fallbackFilename);

      const res = await fetch(`/api/projects/${selectedProjectId}/cards/upload-attachment`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok && data.success) {
        const fileUrl = data.url;
        const newAtt = {
          id: 'att_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6),
          url: fileUrl,
          filename: data.filename || fallbackFilename || (data.is_video ? 'video.mp4' : 'screenshot.png'),
          type: data.type || (data.is_video ? 'video' : 'image')
        };
        commentAttachments = [...commentAttachments, newAtt];
        toast(data.is_video ? "แนบวิดีโอเรียบร้อยแล้ว!" : "แนบรูปภาพจากการวาง/อัปโหลดเรียบร้อยแล้ว!", "success");
        setTimeout(() => {
          if (commentTextareaRef) commentTextareaRef.focus();
        }, 50);
      } else {
        toast(data.error || "เกิดข้อผิดพลาดในการอัปโหลดไฟล์", "error");
      }
    } catch (e) {
      console.error(e);
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
        if (item.type.indexOf('image') !== -1) {
          e.preventDefault();
          const blob = item.getAsFile();
          if (blob) {
            uploadFileAttachment(blob, `screenshot_${Date.now()}.png`);
            return;
          }
        } else if (item.type.indexOf('video') !== -1) {
          e.preventDefault();
          const blob = item.getAsFile();
          if (blob) {
            uploadFileAttachment(blob, `video_${Date.now()}.mp4`);
            return;
          }
        }
      }
    }
    
    const files = e.clipboardData?.files;
    if (files && files.length > 0) {
      const file = files[0];
      if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
        e.preventDefault();
        uploadFileAttachment(file, file.name);
        return;
      }
    }
  }

  function handleFileInputChange(e) {
    if (e.target && e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      uploadFileAttachment(file, file.name);
      e.target.value = '';
    }
  }

  function triggerFileInput() {
    if (commentFileInput) {
      commentFileInput.click();
    }
  }

  function insertLinkPrompt() {
    const url = prompt("กรุณากรอก URL ลิงก์ (เช่น https://example.com):");
    if (!url || !url.trim()) return;
    const cleanUrl = url.trim();
    const text = prompt("กรุณากรอกข้อความแสดงผลสำหรับลิงก์ (ไม่บังคับ):", cleanUrl);
    const linkText = (text && text.trim()) ? text.trim() : cleanUrl;
    const insertion = ` [${linkText}](${cleanUrl}) `;
    
    if (commentTextareaRef) {
      const start = commentTextareaRef.selectionStart || newCommentText.length;
      const end = commentTextareaRef.selectionEnd || newCommentText.length;
      newCommentText = newCommentText.slice(0, start) + insertion + newCommentText.slice(end);
    } else {
      newCommentText = (newCommentText ? newCommentText + ' ' : '') + insertion;
    }
    setTimeout(() => {
      if (commentTextareaRef) commentTextareaRef.focus();
    }, 50);
  }

  async function postComment() {
    let fullComment = newCommentText.trim();
    if (commentAttachments.length > 0) {
      const attsMd = commentAttachments.map(a => `![${a.type === 'video' ? 'Video' : 'Image'}](${a.url})`).join('\n\n');
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
        toast(data.message || "เพิ่มความคิดเห็นและอัปเดตไปยัง Trello เรียบร้อยแล้ว!", "success");
      } else {
        toast(data.error || "เกิดข้อผิดพลาดในการบันทึกความคิดเห็น", "error");
      }
    } catch (e) {
      console.error("Error saving comment:", e);
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

  // --- Drag & Drop Cards Across Columns ---
  let draggedCard = null;
  let sourceColumnId = null;
  let dragOverColumnId = null;

  function handleDragStart(card, colId, e) {
    draggedCard = card;
    sourceColumnId = colId;
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.id || card.raw_ext_id);
    }
  }

  function handleDragOver(colId, e) {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'move';
    }
    if (dragOverColumnId !== colId) {
      dragOverColumnId = colId;
    }
  }

  function handleDragLeave(colId, e) {
    if (dragOverColumnId === colId) {
      dragOverColumnId = null;
    }
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
    const prevStatus = cardToMove.status;
    const cardId = cardToMove.saved_id || cardToMove.id;
    const rawExtId = cardToMove.raw_ext_id || cardToMove.ext_card_id || cardToMove.id;

    // Optimistic local update
    liveCards = liveCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: targetColumnId } : c);
    savedCards = savedCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: targetColumnId } : c);
    if (selectedCard && (selectedCard.id === cardId || selectedCard.raw_ext_id === rawExtId)) {
      selectedCard = { ...selectedCard, status: targetColumnId };
    }

    handleDragEnd();

    // Sync to backend & Trello / GitHub
    try {
      const res = await fetch(`/api/projects/${selectedProjectId}/cards/${cardId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: targetColumnId,
          raw_ext_id: rawExtId
        })
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        toast(data.error || "ไม่สามารถย้าย Card ได้", "error");
        // Revert on failure
        liveCards = liveCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
        savedCards = savedCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
      } else {
        toast("ย้าย Card เรียบร้อยแล้ว!", "success");
      }
    } catch (err) {
      console.error(err);
      toast("เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์", "error");
      // Revert on error
      liveCards = liveCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
      savedCards = savedCards.map(c => (c.id === cardId || c.raw_ext_id === rawExtId) ? { ...c, status: prevStatus } : c);
    }
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
</script>

<div class="board-container" in:fade>
  {#if !$selectedProjectStore}
    <ProjectSelection 
      {projects} 
      subtitle="กรุณาเลือกโครงการที่ต้องการ เพื่อดูและจัดการ QA Board Cards" 
      on:select={(e) => selectProject(e.detail)} 
    />
  {:else}
    <!-- Navigation Top Bar -->
    <div class="top-nav">
      <button class="btn-back" on:click={() => { selectedProjectStore.set(null); }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
          <path fill-rule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
        </svg>
        ย้อนกลับไปหน้าเลือกโครงการ
      </button>
    </div>

    <!-- Header Section -->
    <div class="header-section">
      <div class="header-main-row">
        <div>
          <h2 class="title">SpectraQA Board & Knowledge Hub</h2>
          <p class="subtitle">เลือกการ์ดจาก Trello Board เข้าสู่โครงการและระบบ RAG Vector Indexing อัตโนมัติ</p>
          
          <div class="project-info-row">
            <div class="active-project-badge">
              โครงการ: <strong>{$selectedProjectStore.project_code || ''} - {$selectedProjectStore.name || $selectedProjectStore.project_name || ''}</strong>
            </div>

            {#if currentIntegration}
              <div class="integration-status-badge {currentIntegration.provider}">
                {#if currentIntegration.provider === 'trello'}
                  <span class="provider-pill trello">🔵 Trello Board</span> 
                  <span class="provider-detail">ID: {currentIntegration.trello_board_id}</span>
                {:else if currentIntegration.provider === 'github'}
                  <span class="provider-pill github">🐱 GitHub Repo</span> 
                  <span class="provider-detail">{currentIntegration.github_owner}/{currentIntegration.github_repo}</span>
                {/if}
              </div>
            {:else}
              <div class="integration-status-badge unconfigured">
                ⚠️ ยังไม่ได้เชื่อมต่อบอร์ด (คลิกปุ่มตั้งค่าเพื่อเชื่อมต่อ)
              </div>
            {/if}
          </div>
        </div>

        <div class="header-actions">
          <button class="btn-agile-tools" on:click={() => showAgileSummaryModal = true} title="ดูสรุปแต้ม Story Points (Agile Tools)">
            <span class="agile-icon">⏱️</span>
            <span>Agile Tools</span>
            <span class="agile-pts-badge">{agilePointsSummary.totalPoints} pts</span>
          </button>

          <button class="btn-filter-toggle" class:has-active-filters={activeFilterCount > 0} on:click={() => showFilterModal = true} title="กรองการ์ดตามเงื่อนไข (Keyword, สมาชิก, Label, สถานะ)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
            <span>Filter</span>
            {#if activeFilterCount > 0}
              <span class="filter-count-badge">{activeFilterCount}</span>
            {/if}
          </button>

          <button class="btn-config" on:click={() => showConfigModal = true} title="ตั้งค่าเชื่อมต่อกับ Trello หรือ GitHub">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            ⚙️ ตั้งค่า Board
          </button>
        </div>
      </div>

      <!-- Main Tab Switcher -->
      <div class="tab-switcher-container">
        <button 
          class="tab-btn" 
          class:active={activeTab === 'live'} 
          on:click={() => activeTab = 'live'}
        >
          <span class="tab-icon">🔵</span>
          <span class="tab-label">บอร์ด Trello สด & เลือกบันทึกการ์ด</span>
          <span class="tab-counter-badge">{liveCards.length}</span>
        </button>

        <button 
          class="tab-btn" 
          class:active={activeTab === 'saved'} 
          on:click={() => activeTab = 'saved'}
        >
          <span class="tab-icon">📂</span>
          <span class="tab-label">การ์ดที่บันทึกในโครงการนี้ & RAG</span>
          <span class="tab-counter-badge saved">{savedCards.length}</span>
        </button>
      </div>
    </div>

    <!-- TAB 1: LIVE TRELLO BOARD & SELECTOR -->
    {#if activeTab === 'live'}
      <div class="live-board-wrapper" in:fade={{ duration: 150 }}>
        <!-- Sticky Action Bar for Live Selection -->
        <div class="sticky-action-bar glass-panel">
          <div class="action-bar-left">
            <div class="selection-status-badge">
              <span class="selection-icon">📋</span>
              <span>เลือกแล้ว: <strong>{selectedCardIds.size}</strong> / {liveCards.length} การ์ด</span>
            </div>

            <button class="btn-action-outline" on:click={selectAllLiveCards} title="เลือก Card ทั้งหมดในบอร์ด">
              ☑️ เลือกทั้งหมด
            </button>
            
            {#if selectedCardIds.size > 0}
              <button class="btn-action-outline" on:click={clearCardSelection} title="ล้างการเลือกทั้งหมด">
                ⬜ ล้างที่เลือก
              </button>
            {/if}
          </div>

          <div class="action-bar-right">
            <div class="search-input-wrapper">
              <span class="search-icon">🔍</span>
              <input 
                type="text" 
                placeholder="ค้นหาชื่อ Card, ID, Labels..." 
                bind:value={cardSearchQuery}
                class="card-search-box"
              />
              {#if cardSearchQuery}
                <button class="clear-search-btn" on:click={() => cardSearchQuery = ''}>✕</button>
              {/if}
            </div>

            <button class="btn-filter-quick" class:active={activeFilterCount > 0} on:click={() => showFilterModal = true} title="เปิดแผงตัวกรอง">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
              <span>Filter</span>
              {#if activeFilterCount > 0}
                <span class="filter-count-badge small">{activeFilterCount}</span>
              {/if}
            </button>

            <button class="btn-refresh-live" on:click={fetchLiveCards} disabled={isLoadingLive}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="15" height="15" class:spinning={isLoadingLive}><path d="M23 4v6h-6"></path><path d="M1 20v-6h6"></path><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
              {isLoadingLive ? 'กำลังโหลด...' : 'รีเฟรชบอร์ดสด'}
            </button>

            <button 
              class="btn-save-selected-rag" 
              on:click={saveSelectedCardsToProject} 
              disabled={selectedCardIds.size === 0 || isSavingSelected}
              title="บันทึกการ์ดที่เลือกลงในโครงการนี้ และสร้าง Vector Embedding เข้า RAG"
            >
              {#if isSavingSelected}
                <span class="spinner-small"></span> กำลังบันทึก & Index RAG...
              {:else}
                💾 บันทึก Card ที่เลือกลงโครงการ & RAG ({selectedCardIds.size})
              {/if}
            </button>
          </div>
        </div>

        <!-- Active Filter Strip -->
        {#if activeFilterCount > 0}
          <div class="active-filters-strip glass-panel">
            <span class="strip-label">⚡ กรองอยู่ ({totalFilteredLiveCardsCount} / {liveCards.length} การ์ด):</span>
            {#if cardSearchQuery}
              <span class="active-filter-tag">คำค้น: "{cardSearchQuery}" <button on:click={() => cardSearchQuery = ''}>✕</button></span>
            {/if}
            {#if filterNoMembers}
              <span class="active-filter-tag">ไม่มีสมาชิก <button on:click={() => filterNoMembers = false}>✕</button></span>
            {/if}
            {#each Array.from(selectedMemberIds) as mId}
              <span class="active-filter-tag">สมาชิก: {mId} <button on:click={() => toggleMemberFilter(mId)}>✕</button></span>
            {/each}
            {#if filterNoLabels}
              <span class="active-filter-tag">ไม่มี Label <button on:click={() => filterNoLabels = false}>✕</button></span>
            {/if}
            {#each Array.from(selectedLabelNames) as lName}
              <span class="active-filter-tag">Label: {lName} <button on:click={() => toggleLabelFilter(lName)}>✕</button></span>
            {/each}
            {#if filterSavedStatus !== 'all'}
              <span class="active-filter-tag">สถานะ: {filterSavedStatus === 'saved' ? 'บันทึกแล้ว' : 'ยังไม่บันทึก'} <button on:click={() => filterSavedStatus = 'all'}>✕</button></span>
            {/if}
            {#if filterCompletion !== 'all'}
              <span class="active-filter-tag">ความสมบูรณ์: {filterCompletion === 'complete' ? 'เสร็จแล้ว' : 'ยังไม่เสร็จ'} <button on:click={() => filterCompletion = 'all'}>✕</button></span>
            {/if}
            <button class="btn-clear-all-filters" on:click={resetAllFilters}>ล้างตัวกรองทั้งหมด</button>
          </div>
        {/if}

        <!-- Live Columns Layout -->
        <div class="board-layout">
          {#each columns as column}
            <div 
              class="board-column glass-panel"
              class:drag-over={dragOverColumnId === column.id}
              on:dragover={(e) => handleDragOver(column.id, e)}
              on:dragleave={(e) => handleDragLeave(column.id, e)}
              on:drop={(e) => handleDrop(column.id, e)}
            >
              <div class="column-header">
                <span class="column-dot" style="background-color: {column.color};"></span>
                <span class="column-title">{column.title}</span>
                <span class="column-count">{(liveCardsByCol[column.id] || []).length}</span>
              </div>
              
              <div class="card-list">
                {#each (liveCardsByCol[column.id] || []) as card (card.id || card.ext_card_id)}
                  <!-- svelte-ignore a11y-click-events-have-key-events -->
                  <div 
                    class="task-card live-card" 
                    class:selected={isCardSelected(card, selectedCardIds)}
                    class:is-saved={card.is_saved}
                    class:is-dragging={draggedCard && (draggedCard.id === card.id || draggedCard.raw_ext_id === card.raw_ext_id)}
                    draggable="true"
                    on:dragstart={(e) => handleDragStart(card, column.id, e)}
                    on:dragend={handleDragEnd}
                    on:click={() => openCardDetail(card)} 
                    title="คลิกเพื่อดูรายละเอียด หรือลาก (Drag) เพื่อย้ายแถว"
                  >
                    <!-- Card Top Header: Labels on Left, Checkbox on Right -->
                    <div class="card-top-control-row">
                      <div class="card-labels-group">
                        {#if getCleanLabels(card.labels).length > 0}
                          {#each getCleanLabels(card.labels) as label}
                            <span class="trello-label-pill" style="background-color: {label.color || '#38bdf8'};">
                              {label.name}
                            </span>
                          {/each}
                        {/if}
                        {#if card.is_saved}
                          <span class="saved-status-badge" title="Card ใบนี้ถูกบันทึกและจัดทำดัชนี RAG ในโครงการนี้แล้ว">
                            ✅ บันทึกแล้ว
                          </span>
                        {/if}
                      </div>

                      <!-- svelte-ignore a11y-click-events-have-key-events -->
                      <div 
                        class="card-checkbox-hitbox" 
                        on:click|stopPropagation={(e) => toggleSelectCard(card, e)}
                        title={isCardSelected(card, selectedCardIds) ? "คลิกเพื่อยกเลิกการเลือก" : "คลิกเพื่อเลือก Card นี้เข้าโครงการ"}
                      >
                        <span class="custom-checkbox-ui" class:checked={isCardSelected(card, selectedCardIds)}>
                          {#if isCardSelected(card, selectedCardIds)}
                            <svg viewBox="0 0 16 16" fill="currentColor" width="11" height="11">
                              <path fill-rule="evenodd" d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" clip-rule="evenodd"/>
                            </svg>
                          {/if}
                        </span>
                      </div>
                    </div>
                    
                    <h4 class="card-title">{card.title}</h4>

                    <div class="card-footer">
                      <div class="footer-left-meta">
                        {#if card.description}
                          <span class="desc-icon" title="มีรายละเอียด">≡</span>
                        {/if}
                        <span class="story-points-pill" title="Story Points">
                          P {card.story_points || '1'}
                        </span>
                        <span class="badge priority-{card.priority ? card.priority.toLowerCase() : 'medium'}">
                          {card.priority === 'High' ? 'Main Card' : (card.type || 'Main Card')}
                        </span>
                      </div>

                      <div class="footer-right-members">
                        {#if card.members && card.members.length > 0}
                          {#each card.members as member}
                            {#if member.avatar}
                              <img 
                                src={member.avatar} 
                                alt={member.name} 
                                class="member-avatar" 
                                loading="lazy"
                                decoding="async"
                                title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}"
                                on:error={(e) => {
                                  e.currentTarget.style.display = 'none';
                                  if (e.currentTarget.nextElementSibling) e.currentTarget.nextElementSibling.style.display = 'inline-flex';
                                }}
                              />
                              <span class="member-initials" style="display: none;" title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}">{member.initials || 'M'}</span>
                            {:else}
                              <span class="member-initials" title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}">{member.initials || 'M'}</span>
                            {/if}
                          {/each}
                        {/if}
                      </div>
                    </div>
                  </div>
                {/each}
                {#if (liveCardsByCol[column.id] || []).length === 0}
                  <div class="empty-column">ไม่มี Card ในสถานะนี้</div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>

    <!-- TAB 2: SAVED PROJECT CARDS & RAG VIEW -->
    {:else if activeTab === 'saved'}
      <div class="saved-board-wrapper" in:fade={{ duration: 150 }}>
        <!-- Saved Cards Top Bar -->
        <div class="saved-top-bar glass-panel">
          <div class="saved-bar-left">
            <div class="rag-info-pill">
              <span class="rag-sparkle">⚡</span>
              <span>การ์ดในโครงการนี้: <strong>{savedCards.length}</strong> ใบ (พร้อมระบบ RAG Vector Search)</span>
            </div>
          </div>

          <div class="saved-bar-right">
            <div class="search-input-wrapper">
              <span class="search-icon">🔍</span>
              <input 
                type="text" 
                placeholder="ค้นหาการ์ดที่บันทึกไว้..." 
                bind:value={cardSearchQuery}
                class="card-search-box"
              />
              {#if cardSearchQuery}
                <button class="clear-search-btn" on:click={() => cardSearchQuery = ''}>✕</button>
              {/if}
            </div>

            <button class="btn-filter-quick" class:active={activeFilterCount > 0} on:click={() => showFilterModal = true} title="เปิดแผงตัวกรอง">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
              <span>Filter</span>
              {#if activeFilterCount > 0}
                <span class="filter-count-badge small">{activeFilterCount}</span>
              {/if}
            </button>

            {#if savedCards.length > 0}
              <button class="btn-action-outline btn-danger-outline" on:click={clearAllSavedCards} title="ลบ Card ที่บันทึกไว้ทั้งหมดออกจากโครงการนี้">
                🗑️ ล้างการ์ดที่บันทึกทั้งหมด
              </button>
            {/if}

            <button class="btn-action-outline" on:click={() => activeTab = 'live'} title="ไปเลือกการ์ดจาก Trello Board สด">
              ➕ เลือก Card เพิ่มจากบอร์ดสด
            </button>
          </div>
        </div>

        <!-- Active Filter Strip for Saved Tab -->
        {#if activeFilterCount > 0}
          <div class="active-filters-strip glass-panel">
            <span class="strip-label">⚡ กรองอยู่ ({totalFilteredSavedCardsCount} / {savedCards.length} การ์ด):</span>
            {#if cardSearchQuery}
              <span class="active-filter-tag">คำค้น: "{cardSearchQuery}" <button on:click={() => cardSearchQuery = ''}>✕</button></span>
            {/if}
            {#if filterNoMembers}
              <span class="active-filter-tag">ไม่มีสมาชิก <button on:click={() => filterNoMembers = false}>✕</button></span>
            {/if}
            {#each Array.from(selectedMemberIds) as mId}
              <span class="active-filter-tag">สมาชิก: {mId} <button on:click={() => toggleMemberFilter(mId)}>✕</button></span>
            {/each}
            {#if filterNoLabels}
              <span class="active-filter-tag">ไม่มี Label <button on:click={() => filterNoLabels = false}>✕</button></span>
            {/if}
            {#each Array.from(selectedLabelNames) as lName}
              <span class="active-filter-tag">Label: {lName} <button on:click={() => toggleLabelFilter(lName)}>✕</button></span>
            {/each}
            {#if filterCompletion !== 'all'}
              <span class="active-filter-tag">ความสมบูรณ์: {filterCompletion === 'complete' ? 'เสร็จแล้ว' : 'ยังไม่เสร็จ'} <button on:click={() => filterCompletion = 'all'}>✕</button></span>
            {/if}
            <button class="btn-clear-all-filters" on:click={resetAllFilters}>ล้างตัวกรองทั้งหมด</button>
          </div>
        {/if}

        <!-- Saved Cards List / Columns -->
        {#if savedCards.length === 0}
          <div class="empty-saved-state glass-panel">
            <div class="empty-icon">📂</div>
            <h3>ยังไม่มี Card ที่ถูกเลือกบันทึกในโครงการนี้</h3>
            <p>คุณสามารถเข้าไปที่แท็บ <strong>"บอร์ด Trello สด"</strong> เพื่อติ๊ก Checkbox เลือกเฉพาะ Card ของโครงการนี้ แล้วกดบันทึก</p>
            <button class="btn-primary" on:click={() => activeTab = 'live'}>
              👉 ไปที่แท็บเลือก Card จากบอร์ดสด
            </button>
          </div>
        {:else}
          <div class="board-layout">
            {#each columns as column}
              <div 
                class="board-column glass-panel"
                class:drag-over={dragOverColumnId === column.id}
                on:dragover={(e) => handleDragOver(column.id, e)}
                on:dragleave={(e) => handleDragLeave(column.id, e)}
                on:drop={(e) => handleDrop(column.id, e)}
              >
                <div class="column-header">
                  <span class="column-dot" style="background-color: {column.color};"></span>
                  <span class="column-title">{column.title}</span>
                  <span class="column-count">{(savedCardsByCol[column.id] || []).length}</span>
                </div>
                
                <div class="card-list">
                  {#each (savedCardsByCol[column.id] || []) as card (card.id)}
                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                    <div 
                      class="task-card saved-card-item" 
                      class:is-dragging={draggedCard && (draggedCard.id === card.id || draggedCard.raw_ext_id === card.raw_ext_id)}
                      draggable="true"
                      on:dragstart={(e) => handleDragStart(card, column.id, e)}
                      on:dragend={handleDragEnd}
                      on:click={() => openCardDetail(card)} 
                      title="คลิกเพื่อดูรายละเอียด หรือลาก (Drag) เพื่อย้ายแถว"
                    >
                      <!-- Top Badges Row -->
                      <div class="saved-top-badge-row">
                        <span class="rag-indexed-badge">
                          ⚡ RAG Indexed
                        </span>
                        {#if card.test_result}
                          <span class="test-status-badge passed">✓ Tested</span>
                        {/if}
                      </div>

                      <!-- Trello Tag Labels Row -->
                      {#if getCleanLabels(card.labels).length > 0}
                        <div class="trello-labels-bar">
                          {#each getCleanLabels(card.labels) as label}
                            <span class="trello-label-pill" style="background-color: {label.color || '#38bdf8'};">
                              {label.name}
                            </span>
                          {/each}
                        </div>
                      {/if}
                      
                      <h4 class="card-title">{card.title}</h4>

                      <div class="card-footer">
                        <div class="footer-left-meta">
                          {#if card.description}
                            <span class="desc-icon" title="มีรายละเอียด">≡</span>
                          {/if}
                          <span class="story-points-pill" title="Story Points">
                            P {card.story_points || '1'}
                          </span>
                          <span class="badge priority-{card.priority ? card.priority.toLowerCase() : 'medium'}">
                            {card.priority === 'High' ? 'Main Card' : (card.type || 'Main Card')}
                          </span>
                        </div>

                        <div class="footer-right-members">
                          {#if card.members && card.members.length > 0}
                            {#each card.members as member}
                              {#if member.avatar}
                                <img 
                                  src={member.avatar} 
                                  alt={member.name} 
                                  class="member-avatar" 
                                  loading="lazy"
                                  decoding="async"
                                  title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}"
                                  on:error={(e) => {
                                    e.currentTarget.style.display = 'none';
                                    if (e.currentTarget.nextElementSibling) e.currentTarget.nextElementSibling.style.display = 'inline-flex';
                                  }}
                                />
                                <span class="member-initials" style="display: none;" title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}">{member.initials || 'M'}</span>
                              {:else}
                                <span class="member-initials" title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}">{member.initials || 'M'}</span>
                              {/if}
                            {/each}
                          {/if}
                        </div>
                      </div>

                      <!-- Saved Card Actions Row -->
                      <div class="saved-card-actions-bar" on:click|stopPropagation>
                        <button class="btn-card-action test" on:click={() => handleAgentTest(card.id)} disabled={card.isTesting} title="ทดสอบอัตโนมัติด้วย AI Agent">
                          {#if card.isTesting}
                            <span class="spinner-small"></span> กำลังทดสอบ...
                          {:else}
                            🧪 Test Agent
                          {/if}
                        </button>
                        <button class="btn-card-action unsave" on:click={(e) => unsaveCard(card, e)} title="ยกเลิกการบันทึก Card ออกจากโครงการนี้">
                          🗑️ ยกเลิก
                        </button>
                      </div>
                    </div>
                  {/each}
                  {#if (savedCardsByCol[column.id] || []).length === 0}
                    <div class="empty-column">ไม่มี Card ในสถานะนี้</div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<!-- Modal ตั้งค่าการเชื่อมต่อบอร์ด (Board Integration Modal) -->
{#if showConfigModal}
  <div class="modal-backdrop" transition:fade={{ duration: 150 }}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="modal-card glass-panel" in:scale={{ start: 0.95, duration: 200 }} on:click|stopPropagation>
      <div class="modal-header">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-size: 24px;">🔌</span>
          <div>
            <h3 class="modal-title">ตั้งค่าการเชื่อมต่อบอร์ด (Board Integration)</h3>
            <p class="modal-subtitle">กำหนดค่าการเชื่อมต่อเพื่อดึงงานจาก Trello หรือ GitHub เข้าสู่ระบบ QA Agent</p>
          </div>
        </div>
        <button class="btn-close" on:click={() => showConfigModal = false}>✕</button>
      </div>

      <!-- Provider Tabs -->
      <div class="provider-tabs">
        <button class="tab-btn-modal" class:active={configProvider === 'trello'} on:click={() => configProvider = 'trello'}>
          <span style="color: #38bdf8; font-weight: bold;">🔵 Trello Board</span>
        </button>
        <button class="tab-btn-modal" class:active={configProvider === 'github'} on:click={() => configProvider = 'github'}>
          <span style="color: #f3f4f6; font-weight: bold;">🐱 GitHub Issues / Project</span>
        </button>
      </div>

      <div class="modal-body">
        {#if configProvider === 'trello'}
          <div class="provider-guide">
            <p><strong>วิธีรับค่าจาก Trello:</strong> ไปที่ <a href="https://trello.com/power-ups/admin" target="_blank" rel="noreferrer">Trello Power-Up Admin</a> เพื่อสร้าง Key & Token และดู Board ID จากลิงก์บอร์ดของคุณ</p>
          </div>

          <div class="form-group">
            <label for="trello_api_key">Trello API Key <span class="required">*</span></label>
            <input type="text" id="trello_api_key" bind:value={trelloApiKey} placeholder="เช่น a1b2c3d4e5f6..." />
          </div>

          <div class="form-group">
            <label for="trello_token">Trello API Token <span class="required">*</span></label>
            <input type="password" id="trello_token" bind:value={trelloToken} placeholder="เช่น ATATT..." />
          </div>

          <div class="form-group">
            <label for="trello_board_id">Trello Board ID <span class="required">*</span></label>
            <input type="text" id="trello_board_id" bind:value={trelloBoardId} placeholder="เช่น 64f1234abcd56789 (ดูจาก URL บอร์ดหลัง /b/)" />
          </div>

        {:else if configProvider === 'github'}
          <div class="provider-guide">
            <p><strong>วิธีรับค่าจาก GitHub:</strong> ไปที่ GitHub ➔ Settings ➔ Developer Settings ➔ <a href="https://github.com/settings/tokens" target="_blank" rel="noreferrer">Personal Access Tokens (classic หรือ fine-grained)</a> โดยเลือกสิทธิ์ <code>repo</code></p>
          </div>

          <div class="form-group">
            <label for="github_token">GitHub Personal Access Token (PAT) <span class="required">*</span></label>
            <input type="password" id="github_token" bind:value={githubToken} placeholder="เช่น ghp_xxxxxxxxxxxx หรือ github_pat_..." />
          </div>

          <div class="form-row">
            <div class="form-group" style="flex: 1;">
              <label for="github_owner">Repository Owner / Org <span class="required">*</span></label>
              <input type="text" id="github_owner" bind:value={githubOwner} placeholder="เช่น AkradTTT08 หรือ MyOrganization" />
            </div>

            <div class="form-group" style="flex: 1;">
              <label for="github_repo">Repository Name <span class="required">*</span></label>
              <input type="text" id="github_repo" bind:value={githubRepo} placeholder="เช่น OCR-Document" />
            </div>
          </div>
        {/if}
      </div>

      <div class="modal-footer">
        <button class="btn-test-conn" on:click={testConnection} disabled={isTestingConnection}>
          {#if isTestingConnection}
            <span class="spinner-small"></span> กำลังทดสอบ...
          {:else}
            ⚡ ทดสอบการเชื่อมต่อ (Test)
          {/if}
        </button>

        <div style="display: flex; gap: 8px;">
          <button class="btn-secondary" on:click={() => showConfigModal = false}>ยกเลิก</button>
          <button class="btn-primary" on:click={saveBoardIntegration} disabled={isSavingConfig}>
            {#if isSavingConfig}
              <span class="spinner-small"></span> กำลังบันทึก...
            {:else}
              💾 บันทึกและเชื่อมต่อ
            {/if}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- Modal ดูรายละเอียด Card (Card Detail Modal - Trello Style) -->
{#if showDetailModal && selectedCard}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={closeCardDetail}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="trello-modal-container glass-panel" in:scale={{ start: 0.95, duration: 200 }} on:click|stopPropagation>
      
      <!-- Top Bar with Status Badge & Close -->
      <div class="trello-modal-topbar">
        <div class="trello-modal-top-left">
          <div class="column-status-select">
            <span>{columns.find(c => c.id === selectedCard.status)?.title || 'Doing'}</span>
          </div>

          {#if selectedCard.is_saved}
            <span class="saved-status-badge">
              ✅ บันทึกในโครงการแล้ว & RAG Indexed
            </span>
          {/if}
        </div>

        <div style="display: flex; gap: 10px; align-items: center;">
          {#if getExternalUrl(selectedCard)}
            <a href={getExternalUrl(selectedCard)} target="_blank" rel="noreferrer" class="btn-ext-link {currentIntegration?.provider || 'trello'}">
              {#if currentIntegration?.provider === 'trello'}
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor"><path d="M19.5 2h-15A2.5 2.5 0 0 0 2 4.5v15A2.5 2.5 0 0 0 4.5 22h15a2.5 2.5 0 0 0 2.5-2.5v-15A2.5 2.5 0 0 0 19.5 2zm-8.25 15a1.25 1.25 0 0 1-1.25-1.25V6.75a1.25 1.25 0 0 1 1.25-1.25h3.5a1.25 1.25 0 0 1 1.25 1.25v9a1.25 1.25 0 0 1-1.25 1.25h-3.5zm-5.5-4a1.25 1.25 0 0 1-1.25-1.25V6.75A1.25 1.25 0 0 1 6 5.5h3.5A1.25 1.25 0 0 1 10.75 6.75v5A1.25 1.25 0 0 1 9.5 13H6z"/></svg>
                <span>เปิดดูใน Trello</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
              {:else}
                <span>🐱 เปิดดูใน GitHub</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
              {/if}
            </a>
          {/if}
          <button class="btn-close" on:click={closeCardDetail}>✕</button>
        </div>
      </div>

      <!-- Main Title Header -->
      <div class="trello-modal-header">
        <span class="trello-card-icon">⭕</span>
        <h2 class="trello-card-title">{selectedCard.title}</h2>
      </div>

      <!-- Meta Grid: Members, Labels, Story points, Priority -->
      <div class="trello-meta-grid">
        <div class="meta-group">
          <span class="meta-group-title">Members</span>
          <div class="meta-group-content">
            {#if selectedCard.members && selectedCard.members.length > 0}
              {#each selectedCard.members as member}
                {#if member.avatar}
                  <img 
                    src={member.avatar} 
                    alt={member.name} 
                    class="member-avatar-large" 
                    title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}"
                    on:error={(e) => {
                      e.currentTarget.style.display = 'none';
                      if (e.currentTarget.nextElementSibling) e.currentTarget.nextElementSibling.style.display = 'inline-flex';
                    }}
                  />
                  <span class="member-initials-large" style="display: none;" title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}">{member.initials || 'M'}</span>
                {:else}
                  <span class="member-initials-large" title="{member.name}{member.username ? ' (@' + member.username + ')' : ''}">{member.initials || 'M'}</span>
                {/if}
              {/each}
            {:else}
              <span class="no-meta-text">No members</span>
            {/if}
          </div>
        </div>

        <div class="meta-group">
          <span class="meta-group-title">Labels</span>
          <div class="meta-group-content">
            {#if getCleanLabels(selectedCard.labels).length > 0}
              {#each getCleanLabels(selectedCard.labels) as label}
                <span class="trello-label-pill-large" style="background-color: {label.color || '#38bdf8'};">
                  {label.name}
                </span>
              {/each}
            {:else}
              <span class="no-meta-text">No labels</span>
            {/if}
          </div>
        </div>

        <div class="meta-group">
          <span class="meta-group-title">Story points</span>
          <div class="meta-group-content">
            <span class="trello-points-pill">{selectedCard.story_points || '1'}</span>
          </div>
        </div>

        <div class="meta-group">
          <span class="meta-group-title">Priority</span>
          <div class="meta-group-content">
            <span class="trello-priority-badge">
              {selectedCard.priority === 'High' ? 'Main Card' : (selectedCard.priority || 'Main Card')}
            </span>
          </div>
        </div>
      </div>

      <!-- Quick Save / Unsave Banner in Modal -->
      <div class="modal-card-action-banner">
        {#if !selectedCard.is_saved}
          <button class="btn-modal-save-rag" on:click={() => saveSingleCard(selectedCard)} disabled={isSavingSelected}>
            💾 บันทึก Card นี้ลงในโครงการ & จัดทำดัชนี RAG ทันที
          </button>
        {:else}
          <div style="display: flex; gap: 10px; align-items: center;">
            <button class="btn-modal-unsave" on:click={(e) => unsaveCard(selectedCard, e)}>
              🗑️ ยกเลิกการบันทึกออกจากโครงการ
            </button>
            <button class="btn-modal-test" on:click={() => handleAgentTest(selectedCard.saved_id || selectedCard.id)} disabled={selectedCard.isTesting}>
              🤖 ทดสอบด้วย AI Agent
            </button>
          </div>
        {/if}
      </div>

      <!-- 2-Column Main Layout: Left (Description + Agent Test), Right (Comments & Activity) -->
      <div class="trello-2col-layout">
        <!-- Left Column -->
        <div class="trello-col-main">
          <div class="trello-section-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 1.1rem; font-weight: bold;">≡</span>
              <h3 class="section-title">Description</h3>
            </div>
          </div>

          <div class="trello-description-box">
            {#if selectedCard.description}
              <div class="desc-content">
                {#each parseCommentSegments(selectedCard.description, selectedProjectId) as segment}
                  {#if segment.type === 'text'}
                    <span>{segment.content}</span>
                  {:else if segment.type === 'image'}
                    <!-- svelte-ignore a11y-click-events-have-key-events -->
                    <div class="comment-image-container" on:click|stopPropagation={() => openImagePreview(segment.url, segment.alt)}>
                      <img 
                        src={segment.url} 
                        alt={segment.alt} 
                        class="comment-attached-image" 
                        loading="lazy"
                        title="คลิกเพื่อดูรูปภาพขนาดเต็ม ({segment.alt})" 
                      />
                    </div>
                  {:else if segment.type === 'video'}
                    <div class="comment-video-container">
                      <video 
                        src={segment.url} 
                        controls 
                        class="comment-video-player" 
                        preload="metadata"
                      >
                        <track kind="captions" />
                        เบราว์เซอร์ของคุณไม่รองรับการเล่นวิดีโอนี้
                      </video>
                      <div class="video-meta-bar">
                        <span>🎬 {segment.alt || 'Video attachment'}</span>
                        <a href={segment.url} target="_blank" rel="noreferrer" class="video-open-link" title="เปิดวิดีโอในแท็บใหม่">↗ ขยาย</a>
                      </div>
                    </div>
                  {:else if segment.type === 'link'}
                    <a href={segment.url} target="_blank" rel="noopener noreferrer" class="comment-rich-link" title={segment.url}>
                      🔗 {segment.text || segment.url}
                    </a>
                  {/if}
                {/each}
              </div>
            {:else}
              <div class="desc-content no-data-text">ไม่มีรายละเอียดระบุไว้สำหรับ Card นี้</div>
            {/if}
          </div>

          <!-- QA Agent Test Suite Section -->
          <div class="trello-agent-box">
            <div class="agent-box-header">
              <span style="font-size: 18px;">🤖</span>
              <h4 style="margin: 0; color: #c084fc; font-size: 0.95rem;">AI Agent Tester & Verification</h4>
            </div>

            <div class="agent-box-content">
              {#if selectedCard.isTesting || selectedCard.status === 'testing'}
                <div class="testing-indicator-large">
                  <span class="spinner-small"></span> AI Agent กำลังทดสอบระบบอัตโนมัติสำหรับ Card นี้...
                </div>
              {:else if selectedCard.test_result}
                <div class="agent-report-container">
                  {#if typeof selectedCard.test_result === 'string' && selectedCard.test_result.includes('FAILED')}
                    <div class="test-verdict-badge failed">
                      ⚠️ FAILED: พบข้อบกพร่อง (Defect Detected)
                    </div>
                  {:else if typeof selectedCard.test_result === 'string' && selectedCard.test_result.includes('PASSED')}
                    <div class="test-verdict-badge passed">
                      ✅ PASSED: ตรวจสอบผ่านตามเกณฑ์ทั้งหมด
                    </div>
                  {/if}
                  {#each parseCommentSegments(typeof selectedCard.test_result === 'object' ? JSON.stringify(selectedCard.test_result, null, 2) : selectedCard.test_result, selectedProjectId) as segment}
                    {#if segment.type === 'text'}
                      <pre class="test-result-pre" class:failed={segment.content.includes('FAILED')}>{segment.content}</pre>
                    {:else if segment.type === 'image'}
                      <!-- svelte-ignore a11y-click-events-have-key-events -->
                      <div class="comment-image-container" on:click|stopPropagation={() => openImagePreview(segment.url, segment.alt)}>
                        <img 
                          src={segment.url} 
                          alt={segment.alt} 
                          class="comment-attached-image" 
                          loading="lazy"
                          title="คลิกเพื่อดูรูปภาพหลักฐาน ({segment.alt})" 
                        />
                      </div>
                    {:else if segment.type === 'link'}
                      <a href={segment.url} target="_blank" rel="noopener noreferrer" class="comment-rich-link">
                        🔗 {segment.text || segment.url}
                      </a>
                    {/if}
                  {/each}
                </div>
              {:else}
                <p style="margin: 0; color: #94a3b8; font-size: 0.85rem;">ยังไม่ได้ทำการทดสอบ Card นี้</p>
              {/if}
            </div>

            <div class="agent-box-footer">
              <button class="btn-run-agent" on:click={() => handleAgentTest(selectedCard.saved_id || selectedCard.id)} disabled={selectedCard.isTesting}>
                🤖 Run Agent Test
              </button>
            </div>
          </div>
        </div>

        <!-- Right Column: Comments & Activity Feed -->
        <div class="trello-col-sidebar">
          <div class="trello-section-header">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 1.1rem;">💬</span>
              <h3 class="section-title">Comments and activity</h3>
              {#if selectedCard.actions && selectedCard.actions.length > 0}
                <span class="comment-count-badge">{selectedCard.actions.length}</span>
              {/if}
            </div>
            <button class="btn-toggle-comments" on:click={() => showComments = !showComments} title={showComments ? 'ซ่อนความคิดเห็น' : 'แสดงความคิดเห็น'}>
              {#if showComments}
                <span>👁️ ซ่อน</span>
              {:else}
                <span>👁️‍🗨️ แสดง ({selectedCard.actions ? selectedCard.actions.length : 0})</span>
              {/if}
            </button>
          </div>

          {#if showComments}
            <!-- Write Comment Box with Attachment / Video / Link Toolbar -->
            <div class="comment-input-area">
              <div class="comment-box-wrapper {isUploadingAttachment ? 'is-uploading' : ''}">
                <textarea 
                  bind:this={commentTextareaRef}
                  bind:value={newCommentText} 
                  on:paste={handleCommentPaste}
                  placeholder="Write a comment... (กด Ctrl+V เพื่อวางรูป Cap หน้าจอ หรือแนบวิดีโอ/ลิงก์)" 
                  rows="3"
                ></textarea>

                <!-- Visual Media Attachment Thumbnails in Composer -->
                {#if commentAttachments.length > 0}
                  <div class="composer-attachments-grid">
                    {#each commentAttachments as att (att.id)}
                      <div class="composer-media-card {att.type}">
                        <button type="button" class="btn-del-media-card" on:click={() => removeCommentAttachment(att.id)} title="ลบไฟล์นี้">✕</button>
                        {#if att.type === 'image'}
                          <!-- svelte-ignore a11y-click-events-have-key-events -->
                          <img 
                            src={att.url} 
                            alt="Attached Image" 
                            class="composer-preview-img" 
                            on:click={() => openImagePreview(att.url, 'Attached Image')}
                            title="คลิกเพื่อดูรูปภาพขนาดเต็ม"
                          />
                        {:else if att.type === 'video'}
                          <video src={att.url} controls class="composer-preview-video"></video>
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

                <div class="comment-toolbar">
                  <div class="toolbar-actions">
                    <input 
                      type="file" 
                      accept="image/*,video/*" 
                      bind:this={commentFileInput} 
                      on:change={handleFileInputChange} 
                      style="display: none;" 
                    />
                    <button type="button" class="btn-comment-tool" on:click={triggerFileInput} title="แนบไฟล์รูปภาพหรือวิดีโอ (Upload Image / Video)">
                      📎 แนบไฟล์
                    </button>
                    <button type="button" class="btn-comment-tool" on:click={insertLinkPrompt} title="แทรกลิงก์ (Insert Link)">
                      🔗 ลิงก์
                    </button>
                    <span class="clipboard-paste-hint" title="คุณสามารถกด Ctrl+V เพื่อวางรูปภาพจากการแคปหน้าจอได้โดยตรง">
                      📋 <kbd>Ctrl</kbd>+<kbd>V</kbd> วางรูปแคปจอ
                    </span>
                  </div>

                  {#if newCommentText.trim() || commentAttachments.length > 0}
                    <button class="btn-save-comment" on:click={postComment} disabled={isSendingComment || isUploadingAttachment}>
                      {isSendingComment ? 'Saving...' : 'Save'}
                    </button>
                  {/if}
                </div>
              </div>
            </div>

            <!-- Activity Timeline Feed -->
            <div class="activity-timeline custom-comment-scrollbar">
              {#if selectedCard.actions && selectedCard.actions.length > 0}
                {#each selectedCard.actions as act}
                  <div class="activity-item">
                    {#if act.user_avatar}
                      <img src={act.user_avatar} alt={act.user_name} class="act-avatar" />
                    {:else}
                      <div class="act-initials">
                        {act.user_name ? act.user_name.split(' ').map(n=>n[0]).join('').slice(0,2).toUpperCase() : 'U'}
                      </div>
                    {/if}
                    <div class="act-details">
                      <div class="act-text">
                        <strong>{act.user_name || 'User'}</strong>
                        {#each parseCommentSegments(act.text, selectedProjectId) as segment}
                          {#if segment.type === 'text'}
                            <span>{segment.content}</span>
                          {:else if segment.type === 'image'}
                            <!-- svelte-ignore a11y-click-events-have-key-events -->
                            <div class="comment-image-container" on:click|stopPropagation={() => openImagePreview(segment.url, segment.alt)}>
                              <img 
                                src={segment.url} 
                                alt={segment.alt} 
                                class="comment-attached-image" 
                                loading="lazy"
                                title="คลิกเพื่อดูรูปภาพขนาดเต็ม ({segment.alt})" 
                              />
                            </div>
                          {:else if segment.type === 'video'}
                            <div class="comment-video-container">
                              <video 
                                src={segment.url} 
                                controls 
                                class="comment-video-player" 
                                preload="metadata"
                              >
                                <track kind="captions" />
                                เบราว์เซอร์ของคุณไม่รองรับการเล่นวิดีโอนี้
                              </video>
                              <div class="video-meta-bar">
                                <span>🎬 {segment.alt || 'Video attachment'}</span>
                                <a href={segment.url} target="_blank" rel="noreferrer" class="video-open-link" title="เปิดวิดีโอในแท็บใหม่">↗ ขยาย</a>
                              </div>
                            </div>
                          {:else if segment.type === 'link'}
                            <a href={segment.url} target="_blank" rel="noopener noreferrer" class="comment-rich-link" title={segment.url}>
                              🔗 {segment.text || segment.url}
                            </a>
                          {/if}
                        {/each}
                      </div>
                      <span class="act-date">
                        {act.date ? new Date(act.date).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }) : ''}
                      </span>
                    </div>
                  </div>
                {/each}
              {:else}
                <div style="color: #64748b; font-size: 0.85rem; font-style: italic; padding: 8px 0;">ไม่มีประวัติกิจกรรมล่าสุด</div>
              {/if}
            </div>
          {:else}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <div class="comments-collapsed-placeholder" on:click={() => showComments = true} title="คลิกเพื่อเปิดดูความคิดเห็น">
              <span>💬 ความคิดเห็นถูกซ่อนอยู่ (คลิกเพื่อแสดง {selectedCard.actions ? selectedCard.actions.length : 0} รายการ)</span>
            </div>
          {/if}
        </div>
      </div>

    </div>
  </div>
{/if}

<!-- Image Lightbox Modal -->
{#if showImageModal && previewModalImage}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="image-lightbox-backdrop" transition:fade={{ duration: 150 }} on:click={() => showImageModal = false}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="image-lightbox-content" in:scale={{ start: 0.95, duration: 200 }} on:click|stopPropagation>
      <button class="lightbox-close-btn" on:click={() => showImageModal = false} title="ปิด">✕</button>
      <img src={previewModalImage} alt={previewModalAlt} class="lightbox-full-img" />
      <div class="lightbox-toolbar">
        <a href={previewModalImage} target="_blank" rel="noreferrer" class="lightbox-btn-download">
          🔗 เปิดดูรูปภาพขนาดเต็มในแท็บใหม่
        </a>
      </div>
    </div>
  </div>
{/if}

<!-- Agile Tools & Story Points Modal -->
{#if showAgileSummaryModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={() => showAgileSummaryModal = false}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="agile-tools-modal-card glass-panel" in:scale={{ start: 0.95, duration: 200 }} on:click|stopPropagation>
      <div class="agile-modal-header">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 1.2rem;">⏱️</span>
          <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: #f1f5f9;">Agile Tools</h3>
        </div>
        <button class="close-btn" on:click={() => showAgileSummaryModal = false}>✕</button>
      </div>

      <div class="agile-modal-body">
        <div class="agile-toggle-row">
          <span class="toggle-label">Mark Unestimated</span>
          <label class="switch">
            <input type="checkbox" bind:checked={markUnestimated} />
            <span class="slider round"></span>
          </label>
        </div>

        <div class="points-counts-section">
          <h4 class="points-counts-title">List point counts:</h4>
          
          <div class="points-list-container custom-comment-scrollbar">
            {#each agilePointsSummary.columnsSummary as col}
              <div class="point-item-row">
                <span class="point-col-name">
                  <span class="point-dot" style="background-color: {col.color || '#38bdf8'};"></span>
                  {col.title}
                </span>
                <span class="point-val">{col.points} points</span>
              </div>
            {/each}

            <div class="point-total-row">
              <span class="total-label">TOTAL:</span>
              <span class="total-pts-highlight">{agilePointsSummary.totalPoints} points</span>
            </div>
          </div>
        </div>

        <div class="agile-extra-stats">
          <div class="stat-badge">
            <span>📋 การ์ดทั้งหมด:</span>
            <strong>{agilePointsSummary.totalCards} ใบ</strong>
          </div>
          <div class="stat-badge">
            <span>❓ ยังไม่ประเมินแต้ม:</span>
            <strong>{agilePointsSummary.unestimatedCards} ใบ</strong>
          </div>
        </div>
      </div>
    </div>
  </div>
{/if}

<!-- Filter Cards Modal / Drawer -->
{#if showFilterModal}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div class="modal-backdrop" transition:fade={{ duration: 150 }} on:click={() => showFilterModal = false}>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="filter-modal-card glass-panel" in:scale={{ start: 0.95, duration: 200 }} on:click|stopPropagation>
      <div class="filter-modal-header">
        <div style="display: flex; align-items: center; gap: 8px;">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
          <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700; color: #f1f5f9;">Filter</h3>
        </div>
        <button class="close-btn" on:click={() => showFilterModal = false}>✕</button>
      </div>

      <div class="filter-modal-body custom-comment-scrollbar">
        <!-- 1. Keyword -->
        <div class="filter-section">
          <label class="filter-section-title">Keyword</label>
          <div class="filter-input-wrapper">
            <input 
              type="text" 
              placeholder="Enter a keyword..." 
              bind:value={cardSearchQuery}
              class="filter-text-input" 
            />
            {#if cardSearchQuery}
              <button class="clear-input-inline" on:click={() => cardSearchQuery = ''}>✕</button>
            {/if}
          </div>
          <span class="filter-helper-text">Search cards, members, labels, and more.</span>
        </div>

        <!-- 2. Members -->
        <div class="filter-section">
          <label class="filter-section-title">Members</label>
          
          <label class="filter-checkbox-item">
            <input type="checkbox" bind:checked={filterNoMembers} on:change={() => { if(filterNoMembers) selectedMemberIds = new Set(); }} />
            <span class="member-icon-circle">👤</span>
            <span>No members</span>
          </label>

          {#if !filterNoMembers && boardMembersList.length > 0}
            <div class="filter-members-sublist">
              <span class="sublist-heading">Select members:</span>
              {#each boardMembersList as member}
                {@const mKey = member.id || member.username || member.name}
                <label class="filter-checkbox-item member-item">
                  <input 
                    type="checkbox" 
                    checked={selectedMemberIds.has(mKey)} 
                    on:change={() => toggleMemberFilter(mKey)}
                  />
                  {#if member.avatar}
                    <img src={member.avatar} alt={member.name} class="filter-member-avatar" />
                  {:else}
                    <span class="filter-member-initials">{member.initials || 'M'}</span>
                  {/if}
                  <span class="member-name-text">{member.name} {#if member.username}<small>@{member.username}</small>{/if}</span>
                </label>
              {/each}
            </div>
          {/if}
        </div>

        <!-- 3. Card Status / Completion -->
        <div class="filter-section">
          <label class="filter-section-title">Card status</label>
          <label class="filter-checkbox-item">
            <input 
              type="checkbox" 
              checked={filterCompletion === 'complete'} 
              on:change={(e) => filterCompletion = e.target.checked ? 'complete' : 'all'} 
            />
            <span>Marked as complete</span>
          </label>
          <label class="filter-checkbox-item">
            <input 
              type="checkbox" 
              checked={filterCompletion === 'incomplete'} 
              on:change={(e) => filterCompletion = e.target.checked ? 'incomplete' : 'all'} 
            />
            <span>Not marked as complete</span>
          </label>
        </div>

        <!-- 4. Saved Status (in Live Tab) -->
        {#if activeTab === 'live'}
          <div class="filter-section">
            <label class="filter-section-title">สถานะบันทึกในโครงการ & RAG</label>
            <div class="filter-pill-group">
              <button 
                class="filter-pill-btn" 
                class:active={filterSavedStatus === 'all'} 
                on:click={() => filterSavedStatus = 'all'}
              >
                ทั้งหมด
              </button>
              <button 
                class="filter-pill-btn" 
                class:active={filterSavedStatus === 'saved'} 
                on:click={() => filterSavedStatus = 'saved'}
              >
                ✅ บันทึกแล้ว
              </button>
              <button 
                class="filter-pill-btn" 
                class:active={filterSavedStatus === 'unsaved'} 
                on:click={() => filterSavedStatus = 'unsaved'}
              >
                ⬜ ยังไม่บันทึก
              </button>
            </div>
          </div>
        {/if}

        <!-- 5. Labels -->
        <div class="filter-section">
          <label class="filter-section-title">Labels</label>
          
          <label class="filter-checkbox-item">
            <input type="checkbox" bind:checked={filterNoLabels} on:change={() => { if(filterNoLabels) selectedLabelNames = new Set(); }} />
            <span class="label-icon-tag">🏷️</span>
            <span>No labels</span>
          </label>

          {#if !filterNoLabels && boardLabelsList.length > 0}
            <div class="filter-labels-sublist">
              {#each boardLabelsList as label}
                {@const lKey = label.name.toLowerCase()}
                <label class="filter-label-pill-item">
                  <input 
                    type="checkbox" 
                    checked={selectedLabelNames.has(lKey)} 
                    on:change={() => toggleLabelFilter(label.name)}
                  />
                  <span class="filter-label-bar" style="background-color: {label.color || '#38bdf8'};">
                    <span class="label-text-bold">{label.name}</span>
                    <span class="label-count-tag">{label.count}</span>
                  </span>
                </label>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="filter-modal-footer">
        <button class="btn-clear-filters" on:click={resetAllFilters} disabled={activeFilterCount === 0}>
          Clear all filters
        </button>
        <button class="btn-apply-filters" on:click={() => showFilterModal = false}>
          แสดงผลลัพธ์ ({totalFilteredCardsCount} การ์ด)
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Smart AI Test Launcher Modal -->
{#if isTestModalOpen}
  <SmartTestLauncherModal 
    projectId={selectedProjectId}
    projectName={$selectedProjectStore?.name || $selectedProjectStore?.project_name || 'Project'}
    cardData={testTargetCard}
    isOpen={isTestModalOpen}
    on:close={() => isTestModalOpen = false}
    on:test_completed={handleTestCompleted}
  />
{/if}

<style>
  .board-container {
    padding: 24px;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 16px;
    overflow-y: auto;
    box-sizing: border-box;
  }

  .top-nav {
    margin-bottom: 4px;
  }

  .btn-back {
    background: transparent;
    border: none;
    color: #a78bfa;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: color 0.2s;
  }
  .btn-back:hover {
    color: #c084fc;
  }
  
  .header-section {
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .header-main-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 16px;
  }
  
  .title {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, #a855f7 0%, #3b82f6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  
  .subtitle {
    margin: 4px 0 0 0;
    color: #94a3b8;
    font-size: 0.9rem;
  }

  .project-info-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
    flex-wrap: wrap;
  }

  .active-project-badge {
    padding: 4px 14px;
    background: rgba(139, 92, 246, 0.12);
    border-radius: 20px;
    border: 1px solid rgba(139, 92, 246, 0.3);
    font-size: 13px;
    color: #e2e8f0;
  }

  .integration-status-badge {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 12px;
  }
  .integration-status-badge.trello {
    background: rgba(14, 165, 233, 0.15);
    border: 1px solid rgba(14, 165, 233, 0.4);
    color: #38bdf8;
  }
  .integration-status-badge.github {
    background: rgba(243, 244, 246, 0.1);
    border: 1px solid rgba(243, 244, 246, 0.3);
    color: #f3f4f6;
  }
  .integration-status-badge.unconfigured {
    background: rgba(234, 179, 8, 0.15);
    border: 1px solid rgba(234, 179, 8, 0.35);
    color: #facc15;
  }

  .provider-pill {
    font-weight: 700;
  }
  .provider-detail {
    opacity: 0.9;
    font-family: monospace;
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .btn-config {
    background: rgba(139, 92, 246, 0.15);
    border: 1px solid rgba(139, 92, 246, 0.4);
    color: #c084fc;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .btn-config:hover {
    background: rgba(139, 92, 246, 0.3);
    color: #fff;
    transform: translateY(-1px);
  }

  /* Main Tab Switcher Bar */
  .tab-switcher-container {
    display: flex;
    gap: 12px;
    border-bottom: 2px solid rgba(255, 255, 255, 0.08);
    padding-bottom: 2px;
  }

  .tab-btn {
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 10px 18px;
    font-size: 0.95rem;
    font-weight: 600;
    color: #94a3b8;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s ease;
    border-radius: 8px 8px 0 0;
  }
  .tab-btn:hover {
    color: #e2e8f0;
    background: rgba(255, 255, 255, 0.04);
  }
  .tab-btn.active {
    color: #38bdf8;
    border-bottom-color: #38bdf8;
    background: rgba(56, 189, 248, 0.08);
  }

  .tab-icon {
    font-size: 16px;
  }
  .tab-label {
    letter-spacing: 0.2px;
  }

  .tab-counter-badge {
    background: rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    font-size: 12px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 12px;
  }
  .tab-btn.active .tab-counter-badge {
    background: #0284c7;
    color: #ffffff;
  }
  .tab-counter-badge.saved {
    background: rgba(168, 85, 247, 0.2);
    color: #c084fc;
  }
  .tab-btn.active .tab-counter-badge.saved {
    background: #9333ea;
    color: #ffffff;
  }

  /* Sticky Action Bar (Live Selection) */
  .sticky-action-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 18px;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 12px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 12px;
  }

  .action-bar-left, .action-bar-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .selection-status-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.35);
    border-radius: 8px;
    color: #38bdf8;
    font-size: 0.9rem;
  }

  .btn-action-outline {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: #e2e8f0;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-action-outline:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    transform: translateY(-1px);
  }
  .btn-danger-outline {
    border-color: rgba(239, 68, 68, 0.4);
    color: #f87171;
  }
  .btn-danger-outline:hover {
    background: rgba(239, 68, 68, 0.15);
    color: #fca5a5;
    border-color: rgba(239, 68, 68, 0.7);
  }

  .search-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }
  .search-icon {
    position: absolute;
    left: 10px;
    font-size: 13px;
    color: #64748b;
  }
  .card-search-box {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    color: #f1f5f9;
    padding: 7px 28px 7px 30px;
    font-size: 0.85rem;
    width: 200px;
    transition: width 0.2s, border-color 0.2s;
  }
  .card-search-box:focus {
    width: 250px;
    border-color: #38bdf8;
    outline: none;
  }
  .clear-search-btn {
    position: absolute;
    right: 8px;
    background: transparent;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    font-size: 11px;
  }

  .btn-refresh-live {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #e2e8f0;
    padding: 7px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s;
  }
  .btn-refresh-live:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.16);
    transform: translateY(-1px);
  }

  .btn-save-selected-rag {
    background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
    border: 1px solid rgba(255, 255, 255, 0.25);
    color: #ffffff;
    padding: 7px 18px;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 700;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4);
    transition: all 0.2s ease;
  }
  .btn-save-selected-rag:hover:not(:disabled) {
    box-shadow: 0 6px 20px rgba(124, 58, 237, 0.6);
    transform: translateY(-1px);
  }
  .btn-save-selected-rag:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    box-shadow: none;
  }

  /* Saved Top Bar */
  .saved-top-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 18px;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 12px;
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: 12px;
  }
  .rag-info-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
    color: #e2e8f0;
  }
  .rag-sparkle {
    font-size: 16px;
    color: #c084fc;
  }
  .saved-bar-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  /* Board Layout */
  .glass-panel {
    background: rgba(15, 23, 42, 0.65);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    border-radius: 12px;
  }
  
  .board-layout {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    flex: 1;
    padding-bottom: 12px;
    align-items: flex-start;
  }

  .board-layout::-webkit-scrollbar {
    height: 8px;
  }
  .board-layout::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 4px;
  }
  .board-layout::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.18);
    border-radius: 4px;
  }
  .board-layout::-webkit-scrollbar-thumb:hover {
    background: rgba(168, 85, 247, 0.45);
  }
  
  .board-column {
    min-width: 320px;
    width: 320px;
    display: flex;
    flex-direction: column;
    background: rgba(15, 23, 42, 0.7);
    max-height: calc(100vh - 270px);
    height: calc(100vh - 270px);
    min-height: 480px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .board-column.drag-over {
    border-color: #38bdf8 !important;
    background: rgba(14, 42, 71, 0.85) !important;
    box-shadow: 0 0 24px rgba(56, 189, 248, 0.4) !important;
    transform: scale(1.01);
  }
  
  .column-header {
    display: flex;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(0, 0, 0, 0.25);
    border-radius: 12px 12px 0 0;
    flex-shrink: 0;
  }
  
  .column-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 10px;
  }
  
  .column-title {
    font-weight: 600;
    color: #f1f5f9;
    flex: 1;
    font-size: 0.95rem;
  }
  
  .column-count {
    background: rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  
  .card-list {
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .card-list::-webkit-scrollbar {
    width: 6px;
  }
  .card-list::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 4px;
  }
  .card-list::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 4px;
  }
  .card-list::-webkit-scrollbar-thumb:hover {
    background: rgba(56, 189, 248, 0.5);
  }
  
  .task-card {
    background: rgba(30, 41, 59, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 14px;
    cursor: grab;
    user-select: none;
    -webkit-user-select: none;
    transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s, opacity 0.2s;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .task-card:active {
    cursor: grabbing;
  }
  .task-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
    border-color: rgba(139, 92, 246, 0.5);
  }
  .task-card.is-dragging {
    opacity: 0.35 !important;
    transform: scale(0.96) !important;
    border: 2px dashed #38bdf8 !important;
    box-shadow: none !important;
  }
  .task-card.selected {
    border: 2px solid #38bdf8;
    background: rgba(30, 58, 95, 0.9);
    box-shadow: 0 0 16px rgba(56, 189, 248, 0.35);
  }
  .task-card.is-saved {
    border-left: 4px solid #22c55e;
  }

  /* Card Top Control Row (Labels on Left, Checkbox on Right) */
  .card-top-control-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 4px;
  }
  .card-labels-group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
    flex: 1;
  }

  .card-checkbox-hitbox {
    padding: 2px 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    margin-left: auto;
    border-radius: 6px;
    user-select: none;
    transition: background 0.15s;
  }
  .card-checkbox-hitbox:hover {
    background: rgba(255, 255, 255, 0.08);
  }
  .custom-checkbox-ui {
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1.5px solid rgba(255, 255, 255, 0.4);
    background: rgba(15, 23, 42, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    transition: all 0.15s ease-in-out;
    box-sizing: border-box;
  }
  .card-checkbox-hitbox:hover .custom-checkbox-ui {
    border-color: #38bdf8;
  }
  .custom-checkbox-ui.checked {
    background: #0284c7;
    border-color: #0284c7;
    box-shadow: 0 0 8px rgba(2, 132, 199, 0.5);
  }

  .saved-status-badge {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.4);
    color: #4ade80;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
  }

  .saved-top-badge-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }

  .rag-indexed-badge {
    background: rgba(168, 85, 247, 0.15);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #c084fc;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
  }

  .test-status-badge.passed {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.4);
    color: #4ade80;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 10px;
  }

  .card-title {
    margin: 0;
    font-size: 0.95rem;
    color: #f1f5f9;
    font-weight: 600;
    line-height: 1.35;
  }

  .card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4px;
    flex-wrap: wrap;
    gap: 8px;
  }

  /* Saved Card Actions Bar */
  .saved-card-actions-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    padding-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .btn-card-action {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
  }
  .btn-card-action.test {
    background: rgba(168, 85, 247, 0.2);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #d8b4fe;
  }
  .btn-card-action.test:hover:not(:disabled) {
    background: rgba(168, 85, 247, 0.4);
    color: #ffffff;
  }
  .btn-card-action.unsave {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #f87171;
  }
  .btn-card-action.unsave:hover {
    background: rgba(239, 68, 68, 0.3);
    color: #ffffff;
  }

  /* Empty Saved State */
  .empty-saved-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 24px;
    text-align: center;
    gap: 16px;
    max-width: 540px;
    margin: 40px auto;
  }
  .empty-icon {
    font-size: 48px;
  }
  .empty-saved-state h3 {
    margin: 0;
    color: #f1f5f9;
    font-size: 1.25rem;
  }
  .empty-saved-state p {
    margin: 0;
    color: #94a3b8;
    font-size: 0.9rem;
    line-height: 1.5;
  }

  /* Labels */
  .trello-labels-bar {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .trello-label-pill {
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 700;
    color: #ffffff;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
    display: inline-block;
  }

  .trello-label-pill-large {
    padding: 4px 14px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: 700;
    color: #ffffff;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
    display: inline-block;
  }

  .footer-left-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .desc-icon {
    font-size: 14px;
    color: #94a3b8;
    line-height: 1;
    font-weight: bold;
  }

  .story-points-pill {
    background: #4d7c0f;
    color: #ffffff;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    display: inline-flex;
    align-items: center;
  }

  .footer-right-members {
    display: flex;
    align-items: center;
    gap: -4px;
    margin-left: auto;
  }

  .member-avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    border: 2px solid #1e293b;
    object-fit: cover;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    cursor: pointer;
  }
  .member-avatar:hover {
    transform: scale(1.18);
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.6);
    z-index: 5;
  }

  .member-initials {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #0284c7;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid #1e293b;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
    transition: transform 0.2s ease;
    cursor: pointer;
  }
  .member-initials:hover {
    transform: scale(1.18);
  }

  .member-avatar-large {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 2px solid #2c333a;
    object-fit: cover;
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.5);
    transition: transform 0.2s ease;
    cursor: pointer;
  }
  .member-avatar-large:hover {
    transform: scale(1.15);
  }

  .member-initials-large {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #0284c7;
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid #2c333a;
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.5);
    transition: transform 0.2s ease;
    cursor: pointer;
  }
  .member-initials-large:hover {
    transform: scale(1.15);
  }

  /* Modal Card Action Banner */
  .modal-card-action-banner {
    background: rgba(30, 41, 59, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .btn-modal-save-rag {
    background: linear-gradient(135deg, #0284c7 0%, #7c3aed 100%);
    color: #ffffff;
    border: none;
    padding: 8px 18px;
    border-radius: 8px;
    font-weight: 700;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
  }
  .btn-modal-save-rag:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(2, 132, 199, 0.5);
  }
  .btn-modal-unsave {
    background: rgba(239, 68, 68, 0.2);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #f87171;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-modal-unsave:hover {
    background: rgba(239, 68, 68, 0.35);
  }
  .btn-modal-test {
    background: rgba(168, 85, 247, 0.2);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #d8b4fe;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-modal-test:hover {
    background: rgba(168, 85, 247, 0.35);
  }

  /* Trello Modal Styling */
  .trello-modal-container {
    width: 95vw;
    max-width: 980px;
    max-height: 90vh;
    background: #1d2125;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 16px;
    color: #b6c2cf;
    padding: 26px 32px;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    overflow-x: hidden;
    gap: 20px;
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.85);
  }

  .trello-modal-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .trello-modal-top-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .column-status-select {
    background: #282e33;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 13px;
    font-weight: 600;
    color: #9fadbc;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .btn-ext-link {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    text-decoration: none;
    transition: all 0.2s;
  }
  .btn-ext-link.trello {
    background: #0055cc;
    color: #ffffff;
  }
  .btn-ext-link.trello:hover {
    background: #0065ff;
  }
  .btn-ext-link.github {
    background: #238636;
    color: #ffffff;
  }
  .btn-ext-link.github:hover {
    background: #2ea043;
  }

  .trello-modal-header {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }
  .trello-card-icon {
    font-size: 20px;
    margin-top: 4px;
  }
  .trello-card-title {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 600;
    color: #ffffff;
    line-height: 1.3;
  }

  .trello-meta-grid {
    display: flex;
    gap: 24px;
    flex-wrap: wrap;
  }
  .meta-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .meta-group-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: #8c9bab;
    letter-spacing: 0.5px;
  }
  .meta-group-content {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 32px;
  }
  .no-meta-text {
    color: #738496;
    font-size: 13px;
    font-style: italic;
  }

  .trello-points-pill {
    background: #4d7c0f;
    color: #ffffff;
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
  }

  .trello-priority-badge {
    background: #282e33;
    color: #9fadbc;
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
  }

  .trello-2col-layout {
    display: flex;
    gap: 28px;
    margin-top: 8px;
  }
  @media (max-width: 768px) {
    .trello-2col-layout {
      flex-direction: column;
    }
  }

  .trello-col-main {
    flex: 1.25;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .trello-col-sidebar {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .trello-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }
  .section-title {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 600;
    color: #dee4ea;
  }
  .comment-count-badge {
    background: #282e33;
    color: #9fadbc;
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 12px;
  }

  .btn-toggle-comments {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-toggle-comments:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
  }

  .trello-description-box {
    background: #22272b;
    border-radius: 8px;
    padding: 14px 16px;
    min-height: 90px;
    font-size: 14px;
    line-height: 1.6;
    color: #b6c2cf;
  }
  .desc-content {
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: break-word;
  }
  .no-data-text {
    color: #738496;
    font-style: italic;
  }

  /* QA Agent Tester Box */
  .trello-agent-box {
    background: rgba(88, 28, 135, 0.2);
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 8px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .agent-box-header {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .agent-box-content {
    font-size: 13px;
  }
  .test-verdict-badge {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 700;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .test-verdict-badge.passed {
    background: rgba(34, 197, 94, 0.15);
    border: 1px solid rgba(34, 197, 94, 0.4);
    color: #4ade80;
  }
  .test-verdict-badge.failed {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #f87171;
  }
  .test-result-pre {
    margin: 0;
    background: rgba(0, 0, 0, 0.4);
    padding: 10px;
    border-radius: 6px;
    font-size: 12px;
    color: #4ade80;
    max-height: 240px;
    overflow-y: auto;
    font-family: monospace;
    white-space: pre-wrap;
  }
  .test-result-pre.failed {
    color: #fca5a5;
    border-left: 3px solid #ef4444;
  }
  .agent-box-footer {
    display: flex;
    justify-content: flex-end;
  }
  .btn-run-agent {
    background: #7c3aed;
    color: #ffffff;
    border: none;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-run-agent:hover:not(:disabled) {
    background: #9333ea;
  }

  /* Comments Area & Rich Media */
  .comment-input-area {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .comment-box-wrapper {
    position: relative;
    background: #22272b;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: border-color 0.2s, box-shadow 0.2s;
  }
  .comment-box-wrapper:focus-within {
    border-color: #38bdf8;
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
  }
  .comment-box-wrapper.is-uploading {
    opacity: 0.8;
    pointer-events: none;
  }
  .comment-uploading-overlay {
    position: absolute;
    inset: 0;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(2px);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: #38bdf8;
    font-size: 0.85rem;
    font-weight: 600;
    z-index: 10;
  }
  .comment-input-area textarea {
    width: 100%;
    background: transparent;
    border: none;
    padding: 4px;
    color: #f1f5f9;
    font-size: 14px;
    line-height: 1.45;
    resize: vertical;
    box-sizing: border-box;
  }
  .comment-input-area textarea:focus {
    outline: none;
  }
  .composer-attachments-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 6px 0;
    border-top: 1px dashed rgba(255, 255, 255, 0.12);
  }
  .composer-media-card {
    position: relative;
    background: #181d20;
    border: 1px solid rgba(56, 189, 248, 0.4);
    border-radius: 8px;
    overflow: hidden;
    width: 96px;
    height: 96px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    transition: transform 0.2s, border-color 0.2s;
  }
  .composer-media-card:hover {
    border-color: #38bdf8;
    transform: translateY(-2px);
  }
  .composer-preview-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    cursor: pointer;
    background: #0f172a;
  }
  .composer-preview-video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    background: #000;
  }
  .btn-del-media-card {
    position: absolute;
    top: 4px;
    right: 4px;
    background: rgba(239, 68, 68, 0.9);
    color: #ffffff;
    border: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    font-size: 10px;
    font-weight: bold;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 5;
    transition: background 0.15s, transform 0.15s;
    line-height: 1;
    padding: 0;
  }
  .btn-del-media-card:hover {
    background: #ef4444;
    transform: scale(1.15);
  }
  .comment-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    flex-wrap: wrap;
    gap: 8px;
  }
  .toolbar-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .btn-comment-tool {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .btn-comment-tool:hover {
    background: rgba(255, 255, 255, 0.16);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.25);
  }
  .clipboard-paste-hint {
    font-size: 11px;
    color: #94a3b8;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    background: rgba(255, 255, 255, 0.04);
    border-radius: 4px;
  }
  .clipboard-paste-hint kbd {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 1px 0 rgba(0, 0, 0, 0.3);
    color: #38bdf8;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 10px;
    font-family: inherit;
    font-weight: 600;
  }
  .btn-save-comment {
    background: #0055cc;
    color: #ffffff;
    border: none;
    padding: 5px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }
  .btn-save-comment:hover:not(:disabled) {
    background: #0065ff;
  }
  .btn-save-comment:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .activity-timeline {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-height: 380px;
    overflow-y: auto;
    padding-right: 4px;
  }

  .custom-comment-scrollbar::-webkit-scrollbar {
    width: 6px;
  }
  .custom-comment-scrollbar::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
  }
  .custom-comment-scrollbar::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 4px;
  }
  .custom-comment-scrollbar::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.35);
  }

  .activity-item {
    display: flex;
    gap: 10px;
    font-size: 13px;
  }
  .act-avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    object-fit: cover;
    margin-top: 2px;
  }
  .act-initials {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #0284c7;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 2px;
  }
  .act-details {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .act-text {
    background: #22272b;
    padding: 8px 12px;
    border-radius: 8px;
    color: #dee4ea;
    line-height: 1.45;
    word-break: break-word;
    overflow-wrap: break-word;
  }
  .act-text strong {
    display: block;
    margin-bottom: 4px;
    color: #9fadbc;
  }
  .act-date {
    font-size: 11px;
    color: #738496;
    margin-left: 4px;
  }

  .comments-collapsed-placeholder {
    padding: 12px;
    background: #22272b;
    border-radius: 8px;
    color: #8c9bab;
    font-size: 13px;
    cursor: pointer;
    text-align: center;
    transition: background 0.2s;
  }
  .comments-collapsed-placeholder:hover {
    background: #282e33;
    color: #dee4ea;
  }

  /* Media & Link Styling in Comments & Description */
  .comment-image-container {
    margin: 8px 0;
    cursor: pointer;
  }
  .comment-attached-image {
    max-width: 100%;
    max-height: 260px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(0, 0, 0, 0.2);
    transition: transform 0.2s, border-color 0.2s;
    display: block;
  }
  .comment-attached-image:hover {
    transform: scale(1.015);
    border-color: #38bdf8;
  }

  .comment-video-container {
    margin: 8px 0;
    background: #111827;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    overflow: hidden;
    max-width: 100%;
  }
  .comment-video-player {
    width: 100%;
    max-height: 280px;
    display: block;
    background: #000;
  }
  .video-meta-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 10px;
    font-size: 11px;
    color: #94a3b8;
    background: rgba(0, 0, 0, 0.4);
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
  .video-open-link {
    color: #38bdf8;
    text-decoration: none;
    font-weight: 600;
  }
  .video-open-link:hover {
    text-decoration: underline;
  }

  .comment-rich-link {
    color: #38bdf8;
    text-decoration: underline;
    text-underline-offset: 2px;
    font-weight: 500;
    word-break: break-all;
    transition: color 0.15s;
    margin: 0 2px;
  }
  .comment-rich-link:hover {
    color: #7dd3fc;
  }

  /* Lightbox Modal */
  .image-lightbox-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.88);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .image-lightbox-content {
    position: relative;
    max-width: 90vw;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }
  .lightbox-full-img {
    max-width: 90vw;
    max-height: 80vh;
    object-fit: contain;
    border-radius: 8px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.9);
  }
  .lightbox-close-btn {
    position: absolute;
    top: -36px;
    right: 0;
    background: rgba(255, 255, 255, 0.2);
    border: none;
    color: #ffffff;
    font-size: 18px;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    cursor: pointer;
  }
  .lightbox-toolbar {
    display: flex;
    justify-content: center;
  }
  .lightbox-btn-download {
    color: #38bdf8;
    text-decoration: none;
    font-size: 13px;
    background: rgba(0, 0, 0, 0.6);
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid rgba(56, 189, 248, 0.4);
  }

  /* Common Modal Elements */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(8px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999;
  }
  .modal-card {
    width: 95vw;
    max-width: 580px;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .modal-title {
    margin: 0;
    font-size: 1.25rem;
    color: #f8fafc;
  }
  .modal-subtitle {
    margin: 2px 0 0 0;
    font-size: 0.85rem;
    color: #94a3b8;
  }
  .btn-close {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 18px;
    cursor: pointer;
  }
  .btn-close:hover {
    color: #fff;
  }

  .provider-tabs {
    display: flex;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  .tab-btn-modal {
    flex: 1;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  .tab-btn-modal.active {
    border-bottom-color: #38bdf8;
    background: rgba(56, 189, 248, 0.08);
  }

  .provider-guide {
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    color: #e0f2fe;
    margin-bottom: 14px;
  }
  .provider-guide a {
    color: #38bdf8;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }
  .form-row {
    display: flex;
    gap: 12px;
  }
  .form-group label {
    font-size: 0.85rem;
    color: #cbd5e1;
    font-weight: 500;
  }
  .required {
    color: #f87171;
  }
  .form-group input {
    background: rgba(15, 23, 42, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 8px 12px;
    color: #f1f5f9;
    font-size: 0.9rem;
  }
  .form-group input:focus {
    outline: none;
    border-color: #a855f7;
  }

  .modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
  }

  .btn-test-conn {
    background: rgba(234, 179, 8, 0.15);
    border: 1px solid rgba(234, 179, 8, 0.4);
    color: #facc15;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
  }
  .btn-secondary {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    cursor: pointer;
  }
  .btn-primary {
    background: linear-gradient(135deg, #7c3aed 0%, #3b82f6 100%);
    border: none;
    color: #ffffff;
    padding: 8px 18px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
  }

  .badge {
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
  }
  .badge.priority-high {
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
  }
  .badge.priority-medium {
    background: rgba(59, 130, 246, 0.2);
    color: #60a5fa;
  }
  .badge.priority-low {
    background: rgba(100, 116, 139, 0.2);
    color: #94a3b8;
  }

  .empty-column {
    padding: 24px;
    text-align: center;
    color: #64748b;
    font-size: 0.85rem;
    font-style: italic;
  }

  .spinner-small {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Header Agile & Filter Buttons */
  .btn-agile-tools {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(234, 179, 8, 0.12);
    border: 1px solid rgba(234, 179, 8, 0.35);
    color: #fef08a;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-agile-tools:hover {
    background: rgba(234, 179, 8, 0.22);
    border-color: rgba(234, 179, 8, 0.6);
    transform: translateY(-1px);
  }
  .agile-pts-badge {
    background: #ca8a04;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 10px;
  }

  .btn-filter-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.16);
    color: #cbd5e1;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-filter-toggle:hover {
    background: rgba(255, 255, 255, 0.16);
    color: #ffffff;
    transform: translateY(-1px);
  }
  .btn-filter-toggle.has-active-filters {
    background: rgba(56, 189, 248, 0.18);
    border-color: #38bdf8;
    color: #38bdf8;
  }
  .filter-count-badge {
    background: #0284c7;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 10px;
  }
  .filter-count-badge.small {
    font-size: 10px;
    padding: 1px 5px;
    margin-left: 2px;
  }

  .btn-filter-quick {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-filter-quick:hover {
    background: rgba(255, 255, 255, 0.16);
    color: #ffffff;
  }
  .btn-filter-quick.active {
    background: rgba(56, 189, 248, 0.18);
    border-color: #38bdf8;
    color: #38bdf8;
  }

  /* Active Filters Strip */
  .active-filters-strip {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    margin-bottom: 14px;
    flex-wrap: wrap;
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(56, 189, 248, 0.25);
    border-radius: 10px;
    font-size: 0.82rem;
  }
  .strip-label {
    color: #38bdf8;
    font-weight: 600;
  }
  .active-filter-tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(30, 41, 59, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #e2e8f0;
    padding: 3px 8px;
    border-radius: 6px;
  }
  .active-filter-tag button {
    background: transparent;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    font-size: 11px;
    padding: 0;
  }
  .active-filter-tag button:hover {
    color: #f87171;
  }
  .btn-clear-all-filters {
    background: transparent;
    border: none;
    color: #f87171;
    font-size: 0.8rem;
    cursor: pointer;
    text-decoration: underline;
    margin-left: auto;
  }

  /* Agile Tools Modal Styling (Screenshot 1) */
  .agile-tools-modal-card {
    background: #1c2128;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    width: 380px;
    max-width: 90vw;
    color: #dee4ea;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
    overflow: hidden;
  }
  .agile-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  .agile-modal-body {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .agile-toggle-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }
  .toggle-label {
    font-size: 0.9rem;
    color: #cbd5e1;
    font-weight: 500;
  }

  /* Toggle Switch */
  .switch {
    position: relative;
    display: inline-block;
    width: 44px;
    height: 24px;
  }
  .switch input {
    opacity: 0;
    width: 0;
    height: 0;
  }
  .slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background-color: #334155;
    transition: .3s;
  }
  .slider:before {
    position: absolute;
    content: "";
    height: 18px;
    width: 18px;
    left: 3px;
    bottom: 3px;
    background-color: white;
    transition: .3s;
  }
  input:checked + .slider {
    background-color: #22c55e;
  }
  input:checked + .slider:before {
    transform: translateX(20px);
  }
  .slider.round {
    border-radius: 24px;
  }
  .slider.round:before {
    border-radius: 50%;
  }

  .points-counts-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .points-counts-title {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 700;
    color: #f1f5f9;
  }
  .points-list-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 280px;
    overflow-y: auto;
    padding-right: 4px;
  }
  .point-item-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.88rem;
    color: #cbd5e1;
    padding: 4px 0;
  }
  .point-col-name {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .point-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .point-val {
    font-weight: 600;
    color: #f8fafc;
  }
  .point-total-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 10px;
    margin-top: 6px;
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    font-size: 0.95rem;
  }
  .total-label {
    font-weight: 700;
    color: #f1f5f9;
  }
  .total-pts-highlight {
    color: #facc15;
    font-size: 1.05rem;
    font-weight: 800;
  }

  .agile-extra-stats {
    display: flex;
    gap: 10px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }
  .stat-badge {
    flex: 1;
    background: rgba(15, 23, 42, 0.6);
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.8rem;
    color: #94a3b8;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .stat-badge strong {
    color: #38bdf8;
    font-size: 0.95rem;
  }

  /* Filter Modal Styling (Screenshot 2) */
  .filter-modal-card {
    background: #1c2128;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
    width: 360px;
    max-width: 90vw;
    color: #dee4ea;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6);
    display: flex;
    flex-direction: column;
    max-height: 85vh;
  }
  .filter-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  .filter-modal-body {
    padding: 16px 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 18px;
    flex: 1;
  }
  .filter-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .filter-section-title {
    font-size: 0.85rem;
    font-weight: 700;
    color: #9fadbc;
    text-transform: capitalize;
  }
  .filter-input-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }
  .filter-text-input {
    width: 100%;
    background: #22272b;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    padding: 8px 30px 8px 12px;
    color: #f1f5f9;
    font-size: 0.88rem;
    box-sizing: border-box;
  }
  .filter-text-input:focus {
    outline: none;
    border-color: #38bdf8;
  }
  .clear-input-inline {
    position: absolute;
    right: 8px;
    background: transparent;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    font-size: 11px;
  }
  .filter-helper-text {
    font-size: 0.75rem;
    color: #738496;
  }

  .filter-checkbox-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 6px;
    font-size: 0.88rem;
    color: #cbd5e1;
    cursor: pointer;
    transition: background 0.15s;
  }
  .filter-checkbox-item:hover {
    background: rgba(255, 255, 255, 0.05);
  }
  .filter-checkbox-item input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
    accent-color: #38bdf8;
  }
  .member-icon-circle {
    font-size: 14px;
    color: #94a3b8;
  }

  .filter-members-sublist {
    margin-left: 12px;
    padding-left: 10px;
    border-left: 2px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-height: 180px;
    overflow-y: auto;
  }
  .sublist-heading {
    font-size: 0.78rem;
    color: #738496;
    margin-bottom: 2px;
  }
  .filter-member-avatar {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    object-fit: cover;
  }
  .filter-member-initials {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #0284c7;
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .member-name-text {
    font-size: 0.85rem;
  }
  .member-name-text small {
    color: #738496;
    margin-left: 4px;
  }

  .filter-pill-group {
    display: flex;
    gap: 6px;
  }
  .filter-pill-btn {
    flex: 1;
    background: #22272b;
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  .filter-pill-btn.active {
    background: rgba(56, 189, 248, 0.2);
    border-color: #38bdf8;
    color: #38bdf8;
    font-weight: 600;
  }

  .filter-labels-sublist {
    margin-left: 12px;
    padding-left: 10px;
    border-left: 2px solid rgba(255, 255, 255, 0.08);
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 200px;
    overflow-y: auto;
  }
  .filter-label-pill-item {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
  }
  .filter-label-pill-item input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
    accent-color: #38bdf8;
  }
  .filter-label-bar {
    flex: 1;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 12px;
    border-radius: 6px;
    color: #ffffff;
    font-size: 0.82rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  }
  .label-text-bold {
    font-weight: 700;
  }
  .label-count-tag {
    background: rgba(0, 0, 0, 0.35);
    padding: 1px 6px;
    border-radius: 8px;
    font-size: 0.75rem;
  }

  .filter-modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(0, 0, 0, 0.2);
  }
  .btn-clear-filters {
    background: transparent;
    border: none;
    color: #f87171;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 500;
  }
  .btn-clear-filters:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .btn-apply-filters {
    background: #0055cc;
    border: none;
    color: #ffffff;
    padding: 8px 18px;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
  }
  .btn-apply-filters:hover {
    background: #0065ff;
  }
</style>
