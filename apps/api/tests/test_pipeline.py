from tests.conftest import register


async def _seed(client, headers) -> int:
    r = await client.post("/api/v1/integrations/sync", json={"provider": "demo", "demo": True}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["ingested"]


async def test_full_pipeline(client, user):
    h = user["headers"]
    assert await _seed(client, h) == 11
    assert await _seed(client, h) == 0  # idempotent

    dash = (await client.get("/api/v1/observation/dashboard", headers=h)).json()
    assert sum(dash["category_breakdown"].values()) == 11
    assert dash["hours_lost_estimate"] > 0

    events = (await client.get("/api/v1/observation/events?limit=5", headers=h)).json()
    assert len(events) == 5
    assert (await client.get("/api/v1/observation/events?limit=100000", headers=h)).status_code == 422

    procs = (await client.post("/api/v1/processes/discover", headers=h)).json()
    assert procs and all(p["frequency"] >= 1 for p in procs)
    # relance la découverte : ne doit pas violer les clés étrangères
    procs2 = (await client.post("/api/v1/processes/discover", headers=h)).json()
    assert len(procs2) == len(procs)
    total_instances = 0
    for p in procs2:
        inst = (await client.get(f"/api/v1/processes/{p['id']}/instances", headers=h)).json()
        total_instances += len(inst)
        assert all(i["process_id"] == p["id"] for i in inst)
    assert total_instances == sum(p["frequency"] for p in procs2)

    sugs = (await client.post("/api/v1/suggestions/generate", headers=h)).json()
    titles = {s["title"] for s in sugs}
    assert "Automatiser les relances factures" in titles
    relance = next(s for s in sugs if s["title"] == "Automatiser les relances factures")
    # plus de chiffres inventés (anciennement max(n, 85))
    assert relance["monthly_frequency"] == dash["category_breakdown"]["relances"]

    r = await client.patch(f"/api/v1/suggestions/{relance['id']}", json={"status": "bogus"}, headers=h)
    assert r.status_code == 422
    r = await client.patch(f"/api/v1/suggestions/{relance['id']}", json={"status": "approved"}, headers=h)
    assert r.status_code == 200

    wf = (await client.post(f"/api/v1/workflows/from-suggestion/{relance['id']}", headers=h)).json()
    wf_again = (await client.post(f"/api/v1/workflows/from-suggestion/{relance['id']}", headers=h)).json()
    assert wf["id"] == wf_again["id"]

    # régénérer les suggestions ne supprime pas celle qui est liée au workflow
    sugs2 = (await client.post("/api/v1/suggestions/generate", headers=h)).json()
    assert relance["id"] in {s["id"] for s in sugs2}
    assert len([s for s in sugs2 if s["title"] == relance["title"]]) == 1

    ex = await client.post("/api/v1/workflows/execute", json={"workflow_id": wf["id"]}, headers=h)
    assert ex.status_code == 200 and ex.json()["status"] == "success"
    assert any(log["status"] == "skipped" for log in ex.json()["logs"])

    ks = await client.post(f"/api/v1/workflows/{wf['id']}/kill-switch?enabled=true", headers=h)
    assert ks.json() == {"kill_switch": True, "status": "paused"}
    assert (await client.post("/api/v1/workflows/execute", json={"workflow_id": wf["id"]}, headers=h)).status_code == 409
    ks = await client.post(f"/api/v1/workflows/{wf['id']}/kill-switch?enabled=false", headers=h)
    assert ks.json()["status"] == "approved"

    preds = (await client.post("/api/v1/predictions/generate", headers=h)).json()
    types = {p["prediction_type"] for p in preds}
    assert "payment_delay_risk" in types
    assert all(0 <= p["score"] <= 1 for p in preds)

    run = await client.post("/api/v1/agents/run", json={"agent_type": "support", "task": "FAQ TVA"}, headers=h)
    assert run.status_code == 200
    assert (await client.post("/api/v1/agents/run", json={"agent_type": "hacker", "task": "x"}, headers=h)).status_code == 422

    logs = (await client.get("/api/v1/organization/audit-logs", headers=h)).json()
    assert {"workflow_kill_switch", "suggestion_status_changed", "agent_run"} <= {log["action"] for log in logs}


async def test_tenant_isolation(client):
    a = await register(client)
    b = await register(client)
    await _seed(client, a["headers"])
    sugs = (await client.post("/api/v1/suggestions/generate", headers=a["headers"])).json()
    procs = (await client.post("/api/v1/processes/discover", headers=a["headers"])).json()

    assert (await client.get("/api/v1/observation/events", headers=b["headers"])).json() == []
    assert (await client.get("/api/v1/suggestions", headers=b["headers"])).json() == []
    r = await client.patch(f"/api/v1/suggestions/{sugs[0]['id']}", json={"status": "approved"}, headers=b["headers"])
    assert r.status_code == 404
    r = await client.get(f"/api/v1/processes/{procs[0]['id']}/instances", headers=b["headers"])
    assert r.json() == []
    export = (await client.get("/api/v1/organization/export", headers=b["headers"])).json()
    assert export["raw_events"] == []


async def test_export_and_purge(client, user):
    h = user["headers"]
    await _seed(client, h)
    await client.get("/api/v1/integrations/gmail/connect", headers=h)
    export = (await client.get("/api/v1/organization/export", headers=h)).json()
    assert len(export["raw_events"]) == 11
    assert all("hashed_password" not in u for u in export["users"])

    assert (await client.delete("/api/v1/organization/data", headers=h)).status_code == 400
    r = await client.delete("/api/v1/organization/data?confirm=true", headers=h)
    assert r.status_code == 200 and r.json()["deleted"]["raw_events"] == 11
    assert (await client.get("/api/v1/observation/events", headers=h)).json() == []
    # le compte reste utilisable
    assert (await client.get("/api/v1/auth/me", headers=h)).status_code == 200


async def test_retention_purge(client, user):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.database import async_session_maker
    from app.models.entities import RawEvent
    from app.services.data_governance import purge_expired_events
    from app.services.ingestion import ingest_email_batch

    me = (await client.get("/api/v1/auth/me", headers=user["headers"])).json()
    async with async_session_maker() as db:
        from uuid import UUID

        old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        await ingest_email_batch(db, UUID(me["organization_id"]), "test", [
            {"external_id": "old-1", "subject": "Relance facture", "occurred_at": old},
            {"external_id": "new-1", "subject": "Relance facture"},
        ])
        await db.commit()
        deleted = await purge_expired_events(db, 90)
        await db.commit()
        assert deleted >= 1
        left = (await db.execute(select(RawEvent.external_id).where(RawEvent.source == "test"))).scalars().all()
        assert left == ["new-1"]
