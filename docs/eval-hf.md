
Backend: hf, model: Qwen/Qwen2.5-1.5B-Instruct

| Sample | Correct | Sourced | Time (s) | Misses |
|---|---|---|---|---|
| contract-master-services.pdf | 8/8 | 8/8 | 18.7 | - |
| contract-supply.pdf | 8/8 | 8/8 | 9.0 | - |
| invoice-acme-scanned.pdf | 8/9 | 8/8 | 22.1 | buyer_name='Northwind Parts Pte., Ltd.' (want 'Northwind Parts Pte. Ltd.') |
| invoice-demo-freight-compact.pdf | 9/9 | 9/9 | 10.5 | - |
| invoice-example-logistics-banner.pdf | 9/9 | 9/9 | 9.7 | - |
| invoice-northwind-classic.pdf | 9/9 | 9/9 | 10.9 | - |
| invoice-placeholder-two-page.pdf | 9/9 | 9/9 | 13.6 | - |
| **All** | **60/61 (98%)** | 60/60 | | |
