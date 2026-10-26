"""Embedding windowing/pooling and the CV helpers, without downloading any model (CI-safe)."""

import numpy as np

from embed import _pool, windows
from labels import LABELS
from train import FOLDS, REPEATS, Dataset, cross_validate, fit_predict_linear, splits


def test_windows_wrap_every_chunk_in_cls_sep():
    ids = list(range(10, 20))  # 10 content tokens
    w = windows(ids, cls_id=1, sep_id=2, max_tokens=6)  # 4 content tokens per window
    assert w == [[1, 10, 11, 12, 13, 2], [1, 14, 15, 16, 17, 2], [1, 18, 19, 2]]
    assert windows([], 1, 2, 6) == [[1, 2]]  # empty text still gets one window


def test_mean_pooling_ignores_padding_and_cls_takes_first():
    hidden = np.array([[[1.0, 1.0], [3.0, 3.0], [100.0, 100.0]]])
    mask = np.array([[1, 1, 0]])
    assert np.allclose(_pool(hidden, mask, "mean"), [[2.0, 2.0]])
    assert np.allclose(_pool(hidden, mask, "cls"), [[1.0, 1.0]])


def test_splits_are_deterministic_and_cover_every_item_once_per_repeat():
    y = np.array([0, 1, 2] * 20)
    a = [te.tolist() for _, te in splits(y)]
    assert a == [te.tolist() for _, te in splits(y)]
    assert len(a) == FOLDS * REPEATS
    for r in range(REPEATS):
        seen = sorted(i for te in a[r * FOLDS : (r + 1) * FOLDS] for i in te)
        assert seen == list(range(len(y)))


def test_linear_model_learns_an_obvious_signal():
    words = {
        0: "decide debate together",
        1: "too long padded meeting",
        2: "fyi update announcement",
    }
    texts = [f"{words[k]} item {i}" for i in range(20) for k in range(3)]
    y = np.array([k for _ in range(20) for k in range(3)])
    ds = Dataset([f"x{i}" for i in range(len(y))], texts, y, np.zeros((len(y), 1)))
    res = cross_validate(ds, lambda tr, te: fit_predict_linear(ds, tr, te, C=10, cw=None))
    assert res["macro_f1"] > 0.95
    assert set(res["per_class_f1"]) == set(LABELS)
