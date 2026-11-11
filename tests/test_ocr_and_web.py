from document_extractor.ocr import parse_vision_lines, split_line


def test_split_line_shares_box():
    words = split_line("Total SGD 5,689.11", (100, 10, 280, 22), page=1)
    assert [w.text for w in words] == ["Total", "SGD", "5,689.11"]
    assert words[0].bbox[0] == 100 and abs(words[-1].bbox[2] - 280) < 1e-6
    assert all(w.bbox[1] == 10 and w.bbox[3] == 22 for w in words)


def test_parse_vision_lines_scales_to_points():
    content = 'Sure: [{"text": "Invoice No. AES-5120", "box": [100, 200, 400, 220]}]'
    words = parse_vision_lines(content, size=(1190, 1684), page=1, scale=2.0)
    assert words[0].text == "Invoice" and words[-1].text == "AES-5120"
    assert abs(words[0].bbox[0] - 59.5) < 0.01  # 100/1000 * 595 pt


def test_draw_document_marks_boxes(samples):
    from document_extractor.webapp import draw_document

    plain = draw_document(samples / "invoice-placeholder-two-page.pdf", [])
    marked = draw_document(samples / "invoice-placeholder-two-page.pdf", [(2, (300, 300, 400, 320), "1", "field")])
    assert plain.size == marked.size and plain.height > plain.width  # two pages stacked
    assert plain.tobytes() != marked.tobytes()
