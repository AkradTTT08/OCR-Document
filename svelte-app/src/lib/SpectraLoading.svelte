<script>
  export let title = "กำลังประมวลผล...";
  export let status = "";
  export let progressPct = null;
  export let size = "default"; // 'default' | 'compact' | 'large'
</script>

<div class="spectra-loading-wrap {size}">
  <div class="radar-arena">
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
      <svg class="spectra-iso-cube" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#a855f7" flood-opacity="0.8" />
          </filter>
          <linearGradient id="facetGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#a855f7" stop-opacity="0.3" />
            <stop offset="100%" stop-color="#6366f1" stop-opacity="0.1" />
          </linearGradient>
        </defs>

        <!-- Inner Top Diamond Facet Fill -->
        <polygon points="50,33 69,44 50,55 31,44" fill="url(#facetGrad)" />

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

  {#if progressPct !== null && progressPct !== undefined}
    <div class="progress-bar-container">
      <div class="progress-fill" style="width: {progressPct}%"></div>
    </div>
    <div class="progress-pct-label">{progressPct}%</div>
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
    text-align: center;
    position: relative;
    user-select: none;
  }

  .spectra-loading-wrap.compact {
    padding: 20px 10px;
  }

  /* Radar Arena & Concentric Rings */
  .radar-arena {
    position: relative;
    width: 260px;
    height: 260px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 28px;
  }

  .compact .radar-arena {
    width: 200px;
    height: 200px;
    margin-bottom: 18px;
  }

  .large .radar-arena {
    width: 320px;
    height: 320px;
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
    width: 130px;
    height: 130px;
    border: 2px solid #a855f7;
    box-shadow: 0 0 24px rgba(168, 85, 247, 0.45), inset 0 0 18px rgba(168, 85, 247, 0.25);
    z-index: 2;
    animation: innerRingPulse 2.8s ease-in-out infinite alternate;
  }

  .compact .ring-1 {
    width: 100px;
    height: 100px;
  }

  .large .ring-1 {
    width: 160px;
    height: 160px;
  }

  .ring-core-glow {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(168, 85, 247, 0.15) 0%, rgba(99, 102, 241, 0.05) 60%, transparent 80%);
  }

  /* Ring 2: Middle concentric circle */
  .ring-2 {
    width: 190px;
    height: 190px;
    border: 1.5px solid rgba(147, 51, 234, 0.45);
    z-index: 1;
    animation: midRingBreathe 3.5s ease-in-out infinite alternate;
  }

  .compact .ring-2 {
    width: 145px;
    height: 145px;
  }

  .large .ring-2 {
    width: 235px;
    height: 235px;
  }

  /* Ring 3: Outer concentric circle */
  .ring-3 {
    width: 250px;
    height: 250px;
    border: 1px solid rgba(139, 92, 246, 0.25);
    z-index: 1;
  }

  .compact .ring-3 {
    width: 190px;
    height: 190px;
  }

  .large .ring-3 {
    width: 310px;
    height: 310px;
  }

  /* Outer expanding sonar wave pulse */
  .ring-outer-pulse {
    width: 130px;
    height: 130px;
    border: 1.5px solid rgba(168, 85, 247, 0.6);
    border-radius: 50%;
    animation: sonarWave 3s cubic-bezier(0.1, 0.7, 0.3, 1) infinite;
    z-index: 1;
    opacity: 0;
  }

  .compact .ring-outer-pulse {
    width: 100px;
    height: 100px;
  }

  .large .ring-outer-pulse {
    width: 160px;
    height: 160px;
  }

  /* Radar scanner line */
  .radar-scanner {
    position: absolute;
    width: 250px;
    height: 250px;
    border-radius: 50%;
    border-top: 2px solid rgba(192, 132, 252, 0.6);
    border-right: 2px solid transparent;
    border-bottom: 2px solid transparent;
    border-left: 2px solid transparent;
    animation: radarSweep 4s linear infinite;
    z-index: 1;
  }

  .compact .radar-scanner {
    width: 190px;
    height: 190px;
  }

  .large .radar-scanner {
    width: 310px;
    height: 310px;
  }

  /* Center 3D Isometric Cube Container */
  .iso-cube-container {
    position: relative;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: cubeFloat 3s ease-in-out infinite alternate;
  }

  .spectra-iso-cube {
    width: 68px;
    height: 68px;
    filter: drop-shadow(0 0 14px rgba(168, 85, 247, 0.85)) drop-shadow(0 0 3px rgba(255, 255, 255, 0.9));
    transition: transform 0.3s ease;
  }

  .compact .spectra-iso-cube {
    width: 52px;
    height: 52px;
  }

  .large .spectra-iso-cube {
    width: 86px;
    height: 86px;
  }

  /* Typography */
  .loading-title {
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 10px 0;
    background: linear-gradient(135deg, #ffffff 30%, #d8b4fe 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.01em;
  }

  .compact .loading-title {
    font-size: 18px;
  }

  .loading-status {
    color: #94a3b8;
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
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 999px;
    overflow: hidden;
    position: relative;
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.4);
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #9333ea, #6366f1, #38bdf8);
    background-size: 200% 100%;
    border-radius: 999px;
    box-shadow: 0 0 12px rgba(147, 51, 234, 0.8);
    transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    animation: gradientShift 2.5s ease infinite;
  }

  .progress-pct-label {
    margin-top: 8px;
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
</style>
