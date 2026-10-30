from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.entities import Organization, User
from app.schemas.common import AuthToken, LoginRequest, RegisterRequest, UserOut
from app.security import create_access_token, get_current_user, hash_password, login_limiter, verify_password
from app.services.audit import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])

REGISTER_MAX_PER_WINDOW = 5  # inscriptions par IP et par fenêtre LOGIN_WINDOW_SECONDS


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=AuthToken, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db, scope="function")):
    # Chaque inscription compte (réussie ou non) : sans cela, une IP pouvait créer
    # un nombre illimité d'organisations.
    register_key = f"register:{_client_ip(request)}"
    login_limiter.check(register_key, REGISTER_MAX_PER_WINDOW)
    login_limiter.record_failure(register_key)
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organization(name=body.organization_name, vertical="comptabilite")
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # course entre deux inscriptions simultanées
        raise HTTPException(status_code=400, detail="Email already registered") from exc

    await log_audit(db, org.id, "user_registered", {"user_id": str(user.id)}, actor=user.email)
    return AuthToken(access_token=create_access_token(str(user.id), {"org_id": str(org.id)}))


@router.post("/login", response_model=AuthToken)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db, scope="function")):
    keys = (f"login:ip:{_client_ip(request)}", f"login:email:{body.email}")
    for k in keys:
        login_limiter.check(k)

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # verify_password est appelé même si l'utilisateur n'existe pas (temps constant)
    password_ok = verify_password(body.password, user.hashed_password if user else None)
    if not user or not password_ok or not user.is_active:
        for k in keys:
            login_limiter.record_failure(k)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    login_limiter.reset(keys[1])
    await log_audit(db, user.organization_id, "user_login", None, actor=user.email)
    return AuthToken(access_token=create_access_token(str(user.id), {"org_id": str(user.organization_id)}))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
