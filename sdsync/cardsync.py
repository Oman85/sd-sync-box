"""Lay out the cached songs on a mounted SD card or USB stick.

Each drive target (RNS-E SD card, CD changer USB) has its own list of
folders, and each folder takes songs from one or more playlists.

Example SD card layout (one folder level, which the RNS-E browses as "CD" folders):
    /01 Road Trip/001 Artist - Song.mp3
    /01 Road Trip/002 ...
    /02 Chill (1)/001 ...      playlists longer than max_files_per_folder are split
    /02 Chill (2)/251 ...
    /sdsync.json               what this box wrote, so it never touches your other files

Many older head units play files in the order they were written to the
card rather than by name. So songs are only ever appended to a folder;
if a playlist is reordered or a song disappears, that folder is rewritten
from scratch in the right order.
"""
import json
import logging
import os
import re
import shutil

from . import downloader, names

log = logging.getLogger("sdsync.card")

MANIFEST = "sdsync.json"
_OURS = re.compile(r"^\d{3,4} .*\.mp3$")


def folder_title(cfg, folder):
    """The folder's own name, or the name of its first playlist."""
    if folder.get("name"):
        return folder["name"]
    for pid in folder.get("playlists", []):
        pl = next((p for p in cfg["playlists"] if p["id"] == pid), None)
        if pl:
            return pl.get("name") or downloader.read_order(pid).get("title") or "Playlist"
    return "Playlist"


def build_plan(cfg, target):
    """[{folder, files: [{name, src, size}]}] for one drive target, in its folder order."""
    plan = []
    maxf = max(1, int(target["max_files_per_folder"]))
    maxlen = int(cfg["max_name_len"])
    by_id = {p["id"]: p for p in cfg["playlists"]}
    idx = 0
    for fi, folder in enumerate(target["folders"]):
        tracks = []
        for pid in folder.get("playlists", []):
            pl = by_id.get(pid)
            if not pl or not pl.get("enabled", True):
                continue
            pdir = downloader.playlist_dir(pid)
            tracks += [
                (pdir, t) for t in downloader.read_order(pid)["tracks"]
                if os.path.exists(os.path.join(pdir, t["id"] + ".mp3"))
            ]
        if not tracks:
            continue
        idx += 1
        title = folder_title(cfg, folder)
        if target.get("number_folders", True):
            base = f"{idx:02d} " + names.safe_name(title, maxlen - 11)
        else:
            base = names.safe_name(title, maxlen - 8)
        if target.get("overflow") == "truncate":
            tracks = tracks[:maxf]
        width = 3 if len(tracks) < 1000 else 4
        chunks = [tracks[i:i + maxf] for i in range(0, len(tracks), maxf)]
        for part, chunk in enumerate(chunks, 1):
            name = base + (f" ({part})" if len(chunks) > 1 else "")
            files = []
            for n, (pdir, t) in enumerate(chunk, (part - 1) * maxf + 1):
                src = os.path.join(pdir, t["id"] + ".mp3")
                files.append({
                    "name": names.track_filename(n, width, t["artist"], t["title"], maxlen),
                    "src": src,
                    "size": os.path.getsize(src),
                })
            _dedupe(files)
            plan.append({"folder": name, "files": files, "index": fi})
    return plan[: int(target["max_folders"])]


def _dedupe(files):
    seen = set()
    for f in files:
        name = f["name"]
        while name.lower() in seen:
            name = name[:-4] + "_.mp3"
        seen.add(name.lower())
        f["name"] = name


def read_manifest(root):
    try:
        with open(os.path.join(root, MANIFEST), encoding="utf-8") as f:
            return json.load(f).get("folders", {})
    except (OSError, ValueError):
        return {}


def write_manifest(root, folders):
    path = os.path.join(root, MANIFEST)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"written_by": "sdsync", "folders": folders}, f, indent=1)
        f.flush()
        os.fsync(f.fileno())


def fit_to_card(plan, root, manifest, margin_mb):
    """Trim the plan so it fits. Returns number of songs left out."""
    st = os.statvfs(root)
    cluster = st.f_bsize or 32768
    ours = 0
    for folder, files in manifest.items():
        for f in files:
            p = os.path.join(root, folder, f["name"])
            if os.path.exists(p):
                ours += os.path.getsize(p)
    budget = st.f_bavail * st.f_frsize + ours - margin_mb * 1024 * 1024
    used, skipped = 0, 0
    for entry in plan:
        keep = []
        for f in entry["files"]:
            need = -(-f["size"] // cluster) * cluster
            if used + need <= budget:
                used += need
                keep.append(f)
            else:
                skipped += 1
        entry["files"] = keep
    plan[:] = [e for e in plan if e["files"]]
    return skipped


def _folder_intact(root, folder, old):
    for f in old:
        p = os.path.join(root, folder, f["name"])
        if not os.path.exists(p) or os.path.getsize(p) != f["size"]:
            return False
    return True


def _wipe_folder(root, folder, old_names):
    """Remove our files from a folder; drop the folder if nothing else is in it."""
    d = os.path.join(root, folder)
    if not os.path.isdir(d):
        return
    others = [n for n in os.listdir(d) if n not in old_names and not _OURS.match(n)]
    if not others:
        shutil.rmtree(d)
        return
    for n in os.listdir(d):
        if n in old_names or _OURS.match(n):
            os.remove(os.path.join(d, n))


def apply(root, cfg, target, progress=None, rewrite=False):
    """Write the target's plan to the drive mounted at root. Returns a summary string.

    progress(text, done, total) is called after every song.
    """
    plan = build_plan(cfg, target)
    manifest = {} if rewrite else read_manifest(root)
    if rewrite:
        for folder, files in read_manifest(root).items():
            _wipe_folder(root, folder, {f["name"] for f in files})
    skipped = fit_to_card(plan, root, manifest, cfg["free_space_margin_mb"])

    planned = {e["folder"] for e in plan}
    for folder in list(manifest):
        if folder not in planned:
            log.info("removing folder %s", folder)
            _wipe_folder(root, folder, {f["name"] for f in manifest[folder]})
            del manifest[folder]
    write_manifest(root, manifest)

    total = sum(len(e["files"]) for e in plan)
    copied = done = 0
    if progress:
        progress("Starting", 0, total)
    for entry in plan:
        folder, files = entry["folder"], entry["files"]
        d = os.path.join(root, folder)
        old = manifest.get(folder, [])
        new_names = [f["name"] for f in files]
        old_names = [f["name"] for f in old]
        append_only = (
            old_names == new_names[: len(old_names)]
            and _folder_intact(root, folder, old)
        )
        if append_only:
            start = len(old)
            # Leftovers from an interrupted copy would sit before the new files.
            if os.path.isdir(d):
                stray = [n for n in os.listdir(d) if _OURS.match(n) and n not in old_names]
                if stray:
                    append_only, start = False, 0
        if not append_only:
            if old or os.path.isdir(d):
                log.info("rewriting folder %s in playlist order", folder)
            _wipe_folder(root, folder, set(old_names))
            start = 0
            manifest[folder] = []
            write_manifest(root, manifest)
        os.makedirs(d, exist_ok=True)
        done += start
        for f in files[start:]:
            shutil.copyfile(f["src"], os.path.join(d, f["name"]))
            copied += 1
            done += 1
            if progress:
                progress(f"Writing {folder}", done, total)
        manifest[folder] = [{"name": f["name"], "size": f["size"]} for f in files]
        write_manifest(root, manifest)

    msg = f"{total} songs in {len(plan)} folders, {copied} copied this time"
    if skipped:
        msg += f", {skipped} did not fit"
    return msg
