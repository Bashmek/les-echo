/* Les Echo — separate region maps, atlas, local NPCs and shops. */
/* global snap, myId, cam, me, $, send, hash, safeText, resourceNames, questStages, questDone,
   drawAvatarSprite, drawMobSprite, marketSignature, spellFx, weaponActions, attackFx, vfxParticles,
   abilityFx, hitFlashes, keys, touchDirs, joyRelease, actionKeyLabel */

const WORLD_UI_VERSION = 2;
const terrainCache = window.EchoTerrainCache?.create(3) || new Map();
const entityViews = EchoMotion.createTracker();
const stationNpc = {};
let currentRegionId = null;
let activeNpc = null;
let atlasSelection = null;
let waypoint = null;
let shopFilter = { text: '', kind: 'all' };
let npcRenderSignature = '', atlasRenderSignature = '';

function esc(v) { return safeText(String(v ?? '')); }
function regionAccent() { return snap?.region?.accent || '#e7c77d'; }
function npcDistance(n) { const p = me(); return p ? Math.hypot(p.x - n.x, p.y - n.y) : Infinity; }
function nearestService(service) {
  return (snap?.region?.npcs || []).filter(n => n.services.includes(service) && npcDistance(n) <= 125)
    .sort((a, b) => npcDistance(a) - npcDistance(b))[0] || null;
}
function entityPosition(e, now) {
  return entityViews.sample(e, now, e.id === myId ? 18 : 32);
}

/* ---------- deterministic pixel terrain ---------- */
function rngFor(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
function px(c, x, y, w, h, color) { c.fillStyle = color; c.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h)); }
function ellipse(c, x, y, rx, ry, color) { c.fillStyle = color; c.beginPath(); c.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); c.fill(); }
function poly(c, pts, fill, stroke) { c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]); c.closePath(); c.fillStyle = fill; c.fill(); if (stroke) { c.strokeStyle = stroke; c.lineWidth = 2; c.stroke(); } }

function pixelTree(c, x, y, s, palette, variant = 0) {
  ellipse(c, x, y + s * .7, s * .8, s * .25, '#00000033');
  px(c, x - s * .12, y - s * .1, s * .24, s * .8, '#4a3828');
  px(c, x - s * .05, y, s * .08, s * .6, '#6b5138');
  const [dark, mid, light] = palette;
  if (variant > .6) {
    poly(c, [[x, y - s], [x - s * .7, y + s * .2], [x + s * .7, y + s * .2]], dark);
    poly(c, [[x, y - s * .7], [x - s * .55, y + s * .35], [x + s * .55, y + s * .35]], mid);
    poly(c, [[x, y - s * .45], [x - s * .4, y + s * .45], [x + s * .4, y + s * .45]], light);
  } else {
    ellipse(c, x - s * .35, y - s * .25, s * .5, s * .45, dark);
    ellipse(c, x + s * .35, y - s * .25, s * .5, s * .45, dark);
    ellipse(c, x, y - s * .55, s * .55, s * .5, mid);
    ellipse(c, x - s * .2, y - s * .65, s * .3, s * .25, light);
    ellipse(c, x + s * .3, y - s * .4, s * .25, s * .2, light);
  }
}
function crystal(c, x, y, s, color, glow = '#ffffff') {
  ellipse(c, x, y + s * .5, s * .6, s * .2, '#00000044');
  poly(c, [[x, y - s], [x - s * .4, y], [x, y + s * .5], [x + s * .4, y]], color, '#00000033');
  poly(c, [[x, y - s], [x, y + s * .5], [x + s * .4, y]], glow + '55');
  px(c, x - 1, y - s * .6, 2, s * .7, '#ffffff88');
}
function rock(c, x, y, s, color) {
  ellipse(c, x, y + s * .35, s * .7, s * .22, '#00000033');
  poly(c, [[x - s * .6, y + s * .3], [x - s * .4, y - s * .35], [x + s * .1, y - s * .5], [x + s * .6, y - s * .1], [x + s * .5, y + s * .35]], color, '#00000033');
  poly(c, [[x - s * .4, y - s * .35], [x + s * .1, y - s * .5], [x + s * .2, y - s * .1], [x - s * .2, y]], '#ffffff22');
}
function ruinPillar(c, x, y, h, color) {
  ellipse(c, x, y + 6, 18, 6, '#00000044');
  px(c, x - 10, y - h, 20, h, color); px(c, x - 14, y - h, 28, 7, '#ffffff22'); px(c, x - 14, y - 4, 28, 8, color);
  px(c, x - 6, y - h + 8, 3, h - 14, '#00000022'); px(c, x + 3, y - h + 8, 3, h - 14, '#00000022');
}
function drawRoad(c, r, pts, width = 52) {
  c.lineCap = 'round'; c.lineJoin = 'round';
  c.strokeStyle = r.dark; c.lineWidth = width + 10; c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) c.lineTo(p[0], p[1]); c.stroke();
  c.strokeStyle = r.id === 'glacier' ? '#b8d4d8' : r.id === 'marsh' ? '#7a6548' : r.id === 'rift' || r.id === 'abyss' ? '#6a5a86' : '#a08a62';
  c.lineWidth = width; c.stroke();
  c.strokeStyle = '#ffffff18'; c.lineWidth = 3; c.setLineDash([10, 14]); c.stroke(); c.setLineDash([]);
  if (r.id === 'marsh') { c.strokeStyle = '#3d3022'; c.lineWidth = 2; for (let i = 0; i < pts.length - 1; i++) { const [x1, y1] = pts[i], [x2, y2] = pts[i + 1], d = Math.hypot(x2 - x1, y2 - y1), n = Math.floor(d / 14); for (let j = 0; j <= n; j++) { const t = j / Math.max(1, n), x = x1 + (x2 - x1) * t, y = y1 + (y2 - y1) * t, a = Math.atan2(y2 - y1, x2 - x1) + Math.PI / 2; c.beginPath(); c.moveTo(x + Math.cos(a) * width / 2, y + Math.sin(a) * width / 2); c.lineTo(x - Math.cos(a) * width / 2, y - Math.sin(a) * width / 2); c.stroke(); } } }
}
function drawStall(c, x, y, color) {
  ellipse(c, x, y + 24, 46, 12, '#00000033');
  px(c, x - 38, y - 6, 76, 30, '#6b4e32'); px(c, x - 34, y - 2, 68, 8, '#8a6a44');
  px(c, x - 40, y - 44, 5, 44, '#4a3624'); px(c, x + 35, y - 44, 5, 44, '#4a3624');
  poly(c, [[x - 48, y - 40], [x + 48, y - 40], [x + 38, y - 58], [x - 38, y - 58]], color, '#00000044');
  for (let i = -3; i <= 3; i += 2) px(c, x + i * 12 - 5, y - 40, 10, 8, i % 4 === 1 ? '#ffffff33' : '#00000022');
  px(c, x - 24, y + 4, 12, 8, '#c9a15d'); px(c, x - 4, y + 2, 10, 10, '#7fb8a8'); px(c, x + 14, y + 4, 14, 8, '#b86d5a');
}
function drawTent(c, x, y, color) {
  ellipse(c, x, y + 26, 56, 14, '#00000033');
  poly(c, [[x - 55, y + 25], [x, y - 45], [x + 55, y + 25]], color, '#00000044');
  poly(c, [[x, y - 45], [x + 55, y + 25], [x + 12, y + 25]], '#00000022');
  poly(c, [[x - 14, y + 25], [x, y - 12], [x + 14, y + 25]], '#241c14');
  px(c, x - 2, y - 52, 4, 12, '#5a432c');
}
function drawLandmark(c, r) {
  const [x, y] = r.landmark_pos;
  ellipse(c, x, y + 30, 110, 34, '#00000033');
  if (r.id === 'camp') {
    for (let i = 0; i < 8; i++) { const a = i / 8 * Math.PI * 2; rock(c, x + Math.cos(a) * 34, y + Math.sin(a) * 20, 10, '#7d7464'); }
    px(c, x - 18, y + 4, 36, 8, '#5a3d26'); px(c, x - 12, y - 2, 24, 8, '#6b4a2e');
  } else if (r.id === 'forest') {
    pixelTree(c, x, y, 85, ['#24452f', '#3f7042', '#7fa653'], .2);
    for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; rock(c, x + Math.cos(a) * 85, y + Math.sin(a) * 50, 12, '#8a9278'); }
  } else if (r.id === 'marsh') {
    px(c, x - 24, y - 90, 48, 110, '#6f7a70'); px(c, x - 30, y - 96, 60, 12, '#8a9588'); px(c, x - 16, y - 110, 32, 18, '#4a5a52');
    px(c, x - 8, y - 70, 16, 20, '#a5f2d8'); px(c, x - 10, y - 20, 20, 40, '#3a3026');
  } else if (r.id === 'ruins') {
    ruinPillar(c, x - 60, y + 20, 90, '#8a7660'); ruinPillar(c, x + 60, y + 20, 90, '#8a7660');
    px(c, x - 74, y - 78, 148, 16, '#9a866c'); px(c, x - 30, y - 10, 60, 34, '#4a3a30'); px(c, x - 18, y - 2, 36, 18, '#ff9a4a');
  } else if (r.id === 'glacier') {
    crystal(c, x, y, 80, '#7fd4e8', '#e8ffff'); crystal(c, x - 55, y + 20, 45, '#5aa8c8'); crystal(c, x + 55, y + 20, 45, '#5aa8c8');
  } else if (r.id === 'rift' || r.id === 'abyss') {
    c.strokeStyle = r.accent; c.lineWidth = 4; for (let i = 0; i < 3; i++) { c.beginPath(); c.ellipse(x, y + 20, 70 - i * 18, 30 - i * 8, 0, 0, Math.PI * 2); c.stroke(); }
    crystal(c, x, y - 20, 55, r.accent); for (let i = 0; i < 6; i++) { const a = i / 6 * Math.PI * 2; ruinPillar(c, x + Math.cos(a) * 95, y + Math.sin(a) * 45 + 20, 40, r.light); }
  } else if (r.id === 'obsidian') {
    crystal(c, x, y, 85, '#3a2a44', '#d5a4cf'); crystal(c, x - 60, y + 20, 50, '#2a1f33', '#b87ad0'); crystal(c, x + 60, y + 20, 50, '#2a1f33', '#b87ad0');
    px(c, x - 70, y + 40, 140, 8, '#ff7a3a');
  } else {
    pixelTree(c, x, y, 110, ['#2a5038', '#4f8448', '#a4c86a'], .1);
    for (let i = 0; i < 10; i++) { const a = i / 10 * Math.PI * 2; px(c, x + Math.cos(a) * 95 - 3, y + Math.sin(a) * 55, 6, 6, i % 2 ? '#f2d98a' : '#e8a0c0'); }
  }
}
function buildTerrain(r) {
  const cv = document.createElement('canvas'); cv.width = r.width; cv.height = r.height;
  const c = cv.getContext('2d'); c.imageSmoothingEnabled = false;
  const rnd = rngFor(r.seed);
  c.fillStyle = r.ground; c.fillRect(0, 0, r.width, r.height);
  for (let y = 0; y < r.height; y += 24) for (let x = 0; x < r.width; x += 24) {
    const v = rnd(); if (v > .55) { c.globalAlpha = .05 + v * .07; px(c, x, y, 24, 24, v > .8 ? r.light : r.dark); c.globalAlpha = 1; }
    if (v > .92) px(c, x + rnd() * 18, y + rnd() * 18, 3, 3, r.light + '55');
  }
  // Water, ice, lava and void features.
  if (r.id === 'marsh' || r.id === 'forest') {
    c.fillStyle = r.id === 'marsh' ? '#2c4a4c' : '#3f6f78';
    c.beginPath(); c.moveTo(1150, 0); c.bezierCurveTo(1050, 300, 1350, 500, 1180, 750); c.bezierCurveTo(1050, 980, 1300, 1200, 1150, 1500); c.lineTo(1350, 1500); c.bezierCurveTo(1450, 1200, 1250, 950, 1380, 750); c.bezierCurveTo(1500, 500, 1250, 300, 1350, 0); c.closePath(); c.fill();
    c.strokeStyle = '#ffffff22'; c.lineWidth = 3; c.stroke();
    for (let i = 0; i < 24; i++) { const x = 1180 + rnd() * 160, y = rnd() * 1500; ellipse(c, x, y, 10 + rnd() * 16, 4, '#ffffff18'); }
  }
  if (r.id === 'marsh') for (let i = 0; i < 14; i++) ellipse(c, 750 + rnd() * 1150, 120 + rnd() * 1260, 50 + rnd() * 90, 25 + rnd() * 45, '#2c4a4c');
  if (r.id === 'glacier') { for (let i = 0; i < 8; i++) { const x = 800 + rnd() * 1000, y = 150 + rnd() * 1200; poly(c, [[x - 90, y], [x - 30, y - 45], [x + 70, y - 25], [x + 95, y + 30], [x + 10, y + 55], [x - 70, y + 35]], '#9fc8d4aa', '#e8ffff55'); } }
  if (r.id === 'rift' || r.id === 'abyss') { for (let i = 0; i < 10; i++) { const x = 800 + rnd() * 1100, y = 120 + rnd() * 1260; poly(c, [[x - 70, y], [x - 20, y - 35], [x + 60, y - 15], [x + 40, y + 30], [x - 30, y + 40]], '#151222', r.accent + '44'); } }
  if (r.id === 'obsidian' || r.id === 'ruins') { c.strokeStyle = r.id === 'obsidian' ? '#ff7a3a' : '#c96a3a'; c.lineWidth = 5; for (let i = 0; i < 12; i++) { let x = 800 + rnd() * 1100, y = 100 + rnd() * 1300; c.beginPath(); c.moveTo(x, y); for (let j = 0; j < 5; j++) { x += (rnd() - .5) * 90; y += 30 + rnd() * 40; c.lineTo(x, y); } c.stroke(); } }
  // Roads connect every waystone, hub, landmark and boss arena.
  drawRoad(c, r, [[0, 820], [350, 820], [615, 820], [1000, 820], [1400, 820], [2000, 820]], 58);
  drawRoad(c, r, [[1000, 820], [1050, 620], [1050, 430], [1480, 390]], 40);
  drawRoad(c, r, [[1400, 820], [1500, 980], [1560, 1130]], 40);
  // Settlement plaza.
  ellipse(c, 470, 800, 330, 260, r.id === 'glacier' ? '#a8c4c8' : r.id === 'rift' || r.id === 'abyss' ? '#5a4e72' : '#8a7a58');
  ellipse(c, 470, 800, 300, 235, r.id === 'glacier' ? '#b8d4d8' : r.id === 'rift' || r.id === 'abyss' ? '#6a5a86' : '#9c8a64');
  for (let i = 0; i < 80; i++) { const a = rnd() * Math.PI * 2, d = Math.sqrt(rnd()); px(c, 470 + Math.cos(a) * d * 290, 800 + Math.sin(a) * d * 225, 5, 3, '#00000018'); }
  // Inlaid plaza stones give the settlement a crafted surface at close zoom.
  c.save();
  c.beginPath();c.ellipse(470,800,287,221,0,0,Math.PI*2);c.clip();
  for(let row=0;row<19;row++)for(let col=0;col<25;col++){
    const x=165+col*26+(row%2)*13,y=568+row*26;
    c.fillStyle=(row+col)%4===0?'#ffffff09':'#191d2510';
    c.fillRect(x+1,y+1,24,24);c.strokeStyle='#ead7a014';c.lineWidth=.7;c.strokeRect(x+2,y+2,22,22);
  }
  c.strokeStyle='#e7d39a30';c.lineWidth=2;
  for(const rad of [80,91]){c.beginPath();c.arc(470,800,rad,0,Math.PI*2);c.stroke();}
  for(let i=0;i<8;i++){
    const a=i*Math.PI/4,x=470+Math.cos(a)*86,y=800+Math.sin(a)*86;
    c.save();c.translate(x,y);c.rotate(a);c.fillStyle='#f0dfaa66';c.fillRect(-2,-3,4,6);c.restore();
  }
  c.restore();
  // Biome decoration, kept clear of roads and the hub.
  const palettes = {
    camp: ['#2e4a32', '#4a7040', '#7fa050'], forest: ['#22452f', '#3f7042', '#7fa653'], marsh: ['#2a4a3a', '#4a7050', '#7a9a60'],
    ruins: ['#3a4030', '#5a6040', '#8a8a58'], glacier: ['#4a7080', '#7aa8b8', '#c8e8f0'], rift: ['#3a2a50', '#6a4a8a', '#a87ad0'],
    abyss: ['#2a2a4a', '#4a4a7a', '#7a7ab0'], obsidian: ['#2a1f33', '#4a3050', '#7a5080'], garden: ['#2a5038', '#4f8448', '#a4c86a'],
  };
  // Fine ground texture. Solid props (trees, rocks, pillars, crystals) are
  // drawn by render.js from the authoritative obstacle list so that what you
  // see is exactly what blocks movement.
  const leafCol = r.id === 'glacier' ? '#d8f2f5' : r.id === 'ruins' ? '#b8a06a' : r.id === 'rift' || r.id === 'abyss' ? '#b98ad8' : r.id === 'obsidian' ? '#c88ad8' : r.id === 'garden' ? '#cfe89a' : '#b4d17a';
  for (let i = 0; i < 420; i++) {
    const x = 40 + rnd() * 1920, y = 40 + rnd() * 1420;
    if (Math.abs(y - 820) < 52 || (x < 780 && y > 520 && y < 1080)) continue;
    const v = rnd();
    c.globalAlpha = .18 + v * .28;
    if (v > .82) {
      // grass tuft
      c.strokeStyle = r.light; c.lineWidth = 1.4;
      for (let j = -1; j <= 1; j++) { c.beginPath(); c.moveTo(x, y); c.lineTo(x + j * 3, y - 5 - Math.abs(j)); c.stroke(); }
    } else if (v > .7) {
      // fallen leaf / petal
      px(c, x, y, 3, 2, leafCol);
    } else if (v > .6) {
      // pebble
      px(c, x, y, 3, 2, r.dark);
    }
    c.globalAlpha = 1;
  }
  // Subtle patches of lighter moss and darker soil.
  for (let i = 0; i < 40; i++) {
    const x = rnd() * r.width, y = rnd() * r.height;
    c.globalAlpha = .07 + rnd() * .06;
    ellipse(c, x, y, 40 + rnd() * 90, 20 + rnd() * 40, rnd() > .5 ? r.light : r.dark);
    c.globalAlpha = 1;
  }
  // Hub buildings and NPC stations.
  drawStall(c, 615, 705, '#b86d4a');
  if (r.npcs[2].role === 'forge') { px(c, 555, 940, 70, 26, '#4a4038'); px(c, 565, 930, 50, 12, '#8a9298'); px(c, 580, 920, 20, 12, '#b8c0c8'); px(c, 640, 930, 24, 30, '#6a3a2a'); px(c, 646, 936, 12, 10, '#ff9a4a'); }
  else { ellipse(c, 590, 955, 40, 16, '#3a3a5a'); crystal(c, 590, 935, 22, r.accent); px(c, 550, 950, 12, 18, '#5a4a6a'); px(c, 620, 950, 12, 18, '#5a4a6a'); }
  px(c, 320, 610, 60, 40, '#6a4e32'); px(c, 325, 615, 50, 30, '#d8c8a0'); px(c, 345, 650, 8, 24, '#4a3624');
  if (r.id === 'camp') { drawTent(c, 240, 520, '#7a8a5a'); drawTent(c, 700, 470, '#8a6a4a'); drawStall(c, 800, 650, '#5a7a9a'); }
  drawLandmark(c, r);
  // Map border: dense trees / cliffs.
  c.strokeStyle = r.dark; c.lineWidth = 24; c.strokeRect(0, 0, r.width, r.height);
  return cv;
}
function getTerrain(r) {
  if (!r) return null;
  const key = r.id + ':' + r.seed;
  if (terrainCache.getOrCreate) return terrainCache.getOrCreate(key, () => buildTerrain(r));
  if (!terrainCache.has(key)) terrainCache.set(key, buildTerrain(r));
  return terrainCache.get(key);
}

function drawRegionWorld(c, ox, oy, w, h, now) {
  const r = snap?.region;
  c.fillStyle = '#101812'; c.fillRect(0, 0, w, h);
  if (!r) return;
  const terrain = getTerrain(r); if (terrain) c.drawImage(terrain, ox, oy);
  // Power site glow.
  for (const site of snap.power_sites || []) {
    const x = site.x + ox, y = site.y + oy, pulse = .5 + .5 * Math.sin(now / 500);
    c.save(); c.globalAlpha = .1 + .06 * pulse; ellipse(c, x, y, site.radius, site.radius * .6, r.accent); c.globalAlpha = .7; c.strokeStyle = r.accent; c.lineWidth = 2; c.beginPath(); c.ellipse(x, y, 34 + pulse * 6, 18 + pulse * 3, 0, 0, Math.PI * 2); c.stroke(); c.restore();
  }
  // Waystones.
  for (const portal of snap.portals || []) {
    const x = portal.x + ox, y = portal.y + oy; if (x < -120 || x > w + 120 || y < -120 || y > h + 120) continue;
    const target = snap.regions.find(z => z.id === portal.target), pulse = .5 + .5 * Math.sin(now / 350);
    c.save(); c.globalAlpha = .5 + .3 * pulse; const g = c.createRadialGradient(x, y - 10, 2, x, y - 10, 34); g.addColorStop(0, '#d8c8ff'); g.addColorStop(.5, '#8a6ad0aa'); g.addColorStop(1, '#8a6ad000'); c.fillStyle = g; c.fillRect(x - 34, y - 44, 68, 68); c.restore();
    c.fillStyle = '#e8e0ff'; c.font = 'bold 10px system-ui'; c.textAlign = 'center'; c.fillText(`◆ ${target?.name || ''}`, x, y - 62); c.fillStyle = '#c8b8e8'; c.font = '9px system-ui'; c.fillText(target?.level || '', x, y - 50); c.textAlign = 'left';
  }
  // NPCs.
  const p = me();
  for (const n of r.npcs || []) {
    const x = n.x + ox, y = n.y + oy; if (x < -100 || x > w + 100 || y < -100 || y > h + 100) continue;
    const near = p && npcDistance(n) <= 125;
    c.save(); if (near) { c.globalAlpha = .25; ellipse(c, x, y + 14, 26, 10, n.color); c.globalAlpha = 1; }
    drawAvatarSprite(c, { face_x: 0, face_y: 1, weapon: n.role === 'wizard' ? 'apprentice_staff' : 'sword', class: n.role === 'wizard' ? 'mage' : n.role === 'ranger' ? 'ranger' : null }, x, y, n.color, '#e8d8a8', false, 'traveler');
    c.restore();
    const icon = n.role === 'merchant' ? '⚖' : n.role === 'wizard' ? '✦' : n.role === 'forge' ? '⚒' : '❖';
    c.fillStyle = n.color; c.font = 'bold 13px system-ui'; c.textAlign = 'center'; c.fillText(icon, x, y - 34);
    c.font = 'bold 10px system-ui'; c.fillStyle = '#f4ecd8'; c.strokeStyle = '#101812'; c.lineWidth = 3; c.strokeText(n.name, x, y - 46); c.fillText(n.name, x, y - 46);
    if (near) { c.font = '9px system-ui'; c.fillStyle = n.color; c.fillText(`${actionKeyLabel('interact')} · ${n.title}`, x, y + 34); }
    c.textAlign = 'left';
  }
  // Weather / ambient motes.
  const rnd = rngFor(r.seed + 7); c.save();
  for (let i = 0; i < 42; i++) {
    const sx = rnd() * r.width, sy = rnd() * r.height, speed = 12 + rnd() * 24;
    let x = (sx + now / 1000 * speed * (r.weather === 'snow' ? .3 : 1)) % r.width;
    let y = (sy + now / 1000 * speed * (r.weather === 'embers' || r.weather === 'fireflies' ? -.6 : .5) + r.height) % r.height;
    const alpha = .2 + .3 * (.5 + .5 * Math.sin(now / 400 + i)); c.globalAlpha = alpha; c.fillStyle = r.accent;
    if (r.weather === 'snow' || r.weather === 'petals' || r.weather === 'leaves') px(c, x + ox, y + oy, 3, 3, r.accent);
    else { c.beginPath(); c.arc(x + ox, y + oy, 1.5 + rnd(), 0, Math.PI * 2); c.fill(); }
  }
  c.restore();
  // Waypoint marker.
  if (waypoint) {
    const x = waypoint.x + ox, y = waypoint.y + oy;
    if (x > 0 && x < w && y > 0 && y < h) { c.save(); c.strokeStyle = '#ffe08c'; c.lineWidth = 2; c.setLineDash([5, 5]); c.beginPath(); c.arc(x, y, 22 + 4 * Math.sin(now / 250), 0, Math.PI * 2); c.stroke(); c.setLineDash([]); c.fillStyle = '#ffe08c'; c.font = 'bold 10px system-ui'; c.textAlign = 'center'; c.fillText(waypoint.name, x, y - 32); c.restore(); }
  }
}

/* ---------- extra late-game mob silhouettes ---------- */
const baseDrawMobSprite = drawMobSprite;
drawMobSprite = function (c, m, x, y, s, now, color) {
  if (!['void_wraith', 'astral_titan', 'obsidian_sentinel', 'starseer', 'ancient_warden'].includes(m.kind)) return baseDrawMobSprite(c, m, x, y, s, now, color);
  c.save(); c.translate(x, y); const u = s / 20; c.scale(u, u);
  ellipse(c, 0, 15, 17, 5, '#00000055');
  if (m.kind === 'void_wraith' || m.kind === 'starseer') {
    const col = m.kind === 'void_wraith' ? '#7b2cbf' : '#d9a6ef';
    c.globalAlpha = .85; poly(c, [[-12, 14], [-10, -8], [-5, -16], [5, -16], [10, -8], [12, 14], [6, 10], [0, 16], [-6, 10]], col, '#2a1a3a');
    c.globalAlpha = 1; ellipse(c, 0, -8, 7, 8, '#1a1028'); px(c, -4, -10, 3, 2, '#e8d0ff'); px(c, 2, -10, 3, 2, '#e8d0ff');
    if (m.kind === 'starseer') { c.strokeStyle = '#f0d8ff'; c.lineWidth = 1.5; c.beginPath(); c.arc(0, -18, 8, Math.PI, 0); c.stroke(); crystal(c, 14, -4, 8, '#d9a6ef'); }
  } else {
    const col = m.kind === 'astral_titan' ? '#4a7a9a' : m.kind === 'obsidian_sentinel' ? '#5a4a6a' : '#5a7a4a';
    poly(c, [[-14, 12], [-12, -10], [-7, -18], [7, -18], [12, -10], [14, 12], [8, 16], [-8, 16]], col, '#1a2028');
    px(c, -10, -8, 20, 4, '#ffffff22'); ellipse(c, 0, -10, 8, 7, '#2a3040'); px(c, -5, -12, 3, 2, m.kind === 'ancient_warden' ? '#d4ff9a' : '#9ae8ff'); px(c, 2, -12, 3, 2, m.kind === 'ancient_warden' ? '#d4ff9a' : '#9ae8ff');
    px(c, -16, -6, 5, 16, col); px(c, 11, -6, 5, 16, col); px(c, -9, 14, 6, 8, '#2a2a30'); px(c, 3, 14, 6, 8, '#2a2a30');
    if (m.kind === 'ancient_warden') { pixelTree(c, 0, -22, 12, ['#2a5038', '#4f8448', '#a4c86a'], .5); }
    if (m.kind === 'astral_titan') { c.strokeStyle = '#9ae8ff'; c.lineWidth = 1.5; c.beginPath(); c.arc(0, 0, 24, 0, Math.PI * 2); c.stroke(); }
  }
  c.restore();
};

/* ---------- HUD / atlas / NPC dialogs ---------- */
function injectWorldUI() {
  const game = document.querySelector('.game');
  const ribbon = document.createElement('div'); ribbon.id = 'regionRibbon'; ribbon.className = 'regionRibbon panel';
  ribbon.innerHTML = `<div class="regionChapter" id="regionChapter">I</div><div class="regionText"><b id="regionName">Лагерь Следопытов</b><small id="regionSub">Тихая гавань</small></div><div class="regionMeta"><span id="regionDanger">Безопасно</span><span id="regionOnline">1 в карте</span></div>`;
  game.append(ribbon);
  const tools = document.createElement('div'); tools.id = 'worldTools'; tools.className = 'worldTools';
  tools.innerHTML = `<button type="button" id="charToolButton" class="worldTool worldShortcut">✦ Герой <kbd>C</kbd><span id="charToolBadge" class="toolPointBadge" hidden></span></button><button type="button" id="atlasButton" class="worldTool worldShortcut">◈ Атлас <kbd>M</kbd></button><button type="button" id="recallButton" class="worldTool">⌂ В лагерь</button>`;
  game.append(tools);
  const prompt = document.createElement('button'); prompt.type = 'button'; prompt.id = 'npcPrompt'; prompt.className = 'npcPrompt panel'; prompt.hidden = true; game.append(prompt);
  const local = document.createElement('div'); local.id = 'localQuestChip'; local.className = 'localQuestChip'; local.hidden = true; game.append(local);
  const travel = document.createElement('div'); travel.id = 'travelBanner'; travel.className = 'travelBanner'; travel.hidden = true; travel.innerHTML = `<small id="travelEyebrow">НОВАЯ ЗЕМЛЯ</small><b id="travelName"></b><span id="travelShort"></span>`; game.append(travel);
  const atlas = document.createElement('div'); atlas.id = 'atlasOverlay'; atlas.className = 'atlasOverlay'; atlas.setAttribute('role', 'dialog'); atlas.setAttribute('aria-modal', 'true'); atlas.setAttribute('aria-label', 'Атлас девяти земель');
  atlas.innerHTML = `<section class="atlasCard panel"><header class="atlasHead"><div><span class="eyebrow">ДЕВЯТЬ ЗЕМЕЛЬ · ОДИН МИР</span><h2>Атлас Леса Эхо</h2></div><div class="atlasProgress" id="atlasProgress">1 / 9 открыто</div><button type="button" class="close" id="closeAtlas">Закрыть · Esc</button></header><div class="atlasBody"><div class="atlasGrid" id="atlasGrid"></div><aside class="atlasDetail" id="atlasDetail"></aside></div><footer class="atlasFoot">Переходы — через дорожные камни на краях карт. Возвращение в лагерь доступно вне боя.</footer></section>`;
  game.append(atlas);
  const npc = document.createElement('div'); npc.id = 'npcOverlay'; npc.className = 'npcOverlay'; npc.setAttribute('role', 'dialog'); npc.setAttribute('aria-modal', 'true'); npc.setAttribute('aria-label', 'Разговор с жителем');
  npc.innerHTML = `<section class="npcCard panel"><button type="button" class="close npcClose" id="closeNpc">✕</button><div class="npcHead"><canvas id="npcPortrait" width="96" height="96"></canvas><div><span class="eyebrow" id="npcTitle"></span><h2 id="npcName"></h2><span class="npcRegion" id="npcRegion"></span></div></div><p class="npcDialogue" id="npcDialogue"></p><div id="npcContent"></div><div class="npcActions" id="npcActions"></div></section>`;
  game.append(npc);
  const shopTools = document.createElement('div'); shopTools.className = 'shopTools';
  shopTools.innerHTML = `<input id="shopSearch" type="search" placeholder="Поиск по лавке…" aria-label="Поиск товара"><div class="shopFilters" id="shopFilters"><button type="button" data-shop-kind="all" class="active">Всё</button><button type="button" data-shop-kind="weapon">Оружие</button><button type="button" data-shop-kind="gear">Броня</button><button type="button" data-shop-kind="accessory">Реликвии</button><button type="button" data-shop-kind="consumable">Расходники</button><button type="button" data-shop-kind="material">Материалы</button></div>`;
  const marketHead = document.querySelector('#marketOverlay .marketHead'); marketHead.insertAdjacentElement('afterend', shopTools);
  const marketSub = document.createElement('div'); marketSub.id = 'marketNpcName'; marketSub.className = 'marketNpcName'; marketHead.querySelector('h2').insertAdjacentElement('afterend', marketSub);
  $('charToolButton').onclick = () => { if (typeof toggleCharacter === 'function') toggleCharacter(); };
  $('atlasButton').onclick = () => openAtlas();
  $('mapButton').onclick = () => toggleMap(); if ($('mMapButton')) $('mMapButton').onclick = () => toggleMap();
  $('closeAtlas').onclick = closeAtlas;
  atlas.addEventListener('click', e => { if (e.target === atlas) closeAtlas(); const card = e.target.closest('[data-atlas-region]'); if (card) { atlasSelection = card.dataset.atlasRegion; renderAtlas(); } });
  $('recallButton').onclick = () => send({ type: 'recall' });
  prompt.onclick = () => send({ type: 'interact' });
  $('closeNpc').onclick = closeNpc;
  npc.addEventListener('click', e => { if (e.target === npc) closeNpc(); });
  $('shopSearch').addEventListener('input', e => { shopFilter.text = e.target.value.toLowerCase(); applyShopFilter(); });
  $('shopFilters').addEventListener('click', e => { const b = e.target.closest('[data-shop-kind]'); if (!b) return; shopFilter.kind = b.dataset.shopKind; document.querySelectorAll('[data-shop-kind]').forEach(x => x.classList.toggle('active', x === b)); applyShopFilter(); });
}
function openAtlas(selected) {
  if (!snap?.region) return;
  atlasSelection = selected || snap.region.id; atlasRenderSignature = '';
  renderAtlas(); $('atlasOverlay').style.display = 'flex'; $('closeAtlas').focus();
}
function closeAtlas() { $('atlasOverlay').style.display = 'none'; }
function renderAtlas() {
  const p = me(); if (!p) return;
  const freeTravel = !!p.world_travel_unlocked;
  const portal0 = (snap.portals || []).find(v => v.target === atlasSelection);
  const sig = JSON.stringify([atlasSelection, p.region, p.level, p.visited_regions, p.in_combat, freeTravel, portal0 ? Math.hypot(p.x - portal0.x, p.y - portal0.y) <= 145 : null]);
  if (sig === atlasRenderSignature) return; atlasRenderSignature = sig;
  const visited = new Set(p.visited_regions || []), grid = $('atlasGrid');
  $('atlasProgress').textContent = freeTravel ? `✦ 9 / 9 · Межмировой переход открыт` : `${visited.size} / ${snap.regions.length} открыто`;
  const foot = document.querySelector('#atlasOverlay .atlasFoot');
  if (foot) foot.textContent = freeTravel
    ? '✦ Победа над Хранителем Первозданного сада открыла свободное перемещение между всеми мирами вне боя!'
    : 'Переходы — через дорожные камни на краях карт. Победи Хранителя Первозданного сада, чтобы свободно перемещаться между всеми мирами!';
  grid.innerHTML = snap.regions.map(r => {
    const status = r.id === p.region ? 'current' : (freeTravel || visited.has(r.id)) ? 'visited' : p.level >= r.min_level ? 'open' : 'locked';
    const label = status === 'current' ? 'Ты здесь' : freeTravel ? '✦ Свободный вход' : status === 'visited' ? 'Открыто' : status === 'open' ? 'Доступно' : `Ур. ${r.min_level}`;
    return `<button type="button" class="atlasTile ${status} ${r.id === atlasSelection ? 'selected' : ''}" data-atlas-region="${r.id}" style="--region-accent:${r.accent}"><span class="atlasChapter">${r.chapter}</span><b>${esc(r.name)}</b><small>${esc(r.level)}</small><span class="atlasStatus">${label}</span><span class="atlasShop">⚖ ${esc(r.shop)}</span></button>`;
  }).join('');
  const r = snap.regions.find(z => z.id === atlasSelection) || snap.region;
  const portal = (snap.portals || []).find(v => v.target === r.id);
  const near = portal && Math.hypot(p.x - portal.x, p.y - portal.y) <= 145;
  const levelOk = p.level >= r.min_level;
  let travelHtml = '';
  if (r.id === p.region) travelHtml = `<div class="atlasHere">◆ Ты находишься на этой карте</div>`;
  else if (freeTravel) {
    const disabled = !!p.in_combat;
    const label = p.in_combat ? 'Межмировой переход недоступен в бою' : `✦ Переместиться в «${esc(r.name)}»`;
    travelHtml = `<button type="button" class="primary worldTravelBtn" id="atlasWorldTravel" ${disabled ? 'disabled' : ''}>${label}</button>`;
  } else if (portal) {
    const disabled = !near || !levelOk || p.in_combat;
    const reason = !levelOk ? `Нужен уровень ${r.min_level}` : p.in_combat ? 'Нельзя перейти в бою' : !near ? 'Подойди к дорожному камню' : 'Перейти на карту';
    travelHtml = `<button type="button" class="primary" id="atlasTravel" ${disabled ? 'disabled' : ''}>${reason}</button>${!near && levelOk ? `<button type="button" class="atlasWaypoint" id="atlasWaypoint">Отметить дорожный камень</button>` : ''}`;
  } else {
    const next = snap.regions.find(z => z.id === r.neighbors?.[0]) || snap.regions.find(z => z.neighbors?.includes(r.id));
    travelHtml = `<div class="atlasRoute">Прямой дороги нет. Путь идёт через соседние земли${next ? `: начни с «${esc(next.name)}»` : ''}.</div>`;
  }
  const npcs = (r.npcs || []).map(n => `<li><span>${n.role === 'merchant' ? '⚖' : n.role === 'wizard' ? '✦' : n.role === 'forge' ? '⚒' : '❖'}</span><div><b>${esc(n.name)}</b><small>${esc(n.title)}</small></div></li>`).join('');
  $('atlasDetail').innerHTML = `<div class="atlasDetailHero" style="--region-accent:${r.accent}"><span class="eyebrow">ЗЕМЛЯ ${r.chapter}</span><h3>${esc(r.name)}</h3><p>${esc(r.short)}</p></div><p class="atlasDesc">${esc(r.description)}</p><div class="atlasSection"><h4>Местные жители</h4><ul class="atlasNpcs">${npcs || `<li><span>⚖</span><div><b>${esc(r.merchant)}</b><small>${esc(r.shop)}</small></div></li>`}</ul></div><div class="atlasSection"><h4>Лавка</h4><p>${esc(r.stock_note)}</p></div><div class="atlasTravel">${travelHtml}</div>`;
  const wtb = $('atlasWorldTravel'); if (wtb) wtb.onclick = () => { send({ type: 'world_travel', region: r.id }); closeAtlas(); };
  const tb = $('atlasTravel'); if (tb) tb.onclick = () => { if (portal) send({ type: 'travel', portal_id: portal.id }); };
  const wb = $('atlasWaypoint'); if (wb) wb.onclick = () => { waypoint = { x: portal.x, y: portal.y, name: 'Дорожный камень' }; closeAtlas(); toast('Дорожный камень отмечен на карте.'); };
}
function drawNpcPortrait(n) {
  const cv = $('npcPortrait'), c = cv.getContext('2d'); c.clearRect(0, 0, 96, 96);
  const g = c.createRadialGradient(48, 40, 5, 48, 48, 60); g.addColorStop(0, n.color + '55'); g.addColorStop(1, '#141c16'); c.fillStyle = g; c.fillRect(0, 0, 96, 96);
  c.save(); c.translate(48, 62); c.scale(2.2, 2.2);
  drawAvatarSprite(c, { face_x: 0, face_y: 1, weapon: n.role === 'wizard' ? 'apprentice_staff' : 'sword', class: n.role === 'wizard' ? 'mage' : n.role === 'ranger' ? 'ranger' : null }, 0, 0, n.color, '#e8d8a8', false, 'traveler');
  c.restore();
}
function questProgressHtml(q, p) {
  const rows = [];
  const add = (kind, need, got, isKill) => { if (!need) return; const name = isKill ? (mobNames[kind] || kind) : (resourceNames[kind] || kind); const done = Math.min(got || 0, need); rows.push(`<div class="questRow ${done >= need ? 'done' : ''}"><span>${esc(name)}</span><b>${done} / ${need}</b><i style="width:${Math.min(100, done / need * 100)}%"></i></div>`); };
  add(q.resource, q.count, q.gather?.[q.resource], false);
  if (q.resource2 && q.count2 > 0) add(q.resource2, q.count2, q.gather?.[q.resource2], false);
  if (q.mob) add(q.mob, q.mob_count, q.kills?.[q.mob], true);
  return rows.join('');
}
function localQuestReady(q, p) {
  if (!q || q.done || !q.active) return false;
  const gatherOk = (q.gather?.[q.resource] || 0) >= q.count && (!q.resource2 || q.count2 <= 0 || (q.gather?.[q.resource2] || 0) >= q.count2);
  const killOk = !q.mob || (q.kills?.[q.mob] || 0) >= q.mob_count;
  const invOk = (p.inventory?.[q.resource] || 0) >= q.count && (!q.resource2 || q.count2 <= 0 || (p.inventory?.[q.resource2] || 0) >= q.count2);
  return gatherOk && killOk && invOk;
}
function renderNpcDialog() {
  const p = me(), n = activeNpc; if (!p || !n) return;
  const sig = JSON.stringify([n.id, p.region, p.quest, p.region_quest, p.herald_story, n.herald_story, p.inventory, p.gold]);
  if (sig === npcRenderSignature) return; npcRenderSignature = sig;
  $('npcTitle').textContent = n.title; $('npcName').textContent = n.name; $('npcRegion').textContent = snap.region.name; $('npcDialogue').textContent = n.dialogue;
  drawNpcPortrait(n);
  const content = $('npcContent'), actions = $('npcActions'); content.innerHTML = ''; actions.innerHTML = '';
  if (n.services.includes('shop')) {
    content.innerHTML = `<div class="npcShopPreview"><h3>${esc(n.title)}</h3><p>${esc(snap.region.stock_note)}</p><div class="npcStock">${Object.values(p.shop_catalog || {}).slice(0, 6).map(o => `<span>${esc(o.name)}<b>${o.price} ◉</b></span>`).join('')}</div></div>`;
    actions.innerHTML = `<button type="button" class="primary" id="npcOpenShop">Открыть лавку</button>`;
    $('npcOpenShop').onclick = () => { closeNpc(); openMarket(n); };
  }
  if (n.services.includes('forge') || n.services.includes('wizard')) {
    if (n.services.includes('forge')) actions.insertAdjacentHTML('beforeend', `<button type="button" class="primary" id="npcOpenForge">⚒ Кузница</button>`);
    if (n.services.includes('wizard')) actions.insertAdjacentHTML('beforeend', `<button type="button" class="primary" id="npcOpenWizard">✦ Мастер чар</button>`);
    if ($('npcOpenForge')) $('npcOpenForge').onclick = () => { closeNpc(); openForge(n); };
    if ($('npcOpenWizard')) $('npcOpenWizard').onclick = () => { closeNpc(); openWizard(n); };
  }
  if (n.services.includes('quest')) {
    if (p.region === 'camp') {
      const q = p.quest, done = q.active && questDone(q), finished = q.stage >= q.total;
      content.insertAdjacentHTML('beforeend', `<div class="npcQuest"><h3>Путь следопыта · ${Math.min(q.stage + 1, q.total)} / ${q.total}</h3><p>${finished ? 'История Леса Эха завершена.' : esc(questStages[Math.min(q.stage, questStages.length - 1)][4])}</p>${!finished ? `<div class="questRow"><span>${esc(mobNames[questStages[Math.min(q.stage, questStages.length - 1)][0]] || '')}</span><b>${Math.min(q.kills?.[questStages[Math.min(q.stage, questStages.length - 1)][0]] || 0, questStages[Math.min(q.stage, questStages.length - 1)][1])} / ${questStages[Math.min(q.stage, questStages.length - 1)][1]}</b></div>` : ''}<div class="npcQuestButtons">${!q.active && !finished ? `<button type="button" data-story-quest="accept">Принять поручение</button>` : ''}${done ? `<button type="button" data-story-quest="claim" class="ready">Сдать поручение</button>` : ''}</div></div>`);
      const hs = n.herald_story || p.herald_story;
      if (hs) {
        const current = (hs.chapters || []).find(ch => ch.status !== 'done' && ch.status !== 'hidden');
        const contentText = hs.complete ? 'Три печати отозвались. Имя, спрятанное в их памяти, ведёт глубже — к истоку Эха.'
          : current?.description || 'Три вестника оставили печати в землях Леса Эха.';
        const action = current?.status === 'available'
          ? `<button type="button" data-herald-quest="accept">Принять охоту</button>`
          : current?.status === 'ready'
            ? `<button type="button" data-herald-quest="claim" class="ready">Сдать печать</button>` : '';
        const progress = current && current.status !== 'available'
          ? `<div class="questRow"><span>${esc(mobNames[current.mob] || current.mob)}</span><b>${current.status === 'ready' ? 1 : Math.min(1, Number(hs.kills || 0))} / 1</b></div>` : '';
        content.insertAdjacentHTML('beforeend', `<div class="npcQuest heraldQuest"><h3>Зов трёх вестников · ${Math.min(hs.stage + 1, hs.total)} / ${hs.total}</h3><p>${esc(contentText)}</p>${progress}<div class="questReward">Победы дают Печать вестника для высшей перековки. Завершение главы открывает магам заклинание «Сеть эха».</div><div class="npcQuestButtons">${action}</div></div>`);
      }
    }
    const q = p.region_quest;
    if (q) {
      const ready = localQuestReady(q, p);
      content.insertAdjacentHTML('beforeend', `<div class="npcQuest"><h3>${esc(q.title)} ${q.done ? '· выполнено' : ''}</h3><p>${esc(q.description)}</p>${questProgressHtml(q, p)}<div class="questReward">Награда: ${q.gold} ◉ · ${q.xp} XP · 2 настойки · 1 очко развития</div><div class="npcQuestButtons">${!q.active && !q.done ? `<button type="button" data-region-quest="accept">Принять поручение</button>` : ''}${q.active && !q.done ? `<button type="button" data-region-quest="claim" class="${ready ? 'ready' : ''}" ${ready ? '' : 'disabled'}>Сдать поручение</button>` : ''}</div></div>`);
    }
    content.querySelectorAll('[data-story-quest]').forEach(b => b.onclick = () => send({ type: 'npc_quest', npc_id: n.id, action: b.dataset.storyQuest, quest_kind: 'story' }));
    content.querySelectorAll('[data-herald-quest]').forEach(b => b.onclick = () => send({ type: 'npc_quest', npc_id: n.id, action: b.dataset.heraldQuest, quest_kind: 'herald_story' }));
    content.querySelectorAll('[data-region-quest]').forEach(b => b.onclick = () => send({ type: 'npc_quest', npc_id: n.id, action: b.dataset.regionQuest, quest_kind: 'region' }));
  }
}
function openNpc(n, quest, heraldStory) { activeNpc = { ...n, ...(heraldStory ? { herald_story: heraldStory } : {}) }; npcRenderSignature = ''; renderNpcDialog(); $('npcOverlay').style.display = 'flex'; $('closeNpc').focus(); }
function closeNpc() { $('npcOverlay').style.display = 'none'; activeNpc = null; npcRenderSignature = ''; }
function openPortal(portal) { const target = snap?.regions.find(r => r.id === portal.target); openAtlas(target?.id); }

/* ---------- local shops and stations ---------- */
const baseOpenMarket = openMarket, baseOpenWizard = openWizard, baseOpenForge = openForge;
openMarket = function (npc) {
  const n = npc || nearestService('shop'); if (!n) { toast('Подойди к местному торговцу — его метка ⚖ есть на карте.'); return; }
  stationNpc.marketOverlay = n.id; baseOpenMarket();
  document.querySelector('#marketOverlay h2').textContent = n.title; $('marketNpcName').textContent = `${n.name} · ${snap.region.name}`;
  shopFilter = { text: '', kind: 'all' }; $('shopSearch').value = ''; document.querySelectorAll('[data-shop-kind]').forEach(x => x.classList.toggle('active', x.dataset.shopKind === 'all')); applyShopFilter();
};
openWizard = function (npc) {
  const n = npc || nearestService('wizard'); if (!n) { toast('Подойди к местному мастеру чар — метка ✦.'); return; }
  stationNpc.wizardOverlay = n.id; baseOpenWizard();
  document.querySelector('#wizardOverlay h2').textContent = n.title; document.querySelector('#wizardOverlay .marketHead small').textContent = `${n.name} · ${snap.region.name}`;
};
openForge = function (npc) {
  const n = npc || nearestService('forge'); if (!n) { toast('Подойди к кузнецу этой карты — метка ⚒.'); return; }
  stationNpc.forgeOverlay = n.id; baseOpenForge();
  document.querySelector('#forgeOverlay h2').textContent = n.title; document.querySelector('#forgeOverlay .marketHead small').textContent = `${n.name} · ${snap.region.name}`;
};
const baseSend = send;
send = function (data) {
  const map = { shop_action: 'marketOverlay', forge_action: 'forgeOverlay', wizard_action: 'wizardOverlay' };
  const overlay = map[data.type];
  if (overlay && stationNpc[overlay]) data = { ...data, npc_id: stationNpc[overlay] };
  baseSend(data);
};
const baseRenderMarket = renderMarket;
renderMarket = function (p) { baseRenderMarket(p); enhanceMarket(p); };
function enhanceMarket(p) {
  const catalog = p.shop_catalog || {}, grid = $('marketBuyGrid'); if (!grid) return;
  grid.querySelectorAll('.marketLine').forEach(row => {
    const btn = row.querySelector('[data-market-buy]'); if (!btn) return;
    const id = btn.dataset.marketBuy, o = catalog[id]; if (!o) return;
    const offerKind = String(o.kind || '');
    const kind = typeof marketOfferKind === 'function' ? marketOfferKind(o)
      : offerKind === 'weapon' || offerKind === 'gear' || offerKind === 'accessory' ? offerKind
        : (offerKind === 'crystal' || offerKind === 'shard' || offerKind === 'rune_dust'
          || offerKind === 'essence' || offerKind === 'mithril') ? 'material' : 'consumable';
    row.dataset.shopKind = kind; row.dataset.shopName = o.name.toLowerCase();
    const glyphMap = { weapon: '⚔', gear: '◆', accessory: '💍', consumable: '✚', material: '⛏', supply: '✚' };
    const glyph = offerKind === 'weapon'
      ? (o.name.toLowerCase().includes('лук') ? '➶' : o.name.toLowerCase().includes('посох') ? '✦' : '⚔')
      : glyphMap[kind] || '✚';
    const icon = row.querySelector('.shopIcon');
    if (!icon) { const span = document.createElement('span'); span.className = 'shopIcon'; span.textContent = glyph; row.prepend(span); }
    else icon.textContent = glyph;
    const acc = p.accessory_catalog?.[id];
    if (acc) {
      row.dataset.shopRarity = acc.rarity || 'common';
      let line = row.querySelector('small');
      if (line && !line.dataset.withAcc) { line.textContent = `Реликвия · ${acc.description} · ${o.price} монет`; line.dataset.withAcc = '1'; }
    }
    const owned = (o.kind === 'weapon' && p.weapons?.includes(id))
      || (o.kind === 'gear' && (p.gear === id || p.gear_inventory?.includes(id)))
      || (o.kind === 'accessory' && (p.accessories?.includes(id) || Object.values(p.equipped_accessories || {}).includes(id)));
    if (owned) { btn.disabled = true; btn.textContent = 'Есть'; }
  });
  applyShopFilter();
}
function applyShopFilter() {
  const grid = $('marketBuyGrid'); if (!grid) return;
  grid.querySelectorAll('.marketLine').forEach(row => {
    const okKind = shopFilter.kind === 'all' || row.dataset.shopKind === shopFilter.kind;
    const okText = !shopFilter.text || (row.dataset.shopName || '').includes(shopFilter.text);
    row.hidden = !(okKind && okText);
  });
}

/* ---------- sync / transitions ---------- */
function showTravelBanner(r, reason) {
  $('travelEyebrow').textContent = reason === 'respawn' ? 'ВОЗВРАЩЕНИЕ' : reason === 'recall' ? 'КАМЕНЬ ВОЗВРАЩЕНИЯ' : reason === 'world_travel' ? 'МЕЖМИРОВОЙ ПЕРЕХОД' : 'НОВАЯ ЗЕМЛЯ';
  $('travelName').textContent = r.name; $('travelShort').textContent = r.short;
  const el = $('travelBanner'); el.hidden = false; el.classList.remove('show'); void el.offsetWidth; el.classList.add('show');
  clearTimeout(el._timer); el._timer = setTimeout(() => { el.hidden = true; el.classList.remove('show'); }, 3200);
}
function resetMapViews() {
  entityViews.clear(); keys.clear(); touchDirs.clear(); if (typeof joyRelease === 'function') joyRelease();
  window.LesEchoView?.reset?.();
  window.EncounterView?.reset?.(currentRegionId);
  window.echoBestiaryView?.close();
  spellFx.length = 0; weaponActions.length = 0; attackFx.length = 0; if (typeof vfxParticles !== 'undefined') vfxParticles.length = 0; if (typeof abilityFx !== 'undefined') abilityFx.length = 0;
  for (const k of Object.keys(hitFlashes)) delete hitFlashes[k];
  waypoint = null; closeNpc(); closeAtlas();
  for (const id of ['marketOverlay', 'wizardOverlay', 'forgeOverlay']) { const el = $(id); if (el) el.style.display = 'none'; delete stationNpc[id]; }
  shopFilter = { text: '', kind: 'all' };
}
const WorldUI = {
  sync(p) {
    if (!p || !snap?.region) return;
    const r = snap.region;
    if (currentRegionId !== p.region) {
      const first = currentRegionId === null; currentRegionId = p.region; resetMapViews();
      cam.x = p.x; cam.y = p.y; if (!first) showTravelBanner(r, WorldUI.pendingReason || 'travel'); WorldUI.pendingReason = null;
      document.documentElement.style.setProperty('--region-accent', r.accent);
    }
    entityViews.retain(snap.players, snap.mobs);
    window.LesEchoView?.retain?.(snap.players, snap.mobs);
    $('regionChapter').textContent = r.chapter; $('regionName').textContent = r.name; $('regionSub').textContent = r.short;
    $('regionDanger').textContent = r.danger === 0 ? 'Безопасно' : p.in_combat ? 'В бою' : r.level;
    $('regionDanger').classList.toggle('combat', !!p.in_combat);
    $('regionOnline').textContent = `${snap.players.length} в карте`;
    $('miniMapLabel').textContent = r.name.toUpperCase();
    const recall = $('recallButton'); recall.hidden = p.region === 'camp' || !!p.in_combat; recall.disabled = !p.recall_ready; recall.title = p.in_combat ? 'Недоступно в бою' : 'Вернуться в лагерь · перезарядка 20 с';
    const q = p.region_quest, chip = $('localQuestChip');
    if (q && q.active && !q.done) { chip.hidden = false; chip.textContent = `❖ ${q.title}`; } else chip.hidden = true;
    // Context prompt.
    const npc = (r.npcs || []).filter(n => npcDistance(n) <= 125).sort((a, b) => npcDistance(a) - npcDistance(b))[0];
    const portal = (snap.portals || []).find(v => Math.hypot(p.x - v.x, p.y - v.y) <= 145);
    const node = (snap.nodes || []).find(n => n.active && Math.hypot(p.x - n.x, p.y - n.y) < 68);
    const mobileInteract = $('mInteractButton'); if (mobileInteract) { mobileInteract.hidden = !(npc || portal || node); mobileInteract.disabled = !(npc || portal || node); }
    const prompt = $('npcPrompt');
    const touchLayout = window.matchMedia('(max-width: 760px), (pointer: coarse)').matches;
    prompt.disabled = touchLayout && !!(npc || portal || node);
    if (npc) { prompt.hidden = false; prompt.innerHTML = `<kbd>${actionKeyLabel('interact')}</kbd><span><b>${esc(npc.name)}</b><small>${esc(npc.title)}</small></span>`; $('interactButton').innerHTML = `${actionKeyLabel('interact')} · ${esc(npc.role === 'merchant' ? 'ЛАВКА' : npc.role === 'forge' ? 'КУЗНЯ' : npc.role === 'wizard' ? 'МАГ' : 'ЖИТЕЛЬ')}`; if ($('mInteractButton')) $('mInteractButton').textContent = npc.role === 'merchant' ? 'ТОРГОВАТЬ' : npc.role === 'forge' ? 'КУЗНЯ' : npc.role === 'wizard' ? 'МАГ' : 'ЖИТЕЛЬ'; }
    else if (portal) { const target = snap.regions.find(z => z.id === portal.target); prompt.hidden = false; prompt.innerHTML = `<kbd>${actionKeyLabel('interact')}</kbd><span><b>Дорожный камень</b><small>${esc(target?.name || '')}</small></span>`; $('interactButton').textContent = `${actionKeyLabel('interact')} · ПЕРЕХОД`; if ($('mInteractButton')) $('mInteractButton').textContent = 'ПЕРЕХОД'; }
    else if (node) { prompt.hidden = false; prompt.innerHTML = `<kbd>${actionKeyLabel('gather')}</kbd><span><b>${esc(resourceNames[node.kind] || 'Ресурс')}</b><small>Собрать</small></span>`; $('interactButton').textContent = `${actionKeyLabel('gather')} · СБОР`; if ($('mInteractButton')) $('mInteractButton').textContent = 'СБОР'; }
    else { prompt.hidden = true; $('interactButton').textContent = `${actionKeyLabel('gather')} · РЕСУРС`; if ($('mInteractButton')) $('mInteractButton').textContent = 'СБОР'; }
    if (waypoint && Math.hypot(p.x - waypoint.x, p.y - waypoint.y) < 60) waypoint = null;
    if (activeNpc && npcDistance(activeNpc) > 140) closeNpc();
    if ($('npcOverlay').style.display === 'flex') renderNpcDialog();
    if ($('atlasOverlay').style.display === 'flex') renderAtlas();
  },
  openNpc, openPortal,
};
const baseUpdateHud = updateHud;
updateHud = function () { baseUpdateHud(); WorldUI.sync(me()); };
const baseToast = toast;
toast = function (t) { baseToast(t); const el = $('toast'); el.textContent = t; el.style.opacity = '1'; clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.style.opacity = '0'; }, 2600); };
// Click a nearby NPC / waystone instead of swinging at them.
canvas.addEventListener('pointerdown', e => {
  if (e.pointerType !== 'mouse' || e.button !== 0) return;
  const p = me(); if (!p) return;
  const rect = canvas.getBoundingClientRect(), sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const wp = (window.LesEchoView && typeof window.LesEchoView.screenToWorld === 'function')
    ? window.LesEchoView.screenToWorld(sx, sy)
    : { x: cam.x + (sx - rect.width / 2), y: cam.y + (sy - rect.height / 2) };
  const wx = wp.x, wy = wp.y;
  const npc = (snap?.region?.npcs || []).find(n => Math.hypot(n.x - wx, n.y - wy) < 34 && npcDistance(n) <= 125);
  const portal = (snap?.portals || []).find(v => Math.hypot(v.x - wx, v.y - wy) < 44 && Math.hypot(p.x - v.x, p.y - v.y) <= 145);
  if (npc || portal) { e.stopImmediatePropagation(); e.preventDefault(); send({ type: 'interact' }); }
}, true);
toggleMap = function () { if ($('atlasOverlay').style.display === 'flex') closeAtlas(); else openAtlas(); };
injectWorldUI();
