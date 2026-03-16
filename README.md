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

Ensure your `.env` already contains:

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

## Hosted model outputs

You can view generated graphs for multiple VLM options at:

- <https://kartik34.github.io/pid-entity-detection-graph-construction/>

Direct viewer links:

- Sonnet 4.6: <https://kartik34.github.io/pid-entity-detection-graph-construction/viewers/sonnet-4.6.html>
- GPT-5.4: <https://kartik34.github.io/pid-entity-detection-graph-construction/viewers/gpt-5.4.html>
- Grok 4.2 Beta: <https://kartik34.github.io/pid-entity-detection-graph-construction/viewers/grok-4.2-beta.html>
- Gemini 3 Flash Preview: <https://kartik34.github.io/pid-entity-detection-graph-construction/viewers/gemini-3-flash-preview.html>

Notes:

- Grok did a decent job detecting edges and populating relevant details for a relatively low cost per PID (3 page pdf) pipeline run of about ~10 cents in tokens
- Sonnet 4.6 also performed very well, but each pipeline cost about 30-50 cents in tokens
- At scale (assuming 10,000 documents per client) this could cost upto 5-7k USD for a VLM result.

## Pipeline stages

`main.py` runs 9 steps:

1. Ingest documents (render PDF pages)
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

## Design choices / approach

### OCR

- Used Tesseract to extract raw text boxes, then clustered nearby detections into candidate tag regions.
- Dense P&ID areas and linework (pipes/symbols) reduced OCR quality and made deterministic parsing brittle.

### OCR + LLM normalization

- Added an LLM correction step with strict JSON schema output validation.
- This normalizes noisy OCR text into ISA-style tags and structured attributes.
- Chose this approach because pure deterministic parsing was not robust enough on messy OCR output.

### VLM graph construction

- Used a multimodal VLM to infer connectivity (edges) between confirmed OCR tags.
- Inputs to the VLM include confirmed tags + bounding boxes, the base page image, an overlay image with highlighted boxes, and image dimensions for spatial context.
- If the VLM returns empty or invalid JSON, confirmed nodes are still emitted with `needs_review=true`.
- A fully deterministic graph-construction approach was explored first, but required significantly more modeling/tuning for dense diagrams.

### Audit

- Audit logic is deterministic and rule-based (missing equipment, pressure mismatch, temperature mismatch).
- The same pattern can be extended with configurable rule sets for different plant or spec standards.

## Current limitations

- Dense pages can reduce edge recall/precision in vision extraction.
- SOP parsing currently expects key limits from the first table in the DOCX.
- Only implemented audit rules are missing equipment in P&ID, pressure mismatch, and temperature mismatch.

## Troubleshooting

- `Missing OPENROUTER_API_KEY`: add key to `.env`.
- OCR quality is low: tune `PID_AUDIT_OCR_UPSCALE_FACTOR`, `PID_AUDIT_OCR_CROP_PAD`, and `PID_AUDIT_OCR_LENIENT_MIN_BOX_AREA`, then rerun.
- Viewer looks stale: rerun pipeline or regenerate with `pid-audit-graph-ui`.
