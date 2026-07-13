/**
 * tobii.js — Tobii Dynavox eye/head tracking integration
 * ========================================================
 * Priority 1: Tobii SDK (via window.EyeTracking or Tobii Web SDK)
 * Priority 2: WebGazer.js (webcam-based, if loaded)
 * Priority 3: Mouse pointer fallback (always works for testing)
 *
 * All gaze-aware elements just need class="gaze-btn" or data-gaze="true".
 * Dwell time, radius, and cursor settings are loaded from /api/config.
 */

window.TobiiController = (function () {
  let cfg = {
    dwellTimeMs: 10000,
    dwellRadiusPx: 80,
    gazeCursorVisible: true,
    gazeCursorColor: '#FF6B35',
    fallbackToMouse: true,
    smoothingFactor: 0.3,
    fixationRadiusPx: 60,
    enabled: true
  };

  let gazeCursor = null;
  let dwellRing = null;
  let currentTarget = null;
  let dwellStart = null;
  let dwellTimer = null;
  let dwellAnimation = null;
  let smoothX = 0, smoothY = 0;
  let mode = 'mouse'; // 'tobii' | 'webgazer' | 'mouse'
  let activeListeners = new Set();

  // ── Init ────────────────────────────────────────────────────────────────

  async function init() {
    // Load config from server
    try {
      const res = await fetch('/api/config');
      const data = await res.json();
      const a = data.accessibility || {};
      const t = data.tobii || {};
      cfg.dwellTimeMs       = a.dwell_time_ms       || cfg.dwellTimeMs;
      cfg.dwellRadiusPx     = a.dwell_radius_px     || cfg.dwellRadiusPx;
      cfg.gazeCursorVisible = t.gaze_cursor_visible !== undefined ? t.gaze_cursor_visible : true;
      cfg.gazeCursorColor   = t.gaze_cursor_color   || cfg.gazeCursorColor;
      cfg.fallbackToMouse   = t.fallback_to_mouse   !== undefined ? t.fallback_to_mouse : true;
      cfg.smoothingFactor   = t.smoothing_factor    || cfg.smoothingFactor;
      cfg.fixationRadiusPx  = t.fixation_radius_px  || cfg.fixationRadiusPx;
      cfg.enabled           = t.enabled             !== undefined ? t.enabled : true;

      // Apply CSS variable for dwell time so buttons animate correctly
      document.documentElement.style.setProperty('--dwell-ms', cfg.dwellTimeMs + 'ms');
    } catch (e) {
      console.warn('[Tobii] Could not load config, using defaults.', e);
    }

    gazeCursor = document.getElementById('gaze-cursor');
    dwellRing  = document.getElementById('dwell-ring');

    if (gazeCursor && cfg.gazeCursorColor) {
      gazeCursor.style.background = cfg.gazeCursorColor + 'CC';
    }

    if (!cfg.enabled) {
      console.log('[Tobii] Tracking disabled in config.');
      return;
    }

    // Try Tobii Web SDK first
    if (window.EyeTracking && typeof window.EyeTracking.getGazeData === 'function') {
      mode = 'tobii';
      console.log('[Tobii] Using Tobii Web SDK ✓');
      _startTobiiSDK();
    }
    // Try WebGazer (webcam)
    else if (window.webgazer) {
      mode = 'webgazer';
      console.log('[Tobii] Using WebGazer (webcam) ✓');
      _startWebGazer();
    }
    // Fallback: mouse
    else if (cfg.fallbackToMouse) {
      mode = 'mouse';
      console.log('[Tobii] No eye tracker found — using mouse fallback ✓');
      _startMouseFallback();
    }

    _setupDwellForAllButtons();
  }

  // ── Tobii SDK ────────────────────────────────────────────────────────────

  function _startTobiiSDK() {
    if (gazeCursor) gazeCursor.classList.add('active');

    window.EyeTracking.startTracking((gazeData) => {
      if (!gazeData || !gazeData.x || !gazeData.x.length) return;
      const rawX = gazeData.x[0] * window.innerWidth;
      const rawY = gazeData.y[0] * window.innerHeight;
      _processGaze(rawX, rawY);
    });
  }

  // ── WebGazer ─────────────────────────────────────────────────────────────

  function _startWebGazer() {
    if (gazeCursor) gazeCursor.classList.add('active');

    webgazer.setGazeListener((data) => {
      if (!data) return;
      _processGaze(data.x, data.y);
    }).begin();

    webgazer.showPredictionPoints(false);
    webgazer.showVideoPreview(false);
  }

  // ── Mouse fallback ────────────────────────────────────────────────────────

  function _startMouseFallback() {
    // Show a subtle cursor indicator only if gaze cursor is enabled
    document.addEventListener('mousemove', (e) => {
      smoothX = e.clientX;
      smoothY = e.clientY;
      if (gazeCursor && cfg.gazeCursorVisible) {
        // In mouse mode we don't move the gaze cursor — native cursor is visible.
      }
      _checkDwellTargets(e.clientX, e.clientY);
    });
  }

  // ── Core gaze processor ───────────────────────────────────────────────────

  function _processGaze(rawX, rawY) {
    // Exponential smoothing
    smoothX = smoothX + cfg.smoothingFactor * (rawX - smoothX);
    smoothY = smoothY + cfg.smoothingFactor * (rawY - smoothY);

    // Move gaze cursor
    if (gazeCursor && cfg.gazeCursorVisible) {
      gazeCursor.style.left = smoothX + 'px';
      gazeCursor.style.top  = smoothY + 'px';
    }

    _checkDwellTargets(smoothX, smoothY);
  }

  // ── Dwell engine ──────────────────────────────────────────────────────────

  function _checkDwellTargets(x, y) {
    const els = document.querySelectorAll('[data-gaze="true"]:not(:disabled):not([data-gaze-disabled="true"])');
    let found = null;
    let minDist = Infinity;

    for (const el of els) {
      const rect = el.getBoundingClientRect();
      const cx = rect.left + rect.width  / 2;
      const cy = rect.top  + rect.height / 2;
      const dist = Math.hypot(x - cx, y - cy);
      const threshold = Math.max(cfg.fixationRadiusPx, rect.width / 2, rect.height / 2);

      if (dist < threshold && dist < minDist) {
        minDist = dist;
        found = el;
      }
    }

    if (found !== currentTarget) {
      _cancelDwell();
      currentTarget = found;
      if (found) {
        _startDwell(found);
      }
    }
  }

  function _startDwell(el) {
    dwellStart = performance.now();

    // Visual ring
    if (dwellRing) {
      const rect = el.getBoundingClientRect();
      dwellRing.style.left   = (rect.left + rect.width  / 2) + 'px';
      dwellRing.style.top    = (rect.top  + rect.height / 2) + 'px';
      dwellRing.style.width  = Math.max(rect.width, rect.height) + 20 + 'px';
      dwellRing.style.height = Math.max(rect.width, rect.height) + 20 + 'px';
      dwellRing.style.marginLeft = '-' + (Math.max(rect.width, rect.height) + 20) / 2 + 'px';
      dwellRing.style.marginTop  = '-' + (Math.max(rect.width, rect.height) + 20) / 2 + 'px';
      dwellRing.classList.add('active');
    }

    // Button dwell bar animation
    el.classList.add('dwelling');

    // Trigger after dwell time
    dwellTimer = setTimeout(() => {
      _fireDwell(el);
    }, cfg.dwellTimeMs);
  }

  function _cancelDwell() {
    clearTimeout(dwellTimer);
    if (currentTarget) {
      currentTarget.classList.remove('dwelling');
    }
    if (dwellRing) dwellRing.classList.remove('active');
    dwellStart = null;
  }

  function _fireDwell(el) {
    _cancelDwell();
    currentTarget = null;

    // Prevent rapid re-fire
    el.setAttribute('data-gaze-disabled', 'true');
    setTimeout(() => el.removeAttribute('data-gaze-disabled'), 600);

    el.click();

    // Haptic if available
    if (navigator.vibrate) navigator.vibrate(80);
  }

  // ── Setup gaze on all buttons ─────────────────────────────────────────────

  function _setupDwellForAllButtons() {
    // Also observe DOM mutations so dynamically added buttons work
    const observer = new MutationObserver(() => _markGazeElements());
    observer.observe(document.body, { childList: true, subtree: true });
    _markGazeElements();
  }

  function _markGazeElements() {
    // Auto-tag anything with data-gaze or .gaze-btn
    document.querySelectorAll('.gaze-btn, [data-gaze="true"]').forEach(el => {
      if (!el.hasAttribute('data-gaze')) el.setAttribute('data-gaze', 'true');
    });
    // Also tag .btn buttons if not already tagged
    document.querySelectorAll('.btn:not([data-gaze])').forEach(el => {
      el.setAttribute('data-gaze', 'true');
    });
  }

  // ── Public API ───────────────────────────────────────────────────────────

  function setDwellTime(ms) {
    cfg.dwellTimeMs = ms;
    document.documentElement.style.setProperty('--dwell-ms', ms + 'ms');
  }

  function getMode()     { return mode; }
  function getConfig()   { return { ...cfg }; }

  return { init, setDwellTime, getMode, getConfig };
})();

document.addEventListener('DOMContentLoaded', () => TobiiController.init());
