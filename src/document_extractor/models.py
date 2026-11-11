"""Data models shared by the extractor, the Q&A module and the web demo."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

BBox = tuple[float, float, float, float]  # x0, top, x1, bottom in PDF points, origin top-left


class Word(BaseModel):
    text: str
    page: int  # 1-based
    bbox: BBox


class Page(BaseModel):
    number: int  # 1-based
    width: float
    height: float
    words: list[Word] = Field(default_factory=list)
    ocr: bool = False  # True when the words came from OCR instead of the PDF text layer


class Document(BaseModel):
    path: str
    pages: list[Page]

    @property
    def words(self) -> list[Word]:
        return [w for p in self.pages for w in p.words]


class Source(BaseModel):
    page: int
    bbox: BBox
    text: str


class FieldValue(BaseModel):
    value: Any = None
    raw: str | None = None  # the text the model returned before type conversion
    source: Source | None = None


class ExtractionResult(BaseModel):
    file: str
    schema_name: str = Field(alias="schema")
    backend: str
    model: str
    fields: dict[str, FieldValue]

    model_config = {"populate_by_name": True}

    def values(self) -> dict[str, Any]:
        return {k: v.value for k, v in self.fields.items()}

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class Citation(BaseModel):
    n: int
    page: int
    bbox: BBox
    text: str


class Answer(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    backend: str
    model: str
    retriever: str
