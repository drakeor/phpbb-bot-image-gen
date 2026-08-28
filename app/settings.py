from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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
        )
