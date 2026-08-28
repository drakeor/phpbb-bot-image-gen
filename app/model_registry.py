from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Protocol

from app.schemas import ImageRequest
from app.settings import Settings

if TYPE_CHECKING:
    from PIL import Image


class ImageModel(Protocol):
    alias: str
    model_id: str

    def prefetch(self, settings: Settings) -> None:
        ...

    def start(self, settings: Settings) -> None:
        ...

    def generate(self, req: ImageRequest) -> "Image.Image":
        ...

    def stop(self) -> None:
        ...


MODEL_MODULES = {
    "sd35-large": "app.models.model_sd35_large",
    "ssd-1b": "app.models.model_ssd_1b",
    "flux-schnell": "app.models.model_flux_schnell",
}


def validate_model_alias(alias: str) -> None:
    if alias not in MODEL_MODULES:
        known = ", ".join(sorted(MODEL_MODULES))
        raise ValueError(f"Unknown SD_MODEL '{alias}'. Known models: {known}")


def create_model(alias: str) -> "ImageModel":
    validate_model_alias(alias)
    module_path = MODEL_MODULES[alias]
    module = import_module(module_path)
    return module.create_model()
