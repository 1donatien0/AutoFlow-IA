from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from app.security import create_oauth_state, decrypt_secret, encrypt_secret
from tests.conftest import register


async def test_demo_connect_requires_signed_state(client, user):
    # Ancienne faille : state = org_id brut, sans authentification
    r = await client.get("/api/v1/integrations/gmail/demo-connect", params={"state": str(uuid4())})
    assert r.status_code == 400
    r = await client.get("/api/v1/integrations/gmail/callback", params={"state": str(uuid4()), "code": "x"})
    assert r.status_code == 400


async def test_state_bound_to_provider(client, user):
    r = await client.get("/api/v1/integrations/gmail/connect", headers=user["headers"])
    state = parse_qs(urlparse(r.json()["auth_url"]).query)["state"][0]
    r = await client.get("/api/v1/integrations/outlook/demo-connect", params={"state": state})
    assert r.status_code == 400


async def test_demo_connect_flow(client, user):
    r = await client.get("/api/v1/integrations/gmail/connect", headers=user["headers"])
    url = urlparse(r.json()["auth_url"])
    assert url.netloc == "api.test"
    state = parse_qs(url.query)["state"][0]
    r = await client.get("/api/v1/integrations/gmail/demo-connect", params={"state": state})
    assert r.status_code == 302
    assert r.headers["location"].startswith("http://front.test/integrations?connected=gmail")
    lst = (await client.get("/api/v1/integrations", headers=user["headers"])).json()
    assert [(i["provider"], i["status"]) for i in lst] == [("gmail", "connected")]
    # synchro réelle impossible en mode démo : erreur explicite, pas 0 silencieux
    r = await client.post("/api/v1/integrations/sync", json={"provider": "gmail"}, headers=user["headers"])
    assert r.status_code == 409


async def test_forged_state_for_other_org_is_rejected(client):
    a = await register(client)
    # jeton signé avec une autre clé
    import jwt

    forged = jwt.encode({"sub": str(uuid4()), "org": str(uuid4()), "prv": "gmail", "typ": "oauth_state"},
                        "wrong-key-" + "z" * 32, algorithm="HS256")
    r = await client.get("/api/v1/integrations/gmail/demo-connect", params={"state": forged})
    assert r.status_code == 400
    assert a  # utilisé


async def test_access_token_cannot_be_used_as_state(client, user):
    token = user["headers"]["Authorization"].split()[1]
    r = await client.get("/api/v1/integrations/gmail/demo-connect", params={"state": token})
    assert r.status_code == 400


def test_credentials_encryption_roundtrip():
    blob = encrypt_secret('{"refresh_token": "abc"}')
    assert "abc" not in blob
    assert decrypt_secret(blob) == '{"refresh_token": "abc"}'


def test_state_roundtrip():
    from app.security import verify_oauth_state

    org, usr = uuid4(), uuid4()
    assert verify_oauth_state(create_oauth_state(org, usr, "gmail"), "gmail") == (org, usr)
