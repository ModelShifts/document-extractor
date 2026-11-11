"""Link an extracted value back to the words on the page it came from.

The model is asked to copy values exactly as written. We then look for the
best matching run of consecutive words on any page. If the model normalised a
value (for example ``2026-03-14`` instead of ``14 March 2026``), common
spellings of the typed value are tried as well.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Iterable

from .models import Document, Source, Word
from .pdf import page_lines

STRIP = " \t.,:;()[]{}\"'|*"
MIN_SCORE = 0.86
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


def norm(token: str) -> str:
    return token.strip(STRIP).lower()


def _key(tokens: Iterable[str]) -> str:
    return " ".join(t for t in (norm(x) for x in tokens) if t)


def variants(raw: str | None, value: Any, ftype: str) -> list[str]:
    """Candidate spellings to search for, most specific first."""
    out: list[str] = []
    if raw:
        out.append(str(raw))
    if value is not None and ftype == "number":
        x = float(value)
        out += [f"{x:,.2f}", f"{x:.2f}", f"{x:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")]
    elif value is not None and ftype == "date":
        y, m, d = (int(v) for v in str(value).split("-"))
        mon = MONTH_NAMES[m - 1]
        out += [str(value), f"{d} {mon} {y}", f"{d:02d}/{m:02d}/{y}", f"{d:02d}.{m:02d}.{y}", f"{mon} {d}, {y}",
                f"{d} {mon[:3]} {y}"]
    elif value is not None and ftype == "integer":
        out += [f"({value})", str(value)]
    elif value is not None:
        out.append(str(value))
    seen, uniq = set(), []
    for v in out:
        if v and v not in seen:
            seen.add(v)
            uniq.append(v)
    return uniq


def _union(words: list[Word]) -> tuple[float, float, float, float]:
    return (round(min(w.bbox[0] for w in words), 2), round(min(w.bbox[1] for w in words), 2),
            round(max(w.bbox[2] for w in words), 2), round(max(w.bbox[3] for w in words), 2))


def _reading_order(doc: Document) -> list[Word]:
    ordered: list[Word] = []
    for page in doc.pages:
        for line in page_lines(page):
            ordered.extend(line)
    return ordered


STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "by", "is", "as", "at", "this", "that",
        "which", "who", "with", "from", "be", "it", "its", "date", "name"}


def _stems(text: str) -> set[str]:
    out = set()
    for t in text.replace("_", " ").split():
        t = norm(t)
        if len(t) > 3 and t.endswith("s"):
            t = t[:-1]
        if len(t) > 2 and t not in STOP:
            out.add(t[:5])
    return out


def _context_score(span: list[Word], words: list[Word], hint: set[str]) -> int:
    """How many hint words appear just before the span on the same page (label proximity)."""
    if not hint:
        return 0
    first = words.index(span[0])
    before = [w for w in words[max(0, first - 12) : first] if w.page == span[0].page]
    return len(hint & _stems(" ".join(w.text for w in before)))


def find_span(
    doc: Document, text: str, words: list[Word] | None = None, hint: str = ""
) -> tuple[float, list[Word]] | None:
    """Best matching run of words for ``text``: (score, words) or ``None``.

    When the same text appears more than once, the copy whose preceding words
    share the most terms with ``hint`` (field name and description) wins.
    """
    target = _key(text.split())
    if not target:
        return None
    words = words if words is not None else _reading_order(doc)
    n = len(target.split())
    hint_stems = _stems(hint)
    exact: list[list[Word]] = []
    best: tuple[float, list[Word]] | None = None
    for size in sorted({n, max(1, n - 1), n + 1}):
        for i in range(0, len(words) - size + 1):
            span = words[i : i + size]
            if len({w.page for w in span}) > 1:
                continue
            cand = _key(w.text for w in span)
            if not cand:
                continue
            if cand == target:
                score = 1.0
            elif size == 1 and n == 1 and target in cand and len(target) >= 4:
                score = 0.95  # value printed inside a longer token, e.g. "SGD5,496.68"
            else:
                score = SequenceMatcher(None, cand, target).ratio()
            if score == 1.0:
                exact.append(span)
            elif best is None or score > best[0] + 1e-9:
                best = (score, span)
    if exact:
        ranked = sorted(enumerate(exact), key=lambda e: (-_context_score(e[1], words, hint_stems), e[0]))
        return 1.0, ranked[0][1]
    return best


def ground(doc: Document, raw: str | None, value: Any, ftype: str = "string", hint: str = "") -> Source | None:
    """Return the page, box and text of the best match, or ``None`` if nothing is close enough."""
    words = _reading_order(doc)
    best: tuple[float, list[Word]] | None = None
    for candidate in variants(raw, value, ftype):
        found = find_span(doc, candidate, words, hint)
        if found and (best is None or found[0] > best[0]):
            best = found
        if best and best[0] == 1.0:
            break
    if not best or best[0] < MIN_SCORE:
        return None
    span = best[1]
    return Source(page=span[0].page, bbox=_union(span), text=" ".join(w.text for w in span))
