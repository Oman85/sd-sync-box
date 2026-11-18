"""Player controls shared by the control page, the monitor and the phone remote."""

PLAYER_CSS = r"""
.np{display:grid;gap:8px}
.np .t{font-size:1.25em;font-weight:bold;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.np .a{color:var(--mute);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.np .times{display:flex;justify-content:space-between;font-size:.85em;color:var(--mute)}
.np .seek{cursor:pointer;height:28px}
.ctl{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.ctl button{min-width:64px;font-size:1.15em;letter-spacing:0}
.ctl button.big{min-width:96px}
.ctl .vol{display:flex;align-items:center;gap:6px;margin-left:auto}
.ctl .vol .bar{width:110px;height:18px}
.ctl button.on{box-shadow:var(--sunken)}
.upnext{font-size:.9em;color:var(--mute);margin:0;padding-left:1.4em}
.upnext li{padding:6px 0;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lib .pl{border-top:1px solid var(--sh);padding:8px 0}
.lib .pl:first-child{border-top:0}
.lib .row{align-items:center}
.lib .name{flex:1 1 160px;min-width:0;font-weight:bold;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lib ol{margin:6px 0 0;padding-left:2.2em;max-height:320px;overflow:auto}
.lib ol li{padding:9px 4px;cursor:pointer;border-bottom:1px dotted var(--sh);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lib ol li:active{background:var(--navy);color:#fff}
.desk .upnext li:nth-child(n+4){display:none}
.desk .ctl button{min-height:50px}
#toast{position:fixed;left:50%;bottom:90px;transform:translateX(-50%);z-index:300;display:none;padding:10px 16px;
  background:var(--face);box-shadow:var(--raised);color:var(--ink)}
#toast.on{display:block}
"""

PLAYER_HTML = """<div class="np" id="np">
 <div><div class="t" id="np-title">Nothing playing</div><div class="a" id="np-artist">Pick a playlist below</div></div>
 <div class="bar seek" id="np-seek"><i id="np-bar"></i></div>
 <div class="times"><span id="np-pos">0:00</span><span id="np-list"></span><span id="np-dur">0:00</span></div>
 <div class="ctl">
  <button data-cmd="prev" aria-label="Previous">|&#9664;&#9664;</button>
  <button data-cmd="toggle" class="big hot" id="np-toggle" aria-label="Play or pause">&#9654;</button>
  <button data-cmd="next" aria-label="Next">&#9654;&#9654;|</button>
  <button data-cmd="shuffle" id="np-shuf" title="Shuffle" aria-label="Shuffle">&#8644;</button>
  <button data-cmd="stop" aria-label="Stop">&#9632;</button>
  <span class="vol"><button data-cmd="voldown" aria-label="Volume down">&minus;</button>
   <span class="bar thin"><i id="np-vol"></i></span><button data-cmd="volup" aria-label="Volume up">+</button></span>
 </div>
 <ol class="upnext" id="np-next"></ol>
</div>"""

LIBRARY_HTML = """<div class="lib" id="lib-list"><div class="mute">Loading...</div></div>
<div class="row" style="margin-top:8px"><button data-cmd="play_all">Shuffle everything</button></div>"""

PLAYER_JS = r"""
let PL={volume:70,shuffle:false};
const fmt=s=>{s=Math.max(0,Math.floor(s||0));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')};
function toast(m){let t=document.getElementById('toast');if(!t){t=document.createElement('div');t.id='toast';document.body.appendChild(t)}
 t.textContent=m;t.classList.add('on');clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('on'),3500)}
async function pcmd(cmd,extra){
  if(cmd==='volup'){cmd='volume';extra={value:Math.min(100,PL.volume+5)}}
  if(cmd==='voldown'){cmd='volume';extra={value:Math.max(0,PL.volume-5)}}
  try{const r=await fetch('/api/player',{method:'POST',body:new URLSearchParams({cmd,...(extra||{})})});
   const j=await r.json(); if(j.error)toast(j.error); if(j.player)paintPlayer(j.player);}catch(e){toast('Box not reachable')}
}
function paintPlayer(p){
  if(!document.getElementById('np'))return; PL=p;
  const $=id=>document.getElementById(id);
  if(!p.available){$('np-title').textContent='Player not installed';$('np-artist').textContent='Run: sudo apt install mpv';return}
  $('np-title').textContent=p.playing?p.title:'Nothing playing';
  $('np-artist').textContent=p.playing?(p.artist||''):'Pick a playlist below';
  $('np-list').textContent=p.playing?`${p.playlist} · ${p.index+1} of ${p.count}`:'';
  $('np-pos').textContent=fmt(p.pos); $('np-dur').textContent=fmt(p.duration);
  $('np-bar').style.width=(p.duration?Math.min(100,100*p.pos/p.duration):0)+'%';
  $('np-toggle').innerHTML=p.playing&&!p.paused?'&#10074;&#10074;':'&#9654;';
  $('np-vol').style.width=p.volume+'%';
  $('np-shuf').classList.toggle('on',!!p.shuffle);
  const nx=$('np-next'), h=(p.up_next||[]).map(n=>`<li data-cmd="jump" data-value="${n.index}">${E(n.title)}${n.artist?' <span class=mute>- '+E(n.artist)+'</span>':''}</li>`).join('');
  if(nx._h!==h){nx.innerHTML=h;nx._h=h}
}
async function loadLibrary(){
  const el=document.getElementById('lib-list'); if(!el)return;
  try{const d=await (await fetch('/api/library')).json();
   if(!d.playlists.length){el.innerHTML='<div class="mute">No songs downloaded yet.</div>';return}
   el.innerHTML=d.playlists.map(p=>`<div class="pl"><div class="row"><span class="name">${E(p.name)} <span class="mute">(${p.count})</span></span>
     <button data-cmd="play_playlist" data-id="${E(p.id)}" class="hot">Play</button>
     <button data-cmd="play_playlist" data-id="${E(p.id)}" data-shuffle="1">Shuffle</button>
     <button data-songs="${E(p.id)}">Songs</button></div><ol id="songs-${E(p.id)}" hidden></ol></div>`).join('');
  }catch(e){el.innerHTML='<div class="mute">Could not load the library.</div>'}
}
async function showSongs(id){
  const ol=document.getElementById('songs-'+id); if(!ol)return;
  if(!ol.hidden){ol.hidden=true;return}
  const d=await (await fetch('/api/library?id='+encodeURIComponent(id))).json();
  ol.innerHTML=d.tracks.map((t,i)=>`<li data-cmd="play_playlist" data-id="${E(id)}" data-start="${i}">${E(t.title)}${t.artist?' <span class=mute>- '+E(t.artist)+'</span>':''}</li>`).join('');
  ol.hidden=false;
}
document.addEventListener('click',e=>{
  const s=e.target.closest('[data-songs]'); if(s){e.preventDefault();showSongs(s.dataset.songs);return}
  const sk=e.target.closest('#np-seek'); if(sk&&PL.duration){const r=sk.getBoundingClientRect();
    pcmd('seek',{value:Math.round(PL.duration*(e.clientX-r.left)/r.width)});return}
  const b=e.target.closest('[data-cmd]'); if(!b)return; e.preventDefault();
  const x={}; ['id','value','start','shuffle'].forEach(k=>{if(b.dataset[k]!==undefined)x[k]=b.dataset[k]});
  pcmd(b.dataset.cmd,x);
});
"""

REMOTE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black"><meta name="theme-color" content="#000000">
<link rel="manifest" href="/manifest.json"><link rel="icon" href="/icon.svg"><link rel="apple-touch-icon" href="/icon.svg">
<title>SD//SYNC remote</title><style>@@css@@ @@player_css@@
main{max-width:560px;margin:0 auto;padding:12px 12px calc(30px + env(safe-area-inset-bottom))}
.np .t{font-size:1.4em}
.ctl button{flex:1 1 0;min-height:60px;min-width:0;padding-left:4px;padding-right:4px}

.ctl .vol{flex-basis:100%;margin:0}
.ctl .vol .bar{flex:1}
.mini{font-size:.85em}
</style>@@look@@</head><body><main>
<section class="panel"><h2><span class="ttl">Now playing</span><span class="tag" id="clock"></span></h2><div>@@player@@</div></section>
<section class="panel"><h2><span class="ttl">Playlists</span></h2><div>@@library@@</div></section>
<section class="panel"><h2><span class="ttl">Box</span></h2><div class="mini">
 <div id="dl"></div><div style="height:8px"></div><div id="devs"></div>
 <div class="row" style="margin-top:8px"><form method="get" action="/"><button>Playlists &amp; drives...</button></form></div>
</div></section>
</main><script>
const TARGETS=@@targets_json@@;
@@theme_js@@
@@status_js@@
@@player_js@@
async function tick(){try{const s=await (await fetch('/api/status')).json();
document.getElementById('clock').textContent=s.time.slice(0,5);
document.getElementById('dl').innerHTML=renderDownload(s.download);
const devs=document.getElementById('devs');const html=renderDevices(s.devices,TARGETS,true);
if(devs._h!==html){devs.innerHTML=html;devs._h=html;}
if(s.player)paintPlayer(s.player);}catch(e){document.getElementById('clock').textContent='Offline'}}
tick();setInterval(tick,1000);loadLibrary();
</script></body></html>"""

MANIFEST = {
    "name": "SD//SYNC remote", "short_name": "SD//SYNC", "start_url": "/remote", "display": "standalone",
    "background_color": "#000000", "theme_color": "#000000",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
}

ICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#000"/>
<path d="M14 8h28l8 8v40H14z" fill="none" stroke="#00f0ff" stroke-width="4"/>
<path d="M28 22v18a6 6 0 1 1-4-5.6V22h14v6H28" fill="#ff00d4"/></svg>"""
