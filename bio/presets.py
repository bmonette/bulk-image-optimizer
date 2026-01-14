from __future__ import annotations

from .settings import OptimizeSettings


def apply_preset(name: str, base: OptimizeSettings) -> OptimizeSettings:
    name = name.lower()

    if name == "blog":
        return base.__class__(
            **{**base.__dict__,
               "jpeg_quality": 82,
               "strip_metadata": True,
               "max_width": 1600,
               "output_format": "keep"}
        )

    if name == "ecommerce":
        return base.__class__(
            **{**base.__dict__,
               "jpeg_quality": 88,
               "strip_metadata": True,
               "max_width": 2000}
        )

    if name == "aggressive":
        return base.__class__(
            **{**base.__dict__,
               "jpeg_quality": 70,
               "strip_metadata": True,
               "only_if_smaller": True}
        )

    if name == "webp":
        return base.__class__(
            **{**base.__dict__,
               "output_format": "webp",
               "webp_quality": 80,
               "strip_metadata": True}
        )

    raise ValueError(f"Unknown preset: {name}")
