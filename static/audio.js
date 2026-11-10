/* Les Echo — concise procedural soundscape.
 *
 * No audio files: every cue is synthesised with WebAudio, so the whole
 * soundtrack weighs a few kilobytes and never fights the pixel art.
 * Browsers block audio until the first gesture, so we unlock lazily.
 */
(function () {
  'use strict';

  const G = (typeof window !== 'undefined') ? window : globalThis;
  const STORE_KEY = 'echoAudioV1';
  let ctx = null, master = null, limiter = null, ambientBus = null, ambientWind = null;
  let muted = loadMuted();
  let unlocked = false;
  let birdTimer = 0;

  function loadMuted() {
    try { return localStorage.getItem(STORE_KEY) === 'mute'; } catch { return false; }
  }
  function saveMuted() {
    try { localStorage.setItem(STORE_KEY, muted ? 'mute' : 'on'); } catch { }
  }

  function ensure() {
    if (ctx) return ctx;
    const AC = G.AudioContext || G.webkitAudioContext;
    if (!AC) return null;
    try { ctx = new AC(); } catch { return null; }
    limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -14;
    limiter.knee.value = 22;
    limiter.ratio.value = 8;
    limiter.attack.value = .004;
    limiter.release.value = .18;
    master = ctx.createGain();
    master.gain.value = muted ? 0 : .55;
    master.connect(limiter).connect(ctx.destination);
    ambientBus = ctx.createGain();
    ambientBus.gain.value = muted ? 0 : .5;
    ambientBus.connect(master);
    return ctx;
  }

  function now() { return ctx ? ctx.currentTime : 0; }
  const rand = (a, b) => a + Math.random() * (b - a);

  /* ── voices ─────────────────────────────────────────────────────────── */
  const lastAt = {};
  function gate(name, ms) {
    const t = (typeof performance !== 'undefined' ? performance.now() : Date.now());
    const prev = lastAt[name];
    // `prev === undefined` means "never played": do not let the page's young
    // performance.now() clock swallow the very first cue.
    if (prev !== undefined && t - prev < ms) return false;
    lastAt[name] = t;
    return true;
  }

  function tone(opts) {
    if (!ctx || muted) return;
    const o = opts || {};
    const t0 = now() + (o.delay || 0);
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = o.type || 'sine';
    const f0 = Math.max(20, o.freq || 440);
    const f1 = Math.max(20, o.to == null ? f0 : o.to);
    const dur = Math.max(.02, o.dur || .15);
    osc.frequency.setValueAtTime(f0, t0);
    if (f1 !== f0) {
      if (o.linear) osc.frequency.linearRampToValueAtTime(f1, t0 + dur);
      else osc.frequency.exponentialRampToValueAtTime(f1, t0 + dur);
    }
    if (o.detune) osc.detune.value = o.detune;
    const peak = Math.max(.0001, o.gain == null ? .08 : o.gain);
    const atk = Math.min(dur * .5, o.attack == null ? .006 : o.attack);
    gain.gain.setValueAtTime(.0001, t0);
    gain.gain.exponentialRampToValueAtTime(peak, t0 + atk);
    gain.gain.exponentialRampToValueAtTime(.0001, t0 + dur);
    osc.connect(gain).connect(o.bus || master);
    osc.start(t0);
    osc.stop(t0 + dur + .02);
  }

  let noiseBuf = null;
  function noiseSource() {
    if (!noiseBuf) {
      const len = Math.floor(ctx.sampleRate * 1.2);
      noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate);
      const data = noiseBuf.getChannelData(0);
      let last = 0;
      for (let i = 0; i < len; i++) {
        const white = Math.random() * 2 - 1;
        last = (last + .02 * white) / 1.02;
        data[i] = last * 3.2;
      }
    }
    const src = ctx.createBufferSource();
    src.buffer = noiseBuf;
    src.loop = true;
    return src;
  }

  function noise(opts) {
    if (!ctx || muted) return;
    const o = opts || {};
    const t0 = now() + (o.delay || 0);
    const dur = Math.max(.03, o.dur || .2);
    const src = noiseSource();
    const filter = ctx.createBiquadFilter();
    filter.type = o.filter || 'bandpass';
    filter.Q.value = o.q == null ? 1 : o.q;
    const f0 = o.from == null ? 900 : o.from;
    const f1 = o.to == null ? f0 : o.to;
    filter.frequency.setValueAtTime(f0, t0);
    if (f1 !== f0) filter.frequency.exponentialRampToValueAtTime(Math.max(40, f1), t0 + dur);
    const gain = ctx.createGain();
    const peak = Math.max(.0001, o.gain == null ? .07 : o.gain);
    gain.gain.setValueAtTime(.0001, t0);
    gain.gain.exponentialRampToValueAtTime(peak, t0 + Math.min(.03, dur * .35));
    gain.gain.exponentialRampToValueAtTime(.0001, t0 + dur);
    src.connect(filter).connect(gain).connect(o.bus || master);
    src.start(t0);
    src.stop(t0 + dur + .02);
  }

  /* ── ambient bed: wind + distant birds, deliberately sparse ─────────── */
  function startAmbient() {
    if (!ctx || ambientWind) return;
    const src = noiseSource();
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 420;
    lp.Q.value = .4;
    const gain = ctx.createGain();
    gain.gain.value = .0001;
    src.connect(lp).connect(gain).connect(ambientBus);
    src.start();
    gain.gain.linearRampToValueAtTime(.05, now() + 3.2);
    // slow gust LFO
    const lfo = ctx.createOscillator();
    const lfoGain = ctx.createGain();
    lfo.frequency.value = .055;
    lfoGain.gain.value = .022;
    lfo.connect(lfoGain).connect(gain.gain);
    lfo.start();
    ambientWind = { src, gain, lfo };
    scheduleBirds();
  }

  function scheduleBirds() {
    if (birdTimer) clearTimeout(birdTimer);
    birdTimer = setTimeout(() => {
      if (ctx && !muted && unlocked) chirp();
      scheduleBirds();
    }, rand(7000, 17000));
  }

  function chirp() {
    const base = rand(1900, 2600);
    for (let i = 0; i < 2 + Math.floor(Math.random() * 2); i++) {
      tone({ freq: base, to: base * rand(1.15, 1.5), type: 'sine', dur: .07, gain: .012,
        bus: ambientBus, delay: i * rand(.07, .13), attack: .008 });
    }
  }

  /* ── public cues ────────────────────────────────────────────────────── */
  const api = {
    unlock() {
      const c = ensure();
      if (!c) return;
      if (c.state === 'suspended') c.resume().catch(() => { });
      if (!unlocked) { unlocked = true; startAmbient(); }
    },
    get muted() { return muted; },
    setMuted(value) {
      muted = !!value;
      saveMuted();
      if (master) master.gain.value = muted ? 0 : .55;
      if (ambientBus) ambientBus.gain.value = muted ? 0 : .5;
      updateToggle();
    },
    toggle() { api.setMuted(!muted); return muted; },

    ui() { if (gate('ui', 40)) tone({ freq: 720, type: 'square', dur: .035, gain: .022 }); },
    open() { if (gate('open', 60)) { tone({ freq: 430, to: 620, type: 'triangle', dur: .1, gain: .035 }); } },
    close() { if (gate('close', 60)) tone({ freq: 560, to: 320, type: 'triangle', dur: .1, gain: .03 }); },

    step(run) {
      if (!gate('step', run ? 110 : 190)) return;
      noise({ dur: .05, gain: run ? .028 : .016, from: rand(520, 900), to: 260, q: .8, filter: 'lowpass' });
    },

    swing(heavy) {
      if (!gate('swing', 80)) return;
      const w = heavy ? 1 : 0;
      noise({ dur: .16 + w * .06, gain: .1, from: 1500 + w * 500, to: 280, q: .9 });
      tone({ freq: 240, to: 90 - w * 20, type: 'sine', dur: .14, gain: .05 });
    },

    hit(crit) {
      if (!ctx || !gate('hit', 45)) return;
      const power = crit ? 1 : 0;
      tone({ freq: 170 + power * 30, to: 52, type: 'sine', dur: .16, gain: .14 + power * .06 });
      noise({ dur: .12, gain: .1 + power * .05, from: 1300, to: 220, q: .7 });
      if (crit) {
        tone({ freq: rand(2300, 2700), type: 'triangle', dur: .1, gain: .05, delay: .01 });
        tone({ freq: 120, to: 60, type: 'square', dur: .18, gain: .05 });
      }
    },

    hurt() {
      if (!ctx || !gate('hurt', 90)) return;
      tone({ freq: 110, to: 58, type: 'sine', dur: .18, gain: .13 });
      noise({ dur: .14, gain: .07, from: 700, to: 180, q: .6 });
    },

    bowDraw() { if (gate('draw', 220)) noise({ dur: .3, gain: .03, from: 380, to: 950, q: 6, filter: 'bandpass' }); },
    bowShot() {
      tone({ freq: 680, to: 170, type: 'triangle', dur: .1, gain: .09 });
      noise({ dur: .08, gain: .06, from: 2400, to: 600, q: .8 });
    },

    cast(element) {
      const warm = element === 'fire' || element === 'Огонь';
      tone({ freq: warm ? 280 : 330, to: warm ? 720 : 1080, type: 'sine', dur: .34, gain: .06, attack: .03 });
      tone({ freq: warm ? 560 : 880, type: 'triangle', dur: .4, gain: .022, delay: .02 });
      tone({ freq: 1568, type: 'sine', dur: .5, gain: .018, delay: .06 });
    },

    impact(element) {
      tone({ freq: 140, to: 42, type: 'sine', dur: .34, gain: .16 });
      noise({ dur: .3, gain: .09, from: 1400, to: 160, q: .5 });
      if (element) tone({ freq: rand(300, 420), to: 130, type: 'sawtooth', dur: .18, gain: .03 });
    },

    drink() {
      if (!ctx) return;
      [430, 560, 720].forEach((f, i) => tone({ freq: f, to: f * 1.25, type: 'sine', dur: .08, gain: .05, delay: i * .11 }));
    },

    gather() { if (gate('gather', 180)) { tone({ freq: 190, to: 150, type: 'triangle', dur: .06, gain: .045 }); noise({ dur: .05, gain: .03, from: 1800, to: 700 }); } },
    pickup() { [880, 1320].forEach((f, i) => tone({ freq: f, type: 'sine', dur: .09, gain: .04, delay: i * .07 })); },
    coin() { if (gate('coin', 90)) { tone({ freq: 1180, type: 'triangle', dur: .07, gain: .035 }); tone({ freq: 1560, type: 'triangle', dur: .1, gain: .025, delay: .06 }); } },
    level() { [523, 659, 784, 1047].forEach((f, i) => tone({ freq: f, type: 'triangle', dur: .16, gain: .05, delay: i * .09 })); },
    victory(boss = false) {
      if (!gate('victory', 900)) return;
      [392, 523.25, 659.25, 783.99].forEach((freq, i) =>
        tone({ freq, type: 'triangle', dur: boss ? .32 : .22, gain: .035, delay: i * .1 }));
      if (boss) tone({ freq: 196, type: 'sine', dur: .45, gain: .025 });
    },

    dodge() { noise({ dur: .22, gain: .07, from: 2000, to: 300, q: .8 }); },
    portal() { tone({ freq: 900, to: 280, type: 'sine', dur: .5, gain: .05 }); noise({ dur: .4, gain: .03, from: 600, to: 180, q: 2 }); },
    boss() { tone({ freq: 68, to: 44, type: 'sawtooth', dur: .9, gain: .1, attack: .12 }); noise({ dur: .8, gain: .05, from: 300, to: 90, q: .5 }); },
    death() { [392, 330, 262].forEach((f, i) => tone({ freq: f, to: f * .8, type: 'sine', dur: .28, gain: .06, delay: i * .12 })); },
  };

  /* ── small mute control in the corner ───────────────────────────────── */
  let toggleEl = null;
  function updateToggle() {
    if (!toggleEl) return;
    toggleEl.textContent = muted ? '🔇' : '🔊';
    toggleEl.setAttribute('aria-label', muted ? 'Включить звук' : 'Выключить звук');
    toggleEl.setAttribute('aria-pressed', String(muted));
    toggleEl.classList.toggle('isMuted', muted);
  }
  function makeToggle() {
    if (toggleEl || typeof document === 'undefined' || !document.body) return;
    const host = document.querySelector('.game') || document.body;
    toggleEl = document.createElement('button');
    toggleEl.type = 'button';
    toggleEl.id = 'audioToggle';
    toggleEl.className = 'audioToggle';
    toggleEl.addEventListener('click', e => {
      e.stopPropagation();
      api.unlock();
      const nowMuted = api.toggle();
      if (!nowMuted) api.ui();
    });
    host.appendChild(toggleEl);
    updateToggle();
  }

  function boot() {
    makeToggle();
    const wake = () => { api.unlock(); };
    window.addEventListener('pointerdown', wake, { once: true, passive: true });
    window.addEventListener('keydown', wake, { once: true });
    // Z toggles the soundscape; ignore it while typing or when the game menu
    // owns the keyboard.
    window.addEventListener('keydown', e => {
      if (e.repeat || e.code !== 'KeyZ') return;
      const t = e.target;
      if (t && (t.isContentEditable || (typeof t.matches === 'function' && t.matches('input,textarea,select')))) return;
      if (typeof activeGameMenu === 'function' && activeGameMenu()) return;
      api.unlock();
      api.toggle();
    });
    document.addEventListener('visibilitychange', () => {
      if (!ctx) return;
      if (document.hidden) ctx.suspend().catch(() => { });
      else if (!muted) ctx.resume().catch(() => { });
    });
  }

  G.LesEchoAudio = api;
  G.SFX = api;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }

  if (typeof module === 'object' && module.exports) module.exports = api;
})();
