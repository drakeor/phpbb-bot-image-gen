from __future__ import annotations

import gc

from PIL import Image

from app.schemas import ImageRequest
from app.settings import Settings
from app.sizing import MEGAPIXEL_BUCKETS


class SSD1BModel:
    alias = "ssd-1b"
    model_id = "segmind/SSD-1B"

    default_width = 1024
    default_height = 1024
    default_steps = 25
    default_guidance_scale = 9.0
    default_negative_prompt = (
        "ugly, blurry, low quality, distorted, deformed, watermark, text, signature"
    )

    # SSD-1B is an SDXL distillation and carries the SDXL aspect bucket set.
    size_buckets = MEGAPIXEL_BUCKETS

    def __init__(self) -> None:
        self.pipe = None

    def prefetch(self, settings: Settings) -> None:
        from diffusers import StableDiffusionXLPipeline

        StableDiffusionXLPipeline.download(
            self.model_id,
            use_safetensors=True,
            variant="fp16",
            token=settings.hf_token,
            force_download=settings.force_download,
        )

    def start(self, settings: Settings) -> None:
        import torch
        from diffusers import StableDiffusionXLPipeline

        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            self.model_id,
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16",
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
            negative_prompt=req.negative_prompt or self.default_negative_prompt,
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


def create_model() -> SSD1BModel:
    return SSD1BModel()
