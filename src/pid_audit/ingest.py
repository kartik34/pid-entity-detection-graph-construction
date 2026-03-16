"""
ingest.py - PDF rendering and SOP text extraction.
"""

from pathlib import Path

import fitz

from .utils import ensure_dir

def render_pdf_pages(pdf_path, output_dir, zoom) -> list[str]:

    ensure_dir(output_dir)
    doc = fitz.open(str(pdf_path))
    page_paths = []

    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        out_path = Path(output_dir) / f"page_{index}.png"
        pix.save(str(out_path))
        page_paths.append(str(out_path))
        print(f"        rendered page {index}")

    doc.close()
    return page_paths
