from datetime import timezone

import pytest

from app.config import Settings
from app.services.classification import classify_heuristic, parse_llm_answer
from app.services.ingestion import parse_occurred_at


def test_parse_occurred_at_formats():
    assert parse_occurred_at("1700000000000").year == 2023  # Gmail internalDate (ms)
    assert parse_occurred_at(1700000000).year == 2023
    dt = parse_occurred_at("2026-01-02T03:04:05Z")
    assert dt.tzinfo is not None and dt.utcoffset() == timezone.utc.utcoffset(dt)
    assert parse_occurred_at("garbage").tzinfo is not None


def test_classify_heuristic():
    assert classify_heuristic("Demande de devis", "merci pour l'offre")[0] == "devis"
    assert classify_heuristic("Relance facture impayée", "")[0] == "relances"
    assert classify_heuristic("", "")[0] == "autre"


def test_parse_llm_answer_validates_category():
    assert parse_llm_answer("devis|0.9") == ("devis", 0.9)
    assert parse_llm_answer("hacked|0.99") is None
    assert parse_llm_answer("support|7") == ("support", 0.99)


def test_production_rejects_default_secrets():
    with pytest.raises(ValueError):
        Settings(environment="production", jwt_secret_key="dev-jwt-secret", api_secret_key="a" * 40)
    ok = Settings(environment="production", jwt_secret_key="j" * 40, api_secret_key="a" * 40)
    assert ok.is_production
