from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncomingVital(BaseModel):
    hr: int = Field(ge=0, le=260)
    spo2: int = Field(ge=0, le=100)
    movement: int = Field(ge=0, le=500)
    scenario: str = Field(default="Normal", min_length=1)
    source: str = Field(default="simulator", min_length=1)
    patient_id: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    context: dict[str, Any] | None = None


class SimulationScenarioRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=64)


class ProcessDataRequest(BaseModel):
    values: list[float] = Field(default_factory=list)
    operation: str = Field(default="average", pattern="^(average|sum|min|max)$")
    tag: str | None = None
