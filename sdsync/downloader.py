"""Download YouTube playlists into the local MP3 cache on the Pi.

Cache layout, one folder per playlist:
    cache/<playlist id>/order.json   playlist order and tags, refreshed every run
    cache/<playlist id>/<video>.mp3  finished, tagged songs
    cache/<playlist id>/work/        in-progress downloads (never copied to a card)

Only finished files are moved into the playlist folder, so a card can be
written while a download is still running.
"""
import glob
import json
import logging
import os
import shutil
import time

from . import config, names, takeout

log = logging.getLogger("sdsync.download")

RETRY_FAILED_AFTER = 7 * 24 * 3600  # deleted/blocked videos are retried weekly


def playlist_dir(pid):
    return os.path.join(config.CACHE_DIR, pid)


def read_order(pid):
    try:
        with open(os.path.join(playlist_dir(pid), "order.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"title": "", "tracks": []}


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def _base_opts(cfg):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": True,
        "retries": 5,
        "socket_timeout": 30,
        "logger": logging.getLogger("sdsync.yt-dlp"),
    }
    if cfg.get("cookies_file"):
        opts["cookiefile"] = cfg["cookies_file"]
    return opts


def video_url(vid):
    return f"https://www.youtube.com/watch?v={vid}"


def fetch_listing(url, cfg):
    """Return (playlist title, [ {id, title, artist} ... ]) in playlist order."""
    import yt_dlp

    opts = _base_opts(cfg) | {"extract_flat": "in_playlist", "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("YouTube returned nothing for this link (private playlist or bad URL?)")
    entries = info.get("entries")
    if entries is None:  # a single video link
        entries = [info]
    tracks, seen = [], set()
    for e in entries:
        if not e or not e.get("id") or e["id"] in seen:
            continue
        title = e.get("title") or ""
        if title in ("[Private video]", "[Deleted video]"):
            continue
        seen.add(e["id"])
        artist, song = names.split_artist_title(title, e.get("channel") or e.get("uploader") or "")
        tracks.append({"id": e["id"], "title": song or e["id"], "artist": artist})
    return names.clean_text(info.get("title") or ""), tracks


def tag_mp3(path, title, artist, album):
    """ID3v2.3 plus ID3v1, no cover art: the safest combination for older head units."""
    from mutagen.id3 import ID3, TALB, TIT2, TPE1, ID3NoHeaderError

    try:
        tags = ID3(path)
        tags.delete(path)
    except ID3NoHeaderError:
        pass
    tags = ID3()
    tags.add(TIT2(encoding=0, text=title[:120]))
    if artist:
        tags.add(TPE1(encoding=0, text=artist[:120]))
    if album:
        tags.add(TALB(encoding=0, text=album[:120]))
    tags.save(path, v1=2, v2_version=3)


def sync_playlist(pl, cfg, progress=None):
    """Bring one playlist's cache up to date. Returns number of new songs.

    progress(text, done, total, song_fraction) is called as songs download.
    """
    import yt_dlp

    pid = pl["id"]
    pdir = playlist_dir(pid)
    work = os.path.join(pdir, "work")
    os.makedirs(work, exist_ok=True)

    imported = pl.get("source") == "takeout"
    if imported:
        # A fixed list from a Google Takeout export. Titles of songs that were
        # not in the music library are learned while downloading (see below).
        known = {t["id"]: t for t in read_order(pid)["tracks"]}
        tracks = [known.get(t["id"]) if not t.get("title") and t["id"] in known else t
                  for t in takeout.load_tracks(pid)]
        yt_title = pl.get("name") or "Imported playlist"
    else:
        yt_title, tracks = fetch_listing(pl["url"], cfg)
    album = names.clean_text(pl.get("name") or yt_title) or "Playlist"
    _write_json(os.path.join(pdir, "order.json"), {"title": yt_title, "tracks": tracks})

    # Drop songs that were removed from the playlist.
    wanted = {t["id"] for t in tracks}
    for f in glob.glob(os.path.join(pdir, "*.mp3")):
        if os.path.basename(f)[:-4] not in wanted:
            os.remove(f)

    failed_path = os.path.join(pdir, "failed.json")
    try:
        with open(failed_path) as f:
            failed = json.load(f)
    except (OSError, ValueError):
        failed = {}
    now = time.time()
    missing = [
        t for t in tracks
        if not os.path.exists(os.path.join(pdir, t["id"] + ".mp3"))
        and now - failed.get(t["id"], 0) > RETRY_FAILED_AFTER
    ]
    if not missing:
        log.info("%s: up to date (%d songs)", album, len(tracks))
        return 0
    copied = 0

    by_id = {t["id"]: t for t in tracks}
    done = []

    # A song another playlist already downloaded is copied, not fetched again
    # (sorted playlists made from liked songs share most of theirs).
    for t in list(missing):
        other = next(iter(glob.glob(os.path.join(config.CACHE_DIR, "*", t["id"] + ".mp3"))), None)
        if not other:
            continue
        tmp = os.path.join(work, t["id"] + ".mp3")
        shutil.copyfile(other, tmp)
        tag_mp3(tmp, t.get("title") or t["id"], t.get("artist", ""), album)
        os.replace(tmp, os.path.join(pdir, t["id"] + ".mp3"))
        missing.remove(t)
        failed.pop(t["id"], None)
        copied += 1
    if not missing:
        _write_json(failed_path, failed)
        log.info("%s: %d songs copied from other playlists", album, copied)
        return copied

    def learn(info):
        """Fill in title and artist from YouTube for songs listed by ID only."""
        t = by_id.get(info.get("id"))
        if t is not None and not t.get("title") and info.get("title"):
            artist, song = names.split_artist_title(
                info["title"], info.get("artist") or info.get("channel") or info.get("uploader") or "")
            t["title"], t["artist"] = song or info["title"], artist

    def post_hook(filepath):
        vid = os.path.splitext(os.path.basename(filepath))[0]
        t = by_id.get(vid)
        if not t or not filepath.endswith(".mp3"):
            return
        if not t.get("title"):
            t["title"] = vid
        tag_mp3(filepath, t["title"], t["artist"], album)
        os.replace(filepath, os.path.join(pdir, vid + ".mp3"))
        done.append(vid)
        if progress:
            progress(f"{album}", len(done), len(missing), 0.0)

    def progress_hook(d):
        learn(d.get("info_dict") or {})
        if not progress or d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        frac = (d.get("downloaded_bytes") or 0) / total if total else 0.0
        t = by_id.get((d.get("info_dict") or {}).get("id"), {})
        song = f"{t.get('artist', '')} - {t.get('title', '')}".strip(" -")
        progress(f"{album}: {song}", len(done), len(missing), min(frac, 1.0))

    opts = _base_opts(cfg) | {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(work, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(cfg["bitrate_kbps"]),
        }],
        # CBR, 44.1 kHz, stereo.
        "postprocessor_args": {"extractaudio": ["-ar", "44100", "-ac", "2"]},
        "post_hooks": [post_hook],
        "progress_hooks": [progress_hook],
    }
    log.info("%s: downloading %d new songs", album, len(missing))
    if progress:
        progress(album, 0, len(missing), 0.0)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([video_url(t["id"]) for t in missing])

    for t in missing:
        if t["id"] not in done:
            failed[t["id"]] = now
            log.warning("%s: could not download %s (%s)", album, t["title"], t["id"])
    for vid in done:
        failed.pop(vid, None)
    _write_json(failed_path, failed)
    shutil.rmtree(work, ignore_errors=True)
    if imported:   # keep the titles learned from YouTube for the drive file names
        _write_json(os.path.join(pdir, "order.json"), {"title": yt_title, "tracks": tracks})
    log.info("%s: %d new songs", album, len(done) + copied)
    return len(done) + copied


def remove_orphans(cfg):
    """Delete cache folders of playlists that were removed from the config."""
    keep = {p["id"] for p in cfg["playlists"]}
    if not os.path.isdir(config.CACHE_DIR):
        return
    for d in os.listdir(config.CACHE_DIR):
        if d not in keep:
            shutil.rmtree(os.path.join(config.CACHE_DIR, d), ignore_errors=True)
