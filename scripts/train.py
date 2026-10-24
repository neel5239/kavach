"""Train the layer-mix head on cached features, calibrate thresholds, run experiments E1-E4.

Usage: python scripts/train.py itw [--no-phone-aug]
Writes models/<name>/ and runs/<name>/results.json. Every number in the deck comes from here.
"""
import argparse
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
from kavach.metrics import eer, three_way  # noqa: E402
from kavach.model import LayerMixHead, Thresholds, save_head  # noqa: E402

torch.manual_seed(0)
np.random.seed(0)


def load(name):
    d = ROOT / "data" / "features" / name
    meta = list(csv.DictReader(open(d / "meta.csv", encoding="utf-8")))
    split = np.array([m["split"] for m in meta])
    label = np.array([int(m["label"]) for m in meta])
    feats = {}
    for f in d.glob("*_idx.npy"):
        v = f.name[:-8]
        feats[v] = (np.load(d / f"{v}.npy", mmap_mode="r"), np.load(f))
    return meta, split, label, feats, np.load(d / "shortcut.npy")


def subset(feats, v, split, label, which):
    x, idx = feats[v]
    m = split[idx] == which
    return np.asarray(x[np.where(m)[0]]), label[idx][m]  # stays float16; converted per batch


def predict(head, x):
    head.eval()
    with torch.no_grad():
        out = []
        for k in range(0, len(x), 2048):
            out.append(torch.sigmoid(head(torch.from_numpy(np.asarray(x[k:k + 2048], dtype=np.float32)))).numpy())
    return np.concatenate(out)


def train_head(xtr, ytr, xcal, ycal, epochs=40, lr=1e-3, hidden=128):
    head = LayerMixHead(hidden=hidden)
    opt = torch.optim.AdamW(head.parameters(), lr=lr, weight_decay=1e-2)
    pos_w = torch.tensor((ytr == 0).sum() / max(1, (ytr == 1).sum()), dtype=torch.float32)
    lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pos_w)
    xt, yt = torch.from_numpy(np.ascontiguousarray(xtr, dtype=np.float16)), torch.from_numpy(ytr.astype(np.float32))
    best, best_state, bad = 1.0, None, 0
    for ep in range(epochs):
        head.train()
        perm = torch.randperm(len(xt))
        for k in range(0, len(xt), 256):
            b = perm[k:k + 256]
            opt.zero_grad()
            loss = lossf(head(xt[b].float()), yt[b])
            loss.backward()
            opt.step()
        e, _ = eer(predict(head, xcal), ycal)
        if e < best - 1e-4:
            best, best_state, bad = e, {k: v.clone() for k, v in head.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= 6:
                break
        print(f"  epoch {ep:2d} cal EER {e * 100:.2f}%", flush=True)
    head.load_state_dict(best_state)
    return head, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--no-phone-aug", action="store_true")
    a = ap.parse_args()
    meta, split, label, feats, sc = load(a.name)
    R = {"dataset": a.name, "counts": {}}
    for s in ("train", "cal", "test"):
        m = split == s
        R["counts"][s] = {"real": int(((label == 0) & m).sum()), "fake": int(((label == 1) & m).sum()),
                          "speakers": len({meta[i]["speaker"] for i in np.where(m)[0]})}

    xtr, ytr = subset(feats, "clean", split, label, "train")
    if "phone" in feats and not a.no_phone_aug:
        xp, yp = subset(feats, "phone", split, label, "train")
        xtr, ytr = np.concatenate([xtr, xp]), np.concatenate([ytr, yp])
    xcal, ycal = subset(feats, "clean", split, label, "cal")
    print("training on", len(xtr), "examples")
    head, cal_eer = train_head(xtr, ytr, xcal, ycal)

    # thresholds from calibration split only
    s_cal = predict(head, xcal)
    e_cal, t_eer = eer(s_cal, ycal)
    lo = float(np.quantile(s_cal[ycal == 1], 0.02))   # <=2% of fakes fall below -> REAL
    hi = float(np.quantile(s_cal[ycal == 0], 0.98))   # <=2% of reals rise above -> FAKE
    lo, hi = min(lo, t_eer), max(hi, t_eer)
    th = Thresholds(real_below=lo, fake_above=hi, eer_threshold=t_eer)
    R["calibration"] = {"eer": e_cal, "thresholds": th.__dict__}

    # E1 unseen speakers, E3 lengths, E4 phone
    exps = {}
    for v, key in (("clean", "E1_unseen_speakers_4s"), ("len2", "E3_len_2s"), ("len10", "E3_len_10s"), ("phone", "E4_phone_line")):
        if v not in feats:
            continue
        x, y = subset(feats, v, split, label, "test")
        s = predict(head, x)
        e, _ = eer(s, y)
        exps[key] = {"eer": e, "n": int(len(y)), **three_way(s, y, lo, hi)}
        print(f"{key:24s} EER {e * 100:.2f}%  n={len(y)}")

    # E2 shortcut test: can silence/loudness/duration alone separate real from fake?
    sc_tr, sc_te = sc[split == "train"], sc[split == "test"]
    scaler = StandardScaler().fit(sc_tr)
    lr = LogisticRegression(max_iter=1000).fit(scaler.transform(sc_tr), label[split == "train"])
    s_sc = lr.predict_proba(scaler.transform(sc_te))[:, 1]
    e_sc, _ = eer(s_sc, label[split == "test"])
    xt, yt = subset(feats, "clean", split, label, "test")
    s_model = predict(head, xt)
    idx_test = feats["clean"][1][split[feats["clean"][1]] == "test"]
    corr = {n: float(np.corrcoef(s_model, sc[idx_test][:, j])[0, 1]) for j, n in enumerate(["duration", "total_silence", "leading_silence", "loudness_db"])}
    exps["E2_shortcut_only_classifier"] = {"eer": e_sc, "features": "duration, total silence, leading silence, loudness"}
    exps["E2_model_score_correlation_with_shortcuts"] = corr
    print(f"E2 shortcut-only EER {e_sc * 100:.2f}%  model corr {corr}")

    R["experiments"] = exps
    R["layer_weights"] = head.layer_weights().detach().numpy().round(4).tolist()
    R["phone_augmentation"] = not a.no_phone_aug
    tag = a.name + ("_nophone" if a.no_phone_aug else "")
    out = ROOT / "runs" / tag
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(R, indent=2))
    save_head(ROOT / "models" / tag, head, th, {"hidden": 128, "trained_on": a.name, "cal_eer": e_cal})
    print("saved", out / "results.json")


if __name__ == "__main__":
    main()
