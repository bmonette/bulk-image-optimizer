from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


# Output formats we support in v1.
# "keep" means keep the original format.
OutputFormat = Literal["keep", "jpeg", "png", "webp"]


@dataclass(frozen=True)
class OptimizeSettings:
    """
    All user-configurable knobs for image processing.

    We keep this as a pure data object (no logic) so:
    - it's easy to test
    - easy to save/load later (JSON)
    - easy for a GUI to edit
    """

    # ----- Output handling -----
    output_dir: Path
    output_format: OutputFormat = "keep"
    overwrite: bool = False
    only_if_smaller: bool = True

    # Naming
    suffix: str = "_optimized"  # e.g. photo.jpg -> photo_optimized.jpg

    # ----- Metadata -----
    strip_metadata: bool = True
    auto_orient: bool = True  # should be forced ON if strip_metadata is ON

    # ----- Resize -----
    # If all resize fields are None, resizing is skipped.
    max_width: Optional[int] = None
    max_height: Optional[int] = None
    scale_percent: Optional[int] = None  # e.g. 50 means 50%

    # ----- Crop (v1: center crop by aspect ratio) -----
    # If crop_ratio is None, cropping is skipped.
    # Example: crop_ratio=1.0 for square, 16/9 for widescreen
    crop_ratio: Optional[float] = None

    # ----- JPEG encoding -----
    jpeg_quality: int = 82
    jpeg_progressive: bool = True
    jpeg_optimize: bool = True

    # ----- PNG encoding -----
    # Pillow uses "compress_level" (0-9). Higher = smaller but slower.
    png_compress_level: int = 9
    png_optimize: bool = True

    # ----- WebP encoding -----
    webp_quality: int = 80
    webp_lossless: bool = False
    webp_method: int = 4  # 0-6, higher = smaller but slower

    # ----- JPEG flattening behavior (when source has transparency) -----
    # Only used when saving to JPEG and the image has alpha.
    jpeg_background: tuple[int, int, int] = (255, 255, 255)
