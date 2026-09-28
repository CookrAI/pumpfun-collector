"""pump.fun frontend API sweep.

The API pages ~1000 deep per query, no cursor. So we sweep every sort we know,
once for graduated coins and once for all, and union on mint. Result: the
few thousand coins that actually traded, which is the signal you want.
"""
import time

import httpx

BASE = "https://frontend-api-v3.pump.fun/coins"
SORTS = ["market_cap", "last_trade_timestamp", "reply_count", "last_reply", "created_timestamp"]
PAGE = 50


def norm(c: dict) -> dict:
    return {
        "mint": c["mint"],
        "name": (c.get("name") or "").strip(),
        "symbol": (c.get("symbol") or "").strip(),
        "description": (c.get("description") or "").strip()[:500],
        "image_uri": c.get("image_uri"),
        "metadata_uri": c.get("metadata_uri"),
        "mcap_usd": c.get("usd_market_cap") or c.get("market_cap_usd") or 0,
        "complete": bool(c.get("complete")),
        "created_ts": (c.get("created_timestamp") or 0) // 1000,
        "creator": c.get("creator"),
    }


def sweep(client: httpx.Client, sort: str, graduated: bool, nsfw: bool = False, delay: float = 0.25):
    offset, empty = 0, 0
    while empty < 3:
        params = {"offset": offset, "limit": PAGE, "sort": sort, "order": "DESC", "includeNsfw": str(nsfw).lower()}
        if graduated:
            params["complete"] = "true"
        rows = None
        for attempt in range(5):
            try:
                r = client.get(BASE, params=params, timeout=30)
                if r.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                r.raise_for_status()
                rows = r.json()
                break
            except (httpx.HTTPError, ValueError):
                time.sleep(2 * (attempt + 1))
        if rows is None:
            return
        if not rows:
            empty += 1
        else:
            empty = 0
            for c in rows:
                if c.get("mint"):
                    yield norm(c)
        offset += PAGE
        time.sleep(delay)
