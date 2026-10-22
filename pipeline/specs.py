"""Seeded sampling of invite specs: one spec per invite to generate.

Writes data/specs.jsonl. Same seed and code → same specs, so the dataset is reproducible.

Every spec carries its own random cast of names, project name and sector-appropriate org name.
Left to itself the generator reuses favourite names ("Priya", "Halvorsen") across invites, which
would hand the classifier meaningless tokens to latch onto.

    python pipeline\\specs.py    # 800 main specs + 60 Zoom specs; refuses to change existing ones
"""

from __future__ import annotations

import argparse
import random
from dataclasses import asdict, dataclass

from jsonl import read_jsonl, write_jsonl
from labels import LABELS
from paths import RAW, SPECS

SEED = 20261021
DEFAULT_N = 800
CAST_SIZE = 6

# Supplement: Zoom invites state a start time but no end time or length, and the main set
# barely covers Zoom. Separate seed, so the main 800 are untouched.
ZOOM_SEED = 20261023
ZOOM_N = 60
ZOOM_FORMAT = (
    "Zoom invite as copied from Zoom: Topic, Time (start time only), Join Zoom Meeting link, "
    "Meeting ID, Passcode, One tap mobile / Dial by your location numbers. No end time and no "
    "meeting length anywhere in the invite"
)

# (name, attendee range, durations in minutes)
MEETING_TYPES: list[tuple[str, tuple[int, int], tuple[int, ...]]] = [
    ("weekly status sync", (4, 12), (30, 45, 60)),
    ("project kickoff", (5, 15), (60, 90)),
    ("decision meeting", (3, 8), (30, 60)),
    ("brainstorm", (3, 10), (45, 60, 90)),
    ("1:1", (2, 2), (15, 30)),
    ("retrospective", (4, 10), (45, 60)),
    ("all-hands / town hall", (40, 300), (30, 60)),
    ("quick sync / check-in", (2, 6), (15, 30)),
    ("vendor demo", (3, 12), (30, 60)),
    ("planning session", (4, 12), (60, 90, 120)),
    ("stakeholder review", (5, 20), (30, 60)),
    ("announcement / FYI meeting", (8, 60), (30, 60)),
    ("interview debrief", (3, 6), (30,)),
    ("incident review / postmortem", (4, 15), (45, 60)),
    ("training / walkthrough", (5, 30), (60, 90)),
    ("daily standup", (4, 12), (15, 30)),
    ("budget review", (3, 10), (60,)),
    ("meeting to plan another meeting", (3, 8), (30, 60)),
    ("cross-team alignment", (6, 25), (60,)),
    ("hiring process sync", (3, 8), (30, 45)),
]

FORMATS = [
    "calendar invite: title, date/time, location, description",
    "Outlook/Teams invite with dial-in boilerplate",
    "Google Calendar invite",
    "chat message (Slack/Teams) proposing a meeting",
    "email asking people to meet",
    "pasted agenda document",
    "calendar title only, nothing else",
    "forwarded invite with a short note on top",
]

# Industry → org-name patterns. {place} is a made-up place-like word, {last} a surname.
ORG_PATTERNS: dict[str, list[str]] = {
    "software startup": ["{place}", "{place} Labs", "{place}.io"],
    "hospital administration": ["{place} Medical Center", "{place} Health", "St. {last} Hospital"],
    "public school district": ["{place} Unified School District", "{place} Public Schools"],
    "university department": ["{place} University", "{place} State College"],
    "law firm": ["{last} & {last} LLP", "{last} {last} Law Group"],
    "marketing agency": ["{place} Creative", "{place} & Co.", "Studio {place}"],
    "manufacturing plant": ["{place} Manufacturing", "{place} Industries", "{place} Fabrication"],
    "nonprofit": ["{place} Foundation", "Friends of {place}", "{place} Community Trust"],
    "city government": ["City of {place}", "{place} County"],
    "retail chain headquarters": ["{place} Outfitters", "{place} Market", "{place} Home Goods"],
    "regional bank": ["{place} Savings Bank", "{place} Federal Credit Union", "First {place} Bank"],
    "construction firm": ["{last} Construction", "{place} Builders", "{last} & Sons"],
    "restaurant group": ["{place} Hospitality Group", "{last}'s Kitchens"],
    "game studio": ["{place} Games", "{place} Interactive"],
    "museum": ["{place} Museum of Art", "{place} History Museum"],
    "logistics company": ["{place} Freight", "{place} Logistics"],
    "insurance company": ["{place} Mutual", "{place} Insurance Group"],
    "biotech lab": ["{place} Biosciences", "{place} Therapeutics"],
    "volunteer parent association": ["{place} Elementary PTA", "{place} Middle School PTO"],
    "homeowners association": ["{place} Homeowners Association", "{place} Village HOA"],
    "film production": ["{place} Pictures", "{place} Films"],
    "management consultancy": ["{last} Partners", "{place} Advisory", "{place} Consulting"],
}
INDUSTRIES = list(ORG_PATTERNS)

TONES = [
    "corporate formal",
    "casual and friendly",
    "passive-aggressive",
    "overly enthusiastic",
    "terse",
    "apologetic",
    "jargon-heavy",
    "anxious",
    "bureaucratic",
    "folksy",
]

LENGTHS = [
    "one line (under 15 words)",
    "short (20-60 words)",
    "medium (60-150 words)",
    "long (150-350 words)",
]

VAGUENESS = [
    "clear agenda with specific items and owners",
    "rough agenda",
    "vague purpose only",
    "no stated purpose",
]

MESSINESS = [
    "a few typos",
    "forwarded email chain",
    "emoji",
    "ALL CAPS for emphasis",
    "pasted calendar/dial-in boilerplate",
    "inconsistent bullet formatting",
    "time zone confusion",
    "notes from other people replying",
    "[link] placeholders",
    "non-native English phrasing",
    "too many exclamation marks",
    "unrelated logistics mixed in (parking, lunch, birthdays)",
]

SUBTLETY = ["obvious", "subtle", "borderline"]

# fmt: off
FIRST_NAMES = [
    "Aisha", "Ben", "Carmen", "Dmitri", "Elena", "Femi", "Grace", "Hiroshi", "Imani", "Jonas",
    "Kavya", "Liam", "Mei", "Nadia", "Omar", "Priya", "Quinn", "Rafael", "Sofia", "Tariq",
    "Uma", "Victor", "Wen", "Ximena", "Yusuf", "Zoe", "Andre", "Bianca", "Chidi", "Dana",
    "Erik", "Fatima", "Gus", "Hana", "Ivan", "Jada", "Kenji", "Lucia", "Marcus", "Noor",
    "Oskar", "Paloma", "Raj", "Sam", "Tess", "Valentina", "Will", "Yara", "Abebe", "Bea",
    "Callum", "Deepa", "Esme", "Farid", "Gemma", "Hector", "Ines", "Jamal", "Keiko", "Lars",
    "Mariam", "Nico", "Olu", "Pilar", "Rhys", "Sana", "Teo", "Ulla", "Vikram", "Wanjiru",
    "Xavier", "Yoko", "Zainab", "Arjun", "Beth", "Cyrus", "Delia", "Emeka", "Fern", "Goran",
    "Hollis", "Ilse", "Joaquin", "Kemi", "Leon", "Maeve", "Nils", "Odette", "Pavel", "Rosa",
    "Soren", "Thandi", "Uriel", "Vera", "Wes", "Yasmin", "Ada", "Bruno", "Cleo", "Darius",
]
LAST_NAMES = [
    "Abernathy", "Bakshi", "Castellano", "Dube", "Eriksen", "Fairweather", "Gallo", "Haddad",
    "Ilunga", "Jaramillo", "Kowalczyk", "Lindqvist", "Mbatha", "Nakagawa", "Oyelaran", "Pruitt",
    "Quintero", "Rasmussen", "Szabo", "Thorne", "Underhill", "Vasquez", "Whitcombe", "Yilmaz",
    "Zielinski", "Achterberg", "Bramwell", "Cho", "Delacroix", "Esposito", "Fitzgerald",
    "Gunawardena", "Hollander", "Iversen", "Jovanovic", "Kariuki", "Lefebvre", "Moreau",
    "Nwachukwu", "Ostrowski", "Petrakis", "Rinaldi", "Sorensen", "Tanaka", "Uchenna",
    "Varga", "Wexler", "Xu", "Yamamoto", "Zapata", "Ahmadi", "Brennan", "Carvalho", "Dorsey",
    "Ekwueme", "Ferraro", "Grummond", "Hakimi", "Ishikawa", "Kessler",
]
PLACE_FIRST = [
    "Bright", "North", "Silver", "Cedar", "Blue", "Granite", "Maple", "Harbor", "Summit",
    "Willow", "Copper", "Lantern", "Prairie", "Orbit", "Juniper", "Beacon", "Tidal", "Falcon",
    "Ash", "Elm", "Fox", "Glen", "Iron", "Lake", "Mill", "Oak", "Pine", "Red", "Stone", "West",
]
PLACE_SECOND = [
    "field", "point", "line", "stone", "bridge", "works", "wave", "path", "gate", "leaf",
    "ridge", "spring", "crest", "haven", "forge", "light", "brook", "ford", "wood", "vale",
]
PROJECT_WORDS = [
    "Kestrel", "Marigold", "Basalt", "Lighthouse", "Tangerine", "Quarry", "Nimbus", "Atlas",
    "Bramble", "Cobalt", "Driftwood", "Ember", "Fjord", "Gingham", "Heron", "Indigo", "Jasper",
    "Kiln", "Lattice", "Mosaic", "Nutmeg", "Opal", "Pelican", "Quill", "Rook", "Saffron",
    "Thistle", "Umber", "Velvet", "Wren", "Yarrow", "Zephyr", "Anchor", "Bonfire", "Compass",
    "Dovetail", "Echo", "Foxglove", "Garnet", "Hearth",
]
PROJECT_PATTERNS = [
    "Project {word}", "the {word} rollout", "the {last} account", "{word} 2.0",
    "the {place} site", "the {word} initiative", "the {last} contract", "{word} migration",
]
# fmt: on


@dataclass(frozen=True)
class Spec:
    spec_id: str
    gen_hint: str
    subtlety: str
    meeting_type: str
    format: str
    industry: str
    tone: str
    length: str
    vagueness: str
    attendees: int
    duration_min: int
    messiness: tuple[str, ...]
    sender: str
    cast: tuple[str, ...]
    org: str
    project: str


def _place(rng: random.Random) -> str:
    return rng.choice(PLACE_FIRST) + rng.choice(PLACE_SECOND)


def _fill(pattern: str, rng: random.Random) -> str:
    # Fill each placeholder occurrence separately so "{last} & {last}" gets two names.
    out = pattern
    while "{" in out:
        key = out[out.index("{") + 1 : out.index("}")]
        value = {
            "place": lambda: _place(rng),
            "last": lambda: rng.choice(LAST_NAMES),
            "word": lambda: rng.choice(PROJECT_WORDS),
        }[key]()
        out = out.replace("{" + key + "}", value, 1)
    return out


def _pick_format(rng: random.Random, override: str | None) -> str:
    drawn = rng.choice(FORMATS)  # always draw, so an override doesn't shift later draws
    return override or drawn


def sample_specs(
    n: int = DEFAULT_N, seed: int = SEED, start: int = 1, format_: str | None = None
) -> list[Spec]:
    """n specs numbered from `start`. `format_` pins every spec to one format (the draw still
    happens, so the random sequence, and every existing spec, stays the same)."""
    rng = random.Random(seed)
    # Balanced hints: n/3 of each, shuffled.
    hints = [LABELS[i % len(LABELS)] for i in range(n)]
    rng.shuffle(hints)
    specs = []
    for i, hint in enumerate(hints, start=start):
        mtype, (lo, hi), durations = rng.choice(MEETING_TYPES)
        industry = rng.choice(INDUSTRIES)
        k = rng.choices([0, 1, 2], weights=[4, 4, 2])[0]
        sender, *others = rng.sample(FIRST_NAMES, CAST_SIZE + 1)
        cast = tuple(f"{first} {rng.choice(LAST_NAMES)}" for first in others)
        specs.append(
            Spec(
                spec_id=f"spec_{i:04d}",
                gen_hint=hint,
                subtlety=rng.choice(SUBTLETY),
                meeting_type=mtype,
                format=_pick_format(rng, format_),
                industry=industry,
                tone=rng.choice(TONES),
                length=rng.choice(LENGTHS),
                vagueness=rng.choice(VAGUENESS),
                attendees=rng.randint(lo, hi),
                duration_min=rng.choice(durations),
                messiness=tuple(sorted(rng.sample(MESSINESS, k))),
                sender=sender,
                cast=cast,
                org=_fill(rng.choice(ORG_PATTERNS[industry]), rng),
                project=_fill(rng.choice(PROJECT_PATTERNS), rng),
            )
        )
    return specs


def spec_to_dict(spec: Spec) -> dict:
    d = asdict(spec)
    d["messiness"] = list(spec.messiness)
    d["cast"] = list(spec.cast)
    return d


def spec_from_dict(d: dict) -> Spec:
    return Spec(**{**d, "messiness": tuple(d["messiness"]), "cast": tuple(d["cast"])})


def load_specs(path=SPECS) -> list[Spec]:
    return [spec_from_dict(d) for d in read_jsonl(path)]


def write_specs(specs: list[Spec], path=SPECS) -> None:
    write_jsonl(path, [spec_to_dict(s) for s in specs])


def all_specs() -> list[Spec]:
    """The dataset's specs: the main 800, then the Zoom supplement (spec_0801…)."""
    return sample_specs() + sample_specs(
        ZOOM_N, ZOOM_SEED, start=DEFAULT_N + 1, format_=ZOOM_FORMAT
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--force", action="store_true", help="write even if existing specs change")
    args = ap.parse_args()
    specs = all_specs()
    if SPECS.exists() and any(RAW.glob("b*.json")) and not args.force:
        old = {d["spec_id"]: d for d in read_jsonl(SPECS)}
        changed = [
            s.spec_id for s in specs if s.spec_id in old and spec_to_dict(s) != old[s.spec_id]
        ]
        if changed:
            raise SystemExit(
                f"{len(changed)} existing specs would change (e.g. {changed[0]}), orphaning their "
                "generations in data/raw/. Use --force if you really mean it."
            )
    write_specs(specs)
    print(f"Wrote {len(specs)} specs to {SPECS}")


if __name__ == "__main__":
    main()
