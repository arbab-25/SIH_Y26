"""Shared cross-database column types (PostgreSQL + SQLite compatible)."""

from sqlalchemy import JSON, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

UUID_TYPE = Uuid(as_uuid=True)
JSON_TYPE = JSONB().with_variant(JSON, "sqlite")
TSVECTOR_TYPE = TSVECTOR().with_variant(Text, "sqlite")
