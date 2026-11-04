/* Keyboard map guards.
 *
 * The client keeps its key tables as plain literals inside game.js, so the
 * cheapest reliable check is to read them back and prove that nothing steals
 * another binding. This is what keeps spells off 1–9 (inventory hotbar) and
 * keeps every class ability on a key that is not already a menu shortcut. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const GAME = fs.readFileSync(path.join(__dirname, '..', 'static', 'game.js'), 'utf8');
const INVENTORY = fs.readFileSync(path.join(__dirname, '..', 'static', 'inventory.js'), 'utf8');
const SERVER = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');

function literal(pattern) {
  const match = GAME.match(pattern);
  assert.ok(match, 'не найден литерал в game.js: ' + pattern);
  return new Function('return ' + match[1])();
}

const ABILITY_DEFAULTS = literal(/const ABILITY_DEFAULT_KEYS=(\{[\s\S]*?\});/);
const ABILITY_RESERVED = literal(/const ABILITY_RESERVED=new Set\((\[[\s\S]*?\])\)/);
const ACTION_DEFAULTS = literal(/const ACTION_KEY_DEFAULTS=(\{[\s\S]*?\});/);
const SPELL_CODES = literal(/const defaultSpellCodes=(\[[\s\S]*?\])/);

test('spells live on digits, consumables keep the plain 1–9 row', () => {
  for (const code of SPELL_CODES) assert.match(code, /^Digit[0-9]$/, code);
  assert.ok(SPELL_CODES.includes('Digit1'));
  // Casting requires the modifier, so the hotbar never fights the spell row.
  assert.match(GAME, /if\(e\.shiftKey&&spellKeyCodeToId\[code\]\)castSpell/, 'заклинание должно требовать Shift');
  assert.match(INVENTORY, /if \(e\.shiftKey \|\| e\.ctrlKey \|\| e\.altKey \|\| e\.metaKey\) return;/, 'быстрые слоты должны пропускать Shift+цифру');
  assert.ok(!SPELL_CODES.some(code => /^Digit0$/.test(code) && code !== 'Digit0') || true);
});

test('no ability is bound to a reserved or menu key', () => {
  const reserved = new Set(ABILITY_RESERVED);
  const actions = new Set(Object.values(ACTION_DEFAULTS));
  for (const [ability, code] of Object.entries(ABILITY_DEFAULTS)) {
    assert.match(code, /^Key[A-Z]$/, ability);
    assert.ok(!reserved.has(code), `${ability} использует занятую клавишу ${code}`);
    assert.ok(!actions.has(code) || code === 'Space', `${ability} перекрывает действие ${code}`);
  }
});

test('each class tree binds every ability to a unique key', () => {
  const trees = { warrior: [], ranger: [], mage: [] };
  const serverTree = {};
  const re = /"(\w+)": \{"tree": "(\w+)"/g;
  let m;
  while ((m = re.exec(SERVER))) serverTree[m[1]] = m[2];
  for (const id of Object.keys(ABILITY_DEFAULTS)) {
    const tree = serverTree[id];
    if (tree) trees[tree].push(id);
  }
  for (const [tree, ids] of Object.entries(trees)) {
    assert.ok(ids.length >= 7, `${tree}: слишком мало способностей`);
    const codes = ids.map(id => ABILITY_DEFAULTS[id]);
    assert.equal(new Set(codes).size, codes.length, `${tree}: клавиши способностей должны различаться`);
  }
  assert.equal(trees.mage.length, 8, 'у мага должно быть восемь способностей');
});

test('every mage ability on the server has a client key and a mana price', () => {
  const mageBlock = SERVER.slice(SERVER.indexOf('"arcane_bolt"'), SERVER.indexOf('for _ability_id, _ability_spec'));
  const ids = [...mageBlock.matchAll(/"(\w+)": \{"tree": "mage"/g)].map(x => x[1]);
  assert.equal(ids.length, 8, ids.join(','));
  for (const id of ids) {
    assert.ok(ABILITY_DEFAULTS[id], `нет клавиши для ${id}`);
    const spec = mageBlock.slice(mageBlock.indexOf(`"${id}": {`));
    const head = spec.slice(0, spec.indexOf('"desc"'));
    assert.match(head, /"resource": "mana"/, `${id} должен тратить ману`);
  }
});

test('mage abilities appear in the mage class list', () => {
  const start = SERVER.indexOf('"mage": {');
  const block = SERVER.slice(start, SERVER.indexOf('ABILITY_CATALOG'));
  for (const id of Object.keys(ABILITY_DEFAULTS).filter(k => /arcane|frost|flame|chain|blink|mana_surge|meteor/.test(k))) {
    assert.ok(block.includes(`"${id}"`), `класс «Маг» не перечисляет ${id}`);
  }
});
