"""Gouvernance des données (RGPD) et journal d'audit."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import AuditLog, User
from app.schemas.common import AuditLogOut
from app.security import get_current_user
from app.services.audit import log_audit
from app.services.data_governance import export_organization, purge_organization_data

router = APIRouter(prefix="/organization", tags=["organization"])


@router.get("/audit-logs", response_model=list[AuditLogOut])
async def audit_logs(
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.organization_id == user.organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/export")
async def export_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await log_audit(db, user.organization_id, "organization_data_exported", None, actor=user.email)
    return await export_organization(db, user.organization_id)


@router.delete("/data")
async def delete_data(
    confirm: bool = Query(False, description="Doit valoir true pour confirmer l'effacement"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass confirm=true to delete all organization data")
    deleted = await purge_organization_data(db, user.organization_id, actor=user.email)
    return {"deleted": deleted}
