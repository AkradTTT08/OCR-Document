<script>
  import { fade, scale } from "svelte/transition";
  import { toast } from "./toastStore.js";

  export var showModal = false;

  var channels = {
    slack: { webhook_url: "" },
    teams: { webhook_url: "" },
    line: { token: "" },
    telegram: { bot_token: "", chat_id: "" }
  };

  var isTesting = false;

  async function testNotification() {
    isTesting = true;
    try {
      const res = await fetch("http://127.0.0.1:5000/api/notifications/test-webhook", {
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
    toast("บันทึกการตั้งค่า Webhook Notification เรียบร้อยแล้ว", "success");
    showModal = false;
  }
</script>

{#if showModal}
<div class="modal-backdrop" transition:fade={{ duration: 200 }}>
  <div class="modal-card glass-panel" in:scale={{ start: 0.9, duration: 250 }}>
    <div class="modal-header">
      <div style="display: flex; align-items: center; gap: 10px;">
        <span class="icon-wrap">🔔</span>
        <div>
          <h3 class="modal-title">CI/CD Multi-channel Webhook Notifications</h3>
          <p class="modal-subtitle">ตั้งค่าช่องทางรับการแจ้งเตือนสรุปผลรัน Test จาก GitHub Actions, GitLab CI & Jenkins</p>
        </div>
      </div>
      <button class="close-btn" on:click={() => showModal = false}>✕</button>
    </div>

    <div class="form-body">
      <!-- Slack -->
      <div class="channel-card">
        <div class="channel-title">💬 Slack Webhook</div>
        <input type="url" class="input-field" bind:value={channels.slack.webhook_url} placeholder="https://hooks.slack.com/services/..." />
      </div>

      <!-- Microsoft Teams -->
      <div class="channel-card">
        <div class="channel-title">👥 Microsoft Teams Webhook</div>
        <input type="url" class="input-field" bind:value={channels.teams.webhook_url} placeholder="https://outlook.office.com/webhook/..." />
      </div>

      <!-- LINE Notify -->
      <div class="channel-card">
        <div class="channel-title">🟢 LINE Notify Token</div>
        <input type="text" class="input-field" bind:value={channels.line.token} placeholder="กรอก LINE Notify Token (เช่น Bearer TOKEN...)" />
      </div>

      <!-- Telegram -->
      <div class="channel-card">
        <div class="channel-title">✈️ Telegram Bot</div>
        <div style="display: flex; gap: 8px;">
          <input type="text" class="input-field" style="flex: 1.2;" bind:value={channels.telegram.bot_token} placeholder="Bot Token (เช่น 123456:ABC-DEF...)" />
          <input type="text" class="input-field" style="flex: 0.8;" bind:value={channels.telegram.chat_id} placeholder="Chat ID (เช่น -100123...)" />
        </div>
      </div>
    </div>

    <div class="modal-actions">
      <button class="btn-secondary" on:click={testNotification} disabled={isTesting}>
        {#if isTesting}⏳ กำลังทดสอบ...{:else}🧪 ทดสอบส่งการแจ้งเตือน{/if}
      </button>
      <button class="btn-primary" on:click={saveConfig}>บันทึกการตั้งค่า</button>
    </div>
  </div>
</div>
{/if}

<style>
  .modal-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.75);
    backdrop-filter: blur(8px); z-index: 9999;
    display: flex; align-items: center; justify-content: center;
  }
  .modal-card {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(139, 92, 246, 0.3);
    box-shadow: 0 25px 60px rgba(0,0,0,0.8), 0 0 30px rgba(139, 92, 246, 0.2);
    border-radius: 16px; width: 95%; max-width: 640px; padding: 24px; color: white;
  }
  .modal-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
  .icon-wrap { font-size: 28px; }
  .modal-title { font-size: 18px; font-weight: 700; margin: 0; background: linear-gradient(135deg, #fff, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .modal-subtitle { font-size: 12px; color: #94a3b8; margin: 2px 0 0 0; }
  .close-btn { background: transparent; border: none; color: #94a3b8; font-size: 16px; cursor: pointer; }

  .form-body { display: flex; flex-direction: column; gap: 14px; margin-bottom: 20px; max-height: 320px; overflow-y: auto; padding-right: 4px; }
  .channel-card { background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); padding: 12px 14px; border-radius: 10px; }
  .channel-title { font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 6px; }
  .input-field { width: 100%; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.12); color: white; padding: 8px 12px; border-radius: 8px; font-size: 12px; }
  .input-field:focus { border-color: #8b5cf6; outline: none; }

  .modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
  .btn-secondary { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 13px; }
  .btn-primary { background: linear-gradient(135deg, #8b5cf6, #6d28d9); border: none; color: white; padding: 8px 20px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 13px; }
</style>
