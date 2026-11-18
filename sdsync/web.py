"""Control page (http://sdsync.local) and the full-screen monitor (/screen)."""
import glob
import html
import json
import os
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.parse
from urllib.parse import parse_qs

from . import cardsync, config, downloader, genres, sorter, takeout, theme

URL_OK = re.compile(r"^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)/", re.I)
LABEL_OK = re.compile(r"^[A-Z0-9_\-]{1,11}$")
esc = html.escape

# Client-side status rendering, shared by both pages.
STATUS_JS = r"""
const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=(d,t)=>t?Math.max(0,Math.min(100,Math.round(100*d/t))):0;
function bar(p,cls){return `<div class="bar ${cls||''}"><i style="width:${p}%"></i></div>`}
function renderDownload(d){
  if(d.state!=='busy') return `<div class="barline"><span>Idle. Waiting for the next check.</span><span class="mute">Last check: ${E(d.last||'never')}</span></div>${bar(0)}`;
  const all=d.total?pct(d.done+(d.song||0),d.total):0;
  return `<div class="barline"><span>${E(d.text)}</span><span>${d.total?`${d.done} of ${d.total} new`:'Checking...'}</span></div>
   ${bar(all)}
   <div class="barline"><span class="mute">Playlist ${d.playlist_no} of ${d.playlists}</span><span class="mute">${d.total?'This song: '+Math.round((d.song||0)*100)+'%':''}</span></div>
   ${bar(Math.round((d.song||0)*100),'thin')}`;
}
function libText(l){if(!l)return'';return `${l.songs} songs cached · ${l.gb} GB · ${l.free_gb} GB free`+(l.health&&l.health!=='all songs OK'?' · '+l.health:'')}
function renderDevices(list,targets,withButtons){
  if(!list.length) return `<div class="dev"><span class="ico"></span>No drive plugged in. Insert the SD card or USB stick.<span class="blink">_</span></div>`;
  const next=location.pathname;
  return list.map(v=>{
    const st={busy:'<b class="amber">Writing...</b>',done:'<b class="ok">Safe to remove</b>',
      error:'<b class="red">Error</b>',unassigned:'<b class="amber">Unknown drive</b>'}[v.state]||'';
    let extra='';
    if(v.state==='unassigned'&&withButtons){
      extra='<div class="row" style="margin-top:8px">'+targets.map(t=>
        `<form method="post" action="/assign"><input type="hidden" name="dev" value="${E(v.dev)}"><input type="hidden" name="target" value="${E(t.id)}"><input type="hidden" name="next" value="${E(next)}"><button>This is the ${E(t.name)}</button></form>`).join('')+
        '</div><div class="mute" style="font-size:13px;margin-top:6px">This sets the drive\'s name (volume label). No files are changed.</div>';
    }
    const p=v.state==='done'?100:pct(v.done,v.total);
    return `<div class="dev ${E(v.state)}"><div class="barline"><span><span class="ico"></span><b>${E(v.target_name||v.model)}</b> <span class="mute">${E(v.dev)} · ${v.size_gb||''} GB ${E(v.label||'')}</span></span><span>${st}</span></div>
      ${v.state==='busy'||v.state==='done'?bar(p,'pinkbar'):''}
      <div class="barline"><span class="mute">${E(v.text)}</span><span>${v.total?`${v.done} of ${v.total}`:''}</span></div>${extra}</div>`;
  }).join('');
}
"""

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SD//SYNC</title><style>@@css@@
main{max-width:900px;margin:0 auto;padding:12px 12px 40px}
.app>h2{font-size:15px}
.menu{display:flex;flex-wrap:wrap;gap:0;padding:2px 2px 0!important}
.menu a{color:#000;text-decoration:none;padding:10px 12px;min-height:var(--tap);display:flex;align-items:center}
.menu a:active,.menu a:hover{background:var(--navy);color:#fff}
.menu a u{text-decoration:underline}
</style>@@look@@</head><body><main>
<section class="panel app"><h2><span class="ttl">SD//SYNC :: Playlist Manager</span><span class="tag">@@back@@</span></h2>
<nav class="menu"><a href="#status"><u>S</u>tatus</a><a href="#add"><u>A</u>dd playlist</a><a href="#import"><u>I</u>mport</a><a href="#playlists"><u>P</u>laylists</a>
@@target_links@@<a href="#settings">S<u>e</u>ttings</a><a href="/screen"><u>M</u>onitor view</a></nav></section>

<section class="panel" id="status"><h2><span class="ttl">Status</span><span class="tag" id="clock"></span></h2>
<div><div class="group"><span class="legend">YouTube</span><div id="dl"></div></div>
<div class="group"><span class="legend">Drives</span><div id="devs"></div></div>
<div class="row" style="margin-top:10px">
<form method="post" action="/download"><button>Check YouTube now</button></form>
<form method="post" action="/card"><button>Write drives now</button></form></div></div>
<div class="status"><span id="sb1">Ready</span><span id="sb2"></span><span id="sb3"></span></div></section>

<section class="panel" id="add"><h2><span class="ttl">Add playlist</span></h2>
<form method="post" action="/add" style="display:block"><div class="row">
<div class="grow" style="flex-basis:100%"><label>YouTube playlist link:</label><input name="url" placeholder="https://www.youtube.com/playlist?list=..." required></div>
<div class="grow"><label>Name (optional):</label><input name="name" maxlength="40" placeholder="Taken from YouTube if blank"></div>
<div class="grow"><label>Put it on:</label><select name="to">@@add_targets@@</select></div>
<button class="hot">Add</button></div></form></section>

<section class="panel" id="import"><h2><span class="ttl">Import liked songs &amp; private playlists</span><span class="tag">from Google Takeout</span></h2><div>@@import_@@</div></section>

<section class="panel" id="playlists"><h2><span class="ttl">Playlists</span><span class="tag">downloaded once, used by any drive</span></h2><div>@@playlists@@</div></section>

@@targets@@

<section class="panel" id="settings"><h2><span class="ttl">Settings</span></h2>
<form method="post" action="/settings" style="display:block"><div class="row">
<div class="grow"><label>Check YouTube every (hours):</label><input name="download_interval_hours" type="number" min="1" max="168" value="@@interval@@"></div>
<div class="grow"><label>MP3 quality, kbps (new downloads):</label><select name="bitrate_kbps">@@bitrates@@</select></div>
<div class="grow"><label>Look:</label><select name="look">@@looks@@</select></div>
<div class="grow"><label>Monitor background (cyberspace look):</label><select name="background">@@backgrounds@@</select></div>
<div class="grow"><label>Turn monitor off when untouched for:</label><select name="screen_off_minutes">@@screen_off@@</select></div>
<div class="grow"><label>Check YouTube when a drive is plugged in:</label><select name="check_on_insert">@@check_insert@@</select></div>
<button>Save</button></div></form></section>

<section class="panel"><h2><span class="ttl">Activity log</span></h2><div><pre class="log" id="log"></pre></div></section>
</main><script>
const TARGETS=@@targets_json@@;
@@theme_js@@
@@status_js@@
async function tick(){try{const s=await (await fetch('/api/status')).json();
document.getElementById('clock').textContent=s.time;
document.getElementById('dl').innerHTML=renderDownload(s.download);
const devs=document.getElementById('devs');const html=renderDevices(s.devices,TARGETS,true);
if(devs._h!==html){devs.innerHTML=html;devs._h=html;}
document.getElementById('sb1').textContent=s.download.state==='busy'?'Downloading...':'Ready';
document.getElementById('sb2').textContent=s.devices.length+' drive(s) plugged in';
document.getElementById('sb3').textContent=libText(s.library);
document.getElementById('log').textContent=s.log.slice().reverse().join('\\n');}catch(e){document.getElementById('sb1').textContent='Not connected'}}
tick();setInterval(tick,1500);
@@kiosk@@
</script></body></html>"""

SORT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
@@refresh@@<title>SD//SYNC sort</title><style>@@css@@
main{max-width:900px;margin:0 auto;padding:12px 12px 90px}
.songs .item{display:flex;gap:10px;align-items:center;padding:6px 0}
.songs input[type=checkbox],.gen input[type=checkbox]{width:28px;height:28px;flex:none}
.gen .item{display:flex;gap:10px;align-items:center}
.dock{position:fixed;left:0;right:0;bottom:0;padding:8px 12px;background:#06060f;border-top:2px solid #00f0ff;z-index:5}
.dock .row{max-width:900px;margin:0 auto}
</style>@@look@@</head><body><main>
<section class="panel app"><h2><span class="ttl">Sort :: @@name@@</span><span class="tag"><a href="/#playlists" style="color:inherit">Back</a></span></h2>
<div class="mute">@@stats@@</div></section>
<section class="panel" id="genres"><h2><span class="ttl">By genre</span><span class="tag">from MusicBrainz</span></h2><div>@@genres@@</div></section>
<section class="panel" id="songs"><h2><span class="ttl">Songs</span><span class="tag">tick songs to move them by hand</span></h2><div>
<form method="post" action="/sort/songs" id="songform" style="display:block">@@hidden@@
<div class="row" style="margin-bottom:8px"><div class="grow"><label>Find:</label><input id="find" placeholder="artist, title, album or genre"></div>
<label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="unsorted" style="width:28px;height:28px"> Only unsorted</label></div>
<div class="songs">@@songs@@</div>
<div class="dock"><div class="row"><div class="grow"><label>Ticked songs (<span id="nt">0</span>):</label><select name="dest">@@dests@@</select></div>
<div class="grow"><label>New playlist name:</label><input name="new_name" maxlength="40"></div>
<div class="grow"><label>New ones go on:</label><select name="to">@@add_targets@@</select></div>
<button class="hot" name="op" value="add">Add to playlist</button><button name="op" value="remove">Take out</button></div></div>
</form></div></section>
</main><script>
@@theme_js@@
const rows=[...document.querySelectorAll('.songs .item')];
function filt(){const q=document.getElementById('find').value.toLowerCase();const u=document.getElementById('unsorted').checked;
for(const r of rows){r.style.display=(r.dataset.k.includes(q)&&(!u||r.dataset.s==='0'))?'':'none';}}
document.getElementById('find').addEventListener('input',filt);document.getElementById('unsorted').addEventListener('change',filt);
document.querySelector('.songs').addEventListener('change',()=>{document.getElementById('nt').textContent=document.querySelectorAll('.songs input:checked').length;});
@@kiosk@@
</script></body></html>"""

SCREEN = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SD//SYNC monitor</title><style>@@css@@
html,body{height:100%;overflow:hidden}
body{font-size:clamp(14px,1.45vw,22px)}
.desk{height:100%;display:grid;grid-template-rows:1fr auto}
.wins{display:grid;grid-template-columns:1.15fr 1fr;gap:14px;padding:14px;min-height:0}
.col{display:grid;grid-template-rows:auto 1fr;gap:14px;min-height:0}
.wins>*,.col>*{min-width:0}
.panel{margin:0;min-height:0;display:flex;flex-direction:column}
.panel>h2{font-size:1em}
.panel>div{min-height:0;overflow:auto;flex:1}
.barline{font-size:1em} .bar{height:1.9em} .bar.thin{height:1em}
pre.log{max-height:none;height:100%;font-size:.8em}
.task{display:flex;gap:6px;align-items:center;background:var(--face);box-shadow:inset 0 1px var(--lt),inset 0 2px var(--hi);padding:6px}
.task button{min-height:54px;font-size:1em}
.task .app{font-weight:bold}
.tray{margin-left:auto;box-shadow:inset 1px 1px var(--sh),inset -1px -1px var(--hi);padding:0 14px;min-height:54px;display:flex;align-items:center;gap:14px}
@media (max-width:800px){.wins{grid-template-columns:1fr}}
</style>@@look@@</head><body>@@bg_canvas@@<div class="desk"><div class="wins">
 <div class="col">
  <section class="panel"><h2><span class="ttl">YouTube download</span></h2><div id="dl"></div></section>
  <section class="panel"><h2><span class="ttl">Drives</span></h2><div id="devs"></div></section>
 </div>
 <section class="panel"><h2><span class="ttl">Activity log</span><span class="tag" id="lib">@@lib@@</span></h2><div><pre class="log" id="log"></pre></div></section>
</div>
<div class="task">
 <form method="get" action="/"><button class="app">SD//SYNC</button></form>
 <form method="post" action="/download"><input type="hidden" name="next" value="/screen"><button>Check YouTube now</button></form>
 <form method="post" action="/card"><input type="hidden" name="next" value="/screen"><button>Write drives now</button></form>
 <form method="get" action="/"><button>Playlists &amp; drives...</button></form>
 <div class="tray"><span class="mute">@@addr@@</span><b id="clock">--:--</b></div>
</div></div><script>
const TARGETS=@@targets_json@@;
@@theme_js@@
@@status_js@@
async function tick(){try{const s=await (await fetch('/api/status')).json();
document.getElementById('clock').textContent=s.time.slice(0,5);
document.getElementById('dl').innerHTML=renderDownload(s.download);
const devs=document.getElementById('devs');const html=renderDevices(s.devices,TARGETS,true);
if(devs._h!==html){devs.innerHTML=html;devs._h=html;}
document.getElementById('lib').textContent=libText(s.library);
document.getElementById('log').textContent=s.log.slice().reverse().join('\\n');}catch(e){
document.getElementById('clock').textContent='Offline';}}
tick();setInterval(tick,1000);
@@bg_js@@
if(location.search.includes('bgonly'))document.querySelector('.desk').style.display='none';
@@kiosk@@
</script></body></html>"""


def render(tpl, kiosk=False, look="cyber", background="gibson", **values):
    cyber = look == "cyber"
    bg_js = theme.background_js(background) if cyber else ""
    out = (tpl.replace("@@css@@", theme.CSS).replace("@@theme_js@@", theme.JS)
           .replace("@@look@@", theme.CYBER_FONTS + "<style>" + theme.CYBER_CSS + "</style>" if cyber else "")
           .replace("@@bg_canvas@@", '<canvas id="bg"></canvas>' if bg_js else "")
           .replace("@@bg_js@@", bg_js)
           .replace("@@status_js@@", STATUS_JS).replace("@@kiosk@@", "initKiosk();" if kiosk else ""))
    for k, v in values.items():
        out = out.replace("@@" + k + "@@", str(v))
    return out


def _hidden(**kw):
    return "".join(f"<input type='hidden' name='{k}' value='{esc(str(v))}'>" for k, v in kw.items())


def _btn(action, label, cls="sm", confirm=None, **kw):
    onsub = f" data-confirm='{esc(confirm)}'" if confirm else ""
    return f"<form method='post' action='{action}'{onsub}>{_hidden(**kw)}<button class='{cls}'>{label}</button></form>"


def _pl_title(p):
    return p.get("name") or downloader.read_order(p["id"]).get("title") or "(name comes from YouTube)"


def _playlists_html(cfg):
    if not cfg["playlists"]:
        return "<div class='mute'>No playlists yet. Paste a YouTube playlist link above.</div>"
    out = []
    for p in cfg["playlists"]:
        order = downloader.read_order(p["id"])
        have = len(glob.glob(os.path.join(downloader.playlist_dir(p["id"]), "*.mp3")))
        total = len(order["tracks"])
        count = f"{have}/{total} songs" if total else "not downloaded yet"
        used = [t["name"] for t in cfg["targets"] if any(p["id"] in f["playlists"] for f in t["folders"])]
        on = p.get("enabled", True)
        out.append(
            f"<div class='item{'' if on else ' off'}'><div class='t'>{esc(_pl_title(p))}{'' if on else ' (paused)'}</div>"
            f"<div class='u'>{count} · used on: {esc(', '.join(used) or 'nothing yet')} · "
            f"{'imported from Google Takeout' if p.get('source') == 'takeout' else esc(p['url'])}</div>"
            f"<div class='row' style='margin-top:6px'>"
            + _btn("/toggle", "Pause" if on else "Resume", id=p["id"])
            + (f"<form method='get' action='/sort'><input type='hidden' name='from' value='{esc(p['id'])}'>"
               f"<button class='sm'>Sort into playlists</button></form>"
               if p.get("source") == "takeout" and not p.get("parent") else "")
            + _btn("/remove", "Delete", "sm hot", "Delete this playlist and its songs from every drive?", id=p["id"])
            + "</div></div>")
    return "".join(out)


def _import_html(cfg, add_targets):
    pending = takeout.load_pending()
    if not pending:
        return (
            "<div class='mute' style='margin-bottom:8px'>YouTube keeps liked songs and private playlists to itself, "
            "so the box can't read them from a link. Get a copy at takeout.google.com: deselect all, tick "
            "<b>YouTube and YouTube Music</b>, under <i>All YouTube data included</i> keep only <b>playlists</b> and "
            "<b>music-library-songs</b>, then upload the .zip here. A single playlist .csv from it works too.</div>"
            "<form method='post' action='/import/upload' enctype='multipart/form-data'><div class='row'>"
            "<div class='grow'><label>Takeout file (.zip or .csv):</label><input type='file' name='file' accept='.zip,.csv' required></div>"
            "<button class='hot'>Read file</button></div></form>")
    have = {p["name"]: p for p in cfg["playlists"] if p.get("source") == "takeout"}
    rows = []
    for i, pl in enumerate(pending):
        note = " · already on the box, its song list will be updated" if pl["name"] in have else ""
        checked = " checked" if pl.get("library") or pl["name"] in have else ""
        rows.append(
            f"<label class='item' style='display:flex;gap:10px;align-items:center'>"
            f"<input type='checkbox' name='pick_{i}' value='1'{checked} style='width:28px;height:28px'>"
            f"<span><span class='t'>{esc(pl['name'])}</span>"
            f"<span class='u'> {len(pl['tracks'])} songs{note}</span></span></label>")
    return (
        "<form method='post' action='/import/confirm' style='display:block'>"
        "<div class='mute' style='margin-bottom:8px'>Found in the file. Tick what the box should download:</div>"
        + "".join(rows)
        + f"<div class='row' style='margin-top:8px'><div class='grow'><label>Put new ones on:</label>"
          f"<select name='to'>{add_targets}</select></div><button class='hot'>Import ticked</button></div></form>"
        + "<div class='row' style='margin-top:6px'>" + _btn("/import/cancel", "Cancel") + "</div>")


def _genres_html(cfg, pid, tracks, min_songs, add_targets):
    job = genres.JOB
    hid = _hidden(**{"from": pid})
    if job.running() and job.pid == pid:
        left = max(0, job.total - job.done)
        return (f"<div>Looking up genres: {job.done} of {job.total} songs done, up to {max(1, round(left * 1.1 / 60))} min left. "
                "This page refreshes by itself. Songs already asked about once are instant next time.</div>")
    results = genres.load_results(pid)
    if not results:
        err = f"<div class='red'>Last try stopped: {esc(job.error)}</div>" if job.error and job.pid == pid else ""
        return (err + "<div class='mute' style='margin-bottom:8px'>The box asks MusicBrainz (a free music database) for the genre of "
                f"each song's album, or else its artist. {len(tracks)} songs take about {max(1, len(tracks) // 60)} to "
                f"{max(2, len(tracks) // 30)} minutes the first time. You can leave this page while it runs.</div>"
                f"<form method='post' action='/sort/genres'>{hid}<button class='hot'>Look up genres</button></form>")
    sorted_ids = sorter.membership(cfg, pid)
    groups = genres.summary(results, tracks, sorted_ids, min_songs)
    found = sum(1 for t in tracks if results.get(t["id"]))
    mins = "".join(f"<option value='{m}'{' selected' if m == min_songs else ''}>{m}</option>" for m in (1, 5, 10, 20, 30, 50))
    head = (f"<div class='mute' style='margin-bottom:8px'>Found a genre for {found} of {len(tracks)} songs. "
            "Tick the genres to turn into playlists, and rename them if you like. Songs already sorted aren't counted again.</div>"
            f"<form method='get' action='/sort' class='row' style='margin-bottom:8px'>{hid}"
            f"<div class='grow'><label>Smallest genre with its own playlist (songs):</label><select name='min' onchange='this.form.submit()'>{mins}</select></div></form>")
    if not groups:
        return head + "<div>Every song is sorted.</div>"
    rows = "".join(
        f"<div class='item'><input type='checkbox' name='g_{i}' value='1'{'' if g in ('Unknown genre',) else ' checked'}>"
        f"<div class='grow'><input name='n_{i}' value='{esc(g)}' maxlength='40'></div><span class='u'>{len(ids)} songs</span></div>"
        for i, (g, ids) in enumerate(groups))
    return (head + f"<form method='post' action='/sort/make' style='display:block' class='gen'>{hid}<input type='hidden' name='min' value='{min_songs}'>"
            + rows + f"<div class='row' style='margin-top:8px'><div class='grow'><label>Put new playlists on:</label><select name='to'>{add_targets}</select></div>"
            "<button class='hot'>Make playlists</button></div></form>"
            f"<div class='row' style='margin-top:6px'>" + _btn("/sort/genres", "Look up again", **{"from": pid}) + "</div>")


def _sort_page(cfg, pid, min_songs, kiosk, add_targets):
    src = next((p for p in cfg["playlists"] if p["id"] == pid and p.get("source") == "takeout"), None)
    if not src:
        return None
    tracks = sorter.source_tracks(pid)
    member = sorter.membership(cfg, pid)
    results = genres.load_results(pid) or {}
    kids = sorter.children(cfg, pid)
    songs = []
    for t in tracks:
        g = results.get(t["id"], "")
        inn = member.get(t["id"], [])
        line = " - ".join(x for x in (t.get("artist", ""), t.get("title") or t["id"]) if x)
        sub = " · ".join(x for x in (t.get("album", ""), g, ("in: " + ", ".join(inn)) if inn else "") if x)
        key = f"{line} {sub}".lower()
        songs.append(
            f"<label class='item' data-k='{esc(key)}' data-s='{1 if inn else 0}'><input type='checkbox' name='v' value='{esc(t['id'])}'>"
            f"<span><span class='t'>{esc(line)}</span><br><span class='u'>{esc(sub)}</span></span></label>")
    dests = "<option value=''>New playlist (name it)</option>" + "".join(
        f"<option value='{esc(k['id'])}'>{esc(k['name'])}</option>" for k in kids)
    return render(
        SORT, kiosk, cfg.get("look", "cyber"),
        refresh="<meta http-equiv='refresh' content='5'>" if genres.JOB.running() and genres.JOB.pid == pid else "",
        name=esc(src["name"]), hidden=_hidden(**{"from": pid}),
        stats=f"{len(tracks)} songs · {len(member)} sorted into {len(kids)} playlists · {len(tracks) - len(member)} not sorted yet",
        genres=_genres_html(cfg, pid, tracks, min_songs, add_targets),
        songs="".join(songs), dests=dests, add_targets=add_targets)


def _add_targets(cfg):
    return ("".join(f"<option value='{esc(t['id'])}'>{esc(t['name'])}</option>" for t in cfg["targets"])
            + "<option value=''>Nowhere yet (just download)</option>")


def _sort_post(path, form, raw):
    pid = form.get("from", "")
    try:
        min_songs = max(1, int(form.get("min") or 10))
    except ValueError:
        min_songs = 10
    if path == "/sort/genres":
        genres.JOB.start(pid, sorter.source_tracks(pid))
        return pid
    if path == "/sort/make":
        tracks = sorter.source_tracks(pid)

        def mk(c):
            groups = genres.summary(genres.load_results(pid) or {}, tracks, sorter.membership(c, pid), min_songs)
            t = config.target(c, form.get("to", ""))
            for i, (g, ids) in enumerate(groups):
                if form.get(f"g_{i}"):
                    sorter.add(c, pid, ids, new_name=form.get(f"n_{i}") or g, target=t, next_cd_name=_next_cd_name)
        config.update(mk)
        return pid
    if path == "/sort/songs":
        vids = [v.strip() for v in raw.get("v", [])]

        def so(c):
            if form.get("op") == "remove":
                sorter.remove(c, pid, form.get("dest", ""), vids)
            elif vids:
                sorter.add(c, pid, vids, dest=form.get("dest") or None, new_name=form.get("new_name", ""),
                           target=config.target(c, form.get("to", "")), next_cd_name=_next_cd_name)
        config.update(so)
        return pid
    return None


def _parse_multipart(ctype, body):
    """{field name: (filename, bytes)} from a multipart/form-data body."""
    from email import policy
    from email.parser import BytesParser

    msg = BytesParser(policy=policy.HTTP).parsebytes(b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + body)
    out = {}
    if not msg.is_multipart():
        return out
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if name:
            out[name] = (part.get_filename() or "", part.get_payload(decode=True) or b"")
    return out


def _import_confirm(form):
    pending = takeout.load_pending()
    picked = [pl for i, pl in enumerate(pending) if form.get(f"pick_{i}")]
    if not picked:
        return 0

    def imp(c):
        have = {p["name"]: p for p in c["playlists"] if p.get("source") == "takeout"}
        t = config.target(c, form.get("to", ""))
        for pl in picked:
            old = have.get(pl["name"])
            if old:
                takeout.save_tracks(old["id"], pl["tracks"])
                continue
            new = {"id": uuid.uuid4().hex[:8], "url": "", "name": pl["name"][:40],
                   "source": "takeout", "enabled": True}
            takeout.save_tracks(new["id"], pl["tracks"])
            c["playlists"].append(new)
            if t:
                name = "" if t.get("number_folders") else _next_cd_name(t)
                t["folders"].append({"name": name, "playlists": [new["id"]]})
    config.update(imp)
    takeout.clear_pending()
    return len(picked)


def _target_html(cfg, t):
    on_drive = {}   # folder index -> [(folder name on drive, songs)]
    try:
        for e in cardsync.build_plan(cfg, t):
            on_drive.setdefault(e["index"], []).append((e["folder"], len(e["files"])))
    except Exception:
        pass
    opts = "".join(f"<option value='{esc(p['id'])}'>{esc(_pl_title(p))}</option>" for p in cfg["playlists"])
    rows = []
    for i, f in enumerate(t["folders"]):
        title = cardsync.folder_title(cfg, f)
        parts = on_drive.get(i, [])
        where = " ".join(f"On drive: <b>\\{esc(n)}\\</b> {c} songs" for n, c in parts) \
            or "<span class='mute'>nothing downloaded yet</span>"
        chips = "".join(
            f"<span class='chip'><span>{esc(_pl_title(p))}</span>"
            f"<form method='post' action='/folder/rmpl'>{_hidden(target=t['id'], idx=i, playlist=p['id'])}"
            f"<button title='Take this playlist out of the folder' aria-label='Remove'>X</button></form></span>"
            for pid in f["playlists"] for p in cfg["playlists"] if p["id"] == pid)
        rows.append(
            f"<div class='item'><div class='row'>"
            f"<form method='post' action='/folder/rename' class='grow' style='display:flex;gap:6px'>{_hidden(target=t['id'], idx=i)}"
            f"<input name='name' value='{esc(f.get('name', ''))}' placeholder='{esc(title)}' maxlength='40'><button class='sm'>Rename</button></form>"
            + _btn("/folder/move", "Up", target=t["id"], idx=i, dir=-1)
            + _btn("/folder/move", "Down", target=t["id"], idx=i, dir=1)
            + _btn("/folder/remove", "Remove", "sm hot", "Remove this folder from the drive?", target=t["id"], idx=i)
            + f"</div><div class='u' style='margin-top:6px'>{where}</div><div style='margin-top:4px'>{chips or '<span class=red>No playlist in this folder</span>'}</div>"
            + (f"<form method='post' action='/folder/addpl' class='row' style='margin-top:6px'>{_hidden(target=t['id'], idx=i)}"
               f"<select name='playlist' class='grow'>{opts}</select><button class='sm'>Add to folder</button></form>" if opts else "")
            + "</div>")
    folder_hint = "CD07" if not t.get("number_folders") else "Folder name"
    return (
        f"<section class='panel' id='t-{esc(t['id'])}'><h2><span class='ttl'>{esc(t['name'])}</span><span class='tag'>drive label {esc(t['label'])}</span></h2><div>"
        + ("".join(rows) or "<div class='mute'>No folders yet.</div>")
        + f"<div class='group'><span class='legend'>New folder</span><form method='post' action='/folder/add' class='row'>{_hidden(target=t['id'])}"
          f"<div class='grow'><label>Folder name:</label><input name='name' placeholder='{folder_hint} (blank = playlist name)' maxlength='40'></div>"
          f"<div class='grow'><label>With playlist:</label><select name='playlist'>{opts}</select></div>"
          f"<button>Add folder</button></form></div>"
        + f"<div class='group'><span class='legend'>Drive settings</span><form method='post' action='/target' class='row'>{_hidden(target=t['id'])}"
          f"<div class='grow'><label>Drive label:</label><input name='label' value='{esc(t['label'])}' maxlength='11'></div>"
          f"<div class='grow'><label>Max songs per folder:</label><input name='max_files_per_folder' type='number' min='1' max='999' value='{t['max_files_per_folder']}'></div>"
          f"<div class='grow'><label>Max folders:</label><input name='max_folders' type='number' min='1' max='99' value='{t['max_folders']}'></div>"
          f"<div class='grow'><label>If a playlist is too long:</label><select name='overflow'>"
          f"<option value='split'{' selected' if t['overflow'] == 'split' else ''}>Split into more folders</option>"
          f"<option value='truncate'{' selected' if t['overflow'] == 'truncate' else ''}>Leave the rest out</option></select></div>"
          f"<button>Save</button></form></div>"
        + "<div class='row' style='margin-top:10px'>"
        + _btn("/rewrite", "Rewrite whole drive", "sm hot",
               "Erase this box's folders on the drive and write them again in order?", target=t["id"])
        + "</div></div></section>")


def _next_cd_name(t):
    used = {f.get("name", "").upper() for f in t["folders"]}
    for n in range(1, 100):
        if f"CD{n:02d}" not in used:
            return f"CD{n:02d}"
    return ""


def _folder(c, form):
    t = config.target(c, form.get("target"))
    try:
        i = int(form.get("idx", "-1"))
    except ValueError:
        return t, None, None
    if not t or not 0 <= i < len(t["folders"]):
        return t, None, None
    return t, i, t["folders"][i]


def serve(service, host, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="text/html; charset=utf-8"):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _back(self, to="/"):
            self.send_response(303)
            self.send_header("Location", to if to in ("/", "/screen") else "/")
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/status":
                return self._send(200, json.dumps(service.status.get()), "application/json")
            cfg = config.load()
            kiosk = self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")
            targets_json = json.dumps([{"id": t["id"], "name": t["name"]} for t in cfg["targets"]]).replace("<", "\\u003c")
            if path == "/screen":
                songs = sum(len(glob.glob(os.path.join(downloader.playlist_dir(p["id"]), "*.mp3")))
                            for p in cfg["playlists"])
                host_name = os.uname().nodename
                return self._send(200, render(
                    SCREEN, kiosk, cfg.get('look', 'cyber'), cfg.get('background', 'gibson'), addr=esc(f"http://{host_name}.local"), targets_json=targets_json,
                    lib=f"{len(cfg['playlists'])} playlists · {songs} songs in library"))
            if path == "/sort":
                q = parse_qs(self.path.partition("?")[2])
                try:
                    min_songs = max(1, int(q.get("min", ["10"])[0]))
                except ValueError:
                    min_songs = 10
                page = _sort_page(cfg, q.get("from", [""])[0], min_songs, kiosk, _add_targets(cfg))
                if page is None:
                    return self._send(404, "That playlist is gone. <a href='/'>Back</a>")
                return self._send(200, page)
            if path != "/":
                return self._send(404, "Not found", "text/plain")
            bitrates = "".join(
                f"<option{' selected' if b == int(cfg['bitrate_kbps']) else ''}>{b}</option>"
                for b in (128, 160, 192, 256, 320))
            add_targets = "".join(f"<option value='{esc(t['id'])}'>{esc(t['name'])}</option>" for t in cfg["targets"])
            add_targets += "<option value=''>Nowhere yet (just download)</option>"
            looks = "".join(
                f"<option value='{v}'{' selected' if cfg.get('look', 'cyber') == v else ''}>{n}</option>"
                for v, n in (("cyber", "Cyberspace (neon, hacker movie)"), ("classic", "Classic 90s desktop")))
            cur_bg = cfg.get("background", "gibson")
            backgrounds = "".join(
                f"<option value='{k}'{' selected' if k == cur_bg else ''}>{esc(v[0])}</option>"
                for k, v in theme.BACKGROUNDS.items())
            off = int(float(cfg.get("screen_off_minutes", 5)))
            screen_off = "".join(
                f"<option value='{m}'{' selected' if m == off else ''}>{'Never' if m == 0 else f'{m} min'}</option>"
                for m in (0, 1, 2, 5, 10, 15, 30, 60))
            ci = cfg.get("check_on_insert", True)
            check_insert = (f"<option value='1'{' selected' if ci else ''}>Yes, if the last check is over an hour old</option>"
                            f"<option value='0'{'' if ci else ' selected'}>No</option>")
            target_links = "".join(f"<a href='#t-{esc(t['id'])}'>{esc(t['name'])}</a>" for t in cfg["targets"])
            back = "<a href='/screen' style='color:#fff'>Back to monitor view</a>" if kiosk else ""
            self._send(200, render(
                PAGE, kiosk, cfg.get('look', 'cyber'), back=back, looks=looks, backgrounds=backgrounds, screen_off=screen_off, check_insert=check_insert, target_links=target_links, playlists=_playlists_html(cfg), add_targets=add_targets,
                import_=_import_html(cfg, add_targets),
                targets="".join(_target_html(cfg, t) for t in cfg["targets"]),
                targets_json=targets_json, bitrates=bitrates,
                interval=int(float(cfg["download_interval_hours"]))))

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            path = self.path
            if path == "/import/upload":
                if n > takeout.MAX_UPLOAD:
                    return self._send(413, "That file is too big. Export only playlists and music-library-songs. <a href='/#import'>Back</a>")
                parts = _parse_multipart(self.headers.get("Content-Type", ""), self.rfile.read(n))
                filename, data = parts.get("file", ("", b""))
                try:
                    takeout.save_pending(takeout.parse(filename, data))
                except ValueError as e:
                    return self._send(400, f"{esc(str(e))} <a href='/#import'>Back</a>")
                self.send_response(303)
                self.send_header("Location", "/#import")
                self.end_headers()
                return
            raw = parse_qs(self.rfile.read(n).decode())
            form = {k: v[0].strip() for k, v in raw.items()}
            if path.startswith("/sort/"):
                pid_ = _sort_post(path, form, raw)
                if pid_ is None:
                    return self._send(404, "Not found", "text/plain")
                if path != "/sort/genres":
                    service.download_now.set()
                self.send_response(303)
                self.send_header("Location", "/sort?" + urllib.parse.urlencode({"from": pid_, "min": form.get("min", "10")}))
                self.end_headers()
                return
            pid = form.get("id")
            if path == "/api/wake":
                service.display.activity("touch")
                service.status.display_on = True
                return self._send(200, "{}", "application/json")
            if path == "/add":
                url = form.get("url", "")
                if not URL_OK.match(url):
                    return self._send(400, "That does not look like a YouTube link. <a href='/'>Back</a>")

                def add(c):
                    new = {"id": uuid.uuid4().hex[:8], "url": url, "name": form.get("name", ""), "enabled": True}
                    c["playlists"].append(new)
                    t = config.target(c, form.get("to", ""))
                    if t:
                        name = "" if t.get("number_folders") else _next_cd_name(t)
                        t["folders"].append({"name": name, "playlists": [new["id"]]})
                config.update(add)
                service.download_now.set()
            elif path == "/remove":
                def rm(c):
                    c["playlists"] = [p for p in c["playlists"] if p["id"] != pid]
                    for t in c["targets"]:
                        for f in t["folders"]:
                            f["playlists"] = [x for x in f["playlists"] if x != pid]
                        t["folders"] = [f for f in t["folders"] if f["playlists"]]
                config.update(rm)
                takeout.delete_tracks(pid)
                service.card_now.set()
            elif path == "/toggle":
                def tg(c):
                    for p in c["playlists"]:
                        if p["id"] == pid:
                            p["enabled"] = not p.get("enabled", True)
                config.update(tg)
                service.card_now.set()
            elif path.startswith("/folder/"):
                op = path[len("/folder/"):]

                def fo(c):
                    t, i, f = _folder(c, form)
                    if not t:
                        return
                    if op == "add":
                        pl = form.get("playlist")
                        if any(p["id"] == pl for p in c["playlists"]):
                            name = form.get("name", "")[:40]
                            if not name and not t.get("number_folders"):
                                name = _next_cd_name(t)
                            t["folders"].append({"name": name, "playlists": [pl]})
                        return
                    if f is None:
                        return
                    if op == "remove":
                        t["folders"].pop(i)
                    elif op == "rename":
                        f["name"] = form.get("name", "")[:40]
                    elif op == "move":
                        j = i + int(form.get("dir", "0"))
                        if 0 <= j < len(t["folders"]):
                            t["folders"][i], t["folders"][j] = t["folders"][j], t["folders"][i]
                    elif op == "addpl":
                        pl = form.get("playlist")
                        if pl not in f["playlists"] and any(p["id"] == pl for p in c["playlists"]):
                            f["playlists"].append(pl)
                    elif op == "rmpl":
                        f["playlists"] = [x for x in f["playlists"] if x != form.get("playlist")]
                config.update(fo)
            elif path == "/target":
                err = []

                def ts(c):
                    t = config.target(c, form.get("target"))
                    if not t:
                        return
                    label = form.get("label", "").upper()
                    if LABEL_OK.match(label) and all(o["label"] != label for o in c["targets"] if o is not t):
                        t["label"] = label
                    elif label != t["label"]:
                        err.append("Label must be 1-11 letters, digits, - or _, and differ from the other drive.")
                    t["max_files_per_folder"] = max(1, min(999, int(form.get("max_files_per_folder") or 99)))
                    t["max_folders"] = max(1, min(99, int(form.get("max_folders") or 99)))
                    t["overflow"] = "truncate" if form.get("overflow") == "truncate" else "split"
                config.update(ts)
                if err:
                    return self._send(400, f"{esc(err[0])} <a href='/'>Back</a>")
            elif path == "/assign":
                try:
                    ok = service.assign(form.get("dev", ""), form.get("target", ""))
                except Exception as e:
                    return self._send(500, f"Could not label the drive: {esc(str(e))} <a href='/'>Back</a>")
                if not ok:
                    return self._send(400, "That drive is gone or isn't FAT32. <a href='/'>Back</a>")
            elif path == "/import/confirm":
                if _import_confirm(form):
                    service.download_now.set()
            elif path == "/import/cancel":
                takeout.clear_pending()
            elif path == "/download":
                service.download_now.set()
            elif path == "/card":
                service.card_now.set()
            elif path == "/rewrite":
                service.rewrite_next.add(form.get("target", ""))
                service.card_now.set()
            elif path == "/settings":
                def st(c):
                    c["download_interval_hours"] = max(1, min(168, int(form.get("download_interval_hours") or 6)))
                    c["bitrate_kbps"] = int(form.get("bitrate_kbps") or 192)
                    c["look"] = "classic" if form.get("look") == "classic" else "cyber"
                    if form.get("background") in theme.BACKGROUNDS:
                        c["background"] = form["background"]
                    try:
                        c["screen_off_minutes"] = max(0, min(240, int(form.get("screen_off_minutes", 5))))
                    except ValueError:
                        pass
                    c["check_on_insert"] = form.get("check_on_insert", "1") == "1"
                config.update(st)
            else:
                return self._send(404, "Not found", "text/plain")
            self._back(form.get("next", "/"))

    ThreadingHTTPServer((host, port), Handler).serve_forever()
