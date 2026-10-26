"""Tokenizer and structure features for both models, from features_spec.json.

Everything here takes MASKED text (clean.mask_boilerplate): the masking keeps offsets, so token
spans found here are also spans in the original invite. web/src/lib/features.ts (P4) reads the
same spec and must reproduce these results exactly; data/fixtures.json checks that.

Structure features are rough, rubric-shaped signals (duration, attendees, agenda size, minutes
per item, keyword families), one-hot encoded with an explicit "unknown" bucket: a Zoom invite
with no end time is "duration=unknown", never "short".
"""

from __future__ import annotations

import json
import re
from functools import cache

import numpy as np

from paths import PIPELINE

SPEC_PATH = PIPELINE / "features_spec.json"
FLAGS = re.IGNORECASE | re.ASCII


@cache
def spec() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@cache
def _rx(pattern: str, multiline: bool = False) -> re.Pattern:
    return re.compile(pattern, FLAGS | (re.MULTILINE if multiline else 0))


# ---------- tokenizer ----------

_TIME = re.compile(r"\d{1,2}:\d{2}\s?(am|pm)?", FLAGS)


def tokenize(text: str) -> list[tuple[str, int, int]]:
    """(token, start, end) for every token; start/end index into `text`."""
    tok = spec()["tokenizer"]
    out = []
    for m in _rx(tok["pattern"]).finditer(text):
        raw = m.group(0)
        if _TIME.fullmatch(raw):
            t = tok["time_token"]
        elif raw.isdigit():
            t = tok["number_token"]
        else:
            t = raw.lower()
        out.append((t, m.start(), m.end()))
    return out


def tokens(text: str) -> list[str]:
    """Token strings only: the TfidfVectorizer tokenizer."""
    return [t for t, _, _ in tokenize(text)]


# ---------- duration ----------


def _ampm(s: str | None) -> str | None:
    return None if not s else ("pm" if s.lower().startswith("p") else "am")


def _to24(h: int, ap: str | None) -> int:
    if ap == "pm" and h < 12:
        return h + 12
    if ap == "am" and h == 12:
        return 0
    return h


def _range_minutes(m: re.Match) -> int | None:
    h1, m1, a1, h2, m2, a2 = m.groups()
    if not (m1 or a1 or m2 or a2):  # "4-11" alone isn't a time range
        return None
    h1, h2 = int(h1), int(h2)
    if h1 > 23 or h2 > 23:
        return None
    m1, m2 = int(m1 or 0), int(m2 or 0)
    a1, a2 = _ampm(a1), _ampm(a2)
    if a1 is None and a2 is None:  # 12-hour clock, unknown half: "10:00-11:00", "12-12:30"
        diff = (h2 * 60 + m2) - (h1 * 60 + m1)
        return diff + 720 if diff <= 0 else diff

    # One side's am/pm applies to the other ("2-3pm"); flip it if that makes no sense.
    def flip(x: str) -> str:
        return "am" if x == "pm" else "pm"

    candidates = [(a1 or a2, a2 or a1)]
    if a1 is None:
        candidates.append((flip(a2), a2))
    if a2 is None:
        candidates.append((a1, flip(a1)))
    for x, y in candidates:
        diff = (_to24(h2, y) * 60 + m2) - (_to24(h1, x) * 60 + m1)
        if diff > 0:
            return diff
    return None


def parse_duration(text: str) -> int | None:
    """Meeting length in minutes, or None when the invite doesn't say."""
    d = spec()["duration"]
    lo, hi = d["min_minutes"], d["max_minutes"]
    for m in _rx(d["range"]).finditer(text):
        minutes = _range_minutes(m)
        if minutes is not None and lo <= minutes <= hi:
            return minutes
    for m in _rx(d["length"]).finditer(text):
        n, unit = float(m.group(1)), m.group(2).lower()
        minutes = round(n * 60) if unit.startswith("h") else round(n)
        if lo <= minutes <= hi:
            return minutes
    lowered = text.lower()
    hits = [(lowered.find(w), v) for w, v in d["words"].items() if w in lowered]
    return min(hits)[1] if hits else None


# ---------- attendees ----------


def _list_size(content: str, line: str) -> int:
    a = spec()["attendees"]
    items = [x for x in re.split(r"[;,]", content) if x.strip()]
    n = len(items)
    if m := _rx(a["list_count_in_line"]).search(line):
        n = max(n, int(m.group(1)))
    if m := _rx(a["and_others"]).search(line):
        n += int(m.group(1))
    return n


def parse_attendees(text: str) -> tuple[int | None, bool]:
    """(count or None, invited-a-broad-group flag)."""
    a = spec()["attendees"]
    counts: list[int] = []
    for m in _rx(a["count"]).finditer(text):
        if m.group(2).lower() != "others":  # "and 111 others" is counted with its list
            counts.append(int(m.group(1)))
    for m in _rx(a["all_n"]).finditer(text):
        counts.append(int(m.group(1)))
    for m in _rx(a["word_count"]).finditer(text):
        counts.append(a["words"][m.group(1).lower()])

    lines = text.split("\n")
    list_total, to_max = 0, 0
    header = _rx(a["list_line"])
    guests = _rx(a["guests_header"])
    for i, line in enumerate(lines):
        if m := header.match(line):
            size = _list_size(m.group(2), line)
            if m.group(1).lower() == "to":
                to_max = max(to_max, size)
            else:
                list_total += size
        elif guests.match(line):  # Google: "Guests" then one person per line
            block = 0
            for nxt in lines[i + 1 :]:
                if not nxt.strip():
                    break
                block += 1
            list_total += block
    counts += [n for n in (list_total, to_max) if n]
    counts = [n for n in counts if 0 < n <= a["max"]]
    group = bool(_rx(a["group"]).search(text))
    return (max(counts) if counts else None), group


# ---------- agenda ----------


def agenda_items(text: str) -> int:
    rx = _rx(spec()["agenda_item"])
    return sum(1 for line in text.split("\n") if rx.match(line))


# ---------- structure vector ----------


def _bucket(value: int | None, edges: list[int], name: str) -> str:
    if value is None:
        return f"{name}=unknown"
    for e in edges:
        if value <= e:
            return f"{name}<={e}"
    return f"{name}>{edges[-1]}"


@cache
def structure_names() -> tuple[str, ...]:
    b = spec()["buckets"]
    names = []
    for key, edges in [("duration", b["duration"]), ("attendees", b["attendees"])]:
        names += [f"{key}=unknown", *(f"{key}<={e}" for e in edges), f"{key}>{edges[-1]}"]
    names.append("attendees=group")
    e = b["agenda_items"]
    names += ["agenda_items=0", *(f"agenda_items<={x}" for x in e), f"agenda_items>{e[-1]}"]
    e = b["minutes_per_item"]
    names += ["min_per_item=unknown", *(f"min_per_item<={x}" for x in e), f"min_per_item>{e[-1]}"]
    names += [f"kw:{k}" for k in spec()["keywords"]]
    return tuple(names)


def structure(text: str) -> dict:
    """Parsed values plus the set of active one-hot feature names, for reasons and debugging."""
    b = spec()["buckets"]
    duration = parse_duration(text)
    attendees, group = parse_attendees(text)
    items = agenda_items(text)
    per_item = round(duration / items) if duration and items else None
    active = {
        _bucket(duration, b["duration"], "duration"),
        _bucket(attendees, b["attendees"], "attendees"),
        "agenda_items=0" if items == 0 else _bucket(items, b["agenda_items"], "agenda_items"),
        _bucket(per_item, b["minutes_per_item"], "min_per_item"),
    }
    if group:
        active.add("attendees=group")
    for name, pattern in spec()["keywords"].items():
        if _rx(pattern).search(text):
            active.add(f"kw:{name}")
    return {
        "duration": duration,
        "attendees": attendees,
        "group": group,
        "agenda_items": items,
        "minutes_per_item": per_item,
        "active": sorted(active),
    }


def structure_vector(text: str) -> np.ndarray:
    active = set(structure(text)["active"])
    return np.array([1.0 if n in active else 0.0 for n in structure_names()])


def structure_matrix(texts: list[str]) -> np.ndarray:
    return np.vstack([structure_vector(t) for t in texts]) if texts else np.zeros((0, 0))
