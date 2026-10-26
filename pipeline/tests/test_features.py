import pytest

from clean import mask_boilerplate
from features import (
    agenda_items,
    parse_attendees,
    parse_duration,
    structure,
    structure_names,
    structure_vector,
    tokenize,
    tokens,
)


def test_tokens_lowercase_and_normalize_times_and_numbers():
    assert tokens("Quick SYNC at 10:30 am, 30min, room 210?!") == [
        "quick", "sync", "at", "<time>", "30min", "room", "<num>", "?", "!",
    ]  # fmt: skip


def test_token_offsets_point_into_the_text():
    text = "Decide: go/no-go"
    for tok, start, end in tokenize(text):
        assert text[start:end].lower() in (tok, "go")


def test_token_offsets_survive_masking():
    text = "Meeting ID: 234 567 890\nDecide the vendor"
    masked = mask_boilerplate(text)
    spans = [(t, text[s:e]) for t, s, e in tokenize(masked)]
    assert spans == [("decide", "Decide"), ("the", "the"), ("vendor", "vendor")]


@pytest.mark.parametrize(
    "text, minutes",
    [
        ("When: Oct 28, 2026 10:00 AM-10:30 AM Eastern", 30),
        ("Thu 10:00-11:00", 60),
        ("Friday 12-12:30 PM", 30),
        ("Wed 2–3pm, room 4", 60),
        ("11am - 1", 120),
        ("from 10:00 AM to 11:30 AM", 90),
        ("Quick sync | 15 min | 2 attendees", 15),
        ("Kickoff, 1.5 hrs", 90),
        ("grabbing an hour with you", 60),
        ("Tuesday, Oct 28, 2026 10:00 AM | 60 minutes", 60),
    ],
)
def test_durations(text, minutes):
    assert parse_duration(text) == minutes


@pytest.mark.parametrize(
    "text",
    [
        "Time: Oct 28, 2026 10:00 AM Eastern Time",  # Zoom: start time only
        "LUT mixup on days 14-16, see slides 4-11",  # not times
        "the pipeline dropped UTMs for ~36 hrs",  # longer than any meeting
        "",
    ],
)
def test_unknown_durations(text):
    assert parse_duration(text) is None


@pytest.mark.parametrize(
    "text, count, group",
    [
        ("Quick sync | 15 min | 2 attendees", 2, False),
        ("All 40, 1hr Thurs 7am", 40, False),
        ("there will be eight of us", 8, False),
        ("Required: Ann Lee; Bo Kim; Cy Diaz\nOptional: Dee Ray", 4, False),
        ("To: Merchandising, Store Ops, Regional Leads (12)", 12, False),
        ("Required: corporate-distro@example.com and 111 others", 112, True),
        ("Guests\na@example.com\nb@example.com\nc@example.com\n\nnext", 3, False),
        ("Whole team, please join", None, True),
        ("Can we chat about the font?", None, False),
    ],
)
def test_attendees(text, count, group):
    assert parse_attendees(text) == (count, group)


def test_forwarded_to_line_does_not_hide_the_real_list():
    text = "To: Laurin Klein\n\nRequired: A B; C D; E F; G H; I J"
    assert parse_attendees(text)[0] == 5


def test_agenda_items_in_common_styles():
    text = "Agenda:\n1. Budget\n2) Hiring\n3 - Risks\n- Vendors\n* Q&A\n• Wrap-up\nNot an item"
    assert agenda_items(text) == 6


def test_structure_buckets_and_keywords():
    s = structure("Decide on vendor | 60 min | 12 attendees\n1. Quotes\n2. Pick one")
    assert s["duration"] == 60 and s["attendees"] == 12 and s["agenda_items"] == 2
    assert s["minutes_per_item"] == 30
    for name in ["duration<=60", "attendees<=25", "agenda_items<=3", "min_per_item<=30",
                 "kw:decision"]:  # fmt: skip
        assert name in s["active"]


def test_unknowns_are_explicit():
    s = structure("Topic: Q1 hiring plan\nTime: Oct 28, 2026 10:00 AM")
    assert {
        "duration=unknown",
        "attendees=unknown",
        "min_per_item=unknown",
        "agenda_items=0",
    } <= set(s["active"])


def test_vector_is_one_hot_over_fixed_names():
    v = structure_vector("Status update, 30 min, 5 people")
    names = structure_names()
    assert len(v) == len(names) and set(v) <= {0.0, 1.0}
    active = {n for n, x in zip(names, v, strict=True) if x}
    # exactly one bucket per bucketed family
    for family in ["duration", "attendees", "agenda_items", "min_per_item"]:
        bucket = [n for n in active if n.startswith(family) and n != "attendees=group"]
        assert len(bucket) == 1, family
