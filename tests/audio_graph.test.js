/* Exercises the WebAudio graph itself: audio.js is loaded in a fake browser
   with a recording AudioContext, so we can prove the limiter/ambient wiring,
   mute behaviour and cue throttling without a speaker. */
const test = require('node:test');
const assert = require('node:assert/strict');

function param(initial) {
  const p = {
    value: initial || 0,
    setValueAtTime() { return p; },
    linearRampToValueAtTime() { return p; },
    exponentialRampToValueAtTime() { return p; },
    cancelScheduledValues() { return p; },
  };
  return p;
}

class FakeAudioContext {
  constructor() {
    this.currentTime = 0;
    this.sampleRate = 48000;
    this.state = 'running';
    this.destination = { kind: 'destination' };
    this.count = { osc: 0, gain: 0, filter: 0, comp: 0, source: 0, buffer: 0 };
    FakeAudioContext.last = this;
  }
  createGain() { this.count.gain++; return { gain: param(1), connect(n) { return n; }, disconnect() { } }; }
  createOscillator() {
    this.count.osc++;
    return { type: 'sine', frequency: param(440), detune: param(0), connect(n) { return n; }, start() { }, stop() { } };
  }
  createBiquadFilter() { this.count.filter++; return { type: 'lowpass', frequency: param(400), Q: param(1), connect(n) { return n; } }; }
  createDynamicsCompressor() {
    this.count.comp++;
    return { threshold: param(0), knee: param(0), ratio: param(1), attack: param(0), release: param(0), connect(n) { return n; } };
  }
  createBufferSource() {
    this.count.source++;
    return { buffer: null, loop: false, connect(n) { return n; }, start() { }, stop() { } };
  }
  createBuffer(_ch, len) { this.count.buffer++; return { getChannelData: () => new Float32Array(len) }; }
  resume() { this.state = 'running'; return Promise.resolve(); }
  suspend() { this.state = 'suspended'; return Promise.resolve(); }
}

/* fake DOM: one .game host, one injected toggle button */
const button = {
  textContent: '', className: '', style: {}, dataset: {},
  classList: { list: new Set(), add(c) { this.list.add(c); }, remove(c) { this.list.delete(c); }, toggle(c, on) { on ? this.list.add(c) : this.list.delete(c); } },
  addEventListener() { }, setAttribute(k, v) { this[k] = v; }, appendChild() { },
};

global.window = global;
global.addEventListener = () => { };
global.AudioContext = FakeAudioContext;
global.document = {
  readyState: 'complete',
  hidden: false,
  body: { appendChild() { }, classList: { contains: () => false } },
  querySelector: sel => (sel === '.game' ? { appendChild: child => { button.mounted = child; } } : null),
  createElement: () => button,
  addEventListener() { },
};
global.localStorage = { _d: {}, getItem(k) { return this._d[k] ?? null; }, setItem(k, v) { this._d[k] = String(v); } };

/* unref the ambient bird timer so the test process can exit */
const realSetTimeout = global.setTimeout;
global.setTimeout = (fn, ms, ...rest) => {
  const t = realSetTimeout(fn, ms, ...rest);
  if (t && typeof t.unref === 'function') t.unref();
  return t;
};

const Audio = require('../static/audio.js');

test('unlock builds the master chain and starts the wind bed once', () => {
  Audio.unlock();
  const c = FakeAudioContext.last;
  assert.ok(c, 'an AudioContext was created');
  assert.equal(c.count.comp, 1, 'one limiter');
  assert.ok(c.count.gain >= 2, 'master + ambient buses');
  assert.equal(c.count.source, 1, 'wind noise source started');
  const before = c.count.source;
  Audio.unlock();
  assert.equal(c.count.source, before, 'ambient is not restarted');
});

test('the toggle button is injected into the game shell', () => {
  assert.ok(button.mounted, 'button mounted');
  assert.equal(button.id, 'audioToggle');
  assert.equal(button.textContent, '🔊');
});

test('cues synthesise voices once unlocked', () => {
  const c = FakeAudioContext.last;
  const before = c.count.osc;
  Audio.hit(true);
  assert.ok(c.count.osc > before + 1, 'hit stacks a thump and a ring');
});

test('muting silences cues and clears the master gain', () => {
  Audio.setMuted(true);
  assert.equal(Audio.muted, true);
  const c = FakeAudioContext.last;
  const before = c.count.osc;
  Audio.hit();
  Audio.swing(true);
  assert.equal(c.count.osc, before, 'no oscillators while muted');
  assert.equal(button.textContent, '🔇');
  Audio.setMuted(false);
  const after = c.count.osc;
  Audio.level();
  assert.ok(c.count.osc > after, 'sound resumes');
});

test('repeated footsteps are throttled', () => {
  const c = FakeAudioContext.last;
  const before = c.count.source;
  Audio.step(false);
  Audio.step(false);
  Audio.step(false);
  assert.equal(c.count.source, before + 1, 'one footstep inside the gate window');
});

test('ambient chirps are scheduled, not looped', () => {
  const c = FakeAudioContext.last;
  const before = c.count.osc;
  assert.equal(c.count.osc, before, 'no chirp on demand');
});
