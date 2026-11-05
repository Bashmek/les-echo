'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.join(__dirname, '..', 'static');
const HTML = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const GAME = fs.readFileSync(path.join(ROOT, 'game.js'), 'utf8');
const INV = fs.readFileSync(path.join(ROOT, 'inventory.js'), 'utf8');
const RENDER = fs.readFileSync(path.join(ROOT, 'render.js'), 'utf8');
const CSS = fs.readFileSync(path.join(ROOT, 'overhaul.css'), 'utf8');

test('index.html ships a four-tab forge with every panel the client renders', () => {
  assert.match(HTML, /id="forgeOverlay"/);
  for (const tab of ['blueprints', 'temper', 'reforge', 'custom']) {
    assert.match(HTML, new RegExp(`data-forge-tab="${tab}"`), `missing forge tab ${tab}`);
    assert.match(HTML, new RegExp(`data-forge-pane="${tab}"`), `missing forge pane ${tab}`);
  }
  for (const id of [
    'forgeTabs', 'forgeWallet', 'forgeCraftGrid', 'forgeUpgradeGrid',
    'forgeReforgeGrid', 'forgeReforgeCard', 'forgePrefixTable', 'forgeFilterBar',
    'forgeReforgeTargets', 'temperCatalyst', 'reforgeCatalyst',
    'customBuilder', 'cwName', 'cwArchetype', 'cwCore', 'cwTier',
    'cwPreview', 'cwPreviewCanvas', 'cwCreate', 'customWeaponList',
    'forgeAnvilScene',
  ]) {
    assert.match(HTML, new RegExp(`id="${id}"`), `missing #${id}`);
  }
  // Both catalysts are opt-in checkboxes, never checked by default.
  assert.match(HTML, /<input type="checkbox" id="temperCatalyst">/);
  assert.match(HTML, /<input type="checkbox" id="reforgeCatalyst">/);
});

test('forge tabs announce the Terraria-style rules and the +15 / +10 caps', () => {
  assert.match(HTML, /Закалка \(\+15\)/);
  assert.match(HTML, /Перековка/);
  assert.match(HTML, /Своё оружие/);
  assert.match(HTML, /Чертежи и Реликвии/);
  assert.match(HTML, /Гоблина-изобретателя/);
  assert.match(HTML, /35%/);
  assert.match(HTML, /\+20%/);
  assert.match(HTML, /Мифического/);
});

test('market and wizard overlays expose accessory, reagent and filter surfaces', () => {
  // The shop keeps a single filter bar (world.js); the new categories extend it.
  const WORLD = fs.readFileSync(path.join(ROOT, 'world.js'), 'utf8');
  for (const kind of ['all', 'weapon', 'gear', 'accessory', 'consumable', 'material']) {
    assert.match(WORLD, new RegExp(`data-shop-kind="${kind}"`), `missing shop filter ${kind}`);
  }
  assert.match(WORLD, /id="shopSearch"/);
  assert.match(WORLD, /typeof marketOfferKind === 'function'/);
  assert.match(GAME, /const MARKET_FILTER_KIND=\{weapon:'weapon'/);
  assert.match(GAME, /function renderMarket\(p\)\{/);
  assert.match(GAME, /data-market-type="accessory"/);
  assert.match(GAME, /accessory_sell_prices/);
  assert.match(GAME, /p\.accessory_catalog/);
  // New enchantments must be rendered from the server catalog, not hardcoded.
  assert.match(GAME, /p\.enchant_catalog/);
  assert.match(GAME, /custom_weapons/);
});

test('game.js renders all four forge panes from server catalogs', () => {
  assert.match(GAME, /function setForgeTab\(tab\)/);
  assert.match(GAME, /function setForgeCraftFilter\(cat\)/);
  assert.match(GAME, /function setReforgeTarget\(target\)/);
  assert.match(GAME, /function renderForgeBlueprints\(p\)/);
  assert.match(GAME, /function renderForgeTemper\(p,pending\)/);
  assert.match(GAME, /function renderForgeReforge\(p\)/);
  assert.match(GAME, /function renderForgeCustom\(p\)/);
  assert.match(GAME, /p\.forge_blueprints/);
  assert.match(GAME, /p\.max_item_upgrade/);
  assert.match(GAME, /p\.max_accessory_upgrade/);
  assert.match(GAME, /p\.reforge_prefixes/);
  assert.match(GAME, /p\.custom_weapon_archetypes/);
  assert.match(GAME, /p\.custom_weapon_cores/);
  assert.match(GAME, /p\.custom_weapon_tiers/);
  assert.match(GAME, /data-forge-reforge/);
  assert.match(GAME, /data-forge-craft/);
});

test('tempering sends the catalyst flag and mirrors the server chance curve', () => {
  assert.match(GAME, /use_catalyst:\s*!!\$\('temperCatalyst'\)\?\.checked/);
  assert.match(GAME, /const FORGE_TEMPER_CHANCES=\[1,\.94,\.88,\.82,\.75,\.68,\.6,\.53,\.47,\.42,\.37,\.32,\.28,\.24,\.2\]/);
  assert.match(GAME, /function temperChance\(level,catalysed\)[\s\S]{0,160}\.2/);
  assert.match(GAME, /use_catalyst:\s*!!\$\('reforgeCatalyst'\)\?\.checked/);
  assert.match(GAME, /function temperCostFor\(target,level\)/);
  assert.match(GAME, /function reforgeCostFor\(p,target,itemId\)[\s\S]{0,600}Math\.round\(cost\*\.65\)/);
});

test('custom weapon builder mirrors the server formula and previews stats', () => {
  assert.match(GAME, /function cwResonance\(name\)/);
  assert.match(GAME, /const CW_POWER_ROOTS=\[/);
  assert.match(GAME, /function cwPreviewStats\(p\)/);
  assert.match(GAME, /function renderCwPreview\(p\)/);
  assert.match(GAME, /function drawCwIcon\(p,color,kind\)/);
  assert.match(GAME, /window\.drawCustomArtefact/);
  assert.match(GAME, /type:'forge_action',action:'craft_custom_weapon'/);
  assert.match(GAME, /spellPower/);
  // The preview must never fabricate a name shorter than the server minimum.
  assert.match(GAME, /name\.length<3/);
});

test('reforge and custom weapon results refresh the forge and toast the tier', () => {
  assert.match(GAME, /d\.type==='reforge_result'/);
  assert.match(GAME, /d\.type==='custom_weapon_created'/);
  assert.match(GAME, /d\.type==='forge_result'/);
  assert.match(GAME, /forge-success/);
  assert.match(GAME, /forge-fail/);
  assert.match(GAME, /prefix_name/);
  assert.match(GAME, /prefix_summary/);
  assert.match(GAME, /weapon_id/);
});

test('character overlay exposes tenacity, ferocity and equipment bonuses', () => {
  assert.match(GAME, /tenacity:\['🛡','Стойкость'/);
  assert.match(GAME, /ferocity:\['🔥','Свирепость'/);
  assert.match(GAME, /tenacity:40,ferocity:40/);
  assert.match(GAME, /const LEVEL_STATS=\['mana_regen','magic_damage','insight','tenacity','ferocity'\]/);
  assert.match(GAME, /function equipmentBonusRows\(bonuses\)/);
  assert.match(GAME, /charBonusSummary/);
  assert.match(HTML, /id="charBonusSummary"/);
  assert.match(HTML, /id="charVitalsGrid"/);
});

test('reagent names and icons cover essence, rune dust and mithril', () => {
  for (const key of ['essence', 'rune_dust', 'mithril']) {
    assert.match(GAME, new RegExp(`${key}:'`), `game.js resourceNames missing ${key}`);
    assert.match(INV, new RegExp(`${key}:`), `inventory.js missing ${key}`);
  }
  assert.match(GAME, /essence:'Стихийная эссенция'/);
  assert.match(GAME, /rune_dust:'Рунная пыль'/);
  assert.match(GAME, /mithril:'Мифрил'/);
});

test('inventory grid is scrollable, filterable and searchable', () => {
  assert.match(INV, /class="mcGridWrap" id="mcGridWrap"/);
  assert.match(INV, /class="mcGrid" id="mcGrid"/);
  assert.match(INV, /class="mcFilterToolbar"/);
  assert.match(INV, /class="mcSearchInput"/);
  assert.match(INV, /id="mcSearch"/);
  for (const filter of ['all', 'weapon', 'gear', 'accessory', 'consumable', 'material']) {
    assert.match(INV, new RegExp(`data-mc-filter="${filter}"`), `missing inventory filter ${filter}`);
  }
  assert.match(CSS, /\.mcGridWrap\s*\{[^}]*overflow-y:\s*auto/);
  assert.match(CSS, /\.mcGridWrap::\-webkit\-scrollbar-thumb/);
});

test('six-slot paper doll covers weapon, gear, ring, amulet and two artifacts', () => {
  assert.match(INV, /class="mcEquip mcEquipSix"/);
  for (const slot of ['weapon', 'gear', 'ring', 'amulet', 'artifact_1', 'artifact_2']) {
    assert.match(INV, new RegExp(`data-equip="${slot}"`), `missing paper-doll slot ${slot}`);
  }
  assert.match(INV, /unequip_accessory/);
  assert.match(INV, /type: 'equip_accessory', id: item\.id, slot: 'artifact_1'/);
  assert.match(INV, /type: 'equip_accessory', id: item\.id, slot: 'artifact_2'/);
  assert.match(CSS, /\.mcEquipSix\s*\{[^}]*grid-template-columns:\s*repeat\(3, 1fr\)/);
});

test('inventory shows +N upgrades, reforge tier pills and bonus rows', () => {
  assert.match(INV, /className = 'mcUpgradeBadge'/);
  assert.match(INV, /mcEquipMiniTag/);
  assert.match(INV, /mcReforgePill/);
  assert.match(INV, /mcBonusRow/);
  assert.match(CSS, /\.mcUpgradeBadge\s*\{/);
  assert.match(CSS, /\.mcEquipMiniTag\s*\{/);
  assert.match(CSS, /\.mcReforgePill\s*\{/);
  assert.match(CSS, /\.mcBonusRow b\s*\{/);
  assert.match(CSS, /\.mcFilterBtn\.active\s*\{/);
  assert.match(CSS, /\.mcSearchInput:focus\s*\{/);
});

test('forge styling covers the anvil card, tier colours and the custom builder', () => {
  assert.match(CSS, /\.forgeTabs button\.active\s*\{/);
  assert.match(CSS, /\.forgePane\.active\s*\{/);
  assert.match(CSS, /\.reforgeAnvilCard\s*\{/);
  assert.match(CSS, /\.reforgeAnvilCard\.isMythic\s*\{/);
  assert.match(CSS, /\.reforgeAnvilCard\.isBroken\s*\{/);
  assert.match(CSS, /\.forgePrefixTable\s*\{/);
  assert.match(CSS, /\.customBuilder\s*\{/);
  assert.match(CSS, /\.cwPreviewWrap\s*\{/);
  assert.match(CSS, /\.customWeaponCard\s*\{/);
  assert.match(CSS, /\.forgeCatalyst\s*\{/);
  assert.match(CSS, /--reforge/);
});

test('craft panel switches between supplies, weapons, gear and accessories', () => {
  assert.match(GAME, /function renderCraftPanel\(p\)/);
  assert.match(GAME, /function setCraftTab\(tab\)/);
  assert.match(GAME, /p\?\.craft_recipes/);
  for (const tab of ['supplies', 'weapon', 'gear', 'accessory']) {
    assert.match(INV, new RegExp(`data-craft-tab="${tab}"`), `missing craft tab ${tab}`);
  }
  assert.match(INV, /id="craftGrid"/);
  assert.match(GAME, /window\.renderCraftPanel=renderCraftPanel/);
  assert.match(GAME, /window\.setCraftTab=setCraftTab/);
});

test('renderer resolves authored weapon kind, colour and silhouette', () => {
  assert.match(RENDER, /function customWeaponMeta\(id, ownerId\)/);
  assert.match(RENDER, /const CUSTOM_ARCHETYPE_SHAPES\s*=\s*\{/);
  assert.match(RENDER, /const weaponMeta = customWeaponMeta\(/);
  assert.match(RENDER, /\/\^cw_\//);
  assert.match(RENDER, /const coreCol = \/\^#\[0-9a-f\]\{6\}\$\/i\.test/);
  assert.match(RENDER, /shape === 'greatsword' \|\| shape === 'spear'/);
  assert.match(RENDER, /window\.drawCustomArtefact = function/);
});
