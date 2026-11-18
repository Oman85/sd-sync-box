#!/usr/bin/env python3
"""One-time: turn liked songs from a Google Takeout into genre playlists on YouTube.

Run it on any computer with Python 3 and a web browser (the box works too).

Step 1, genres (no account needed, 10 to 30 minutes for ~1,700 songs):

    python3 tools/takeout_to_youtube.py genres takeout.zip

  Looks up each liked song's genre on MusicBrainz and writes genres.csv
  (video_id, artist, title, album, genre). Open it in a spreadsheet and change
  any genre you like before step 2; songs with an empty genre are left out.
  Small genres are merged into "Other genres" (change with --min).

Step 2, upload (needs a Google Cloud OAuth client, see --help-setup):

    pip install google-api-python-client google-auth-oauthlib
    python3 tools/takeout_to_youtube.py upload genres.csv

  Creates one unlisted playlist per genre on your YouTube account and adds the
  songs. YouTube's free API quota allows about 190 songs a day, so ~1,700 songs
  take about 9 days: leave it running and it waits for the quota to reset each
  night (midnight Pacific time), or stop it and run the same command again
  later; it carries on where it stopped (progress is kept in upload-progress.json).

Unlisted playlists can then be added to the box with their normal links.
"""
import argparse
import csv
import datetime
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
WORK = os.path.abspath(os.environ.get("SDSYNC_HOME", "takeout-work"))
os.environ["SDSYNC_HOME"] = WORK          # genre cache goes here, not /var/lib/sdsync

from sdsync import genres, takeout  # noqa: E402

SETUP = """\
One-time Google setup for 'upload' (about 10 minutes):
 1. Go to https://console.cloud.google.com/ and create a project (any name).
 2. APIs & Services > Library: enable "YouTube Data API v3".
 3. APIs & Services > OAuth consent screen: External, fill in the app name and
    your email, and under Test users add the Google account that owns your YouTube.
 4. APIs & Services > Credentials > Create credentials > OAuth client ID >
    Desktop app. Download the JSON and save it as client_secret.json next to
    genres.csv (or pass --client-secret PATH).
 5. Run the upload command. A browser opens: sign in, and allow access
    (Google warns the app is unverified because it's your own; continue).
"""

SCOPES = ["https://www.googleapis.com/auth/youtube"]


# ---- step 1 -------------------------------------------------------------

def cmd_genres(a):
    with open(a.takeout, "rb") as f:
        found = takeout.parse(os.path.basename(a.takeout), f.read())
    lib = next((p for p in found if p["library"]), None)
    if not lib:
        sys.exit("No liked/library songs list in this Takeout (music library songs.csv).")
    tracks = lib["tracks"]
    print(f"{len(tracks)} liked songs. Looking up genres on MusicBrainz "
          f"(about 1 per second, answers are cached in {WORK}) ...")

    def prog(n, total):
        if n % 25 == 0 or n == total:
            print(f"  {n}/{total}", flush=True)

    try:
        res = genres.lookup(tracks, progress=prog)
    except RuntimeError as e:
        sys.exit(f"Stopped: {e}\nAnswers so far are kept; running it again carries on.")
    by_id = {}
    for g, ids in genres.summary(res, tracks, min_songs=a.min):
        for v in ids:
            by_id[v] = "" if g == "Unknown genre" else g
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "artist", "title", "album", "genre"])
        for t in tracks:
            w.writerow([t["id"], t.get("artist", ""), t.get("title", ""), t.get("album", ""), by_id.get(t["id"], "")])
    counts = {}
    for g in by_id.values():
        counts[g or "(no genre, left out)"] = counts.get(g or "(no genre, left out)", 0) + 1
    print(f"\nWrote {a.out}:")
    for g, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {n:5d}  {g}")
    print("\nEdit the genre column if you like, then run: upload " + a.out)


# ---- step 2 -------------------------------------------------------------

class QuotaExceeded(Exception):
    pass


def _youtube(client_secret, token_path):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Install the Google libraries first:\n  pip install google-api-python-client google-auth-oauthlib")
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not os.path.exists(client_secret):
            sys.exit(f"{client_secret} not found.\n\n" + SETUP)
        flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _call(req):
    try:
        from googleapiclient.errors import HttpError
    except ImportError:          # only in tests
        class HttpError(Exception):
            pass
    for attempt in range(5):
        try:
            return req.execute()
        except HttpError as e:
            text = str(e)
            if e.resp.status == 403 and ("quotaExceeded" in text or "dailyLimitExceeded" in text):
                raise QuotaExceeded()
            if e.resp.status == 404 or "videoNotFound" in text:
                return None                     # video deleted or private: skip it
            if e.resp.status in (409, 500, 503) and attempt < 4:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def _seconds_to_quota_reset():
    """YouTube's daily quota resets at midnight Pacific time."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-8)))
    nxt = (now + datetime.timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    return (nxt - now).total_seconds()


def plan(csv_path):
    """{genre: [video ids]} in file order, empty genres left out."""
    out = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            g, v = (r.get("genre") or "").strip(), (r.get("video_id") or "").strip()
            if g and takeout.VIDEO_ID.match(v):
                out.setdefault(g[:150], [])
                if v not in out[g[:150]]:
                    out[g[:150]].append(v)
    return out


def upload(yt, groups, state, save, privacy="unlisted", log=print):
    """Create playlists and add songs, skipping what state says is done.

    state: {"playlists": {genre: playlist id}, "done": {genre: [video ids]}}
    Raises QuotaExceeded when the day's quota is used up.
    """
    for g, ids in groups.items():
        pid = state["playlists"].get(g)
        if not pid:
            res = _call(yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": g, "description": "Liked songs sorted by genre (from Google Takeout)."},
                "status": {"privacyStatus": privacy}}))
            pid = state["playlists"][g] = res["id"]
            save()
            log(f"Created playlist {g}: https://www.youtube.com/playlist?list={pid}")
        done = set(state["done"].setdefault(g, []))
        todo = [v for v in ids if v not in done]
        for n, v in enumerate(todo, 1):
            _call(yt.playlistItems().insert(part="snippet", body={
                "snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": v}}}))
            state["done"][g].append(v)
            save()
            if n % 10 == 0 or n == len(todo):
                log(f"  {g}: {len(state['done'][g])}/{len(ids)}")


def cmd_upload(a):
    if not os.path.exists(a.csv):
        sys.exit(f"{a.csv} not found. Run the 'genres' step first.")
    groups = plan(a.csv)
    if not groups:
        sys.exit("No songs with a genre in " + a.csv)
    total = sum(len(v) for v in groups.values())
    state = {"playlists": {}, "done": {}}
    if os.path.exists(a.progress):
        with open(a.progress, encoding="utf-8") as f:
            state = json.load(f)

    def save():
        tmp = a.progress + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, a.progress)

    left = total - sum(len(set(state["done"].get(g, [])) & set(ids)) for g, ids in groups.items())
    print(f"{len(groups)} playlists, {total} songs, {left} still to add "
          f"(about {max(1, -(-left // 190))} day(s) of YouTube quota).")
    yt = _youtube(a.client_secret, a.token)
    while True:
        try:
            upload(yt, groups, state, save, a.privacy)
            break
        except QuotaExceeded:
            if not a.wait:
                sys.exit("YouTube's daily quota is used up. Run the same command again tomorrow to carry on.")
            secs = _seconds_to_quota_reset()
            print(f"Daily quota used up. Waiting {secs / 3600:.1f} h for it to reset (Ctrl+C to stop; "
                  "run the same command later to carry on).", flush=True)
            time.sleep(secs)
    print("\nAll done:")
    for g, pid in state["playlists"].items():
        print(f"  {g}: https://www.youtube.com/playlist?list={pid}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--help-setup", action="store_true", help="how to get client_secret.json")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("genres", help="look up genres, write genres.csv")
    g.add_argument("takeout", help="the Takeout .zip, or music library songs.csv")
    g.add_argument("--out", default="genres.csv")
    g.add_argument("--min", type=int, default=10, help="smallest genre with its own playlist (default 10)")
    u = sub.add_parser("upload", help="create the playlists on YouTube from genres.csv")
    u.add_argument("csv", nargs="?", default="genres.csv")
    u.add_argument("--client-secret", default="client_secret.json")
    u.add_argument("--token", default="youtube-token.json", help="where the sign-in is kept (keep it private)")
    u.add_argument("--progress", default="upload-progress.json")
    u.add_argument("--privacy", default="unlisted", choices=["unlisted", "private", "public"],
                   help="unlisted (default) lets the box read the playlists by link")
    u.add_argument("--no-wait", dest="wait", action="store_false", help="stop instead of waiting for tomorrow's quota")
    a = ap.parse_args(argv)
    if a.help_setup:
        print(SETUP)
    elif a.cmd == "genres":
        cmd_genres(a)
    elif a.cmd == "upload":
        cmd_upload(a)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
