"""coins.jsonl -> images/<mint>.jpg + images.jsonl (status, size, phash, dup_of).

IPFS: pump's pinata gateway first, ipfs.io last (it rate-limits hard).
Twitter thumbnails get rewritten to the large variant.
Coins are processed best-first (graduated, then mcap) so the dedup keeps the
coin that stuck as the representative of each visual cluster.
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from .images import UA, DupIndex, get, normalise, save
from .store import Store

GATEWAYS = ["https://pump.mypinata.cloud/ipfs/", "https://gateway.pinata.cloud/ipfs/", "https://ipfs.io/ipfs/"]


def candidates(url: str) -> list[str]:
    if "/ipfs/" in url:
        return [g + url.split("/ipfs/", 1)[1] for g in GATEWAYS]
    if "pbs.twimg.com" in url:
        big = re.sub(r"name=\w+", "name=large", url)
        return [big, url] if big != url else [url]
    return [url]


def fetch_any(client: httpx.Client, url: str, min_len: int = 500) -> bytes | None:
    for u in candidates(url):
        raw = get(client, u, min_len=min_len, tries=2)
        if raw:
            return raw
    return None


def one(client: httpx.Client, coin: dict, out: Path) -> dict:
    url, desc = coin.get("image_uri"), None
    if not url and coin.get("metadata_uri"):
        raw = fetch_any(client, coin["metadata_uri"], min_len=20)
        if raw:
            try:
                j = json.loads(raw)
                url, desc = j.get("image"), (j.get("description") or "")[:500]
            except ValueError:
                pass
    rec = {"key": coin["mint"], "image_uri": url, "description": desc, "status": "failed", "path": None, "w": None, "h": None, "phash": None, "dup_of": None}
    if not url:
        return rec
    raw = fetch_any(client, url)
    if not raw:
        return rec
    im, status = normalise(raw)
    rec["status"] = status
    if im is not None:
        p = out / "images" / f"{coin['mint']}.jpg"
        rec["phash"] = save(im, p)
        rec["path"], rec["w"], rec["h"] = str(p.relative_to(out)), im.size[0], im.size[1]
    return rec


def run(out: Path, workers: int = 16, limit: int = 0):
    coins = Store(out / "coins.jsonl", key="mint")
    images = Store(out / "images.jsonl")
    index = DupIndex()
    for r in images.rows.values():
        if r["status"] == "ok" and r["phash"]:
            index.add(r["phash"], r["key"])
    todo = sorted((c for c in coins.rows.values() if c["mint"] not in images), key=lambda c: (not c.get("complete"), -(c.get("mcap_usd") or 0)))
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} coins to fetch", flush=True)
    counts: dict[str, int] = {}
    with httpx.Client(headers=UA, http2=True, limits=httpx.Limits(max_connections=workers)) as client, ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(one, client, c, out): c for c in todo}
        for i, f in enumerate(as_completed(futs), 1):
            rec = f.result()
            if rec["status"] == "ok":
                d = index.find(rec["phash"])
                if d:
                    rec["status"], rec["dup_of"] = "dup", d
                else:
                    index.add(rec["phash"], rec["key"])
            counts[rec["status"]] = counts.get(rec["status"], 0) + 1
            images.add(rec)
            if i % 100 == 0:
                print(f"{i}/{len(todo)} {counts}", flush=True)
    print("done", counts, flush=True)
    return counts
