"""Extract and cache frozen XLS-R features for an index CSV.

Every clip is preprocessed (silence trim + loudness normalisation) and centre-cropped.
Variants:
  clean   - preprocessed audio, crop 4 s
  phone   - phone-line simulation of the same crop
  len2/len10 - crops of 2 s / 10 s (test split only) for the clip-length experiment
Also saves shortcut features (raw leading/trailing silence, raw RMS level, duration).

Usage: python scripts/extract.py data/index/itw.csv itw [--variants clean,phone,len2,len10] [--limit N]
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio  # noqa: E402
from kavach.features import Extractor  # noqa: E402

CROPS = {"clean": 4.0, "phone": 4.0, "replay": 4.0, "len2": 2.0, "len10": 10.0, "r8k": 4.0, "amr": 4.0, "opus": 4.0,
         "noise": 4.0, "noisetr": 4.0, "chan": 4.0, "seg1": 1.0, "seg1c": 1.0}


def shortcut_feats(raw: np.ndarray) -> list[float]:
    s, e = audio.trim_bounds(raw)
    dur = len(raw) / audio.SR
    rms = float(np.sqrt(np.mean(raw ** 2) + 1e-12))
    return [dur, dur - (e - s) / audio.SR, s / audio.SR, 20 * np.log10(rms + 1e-12)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("index")
    ap.add_argument("name")
    ap.add_argument("--variants", default="clean,phone,len2,len10")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--splits", default="train,cal,test")
    a = ap.parse_args()
    variants = a.variants.split(",")
    splits = set(a.splits.split(","))
    rows = [r for r in csv.DictReader(open(ROOT / a.index, encoding="utf-8")) if r["split"] in splits]
    if a.limit:
        rows = rows[: a.limit]
    out = ROOT / "data" / "features" / a.name
    out.mkdir(parents=True, exist_ok=True)
    ex = Extractor()
    rng = np.random.default_rng(11)
    feats = {v: [] for v in variants}
    keep = {v: [] for v in variants}
    meta, shortcut = [], []
    t0 = time.time()
    for k, r in enumerate(rows):
        try:
            wav, sr = sf.read(ROOT / r["path"], dtype="float32", always_2d=False)
        except Exception as e:  # unreadable file: skip, report
            print("skip", r["path"], e)
            continue
        raw = audio.to_mono_16k(wav, sr)
        clean = audio.preprocess(raw)
        if len(clean) < audio.SR // 2:
            continue
        idx = len(meta)
        meta.append(r)
        shortcut.append(shortcut_feats(raw))
        for v in variants:
            if v in ("len2", "len10") and r["split"] != "test":
                continue
            if v.startswith("seg1"):  # random 1 s crop for the segment (localisation) head
                n1 = audio.SR
                st = int(rng.integers(0, max(1, len(clean) - n1)))
                x = clean[st: st + n1]
            else:
                x = audio.center_crop(clean, CROPS[v])
            if v == "r8k":
                x = audio.resample_8k(x)
            elif v in ("amr", "opus"):
                x = audio.codec(x, v)
            elif v == "noise":
                x = audio.add_noise(x, 10.0, rng)
            elif v == "noisetr":  # training-time noise, random SNR, sometimes after a codec
                if rng.random() < 0.4:
                    x = audio.codec(x, str(rng.choice(["amr", "opus"])))
                x = audio.add_noise(x, float(rng.uniform(3, 20)), rng, kind=str(rng.choice(["mixed", "white"])))
            elif v in ("chan", "seg1c"):
                x = audio.channel_aug(x, rng)
            elif v == "phone":
                x = audio.phone_sim(x, rng)
            elif v == "replay":
                x = audio.replay_sim(x, rng)
                if rng.random() < 0.5:
                    x = audio.phone_sim(x, rng)
            feats[v].append(ex(x).astype(np.float16))
            keep[v].append(idx)
        if k % 500 == 0:
            el = time.time() - t0
            print(f"{k}/{len(rows)}  {el / 60:.1f} min  eta {(el / max(k, 1)) * (len(rows) - k) / 60:.1f} min", flush=True)
    for v in variants:
        np.save(out / f"{v}.npy", np.stack(feats[v]))
        np.save(out / f"{v}_idx.npy", np.array(keep[v]))
    np.save(out / "shortcut.npy", np.array(shortcut, dtype=np.float32))
    with open(out / "meta.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(meta[0].keys()))
        w.writeheader()
        w.writerows(meta)
    print("done", len(meta), "clips", f"{(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
