from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .batch import BatchSummary
from .results import ProcessResult


@dataclass(frozen=True)
class FileReport:
    src_path: str
    out_path: Optional[str]
    src_bytes: int
    out_bytes: int
    saved_bytes: int
    saved_percent: float
    changed: bool
    skipped_reason: Optional[str]


@dataclass(frozen=True)
class BatchReport:
    created_utc: str
    summary: dict
    files: List[FileReport]


def build_report(results: List[ProcessResult], summary: BatchSummary) -> BatchReport:
    created_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    files: List[FileReport] = []
    for r in results:
        files.append(
            FileReport(
                src_path=str(r.src_path),
                out_path=str(r.out_path) if r.out_path else None,
                src_bytes=r.src_bytes,
                out_bytes=r.out_bytes,
                saved_bytes=r.saved_bytes,
                saved_percent=round(r.saved_percent, 2),
                changed=r.changed,
                skipped_reason=r.skipped_reason,
            )
        )

    summary_dict = {
        "total_files": summary.total_files,
        "processed": summary.processed,
        "skipped": summary.skipped,
        "total_src_bytes": summary.total_src_bytes,
        "total_out_bytes": summary.total_out_bytes,
        "saved_bytes": summary.saved_bytes,
        "saved_percent": round(summary.saved_percent, 2),
    }

    return BatchReport(created_utc=created_utc, summary=summary_dict, files=files)


def save_report_json(report: BatchReport, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, ensure_ascii=False)
