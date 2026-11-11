import csv
import json

from document_extractor import cli
from document_extractor.pdf import load_pdf
from document_extractor.qa import ask
from document_extractor.retrieval import BM25Retriever, chunk

from conftest import FakeLLM, truth


def test_chunks_cover_pages(samples):
    doc = load_pdf(samples / "contract-master-services.pdf")
    passages = chunk(doc)
    assert len(passages) > 3
    assert any("sixty (60) days" in p.text for p in passages)


def test_ask_cites_retrieved_passage(samples):
    doc = load_pdf(samples / "contract-master-services.pdf")
    llm = FakeLLM("The notice period starts on the day the notice is received [1].")
    answer = ask(doc, "When does the notice period start?", llm, BM25Retriever())
    assert answer.citations and answer.citations[0].n == 1
    assert "notice" in answer.citations[0].text.lower()
    assert answer.retriever == "bm25"
    assert "Passages:" in llm.prompts[0][1]["content"]


def test_ask_not_found_has_no_citation(samples):
    doc = load_pdf(samples / "contract-supply.pdf")
    answer = ask(doc, "What colour is the logo?", FakeLLM("Not found in the document."), BM25Retriever())
    assert answer.citations == []
    stray = ask(doc, "What colour is the logo?", FakeLLM("Not found in the document. [2]"), BM25Retriever())
    assert stray.answer == "Not found in the document." and stray.citations == []


def _patch_llm(monkeypatch):
    from document_extractor import pipeline

    def fake_get_llm(settings):
        def reply_for(messages):
            content = messages[1]["content"]
            for t in ("invoice-northwind-classic", "invoice-example-logistics-banner"):
                fields = truth(t)["fields"]
                if fields["invoice_number"] in content:
                    return json.dumps(fields)
            return "{}"

        class L:
            name = "fake-llm"

            def complete(self, messages, max_new_tokens=None):
                return reply_for(messages)

        return L()

    monkeypatch.setattr(pipeline, "get_llm", fake_get_llm)
    monkeypatch.setenv("MS_BACKEND", "api")
    monkeypatch.setenv("MS_API_BASE", "http://localhost:0/v1")
    monkeypatch.setenv("MS_MODEL", "fake")


def test_cli_extract(samples, monkeypatch, capsys):
    _patch_llm(monkeypatch)
    assert cli.main(["extract", str(samples / "invoice-northwind-classic.pdf"), "--schema", "invoice"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == "invoice"
    assert out["fields"]["invoice_number"]["source"]["page"] == 1


def test_cli_batch_csv_and_json(samples, monkeypatch, tmp_path):
    _patch_llm(monkeypatch)
    folder = tmp_path / "in"
    folder.mkdir()
    for n in ("invoice-northwind-classic", "invoice-example-logistics-banner", "invoice-acme-scanned"):
        (folder / f"{n}.pdf").write_bytes((samples / f"{n}.pdf").read_bytes())
    out_csv = tmp_path / "results.csv"
    assert cli.main(["batch", str(folder), "--schema", "invoice", "--out", str(out_csv)]) == 0
    rows = list(csv.DictReader(out_csv.open()))
    assert len(rows) == 3
    by_file = {r["file"]: r for r in rows}
    assert by_file["invoice-northwind-classic.pdf"]["invoice_number"] == "NWP-2026-0412"
    assert "no text layer" in by_file["invoice-acme-scanned.pdf"]["error"]  # api backend without a vision model
    out_json = tmp_path / "results.json"
    assert cli.main(["batch", str(folder), "--schema", "invoice", "--out", str(out_json)]) == 0
    assert len(json.loads(out_json.read_text())) == 2


def test_cli_bad_backend(monkeypatch, capsys, samples):
    monkeypatch.setenv("MS_BACKEND", "nope")
    assert cli.main(["extract", str(samples / "contract-supply.pdf"), "--schema", "contract"]) == 2
    assert "MS_BACKEND" in capsys.readouterr().err


def test_wrong_citation_number_is_repaired(samples):
    doc = load_pdf(samples / "contract-master-services.pdf")
    retriever = BM25Retriever()
    passages = retriever.search("When does the notice period start?", chunk(doc), 4)
    wrong = next(i for i, p in enumerate(passages, 1) if "received" not in p.text)
    llm = FakeLLM(f"The notice period starts on the day the notice is received [{wrong}].")
    answer = ask(doc, "When does the notice period start?", llm, retriever)
    assert "received" in answer.citations[0].text
    assert f"[{answer.citations[0].n}]" in answer.answer
