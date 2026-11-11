
Backend: api, model: qwen2.5-1.5b-instruct-q4_k_m

| Sample | Correct | Sourced | Time (s) | Misses |
|---|---|---|---|---|
| contract-master-services.pdf | 8/8 | 8/8 | 7.0 | - |
| contract-supply.pdf | 8/8 | 8/8 | 3.9 | - |
| invoice-acme-scanned.pdf | 0/9 | 0/0 | 0.0 | error: invoice-acme-scanned.pdf, page 1: this page has no text layer (it looks like a scan) and no OCR engine is configured. Use MS_BACKEND=hf (Florence-2 OCR) or set MS_VISION_MODEL for MS_BACKEND=api. |
| invoice-demo-freight-compact.pdf | 9/9 | 9/9 | 6.4 | - |
| invoice-example-logistics-banner.pdf | 9/9 | 9/9 | 4.7 | - |
| invoice-northwind-classic.pdf | 9/9 | 9/9 | 5.9 | - |
| invoice-placeholder-two-page.pdf | 9/9 | 9/9 | 12.1 | - |
| **All** | **52/61 (85%)** | 52/52 | | |
