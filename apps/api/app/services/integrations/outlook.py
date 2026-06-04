"""Microsoft Outlook OAuth — read-only (Microsoft Graph, Mail.Read)."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import Integration, IntegrationProvider, IntegrationStatus
from app.services.ingestion import ingest_email_batch
from app.services.integrations.common import (
    IntegrationError,
    get_integration,
    mark_synced,
    read_credentials,
    store_credentials,
    upsert_connected_integration,
)

logger = logging.getLogger(__name__)

OUTLOOK_SCOPES = ["https://graph.microsoft.com/Mail.Read"]
PROVIDER = IntegrationProvider.OUTLOOK.value
GRAPH_MESSAGES_URL = "https://graph.microsoft.com/v1.0/me/messages"


def outlook_configured() -> bool:
    s = get_settings()
    return bool(s.microsoft_client_id and s.microsoft_client_secret)


def _msal_app(cache=None):
    import msal

    s = get_settings()
    return msal.ConfidentialClientApplication(
        s.microsoft_client_id,
        authority=f"https://login.microsoftonline.com/{s.microsoft_tenant_id}",
        client_credential=s.microsoft_client_secret,
        token_cache=cache,
    )


def get_outlook_auth_url(state: str) -> str:
    settings = get_settings()
    if not outlook_configured():
        if not settings.demo_mode:
            raise IntegrationError("Outlook OAuth is not configured")
        return f"{settings.api_public_url}/api/v1/integrations/outlook/demo-connect?{urlencode({'state': state})}"
    # MSAL encode correctement les paramètres et ajoute offline_access
    return _msal_app().get_authorization_request_url(
        OUTLOOK_SCOPES, state=state, redirect_uri=settings.microsoft_redirect_uri
    )


def _exchange_code(code: str) -> str:
    import msal

    cache = msal.SerializableTokenCache()
    result = _msal_app(cache).acquire_token_by_authorization_code(
        code, scopes=OUTLOOK_SCOPES, redirect_uri=get_settings().microsoft_redirect_uri
    )
    if "access_token" not in result:
        raise RuntimeError(result.get("error", "token exchange failed"))
    return cache.serialize()


async def handle_outlook_callback(db: AsyncSession, org_id: UUID, code: str) -> Integration:
    try:
        cache_blob = await asyncio.to_thread(_exchange_code, code)
    except Exception as exc:
        logger.exception("Outlook token exchange failed")
        raise IntegrationError("Outlook authorization failed") from exc
    return await upsert_connected_integration(db, org_id, PROVIDER, OUTLOOK_SCOPES, cache_blob)


async def connect_outlook_demo(db: AsyncSession, org_id: UUID) -> Integration:
    return await upsert_connected_integration(db, org_id, PROVIDER, OUTLOOK_SCOPES, None, {"demo": True})


def _acquire_token(cache_blob: str) -> tuple[str, str]:
    import msal

    cache = msal.SerializableTokenCache()
    cache.deserialize(cache_blob)
    app = _msal_app(cache)
    accounts = app.get_accounts()
    if not accounts:
        raise RuntimeError("no cached account")
    result = app.acquire_token_silent(OUTLOOK_SCOPES, account=accounts[0])
    if not result or "access_token" not in result:
        raise RuntimeError("silent token acquisition failed")
    return result["access_token"], cache.serialize()


async def sync_outlook_messages(db: AsyncSession, org_id: UUID, max_results: int = 50) -> int:
    integration = await get_integration(db, org_id, PROVIDER)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise IntegrationError("Outlook is not connected")
    cache_blob = read_credentials(integration)
    if not cache_blob:
        raise IntegrationError("Outlook is connected in demo mode only — use demo data")
    if not outlook_configured():
        raise IntegrationError("Outlook OAuth is not configured")

    try:
        token, new_cache = await asyncio.to_thread(_acquire_token, cache_blob)
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                GRAPH_MESSAGES_URL,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "$top": str(max_results),
                    "$select": "id,conversationId,subject,bodyPreview,from,receivedDateTime",
                    "$orderby": "receivedDateTime desc",
                },
            )
            resp.raise_for_status()
            items = resp.json().get("value", [])
    except Exception as exc:
        logger.exception("Outlook sync failed for org %s", org_id)
        integration.status = IntegrationStatus.ERROR.value
        raise IntegrationError("Outlook sync failed") from exc

    store_credentials(integration, new_cache)
    messages = [
        {
            "external_id": it.get("id"),
            "thread_id": it.get("conversationId"),
            "subject": it.get("subject") or "",
            "body_preview": it.get("bodyPreview") or "",
            "sender": ((it.get("from") or {}).get("emailAddress") or {}).get("address", ""),
            "occurred_at": it.get("receivedDateTime"),
        }
        for it in items
    ]
    count = await ingest_email_batch(db, org_id, PROVIDER, messages)
    mark_synced(integration)
    return count
