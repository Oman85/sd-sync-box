"""Look up song genres on MusicBrainz, for sorting liked songs into playlists.

Takeout lists artist and album for liked songs but no genre. MusicBrainz
(musicbrainz.org, free, no account) has genre tags on albums and artists.
For each song the album's top genre is used, else the artist's. Answers are
cached in genres.json, so a second run (or a newer Takeout) only asks about
new albums and artists. MusicBrainz allows about one request per second, so
the first run over ~1,700 songs takes a while (10 to 30 minutes).
"""
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

log = logging.getLogger("sdsync.genres")

API = "https://musicbrainz.org/ws/2/"
USER_AGENT = "sdsync-box/1.0 (home music box; https://musicbrainz.org/doc/MusicBrainz_API)"
CACHE = os.path.join(config.HOME, "genres.json")
RESULTS_DIR = os.path.join(config.HOME, "imports")
MIN_SCORE = 90          # how sure MusicBrainz must be that it found the right artist/album
NOT_GENRES = {"seen live", "favorites", "favourite", "british", "american", "uk", "usa"}


class MusicBrainz:
    def __init__(self, fetch=None, delay=1.1):
        self._fetch = fetch or self._http
        self.delay = delay
        self._last = 0.0
        self._genres = None

    def _http(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8")

    def get(self, path, **params):
        url = API + path + "?" + urllib.parse.urlencode(params)
        for attempt in range(4):
            wait = self._last + self.delay - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            try:
                return self._fetch(url)
            except urllib.error.HTTPError as e:
                if e.code not in (429, 503) or attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))   # rate limited: back off
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))

    def genre_names(self):
        """MusicBrainz's own genre list, so tags like 'seen live' are ignored."""
        if self._genres is None:
            try:
                txt = self.get("genre/all", fmt="txt")
                self._genres = {g.strip().lower() for g in txt.splitlines() if g.strip()}
            except Exception as e:
                log.warning("could not get the genre list (%s); using all tags", e)
                self._genres = set()
        return self._genres

    def _best(self, items, name_key="name"):
        for it in items:
            if int(it.get("score", 0)) < MIN_SCORE:
                break
            tags = self.top_tags(it.get("genres") or it.get("tags") or [])
            if tags:
                return tags
        return []

    def top_tags(self, tags):
        known = self.genre_names()
        good = [t for t in tags if t.get("name") and int(t.get("count", 0)) > 0
                and t["name"].lower() not in NOT_GENRES
                and (not known or t["name"].lower() in known)]
        good.sort(key=lambda t: -int(t.get("count", 0)))
        return [t["name"].lower() for t in good[:3]]

    def album(self, artist, album):
        q = f'releasegroup:"{_q(album)}" AND artist:"{_q(artist)}"'
        data = json.loads(self.get("release-group", query=q, fmt="json", limit=3))
        return self._best(data.get("release-groups", []))

    def artist(self, artist):
        data = json.loads(self.get("artist", query=f'artist:"{_q(artist)}"', fmt="json", limit=3))
        return self._best(data.get("artists", []))


def _q(s):
    """Lucene query escaping for a quoted phrase."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def pretty(tag):
    small = {"and", "of", "n", "the"}
    return " ".join(w if w in small and i else w[:1].upper() + w[1:] for i, w in enumerate(tag.split(" ")))


def lookup(tracks, mb=None, progress=None, stop=None):
    """{video id: genre ('' if unknown)} for songs with an artist."""
    mb = mb or MusicBrainz()
    cache = _load(CACHE, {})
    out = {}
    for n, t in enumerate(tracks, 1):
        if stop is not None and stop.is_set():
            break
        artist = (t.get("main_artist") or t.get("artist", "").split(", ")[0]).strip()
        album = (t.get("album") or "").strip()
        tags = []
        try:
            if artist and album:
                key = f"r:{artist.lower()}|{album.lower()}"
                if key not in cache:
                    cache[key] = mb.album(artist, album)
                tags = cache[key]
            if artist and not tags:
                key = f"a:{artist.lower()}"
                if key not in cache:
                    cache[key] = mb.artist(artist)
                tags = cache[key]
        except Exception as e:  # network trouble: leave this song unknown, try again next run
            log.warning("genre lookup failed for %s: %s", artist, e)
        out[t["id"]] = pretty(tags[0]) if tags else ""
        if n % 20 == 0:
            _save(CACHE, cache)
        if progress:
            progress(n, len(tracks))
    _save(CACHE, cache)
    return out


# ---- background job, one at a time --------------------------------------

def results_path(pid):
    return os.path.join(RESULTS_DIR, f"genres-{pid}.json")


def load_results(pid):
    return _load(results_path(pid), None)


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.pid = None
        self.done = 0
        self.total = 0
        self.error = ""
        self.thread = None
        self.stop = threading.Event()

    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, pid, tracks, mb=None):
        with self.lock:
            if self.running():
                return False
            self.pid, self.done, self.total, self.error = pid, 0, len(tracks), ""
            self.stop.clear()

            def run():
                def prog(d, tot):
                    self.done = d
                try:
                    res = lookup(tracks, mb, prog, self.stop)
                    if not self.stop.is_set():
                        _save(results_path(pid), res)
                except Exception as e:
                    self.error = str(e)
                    log.error("genre lookup stopped: %s", e)

            self.thread = threading.Thread(target=run, daemon=True, name="genres")
            self.thread.start()
            return True


JOB = Job()


def summary(results, tracks, sorted_ids=(), min_songs=10):
    """[(genre, [video ids])] for songs not yet sorted, biggest first.

    Genres with fewer than min_songs songs are merged into "Other genres";
    songs MusicBrainz didn't know go to "Unknown genre".
    """
    groups, small, unknown = {}, [], []
    for t in tracks:
        if t["id"] in sorted_ids:
            continue
        g = (results or {}).get(t["id"], "")
        if g:
            groups.setdefault(g, []).append(t["id"])
        else:
            unknown.append(t["id"])
    out = []
    for g, ids in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(ids) >= min_songs:
            out.append((g, ids))
        else:
            small += ids
    if small:
        out.append(("Other genres", small))
    if unknown:
        out.append(("Unknown genre", unknown))
    return out
