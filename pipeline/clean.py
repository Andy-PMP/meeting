"""Mask meeting boilerplate (join blocks, dial-ins, passcodes, links, forward headers).

Everything the models and similarity checks see goes through mask_boilerplate(); people
(labeler, review output, the site) see the original. Masked characters become spaces and
newlines stay put, so the result is exactly as long as the input and every offset in it is also
an offset in the original text: highlights map back with no bookkeeping.

The rules live in clean_rules.json and are shared with web/src/lib/clean.ts. Python uses
re.ASCII | re.IGNORECASE so \\b \\w \\d behave like JavaScript's.
"""

from __future__ import annotations

import json
import re
from functools import cache

from paths import PIPELINE

RULES_PATH = PIPELINE / "clean_rules.json"
FLAGS = re.IGNORECASE | re.ASCII


@cache
def _rules() -> tuple[list[re.Pattern], list[re.Pattern]]:
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    line = [re.compile(r["pattern"], FLAGS) for r in rules["line"]]
    inline = [re.compile(r["pattern"], FLAGS) for r in rules["inline"]]
    return line, inline


def _blank(s: str) -> str:
    return re.sub(r"[^\n]", " ", s)


def mask_line(line: str) -> str:
    """Mask one line. Repeats until stable: an inline mask can leave a bare label behind
    ("Dial-in:" once its number is gone) that a whole-line rule then removes."""
    line_rules, inline_rules = _rules()
    while True:
        trimmed = line.strip()
        if trimmed and any(p.search(trimmed) for p in line_rules):
            return _blank(line)
        chars = list(line)
        for p in inline_rules:
            for m in p.finditer(line):
                chars[m.start() : m.end()] = " " * (m.end() - m.start())
        masked = "".join(chars)
        if masked == line:
            return line
        line = masked


def mask_boilerplate(text: str) -> str:
    return "\n".join(mask_line(line) for line in text.split("\n"))


def masked_fraction(text: str) -> float:
    """Share of the text's non-whitespace characters that masking removed."""
    before = sum(not c.isspace() for c in text)
    after = sum(not c.isspace() for c in mask_boilerplate(text))
    return (before - after) / before if before else 0.0
