<p align="center">
  <img src="assets/banner.svg" alt="document-extractor" width="100%">
</p>

<p align="center"><em>Turn PDF invoices and contracts into structured fields, each linked to its source.</em></p>

<p align="center">
  <img alt="Status: v1" src="https://img.shields.io/badge/status-v1-8a3a24?style=flat-square">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-1c1a17?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-1c1a17?style=flat-square">
  <img alt="Backends: API or Hugging Face" src="https://img.shields.io/badge/backends-API%20%7C%20Hugging%20Face-1c1a17?style=flat-square">
</p>

---

## Features

All five features below work in v1. See [Limitations](#limitations) for what they do not cover yet.

- **Field extraction to JSON**: define the fields you want (invoice number, totals, parties, dates) and get typed JSON back.
- **Source citation per value**: every value carries the page and bounding box it came from, so it can be checked in one click.
- **Q&A over the document (RAG)**: ask a question and get an answer grounded in cited passages.
- **Batch mode**: point it at a folder and get one CSV or JSON file per run.
- **Web demo**: pick a sample or upload a PDF, see fields highlighted on the page.

<p align="center">
  <img src="assets/demo.gif" alt="Web demo: a synthetic invoice is selected, the extracted fields appear with their source boxes on the page, and a question is answered with a cited passage" width="100%">
</p>
<p align="center"><sub>Web demo on a synthetic invoice (<a href="assets/demo.mp4">MP4</a>). Results in the recording were computed earlier by Qwen2.5-1.5B-Instruct on CPU and loaded from the demo's result cache.</sub></p>

## Architecture

```mermaid
%%{init: {"theme":"base","flowchart":{"curve":"basis","wrappingWidth":260},"themeVariables":{"fontFamily":"Georgia, Times New Roman, serif","fontSize":"14px","primaryColor":"#f3efe6","primaryTextColor":"#1c1a17","primaryBorderColor":"#1c1a17","lineColor":"#1c1a17","clusterBkg":"#faf7f0","clusterBorder":"#8a3a24","titleColor":"#8a3a24","edgeLabelBackground":"#f3efe6"}}}%%
flowchart TB
  P["PDF / scan"]:::ink --> L["Layout and OCR<br/>pages, blocks, boxes"]:::ink
  L --> X["Field extractor<br/>schema to JSON"]:::ink
  L --> C["Chunk and embed"]:::ink
  C --> Q["Q&A (RAG)<br/>retrieve, answer, cite"]:::ink
  X --> G["Grounding<br/>match each value to page words"]:::ink
  G --> O["JSON + source links<br/>page, box, snippet"]:::ink
  Q --> O
  subgraph BK["Backend · pick one"]
    direction LR
    BKA["<b>(a) Your API key</b><br/>OpenAI-compatible<br/>LLM + embeddings"]:::rust
    BKH["<b>(b) Hugging Face</b><br/>Qwen2.5-7B-Instruct<br/>bge-m3 · Florence-2"]:::rust
  end
  BK -.-> X
  BK -.-> Q
  BK -.-> C

  classDef cl fill:#faf7f0,stroke:#8a3a24,stroke-dasharray:4 3,color:#8a3a24;
  classDef ink fill:#f3efe6,stroke:#1c1a17,color:#1c1a17,stroke-width:1px;
  classDef rust fill:#f3efe6,stroke:#8a3a24,color:#8a3a24,stroke-width:1.5px;
```

### Two interchangeable backends

Pick one with `MS_BACKEND` in `.env`. The rest of the pipeline does not change.

| | (a) Bring your own API key | (b) Open-source on Hugging Face |
|---|---|---|
| **What** | Any OpenAI-compatible endpoint | Open models, run locally with `transformers` |
| **Set** | `MS_BACKEND=api`, `MS_API_BASE`, `MS_API_KEY`, `MS_MODEL` | `MS_BACKEND=hf`, optionally `MS_HF_MODEL` |
| **Scanned pages** | `MS_VISION_MODEL` (a vision model on the same endpoint) | Florence-2 |
| **Q&A retrieval** | `MS_EMBED_MODEL` if set, otherwise BM25 | bge-m3 |
| **Good for** | Fastest start, strongest hosted models | Data stays on your machines, no per-call cost |

**Default open-source models**

| Model | Used for | License |
|---|---|---|
| [`Qwen/Qwen2.5-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | field extraction and answers | Apache-2.0 |
| [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) | embeddings for retrieval | MIT |
| [`florence-community/Florence-2-large`](https://huggingface.co/florence-community/Florence-2-large) | OCR for scanned pages (`transformers`-native copy of [`microsoft/Florence-2-large`](https://huggingface.co/microsoft/Florence-2-large)) | MIT |

On a machine without a GPU, set `MS_HF_MODEL=Qwen/Qwen2.5-1.5B-Instruct`. The 7B model needs a GPU or a lot of memory.
`MS_RETRIEVER=bm25` skips the bge-m3 download and uses keyword retrieval instead.

## Quickstart

Python 3.11 or newer.

```bash
git clone https://github.com/ModelShifts/document-extractor
cd document-extractor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[hf,demo]"      # open models; use ".[api,demo]" for the API backend
cp .env.example .env              # choose a backend and models
```

On a CPU-only machine, install the CPU build of PyTorch first (`pip install torch --index-url https://download.pytorch.org/whl/cpu`) and set `MS_HF_MODEL=Qwen/Qwen2.5-1.5B-Instruct` in `.env`. Models download from Hugging Face on first use.

```bash
# fields as JSON, each with {page, bbox, text}
document-extractor extract samples/invoice-northwind-classic.pdf --schema schemas/invoice.yaml

# a question, answered with cited passages
document-extractor ask samples/contract-master-services.pdf "When does the notice period start?"

# a folder to one CSV (or .json)
document-extractor batch samples --glob "invoice-*.pdf" --schema invoice --out results.csv

# the web demo at http://127.0.0.1:7860 (python app.py does the same)
document-extractor serve
```

### Using the API backend

Any OpenAI-compatible endpoint works. In `.env`:

```bash
MS_BACKEND=api
MS_API_BASE=https://your-provider.example/v1
MS_API_KEY=your-api-key
MS_MODEL=your-chat-model
```

To try it without a paid key, run an open model behind a local OpenAI-compatible server, for example [llama-cpp-python](https://github.com/abetlen/llama-cpp-python):

```bash
pip install "llama-cpp-python[server]" huggingface_hub \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu   # prebuilt CPU wheels, no compiler needed
hf download Qwen/Qwen2.5-1.5B-Instruct-GGUF qwen2.5-1.5b-instruct-q4_k_m.gguf --local-dir models
python -m llama_cpp.server --model models/qwen2.5-1.5b-instruct-q4_k_m.gguf --n_ctx 8192 --port 8001
# then: MS_API_BASE=http://127.0.0.1:8001/v1  MS_API_KEY=local  MS_MODEL=qwen2.5-1.5b-instruct-q4_k_m
```

### Schemas

A schema is a YAML file that lists fields and their types (`string`, `date`, `number`, `integer`). See [`schemas/invoice.yaml`](schemas/invoice.yaml) and [`schemas/contract.yaml`](schemas/contract.yaml). Dates come back as `YYYY-MM-DD` and amounts as numbers. The model is asked to copy each value as printed, and the value is then matched back to the words on the page to find its box.

### Sample documents and tests

`samples/` holds seven synthetic PDFs (four invoice layouts, two contracts, one image-only scan) with a ground-truth file for each. All names and figures in them are fictional.

```bash
pip install -e ".[dev]"
python scripts/make_samples.py   # regenerate samples/
pytest                           # uses a mocked model, no downloads
python scripts/evaluate.py       # compare the configured backend with the ground truth
```

## Limitations

- The samples are synthetic and have simple layouts. The project has not been measured on real-world documents.
- On a CPU, extraction with the open models takes tens of seconds per document, and loading Qwen, bge-m3 and Florence-2 together needs several GB of memory. The 7B default needs a GPU.
- Florence-2 reads a scanned page in one pass, so small or dense text can be misread. On the API backend, OCR through `MS_VISION_MODEL` is implemented but has only been tested with a mocked model.
- Source boxes come from matching the value against the page text. If a value is printed more than once, the copy closest to a matching label is used, which is not always the one the model read.
- Numeric dates such as `03.02.2026` are read day-first.
- The web demo saves results under `.cache/results` and reuses them for the same file, schema and model.

## Roadmap

- [x] Repository scaffold and README
- [x] PDF parsing with page and box coordinates
- [x] Schema-driven field extraction
- [x] Source citation per value
- [x] Q&A over the document (RAG)
- [x] Batch mode
- [x] Web demo
- [ ] Reranking retrieved passages with `BAAI/bge-reranker-v2-m3`
- [ ] Scanned-page OCR tested with a real vision model on the API backend
- [ ] Hosted demo

## License

[MIT](LICENSE) © Modelshifts Technology Pte. Ltd.

<p align="center"><sub>Part of the <a href="https://modelshifts.com/work">Modelshifts</a> showcase.</sub></p>
