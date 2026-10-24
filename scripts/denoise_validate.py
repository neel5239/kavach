"""Does 'denoise then detect' cause false alarms? 100 real + 100 fake held-out clips with street noise 15 dB,
scored raw and after Demucs vocal isolation. Run with the kavach venv while the app runs on :8320.
Usage: python scripts/denoise_validate.py   -> runs/denoise_validation.json
"""
import csv
import json
import random
import subprocess
import sys
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio  # noqa: E402

OUT = ROOT / "runs" / "denoise_val"


def main():
    rd = lambda f: list(csv.DictReader(open(ROOT / "data/index" / f, encoding="utf-8")))
    itw = [r for r in rd("itw.csv") if r["split"] == "test"]
    rng = random.Random(9)  # dataset sampling only
    rng.shuffle(itw)
    reals = [r["path"] for r in itw if r["label"] == "0"][:60] + [r["path"] for r in rng.sample([r for r in rd("libri.csv") if r["split"] == "test"], 40)]
    fakes = [r["path"] for r in itw if r["label"] == "1"][:60] + [r["path"] for r in rng.sample([r for r in rd("modern.csv") if r["split"] == "test"], 40)]
    (OUT / "in").mkdir(parents=True, exist_ok=True)
    items = []
    nrng = np.random.default_rng(5)
    for lab, paths in ((0, reals), (1, fakes)):
        for k, p in enumerate(paths):
            x, sr = sf.read(ROOT / p, dtype="float32")
            x = audio.center_crop(audio.preprocess(audio.to_mono_16k(x, sr)), 6.0)
            y = audio.add_noise(x, 15.0, nrng)
            name = f"{'real' if lab == 0 else 'fake'}_{k:03d}"
            sf.write(OUT / "in" / f"{name}.wav", y, audio.SR)
            items.append((name, lab))
    files = [str(OUT / "in" / f"{n}.wav") for n, _ in items]
    subprocess.run(["D:/tts-venv/Scripts/python.exe", "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", str(OUT / "den"), *files],
                   check=True, capture_output=True)  # nosec B603 - fixed argv
    c = httpx.Client(timeout=120)
    score = lambda p: c.post("http://127.0.0.1:8320/api/analyze", files={"file": ("a.wav", Path(p).read_bytes(), "audio/wav")}).json()
    rows = []
    for n, lab in items:
        a = score(OUT / "in" / f"{n}.wav")
        b = score(OUT / "den" / "htdemucs" / n / "vocals.wav")
        rows.append({"name": n, "label": lab, "raw": a["verdict"], "raw_score": a["score"], "den": b["verdict"], "den_score": b["score"]})
    def rate(lab, key, v):
        r = [x for x in rows if x["label"] == lab]
        return sum(x[key] == v for x in r) / len(r)
    R = {"n_real": len(reals), "n_fake": len(fakes), "snr_db": 15,
         "raw": {"fake_caught": rate(1, "raw", "FAKE"), "real_false_alarm": rate(0, "raw", "FAKE")},
         "denoised": {"fake_caught": rate(1, "den", "FAKE"), "real_false_alarm": rate(0, "den", "FAKE")}, "rows": rows}
    (ROOT / "runs" / "denoise_validation.json").write_text(json.dumps(R, indent=1))
    print(json.dumps({k: v for k, v in R.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
