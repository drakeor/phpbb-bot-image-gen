from __future__ import annotations

import io
import random

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

Size = tuple[int, int]

# Each generation bucket maps to a crop window at an exact conventional ratio and
# the output sizes reachable from that window by downscale alone.
STANDARD_TARGETS: dict[Size, tuple[Size, tuple[Size, ...]]] = {
    (1344, 768): ((1344, 756), ((1280, 720), (1024, 576))),
    (1152, 896): ((1152, 864), ((1024, 768), (800, 600), (640, 480))),
    (1216, 832): ((1215, 810), ((1200, 800), (900, 600), (720, 480))),
    (1024, 1024): ((1024, 1024), ((800, 800), (640, 640))),
    (768, 1344): ((756, 1344), ((720, 1280), (576, 1024))),
    (896, 1152): ((864, 1152), ((768, 1024), (600, 800), (480, 640))),
    (832, 1216): ((810, 1215), ((800, 1200), (600, 900), (480, 720))),
}

CROP_MARGIN_RANGE = (0.02, 0.06)
NOISE_SIGMA_RANGE = (1.0, 3.0)
BLUR_RADIUS_RANGE = (0.3, 0.8)
CONTRAST_FACTOR_RANGE = (0.85, 0.95)
PIXELATE_FACTOR_RANGE = (2, 4)
JPEG_QUALITY_RANGE = (75, 90)


def apply(image: Image.Image, settings, rng=random) -> Image.Image:
    """Run the crop, downscale, and filter gates over a generated image."""
    if not settings.variation_enabled:
        return image
    image = _resize_stage(image, settings, rng)
    return _filter_stage(image, settings, rng)


def _resize_stage(image: Image.Image, settings, rng) -> Image.Image:
    target = STANDARD_TARGETS.get((image.width, image.height))
    offset = rng.random() < settings.p_random_crop
    to_standard = rng.random() < settings.p_standard_size and target is not None

    if to_standard:
        (ratio_w, ratio_h), outputs = target
        margin = rng.uniform(*CROP_MARGIN_RANGE) if offset else 0.0
        image = _crop_to_ratio(image, ratio_w, ratio_h, margin, offset, rng)
        out_w, out_h = rng.choice(list(outputs))
        if out_w <= image.width and out_h <= image.height:
            image = image.resize((out_w, out_h), Image.Resampling.LANCZOS)
        return image

    if offset:
        margin = rng.uniform(*CROP_MARGIN_RANGE)
        image = _crop_to_ratio(image, image.width, image.height, margin, True, rng)
    return image


def _crop_to_ratio(
    image: Image.Image,
    ratio_w: int,
    ratio_h: int,
    margin: float,
    offset: bool,
    rng,
) -> Image.Image:
    """Crop a window of the given dimensions, shrunk by margin and placed by offset.

    The scale is capped at 1.0 so a zero margin keeps the window at exactly the
    dimensions passed in, which is what holds the conventional ratio exact.
    """
    scale = min(image.width / ratio_w, image.height / ratio_h, 1.0) * (1.0 - margin)
    win_w = min(image.width, max(1, int(round(ratio_w * scale))))
    win_h = min(image.height, max(1, int(round(ratio_h * scale))))
    left = _place(image.width, win_w, offset, rng)
    top = _place(image.height, win_h, offset, rng)
    return image.crop((left, top, left + win_w, top + win_h))


def _place(span: int, window: int, offset: bool, rng) -> int:
    slack = span - window
    if slack <= 0:
        return 0
    return rng.randint(0, slack) if offset else slack // 2


def _filter_stage(image: Image.Image, settings, rng) -> Image.Image:
    if rng.random() < settings.p_noise:
        image = _add_noise(image, rng.uniform(*NOISE_SIGMA_RANGE))
    if rng.random() < settings.p_blur:
        radius = rng.uniform(*BLUR_RADIUS_RANGE)
        image = image.filter(ImageFilter.GaussianBlur(radius))
    if rng.random() < settings.p_contrast:
        factor = rng.uniform(*CONTRAST_FACTOR_RANGE)
        image = ImageEnhance.Contrast(image).enhance(factor)
    if rng.random() < settings.p_pixelate:
        image = _pixelate(image, rng.randint(*PIXELATE_FACTOR_RANGE))
    if rng.random() < settings.p_jpeg:
        image = _jpeg_roundtrip(image, rng.randint(*JPEG_QUALITY_RANGE))
    return image


def _add_noise(image: Image.Image, sigma: float) -> Image.Image:
    """Add per-channel gaussian noise centered on zero.

    PIL's effect_noise produces gaussian values centered on 128, so the add with
    an offset of -128 leaves the channel mean where it was.
    """
    image = image.convert("RGB")
    channels = [
        ImageChops.add(
            channel,
            Image.effect_noise(image.size, sigma),
            scale=1.0,
            offset=-128,
        )
        for channel in image.split()
    ]
    return Image.merge("RGB", channels)


def _pixelate(image: Image.Image, factor: int) -> Image.Image:
    small = image.resize(
        (max(1, image.width // factor), max(1, image.height // factor)),
        Image.Resampling.BILINEAR,
    )
    return small.resize((image.width, image.height), Image.Resampling.NEAREST)


def _jpeg_roundtrip(image: Image.Image, quality: int) -> Image.Image:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as decoded:
        return decoded.convert("RGB")
