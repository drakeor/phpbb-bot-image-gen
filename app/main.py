from __future__ import annotations

import sys
import uvicorn

from app.model_registry import validate_model_alias
from app.settings import Settings


def main() -> None:
    try:
        settings = Settings.from_env()
        validate_model_alias(settings.model)
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(2)

    uvicorn.run("app.api:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
