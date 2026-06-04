"""Email ingestion — read-only observation."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ClassifiedEvent, RawEvent
from app.services.classification import classify_text

MAX_SUBJECT = 1024
MAX_PREVIEW = 2000
MAX_SENDER = 512


def parse_occurred_at(value) -> datetime:
    """Accepte ISO 8601, epoch (s ou ms, int ou str) ou datetime ; défaut = maintenant (UTC)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        ts = float(value)
        if ts > 1e11:  # millisecondes (ex. Gmail internalDate)
            ts /= 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _trunc(value, limit: int) -> str | None:
    if value is None:
        return None
    return str(value)[:limit]


async def ingest_email_batch(
    db: AsyncSession,
    org_id: UUID,
    source: str,
    messages: list[dict],
) -> int:
    ids = [m.get("external_id") for m in messages if m.get("external_id")]
    existing_ids: set[str] = set()
    if ids:
        rows = await db.execute(
            select(RawEvent.external_id).where(
                RawEvent.organization_id == org_id,
                RawEvent.source == source,
                RawEvent.external_id.in_(ids),
            )
        )
        existing_ids = {r[0] for r in rows}

    count = 0
    for msg in messages:
        external_id = _trunc(msg.get("external_id"), 512)
        if external_id:
            if external_id in existing_ids:
                continue
            existing_ids.add(external_id)  # dédoublonnage intra-lot

        thread_id = _trunc(msg.get("thread_id"), 512)
        subject = _trunc(msg.get("subject"), MAX_SUBJECT)
        preview = _trunc(msg.get("body_preview"), MAX_PREVIEW)
        sender = _trunc(msg.get("sender"), MAX_SENDER)

        raw = RawEvent(
            organization_id=org_id,
            source=source,
            external_id=external_id,
            thread_id=thread_id,
            case_id=thread_id or external_id,
            subject=subject,
            body_preview=preview,
            sender=sender,
            event_type="email",
            # Minimisation RGPD : on ne conserve que les métadonnées utiles
            payload={"labels": msg.get("labels")} if msg.get("labels") else None,
            occurred_at=parse_occurred_at(msg.get("occurred_at")),
        )
        db.add(raw)
        await db.flush()

        category, confidence, classifier = await classify_text(subject or "", preview or "")
        db.add(
            ClassifiedEvent(
                organization_id=org_id,
                raw_event_id=raw.id,
                category=category,
                confidence=confidence,
                classifier=classifier,
            )
        )
        count += 1

    await db.flush()
    return count
