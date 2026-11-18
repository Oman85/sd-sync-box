"""Shared look for the web page and the monitor: mid-90s desktop software on a black desktop.

Bevelled grey windows, navy title bars, block progress bars, sunken white
fields. Every control is at least 44 px tall so it works on a touch monitor.
"""

FONTS = ""  # system fonts only: works offline and on the kiosk

CSS = r"""
:root{
  --desk:#000; --face:#c0c0c0; --hi:#fff; --lt:#dfdfdf; --sh:#808080; --dk:#0a0a0a;
  --navy:#000080; --title2:#1084d0; --ink:#000; --mute:#404040;
  --ui:Tahoma,Verdana,"DejaVu Sans","Segoe UI",sans-serif;
  --mono:"Courier New","DejaVu Sans Mono","Liberation Mono",monospace;
  --raised:inset -1px -1px var(--dk),inset 1px 1px var(--hi),inset -2px -2px var(--sh),inset 2px 2px var(--lt);
  --sunken:inset 1px 1px var(--sh),inset -1px -1px var(--hi),inset 2px 2px var(--dk),inset -2px -2px var(--lt);
  --tap:44px;
}
*{box-sizing:border-box}
html{background:var(--desk)}
body{margin:0;min-height:100vh;background:var(--desk);color:var(--ink);font:15px/1.4 var(--ui);
  -webkit-tap-highlight-color:transparent;touch-action:manipulation}
a{color:var(--navy)}
.mute{color:var(--mute)} .cyan{color:var(--navy)} .pink{color:#800080} .amber{color:#7a5a00}
.red{color:#a00000} .ok{color:#006000}

/* windows */
.panel{background:var(--face);box-shadow:var(--raised);padding:3px;margin:0 0 14px}
.panel>h2{display:flex;justify-content:space-between;align-items:center;gap:2px 10px;flex-wrap:wrap;margin:0;
  min-height:28px;padding:3px 4px 3px 6px;font:bold 14px/1.2 var(--ui);color:#fff;letter-spacing:0;
  background:linear-gradient(90deg,var(--navy),var(--title2))}
.panel>h2::before{content:"";width:16px;height:14px;margin-right:6px;flex:none;
  background:linear-gradient(#fff 0 3px,var(--face) 3px);box-shadow:inset 0 0 0 1px #000}
.panel>h2 .ttl{flex:1}
.panel>h2 .tag{font-weight:normal;font-size:12px;color:#dfe8ff}
.panel>.body,.panel>h2~*{padding:10px 8px 8px}
.panel>h2~*+*{padding-top:0}
.status{display:flex;gap:3px;padding:3px 0 0!important}
.status>span{flex:1;box-shadow:inset 1px 1px var(--sh),inset -1px -1px var(--hi);padding:2px 6px;font-size:12px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

/* controls */
button{font:14px var(--ui);color:var(--ink);background:var(--face);border:0;box-shadow:var(--raised);
  min-height:var(--tap);min-width:76px;padding:6px 14px;cursor:pointer;border-radius:0;white-space:nowrap;flex-shrink:0}
button:active,button.down{box-shadow:var(--sunken);padding:7px 13px 5px 15px}
button:focus-visible{outline:1px dotted #000;outline-offset:-5px}
button.hot{font-weight:bold}
button.sm{min-width:0;padding:6px 12px}
input,select{font:15px var(--ui);color:#000;background:#fff;border:0;border-radius:0;box-shadow:var(--sunken);
  min-height:var(--tap);padding:6px 8px;width:100%}
select{appearance:none;-webkit-appearance:none;padding-right:42px;background:#fff
  url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='34' height='38'%3E%3Crect width='34' height='38' fill='%23c0c0c0'/%3E%3Cpath d='M0 0h33v1H1v36H0z' fill='%23fff'/%3E%3Cpath d='M33 0h1v38H0v-1h33z' fill='%23000'/%3E%3Cpath d='M1 36h32v1H1z' fill='%23808080'/%3E%3Cpath d='M11 16h12l-6 7z' fill='%23000'/%3E%3C/svg%3E")
  right 2px center/34px calc(100% - 4px) no-repeat}
input:focus,select:focus{outline:1px dotted #000;outline-offset:-4px}
input::placeholder{color:#808080}
form{margin:0;display:inline}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end}
.grow{flex:1 1 200px;min-width:0}
label{display:block;font-size:13px;color:#000;margin:0 0 3px}

/* group boxes, lists */
.group{position:relative;border:1px solid var(--sh);box-shadow:1px 1px 0 var(--hi),inset 1px 1px 0 var(--hi);
  padding:14px 10px 10px;margin:12px 0 4px}
.group>.legend{position:absolute;top:-9px;left:8px;background:var(--face);padding:0 4px;font-size:13px}
.item{border-top:1px solid var(--sh);box-shadow:inset 0 1px 0 var(--hi);padding:10px 0}
.item:first-of-type{border-top:0;box-shadow:none;padding-top:0}
.item .t{font-weight:bold;overflow-wrap:anywhere}
.item .u{color:var(--mute);font-size:13px;overflow-wrap:anywhere}
.off .t{color:var(--sh);text-shadow:1px 1px 0 var(--hi)}
.chip{display:inline-flex;align-items:stretch;background:#fff;box-shadow:var(--sunken);
  margin:3px 6px 3px 0;padding:2px 2px 2px 10px;font-size:14px;min-height:var(--tap);vertical-align:middle}
.chip>span{display:flex;align-items:center;padding-right:8px}
.chip form{display:flex}
.chip button{min-width:40px;min-height:0;padding:0 10px;font-weight:bold}

/* progress: navy blocks in a sunken trough */
.bar{position:relative;height:24px;background:#fff;box-shadow:var(--sunken);padding:3px;overflow:hidden}
.bar>i{display:block;height:100%;width:0;transition:width .5s steps(8,end);
  background:repeating-linear-gradient(90deg,var(--navy) 0 10px,transparent 10px 12px)}
.bar.thin{height:14px}
.bar.pinkbar>i{background:repeating-linear-gradient(90deg,#008080 0 10px,transparent 10px 12px)}
.barline{display:flex;justify-content:space-between;gap:10px;font-size:14px;margin:8px 0 4px}
.barline span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.barline span:last-child:not(:first-child){white-space:nowrap;flex:none}
.blink{animation:blink 1s steps(1) infinite} @keyframes blink{50%{opacity:0}}

/* the log is a black console window */
pre.log{margin:0;white-space:pre-wrap;font:13px/1.35 var(--mono);color:#c0c0c0;background:#000;
  box-shadow:var(--sunken);padding:8px;max-height:280px;overflow:auto}

/* drive boxes */
.dev{position:relative;border:1px solid var(--sh);box-shadow:1px 1px 0 var(--hi),inset 1px 1px 0 var(--hi);padding:8px 10px;margin:0 0 10px}
.dev .ico{display:inline-block;width:14px;height:18px;margin-right:6px;vertical-align:-3px;background:#404040;
  clip-path:polygon(0 0,70% 0,100% 22%,100% 100%,0 100%);box-shadow:inset 0 0 0 2px #000}
.dev.done{background:#d4ead4} .dev.error{background:#f0d0d0} .dev.unassigned{background:#fff6c8}
.dev button{white-space:normal;text-align:center;max-width:100%}

/* message box */
.modal{position:fixed;inset:0;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;z-index:100;padding:16px}
.modal .panel{width:min(440px,100%);margin:0}
.msg{display:flex;gap:14px;align-items:flex-start;padding:16px 10px 6px}
.msg .q{flex:none;width:36px;height:36px;border-radius:50%;background:#fff;box-shadow:inset 0 0 0 2px var(--navy);
  color:var(--navy);font:bold 22px/36px var(--ui);text-align:center}
.btns{display:flex;justify-content:center;gap:10px;padding:10px}

/* on-screen keyboard (touch monitor only) */
#osk{position:fixed;left:0;right:0;bottom:0;z-index:90;display:none}
#osk.on{display:block}
#osk .panel{margin:0}
#osk .keys{padding:6px;display:grid;gap:4px}
#osk .r{display:flex;gap:4px}
#osk button{flex:1 1 0;min-width:0;padding:0;height:52px;font-size:18px}
#osk button.w2{flex-grow:2} #osk button.w5{flex-grow:6}
body.kiosk{cursor:none}
#curtain{position:fixed;inset:0;background:#000;z-index:500;display:none}
#curtain.on{display:block}
body.kiosk.osk-open main{padding-bottom:300px}
"""

# Message boxes instead of the browser's own confirm(), and the touch keyboard.
JS = r"""
function msgbox(text,yes){
  const m=document.createElement('div');m.className='modal';
  m.innerHTML=`<div class="panel"><h2><span class="ttl">SD//SYNC</span></h2><div><div class="msg"><div class="q">?</div><div></div></div>
   <div class="btns"><button class="hot">Yes</button><button>No</button></div></div></div>`;
  m.querySelector('.msg div:last-child').textContent=text;
  const [y,n]=m.querySelectorAll('.btns button');
  y.onclick=()=>{m.remove();yes()}; n.onclick=()=>m.remove();
  document.body.appendChild(m); y.focus();
}
document.addEventListener('submit',e=>{
  const f=e.target; if(!f.dataset.confirm||f._ok) return;
  e.preventDefault(); msgbox(f.dataset.confirm,()=>{f._ok=true;f.submit()});
},true);

function initKiosk(){
  document.body.classList.add('kiosk');
  // Monitor sleep: the box turns the monitor off when idle. While it is off a black
  // curtain covers the page, so the first touch only wakes it and presses nothing.
  const cur=document.createElement('div');cur.id='curtain';document.body.appendChild(cur);
  let lastWake=0;
  const wake=()=>{lastWake=Date.now();fetch('/api/wake',{method:'POST'}).catch(()=>{})};
  cur.addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();cur.classList.remove('on');wake()},true);
  addEventListener('pointerdown',()=>{if(Date.now()-lastWake>20000)wake()},true);
  setInterval(async()=>{try{const s=await (await fetch('/api/status')).json();
    cur.classList.toggle('on',s.display==='off'&&Date.now()-lastWake>5000)}catch(_){}} ,2000);
  // back to the monitor view after 3 minutes without a touch
  let idle; const reset=()=>{clearTimeout(idle);idle=setTimeout(()=>{if(location.pathname!=='/screen')location='/screen'},180000)};
  ['pointerdown','keydown'].forEach(ev=>addEventListener(ev,reset,true)); reset();
  const rows=[['1','2','3','4','5','6','7','8','9','0','Bksp'],['q','w','e','r','t','y','u','i','o','p','/'],
    ['a','s','d','f','g','h','j','k','l',':','.'],['Shift','z','x','c','v','b','n','m','?','=','&'],
    ['Clear','-','_','Space','YT link','Done']];
  const k=document.createElement('div');k.id='osk';
  k.innerHTML='<div class="panel"><h2><span class="ttl">Keyboard</span></h2><div class="keys"></div></div>';
  const keys=k.querySelector('.keys'); let shift=false, target=null;
  rows.forEach(r=>{const d=document.createElement('div');d.className='r';
    r.forEach(c=>{const b=document.createElement('button');b.type='button';b.textContent=c==='Space'?'':c;b.dataset.k=c;
      if(['Bksp','Shift','Clear','Done'].includes(c))b.className='w2';
      if(c==='Space'||c==='YT link')b.className='w5';d.appendChild(b)});keys.appendChild(d)});
  const paint=()=>keys.querySelectorAll('button').forEach(b=>{const c=b.dataset.k;
    if(c.length===1)b.textContent=shift?c.toUpperCase():c; b.classList.toggle('down',c==='Shift'&&shift)});
  k.addEventListener('pointerdown',e=>e.preventDefault());   // keep focus in the field
  k.addEventListener('click',e=>{const b=e.target.closest('button'); if(!b||!target)return; const c=b.dataset.k;
    const ins=t=>{const s=target.selectionStart??target.value.length,en=target.selectionEnd??s;
      target.value=target.value.slice(0,s)+t+target.value.slice(en); try{target.setSelectionRange(s+t.length,s+t.length)}catch(_){} };
    if(c==='Done'){target.blur();return}
    if(c==='Shift'){shift=!shift;paint();return}
    if(c==='Bksp'){const s=target.selectionStart??target.value.length,en=target.selectionEnd??s;
      const a=s===en?Math.max(0,s-1):s;target.value=target.value.slice(0,a)+target.value.slice(en);try{target.setSelectionRange(a,a)}catch(_){} return}
    if(c==='Clear'){target.value='';return}
    ins(c==='Space'?' ':c==='YT link'?'https://www.youtube.com/playlist?list=':(shift?c.toUpperCase():c));
    if(shift){shift=false;paint()}
  });
  document.body.appendChild(k);
  document.addEventListener('focusin',e=>{if(e.target.matches('input:not([type=hidden])')){target=e.target;
    if(target.type==='number'){target.type='text';target.inputMode='numeric'}
    k.classList.add('on');document.body.classList.add('osk-open');setTimeout(()=>target.scrollIntoView({block:'center'}),50)}});
  document.addEventListener('focusout',e=>{setTimeout(()=>{if(!document.activeElement||!document.activeElement.matches('input')){
    k.classList.remove('on');document.body.classList.remove('osk-open')}},0)});
}
"""


# ---------------------------------------------------------------------------
# "Cyberspace" look: neon-on-black interfaces like the computer screens in
# 90s hacker films. It is layered over the classic look, so the same markup,
# touch sizes, keyboard and message boxes work in both.
CYBER_FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
               '<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;800&family=Share+Tech+Mono&display=swap" rel="stylesheet">')

CYBER_CSS = r"""
:root{
  --desk:#000; --face:rgba(6,0,22,.78); --ink:#dffcff; --mute:#7fb8c8;
  --c1:#00f0ff; --c2:#ff00d4; --c3:#f6ff00; --c4:#39ff14; --c5:#7a00ff;
  --hi:rgba(0,240,255,.35); --lt:rgba(0,240,255,.15); --sh:rgba(0,240,255,.35); --dk:#000;
  --navy:var(--c2); --title2:var(--c1);
  --ui:"Share Tech Mono","DejaVu Sans Mono",monospace; --mono:"Share Tech Mono","DejaVu Sans Mono",monospace;
  --head:"Orbitron","DejaVu Sans",sans-serif;
  --raised:0 0 0 1px var(--c1),0 0 12px rgba(0,240,255,.35),inset 0 0 12px rgba(0,240,255,.12);
  --sunken:0 0 0 1px rgba(0,240,255,.55),inset 0 0 14px rgba(0,240,255,.18);
}
body{color:var(--ink);letter-spacing:.02em;
  background:
    linear-gradient(transparent 62%,rgba(255,0,212,.10)),
    repeating-linear-gradient(0deg,rgba(0,240,255,.06) 0 1px,transparent 1px 40px),
    repeating-linear-gradient(90deg,rgba(0,240,255,.06) 0 1px,transparent 1px 40px),#000}
body::after{content:"";pointer-events:none;position:fixed;inset:0;z-index:80;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,.25) 0 1px,transparent 1px 3px)}
a{color:var(--c1)}
.mute{color:var(--mute)} .cyan{color:var(--c1)} .pink{color:var(--c2)} .amber{color:var(--c3)}
.red{color:#ff3355} .ok{color:var(--c4)}
b{color:#fff}

.panel{background:var(--face);box-shadow:0 0 0 1px var(--c1),0 0 22px rgba(0,240,255,.25),inset 0 0 30px rgba(122,0,255,.18);
  padding:0}
.panel>h2{font:800 13px/1 var(--head);letter-spacing:.28em;text-transform:uppercase;color:#000;min-height:30px;
  padding:6px 10px;background:linear-gradient(100deg,var(--c2),var(--c5) 45%,var(--c1));
  text-shadow:none;box-shadow:0 0 18px rgba(255,0,212,.55)}
.panel>h2::before{width:10px;height:10px;background:#000;box-shadow:none;transform:rotate(45deg);margin-right:10px}
.panel>h2 .tag{color:#000;font:500 11px var(--ui);letter-spacing:.12em;text-transform:none;opacity:.8}
.status>span{box-shadow:0 0 0 1px rgba(0,240,255,.35);color:var(--c1)}

button{background:rgba(0,0,0,.55);color:var(--c1);font:500 12px var(--head);letter-spacing:.1em;text-transform:uppercase;
  text-shadow:0 0 8px rgba(0,240,255,.8)}
button:active,button.down{background:var(--c1);color:#000;text-shadow:none;box-shadow:0 0 22px var(--c1);padding:6px 14px}
button.hot{color:var(--c2);box-shadow:0 0 0 1px var(--c2),0 0 14px rgba(255,0,212,.45);text-shadow:0 0 8px rgba(255,0,212,.8)}
button.hot:active{background:var(--c2);color:#000}
button:focus-visible{outline:1px solid var(--c3);outline-offset:2px}
input,select{background:rgba(0,0,0,.7);color:var(--c3);font:16px var(--mono);caret-color:var(--c2);text-shadow:0 0 6px rgba(246,255,0,.5)}
input:focus,select:focus{outline:none;box-shadow:0 0 0 1px var(--c2),0 0 16px rgba(255,0,212,.55)}
input::placeholder{color:#3d6b78;text-shadow:none}
select{background:rgba(0,0,0,.7)
  url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='34' height='38'%3E%3Cpath d='M10 15h14l-7 9z' fill='%2300f0ff'/%3E%3C/svg%3E")
  right 2px center/34px 38px no-repeat}
select option{background:#05001a;color:var(--c3)}
label{color:var(--c1);font:500 11px var(--head);letter-spacing:.2em;text-transform:uppercase}

.group{border:1px solid rgba(0,240,255,.4);box-shadow:none}
.group>.legend{background:#05001a;color:var(--c2);font:800 11px var(--head);letter-spacing:.25em;text-transform:uppercase}
.item{border-top:1px solid rgba(0,240,255,.25);box-shadow:none}
.item .t{color:var(--c3);text-shadow:0 0 8px rgba(246,255,0,.45)}
.off .t{color:#4a5a60;text-shadow:none}
.chip{background:rgba(0,0,0,.6);box-shadow:0 0 0 1px var(--c2),0 0 10px rgba(255,0,212,.35);color:#fff}

.bar{background:rgba(0,0,0,.75);box-shadow:0 0 0 1px var(--c1),inset 0 0 10px rgba(0,240,255,.2)}
.bar>i{position:relative;transition:width .6s ease;
  background:linear-gradient(90deg,var(--c2),var(--c3) 50%,var(--c1));
  -webkit-mask:repeating-linear-gradient(90deg,#000 0 8px,transparent 8px 11px);mask:repeating-linear-gradient(90deg,#000 0 8px,transparent 8px 11px);
  filter:drop-shadow(0 0 6px rgba(255,0,212,.9))}
.bar.pinkbar>i{background:linear-gradient(90deg,var(--c4),var(--c1))}
.bar::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent) -40% 0/30% 100% no-repeat;animation:sweep 2.4s linear infinite}
@keyframes sweep{to{background-position:140% 0}}

pre.log{background:rgba(0,0,0,.6);color:var(--c4);text-shadow:0 0 6px rgba(57,255,20,.55);box-shadow:var(--sunken)}
.dev{border:1px solid rgba(0,240,255,.4);box-shadow:none;background:rgba(0,0,0,.35)}
.dev .ico{background:var(--c1);box-shadow:0 0 8px var(--c1)}
.dev.done{background:rgba(57,255,20,.08);border-color:var(--c4)} .dev.error{background:rgba(255,40,80,.12);border-color:#ff3355}
.dev.unassigned{background:rgba(246,255,0,.07);border-color:var(--c3);animation:alert 1.4s ease-in-out infinite alternate}
@keyframes alert{to{box-shadow:0 0 22px rgba(246,255,0,.45)}}
.modal{background:rgba(0,0,0,.65)}
.msg .q{background:#000;box-shadow:0 0 0 2px var(--c2),0 0 16px var(--c2);color:var(--c2);font-family:var(--head)}
#osk .keys{background:rgba(0,0,0,.6)}
#osk button{font-family:var(--mono);font-size:20px;letter-spacing:0;text-transform:none}

/* monitor view */
.task{background:rgba(0,0,0,.8)!important;box-shadow:0 -1px 0 var(--c2),0 -8px 24px rgba(255,0,212,.25)!important}
.tray{box-shadow:0 0 0 1px rgba(0,240,255,.4)!important;color:var(--c1)}
.tray b{font:800 1.2em var(--head);color:var(--c3);text-shadow:0 0 10px var(--c3)}
.desk{position:relative;z-index:1}
.desk .panel{background:rgba(6,0,22,.55)}
.task{flex-wrap:wrap}
.task button{font-size:.72em;letter-spacing:.08em;padding:6px 12px}
.tray{min-width:0;overflow:hidden}
.menu a{color:var(--c1);font:500 12px var(--head);letter-spacing:.18em;text-transform:uppercase}
.menu a:active,.menu a:hover{background:var(--c2);color:#000}
.menu a u{text-decoration:none;color:var(--c3)}
.logo{font:800 22px var(--head);letter-spacing:.3em;color:#fff;
  text-shadow:-2px 0 var(--c2),2px 0 var(--c1),0 0 18px rgba(255,0,212,.6)}
#bg{position:fixed;inset:0;z-index:0;width:100%;height:100%}
@media (prefers-reduced-motion:reduce){.bar::after,.dev.unassigned{animation:none}}
"""

# A fly-through of an endless city of glowing data towers, drawn on a canvas.
CITY_JS = r"""
(function(){
 const c=document.getElementById('bg'); if(!c) return; const x=c.getContext('2d');
 const cols=['#00f0ff','#ff00d4','#f6ff00','#39ff14','#7a00ff'], G='0123456789ABCDEF';
 let W,H,towers=[],t=0; const FAR=60, SPEED=0.06;
 function size(){W=c.width=innerWidth;H=c.height=innerHeight}
 function tower(z){const side=Math.random()<.5?-1:1;return{x:side*(1.2+Math.random()*7),z:z,w:.5+Math.random()*1.2,
   h:1+Math.random()*7,col:cols[Math.random()*cols.length|0],seed:Math.random()*1e4|0}}
 size(); addEventListener('resize',size);
 for(let i=0;i<70;i++) towers.push(tower(Math.random()*FAR+1));
 function frame(){
  const cu=document.getElementById('curtain'); if(cu&&cu.classList.contains('on')){setTimeout(()=>requestAnimationFrame(frame),1000);return}
  t+=1; x.fillStyle='rgba(0,0,0,.35)'; x.fillRect(0,0,W,H);
  const f=H*0.9, hy=H*0.42, cx=W/2;
  // floor grid
  x.strokeStyle='rgba(255,0,212,.25)'; x.lineWidth=1; x.beginPath();
  for(let i=-12;i<=12;i++){const X=i*1.5;x.moveTo(cx+X*f/1.2,hy+1.6*f/1.2);x.lineTo(cx+X*f/FAR,hy+1.6*f/FAR)}
  for(let z=(1-(t*SPEED)%2);z<FAR;z+=2){const y=hy+1.6*f/z;x.moveTo(0,y);x.lineTo(W,y)}
  x.stroke();
  towers.sort((a,b)=>b.z-a.z);
  for(const tw of towers){
   tw.z-=SPEED; if(tw.z<0.6){Object.assign(tw,tower(FAR));continue}
   const s=f/tw.z, X0=cx+(tw.x-tw.w/2)*s, X1=cx+(tw.x+tw.w/2)*s, Yb=hy+1.6*s, Yt=hy+(1.6-tw.h)*s;
   const a=Math.max(0,Math.min(1,(FAR-tw.z)/20));
   x.globalAlpha=a*.9; x.strokeStyle=tw.col; x.shadowColor=tw.col; x.shadowBlur=8;
   x.strokeRect(X0,Yt,X1-X0,Yb-Yt); x.shadowBlur=0;
   const fs=Math.max(4,Math.min(22,s*0.22)); if(fs>5){x.font=fs+'px monospace';x.fillStyle=tw.col;
    const n=Math.floor((X1-X0)/fs), m=Math.floor((Yb-Yt)/fs);
    for(let i=0;i<n;i++)for(let j=0;j<m;j++){const k=(tw.seed+i*31+j*17+((t/8)|0)*(i%3===0?1:0))%97;
     if(k%3)continue; x.globalAlpha=a*(k%7===0?.95:.45); x.fillText(G[k%16],X0+i*fs+1,Yt+(j+1)*fs)}}
  }
  x.globalAlpha=1; requestAnimationFrame(frame);
 }
 if(!matchMedia('(prefers-reduced-motion: reduce)').matches) frame();
})();
"""


# 3D falling code, in the spirit of the "GLMatrix" hack from xscreensaver
# (by Jamie Zawinski). Written from scratch for a 2D canvas: strips of glyphs
# hang at different depths, a bright head drops down each one, the tail fades
# behind it, glyphs flicker, and the view slowly drifts forward and sways.
GLMATRIX_JS = r"""
(function(){
 const c=document.getElementById('bg'); if(!c) return; const x=c.getContext('2d');
 const G='ｦｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789Z:.=*+-<>¦|';
 const pick=()=>G[Math.random()*G.length|0];
 const NEAR=1.2, FAR=42, N=110, LEN=30;
 let W,H,strips=[],t=0,last=0;
 function size(){W=c.width=innerWidth;H=c.height=innerHeight}
 function strip(z){
  const s={x:(Math.random()-.5)*34,y:6+Math.random()*10,z:z,len:LEN,head:-Math.random()*LEN|0,
    speed:.12+Math.random()*.25,acc:0,erase:Math.random()<.35,glyphs:[]};
  for(let i=0;i<LEN;i++)s.glyphs.push(pick()); return s;
 }
 size(); addEventListener('resize',size);
 for(let i=0;i<N;i++) strips.push(strip(NEAR+Math.random()*(FAR-NEAR)));
 function frame(now){
  const cu=document.getElementById('curtain');
  if(cu&&cu.classList.contains('on')){setTimeout(()=>requestAnimationFrame(frame),1000);return}
  requestAnimationFrame(frame);
  if(now-last<33) return;
  // slow machine? draw fewer strips (keeps the monitor smooth on old PCs)
  if(last&&now-last>70&&strips.length>40) strips.length-=4;
  last=now; t++;                                // ~30 fps is plenty
  x.fillStyle='#000'; x.fillRect(0,0,W,H);
  const f=Math.min(W,H)*0.9, cx=W/2, cy=H/2;
  const sway=Math.sin(t*0.004)*0.35, bob=Math.sin(t*0.003)*1.2;
  const cs=Math.cos(sway), sn=Math.sin(sway);
  strips.sort((a,b)=>b.z-a.z);
  x.textAlign='center'; x.textBaseline='middle'; let curFs=0;
  for(const s of strips){
   s.z-=0.035;                                      // drift toward the viewer
   s.acc+=s.speed; while(s.acc>=1){s.acc-=1;s.head++}
   if(s.head>s.len+LEN){s.head=0;if(s.erase){s.glyphs=s.glyphs.map(pick)}}
   if(Math.random()<.08) s.glyphs[Math.random()*s.len|0]=pick();
   // rotate the strip around the vertical axis for the slow sway
   const X=s.x*cs-s.z*sn*0.15, Z=s.z+s.x*sn*0.15;
   if(Z<NEAR){Object.assign(s,strip(FAR));continue}
   const k=f/Z, sx=cx+X*k; if(sx<-50||sx>W+50) continue;
   const fs=Math.round(k*0.95); if(fs<5) continue;
   const fog=Math.max(0,Math.min(1,(FAR-Z)/(FAR*0.75)));
   if(fs!==curFs){curFs=fs;x.font=fs+'px "IPAGothic","Noto Sans Mono CJK JP","VL Gothic","DejaVu Sans Mono",monospace'}
   for(let i=0;i<s.len;i++){
    const age=s.head-i; if(age<0||age>LEN) continue;   // above the head: not drawn yet
    const sy=cy+(s.y-bob-i*1.0)*-k;
    if(sy<-fs||sy>H+fs) continue;
    const a=fog*(age===0?1:Math.max(0,1-age/LEN)*0.85);
    if(a<0.03) continue;
    x.fillStyle=age===0?`rgba(220,255,230,${a})`:`rgba(0,${150+((i*37)%90)},${40+((i*13)%40)},${a})`;
    x.fillText(s.glyphs[i],sx,sy);
   }
  }
 }
 if(!matchMedia('(prefers-reduced-motion: reduce)').matches) requestAnimationFrame(frame);
})();
"""

BACKGROUNDS = {
    "glmatrix": ("3D falling code (xscreensaver GLMatrix style)", "GLMATRIX_JS"),
    "city": ("Data city fly-through", "CITY_JS"),
    "none": ("None", None),
}


def background_js(name):
    entry = BACKGROUNDS.get(name) or BACKGROUNDS["glmatrix"]
    return globals()[entry[1]] if entry[1] else ""
