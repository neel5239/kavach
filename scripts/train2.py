"""Train the final Kavach head on several cached feature sets and report every condition separately.

Usage: python scripts/train2.py OUTNAME SET[:variant,variant] SET[:variants] ...
  e.g. python scripts/train2.py kavach itw:clean,phone itw_replay:replay modern:clean,replay
Rows with split=train train the head; split=cal sets thresholds; split=test is only reported.
Also runs the shortcut test on the 'itw' set if present. Writes models/OUTNAME and runs/OUTNAME/results.json.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from kavach.metrics import eer, three_way  # noqa: E402
from kavach.model import Thresholds, save_head  # noqa: E402
from train import predict, train_head  # noqa: E402

torch.manual_seed(0)
np.random.seed(0)


def load_set(name, variants):
    d = ROOT / "data" / "features" / name
    meta = list(csv.DictReader(open(d / "meta.csv", encoding="utf-8")))
    out = {}
    for v in variants:
        if not (d / f"{v}.npy").exists():
            continue
        x, idx = np.load(d / f"{v}.npy", mmap_mode="r"), np.load(d / f"{v}_idx.npy")
        out[v] = (x, np.array([int(meta[i]["label"]) for i in idx]), np.array([meta[i]["split"] for i in idx]),
                  np.array([meta[i].get("generator", "itw") for i in idx]))
    return meta, out


def main():
    outname, specs = sys.argv[1], sys.argv[2:]
    sets, weight = {}, {}
    for sp in specs:
        sp, _, w = sp.partition("@")  # name:variants@K repeats that set's training rows K times
        name, _, vs = sp.partition(":")
        sets[name] = load_set(name, vs.split(",") if vs else ["clean"])
        weight[name] = int(w) if w else 1
    Xtr, Ytr, Xcal, Ycal = [], [], [], []
    for name, (_, vs) in sets.items():
        for v, (x, y, s, g) in vs.items():
            for _ in range(weight[name]):
                Xtr.append(np.asarray(x[np.where(s == "train")[0]])), Ytr.append(y[s == "train"])
            Xcal.append(np.asarray(x[np.where(s == "cal")[0]])), Ycal.append(y[s == "cal"])
    xtr, ytr = np.concatenate(Xtr), np.concatenate(Ytr)
    del Xtr
    xcal, ycal = np.concatenate(Xcal), np.concatenate(Ycal)
    print("train", len(ytr), "fake share", ytr.mean().round(3), "| cal", len(ycal))
    head, _ = train_head(xtr, ytr, xcal, ycal)
    s_cal = predict(head, xcal)
    e_cal, t_eer = eer(s_cal, ycal)
    lo = min(float(np.quantile(s_cal[ycal == 1], 0.02)), t_eer)
    hi = max(float(np.quantile(s_cal[ycal == 0], 0.98)), t_eer)
    th = Thresholds(real_below=lo, fake_above=hi, eer_threshold=t_eer)
    R = {"train_examples": int(len(ytr)), "calibration": {"eer": e_cal, "thresholds": th.__dict__}, "experiments": {}}

    # every test condition reported on its own; fake-only sets are paired with the real clips of the same variant
    reals = {}
    for name, (_, vs) in sets.items():
        for v, (x, y, s, g) in vs.items():
            m = (s == "test") & (y == 0)
            if m.any():
                reals.setdefault(v, []).append(np.asarray(x[np.where(m)[0]]))
    reals = {v: np.concatenate(a) for v, a in reals.items()}
    for name, (_, vs) in sets.items():
        for v, (x, y, s, g) in vs.items():
            m = s == "test"
            if not m.any():
                continue
            xt, yt = np.asarray(x[np.where(m)[0]]), y[m]
            if yt.min() == yt.max() == 1 and v in reals:  # fakes only: add real test clips of the same condition
                xt, yt = np.concatenate([reals[v], xt]), np.r_[np.zeros(len(reals[v]), int), yt]
            if yt.max() == 0:  # real-only set: report false alarms
                sc = predict(head, xt)
                R["experiments"][f"{name}:{v}"] = {"n_real": int(len(yt)), "real_called_fake": float((sc > hi).mean()),
                                                   "real_called_real": float((sc < lo).mean()), "not_sure_rate": float(((sc >= lo) & (sc <= hi)).mean())}
                print(f"{name}:{v:16s} real-only n={len(yt)} called_fake={R['experiments'][f'{name}:{v}']['real_called_fake']:.3f}")
                continue
            if yt.min() == yt.max():
                continue
            sc = predict(head, xt)
            e, _ = eer(sc, yt)
            key = f"{name}:{v}"
            R["experiments"][key] = {"eer": e, "n_real": int((yt == 0).sum()), "n_fake": int((yt == 1).sum()),
                                      "fake_flagged": float((sc[yt == 1] > hi).mean()), **three_way(sc, yt, lo, hi)}
            print(f"{key:22s} EER {e * 100:5.2f}%  real={int((yt == 0).sum())} fake={int((yt == 1).sum())}  flagged={R['experiments'][key]['fake_flagged']:.3f} missed={R['experiments'][key]['fake_called_real']:.3f}")
    # shortcut test
    if "itw" in sets:
        d = ROOT / "data" / "features" / "itw"
        meta = sets["itw"][0]
        sc_all = np.load(d / "shortcut.npy")
        split = np.array([m["split"] for m in meta])
        lab = np.array([int(m["label"]) for m in meta])
        scl = StandardScaler().fit(sc_all[split == "train"])
        lr = LogisticRegression(max_iter=1000).fit(scl.transform(sc_all[split == "train"]), lab[split == "train"])
        e_sc, _ = eer(lr.predict_proba(scl.transform(sc_all[split == "test"]))[:, 1], lab[split == "test"])
        R["experiments"]["shortcut_only_classifier"] = {"eer": e_sc}
        print("shortcut-only EER", round(e_sc * 100, 2))
    R["layer_weights"] = head.layer_weights().detach().numpy().round(4).tolist()
    out = ROOT / "runs" / outname
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(R, indent=2))
    save_head(ROOT / "models" / outname, head, th, {"hidden": 128, "trained_on": specs, "cal_eer": e_cal})
    print("saved", out / "results.json")


if __name__ == "__main__":
    main()
