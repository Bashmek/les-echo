const test = require('node:test');
const assert = require('node:assert/strict');

/* A tiny 2D-context stub is enough to prove every sprite path executes
   without touching a real browser. */
function mockContext() {
  const gradient = { addColorStop() { } };
  const noop = () => { };
  return new Proxy({}, {
    get(_target, prop) {
      if (prop === 'createLinearGradient' || prop === 'createRadialGradient') return () => gradient;
      if (prop === 'measureText') return () => ({ width: 12 });
      if (prop === 'canvas') return { width: 100, height: 100 };
      if (prop === 'globalAlpha' || prop === 'lineWidth') return 1;
      return noop;
    },
    set() { return true; },
  });
}


function mockElement() {
  const el = {
    style: {}, dataset: {}, children: [],
    classList: { add() { }, remove() { }, toggle() { }, contains: () => false },
    getContext: () => mockContext(),
    appendChild(child) { this.children.push(child); return child; },
    replaceChildren() { this.children.length = 0; },
    setAttribute() { }, removeAttribute() { }, getAttribute: () => null,
    addEventListener() { }, removeEventListener() { }, focus() { }, remove() { },
    closest: () => null, querySelector: () => null, querySelectorAll: () => [],
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }),
  };
  return el;
}

global.window = global;
global.document = {
  body: { classList: { contains: () => false, add() { }, remove() { } } },
  getElementById: () => null,
  createElement: () => mockElement(),
  querySelector: () => null,
  addEventListener() { },
};
global.matchMedia = () => ({ matches: false });
global.requestAnimationFrame = fn => { if (typeof fn === 'function') fn(0); return 0; };
global.localStorage = { _d: {}, getItem(k) { return this._d[k] ?? null; }, setItem(k, v) { this._d[k] = String(v); } };
global.addEventListener = () => { };
global.canvas = { getBoundingClientRect: () => ({ width: 800, height: 600, left: 0, top: 0 }), clientWidth: 800, clientHeight: 600 };
global.cam = { x: 1000, y: 750 };
global.worldSize = () => ({ w: 2000, h: 1500 });
global.me = () => null;
global.activeGameMenu = () => false;
global.weaponNames = {};
global.gearNames = {};
global.gearDefense = {};
global.resourceNames = { wood: 'Древесина', herb: 'Лунная трава' };
global.mobNames = { echo_dragon: 'Дракон Пустого Эха', astral_titan: 'Титан Астральной Бездны', slime: 'Моховой слизень' };

const Render = require('../static/render.js');
const Inventory = require('../static/inventory.js');

const MOB_KINDS = ['slime', 'wolf', 'boar', 'wisp', 'stone', 'ashling', 'ashguard', 'colossus',
  'frost_wyrm', 'echo_dragon', 'rift_knight', 'void_wraith', 'astral_titan', 'obsidian_sentinel',
  'starseer', 'ancient_warden', 'unknown_kind'];

test('every mob model renders without throwing', () => {
  const c = mockContext();
  for (const kind of MOB_KINDS) {
    assert.doesNotThrow(() => Render.drawMobModel(c, kind, 30, 1.25, 0.42, { walk: 1.4, move: 90, hurt: .2, atk: .6 }), kind);
  }
});

test('hero poses: walk, run, sneak, aim, cast, gather, drink, swap, hurt', () => {
  const c = mockContext();
  const poses = [
    { walk: 2.2, move: 120 },
    { walk: 3.6, move: 330, run: true },
    { walk: 1.2, move: 70, sneak: true },
    { aim: .9 }, { shoot: 1 }, { swing: .36, charge: .9 }, { swing: 1 },
    { cast: 1 }, { gather: 1 }, { drink: 1 }, { swap: .7 }, { hurt: 1 }, { charge: 1 },
  ];
  for (const pose of poses) {
    for (const [kind, weapon] of [['melee', 'iron_sword'], ['bow', 'forest_bow'], ['staff', 'apprentice_staff']]) {
      assert.doesNotThrow(() => Render.drawHeroModel(c, { class: 'warrior', weapon, face_x: 1 }, {
        coat: '#547c50', trim: '#e6cf8f', local: true, time: 2.1, walk: 1.5, move: 60, swing: 0, ...pose,
      }), `${kind} ${JSON.stringify(pose)}`);
    }
  }
});

test('one-shot hero gestures are exposed to the HUD', () => {
  assert.equal(typeof window.heroGesture, 'function');
  for (const kind of ['drink', 'swap', 'cast']) assert.doesNotThrow(() => window.heroGesture(kind));
});

test('hero model renders for every class and weapon family', () => {
  const c = mockContext();
  for (const cls of ['', 'warrior', 'ranger', 'mage']) {
    for (const weapon of ['sword', 'bow', 'apprentice_staff', 'obsidian_axe', 'daggers', 'halberd']) {
      assert.doesNotThrow(() => Render.drawHeroModel(c, { class: cls, weapon, face_x: -1 }, {
        coat: '#547c50', trim: '#e6cf8f', local: true, time: 2.4, walk: 2, move: 60, swing: .5,
      }), `${cls}:${weapon}`);
    }
  }
});

test('all solid scenery models render', () => {
  const c = mockContext();
  for (const kind of ['tree', 'bush', 'rock', 'pillar', 'crystal', 'reed', 'stump']) {
    for (const rid of ['camp', 'forest', 'marsh', 'ruins', 'glacier', 'rift', 'abyss', 'obsidian', 'garden']) {
      assert.doesNotThrow(() => Render.drawObstacle(c, {
        x: 100, y: 120, kind, scale: 1.1, h: 40, variant: .4,
      }, 1000, rid), `${rid}:${kind}`);
    }
  }
});

test('slash effects are safe before, during and after their lifetime', () => {
  const c = mockContext();
  const swing = { x: 10, y: 12, aim_x: 1, aim_y: 0, charge: .8, started: 1000, class: 'warrior' };
  for (const now of [900, 1000, 1100, 1350, 1500]) {
    assert.doesNotThrow(() => Render.drawSlashFx(c, swing, now));
  }
});

test('inventory resolves weapons, potions and materials', () => {
  const player = {
    weapon: 'sword', weapons: ['sword', 'forest_bow'], gear: 'traveler', gear_inventory: ['wolf_cloak'],
    inventory: { potion: 2, mana_potion: 1, wood: 5, arrows: 18 },
    weapon_catalog: {
      sword: { name: 'Меч дозорного', kind: 'melee', damage: 18, rarity: 'common' },
      forest_bow: { name: 'Лук следопыта', kind: 'bow', damage: 21, rarity: 'uncommon' },
    },
    gear_catalog: {
      traveler: { name: 'Куртка путника', defense: 2, rarity: 'common' },
      wolf_cloak: { name: 'Плащ волка', defense: 5, rarity: 'uncommon' },
    },
    upgrades: { weapon: { sword: 1 } },
  };
  const items = Inventory.inventoryItems(player);
  assert.ok(items.some(i => i.id === 'sword' && i.kind === 'weapon' && i.equipped));
  assert.ok(items.some(i => i.id === 'forest_bow' && i.kind === 'weapon' && !i.equipped));
  assert.ok(items.some(i => i.id === 'wolf_cloak' && i.kind === 'gear'));
  assert.ok(items.some(i => i.id === 'potion' && i.kind === 'consumable' && i.count === 2));
  assert.ok(items.some(i => i.id === 'wood' && i.kind === 'material' && i.count === 5));
  assert.equal(Inventory.resolveItem(player, '@weapon').id, 'sword');
  assert.equal(Inventory.resolveItem(player, 'missing_item'), null);
});

test('every sold potion has a client use path', () => {
  for (const id of ['potion', 'mana_potion', 'stamina_potion', 'elixir', 'bandage']) {
    assert.ok(Inventory.CONSUMABLE_META[id], id);
  }
});

/* ── HUD wiring: hotbar, inventory window and boss plate ───────────────── */
function fakeHost() {
  const el = mockElement();
  el.innerHTML = ''; el.textContent = ''; el.dataset = {}; el.id = '';
  el.classList = {
    _s: new Set(),
    add(...c) { c.forEach(x => this._s.add(x)); },
    remove(...c) { c.forEach(x => this._s.delete(x)); },
    toggle(c, on) { on === undefined ? (this._s.has(c) ? this._s.delete(c) : this._s.add(c)) : (on ? this._s.add(c) : this._s.delete(c)); },
    contains: c => el.classList._s.has(c),
  };
  el.querySelector = sel => (/mcEquipSlot/.test(sel) || sel === '#mcClose' ? fakeHost() : null);
  el.insertAdjacentHTML = () => { };
  return el;
}

test('hotbar, inventory window and boss plate render from a server snapshot', () => {
  const nodes = new Map();
  const get = id => { if (!nodes.has(id)) { const el = fakeHost(); el.id = id; nodes.set(id, el); } return nodes.get(id); };
  const game = fakeHost();
  const prevDoc = global.document;
  global.document = {
    body: { classList: { contains: () => false, add() { }, remove() { } } },
    getElementById: get,
    createElement: () => fakeHost(),
    querySelector: sel => (sel === '.game' ? game : null),
    querySelectorAll: () => [],
    addEventListener() { },
  };

  const fill = { potion: 4, mana_potion: 2, elixir: 1, arrows: 40, wood: 12, herb: 3, iron_sword: 1, moss_armor: 1 };
  const player = {
    x: 1000, y: 700, hp: 88, max_hp: 120, mana: 40, max_mana: 70, stamina: 55, max_stamina: 90,
    level: 6, gold: 240, class_name: 'Следопыт', weapon: 'forest_bow', gear: 'moss_armor',
    inventory: fill, upgrades: { weapon: {}, gear: {} },
    weapon_catalog: {
      forest_bow: { name: 'Лук следопыта', kind: 'bow', rarity: 'uncommon', damage: 21 },
      iron_sword: { name: 'Железный меч', kind: 'melee', rarity: 'common', damage: 26 },
    },
    gear_catalog: { moss_armor: { name: 'Мшистая броня', rarity: 'uncommon', defense: 12 } },
  };
  global.me = () => player;
  global.snap = { mobs: [
    { id: 'm1', kind: 'colossus', boss: true, level: 9, hp: 320, max_hp: 800, x: 1080, y: 700 },
    { id: 'm2', kind: 'slime', level: 1, hp: 12, max_hp: 20, x: 5000, y: 5000 },
  ] };

  assert.doesNotThrow(() => window.renderHotbar(player));
  const hot = get('mcHotbar');
  assert.equal(hot.children.length, 9, 'hotbar always renders nine slots');

  assert.doesNotThrow(() => window.openInventory());
  assert.doesNotThrow(() => window.renderInventory(player));
  assert.equal(get('mcGrid').children.length, 36, 'inventory grid is a 36-slot chest');
  assert.equal(get('mcHotbarEdit').children.length, 9);
  assert.match(get('mcMeta').textContent, /уровень/);
  assert.match(get('mcGold').textContent, /240/);
  assert.match(get('mcStats').innerHTML, /120/);

  assert.doesNotThrow(() => window.closeInventory());
  global.document = prevDoc;
});

test('boss plate tracks the nearest boss and ignores distant ones', () => {
  const nodes = new Map();
  const get = id => { if (!nodes.has(id)) { const el = fakeHost(); el.id = id; nodes.set(id, el); } return nodes.get(id); };
  global.document = {
    body: { classList: { contains: () => false, add() { }, remove() { } } },
    getElementById: get,
    createElement: () => fakeHost(),
    querySelector: sel => (sel === '.game' ? fakeHost() : null),
    querySelectorAll: () => [],
    addEventListener() { },
  };
  const player = { x: 1000, y: 700, hp: 50, max_hp: 100, mana: 1, max_mana: 1, stamina: 1, max_stamina: 1 };
  global.me = () => player;

  global.snap = { mobs: [{ id: 'far', kind: 'astral_titan', boss: true, level: 12, hp: 900, max_hp: 900, x: 1900, y: 1400 }] };
  window.renderBossBar();
  assert.equal(get('bossBar').classList.contains('show'), false, 'no plate for a distant boss');

  global.snap = { mobs: [
    { id: 'near', kind: 'echo_dragon', boss: true, level: 10, hp: 450, max_hp: 900, x: 1200, y: 760 },
    { id: 'far', kind: 'astral_titan', boss: true, level: 12, hp: 900, max_hp: 900, x: 1900, y: 1400 },
  ] };
  window.renderBossBar();
  assert.equal(get('bossBar').classList.contains('show'), true, 'plate shows for a nearby boss');
  assert.match(get('bossName').textContent, /Дракон/);
  assert.match(get('bossMeta').textContent, /450 \/ 900/);
  assert.equal(get('bossFill').style.width, '50%');
  global.me = () => null;
  global.snap = { mobs: [] };
});

/* ── FX bus: combat moments must turn into cosmetic effects ───────────── */
test('effect bus registers every combat cue', () => {
  for (const kind of ['hit', 'crit', 'cast', 'level', 'dodge', 'pickup', 'heal']) {
    assert.equal(typeof Render.EFFECTS[kind], 'number', kind);
    assert.ok(Render.EFFECTS[kind] > 0, kind);
  }
});

test('world effects render and then expire', () => {
  const c = mockContext();
  assert.equal(Render.list.length, 0);
  Render.spawn({ kind: 'hit', x: 10, y: 20, color: '#fff' });
  Render.spawn({ kind: 'crit', x: 12, y: 22 });
  Render.spawn({ kind: 'cast', x: 14, y: 24 });
  Render.spawn({ kind: 'level', x: 16, y: 26 });
  Render.spawn({ kind: 'dodge', x: 18, y: 28 });
  Render.spawn({ kind: 'pickup', x: 20, y: 30 });
  Render.spawn({ kind: 'heal', x: 22, y: 32 });
  assert.equal(Render.list.length, 7);
  const start = Render.list[0].start;
  for (const dt of [0, 60, 140, 300, 500]) {
    assert.doesNotThrow(() => Render.drawWorldFx(c, start + dt), 'frame +' + dt);
  }
  Render.drawWorldFx(c, start + 100000);
  assert.equal(Render.list.length, 0, 'expired effects are collected');
});

test('hit-stop and punch zoom stay inside sane bounds', () => {
  Render.punch(0);
  assert.equal(Render.VIEW.punch, 0);
  for (let i = 0; i < 20; i++) Render.punch(.05);
  assert.ok(Render.VIEW.punch <= .075 + 1e-9, 'punch is clamped');
  Render.freeze(0);
  Render.freeze(80);
  Render.freeze(80);
  assert.ok(Render.VIEW.freeze <= 190, 'freeze is clamped');
  assert.ok(Render.VIEW.freeze >= 80, 'freeze keeps the longest request');
});

test('heavy charged swings and casts draw without throwing', () => {
  const c = mockContext();
  const now = performance.now();
  assert.doesNotThrow(() => Render.drawSlashFx(c, { class: 'warrior', weapon: 'ember_greatsword', weapon_kind: 'melee', x: 0, y: 0, aim_x: 1, aim_y: 0, charge: 1, started: now - 40 }, now));
  assert.doesNotThrow(() => Render.drawSlashFx(c, { class: 'mage', weapon: 'elder_staff', weapon_kind: 'staff', x: 0, y: 0, aim_x: 0, aim_y: 1, charge: 0, action: 'cast', started: now - 40 }, now));
  assert.doesNotThrow(() => Render.drawSlashFx(c, { class: 'ranger', weapon: 'bow', weapon_kind: 'bow', x: 0, y: 0, aim_x: -1, aim_y: 0, charge: .4, started: now - 40 }, now));
});
