from import_test import parse

SOURCE = """My scratch notes up here are ignored.

=== keep
note: borderline, 9 people
Subject: Pick the launch date
We need to choose between the 3rd and the 10th.

=== EMAIL

FYI: the new expense tool goes live Monday.
"""


def test_parse_assigns_ids_labels_and_notes():
    rows, errors = parse(SOURCE)
    assert errors == []
    assert rows == [
        {
            "id": "test_001",
            "text": "Subject: Pick the launch date\n"
            "We need to choose between the 3rd and the 10th.",
            "label": "keep",
            "note": "borderline, 9 people",
        },
        {
            "id": "test_002",
            "text": "FYI: the new expense tool goes live Monday.",
            "label": "email",
            "note": "",
        },
    ]


def test_parse_reports_bad_label_and_empty_invite():
    rows, errors = parse("=== maybe\nsome text\n\n=== keep\n\n=== shorter\nreal one\n")
    assert len(errors) == 2
    assert "'maybe'" in errors[0] and "empty invite" in errors[1]
    assert [r["id"] for r in rows] == ["test_001"]
