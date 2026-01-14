from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

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


def iter_images(paths: Sequence[Path], recursive: bool = True) -> Iterable[Path]:
    """
    Yield supported image paths from a mixture of files and directories.
    """
    for p in paths:
        p = Path(p)

        if p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTS:
                yield p
            continue

        if p.is_dir():
            pattern = "**/*" if recursive else "*"
            for f in p.glob(pattern):
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
                    yield f


def process_batch(
    inputs: Sequence[Path],
    settings: OptimizeSettings,
    recursive: bool = True,
) -> tuple[List[ProcessResult], BatchSummary]:
    results: List[ProcessResult] = []

    total_src = 0
    total_out = 0
    processed = 0
    skipped = 0
    total_files = 0

    for img_path in iter_images(inputs, recursive=recursive):
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
