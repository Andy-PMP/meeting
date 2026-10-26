"""Sentence embeddings from the exact quantized ONNX files the browser will load. No PyTorch.

    python pipeline\\embed.py --check    # download both models, embed a few sentences, print sims

Models are pinned in embed_models.json and downloaded once to pipeline/.cache/hf/. Embeddings
of the training texts are cached in pipeline/.cache/emb_<model>_<hash>.npy, keyed by the exact
texts, so CV reruns are instant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from functools import cache

import numpy as np

from paths import CACHE, PIPELINE

SPEC_PATH = PIPELINE / "embed_models.json"
BATCH = 32
# Windows without Developer Mode can't symlink; the HF cache then copies files, which is fine.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


@cache
def model_spec(name: str) -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))["models"][name]


def model_names() -> list[str]:
    return list(json.loads(SPEC_PATH.read_text(encoding="utf-8"))["models"])


@cache
def _load(name: str):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    s = model_spec(name)
    kw = {"repo_id": s["repo"], "revision": s["revision"], "cache_dir": CACHE / "hf"}
    tok = Tokenizer.from_file(hf_hub_download(filename="tokenizer.json", **kw))
    tok.no_truncation()
    tok.no_padding()
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    session = ort.InferenceSession(
        hf_hub_download(filename=s["onnx"], **kw), opts, providers=["CPUExecutionProvider"]
    )
    return tok, session


def windows(ids: list[int], cls_id: int, sep_id: int, max_tokens: int) -> list[list[int]]:
    """Split content token ids into [CLS] chunk [SEP] windows of at most max_tokens."""
    size = max_tokens - 2
    chunks = [ids[i : i + size] for i in range(0, len(ids), size)] or [[]]
    return [[cls_id, *c, sep_id] for c in chunks]


def _run(session, batch: list[list[int]]) -> np.ndarray:
    """last_hidden_state for a batch of id lists, right-padded with 0."""
    width = max(len(x) for x in batch)
    ids = np.zeros((len(batch), width), dtype=np.int64)
    mask = np.zeros_like(ids)
    for i, x in enumerate(batch):
        ids[i, : len(x)] = x
        mask[i, : len(x)] = 1
    feeds = {"input_ids": ids, "attention_mask": mask}
    if any(i.name == "token_type_ids" for i in session.get_inputs()):
        feeds["token_type_ids"] = np.zeros_like(ids)
    hidden = session.run(None, feeds)[0]
    return hidden, mask


def _pool(hidden: np.ndarray, mask: np.ndarray, how: str) -> np.ndarray:
    if how == "cls":
        return hidden[:, 0, :]
    m = mask[..., None].astype(hidden.dtype)
    return (hidden * m).sum(axis=1) / np.maximum(m.sum(axis=1), 1e-9)


def embed(texts: list[str], name: str) -> np.ndarray:
    """(n, dims) L2-normalized embeddings of the given (already masked) texts."""
    s = model_spec(name)
    tok, session = _load(name)
    cls_id, sep_id = tok.token_to_id("[CLS]"), tok.token_to_id("[SEP]")
    # Every window of every text, remembering which text it belongs to and its size.
    wins, owner = [], []
    for t_i, text in enumerate(texts):
        ids = tok.encode(" ".join(text.split()), add_special_tokens=False).ids
        for w in windows(ids, cls_id, sep_id, s["max_tokens"]):
            wins.append(w)
            owner.append(t_i)
    order = sorted(range(len(wins)), key=lambda i: len(wins[i]))  # similar lengths per batch
    pooled = np.zeros((len(wins), s["dims"]), dtype=np.float32)
    for b in range(0, len(order), BATCH):
        idx = order[b : b + BATCH]
        hidden, mask = _run(session, [wins[i] for i in idx])
        pooled[idx] = _pool(hidden, mask, s["pooling"])
    out = np.zeros((len(texts), s["dims"]), dtype=np.float32)
    weight = np.zeros(len(texts), dtype=np.float32)
    for w_i, t_i in enumerate(owner):
        n = len(wins[w_i])
        out[t_i] += pooled[w_i] * n
        weight[t_i] += n
    out /= weight[:, None]
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)


def embed_cached(texts: list[str], name: str) -> np.ndarray:
    key = hashlib.sha256(
        json.dumps([model_spec(name)["revision"], texts]).encode("utf-8")
    ).hexdigest()[:16]
    path = CACHE / f"emb_{name}_{key}.npy"
    if path.exists():
        return np.load(path)
    vecs = embed(texts, name)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(path, vecs)
    return vecs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", action="store_true", help="smoke test both models")
    args = ap.parse_args()
    if args.check:
        sents = [
            "Decide which vendor we pick before Friday.",
            "We need to choose a supplier by end of week.",
            "Happy hour on the roof at 5, drinks on us!",
        ]
        for name in model_names():
            v = embed(sents, name)
            sims = v @ v.T
            print(f"{name}: similar pair {sims[0, 1]:.3f} · unrelated pair {sims[0, 2]:.3f}")


if __name__ == "__main__":
    main()
