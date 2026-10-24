"""Layer-mixing classifier head, verdict logic and the end-to-end Detector."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import torch
from torch import nn

from . import audio
from .features import DIM, N_LAYERS

MIN_SPEECH_S = 1.0
SHIELD = True
SHIELD_FAKE_ABOVE = 0.90  # denoised score needed for a red FAKE (validation: 4% false alarms on noisy real speech)


class LayerMixHead(nn.Module):
    """Softmax-weighted sum of layer vectors -> LayerNorm -> small MLP -> fake logit."""

    def __init__(self, n_layers: int = N_LAYERS, dim: int = DIM, hidden: int = 128, dropout: float = 0.3):
        super().__init__()
        self.layer_logits = nn.Parameter(torch.zeros(n_layers))
        self.norm = nn.LayerNorm(dim)
        self.mlp = nn.Sequential(nn.Dropout(dropout), nn.Linear(dim, hidden), nn.GELU(), nn.Dropout(dropout), nn.Linear(hidden, 1))

    def layer_weights(self) -> torch.Tensor:
        return torch.softmax(self.layer_logits, dim=0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # x: (B, L, D)
        mixed = (x * self.layer_weights()[None, :, None]).sum(dim=1)
        return self.mlp(self.norm(mixed)).squeeze(-1)


@dataclass
class Thresholds:
    real_below: float  # score < real_below -> REAL
    fake_above: float  # score > fake_above -> FAKE ; in between -> NOT SURE
    eer_threshold: float


def verdict_for(score: float, th: Thresholds, speech_s: float) -> str:
    if speech_s < MIN_SPEECH_S:
        return "NOT SURE"
    if score > th.fake_above:
        return "FAKE"
    if score < th.real_below:
        return "REAL"
    return "NOT SURE"


def aggregate(window_scores: list[float]) -> float:
    """Clip score = mean of the top half of window scores (a fake segment should not be averaged away)."""
    s = np.sort(np.asarray(window_scores, dtype=np.float64))[::-1]
    k = max(1, int(np.ceil(len(s) / 2)))
    return float(s[:k].mean())


def save_head(path: Path, head: LayerMixHead, th: Thresholds, meta: dict) -> None:
    path.mkdir(parents=True, exist_ok=True)
    torch.save(head.state_dict(), path / "head.pt")
    (path / "config.json").write_text(json.dumps({"thresholds": asdict(th), **meta}, indent=2))


CELL_S = 0.5  # localisation resolution
SEG_WIN_S = 1.0


def cell_scores(window_scores: list[tuple[float, float, float]], duration: float) -> list[dict]:
    """Mean score of all windows covering each 0.5 s cell."""
    n = max(1, int(np.ceil(duration / CELL_S - 1e-6)))
    out = []
    for c in range(n):
        a, b = c * CELL_S, min(duration, (c + 1) * CELL_S)
        cov = [s for (ws, we, s) in window_scores if ws < b and we > a]
        out.append({"start": round(a, 2), "end": round(b, 2), "score": round(float(np.mean(cov)) if cov else 0.0, 4)})
    return out


def load_head(model_dir: Path) -> tuple[LayerMixHead, dict]:
    cfg = json.loads((model_dir / "config.json").read_text())
    head = LayerMixHead(hidden=cfg.get("hidden", 128))
    head.load_state_dict(torch.load(model_dir / "head.pt", map_location="cpu", weights_only=True))
    head.eval()
    return head, cfg


class Detector:
    def __init__(self, model_dir: str | Path, device: str | None = None):
        from .features import Extractor

        model_dir = Path(model_dir)
        cfg = json.loads((model_dir / "config.json").read_text())
        self.config = cfg
        self.th = Thresholds(**cfg["thresholds"])
        self.head = LayerMixHead(hidden=cfg.get("hidden", 128))
        self.head.load_state_dict(torch.load(model_dir / "head.pt", map_location="cpu", weights_only=True))
        self.head.eval()
        self.extractor = Extractor(device=device)
        seg_dir = model_dir.parent / (model_dir.name + "_seg")
        self.seg = load_head(seg_dir) if (seg_dir / "head.pt").exists() else None

    @torch.inference_mode()
    def score_features(self, feats: np.ndarray) -> np.ndarray:
        logits = self.head(torch.from_numpy(np.asarray(feats, dtype=np.float32)))
        return torch.sigmoid(logits).numpy()

    @torch.inference_mode()
    def score_window(self, wav: np.ndarray) -> float:
        """Score one short window (used by streaming mode)."""
        f = self.extractor(audio.normalise(wav))
        return float(torch.sigmoid(self.head(torch.from_numpy(f[None].astype(np.float32))))[0])

    @torch.inference_mode()
    def localize(self, wav: np.ndarray) -> dict | None:
        """Per-0.5 s synthetic score on the loudness-normalised (untrimmed) timeline."""
        if self.seg is None or len(wav) < audio.SR:
            return None
        head, cfg = self.seg
        x = audio.normalise(wav)
        wins = audio.windows(x, SEG_WIN_S, CELL_S)
        feats = self.extractor.batch([w for _, _, w in wins])
        sc = torch.sigmoid(head(torch.from_numpy(feats.astype(np.float32)))).numpy().tolist()
        cells = cell_scores([(a, b, s) for (a, b, _), s in zip(wins, sc)], len(x) / audio.SR)
        thr = cfg.get("cell_threshold", 0.5)
        return {"cell_s": CELL_S, "threshold": thr, "cells": cells,
                "synthetic_seconds": round(sum(c["end"] - c["start"] for c in cells if c["score"] > thr), 2)}

    def analyze(self, wav: np.ndarray, orig_duration: float | None = None) -> dict:
        t0 = time.perf_counter()
        duration = orig_duration if orig_duration is not None else len(wav) / audio.SR
        clean = audio.preprocess(wav)
        speech_s = audio.speech_seconds(clean)
        if speech_s < 0.3:
            return {"verdict": "NOT SURE", "score": None, "confidence": 0.0, "duration_s": round(duration, 2),
                    "speech_s": round(speech_s, 2), "windows": [], "reason": "No speech found in the clip.",
                    "thresholds": asdict(self.th), "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
        wins = audio.windows(clean)
        feats = self.extractor.batch([w for _, _, w in wins])
        scores = self.score_features(feats).tolist()
        clip = aggregate(scores)
        v = verdict_for(clip, self.th, speech_s)
        shield, reason = None, None
        if SHIELD and v != "FAKE":
            from . import denoise as dn
            snr = dn.estimate_snr_db(clean)
            if snr < dn.NOISY_BELOW_DB:
                try:
                    dclean = audio.preprocess(dn.denoise(wav))
                    dw = audio.windows(dclean)
                    dscore = aggregate(self.score_features(self.extractor.batch([w for _, _, w in dw])).tolist())
                except Exception as e:  # shield is best-effort; never break the main verdict
                    dscore, reason = None, None
                    shield = {"active": False, "error": type(e).__name__}
                else:
                    shield = {"active": True, "snr_db": round(snr, 1), "denoised_score": round(dscore, 4)}
                    if dscore > SHIELD_FAKE_ABOVE:
                        v, clip = "FAKE", max(clip, dscore)
                        reason = "Clone fingerprint found after removing background noise."
                    elif dscore > self.th.fake_above and v == "REAL":
                        v = "NOT SURE"
                        reason = "Possible clone hidden by background noise. Verify another way."
        if v == "FAKE":
            conf = (clip - self.th.fake_above) / max(1e-6, 1 - self.th.fake_above)
        elif v == "REAL":
            conf = (self.th.real_below - clip) / max(1e-6, self.th.real_below)
        else:
            conf = 0.0
        if speech_s < MIN_SPEECH_S:
            reason = "Less than 1 second of speech. Try a longer clip."
        return {
            "verdict": v,
            "score": round(clip, 4),
            "confidence": round(float(np.clip(0.5 + 0.5 * conf, 0, 1)) if v != "NOT SURE" else 0.0, 3),
            "duration_s": round(duration, 2),
            "speech_s": round(speech_s, 2),
            "windows": [{"start": round(a, 2), "end": round(b, 2), "score": round(s, 4)} for (a, b, _), s in zip(wins, scores)],
            "reason": reason,
            "thresholds": asdict(self.th),
            "segments": self.localize(wav),
            "noise_shield": shield,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
