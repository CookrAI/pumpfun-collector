import argparse
from pathlib import Path

import httpx

from . import api, fetch, stream
from .images import UA
from .store import Store


def cmd_sweep(a):
    out = Path(a.out)
    coins = Store(out / "coins.jsonl", key="mint")
    with httpx.Client(headers=UA, http2=True) as client:
        for graduated in ([True] if a.graduated_only else [True, False]):
            for sort in api.SORTS:
                n = 0
                for c in api.sweep(client, sort, graduated, nsfw=a.nsfw):
                    if c["mint"] in coins:
                        continue
                    if a.min_mcap and (c["mcap_usd"] or 0) < a.min_mcap:
                        continue
                    coins.add(c)
                    n += 1
                print(f"{sort:22s} graduated={int(graduated)} new={n:5d} total={len(coins)}", flush=True)


def cmd_stream(a):
    out = Path(a.out)
    coins = Store(out / "coins.jsonl", key="mint")
    n = [0]

    def sink(c):
        if c["mint"] in coins:
            return
        coins.add(c)
        n[0] += 1
        if n[0] % 50 == 0:
            print(f"+{n[0]} new, total {len(coins)}", flush=True)

    print(f"streaming for {a.minutes} min (0 = forever), Ctrl-C to stop", flush=True)
    stream.stream(a.minutes * 60, sink)
    print(f"stream done, +{n[0]} new coins, total {len(coins)}")


def cmd_fetch(a):
    fetch.run(Path(a.out), workers=a.workers, limit=a.limit)


def cmd_stats(a):
    out = Path(a.out)
    coins = Store(out / "coins.jsonl", key="mint")
    images = Store(out / "images.jsonl")
    print("coins    :", len(coins), " graduated:", sum(1 for c in coins.rows.values() if c.get("complete")))
    counts: dict[str, int] = {}
    for r in images.rows.values():
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("images   :", dict(sorted(counts.items(), key=lambda kv: -kv[1])))


def main():
    p = argparse.ArgumentParser(prog="pumpfun-collector", description="pump.fun coins + logos as a dataset")
    p.add_argument("--out", default="out", help="output folder (default ./out)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sweep", help="pull the coins that traded (frontend API, all sorts)")
    s.add_argument("--graduated-only", action="store_true")
    s.add_argument("--min-mcap", type=float, default=0, help="skip coins under this USD mcap")
    s.add_argument("--nsfw", action="store_true")
    s.set_defaults(fn=cmd_sweep)
    s = sub.add_parser("stream", help="collect new coins live from PumpPortal")
    s.add_argument("--minutes", type=float, default=0, help="stop after N minutes (0 = until Ctrl-C)")
    s.set_defaults(fn=cmd_stream)
    s = sub.add_parser("fetch", help="download + normalise + dedup images for coins.jsonl")
    s.add_argument("--workers", type=int, default=16)
    s.add_argument("--limit", type=int, default=0)
    s.set_defaults(fn=cmd_fetch)
    s = sub.add_parser("stats", help="what is in out/")
    s.set_defaults(fn=cmd_stats)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
