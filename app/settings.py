from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid {name} '{value}': must be a number") from exc
    if parsed < 0.0:
        raise ValueError(f"Invalid {name} '{value}': must be zero or greater")
    return parsed


def _env_prob(name: str, default: float) -> float:
    parsed = _env_float(name, default)
    if parsed > 1.0:
        raise ValueError(f"Invalid {name} '{parsed}': must be between 0 and 1")
    return parsed


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    host: str
    port: int
    hf_token: str | None
    hf_home: str
    device: str
    force_download: bool
    local_files_only: bool
    variation_enabled: bool
    size_weight_wide: float
    size_weight_tall: float
    size_weight_square: float
    p_standard_size: float
    p_random_crop: float
    p_noise: float
    p_blur: float
    p_contrast: float
    p_pixelate: float
    p_jpeg: float

    def orientation_weights(self) -> dict[str, float]:
        return {
            "wide": self.size_weight_wide,
            "tall": self.size_weight_tall,
            "square": self.size_weight_square,
        }

    @classmethod
    def from_env(cls, require_api_key: bool = True) -> "Settings":
        hf_home = os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
        os.environ["HF_HOME"] = hf_home
        api_key = os.getenv("SD_API_KEY")
        if require_api_key and not api_key:
            raise RuntimeError("SD_API_KEY is required")

        port_str = os.getenv("SD_PORT", "8005")
        try:
            port = int(port_str)
        except ValueError as exc:
            raise ValueError(f"Invalid SD_PORT '{port_str}': must be an integer") from exc

        return cls(
            api_key=api_key,
            model=os.getenv("SD_MODEL", "sd35-large"),
            host=os.getenv("SD_HOST", "0.0.0.0"),
            port=port,
            hf_token=os.getenv("HF_TOKEN"),
            hf_home=hf_home,
            device=os.getenv("SD_DEVICE", "cuda"),
            force_download=_env_bool("SD_FORCE_DOWNLOAD", False),
            local_files_only=_env_bool("SD_LOCAL_FILES_ONLY", False),
            variation_enabled=_env_bool("SD_VARIATION_ENABLED", True),
            size_weight_wide=_env_float("SD_SIZE_WEIGHT_WIDE", 0.55),
            size_weight_tall=_env_float("SD_SIZE_WEIGHT_TALL", 0.35),
            size_weight_square=_env_float("SD_SIZE_WEIGHT_SQUARE", 0.10),
            p_standard_size=_env_prob("SD_P_STANDARD_SIZE", 0.50),
            p_random_crop=_env_prob("SD_P_RANDOM_CROP", 0.35),
            p_noise=_env_prob("SD_P_NOISE", 0.03),
            p_blur=_env_prob("SD_P_BLUR", 0.03),
            p_contrast=_env_prob("SD_P_CONTRAST", 0.08),
            p_pixelate=_env_prob("SD_P_PIXELATE", 0.02),
            p_jpeg=_env_prob("SD_P_JPEG", 0.30),
        )
