<script>
  export let title = "Coming Soon";
</script>

<div class="coming-soon">
  <div class="cs-icon">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  </div>
  <h2>{title}</h2>
  <p>ฟีเจอร์นี้กำลังอยู่ระหว่างการพัฒนา</p>
</div>

<style>
  .coming-soon {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    min-height: 400px;
    gap: 16px;
    color: var(--text-muted);
    font-family: var(--font-th);
  }
  .cs-icon {
    width: 80px;
    height: 80px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--primary);
    margin-bottom: 8px;
  }
  h2 {
    font-family: var(--font-en);
    font-size: 24px;
    font-weight: 700;
    color: var(--text-main);
    margin: 0;
  }
  p {
    font-size: 14px;
    color: var(--text-dim);
    margin: 0;
  }
</style>
