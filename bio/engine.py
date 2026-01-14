from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

from .results import ProcessResult
from .settings import OptimizeSettings


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def process_image(src_path: Path, s: OptimizeSettings) -> ProcessResult:
    """
    Process a single image according to settings.

    This function will eventually:
    - load + normalize
    - optional crop/resize
    - optional metadata strip
    - encode/save in chosen format with compression settings
    - return stats
    """
    src_path = Path(src_path)

    if src_path.suffix.lower() not in SUPPORTED_EXTS:
        return ProcessResult(
            src_path=src_path,
            out_path=None,
            src_bytes=_file_size(src_path),
            out_bytes=_file_size(src_path),
            changed=False,
            skipped_reason="unsupported_extension",
        )

    # Guardrail: if metadata stripping is ON, we should ensure auto-orient is ON
    if s.strip_metadata and not s.auto_orient:
        # In v1 we’ll just enforce it rather than surprise the user with rotated images.
        # (Later we can expose a UI warning.)
        object.__setattr__(s, "auto_orient", True)  # NOTE: frozen dataclass workaround avoided later

    # Load
    with Image.open(src_path) as im:
        im.load()  # force file read now (so we can safely close file handle later)

        # Normalize orientation (if enabled)
        if s.auto_orient:
            im = ImageOps.exif_transpose(im)

        # TODO (next steps):
        # - crop center to ratio if s.crop_ratio is set
        # - resize if max_width/max_height/scale_percent are set
        # - determine output path + format
        # - flatten if saving JPEG and image has alpha
        # - strip metadata on save
        # - encode with correct parameters
        # - only_if_smaller logic

    # Temporary placeholder until we implement saving:
    src_bytes = _file_size(src_path)
    return ProcessResult(
        src_path=src_path,
        out_path=None,
        src_bytes=src_bytes,
        out_bytes=src_bytes,
        changed=False,
        skipped_reason="not_implemented_yet",
    )


def _file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except FileNotFoundError:
        return 0
