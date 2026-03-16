"""
models.py

Internal typed models used by audit and vision stages.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    tag: str = ""
    notation: str | None = None
    service: str | None = None
    position_description: str | None = None
    design_pressure_psig: float | None = None
    pressure_rating_psig: float | None = None
    design_temperature_f: float | None = None
    temperature_f: str | None = None

    @field_validator("temperature_f", mode="before")
    @classmethod
    def coerce_temperature_text(cls, value):
        if value is None:
            return None
        return str(value)

    @classmethod
    def from_raw(cls, raw: dict) -> "AuditNode":
        data = dict(raw)
        tag = data.get("tag")
        if not tag:
            node_id = str(data.get("id", ""))
            tag = node_id.split("@p")[0] if "@p" in node_id else node_id
        data["tag"] = tag
        return cls.model_validate(data)


class VisionAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    set_point_psig: float | None
    size_inches: str | None
    notation: str | None
    pipe_label: str | None
    service: str | None
    design_pressure_psig: float | None
    design_temperature_f: float | None
    pressure_rating_psig: float | None


class VisionNodePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    component_type: str | None
    attributes: VisionAttributes
    position_description: str | None


class VisionEdgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    pipe_label: str | None
    flow_direction: Literal["forward", "bidirectional"]
    external: bool


class VisionResponsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[VisionNodePayload]
    edges: list[VisionEdgePayload]


class OCRCorrectionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag: str
    component_type: str
    set_point_psig: float | None = None
    size_inches: str | None = None
    notation: str | None = None
    pipe_label: str | None = None
    confidence: float
    raw_ocr: list[str] = Field(default_factory=list)
    cluster_index: int


class OCRCorrectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tags: list[OCRCorrectionItem] = Field(default_factory=list)
