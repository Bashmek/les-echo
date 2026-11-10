/* Encounter presentation. All geometry and phase decisions come from the server. */
(function(root) {
  'use strict';
  const clamp = n => Math.max(0, Math.min(1, n));
  const impacts=[];
  function onCombat(event) {
    if(event.kind==='monster_strike'&&event.attack_hint){
      impacts.push({attack:event.attack_hint,start:performance.now()});
      if(impacts.length>32)impacts.shift();
    }
  }
  function drawImpacts(c,now) {
    for(let i=impacts.length-1;i>=0;i--){
      const age=(now-impacts[i].start)/320;
      if(age>=1){impacts.splice(i,1);continue;}
      c.save();c.globalCompositeOperation='lighter';
      drawTelegraph(c,{...impacts[i].attack,progress:1,opacity:(1-age)*.65});
      c.restore();
    }
  }
  function selectBoss(mobs, player) {
    if (!player) return null;
    return mobs.filter(m => (m.boss || m.mini_boss) && m.hp > 0 && m.region === player.region &&
      Math.hypot(m.x-player.x,m.y-player.y) < 600)
      .sort((a,b)=>Math.hypot(a.x-player.x,a.y-player.y)-Math.hypot(b.x-player.x,b.y-player.y))[0] || null;
  }
  function drawTelegraph(c, a) {
    if (!a || !Number.isFinite(a.radius)) return;
    const progress = clamp(a.progress || 0);
    const color = a.phase >= 3 ? '#ff657c' : a.phase >= 2 ? '#ffad68' : '#ffd48b';
    c.save(); c.translate(a.x,a.y); c.rotate(a.angle || 0);
    function path(scale) {
      const r = a.radius * scale;
      c.beginPath();
      if(a.shape === 'line') c.rect(0,-a.width,r,a.width*2);
      else if(a.shape === 'cone') { c.moveTo(0,0); c.arc(0,0,r,-a.half_angle,a.half_angle); c.closePath(); }
      else c.arc(0,0,r,0,Math.PI*2);
    }
    const opacity=a.opacity??1;
    path(1); c.fillStyle='#2a101b'; c.globalAlpha=.30*opacity; c.fill();
    path(Math.max(.015,progress)); c.fillStyle=color; c.globalAlpha=(.12+progress*.17)*opacity; c.fill();
    path(1); c.strokeStyle=color; c.lineWidth=1.6; c.globalAlpha=.9*opacity; c.stroke();
    // Dashed inner edge remains readable on bright terrain and without color vision.
    c.setLineDash([4,5]); path(.96); c.strokeStyle='#fff3de'; c.lineWidth=.7; c.stroke(); c.setLineDash([]);
    c.rotate(-(a.angle || 0));
    c.beginPath(); c.arc(0,0,9,-Math.PI/2,-Math.PI/2+Math.PI*2*progress);
    c.lineWidth=2; c.strokeStyle='#fff8df'; c.stroke(); c.restore();
  }

  let panel, title, health, status, phase, kind, cast, tip, lastUpdate=0, currentId='';
  let victoryNotice, victory=null, activeRegion=null;
  const recentDefeats=new Map();
  function hideVictory() {
    victory=null;
    if(victoryNotice){victoryNotice.hidden=true;victoryNotice.textContent='';}
  }
  function reset(region) {
    activeRegion=region??null;
    recentDefeats.clear();impacts.length=0;currentId='';lastUpdate=-Infinity;
    hideVictory();
    if(panel)panel.hidden=true;
    if(tip){tip.hidden=true;tip.textContent='';}
  }
  function onDefeat(event,playerId,nowMs=performance.now()) {
    if(!event || !playerId || !Number.isFinite(nowMs) || !(event.boss||event.mini_boss) ||
      !Array.isArray(event.participants) || !event.participants.includes(playerId) ||
      !event.region || !event.mob || (activeRegion!==null&&event.region!==activeRegion))return false;
    for(const [key,until] of recentDefeats)if(until<=nowMs)recentDefeats.delete(key);
    const key=JSON.stringify([event.region,event.mob]);
    if(recentDefeats.has(key))return false;
    if(activeRegion===null)activeRegion=event.region;
    recentDefeats.set(key,nowMs+5000);
    if(recentDefeats.size>128)recentDefeats.delete(recentDefeats.keys().next().value);
    victory={until:nowMs+2600,region:event.region};
    if(typeof document!=='undefined') {
      if(!victoryNotice) {
        victoryNotice=document.createElement('div');victoryNotice.id='victoryNotice';
        victoryNotice.setAttribute('role','status');victoryNotice.setAttribute('aria-live','polite');
        victoryNotice.setAttribute('aria-atomic','true');document.body.appendChild(victoryNotice);
      }
      victoryNotice.textContent=`ПОБЕДА · ${event.name||event.kind||'Хранитель'}${event.mini_boss?' · МИНИ-БОСС':''}`;
      victoryNotice.hidden=false;
    }
    return true;
  }
  function init() {
    panel=document.createElement('section');panel.id='encounterHud';panel.hidden=true;
    panel.setAttribute('aria-label','Бой с боссом');
    panel.innerHTML='<div class="encounterEyebrow"><span class="encounterKind">ХРАНИТЕЛЬ ЗЕМЛИ</span><span class="encounterPhase"></span></div><div class="encounterTitle"></div><div class="encounterHealth" role="progressbar" aria-label="Здоровье босса" aria-valuemin="0" aria-valuemax="100"><i></i><b></b></div><small class="encounterStatus"></small><div class="encounterCast"></div>';
    document.body.appendChild(panel);
    document.body.classList.add('encounters-enabled');
    title=panel.querySelector('.encounterTitle');health=panel.querySelector('.encounterHealth');
    status=panel.querySelector('.encounterStatus');phase=panel.querySelector('.encounterPhase');kind=panel.querySelector('.encounterKind');cast=panel.querySelector('.encounterCast');
    tip=document.createElement('div');tip.id='combatCue';tip.hidden=true;document.body.appendChild(tip);
  }
  function update(mobs,p,names,now,menuOpen) {
    // Lifecycle and notice expiry use RAF time even when the HUD is throttled
    // or sprite animation is paused by hitstop.
    if(p&&p.region!==activeRegion)reset(p.region);
    if(victory&&now>=victory.until)hideVictory();
    if(victoryNotice)victoryNotice.hidden=!victory||!!menuOpen;
    if(typeof document === 'undefined' || now-lastUpdate<80)return;
    lastUpdate=now;if(!panel)init();
    const boss=selectBoss(mobs,p);
    panel.hidden=!boss||!!menuOpen;
    if(boss&&!menuOpen){
      const ratio=clamp(boss.hp/Math.max(1,boss.max_hp));
      if(currentId!==boss.id){currentId=boss.id;health.style.setProperty('--hp',`${ratio*100}%`);}
      kind.textContent=boss.mini_boss?'МИНИ-БОСС · ВЕСТНИК':'ХРАНИТЕЛЬ ЗЕМЛИ';
      panel.dataset.miniBoss=boss.mini_boss?'true':'false';
      panel.classList.toggle('isMiniBoss',!!boss.mini_boss);
      title.textContent=names[boss.kind]||boss.kind;
      phase.textContent=`${['','I · ПРОБУЖДЁН','II · НЕИСТОВСТВО','III · ЯРОСТЬ'][boss.phase||1]}`;
      panel.dataset.phase=String(boss.phase||1);
      health.style.setProperty('--hp',`${ratio*100}%`);health.setAttribute('aria-valuenow',String(Math.round(ratio*100)));
      status.textContent=`${Math.ceil(boss.hp).toLocaleString('ru-RU')} / ${boss.max_hp.toLocaleString('ru-RU')} · СТОЙКОСТЬ ${Math.round(boss.stagger||0)}%`;
      const a=boss.attack_hint;
      cast.textContent=a?`${a.name}${a.effect_label?` · ${a.effect_label}`:''} · ${Math.max(0,a.duration*(1-a.progress)).toFixed(1)} с`:boss.staggered?'СТОЙКОСТЬ СЛОМЛЕНА · АТАКУЙ':boss.recovering?'ОКНО ДЛЯ КОНТРАТАКИ':'СЛЕДИ ЗА ЗАМАХОМ';
      cast.style.setProperty('--cast',`${a?clamp(a.progress)*100:0}%`);
    }
    let message='';
    if(p&&!menuOpen&&p.hp>0){
      const threats=mobs.filter(m=>m.attack_hint&&Math.hypot(m.x-p.x,m.y-p.y)<220);
      if(threats.length)message='ВЫЙДИ ИЗ ПОДСВЕЧЕННОЙ ЗОНЫ · РЫВОК';
      else if(p.hp/p.max_hp<.3)message='МАЛО ЗДОРОВЬЯ · ОТСТУПИ И ИСПОЛЬЗУЙ НАСТОЙКУ';
      else if(p.stamina/p.max_stamina<.2)message='ВЫНОСЛИВОСТЬ НА ИСХОДЕ · ДАЙ ГЕРОЮ ПЕРЕДЫШКУ';
      else if(mobs.some(m=>m.staggered&&Math.hypot(m.x-p.x,m.y-p.y)<150))message='ВРАГ ОГЛУШЁН · ВРЕМЯ СИЛЬНОГО УДАРА';
    }
    tip.hidden=!message;tip.textContent=message;
  }
  const api={selectBoss,drawTelegraph,update,onCombat,drawImpacts,onDefeat,reset};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.EncounterView=api;
})(typeof window!=='undefined'?window:globalThis);
