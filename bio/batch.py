from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Callable, Optional
import threading

from .engine import SUPPORTED_EXTS, process_image
from .results import ProcessResult
from .settings import OptimizeSettings


@dataclass(frozen=True)
class BatchSummary:
    total_files: int
    processed: int
    skipped: int
    total_src_bytes: int
    total_out_bytes: int

    @property
    def saved_bytes(self) -> int:
        return max(0, self.total_src_bytes - self.total_out_bytes)

    @property
    def saved_percent(self) -> float:
        if self.total_src_bytes <= 0:
            return 0.0
        return (self.saved_bytes / self.total_src_bytes) * 100.0


def _is_relative_to(child: Path, parent: Path) -> bool:
    """Compat helper for Python < 3.9 Path.is_relative_to()."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def iter_images(
    paths: Sequence[Path],
    recursive: bool = True,
    exclude_dir: Optional[Path] = None,
) -> Iterable[Path]:
    """
    Yield supported image paths from a mixture of files and directories.

    exclude_dir:
        If provided, any files inside this directory will be skipped.
        (Prevents re-processing output files when output_dir is inside input_dir.)
    """
    exclude_resolved = exclude_dir.resolve() if exclude_dir else None

    for p in paths:
        p = Path(p)

        # If it's a file, just yield it if supported and not excluded
        if p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTS:
                if exclude_resolved and _is_relative_to(p.resolve(), exclude_resolved):
                    continue
                yield p
            continue

        # If it's a directory, walk it
        if p.is_dir():
            pattern = "**/*" if recursive else "*"
            for f in p.glob(pattern):
                if not f.is_file():
                    continue
                if f.suffix.lower() not in SUPPORTED_EXTS:
                    continue

                if exclude_resolved and _is_relative_to(f.resolve(), exclude_resolved):
                    continue

                yield f


def process_batch(
    inputs: Sequence[Path],
    settings: OptimizeSettings,
    recursive: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> tuple[List[ProcessResult], BatchSummary]:
    results: List[ProcessResult] = []

    total_src = 0
    total_out = 0
    processed = 0
    skipped = 0
    total_files = 0

    image_list = list(iter_images(inputs, recursive=recursive, exclude_dir=settings.output_dir))
    total = len(image_list)

    for idx, img_path in enumerate(image_list, start=1):
        if cancel_event and cancel_event.is_set():
            break

        if progress_callback:
            progress_callback(idx, total)

        total_files += 1
        r = process_image(img_path, settings)
        results.append(r)

        total_src += r.src_bytes
        total_out += r.out_bytes

        if r.out_path is None:
            skipped += 1
        else:
            processed += 1

    summary = BatchSummary(
        total_files=total_files,
        processed=processed,
        skipped=skipped,
        total_src_bytes=total_src,
        total_out_bytes=total_out,
    )
    return results, summary
