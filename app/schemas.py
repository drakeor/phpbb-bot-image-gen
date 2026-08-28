from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ImageRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    n: int = Field(default=1, ge=1, le=10)
    width: Optional[int] = Field(default=None, ge=64, le=2048)
    height: Optional[int] = Field(default=None, ge=64, le=2048)
    guidance_scale: Optional[float] = Field(default=None, ge=0.0, le=50.0)
    steps: Optional[int] = Field(default=None, ge=1, le=150)
    model: Optional[str] = None


class ImageData(BaseModel):
    b64_json: str


class ImageResponse(BaseModel):
    created: int
    data: list[ImageData]
