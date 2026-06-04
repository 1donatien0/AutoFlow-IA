"""Suggestions d'automatisation — Phase 3.

Toutes les valeurs affichées (fréquence, gain estimé) sont calculées à partir des
emails réellement observés : aucune donnée « de vitrine » n'est injectée.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import DiscoveredProcess, Suggestion, SuggestionStatus, Workflow
from app.services.audit import log_audit
from app.services.metrics import PERIOD_DAYS, category_breakdown, estimate_hours

MIN_RELANCES = 3
MIN_DEVIS = 2
# Part du temps qu'on estime récupérable par l'automatisation (brouillon + validation humaine)
AUTOMATABLE_SHARE = 0.6


def _roi_score(hours_saved: float) -> float:
    """Score 0-100 croissant avec les heures économisées (saturation à ~20 h/mois)."""
    return round(min(100.0, 30 + hours_saved * 3.5), 1)


async def generate_suggestions(db: AsyncSession, org_id: UUID) -> list[Suggestion]:
    """Analyse les emails des 30 derniers jours et les processus découverts."""
    since = datetime.now(timezone.utc) - timedelta(days=PERIOD_DAYS)
    breakdown = await category_breakdown(db, org_id, since)

    processes = (
        await db.execute(
            select(DiscoveredProcess)
            .where(DiscoveredProcess.organization_id == org_id)
            .order_by(DiscoveredProcess.frequency.desc())
        )
    ).scalars().all()

    # On ne régénère que les brouillons/rejets non référencés : une suggestion
    # approuvée (ou liée à un workflow) fait partie de l'historique de décision.
    referenced = select(Workflow.suggestion_id).where(Workflow.suggestion_id.is_not(None))
    stale = (
        await db.execute(
            select(Suggestion).where(
                Suggestion.organization_id == org_id,
                Suggestion.status != SuggestionStatus.APPROVED.value,
                Suggestion.id.not_in(referenced),
            )
        )
    ).scalars().all()
    for s in stale:
        await db.delete(s)
    await db.flush()

    kept_titles = set(
        (
            await db.execute(select(Suggestion.title).where(Suggestion.organization_id == org_id))
        ).scalars().all()
    )

    candidates: list[Suggestion] = []

    relances = breakdown.get("relances", 0)
    if relances >= MIN_RELANCES:
        saved = round(estimate_hours("relances", relances) * AUTOMATABLE_SHARE, 1)
        candidates.append(
            Suggestion(
                organization_id=org_id,
                title="Automatiser les relances factures",
                description=(
                    f"{relances} emails de relance observés sur {PERIOD_DAYS} jours. "
                    f"Gain estimé : {saved} h/mois."
                ),
                monthly_frequency=relances,
                estimated_hours_saved=saved,
                workflow_draft={
                    "readable": (
                        'SI email contient "relance" OU "impayé"\n'
                        "ALORS classifier dossier → proposer brouillon relance → validation humaine"
                    ),
                    "structured": {
                        "trigger": {"type": "email_contains", "values": ["relance", "impayé"]},
                        "actions": [
                            {"type": "tag_case", "label": "relance_facture"},
                            {"type": "draft_email", "template": "relance_facture_v1"},
                            {"type": "await_approval"},
                        ],
                    },
                },
                status=SuggestionStatus.DRAFT.value,
                roi_score=_roi_score(saved),
                risk_notes="Conformité : validation humaine obligatoire avant envoi (Phase 4+).",
            )
        )

    devis = breakdown.get("devis", 0)
    if devis >= MIN_DEVIS:
        saved = round(estimate_hours("devis", devis) * AUTOMATABLE_SHARE, 1)
        candidates.append(
            Suggestion(
                organization_id=org_id,
                title="Accélérer les demandes de devis",
                description=(
                    f"{devis} demandes de devis observées sur {PERIOD_DAYS} jours. "
                    "Création dossier + brouillon automatisable."
                ),
                monthly_frequency=devis,
                estimated_hours_saved=saved,
                workflow_draft={
                    "readable": (
                        'SI email contient "demande devis" OU "lettre de mission"\n'
                        "ALORS créer dossier → générer brouillon devis → envoyer validation"
                    ),
                    "structured": {
                        "trigger": {"type": "email_contains", "values": ["devis", "lettre de mission"]},
                        "actions": [
                            {"type": "create_folder"},
                            {"type": "draft_quote"},
                            {"type": "notify_validator"},
                        ],
                    },
                },
                status=SuggestionStatus.DRAFT.value,
                roi_score=_roi_score(saved),
                risk_notes="Vérifier mentions légales cabinet avant envoi automatique.",
            )
        )

    if processes:
        proc = processes[0]
        saved = round(proc.frequency * proc.avg_duration_minutes / 60 * AUTOMATABLE_SHARE, 1)
        candidates.append(
            Suggestion(
                organization_id=org_id,
                title=f"Optimiser : {proc.name}",
                description=(
                    f"Processus découvert ({proc.frequency} occurrences, "
                    f"{proc.avg_duration_minutes} min de bout en bout en moyenne)."
                ),
                monthly_frequency=proc.frequency,
                estimated_hours_saved=saved,
                workflow_draft={
                    "readable": " → ".join(proc.steps),
                    "structured": {
                        "steps": proc.steps,
                        "process_id": str(proc.id),
                        "actions": [{"type": "notify_validator"}],
                    },
                },
                status=SuggestionStatus.DRAFT.value,
                roi_score=_roi_score(saved),
                risk_notes="Durée mesurée entre le premier et le dernier email du fil (inclut l'attente).",
            )
        )

    created = [s for s in candidates if s.title not in kept_titles]
    for s in created:
        db.add(s)
    await db.flush()
    await log_audit(db, org_id, "suggestions_generated", {"count": len(created)})

    return list(
        (
            await db.execute(
                select(Suggestion)
                .where(Suggestion.organization_id == org_id)
                .order_by(Suggestion.roi_score.desc())
            )
        ).scalars().all()
    )


async def update_suggestion_status(
    db: AsyncSession,
    org_id: UUID,
    suggestion_id: UUID,
    status: str,
    actor: str | None = None,
) -> Suggestion | None:
    result = await db.execute(
        select(Suggestion).where(Suggestion.id == suggestion_id, Suggestion.organization_id == org_id)
    )
    sug = result.scalar_one_or_none()
    if not sug:
        return None
    sug.status = status
    await log_audit(
        db, org_id, "suggestion_status_changed", {"id": str(suggestion_id), "status": status}, actor=actor
    )
    return sug
