# Evaluation record

Numbers used in the README and on the case page. Re-run with:

```bash
python scripts/evaluate.py
```

A field counts as correct when the typed value matches the ground truth in `samples/*.truth.json` (strings compared case-insensitively, extra spaces and trailing punctuation ignored; numbers within 0.005). “Sourced” counts correct values that also carry a source box whose text matches the value. The logic is in `scripts/evaluate.py`. All seven PDFs are synthetic; all names and figures are fictional.

## Hugging Face backend — 12 November 2026

- Backend: `hf`
- Model: `Qwen/Qwen2.5-1.5B-Instruct`
- OCR (scanned page): Florence-2 (`florence-community/Florence-2-large`)
- Machine: 8-core CPU (Intel Xeon), 15 GB RAM, no GPU, PyTorch 2.15.0+cpu, 8 threads
- Wall-clock for all seven samples: 96 seconds, including model load
- Source of this table: a quiet re-run of `scripts/evaluate.py` on that machine, 12 November 2026 (Asia/Singapore)

| Sample | Correct | Sourced | Time (s) | Notes |
|---|---|---|---|---|
| contract-master-services.pdf | 8/8 | 8/8 | 18.7 | — |
| contract-supply.pdf | 8/8 | 8/8 | 9.0 | — |
| invoice-acme-scanned.pdf | 8/9 | 8/8 | 22.1 | `buyer_name='Northwind Parts Pte., Ltd.'` (want `'Northwind Parts Pte. Ltd.'`) |
| invoice-demo-freight-compact.pdf | 9/9 | 9/9 | 10.5 | — |
| invoice-example-logistics-banner.pdf | 9/9 | 9/9 | 9.7 | — |
| invoice-northwind-classic.pdf | 9/9 | 9/9 | 10.9 | — |
| invoice-placeholder-two-page.pdf | 9/9 | 9/9 | 13.6 | — |
| **All** | **60/61 (98%)** | **60/60** | **9.0–22.1** | |

The first document’s time includes some model-load cost. The same accuracy (60/61, 60/60 sourced, the same OCR miss) was also obtained on an earlier run on this machine, with per-document times of 9.3–24.9 seconds.

## API backend — November 2026

Recorded on the same 8-core CPU, against a local llama.cpp server running Qwen2.5-1.5B-Instruct (Q4_K_M GGUF). Source: the evaluation captured for v1 (`eval-api.md`).

| Sample | Correct | Sourced | Time (s) | Notes |
|---|---|---|---|---|
| contract-master-services.pdf | 8/8 | 8/8 | 7.0 | — |
| contract-supply.pdf | 8/8 | 8/8 | 3.9 | — |
| invoice-acme-scanned.pdf | 0/9 | 0/0 | 0.0 | no text layer, no OCR configured; clean error |
| invoice-demo-freight-compact.pdf | 9/9 | 9/9 | 6.4 | — |
| invoice-example-logistics-banner.pdf | 9/9 | 9/9 | 4.7 | — |
| invoice-northwind-classic.pdf | 9/9 | 9/9 | 5.9 | — |
| invoice-placeholder-two-page.pdf | 9/9 | 9/9 | 12.1 | — |
| **All** | **52/61 (85%)** | **52/52** | **3.9–12.1** | |

The 7B default (`Qwen/Qwen2.5-7B-Instruct`) has not been measured.
