"""
ocr.py

OCR pipeline:
1. Detect text tokens with Tesseract on an upscaled image.
2. Group tokens into connected text regions using a graph.
3. Re-read each region with a tighter OCR pass.
"""

import os

import cv2
import networkx as nx
import pytesseract
from pytesseract import Output

from .schemas import OCRBox, OCRCluster

# Tunable knobs (keep this surface small)
UPSCALE_FACTOR = float(os.getenv("PID_AUDIT_OCR_UPSCALE_FACTOR", "4"))
CROP_PAD = int(os.getenv("PID_AUDIT_OCR_CROP_PAD", "18"))
LENIENT_MIN_BOX_AREA = int(os.getenv("PID_AUDIT_OCR_LENIENT_MIN_BOX_AREA", "70"))
MAX_CENTER_LINK = int(os.getenv("PID_AUDIT_OCR_MAX_CENTER_LINK", "185"))
TESSERACT_CONFIG = os.getenv("PID_AUDIT_OCR_TESS_CONFIG", "--oem 1 --psm 12")
LENIENT_MIN_DETECT_CONF = float(os.getenv("PID_AUDIT_OCR_LENIENT_MIN_DETECT_CONF", "0.0"))
REFINE_UPSCALE_FACTOR = float(os.getenv("PID_AUDIT_OCR_REFINE_UPSCALE_FACTOR", "4"))
DEDUP_CENTER_RADIUS = int(os.getenv("PID_AUDIT_OCR_DEDUP_CENTER_RADIUS", "18"))
NEIGHBOR_PAD = int(os.getenv("PID_AUDIT_OCR_NEIGHBOR_PAD", "8"))
ROW_Y_TOL = int(os.getenv("PID_AUDIT_OCR_ROW_Y_TOL", "18"))
ROW_H_TOL = int(os.getenv("PID_AUDIT_OCR_ROW_H_TOL", "18"))
COL_X_TOL = int(os.getenv("PID_AUDIT_OCR_COL_X_TOL", "18"))
COL_W_TOL = int(os.getenv("PID_AUDIT_OCR_COL_W_TOL", "26"))
LENIENT_BORDER_MARGIN_RATIO = float(os.getenv("PID_AUDIT_OCR_LENIENT_BORDER_MARGIN_RATIO", "0.012"))
LENIENT_BORDER_MIN_CONF = float(os.getenv("PID_AUDIT_OCR_LENIENT_BORDER_MIN_CONF", "30.0"))


def run_ocr(
    image_path: str,
    page: int,
) -> list[OCRBox]:
    """
    Return word-level OCR detections in original image coordinates.
    Single-pass detection on an upscaled grayscale image.
    """
    gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"Could not read image: {image_path}")

    up = cv2.resize(
        gray,
        None,
        fx=UPSCALE_FACTOR,
        fy=UPSCALE_FACTOR,
        interpolation=cv2.INTER_CUBIC,
    )
    up_w = up.shape[1]
    up_h = up.shape[0]

    detections = detect_tokens(up, page)
    detections = filter_lenient_tokens(detections, canvas_w=up_w, canvas_h=up_h)

    detections = scale_boxes(detections, scale=1.0 / UPSCALE_FACTOR)
    return dedupe_by_center(detections)


def cluster_ocr_boxes(
    boxes: list[OCRBox],
    image_path: str = "",
) -> list[OCRCluster]:
    """
    Group OCR tokens into text regions and optionally refine text per region.
    """
    if not boxes:
        return []

    groups = connected_box_groups(boxes)
    gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE) if image_path else None

    clusters: list[OCRCluster] = []
    for group in groups:
        x1 = min(b.bbox[0] for b in group)
        y1 = min(b.bbox[1] for b in group)
        x2 = max(b.bbox[2] for b in group)
        y2 = max(b.bbox[3] for b in group)
        page = group[0].page
        ordered = sorted(group, key=lambda b: (b.bbox[1], b.bbox[0]))
        texts = [b.text.strip() for b in ordered if b.text.strip()]

        if gray is not None:
            refined = reread_region(gray, x1, y1, x2, y2)
            if refined:
                texts = [refined]

        if not texts:
            continue

        clusters.append(OCRCluster(
            texts=texts,
            bbox=[x1, y1, x2, y2],
            page=page,
        ))

    return clusters


def detect_tokens(image, page: int) -> list[OCRBox]:
    data = pytesseract.image_to_data(image, output_type=Output.DICT, config=TESSERACT_CONFIG)
    out: list[OCRBox] = []

    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        if not text or conf < LENIENT_MIN_DETECT_CONF:
            continue

        x = data["left"][i]
        y = data["top"][i]
        w = data["width"][i]
        h = data["height"][i]
        out.append(OCRBox(
            text=text,
            confidence=conf,
            bbox=[x, y, x + w, y + h],
            page=page,
        ))
    return out


def scale_boxes(boxes: list[OCRBox], scale: float) -> list[OCRBox]:
    out: list[OCRBox] = []
    for box in boxes:
        x1, y1, x2, y2 = box.bbox
        out.append(OCRBox(
            text=box.text,
            confidence=box.confidence,
            bbox=[
                int(round(x1 * scale)),
                int(round(y1 * scale)),
                int(round(x2 * scale)),
                int(round(y2 * scale)),
            ],
            page=box.page,
        ))
    return out


def dedupe_by_center(boxes: list[OCRBox]) -> list[OCRBox]:
    kept: list[OCRBox] = []
    for box in boxes:
        cx = (box.bbox[0] + box.bbox[2]) / 2
        cy = (box.bbox[1] + box.bbox[3]) / 2

        duplicate_idx = None
        for i, existing in enumerate(kept):
            ex = (existing.bbox[0] + existing.bbox[2]) / 2
            ey = (existing.bbox[1] + existing.bbox[3]) / 2
            dist = ((cx - ex) ** 2 + (cy - ey) ** 2) ** 0.5
            if dist < DEDUP_CENTER_RADIUS:
                duplicate_idx = i
                break

        if duplicate_idx is None:
            kept.append(box)
            continue

        if box.confidence > kept[duplicate_idx].confidence:
            kept[duplicate_idx] = box

    return kept


def filter_lenient_tokens(tokens: list[OCRBox], canvas_w: int, canvas_h: int) -> list[OCRBox]:
    """
    Remove obvious false positives from lenient OCR 
    """
    margin = max(12, int(min(canvas_w, canvas_h) * LENIENT_BORDER_MARGIN_RATIO))
    symbol_chars = set("|/\\-_=~<>.,:;()[]{}'\"`")
    ambiguous_singletons = {"I", "l", "i", "!", "|"}
    kept: list[OCRBox] = []

    for box in tokens:
        text = box.text.strip()
        if not text:
            continue

        x1, y1, x2, y2 = box.bbox
        w = max(1, x2 - x1)
        h = max(1, y2 - y1)
        area = w * h

        alnum = sum(ch.isalnum() for ch in text)
        symbols = sum((not ch.isalnum()) and (not ch.isspace()) for ch in text)
        single_symbol = len(text) == 1 and text in symbol_chars
        all_symbols = all((not ch.isalnum()) for ch in text)
        ambiguous_single = len(text) == 1 and text in ambiguous_singletons
        near_border = (
            x1 < margin or y1 < margin or x2 > (canvas_w - margin) or y2 > (canvas_h - margin)
        )

        if all_symbols or single_symbol:
            continue
        if ambiguous_single:
            continue
        if area < LENIENT_MIN_BOX_AREA and alnum <= 1:
            continue
        if symbols > (alnum * 2) and alnum <= 1:
            continue
        if near_border and alnum <= 1 and box.confidence < LENIENT_BORDER_MIN_CONF:
            continue

        kept.append(box)

    return kept


def connected_box_groups(boxes: list[OCRBox]) -> list[list[OCRBox]]:
    graph = nx.Graph()
    graph.add_nodes_from(range(len(boxes)))

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes_should_link(boxes[i], boxes[j]):
                graph.add_edge(i, j)

    groups: list[list[OCRBox]] = []
    for component in nx.connected_components(graph):
        group = [boxes[i] for i in component]
        groups.append(group)
    return groups


def boxes_should_link(a: OCRBox, b: OCRBox) -> bool:
    ax1, ay1, ax2, ay2 = a.bbox
    bx1, by1, bx2, by2 = b.bbox
    aw, ah = ax2 - ax1, ay2 - ay1
    bw, bh = bx2 - bx1, by2 - by1

    acx = (ax1 + ax2) / 2
    acy = (ay1 + ay2) / 2
    bcx = (bx1 + bx2) / 2
    bcy = (by1 + by2) / 2
    center_dist = ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5
    if center_dist > MAX_CENTER_LINK:
        return False

    # Small expanded-overlap to allow near-touching tokens.
    expanded_overlap = not (
        (ax1 - NEIGHBOR_PAD) > (bx2 + NEIGHBOR_PAD)
        or (bx1 - NEIGHBOR_PAD) > (ax2 + NEIGHBOR_PAD)
        or (ay1 - NEIGHBOR_PAD) > (by2 + NEIGHBOR_PAD)
        or (by1 - NEIGHBOR_PAD) > (ay2 + NEIGHBOR_PAD)
    )

    # Row-wise merge: similar baseline/height and small horizontal gap.
    row_gap = max(0, max(bx1 - ax2, ax1 - bx2))
    y_overlap = max(0, min(ay2, by2) - max(ay1, by1))
    y_overlap_ratio = y_overlap / max(1, min(ah, bh))
    row_aligned = (
        row_gap <= max(26, int(1.1 * max(aw, bw)))
        and y_overlap_ratio >= 0.45
        and abs(ay1 - by1) < ROW_Y_TOL
        and abs(ah - bh) < ROW_H_TOL
    )

    # Column-wise merge: same x band and small vertical gap.
    col_gap = max(0, max(by1 - ay2, ay1 - by2))
    x_overlap = max(0, min(ax2, bx2) - max(ax1, bx1))
    x_overlap_ratio = x_overlap / max(1, min(aw, bw))
    col_aligned = (
        col_gap <= max(28, int(1.15 * max(ah, bh)))
        and x_overlap_ratio >= 0.40
        and abs(ax1 - bx1) < COL_X_TOL
        and abs(aw - bw) < COL_W_TOL
    )

    # Extra allowance for two-row tags where top and bottom fragments are center-aligned
    # but have noticeably different widths (e.g., "MV-715" over "-06A").
    center_x_diff = abs(acx - bcx)
    stacked_tag = (
        col_gap <= max(34, int(1.35 * max(ah, bh)))
        and x_overlap_ratio >= 0.25
        and center_x_diff <= max(24, int(0.2 * max(aw, bw)))
    )

    return expanded_overlap or row_aligned or col_aligned or stacked_tag


def reread_region(gray, x1: int, y1: int, x2: int, y2: int) -> str:
    h_img, w_img = gray.shape[:2]
    cx1 = max(0, x1 - CROP_PAD)
    cy1 = max(0, y1 - CROP_PAD)
    cx2 = min(w_img, x2 + CROP_PAD)
    cy2 = min(h_img, y2 + CROP_PAD)

    crop = gray[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return ""

    base = cv2.resize(
        crop,
        None,
        fx=REFINE_UPSCALE_FACTOR,
        fy=REFINE_UPSCALE_FACTOR,
        interpolation=cv2.INTER_CUBIC,
    )
    base_text, base_conf = reread_text_and_conf(base)

    rotated = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
    rotated = cv2.resize(
        rotated,
        None,
        fx=REFINE_UPSCALE_FACTOR,
        fy=REFINE_UPSCALE_FACTOR,
        interpolation=cv2.INTER_CUBIC,
    )
    rot_text, rot_conf = reread_text_and_conf(rotated)
    return rot_text if rot_conf > base_conf else base_text


def reread_text_and_conf(image) -> tuple[str, float]:
    data = pytesseract.image_to_data(image, output_type=Output.DICT, config=TESSERACT_CONFIG)

    words: list[str] = []
    confs: list[float] = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        conf = float(data["conf"][i])
        if conf < 0:
            continue
        words.append(text)
        confs.append(conf)

    if not words:
        return "", -1.0

    return " ".join(words).strip(), sum(confs) / len(confs)
