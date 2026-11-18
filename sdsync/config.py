"""Settings and playlist list, stored as one JSON file.

Edit it from the web page, or by hand while the service is stopped.
"""
import json
import os
import threading
import uuid

HOME = os.environ.get("SDSYNC_HOME", "/var/lib/sdsync")
CONFIG_PATH = os.environ.get("SDSYNC_CONFIG", os.path.join(HOME, "config.json"))
CACHE_DIR = os.path.join(HOME, "cache")
MOUNT_POINT = os.environ.get("SDSYNC_MOUNT", "/mnt/sdsync")  # one subfolder per drive

DEFAULTS = {
    "playlists": [],   # the download library; which drive folder each goes to is in "targets"
    # How often to check YouTube for new songs.
    "download_interval_hours": 6,
    # MP3 output. Constant bitrate, 44.1 kHz stereo is what the RNS-E plays most reliably.
    "bitrate_kbps": 192,
    "max_name_len": 60,            # characters, including the "001 " prefix and ".mp3"
    "free_space_margin_mb": 50,
    "cookies_file": "",            # optional Netscape cookies.txt if YouTube asks to "sign in"
    "auto_update_ytdlp": True,     # YouTube changes often; keep yt-dlp fresh once a day
    "screen_off_minutes": 5,       # monitor goes to standby after this long untouched (0 = never)
    "check_on_insert": True,       # plugging in a drive also checks YouTube (if last check > 1 h ago)
    "look": "cyber",               # "cyber" (neon hacker-movie screens) or "classic" (90s desktop)
    "background": "glmatrix",      # monitor background in the cyber look: glmatrix, city or none
}

# Each kind of drive the box writes. A drive is recognised by its FAT volume
# label; an unlabelled drive is only written after you pick its kind on the
# web page (which then sets the label). Each target has its own folders, and
# each folder takes songs from one or more playlists.
DEFAULT_TARGETS = [
    {
        "id": "sd",
        "name": "RNS-E SD card",
        "label": "RNSE",
        "number_folders": True,     # "01 Road Trip", "02 ..." in the order listed
        "max_files_per_folder": 250,
        "max_folders": 99,
        "overflow": "split",        # split: "Name (1)", "Name (2)"; truncate: drop the rest
        "folders": [],
    },
    {
        "id": "cdc",
        "name": "CD changer USB",
        "label": "CDCHANGER",
        "number_folders": False,    # folder names used exactly, e.g. CD01 ... CD06
        "max_files_per_folder": 99,
        "max_folders": 6,
        "overflow": "truncate",
        "folders": [],
    },
]

_lock = threading.Lock()


def _migrate(cfg, saved):
    """Configs from before drive targets existed: every playlist goes to the SD card."""
    if "targets" in saved:
        return
    import copy
    cfg["targets"] = copy.deepcopy(DEFAULT_TARGETS)
    sd = cfg["targets"][0]
    for key in ("max_files_per_folder", "max_folders"):
        if key in saved:
            sd[key] = saved[key]
    if saved.get("card_label"):
        sd["label"] = saved["card_label"][:11].upper()
    sd["folders"] = [{"name": p.get("name", ""), "playlists": [p["id"]]} for p in cfg["playlists"]]


def target(cfg, tid):
    return next((t for t in cfg["targets"] if t["id"] == tid), None)


def load():
    with _lock:
        import copy
        cfg = copy.deepcopy(DEFAULTS)
        saved = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
        cfg.update(saved)
        for p in cfg["playlists"]:
            p.setdefault("id", uuid.uuid4().hex[:8])
            p.setdefault("enabled", True)
            p.setdefault("name", "")
        _migrate(cfg, saved)
        for t in cfg["targets"]:
            d = next((d for d in DEFAULT_TARGETS if d["id"] == t.get("id")), DEFAULT_TARGETS[0])
            for k, v in d.items():
                t.setdefault(k, copy.deepcopy(v))
        return cfg


def save(cfg):
    with _lock:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, CONFIG_PATH)


def update(fn):
    """Load, let fn change the dict in place, save. Returns the new config."""
    cfg = load()
    fn(cfg)
    save(cfg)
    return cfg
