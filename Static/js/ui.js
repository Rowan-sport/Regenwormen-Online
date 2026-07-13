/**
 * ui.js — Shared UI utilities for Pickomino
 */

window.UI = (function () {

  function toast(msg, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = msg;
    container.appendChild(t);
    setTimeout(() => t.remove(), duration + 100);
  }

  function diceLabel(value) {
    return value === 5 ? '🪱' : String(value);
  }

  function tileWorms(n) {
    if (n <= 24) return 1;
    if (n <= 28) return 2;
    if (n <= 32) return 3;
    return 4;
  }

  function wormDots(count) {
    return '🪱'.repeat(count);
  }

  function animateDice(diceEls) {
    diceEls.forEach((el, i) => {
      setTimeout(() => {
        el.classList.add('rolling');
        setTimeout(() => el.classList.remove('rolling'), 420);
      }, i * 60);
    });
  }

  function showModal(title, body, buttons = []) {
    // Remove any existing modal
    const existing = document.getElementById('modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-box">
        <h2 class="display text-xl mb-4">${title}</h2>
        <div class="mb-4">${body}</div>
        <div class="flex justify-center gap-4 wrap" id="modal-btns"></div>
      </div>`;
    document.body.appendChild(overlay);

    const btnContainer = overlay.querySelector('#modal-btns');
    buttons.forEach(({ label, cls, action }) => {
      const btn = document.createElement('button');
      btn.className = `btn ${cls || 'btn-primary'} gaze-btn`;
      btn.setAttribute('data-gaze', 'true');
      btn.innerHTML = `<span class="dwell-bar"></span>${label}`;
      btn.addEventListener('click', () => { overlay.remove(); action && action(); });
      btnContainer.appendChild(btn);
    });

    return overlay;
  }

  function hideModal() {
    const m = document.getElementById('modal-overlay');
    if (m) m.remove();
  }

  function confetti(count = 30) {
    const colors = ['#FF6B35','#4ECDC4','#FFE66D','#6BCF7F','#FF4757','#A855F7'];
    for (let i = 0; i < count; i++) {
      setTimeout(() => {
        const dot = document.createElement('div');
        dot.style.cssText = `
          position:fixed;
          left:${Math.random()*100}vw;
          top:-20px;
          width:${8+Math.random()*14}px;
          height:${8+Math.random()*14}px;
          background:${colors[Math.floor(Math.random()*colors.length)]};
          border-radius:${Math.random()>0.5?'50%':'3px'};
          z-index:9999;
          pointer-events:none;
          animation: confettiFall ${1.2+Math.random()*1.8}s ease-in forwards;
        `;
        document.body.appendChild(dot);
        setTimeout(() => dot.remove(), 3500);
      }, i * 70);
    }

    if (!document.getElementById('confetti-style')) {
      const s = document.createElement('style');
      s.id = 'confetti-style';
      s.textContent = `
        @keyframes confettiFall {
          to { transform: translateY(110vh) rotate(${360+Math.random()*360}deg); opacity:0; }
        }`;
      document.head.appendChild(s);
    }
  }

  return { toast, diceLabel, tileWorms, wormDots, animateDice, showModal, hideModal, confetti };
})();
