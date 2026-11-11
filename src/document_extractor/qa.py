"""Question answering over one document, with cited passages."""

from __future__ import annotations

import re

from .llm import LLM
from .models import Answer, Citation, Document
from .retrieval import Passage, Retriever, chunk

SYSTEM = (
    "You answer questions about a business document using only the numbered passages you are given. "
    "Keep answers short (one or two sentences). After each fact, cite the passage number in square "
    "brackets, for example [2]. If the passages do not contain the answer, reply exactly: "
    "Not found in the document."
)


def build_prompt(question: str, passages: list[Passage]) -> list[dict[str, str]]:
    blocks = [f"[{i}] (page {p.page})\n{p.text}" for i, p in enumerate(passages, start=1)]
    user = "Passages:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}\nAnswer:"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def ask(doc: Document, question: str, llm: LLM, retriever: Retriever, k: int = 4, backend: str = "") -> Answer:
    passages = retriever.search(question, chunk(doc), k)
    reply = llm.complete(build_prompt(question, passages), max_new_tokens=200).strip()
    cited = []
    for n in re.findall(r"\[(\d+)\]", reply):
        i = int(n)
        if 1 <= i <= len(passages) and i not in cited:
            cited.append(i)
    if not cited and passages and not reply.lower().startswith("not found"):
        cited = [1]  # model forgot to cite: point at the top-ranked passage
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
