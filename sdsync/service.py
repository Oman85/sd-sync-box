"""The always-on part: download on a schedule, write every drive that is plugged in."""
import collections
import glob
import shutil
import logging
import os
import subprocess
import sys
import threading
import time

from . import card, cardsync, config, display, downloader, player

log = logging.getLogger("sdsync")


class Status:
    """Everything the web page and the screen show. Read with get()."""

    def __init__(self):
        self._lock = threading.Lock()
        self.download = {"state": "idle", "text": "Idle", "done": 0, "total": 0,
                         "song": 0.0, "playlist_no": 0, "playlists": 0, "last": None}
        self.devices = {}
        self.library = {"songs": 0, "gb": 0.0, "free_gb": 0.0, "health": "", "checked": None}
        self.display_on = True
        self.log = collections.deque(maxlen=300)

    def set_download(self, **kw):
        with self._lock:
            self.download.update(kw)

    def set_device(self, key, **kw):
        with self._lock:
            self.devices.setdefault(key, {"key": key}).update(kw)

    def drop_device(self, key):
        with self._lock:
            self.devices.pop(key, None)

    def get(self):
        with self._lock:
            return {
                "download": dict(self.download),
                "devices": [dict(d) for d in self.devices.values()],
                "library": dict(self.library),
                "display": "on" if self.display_on else "off",
                "log": list(self.log)[-60:],
                "time": time.strftime("%H:%M:%S"),
            }


class RingHandler(logging.Handler):
    def __init__(self, status):
        super().__init__()
        self.status = status

    def emit(self, record):
        self.status.log.append(time.strftime("%d %b %H:%M ") + record.getMessage()[:240])


class Led:
    """Pi activity LED (no-op on a PC): blinks while writing, steady on when done."""
    PATHS = ["/sys/class/leds/ACT", "/sys/class/leds/led0"]

    def __init__(self):
        self.path = next((p for p in self.PATHS if os.path.isdir(p)), None)

    def _w(self, name, value):
        if not self.path:
            return
        try:
            with open(f"{self.path}/{name}", "w") as f:
                f.write(value)
        except OSError:
            pass

    def busy(self):
        self._w("trigger", "timer")

    def done(self):
        self._w("trigger", "none")
        self._w("brightness", "1")

    def idle(self):
        self._w("trigger", "mmc0")


def target_for(cfg, info):
    label = (info.get("label") or "").strip().upper()
    if not label:
        return None
    return next((t for t in cfg["targets"] if t["label"].upper() == label), None)


class Service:
    def __init__(self):
        self.status = Status()
        self.led = Led()
        self.download_now = threading.Event()
        self.card_now = threading.Event()
        self.rewrite_next = set()       # target ids to rewrite from scratch on next write
        self.cache_gen = 0
        self._last_update_check = 0
        self._busy = set()              # device keys being written
        self._synced = {}               # device key -> cache_gen it was last written at
        self._lock = threading.Lock()
        self.display = display.Display()
        self.player = player.Player()
        self._last_health = 0
        self._last_download_run = 0

    # ---- cache and health ---------------------------------------------
    def update_library_stats(self):
        songs, size = 0, 0
        for root, _dirs, files in os.walk(config.CACHE_DIR):
            if os.path.basename(root) == "work":
                continue
            for f in files:
                if f.endswith(".mp3"):
                    songs += 1
                    try:
                        size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        os.makedirs(config.HOME, exist_ok=True)
        free = shutil.disk_usage(config.HOME).free
        self.status.library.update(songs=songs, gb=round(size / 1e9, 2), free_gb=round(free / 1e9, 1))
        return free

    def health_check(self):
        """Daily: find broken MP3s in the cache (they get downloaded again), tidy, check disk space."""
        from mutagen.mp3 import MP3
        broken = 0
        for path in glob.glob(os.path.join(config.CACHE_DIR, "*", "*.mp3")):
            try:
                if MP3(path).info.length < 1:
                    raise ValueError("no audio")
            except Exception:
                os.remove(path)
                broken += 1
        for work in glob.glob(os.path.join(config.CACHE_DIR, "*", "work")):
            shutil.rmtree(work, ignore_errors=True)
        free = self.update_library_stats()
        notes = []
        if broken:
            notes.append(f"{broken} broken songs removed, they will download again")
        if free < 2e9:
            notes.append(f"low disk space: {free / 1e9:.1f} GB free")
            log.warning("low disk space on the box: %.1f GB free", free / 1e9)
        text = "; ".join(notes) or "all songs OK"
        log.info("health check: %s", text)
        self.status.library.update(health=text, checked=time.strftime("%d %b %H:%M"))
        self._last_health = time.time()

    # ---- downloads ------------------------------------------------------
    def _maybe_update_ytdlp(self, cfg):
        if not cfg.get("auto_update_ytdlp") or time.time() - self._last_update_check < 86400:
            return
        self._last_update_check = time.time()
        log.info("checking for a yt-dlp update")
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp[default,deno]"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and "Successfully installed" in (r.stdout + r.stderr):
            if self._busy:
                log.info("yt-dlp updated; will restart after the drive write")
                return
            log.info("yt-dlp updated, restarting to load it")
            os._exit(3)  # systemd restarts the service

    def download_loop(self):
        while True:
            cfg = config.load()
            self._maybe_update_ytdlp(cfg)
            downloader.remove_orphans(cfg)
            if time.time() - self._last_health > 86400:
                try:
                    self.health_check()
                except Exception as e:
                    log.error("health check failed: %s", e)
            self._last_download_run = time.time()
            new = 0
            pls = [p for p in cfg["playlists"] if p.get("enabled", True)]
            for n, pl in enumerate(pls, 1):
                label = pl.get("name") or downloader.read_order(pl["id"]).get("title") or pl["url"]
                self.status.set_download(state="busy", text=f"Checking {label}", done=0, total=0,
                                         song=0.0, playlist_no=n, playlists=len(pls))

                def progress(text, done, total, song):
                    self.status.set_download(text=text, done=done, total=total, song=song)

                try:
                    added = downloader.sync_playlist(pl, cfg, progress)
                except Exception as e:  # keep going with the other playlists
                    log.error("%s: %s", label, e)
                    continue
                new += added
                if added:
                    self.cache_gen += 1   # lets a drive that is plugged in pick up new songs
            self.status.set_download(state="idle", text="Idle", done=0, total=0, song=0.0,
                                     playlist_no=0, playlists=len(pls),
                                     last=time.strftime("%d %b %H:%M"))
            log.info("download run finished, %d new songs", new)
            self.update_library_stats()
            self.download_now.wait(float(cfg["download_interval_hours"]) * 3600)
            self.download_now.clear()

    # ---- drives ---------------------------------------------------------
    def card_loop(self):
        known = set()
        while True:
            triggered = self.card_now.wait(3)
            self.card_now.clear()
            cfg = config.load()
            present = {}
            for info in card.find_cards():
                key = info["uuid"] or info["dev"]
                present[key] = info
            for key in known - set(present):
                if key not in self._busy:
                    log.info("drive removed")
                    self.status.drop_device(key)
                    self._synced.pop(key, None)
            if not present:
                self.led.idle()
            if set(present) - known:
                self.display.activity("drive plugged in")
                # fresh songs before a trip: check YouTube if the last check is over an hour old
                if cfg.get("check_on_insert", True) and time.time() - self._last_download_run > 3600:
                    self.download_now.set()
            elif known - set(present):
                self.display.activity("drive removed")
            known = set(present)
            self.display.tick(float(cfg.get("screen_off_minutes", 5)), keep_awake=bool(self._busy))
            self.status.display_on = self.display.on

            for key, info in present.items():
                if key in self._busy:
                    continue
                base = {"dev": info["dev"], "model": info["model"], "label": info["label"],
                        "size_gb": round(card.capacity_gb(info["dev"]), 1)}
                if key not in self._synced:
                    self._synced[key] = -1
                    log.info("drive found: %s %s %s %.0f GB", info["model"], info["dev"],
                             info["fstype"] or "unformatted", base["size_gb"])
                if info["fstype"] != "vfat":
                    self.status.set_device(key, **base, target="", target_name="", state="error",
                                           text=f"{info['fstype'] or 'Not formatted'}: needs FAT32",
                                           done=0, total=0)
                    continue
                tgt = target_for(cfg, info)
                if not tgt:
                    self.status.set_device(key, **base, target="", target_name="", state="unassigned",
                                           text="New drive: tell the box what it is",
                                           done=0, total=0)
                    continue
                if self._synced[key] == self.cache_gen and not triggered:
                    continue
                self._synced[key] = self.cache_gen
                self._busy.add(key)
                self.status.set_device(key, **base, target=tgt["id"], target_name=tgt["name"],
                                       state="busy", text="Starting", done=0, total=0)
                threading.Thread(target=self._write, args=(key, info, cfg, tgt), daemon=True).start()

    def _write(self, key, info, cfg, tgt):
        self.led.busy()
        rewrite = tgt["id"] in self.rewrite_next
        self.rewrite_next.discard(tgt["id"])

        def progress(text, done, total):
            self.status.set_device(key, text=text, done=done, total=total)

        try:
            root = card.mount(info["dev"])
            try:
                summary = cardsync.apply(root, cfg, tgt, progress, rewrite=rewrite)
            finally:
                card.unmount(info["dev"])
        except Exception as e:
            log.warning("%s write failed: %s", tgt["name"], e)
            self.status.set_device(key, state="error", text=f"Write failed: {e}")
            self.led.idle()
        else:
            log.info("%s done: %s", tgt["name"], summary)
            self.display.activity("drive finished")
            self.status.set_device(key, state="done", text=f"Done, safe to remove. {summary}",
                                   finished=time.strftime("%H:%M"))
            self.led.done()
        finally:
            self._busy.discard(key)

    def assign(self, dev, tid):
        """Label an unrecognised drive as one of the targets, then write it."""
        cfg = config.load()
        tgt = config.target(cfg, tid)
        info = next((c for c in card.find_cards() if c["dev"] == dev), None)
        if not tgt or not info or info["fstype"] != "vfat":
            return False
        card.set_label(dev, tgt["label"])
        log.info("drive %s is now '%s' (label %s)", dev, tgt["name"], tgt["label"])
        self.card_now.set()
        return True

    def run(self, host="0.0.0.0", port=80):
        from . import web
        logging.getLogger().addHandler(RingHandler(self.status))
        try:
            self.update_library_stats()
        except OSError:
            pass
        threading.Thread(target=self.download_loop, daemon=True, name="download").start()
        threading.Thread(target=self.card_loop, daemon=True, name="card").start()
        web.serve(self, host, port)
