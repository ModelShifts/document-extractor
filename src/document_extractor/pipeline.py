"""High-level helpers used by the CLI and the web demo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import Settings
from .extract import extract
from .llm import get_llm, get_ocr
from .models import Answer, Document, ExtractionResult
from .pdf import NoTextLayerError, load_pdf
from .qa import ask
from .retrieval import get_retriever
from .schema import load_schema

_DOCS: dict[tuple[str, str], Document] = {}


def file_digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def load_document(path: str | Path, settings: Settings) -> Document:
    """Load a PDF, running OCR only when a page has no text layer. Results are memoised per file."""
    key = (file_digest(path), settings.backend)
    if key in _DOCS:
        return _DOCS[key]
    try:
        doc = load_pdf(path)
    except NoTextLayerError:
        ocr = get_ocr(settings)
        if ocr is None:
            raise
        doc = load_pdf(path, ocr=ocr)
    _DOCS[key] = doc
    return doc


def run_extract(path: str | Path, schema: str | Path, settings: Settings) -> ExtractionResult:
    doc = load_document(path, settings)
    return extract(doc, load_schema(schema), get_llm(settings), backend=settings.backend)


def run_ask(path: str | Path, question: str, settings: Settings) -> Answer:
    doc = load_document(path, settings)
    return ask(doc, question, get_llm(settings), get_retriever(settings), backend=settings.backend)


class ResultCache:
    """Small JSON cache keyed by file content, task and model. Used by the web demo."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def _path(self, path: str | Path, kind: str, key: str, settings: Settings) -> Path:
        tag = hashlib.sha256(f"{kind}|{key}|{settings.backend}|{settings.model_name}".encode()).hexdigest()[:16]
        return self.root / f"{file_digest(path)}-{kind}-{tag}.json"

    def get(self, path, kind: str, key: str, settings: Settings) -> dict | None:
        p = self._path(path, kind, key, settings)
        return json.loads(p.read_text()) if p.exists() else None

    def put(self, path, kind: str, key: str, settings: Settings, data: dict) -> None:
        p = self._path(path, kind, key, settings)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2))
