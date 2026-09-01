from __future__ import annotations

import gc

from PIL import Image

from app.schemas import ImageRequest
from app.settings import Settings
from app.sizing import MEGAPIXEL_BUCKETS


class SD35LargeModel:
    alias = "sd35-large"
    model_id = "stabilityai/stable-diffusion-3.5-large"

    default_width = 1024
    default_height = 1024
    default_steps = 30
    default_guidance_scale = 7.5

    # Trained multi-aspect near 1 megapixel with a 16-channel VAE. Every entry
    # aligns to 16 and to 64, so this set covers both requirements.
    size_buckets = MEGAPIXEL_BUCKETS

    def __init__(self) -> None:
        self.pipe = None

    def prefetch(self, settings: Settings) -> None:
        from diffusers import StableDiffusion3Pipeline

        StableDiffusion3Pipeline.download(
            self.model_id,
            token=settings.hf_token,
            force_download=settings.force_download,
        )

    def start(self, settings: Settings) -> None:
        import torch
        from diffusers import StableDiffusion3Pipeline

        self.pipe = StableDiffusion3Pipeline.from_pretrained(
            self.model_id,
            torch_dtype=torch.bfloat16,
            token=settings.hf_token,
            force_download=settings.force_download,
            local_files_only=settings.local_files_only,
        )
        self.pipe = self.pipe.to(settings.device)
        if hasattr(self.pipe, "enable_attention_slicing"):
            self.pipe.enable_attention_slicing()
        if hasattr(self.pipe, "enable_vae_slicing"):
            self.pipe.enable_vae_slicing()

    def generate(self, req: ImageRequest) -> Image.Image:
        if self.pipe is None:
            raise RuntimeError("Model is not initialized")

        result = self.pipe(
            prompt=req.prompt,
            negative_prompt=req.negative_prompt,
            width=req.width or self.default_width,
            height=req.height or self.default_height,
            guidance_scale=(
                req.guidance_scale
                if req.guidance_scale is not None
                else self.default_guidance_scale
            ),
            num_inference_steps=req.steps or self.default_steps,
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


def create_model() -> SD35LargeModel:
    return SD35LargeModel()
