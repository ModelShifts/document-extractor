import json

from document_extractor.extract import extract
from document_extractor.grounding import ground
from document_extractor.pdf import load_pdf
from document_extractor.schema import load_schema

from conftest import truth


def verbatim_reply(name):
    """What a well-behaved model returns: values copied as printed on the page."""
    t = truth(name)["fields"]
    return {
        "invoice-northwind-classic": {
            "invoice_number": "NWP-2026-0412", "invoice_date": "14 March 2026", "due_date": "13 April 2026",
            "seller_name": "Northwind Parts Pte. Ltd.", "buyer_name": "Example Logistics Pte. Ltd.",
            "currency": "SGD", "subtotal": f"{t['subtotal']:,.2f}", "tax": f"{t['tax']:,.2f}",
            "total": f"{t['total']:,.2f}",
        },
    }[name]


def test_extract_types_and_sources(samples, fake_llm):
    name = "invoice-northwind-classic"
    llm = fake_llm("Here you go:\n```json\n" + json.dumps(verbatim_reply(name)) + "\n```")
    doc = load_pdf(samples / f"{name}.pdf")
    result = extract(doc, load_schema("invoice"), llm, backend="test")
    want = truth(name)["fields"]
    assert result.values() == want
    for field, fv in result.fields.items():
        assert fv.source is not None, field
        assert fv.source.page == 1
    assert result.fields["invoice_number"].source.text == "NWP-2026-0412"
    assert result.fields["total"].source.text.endswith(f"{want['total']:,.2f}")
    # the prompt carries the document text and the field list
    prompt = llm.prompts[0][1]["content"]
    assert "NWP-2026-0412" in prompt and "invoice_number (string)" in prompt


def test_normalised_values_are_still_grounded(samples, fake_llm):
    name = "invoice-demo-freight-compact"
    want = truth(name)["fields"]
    reply = dict(want)  # model returned ISO dates and plain floats instead of the printed text
    result = extract(load_pdf(samples / f"{name}.pdf"), load_schema("invoice"), fake_llm(json.dumps(reply)))
    assert result.values() == want
    assert result.fields["invoice_date"].source.text == "03.02.2026"
    assert result.fields["total"].source is not None


def test_missing_and_bad_json(samples, fake_llm):
    doc = load_pdf(samples / "contract-supply.pdf")
    result = extract(doc, load_schema("contract"), fake_llm("sorry, no idea"))
    assert all(fv.value is None and fv.source is None for fv in result.fields.values())


def test_hallucinated_value_has_no_source(samples):
    doc = load_pdf(samples / "invoice-northwind-classic.pdf")
    assert ground(doc, "ZZ-9999-XYZ", "ZZ-9999-XYZ") is None


def test_repeated_value_prefers_labelled_copy(samples):
    doc = load_pdf(samples / "contract-master-services.pdf")
    src = ground(doc, "Singapore", "Singapore", "string", hint="governing_law The jurisdiction whose laws govern")
    lines = [w for w in doc.words if w.page == src.page and abs(w.bbox[1] - src.bbox[1]) < 2]
    assert "governed" in " ".join(w.text for w in lines)
