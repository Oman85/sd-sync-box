import argparse
import logging

from .service import Service

p = argparse.ArgumentParser(prog="sdsync")
p.add_argument("--port", type=int, default=80)
p.add_argument("--host", default="0.0.0.0")
a = p.parse_args()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("sdsync.yt-dlp").setLevel(logging.WARNING)
Service().run(a.host, a.port)
