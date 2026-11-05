'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const HTML = fs.readFileSync(path.join(__dirname, '..', 'static', 'index.html'), 'utf8');
const GAME = fs.readFileSync(path.join(__dirname, '..', 'static', 'game.js'), 'utf8');
const WORLD = fs.readFileSync(path.join(__dirname, '..', 'static', 'world.js'), 'utf8');
const INV = fs.readFileSync(path.join(__dirname, '..', 'static', 'inventory.js'), 'utf8');

test('index.html exposes 3-tab character progression overlay, HUD spell bar, combat indicator, and all 12 base spells', () => {
  for (const id of [
    'charOverlay',
    'charTabs',
    'charStatsList',
    'charSkillsList',
    'charPerksList',
    'hudSpellBar',
    'combatIndicator',
    'closeCharacter',
  ]) {
    assert.match(HTML, new RegExp(`id="${id}"`), `missing #${id} in index.html`);
  }
  for (const tab of ['stats', 'skills', 'perks']) {
    assert.match(HTML, new RegExp(`data-char-tab="${tab}"`), `missing tab ${tab}`);
    assert.match(HTML, new RegExp(`data-char-pane="${tab}"`), `missing pane ${tab}`);
  }
  for (const spellId of [
    'fireball', 'lightning', 'heal', 'thorns', 'ice_lance',
    'arcane_burst', 'meteor', 'frost_nova', 'shadow_bolt',
    'frost_ring', 'root_bind', 'mind_chill',
  ]) {
    assert.match(HTML, new RegExp(`data-spell="${spellId}"`), `missing spell button ${spellId}`);
  }
});

test('game.js wires HUD spell bar, skill upgrades, multi-stat upgrades, and zoom-aware pointer aiming', () => {
  assert.match(GAME, /function renderHudSpellBar\(p\)/);
  assert.match(GAME, /const extraSpellIds=\['frost_ring','root_bind','mind_chill'\]/);
  assert.match(GAME, /type:'upgrade_skill'/);
  assert.match(GAME, /let wp=pointerWorld\(\),dx=wp\.x-p\.x,dy=wp\.y-p\.y/);
  assert.match(GAME, /const UPGRADE_CAPS=\{might:100,vitality:100,agility:100,mana_regen:50,magic_damage:60,insight:40,precision:30,fortune:25,tenacity:40,ferocity:40\}/);
  assert.match(GAME, /const LEVEL_STATS=\['mana_regen','magic_damage','insight','tenacity','ferocity'\]/);
});

test('world.js exposes Hero HUD button and post-boss free world travel in Atlas', () => {
  assert.match(WORLD, /id="charToolButton"/);
  assert.match(WORLD, /type:\s*'world_travel'/);
  assert.match(WORLD, /window\.LesEchoView\s*&&\s*typeof window\.LesEchoView\.screenToWorld/);
});

test('inventory.js boss bar includes stagger poise sub-bar', () => {
  assert.match(INV, /id="bossPoiseFill"/);
  assert.match(INV, /isStaggered/);
});
