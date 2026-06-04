import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    agents,
    auth,
    health,
    integrations,
    observation,
    organization,
    predictions,
    processes,
    suggestions,
    workflows,
)
from app.config import get_settings
from app.database import Base, engine
from app.models import entities  # noqa: F401  (enregistre les modèles dans Base.metadata)

logger = logging.getLogger("autoflow")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    if not settings.is_production and settings.jwt_secret_key == "dev-jwt-secret":  # noqa: S105
        logger.warning("JWT_SECRET_KEY par défaut utilisé — à ne JAMAIS faire en production.")
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

    app = FastAPI(
        title="AutoFlow AI API",
        description="Observer → Comprendre → Suggérer → Automatiser",
        version="0.2.0",
        lifespan=lifespan,
        # Pas de documentation interactive publique en production
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health.router)
    for module in (auth, integrations, observation, processes, suggestions, workflows, agents, predictions,
                   organization):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
