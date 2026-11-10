/* A bounded, reusable light mask. Visual only; never changes simulation time. */
(function(root){
  'use strict';
  const nightAmount=ms=>(1-Math.cos((ms%480000)/480000*Math.PI*2))*.5;
  const project=(point,camera,zoom,w,h,lookY)=>({x:w/2+(point.x-camera.x)*zoom,y:h/2+lookY+(point.y-camera.y)*zoom});
  let mask,light;
  function draw(c,w,h,region,hero,sites,camera,zoom,lookY,now){
    if(!hero||typeof document==='undefined')return;
    if(!mask){mask=document.createElement('canvas');light=mask.getContext('2d');}
    if(mask.width!==Math.ceil(w)||mask.height!==Math.ceil(h)){mask.width=Math.ceil(w);mask.height=Math.ceil(h);}
    const night=nightAmount(now), depth=['rift','abyss','obsidian'].includes(region.id)?.12:0;
    light.clearRect(0,0,w,h);light.globalCompositeOperation='source-over';
    light.fillStyle=`rgba(8,16,35,${.025+night*.17+depth})`;light.fillRect(0,0,w,h);
    const lamps=[{x:hero.x,y:hero.y,r:140,color:'#a9dfff',strength:.035},
      {x:470,y:790,r:190,color:'#ffc777',strength:.10},
      ...sites.map(s=>({...s,r:150,color:region.accent||'#b0eaff',strength:.055}))];
    for(const lamp of lamps){
      const p=project(lamp,camera,zoom,w,h,lookY),r=lamp.r*zoom;
      if(p.x+r<0||p.x-r>w||p.y+r<0||p.y-r>h)continue;
      const hole=light.createRadialGradient(p.x,p.y,0,p.x,p.y,r);
      hole.addColorStop(0,'#000');hole.addColorStop(.25,'#000c');hole.addColorStop(1,'#0000');
      light.globalCompositeOperation='destination-out';light.fillStyle=hole;light.fillRect(p.x-r,p.y-r,r*2,r*2);
    }
    c.save();c.drawImage(mask,0,0,w,h);c.globalCompositeOperation='screen';
    for(const lamp of lamps.slice(1)){
      const p=project(lamp,camera,zoom,w,h,lookY),r=lamp.r*zoom;
      if(p.x+r<0||p.x-r>w||p.y+r<0||p.y-r>h)continue;
      const g=c.createRadialGradient(p.x,p.y,0,p.x,p.y,r);
      g.addColorStop(0,lamp.color);g.addColorStop(1,lamp.color+'00');
      c.globalAlpha=lamp.strength*(.6+night*.4);c.fillStyle=g;c.fillRect(p.x-r,p.y-r,r*2,r*2);
    }
    c.restore();
  }
  const api={nightAmount,project,draw};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.EchoAtmosphere=api;
})(typeof window!=='undefined'?window:globalThis);
