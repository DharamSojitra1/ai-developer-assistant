from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


ENV_EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"

AGENT_SETTINGS = [
    "AGENT_TEMPERATURE",
    "AGENT_MAX_TOKENS",
    "AGENT_MAX_ITERATIONS",
    "AGENT_HISTORY_LIMIT",
    "TOOL_TIMEOUT_SECONDS",
    "FRONTEND_URL",
]


def env_example_keys() -> set[str]:
    keys = set()

    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        keys.add(line.split("=", 1)[0].strip())

    return keys


def test_every_setting_is_documented_in_env_example():
    missing = set(Settings.model_fields) - env_example_keys()

    assert not missing, f"Add to .env.example: {sorted(missing)}"


def test_agent_settings_defaults(monkeypatch):
    for name in AGENT_SETTINGS:
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.AGENT_TEMPERATURE == 0.0
    assert settings.AGENT_MAX_TOKENS == 500
    assert settings.AGENT_MAX_ITERATIONS == 5
    assert settings.AGENT_HISTORY_LIMIT == 10
    assert settings.TOOL_TIMEOUT_SECONDS == 30.0
    assert settings.FRONTEND_URL == "http://localhost:5173"


def test_agent_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("AGENT_TEMPERATURE", "0.7")
    monkeypatch.setenv("AGENT_MAX_TOKENS", "1024")
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "8")
    monkeypatch.setenv("AGENT_HISTORY_LIMIT", "0")
    monkeypatch.setenv("FRONTEND_URL", "https://app.example.com")

    settings = Settings()

    assert settings.AGENT_TEMPERATURE == 0.7
    assert settings.AGENT_MAX_TOKENS == 1024
    assert settings.AGENT_MAX_ITERATIONS == 8
    assert settings.AGENT_HISTORY_LIMIT == 0
    assert settings.FRONTEND_URL == "https://app.example.com"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AGENT_TEMPERATURE", "-0.1"),
        ("AGENT_TEMPERATURE", "2.5"),
        ("AGENT_TEMPERATURE", "hot"),
        ("AGENT_MAX_TOKENS", "0"),
        ("AGENT_MAX_ITERATIONS", "0"),
        ("AGENT_MAX_ITERATIONS", "100"),
        ("AGENT_HISTORY_LIMIT", "-1"),
        ("TOOL_TIMEOUT_SECONDS", "0"),
        ("REQUEST_TIMEOUT", "-5"),
        ("RERANKER_DEVICE", "gpu"),
        ("MOCK_MODE", "maybe"),
        ("RAG_RETRIEVAL_TOP_K", "0"),
    ],
)
def test_invalid_values_fail_at_startup(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("name", ["API_KEY", "JWT_SECRET_KEY"])
def test_required_secrets_must_be_set(monkeypatch, name):
    monkeypatch.setenv(name, "")

    with pytest.raises(ValidationError):
        Settings()
