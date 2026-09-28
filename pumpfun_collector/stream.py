"""Live token creations via PumpPortal's public websocket (no key).
Roughly 20-40k new coins a day. Yields {mint,name,symbol,metadata_uri}."""
import asyncio
import json
import time

import websockets

WS = "wss://pumpportal.fun/api/data"


async def _run(seconds: float, sink):
    deadline = time.time() + seconds if seconds else None
    while deadline is None or time.time() < deadline:
        try:
            async with websockets.connect(WS, ping_interval=20) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                while deadline is None or time.time() < deadline:
                    try:
                        m = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    except asyncio.TimeoutError:
                        continue
                    if "mint" in m and m.get("uri"):
                        sink({
                            "mint": m["mint"], "name": (m.get("name") or "").strip(),
                            "symbol": (m.get("symbol") or "").strip(),
                            "metadata_uri": m["uri"], "image_uri": None,
                            "mcap_usd": 0, "complete": False, "created_ts": int(time.time()),
                            "creator": m.get("traderPublicKey"),
                        })
        except (websockets.WebSocketException, OSError) as e:
            print("ws reconnect:", e, flush=True)
            await asyncio.sleep(3)


def stream(seconds: float, sink):
    try:
        asyncio.run(_run(seconds, sink))
    except KeyboardInterrupt:
        pass
