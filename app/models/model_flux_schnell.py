from __future__ import annotations

import gc

from PIL import Image

from app.schemas import ImageRequest
from app.settings import Settings


class FluxSchnellModel:
    alias = "flux-schnell"
    model_id = "black-forest-labs/FLUX.1-schnell"

    default_width = 1024
    default_height = 1024
    default_steps = 4
    default_guidance_scale = 0.0
    max_sequence_length = 256

    def __init__(self) -> None:
        self.pipe = None

    def prefetch(self, settings: Settings) -> None:
        from diffusers import FluxPipeline

        FluxPipeline.download(
            self.model_id,
            token=settings.hf_token,
            force_download=settings.force_download,
        )

    def start(self, settings: Settings) -> None:
        import torch
        from diffusers import FluxPipeline

        self.pipe = FluxPipeline.from_pretrained(
            self.model_id,
            torch_dtype=torch.bfloat16,
            token=settings.hf_token,
            force_download=settings.force_download,
            local_files_only=settings.local_files_only,
        )
        if settings.device.startswith("cuda") and torch.cuda.is_available():
            device_idx = 0
            if ":" in settings.device:
                try:
                    device_idx = int(settings.device.split(":")[1])
                except ValueError:
                    device_idx = 0
            total_vram_gb = torch.cuda.get_device_properties(device_idx).total_memory / (1024 ** 3)
            if total_vram_gb < 32 and hasattr(self.pipe, "enable_model_cpu_offload"):
                self.pipe.enable_model_cpu_offload(device=settings.device)
            else:
                self.pipe = self.pipe.to(settings.device)
        else:
            self.pipe = self.pipe.to(settings.device)

    def generate(self, req: ImageRequest) -> Image.Image:
        if self.pipe is None:
            raise RuntimeError("Model is not initialized")

        result = self.pipe(
            req.prompt,
            width=req.width or self.default_width,
            height=req.height or self.default_height,
            guidance_scale=(
                req.guidance_scale
                if req.guidance_scale is not None
                else self.default_guidance_scale
            ),
            num_inference_steps=req.steps or self.default_steps,
            max_sequence_length=self.max_sequence_length,
        )
        return result.images[0]

    def stop(self) -> None:
        self.pipe = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def create_model() -> FluxSchnellModel:
    return FluxSchnellModel()
