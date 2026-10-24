"""System test against a running server: latency p50/p95, concurrency, memory stability.

Usage: python tests/load_check.py [base_url] [n_requests] [concurrency]
Writes runs/load_test.json.
"""
import concurrent.futures as cf
import csv
import io
import json
import random
import statistics
import sys
import time
from pathlib import Path

import httpx
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]


def clips(n):
    rows = [r for r in csv.DictReader(open(ROOT / "data/index/itw.csv", encoding="utf-8")) if r["split"] == "test"]
    random.Random(4).shuffle(rows)
    out = []
    for r in rows[:n]:
        x, sr = sf.read(ROOT / r["path"], dtype="float32")
        x = x[: sr * 10]
        b = io.BytesIO()
        sf.write(b, x, sr, format="WAV")
        out.append(b.getvalue())
    return out


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8320"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    conc = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    data = clips(min(n, 40))
    client = httpx.Client(timeout=60)
    client.post(base + "/api/analyze", files={"file": ("w.wav", data[0], "audio/wav")})  # warm-up

    def one(k):
        t = time.perf_counter()
        r = client.post(base + "/api/analyze", files={"file": ("c.wav", data[k % len(data)], "audio/wav")})
        return r.status_code, (time.perf_counter() - t) * 1000, r.json().get("latency_ms") if r.status_code == 200 else None

    seq = [one(k) for k in range(min(20, n))]
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(conc) as ex:
        par = list(ex.map(one, range(n)))
    wall = time.perf_counter() - t0
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]
    lat_seq = [x[1] for x in seq]
    lat_par = [x[1] for x in par]
    srv = [x[2] for x in seq if x[2]]
    R = {
        "sequential": {"n": len(seq), "p50_ms": statistics.median(lat_seq), "p95_ms": q(lat_seq, 0.95), "server_p50_ms": statistics.median(srv)},
        "concurrent": {"n": n, "workers": conc, "p50_ms": statistics.median(lat_par), "p95_ms": q(lat_par, 0.95),
                       "throughput_rps": n / wall, "errors": sum(1 for x in par if x[0] != 200)},
        "health_after": client.get(base + "/api/health").json(),
    }
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs" / "load_test.json").write_text(json.dumps(R, indent=2))
    print(json.dumps(R, indent=2))


if __name__ == "__main__":
    main()
