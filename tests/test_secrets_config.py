from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

STRONG = "x" * 48
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("API_KEY", STRONG)
    monkeypatch.setenv("JWT_SECRET_KEY", STRONG)


def test_strong_production_secrets_are_accepted(production):
    assert Settings().APP_ENV == "production"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("JWT_SECRET_KEY", "change-me-to-a-long-random-string"),
        ("JWT_SECRET_KEY", "short-secret"),
        ("API_KEY", "your-super-secret-api-key-change-this"),
        ("API_KEY", "short"),
        ("DEBUG", "true"),
    ],
)
def test_unsafe_production_values_stop_startup(production, monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match="Unsafe production configuration"):
        Settings()


def test_development_allows_example_secrets(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "change-me-to-a-long-random-string")

    Settings()


def test_env_file_is_gitignored():
    ignored = {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    }

    assert ".env" in ignored
