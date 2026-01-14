from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProcessResult:
    """
    Output of processing a single image.

    Keeping it immutable (frozen=True) makes it easier to reason about.
    """
    src_path: Path
    out_path: Optional[Path]  # None if we skipped writing
    src_bytes: int
    out_bytes: int
    changed: bool
    skipped_reason: Optional[str] = None

    @property
    def saved_bytes(self) -> int:
        return max(0, self.src_bytes - self.out_bytes)

    @property
    def saved_percent(self) -> float:
        if self.src_bytes <= 0:
            return 0.0
        return (self.saved_bytes / self.src_bytes) * 100.0
