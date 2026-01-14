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
