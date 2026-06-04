from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from tests.conftest import register


async def test_register_login_me(client):
    u = await register(client, email="Alice@Cabinet-Autoflow.FR")
    r = await client.get("/api/v1/auth/me", headers=u["headers"])
    assert r.status_code == 200
    assert r.json()["email"] == "alice@cabinet-autoflow.fr"  # normalisé

    r = await client.post("/api/v1/auth/login", json={"email": "ALICE@cabinet-autoflow.fr", "password": u["password"]})
    assert r.status_code == 200


async def test_duplicate_email_rejected(client):
    u = await register(client)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": u["email"], "password": "autre-motdepasse", "organization_name": "Autre"},
    )
    assert r.status_code == 400


async def test_bad_password_and_unknown_user(client):
    u = await register(client)
    r1 = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": "faux-mot-de-passe"})
    r2 = await client.post("/api/v1/auth/login", json={"email": "nobody@exemple-autoflow.fr", "password": "faux-mot-de-passe"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()  # pas d'énumération des comptes


async def test_login_rate_limited(client):
    u = await register(client)
    codes = []
    for _ in range(get_settings().login_max_attempts + 1):
        r = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": "mauvais-mdp"})
        codes.append(r.status_code)
    assert codes[-1] == 429


async def test_password_too_long_is_422_not_500(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "long@exemple-autoflow.fr", "password": "é" * 40, "organization_name": "Org"},
    )
    assert r.status_code == 422


async def test_invalid_tokens(client):
    s = get_settings()
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nope"})).status_code == 401
    # sub non UUID -> 401 et non 500
    bad = jwt.encode(
        {"sub": "not-a-uuid", "typ": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        s.jwt_secret_key,
        algorithm="HS256",
    )
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad}"})).status_code == 401
    # jeton "none" refusé
    none_tok = jwt.encode({"sub": "x", "typ": "access"}, key=None, algorithm="none")
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {none_tok}"})).status_code == 401


async def test_security_headers_and_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert (await client.get("/health/ready")).json()["database"] == "up"
