from __future__ import annotations

import dataclasses
import random

import pytest
from PIL import Image

from app import postprocess, sizing
from app.schemas import ImageRequest
from app.settings import Settings

ONE_MEGAPIXEL = 1024 * 1024


class ScriptedRandom:
    """Deterministic replacement for the random module.

    Values are consumed in order and cycle once exhausted, so a test names the
    exact draw sequence a gate sees.
    """

    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def _next(self) -> float:
        value = self.values[self.index % len(self.values)]
        self.index += 1
        return value

    def random(self) -> float:
        return self._next()

    def uniform(self, low, high):
        return low + (high - low) * self._next()

    def randint(self, low, high):
        return low + int(self._next() * (high - low + 1))

    def choice(self, seq):
        seq = list(seq)
        return seq[min(int(self._next() * len(seq)), len(seq) - 1)]

    def choices(self, population, weights=None, k=1):
        return [self.choice(population) for _ in range(k)]


class BucketModel:
    alias = "bucket"
    model_id = "test/bucket"
    size_buckets = sizing.MEGAPIXEL_BUCKETS


class PlainModel:
    alias = "plain"
    model_id = "test/plain"


def _settings(monkeypatch, **overrides) -> Settings:
    monkeypatch.setenv("SD_API_KEY", "secret")
    base = Settings.from_env()
    return dataclasses.replace(base, **overrides) if overrides else base


def test_default_probabilities_match_the_agreed_rates(monkeypatch):
    settings = _settings(monkeypatch)

    assert settings.size_weight_wide == 0.55
    assert settings.size_weight_tall == 0.35
    assert settings.size_weight_square == 0.10
    assert settings.p_noise == 0.03
    assert settings.p_blur == 0.03
    assert settings.p_contrast == 0.08
    assert settings.p_pixelate == 0.02
    assert settings.p_jpeg == 0.30


def test_probability_outside_zero_to_one_is_rejected(monkeypatch):
    monkeypatch.setenv("SD_API_KEY", "secret")
    monkeypatch.setenv("SD_P_JPEG", "1.5")

    with pytest.raises(ValueError, match="must be between 0 and 1"):
        Settings.from_env()


def test_every_bucket_aligns_to_64_near_one_megapixel():
    for group, entries in sizing.MEGAPIXEL_BUCKETS.items():
        for width, height in entries:
            assert width % 64 == 0, f"{group} {width}x{height}"
            assert height % 64 == 0, f"{group} {width}x{height}"
            drift = abs(width * height - ONE_MEGAPIXEL) / ONE_MEGAPIXEL
            assert drift < 0.05, f"{group} {width}x{height} drifts {drift:.3f}"


def test_orientation_groups_hold_the_expected_directions():
    for width, height in sizing.MEGAPIXEL_BUCKETS["wide"]:
        assert width > height
    for width, height in sizing.MEGAPIXEL_BUCKETS["tall"]:
        assert height > width
    for width, height in sizing.MEGAPIXEL_BUCKETS["square"]:
        assert width == height


def test_every_bucket_has_a_standard_target():
    entries = {
        entry for group in sizing.MEGAPIXEL_BUCKETS.values() for entry in group
    }
    assert entries == set(postprocess.STANDARD_TARGETS)


def test_standard_targets_hold_an_exact_ratio_and_fit_their_bucket():
    for bucket, (window, outputs) in postprocess.STANDARD_TARGETS.items():
        assert window[0] <= bucket[0] and window[1] <= bucket[1]
        window_ratio = window[0] / window[1]
        for out_w, out_h in outputs:
            assert out_w <= window[0] and out_h <= window[1]
            assert abs(out_w / out_h - window_ratio) < 1e-9


def test_orientation_weights_drive_the_draw():
    rng = random.Random(20240831)
    weights = {"wide": 0.55, "tall": 0.35, "square": 0.10}
    counts = {"wide": 0, "tall": 0, "square": 0}

    for _ in range(20000):
        width, height = sizing.choose_size(sizing.MEGAPIXEL_BUCKETS, weights, rng)
        if width > height:
            counts["wide"] += 1
        elif height > width:
            counts["tall"] += 1
        else:
            counts["square"] += 1

    assert abs(counts["wide"] / 20000 - 0.55) < 0.02
    assert abs(counts["tall"] / 20000 - 0.35) < 0.02
    assert abs(counts["square"] / 20000 - 0.10) < 0.02


def test_draw_stays_uniform_inside_an_orientation():
    rng = random.Random(7)
    weights = {"wide": 1.0, "tall": 0.0, "square": 0.0}
    counts: dict[tuple[int, int], int] = {}

    for _ in range(12000):
        size = sizing.choose_size(sizing.MEGAPIXEL_BUCKETS, weights, rng)
        counts[size] = counts.get(size, 0) + 1

    assert set(counts) == set(sizing.MEGAPIXEL_BUCKETS["wide"])
    for count in counts.values():
        assert abs(count / 12000 - 1 / 3) < 0.02


def test_resolve_size_fills_an_omitted_size(monkeypatch):
    settings = _settings(monkeypatch)
    req = ImageRequest(prompt="test")

    resolved = sizing.resolve_size(req, BucketModel(), settings, random.Random(3))

    assert (resolved.width, resolved.height) in postprocess.STANDARD_TARGETS
    assert req.width is None and req.height is None


def test_resolve_size_passes_an_explicit_size_through(monkeypatch):
    settings = _settings(monkeypatch)

    both = ImageRequest(prompt="test", width=512, height=512)
    width_only = ImageRequest(prompt="test", width=900)
    height_only = ImageRequest(prompt="test", height=900)

    assert sizing.resolve_size(both, BucketModel(), settings) is both
    assert sizing.resolve_size(width_only, BucketModel(), settings) is width_only
    assert sizing.resolve_size(height_only, BucketModel(), settings) is height_only


def test_resolve_size_leaves_a_model_without_buckets_alone(monkeypatch):
    settings = _settings(monkeypatch)
    req = ImageRequest(prompt="test")

    assert sizing.resolve_size(req, PlainModel(), settings) is req


def test_resolve_size_is_off_when_variation_is_disabled(monkeypatch):
    settings = _settings(monkeypatch, variation_enabled=False)
    req = ImageRequest(prompt="test")

    assert sizing.resolve_size(req, BucketModel(), settings) is req


def test_standard_gate_crops_and_downscales_to_the_target(monkeypatch):
    settings = _settings(monkeypatch, p_random_crop=0.0, p_standard_size=1.0)
    # offset draw, standard draw, output choice, then five filter draws.
    rng = ScriptedRandom([0.99, 0.01, 0.0, 0.99, 0.99, 0.99, 0.99, 0.99])

    result = postprocess.apply(Image.new("RGB", (1344, 768), "red"), settings, rng)

    assert result.size == (1280, 720)


def test_offset_gate_crops_without_changing_the_ratio(monkeypatch):
    settings = _settings(monkeypatch, p_random_crop=1.0, p_standard_size=0.0)
    rng = ScriptedRandom([0.0, 0.99, 0.5, 0.5, 0.5, 0.99, 0.99, 0.99, 0.99, 0.99])

    source = Image.new("RGB", (1024, 1024), "red")
    result = postprocess.apply(source, settings, rng)

    assert result.width < 1024 and result.height < 1024
    assert result.width == result.height


def test_every_filter_holds_the_image_dimensions(monkeypatch):
    settings = _settings(
        monkeypatch,
        p_random_crop=0.0,
        p_standard_size=0.0,
        p_noise=1.0,
        p_blur=1.0,
        p_contrast=1.0,
        p_pixelate=1.0,
        p_jpeg=1.0,
    )
    rng = ScriptedRandom([0.5])

    result = postprocess.apply(Image.new("RGB", (64, 64), "red"), settings, rng)

    assert result.size == (64, 64)
    assert result.mode == "RGB"


def test_disabled_variation_returns_the_original_image(monkeypatch):
    settings = _settings(monkeypatch, variation_enabled=False)
    source = Image.new("RGB", (1344, 768), "red")

    assert postprocess.apply(source, settings, ScriptedRandom([0.0])) is source


def test_unmapped_size_skips_the_standard_gate(monkeypatch):
    settings = _settings(monkeypatch, p_random_crop=0.0, p_standard_size=1.0)
    rng = ScriptedRandom([0.99, 0.0, 0.99, 0.99, 0.99, 0.99, 0.99])

    source = Image.new("RGB", (640, 400), "red")
    result = postprocess.apply(source, settings, rng)

    assert result.size == (640, 400)
