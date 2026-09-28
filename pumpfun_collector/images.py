"""Fetch -> normalise -> phash -> near-dup check. Standalone, no db.

Normalisation rules (what a diffusion trainer wants):
  RGB, alpha flattened on white, longest side <= MAX_SIDE, shortest side >= MIN_SIDE
  (never upscale), near-blank images dropped, saved as JPEG q92.
"""
import io
import re
import time
from collections import defaultdict
from pathlib import Path

import httpx
import imagehash
from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
MAX_SIDE = 1024
MIN_SIDE = 256
DUP_THRESH = 3  # hamming distance on 64-bit phash


def get(client: httpx.Client, url: str, min_len: int = 500, tries: int = 3) -> bytes | None:
    for i in range(tries):
        try:
            r = client.get(url, timeout=25, follow_redirects=True)
            if r.status_code == 200 and len(r.content) >= min_len:
                return r.content
            if r.status_code in (429, 503):
                time.sleep(2 * (i + 1))
                continue
            return None
        except httpx.HTTPError:
            time.sleep(1 + i)
    return None


def normalise(raw: bytes) -> tuple[Image.Image | None, str]:
    try:
        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im)
        if getattr(im, "is_animated", False):
            im.seek(0)
        im.load()
    except (UnidentifiedImageError, OSError, ValueError):
        return None, "bad"
    if min(im.size) < MIN_SIDE:
        return None, "small"
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    if ImageStat.Stat(im.convert("L").resize((64, 64))).var[0] < 30:
        return None, "flat"
    return im, "ok"


class DupIndex:
    """phash near-duplicate index. Pigeonhole: hashes within distance 3 share
    at least one of 4 exact 16-bit chunks, so only bucket-mates are compared."""

    def __init__(self, thresh: int = DUP_THRESH):
        self.thresh = thresh
        self.buckets: dict[tuple[int, int], list[tuple[int, str]]] = defaultdict(list)

    @staticmethod
    def chunks(h: int):
        for i in range(4):
            yield i, (h >> (16 * i)) & 0xFFFF

    def find(self, phash: str) -> str | None:
        h = int(phash, 16)
        seen = set()
        for cb in self.chunks(h):
            for kh, key in self.buckets[cb]:
                if key in seen:
                    continue
                seen.add(key)
                if bin(h ^ kh).count("1") <= self.thresh:
                    return key
        return None

    def add(self, phash: str, key: str):
        h = int(phash, 16)
        for cb in self.chunks(h):
            self.buckets[cb].append((h, key))


def save(im: Image.Image, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "JPEG", quality=92)
    return str(imagehash.phash(im))


def safe_name(s: str, n: int = 80) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:n].strip("_") or "x"
