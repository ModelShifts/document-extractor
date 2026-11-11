"""Split a document into passages and retrieve the ones relevant to a question.

Retrievers:

* ``embed`` with the ``hf`` backend: BAAI/bge-m3 dense embeddings (sentence-transformers).
* ``embed`` with the ``api`` backend: the endpoint's ``/v1/embeddings`` with ``MS_EMBED_MODEL``.
* ``bm25``: keyword ranking (rank-bm25). No model download, used by the tests and as a
  fallback when no embedding model is configured.

``MS_RETRIEVER=auto`` (default) picks ``embed`` when an embedding model is
available for the backend and ``bm25`` otherwise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median
from typing import Protocol

from .config import Settings
from .models import Document, Word
from .pdf import line_text, page_lines


@dataclass
class Passage:
    page: int
    text: str
    words: list[Word]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        ws = self.words
        return (round(min(w.bbox[0] for w in ws), 2), round(min(w.bbox[1] for w in ws), 2),
                round(max(w.bbox[2] for w in ws), 2), round(max(w.bbox[3] for w in ws), 2))


HEADING = re.compile(r"^(\d+(\.\d+)*\.?|[A-Z][A-Z ]{3,})\s+[A-Z]")


def chunk(doc: Document, max_chars: int = 600) -> list[Passage]:
    """Paragraph-like passages.

    A new passage starts at a vertical gap larger than a line height, at a numbered
    or upper-case heading (``7. Governing Law``), or when ``max_chars`` is reached.
    """
    passages: list[Passage] = []
    for page in doc.pages:
        lines = page_lines(page)
        if not lines:
            continue
        heights = [max(w.bbox[3] for w in ln) - min(w.bbox[1] for w in ln) for ln in lines]
        h = median(heights) or 10.0
        cur_words: list[Word] = []
        cur_text: list[str] = []
        prev_bottom = None
        for ln in lines:
            top = min(w.bbox[1] for w in ln)
            text = line_text(ln)
            gap = None if prev_bottom is None else top - prev_bottom
            too_long = sum(len(t) for t in cur_text) + len(text) > max_chars
            heading = bool(HEADING.match(text))
            if cur_words and ((gap is not None and gap > 0.9 * h) or too_long or heading):
                passages.append(Passage(page.number, "\n".join(cur_text), cur_words))
                cur_words, cur_text = [], []
            cur_words = cur_words + ln
            cur_text.append(text)
            prev_bottom = max(w.bbox[3] for w in ln)
        if cur_words:
            passages.append(Passage(page.number, "\n".join(cur_text), cur_words))
    return passages


class Retriever(Protocol):
    name: str

    def search(self, query: str, passages: list[Passage], k: int) -> list[Passage]: ...


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever:
    name = "bm25"

    def search(self, query: str, passages: list[Passage], k: int) -> list[Passage]:
        from rank_bm25 import BM25Okapi

        if not passages:
            return []
        bm25 = BM25Okapi([_tokens(p.text) or ["_"] for p in passages])
        scores = bm25.get_scores(_tokens(query))
        order = sorted(range(len(passages)), key=lambda i: -scores[i])
        return [passages[i] for i in order[:k]]


class _DenseRetriever:
    name = "embed"

    def embed(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - abstract
        raise NotImplementedError

    def search(self, query: str, passages: list[Passage], k: int) -> list[Passage]:
        import numpy as np

        if not passages:
            return []
        vecs = np.asarray(self.embed([query] + [p.text for p in passages]), dtype="float32")
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        scores = vecs[1:] @ vecs[0]
        order = np.argsort(-scores)[:k]
        return [passages[int(i)] for i in order]


class BGEM3Retriever(_DenseRetriever):
    def __init__(self, model_id: str):
        from sentence_transformers import SentenceTransformer

        self.name = f"embed:{model_id}"
        self.model = SentenceTransformer(model_id, device="cpu")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True, batch_size=16).tolist()


class APIEmbeddingRetriever(_DenseRetriever):
    def __init__(self, client, model: str):
        self.name = f"embed:{model}"
        self.client = client
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        response = self.client.embeddings.create(model=self.model, input=texts)
        out = []
        for d in response.data:
            vec = np.asarray(d.embedding, dtype="float32")
            if vec.ndim == 2:  # some local servers return one vector per token: mean-pool them
                vec = vec.mean(axis=0)
            out.append(vec.tolist())
        return out


_RETRIEVERS: dict[tuple, Retriever] = {}


def get_retriever(settings: Settings) -> Retriever:
    mode = settings.retriever
    if mode not in {"auto", "embed", "bm25"}:
        raise ValueError("MS_RETRIEVER must be auto, embed or bm25")
    if mode == "bm25" or (mode == "auto" and settings.backend == "api" and not settings.embed_model):
        return BM25Retriever()
    if settings.backend == "api" and not settings.embed_model:
        raise ValueError("MS_RETRIEVER=embed with MS_BACKEND=api needs MS_EMBED_MODEL")
    key = (settings.backend, settings.hf_embed_model, settings.embed_model, settings.api_base)
    if key not in _RETRIEVERS:
        if settings.backend == "hf":
            _RETRIEVERS[key] = BGEM3Retriever(settings.hf_embed_model)
        else:
            from .llm import get_llm

            _RETRIEVERS[key] = APIEmbeddingRetriever(get_llm(settings).client, settings.embed_model)  # type: ignore[attr-defined]
    return _RETRIEVERS[key]
