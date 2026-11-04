
const $=id=>document.getElementById(id), canvas=$('world'),ctx=canvas.getContext('2d'),mini=$('mini'),mctx=mini.getContext('2d'),full=$('fullmap'),fctx=full.getContext('2d');
const zoneInfo={camp:{name:'Лагерь Следопытов',level:'Безопасная зона',color:'#799457'},forest:{name:'Шепчущий лес',level:'Уровень 1–3',color:'#63834e'},marsh:{name:'Затонувшие топи',level:'Уровень 4–6',color:'#4d766c'},ruins:{name:'Пепельные руины',level:'Уровень 7–10',color:'#77614e'},glacier:{name:'Хребет Синего Пламени',level:'Уровень 11–14',color:'#73949c'},rift:{name:'Разлом Эха',level:'Уровень 15–19',color:'#584e76'},abyss:{name:'Астральная Бездна',level:'Уровень 20–25',color:'#352d51'},obsidian:{name:'Обсидиановый край',level:'Уровень 26–30',color:'#54435f'},garden:{name:'Первозданный сад',level:'Уровень 31–35',color:'#557a4a'}};
const weaponNames={sword:'Меч дозорного',axe:'Лесной колун',bow:'Тисовый лук',iron_sword:'Клинок из болотной стали',moonblade:'Лунный резец',ember_greatsword:'Клинок последнего зарева',starfall_bow:'Лук звёздного падения',forest_bow:'Лук следопыта',apprentice_staff:'Посох ученика',thorn_staff:'Посох живых терний',stormbrand:'Клинок Грозового кедра',obsidian_axe:'Топор Чёрного стекла',sunfall_bow:'Лук Солнцепада',elder_staff:'Посох Первозданного корня'},gearNames={traveler:'Куртка путника',wolf_cloak:'Плащ туманного волка',moss_guard:'Живой моховой панцирь',marsh_armor:'Болотная броня',moonweave:'Мантия лунного ткача',ash_plate:'Пепельный панцирь',colossus_core:'Сердце Колосса',glacier_mantle:'Мантия Синего Пламени',rift_plate:'Доспех Пустого Эха',obsidian_shell:'Панцирь чёрного стекла',starseer_robe:'Мантия звёздочёта',elder_mantle:'Плащ Первозданного сада'},gearDefense={traveler:2,wolf_cloak:5,moss_guard:6,marsh_armor:8,moonweave:9,ash_plate:12,colossus_core:18,glacier_mantle:21,rift_plate:27,obsidian_shell:30,starseer_robe:32,elder_mantle:36},rarityNames={common:'Обычный',uncommon:'Необычный',rare:'Редкий',epic:'Эпический',legendary:'Легендарный'},resourceNames={wood:'Древесина',herb:'Лунная трава',ore:'Болотная руда',crystal:'Эхо-кристалл',shard:'Осколок разлома',hide:'Шкура',slime:'Слизь',arrows:'Стрелы',potion:'Настойка'};
const spellNames={fireball:'Огненный шар',lightning:'Молния',heal:'Исцеление',thorns:'Колючие терни',ice_lance:'Ледяное копьё',arcane_burst:'Всплеск маны',meteor:'Метеоритный дождь',frost_nova:'Кольцо инея',shadow_bolt:'Сумрачный снаряд'};
// --- ENHANCED VFX & PARTICLES SYSTEM ---
let screenShake = 0, screenShakeDecay = 0.9;
let screenShakeX = 0, screenShakeY = 0;
function triggerScreenShake(amt, worldX, worldY){
  const p=me();
  if(!p || !Number.isFinite(worldX) || !Number.isFinite(worldY)) return;
  const dx=worldX-p.x, dy=worldY-p.y, distance=Math.hypot(dx,dy);
  const radius=720;
  if(distance>=radius) return;
  const falloff=1-distance/radius;
  const local=amt*falloff*falloff;
  screenShake=Math.max(screenShake,local);
}
/* ── sound / impact bus ─────────────────────────────────────────────────
   Every call is defensive: if audio.js or render.js failed to load, or the
   browser blocks WebAudio, the game keeps running silently.                */
function sfxCall(name){
  try{const a=window.LesEchoAudio;if(a&&typeof a[name]==='function'){const rest=[].slice.call(arguments,1);a[name].apply(a,rest)}}catch(e){}
}
function fxCall(name){
  try{const f=window.LesEchoFx;if(f&&typeof f[name]==='function'){const rest=[].slice.call(arguments,1);f[name].apply(f,rest)}}catch(e){}
}
window.echoSfx=sfxCall;
let vfxParticles = [];
function spawnParticles(x, y, color, count=12, speed=3, size=4, life=0.6){
  for(let i=0; i<count; i++){
    let ang = Math.random()*Math.PI*2;
    let spd = (0.3 + Math.random()*0.7) * speed;
    vfxParticles.push({
      x, y,
      vx: Math.cos(ang)*spd,
      vy: Math.sin(ang)*spd,
      color: color,
      size: size*(0.6+Math.random()*0.8),
      alpha: 1,
      decay: 1 / (life * 60)
    });
  }
}
function updateAndDrawParticles(ctx, ox, oy){
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  for(let i=vfxParticles.length-1; i>=0; i--){
    let p = vfxParticles[i];
    p.x += p.vx;
    p.y += p.vy;
    p.vx *= 0.95;
    p.vy *= 0.95;
    p.alpha -= p.decay;
    if(p.alpha <= 0){ vfxParticles.splice(i, 1); continue; }
    ctx.globalAlpha = p.alpha;
    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.arc(p.x + ox, p.y + oy, p.size * p.alpha, 0, Math.PI*2);
    ctx.fill();
  }
  ctx.restore();
}

let spellFx=[];
let weaponActions=[];
const mobNames={slime:'Моховой слизень',wolf:'Туманный волк',boar:'Топкий вепрь',wisp:'Болотный огонёк',stone:'Каменный дозорный',ashling:'Пепельный искатель',ashguard:'Страж руин',colossus:'Пепельный колосс',frost_wyrm:'Ледяной змей',rift_knight:'Рыцарь разлома',echo_dragon:'Дракон Пустого Эха',void_wraith:'Призрак Бездны',astral_titan:'Титан Астральной Бездны',obsidian_sentinel:'Страж чёрного стекла',starseer:'Звёздочёт Пустоты',ancient_warden:'Хранитель Первозданного сада'};
const nodeNames={wood:'Дерево',herb:'Лунная трава',ore:'Болотная руда',crystal:'Эхо-кристалл'};
let ws=null,myId=null,snap=null,keys=new Set(),touchDirs=new Set(),aim={x:1,y:0},hasPointerAim=false,chargeLocal=false,chargeStart=0,lastInput=0,runHeld=false,sneakHeld=false,toastTimer=0,cam={x:330,y:1100},hitFlashes={},attackFx=[],decor=[],deviceScale=1;
const hash=(x,y)=>{let n=Math.imul(x,374761393)^Math.imul(y,668265263);n=Math.imul(n^(n>>>13),1274126177);return ((n^(n>>>16))>>>0)/4294967295};
function resize(){let r=canvas.getBoundingClientRect();deviceScale=Math.min(2,devicePixelRatio||1);canvas.width=Math.max(1,Math.floor(r.width*deviceScale));canvas.height=Math.max(1,Math.floor(r.height*deviceScale));ctx.setTransform(deviceScale,0,0,deviceScale,0,0);mini.width=Math.max(1,Math.floor(mini.clientWidth*deviceScale));mini.height=Math.max(1,Math.floor(mini.clientHeight*deviceScale));mctx.setTransform(deviceScale,0,0,deviceScale,0,0);full.width=Math.max(1,Math.floor(full.clientWidth*deviceScale));full.height=Math.max(1,Math.floor(full.clientHeight*deviceScale));fctx.setTransform(deviceScale,0,0,deviceScale,0,0);}
addEventListener('resize',resize);resize();
function send(data){if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify(data))}
// The server owns the point pool: a click always sends {type:'upgrade'} and the
// authoritative answer arrives via stats_updated/player_update. Local copies of
// skill_points may lag behind, so they only dim the button — never block it.
const UPGRADE_CAPS={might:50,vitality:50,agility:50,mana_regen:20,magic_damage:20,insight:15,precision:13,fortune:9};
const LEVEL_STATS=['mana_regen','magic_damage','insight'];
let lastUpgradeSync=0;
function upgradeLevel(p,stat){const view=p?.upgrades_view||{},entry=view[stat];let raw=Number(entry?.level);if(!Number.isFinite(raw)){const src=(stat==='insight')?(p?.insight_level??0):(LEVEL_STATS.includes(stat)?(p?.[`${stat}_level`]??0):(p?.stats?.[stat]??1));raw=Number(src)}return Number.isFinite(raw)?Math.floor(raw):0}
function refreshUpgradeButton(button,p){const stat=button.dataset.stat;if(!stat)return;const own=p||me()||{};const points=Math.max(0,Number(own.skill_points)||0),lvl=upgradeLevel(own,stat),atCap=lvl>=UPGRADE_CAPS[stat],effect=own.upgrades_view?.[stat]?.effect;const pending=button.dataset.pending==='1';button.classList.toggle('dim',points<=0&&!pending);if(atCap){button.disabled=true;button.title='Достигнут предел этой характеристики'}else if(pending){button.disabled=false;button.title='Запрос отправлен, ждём ответ сервера…'}else{button.disabled=false;button.title=points>0?`Потратить 1 очко развития · осталось ${points}${effect?` · Сейчас: ${effect}`:''}`:`Сервер проверит очки · сейчас: ${points}${effect?` · ${effect}`:''}`}if(points>0&&!pending&&Date.now()-lastUpgradeSync>1000){lastUpgradeSync=Date.now();send({type:'sync'})}}
function requestStatUpgrade(button){const stat=button?.dataset.stat;if(!stat||button.disabled)return;const finish=()=>{delete button.dataset.pending;clearTimeout(button._upgradeTimer);refreshUpgradeButton(button,me());if(window.renderCharOverlay)try{renderCharOverlay(me())}catch(err){}};button.dataset.pending='1';button._upgradeTimer=setTimeout(finish,2500);send({type:'upgrade',stat})}
function renderStatsPanel(p){if(!p)return;const pointsNode=$('points');if(pointsNode){const raw=Number(p.skill_points);const points=Number.isFinite(raw)?Math.max(0,Math.floor(raw)):0;pointsNode.textContent=`Свободно: ${points}`;pointsNode.classList.toggle('hasPoints',points>0)}const view=p.upgrades_view||{},stats=p.stat_values||p.stats||{};const fallback={might:stats.might,vitality:stats.vitality,agility:stats.agility,mana_regen:p.mana_regen_level,magic_damage:p.magic_damage_level,insight:p.insight_level,precision:stats.precision,fortune:stats.fortune};for(const [key,id] of [['might','might'],['vitality','vitality'],['agility','agility'],['mana_regen','manaRegenLevel'],['magic_damage','magicDamageLevel'],['precision','precision'],['fortune','fortune']]){const node=$(id),entry=view[key];if(!node)continue;const raw=entry&&entry.level!==undefined?entry.level:fallback[key];const n=Number(raw);if(Number.isFinite(n)){const value=Math.max(['might','vitality','agility','precision','fortune'].includes(key)?1:0,Math.floor(n));node.textContent=String(value);if(entry?.effect)node.title=entry.effect}}document.querySelectorAll('.upgrade').forEach(button=>refreshUpgradeButton(button,p))}
function me(){return snap?.players.find(p=>p.id===myId)}
function message(text,type='notice',name=''){let box=$('messages'),row=document.createElement('div');row.className='msg '+type;if(type==='chat'){let b=document.createElement('b');b.textContent=name+': ';row.append(b,document.createTextNode(text))}else row.textContent=text;box.append(row);while(box.children.length>5)box.removeChild(box.firstChild);setTimeout(()=>row.remove(),14000)}function toast(t){message(t,'notice')}
const ABILITY_DEFAULT_KEYS={roar:'KeyR',lunge:'KeyT',whirlwind:'KeyK',iron_guard:'KeyP',bash:'KeyO',bloodhunt:'KeyN',seismic_slam:'KeyL',arrow_rain:'KeyR',piercing_shot:'KeyT',fire_arrow:'KeyK',ice_arrow:'KeyP',double_shot:'KeyX',poison_arrow:'KeyO',blackout_bolt:'KeyN',eagle_mark:'KeyL',arcane_bolt:'KeyR',frost_lance:'KeyT',chain_lightning:'KeyX',arcane_shield:'KeyN',blink:'KeyO',flame_burst:'KeyP',mana_surge:'KeyK',meteor_fall:'KeyL'};
const ABILITY_TREE_NAMES={warrior:'Воин',ranger:'Следопыт',mage:'Маг'};
const ABILITY_RESERVED=new Set(['KeyW','KeyA','KeyS','KeyD','KeyE','KeyF','KeyI','KeyM','KeyB','KeyG','KeyH', 'KeyJ','KeyQ','KeyC','KeyV','KeyZ']);
let abilityKeys={};
try{abilityKeys=JSON.parse(localStorage.getItem('echoAbilityKeys')||'{}')||{}}catch{abilityKeys={}}
let abilityKeyCodeToId={},pendingAbilityBinding='',classOfferDismissed=false,classChoicePending=false,abilityFx=[],hoverAbilityId='';

function classAbilityList(p,tree){
 return Object.values(p?.abilities||{}).filter(a=>a.tree===tree).sort((a,b)=>a.mastery_required-b.mastery_required);
}
function abilityBindingCode(a){return abilityKeys[a.id]||ABILITY_DEFAULT_KEYS[a.id]||a.key||''}
function validAbilityBinding(code){
 if(!/^Key[A-Z]$/.test(code))return false;
 return !ABILITY_RESERVED.has(code);
}
function saveAbilityKeys(){try{localStorage.setItem('echoAbilityKeys',JSON.stringify(abilityKeys))}catch{}}

function renderClassChoices(){
 const grid=$('classGrid');if(!grid)return;
 grid.textContent='';
 const classes=snap?.classes||{},p=me(),statNames={might:'Сила',vitality:'Живучесть',agility:'Ловкость',mana_regen:'Восстановление маны',magic_damage:'Сила магии'};
 Object.entries(classes).forEach(([id,cls])=>{
  const card=document.createElement('article');card.className='classOption';
  const h=document.createElement('h3');h.textContent=cls.name;
  const small=document.createElement('small');small.textContent=`${cls.style} · ${cls.title}`;
  const desc=document.createElement('p');desc.textContent=cls.description;
  const list=document.createElement('ul');
  const abilities=(cls.abilities||[]).map(aid=>p?.abilities?.[aid]?.name||aid);
  if(abilities.length)abilities.forEach(name=>{const li=document.createElement('li');li.textContent=name;list.append(li)});
  else{const li=document.createElement('li');li.textContent='Прежняя система заклинаний и созданные чары';list.append(li)}
  const bonus=document.createElement('p');bonus.textContent='Бонус: '+(Object.entries(cls.stat_bonus||{}).map(([k,v])=>`${statNames[k]||k} +${k==='magic_damage'?v*8+'%':v}`).join(', ')||'нет');
  const btn=document.createElement('button');btn.type='button';btn.dataset.chooseClass=id;btn.textContent=`Выбрать: ${cls.name}`;btn.disabled=classChoicePending;
  card.append(h,small,desc,list,bonus,btn);grid.append(card);
 });
}
function showClassOffer(force=false){
 const p=me();if(!p||!snap?.classes||p.class||Number(p.level)<5)return;
 if(!force&&classOfferDismissed)return;
 if(!force&&$('classOverlay').style.display==='flex')return;
 classOfferDismissed=false;renderClassChoices();$('classOverlay').style.display='flex';
}
function hideClassOffer(){classOfferDismissed=true;classChoicePending=false;const el=$('classOverlay');if(el)el.style.display='none'}

function renderClassUi(p){
 const badge=$('classBadge');
 if(badge)badge.textContent=p.class_name||'Путник';
 const strip=$('masteryStrip');
 if(strip){
  strip.textContent='';
  const order=['warrior','ranger','mage'];
  order.forEach(tree=>{
   const m=p.mastery?.[tree]||{level:1,next:0,xp:0},chip=document.createElement('span');chip.className='masteryChip';
   chip.title=`${m.name||ABILITY_TREE_NAMES[tree]}: ${m.xp||0}${m.next?' / '+m.next:''} опыта · максимум ${m.max||5}`;
   const name=document.createElement('span');name.textContent=ABILITY_TREE_NAMES[tree].slice(0,3).toUpperCase();
   const level=document.createElement('b');level.textContent=`${m.level||1}/${m.max||5}`;
   chip.append(name,level);strip.append(chip);
  });
 }
 const warn=$('classWarning');
 if(warn){
  let text='';
  if(!p.class){if(Number(p.level)>=5)text='Достигнут 5-й уровень: выбери класс в окне выбора. До выбора прежние заклинания работают с любым оружием.'}
  else if(!p.class_compatible){
   const weapon=p.weapon_catalog?.[p.weapon]?.name||p.weapon||'оружие';
   if(p.action_tree==='mage')text=`Экипировано: ${weapon}. Класс «${p.class_name}» не может использовать заклинания — они доступны только Магу с посохом.`;
   else text=`Экипировано: ${weapon}. Набор «${ABILITY_TREE_NAMES[p.action_tree]||p.action_tree}» несовместим с классом «${p.class_name}». Способности заблокированы — смени оружие.`;
  }
  warn.textContent=text;warn.hidden=!text;
 }
 if(p.class_offer&&!p.class&&!classOfferDismissed)showClassOffer(false);
}

function renderAbilityCards(container,p,tree,compact){
 if(!container)return;
 const list=classAbilityList(p,tree),sig=`${tree}|${p.class||''}|${p.weapon_kind}|${compact?'1':'0'}|${list.map(a=>a.id).join(',')}`;
 if(container.dataset.renderSig===sig){return}
 container.dataset.renderSig=sig;container.textContent='';
 list.forEach(a=>{
  const b=document.createElement('button');b.type='button';b.className='abilityBtn';b.dataset.ability=a.id;
  const cost=document.createElement('span');cost.className='abilityCost'+(a.resource==='mana'?' isMana':'');cost.textContent=a.arrows?`${a.arrows}➶`:`${a.cost}`;
  const key=document.createElement('span');key.className='abilityKey';key.textContent=keyLabel(abilityBindingCode(a));
  const icon=document.createElement('span');icon.className='abilityIcon';icon.textContent=a.icon||'✦';
  const name=document.createElement('span');name.className='abilityName';name.textContent=a.name;
  const meta=document.createElement('span');meta.className='abilityMeta';
  const bar=document.createElement('span');bar.className='abilityCooldown';
  b.append(cost,key,icon,name);
  if(!compact){const desc=document.createElement('span');desc.className='abilityDesc';desc.textContent=a.desc||'';b.append(desc)}
  b.append(meta,bar);container.append(b);
 });
}
function refreshAbilityCards(p){
 if(!p)return;
 document.querySelectorAll('[data-ability]').forEach(b=>{
  const a=p.abilities?.[b.dataset.ability];if(!a){b.disabled=true;return}
  const resKey=a.resource==='mana'?'mana':'stamina',resWord=a.resource==='mana'?'маны':'выносливости',resShort=a.resource==='mana'?'ман':'вын';  const compatible=!!p.class&&p.class===a.tree,remain=Number(a.remaining||0),cd=Math.max(.1,Number(a.cooldown||1)),low=Number(p[resKey]||0)<Number(a.cost||0),needArrows=Number(a.arrows||0),arrows=Number(p.inventory?.arrows||0),noArrows=needArrows>arrows;
  b.disabled=!compatible||!a.unlocked||remain>0||low||noArrows;
  b.classList.toggle('is-locked',!!p.class&&!a.unlocked);
  b.classList.toggle('incompatible',!!p.class&&!compatible);
  b.classList.toggle('is-cooling',remain>0);
  b.style.setProperty('--cd-width',`${Math.max(0,Math.min(1,remain/cd))*100}%`);
  const meta=b.querySelector('.abilityMeta');
  if(meta){
   if(!p.class)meta.textContent='Сначала выбери класс';
   else if(!compatible)meta.textContent=`Только для класса «${ABILITY_TREE_NAMES[a.tree]}»`;
   else if(!a.unlocked)meta.textContent=`Откроется на ${a.mastery_required} ур. мастерства`;
   else if(remain>0)meta.textContent=`Перезарядка ${remain.toFixed(1)} с`;
   else if(low)meta.textContent=`Нужно ${a.cost} ${resWord}`;
   else if(noArrows)meta.textContent=`Нужно стрел: ${needArrows}`;
   else meta.textContent=`${a.cost} ${resShort} · ${cd.toFixed(1)} с${needArrows?` · ${needArrows}➶`:''}`;
  }
  b.title=`${a.name} · ${a.cost} ${resWord}${needArrows?`, стрел: ${needArrows}`:''} · перезарядка ${cd.toFixed(1)} с · открывается на ${a.mastery_required} ур. мастерства «${ABILITY_TREE_NAMES[a.tree]}». ${a.desc||''}`;
 });
}
function renderAbilityBindings(p,tree){
 const box=$('abilityKeyList');if(!box)return;
 const list=classAbilityList(p,tree),sig=list.map(a=>a.id).join(',')+'|'+list.map(a=>abilityBindingCode(a)).join(',')+'|'+pendingAbilityBinding;
 if(box.dataset.renderSig===sig)return;
 box.dataset.renderSig=sig;box.textContent='';
 list.forEach(a=>{
  const row=document.createElement('span');row.className='abilityKeyRow'+(pendingAbilityBinding===a.id?' pending':'');
  const name=document.createElement('span');name.textContent=a.name;
  const btn=document.createElement('button');btn.type='button';btn.dataset.bindAbility=a.id;btn.textContent=keyLabel(abilityBindingCode(a));
  row.append(name,btn);box.append(row);
 });
 const reset=document.createElement('button');reset.type='button';reset.className='abilityReset';reset.dataset.resetAbilities='1';reset.textContent='Сбросить клавиши';box.append(reset);
 const hint=$('abilityBindingHint');
 if(hint)hint.textContent=pendingAbilityBinding?'Нажми новую клавишу (A–Z, кроме служебных). Escape — отмена.':'Нажми «Назначить» на карточке клавиши, затем новую клавишу.';
}
function syncAbilityKeyMap(p,tree){
 abilityKeyCodeToId={};
 classAbilityList(p,tree).forEach(a=>{const code=abilityBindingCode(a);if(code)abilityKeyCodeToId[code]=a.id});
}
function updateActionPanels(p){
 if(!p)return;
 renderClassUi(p);
 const tree=p.action_tree||'warrior',chosen=!!p.class,showAbilities=chosen;
 const spellBar=$('spellBar');
 if(spellBar)spellBar.style.display=(!chosen||tree==='mage')?'':'none';
 const bar=$('abilityBar');
 if(bar){bar.style.display=showAbilities?'flex':'none';bar.classList.toggle('stacked',showAbilities&&tree==='mage');if(showAbilities)renderAbilityCards(bar,p,tree,true)}
 const section=$('abilitySection');
 if(section){
  section.hidden=!showAbilities;
  if(showAbilities){
   renderAbilityCards($('abilityPanel'),p,tree,false);
   const title=$('abilitySectionTitle'),state=$('abilitySectionState'),hint=$('abilitySectionHint');
   if(title)title.textContent=`Набор: ${ABILITY_TREE_NAMES[tree]||tree}`;
   if(state)state.textContent=p.class===tree?'НАБОР АКТИВЕН':`КЛАСС: ${p.class_name||'—'}`;
   if(hint)hint.textContent=p.class===tree?'Способности открываются уровнями мастерства. Клавиши можно переназначить ниже.':`Оружие требует набор «${ABILITY_TREE_NAMES[tree]||tree}», но твой класс — «${p.class_name}». Способности заблокированы сервером до смены оружия.`;
   renderAbilityBindings(p,tree);
  }
 }
 syncAbilityKeyMap(p,showAbilities?tree:'mage');
 refreshAbilityCards(p);
}
function useAbility(id){
 const p=me();if(!p)return;
 const t=hasPointerAim?pointerWorld():{x:p.x+aim.x*260,y:p.y+aim.y*260},dx=t.x-p.x,dy=t.y-p.y;
 send({type:'ability',ability:id,aim_x:dx,aim_y:dy,target_x:t.x,target_y:t.y});
}
function handleAbilityCast(d){
 const colors={roar:'#ffd27a',lunge:'#ffe39a',whirlwind:'#ffcf7c',iron_guard:'#9bd7ff',bash:'#ffb37a',bloodhunt:'#e2555f',seismic_slam:'#d9b26a',arrow_rain:'#c7e884',piercing_shot:'#d8f5b0',fire_arrow:'#ff8b4a',ice_arrow:'#86e8ff',double_shot:'#d8f5b0',poison_arrow:'#9ede6a',blackout_bolt:'#a98bd8',eagle_mark:'#ffd98a',arcane_bolt:'#b678ff',frost_lance:'#65dfff',flame_burst:'#ff7a3d',chain_lightning:'#fff078',blink:'#a6e8ff',arcane_shield:'#8fd4ff',mana_surge:'#86d9ff',meteor_fall:'#ffb347'};
 const col=colors[d.ability]||'#e8d38c',now=performance.now();
 abilityFx.push({kind:d.ability,x:d.x,y:d.y,from_x:d.from_x??d.x,from_y:d.from_y??d.y,to_x:d.target_x??d.x,to_y:d.target_y??d.y,radius:Number(d.radius||0),chain:Array.isArray(d.chain)?d.chain:[],until:now+(d.ability==='lunge'?380:d.ability==='blink'?420:760)});
 spawnParticles(d.x,d.y,col,d.ability==='meteor_fall'?30:16,d.ability==='meteor_fall'?6:4.5,d.ability==='meteor_fall'?6:4,.55);
 // concise audio for the caster's own casts (server echoes are for everyone)
 if(typeof myId!=='undefined'&&d.id===myId){const a=window.LesEchoAudio;if(a){const elem={arcane_bolt:'Тень',frost_lance:'Лёд',flame_burst:'Огонь',chain_lightning:'Молния',meteor_fall:'Звёзды'}[d.ability];if(d.ability==='meteor_fall'){sfxCall('impact','fire');triggerScreenShake(11,d.x,d.y)}else if(d.ability==='chain_lightning'){sfxCall('cast','Молния');triggerScreenShake(4,d.x,d.y)}else if(d.ability==='blink'){sfxCall('dodge')}else if(d.ability==='mana_surge'){sfxCall('level')}else if(elem){sfxCall('cast',elem)}else{sfxCall('swing',d.ability==='whirlwind'||d.ability==='seismic_slam')}}}
}
function drawGroundAndAbilityFx(now,ox,oy){
 if(snap?.ground_effects)for(const f of snap.ground_effects){
  const x=Number(f.x)+ox,y=Number(f.y)+oy,r=Math.max(8,Number(f.radius||0)),tele=Number(f.telegraph||0);
  ctx.save();
  if(tele>0){
   ctx.globalAlpha=.16+.1*Math.sin(now/90);ctx.fillStyle='#e8c56e';ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
   ctx.globalAlpha=.9;ctx.strokeStyle='#ffe29a';ctx.lineWidth=2;ctx.setLineDash([7,5]);ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);
   ctx.fillStyle='#fff0bc';ctx.font='bold 11px system-ui';ctx.textAlign='center';ctx.fillText(`ЗАЛП · ${tele.toFixed(1)} с`,x,y-r-8);
  }else{
   const pulse=.5+.5*Math.sin(now/110);ctx.globalAlpha=.18+.1*pulse;ctx.fillStyle='#a9d96d';ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();
   ctx.globalAlpha=.8;ctx.strokeStyle='#d7f39a';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.stroke();
   for(let i=0;i<14;i++){const phase=(now/380+i*.137)%1,ang=i*2.39996,rr=r*.15+phase*r*.9;ctx.globalAlpha=.75*(1-phase);ctx.strokeStyle=i%2?'#e9ffbd':'#a6d983';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x+Math.cos(ang)*rr,y+Math.sin(ang)*rr-16);ctx.lineTo(x+Math.cos(ang)*rr,y+Math.sin(ang)*rr+8);ctx.stroke()}
  }
  ctx.restore();
 }
 drawAbilityFx(now,ox,oy);
}
function drawAbilityFx(now,ox,oy){
 for(const fx of abilityFx){
  const life=Math.max(0,Math.min(1,(fx.until-now)/700)),x=fx.x+ox,y=fx.y+oy;
  ctx.save();ctx.globalCompositeOperation='lighter';
  if(fx.kind==='lunge'){
   ctx.globalAlpha=life*.85;ctx.strokeStyle='#ffe7a1';ctx.lineWidth=9;ctx.lineCap='round';ctx.beginPath();ctx.moveTo(fx.from_x+ox,fx.from_y+oy);ctx.lineTo(fx.to_x+ox,fx.to_y+oy);ctx.stroke();
   ctx.strokeStyle='#fff6ce';ctx.lineWidth=2;ctx.stroke();
  }else if(fx.kind==='roar'){
   const rr=30+(1-life)*80;ctx.globalAlpha=life*.8;ctx.strokeStyle='#ffd887';ctx.lineWidth=3;ctx.beginPath();ctx.arc(x,y,rr,0,Math.PI*2);ctx.stroke();
  }else if(fx.kind==='iron_guard'){
   ctx.globalAlpha=life*.7;ctx.strokeStyle='#a8e2ff';ctx.lineWidth=3;ctx.beginPath();ctx.arc(x,y,24+(1-life)*8,0,Math.PI*2);ctx.stroke();
  }else if(fx.kind==='blink'){
   // a streak that only ignites toward the landing point, plus fading sparks:
   // a flat white bar would burn out the whole screen under 'lighter'.
   const x0=fx.from_x+ox,y0=fx.from_y+oy,x1=fx.to_x+ox,y1=fx.to_y+oy;
   const along=ctx.createLinearGradient(x0,y0,x1,y1);
   along.addColorStop(0,'#7fd4ff00');along.addColorStop(.5,'#8fdcff99');along.addColorStop(1,'#eafaff');
   ctx.lineCap='round';ctx.globalAlpha=life*.8;ctx.strokeStyle=along;ctx.lineWidth=5;
   ctx.beginPath();ctx.moveTo(x0,y0);ctx.lineTo(x1,y1);ctx.stroke();
   ctx.globalAlpha=life*.85;ctx.strokeStyle='#ffffff';ctx.lineWidth=1.3;
   ctx.beginPath();ctx.moveTo(x0+(x1-x0)*.45,y0+(y1-y0)*.45);ctx.lineTo(x1,y1);ctx.stroke();
   for(let i=0;i<7;i++){const q=i/7;ctx.globalAlpha=life*(1-q)*.6;ctx.fillStyle='#bfe9ff';ctx.beginPath();ctx.arc(x0+(x1-x0)*q,y0+(y1-y0)*q-4*Math.sin(q*7),Math.max(.6,2.6-q*1.8),0,Math.PI*2);ctx.fill()}
  }else if(fx.kind==='chain_lightning'){
   const pts=[{x:fx.from_x,y:fx.from_y},...(fx.chain||[]).map(c=>({x:Number(c.x),y:Number(c.y)}))];
   ctx.lineCap='round';
   for(let i=1;i<pts.length;i++){
    const a=pts[i-1],b=pts[i];
    for(const [w,col,al] of [[6,'#3fa4ff',.55],[2.4,'#eafcff',.95]]){
     ctx.globalAlpha=life*al;
     ctx.strokeStyle=col;ctx.lineWidth=w;ctx.beginPath();ctx.moveTo(a.x+ox,a.y+oy);
     const segs=5;
     for(let k=1;k<=segs;k++){const t=k/segs,jx=k<segs?(Math.random()-.5)*14:0,jy=k<segs?(Math.random()-.5)*14:0;
      ctx.lineTo(a.x+ox+(b.x-a.x)*t+jx,a.y+oy+(b.y-a.y)*t+jy)}
     ctx.stroke();
    }
    // sparks where the arc bites each target
    ctx.globalAlpha=life*.9;
    for(let n=0;n<5;n++){const ang=n*1.2566+i*.6,len=7+((i*3+n)%5)*2.4;
     ctx.strokeStyle=n%2?'#fff8c8':'#8fdcff';ctx.lineWidth=1.4;
     ctx.beginPath();ctx.moveTo(b.x+ox,b.y+oy);ctx.lineTo(b.x+ox+Math.cos(ang)*len,b.y+oy+Math.sin(ang)*len);ctx.stroke()}
   }
  }else if(fx.kind==='flame_burst'||fx.kind==='meteor_fall'){
   const rr=Math.max(60,Number(fx.radius||120)),k=fx.kind==='meteor_fall';
   ctx.globalAlpha=life*.9;ctx.strokeStyle=k?'#ffb347':'#ff7a3d';ctx.lineWidth=k?7:5;
   ctx.beginPath();ctx.arc(x,y,rr*(.3+.7*(1-life)),0,Math.PI*2);ctx.stroke();
   ctx.globalAlpha=life*.6;ctx.strokeStyle=k?'#fff0a8':'#ffd08a';ctx.lineWidth=2;
   ctx.beginPath();ctx.arc(x,y,rr*(.15+.85*(1-life))*1.12,0,Math.PI*2);ctx.stroke();
   if(k){const fall=(1-life)*260;ctx.globalAlpha=life;ctx.strokeStyle='#ffd08a';ctx.lineWidth=9;ctx.lineCap='round';
    ctx.beginPath();ctx.moveTo(x+34,y-fall-40);ctx.lineTo(x,y);ctx.stroke();}
   else{// flame burst: tongues licking up off the shockwave so it reads as fire, not a ring
    const edge=rr*(.3+.7*(1-life));
    for(let n=0;n<12;n++){const ang=n/12*Math.PI*2+.2,h=(9+7*Math.abs(Math.sin(now/145+n*1.7)))*(0.5+life);
     const bx=x+Math.cos(ang)*edge,by=y+Math.sin(ang)*edge*.72;
     ctx.globalAlpha=life*.5;ctx.fillStyle=n%2?'#ffb347':'#ff6a34';
     ctx.beginPath();ctx.moveTo(bx-4,by);ctx.quadraticCurveTo(bx,by-2*h,bx+4,by);ctx.fill()}
   }
  }else if(fx.kind==='arcane_shield'){
   ctx.globalAlpha=life*.7;ctx.strokeStyle='#8fd4ff';ctx.lineWidth=2.5;
   ctx.beginPath();ctx.arc(x,y-16,26+(1-life)*6,0,Math.PI*2);ctx.stroke();
   ctx.globalAlpha=life*.35;ctx.fillStyle='#3f7fbf';ctx.beginPath();ctx.arc(x,y-16,24+(1-life)*5,0,Math.PI*2);ctx.fill();
  }else if(fx.kind==='mana_surge'){
   for(let i=0;i<9;i++){const q=(i/9+(1-life))%1;ctx.globalAlpha=(1-q)*life;ctx.fillStyle='#a9e7ff';ctx.beginPath();ctx.arc(x+(i%3-1)*10,y-6-q*54,2.4,0,Math.PI*2);ctx.fill()}
   ctx.globalAlpha=life*.5;ctx.strokeStyle='#86d9ff';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,18+(1-life)*26,0,Math.PI*2);ctx.stroke();
  }else if(fx.kind==='whirlwind'){
   const rr=Math.max(70,Number(fx.radius||100));ctx.globalAlpha=life*.8;ctx.strokeStyle='#ffd27a';ctx.lineWidth=5;ctx.beginPath();ctx.arc(x,y,rr*(.45+.55*(1-life)),0,Math.PI*2);ctx.stroke();
  }else{
   ctx.globalAlpha=life*.7;ctx.strokeStyle='#e7f1b0';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,14+(1-life)*36,0,Math.PI*2);ctx.stroke();
  }
  ctx.restore();
 }
 abilityFx=abilityFx.filter(fx=>now<fx.until);
 const p=me();
 if(p&&hoverAbilityId&&hasPointerAim&&p.abilities?.[hoverAbilityId]){
  const a=p.abilities[hoverAbilityId],t=pointerWorld(),dx=t.x-p.x,dy=t.y-p.y,dist=Math.max(.01,Math.hypot(dx,dy)),range=Number(a.range||0),k=range&&dist>range?range/dist:1,tx=p.x+dx*k,ty=p.y+dy*k,sx=p.x+ox,sy=p.y+oy,ex=tx+ox,ey=ty+oy;
  ctx.save();ctx.strokeStyle='#ffe6a0aa';ctx.fillStyle='#ffe6a01a';ctx.lineWidth=1.5;ctx.setLineDash([5,5]);
  if(a.id==='lunge'){const len=Math.max(60,Number(a.distance||155)),w=Math.max(10,Number(a.width||34));ctx.beginPath();ctx.moveTo(sx,sy);ctx.lineTo(sx+aim.x*len,sy+aim.y*len);ctx.stroke();ctx.setLineDash([]);ctx.beginPath();ctx.arc(sx+aim.x*len,sy+aim.y*len,w,0,Math.PI*2);ctx.stroke()}
  else if(Number(a.radius||0)>0){ctx.beginPath();ctx.arc(ex,ey,Number(a.radius),0,Math.PI*2);ctx.fill();ctx.stroke();ctx.setLineDash([]);ctx.beginPath();ctx.arc(ex,ey,6,0,Math.PI*2);ctx.stroke()}
  else{ctx.beginPath();ctx.moveTo(sx,sy);ctx.lineTo(ex,ey);ctx.stroke()}
  ctx.restore();
 }
}

function connect(name){let scheme=location.protocol==='https:'?'wss:':'ws:';ws=new WebSocket(`${scheme}//${location.host}/ws?name=${encodeURIComponent(name)}`);ws.onopen=()=>$('connection').style.display='none';ws.onmessage=e=>{let d;try{d=JSON.parse(e.data)}catch{return}if(d.type==='ping'){send({type:'pong',t:d.t});return}if(!MapEvents.accepts(d,me()?.region))return;if(d.type==='npc_dialog'&&d.target===myId){WorldUI.openNpc(d.npc,d.quest);return}if(d.type==='portal_dialog'&&d.target===myId){sfxCall('portal');WorldUI.openPortal(d.portal);return}if(d.type==='region_changed'&&d.target===myId){WorldUI.pendingReason=d.reason;sfxCall('portal');return}if(d.type==='kick'){$('connection').style.display='none';$('login').style.display='flex';$('authError').textContent=d.message||'Соединение закрыто сервером.';setAuthMode('login');return}if(d.type==='state'){snap=d;myId=d.you;updateHud();syncCustomSpellButtons(me());renderCustomSpellBindings(me());renderCustomSpellLibrary(me())}else if(d.type==='stats_updated'){if(d.target===myId){let own=me();if(own){own.stats=d.stats||d.stat_values||own.stats;own.stat_values=d.stat_values||d.stats||own.stat_values;own.skill_points=d.skill_points??own.skill_points;own.xp=d.xp??own.xp;own.level=d.level??own.level;own.mana_regen_level=d.mana_regen_level??own.mana_regen_level;own.magic_damage_level=d.magic_damage_level??own.magic_damage_level;own.upgrades_view=d.upgrades_view??own.upgrades_view;own.insight_level=d.insight_level??own.insight_level;for(const k of ['hp','max_hp','mana','max_mana','stamina','max_stamina','mana_growth','mana_growth_next'])if(d[k]!==undefined)own[k]=d[k];own.stats_revision=d.stats_revision??own.stats_revision;document.querySelectorAll('.upgrade[data-pending]').forEach(b=>{clearTimeout(b._upgradeTimer);delete b.dataset.pending});renderStatsPanel(own);if(typeof renderCharOverlay==='function')renderCharOverlay(own);updateHud()}}}else if(d.type==='player_update'){if(d.target===myId&&d.player&&snap){let i=snap.players.findIndex(q=>q.id===myId);if(i>=0)snap.players[i]=d.player;inventorySignature='';marketSignature='';wizardRenderSignature='';forgeRenderSignature='';updateHud();renderInventory(me());renderMarket(me());if($('charOverlay')?.style.display==='flex'&&typeof renderCharOverlay==='function')renderCharOverlay(me());syncCustomSpellButtons(me());renderCustomSpellBindings(me());renderCustomSpellLibrary(me());if($('wizardOverlay')?.style.display==='flex')renderWizard(me());if($('forgeOverlay')?.style.display==='flex')renderForge(me())}}else if(d.type==='forge_result'){if(d.target===myId){let own=me();if(own){own.gold=d.gold??own.gold;own.inventory=d.inventory||own.inventory;own.upgrades=d.upgrades||own.upgrades;own.weapon=d.weapon||own.weapon;own.gear=d.gear||own.gear;let scene=$('forgeAnvilScene');if(scene){scene.dataset.pending='0';scene.classList.remove('hammering','forge-success','forge-fail');scene.classList.add(d.success?'forge-success':'forge-fail')}renderForge(own);updateHud();if(d.success){toast(`${d.item_name} улучшено до +${d.level_after}: ${d.benefit}`)}else{toast(`Неудача (${d.chance}% шанс). Стоимость попытки списана, уровень не изменился.`)}}}}else if(d.type==='notice'){if(!d.target||d.target===myId){if(/уровня/.test(d.text||'')){sfxCall('level');const own=me();if(own)fxCall('level',own.x,own.y)}let scene=$('forgeAnvilScene');if(scene?.dataset.pending==='1'){scene.dataset.pending='0';scene.classList.remove('hammering');renderForge(me())}message(d.text)}}else if(d.type==='chat')message(d.text,'chat',d.name);else if(d.type==='class_offer'){if(d.target===myId||!d.target){classOfferDismissed=false;if(!snap?.classes&&d.classes)snap={...(snap||{}),classes:d.classes};showClassOffer(true)}}else if(d.type==='class_selected'){if(d.target===myId){classChoicePending=false;classOfferDismissed=true;hideClassOffer();let own=me();if(own&&d.player&&snap){const i=snap.players.findIndex(q=>q.id===myId);if(i>=0)snap.players[i]=d.player}else if(snap){send({type:'sync'})}updateHud();if(typeof renderCharOverlay==='function')renderCharOverlay(me());toast(`Класс выбран: ${d.class_name}. Постоянные бонусы: ${(d.bonus||[]).join(', ')||'нет'}.`)}}else if(d.type==='mastery_update'){if(d.target===myId){let own=me();if(own&&d.mastery){own.mastery=d.mastery;updateHud()}toast(`Мастерство «${ABILITY_TREE_NAMES[d.tree]||d.tree}»: уровень ${d.level}.`)}}else if(d.type==='ability_cast')handleAbilityCast(d);else if(d.type==='ability_impact'||d.type==='ground_pulse'){const col=d.element==='fire'?'#ff9a54':d.element==='ice'?'#8ce9ff':'#cfe99b';spawnParticles(d.x,d.y,col,d.type==='ground_pulse'?12:18,4,4,.55);sfxCall('impact',d.element);fxCall('cast',d.x,d.y,col);triggerScreenShake(d.type==='ground_pulse'?8:5,d.x,d.y)}else if(d.type==='weapon_action'){weaponActions.push({id:d.id,action:d.action,weapon:d.weapon,weapon_kind:d.weapon_kind,x:d.x,y:d.y,aim_x:d.aim_x,aim_y:d.aim_y,charge:d.charge||0,started:performance.now(),until:performance.now()+(d.action==='cast'?460:360)});const heavyMelee=d.weapon_kind==='melee'&&(((d.charge||0)>.55)||/axe|maul|greatsword|halberd|scythe/.test(d.weapon||''));if(d.action==='cast'){sfxCall('cast',d.element);fxCall('cast',d.x,d.y)}else if(d.weapon_kind==='bow'){sfxCall('bowShot')}else{sfxCall('swing',heavyMelee)}}else if(d.type==='hit'){spawnParticles(d.x,d.y,d.critical?'#fff1a6':'#ffda79',d.critical?22:12,d.critical?6:4,d.critical?5:4,d.critical?.72:.5);hitFlashes[d.mob]=performance.now()+240;attackFx.push({x:d.x,y:d.y,until:performance.now()+420,text:d.critical?`КРИТ · -${d.damage}`:`-${d.damage}`,critical:!!d.critical});sfxCall('hit',!!d.critical);fxCall('hit',d.x,d.y,!!d.critical,d.critical?'#ffe08c':'#ffd9a0');triggerScreenShake(d.critical?7.5:4.2,d.x,d.y)}else if(d.type==='spell_fx'){if(d.spell==='meteor'){triggerScreenShake(13,d.x,d.y);sfxCall('impact','fire')}else{sfxCall('impact',d.element)}fxCall('cast',d.x,d.y,(d.palette?.colors||['#bd77ff'])[0]);let pal=d.palette?.colors||['#bd77ff','#6edfff','#fff1c8'];spawnParticles(d.x,d.y,pal[0],24+Math.min(18,(d.mastery||1)*2),6,6,0.8);spellFx.push({spell:d.spell,kind:d.kind||d.spell,name:d.name||d.spell,rarity:d.rarity||1,mastery:d.mastery||1,variant:d.variant||0,palette:d.palette||null,x:d.x,y:d.y,radius:d.radius||100,until:performance.now()+1500})}else if(d.type==='hit_player'&&d.id===myId){sfxCall('hurt');$('flash').style.opacity='.26';setTimeout(()=>$('flash').style.opacity='0',100);toast(`Получен урон: ${d.damage}`)}else if(d.type==='pvp_hit'){if(d.id===myId){sfxCall('hurt');$('flash').style.opacity='.34';setTimeout(()=>$('flash').style.opacity='0',130);toast(`Игрок нанёс ${d.damage} урона`)}else if(d.attacker===myId){attackFx.push({x:d.x,y:d.y,until:performance.now()+420,text:`-${d.damage}`})}}else if(d.type==='error'){ $('connection').textContent=d.message;$('connection').style.display='block';message(d.message)}};ws.onclose=e=>{if(e.reason==='AUTH_REQUIRED'){$('connection').style.display='none';$('login').style.display='flex';$('authError').textContent='Сессия завершена. Войдите снова.';setAuthMode('login');return}$('connection').style.display='block';setTimeout(()=>{if($('login').style.display==='none')connect(name)},1600)}}
let authMode='register';
function setAuthMode(mode){authMode=mode;const isRegister=mode==='register';$('registerMode').classList.toggle('active',isRegister);$('loginMode').classList.toggle('active',!isRegister);$('confirmWrap').style.display=isRegister?'block':'none';$('confirmInput').required=isRegister;$('passwordInput').autocomplete=isRegister?'new-password':'current-password';$('authSubmit').textContent=isRegister?'Создать аккаунт':'Войти в мир';$('authError').textContent=''}
$('registerMode').addEventListener('click',()=>setAuthMode('register'));$('loginMode').addEventListener('click',()=>setAuthMode('login'));
$('loginForm').addEventListener('submit',async e=>{e.preventDefault();const username=$('nameInput').value.trim(),password=$('passwordInput').value;if(authMode==='register'&&password!==$('confirmInput').value){$('authError').textContent='Пароли не совпадают.';return}const button=$('authSubmit');button.disabled=true;$('authError').textContent='';try{const response=await fetch(`/api/auth/${authMode}`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({username,password})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Не удалось выполнить запрос.');$('login').style.display='none';connect(data.username)}catch(err){$('authError').textContent=err.message||'Не удалось связаться с сервером.'}finally{button.disabled=false}});
async function restoreSession(){try{const response=await fetch('/api/auth/me',{credentials:'same-origin'}),data=await response.json();if(data.authenticated){$('login').style.display='none';connect(data.username)}else{$('login').style.display='flex';$('nameInput').focus()}}catch{$('login').style.display='flex';$('authError').textContent='Не удалось связаться с сервером. Обновите страницу.'}}
$('logoutButton').addEventListener('click',async()=>{try{await fetch('/api/auth/logout',{method:'POST',credentials:'same-origin'})}finally{if(ws)ws.close(1000,'logout');snap=null;myId=null;$('controlsOverlay').style.display='none';$('login').style.display='flex';$('passwordInput').value='';$('confirmInput').value='';setAuthMode('login')}});
restoreSession();



/* ===== ИГРОВОЕ МЕНЮ (Esc) · НАЗНАЧЕНИЕ КЛАВИШ · СМЕНА АККАУНТА ===== */
const GAME_MENU_IDS=['gameMenuOverlay','keybindOverlay','accountOverlay','charOverlay'];
// --- общие объявления, доступные и внутри основного IIFE, и после него ---
let actionKeys={};
const ACTION_KEY_DEFAULTS={character:'KeyC',inventory:'KeyI',journal:'KeyJ',market:'KeyB',wizard:'KeyG',forge:'KeyH',map:'KeyM',dodge:'KeyV',gather:'KeyE',interact:'KeyF',potion:'KeyQ',attack:'Space',chat:'Enter'};
const ACTION_KEY_NAMES={character:'Меню персонажа',inventory:'Рюкзак и крафт',journal:'Журнал поручений',market:'Лавка',wizard:'Маг',forge:'Кузница',map:'Карта мира',dodge:'Рывок',gather:'Сбор ресурса',interact:'Взаимодействие (Хранитель)',potion:'Настойка',attack:'Атака (удерживай)',chat:'Чат'};
let listeningActionKey=null;
let toggleCharacter=()=>{};
let setListeningAction=()=>{};
let renderKeybindSections=()=>{};
let syncActionKeyLabels=()=>{};
let applyActionToGame=()=>false;
let movementCodeSet=()=>new Set();
let RESERVED_ACTION_CODES=new Set(['Escape','Tab']);
let lastGameMenuToggle=0,lastSubmenuToggle=0;
function toggleGameMenu(open,force){const el=$('gameMenuOverlay');if(!el)return;if(!force&&performance.now()-lastGameMenuToggle<260)return;lastGameMenuToggle=performance.now();const next=open??(getComputedStyle(el).display==='none');const prev=performance.now();if(next){lastGameMenuToggle=0;lastSubmenuToggle=0;closeTopGameMenu();toggleKeybinds(false,true);toggleAccounts(false,true);lastGameMenuToggle=prev;lastSubmenuToggle=prev;el.style.display='flex';$('closeGameMenu').focus()}else{lastSubmenuToggle=0;el.style.display='none';toggleKeybinds(false,true);toggleAccounts(false,true);toggleCharacter(false,true);lastSubmenuToggle=prev}}
function toggleKeybinds(open,force){const el=$('keybindOverlay');if(!el)return;if(!force&&performance.now()-lastSubmenuToggle<260)return;lastSubmenuToggle=performance.now();const next=open??(getComputedStyle(el).display==='none');el.style.display=next?'flex':'none';if(next){renderKeybindSections();$('closeKeybinds').focus()}}
function toggleAccounts(open,force){const el=$('accountOverlay');if(!el)return;if(!force&&performance.now()-lastSubmenuToggle<260)return;lastSubmenuToggle=performance.now();const next=open??(getComputedStyle(el).display==='none');el.style.display=next?'flex':'none';if(next){loadAccountRoster();hideSwitchForm()}else hideSwitchForm()}
function openClassPicker(){if(me()?.class){toast('Класс уже выбран — смена класса сервером запрещена.');return}showClassOffer(true)}
function wireGameMenuUI(){
 const btn=$('gameMenuButton');
 if(btn&&!btn.dataset.wired){btn.dataset.wired='1';btn.type='button';btn.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();toggleGameMenu()})}
 $('closeGameMenu').onclick=()=>{lastGameMenuToggle=0;toggleGameMenu(false,true)};
 $('closeKeybinds').onclick=()=>{lastSubmenuToggle=0;toggleKeybinds(false,true)};
 $('closeAccounts').onclick=()=>{lastSubmenuToggle=0;toggleAccounts(false,true)};
 GAME_MENU_IDS.forEach(id=>{const el=$(id);if(!el||el.dataset.backdropWired)return;el.dataset.backdropWired='1';el.addEventListener('click',e=>{if(e.target===el){if(id==='gameMenuOverlay'){lastGameMenuToggle=0;toggleGameMenu(false,true)}else if(id==='keybindOverlay'){lastSubmenuToggle=0;toggleKeybinds(false,true)}else if(id==='charOverlay'){lastSubmenuToggle=0;toggleCharacter(false,true)}else{lastSubmenuToggle=0;toggleAccounts(false,true)}}})});
 document.querySelectorAll('#gameMenuList [data-menu-action]').forEach(b=>{if(b.dataset.wired)return;b.dataset.wired='1';b.type='button';b.addEventListener('click',async()=>{
  const action=b.dataset.menuAction;
  if(action==='continue'){lastGameMenuToggle=0;toggleGameMenu(false,true);return}
  if(action==='keybinds'){lastSubmenuToggle=0;toggleKeybinds(true,true);return}
  if(action==='accounts'){lastSubmenuToggle=0;toggleAccounts(true,true);return}
  if(action==='character'){lastGameMenuToggle=0;toggleGameMenu(false,true);toggleCharacter(true,true);return}
  if(action==='inventory'){lastGameMenuToggle=0;toggleGameMenu(false,true);openInventory();return}
  if(action==='quests'){lastGameMenuToggle=0;toggleGameMenu(false,true);openQuestJournal();return}
  if(action==='classes'){lastGameMenuToggle=0;toggleGameMenu(false,true);openClassPicker();return}
  if(action==='controls'){lastGameMenuToggle=0;toggleGameMenu(false,true);toggleControls(true);return}
  if(action==='spelllib'){lastGameMenuToggle=0;toggleGameMenu(false,true);toggleControls(true);requestAnimationFrame(()=>$('customSpellLibraryList').scrollIntoView({behavior:'smooth',block:'center'}));return}
  if(action==='help'){lastGameMenuToggle=0;toggleGameMenu(false,true);toggleGuide(true);return}
  if(action==='map'){lastGameMenuToggle=0;toggleGameMenu(false,true);toggleMap();return}
  if(action==='logout'){lastGameMenuToggle=0;toggleGameMenu(false,true);$('logoutButton').click()}
 })});
}
wireGameMenuUI();
document.addEventListener('DOMContentLoaded',wireGameMenuUI);

/* ---- Назначение клавиш: способности, заклинания, созданные чары ---- */
let keybindListening=null,keybindSig='';
function finishKeybindCapture(kind,id,code,label){
 if(kind==='ability'){
  if(!validAbilityBinding(code)){toast('Эта клавиша недоступна для способности. Выбери букву A–Z.');renderKeybindSections();return}
  Object.keys(abilityKeys).forEach(k=>{if(k!==id&&abilityKeys[k]===code)delete abilityKeys[k]});
  abilityKeys[id]=code;saveAbilityKeys();updateActionPanels(me());toast(`Способность назначена на ${label}`);
 }else if(kind==='spell'){
  const i=spellIds.indexOf(id);if(i<0)return renderKeybindSections();
  const j=spellKeyCodes.indexOf(code);if(j>=0&&j!==i)[spellKeyCodes[i],spellKeyCodes[j]]=[spellKeyCodes[j],spellKeyCodes[i]];else spellKeyCodes[i]=code;
  try{localStorage.setItem(spellKeyStore,JSON.stringify(spellKeyCodes))}catch{}
  syncSpellKeys();toast(`Заклинание назначено на ${label}`);
 }else if(kind==='custom'){
  send({type:'bind_custom_spell',spell:id,key:code});toast(`Сохраняю назначение на ${label}…`);
 }
 keybindListening=null;renderKeybindSections();
}
function validSpellBindCode(code){return /^Digit[0-9]$/.test(code)||/^Numpad[0-9]$/.test(code)}
document.addEventListener('keydown',e=>{
 if(!keybindListening||getComputedStyle($('keybindOverlay')).display==='none')return;
 e.preventDefault();e.stopPropagation();
 if(e.key==='Escape'){keybindListening=null;renderKeybindSections();return}
 const{kind,id}=keybindListening,code=e.code,label=keyLabel(code)||code;
 if(kind==='ability'&&/^Key[A-Z]$/.test(code)){finishKeybindCapture(kind,id,code,label);return}
 if(kind==='spell'&&validSpellBindCode(code)){finishKeybindCapture(kind,id,code,label);return}
 if(kind==='custom'&&(normalizeCustomKey(code)||code==='Digit0')){finishKeybindCapture(kind,id,normalizeCustomKey(code)||code,label);return}
 toast('Клавиша не подходит для этого действия. Esc — отмена.');
},true);
function keybindRow(name,current,listening,onedit){const row=document.createElement('div');row.className='keybindRow'+(listening?' is-listening':'');const label=document.createElement('span');label.className='keybindName';label.textContent=name;const key=document.createElement('span');key.className='keybindKey';key.textContent=current;const btn=document.createElement('button');btn.type='button';btn.textContent=listening?'Жду клавишу…':'Изменить';btn.disabled=!onedit;if(onedit)btn.onclick=onedit;btn.setAttribute('aria-label',`Изменить клавишу: ${name}`);row.append(label,key,btn);return row}
function keybindSection(title,note,rows,extra){const sec=document.createElement('section');sec.className='keybindSection';const h=document.createElement('h3');h.textContent=title;sec.appendChild(h);if(note){const p=document.createElement('p');p.className='bindingHint';p.textContent=note;sec.appendChild(p)}const grid=document.createElement('div');grid.className='customSpellKeyList';rows.forEach(r=>grid.appendChild(r));sec.appendChild(grid);if(extra)sec.appendChild(extra);return sec}
renderKeybindSections=()=>{
 const host=$('keybindSections'),p=me();if(!host)return;
 if(getComputedStyle($('keybindOverlay')).display==='none')return;
 const tree=p?.action_tree||'warrior';
 const sig=[tree,p?.class,Object.keys(p?.abilities||{}).join(','),JSON.stringify(spellKeyCodes),JSON.stringify((p?.custom_spells||[]).map(x=>[x.id||x.spell_id,x.name,x.key])),JSON.stringify(abilityKeys),JSON.stringify(actionKeys),keybindListening?keybindListening.kind+':'+keybindListening.id:'',listeningActionKey||''].join('|');
 if(sig===keybindSig)return;keybindSig=sig;host.replaceChildren();
 if(!p){const sec=keybindSection('Клавиши','Игровые данные ещё не загружены.',[]);const empty=document.createElement('span');empty.className='bindingEmpty';empty.textContent='Подожди подключения к миру.';sec.querySelector('.customSpellKeyList').appendChild(empty);host.appendChild(sec);return}
 const moveRows=[['Движение вперёд','W / ↑'],['Движение назад','S / ↓'],['Движение влево','A / ←'],['Движение вправо','D / →']].map(m=>keybindRow(m[0],m[1],false,null));
 moveRows.forEach(r=>{const b=r.querySelector('button');b.disabled=true;b.title='Клавиши движения закреплены, чтобы персонаж всегда мог уйти от опасности'});
 host.appendChild(keybindSection('Движение','WASD и стрелки закреплены и не переназначаются.',moveRows));
 const actOrder=['attack','dodge','gather','interact','potion','character','inventory','market','wizard','forge','map','chat'];
 const actRows=actOrder.map(a=>keybindRow(ACTION_KEY_NAMES[a],actionKeyLabel(a),listeningActionKey===a,()=>setListeningAction(a)));
 const resetAct=document.createElement('button');resetAct.type='button';resetAct.className='close';resetAct.style.marginTop='8px';resetAct.textContent='Сбросить клавиши действий к стандартным';
 resetAct.onclick=()=>{actionKeys={...ACTION_KEY_DEFAULTS};saveActionKeys();listeningActionKey=null;syncActionKeyLabels();updateActionPanels(me());renderKeybindSections();toast('Клавиши действий сброшены')};
 host.appendChild(keybindSection('Игровые действия','Нажмите «Изменить», затем любую свободную клавишу. Esc — отмена. ESC, Enter и WASD защищены от назначения, чтобы меню и чат всегда открывались.',actRows,resetAct));
 if(p.class){
  const list=classAbilityList(p,tree);
  const rows=list.map(a=>keybindRow(`${a.name} · ${ABILITY_TREE_NAMES[tree]||''}`,keyLabel(abilityBindingCode(a)),keybindListening?.kind==='ability'&&keybindListening.id===a.id,()=>{keybindListening={kind:'ability',id:a.id};renderKeybindSections()}));
  const reset=document.createElement('button');reset.type='button';reset.className='close';reset.style.marginTop='8px';reset.textContent='Сбросить клавиши способностей';
  reset.onclick=()=>{abilityKeys={};saveAbilityKeys();keybindListening=null;updateActionPanels(me());renderKeybindSections();toast('Клавиши способностей сброшены к стандартным')};
  host.appendChild(keybindSection(`Способности · ${ABILITY_TREE_NAMES[tree]||tree}`,tree==='mage'?'Способности мага тратят ману. Клавиши — буквы A–Z, кроме занятых (WASD, E, F, I, J, M, B, G, H, Q, C, V, Z).':'Клавиши — буквы A–Z, кроме занятых (WASD, E, F, I, J, M, B, G, H, Q, C, V, Z).',rows,reset));
 }
 if(!p.class||tree==='mage'){
  const catalog=p.spell_catalog||{};
  const rows=spellIds.map((id,i)=>keybindRow(spellNames[id]||id,spellKeyLabel(spellKeyCodes[i]),keybindListening?.kind==='spell'&&keybindListening.id===id,()=>{keybindListening={kind:'spell',id};renderKeybindSections()}));
  host.appendChild(keybindSection('Классовые заклинания','Заклинания нажимаются с Shift + цифра, чтобы не мешать быстрым слотам инвентаря (1–9).',rows));
  const customs=p.custom_spells||[];
  if(customs.length){
   const crows=customs.map(sp=>{const id=sp.id||sp.spell_id||sp.custom_id;if(!id)return null;return keybindRow(sp.name||'Заклинание',displaySpellKey(sp.key),keybindListening?.kind==='custom'&&keybindListening.id===id,()=>{keybindListening={kind:'custom',id};renderKeybindSections()})}).filter(Boolean);
   host.appendChild(keybindSection('Созданные заклинания','Доступны F1–F12 и 0. Назначение сохраняется на аккаунте.',crows));
  }
 }
}
$('closeControls').addEventListener('click',()=>{keybindSig=''});

/* ---- Смена аккаунта (только аккаунты этого браузера) ---- */
let accountRoster=[],switchTarget='';
function hideSwitchForm(){const f=$('switchForm');if(f)f.style.display='none';$('switchPassword').value='';$('switchError').textContent='';switchTarget=''}
function renderAccountList(){
 const host=$('accountList');if(!host)return;host.replaceChildren();
 const current=(snap?.players.find(q=>q.id===myId)?.name)||'';
 if(!accountRoster.length){const empty=document.createElement('span');empty.className='bindingEmpty';empty.textContent='Из этого браузера больше ни в один аккаунт не выполнялся вход.';host.appendChild(empty);return}
 for(const acc of accountRoster){
  const row=document.createElement('button');row.type='button';
  const name=document.createElement('strong');name.textContent=acc.username;
  const kbd=document.createElement('kbd');kbd.textContent=`ур. ${acc.level} · ${acc.class||'Путник'}`;
  row.append(name,kbd);
  if(acc.username===current){row.disabled=true;kbd.textContent+=' · текущий';row.style.opacity='.65'}
  else row.onclick=()=>{switchTarget=acc.username;$('switchTargetName').textContent=acc.username;$('switchError').textContent='';$('switchForm').style.display='block';$('switchPassword').value='';$('switchPassword').focus()};
  host.appendChild(row);
 }
}
async function loadAccountRoster(){
 try{const response=await fetch('/api/auth/me',{credentials:'same-origin'}),data=await response.json();accountRoster=Array.isArray(data.accounts)?data.accounts:[]}
 catch{accountRoster=[]}
 renderAccountList();
}
$('switchForm').addEventListener('submit',async e=>{
 e.preventDefault();
 if(!switchTarget)return;
 const password=$('switchPassword').value,button=$('switchConfirm');
 button.disabled=true;$('switchError').textContent='';
 try{
  const response=await fetch('/api/auth/switch',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({username:switchTarget,password})});
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.detail||'Не удалось переключить аккаунт.');
  hideSwitchForm();toggleAccounts(false,true);toggleKeybinds(false,true);toggleGameMenu(false);
  snap=null;myId=null;inventorySignature='';marketSignature='';wizardRenderSignature='';forgeRenderSignature='';customSpellLibrarySignature='';customSpellBindingSignature='';customSpellSignature='';keybindSig='';
  if(ws){try{ws.onclose=null;ws.close(1000,'switch')}catch{}}
  $('connection').style.display='none';
  connect(data.username||switchTarget);
  toast(`Аккаунт переключён: ${data.username||switchTarget}`);
 }catch(err){$('switchError').textContent=err.message||'Сервер недоступен.'}
 finally{button.disabled=false}
});
function safeText(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function itemCard(name,detail,rarity='common',button='',count=''){return `<article class="itemCard"><div class="itemMain"><div class="itemName rarity-${rarity}">${safeText(name)}</div><div class="itemDetail">${safeText(detail)}</div></div>${count?`<span class="itemCount">× ${safeText(count)}</span>`:''}${button}</article>`}
let inventorySignature="";function renderInventory(p){let signature=JSON.stringify([p.gear,p.gear_inventory,p.weapons,p.weapon,p.inventory,p.gear_catalog,p.weapon_catalog,p.enchantments,p.upgrades]);if(signature===inventorySignature)return;inventorySignature=signature;let gearList=$('gearInventoryList'),resList=$('resourceInventoryList');if(!gearList||!resList)return;let wc=p.weapon_catalog||{},gc=p.gear_catalog||{};let weapons=(p.weapons||[]).map(id=>{let w=wc[id]||{},kind=w.kind==='bow'?'Дальний бой':w.kind==='staff'?'Магия':'Ближний бой',up=Number(p.upgrades?.weapon?.[id]||0),dmg=Number(w.damage||0)+Number(w.bonus||0)+((w.kind==='staff')?0:up*6),detail=w.kind==='staff'?`${kind} · урон заклинаний +${up*6} за уровень улучшения · сила чар +${Math.round(Number(w.spell_power||0)*100)}%`:`${kind} · урон ${dmg}${w.kind==='bow'?' · усиление стрел':''}`;return {id,name:w.name||weaponNames[id]||id,rarity:w.rarity||'common',equipped:p.weapon===id,detail}});let armor=[p.gear,...(p.gear_inventory||[])].filter((id,i,a)=>id&&a.indexOf(id)===i).map(id=>({id,name:gc[id]?.name||gearNames[id]||id,rarity:gc[id]?.rarity||'common',equipped:p.gear===id,detail:`Защита ${gc[id]?.defense??gearDefense[id]??0} · ${gc[id]?.lore||'Броня следопыта'}`}));let rows=[...weapons.map(it=>{let action=it.equipped?'Надето':`Надеть`;return itemCard(it.name,it.detail,it.rarity,`<button data-inv-equip-weapon="${safeText(it.id)}" ${it.equipped?'disabled':''}>${action}</button>`,it.equipped?'Экипировано':'') }),...armor.map(it=>itemCard(it.name,it.detail,it.rarity,`<button data-inv-equip-gear="${safeText(it.id)}" ${it.equipped?'disabled':''}>${it.equipped?'Надето':'Надеть'}</button>`,it.equipped?'Экипировано':''))];gearList.innerHTML=rows.length?rows.join(''):'<div class="emptyInventory">Пока нет снаряжения. Ищи трофеи в лесу.</div>';let inv=p.inventory||{},res=Object.keys(resourceNames).filter(k=>Number(inv[k]||0)>0);resList.innerHTML=res.length?res.map(k=>itemCard(resourceNames[k],k==='potion'?'Восстанавливает здоровье':k==='arrows'?'Боеприпас для лука':'Материал для ремесла',k==='crystal'||k==='shard'?'rare':'common','',inv[k])).join(''):'<div class="emptyInventory">Рюкзак пуст. Собирай ресурсы клавишей E.</div>';let used=(p.weapons||[]).length+armor.length+res.reduce((n,k)=>n+(inv[k]>0?1:0),0);$('inventoryMeta').textContent=`${used} типов предметов · ${p.gold||0} монет · предметы сохраняются за персонажем`;}
let marketSignature="";const resourceSellNames={wood:'Древесина',herb:'Лунная трава',ore:'Болотная руда',hide:'Шкура',slime:'Слизь',crystal:'Эхо-кристалл',shard:'Осколок разлома',potion:'Настойка',arrows:'Стрела'};
function renderMarket(p){if(!$('marketOverlay'))return;let signature=JSON.stringify([p.gold,p.inventory,p.weapons,p.weapon,p.gear,p.gear_inventory,p.shop_catalog,p.enchantments,p.region]);if(signature===marketSignature)return;marketSignature=signature;let offers=Object.entries(p.shop_catalog||{});$('marketBuyGrid').innerHTML=offers.map(([id,o])=>`<article class="marketLine"><div><strong>${safeText(o.name)}</strong><small>${safeText(o.description)} · ${o.price} монет</small></div><button class="marketBuy" data-market-buy="${safeText(id)}" ${p.gold<o.price?'disabled':''}>Купить</button></article>`).join('')||'<p class="marketNote">Лавка временно закрыта.</p>';let inv=p.inventory||{},sell=[];for(const [id,name] of Object.entries(resourceSellNames)){let n=Number(inv[id]||0);if(n>0)sell.push(`<article class="marketLine"><div><strong>${name} × ${n}</strong><small>${(p.sell_prices||{})[id]||0} монет за штуку</small></div><button class="marketSell" data-market-sell="${safeText(id)}" data-market-type="resource">Продать 1</button><button class="marketSell" data-market-sell="${safeText(id)}" data-market-type="resource" data-market-count="${n}">Продать всё</button></article>`)}const wc=p.weapon_catalog||{},gc=p.gear_catalog||{};for(const id of p.weapons||[]){if(id===p.weapon)continue;sell.push(`<article class="marketLine"><div><strong>${safeText(wc[id]?.name||id)}</strong><small>Оружие · ${p.weapon_sell_prices?.[id]||0} монет</small></div><button class="marketSell" data-market-sell="${safeText(id)}" data-market-type="weapon">Продать</button></article>`)}for(const id of p.gear_inventory||[]){sell.push(`<article class="marketLine"><div><strong>${safeText(gc[id]?.name||id)}</strong><small>Броня · ${p.gear_sell_prices?.[id]||0} монет</small></div><button class="marketSell" data-market-sell="${safeText(id)}" data-market-type="gear">Продать</button></article>`)}$('marketSellGrid').innerHTML=sell.join('')||'<p class="marketNote">Пока нечего продавать. Добывай ресурсы или охоться на монстров.</p>';}
function stationLine(title,detail,button,disabled=false){return `<article class="stationLine"><div><strong>${safeText(title)}</strong><small>${safeText(detail)}</small></div>${button?`<button ${disabled?'disabled':''}>${button}</button>`:''}</article>`}
let wizardRenderSignature="",forgeRenderSignature="";
function renderWizard(p){if(!p)return;const signature=JSON.stringify([p.gold,p.inventory,p.weapons,p.weapon,p.gear,p.gear_inventory,p.enchantments,p.enchant_catalog,p.spells_unlocked,p.magic_mana_spent,p.mana_growth,p.mana_growth_next]);if(signature===wizardRenderSignature)return;wizardRenderSignature=signature;let spent=Number(p.magic_mana_spent||0),unlocked=new Set(p.spells_unlocked||[]);$('wizardProgress').textContent=`Потрачено маны: ${spent}. Навсегда добавлено к максимуму: +${Number(p.mana_growth||0)}. Следующий +1 — при суммарном расходе ${p.mana_growth_next?`${p.mana_growth_next} маны`:'достигнут предел'}.`;
let owns=(p.weapons||[]).includes('apprentice_staff'),price=p.shop_catalog?.apprentice_staff?.price||185;
$('wizardStaff').innerHTML=stationLine('Посох ученика',owns?'Уже куплен · экипируй в рюкзаке · сила заклинаний +12%':`Первый посох · ${price} монет · сила заклинаний +12%`,'Купить посох',owns||p.gold<price).replace('<button ','<button data-wizard-staff="1" ');
const oldW=$('wizardWeaponSelect')?.value||p.weapon,oldG=$('wizardGearSelect')?.value||p.gear;const weaponIds=[...new Set(p.weapons||[])],gearIds=[...new Set([p.gear,...(p.gear_inventory||[])].filter(Boolean))];const makeOptions=(ids,selected,catalog)=>ids.map(id=>`<option value="${safeText(id)}" ${id===selected?'selected':''}>${safeText(catalog[id]?.name||id)}${id===(p.weapon||p.gear)?' · надето':''}</option>`).join('');
$('wizardEnchantGrid').innerHTML=`<div class="stationLine"><div><strong>Предмет для зачарования</strong><small>Можно выбрать оружие или броню из рюкзака</small></div><div class="enchantTargetSelects"><select id="wizardWeaponSelect" aria-label="Оружие для зачарования">${makeOptions(weaponIds,weaponIds.includes(oldW)?oldW:p.weapon,p.weapon_catalog||{})}</select><select id="wizardGearSelect" aria-label="Броня для зачарования">${makeOptions(gearIds,gearIds.includes(oldG)?oldG:p.gear,p.gear_catalog||{})}</select></div></div>`+Object.entries(p.enchant_catalog||{}).map(([id,e])=>{let target=e.target==='weapon'?'weapon':'gear',item=target==='weapon'?($('wizardWeaponSelect')?.value||p.weapon):($('wizardGearSelect')?.value||p.gear),lvl=Number(p.enchantments?.[target]?.[item]?.[id]||0),cost=70+lvl*85,crystals=1+lvl,enough=p.gold>=cost&&Number(p.inventory?.crystal||0)>=crystals;return stationLine(`${e.name} · ${e.target==='weapon'?(p.weapon_catalog?.[item]?.name||item):(p.gear_catalog?.[item]?.name||item)}`,`${e.description} · уровень ${lvl}/3 · ${cost} монет и ${crystals} эхо-кристалл(а)`, 'Наложить',lvl>=3||!enough).replace('<button ','<button data-wizard-enchant="'+safeText(id)+'" data-enchant-target="'+target+'" ')}).join('');let spells=p.spell_catalog||{},locked=Object.entries(spells).filter(([id])=>!unlocked.has(id));$('wizardSpellGrid').innerHTML=locked.length?locked.map(([id,sp])=>stationLine(sp.name,`Уровень ${sp.unlock_level} и расход маны ${sp.unlock_spent} · стоимость ${sp.mana} маны`,'',true)).join(''):'<p class="stationNote">Все доступные заклинания уже открыты.</p>'}
function renderForge(p){if(!p)return;const signature=JSON.stringify([p.gold,p.inventory,p.weapons,p.weapon,p.gear,p.gear_inventory,p.upgrades,$("forgeAnvilScene")?.dataset.pending]);if(signature===forgeRenderSignature)return;forgeRenderSignature=signature;let inv=p.inventory||{},owns=id=>(p.weapons||[]).includes(id),recipes=[['forest_bow','Лук следопыта','8 дерева · 3 шкуры · 2 руды'],['thorn_staff','Посох живых терний','6 дерева · 5 эхо-кристаллов · 4 травы'],['stormbrand','Клинок Грозового кедра','8 руды · 4 кристалла · 3 осколка'],['obsidian_axe','Топор Чёрного стекла','14 руды · 10 кристаллов · 12 осколков · 4 шкуры'],['elder_staff','Посох Первозданного корня','16 дерева · 12 кристаллов · 8 осколков · 6 травы']];$('forgeCraftGrid').innerHTML=recipes.map(([id,name,cost])=>{let enough=id==='forest_bow'?inv.wood>=8&&inv.hide>=3&&inv.ore>=2:id==='thorn_staff'?inv.wood>=6&&inv.crystal>=5&&inv.herb>=4:id==='stormbrand'?inv.ore>=8&&inv.crystal>=4&&inv.shard>=3:id==='obsidian_axe'?inv.ore>=14&&inv.crystal>=10&&inv.shard>=12&&inv.hide>=4:inv.wood>=16&&inv.crystal>=12&&inv.shard>=8&&inv.herb>=6;return stationLine(name,cost,owns(id)?'Изготовлено':'Сковать',owns(id)||!enough).replace('<button ','<button data-forge-craft="'+id+'" ')}).join('');
const oldW=$('forgeWeaponSelect')?.value||p.weapon,oldG=$('forgeGearSelect')?.value||p.gear,weaponIds=[...new Set(p.weapons||[])],gearIds=[...new Set([p.gear,...(p.gear_inventory||[])].filter(Boolean))];const makeOptions=(ids,selected,catalog)=>ids.map(id=>`<option value="${safeText(id)}" ${id===selected?'selected':''}>${safeText(catalog[id]?.name||id)}${id===(p.weapon||p.gear)?' · надето':''}</option>`).join('');const selects=`<div class="stationLine"><div><strong>Выбери предмет</strong><small>Можно улучшать предметы из рюкзака, не только надетые</small></div><div class="enchantTargetSelects"><select id="forgeWeaponSelect" aria-label="Оружие для улучшения">${makeOptions(weaponIds,weaponIds.includes(oldW)?oldW:p.weapon,p.weapon_catalog||{})}</select><select id="forgeGearSelect" aria-label="Броня для улучшения">${makeOptions(gearIds,gearIds.includes(oldG)?oldG:p.gear,p.gear_catalog||{})}</select></div></div>`;
const wlItem=weaponIds.includes(oldW)?oldW:p.weapon,glItem=gearIds.includes(oldG)?oldG:p.gear,wl=Number(p.upgrades?.weapon?.[wlItem]||0),gl=Number(p.upgrades?.gear?.[glItem]||0),wc=75+wl*55,gc=65+gl*50,wo=2+wl,go=2+gl,wcst=wl<2?0:1+Math.floor(wl/2),gcst=gl<2?0:1+Math.floor(gl/2),chances=[100,90,80,70,60],wchance=chances[Math.min(4,wl)],gchance=chances[Math.min(4,gl)],pending=$('forgeAnvilScene')?.dataset.pending==='1',weaponKind=p.weapon_catalog?.[wlItem]?.kind,weaponBenefit=weaponKind==='staff'?'+6 к урону заклинаний при успехе':weaponKind==='bow'?'+6 к урону стрел при успехе':'+6 к урону ближней атаки при успехе';$('forgeUpgradeGrid').innerHTML=selects+stationLine(`Оружие · ${p.weapon_catalog?.[wlItem]?.name||wlItem} · +${wl}/5`,`${weaponBenefit} · шанс ${wchance}% · стоимость: ${wc} монет, ${wo} руды, ${wcst} кристаллов. Стоимость списывается при каждой попытке.`,`Улучшить оружие · ${wchance}%`,pending||wl>=5||p.gold<wc||inv.ore<wo||inv.crystal<wcst).replace('<button ','<button data-forge-upgrade="weapon" data-upgrade-target="weapon" ')+stationLine(`Броня · ${p.gear_catalog?.[glItem]?.name||glItem} · +${gl}/5`,`+3 к защите при успехе · шанс ${gchance}% · стоимость: ${gc} монет, ${go} руды, ${gcst} кристаллов. Стоимость списывается при каждой попытке.`,`Улучшить броню · ${gchance}%`,pending||gl>=5||p.gold<gc||inv.ore<go||inv.crystal<gcst).replace('<button ','<button data-forge-upgrade="armor" data-upgrade-target="gear" ')}

function openWizard(){let p=me();if(!p)return;$('wizardOverlay').style.display='flex';wizardRenderSignature='';renderWizard(p);$('closeWizard').focus()}
function openForge(){let p=me();if(!p)return;$('forgeOverlay').style.display='flex';forgeRenderSignature='';renderForge(p);$('closeForge').focus()}
function closeStation(id){if($(id))$(id).style.display='none'}
$('wizardButton').onclick=openWizard;$('forgeButton').onclick=openForge;$('closeWizard').onclick=()=>closeStation('wizardOverlay');$('closeForge').onclick=()=>closeStation('forgeOverlay');
$('wizardOverlay').addEventListener('click',e=>{if(e.target===$('wizardOverlay'))closeStation('wizardOverlay');if(e.target.closest('[data-wizard-staff]')){send({type:'wizard_action',action:'buy_staff'});toast('Запрос волшебнику отправлен')};let b=e.target.closest('[data-wizard-enchant]');if(b&&!b.disabled){let target=b.dataset.enchantTarget,item=target==='weapon'?$('wizardWeaponSelect')?.value:$('wizardGearSelect')?.value;send({type:'wizard_action',action:'enchant',id:b.dataset.wizardEnchant,item_id:item});toast('Запрос на зачарование отправлен')}});
$('forgeOverlay').addEventListener('click',e=>{if(e.target===$('forgeOverlay'))closeStation('forgeOverlay');let c=e.target.closest('[data-forge-craft]'),u=e.target.closest('[data-forge-upgrade]');if(c&&!c.disabled){send({type:'forge_action',action:'craft',id:c.dataset.forgeCraft});toast('Запрос кузнецу отправлен')}if(u&&!u.disabled){let scene=$('forgeAnvilScene');if(scene){scene.dataset.pending='1';scene.classList.remove('forge-success','forge-fail','hammering');void scene.offsetWidth;scene.classList.add('hammering');setTimeout(()=>{if(scene.dataset.pending==='1'){scene.dataset.pending='0';scene.classList.remove('hammering');renderForge(me())}},2200)}u.disabled=true;let target=u.dataset.upgradeTarget,item=target==='weapon'?$('forgeWeaponSelect')?.value:$('forgeGearSelect')?.value;send({type:'forge_action',action:'upgrade_'+u.dataset.forgeUpgrade,item_id:item});toast('Запрос отправлен в кузницу')}});
$('wizardOverlay').addEventListener('change',e=>{if(e.target.matches('#wizardWeaponSelect,#wizardGearSelect')){wizardRenderSignature='';renderWizard(me())}});
$('forgeOverlay').addEventListener('change',e=>{if(e.target.matches('#forgeWeaponSelect,#forgeGearSelect')){forgeRenderSignature='';renderForge(me())}});
function openMarket(){let el=$('marketOverlay');if(!el)return;el.style.display='flex';marketSignature='';let p=me();if(p)renderMarket(p);setMarketTab('buy');$('closeMarket').focus()}function closeMarket(){if($('marketOverlay'))$('marketOverlay').style.display='none'}function setMarketTab(tab){document.querySelectorAll('[data-market-tab]').forEach(b=>b.classList.toggle('active',b.dataset.marketTab===tab));document.querySelectorAll('[data-market-pane]').forEach(p=>p.classList.toggle('active',p.dataset.marketPane===tab))}$('marketButton').onclick=openMarket;$('closeMarket').onclick=closeMarket;$('marketOverlay').addEventListener('click',e=>{if(e.target===$('marketOverlay'))closeMarket();let buy=e.target.closest('[data-market-buy]'),sell=e.target.closest('[data-market-sell]'),ench=e.target.closest('[data-enchant]');if(buy)send({type:'shop_action',action:'buy',id:buy.dataset.marketBuy});if(sell)send({type:'shop_action',action:'sell',id:sell.dataset.marketSell,item_type:sell.dataset.marketType,count:Number(sell.dataset.marketCount||1)});if(ench)send({type:'shop_action',action:'enchant',id:ench.dataset.enchant})});document.querySelectorAll('[data-market-tab]').forEach(b=>b.addEventListener('click',()=>setMarketTab(b.dataset.marketTab)));
const spellIds=['fireball','lightning','heal','thorns','ice_lance','arcane_burst','meteor','frost_nova','shadow_bolt'];
const spellKeyStore='echo-spell-keys-v2';
const defaultSpellCodes=['Digit1','Digit2','Digit3','Digit4','Digit5','Digit6','Digit7','Digit8','Digit9'];
let spellKeyCodes=(()=>{try{let saved=JSON.parse(localStorage.getItem(spellKeyStore)||'null');return Array.isArray(saved)&&saved.length===spellIds.length?saved:defaultSpellCodes.slice()}catch{return defaultSpellCodes.slice()}})();
let spellKeyCodeToId={}; let customSpellKeys={},customSpellSignature="";
function keyLabel(code){return code?.startsWith('Digit')?code.slice(5):code?.startsWith('Numpad')?code.slice(6):code?.replace('Key','')||'?'}
/* Base spells sit on Shift + digits: plain 1–9 feed the inventory hotbar. */
function spellKeyLabel(code){return `⇧${keyLabel(code)}`}
function syncSpellKeys(){spellKeyCodeToId={};spellIds.forEach((id,i)=>{spellKeyCodeToId[spellKeyCodes[i]]=id;let b=document.querySelector(`[data-spell="${id}"]`);if(b){let base=b.dataset.label||id;b.innerHTML=`<span class="spellKey">${spellKeyLabel(spellKeyCodes[i])}</span><span class="spellIcon">${b.dataset.icon||'✦'}</span><span class="spellTitle">${base}</span><span class="spellMeta">ур. 1 · готово</span><i class="spellCooldown"></i>`}})}
function syncCustomSpellButtons(p){if(!p)return;let bar=$('spellBar');if(!bar)return;let customs=p.custom_spells||[],signature=JSON.stringify(customs.map(x=>[x.id,x.name,x.key]));if(signature===customSpellSignature)return;customSpellSignature=signature;bar.querySelectorAll('[data-custom-spell]').forEach(b=>b.remove());customSpellKeys={};customs.forEach(sp=>{let id=sp.id||sp.spell_id||sp.custom_id;if(!id)return;let key=sp.key||'F1';customSpellKeys[id]=key;let b=document.createElement('button');b.type='button';b.className='spellBtn customCrafted';b.dataset.customSpell=id;b.title=`${sp.name} · ${sp.kind||'Аркана'} · ${sp.mana} маны`;b.innerHTML=`<span class="spellKey">${key==='Digit0'?'0':key}</span><span class="spellIcon">✧</span><span class="spellTitle"></span><span class="spellMeta"></span><i class="spellCooldown"></i>`;b.querySelector('.spellTitle').textContent=sp.name;b.dataset.label=sp.name;b.onclick=()=>castSpell(id);bar.appendChild(b)})}
let customSpellBindingSignature="",customSpellLibrarySignature="",pendingSpellBinding="";
function displaySpellKey(key){return key==='Digit0'?'0':key||'—'}
function renderCustomSpellBindings(p){const host=$('customSpellKeyList');if(!host||!p)return;const spells=p.custom_spells||[],signature=JSON.stringify([spells.map(x=>[x.id||x.spell_id,x.name,x.key]),pendingSpellBinding]);if(signature===customSpellBindingSignature)return;customSpellBindingSignature=signature;host.replaceChildren();if(!spells.length){const empty=document.createElement('span');empty.className='bindingEmpty';empty.textContent='Созданные заклинания появятся здесь.';host.appendChild(empty);return}for(const sp of spells){const id=sp.id||sp.spell_id||sp.custom_id;if(!id)continue;const row=document.createElement('div');row.className='customSpellKeyRow';const name=document.createElement('span');name.className='customSpellKeyName';name.textContent=sp.name||'Заклинание';const button=document.createElement('button');button.type='button';button.className='customSpellKeyButton'+(pendingSpellBinding===id?' is-binding':'');button.dataset.bindCustomSpell=id;button.textContent=pendingSpellBinding===id?'Нажмите клавишу':displaySpellKey(sp.key);button.setAttribute('aria-label',`Назначить клавишу для ${sp.name||'заклинания'}`);button.addEventListener('click',()=>{pendingSpellBinding=id;$('customSpellBindingHint').textContent='Нажми F1–F12 или 0. Esc отменяет назначение.';customSpellBindingSignature='';renderCustomSpellBindings(me())});row.append(name,button);host.appendChild(row)}}
function renderCustomSpellLibrary(p){const host=$('customSpellLibraryList'),count=$('customSpellCount');if(!host||!p)return;const spells=p.custom_spells||[],catalog=p.spell_catalog||{};if(count)count.textContent=`${spells.length} / 24`;const sig=JSON.stringify(spells.map(sp=>[sp.id||sp.spell_id,sp.name,sp.key,sp.kind,sp.mana,sp.damage,sp.heal,sp.radius,sp.cooldown,sp.rarity,sp.source]));if(sig===customSpellLibrarySignature)return;customSpellLibrarySignature=sig;host.replaceChildren();if(!spells.length){const empty=document.createElement('span');empty.className='bindingEmpty';empty.textContent='Создай первое заклинание в мастерской.';host.appendChild(empty);return}for(const sp of spells){const id=sp.id||sp.spell_id||sp.custom_id;if(!id)continue;const card=document.createElement('article');card.className='customSpellCardMini';const title=document.createElement('div');title.className='customSpellMiniTitle';const name=document.createElement('strong');name.textContent=sp.name||'Заклинание';const key=document.createElement('span');key.className='customSpellMiniKey';key.textContent=displaySpellKey(sp.key);title.append(name,key);const meta=document.createElement('div');meta.className='customSpellMiniMeta';const power=sp.heal??sp.damage??0;meta.textContent=`${sp.kind||'Аркана'} · ${sp.heal?'лечение':'урон'} ${power} · область ${sp.radius||0} · мана ${sp.mana||0} · перезарядка ${Number(sp.cooldown||0).toFixed(1)} с · редкость ${sp.rarity||1}/5`;const source=document.createElement('div');source.className='customSpellMiniMeta customSpellMiniSource';const parts=(sp.source||[]).map(src=>catalog[src]?.name||src);source.textContent=parts.length?`Рецепт: ${parts.join(' + ')}`:'Созданное заклинание';const actions=document.createElement('div');actions.className='customSpellMiniActions';const bind=document.createElement('button');bind.type='button';bind.textContent='Назначить клавишу';bind.onclick=()=>{pendingSpellBinding=id;$('customSpellBindingHint').textContent='Нажми F1–F12 или 0. Esc отменяет назначение.';customSpellBindingSignature='';renderCustomSpellBindings(me())};const remove=document.createElement('button');remove.type='button';remove.className='deleteCustomSpell';remove.textContent='Удалить';remove.onclick=()=>{if(!window.confirm(`Удалить заклинание «${sp.name||'Заклинание'}»? Это действие нельзя отменить.`))return;send({type:'delete_custom_spell',spell:id});customSpellLibrarySignature='';customSpellBindingSignature=''};actions.append(bind,remove);card.append(title,meta,source,actions);host.appendChild(card)}}
function normalizeCustomKey(key){if(/^F(?:[1-9]|1[0-2])$/.test(key))return key;if(key==='Digit0'||key==='0')return'Digit0';return''}
function castCustomSpellByKey(code){const p=me();if(!p)return false;const spell=(p.custom_spells||[]).find(x=>normalizeCustomKey(x.key)===code);const id=spell&&(spell.id||spell.spell_id||spell.custom_id);if(!id)return false;castSpell(id);return true}
document.addEventListener('keydown',e=>{if(!pendingSpellBinding)return;const target=e.target;if(target&&(target.matches('input,textarea,select')||target.isContentEditable))return;if(e.key==='Escape'){pendingSpellBinding='';customSpellBindingSignature='';$('customSpellBindingHint').textContent='Назначение отменено. Доступны F1–F12 и 0.';renderCustomSpellBindings(me());e.preventDefault();e.stopPropagation();return}const key=normalizeCustomKey(e.code);if(!key){$('customSpellBindingHint').textContent='Эта клавиша недоступна. Нажми F1–F12 или 0.';e.preventDefault();e.stopPropagation();return}const id=pendingSpellBinding;pendingSpellBinding='';send({type:'bind_custom_spell',spell:id,key});$('customSpellBindingHint').textContent='Сохраняю назначение…';customSpellBindingSignature='';e.preventDefault();e.stopPropagation()},true);
document.addEventListener('keydown',e=>{if(!pendingAbilityBinding)return;const target=e.target;if(target&&(target.matches('input,textarea,select')||target.isContentEditable))return;if(e.key==='Escape'){pendingAbilityBinding='';$('abilityBindingHint').textContent='Назначение отменено.';updateActionPanels(me());e.preventDefault();e.stopPropagation();return}const code=e.code;if(!validAbilityBinding(code)){$('abilityBindingHint').textContent='Эта клавиша занята или недоступна. Выбери букву A–Z, кроме служебных.';e.preventDefault();e.stopPropagation();return}const id=pendingAbilityBinding;Object.keys(abilityKeys).forEach(k=>{if(k!==id&&abilityKeys[k]===code)delete abilityKeys[k]});abilityKeys[id]=code;saveAbilityKeys();pendingAbilityBinding='';updateActionPanels(me());toast('Клавиша способности сохранена');e.preventDefault();e.stopPropagation()},true);
document.addEventListener('click',e=>{
 const choose=e.target.closest('[data-choose-class]');
 if(choose&&!choose.disabled){const id=choose.dataset.chooseClass;classChoicePending=true;document.querySelectorAll('[data-choose-class]').forEach(b=>b.disabled=true);choose.textContent='Выбираю…';send({type:'choose_class',class:id});setTimeout(()=>{if(classChoicePending){classChoicePending=false;renderClassChoices()}},2600);return}
 const ab=e.target.closest('[data-ability]');
 if(ab&&!ab.disabled){useAbility(ab.dataset.ability);return}
 const bind=e.target.closest('[data-bind-ability]');
 if(bind){pendingAbilityBinding=bind.dataset.bindAbility;updateActionPanels(me());return}
 const reset=e.target.closest('[data-reset-abilities]');
 if(reset){abilityKeys={};saveAbilityKeys();pendingAbilityBinding='';updateActionPanels(me());toast('Клавиши способностей сброшены к стандартным');return}
});
document.addEventListener('pointerover',e=>{const ab=e.target.closest?.('[data-ability]');if(ab)hoverAbilityId=ab.dataset.ability});
document.addEventListener('pointerout',e=>{const ab=e.target.closest?.('[data-ability]');if(ab&&hoverAbilityId===ab.dataset.ability)hoverAbilityId=''});
$('classLater').onclick=hideClassOffer;$('classOverlay').addEventListener('click',e=>{if(e.target===$('classOverlay'))hideClassOffer()});
function refreshCustomSpellForge(){const p=me();if(!p)return;const cat=p.spell_catalog||{},unlocked=new Set(p.spells_unlocked||[]),entries=Object.entries(cat).filter(([id])=>unlocked.has(id));for(const sel of [$('spellPartA'),$('spellPartB')]){if(!sel)continue;const prev=sel.value;sel.innerHTML='';entries.forEach(([id,sp])=>{let o=document.createElement('option');o.value=id;o.textContent=sp.name;sel.appendChild(o)});if(entries.some(([id])=>id===prev))sel.value=prev}updateSpellPreview()}
function updateSpellPreview(){const p=me(),a=$('spellPartA')?.value,b=$('spellPartB')?.value,name=$('customSpellName')?.value.trim()||'';const out=$('spellRecipePreview'),btn=$('createSpellButton');if(!p||!out)return;let cat=p.spell_catalog||{},sa=cat[a],sb=cat[b];if(!sa||!sb){out.textContent='Пока не хватает двух изученных заклинаний.';if(btn)btn.disabled=true;return}let words=name.toLowerCase().match(/[а-яёa-z]+/g)||[],lex={огонь:['Огонь',3],пламя:['Огонь',4],жар:['Огонь',2],лед:['Лёд',3],лёд:['Лёд',3],иней:['Лёд',3],мороз:['Лёд',4],молния:['Молния',4],гром:['Молния',3],шторм:['Молния',3],тень:['Тень',3],мрак:['Тень',4],ночь:['Тень',2],пустота:['Тень',4],исцеление:['Исцеление',4],лечение:['Исцеление',4],свет:['Исцеление',2],терн:['Терни',3],шип:['Терни',3],взрыв:['Всплеск',4],звезда:['Звёзды',3],метеор:['Звёзды',4],яд:['Яд',3],кислота:['Яд',3],эхо:['Эхо',2]};let scores={};words.forEach(w=>Object.entries(lex).forEach(([stem,v])=>{if(w===stem||(stem.length>=4&&w.startsWith(stem.slice(0,Math.max(4,stem.length-2)))))scores[v[0]]=(scores[v[0]]||0)+v[1]}));let kind=Object.keys(scores).sort((x,y)=>scores[y]-scores[x])[0]||'Аркана',rarity=Math.min(5,Math.max(1,words.length+(name.length>=12?1:0))),power=Object.values(scores).reduce((x,y)=>x+y,0);let dmg=Math.max(12,Math.min(180,Math.round(((sa.damage||sa.heal||22)+(sb.damage||sb.heal||22))*.42*(.78+rarity*.12+Math.min(power,8)*.025)))),radius=Math.max(52,Math.min(230,Math.round(((sa.radius||90)+(sb.radius||90))*.36*(.82+rarity*.09+Math.min(power,8)*.025)))),mana=Math.max(12,Math.min(100,Math.round(((sa.mana||20)+(sb.mana||20))*.32*(.85+rarity*.14))));out.innerHTML='';let lines=[['Тип: ',kind,' · редкость имени: ',rarity,'/5'],['Сила: ',dmg,' · область: ',radius,' · мана: ',mana]];lines.forEach(parts=>{let div=document.createElement('div');parts.forEach(part=>{if(typeof part==='number')div.append(document.createTextNode(String(part)));else if(part===kind){let b=document.createElement('b');b.textContent=part;div.appendChild(b)}else div.append(document.createTextNode(part))});out.appendChild(div)});if(btn)btn.disabled=!(name.length>=3&&name.length<=28&&a!==b)}
function openSpellForge(){refreshCustomSpellForge();$('customSpellOverlay').style.display='flex'}$('openSpellForge').onclick=openSpellForge;$('closeSpellForge').onclick=()=>$('customSpellOverlay').style.display='none';$('customSpellOverlay').addEventListener('click',e=>{if(e.target===$('customSpellOverlay'))$('customSpellOverlay').style.display='none'});$('spellPartA').addEventListener('change',updateSpellPreview);$('spellPartB').addEventListener('change',updateSpellPreview);$('customSpellName').addEventListener('input',updateSpellPreview);$('createSpellButton').onclick=()=>{let a=$('spellPartA').value,b=$('spellPartB').value,name=$('customSpellName').value.trim();if(!a||!b||!name)return;send({type:'create_spell',a,b,name,key:$('customSpellKey').value});$('customSpellOverlay').style.display='none';$('customSpellName').value=''};
function remapSpellKeys(){let used=new Set(),i=0;for(;i<spellIds.length;i++){let accepted=false;while(!accepted){let raw=prompt(`Заклинание ${i+1} из ${spellIds.length}. Введите цифру 0–9 — в бою она нажимается с Shift.`,keyLabel(spellKeyCodes[i]));if(raw===null)break;let n=raw.trim();if(!/^[0-9]$/.test(n)){toast('Для заклинаний доступны цифры 0–9 (в бою — с Shift)');continue}let code='Digit'+n;if(used.has(code)){toast('Эта клавиша уже назначена другому заклинанию');continue}used.add(code);spellKeyCodes[i]=code;accepted=true}if(!accepted)break}for(let j=i;j<spellIds.length;j++){let old=spellKeyCodes[j];if(!used.has(old)){used.add(old);continue}let free=Array.from({length:10},(_,n)=>'Digit'+n).find(code=>!used.has(code));if(free){spellKeyCodes[j]=free;used.add(free)}}localStorage.setItem(spellKeyStore,JSON.stringify(spellKeyCodes));syncSpellKeys();toast('Клавиши заклинаний сохранены')}
function updateSpellBar(p){if(!p)return;const unlocked=new Set(p.spells_unlocked||[]),levels=p.spell_levels||{},uses=p.spell_uses||{},cooldowns=p.spell_cooldowns||{},catalog=p.spell_catalog||{},spellAllowed=!p.class||(p.class==='mage'&&p.weapon_kind==='staff');for(const b of document.querySelectorAll('#spellBar [data-spell],#spellBar [data-custom-spell]')){const id=b.dataset.spell||b.dataset.customSpell,spec=catalog[id]||{},isUnlocked=unlocked.has(id),level=levels[id]||1,used=Number(uses[id]||0),cd=cooldowns[id]||{},remain=Number(cd.remaining||0),total=Number(cd.total||spec.cooldown||0),mana=Number(spec.mana||0),low=(p.mana||0)<mana;b.disabled=!spellAllowed||!isUnlocked||remain>0||low;b.classList.toggle('is-locked',!isUnlocked);b.classList.toggle('is-cooling',remain>0);b.classList.toggle('no-mana',low);b.classList.toggle('incompatible-spell',!spellAllowed);b.style.setProperty('--cd-width',`${total>0?Math.max(0,Math.min(1,remain/total))*100:0}%`);const meta=b.querySelector('.spellMeta');if(meta)meta.textContent=!spellAllowed?(p.class==='mage'?'Нужен посох':'Только класс «Маг»'):!isUnlocked?`Нужно: уровень ${spec.unlock_level||1}`:remain>0?`Перезарядка ${remain.toFixed(1)} с · ур. ${level}`:low?`Не хватает ${mana} маны`: `Уровень ${level} · применено ${used}`;b.title=`${spec.name||id} · ${mana} маны · перезарядка ${Number(spec.cooldown||0).toFixed(1)} с · личный уровень ${level}${!spellAllowed?' · недоступно: '+(p.class==='mage'?'нужен посох':'класс не Маг'):''}`}}


function toggleControls(open){const el=$('controlsOverlay');el.style.display=(open??el.style.display!=='flex')?'flex':'none';if(el.style.display==='flex')$('closeControls').focus()}$('controlsButton').onclick=()=>toggleControls(true);$('spellLibraryButton').onclick=()=>{toggleControls(true);requestAnimationFrame(()=>$('customSpellLibraryList').scrollIntoView({behavior:'smooth',block:'center'}))};$('closeControls').onclick=()=>toggleControls(false);$('controlsOverlay').addEventListener('click',e=>{if(e.target===$('controlsOverlay'))toggleControls(false)});document.querySelectorAll('.controlActions:not(.controlExtraActions) .actionBtn,[data-spell]').forEach(b=>b.addEventListener('click',()=>setTimeout(()=>toggleControls(false),80)));document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('controlsOverlay').style.display==='flex')toggleControls(false)});
function pointerWorld(){let r=canvas.getBoundingClientRect();return {x:cam.x+(mouse.x-r.width/2),y:cam.y+(mouse.y-r.height/2)}}
function castSpell(id){let p=me();if(!p)return;if(window.heroGesture)heroGesture('cast');let t=hasPointerAim?pointerWorld():{x:p.x+aim.x*180,y:p.y+aim.y*180},dx=t.x-p.x,dy=t.y-p.y;send({type:'spell',spell:id,aim_x:dx,aim_y:dy,target_x:t.x,target_y:t.y})}document.querySelectorAll('[data-spell]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.spell)castSpell(b.dataset.spell);else remapSpellKeys()}));$('spellSettings').onclick=remapSpellKeys;syncSpellKeys();function toggleGuide(open){const el=$('guideOverlay');el.style.display=(open??el.style.display!=='flex')?'flex':'none';if(el.style.display==='flex')$('closeGuide').focus()}$('guideButton').onclick=()=>toggleGuide(true);$('closeGuide').onclick=()=>toggleGuide(false);$('guideOverlay').addEventListener('click',e=>{if(e.target===$('guideOverlay'))toggleGuide(false)});
function openInventory(){if(!$('invOverlay'))return;$('invOverlay').style.display='flex';document.querySelectorAll('[data-inv-tab]').forEach(x=>x.classList.toggle('active',x.dataset.invTab==='all'));document.querySelectorAll('[data-inv-section]').forEach(x=>x.style.display='block');inventorySignature='';let p=me();if(p)renderInventory(p);$('closeInventory').focus()}
function closeInventory(){if($('invOverlay'))$('invOverlay').style.display='none'}
const QUEST_STATUS_LABEL={active:'В работе',ongoing:'В работе',ready:'Готово к сдаче',short:'Нужны материалы',done:'Выполнено'};
const QUEST_MOB_NAMES={slime:'Моховые слизни',wolf:'Туманные волки',boar:'Топкие вепри',ashguard:'Стражи руин',colossus:'Пепельный колосс',frost_wyrm:'Ледяные змеи',echo_dragon:'Дракон Пустого Эха',rift_knight:'Рыцари разлома',void_wraith:'Призраки Бездны',obsidian_sentinel:'Стражи чёрного стекла',starseer:'Звёздочёты',ancient_warden:'Хранитель сада'};
const QUEST_RESOURCE_NAMES={herb:'Лунная трава',ore:'Болотная руда',crystal:'Эхо-кристаллы',shard:'Осколки разлома',wood:'Древесина'};
function questObjectiveName(objective){
 const key=objective?.key||'';
 if(objective?.kind==='kill')return QUEST_MOB_NAMES[key]||mobNames[key]||key;
 return QUEST_RESOURCE_NAMES[key]||nodeNames[key]||key;
}
function questObjectiveDone(objective){return Number(objective?.have||0)>=Number(objective?.need||0)}
function journalOf(p){return Array.isArray(p?.journal)?p.journal:[]}
// The server decides the default (ready → in work → nothing) and remembers a pin.
function trackedQuestEntry(p){const journal=journalOf(p);if(!journal.length)return null;const pinned=p?.tracked_quest;return journal.find(q=>q.id===pinned)||journal.find(q=>q.status==='ready')||journal.find(q=>q.status==='short')||journal.find(q=>q.status==='active'||q.status==='ongoing')||null}
function questProgressMarkup(quest){
 return (quest.objectives||[]).map(o=>{const need=Math.max(1,Number(o.need||1)),have=Math.min(Number(o.have||0),need),pct=Math.round(100*have/need);
  return `<div class="qObjective"><span>${safeText(questObjectiveName(o))}</span><b class="qCount">${have} / ${need}</b></div><div class="questTrack"><i style="width:${pct}%"></i></div>`}).join('');
}
function questRewardText(quest){
 const reward=quest.reward||{},parts=[];
 if(reward.gold)parts.push(`${reward.gold} монет`);
 if(reward.xp)parts.push(`${reward.xp} опыта`);
 if(reward.points)parts.push('+1 очко развития');
 for(const item of reward.items||[]){
  const label=item.type==='potion'?'настойка':item.type==='gear'?(gearNames[item.id]||item.id):(weaponNames[item.id]||item.id);
  parts.push(`${label}${Number(item.count)>1?` ×${item.count}`:''}`);
 }
 return parts.join(' · ');
}
function updateQuestTracker(p){
 const panel=$('questPanel');if(!panel)return;
 const tracked=trackedQuestEntry(p),titleEl=$('questName'),stageEl=$('questStageLabel'),statusEl=$('questStatus'),box=$('questObjectives');
 panel.classList.remove('ready','done','empty');
 if(!titleEl||!box)return;
 if(!tracked){
  titleEl.textContent='Поручений нет';
  if(stageEl)stageEl.textContent='—';
  box.innerHTML='<div class="qEmpty">Поговори с Хранителем истории в лагере и нажми <kbd>F</kbd>, чтобы принять первое поручение.</div>';
  if(statusEl)statusEl.textContent='Журнал всех поручений: J';
  panel.classList.add('empty');
  return;
 }
 titleEl.textContent=tracked.title;
 if(stageEl)stageEl.textContent=tracked.kind==='story'?`${Number(tracked.stage||0)+1} / ${tracked.total||'?'}`:(tracked.region_name||'');
 box.innerHTML=questProgressMarkup(tracked);
 if(statusEl){
  const where=tracked.region_name?` · ${tracked.region_name}`:'';
  statusEl.textContent=tracked.status==='ready'?`Цели закрыты${where}. Сдай поручение: ${tracked.giver||'Хранитель'} (F).`
   :tracked.status==='short'?`Цели закрыты, но нужны материалы в рюкзаке${where}.`
   :tracked.status==='done'?'Поручение выполнено.'
   :`${QUEST_STATUS_LABEL[tracked.status]||'В работе'}${where}.`;
 }
 panel.classList.add(tracked.status==='ready'?'ready':tracked.status==='done'?'done':'active');
}

/* ── журнал поручений: основная ветка + местные поручения + выбор трекера ── */
let questJournalSignature='';
function questJournalCard(quest,trackedId){
 const done=quest.status==='done',isTracked=quest.id===trackedId;
 const badge=`<span class="qjStatus ${quest.status}">${QUEST_STATUS_LABEL[quest.status]||'В работе'}</span>`;
 const chain=quest.kind==='story'?`<span class="qjChapter">${Number(quest.stage||0)+1} / ${quest.total||'?'}</span>`:'';
 const reward=questRewardText(quest);
 return `<article class="qjCard${done?' isDone':''}${isTracked?' isTracked':''}" data-quest-card="${safeText(quest.id)}">
  <header><div class="qjHead"><b>${safeText(quest.title)}</b>${chain}${badge}</div>
   <button type="button" class="qjTrack" data-quest-track="${safeText(quest.id)}"${done?' disabled':''}>${isTracked?'Отслеживается':'Отслеживать'}</button></header>
  <div class="qjMeta">${safeText(quest.region_name||'')}${quest.giver?` · ${safeText(quest.giver)}`:''}</div>
  <div class="qjObjectives">${questProgressMarkup(quest)}</div>
  <div class="qjReward">Награда: ${safeText(reward||'—')}</div>
 </article>`;
}
function renderQuestJournal(p){
 const host=$('questJournalBody');if(!host||!p)return;
 const journal=journalOf(p),tracked=trackedQuestEntry(p),trackedId=tracked?tracked.id:'';
 const signature=JSON.stringify([journal.map(q=>[q.id,q.status,(q.objectives||[]).map(o=>o.have)]),trackedId]);
 if(signature===questJournalSignature&&host.dataset.ready==='1')return;
 questJournalSignature=signature;host.dataset.ready='1';
 const story=journal.filter(q=>q.kind==='story').sort((a,b)=>Number(a.stage||0)-Number(b.stage||0));
 const side=journal.filter(q=>q.kind==='region');
 const active=journal.filter(q=>q.status!=='done').length,ready=journal.filter(q=>q.status==='ready').length,done=journal.filter(q=>q.status==='done').length;
 $('questJournalStats').innerHTML=`<span>В работе: <b>${active}</b></span><span>Готово к сдаче: <b>${ready}</b></span><span>Выполнено: <b>${done}</b></span>`;
 const section=(title,hint,items)=>`<section class="qjSection"><h3>${title}${hint?`<small>${hint}</small>`:''}</h3>${items.length?items.map(q=>questJournalCard(q,trackedId)).join(''):'<p class="qjEmpty">Пока пусто.</p>'}</section>`;
 host.innerHTML=[
  tracked?`<section class="qjSection qjTrackedSection"><h3>Отслеживается<small>это видно на панели справа сверху</small></h3>${questJournalCard(tracked,trackedId)}</section>`:'',
  section('Основная ветка','принятые и выполненные поручения Хранителя',story),
  section('Побочные поручения','местные дела в девяти землях; их выдаёт местный Хранитель',side),
 ].join('');
}
function openQuestJournal(){
 const el=$('questOverlay');if(!el)return;
 el.style.display='flex';questJournalSignature='';
 const p=me();if(p)renderQuestJournal(p);
 const close=$('closeQuestJournal');if(close)close.focus();
}
function closeQuestJournal(){const el=$('questOverlay');if(el)el.style.display='none'}
function toggleQuestJournal(open){const el=$('questOverlay');if(!el)return;const next=open??el.style.display!=='flex';if(next)openQuestJournal();else closeQuestJournal()}
if($('closeQuestJournal'))$('closeQuestJournal').onclick=closeQuestJournal;
if($('questOpenButton'))$('questOpenButton').onclick=openQuestJournal;
if($('questOverlay'))$('questOverlay').addEventListener('click',e=>{
 if(e.target===$('questOverlay')){closeQuestJournal();return}
 const button=e.target.closest('[data-quest-track]');
 if(!button||button.disabled)return;
 const id=button.dataset.questTrack;if(!id)return;
 send({type:'quest_track',id});
 button.textContent='Отслеживается';
 button.closest('.qjCard')?.classList.add('isTracked');
 toast('Поручение закреплено в трекере');
});
function updateHud(){let p=me();if(!p)return;$('heroName').textContent=`${p.name} · ур. ${p.level}`;$('gold').textContent=`${p.gold} монет`;const hpPct=Math.max(0,Math.min(100,100*p.hp/Math.max(1,p.max_hp))),stamPct=Math.max(0,Math.min(100,100*p.stamina/Math.max(1,p.max_stamina))),manaPct=Math.max(0,Math.min(100,100*(p.mana||0)/Math.max(1,p.max_mana||1)));$('hpShort').textContent=Math.ceil(p.hp);$('stamShort').textContent=Math.floor(p.stamina);$('manaShort').textContent=Math.floor(p.mana||0);$('hpOrb').title=`Здоровье: ${p.hp} / ${p.max_hp}`;$('manaOrb').title=`Мана: ${Math.floor(p.mana||0)} / ${p.max_mana||0}`;$('stamOrb').title=`Выносливость: ${Math.floor(p.stamina)} / ${p.max_stamina}`;$('hpOrb').style.setProperty('--value',hpPct+'%');$('stamOrb').style.setProperty('--value',stamPct+'%');$('manaOrb').style.setProperty('--value',manaPct+'%');let need=p.level*120;$('xpText').textContent=`${p.xp} / ${need} XP`;$('xpFill').style.width=`${Math.max(0,Math.min(100,100*p.xp/need))}%`;updateSpellBar(p);updateActionPanels(p);
const z=zoneInfo[p.zone]||zoneInfo.camp;$('zoneLabel').textContent=`${z.name} · ${z.level}`;
updateQuestTracker(p);if($('questOverlay')&&$('questOverlay').style.display==='flex')renderQuestJournal(p);;
const inv=p.inventory;for(let k of ['wood','herb','ore','crystal','hide','slime','shard','arrows','potion']){let e=$(k);if(e)e.textContent=inv[k]||0;}$('weaponName').textContent=weaponNames[p.weapon]||p.weapon;$('gearName').textContent=gearNames[p.gear]||'Нет';$('defenseLabel').textContent=`· броня ${gearDefense[p.gear]||0}`;

try{renderInventory(p)}catch(err){console.warn('renderInventory',err)}if($('wizardOverlay').style.display==='flex')renderWizard(p);if($('forgeOverlay').style.display==='flex')renderForge(p);const kind=p.weapon_catalog?.[p.weapon]?.kind||'melee';try{updateCharacterPanel(p)}catch(err){console.warn('updateCharacterPanel',err)}if($('manaBadge'))$('manaBadge').textContent=`${Math.floor(p.mana||0)} / ${p.max_mana||0} маны`;$('marketBalance').textContent=`${p.gold||0} монет`;renderMarket(p);document.querySelectorAll('[data-spell]').forEach(b=>{let costs={fireball:18,lightning:26,heal:24,thorns:23,ice_lance:30,arcane_burst:38,meteor:58},unlocked=new Set(p.spells_unlocked||[]);b.disabled=!unlocked.has(b.dataset.spell)||(p.mana||0)<(costs[b.dataset.spell]||999)});
renderStatsPanel(p);if(window.renderCharOverlay)try{window.renderCharOverlay(me())}catch(err){}
document.querySelectorAll('[data-craft]').forEach(b=>{let r=b.dataset.craft;b.disabled=r==='arrows'?inv.wood<2||inv.ore<1:r==='potion'?inv.herb<3||inv.slime<1:r==='iron_sword'?inv.ore<6||inv.wood<4||p.weapons.includes('iron_sword'):inv.hide<4||inv.ore<3||(p.gear==='marsh_armor'||p.gear_inventory.includes('marsh_armor'))});
let keeper=Math.hypot(p.x-330,p.y-1100)<110,node=snap.nodes.some(n=>n.active&&Math.hypot(n.x-p.x,n.y-p.y)<68);$('interactButton').textContent=keeper?`${actionKeyLabel('interact')} · ХРАНИТЕЛЬ`:node?`${actionKeyLabel('gather')} · СБОР`:`${actionKeyLabel('gather')} · РЕСУРС`;$('progress').style.display=p.gathering?'block':'none';if(p.gathering){let g=snap.nodes.find(n=>n.active&&Math.hypot(n.x-p.x,n.y-p.y)<75);$('progressText').textContent=`Сбор: ${nodeNames[g?.kind]||'ресурс'}`;$('progressFill').style.width=`${Math.min(100,(p.gather_progress||0)*100)}%`}$('dodgeButton').disabled=!p.dodge_ready||p.stamina<24;if($('mDodgeButton'))$('mDodgeButton').disabled=$('dodgeButton').disabled;if($('mInteractButton'))$('mInteractButton').textContent=keeper?'ХРАНИТЕЛЬ':node?'СБОР':'РЕСУРС';
}
const questStages=[['slime',4,'herb',3,'Очистить опушку'],['wolf',3,'ore',4,'Следы в топи'],['boar',3,'crystal',3,'Свет под водой'],['colossus',1,'',0,'Пепельный колосс'],['frost_wyrm',4,'crystal',6,'Синий хребет'],['echo_dragon',1,'shard',8,'Разлом Эха'],['rift_knight',4,'shard',6,'Стражи разлома'],['echo_dragon',2,'crystal',12,'Сердце пустоты'],['void_wraith',5,'shard',12,'Угольный след'],['obsidian_sentinel',5,'ore',18,'Ключ из чёрного стекла'],['starseer',4,'crystal',20,'Охота на звёздочёта'],['starseer',5,'herb',22,'Корни под звёздами'],['ancient_warden',1,'shard',30,'Страж Первозданного сада']];function questDone(q){let t=questStages[Math.min(q.stage,questStages.length-1)];return(q.kills[t[0]]||0)>=t[1]&&(!t[2]||(q.gather[t[2]]||0)>=t[3])}
// weapon selection is handled by the weapon wheel; summary panel is display-only.
document.querySelectorAll('[data-craft]').forEach(b=>b.addEventListener('click',()=>send({type:'craft',recipe:b.dataset.craft})));$('potionButton').onclick=()=>send({type:'use_potion'});$('interactButton').onclick=()=>send({type:'interact'});$('chatForm').addEventListener('submit',e=>{e.preventDefault();let text=$('chatInput').value.trim();if(text)send({type:'chat',text});$('chatInput').value='';$('chatInput').blur()});
function attackChargeDuration(p){return Math.max(.25,Number(p?.weapon_catalog?.[p.weapon]?.charge)||.65)}function vectorAim(){return aim}function beginAttack(e){e.preventDefault();chargeLocal=true;chargeStart=performance.now();$('chargePercent').textContent='0%';$('chargeTier').textContent='НАБОР';$('attackButton').classList.add('charging');send({type:'attack_start',aim_x:aim.x,aim_y:aim.y})}function releaseAttack(e){if(!chargeLocal)return;e.preventDefault();const p=me(),charge=p?Math.min(1,(performance.now()-chargeStart)/(attackChargeDuration(p)*1000)):0;chargeLocal=false;$('attackButton').classList.remove('charging');$('chargeTier').textContent=charge>=.8?'ПОЛНЫЙ':'УДАР';send({type:'attack_release',aim_x:aim.x,aim_y:aim.y});if(p){let w=p.weapon,spec=p.weapon_catalog?.[w]||{};if(spec.kind==='bow'){sfxCall('bowShot')}else{const heavy=charge>.75||/axe|maul|greatsword|halberd|scythe/.test(w||'');sfxCall('swing',heavy);fxCall('punch',heavy?.012:.008)}if(spec.kind!=='bow'){let range=Number(spec.range||44)+12*charge;attackFx.push({x:p.x,y:p.y,fx:true,ax:aim.x,ay:aim.y,weapon:w,range,arcCos:Number(spec.arc??.28),charge,until:performance.now()+340})}}}
$('attackButton').addEventListener('pointerdown',beginAttack);$('attackButton').addEventListener('pointerup',releaseAttack);$('attackButton').addEventListener('pointercancel',releaseAttack);$('attackButton').addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse'&&e.button===0&&!e.target.closest('button')){e.preventDefault();setAimFromPointer();beginAttack(e);try{canvas.setPointerCapture(e.pointerId)}catch{}}});
addEventListener('pointerup',e=>{if(chargeLocal)releaseAttack(e)});
document.addEventListener('pointerdown',e=>{const t=e.target&&e.target.closest?e.target.closest('button,[role=button],.actionBtn,.pad,[data-inv-tab]'):null;if(!t)return;if(t.id==='attackButton'||t.id==='dodgeButton'||t.id==='audioToggle'||(t.classList&&t.classList.contains('pad')))return;sfxCall('ui')},true);
canvas.addEventListener('contextmenu',e=>e.preventDefault());
function dodge(){const p=me();if(p)fxCall('dodge',p.x,p.y);sfxCall('dodge');send({type:'dodge'})}$('inventoryButton').onclick=openInventory;if($('openInventory'))$('openInventory').onclick=openInventory;$('closeInventory').onclick=closeInventory;$('invOverlay').addEventListener('click',e=>{if(e.target===$('invOverlay'))closeInventory()});$('invOverlay').addEventListener('click',e=>{let g=e.target.closest('button[data-inv-equip-gear]'),w=e.target.closest('button[data-inv-equip-weapon]');if(g&&!g.disabled){send({type:'equip_gear',id:g.dataset.invEquipGear});toast('Надеваю броню…')}if(w&&!w.disabled){send({type:'weapon',id:w.dataset.invEquipWeapon});toast('Оружие экипировано')}});document.querySelectorAll('[data-inv-tab]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-inv-tab]').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('[data-inv-section]').forEach(x=>x.style.display=b.dataset.invTab==='all'||x.dataset.invSection===b.dataset.invTab?'block':'none')}));$('dodgeButton').onclick=dodge;const movementCodes={KeyW:'w',ArrowUp:'arrowup',KeyS:'s',ArrowDown:'arrowdown',KeyA:'a',ArrowLeft:'arrowleft',KeyD:'d',ArrowRight:'arrowright'};function activeGameMenu(){const ids=['classOverlay','invOverlay','marketOverlay','wizardOverlay','forgeOverlay','customSpellOverlay','controlsOverlay','guideOverlay','mapOverlay','gameMenuOverlay','charOverlay','keybindOverlay','accountOverlay','questOverlay','login'];return ids.some(id=>{const el=$(id);return !!(el&&el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden')})||[...document.querySelectorAll('[role=dialog]')].some(el=>el.getClientRects().length>0&&getComputedStyle(el).visibility!=='hidden')}
function closeTopGameMenu(){const order=['npcOverlay','atlasOverlay','classOverlay','customSpellOverlay','keybindOverlay','accountOverlay','charOverlay','guideOverlay','wizardOverlay','forgeOverlay','marketOverlay','questOverlay','invOverlay','mapOverlay','controlsOverlay','gameMenuOverlay'];for(const id of order){const el=$(id);if(!el||getComputedStyle(el).display==='none')continue;if(id==='npcOverlay')closeNpc();else if(id==='atlasOverlay')closeAtlas();else if(id==='questOverlay')closeQuestJournal();else if(id==='classOverlay')hideClassOffer();else if(id==='guideOverlay')toggleGuide(false);else if(id==='wizardOverlay'||id==='forgeOverlay')closeStation(id);else if(id==='invOverlay')closeInventory();else if(id==='marketOverlay')closeMarket();else if(id==='controlsOverlay')toggleControls(false);else if(id==='keybindOverlay')toggleKeybinds(false,true);else if(id==='accountOverlay')toggleAccounts(false,true);else if(id==='charOverlay')toggleCharacter(false,true);else if(id==='gameMenuOverlay')toggleGameMenu(false);else el.style.display='none';return true}return false}
// Capture keyboard events before global gameplay bindings: visible menus never leak hotkeys.
document.addEventListener('keydown',e=>{if(!activeGameMenu())return;if(e.key==='Escape'){closeTopGameMenu();e.preventDefault()}if(!(e.key==='Enter'&&e.target===$('chatInput')))e.stopPropagation()},true);
document.addEventListener('keyup',e=>{if(activeGameMenu()){keys.clear();touchDirs.clear();e.stopPropagation()}},true);
addEventListener('keydown',e=>{if(e.repeat)return;const target=e.target;if(target&&(target.matches('input,textarea,select')||target.isContentEditable))return;const code=e.code;if(activeGameMenu()){if(code==='Escape'){closeTopGameMenu();e.preventDefault()}return;}let k=movementCodes[code]||e.key.toLowerCase();if(code==='Space'||code.startsWith('Arrow'))e.preventDefault();if(code==='Escape'){if(closeTopGameMenu())return;toggleGameMenu(true);return}if(document.activeElement===$('chatInput')||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;if(code==='ShiftLeft'||code==='ShiftRight'){runHeld=true;lastInput=0;return}if(code==='ControlLeft'||code==='ControlRight'){sneakHeld=true;lastInput=0;return}if(movementCodes[code]){keys.add(k);return}const act=actionByCode(code);if(act){if(applyActionToGame(act,e))return}if(abilityKeyCodeToId[code]){useAbility(abilityKeyCodeToId[code]);e.preventDefault();return}if(e.shiftKey&&spellKeyCodeToId[code])castSpell(spellKeyCodeToId[code]);if(code.startsWith('F')&&/^F(?:[1-9]|1[0-2])$/.test(code))e.preventDefault();castCustomSpellByKey(code)});addEventListener('keyup',e=>{if(e.code==='ShiftLeft'||e.code==='ShiftRight'){runHeld=false;lastInput=0}if(e.code==='ControlLeft'||e.code==='ControlRight'){sneakHeld=false;lastInput=0}const k=movementCodes[e.code];if(k)keys.delete(k);const upAct=actionByCode(e.code);if(upAct==='gather')send({type:'gather_stop'});if(upAct==='attack')releaseAttack(e)});addEventListener('blur',()=>{keys.clear();touchDirs.clear();runHeld=false;sneakHeld=false;lastInput=0});
let mouse={x:0,y:0};canvas.addEventListener('pointermove',e=>{let r=canvas.getBoundingClientRect();mouse.x=e.clientX-r.left;mouse.y=e.clientY-r.top;setAimFromPointer()});function setAimFromPointer(){let p=me();if(!p)return;let r=canvas.getBoundingClientRect(),wx=cam.x+(mouse.x-r.width/2),wy=cam.y+(mouse.y-r.height/2),dx=wx-p.x,dy=wy-p.y,l=Math.hypot(dx,dy);if(l>.1){aim={x:dx/l,y:dy/l};hasPointerAim=true}}
document.querySelectorAll('.pad').forEach(b=>{let dir=b.dataset.dir;b.addEventListener('pointerdown',e=>{e.preventDefault();b.setPointerCapture(e.pointerId);touchDirs.add(dir)});['pointerup','pointercancel','lostpointercapture'].forEach(ev=>b.addEventListener(ev,()=>touchDirs.delete(dir))) });
/* ─── МОБИЛЬНОЕ УПРАВЛЕНИЕ: джойстик-стик для ходьбы + панель кнопок ─── */
const isMobileUI=('ontouchstart' in window)||navigator.maxTouchPoints>0;
if(isMobileUI)document.body.classList.add('is-mobile');
let joyVec={x:0,y:0},joyPointer=null;
const joyZone=$('joystickZone'),joyKnobEl=$('joyKnob');
function joySetKnob(dx,dy){joyKnobEl.style.transform=`translate(${dx}px,${dy}px)`}
function joyUpdate(e){const r=joyZone.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2,max=r.width/2;let dx=e.clientX-cx,dy=e.clientY-cy,l=Math.hypot(dx,dy);if(l>max){dx*=max/l;dy*=max/l}const nl=Math.hypot(dx,dy)/max;joyVec=nl>.14?{x:dx/max,y:dy/max}:{x:0,y:0};joySetKnob(dx,dy)}
function joyRelease(){joyPointer=null;joyVec={x:0,y:0};joySetKnob(0,0);joyZone.classList.remove('active')}
if(joyZone){joyZone.addEventListener('pointerdown',e=>{e.preventDefault();if(joyPointer!==null)return;joyPointer=e.pointerId;joyZone.setPointerCapture(e.pointerId);joyZone.classList.add('active');joyUpdate(e)});joyZone.addEventListener('pointermove',e=>{if(e.pointerId===joyPointer)joyUpdate(e)});['pointerup','pointercancel','lostpointercapture'].forEach(ev=>joyZone.addEventListener(ev,e=>{if(ev==='lostpointercapture'?joyPointer!==null:e.pointerId===joyPointer)joyRelease()}))}
(function wireMobileButtons(){
 const mAttack=$('mAttackButton');
 if(mAttack){mAttack.addEventListener('pointerdown',beginAttack);['pointerup','pointercancel','lostpointercapture'].forEach(ev=>mAttack.addEventListener(ev,e=>{if(chargeLocal)releaseAttack(e)}));mAttack.addEventListener('contextmenu',e=>e.preventDefault())}
 const act=(fn)=>(e)=>{e.preventDefault();e.stopPropagation();fn()};
 $('mInteractButton').onclick=act(()=>$('interactButton').click());
 $('mDodgeButton').onclick=act(dodge);
 $('mPotionButton').onclick=act(()=>send({type:'use_potion'}));
 $('mMapButton').onclick=act(toggleMap);
 $('mInventoryButton').onclick=act(openInventory);
 $('mMarketButton').onclick=act(()=>{if($('marketOverlay').style.display==='flex')closeMarket();else openMarket()});
 $('mWizardButton').onclick=act(openWizard);
 $('mForgeButton').onclick=act(openForge);
 $('mControlsButton').onclick=act(()=>toggleControls(true));
 $('mCharButton').onclick=act(()=>toggleCharacter());
 $('mMenuButton').onclick=act(()=>toggleGameMenu());
 $('mChatButton').onclick=act(()=>{$('chatInput').focus()});
})();
function toggleMap(){let el=$('mapOverlay');let opening=el.style.display!=='flex';el.style.display=opening?'flex':'none';if(opening)requestAnimationFrame(()=>{resize();drawMap(full,fctx,true);$('closeMap').focus()})}$('mapButton').onclick=toggleMap;$('closeMap').onclick=toggleMap;$('mapOverlay').addEventListener('click',e=>{if(e.target===$('mapOverlay'))toggleMap()});addEventListener('resize',()=>{if($('mapOverlay').style.display==='flex')requestAnimationFrame(()=>drawMap(full,fctx,true))});
function inputFrame(){if(activeGameMenu()){window.echoMoving=false;keys.clear();touchDirs.clear();joyRelease();if(performance.now()-lastInput>45){send({type:'input',x:0,y:0,aim_x:aim.x,aim_y:aim.y,run:false,sneak:false});lastInput=performance.now()}return}let x=0,y=0;for(const k of keys){if(k==='w'||k==='arrowup')y--;if(k==='s'||k==='arrowdown')y++;if(k==='a'||k==='arrowleft')x--;if(k==='d'||k==='arrowright')x++}if(touchDirs.has('up'))y--;if(touchDirs.has('down'))y++;if(touchDirs.has('left'))x--;if(touchDirs.has('right'))x++;x+=joyVec.x;y+=joyVec.y;let l=Math.hypot(x,y);if(l>.1&&!hasPointerAim){aim={x:x/l,y:y/l}}if(l>1){x/=l;y/=l}const mv=Math.hypot(x,y),joyRun=Math.hypot(joyVec.x,joyVec.y)>.92;const modeRun=!!(runHeld||joyRun)&&mv>.1, modeSneak=!!sneakHeld&&mv>.1&&!modeRun;window.echoMoving=mv>.1;window.echoRun=modeRun;window.echoSneak=modeSneak;if(performance.now()-lastInput>45){send({type:'input',x,y,aim_x:aim.x,aim_y:aim.y,run:modeRun,sneak:modeSneak});lastInput=performance.now()}}
const WORLD_FALLBACK={w:2000,h:1500};
const zonePalettes={camp:'#758f54',forest:'#69864f',marsh:'#50796d',ruins:'#786650',glacier:'#7599a1',rift:'#564b78',abyss:'#352d51',obsidian:'#54435f',garden:'#557a4a'};
function worldSize(){return snap?.world||WORLD_FALLBACK}
function seedDecor(){}
function drawPath(c,cx,cy){let W=worldSize(),pts=[];for(let i=0;i<=7;i++)pts.push([W.w*(.035+i*.132),W.h*(.22+.07*Math.sin(i*1.7)+.035*Math.sin(i*3.3))]);c.beginPath();c.moveTo(pts[0][0]+cx,pts[0][1]+cy);for(let i=1;i<pts.length;i++){let [x,y]=pts[i],[px,py]=pts[i-1],dx=(x-px)/3;c.bezierCurveTo(px+dx+cx,py+Math.sin(i)*90+cy,x-dx+cx,y-Math.sin(i)*90+cy,x+cx,y+cy)}c.strokeStyle='#302f27';c.lineWidth=46;c.stroke();c.strokeStyle='#d0b77b';c.lineWidth=32;c.stroke();c.strokeStyle='#998b60';c.lineWidth=3;c.stroke()}
function drawTree(c,x,y,r,kind,k){
 c.save();c.translate(x,y);c.scale(r/20,r/20);
 c.fillStyle='#10170f55';c.beginPath();c.ellipse(0,14,17,5,0,0,Math.PI*2);c.fill();
 const trunk=kind==='glacier'?'#5d7778':kind==='marsh'?'#554b39':kind==='rift'||kind==='abyss'?'#40364d':'#594331';
 const bark=c.createLinearGradient(-5,0,6,0);bark.addColorStop(0,'#171b17');bark.addColorStop(.35,trunk);bark.addColorStop(.7,'#9a7651');bark.addColorStop(1,'#29291f');
 c.fillStyle=bark;c.beginPath();c.moveTo(-4,13);c.lineTo(-2,-6);c.quadraticCurveTo(0,-11,3,-5);c.lineTo(5,14);c.closePath();c.fill();
 c.strokeStyle='#d0a06a55';c.lineWidth=1;c.beginPath();c.moveTo(-1,10);c.lineTo(0,-4);c.moveTo(2,7);c.lineTo(1,1);c.stroke();
 if(kind==='marsh'){
  c.strokeStyle='#927d54';c.lineWidth=2;c.beginPath();c.moveTo(0,-3);c.lineTo(-11,-13);c.moveTo(1,-4);c.lineTo(12,-14);c.moveTo(0,-8);c.lineTo(1,-19);c.stroke();
  for(const [lx,ly,rx,ry] of [[-12,-14,5,11],[12,-15,5,12],[1,-21,5,12],[-7,-10,4,9],[8,-11,4,9]]){c.fillStyle='#3e7564';c.beginPath();c.ellipse(lx,ly,rx,ry,-.35,0,Math.PI*2);c.fill();c.strokeStyle='#a4d0a044';c.lineWidth=.7;c.stroke()}
 }else{
  let leaves=kind==='glacier'?['#a7d7d7','#6da9b0','#d8f0e5']:kind==='rift'?['#7953a4','#9a64c2','#cf8de0']:kind==='abyss'?['#533d69','#79506c','#b16d88']:kind==='ruins'?['#586044','#74714c','#91815b']:['#31573b','#477447','#71904d'];
  for(let i=0;i<3;i++){let lx=[-8,1,8][i],ly=[-10,-17,-9][i],rx=[9,11,8][i],ry=[8,9,8][i],g=c.createRadialGradient(lx-3,ly-4,1,lx,ly,rx+ry);g.addColorStop(0,leaves[2]);g.addColorStop(.48,leaves[1]);g.addColorStop(1,leaves[0]);c.fillStyle=g;c.beginPath();c.ellipse(lx,ly,rx,ry,(i-1)*.22,0,Math.PI*2);c.fill();c.strokeStyle='#17231b66';c.lineWidth=.8;c.stroke();
   for(let j=0;j<3;j++){let a=k*17+i*2+j*2.1,px=lx+Math.cos(a)*rx*.53,py=ly+Math.sin(a)*ry*.48;c.fillStyle=j===0?'#f1e6a333':'#dff2c522';c.beginPath();c.ellipse(px,py,1.8,1, a,0,Math.PI*2);c.fill()}}
 }
 c.restore();
}
function drawMobSprite(c,m,x,y,s,now,color){
 c.save();c.translate(x,y);let u=s/20;c.scale(u,u);const kind=m.kind;
 const colors={slime:'#91d56d',wolf:'#bac9b8',boar:'#a87956',wisp:'#69dfd3',stone:'#a99578',ashling:'#d27e5e',ashguard:'#b5a58e',colossus:'#d38a5d',rift_knight:'#9972c5',echo_dragon:'#d75d9f',frost_wyrm:'#77cce0'};
 let base=colors[kind]||color||'#aabb99',shade=c.createLinearGradient(-15,-18,16,17);shade.addColorStop(0,'#fff4d077');shade.addColorStop(.32,base);shade.addColorStop(1,'#18251e');
 c.fillStyle='#10170f66';c.beginPath();c.ellipse(0,15,17,5,0,0,Math.PI*2);c.fill();
 const ell=(cx,cy,rx,ry,fill,rot=0)=>{c.fillStyle=fill;c.beginPath();c.ellipse(cx,cy,rx,ry,rot,0,Math.PI*2);c.fill()};
 const poly=(pts,fill,stroke='#20251d',lw=1)=>{c.beginPath();c.moveTo(pts[0][0],pts[0][1]);for(let i=1;i<pts.length;i++)c.lineTo(pts[i][0],pts[i][1]);c.closePath();c.fillStyle=fill;c.fill();if(stroke){c.strokeStyle=stroke;c.lineWidth=lw;c.stroke()}};
 const eye=(ex,ey,glow='#f4e7a2')=>{ell(ex,ey,2.5,2.1,'#17201b');ell(ex+.5,ey,1.15,1.2,glow)};
 if(kind==='slime'){
  c.fillStyle=shade;c.beginPath();c.moveTo(-16,9);c.quadraticCurveTo(-18,0,-12,-7);c.quadraticCurveTo(-7,-14,-2,-9);c.quadraticCurveTo(5,-17,10,-8);c.quadraticCurveTo(18,-2,16,9);c.quadraticCurveTo(9,14,-10,12);c.closePath();c.fill();c.strokeStyle='#e2ff9c99';c.lineWidth=1.2;c.stroke();ell(-6,-5,3,1.5,'#efffc788',-.5);eye(-6,1,'#fff4ae');eye(6,1,'#fff4ae');ell(0,7,5,1,'#4f833d')
 }else if(kind==='wolf'||kind==='boar'){
  ell(-1,1,15,8,shade,-.12);ell(10,-5,8,7,shade,-.2);ell(13,-9,5,4,base);
  poly([[-1,-5],[-5,-13],[2,-9],[5,-5]],base,'#30362b',.8);poly([[9,-10],[8,-16],[13,-11]],base,'#30362b',.8);
  for(const lx of [-10,0,8]){c.strokeStyle='#473b31';c.lineWidth=2.6;c.beginPath();c.moveTo(lx,5);c.lineTo(lx-2,13);c.stroke();ell(lx-2,13,2,1.5,'#3a3028')}
  if(kind==='boar'){poly([[15,-3],[21,0],[15,2]],'#6d4836');poly([[9,0],[12,4],[14,0]],'#f3dfb0','#fff4d0',.5);poly([[16,0],[18,4],[19,0]],'#f3dfb0','#fff4d0',.5);ell(12,-6,2,1,'#1a211c')}
  else{ell(9,-6,3.5,2.8,'#d3d3c5');eye(10,-6,'#e96c57');c.strokeStyle='#e1e0cf';c.lineWidth=1;c.beginPath();c.moveTo(11,-11);c.lineTo(15,-15);c.stroke()}
 }else if(kind==='wisp'){
  let glow=c.createRadialGradient(0,0,2,0,0,22);glow.addColorStop(0,'#e8fff4cc');glow.addColorStop(.3,'#83ffe5aa');glow.addColorStop(1,'#4acac000');ell(0,0,22,24,glow);
  c.fillStyle=shade;c.beginPath();c.moveTo(-10,8);c.quadraticCurveTo(-15,-3,-8,-10);c.quadraticCurveTo(-3,-20,2,-10);c.quadraticCurveTo(13,-12,10,2);c.quadraticCurveTo(8,13,2,18);c.quadraticCurveTo(0,11,-4,17);c.closePath();c.fill();eye(-3,-3,'#f4fff0');eye(5,-3,'#f4fff0')
 }else if(kind==='frost_wyrm'||kind==='echo_dragon'){
  let wing=kind==='frost_wyrm'?'#9ae5eb':'#ef8fbd';
  poly([[-4,-2],[-20,-20],[-17,-3],[-11,6],[-20,14],[-4,9]],wing,'#392b3f',1.1);poly([[3,-2],[20,-20],[17,-3],[11,6],[20,14],[4,9]],wing,'#392b3f',1.1);
  c.strokeStyle=kind==='frost_wyrm'?'#e8ffffaa':'#ffe0f2aa';c.lineWidth=1;c.beginPath();c.moveTo(-18,-18);c.lineTo(-7,5);c.moveTo(18,-18);c.lineTo(7,5);c.stroke();
  c.strokeStyle=shade;c.lineWidth=9;c.lineCap='round';c.beginPath();c.moveTo(-9,4);c.quadraticCurveTo(0,-5,8,2);c.quadraticCurveTo(15,8,17,1);c.stroke();ell(-2,1,8,5,base);ell(8,-5,6,5,shade);poly([[7,-9],[4,-15],[11,-10]],'#f2e9df');poly([[12,-8],[16,-13],[15,-7]],'#f2e9df');eye(10,-6,kind==='frost_wyrm'?'#eaffff':'#ffe49a');
 }else if(kind==='rift_knight'||kind==='ashguard'||kind==='stone'||kind==='colossus'){
  let big=kind==='colossus';let armor=kind==='rift_knight'?'#4f416b':kind==='stone'||big?'#887963':'#665e52';
  poly([[-12,-10],[-7,-17],[7,-17],[13,-8],[11,9],[7,14],[-8,14],[-13,7]],shade,'#272b28',1.4);
  poly([[-11,-9],[-17,-5],[-13,3],[-8,1]],armor);poly([[11,-9],[17,-5],[13,3],[8,1]],armor);
  ell(0,-10,9,7,kind==='rift_knight'?'#665287':'#9c927f');poly([[-8,-8],[-10,-15],[0,-19],[10,-15],[8,-8],[0,-5]],shade,'#24272a',1);
  c.fillStyle=kind==='rift_knight'?'#e8a9ff':'#ffd078';c.shadowColor=c.fillStyle;c.shadowBlur=8;c.fillRect(-5,-10,3,2);c.fillRect(3,-10,3,2);c.shadowBlur=0;
  poly([[-8,13],[-11,20],[-3,20],[-2,13]],'#3d342e');poly([[3,13],[4,20],[12,20],[9,13]],'#3d342e');
  if(big){ell(-14,-12,5,8,'#887963',-.4);ell(15,-12,5,8,'#887963',.4);c.strokeStyle='#ffd08a';c.lineWidth=1.2;c.beginPath();c.moveTo(-3,-3);c.lineTo(1,2);c.lineTo(-2,7);c.stroke()}
 }else{
  // ashling and fallback: small ember spirit with horned silhouette
  poly([[-11,10],[-9,-7],[-5,-11],[-8,-18],[-1,-13],[2,-19],[6,-11],[11,-7],[12,10],[5,15],[-5,15]],shade,'#3a2823',1.2);
  poly([[-7,-10],[-12,-17],[-3,-13]],'#f19a66');poly([[5,-11],[11,-18],[9,-10]],'#f19a66');eye(-4,-5,'#fff0a0');eye(4,-5,'#fff0a0');ell(0,5,5,4,'#ffb078');
 }
 // engraved highlights and a small ground contact shadow
 c.restore();
}
function drawCombatAnimation(c,q,x,y,now){
 const active=q.attack;
 if(active){const charge=Math.max(0,Math.min(1,Number(active.charge||0))),ax=Number(active.aim_x??q.face_x??1),ay=Number(active.aim_y??q.face_y??0),angle=Math.atan2(ay,ax),radius=25+charge*13,color=charge>.8?'#ffe08c':charge>.35?'#d6c77b':'#9ed38b';c.save();c.translate(x,y);c.globalAlpha=.35+.55*charge;c.strokeStyle=color;c.lineWidth=1.6+charge*2;c.shadowColor=color;c.shadowBlur=6+charge*12;c.beginPath();c.arc(0,0,radius,-Math.PI/2,-Math.PI/2+Math.PI*2*charge);c.stroke();c.shadowBlur=0;for(let i=0;i<3;i++){let a=angle+(now/480)+i*2.094,rr=radius*(.48+.32*charge);c.globalAlpha=.25+.7*charge;c.fillStyle=color;c.beginPath();c.arc(Math.cos(a)*rr,Math.sin(a)*rr,1.6+charge*1.7,0,Math.PI*2);c.fill()}c.restore()}
 // While charging a bow attack, draw the bow and pull the string progressively.
 if(active&&active.kind==='bow'){
  const ax=Number(active.aim_x??q.face_x??1),ay=Number(active.aim_y??q.face_y??0),angle=Math.atan2(ay,ax),charge=Math.max(0,Math.min(1,Number(active.charge||0)));
  c.save();c.translate(x,y);c.rotate(angle);c.lineCap='round';
  c.strokeStyle='#533b27';c.lineWidth=3.6;c.beginPath();c.moveTo(17,-14);c.quadraticCurveTo(29,0,17,14);c.stroke();
  c.strokeStyle='#b88952';c.lineWidth=2;c.beginPath();c.moveTo(17,-14);c.quadraticCurveTo(27,0,17,14);c.stroke();
  c.strokeStyle='#e9dfbd';c.lineWidth=1;c.beginPath();c.moveTo(17,-14);c.lineTo(17-charge*11,0);c.lineTo(17,14);c.stroke();
  c.strokeStyle='#d9c58d';c.lineWidth=1.6;c.beginPath();c.moveTo(17-charge*11,0);c.lineTo(35-charge*11,0);c.stroke();
  c.fillStyle='#e6c68f';c.beginPath();c.arc(17-charge*11,0,2.2,0,Math.PI*2);c.fill();
  c.restore();
 }
 for(const a of weaponActions){
  if(a.id!==q.id||now>a.until)continue;
  const duration=a.until-a.started,u=Math.max(0,Math.min(1,(now-a.started)/Math.max(1,duration))),ease=u*u*(3-2*u),angle=Math.atan2(a.aim_y||0,a.aim_x||1);
  const weapon=a.weapon||q.weapon,kind=a.weapon_kind||q.weapon_catalog?.[weapon]?.kind||'melee';
  c.save();c.translate(x,y);c.rotate(angle);c.lineCap='round';c.lineJoin='round';
  const staff=kind==='staff',bow=kind==='bow';
  const wood=weapon==='thorn_staff'?'#92c85c':weapon==='archon_staff'?'#55cfe0':'#b98a56';
  if(a.action==='cast'){
   if(staff){
    // Spear-like thrust from the character center toward the aim vector, same scale throughout.
    const thrust=Math.sin(Math.PI*ease),tipX=54+thrust*7;
    c.save();c.strokeStyle='#382b20';c.lineWidth=5;c.beginPath();c.moveTo(1,0);c.lineTo(tipX,0);c.stroke();
    c.strokeStyle=wood;c.lineWidth=2.8;c.beginPath();c.moveTo(1,0);c.lineTo(tipX,0);c.stroke();
    c.shadowColor=wood;c.shadowBlur=10;c.fillStyle=weapon==='thorn_staff'?'#d4ff83':weapon==='archon_staff'?'#a9f4ff':'#a9f4ff';c.beginPath();c.arc(tipX+3,0,4,0,Math.PI*2);c.fill();c.shadowBlur=0;
    c.strokeStyle='#d7b979';c.lineWidth=4;c.beginPath();c.moveTo(9,0);c.lineTo(17,0);c.stroke();c.restore();
   }else{
    // Free hand casting: extend the palm and gather a brief point of light.
    const reach=10+8*Math.sin(Math.PI*ease);
    c.strokeStyle='#314133';c.lineWidth=5;c.beginPath();c.moveTo(3,-5);c.quadraticCurveTo(9,-7,reach,0);c.stroke();
    c.strokeStyle='#d2a47d';c.lineWidth=3;c.beginPath();c.moveTo(reach-2,0);c.lineTo(reach+3,0);c.stroke();
    c.globalAlpha=.55+.45*Math.sin(Math.PI*ease);c.shadowColor='#a7f4d2';c.shadowBlur=12;c.fillStyle='#c9ffe4';c.beginPath();c.arc(reach+5,0,3+2*Math.sin(Math.PI*ease),0,Math.PI*2);c.fill();c.shadowBlur=0;
   }
  }else if(bow){
   // Bow release: string snaps forward after the draw phase.
   const pull=(1-ease)*Math.max(.35,Number(a.charge||0));
   c.strokeStyle='#533b27';c.lineWidth=3.6;c.beginPath();c.moveTo(17,-14);c.quadraticCurveTo(29,0,17,14);c.stroke();
   c.strokeStyle='#b88952';c.lineWidth=2;c.beginPath();c.moveTo(17,-14);c.quadraticCurveTo(27,0,17,14);c.stroke();
   c.strokeStyle='#efe4c5';c.lineWidth=1;c.beginPath();c.moveTo(17,-14);c.lineTo(17-pull*10,0);c.lineTo(17,14);c.stroke();
   c.strokeStyle='#d9c58d';c.lineWidth=1.5;c.beginPath();c.moveTo(17-pull*10,0);c.lineTo(33,0);c.stroke();
  }else{
   // Sword-style swing. Staffs use the same motion, but keep their own wooden/gem texture.
   const swing=-1.45+2.35*ease,gripX=5,gripY=-5;
   c.save();c.translate(gripX,gripY);c.rotate(swing);
   c.strokeStyle='#28362d';c.lineWidth=5;c.beginPath();c.moveTo(0,0);c.lineTo(9,1);c.stroke();
   c.strokeStyle='#d7a980';c.lineWidth=3;c.beginPath();c.moveTo(6,1);c.lineTo(11,2);c.stroke();
   if(staff){
    c.strokeStyle='#392a1d';c.lineWidth=5;c.beginPath();c.moveTo(10,2);c.lineTo(42,2);c.stroke();
    c.strokeStyle=wood;c.lineWidth=2.8;c.beginPath();c.moveTo(10,2);c.lineTo(42,2);c.stroke();
    c.shadowColor=wood;c.shadowBlur=8;c.fillStyle=weapon==='thorn_staff'?'#d7ff83':weapon==='archon_staff'?'#9df8ff':'#caffff';c.beginPath();c.arc(44,2,4,0,Math.PI*2);c.fill();c.shadowBlur=0;
    c.fillStyle='#d7b979';c.fillRect(11,-1.5,3,7);
   }else{
    c.strokeStyle='#ddd0aa';c.lineWidth=5;c.beginPath();c.moveTo(10,2);c.lineTo(14,2);c.stroke();
    const blade=c.createLinearGradient(14,-4,14,5);blade.addColorStop(0,'#f8f3df');blade.addColorStop(.5,'#92c9cf');blade.addColorStop(1,'#526d70');c.fillStyle=blade;c.beginPath();c.moveTo(14,-3);c.lineTo(37,0);c.lineTo(14,4);c.closePath();c.fill();
    c.strokeStyle='#e8d9a7';c.lineWidth=1;c.beginPath();c.moveTo(15,0);c.lineTo(34,0);c.stroke();
   }
   c.restore();
  }
  c.restore();
 }
 weaponActions=weaponActions.filter(a=>now<=a.until);
}
function drawAvatarSprite(c,q,x,y,coat,trim,local,equipment){
 c.save();c.translate(x,y);c.scale(1.12,1.12);
 c.fillStyle='#10160f88';c.beginPath();c.ellipse(0,15,13,4,0,0,Math.PI*2);c.fill();
 const facing=Math.atan2(q.face_y||0,q.face_x||1),fx=Math.cos(facing),fy=Math.sin(facing);
 // cloak silhouette and layered tunic
 c.fillStyle='#171d18';c.beginPath();c.moveTo(-8,-10);c.quadraticCurveTo(-14,-4,-12,9);c.lineTo(-7,13);c.lineTo(8,13);c.lineTo(12,8);c.quadraticCurveTo(11,-4,7,-10);c.closePath();c.fill();
 let body=c.createLinearGradient(-9,0,9,0);body.addColorStop(0,'#18221d');body.addColorStop(.25,coat);body.addColorStop(.68,coat);body.addColorStop(1,'#20251e');c.fillStyle=body;c.beginPath();c.moveTo(-7,-11);c.lineTo(7,-11);c.lineTo(10,8);c.lineTo(7,13);c.lineTo(-7,13);c.lineTo(-10,8);c.closePath();c.fill();
 c.strokeStyle=trim;c.globalAlpha=.9;c.lineWidth=1.3;c.beginPath();c.moveTo(-7,-7);c.lineTo(-4,5);c.lineTo(0,9);c.lineTo(4,5);c.lineTo(7,-7);c.stroke();c.globalAlpha=1;
 // belt, buckle and boots
 c.fillStyle='#513d2b';c.fillRect(-9,5,18,2.2);c.fillStyle=trim;c.fillRect(-1.3,4.5,3,3);c.fillStyle='#30271f';c.fillRect(-8,11,6,4);c.fillRect(3,11,6,4);
 // hood and face
 c.fillStyle=equipment==='rift_plate'?'#4b3b63':equipment==='glacier_mantle'?'#83aeb9':'#443729';c.beginPath();c.ellipse(0,-13,8,9,0,0,Math.PI*2);c.fill();
 c.fillStyle=equipment==='colossus_core'?'#e4c59c':'#d5ad87';c.beginPath();c.ellipse(0,-12,5.4,6.1,0,0,Math.PI*2);c.fill();
 c.fillStyle='#2a241e';c.beginPath();c.moveTo(-7,-16);c.quadraticCurveTo(0,-23,8,-16);c.lineTo(6,-13);c.quadraticCurveTo(0,-17,-6,-12);c.closePath();c.fill();
 let ex=fx*2.1,ey=-12+fy*1.1;c.fillStyle=local?'#fff1a3':'#d4e3cf';c.beginPath();c.arc(ex,ey,1.25,0,Math.PI*2);c.fill();
 // shoulder armor, straps and gear silhouette
 c.fillStyle=trim;c.globalAlpha=.8;c.beginPath();c.ellipse(-8,-7,3.2,2.5,-.4,0,Math.PI*2);c.fill();c.beginPath();c.ellipse(8,-7,3.2,2.5,.4,0,Math.PI*2);c.fill();c.globalAlpha=1;
 c.strokeStyle='#e3c989';c.lineWidth=1;c.beginPath();c.moveTo(-5,-4);c.lineTo(4,4);c.stroke();
 // Class silhouettes are shared by every client and stay above the equipped armor colours.
 if(q.class==='warrior'){c.fillStyle='#b9c4c0';c.beginPath();c.ellipse(-9,-8,4.3,3,-.35,0,Math.PI*2);c.fill();c.beginPath();c.ellipse(9,-8,4.3,3,.35,0,Math.PI*2);c.fill();c.fillStyle='#a34f45';c.fillRect(-1.2,-23,2.8,6);c.fillStyle='#7e3b35';c.fillRect(-3,-18,7,2)}
 else if(q.class==='ranger'){c.strokeStyle='#b7d67c';c.lineWidth=1.4;c.beginPath();c.moveTo(6,-18);c.quadraticCurveTo(14,-28,19,-25);c.stroke();c.fillStyle='#6f8b4e';c.beginPath();c.moveTo(5,-13);c.quadraticCurveTo(14,-16,15,-7);c.quadraticCurveTo(8,-9,5,-13);c.fill();c.strokeStyle='#9a7547';c.lineWidth=2.4;c.beginPath();c.moveTo(-9,-4);c.lineTo(-13,9);c.stroke()}
 else if(q.class==='mage'){c.strokeStyle='#9ee8ff';c.lineWidth=1.4;c.beginPath();c.arc(0,-18,6.5,Math.PI*1.08,Math.PI*1.92);c.stroke();c.fillStyle='#b6f3ff';c.shadowColor='#7ee8ff';c.shadowBlur=7;c.beginPath();c.arc(0,-24,1.7,0,Math.PI*2);c.fill();c.shadowBlur=0;c.strokeStyle='#8ed7ef';c.globalAlpha=.85;c.beginPath();c.moveTo(-4,2);c.lineTo(0,7);c.lineTo(4,2);c.stroke();c.globalAlpha=1}
 if(local){c.globalAlpha=.42;c.fillStyle=trim;c.beginPath();c.ellipse(0,0,17,21,0,0,Math.PI*2);c.fill();c.globalAlpha=1}
 if(local&&['apprentice_staff','thorn_staff'].includes(q.weapon)){
  let staff=q.weapon==='thorn_staff'?'#b9ef7f':'#b8f3ff';c.strokeStyle='#493b2b';c.lineWidth=3.4;c.beginPath();c.moveTo(12,10);c.lineTo(16,-22);c.stroke();c.strokeStyle=staff;c.lineWidth=1.8;c.beginPath();c.moveTo(12,9);c.lineTo(16,-22);c.stroke();c.shadowColor=staff;c.shadowBlur=10;c.fillStyle=staff;c.beginPath();c.arc(16,-24,4.3,0,Math.PI*2);c.fill();c.shadowBlur=0;
 }
 c.restore();
}
// Fallbacks until world.js enhances the renderer; keep the loop alive on slow loads.
function drawRegionWorld(c,ox,oy,w,h,now){c.fillStyle='#172018';c.fillRect(0,0,w,h)}
function entityPosition(e,now){return e}
function getTerrain(r){return null}
function drawWorld(now){let r=canvas.getBoundingClientRect(),w=r.width,h=r.height,p=me();if(p){let pos=entityPosition(p,now);cam.x+=(pos.x-cam.x)*.18;cam.y+=(pos.y-cam.y)*.18;if(hasPointerAim)setAimFromPointer()}const WS=worldSize();cam.x=WS.w>w?Math.max(w/2,Math.min(WS.w-w/2,cam.x)):WS.w/2;cam.y=WS.h>h?Math.max(h/2,Math.min(WS.h-h/2,cam.y)):WS.h/2;ctx.clearRect(0,0,w,h);if(screenShake>0.1){screenShakeX=(Math.random()-0.5)*screenShake;screenShakeY=(Math.random()-0.5)*screenShake;screenShake*=screenShakeDecay;if(screenShake<0.12){screenShake=0;screenShakeX=0;screenShakeY=0;}}let ox=w/2-cam.x+screenShakeX,oy=h/2-cam.y+screenShakeY;drawRegionWorld(ctx,ox,oy,w,h,now);
// nodes
if(snap)for(const n of snap.nodes){if(!n.active)continue;let x=n.x+ox,y=n.y+oy;if(x<-25||x>w+25||y<-25||y>h+25)continue;const cols={wood:'#ba9161',herb:'#a6d979',ore:'#91abb0',crystal:'#8de5d8'};ctx.fillStyle=cols[n.kind]||'#ddd';if(n.kind==='wood'){ctx.fillRect(x-7,y-9,14,18);ctx.fillRect(x-12,y-7,7,5);ctx.fillRect(x+5,y+1,8,5)}else if(n.kind==='herb'){ctx.fillRect(x-2,y-8,4,17);ctx.fillRect(x-8,y-4,6,3);ctx.fillRect(x+2,y-1,7,3);ctx.fillRect(x-6,y-11,5,4)}else{ctx.fillRect(x-8,y-4,16,10);ctx.fillStyle=cols[n.kind];ctx.fillRect(x-5,y-10,8,8);ctx.fillStyle='#ffffff55';ctx.fillRect(x-4,y-8,3,3)}ctx.fillStyle='#171c14';ctx.fillRect(x-12,y+11,24,2)}
// mob render
if(snap)for(const m of snap.mobs){let mp=entityPosition(m,now);let x=mp.x+ox,y=mp.y+oy;if(x<-90||x>w+90||y<-90||y>h+90)continue;let spec={slime:['#8fce73',20],wolf:['#b7c7b5',22],boar:['#a7805b',26],wisp:['#72d9cf',20],stone:['#b39c7b',28],ashling:['#d38e67',23],ashguard:['#c6ad86',34],colossus:['#df9c65',55],void_wraith:['#7b2cbf',28],astral_titan:['#00f0ff',58],obsidian_sentinel:['#86718f',36],starseer:['#d9a6ef',30],ancient_warden:['#91cb79',56]}[m.kind]||['#aabb99',20],s=spec[1]*(m.kind==='echo_dragon'?1.62:m.boss?1.22:1);let tele=!!m.telegraphing;if(['echo_dragon','rift_knight','frost_wyrm'].includes(m.kind)){ctx.save();let aura=ctx.createRadialGradient(x,y,3,x,y,s*2.2);aura.addColorStop(0,m.kind==='echo_dragon'?'#ff78bd55':m.kind==='rift_knight'?'#ca88ff55':'#87f0ff55');aura.addColorStop(1,'#00000000');ctx.fillStyle=aura;ctx.beginPath();ctx.arc(x,y,s*2.2,0,Math.PI*2);ctx.fill();ctx.restore()}if(tele){ctx.strokeStyle='#ffdb72';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(x,y,s+8,s+5,0,0,Math.PI*2);ctx.stroke()}drawMobSprite(ctx,m,x,y,s,now,spec[0]);
ctx.fillStyle='#182016';ctx.fillRect(x-s,y-s-13,s*2,4);ctx.fillStyle=m.kind==='colossus'?'#ed8a56':'#df6d5c';ctx.fillRect(x-s,y-s-13,s*2*Math.max(0,m.hp/m.max_hp),4);ctx.fillStyle='#f4ecd1';ctx.font=m.boss?'bold 10px system-ui':'9px system-ui';ctx.textAlign='center';ctx.fillText(`${m.boss?'BOSS · ':''}${mobNames[m.kind]} · ур. ${m.level}`,x,y-s-19);ctx.textAlign='left'}
// arrows
if(snap)for(const a of snap.arrows){ctx.save();let semantic=a.element==='ice'?'Лёд':a.spell_kind||a.spell_id||'Огонь';const pc={"Огонь":["#ff552e","#ffb347","#fff2a8"],"Лёд":["#40d9ff","#a4f3ff","#ffffff"],"Молния":["#fff05a","#6beaff","#ffffff"],"Исцеление":["#53dfa0","#b4ffda","#ffffff"],"Тень":["#8e62ed","#d1a4ff","#fff0ff"],"Эхо":["#4bd7d0","#a8fff0","#ffffff"],"Яд":["#63e85b","#caff72","#ffffb4"],"Терни":["#61c953","#b5ef7a","#efffd0"],"Звёзды":["#ff9940","#ffe878","#ffffff"],"Аркана":["#bd77ff","#6edfff","#fff1c8"]};let c=a.spell_palette?.colors||pc[semantic]||pc["Огонь"],px=a.x+ox,py=a.y+oy,ang=Math.atan2(a.vy,a.vx),variant=Number(a.spell_variant||0)%97;ctx.globalCompositeOperation='lighter';ctx.translate(px,py);ctx.rotate(ang);ctx.shadowColor=c[0];ctx.shadowBlur=25;let speed=Math.hypot(a.vx||0,a.vy||0);ctx.globalAlpha=.75;ctx.strokeStyle=c[0];ctx.lineWidth=3+Math.min(5,Number(a.spell_mastery||1));ctx.beginPath();ctx.moveTo(-22-Math.min(4,Number(a.spell_mastery||1))*3,0);ctx.lineTo(2,0);ctx.stroke();for(let j=0;j<6;j++){let phase=(now/55+j*.31+variant*.001)%1;ctx.globalAlpha=.55*(1-phase);ctx.fillStyle=c[j%3];ctx.beginPath();ctx.arc(-6-phase*(12+j*2),Math.sin(now/48+j*2)*((j%3)+2),2+j%2,0,Math.PI*2);ctx.fill()}ctx.globalAlpha=1;ctx.fillStyle=c[1];ctx.beginPath();ctx.moveTo(13,0);ctx.quadraticCurveTo(1,12,-9,0);ctx.quadraticCurveTo(1,-12,13,0);ctx.fill();ctx.fillStyle=c[2];ctx.beginPath();ctx.arc(1,0,4.5,0,Math.PI*2);ctx.fill();ctx.restore()}// other players then local
if(snap)for(const q of snap.players){let qp=entityPosition(q,now);let x=qp.x+ox,y=qp.y+oy;if(x<-50||x>w+50||y<-50||y>h+50)continue;let local=q.id===myId;let equipped=q.gear||'traveler',armorColors={traveler:'#547c50',wolf_cloak:'#778d8d',moss_guard:'#8bb56b',marsh_armor:'#9c815e',moonweave:'#9bc8bd',ash_plate:'#a8aaa4',colossus_core:'#f49a60',glacier_mantle:'#8ee8f2',rift_plate:'#bd85ed',obsidian_shell:'#887090',starseer_robe:'#d2a4d7',elder_mantle:'#8ec884'},rarityColors={traveler:'#d6c27b',wolf_cloak:'#86cf91',moss_guard:'#86cf91',marsh_armor:'#79bce2',moonweave:'#c49be8',ash_plate:'#c49be8',colossus_core:'#f1b75e',glacier_mantle:'#8ee8f2',rift_plate:'#bd85ed',obsidian_shell:'#887090',starseer_robe:'#d2a4d7',elder_mantle:'#8ec884'};drawAvatarSprite(ctx,q,x,y,armorColors[equipped]||'#547c50',rarityColors[equipped]||'#f0e6c6',local,equipped);drawCombatAnimation(ctx,q,x,y,now);ctx.fillStyle='#fff3d0';ctx.font=local?'bold 10px system-ui':'10px system-ui';ctx.textAlign='center';ctx.lineWidth=3;ctx.strokeStyle='#111a';ctx.strokeText(q.name,x,y-34);ctx.fillText(q.name,x,y-34);ctx.textAlign='left'}
updateAndDrawParticles(ctx, ox, oy);drawGroundAndAbilityFx(now,ox,oy);
// local attack visualization
for(const fx of attackFx){if(now>fx.until)continue;if(fx.fx){let x=fx.x+ox,y=fx.y+oy;ctx.save();
ctx.globalCompositeOperation='lighter';
let ang=Math.atan2(fx.ay,fx.ax);
let weaponColors={daggers:'#00f5d4',spear:'#ffd166',scythe:'#9d4edd',astral_blade:'#f72585',archon_staff:'#4cc9f0',axe:'#d9a66d',bow:'#c3e48f',sword:'#fff0ad',iron_sword:'#79bce2'};
let col=weaponColors[fx.weapon]||'#fff0ad';
let arcRad=Number.isFinite(fx.arcCos)?Math.acos(Math.max(-.99,Math.min(.99,fx.arcCos))):fx.weapon==='scythe'?1.2:fx.weapon==='daggers'?0.9:fx.weapon==='spear'?0.25:0.75;
let slashDist=Number(fx.range)||(fx.weapon==='spear'?76:44);
ctx.strokeStyle=col;ctx.lineWidth=fx.weapon==='scythe'?7:fx.weapon==='daggers'?3:5;ctx.shadowColor=col;ctx.shadowBlur=12;
ctx.beginPath();ctx.arc(x,y,slashDist,ang-arcRad,ang+arcRad);ctx.stroke();
if(fx.weapon==='spear'){ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+Math.cos(ang)*slashDist,y+Math.sin(ang)*slashDist);ctx.stroke();}
ctx.restore();}else{ctx.fillStyle='#ffedb3';ctx.font='bold 13px system-ui';ctx.fillText(fx.text,fx.x+ox,fx.y+oy-(fx.until-now)/12)}}attackFx=attackFx.filter(a=>now<a.until);
// Server spell flashes and area indicators.
for(const fx of spellFx){let life=Math.max(0,Math.min(1,(fx.until-now)/1500)),t=1-life,x=fx.x+ox,y=fx.y+oy,r=fx.radius||90,semantic=fx.kind||fx.spell;const palette={"Огонь":["#ff693d","#ffc45c","#fff2b0"],"Молния":["#fff078","#7be9ff","#fff9d5"],"Исцеление":["#60e7b0","#caffdd","#ffffff"],"Терни":["#8bdc62","#d3ff84","#f3ffd0"],"Яд":["#7df06b","#d4ff73","#efffb4"],"Лёд":["#65dfff","#b5f5ff","#ffffff"],"Всплеск":["#bd75ff","#f09cff","#fff0ff"],"Звёзды":["#ffb347","#fff08a","#ffffff"],"Тень":["#9162dd","#d7a5ff","#fff0ff"],"Эхо":["#52d7d0","#a7fff0","#fffbd2"],"Душа":["#fa77c9","#ffc5eb","#ffffff"],"Аркана":["#b678ff","#69e8ff","#fff0c2"]};let c=fx.palette?.colors||palette[semantic]||palette[fx.spell]||palette["Аркана"];ctx.save();ctx.globalCompositeOperation='lighter';ctx.globalAlpha=Math.min(.95,life*1.2);ctx.lineWidth=2.5;
// Layered expanding rings and charged core
for(let ring=0;ring<Math.min(6,2+(fx.mastery||1));ring++){let phase=(t*1.8+ring/Math.min(6,2+(fx.mastery||1))+(Number(fx.variant||0)%100)*.0001)%1,rr=r*(.22+phase*.9),a=Math.max(0,1-phase);ctx.globalAlpha=a*.56;ctx.strokeStyle=c[ring%3];ctx.lineWidth=ring===0?3:1.7;ctx.beginPath();ctx.arc(x,y,rr,0,Math.PI*2);ctx.stroke();if(ring<2){ctx.globalAlpha=a*.12;ctx.fillStyle=c[ring];ctx.beginPath();ctx.arc(x,y,rr,0,Math.PI*2);ctx.fill()}}
// Rune orbit, beams, deterministic sparks
ctx.globalAlpha=life*.82;ctx.strokeStyle=c[1];ctx.lineWidth=1.5;let sides=semantic==='Молния'?8:6,rot=t*1.8+(Number(fx.variant||0)%628)/100;ctx.beginPath();for(let j=0;j<sides;j++){let ang=rot+j*Math.PI*2/sides,rr=r*(.45+.05*Math.sin(now/90+j));let px=x+Math.cos(ang)*rr,py=y+Math.sin(ang)*rr;if(!j)ctx.moveTo(px,py);else ctx.lineTo(px,py)}ctx.closePath();ctx.stroke();
for(let j=0;j<28;j++){let seed=j*2.39996+(fx.spell.length||1)*.73,ang=seed+t*(j%2?2.4:-1.8),travel=r*(.28+t*(.65+(j%5)*.08)),px=x+Math.cos(ang)*travel,py=y+Math.sin(ang)*travel;ctx.globalAlpha=life*(.35+.55*((j%4)/4));ctx.fillStyle=c[j%3];ctx.shadowColor=c[j%3];ctx.shadowBlur=8+(fx.rarity||1)*2;let sz=1.5+(j%3)*.9;ctx.save();ctx.translate(px,py);ctx.rotate(ang+t*5);ctx.beginPath();if(j%3===0){ctx.moveTo(0,-sz*2);ctx.lineTo(sz,0);ctx.lineTo(0,sz*2);ctx.lineTo(-sz,0);ctx.closePath()}else{ctx.arc(0,0,sz,0,Math.PI*2)}ctx.fill();ctx.restore()}
// Element-specific signature: lightning forks, healing petals, frost crystals, fire spiral, shadow orbit
ctx.shadowBlur=14;ctx.shadowColor=c[0];ctx.strokeStyle=c[0];ctx.fillStyle=c[0];ctx.lineWidth=3;ctx.globalAlpha=life*.92;
if(semantic==='Молния'){for(let k=0;k<5;k++){let a=k*1.256+rot;ctx.beginPath();ctx.moveTo(x+Math.cos(a)*r*.12,y+Math.sin(a)*r*.12);for(let q=1;q<=4;q++){let rr=r*(.16+q*.16),aa=a+(q%2?-.2:.19);ctx.lineTo(x+Math.cos(aa)*rr,y+Math.sin(aa)*rr)}ctx.stroke()}}
else if(semantic==='Лёд'){for(let k=0;k<8;k++){let a=k*Math.PI/4+rot*.25;ctx.save();ctx.translate(x+Math.cos(a)*r*.48,y+Math.sin(a)*r*.48);ctx.rotate(a);ctx.beginPath();ctx.moveTo(0,-13);ctx.lineTo(7,4);ctx.lineTo(0,1);ctx.lineTo(-7,4);ctx.closePath();ctx.fill();ctx.restore()}}
else if(semantic==='Исцеление'||semantic==='Душа'){for(let k=0;k<10;k++){let a=k*Math.PI/5+rot*.4,rr=r*.24;ctx.save();ctx.translate(x+Math.cos(a)*rr,y+Math.sin(a)*rr);ctx.rotate(a);ctx.beginPath();ctx.ellipse(0,-13,5,13,0,0,Math.PI*2);ctx.fill();ctx.restore()}ctx.beginPath();ctx.arc(x,y,r*(.18+.04*Math.sin(now/70)),0,Math.PI*2);ctx.stroke()}
else if(semantic==='Терни'||semantic==='Яд'){for(let k=0;k<12;k++){let a=k*Math.PI/6+rot*.3,rr=r*.72;ctx.beginPath();ctx.moveTo(x+Math.cos(a)*rr,y+Math.sin(a)*rr);ctx.lineTo(x+Math.cos(a+.18)*(rr-15),y+Math.sin(a+.18)*(rr-15));ctx.lineTo(x+Math.cos(a)*(rr-23),y+Math.sin(a)*(rr-23));ctx.stroke()}}
else if(semantic==='Тень'||semantic==='Эхо'){for(let k=0;k<4;k++){ctx.beginPath();ctx.ellipse(x,y,r*(.2+k*.11),r*(.1+k*.07),rot+k*.8,0,Math.PI*1.65);ctx.stroke()}}
else{for(let k=0;k<4;k++){let a=rot+k*Math.PI/2;ctx.beginPath();ctx.arc(x,y,r*(.16+k*.045),a,a+1.6);ctx.stroke()}if(semantic==='Огонь'||semantic==='Звёзды'){for(let k=0;k<5;k++){let a=rot+k*1.256,rr=r*(.18+t*.35);ctx.beginPath();ctx.arc(x+Math.cos(a)*rr,y+Math.sin(a)*rr,3+(k%3),0,Math.PI*2);ctx.fill()}}}
// Nameplate makes custom spell identity legible
if(fx.name){ctx.globalCompositeOperation='source-over';ctx.globalAlpha=Math.min(1,life*1.6);ctx.font='bold 12px system-ui';ctx.textAlign='center';ctx.lineWidth=3;ctx.strokeStyle='#111b';ctx.strokeText(fx.name,x,y-r*.62);ctx.fillStyle=c[2];ctx.fillText(fx.name,x,y-r*.62)}ctx.restore()}spellFx=spellFx.filter(fx=>now<fx.until);if(snap?.thorn_fields){for(const f of snap.thorn_fields){let x=f.x+ox,y=f.y+oy;ctx.save();ctx.strokeStyle='#8fe77a';ctx.fillStyle='#91da641d';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,f.radius,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.restore()}}
// Biome light pools and subtle ground grain
ctx.save();ctx.globalAlpha=.13;for(let i=0;i<18;i++){let wx=(i*271+113)%worldSize().w,wy=(i*397+219)%worldSize().h,sx=wx+ox,sy=wy+oy;if(sx< -120||sx>w+120||sy< -120||sy>h+120)continue;let z=snap?.region?.id||'camp',col=z==='glacier'?'#bceeff':z==='rift'?'#d99aff':z==='marsh'?'#8bd7b8':'#f0d88a';let glow=ctx.createRadialGradient(sx,sy,1,sx,sy,48);glow.addColorStop(0,col);glow.addColorStop(1,'#00000000');ctx.fillStyle=glow;ctx.fillRect(sx-48,sy-48,96,96)}ctx.restore();
// local character highlight
if(p){let px=p.x+ox,py=p.y+oy;ctx.save();let aura=ctx.createRadialGradient(px,py,2,px,py,28);aura.addColorStop(0,'#ffe7a31b');aura.addColorStop(1,'#ffe7a300');ctx.fillStyle=aura;ctx.beginPath();ctx.arc(px,py,28,0,Math.PI*2);ctx.fill();ctx.restore()}
// Spell target preview: server clamps spells to 420 units from the caster.
if(p&&hasPointerAim){const t=pointerWorld(),dx=t.x-p.x,dy=t.y-p.y,d=Math.hypot(dx,dy),range=420,k=d>range?range/d:1,tx=p.x+dx*k,ty=p.y+dy*k;ctx.save();ctx.strokeStyle='#baffdf88';ctx.lineWidth=1;ctx.setLineDash([4,5]);ctx.beginPath();ctx.moveTo(p.x+ox,p.y+oy);ctx.lineTo(tx+ox,ty+oy);ctx.stroke();ctx.setLineDash([]);if(d>range){ctx.strokeStyle='#ffe38f';ctx.beginPath();ctx.arc(tx+ox,ty+oy,8,0,Math.PI*2);ctx.stroke()}ctx.restore()}
// Bow range guide follows the cursor and grows with draw charge.
if(p&&p.weapon_catalog?.[p.weapon]?.kind==='bow'&&hasPointerAim){const charge=Number(p.attack?.charge??(chargeLocal?Math.min(1,(performance.now()-chargeStart)/(attackChargeDuration(p)*1000)):0)),range=180+620*Math.max(0,Math.min(1,charge)),sx=p.x+ox,sy=p.y+oy,ex=sx+aim.x*range,ey=sy+aim.y*range;ctx.save();ctx.strokeStyle=chargeLocal?'#dfffa9cc':'#dfffa966';ctx.lineWidth=1.5;ctx.setLineDash([6,5]);ctx.beginPath();ctx.moveTo(sx,sy);ctx.lineTo(ex,ey);ctx.stroke();ctx.setLineDash([]);ctx.beginPath();ctx.arc(ex,ey,5,0,Math.PI*2);ctx.stroke();ctx.font='11px system-ui';ctx.textAlign='center';ctx.fillText(`${Math.round(range)} ед.`,ex,ey-10);ctx.restore()}
// Melee wind-up cone uses the same range and angle as the server hit test.
if(p&&chargeLocal&&p.weapon_catalog?.[p.weapon]?.kind!=='bow'){const spec=p.weapon_catalog[p.weapon]||{},charge=Math.min(1,(performance.now()-chargeStart)/(attackChargeDuration(p)*1000)),range=Number(spec.range||44)+12*charge,half=Math.acos(Math.max(-.99,Math.min(.99,Number(spec.arc??.28)))),angle=Math.atan2(aim.y,aim.x),sx=p.x+ox,sy=p.y+oy;ctx.save();ctx.globalAlpha=.08+.12*charge;ctx.fillStyle=charge>.8?'#ffe08c':'#b9d889';ctx.beginPath();ctx.moveTo(sx,sy);ctx.arc(sx,sy,range,angle-half,angle+half);ctx.closePath();ctx.fill();ctx.globalAlpha=.7;ctx.strokeStyle=charge>.8?'#ffe08c':'#c8e09b';ctx.lineWidth=1.5;ctx.setLineDash([4,4]);ctx.beginPath();ctx.arc(sx,sy,range,angle-half,angle+half);ctx.stroke();ctx.setLineDash([]);ctx.restore()}
// aim reticle
if(p){let wp=hasPointerAim?pointerWorld():{x:p.x+aim.x*74,y:p.y+aim.y*74},ax=wp.x+ox,ay=wp.y+oy;ctx.strokeStyle='#fff1bdaa';ctx.lineWidth=1;ctx.beginPath();ctx.arc(ax,ay,5,0,7);ctx.moveTo(ax-8,ay);ctx.lineTo(ax+8,ay);ctx.moveTo(ax,ay-8);ctx.lineTo(ax,ay+8);ctx.stroke()}
// vignette
let grad=ctx.createRadialGradient(w/2,h/2,Math.min(w,h)*.25,w/2,h/2,Math.max(w,h)*.75);grad.addColorStop(0,'#0000');grad.addColorStop(1,'#10171144');ctx.fillStyle=grad;ctx.fillRect(0,0,w,h);
}
function drawMap(c,context,large=false){
 let w=c.clientWidth,h=c.clientHeight;if(!w||!h||!snap?.region)return;context.clearRect(0,0,w,h);
 const W=worldSize(),sx=x=>x/W.w*w,sy=y=>y/W.h*h;
 context.fillStyle=snap.region.dark;context.fillRect(0,0,w,h);
 const terrain=getTerrain(snap.region);if(terrain)context.drawImage(terrain,0,0,w,h);
 context.fillStyle='#0b141055';context.fillRect(0,0,w,h);
 for(const n of snap.nodes||[])if(n.active){context.fillStyle=n.kind==='crystal'?'#96e7dd':n.kind==='shard'?'#d7a4ff':'#c8db8b';context.fillRect(sx(n.x)-1,sy(n.y)-1,2,2)}
 for(const m of snap.mobs||[]){context.fillStyle=m.boss?'#ff6b5d':'#edaa6d';context.beginPath();context.arc(sx(m.x),sy(m.y),m.boss?3:1.6,0,Math.PI*2);context.fill()}
 for(const n of snap.region.npcs||[]){context.fillStyle=n.role==='merchant'?'#e7c77d':'#9ccbd8';context.fillRect(sx(n.x)-2,sy(n.y)-2,4,4)}
 for(const portal of snap.portals||[]){context.strokeStyle='#bca6ff';context.lineWidth=1.5;context.strokeRect(sx(portal.x)-3,sy(portal.y)-3,6,6)}
 for(const q of snap.players||[]){context.fillStyle=q.id===myId?'#fff6d0':'#7de0c0';context.beginPath();context.arc(sx(q.x),sy(q.y),q.id===myId?3.5:2.5,0,Math.PI*2);context.fill()}
 context.strokeStyle='#fff6d066';context.lineWidth=1;context.strokeRect(sx(cam.x-360),sy(cam.y-240),720/W.w*w,480/W.h*h);
}
function frame(now){inputFrame();if(window.echoMoving&&!chargeLocal){sfxCall('step',!!window.echoRun)}{const mo=activeGameMenu();if(window.__echoMenuWas===undefined)window.__echoMenuWas=mo;else if(mo!==window.__echoMenuWas){window.__echoMenuWas=mo;sfxCall(mo?'open':'close')}}if(chargeLocal){let p=me(),pct=p?Math.min(1,(now-chargeStart)/(attackChargeDuration(p)*1000)):0;$('chargeFill').style.width=`${pct*100}%`;if($('mChargeFill'))$('mChargeFill').style.width=`${pct*100}%`;$('chargePercent').textContent=`${Math.round(pct*100)}%`;$('chargeTier').textContent=pct<.35?'НАБОР':pct<.8?'СИЛЬНЕЕ':'ПОЛНЫЙ УДАР';$('attackButton').style.setProperty('--charge',pct)}else{$('attackButton').style.setProperty('--charge',0);if($('mChargeFill'))$('mChargeFill').style.width='0'}drawWorld(now);drawMap(mini,mctx,false);requestAnimationFrame(frame)}requestAnimationFrame(frame);
/* ==== МЕНЮ ПЕРСОНАЖА: характеристики + экипировка с всплывающими подсказками ==== */
const CHAR_STAT_META={might:['⚔','Сила','Урон ближнего боя и выстрелов'],vitality:['♥','Живучесть','Запас здоровья'],agility:['➶','Ловкость','Скорость бега и рывка'],mana_regen:['✧','Восстановление маны','Регенерация маны и её запас'],magic_damage:['☄','Урон магии','Сила всех заклинаний'],insight:['✵','Прозорливость','Больше опыта от побед и монет из-за удачи'],precision:['◎','Точность','Шанс критического удара'],fortune:['♣','Удача','Шанс редкой добычи']};
function weaponKindLabel(kind){return kind==='bow'?'Дальний бой':kind==='staff'?'Магический посох':'Ближний бой'}
function weaponIconGlyph(kind){return kind==='bow'?'➶':kind==='staff'?'✦':'⚔'}
function tipRow(label,value){return `<span class="tipLine"><span>${label}</span><b>${value}</b></span>`}
function buildWeaponTip(p){const id=p.weapon,w=(p.weapon_catalog||{})[id]||{},up=Number(p.upgrades?.weapon?.[id]||0);
 const ench=Object.entries(p.enchantments?.weapon?.[id]||{}).filter(([,lv])=>Number(lv)>0);
 const baseDmg=Number(w.damage||0)+Number(w.bonus||0)+(w.kind==='staff'?0:up*6);
 let html=`<strong>${safeText(w.name||weaponNames[id]||id)}${up?` +${up}`:''}</strong><span class="tipRarity rarity-${w.rarity||'common'}">${rarityNames[w.rarity]||'Обычное'}</span>`;
 html+=tipRow('Тип',weaponKindLabel(w.kind));
 if(w.kind==='staff')html+=tipRow('Урон магии',`+${up*6} за уровень улучшения`),html+=tipRow('Сила чар',`+${Math.round(Number(w.spell_power||0)*100)}%`);
 else html+=tipRow('Урон',String(baseDmg));
 if(w.range)html+=tipRow('Дальность',`${Math.round((Number(w.range)||44)*(me()?.melee_reach_factor||p.melee_reach_factor||1))} ед.`);
 if(w.arc!=null&&w.kind!=='bow')html+=tipRow('Широкая дуга',w.arc<=.15?'нет':w.arc>=.35?'да, широкая':'средняя');
 if(w.cooldown!=null)html+=tipRow('Скорость',`${(1/Math.max(.05,Number(w.cooldown)||.3)).toFixed(1)} уд/с`);
 if(w.charge!=null)html+=tipRow('Набор силы',`${Number(w.charge).toFixed(2)} с до полного`);
 if(w.stamina!=null)html+=tipRow('Расход выносливости',String(Math.round(Number(w.stamina))));
 for(const[eId,lv]of ench){const en=(p.enchant_catalog||{})[eId];if(en)html+=tipRow(`${en.name} · ${lv} ур.`,en.description)}
 if(w.lore)html+=`<em class="tipLore">${safeText(w.lore)}</em>`;
 return html}
function buildGearTip(p){const id=p.gear,g=(p.gear_catalog||{})[id]||{},up=Number(p.upgrades?.gear?.[id]||0);
 const ench=Object.entries(p.enchantments?.gear?.[id]||{}).filter(([,lv])=>Number(lv)>0);
 const def=Number(g.defense??gearDefense[id]??0)+up*3;
 let html=`<strong>${safeText(g.name||gearNames[id]||id)}${up?` +${up}`:''}</strong><span class="tipRarity rarity-${g.rarity||'common'}">${rarityNames[g.rarity]||'Обычная'}</span>`;
 html+=tipRow('Защита',String(def));
 for(const[eId,lv]of ench){const en=(p.enchant_catalog||{})[eId];if(en)html+=tipRow(`${en.name} · ${lv} ур.`,en.description)}
 if(g.lore)html+=`<em class="tipLore">${safeText(g.lore)}</em>`;
 return html}
function updateCharacterPanel(p){if(!p)return;
 const wKind=p.weapon_catalog?.[p.weapon]?.kind||'melee';
 const wi=$('weaponIcon');if(wi){wi.textContent=weaponIconGlyph(wKind);wi.classList.remove('rareGlow');if(['epic','legendary'].includes(p.weapon_catalog?.[p.weapon]?.rarity))wi.classList.add('rareGlow')}
 const wn=$('weaponName');if(wn)wn.textContent=p.weapon_catalog?.[p.weapon]?.name||weaponNames[p.weapon]||p.weapon;
 const gi=$('gearIcon');if(gi)gi.textContent='◆';
 const gn=$('gearName');if(gn)gn.textContent=p.gear_catalog?.[p.gear]?.name||gearNames[p.gear]||'Нет';

 const dl=$('defenseLabel');if(dl)dl.textContent=`броня ${p.gear_catalog?.[p.gear]?.defense??gearDefense[p.gear]??0}${Number(p.upgrades?.gear?.[p.gear]||0)?` (+${Number(p.upgrades?.gear?.[p.gear]||0)*3})`:''}`;
 const clm=$('charLevelMini');if(clm)clm.textContent=`ур. ${p.level}`;
 renderCharOverlay(p)}
function renderCharOverlay(p){const el=$('charOverlay');if(!el||getComputedStyle(el).display==='none'||!p)return;
 const meta=$('charMeta');if(meta)meta.textContent=`${p.name} · ${p.class_name||'Путник'} · ур. ${p.level}`;
 const pts=Math.max(0,Number(p.skill_points)||0),cp=$('charPoints');
 if(cp){cp.textContent=`Очки развития: ${pts}`;cp.classList.toggle('hasPoints',pts>0)}
 const host=$('charStatsList');
 if(host){const view=p.upgrades_view||{};
  // Rows and their "+" buttons are built once and only patched in place when
  // the server keeps refreshing the snapshot. Rebuilding the DOM on every tick
  // destroyed the button mid-click, so upgrading a skill required hitting the
  // narrow gap between two state updates.
  if(!host.dataset.built){
   host.replaceChildren(...Object.keys(CHAR_STAT_META).map(key=>{const [icon,name]=CHAR_STAT_META[key],row=document.createElement('div');
    row.className='statRow';row.dataset.statRow=key;
    row.innerHTML=`<span class="sIcon">${icon}</span><span class="sName"><b>${name}</b><small></small></span><b class="sVal"></b>`;
    const btn=document.createElement('button');btn.type='button';btn.className='upgrade';btn.dataset.stat=key;btn.textContent='+';
    row.appendChild(btn);return row}));
   host.dataset.built='1'}
  for(const key of Object.keys(CHAR_STAT_META)){const row=host.querySelector(`[data-stat-row="${key}"]`);if(!row)continue;
   const effect=view[key]?.effect||CHAR_STAT_META[key][2];
   row.title=effect;
   row.querySelector('.sName small').textContent=effect;
   const lvl=upgradeLevel(p,key);
   row.querySelector('.sVal').textContent=`${lvl}${LEVEL_STATS.includes(key)?' ур.':''}`;
   refreshUpgradeButton(row.querySelector('.upgrade'),p)}}
 const sw=$('slotWeapon'),sa=$('slotArmor');
 if(sw){const w=p.weapon_catalog?.[p.weapon]||{};sw.className=`gearSlot rarity-${w.rarity||'common'}`;sw.tabIndex=0;
  $('slotWeaponIcon').textContent=weaponIconGlyph(w.kind||'melee');$('slotWeaponName').textContent=w.name||weaponNames[p.weapon]||p.weapon;$('slotWeaponTip').innerHTML=buildWeaponTip(p)}
 if(sa){const g=p.gear_catalog?.[p.gear]||{};sa.className=`gearSlot rarity-${g.rarity||'common'}`;sa.tabIndex=0;
  $('slotArmorName').textContent=g.name||gearNames[p.gear]||'Нет';$('slotArmorTip').innerHTML=buildGearTip(p)}}
let lastCharToggle=0;
const toggleCharacterReal=(open,force)=>{const el=$('charOverlay');if(!el)return;if(!force&&performance.now()-lastCharToggle<260)return;lastCharToggle=performance.now();
 const next=open??(getComputedStyle(el).display==='none');
 if(next){
  for(const other of ['gameMenuOverlay','keybindOverlay','accountOverlay']){const o=$(other);if(o)o.style.display='none'}
  el.style.display='flex';renderCharOverlay(me());$('closeCharacter').focus()}
 else el.style.display='none'}
toggleCharacter=toggleCharacterReal;
window.updateCharacterPanel=updateCharacterPanel;
if($('characterButton'))$('characterButton').onclick=()=>toggleCharacter();
if($('closeCharacter'))$('closeCharacter').onclick=()=>{lastCharToggle=0;toggleCharacter(false,true)};
for(const miniId of ['miniWeaponBtn','miniGearBtn']){const b=$(miniId);if(b)b.onclick=()=>toggleCharacter()}
// One delegated path for every "+" button (the character overlay rebuilds its
// rows, so per-button listeners would leak and double-handle clicks). The
// server validates the point pool; we never block the request locally.
document.addEventListener('click',e=>{const b=e.target.closest('.upgrade');if(!b)return;e.preventDefault();requestStatUpgrade(b)});
let miniTipEl=null;
function hideMiniTip(){if(miniTipEl){miniTipEl.remove();miniTipEl=null}}
function showMiniTip(btn,html){hideMiniTip();const tip=document.createElement('span');tip.className='gearTip is-floating';tip.innerHTML=html;document.body.appendChild(tip);miniTipEl=tip;
 const br=btn.getBoundingClientRect(),tr=tip.getBoundingClientRect();
 let left=Math.min(Math.max(8,br.left+br.width/2-tr.width/2),innerWidth-tr.width-8);
 let top=br.top-tr.height-10;if(top<8)top=br.bottom+10;
 tip.style.left=`${left}px`;tip.style.top=`${top}px`}
for(const [id,kind] of [['miniWeaponBtn','weapon'],['miniGearBtn','gear']]){const btn=$(id);if(!btn)continue;
 btn.addEventListener('pointerenter',()=>{const p=me();if(!p)return;showMiniTip(btn,kind==='weapon'?buildWeaponTip(p):buildGearTip(p))});
 btn.addEventListener('pointerleave',hideMiniTip);
 btn.addEventListener('focus',()=>{const p=me();if(!p)return;showMiniTip(btn,kind==='weapon'?buildWeaponTip(p):buildGearTip(p))});
 btn.addEventListener('blur',hideMiniTip)}
addEventListener('resize',hideMiniTip);addEventListener('scroll',hideMiniTip,true);

/* ==== ПЕРЕНАЗНАЧАЕМЫЕ КЛАВИШИ ИГРОВЫХ ДЕЙСТВИЙ (инвентарь, рывок, сбор и т.д.) ==== */
// Все объявления — в общей области видимости скрипта (см. начало файла), здесь только инициализация и логика.
RESERVED_ACTION_CODES=new Set(['Escape','Tab','Backspace','Delete','ControlLeft','ControlRight','AltLeft','AltRight','MetaLeft','MetaRight','CapsLock','NumLock','ScrollLock','PrintScreen','Home','End','PageUp','PageDown','Insert']);
actionKeys={...ACTION_KEY_DEFAULTS};
try{const raw=localStorage.getItem('echoActionKeysV2');if(raw){const saved=JSON.parse(raw);Object.keys(ACTION_KEY_DEFAULTS).forEach(k=>{if(typeof saved[k]==='string')actionKeys[k]=saved[k]})}}catch{}
// Shift is the sprint modifier now, so an old Shift dodge binding moves to V.
if(/^Shift/.test(actionKeys.dodge||''))actionKeys.dodge='KeyV';
function saveActionKeys(){try{localStorage.setItem('echoActionKeysV2',JSON.stringify(actionKeys))}catch{}}
function actionByCode(code){for(const k of Object.keys(ACTION_KEY_DEFAULTS)){if(actionKeys[k]===code)return k}return ''}
function isReservedCode(code){return RESERVED_ACTION_CODES.has(code)||/^(?:Control|Alt|Meta)/.test(code)}
function actionKeyLabel(act){const code=actionKeys[act];if(act==='dodge'&&/^Shift/.test(code))return code==='ShiftRight'?'ПК Shift':'ЛК Shift';if(act==='attack')return code==='Space'?'Пробел':keyLabel(code)||code;return keyLabel(code)||code||'—'}
movementCodeSet=()=>new Set(Object.values(movementCodes));
function actionCodeConflict(code,exceptAct){for(const k of Object.keys(ACTION_KEY_DEFAULTS)){if(k!==exceptAct&&actionKeys[k]===code)return k}return ''}applyActionToGame=(act,e)=>{switch(act){case 'character':toggleCharacter();return true;case 'inventory':if($('invOverlay').style.display==='flex')closeInventory();else openInventory();return true;case 'journal':if($('questOverlay')&&$('questOverlay').style.display==='flex')closeQuestJournal();else openQuestJournal();return true;case 'market':if($('marketOverlay').style.display==='flex')closeMarket();else openMarket();return true;case 'wizard':if($('wizardOverlay').style.display==='flex')closeStation('wizardOverlay');else openWizard();return true;case 'forge':if($('forgeOverlay').style.display==='flex')closeStation('forgeOverlay');else openForge();return true;case 'map':toggleMap();return true;case 'dodge':dodge();return true;case 'gather':sfxCall('gather');send({type:'gather_start'});return true;case 'interact':send({type:'interact'});return true;case 'potion':if(window.heroGesture)heroGesture('drink');sfxCall('drink');{const own=me();if(own)fxCall('heal',own.x,own.y)}send({type:'use_potion'});return true;case 'attack':beginAttack(e);return true;case 'chat':if(document.activeElement===$('chatInput'))return false;if(document.activeElement&&document.activeElement.blur)document.activeElement.blur();$('chatInput').focus();return true}};
setListeningAction=(act)=>{listeningActionKey=act;renderKeybindSections()};
function finishActionCapture(code){const act=listeningActionKey;listeningActionKey=null;if(!act){renderKeybindSections();return}
 const label=keyLabel(code)||code;
 if(isReservedCode(code)){toast('Эта клавиша зарезервирована системой. Esc — отмена.');renderKeybindSections();return}
 if(movementCodeSet().has(code)&&act!=='attack'){toast('Клавиша занята движением (WASD/стрелки). Esc — отмена.');renderKeybindSections();return}
 const clash=actionCodeConflict(code,act);
 if(clash){toast(`Клавиша уже назначена на действие «${ACTION_KEY_NAMES[clash]}». Сначала измените его.`);renderKeybindSections();return}
 if(abilityKeyCodeToId[code]){toast('Клавиша занята способностью — измените её в этом же меню.');renderKeybindSections();return}
 if(spellKeyCodeToId[code]){toast('Клавиша занята заклинанием — измените её в этом же меню.');renderKeybindSections();return}
 actionKeys[act]=code;saveActionKeys();syncActionKeyLabels();updateActionPanels(me());toast(`Действие «${ACTION_KEY_NAMES[act]}» → ${label}`);renderKeybindSections()}
// ACTION_KEY_NAMES объявлен в общей области видимости (см. начало скрипта)
const ACTION_BUTTON_BASE={inventoryButton:'СУМКА',marketButton:'ЛАВКА',wizardButton:'МАГ',forgeButton:'КУЗНЯ',mapButton:'КАРТА',potionButton:'НАСТОЙКА',dodgeButton:'РЫВОК'};
syncActionKeyLabels=()=>{for(const[id,act]of Object.entries([['inventoryButton','inventory'],['marketButton','market'],['wizardButton','wizard'],['forgeButton','forge'],['mapButton','map'],['potionButton','potion'],['dodgeButton','dodge']].reduce((o,[k,v])=>(o[k]=v,o),{}))){const b=$(id);if(!b)continue;const base=ACTION_BUTTON_BASE[id]||b.textContent.trim();b.innerHTML=`${base}<br><small class="btnKeyHint">${actionKeyLabel(act)}</small>`}}
document.addEventListener('keydown',e=>{if(!listeningActionKey||getComputedStyle($('keybindOverlay')).display==='none'||e.target.matches('input,textarea,select'))return;e.preventDefault();e.stopPropagation();if(e.key==='Escape'){listeningActionKey=null;renderKeybindSections();return}finishActionCapture(e.code)},true);

syncActionKeyLabels();
