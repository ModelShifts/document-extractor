"""Question answering over one document, with cited passages."""

from __future__ import annotations

import re

from .llm import LLM
from .models import Answer, Citation, Document
from .retrieval import Passage, Retriever, chunk

SYSTEM = (
    "You answer questions about a business document using only the numbered passages you are given. "
    "Write the answer as one short sentence, then put the number of the passage you used in square "
    "brackets at the end. Example: The term is 24 months [2]. "
    "Only if none of the passages answers the question, reply: Not found in the document."
)


def build_prompt(question: str, passages: list[Passage]) -> list[dict[str, str]]:
    blocks = [f"[{i}] (page {p.page})\n{p.text}" for i, p in enumerate(passages, start=1)]
    user = (
        "Passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}\n"
        "Answer in one sentence, ending with the passage number in brackets."
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def _content_tokens(text: str) -> set[str]:
    text = re.sub(r"\[\d+\]", " ", text.lower())
    return {t for t in re.findall(r"[a-z0-9][a-z0-9,.\-]*[a-z0-9]|\d", text) if any(c.isdigit() for c in t) or len(t) > 3}


def _repair_citations(reply: str, passages: list[Passage], cited: list[int]) -> tuple[list[int], dict[int, int]]:
    """Small models sometimes cite the wrong number. If another retrieved passage shares at
    least two more content words with the answer than the cited one, cite that one instead."""
    words = _content_tokens(reply)
    if not words:
        return cited, {}
    overlap = [len(words & _content_tokens(p.text)) for p in passages]
    fixed, moved = [], {}
    for i in cited:
        best = max(range(len(passages)), key=lambda j: overlap[j])
        if overlap[best] >= overlap[i - 1] + 2:
            moved[i] = best + 1
            i = best + 1
        if i not in fixed:
            fixed.append(i)
    return fixed, moved


def ask(doc: Document, question: str, llm: LLM, retriever: Retriever, k: int = 4, backend: str = "") -> Answer:
    passages = retriever.search(question, chunk(doc), k)
    reply = llm.complete(build_prompt(question, passages), max_new_tokens=200).strip()
    if reply.lower().startswith("not found"):
        reply = "Not found in the document."
    cited = []
    for n in re.findall(r"\[(\d+)\]", reply):
        i = int(n)
        if 1 <= i <= len(passages) and i not in cited:
            cited.append(i)
    if not cited and passages and not reply.lower().startswith("not found"):
        cited = [1]  # model forgot to cite: point at the top-ranked passage
    cited, moved = _repair_citations(reply, passages, cited)
    if moved:  # keep the numbers in the answer text in step with the citations
        reply = re.sub(r"\[(\d+)\]", lambda m: f"[{moved.get(int(m.group(1)), int(m.group(1)))}]", reply)
    if reply == "Not found in the document.":
        cited = []
    citations = [
        Citation(n=i, page=passages[i - 1].page, bbox=passages[i - 1].bbox, text=passages[i - 1].text)
        for i in cited
    ]
    return Answer(
        question=question,
        answer=reply,
        citations=citations,
        backend=backend,
        model=getattr(llm, "name", "unknown"),
        retriever=retriever.name,
    )
