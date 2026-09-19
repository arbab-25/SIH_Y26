"""Pydantic schemas for rules and schedules."""

from pydantic import BaseModel
from typing import Optional, Any
from uuid import UUID


class RuleResponse(BaseModel):
    id: UUID
    rule_number: str
    chapter: Optional[str] = None
    title: Optional[str] = None
    full_text: str
    schedule_ref: Optional[str] = None
    applies_to: Optional[dict[str, Any]] = None
    source_page: Optional[int] = None
    highlight: Optional[str] = None

    class Config:
        from_attributes = True


class SchedulePackSizeResponse(BaseModel):
    id: UUID
    commodity: str
    unit: str
    allowed_values: list[Any]
    rule_ref: Optional[str] = None

    class Config:
        from_attributes = True
