"""Print generated invites for review, with the spec they came from.

The spec's gen_hint (the verdict we asked for) is hidden unless --hints, so reviewing style
doesn't prime your labels.

    python pipeline\\sample.py -n 20            # 20 random invites
    python pipeline\\sample.py --first 20       # the first 20 (e.g. after a --limit 4 run)
    python pipeline\\sample.py --all            # every invite → pipeline\\.cache\\review.txt
"""

from __future__ import annotations

import argparse
import random

from jsonl import read_jsonl
from paths import CACHE, INVITES, SPECS

SPEC_FIELDS = ["meeting_type", "format", "industry", "tone", "length", "vagueness", "subtlety"]


def render(inv: dict, spec: dict | None, hints: bool) -> str:
    lines = [f"===== {inv['id']} " + "=" * 50]
    if spec:
        meta = [f"{spec[k]}" for k in SPEC_FIELDS]
        meta.append(f"{spec['attendees']} people, {spec['duration_min']} min")
        if spec["messiness"]:
            meta.append("mess: " + ", ".join(spec["messiness"]))
        if hints:
            meta.insert(0, f"HINT={spec['gen_hint']}")
        lines.append("[" + " | ".join(meta) + "]")
    lines += ["", inv["text"], ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("-n", type=int, default=10, help="random sample size")
    g.add_argument("--first", type=int, help="the first N invites in file order")
    g.add_argument("--all", action="store_true", help="write all to pipeline/.cache/review.txt")
    ap.add_argument("--hints", action="store_true", help="show the requested verdict")
    ap.add_argument("--seed", type=int, help="seed for a repeatable random sample")
    args = ap.parse_args()

    invites = read_jsonl(INVITES)
    if not invites:
        raise SystemExit("No invites yet. Run generate.py first.")
    specs = {s["spec_id"]: s for s in read_jsonl(SPECS)}

    if args.all:
        CACHE.mkdir(parents=True, exist_ok=True)
        out = CACHE / "review.txt"
        text = "\n".join(render(i, specs.get(i["spec_id"]), args.hints) for i in invites)
        out.write_text(text, encoding="utf-8")
        print(f"Wrote {len(invites)} invites to {out}")
        return
    if args.first:
        chosen = invites[: args.first]
    else:
        chosen = random.Random(args.seed).sample(invites, min(args.n, len(invites)))
    for inv in chosen:
        print(render(inv, specs.get(inv["spec_id"]), args.hints))


if __name__ == "__main__":
    main()
