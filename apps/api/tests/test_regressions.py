"""Non-régression des correctifs d'octobre 2026 (lot 2)."""

import json
from uuid import UUID

from sqlalchemy import select

from app.database import async_session_maker
from app.main import app
from app.models.entities import Integration, Suggestion
from app.security import LoginRateLimiter
from app.services.classification import classify_heuristic
from app.services.process_mining import process_name
from tests.conftest import register


async def _seed(client, headers) -> None:
    r = await client.post("/api/v1/integrations/sync", json={"provider": "demo", "demo": True}, headers=headers)
    assert r.status_code == 200, r.text


async def test_commit_happens_before_response_is_sent(client, user):
    """Avant : le commit avait lieu APRÈS l'envoi de la réponse (portée « request »
    des dépendances yield) ; la requête suivante du front lisait l'ancien état."""
    h = user["headers"]
    await _seed(client, h)
    sugs = (await client.post("/api/v1/suggestions/generate", headers=h)).json()
    sid = sugs[0]["id"]
    seen: dict = {}

    async def check():
        async with async_session_maker() as other:  # autre connexion : ne voit que le commité
            seen["status"] = (
                await other.execute(select(Suggestion.status).where(Suggestion.id == UUID(sid)))
            ).scalar_one()

    async def call_with_body():
        body = json.dumps({"status": "approved"}).encode()
        sent: dict = {}
        delivered = False

        async def receive():
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                sent["status"] = message["status"]
            if message["type"] == "http.response.body" and not message.get("more_body"):
                await check()

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "PATCH",
            "scheme": "http", "path": f"/api/v1/suggestions/{sid}", "raw_path": f"/api/v1/suggestions/{sid}".encode(),
            "query_string": b"", "root_path": "", "server": ("api.test", 80), "client": ("127.0.0.1", 1234),
            "headers": [(b"content-type", b"application/json")]
            + [(k.lower().encode(), v.encode()) for k, v in h.items()],
        }
        await app(scope, receive, send)
        return sent["status"]

    assert await call_with_body() == 200
    assert seen["status"] == "approved"


async def test_rejected_suggestion_is_not_resurrected(client, user):
    h = user["headers"]
    await _seed(client, h)
    sugs = (await client.post("/api/v1/suggestions/generate", headers=h)).json()
    target = sugs[0]
    r = await client.patch(f"/api/v1/suggestions/{target['id']}", json={"status": "rejected"}, headers=h)
    assert r.status_code == 200
    again = (await client.post("/api/v1/suggestions/generate", headers=h)).json()
    same_title = [s for s in again if s["title"] == target["title"]]
    assert len(same_title) == 1 and same_title[0]["status"] == "rejected"


async def test_failed_sync_persists_error_status_and_can_retry(client, user, monkeypatch):
    h = user["headers"]
    me = (await client.get("/api/v1/auth/me", headers=h)).json()
    org_id = UUID(me["organization_id"])

    from app.services.integrations import common, gmail

    async with async_session_maker() as db:
        await common.upsert_connected_integration(db, org_id, "gmail", gmail.GMAIL_SCOPES, '{"token": "x"}')
        await db.commit()

    monkeypatch.setattr(gmail, "gmail_configured", lambda: True)

    def boom(*_a, **_k):
        raise RuntimeError("token revoked")

    monkeypatch.setattr(gmail, "_fetch_messages", boom)
    r = await client.post("/api/v1/integrations/sync", json={"provider": "gmail"}, headers=h)
    assert r.status_code == 409
    integ = next(i for i in (await client.get("/api/v1/integrations", headers=h)).json() if i["provider"] == "gmail")
    assert integ["status"] == "error"  # avant : annulé par le rollback, restait « connected »

    monkeypatch.setattr(gmail, "_fetch_messages", lambda creds, n: ([], creds))
    r = await client.post("/api/v1/integrations/sync", json={"provider": "gmail"}, headers=h)
    assert r.status_code == 200  # avant : « Gmail is not connected » tant qu'on ne reconnectait pas
    async with async_session_maker() as db:
        row = (await db.execute(
            select(Integration).where(Integration.organization_id == org_id, Integration.provider == "gmail")
        )).scalar_one()
        assert row.status == "connected"


async def test_demo_integration_is_flagged(client, user):
    h = user["headers"]
    url = (await client.get("/api/v1/integrations/outlook/connect", headers=h)).json()["auth_url"]
    await client.get(url.replace("http://api.test", ""))
    integ = (await client.get("/api/v1/integrations", headers=h)).json()
    assert integ and integ[0]["is_demo"] is True


async def test_registration_is_rate_limited_per_ip(client):
    codes = []
    for i in range(7):
        r = await client.post(
            "/api/v1/auth/register",
            json={"email": f"spam{i}@exemple-autoflow.fr", "password": "motdepasse-solide", "organization_name": "Spam"},
        )
        codes.append(r.status_code)
    assert codes[:5] == [201] * 5 and codes[-1] == 429


def test_rate_limiter_does_not_leak_keys():
    lim = LoginRateLimiter()
    for i in range(1000):
        lim.check(f"login:email:random{i}@x.fr")  # vérifications sans échec : rien n'est stocké
    assert len(lim) == 0
    lim.record_failure("k")
    assert len(lim) == 1
    lim.reset("k")
    assert len(lim) == 0


def test_classification_whole_words_and_accents():
    # « commentaire » ≠ « comment », verbe « avoir » ≠ avoir comptable
    assert classify_heuristic("Commentaire sur le bilan", "Je voudrais avoir votre avis")[0] == "autre"
    # « rappelle » ne déclenche plus « appel » (rendez-vous)
    assert classify_heuristic("Je vous rappelle demain", "")[0] == "autre"
    # sans accents / majuscules
    assert classify_heuristic("RELANCE FACTURE IMPAYEE", "")[0] == "relances"
    assert classify_heuristic("Relance facture #1042", "La facture 1042 reste impayée.")[0] == "relances"
    # cas signalé dans l'audit : classé « autre » auparavant
    assert classify_heuristic("Où en est ma déclaration TVA ?", "Pouvez-vous me donner le statut ?")[0] == "support"
    assert classify_heuristic("Avoir sur facture 12", "Pourriez-vous émettre un avoir ?")[0] == "facturation"


def test_process_names_are_readable_and_stable():
    assert process_name(["Relance", "Relance", "Relance"]) == "Relance ×3"
    assert process_name(["Email_demande", "Facturation"]) == "Demande de devis → Facturation"


async def test_retention_purges_derived_personal_data(client, user):
    from datetime import datetime, timedelta, timezone

    from app.models.entities import Prediction
    from app.services.data_governance import purge_expired_events

    me = (await client.get("/api/v1/auth/me", headers=user["headers"])).json()
    org_id = UUID(me["organization_id"])
    async with async_session_maker() as db:
        db.add(Prediction(organization_id=org_id, prediction_type="payment_delay_risk",
                          entity_ref="client@exemple.fr", score=0.5, explanation="x",
                          created_at=datetime.now(timezone.utc) - timedelta(days=400)))
        await db.commit()
        await purge_expired_events(db, 90)
        await db.commit()
        left = (await db.execute(select(Prediction).where(Prediction.organization_id == org_id))).scalars().all()
        assert left == []


async def test_export_includes_metrics_snapshots(client):
    u = await register(client)
    await client.get("/api/v1/observation/dashboard", headers=u["headers"])
    export = (await client.get("/api/v1/organization/export", headers=u["headers"])).json()
    assert len(export["metrics_snapshots"]) == 1
