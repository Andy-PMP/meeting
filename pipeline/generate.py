"""Generate synthetic invites with the Claude Message Batches API, then rebuild data/invites.jsonl.

Each request carries 5 specs (one invite each). Every response is cached in data/raw/<bundle>.json
with the hash of the exact request, so re-running never pays twice for the same request, and a
change to the prompt or specs regenerates only what changed. If the script is interrupted while
a batch is running, the next run resumes that batch (data/raw/_pending.json) instead of
resubmitting.

The API key is read by the SDK from the ANTHROPIC_API_KEY environment variable. Never pass or
log it.

    python pipeline\\generate.py --dry-run      # what would be sent + estimated cost, no API
    python pipeline\\generate.py --limit 4      # first 4 bundles (20 invites)
    python pipeline\\generate.py                # everything not cached yet
    python pipeline\\generate.py --rebuild      # no API: rebuild invites.jsonl from data/raw
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dedup import find_duplicates
from jsonl import write_jsonl
from paths import DATA, INVITES, PROMPTS, RAW, SPECS
from specs import Spec, load_specs, spec_to_dict

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "generate_v2"  # v1 → v2: per-spec cast/project names (see specs.py)
EFFORT = "low"
BUNDLE_SIZE = 5
MAX_TOKENS = 16000
POLL_SECONDS = 30

# USD per million tokens (input, output), standard API rates; batches are half price.
PRICES = {"claude-opus-5-5": (4.00, 20.00)}
BATCH_DISCOUNT = 0.5

PENDING = RAW / "_pending.json"
DUPLICATES = DATA / "duplicates.jsonl"

# Structured output. Array length can't be constrained in the schema, so parse_invites checks it.
SCHEMA = {
    "type": "object",
    "properties": {
        "invites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"spec_id": {"type": "string"}, "text": {"type": "string"}},
                "required": ["spec_id", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["invites"],
    "additionalProperties": False,
}


def make_bundles(specs: list[Spec], size: int = BUNDLE_SIZE) -> list[tuple[str, list[Spec]]]:
    return [
        (f"b{n + 1:04d}", specs[i : i + size]) for n, i in enumerate(range(0, len(specs), size))
    ]


def load_template(version: str = PROMPT_VERSION) -> str:
    return (PROMPTS / f"{version}.md").read_text(encoding="utf-8")


def prompt_text(specs: list[Spec], template: str) -> str:
    payload = json.dumps([spec_to_dict(s) for s in specs], indent=1, ensure_ascii=False)
    return template.replace("{{SPECS}}", payload)


def request_hash(specs: list[Spec], template: str) -> str:
    key = {
        "model": MODEL,
        "effort": EFFORT,
        "max_tokens": MAX_TOKENS,
        "prompt": prompt_text(specs, template),
        "schema": SCHEMA,
    }
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def invite_id(spec_id: str) -> str:
    return "inv_" + spec_id.removeprefix("spec_")


def parse_invites(text: str, specs: list[Spec]) -> list[dict]:
    """The response's invites, in spec order. Raises ValueError if it doesn't match the specs."""
    try:
        invites = json.loads(text)["invites"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"unparseable response: {e}") from e
    by_id = {inv["spec_id"]: inv["text"].strip() for inv in invites}
    want = [s.spec_id for s in specs]
    if len(invites) != len(specs) or set(by_id) != set(want):
        raise ValueError(f"expected spec ids {want}, got {[i['spec_id'] for i in invites]}")
    if empty := [sid for sid in want if not by_id[sid]]:
        raise ValueError(f"empty invite text for {empty}")
    return [{"spec_id": sid, "text": by_id[sid]} for sid in want]


def raw_path(bundle_id: str, raw_dir: Path = RAW) -> Path:
    return raw_dir / f"{bundle_id}.json"


def load_raw(bundle_id: str, raw_dir: Path = RAW) -> dict | None:
    p = raw_path(bundle_id, raw_dir)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cached_invites(
    bundle_id: str, specs: list[Spec], template: str, raw_dir: Path = RAW
) -> tuple[dict, list[dict]] | None:
    """(raw record, invites) if this exact request already succeeded with a valid response."""
    raw = load_raw(bundle_id, raw_dir)
    if not raw or raw.get("request_hash") != request_hash(specs, template):
        return None
    if raw.get("result_type") != "succeeded":
        return None
    try:
        return raw, parse_invites(raw["text"], specs)
    except ValueError:
        return None


def cost_usd(usage: dict | None, model: str = MODEL) -> float:
    if not usage:
        return 0.0
    price_in, price_out = PRICES[model]
    tokens_in = (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + (usage.get("cache_read_input_tokens") or 0)
    )
    tokens_out = usage.get("output_tokens") or 0
    return (tokens_in * price_in + tokens_out * price_out) / 1e6 * BATCH_DISCOUNT


# ---------- API ----------


def build_request(bundle_id: str, specs: list[Spec], template: str):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    return Request(
        custom_id=bundle_id,
        params=MessageCreateParamsNonStreaming(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt_text(specs, template)}],
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
        ),
    )


def record_result(result, hashes: dict[str, str], batch_id: str, raw_dir: Path = RAW) -> str:
    """Write one batch result to data/raw/ and return its type."""
    r = result.result
    rec = {
        "bundle_id": result.custom_id,
        "request_hash": hashes[result.custom_id],
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "batch_id": batch_id,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "result_type": r.type,
    }
    if r.type == "succeeded":
        msg = r.message
        rec["stop_reason"] = msg.stop_reason
        rec["usage"] = msg.usage.model_dump(mode="json")
        rec["text"] = "".join(b.text for b in msg.content if b.type == "text")
    elif r.type == "errored":
        rec["error"] = str(r.error)
    raw_dir.mkdir(parents=True, exist_ok=True)
    # Keep the response this one replaces (prompt change, failed validation): the history stays
    # complete and total_cost still counts what it cost.
    if old := load_raw(result.custom_id, raw_dir):
        superseded = raw_dir / "superseded"
        superseded.mkdir(exist_ok=True)
        stale = superseded / f"{result.custom_id}-{old.get('batch_id', 'unknown')}.json"
        raw_path(result.custom_id, raw_dir).replace(stale)
    raw_path(result.custom_id, raw_dir).write_text(
        json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return r.type


def wait_and_collect(client, batch_id: str, hashes: dict[str, str]) -> None:
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        c = batch.request_counts
        print(
            f"  batch {batch_id}: {batch.processing_status} "
            f"(processing {c.processing}, succeeded {c.succeeded}, errored {c.errored})",
            flush=True,
        )
        if batch.processing_status == "ended":
            break
        time.sleep(POLL_SECONDS)
    counts: dict[str, int] = {}
    for result in client.messages.batches.results(batch_id):
        t = record_result(result, hashes, batch_id)
        counts[t] = counts.get(t, 0) + 1
    PENDING.unlink(missing_ok=True)
    print(f"  results: {counts}")


def submit(client, todo: list[tuple[str, list[Spec]]], template: str) -> None:
    hashes = {bid: request_hash(specs, template) for bid, specs in todo}
    batch = client.messages.batches.create(
        requests=[build_request(bid, specs, template) for bid, specs in todo]
    )
    RAW.mkdir(parents=True, exist_ok=True)
    PENDING.write_text(json.dumps({"batch_id": batch.id, "hashes": hashes}, indent=1) + "\n")
    print(
        f"Submitted batch {batch.id} with {len(todo)} requests ({len(todo) * BUNDLE_SIZE} invites)"
    )
    wait_and_collect(client, batch.id, hashes)


# ---------- dataset ----------


def build_invites(
    specs: list[Spec],
    template: str,
    raw_dir: Path = RAW,
    out: Path = INVITES,
    dup_out: Path = DUPLICATES,
) -> dict:
    """Rebuild invites.jsonl from every cached, valid response, dropping duplicates."""
    records = []
    for bundle_id, bundle in make_bundles(specs):
        got = cached_invites(bundle_id, bundle, template, raw_dir)
        if not got:
            continue
        raw, invites = got
        for inv in invites:
            records.append(
                {
                    "id": invite_id(inv["spec_id"]),
                    "text": inv["text"],
                    "source": "synthetic",
                    "spec_id": inv["spec_id"],
                    "gen_model": raw["model"],
                    "prompt_version": raw["prompt_version"],
                    "created": raw["created"],
                }
            )
    dups = find_duplicates([r["text"] for r in records])
    kept = [r for i, r in enumerate(records) if i not in dups]
    write_jsonl(out, kept)
    write_jsonl(
        dup_out,
        [
            {"id": records[i]["id"], "duplicate_of": records[j]["id"], "kind": kind}
            for i, (j, kind) in sorted(dups.items())
        ],
    )
    return {"generated": len(records), "duplicates": len(dups), "kept": len(kept)}


def total_cost(raw_dir: Path = RAW) -> tuple[float, int]:
    """(USD, request count) over every response on disk, including superseded ones."""
    files = [*raw_dir.glob("b*.json"), *raw_dir.glob("superseded/b*.json")]
    usd = sum(cost_usd(json.loads(p.read_text(encoding="utf-8")).get("usage")) for p in files)
    return usd, len(files)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--limit", type=int, help="only the first N bundles (5 invites each)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be sent; no API calls")
    ap.add_argument("--rebuild", action="store_true", help="no API calls; rebuild invites.jsonl")
    args = ap.parse_args()

    if not SPECS.exists():
        sys.exit("No data/specs.jsonl yet. Run: .\\.venv\\Scripts\\python pipeline\\specs.py")
    specs = load_specs()
    template = load_template()
    bundles = make_bundles(specs)[: args.limit]
    todo = [(bid, b) for bid, b in bundles if not cached_invites(bid, b, template)]
    print(f"{len(bundles)} bundles selected, {len(bundles) - len(todo)} cached, {len(todo)} to do")

    if args.dry_run:
        if todo:
            sample = prompt_text(todo[0][1], template)
            est_in = len(sample) / 4 * len(todo)
            est_out = 2500 * len(todo)  # ~5 invites + low-effort thinking per request
            price_in, price_out = PRICES[MODEL]
            est = (est_in * price_in + est_out * price_out) / 1e6 * BATCH_DISCOUNT
            print(f"Estimated cost: ~${est:.2f}\n\n--- first request prompt ---\n{sample}")
        return

    if not args.rebuild and (todo or PENDING.exists()):
        import anthropic

        client = anthropic.Anthropic()
        try:
            if PENDING.exists():
                pending = json.loads(PENDING.read_text())
                print(f"Resuming batch {pending['batch_id']} from an earlier run")
                wait_and_collect(client, pending["batch_id"], pending["hashes"])
                todo = [(bid, b) for bid, b in bundles if not cached_invites(bid, b, template)]
            if todo:
                submit(client, todo, template)
                todo = [(bid, b) for bid, b in bundles if not cached_invites(bid, b, template)]
            if todo:
                print(f"Retrying {len(todo)} failed or invalid requests once")
                submit(client, todo, template)
        except anthropic.AuthenticationError:
            sys.exit(
                "Authentication failed: check the ANTHROPIC_API_KEY user environment variable."
            )
        except anthropic.APIConnectionError as e:
            sys.exit(f"Could not reach the API ({e}). Re-run to resume; nothing is lost.")
        except anthropic.APIStatusError as e:
            sys.exit(f"API error {e.status_code}: {e.message}")

    stats = build_invites(specs, template)
    usd, n = total_cost()
    missing = [bid for bid, b in bundles if not cached_invites(bid, b, template)]
    print(
        f"invites.jsonl: {stats['kept']} kept of {stats['generated']} generated "
        f"({stats['duplicates']} duplicates dropped)"
    )
    print(f"Spend so far: ${usd:.2f} over {n} requests")
    if missing:
        print(f"Still missing after retry: {', '.join(missing)} (re-run to try again)")


if __name__ == "__main__":
    main()
