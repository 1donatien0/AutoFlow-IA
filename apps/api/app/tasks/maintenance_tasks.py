"""Tâches de maintenance (RGPD : rétention des données)."""

from __future__ import annotations

from app.tasks.celery_app import celery_app
from app.tasks.workflow_tasks import run_with_session


async def _purge(db) -> int:
    from app.config import get_settings
    from app.services.data_governance import purge_expired_events

    return await purge_expired_events(db, get_settings().data_retention_days)


@celery_app.task(name="purge_expired_events")
def purge_expired_events_task() -> dict:
    return {"deleted_events": run_with_session(_purge)}
