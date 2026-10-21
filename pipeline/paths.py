"""Shared filesystem locations for the pipeline scripts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "pipeline"
CACHE = PIPELINE / ".cache"
PROMPTS = PIPELINE / "prompts"

DATA = ROOT / "data"
RAW = DATA / "raw"
SPECS = DATA / "specs.jsonl"
INVITES = DATA / "invites.jsonl"
LABELS = DATA / "labels.jsonl"
TEST_INVITES = DATA / "test" / "test_invites.jsonl"
EVAL = DATA / "eval.json"
FIXTURES = DATA / "fixtures.json"

MODELS = ROOT / "models"
DOCS = ROOT / "docs"
