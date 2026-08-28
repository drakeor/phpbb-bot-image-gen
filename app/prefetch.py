from __future__ import annotations

from app.model_registry import create_model
from app.settings import Settings


def main() -> None:
    settings = Settings.from_env(require_api_key=False)
    model = create_model(settings.model)
    model.prefetch(settings)


if __name__ == "__main__":
    main()
