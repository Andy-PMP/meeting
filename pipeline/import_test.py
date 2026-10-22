"""Turn your hand-written test invites (plain text) into data/test/test_invites.jsonl.

Write the invites in data/test/test_invites.txt. Each one starts with a header line naming its
label, then an optional "note:" line, then the invite exactly as it would appear:

    === keep
    note: borderline, 9 people but everyone owns a piece
    Subject: Pick the launch date
    ...

    === email
    FYI: new expense tool goes live Monday

IDs (test_001, test_002, ...) follow the order in the file, so only ever add new invites at the
end. Once you use the .txt, it is the source of truth: edit it, not the .jsonl.

    python pipeline\\import_test.py
"""

from __future__ import annotations

import re
import sys

from dedup import find_duplicates, find_leaks
from jsonl import read_jsonl, write_jsonl
from labels import LABELS
from paths import INVITES, TEST_INVITES, TEST_SOURCE

HEADER = re.compile(r"^===\s*(\S+)\s*$")


def parse(text: str) -> tuple[list[dict], list[str]]:
    """(rows, errors). Text before the first header is ignored (room for your own notes)."""
    rows: list[dict] = []
    errors: list[str] = []
    blocks: list[tuple[int, str, list[str]]] = []
    for n, line in enumerate(text.splitlines(), start=1):
        if m := HEADER.match(line):
            blocks.append((n, m.group(1).lower(), []))
        elif blocks:
            blocks[-1][2].append(line)
    for n, label, lines in blocks:
        if label not in LABELS:
            errors.append(f"line {n}: '{label}' is not one of {', '.join(LABELS)}")
            continue
        note = ""
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and lines[0].lower().startswith("note:"):
            note = lines.pop(0)[5:].strip()
        body = "\n".join(lines).strip()
        if not body:
            errors.append(f"line {n}: empty invite")
            continue
        rows.append({"id": f"test_{len(rows) + 1:03d}", "text": body, "label": label, "note": note})
    return rows, errors


def main() -> None:
    if not TEST_SOURCE.exists():
        sys.exit(f"Write your invites in {TEST_SOURCE} first (format in this script's docstring).")
    rows, errors = parse(TEST_SOURCE.read_text(encoding="utf-8"))
    texts = [r["text"] for r in rows]
    for i, (j, kind) in sorted(find_duplicates(texts).items()):
        errors.append(f"{rows[i]['id']} is a {kind} duplicate of {rows[j]['id']}")
    train = read_jsonl(INVITES)
    for i, j, sim in find_leaks(texts, [r["text"] for r in train]):
        errors.append(
            f"{rows[i]['id']} is too close to training invite {train[j]['id']} ({sim}). "
            "Test invites must be written from scratch"
        )
    if errors:
        print("\n".join(f"ERROR {e}" for e in errors))
        sys.exit(f"{len(errors)} error(s); nothing written.")
    write_jsonl(TEST_INVITES, rows)
    by = {lab: sum(r["label"] == lab for r in rows) for lab in LABELS}
    print(
        f"Wrote {len(rows)} test invites to {TEST_INVITES}: "
        + ", ".join(f"{k} {v}" for k, v in by.items())
    )
    if low := [k for k, v in by.items() if v < 15]:
        print(f"Still under 15: {', '.join(low)} (goal: ~25 per label, at least 15)")


if __name__ == "__main__":
    main()
