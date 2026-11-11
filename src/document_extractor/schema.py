"""YAML field schemas and type conversion.

A schema file looks like::

    name: invoice
    description: A commercial invoice.
    fields:
      invoice_number: {type: string, description: The invoice identifier}
      total: {type: number, description: The final amount due}

Supported types: ``string``, ``date`` (ISO ``YYYY-MM-DD`` output), ``number``
(float) and ``integer``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

TYPES = {"string", "date", "number", "integer"}
PACKAGE_SCHEMAS = Path(__file__).resolve().parent / "schemas"  # wheel installs
REPO_SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"  # source checkout / editable install


@dataclass
class FieldSpec:
    name: str
    type: str
    description: str


@dataclass
class Schema:
    name: str
    description: str
    fields: list[FieldSpec]

    @property
    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]


def resolve_schema_path(name_or_path: str | Path) -> Path:
    """Accept a path, or a bare name like ``invoice`` for a bundled schema."""
    p = Path(name_or_path)
    if p.exists():
        return p
    stem = Path(name_or_path).stem
    for folder in (Path("schemas"), REPO_SCHEMAS, PACKAGE_SCHEMAS):
        candidate = folder / f"{stem}.yaml"
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"schema not found: {name_or_path}")


def load_schema(name_or_path: str | Path) -> Schema:
    path = resolve_schema_path(name_or_path)
    data = yaml.safe_load(path.read_text())
    fields = []
    for name, spec in (data.get("fields") or {}).items():
        spec = spec or {}
        ftype = str(spec.get("type", "string"))
        if ftype not in TYPES:
            raise ValueError(f"{path}: field {name!r} has unknown type {ftype!r} (use one of {sorted(TYPES)})")
        fields.append(FieldSpec(name=name, type=ftype, description=str(spec.get("description", ""))))
    if not fields:
        raise ValueError(f"{path}: schema has no fields")
    return Schema(name=str(data.get("name", path.stem)), description=str(data.get("description", "")), fields=fields)


# --------------------------------------------------------------------------- #
# Type conversion
# --------------------------------------------------------------------------- #
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "forty-five": 45, "sixty": 60, "ninety": 90,
}


def parse_date(text: str) -> str | None:
    s = text.strip().lower().replace(",", " ")
    if m := re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s):
        y, mo, d = map(int, m.groups())
    elif m := re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b", s):
        d, mo, y = map(int, m.groups())  # day-first, as on the sample documents
        if mo > 12 and d <= 12:
            d, mo = mo, d
    elif m := re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s+(\d{4})\b", s):
        d, mon, y = int(m.group(1)), m.group(2), int(m.group(3))
        if mon not in MONTHS:
            return None
        mo = MONTHS[mon]
    elif m := re.search(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})\b", s):
        mon, d, y = m.group(1), int(m.group(2)), int(m.group(3))
        if mon not in MONTHS:
            return None
        mo = MONTHS[mon]
    else:
        return None
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_number(text: str) -> float | None:
    s = re.sub(r"[^\d,.\-]", "", str(text))
    if not re.search(r"\d", s):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:  # 1,234.56
            s = s.replace(",", "")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = s.replace(",", "") if len(tail) == 3 else f"{head.replace(',', '')}.{tail}"
    try:
        return float(s)
    except ValueError:
        return None


def parse_integer(text: str) -> int | None:
    s = str(text).lower()
    if m := re.search(r"\(\s*(\d+)\s*\)", s):
        return int(m.group(1))
    if m := re.search(r"-?\d[\d,]*", s):
        return int(m.group(0).replace(",", ""))
    for word, n in sorted(WORD_NUMBERS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{word}\b", s):
            return n
    return None


def coerce(value: Any, ftype: str) -> Any:
    """Convert a raw model value to the schema type. Returns ``None`` when it cannot."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "null", "none", "n/a", "not found"}:
        return None
    if ftype == "string":
        return str(value).strip()
    if ftype == "date":
        return parse_date(str(value))
    if ftype == "number":
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else parse_number(value)
    if ftype == "integer":
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else parse_integer(str(value))
    return value
