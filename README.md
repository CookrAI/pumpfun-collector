# pumpfun-collector

Collect pump.fun coin metadata and logo images as a clean, deduplicated
image dataset. No API keys.

```
pip install git+https://github.com/CookrAI/pumpfun-collector
pumpfun-collector sweep            # ~7k coins that actually traded (graduated first)
pumpfun-collector stream --minutes 60   # live creations, ~25/min, no key
pumpfun-collector fetch            # images/<mint>.jpg + images.jsonl (phash, dedup)
pumpfun-collector stats
```

## What you get

```
out/
  coins.jsonl    mint, name, symbol, description, image_uri, mcap_usd, complete, creator
  images.jsonl   key(mint), status, path, w, h, phash, dup_of
  images/<mint>.jpg
```

Status values: `ok` `dup` `small` `flat` `bad` `failed`.

## How it works

- `sweep` hits the frontend API. It only pages ~1000 deep per query, so every
  sort (market cap, last trade, replies, created) is swept for graduated and
  for all coins, unioned on mint. That is the top of the platform: coins
  people actually bought.
- `stream` subscribes to PumpPortal's public websocket for new mints. Volume,
  not quality: most of these die in minutes. Leave it running if you want
  tens of thousands.
- `fetch` resolves IPFS through pump's own gateway first (ipfs.io rate-limits),
  flattens transparent PNGs on white, caps at 1024px, drops anything under
  256px instead of upscaling, drops blank images, and marks perceptual
  near-duplicates (about 18% of pump.fun) keeping the highest-mcap coin as the
  representative.

Everything is resumable: re-run any command and it only touches new rows.

---
Part of [COOKR](https://github.com/CookrAI/cookr), the open meme image model. [cookr.pro](https://cookr.pro) · hi@cookr.pro · MIT
