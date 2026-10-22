import pytest

from clean import mask_boilerplate, masked_fraction
from dedup import find_duplicates

TEAMS = """________________________________________________________________________________
Microsoft Teams meeting
Join on your computer, mobile app or room device
Click here to join the meeting
Meeting ID: 284 551 903 117
Passcode: Lh7xQ2
Or call in (audio only)
+1 555-0148,,62019384#   United States
Phone Conference ID: 620 193 84#
Find a local number | Reset PIN
Brightgate & Sons Parent Association | Learn More | Meeting options
________________________________________________________________________________"""

ZOOM = """Join Zoom Meeting
https://zoom.us/j/98765432100?pwd=abc
Meeting ID: 987 6543 2100
Passcode: 445566
One tap mobile
+16465588656,,98765432100# US (New York)
Dial by your location"""

MEET = """Join with Google Meet: meet.google.com/qrx-tbna-wpe
Join by phone: +1 555-0199 PIN: 123 456 789#"""

FORWARD = """Sorry, forwarding in case this got missed?? -Nadia

---------- Forwarded message ----------
From: Greg Pruitt <greg@example.com>
Sent: Monday 9:14 AM
Cc: Andre Iversen
Subject: Retro: Q3 matter
To: Litigation team (9)
Date: Wednesday, 2:00-2:45pm"""


def visible(text: str) -> list[str]:
    return [ln.strip() for ln in mask_boilerplate(text).split("\n") if ln.strip()]


@pytest.mark.parametrize("block", [TEAMS, ZOOM, MEET])
def test_join_blocks_disappear_entirely(block):
    assert visible(block) == []


def test_forwarding_keeps_note_subject_recipients_and_time():
    assert visible(FORWARD) == [
        "Sorry, forwarding in case this got missed?? -Nadia",
        "Subject: Retro: Q3 matter",
        "To: Litigation team (9)",
        "Date: Wednesday, 2:00-2:45pm",
    ]


def test_agenda_between_rule_lines_survives():
    text = (
        "Gala retro\n"
        + "_" * 40
        + "\n- 9 attendees: Rafael + committee\n* agenda: numbers\n"
        + "_" * 40
    )
    assert visible(text) == ["Gala retro", "- 9 attendees: Rafael + committee", "* agenda: numbers"]


def test_inline_links_codes_and_dial_strings_are_masked_in_place():
    line = "Decision on hiring (Rhys, Cleo) - see [link], PIN 1234#, or +1 555-0142,,8831#"
    assert mask_boilerplate(line).split() == [
        "Decision",
        "on",
        "hiring",
        "(Rhys,",
        "Cleo)",
        "-",
        "see",
        ",",
        ",",
        "or",
    ]


def test_dial_label_left_after_inline_masking_goes_too():
    assert visible("Dial-in: +1 555-0142, Conference ID: 448 219 03#") == []


def test_content_mentions_of_tools_and_locations_stay():
    lines = [
        "Where: Admin Bldg Rm 210 / Teams",
        "Quick all-hands on Zoom Friday, rough plan below",
        "> Can field crews dial in from site?",
        "We need to pin down the vendor before Friday",
    ]
    assert visible("\n".join(lines)) == lines


def test_length_and_newlines_are_preserved_and_masking_is_idempotent():
    for text in [TEAMS, ZOOM, MEET, FORWARD, "plain text, nothing to mask"]:
        once = mask_boilerplate(text)
        assert len(once) == len(text)
        assert [i for i, c in enumerate(once) if c == "\n"] == [
            i for i, c in enumerate(text) if c == "\n"
        ]
        assert mask_boilerplate(once) == once


def test_masked_fraction():
    assert masked_fraction(TEAMS) == 1
    assert masked_fraction("nothing here") == 0
    assert 0 < masked_fraction("Budget review, Thursday\n" + MEET) < 1


def test_shared_boilerplate_does_not_make_invites_duplicates():
    a = "Budget review: approve the HVAC quote before Friday. Facilities + finance.\n" + TEAMS
    b = "Interview debrief for the designer role, pick a finalist.\n" + TEAMS
    assert find_duplicates([a, b]) == {}
