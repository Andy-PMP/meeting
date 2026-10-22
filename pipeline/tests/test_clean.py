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

ZOOM_FULL = """Darius is inviting you to a scheduled Zoom meeting.

Topic: Cobalt migration go/no-go
Time: Oct 28, 2026 10:00 AM Eastern Time (US and Canada)

Join Zoom Meeting
https://us02web.zoom.us/j/81234567890?pwd=xyz

Meeting ID: 812 3456 7890
Passcode: 123456

Find your local number: https://us02web.zoom.us/u/kabc
Join by SIP
• 81234567890@zoomcrc.com
Join by H.323
• 162.255.37.11 (US West)
162.255.36.11 (US East)"""

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


GOOGLE_EMAIL = """Invitation: Budget sync @ Tue Oct 28, 2026 10am - 11am (EDT) (sam@example.com)

Decide which two pilots we fund.

Join with Google Meet
meet.google.com/abc-defg-hij
Join by phone
(US) +1 555-555-0123
PIN: 123456789
More phone numbers
Video call link: https://meet.google.com/abc-defg-hij
Time zone: America/New_York
View all guest info
Organizer
pat@example.com
Guests
pat@example.com - organizer
sam@example.com
Reply for sam@example.com
Yes   No   Maybe   More options
Invitation from Google Calendar
You are receiving this email because you are an attendee on the event."""

WEBEX_NEW_TEAMS = """-- Do not delete or change any of the following text. --
When it's time, join the Webex meeting here.
Join from the meeting link
https://example.webex.com/example/j.php?MTID=X
Join by meeting number
Meeting number (access code): 2634 123 4567
Meeting password: besafe
Microsoft Teams Need help?
Join the meeting now"""


def test_google_calendar_email_keeps_subject_purpose_and_guests():
    assert visible(GOOGLE_EMAIL) == [
        "Invitation: Budget sync @ Tue Oct 28, 2026 10am - 11am (EDT) (sam@example.com)",
        "Decide which two pilots we fund.",
        "Organizer",
        "pat@example.com",
        "Guests",
        "pat@example.com - organizer",
        "sam@example.com",
    ]


def test_webex_and_new_teams_wording_disappear():
    assert visible(WEBEX_NEW_TEAMS) == []


def test_full_zoom_invite_keeps_only_topic_and_time():
    assert visible(ZOOM_FULL) == [
        "Topic: Cobalt migration go/no-go",
        "Time: Oct 28, 2026 10:00 AM Eastern Time (US and Canada)",
    ]


def test_forwarding_keeps_note_subject_recipients_and_time():
    assert visible(FORWARD) == [
        "Sorry, forwarding in case this got missed?? -Nadia",
        "Subject: Retro: Q3 matter",
        "To: Litigation team (9)",
        "Date: Wednesday, 2:00-2:45pm",
    ]


@pytest.mark.parametrize(
    "separator",
    [
        "---------- Forwarded message ----------",
        "-----Original Message-----",
        "-----Original Appointment-----",
        "----- Forwarded -----",
    ],
)
def test_forward_separators_in_gmail_and_outlook_styles(separator):
    assert visible(f"FYI, see below\n\n{separator}\nSubject: Data migration") == [
        "FYI, see below",
        "Subject: Data migration",
    ]


@pytest.mark.parametrize("rule", ["_" * 20, "-" * 10, "─" * 10, "━" * 8, "—" * 6])
def test_rule_lines_in_ascii_and_box_drawing_styles(rule):
    assert visible(f"Can we discuss the quote?\n{rule}\nThanks") == [
        "Can we discuss the quote?",
        "Thanks",
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
