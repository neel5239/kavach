"""Second opinion for CLEAN / direct audio: mo-thecreator/Deepfake-audio-detection (open-source wav2vec2 classifier).
Measured here on held-out clips: clean audio 0% false alarms, 97% fakes caught; through a speaker into a mic it
flags 57% of real voices, so it is only used for upload / computer-audio / simulated paths, never for the mic."""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "models" / "second_opinion"
HUB_ID = "mo-thecreator/Deepfake-audio-detection"
_m = None
_lock = threading.Lock()


def _get():
    global _m
    with _lock:
        if _m is None:
            import torch
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
            src = str(LOCAL) if (LOCAL / "config.json").exists() else HUB_ID
            fe = AutoFeatureExtractor.from_pretrained(src)
            model = AutoModelForAudioClassification.from_pretrained(src).eval()
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            model.to(dev)
            fi = [int(i) for i, lab in model.config.id2label.items() if "fake" in lab.lower()][0]
            _m = (fe, model, dev, fi)
    return _m


def p_fake(wav16k: np.ndarray) -> float | None:
    try:
        import torch
        fe, model, dev, fi = _get()
        x = np.asarray(wav16k, dtype=np.float32)[: 16000 * 10]
        inp = fe(x, sampling_rate=16000, return_tensors="pt")
        with torch.inference_mode():
            return float(torch.softmax(model(**{k: v.to(dev) for k, v in inp.items()}).logits, -1)[0, fi])
    except Exception:
        return None
