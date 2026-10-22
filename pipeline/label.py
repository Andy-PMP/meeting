"""Keyboard labeler: one keypress per invite, saved instantly, resumable.

Shows each unlabeled invite with the rubric cheat-sheet (docs/rubric.md §5) and running label
counts. Every keypress appends one row to data/labels.jsonl; for an invite labeled more than
once in the same pass, the last row wins. The verdict the generator was asked for is never shown.

Keys: 1 keep · 2 shorter · 3 email · d discard · s skip (comes back next session)
      n add a note to this invite · u undo the last label · q quit

    python pipeline\\label.py                  # label everything not labeled yet
    python pipeline\\label.py --id inv_0042    # redo one invite
    python pipeline\\label.py --relabel 0.1    # blind second pass on 10% (≥5 days after pass 1)
"""

from __future__ import annotations

import argparse
import random
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jsonl import append_jsonl, read_jsonl
from labels import LABELS
from paths import DOCS, INVITES
from paths import LABELS as LABELS_PATH

KEYS = {"1": "keep", "2": "shorter", "3": "email"}
RELABEL_SEED = 20261022
RELABEL_MIN_DAYS = 5


# ---------- pure logic (tested) ----------


def latest_labels(rows: list[dict], pass_: int = 1) -> dict[str, dict]:
    """id → most recent row for that pass."""
    out: dict[str, dict] = {}
    for r in rows:
        if r["pass"] == pass_:
            out[r["id"]] = r
    return out


def todo_ids(invite_ids: list[str], done: dict[str, dict]) -> list[str]:
    return [i for i in invite_ids if i not in done]


def relabel_sample(pass1: dict[str, dict], fraction: float, seed: int = RELABEL_SEED) -> list[str]:
    """A fixed random sample of labeled (non-discarded) invites. Same answer every session, so
    the second pass can be spread over several sittings."""
    ids = sorted(i for i, r in pass1.items() if not r["discarded"])
    k = max(1, round(len(ids) * fraction)) if ids else 0
    return sorted(random.Random(seed).sample(ids, k))


def counts(done: dict[str, dict]) -> dict[str, int]:
    c = {lab: 0 for lab in LABELS}
    c["discarded"] = 0
    for r in done.values():
        c["discarded" if r["discarded"] else r["label"]] += 1
    return c


def cheat_sheet(rubric_md: str) -> list[str]:
    """The bullet lines under the rubric's '## 5.' heading, markdown bold removed."""
    m = re.search(r"^## 5\..*?$(.*?)(?=^## |\Z)", rubric_md, re.M | re.S)
    if not m:
        return []
    lines = [ln.strip()[2:] for ln in m.group(1).splitlines() if ln.strip().startswith("- ")]
    return [ln.replace("**", "") for ln in lines]


def make_row(invite_id: str, key: str, note: str, pass_: int) -> dict:
    discarded = key == "d"
    return {
        "id": invite_id,
        "label": None if discarded else KEYS[key],
        "discarded": discarded,
        "note": note,
        "pass": pass_,
        "labeled_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def remove_last_row(path: Path, invite_id: str) -> bool:
    """Undo: drop the file's last line if it is a row for invite_id. The only exception to
    append-only, and only for the row this session just wrote."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or f'"id": "{invite_id}"' not in lines[-1]:
        return False
    path.write_text("".join(lines[:-1]), encoding="utf-8", newline="")
    return True


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Agreement between two label lists beyond chance (1 = perfect, 0 = chance)."""
    n = len(a)
    if n == 0:
        return float("nan")
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    cats = set(a) | set(b)
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


# ---------- terminal ----------


def read_key() -> str:
    """One keypress, no Enter needed (Windows); falls back to a line of input elsewhere."""
    try:
        import msvcrt
    except ImportError:
        return (input("> ").strip()[:1] or " ").lower()
    while True:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):  # arrow/function keys arrive as two characters
            msvcrt.getwch()
            continue
        return ch.lower()


def run(queue: list[str], invites: dict[str, dict], pass_: int, total_done: dict) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    sheet = cheat_sheet((DOCS / "rubric.md").read_text(encoding="utf-8"))
    history: list[str] = []  # ids labeled this session, for undo
    i, started, labeled_now = 0, time.monotonic(), 0
    note = ""
    while i < len(queue):
        inv_id = queue[i]
        console.clear()
        c = counts(total_done)
        n_lab = sum(c[lab] for lab in LABELS)
        mix = " · ".join(
            f"{lab} {c[lab]} ({c[lab] / n_lab:.0%})" if n_lab else f"{lab} 0" for lab in LABELS
        )
        rate = (time.monotonic() - started) / labeled_now if labeled_now else None
        eta = f" · ~{rate:.0f}s each, ~{rate * (len(queue) - i) / 60:.0f} min left" if rate else ""
        title = "Second pass (blind)" if pass_ == 2 else "Labeling"
        console.print(
            f"[bold]{title}[/] · {i + 1} of {len(queue)} this session · {inv_id}{eta}\n"
            f"[dim]{mix} · discarded {c['discarded']}[/]"
        )
        # Text(), not markup: invites contain [link]-style brackets.
        console.print(Panel(Text(invites[inv_id]["text"]), padding=(1, 2)))
        for line in sheet:
            console.print(Text(line, style="cyan"))
        if note:
            console.print(Text(f"note: {note}", style="yellow"))
        console.print(
            "[bold]1[/] keep  [bold]2[/] shorter  [bold]3[/] email  [bold]d[/] discard  "
            "[bold]s[/] skip  [bold]n[/] note  [bold]u[/] undo  [bold]q[/] quit"
        )

        key = read_key()
        if key == "q":
            break
        if key == "n":
            note = input("note: ").strip()
            continue
        if key == "s":
            i, note = i + 1, ""
            continue
        if key == "u":
            if history and remove_last_row(LABELS_PATH, history[-1]):
                prev = history.pop()
                total_done.pop(prev, None)
                for r in reversed(read_jsonl(LABELS_PATH)):  # restore any earlier label
                    if r["id"] == prev and r["pass"] == pass_:
                        total_done[prev] = r
                        break
                i = max(0, queue.index(prev))
                labeled_now = max(0, labeled_now - 1)
            continue
        if key in KEYS or key == "d":
            row = make_row(inv_id, key, note, pass_)
            append_jsonl(LABELS_PATH, row)
            total_done[inv_id] = row
            history.append(inv_id)
            i, note, labeled_now = i + 1, "", labeled_now + 1
    console.clear()
    console.print(f"Saved. {labeled_now} labeled this session.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--id", help="relabel one invite (pass 1)")
    ap.add_argument("--relabel", type=float, metavar="FRACTION", help="blind second pass")
    ap.add_argument("--force", action="store_true", help="skip the 5-day wait for --relabel")
    args = ap.parse_args()

    invite_rows = read_jsonl(INVITES)
    if not invite_rows:
        sys.exit("No invites yet (data/invites.jsonl).")
    invites = {r["id"]: r for r in invite_rows}
    rows = read_jsonl(LABELS_PATH)
    pass1 = latest_labels(rows, 1)

    if args.relabel:
        if not pass1:
            sys.exit("Nothing labeled yet.")
        last = max(datetime.fromisoformat(r["labeled_at"]) for r in pass1.values())
        if datetime.now(UTC) - last < timedelta(days=RELABEL_MIN_DAYS) and not args.force:
            sys.exit(
                f"Your last first-pass label was {last:%Y-%m-%d}. Wait {RELABEL_MIN_DAYS} days so "
                "the second pass is a fair test of consistency (or pass --force)."
            )
        pass2 = latest_labels(rows, 2)
        sample = relabel_sample(pass1, args.relabel)
        queue = todo_ids(sample, pass2)
        if queue:
            run(queue, invites, 2, pass2)
            pass2 = latest_labels(read_jsonl(LABELS_PATH), 2)
        both = [i for i in sample if i in pass2]
        if both:
            a = [pass1[i]["label"] or "discard" for i in both]
            b = [pass2[i]["label"] or "discard" for i in both]
            agree = sum(x == y for x, y in zip(a, b, strict=True))
            print(
                f"Second pass: {len(both)}/{len(sample)} done · agreement {agree}/{len(both)} · "
                f"Cohen's kappa {cohen_kappa(a, b):.2f} (target ≥ 0.7)"
            )
        return

    if args.id:
        if args.id not in invites:
            sys.exit(f"Unknown invite {args.id}")
        run([args.id], invites, 1, pass1)
        return

    queue = todo_ids(list(invites), pass1)
    if not queue:
        print("Everything is labeled. Next: --relabel 0.1 after 5 days.")
        return
    run(queue, invites, 1, pass1)


if __name__ == "__main__":
    main()
