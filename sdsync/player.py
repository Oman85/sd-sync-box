"""Music player: plays the cached songs through the box's own audio output.

Uses mpv in the background (no window), controlled over its JSON IPC socket.
mpv is started on the first play, so a box without speakers never runs it.
"""
import json
import logging
import os
import random
import shutil
import socket
import subprocess
import threading
import time

from . import downloader

log = logging.getLogger("sdsync.player")

SOCKET = os.environ.get("SDSYNC_MPV_SOCKET", "/run/sdsync-mpv.sock")


class PlayerError(Exception):
    pass


class Player:
    def __init__(self, sock=SOCKET):
        self.sock = sock
        self.proc = None
        self._lock = threading.Lock()
        self._req = 0
        self.queue = []          # [{path, title, artist, playlist}]
        self.queue_name = ""
        self.shuffle = False
        self._cache = (0, None)

    # ---- mpv process and IPC ------------------------------------------
    def _start(self):
        if self.proc and self.proc.poll() is None:
            return
        exe = shutil.which("mpv")
        if not exe:
            raise PlayerError("mpv is not installed (sudo apt install mpv)")
        try:
            os.remove(self.sock)
        except OSError:
            pass
        self.proc = subprocess.Popen(
            [exe, "--idle=yes", "--no-video", "--no-terminal", "--audio-display=no",
             "--gapless-audio=yes", "--volume=70", f"--input-ipc-server={self.sock}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if os.path.exists(self.sock):
                return
            time.sleep(0.1)
        raise PlayerError("mpv did not start (is there a sound card?)")

    def _ipc(self, *command, start=False):
        if start:
            self._start()
        if not os.path.exists(self.sock):
            raise PlayerError("not playing")
        with self._lock:
            self._req += 1
            rid = self._req
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            try:
                s.connect(self.sock)
                s.sendall((json.dumps({"command": list(command), "request_id": rid}) + "\n").encode())
                buf = b""
                while True:
                    chunk = s.recv(65536)
                    if not chunk:
                        raise PlayerError("mpv closed the connection")
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        msg = json.loads(line or b"{}")
                        if msg.get("request_id") == rid:
                            if msg.get("error") not in (None, "success"):
                                raise PlayerError(msg["error"])
                            return msg.get("data")
            except (OSError, ValueError) as e:
                raise PlayerError(str(e)) from e
            finally:
                s.close()

    def _get(self, prop, default=None):
        try:
            return self._ipc("get_property", prop)
        except PlayerError:
            return default

    # ---- queue --------------------------------------------------------
    @staticmethod
    def tracks_for(cfg, pid):
        pl = next((p for p in cfg["playlists"] if p["id"] == pid), None)
        if not pl:
            return []
        order = downloader.read_order(pid)
        name = pl.get("name") or order.get("title") or "Playlist"
        pdir = downloader.playlist_dir(pid)
        out = []
        for t in order["tracks"]:
            path = os.path.join(pdir, t["id"] + ".mp3")
            if os.path.exists(path):
                out.append({"path": path, "title": t["title"], "artist": t["artist"], "playlist": name})
        return out

    def play(self, tracks, name, start=0, shuffle=None):
        if not tracks:
            raise PlayerError("nothing downloaded in that playlist yet")
        if shuffle is not None:
            self.shuffle = shuffle
        tracks = list(tracks)
        if self.shuffle:
            first = tracks.pop(start) if 0 <= start < len(tracks) else None
            random.shuffle(tracks)
            if first:
                tracks.insert(0, first)
            start = 0
        self.queue, self.queue_name = tracks, name
        self._ipc("playlist-clear", start=True)
        self._ipc("stop")
        for i, t in enumerate(tracks):
            self._ipc("loadfile", t["path"], "append-play" if i == 0 else "append")
        if start:
            self._ipc("set_property", "playlist-pos", start)
        self._ipc("set_property", "pause", False)
        self._cache = (0, None)
        log.info("playing %s (%d songs)", name, len(tracks))

    def play_playlist(self, cfg, pid, start=0, shuffle=None):
        tracks = self.tracks_for(cfg, pid)
        name = tracks[0]["playlist"] if tracks else ""
        self.play(tracks, name, start, shuffle)

    def play_all(self, cfg):
        tracks = []
        for p in cfg["playlists"]:
            if p.get("enabled", True):
                tracks += self.tracks_for(cfg, p["id"])
        self.play(tracks, "Everything", 0, shuffle=True)

    # ---- controls -----------------------------------------------------
    def command(self, cmd, value=None):
        if cmd == "toggle":
            self._ipc("cycle", "pause")
        elif cmd == "pause":
            self._ipc("set_property", "pause", True)
        elif cmd == "resume":
            self._ipc("set_property", "pause", False)
        elif cmd == "next":
            self._ipc("playlist-next", "force")
        elif cmd == "prev":
            if (self._get("time-pos") or 0) > 5:
                self._ipc("seek", 0, "absolute")
            else:
                self._ipc("playlist-prev", "force")
        elif cmd == "seek":
            self._ipc("seek", float(value), "absolute")
        elif cmd == "volume":
            self._ipc("set_property", "volume", max(0, min(100, float(value))))
        elif cmd == "jump":
            self._ipc("set_property", "playlist-pos", int(value))
        elif cmd == "stop":
            self._ipc("stop")
            self.queue, self.queue_name = [], ""
        else:
            raise PlayerError(f"unknown command {cmd}")
        self._cache = (0, None)

    def state(self):
        """Now-playing info for the pages. Cached for half a second."""
        now = time.time()
        if now - self._cache[0] < 0.5 and self._cache[1] is not None:
            return self._cache[1]
        st = {"playing": False, "paused": False, "title": "", "artist": "", "playlist": self.queue_name,
              "pos": 0, "duration": 0, "volume": 70, "index": -1, "count": len(self.queue),
              "shuffle": self.shuffle, "up_next": [], "available": bool(shutil.which("mpv"))}
        if self.proc and self.proc.poll() is None and os.path.exists(self.sock):
            idx = self._get("playlist-pos", -1)
            if isinstance(idx, int) and 0 <= idx < len(self.queue):
                t = self.queue[idx]
                st.update(playing=True, title=t["title"], artist=t["artist"], index=idx,
                          paused=bool(self._get("pause", False)),
                          pos=round(self._get("time-pos", 0) or 0, 1),
                          duration=round(self._get("duration", 0) or 0, 1),
                          up_next=[{"title": q["title"], "artist": q["artist"], "index": idx + 1 + k}
                                   for k, q in enumerate(self.queue[idx + 1: idx + 6])])
            st["volume"] = round(self._get("volume", 70) or 0)
        self._cache = (now, st)
        return st

    def shutdown(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
