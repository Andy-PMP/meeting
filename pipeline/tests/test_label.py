import math

from jsonl import append_jsonl, read_jsonl
from label import (
    cheat_sheet,
    cohen_kappa,
    counts,
    latest_labels,
    make_row,
    relabel_sample,
    remove_last_row,
    todo_ids,
)
from paths import DOCS


def row(id_, label="keep", pass_=1, discarded=False):
    return {"id": id_, "label": label, "discarded": discarded, "note": "", "pass": pass_,
            "labeled_at": "2026-10-22T00:00:00+00:00"}  # fmt: skip


def test_last_row_wins_within_a_pass():
    rows = [row("inv_0001", "keep"), row("inv_0001", "email"), row("inv_0001", "shorter", 2)]
    assert latest_labels(rows, 1)["inv_0001"]["label"] == "email"
    assert latest_labels(rows, 2)["inv_0001"]["label"] == "shorter"


def test_resume_skips_labeled_and_keeps_order():
    done = latest_labels([row("inv_0002")])
    assert todo_ids(["inv_0001", "inv_0002", "inv_0003"], done) == ["inv_0001", "inv_0003"]


def test_counts_separate_discards():
    done = latest_labels([row("a"), row("b", "email"), row("c", None, discarded=True)])
    assert counts(done) == {"keep": 1, "shorter": 0, "email": 1, "discarded": 1}


def test_relabel_sample_is_stable_and_skips_discards():
    pass1 = latest_labels(
        [row(f"inv_{i:04d}") for i in range(100)] + [row("x", None, discarded=True)]
    )
    a = relabel_sample(pass1, 0.1)
    assert a == relabel_sample(pass1, 0.1)
    assert len(a) == 10 and "x" not in a


def test_make_row_for_label_and_discard():
    r = make_row("inv_0001", "2", "hmm", 1)
    assert (r["label"], r["discarded"], r["note"], r["pass"]) == ("shorter", False, "hmm", 1)
    d = make_row("inv_0001", "d", "", 1)
    assert (d["label"], d["discarded"]) == (None, True)


def test_cheat_sheet_reads_the_real_rubric():
    lines = cheat_sheet((DOCS / "rubric.md").read_text(encoding="utf-8"))
    assert len(lines) == 3
    assert lines[0].startswith("1 keep") and "**" not in lines[0]


def test_undo_removes_only_this_sessions_last_row(tmp_path):
    p = tmp_path / "labels.jsonl"
    append_jsonl(p, row("inv_0001"))
    append_jsonl(p, row("inv_0002"))
    assert not remove_last_row(p, "inv_0001")  # not the last row: refuse
    assert remove_last_row(p, "inv_0002")
    assert [r["id"] for r in read_jsonl(p)] == ["inv_0001"]


def test_cohen_kappa():
    a = ["keep", "email", "shorter", "keep"]
    assert cohen_kappa(a, a) == 1
    assert cohen_kappa(["keep", "email"], ["email", "keep"]) < 0
    assert math.isnan(cohen_kappa([], []))
