<script>
    import { logout, authUser } from './authStore.js';
</script>

<div class="coming-soon">
    <div class="content">
        <div class="icon">🚀</div>
        <h2>Coming Soon</h2>
        <p>สวัสดีคุณ <strong>{$authUser}</strong></p>
        <p class="desc">ฟีเจอร์สำหรับผู้ใช้งานทั่วไป (User) กำลังอยู่ระหว่างการพัฒนา<br>กรุณารอติดตามการอัปเดตในเวอร์ชันถัดไปครับ</p>
        <button class="logout-btn" on:click={logout}>ออกจากระบบ</button>
    </div>
</div>

<style>
    .coming-soon {
        width: 100vw; height: 100vh;
        display: flex; align-items: center; justify-content: center;
        background: var(--bg, #0a0a0c);
        color: var(--text, #f0f0f5);
        text-align: center;
    }
    .content {
        background: var(--surface, #121216);
        padding: 50px; border-radius: 20px;
        border: 1px solid var(--border, #2a2a35);
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .icon { font-size: 60px; margin-bottom: 20px; animation: float 3s ease-in-out infinite; }
    h2 { font-size: 32px; margin-bottom: 10px; background: linear-gradient(135deg, var(--primary, #6C8EFB), var(--accent, #9B6Cfb)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .desc { color: var(--text3, #8a8a9a); margin-top: 10px; font-size: 15px; line-height: 1.6; }
    .logout-btn {
        margin-top: 30px; padding: 10px 24px;
        background: transparent; color: var(--danger, #f87171);
        border: 1px solid rgba(248,113,113,0.3); border-radius: 8px;
        cursor: pointer; font-size: 14px; transition: all 0.2s;
    }
    .logout-btn:hover { background: rgba(248,113,113,0.1); }
    @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }
</style>
