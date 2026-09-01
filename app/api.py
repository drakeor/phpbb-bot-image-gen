from __future__ import annotations

import asyncio
import base64
import gc
import io
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from app import postprocess, sizing
from app.model_registry import ImageModel, create_model
from app.schemas import ImageRequest, ImageResponse
from app.settings import Settings

logger = logging.getLogger("app.api")
logging.basicConfig(level=logging.INFO)

generation_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_env()
    app.state.settings = settings

    t0 = time.perf_counter()
    logger.info("Loading model '%s' on %s...", settings.model, settings.device)
    active_model = create_model(settings.model)
    active_model.start(settings)
    app.state.active_model = active_model
    elapsed = time.perf_counter() - t0
    logger.info("Loaded model '%s' in %.2f seconds", settings.model, elapsed)

    try:
        yield
    finally:
        active_model = getattr(app.state, "active_model", None)
        if active_model is not None:
            logger.info("Stopping active model...")
            active_model.stop()
            logger.info("Active model stopped.")


app = FastAPI(lifespan=lifespan)


def verify_key(request: Request) -> None:
    settings: Settings | None = getattr(request.app.state, "settings", None)
    if settings is None or request.headers.get("x-api-key") != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")


def _encode_png(image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _is_gpu_oom(exc: Exception) -> bool:
    try:
        import torch

        oom_types = [torch.cuda.OutOfMemoryError]
        if hasattr(torch, "OutOfMemoryError"):
            oom_types.append(torch.OutOfMemoryError)
        if isinstance(exc, tuple(oom_types)):
            return True
    except Exception:
        pass
    return "out of memory" in str(exc).lower()


def _clear_gpu_cache() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


@app.post("/v1/images/generations", response_model=ImageResponse)
async def create_image(
    req: ImageRequest,
    request: Request,
    _: None = Depends(verify_key),
):
    active_model: ImageModel | None = getattr(request.app.state, "active_model", None)
    if active_model is None:
        raise HTTPException(status_code=503, detail="Model is not ready")

    settings: Settings = request.app.state.settings

    async with generation_lock:
        t0 = time.perf_counter()
        logger.info(
            "Generating %d image(s) for prompt=%r (width=%s, height=%s, steps=%s, guidance_scale=%s)",
            req.n,
            req.prompt,
            req.width,
            req.height,
            req.steps,
            req.guidance_scale,
        )
        data = []
        sizes: list[str] = []
        try:
            for _ in range(req.n):
                image_req = sizing.resolve_size(req, active_model, settings)
                image = await asyncio.to_thread(active_model.generate, image_req)
                image = await asyncio.to_thread(postprocess.apply, image, settings)
                sizes.append(f"{image.width}x{image.height}")
                data.append({"b64_json": _encode_png(image)})
        except Exception as exc:
            if _is_gpu_oom(exc):
                _clear_gpu_cache()
                logger.error("GPU allocation failure during generation: %s", exc)
                raise HTTPException(
                    status_code=503,
                    detail=f"GPU allocation failed: {exc}",
                ) from exc

            logger.error("Generation failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Generation failed: {exc}",
            ) from exc

        elapsed = time.perf_counter() - t0
        logger.info(
            "Completed %d image(s) in %.2f seconds (sizes: %s)",
            req.n,
            elapsed,
            ", ".join(sizes),
        )

    return {"created": int(time.time()), "data": data}


@app.get("/health")
async def health():
    return {"ok": True}
