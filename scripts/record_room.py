"""Record a real speaker -> room -> microphone dataset on THIS laptop, to train Kavach on the user's actual chain.

Plays real and fake clips through the default speaker and records them with the default microphone at the
same time (sounddevice.playrec). Speakers stay in their original split: train / cal / test never mix.
Usage: python scripts/record_room.py [--n-train 150] [--n-cal 30] [--n-test 50] [--check]
Writes data/room/<split>_<k>.wav and data/index/room.csv
"""
import argparse
import csv
import random
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio  # noqa: E402

OUT = ROOT / "data" / "room"
FS = 48000


def pool():
    rd = lambda f: list(csv.DictReader(open(ROOT / "data/index" / f, encoding="utf-8")))
    itw, libri, modern = rd("itw.csv"), rd("libri.csv"), rd("modern.csv")
    P = {}
    for sp in ("train", "cal", "test"):
        real = [(r["path"], "itw_real") for r in itw if r["split"] == sp and r["label"] == "0"]
        real += [(r["path"], "libri") for r in libri if r["split"] == sp]
        fake = [(r["path"], "itw_fake") for r in itw if r["split"] == sp and r["label"] == "1"]
        fake += [(r["path"], r["generator"]) for r in modern if r["split"] == sp]
        P[sp] = (real, fake)
    return P


def play_rec(x16, gain):
    x = resample_poly(x16, 3, 1).astype(np.float32)  # 16 k -> 48 k
    x = x / (np.max(np.abs(x)) + 1e-9) * gain
    pad = np.zeros(int(0.35 * FS), np.float32)
    y = sd.playrec(np.concatenate([pad, x, pad])[:, None], samplerate=FS, channels=1, dtype="float32", blocking=True)[:, 0]
    return resample_poly(y, 1, 3).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-train", type=int, default=150)
    ap.add_argument("--n-cal", type=int, default=30)
    ap.add_argument("--n-test", type=int, default=50)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    P = pool()
    rng = random.Random(77)  # dataset sampling only
    nrng = np.random.default_rng(77)
    jobs = []
    for sp, n in (("train", a.n_train), ("cal", a.n_cal), ("test", a.n_test)):
        real, fake = P[sp]
        rng.shuffle(real)
        rng.shuffle(fake)
        # balance fake sources: half In-the-Wild fakes, half modern neural TTS when available
        mod = [f for f in fake if f[1] != "itw_fake"]
        itwf = [f for f in fake if f[1] == "itw_fake"]
        fk = (mod[: n // 2] + itwf)[:n] if mod else itwf[:n]
        jobs += [(sp, 0, p, g) for p, g in real[:n]] + [(sp, 1, p, g) for p, g in fk]
    rng.shuffle(jobs)
    if a.check:
        jobs = jobs[:5]
    print("input:", sd.query_devices(kind="input")["name"], "| output:", sd.query_devices(kind="output")["name"], "| clips", len(jobs), flush=True)
    idx = ROOT / "data" / "index" / ("room_check.csv" if a.check else "room.csv")
    with idx.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "speaker", "label", "split", "generator", "lang"])
        t0 = time.time()
        for k, (sp, lab, p, g) in enumerate(jobs):
            x, sr = sf.read(ROOT / p, dtype="float32")
            x = audio.center_crop(audio.preprocess(audio.to_mono_16k(x, sr)), 4.5)
            if len(x) < audio.SR:
                continue
            y = play_rec(x, float(nrng.uniform(0.35, 0.9)))
            out = OUT / f"{sp}_{k:04d}_{lab}.wav"
            sf.write(out, y, audio.SR)
            w.writerow([str(out.relative_to(ROOT)), Path(p).stem, lab, sp, "room_" + g, "en"])
            f.flush()
            if k % 20 == 0 or a.check:
                lvl = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-9)
                print(f"{k}/{len(jobs)} {sp} label={lab} {g:10s} rec level {lvl:.1f} dB  {(time.time() - t0) / 60:.1f} min", flush=True)
    print("done", idx)


if __name__ == "__main__":
    main()
