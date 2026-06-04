import os
import tempfile

_db_dir = tempfile.mkdtemp(prefix="autoflow-test-")
_db_path = os.path.join(_db_dir, "test.db")
# TEST_DATABASE_URL permet de lancer la suite sur PostgreSQL (ex. en CI)
_test_db = os.environ.get("TEST_DATABASE_URL", f"sqlite+aiosqlite:///{_db_path}")
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": _test_db,
        "JWT_SECRET_KEY": "test-jwt-secret-" + "x" * 32,
        "API_SECRET_KEY": "test-api-secret-" + "y" * 32,
        "OPENAI_API_KEY": "",
        "GOOGLE_CLIENT_ID": "",
        "GOOGLE_CLIENT_SECRET": "",
        "MICROSOFT_CLIENT_ID": "",
        "MICROSOFT_CLIENT_SECRET": "",
        "DEMO_MODE": "true",
        "WORKFLOW_EXECUTOR": "local",
        "FRONTEND_URL": "http://front.test",
        "API_PUBLIC_URL": "http://api.test",
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import login_limiter  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_limiter():
    login_limiter.reset()
    yield


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as c:
        yield c


_counter = {"n": 0}


async def register(client, email: str | None = None, password: str = "motdepasse-solide") -> dict:
    _counter["n"] += 1
    email = email or f"user{_counter['n']}@cabinet-autoflow.fr"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "organization_name": f"Cabinet {_counter['n']}"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    return {"email": email, "password": password, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
async def user(client):
    return await register(client)
