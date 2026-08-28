from __future__ import annotations

import types

import pytest

from app import model_registry


def test_known_aliases_are_registered():
    assert model_registry.MODEL_MODULES == {
        "sd35-large": "app.models.model_sd35_large",
        "ssd-1b": "app.models.model_ssd_1b",
        "flux-schnell": "app.models.model_flux_schnell",
    }


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError, match="Unknown SD_MODEL"):
        model_registry.create_model("nope")


def test_create_model_imports_only_selected_module(monkeypatch):
    calls: list[str] = []

    def fake_import(name: str):
        calls.append(name)
        return types.SimpleNamespace(create_model=lambda: {"module": name})

    monkeypatch.setattr(model_registry, "import_module", fake_import)

    created = model_registry.create_model("ssd-1b")

    assert created == {"module": "app.models.model_ssd_1b"}
    assert calls == ["app.models.model_ssd_1b"]
