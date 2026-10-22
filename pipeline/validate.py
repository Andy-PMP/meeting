"""Check data/ for schema errors, broken references and test/train leakage.

Missing files are fine (the dataset fills in phase by phase); anything present must be valid.

    python pipeline\\validate.py
"""

from __future__ import annotations

import re
import sys

from dedup import find_leaks
from jsonl import read_jsonl
from labels import LABELS
from paths import INVITES, SPECS, TEST_INVITES
from paths import LABELS as LABELS_PATH

INVITE_KEYS = {"id", "text", "source", "spec_id", "gen_model", "prompt_version", "created"}
LABEL_KEYS = {"id", "label", "discarded", "note", "pass", "labeled_at"}
TEST_KEYS = {"id", "text", "label", "note"}
MAX_WORDS = 800


def check_invites(invites: list[dict], spec_ids: set[str]) -> list[str]:
    errors = []
    seen: set[str] = set()
    for n, r in enumerate(invites, start=1):
        where = f"invites.jsonl line {n}"
        if set(r) != INVITE_KEYS:
            errors.append(f"{where}: keys {sorted(r)} != {sorted(INVITE_KEYS)}")
            continue
        if not re.fullmatch(r"inv_\d{4}", r["id"]):
            errors.append(f"{where}: bad id {r['id']!r}")
        if r["id"] in seen:
            errors.append(f"{where}: duplicate id {r['id']}")
        seen.add(r["id"])
        if not r["text"].strip():
            errors.append(f"{where}: empty text")
        elif len(r["text"].split()) > MAX_WORDS:
            errors.append(f"{where}: over {MAX_WORDS} words")
        if spec_ids and r["spec_id"] not in spec_ids:
            errors.append(f"{where}: unknown spec_id {r['spec_id']}")
    return errors


def check_labels(labels: list[dict], invite_ids: set[str]) -> list[str]:
    errors = []
    for n, r in enumerate(labels, start=1):
        where = f"labels.jsonl line {n}"
        if set(r) != LABEL_KEYS:
            errors.append(f"{where}: keys {sorted(r)} != {sorted(LABEL_KEYS)}")
            continue
        if r["id"] not in invite_ids:
            errors.append(f"{where}: unknown invite {r['id']}")
        if r["discarded"]:
            if r["label"] is not None:
                errors.append(f"{where}: discarded rows must have label null")
        elif r["label"] not in LABELS:
            errors.append(f"{where}: label {r['label']!r} not in {LABELS}")
        if r["pass"] not in (1, 2):
            errors.append(f"{where}: pass must be 1 or 2")
    return errors


def check_test(test: list[dict], train_texts: list[str]) -> list[str]:
    errors = []
    seen: set[str] = set()
    for n, r in enumerate(test, start=1):
        where = f"test_invites.jsonl line {n}"
        if set(r) != TEST_KEYS:
            errors.append(f"{where}: keys {sorted(r)} != {sorted(TEST_KEYS)}")
            continue
        if not re.fullmatch(r"test_\d{3}", r["id"]):
            errors.append(f"{where}: bad id {r['id']!r}")
        if r["id"] in seen:
            errors.append(f"{where}: duplicate id {r['id']}")
        seen.add(r["id"])
        if r["label"] not in LABELS:
            errors.append(f"{where}: label {r['label']!r} not in {LABELS}")
        if not r["text"].strip():
            errors.append(f"{where}: empty text")
    if not errors:
        for i, _, sim in find_leaks([r["text"] for r in test], train_texts):
            errors.append(f"test {test[i]['id']} near-duplicates a training invite ({sim})")
    return errors


def main() -> None:
    spec_ids = {r["spec_id"] for r in read_jsonl(SPECS)}
    invites = read_jsonl(INVITES)
    labels = read_jsonl(LABELS_PATH)
    test = read_jsonl(TEST_INVITES)

    errors = check_invites(invites, spec_ids)
    errors += check_labels(labels, {r["id"] for r in invites})
    errors += check_test(test, [r["text"] for r in invites])

    counts = f"specs {len(spec_ids)} · invites {len(invites)} · label rows {len(labels)}"
    print(f"{counts} · test {len(test)}")
    for e in errors[:50]:
        print("ERROR", e)
    if len(errors) > 50:
        print(f"... and {len(errors) - 50} more")
    print(f"{len(errors)} error(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
