import io
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SR = 16000


def tone(seconds=3.0, freq=220.0, amp=0.3, lead_silence=0.0, tail_silence=0.0, sr=SR):
    t = np.arange(int(seconds * sr)) / sr
    x = amp * np.sin(2 * np.pi * freq * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
    z1, z2 = np.zeros(int(lead_silence * sr)), np.zeros(int(tail_silence * sr))
    return np.concatenate([z1, x, z2]).astype(np.float32)


def wav_bytes(x, sr=SR, fmt="WAV"):
    buf = io.BytesIO()
    sf.write(buf, x, sr, format=fmt)
    return buf.getvalue()


@pytest.fixture
def speechlike():
    return tone(3.0)
