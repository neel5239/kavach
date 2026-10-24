"""Stream clips through /ws/stream exactly like the browser does (100 ms float32 chunks, real time optional)
and compare the live verdicts with the upload verdict.  Usage: python tests/stream_check.py clip1 [clip2 ...]"""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import numpy as np
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kavach import audio  # noqa: E402

BASE = "127.0.0.1:8320"


async def stream(x):
    out = []
    async with websockets.connect(f"ws://{BASE}/ws/stream", origin="http://localhost:8320", max_size=None) as ws:
        async def rx():
            try:
                async for m in ws:
                    out.append(json.loads(m))
            except Exception:
                pass
        t = asyncio.create_task(rx())
        for k in range(0, len(x), 1600):
            await ws.send(x[k:k + 1600].astype(np.float32).tobytes())
            await asyncio.sleep(0.02)
        await asyncio.sleep(2.0)
        await ws.close()
        await t
    return out


def main():
    c = httpx.Client(timeout=120)
    for p in sys.argv[1:]:
        up = c.post(f"http://{BASE}/api/analyze", files={"file": (Path(p).name, Path(p).read_bytes(), "audio/wav")}).json()
        x = audio.decode_bytes(Path(p).read_bytes())
        msgs = asyncio.run(stream(x))
        live = [m for m in msgs if m.get("score") is not None]
        verdicts = [m["verdict"] for m in live]
        print(f"{Path(p).name:42s} upload={up['verdict']:8s} {up['score']}  | live n={len(live)} last={verdicts[-1] if verdicts else None} "
              f"raw={[round(m['score'], 2) for m in live][:12]}")


if __name__ == "__main__":
    main()
