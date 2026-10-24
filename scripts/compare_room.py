"""Compare model heads on the held-out room recordings (speaker -> room -> mic on this laptop) and on In-the-Wild.
Usage: python scripts/compare_room.py kavach kavach_room   -> runs/room_compare.json"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from kavach.metrics import eer  # noqa: E402
from kavach.model import load_head  # noqa: E402
from train2 import load_set  # noqa: E402


def score(head, x):
    out = []
    with torch.no_grad():
        for k in range(0, len(x), 2048):
            out.append(torch.sigmoid(head(torch.from_numpy(np.asarray(x[k:k + 2048], dtype=np.float32)))).numpy())
    return np.concatenate(out)


def main():
    R = {}
    tests = {("room", v): None for v in ("clean", "noisetr", "noise")}
    tests.update({("itw", "clean"): None, ("itw", "phone"): None, ("modern", "clean"): None, ("modern", "replay"): None})
    data = {}
    for (name, v) in tests:
        _, d = load_set(name, [v])
        if v in d:
            x, y, s, g = d[v]
            m = s == "test"
            data[(name, v)] = (x[np.where(m)[0]], y[m])
    reals_by_v = {v: data[("itw", "clean")] for v in ("clean",)}
    for h in sys.argv[1:]:
        head, cfg = load_head(ROOT / "models" / h)
        th = cfg["thresholds"]
        R[h] = {}
        for key, (x, y) in data.items():
            if y.min() == y.max():  # fakes only (modern): pair with real In-the-Wild test clips
                xr, yr = data[("itw", "clean")]
                xr = xr[yr == 0]
                x, y = np.concatenate([xr, x]), np.r_[np.zeros(len(xr), int), y]
            sc = score(head, x)
            e, _ = eer(sc, y)
            R[h][f"{key[0]}:{key[1]}"] = {"eer": e, "fake_flagged": float((sc[y == 1] > th["fake_above"]).mean()),
                                          "real_called_fake": float((sc[y == 0] > th["fake_above"]).mean()), "n": int(len(y))}
        print(h)
        for k, v in R[h].items():
            print(f"   {k:16s} EER {v['eer'] * 100:5.1f}%  fakes flagged {v['fake_flagged'] * 100:5.1f}%  real wrongly FAKE {v['real_called_fake'] * 100:5.1f}%  n={v['n']}")
    (ROOT / "runs" / "room_compare.json").write_text(json.dumps(R, indent=1))


if __name__ == "__main__":
    main()
