from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRETS = {
    "",
    "dev-secret-change-in-production",
    "dev-jwt-secret",
    "change-me-jwt-secret",
    "change-me-in-production-use-openssl-rand-hex-32",
}


def _env_files() -> tuple[str, ...]:
    """Charge le .env racine du monorepo puis un éventuel .env local (apps/api).

    Les fichiers suivants écrasent les précédents ; les variables d'environnement
    réelles restent prioritaires sur tous les fichiers.
    """
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    if len(here.parents) > 3:
        candidates.append(here.parents[3] / ".env")  # racine du dépôt
    candidates.append(here.parents[1] / ".env")  # apps/api/.env
    candidates.append(Path.cwd() / ".env")
    unique: list[str] = []
    for c in candidates:
        if str(c) not in unique:
            unique.append(str(c))
    return tuple(unique)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_files(), env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "sqlite+aiosqlite:///./autoflow.db"
    database_url_sync: str = "sqlite:///./autoflow.db"
    auto_create_tables: bool = True  # dev uniquement — en prod : `alembic upgrade head`
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    workflow_executor: Literal["local", "celery"] = "local"

    api_secret_key: str = "dev-secret-change-in-production"  # noqa: S105 - refusé en production
    encryption_key: str = ""  # clé Fernet (base64 urlsafe). Vide = dérivée de API_SECRET_KEY
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"

    jwt_secret_key: str = "dev-jwt-secret"  # noqa: S105 - refusé en production
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_expire_minutes: int = 1440

    login_max_attempts: int = 10
    login_window_seconds: int = 300

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/integrations/gmail/callback"

    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_redirect_uri: str = "http://localhost:8000/api/v1/integrations/outlook/callback"
    microsoft_tenant_id: str = "common"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    observation_only: bool = True  # Phases 1-3 : aucune écriture vers les systèmes externes
    demo_mode: bool = True  # autorise les données démo et la connexion OAuth simulée
    data_retention_days: int = 90

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_production_settings(self) -> "Settings":
        if self.is_production:
            for name in ("jwt_secret_key", "api_secret_key"):
                value = getattr(self, name)
                if value in _INSECURE_SECRETS or len(value) < 32:
                    raise ValueError(
                        f"{name.upper()} doit être défini (≥ 32 caractères) en production. "
                        "Générez-le avec : openssl rand -hex 32"
                    )
            if "*" in self.cors_origin_list:
                raise ValueError("CORS_ORIGINS='*' interdit en production (credentials activés).")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
