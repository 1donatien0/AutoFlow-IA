"""Celery tasks for workflow execution — Phase 4."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from app.tasks.celery_app import celery_app

T = TypeVar("T")


def run_with_session(fn: Callable[..., Awaitable[T]], *args) -> T:
    """Exécute une coroutine avec une session dédiée (moteur créé puis libéré à chaque tâche)."""

    async def _runner() -> T:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from app.config import get_settings
        from app.database import make_engine

        engine = make_engine(get_settings().database_url)
        try:
            maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with maker() as db:
                try:
                    out = await fn(db, *args)
                    await db.commit()
                    return out
                except Exception:
                    await db.rollback()
                    raise
        finally:
            await engine.dispose()

    return asyncio.run(_runner())


async def _execute(db, execution_id: str) -> dict:
    from sqlalchemy import select

    from app.models.entities import Workflow, WorkflowExecution
    from app.services.workflows import run_steps

    execution = (
        await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == UUID(execution_id)))
    ).scalar_one_or_none()
    if not execution:
        return {"error": "not_found"}
    wf = (await db.execute(select(Workflow).where(Workflow.id == execution.workflow_id))).scalar_one()
    await run_steps(db, execution, wf)
    return {"execution_id": execution_id, "status": execution.status}


@celery_app.task(name="run_workflow_execution")
def run_workflow_execution(execution_id: str) -> dict:
    return run_with_session(_execute, execution_id)
