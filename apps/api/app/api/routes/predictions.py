from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import Prediction, User
from app.schemas.common import PredictionOut
from app.security import get_current_user
from app.services.predictive import generate_predictions

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/generate", response_model=list[PredictionOut])
async def generate(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await generate_predictions(db, user.organization_id)


@router.get("", response_model=list[PredictionOut])
async def list_predictions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Prediction)
        .where(Prediction.organization_id == user.organization_id)
        .order_by(Prediction.score.desc())
    )
    return result.scalars().all()
