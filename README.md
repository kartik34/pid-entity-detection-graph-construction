# P&ID Audit Pipeline

Convert a P&ID PDF into a structured graph, cross-reference it against SOP limits, and generate both machine-readable findings and a simple interactive HTML viewer.

## What this project does

- Renders P&ID pages from `data/pid/diagram.pdf`
- Runs OCR + clustering to detect text regions
- Uses an LLM to normalize OCR text into equipment tags and attributes
- Uses a vision model to infer process connectivity (edges) between confirmed tags and populate missed details
- Builds a graph (`graph.json`) with node attributes and edges
- Parses SOP records from `data/sop/sop.docx`
- Audits SOP vs P&ID for:
  - `missing_in_pid`
  - `pressure_mismatch`
  - `temperature_mismatch`
- Generates:
  - `outputs/findings.json`
  - `outputs/report.md`
  - `outputs/graph_viewer.html`

## Repository layout

- `src/pid_audit/main.py` - pipeline entrypoint
- `src/pid_audit/ingest.py` - PDF render
- `src/pid_audit/ocr.py` - OCR token detection + clustering
- `src/pid_audit/ocr_correct.py` - LLM OCR correction + tag extraction
- `src/pid_audit/vision.py` - vision graph extraction
- `src/pid_audit/graph_build.py` - merges OCR + vision into graph
- `src/pid_audit/sop_parse.py` - SOP table parsing
- `src/pid_audit/audit.py` - deterministic SOP/P&ID checks
- `src/pid_audit/graph_ui.py` - interactive HTML graph viewer
- `src/pid_audit/report.py` - markdown report generation

## Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- Tesseract OCR installed

macOS:

```bash
brew install tesseract
```

```bash
poetry install
```

## Environment variables

Create a `.env` file in repo root:

```env
OPENROUTER_API_KEY=your_key_here
```

Model aliases are set in `src/pid_audit/client.py`:

- `TEXT_MODEL` (used for OCR correction)
- `VISION_MODEL` (used for graph extraction)

## Run the pipeline

```bash
poetry run pid-audit
```

This executes all steps and writes outputs under `outputs/`.

## Pipeline stages

`main.py` runs 9 steps:

1. Ingest documents (render PDF pages, preprocess OCR images)
2. Parse SOP
3. OCR and clustering
4. OCR correction with LLM
5. Vision graph extraction
6. Graph build
7. Audit
8. Report
9. HTML graph viewer

## Output files

Core outputs:

- `outputs/sop_structured.json`
- `outputs/ocr_page_{n}_raw.json`
- `outputs/ocr_page_{n}_clustered.json`
- `outputs/ocr_page_{n}_corrected.json`
- `outputs/vision_page_{n}.json`
- `outputs/confirmed_tags.json`
- `outputs/graph.json`
- `outputs/findings.json`
- `outputs/report.md`
- `outputs/graph_viewer.html`

Debug images:

- `outputs/debug_1_ocr_raw_page_{n}.png`
- `outputs/debug_2_ocr_clusters_page_{n}.png`
- `outputs/debug_3_confirmed_tags_page_{n}.png`

## Graph schema (high-level)

`graph.json` contains:

- `nodes`: each with
  - `id` (instance key, e.g. `TAG@p2`)
  - `tag` (human-readable tag)
  - `component_type`
  - `equipment_class` (`major` / `minor` / `external`)
  - `page`, `bbox`, `confidence`, `needs_review`, `family`, `source`, and extracted attributes
- `edges`: each with
  - `source`, `target`
  - `pipe_label`
  - `flow_direction`

## Design choices

- OCR determines node existence; vision enriches nodes and extracts connectivity.
- Vision output is constrained with strict JSON schema.
- If vision returns empty/unparseable output, confirmed nodes are still emitted with `needs_review=true`.
- Audit logic is deterministic and rule-based.

## Current limitations

- Dense pages can reduce edge recall/precision in vision extraction.
- SOP parsing currently expects key limits from the first table in the DOCX.
- Only implemented audit rules are missing equipment in P&ID, pressure mismatch, and temperature mismatch.

## Troubleshooting

- `Missing OPENROUTER_API_KEY`: add key to `.env`.
- OCR quality is low: tune `PID_AUDIT_OCR_PREPROCESS_SCALE` and rerun.
- Viewer looks stale: rerun pipeline or regenerate with `pid-audit-graph-ui`.

## Notes for take-home evaluation

This implementation prioritizes:

- modular pipeline stages
- intermediate artifacts at every step
- deterministic audit rules
