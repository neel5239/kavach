import numpy as np
import pytest
import torch

from kavach.metrics import eer, three_way
from kavach.model import LayerMixHead, Thresholds, aggregate, cell_scores, verdict_for


def test_eer_perfect_and_random():
    y = np.array([0] * 50 + [1] * 50)
    assert eer(np.r_[np.zeros(50), np.ones(50)], y)[0] == 0.0
    rng = np.random.default_rng(0)
    e, _ = eer(rng.random(20000), np.r_[np.zeros(10000), np.ones(10000)].astype(int))
    assert 0.47 < e < 0.53


def test_eer_inverted_scores_is_high():
    y = np.array([0] * 50 + [1] * 50)
    assert eer(np.r_[np.ones(50), np.zeros(50)], y)[0] == 1.0


def test_eer_needs_two_classes():
    with pytest.raises(ValueError):
        eer(np.ones(5), np.ones(5, int))


def test_three_way_counts():
    s = np.array([0.1, 0.5, 0.9, 0.95])
    y = np.array([0, 1, 1, 0])
    r = three_way(s, y, 0.3, 0.8)
    assert r["not_sure_rate"] == 0.25 and r["real_called_fake"] == 0.5


TH = Thresholds(real_below=0.3, fake_above=0.7, eer_threshold=0.5)


@pytest.mark.parametrize("score,expect", [(0.1, "REAL"), (0.5, "NOT SURE"), (0.9, "FAKE")])
def test_verdict(score, expect):
    assert verdict_for(score, TH, speech_s=3.0) == expect


def test_verdict_short_speech_is_unsure():
    assert verdict_for(0.99, TH, speech_s=0.5) == "NOT SURE"


def test_aggregate_keeps_fake_segment():
    assert aggregate([0.05, 0.05, 0.05, 0.95]) > 0.45


def test_head_shapes_and_weights_sum_to_one():
    h = LayerMixHead()
    out = h(torch.randn(3, 25, 1024))
    assert out.shape == (3,)
    assert torch.isclose(h.layer_weights().sum(), torch.tensor(1.0))


def test_cell_scores_half_second_cells():
    wins = [(0.0, 1.0, 0.1), (0.5, 1.5, 0.9), (1.0, 2.0, 0.9)]
    cells = cell_scores(wins, 2.0)
    assert [c["start"] for c in cells] == [0.0, 0.5, 1.0, 1.5]
    assert cells[0]["score"] == 0.1 and cells[3]["score"] == 0.9
    assert abs(cells[1]["score"] - 0.5) < 1e-6
