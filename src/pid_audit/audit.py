"""
audit.py

Simple deterministic SOP vs P&ID audit.
Uses current graph fields only.
"""

import re

from .models import AuditNode
from .schemas import SOPRecord, Finding

TEMP_F_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*°?\s*F\b", re.IGNORECASE)


def family_tag(tag: str) -> str:
    match = re.match(r"^([A-Z]+-\d+)", tag)
    return match.group(1) if match else tag


def variant_from_name(raw_name: str) -> str | None:
    name = (raw_name or "").lower()
    if "shell" in name:
        return "SHELL"
    if "tube" in name:
        return "TUBE"
    return None


def node_blob(node: AuditNode) -> str:
    parts = [node.tag, node.notation, node.service, node.position_description]
    return " ".join(str(p).strip().upper() for p in parts if p)


def matching_nodes(
    rec: SOPRecord,
    nodes: list[AuditNode],
    by_family: dict[str, list[AuditNode]],
) -> list[AuditNode]:
    exact = by_family.get(rec.equipment_id, [])
    if exact:
        return exact

    variant = variant_from_name(rec.raw_name)
    out: list[AuditNode] = []
    for node in nodes:
        blob = node_blob(node)
        if rec.equipment_id not in blob:
            continue
        if variant and variant not in blob:
            continue
        out.append(node)
    return out


def pressure_candidates(nodes: list[AuditNode]) -> list[float]:
    vals: list[float] = []
    for node in nodes:
        if node.design_pressure_psig is not None:
            vals.append(node.design_pressure_psig)
        if node.pressure_rating_psig is not None:
            vals.append(node.pressure_rating_psig)
    return vals


def temperature_candidates(nodes: list[AuditNode]) -> list[float]:
    vals: list[float] = []
    for node in nodes:
        if node.design_temperature_f is not None:
            vals.append(node.design_temperature_f)
        if node.temperature_f:
            vals.extend(float(v) for v in TEMP_F_RE.findall(node.temperature_f))

    out: list[float] = []
    for value in vals:
        if value not in out:
            out.append(value)
    return out


def audit(sop_records: list[SOPRecord], graph: dict) -> list[Finding]:
    findings: list[Finding] = []

    nodes: list[AuditNode] = []
    by_family: dict[str, list[AuditNode]] = {}
    for raw_node in graph.get("nodes", []):
        try:
            node = AuditNode.from_raw(raw_node)
        except Exception:
            continue
        nodes.append(node)
        by_family.setdefault(family_tag(node.tag), []).append(node)

    for rec in sop_records:
        has_issue = False
        matches = matching_nodes(rec, nodes, by_family)

        if not matches:
            findings.append(Finding(
                severity="ERROR",
                rule="missing_in_pid",
                equipment_id=rec.equipment_id,
                detail=f"{rec.equipment_id} ({rec.raw_name}) is required by SOP but not found in the P&ID.",
            ))
            continue

        if rec.pressure_psig is not None:
            pressures = pressure_candidates(matches)
            if pressures:
                sop_p = float(rec.pressure_psig)
                if not any(int(p) == int(sop_p) for p in pressures):
                    has_issue = True
                    findings.append(Finding(
                        severity="WARNING",
                        rule="pressure_mismatch",
                        equipment_id=rec.equipment_id,
                        detail=f"Pressure mismatch on {rec.equipment_id}: SOP={sop_p:g} PSIG, P&ID={pressures[0]:g} PSIG.",
                        sop_value=f"{sop_p:g}",
                        pid_value=f"{pressures[0]:g}",
                    ))

        if rec.temperature_min_f is not None and rec.temperature_max_f is not None:
            temps = temperature_candidates(matches)
            if temps:
                sop_min = float(rec.temperature_min_f)
                sop_max = float(rec.temperature_max_f)
                if not any(sop_min <= t <= sop_max for t in temps):
                    has_issue = True
                    nearest = min(temps, key=lambda t: min(abs(t - sop_min), abs(t - sop_max)))
                    findings.append(Finding(
                        severity="WARNING",
                        rule="temperature_mismatch",
                        equipment_id=rec.equipment_id,
                        detail=f"Temperature mismatch on {rec.equipment_id}: SOP={sop_min:g} to {sop_max:g} F, P&ID={nearest:g} F.",
                        sop_value=f"{sop_min:g} to {sop_max:g}",
                        pid_value=f"{nearest:g}",
                    ))

        if not has_issue:
            findings.append(Finding(
                severity="INFO",
                rule="sop_check_pass",
                equipment_id=rec.equipment_id,
                detail=f"{rec.equipment_id} ({rec.raw_name}) passed: no SOP-vs-P&ID mismatches detected.",
            ))

    return findings
