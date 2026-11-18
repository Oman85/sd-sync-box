"""Split a big imported list (liked songs) into smaller playlists for the drives.

A sorted playlist is an imported playlist with "parent" set to the list its
songs came from. Its songs are a fixed list like any import, so it downloads
and goes into drive folders like every other playlist (songs already
downloaded for the parent are copied, not fetched again).
"""
import uuid

from . import downloader, takeout


def source_tracks(pid):
    """The imported list, with titles learned from YouTube filled in."""
    known = {t["id"]: t for t in downloader.read_order(pid)["tracks"]}
    out = []
    for t in takeout.load_tracks(pid):
        k = known.get(t["id"])
        if k and not t.get("title"):
            t = dict(t, title=k.get("title", ""), artist=k.get("artist", ""))
        out.append(t)
    return out


def children(cfg, pid):
    return [p for p in cfg["playlists"] if p.get("parent") == pid]


def membership(cfg, pid):
    """{video id: [names of the sorted playlists it is in]}"""
    out = {}
    for c in children(cfg, pid):
        for t in takeout.load_tracks(c["id"]):
            out.setdefault(t["id"], []).append(c["name"])
    return out


def _new_child(cfg, pid, name, target, next_cd_name):
    new = {"id": uuid.uuid4().hex[:8], "url": "", "name": name[:40], "source": "takeout",
           "parent": pid, "enabled": True}
    cfg["playlists"].append(new)
    if target is not None:
        folder = "" if target.get("number_folders") else next_cd_name(target)
        target["folders"].append({"name": folder, "playlists": [new["id"]]})
    return new


def add(cfg, pid, vids, dest=None, new_name="", target=None, next_cd_name=None):
    """Put songs (in the source's order) into a sorted playlist. Returns its id or None."""
    if dest:
        d = next((p for p in children(cfg, pid) if p["id"] == dest), None)
    else:
        name = new_name.strip()
        if not name:
            return None
        d = next((p for p in children(cfg, pid) if p["name"] == name[:40]), None) \
            or _new_child(cfg, pid, name, target, next_cd_name)
    if d is None:
        return None
    have = takeout.load_tracks(d["id"])
    ids = {t["id"] for t in have}
    want = set(vids)
    have += [t for t in source_tracks(pid) if t["id"] in want and t["id"] not in ids]
    takeout.save_tracks(d["id"], have)
    return d["id"]


def remove(cfg, pid, dest, vids):
    d = next((p for p in children(cfg, pid) if p["id"] == dest), None)
    if d is None:
        return
    drop = set(vids)
    takeout.save_tracks(d["id"], [t for t in takeout.load_tracks(d["id"]) if t["id"] not in drop])


def _artist(t):
    return (t.get("main_artist") or t.get("artist", "").split(", ")[0]).strip()


def artist_groups(tracks, min_songs):
    """{artist: [video ids]} for artists with at least min_songs songs, biggest first."""
    groups = {}
    for t in tracks:
        a = _artist(t)
        if a:
            groups.setdefault(a, []).append(t["id"])
    big = [(a, ids) for a, ids in groups.items() if len(ids) >= min_songs]
    big.sort(key=lambda x: (-len(x[1]), x[0].lower()))
    return dict(big)


def group_by_artist(cfg, pid, min_songs, target=None, next_cd_name=None, only_unsorted=True):
    """One sorted playlist per artist with enough songs. Returns how many playlists got songs."""
    tracks = source_tracks(pid)
    if only_unsorted:
        sorted_ids = membership(cfg, pid)
        tracks = [t for t in tracks if t["id"] not in sorted_ids]
    groups = artist_groups(tracks, max(1, min_songs))
    for artist, ids in groups.items():
        add(cfg, pid, ids, new_name=artist, target=target, next_cd_name=next_cd_name)
    return len(groups)
