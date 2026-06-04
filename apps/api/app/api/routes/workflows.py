from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import User, Workflow, WorkflowExecution
from app.schemas.common import WorkflowExecuteRequest, WorkflowExecutionOut, WorkflowOut
from app.security import get_current_user
from app.services.workflows import (
    WorkflowError,
    create_workflow_from_suggestion,
    execute_workflow,
    toggle_kill_switch,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/from-suggestion/{suggestion_id}", response_model=WorkflowOut)
async def from_suggestion(
    suggestion_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await create_workflow_from_suggestion(db, user.organization_id, suggestion_id, actor=user.email)
    if not wf:
        raise HTTPException(status_code=400, detail="Suggestion must be approved and have a workflow draft")
    return wf


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workflow).where(Workflow.organization_id == user.organization_id).order_by(Workflow.created_at.desc())
    )
    return result.scalars().all()


@router.post("/execute", response_model=WorkflowExecutionOut)
async def execute(
    body: WorkflowExecuteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await execute_workflow(db, user.organization_id, body.workflow_id, actor=user.email)
    except WorkflowError as e:
        code = 404 if "not found" in str(e) else 409
        raise HTTPException(status_code=code, detail=str(e)) from e


@router.get("/executions", response_model=list[WorkflowExecutionOut])
async def list_executions(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkflowExecution)
        .where(WorkflowExecution.organization_id == user.organization_id)
        .order_by(WorkflowExecution.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/{workflow_id}/kill-switch")
async def kill_switch(
    workflow_id: UUID,
    enabled: bool = True,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    wf = await toggle_kill_switch(db, user.organization_id, workflow_id, enabled, actor=user.email)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"kill_switch": wf.kill_switch, "status": wf.status}
