"""OCR for pages without a text layer.

* ``hf`` backend: Florence-2 (``<OCR_WITH_REGION>`` task) gives text lines with boxes.
* ``api`` backend: a vision model behind the same OpenAI-compatible endpoint, if
  ``MS_VISION_MODEL`` is set. It is asked for text lines with boxes on a 0-1000
  grid. Box quality depends on the model.

Both return :class:`~document_extractor.models.Word` objects in PDF points.
"""

from __future__ import annotations

import base64
import io
import json
import re
from typing import Protocol

from PIL import Image

from .models import Word


class OCREngine(Protocol):
    name: str

    def recognise(self, image: Image.Image, page: int, scale: float) -> list[Word]: ...


def split_line(text: str, box: tuple[float, float, float, float], page: int) -> list[Word]:
    """Split one OCR line into words, sharing the line box out by character count."""
    x0, y0, x1, y1 = box
    tokens = text.split()
    if not tokens:
        return []
    total = sum(len(t) for t in tokens) + (len(tokens) - 1)
    width = max(x1 - x0, 1e-6)
    words, cursor = [], 0
    for t in tokens:
        a = x0 + width * cursor / total
        b = x0 + width * (cursor + len(t)) / total
        words.append(Word(text=t, page=page, bbox=(a, y0, b, y1)))
        cursor += len(t) + 1
    return words


class Florence2OCR:
    """Florence-2 OCR via ``transformers`` (runs on CPU or GPU)."""

    def __init__(self, model_id: str):
        import torch
        from transformers import AutoProcessor, Florence2ForConditionalGeneration

        self.name = model_id
        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.model = Florence2ForConditionalGeneration.from_pretrained(model_id, dtype=dtype).to(self.device).eval()
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.dtype = dtype

    def recognise(self, image: Image.Image, page: int, scale: float) -> list[Word]:
        task = "<OCR_WITH_REGION>"
        inputs = self.processor(text=task, images=image.convert("RGB"), return_tensors="pt").to(self.device, self.dtype)
        with self._torch.no_grad():
            generated = self.model.generate(**inputs, max_new_tokens=1024, num_beams=3, do_sample=False)
        text = self.processor.batch_decode(generated, skip_special_tokens=False)[0]
        parsed = self.processor.post_process_generation(text, task=task, image_size=image.size)[task]
        words: list[Word] = []
        for label, quad in zip(parsed.get("labels", []), parsed.get("quad_boxes", [])):
            xs, ys = quad[0::2], quad[1::2]
            box = (min(xs) / scale, min(ys) / scale, max(xs) / scale, max(ys) / scale)
            words.extend(split_line(label.replace("</s>", "").strip(), box, page))
        return words


VISION_PROMPT = (
    "Read all text on this page. Reply with JSON only: a list of objects "
    '{"text": "<one line of text>", "box": [x0, y0, x1, y1]} where the box is the line position '
    "on a 0-1000 grid (0,0 = top-left, 1000,1000 = bottom-right). Keep the reading order."
)


class APIVisionOCR:
    """OCR with a vision-capable chat model on an OpenAI-compatible endpoint."""

    def __init__(self, client, model: str):
        self.client = client
        self.name = model
        self.model = model

    def recognise(self, image: Image.Image, page: int, scale: float) -> list[Word]:
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": url}},
                    ],
                }
            ],
        )
        return parse_vision_lines(response.choices[0].message.content or "", image.size, page, scale)


def parse_vision_lines(content: str, size: tuple[int, int], page: int, scale: float) -> list[Word]:
    match = re.search(r"\[.*\]", content, re.S)
    if not match:
        return []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    w_pts, h_pts = size[0] / scale, size[1] / scale
    words: list[Word] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("text"):
            continue
        box = item.get("box") or [0, 0, 1000, 1000]
        try:
            x0, y0, x1, y1 = (float(v) for v in box[:4])
        except (TypeError, ValueError):
            continue
        pts = (x0 / 1000 * w_pts, y0 / 1000 * h_pts, x1 / 1000 * w_pts, y1 / 1000 * h_pts)
        words.extend(split_line(str(item["text"]), pts, page))
    return words
