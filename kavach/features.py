"""Frozen XLS-R feature extractor: mean-pooled hidden states of every layer."""
from __future__ import annotations

import os

import numpy as np
import torch

MODEL_ID = os.environ.get("KAVACH_SSL", "facebook/wav2vec2-xls-r-300m")
REVISION = "1a640f32ac3e39899438a2931f9924c02f080a54"  # pinned commit: weights cannot change silently
N_LAYERS = 25  # CNN/embedding output + 24 transformer layers
DIM = 1024
MIN_SAMPLES = 8000  # 0.5 s; shorter input is padded by repetition


def _local_path(model_id: str) -> str:
    """Prefer the cached snapshot so the app works fully offline (venue internet is unreliable)."""
    if os.path.isdir(model_id):
        return model_id
    bundled = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "xlsr-300m")
    if os.path.isfile(os.path.join(bundled, "config.json")):
        return bundled  # weights shipped inside the project zip
    try:
        from huggingface_hub import snapshot_download
        return snapshot_download(model_id, revision=REVISION, local_files_only=True)
    except Exception:
        return model_id


class Extractor:
    def __init__(self, device: str | None = None, fp16: bool = True):
        from transformers import Wav2Vec2Model

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = torch.float16 if (fp16 and self.device == "cuda") else torch.float32
        model = Wav2Vec2Model.from_pretrained(_local_path(MODEL_ID), revision=REVISION)  # nosec B615 - revision pinned
        self.model = model.to(self.device, dtype=self.dtype).eval()
        for prm in self.model.parameters():
            prm.requires_grad_(False)

    @torch.inference_mode()
    def __call__(self, wav: np.ndarray) -> np.ndarray:
        """wav: 16 kHz mono float32 -> (25, 1024) float32 of per-layer time-mean."""
        x = np.asarray(wav, dtype=np.float32)
        if len(x) < MIN_SAMPLES:
            reps = int(np.ceil(MIN_SAMPLES / max(len(x), 1)))
            x = np.tile(x, reps)[:MIN_SAMPLES] if len(x) else np.zeros(MIN_SAMPLES, np.float32)
        x = (x - x.mean()) / (x.std() + 1e-7)  # XLS-R expects per-utterance normalisation
        t = torch.from_numpy(x).to(self.device, dtype=self.dtype)[None]
        out = self.model(t, output_hidden_states=True)
        hs = torch.stack(out.hidden_states, dim=1)[0]  # (25, T, 1024)
        return hs.float().mean(dim=1).cpu().numpy()

    def batch(self, wavs: list[np.ndarray]) -> np.ndarray:
        return np.stack([self(w) for w in wavs])
