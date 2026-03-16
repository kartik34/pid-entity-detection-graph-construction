"""
(vibe coded) graph_ui.py

Create a simple interactive HTML viewer for graph.json:
- Tab per page
- Findings tab from findings.json
- Node hover shows all attributes
- Edge labels show pipe labels
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>P&ID Graph Viewer</title>
  <script src="https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"></script>
  <style>
    :root {
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --line: #dbe2ea;
      --accent: #1d4ed8;
      --offpage: #94a3b8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
    }
    .wrap {
      max-width: 1400px;
      margin: 0 auto;
      padding: 14px;
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
    }
    .title {
      margin: 0 0 8px;
      font-size: 18px;
      font-weight: 700;
    }
    .meta {
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }
    .tab {
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 13px;
      cursor: pointer;
    }
    .tab.active {
      border-color: var(--accent);
      color: var(--accent);
      background: #eff6ff;
    }
    #cy {
      width: 100%;
      height: 70vh;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }
    #findings {
      display: none;
      width: 100%;
      min-height: 70vh;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      padding: 12px;
      overflow: auto;
    }
    .finding {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      margin-bottom: 8px;
      font-size: 13px;
    }
    .sev {
      display: inline-block;
      font-weight: 700;
      margin-right: 8px;
      padding: 2px 6px;
      border-radius: 999px;
      font-size: 11px;
    }
    .sev.ERROR { background: #fee2e2; color: #991b1b; }
    .sev.WARNING { background: #fef3c7; color: #92400e; }
    .sev.INFO { background: #dbeafe; color: #1e3a8a; }
    .legend {
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }
    .colour-legend {
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      font-size: 12px;
      color: var(--text);
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 8px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
    }
    .swatch {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      border: 1px solid #1f2937;
      display: inline-block;
    }
    #tooltip {
      position: fixed;
      z-index: 9999;
      pointer-events: none;
      min-width: 220px;
      max-width: 520px;
      display: none;
      border: 1px solid #1f2937;
      border-radius: 8px;
      background: #0f172a;
      color: #e2e8f0;
      padding: 10px;
      font-size: 12px;
      white-space: pre-wrap;
      line-height: 1.35;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1 class="title">P&ID Graph Viewer</h1>
      <p class="meta" id="meta"></p>
      <div class="tabs" id="tabs"></div>
      <div id="cy"></div>
      <div id="findings"></div>
      <div class="colour-legend">
        <span class="legend-item"><span class="swatch" style="background:#0ea5e9"></span>Valves / Instruments</span>
        <span class="legend-item"><span class="swatch" style="background:#16a34a"></span>Vessels / Separators</span>
        <span class="legend-item"><span class="swatch" style="background:#f97316"></span>Pumps</span>
        <span class="legend-item"><span class="swatch" style="background:#eab308"></span>Exchangers</span>
        <span class="legend-item"><span class="swatch" style="background:#8b5cf6"></span>Coolers</span>
        <span class="legend-item"><span class="swatch" style="background:#cbd5e1"></span>External (off-page)</span>
        <span class="legend-item"><span class="swatch" style="background:#64748b"></span>Unknown / Other</span>
      </div>
      <div class="legend">
        <span><b>Hover node:</b> full attributes</span>
        <span><b>Larger node:</b> major equipment (V/F/P/E/AC)</span>
        <span><b>Gray dashed node:</b> connected from another page</span>
        <span><b>Edge label:</b> pipe label</span>
      </div>
    </div>
  </div>
  <div id="tooltip"></div>

  <script>
    const payload = __GRAPH_PAYLOAD__;

    const meta = document.getElementById("meta");
    const tabs = document.getElementById("tabs");
    const findingsPanel = document.getElementById("findings");
    const graphPanel = document.getElementById("cy");
    const tooltip = document.getElementById("tooltip");
    let cy = null;

    function esc(v) {
      return String(v)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function nodeColor(type) {
      const t = String(type || "").toLowerCase();
      if (
        t.includes("valve") ||
        t.includes("indicator") ||
        t.includes("transmitter") ||
        t.includes("recorder") ||
        t.includes("instrument")
      ) return "#0ea5e9";
      if (t.includes("vessel") || t.includes("separator") || t.includes("filter")) return "#16a34a";
      if (t.includes("pump")) return "#f97316";
      if (t.includes("exchanger")) return "#eab308";
      if (t.includes("cooler")) return "#8b5cf6";
      return "#64748b";
    }

    function pageElements(page) {
      const pageNodeIds = new Set(
        payload.nodes.filter(n => n.page === page).map(n => n.id)
      );
      const edges = payload.edges.filter(
        e => pageNodeIds.has(e.source) || pageNodeIds.has(e.target)
      );
      const keepIds = new Set(pageNodeIds);
      for (const e of edges) {
        keepIds.add(e.source);
        keepIds.add(e.target);
      }

      const pageNodes = payload.nodes.filter(n => keepIds.has(n.id));
      const pageNodesWithBbox = pageNodes.filter(
        n => n.page === page && Array.isArray(n.attrs?.bbox) && n.attrs.bbox.length === 4
      );

      let minX = 0, maxX = 1, minY = 0, maxY = 1;
      if (pageNodesWithBbox.length > 0) {
        const xs = pageNodesWithBbox.map(n => (n.attrs.bbox[0] + n.attrs.bbox[2]) / 2);
        const ys = pageNodesWithBbox.map(n => (n.attrs.bbox[1] + n.attrs.bbox[3]) / 2);
        minX = Math.min(...xs); maxX = Math.max(...xs);
        minY = Math.min(...ys); maxY = Math.max(...ys);
      }

      function norm(val, minVal, maxVal, outMin, outMax) {
        if (maxVal <= minVal) return (outMin + outMax) / 2;
        return outMin + ((val - minVal) / (maxVal - minVal)) * (outMax - outMin);
      }

      const OFFPAGE_X = 1120;
      const OFFPAGE_Y_START = 80;
      const OFFPAGE_Y_STEP = 42;
      const offpageOrder = pageNodes
        .filter(n => !(n.page === page && Array.isArray(n.attrs?.bbox) && n.attrs.bbox.length === 4))
        .map(n => n.id)
        .sort();
      const offpageIndex = new Map(offpageOrder.map((id, i) => [id, i]));

      const nodes = pageNodes.map(n => {
        const attrs = Object.assign({}, n.attrs);
        const lines = [`id: ${n.id}`];
        for (const [k, v] of Object.entries(attrs)) {
          lines.push(`${k}: ${JSON.stringify(v)}`);
        }

        let x = 220;
        let y = 220;
        if (n.page === page && Array.isArray(attrs.bbox) && attrs.bbox.length === 4) {
          const cx = (attrs.bbox[0] + attrs.bbox[2]) / 2;
          const cy = (attrs.bbox[1] + attrs.bbox[3]) / 2;
          x = norm(cx, minX, maxX, 80, 980);
          y = norm(cy, minY, maxY, 80, 740);
        } else {
          const idx = offpageIndex.get(n.id) || 0;
          x = OFFPAGE_X;
          y = OFFPAGE_Y_START + idx * OFFPAGE_Y_STEP;
        }

        return {
          data: {
            id: n.id,
            label: n.label,
            type: n.component_type || "unknown",
            eq_class: n.equipment_class || "minor",
            page: n.page,
            offpage: n.page !== page ? "1" : "0",
            tooltip: lines.join("\\n"),
          },
          position: { x, y }
        };
      });

      const cyEdges = edges.map(e => ({
        data: {
          id: `${e.source}->${e.target}::${e.pipe_label || ""}`,
          source: e.source,
          target: e.target,
          label: e.pipe_label || "",
          flow: e.flow_direction || "forward",
        }
      }));
      return { nodes, edges: cyEdges };
    }

    function showGraph() {
      graphPanel.style.display = "block";
      findingsPanel.style.display = "none";
    }

    function showFindings() {
      graphPanel.style.display = "none";
      findingsPanel.style.display = "block";
      if (!payload.findings || payload.findings.length === 0) {
        findingsPanel.innerHTML = "<p>No findings.</p>";
        return;
      }

      const rows = payload.findings.map(f => {
        const sev = esc(f.severity || "INFO");
        const eq = esc(f.equipment_id || "");
        const detail = esc(f.detail || "");
        const rule = esc(f.rule || "");
        return `
          <div class="finding">
            <span class="sev ${sev}">${sev}</span>
            <b>${eq}</b>
            <div>${detail}</div>
            <div style="color:#64748b;margin-top:4px;">rule: ${rule}</div>
          </div>
        `;
      });
      findingsPanel.innerHTML = rows.join("");
    }

    function renderGraph(page) {
      showGraph();
      const { nodes, edges } = pageElements(page);
      if (cy) cy.destroy();

      cy = cytoscape({
        container: document.getElementById("cy"),
        elements: [...nodes, ...edges],
        style: [
          {
            selector: "node",
            style: {
              "background-color": ele => nodeColor(ele.data("type")),
              "label": "data(label)",
              "font-size": 10,
              "text-wrap": "wrap",
              "text-max-width": 90,
              "text-valign": "center",
              "text-halign": "center",
              "color": "#0f172a",
              "border-width": 2,
              "border-color": "#0f172a",
              "width": 28,
              "height": 28
            }
          },
          {
            selector: 'node[eq_class = "major"]',
            style: {
              "width": 44,
              "height": 44,
              "font-size": 12,
              "border-width": 3
            }
          },
          {
            selector: 'node[offpage = "1"]',
            style: {
              "background-color": "#cbd5e1",
              "border-color": "#64748b",
              "border-style": "dashed"
            }
          },
          {
            selector: "edge",
            style: {
              "width": 2,
              "line-color": "#64748b",
              "target-arrow-color": "#64748b",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              "label": "data(label)",
              "font-size": 9,
              "text-background-opacity": 1,
              "text-background-color": "#ffffff",
              "text-background-padding": 1
            }
          }
        ],
        layout: {
          name: "preset",
          fit: true,
          padding: 18
        }
      });

      cy.on("mouseover", "node", evt => {
        tooltip.textContent = evt.target.data("tooltip");
        tooltip.style.display = "block";
      });
      cy.on("mousemove", "node", evt => {
        tooltip.style.left = `${evt.originalEvent.clientX + 12}px`;
        tooltip.style.top = `${evt.originalEvent.clientY + 12}px`;
      });
      cy.on("mouseout", "node", () => {
        tooltip.style.display = "none";
      });
    }

    function renderTabs() {
      const pages = payload.pages;
      tabs.innerHTML = "";
      pages.forEach((p, idx) => {
        const btn = document.createElement("button");
        btn.className = `tab ${idx === 0 ? "active" : ""}`;
        btn.textContent = `Page ${p}`;
        btn.addEventListener("click", () => {
          document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
          btn.classList.add("active");
          renderGraph(p);
        });
        tabs.appendChild(btn);
      });

      const findingsBtn = document.createElement("button");
      findingsBtn.className = "tab";
      findingsBtn.textContent = "Findings";
      findingsBtn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        findingsBtn.classList.add("active");
        showFindings();
      });
      tabs.appendChild(findingsBtn);

      if (pages.length > 0) renderGraph(pages[0]);
    }

    const findingCount = (payload.findings || []).length;
    meta.textContent = `Nodes: ${payload.nodes.length} | Edges: ${payload.edges.length} | Findings: ${findingCount}`;
    renderTabs();
  </script>
</body>
</html>
"""


def node_label(node: dict) -> str:
    tag = node.get("tag")
    if isinstance(tag, str) and tag:
        return tag
    node_id = str(node.get("id", ""))
    if "@p" in node_id:
        return node_id.split("@p")[0]
    return node_id


def build_graph_viewer(graph_path: Path, out_path: Path, findings_path: Path | None = None) -> Path:
    graph = json.loads(graph_path.read_text())
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    findings = []
    if findings_path and findings_path.exists():
        findings = json.loads(findings_path.read_text())

    pages = sorted({
        int(n.get("page"))
        for n in nodes
        if isinstance(n.get("page"), int)
    })

    payload_nodes = []
    for n in nodes:
        attrs = {k: v for k, v in n.items() if k != "id"}
        payload_nodes.append({
            "id": n.get("id"),
            "label": node_label(n),
            "page": n.get("page"),
            "component_type": n.get("component_type"),
            "equipment_class": n.get("equipment_class"),
            "attrs": attrs,
        })

    payload_edges = [
        {
            "source": e.get("source"),
            "target": e.get("target"),
            "pipe_label": e.get("pipe_label"),
            "flow_direction": e.get("flow_direction", "forward"),
        }
        for e in edges
        if e.get("source") and e.get("target")
    ]

    payload = {
        "pages": pages,
        "nodes": payload_nodes,
        "edges": payload_edges,
        "findings": findings,
    }

    html = HTML_TEMPLATE.replace("__GRAPH_PAYLOAD__", json.dumps(payload))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Build simple interactive graph viewer HTML.")
    parser.add_argument("--graph", default="outputs/graph.json", help="Path to graph.json")
    parser.add_argument("--findings", default="outputs/findings.json", help="Path to findings.json")
    parser.add_argument("--out", default="outputs/graph_viewer.html", help="Output HTML path")
    args = parser.parse_args()

    out = build_graph_viewer(Path(args.graph), Path(args.out), Path(args.findings))
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
