"""Turn YouTube titles into names and tags the RNS-E can show.

The RNS-E display only handles plain ASCII reliably, FAT32 forbids some
characters, and long names get cut off on screen, so everything is
transliterated, cleaned and shortened here.
"""
import re
import unicodedata

_FAT_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_NOISE = re.compile(
    r"\s*[\(\[](?:official\s*)?(?:music\s*)?(?:hd\s*|hq\s*|4k\s*)?"
    r"(?:video|audio|lyrics?|lyric video|visualizer|visualiser|clip officiel|"
    r"official|remastered(?: \d{4})?|\d{4} remaster(?:ed)?|hd|hq|4k)[^\)\]]*[\)\]]",
    re.IGNORECASE,
)
_TOPIC = re.compile(r"\s*-\s*Topic$", re.IGNORECASE)


def ascii_fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = text.replace("ß", "ss").replace("Æ", "AE").replace("æ", "ae").replace("Ø", "O").replace("ø", "o")
    return text.encode("ascii", "ignore").decode("ascii")


def clean_text(text):
    """ASCII, no control chars, single spaces."""
    text = ascii_fold(text)
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def safe_name(text, max_len):
    """A FAT32-safe file or folder name, at most max_len characters."""
    text = _FAT_BAD.sub("", clean_text(text))
    text = text.strip(" .")
    if len(text) > max_len:
        text = text[:max_len].rstrip(" .-_")
    return text or "Untitled"


def split_artist_title(title, channel=""):
    """'Artist - Song (Official Video)' -> ('Artist', 'Song')."""
    title = _NOISE.sub("", title or "").strip()
    channel = _TOPIC.sub("", channel or "").strip()
    for sep in (" - ", " – ", " — ", " | "):
        if sep in title:
            artist, song = title.split(sep, 1)
            if artist.strip() and song.strip():
                return clean_text(artist), clean_text(song)
    return clean_text(channel), clean_text(title)


def track_filename(number, width, artist, title, max_len):
    prefix = f"{number:0{width}d} "
    body = f"{artist} - {title}" if artist else title
    return prefix + safe_name(body, max_len - len(prefix) - 4) + ".mp3"
