"""
ocr_correct.py

LLM correction for OCR clusters -> structured equipment tags.
"""

import json
import re

from .client import get_client, TEXT_MODEL
from .models import OCRCorrectionResponse
from .schemas import OCRCluster, ConfirmedTag

TAG_PATTERN = re.compile(r"^[A-Z]{1,4}-\d{2,4}[A-Z0-9-]*$")
CLUSTER_BATCH_SIZE = 35
RESPONSE_SCHEMA = OCRCorrectionResponse.model_json_schema()

SYSTEM_PROMPT = """You correct OCR text into ISA-style P&ID equipment tags.

Rules:
- Only use information present in OCR text.
- ISA-style tag format: PREFIX-NUMBER[-SUFFIX], e.g. F-715, E-742, AC-746, MV-715-10A, PSV-715A.
- Valid prefixes: F, V, P, E, AC, MV, PSV, RV, PI, TI, FI, DR, LI, PT, TT, DPI, CV, XV, HV, LV, FV.
- Fix common OCR confusions (O/0, I/1, B/8, S/5, G/6, /7, stray punctuation).
- In numeric parts of tags, "/" is often a broken "7" and should be corrected when it fits the tag pattern.
- Common tag fixes:
  - E—742, E_742, E.742, E 742 -> E-742
  - AC-/46, AC-74G -> AC-746
  - MV 715 10A, MV-7I5-10A, MV-/15-10A -> MV-715-10A
  - PSV715A, PSV-7I5A -> PSV-715A
  - PI-7I5, TI-7I5, LI-7I5 -> PI-715, TI-715, LI-715
  - RV-7S0 -> RV-750
- A cluster can contain multiple tags; return one item per tag.
- Use the input cluster_index on every returned item.
- Skip non-equipment text (dimensions, headers, pure line labels).
- Return JSON only.
"""

USER_PROMPT = """OCR clusters for one page:
{clusters}
"""


def sanitize_cluster_texts(texts: list[str]) -> list[str]:
    return [t.replace("?", "").strip() for t in texts if t.replace("?", "").strip()]


def run_correction_batch(client, cluster_data: list[dict], page: int, start: int, end: int) -> OCRCorrectionResponse | None:
    response = client.chat.completions.create(
        model=TEXT_MODEL,
        max_tokens=10000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(clusters=json.dumps(cluster_data))},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "ocr_corrections",
                "strict": True,
                "schema": RESPONSE_SCHEMA,
            },
        },
    )

    choice = response.choices[0] if getattr(response, "choices", None) else None
    if choice is None or getattr(choice, "message", None) is None:
        print(f"  [warn] no message on page {page}, batch {start}:{end}")
        return None

    content = getattr(choice.message, "content", None)
    if isinstance(content, str) and content.strip():
        try:
            return OCRCorrectionResponse.model_validate_json(content)
        except Exception:
            print(f"  [warn] invalid JSON content on page {page}, batch {start}:{end}")
            return None

    print(f"  [warn] no JSON content on page {page}, batch {start}:{end} (content_type={type(content).__name__})")
    return None


def correct_ocr_tags(clusters: list[OCRCluster], page: int) -> list[ConfirmedTag]:
    if not clusters:
        return []

    client = get_client()
    confirmed: list[ConfirmedTag] = []

    for start in range(0, len(clusters), CLUSTER_BATCH_SIZE):
        end = min(len(clusters), start + CLUSTER_BATCH_SIZE)
        batch = clusters[start:end]
        cluster_data = [
            {"index": start + i, "texts": sanitize_cluster_texts(c.texts), "bbox": c.bbox}
            for i, c in enumerate(batch)
        ]

        result = run_correction_batch(client, cluster_data, page, start, end)
        if result is None:
            continue

        for item in result.tags:
            tag = item.tag.strip().upper()
            if not TAG_PATTERN.match(tag):
                continue
            if not (0 <= item.cluster_index < len(clusters)):
                continue

            confirmed.append(ConfirmedTag(
                tag=tag,
                component_type=item.component_type,
                attributes={
                    "set_point_psig": item.set_point_psig,
                    "size_inches": item.size_inches,
                    "notation": item.notation,
                    "pipe_label": item.pipe_label,
                },
                page=page,
                confidence=float(item.confidence),
                raw_ocr=item.raw_ocr,
                bbox=clusters[item.cluster_index].bbox,
                requires_review=float(item.confidence) < 0.7,
            ))

    return confirmed
