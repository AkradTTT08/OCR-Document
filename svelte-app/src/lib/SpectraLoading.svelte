<script>
  export let title = "กำลังประมวลผล...";
  export let status = "";
  export let progressPct = null;
  export let size = "default"; // 'default' | 'compact' | 'large'

  const facetGradId = `spectra-facet-${Math.random().toString(36).slice(2, 8)}`;

  $: clampedProgress =
    progressPct !== null && progressPct !== undefined
      ? Math.max(0, Math.min(100, Math.round(Number(progressPct) || 0)))
      : null;
</script>

<div class="spectra-loading-wrap {size}" role="status" aria-live="polite">
  <div class="radar-arena" aria-hidden="true">
    <!-- Outer concentric sonar rings -->
    <div class="concentric-ring ring-outer-pulse"></div>
    <div class="concentric-ring ring-3"></div>
    <div class="concentric-ring ring-2"></div>
    
    <!-- Rotating subtle scan radar sweep -->
    <div class="radar-scanner"></div>

    <!-- Inner active ring with glow -->
    <div class="concentric-ring ring-1">
      <div class="ring-core-glow"></div>
    </div>

    <!-- Center 3D Isometric Wireframe Cube Logo -->
    <div class="iso-cube-container">
      <svg class="spectra-iso-cube" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <linearGradient id={facetGradId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#a855f7" stop-opacity="0.3" />
            <stop offset="100%" stop-color="#6366f1" stop-opacity="0.1" />
          </linearGradient>
        </defs>

        <!-- Inner Top Diamond Facet Fill -->
        <polygon points="50,33 69,44 50,55 31,44" fill={`url(#${facetGradId})`} />

        <!-- Outer Hexagon Frame -->
        <polygon 
          points="50,10 85,30 85,70 50,90 15,70 15,30" 
          stroke="#ffffff" 
          stroke-width="4.5" 
          stroke-linejoin="round" 
          stroke-linecap="round"
        />

        <!-- Inner Diamond Frame -->
        <polygon 
          points="50,33 69,44 50,55 31,44" 
          stroke="#ffffff" 
          stroke-width="4.5" 
          stroke-linejoin="round" 
          stroke-linecap="round"
        />

        <!-- Radial Connecting Struts -->
        <line x1="50" y1="10" x2="50" y2="33" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" />
        <line x1="85" y1="30" x2="69" y2="44" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" />
        <line x1="15" y1="30" x2="31" y2="44" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" />
        <line x1="50" y1="55" x2="50" y2="90" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" />
        <line x1="69" y1="44" x2="85" y2="70" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" />
        <line x1="31" y1="44" x2="15" y2="70" stroke="#ffffff" stroke-width="4.5" stroke-linecap="round" />
      </svg>
    </div>
  </div>

  {#if title}
    <h2 class="loading-title">{title}</h2>
  {/if}

  {#if status}
    <p class="loading-status">{status}</p>
  {/if}

  {#if clampedProgress !== null}
    <div
      class="progress-bar-container"
      role="progressbar"
      aria-valuenow={clampedProgress}
      aria-valuemin="0"
      aria-valuemax="100"
      aria-label={title || 'ความคืบหน้าการประมวลผล'}
    >
      <div class="progress-fill" style="width: {clampedProgress}%"></div>
    </div>
    <div class="progress-pct-label">{clampedProgress}%</div>
  {/if}
</div>

<style>
  .spectra-loading-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    width: 100%;
    max-width: 100%;
    overflow: hidden;
    text-align: center;
    position: relative;
    user-select: none;
    box-sizing: border-box;
  }

  .spectra-loading-wrap.compact {
    padding: 20px 10px;
  }

  /* Radar Arena & Concentric Rings */
  .radar-arena {
    position: relative;
    width: min(260px, 75vw);
    height: min(260px, 75vw);
    max-width: min(260px, 75vw);
    aspect-ratio: 1 / 1;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 28px;
    flex-shrink: 0;
  }

  .compact .radar-arena {
    width: min(200px, 68vw);
    height: min(200px, 68vw);
    max-width: min(200px, 68vw);
    margin-bottom: 18px;
  }

  .large .radar-arena {
    width: min(320px, 80vw);
    height: min(320px, 80vw);
    max-width: min(320px, 80vw);
    margin-bottom: 36px;
  }

  /* Concentric Rings */
  .concentric-ring {
    position: absolute;
    border-radius: 50%;
    box-sizing: border-box;
    pointer-events: none;
  }

  /* Ring 1: Inner active circle */
  .ring-1 {
    width: 50%;
    height: 50%;
    border: 2px solid var(--secondary, #a855f7);
    box-shadow: 0 0 24px rgba(168, 85, 247, 0.45), inset 0 0 18px rgba(168, 85, 247, 0.25);
    z-index: 2;
    animation: innerRingPulse 2.8s ease-in-out infinite alternate;
  }

  .ring-core-glow {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.15) 0%, rgba(99, 102, 241, 0.05) 60%, transparent 80%);
  }

  /* Ring 2: Middle concentric circle */
  .ring-2 {
    width: 73%;
    height: 73%;
    border: 1.5px solid rgba(147, 51, 234, 0.45);
    z-index: 1;
    animation: midRingBreathe 3.5s ease-in-out infinite alternate;
  }

  /* Ring 3: Outer concentric circle */
  .ring-3 {
    width: 96%;
    height: 96%;
    border: 1px solid rgba(139, 92, 246, 0.25);
    z-index: 1;
  }

  /* Outer expanding sonar wave pulse */
  .ring-outer-pulse {
    width: 50%;
    height: 50%;
    border: 1.5px solid rgba(168, 85, 247, 0.6);
    border-radius: 50%;
    animation: sonarWave 3s cubic-bezier(0.1, 0.7, 0.3, 1) infinite;
    z-index: 1;
    opacity: 0;
  }

  /* Radar scanner line */
  .radar-scanner {
    position: absolute;
    width: 96%;
    height: 96%;
    border-radius: 50%;
    border-top: 2px solid rgba(192, 132, 252, 0.6);
    border-right: 2px solid transparent;
    border-bottom: 2px solid transparent;
    border-left: 2px solid transparent;
    animation: radarSweep 4s linear infinite;
    z-index: 1;
  }

  /* Center 3D Isometric Cube Container */
  .iso-cube-container {
    position: relative;
    z-index: 5;
    width: 26%;
    height: 26%;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: cubeFloat 3s ease-in-out infinite alternate;
  }

  .spectra-iso-cube {
    width: 100%;
    height: 100%;
    filter: drop-shadow(0 0 14px rgba(168, 85, 247, 0.85)) drop-shadow(0 0 3px rgba(255, 255, 255, 0.9));
    transition: transform 0.3s ease;
  }

  /* Typography */
  .loading-title {
    font-family: var(--font-th, 'Prompt', sans-serif);
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 10px 0;
    color: var(--text-main, #f8fafc);
    letter-spacing: -0.01em;
  }

  .compact .loading-title {
    font-size: 18px;
  }

  .loading-status {
    font-family: var(--font-th, 'Prompt', sans-serif);
    color: var(--text-muted, #94a3b8);
    font-size: 14.5px;
    margin: 0 0 24px 0;
    max-width: 540px;
    line-height: 1.5;
  }

  .compact .loading-status {
    font-size: 13px;
    margin-bottom: 16px;
  }

  /* Progress Bar */
  .progress-bar-container {
    width: 100%;
    max-width: 440px;
    height: 7px;
    background: var(--glass-border, rgba(255, 255, 255, 0.08));
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 999px;
    overflow: hidden;
    position: relative;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.4);
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--secondary, #a855f7), var(--primary, #6366f1), var(--accent, #06b6d4));
    background-size: 200% 100%;
    border-radius: 999px;
    box-shadow: 0 0 12px rgba(147, 51, 234, 0.8);
    transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    animation: gradientShift 2.5s ease infinite;
  }

  .progress-pct-label {
    margin-top: 8px;
    font-family: var(--font-en, 'Outfit', sans-serif);
    font-size: 12px;
    font-weight: 600;
    color: #c084fc;
    font-variant-numeric: tabular-nums;
  }

  /* Keyframe Animations */
  @keyframes cubeFloat {
    0% {
      transform: translateY(0px) scale(1);
    }
    100% {
      transform: translateY(-6px) scale(1.03);
    }
  }

  @keyframes innerRingPulse {
    0% {
      box-shadow: 0 0 16px rgba(168, 85, 247, 0.35), inset 0 0 10px rgba(168, 85, 247, 0.15);
      border-color: rgba(168, 85, 247, 0.8);
    }
    100% {
      box-shadow: 0 0 32px rgba(168, 85, 247, 0.75), inset 0 0 24px rgba(168, 85, 247, 0.4);
      border-color: #c084fc;
    }
  }

  @keyframes midRingBreathe {
    0% {
      transform: scale(0.97);
      opacity: 0.6;
    }
    100% {
      transform: scale(1.02);
      opacity: 1;
    }
  }

  @keyframes sonarWave {
    0% {
      transform: scale(0.85);
      opacity: 0.8;
    }
    50% {
      opacity: 0.4;
    }
    100% {
      transform: scale(2.05);
      opacity: 0;
    }
  }

  @keyframes radarSweep {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
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

  @media (prefers-reduced-motion: reduce) {
    .ring-1,
    .ring-2,
    .ring-outer-pulse,
    .radar-scanner,
    .iso-cube-container,
    .progress-fill {
      animation: none !important;
    }
    .ring-outer-pulse {
      opacity: 0;
    }
  }
</style>
