<script>
  import { createEventDispatcher } from 'svelte';

  export let title = "กำลังประมวลผล...";
  export let status = "";
  export let progressPct = null;
  export let size = "default"; // 'default' | 'compact' | 'large'
  export let subtitleChip = "";
  export let elapsedSeconds = null;
  export let stages = []; // Optional: [{ label: string, minPct: number }]
  export let showCancel = false;
  export let cancelLabel = "หยุดการสแกนเอกสาร";
  export let cancelling = false;

  const dispatch = createEventDispatcher();
  const uid = Math.random().toString(36).slice(2, 8);
  const facetTopId = `spectra-top-${uid}`;
  const facetLeftId = `spectra-left-${uid}`;
  const facetRightId = `spectra-right-${uid}`;
  const runnerGradId = `spectra-runner-${uid}`;

  $: clampedProgress =
    progressPct !== null && progressPct !== undefined
      ? Math.max(0, Math.min(100, Math.round(Number(progressPct) || 0)))
      : null;

  $: formattedElapsed = (() => {
    if (elapsedSeconds === null || elapsedSeconds === undefined || elapsedSeconds < 0) return "";
    const total = Math.floor(Number(elapsedSeconds) || 0);
    const mins = String(Math.floor(total / 60)).padStart(2, "0");
    const secs = String(total % 60).padStart(2, "0");
    return `${mins}:${secs}`;
  })();

  $: activeStageIdx = (() => {
    if (!stages || stages.length === 0 || clampedProgress === null) return -1;
    let idx = 0;
    for (let i = 0; i < stages.length; i++) {
      if (clampedProgress >= (stages[i].minPct ?? 0)) {
        idx = i;
      }
    }
    return idx;
  })();

  function handleCancel() {
    if (cancelling) return;
    dispatch('cancel');
  }
</script>

<div class="spectra-loading-wrap {size}" role="status" aria-live="polite">
  <div class="radar-arena" aria-hidden="true">
    <!-- Dual staggered sonar waves -->
    <div class="concentric-ring ring-outer-pulse"></div>
    <div class="concentric-ring ring-outer-pulse delayed"></div>

    <!-- Outer static reference ring -->
    <div class="concentric-ring ring-3"></div>

    <!-- Conic sweeping radar beam -->
    <div class="radar-beam"></div>

    <!-- Precision counter-rotating SVG telemetry orbits & satellite nodes -->
    <svg class="orbit-svg orbit-ccw" viewBox="0 0 260 260" fill="none">
      <circle
        cx="130"
        cy="130"
        r="114"
        stroke="rgba(129, 140, 248, 0.34)"
        stroke-width="1.25"
        stroke-dasharray="8 12 24 12"
      />
      <circle cx="130" cy="16" r="3" fill="#06b6d4" />
      <circle cx="130" cy="244" r="2.5" fill="#a855f7" />
    </svg>

    <svg class="orbit-svg orbit-cw" viewBox="0 0 260 260" fill="none">
      <circle
        cx="130"
        cy="130"
        r="94"
        stroke="rgba(168, 85, 247, 0.32)"
        stroke-width="1.5"
        stroke-dasharray="46 28 14 28"
        stroke-linecap="round"
      />
      <circle cx="224" cy="130" r="3.8" fill="#c084fc" />
      <circle cx="63" cy="64" r="3" fill="#06b6d4" />
    </svg>

    <!-- Middle breathing ring -->
    <div class="concentric-ring ring-2"></div>

    <!-- Inner active core with sweeping laser scan line -->
    <div class="concentric-ring ring-1">
      <div class="ring-core-glow"></div>
      <div class="prism-scan-laser"></div>
    </div>

    <!-- Center 3D Isometric Prism Core with Multi-Facet Refraction & Perimeter Energy Trace -->
    <div class="iso-cube-container">
      <svg class="spectra-iso-cube" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id={facetTopId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#06b6d4" stop-opacity="0.48" />
            <stop offset="100%" stop-color="#a855f7" stop-opacity="0.2" />
          </linearGradient>
          <linearGradient id={facetLeftId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#6366f1" stop-opacity="0.42" />
            <stop offset="100%" stop-color="#12141c" stop-opacity="0.08" />
          </linearGradient>
          <linearGradient id={facetRightId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#a855f7" stop-opacity="0.44" />
            <stop offset="100%" stop-color="#06b6d4" stop-opacity="0.1" />
          </linearGradient>
          <linearGradient id={runnerGradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#06b6d4" />
            <stop offset="50%" stop-color="#ffffff" />
            <stop offset="100%" stop-color="#c084fc" />
          </linearGradient>
        </defs>

        <!-- Sequentially pulsing isometric facets -->
        <polygon class="prism-facet facet-top" points="50,10 85,30 50,50 15,30" fill={`url(#${facetTopId})`} />
        <polygon class="prism-facet facet-left" points="15,30 50,50 50,90 15,70" fill={`url(#${facetLeftId})`} />
        <polygon class="prism-facet facet-right" points="85,30 85,70 50,90 50,50" fill={`url(#${facetRightId})`} />

        <!-- Inner Core Diamond -->
        <polygon
          class="inner-diamond"
          points="50,31 69,43 50,55 31,43"
          fill="rgba(199, 210, 254, 0.16)"
          stroke="#ffffff"
          stroke-width="3.8"
          stroke-linejoin="round"
        />

        <!-- Base Outer Hexagon Wireframe -->
        <polygon
          points="50,10 85,30 85,70 50,90 15,70 15,30"
          stroke="rgba(255, 255, 255, 0.86)"
          stroke-width="4"
          stroke-linejoin="round"
        />

        <!-- Animated Energy Runner tracing around Outer Hexagon -->
        <polygon
          class="hex-energy-runner"
          points="50,10 85,30 85,70 50,90 15,70 15,30"
          stroke={`url(#${runnerGradId})`}
          stroke-width="4.6"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <!-- Radial Connecting Struts -->
        <line x1="50" y1="10" x2="50" y2="31" stroke="#ffffff" stroke-width="3.6" stroke-linecap="round" />
        <line x1="85" y1="30" x2="69" y2="43" stroke="#ffffff" stroke-width="3.6" stroke-linecap="round" />
        <line x1="15" y1="30" x2="31" y2="43" stroke="#ffffff" stroke-width="3.6" stroke-linecap="round" />
        <line x1="50" y1="55" x2="50" y2="90" stroke="#ffffff" stroke-width="3.6" stroke-linecap="round" />
        <line x1="69" y1="43" x2="85" y2="70" stroke="#ffffff" stroke-width="3.6" stroke-linecap="round" />
        <line x1="31" y1="43" x2="15" y2="70" stroke="#ffffff" stroke-width="3.6" stroke-linecap="round" />
      </svg>
    </div>
  </div>

  {#if subtitleChip}
    <div class="doc-target-chip" title={subtitleChip}>
      <span class="live-scan-dot" aria-hidden="true"></span>
      <span class="doc-target-name">{subtitleChip}</span>
    </div>
  {/if}

  {#if title}
    <h2 class="loading-title">{title}</h2>
  {/if}

  {#if status}
    <p class="loading-status">{status}</p>
  {/if}

  {#if clampedProgress !== null}
    <div class="progress-telemetry-box">
      <div
        class="progress-bar-container"
        role="progressbar"
        aria-valuenow={clampedProgress}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-label={title || 'ความคืบหน้าการประมวลผล'}
      >
        <div class="progress-fill" style="width: {clampedProgress}%">
          <div class="progress-shimmer"></div>
        </div>
      </div>

      <div class="progress-meta-row">
        {#if formattedElapsed}
          <span class="elapsed-badge">เวลาที่ใช้ {formattedElapsed}</span>
        {:else}
          <span></span>
        {/if}
        <span class="progress-pct-label">{clampedProgress}%</span>
      </div>
    </div>
  {/if}

  {#if stages && stages.length > 0}
    <div class="stage-track" aria-hidden="true">
      {#each stages as st, i}
        <div
          class="stage-pill"
          class:is-done={i < activeStageIdx}
          class:is-active={i === activeStageIdx}
        >
          {#if i < activeStageIdx}
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" width="12" height="12">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          {:else}
            <span class="stage-dot"></span>
          {/if}
          <span>{st.label}</span>
        </div>
      {/each}
    </div>
  {/if}

  {#if showCancel}
    <div class="cancel-action-wrap">
      <button
        type="button"
        class="btn-stop-scan"
        on:click={handleCancel}
        disabled={cancelling}
      >
        {#if cancelling}
          <span class="spinner" aria-hidden="true"></span>
          <span>กำลังยกเลิกการสแกน...</span>
        {:else}
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
            <rect x="5" y="5" width="14" height="14" rx="2.5"></rect>
          </svg>
          <span>{cancelLabel}</span>
        {/if}
      </button>
    </div>
  {/if}
</div>

<style>
  .spectra-loading-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 36px 20px;
    width: 100%;
    max-width: 100%;
    overflow: hidden;
    text-align: center;
    position: relative;
    user-select: none;
    box-sizing: border-box;
  }

  .spectra-loading-wrap.compact {
    padding: 20px 12px;
  }

  /* Radar Arena & Multi-Layer Orbital Scanner */
  .radar-arena {
    position: relative;
    width: min(248px, 72vw);
    height: min(248px, 72vw);
    max-width: min(248px, 72vw);
    aspect-ratio: 1 / 1;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 24px;
    flex-shrink: 0;
  }

  .compact .radar-arena {
    width: min(188px, 64vw);
    height: min(188px, 64vw);
    max-width: min(188px, 64vw);
    margin-bottom: 16px;
  }

  .large .radar-arena {
    width: min(300px, 78vw);
    height: min(300px, 78vw);
    max-width: min(300px, 78vw);
    margin-bottom: 32px;
  }

  .concentric-ring {
    position: absolute;
    border-radius: 50%;
    box-sizing: border-box;
    pointer-events: none;
  }

  /* Conic Radar Sweep Beam */
  .radar-beam {
    position: absolute;
    width: 92%;
    height: 92%;
    border-radius: 50%;
    background: conic-gradient(
      from 0deg,
      transparent 0deg 265deg,
      rgba(6, 182, 212, 0.08) 310deg,
      rgba(99, 102, 241, 0.22) 342deg,
      rgba(168, 85, 247, 0.44) 360deg
    );
    -webkit-mask-image: radial-gradient(circle, transparent 24%, #000 32%, #000 70%, transparent 72%);
    mask-image: radial-gradient(circle, transparent 24%, #000 32%, #000 70%, transparent 72%);
    animation: radarSweep 3.2s linear infinite;
    z-index: 1;
    pointer-events: none;
  }

  /* Counter-Rotating SVG Telemetry Orbits */
  .orbit-svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 2;
  }

  .orbit-ccw {
    animation: radarSweepReverse 9.5s linear infinite;
  }

  .orbit-cw {
    animation: radarSweep 5.2s linear infinite;
    filter: drop-shadow(0 0 6px rgba(168, 85, 247, 0.55));
  }

  /* Ring 1: Inner active prism chamber */
  .ring-1 {
    width: 50%;
    height: 50%;
    border: 1.5px solid rgba(192, 132, 252, 0.78);
    box-shadow: 0 8px 28px rgba(99, 102, 241, 0.34), inset 0 0 20px rgba(168, 85, 247, 0.24);
    z-index: 3;
    overflow: hidden;
    animation: innerRingPulse 2.4s ease-in-out infinite alternate;
  }

  .ring-core-glow {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.22) 0%, rgba(6, 182, 212, 0.08) 58%, transparent 82%);
  }

  /* Horizontal Laser Scan Line sweeping across the inner prism chamber */
  .prism-scan-laser {
    position: absolute;
    left: 8%;
    right: 8%;
    top: 12%;
    height: 2px;
    border-radius: var(--radius-sm, 8px);
    background: linear-gradient(90deg, transparent, #06b6d4 22%, #ffffff 50%, #c084fc 78%, transparent);
    box-shadow: 0 2px 12px rgba(6, 182, 212, 0.75);
    animation: laserScanSweep 2.2s cubic-bezier(0.45, 0, 0.55, 1) infinite;
    z-index: 6;
  }

  /* Ring 2: Middle concentric circle */
  .ring-2 {
    width: 72%;
    height: 72%;
    border: 1px solid rgba(147, 51, 234, 0.38);
    z-index: 1;
    animation: midRingBreathe 3s ease-in-out infinite alternate;
  }

  /* Ring 3: Outer perimeter */
  .ring-3 {
    width: 96%;
    height: 96%;
    border: 1px solid rgba(139, 92, 246, 0.22);
    z-index: 1;
  }

  /* Dual staggered sonar pulses */
  .ring-outer-pulse {
    width: 50%;
    height: 50%;
    border: 1.5px solid rgba(168, 85, 247, 0.58);
    border-radius: 50%;
    animation: sonarWave 3s cubic-bezier(0.16, 1, 0.3, 1) infinite;
    z-index: 1;
    opacity: 0;
  }

  .ring-outer-pulse.delayed {
    border-color: rgba(6, 182, 212, 0.45);
    animation-delay: 1.5s;
  }

  /* Center 3D Isometric Cube Container */
  .iso-cube-container {
    position: relative;
    z-index: 5;
    width: 28%;
    height: 28%;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: prismGyroFloat 3.6s ease-in-out infinite;
  }

  .spectra-iso-cube {
    width: 100%;
    height: 100%;
    filter: drop-shadow(0 4px 14px rgba(168, 85, 247, 0.65));
  }

  .prism-facet {
    animation: facetRefract 2.4s ease-in-out infinite;
  }
  .facet-top { animation-delay: 0s; }
  .facet-left { animation-delay: 0.8s; }
  .facet-right { animation-delay: 1.6s; }

  .inner-diamond {
    transform-origin: 50px 43px;
    animation: diamondCorePulse 1.8s ease-in-out infinite alternate;
  }

  .hex-energy-runner {
    stroke-dasharray: 56 186;
    animation: hexTraceRun 2.4s linear infinite;
  }

  /* Active File Chip */
  .doc-target-chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    max-width: min(460px, 90vw);
    padding: 5px 14px;
    margin-bottom: 12px;
    border-radius: var(--radius-lg, 20px);
    background: rgba(99, 102, 241, 0.14);
    border: 1px solid rgba(129, 140, 248, 0.34);
    color: var(--primary-soft-text-hover, #c7d2fe);
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 12px;
    font-weight: 600;
  }

  .live-scan-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent, #06b6d4);
    flex-shrink: 0;
    animation: liveDotBlink 1.2s ease-in-out infinite alternate;
  }

  .doc-target-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Typography */
  .loading-title {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 20px;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: var(--text-main, #f8fafc);
    line-height: 1.3;
  }

  .compact .loading-title {
    font-size: 18px;
  }

  .loading-status {
    font-family: var(--font-th, 'Prompt', sans-serif);
    color: var(--text-muted, #94a3b8);
    font-size: 14px;
    margin: 0 0 20px 0;
    max-width: 540px;
    line-height: 1.55;
  }

  .compact .loading-status {
    font-size: 14px;
    margin-bottom: 16px;
  }

  /* Progress Telemetry Box */
  .progress-telemetry-box {
    width: 100%;
    max-width: 460px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .progress-bar-container {
    width: 100%;
    height: 8px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: var(--radius-lg, 20px);
    overflow: hidden;
    position: relative;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--primary, #6366f1), var(--secondary, #a855f7), var(--accent, #06b6d4));
    background-size: 200% 100%;
    border-radius: var(--radius-lg, 20px);
    position: relative;
    overflow: hidden;
    transition: width 0.35s cubic-bezier(0.16, 1, 0.3, 1);
    animation: gradientShift 2.5s ease infinite;
  }

  .progress-shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent 0%,
      rgba(255, 255, 255, 0.42) 50%,
      transparent 100%
    );
    transform: translateX(-100%);
    animation: barShimmer 1.8s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  }

  .progress-meta-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    font-size: 12px;
  }

  .elapsed-badge {
    font-family: var(--font-th, 'Prompt', sans-serif);
    color: var(--text-muted, #94a3b8);
    font-variant-numeric: tabular-nums;
  }

  .progress-pct-label {
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 12px;
    font-weight: 700;
    color: var(--primary-soft-text-hover, #c7d2fe);
    font-variant-numeric: tabular-nums;
  }

  /* Pipeline Stage Pills */
  .stage-track {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 18px;
    max-width: 620px;
  }

  .stage-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: var(--radius-lg, 20px);
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--glass-border, rgba(255, 255, 255, 0.08));
    color: var(--text-dim, #8494aa);
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 12px;
    font-weight: 500;
    transition: border-color 0.2s ease, background-color 0.2s ease, color 0.2s ease;
  }

  .stage-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.6;
  }

  .stage-pill.is-done {
    background: rgba(16, 185, 129, 0.12);
    border-color: rgba(16, 185, 129, 0.34);
    color: var(--success-soft-text, #6ee7b7);
  }

  .stage-pill.is-active {
    background: rgba(99, 102, 241, 0.18);
    border-color: rgba(168, 85, 247, 0.52);
    color: var(--text-main, #f8fafc);
    font-weight: 600;
  }

  .stage-pill.is-active .stage-dot {
    background: var(--accent, #06b6d4);
    opacity: 1;
    animation: liveDotBlink 0.9s ease-in-out infinite alternate;
  }

  /* Stop Scan Action Button (Spectra Obsidian Rose-Alert Discipline) */
  .cancel-action-wrap {
    margin-top: 24px;
    display: flex;
    justify-content: center;
  }

  .btn-stop-scan {
    min-height: 40px;
    padding: 0 20px;
    border-radius: var(--radius-md, 12px);
    background: rgba(244, 63, 94, 0.12);
    border: 1px solid rgba(244, 63, 94, 0.42);
    color: var(--danger-soft-text, #fda4af);
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 14px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
  }

  .btn-stop-scan:hover:not(:disabled) {
    background: var(--danger-solid, #be123c);
    border-color: var(--danger-solid, #be123c);
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(190, 18, 60, 0.4);
  }

  .btn-stop-scan:active:not(:disabled) {
    transform: translateY(0);
  }

  .btn-stop-scan:focus-visible {
    outline: 2px solid var(--danger-soft-text, #fda4af);
    outline-offset: 2px;
  }

  .btn-stop-scan:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Keyframe Animations */
  @keyframes prismGyroFloat {
    0% {
      transform: translateY(2px) rotate(-3.5deg) scale(0.98);
    }
    50% {
      transform: translateY(-6px) rotate(3.5deg) scale(1.04);
    }
    100% {
      transform: translateY(2px) rotate(-3.5deg) scale(0.98);
    }
  }

  @keyframes facetRefract {
    0%, 100% {
      opacity: 0.35;
    }
    50% {
      opacity: 1;
    }
  }

  @keyframes diamondCorePulse {
    0% {
      transform: scale(0.94);
      opacity: 0.72;
    }
    100% {
      transform: scale(1.06);
      opacity: 1;
    }
  }

  @keyframes hexTraceRun {
    from {
      stroke-dashoffset: 242;
    }
    to {
      stroke-dashoffset: 0;
    }
  }

  @keyframes laserScanSweep {
    0% {
      transform: translateY(0);
      opacity: 0.25;
    }
    15% {
      opacity: 1;
    }
    50% {
      transform: translateY(88px);
      opacity: 1;
    }
    85% {
      opacity: 1;
    }
    100% {
      transform: translateY(0);
      opacity: 0.25;
    }
  }

  @keyframes innerRingPulse {
    0% {
      border-color: rgba(129, 140, 248, 0.65);
    }
    100% {
      border-color: rgba(6, 182, 212, 0.85);
    }
  }

  @keyframes midRingBreathe {
    0% {
      transform: scale(0.96);
      opacity: 0.55;
    }
    100% {
      transform: scale(1.03);
      opacity: 1;
    }
  }

  @keyframes sonarWave {
    0% {
      transform: scale(0.92);
      opacity: 0.78;
    }
    60% {
      opacity: 0.32;
    }
    100% {
      transform: scale(2);
      opacity: 0;
    }
  }

  @keyframes radarSweep {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @keyframes radarSweepReverse {
    from {
      transform: rotate(360deg);
    }
    to {
      transform: rotate(0deg);
    }
  }

  @keyframes gradientShift {
    0% {
      background-position: 0% 50%;
    }
    50% {
      background-position: 100% 50%;
    }
    100% {
      background-position: 0% 50%;
    }
  }

  @keyframes barShimmer {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(180%);
    }
  }

  @keyframes liveDotBlink {
    from {
      opacity: 0.45;
    }
    to {
      opacity: 1;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .radar-beam,
    .orbit-ccw,
    .orbit-cw,
    .ring-1,
    .ring-2,
    .ring-outer-pulse,
    .prism-scan-laser,
    .iso-cube-container,
    .inner-diamond,
    .hex-energy-runner,
    .progress-fill,
    .progress-shimmer,
    .live-scan-dot,
    .stage-pill.is-active .stage-dot {
      animation: none !important;
    }
    .ring-outer-pulse,
    .prism-scan-laser,
    .progress-shimmer {
      opacity: 0;
    }
    .btn-stop-scan:hover:not(:disabled) {
      transform: none;
    }
  }
</style>
