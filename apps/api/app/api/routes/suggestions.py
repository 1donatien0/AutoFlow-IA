from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import Suggestion, User
from app.schemas.common import SuggestionOut, SuggestionUpdate
from app.security import get_current_user
from app.services.suggestions import generate_suggestions, update_suggestion_status

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


@router.post("/generate", response_model=list[SuggestionOut])
async def generate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await generate_suggestions(db, user.organization_id)


@router.get("", response_model=list[SuggestionOut])
async def list_suggestions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Suggestion)
        .where(Suggestion.organization_id == user.organization_id)
        .order_by(Suggestion.roi_score.desc())
    )
    return result.scalars().all()


@router.patch("/{suggestion_id}", response_model=SuggestionOut)
async def update_suggestion(
    suggestion_id: UUID,
    body: SuggestionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sug = await update_suggestion_status(db, user.organization_id, suggestion_id, body.status, actor=user.email)
    if not sug:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return sug
