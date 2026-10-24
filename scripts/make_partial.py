"""Build partial fakes: a real clip of a speaker with one 1-3 s stretch replaced by a fake of the SAME speaker.

100 test partial fakes from test speakers + 60 calibration ones from cal speakers (threshold tuning only).
Loudness matched, 20 ms crossfades. Ground truth fake interval saved in data/partial/labels.json.
Run: python scripts/make_partial.py
"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio  # noqa: E402

OUT = ROOT / "data" / "partial"


def load(p):
    x, sr = sf.read(ROOT / p, dtype="float32")
    return audio.preprocess(audio.to_mono_16k(x, sr))


def splice(real, fake, rng):
    sr = audio.SR
    total = min(len(real), int(rng.uniform(6, 10) * sr))
    base = real[:total].copy()
    seg_len = int(rng.uniform(1.0, 3.0) * sr)
    seg_len = min(seg_len, len(fake), total - sr)
    if seg_len < sr:
        return None
    fs = int(rng.integers(0, len(fake) - seg_len + 1))
    seg = fake[fs: fs + seg_len].copy()
    seg *= np.sqrt(np.mean(base ** 2) + 1e-12) / np.sqrt(np.mean(seg ** 2) + 1e-12)
    start = int(rng.integers(int(0.5 * sr), total - seg_len - int(0.3 * sr) + 1)) if total - seg_len - int(0.8 * sr) > 0 else 0
    xf = int(0.02 * sr)
    ramp = np.linspace(0, 1, xf, dtype=np.float32)
    out = base.copy()
    out[start: start + seg_len] = seg
    out[start: start + xf] = base[start: start + xf] * (1 - ramp) + seg[:xf] * ramp
    e = start + seg_len
    out[e - xf: e] = seg[-xf:] * (1 - ramp) + base[e - xf: e] * ramp
    return audio.normalise(out), start / sr, e / sr


def main():
    rows = list(csv.DictReader(open(ROOT / "data/index/itw.csv", encoding="utf-8")))
    by = defaultdict(lambda: {0: [], 1: []})
    for r in rows:
        by[(r["split"], r["speaker"])][int(r["label"])].append(r["path"])
    rng = np.random.default_rng(42)
    OUT.mkdir(parents=True, exist_ok=True)
    labels = []
    for split, n in (("test", 100), ("cal", 60)):
        spk = [k for k in by if k[0] == split and by[k][0] and by[k][1]]
        random.Random(7).shuffle(spk)  # dataset shuffling only
        made, k = 0, 0
        while made < n and k < 5000:
            key = spk[k % len(spk)]
            k += 1
            reals = [p for p in by[key][0]]
            fakes = by[key][1]
            real = load(reals[int(rng.integers(len(reals)))])
            if len(real) < 6 * audio.SR:
                continue
            fake = load(fakes[int(rng.integers(len(fakes)))])
            res = splice(real, fake, rng)
            if res is None:
                continue
            x, a, b = res
            p = OUT / f"{split}_{made:03d}.wav"
            sf.write(p, x, audio.SR)
            labels.append({"path": str(p.relative_to(ROOT)), "split": split, "speaker": key[1], "fake_start": round(a, 3),
                           "fake_end": round(b, 3), "duration": round(len(x) / audio.SR, 3)})
            made += 1
        print(split, made)
    (OUT / "labels.json").write_text(json.dumps(labels, indent=1))


if __name__ == "__main__":
    main()
