"""Local web demo (Gradio): pick or upload a PDF, extract fields, see sources, ask questions."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .config import Settings
from .models import Answer, ExtractionResult
from .pdf import NoTextLayerError, render_page
from .pipeline import ResultCache, run_ask, run_extract

import pypdfium2 as pdfium

RENDER_SCALE = 1.6
FIELD_COLOUR = (138, 58, 36)  # rust
CITE_COLOUR = (28, 26, 23)  # ink
CITE_FILL = (231, 196, 92, 90)  # soft amber
PAGE_GAP = 18


def samples_dir() -> Path:
    for d in (Path.cwd() / "samples", Path(__file__).resolve().parents[2] / "samples"):
        if d.is_dir():
            return d
    return Path.cwd() / "samples"


def list_samples() -> list[str]:
    return sorted(p.name for p in samples_dir().glob("*.pdf"))


def guess_schema(path: str | Path) -> str:
    truth = Path(path).with_suffix(".truth.json")
    if truth.exists():
        return json.loads(truth.read_text())["schema"]
    return "contract" if "contract" in Path(path).name.lower() or "agreement" in Path(path).name.lower() else "invoice"


def _font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_document(path: str | Path, boxes: list[tuple[int, tuple, str, str]]) -> Image.Image:
    """Render all pages stacked vertically with highlighted boxes.

    ``boxes``: (page, bbox in points, label, kind) where kind is ``field`` or ``cite``.
    """
    n_pages = len(pdfium.PdfDocument(str(path)))
    pages = [render_page(path, i, RENDER_SCALE).convert("RGBA") for i in range(1, n_pages + 1)]
    font = _font(13)
    out_pages = []
    for i, img in enumerate(pages, start=1):
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        for page, bbox, label, kind in boxes:
            if page != i:
                continue
            x0, y0, x1, y1 = (v * RENDER_SCALE for v in bbox)
            pad = 3
            rect = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
            if kind == "cite":
                d.rectangle(rect, fill=CITE_FILL, outline=CITE_COLOUR + (220,), width=2)
            else:
                d.rectangle(rect, fill=FIELD_COLOUR + (38,), outline=FIELD_COLOUR + (255,), width=2)
            if label:
                tw = d.textlength(label, font=font)
                lx, ly = rect[0], rect[1] - 18
                if ly < 0:
                    ly = rect[3] + 2
                colour = CITE_COLOUR if kind == "cite" else FIELD_COLOUR
                d.rounded_rectangle((lx, ly, lx + tw + 10, ly + 17), radius=4, fill=colour + (255,))
                d.text((lx + 5, ly + 1), label, font=font, fill=(255, 255, 255, 255))
        out_pages.append(Image.alpha_composite(img, overlay).convert("RGB"))
    width = max(p.width for p in out_pages)
    height = sum(p.height for p in out_pages) + PAGE_GAP * (len(out_pages) - 1)
    sheet = Image.new("RGB", (width, height), (232, 226, 214))
    y = 0
    for p in out_pages:
        sheet.paste(p, (0, y))
        y += p.height + PAGE_GAP
    return sheet


def field_rows(result: ExtractionResult) -> list[list]:
    rows = []
    for i, (name, fv) in enumerate(result.fields.items(), start=1):
        value = "" if fv.value is None else (f"{fv.value:,.2f}" if isinstance(fv.value, float) else str(fv.value))
        rows.append([i, name, value, fv.source.page if fv.source else "", fv.source.text if fv.source else "not found"])
    return rows


def field_boxes(result: ExtractionResult | None) -> list:
    if result is None:
        return []
    return [(fv.source.page, fv.source.bbox, str(i), "field")
            for i, fv in enumerate(result.fields.values(), start=1) if fv.source]


def cite_boxes(answer: Answer | None) -> list:
    if answer is None:
        return []
    return [(c.page, c.bbox, f"[{c.n}]", "cite") for c in answer.citations]


def answer_markdown(answer: Answer) -> str:
    lines = [f"**{answer.answer}**", ""]
    for c in answer.citations:
        snippet = " ".join(c.text.split())
        if len(snippet) > 220:
            snippet = snippet[:217] + "..."
        lines.append(f"[{c.n}] page {c.page}: {snippet}")
        lines.append("")
    lines.append(f"<span class='ms-muted'>Retriever: {answer.retriever} · Model: {answer.model}</span>")
    return "\n".join(lines)


CSS = """
:root, .gradio-container { --ms-ink:#1c1a17; --ms-rust:#8a3a24; --ms-paper:#f3efe6; --ms-cream:#faf7f0; }
.gradio-container { background: var(--ms-cream) !important; font-family: Georgia, 'Times New Roman', serif !important; max-width: 1240px !important; }
.ms-header { border-bottom: 1px solid var(--ms-ink); padding: 18px 4px 14px; margin-bottom: 6px; }
.ms-brand { letter-spacing: .22em; font-size: 12px; color: var(--ms-rust); font-weight: 700; }
.ms-header h1 { font-family: Georgia, serif; font-weight: 400; font-size: 34px; margin: 4px 0 2px; color: var(--ms-ink); }
.ms-header p { margin: 0; color: #4a463f; font-style: italic; }
.ms-meta { margin-top: 8px; font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: #6b665e; }
.ms-muted { color: #6b665e; font-size: 12px; }
.ms-card { background: #fff !important; border: 1px solid #ddd5c6 !important; border-radius: 10px !important; }
.ms-section-title { font-size: 12px; letter-spacing: .14em; text-transform: uppercase; color: var(--ms-rust); margin: 2px 0; }
button.primary, .ms-primary button { background: var(--ms-rust) !important; border-color: var(--ms-rust) !important; color: #fff !important; }
footer { display: none !important; }
"""


def build_app(settings: Settings | None = None):
    import gradio as gr

    settings = settings or Settings.from_env()
    cache = ResultCache(settings.cache_dir)
    samples = list_samples()
    default = next((s for s in samples if s.startswith("invoice-northwind")), samples[0] if samples else None)

    def resolve(sample: str | None, upload: str | None) -> str | None:
        if upload:
            return upload
        if sample:
            return str(samples_dir() / sample)
        return None

    def preview(sample, upload):
        path = resolve(sample, upload)
        if not path:
            return None, gr.update(), [], "Pick a sample or upload a PDF.", None, None
        return (draw_document(path, []), guess_schema(path), [], f"Loaded **{Path(path).name}**. Choose a schema and "
                "press **Extract fields**.", None, None)

    def do_extract(sample, upload, schema):
        path = resolve(sample, upload)
        if not path:
            return [], None, "Pick a sample or upload a PDF first.", None, None
        cached = cache.get(path, "extract", schema, settings)
        try:
            if cached:
                result = ExtractionResult.model_validate(cached)
                note = f"Loaded a saved result for this file, computed earlier by `{result.model}`."
            else:
                result = run_extract(path, schema, settings)
                cache.put(path, "extract", schema, settings, result.to_json_dict())
                note = f"Extracted with `{result.model}` ({settings.backend} backend)."
        except NoTextLayerError as exc:
            return [], draw_document(path, []), f"⚠️ {exc}", None, None
        found = sum(1 for f in result.fields.values() if f.value is not None)
        linked = sum(1 for f in result.fields.values() if f.source is not None)
        status = f"{note} {found} of {len(result.fields)} fields found, {linked} linked to a source box."
        return field_rows(result), draw_document(path, field_boxes(result)), status, result.to_json_dict(), None

    def do_ask(sample, upload, question, result_json):
        path = resolve(sample, upload)
        if not path or not question.strip():
            return "Type a question first.", gr.update()
        result = ExtractionResult.model_validate(result_json) if result_json else None
        cached = cache.get(path, "ask", question.strip(), settings)
        try:
            if cached:
                answer = Answer.model_validate(cached)
            else:
                answer = run_ask(path, question.strip(), settings)
                cache.put(path, "ask", question.strip(), settings, answer.model_dump())
        except NoTextLayerError as exc:
            return f"⚠️ {exc}", gr.update()
        return answer_markdown(answer), draw_document(path, field_boxes(result) + cite_boxes(answer))

    model = settings.model_name
    with gr.Blocks(title="document-extractor · Modelshifts") as demo:
        gr.HTML(
            "<div class='ms-header'><div class='ms-brand'>MODELSHIFTS</div><h1>document-extractor</h1>"
            "<p>Turn PDF invoices and contracts into structured fields, each linked to its source.</p>"
            f"<div class='ms-meta'>backend: {settings.backend} · model: {model} · v{__version__}</div></div>"
        )
        result_state = gr.State(None)
        with gr.Row(equal_height=False):
            with gr.Column(scale=5, min_width=420):
                gr.HTML("<div class='ms-section-title'>1 · Document</div>")
                sample = gr.Dropdown(samples, value=default, label="Synthetic sample", interactive=True)
                upload = gr.File(label="…or upload a PDF", file_types=[".pdf"], type="filepath", height=90)
                schema = gr.Radio(["invoice", "contract"], value=guess_schema(default) if default else "invoice",
                                  label="Schema")
                extract_btn = gr.Button("Extract fields", variant="primary", elem_classes="ms-primary")
                status = gr.Markdown("")
                gr.HTML("<div class='ms-section-title'>2 · Fields</div>")
                table = gr.Dataframe(headers=["#", "Field", "Value", "Page", "Source text"],
                                     datatype=["number", "str", "str", "str", "str"], interactive=False,
                                     wrap=True, column_widths=["6%", "24%", "28%", "8%", "34%"])
                gr.HTML("<div class='ms-section-title'>3 · Ask the document</div>")
                with gr.Row():
                    question = gr.Textbox(placeholder="e.g. When is payment due?", show_label=False, scale=4)
                    ask_btn = gr.Button("Ask", scale=1, variant="secondary")
                answer = gr.Markdown("")
            with gr.Column(scale=6, min_width=480):
                gr.HTML("<div class='ms-section-title'>Page view · numbered boxes are field sources, "
                        "amber boxes are cited passages</div>")
                page = gr.Image(type="pil", show_label=False, height=760, interactive=False,
                                elem_classes="ms-card")
        gr.HTML("<p class='ms-muted'>All sample documents are synthetic. Uploaded files stay on the machine running "
                "this demo.</p>")

        sample.change(lambda s: (s, None), [sample], [sample, upload]).then(
            preview, [sample, upload], [page, schema, table, status, result_state, answer])
        upload.change(preview, [sample, upload], [page, schema, table, status, result_state, answer])
        extract_btn.click(do_extract, [sample, upload, schema], [table, page, status, result_state, answer])
        ask_btn.click(do_ask, [sample, upload, question, result_state], [answer, page])
        question.submit(do_ask, [sample, upload, question, result_state], [answer, page])
        demo.load(preview, [sample, upload], [page, schema, table, status, result_state, answer])
    return demo


def theme():
    import gradio as gr

    return gr.themes.Base(
        primary_hue=gr.themes.colors.orange,
        neutral_hue=gr.themes.colors.stone,
        font=["Georgia", "Times New Roman", "serif"],
        font_mono=["ui-monospace", "Menlo", "monospace"],
        radius_size=gr.themes.sizes.radius_md,
    )


def launch(host: str = "127.0.0.1", port: int = 7860, share: bool = False) -> None:
    demo = build_app()
    demo.queue().launch(server_name=host, server_port=port, share=share, theme=theme(), css=CSS)
