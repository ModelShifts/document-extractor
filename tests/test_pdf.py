import pytest

from document_extractor.pdf import NoTextLayerError, document_text, load_pdf, render_page


def test_words_have_page_and_bbox(samples):
    doc = load_pdf(samples / "invoice-placeholder-two-page.pdf")
    assert [p.number for p in doc.pages] == [1, 2]
    for page in doc.pages:
        assert page.words
        for w in page.words:
            x0, top, x1, bottom = w.bbox
            assert w.page == page.number
            assert 0 <= x0 < x1 <= page.width
            assert 0 <= top < bottom <= page.height


def test_document_text_has_page_markers(samples):
    text = document_text(load_pdf(samples / "invoice-placeholder-two-page.pdf"))
    assert "[Page 1]" in text and "[Page 2]" in text
    assert "PS-INV-30027" in text


def test_scanned_pdf_without_ocr_gives_clear_message(samples):
    with pytest.raises(NoTextLayerError) as err:
        load_pdf(samples / "invoice-acme-scanned.pdf")
    assert "MS_VISION_MODEL" in str(err.value) and "MS_BACKEND=hf" in str(err.value)


def test_scanned_pdf_uses_ocr_engine(samples):
    from document_extractor.models import Word

    class FakeOCR:
        name = "fake-ocr"

        def recognise(self, image, page, scale):
            assert image.width > 500
            return [Word(text="AES-5120", page=page, bbox=(100, 100, 160, 112))]

    doc = load_pdf(samples / "invoice-acme-scanned.pdf", ocr=FakeOCR())
    assert doc.pages[0].ocr is True
    assert doc.pages[0].words[0].text == "AES-5120"


def test_render_page(samples):
    img = render_page(samples / "invoice-northwind-classic.pdf", 1, scale=1.0)
    assert abs(img.width - 595) <= 1 and abs(img.height - 842) <= 1
