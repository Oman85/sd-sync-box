"""Run with: python3 -m pytest tests  (no Pi, card or internet needed)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SDSYNC_HOME", str(tmp_path / "home"))
    for m in [m for m in sys.modules if m.startswith("sdsync")]:
        del sys.modules[m]
    from sdsync import cardsync, config, downloader
    card = tmp_path / "card"
    card.mkdir()

    def make_playlist(pid, name, ids):
        d = tmp_path / "home" / "cache" / pid
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.mp3"):
            f.unlink()
        tracks = []
        for i in ids:
            (d / f"{i}.mp3").write_bytes(b"x" * 1000)
            tracks.append({"id": i, "title": f"Song {i}", "artist": "Band"})
        (d / "order.json").write_text(json.dumps({"title": name, "tracks": tracks}))
        return {"id": pid, "url": "u", "name": name, "enabled": True}

    import copy
    cfg = copy.deepcopy(config.DEFAULTS)
    cfg["targets"] = copy.deepcopy(config.DEFAULT_TARGETS)
    return cardsync, cfg, card, make_playlist


def use(cfg, pls, target="sd"):
    """Put each playlist in its own folder on the target."""
    cfg["playlists"] = pls
    t = next(t for t in cfg["targets"] if t["id"] == target)
    t["folders"] = [{"name": "", "playlists": [p["id"]]} for p in pls]
    return t


def listing(card):
    return {d: sorted(os.listdir(card / d)) for d in sorted(os.listdir(card)) if (card / d).is_dir()}


def test_names():
    from sdsync import names
    assert names.split_artist_title("Mötley Crüe - Kickstart My Heart (Official Music Video)") == (
        "Motley Crue", "Kickstart My Heart")
    assert names.split_artist_title("Song Only [HD]", "Some Artist - Topic") == ("Some Artist", "Song Only")
    fn = names.track_filename(7, 3, "AC/DC", 'Who: "Made" Who?', 40)
    assert fn == "007 ACDC - Who Made Who.mp3"
    long = names.track_filename(1, 3, "A" * 80, "B" * 80, 60)
    assert len(long) <= 60 and long.endswith(".mp3")


def test_first_write_and_append(env):
    cardsync, cfg, card, mk = env
    t = use(cfg, [mk("p1", "Road Trip", ["a", "b"])])
    cardsync.apply(str(card), cfg, t)
    assert listing(card) == {"01 Road Trip": ["001 Band - Song a.mp3", "002 Band - Song b.mp3"]}
    first = os.stat(card / "01 Road Trip" / "001 Band - Song a.mp3").st_ino

    t = use(cfg, [mk("p1", "Road Trip", ["a", "b", "c"])])
    msg = cardsync.apply(str(card), cfg, t)
    assert "1 copied" in msg
    assert os.stat(card / "01 Road Trip" / "001 Band - Song a.mp3").st_ino == first  # untouched


def test_reorder_rewrites_folder(env):
    cardsync, cfg, card, mk = env
    t = use(cfg, [mk("p1", "Mix", ["a", "b"])])
    cardsync.apply(str(card), cfg, t)
    t = use(cfg, [mk("p1", "Mix", ["z", "a", "b"])])
    msg = cardsync.apply(str(card), cfg, t)
    assert "3 copied" in msg
    assert listing(card)["01 Mix"] == ["001 Band - Song z.mp3", "002 Band - Song a.mp3", "003 Band - Song b.mp3"]


def test_split_remove_and_leave_other_files(env):
    cardsync, cfg, card, mk = env
    (card / "My own stuff").mkdir()
    (card / "My own stuff" / "keep.mp3").write_bytes(b"k")
    t = use(cfg, [mk("p1", "Long", ["a", "b", "c"]), mk("p2", "Short", ["d"])])
    t["max_files_per_folder"] = 2
    cardsync.apply(str(card), cfg, t)
    l = listing(card)
    assert l["01 Long (1)"] == ["001 Band - Song a.mp3", "002 Band - Song b.mp3"]
    assert l["01 Long (2)"] == ["003 Band - Song c.mp3"]
    assert l["02 Short"] == ["001 Band - Song d.mp3"]

    t["folders"] = t["folders"][:1]
    cardsync.apply(str(card), cfg, t)
    l = listing(card)
    assert "02 Short" not in l
    assert l["My own stuff"] == ["keep.mp3"]


def test_interrupted_copy_is_repaired(env):
    cardsync, cfg, card, mk = env
    t = use(cfg, [mk("p1", "Mix", ["a", "b"])])
    cardsync.apply(str(card), cfg, t)
    with open(card / "01 Mix" / "002 Band - Song b.mp3", "wb") as f:
        f.write(b"half")
    msg = cardsync.apply(str(card), cfg, t)
    assert "2 copied" in msg
    assert os.path.getsize(card / "01 Mix" / "002 Band - Song b.mp3") == 1000


def test_full_card_skips(env, monkeypatch):
    cardsync, cfg, card, mk = env
    t = use(cfg, [mk("p1", "Mix", ["a", "b", "c"])])

    class St:
        f_bsize = 1024
        f_frsize = 1
        f_bavail = 2048 + cfg["free_space_margin_mb"] * 1024 * 1024

    monkeypatch.setattr(cardsync.os, "statvfs", lambda p: St)
    msg = cardsync.apply(str(card), cfg, t)
    assert "1 did not fit" in msg
    assert len(listing(card)["01 Mix"]) == 2


def test_card_detection_skips_system_disk(tmp_path, monkeypatch):
    """On a PC the system drive is often sda too; only USB disks that aren't the system disk count."""
    from sdsync import card
    sysb = tmp_path / "fakesysblock"
    for disk, bus in (("sda", "ata1"), ("sdb", "usb1"), ("sdc", "usb2")):
        d = tmp_path / "devices" / bus / disk
        (d / (disk + "1")).mkdir(parents=True)
        (d / "size").write_text("1000" if disk != "sdc" else "0")
        sysb.mkdir(parents=True, exist_ok=True)
        os.symlink(d, sysb / disk)
    real_glob = card.glob.glob
    monkeypatch.setattr(card.glob, "glob", lambda p: real_glob(p.replace("/sys/block", str(sysb))))
    monkeypatch.setattr(card, "_blkid", lambda dev, f: {"TYPE": "vfat"}.get(f, ""))

    monkeypatch.setattr(card, "system_disks", lambda: {"sda"})
    monkeypatch.setattr(card, "_model", lambda d: "Reader")
    assert card.find_card()["dev"] == "/dev/sdb1"   # sda is SATA, sdc reader is empty

    monkeypatch.setattr(card, "system_disks", lambda: {"sdb"})  # e.g. booted from a USB stick
    assert card.find_card() is None


def test_cd_changer_folders_merge_and_truncate(env):
    cardsync, cfg, card, mk = env
    a, b, c = mk("p1", "Rock", ["a", "b"]), mk("p2", "Pop", ["c"]), mk("p3", "Big", [str(i) for i in range(120)])
    cfg["playlists"] = [a, b, c]
    t = next(t for t in cfg["targets"] if t["id"] == "cdc")
    t["folders"] = [{"name": "CD01", "playlists": ["p1", "p2"]}, {"name": "CD02", "playlists": ["p3"]}]
    msg = cardsync.apply(str(card), cfg, t)
    l = listing(card)
    assert l["CD01"] == ["001 Band - Song a.mp3", "002 Band - Song b.mp3", "003 Band - Song c.mp3"]
    assert len(l["CD02"]) == 99           # changer limit, rest left out
    assert "CD02 (2)" not in l


def test_old_config_is_migrated(tmp_path, monkeypatch):
    monkeypatch.setenv("SDSYNC_HOME", str(tmp_path))
    for m in [m for m in sys.modules if m.startswith("sdsync")]:
        del sys.modules[m]
    (tmp_path / "config.json").write_text(json.dumps({
        "playlists": [{"id": "x1", "url": "u", "name": "Road"}], "max_files_per_folder": 200, "card_label": "music"}))
    from sdsync import config
    cfg = config.load()
    sd = config.target(cfg, "sd")
    assert sd["folders"] == [{"name": "Road", "playlists": ["x1"]}]
    assert sd["max_files_per_folder"] == 200 and sd["label"] == "MUSIC"
    assert config.target(cfg, "cdc")["folders"] == []


def test_display_sleeps_and_wakes(monkeypatch):
    from sdsync import display
    d = display.Display()
    calls = []
    monkeypatch.setattr(d, "_wlopm", lambda state: calls.append(state) or True)
    d.last_activity -= 200
    d.tick(5, keep_awake=False)
    assert d.on                            # only 200 s idle
    d.last_activity -= 200
    d.tick(5, keep_awake=True)             # a drive is writing: stays on, timer reset
    assert d.on
    d.last_activity -= 400
    d.tick(5, keep_awake=False)
    assert not d.on and calls == ["off"]
    d.activity("drive plugged in")
    assert d.on and calls == ["off", "on"]
    d.last_activity -= 10_000
    d.tick(0, keep_awake=False)            # 0 = never turn off
    assert d.on


def test_health_check_removes_broken_mp3(tmp_path, monkeypatch):
    monkeypatch.setenv("SDSYNC_HOME", str(tmp_path))
    for m in [m for m in sys.modules if m.startswith("sdsync")]:
        del sys.modules[m]
    from sdsync import service
    d = tmp_path / "cache" / "p1"
    d.mkdir(parents=True)
    (d / "bad.mp3").write_bytes(b"not an mp3 at all")
    (d / "work").mkdir()
    svc = service.Service()
    svc.health_check()
    assert not (d / "bad.mp3").exists() and not (d / "work").exists()
    assert "1 broken" in svc.status.library["health"]


def _takeout_zip():
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        base = "Takeout/YouTube and YouTube Music/"
        z.writestr(base + "playlists/playlists.csv",
                   "Playlist ID,Title\nPLabcdefghijklmnopqrstuvwxyz012345,Road Trip\n")
        z.writestr(base + "playlists/Road Trip-videos.csv",
                   "Video ID,Playlist Video Creation Timestamp\naaaaaaaaaaa,2024-01-01\nbbbbbbbbbbb,2024-01-01\naaaaaaaaaaa,x\n\n\n")
        z.writestr(base + "playlists/Jízda#U00e1-videos.csv", "Video ID,Time\nccccccccccc,2024\n")
        z.writestr(base + "music (library and uploads)/music library songs.csv",
                   "﻿Video ID,Song Title,Album Title,Artist Name 1,Artist Name 2\n"
                   "ddddddddddd,Song D,Album,Band,Guest\n")
        z.writestr(base + "videos/videos.csv", "Video ID,Duration,Language,Category,Title\neeeeeeeeeee,1,cs,10,Mine\n")
    return buf.getvalue()


def test_takeout_parse(env):
    from sdsync import takeout
    found = takeout.parse("takeout.zip", _takeout_zip())
    assert [(p["name"], len(p["tracks"])) for p in found] == [
        ("Liked & library songs", 1), ("Jízdaá", 1), ("Road Trip", 2)]
    assert found[0]["tracks"][0] == {"id": "ddddddddddd", "title": "Song D", "artist": "Band, Guest",
                                    "album": "Album", "main_artist": "Band"}
    one = takeout.parse("Road Trip-videos.csv", b"Video ID,Time\nbbbbbbbbbbb,1\n")
    assert one[0]["name"] == "Road Trip"
    with pytest.raises(ValueError):
        takeout.parse("x.csv", b"Playlist ID,Title\nPLx,y\n")


def test_takeout_import_downloads_by_id(env, monkeypatch):
    import types
    cardsync, cfg, card, make_playlist = env
    from sdsync import downloader, takeout

    takeout.save_tracks("imp1", [{"id": "aaaaaaaaaaa", "title": "", "artist": ""},
                                 {"id": "ddddddddddd", "title": "Song D", "artist": "Band"}])
    asked = []

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def extract_info(self, *a, **k):
            raise AssertionError("an imported playlist must not be listed from YouTube")

        def download(self, urls):
            for u in urls:
                vid = u.rsplit("=", 1)[1]
                asked.append(vid)
                info = {"id": vid, "title": "Some Artist - Real Title (Official Video)", "channel": "x"}
                for h in self.opts["progress_hooks"]:
                    h({"status": "downloading", "info_dict": info, "downloaded_bytes": 1, "total_bytes": 2})
                path = self.opts["outtmpl"].replace("%(id)s.%(ext)s", vid + ".mp3")
                open(path, "wb").write(b"\xff\xfb" + b"\0" * 500)
                for h in self.opts["post_hooks"]:
                    h(path)

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=FakeYDL))
    pl = {"id": "imp1", "url": "", "name": "Liked", "source": "takeout", "enabled": True}
    assert downloader.sync_playlist(pl, cfg) == 2
    assert sorted(asked) == ["aaaaaaaaaaa", "ddddddddddd"]
    tracks = downloader.read_order("imp1")["tracks"]
    assert tracks[0] == {"id": "aaaaaaaaaaa", "title": "Real Title", "artist": "Some Artist"}
    assert tracks[1]["title"] == "Song D"   # titles from the music library are kept
    assert downloader.sync_playlist(pl, cfg) == 0


def test_takeout_web_flow(env, monkeypatch):
    from sdsync import config, takeout, web
    body = (b"--XX\r\nContent-Disposition: form-data; name=\"file\"; filename=\"t.zip\"\r\n"
            b"Content-Type: application/zip\r\n\r\n" + _takeout_zip() + b"\r\n--XX--\r\n")
    name, data = web._parse_multipart("multipart/form-data; boundary=XX", body)["file"]
    assert name == "t.zip" and data == _takeout_zip()
    takeout.save_pending(takeout.parse(name, data))
    cfg = config.load()
    assert "Liked &amp; library songs" in web._import_html(cfg, "")
    assert web._import_confirm({"pick_0": "1", "pick_2": "1", "to": "sd"}) == 2
    cfg = config.load()
    assert [p["name"] for p in cfg["playlists"]] == ["Liked & library songs", "Road Trip"]
    assert len(config.target(cfg, "sd")["folders"]) == 2
    assert not takeout.load_pending()
    # A newer export updates the same playlist instead of adding another one.
    takeout.save_pending([{"name": "Road Trip", "library": False, "tracks": [{"id": "zzzzzzzzzzz"}]}])
    web._import_confirm({"pick_0": "1", "to": "sd"})
    cfg = config.load()
    rt = next(p for p in cfg["playlists"] if p["name"] == "Road Trip")
    assert len(cfg["playlists"]) == 2 and takeout.load_tracks(rt["id"]) == [{"id": "zzzzzzzzzzz"}]


def test_genre_sort(env, monkeypatch):
    from sdsync import config, genres, sorter, takeout, web
    tracks = [{"id": f"song{i:07d}", "title": f"S{i}", "artist": a, "main_artist": a, "album": al}
              for i, (a, al) in enumerate([("Goldie", "Timeless")] * 3 + [("Aphex Twin", "SAW")] * 2
                                          + [("Nobody", "")] + [("Polka Man", "Polkas")])]
    takeout.save_tracks("liked", tracks)
    cfg = config.load()
    cfg["playlists"] = [{"id": "liked", "url": "", "name": "Liked", "source": "takeout", "enabled": True}]
    config.save(cfg)

    asked = []

    def fetch(url):
        asked.append(url)
        if "genre/all" in url:
            return "drum and bass\nambient\npolka\n"
        if "release-group" in url and "Timeless" in url:
            return json.dumps({"release-groups": [{"score": 100, "tags": [
                {"name": "seen live", "count": 9}, {"name": "drum and bass", "count": 5}, {"name": "jungle", "count": 2}]}]})
        if "release-group" in url and "Polkas" in url:
            return json.dumps({"release-groups": [{"score": 100, "tags": [{"name": "polka", "count": 1}]}]})
        if "release-group" in url:
            return json.dumps({"release-groups": [{"score": 40, "tags": [{"name": "polka", "count": 3}]}]})
        if "Aphex" in url:
            return json.dumps({"artists": [{"score": 100, "tags": [{"name": "ambient", "count": 4}]}]})
        return json.dumps({"artists": []})

    mb = genres.MusicBrainz(fetch, delay=0)
    res = genres.lookup(tracks, mb)
    assert res["song0000000"] == "Drum and Bass" and res["song0000003"] == "Ambient"
    assert res["song0000005"] == "" and res["song0000006"] == "Polka"
    n = len(asked)
    genres.lookup(tracks, genres.MusicBrainz(fetch, delay=0))
    assert len(asked) == n   # all answers come from the cache
    genres._save(genres.results_path("liked"), res)

    groups = genres.summary(res, tracks, min_songs=2)
    assert [(g, len(ids)) for g, ids in groups] == [
        ("Drum and Bass", 3), ("Ambient", 2), ("Other genres", 1), ("Unknown genre", 1)]
    html = web._sort_page(config.load(), "liked", 2, False, web._add_targets(cfg))
    assert "Drum and Bass" in html and "Make playlists" in html

    web._sort_post("/sort/make", {"from": "liked", "min": "2", "to": "sd", "g_0": "1", "n_0": "DnB", "g_1": "1"}, {})
    cfg = config.load()
    kids = sorter.children(cfg, "liked")
    assert [k["name"] for k in kids] == ["DnB", "Ambient"]
    assert len(takeout.load_tracks(kids[0]["id"])) == 3
    assert len(config.target(cfg, "sd")["folders"]) == 2
    # Sorted songs drop out of the genre list; the rest can be moved by hand.
    assert [g for g, _ in genres.summary(res, tracks, sorter.membership(cfg, "liked"), 1)] == ["Polka", "Unknown genre"]
    web._sort_post("/sort/songs", {"from": "liked", "op": "add", "dest": kids[0]["id"]}, {"v": ["song0000005"]})
    assert len(takeout.load_tracks(kids[0]["id"])) == 4
    web._sort_post("/sort/songs", {"from": "liked", "op": "remove", "dest": kids[0]["id"]}, {"v": ["song0000005"]})
    assert len(takeout.load_tracks(kids[0]["id"])) == 3


def test_song_already_downloaded_is_copied(env, monkeypatch):
    import types
    cardsync, cfg, card, make_playlist = env
    from sdsync import downloader, takeout
    make_playlist("liked", "Liked", ["song0000001"])
    takeout.save_tracks("kid", [{"id": "song0000001", "title": "S", "artist": "A"}])
    monkeypatch.setattr(downloader, "tag_mp3", lambda *a: None)

    class NoYDL:
        def __init__(self, opts):
            raise AssertionError("must not download again")
    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=NoYDL))
    pl = {"id": "kid", "url": "", "name": "Kid", "source": "takeout", "enabled": True}
    assert downloader.sync_playlist(pl, cfg) == 1
    assert os.path.exists(os.path.join(downloader.playlist_dir("kid"), "song0000001.mp3"))


def test_takeout_to_youtube_resumes_after_quota(env, tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "t2y", os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "takeout_to_youtube.py"))
    t2y = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t2y)
    csvp = tmp_path / "genres.csv"
    csvp.write_text("video_id,artist,title,album,genre\n"
                    "aaaaaaaaaaa,A,1,,Jungle\nbbbbbbbbbbb,B,2,,Jungle\nccccccccccc,C,3,,Ambient\n"
                    "ddddddddddd,D,4,,\nnot-an-id,E,5,,Jungle\n")
    groups = t2y.plan(str(csvp))
    assert groups == {"Jungle": ["aaaaaaaaaaa", "bbbbbbbbbbb"], "Ambient": ["ccccccccccc"]}

    calls = []

    class Req:
        def __init__(self, kind, body):
            self.kind, self.body = kind, body

        def execute(self):
            if len(calls) == 3:
                calls.append("quota")
                raise t2y.QuotaExceeded()
            calls.append((self.kind, self.body["snippet"].get("title") or self.body["snippet"]["resourceId"]["videoId"]))
            return {"id": "PL" + self.body["snippet"].get("title", "x")}

    class YT:
        def playlists(self):
            return type("P", (), {"insert": lambda s, part, body: Req("pl", body)})()

        def playlistItems(self):
            return type("I", (), {"insert": lambda s, part, body: Req("item", body)})()

    state = {"playlists": {}, "done": {}}
    with pytest.raises(t2y.QuotaExceeded):
        t2y.upload(YT(), groups, state, lambda: None, log=lambda *a: None)
    assert state["done"] == {"Jungle": ["aaaaaaaaaaa", "bbbbbbbbbbb"]}
    t2y.upload(YT(), groups, state, lambda: None, log=lambda *a: None)
    assert calls[-2:] == [("pl", "Ambient"), ("item", "ccccccccccc")]
    assert [c for c in calls if c != "quota" and c[0] == "pl"] == [("pl", "Jungle"), ("pl", "Ambient")]
    assert 0 < t2y._seconds_to_quota_reset() <= 86400 + 600
