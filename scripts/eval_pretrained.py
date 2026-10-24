"""Compare ready-made open-source deepfake-audio detectors (Hugging Face) with Kavach on the same clips:
the user's own GPT/Gemini recordings, known real voices and known fakes. Prints P(fake) per clip.
Usage: python scripts/eval_pretrained.py"""
import csv
import glob
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kavach import audio  # noqa: E402

MODELS = ["mo-thecreator/Deepfake-audio-detection", "MelodyMachine/Deepfake-audio-detection-V2",
          ] + (["Gustking/wav2vec2-large-xlsr-deepfake-audio-classification"] if "--all" in sys.argv else [])
dev = "cuda" if torch.cuda.is_available() else "cpu"


def fake_index(cfg):
    for i, lab in cfg.id2label.items():
        if any(k in lab.lower() for k in ("fake", "spoof", "synthetic", "ai")):
            return int(i)
    return 1


def clips():
    cap = sorted(glob.glob(str(ROOT / "data/user_tests/captures/*.wav")))
    out = [("AI(user)", p) for p in cap]
    rows = list(csv.DictReader(open(ROOT / "data/index/itw.csv", encoding="utf-8")))
    out += [("real", r["path"]) for r in rows if r["split"] == "test" and r["label"] == "0"][400:410]
    out += [("real", r["path"]) for r in csv.DictReader(open(ROOT / "data/index/libri.csv", encoding="utf-8")) if r["split"] == "test"][300:305]
    out += [("fake", r["path"]) for r in rows if r["split"] == "test" and r["label"] == "1"][400:405]
    out += [("fake", r["path"]) for r in csv.DictReader(open(ROOT / "data/index/modern.csv", encoding="utf-8")) if r["split"] == "test"][:8]
    return out


def main():
    data = []
    for lab, p in clips():
        x, sr = sf.read(ROOT / p, dtype="float32")
        data.append((lab, Path(p).name, audio.center_crop(audio.normalise(audio.to_mono_16k(x, sr)), 8.0)))
    res = {}
    for name in MODELS:
        try:
            fe = AutoFeatureExtractor.from_pretrained(name)
            m = AutoModelForAudioClassification.from_pretrained(name).to(dev).eval()
        except Exception as e:
            print("skip", name, type(e).__name__, e)
            continue
        fi = fake_index(m.config)
        sc = []
        for lab, n, x in data:
            inp = fe(x, sampling_rate=16000, return_tensors="pt")
            with torch.no_grad():
                pr = torch.softmax(m(**{k: v.to(dev) for k, v in inp.items()}).logits, -1)[0, fi].item()
            sc.append(pr)
        res[name] = sc
        del m
        torch.cuda.empty_cache()
        labs = np.array([d[0] for d in data]); s = np.array(sc)
        print(f"\n{name}  labels={m.config.id2label if False else ''}")
        for g in ("AI(user)", "real", "fake"):
            v = s[labs == g]
            print(f"  {g:9s} n={len(v):2d}  P(fake) mean={v.mean():.2f}  >0.5: {(v > 0.5).sum()}/{len(v)}  {np.round(v, 2).tolist() if g == 'AI(user)' else ''}")
    (ROOT / "runs" / "pretrained_compare.json").write_text(json.dumps({"clips": [(d[0], d[1]) for d in data], "scores": res}, indent=1))


if __name__ == "__main__":
    main()
