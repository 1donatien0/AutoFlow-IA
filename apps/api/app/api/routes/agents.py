from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import AgentRun, User
from app.schemas.common import AgentRunRequest, AgentRunResponse
from app.security import get_current_user
from app.services.agents import run_agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run", response_model=AgentRunResponse)
async def run(
    body: AgentRunRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    return await run_agent(db, user.organization_id, body.agent_type, body.task, actor=user.email)


@router.get("/runs", response_model=list[AgentRunResponse])
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.organization_id == user.organization_id)
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
