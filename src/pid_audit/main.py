"""
main.py - P&ID Auditing Pipeline

"""

from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

from .ingest import render_pdf_pages
from .sop_parse import parse_sop
from .ocr import run_ocr, cluster_ocr_boxes
from .ocr_correct import correct_ocr_tags
from .vision import extract_graph_from_vision
from .graph_build import build_graph
from .audit import audit
from .report import build_report
from .graph_ui import build_graph_viewer
from .visualize import draw_raw_ocr, draw_clusters, draw_confirmed_tags
from .utils import save_json, save_text, ensure_dir


ROOT = Path(__file__).resolve().parents[2]
PID  = ROOT / "data" / "pid" / "diagram.pdf"
SOP  = ROOT / "data" / "sop" / "sop.docx"
OUT  = ROOT / "outputs"


def ingest_documents() -> list[str]:
    print("[1/9] Ingesting documents...")
    page_paths = render_pdf_pages(PID, OUT / "pages", zoom=5.0)
    return page_paths


def parse_sop_records():
    print("[2/9] Parsing SOP...")
    sop_records = parse_sop(SOP)
    save_json(OUT / "sop_structured.json", [r.model_dump() for r in sop_records])
    print(f"      {len(sop_records)} equipment records found")
    return sop_records


def run_ocr_stage(page_paths: list[str]) -> dict[int, list]:
    print("[3/9] Running OCR...")
    clustered_by_page = {}

    for page_num, img_path in enumerate(page_paths, start=1):
        raw_boxes = run_ocr(img_path, page=page_num)
        clusters = cluster_ocr_boxes(raw_boxes, image_path=img_path)

        clustered_by_page[page_num] = clusters

        print(f"      page {page_num}: {len(raw_boxes)} boxes → {len(clusters)} clusters")

        draw_raw_ocr(
            img_path,
            raw_boxes,
            str(OUT / f"debug_1_ocr_raw_page_{page_num}.png"),
        )
        draw_clusters(
            img_path,
            clusters,
            str(OUT / f"debug_2_ocr_clusters_page_{page_num}.png"),
        )

    return clustered_by_page


def run_ocr_correction_stage(clustered_by_page: dict[int, list], page_paths: list[str]) -> dict[int, list]:
    print("[4/9] Correcting OCR tags with LLM...")
    confirmed_by_page = {}

    for page_num, clusters in clustered_by_page.items():
        corrected = correct_ocr_tags(clusters, page_num)
        confirmed_by_page[page_num] = corrected

        print(f"      page {page_num}: {len(corrected)} confirmed tags")

        draw_confirmed_tags(
            page_paths[page_num - 1],
            corrected,
            str(OUT / f"debug_3_confirmed_tags_page_{page_num}.png"),
        )

    all_confirmed = [t for tags in confirmed_by_page.values() for t in tags]
    save_json(OUT / "confirmed_tags.json", [t.model_dump() for t in all_confirmed])
    return confirmed_by_page


def run_vision_stage(page_paths: list[str], confirmed_by_page: dict[int, list]) -> dict[int, dict]:
    print("[5/9] Running Vision graph extraction...")
    vision_by_page = {}

    for page_num, img_path in enumerate(page_paths, start=1):
        confirmed = confirmed_by_page[page_num]
        overlay_path = str(OUT / f"debug_3_confirmed_tags_page_{page_num}.png")
        result = extract_graph_from_vision(img_path, overlay_path, confirmed, page_num)
        vision_by_page[page_num] = result

        print(f"      page {page_num}: {len(result['nodes'])} nodes, {len(result['edges'])} edges")
    return vision_by_page


def run_graph_build_stage(confirmed_by_page: dict[int, list], vision_by_page: dict[int, dict]) -> dict:
    print("[6/9] Building graph...")
    graph = build_graph(confirmed_by_page, vision_by_page)
    save_json(OUT / "graph.json", graph)
    print(f"      {graph['node_count']} nodes, {graph['edge_count']} edges")
    return graph


def run_audit_stage(sop_records, graph: dict):
    print("[7/9] Running audit...")
    findings = audit(sop_records, graph)
    save_json(OUT / "findings.json", [f.model_dump() for f in findings])

    errors = sum(1 for f in findings if f.severity == "ERROR")
    warnings = sum(1 for f in findings if f.severity == "WARNING")
    infos = sum(1 for f in findings if f.severity == "INFO")
    print(f"      {len(findings)} findings: {errors} errors, {warnings} warnings, {infos} info")
    return findings


def run_report_stage(sop_records, graph: dict, findings):
    print("[8/9] Building report...")
    report = build_report(sop_records, graph, findings)
    save_text(OUT / "report.md", report)


def run_graph_ui_stage():
    print("[9/9] Building graph viewer HTML...")
    viewer_path = build_graph_viewer(
        OUT / "graph.json",
        OUT / "graph_viewer.html",
        OUT / "findings.json",
    )
    print(f"      saved: {viewer_path}")


def main():

    ensure_dir(OUT)

    page_paths = ingest_documents()
    sop_records = parse_sop_records()
    clustered_by_page = run_ocr_stage(page_paths)
    confirmed_by_page = run_ocr_correction_stage(clustered_by_page, page_paths)
    vision_by_page = run_vision_stage(page_paths, confirmed_by_page)
    graph = run_graph_build_stage(confirmed_by_page, vision_by_page)
    findings = run_audit_stage(sop_records, graph)
    run_report_stage(sop_records, graph, findings)
    run_graph_ui_stage()

    print("\n Pipeline complete.")

if __name__ == "__main__":
    main()
