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
    font = _font(12)
    out_pages = []
    for i, img in enumerate(pages, start=1):
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        mine = [(bbox, label, kind) for page, bbox, label, kind in boxes if page == i]
        pad = 3
        rects = [tuple(v * RENDER_SCALE + o for v, o in zip(b, (-pad, -pad, pad, pad))) for b, _, _ in mine]
        for rect, (_, _, kind) in zip(rects, mine):
            if kind == "cite":
                d.rectangle(rect, fill=CITE_FILL, outline=CITE_COLOUR + (220,), width=2)
            else:
                d.rectangle(rect, fill=FIELD_COLOUR + (38,), outline=FIELD_COLOUR + (255,), width=2)
        placed: list[tuple[float, float, float, float]] = []
        # outermost boxes first, so a badge stays next to its own box when neighbours compete
        order = sorted(zip(rects, mine), key=lambda rm: -rm[0][2] if (rm[0][0] + rm[0][2]) > img.width else rm[0][0])
        for rect, (_, label, kind) in order:
            if not label:
                continue
            colour = (CITE_COLOUR if kind == "cite" else FIELD_COLOUR) + (255,)
            bw, bh = d.textlength(label, font=font) + 10, 17
            cy = (rect[1] + rect[3]) / 2
            right = (rect[0] + rect[2]) / 2 > img.width / 2
            # badges sit beside the box, pushed sideways past other boxes and badges so they never cover text
            bx = rect[2] + 8 if right else rect[0] - bw - 8
            obstacles = [r for r in rects if r is not rect and r[1] < cy + bh / 2 and r[3] > cy - bh / 2] + placed
            moved, shifted = True, False
            while moved:
                moved = False
                for r in obstacles:
                    if bx < r[2] + 2 and bx + bw > r[0] - 2 and cy - bh / 2 < r[3] and cy + bh / 2 > r[1]:
                        bx = r[2] + 4 if right else r[0] - bw - 4
                        moved = shifted = True
            bx = min(max(bx, 2), img.width - bw - 2)
            anchor = rect[2] if right else rect[0]
            end = bx + bw / 2
            if shifted:  # route the leader along the box bottom so it does not cross a neighbour's text
                y = rect[3] + 2
                d.line((rect[0] if not right else (rect[0] + rect[2]) / 2, y, end, y), fill=colour, width=1)
                d.line((end, y, end, cy + bh / 2), fill=colour, width=1)
            else:
                d.line((anchor, cy, bx if right else bx + bw, cy), fill=colour, width=1)
            d.rounded_rectangle((bx, cy - bh / 2, bx + bw, cy + bh / 2), radius=4, fill=colour)
            d.text((bx + 5, cy - bh / 2 + 1), label, font=font, fill=(255, 255, 255, 255))
            placed.append((bx, cy - bh / 2, bx + bw, cy + bh / 2))
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
.ms-header { border-bottom: 1px solid var(--ms-ink); padding: 10px 4px 12px; margin-bottom: 4px; }
.ms-brand { letter-spacing: .22em; font-size: 12px; color: var(--ms-rust); font-weight: 700; }
.ms-header h1 { font-family: Georgia, serif; font-weight: 400; font-size: 30px; margin: 2px 0 2px; color: var(--ms-ink); }
.ms-header p { margin: 0; color: #4a463f; font-style: italic; }
.ms-meta { margin-top: 8px; font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: #6b665e; }
.ms-muted { color: #6b665e; font-size: 12px; }
.ms-card { background: #fff !important; border: 1px solid #ddd5c6 !important; border-radius: 10px !important; }
.ms-section-title { font-size: 12px; letter-spacing: .14em; text-transform: uppercase; color: var(--ms-rust); margin: 2px 0; }
.ms-left { max-height: calc(100vh - 150px); min-height: 560px; overflow-y: auto !important; padding-right: 8px; scroll-behavior: smooth; flex-wrap: nowrap !important; }
.ms-left > * { flex-shrink: 0 !important; }
.ms-table * { font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif !important; font-size: 12.5px !important; }
.ms-status, .ms-answer { font-size: 14px; }
.ms-answer strong { color: var(--ms-ink); }
.ms-secondary, button.ms-secondary { background: #fff !important; color: var(--ms-rust) !important; border: 1px solid var(--ms-rust) !important; }
button.primary, .ms-primary button { background: var(--ms-rust) !important; border-color: var(--ms-rust) !important; color: #fff !important; }
footer { display: none !important; }
"""


def build_app(settings: Settings | None = None):
    import gradio as gr

    settings = settings or Settings.from_env()
    cache = ResultCache(settings.cache_dir)
    samples = list_samples()

    def pick_sample(name):
        if not name:
            return gr.update()  # dropdown cleared after an upload: keep the uploaded file
        return str(samples_dir() / name)

    def pick_upload(file):
        return (file if isinstance(file, str) else getattr(file, "name", None)), gr.update(value=None)

    def preview(path):
        if not path:
            return None, gr.update(), [], "Pick a synthetic sample or upload a PDF.", None, ""
        return (draw_document(path, []), guess_schema(path), [],
                f"Loaded **{Path(path).name}**. Choose a schema and press **Extract fields**.", None, "")

    def do_extract(path, schema):
        if not path:
            return [], None, "Pick a sample or upload a PDF first.", None, ""
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
            return [], draw_document(path, []), f"⚠️ {exc}", None, ""
        found = sum(1 for f in result.fields.values() if f.value is not None)
        linked = sum(1 for f in result.fields.values() if f.source is not None)
        status = f"{note} {found} of {len(result.fields)} fields found, {linked} linked to a source box."
        return field_rows(result), draw_document(path, field_boxes(result)), status, result.to_json_dict(), ""

    def do_ask(path, question, result_json):
        if not path or not question.strip():
            return "Pick a document and type a question first.", gr.update()
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

    with gr.Blocks(title="document-extractor · Modelshifts") as demo:
        gr.HTML(
            "<div class='ms-header'><div class='ms-brand'>MODELSHIFTS</div><h1>document-extractor</h1>"
            "<p>Turn PDF invoices and contracts into structured fields, each linked to its source.</p>"
            f"<div class='ms-meta'>backend: {settings.backend} · model: {settings.model_name} · "
            f"v{__version__}</div></div>"
        )
        current = gr.State(None)
        result_state = gr.State(None)
        with gr.Row(equal_height=False):
            with gr.Column(scale=4, min_width=400, elem_classes="ms-left", elem_id="ms-left"):
                gr.HTML("<div class='ms-section-title'>1 · Document</div>")
                with gr.Row(equal_height=True):
                    sample = gr.Dropdown(samples, value=None, label="Synthetic sample", interactive=True, scale=3)
                    upload = gr.UploadButton("Upload PDF", file_types=[".pdf"], type="filepath", scale=1,
                                             elem_classes="ms-secondary")
                schema = gr.Radio(["invoice", "contract"], value="invoice", label="Schema")
                extract_btn = gr.Button("Extract fields", variant="primary", elem_classes="ms-primary")
                status = gr.Markdown("Pick a synthetic sample or upload a PDF.", elem_classes="ms-status")
                gr.HTML("<div class='ms-section-title'>2 · Fields</div>")
                table = gr.Dataframe(headers=["#", "Field", "Value", "Pg", "Source text"],
                                     datatype=["number", "str", "str", "str", "str"], interactive=False,
                                     wrap=True, column_widths=["6%", "27%", "26%", "7%", "34%"],
                                     elem_classes="ms-table")
                gr.HTML("<div class='ms-section-title'>3 · Ask the document</div>")
                with gr.Row(equal_height=True):
                    question = gr.Textbox(placeholder="e.g. When is payment due?", show_label=False, scale=4,
                                          container=False)
                    ask_btn = gr.Button("Ask", scale=1, elem_classes="ms-secondary")
                answer = gr.Markdown("", elem_classes="ms-answer")
            with gr.Column(scale=6, min_width=480):
                gr.HTML("<div class='ms-section-title'>Page view · numbered boxes are field sources, "
                        "amber boxes are cited passages</div>")
                page = gr.Image(type="pil", show_label=False, height=720, interactive=False,
                                elem_classes="ms-card", buttons=["fullscreen", "download"])
        gr.HTML("<p class='ms-muted'>All sample documents are synthetic. Uploaded files stay on the machine running "
                "this demo.</p>")

        outs = [page, schema, table, status, result_state, answer]
        sample.change(pick_sample, [sample], [current]).then(preview, [current], outs)
        upload.upload(pick_upload, [upload], [current, sample]).then(preview, [current], outs)
        extract_btn.click(do_extract, [current, schema], [table, page, status, result_state, answer])
        ask_btn.click(do_ask, [current, question, result_state], [answer, page])
        question.submit(do_ask, [current, question, result_state], [answer, page])
    return demo


def theme():
    import gradio as gr

    return gr.themes.Base(
        primary_hue=gr.themes.colors.orange,
        neutral_hue=gr.themes.colors.stone,
        font=[gr.themes.Font("Georgia"), gr.themes.Font("Times New Roman"), gr.themes.Font("serif")],
        font_mono=[gr.themes.Font("ui-monospace"), gr.themes.Font("Menlo"), gr.themes.Font("monospace")],
        radius_size=gr.themes.sizes.radius_md,
    )


def launch(host: str = "127.0.0.1", port: int = 7860, share: bool = False) -> None:
    demo = build_app()
    demo.queue().launch(server_name=host, server_port=port, share=share, theme=theme(), css=CSS)
