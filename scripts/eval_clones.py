"""E5/E6: score our own clone sets with the trained detector. None of these generators were in training.

Fakes: data/index/clones.csv (snac, kokoro, veena, rvc).
Reals: the In-the-Wild test-split real clips (unseen speakers) + optional team recordings in data/index/team.csv.
Usage: python scripts/eval_clones.py itw
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio  # noqa: E402
from kavach.features import Extractor  # noqa: E402
from kavach.metrics import eer, three_way  # noqa: E402
from kavach.model import LayerMixHead, Thresholds  # noqa: E402


def feats_for(rows, ex, phone=False):
    out, keep = [], []
    rng = np.random.default_rng(1)
    for r in rows:
        x, sr = sf.read(ROOT / r["path"], dtype="float32")
        x = audio.preprocess(audio.to_mono_16k(x, sr))
        if len(x) < audio.SR // 2:
            continue
        x = audio.center_crop(x, 4.0)
        if phone:
            x = audio.phone_sim(x, rng)
        out.append(ex(x))
        keep.append(r)
    return np.stack(out).astype(np.float32), keep


def main():
    name = sys.argv[1]
    mdir = ROOT / "models" / name
    cfg = json.loads((mdir / "config.json").read_text())
    th = Thresholds(**cfg["thresholds"])
    head = LayerMixHead(hidden=cfg.get("hidden", 128))
    head.load_state_dict(torch.load(mdir / "head.pt", weights_only=True))
    head.eval()
    score = lambda x: torch.sigmoid(head(torch.from_numpy(x))).detach().numpy()

    fd = ROOT / "data" / "features" / (sys.argv[2] if len(sys.argv) > 2 else "itw")
    meta = list(csv.DictReader(open(fd / "meta.csv", encoding="utf-8")))
    xc, idx = np.load(fd / "clean.npy").astype(np.float32), np.load(fd / "clean_idx.npy")
    m = np.array([meta[i]["split"] == "test" and meta[i]["label"] == "0" for i in idx])
    real_scores = score(xc[m])
    xp, idxp = np.load(fd / "phone.npy").astype(np.float32), np.load(fd / "phone_idx.npy")
    mp = np.array([meta[i]["split"] == "test" and meta[i]["label"] == "0" for i in idxp])
    real_phone = score(xp[mp])

    ex = Extractor()
    rows = list(csv.DictReader(open(ROOT / "data/index/clones.csv", encoding="utf-8")))
    mod = ROOT / "data/index/modern.csv"
    if mod.exists():  # Kokoro voices used in training must not count as unseen
        testv = {r["speaker"] for r in csv.DictReader(open(mod, encoding="utf-8")) if r["generator"] == "kokoro" and r["split"] == "test"}
        rows = [r for r in rows if r["generator"] != "kokoro" or r["speaker"] in testv]
    team = ROOT / "data/index/team.csv"
    team_real = None
    if team.exists():
        trows = list(csv.DictReader(open(team, encoding="utf-8")))
        tx, _ = feats_for(trows, ex)
        team_real = score(tx)

    R = {"model": name, "real_itw_test_n": int(len(real_scores)), "generators": {}}
    all_fake = []
    for g in sorted({r["generator"] for r in rows}):
        gr = [r for r in rows if r["generator"] == g]
        x, kept = feats_for(gr, ex)
        s = score(x)
        all_fake.append(s)
        y = np.r_[np.zeros(len(real_scores)), np.ones(len(s))]
        sc = np.r_[real_scores, s]
        e, _ = eer(sc, y)
        xph, _ = feats_for(gr, ex, phone=True)
        sph = score(xph)
        eph, _ = eer(np.r_[real_phone, sph], np.r_[np.zeros(len(real_phone)), np.ones(len(sph))])
        R["generators"][g] = {"n": len(s), "eer_vs_itw_real": e, "eer_phone_line": eph,
                              "detected_as_fake": float((s > th.fake_above).mean()),
                              "called_real": float((s < th.real_below).mean()), **{"three_way": three_way(sc, y, th.real_below, th.fake_above)}}
        langs = {r["lang"] for r in kept}
        if "hi" in langs:
            hs = s[[r["lang"] == "hi" for r in kept]]
            R["generators"][g]["hindi_detected_as_fake"] = float((hs > th.fake_above).mean())
        print(g, R["generators"][g])
    if team_real is not None:
        R["team_real_n"] = int(len(team_real))
        R["team_real_called_real"] = float((team_real < th.real_below).mean())
        R["team_real_called_fake"] = float((team_real > th.fake_above).mean())
    ut = ROOT / "data" / "user_tests"  # clips the team recorded from GPT / Gemini voice chat (all AI)
    if ut.is_dir():
        files = [p for p in sorted(ut.iterdir()) if p.suffix.lower() in {".wav", ".m4a", ".mp3", ".ogg", ".webm", ".flac", ".aac", ".opus", ".mp4"}]
        res = []
        for p in files:
            x = audio.preprocess(audio.decode_bytes(p.read_bytes()))
            ws = audio.windows(x)
            sc = score(np.stack([ex(w) for _, _, w in ws]).astype(np.float32))
            from kavach.model import aggregate, verdict_for
            c = aggregate(sc.tolist())
            res.append({"file": p.name, "score": round(c, 4), "verdict": verdict_for(c, th, len(x) / audio.SR)})
            print("user test", res[-1])
        R["user_tests"] = res
    out = ROOT / "runs" / name / "clones.json"
    out.write_text(json.dumps(R, indent=2))
    print("saved", out)


if __name__ == "__main__":
    main()
