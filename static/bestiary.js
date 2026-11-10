/* A field journal built from the server's real monster catalog. */
(function(root,factory){
  'use strict';
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.EchoBestiary=factory();
})(typeof window!=='undefined'?window:globalThis,function(){
  'use strict';
  const RANKS={unknown:'Неизвестно',discovered:'Открыто',studied:'Изучено',mastered:'Мастерство охоты'};
  const EMPTY_CATALOG=[];
  function countKills(value){return Number.isFinite(value)?Math.max(0,Math.min(1000000,Math.floor(value))):0;}
  function rankForKills(value){const n=countKills(value);return n>=15?'mastered':n>=5?'studied':n>=1?'discovered':'unknown';}
  function regionsOf(entry){return Array.isArray(entry.regions)?entry.regions:[];}
  function visibleEntry(entry,value){
    const kills=countKills(value),rank=rankForKills(kills);
    if(!kills)return {name:'Неизвестное существо',regions:regionsOf(entry),kills,rank,discovered:false};
    return {...entry,regions:regionsOf(entry),kills,rank,discovered:true};
  }
  function summarize(catalog,kills){
    const summary={total:catalog.length,discovered:0,studied:0,mastered:0,kills:0};
    for(const entry of catalog){const n=countKills((kills||{})[entry.id]);summary.kills+=n;if(n>=1)summary.discovered++;if(n>=5)summary.studied++;if(n>=15)summary.mastered++;}
    return summary;
  }
  function selectEntries(catalog,kills,filters={}){
    const query=String(filters.query||'').trim().toLocaleLowerCase('ru');
    return catalog.filter(entry=>{
      const view=visibleEntry(entry,(kills||{})[entry.id]);
      if(filters.region&&filters.region!=='all'&&!view.regions.some(r=>r.id===filters.region))return false;
      if(filters.status==='unknown'&&view.discovered)return false;
      if(filters.status==='discovered'&&!view.discovered)return false;
      if(filters.status==='studied'&&view.kills<5)return false;
      if(filters.status==='mastered'&&view.kills<15)return false;
      // Hidden identities must not be discoverable through the search box.
      return !query||[view.name,...view.regions.map(r=>r.name)].join(' ').toLocaleLowerCase('ru').includes(query);
    });
  }
  function create(options={}){
    const doc=options.document||(typeof document!=='undefined'?document:null);
    if(!doc)throw new Error('EchoBestiary.create requires a document');
    let overlay=null,grid,search,status,region,progress,progressFill,totals,resultCount,empty;
    let opened=false,latest=null,signature='',regionSignature='',returnFocus=null,catalogRef=null,catalogRevision=0;
    const filters={query:'',status:'all',region:'all'},focusables=[];
    function element(tag,className,text){const el=doc.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;return el;}
    function append(parent,...children){for(const child of children)parent.appendChild(child);return parent;}
    function option(select,value,label){const item=element('option','',label);item.value=value;select.appendChild(item);}
    function control(labelText,control){const label=element('label','bestiaryFilter');append(label,element('span','bestiaryFilterLabel',labelText),control);return label;}
    function ensure(){
      if(overlay)return;
      overlay=element('div','bestiaryOverlay');overlay.id='bestiaryOverlay';overlay.hidden=true;
      overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');overlay.setAttribute('aria-labelledby','bestiaryTitle');overlay.setAttribute('aria-describedby','bestiaryHelp');
      const panel=element('section','bestiaryPanel');
      const header=element('header','bestiaryHeader'),heading=element('div','bestiaryHeading');
      const title=element('h2','','Бестиарий');title.id='bestiaryTitle';
      append(heading,element('div','bestiaryEyebrow','ПОЛЕВОЙ ДНЕВНИК · ЭХО ЗЕМЕЛЬ'),title,element('p','bestiaryIntro','Каждая встреча оставляет след. Каждая победа — знание.'));
      const closeButton=element('button','bestiaryClose','✕');closeButton.type='button';closeButton.setAttribute('aria-label','Закрыть бестиарий');closeButton.addEventListener('click',close);
      append(header,heading,closeButton);focusables.push(closeButton);
      const summary=element('section','bestiarySummary');summary.setAttribute('aria-label','Прогресс коллекции');
      progress=element('strong','bestiaryProgressText');totals=element('span','bestiaryTotals');
      const progressBar=element('div','bestiaryProgress');progressBar.setAttribute('role','progressbar');progressBar.setAttribute('aria-label','Открытые виды');progressBar.setAttribute('aria-valuemin','0');
      progressFill=element('i');progressBar.appendChild(progressFill);
      append(summary,append(element('div','bestiarySummaryLine'),progress,totals),progressBar);
      const help=element('p','bestiaryHelp','1 победа — открытие · 5 — изучение · 15 — мастерство охоты. Ранги коллекции не изменяют силу героя.');help.id='bestiaryHelp';
      const toolbar=element('div','bestiaryToolbar');
      search=element('input','bestiaryInput');search.type='search';search.placeholder='Название или земля…';search.autocomplete='off';search.maxLength=120;
      status=element('select','bestiarySelect');for(const [value,label] of [['all','Все записи'],['unknown','Неизвестные'],['discovered','Открытые'],['studied','Изученные · 5+'],['mastered','Мастерство · 15+']])option(status,value,label);
      region=element('select','bestiarySelect');option(region,'all','Все земли');
      append(toolbar,control('Поиск',search),control('Знание',status),control('Земля',region));focusables.push(search,status,region);
      search.addEventListener('input',()=>{filters.query=search.value;render();});
      status.addEventListener('change',()=>{filters.status=status.value;render();});
      region.addEventListener('change',()=>{filters.region=region.value;render();});
      const results=element('div','bestiaryResultsLine');
      resultCount=element('span');resultCount.setAttribute('aria-live','polite');resultCount.setAttribute('aria-atomic','true');
      append(results,resultCount,element('span','bestiaryScaleNote','Характеристики базовые · растут с уровнем врага'));
      grid=element('div','bestiaryGrid');
      empty=element('div','bestiaryEmpty','Ничего не найдено. Попробуй другую землю или сбрось поиск.');empty.hidden=true;
      append(panel,header,summary,help,toolbar,results,grid,empty);append(overlay,panel);doc.body.appendChild(overlay);
      overlay.addEventListener('click',event=>{if(event.target===overlay)close();});
      doc.addEventListener('keydown',event=>{
        if(!opened)return;
        if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close();}
        if(event.key==='Tab'){
          const current=focusables.indexOf(doc.activeElement),last=focusables.length-1;
          if(event.shiftKey&&(current<=0)){event.preventDefault();focusables[last].focus();}
          else if(!event.shiftKey&&(current===last||current<0)){event.preventDefault();focusables[0].focus();}
        }
      });
    }
    function card(entry,kills){
      const view=visibleEntry(entry,kills),article=element('article',`bestiaryCard bestiaryRank-${view.rank}`);
      const top=element('div','bestiaryCardTop'),portrait=element('div','bestiaryPortrait');
      const canvas=element('canvas');canvas.width=112;canvas.height=96;canvas.setAttribute('aria-hidden','true');portrait.appendChild(canvas);
      if(!view.discovered)portrait.appendChild(element('span','bestiaryUnknownMark','?'));
      const identity=element('div','bestiaryIdentity');
      append(identity,element('span','bestiaryType',view.discovered?(entry.boss?'ХРАНИТЕЛЬ':entry.mini_boss?'МИНИ-БОСС':'ОБИТАТЕЛЬ ЗЕМЕЛЬ'):'НЕИЗВЕСТНЫЙ СЛЕД'),element('h3','bestiaryName',view.name),element('span','bestiaryRank',RANKS[view.rank]));
      append(top,portrait,identity);article.appendChild(top);
      article.appendChild(element('p','bestiaryRegions',view.regions.map(r=>r.name+(Number.isFinite(r.level)?` · ур. ${r.level}`:typeof r.level==='string'&&r.level?` · ${r.level}`:'')).join(' / ')||'Земля не указана'));
      if(!view.discovered){
        article.appendChild(element('p','bestiaryLocked','Победи это существо, чтобы открыть портрет, повадки и трофеи.'));
        article.appendChild(element('div','bestiaryKillCount','0 / 1 · ДО ОТКРЫТИЯ'));
      }else{
        const next=view.kills<5?5:view.kills<15?15:null;
        article.appendChild(element('div','bestiaryKillCount',`ПОБЕД: ${view.kills.toLocaleString('ru-RU')}${next?` · ${view.kills} / ${next} ДО СЛЕДУЮЩЕГО РАНГА`:' · КОЛЛЕКЦИЯ ИЗУЧЕНА'}`));
        const stats=element('dl','bestiaryStats');
        for(const [label,key,suffix] of [['Здоровье','base_hp',''],['Урон','base_damage',''],['Дальность','range',''],['Интервал','cooldown',' с'],['Опыт','xp','']]){
          if(Number.isFinite(entry[key]))append(stats,append(element('div'),element('dt','',label),element('dd','',entry[key].toLocaleString('ru-RU')+suffix)));
        }
        article.appendChild(stats);
        if(entry.lore)article.appendChild(element('p','bestiaryLore',entry.lore));
        if(Array.isArray(entry.tactics)&&entry.tactics.length){const list=element('ul','bestiaryTactics');for(const tip of entry.tactics)list.appendChild(element('li','',tip));append(article,element('h4','bestiarySectionTitle','В ПОЛЕ'),list);}
        if(Array.isArray(entry.loot)&&entry.loot.length)append(article,element('h4','bestiarySectionTitle','ВОЗМОЖНЫЕ ТРОФЕИ'),element('p','bestiaryLoot',entry.loot.join(' · ')));
      }
      if(typeof options.drawPortrait==='function')options.drawPortrait(canvas,entry,view.discovered);
      return article;
    }
    function render(){
      if(!opened)return;
      const catalog=Array.isArray(latest?.bestiary_catalog)?latest.bestiary_catalog:EMPTY_CATALOG,kills=latest?.bestiary_kills||{};
      if(catalog!==catalogRef){catalogRef=catalog;catalogRevision++;}
      // Full catalogs are static between full snapshots. Compact snapshots can arrive
      // twenty times a second: only compare the bounded, known-species kill counts.
      const counts=catalog.map(entry=>countKills(kills[entry.id]));
      const nextSignature=JSON.stringify([catalogRevision,counts,filters]);
      if(nextSignature===signature)return;
      const regions=new Map();for(const entry of catalog)for(const r of regionsOf(entry))if(r.id)regions.set(r.id,r.name);
      const nextRegions=JSON.stringify([...regions]);
      if(nextRegions!==regionSignature){
        regionSignature=nextRegions;region.replaceChildren();option(region,'all','Все земли');
        for(const [id,name] of regions)option(region,id,name);
        if(filters.region!=='all'&&!regions.has(filters.region))filters.region='all';
        region.value=filters.region;
      }
      const summary=summarize(catalog,kills);
      progress.textContent=`${summary.discovered} / ${summary.total} видов открыто`;
      totals.textContent=`Изучено ${summary.studied} · Мастерство ${summary.mastered}`;
      progressFill.style.setProperty('width',`${summary.total?summary.discovered/summary.total*100:0}%`);
      const bar=progressFill.parentNode;bar.setAttribute('aria-valuemax',String(summary.total));bar.setAttribute('aria-valuenow',String(summary.discovered));
      const entries=selectEntries(catalog,kills,filters);
      resultCount.textContent=`Записей: ${entries.length} / ${catalog.length}`;
      empty.hidden=entries.length>0;
      if(!catalog.length)empty.textContent='Дневник ещё загружается. Записи появятся с данными героя.';
      else empty.textContent='Ничего не найдено. Попробуй другую землю или сбрось поиск.';
      grid.replaceChildren(...entries.map(entry=>card(entry,kills[entry.id])));
      signature=JSON.stringify([catalogRevision,counts,filters]);
    }
    function open(player){
      if(player!==undefined)latest=player;
      ensure();if(!opened)returnFocus=doc.activeElement;
      opened=true;overlay.hidden=false;render();focusables[0].focus();
    }
    function close(){
      if(!opened)return;
      opened=false;overlay.hidden=true;
      if(returnFocus&&returnFocus.isConnected!==false&&typeof returnFocus.focus==='function')returnFocus.focus();
      returnFocus=null;
    }
    function sync(player){latest=player;if(opened)render();}
    return {open,close,sync,isOpen:()=>opened,get root(){return overlay;}};
  }
  return {create,rankForKills,summarize,selectEntries,visibleEntry};
});
