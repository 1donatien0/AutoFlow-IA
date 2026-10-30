"""Helpers partagés par les intégrations email (stockage chiffré des jetons)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Integration, IntegrationStatus
from app.security import decrypt_secret, encrypt_secret

# Une intégration en erreur (jeton expiré, panne fournisseur…) peut être resynchronisée :
# un succès la repasse en « connected ».
SYNCABLE_STATUSES = frozenset({IntegrationStatus.CONNECTED.value, IntegrationStatus.ERROR.value})


class IntegrationError(Exception):
    """Erreur côté fournisseur (OAuth / API) présentable à l'utilisateur."""


async def get_integration(db: AsyncSession, org_id: UUID, provider: str) -> Integration | None:
    result = await db.execute(
        select(Integration).where(Integration.organization_id == org_id, Integration.provider == provider)
    )
    return result.scalar_one_or_none()


async def upsert_connected_integration(
    db: AsyncSession,
    org_id: UUID,
    provider: str,
    scopes: list[str],
    credentials: str | None,
    metadata: dict | None = None,
) -> Integration:
    integration = await get_integration(db, org_id, provider)
    if not integration:
        integration = Integration(organization_id=org_id, provider=provider)
        db.add(integration)
    integration.scopes = " ".join(scopes)
    integration.status = IntegrationStatus.CONNECTED.value
    integration.credentials_encrypted = encrypt_secret(credentials) if credentials else None
    integration.metadata_json = metadata
    await db.flush()
    return integration


def read_credentials(integration: Integration) -> str | None:
    if not integration.credentials_encrypted:
        return None
    return decrypt_secret(integration.credentials_encrypted)


def store_credentials(integration: Integration, credentials: str) -> None:
    integration.credentials_encrypted = encrypt_secret(credentials)


def mark_synced(integration: Integration) -> None:
    integration.last_sync_at = datetime.now(timezone.utc)
    integration.status = IntegrationStatus.CONNECTED.value
