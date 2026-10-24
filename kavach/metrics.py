"""Evaluation metrics."""
from __future__ import annotations

import numpy as np


def eer(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Equal error rate. labels: 1 = fake, 0 = real; higher score = more fake.

    Returns (eer, threshold) where false-accept rate (fake called real) equals
    false-reject rate (real called fake).
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    if labels.min() == labels.max():
        raise ValueError("EER needs both classes")
    order = np.argsort(scores)
    s, y = scores[order], labels[order]
    n_fake, n_real = y.sum(), (1 - y).sum()
    # threshold just above s[k]: everything <= s[k] called real
    fake_called_real = np.cumsum(y) / n_fake          # FAR
    real_called_fake = 1 - np.cumsum(1 - y) / n_real  # FRR
    k = int(np.argmin(np.abs(fake_called_real - real_called_fake)))
    return float((fake_called_real[k] + real_called_fake[k]) / 2), float(s[k])


def threshold_at_rate(scores: np.ndarray, labels: np.ndarray, target: float, side: str) -> float:
    """side='real': threshold below which at most `target` of fakes fall (fake called real).
    side='fake': threshold above which at most `target` of reals fall (real called fake)."""
    scores, labels = np.asarray(scores), np.asarray(labels)
    if side == "real":
        return float(np.quantile(scores[labels == 1], target))
    return float(np.quantile(scores[labels == 0], 1 - target))


def three_way(scores: np.ndarray, labels: np.ndarray, lo: float, hi: float) -> dict:
    scores, labels = np.asarray(scores), np.asarray(labels)
    real, fake = scores < lo, scores > hi
    unsure = ~(real | fake)
    decided = ~unsure
    correct = (fake & (labels == 1)) | (real & (labels == 0))
    return {
        "not_sure_rate": float(unsure.mean()),
        "accuracy_when_decided": float(correct[decided].mean()) if decided.any() else None,
        "fake_called_real": float((real & (labels == 1)).sum() / max(1, (labels == 1).sum())),
        "real_called_fake": float((fake & (labels == 0)).sum() / max(1, (labels == 0).sum())),
    }
