"""Noise shield: background noise hides clone fingerprints, so noisy clips are also scored after
Demucs vocal isolation (htdemucs). Model weights are bundled in models/torch for offline use."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from . import audio

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("TORCH_HOME", str(ROOT / "models" / "torch"))

NOISY_BELOW_DB = 24.0  # calibrated on held-out clips: catches all 15 dB noisy clips

_model = None


def estimate_snr_db(wav: np.ndarray, frame_ms: int = 30) -> float:
    """Rough SNR: loud-frame level minus quiet-frame level (speech has pauses; noise fills them)."""
    n = int(audio.SR * frame_ms / 1000)
    k = len(wav) // n
    if k < 10:
        return 99.0
    e = 10 * np.log10(np.mean(wav[: k * n].reshape(k, n) ** 2, axis=1) + 1e-12)
    return float(np.percentile(e, 95) - np.percentile(e, 10))


def _get():
    global _model
    if _model is None:
        import torch
        from demucs.pretrained import get_model

        _model = get_model("htdemucs").eval()
        _model.to("cuda" if torch.cuda.is_available() else "cpu")
    return _model


def denoise(wav: np.ndarray) -> np.ndarray:
    """16 kHz mono in, vocals-only 16 kHz mono out."""
    import torch
    from demucs.apply import apply_model

    m = _get()
    x = resample_poly(wav, 441, 160).astype(np.float32)
    t = torch.from_numpy(np.stack([x, x]))[None].to(next(m.parameters()).device)
    with torch.inference_mode():
        out = apply_model(m, t, split=True, overlap=0.1, progress=False)[0]
    v = out[m.sources.index("vocals")].mean(0).cpu().numpy()
    y = resample_poly(v, 160, 441).astype(np.float32)[: len(wav)]
    return audio.normalise(y)
