"""Gmail OAuth — read-only scopes for observation."""

from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urlencode
from uuid import UUID

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

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
PROVIDER = IntegrationProvider.GMAIL.value


def gmail_configured() -> bool:
    s = get_settings()
    return bool(s.google_client_id and s.google_client_secret)


def _flow(state: str | None = None):
    from google_auth_oauthlib.flow import Flow

    settings = get_settings()
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.google_redirect_uri],
            }
        },
        scopes=GMAIL_SCOPES,
        state=state,
        # Client confidentiel (secret côté serveur) : pas de PKCE, sinon le
        # code_verifier généré ici serait perdu avant le callback.
        autogenerate_code_verifier=False,
    )
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def get_gmail_auth_url(state: str) -> str:
    settings = get_settings()
    if not gmail_configured():
        if not settings.demo_mode:
            raise IntegrationError("Gmail OAuth is not configured")
        return f"{settings.api_public_url}/api/v1/integrations/gmail/demo-connect?{urlencode({'state': state})}"

    auth_url, _ = _flow(state).authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return auth_url


def _exchange_code(code: str) -> str:
    flow = _flow()
    flow.fetch_token(code=code)
    return flow.credentials.to_json()


async def handle_gmail_callback(db: AsyncSession, org_id: UUID, code: str) -> Integration:
    """Échange le code d'autorisation contre des jetons et les stocke chiffrés."""
    try:
        creds_json = await asyncio.to_thread(_exchange_code, code)
    except Exception as exc:
        logger.exception("Gmail token exchange failed")
        raise IntegrationError("Gmail authorization failed") from exc
    return await upsert_connected_integration(db, org_id, PROVIDER, GMAIL_SCOPES, creds_json)


async def connect_gmail_demo(db: AsyncSession, org_id: UUID) -> Integration:
    return await upsert_connected_integration(db, org_id, PROVIDER, GMAIL_SCOPES, None, {"demo": True})


def _fetch_messages(creds_json: str, max_results: int) -> tuple[list[dict], str]:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_info(json.loads(creds_json), GMAIL_SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    resp = service.users().messages().list(userId="me", maxResults=max_results).execute()
    messages: list[dict] = []
    for m in resp.get("messages", []):
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["Subject", "From"])
            .execute()
        )
        headers = {h["name"].lower(): h["value"] for h in detail.get("payload", {}).get("headers", [])}
        messages.append(
            {
                "external_id": m["id"],
                "thread_id": detail.get("threadId"),
                "subject": headers.get("subject", ""),
                "body_preview": detail.get("snippet", ""),
                "sender": headers.get("from", ""),
                "occurred_at": detail.get("internalDate"),  # epoch ms
                "labels": detail.get("labelIds"),
            }
        )
    return messages, creds.to_json()


async def sync_gmail_messages(db: AsyncSession, org_id: UUID, max_results: int = 50) -> int:
    integration = await get_integration(db, org_id, PROVIDER)
    if not integration or integration.status != IntegrationStatus.CONNECTED.value:
        raise IntegrationError("Gmail is not connected")
    creds_json = read_credentials(integration)
    if not creds_json:
        raise IntegrationError("Gmail is connected in demo mode only — use demo data")
    if not gmail_configured():
        raise IntegrationError("Gmail OAuth is not configured")

    try:
        messages, refreshed = await asyncio.to_thread(_fetch_messages, creds_json, max_results)
    except Exception as exc:
        logger.exception("Gmail sync failed for org %s", org_id)
        integration.status = IntegrationStatus.ERROR.value
        raise IntegrationError("Gmail sync failed") from exc

    store_credentials(integration, refreshed)
    count = await ingest_email_batch(db, org_id, PROVIDER, messages)
    mark_synced(integration)
    return count
