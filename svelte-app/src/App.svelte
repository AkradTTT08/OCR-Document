<script>
  import { fade, fly, scale, slide } from "svelte/transition";
  import UploadPanel from "./lib/UploadPanel.svelte";
  import ResultsPanel from "./lib/ResultsPanel.svelte";
  import KnowledgeBase from "./lib/KnowledgeBase.svelte";
  import SkillManager from "./lib/SkillManager.svelte";
  import { qaHistory, selectedHistory, loadQAHistoryFromDB, selectedProjectStore, qaSessionGroups, activeQAContext, allGroups, loadQAGroupsFromDB, activeSidebarGroup } from "./lib/qaHistoryStore.js";
  import { perfHistory, selectedPerfHistory, loadPerfHistory } from "./lib/perfHistoryStore.js";
  import { ocrHistory, loadOCRHistory, saveOCRResult, deleteOCRHistory, getOCRDetail } from "./lib/ocrHistoryStore.js";
  import ProjectManagement from './lib/ProjectManagement.svelte';

  import Toast from "./lib/Toast.svelte";
  import Login from "./lib/Login.svelte";
  import ComingSoon from "./lib/ComingSoon.svelte";
  import QAConsult from "./lib/QAConsult.svelte";
  import QAMember from "./lib/QAMember.svelte";
  import ExitCriteriaManager from "./lib/ExitCriteriaManager.svelte";
  import ApiCollectionAdmin from "./lib/ApiCollectionAdmin.svelte";
  import ApiUsageDashboard from "./lib/ApiUsageDashboard.svelte";
  import QAAnalysisDiagram from "./lib/QAAnalysisDiagram.svelte";
  import QAPerformance from "./lib/QAPerformance.svelte";
  import QAResearch from "./lib/QAResearch.svelte";
  import QASecurity from "./lib/QASecurity.svelte";
  import QATestAutomation from "./lib/QATestAutomation.svelte";
  import QADocumentCreation from "./lib/QADocumentCreation.svelte";
  import QABoardCard from "./lib/QABoardCard.svelte";
  import MasterAgentUI from "./lib/MasterAgentUI.svelte";
  import WorkflowBuilder from "./lib/WorkflowBuilder.svelte";
  import TutorialOverlay from "./lib/TutorialOverlay.svelte";
  import LegalModal from "./lib/LegalModal.svelte";
  import NotificationDropdown from "./lib/NotificationDropdown.svelte";
  import NotificationConfigModal from "./lib/NotificationConfigModal.svelte";
  import { unreadCount, startNotificationSync, stopNotificationSync } from "./lib/notificationStore.js";
  import { showLogin, authRole, authUser, authDisplayName, authAvatar, authAllowedMenus, authAllowedProjects, DEFAULT_USER_MENUS, DEFAULT_ADMIN_MENUS, logout, updateAuthProfile } from "./lib/authStore.js";
  import { globalSearchQuery, triggerGlobalSearch } from "./lib/globalStore.js";
  import { onMount, onDestroy } from "svelte";
  import { toast } from "./lib/toastStore.js";

  let showNotifications = false;
  let notiTriggerBtn = null;
  let showNotificationConfigModal = false;
  let isOcrHistoryExpanded = true;
  let isQaGroupsExpanded = true;
  let isQaHistoryExpanded = true;
  let isPerfHistoryExpanded = true;
  let isSidebarCollapsed = false;
  let isMobileSidebarOpen = false;
  let sidebarHistorySearch = "";
  let activeHistoryId = null;
  let navSectionOpen = {
    discovery: true,
    testing: true,
    agents: true,
    admin_ocr: true,
    admin_platform: true,
    admin_api: true
  };

  function toggleNavSection(key) {
    if (isSidebarCollapsed) {
      isSidebarCollapsed = false;
      navSectionOpen[key] = true;
      return;
    }
    navSectionOpen[key] = !navSectionOpen[key];
  }

  function getHistoryExitStatus(item) {
    const st = String(item?.exit_criteria_eval?.status || item?.status || '').toUpperCase();
    if (st === 'PASSED' || st === 'PASS') return 'passed';
    if (st.includes('CONDITIONAL')) return 'conditional';
    if (st === 'REJECTED' || st === 'FAIL' || st === 'FAILED') return 'rejected';
    return 'neutral';
  }

  function handleSidebarProjectSelect(e) {
    const val = e.target.value;
    if (!val) {
      selectedProjectStore.set(null);
      activeSidebarGroup.set(null);
      return;
    }
    const found = sidebarProjects.find(p => String(p.id || p.project_id) === String(val));
    if (found) {
      selectedProjectStore.set(found);
      activeSidebarGroup.set(null);
    }
  }

  function formatCleanGroupName(name) {
    let clean = String(name || 'General').trim();
    while (/^\[.*?\]\s*/.test(clean)) {
      clean = clean.replace(/^\[.*?\]\s*/, '').trim();
    }
    return clean || 'General';
  }

  function formatGroupType(group) {
    const rawType = String(group?.group_type || '').replace(/^\[|\]$/g, '').trim();
    if (rawType) return rawType;
    const match = String(group?.group_name || '').match(/^\[(.*?)\]/);
    return match ? match[1].trim() : 'General';
  }

  let sidebarProjects = [];

  function isMenuAllowed(menuKey) {
    if (!$authAllowedMenus || $authAllowedMenus.length === 0) {
      return true;
    }
    return $authAllowedMenus.includes(menuKey);
  }

  function isProjectAllowed(proj) {
    if (!$authAllowedProjects || $authAllowedProjects.includes('all')) return true;
    if (!proj) return false;
    const pId = String(proj.id || proj.project_id || '').trim().toLowerCase();
    const pCode = String(proj.project_code || '').trim().toLowerCase();
    return $authAllowedProjects.some(allowed => {
      const a = String(allowed).trim().toLowerCase();
      return (pId && a === pId) || (pCode && a === pCode);
    });
  }

  // Reactive enforcement: if selected project is not in allowed projects, reset selection immediately
  $: {
    if ($authRole === 'user' && $selectedProjectStore && !isProjectAllowed($selectedProjectStore)) {
      selectedProjectStore.set(null);
      activeSidebarGroup.set(null);
    }
  }

  onMount(async () => {
    loadQAHistoryFromDB();
    loadQAGroupsFromDB();
    loadPerfHistory();
    loadOCRHistory();
    startNotificationSync(6000);
    // Load projects for sidebar group mapping
    try {
      const res = await fetch('/api/projects');
      if (res.ok) {
        const data = await res.json();
        sidebarProjects = (data.projects || []).filter(isProjectAllowed);
      }
    } catch(e) {
      console.error('Failed to load projects for sidebar:', e);
    }


    // Health check polling
    setInterval(async () => {
      try {
        const res = await fetch('/api/projects', { method: 'GET' });
        systemReady = res.ok;
      } catch (e) {
        systemReady = false;
      }
    }, 10000);
  });

  onDestroy(() => {
    stopNotificationSync();
  });

  let systemReady = true;
  let globalSearchInputEl;

  const VIEW_LABELS = {
    ocr: 'OCR Spell Check',
    project_management: 'Project Management',
    kb: 'Knowledge Base',
    skills: 'AI Skills',
    qa_member: 'QA Member',
    exit_criteria: 'Exit Criteria',
    api_collection: 'API Collections',
    api_usage: 'Token Usage',
    qa_consult: 'QA Consult',
    qa_doc_creation: 'QA Document Creation',
    qa_analysis_diagram: 'QA Analysis Diagram',
    qa_board: 'QA Board Card',
    qa_automate: 'QA Test Automation',
    qa_performance: 'QA Performance',
    qa_security: 'QA Security',
    qa_research: 'QA Research',
    master_agent: 'Spectra QA — Orchestration',
    workflow_builder: 'AI Workflow Builder',
  };

  function handleGlobalKeydown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      if (globalSearchInputEl) {
        e.preventDefault();
        globalSearchInputEl.focus();
      }
      return;
    }
    if (e.key === 'Escape') {
      if (showSidebarDeleteModal && !isSidebarDeleting) cancelSidebarDelete();
      else if (showMyProfileModal) requestCloseProfileModal();
      else if (showProfileMenu) showProfileMenu = false;
      else if (showNotifications) { showNotifications = false; notiTriggerBtn?.focus(); }
      else if (showNotificationConfigModal) showNotificationConfigModal = false;
    }
  }

  function handleGroupClick(group) {
    const cleanClickedName = String(group.group_name || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();
    const cleanActiveName = String($activeSidebarGroup?.group_name || '').replace(/^\[.*?\]\s*/, '').trim().toLowerCase();

    // Toggle off if clicking the already active group
    if ($activeSidebarGroup && cleanClickedName === cleanActiveName) {
      activeSidebarGroup.set(null);
      return;
    }

    // Find the project for this group
    const proj = sidebarProjects.find(p => String(p.id || p.project_id) === String(group.project_id) || (p.project_code && group.project_code && p.project_code === group.project_code)) || $selectedProjectStore;
    if (proj) {
      selectedProjectStore.set(proj);
      activeView = 'qa_consult';
      activeQAContext.set({ project: proj, group_name: group.group_name, group_type: group.group_type });
      activeSidebarGroup.set({ project: proj, group_name: group.group_name, group_type: group.group_type });
    } else {
      // If project not found in list, still try to navigate
      activeView = 'qa_consult';
      const ctx = { 
        project: { id: group.project_id, project_id: group.project_id, project_code: group.project_code || 'Unknown', name: group.project_code || 'Project' }, 
        group_name: group.group_name, 
        group_type: group.group_type 
      };
      selectedProjectStore.set(ctx.project);
      activeQAContext.set(ctx);
      activeSidebarGroup.set(ctx);
    }
  }

  let showSidebarDeleteModal = false;
  let sidebarItemToDelete = null;
  let isSidebarDeleting = false;

  function promptDeleteGroup(group) {
    sidebarItemToDelete = { type: 'group', item: group, name: group.group_name || 'General', typeName: group.group_type || 'General' };
    showSidebarDeleteModal = true;
  }

  function promptDeleteHistory(history) {
    sidebarItemToDelete = { type: 'history', item: history, name: history.filename || 'เอกสารนี้', typeName: history.docType || 'Document' };
    showSidebarDeleteModal = true;
  }

  function cancelSidebarDelete() {
    showSidebarDeleteModal = false;
    sidebarItemToDelete = null;
  }

  async function executeSidebarDelete() {
    if (!sidebarItemToDelete) return;
    isSidebarDeleting = true;
    try {
      if (sidebarItemToDelete.type === 'group') {
        const group = sidebarItemToDelete.item;
        const gName = group.group_name || 'General';
        const res = await fetch("/api/qa_groups/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: group.project_id,
            group_name: gName
          })
        });
        if (res.ok) {
          toast(`ลบกลุ่ม "${gName}" เรียบร้อยแล้ว`, "success");
          qaSessionGroups.update(gs => gs.filter(g => !(g.project_id === group.project_id && g.group_name === gName)));
          if ($activeSidebarGroup && String($activeSidebarGroup.group_name || '').toLowerCase() === String(gName).toLowerCase()) {
            activeSidebarGroup.set(null);
          }
          await loadQAGroupsFromDB();
          await loadQAHistoryFromDB();
          showSidebarDeleteModal = false;
          sidebarItemToDelete = null;
        } else {
          const err = await res.json();
          toast(err.error || "ไม่สามารถลบกลุ่มได้", "error");
        }
      } else if (sidebarItemToDelete.type === 'history') {
        const item = sidebarItemToDelete.item;
        const fName = item.filename || 'เอกสารนี้';
        const res = await fetch(`/api/qa_transactions/${item.id}`, {
          method: "DELETE"
        });
        if (res.ok) {
          toast(`ลบประวัติ "${fName}" เรียบร้อยแล้ว`, "success");
          await loadQAHistoryFromDB();
          await loadQAGroupsFromDB();
          showSidebarDeleteModal = false;
          sidebarItemToDelete = null;
        } else {
          const err = await res.json();
          toast(err.error || "ไม่สามารถลบประวัติได้", "error");
        }
      }
    } catch (e) {
      console.error(e);
      toast("เกิดข้อผิดพลาดในการลบ", "error");
    } finally {
      isSidebarDeleting = false;
    }
  }

  let scanResult = null;
  let isProcessing = false;
  let progress = { pct: 0, label: "", step: 0 };
  let activeView = "ocr"; // 'ocr' | 'kb' | 'skills' | 'qa_consult'

  // Reactive statement to enforce allowed view based on permissions and role
  $: {
    if ($authRole === 'user') {
      const userAllowed = ($authAllowedMenus && $authAllowedMenus.length > 0) ? $authAllowedMenus : DEFAULT_USER_MENUS;
      if (!userAllowed.includes(activeView)) {
        activeView = userAllowed[0] || 'qa_consult';
      }
    } else if ($authRole === 'admin') {
      const adminAllowed = ($authAllowedMenus && $authAllowedMenus.length > 0) ? $authAllowedMenus : DEFAULT_ADMIN_MENUS;
      if (!adminAllowed.includes(activeView)) {
        activeView = adminAllowed[0] || 'ocr';
      }
    }
  }

  async function handleResult(event) {
    scanResult = event.detail;
    if (scanResult && !scanResult.id) {
        const saved = await saveOCRResult(scanResult);
        if (saved && saved.id) {
            scanResult = { ...scanResult, id: saved.id, date: saved.date };
        }
    }
  }

  async function selectOCRHistory(item) {
    if (!item) return;
    activeView = 'ocr';
    scanResult = item;
    if (!item.pages || item.pages.length === 0) {
      const full = await getOCRDetail(item.id);
      if (full && full.pages) {
        scanResult = full;
      }
    }
  }

  function handleProcessing(event) {
    isProcessing = event.detail.active;
    if (event.detail.progress) progress = event.detail.progress;
  }


  function onGlobalSearchKey(e) {
    if (e.key === 'Enter' && $globalSearchQuery.trim()) {
      activeView = 'kb';
      triggerGlobalSearch.set(true);
    }
  }

  let showProfileMenu = false;
  let showMyProfileModal = false;
  let showTutorial = false;
  let legalModalType = null;
  let myProfileFormData = { 
    display_name: '', 
    current_password: '',
    password: '',
    password_confirm: '',
    phone: '',
    department: '',
    github_url: '',
    linkedin_url: '',
    line_id: '',
    avatar_path: undefined
  };
  let initialProfileSnapshot = null;
  let isLoadingMyProfile = false;
  let profileLoadError = null;
  let isSavingMyProfile = false;
  let showMyCurrentPassword = false;
  let showMyPassword = false;
  let showMyPasswordConfirm = false;
  let profileValidationError = '';
  let confirmDiscardProfile = false;
  let myProfileAvatarFile = null;
  let myProfileAvatarPreview = null;
  let myProfileAvatarBlobUrl = null;
  let previousAvatarBeforeRemove = null;
  let avatarRemovalPending = false;
  let previewImageError = false;
  let topbarAvatarError = false;
  let isDragOverAvatar = false;
  let activeProfileTab = 'general';

  $: hasUnsavedProfileChanges = (() => {
    if (!initialProfileSnapshot) return false;
    if (myProfileAvatarFile || avatarRemovalPending) return true;
    if (myProfileFormData.password || myProfileFormData.password_confirm) return true;
    return (
      (myProfileFormData.display_name || '') !== (initialProfileSnapshot.display_name || '') ||
      (myProfileFormData.department || '') !== (initialProfileSnapshot.department || '') ||
      (myProfileFormData.phone || '') !== (initialProfileSnapshot.phone || '') ||
      (myProfileFormData.github_url || '') !== (initialProfileSnapshot.github_url || '') ||
      (myProfileFormData.linkedin_url || '') !== (initialProfileSnapshot.linkedin_url || '') ||
      (myProfileFormData.line_id || '') !== (initialProfileSnapshot.line_id || '')
    );
  })();

  $: generalTabDirty = !!(initialProfileSnapshot && (
    (myProfileFormData.display_name || '') !== (initialProfileSnapshot.display_name || '') ||
    (myProfileFormData.department || '') !== (initialProfileSnapshot.department || '') ||
    (myProfileFormData.phone || '') !== (initialProfileSnapshot.phone || '')
  ));

  $: socialTabDirty = !!(initialProfileSnapshot && (
    (myProfileFormData.github_url || '') !== (initialProfileSnapshot.github_url || '') ||
    (myProfileFormData.linkedin_url || '') !== (initialProfileSnapshot.linkedin_url || '') ||
    (myProfileFormData.line_id || '') !== (initialProfileSnapshot.line_id || '')
  ));

  $: securityTabDirty = !!(myProfileFormData.current_password || myProfileFormData.password || myProfileFormData.password_confirm);

  $: passwordMismatch = !!(
    myProfileFormData.password &&
    myProfileFormData.password_confirm &&
    myProfileFormData.password !== myProfileFormData.password_confirm
  );

  $: passwordTooShort = !!(
    myProfileFormData.password &&
    myProfileFormData.password.length > 0 &&
    myProfileFormData.password.length < 8
  );
  
  function getUserIdFromToken() {
      const token = localStorage.getItem('jwt_token');
      if (!token) return null;
      try {
          const base64Url = token.split('.')[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const payload = JSON.parse(window.atob(base64));
          return payload.user_id;
      } catch(e) { return null; }
  }

  function revokeAvatarBlob() {
      if (myProfileAvatarBlobUrl) {
          URL.revokeObjectURL(myProfileAvatarBlobUrl);
          myProfileAvatarBlobUrl = null;
      }
  }

  function requestCloseProfileModal() {
      if (isSavingMyProfile) return;
      if (hasUnsavedProfileChanges && !confirmDiscardProfile) {
          confirmDiscardProfile = true;
          return;
      }
      revokeAvatarBlob();
      confirmDiscardProfile = false;
      profileValidationError = '';
      showMyProfileModal = false;
  }

  function handleProfileKeydown(e) {
      if (showMyProfileModal && e.key === 'Escape') {
          e.preventDefault();
          requestCloseProfileModal();
      }
  }
  
  async function openMyProfileModal() {
      showProfileMenu = false;
      revokeAvatarBlob();
      confirmDiscardProfile = false;
      profileValidationError = '';
      profileLoadError = null;
      avatarRemovalPending = false;
      previousAvatarBeforeRemove = null;
      showMyCurrentPassword = false;
      showMyPassword = false;
      showMyPasswordConfirm = false;

      let currentDisplayName = localStorage.getItem('auth_display_name') || localStorage.getItem('auth_user') || '';
      let currentAvatar = localStorage.getItem('auth_avatar_path') || '';
      myProfileFormData = { 
        display_name: currentDisplayName, 
        current_password: '',
        password: '',
        password_confirm: '',
        phone: '',
        department: '',
        github_url: '',
        linkedin_url: '',
        line_id: '',
        avatar_path: currentAvatar || undefined
      };
      myProfileAvatarFile = null;
      myProfileAvatarPreview = currentAvatar ? `${currentAvatar}` : null;
      previewImageError = false;
      activeProfileTab = 'general';
      showMyProfileModal = true;

      await fetchMyProfileDetail(currentDisplayName, currentAvatar);
  }

  async function fetchMyProfileDetail(fallbackName = '', fallbackAvatar = '') {
      const userId = getUserIdFromToken();
      if (!userId) {
          profileLoadError = 'ไม่พบข้อมูลเซสชันผู้ใช้งาน กรุณาเข้าสู่ระบบใหม่อีกครั้ง';
          return;
      }
      isLoadingMyProfile = true;
      profileLoadError = null;
      try {
          const token = localStorage.getItem('jwt_token');
          const res = await fetch(`/api/users/${userId}`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
          }
          const data = await res.json();
          if (data.user) {
            myProfileFormData = {
              display_name: data.user.display_name || fallbackName,
              current_password: '',
              password: '',
              password_confirm: '',
              phone: data.user.phone || '',
              department: data.user.department || '',
              github_url: data.user.github_url || '',
              linkedin_url: data.user.linkedin_url || '',
              line_id: data.user.line_id || '',
              avatar_path: data.user.avatar_path || fallbackAvatar || undefined
            };
            myProfileAvatarPreview = data.user.avatar_path ? `${data.user.avatar_path}` : (fallbackAvatar || null);
            previewImageError = false;
            initialProfileSnapshot = { ...myProfileFormData };
          } else {
            throw new Error('ไม่พบข้อมูลผู้ใช้งาน');
          }
      } catch (e) {
          console.error('Failed to load user detail', e);
          profileLoadError = 'ไม่สามารถโหลดข้อมูลโปรไฟล์ล่าสุดจากเซิร์ฟเวอร์ได้ กรุณาลองใหม่อีกครั้งเพื่อป้องกันการบันทึกทับข้อมูลเดิม';
      } finally {
          isLoadingMyProfile = false;
      }
  }

  function validateAndSetAvatarFile(file) {
      if (!file) return;
      const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
      if (!allowedTypes.includes(file.type)) {
          toast('รองรับเฉพาะไฟล์รูปภาพ JPG, PNG หรือ WEBP เท่านั้น', 'warning');
          return;
      }
      const maxSizeBytes = 5 * 1024 * 1024;
      if (file.size > maxSizeBytes) {
          toast('ขนาดไฟล์รูปภาพต้องไม่เกิน 5 MB', 'warning');
          return;
      }
      revokeAvatarBlob();
      myProfileAvatarBlobUrl = URL.createObjectURL(file);
      myProfileAvatarFile = file;
      myProfileAvatarPreview = myProfileAvatarBlobUrl;
      avatarRemovalPending = false;
      previousAvatarBeforeRemove = null;
      previewImageError = false;
      confirmDiscardProfile = false;
      toast('เลือกรูปโปรไฟล์ใหม่แล้ว (กดบันทึกเพื่อยืนยัน)', 'success');
  }
  
  function removeMyAvatar() {
      if (!avatarRemovalPending) {
          previousAvatarBeforeRemove = myProfileAvatarPreview;
      }
      revokeAvatarBlob();
      myProfileAvatarFile = null;
      myProfileAvatarPreview = null;
      myProfileFormData.avatar_path = '';
      avatarRemovalPending = true;
      previewImageError = false;
      confirmDiscardProfile = false;
  }

  function undoRemoveMyAvatar() {
      myProfileAvatarPreview = previousAvatarBeforeRemove;
      myProfileFormData.avatar_path = previousAvatarBeforeRemove || undefined;
      avatarRemovalPending = false;
      previousAvatarBeforeRemove = null;
      previewImageError = false;
  }

  function handleAvatarDrop(e) {
      e.preventDefault();
      isDragOverAvatar = false;
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
          validateAndSetAvatarFile(e.dataTransfer.files[0]);
      }
  }

  async function saveMyProfile() {
      if (isSavingMyProfile || isLoadingMyProfile || profileLoadError) return;
      profileValidationError = '';

      if (!myProfileFormData.display_name || !myProfileFormData.display_name.trim()) {
          activeProfileTab = 'general';
          profileValidationError = 'กรุณาระบุชื่อที่แสดงในระบบ (Display Name)';
          return;
      }

      if (myProfileFormData.password || myProfileFormData.password_confirm) {
          if ($authRole !== 'admin' && !myProfileFormData.current_password) {
              activeProfileTab = 'security';
              profileValidationError = 'กรุณาระบุรหัสผ่านปัจจุบันเพื่อยืนยันการเปลี่ยนรหัสผ่าน';
              return;
          }
          if (myProfileFormData.password.length < 8) {
              activeProfileTab = 'security';
              profileValidationError = 'รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 8 ตัวอักษร';
              return;
          }
          if (myProfileFormData.password.length > 72) {
              activeProfileTab = 'security';
              profileValidationError = 'รหัสผ่านใหม่ต้องมีความยาวไม่เกิน 72 ตัวอักษร';
              return;
          }
          if (myProfileFormData.password !== myProfileFormData.password_confirm) {
              activeProfileTab = 'security';
              profileValidationError = 'รหัสผ่านใหม่และการยืนยันรหัสผ่านไม่ตรงกัน';
              return;
          }
      }

      const userId = getUserIdFromToken();
      if (!userId) {
          toast('เซสชันหมดอายุ กรุณาเข้าสู่ระบบใหม่อีกครั้ง', 'error');
          return;
      }
      
      isSavingMyProfile = true;
      try {
          const token = localStorage.getItem('jwt_token');
          const headers = { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
          
          let newAvatarPath = myProfileFormData.avatar_path;

          // 1) หากผู้ใช้อัปโหลดรูปใหม่ ให้ส่งไฟล์ไปยัง /api/users/:id/avatar ก่อน
          if (myProfileAvatarFile) {
              const fd = new FormData();
              fd.append('avatar', myProfileAvatarFile);
              const avaRes = await fetch(`/api/users/${userId}/avatar`, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${token}` },
                  body: fd
              });
              const avaData = await avaRes.json().catch(() => ({}));
              if (avaRes.ok && avaData.success) {
                  newAvatarPath = avaData.avatar_path;
              } else {
                  toast(avaData.error || 'ไม่สามารถอัปโหลดรูปภาพโปรไฟล์ได้ กรุณาลองใหม่', 'error');
                  return;
              }
          }

          const payload = {
              display_name: myProfileFormData.display_name.trim(),
              phone: myProfileFormData.phone.trim(),
              department: myProfileFormData.department.trim(),
              github_url: myProfileFormData.github_url.trim(),
              linkedin_url: myProfileFormData.linkedin_url.trim(),
              line_id: myProfileFormData.line_id.trim(),
              password: myProfileFormData.password || ''
          };
          if (myProfileFormData.password && myProfileFormData.current_password) {
              payload.current_password = myProfileFormData.current_password;
          }
          if (newAvatarPath !== undefined) {
              payload.avatar_path = newAvatarPath;
          }
          
          // 2) บันทึกข้อมูลโปรไฟล์ทั้งหมด
          const res = await fetch(`/api/users/${userId}`, {
              method: 'PUT',
              headers,
              body: JSON.stringify(payload)
          });
          const data = await res.json().catch(() => ({}));
          
          if (res.ok && data.success) {
              const finalAvatar = data.user?.avatar_path !== undefined ? data.user.avatar_path : newAvatarPath;
              const finalName = data.user?.display_name || payload.display_name;
              updateAuthProfile(finalName, finalAvatar);
              topbarAvatarError = false;
              previewImageError = false;
              revokeAvatarBlob();
              confirmDiscardProfile = false;
              showMyProfileModal = false;
              toast(payload.password ? 'บันทึกข้อมูลส่วนตัวและเปลี่ยนรหัสผ่านเรียบร้อยแล้ว' : 'บันทึกข้อมูลส่วนตัวเรียบร้อยแล้ว', 'success');
          } else {
              toast(data.error || 'ไม่สามารถบันทึกข้อมูลโปรไฟล์ได้ กรุณาลองใหม่อีกครั้ง', 'error');
          }
      } catch (e) {
          toast('ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้ กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต', 'error');
      } finally {
          isSavingMyProfile = false;
      }
  }
  
  function doLogout() {
      showProfileMenu = false;
      logout();
  }

  function formatHistoryDate(dateString) {
    if (!dateString) return "";
    // If the database returns UTC time without a timezone marker, append 'Z'
    // so JS parses it as UTC and correctly converts it to local time.
    let parsedString = dateString;
    if (!parsedString.endsWith('Z') && !parsedString.includes('+')) {
      parsedString += 'Z';
    }
    const d = new Date(parsedString);
    return d.toLocaleString('th-TH', { 
      day: '2-digit', 
      month: '2-digit', 
      year: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit'
    });
  }

  $: projectGroups = (() => {
    if (!$selectedProjectStore) return [];
    const pId = $selectedProjectStore.id || $selectedProjectStore.project_id;
    
    const sessionGs = $qaSessionGroups.filter(g => g.project_id === pId);
    
    const histGs = $qaHistory.filter(h => h.project_id === pId).map(h => ({
      group_name: h.group_name || 'General',
      group_type: h.group_type || 'Project Plan',
      project_id: pId
    }));
    
    const all = [...sessionGs, ...histGs];
    const unique = [];
    const seen = new Set();
    for (let g of all) {
      if (!seen.has(g.group_name)) {
        seen.add(g.group_name);
        unique.push(g);
      }
    }
    return unique;
  })();

  $: activeProjectGroups = (() => {
    if (!$selectedProjectStore) return [];
    const pId = String($selectedProjectStore.id || $selectedProjectStore.project_id || '');
    const pCode = String($selectedProjectStore.project_code || '').trim().toLowerCase();
    return $allGroups.filter(g => {
      const gPid = String(g.project_id || '');
      const gCode = String(g.project_code || '').trim().toLowerCase();
      return !gPid || !pId || gPid === pId || (pCode && gCode && gCode === pCode);
    }).sort((a, b) => {
      const tA = new Date(a.latest_date || 0).getTime();
      const tB = new Date(b.latest_date || 0).getTime();
      return tB - tA;
    });
  })();

  $: filteredQAHistory = (() => {
    const history = $qaHistory;
    const project = $selectedProjectStore;
    const context = $activeSidebarGroup;
    
    if (!project) return [];
    const targetProject = String(project.id || project.project_id || '');
    const targetCode = String(project.project_code || '').trim().toLowerCase();
    
    return (history || []).filter(h => {
      const hPid = String(h.project_id || '');
      const hCode = String(h.project_code || '').trim().toLowerCase();
      
      const matchProj = !hPid || !targetProject || hPid === targetProject || (targetCode && hCode && hCode === targetCode);
      if (!matchProj) return false;
      
      if (context && context.group_name) {
        let cleanHGroup = String(h.group_name || 'General').trim();
        while (/^\[.*?\]\s*/.test(cleanHGroup)) {
          cleanHGroup = cleanHGroup.replace(/^\[.*?\]\s*/, '').trim();
        }
        cleanHGroup = cleanHGroup.toLowerCase();

        let cleanCtxGroup = String(context.group_name || 'General').trim();
        while (/^\[.*?\]\s*/.test(cleanCtxGroup)) {
          cleanCtxGroup = cleanCtxGroup.replace(/^\[.*?\]\s*/, '').trim();
        }
        cleanCtxGroup = cleanCtxGroup.toLowerCase();

        return cleanHGroup === cleanCtxGroup || cleanHGroup.includes(cleanCtxGroup) || cleanCtxGroup.includes(cleanHGroup);
      }
      return true; // Show all project history if no group context selected
    }).sort((a, b) => {
      if (a.is_processing && !b.is_processing) return -1;
      if (!a.is_processing && b.is_processing) return 1;
      const tA = new Date(a.date || a.created_at || 0).getTime();
      const tB = new Date(b.date || b.created_at || 0).getTime();
      return tB - tA;
    });
  })();

  $: displayedQAHistory = (() => {
    const q = String(sidebarHistorySearch || '').trim().toLowerCase();
    if (!q) return filteredQAHistory;
    return filteredQAHistory.filter(h => {
      const fn = String(h.filename || '').toLowerCase();
      const gn = formatCleanGroupName(h.group_name).toLowerCase();
      return fn.includes(q) || gn.includes(q);
    });
  })();
</script>

<svelte:window on:keydown={handleGlobalKeydown} />

<div class="app-wrapper">
  <!-- ── Animated Spectrum Background ── -->
  <div class="spectrum-bg"></div>
  <div class="spectrum-bg layer-2"></div>

  <div class="app-container">

{#if $showLogin}
    <Login />
  {:else}
    {#if isMobileSidebarOpen}
      <div
        class="sidebar-mobile-backdrop"
        aria-hidden="true"
        on:click={() => (isMobileSidebarOpen = false)}
      ></div>
    {/if}

    <!-- ── Sidebar ── -->
    <aside
      class="sidebar"
      class:collapsed={isSidebarCollapsed}
      class:mobile-open={isMobileSidebarOpen}
    >
      <div class="sidebar-logo">
        <div class="logo-brand-group">
          <div class="logo-icon">
            <img src="/spectra-logo.png" alt="Spectra QA Logo" />
          </div>
          {#if !isSidebarCollapsed}
            <div class="logo-text-wrap">
              <div class="logo-title">Spectra QA</div>
              <div class="logo-sub">Intelligent Document Analysis</div>
            </div>
          {/if}
        </div>
        <button
          type="button"
          class="btn-sidebar-collapse"
          aria-label={isSidebarCollapsed ? "ขยายแถบเมนูด้านข้าง" : "ย่อแถบเมนูด้านข้าง"}
          title={isSidebarCollapsed ? "ขยายแถบเมนู (Expand)" : "ย่อแถบเมนู (Collapse)"}
          on:click={() => {
            if (isMobileSidebarOpen) {
              isMobileSidebarOpen = false;
            } else {
              isSidebarCollapsed = !isSidebarCollapsed;
            }
          }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            {#if isSidebarCollapsed}
              <polyline points="9 18 15 12 9 6"></polyline>
            {:else}
              <polyline points="15 18 9 12 15 6"></polyline>
            {/if}
          </svg>
        </button>
      </div>

      <nav class="sidebar-nav" aria-label="Primary Navigation">
        <div class="sidebar-menu-zone">
          {#if $authRole === 'admin'}
            <button
              type="button"
              class="nav-group-header"
              on:click={() => toggleNavSection('admin_ocr')}
              aria-expanded={navSectionOpen.admin_ocr}
            >
              <span class="nav-group-label">Document &amp; OCR</span>
              {#if !isSidebarCollapsed}
                <svg class="nav-group-chevron" class:collapsed={!navSectionOpen.admin_ocr} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              {/if}
            </button>
            {#if navSectionOpen.admin_ocr || isSidebarCollapsed}
              {#if isMenuAllowed('ocr')}
                <button
                  class="nav-item"
                  title="Scan OCR"
                  class:active={activeView === "ocr" && !scanResult}
                  on:click={() => { activeView = "ocr"; scanResult = null; isMobileSidebarOpen = false; }}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"/></svg>
                  <span class="nav-item-label">Scan OCR</span>
                </button>
              {/if}
            {/if}

            <button
              type="button"
              class="nav-group-header"
              on:click={() => toggleNavSection('admin_platform')}
              aria-expanded={navSectionOpen.admin_platform}
            >
              <span class="nav-group-label">Platform &amp; Knowledge</span>
              {#if !isSidebarCollapsed}
                <svg class="nav-group-chevron" class:collapsed={!navSectionOpen.admin_platform} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              {/if}
            </button>
            {#if navSectionOpen.admin_platform || isSidebarCollapsed}
              {#if isMenuAllowed('project_management')}
                <button class="nav-item" title="Project Management" class:active={activeView === "project_management"} on:click={() => { activeView = "project_management"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>
                  <span class="nav-item-label">Project Management</span>
                </button>
              {/if}
              {#if isMenuAllowed('kb')}
                <button class="nav-item" title="Knowledge Base" class:active={activeView === "kb"} on:click={() => { activeView = "kb"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"></path></svg>
                  <span class="nav-item-label">Knowledge Base</span>
                </button>
              {/if}
              {#if isMenuAllowed('skills')}
                <button class="nav-item" title="AI Skills" class:active={activeView === "skills"} on:click={() => { activeView = "skills"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"></path></svg>
                  <span class="nav-item-label">AI Skills</span>
                </button>
              {/if}
              {#if isMenuAllowed('qa_member')}
                <button class="nav-item" title="QA Member" class:active={activeView === "qa_member"} on:click={() => { activeView = "qa_member"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                  <span class="nav-item-label">QA Member</span>
                </button>
              {/if}
              {#if isMenuAllowed('exit_criteria')}
                <button class="nav-item" title="Exit Criteria" class:active={activeView === "exit_criteria"} on:click={() => { activeView = "exit_criteria"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
                  <span class="nav-item-label">Exit Criteria</span>
                </button>
              {/if}
            {/if}

            <button
              type="button"
              class="nav-group-header"
              on:click={() => toggleNavSection('admin_api')}
              aria-expanded={navSectionOpen.admin_api}
            >
              <span class="nav-group-label">API &amp; Telemetry</span>
              {#if !isSidebarCollapsed}
                <svg class="nav-group-chevron" class:collapsed={!navSectionOpen.admin_api} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              {/if}
            </button>
            {#if navSectionOpen.admin_api || isSidebarCollapsed}
              {#if isMenuAllowed('api_collection')}
                <button class="nav-item" title="API Collections" class:active={activeView === "api_collection"} on:click={() => { activeView = "api_collection"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                  <span class="nav-item-label">API Collections</span>
                </button>
              {/if}
              {#if isMenuAllowed('api_usage')}
                <button class="nav-item" title="Token Usage" class:active={activeView === "api_usage"} on:click={() => { activeView = "api_usage"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M3 3v18h18"/><path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3"/></svg>
                  <span class="nav-item-label">Token Usage</span>
                </button>
              {/if}
            {/if}

          {:else if $authRole === 'user'}
            <button
              type="button"
              class="nav-group-header"
              on:click={() => toggleNavSection('discovery')}
              aria-expanded={navSectionOpen.discovery}
            >
              <span class="nav-group-label">Discovery &amp; Docs</span>
              {#if !isSidebarCollapsed}
                <svg class="nav-group-chevron" class:collapsed={!navSectionOpen.discovery} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              {/if}
            </button>
            {#if navSectionOpen.discovery || isSidebarCollapsed}
              {#if isMenuAllowed('qa_consult')}
                <button class="nav-item" title="QA Consult" class:active={activeView === "qa_consult"} on:click={() => { activeView = "qa_consult"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                  <span class="nav-item-label">QA Consult</span>
                </button>
              {/if}
              {#if isMenuAllowed('qa_doc_creation')}
                <button class="nav-item" title="QA Document Creation" class:active={activeView === "qa_doc_creation"} on:click={() => { activeView = "qa_doc_creation"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                  <span class="nav-item-label">QA Document Creation</span>
                </button>
              {/if}
              {#if isMenuAllowed('qa_analysis_diagram')}
                <button class="nav-item" title="QA Analysis Diagram" class:active={activeView === "qa_analysis_diagram"} on:click={() => { activeView = "qa_analysis_diagram"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polygon points="12 2 2 7 12 12 22 7 12 2"></polygon><polyline points="2 17 12 22 22 17"></polyline><polyline points="2 12 12 17 22 12"></polyline></svg>
                  <span class="nav-item-label">QA Analysis Diagram</span>
                </button>
              {/if}
            {/if}

            <button
              type="button"
              class="nav-group-header"
              on:click={() => toggleNavSection('testing')}
              aria-expanded={navSectionOpen.testing}
            >
              <span class="nav-group-label">Quality &amp; Testing</span>
              {#if !isSidebarCollapsed}
                <svg class="nav-group-chevron" class:collapsed={!navSectionOpen.testing} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              {/if}
            </button>
            {#if navSectionOpen.testing || isSidebarCollapsed}
              {#if isMenuAllowed('qa_board')}
                <button class="nav-item" title="QA Board Card" class:active={activeView === "qa_board"} on:click={() => { activeView = "qa_board"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line></svg>
                  <span class="nav-item-label">QA Board Card</span>
                </button>
              {/if}
              {#if isMenuAllowed('qa_automate')}
                <button class="nav-item" title="QA Test Automation" class:active={activeView === "qa_automate"} on:click={() => { activeView = "qa_automate"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 2v20m-7-7h14m-14-6h14"></path><path d="M2 12h20"></path></svg>
                  <span class="nav-item-label">QA Test Automation</span>
                </button>
              {/if}
              {#if isMenuAllowed('qa_performance')}
                <button class="nav-item" title="QA Performance" class:active={activeView === "qa_performance"} on:click={() => { activeView = "qa_performance"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path></svg>
                  <span class="nav-item-label">QA Performance</span>
                </button>
              {/if}
              {#if isMenuAllowed('qa_security')}
                <button class="nav-item" title="QA Security" class:active={activeView === "qa_security"} on:click={() => { activeView = "qa_security"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                  <span class="nav-item-label">QA Security</span>
                </button>
              {/if}
              {#if isMenuAllowed('qa_research')}
                <button class="nav-item" title="QA Research" class:active={activeView === "qa_research"} on:click={() => { activeView = "qa_research"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><path d="M11 7v4l3 3"></path></svg>
                  <span class="nav-item-label">QA Research</span>
                </button>
              {/if}
            {/if}

            <button
              type="button"
              class="nav-group-header"
              on:click={() => toggleNavSection('agents')}
              aria-expanded={navSectionOpen.agents}
            >
              <span class="nav-group-label">AI Agents</span>
              {#if !isSidebarCollapsed}
                <svg class="nav-group-chevron" class:collapsed={!navSectionOpen.agents} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="11" height="11">
                  <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
              {/if}
            </button>
            {#if navSectionOpen.agents || isSidebarCollapsed}
              {#if isMenuAllowed('master_agent')}
                <button class="nav-item nav-agent-master" title="Master Agent" class:active={activeView === "master_agent"} on:click={() => { activeView = "master_agent"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M12 2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h6z"></path><path d="M22 10v6a2 2 0 0 1-2 2h-6l-4 4v-4H6a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                  <span class="nav-item-label">Master Agent</span>
                </button>
              {/if}
              {#if isMenuAllowed('workflow_builder')}
                <button class="nav-item nav-agent-workflow" title="AI Workflow Builder" class:active={activeView === "workflow_builder"} on:click={() => { activeView = "workflow_builder"; isMobileSidebarOpen = false; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line></svg>
                  <span class="nav-item-label">AI Workflow Builder</span>
                </button>
              {/if}
            {/if}
          {/if}
        </div>

        <!-- ── Contextual Workspace Zone (Stretches dynamically to fill remaining height) ── -->
        {#if !isSidebarCollapsed}
          {#if $authRole === 'admin' && activeView === 'ocr'}
            <div class="sidebar-context-zone">
              <div class="history-section" class:expanded={isOcrHistoryExpanded}>
                <button
                  type="button"
                  class="history-title-toggle"
                  aria-expanded={isOcrHistoryExpanded}
                  on:click={() => (isOcrHistoryExpanded = !isOcrHistoryExpanded)}
                >
                  <div class="history-title-left">
                    <span class="history-title-text">ประวัติการสแกนล่าสุด</span>
                    {#if $ocrHistory.length > 0}
                      <span class="history-count-badge">{$ocrHistory.length}</span>
                    {/if}
                  </div>
                  <svg class="chevron-icon" class:collapsed={!isOcrHistoryExpanded} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="13" height="13">
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </button>

                {#if isOcrHistoryExpanded}
                  {#if $ocrHistory.length > 0}
                    <div class="history-list qa-flex-scroll">
                      {#each $ocrHistory as item}
                        <div class="sidebar-item-row">
                          <button type="button" class="history-item" class:active={scanResult && scanResult.id === item.id} on:click={() => { selectOCRHistory(item); isMobileSidebarOpen = false; }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
                            <div class="history-details">
                              <span class="h-filename" title={item.filename}>{item.filename || 'Unknown Document'}</span>
                              <span class="h-date">{formatHistoryDate(item.date)}</span>
                            </div>
                          </button>
                          <button
                            type="button"
                            class="btn-sidebar-delete"
                            title="ลบประวัติ"
                            aria-label={`ลบประวัติ ${item.filename}`}
                            on:click|stopPropagation={() => deleteOCRHistory(item.id)}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M18 6L6 18M6 6l12 12"></path></svg>
                          </button>
                        </div>
                      {/each}
                    </div>
                  {:else}
                    <div class="sidebar-empty-box">ยังไม่มีประวัติการสแกน</div>
                  {/if}
                {/if}
              </div>
            </div>
          {:else if $authRole === 'user' && (activeView === 'qa_consult' || activeView === 'qa_performance')}
            <div class="sidebar-context-zone">
              <!-- Active Project Quick Switcher -->
              {#if sidebarProjects.length > 0}
                <div class="sidebar-project-bar">
                  <div class="sidebar-proj-label-row">
                    <span class="sidebar-proj-dot"></span>
                    <span class="sidebar-proj-caption">โครงการ (Project)</span>
                  </div>
                  <select
                    class="sidebar-proj-select"
                    aria-label="เลือกโครงการ"
                    value={$selectedProjectStore ? String($selectedProjectStore.id || $selectedProjectStore.project_id) : ""}
                    on:change={handleSidebarProjectSelect}
                  >
                    <option value="">— เลือกโครงการ —</option>
                    {#each sidebarProjects as p}
                      <option value={String(p.id || p.project_id)}>
                        [{p.project_code}] {p.name || p.project_name}
                      </option>
                    {/each}
                  </select>
                </div>
              {/if}

              {#if activeView === 'qa_performance' && $selectedProjectStore}
                {@const projPerfList = $perfHistory.filter(h => h.project_id === ($selectedProjectStore.id || $selectedProjectStore.project_id))}
                {#if projPerfList.length > 0}
                  <div class="history-section" class:expanded={isPerfHistoryExpanded}>
                    <button
                      type="button"
                      class="history-title-toggle"
                      aria-expanded={isPerfHistoryExpanded}
                      on:click={() => (isPerfHistoryExpanded = !isPerfHistoryExpanded)}
                    >
                      <div class="history-title-left">
                        <span class="history-title-text">ประวัติ Performance</span>
                        <span class="history-count-badge">{projPerfList.length}</span>
                      </div>
                      <svg class="chevron-icon" class:collapsed={!isPerfHistoryExpanded} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="13" height="13">
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </button>
                    {#if isPerfHistoryExpanded}
                      <div class="history-list qa-flex-scroll">
                        {#each projPerfList as item}
                          <button class="history-item" on:click={() => { activeView = "qa_performance"; selectedPerfHistory.set(item); isMobileSidebarOpen = false; }}>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path></svg>
                            <div class="history-details">
                              <span class="h-filename" style="color: #facc15;">{item.name}</span>
                              <div class="h-meta-row">
                                <span class="h-group-pill">{item.scriptFileName || 'k6_test.js'}</span>
                                {#if item.date}
                                  <span class="h-date">{formatHistoryDate(item.date)}</span>
                                {/if}
                              </div>
                            </div>
                          </button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}
              {:else if activeView === 'qa_consult' && $selectedProjectStore}
                <!-- Groups filtered by selected project -->
                {#if activeProjectGroups.length > 0}
                  <div class="history-section" class:expanded={isQaGroupsExpanded}>
                    <button
                      type="button"
                      class="history-title-toggle"
                      aria-expanded={isQaGroupsExpanded}
                      on:click={() => (isQaGroupsExpanded = !isQaGroupsExpanded)}
                    >
                      <div class="history-title-left">
                        <span class="history-title-text">กลุ่มการตรวจสอบ (Groups)</span>
                        <span class="history-count-badge">{activeProjectGroups.length}</span>
                      </div>
                      <svg class="chevron-icon" class:collapsed={!isQaGroupsExpanded} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="13" height="13">
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </button>

                    {#if isQaGroupsExpanded}
                      <div class="history-list qa-flex-scroll">
                        {#each activeProjectGroups as group}
                          {@const isGroupActive = $activeSidebarGroup && formatCleanGroupName($activeSidebarGroup.group_name).toLowerCase() === formatCleanGroupName(group.group_name).toLowerCase()}
                          <div class="sidebar-item-row">
                            <button
                              type="button"
                              class="history-item group-item"
                              class:active={isGroupActive}
                              on:click={() => { handleGroupClick(group); isMobileSidebarOpen = false; }}
                            >
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                              </svg>
                              <div class="history-details">
                                <div class="h-title-row">
                                  <span class="h-type-badge">{formatGroupType(group)}</span>
                                  <span class="h-filename" title={formatCleanGroupName(group.group_name)}>{formatCleanGroupName(group.group_name)}</span>
                                </div>
                                <div class="h-meta-row">
                                  {#if group.scan_count > 0}
                                    <span class="h-date">{group.scan_count} ไฟล์ที่ตรวจแล้ว</span>
                                  {:else}
                                    <span class="h-date" style="color: #f59e0b;">ยังไม่มีไฟล์</span>
                                  {/if}
                                </div>
                              </div>
                            </button>
                            <button 
                              type="button"
                              class="btn-sidebar-delete" 
                              title="ลบกลุ่มนี้" 
                              aria-label={`ลบกลุ่ม ${formatCleanGroupName(group.group_name)}`}
                              on:click|stopPropagation={() => promptDeleteGroup(group)}
                            >
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                              </svg>
                            </button>
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}

                <!-- History filtered by selected group OR all project history -->
                {#if filteredQAHistory.length > 0}
                  <div class="history-section" class:expanded={isQaHistoryExpanded}>
                    <div class="history-header-bar">
                      <button
                        type="button"
                        class="history-title-toggle flex-1"
                        aria-expanded={isQaHistoryExpanded}
                        on:click={() => (isQaHistoryExpanded = !isQaHistoryExpanded)}
                      >
                        <div class="history-title-left" style="min-width: 0;">
                          <span class="history-title-text truncate">
                            {#if $activeSidebarGroup}
                              ประวัติ ({formatCleanGroupName($activeSidebarGroup.group_name)})
                            {:else}
                              ประวัติล่าสุด
                            {/if}
                          </span>
                          <span class="history-count-badge">{filteredQAHistory.length}</span>
                        </div>
                        <svg class="chevron-icon" class:collapsed={!isQaHistoryExpanded} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="13" height="13">
                          <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                      </button>
                      {#if $activeSidebarGroup}
                        <button 
                          type="button"
                          class="btn-reset-group-pill" 
                          title="คลิกเพื่อแสดงประวัติทั้งหมดในโครงการ"
                          on:click={() => activeSidebarGroup.set(null)}
                        >
                          ดูทั้งหมด
                        </button>
                      {/if}
                    </div>

                    {#if isQaHistoryExpanded}
                      {#if filteredQAHistory.length > 4}
                        <div class="sidebar-filter-box">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                          <input
                            type="text"
                            bind:value={sidebarHistorySearch}
                            placeholder="กรองชื่อไฟล์ประวัติ..."
                            aria-label="กรองชื่อไฟล์ประวัติ"
                          />
                          {#if sidebarHistorySearch}
                            <button type="button" class="btn-clear-filter" aria-label="ล้างคำค้นหา" on:click={() => (sidebarHistorySearch = "")}>✕</button>
                          {/if}
                        </div>
                      {/if}

                      <div class="history-list qa-flex-scroll">
                        {#each displayedQAHistory as item}
                          {@const exitStatus = getHistoryExitStatus(item)}
                          <div class="sidebar-item-row">
                            <button
                              type="button"
                              class="history-item"
                              class:active={activeHistoryId === item.id}
                              class:is-processing={item.is_processing}
                              on:click={() => { activeView = "qa_consult"; activeHistoryId = item.id; selectedHistory.set(item); isMobileSidebarOpen = false; }}
                            >
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg>
                              <div class="history-details">
                                <div class="h-title-row">
                                  <span class="h-status-dot {exitStatus}" title={`Exit Status: ${exitStatus.toUpperCase()}`}></span>
                                  <span class="h-filename" title={item.filename}>{item.filename}</span>
                                </div>
                                {#if item.is_processing}
                                  <span class="h-status" style="color: #60a5fa; font-size: 11px; margin-top: 2px; display: flex; align-items: center; gap: 4px;">
                                    <svg class="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="10" height="10" style="animation: spin 2s linear infinite;">
                                      <line x1="12" y1="2" x2="12" y2="6"></line>
                                      <line x1="12" y1="18" x2="12" y2="22"></line>
                                      <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                                      <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                                      <line x1="2" y1="12" x2="6" y2="12"></line>
                                      <line x1="18" y1="12" x2="22" y2="12"></line>
                                      <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                                      <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
                                    </svg>
                                    กำลังประมวลผล...
                                  </span>
                                {:else}
                                  <div class="h-meta-row">
                                    <span class="h-group-pill">{formatCleanGroupName(item.group_name)}</span>
                                    {#if item.date}
                                      <span class="h-date">{formatHistoryDate(item.date)}</span>
                                    {/if}
                                  </div>
                                {/if}
                              </div>
                            </button>
                            {#if !item.is_processing}
                              <button 
                                type="button"
                                class="btn-sidebar-delete" 
                                title="ลบประวัติการตรวจนี้" 
                                aria-label={`ลบประวัติ ${item.filename}`}
                                on:click|stopPropagation={() => promptDeleteHistory(item)}
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
                                  <polyline points="3 6 5 6 21 6"></polyline>
                                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                </svg>
                              </button>
                            {/if}
                          </div>
                        {:else}
                          <div class="sidebar-empty-box">ไม่พบไฟล์ที่ตรงกับ "{sidebarHistorySearch}"</div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {:else if $activeSidebarGroup}
                  <div class="history-section">
                    <div class="history-header-bar">
                      <span class="history-title-text truncate">ประวัติ ({formatCleanGroupName($activeSidebarGroup.group_name)})</span>
                      <button 
                        type="button"
                        class="btn-reset-group-pill" 
                        on:click={() => activeSidebarGroup.set(null)}
                      >
                        ดูทั้งหมด
                      </button>
                    </div>
                    <div class="sidebar-empty-box">ยังไม่มีประวัติการตรวจในกลุ่มนี้</div>
                  </div>
                {/if}
              {/if}
            </div>
          {/if}
        {/if}
      </nav>

      <div class="sidebar-footer">
        <button class="btn-tutorial" on:click={() => (showTutorial = true)} title="เปิดคู่มือการใช้งาน (Tutorial Guide)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <circle cx="12" cy="12" r="10"/>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
            <line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
          {#if !isSidebarCollapsed}
            <span class="footer-btn-text">Tutorial</span>
            <span class="tutorial-badge">Guide</span>
          {/if}
        </button>

        <button class="btn-logout" on:click={logout} title="ออกจากระบบ (Logout)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
          {#if !isSidebarCollapsed}
            <span class="footer-btn-text">Logout</span>
          {/if}
        </button>
      </div>
    </aside>

    <!-- ── Main Workspace ── -->
    <main class="workspace">
      <!-- Topbar -->
      <header class="topbar">
        <div class="topbar-left">
          <button
            type="button"
            class="btn-mobile-menu"
            aria-label="เปิดเมนูด้านข้าง"
            on:click={() => (isMobileSidebarOpen = !isMobileSidebarOpen)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          <div class="breadcrumb">WORKSPACE / <span class="bc-active">{VIEW_LABELS[activeView] || activeView.toUpperCase()}</span></div>
          {#if $selectedProjectStore}
            <span class="active-project-pill" title={$selectedProjectStore.name || $selectedProjectStore.project_code}>
              <span class="proj-dot"></span>
              {$selectedProjectStore.project_code || $selectedProjectStore.name}
            </span>
          {/if}
        </div>
        <div class="topbar-right">
          {#if $authRole === 'admin'}
            <div class="search-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <input bind:this={globalSearchInputEl} type="text" bind:value={$globalSearchQuery} on:keydown={onGlobalSearchKey} placeholder="ค้นหา (Ctrl+K)..." aria-label="ค้นหา Knowledge Base" />
            </div>
          {/if}
          <div style="position: relative;">
            <button
              bind:this={notiTriggerBtn}
              type="button"
              class="icon-btn"
              class:active={showNotifications}
              on:click={() => showNotifications = !showNotifications}
              title="การแจ้งเตือน"
              aria-label={$unreadCount > 0 ? `การแจ้งเตือน (${$unreadCount} รายการใหม่)` : 'การแจ้งเตือน'}
              aria-expanded={showNotifications}
              aria-haspopup="dialog"
              aria-controls="noti-panel"
            >
              <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 01-3.46 0"></path></svg>
              {#if $unreadCount > 0}
                <span class="noti-badge-count" aria-hidden="true">{$unreadCount > 99 ? '99+' : $unreadCount}</span>
              {/if}
            </button>

            {#if showNotifications}
              <NotificationDropdown 
                on:close={() => {
                  showNotifications = false;
                  notiTriggerBtn?.focus();
                }}
                on:navigate={(e) => {
                  activeView = e.detail.view;
                  showNotifications = false;
                }}
              />
            {/if}
          </div>
          <div class="status-badge" class:error={!systemReady}>
            <span class="dot"></span> {systemReady ? 'System Ready' : 'System Unavailable'}
          </div>
          <div class="user-profile-wrap" style="position: relative;">
            <button
              type="button"
              class="user-profile-container"
              aria-haspopup="menu"
              aria-expanded={showProfileMenu}
              on:click={() => showProfileMenu = !showProfileMenu}
            >
              <div class="user-info">
                <span class="user-name">{$authDisplayName || $authUser}</span>
                <span class="user-role">{$authRole === 'admin' ? 'System Admin' : 'Standard User'}</span>
              </div>
              <div class="avatar" title="{$authDisplayName || $authUser} ({$authRole})">
                {#if $authAvatar && !topbarAvatarError}
                  <img src={`${$authAvatar}`} alt="Profile" on:error={() => topbarAvatarError = true} />
                {:else}
                  {$authDisplayName ? $authDisplayName.charAt(0).toUpperCase() : ($authUser ? $authUser.charAt(0).toUpperCase() : 'A')}
                {/if}
              </div>
            </button>
            
            {#if showProfileMenu}
              <div class="dropdown-overlay" aria-hidden="true" on:click|stopPropagation={() => showProfileMenu = false}></div>
              <div class="profile-dropdown" role="menu">
                <button class="dropdown-item" on:click|stopPropagation={openMyProfileModal}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                  Profile
                </button>
                <button class="dropdown-item" on:click|stopPropagation={() => { showProfileMenu = false; showNotificationConfigModal = true; }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
                  CI/CD Webhooks Config
                </button>
                <button class="dropdown-item logout-btn" on:click|stopPropagation={doLogout}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                  Logout
                </button>
              </div>
            {/if}
          </div>
        </div>
      </header>

      <!-- Content Area -->
      <div class="content-scroll" id="main-content" class:no-padding={['kb', 'ocr', 'qa_consult', 'qa_doc_creation', 'qa_member', 'qa_analysis_diagram', 'qa_performance', 'qa_research', 'qa_security', 'qa_automate', 'qa_board', 'master_agent', 'workflow_builder'].includes(activeView)}>
        {#key activeView}
          <div class="view-wrapper" in:fade="{{ duration: 300, delay: 150 }}">
            {#if activeView === "ocr" && $authRole === "admin"}
              <div style="display: {(!isProcessing && !scanResult) ? 'flex' : 'none'}; flex-direction: column; width: 100%; height: 100%;">
                <div class="upload-container" style="flex: 1; padding: 0;">
                  <UploadPanel on:result={handleResult} on:processing={handleProcessing} />
                </div>
              </div>
              {#if isProcessing || scanResult}
                <ResultsPanel result={scanResult} {isProcessing} {progress} on:close={() => {scanResult = null; isProcessing = false;}} />
              {/if}
            {:else if activeView === 'project_management'}
              <ProjectManagement />
            {:else if activeView === "kb" && $authRole === "admin"}
              <KnowledgeBase mode="knowledge_base" />
            {:else if activeView === "skills" && $authRole === "admin"}
              <SkillManager />
            {:else if activeView === "qa_member" && $authRole === "admin"}
              <QAMember />
            {:else if activeView === "exit_criteria" && $authRole === "admin"}
              <ExitCriteriaManager />
            {:else if activeView === "api_collection" && $authRole === "admin"}
              <ApiCollectionAdmin />
            {:else if activeView === "api_usage" && $authRole === "admin"}
              <ApiUsageDashboard />
            {:else if activeView === "qa_consult"}
              <QAConsult on:navigate={(e) => { if (e.detail?.view) activeView = e.detail.view; }} />
            {:else if activeView === "qa_performance"}
              <QAPerformance />
            {:else if activeView === "qa_research"}
              <QAResearch on:navigate={(e) => { if (e.detail?.view) activeView = e.detail.view; }} />
            {:else if activeView === "qa_security"}
              <QASecurity />
            {:else if activeView === "qa_automate"}
              <QATestAutomation on:navigate={(e) => { if (e.detail?.view) activeView = e.detail.view; }} />
            {:else if activeView === "qa_doc_creation"}
              <QADocumentCreation on:navigate={(e) => { if (e.detail?.view) activeView = e.detail.view; }} />
            {:else if activeView === "qa_analysis_diagram"}
              <QAAnalysisDiagram />
            {:else if activeView === "qa_board"}
              <QABoardCard />
            {:else if activeView === "master_agent"}
              <MasterAgentUI on:navigate={(e) => { if (e.detail?.view) activeView = e.detail.view; }} />
            {:else if activeView === "workflow_builder"}
              <WorkflowBuilder />
            {/if}
          </div>
        {/key}
      </div>

      <!-- ── Footer ── -->
      <footer class="app-footer">
        <div class="footer-left">
          &copy; 2026 Spectra QA v1.0.4. Powered by Prism AI.
        </div>
        <div class="footer-links">
          <a href="#" on:click|preventDefault={() => legalModalType = 'privacy'}>Privacy Policy</a>
          <a href="#" on:click|preventDefault={() => legalModalType = 'terms'}>Terms of Service</a>
          <a href="#" on:click|preventDefault={() => legalModalType = 'security'}>Security Architecture</a>
        </div>
      </footer>
    </main>
  {/if}
  </div>
</div>

<!-- Global Toast Notifications -->
<Toast />

<!-- Tutorial Overlay -->
{#if showTutorial}
  <TutorialOverlay userRole={$authRole} on:close={() => (showTutorial = false)} />
{/if}

<!-- Legal Modal -->
{#if legalModalType}
  <LegalModal type={legalModalType} on:close={() => legalModalType = null} />
{/if}

<!-- Notification Config Modal -->
<NotificationConfigModal bind:showModal={showNotificationConfigModal} />

{#if showMyProfileModal}
<div class="modal-backdrop" transition:fade={{ duration: 180 }} on:click={requestCloseProfileModal}>
    <div
      class="modal-content profile-modal-card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="profile-modal-heading"
      in:scale={{ start: 0.94, duration: 200 }}
      on:click|stopPropagation
    >
        <div class="profile-modal-top">
            <div class="profile-modal-title-wrap">
                <h2 id="profile-modal-heading" class="modal-title">แก้ไขข้อมูลส่วนตัว & โปรไฟล์</h2>
                <p class="modal-subtitle">จัดการข้อมูลบัญชี รูปโปรไฟล์ ช่องทางติดต่อ และความปลอดภัย</p>
            </div>
            <button type="button" class="profile-close-btn" on:click={requestCloseProfileModal} title="ปิด (Esc)" aria-label="ปิดหน้าต่างโปรไฟล์">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>

        {#if confirmDiscardProfile}
            <div class="profile-discard-banner" transition:slide={{ duration: 140 }}>
                <span>มีการแก้ไขที่ยังไม่ได้บันทึก ต้องการทิ้งการเปลี่ยนแปลงและปิดหน้าต่างหรือไม่?</span>
                <div class="discard-banner-actions">
                    <button type="button" class="btn-banner-stay" on:click={() => (confirmDiscardProfile = false)}>แก้ไขต่อ</button>
                    <button type="button" class="btn-banner-discard" on:click={requestCloseProfileModal}>ทิ้งการแก้ไข</button>
                </div>
            </div>
        {/if}

        {#if isLoadingMyProfile}
            <div class="profile-state-box">
                <div class="profile-spinner"></div>
                <span>กำลังโหลดข้อมูลโปรไฟล์ล่าสุด...</span>
            </div>
        {:else if profileLoadError}
            <div class="profile-state-box error">
                <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                <p>{profileLoadError}</p>
                <button type="button" class="btn-avatar-action upload" on:click={() => fetchMyProfileDetail(myProfileFormData.display_name, myProfileAvatarPreview || '')}>
                    ลองโหลดข้อมูลใหม่
                </button>
            </div>
        {:else}
            <form on:submit|preventDefault={saveMyProfile} class="profile-form-root">
                <!-- Compact Horizontal Identity & Avatar Header -->
                <div
                  class="profile-identity-bar"
                  class:drag-over={isDragOverAvatar}
                  on:dragover|preventDefault={() => (isDragOverAvatar = true)}
                  on:dragleave|preventDefault={() => (isDragOverAvatar = false)}
                  on:drop|preventDefault={handleAvatarDrop}
                >
                    <label
                      for="my_profile_avatar_input"
                      class="avatar-trigger-circle"
                      title="คลิกหรือลากวางไฟล์รูปภาพเพื่อเปลี่ยนรูปโปรไฟล์"
                    >
                        {#if myProfileAvatarPreview && !previewImageError}
                            <img src={myProfileAvatarPreview} alt="รูปโปรไฟล์ปัจจุบัน" on:error={() => (previewImageError = true)} />
                        {:else}
                            <span class="avatar-fallback-text">
                                {myProfileFormData.display_name ? myProfileFormData.display_name.charAt(0).toUpperCase() : ($authUser ? $authUser.charAt(0).toUpperCase() : 'U')}
                            </span>
                        {/if}
                        <span class="avatar-hover-overlay" aria-hidden="true">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" width="18" height="18"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>
                        </span>
                    </label>

                    <input
                      type="file"
                      id="my_profile_avatar_input"
                      accept="image/jpeg,image/png,image/webp"
                      class="sr-only-input"
                      on:change={(e) => {
                          const file = e.target.files?.[0];
                          if (file) validateAndSetAvatarFile(file);
                          e.target.value = '';
                      }}
                    />

                    <div class="identity-meta">
                        <div class="identity-name-row">
                            <strong class="identity-display">{myProfileFormData.display_name || $authDisplayName || $authUser || 'ผู้ใช้งาน'}</strong>
                            <span class="identity-role-pill">{$authRole === 'admin' ? 'Admin' : 'Member'}</span>
                        </div>
                        <span class="identity-username">@{$authUser || 'account'}</span>
                        <span class="drag-hint-text">รองรับ JPG, PNG, WEBP ไม่เกิน 5 MB (คลิกหรือลากวาง)</span>
                    </div>

                    <div class="avatar-controls">
                        <label for="my_profile_avatar_input" class="btn-avatar-action upload">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" width="14" height="14"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                            <span>เปลี่ยนรูป</span>
                        </label>

                        {#if avatarRemovalPending}
                            <button type="button" class="btn-avatar-action undo" on:click={undoRemoveMyAvatar}>
                                ยกเลิกการลบ
                            </button>
                        {:else if myProfileAvatarPreview}
                            <button type="button" class="btn-avatar-action remove" on:click={removeMyAvatar}>
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" width="14" height="14"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                                <span>ลบรูป</span>
                            </button>
                        {/if}
                    </div>
                </div>

                <!-- Accessible Form Tab Switcher -->
                <div class="profile-tabs-header" role="tablist" aria-label="หมวดหมู่การตั้งค่าโปรไฟล์">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activeProfileTab === 'general'}
                      class="ptab-btn"
                      class:active={activeProfileTab === 'general'}
                      on:click={() => (activeProfileTab = 'general')}
                    >
                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                        <span>ข้อมูลทั่วไป</span>
                        {#if generalTabDirty}<span class="tab-dirty-dot" title="มีการแก้ไข"></span>{/if}
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activeProfileTab === 'social'}
                      class="ptab-btn"
                      class:active={activeProfileTab === 'social'}
                      on:click={() => (activeProfileTab = 'social')}
                    >
                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                        <span>ช่องทางติดต่อ</span>
                        {#if socialTabDirty}<span class="tab-dirty-dot" title="มีการแก้ไข"></span>{/if}
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={activeProfileTab === 'security'}
                      class="ptab-btn"
                      class:active={activeProfileTab === 'security'}
                      on:click={() => (activeProfileTab = 'security')}
                    >
                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                        <span>รหัสผ่าน</span>
                        {#if securityTabDirty}<span class="tab-dirty-dot warn" title="เตรียมเปลี่ยนรหัสผ่าน"></span>{/if}
                    </button>
                </div>

                {#if profileValidationError}
                    <div class="profile-inline-error" role="alert">
                        {profileValidationError}
                    </div>
                {/if}

                <!-- Form Body -->
                <div class="profile-form-body">
                    {#if activeProfileTab === 'general'}
                        <div class="form-grid">
                            <div class="form-group">
                                <label for="my_display_name">ชื่อที่แสดงในระบบ (Display Name)</label>
                                <input type="text" id="my_display_name" bind:value={myProfileFormData.display_name} placeholder="เช่น เอกราช โอสถานุเคราะห์" required />
                            </div>

                            <div class="form-group">
                                <label for="my_department">แผนก / ตำแหน่งงาน (Department / Position)</label>
                                <input type="text" id="my_department" bind:value={myProfileFormData.department} placeholder="เช่น Senior QA Automation Lead" />
                            </div>

                            <div class="form-group">
                                <label for="my_phone">เบอร์โทรศัพท์ (Phone Number)</label>
                                <div class="input-with-icon">
                                    <span class="field-icon" aria-hidden="true">
                                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>
                                    </span>
                                    <input type="tel" id="my_phone" bind:value={myProfileFormData.phone} placeholder="081-234-5678" />
                                </div>
                            </div>
                        </div>

                    {:else if activeProfileTab === 'social'}
                        <div class="form-grid">
                            <div class="form-group">
                                <label for="my_github">ลิงก์โปรไฟล์ GitHub (GitHub Profile URL)</label>
                                <div class="input-with-icon">
                                    <span class="field-icon" aria-hidden="true">
                                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
                                    </span>
                                    <input type="url" id="my_github" bind:value={myProfileFormData.github_url} placeholder="https://github.com/username" />
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="my_linkedin">ลิงก์โปรไฟล์ LinkedIn (LinkedIn URL)</label>
                                <div class="input-with-icon">
                                    <span class="field-icon" aria-hidden="true">
                                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"></path><rect x="2" y="9" width="4" height="12"></rect><circle cx="4" cy="4" r="2"></circle></svg>
                                    </span>
                                    <input type="url" id="my_linkedin" bind:value={myProfileFormData.linkedin_url} placeholder="https://linkedin.com/in/username" />
                                </div>
                            </div>

                            <div class="form-group">
                                <label for="my_line_id">Line ID / Telegram</label>
                                <div class="input-with-icon">
                                    <span class="field-icon" aria-hidden="true">
                                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                                    </span>
                                    <input type="text" id="my_line_id" bind:value={myProfileFormData.line_id} placeholder="@line_id หรือ @telegram" />
                                </div>
                            </div>
                        </div>

                    {:else if activeProfileTab === 'security'}
                        <div class="security-grid">
                            {#if $authRole !== 'admin'}
                                <div class="form-group" style="grid-column: 1 / -1;">
                                    <label for="my_current_password">รหัสผ่านปัจจุบัน (Current Password)</label>
                                    <div class="input-with-icon">
                                        <span class="field-icon" aria-hidden="true">
                                            <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                                        </span>
                                        <input
                                          id="my_current_password"
                                          type={showMyCurrentPassword ? "text" : "password"}
                                          bind:value={myProfileFormData.current_password}
                                          maxlength="72"
                                          placeholder="ระบุรหัสผ่านปัจจุบันเมื่อต้องการเปลี่ยนรหัสผ่าน"
                                          autocomplete="current-password"
                                          class="password-input"
                                        />
                                        <button type="button" class="eye-btn" on:click={() => (showMyCurrentPassword = !showMyCurrentPassword)} title={showMyCurrentPassword ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"} aria-label={showMyCurrentPassword ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"}>
                                            {#if showMyCurrentPassword}
                                                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.75" fill="none"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                                            {:else}
                                                <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.75" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                                            {/if}
                                        </button>
                                    </div>
                                </div>
                            {/if}

                            <div class="form-group">
                                <label for="my_new_password">รหัสผ่านใหม่ (New Password)</label>
                                <div class="input-with-icon">
                                    <span class="field-icon" aria-hidden="true">
                                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"></path></svg>
                                    </span>
                                    <input
                                      id="my_new_password"
                                      type={showMyPassword ? "text" : "password"}
                                      bind:value={myProfileFormData.password}
                                      maxlength="72"
                                      placeholder="อย่างน้อย 8 ตัวอักษร"
                                      autocomplete="new-password"
                                      class="password-input"
                                    />
                                    <button type="button" class="eye-btn" on:click={() => (showMyPassword = !showMyPassword)} title={showMyPassword ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"} aria-label={showMyPassword ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"}>
                                        {#if showMyPassword}
                                            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.75" fill="none"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                                        {:else}
                                            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.75" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                                        {/if}
                                    </button>
                                </div>
                                {#if passwordTooShort}
                                    <span class="field-error-text">รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร</span>
                                {/if}
                            </div>

                            <div class="form-group">
                                <label for="my_confirm_password">ยืนยันรหัสผ่านใหม่ (Confirm Password)</label>
                                <div class="input-with-icon">
                                    <span class="field-icon" aria-hidden="true">
                                        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.75"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                    </span>
                                    <input
                                      id="my_confirm_password"
                                      type={showMyPasswordConfirm ? "text" : "password"}
                                      bind:value={myProfileFormData.password_confirm}
                                      maxlength="72"
                                      placeholder="พิมพ์รหัสผ่านใหม่อีกครั้งเพื่อยืนยัน"
                                      autocomplete="new-password"
                                      class="password-input"
                                    />
                                    <button type="button" class="eye-btn" on:click={() => (showMyPasswordConfirm = !showMyPasswordConfirm)} title={showMyPasswordConfirm ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"} aria-label={showMyPasswordConfirm ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน"}>
                                        {#if showMyPasswordConfirm}
                                            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.75" fill="none"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                                        {:else}
                                            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="1.75" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                                        {/if}
                                    </button>
                                </div>
                                {#if passwordMismatch}
                                    <span class="field-error-text">รหัสผ่านใหม่ทั้งสองช่องไม่ตรงกัน</span>
                                {:else}
                                    <span class="field-hint">ปล่อยว่างทั้งสองช่องหากไม่ต้องการเปลี่ยนรหัสผ่าน</span>
                                {/if}
                            </div>
                        </div>
                    {/if}
                </div>

                <div class="profile-modal-footer">
                    <div class="footer-status-hint">
                        {#if securityTabDirty}
                            <span class="staged-pill warn">เตรียมอัปเดตรหัสผ่านใหม่</span>
                        {:else if hasUnsavedProfileChanges}
                            <span class="staged-pill">มีการแก้ไขที่ยังไม่บันทึก</span>
                        {/if}
                    </div>
                    <div class="footer-btn-group">
                        <button type="button" class="btn-secondary" on:click={requestCloseProfileModal} disabled={isSavingMyProfile}>ยกเลิก</button>
                        <button
                          type="submit"
                          class="btn-primary profile-save-btn"
                          disabled={isSavingMyProfile || passwordMismatch || passwordTooShort}
                        >
                            {#if isSavingMyProfile}
                                <span class="btn-spinner-sm"></span>
                                <span>กำลังบันทึก...</span>
                            {:else}
                                <span>บันทึกข้อมูลส่วนตัว</span>
                            {/if}
                        </button>
                    </div>
                </div>
            </form>
        {/if}
    </div>
</div>
{/if}

<!-- Sidebar Delete Confirmation Modal -->
{#if showSidebarDeleteModal && sidebarItemToDelete}
<div class="modal-backdrop" role="presentation" transition:fade={{ duration: 150 }} on:click={cancelSidebarDelete}>
  <div class="modal-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="sidebar-delete-title" on:click|stopPropagation>
    <div class="modal-delete-icon-wrap">
      <div class="delete-icon-circle">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="28" height="28">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          <line x1="10" y1="11" x2="10" y2="17"></line>
          <line x1="14" y1="11" x2="14" y2="17"></line>
        </svg>
      </div>
    </div>

    <div class="modal-delete-content">
      <h3 id="sidebar-delete-title" class="modal-delete-title">
        {sidebarItemToDelete.type === 'group' ? 'ยืนยันการลบกลุ่มการตรวจสอบ' : 'ยืนยันการลบประวัติการตรวจ'}
      </h3>
      <p class="modal-delete-desc">
        คุณต้องการลบ {sidebarItemToDelete.type === 'group' ? 'กลุ่ม' : 'เอกสาร'}
        <span class="delete-target-badge">[{sidebarItemToDelete.typeName}] {sidebarItemToDelete.name}</span>
      </p>

      <div class="delete-warning-box">
        <div class="warning-icon" aria-hidden="true">!</div>
        <div class="warning-text">
          {sidebarItemToDelete.type === 'group'
            ? 'ประวัติการสแกนเอกสารและรายงานผล QA ทั้งหมดในกลุ่มนี้จะถูกลบอย่างถาวร'
            : 'ข้อมูลและรายงานผลการตรวจของเอกสารนี้จะถูกลบออกจากระบบอย่างถาวร'}
        </div>
      </div>
    </div>

    <div class="modal-delete-actions">
      <button type="button" class="btn-cancel-action" on:click={cancelSidebarDelete} disabled={isSidebarDeleting}>
        ยกเลิก
      </button>
      <button type="button" class="btn-danger-confirm" on:click={executeSidebarDelete} disabled={isSidebarDeleting}>
        {#if isSidebarDeleting}
          <span>กำลังลบ...</span>
        {:else}
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          ยืนยันการลบ
        {/if}
      </button>
    </div>
  </div>
</div>
{/if}

<style>
  .app-wrapper {
    position: relative;
    width: 100vw;
    height: 100vh;
    background-color: transparent; /* Changed from var(--bg-dark) to show body animated background */
    overflow: hidden;
  }

  /* ── Ambient Spectrum Background (Static GPU-friendly glow) ── */
  .spectrum-bg {
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 18% 22%, rgba(99, 102, 241, 0.14), transparent 45%),
                radial-gradient(circle at 82% 76%, rgba(168, 85, 247, 0.14), transparent 45%);
    opacity: 0.75;
    z-index: 0;
    pointer-events: none;
  }

  .spectrum-bg.layer-2 {
    background: radial-gradient(circle at 70% 30%, rgba(99, 102, 241, 0.12), transparent 42%),
                radial-gradient(circle at 30% 70%, rgba(168, 85, 247, 0.12), transparent 42%);
    opacity: 0.65;
    z-index: 0;
  }

  @keyframes spin { 100% { transform: rotate(360deg); } }

  .app-container {
    position: relative;
    z-index: 1;
    display: flex;
    height: 100vh;
    color: var(--text-main);
    font-family: var(--font-th);
  }

  /* ── Sidebar ── */
  .sidebar {
    width: clamp(260px, 18.5vw, 296px);
    height: 100vh;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border-right: 1px solid var(--glass-border);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    z-index: 100;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.37);
    transition: width 0.28s cubic-bezier(0.16, 1, 0.3, 1), transform 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  }

  .sidebar.collapsed {
    width: 72px;
  }

  .sidebar-logo {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 14px 14px 12px 16px;
    border-bottom: 1px solid var(--glass-border);
    flex-shrink: 0;
  }

  .sidebar.collapsed .sidebar-logo {
    padding: 14px 10px 12px;
    justify-content: center;
    flex-direction: column;
    gap: 8px;
  }

  .logo-brand-group {
    display: flex;
    align-items: center;
    gap: 11px;
    min-width: 0;
  }

  .logo-icon {
    width: 38px;
    height: 38px;
    padding: 0;
    background: #080912;
    border: 1px solid rgba(168, 85, 247, 0.35);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(99, 102, 241, 0.22);
  }

  .logo-icon img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .logo-text-wrap {
    min-width: 0;
  }

  .logo-title {
    font-family: var(--font-en);
    font-size: 17.5px;
    font-weight: 700;
    color: var(--text-main);
    line-height: 1.2;
    letter-spacing: 0.02em;
    white-space: nowrap;
  }
  
  .logo-sub {
    font-family: var(--font-en);
    font-size: 10.5px;
    color: var(--text-muted);
    font-weight: 500;
    letter-spacing: 0.03em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .btn-sidebar-collapse {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.2s ease;
  }

  .btn-sidebar-collapse:hover {
    background: rgba(99, 102, 241, 0.16);
    border-color: rgba(99, 102, 241, 0.35);
    color: var(--text-main);
  }

  .sidebar-nav {
    flex: 1;
    min-height: 0;
    padding: 8px 10px 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    scrollbar-color: rgba(139, 92, 246, 0.35) transparent;
  }

  .sidebar.collapsed .sidebar-nav {
    padding: 8px 8px;
    align-items: center;
  }

  .sidebar-menu-zone {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex-shrink: 0;
  }

  .sidebar.collapsed .sidebar-menu-zone {
    width: 100%;
    align-items: center;
  }

  /* ── Contextual Workspace Zone (Fills Remaining Vertical Space Dynamically) ── */
  .sidebar-context-zone {
    flex: 1 1 auto;
    min-height: 210px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--glass-border);
    overflow: hidden;
  }

  .sidebar-project-bar {
    background: rgba(18, 20, 28, 0.65);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 7px 10px;
    display: flex;
    flex-direction: column;
    gap: 5px;
    flex-shrink: 0;
  }

  .sidebar-proj-label-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .sidebar-proj-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--primary);
    box-shadow: 0 0 8px rgba(99, 102, 241, 0.6);
  }

  .sidebar-proj-caption {
    font-family: var(--font-th);
    font-size: 10.5px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 0.02em;
  }

  .sidebar-proj-select {
    width: 100%;
    background-color: rgba(10, 11, 18, 0.85);
    color: var(--text-main);
    border: 1px solid rgba(168, 85, 247, 0.3);
    border-radius: 8px;
    padding: 6px 28px 6px 10px;
    font-family: var(--font-th);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    outline: none;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .sidebar-proj-select:focus {
    border-color: var(--secondary);
    box-shadow: 0 0 0 2px rgba(168, 85, 247, 0.2);
  }

  .sidebar-filter-box {
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(10, 11, 18, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 5px 8px;
    margin-bottom: 6px;
    flex-shrink: 0;
    transition: border-color 0.2s ease;
  }

  .sidebar-filter-box:focus-within {
    border-color: rgba(99, 102, 241, 0.45);
  }

  .sidebar-filter-box svg {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .sidebar-filter-box input {
    flex: 1;
    min-width: 0;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-main);
    font-family: var(--font-th);
    font-size: 11.5px;
  }

  .sidebar-filter-box input::placeholder {
    color: var(--text-dim);
  }

  .btn-clear-filter {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 10px;
    cursor: pointer;
    padding: 0 2px;
    line-height: 1;
  }

  .btn-clear-filter:hover {
    color: var(--text-main);
  }

  .sidebar-empty-box {
    padding: 10px 12px;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 8px;
  }

  /* Custom Ultra-Clean Scrollbars (No Windows Arrows) */
  .sidebar-nav::-webkit-scrollbar,
  .qa-flex-scroll::-webkit-scrollbar {
    width: 4px;
    height: 4px;
  }
  .sidebar-nav::-webkit-scrollbar-button,
  .qa-flex-scroll::-webkit-scrollbar-button {
    display: none;
    width: 0;
    height: 0;
  }
  .sidebar-nav::-webkit-scrollbar-track,
  .qa-flex-scroll::-webkit-scrollbar-track {
    background: transparent;
  }
  .sidebar-nav::-webkit-scrollbar-thumb,
  .qa-flex-scroll::-webkit-scrollbar-thumb {
    background: rgba(139, 92, 246, 0.32);
    border-radius: 8px;
  }
  .sidebar-nav::-webkit-scrollbar-thumb:hover,
  .qa-flex-scroll::-webkit-scrollbar-thumb:hover {
    background: rgba(168, 85, 247, 0.65);
  }

  .nav-group-header {
    width: 100%;
    background: transparent;
    border: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px 3px;
    cursor: pointer;
    color: var(--text-dim);
    transition: color 0.2s ease;
  }

  .nav-group-header:first-child {
    padding-top: 2px;
  }

  .nav-group-header:hover .nav-group-label,
  .nav-group-header:hover .nav-group-chevron {
    color: var(--text-muted);
  }

  .sidebar.collapsed .nav-group-header {
    display: none;
  }

  .nav-group-label {
    font-family: var(--font-en);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
    transition: color 0.2s ease;
  }

  .nav-group-chevron {
    color: var(--text-dim);
    transition: transform 0.22s ease, color 0.2s ease;
  }

  .nav-group-chevron.collapsed {
    transform: rotate(-90deg);
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: clamp(7px, 0.85vh, 10px) 12px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    color: var(--text-muted);
    font-family: var(--font-en);
    font-size: 13.5px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
    text-align: left;
    position: relative;
    overflow: hidden;
    flex-shrink: 0;
  }

  .sidebar.collapsed .nav-item {
    width: 44px;
    height: 44px;
    padding: 0;
    justify-content: center;
  }

  .sidebar.collapsed .nav-item-label {
    display: none;
  }

  .nav-item-label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .nav-agent-master {
    color: #c084fc;
  }

  .nav-agent-workflow {
    color: #34d399;
  }

  .nav-item:hover {
    color: var(--text-main);
    background: var(--glass-bg-hover);
    border-color: var(--glass-border);
  }

  .nav-item.active {
    color: #fff;
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.3);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
  }

  .nav-item.active::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    width: 4px;
    background: var(--gradient-main);
    border-radius: 0 4px 4px 0;
  }
  
  .nav-item.active svg {
    color: var(--secondary);
    filter: drop-shadow(0 0 8px rgba(168, 85, 247, 0.5));
  }

  .history-section {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    min-height: 0;
  }

  .history-section.expanded {
    flex: 1 1 0;
    min-height: 105px;
    overflow: hidden;
  }

  .history-title-toggle {
    width: 100%;
    font: inherit;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 8px;
    border-radius: 8px;
    cursor: pointer;
    user-select: none;
    transition: all 0.2s ease;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    margin-bottom: 6px;
    flex-shrink: 0;
  }

  .history-title-toggle.flex-1 {
    flex: 1;
    min-width: 0;
    margin-bottom: 0;
  }

  .history-header-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 6px;
    flex-shrink: 0;
  }

  .btn-reset-group-pill {
    flex-shrink: 0;
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #d8b4fe;
    font-family: var(--font-th);
    font-size: 10.5px;
    font-weight: 500;
    padding: 5px 8px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-reset-group-pill:hover {
    background: rgba(168, 85, 247, 0.28);
    color: #ffffff;
  }

  .history-title-toggle:hover {
    background: rgba(99, 102, 241, 0.12);
    border-color: rgba(99, 102, 241, 0.25);
  }

  .history-title-left {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .history-title-text {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }

  .history-title-toggle:hover .history-title-text {
    color: var(--text-main);
  }

  .history-count-badge {
    background: rgba(99, 102, 241, 0.25);
    color: #a5b4fc;
    font-family: var(--font-en);
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 12px;
    line-height: 1.2;
    border: 1px solid rgba(99, 102, 241, 0.3);
  }

  .chevron-icon {
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    flex-shrink: 0;
  }

  .chevron-icon.collapsed {
    transform: rotate(-90deg);
  }

  .history-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .qa-flex-scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 3px;
    scrollbar-width: thin;
    scrollbar-color: rgba(139, 92, 246, 0.35) transparent;
  }

  .history-item {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 7px 8px;
    border-radius: 8px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s ease;
    color: var(--text-muted);
  }

  .history-item:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.12);
    color: var(--text-main);
  }

  .history-item.active {
    border-color: rgba(99, 102, 241, 0.45);
    background: rgba(99, 102, 241, 0.14);
    color: #fff;
  }

  .history-item.group-item:hover {
    border-color: rgba(139, 92, 246, 0.4);
    background: rgba(139, 92, 246, 0.08);
  }

  .history-item.group-item.active {
    border-color: rgba(168, 85, 247, 0.55);
    background: rgba(168, 85, 247, 0.16);
    color: #fff;
  }

  .sidebar-item-row {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    border-radius: 8px;
    flex-shrink: 0;
  }

  .sidebar-item-row .history-item {
    flex: 1;
    min-width: 0;
    padding-right: 26px;
  }

  .btn-sidebar-delete {
    position: absolute;
    right: 5px;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0;
    background: transparent;
    border: none;
    color: #94a3b8;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.2s ease, color 0.2s ease, background-color 0.2s ease;
    z-index: 2;
  }

  @media (hover: none), (pointer: coarse) {
    .btn-sidebar-delete {
      opacity: 0.78;
    }
  }

  .sidebar-item-row:hover .btn-sidebar-delete,
  .btn-sidebar-delete:focus-visible {
    opacity: 0.85;
  }

  .btn-sidebar-delete:hover {
    opacity: 1 !important;
    color: #f87171;
    background: rgba(239, 68, 68, 0.18);
  }

  .history-item svg {
    margin-top: 2px;
    flex-shrink: 0;
  }

  .history-details {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
    flex: 1;
    overflow: hidden;
  }

  .h-title-row {
    display: flex;
    align-items: center;
    gap: 5px;
    min-width: 0;
  }

  .h-status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    background: #64748b;
  }

  .h-status-dot.passed {
    background: var(--success, #10b981);
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.55);
  }

  .h-status-dot.conditional {
    background: var(--warning, #f59e0b);
    box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
  }

  .h-status-dot.rejected {
    background: var(--danger, #f43f5e);
    box-shadow: 0 0 6px rgba(244, 63, 94, 0.55);
  }

  .h-type-badge {
    flex-shrink: 0;
    font-family: var(--font-en);
    font-size: 9.5px;
    font-weight: 700;
    color: #d8b4fe;
    background: rgba(168, 85, 247, 0.18);
    border: 1px solid rgba(168, 85, 247, 0.32);
    padding: 1px 5px;
    border-radius: 4px;
    line-height: 1.3;
  }

  .h-meta-row {
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    flex-wrap: wrap;
  }

  .h-group-pill {
    font-size: 10px;
    font-weight: 500;
    color: #c4b5fd;
    background: rgba(139, 92, 246, 0.12);
    padding: 0 5px;
    border-radius: 4px;
    line-height: 1.4;
    max-width: 110px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .h-filename {
    font-size: 12.2px;
    font-weight: 500;
    line-height: 1.35;
    color: var(--text-main);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .h-date {
    font-family: var(--font-en);
    font-size: 10px;
    line-height: 1.3;
    color: var(--text-muted);
  }

  .sidebar-footer {
    padding: 10px 12px;
    border-top: 1px solid var(--glass-border);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .sidebar.collapsed .sidebar-footer {
    padding: 10px 8px;
    align-items: center;
  }

  /* ── Tutorial Button ── */
  .btn-tutorial {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 9px 12px;
    background: rgba(99, 102, 241, 0.06);
    border: 1px solid rgba(99, 102, 241, 0.18);
    color: rgba(167, 139, 250, 0.9);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border-radius: var(--radius-md);
    transition: all 0.25s ease;
    position: relative;
    overflow: hidden;
  }

  .sidebar.collapsed .btn-tutorial,
  .sidebar.collapsed .btn-logout {
    width: 44px;
    height: 40px;
    padding: 0;
    justify-content: center;
  }

  .btn-tutorial:hover {
    background: rgba(99, 102, 241, 0.14);
    border-color: rgba(99, 102, 241, 0.35);
    color: #c4b5fd;
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.15);
  }

  .tutorial-badge {
    margin-left: auto;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    padding: 2px 7px;
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 20px;
    color: #818cf8;
    font-family: var(--font-en);
  }

  .btn-logout {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 9px 12px;
    background: transparent;
    border: 1px solid transparent;
    color: var(--danger);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border-radius: var(--radius-md);
    transition: all 0.25s ease;
  }

  .btn-logout:hover {
    background: rgba(244, 63, 94, 0.1);
    border-color: rgba(244, 63, 94, 0.2);
  }

  .btn-mobile-menu {
    display: none;
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--glass-border);
    color: var(--text-main);
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
  }

  .sidebar-mobile-backdrop {
    display: none;
  }

  /* ── Main Workspace ── */
  .workspace {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
    background: rgba(18, 20, 28, 0.2);
  }

  /* Topbar */
  .topbar {
    position: relative;
    height: 70px;
    padding: 0 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    border-bottom: 1px solid var(--glass-border);
    background: transparent;
    z-index: var(--z-topbar, 900);
  }
  .topbar::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    z-index: -1;
    pointer-events: none;
  }

  .breadcrumb {
    font-family: var(--font-en);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-dim);
    letter-spacing: 1.2px;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .bc-active { color: var(--text-muted); }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-shrink: 0;
  }

  .search-box {
    display: flex; align-items: center; gap: 8px;
    background: var(--glass-bg-hover);
    border: 1px solid var(--glass-border);
    border-radius: 20px;
    padding: 8px 14px;
    width: clamp(160px, 18vw, 240px);
    transition: border-color 0.2s ease;
  }
  .search-box:focus-within {
    border-color: rgba(99, 102, 241, 0.5);
    box-shadow: 0 0 10px rgba(99, 102, 241, 0.15);
  }
  .search-box input {
    background: transparent; border: none; outline: none;
    color: var(--text-main); font-size: 13px; width: 100%;
    font-family: var(--font-th);
  }
  .search-box svg { color: var(--text-muted); }

  .icon-btn {
    background: var(--glass-bg-hover);
    border: 1px solid var(--glass-border);
    color: var(--text-muted);
    border-radius: 50%;
    width: 36px; height: 36px;
    cursor: pointer; position: relative;
    display: flex; align-items: center; justify-content: center;
    transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease, transform 0.2s ease;
  }
  .icon-btn:hover,
  .icon-btn.active {
    color: var(--text-main);
    border-color: var(--glass-border-light);
    background: rgba(168, 85, 247, 0.14);
  }
  .icon-btn:hover {
    transform: scale(1.05);
  }
  .noti-badge-count {
    position: absolute;
    top: -4px;
    right: -4px;
    background: var(--danger, #f43f5e);
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
    min-width: 18px;
    height: 18px;
    padding: 0 4px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid var(--bg-dark);
    box-shadow: 0 0 8px rgba(244, 63, 94, 0.6);
    font-family: var(--font-en);
    font-variant-numeric: tabular-nums;
  }

  .status-badge {
    display: flex; align-items: center; gap: 6px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.2);
    padding: 6px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 500; color: var(--success);
    font-family: var(--font-en);
    transition: all 0.3s ease;
  }
  .status-badge.error {
    background: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.2);
    color: var(--danger, #ef4444);
  }
  .dot {
    width: 8px; height: 8px; background: var(--success); border-radius: 50%;
    box-shadow: 0 0 8px var(--success);
    transition: all 0.3s ease;
  }
  .status-badge.error .dot {
    background: var(--danger, #ef4444);
    box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
  }

  .active-project-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 20px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #c7d2fe;
    font-family: var(--font-en);
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .proj-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--primary);
    flex-shrink: 0;
  }

  .user-profile-wrap {
    display: flex;
    align-items: center;
  }

  .user-profile-container {
    background: transparent;
    color: inherit;
    font: inherit;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    padding: 4px 12px 4px 16px;
    border-radius: 30px;
    transition: background 0.3s;
    border: 1px solid transparent;
  }
  .user-profile-container:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.1);
  }
  .user-info {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }
  .user-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-main);
    line-height: 1.2;
    font-family: var(--font-th);
  }
  .user-role {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-en);
  }

  .avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--gradient-main);
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px;
    font-family: var(--font-en);
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    transition: transform 0.3s;
    overflow: hidden;
  }
  .avatar img {
    width: 100%; height: 100%; object-fit: cover;
  }
  .user-profile-container:hover .avatar { transform: scale(1.05); }

  /* Content Scroll */
  .content-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 32px;
    position: relative;
    scroll-behavior: smooth;
    display: flex;
    flex-direction: column;
  }
  .content-scroll.no-padding {
    padding: 0;
    overflow: hidden;
  }
  .view-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .upload-container {
    padding: 32px;
    flex: 1;
  }

  /* Responsive Height & Viewport Scaling */
  @media (max-height: 860px) {
    .sidebar-logo {
      padding: 10px 12px;
    }
    .nav-group-header {
      padding: 5px 10px 2px;
    }
    .nav-item {
      padding: 6px 10px;
      font-size: 13px;
    }
    .sidebar-footer {
      padding: 8px 10px;
    }
    .btn-tutorial,
    .btn-logout {
      padding: 7px 10px;
      font-size: 12.5px;
    }
  }

  @media (max-width: 960px) {
    .btn-mobile-menu {
      display: inline-flex;
    }
    .sidebar-mobile-backdrop {
      display: block;
      position: fixed;
      inset: 0;
      background: rgba(5, 5, 5, 0.65);
      backdrop-filter: blur(4px);
      z-index: 1090;
    }
    .sidebar {
      position: fixed;
      top: 0;
      left: 0;
      bottom: 0;
      width: 280px !important;
      height: 100vh;
      transform: translateX(-100%);
      z-index: 1100;
      background: rgba(10, 11, 18, 0.96);
    }
    .sidebar.mobile-open {
      transform: translateX(0);
    }
    .topbar { height: 56px; padding: 0 16px; }
    .topbar-right { gap: 10px; }
    .search-box { display: none; }
    .user-info { display: none; }
    .status-badge { padding: 4px 10px; font-size: 11px; }
    .breadcrumb { font-size: 11px; }
  }

  @media (prefers-reduced-motion: reduce) {
    .spectrum-bg,
    .spectrum-bg.layer-2,
    .tutorial-badge {
      animation: none !important;
    }
  }

  /* ── Footer ── */
  .app-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px 16px;
    padding: 14px 28px;
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border-top: 1px solid var(--glass-border);
    font-size: 12px;
    color: var(--text-dim);
    flex-shrink: 0;
    font-family: var(--font-en);
  }
  .footer-links {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 20px;
  }
  @media (max-width: 680px) {
    .app-footer {
      padding: 12px 16px;
      font-size: 11px;
    }
    .footer-links {
      gap: 8px 14px;
    }
  }
  .footer-links a {
    color: var(--text-dim);
    text-decoration: none;
    transition: color 0.2s;
  }
  .footer-links a:hover {
    color: var(--text-muted);
  }

  /* Profile Dropdown */
  .dropdown-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    z-index: 9998;
  }
  .profile-dropdown {
    position: absolute; top: 100%; right: 0; margin-top: 10px;
    background: var(--bg-dark); border: 1px solid var(--glass-border);
    border-radius: var(--radius-md); box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    padding: 8px; z-index: 9999; min-width: 160px;
    display: flex; flex-direction: column; gap: 4px;
  }
  .dropdown-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 16px; background: transparent; border: none;
    color: var(--text-main); font-size: 13px; font-family: var(--font-en);
    border-radius: 6px; cursor: pointer; transition: all 0.2s;
    text-align: left;
  }
  .dropdown-item:hover {
    background: rgba(255,255,255,0.05);
  }
  .dropdown-item svg { width: 16px; height: 16px; color: var(--text-muted); }
  .logout-btn:hover { background: rgba(239, 68, 68, 0.1); color: var(--danger); }
  .logout-btn:hover svg { color: var(--danger); }

  /* Modal Base */
  .modal-backdrop {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.75); z-index: 10000;
    display: flex; align-items: center; justify-content: center;
    backdrop-filter: blur(5px);
  }
  .modal-content {
    background: var(--bg-dark); border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg); padding: 32px; width: 100%; max-width: 500px;
    position: relative; box-shadow: 0 20px 50px rgba(0,0,0,0.5);
  }
  .close-btn {
    position: absolute; top: 20px; right: 20px;
    background: transparent; border: none; color: var(--text-muted);
    cursor: pointer; transition: color 0.2s;
  }
  .close-btn:hover { color: white; }
  .close-btn svg { width: 24px; height: 24px; }
  .modal-title {
    font-size: 20px; font-weight: 600; margin-top: 0; margin-bottom: 24px;
    color: white; font-family: var(--font-th);
  }

  .history-item.is-processing {
    background: rgba(59, 130, 246, 0.05);
    border-color: rgba(59, 130, 246, 0.3);
  }
  .history-item.is-processing:hover {
    background: rgba(59, 130, 246, 0.1);
    transform: none;
    box-shadow: none;
  }

  /* Form & Avatar in Modal */
  .form-group {
    display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px;
    text-align: left;
  }
  .form-group label {
    font-size: 13px; color: var(--text-muted); font-weight: 500; font-family: var(--font-en);
  }
  .form-group input {
    background: rgba(0,0,0,0.2); border: 1px solid var(--glass-border);
    border-radius: var(--radius-md); padding: 12px 15px; color: white;
    font-size: 14px; font-family: var(--font-en); transition: border-color 0.3s;
  }
  .form-group input:focus { border-color: var(--primary); outline: none; }
  
  .eye-btn {
    position: absolute; right: 12px; background: transparent; border: none;
    color: var(--text-muted); cursor: pointer; display: flex; align-items: center;
    justify-content: center; padding: 4px; border-radius: 4px; transition: color 0.2s;
  }
  .eye-btn:hover { color: var(--text-main); }
  .modal-actions {
    display: flex; justify-content: flex-end; gap: 10px; margin-top: 25px;
  }
  .btn-secondary {
    background: rgba(255,255,255,0.05); border: 1px solid var(--glass-border);
    color: white; padding: 10px 20px; border-radius: var(--radius-md);
    cursor: pointer; transition: background 0.2s; font-family: var(--font-th);
  }
  .btn-secondary:hover { background: rgba(255,255,255,0.1); }
  .btn-sm { padding: 6px 12px; font-size: 13px; }

  /* ── Polished Profile Modal Styles (DESIGN.md aligned) ── */
  .modal-content.profile-modal-card {
    max-width: 640px;
    width: 94%;
    max-height: 90vh;
    overflow-y: auto;
    padding: 26px 28px;
    background: #141928;
    border: 1px solid rgba(148, 163, 184, 0.22);
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.52);
    border-radius: 20px;
    font-family: var(--font-th);
  }
  .profile-modal-card button:focus-visible,
  .profile-modal-card label.btn-avatar-action:focus-visible,
  .profile-modal-card input:focus-visible {
    outline: 2px solid #818cf8;
    outline-offset: 2px;
  }
  .profile-modal-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 18px;
  }
  .profile-modal-title-wrap .modal-title {
    font-size: 20px;
    font-weight: 600;
    margin: 0 0 4px 0;
    color: #f8fafc;
    font-family: var(--font-th);
  }
  .profile-modal-title-wrap .modal-subtitle {
    font-size: 13px;
    color: #94a3b8;
    margin: 0;
  }
  .profile-close-btn {
    width: 34px;
    height: 34px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: #cbd5e1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.16s ease, color 0.16s ease;
  }
  .profile-close-btn:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
  }

  .profile-discard-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    padding: 10px 14px;
    margin-bottom: 16px;
    background: rgba(245, 158, 11, 0.14);
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: 12px;
    font-size: 13px;
    color: #fde68a;
  }
  .discard-banner-actions {
    display: flex;
    gap: 8px;
  }
  .btn-banner-stay {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.18);
    color: #f8fafc;
    padding: 5px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-family: var(--font-th);
    cursor: pointer;
  }
  .btn-banner-discard {
    background: #e11d48;
    border: none;
    color: #ffffff;
    padding: 5px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    font-family: var(--font-th);
    cursor: pointer;
  }

  .profile-state-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 40px 20px;
    color: #cbd5e1;
    font-size: 14px;
    text-align: center;
  }
  .profile-state-box.error {
    color: #fecdd3;
  }
  .profile-state-box p {
    margin: 0;
    max-width: 48ch;
    line-height: 1.55;
  }
  .profile-spinner {
    width: 28px;
    height: 28px;
    border: 3px solid rgba(148, 163, 184, 0.2);
    border-top-color: #6366f1;
    border-radius: 50%;
    animation: profileSpin 0.8s linear infinite;
  }
  @keyframes profileSpin {
    to { transform: rotate(360deg); }
  }

  .sr-only-input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    border: 0;
  }

  /* Compact Horizontal Identity & Avatar Header */
  .profile-identity-bar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;
    margin-bottom: 18px;
    background: #1b2338;
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 12px;
    transition: border-color 0.18s ease, background-color 0.18s ease;
  }
  .profile-identity-bar.drag-over {
    border-color: #6366f1;
    background: rgba(99, 102, 241, 0.12);
  }
  .avatar-trigger-circle {
    position: relative;
    width: 72px;
    height: 72px;
    border-radius: 50%;
    background: #232f4d;
    border: 2px solid rgba(148, 163, 184, 0.32);
    cursor: pointer;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: border-color 0.18s ease;
  }
  .avatar-trigger-circle:hover {
    border-color: #818cf8;
  }
  .avatar-trigger-circle img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .avatar-fallback-text {
    font-family: var(--font-en);
    font-size: 26px;
    font-weight: 700;
    color: #e2e8f0;
  }
  .avatar-hover-overlay {
    position: absolute;
    inset: 0;
    background: rgba(15, 23, 42, 0.72);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #f8fafc;
    opacity: 0;
    transition: opacity 0.18s ease;
  }
  .avatar-trigger-circle:hover .avatar-hover-overlay {
    opacity: 1;
  }
  .identity-meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .identity-name-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .identity-display {
    font-size: 15px;
    font-weight: 600;
    color: #f8fafc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .identity-role-pill {
    font-family: var(--font-en);
    font-size: 12px;
    font-weight: 600;
    padding: 1px 8px;
    border-radius: 20px;
    background: rgba(99, 102, 241, 0.18);
    border: 1px solid rgba(129, 140, 248, 0.35);
    color: #c7d2fe;
  }
  .identity-username {
    font-family: var(--font-en);
    font-size: 12.5px;
    color: #94a3b8;
  }
  .drag-hint-text {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 2px;
  }
  .avatar-controls {
    display: flex;
    flex-direction: column;
    gap: 6px;
    flex-shrink: 0;
  }
  .btn-avatar-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
    font-family: var(--font-th);
    white-space: nowrap;
  }
  .btn-avatar-action.upload {
    background: #232f4d;
    border: 1px solid rgba(129, 140, 248, 0.38);
    color: #e0e7ff;
  }
  .btn-avatar-action.upload:hover {
    background: rgba(99, 102, 241, 0.25);
    border-color: #818cf8;
    color: #ffffff;
  }
  .btn-avatar-action.remove {
    background: transparent;
    border: 1px solid rgba(148, 163, 184, 0.24);
    color: #cbd5e1;
  }
  .btn-avatar-action.remove:hover {
    background: rgba(244, 63, 94, 0.14);
    border-color: rgba(244, 63, 94, 0.45);
    color: #fecdd3;
  }
  .btn-avatar-action.undo {
    background: rgba(245, 158, 11, 0.16);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: #fde68a;
  }

  /* Profile Tabs Navigation */
  .profile-tabs-header {
    display: flex;
    gap: 6px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.18);
    margin-bottom: 18px;
    padding-bottom: 10px;
    flex-wrap: wrap;
  }
  .ptab-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: transparent;
    border: 1px solid transparent;
    color: #94a3b8;
    padding: 8px 14px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border-radius: 8px;
    transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
    font-family: var(--font-th);
  }
  .ptab-btn:hover {
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.05);
  }
  .ptab-btn.active {
    color: #ffffff;
    background: rgba(99, 102, 241, 0.2);
    border-color: rgba(129, 140, 248, 0.42);
    font-weight: 600;
  }
  .tab-dirty-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #818cf8;
  }
  .tab-dirty-dot.warn {
    background: #f59e0b;
  }

  .profile-inline-error {
    padding: 10px 14px;
    margin-bottom: 14px;
    background: rgba(244, 63, 94, 0.14);
    border: 1px solid rgba(244, 63, 94, 0.4);
    border-radius: 8px;
    color: #fecdd3;
    font-size: 13px;
  }

  /* Form Layout & Icon Inputs */
  .profile-form-body {
    min-height: 175px;
  }
  .profile-form-body .form-group {
    margin-bottom: 0;
  }
  .profile-form-body label {
    font-family: var(--font-th);
    font-size: 13px;
    color: #cbd5e1;
    margin-bottom: 6px;
    display: block;
  }
  .profile-form-body input {
    font-family: var(--font-th);
    font-size: 14px;
    background: #1b2338;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
    color: #f8fafc;
    padding: 10px 14px;
    width: 100%;
    box-sizing: border-box;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }
  .profile-form-body input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.18);
    outline: none;
  }
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .form-grid .form-group:first-child {
    grid-column: 1 / -1;
  }
  .security-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .input-with-icon {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
  }
  .field-icon {
    position: absolute;
    left: 13px;
    color: #94a3b8;
    display: inline-flex;
    align-items: center;
    pointer-events: none;
    z-index: 1;
  }
  .profile-form-body .input-with-icon input {
    padding-left: 38px;
  }
  .profile-form-body .input-with-icon input.password-input {
    padding-right: 40px;
  }
  .field-hint {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 6px;
    display: block;
    font-family: var(--font-th);
  }
  .field-error-text {
    font-size: 12px;
    color: #fda4af;
    margin-top: 6px;
    display: block;
    font-family: var(--font-th);
  }

  .profile-modal-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    margin-top: 22px;
    padding-top: 16px;
    border-top: 1px solid rgba(148, 163, 184, 0.16);
  }
  .footer-status-hint {
    display: flex;
    align-items: center;
  }
  .staged-pill {
    font-size: 12px;
    color: #c7d2fe;
    background: rgba(99, 102, 241, 0.16);
    border: 1px solid rgba(129, 140, 248, 0.35);
    padding: 4px 10px;
    border-radius: 20px;
  }
  .staged-pill.warn {
    color: #fde68a;
    background: rgba(245, 158, 11, 0.16);
    border-color: rgba(245, 158, 11, 0.4);
  }
  .footer-btn-group {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-left: auto;
  }
  .profile-save-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 0;
  }
  .profile-save-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .btn-spinner-sm {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: profileSpin 0.7s linear infinite;
  }

  @media (max-width: 600px) {
    .profile-identity-bar {
      flex-direction: column;
      align-items: flex-start;
    }
    .avatar-controls {
      flex-direction: row;
      width: 100%;
    }
    .form-grid,
    .security-grid {
      grid-template-columns: 1fr;
    }
  }

  /* Delete Confirmation Modal */
  .modal-delete-dialog {
    background: rgba(15, 23, 42, 0.96);
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 18px;
    width: 90%;
    max-width: 440px;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.85), 0 0 35px rgba(239, 68, 68, 0.15);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    overflow: hidden;
    text-align: center;
    padding: 28px 24px;
    animation: modalPop 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }
  @keyframes modalPop {
    from { opacity: 0; transform: scale(0.95) translateY(10px); }
    to { opacity: 1; transform: scale(1) translateY(0); }
  }
  .modal-delete-icon-wrap {
    display: flex;
    justify-content: center;
    margin-bottom: 16px;
  }
  .delete-icon-circle {
    width: 58px;
    height: 58px;
    border-radius: 50%;
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.35);
    color: #f87171;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.2);
  }
  .modal-delete-title {
    margin: 0 0 8px 0;
    font-size: 18px;
    font-weight: 700;
    color: #f8fafc;
  }
  .modal-delete-desc {
    margin: 0 0 16px 0;
    font-size: 13.5px;
    color: #94a3b8;
    line-height: 1.5;
  }
  .delete-target-badge {
    display: inline-block;
    margin-top: 4px;
    background: rgba(168, 85, 247, 0.15);
    border: 1px solid rgba(168, 85, 247, 0.35);
    color: #e9d5ff;
    padding: 3px 10px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 13px;
  }
  .delete-warning-box {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.25);
    border-radius: 10px;
    padding: 10px 14px;
    display: flex;
    align-items: center;
    gap: 10px;
    text-align: left;
    margin-bottom: 22px;
  }
  .warning-icon {
    font-size: 18px;
    flex-shrink: 0;
  }
  .warning-text {
    font-size: 12px;
    color: #fca5a5;
    line-height: 1.4;
  }
  .modal-delete-actions {
    display: flex;
    gap: 12px;
    justify-content: center;
  }
  .modal-delete-actions button {
    flex: 1;
    margin: 0;
  }
  .btn-cancel-action {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #cbd5e1;
    padding: 10px 18px;
    font-size: 13.5px;
    font-weight: 500;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .btn-cancel-action:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
    color: white;
  }
  .btn-danger-confirm {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    border: 1px solid #f87171;
    color: #ffffff;
    padding: 10px 18px;
    font-size: 13.5px;
    font-weight: 600;
    border-radius: 10px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s ease;
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3);
  }
  .btn-danger-confirm:hover:not(:disabled) {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    box-shadow: 0 6px 18px rgba(239, 68, 68, 0.5);
    transform: translateY(-1px);
  }
  .btn-danger-confirm:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>

