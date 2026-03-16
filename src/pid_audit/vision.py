"""
vision.py

Simple Vision extraction:
1. Send page image + Overlay page image + confirmed tag list + dimensions
2. Enforce strict JSON schema response
3. Keep only nodes/edges that reference confirmed tags
"""

import base64
import json

import cv2

from .client import get_client, VISION_MODEL
from .models import VisionResponsePayload
from .schemas import ConfirmedTag

VISION_MAX_TOKENS = 25000

RESPONSE_SCHEMA = VisionResponsePayload.model_json_schema()
EMPTY_VISION_ATTRIBUTES = {
    "set_point_psig": None,
    "size_inches": None,
    "notation": None,
    "pipe_label": None,
    "service": None,
    "design_pressure_psig": None,
    "design_temperature_f": None,
    "pressure_rating_psig": None,
}

VISION_PROMPT = """Extract process-pipe connectivity from this P&ID.

Confirmed OCR tags with bbox=[x1,y1,x2,y2] in image pixels:
{confirmed_tags}

Rules:
- Use only confirmed tags as node ids.
- Do not invent tags.
- Use bbox proximity to resolve local connections.
- Set external=true for off-page targets.
- Add node attributes only when clearly visible.
- Return JSON only.
"""


def extract_graph_from_vision(
    image_path: str,
    overlay_image_path: str,
    confirmed_tags: list[ConfirmedTag],
    page: int,
) -> dict:
    if not confirmed_tags:
        return {"nodes": [], "edges": [], "page": page}

    confirmed_payload = json.dumps(
        [
            {
                "tag": t.tag,
                "component_type": t.component_type,
                "bbox": t.bbox,
            }
            for t in confirmed_tags
        ]
    )
    prompt_text = VISION_PROMPT.format(confirmed_tags=confirmed_payload)

    with open(image_path, "rb") as f:
        img_b64 = base64.standard_b64encode(f.read()).decode()
    overlay_img_b64: str | None = None
    try:
        with open(overlay_image_path, "rb") as f:
            overlay_img_b64 = base64.standard_b64encode(f.read()).decode()
    except Exception as exc:
        print(f"  [warn] could not read overlay for page {page}; using base image only ({exc})")

    image = cv2.imread(image_path)
    if image is not None:
        height, width = image.shape[:2]
        prompt_text += f"\nImage size in pixels: width={width}, height={height}."

    client = get_client()
    response = run_vision_completion(
        client=client,
        img_b64=img_b64,
        overlay_img_b64=overlay_img_b64,
        prompt_text=prompt_text,
        max_tokens=VISION_MAX_TOKENS,
    )
    result = response

    vision_by_tag = {t.tag: None for t in confirmed_tags}
    for node in result.nodes:
        if node.id in vision_by_tag:
            vision_by_tag[node.id] = node
    confirmed_set = set(vision_by_tag)

    clean_edges = []
    connected_confirmed_tags: set[str] = set()
    for edge in result.edges:
        if edge.source not in confirmed_set:
            continue

        connected_confirmed_tags.add(edge.source)
        external = edge.external or edge.target not in confirmed_set
        if edge.target in confirmed_set:
            connected_confirmed_tags.add(edge.target)

        clean_edges.append({
            "source": edge.source,
            "target": edge.target,
            "pipe_label": edge.pipe_label,
            "flow_direction": edge.flow_direction,
            "external": external,
        })

    # Always emit one node per confirmed tag.
    output_nodes: list[dict] = []
    for tag in confirmed_tags:
        vision_node = vision_by_tag[tag.tag]
        attributes = vision_node.attributes.model_dump() if vision_node else EMPTY_VISION_ATTRIBUTES
        position_description = vision_node.position_description if vision_node else None

        has_info = any(v is not None for v in attributes.values()) or bool(position_description)
        has_edges = tag.tag in connected_confirmed_tags

        output_nodes.append({
            "id": tag.tag,
            "component_type": (vision_node.component_type if vision_node else None) or tag.component_type,
            "attributes": attributes,
            "position_description": position_description,
            "needs_review": not (has_info or has_edges),
        })

    return {
        "page": page,
        "nodes": output_nodes,
        "edges": clean_edges,
    }


def run_vision_completion(
    client,
    img_b64: str,
    overlay_img_b64: str | None,
    prompt_text: str,
    max_tokens: int,
) -> VisionResponsePayload:
    content = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
        },
        {
            "type": "text",
            "text": prompt_text,
        },
    ]
    if overlay_img_b64:
        content.insert(1, {
            "type": "text",
            "text": "A second image is provided with confirmed tag bounding boxes and labels overlaid. Use it as guidance for node localization.",
        })
        content.insert(2, {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{overlay_img_b64}"},
        })

    response = client.chat.completions.create(
        model=VISION_MODEL,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": content,
        }],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "vision_graph",
                "strict": True,
                "schema": RESPONSE_SCHEMA,
            },
        },
    )
    choice = response.choices[0] if getattr(response, "choices", None) else None
    if choice is None or getattr(choice, "message", None) is None:
        raise ValueError("Vision returned no message")

    content = getattr(choice.message, "content", None)
    if isinstance(content, str) and content.strip():
        try:
            return VisionResponsePayload.model_validate_json(content)
        except Exception as exc:
            raise ValueError("Vision returned invalid JSON content payload") from exc

    raise ValueError(f"Vision returned no JSON content (content_type={type(content).__name__})")
