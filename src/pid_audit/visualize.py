"""Simple debug visualizations for OCR pipeline outputs."""

from pathlib import Path

import cv2

from .schemas import OCRBox, OCRCluster, ConfirmedTag
from .utils import ensure_dir


CLUSTER_COLOUR = (120, 160, 220)


def confidence_colour(confidence: float) -> tuple[int, int, int]:
    if confidence >= 70:
        return (0, 200, 0)
    if confidence >= 40:
        return (0, 200, 200)
    return (0, 0, 200)


def draw_raw_ocr(image_path: str, boxes: list[OCRBox], out_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read: {image_path}")

    for box in boxes:
        x1, y1, x2, y2 = box.bbox
        colour = confidence_colour(box.confidence)
        label = f"{box.text} ({int(box.confidence)})"

        cv2.rectangle(img, (x1, y1), (x2, y2), colour, 1)
        cv2.putText(
            img,
            label,
            (x1, max(y1 - 4, 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.35,
            colour,
            1,
        )

    save_image(img, out_path)


def draw_clusters(image_path: str, clusters: list[OCRCluster], out_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read: {image_path}")

    for i, cluster in enumerate(clusters):
        x1, y1, x2, y2 = cluster.bbox
        colour = CLUSTER_COLOUR

        preview = " | ".join(cluster.texts[:3])
        if len(cluster.texts) > 3:
            preview += " ..."

        cv2.rectangle(img, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(
            img,
            f"[{i}] {preview}",
            (x1, max(y1 - 5, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            colour,
            1,
        )

    save_image(img, out_path)


def draw_confirmed_tags(image_path: str, tags: list[ConfirmedTag], out_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read: {image_path}")

    tags_by_bbox: dict[tuple[int, int, int, int], list[ConfirmedTag]] = {}
    for tag in tags:
        if tag.bbox is None:
            continue
        key = tuple(tag.bbox)
        tags_by_bbox.setdefault(key, []).append(tag)

    for bbox, grouped_tags in tags_by_bbox.items():
        x1, y1, x2, y2 = bbox

        requires_review = any(t.requires_review for t in grouped_tags)
        best_conf = max(t.confidence for t in grouped_tags)

        if requires_review or best_conf < 0.6:
            colour = (0, 0, 220)
        elif best_conf < 0.8:
            colour = (0, 200, 200)
        else:
            colour = (0, 200, 0)

        cv2.rectangle(img, (x1, y1), (x2, y2), colour, 2)

        tag_names = sorted({t.tag for t in grouped_tags})
        label = " | ".join(tag_names)
        if len(label) > 72:
            label = label[:69] + "..."
        if requires_review:
            label += " [REVIEW]"

        cv2.putText(
            img,
            label,
            (x1, max(y1 - 6, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            colour,
            1,
        )

    save_image(img, out_path)


def save_image(img, out_path: str):
    ensure_dir(Path(out_path).parent)
    cv2.imwrite(out_path, img)
    print(f"      saved: {out_path}")
