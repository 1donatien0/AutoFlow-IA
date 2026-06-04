"""Workflow engine — Phase 4 (exécution simulée, aucune écriture externe en mode observation)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import (
    ExecutionStatus,
    Suggestion,
    SuggestionStatus,
    Workflow,
    WorkflowExecution,
    WorkflowStatus,
)
from app.services.audit import log_audit

logger = logging.getLogger(__name__)

EXTERNAL_WRITE_ACTIONS = {"draft_email", "send_email", "draft_quote", "create_folder"}


class WorkflowError(Exception):
    pass


async def create_workflow_from_suggestion(
    db: AsyncSession,
    org_id: UUID,
    suggestion_id: UUID,
    actor: str | None = None,
) -> Workflow | None:
    result = await db.execute(
        select(Suggestion).where(
            Suggestion.id == suggestion_id,
            Suggestion.organization_id == org_id,
            Suggestion.status == SuggestionStatus.APPROVED.value,
        )
    )
    sug = result.scalar_one_or_none()
    if not sug or not sug.workflow_draft:
        return None

    existing = (
        await db.execute(
            select(Workflow).where(Workflow.organization_id == org_id, Workflow.suggestion_id == suggestion_id)
        )
    ).scalar_one_or_none()
    if existing:  # idempotent : un double clic ne crée pas deux workflows
        return existing

    wf = Workflow(
        organization_id=org_id,
        suggestion_id=suggestion_id,
        name=sug.title,
        definition=sug.workflow_draft.get("structured", sug.workflow_draft),
        status=WorkflowStatus.APPROVED.value,
    )
    db.add(wf)
    await db.flush()
    await log_audit(db, org_id, "workflow_created", {"workflow_id": str(wf.id)}, actor=actor)
    return wf


async def execute_workflow(
    db: AsyncSession,
    org_id: UUID,
    workflow_id: UUID,
    *,
    actor: str | None = None,
) -> WorkflowExecution:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise WorkflowError("Workflow not found")
    if wf.kill_switch or wf.status == WorkflowStatus.PAUSED.value:
        raise WorkflowError("Workflow kill switch is active")

    execution = WorkflowExecution(
        workflow_id=workflow_id,
        organization_id=org_id,
        status=ExecutionStatus.PENDING.value,
        logs=[],
        triggered_by=actor or "user",
    )
    db.add(execution)
    await db.flush()
    await log_audit(db, org_id, "workflow_execution_started", {"execution_id": str(execution.id)}, actor=actor)

    if get_settings().workflow_executor == "celery":
        # Commit AVANT l'envoi : sinon le worker peut lire la base avant que
        # l'exécution n'y existe (condition de course).
        await db.commit()
        try:
            from app.tasks.workflow_tasks import run_workflow_execution

            run_workflow_execution.delay(str(execution.id))
            return execution
        except Exception:
            logger.exception("Celery dispatch failed, running workflow locally")

    await run_steps(db, execution, wf)
    await db.flush()
    return execution


async def run_steps(db: AsyncSession, execution: WorkflowExecution, wf: Workflow) -> None:
    """Exécution simulée des actions. Respecte le kill switch et le mode observation."""
    settings = get_settings()
    logs: list[dict] = []
    execution.status = ExecutionStatus.RUNNING.value
    execution.started_at = datetime.now(timezone.utc)

    if wf.kill_switch:
        execution.status = ExecutionStatus.FAILED.value
        execution.logs = [{"step": 0, "action": None, "status": "aborted", "note": "Kill switch actif"}]
        execution.finished_at = datetime.now(timezone.utc)
        return

    for i, action in enumerate((wf.definition or {}).get("actions", [])):
        a_type = action.get("type") if isinstance(action, dict) else None
        entry = {"step": i, "action": a_type, "status": "simulated", "observation_only": settings.observation_only}
        if settings.observation_only and a_type in EXTERNAL_WRITE_ACTIONS:
            entry["status"] = "skipped"
            entry["note"] = "Ignoré — mode observation (Phases 1-3)"
        logs.append(entry)

    execution.logs = logs
    execution.status = ExecutionStatus.SUCCESS.value
    execution.finished_at = datetime.now(timezone.utc)
    if wf.status == WorkflowStatus.APPROVED.value:
        wf.status = WorkflowStatus.ACTIVE.value


async def toggle_kill_switch(
    db: AsyncSession,
    org_id: UUID,
    workflow_id: UUID,
    enabled: bool,
    actor: str | None = None,
) -> Workflow | None:
    result = await db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org_id)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        return None
    wf.kill_switch = enabled
    if enabled:
        wf.status = WorkflowStatus.PAUSED.value
    elif wf.status == WorkflowStatus.PAUSED.value:
        wf.status = WorkflowStatus.APPROVED.value
    await log_audit(
        db, org_id, "workflow_kill_switch", {"workflow_id": str(workflow_id), "enabled": enabled}, actor=actor
    )
    return wf
