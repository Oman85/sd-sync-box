"""Turn the attached monitor off when nobody is using it, and back on.

The monitor view runs in the "cage" kiosk as the sdsync-screen user. Power is
switched with wlopm (Wayland output power management), which puts the monitor
into standby the same way a PC's screen saver does. If wlopm is missing or the
compositor doesn't support it, the page still blacks itself out, so the screen
at least goes dark, and a touch wakes it either way.
"""
import glob
import logging
import os
import pwd
import shutil
import subprocess
import threading
import time

log = logging.getLogger("sdsync.display")

SCREEN_USER = "sdsync-screen"


class Display:
    def __init__(self):
        self._lock = threading.Lock()
        self.on = True
        self.last_activity = time.time()
        self.hw = None   # True/False once we know if wlopm works

    def _wlopm(self, state):
        exe = shutil.which("wlopm")
        if not exe:
            return False
        try:
            pw = pwd.getpwnam(SCREEN_USER)
        except KeyError:
            return False
        run_dir = f"/run/user/{pw.pw_uid}"
        sockets = [os.path.basename(p) for p in glob.glob(os.path.join(run_dir, "wayland-*")) if not p.endswith(".lock")]
        if not sockets:
            return False
        env = {"XDG_RUNTIME_DIR": run_dir, "WAYLAND_DISPLAY": sockets[0], "PATH": "/usr/bin:/bin"}
        cmd = [exe, f"--{state}", "*"]
        if os.geteuid() == 0:
            cmd = ["runuser", "-u", SCREEN_USER, "--"] + cmd
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=10)
        return r.returncode == 0

    def set(self, on, reason=""):
        with self._lock:
            if on == self.on:
                return
            self.on = on
        try:
            ok = self._wlopm("on" if on else "off")
        except Exception as e:  # noqa: BLE001
            ok = False
            log.debug("wlopm failed: %s", e)
        if self.hw is None and not on:
            self.hw = ok
            if not ok:
                log.info("monitor power control not available; the screen will black out instead")
        log.info("monitor %s%s", "on" if on else "off", f" ({reason})" if reason else "")

    def activity(self, reason=""):
        """Something happened that a person would want to see: wake up."""
        self.last_activity = time.time()
        if not self.on:
            self.set(True, reason)

    def tick(self, idle_minutes, keep_awake):
        """Call every few seconds. Turns the monitor off after idle_minutes (0 = never)."""
        if keep_awake:
            self.last_activity = time.time()
            return
        if idle_minutes and self.on and time.time() - self.last_activity > idle_minutes * 60:
            self.set(False, f"idle {idle_minutes} min")
