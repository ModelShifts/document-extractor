"""Schema-driven field extraction with a source for every value."""

from __future__ import annotations

from pathlib import Path

from .grounding import ground
from .llm import LLM, parse_json_object
from .models import Document, ExtractionResult, FieldValue
from .pdf import document_text
from .schema import Schema, coerce

SYSTEM = (
    "You extract fields from business documents. Reply with a single JSON object and nothing else."
)

MAX_DOC_CHARS = 12000


def build_prompt(doc: Document, schema: Schema) -> list[dict[str, str]]:
    lines = [f"- {f.name} ({f.type}): {f.description}" for f in schema.fields]
    text = document_text(doc)
    if len(text) > MAX_DOC_CHARS:
        text = text[:MAX_DOC_CHARS] + "\n[...truncated]"
    example = "{" + ", ".join(f'"{f.name}": "..."' for f in schema.fields[:2]) + ", ...}"
    user = (
        f"Document type: {schema.name}. {schema.description}\n\n"
        "Fields to extract:\n" + "\n".join(lines) + "\n\n"
        "Rules:\n"
        "- Copy each value exactly as it is written in the document: same spelling, number format and "
        "date format. Do not convert or calculate.\n"
        "- For amounts, copy only the number (for example 1,234.50), not the currency code.\n"
        "- Use null if a field is not in the document.\n"
        f"- Reply with one JSON object with exactly these keys: {', '.join(schema.field_names)}.\n"
        f"  Example shape: {example}\n\n"
        "Document text (columns separated by |):\n<<<\n" + text + "\n>>>"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def extract(doc: Document, schema: Schema, llm: LLM, backend: str = "") -> ExtractionResult:
    """Ask the model for the schema fields, convert types and attach sources."""
    reply = llm.complete(build_prompt(doc, schema))
    try:
        data = parse_json_object(reply)
    except ValueError:
        data = {}
    fields: dict[str, FieldValue] = {}
    for spec in schema.fields:
        raw = data.get(spec.name)
        if isinstance(raw, (dict, list)):
            raw = None
        raw_text = None if raw is None else str(raw)
        value = coerce(raw, spec.type)
        source = None
        if value is not None:
            source = ground(doc, raw_text, value, spec.type, hint=f"{spec.name} {spec.description}")
        fields[spec.name] = FieldValue(value=value, raw=raw_text, source=source)
    return ExtractionResult(
        file=Path(doc.path).name,
        schema=schema.name,
        backend=backend,
        model=getattr(llm, "name", "unknown"),
        fields=fields,
    )
