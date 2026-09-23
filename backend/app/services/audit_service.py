"""Audit service — records who scanned what, with what inputs and outcome.

Phase 3: the audit_logs table existed but nothing wrote to it. Every scan
now logs: actor, action, input SHA-256 (the label images — never the images
themselves), rule version applied, outcome and duration. Auth events and
overrides are logged too. Failures never break the audited operation: a
failed audit write prints and moves on.
"""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


def hash_input(payload: dict) -> str:
    """Deterministic SHA-256 over the scan inputs (image paths + options).

    Image paths are uuid-renamed on upload so the hash identifies the exact
    submission without exposing file contents.
    """
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def record_audit(
    db: AsyncSession,
    *,
    user_id: Optional[uuid.UUID],
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    meta: Optional[dict] = None,
    ip: Optional[str] = None,
) -> None:
    """Write one audit row. Never raises — audit failure must not fail the scan."""
    try:
        db.add(
            AuditLog(
                user_id=user_id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                meta=meta or {},
                ip=(ip or "")[:45] or None,
                created_at=datetime.utcnow(),
            )
        )
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] audit write failed for action={action}: {exc}")
