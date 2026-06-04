"""Predictive intelligence — Phase 6.

Scores heuristiques transparents, calculés à partir des emails observés.
Chaque prédiction expose les variables utilisées (`features`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ClassifiedEvent, Prediction, RawEvent
from app.services.llm import chat_completion, llm_enabled

LOOKBACK_DAYS = 90
MAX_EVENTS = 1000


async def generate_predictions(db: AsyncSession, org_id: UUID) -> list[Prediction]:
    await db.execute(delete(Prediction).where(Prediction.organization_id == org_id))

    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    rows = (
        await db.execute(
            select(RawEvent.sender, RawEvent.thread_id, ClassifiedEvent.category)
            .join(ClassifiedEvent, ClassifiedEvent.raw_event_id == RawEvent.id)
            .where(RawEvent.organization_id == org_id, RawEvent.occurred_at >= since)
            .order_by(RawEvent.occurred_at.desc())
            .limit(MAX_EVENTS)
        )
    ).all()

    relance_senders: dict[str, int] = {}
    devis_threads: dict[str, int] = {}
    counts: dict[str, int] = {}
    for sender, thread_id, category in rows:
        counts[category] = counts.get(category, 0) + 1
        if category == "relances" and sender:
            relance_senders[sender] = relance_senders.get(sender, 0) + 1
        if category == "devis" and thread_id:
            devis_threads[thread_id] = devis_threads.get(thread_id, 0) + 1

    predictions: list[Prediction] = []

    for sender, count in sorted(relance_senders.items(), key=lambda x: -x[1])[:3]:
        score = round(min(0.95, 0.4 + count * 0.12), 2)
        explanation = (
            f"{count} relance(s) liée(s) à {sender} sur {LOOKBACK_DAYS} jours — "
            f"risque estimé de retard de paiement : {score:.0%}."
        )
        predictions.append(
            Prediction(
                organization_id=org_id,
                prediction_type="payment_delay_risk",
                entity_ref=sender,
                score=score,
                explanation=await _maybe_enrich(explanation, "payment_delay_risk"),
                features={"relance_count": count, "lookback_days": LOOKBACK_DAYS},
            )
        )

    if devis_threads:
        avg_msgs = sum(devis_threads.values()) / len(devis_threads)
        score = round(min(0.9, 0.3 + (avg_msgs - 1) * 0.2), 2)
        expected_exchanges = max(1, round(avg_msgs))
        predictions.append(
            Prediction(
                organization_id=org_id,
                prediction_type="validation_steps",
                entity_ref="pipeline_devis",
                score=max(score, 0.1),
                explanation=(
                    f"Une demande de devis donne en moyenne lieu à {avg_msgs:.1f} échange(s) "
                    f"({len(devis_threads)} fil(s) analysé(s)) : prévoir ~{expected_exchanges} "
                    "aller-retour avant validation."
                ),
                features={"devis_threads": len(devis_threads), "avg_messages_per_thread": round(avg_msgs, 2)},
            )
        )

    devis, support = counts.get("devis", 0), counts.get("support", 0)
    if devis + support > 0:
        closing = round(devis / (devis + support), 2)
        predictions.append(
            Prediction(
                organization_id=org_id,
                prediction_type="commercial_closing",
                entity_ref="pipeline_global",
                score=closing,
                explanation=(
                    f"Indicateur d'activité commerciale : {devis} demande(s) de devis pour "
                    f"{support} question(s) support ({closing:.0%}). Heuristique, non calibrée "
                    "sur des signatures réelles."
                ),
                features={"devis": devis, "support": support},
            )
        )

    for p in predictions:
        db.add(p)
    await db.flush()
    return predictions


async def _maybe_enrich(base: str, prediction_type: str) -> str:
    if not llm_enabled():
        return base
    text = await chat_completion(
        [
            {
                "role": "user",
                "content": (
                    "Reformule en 2 phrases françaises claires et transparentes, sans inventer "
                    f"de chiffres : {base} (type={prediction_type})"
                ),
            }
        ],
        max_tokens=120,
    )
    return text or base
