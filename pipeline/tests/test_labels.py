import pytest

from labels import DISPLAY, LABELS, label_index


def test_label_order_is_fixed():
    assert LABELS == ("keep", "shorter", "email")


def test_every_label_has_display_text():
    assert set(DISPLAY) == set(LABELS)


def test_label_index_round_trips():
    assert [label_index(lab) for lab in LABELS] == [0, 1, 2]


def test_label_index_rejects_unknown():
    with pytest.raises(ValueError):
        label_index("cancel")
