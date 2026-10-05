# AFRIYANA INDIA – FC Shipment Plan (Amazon.in)

Ported from the Cowork scheduled task "Amazon india inventory planning" (run of 5 Oct 2026).
Files rebuilt from the task transcript.

- `r1_*.tsv`, `r2_*.tsv`, `r3_*.tsv` – aggregated Seller Central report data (no buyer PII)
- `build_fc_plan.py` – demand model, inbound netting, capacity + IXD overflow → `plan_model.json`
- `build_fc_workbook.py` – renders `FC Shipment Plan DD-Mon-YYYY.xlsx` (8 tabs)

Run: `python3 build_fc_plan.py && python3 build_fc_workbook.py`
(reads/writes the script's folder; override with `AFRIYANA_DIR`). Requires `openpyxl`.
