"""Finer RBAC dependencies (Phase 3).

Role hierarchy (least privilege first):
    INSPECTOR < SUPERVISOR < SENIOR_OFFICER?  — no: SUPERVISOR is a distinct
    office role, not a rank between inspector and officer.

Actual roles and their powers:
    INSPECTOR       scan, view own scans/reports, override own fields
    SUPERVISOR      everything an inspector does + view office scans/reports
                    + bulk exports (the 'office' view, previously hardwired
                    to SENIOR_OFFICER)
    SENIOR_OFFICER  supervisor powers + escalate/email reports + rerun scans
    ADMIN           everything + user management + audit log + deletions

The role enum on users gains SUPERVISOR; existing rows keep working because
the check helpers treat SENIOR_OFFICER/ADMIN as strictly containing the
supervisor powers.
"""

from fastapi import Depends, HTTPException

from app.api.deps import get_current_user
from app.models.user import User, UserRole


def role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def is_at_least(user: User, roles: tuple) -> bool:
    """Membership check for the passed role tuple (order-insensitive)."""
    return role_value(user) in roles


async def require_inspector_or_above(user: User = Depends(get_current_user)) -> User:
    """Any authenticated staff role (all current roles qualify)."""
    return user


async def require_supervisor_or_above(user: User = Depends(get_current_user)) -> User:
    """Supervisor powers: office-wide visibility + exports."""
    if not is_at_least(user, ("SUPERVISOR", "SENIOR_OFFICER", "ADMIN")):
        raise HTTPException(status_code=403, detail="Supervisor access required")
    return user


async def require_officer_or_above(user: User = Depends(get_current_user)) -> User:
    """Officer powers: escalation, reruns."""
    if not is_at_least(user, ("SENIOR_OFFICER", "ADMIN")):
        raise HTTPException(status_code=403, detail="Senior officer access required")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_at_least(user, ("ADMIN",)):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def sees_all_scans(user: User) -> bool:
    """Office-wide scan/report visibility (supervisor and above)."""
    return is_at_least(user, ("SUPERVISOR", "SENIOR_OFFICER", "ADMIN"))
