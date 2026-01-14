from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import os
import tempfile

from PIL import Image, ImageOps

from .results import ProcessResult
from .settings import OptimizeSettings


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Maps "keep" to the correct encoder format based on source extension.
EXT_TO_FORMAT = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
}

FORMAT_TO_EXT = {
    "jpeg": ".jpg",
    "png": ".png",
    "webp": ".webp",
}


def process_image(src_path: Path, s: OptimizeSettings) -> ProcessResult:
    src_path = Path(src_path)

    src_bytes = _file_size(src_path)

    if src_path.suffix.lower() not in SUPPORTED_EXTS:
        return ProcessResult(
            src_path=src_path,
            out_path=None,
            src_bytes=src_bytes,
            out_bytes=src_bytes,
            changed=False,
            skipped_reason="unsupported_extension",
        )

    s = _normalize_settings(s)

    # Ensure output directory exists
    s.output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(src_path) as im:
        im.load()

        # Auto-orient (important if we're stripping EXIF)
        if s.auto_orient:
            im = ImageOps.exif_transpose(im)

        # Center crop (optional)
        im = _apply_center_crop(im, s)

        # Resize (optional)
        im = _apply_resize(im, s)

        out_format = _choose_output_format(src_path, s)
        out_path = _build_output_path(src_path, s, out_format)

        if out_path.exists() and not s.overwrite:
            out_path = _next_available_name(out_path)

        # If converting to JPEG and image has alpha, flatten onto background.
        if out_format == "jpeg" and _has_alpha(im):
            im = _flatten_alpha(im, s.jpeg_background)

        # Write to a temp file first (lets us enforce only_if_smaller safely)
        tmp_path = _save_to_temp(im, s, out_format, s.strip_metadata)

        tmp_bytes = _file_size(tmp_path)

        if s.only_if_smaller and tmp_bytes >= src_bytes:
            # Not smaller -> discard temp output
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

            return ProcessResult(
                src_path=src_path,
                out_path=None,
                src_bytes=src_bytes,
                out_bytes=src_bytes,
                changed=False,
                skipped_reason="not_smaller",
            )

        # Move temp file to final destination (atomic replace if overwrite)
        _finalize_output(tmp_path, out_path, overwrite=s.overwrite)

        out_bytes = _file_size(out_path)

        return ProcessResult(
            src_path=src_path,
            out_path=out_path,
            src_bytes=src_bytes,
            out_bytes=out_bytes,
            changed=True,
            skipped_reason=None,
        )


def _normalize_settings(s: OptimizeSettings) -> OptimizeSettings:
    # Guardrail: if stripping metadata, force auto-orient to avoid "rotated wrong" results.
    if s.strip_metadata and not s.auto_orient:
        s = replace(s, auto_orient=True)
    return s


def _choose_output_format(src_path: Path, s: OptimizeSettings) -> str:
    if s.output_format == "keep":
        fmt = EXT_TO_FORMAT.get(src_path.suffix.lower())
        if not fmt:
            # Shouldn't happen due to SUPPORTED_EXTS check
            return "jpeg"
        return fmt
    return s.output_format


def _build_output_path(src_path: Path, s: OptimizeSettings, out_format: str) -> Path:
    ext = FORMAT_TO_EXT[out_format]
    stem = src_path.stem + s.suffix
    return s.output_dir / f"{stem}{ext}"


def _next_available_name(path: Path) -> Path:
    # photo_optimized.jpg -> photo_optimized (1).jpg
    base = path.with_suffix("")
    ext = path.suffix
    i = 1
    while True:
        candidate = Path(f"{base} ({i}){ext}")
        if not candidate.exists():
            return candidate
        i += 1


def _save_to_temp(im: Image.Image, s: OptimizeSettings, out_format: str, strip_metadata: bool) -> Path:
    # Create temp file in output dir so move/rename is cheap
    fd, tmp_name = tempfile.mkstemp(prefix="bio_", suffix=FORMAT_TO_EXT[out_format], dir=str(s.output_dir))
    os.close(fd)
    tmp_path = Path(tmp_name)

    save_kwargs = _build_save_kwargs(im, s, out_format, strip_metadata)

    # Important: Pillow chooses encoder by format=... not extension alone
    im.save(tmp_path, format=out_format.upper(), **save_kwargs)

    return tmp_path


def _build_save_kwargs(im: Image.Image, s: OptimizeSettings, out_format: str, strip_metadata: bool) -> dict:
    kwargs: dict = {}

    # If strip_metadata is False, keep EXIF if present (JPEG usually).
    # If True, we simply don't pass exif / pnginfo / etc.
    if not strip_metadata:
        exif = im.info.get("exif")
        if exif is not None:
            kwargs["exif"] = exif

        icc = im.info.get("icc_profile")
        if icc is not None:
            kwargs["icc_profile"] = icc

    if out_format == "jpeg":
        kwargs["quality"] = int(s.jpeg_quality)
        kwargs["optimize"] = bool(s.jpeg_optimize)
        kwargs["progressive"] = bool(s.jpeg_progressive)

    elif out_format == "png":
        kwargs["compress_level"] = int(s.png_compress_level)
        kwargs["optimize"] = bool(s.png_optimize)

    elif out_format == "webp":
        kwargs["quality"] = int(s.webp_quality)
        kwargs["lossless"] = bool(s.webp_lossless)
        kwargs["method"] = int(s.webp_method)

    return kwargs


def _finalize_output(tmp_path: Path, out_path: Path, overwrite: bool) -> None:
    if overwrite and out_path.exists():
        out_path.unlink()
    tmp_path.replace(out_path)


def _flatten_alpha(im: Image.Image, background_rgb: tuple[int, int, int]) -> Image.Image:
    # Ensure we are in RGBA so alpha exists
    rgba = im.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, background_rgb + (255,))
    comp = Image.alpha_composite(bg, rgba)
    return comp.convert("RGB")


def _has_alpha(im: Image.Image) -> bool:
    if im.mode in ("RGBA", "LA"):
        return True
    if im.mode == "P" and "transparency" in im.info:
        return True
    return False


def _file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except FileNotFoundError:
        return 0


def _apply_resize(im: Image.Image, s: OptimizeSettings) -> Image.Image:
    """
    Apply resizing based on settings.
    - scale_percent takes precedence if set
    - otherwise max_width/max_height define a bounding box
    - never upscale unless allow_upscale=True
    """
    w, h = im.size

    # 1) Percent scaling
    if s.scale_percent is not None:
        pct = max(1, int(s.scale_percent))
        new_w = max(1, (w * pct) // 100)
        new_h = max(1, (h * pct) // 100)

        if not s.allow_upscale and (new_w > w or new_h > h):
            return im

        if (new_w, new_h) == (w, h):
            return im

        return im.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # 2) Fit within max dimensions
    if s.max_width is None and s.max_height is None:
        return im

    max_w = s.max_width if s.max_width is not None else w
    max_h = s.max_height if s.max_height is not None else h

    # compute scale factor that keeps aspect ratio
    scale = min(max_w / w, max_h / h)

    if not s.allow_upscale and scale >= 1.0:
        return im

    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    if (new_w, new_h) == (w, h):
        return im

    return im.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _apply_center_crop(im: Image.Image, s: OptimizeSettings) -> Image.Image:
    """
    Center-crop an image to the requested aspect ratio (width/height).

    Example ratios:
      - 1.0 for square (1:1)
      - 16/9 for widescreen
      - 4/3 for classic photo

    If s.crop_ratio is None, cropping is skipped.
    """
    if s.crop_ratio is None:
        return im

    ratio = float(s.crop_ratio)
    if ratio <= 0:
        return im  # ignore invalid values safely

    w, h = im.size
    if w <= 0 or h <= 0:
        return im

    current = w / h

    # Already basically at ratio (avoid tiny rounding crops)
    if abs(current - ratio) < 1e-6:
        return im

    if current > ratio:
        # Image is too wide -> crop width
        new_w = int(h * ratio)
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        # Image is too tall -> crop height
        new_h = int(w / ratio)
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)

    return im.crop(box)
