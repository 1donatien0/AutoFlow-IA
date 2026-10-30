from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import DiscoveredProcess, ProcessInstance, User
from app.schemas.common import DiscoveredProcessOut, ProcessInstanceOut
from app.security import get_current_user
from app.services.process_mining import discover_processes

router = APIRouter(prefix="/processes", tags=["processes"])


@router.post("/discover", response_model=list[DiscoveredProcessOut])
async def discover(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await discover_processes(db, user.organization_id)


@router.get("", response_model=list[DiscoveredProcessOut])
async def list_processes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    result = await db.execute(
        select(DiscoveredProcess)
        .where(DiscoveredProcess.organization_id == user.organization_id)
        .order_by(DiscoveredProcess.frequency.desc())
    )
    return result.scalars().all()


@router.get("/{process_id}/instances", response_model=list[ProcessInstanceOut])
async def list_instances(
    process_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    result = await db.execute(
        select(ProcessInstance)
        .where(
            ProcessInstance.organization_id == user.organization_id,
            ProcessInstance.process_id == process_id,
        )
        .order_by(ProcessInstance.started_at.desc())
    )
    return result.scalars().all()


@router.get("/instances/{instance_id}/timeline")
async def instance_timeline(
    instance_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    result = await db.execute(
        select(ProcessInstance).where(
            ProcessInstance.id == instance_id,
            ProcessInstance.organization_id == user.organization_id,
        )
    )
    inst = result.scalar_one_or_none()
    if not inst:
        raise HTTPException(status_code=404, detail="Instance not found")
    return {"case_id": inst.case_id, "timeline": inst.timeline, "duration_minutes": inst.duration_minutes}
