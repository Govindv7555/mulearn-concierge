/* ============================================================
   µLearn Concierge — Two-State Controller (SCENE & CHAT)
   Seamless WebGL Intro & Time-Based Transition System
   ============================================================ */

import * as THREE from '../vendor/three.module.js';
import {
  sceneState,
  initScene,
  renderScene,
  resizeScene,
  updateIdle,
  updateLogoLift,
  getHandoffMetrics,
  updateParticleMorph,
  computeScreenCameraTargets,
  getScreenViewportMetrics,
  verifyStandLaptopClearance,
  verifyHeadsetClearance,
  verifyWorkspacePenetrations
} from './scene.js';

// Application States
export const AppState = {
  SCENE: 'SCENE',
  TRANSITIONING: 'TRANSITIONING',
  CHAT: 'CHAT'
};

export let currentState = AppState.SCENE;

let lenis = null;
let masterTimeline = null;
let scrollTriggerInstance = null;
let isReducedMotion = false;
let animFrameId = null;
let isLoopRunning = false;

// Expose hooks for automated tests & inspection immediately
if (typeof window !== 'undefined') {
  window.__sceneState = sceneState;
  window.__computeScreenCameraTargets = computeScreenCameraTargets;
  window.__getScreenViewportMetrics = getScreenViewportMetrics;
  window.__verifyStandLaptopClearance = verifyStandLaptopClearance;
  window.__verifyHeadsetClearance = verifyHeadsetClearance;
  window.__verifyWorkspacePenetrations = verifyWorkspacePenetrations;
  window.__updateLogoLift = updateLogoLift;
  window.__getHandoffMetrics = getHandoffMetrics;
  window.__updateParticleMorph = updateParticleMorph;
  window.__resizeScene = resizeScene;
  window.__getAppState = () => currentState;
  window.__isRenderLoopRunning = () => isLoopRunning;
  window.__swapToChat = () => swapToChat();
  window.__swapToScene = () => swapToScene();
}

// Camera animated state proxy
const camProxy = {
  x: 0,
  y: 0,
  z: 7.5,
  targetX: 0,
  targetY: 0,
  targetZ: 0,
  upX: 0,
  upY: 1,
  upZ: 0
};

// Particle animation proxy
const particleProxy = {
  progress: 0,
  opacity: 0
};

/**
 * Check WebGL capability
 */
function isWebGLAvailable() {
  try {
    const canvas = document.createElement('canvas');
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext('webgl') || canvas.getContext('experimental-webgl'))
    );
  } catch (e) {
    return false;
  }
}

/**
 * Main Initialization
 */
document.addEventListener('DOMContentLoaded', () => {
  const introCanvas = document.getElementById('introCanvas');
  const heroOverlay = document.getElementById('heroOverlay');
  const flashOverlay = document.getElementById('flashOverlay');
  const btnSkipIntro = document.getElementById('btnSkipIntro');
  const btnBackToScene = document.getElementById('btnBackToScene');
  const chatSection = document.getElementById('chat');

  // Check prefers-reduced-motion
  isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Direct skip conditions: reduced motion, no WebGL, direct #chat hash, or stored preference
  let shouldDirectChat = false;
  if (!isWebGLAvailable() || isReducedMotion || !introCanvas) {
    shouldDirectChat = true;
  }
  if (window.location.hash === '#chat') {
    shouldDirectChat = true;
  }
  try {
    if (sessionStorage.getItem('mulearn_skip_intro') === '1') {
      shouldDirectChat = true;
    }
  } catch (e) {}

  if (shouldDirectChat) {
    enterChatImmediate();
    setupChatInteraction(chatSection, btnBackToScene);
    return;
  }

  // 1. Initialize Three.js scene
  initScene(introCanvas);

  // 2. Setup Lenis Smooth Scroll (autoRaf: false, driven by gsap.ticker)
  if (typeof window.Lenis !== 'undefined') {
    lenis = new window.Lenis({
      autoRaf: false,
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      touchMultiplier: 1.5,
      infinite: false
    });

    window.lenis = lenis;

    lenis.on('scroll', window.ScrollTrigger ? window.ScrollTrigger.update : null);

    window.gsap.ticker.add((time) => {
      lenis.raf(time * 1000);
    });
    window.gsap.ticker.lagSmoothing(0);
  }

  // 3. Register ScrollTrigger & build master timeline (Phases 1 to 5)
  if (window.gsap && window.ScrollTrigger) {
    window.gsap.registerPlugin(window.ScrollTrigger);
    buildScrollTimeline(heroOverlay, flashOverlay, btnSkipIntro, chatSection);
  }

  // 4. Start Render Loop
  startAnimationLoop();

  // 5. Window Resize Handler
  window.addEventListener('resize', () => {
    resizeScene(window.innerWidth, window.innerHeight);
    if (window.ScrollTrigger) {
      window.ScrollTrigger.refresh();
    }
  });

  // 6. Navigation Controls & Replay Listeners
  setupNavigation(btnSkipIntro, btnBackToScene, chatSection);
  setupChatInteraction(chatSection, btnBackToScene);

  // Expose hooks for automated tests & inspection
  window.__lenis = lenis;
  window.__masterTimeline = masterTimeline;
  window.__scrollTrigger = scrollTriggerInstance;
  window.__getAppState = () => currentState;
  window.__isRenderLoopRunning = () => isLoopRunning;
  window.__swapToChat = () => swapToChat(flashOverlay, chatSection);
  window.__swapToScene = () => swapToScene();
});

/**
 * Build continuous, reversible master GSAP scroll timeline (Phases 1 to 5)
 */
function buildScrollTimeline(heroOverlay, flashOverlay, btnSkipIntro, chatSection) {
  const masterTL = window.gsap.timeline({
    scrollTrigger: {
      trigger: '#introSpacer',
      start: 'top top',
      end: 'bottom bottom',
      scrub: 1, // ~1 second smoothing
      onUpdate: (self) => {
        // Trigger time-based swap to chat when scroll reaches swap threshold at end of phase 5
        const swapProg = masterTL.labels && masterTL.labels.swapThreshold ? (masterTL.labels.swapThreshold / masterTL.duration()) : (80 / 88);
        if (currentState === AppState.SCENE && self.progress >= swapProg) {
          swapToChat(flashOverlay, chatSection);
        }
      }
    }
  });

  masterTimeline = masterTL;
  scrollTriggerInstance = masterTL.scrollTrigger;
  window.__masterTimeline = masterTL;
  window.__scrollTrigger = scrollTriggerInstance;

  // -------------------------------------------------------------
  // LABELS (deadzone removed: shifted by 12 timeline units earlier)
  // -------------------------------------------------------------
  masterTL.addLabel('hero', 0);
  masterTL.addLabel('approachStart', 0);
  masterTL.addLabel('rotationStart', 0);

  // -------------------------------------------------------------
  // PHASE 1: HERO OVERLAY: Fade out "Scroll to enter" hint over first ~200px (t: 0 -> 3.7)
  // -------------------------------------------------------------
  masterTL.to(heroOverlay, {
    opacity: 0,
    ease: 'power1.out',
    duration: 3.7
  }, 0);

  // -------------------------------------------------------------
  // PHASE 2: APPROACH & ROTATION (0 - 18)
  // -------------------------------------------------------------
  masterTL.to(camProxy, {
    x: 0,
    y: 0.25,
    z: 3.6,
    targetX: 0,
    targetY: 0,
    targetZ: 0,
    ease: 'power2.inOut',
    duration: 18
  }, 0);

  if (sceneState.logoGroup) {
    // Immediate, eased response over first 120px (~2.22 timeline units) giving ~6.5 degrees
    const immediateRad = - (6.5 * Math.PI / 180);
    const dur120 = 2.22;

    masterTL.to(sceneState.logoGroup.rotation, {
      y: immediateRad,
      ease: 'power1.out',
      duration: dur120
    }, 0);

    masterTL.to(sceneState.logoGroup.rotation, {
      y: -Math.PI * 0.52,
      ease: 'power2.inOut',
      duration: 18 - dur120
    }, dur120);

    masterTL.to(sceneState.logoGroup.scale, {
      x: 1.25,
      y: 1.25,
      z: 1.25,
      ease: 'power2.inOut',
      duration: 18
    }, 0);
  }

  // LIFT WAVE: Starts just after rotation reaches ~60% (progress 10.8) and finishes when rotation completes (18.0)
  masterTL.addLabel('liftStart', 10.8);
  const liftProxy = { value: 0.0 };
  masterTL.to(liftProxy, {
    value: 1.0,
    duration: 7.2,
    ease: 'none',
    onUpdate: () => {
      updateLogoLift(liftProxy.value);
    }
  }, 10.8);

  masterTL.addLabel('rotationEnd', 18);
  masterTL.addLabel('liftEnd', 18);

  // -------------------------------------------------------------
  // PHASE 3: PIXEL-TO-OBJECT PARTICLE MORPH (18 - 50)
  // -------------------------------------------------------------
  masterTL.addLabel('phase3Start', 18);
  masterTL.addLabel('swirlStart', 18);

  const morphProxy = { p: 0.0 };
  masterTL.to(morphProxy, {
    p: 1.0,
    duration: 32,
    ease: 'none',
    onUpdate: () => {
      updateParticleMorph(morphProxy.p);
    }
  }, 18);

  // Camera pulls back to elevated cinematic view of workspace (desk fills ~70% of viewport width)
  masterTL.to(camProxy, {
    x: -0.12,
    y: 1.25,
    z: 1.62,
    targetX: 0.06,
    targetY: 0.88,
    targetZ: -0.05,
    ease: 'power2.inOut',
    duration: 32
  }, 18);

  // Desk lamp is a prop only in bright morning studio: stays OFF with zero emission
  if (sceneState.lampLight) {
    sceneState.lampLight.intensity = 0;
  }

  masterTL.addLabel('phase3End', 50);

  // -------------------------------------------------------------
  // PHASE 4: LAPTOP 3/4 VIEW (50 - 66) & PHASE 5: SCREEN ZOOM IN (66 - 77)
  // -------------------------------------------------------------
  masterTL.addLabel('phase4Start', 50);

  // Dynamically computed from laptop screen mesh world position, normal and up vector
  const screenTargets = computeScreenCameraTargets(sceneState.camera, sceneState.camera?.aspect);
  const p4 = screenTargets ? screenTargets.phase4 : { x: 0.28, y: 1.05, z: 0.62, targetX: 0.05, targetY: 0.96, targetZ: -0.19, upX: 0, upY: 1, upZ: 0 };
  const p5 = screenTargets ? screenTargets.phase5 : { x: 0.05, y: 0.98, z: 0.05, targetX: 0.05, targetY: 0.98, targetZ: -0.19, upX: 0, upY: 0.98, upZ: -0.17 };

  // Phase 4: Camera glides to a 3/4 view of the laptop
  masterTL.to(camProxy, {
    x: p4.x,
    y: p4.y,
    z: p4.z,
    targetX: p4.targetX,
    targetY: p4.targetY,
    targetZ: p4.targetZ,
    upX: p4.upX !== undefined ? p4.upX : 0,
    upY: p4.upY !== undefined ? p4.upY : 1,
    upZ: p4.upZ !== undefined ? p4.upZ : 0,
    ease: 'power2.inOut',
    duration: 16
  }, 50);

  masterTL.addLabel('phase4End', 66);
  masterTL.addLabel('phase5Start', 66);

  // Phase 5: Camera moves along screenNormal to point screenCenter + normal * d
  // with camera up vector matching the screen's up vector
  masterTL.to(camProxy, {
    x: p5.x,
    y: p5.y,
    z: p5.z,
    targetX: p5.targetX,
    targetY: p5.targetY,
    targetZ: p5.targetZ,
    upX: p5.upX !== undefined ? p5.upX : 0,
    upY: p5.upY !== undefined ? p5.upY : 1,
    upZ: p5.upZ !== undefined ? p5.upZ : 0,
    ease: 'power2.inOut',
    duration: 11
  }, 66);

  masterTL.addLabel('screenZoomEnd', 77);
  masterTL.addLabel('phase5End', 77);

  // Crossfade to white ONLY in the last 8% of Phase 5 (progress 78.64 to 80.0)
  // Ensures screen texture is crisp and 100% visible throughout Phase 5
  if (sceneState.screenFadeMesh) {
    masterTL.to(sceneState.screenFadeMesh.material, {
      opacity: 1,
      ease: 'power2.in',
      duration: 1.36
    }, 78.64);
  }

  masterTL.addLabel('swapThreshold', 80);

  // Ensure master timeline duration is strictly 88 (matching 0-88 scroll progress over 528vh)
  masterTL.set({}, {}, 88);
  masterTL.addLabel('end', 88);
}

/**
 * TIME-BASED SWAP: SCENE -> CHAT (2.4s total)
 * Flash in: 0.8s | Hold: 0.6s | Flash out: 1.0s
 */
export function swapToChat(flashOverlay, chatSection) {
  if (currentState !== AppState.SCENE) return;
  currentState = AppState.TRANSITIONING;

  if (!flashOverlay) flashOverlay = document.getElementById('flashOverlay');
  if (!chatSection) chatSection = document.getElementById('chat');

  // Input lock during transition
  const inputShield = createInputShield();
  flashOverlay.style.display = 'block';
  flashOverlay.style.opacity = '0';

  const startTime = performance.now();
  window.__transitionMetrics = {
    type: 'toChat',
    startTime,
    fadeInDuration: 0.8,
    holdDuration: 0.6,
    fadeOutDuration: 1.0,
    totalDuration: 2.4,
    fadedInTime: null,
    holdTime: null,
    completedTime: null
  };

  const swapTL = window.gsap.timeline({
    onComplete: () => {
      currentState = AppState.CHAT;
      window.__chatAppearedTime = performance.now();
      if (window.__transitionMetrics) window.__transitionMetrics.completedTime = performance.now();
      flashOverlay.style.display = 'none';
      flashOverlay.style.opacity = '0';
      removeInputShield(inputShield);

      // Focus message input
      const msgInput = document.getElementById('messageInput');
      if (msgInput) msgInput.focus({ preventScroll: true });
    }
  });

  // 1. Flash fades in to full white over 0.8s (t: 0 -> 0.8s)
  swapTL.to(flashOverlay, {
    opacity: 1,
    duration: 0.8,
    ease: 'power2.in'
  }, 0);

  swapTL.call(() => {
    if (window.__transitionMetrics) window.__transitionMetrics.fadedInTime = performance.now();
  }, null, 0.8);

  // 2. Holds fully white for 0.6s (action taken at midpoint t = 1.1s)
  swapTL.call(() => {
    if (window.__transitionMetrics) window.__transitionMetrics.holdTime = performance.now();

    // Stop 3D render loop
    stopAnimationLoop();

    // Stop Lenis
    if (lenis) lenis.stop();

    // Disable ScrollTrigger
    if (scrollTriggerInstance) {
      scrollTriggerInstance.disable(false);
    } else if (window.ScrollTrigger) {
      window.ScrollTrigger.getAll().forEach(st => st.disable(false));
    }

    // Hide scene wrapper, canvas, spacer, skip button
    const introContainer = document.getElementById('introContainer');
    const introCanvas = document.getElementById('introCanvas');
    const introSpacer = document.getElementById('introSpacer');
    const btnSkipIntro = document.getElementById('btnSkipIntro');
    if (introContainer) introContainer.style.display = 'none';
    if (introCanvas) introCanvas.style.display = 'none';
    if (introSpacer) introSpacer.style.display = 'none';
    if (btnSkipIntro) btnSkipIntro.style.display = 'none';

    // Scroll window to top
    window.scrollTo(0, 0);

    // Lock html and body behind chat
    document.documentElement.classList.add('chat-active');
    document.body.classList.add('chat-active');

    // Show #chat as clean full-viewport layer
    if (chatSection) {
      chatSection.classList.add('chat-active');
      chatSection.scrollTop = 0;
    }
    const msgList = document.getElementById('chatMessages');
    if (msgList) {
      msgList.scrollTop = 0;
    }
  }, null, 1.1);

  // 3. Flash fades out over 1.0s (starts at t = 1.4s, ends at t = 2.4s)
  swapTL.to(flashOverlay, {
    opacity: 0,
    duration: 1.0,
    ease: 'power2.out'
  }, 1.4);
}

/**
 * TIME-BASED REPLAY: CHAT -> SCENE (2.4s total)
 */
export function swapToScene() {
  if (currentState !== AppState.CHAT) return;
  currentState = AppState.TRANSITIONING;

  const flashOverlay = document.getElementById('flashOverlay');
  const chatSection = document.getElementById('chat');

  const inputShield = createInputShield();
  flashOverlay.style.display = 'block';
  flashOverlay.style.opacity = '0';

  const startTime = performance.now();
  window.__transitionMetrics = {
    type: 'toScene',
    startTime,
    fadeInDuration: 0.8,
    holdDuration: 0.6,
    fadeOutDuration: 1.0,
    totalDuration: 2.4,
    fadedInTime: null,
    holdTime: null,
    completedTime: null
  };

  const replayTL = window.gsap.timeline({
    onComplete: () => {
      currentState = AppState.SCENE;
      if (window.__transitionMetrics) window.__transitionMetrics.completedTime = performance.now();
      flashOverlay.style.display = 'none';
      flashOverlay.style.opacity = '0';
      removeInputShield(inputShield);
    }
  });

  // 1. Flash fades in to white over 0.8s (t: 0 -> 0.8s)
  replayTL.to(flashOverlay, {
    opacity: 1,
    duration: 0.8,
    ease: 'power2.in'
  }, 0);

  replayTL.call(() => {
    if (window.__transitionMetrics) window.__transitionMetrics.fadedInTime = performance.now();
  }, null, 0.8);

  // 2. Holds white for 0.6s (swap scene back in at midpoint t = 1.1s)
  replayTL.call(() => {
    if (window.__transitionMetrics) window.__transitionMetrics.holdTime = performance.now();

    // Hide #chat
    if (chatSection) {
      chatSection.classList.remove('chat-active');
    }
    document.documentElement.classList.remove('chat-active');
    document.body.classList.remove('chat-active');

    // Restore scene elements
    const introContainer = document.getElementById('introContainer');
    const introCanvas = document.getElementById('introCanvas');
    const introSpacer = document.getElementById('introSpacer');
    const btnSkipIntro = document.getElementById('btnSkipIntro');
    if (introContainer) introContainer.style.display = '';
    if (introCanvas) introCanvas.style.display = '';
    if (introSpacer) introSpacer.style.display = '';
    if (btnSkipIntro) {
      btnSkipIntro.style.display = '';
      btnSkipIntro.style.opacity = '1';
      btnSkipIntro.style.pointerEvents = 'auto';
    }

    // Re-enable ScrollTrigger
    if (scrollTriggerInstance) {
      scrollTriggerInstance.enable();
    } else if (window.ScrollTrigger) {
      window.ScrollTrigger.getAll().forEach(st => st.enable());
    }
    if (window.ScrollTrigger) {
      window.ScrollTrigger.refresh();
    }

    // Position timeline at progress recomputed from labels (screenZoomEnd + 1.0)
    const st = scrollTriggerInstance || (window.ScrollTrigger && window.ScrollTrigger.getAll()[0]);
    const tl = masterTimeline;
    const replayLabelPos = tl && tl.labels && tl.labels.screenZoomEnd !== undefined ? (tl.labels.screenZoomEnd + 1.0) : 78.0;
    const replayProgress = tl ? (replayLabelPos / tl.duration()) : (78.0 / 88.0);
    const targetScroll = st ? (st.start + replayProgress * (st.end - st.start)) : Math.round(replayProgress * 4752);
    window.scrollTo(0, targetScroll);

    if (lenis) {
      lenis.start();
      lenis.resize();
      lenis.scrollTo(targetScroll, { immediate: true, force: true });
    }

    if (st) {
      if (st.scroll) st.scroll(targetScroll);
      if (st.animation) st.animation.progress(replayProgress);
      st.update();
    }

    // Resume Three.js render loop
    startAnimationLoop();
  }, null, 1.1);

  // 3. Flash fades out over 1.0s (starts at t = 1.4s, ends at t = 2.4s)
  replayTL.to(flashOverlay, {
    opacity: 0,
    duration: 1.0,
    ease: 'power2.out'
  }, 1.4);
}

/**
 * Direct entry to CHAT state (Skip Intro, #chat hash, reduced motion, no WebGL)
 */
export function enterChatImmediate() {
  currentState = AppState.CHAT;
  window.__chatAppearedTime = performance.now();
  stopAnimationLoop();
  if (lenis) lenis.stop();
  if (scrollTriggerInstance) {
    scrollTriggerInstance.disable(false);
  } else if (window.ScrollTrigger) {
    window.ScrollTrigger.getAll().forEach(st => st.disable(false));
  }

  const introContainer = document.getElementById('introContainer');
  const introCanvas = document.getElementById('introCanvas');
  const introSpacer = document.getElementById('introSpacer');
  const btnSkipIntro = document.getElementById('btnSkipIntro');
  const flashOverlay = document.getElementById('flashOverlay');
  if (introContainer) introContainer.style.display = 'none';
  if (introCanvas) introCanvas.style.display = 'none';
  if (introSpacer) introSpacer.style.display = 'none';
  if (btnSkipIntro) btnSkipIntro.style.display = 'none';
  if (flashOverlay) {
    flashOverlay.style.display = 'none';
    flashOverlay.style.opacity = '0';
  }

  document.documentElement.classList.add('chat-active');
  document.body.classList.add('chat-active');
  const chatSection = document.getElementById('chat');
  if (chatSection) {
    chatSection.classList.add('chat-active');
    chatSection.scrollTop = 0;
  }
  const msgList = document.getElementById('chatMessages');
  if (msgList) {
    msgList.scrollTop = 0;
  }

  const msgInput = document.getElementById('messageInput');
  if (msgInput) msgInput.focus({ preventScroll: true });
}

/**
 * Temporary shield to block inputs during the 2.4s swap
 */
function createInputShield() {
  const shield = document.createElement('div');
  shield.id = 'transitionInputShield';
  shield.style.position = 'fixed';
  shield.style.inset = '0';
  shield.style.zIndex = '999999';
  shield.style.pointerEvents = 'all';
  shield.style.cursor = 'wait';
  document.body.appendChild(shield);
  return shield;
}

function removeInputShield(shield) {
  if (shield && shield.parentNode) {
    shield.parentNode.removeChild(shield);
  }
}

/**
 * Interpolate gold transformation particles
 */
function updateParticles(progress, opacity) {
  if (!sceneState.particlesGroup) return;

  const { points, geometry, initialPositions, targetPositions, count, material } = sceneState.particlesGroup;
  material.opacity = opacity;

  const posAttr = geometry.attributes.position;
  const arr = posAttr.array;

  for (let i = 0; i < count; i++) {
    const idx = i * 3;
    const ix = initialPositions[idx];
    const iy = initialPositions[idx + 1];
    const iz = initialPositions[idx + 2];

    const tx = targetPositions[idx];
    const ty = targetPositions[idx + 1];
    const tz = targetPositions[idx + 2];

    // Lerp with slight arc
    const arcHeight = Math.sin(progress * Math.PI) * 0.4;
    arr[idx] = ix + (tx - ix) * progress;
    arr[idx + 1] = iy + (ty - iy) * progress + arcHeight;
    arr[idx + 2] = iz + (tz - iz) * progress;
  }

  posAttr.needsUpdate = true;
}

/**
 * Render frame loop controls
 */
let clock = new THREE.Clock();

export function startAnimationLoop() {
  if (isLoopRunning) return;
  isLoopRunning = true;
  clock.start();

  function tick() {
    if (!isLoopRunning) return;
    animFrameId = requestAnimationFrame(tick);

    const elapsed = clock.getElapsedTime();
    updateIdle(elapsed);

    if (sceneState.camera) {
      sceneState.camera.position.set(camProxy.x, camProxy.y, camProxy.z);
      if (camProxy.upX !== undefined && camProxy.upY !== undefined && camProxy.upZ !== undefined) {
        sceneState.camera.up.set(camProxy.upX, camProxy.upY, camProxy.upZ);
      }
      sceneState.camera.lookAt(camProxy.targetX, camProxy.targetY, camProxy.targetZ);
    }

    renderScene();
  }

  tick();
}

export function stopAnimationLoop() {
  isLoopRunning = false;
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
}

/**
 * Navigation handlers: Skip Intro and Back to Scene
 */
function setupNavigation(btnSkipIntro, btnBackToScene, chatSection) {
  if (btnSkipIntro) {
    btnSkipIntro.addEventListener('click', () => {
      try {
        sessionStorage.setItem('mulearn_skip_intro', '1');
      } catch (e) {}
      enterChatImmediate();
    });
  }

  if (btnBackToScene) {
    btnBackToScene.addEventListener('click', () => {
      try {
        sessionStorage.removeItem('mulearn_skip_intro');
      } catch (e) {}
      swapToScene();
    });
  }
}

/**
 * Accidental Replay Dead Zone & Deliberate Replay Controller
 * Requirements:
 * 1. Casual wheel-up and swipe-down outside the box do nothing (no flash, no scene change).
 * 2. Back to 3D scene button remains the primary, always-working way back.
 * 3. Deliberate gesture requires ALL of:
 *    - Chat page is at top (scrollTop <= 0, window.scrollY <= 0)
 *    - Pointer is NOT over the chat card (.chat-panel)
 *    - Armed flag: >= 2.5s passed since chat appeared
 *    - Wheel: accumulated wheel-up delta reaches >= 1200 within a rolling 900ms window
 *      OR touch: swipe-down distance >= 220px within 600ms starting at top
 *    - Progress bar: 2px gold line fills 0-100%, resets after 600ms of no input. Replay only when 100%.
 *    - 1.5s cooldown after any failed attempt; reset accumulation when clicking, typing, or scrolling inside chat card.
 * 4. Wheel over chat card never triggers anything (scrolls messages).
 * 5. Keyboard Home or PageUp does not trigger replay.
 */
function setupChatInteraction(chatSection, btnBackToScene) {
  if (!chatSection) return;

  const chatCard = document.querySelector('.chat-panel');
  const progressBar = document.getElementById('replayProgressBar');

  let wheelHistory = [];
  let resetTimer = null;
  let cooldownUntil = 0;
  let lastPointerX = -1;
  let lastPointerY = -1;

  if (typeof window !== 'undefined') {
    window.__getReplayCooldownUntil = () => cooldownUntil;
    window.__setReplayCooldownUntil = (t) => { cooldownUntil = t; };
    window.__getWheelHistory = () => wheelHistory;
  }

  // Track mouse position
  window.addEventListener('mousemove', (e) => {
    lastPointerX = e.clientX;
    lastPointerY = e.clientY;
  }, { passive: true });

  function updateProgressBar(progress) {
    if (!progressBar) return;
    if (progress > 0) {
      progressBar.classList.add('active');
      progressBar.style.width = Math.min(100, Math.round(progress * 100)) + '%';
    } else {
      progressBar.style.width = '0%';
      progressBar.classList.remove('active');
    }
  }

  function resetAccumulation() {
    wheelHistory = [];
    if (resetTimer) {
      clearTimeout(resetTimer);
      resetTimer = null;
    }
    updateProgressBar(0);
  }

  function triggerFailedCooldown() {
    resetAccumulation();
    cooldownUntil = performance.now() + 1500;
  }

  // Reset accumulation when user clicks, types, or scrolls inside chat card
  if (chatCard) {
    chatCard.addEventListener('pointerdown', resetAccumulation, { passive: true });
    chatCard.addEventListener('input', resetAccumulation, { passive: true });
    chatCard.addEventListener('scroll', resetAccumulation, { passive: true, capture: true });
    const msgList = document.getElementById('chatMessages');
    if (msgList) {
      msgList.addEventListener('scroll', resetAccumulation, { passive: true });
    }
  }

  // Keyboard: Home or PageUp never triggers replay
  window.addEventListener('keydown', (e) => {
    if (currentState === AppState.CHAT) {
      if (e.key === 'Home' || e.key === 'PageUp') {
        resetAccumulation();
      }
    }
  }, { passive: true });

  function isPointerOverCard(clientX, clientY, target) {
    if (!chatCard) return false;
    if (target && (chatCard === target || chatCard.contains(target))) {
      return true;
    }
    const rect = chatCard.getBoundingClientRect();
    const x = clientX !== undefined && clientX >= 0 ? clientX : lastPointerX;
    const y = clientY !== undefined && clientY >= 0 ? clientY : lastPointerY;
    if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
      return true;
    }
    return false;
  }

  // WHEEL EVENT LISTENER
  window.addEventListener('wheel', (e) => {
    if (currentState !== AppState.CHAT) return;

    // Condition 4: Wheel events over chat card never trigger replay
    if (isPointerOverCard(e.clientX, e.clientY, e.target)) {
      resetAccumulation();
      return;
    }

    const now = performance.now();

    // Check 1.5s cooldown
    if (now < cooldownUntil) {
      return;
    }

    // Condition 3a: Armed flag — at least 2.5s since chat appeared
    const appearedTime = window.__chatAppearedTime || 0;
    if (now - appearedTime < 2500) {
      return;
    }

    // Condition 3a: Chat page must be at top (scrollTop <= 0 and window.scrollY <= 0)
    if (chatSection.scrollTop > 0 || window.scrollY > 0) {
      resetAccumulation();
      return;
    }

    // Scrolling down (deltaY >= 0)? Reset and exit
    if (e.deltaY >= 0) {
      if (wheelHistory.length > 0) {
        triggerFailedCooldown();
      }
      return;
    }

    // e.deltaY < 0 is upward scroll. Positive magnitude:
    const delta = -e.deltaY;
    wheelHistory.push({ time: now, delta });

    // Condition 3b: Rolling 900 ms window
    wheelHistory = wheelHistory.filter(item => now - item.time <= 900);
    const accumulated = wheelHistory.reduce((sum, item) => sum + item.delta, 0);

    // Condition 3c: Progress bar (0 to 100%)
    const progress = Math.min(1.0, accumulated / 1200);
    updateProgressBar(progress);

    // Reset after 600 ms of no input and apply 1.5s cooldown
    if (resetTimer) clearTimeout(resetTimer);
    resetTimer = setTimeout(() => {
      if (wheelHistory.length > 0) {
        triggerFailedCooldown();
      }
    }, 600);

    // Trigger replay only when reaching 100% (accumulated >= 1200)
    if (accumulated >= 1200) {
      e.preventDefault();
      resetAccumulation();
      swapToScene();
    }
  }, { passive: false });

  // TOUCH SWIPE-DOWN GESTURE (mobile)
  let touchStartY = 0;
  let touchStartTime = 0;
  let touchActive = false;

  window.addEventListener('touchstart', (e) => {
    if (currentState !== AppState.CHAT) return;
    const now = performance.now();

    if (now < cooldownUntil) return;
    const appearedTime = window.__chatAppearedTime || 0;
    if (now - appearedTime < 2500) return;
    if (chatSection.scrollTop > 0) return;

    if (e.touches && e.touches.length === 1) {
      const touch = e.touches[0];
      if (isPointerOverCard(touch.clientX, touch.clientY, e.target)) {
        touchActive = false;
        resetAccumulation();
        return;
      }
      touchStartY = touch.clientY;
      touchStartTime = now;
      touchActive = true;
    }
  }, { passive: true });

  window.addEventListener('touchmove', (e) => {
    if (!touchActive || currentState !== AppState.CHAT) return;
    const now = performance.now();
    if (now < cooldownUntil) return;

    if (e.touches && e.touches.length === 1) {
      const elapsed = now - touchStartTime;
      // Must be within 600 ms window
      if (elapsed > 600) {
        touchActive = false;
        triggerFailedCooldown();
        return;
      }

      const touch = e.touches[0];
      const deltaY = touch.clientY - touchStartY;

      if (deltaY > 0) {
        const progress = Math.min(1.0, deltaY / 220);
        updateProgressBar(progress);

        if (deltaY >= 220 && elapsed <= 600) {
          touchActive = false;
          resetAccumulation();
          swapToScene();
        }
      }
    }
  }, { passive: true });

  window.addEventListener('touchend', () => {
    if (touchActive) {
      touchActive = false;
      triggerFailedCooldown();
    }
  }, { passive: true });
}
