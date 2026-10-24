"""Speech detection for live mode (Silero VAD, MIT). Background noise and silence are never judged as a voice.
Falls back to the simple energy/flatness detector in audio.py if Silero is not installed."""
from __future__ import annotations

import threading

import numpy as np

from . import audio

_model = None
_lock = threading.Lock()


def _get():
    global _model
    with _lock:
        if _model is None:
            from silero_vad import load_silero_vad
            _model = load_silero_vad()
    return _model


def speech_seconds(wav: np.ndarray) -> float:
    """Seconds of speech in a 16 kHz mono window."""
    try:
        import torch
        from silero_vad import get_speech_timestamps
        x = torch.from_numpy(np.ascontiguousarray(wav, dtype=np.float32))
        ts = get_speech_timestamps(x, _get(), sampling_rate=audio.SR, threshold=0.5, min_speech_duration_ms=250)
        return sum(t["end"] - t["start"] for t in ts) / audio.SR
    except ImportError:
        act = audio.speech_activity(wav)
        return act["ratio"] * len(wav) / audio.SR if act["speech"] else 0.0
