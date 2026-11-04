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
    bandage: { name: 'Лубяная повязка', desc: '+24 здоровья', color: '#c8b894', color2: '#f0e6c8', kind: 'bandage' },
    throwing_knife: { name: 'Метательные ножи', desc: 'Метательный боеприпас', color: '#a8b8bd', color2: '#e8f4f8', kind: 'knife' },
  };
  const RES_ICON = { wood: 'wood', herb: 'herb', ore: 'ore', crystal: 'crystal', shard: 'shard', hide: 'hide', slime: 'slime', arrows: 'arrows', potion: 'potion', mana_potion: 'potion', stamina_potion: 'potion', elixir: 'potion', bandage: 'bandage', throwing_knife: 'knife' };
  const RARITY_COL = { common: '#b9c0aa', uncommon: '#86cf91', rare: '#79bce2', epic: '#c49be8', legendary: '#f1b75e' };

  let hotbar = loadHotbar();
  let selected = '';
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
    if (resourceNames?.[id]) return resourceNames[id];
    return weaponNames?.[id] || gearNames?.[id] || id;
  }

  /** Resolve one inventory id into a uniform item descriptor. */
  function resolveItem(p, id) {
    if (!p || !id) return null;
    if (id === '@weapon') id = p.weapon;
    const consumable = CONSUMABLE_META[id];
    if (consumable) {
      const count = Number(p.inventory?.[id] || 0);
      return { id, kind: 'consumable', name: consumable.name, desc: consumable.desc, count, rarity: id === 'elixir' ? 'rare' : 'common', color: consumable.color, icon: RES_ICON[id] || 'potion' };
    }
    const weapon = p.weapon_catalog?.[id];
    if (weapon && (p.weapons || []).includes(id)) {
      const up = Number(p.upgrades?.weapon?.[id] || 0);
      return {
        id, kind: 'weapon', name: weapon.name, rarity: weapon.rarity || 'common', count: 1,
        weaponKind: weapon.kind, desc: `${weapon.kind === 'bow' ? 'Лук' : weapon.kind === 'staff' ? 'Посох' : 'Ближний бой'} · урон ${weapon.damage}${up ? ` (+${up})` : ''}${p.weapon === id ? ' · в руке' : ''}`,
        icon: weapon.kind === 'bow' ? 'bow' : weapon.kind === 'staff' ? 'staff' : 'sword', equipped: p.weapon === id,
      };
    }
    const gear = p.gear_catalog?.[id];
    if (gear && (p.gear === id || (p.gear_inventory || []).includes(id))) {
      return { id, kind: 'gear', name: gear.name, rarity: gear.rarity || 'common', count: 1, desc: `Защита ${gear.defense}${p.gear === id ? ' · надето' : ''}`, icon: 'gear', equipped: p.gear === id };
    }
    if (resourceNames?.[id]) {
      return { id, kind: id === 'arrows' ? 'ammo' : 'material', name: resourceNames[id], rarity: RES_ICON[id] === 'crystal' ? 'rare' : 'common', count: Number(p.inventory?.[id] || 0), desc: materialDesc(id), icon: RES_ICON[id] || 'material' };
    }
    return null;
  }

  function materialDesc(id) {
    return ({
      wood: 'Строительный материал и древко для оружия.',
      herb: 'Лунная трава для настоек и зачарований.',
      ore: 'Болотная руда для ковки и стрел.',
      crystal: 'Эхо-кристалл. Нужен мастеру чар.',
      shard: 'Осколок разлома — редкий reagent.',
      hide: 'Шкура для брони и отваров.',
      slime: 'Слизь для настоек.',
      arrows: 'Боеприпас для лука.',
      potion: 'Восстанавливает здоровье.',
    })[id] || 'Материал для ремесла.';
  }

  /** Every owned item, in a stable order: weapons → armour → potions → materials. */
  function inventoryItems(p) {
    if (!p) return [];
    const seen = new Set(), out = [];
    const push = id => { if (!id || seen.has(id)) return; const item = resolveItem(p, id); if (item && (item.count === undefined || item.count > 0)) { seen.add(id); out.push(item); } };
    for (const id of p.weapons || []) push(id);
    push(p.gear);
    for (const id of p.gear_inventory || []) push(id);
    for (const id of Object.keys(CONSUMABLE_META)) if (Number(p.inventory?.[id] || 0) > 0) push(id);
    for (const id of Object.keys(resourceNames || {})) if (Number(p.inventory?.[id] || 0) > 0) push(id);
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
      const blade = item.rarity === 'legendary' ? '#ffd27a' : item.rarity === 'epic' ? '#d9b0ff' : item.rarity === 'rare' ? '#bfe3f5' : '#e6f0ea';
      if (item.icon === 'bow') {
        c.strokeStyle = '#a87c4a'; c.lineWidth = 2.6; c.beginPath(); c.arc(12, 18, 11, -1.15, 1.15); c.stroke();
        c.strokeStyle = '#efe8cf'; c.lineWidth = .9; c.beginPath(); c.moveTo(17, 7.5); c.lineTo(17, 28.5); c.stroke();
        px(16, 4, 2, 7, '#cfd8d2'); px(16, 23, 2, 7, '#cfd8d2');
        poly([[18, 17], [26, 15], [26, 19]], '#c8d8d0');
      } else if (item.icon === 'staff') {
        px(16, 10, 3, 21, '#7a5836'); px(15, 16, 1, 12, '#a8804a');
        c.save(); c.shadowColor = '#a8e8ff'; c.shadowBlur = 6; c.fillStyle = '#bff2ff'; c.beginPath(); c.arc(17.5, 9, 4.2, 0, Math.PI * 2); c.fill(); c.restore();
        c.fillStyle = '#ffffffcc'; c.beginPath(); c.arc(16.4, 8, 1.6, 0, Math.PI * 2); c.fill();
      } else if (/spear|halberd|glaive|scythe|war_maul|axe|warhammer|mace/.test(name) || /halberd|glaive|scythe|war_maul|axe|warhammer|mace|spear/.test(item.id)) {
        c.strokeStyle = '#7a5836'; c.lineWidth = 2.6; c.beginPath(); c.moveTo(9, 29); c.lineTo(23, 7); c.stroke();
        poly([[23, 7], [29, 4], [26, 12], [21, 13]], blade, '#6e7a72');
        px(8, 26, 5, 5, '#c9a25a');
      } else if (/dagger|claw/.test(item.id)) {
        poly([[9, 27], [14, 22], [20, 10], [23, 12], [16, 23]], blade, '#6e7a72');
        poly([[19, 27], [24, 22], [28, 13], [30, 15], [26, 24]], blade, '#6e7a72');
        px(7, 25, 5, 3, '#b89a5c'); px(17, 25, 5, 3, '#b89a5c');
      } else {
        poly([[8, 29], [10, 24], [22, 8], [26, 4], [27, 8], [13, 26]], blade, '#6e7a72');
        px(7, 26, 7, 2.6, '#c9a25a'); px(5.4, 28.6, 3, 4, '#8a6a40');
        c.strokeStyle = '#ffffffaa'; c.lineWidth = .9; c.beginPath(); c.moveTo(22.5, 7.5); c.lineTo(12.5, 22); c.stroke();
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
              <canvas id="mcAvatar" width="150" height="180" aria-label="Персонаж"></canvas>
              <div class="mcEquip">
                <button type="button" class="mcSlot mcEquipSlot" data-equip="weapon" aria-label="Оружие в руке"><span class="mcSlotKey">РУКА</span></button>
                <button type="button" class="mcSlot mcEquipSlot" data-equip="gear" aria-label="Надетая броня"><span class="mcSlotKey">БРОНЯ</span></button>
              </div>
            </div>
            <div class="mcStats" id="mcStats"></div>
          </aside>
          <section class="mcMain">
            <div class="mcGrid" id="mcGrid" aria-label="Предметы"></div>
            <div class="mcHotbarEdit">
              <span class="mcHotbarLabel">Быстрый доступ</span>
              <div class="mcHotbarSlots" id="mcHotbarEdit"></div>
            </div>
            <div class="mcActions" id="mcActions"><span class="mcHint">Выбери предмет. Двойной клик — взять в руку или использовать. Перетащи предмет в горячий слот.</span></div>
            <p class="mcFootNote">Клавиши <b>1–9</b> используют предмет из горячего слота, <b>I</b> — сумка, <b>Esc</b> — закрыть.</p>
          </section>
        </div>
      </section>`;
    el.addEventListener('click', e => {
      if (e.target === el) closeMC();
    });
    el.querySelector('#mcClose').addEventListener('click', closeMC);
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
    const sig = JSON.stringify([items.map(i => [i.id, i.count, i.equipped]), p.gold, p.hp, p.max_hp, p.mana, p.max_mana, p.stamina, p.max_stamina, hotbar, selected]);
    if (sig === invSig) return;
    invSig = sig;
    document.getElementById('mcMeta').textContent = `${items.length} типов предметов · ${p.level} уровень · ${p.class_name || 'Путник'}`;
    document.getElementById('mcGold').textContent = `${p.gold || 0} ◉`;
    // equipment slots
    for (const [kind, id] of [['weapon', p.weapon], ['gear', p.gear]]) {
      const slot = el.querySelector(`.mcEquipSlot[data-equip="${kind}"]`);
      if (!slot) continue;
      slot.replaceChildren();
      const item = resolveItem(p, id);
      slot.className = `mcSlot mcEquipSlot rarity-${item?.rarity || 'common'}`;
      slot.dataset.equip = kind;
      if (item) {
        slot.appendChild(iconCanvas(item, 34));
        slot.setAttribute('title', item.name);
        if (kind === 'weapon') {
          const k = document.createElement('span'); k.className = 'mcEquipLabel'; k.textContent = item.name; slot.appendChild(k);
        }
      } else {
        const k = document.createElement('span'); k.className = 'mcSlotKey'; k.textContent = kind === 'weapon' ? 'РУКА' : 'БРОНЯ'; slot.appendChild(k);
      }
      const equippedItem = resolveItem(p, id);
      slot.onclick = () => primaryAction(equippedItem);
      if (equippedItem) {
        slot.addEventListener('pointerenter', () => showTooltip(slot, equippedItem));
        slot.addEventListener('pointerleave', hideTooltip);
        slot.addEventListener('pointerdown', ev => onDragStart(ev, equippedItem, slot, { equip: kind }));
      }
    }
    // grid
    const grid = document.getElementById('mcGrid');
    grid.replaceChildren();
    const total = 36;
    for (let i = 0; i < total; i++) {
      const item = items[i] || null;
      grid.appendChild(slotEl(item, {}));
    }
    // hotbar edit row
    const hot = document.getElementById('mcHotbarEdit');
    hot.replaceChildren();
    for (let i = 0; i < 9; i++) {
      const item = resolveItem(p, hotbar[i]) || null;
      hot.appendChild(slotEl(item, { hotIndex: i, keyLabel: String(i + 1) }));
    }
    // stats
    const defense = (p.gear_catalog?.[p.gear]?.defense || gearDefense?.[p.gear] || 0) + Number(p.upgrades?.gear?.[p.gear] || 0) * 3;
    const w = p.weapon_catalog?.[p.weapon] || {};
    document.getElementById('mcStats').innerHTML = `
      <div class="mcStat"><span>Здоровье</span><b>${Math.ceil(p.hp)} / ${p.max_hp}</b></div>
      <div class="mcStat"><span>Мана</span><b>${Math.floor(p.mana || 0)} / ${p.max_mana || 0}</b></div>
      <div class="mcStat"><span>Выносливость</span><b>${Math.floor(p.stamina)} / ${p.max_stamina}</b></div>
      <div class="mcStat"><span>Защита</span><b>${defense}</b></div>
      <div class="mcStat"><span>Оружие</span><b>${w.name || '—'}</b></div>
      <div class="mcStat"><span>Опыт</span><b>${p.xp || 0} / ${p.level * 120}</b></div>`;
    renderActions(p);
    drawAvatar(p);
    renderHotbar(p);
  }

  function renderActions(p) {
    const box = document.getElementById('mcActions');
    if (!box) return;
    const item = selected ? resolveItem(p, selected) : null;
    if (!item) {
      box.innerHTML = '<span class="mcHint">Выбери предмет. Двойной клик — взять в руку или использовать. Перетащи предмет в горячий слот.</span>';
      return;
    }
    const actions = [];
    if (item.kind === 'weapon') actions.push(`<button type="button" data-mc-action="primary">${item.equipped ? 'Уже в руке' : 'Взять в руку'}</button>`);
    if (item.kind === 'gear') actions.push(`<button type="button" data-mc-action="primary">${item.equipped ? 'Уже надето' : 'Надеть'}</button>`);
    if (item.kind === 'consumable') actions.push(`<button type="button" data-mc-action="primary">Использовать</button>`);
    if (item.kind !== 'material' && item.kind !== 'ammo') actions.push('<button type="button" data-mc-action="hot">В горячий слот</button>');
    box.innerHTML = `<div class="mcSel"><span class="mcSelIcon"></span><div><b class="rarity-${item.rarity}">${escapeHtml(item.name)}</b><small>${escapeHtml(item.desc || '')}${item.count > 1 ? ` · ${item.count} шт.` : ''}</small></div></div><div class="mcActBtns">${actions.join('')}</div>`;
    const iconHost = box.querySelector('.mcSelIcon');
    if (iconHost) iconHost.appendChild(iconCanvas(item, 30));
    box.querySelectorAll('[data-mc-action]').forEach(b => b.addEventListener('click', () => {
      if (b.dataset.mcAction === 'primary') primaryAction(item);
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
    el.innerHTML = '<b id="bossName">—</b><div class="bossTrack"><i id="bossFill"></i></div><small id="bossMeta"></small>';
    document.querySelector('.game')?.appendChild(el);
    return el;
  }
  function renderBossBar() {
    const p = meSafe();
    const host = ensureBossBar();
    if (!p || !host) return;
    const bosses = (snap?.mobs || []).filter(m => m.boss || ['colossus', 'echo_dragon', 'astral_titan', 'ancient_warden'].includes(m.kind));
    let best = null, bestDist = Infinity;
    for (const m of bosses) {
      const d = Math.hypot(m.x - p.x, m.y - p.y);
      if (d < bestDist) { bestDist = d; best = m; }
    }
    if (!best || bestDist > 900) { host.classList.remove('show'); bossSig = ''; return; }
    host.classList.add('show');
    const frac = Math.max(0, Math.min(1, best.hp / Math.max(1, best.maxHp || best.max_hp)));
    const sig = `${best.id}:${Math.round(frac * 1000)}:${best.level}`;
    if (sig === bossSig) return;
    bossSig = sig;
    const nameEl = document.getElementById('bossName'), fillEl = document.getElementById('bossFill'), metaEl = document.getElementById('bossMeta');
    const label = typeof mobNames !== 'undefined' ? (mobNames[best.kind] || best.kind) : best.kind;
    if (nameEl) nameEl.textContent = label;
    if (fillEl) fillEl.style.width = `${frac * 100}%`;
    if (metaEl) metaEl.textContent = `${best.boss ? 'БОСС' : 'ОПАСНЫЙ ВРАГ'} · ур. ${best.level} · ${Math.ceil(best.hp)} / ${best.maxHp || best.max_hp}`;
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
        else toast(equip === 'weapon' ? 'Сюда можно положить только оружие.' : 'Сюда можно надеть только броню.');
      }
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
    tip.innerHTML = `<b class="rarity-${item.rarity}">${escapeHtml(item.name)}</b><small>${escapeHtml(item.desc || '')}</small>${item.count > 1 ? `<em>Количество: ${item.count}</em>` : ''}`;
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
