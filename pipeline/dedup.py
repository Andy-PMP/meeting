"""Exact and near-duplicate detection for invite texts.

Used when building data/invites.jsonl (drop duplicates within the generated pool) and by
validate.py (no test invite may near-duplicate a training invite).
"""

from __future__ import annotations

import hashlib
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from clean import mask_boilerplate

NEAR_DUP_THRESHOLD = 0.9


def normalize(text: str) -> str:
    """Mask boilerplate, lowercase, drop punctuation, collapse whitespace. Two invites sharing
    an identical Teams block shouldn't look alike because of it."""
    text = re.sub(r"[^\w\s]", " ", mask_boilerplate(text).lower())
    return re.sub(r"\s+", " ", text).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def _vectorize(*corpora: list[str]):
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    vec.fit([normalize(t) for corpus in corpora for t in corpus])
    return [vec.transform([normalize(t) for t in corpus]) for corpus in corpora]


def find_duplicates(
    texts: list[str], threshold: float = NEAR_DUP_THRESHOLD
) -> dict[int, tuple[int, str]]:
    """Map index → (index it duplicates, "exact" | "near") for every text after the first of
    its group. Earlier texts win, so callers keep a stable, order-defined survivor."""
    dups: dict[int, tuple[int, str]] = {}
    seen: dict[str, int] = {}
    for i, t in enumerate(texts):
        h = text_hash(t)
        if h in seen:
            dups[i] = (seen[h], "exact")
        else:
            seen[h] = i
    if len(texts) < 2:
        return dups
    (m,) = _vectorize(texts)
    sims = cosine_similarity(m, dense_output=False).tocoo()
    # In index order, so a text is dropped only for resembling an earlier text that survived.
    pairs = sorted(
        (int(i), int(j))
        for i, j, s in zip(sims.row, sims.col, sims.data, strict=True)
        if j < i and s >= threshold
    )
    for i, j in pairs:
        if i not in dups and j not in dups:
            dups[i] = (j, "near")
    return dups


def find_leaks(
    test: list[str], train: list[str], threshold: float = NEAR_DUP_THRESHOLD
) -> list[tuple[int, int, float]]:
    """(test index, train index, similarity) for every test text too close to a train text."""
    if not test or not train:
        return []
    t, r = _vectorize(test, train)
    sims = cosine_similarity(t, r, dense_output=False).tocoo()
    return sorted(
        (int(i), int(j), round(float(s), 3))
        for i, j, s in zip(sims.row, sims.col, sims.data, strict=True)
        if s >= threshold
    )
