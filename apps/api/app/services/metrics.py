"""Dashboard metrics aggregation — Phase 1 observation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ClassifiedEvent, MetricsSnapshot, RawEvent
from app.schemas.common import DashboardMetrics, InsightItem

# Vertical compta : minutes estimées par catégorie / occurrence
MINUTES_PER_CATEGORY = {
    "devis": 25,
    "support": 12,
    "facturation": 18,
    "rendez_vous": 10,
    "relances": 15,
    "autre": 8,
}
DEFAULT_MINUTES = 10
REPETITIVE_THRESHOLD = 5  # occurrences / 30 j à partir desquelles une catégorie est « répétitive »
PERIOD_DAYS = 30
SNAPSHOT_MIN_INTERVAL = timedelta(hours=1)
WEEKS_PER_MONTH = 4.3


def estimate_hours(category: str, count: int) -> float:
    return count * MINUTES_PER_CATEGORY.get(category, DEFAULT_MINUTES) / 60


async def category_breakdown(db: AsyncSession, org_id: UUID, since: datetime) -> dict[str, int]:
    """Nombre d'emails par catégorie, selon la date réelle de l'email (et non d'ingestion)."""
    query = (
        select(ClassifiedEvent.category, func.count())
        .join(RawEvent, RawEvent.id == ClassifiedEvent.raw_event_id)
        .where(ClassifiedEvent.organization_id == org_id, RawEvent.occurred_at >= since)
        .group_by(ClassifiedEvent.category)
    )
    return {row[0]: row[1] for row in (await db.execute(query)).all()}


async def compute_dashboard(db: AsyncSession, org_id: UUID) -> DashboardMetrics:
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=PERIOD_DAYS)

    breakdown = await category_breakdown(db, org_id, period_start)
    hours_lost = sum(estimate_hours(cat, n) for cat, n in breakdown.items())
    repetitive = sum(1 for c in breakdown.values() if c >= REPETITIVE_THRESHOLD)
    automation_score = min(100.0, hours_lost * 2 + repetitive * 5)

    metrics = DashboardMetrics(
        period_start=period_start,
        period_end=now,
        hours_lost_estimate=round(hours_lost, 1),
        repetitive_tasks_count=repetitive,
        automation_potential_score=round(automation_score, 1),
        category_breakdown=breakdown,
        insights=_build_insights(breakdown),
    )
    await _maybe_snapshot(db, org_id, metrics)
    return metrics


async def _maybe_snapshot(db: AsyncSession, org_id: UUID, m: DashboardMetrics) -> None:
    """Historise au plus un snapshot par heure (évite une écriture à chaque affichage)."""
    last = (
        await db.execute(
            select(MetricsSnapshot.created_at)
            .where(MetricsSnapshot.organization_id == org_id)
            .order_by(MetricsSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last is not None:
        last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - last_aware < SNAPSHOT_MIN_INTERVAL:
            return
    db.add(
        MetricsSnapshot(
            organization_id=org_id,
            period_start=m.period_start,
            period_end=m.period_end,
            metrics={
                "hours_lost_estimate": m.hours_lost_estimate,
                "repetitive_tasks_count": m.repetitive_tasks_count,
                "automation_potential_score": m.automation_potential_score,
                "category_breakdown": m.category_breakdown,
            },
        )
    )


def _build_insights(breakdown: dict[str, int]) -> list[InsightItem]:
    insights: list[InsightItem] = []
    devis = breakdown.get("devis", 0)
    if devis:
        insights.append(
            InsightItem(
                label="Devis",
                value=f"~{round(devis / WEEKS_PER_MONTH, 1)} devis/semaine",
                detail="Basé sur les emails classés « devis » sur 30 jours",
            )
        )
    support = breakdown.get("support", 0)
    if support:
        insights.append(
            InsightItem(
                label="Support",
                value=f"~{support} questions clients/mois",
                detail="Réponses répétitives potentielles",
            )
        )
    relances = breakdown.get("relances", 0)
    if relances:
        insights.append(
            InsightItem(
                label="Relances",
                value=f"~{round(estimate_hours('relances', relances), 1)} h/mois en relances",
                detail="Factures et documents manquants",
            )
        )
    if not insights:
        insights.append(
            InsightItem(
                label="Observation",
                value="Connectez Gmail et synchronisez",
                detail="Aucune donnée classifiée pour le moment",
            )
        )
    return insights


async def seed_demo_events(db: AsyncSession, org_id: UUID) -> int:
    """Seed demo emails for cabinet comptable vertical."""
    from app.services.ingestion import ingest_email_batch

    demos = [
        ("Demande de devis comptabilité", "Bonjour, pourriez-vous nous envoyer un devis pour la tenue ?", "client1@example.com"),
        ("Relance facture #1042", "Sauf erreur, la facture 1042 reste impayée.", "compta@cabinet.example"),
        ("Où en est ma déclaration TVA ?", "Pouvez-vous me donner le statut de ma déclaration ?", "client2@example.com"),
        ("RDV bilan annuel", "Proposition de créneau pour le bilan annuel.", "compta@cabinet.example"),
        ("Facture prestation mars", "Veuillez trouver ci-joint la facture mars.", "compta@cabinet.example"),
        ("Documents manquants dossier Martin", "Relance : il manque les relevés bancaires Q1.", "compta@cabinet.example"),
        ("Demande lettre de mission", "Merci de nous transmettre une proposition / devis.", "client3@example.com"),
        ("Question URSSAF", "Comment déclarer les indemnités ?", "client4@example.com"),
    ]
    now = datetime.now(timezone.utc)
    batch = [
        {
            "external_id": f"demo-{i}",
            "thread_id": f"thread-{i % 3}",
            "subject": subject,
            "body_preview": body,
            "sender": sender,
            "occurred_at": (now - timedelta(days=i * 2)).isoformat(),
        }
        for i, (subject, body, sender) in enumerate(demos)
    ]
    for j in range(3):
        batch.append(
            {
                "external_id": f"demo-extra-{j}",
                "thread_id": "thread-relance",
                "subject": "Relance facture impayée",
                "body_preview": "Deuxième relance pour facture 998.",
                "sender": "compta@cabinet.example",
                "occurred_at": (now - timedelta(hours=j * 6)).isoformat(),
            }
        )
    return await ingest_email_batch(db, org_id, "demo", batch)
