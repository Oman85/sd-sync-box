"""Read playlists out of a Google Takeout export of YouTube / YouTube Music.

Private lists (liked songs, private playlists) can't be read by the box from
YouTube without signing in, but Takeout has them all as CSV files:

    Takeout/YouTube and YouTube Music/playlists/<name>-videos.csv
    Takeout/YouTube and YouTube Music/music (library and uploads)/music library songs.csv

Folder and file names are translated into the account's language (for
example "playlisty/<name>-videa.csv" in Czech), so files are recognised by
their content: the first column of every one of these CSVs is the video ID.

Imported playlists are stored on the box as a fixed list of video IDs
(imports/<playlist id>.json) and download like any other playlist. Importing
a newer Takeout replaces the list of a playlist with the same name.
"""
import csv
import io
import json
import os
import re
import zipfile

from . import config

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
MAX_UPLOAD = 200 * 1024 * 1024     # a music-only Takeout is a few MB; refuse anything silly
LIBRARY_NAME = "Liked & library songs"

IMPORT_DIR = os.path.join(config.HOME, "imports")
PENDING = os.path.join(IMPORT_DIR, "pending.json")


def _unescape(name):
    """Takeout writes non-ASCII characters in zip names as #U00e1."""
    return re.sub(r"#U([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), name)


def _rows(data):
    text = data.decode("utf-8-sig", errors="replace")
    return [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]


def _playlist_name(path):
    """'.../Road Trip-videos.csv' -> 'Road Trip' (the suffix is translated, so cut at the last '-')."""
    stem = os.path.basename(_unescape(path))
    stem = stem[:-4] if stem.lower().endswith(".csv") else stem
    if "-" in stem:
        stem = stem.rsplit("-", 1)[0]
    return stem.strip() or "Imported playlist"


def _is_library(header):
    h = [c.strip().lower() for c in header]
    return len(h) >= 3 and "song title" in h


def parse_csv(path, data):
    """One playlist from one CSV file, or None if it isn't a list of videos."""
    rows = _rows(data)
    # Older exports put a few lines about the playlist above the video list.
    start = next((i for i, r in enumerate(rows) if i and VIDEO_ID.match(r[0].strip())), None)
    if start is None:
        return None   # playlists.csv, subscriptions.csv: other things in the first column
    header, body = rows[start - 1], rows[start:]
    library = _is_library(header)
    if not library and len(header) > 3:
        return None   # e.g. the list of your own uploads, which has many columns per video
    tracks, seen = [], set()
    for r in body:
        vid = r[0].strip()
        if not VIDEO_ID.match(vid) or vid in seen:
            continue
        seen.add(vid)
        t = {"id": vid, "title": "", "artist": ""}
        if library:
            t["title"] = (r[1] if len(r) > 1 else "").strip()
            t["artist"] = ", ".join(a.strip() for a in r[3:6] if a.strip())
        tracks.append(t)
    if not tracks:
        return None
    return {"name": LIBRARY_NAME if library else _playlist_name(path), "library": library, "tracks": tracks}


def parse(filename, data):
    """[{name, library, tracks}] from a Takeout .zip or a single .csv, library first.

    Raises ValueError with a message for the user when nothing usable is found.
    """
    found = []
    if data[:4] == b"PK\x03\x04":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise ValueError("That zip file is damaged.")
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".csv") or info.file_size > 20 * 1024 * 1024:
                continue
            pl = parse_csv(info.filename, zf.read(info))
            if pl:
                found.append(pl)
    else:
        pl = parse_csv(filename or "Imported playlist.csv", data)
        if pl:
            found.append(pl)
    if not found:
        raise ValueError("No YouTube playlists found. Upload the Takeout .zip, or one playlist .csv from it.")
    # Two playlists with the same name: keep both, numbered.
    counts = {}
    for pl in found:
        n = counts.get(pl["name"], 0) + 1
        counts[pl["name"]] = n
        if n > 1:
            pl["name"] = f"{pl['name']} ({n})"
    found.sort(key=lambda p: (not p["library"], p["name"].lower()))
    return found


# ---- storage on the box ---------------------------------------------------

def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def save_pending(found):
    _write_json(PENDING, found)


def load_pending():
    try:
        with open(PENDING, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def clear_pending():
    try:
        os.remove(PENDING)
    except OSError:
        pass


def tracks_path(pid):
    return os.path.join(IMPORT_DIR, pid + ".json")


def save_tracks(pid, tracks):
    _write_json(tracks_path(pid), tracks)


def load_tracks(pid):
    try:
        with open(tracks_path(pid), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def delete_tracks(pid):
    try:
        os.remove(tracks_path(pid))
    except OSError:
        pass
