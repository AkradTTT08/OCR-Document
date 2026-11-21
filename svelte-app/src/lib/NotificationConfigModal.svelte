<script>
  import { onMount } from "svelte";
  import { fade, scale } from "svelte/transition";
  import { toast } from "./toastStore.js";

  export let showModal = false;

  const STORAGE_KEY = "spectra_qa_webhook_config";

  function defaultChannels() {
    return {
      slack: { webhook_url: "" },
      teams: { webhook_url: "" },
      line: { token: "" },
      telegram: { bot_token: "", chat_id: "" }
    };
  }

  let channels = defaultChannels();
  let isTesting = false;

  function loadConfig() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        channels = {
          slack: { webhook_url: parsed?.slack?.webhook_url || "" },
          teams: { webhook_url: parsed?.teams?.webhook_url || "" },
          line: { token: parsed?.line?.token || "" },
          telegram: {
            bot_token: parsed?.telegram?.bot_token || "",
            chat_id: parsed?.telegram?.chat_id || ""
          }
        };
      }
    } catch {
      channels = defaultChannels();
    }
  }

  onMount(() => {
    loadConfig();
  });

  $: if (showModal) {
    loadConfig();
  }

  function closeModal() {
    showModal = false;
  }

  function handleKeydown(e) {
    if (showModal && e.key === "Escape") {
      e.preventDefault();
      closeModal();
    }
  }

  async function testNotification() {
    isTesting = true;
    try {
      const res = await fetch("/api/notifications/test-webhook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          channels,
          message: "🚀 Spectra QA Webhook Test Alert: All quality gates passed successfully!",
          title: "Spectra QA Notification Test"
        })
      });
      if (res.ok) {
        toast("✅ ส่งข้อความทดสอบไปยังช่องทางที่ตั้งค่าไว้สำเร็จ!", "success");
      } else {
        toast("❌ เกิดข้อผิดพลาดในการส่งข้อความทดสอบ", "error");
      }
    } catch (e) {
      toast("ไม่สามารถเชื่อมต่อกับ Server ได้", "error");
    } finally {
      isTesting = false;
    }
  }

  function saveConfig() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(channels));
    } catch {
      // ignore storage quota errors
    }
    toast("บันทึกการตั้งค่า Webhook Notification เรียบร้อยแล้ว", "success");
    showModal = false;
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if showModal}
<div class="modal-backdrop" role="presentation" transition:fade={{ duration: 200 }} on:click|self={closeModal}>
  <div
    class="modal-card glass-panel"
    role="dialog"
    aria-modal="true"
    aria-labelledby="noti-config-title"
    in:scale={{ start: 0.9, duration: 250 }}
  >
    <div class="modal-header">
      <div class="header-lead">
        <span class="icon-wrap" aria-hidden="true">🔔</span>
        <div class="header-text">
          <h3 id="noti-config-title" class="modal-title">CI/CD Multi-channel Webhook Notifications</h3>
          <p class="modal-subtitle">ตั้งค่าช่องทางรับการแจ้งเตือนสรุปผลรัน Test จาก GitHub Actions, GitLab CI &amp; Jenkins</p>
        </div>
      </div>
      <button type="button" class="close-btn" aria-label="ปิดหน้าต่าง" title="ปิดหน้าต่าง (Esc)" on:click={closeModal}>✕</button>
    </div>

    <div class="form-body">
      <!-- Slack -->
      <div class="channel-card">
        <label for="noti-slack-url" class="channel-title">💬 Slack Webhook</label>
        <input id="noti-slack-url" type="url" class="input-field" aria-label="Slack Webhook URL" bind:value={channels.slack.webhook_url} placeholder="https://hooks.slack.com/services/..." />
      </div>

      <!-- Microsoft Teams -->
      <div class="channel-card">
        <label for="noti-teams-url" class="channel-title">👥 Microsoft Teams Webhook</label>
        <input id="noti-teams-url" type="url" class="input-field" aria-label="Microsoft Teams Webhook URL" bind:value={channels.teams.webhook_url} placeholder="https://outlook.office.com/webhook/..." />
      </div>

      <!-- LINE Notify -->
      <div class="channel-card">
        <label for="noti-line-token" class="channel-title">🟢 LINE Notify Token</label>
        <input id="noti-line-token" type="text" class="input-field" aria-label="LINE Notify Token" bind:value={channels.line.token} placeholder="กรอก LINE Notify Token (เช่น Bearer TOKEN...)" />
      </div>

      <!-- Telegram -->
      <div class="channel-card">
        <label for="noti-telegram-token" class="channel-title">✈️ Telegram Bot</label>
        <div class="telegram-row">
          <input id="noti-telegram-token" type="text" class="input-field telegram-token-input" aria-label="Telegram Bot Token" bind:value={channels.telegram.bot_token} placeholder="Bot Token (เช่น 123456:ABC-DEF...)" />
          <input id="noti-telegram-chat-id" type="text" class="input-field telegram-chat-input" aria-label="Telegram Chat ID" bind:value={channels.telegram.chat_id} placeholder="Chat ID (เช่น -100123...)" />
        </div>
      </div>
    </div>

    <div class="modal-actions">
      <button type="button" class="btn-secondary" on:click={testNotification} disabled={isTesting}>
        {#if isTesting}⏳ กำลังทดสอบ...{:else}🧪 ทดสอบส่งการแจ้งเตือน{/if}
      </button>
      <button type="button" class="btn-primary" on:click={saveConfig}>บันทึกการตั้งค่า</button>
    </div>
  </div>
</div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    padding: 16px;
    background: rgba(0, 0, 0, 0.75);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    z-index: var(--z-modal, 10000);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal-card {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(139, 92, 246, 0.3);
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.8), 0 0 30px rgba(139, 92, 246, 0.2);
    border-radius: 16px;
    width: 100%;
    max-width: 640px;
    max-height: 90vh;
    overflow-y: auto;
    padding: 24px;
    color: var(--text-main, #f8fafc);
  }
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 16px;
  }
  .header-lead {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .header-text {
    min-width: 0;
  }
  .icon-wrap {
    font-size: 28px;
    flex-shrink: 0;
  }
  .modal-title {
    font-size: 18px;
    font-weight: 700;
    margin: 0;
    color: var(--text-main, #f8fafc);
  }
  .modal-subtitle {
    font-size: 12px;
    color: var(--text-muted, #94a3b8);
    margin: 2px 0 0 0;
  }
  .close-btn {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    border-radius: 8px;
    color: var(--text-muted, #94a3b8);
    font-size: 15px;
    cursor: pointer;
    transition: background-color 0.2s, color 0.2s;
  }
  .close-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-main, #f8fafc);
  }

  .form-body {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 20px;
    max-height: 50vh;
    overflow-y: auto;
    padding-right: 4px;
  }
  .channel-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 12px 14px;
    border-radius: 10px;
  }
  .channel-title {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: #e2e8f0;
    margin-bottom: 6px;
  }
  .telegram-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .telegram-token-input {
    flex: 1.2 1 200px;
    min-width: 0;
  }
  .telegram-chat-input {
    flex: 0.8 1 160px;
    min-width: 0;
  }
  .input-field {
    width: 100%;
    min-width: 0;
    background: rgba(0, 0, 0, 0.4);
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: var(--text-main, #f8fafc);
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12.5px;
  }
  .input-field:focus {
    border-color: #8b5cf6;
    outline: none;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 10px;
  }
  .btn-secondary,
  .btn-primary {
    min-height: 38px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 8px 18px;
    border-radius: 8px;
    font-size: 13px;
    font-family: inherit;
    cursor: pointer;
    transition: background-color 0.2s, opacity 0.2s, transform 0.2s;
  }
  .btn-secondary {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid var(--glass-border-light, rgba(255, 255, 255, 0.15));
    color: var(--text-main, #f8fafc);
    font-weight: 500;
  }
  .btn-secondary:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.12);
  }
  .btn-secondary:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
  .btn-primary {
    background: linear-gradient(135deg, #8b5cf6, #6d28d9);
    border: 1px solid transparent;
    color: #ffffff;
    font-weight: 600;
  }
  .btn-primary:hover:not(:disabled) {
    opacity: 0.94;
    transform: translateY(-1px);
  }
</style>
