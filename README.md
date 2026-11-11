<p align="center">
  <img src="assets/banner.svg" alt="document-extractor" width="100%">
</p>

<p align="center"><em>Turn PDF invoices and contracts into structured fields, each linked to its source.</em></p>

<p align="center">
  <img alt="Status: in development" src="https://img.shields.io/badge/status-in%20development-8a3a24?style=flat-square">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-1c1a17?style=flat-square">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-1c1a17?style=flat-square">
  <img alt="Backends: API or Hugging Face" src="https://img.shields.io/badge/backends-API%20%7C%20Hugging%20Face-1c1a17?style=flat-square">
</p>

---

## Features

Planned for v1. Progress is tracked in the Roadmap below.

- **Field extraction to JSON**: define the fields you want (invoice number, totals, parties, dates) and get typed JSON back.
- **Source citation per value**: every value carries the page and bounding box it came from, so it can be checked in one click.
- **Q&A over the document (RAG)**: ask a question and get an answer grounded in cited passages.
- **Batch mode**: point it at a folder and get one JSON file and one CSV summary per run.
- **Web demo**: drop a PDF, see fields highlighted on the page.

## Architecture

```mermaid
%%{init: {"theme":"base","flowchart":{"curve":"basis","wrappingWidth":260},"themeVariables":{"fontFamily":"Georgia, Times New Roman, serif","fontSize":"14px","primaryColor":"#f3efe6","primaryTextColor":"#1c1a17","primaryBorderColor":"#1c1a17","lineColor":"#1c1a17","clusterBkg":"#faf7f0","clusterBorder":"#8a3a24","titleColor":"#8a3a24","edgeLabelBackground":"#f3efe6"}}}%%
flowchart TB
  P["PDF / scan"]:::ink --> L["Layout and OCR<br/>pages, blocks, boxes"]:::ink
  L --> C["Chunk and embed"]:::ink
  C --> X["Field extractor<br/>schema to JSON"]:::ink
  C --> Q["Q&A (RAG)<br/>retrieve, answer, cite"]:::ink
  X --> O["JSON + source links<br/>page, box, snippet"]:::ink
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
| **What** | Any OpenAI-compatible endpoint | Open models, run locally or via Hugging Face Inference |
| **Set** | `MS_BACKEND=api`, `OPENAI_BASE_URL`, `OPENAI_API_KEY` | `MS_BACKEND=hf`, `HF_MODE=local` or `inference` |
| **Good for** | Fastest start, strongest hosted models | Data stays on your machines, no per-call cost |

**Default open-source models**

| Model | Used for | License |
|---|---|---|
| [`Qwen/Qwen2.5-7B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) | field extraction and answers | Apache-2.0 |
| [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) | embeddings for retrieval | MIT |
| [`BAAI/bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3) | reranking retrieved passages | Apache-2.0 |
| [`microsoft/Florence-2-large`](https://huggingface.co/microsoft/Florence-2-large) | OCR for scanned pages | MIT |

## Quickstart

> **Coming soon.** The commands below show the planned interface.

```bash
git clone https://github.com/ModelShifts/document-extractor
cd document-extractor
cp .env.example .env   # choose a backend
pip install -e .
document-extractor extract invoice.pdf --schema schemas/invoice.yaml
document-extractor ask contract.pdf "When does the notice period start?"
```

## Roadmap

- [x] Repository scaffold and README
- [ ] PDF parsing with page and box coordinates
- [ ] Schema-driven field extraction
- [ ] Source citation per value
- [ ] Q&A over the document (RAG)
- [ ] Batch mode
- [ ] Web demo

## License

[MIT](LICENSE) © Modelshifts Technology Pte. Ltd.

<p align="center"><sub>Part of the <a href="https://modelshifts.com/work">Modelshifts</a> showcase.</sub></p>
