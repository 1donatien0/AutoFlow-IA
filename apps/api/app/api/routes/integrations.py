from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.entities import Integration, User
from app.schemas.common import IntegrationOut, SyncRequest
from app.security import create_oauth_state, get_current_user, verify_oauth_state
from app.services.audit import log_audit
from app.services.integrations import (
    IntegrationError,
    connect_gmail_demo,
    connect_outlook_demo,
    get_gmail_auth_url,
    get_outlook_auth_url,
    handle_gmail_callback,
    handle_outlook_callback,
    sync_gmail_messages,
    sync_outlook_messages,
)
from app.services.metrics import seed_demo_events

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _front_redirect(**params: str) -> RedirectResponse:
    # Destination fixe (FRONTEND_URL) : pas de redirection ouverte possible
    return RedirectResponse(url=f"{get_settings().frontend_url}/integrations?{urlencode(params)}", status_code=302)


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    result = await db.execute(select(Integration).where(Integration.organization_id == user.organization_id))
    return result.scalars().all()


# ----------------------------------------------------------------------------- connexion
@router.get("/{provider}/connect")
async def connect(provider: str, user: User = Depends(get_current_user)):
    state = create_oauth_state(user.organization_id, user.id, provider)
    try:
        if provider == "gmail":
            return {"auth_url": get_gmail_auth_url(state)}
        if provider == "outlook":
            return {"auth_url": get_outlook_auth_url(state)}
    except IntegrationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    raise HTTPException(status_code=404, detail="Unknown provider")


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    state: str = Query(..., max_length=2048),
    code: str | None = Query(None, max_length=4096),
    error: str | None = Query(None, max_length=256),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    if provider not in ("gmail", "outlook"):
        raise HTTPException(status_code=404, detail="Unknown provider")
    org_id, user_id = verify_oauth_state(state, provider)
    if error or not code:
        return _front_redirect(error=provider)
    try:
        handler = handle_gmail_callback if provider == "gmail" else handle_outlook_callback
        await handler(db, org_id, code)
    except IntegrationError:
        return _front_redirect(error=provider)
    await log_audit(db, org_id, "integration_connected", {"provider": provider}, actor=str(user_id))
    return _front_redirect(connected=provider)


@router.get("/{provider}/demo-connect")
async def demo_connect(
    provider: str,
    state: str = Query(..., max_length=2048),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    """Connexion simulée (sans OAuth réel) — uniquement si DEMO_MODE=true et état signé valide."""
    if not get_settings().demo_mode or provider not in ("gmail", "outlook"):
        raise HTTPException(status_code=404, detail="Not found")
    org_id, user_id = verify_oauth_state(state, provider)
    if provider == "gmail":
        await connect_gmail_demo(db, org_id)
    else:
        await connect_outlook_demo(db, org_id)
    await log_audit(db, org_id, "integration_connected", {"provider": provider, "demo": True}, actor=str(user_id))
    return _front_redirect(connected=provider)


# ----------------------------------------------------------------------------- synchronisation
@router.post("/sync")
async def sync_data(
    body: SyncRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    provider = "demo" if body.demo else body.provider
    try:
        if provider == "demo":
            if not get_settings().demo_mode:
                raise HTTPException(status_code=403, detail="Demo data is disabled")
            count = await seed_demo_events(db, user.organization_id)
        elif provider == "gmail":
            count = await sync_gmail_messages(db, user.organization_id)
        else:
            count = await sync_outlook_messages(db, user.organization_id)
    except IntegrationError as exc:
        # Conserve le statut « error » posé par le connecteur (sinon annulé par le rollback)
        # et trace l'échec ; aucun email partiel n'a été ingéré à ce stade.
        await log_audit(db, user.organization_id, "integration_sync_failed", {"provider": provider},
                        actor=user.email)
        await db.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await log_audit(db, user.organization_id, "integration_sync", {"provider": provider, "ingested": count},
                    actor=user.email)
    return {"ingested": count, "provider": provider}
