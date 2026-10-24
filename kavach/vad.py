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


def speech_only(wav: np.ndarray) -> tuple[np.ndarray, float]:
    """Keep only the spoken parts of a window (pauses add noise to the score)."""
    try:
        import torch
        from silero_vad import get_speech_timestamps
        x = torch.from_numpy(np.ascontiguousarray(wav, dtype=np.float32))
        ts = get_speech_timestamps(x, _get(), sampling_rate=audio.SR, threshold=0.5, min_speech_duration_ms=250, speech_pad_ms=60)
        if not ts:
            return wav[:0], 0.0
        parts = [wav[t["start"]: t["end"]] for t in ts]
        return np.concatenate(parts), sum(len(q) for q in parts) / audio.SR
    except ImportError:
        return wav, speech_seconds(wav)
