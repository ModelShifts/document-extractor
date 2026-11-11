import pytest

from document_extractor.schema import coerce, load_schema, parse_date, parse_integer, parse_number


def test_bundled_schemas_load():
    inv = load_schema("invoice")
    con = load_schema("schemas/contract.yaml")
    assert "total" in inv.field_names and inv.name == "invoice"
    assert "notice_period_days" in con.field_names


@pytest.mark.parametrize("text,want", [
    ("14 March 2026", "2026-03-14"),
    ("2026-05-02", "2026-05-02"),
    ("03.02.2026", "2026-02-03"),
    ("20/01/2026", "2026-01-20"),
    ("March 14, 2026", "2026-03-14"),
    ("1st July 2026", "2026-07-01"),
    ("soon", None),
])
def test_parse_date(text, want):
    assert parse_date(text) == want


@pytest.mark.parametrize("text,want", [
    ("5,496.68", 5496.68), ("SGD 453.85", 453.85), ("1.234,56", 1234.56), ("12,50", 12.5), ("n/a", None),
])
def test_parse_number(text, want):
    assert parse_number(text) == want


@pytest.mark.parametrize("text,want", [
    ("sixty (60) days", 60), ("24 months", 24), ("twelve months", 12), ("45", 45),
])
def test_parse_integer(text, want):
    assert parse_integer(text) == want


def test_coerce_nulls():
    assert coerce(None, "string") is None
    assert coerce("null", "number") is None
    assert coerce(12, "number") == 12.0
