"""Pydantic schemas for rules and schedules."""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from uuid import UUID


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rule_number: str
    chapter: Optional[str] = None
    title: Optional[str] = None
    full_text: str
    schedule_ref: Optional[str] = None
    applies_to: Optional[dict[str, Any]] = None
    source_page: Optional[int] = None
    highlight: Optional[str] = None


class SchedulePackSizeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    commodity: str
    unit: str
    allowed_values: list[Any]
    rule_ref: Optional[str] = None
