from __future__ import annotations

import argparse
from pathlib import Path

from .batch import process_batch
from .report import build_report, save_report_csv, save_report_json
from .settings import OptimizeSettings


def _parse_ratio(text: str) -> float:
    """
    Accept either:
      - "1:1"
      - "16:9"
      - "1.7777"
    """
    t = text.strip()
    if ":" in t:
        a, b = t.split(":", 1)
        num = float(a)
        den = float(b)
        if den == 0:
            raise ValueError("ratio denominator cannot be 0")
        return num / den
    return float(t)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bio",
        description="Bulk Image Optimizer (engine + CLI)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    opt = sub.add_parser("optimize", help="Optimize images in files/folders")
    opt.add_argument("inputs", nargs="+", help="Files and/or folders to process")

    # Output
    opt.add_argument("--out", required=True, help="Output directory")
    opt.add_argument("--overwrite", action="store_true", help="Overwrite output files if they exist")
    opt.add_argument(
        "--only-if-smaller",
        action="store_true",
        default=True,
        help="Only write output when smaller (default: on)",
    )
    opt.add_argument("--dry-run", action="store_true", help="Estimate savings without writing files")
    opt.add_argument(
        "--allow-bigger-for-metadata",
        action="store_true",
        help="If stripping metadata, still write even if output isn't smaller",
    )
    opt.add_argument("--suffix", default="_optimized", help="Filename suffix (default: _optimized)")
    opt.add_argument("--no-recursive", action="store_true", help="Do not scan folders recursively")

    # Format
    fmt = opt.add_mutually_exclusive_group()
    fmt.add_argument("--keep", action="store_true", help="Keep original format (default)")
    fmt.add_argument("--jpeg", action="store_true", help="Output JPEG")
    fmt.add_argument("--png", action="store_true", help="Output PNG")
    fmt.add_argument("--webp", action="store_true", help="Output WebP")

    # Metadata
    opt.add_argument("--strip-metadata", action="store_true", default=True, help="Strip metadata (default: on)")
    opt.add_argument("--keep-metadata", action="store_true", help="Keep metadata (overrides --strip-metadata)")

    # Resize
    opt.add_argument("--max-width", type=int, default=None, help="Max width (keeps aspect)")
    opt.add_argument("--max-height", type=int, default=None, help="Max height (keeps aspect)")
    opt.add_argument("--scale", type=int, default=None, help="Scale percent (e.g. 50)")
    opt.add_argument("--allow-upscale", action="store_true", help="Allow enlarging pixels")

    # Crop
    opt.add_argument("--crop", type=str, default=None, help='Center crop ratio, e.g. "1:1" or "16:9"')

    # Encoder knobs (keep it minimal for v1 CLI)
    opt.add_argument("--quality", type=int, default=82, help="JPEG quality (1-100), default 82")
    opt.add_argument("--webp-quality", type=int, default=80, help="WebP quality (1-100), default 80")
    opt.add_argument("--webp-lossless", action="store_true", help="WebP lossless mode")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "optimize":
        inputs = [Path(p) for p in args.inputs]
        out_dir = Path(args.out)

        # Output format selection
        if args.jpeg:
            out_fmt = "jpeg"
        elif args.png:
            out_fmt = "png"
        elif args.webp:
            out_fmt = "webp"
        else:
            out_fmt = "keep"  # default

        # Metadata
        strip_metadata = True
        if args.keep_metadata:
            strip_metadata = False

        crop_ratio = _parse_ratio(args.crop) if args.crop else None

        settings = OptimizeSettings(
            output_dir=out_dir,
            output_format=out_fmt,
            overwrite=bool(args.overwrite),
            only_if_smaller=bool(args.only_if_smaller),
            write_even_if_bigger_when_stripping_metadata=bool(args.allow_bigger_for_metadata),
            suffix=str(args.suffix),
            strip_metadata=strip_metadata,
            auto_orient=True,  # keep this sane for CLI v1
            max_width=args.max_width,
            max_height=args.max_height,
            scale_percent=args.scale,
            allow_upscale=bool(args.allow_upscale),
            crop_ratio=crop_ratio,
            jpeg_quality=int(args.quality),
            webp_quality=int(args.webp_quality),
            webp_lossless=bool(args.webp_lossless),
            dry_run=bool(args.dry_run),
        )

        results, summary = process_batch(
            inputs,
            settings,
            recursive=not bool(args.no_recursive),
        )

        # Print summary
        print("\n=== Batch Summary ===")
        print("Total found:", summary.total_files)
        print("Processed  :", summary.processed)
        print("Skipped    :", summary.skipped)
        print(f"Saved      : {summary.saved_bytes} bytes ({summary.saved_percent:.1f}%)")

        # Skip reasons breakdown
        reasons: dict[str, int] = {}
        for r in results:
            if r.out_path is None and r.skipped_reason:
                reasons[r.skipped_reason] = reasons.get(r.skipped_reason, 0) + 1

        if reasons:
            print("\nSkip reasons:")
            for k, v in sorted(reasons.items(), key=lambda x: (-x[1], x[0])):
                print(f"  {k}: {v}")

        # Reports
        report = build_report(results, summary)

        json_path = out_dir / "report.json"
        save_report_json(report, json_path)

        csv_path = out_dir / "report.csv"
        save_report_csv(report, csv_path)

        print("\nReport written:", json_path)
        print("CSV written   :", csv_path)
        return 0

    parser.print_help()
    return 2
