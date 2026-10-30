from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import ClassifiedEvent, RawEvent, User
from app.schemas.common import DashboardMetrics, EventOut
from app.security import get_current_user
from app.services.metrics import compute_dashboard

router = APIRouter(prefix="/observation", tags=["observation"])


@router.get("/dashboard", response_model=DashboardMetrics)
async def dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await compute_dashboard(db, user.organization_id)


@router.get("/events", response_model=list[EventOut])
async def list_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    query = (
        select(RawEvent, ClassifiedEvent)
        .join(ClassifiedEvent, ClassifiedEvent.raw_event_id == RawEvent.id)
        .where(RawEvent.organization_id == user.organization_id)
        .order_by(RawEvent.occurred_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(query)).all()
    return [
        EventOut(
            id=raw.id,
            subject=raw.subject,
            sender=raw.sender,
            category=cls.category,
            confidence=cls.confidence,
            occurred_at=raw.occurred_at,
        )
        for raw, cls in rows
    ]
