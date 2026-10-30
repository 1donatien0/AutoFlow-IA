"""Accès LLM centralisé (OpenAI, optionnel).

- Client asynchrone pour ne pas bloquer la boucle d'événements FastAPI.
- Les erreurs sont journalisées mais jamais renvoyées telles quelles à l'utilisateur
  (elles peuvent contenir des détails internes).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 20.0


@lru_cache(maxsize=2)
def _client(api_key: str):
    """Client partagé (pool de connexions réutilisé) au lieu d'un client par appel."""
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)


def llm_enabled() -> bool:
    return bool(get_settings().openai_api_key)


async def chat_completion(messages: list[dict], max_tokens: int = 300) -> str | None:
    """Retourne le texte de la réponse, ou None si le LLM est indisponible."""
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    try:
        resp = await _client(settings.openai_api_key).chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip() or None
    except Exception:
        logger.exception("LLM call failed")
        return None
