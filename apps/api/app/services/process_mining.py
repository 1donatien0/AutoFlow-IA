"""Process discovery from event traces — Phase 2."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import ClassifiedEvent, DiscoveredProcess, ProcessInstance, RawEvent

STEP_LABELS = {
    "devis": "Email_demande",
    "support": "Email_question",
    "facturation": "Facturation",
    "rendez_vous": "Planification",
    "relances": "Relance",
    "autre": "Email_generique",
}
# Libellés lisibles pour nommer les processus (le nom doit être stable d'une
# découverte à l'autre : il sert de titre aux suggestions associées).
STEP_NAMES = {
    "Email_demande": "Demande de devis",
    "Email_question": "Question client",
    "Facturation": "Facturation",
    "Planification": "Rendez-vous",
    "Relance": "Relance",
    "Email_generique": "Échange",
}
SEP = " → "
MAX_PROCESSES = 10
MAX_INSTANCES_PER_PROCESS = 20
MIN_DURATION_MINUTES = 5


def process_name(steps: list[str]) -> str:
    """Nom lisible et déterministe : étapes consécutives identiques regroupées (« Relance ×3 »)."""
    parts: list[str] = []
    prev, run = None, 0
    for step in [*steps, None]:
        if step == prev:
            run += 1
            continue
        if prev is not None:
            label = STEP_NAMES.get(prev, prev)
            parts.append(f"{label} ×{run}" if run > 1 else label)
        prev, run = step, 1
    return SEP.join(parts)[:255]


async def discover_processes(db: AsyncSession, org_id: UUID) -> list[DiscoveredProcess]:
    """Mine frequent step sequences per case_id (thread/dossier)."""
    query = (
        select(RawEvent.case_id, RawEvent.occurred_at, RawEvent.id, ClassifiedEvent.category)
        .join(ClassifiedEvent, ClassifiedEvent.raw_event_id == RawEvent.id)
        .where(RawEvent.organization_id == org_id, RawEvent.case_id.is_not(None))
        .order_by(RawEvent.case_id, RawEvent.occurred_at)
    )
    cases: dict[str, list[tuple[datetime, str, UUID]]] = defaultdict(list)
    for case_id, occurred_at, raw_id, category in (await db.execute(query)).all():
        cases[case_id].append((occurred_at, STEP_LABELS.get(category, "Email_generique"), raw_id))

    sequence_counts: dict[str, int] = defaultdict(int)
    sequence_durations: dict[str, list[float]] = defaultdict(list)
    case_sequences: dict[str, str] = {}
    case_timelines: dict[str, list[dict]] = {}

    for case_id, events in cases.items():
        if len(events) < 2:
            continue
        events.sort(key=lambda x: x[0])
        key = SEP.join(e[1] for e in events)
        sequence_counts[key] += 1
        duration = (events[-1][0] - events[0][0]).total_seconds() / 60
        sequence_durations[key].append(max(duration, MIN_DURATION_MINUTES))
        case_sequences[case_id] = key
        case_timelines[case_id] = [
            {"at": e[0].isoformat(), "step": e[1], "event_id": str(e[2])} for e in events
        ]

    # Suppression dans l'ordre des dépendances (instances → processus)
    await db.execute(delete(ProcessInstance).where(ProcessInstance.organization_id == org_id))
    await db.execute(delete(DiscoveredProcess).where(DiscoveredProcess.organization_id == org_id))

    discovered: list[DiscoveredProcess] = []
    process_by_seq: dict[str, DiscoveredProcess] = {}
    for seq, freq in sorted(sequence_counts.items(), key=lambda x: -x[1])[:MAX_PROCESSES]:
        steps = seq.split(SEP)
        durations = sequence_durations[seq]
        proc = DiscoveredProcess(
            organization_id=org_id,
            name=process_name(steps),
            trigger_label=steps[0],
            steps=steps,
            frequency=freq,
            avg_duration_minutes=round(sum(durations) / len(durations), 1),
        )
        db.add(proc)
        discovered.append(proc)
        process_by_seq[seq] = proc
    await db.flush()

    per_process: dict[UUID, int] = defaultdict(int)
    for case_id, seq in case_sequences.items():
        proc = process_by_seq.get(seq)
        if proc is None or per_process[proc.id] >= MAX_INSTANCES_PER_PROCESS:
            continue
        per_process[proc.id] += 1
        timeline = case_timelines[case_id]
        events = cases[case_id]
        started, completed = events[0][0], events[-1][0]
        db.add(
            ProcessInstance(
                organization_id=org_id,
                process_id=proc.id,
                case_id=case_id,
                timeline=timeline,
                duration_minutes=round(max((completed - started).total_seconds() / 60, MIN_DURATION_MINUTES), 1),
                started_at=started,
                completed_at=completed,
            )
        )
    await db.flush()
    return discovered
