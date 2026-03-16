"""
graph_build.py

Merges OCR confirmed tags (nodes + attributes) with Vision results
(edges + topology) into a NetworkX graph, then serialises to dict.
"""

import re
import networkx as nx

from .schemas import ConfirmedTag
from .tag_taxonomy import PREFIX_TYPES, MAJOR_PREFIXES


def family_tag(tag: str) -> str:
    """F-715A → F-715"""
    match = re.match(r'^([A-Z]+-\d+)', tag)
    return match.group(1) if match else tag


def prefix_tag(tag: str) -> str:
    return tag.split("-")[0]


def node_key(tag: str, page: int) -> str:
    return f"{tag}@p{page}"


def equipment_class(tag: str) -> str:
    return "major" if prefix_tag(tag) in MAJOR_PREFIXES else "minor"


def canonical_component_type(tag: str, suggested_type: str | None) -> str:
    by_prefix = PREFIX_TYPES.get(prefix_tag(tag))
    if by_prefix:
        return by_prefix
    if isinstance(suggested_type, str) and suggested_type.strip():
        return suggested_type.strip().lower().replace(" ", "_")
    return "unknown"


def build_graph(
    confirmed_by_page: dict[int, list[ConfirmedTag]],
    vision_by_page: dict[int, dict],
) -> dict:
    G = nx.DiGraph()
    tag_to_node_key: dict[tuple[int, str], str] = {}

    for page, tags in confirmed_by_page.items():
        for t in tags:
            comp_type = canonical_component_type(t.tag, t.component_type)
            node_id = node_key(t.tag, page)
            tag_to_node_key[(page, t.tag)] = node_id
            G.add_node(node_id, **{
                "tag": t.tag,
                "component_type": comp_type,
                "equipment_class": equipment_class(t.tag),
                "family": family_tag(t.tag),
                "page": page,
                "confidence": t.confidence,
                "needs_review": t.requires_review,
                "bbox": t.bbox,
                "source": "ocr",
                **{k: v for k, v in t.attributes.items() if v is not None},
            })

    for page, vision in vision_by_page.items():
        for vnode in vision.get("nodes", []):
            raw_id = vnode.get("id")
            if not raw_id:
                nid = None
            else:
                nid = tag_to_node_key.get((page, raw_id))
                if nid is None:
                    nid = node_key(raw_id, page)
            if raw_id and G.has_node(nid):
                vision_needs_review = bool(vnode.get("needs_review", False))
                G.nodes[nid]["needs_review"] = bool(G.nodes[nid].get("needs_review", False)) or vision_needs_review
                for k, v in vnode.get("attributes", {}).items():
                    if v is not None and k not in G.nodes[nid]:
                        G.nodes[nid][k] = v
                if not G.nodes[nid].get("position_description"):
                    G.nodes[nid]["position_description"] = vnode.get("position_description")

        for edge in vision.get("edges", []):
            src_tag = edge.get("source")
            tgt_tag = edge.get("target")
            if not src_tag or not tgt_tag:
                continue
            src = tag_to_node_key.get((page, src_tag), node_key(src_tag, page))
            tgt = tag_to_node_key.get((page, tgt_tag), node_key(tgt_tag, page))
            # add external nodes that don't exist yet
            for nid, tag in [(src, src_tag), (tgt, tgt_tag)]:
                if not G.has_node(nid):
                    G.add_node(nid,
                        tag=tag,
                        component_type="external",
                        equipment_class="external",
                        family=family_tag(tag),
                        page=page,
                        source="vision_inference",
                        confidence=1.0,
                        needs_review=False,
                        bbox=None,
                    )
            G.add_edge(src, tgt,
                pipe_label=edge.get("pipe_label"),
                flow_direction=edge.get("flow_direction", "unknown"),
            )

    return {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "nodes": [{"id": nid, **attrs} for nid, attrs in G.nodes(data=True)],
        "edges": [{"source": u, "target": v, **attrs} for u, v, attrs in G.edges(data=True)],
    }
