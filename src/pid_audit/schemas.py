"""
schemas.py - Shared data models for the pipeline.
"""

from typing import Optional
from pydantic import BaseModel


class SOPRecord(BaseModel):
    equipment_id: str
    raw_name: str
    pressure_psig: Optional[int]
    temperature_min_f: Optional[float]
    temperature_max_f: Optional[float]

class OCRBox(BaseModel):
    text: str
    confidence: float
    bbox: list[int]
    page: int


class OCRCluster(BaseModel):
    texts: list[str]
    bbox: list[int]
    page: int


class ConfirmedTag(BaseModel):
    tag: str
    component_type: Optional[str]
    attributes: dict
    page: int
    confidence: float
    raw_ocr: list[str]
    bbox: Optional[list[int]] = None
    requires_review: bool = False

class Finding(BaseModel):
    severity: str
    rule: str
    equipment_id: str
    detail: str
    sop_value: Optional[str] = None
    pid_value: Optional[str] = None
