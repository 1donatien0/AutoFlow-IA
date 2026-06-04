from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AuditLog


async def log_audit(
    db: AsyncSession,
    org_id: UUID,
    action: str,
    details: dict | None = None,
    actor: str | None = None,
) -> None:
    db.add(
        AuditLog(
            organization_id=org_id,
            action=action,
            actor=actor,
            details=details,
        )
    )
