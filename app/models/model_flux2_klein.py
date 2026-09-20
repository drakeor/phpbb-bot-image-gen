from __future__ import annotations

import gc

from PIL import Image

from app.schemas import ImageRequest
from app.settings import Settings
from app.sizing import MEGAPIXEL_BUCKETS


class Flux2KleinModel:
    alias = "flux2-klein"
    model_id = "black-forest-labs/FLUX.2-klein-9B"
    text_encoder_id = "ponpoke/flux2-klein-9b-uncensored-text-encoder"

    default_width = 1024
    default_height = 1024
    default_steps = 4
    default_guidance_scale = 1.0
    max_sequence_length = 512

    size_buckets = MEGAPIXEL_BUCKETS

    def __init__(self) -> None:
        self.pipe = None

    def prefetch(self, settings: Settings) -> None:
        from diffusers import Flux2KleinPipeline
        from huggingface_hub import snapshot_download

        Flux2KleinPipeline.download(
            self.model_id,
            token=settings.hf_token,
            force_download=settings.force_download,
        )
        snapshot_download(
            self.text_encoder_id,
            token=settings.hf_token,
            force_download=settings.force_download,
        )

    def start(self, settings: Settings) -> None:
        import torch
        from diffusers import Flux2KleinPipeline
        from transformers import AutoModel, AutoTokenizer

        dtype = torch.bfloat16
        tokenizer = AutoTokenizer.from_pretrained(
            self.text_encoder_id,
            token=settings.hf_token,
            force_download=settings.force_download,
            local_files_only=settings.local_files_only,
        )
        text_encoder = AutoModel.from_pretrained(
            self.text_encoder_id,
            torch_dtype=dtype,
            token=settings.hf_token,
            force_download=settings.force_download,
            local_files_only=settings.local_files_only,
        )
        self.pipe = Flux2KleinPipeline.from_pretrained(
            self.model_id,
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            torch_dtype=dtype,
            token=settings.hf_token,
            force_download=settings.force_download,
            local_files_only=settings.local_files_only,
        )

        if (
            settings.device.startswith("cuda")
            and torch.cuda.is_available()
            and hasattr(self.pipe, "enable_model_cpu_offload")
        ):
            self.pipe.enable_model_cpu_offload(device=settings.device)
        else:
            self.pipe = self.pipe.to(settings.device)

    def generate(self, req: ImageRequest) -> Image.Image:
        if self.pipe is None:
            raise RuntimeError("Model is not initialized")

        result = self.pipe(
            prompt=req.prompt,
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


def create_model() -> Flux2KleinModel:
    return Flux2KleinModel()
