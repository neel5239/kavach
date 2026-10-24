"""Phase 2 pipeline: train final detector + segment head, then measure R1-R4 into runs/phase2/results.json.

Run after the Phase 2 feature extraction:  python scripts/phase2.py [--skip-train]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from kavach import audio  # noqa: E402
from kavach.features import Extractor  # noqa: E402
from kavach.model import CELL_S, SEG_WIN_S, Thresholds, cell_scores, load_head, save_head  # noqa: E402
from train import train_head  # noqa: E402
from train2 import load_set  # noqa: E402

SETS = ["itw:clean,phone,len2,len10", "itw_aug:chan,replay", "itw_aug_n:noisetr", "libri_n:noisetr", "modern:clean,replay", "libri:clean,replay,chan",
        "itw_p2test:clean,r8k,amr,opus,noise,chan"]


def f1_cells(items, thr):
    tp = fp = fn = 0
    for cells, a, b in items:
        for c in cells:
            mid = (c["start"] + c["end"]) / 2
            truth = a <= mid < b
            pred = c["score"] > thr
            tp += truth and pred
            fp += (not truth) and pred
            fn += truth and not pred
    p = tp / max(1, tp + fp)
    r = tp / max(1, tp + fn)
    return p, r, 2 * p * r / max(1e-9, p + r)


def main():
    out = ROOT / "runs" / "phase2"
    out.mkdir(parents=True, exist_ok=True)
    if "--skip-train" not in sys.argv:
        subprocess.run([sys.executable, "-u", str(ROOT / "scripts/train2.py"), "kavach", *SETS], check=True)
    K = json.loads((ROOT / "runs/kavach/results.json").read_text())["experiments"]
    B = json.loads((ROOT / "runs/itw/results.json").read_text())["experiments"]
    R = {}

    # R1 channel robustness on the 2,000-clip Phase 2 test set
    R["R1"] = {v: {"eer": K[f"itw_p2test:{v}"]["eer"]} for v in ["clean", "r8k", "amr", "opus", "noise", "chan"] if f"itw_p2test:{v}" in K}
    c = R["R1"]["clean"]["eer"]
    R["R1_worst_ratio"] = max(R["R1"][v]["eer"] for v in ["r8k", "amr", "opus", "noise"]) / max(c, 1e-9)
    R["R1_worst_condition"] = max(["r8k", "amr", "opus", "noise"], key=lambda v: R["R1"][v]["eer"])

    # R4 Phase 1 guard
    R["R4"] = {}
    for k, kk in [("E1_unseen_speakers_4s", "itw:clean"), ("E3_len_2s", "itw:len2"), ("E3_len_10s", "itw:len10"), ("E4_phone_line", "itw:phone")]:
        R["R4"][k] = {"eer": K[kk]["eer"], "phase1_eer": B[k]["eer"], "delta_points": (K[kk]["eer"] - B[k]["eer"]) * 100}
    R["R4_pass"] = all(abs(v["delta_points"]) <= 2.0 for v in R["R4"].values())

    # R2 segment head on 1 s crops
    meta, vs = load_set("itw_seg", ["seg1", "seg1c"])
    xtr = np.concatenate([np.asarray(x[np.where(s == "train")[0]]) for x, y, s, g in vs.values()])
    ytr = np.concatenate([y[s == "train"] for x, y, s, g in vs.values()])
    xcal = np.concatenate([np.asarray(x[np.where(s == "cal")[0]]) for x, y, s, g in vs.values()])
    ycal = np.concatenate([y[s == "cal"] for x, y, s, g in vs.values()])
    seg_head, seg_cal_eer = train_head(xtr, ytr, xcal, ycal)
    ex = Extractor()
    labels = json.loads((ROOT / "data/partial/labels.json").read_text())

    def cells_for(path):
        x, sr = sf.read(ROOT / path, dtype="float32")
        x = audio.normalise(audio.to_mono_16k(x, sr))
        wins = audio.windows(x, SEG_WIN_S, CELL_S)
        f = ex.batch([w for _, _, w in wins]).astype(np.float32)
        with torch.no_grad():
            sc = torch.sigmoid(seg_head(torch.from_numpy(f))).numpy().tolist()
        return cell_scores([(a, b, s) for (a, b, _), s in zip(wins, sc)], len(x) / audio.SR)

    cal = [(cells_for(l["path"]), l["fake_start"], l["fake_end"]) for l in labels if l["split"] == "cal"]
    test = [(cells_for(l["path"]), l["fake_start"], l["fake_end"]) for l in labels if l["split"] == "test"]
    grid = np.linspace(0.05, 0.95, 91)
    best = max(grid, key=lambda t: f1_cells(cal, t)[2])
    p, r, f = f1_cells(test, best)
    R["R2"] = {"n_test": len(test), "n_cal": len(cal), "cell_s": CELL_S, "threshold": float(best), "precision": p, "recall": r, "f1": f,
               "segment_head_cal_eer": seg_cal_eer,
               "cal_f1": f1_cells(cal, best)[2]}
    save_head(ROOT / "models" / "kavach_seg", seg_head, Thresholds(0.5, 0.5, 0.5), {"hidden": 128, "cell_threshold": float(best), "cell_s": CELL_S})
    # keep a few example timelines for the deck
    R["R2_examples"] = [{"path": l["path"], "fake": [l["fake_start"], l["fake_end"]], "cells": c} for (c, _, _), l in zip(test[:3], [l for l in labels if l["split"] == "test"][:3])]
    print("R2", R["R2"])

    # R3 streaming: cost of one 500 ms update = score latest 2 s
    head, cfg = load_head(ROOT / "models" / "kavach")
    x, sr = sf.read(ROOT / labels[0]["path"], dtype="float32")
    x = audio.normalise(audio.to_mono_16k(x, sr))
    ts = []
    for k in range(40):
        end = int((2 + (k % 8) * 0.5) * audio.SR)
        t0 = time.perf_counter()
        f = ex(audio.normalise(x[max(0, end - 2 * audio.SR): end]))
        with torch.no_grad():
            torch.sigmoid(head(torch.from_numpy(f[None].astype(np.float32))))
        ts.append((time.perf_counter() - t0) * 1000)
    ts = sorted(ts[5:])
    R["R3"] = {"interval_ms": 500, "window_s": 2.0, "p50_ms": round(ts[len(ts) // 2], 1), "p95_ms": round(ts[int(len(ts) * 0.95)], 1),
               "device": ex.device, "pass": ts[int(len(ts) * 0.95)] < 500}
    (out / "results.json").write_text(json.dumps(R, indent=2))
    print(json.dumps({k: v for k, v in R.items() if k != "R2_examples"}, indent=2))


if __name__ == "__main__":
    main()
