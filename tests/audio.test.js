const test = require('node:test');
const assert = require('node:assert/strict');

/* audio.js must survive a headless environment: no window, no AudioContext,
   no document. Every cue then becomes a silent no-op instead of a crash. */
const store = {};
global.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
};

const Audio = require('../static/audio.js');

const CUES = ['ui', 'open', 'close', 'step', 'swing', 'hit', 'hurt', 'bowDraw', 'bowShot',
  'cast', 'impact', 'drink', 'gather', 'pickup', 'coin', 'level', 'dodge', 'portal', 'boss', 'death'];

test('exposes the full cue vocabulary', () => {
  for (const name of CUES) assert.equal(typeof Audio[name], 'function', name);
  for (const name of ['unlock', 'setMuted', 'toggle']) assert.equal(typeof Audio[name], 'function', name);
});

test('every cue is silent but safe without an AudioContext', () => {
  for (const name of CUES) assert.doesNotThrow(() => Audio[name](), name);
  assert.doesNotThrow(() => Audio.step(true));
  assert.doesNotThrow(() => Audio.swing(true));
  assert.doesNotThrow(() => Audio.hit(true));
  assert.doesNotThrow(() => Audio.cast('fire'));
  assert.doesNotThrow(() => Audio.impact('ice'));
});

test('unlock never throws when WebAudio is unavailable', () => {
  assert.doesNotThrow(() => Audio.unlock());
});

test('mute state toggles and persists', () => {
  Audio.setMuted(false);
  assert.equal(Audio.muted, false);
  assert.equal(store.echoAudioV1, 'on');
  assert.equal(Audio.toggle(), true);
  assert.equal(Audio.muted, true);
  assert.equal(store.echoAudioV1, 'mute');
  assert.equal(Audio.toggle(), false);
  assert.equal(store.echoAudioV1, 'on');
  Audio.setMuted(true);
  assert.equal(Audio.muted, true);
  Audio.setMuted(false);
});

test('the engine is exposed on the global object', () => {
  assert.equal(globalThis.LesEchoAudio, Audio);
  assert.equal(globalThis.SFX, Audio);
});
