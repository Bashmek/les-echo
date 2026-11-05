/* Les Echo — pixel-MMORPG renderer.
 *
 * Loaded after game.js/world.js. It replaces the flat 1:1 overhead canvas with a
 * close, slightly lowered third-person camera, depth-sorted pixel sprites and a
 * layered combat-effects pass.  All simulation stays authoritative on the
 * server; this file only decides how the world is presented.
 */
(function () {
  'use strict';

  const TAU = Math.PI * 2;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const lerp = (a, b, t) => a + (b - a) * t;
  const easeOut = t => 1 - Math.pow(1 - Math.max(0, Math.min(1, t)), 3);
  const easeInOut = t => (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

  function seedOf(value) {
    let h = 2166136261;
    const str = String(value ?? '');
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0) / 4294967295;
  }

  /* ── low-level pixel helpers ─────────────────────────────────────────── */
  function P(c, x, y, w, h, col, alpha) {
    if (alpha !== undefined) { c.globalAlpha = alpha; }
    c.fillStyle = col; c.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
    if (alpha !== undefined) c.globalAlpha = 1;
  }
  function ell(c, x, y, rx, ry, col, rot) {
    c.fillStyle = col; c.beginPath(); c.ellipse(x, y, Math.max(.2, rx), Math.max(.2, ry), rot || 0, 0, TAU); c.fill();
  }
  function poly(c, pts, fill, stroke, lw) {
    c.beginPath(); c.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]);
    c.closePath();
    if (fill) { c.fillStyle = fill; c.fill(); }
    if (stroke) { c.strokeStyle = stroke; c.lineWidth = lw || 1; c.stroke(); }
  }
  function seg(c, x1, y1, x2, y2, col, lw, glowCol) {
    c.strokeStyle = col; c.lineWidth = lw || 1;
    if (glowCol) { c.shadowColor = glowCol; c.shadowBlur = 8; }
    c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
    if (glowCol) c.shadowBlur = 0;
  }
  function glow(c, x, y, r, col, alpha) {
    const g = c.createRadialGradient(x, y, 0, x, y, Math.max(1, r));
    g.addColorStop(0, col);
    g.addColorStop(.45, col + (alpha !== undefined ? '' : '88'));
    g.addColorStop(1, col + '00');
    c.save(); c.globalCompositeOperation = 'lighter';
    c.fillStyle = g; c.globalAlpha = alpha === undefined ? 1 : alpha;
    c.fillRect(x - r, y - r, r * 2, r * 2); c.restore();
  }
  function eye(c, x, y, r, tint, pupil) {
    c.save(); c.shadowColor = tint; c.shadowBlur = 7;
    ell(c, x, y, r, r * 1.06, '#10150f');
    ell(c, x + .2, y + .1, r * .62, r * .74, tint);
    if (pupil !== false) ell(c, x + .3, y + .2, r * .22, r * .55, '#1a1208');
    c.restore();
  }
  function label(c, text, x, y, col, size, weight) {
    c.font = `${weight || 'bold'} ${size || 10}px ui-monospace, "Courier New", monospace`;
    c.textAlign = 'center'; c.lineWidth = 3; c.strokeStyle = '#0b120e';
    c.strokeText(text, x, y); c.fillStyle = col || '#f4ecd8'; c.fillText(text, x, y);
    c.textAlign = 'left';
  }
  function vignetteAlpha() { return 1; }

  /* ── camera ──────────────────────────────────────────────────────────── */
  const VIEW = { zoom: 1.85, targetZoom: 1.85, lookY: 0, ready: false, shakeX: 0, shakeY: 0, hurt: 0, punch: 0, freeze: 0, lastFrame: 0 };
  const coarse = () => (typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches) ||
    document.body.classList.contains('is-mobile');
  function desiredZoom(w, h) {
    if (coarse()) return clamp(Math.min(w, h) / 290, 1, 1.4);
    return clamp(Math.min(w, h) / 410, 1.8, 2.35);
  }
  function extendCameraBounds(w, h) {
    const Z = VIEW.zoom, WS = typeof worldSize === 'function' ? worldSize() : { w: 2000, h: 1500 };
    const halfW = w / (2 * Z);
    const up = (h / 2 + VIEW.lookY) / Z, down = (h / 2 - VIEW.lookY) / Z;
    return { WS, Z, halfW, up, down };
  }
  /** Convert canvas-local pixels (relative to canvas top-left) to world units. */
  function screenToWorld(cx, cy) {
    const rect = canvas.getBoundingClientRect();
    const Z = VIEW.zoom || 1;
    return { x: cam.x + (cx - rect.width / 2) / Z, y: cam.y + (cy - rect.height / 2 - VIEW.lookY) / Z };
  }

  /* ── mob sprites ─────────────────────────────────────────────────────── */
  // Every model is drawn with its feet at (0,0), facing right before the
  // facing flip. `s` is the server hitbox size, so silhouettes stay honest.
  function drawMobModel(c, kind, s, t, seed, st) {
    const u = Math.max(.5, s / 20);
    const walk = st && st.walk || 0;
    const move = st && st.move || 0;
    const atk = st && st.atk || 0;
    const hurt = st && st.hurt || 0;
    c.save();
    c.scale(u, u);
    if (hurt > 0) c.filter = 'brightness(2.6) saturate(.35)';
    switch (kind) {
      case 'slime': drawSlime(c, t, seed, move); break;
      case 'wolf': drawWolf(c, t, seed, move, atk); break;
      case 'boar': drawBoar(c, t, seed, move, atk); break;
      case 'wisp': drawWisp(c, t, seed); break;
      case 'stone': drawStone(c, t, seed, move); break;
      case 'ashling': drawAshling(c, t, seed); break;
      case 'ashguard': drawAshguard(c, t, seed, move, atk); break;
      case 'colossus': drawColossus(c, t, seed, move, atk); break;
      case 'frost_wyrm': drawWyrm(c, t, seed, 'ice', atk); break;
      case 'echo_dragon': drawWyrm(c, t, seed, 'echo', atk); break;
      case 'rift_knight': drawRiftKnight(c, t, seed, move, atk); break;
      case 'void_wraith': drawWraith(c, t, seed); break;
      case 'astral_titan': drawTitan(c, t, seed, move, atk); break;
      case 'obsidian_sentinel': drawSentinel(c, t, seed, move, atk); break;
      case 'starseer': drawStarseer(c, t, seed); break;
      case 'ancient_warden': drawWarden(c, t, seed, move, atk); break;
      default: drawWolf(c, t, seed, move, atk);
    }
    if (hurt > 0) c.filter = 'none';
    c.restore();
  }

  function drawSlime(c, t, seed, move) {
    const sq = 1 + Math.sin(t * 3.4 + seed * 9) * .07 + Math.sin(t * 7.2 + seed) * .015;
    c.save();
    c.scale(1 / Math.sqrt(sq), sq);
    const bob = Math.abs(Math.sin(t * 4 + seed * 5)) * (move ? 2.4 : .8);
    c.translate(0, -bob);
    const body = c.createLinearGradient(0, -30, 0, 3);
    body.addColorStop(0, '#d4ff96'); body.addColorStop(.3, '#8ade63'); body.addColorStop(.72, '#4f9b4c'); body.addColorStop(1, '#2a5c30');
    c.fillStyle = body;
    c.beginPath();
    c.moveTo(-18, 0);
    c.bezierCurveTo(-22, -9, -18, -19, -9, -22);
    c.bezierCurveTo(-2, -27, 8, -25, 13, -17);
    c.bezierCurveTo(19, -12, 21, -5, 16, 0);
    c.bezierCurveTo(12, 4, 6, 1, 3, 4);
    c.bezierCurveTo(-1, 1, -8, 5, -12, 2);
    c.closePath(); c.fill();
    c.strokeStyle = '#1e3d22'; c.lineWidth = 1.6; c.stroke();
    // gooey rim light
    c.strokeStyle = '#eaffbd77'; c.lineWidth = 1.1;
    c.beginPath(); c.ellipse(-2, -13, 13, 8, -.15, Math.PI * 1.02, Math.PI * 1.72); c.stroke();
    // inner bubbles
    ell(c, -7, -8, 3.4, 2.1, '#f2ffcf77', -.6);
    ell(c, 6, -13, 2.4, 1.6, '#f2ffcf55', .4);
    ell(c, -2, -18, 4, 2.4, '#ffffff55');
    // narrowed predatory eyes
    c.save();
    c.fillStyle = '#152315';
    poly(c, [[-11, -12], [-4, -14], [-4, -9], [-9, -8]], '#152315');
    poly(c, [[2, -14], [9, -12], [7, -8], [1, -9]], '#152315');
    c.restore();
    c.save(); c.shadowColor = '#fff08a'; c.shadowBlur = 9;
    poly(c, [[-10, -11.6], [-5, -12.8], [-5, -9.8], [-9, -9.2]], '#fff08a');
    poly(c, [[3, -12.8], [8, -11.6], [6.4, -9.2], [2, -9.8]], '#fff08a');
    c.restore();
    c.fillStyle = '#1a2a18';
    poly(c, [[-9, -11.6], [-7, -12.2], [-7, -10.2]], '#1a2a18');
    poly(c, [[4.4, -12.2], [6.6, -11.6], [5.4, -10.2]], '#1a2a18');
    // jagged grin
    c.fillStyle = '#1d3a1c';
    c.beginPath(); c.moveTo(-6, -3); c.quadraticCurveTo(0, 1, 7, -4); c.quadraticCurveTo(1, -1, -6, -3); c.fill();
    poly(c, [[-4, -3], [-2, 1.4], [0, -2]], '#f4ffd8', null, 0);
    poly(c, [[2, -2], [4, 1], [5.4, -2.4]], '#f4ffd8', null, 0);
    // drips
    ell(c, -13, -1, 2.6, 4, '#4f9b4c');
    ell(c, 12, 0, 2, 3.2, '#3f8642');
    c.restore();
  }

  function drawWolf(c, t, seed, move, atk) {
    const gait = Math.sin(t * (move ? 11 : 3) + seed * 8);
    const legSwing = move ? gait * 4.6 : Math.sin(t * 2.2) * .35;
    c.save();
    // huge bushy tail, arcing low then up
    const tailWag = Math.sin(t * 3.4 + seed) * 4;
    c.strokeStyle = '#586a5e'; c.lineWidth = 6; c.lineCap = 'round';
    c.beginPath(); c.moveTo(-13, -19);
    c.bezierCurveTo(-24, -22, -30, -14 + tailWag * .5, -34, -24 + tailWag); c.stroke();
    c.strokeStyle = '#b9c6bc'; c.lineWidth = 3.4;
    c.beginPath(); c.moveTo(-14, -20);
    c.bezierCurveTo(-24, -22.5, -29, -16 + tailWag * .5, -33, -24 + tailWag); c.stroke();
    // long legs with claws
    for (let i = 0; i < 4; i++) {
      const lx = -12 + i * 8.4, ph = i % 2 ? legSwing : -legSwing;
      c.strokeStyle = '#2f3a33'; c.lineWidth = 2.6;
      c.beginPath(); c.moveTo(lx, -15); c.lineTo(lx + ph * .5, -7); c.lineTo(lx + ph * .9 - 1, -1); c.stroke();
      ell(c, lx + ph * .9 - 1, -.6, 2.8, 1.4, '#232c26');
      for (let k = 0; k < 2; k++) P(c, lx + ph * .9 - 2.6 + k * 3, -1.2, 1.4, 1, '#e8efe4');
    }
    // lean, high-shouldered body
    const body = c.createLinearGradient(0, -30, 0, -6);
    body.addColorStop(0, '#dbe6dc'); body.addColorStop(.32, '#a7b8ac'); body.addColorStop(.74, '#66786c'); body.addColorStop(1, '#3a4a40');
    c.fillStyle = body;
    c.beginPath();
    c.moveTo(-15, -14);
    c.quadraticCurveTo(-16, -24, -6, -26);
    c.quadraticCurveTo(2, -30, 10, -25);
    c.quadraticCurveTo(17, -22, 15, -14);
    c.quadraticCurveTo(9, -10, -1, -11);
    c.quadraticCurveTo(-11, -10, -15, -14);
    c.closePath(); c.fill();
    c.strokeStyle = '#28322b'; c.lineWidth = 1.5; c.stroke();
    // ragged back fur
    for (let i = 0; i < 7; i++) {
      const bx = -13 + i * 4.2;
      poly(c, [[bx, -24], [bx + 1.8, -31 - (i % 3) * 2.2], [bx + 3.4, -23]], i % 2 ? '#d6e2d8' : '#8fa196', '#3a473c', .7);
    }
    // chest ruff
    for (let i = 0; i < 3; i++) poly(c, [[11, -20], [14 - i, -16 + i * 2], [9, -14 + i]], '#c2d0c4');
    // neck into lowered head
    poly(c, [[5, -25], [14, -28], [21, -23], [18, -16], [8, -15]], '#c5d2c7', '#28322b', 1.2);
    c.save(); c.translate(20, -19); c.rotate(-.08);
    // skull
    c.beginPath();
    c.moveTo(-8, -6); c.quadraticCurveTo(-2, -10, 6, -7);
    c.quadraticCurveTo(13, -5, 15, 0); c.quadraticCurveTo(9, 1, 6, 3);
    c.quadraticCurveTo(-2, 6, -8, 2); c.closePath();
    c.fillStyle = '#d3ded4'; c.fill(); c.strokeStyle = '#28322b'; c.lineWidth = 1.3; c.stroke();
    // muzzle + open jaw
    poly(c, [[5, -1], [17, 0], [16, 3], [6, 3]], '#c0ccc1', '#28322b', 1);
    P(c, 15.4, 1.2, 2.6, 1.8, '#2a211a');
    poly(c, [[6, 3], [16, 3], [12, 6.6], [7, 6]], '#8a3a34', '#3a1a16', .8);
    poly(c, [[7, 6], [8, 9], [9.6, 6]], '#fff6df');
    poly(c, [[11, 6], [12.4, 8.6], [13.6, 6]], '#fff6df');
    poly(c, [[14, 2.6], [15.4, 5.6], [16.4, 2.4]], '#fff6df');
    // swept ears
    poly(c, [[-6, -6], [-11, -15], [-1, -8]], '#7d8f84', '#26302a', 1);
    poly(c, [[1, -8], [1, -16], [7, -7]], '#8fa196', '#26302a', 1);
    // angry brow + amber eye
    poly(c, [[-4, -4], [4, -6.4], [4, -3.4], [-3.6, -1.8]], '#1d2620');
    c.save(); c.shadowColor = '#ffc85e'; c.shadowBlur = 8;
    poly(c, [[-3.2, -4.2], [3.2, -5.8], [3.2, -3.6], [-3, -2.6]], '#ffc85e');
    c.restore();
    P(c, -.2, -4.4, .9, 2.4, '#1a0f04');
    c.restore();
    if (atk > 0) {
      c.save(); c.globalAlpha = Math.min(1, atk * 1.4);
      for (let i = 0; i < 4; i++) {
        c.strokeStyle = i % 2 ? '#ffe6b0' : '#ffb066'; c.lineWidth = 2;
        c.beginPath(); c.arc(30, -16, 6 + i * 5, -.8 + i * .1, .9); c.stroke();
      }
      c.restore();
    }
    c.restore();
  }

  function drawBoar(c, t, seed, move, atk) {
    const gait = Math.sin(t * (move ? 10 : 2.8) + seed * 6);
    c.save();
    for (let i = 0; i < 4; i++) {
      const lx = -12 + i * 8.4, ph = i % 2 ? gait : -gait;
      c.strokeStyle = '#4a3123'; c.lineWidth = 3.4;
      c.beginPath(); c.moveTo(lx, -13); c.lineTo(lx + ph * .7, -1); c.stroke();
      P(c, lx + ph * .7 - 2, -1, 4, 1.6, '#241811');
    }
    // mane spikes (bristles)
    for (let i = 0; i < 9; i++) {
      const sx = -14 + i * 3.4;
      poly(c, [[sx, -25], [sx + 1.6, -32 - (i % 3) * 2], [sx + 3, -24]], i % 2 ? '#c99060' : '#8a5c3a', '#3a2518', .7);
    }
    const body = c.createLinearGradient(0, -30, 0, -6);
    body.addColorStop(0, '#d3a274'); body.addColorStop(.4, '#9b6c48'); body.addColorStop(.8, '#6b452c'); body.addColorStop(1, '#452b1b');
    c.fillStyle = body;
    c.beginPath();
    c.moveTo(-16, -14);
    c.quadraticCurveTo(-19, -25, -8, -28);
    c.quadraticCurveTo(3, -31, 11, -26);
    c.quadraticCurveTo(17, -22, 16, -14);
    c.quadraticCurveTo(10, -9, -2, -10);
    c.quadraticCurveTo(-12, -9, -16, -14);
    c.closePath(); c.fill();
    c.strokeStyle = '#2e1d12'; c.lineWidth = 1.5; c.stroke();
    // hunched front shoulder
    ell(c, 8, -22, 10, 9, '#8a5c3a');
    ell(c, 4, -25, 6, 4, '#a97850');
    // head lowered
    c.save(); c.translate(16, -15); c.rotate(.12);
    poly(c, [[-6, -6], [3, -9], [10, -3], [8, 5], [-3, 7]], '#9a6b46', '#2e1d12', 1.4);
    poly(c, [[6, -2], [16, 1], [7, 6]], '#855a3a', '#2e1d12', 1.1);
    ell(c, 14, 2, 3, 2.4, '#5a3a26');
    // tusks, curved upward
    poly(c, [[10, 4], [17, 8], [16, -2], [12, 2]], '#f3e3bd', '#8a7752', .8);
    poly(c, [[7, 5], [11, 10], [9, 1]], '#f7ebc8', '#8a7752', .8);
    // red eye under heavy brow
    poly(c, [[-2, -4], [4, -5.4], [3.4, -2], [-1, -1.6]], '#20100a');
    c.save(); c.shadowColor = '#ff6a4a'; c.shadowBlur = 8;
    poly(c, [[-1.4, -3.6], [3.2, -4.8], [2.8, -2.4], [-1, -2.1]], '#ff7a5c');
    c.restore();
    c.restore();
    // dust puffs while charging
    if (move) {
      c.globalAlpha = .25;
      for (let i = 0; i < 3; i++) ell(c, -18 - i * 5 - (t * 30 + i * 9) % 14, -1, 4, 2.4, '#c8b090');
      c.globalAlpha = 1;
    }
    if (atk > 0) { c.globalAlpha = atk * .5; ell(c, 26, -12, 8, 4, '#ffb08a'); c.globalAlpha = 1; }
    c.restore();
  }

  function drawWisp(c, t, seed) {
    const bob = Math.sin(t * 2.6 + seed * 7) * 3;
    c.save(); c.translate(0, bob - 16);
    glow(c, 0, 0, 32, '#5ff2d8', .42);
    for (let i = 0; i < 8; i++) {
      const a = t * 2 + i * 1.1, r = 12 + Math.sin(t * 3 + i) * 4;
      ell(c, Math.cos(a) * r, Math.sin(a) * r * .7, 1.6, 1.6, i % 2 ? '#bffcf1' : '#6ce6d0');
    }
    // ragged flame body
    const g = c.createRadialGradient(0, -2, 1, 0, 0, 16);
    g.addColorStop(0, '#ffffff'); g.addColorStop(.25, '#c8fff6'); g.addColorStop(.6, '#4bdbc8'); g.addColorStop(1, '#1a6e66');
    c.fillStyle = g;
    c.beginPath();
    c.moveTo(-2, -20);
    c.bezierCurveTo(7, -17, 13, -7, 9, 2);
    c.bezierCurveTo(7, 8, 4, 6, 2, 12);
    c.bezierCurveTo(0, 8, -4, 10, -7, 5);
    c.bezierCurveTo(-12, -2, -8, -15, -2, -20);
    c.fill();
    c.strokeStyle = '#0f4a45'; c.lineWidth = 1.2; c.stroke();
    // hollow mask-like face
    ell(c, 0, -3, 6, 5.4, '#0b2e2b');
    c.save(); c.shadowColor = '#eafff7'; c.shadowBlur = 10;
    poly(c, [[-4, -4], [-1, -6], [-1, -2], [-4, -1.8]], '#eafff7');
    poly(c, [[1, -6], [4, -4], [4, -1.8], [1, -2]], '#eafff7');
    c.restore();
    // claw tendrils
    for (let i = 0; i < 3; i++) {
      c.strokeStyle = '#7fe8d8'; c.lineWidth = 1.2; c.globalAlpha = .6;
      c.beginPath(); c.moveTo(-6 + i * 5, 2); c.quadraticCurveTo(-9 + i * 6, 8 + Math.sin(t * 3 + i) * 2, -5 + i * 5, 14); c.stroke();
    }
    c.globalAlpha = 1;
    c.restore();
  }

  function drawStone(c, t, seed, move) {
    const sway = move ? Math.sin(t * 6 + seed) * 1.6 : 0;
    c.save();
    P(c, -11, -12, 9, 12, '#6b6355'); P(c, 2, -13, 9, 13, '#5c5548');
    P(c, -13, 0, 11, 4, '#403b32'); P(c, 2, 0, 12, 4, '#37332b');
    // torso: stacked angular slabs
    poly(c, [[-15, -13 + sway], [-13, -28], [-3, -33], [9, -29], [15, -14], [9, -9], [-9, -9]], '#7e7866', '#2a2821', 1.6);
    poly(c, [[-12, -15], [-10, -27], [-2, -30], [7, -27], [12, -16], [-1, -13]], '#9a9481');
    poly(c, [[-10, -27], [-2, -30], [1, -24], [-5, -21]], '#aca58f');
    // cracks + core
    seg(c, -6, -23, -3, -16, '#8fe0c0', 1.4, '#6fe8c0');
    seg(c, -3, -16, -7, -11, '#8fe0c0', 1.2, '#6fe8c0');
    seg(c, 6, -25, 3, -18, '#8fe0c0', 1.1, '#6fe8c0');
    ell(c, 0, -18, 3.4, 4.4, '#12302a');
    c.save(); c.shadowColor = '#8fffe0'; c.shadowBlur = 12; ell(c, 0, -18, 2, 3, '#c8ffe8'); c.restore();
    // moss
    ell(c, -6, -30, 6, 2.6, '#6f8f4c');
    ell(c, 8, -24, 3.2, 1.8, '#5d7b40');
    // head
    poly(c, [[-8, -32], [-5, -39], [5, -39], [9, -31], [0, -28]], '#6f6a59', '#2a2821', 1.3);
    c.save(); c.shadowColor = '#c8ffe8'; c.shadowBlur = 8;
    poly(c, [[-5, -34], [-1, -35.4], [-1, -32.4], [-5, -32]], '#c8ffe8');
    poly(c, [[1, -35.4], [5, -34], [5, -32], [1, -32.4]], '#c8ffe8');
    c.restore();
    // heavy fists
    poly(c, [[-14, -22], [-22, -16], [-20, -7], [-13, -9], [-11, -16]], '#6f6a59', '#2a2821', 1.2);
    poly(c, [[14, -23], [22, -18], [21, -9], [14, -11], [12, -17]], '#6f6a59', '#2a2821', 1.2);
    P(c, -21, -9, 7, 2, '#4b473d'); P(c, 15, -11, 7, 2, '#4b473d');
    c.restore();
  }

  function drawAshling(c, t, seed) {
    const bob = Math.sin(t * 3.1 + seed * 5) * 2.2;
    c.save(); c.translate(0, bob);
    glow(c, 0, -18, 26, '#ff8a4a', .34);
    // flame mane
    for (let i = 0; i < 6; i++) {
      const ph = Math.sin(t * 6 + i * 1.3) * 3;
      poly(c, [[-9 + i * 3.6, -27], [-7 + i * 3.6 + ph, -40 - (i % 3) * 4], [-3 + i * 3.6, -28]], i % 2 ? '#ffd479' : '#ff7a3a');
    }
    // body
    poly(c, [[-10, 0], [-11, -16], [-6, -26], [4, -27], [10, -17], [11, 0], [5, 3], [-5, 3]], '#a8492f', '#3f1c14', 1.3);
    poly(c, [[-6, -4], [-5, -18], [2, -21], [7, -14], [6, -2]], '#e8895c');
    ell(c, 0, -14, 4.2, 5.4, '#3a1710');
    c.save(); c.shadowColor = '#ffb066'; c.shadowBlur = 12; ell(c, 0, -14, 2.4, 3.4, '#ffd08a'); c.restore();
    // skull-ish face with horns
    poly(c, [[-6, -26], [-9, -34], [-2, -29]], '#e8d8c0', '#3f2a1c', .9);
    poly(c, [[5, -27], [10, -35], [2, -29]], '#e8d8c0', '#3f2a1c', .9);
    poly(c, [[-6, -28], [-4, -33], [4, -33], [7, -27], [0, -24]], '#d8c4a8', '#3f2a1c', 1);
    c.save(); c.shadowColor = '#fff0a8'; c.shadowBlur = 8;
    P(c, -4, -30, 3, 1.8, '#fff0a8'); P(c, 2, -30, 3, 1.8, '#fff0a8');
    c.restore();
    // claws & tail embers
    for (const dir of [-1, 1]) {
      c.save(); c.scale(dir, 1);
      seg(c, 9, -15, 15, -8, '#8a3a26', 2.4); P(c, 14, -9, 2, 4, '#ffcf8a');
      c.restore();
    }
    for (let i = 0; i < 5; i++) {
      const ph = (t * .7 + i * .21) % 1;
      ell(c, Math.sin(i * 2 + t) * 11, -ph * 30, 1.4, 1.4, '#ffb066', 1 - ph);
    }
    c.restore();
  }

  function drawAshguard(c, t, seed, move, atk) {
    const gait = move ? Math.sin(t * 7 + seed) * 1.6 : 0;
    c.save();
    // tattered cape
    poly(c, [[-8, -30], [-16, -16 + Math.sin(t * 2.4) * 2], [-13, -2], [-2, -8], [3, -26]], '#3a2c22', '#1c140f', 1);
    P(c, -9, -10 + gait, 7.6, 11, '#4f4034'); P(c, 3, -10 - gait, 7.6, 11, '#44362b');
    P(c, -11, 0, 10, 3.4, '#2a211a'); P(c, 3, 0, 11, 3.4, '#2a211a');
    // plate torso
    poly(c, [[-13, -11], [-15, -28], [-7, -35], [7, -35], [15, -28], [13, -11], [5, -7], [-5, -7]], '#7a6a55', '#2c241d', 1.5);
    poly(c, [[-10, -13], [-11, -27], [-3, -32], [3, -32], [11, -27], [10, -13]], '#9c8a6e');
    poly(c, [[-10, -27], [-3, -32], [0, -24], [-8, -22]], '#b8a684');
    P(c, -3, -23, 7, 1.8, '#d8c49a');
    // pauldrons with spikes
    poly(c, [[-15, -30], [-24, -26], [-22, -18], [-14, -20]], '#6a5a46', '#2c241d', 1.2);
    poly(c, [[15, -30], [24, -26], [22, -18], [14, -20]], '#6a5a46', '#2c241d', 1.2);
    poly(c, [[-20, -30], [-24, -37], [-16, -32]], '#8a7a5e');
    poly(c, [[20, -30], [25, -37], [16, -32]], '#8a7a5e');
    // helm with glowing slit
    poly(c, [[-8, -33], [-6, -41], [6, -41], [9, -33], [4, -29], [-4, -29]], '#5c4f3e', '#241d17', 1.2);
    c.save(); c.shadowColor = '#ff9a4a'; c.shadowBlur = 10;
    P(c, -5, -36, 10, 1.8, '#ffd18a'); P(c, -1, -38, 2, 4, '#ffb066');
    c.restore();
    // spear
    c.save(); c.translate(17, 2); c.rotate(-.2 + (atk > 0 ? -.5 : 0));
    P(c, -1.4, -50, 2.8, 52, '#6b5236'); P(c, -1.4, -50, 1, 52, '#9a7a4e');
    poly(c, [[-4, -50], [0, -62], [4, -50]], '#d8e2e0', '#fff8d8', .9);
    P(c, -4, -50, 8, 2, '#b79a5e');
    c.restore();
    if (atk > 0) { c.save(); c.globalAlpha = atk * .8; glow(c, 18, -30, 20, '#ffb066', .4); c.restore(); }
    c.restore();
  }

  function drawColossus(c, t, seed, move, atk) {
    const sway = Math.sin(t * 2.2 + seed) * 1.4;
    c.save();
    // massive legs
    P(c, -19, -10, 14, 12, '#5c4a38'); P(c, 5, -10, 14, 12, '#4c3c2e');
    P(c, -22, 0, 18, 4, '#2e241c'); P(c, 4, 0, 19, 4, '#2e241c');
    // hips + torso
    poly(c, [[-22, -12 + sway], [-27, -44], [-14, -58], [14, -58], [27, -44], [22, -12], [11, -7], [-11, -7]], '#7a6248', '#2c2018', 1.9);
    poly(c, [[-18, -14], [-21, -42], [-9, -53], [9, -53], [20, -42], [18, -14]], '#967a58');
    // rock plates
    poly(c, [[-18, -40], [-8, -46], [8, -46], [19, -40], [14, -34], [-14, -34]], '#ab8d66');
    poly(c, [[-14, -34], [-5, -28], [5, -28], [15, -34], [8, -26], [-8, -26]], '#886e4e');
    // molten core
    ell(c, 0, -33, 8, 10, '#3a2014');
    c.save(); c.shadowColor = '#ff8a3a'; c.shadowBlur = 18;
    ell(c, 0, -33, 5.2, 7, '#ffb05c');
    ell(c, -1.4, -35, 2.6, 3.6, '#ffe0a0');
    c.restore();
    seg(c, -12, -46, -5, -37, '#ffcf7a', 1.8, '#ff8a3a');
    seg(c, 9, -50, 4, -43, '#ffcf7a', 1.6, '#ff8a3a');
    seg(c, -17, -26, -10, -20, '#ffcf7a', 1.4, '#ff8a3a');
    // tiny head
    poly(c, [[-8, -55], [-6, -64], [6, -64], [9, -55], [0, -51]], '#6f5a44', '#281c13', 1.3);
    c.save(); c.shadowColor = '#ffd06a'; c.shadowBlur = 10;
    P(c, -4, -60, 3.4, 2.2, '#ffd06a'); P(c, 2, -60, 3.4, 2.2, '#ffd06a');
    c.restore();
    poly(c, [[-5, -56], [5, -56], [4, -51], [0, -50], [-4, -51]], '#1b120c', '#281c13', .8);
    for (let i = 0; i < 4; i++) poly(c, [[-4 + i * 2.6, -56], [-3.4 + i * 2.6, -53], [-2.4 + i * 2.6, -56]], '#f4ecd8');
    P(c, -1, -58, 1.8, 3, '#d8a060');
    // rock shoulder slabs
    poly(c, [[-24, -48], [-38, -40], [-34, -30], [-20, -34]], '#8a7050', '#2c2018', 1.4);
    poly(c, [[24, -48], [38, -40], [34, -30], [20, -34]], '#8a7050', '#2c2018', 1.4);
    poly(c, [[-34, -40], [-40, -50], [-27, -44]], '#c0a078', '#4a3a28', .9);
    poly(c, [[34, -40], [40, -50], [27, -44]], '#c0a078', '#4a3a28', .9);
    seg(c, -32, -36, -24, -40, '#ffcf7a', 1.4, '#ff8a3a');
    seg(c, 26, -41, 34, -35, '#ffcf7a', 1.4, '#ff8a3a');
    // gigantic arms
    poly(c, [[-22, -46], [-36, -34], [-32, -14], [-22, -18], [-17, -34]], '#6b5741', '#2c2018', 1.3);
    poly(c, [[22, -46], [36, -34], [32, -14], [22, -18], [17, -34]], '#6b5741', '#2c2018', 1.3);
    for (let i = 0; i < 3; i++) {
      poly(c, [[-37 + i * 3, -16], [-38 + i * 3, -8], [-33 + i * 3, -12]], '#d8c8a8', '#4a3c2c', .7);
      poly(c, [[27 + i * 3, -16], [28 + i * 3, -8], [33 + i * 3, -12]], '#d8c8a8', '#4a3c2c', .7);
    }
    if (atk > 0) {
      c.save(); c.globalAlpha = atk; glow(c, 0, -30, 30, '#ff8a3a', .4); c.restore();
    }
    c.restore();
  }

  function drawWyrm(c, t, seed, mode, atk) {
    const ice = mode === 'ice';
    const fly = Math.sin(t * 2.4 + seed * 4) * 3;
    const bodyCol = ice ? '#7fd0e2' : '#dc7ba6';
    const bodyLit = ice ? '#c8f6ff' : '#ffc0dc';
    const dark = ice ? '#1d4a5c' : '#5c203e';
    const membrane = ice ? '#a8e8f2' : '#f6a8ca';
    c.save(); c.translate(0, fly - 12);
    // wings: wide, layered membranes with bone fingers
    const flap = Math.sin(t * (atk > 0 ? 13 : 4.4) + seed) * .35 + .15;
    for (const dir of [-1, 1]) {
      c.save(); c.scale(dir, 1);
      const spread = 1 + flap;
      poly(c, [[4, -18], [22, -40 * spread], [42, -30 * spread], [46, -6], [28, 10], [12, 0]], membrane, dark, 1.4);
      // membrane shading
      poly(c, [[22, -34 * spread], [42, -26 * spread], [36, -14], [20, -8]], ice ? '#d8faff66' : '#ffd6ea66');
      // bone fingers
      seg(c, 6, -18, 24, -36 * spread, dark + 'cc', 1.8);
      seg(c, 8, -14, 42, -24 * spread, dark + 'cc', 1.6);
      seg(c, 9, -10, 44, -4, dark + 'cc', 1.4);
      // wing claw
      poly(c, [[24, -36 * spread], [30, -46 * spread], [26, -33 * spread]], '#f2f7f2', dark, .7);
      c.restore();
    }
    // long serpentine tail
    c.strokeStyle = ice ? '#4fa8c0' : '#b5547e'; c.lineWidth = 10; c.lineCap = 'round';
    c.beginPath(); c.moveTo(-4, -12);
    c.bezierCurveTo(-18, -6, -30, -6, -36, -18 + Math.sin(t * 2.6) * 4);
    c.stroke();
    c.strokeStyle = bodyCol; c.lineWidth = 6.5;
    c.beginPath(); c.moveTo(-4, -12);
    c.bezierCurveTo(-18, -7, -28, -8, -35, -18 + Math.sin(t * 2.6) * 4);
    c.stroke();
    // tail spade
    poly(c, [[-35, -18], [-46, -24], [-42, -10]], bodyLit, dark, 1);
    // body
    const g = c.createLinearGradient(0, -28, 0, 2);
    g.addColorStop(0, bodyLit); g.addColorStop(.45, bodyCol); g.addColorStop(1, dark);
    ell(c, 2, -16, 16, 11, g, -.14);
    c.strokeStyle = dark; c.lineWidth = 1.5;
    c.beginPath(); c.ellipse(2, -16, 16, 11, -.14, 0, TAU); c.stroke();
    // belly scales
    for (let i = 0; i < 5; i++) {
      c.strokeStyle = ice ? '#e8ffff66' : '#ffe0f066'; c.lineWidth = .9;
      c.beginPath(); c.arc(0 + i * 3, -8, 5, .3, Math.PI - .3); c.stroke();
    }
    // dorsal spines
    for (let i = 0; i < 4; i++) {
      poly(c, [[-6 + i * 5, -25], [-4 + i * 5, -33], [-1 + i * 5, -24]], ice ? '#eaffff' : '#ffd0e4', dark, .6);
    }
    // sinuous neck rising into a big horned skull
    poly(c, [[10, -24], [18, -35], [27, -38], [34, -33], [26, -29], [17, -27], [12, -18]], bodyCol, dark, 1.3);
    poly(c, [[12, -23], [19, -33], [27, -35], [30, -31], [22, -28], [16, -25]], bodyLit);
    // throat plates
    for (let i = 0; i < 4; i++) {
      c.strokeStyle = ice ? '#eaffff77' : '#ffe4f077'; c.lineWidth = .9;
      c.beginPath(); c.moveTo(13 + i * 4, -22 + i * 2.4); c.lineTo(19 + i * 4, -25 + i * 2.6); c.stroke();
    }
    // skull
    c.save(); c.translate(32, -32); c.rotate(-.1);
    poly(c, [[-8, -5], [-2, -8], [8, -5], [15, -1], [8, 4], [-4, 4]], bodyLit, dark, 1.5);
    // brow ridge
    poly(c, [[-6, -6], [4, -8], [7, -4], [-4, -3]], ice ? '#eaffff' : '#ffdce8');
    // open maw
    poly(c, [[2, 1], [15, -1], [14, 4], [3, 4.6]], '#3a1224', dark, 1.1);
    poly(c, [[3, 4], [6, 7], [7, 3.4]], '#fff6e0', dark, .5);
    poly(c, [[8.4, 3.4], [10.6, 6.4], [11.6, 3]], '#fff6e0', dark, .5);
    poly(c, [[3, 2], [6, -3], [7, 1.6]], '#fff6e0', dark, .5);
    poly(c, [[9, 1.4], [11.6, -3.4], [12.4, 1]], '#fff6e0', dark, .5);
    // eye with slit pupil
    c.save(); c.shadowColor = ice ? '#eaffff' : '#ffe08a'; c.shadowBlur = 10;
    poly(c, [[-3, -2.6], [3, -3.8], [3, -.6], [-3, 0]], ice ? '#eaffff' : '#ffe08a');
    c.restore();
    P(c, .2, -2.6, 1, 2.6, '#101a22');
    // crown of horns
    poly(c, [[-4, -7], [-13, -19], [-1, -8]], ice ? '#f4ffff' : '#ffeaf2', dark, .9);
    poly(c, [[1, -8], [0, -21], [5, -8]], ice ? '#f4ffff' : '#ffeaf2', dark, .9);
    poly(c, [[5, -7], [10, -18], [8, -6]], ice ? '#f4ffff' : '#ffeaf2', dark, .8);
    c.restore();
    // fins along the jaw
    for (let i = 0; i < 3; i++) poly(c, [[28 - i * 2, -26 + i], [22 - i * 2, -22 + i], [28 - i * 2, -21 + i]], membrane, dark, .6);
    // breath
    for (let i = 0; i < 6; i++) {
      const ph = (t * .85 + i * .16) % 1;
      c.globalAlpha = (1 - ph) * .8;
      ell(c, 47 + ph * 16, -30 + Math.sin(i * 2 + t * 3) * 3, 3 * (1 - ph) + 1, 3 * (1 - ph) + 1, ice ? '#d8ffff' : '#ffd0e8');
    }
    c.globalAlpha = 1;
    c.restore();
  }

  function drawRiftKnight(c, t, seed, move, atk) {
    const gait = move ? Math.sin(t * 7 + seed) * 1.5 : 0;
    c.save();
    // cape
    poly(c, [[-8, -32], [-20, -18 + Math.sin(t * 3) * 3], [-14, -2], [-2, -9], [4, -30]], '#3b2a55', '#160f24', 1.1);
    P(c, -9, -10 + gait, 7.4, 11, '#4b3b63'); P(c, 3, -10 - gait, 7.4, 11, '#3f3155');
    P(c, -11, 0, 10, 3, '#1d1626'); P(c, 3, 0, 11, 3, '#191322');
    // armour
    poly(c, [[-12, -11], [-14, -30], [-6, -37], [6, -37], [14, -30], [12, -11], [5, -7], [-5, -7]], '#493763', '#1a1327', 1.6);
    poly(c, [[-9, -13], [-10, -28], [-2, -33], [3, -33], [10, -28], [9, -13]], '#6b5490');
    poly(c, [[-9, -28], [-2, -33], [1, -25], [-7, -23]], '#8669ab');
    P(c, -2, -24, 6, 1.8, '#b88cf0');
    // pauldrons with void shards
    poly(c, [[-14, -31], [-23, -27], [-20, -18], [-12, -21]], '#3c2c56', '#160f24', 1.2);
    poly(c, [[14, -31], [23, -27], [20, -18], [12, -21]], '#3c2c56', '#160f24', 1.2);
    poly(c, [[-19, -30], [-25, -40], [-14, -33]], '#8a6ab5', '#2a1c3e', .8);
    poly(c, [[19, -30], [26, -40], [15, -33]], '#8a6ab5', '#2a1c3e', .8);
    // horned helm
    poly(c, [[-8, -34], [-6, -43], [6, -43], [9, -34], [0, -30]], '#2f2444', '#120d1d', 1.2);
    poly(c, [[-6, -42], [-14, -50], [-4, -43]], '#8a6ab5');
    poly(c, [[6, -42], [14, -50], [4, -43]], '#8a6ab5');
    c.save(); c.shadowColor = '#d9a0ff'; c.shadowBlur = 12;
    P(c, -5, -38, 10, 2, '#e8b6ff');
    c.restore();
    // obsidian greatsword
    c.save(); c.translate(18, -13); c.rotate(.42 + (atk > 0 ? -1.35 : 0) + Math.sin(t * 2) * .03);
    P(c, -2, -5, 4, 12, '#4a3524'); P(c, -7, -6, 14, 2.6, '#8a6a3f');
    const g2 = c.createLinearGradient(-4, -46, 4, -6);
    g2.addColorStop(0, '#e8d0ff'); g2.addColorStop(.5, '#b98ad4'); g2.addColorStop(1, '#5a4372');
    poly(c, [[-3.4, -6], [-2.8, -44], [0, -49], [2.8, -44], [3.4, -6]], g2, '#f4e2ff', 1);
    c.save(); c.shadowColor = '#ca88ff'; c.shadowBlur = 12;
    seg(c, 0, -44, 0, -10, '#f0dcff', 1.4, '#ca88ff');
    c.restore();
    c.restore();
    if (atk > 0) { c.save(); c.globalAlpha = atk * .6; glow(c, 16, -34, 24, '#ca88ff', .4); c.restore(); }
    c.restore();
  }

  function drawWraith(c, t, seed) {
    const float = Math.sin(t * 1.8 + seed * 4) * 2.5;
    c.save(); c.translate(0, float - 8);
    glow(c, 0, -20, 30, '#8b45c8', .3);
    // robe with many tattered strips
    c.beginPath();
    c.moveTo(-12, -26);
    c.bezierCurveTo(-18, -10, -14, 4, -9, 10 + Math.sin(t * 3) * 3);
    c.lineTo(-6, 3); c.lineTo(-3, 12 + Math.sin(t * 3.5) * 2);
    c.lineTo(1, 2); c.lineTo(5, 11); c.lineTo(8, 1); c.lineTo(13, 8);
    c.bezierCurveTo(16, -4, 14, -16, 12, -26);
    c.closePath(); c.fillStyle = '#2b1a44'; c.fill();
    c.strokeStyle = '#6c3fa0'; c.lineWidth = 1.2; c.stroke();
    // inner void
    c.globalAlpha = .5; ell(c, 0, -12, 6, 12, '#120a20'); c.globalAlpha = 1;
    // hood
    poly(c, [[-11, -27], [-8, -39], [0, -44], [8, -39], [11, -27], [4, -23], [-4, -23]], '#3a2258', '#140c22', 1.3);
    ell(c, 0, -31, 7.4, 8.4, '#0d0717');
    // hollow eyes
    c.save(); c.shadowColor = '#d9a6ff'; c.shadowBlur = 10;
    poly(c, [[-4.4, -32], [-1, -33.4], [-1, -30], [-4.4, -30]], '#e0c0ff');
    poly(c, [[1, -33.4], [4.4, -32], [4.4, -30], [1, -30]], '#e0c0ff');
    c.restore();
    // claw hands
    for (const dir of [-1, 1]) {
      c.save(); c.scale(dir, 1);
      seg(c, 9, -20, 15, -12, '#4a2a70', 2);
      for (let i = 0; i < 3; i++) seg(c, 15, -12, 17 + i, -8 + i, '#b48ad8', 1);
      c.restore();
    }
    // drifting soul motes
    for (let i = 0; i < 5; i++) {
      const ph = (t * .6 + i * .21) % 1;
      ell(c, Math.sin(i * 2 + t) * 10, -ph * 26, 1.4, 1.4, '#b48ad8', (1 - ph) * .8);
    }
    c.restore();
  }

  function drawTitan(c, t, seed, move, atk) {
    const sway = Math.sin(t * 1.8 + seed) * 2;
    c.save();
    // orbit rings
    c.save(); c.translate(0, -38);
    for (let i = 0; i < 3; i++) {
      c.strokeStyle = i % 2 ? '#7fe6ff88' : '#8f9bff55'; c.lineWidth = 1.4;
      c.beginPath(); c.ellipse(0, 0, 34 + i * 8, 11 + i * 3, t * .3 + i, 0, TAU); c.stroke();
    }
    for (let i = 0; i < 4; i++) {
      const a = t * .9 + i * TAU / 4;
      c.save(); c.shadowColor = '#bff5ff'; c.shadowBlur = 8;
      ell(c, Math.cos(a) * 36, Math.sin(a) * 12, 1.8, 1.8, '#dffaff'); c.restore();
    }
    c.restore();
    P(c, -18, -10, 14, 12, '#3f5570'); P(c, 5, -10, 14, 12, '#354861');
    P(c, -21, 0, 17, 4, '#1d2b3a'); P(c, 5, 0, 18, 4, '#1d2b3a');
    // massive armoured torso
    poly(c, [[-24, -12 + sway], [-28, -46], [-14, -60], [14, -60], [28, -46], [24, -12], [11, -7], [-11, -7]], '#3a5878', '#16233a', 1.8);
    poly(c, [[-20, -14], [-23, -44], [-10, -54], [10, -54], [23, -44], [20, -14]], '#557da3');
    poly(c, [[-20, -44], [-8, -52], [8, -52], [21, -44], [12, -38], [-12, -38]], '#6f9cc4');
    // star core
    c.save(); c.shadowColor = '#8fefff'; c.shadowBlur = 20;
    poly(c, [[0, -46], [4.6, -36], [15, -35], [7, -28], [9, -17], [0, -23], [-9, -17], [-7, -28], [-15, -35], [-4.6, -36]], '#dffaff', '#ffffff', 1.2);
    c.restore();
    // shoulders with spikes
    poly(c, [[-26, -48], [-38, -40], [-34, -22], [-24, -26]], '#34506e', '#16233a', 1.3);
    poly(c, [[26, -48], [38, -40], [34, -22], [24, -26]], '#34506e', '#16233a', 1.3);
    poly(c, [[-32, -44], [-42, -56], [-28, -48]], '#8fc8e8');
    poly(c, [[32, -44], [42, -56], [28, -48]], '#8fc8e8');
    // helm
    poly(c, [[-8, -58], [-5, -67], [5, -67], [8, -58], [0, -54]], '#2c4460', '#111c2c', 1.2);
    c.save(); c.shadowColor = '#aef4ff'; c.shadowBlur = 10;
    P(c, -4, -63, 3.4, 2, '#aef4ff'); P(c, 2, -63, 3.4, 2, '#aef4ff');
    c.restore();
    if (atk > 0) { c.save(); c.globalAlpha = atk * .55; glow(c, 0, -36, 36, '#7fe6ff', .4); c.restore(); }
    c.restore();
  }

  function drawSentinel(c, t, seed, move, atk) {
    const gait = move ? Math.sin(t * 7 + seed) * 1.3 : 0;
    c.save();
    P(c, -10, -8 + gait, 7, 10, '#221a2c'); P(c, 3, -8 - gait, 7, 10, '#1b1424');
    P(c, -12, 0, 10, 3, '#120d18'); P(c, 3, 0, 11, 3, '#0f0b14');
    // angular obsidian armour
    poly(c, [[-13, -10], [-16, -31], [-7, -40], [7, -40], [16, -31], [13, -10], [5, -6], [-5, -6]], '#392b45', '#120d1b', 1.6);
    poly(c, [[-10, -12], [-12, -30], [-3, -36], [4, -36], [12, -30], [10, -12]], '#57415f');
    poly(c, [[-10, -30], [-3, -36], [0, -27], [-8, -24]], '#725588');
    // glass shard crown + shoulders
    poly(c, [[-15, -34], [-22, -46], [-10, -36]], '#7c5e8c', '#2a1f33', 1);
    poly(c, [[14, -34], [23, -47], [9, -37]], '#7c5e8c', '#2a1f33', 1);
    poly(c, [[-4, -40], [1, -52], [6, -40]], '#936ca6', '#2a1f33', 1);
    // helm slit
    poly(c, [[-8, -34], [-5, -42], [5, -42], [8, -34], [0, -31]], '#251c2e', '#0e0a14', 1.2);
    c.save(); c.shadowColor = '#d48aff'; c.shadowBlur = 12;
    P(c, -5, -38, 10, 1.8, '#e2a8ff');
    c.restore();
    // blade
    c.save(); c.translate(15, 2); c.rotate(-.15 + (atk > 0 ? -.55 : 0));
    P(c, -2, -48, 4, 50, '#241b2e'); P(c, -2, -48, 1.4, 50, '#4a3558');
    const g3 = c.createLinearGradient(0, -64, 0, -44);
    g3.addColorStop(0, '#f0d8ff'); g3.addColorStop(.5, '#b98ad4'); g3.addColorStop(1, '#5a4372');
    poly(c, [[-4, -48], [-2.6, -62], [0, -68], [2.6, -62], [4, -48]], g3, '#2a1f33', 1);
    c.save(); c.shadowColor = '#d48aff'; c.shadowBlur = 10; seg(c, 0, -62, 0, -50, '#f0dcff', 1.2, '#ca88ff'); c.restore();
    c.restore();
    c.restore();
  }

  function drawStarseer(c, t, seed) {
    const float = Math.sin(t * 2 + seed * 3) * 3;
    c.save(); c.translate(0, float - 10);
    glow(c, 0, -24, 32, '#c88cff', .26);
    // star halo
    c.save(); c.strokeStyle = '#f2d7ff'; c.lineWidth = 1.6; c.shadowColor = '#e0b0ff'; c.shadowBlur = 10;
    c.beginPath(); c.ellipse(0, -48, 13, 4.2, 0, 0, TAU); c.stroke(); c.restore();
    for (let i = 0; i < 7; i++) {
      const a = t * 1.2 + i * .9;
      ell(c, Math.cos(a) * 20, -28 + Math.sin(a) * 13, 1.6, 1.6, i % 2 ? '#f2d7ff' : '#b9e8ff');
    }
    // robes
    poly(c, [[-11, -12], [-17, 2], [-8, 8], [0, 2], [8, 8], [17, 2], [11, -12], [5, -30], [-5, -30]], '#5a3a75', '#231332', 1.3);
    poly(c, [[-7, -10], [-5, -25], [4, -25], [8, -10], [0, -5]], '#8a5fa8');
    // runic sash
    P(c, -6, -14, 12, 1.6, '#e8c8ff');
    // head and third eye
    ell(c, 0, -31, 6, 6.4, '#d8c0d8');
    poly(c, [[-6, -34], [-5, -39], [5, -39], [6, -34], [0, -31]], '#4a2d60', '#1e1128', 1);
    c.save(); c.shadowColor = '#e8d0ff'; c.shadowBlur = 9;
    P(c, -3.4, -32, 2.4, 1.6, '#f0dcff'); P(c, 1, -32, 2.4, 1.6, '#f0dcff');
    ell(c, 0, -37, 1.6, 1.6, '#f0dcff');
    c.restore();
    // staff with crystal
    c.save(); c.translate(16, 4); c.rotate(.08);
    P(c, -1.2, -48, 2.4, 50, '#6f5a3f'); P(c, -1.2, -48, .8, 50, '#9a7f58');
    c.save(); c.shadowColor = '#d9a6ef'; c.shadowBlur = 14;
    poly(c, [[0, -56], [5, -48], [0, -40], [-5, -48]], '#e8c8ff', '#f8ecff', 1);
    c.restore();
    c.restore();
    c.restore();
  }

  function drawWarden(c, t, seed, move, atk) {
    const sway = Math.sin(t * 1.6 + seed) * 2;
    c.save();
    P(c, -16, -10, 12, 12, '#4a3a28'); P(c, 5, -10, 12, 12, '#3f3122');
    // roots
    for (let i = 0; i < 6; i++) seg(c, -18 + i * 7.4, 0, -22 + i * 8, 5, '#5c7a42', 2.2);
    // bark torso
    poly(c, [[-22, -11 + sway], [-26, -44], [-12, -58], [12, -58], [26, -44], [22, -11], [10, -6], [-10, -6]], '#56462f', '#1f1810', 1.9);
    poly(c, [[-18, -13], [-21, -42], [-9, -53], [9, -53], [21, -42], [18, -13]], '#7d6647');
    poly(c, [[-18, -42], [-9, -51], [0, -44], [-12, -36]], '#96794f');
    // bark grooves
    for (let i = -2; i <= 2; i++) seg(c, i * 6, -46, i * 6 + 1.4, -16, '#4a3a22', 1.2);
    // moss
    ell(c, -6, -46, 9, 3.6, '#6f9a4d');
    ell(c, 9, -30, 4, 2.4, '#5c8441');
    ell(c, -11, -24, 3.4, 2, '#6f9a4d');
    // glowing heart
    ell(c, 0, -34, 4.4, 5.4, '#243a1c');
    c.save(); c.shadowColor = '#a8ff7a'; c.shadowBlur = 14; ell(c, 0, -34, 2.6, 3.4, '#c8ff9a'); c.restore();
    // antlers
    for (const dir of [-1, 1]) {
      c.save(); c.scale(dir, 1);
      seg(c, 5, -56, 14, -70, '#8a7550', 3);
      seg(c, 9, -64, 17, -66, '#8a7550', 2.2);
      seg(c, 14, -70, 21, -74, '#8a7550', 1.8);
      seg(c, 14, -70, 12, -78, '#8a7550', 1.6);
      c.restore();
    }
    // head in the trunk
    poly(c, [[-10, -52], [-7, -60], [7, -60], [10, -52], [0, -48]], '#5a4a33', '#1f1810', 1.3);
    c.save(); c.shadowColor = '#c8ff9a'; c.shadowBlur = 12;
    poly(c, [[-7, -55], [-2, -57], [-2, -52.6], [-7, -52]], '#c8ff9a');
    poly(c, [[2, -57], [7, -55], [7, -52], [2, -52.6]], '#c8ff9a');
    c.restore();
    // leaf crown
    for (let i = 0; i < 8; i++) {
      const a = -Math.PI + i * (Math.PI / 7);
      ell(c, Math.cos(a) * 15, -58 + Math.sin(a) * 5, 5, 3.2, i % 2 ? '#4f8448' : '#7fae57', a);
    }
    // club arms
    poly(c, [[-22, -46], [-34, -32], [-29, -12], [-20, -17], [-16, -33]], '#4d3f2c', '#1f1810', 1.3);
    poly(c, [[22, -46], [34, -32], [29, -12], [20, -17], [16, -33]], '#4d3f2c', '#1f1810', 1.3);
    ell(c, -30, -14, 7, 6, '#5f4c33'); ell(c, 30, -14, 7, 6, '#5f4c33');
    for (let i = 0; i < 3; i++) { poly(c, [[-36 + i * 4, -16], [-38 + i * 4, -8], [-32 + i * 4, -13]], '#8a7550'); poly(c, [[24 + i * 4, -16], [26 + i * 4, -8], [32 + i * 4, -13]], '#8a7550'); }
    if (atk > 0) { c.save(); c.globalAlpha = atk * .5; glow(c, 0, -38, 32, '#a8ff7a', .4); c.restore(); }
    c.restore();
  }

  /* ── hero / NPC sprite ───────────────────────────────────────────────── */
  const SKIN = '#e8c39a', SKIN_SH = '#c09068';
  const HAIR = '#4a3324', HAIR_LIT = '#6b4a30';
  /* ── hero model: pose-driven so every verb reads at a glance ─────────── */
  function drawHeroModel(c, q, opts) {
    const o = opts || {};
    const t = o.time || 0;
    const coat = o.coat || '#547c50';
    const trim = o.trim || '#e6cf8f';
    const local = !!o.local;
    const face = Number(q.face_x) < -0.05 ? -1 : 1;
    const walk = o.walk || 0;
    const moving = !!(o.move && o.move > .2);
    const swing = clamp(o.swing || 0, 0, 1);
    const cls = q.class || o.class || '';
    const weaponId = q.weapon || o.weapon || 'sword';
    const weaponMeta = customWeaponMeta(weaponId, q.id || (local && typeof myId !== 'undefined' ? myId : ''));
    const weaponKind = o.weaponKind || weaponMeta.kind
      || (/bow|longbow/.test(weaponId) ? 'bow' : /staff/.test(weaponId) ? 'staff' : 'melee');
    const weaponPaint = {
      core: o.weaponColor || weaponMeta.color || '',
      shape: weaponMeta.shape || '',
    };
    const gatherKind = o.gatherKind || '';
    const run = !!o.run && moving;
    const sneak = !!o.sneak;
    const aim = clamp(o.aim || 0, 0, 1);
    const cast = clamp(o.cast || 0, 0, 1);
    const drink = clamp(o.drink || 0, 0, 1);
    const gather = clamp(o.gather || 0, 0, 1);
    const swap = clamp(o.swap || 0, 0, 1);
    const shoot = clamp(o.shoot || 0, 0, 1);
    const hurt = clamp(o.hurt || 0, 0, 1);
    const charge = clamp(o.charge || 0, 0, 1);
    const dark = '#1d2a1f';

    const stride = run ? 5.6 : sneak ? 2.1 : 3.4;
    const step = Math.sin(walk) * (moving ? stride : .45);
    const bob = Math.abs(Math.sin(walk)) * (moving ? (run ? 2.6 : 1.6) : .5) * (sneak ? .45 : 1);
    const crouch = sneak ? 5.2 : gather ? 4.2 : 0;
    // Positive rotation tips the head toward local +x, i.e. the direction the
    // hero faces — a sprint leans into the run, it does not lean back.
    const lean = run ? .14 : sneak ? .26 : gather ? .17 : 0;
    const sway = run ? Math.sin(walk * 2) * .03 : 0;

    c.save();
    if (hurt > 0) c.translate(-face * hurt * 1.8, 0);
    c.scale(face, 1);
    c.rotate(lean + sway);
    c.translate(0, -bob);

    /* cloak: streams behind, tucks in when sneaking */
    const flare = run ? 6 : sneak ? -2 : 0;
    c.beginPath();
    c.moveTo(-7, -26 + crouch);
    c.quadraticCurveTo(-15 - flare - Math.abs(step) * .35, -13 + Math.sin(t * 2.3) * (run ? 3 : 1.4), -10 - flare * .7, 0);
    c.lineTo(-2, -5 + crouch * .4);
    c.lineTo(7, -25 + crouch);
    c.closePath();
    c.fillStyle = coat; c.globalAlpha = .88; c.fill();
    c.globalAlpha = 1; c.strokeStyle = dark; c.lineWidth = .9; c.stroke();

    /* legs: bent when sneaking, wide stride when running */
    const lift = moving ? Math.max(0, Math.sin(walk)) * (run ? 2.6 : 1.2) : 0;
    P(c, -6 + step * .55, -13, 5, 11.5 - lift * .4, '#3c4054');
    P(c, 1.6 - step * .55, -13, 5, 11.5 - Math.max(0, -Math.sin(walk)) * (run ? 2 : .9) * .4, '#313547');
    P(c, -6.4 + step * .55, -3, 5.8, 3.4, '#241d15');
    P(c, 1.4 - step * .55, -3, 5.8, 3.4, '#1e1812');
    P(c, -6 + step * .55, -13, 5, 1.4, '#565b70');
    P(c, 1.6 - step * .55, -13, 5, 1.4, '#4a4f63');

    /* upper body sinks when crouching */
    c.save();
    c.translate(0, crouch);
    if (cast > 0 || drink > 0) c.rotate(Math.sin(t * 2) * .012);

    /* torso */
    const bodyGrad = c.createLinearGradient(-7, -28, 7, -10);
    bodyGrad.addColorStop(0, lighten(coat, 18));
    bodyGrad.addColorStop(.55, coat);
    bodyGrad.addColorStop(1, darken(coat, 34));
    c.fillStyle = bodyGrad;
    c.beginPath();
    c.moveTo(-7.4, -27.5); c.lineTo(7.4, -27.5); c.lineTo(6.2, -12); c.lineTo(-6.2, -12); c.closePath();
    c.fill(); c.strokeStyle = dark; c.lineWidth = 1; c.stroke();
    P(c, -6.6, -15.4, 13.2, 2.4, '#4a3524');
    P(c, -1.6, -15.8, 3.2, 3, trim);
    c.strokeStyle = '#00000044'; c.lineWidth = 1.2;
    c.beginPath(); c.moveTo(-5, -26); c.lineTo(5, -16); c.stroke();
    poly(c, [[-10.6, -27.4], [-5.4, -27.4], [-4.8, -23.8], [-7.6, -22.6], [-10.2, -24.4]], trim, dark, .8);
    poly(c, [[10.6, -27.4], [5.4, -27.4], [4.8, -23.8], [7.6, -22.6], [10.2, -24.4]], trim, dark, .8);

    /* head */
    const headTilt = (drink > 0 ? .18 * drink : 0) - (hurt > 0 ? .1 * hurt : 0) - (aim > 0 ? .05 : 0);
    c.save();
    c.translate(0, -33);
    c.rotate(headTilt);
    ell(c, 0, 0, 6.4, 6.8, SKIN);
    ell(c, -2.2, -.4, 3.4, 3.6, lighten(SKIN, 10));
    c.strokeStyle = '#6a4a30'; c.lineWidth = .8;
    c.beginPath(); c.ellipse(0, 0, 6.4, 6.8, 0, 0, TAU); c.stroke();
    if (cls === 'mage') {
      poly(c, [[-7, 0], [-6, -9], [0, -12], [6, -9], [7, 0], [4, -3], [-4, -3]], '#3f5a7a', '#1d2a36', 1);
      P(c, -1, -11, 2, 4, trim);
    } else {
      c.fillStyle = HAIR;
      c.beginPath(); c.arc(0, -2.6, 6.6, Math.PI * 1.03, Math.PI * 2.02); c.fill();
      P(c, -6.6, -3.4, 3.2, 6.6, HAIR);
      P(c, 3.4, -4.2, 3.2, 3.6, HAIR_LIT);
      P(c, -1.4, -7.4, 4.4, 2, HAIR_LIT);
      c.strokeStyle = '#2a1c12'; c.lineWidth = .7;
      c.beginPath(); c.arc(0, -2.6, 6.6, Math.PI * 1.03, Math.PI * 2.02); c.stroke();
    }
    if (cls === 'warrior') { P(c, -1.6, -9.4, 3.2, 3, '#a34f45'); P(c, -3.6, -6.4, 7.2, 1.6, '#7e3b35'); }
    /* face */
    const eyeShut = hurt > .4 || drink > .5;
    if (eyeShut) {
      c.strokeStyle = '#15130e'; c.lineWidth = .9;
      c.beginPath();
      c.moveTo(.2, -.6); c.lineTo(2, -.6); c.moveTo(3.9, -.6); c.lineTo(5.6, -.6);
      c.stroke();
    } else {
      P(c, .2, -.6, 2, 1.9, '#15130e');
      P(c, 3.9, -.6, 1.7, 1.8, '#15130e');
      P(c, .9, -1, .7, .7, '#fff8e8');
      P(c, 4.4, -1, .6, .6, '#fff8e8');
    }
    c.strokeStyle = HAIR_LIT; c.lineWidth = .9;
    c.beginPath(); c.moveTo(-.4, -2.6); c.lineTo(2.2, -2.2); c.moveTo(3.7, -2.2); c.lineTo(5.4, -2.6); c.stroke();
    P(c, 2.4, 2.6, 2.4, .9, '#b07a5a');
    if (cls === 'ranger') {
      c.save(); c.translate(-7, 11); c.rotate(-.4);
      P(c, -2, -6, 5, 14, '#5a4326'); P(c, -2, -6, 5, 2, '#7a5a36');
      for (let i = -1; i <= 1; i++) P(c, i * 2, -10, 1.2, 6, '#c8d8a8');
      c.restore();
    }
    if (cls === 'mage') {
      c.save(); c.shadowColor = '#8fe8ff'; c.shadowBlur = 7; c.fillStyle = '#baf3ff';
      c.beginPath(); c.arc(-6, -10, 1.7, 0, TAU); c.fill(); c.restore();
    }
    c.restore();

    /* ── arms & weapon: the hand position is the whole performance ─────── */
    const idleSwing = moving ? Math.sin(walk + Math.PI) * (run ? .22 : .12) : Math.sin(t * 2) * .035;
    let hand = { x: 9.4 + idleSwing * 4, y: -13.4 };
    let off = { x: -8.6 - idleSwing * 3, y: -14.6 };
    let offRot = 0, weaponAlpha = 1;
    const tool = null;
    // Gathering is a two-handed pull, not a weapon flourish: the arm reaches
    // down to the node and drags the find back toward the chest.
    const gatherReach = gather > 0 ? (Math.sin(t * 7) + 1) / 2 : 0;

    if (aim > 0) {
      hand = { x: 13.2, y: -24.2 - aim * .6 };
      off = { x: 5.6 - aim * 1.2, y: -24.6 - aim * 1.4 };
    } else if (cast > 0) {
      hand = { x: 6.4, y: -30.4 };
      off = { x: -7.8, y: -27.4 };
    } else if (drink > 0) {
      off = { x: 3.6, y: -28.4 };
      hand = { x: 9.6, y: -13.8 };
    } else if (gather > 0) {
      hand = { x: 12.4 - gatherReach * 4.6, y: -9.4 - gatherReach * 4.6 };
      off = { x: 6.2 - gatherReach * 2.4, y: -8.6 - gatherReach * 3.2 };
    } else if (run) {
      hand = { x: 10.6, y: -16.4 + idleSwing * 2 };
      off = { x: -9.2, y: -17 + Math.sin(walk) * 2 };
    } else if (sneak) {
      hand = { x: 8.2, y: -11.4 };
      off = { x: -7.4, y: -12.2 };
    }
    if (charge > 0 && aim <= 0 && cast <= 0 && drink <= 0) {
      hand.x -= charge * 1.6;
      hand.y -= charge * .8;
    }
    if (swing > .36) {
      hand.x += (swing - .36) * 6;
      hand.y -= (swing - .36) * 5;
    }
    if (swap > 0.02) {
      weaponAlpha = 1 - swap * .9;
      hand.y += swap * 3;
    }

    // weapon arm
    c.strokeStyle = dark; c.lineWidth = 2.9;
    c.beginPath(); c.moveTo(7.2, -24); c.lineTo(hand.x, hand.y); c.stroke();
    c.strokeStyle = coat; c.lineWidth = 2.2;
    c.beginPath(); c.moveTo(7.2, -24); c.lineTo(hand.x, hand.y); c.stroke();
    ell(c, hand.x, hand.y, 2.1, 2.1, SKIN);
    if (gather > 0) {
      // the blade would only wave around at hip height — show the tool instead
      drawGatherTool(c, gatherKind, t, hand.x, hand.y, gatherReach);
    } else if (weaponAlpha > .05) {
      c.save();
      c.globalAlpha = weaponAlpha;
      drawHeldWeapon(c, weaponId, weaponKind, trim, swing, local, t, hand.x, hand.y,
        { aim, cast, gather, charge, tool, shoot, swap,
          core: weaponPaint.core, shape: weaponPaint.shape });
      c.restore();
    }
    // off arm
    const elbowX = off.x * .55 - 1.2, elbowY = off.y * .62 - 8;
    c.strokeStyle = dark; c.lineWidth = 2.6;
    c.beginPath(); c.moveTo(-6.4, -24); c.quadraticCurveTo(elbowX, elbowY, off.x, off.y); c.stroke();
    c.strokeStyle = coat; c.lineWidth = 1.9;
    c.beginPath(); c.moveTo(-6.4, -24); c.quadraticCurveTo(elbowX, elbowY, off.x, off.y); c.stroke();
    ell(c, off.x, off.y, 2, 2, SKIN);

    // flask in the off hand while drinking
    if (drink > .05) {
      // soft halo so the gesture reads even at gameplay zoom
      c.save(); c.globalAlpha = Math.min(1, drink) * .3;
      c.fillStyle = '#8fe8c8';
      c.beginPath(); c.arc(off.x + 1, off.y - 3, 7, 0, TAU); c.fill();
      c.restore();
      for (let i = 0; i < 3; i++) {
        const ph = ((t * .9 + i * .33) % 1);
        c.globalAlpha = (1 - ph) * drink * .8;
        ell(c, off.x + 2 + Math.sin(t * 3 + i) * 2, off.y - 8 - ph * 12, 1.3, 1.3, '#bff4ea');
      }
      c.globalAlpha = 1;
      c.save(); c.translate(off.x + 1.4, off.y - 1.4); c.rotate(-.55);
      c.globalAlpha = Math.min(1, drink * 1.6);
      c.shadowColor = '#8fe8c8'; c.shadowBlur = 8;
      P(c, -2.6, -4.6, 5.2, 7, '#2e6e60');
      P(c, -2.2, -4.2, 4.4, 6.2, '#7fe0c8');
      P(c, -1.4, -3.4, 2.8, 3, '#c8fff0');
      c.shadowBlur = 0;
      P(c, -1.2, -6.6, 2.4, 2.2, '#d8c8a8');
      c.strokeStyle = '#1e3a34'; c.lineWidth = .7;
      c.strokeRect(-2.6, -4.6, 5.2, 7);
      c.restore();
    }
    // shield / focus in the off hand for warriors and mages
    if (cls === 'warrior') {
      c.save(); c.translate(-11.6, -17.4 + crouch * 0); c.rotate(-.18 + (aim > 0 ? .3 : 0));
      poly(c, [[-6, -7], [4, -8], [6, 1], [3, 8], [-3, 8], [-6, 1]], '#6f5a3f', dark, 1.2);
      poly(c, [[-4, -5], [2.6, -6], [4, 0], [1.6, 5.6], [-2, 5.6], [-4, 0]], '#8d7550');
      poly(c, [[-2.4, -3], [0, -1], [-2.4, 3]], trim);
      P(c, -4, -6.4, 8, 1.4, '#b79a5e');
      c.restore();
    }
    if (cls === 'mage' && cast > .05) {
      c.save(); c.globalAlpha = cast * .9; c.shadowColor = '#9fe8ff'; c.shadowBlur = 10;
      ell(c, off.x, off.y - 1.4, 2.6 + cast * 1.6, 2.6 + cast * 1.6, '#cdf6ff');
      c.restore();
    }
    c.restore();

    /* charge shimmer: a thin rim, not a floodlight */
    if (charge > .02) {
      c.save();
      c.globalAlpha = .18 + charge * .3;
      c.strokeStyle = '#ffe6a3'; c.lineWidth = 1.1;
      c.beginPath(); c.ellipse(0, 1, 12 + charge * 3, 4.4 + charge * 1.2, 0, 0, TAU); c.stroke();
      c.restore();
    }
    if (local) {
      c.globalAlpha = .32; c.strokeStyle = trim; c.lineWidth = 1;
      c.beginPath(); c.ellipse(0, 1, 13, 4, 0, 0, TAU); c.stroke(); c.globalAlpha = 1;
    }
    c.restore();
  }

  /* ── weapons ─────────────────────────────────────────────────────────── */

  /* Authored weapons (`cw_*`) live only in the owning player's save, so the
     renderer resolves their archetype kind, core colour and silhouette from the
     synced snapshot instead of a static catalogue. */
  const CUSTOM_ARCHETYPE_SHAPES = {
    sword: 'sword', greatsword: 'greatsword', daggers: 'dagger', spear: 'spear',
    bow: 'bow', staff: 'staff',
  };
  function customWeaponMeta(id, ownerId) {
    const empty = { kind: '', color: '', shape: '' };
    if (!id || !/^cw_/.test(String(id))) return empty;
    const pools = [];
    if (typeof snap !== 'undefined' && snap && Array.isArray(snap.players)) pools.push(...snap.players);
    if (typeof me === 'function') {
      const own = me();
      if (own) pools.push(own);
    }
    for (const row of pools) {
      if (!row) continue;
      if (ownerId && row.id && row.id !== ownerId) continue;
      const spec = row.custom_weapons?.[id] || row.weapon_catalog?.[id];
      if (!spec) continue;
      const archetype = spec.archetype || '';
      return {
        kind: spec.kind || (archetype === 'bow' ? 'bow' : archetype === 'staff' ? 'staff' : 'melee'),
        color: spec.color || '',
        shape: CUSTOM_ARCHETYPE_SHAPES[archetype] || (spec.kind === 'bow' ? 'bow' : spec.kind === 'staff' ? 'staff' : 'sword'),
      };
    }
    return empty;
  }

    /* ── harvesting tool: the hand works the node, the blade stays sheathed ── */
  function drawGatherTool(c, kind, t, handX, handY, reach) {
    const pull = clamp(reach == null ? .5 : reach, 0, 1);
    c.save();
    c.translate(handX, handY);
    // The tool points down-and-forward at the node (+x is the facing side), so
    // the local +y handle has to swing clockwise; the pull lifts it back up.
    c.rotate(-.72 + pull * .55);
    if (kind === 'herb') {
      P(c, -.9, -3, 1.8, 11, '#6b4d2f');
      c.strokeStyle = '#d3ddd4'; c.lineWidth = 1.7; c.lineCap = 'round';
      c.beginPath(); c.arc(.4, 2.4, 5.4, Math.PI * .18, Math.PI * 1.15); c.stroke();
      c.strokeStyle = '#ffffff88'; c.lineWidth = .8;
      c.beginPath(); c.arc(.4, 2.4, 5.4, Math.PI * .35, Math.PI * .95); c.stroke();
    } else if (kind === 'wood') {
      P(c, -1.1, -4, 2.2, 14, '#7a5a36');
      P(c, -1.1, -4, .8, 14, '#9b7548');
      poly(c, [[-5.2, 9.4], [5.2, 9.4], [4.4, 14.2], [-4.4, 14.2]], '#c9d5cf', '#2b3630', .7);
      P(c, 2.6, 9.4, 2.6, 4.8, '#eef7f1');
    } else {
      // pick for ore and crystals
      P(c, -1.1, -5, 2.2, 15, '#7a5a36');
      c.strokeStyle = '#ccd8d2'; c.lineWidth = 2.1; c.lineCap = 'round';
      c.beginPath(); c.moveTo(-6.4, 10.6); c.quadraticCurveTo(0, 7.4, 6.4, 10.2); c.stroke();
      c.strokeStyle = '#ffffff77'; c.lineWidth = .8;
      c.beginPath(); c.moveTo(-5.4, 9.2); c.quadraticCurveTo(0, 6.4, 5.6, 8.8); c.stroke();
    }
    ell(c, 0, -1.2, 2, 2, '#c79b74');
    c.restore();
  }

  function drawHeldWeapon(c, id, kind, trim, swing, local, t, handX, handY, pose) {
    const ps = pose || {};
    // Authored weapons carry their own core colour, which wins over name heuristics.
    const coreCol = /^#[0-9a-f]{6}$/i.test(String(ps.core || '')) ? ps.core : '';
    const glowCol = coreCol || (/frost|ice/.test(id) ? '#a8ecff' : /ember|flame/.test(id) ? '#ffb066' : /void|astral/.test(id) ? '#e0b0ff' : /storm/.test(id) ? '#8fe0ff' : local ? '#ffe6a3' : trim);
    const px = handX === undefined ? 9 : handX;
    const py = handY === undefined ? -13 : handY;
    c.save();
    c.translate(px, py);

    if (kind === 'staff') {
      const raised = ps.cast > 0 ? -0.06 : 0.1 + swing * -.25;
      c.rotate(raised);
      P(c, -1.3, -44, 2.6, 54, '#5a4630');
      P(c, -1.3, -44, .9, 54, '#8a6a44');
      P(c, -3.4, 8, 6.8, 3, '#3f3020');
      c.translate(0, -46);
      const flare = 1 + (ps.cast || 0) * 1.4;
      c.save(); c.shadowColor = glowCol; c.shadowBlur = 12 + (ps.cast || 0) * 14;
      poly(c, [[0, -7 * flare], [4.4 * flare, 0], [0, 6 * flare], [-4.4 * flare, 0]], glowCol, '#ffffff', .9);
      ell(c, -.6, -.6, 1.8 * flare, 1.8 * flare, '#ffffff');
      c.restore();
      c.strokeStyle = glowCol + '99'; c.lineWidth = 1;
      c.beginPath(); c.arc(0, 0, 8 + (ps.cast || 0) * 4, 0, TAU); c.stroke();
      if (ps.charge > .02) {
        c.strokeStyle = `rgba(255,240,190,${.25 + ps.charge * .5})`; c.lineWidth = 1.6;
        c.beginPath(); c.arc(0, 0, 10 + ps.charge * 5, -Math.PI / 2, -Math.PI / 2 + TAU * ps.charge); c.stroke();
      }
      c.restore();
      return;
    }

    if (kind === 'bow') {
      const aim = ps.aim || 0;
      c.rotate(aim > 0 ? -.02 : .04 + (aim > 0 ? 0 : 0));
      const pull = Math.max(aim, ps.charge || 0, swing > .05 ? swing : 0);
      c.strokeStyle = '#7a5a38'; c.lineWidth = 2.8;
      c.beginPath(); c.arc(-1, -5, 10, -1.24, 1.24); c.stroke();
      c.strokeStyle = '#c9a25a'; c.lineWidth = 1.2;
      c.beginPath(); c.arc(-1, -5, 10, -1.24, 1.24); c.stroke();
      c.strokeStyle = '#efe8cf'; c.lineWidth = .9;
      c.beginPath();
      c.moveTo(2.4, -14.7 + pull * 2.4); c.lineTo(2.4 + pull * 5, -5); c.lineTo(2.4, 4.7 - pull * 2.4);
      c.stroke();
      if (pull > .05) {
        c.strokeStyle = '#d8e4c8'; c.lineWidth = 1.1;
        c.beginPath(); c.moveTo(2.4 + pull * 5, -5); c.lineTo(19, -5); c.stroke();
        poly(c, [[19, -5], [14.6, -7.4], [14.6, -2.6]], '#e8f2e8');
        poly(c, [[21.6, -5], [18.4, -6.6], [18.4, -3.4]], '#b8c8b8');
      }
      P(c, -.8, 2, 5, 2.4, '#6b4d2f');
      c.restore();
      return;
    }

    const shape = ps.shape || '';
    const heavy = shape === 'greatsword' || shape === 'spear'
      || /greatsword|war_maul|warhammer|obsidian_axe|axe|halberd|glaive|scythe|colossus|spear/.test(id);
    const blazing = !!coreCol || /ember|flamberge|astral|void|frost|moon|storm/.test(id);
    const toolSwing = ps.tool;
    const wind = (ps.charge || 0) * .8;
    const base = .34 + wind;
    // the release only exists after the wind-up, so the blade sweeps forward
    const rot = toolSwing !== null && toolSwing !== undefined
      ? toolSwing
      : base + Math.max(0, swing - .36) * 2.9;
    c.rotate(rot);
    P(c, -1.7, -2, 3.4, 9.4, '#6b4d2f');
    P(c, -1.7, -2, 1.2, 9.4, '#8a6a44');
    P(c, -5, -3.6, 10, 2.3, '#b79a5e');
    P(c, -1.4, 7.4, 2.8, 2.6, '#8a6a44');
    const len = heavy ? 24 : 20;
    const bladeGrad = c.createLinearGradient(-3, 0, 3, -len);
    if (coreCol) {
      bladeGrad.addColorStop(0, shadeColor(coreCol, -52));
      bladeGrad.addColorStop(.55, coreCol);
      bladeGrad.addColorStop(1, shadeColor(coreCol, 58));
    } else {
      bladeGrad.addColorStop(0, '#8ba39f'); bladeGrad.addColorStop(.55, '#cddeda'); bladeGrad.addColorStop(1, '#f8fffa');
    }
    c.fillStyle = bladeGrad;
    c.beginPath();
    c.moveTo(-2.6, 0); c.lineTo(-2, -len); c.lineTo(0, -len - 3.4); c.lineTo(2, -len); c.lineTo(2.6, 0);
    c.closePath(); c.fill();
    c.strokeStyle = blazing ? glowCol : '#243028'; c.lineWidth = .9;
    if (blazing) { c.shadowColor = glowCol; c.shadowBlur = 9; }
    c.stroke(); c.shadowBlur = 0;
    P(c, -.7, -len + 3, 1.2, len - 6, '#ffffff77');
    if (shape) {
      // rune sigil at the base of an authored blade
      c.save(); c.shadowColor = glowCol; c.shadowBlur = 6; c.fillStyle = glowCol;
      if (shape === 'spear') c.fillRect(-1.2, -len * .62, 2.4, 6);
      else if (shape === 'dagger') c.fillRect(-1, -len * .5, 2, 4);
      else c.fillRect(-1.4, -len * .55, 2.8, 5);
      c.restore();
    }
    // sharp glint that runs up the edge as the swing charges
    const charge = ps.charge || 0;
    if (charge > .03) {
      const gy = -len + 4 + (1 - charge) * (len - 8);
      c.save(); c.globalAlpha = .35 + charge * .55;
      c.fillStyle = '#fffbe6'; c.shadowColor = '#ffe6a3'; c.shadowBlur = 8;
      c.fillRect(-1.9, gy, 1.1, len * .35 + 2);
      c.restore();
    }
    c.restore();
  }

  function lighten(hex, amt) { return shadeColor(hex, amt); }
  function darken(hex, amt) { return shadeColor(hex, -amt); }
  function shadeColor(hex, amt) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return hex;
    const n = parseInt(m[1], 16);
    const r = Math.max(0, Math.min(255, ((n >> 16) & 255) + amt));
    const g = Math.max(0, Math.min(255, ((n >> 8) & 255) + amt));
    const b = Math.max(0, Math.min(255, (n & 255) + amt));
    return `rgb(${r},${g},${b})`;
  }

  /* ── scenery ─────────────────────────────────────────────────────────── */
  const OBSTACLE_PALETTE = {
    camp: ['#24401f', '#3f6b34', '#77a154'], forest: ['#1e3b28', '#386b3b', '#6fa256'],
    marsh: ['#1f3e34', '#37665a', '#6f9a72'], ruins: ['#3b3a2c', '#6b6547', '#9b8f63'],
    glacier: ['#345c6b', '#6fa6b4', '#c2e6ea'], rift: ['#2b2145', '#544186', '#a47bd6'],
    abyss: ['#232a4a', '#475387', '#8398d0'], obsidian: ['#241b2e', '#4b3559', '#93689f'],
    garden: ['#20452d', '#3f7444', '#93c26b'],
  };
  function drawObstacle(c, ob, now, rid) {
    const pal = OBSTACLE_PALETTE[rid] || OBSTACLE_PALETTE.forest;
    const sc = ob.scale || 1;
    const sway = Math.sin(now / 900 + (ob.variant || 0) * 8) * (ob.kind === 'tree' ? 1.4 : .5);
    c.save(); c.translate(ob.x, ob.y);
    c.save(); c.translate(0, 2); c.scale(1, .38);
    ell(c, 0, 0, 16 * sc, 6 * sc, '#00000044'); c.restore();
    switch (ob.kind) {
      case 'tree': {
        // Trees read as a canopy above the hero, not a shrub at their feet.
        const h = (ob.h || 46) * 1.42;
        // trunk with flared roots
        P(c, -3.6 * sc, -h * .58, 7.2 * sc, h * .6, '#4a3324');
        P(c, -1.6 * sc, -h * .58, 2.4 * sc, h * .6, '#6b4a2e');
        poly(c, [[-3.6 * sc, -2], [-8 * sc, 2], [-3.2 * sc, 0], [0, 2], [3.2 * sc, 0], [8 * sc, 2], [3.6 * sc, -2]], '#3c2a1c');
        c.save(); c.translate(sway, -h * .58);
        const w = h * .5, hh = h * .5;
        // dark silhouette: pointed broadleaf crown
        c.beginPath();
        c.moveTo(0, -hh * 1.12);
        c.quadraticCurveTo(w * 1.05, -hh * .8, w * .92, -hh * .22);
        c.quadraticCurveTo(w * .8, hh * .22, w * .34, hh * .3);
        c.quadraticCurveTo(0, hh * .4, -w * .34, hh * .3);
        c.quadraticCurveTo(-w * .8, hh * .22, -w * .92, -hh * .22);
        c.quadraticCurveTo(-w * 1.05, -hh * .8, 0, -hh * 1.12);
        c.closePath();
        c.fillStyle = pal[0]; c.fill();
        c.strokeStyle = '#0e1a11'; c.lineWidth = 1.2; c.stroke();
        // mid layer
        c.beginPath();
        c.moveTo(0, -hh * .95);
        c.quadraticCurveTo(w * .82, -hh * .62, w * .66, -hh * .1);
        c.quadraticCurveTo(w * .4, hh * .2, 0, hh * .22);
        c.quadraticCurveTo(-w * .4, hh * .2, -w * .66, -hh * .1);
        c.quadraticCurveTo(-w * .82, -hh * .62, 0, -hh * .95);
        c.closePath();
        c.fillStyle = pal[1]; c.fill();
        // lit crown
        c.beginPath();
        c.moveTo(-w * .1, -hh * .92);
        c.quadraticCurveTo(w * .5, -hh * .62, w * .3, -hh * .12);
        c.quadraticCurveTo(0, hh * .1, -w * .34, -hh * .08);
        c.quadraticCurveTo(-w * .6, -hh * .55, -w * .1, -hh * .92);
        c.fillStyle = pal[2]; c.fill();
        // leaf clumps on the silhouette
        for (let i = 0; i < 6; i++) {
          const a = i / 6 * TAU + (ob.variant || 0) * 4;
          ell(c, Math.cos(a) * w * .58, -hh * .2 + Math.sin(a) * hh * .34, w * .19, hh * .16, i % 2 ? pal[2] : pal[1]);
        }
        ell(c, -w * .22, -hh * .5, w * .22, hh * .16, '#ffffff1c');
        for (let i = 0; i < 3; i++) ell(c, -8 + i * 9, -hh * .1 + (i % 2) * 8, 1.6, 1.6, pal[3] || '#d9a25a');
        c.restore();
        break;
      }
      case 'bush': {
        const h = (ob.h || 16) * sc;
        c.save(); c.translate(sway, 0);
        ell(c, 0, -h * .35, 14 * sc, h * .55, pal[1]);
        c.strokeStyle = '#101c12'; c.lineWidth = 1;
        c.beginPath(); c.ellipse(0, -h * .35, 14 * sc, h * .55, 0, 0, TAU); c.stroke();
        ell(c, -8 * sc, -h * .3, 6.5 * sc, h * .38, pal[0]);
        ell(c, 8 * sc, -h * .32, 6.5 * sc, h * .4, pal[0]);
        ell(c, 0, -h * .6, 7 * sc, h * .36, pal[2]);
        ell(c, -3 * sc, -h * .66, 4 * sc, h * .2, '#ffffff22');
        for (let i = 0; i < 3; i++) {
          ell(c, -7 + i * 7, -h * .48 + (i % 2) * 3, 1.5, 1.5, i % 2 ? '#e8c27a' : '#d9a25a');
        }
        c.restore();
        break;
      }
      case 'rock': {
        const h = (ob.h || 18) * sc;
        poly(c, [[-16 * sc, 0], [-13 * sc, -h * .72], [-5 * sc, -h], [7 * sc, -h * .86], [15 * sc, -h * .22], [12 * sc, 2]], '#6b6a58', '#26261f', 1.4);
        poly(c, [[-12 * sc, -h * .7], [-5 * sc, -h * .94], [6 * sc, -h * .8], [3 * sc, -h * .42], [-8 * sc, -h * .48]], '#8b8872');
        poly(c, [[3 * sc, -h * .78], [13 * sc, -h * .3], [6 * sc, -h * .1], [1 * sc, -h * .5]], '#585848');
        P(c, -9 * sc, -h * .3, 9 * sc, 1.6, '#ffffff14');
        ell(c, -7 * sc, -h * .8, 4 * sc, 2 * sc, '#6f8f4c');
        break;
      }
      case 'pillar': {
        const h = (ob.h || 58) * sc;
        P(c, -9 * sc, -h, 18 * sc, h, '#5c5748');
        P(c, -9 * sc, -h, 6 * sc, h, '#6e6857');
        P(c, -12 * sc, -h - 5, 24 * sc, 6, '#7a735c');
        P(c, -13 * sc, -7, 26 * sc, 7, '#484436');
        P(c, -4 * sc, -h + 8, 2.4 * sc, h - 14, '#00000033');
        P(c, 3 * sc, -h + 10, 2 * sc, h - 18, '#00000022');
        c.strokeStyle = '#2e2b22'; c.lineWidth = 1;
        for (let i = 0; i < 3; i++) {
          const y0 = -h * (.25 + i * .22);
          c.beginPath(); c.moveTo(-8 * sc, y0); c.lineTo(-2 * sc, y0 + 6); c.lineTo(2 * sc, y0 + 2); c.stroke();
        }
        if (rid === 'rift' || rid === 'abyss' || rid === 'obsidian') {
          c.save(); c.shadowColor = pal[2]; c.shadowBlur = 9;
          P(c, -1.2 * sc, -h * .72, 2.4 * sc, h * .3, pal[2] + 'cc'); c.restore();
        }
        ell(c, 0, -h - 5, 9 * sc, 2.4 * sc, '#8a8368');
        break;
      }
      case 'crystal': {
        const h = (ob.h || 34) * sc;
        c.save(); c.shadowColor = pal[2]; c.shadowBlur = 12;
        // side shards
        poly(c, [[-9 * sc, -h * .5], [-15 * sc, -h * .1], [-8 * sc, 2], [-3 * sc, -h * .2]], pal[0], '#132024', 1);
        poly(c, [[9 * sc, -h * .62], [16 * sc, -h * .16], [8 * sc, 2], [4 * sc, -h * .25]], pal[0], '#132024', 1);
        // main shard with facets
        poly(c, [[0, -h], [-8 * sc, -h * .32], [-4 * sc, 3], [5 * sc, 3], [9 * sc, -h * .36]], pal[1], '#132024', 1.2);
        poly(c, [[0, -h], [0, 3], [9 * sc, -h * .36]], pal[2] + 'bb');
        poly(c, [[0, -h], [-8 * sc, -h * .32], [-4 * sc, 3]], '#ffffff22');
        seg(c, -1 * sc, -h * .85, -1 * sc, -h * .2, '#ffffff88', 1.2);
        c.restore();
        break;
      }
      case 'reed': {
        const h = (ob.h || 22) * sc;
        for (let i = -2; i <= 2; i++) {
          const lean = Math.sin(now / 1000 + i + (ob.variant || 0) * 5) * 2.4;
          seg(c, i * 4 * sc, 0, i * 4 * sc + lean, -h + Math.abs(i) * 3, pal[1], 1.6);
          ell(c, i * 4 * sc + lean, -h + Math.abs(i) * 3, 1.6, 3.4, pal[0], lean * .05);
        }
        break;
      }
      case 'stump': {
        ell(c, 0, -2, 12 * sc, 4.5, '#5a4329');
        P(c, -11 * sc, -12 * sc, 22 * sc, 11 * sc, '#4a3624');
        ell(c, 0, -12 * sc, 11 * sc, 4.2 * sc, '#8a6a44');
        ell(c, 0, -12 * sc, 6 * sc, 2.2 * sc, '#a3835a');
        break;
      }
    }
    if (ob.kind === 'tree' && rid === 'marsh') {
      seg(c, 0, -8, -10, -22, '#927d54', 1.4);
    }
    c.restore();
  }

  function drawNode(c, n, now) {
    const pulse = .5 + .5 * Math.sin(now / 320 + seedOf(n.id) * 9);
    const x = 0;
    c.save(); c.translate(n.x, n.y);
    c.save(); c.translate(0, 2); c.scale(1, .35); ell(c, 0, 0, 15, 5, '#00000044'); c.restore();
    if (n.kind === 'wood') {
      P(c, -6, -14, 12, 15, '#7a5a36'); P(c, -3, -14, 3, 15, '#9c7648');
      P(c, -12, -9, 7, 4, '#6b4c2e'); P(c, 5, -3, 7, 4, '#6b4c2e');
      ell(c, 0, -14, 6, 2.4, '#b18b57');
    } else if (n.kind === 'herb') {
      c.strokeStyle = '#8fd06a'; c.lineWidth = 1.6;
      for (let i = -2; i <= 2; i++) seg(c, 0, 0, i * 4, -12 - Math.abs(i) * 2, '#7dbd5c', 1.6);
      for (let i = -2; i <= 2; i++) ell(c, i * 5, -13 - Math.abs(i) * 2, 2.4, 1.6, i % 2 ? '#b8ee8a' : '#93d06a');
      c.save(); c.shadowColor = '#a8ff9a'; c.shadowBlur = 10; ell(c, 0, -16, 2.4, 2.4, '#eaffcf'); c.restore();
    } else if (n.kind === 'ore' || n.kind === 'crystal' || n.kind === 'shard') {
      const col = n.kind === 'crystal' ? '#7fe8de' : n.kind === 'shard' ? '#c49be8' : '#9fb8bd';
      c.save(); c.shadowColor = col; c.shadowBlur = 10 + pulse * 8;
      poly(c, [[0, -20 - pulse * 2], [-9, -5], [0, 2], [9, -5]], col, '#ffffff55', .8);
      poly(c, [[0, -20], [0, 2], [9, -5]], '#ffffff66');
      c.restore();
      P(c, -9, -3, 18, 5, '#4a5450');
    } else {
      c.save(); c.shadowColor = '#a8ffd8'; c.shadowBlur = 9; ell(c, 0, -8, 6, 7, '#8fe8c8'); c.restore();
    }
    if (pulse > .6) {
      c.globalAlpha = (pulse - .6) * 1.4;
      c.strokeStyle = '#ffffff88'; c.lineWidth = 1;
      c.beginPath(); c.arc(0, -8, 12 + (1 - pulse) * 10, 0, TAU); c.stroke();
      c.globalAlpha = 1;
    }
    c.restore();
  }

  function drawWaystone(c, portal, now, rid) {
    const t = now / 1000, pulse = .5 + .5 * Math.sin(t * 2 + seedOf(portal.id) * 6);
    c.save(); c.translate(portal.x, portal.y);
    c.save(); c.translate(0, 2); c.scale(1, .34); ell(c, 0, 0, 32, 11, '#00000055'); c.restore();
    // arch
    P(c, -28, -52, 9, 54, '#6a6a78'); P(c, 19, -52, 9, 54, '#5c5c6a');
    P(c, -32, -58, 17, 8, '#8a8a98'); P(c, 15, -58, 17, 8, '#7a7a88');
    P(c, -12, -62, 24, 6, '#9a9aa8');
    c.save(); c.shadowColor = '#bda6ff'; c.shadowBlur = 10;
    P(c, -25, -44, 3, 40, '#a890ff' + '99'); P(c, 22, -44, 3, 40, '#a890ff' + '99'); c.restore();
    // portal glow
    glow(c, 0, -28, 30 + pulse * 8, '#a98cff', .35);
    c.save(); c.globalAlpha = .6 + pulse * .3; c.strokeStyle = '#e8dcff'; c.lineWidth = 1.4;
    c.beginPath(); c.ellipse(0, -28, 17 + pulse * 3, 25 + pulse * 4, 0, 0, TAU); c.stroke(); c.restore();
    c.restore();
  }

  function drawPowerSite(c, site, now) {
    const pulse = .5 + .5 * Math.sin(now / 420);
    c.save(); c.translate(site.x, site.y);
    c.save(); c.globalCompositeOperation = 'lighter'; c.globalAlpha = .07 + pulse * .05;
    ell(c, 0, 0, site.radius, site.radius * .66, '#e8d79a'); c.restore();
    c.strokeStyle = '#e8d79a55'; c.lineWidth = 1.6; c.setLineDash([9, 11]);
    c.beginPath(); c.ellipse(0, 0, 42 + pulse * 4, 22 + pulse * 2, 0, 0, TAU); c.stroke(); c.setLineDash([]);
    for (let i = 0; i < 4; i++) {
      const a = now / 1400 + i * TAU / 4;
      const x = Math.cos(a) * 32, y = Math.sin(a) * 18;
      c.save(); c.shadowColor = '#ffe9a8'; c.shadowBlur = 8; ell(c, x, y - 6, 1.8, 1.8, '#fff3c4'); c.restore();
    }
    c.restore();
  }

  /* ── effects ─────────────────────────────────────────────────────────── */
  const ELEMENT_PALETTE = {
    'Огонь': ['#ff7a3d', '#ffc45c', '#fff2b0'], 'Молния': ['#fff078', '#7be9ff', '#fff9d5'],
    'Исцеление': ['#60e7b0', '#caffdd', '#ffffff'], 'Терни': ['#8bdc62', '#d3ff84', '#f3ffd0'],
    'Яд': ['#7df06b', '#d4ff73', '#efffb4'], 'Лёд': ['#65dfff', '#b5f5ff', '#ffffff'],
    'Всплеск': ['#bd75ff', '#f09cff', '#fff0ff'], 'Звёзды': ['#ffb347', '#fff08a', '#ffffff'],
    'Тень': ['#9162dd', '#d7a5ff', '#fff0ff'], 'Эхо': ['#52d7d0', '#a7fff0', '#fffbd2'],
    'Душа': ['#fa77c9', '#ffc5eb', '#ffffff'], 'Аркана': ['#b678ff', '#69e8ff', '#fff0c2'],
  };
  function paletteFor(kind) { return ELEMENT_PALETTE[kind] || ELEMENT_PALETTE['Аркана']; }

  /* ── impact flourish pool (client-side, purely cosmetic) ────────────── */
  const worldFx = [];
  const FX_LIFE = { hit: 430, crit: 680, cast: 760, level: 1500, dodge: 420, pickup: 560, heal: 820 };

  function spawnWorldFx(kind, x, y, opts) {
    const o = opts || {};
    worldFx.push({
      kind, x, y,
      color: o.color || '#ffe6a3',
      color2: o.color2 || '#fff6d8',
      power: clamp(o.power == null ? 1 : o.power, .2, 3),
      radius: o.radius || 46,
      start: (typeof performance !== 'undefined' ? performance.now() : Date.now()),
    });
    if (worldFx.length > 70) worldFx.shift();
  }

  function punch(amount) { const a = amount == null ? .03 : Math.max(0, amount); VIEW.punch = Math.min(.075, VIEW.punch + a); }
  function freeze(ms) { VIEW.freeze = Math.min(190, Math.max(VIEW.freeze, ms || 60)); }

  function drawWorldFx(c, now) {
    if (!worldFx.length) return;
    for (let i = worldFx.length - 1; i >= 0; i--) {
      const fx = worldFx[i];
      const life = FX_LIFE[fx.kind] || 500;
      const t = (now - fx.start) / life;
      if (t >= 1 || t < 0) { if (t >= 1) worldFx.splice(i, 1); continue; }
      const e = easeOut(t);
      const k = fx.power;
      c.save();
      c.translate(fx.x, fx.y);
      if (fx.kind === 'hit' || fx.kind === 'crit') {
        c.globalCompositeOperation = 'lighter';
        // ground shockwave: one bright ring, one soft echo, both squashed
        c.globalAlpha = (1 - t) * .7;
        c.strokeStyle = fx.color2; c.lineWidth = (2.8 - 2 * t) * k;
        c.beginPath(); c.ellipse(0, 0, (8 + fx.radius * e) * k, (4 + fx.radius * e * .42) * k, 0, 0, TAU); c.stroke();
        c.globalAlpha = (1 - t) * .38;
        c.strokeStyle = fx.color; c.lineWidth = 1.4;
        c.beginPath(); c.ellipse(0, 0, (4 + fx.radius * e * .58) * k, (2 + fx.radius * e * .26) * k, 0, 0, TAU); c.stroke();
        // four thin light spokes, fading fast — reads as force, not a wheel
        if (t < .45) {
          c.globalAlpha = (1 - t / .45) * .5;
          c.strokeStyle = fx.color2; c.lineWidth = 1.2;
          for (let n = 0; n < 4; n++) {
            const ang = n / 4 * TAU + .4;
            const r0 = fx.radius * e * .7, r1 = r0 + 12 * k;
            c.beginPath();
            c.moveTo(Math.cos(ang) * r0, Math.sin(ang) * r0 * .4);
            c.lineTo(Math.cos(ang) * r1, Math.sin(ang) * r1 * .4);
            c.stroke();
          }
        }
        // white flash: a small disc plus a cross flare
        if (t < .28) {
          const ft = t / .28;
          c.globalAlpha = (1 - ft) * .8;
          c.fillStyle = '#fffdf2';
          c.beginPath(); c.arc(0, -6, Math.max(.8, (5.5 - ft * 12) * k), 0, TAU); c.fill();
          c.globalAlpha = (1 - ft) * .55;
          const arm = 10 + 24 * ft;
          c.beginPath();
          c.moveTo(-arm * k, -6); c.lineTo(arm * k, -6);
          c.moveTo(0, -6 - arm * .7 * k); c.lineTo(0, -6 + arm * .7 * k);
          c.lineWidth = 1.6; c.strokeStyle = '#fffdf2'; c.stroke();
        }
        // dust kicked up on the ground line
        c.globalCompositeOperation = 'source-over';
        c.globalAlpha = (1 - t) * .3;
        for (let n = 0; n < 4; n++) {
          const a = n * 1.7 + fx.start * .0007;
          ell(c, Math.cos(a) * fx.radius * e * .9, 2 + Math.sin(a) * fx.radius * .2, 3 * (1 - t), 1.5 * (1 - t), fx.color);
        }
      } else if (fx.kind === 'cast') {
        c.globalAlpha = (1 - t) * .75;
        c.strokeStyle = fx.color; c.lineWidth = 2.2 * (1 - t * .6);
        c.beginPath(); c.arc(0, 0, 10 + fx.radius * e, 0, TAU); c.stroke();
        c.globalAlpha = (1 - t) * .5;
        c.strokeStyle = fx.color2; c.lineWidth = 1.3;
        c.beginPath(); c.arc(0, 0, 6 + fx.radius * e * .62, 0, TAU); c.stroke();
        // runes
        for (let n = 0; n < 6; n++) {
          const a = fx.start * .002 + n * TAU / 6;
          const r = 12 + fx.radius * e * .78;
          c.globalAlpha = (1 - t) * .85;
          P(c, Math.cos(a) * r - 1.4, Math.sin(a) * r * .55 - 1.4, 2.8, 2.8, fx.color2);
        }
        // rising motes
        c.globalAlpha = (1 - t) * .7;
        for (let n = 0; n < 7; n++) {
          const a = n * 2.1 + fx.start * .001;
          ell(c, Math.cos(a) * 14, -10 - e * 34 - n * 2, 1.6, 1.6, n % 2 ? fx.color : fx.color2);
        }
      } else if (fx.kind === 'level') {
        const col = '#ffe08c';
        c.globalCompositeOperation = 'lighter';
        c.globalAlpha = (1 - t) * .5;
        const grad = c.createLinearGradient(0, -150, 0, 8);
        grad.addColorStop(0, 'rgba(255,224,140,0)');
        grad.addColorStop(.5, 'rgba(255,224,140,.42)');
        grad.addColorStop(1, 'rgba(255,246,216,.8)');
        c.fillStyle = grad;
        c.fillRect(-16 - 6 * e, -150, 32 + 12 * e, 158);
        for (let n = 0; n < 2; n++) {
          const p = clamp(t * 1.3 - n * .18, 0, 1);
          c.globalAlpha = (1 - p) * .8;
          c.strokeStyle = n ? '#fff6d8' : col; c.lineWidth = 2;
          c.beginPath(); c.ellipse(0, 1, 14 + 40 * p, 5 + 14 * p, 0, 0, TAU); c.stroke();
        }
        c.globalAlpha = (1 - t) * .9;
        for (let n = 0; n < 10; n++) {
          const a = n * 2.4 + fx.start * .0015;
          ell(c, Math.cos(a) * (16 + 20 * e), -20 - e * 60 + Math.sin(a) * 6, 1.8, 1.8, n % 2 ? '#ffe08c' : '#fff6d8');
        }
      } else if (fx.kind === 'dodge') {
        c.globalAlpha = (1 - t) * .5;
        c.strokeStyle = fx.color; c.lineWidth = 2.4 * (1 - t);
        for (let n = 0; n < 3; n++) {
          const off = (n - 1) * 7;
          c.beginPath();
          c.moveTo(-14 - 20 * e, off - 10);
          c.lineTo(6 + 8 * e, off - 14);
          c.stroke();
        }
        c.globalAlpha = (1 - t) * .35;
        ell(c, -6, 2, 22 * e, 6 * e, fx.color);
      } else if (fx.kind === 'pickup' || fx.kind === 'heal') {
        c.globalAlpha = (1 - t) * .85;
        for (let n = 0; n < 5; n++) {
          const a = n * 1.6 + fx.start * .001;
          const y = -e * (16 + n * 6);
          P(c, Math.cos(a) * 8 - 1.5, y, 3, 3, n % 2 ? fx.color : fx.color2);
        }
        c.globalAlpha = (1 - t) * .5;
        c.strokeStyle = fx.color; c.lineWidth = 1.4;
        c.beginPath(); c.ellipse(0, 1, 10 + 10 * e, 4 + 3 * e, 0, 0, TAU); c.stroke();
      }
      c.restore();
    }
  }

  /* Punchier melee arcs: three tapered layers plus a white leading edge. */
  function drawSlashFx(c, sw, now) {
    const started = sw.started || now;
    const dur = sw.action === 'cast' ? 520 : 340;
    const t = (now - started) / dur;
    if (t < 0 || t > 1) return;
    const a = easeOut(t);
    const charge = clamp(Number(sw.charge) || 0, 0, 1);
    const heavy = sw.weapon_kind === 'melee' && (charge > .55 || /axe|maul|greatsword|halberd|scythe/.test(sw.weapon || ''));
    const ang = Math.atan2(sw.aim_y, sw.aim_x);
    const half = .62 + charge * .34;
    const R = 42 + charge * 30;
    const colors = { warrior: '#ffe6a3', ranger: '#c9ef9a', mage: '#a6e8ff' }[sw.class] || '#ffe6a3';
    c.save(); c.globalCompositeOperation = 'lighter';
    c.translate(sw.x, sw.y - 10);
    // soft bloom behind the arc
    c.globalAlpha = (1 - t) * (heavy ? .1 : .06);
    glow(c, Math.cos(ang) * R * .64, Math.sin(ang) * R * .44, R * .8, colors, (1 - t) * (heavy ? .12 : .07));
    // tapered trails
    for (let i = 0; i < 4; i++) {
      const trail = Math.max(0, a - i * .13);
      if (trail <= 0) continue;
      const a0 = ang - half, a1 = ang - half + 2 * half * trail;
      const fade = 1 - t;
      c.globalAlpha = fade * (heavy ? .62 : .5) * (1 - i * .21);
      c.strokeStyle = i === 0 ? '#ffffff' : colors;
      c.lineWidth = (i === 0 ? 2.1 : 9 - i * 2.1) * (1 + charge * .5);
      c.lineCap = 'round';
      c.beginPath(); c.arc(0, 0, R + i * 3.5, a0, a1); c.stroke();
    }
    // leading edge spark burst + ground dust at the strike point
    const tipA = ang - half + 2 * half * a;
    const tx = Math.cos(tipA) * R, ty = Math.sin(tipA) * R;
    c.globalAlpha = (1 - t) * .95;
    glow(c, tx, ty, 16 + charge * 10, colors, .6);
    for (let i = 0; i < 8; i++) {
      const sa = tipA + (i - 3.5) * .14, sr = R + 2 + ((now / 8 + i * 13) % (12 + charge * 10));
      ell(c, Math.cos(sa) * sr, Math.sin(sa) * sr, 1.6 + charge, 1.6 + charge, i % 2 ? '#ffffff' : colors);
    }
    if (heavy && t < .6) {
      c.globalAlpha = (1 - t / .6) * .35;
      c.strokeStyle = '#fff6d8'; c.lineWidth = 1.4;
      c.beginPath(); c.arc(0, 2, R * .72, ang - half * .8, ang + half * .5); c.stroke();
    }
    c.restore();
  }

  function drawImpactRunes(c, fx, now) {
    const started = fx.until - 1500;
    const life = clamp((fx.until - now) / 1500, 0, 1);
    if (life <= 0) return;
    const t = 1 - life;
    const col = paletteFor(fx.kind || fx.spell);
    const r = fx.radius || 100;
    c.save(); c.globalCompositeOperation = 'lighter';
    c.translate(fx.x, fx.y);
    // shockwave rings
    for (let i = 0; i < 3; i++) {
      const p = clamp(t * 1.6 - i * .16, 0, 1);
      c.globalAlpha = (1 - p) * .65 * life;
      c.strokeStyle = col[i % 3]; c.lineWidth = 3 - i;
      c.beginPath(); c.arc(0, 0, r * (.18 + p * .9), 0, TAU); c.stroke();
    }
    // rotating rune circle
    c.globalAlpha = life * .8;
    c.strokeStyle = col[1]; c.lineWidth = 1.5;
    const sides = fx.kind === 'Молния' ? 8 : 6, rot = t * 2 + (fx.variant || 0) % 6;
    c.beginPath();
    for (let i = 0; i <= sides; i++) {
      const a = rot + i * TAU / sides, rr = r * .5;
      const x = Math.cos(a) * rr, y = Math.sin(a) * rr * .8;
      i ? c.lineTo(x, y) : c.moveTo(x, y);
    }
    c.stroke();
    // motes
    for (let i = 0; i < 22; i++) {
      const a = i * 2.4 + t * 2.6, rr = r * (.25 + ((i * 37) % 100) / 130 * (0.4 + t * .8));
      ell(c, Math.cos(a) * rr, Math.sin(a) * rr * .75, 1.4 + (i % 3) * .6, 1.4 + (i % 3) * .6, col[i % 3]);
    }
    c.restore();
    if (fx.name) {
      c.save(); c.globalAlpha = Math.min(1, life * 1.5);
      label(c, fx.name, fx.x, fx.y - r * .55, col[2], 10);
      c.restore();
    }
  }

  function drawGroundEffect(c, f, now) {
    const rem = Number(f.remaining || 0), total = Number(f.duration || 1);
    const tele = Number(f.telegraph || 0);
    const col = f.kind === 'arrow_rain' ? '#d8ef9a' : f.kind === 'meteor' ? '#ff9a54' : f.kind === 'frost_nova' ? '#9fe8ff' : f.kind === 'shadow' ? '#c08aff' : '#ffb066';
    c.save(); c.translate(f.x, f.y);
    if (tele > 0) {
      const p = 1 - tele / Math.max(.01, total);
      c.globalAlpha = .16 + .16 * Math.sin(now / 70);
      ell(c, 0, 0, f.radius, f.radius * .62, col);
      c.globalAlpha = .8;
      c.strokeStyle = col; c.lineWidth = 2; c.setLineDash([7, 7]);
      c.beginPath(); c.ellipse(0, 0, f.radius * p, f.radius * .62 * p, 0, 0, TAU); c.stroke(); c.setLineDash([]);
    } else {
      c.globalAlpha = .2 + .08 * Math.sin(now / 120);
      ell(c, 0, 0, f.radius, f.radius * .6, col);
      c.globalAlpha = .65;
      c.strokeStyle = col; c.lineWidth = 1.5;
      c.beginPath(); c.ellipse(0, 0, f.radius, f.radius * .6, 0, 0, TAU); c.stroke();
      for (let i = 0; i < 7; i++) {
        const a = now / 700 + i * .9, rr = f.radius * (.35 + (i % 3) * .17);
        ell(c, Math.cos(a) * rr, Math.sin(a) * rr * .55, 2, 3.4, col);
      }
    }
    c.restore();
  }

  function drawArrowProjectile(c, a, now) {
    const ang = Math.atan2(a.vy || 0, a.vx || 0);
    const pal = a.spell_palette?.colors || paletteFor(a.spell_kind || a.element || 'Огонь');
    const speed = Math.hypot(a.vx || 0, a.vy || 0);
    c.save(); c.translate(a.x, a.y); c.rotate(ang);
    if (a.kind === 'arrow') {
      // fading motion trail behind the shaft
      c.globalAlpha = .3;
      c.strokeStyle = '#eef4e0'; c.lineWidth = 2.6;
      c.beginPath(); c.moveTo(-15, 0); c.lineTo(-42, 0); c.stroke();
      c.globalAlpha = .16;
      c.beginPath(); c.moveTo(-40, 0); c.lineTo(-66, 0); c.stroke();
      c.globalAlpha = 1;
      c.strokeStyle = '#e8dcc0'; c.lineWidth = 1.6;
      c.beginPath(); c.moveTo(-14, 0); c.lineTo(8, 0); c.stroke();
      poly(c, [[8, 0], [2, -3], [2, 3]], '#cfd8d2', '#eef5ef', .6);
      poly(c, [[-14, 0], [-18, -3.4], [-10, 0], [-18, 3.4]], '#b8d18a');
      c.restore(); return;
    }
    c.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 7; i++) {
      const p = i / 7;
      c.globalAlpha = (1 - p) * .5;
      c.fillStyle = pal[i % 3];
      const w = 8 * (1 - p * .6);
      ell(c, -6 - p * 24, Math.sin(now / 60 + i) * (1 + p * 2), w, w * .55, pal[i % 3]);
    }
    c.globalAlpha = 1;
    c.save(); c.shadowColor = pal[0]; c.shadowBlur = 16;
    ell(c, 0, 0, 5.5, 4.5, pal[1]);
    ell(c, 1.5, 0, 3, 2.6, pal[2]);
    c.restore();
    c.restore();
  }

  function drawThornField(c, f, now) {
    c.save(); c.translate(f.x, f.y);
    c.globalAlpha = .16; ell(c, 0, 0, f.radius, f.radius * .6, '#7ad46a');
    c.globalAlpha = .8; c.strokeStyle = '#9ef080'; c.lineWidth = 1.4;
    c.beginPath(); c.ellipse(0, 0, f.radius, f.radius * .6, 0, 0, TAU); c.stroke();
    for (let i = 0; i < 12; i++) {
      const a = i * TAU / 12 + Math.sin(now / 800 + i) * .1, rr = f.radius * .82;
      c.beginPath(); c.moveTo(Math.cos(a) * rr, Math.sin(a) * rr * .6);
      c.lineTo(Math.cos(a + .1) * (rr - 9), Math.sin(a + .1) * (rr - 9) * .6);
      c.stroke();
    }
    c.restore();
  }

  function drawDamageNumber(c, fx, now) {
    const left = fx.until - now;
    if (left <= 0) return;
    const p = 1 - left / 420;
    const y = fx.y - 26 - easeOut(p) * 26;
    c.save();
    const scale = p < .18 ? 1 + (0.18 - p) * 2.2 : 1;
    c.translate(fx.x, y); c.scale(scale, scale);
    c.font = `${fx.critical ? 'bold 15px' : 'bold 12px'} ui-monospace, monospace`;
    c.textAlign = 'center'; c.lineWidth = 3;
    c.strokeStyle = '#0a0f0b'; c.globalAlpha = Math.min(1, left / 120);
    c.strokeText(fx.text, 0, 0);
    c.fillStyle = fx.critical ? '#ffe27a' : '#fff2c8';
    c.fillText(fx.text, 0, 0);
    if (fx.critical) {
      c.globalAlpha *= .98;
      c.fillStyle = '#ffb04a'; c.font = 'bold 8px ui-monospace, monospace';
      c.fillText('КРИТ', 0, -11);
    }
    c.restore();
  }

  /* ── world renderer ──────────────────────────────────────────────────── */
  const playerViews = new Map();
  const mobViews = new Map();

  /* ── animation state ─────────────────────────────────────────────────── */
  // Explicit one-shot gestures pushed by the HUD (potion, weapon swap, cast).
  const gestures = new Map();
  function heroGesture(kind, id) {
    const key = id || (typeof myId !== 'undefined' && myId) || 'local';
    gestures.set(key, { kind, start: performance.now() });
  }
  function gestureEnvelope(id, kind, duration) {
    const g = gestures.get(id);
    if (!g || g.kind !== kind) return 0;
    const p = (performance.now() - g.start) / duration;
    if (p >= 1) { gestures.delete(id); return 0; }
    // quick in, hold, quick out
    return p < .22 ? p / .22 : p > .74 ? (1 - p) / .26 : 1;
  }
  window.heroGesture = heroGesture;

  function offsetParticle(x, y, color, count, speed, size, life) {
    if (typeof spawnParticles === 'function') spawnParticles(x, y, color, count, speed, size, life);
  }

  function playerVisual(q, now) {
    let v = playerViews.get(q.id);
    if (!v) {
      v = { x: q.x, y: q.y, walk: 0, move: 0, swing: 0, hurt: 0, last: now, weapon: q.weapon,
        hp: q.hp, mana: q.mana, swap: 0, cast: 0, aim: 0, shoot: 0, gather: 0,
        dust: 0, spark: 0, prevAttack: !!q.attack, run: !!q.run, sneak: !!q.sneak };
      playerViews.set(q.id, v);
      return v;
    }
    const dt = Math.max(.001, (now - v.last) / 1000); v.last = now;
    const pos = typeof entityPosition === 'function' ? entityPosition(q, now) : q;
    const dx = pos.x - v.x, dy = pos.y - v.y;
    const speed = Math.hypot(dx, dy) / dt;
    v.move = lerp(v.move || 0, speed, .25);
    if (speed > 6) v.walk += Math.min(1.6, speed / 150) * dt * 14;
    v.x = pos.x; v.y = pos.y;
    v.run = !!q.run; v.sneak = !!q.sneak;
    v.gather = q.gathering ? 1 : 0;

    // weapon swap: the old blade drops out of frame, the new one arrives
    if (q.weapon && q.weapon !== v.weapon) { v.weapon = q.weapon; v.swap = 1; }
    // flinch when hit
    if (q.hp !== undefined && v.hp !== undefined && q.hp < v.hp - .01) v.hurt = 1;
    v.hp = q.hp;
    // a sudden mana drop means a spell just left the staff
    if (q.mana !== undefined && v.mana !== undefined && v.mana - q.mana > 4) v.cast = 1;
    v.mana = q.mana;

    const bow = q.weapon_kind === 'bow' || /bow|longbow/.test(q.weapon || '');
    if (q.attack && bow) {
      v.aim = clamp(Number(q.attack.charge) || 0, 0, 1);
    } else {
      if (v.aim > .12) v.shoot = 1;
      v.aim = 0;
    }

    // swing: wind up with the charge, then snap forward on release
    if (q.attack) {
      v.swing = clamp(Number(q.attack.charge) || 0, 0, 1) * .35;
      v.prevAttack = true;
    } else {
      if (v.prevAttack) { v.swing = 1; v.prevAttack = false; }
      v.swing = Math.max(0, v.swing - dt * 5.2);
    }

    v.swap = Math.max(0, v.swap - dt * 2.6);
    v.hurt = Math.max(0, v.hurt - dt * 3.2);
    v.cast = Math.max(0, v.cast - dt * 1.5);
    v.shoot = Math.max(0, v.shoot - dt * 6);
    return v;
  }

  function mobVisual(m, now) {
    let v = mobViews.get(m.id);
    const pos = typeof entityPosition === 'function' ? entityPosition(m, now) : m;
    if (!v) {
      v = { x: pos.x, y: pos.y, walk: 0, move: 0, hp: m.hp, hurt: 0, atk: 0, last: now, fade: 1 };
      mobViews.set(m.id, v);
      return v;
    }
    const dt = Math.max(.001, (now - v.last) / 1000); v.last = now;
    const speed = Math.hypot(pos.x - v.x, pos.y - v.y) / dt;
    v.move = lerp(v.move || 0, speed, .3);
    if (speed > 4) v.walk += Math.min(1.6, speed / 120) * dt * 12;
    v.x = pos.x; v.y = pos.y;
    if (m.hp < v.hp - .01) v.hurt = .22;
    v.hp = m.hp;
    v.hurt = Math.max(0, v.hurt - dt);
    const tele = !!m.telegraphing;
    v.atk = lerp(v.atk || 0, tele ? .75 : 0, .2);
    return v;
  }

  function drawPlayer(c, q, now, oxUnused) {
    const vis = playerVisual(q, now);
    const local = q.id === myId;
    q = { ...q, x: vis.x, y: vis.y };
    const coatMap = {
      traveler: '#547c50', wolf_cloak: '#778d8d', moss_guard: '#8bb56b', marsh_armor: '#9c815e', moonweave: '#9bc8bd',
      ash_plate: '#a8aaa4', colossus_core: '#f49a60', glacier_mantle: '#8ee8f2', rift_plate: '#bd85ed', obsidian_shell: '#887090',
      starseer_robe: '#d2a4d7', elder_mantle: '#8ec884', leather_vest: '#8a6a44', chain_shirt: '#8d9599', bark_plate: '#6f8a4a',
      ember_mail: '#a25a3e', frostguard_plate: '#7fa9b8', void_cloak: '#5c4a7a',
    };
    const trimMap = {
      traveler: '#e6cf8f', wolf_cloak: '#a8d8c8', moss_guard: '#a8d878', marsh_armor: '#d8b878', moonweave: '#b8e8e0',
      ash_plate: '#e8d0b0', colossus_core: '#ffb078', glacier_mantle: '#c8f8ff', rift_plate: '#dcb0ff', obsidian_shell: '#bb9cc8',
      starseer_robe: '#f0c8f8', elder_mantle: '#c8f0a8', leather_vest: '#b89a6a', chain_shirt: '#c8d0d8', bark_plate: '#b8d890',
      ember_mail: '#ffb08a', frostguard_plate: '#c8f0ff', void_cloak: '#b8a0e0',
    };
    const coat = coatMap[q.gear] || '#547c50';
    const trim = trimMap[q.gear] || '#e6cf8f';
    const charge = q.attack ? clamp(Number(q.attack.charge) || 0, 0, 1) : 0;
    const gid = typeof myId !== 'undefined' && myId ? myId : 'local';
    const drink = local ? gestureEnvelope(gid, 'drink', 950) : 0;
    const castG = local ? gestureEnvelope(gid, 'cast', 700) : 0;
    const swapG = local ? gestureEnvelope(gid, 'swap', 500) : 0;
    const cast = Math.max(vis.cast, local ? castG : 0);
    const swap = Math.max(vis.swap, swapG);

    c.save(); c.translate(q.x, q.y);
    // contact shadow
    c.save(); c.translate(0, 1); c.scale(1, .34); ell(c, 0, 0, 13, 4.6, local ? '#00000066' : '#0000004a'); c.restore();
    // magic circle under a casting hero
    if (cast > .05) {
      c.save(); c.globalAlpha = cast * .55;
      c.strokeStyle = '#b8ecff'; c.lineWidth = 1.2;
      c.beginPath(); c.ellipse(0, 1, 17 + cast * 5, 6 + cast * 2, 0, 0, TAU); c.stroke();
      c.strokeStyle = '#e6d0ff'; c.lineWidth = 2;
      c.beginPath(); c.ellipse(0, 1, 13 + cast * 3, 4.6 + cast, 0, now / 260, now / 260 + 4.2); c.stroke();
      for (let i = 0; i < 6; i++) {
        const a = now / 420 + i * TAU / 6;
        ell(c, Math.cos(a) * (16 + cast * 4), 1 + Math.sin(a) * (5.6 + cast), 1.2, 1.2, '#d8f4ff');
      }
      c.restore();
    }
    drawHeroModel(c, q, {
      coat, trim, local, class: q.class, weapon: q.weapon, time: now / 1000,
      walk: vis.walk, move: vis.move, swing: vis.swing,
      run: vis.run, sneak: vis.sneak, aim: vis.aim, cast, drink, gather: vis.gather,
      gatherKind: q.gather_kind || '',
      swap, shoot: vis.shoot, hurt: vis.hurt, charge,
    });

    // ── world-space flourishes ───────────────────────────────────────────
    const speed = vis.move || 0;
    // footsteps: dust when running, scuffs while walking
    const dustGap = vis.run ? 120 : vis.sneak ? 620 : 330;
    if (vis.move > 40 && now - (vis.dust || 0) > dustGap) {
      vis.dust = now;
      const col = vis.run ? '#cbb894' : '#a89a80';
      offsetParticle(q.x - (q.face_x < 0 ? -1 : 1) * 7, q.y + 1, col, vis.run ? 4 : 2, vis.run ? 2.2 : 1.2, vis.run ? 3 : 2, .45);
    }
    // sparks fly while gathering
    if (vis.gather) {
      if (now - (vis.spark || 0) > 210) {
        vis.spark = now;
        const dir = q.face_x < 0 ? -1 : 1;
        offsetParticle(q.x + dir * 14, q.y - 4, '#ffe6a3', 4, 2.2, 3, .5);
      }
    }
    // spell motes rise from the orb
    if (cast > .2 && now - (vis.castFx || 0) > 90) {
      vis.castFx = now;
      offsetParticle(q.x + (q.face_x < 0 ? -6 : 6), q.y - 34, '#cdf6ff', 3, 1.4, 2, .6);
    }
    // potion gloop
    if (drink > .3 && now - (vis.drinkFx || 0) > 140) {
      vis.drinkFx = now;
      offsetParticle(q.x + 2, q.y - 30, '#8fe8c8', 3, 1.1, 2, .5);
    }
    // bow release puff
    if (vis.shoot > .5 && local) offsetParticle(q.x + 18, q.y - 24, '#e8f2e8', 3, 2.4, 2, .3);
    // wind streaks behind a sprinting hero
    if (vis.run && speed > 150) {
      const dir = q.face_x < 0 ? 1 : -1;
      c.save(); c.globalAlpha = .22; c.strokeStyle = '#eaf4e0'; c.lineWidth = 1.4;
      for (let i = 0; i < 3; i++) {
        const yy = -8 - i * 8, len = 7 + ((now / 70 + i * 11) % 12);
        c.beginPath(); c.moveTo(dir * 9, yy); c.lineTo(dir * (9 + len), yy); c.stroke();
      }
      c.restore();
    }

    // player labels
    const nameCol = local ? '#ffe9ab' : '#d8e8d0';
    label(c, q.name, 0, -52, nameCol, 10);
    P(c, -10, -48, 20, 3, '#0d140f');
    P(c, -10, -48, 20 * clamp(q.hp / Math.max(1, q.max_hp), 0, 1), 3, local ? '#8fd96a' : '#7fc86a');
    c.restore();
  }

  function drawMob(c, m, now) {
    const vis = mobVisual(m, now);
    const mx = vis.x, my = vis.y;
    const spec = {
      slime: 20, wolf: 22, boar: 26, wisp: 20, stone: 28, ashling: 23, ashguard: 34, colossus: 55,
      frost_wyrm: 40, rift_knight: 32, echo_dragon: 50, void_wraith: 28, astral_titan: 58,
      obsidian_sentinel: 36, starseer: 30, ancient_warden: 56,
    }[m.kind] || 22;
    const s = spec * (m.boss ? 1.24 : 1);
    const feet = my + s * .5;
    const hero = me();
    const dist = hero ? Math.hypot(hero.x - mx, hero.y - my) : 999;
    const aggro = dist < 300 && snap?.region?.danger > 0;
    const faceLeft = hero && hero.x < mx;
    c.save();
    // contact shadow
    c.save(); c.translate(mx, feet); c.scale(1, .36); ell(c, 0, 0, s * .74, s * .24, '#00000066'); c.restore();
    // boss aura
    if (m.boss || ['echo_dragon', 'astral_titan', 'ancient_warden', 'colossus'].includes(m.kind)) {
      c.save(); c.globalCompositeOperation = 'lighter';
      const auraCol = { echo_dragon: '#ff6fb4', astral_titan: '#6fe8ff', ancient_warden: '#9ff06a', colossus: '#ff9a4a', frost_wyrm: '#8fe8ff', void_wraith: '#a45cd8' }[m.kind] || '#ffb066';
      c.globalAlpha = .1 + .05 * Math.sin(now / 400);
      ell(c, mx, feet - s * .45, s * 1.25, s * .95, auraCol);
      c.restore();
    }
    if (m.telegraphing) {
      const pulse = .5 + .5 * Math.sin(now / 90);
      c.save(); c.translate(mx, feet);
      c.globalAlpha = .35 + pulse * .25;
      c.strokeStyle = '#ff9a6a'; c.lineWidth = 2.4;
      c.beginPath(); c.ellipse(0, 0, s * .85 + pulse * 5, s * .33 + pulse * 2, 0, 0, TAU); c.stroke();
      c.globalAlpha = .18; ell(c, 0, 0, s * .85, s * .33, '#ff7a4a');
      c.restore();
      c.save(); c.globalAlpha = .85 + pulse * .15;
      label(c, '!', mx, feet - s * 1.72, '#ffd27a', 18); c.restore();
    }
    if (m.burning) {
      c.save(); c.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 5; i++) {
        const ph = (now / 500 + i * .2) % 1;
        ell(c, mx + Math.sin(i * 2 + now / 180) * s * .5, feet - s * .25 - ph * s * .7, 2.4 * (1 - ph), 3.6 * (1 - ph), '#ff9a4a', .8 * (1 - ph));
      }
      c.restore();
    }
    if (m.slowed) { c.save(); c.globalAlpha = .3; ell(c, mx, feet - s * .35, s * .8, s * .6, '#a8ecff'); c.restore(); }
    if (m.bleeding) {
      c.save(); c.globalAlpha = .8;
      for (let i = 0; i < 4; i++) {
        const ph = (now / 420 + i * .25) % 1;
        ell(c, mx + Math.sin(i * 2.4 + now / 210) * s * .42, feet - s * .6 + ph * s * .45, 2.1, 3.0, '#e33b4d', .85 * (1 - ph));
      }
      c.restore();
    }
    if (m.sundered) {
      c.save(); c.strokeStyle = '#ffae52'; c.lineWidth = 1.4; c.globalAlpha = .72;
      c.beginPath(); c.ellipse(mx, feet - 2, s * .76, s * .28, 0, 0, TAU); c.stroke();
      c.restore();
    }
    if (m.stunned || m.staggered) {
      c.save(); c.globalAlpha = .95;
      const starCol = m.staggered ? '#ffbe45' : '#ffe9a0';
      for (let i = 0; i < (m.staggered ? 4 : 3); i++) {
        const a = now / (m.staggered ? 210 : 300) + i * TAU / (m.staggered ? 4 : 3);
        ell(c, mx + Math.cos(a) * s * .46, feet - s * 1.54 + Math.sin(a) * 4, m.staggered ? 2.4 : 1.8, m.staggered ? 2.4 : 1.8, starCol);
      }
      c.restore();
    }
    if (m.boss && aggro) {
      c.save(); c.globalAlpha = .35;
      c.strokeStyle = '#ff7a5a'; c.lineWidth = 2;
      c.beginPath(); c.ellipse(mx, feet, s * 1.05 + Math.sin(now / 200) * 4, s * .42, 0, 0, TAU); c.stroke();
      c.restore();
    }
    // body (flipped toward the hero)
    c.save(); c.translate(mx, feet);
    if (faceLeft) c.scale(-1, 1);
    drawMobModel(c, m.kind, s, now / 1000, seedOf(m.id), {
      walk: vis.walk, move: vis.move, hurt: vis.hurt, atk: vis.atk,
    });
    c.restore();
    if (m.marked) {
      c.save(); c.strokeStyle = '#ffe27a'; c.lineWidth = 1.6; c.globalAlpha = .85;
      c.beginPath(); c.moveTo(mx, feet - s * 1.78); c.lineTo(mx + 5, feet - s * 1.88); c.lineTo(mx, feet - s * 1.98); c.lineTo(mx - 5, feet - s * 1.88); c.closePath(); c.stroke();
      c.restore();
    }
    // health bar + nameplate
    const w = m.boss ? 68 : Math.max(24, s * 1.35);
    const top = feet - s * 1.62 - (m.boss ? 17 : 12);
    c.save(); c.translate(mx, top);
    P(c, -w / 2 - 1, -1, w + 2, m.boss ? 7 : 5, '#0a110c');
    const hpFrac = clamp(m.hp / Math.max(1, m.max_hp), 0, 1);
    P(c, -w / 2, 0, w * hpFrac, m.boss ? 5 : 3, m.boss ? '#ff6f5a' : aggro ? '#e0745c' : '#c87e5a');
    P(c, -w / 2, 0, w * hpFrac, 1, '#ffffff44');
    if ((m.stagger_pct && m.stagger_pct > 0) || m.staggered) {
      const pf = m.staggered ? 1 : clamp((m.stagger_pct || 0) / 100, 0, 1);
      const py = m.boss ? 6 : 4;
      P(c, -w / 2 - 1, py, w + 2, 3, '#0a110c');
      P(c, -w / 2, py + .5, w * pf, 2, m.staggered ? '#ffd45e' : '#d6a449');
    }
    if (m.boss || aggro) {
      c.font = `${m.boss ? 'bold 9px' : '9px'} ui-monospace, monospace`; c.textAlign = 'center';
      c.lineWidth = 3; c.strokeStyle = '#0b120e';
      const nm = `${m.boss ? '◆ ' : ''}${mobNames[m.kind] || m.kind}${m.boss ? ' ◆' : ''} · ур. ${m.level}`;
      c.strokeText(nm, 0, m.boss ? -6 : -5);
      c.fillStyle = m.boss ? '#ffd0b8' : aggro ? '#f3d7b0' : '#d8e0c8';
      c.fillText(nm, 0, m.boss ? -6 : -5);
      c.textAlign = 'left';
    }
    c.restore();
    c.restore();
  }

  function drawNPC(c, n, p, now) {
    const near = p && Math.hypot(p.x - n.x, p.y - n.y) <= 125;
    c.save(); c.translate(n.x, n.y);
    c.save(); c.translate(0, 1); c.scale(1, .34); ell(c, 0, 0, 13, 4.6, '#00000055'); c.restore();
    drawHeroModel(c, { face_x: 0, face_y: 1, weapon: n.role === 'wizard' ? 'apprentice_staff' : 'sword', class: n.role === 'wizard' ? 'mage' : n.role === 'ranger' ? 'ranger' : null }, {
      coat: n.color || '#8a7a58', trim: '#f0e2b0', time: now / 1000 + seedOf(n.id) * 5,
      walk: .2, move: 0, class: n.role === 'wizard' ? 'mage' : n.role === 'ranger' ? 'ranger' : '',
    });
    if (near) {
      c.save(); c.globalAlpha = .22; ell(c, 0, 0, 24, 8, n.color); c.restore();
      c.strokeStyle = n.color; c.lineWidth = 1.4;
      c.beginPath(); c.ellipse(0, 0, 20, 7, 0, 0, TAU); c.stroke();
    }
    const icon = n.role === 'merchant' ? '⚖' : n.role === 'wizard' ? '✦' : n.role === 'forge' ? '⚒' : '❖';
    c.save(); c.shadowColor = n.color; c.shadowBlur = 8;
    c.font = 'bold 13px ui-monospace, monospace'; c.textAlign = 'center'; c.fillStyle = n.color;
    c.fillText(icon, 0, -56); c.restore();
    label(c, n.name, 0, -66, '#f4ecd8', 10);
    if (near) label(c, `${actionKeyLabel('interact')} · ${n.title}`, 0, 12, n.color, 9);
    c.restore();
  }

  function drawWeather(c, w, h, r, now) {
    const t = now / 1000;
    const weather = r.weather || 'fireflies';
    const count = weather === 'snow' || weather === 'petals' ? 90 : 60;
    const rnd = seedOf(r.seed + ':' + weather);
    c.save();
    c.globalCompositeOperation = weather === 'embers' || weather === 'fireflies' || weather === 'runes' || weather === 'stars' ? 'lighter' : 'source-over';
    for (let i = 0; i < count; i++) {
      const sx = ((rnd * 9301 + i * 49297) % 233280) / 233280;
      const sy = ((rnd * 49297 + i * 9301) % 233280) / 233280;
      let x, y;
      if (weather === 'embers' || weather === 'fireflies') {
        x = (sx * w + Math.sin(t * .7 + i) * 18) % w; y = (h - ((sy * h + t * (14 + (i % 7) * 6)) % h));
        if (y > h) y = 0;
      } else if (weather === 'snow' || weather === 'petals') {
        x = (sx * w + Math.sin(t * .8 + i) * 26 + t * 8) % w; y = (sy * h + t * (18 + (i % 5) * 9)) % h;
      } else {
        x = (sx * w + Math.sin(t * .4 + i) * 30 + t * 5) % w; y = (sy * h + t * (10 + (i % 4) * 5)) % h;
      }
      const a = .18 + .32 * (.5 + .5 * Math.sin(t * 1.6 + i));
      c.globalAlpha = a;
      const col = weather === 'embers' ? (i % 3 ? '#ff9a4a' : '#ffd27a') : weather === 'fireflies' ? (i % 2 ? '#e8ff9a' : '#b8ffd0') :
        weather === 'snow' ? '#eafaff' : weather === 'petals' ? (i % 2 ? '#f8c8e0' : '#fff0c0') : weather === 'leaves' ? '#c8d878' :
          weather === 'runes' ? '#d8b0ff' : weather === 'stars' ? '#dff0ff' : '#b8e8d8';
      const size = weather === 'snow' ? 2.5 : weather === 'petals' ? 3 : 2;
      c.fillStyle = col;
      c.fillRect(Math.round(x), Math.round(y), size, weather === 'petals' ? size * .7 : size);
      if (weather === 'fireflies' || weather === 'embers' || weather === 'stars') {
        c.globalAlpha = a * .35; c.fillRect(Math.round(x - 2), Math.round(y - 2), size + 4, size + 4);
      }
    }
    c.restore();
  }

  function renderFrame(now) {
    const rect = canvas.getBoundingClientRect();
    const w = rect.width, h = rect.height;
    if (!w || !h) return;
    // frame timing drives hit-stop (freeze) and the punch-zoom kick
    const dtMs = Math.max(0, Math.min(64, now - (VIEW.lastFrame || now)));
    VIEW.lastFrame = now;
    if (VIEW.punch > 0) VIEW.punch = Math.max(0, VIEW.punch - dtMs * .00022);
    if (VIEW.freeze > 0) VIEW.freeze = Math.max(0, VIEW.freeze - dtMs);
    now -= VIEW.freeze;
    const p = me();
    // camera zoom eases gently so travel and resizes never snap.
    VIEW.targetZoom = desiredZoom(w, h);
    VIEW.zoom = lerp(VIEW.zoom || VIEW.targetZoom, VIEW.targetZoom, .08);
    VIEW.lookY = h * (coarse() ? .06 : .085);

    if (p) {
      const pos = typeof entityPosition === 'function' ? entityPosition(p, now) : p;
      if (VIEW.lastPos) {
        VIEW.leadX = lerp(VIEW.leadX || 0, clamp((pos.x - VIEW.lastPos.x) * 2.4, -26, 26), .09);
        VIEW.leadY = lerp(VIEW.leadY || 0, clamp((pos.y - VIEW.lastPos.y) * 2.4, -18, 18), .09);
      }
      VIEW.lastPos = { x: pos.x, y: pos.y };
      cam.x += (pos.x + (VIEW.leadX || 0) - cam.x) * .18;
      cam.y += (pos.y + (VIEW.leadY || 0) - cam.y) * .18;
      if (hasPointerAim && typeof setAimFromPointer === 'function') setAimFromPointer();
    }
    const { WS, Z, halfW, up, down } = extendCameraBounds(w, h);
    cam.x = clamp(cam.x, halfW, Math.max(halfW, WS.w - halfW));
    cam.y = clamp(cam.y, up, Math.max(up, WS.h - down));
    // punch kick: a short outward zoom pulse that decays inside ~40 frames
    const Zp = Z * (1 + VIEW.punch);

    if (screenShake > .1) {
      screenShakeX = (Math.random() - .5) * screenShake;
      screenShakeY = (Math.random() - .5) * screenShake;
      screenShake *= screenShakeDecay;
      if (screenShake < .12) { screenShake = 0; screenShakeX = 0; screenShakeY = 0; }
    }

    ctx.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.imageSmoothingEnabled = false;
    ctx.save();
    ctx.setTransform(deviceScale * Zp, 0, 0, deviceScale * Zp,
      deviceScale * (w / 2 - cam.x * Zp + screenShakeX),
      deviceScale * (h / 2 + VIEW.lookY - cam.y * Zp + screenShakeY));

    const r = snap?.region;
    if (!r) { ctx.restore(); return; }
    const t = now / 1000;

    // ground
    const terrain = typeof getTerrain === 'function' ? getTerrain(r) : null;
    if (terrain) ctx.drawImage(terrain, 0, 0);
    else { ctx.fillStyle = r.ground || '#3f5540'; ctx.fillRect(0, 0, WS.w, WS.h); }
    // power sites and boss stage decals sit under everything
    for (const site of snap.power_sites || []) drawPowerSite(ctx, site, now);
    if (r.danger > 0 && r.boss_arena) {
      ctx.save(); ctx.translate(r.boss_arena[0], r.boss_arena[1]);
      ctx.strokeStyle = (r.accent || '#e7c77d') + '55'; ctx.lineWidth = 2.4;
      ctx.beginPath(); ctx.ellipse(0, 0, 122, 66, 0, 0, TAU); ctx.stroke();
      ctx.setLineDash([8, 12]); ctx.globalAlpha = .5;
      ctx.beginPath(); ctx.ellipse(0, 0, 96, 52, 0, 0, TAU); ctx.stroke();
      ctx.setLineDash([]); ctx.restore();
    }
    for (const f of snap.thorn_fields || []) drawThornField(ctx, f, now);
    for (const f of snap.ground_effects || []) drawGroundEffect(ctx, f, now);
    for (const portal of snap.portals || []) drawWaystone(ctx, portal, now, r.id);

    // y-sorted cast
    const layers = [];
    for (const ob of r.obstacles || []) layers.push({ y: ob.y, kind: 'ob', ref: ob });
    for (const n of snap.nodes || []) if (n.active) layers.push({ y: n.y, kind: 'node', ref: n });
    for (const n of r.npcs || []) layers.push({ y: n.y, kind: 'npc', ref: n });
    for (const m of snap.mobs || []) layers.push({ y: m.y + 6, kind: 'mob', ref: m });
    for (const q of snap.players || []) layers.push({ y: q.y + 8, kind: 'player', ref: q });
    layers.sort((a, b) => a.y - b.y);
    for (const layer of layers) {
      if (layer.kind === 'ob') drawObstacle(ctx, layer.ref, now, r.id);
      else if (layer.kind === 'node') drawNode(ctx, layer.ref, now);
      else if (layer.kind === 'npc') drawNPC(ctx, layer.ref, p, now);
      else if (layer.kind === 'mob') drawMob(ctx, layer.ref, now);
      else if (layer.kind === 'player') drawPlayer(ctx, layer.ref, now);
    }

    // projectiles above bodies
    for (const a of snap.arrows || []) drawArrowProjectile(ctx, a, now);

    // melee swings (server broadcast + local prediction)
    for (const sw of weaponActions || []) {
      if (sw.weapon_kind === 'bow') continue;
      drawSlashFx(ctx, { ...sw, x: sw.x, y: sw.y }, now);
    }
    for (const fx of attackFx || []) {
      if (fx.fx) {
        drawSlashFx(ctx, { x: fx.x, y: fx.y, aim_x: fx.ax, aim_y: fx.ay, charge: fx.charge, started: fx.until - 330, class: '' }, now);
      } else drawDamageNumber(ctx, fx, now);
    }
    for (const fx of spellFx || []) drawImpactRunes(ctx, fx, now);
    drawWorldFx(ctx, now);
    // game.js keeps its class-ability arcs (lunge trails, chain lightning, blasts)
    // in world coordinates — the camera transform is already applied here.
    if (typeof drawAbilityFx === 'function') drawAbilityFx(now, 0, 0);

    // shared particle pool (world coordinates)
    if (typeof updateAndDrawParticles === 'function') updateAndDrawParticles(ctx, 0, 0);

    // hero aura / targeting
    if (p) {
      ctx.save();
      const grd = ctx.createRadialGradient(p.x, p.y - 10, 2, p.x, p.y - 10, 46);
      grd.addColorStop(0, '#ffe7a314'); grd.addColorStop(1, '#ffe7a300');
      ctx.fillStyle = grd; ctx.fillRect(p.x - 46, p.y - 56, 92, 92);
      ctx.restore();
    }
    if (waypoint) {
      ctx.save(); ctx.strokeStyle = '#ffe08c'; ctx.lineWidth = 1.6; ctx.setLineDash([5, 5]);
      ctx.beginPath(); ctx.arc(waypoint.x, waypoint.y, 20 + 4 * Math.sin(now / 260), 0, TAU); ctx.stroke();
      ctx.setLineDash([]); ctx.restore();
    }
    if (p && hasPointerAim) {
      const tgt = pointerWorld();
      const dx = tgt.x - p.x, dy = tgt.y - p.y;
      const isBow = p.weapon_catalog?.[p.weapon]?.kind === 'bow';
      if (isBow) {
        const charge = p.attack ? Number(p.attack.charge) || 0 : (chargeLocal ? Math.min(1, (performance.now() - chargeStart) / (attackChargeDuration(p) * 1000)) : 0);
        const range = 180 + 620 * charge;
        ctx.save(); ctx.strokeStyle = charge > .6 ? '#dfffa9cc' : '#dfffa966'; ctx.lineWidth = 1.4;
        ctx.setLineDash([6, 6]);
        ctx.beginPath(); ctx.moveTo(p.x, p.y - 12); ctx.lineTo(p.x + aim.x * range, p.y - 12 + aim.y * range); ctx.stroke();
        ctx.setLineDash([]); ctx.restore();
      } else if (chargeLocal) {
        const charge = Math.min(1, (performance.now() - chargeStart) / (attackChargeDuration(p) * 1000));
        const spec = p.weapon_catalog?.[p.weapon] || {};
        const range = Number(spec.range || 44) + 12 * charge;
        const half = Math.acos(Math.max(-.99, Math.min(.99, Number(spec.arc ?? .28))));
        const angle = Math.atan2(aim.y, aim.x);
        ctx.save(); ctx.globalAlpha = .05 + .07 * charge; ctx.fillStyle = charge > .8 ? '#ffe08c' : '#b9d889';
        ctx.beginPath(); ctx.moveTo(p.x, p.y - 10); ctx.arc(p.x, p.y - 10, range, angle - half, angle + half); ctx.closePath(); ctx.fill();
        ctx.globalAlpha = .6; ctx.strokeStyle = charge > .8 ? '#ffe08c' : '#c8e09b'; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(p.x, p.y - 10, range, angle - half, angle + half); ctx.stroke(); ctx.restore();
      }
    }
    // aim reticle
    if (p) {
      const wp = hasPointerAim ? pointerWorld() : { x: p.x + aim.x * 74, y: p.y + aim.y * 74 };
      ctx.save(); ctx.strokeStyle = '#fff1bdaa'; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.arc(wp.x, wp.y, 5, 0, TAU);
      ctx.moveTo(wp.x - 9, wp.y); ctx.lineTo(wp.x - 3, wp.y);
      ctx.moveTo(wp.x + 3, wp.y); ctx.lineTo(wp.x + 9, wp.y);
      ctx.moveTo(wp.x, wp.y - 9); ctx.lineTo(wp.x, wp.y - 3);
      ctx.moveTo(wp.x, wp.y + 3); ctx.lineTo(wp.x, wp.y + 9);
      ctx.stroke(); ctx.restore();
    }
    ctx.restore();

    // screen-space weather + grade
    drawWeather(ctx, w, h, r, now);
    ctx.save();
    // region colour grade
    ctx.globalCompositeOperation = 'soft-light';
    ctx.globalAlpha = .22; ctx.fillStyle = r.accent || '#e7c77d'; ctx.fillRect(0, 0, w, h);
    ctx.restore();
    if (r.id === 'marsh' || r.weather === 'mist') {
      ctx.save();
      for (let i = 0; i < 3; i++) {
        const y = h * (.35 + i * .2) + Math.sin(now / 2600 + i) * 18;
        const g = ctx.createLinearGradient(0, y - 60, 0, y + 60);
        g.addColorStop(0, '#9fd8c800'); g.addColorStop(.5, '#9fd8c81f'); g.addColorStop(1, '#9fd8c800');
        ctx.fillStyle = g; ctx.fillRect(0, y - 60, w, 120);
      }
      ctx.restore();
    }
    // vignette
    ctx.save();
    const vg = ctx.createRadialGradient(w / 2, h * .5, Math.min(w, h) * .3, w / 2, h * .5, Math.max(w, h) * .74);
    vg.addColorStop(0, '#00000000'); vg.addColorStop(.72, '#060c0822'); vg.addColorStop(1, '#04080688');
    ctx.fillStyle = vg; ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }

  /* ── minimap ─────────────────────────────────────────────────────────── */
  function renderMap(c, context, large) {
    const w = c.clientWidth, h = c.clientHeight;
    if (!w || !h || !snap?.region) return;
    const WS = worldSize();
    const sx = x => x / WS.w * w, sy = y => y / WS.h * h;
    context.clearRect(0, 0, w, h);
    context.fillStyle = snap.region.dark || '#1a241c'; context.fillRect(0, 0, w, h);
    const terrain = typeof getTerrain === 'function' ? getTerrain(snap.region) : null;
    if (terrain) context.drawImage(terrain, 0, 0, w, h);
    context.fillStyle = '#07100a66'; context.fillRect(0, 0, w, h);
    // viewport rectangle
    context.strokeStyle = '#fff2c0aa'; context.lineWidth = 1;
    const vw = (canvas.clientWidth / VIEW.zoom) / WS.w * w;
    const vh = (canvas.clientHeight / VIEW.zoom) / WS.h * h;
    context.strokeRect(sx(cam.x) - vw / 2, sy(cam.y) - vh / 2, vw, vh);
    for (const ob of snap.region.obstacles || []) {
      if (ob.kind !== 'tree' && ob.kind !== 'pillar' && ob.kind !== 'crystal') continue;
      context.globalAlpha = .3;
      context.fillStyle = ob.kind === 'crystal' ? '#9fe8e0' : '#3a5a3a';
      context.fillRect(sx(ob.x) - 1, sy(ob.y) - 1, 2, 2);
    }
    context.globalAlpha = 1;
    for (const n of snap.nodes || []) if (n.active) {
      context.fillStyle = n.kind === 'crystal' ? '#8fe8de' : n.kind === 'shard' ? '#c49be8' : '#c8db8b';
      context.fillRect(sx(n.x) - 1.5, sy(n.y) - 1.5, 3, 3);
    }
    for (const n of snap.region.npcs || []) {
      context.fillStyle = n.role === 'merchant' ? '#e7c77d' : '#9ccbd8';
      context.fillRect(sx(n.x) - 2, sy(n.y) - 2, 4, 4);
    }
    for (const portal of snap.portals || []) {
      context.strokeStyle = '#bca6ff'; context.lineWidth = 1.4;
      context.strokeRect(sx(portal.x) - 3, sy(portal.y) - 3, 6, 6);
    }
    for (const m of snap.mobs || []) {
      context.fillStyle = m.boss ? '#ff6b5d' : '#edaa6d';
      context.beginPath(); context.arc(sx(m.x), sy(m.y), m.boss ? 3.2 : 1.7, 0, TAU); context.fill();
    }
    for (const q of snap.players || []) {
      context.fillStyle = q.id === myId ? '#fff6d0' : '#7de0c0';
      context.beginPath(); context.arc(sx(q.x), sy(q.y), q.id === myId ? 3.6 : 2.4, 0, TAU); context.fill();
    }
    // player heading
    const p = me();
    if (p) {
      context.strokeStyle = '#fff6d0'; context.lineWidth = 1.4;
      context.beginPath(); context.moveTo(sx(p.x), sy(p.y)); context.lineTo(sx(p.x) + aim.x * 8, sy(p.y) + aim.y * 8); context.stroke();
    }
  }

  /* ── install browser overrides ───────────────────────────────────────── */
  function install() {
    window.drawWorld = renderFrame;
    window.drawMap = renderMap;
    // zoom-aware pointer maths
    window.pointerWorld = function () { return screenToWorld(mouse.x, mouse.y); };
    window.setAimFromPointer = function () {
      const p = me(); if (!p) return;
      const wx = screenToWorld(mouse.x, mouse.y);
      const dx = wx.x - p.x, dy = wx.y - p.y, l = Math.hypot(dx, dy);
      if (l > .1) { aim = { x: dx / l, y: dy / l }; hasPointerAim = true; }
    };
    window.drawAvatarSprite = function (c, q, x, y, coat, trim, local) {
      c.save(); c.translate(x, y);
      drawHeroModel(c, q || {}, { coat, trim, local, time: performance.now() / 1000, walk: .3, move: 0 });
      c.restore();
    };
    // world.js may still call drawMobSprite for legacy paths; keep it usable.
    window.drawMobSprite = function (c, m, x, y, s, now) {
      c.save(); c.translate(x, y);
      drawMobModel(c, m.kind, s, now / 1000, seedOf(m.id), {});
      c.restore();
    };
    // Reusable pixel artefacts for the forge: custom-weapon preview and item icons.
    window.drawCustomArtefact = function (canvas, opts) {
      const o = opts || {};
      const cv = canvas;
      if (!cv || typeof cv.getContext !== 'function') return false;
      const c = cv.getContext('2d');
      if (!c) return false;
      const w = cv.width, h = cv.height;
      c.clearRect(0, 0, w, h);
      const col = /^#[0-9a-f]{6}$/i.test(String(o.color || '')) ? o.color : '#e0e8ea';
      const grd = c.createRadialGradient(w / 2, h * .55, 3, w / 2, h * .55, Math.max(w, h) * .62);
      grd.addColorStop(0, col + '44'); grd.addColorStop(1, '#0d141000');
      c.fillStyle = grd; c.fillRect(0, 0, w, h);
      // drawHeldWeapon works in hero-sprite units (~30 px tall), so scale the
      // artefact up to fill the preview canvas and centre the blade mass.
      const k = Math.min(w, h) / 46;
      const shape = o.shape || 'sword';
      const lift = (shape === 'staff' ? 22 : shape === 'bow' ? 6 : 12) * k;
      c.save();
      c.translate(w / 2, h / 2 + lift); c.scale(k, k);
      drawHeldWeapon(c, 'cw_preview', o.kind === 'bow' ? 'bow' : o.kind === 'staff' ? 'staff' : 'melee',
        '#e6cf8f', 0, true, 0, 0, 0, { core: col, shape, charge: .55 });
      c.restore();
      return true;
    };
    window.LesEchoView = { VIEW, screenToWorld, drawMobModel, drawHeroModel, drawObstacle, renderFrame, renderMap };
    // ── FX bus: game.js feeds combat moments, the renderer turns them into
    //    shockwaves, runes, level columns and camera kicks. All cosmetic.
    window.LesEchoFx = {
      spawn: spawnWorldFx,
      hit(x, y, crit, color) {
        spawnWorldFx(crit ? 'crit' : 'hit', x, y, { power: crit ? 1.32 : 1, radius: crit ? 34 : 24, color: color || '#ffd9a0', color2: '#fff6dc' });
        punch(crit ? .05 : .028);
        freeze(crit ? 110 : 64);
      },
      cast(x, y, color) { spawnWorldFx('cast', x, y - 6, { color: color || '#a6e8ff', radius: 54 }); },
      level(x, y) { spawnWorldFx('level', x, y, {}); punch(.055); freeze(140); },
      dodge(x, y) { spawnWorldFx('dodge', x, y, { color: '#cfe4ff' }); },
      pickup(x, y, color) { spawnWorldFx('pickup', x, y, { color: color || '#ffe08c' }); },
      heal(x, y) { spawnWorldFx('heal', x, y, { color: '#b9f0a8' }); },
      punch, freeze,
      list: worldFx,
    };
  }

  // The game loop still calls the global drawWorld; install() swaps it. A tiny
  // trampoline keeps `frame()` bound to this renderer even if another script
  // reassigns drawWorld later (world.js only does that for mob sprites).
  if (typeof document !== 'undefined') install();

  if (typeof module === 'object' && module.exports) {
    module.exports = { drawMobModel, drawHeroModel, drawObstacle, drawSlashFx, VIEW, screenToWorld, seedOf, spawnWorldFx, spawn: spawnWorldFx, drawWorldFx, punch, freeze, list: worldFx, EFFECTS: FX_LIFE };
  }
})();
