/* Les Echo — Minecraft-style inventory, hotbar and consumables.
 *
 * Replaces the old "two lists of rows" bag with a slot grid, equipment slots,
 * drag & drop, tooltips and a persistent 9-slot hotbar.  All actions still go
 * through the authoritative WebSocket messages (`weapon`, `equip_gear`,
 * `use_consumable`).
 */
(function () {
  'use strict';

  const HOT_KEY = 'echoHotbarV2';
  const CONSUMABLE_META = {
    potion: { name: 'Настойка следопыта', desc: '+48 здоровья', color: '#e0574d', color2: '#ff8a72', kind: 'potion' },
    mana_potion: { name: 'Эссенция синего пламени', desc: '+60 маны', color: '#3f7fd8', color2: '#7fc4ff', kind: 'mana_potion' },
    stamina_potion: { name: 'Отвар живучести', desc: '+55 выносливости', color: '#63a640', color2: '#b6e884', kind: 'stamina_potion' },
    elixir: { name: 'Эликсир первозданной росы', desc: '+90 здоровья, +60 маны, +40 выносливости', color: '#c9a23a', color2: '#ffe79a', kind: 'elixir' },
    rage_potion: { name: 'Эликсир ярости берсерка', desc: '+18% урона и +8% крита на 45с', color: '#d93848', color2: '#ff7d6b', kind: 'rage_potion' },
    ironskin_potion: { name: 'Отвар каменной кожи', desc: '+10 защиты и -12% входящего урона на 60с', color: '#7c8a96', color2: '#c5d6e2', kind: 'ironskin_potion' },
    haste_potion: { name: 'Настой стремительного ветра', desc: '+16% скорости бега и +12% скорости атаки на 50с', color: '#3fbf9f', color2: '#94ffe0', kind: 'haste_potion' },
    arcane_tonic: { name: 'Звёздный тоник чародея', desc: '+22% силы чар и +5 маны/с на 45с', color: '#8f52e0', color2: '#dfb2ff', kind: 'arcane_tonic' },
    bandage: { name: 'Лубяная повязка', desc: '+24 здоровья', color: '#c8b894', color2: '#f0e6c8', kind: 'bandage' },
    throwing_knife: { name: 'Метательные ножи', desc: 'Метательный боеприпас', color: '#a8b8bd', color2: '#e8f4f8', kind: 'knife' },
  };
  const RES_ICON = {
    wood: 'wood', herb: 'herb', ore: 'ore', crystal: 'crystal', shard: 'shard', hide: 'hide', slime: 'slime',
    essence: 'essence', rune_dust: 'rune_dust', mithril: 'mithril',
    arrows: 'arrows', potion: 'potion', mana_potion: 'potion', stamina_potion: 'potion', elixir: 'potion',
    rage_potion: 'potion', ironskin_potion: 'potion', haste_potion: 'potion', arcane_tonic: 'potion',
    bandage: 'bandage', throwing_knife: 'knife',
  };
  const RARITY_COL = { common: '#b9c0aa', uncommon: '#86cf91', rare: '#79bce2', epic: '#c49be8', legendary: '#f1b75e' };
  const TIER_COL = { '-1': '#d96b6b', '1': '#9ad69c', '2': '#7cc6f2', '3': '#cf9eff', '4': '#ffcf66' };

  let hotbar = loadHotbar();
  let selected = '';
  let activeFilter = 'all';
  let searchQuery = '';
  let invOpen = false;
  let hotSig = '', invSig = '';
  let dragState = null;
  let tooltipEl = null;

  function loadHotbar() {
    const fallback = ['@weapon', 'potion', 'mana_potion', 'stamina_potion', 'elixir', 'bandage', 'arrows', '', ''];
    try {
      const raw = JSON.parse(localStorage.getItem(HOT_KEY) || 'null');
      if (Array.isArray(raw) && raw.length === 9) return raw.map(v => (typeof v === 'string' ? v : ''));
    } catch { }
    return fallback;
  }
  function saveHotbar() {
    try { localStorage.setItem(HOT_KEY, JSON.stringify(hotbar)); } catch { }
  }

  function meSafe() { return typeof me === 'function' ? me() : null; }
  function itemName(p, id) {
    if (!id) return '';
    if (id === '@weapon') return p.weapon_catalog?.[p.weapon]?.name || weaponNames?.[p.weapon] || 'Оружие';
    if (CONSUMABLE_META[id]) return CONSUMABLE_META[id].name;
    if (p.weapon_catalog?.[id]) return p.weapon_catalog[id].name;
    if (p.gear_catalog?.[id]) return p.gear_catalog[id].name;
    if (p.accessory_catalog?.[id]) return p.accessory_catalog[id].name;
    if (resourceNames?.[id]) return resourceNames[id];
    return weaponNames?.[id] || gearNames?.[id] || id;
  }

  function reforgeInfo(p, target, id) {
    const pid = p?.reforges?.[target]?.[id];
    if (!pid) return null;
    const spec = p?.reforge_prefixes?.[pid];
    return spec ? { id: pid, ...spec } : null;
  }

  /** Resolve one inventory id into a uniform item descriptor. */
  function resolveItem(p, id) {
    if (!p || !id) return null;
    if (id === '@weapon') id = p.weapon;
    const consumable = CONSUMABLE_META[id];
    if (consumable) {
      const count = Number(p.inventory?.[id] || 0);
      const rarePot = id === 'elixir' || id === 'arcane_tonic' || id === 'rage_potion';
      return { id, kind: 'consumable', name: consumable.name, desc: consumable.desc, count, rarity: rarePot ? 'rare' : 'common', color: consumable.color, icon: RES_ICON[id] || 'potion' };
    }
    const weapon = p.weapon_catalog?.[id];
    if (weapon && (p.weapons || []).includes(id)) {
      const up = Number(p.upgrades?.weapon?.[id] || 0);
      const ref = reforgeInfo(p, 'weapon', id);
      const fullName = `${ref ? ref.name + ' ' : ''}${weapon.name}${up ? ` +${up}` : ''}`;
      const elemLabel = weapon.element ? ` · стихия: ${weapon.element}` : '';
      return {
        id, kind: 'weapon', name: fullName, baseName: weapon.name, rarity: weapon.rarity || 'common', count: 1,
        upgrade: up, reforge: ref, custom: !!weapon.custom, color: weapon.color,
        weaponKind: weapon.kind,
        desc: `${weapon.custom ? 'Авторское · ' : ''}${weapon.kind === 'bow' ? 'Лук' : weapon.kind === 'staff' ? 'Посох' : 'Ближний бой'} · урон ${weapon.damage}+${weapon.bonus || 0}${elemLabel}${p.weapon === id ? ' · в руке' : ''}`,
        lore: weapon.lore || '',
        icon: weapon.kind === 'bow' ? 'bow' : weapon.kind === 'staff' ? 'staff' : 'sword', equipped: p.weapon === id,
      };
    }
    const gear = p.gear_catalog?.[id];
    if (gear && (p.gear === id || (p.gear_inventory || []).includes(id))) {
      const up = Number(p.upgrades?.gear?.[id] || 0);
      const ref = reforgeInfo(p, 'gear', id);
      const fullName = `${ref ? ref.name + ' ' : ''}${gear.name}${up ? ` +${up}` : ''}`;
      const bonusHints = formatGearBonuses(gear.bonuses);
      return {
        id, kind: 'gear', name: fullName, baseName: gear.name, rarity: gear.rarity || 'common', count: 1,
        upgrade: up, reforge: ref,
        desc: `Защита ${gear.defense + up * 3}${bonusHints ? ' · ' + bonusHints : ''}${p.gear === id ? ' · надето' : ''}`,
        lore: gear.lore || '',
        icon: 'gear', equipped: p.gear === id,
      };
    }
    const acc = p.accessory_catalog?.[id];
    const eqMap = p.equipped_accessories || {};
    const eqSlot = Object.keys(eqMap).find(k => eqMap[k] === id) || '';
    if (acc && (eqSlot || (p.accessories || []).includes(id))) {
      const up = Number(p.upgrades?.accessory?.[id] || 0);
      const ref = reforgeInfo(p, 'accessory', id);
      const fullName = `${ref ? ref.name + ' ' : ''}${acc.name}${up ? ` +${up}` : ''}`;
      const slotLabel = acc.slot === 'ring' ? 'Кольцо' : acc.slot === 'amulet' ? 'Ожерелье' : 'Артефакт';
      return {
        id, kind: 'accessory', slotType: acc.slot, equippedSlot: eqSlot,
        name: fullName, baseName: acc.name, rarity: acc.rarity || 'rare', count: 1,
        upgrade: up, reforge: ref, color: acc.color,
        desc: `${slotLabel} · ${acc.description}${up ? ` (закалка +${up * 8}%)` : ''}${eqSlot ? ' · надето' : ''}`,
        lore: acc.lore || '',
        icon: acc.slot, equipped: !!eqSlot,
      };
    }
    const matName = resourceNames?.[id] || ({ essence: 'Стихийная эссенция', rune_dust: 'Рунная пыль', mithril: 'Мифрил' })[id];
    if (matName) {
      const matRarity = id === 'mithril' ? 'epic' : (id === 'essence' || id === 'rune_dust' || id === 'shard' || id === 'crystal') ? 'rare' : 'common';
      return { id, kind: id === 'arrows' ? 'ammo' : 'material', name: matName, rarity: matRarity, count: Number(p.inventory?.[id] || 0), desc: materialDesc(id), icon: RES_ICON[id] || 'material' };
    }
    return null;
  }

  function formatGearBonuses(b) {
    if (!b) return '';
    const parts = [];
    if (b.hp_flat) parts.push(`+${b.hp_flat} HP`);
    if (b.mana_flat) parts.push(`+${b.mana_flat} маны`);
    if (b.stamina_flat) parts.push(`+${b.stamina_flat} вын.`);
    if (b.damage_pct) parts.push(`+${Math.round(b.damage_pct * 100)}% урона`);
    if (b.spell_power_pct) parts.push(`+${Math.round(b.spell_power_pct * 100)}% чар`);
    if (b.crit_pct) parts.push(`+${Math.round(b.crit_pct * 100)}% крит`);
    if (b.move_speed_pct) parts.push(`+${Math.round(b.move_speed_pct * 100)}% скор.`);
    if (b.cdr_pct) parts.push(`-${Math.round(b.cdr_pct * 100)}% КД`);
    if (b.thorns_pct) parts.push(`${Math.round(b.thorns_pct * 100)}% шипы`);
    return parts.join(', ');
  }

  function materialDesc(id) {
    return ({
      wood: 'Строительный материал и древко для оружия.',
      herb: 'Лунная трава для настоек и эликсиров.',
      ore: 'Болотная руда для ковки, закалки и стрел.',
      crystal: 'Эхо-кристалл. Нужен мастеру чар и кузнецу.',
      shard: 'Осколок разлома — редкий реагент межмирья.',
      essence: 'Стихийная эссенция — сердцевина для артефактов и авторского оружия.',
      rune_dust: 'Рунная пыль — катализатор перековки и закалки в кузнице.',
      mithril: 'Благородный мифрил для высшей ковки и закалки +11..+15.',
      hide: 'Шкура для брони, сапог и отваров.',
      slime: 'Слизь для целебных настоек.',
      arrows: 'Боеприпас для луков и арбалетов.',
      potion: 'Восстанавливает здоровье.',
    })[id] || 'Материал для ремесла.';
  }

  /** Every owned item, in a stable order: weapons → armour → accessories → potions → materials. */
  function inventoryItems(p) {
    if (!p) return [];
    const seen = new Set(), out = [];
    const push = id => { if (!id || seen.has(id)) return; const item = resolveItem(p, id); if (item && (item.count === undefined || item.count > 0)) { seen.add(id); out.push(item); } };
    for (const id of p.weapons || []) push(id);
    push(p.gear);
    for (const id of p.gear_inventory || []) push(id);
    const eqAcc = p.equipped_accessories || {};
    for (const k of ['ring', 'amulet', 'artifact_1', 'artifact_2']) if (eqAcc[k]) push(eqAcc[k]);
    for (const id of p.accessories || []) push(id);
    for (const id of Object.keys(CONSUMABLE_META)) if (Number(p.inventory?.[id] || 0) > 0) push(id);
    const allResKeys = new Set([...Object.keys(resourceNames || {}), 'essence', 'rune_dust', 'mithril']);
    for (const id of allResKeys) if (Number(p.inventory?.[id] || 0) > 0) push(id);
    return out;
  }

  /* ── pixel item icons ───────────────────────────────────────────────── */
  function drawIcon(canvas, item) {
    const c = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    c.clearRect(0, 0, W, H);
    c.imageSmoothingEnabled = false;
    const u = W / 34;
    c.save(); c.scale(u, u);
    const px = (x, y, w, h, col) => { c.fillStyle = col; c.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); };
    const poly = (pts, fill, stroke) => { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); c.closePath(); c.fillStyle = fill; c.fill(); if (stroke) { c.strokeStyle = stroke; c.lineWidth = .8; c.stroke(); } };
    const name = (item.name || '').toLowerCase();
    if (item.kind === 'weapon') {
      const blade = item.color || (item.rarity === 'legendary' ? '#ffd27a' : item.rarity === 'epic' ? '#d9b0ff' : item.rarity === 'rare' ? '#bfe3f5' : '#e6f0ea');
      if (item.custom) {
        c.save(); c.shadowColor = blade; c.shadowBlur = 7;
        c.fillStyle = blade + '33'; c.beginPath(); c.arc(17, 17, 11, 0, Math.PI * 2); c.fill();
        c.restore();
      }
      if (item.icon === 'bow') {
        c.strokeStyle = item.custom ? blade : '#a87c4a'; c.lineWidth = 2.6; c.beginPath(); c.arc(12, 18, 11, -1.15, 1.15); c.stroke();
        c.strokeStyle = '#efe8cf'; c.lineWidth = .9; c.beginPath(); c.moveTo(17, 7.5); c.lineTo(17, 28.5); c.stroke();
        px(16, 4, 2, 7, blade); px(16, 23, 2, 7, blade);
        poly([[18, 17], [26, 15], [26, 19]], blade);
      } else if (item.icon === 'staff') {
        px(16, 10, 3, 21, '#7a5836'); px(15, 16, 1, 12, '#a8804a');
        c.save(); c.shadowColor = blade; c.shadowBlur = 7; c.fillStyle = blade; c.beginPath(); c.arc(17.5, 9, 4.4, 0, Math.PI * 2); c.fill(); c.restore();
        c.fillStyle = '#ffffffcc'; c.beginPath(); c.arc(16.4, 8, 1.6, 0, Math.PI * 2); c.fill();
      } else if (/spear|halberd|glaive|scythe|war_maul|axe|warhammer|mace|reaper|claymore/.test(name) || /halberd|glaive|scythe|war_maul|axe|warhammer|mace|spear|reaper|claymore/.test(item.id)) {
        c.strokeStyle = '#7a5836'; c.lineWidth = 2.6; c.beginPath(); c.moveTo(9, 29); c.lineTo(23, 7); c.stroke();
        poly([[23, 7], [29, 4], [26, 12], [21, 13]], blade, '#6e7a72');
        px(8, 26, 5, 5, '#c9a25a');
      } else if (/dagger|claw|twin|fist/.test(item.id)) {
        poly([[9, 27], [14, 22], [20, 10], [23, 12], [16, 23]], blade, '#6e7a72');
        poly([[19, 27], [24, 22], [28, 13], [30, 15], [26, 24]], blade, '#6e7a72');
        px(7, 25, 5, 3, '#b89a5c'); px(17, 25, 5, 3, '#b89a5c');
      } else {
        poly([[8, 29], [10, 24], [22, 8], [26, 4], [27, 8], [13, 26]], blade, '#6e7a72');
        px(7, 26, 7, 2.6, '#c9a25a'); px(5.4, 28.6, 3, 4, '#8a6a40');
        c.strokeStyle = '#ffffffaa'; c.lineWidth = .9; c.beginPath(); c.moveTo(22.5, 7.5); c.lineTo(12.5, 22); c.stroke();
      }
    } else if (item.kind === 'accessory') {
      const gem = item.color || (item.rarity === 'legendary' ? '#ffd27a' : item.rarity === 'epic' ? '#d09cff' : '#79d2f2');
      if (item.slotType === 'ring') {
        c.save();
        c.strokeStyle = '#d9b464'; c.lineWidth = 3.2;
        c.beginPath(); c.arc(17, 19, 7.5, 0, Math.PI * 2); c.stroke();
        c.strokeStyle = '#fff0b8aa'; c.lineWidth = 1.0;
        c.beginPath(); c.arc(17, 19, 7.5, -2.3, -0.8); c.stroke();
        c.shadowColor = gem; c.shadowBlur = 7;
        poly([[17, 6], [22, 11], [17, 15], [12, 11]], gem, '#ffffffcc');
        c.restore();
      } else if (item.slotType === 'amulet') {
        c.save();
        c.strokeStyle = '#c9b37e'; c.lineWidth = 1.6;
        c.beginPath(); c.arc(17, 13, 8.5, -2.7, -0.44); c.stroke();
        c.beginPath(); c.moveTo(9.5, 11); c.lineTo(17, 18); c.lineTo(24.5, 11); c.stroke();
        c.shadowColor = gem; c.shadowBlur = 8;
        poly([[17, 15], [23, 22], [17, 30], [11, 22]], gem, '#fff4cc');
        px(16, 18, 2, 5, '#ffffffaa');
        c.restore();
      } else {
        c.save();
        c.shadowColor = gem; c.shadowBlur = 7;
        if (/boots/.test(item.id)) {
          poly([[10, 9], [18, 9], [18, 21], [26, 23], [26, 28], [9, 28]], gem, '#2a382c');
          poly([[19, 12], [25, 9], [23, 15]], '#fff6d0');
        } else if (/shield/.test(item.id)) {
          poly([[9, 7], [25, 7], [24, 19], [17, 29], [10, 19]], gem, '#fff2b8');
          px(16, 11, 2.4, 12, '#3a2c14'); px(12, 15, 10, 2.4, '#3a2c14');
        } else if (/chalice/.test(item.id)) {
          poly([[10, 8], [24, 8], [21, 18], [13, 18]], '#e6c167', '#5c441c');
          px(11.5, 9, 11, 4, gem); px(15.5, 18, 3, 7, '#d4af53'); px(11, 25, 12, 3, '#e6c167');
        } else if (/hourglass/.test(item.id)) {
          px(10, 6, 14, 2.5, '#d9b86c'); px(10, 26, 14, 2.5, '#d9b86c');
          poly([[11, 8.5], [23, 8.5], [17, 17]], gem, '#ffffffaa');
          poly([[17, 17], [23, 26], [11, 26]], gem, '#ffffffaa');
        } else {
          poly([[17, 5], [27, 14], [23, 27], [11, 27], [7, 14]], gem, '#fff4d2');
          c.fillStyle = '#ffffffaa'; c.beginPath(); c.arc(17, 16, 3.5, 0, Math.PI * 2); c.fill();
        }
        c.restore();
      }
    } else if (item.kind === 'gear') {
      const col = item.rarity === 'legendary' ? '#c8a45a' : item.rarity === 'epic' ? '#9a7ab8' : item.rarity === 'rare' ? '#6f94a8' : '#6f8a58';
      poly([[8, 9], [12, 6], [22, 6], [26, 9], [27, 21], [21, 27], [13, 27], [7, 21]], col, '#2c3a2c');
      poly([[12, 10], [17, 13], [22, 10], [22, 22], [17, 25], [12, 22]], '#ffffff1f');
      px(12, 15, 10, 1.6, '#e8e0c0aa');
    } else if (item.icon === 'gear') {
      poly([[8, 9], [12, 6], [22, 6], [26, 9], [27, 21], [21, 27], [13, 27], [7, 21]], '#6f8a58', '#2c3a2c');
    } else if (item.icon === 'potion') {
      const meta = CONSUMABLE_META[item.id] || { color: '#e0574d', color2: '#ff8a72' };
      px(13, 5, 8, 4, '#c8bfa8');
      px(12, 8, 10, 3, '#e8e0cc');
      poly([[10, 11], [24, 11], [25, 27], [9, 27]], '#d9d2c0', '#4a4438');
      px(11.5, 17, 11, 8, meta.color);
      px(11.5, 17, 11, 2, meta.color2);
      px(13, 12, 2.4, 12, '#ffffff55');
      c.save(); c.shadowColor = meta.color2; c.shadowBlur = 5; px(15, 20, 4, 3, meta.color2); c.restore();
    } else if (item.icon === 'bandage') {
      px(8, 13, 18, 10, '#e8dcc0'); px(8, 13, 18, 2, '#fff6de');
      px(15, 10, 4, 16, '#c8a878'); px(11, 16, 12, 1.2, '#b09060');
    } else if (item.icon === 'knife') {
      poly([[9, 27], [13, 22], [22, 11], [24, 13], [15, 24]], '#c8d8d8', '#5a6460');
      px(8, 25, 5, 3, '#8a6a40');
      poly([[19, 26], [24, 21], [28, 16], [29, 18], [24, 27]], '#c8d8d8', '#5a6460');
    } else if (item.icon === 'arrows') {
      for (let i = 0; i < 3; i++) {
        const x = 8 + i * 7;
        px(x, 8, 2, 18, '#c8a878'); poly([[x - 2, 26], [x + 1, 30], [x + 4, 26]], '#cfd8d2');
        px(x - 2, 8, 6, 4, i % 2 ? '#b8d18a' : '#9fc47a');
      }
    } else if (item.icon === 'wood') {
      px(8, 12, 18, 12, '#7a5836'); px(8, 12, 18, 3, '#9c7448');
      px(8, 15, 18, 1.6, '#5c4026'); px(8, 21, 18, 1.6, '#5c4026');
      c.fillStyle = '#b18b57'; c.beginPath(); c.ellipse(26, 18, 3.4, 6, 0, 0, Math.PI * 2); c.fill();
      c.strokeStyle = '#8a6a40'; c.lineWidth = 1; c.beginPath(); c.arc(26, 18, 1.6, 0, Math.PI * 2); c.stroke();
    } else if (item.icon === 'herb') {
      c.strokeStyle = '#7dbd5c'; c.lineWidth = 2; c.beginPath(); c.moveTo(17, 30); c.lineTo(17, 12); c.stroke();
      for (const [x, y, r] of [[11, 16, -0.5], [23, 19, 0.5], [10, 23, -0.4], [24, 26, 0.4]]) {
        c.save(); c.translate(x, y); c.rotate(r); c.fillStyle = '#9be07a'; c.beginPath(); c.ellipse(0, 0, 6, 3.2, 0, 0, Math.PI * 2); c.fill();
        c.strokeStyle = '#5e9a48'; c.lineWidth = .8; c.stroke(); c.restore();
      }
      c.save(); c.shadowColor = '#eaffb0'; c.shadowBlur = 6; c.fillStyle = '#f2ffce'; c.beginPath(); c.arc(17, 11, 2.4, 0, Math.PI * 2); c.fill(); c.restore();
    } else if (item.icon === 'ore') {
      poly([[8, 26], [10, 13], [17, 8], [26, 14], [25, 26], [16, 30]], '#6f7570', '#3c423e');
      poly([[12, 15], [17, 11], [23, 15], [19, 20], [13, 20]], '#9aa39c');
      px(13, 22, 3, 3, '#d8b45a'); px(20, 19, 2.4, 2.4, '#d8b45a'); px(17, 24, 2, 2, '#f0d08a');
    } else if (item.icon === 'crystal') {
      c.save(); c.shadowColor = '#8fe8de'; c.shadowBlur = 8;
      poly([[17, 4], [26, 15], [20, 30], [12, 27], [8, 15]], '#5fbfb8', '#d8fffa');
      poly([[17, 4], [17, 27], [26, 15]], '#a8f0e8aa');
      c.restore();
    } else if (item.icon === 'shard') {
      c.save(); c.shadowColor = '#c49be8'; c.shadowBlur = 7;
      poly([[17, 4], [25, 16], [17, 30], [9, 17]], '#8a62c0', '#e8d0ff');
      px(15, 8, 2, 14, '#d8b0ff');
      c.restore();
    } else if (item.icon === 'hide') {
      poly([[8, 8], [24, 7], [28, 16], [24, 29], [10, 28], [6, 17]], '#a8794a', '#5a3c24');
      px(12, 11, 10, 3, '#c69a68'); px(14, 18, 6, 4, '#8a6038');
    } else if (item.icon === 'slime') {
      c.fillStyle = '#8ade63'; c.beginPath(); c.ellipse(17, 20, 10, 8, 0, 0, Math.PI * 2); c.fill();
      c.strokeStyle = '#d8ff9a'; c.lineWidth = 1; c.stroke();
      px(13, 18, 3, 4, '#1b2a18'); px(19, 18, 3, 4, '#1b2a18');
    } else if (item.icon === 'essence') {
      c.save(); c.shadowColor = '#7cf7df'; c.shadowBlur = 9;
      c.fillStyle = '#56e3c8'; c.beginPath(); c.arc(17, 17, 8, 0, Math.PI * 2); c.fill();
      c.fillStyle = '#e6fff9'; c.beginPath(); c.arc(15, 14.5, 3.4, 0, Math.PI * 2); c.fill();
      c.restore();
    } else if (item.icon === 'rune_dust') {
      poly([[10, 13], [24, 13], [26, 27], [8, 27]], '#6b4d8a', '#cfa8ff');
      px(13, 9, 8, 4, '#d9b468');
      px(13, 18, 2.5, 2.5, '#ffe89c'); px(18, 21, 2.5, 2.5, '#9df5ff'); px(16, 15, 2, 2, '#f0b8ff');
    } else if (item.icon === 'mithril') {
      c.save(); c.shadowColor = '#93dcff'; c.shadowBlur = 6;
      poly([[7, 22], [12, 12], [27, 12], [23, 22]], '#7ec8eb', '#e4f8ff');
      poly([[7, 22], [23, 22], [25, 26], [9, 26]], '#4f8eb0');
      px(13, 14, 10, 2, '#ffffffbb');
      c.restore();
    } else {
      px(10, 10, 14, 14, '#8a7a5a'); px(13, 13, 8, 8, '#b0a078');
    }
    c.restore();
  }
  function iconCanvas(item, size) {
    const cv = document.createElement('canvas');
    cv.width = cv.height = size || 34;
    cv.className = 'mcIcon';
    drawIcon(cv, item);
    return cv;
  }

  /* ── overlay / UI construction ─────────────────────────────────────── */
  function ensureOverlay() {
    let el = document.getElementById('invOverlay');
    if (!el) return null;
    if (el.dataset.mc === '1') return el;
    el.dataset.mc = '1';
    el.classList.add('mcInvOverlay');
    el.innerHTML = `
      <section class="mcWindow" role="document">
        <header class="mcHead">
          <div>
            <span class="mcEyebrow">СУМКА ПУТНИКА</span>
            <h2>Снаряжение и трофеи</h2>
            <small id="mcMeta">—</small>
          </div>
          <div class="mcHeadRight">
            <span id="mcGold" class="mcGold">0 ◉</span>
            <button type="button" class="mcClose" id="mcClose" aria-label="Закрыть инвентарь">✕</button>
          </div>
        </header>
        <div class="mcBody">
          <aside class="mcSide">
            <div class="mcPaper">
              <canvas id="mcAvatar" width="142" height="166" aria-label="Персонаж"></canvas>
              <div class="mcEquip mcEquipSix">
                <button type="button" class="mcSlot mcEquipSlot" data-equip="weapon" aria-label="Оружие в руке"><span class="mcSlotKey">РУКА</span></button>
                <button type="button" class="mcSlot mcEquipSlot" data-equip="gear" aria-label="Надетая броня"><span class="mcSlotKey">БРОНЯ</span></button>
                <button type="button" class="mcSlot mcEquipSlot" data-equip="ring" aria-label="Кольцо"><span class="mcSlotKey">КОЛЬЦО</span></button>
                <button type="button" class="mcSlot mcEquipSlot" data-equip="amulet" aria-label="Ожерелье"><span class="mcSlotKey">АМУЛЕТ</span></button>
                <button type="button" class="mcSlot mcEquipSlot" data-equip="artifact_1" aria-label="Артефакт I"><span class="mcSlotKey">АРТ I</span></button>
                <button type="button" class="mcSlot mcEquipSlot" data-equip="artifact_2" aria-label="Артефакт II"><span class="mcSlotKey">АРТ II</span></button>
              </div>
            </div>
            <div class="mcStats" id="mcStats"></div>
          </aside>
          <section class="mcMain">
            <div class="mcFilterToolbar">
              <div class="mcFilterTabs" id="mcFilterBar" role="tablist" aria-label="Фильтр предметов">
                <button type="button" class="mcFilterBtn active" data-mc-filter="all">Все</button>
                <button type="button" class="mcFilterBtn" data-mc-filter="weapon">Оружие</button>
                <button type="button" class="mcFilterBtn" data-mc-filter="gear">Броня</button>
                <button type="button" class="mcFilterBtn" data-mc-filter="accessory">Реликвии</button>
                <button type="button" class="mcFilterBtn" data-mc-filter="consumable">Зелья</button>
                <button type="button" class="mcFilterBtn" data-mc-filter="material">Ресурсы</button>
              </div>
              <input type="search" id="mcSearch" class="mcSearchInput" placeholder="Поиск в сумке..." autocomplete="off" />
            </div>
            <div class="mcGridWrap" id="mcGridWrap">
              <div class="mcGrid" id="mcGrid" aria-label="Предметы"></div>
            </div>
            <div class="mcHotbarEdit">
              <span class="mcHotbarLabel">Быстрый доступ (1–9)</span>
              <div class="mcHotbarSlots" id="mcHotbarEdit"></div>
            </div>
            <div class="mcActions" id="mcActions"><span class="mcHint">Выбери предмет. Двойной клик — экипировать или использовать. Колёсико мыши прокручивает сумку.</span></div>
            <div class="mcCraftBlock">
              <h3 class="craftHeadTitle">Ремесло из собранных материалов</h3>
              <nav class="invCraftTabs" id="craftTabs" aria-label="Категории ремесла">
                <button type="button" class="active" data-craft-tab="supplies">Расходники</button>
                <button type="button" data-craft-tab="weapon">Оружие</button>
                <button type="button" data-craft-tab="gear">Броня</button>
                <button type="button" data-craft-tab="accessory">Реликвии</button>
              </nav>
              <div class="craft invCraftGrid" id="craftGrid"></div>
            </div>
            <p class="mcFootNote">Клавиши <b>1–9</b> — горячий слот, <b>I</b> — сумка, перековка, закалка и авторское оружие — у <b>Кузнеца</b>.</p>
          </section>
        </div>
      </section>`;
    el.addEventListener('click', e => {
      if (e.target === el) closeMC();
      const fbtn = e.target?.closest?.('[data-mc-filter]');
      if (fbtn) {
        activeFilter = fbtn.dataset.mcFilter || 'all';
        (el.querySelectorAll?.('[data-mc-filter]') || []).forEach(b => b.classList?.toggle('active', b === fbtn));
        invSig = '';
        renderMC(meSafe());
      }
    });
    el.querySelector('#mcClose')?.addEventListener('click', closeMC);
    el.querySelector('#mcSearch')?.addEventListener('input', e => {
      searchQuery = String(e.target?.value || '').trim().toLowerCase();
      invSig = '';
      renderMC(meSafe());
    });
    el.addEventListener('pointermove', onDragMove);
    el.addEventListener('pointerup', onDragEnd);
    el.addEventListener('pointercancel', () => endDrag(false));
    return el;
  }

  function openMC() {
    const el = ensureOverlay();
    if (!el) return;
    invOpen = true;
    invSig = '';
    el.style.display = 'flex';
    renderMC(meSafe());
    requestAnimationFrame(() => { const b = document.getElementById('mcClose'); if (b) b.focus(); });
  }
  function closeMC() {
    invOpen = false;
    const el = document.getElementById('invOverlay');
    if (el) el.style.display = 'none';
    hideTooltip();
    endDrag(false);
  }

  function slotEl(item, opts) {
    const o = opts || {};
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'mcSlot' + (item ? ` rarity-${item.rarity || 'common'}` : '') + (o.cls ? ' ' + o.cls : '') + (item && item.equipped ? ' isEquipped' : '') + (selected === (item && item.id) ? ' isSelected' : '');
    if (item) {
      b.dataset.item = item.id;
      const cv = iconCanvas(item, 34);
      b.appendChild(cv);
      if (item.count > 1) {
        const n = document.createElement('span'); n.className = 'mcCount'; n.textContent = item.count > 999 ? '999+' : String(item.count); b.appendChild(n);
      } else if (item.upgrade > 0) {
        const u = document.createElement('span'); u.className = 'mcUpgradeBadge'; u.textContent = `+${item.upgrade}`; b.appendChild(u);
      }
      if (item.equipped) { const t = document.createElement('span'); t.className = 'mcTag'; t.textContent = '✓'; b.appendChild(t); }
      b.setAttribute('aria-label', `${item.name}${item.count > 1 ? ' × ' + item.count : ''}`);
    }
    if (o.keyLabel) {
      const k = document.createElement('span'); k.className = 'mcKey'; k.textContent = o.keyLabel; b.appendChild(k);
    }
    if (o.hotIndex !== undefined) b.dataset.hotSlot = String(o.hotIndex);
    if (o.equip) b.dataset.equip = o.equip;
    if (item) {
      b.addEventListener('pointerenter', () => showTooltip(b, item));
      b.addEventListener('pointerleave', hideTooltip);
      b.addEventListener('focus', () => showTooltip(b, item));
      b.addEventListener('blur', hideTooltip);
      b.addEventListener('pointerdown', e => onDragStart(e, item, b, o));
      b.addEventListener('dblclick', e => { e.preventDefault(); primaryAction(item); });
      b.addEventListener('contextmenu', e => { e.preventDefault(); if (o.hotIndex === undefined) quickAssign(item); });
    } else if (o.equip) {
      b.addEventListener('pointerdown', e => onDragStart(e, null, b, o));
    } else if (o.hotIndex !== undefined) {
      b.addEventListener('pointerdown', e => onDragStart(e, null, b, o));
      b.addEventListener('click', () => hotbarSlotClick(o.hotIndex));
    }
    return b;
  }

  function renderMC(p) {
    if (!invOpen || !p) return;
    const el = document.getElementById('invOverlay');
    if (!el || el.dataset.mc !== '1') return;
    const items = inventoryItems(p);
    const eqAcc = p.equipped_accessories || {};
    const sig = JSON.stringify([
      items.map(i => [i.id, i.count, i.equipped, i.upgrade, i.reforge?.id]),
      eqAcc, activeFilter, searchQuery,
      p.gold, p.hp, p.max_hp, p.mana, p.max_mana, p.stamina, p.max_stamina, p.defense, p.crit_chance_pct,
      hotbar, selected,
    ]);
    if (sig === invSig) return;
    invSig = sig;

    const filtered = items.filter(it => {
      if (activeFilter !== 'all') {
        if (activeFilter === 'material' && it.kind !== 'material' && it.kind !== 'ammo') return false;
        if (activeFilter !== 'material' && it.kind !== activeFilter) return false;
      }
      if (searchQuery) {
        const hay = `${it.name || ''} ${it.desc || ''} ${it.lore || ''}`.toLowerCase();
        if (!hay.includes(searchQuery)) return false;
      }
      return true;
    });

    document.getElementById('mcMeta').textContent = `${items.length} предметов в коллекции · уровень ${p.level} · ${p.class_name || 'Путник'}`;
    const goldNode = document.getElementById('mcGold');
    if (goldNode) goldNode.textContent = `${p.gold || 0} ◉`;
    document.getElementById('mcGold').textContent = `${p.gold || 0} ◉`;

    // 6 слотов экипировки (Оружие, Броня, Кольцо, Ожерелье, Артефакт I, Артефакт II)
    const equipLayout = [
      ['weapon', p.weapon, 'РУКА'],
      ['gear', p.gear, 'БРОНЯ'],
      ['ring', eqAcc.ring || '', 'КОЛЬЦО'],
      ['amulet', eqAcc.amulet || '', 'АМУЛЕТ'],
      ['artifact_1', eqAcc.artifact_1 || '', 'АРТ I'],
      ['artifact_2', eqAcc.artifact_2 || '', 'АРТ II'],
    ];
    for (const [kind, id, emptyLabel] of equipLayout) {
      const slot = el.querySelector(`.mcEquipSlot[data-equip="${kind}"]`);
      if (!slot) continue;
      slot.replaceChildren();
      const item = id ? resolveItem(p, id) : null;
      slot.className = `mcSlot mcEquipSlot rarity-${item?.rarity || 'common'}`;
      slot.dataset.equip = kind;
      if (item) {
        slot.appendChild(iconCanvas(item, 32));
        slot.setAttribute('title', item.name);
        if (item.upgrade > 0) {
          const u = document.createElement('span'); u.className = 'mcUpgradeBadge'; u.textContent = `+${item.upgrade}`; slot.appendChild(u);
        }
        const k = document.createElement('span'); k.className = 'mcEquipMiniTag'; k.textContent = emptyLabel; slot.appendChild(k);
      } else {
        const k = document.createElement('span'); k.className = 'mcSlotKey'; k.textContent = emptyLabel; slot.appendChild(k);
      }
      slot.onclick = () => {
        if (!item) return;
        selected = item.id;
        invSig = '';
        renderMC(meSafe());
      };
      slot.ondblclick = e => {
        e.preventDefault();
        if (item && ['ring', 'amulet', 'artifact_1', 'artifact_2'].includes(kind)) {
          send({ type: 'unequip_accessory', slot: kind });
        }
      };
      if (item) {
        slot.addEventListener('pointerenter', () => showTooltip(slot, item));
        slot.addEventListener('pointerleave', hideTooltip);
        slot.addEventListener('pointerdown', ev => onDragStart(ev, item, slot, { equip: kind }));
      }
    }

    // Прокручиваемая сетка предметов (минимум 36 слотов, автоматически растёт при >31 предмета!)
    const grid = document.getElementById('mcGrid');
    grid.replaceChildren();
    const total = filtered.length <= 31 ? 36 : Math.ceil((filtered.length + 9) / 9) * 9;
    for (let i = 0; i < total; i++) {
      const item = filtered[i] || null;
      grid.appendChild(slotEl(item, {}));
    }

    // hotbar edit row
    const hot = document.getElementById('mcHotbarEdit');
    hot.replaceChildren();
    for (let i = 0; i < 9; i++) {
      const item = resolveItem(p, hotbar[i]) || null;
      hot.appendChild(slotEl(item, { hotIndex: i, keyLabel: String(i + 1) }));
    }

    // Сводка характеристик с учётом колец, амулетов, артефактов и перековки
    const defense = p.defense ?? ((p.gear_catalog?.[p.gear]?.defense || gearDefense?.[p.gear] || 0) + Number(p.upgrades?.gear?.[p.gear] || 0) * 3);
    const w = p.weapon_catalog?.[p.weapon] || {};
    const eqB = p.equipment_bonuses || {};
    const bonusPills = [];
    if (eqB.damage_pct) bonusPills.push(`${eqB.damage_pct > 0 ? '+' : ''}${Math.round(eqB.damage_pct * 100)}% урон`);
    if (eqB.spell_power_pct) bonusPills.push(`+${Math.round(eqB.spell_power_pct * 100)}% чары`);
    if (eqB.attack_speed_pct) bonusPills.push(`${eqB.attack_speed_pct > 0 ? '+' : ''}${Math.round(eqB.attack_speed_pct * 100)}% ск.атаки`);
    if (eqB.move_speed_pct) bonusPills.push(`+${Math.round(eqB.move_speed_pct * 100)}% бег`);
    if (eqB.vampirism_pct) bonusPills.push(`+${Math.round(eqB.vampirism_pct * 100)}% вамп.`);
    if (eqB.cdr_pct) bonusPills.push(`-${Math.round(eqB.cdr_pct * 100)}% КД`);
    document.getElementById('mcStats').innerHTML = `
      <div class="mcStat"><span>Здоровье</span><b>${Math.ceil(p.hp)} / ${p.max_hp}</b></div>
      <div class="mcStat"><span>Мана</span><b>${Math.floor(p.mana || 0)} / ${p.max_mana || 0}</b></div>
      <div class="mcStat"><span>Выносливость</span><b>${Math.floor(p.stamina)} / ${p.max_stamina}</b></div>
      <div class="mcStat"><span>Защита / Крит</span><b>${defense} 🛡 · ${p.crit_chance_pct ?? p.crit_chance ?? 0}%</b></div>
      <div class="mcStat"><span>Оружие</span><b>${escapeHtml(w.name || '—')}</b></div>
      ${bonusPills.length ? `<div class="mcStat mcBonusRow"><span>Реликвии</span><b>${escapeHtml(bonusPills.slice(0, 4).join(' · '))}</b></div>` : `<div class="mcStat"><span>Опыт</span><b>${p.xp || 0} / ${p.xp_next || p.level * 120}</b></div>`}`;
    renderActions(p);
    drawAvatar(p);
    renderHotbar(p);
    // Crafting tabs live inside this window and are re-bound after every rebuild
    // of the markup, because the overlay body is regenerated on open.
    const craftHost = document.getElementById('craftGrid');
    if (craftHost && typeof window.renderCraftPanel === 'function') {
      try { window.renderCraftPanel(p); } catch (err) { console.warn('renderCraftPanel', err); }
      (el.querySelectorAll?.('#craftTabs [data-craft-tab]') || []).forEach(btn => {
        btn.addEventListener('click', () => {
          if (typeof window.setCraftTab === 'function') window.setCraftTab(btn.dataset.craftTab);
        });
      });
    }
  }

  function renderActions(p) {
    const box = document.getElementById('mcActions');
    if (!box) return;
    const item = selected ? resolveItem(p, selected) : null;
    if (!item) {
      box.innerHTML = '<span class="mcHint">Выбери предмет. Двойной клик — экипировать или использовать. Перетащи реликвии в слоты Кольца, Амулета или Артефактов.</span>';
      return;
    }
    const actions = [];
    if (item.kind === 'weapon') actions.push(`<button type="button" data-mc-action="primary">${item.equipped ? 'Уже в руке' : 'Взять в руку'}</button>`);
    if (item.kind === 'gear') actions.push(`<button type="button" data-mc-action="primary">${item.equipped ? 'Уже надето' : 'Надеть'}</button>`);
    if (item.kind === 'accessory') {
      if (item.equipped) actions.push('<button type="button" data-mc-action="unequip">Снять</button>');
      else if (item.slotType === 'artifact') {
        actions.push('<button type="button" data-mc-action="art1">В Артефакт I</button>');
        actions.push('<button type="button" data-mc-action="art2">В Артефакт II</button>');
      } else {
        actions.push('<button type="button" data-mc-action="primary">Надеть</button>');
      }
    }
    if (item.kind === 'consumable') actions.push(`<button type="button" data-mc-action="primary">Использовать</button>`);
    if (item.kind !== 'material' && item.kind !== 'ammo' && item.kind !== 'accessory') actions.push('<button type="button" data-mc-action="hot">В горячий слот</button>');
    const refBadge = item.reforge ? `<span class="mcReforgePill" style="color:${TIER_COL[String(item.reforge.tier)] || '#d8e4dc'}">✦ ${escapeHtml(item.reforge.name)}: ${escapeHtml(item.reforge.summary)}</span>` : '';
    box.innerHTML = `<div class="mcSel"><span class="mcSelIcon"></span><div><b class="rarity-${item.rarity}">${escapeHtml(item.name)}</b><small>${escapeHtml(item.desc || '')}${item.count > 1 ? ` · ${item.count} шт.` : ''}</small>${refBadge}</div></div><div class="mcActBtns">${actions.join('')}</div>`;
    const iconHost = box.querySelector?.('.mcSelIcon');
    if (iconHost) iconHost.appendChild(iconCanvas(item, 30));
    (box.querySelectorAll?.('[data-mc-action]') || []).forEach(b => b.addEventListener('click', () => {
      const act = b.dataset.mcAction;
      if (act === 'primary') primaryAction(item);
      else if (act === 'unequip' && item.equippedSlot) send({ type: 'unequip_accessory', slot: item.equippedSlot });
      else if (act === 'art1') send({ type: 'equip_accessory', id: item.id, slot: 'artifact_1' });
      else if (act === 'art2') send({ type: 'equip_accessory', id: item.id, slot: 'artifact_2' });
      else quickAssign(item);
    }));
  }

  function drawAvatar(p) {
    const cv = document.getElementById('mcAvatar');
    if (!cv) return;
    const c = cv.getContext('2d');
    const w = cv.width, h = cv.height;
    c.clearRect(0, 0, w, h);
    c.imageSmoothingEnabled = false;
    const grd = c.createRadialGradient(w / 2, h * .82, 4, w / 2, h * .82, w * .6);
    grd.addColorStop(0, '#3a4a34'); grd.addColorStop(1, '#141c16');
    c.fillStyle = grd; c.fillRect(0, 0, w, h);
    c.fillStyle = '#0a100c55'; c.beginPath(); c.ellipse(w / 2, h * .86, w * .32, 12, 0, 0, Math.PI * 2); c.fill();
    const coatMap = { traveler: '#547c50', wolf_cloak: '#778d8d', moss_guard: '#8bb56b', marsh_armor: '#9c815e', moonweave: '#9bc8bd', ash_plate: '#a8aaa4', colossus_core: '#f49a60', glacier_mantle: '#8ee8f2', rift_plate: '#bd85ed', obsidian_shell: '#887090', starseer_robe: '#d2a4d7', elder_mantle: '#8ec884' };
    const trimMap = { traveler: '#e6cf8f', wolf_cloak: '#a8d8c8', moss_guard: '#a8d878', marsh_armor: '#d8b878', moonweave: '#b8e8e0', ash_plate: '#e8d0b0', colossus_core: '#ffb078', glacier_mantle: '#c8f8ff', rift_plate: '#dcb0ff', obsidian_shell: '#bb9cc8', starseer_robe: '#f0c8f8', elder_mantle: '#c8f0a8' };
    const model = window.LesEchoView?.drawHeroModel;
    c.save(); c.translate(w / 2, h * .84); c.scale(2.1, 2.1);
    if (model) {
      model(c, { class: p.class, weapon: p.weapon, face_x: 1 }, {
        coat: coatMap[p.gear] || '#547c50', trim: trimMap[p.gear] || '#e6cf8f',
        time: performance.now() / 1000, walk: .6, move: 0, local: true,
      });
    }
    c.restore();
  }

  /* ── hotbar HUD ─────────────────────────────────────────────────────── */
  function ensureHotbar() {
    let host = document.getElementById('mcHotbar');
    if (host) return host;
    host = document.createElement('div');
    host.id = 'mcHotbar';
    host.className = 'mcHotbar';
    host.setAttribute('aria-label', 'Горячий доступ');
    document.querySelector('.game')?.appendChild(host);
    return host;
  }

  function renderHotbar(pArg) {
    const p = pArg || meSafe();
    const host = ensureHotbar();
    if (!p || !host) return;
    const sig = JSON.stringify([hotbar, p.weapon, p.inventory, p.gear]);
    if (sig === hotSig) return;
    hotSig = sig;
    host.replaceChildren();
    for (let i = 0; i < 9; i++) {
      const item = resolveItem(p, hotbar[i]) || null;
      const slot = document.createElement('button');
      slot.type = 'button';
      slot.className = 'mcHotSlot' + (item ? ` rarity-${item.rarity}` : '') + (item && item.equipped ? ' isActive' : '');
      slot.dataset.hotSlot = String(i);
      slot.title = item ? `${item.name} · клавиша ${i + 1}` : `Пустой слот · ${i + 1}`;
      if (item) {
        slot.appendChild(iconCanvas(item, 30));
        if (item.count > 1) { const n = document.createElement('span'); n.className = 'mcCount'; n.textContent = item.count > 999 ? '999+' : item.count; slot.appendChild(n); }
      }
      const k = document.createElement('span'); k.className = 'mcKey'; k.textContent = String(i + 1); slot.appendChild(k);
      slot.addEventListener('click', () => hotbarSlotClick(i));
      slot.addEventListener('pointerenter', () => item && showTooltip(slot, item));
      slot.addEventListener('pointerleave', hideTooltip);
      host.appendChild(slot);
    }
  }

  function hotbarSlotClick(i) {
    const p = meSafe(); if (!p) return;
    const id = hotbar[i];
    if (!id) { toast(`Слот ${i + 1} пуст. Перетащи в него предмет в сумке.`); return; }
    const item = resolveItem(p, id);
    if (!item) { toast('Этого предмета больше нет в сумке.'); return; }
    if (item.kind === 'weapon') { if (!item.equipped) { if (window.heroGesture) window.heroGesture('swap'); send({ type: 'weapon', id: item.id }); toast(`В руке: ${item.name}`); } return; }
    if (item.kind === 'gear') { if (!item.equipped) { send({ type: 'equip_gear', id: item.id }); } return; }
    if (item.kind === 'consumable') { useConsumable(item); return; }
    if (item.kind === 'ammo') { toast(`Стрелы: ${item.count}. Нужны для лука.`); return; }
    toast(`${item.name}: ${item.count} шт. Материал для ремесла.`);
  }

  function useConsumable(item) {
    if (!item || item.kind !== 'consumable') return;
    if (item.count <= 0) { toast('В сумке нет этого зелья.'); return; }
    if (window.heroGesture) window.heroGesture('drink');
    send({ type: 'use_consumable', id: item.id });
    // A small local flourish so the key press always feels responsive.
    const p = meSafe();
    if (p && window.spawnParticles) {
      const col = item.id === 'mana_potion' ? '#7fc4ff' : item.id === 'stamina_potion' ? '#b6e884' : item.id === 'elixir' ? '#ffe79a' : '#ff9a8a';
      spawnParticles(p.x, p.y - 12, col, 18, 2.4, 3, .7);
    }
  }

  function primaryAction(item) {
    if (!item) return;
    if (item.kind === 'weapon' && !item.equipped) { if (window.heroGesture) window.heroGesture('swap'); send({ type: 'weapon', id: item.id }); toast(`В руке: ${item.name}`); }
    else if (item.kind === 'gear' && !item.equipped) { send({ type: 'equip_gear', id: item.id }); }
    else if (item.kind === 'accessory') {
      if (item.equipped && item.equippedSlot) send({ type: 'unequip_accessory', slot: item.equippedSlot });
      else send({ type: 'equip_accessory', id: item.id });
    }
    else if (item.kind === 'consumable') useConsumable(item);
    else if (item.kind === 'weapon') toast(`${item.name} уже в руке.`);
    else if (item.kind === 'gear') toast(`${item.name} уже надето.`);
  }

  function quickAssign(item) {
    if (!item || item.kind === 'material' || item.kind === 'ammo') { toast('Этот предмет не используется из горячего слота.'); return; }
    let idx = hotbar.findIndex(v => !v);
    if (idx < 0) idx = hotbar.findIndex(v => v === item.id);
    if (idx < 0) idx = 8;
    hotbar[idx] = item.kind === 'weapon' ? item.id : item.id;
    saveHotbar(); hotSig = ''; invSig = '';
    toast(`${item.name} → слот ${idx + 1}`);
    renderHotbar(meSafe()); renderMC(meSafe());
  }

  /* ── boss plate ─────────────────────────────────────────────────────── */
  let bossSig = '';
  function ensureBossBar() {
    let el = document.getElementById('bossBar');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'bossBar';
    el.className = 'bossBar';
    el.setAttribute('aria-live', 'polite');
    el.innerHTML = '<b id="bossName">—</b><div class="bossTrack"><i id="bossFill"></i></div><div class="bossPoiseTrack" title="Шкала стойкости: заполни ударами, чтобы ошеломить босса (+35% урона)"><i id="bossPoiseFill"></i></div><small id="bossMeta"></small>';
    document.querySelector('.game')?.appendChild(el);
    return el;
  }
  function renderBossBar() {
    const p = meSafe();
    const host = ensureBossBar();
    if (!p || !host) return;
    const bosses = (snap?.mobs || []).filter(m => m.boss || ['colossus', 'echo_dragon', 'astral_titan', 'ancient_warden', 'obsidian_sentinel', 'crystal_stag', 'sun_golem'].includes(m.kind));
    let best = null, bestDist = Infinity;
    for (const m of bosses) {
      const d = Math.hypot(m.x - p.x, m.y - p.y);
      if (d < bestDist) { bestDist = d; best = m; }
    }
    if (!best || bestDist > 900) { host.classList.remove('show'); bossSig = ''; return; }
    host.classList.add('show');
    const frac = Math.max(0, Math.min(1, best.hp / Math.max(1, best.maxHp || best.max_hp)));
    const poiseFrac = best.staggered ? 1 : Math.max(0, Math.min(1, Number(best.stagger_pct || 0) / 100));
    const sig = `${best.id}:${Math.round(frac * 1000)}:${Math.round(poiseFrac * 100)}:${best.staggered ? 1 : 0}:${best.bleeding ? 1 : 0}:${best.sundered ? 1 : 0}:${best.slowed ? 1 : 0}:${best.stunned ? 1 : 0}:${best.level}`;
    if (sig === bossSig) return;
    bossSig = sig;
    host.classList.toggle('isStaggered', !!best.staggered);
    const nameEl = document.getElementById('bossName'), fillEl = document.getElementById('bossFill'), poiseEl = document.getElementById('bossPoiseFill'), metaEl = document.getElementById('bossMeta');
    const label = typeof mobNames !== 'undefined' ? (mobNames[best.kind] || best.kind) : best.kind;
    if (nameEl) nameEl.textContent = label;
    if (fillEl) fillEl.style.width = `${frac * 100}%`;
    if (poiseEl) poiseEl.style.width = `${poiseFrac * 100}%`;
    const statuses = [];
    if (best.staggered) statuses.push('⚡ ОШЕЛОМЛЁН (+35% УРОНА)');
    if (best.bleeding) statuses.push('🩸 Кровоток');
    if (best.sundered) statuses.push('🛡 Раскол');
    if (best.slowed) statuses.push('❄ Озноб');
    if (best.stunned && !best.staggered) statuses.push('✦ Скован');
    if (metaEl) metaEl.textContent = `${best.boss ? 'БОСС' : 'ЭЛИТНЫЙ ВРАГ'} · ур. ${best.level} · ${Math.ceil(best.hp)} / ${best.maxHp || best.max_hp}${statuses.length ? ' · ' + statuses.join(' · ') : ''}`;
  }

  /* ── drag & drop ────────────────────────────────────────────────────── */
  function onDragStart(e, item, el, opts) {
    if (e.button !== 0) return;
    const o = opts || {};
    if (o.hotIndex !== undefined && !item) return;
    if (o.equip && !item) return;
    dragState = { item, fromHot: o.hotIndex, fromEquip: o.equip, startX: e.clientX, startY: e.clientY, moved: false, ghost: null, sourceEl: el };
    el.setPointerCapture?.(e.pointerId);
  }
  function onDragMove(e) {
    if (!dragState) return;
    if (!dragState.moved) {
      if (Math.hypot(e.clientX - dragState.startX, e.clientY - dragState.startY) < 7) return;
      dragState.moved = true;
      if (dragState.item) {
        const g = document.createElement('div');
        g.className = 'mcGhost';
        g.appendChild(iconCanvas(dragState.item, 34));
        document.body.appendChild(g);
        dragState.ghost = g;
        dragState.sourceEl?.classList.add('isDragging');
      }
    }
    if (dragState.ghost) {
      dragState.ghost.style.left = `${e.clientX + 10}px`;
      dragState.ghost.style.top = `${e.clientY + 10}px`;
    }
  }
  function onDragEnd(e) {
    if (!dragState) return;
    const st = dragState;
    if (!st.moved) {
      // plain click: select the item
      if (st.item) { selected = st.item.id; invSig = ''; renderMC(meSafe()); }
      else if (st.fromHot !== undefined) hotbarSlotClick(st.fromHot);
      dragState = null;
      return;
    }
    const target = document.elementFromPoint(e.clientX, e.clientY)?.closest('[data-hot-slot],[data-equip]');
    const p = meSafe();
    if (target && p) {
      const hotIdx = target.dataset.hotSlot;
      const equip = target.dataset.equip;
      if (hotIdx !== undefined) {
        const i = Number(hotIdx);
        const moved = st.item ? st.item.id : '';
        const prev = hotbar[i];
        if (st.item) hotbar[i] = moved;
        else hotbar[i] = '';
        if (st.fromHot !== undefined && st.fromHot !== i) hotbar[st.fromHot] = prev || '';
        else if (st.fromEquip === 'weapon') hotbar[i] = '@weapon';
        saveHotbar(); hotSig = ''; invSig = '';
        if (st.item) toast(`${st.item.name} → слот ${i + 1}`);
      } else if (equip && st.item) {
        if (equip === 'weapon' && st.item.kind === 'weapon') send({ type: 'weapon', id: st.item.id });
        else if (equip === 'gear' && st.item.kind === 'gear') send({ type: 'equip_gear', id: st.item.id });
        else if (equip === 'ring' && st.item.kind === 'accessory' && st.item.slotType === 'ring') send({ type: 'equip_accessory', id: st.item.id, slot: 'ring' });
        else if (equip === 'amulet' && st.item.kind === 'accessory' && st.item.slotType === 'amulet') send({ type: 'equip_accessory', id: st.item.id, slot: 'amulet' });
        else if ((equip === 'artifact_1' || equip === 'artifact_2') && st.item.kind === 'accessory' && st.item.slotType === 'artifact') send({ type: 'equip_accessory', id: st.item.id, slot: equip });
        else toast('Этот предмет не подходит к выбранному слоту экипировки.');
      }
    } else if (st.fromEquip && ['ring', 'amulet', 'artifact_1', 'artifact_2'].includes(st.fromEquip) && st.moved) {
      send({ type: 'unequip_accessory', slot: st.fromEquip });
    } else if (st.fromHot !== undefined && st.moved) {
      // dragging out of the hotbar clears the slot
      const i = st.fromHot;
      const el = document.elementFromPoint(e.clientX, e.clientY);
      if (!el || !el.closest('.mcWindow')) { hotbar[i] = ''; saveHotbar(); hotSig = ''; invSig = ''; }
    }
    endDrag(true);
  }
  function endDrag(rerender) {
    if (dragState?.ghost) dragState.ghost.remove();
    dragState?.sourceEl?.classList.remove('isDragging');
    dragState = null;
    if (rerender) { renderMC(meSafe()); renderHotbar(meSafe()); }
  }

  /* ── tooltip ────────────────────────────────────────────────────────── */
  function showTooltip(slot, item) {
    hideTooltip();
    if (!item) return;
    const tip = document.createElement('div');
    tip.className = 'mcTooltip';
    const refLine = item.reforge
      ? `<em style="color:${TIER_COL[String(item.reforge.tier)] || '#e2ecd8'}">✦ Модификатор «${escapeHtml(item.reforge.name)}»: ${escapeHtml(item.reforge.summary)}</em>`
      : '';
    const loreLine = item.lore ? `<em class="mcLoreLine">${escapeHtml(item.lore)}</em>` : '';
    tip.innerHTML = `<b class="rarity-${item.rarity}">${escapeHtml(item.name)}</b><small>${escapeHtml(item.desc || '')}</small>${refLine}${loreLine}${item.count > 1 ? `<em>Количество: ${item.count}</em>` : ''}`;
    document.body.appendChild(tip);
    tooltipEl = tip;
    const r = slot.getBoundingClientRect(), tr = tip.getBoundingClientRect();
    let left = Math.min(Math.max(8, r.left + r.width / 2 - tr.width / 2), innerWidth - tr.width - 8);
    let top = r.top - tr.height - 10;
    if (top < 8) top = r.bottom + 10;
    tip.style.left = `${left}px`; tip.style.top = `${top}px`;
  }
  function hideTooltip() { if (tooltipEl) { tooltipEl.remove(); tooltipEl = null; } }

  function escapeHtml(s) { return String(s ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]); }

  /* ── install ────────────────────────────────────────────────────────── */
  function install() {
    window.openInventory = openMC;
    window.closeInventory = closeMC;
    window.renderInventory = function (p) { if (invOpen) renderMC(p || meSafe()); };
    window.renderHotbar = renderHotbar;
    window.renderBossBar = renderBossBar;

    // Keep the hotbar in sync with every snapshot.
    const baseHud = window.updateHud;
    if (typeof baseHud === 'function') {
      window.updateHud = function () {
        baseHud();
        const p = meSafe();
        if (p) { renderHotbar(p); renderBossBar(); if (invOpen) renderMC(p); }
      };
    }

    // 1–9 use the hotbar. When a slot is empty the key is left to the spell
    // system, exactly like before this inventory existed.
    window.addEventListener('keydown', e => {
      if (e.repeat) return;
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable) return;
      if (typeof activeGameMenu === 'function' && activeGameMenu()) return;
      // Shift + digit is the spell row, so modified digits never reach the hotbar.
      if (e.shiftKey || e.ctrlKey || e.altKey || e.metaKey) return;
      const m = /^(?:Digit|Numpad)([1-9])$/.exec(e.code);
      if (!m) return;
      const i = Number(m[1]) - 1;
      if (!hotbar[i]) return;
      e.preventDefault(); e.stopImmediatePropagation(); e.stopPropagation();
      hotbarSlotClick(i);
    }, true);

    // Escape closes our window even if another overlay manager looks first.
    window.addEventListener('keydown', e => {
      if (e.key !== 'Escape' || !invOpen) return;
      closeMC();
    }, true);

    ensureHotbar();
    const p = meSafe();
    if (p) renderHotbar(p);
  }

  if (typeof document !== 'undefined') install();

  if (typeof module === 'object' && module.exports) {
    module.exports = { inventoryItems, resolveItem, HOT_KEY, CONSUMABLE_META };
  }
})();
