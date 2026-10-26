"""Cross-validate both model families on the training labels. Never touches the test set.

    python pipeline\\train.py    # all configs → data/cv.json + docs/model-report.md (CV part)

Model A (linear): TF-IDF word 1-2-grams over the shared tokenizer + structure features →
logistic regression. Model B (embedding): MiniLM or BGE embedding + structure features →
standardized logistic regression. All inputs are mask_boilerplate(text).

Scores are repeated stratified 5-fold CV (3 shuffles), so each number averages 15 splits.
Everything that learns from data (TF-IDF vocabulary, scaler) is fitted inside each fold.
Picking the best config on the same folds flatters its CV score a little; the hand-written test
set (evaluate.py, once per frozen model) is the unbiased number.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from functools import partial

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from clean import mask_boilerplate
from embed import embed_cached, model_names
from features import structure_matrix, tokens
from jsonl import read_jsonl
from label import latest_labels
from labels import LABELS
from paths import DATA, DOCS, INVITES
from paths import LABELS as LABELS_PATH

SEED = 20261026
REPEATS = 3
FOLDS = 5
CV_PATH = DATA / "cv.json"
REPORT = DOCS / "model-report.md"
EMBED_PICK_MARGIN = 0.03  # ship MiniLM unless BGE beats it by >= 3 macro-F1 points

LINEAR_C = [1, 3, 10, 30, 100, 300]
EMBED_C = [0.001, 0.003, 0.01, 0.03, 0.1]
CLASS_WEIGHTS = [None, "balanced"]


@dataclass
class Dataset:
    ids: list[str]
    texts: list[str]  # masked
    y: np.ndarray  # label indices, LABELS order
    structure: np.ndarray
    zoom: np.ndarray = field(default_factory=lambda: np.zeros(0, bool))


def load_dataset() -> Dataset:
    invites = {r["id"]: r for r in read_jsonl(INVITES)}
    labeled = latest_labels(read_jsonl(LABELS_PATH), 1)
    ids = sorted(i for i, r in labeled.items() if not r["discarded"] and i in invites)
    texts = [mask_boilerplate(invites[i]["text"]) for i in ids]
    y = np.array([LABELS.index(labeled[i]["label"]) for i in ids])
    zoom = np.array([int(i[4:]) > 800 for i in ids])
    return Dataset(ids, texts, y, structure_matrix(texts), zoom)


# ---------- the two model families (also used by export/evaluate) ----------


def make_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        tokenizer=tokens,
        lowercase=False,
        token_pattern=None,
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=2,
        max_features=5000,
    )


def linear_features(vec, texts, structure, use_text=True, use_structure=True):
    parts = []
    if use_text:
        parts.append(vec.transform(texts))
    if use_structure:
        parts.append(csr_matrix(structure))
    return hstack(parts).tocsr()


def fit_predict_linear(ds, tr, te, C, cw, use_text=True, use_structure=True):
    vec = make_vectorizer().fit([ds.texts[i] for i in tr]) if use_text else None
    X_tr = linear_features(
        vec, [ds.texts[i] for i in tr], ds.structure[tr], use_text, use_structure
    )
    X_te = linear_features(
        vec, [ds.texts[i] for i in te], ds.structure[te], use_text, use_structure
    )
    clf = LogisticRegression(C=C, class_weight=cw, max_iter=5000).fit(X_tr, ds.y[tr])
    return clf.predict(X_te)


def fit_predict_embed(ds, emb, tr, te, C, cw, use_structure=True):
    X = np.hstack([emb, ds.structure]) if use_structure else emb
    scaler = StandardScaler().fit(X[tr])
    clf = LogisticRegression(C=C, class_weight=cw, max_iter=5000)
    clf.fit(scaler.transform(X[tr]), ds.y[tr])
    return clf.predict(scaler.transform(X[te]))


# ---------- cross-validation ----------


def splits(y: np.ndarray):
    for r in range(REPEATS):
        yield from StratifiedKFold(FOLDS, shuffle=True, random_state=SEED + r).split(y, y)


def cross_validate(ds: Dataset, fit_predict) -> dict:
    """Macro-F1 etc. per repeat (each repeat predicts every invite once)."""
    n = len(ds.y)
    preds = np.full((REPEATS, n), -1)
    for k, (tr, te) in enumerate(splits(ds.y)):
        preds[k // FOLDS, te] = fit_predict(tr, te)
    f1s = [f1_score(ds.y, p, average="macro") for p in preds]
    per_class = np.mean([f1_score(ds.y, p, average=None) for p in preds], axis=0)
    zoom_acc = [accuracy_score(ds.y[ds.zoom], p[ds.zoom]) for p in preds] if ds.zoom.any() else []
    return {
        "macro_f1": float(np.mean(f1s)),
        "macro_f1_sd": float(np.std(f1s)),
        "accuracy": float(np.mean([accuracy_score(ds.y, p) for p in preds])),
        "per_class_f1": {lab: float(v) for lab, v in zip(LABELS, per_class, strict=True)},
        "confusion": confusion_matrix(ds.y, preds[0], labels=range(len(LABELS))).tolist(),
        "zoom_accuracy": float(np.mean(zoom_acc)) if zoom_acc else None,
    }


def run_all(ds: Dataset) -> list[dict]:
    results = []

    def record(family, name, params, fp):
        t = time.monotonic()
        res = cross_validate(ds, fp)
        res.update(family=family, name=name, params=params, seconds=round(time.monotonic() - t, 1))
        results.append(res)
        print(f"  {name:38s} macro-F1 {res['macro_f1']:.3f} ± {res['macro_f1_sd']:.3f}", flush=True)

    def best_params(family):
        best = max((r for r in results if r["family"] == family), key=lambda r: r["macro_f1"])
        return best["params"]["C"], best["params"]["class_weight"]

    print("Model A: TF-IDF + structure → logistic regression")
    linear = partial(fit_predict_linear, ds)
    for C in LINEAR_C:
        for cw in CLASS_WEIGHTS:
            fp = partial(linear, C=C, cw=cw)
            record("linear", f"linear C={C} cw={cw}", {"C": C, "class_weight": cw}, fp)
    C, cw = best_params("linear")
    params = {"C": C, "class_weight": cw}
    record("ablation", "linear text only", params, partial(linear, C=C, cw=cw, use_structure=False))
    record("ablation", "linear structure only", params, partial(linear, C=C, cw=cw, use_text=False))

    for model in model_names():
        print(f"Model B: {model} embedding + structure → logistic regression")
        emb = partial(fit_predict_embed, ds, embed_cached(ds.texts, model))
        for C in EMBED_C:
            for cw in CLASS_WEIGHTS:
                params = {"model": model, "C": C, "class_weight": cw}
                record(f"embed:{model}", f"{model} C={C} cw={cw}", params, partial(emb, C=C, cw=cw))
        C, cw = best_params(f"embed:{model}")
        params = {"model": model, "C": C, "class_weight": cw}
        fp = partial(emb, C=C, cw=cw, use_structure=False)
        record("ablation", f"{model} embedding only", params, fp)
    return results


def select(results: list[dict]) -> dict:
    best = {}
    for fam in {r["family"] for r in results if r["family"] != "ablation"}:
        best[fam] = max((r for r in results if r["family"] == fam), key=lambda r: r["macro_f1"])
    m, b = best.get("embed:minilm"), best.get("embed:bge")
    embed_pick = (
        "bge" if (m and b and b["macro_f1"] - m["macro_f1"] >= EMBED_PICK_MARGIN) else "minilm"
    )
    return {
        "linear": best["linear"]["name"],
        "linear_params": best["linear"]["params"],
        "embedding_model": embed_pick,
        "embedding": best[f"embed:{embed_pick}"]["name"],
        "embedding_params": best[f"embed:{embed_pick}"]["params"],
        "rule": "MiniLM unless BGE beats it by >= 3 macro-F1 points in CV",
    }


# ---------- report ----------


def _row(r: dict) -> str:
    pc = r["per_class_f1"]
    z = f"{r['zoom_accuracy']:.0%}" if r["zoom_accuracy"] is not None else "–"
    return (
        f"| {r['name']} | **{r['macro_f1']:.3f}** ± {r['macro_f1_sd']:.3f} | {r['accuracy']:.1%} | "
        f"{pc['keep']:.2f} / {pc['shorter']:.2f} / {pc['email']:.2f} | {z} |"
    )


def write_report(ds: Dataset, results: list[dict], selected: dict) -> None:
    by_name = {r["name"]: r for r in results}
    counts = Counter(LABELS[i] for i in ds.y)
    best = sorted((r for r in results if r["family"] != "ablation"), key=lambda r: -r["macro_f1"])
    fam_best = {}
    for r in best:
        fam_best.setdefault(r["family"], r)
    md = [
        "# Model report",
        "",
        "Generated by `pipeline/train.py`. Don't edit by hand. Test-set results are added by "
        "`evaluate.py` once the models are frozen.",
        "",
        "## Data",
        "",
        f"- {len(ds.y)} labeled training invites (discards excluded): "
        + ", ".join(f"{lab} {counts[lab]}" for lab in LABELS),
        "- All model input is boilerplate-masked (`clean.py`).",
        f"- Repeated stratified {FOLDS}-fold cross-validation, {REPEATS} shuffles "
        f"({FOLDS * REPEATS} train/validate splits per config). Primary metric: macro-F1.",
        "",
        "## Best config per family (CV)",
        "",
        "| config | macro-F1 | accuracy | F1 keep / shorter / email | Zoom-format accuracy |",
        "|---|---|---|---|---|",
        *(_row(r) for r in fam_best.values()),
        "",
        "## Ablations (best config's settings)",
        "",
        "| config | macro-F1 | accuracy | F1 keep / shorter / email | Zoom-format accuracy |",
        "|---|---|---|---|---|",
        *(_row(r) for r in results if r["family"] == "ablation"),
        "",
        "## Selection",
        "",
        f"- Linear model: `{selected['linear']}`",
        f"- Embedding model: **{selected['embedding_model']}** (`{selected['embedding']}`). "
        f"Rule: {selected['rule']}.",
        "",
        "Confusion matrices (first CV shuffle; rows = your label, columns = prediction, "
        "order keep / shorter / email):",
        "",
    ]
    for key in ("linear", "embedding"):
        r = by_name[selected[key]]
        md += [f"- `{r['name']}`: `{r['confusion']}`"]
    md += ["", "## Every config", "", "| config | macro-F1 | accuracy | F1 k / s / e | Zoom acc |"]
    md += ["|---|---|---|---|---|", *(_row(r) for r in best)]
    DOCS.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    ds = load_dataset()
    print(f"{len(ds.y)} labeled invites: {dict(Counter(LABELS[i] for i in ds.y))}")
    results = run_all(ds)
    selected = select(results)
    CV_PATH.write_text(
        json.dumps({"seed": SEED, "folds": FOLDS, "repeats": REPEATS, "selected": selected,
                    "results": results}, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )  # fmt: skip
    write_report(ds, results, selected)
    print(f"Selected: {selected['linear']} · {selected['embedding']}")
    print(f"Wrote {CV_PATH} and {REPORT}")


if __name__ == "__main__":
    main()
