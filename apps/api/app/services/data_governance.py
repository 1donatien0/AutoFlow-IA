"""RGPD : export, effacement et rétention des données d'une organisation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    AgentRun,
    AuditLog,
    ClassifiedEvent,
    DiscoveredProcess,
    Integration,
    MetricsSnapshot,
    Organization,
    Prediction,
    ProcessInstance,
    RawEvent,
    Suggestion,
    User,
    Workflow,
    WorkflowExecution,
)
from app.services.audit import log_audit

# Ordre de suppression respectant les clés étrangères
_OBSERVED_DATA = [
    ClassifiedEvent,
    RawEvent,
    ProcessInstance,
    DiscoveredProcess,
    Prediction,
    MetricsSnapshot,
]
_ALL_DATA = [
    WorkflowExecution,
    Workflow,
    Suggestion,
    AgentRun,
    *_OBSERVED_DATA,
    Integration,
]


def _row(obj, exclude: set[str] | None = None) -> dict:
    exclude = exclude or set()
    out = {}
    for col in obj.__table__.columns:
        if col.key in exclude:
            continue
        val = getattr(obj, col.key)
        out[col.key] = val.isoformat() if isinstance(val, datetime) else (str(val) if isinstance(val, UUID) else val)
    return out


async def export_organization(db: AsyncSession, org_id: UUID) -> dict:
    """Droit d'accès / portabilité (art. 15 & 20). Les jetons OAuth ne sont jamais exportés."""
    org = await db.get(Organization, org_id)
    data: dict = {"organization": _row(org) if org else None, "exported_at": datetime.now(timezone.utc).isoformat()}
    sensitive = {"hashed_password", "credentials_encrypted"}
    for model in [User, Integration, RawEvent, ClassifiedEvent, DiscoveredProcess, ProcessInstance,
                  Suggestion, Workflow, WorkflowExecution, AgentRun, Prediction, MetricsSnapshot, AuditLog]:
        rows = (await db.execute(select(model).where(model.organization_id == org_id))).scalars().all()
        data[model.__tablename__] = [_row(r, sensitive) for r in rows]
    return data


async def purge_organization_data(db: AsyncSession, org_id: UUID, actor: str | None = None) -> dict[str, int]:
    """Droit à l'effacement (art. 17) : supprime toutes les données métier, conserve le compte
    et le journal d'audit (preuve de la suppression)."""
    counts: dict[str, int] = {}
    for model in _ALL_DATA:
        res = await db.execute(delete(model).where(model.organization_id == org_id))
        counts[model.__tablename__] = res.rowcount or 0
    await log_audit(db, org_id, "organization_data_purged", counts, actor=actor)
    return counts


async def purge_expired_events(db: AsyncSession, retention_days: int) -> int:
    """Rétention (toutes organisations) : supprime les emails observés plus anciens que
    `retention_days`, ainsi que les données qui en sont dérivées et peuvent contenir des
    données personnelles (adresses d'expéditeurs dans les prédictions, extraits dans les
    fils de processus, texte des demandes aux agents, instantanés de métriques).

    Retourne le nombre d'emails supprimés.
    """
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    old_ids = select(RawEvent.id).where(RawEvent.occurred_at < cutoff)
    await db.execute(delete(ClassifiedEvent).where(ClassifiedEvent.raw_event_id.in_(old_ids)))
    res = await db.execute(delete(RawEvent).where(RawEvent.occurred_at < cutoff))
    # Dérivés : un fil dont le dernier email a expiré n'a plus de source
    await db.execute(delete(ProcessInstance).where(ProcessInstance.completed_at < cutoff))
    for model in (Prediction, AgentRun, MetricsSnapshot):
        await db.execute(delete(model).where(model.created_at < cutoff))
    return res.rowcount or 0
