from __future__ import annotations

import pytest

from app.settings import Settings


def test_service_settings_require_api_key(monkeypatch):
    monkeypatch.delenv("SD_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SD_API_KEY is required"):
        Settings.from_env()


def test_prefetch_settings_do_not_require_api_key(monkeypatch):
    monkeypatch.delenv("SD_API_KEY", raising=False)

    settings = Settings.from_env(require_api_key=False)

    assert settings.api_key is None


def test_invalid_sd_port_raises_descriptive_error(monkeypatch):
    monkeypatch.setenv("SD_API_KEY", "secret")
    monkeypatch.setenv("SD_PORT", "not-a-port")

    with pytest.raises(ValueError, match="Invalid SD_PORT 'not-a-port': must be an integer"):
        Settings.from_env()
