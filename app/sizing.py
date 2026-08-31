from __future__ import annotations

import random
from typing import Mapping, Sequence

from app.schemas import ImageRequest

Size = tuple[int, int]
Buckets = Mapping[str, Sequence[Size]]

ORIENTATIONS = ("wide", "tall", "square")

# Every entry is a multiple of 64 in both dimensions and holds a pixel area near
# 1024**2 (1,048,576), which is the range these families were trained across.
MEGAPIXEL_BUCKETS: dict[str, list[Size]] = {
    "wide": [(1152, 896), (1216, 832), (1344, 768)],
    "tall": [(896, 1152), (832, 1216), (768, 1344)],
    "square": [(1024, 1024)],
}


def choose_size(buckets: Buckets, weights: Mapping[str, float], rng=random) -> Size:
    """Pick an orientation by weight, then an entry inside that orientation uniformly."""
    groups = [name for name in ORIENTATIONS if buckets.get(name)]
    if not groups:
        raise ValueError("size_buckets holds no entries")

    group_weights = [max(0.0, float(weights.get(name, 0.0))) for name in groups]
    if sum(group_weights) <= 0.0:
        group_weights = [1.0] * len(groups)

    group = rng.choices(groups, weights=group_weights, k=1)[0]
    width, height = rng.choice(list(buckets[group]))
    return int(width), int(height)


def resolve_size(req: ImageRequest, model, settings, rng=random) -> ImageRequest:
    """Fill width and height from the model's buckets when the caller omitted both.

    A request carrying either dimension passes through untouched, so an explicit
    size from the phpBB bot reaches the pipeline exactly as sent.
    """
    if not settings.variation_enabled:
        return req
    if req.width is not None or req.height is not None:
        return req

    buckets = getattr(model, "size_buckets", None)
    if not buckets:
        return req

    width, height = choose_size(buckets, settings.orientation_weights(), rng)
    return req.model_copy(update={"width": width, "height": height})
