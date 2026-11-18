"""A stand-in for mpv's JSON IPC, for tests and demos without a sound card."""
import json
import os
import socket
import sys
import threading
import time

sock_path = next(a.split("=", 1)[1] for a in sys.argv if a.startswith("--input-ipc-server="))
state = {"playlist": [], "pos": -1, "pause": False, "volume": 70.0, "t0": time.time(), "time": 0.0}


def handle(cmd):
    name, args = cmd[0], cmd[1:]
    if name == "get_property":
        p = args[0]
        if p == "playlist-pos":
            return state["pos"]
        if p == "pause":
            return state["pause"]
        if p == "volume":
            return state["volume"]
        if p == "time-pos":
            return state["time"] + (0 if state["pause"] else time.time() - state["t0"])
        if p == "duration":
            return 200.0
        return None
    if name == "set_property":
        p, v = args
        if p == "playlist-pos":
            state["pos"] = v
        elif p == "pause":
            state["pause"] = v
        elif p == "volume":
            state["volume"] = v
        return None
    if name == "loadfile":
        state["playlist"].append(args[0])
        if state["pos"] < 0:
            state["pos"] = 0
        return None
    if name == "playlist-clear":
        state["playlist"] = []
        return None
    if name == "stop":
        state["playlist"], state["pos"] = [], -1
        return None
    if name == "cycle":
        state["pause"] = not state["pause"]
        return None
    if name == "playlist-next":
        state["pos"] = min(len(state["playlist"]) - 1, state["pos"] + 1)
        return None
    if name == "playlist-prev":
        state["pos"] = max(0, state["pos"] - 1)
        return None
    if name == "seek":
        state["time"], state["t0"] = float(args[0]), time.time()
        return None
    raise ValueError(name)


def client(c):
    buf = b""
    while True:
        d = c.recv(65536)
        if not d:
            return
        buf += d
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            msg = json.loads(line)
            try:
                out = {"data": handle(msg["command"]), "error": "success"}
            except Exception as e:  # noqa: BLE001
                out = {"error": str(e)}
            out["request_id"] = msg.get("request_id")
            c.sendall((json.dumps(out) + "\n").encode())


if os.path.exists(sock_path):
    os.remove(sock_path)
srv = socket.socket(socket.AF_UNIX)
srv.bind(sock_path)
srv.listen(8)
while True:
    conn, _ = srv.accept()
    threading.Thread(target=client, args=(conn,), daemon=True).start()
