"""Authentification (JWT, bcrypt), jetons d'état OAuth signés et chiffrement des secrets."""

from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.entities import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - type de jeton, pas un secret
OAUTH_STATE_TYPE = "oauth_state"
OAUTH_STATE_TTL_MINUTES = 10

# Hash factice pour égaliser le temps de réponse quand l'utilisateur n'existe pas
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalizer", bcrypt.gensalt()).decode("utf-8")


# --------------------------------------------------------------------------- mots de passe
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), (hashed or _DUMMY_HASH).encode("utf-8")) and bool(hashed)
    except ValueError:
        return False


# --------------------------------------------------------------------------- JWT
def _encode(payload: dict[str, Any], minutes: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    full = {**payload, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(full, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    return _encode({**(extra or {}), "sub": subject, "typ": ACCESS_TOKEN_TYPE}, get_settings().jwt_expire_minutes)


def create_oauth_state(org_id: UUID, user_id: UUID, provider: str) -> str:
    """État OAuth signé, lié à l'organisation, à l'utilisateur et au fournisseur (anti-CSRF)."""
    return _encode(
        {
            "sub": str(user_id),
            "org": str(org_id),
            "prv": provider,
            "typ": OAUTH_STATE_TYPE,
            "nonce": secrets.token_urlsafe(8),
        },
        OAUTH_STATE_TTL_MINUTES,
    )


def verify_oauth_state(state: str, provider: str) -> tuple[UUID, UUID]:
    """Retourne (org_id, user_id) ou lève HTTP 400."""
    try:
        payload = _decode(state, OAUTH_STATE_TYPE)
        if payload.get("prv") != provider:
            raise jwt.InvalidTokenError("provider mismatch")
        return UUID(payload["org"]), UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state") from exc


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = _decode(token, ACCESS_TOKEN_TYPE)
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise credentials_exception from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# --------------------------------------------------------------------------- chiffrement
def _fernet() -> Fernet:
    settings = get_settings()
    if settings.encryption_key:
        return Fernet(settings.encryption_key.encode())
    digest = hashlib.sha256(f"autoflow-credentials:{settings.api_secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Unable to decrypt stored credentials") from exc


# --------------------------------------------------------------------------- anti brute-force
class LoginRateLimiter:
    """Limiteur en mémoire (fenêtre glissante). Suffisant pour un process unique ;
    en multi-instances, remplacer par Redis."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float, window: int) -> deque[float]:
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        return q

    def check(self, key: str) -> None:
        s = get_settings()
        with self._lock:
            q = self._prune(key, time.monotonic(), s.login_window_seconds)
            if len(q) >= s.login_max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts, try again later",
                )

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


login_limiter = LoginRateLimiter()
