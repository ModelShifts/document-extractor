"""PDF loading: words with page numbers and bounding boxes, plus page images.

Text-layer PDFs are read with pdfplumber. Pages without a text layer (scans)
are rendered with pypdfium2 and passed to an OCR engine (see ``ocr.py``).
Coordinates are PDF points with the origin at the top-left of the page.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

from .models import Document, Page, Word

if TYPE_CHECKING:  # pragma: no cover
    from .ocr import OCREngine

MIN_TEXT_WORDS = 3  # fewer words than this on a page with an image -> treat as a scan
OCR_SCALE = 2.0  # render scale for OCR (2.0 = 144 dpi)


def render_page(path: str | Path, page_number: int, scale: float = 2.0) -> Image.Image:
    """Render one page (1-based) to an RGB image. ``scale`` is pixels per PDF point."""
    pdf = pdfium.PdfDocument(str(path))
    try:
        return pdf[page_number - 1].render(scale=scale).to_pil().convert("RGB")
    finally:
        pdf.close()


def load_pdf(path: str | Path, ocr: "OCREngine | None" = None) -> Document:
    """Read every page of ``path`` into a :class:`Document`.

    If a page has no usable text layer, ``ocr`` is used to recognise it. When no
    OCR engine is given, :class:`NoTextLayerError` explains how to enable one.
    """
    path = Path(path)
    pages: list[Page] = []
    with pdfplumber.open(str(path)) as pdf:
        for i, p in enumerate(pdf.pages, start=1):
            words = [
                Word(text=w["text"], page=i, bbox=(float(w["x0"]), float(w["top"]), float(w["x1"]), float(w["bottom"])))
                for w in p.extract_words(keep_blank_chars=False, use_text_flow=False)
            ]
            page = Page(number=i, width=float(p.width), height=float(p.height), words=words)
            if len(words) < MIN_TEXT_WORDS and (p.images or not words):
                if ocr is None:
                    raise NoTextLayerError(path.name, i)
                image = render_page(path, i, scale=OCR_SCALE)
                page.words = ocr.recognise(image, page=i, scale=OCR_SCALE)
                page.ocr = True
            pages.append(page)
    return Document(path=str(path), pages=pages)


def has_text_layer(path: str | Path) -> bool:
    with pdfplumber.open(str(path)) as pdf:
        return all(len(p.extract_words()) >= MIN_TEXT_WORDS for p in pdf.pages)


class NoTextLayerError(RuntimeError):
    def __init__(self, name: str, page: int):
        super().__init__(
            f"{name}, page {page}: this page has no text layer (it looks like a scan) and no OCR engine is "
            "configured. Use MS_BACKEND=hf (Florence-2 OCR) or set MS_VISION_MODEL for MS_BACKEND=api."
        )
        self.page = page


def page_lines(page: Page, y_tolerance: float = 3.0) -> list[list[Word]]:
    """Group a page's words into visual lines, top to bottom, left to right."""
    lines: list[list[Word]] = []
    for w in sorted(page.words, key=lambda w: (w.bbox[1], w.bbox[0])):
        mid = (w.bbox[1] + w.bbox[3]) / 2
        for line in lines:
            ref = line[0]
            if abs(mid - (ref.bbox[1] + ref.bbox[3]) / 2) <= y_tolerance:
                line.append(w)
                break
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w.bbox[0])
    lines.sort(key=lambda ln: min(w.bbox[1] for w in ln))
    return lines


def line_text(line: list[Word], gap: float = 14.0) -> str:
    """Join a line's words; wide horizontal gaps become ``" | "`` so table columns stay apart."""
    out = ""
    prev: Word | None = None
    for w in line:
        if prev is not None:
            out += " | " if w.bbox[0] - prev.bbox[2] > gap else " "
        out += w.text
        prev = w
    return out


def document_text(doc: Document) -> str:
    """Plain-text view of the document used in prompts, with page markers."""
    parts = []
    for page in doc.pages:
        parts.append(f"[Page {page.number}]")
        parts.extend(line_text(line) for line in page_lines(page))
    return "\n".join(parts)
